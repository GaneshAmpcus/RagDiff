from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def git_worktree(repository: str | Path, revision: str) -> Iterator[Path]:
    """Create a temporary worktree for a revision and always remove it."""
    repo = Path(repository).resolve()
    with tempfile.TemporaryDirectory(prefix="ragdiff-worktree-") as directory:
        worktree = Path(directory) / "checkout"
        subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), revision],
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            yield worktree
        finally:
            subprocess.run(
                ["git", "-C", str(repo), "worktree", "remove", "--force", str(worktree)],
                check=True,
                capture_output=True,
                text=True,
            )


def isolated_environment(
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    environment = os.environ.copy()
    if overrides:
        environment.update(overrides)
    return environment
