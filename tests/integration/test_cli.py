import logging
from pathlib import Path

from typer.testing import CliRunner

from ragdiff.cli.main import app


def test_cli_init_bootstrap_run_report(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    examples = Path(__file__).parents[2] / "examples"
    monkeypatch.syspath_prepend(str(examples))
    runner = CliRunner()
    config = tmp_path / "evals.yaml"

    assert runner.invoke(app, ["init", "--config", str(config)]).exit_code == 0
    assert runner.invoke(app, ["bootstrap", "--config", str(config)]).exit_code == 0
    run_result = runner.invoke(app, ["run", "--config", str(config)])
    assert run_result.exit_code == 0, run_result.output
    run_id = Path(run_result.output.strip()).name
    report_result = runner.invoke(app, ["report", run_id])

    assert report_result.exit_code == 0, report_result.output
    assert (tmp_path / ".ragdiff" / "runs" / run_id / "report.md").is_file()

    logger = logging.getLogger("ragdiff")
    for handler in logger.handlers[:]:
        if getattr(handler, "_ragdiff_owned", False):
            logger.removeHandler(handler)
            handler.close()
