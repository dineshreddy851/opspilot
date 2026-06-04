import unittest

from opspilot.models import Operation, Risk
from opspilot.policy import CommandPolicy, PolicyViolation


class CommandPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = CommandPolicy()

    def test_allows_known_read_only_operation(self) -> None:
        operation = Operation("status", "status", ("git", "status"))
        self.policy.validate(operation)

    def test_mutating_operation_requires_apply(self) -> None:
        operation = Operation(
            "restart",
            "restart",
            ("kubectl", "rollout", "restart", "deployment/api"),
            risk=Risk.MUTATING,
        )
        with self.assertRaises(PolicyViolation):
            self.policy.validate(operation)
        self.policy.validate(operation, apply=True)

    def test_blocks_destructive_token_even_with_apply(self) -> None:
        operation = Operation(
            "destroy",
            "destroy",
            ("terraform", "destroy"),
            risk=Risk.MUTATING,
        )
        with self.assertRaises(PolicyViolation):
            self.policy.validate(operation, apply=True)

    def test_blocks_unknown_executable(self) -> None:
        operation = Operation("shell", "shell", ("powershell", "Get-Process"))
        with self.assertRaises(PolicyViolation):
            self.policy.validate(operation)


if __name__ == "__main__":
    unittest.main()

