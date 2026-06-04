from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Risk(StrEnum):
    READ_ONLY = "read-only"
    MUTATING = "mutating"


@dataclass(frozen=True)
class Operation:
    name: str
    description: str
    command: tuple[str, ...]
    risk: Risk = Risk.READ_ONLY
    timeout_seconds: int = 60


@dataclass(frozen=True)
class ExecutionResult:
    operation: Operation
    return_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0

