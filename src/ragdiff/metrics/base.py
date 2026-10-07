from typing import Protocol

from ragdiff.bootstrap.dataset import DatasetCase
from ragdiff.contract import RunOutput


class Metric(Protocol):
    name: str

    def score(self, case: DatasetCase, output: RunOutput) -> float: ...
