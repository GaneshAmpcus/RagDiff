"""Subprocess entrypoint: run one app variant over a dataset and dump raw records.

Executed inside a git worktree by ``ragdiff.runner.subprocess_runner`` so the
base and head revisions never share an interpreter or module cache. It does not
score; scoring (and the judge model) stays in the parent process.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ragdiff.bootstrap.dataset import read_dataset
from ragdiff.contract import load_app
from ragdiff.runner.executor import execute
from ragdiff.runner.variants import Variant


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ragdiff.runner.worker")
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--config", default="{}")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--out", required=True)
    parser.add_argument("--path", action="append", default=[])
    args = parser.parse_args(argv)

    for entry in reversed(args.path):
        sys.path.insert(0, entry)
    config = json.loads(args.config)
    records = execute(
        read_dataset(args.cases),
        [Variant(name=args.variant, app=load_app(args.entrypoint), config=config)],
        repeats=args.repeats,
    )
    with Path(args.out).open("w", encoding="utf-8") as stream:
        stream.writelines(json.dumps(record.to_dict(), ensure_ascii=False) + "\n" for record in records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
