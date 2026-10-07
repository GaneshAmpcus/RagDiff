import json
import logging

from ragdiff.observability import context
from ragdiff.observability.redaction import redact


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = context.run_id.get()
        record.case_id = context.case_id.get()
        record.variant = context.variant.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "run_id": getattr(record, "run_id", "-"),
            "case_id": getattr(record, "case_id", "-"),
            "variant": getattr(record, "variant", "-"),
            "msg": redact(record.getMessage()),
            "phase": getattr(record, "phase", None),
            "event": getattr(record, "event", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "tokens": getattr(record, "tokens", None),
            "cost": getattr(record, "cost", None),
            "cache_hit": getattr(record, "cache_hit", None),
            "error": self._redacted(getattr(record, "error", None)),
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _redacted(value: object) -> object:
        return redact(value) if isinstance(value, str) else value


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))
