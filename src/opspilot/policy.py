from __future__ import annotations

from opspilot.models import Operation, Risk

ALLOWED_EXECUTABLES = frozenset({"docker", "git", "kubectl", "terraform"})
BLOCKED_TOKENS = frozenset({"delete", "destroy", "prune", "rm", "rmdir"})


class PolicyViolation(RuntimeError):
    pass


class CommandPolicy:
    def validate(self, operation: Operation, apply: bool = False) -> None:
        if not operation.command:
            raise PolicyViolation("An operation must include a command.")

        executable = operation.command[0].lower()
        if executable not in ALLOWED_EXECUTABLES:
            raise PolicyViolation(f"Executable {executable!r} is not allowed.")

        for argument in operation.command:
            if "\x00" in argument or "\n" in argument or "\r" in argument:
                raise PolicyViolation("Command arguments cannot contain control characters.")

        tokens = {argument.lower() for argument in operation.command}
        blocked = tokens.intersection(BLOCKED_TOKENS)
        if blocked:
            raise PolicyViolation(f"Blocked destructive command token: {sorted(blocked)[0]}")

        if operation.risk is Risk.MUTATING and not apply:
            raise PolicyViolation(
                "This operation changes infrastructure. Run again with --apply to authorize it."
            )

