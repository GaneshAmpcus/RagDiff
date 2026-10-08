from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from ragdiff.bootstrap.dataset import DatasetCase, write_dataset
from ragdiff.errors import RunnerError
from ragdiff.runner.executor import RunRecord
from ragdiff.runner.isolation import git_worktree, isolated_environment


def run_ref(
    *,
    repository: str | Path,
    revision: str,
    entrypoint: str,
    cases: list[DatasetCase],
    variant: str,
    config: dict[str, Any] | None = None,
    repeats: int = 1,
    app_dir: str | Path = ".",
) -> list[RunRecord]:
    """Run the app as it exists at ``revision`` in a throwaway worktree + process."""
    with tempfile.TemporaryDirectory(prefix="ragdiff-run-") as work:
        cases_path = Path(work) / "cases.jsonl"
        out_path = Path(work) / "records.jsonl"
        write_dataset(cases_path, cases)
        with git_worktree(repository, revision) as checkout:
            root = checkout / app_dir
            command = [
                sys.executable,
                "-m",
                "ragdiff.runner.worker",
                "--entrypoint", entrypoint,
                "--cases", str(cases_path),
                "--variant", variant,
                "--config", json.dumps(config or {}),
                "--repeats", str(repeats),
                "--out", str(out_path),
                "--path", str(root),
            ]  # fmt: skip
            completed = subprocess.run(
                command,
                cwd=root,
                env=isolated_environment(),
                capture_output=True,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RunnerError(
                f"Running {revision!r} failed (exit {completed.returncode}):\n"
                f"{completed.stderr.strip()}"
            )
        return [
            RunRecord(**json.loads(line))
            for line in out_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
