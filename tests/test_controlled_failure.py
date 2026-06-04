import json
import unittest

from services.api.lambda_function import WebApiApplication


class RecordingTable:
    def __init__(self):
        self.items = []

    def put_item(self, *, Item):
        self.items.append(Item)


class FailingStepFunctions:
    def __init__(self):
        self.calls = []

    def start_execution(self, **kwargs):
        self.calls.append(kwargs)
        raise RuntimeError("controlled Step Functions outage")


class MutationMustNotRun:
    def update_service(self, **kwargs):
        raise AssertionError("A workflow-start failure must never reach mutation.")


class ControlledFailureTests(unittest.TestCase):
    def test_workflow_start_failure_is_returned_and_audited_without_mutation(self):
        audit = RecordingTable()
        stepfunctions = FailingStepFunctions()
        application = WebApiApplication(
            audit_table=audit,
            approval_table=object(),
            stepfunctions_client=stepfunctions,
            approval_state_machine_arn=(
                "arn:aws:states:us-east-1:123456789012:stateMachine:opspilot-approval"
            ),
        )
        mutation = MutationMustNotRun()

        with self.assertLogs(level="ERROR"):
            response = application.start_controlled_request(
                "restart the approved demo ECS service",
                "cognito-user-123",
            )
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["reason"], "approval_workflow_start_failed")
        self.assertEqual(len(stepfunctions.calls), 1)
        self.assertEqual(audit.items[0]["status"], "failed")
        self.assertEqual(audit.items[0]["risk"], "controlled_mutation")
        self.assertFalse(hasattr(mutation, "calls"))


if __name__ == "__main__":
    unittest.main()
