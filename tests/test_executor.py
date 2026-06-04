import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from opspilot.executor import CommandExecutor
from opspilot.models import Operation


class CommandExecutorTests(unittest.TestCase):
    def test_missing_binary_is_reported_and_audited(self) -> None:
        operation = Operation("status", "status", ("git", "status"))
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.jsonl"
            executor = CommandExecutor(audit_path=audit_path)
            with patch("opspilot.executor.subprocess.run", side_effect=FileNotFoundError):
                result = executor.execute(operation)

            self.assertEqual(result.return_code, 127)
            entry = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual(entry["operation"], "status")
            self.assertEqual(entry["return_code"], 127)


if __name__ == "__main__":
    unittest.main()

