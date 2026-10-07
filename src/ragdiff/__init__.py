import logging

from ragdiff.api import CompareReport, RagDiff
from ragdiff.contract import RunOutput
from ragdiff.errors import RagDiffError

__version__ = "0.1.0"

logging.getLogger("ragdiff").addHandler(logging.NullHandler())

__all__ = ["CompareReport", "RagDiff", "RagDiffError", "RunOutput", "__version__"]
