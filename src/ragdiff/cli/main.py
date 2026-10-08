import json
import logging
import uuid
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Annotated

import typer

from ragdiff.api import RagDiff
from ragdiff.bootstrap.dataset import read_dataset, runnable_cases
from ragdiff.config.loader import load_config
from ragdiff.contract import load_app
from ragdiff.llm.litellm_client import LiteLLMClient
from ragdiff.metrics.builtin import build_builtin_metrics
from ragdiff.observability import context
from ragdiff.observability.logger import setup_logging
from ragdiff.runner.executor import execute
from ragdiff.runner.variants import Variant
from ragdiff.storage.filesystem import FileSystemStorage

app = typer.Typer(help="Evaluate and compare retrieval-augmented generation apps.")


@app.command()
def init(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("evals.yaml"),
) -> None:
    """Write a starter evaluation configuration."""
    if config_path.exists():
        raise typer.BadParameter(f"{config_path} already exists")
    config_path.write_text(
        "app: sample_rag.app:run\n"
        "dataset: .ragdiff/datasets/dataset.jsonl\n"
        "repeats: 1\n"
        "metrics: []\n"
        "thresholds: {}\n",
        encoding="utf-8",
    )
    typer.echo(f"Created {config_path}")


@app.command()
def bootstrap(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("evals.yaml"),
) -> None:
    """Create or load the configured evaluation dataset."""
    config = load_config(config_path)
    llm_client = LiteLLMClient() if config.docs and config.model else None
    cases = RagDiff(config, llm_client=llm_client).bootstrap()
    typer.echo(f"Dataset ready: {config.dataset} ({len(cases)} cases)")


@app.command()
def baseline(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("evals.yaml"),
) -> None:
    """Bootstrap a dataset if needed, then run and score a baseline."""
    config = load_config(config_path)
    llm_client = LiteLLMClient() if config.docs and config.model else None
    result = RagDiff(config, llm_client=llm_client).baseline()
    typer.echo(f"Baseline {result.run_id}: {result.cases} case(s)")
    for metric, stats in sorted(result.summary.items()):
        typer.echo(f"  {metric}: {stats['mean']:.4f} (n={stats['count']})")
    typer.echo(str(Path(".ragdiff") / "runs" / result.run_id))


@app.command()
def run(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("evals.yaml"),
) -> None:
    """Run the configured application over its dataset."""
    config = load_config(config_path)
    if not config.app:
        raise typer.BadParameter("Config must define an 'app' entrypoint")
    cases = runnable_cases(read_dataset(config.dataset))
    metrics = (
        build_builtin_metrics(config.metrics, judge_model=config.judge_model)
        if config.metrics
        else None
    )
    run_id = uuid.uuid4().hex
    run_dir = Path(".ragdiff") / "runs" / run_id
    token = context.run_id.set(run_id)
    try:
        setup_logging(run_dir)
        logger = logging.getLogger("ragdiff.cli")
        logger.info("Run started", extra={"phase": "run", "event": "phase_start"})
        records = execute(
            cases,
            [Variant(name="current", app=load_app(config.app))],
            repeats=config.repeats,
            metrics=metrics,
        )
        storage = FileSystemStorage()
        storage.write_jsonl(
            Path("runs") / run_id / "results.jsonl",
            [record.to_dict() for record in records],
        )
        storage.write_json(
            Path("runs") / run_id / "meta.json",
            {"run_id": run_id, "config": config.model_dump(mode="json")},
        )
        logger.info("Run completed", extra={"phase": "run", "event": "phase_end"})
        typer.echo(str(run_dir))
    except Exception:
        logging.getLogger("ragdiff.cli").exception(
            "Run failed", extra={"phase": "run", "event": "phase_error"}
        )
        raise
    finally:
        context.run_id.reset(token)


@app.command()
def compare(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("evals.yaml"),
    base: Annotated[str | None, typer.Option(help="Base variant name")] = None,
    head: Annotated[str | None, typer.Option(help="Head variant name")] = None,
    base_ref: Annotated[str | None, typer.Option(help="Base git revision")] = None,
    head_ref: Annotated[str | None, typer.Option(help="Head git revision")] = None,
    repository: Annotated[Path, typer.Option(help="Git repo for --base-ref")] = Path("."),
    report_path: Annotated[
        Path | None, typer.Option(help="Also write the Markdown report here")
    ] = None,
) -> None:
    """Compare base vs head (variants or git revisions); exit 1 on a failed gate."""
    config = load_config(config_path)
    ragdiff = RagDiff(config)
    if base_ref or head_ref:
        if not (base_ref and head_ref):
            raise typer.BadParameter("Pass both --base-ref and --head-ref")
        result = ragdiff.compare_refs(
            base_ref=base_ref, head_ref=head_ref, repository=repository
        )
    else:
        if not (base and head):
            raise typer.BadParameter("Pass --base and --head, or both git refs")
        result = ragdiff.compare(base=base, head=head)
    typer.echo(f"Verdict: {result.verdict}")
    if result.attribution:
        typer.echo(
            f"Culprit: {result.attribution.factor} "
            f"(tier {result.attribution.tier}, "
            f"confidence {result.attribution.confidence:.2f})"
        )
        typer.echo(f"Fix: {result.attribution.suggestion}")
    for metric, entry in sorted(result.differences.items()):
        typer.echo(
            f"  {metric}: {entry['delta']:+.4f} "
            f"({len(entry['regressed'])} regressed question(s))"
        )
    typer.echo(str(Path(".ragdiff") / "runs" / result.run_id))
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            FileSystemStorage().read_text(Path("runs") / result.run_id / "report.md"),
            encoding="utf-8",
        )
    if result.verdict == "fail":
        raise typer.Exit(code=1)


@app.command()
def report(
    run_id: Annotated[str, typer.Argument()],
) -> None:
    """Render a Markdown report from a run's result JSONL."""
    storage = FileSystemStorage()
    results = storage.read_jsonl(Path("runs") / run_id / "results.jsonl")
    scores: dict[str, list[float]] = defaultdict(list)
    for record in results:
        for metric, score in record.get("scores", {}).items():
            if isinstance(score, (int, float)):
                scores[metric].append(float(score))
    lines = [
        "# RagDiff run report",
        "",
        f"Run `{run_id}` contains {len(results)} result(s).",
        "",
    ]
    if scores:
        lines.extend(
            [
                "| Metric | Mean | Count |",
                "| --- | ---: | ---: |",
            ]
        )
        lines.extend(
            f"| {metric} | {mean(values):.4f} | {len(values)} |"
            for metric, values in sorted(scores.items())
        )
    else:
        lines.append("No metric scores were recorded.")
    storage.write_text(
        Path("runs") / run_id / "report.md",
        "\n".join(lines) + "\n",
    )
    typer.echo(json.dumps({"run_id": run_id, "results": len(results)}))
