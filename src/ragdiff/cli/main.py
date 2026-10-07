import json
import logging
import uuid
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Annotated

import typer

from ragdiff.api import RagDiff
from ragdiff.bootstrap.dataset import read_dataset
from ragdiff.config.loader import load_config
from ragdiff.contract import load_app
from ragdiff.llm.litellm_client import LiteLLMClient
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
def run(
    config_path: Annotated[Path, typer.Option("--config", "-c")] = Path("evals.yaml"),
) -> None:
    """Run the configured application over its dataset."""
    config = load_config(config_path)
    if not config.app:
        raise typer.BadParameter("Config must define an 'app' entrypoint")
    if config.metrics:
        raise typer.BadParameter(
            "Metric implementations must be registered through the Python API"
        )
    cases = read_dataset(config.dataset)
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
