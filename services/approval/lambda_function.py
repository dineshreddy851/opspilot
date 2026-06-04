from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

APPROVED = "APPROVED"
REJECTED = "REJECTED"
FINAL_STATUSES = frozenset({"COMPLETED", "EXPIRED", "FAILED", REJECTED})


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _conditional_failure(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


class ApprovalApplication:
    """Records approval state and safely resumes Step Functions callbacks."""

    def __init__(
        self,
        table: Any,
        sns_client: Any,
        stepfunctions_client: Any,
        topic_arn: str,
        controlled_action: str,
    ) -> None:
        self.table = table
        self.sns = sns_client
        self.stepfunctions = stepfunctions_client
        self.topic_arn = topic_arn
        self.controlled_action = controlled_action

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        operation = _required_text(event.get("operation"), "operation")
        if operation == "record_pending":
            return self.record_pending(event.get("request"))
        if operation == "notify_and_wait":
            return self.notify_and_wait(event.get("request"), event.get("task_token"))
        if operation == "decide":
            return self.decide(event)
        if operation == "record_result":
            return self.record_result(event)
        raise ValueError(f"Unsupported approval operation: {operation}")

    def record_pending(self, request: Any) -> dict[str, Any]:
        request = self._validated_request(request)
        item = {
            **request,
            "status": "PENDING",
            "created_at": _now(),
            "updated_at": _now(),
        }
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(request_id)",
            )
        except ClientError as error:
            if not _conditional_failure(error):
                raise
            return {**request, "duplicate": True, "status": "DUPLICATE"}
        return {**request, "duplicate": False, "status": "PENDING"}

    def notify_and_wait(self, request: Any, task_token: Any) -> dict[str, Any]:
        request = self._validated_request(request)
        token = _required_text(task_token, "task_token")
        self.table.update_item(
            Key={"request_id": request["request_id"]},
            UpdateExpression=(
                "SET #status = :waiting, task_token = :token, updated_at = :updated"
            ),
            ConditionExpression="#status = :pending",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":waiting": "WAITING_APPROVAL",
                ":pending": "PENDING",
                ":token": token,
                ":updated": _now(),
            },
        )
        message = {
            "request_id": request["request_id"],
            "action": request["action"],
            "requested_by": request["requested_by"],
            "instructions": (
                "Review the request, then invoke the approval Lambda with operation=decide, "
                "this request_id, decision=APPROVED or REJECTED, and your actor_subject."
            ),
        }
        self.sns.publish(
            TopicArn=self.topic_arn,
            Subject=f"OpsPilot approval required: {request['request_id']}",
            Message=json.dumps(message),
        )
        return {"request_id": request["request_id"], "status": "WAITING_APPROVAL"}

    def decide(self, event: dict[str, Any]) -> dict[str, Any]:
        request_id = _required_text(event.get("request_id"), "request_id")
        actor_subject = _required_text(event.get("actor_subject"), "actor_subject")
        decision = _required_text(event.get("decision"), "decision").upper()
        if decision not in {APPROVED, REJECTED}:
            raise ValueError("decision must be APPROVED or REJECTED.")

        item = self.table.get_item(
            Key={"request_id": request_id},
            ConsistentRead=True,
        ).get("Item")
        if not item or item.get("status") != "WAITING_APPROVAL":
            raise ValueError("Approval request is not waiting for a decision.")

        self.table.update_item(
            Key={"request_id": request_id},
            UpdateExpression=(
                "SET #status = :decision, decided_by = :actor, updated_at = :updated "
                "REMOVE task_token"
            ),
            ConditionExpression="#status = :waiting",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":decision": decision,
                ":actor": actor_subject,
                ":updated": _now(),
                ":waiting": "WAITING_APPROVAL",
            },
        )
        callback_output = {
            "request_id": request_id,
            "action": item["action"],
            "requested_by": item["requested_by"],
            "decision": decision,
            "decided_by": actor_subject,
        }
        self.stepfunctions.send_task_success(
            taskToken=item["task_token"],
            output=json.dumps(callback_output),
        )
        return {"request_id": request_id, "status": decision}

    def record_result(self, event: dict[str, Any]) -> dict[str, Any]:
        request_id = _required_text(event.get("request_id"), "request_id")
        status = _required_text(event.get("status"), "status").upper()
        if status not in FINAL_STATUSES:
            raise ValueError(f"Unsupported final status: {status}")

        values: dict[str, Any] = {
            ":status": status,
            ":updated": _now(),
        }
        update_expression = "SET #status = :status, updated_at = :updated"
        if "result" in event:
            update_expression += ", action_result = :result"
            values[":result"] = event["result"]
        update_expression += " REMOVE task_token"

        self.table.update_item(
            Key={"request_id": request_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues=values,
        )
        return {"request_id": request_id, "status": status}

    def _validated_request(self, request: Any) -> dict[str, str]:
        if not isinstance(request, dict):
            raise ValueError("request must be an object.")
        action = _required_text(request.get("action"), "action")
        if action != self.controlled_action:
            raise ValueError("The requested controlled action is not allowed.")
        return {
            "request_id": _required_text(request.get("request_id"), "request_id"),
            "action": action,
            "requested_by": _required_text(request.get("requested_by"), "requested_by"),
        }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    application = ApprovalApplication(
        table=boto3.resource("dynamodb").Table(os.environ["APPROVAL_TABLE_NAME"]),
        sns_client=boto3.client("sns"),
        stepfunctions_client=boto3.client("stepfunctions"),
        topic_arn=os.environ["APPROVAL_TOPIC_ARN"],
        controlled_action=os.environ["CONTROLLED_ACTION_NAME"],
    )
    result = application.handle(event)
    LOGGER.info(json.dumps({"event": "approval_operation", **result}))
    return result
