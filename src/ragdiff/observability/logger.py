import logging
from pathlib import Path

from ragdiff.observability.formatters import (
    ContextFilter,
    JsonFormatter,
    RedactingFormatter,
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"ragdiff.{name}")


def setup_logging(
    run_dir: str | Path,
    *,
    level: str = "INFO",
    console: bool = True,
    rotating_log: bool = False,
) -> None:
    log_level = logging.getLevelName(level.upper())
    if not isinstance(log_level, int):
        raise ValueError(f"Unknown logging level {level!r}")  # noqa: TRY004
    root = logging.getLogger("ragdiff")
    root.setLevel(log_level)
    for existing in root.handlers[:]:
        if getattr(existing, "_ragdiff_owned", False):
            root.removeHandler(existing)
            existing.close()
    context_filter = ContextFilter()
    if console:
        handler = logging.StreamHandler()
        handler._ragdiff_owned = True  # type: ignore[attr-defined]
        handler.addFilter(context_filter)
        handler.setFormatter(
            RedactingFormatter("%(levelname)s %(variant)s %(case_id)s %(message)s")
        )
        root.addHandler(handler)
    directory = Path(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(directory / "run.log.jsonl", encoding="utf-8")
    file_handler._ragdiff_owned = True  # type: ignore[attr-defined]
    file_handler.addFilter(context_filter)
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)
    if rotating_log:
        from logging.handlers import RotatingFileHandler

        rotating_handler = RotatingFileHandler(
            directory.parent / "ragdiff.log",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        rotating_handler._ragdiff_owned = True  # type: ignore[attr-defined]
        rotating_handler.addFilter(context_filter)
        rotating_handler.setFormatter(JsonFormatter())
        root.addHandler(rotating_handler)
