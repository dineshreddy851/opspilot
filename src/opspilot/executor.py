from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from opspilot.models import ExecutionResult, Operation
from opspilot.policy import CommandPolicy


class CommandExecutor:
    def __init__(
        self,
        policy: CommandPolicy | None = None,
        audit_path: Path | None = None,
    ) -> None:
        self.policy = policy or CommandPolicy()
        self.audit_path = audit_path or Path(".opspilot") / "audit.jsonl"

    def execute(self, operation: Operation, apply: bool = False) -> ExecutionResult:
        self.policy.validate(operation, apply=apply)

        try:
            completed = subprocess.run(
                operation.command,
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=operation.timeout_seconds,
            )
            result = ExecutionResult(
                operation=operation,
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        except FileNotFoundError:
            result = ExecutionResult(
                operation=operation,
                return_code=127,
                stdout="",
                stderr=f"Required executable not found: {operation.command[0]}",
            )
        except subprocess.TimeoutExpired as error:
            result = ExecutionResult(
                operation=operation,
                return_code=124,
                stdout=error.stdout or "",
                stderr=f"Operation timed out after {operation.timeout_seconds} seconds.",
            )

        self._audit(result, apply)
        return result

    def _audit(self, result: ExecutionResult, apply: bool) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "operation": result.operation.name,
            "command": list(result.operation.command),
            "risk": result.operation.risk.value,
            "apply_authorized": apply,
            "return_code": result.return_code,
        }
        with self.audit_path.open("a", encoding="utf-8") as audit_file:
            audit_file.write(json.dumps(entry, separators=(",", ":")) + "\n")

