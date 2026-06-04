from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

PROJECT_TAG = "OpsPilot"
MAX_REQUEST_LENGTH = 1_000
BLOCKED_WORDS = frozenset(
    {
        "create",
        "delete",
        "destroy",
        "reboot",
        "restart",
        "start",
        "stop",
        "terminate",
        "update",
    }
)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, default=_json_default),
    }


def _request_from_event(event: dict[str, Any]) -> Any:
    body = event.get("body", event)
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return None
    if not isinstance(body, dict):
        return None
    return body.get("request")


class AwsApiApplication:
    """Runs narrowly defined, read-only AWS tools and records every outcome."""

    def __init__(
        self,
        cloudwatch_client: Any,
        ec2_client: Any,
        audit_table: Any,
    ) -> None:
        self.cloudwatch = cloudwatch_client
        self.ec2 = ec2_client
        self.audit_table = audit_table

    def handle(self, request: Any) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        request_text = request.strip() if isinstance(request, str) else ""
        request_text = request_text[:MAX_REQUEST_LENGTH]
        tool: str | None = None
        status = "refused"
        reason = "unknown_request"
        status_code = 400
        result: dict[str, Any] | None = None

        try:
            normalized = " ".join(request_text.lower().split())
            words = set(normalized.split())

            if not normalized:
                reason = "request_must_be_a_non_empty_string"
            elif words.intersection(BLOCKED_WORDS):
                reason = "mutating_or_destructive_request"
                status_code = 403
            elif "alarm" in normalized or "cloudwatch" in normalized:
                tool = "list_cloudwatch_alarms"
                result = self._list_cloudwatch_alarms()
                status = "succeeded"
                reason = "approved_read_only_tool"
                status_code = 200
            elif "ec2" in normalized or "instance" in normalized:
                tool = "list_opspilot_ec2_instances"
                result = self._list_opspilot_ec2_instances()
                status = "succeeded"
                reason = "approved_read_only_tool"
                status_code = 200

            payload = {
                "request_id": request_id,
                "status": status,
                "reason": reason,
                "tool": tool,
                "result": result,
            }
        except Exception:
            LOGGER.exception("AWS tool execution failed", extra={"request_id": request_id})
            status = "failed"
            reason = "tool_execution_failed"
            status_code = 500
            payload = {
                "request_id": request_id,
                "status": status,
                "reason": reason,
                "tool": tool,
                "result": None,
            }
        finally:
            self._write_audit_event(
                request_id=request_id,
                request_text=request_text,
                status=status,
                reason=reason,
                status_code=status_code,
                tool=tool,
            )

        return _response(status_code, payload)

    def _list_cloudwatch_alarms(self) -> dict[str, Any]:
        response = self.cloudwatch.describe_alarms(
            StateValue="ALARM",
            MaxRecords=50,
        )
        alarms = [
            {
                "name": alarm.get("AlarmName"),
                "state": alarm.get("StateValue"),
                "reason": alarm.get("StateReason"),
                "updated_at": alarm.get("StateUpdatedTimestamp"),
            }
            for alarm in response.get("MetricAlarms", [])
        ]
        return {"alarm_count": len(alarms), "alarms": alarms}

    def _list_opspilot_ec2_instances(self) -> dict[str, Any]:
        response = self.ec2.describe_instances(
            Filters=[{"Name": "tag:Project", "Values": [PROJECT_TAG]}]
        )
        instances = []
        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                tags = {
                    tag.get("Key"): tag.get("Value")
                    for tag in instance.get("Tags", [])
                    if tag.get("Key")
                }
                instances.append(
                    {
                        "instance_id": instance.get("InstanceId"),
                        "name": tags.get("Name"),
                        "state": instance.get("State", {}).get("Name"),
                        "instance_type": instance.get("InstanceType"),
                        "private_ip": instance.get("PrivateIpAddress"),
                        "public_ip": instance.get("PublicIpAddress"),
                    }
                )
        return {"instance_count": len(instances), "instances": instances}

    def _write_audit_event(
        self,
        *,
        request_id: str,
        request_text: str,
        status: str,
        reason: str,
        status_code: int,
        tool: str | None,
    ) -> None:
        item = {
            "request_id": request_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "request": request_text,
            "status": status,
            "reason": reason,
            "status_code": status_code,
            "tool": tool or "none",
        }
        self.audit_table.put_item(Item=item)
        LOGGER.info(json.dumps({"event": "request_audited", **item}))


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """API Gateway Lambda entry point."""
    table_name = os.environ["AUDIT_TABLE_NAME"]
    application = AwsApiApplication(
        cloudwatch_client=boto3.client("cloudwatch"),
        ec2_client=boto3.client("ec2"),
        audit_table=boto3.resource("dynamodb").Table(table_name),
    )
    return application.handle(_request_from_event(event))

