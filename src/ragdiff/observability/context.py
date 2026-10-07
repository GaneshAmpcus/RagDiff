from contextvars import ContextVar

run_id: ContextVar[str] = ContextVar("ragdiff_run_id", default="-")
case_id: ContextVar[str] = ContextVar("ragdiff_case_id", default="-")
variant: ContextVar[str] = ContextVar("ragdiff_variant", default="-")
