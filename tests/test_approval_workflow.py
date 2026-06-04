import json
import unittest

from botocore.exceptions import ClientError

from services.approval.lambda_function import ApprovalApplication
from services.mutation.lambda_function import ControlledActionApplication


CONTROLLED_ACTION = "restart_approved_ecs_service"


class FakeApprovalTable:
    def __init__(self):
        self.items = {}
        self.updates = []

    def put_item(self, *, Item, ConditionExpression):
        request_id = Item["request_id"]
        if request_id in self.items:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}},
                "PutItem",
            )
        self.items[request_id] = dict(Item)

    def get_item(self, *, Key, ConsistentRead):
        return {"Item": dict(self.items[Key["request_id"]])}

    def update_item(self, **kwargs):
        request_id = kwargs["Key"]["request_id"]
        values = kwargs["ExpressionAttributeValues"]
        item = self.items.setdefault(request_id, {"request_id": request_id})
        condition = kwargs.get("ConditionExpression", "")
        if ":waiting" in condition and item.get("status") != values[":waiting"]:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}},
                "UpdateItem",
            )
        if ":pending" in condition and item.get("status") != values[":pending"]:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}},
                "UpdateItem",
            )
        if ":status" in values:
            item["status"] = values[":status"]
        if ":waiting" in values and ":pending" in values:
            item["status"] = values[":waiting"]
        if ":decision" in values:
            item["status"] = values[":decision"]
        if ":token" in values:
            item["task_token"] = values[":token"]
        if ":actor" in values:
            item["decided_by"] = values[":actor"]
        if ":result" in values:
            item["action_result"] = values[":result"]
        if "REMOVE task_token" in kwargs["UpdateExpression"]:
            item.pop("task_token", None)
        self.updates.append(kwargs)
        return {}


class FakeSns:
    def __init__(self):
        self.messages = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)
        return {"MessageId": "message-1"}


class FakeStepFunctions:
    def __init__(self):
        self.successes = []

    def send_task_success(self, **kwargs):
        self.successes.append(kwargs)
        return {}


class FakeEcs:
    def __init__(self):
        self.calls = []

    def update_service(self, **kwargs):
        self.calls.append(kwargs)
        return {"service": {"serviceArn": "arn:aws:ecs:us-east-1:123:service/demo/api"}}


class ApprovalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.table = FakeApprovalTable()
        self.sns = FakeSns()
        self.stepfunctions = FakeStepFunctions()
        self.application = ApprovalApplication(
            table=self.table,
            sns_client=self.sns,
            stepfunctions_client=self.stepfunctions,
            topic_arn="arn:aws:sns:us-east-1:123:opspilot-approvals",
            controlled_action=CONTROLLED_ACTION,
        )
        self.request = {
            "request_id": "request-123",
            "action": CONTROLLED_ACTION,
            "requested_by": "cognito-user-123",
        }

    def prepare_waiting_request(self):
        self.application.handle({"operation": "record_pending", "request": self.request})
        self.application.handle(
            {
                "operation": "notify_and_wait",
                "request": self.request,
                "task_token": "secret-task-token",
            }
        )

    def test_approved_request_resumes_workflow(self):
        self.prepare_waiting_request()

        result = self.application.handle(
            {
                "operation": "decide",
                "request_id": self.request["request_id"],
                "decision": "APPROVED",
                "actor_subject": "approver-123",
            }
        )

        self.assertEqual(result["status"], "APPROVED")
        callback = json.loads(self.stepfunctions.successes[0]["output"])
        self.assertEqual(callback["decision"], "APPROVED")
        self.assertEqual(callback["action"], CONTROLLED_ACTION)
        self.assertNotIn("task_token", self.table.items[self.request["request_id"]])

    def test_rejected_request_resumes_workflow_without_mutation(self):
        self.prepare_waiting_request()

        result = self.application.handle(
            {
                "operation": "decide",
                "request_id": self.request["request_id"],
                "decision": "REJECTED",
                "actor_subject": "approver-123",
            }
        )

        self.assertEqual(result["status"], "REJECTED")
        callback = json.loads(self.stepfunctions.successes[0]["output"])
        self.assertEqual(callback["decision"], "REJECTED")

    def test_expired_request_is_recorded(self):
        self.prepare_waiting_request()

        result = self.application.handle(
            {
                "operation": "record_result",
                "request_id": self.request["request_id"],
                "status": "EXPIRED",
            }
        )

        self.assertEqual(result["status"], "EXPIRED")
        self.assertEqual(self.table.items[self.request["request_id"]]["status"], "EXPIRED")
        self.assertNotIn("task_token", self.table.items[self.request["request_id"]])

    def test_duplicate_request_is_not_created_twice(self):
        first = self.application.handle(
            {"operation": "record_pending", "request": self.request}
        )
        duplicate = self.application.handle(
            {"operation": "record_pending", "request": self.request}
        )

        self.assertFalse(first["duplicate"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(len(self.table.items), 1)

    def test_notification_does_not_expose_task_token(self):
        self.prepare_waiting_request()

        message = self.sns.messages[0]
        self.assertNotIn("secret-task-token", message["Message"])
        self.assertIn(self.request["request_id"], message["Message"])

    def test_mutating_lambda_runs_dry_run_only_after_approval(self):
        ecs = FakeEcs()
        application = ControlledActionApplication(
            ecs_client=ecs,
            dry_run=True,
            controlled_action=CONTROLLED_ACTION,
            ecs_cluster="demo-cluster",
            ecs_service="demo-service",
        )

        result = application.handle(
            {
                "request_id": self.request["request_id"],
                "action": CONTROLLED_ACTION,
                "decision": "APPROVED",
            }
        )

        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(ecs.calls, [])

    def test_mutating_lambda_refuses_unapproved_request(self):
        ecs = FakeEcs()
        application = ControlledActionApplication(
            ecs_client=ecs,
            dry_run=True,
            controlled_action=CONTROLLED_ACTION,
            ecs_cluster="demo-cluster",
            ecs_service="demo-service",
        )

        with self.assertRaises(ValueError):
            application.handle(
                {
                    "request_id": self.request["request_id"],
                    "action": CONTROLLED_ACTION,
                    "decision": "REJECTED",
                }
            )
        self.assertEqual(ecs.calls, [])


if __name__ == "__main__":
    unittest.main()
