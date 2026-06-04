from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

APPROVED = "APPROVED"


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class ControlledActionApplication:
    """Runs one configured action only after an approved workflow decision."""

    def __init__(
        self,
        ecs_client: Any,
        dry_run: bool,
        controlled_action: str,
        ecs_cluster: str,
        ecs_service: str,
    ) -> None:
        self.ecs = ecs_client
        self.dry_run = dry_run
        self.controlled_action = controlled_action
        self.ecs_cluster = ecs_cluster
        self.ecs_service = ecs_service

    def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        if event.get("decision") != APPROVED:
            raise ValueError("The controlled action requires an APPROVED decision.")
        if event.get("action") != self.controlled_action:
            raise ValueError("The requested controlled action is not allowed.")

        result = {
            "request_id": event.get("request_id"),
            "action": self.controlled_action,
            "dry_run": self.dry_run,
            "cluster": self.ecs_cluster,
            "service": self.ecs_service,
        }
        if self.dry_run:
            result["status"] = "DRY_RUN"
        else:
            response = self.ecs.update_service(
                cluster=self.ecs_cluster,
                service=self.ecs_service,
                forceNewDeployment=True,
            )
            result["status"] = "EXECUTED"
            result["service_arn"] = response.get("service", {}).get("serviceArn")

        LOGGER.info(json.dumps({"event": "controlled_action", **result}))
        return result


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    application = ControlledActionApplication(
        ecs_client=boto3.client("ecs"),
        dry_run=_env_flag("DRY_RUN", default=True),
        controlled_action=os.environ["CONTROLLED_ACTION_NAME"],
        ecs_cluster=os.environ["CONTROLLED_ACTION_ECS_CLUSTER"],
        ecs_service=os.environ["CONTROLLED_ACTION_ECS_SERVICE"],
    )
    return application.handle(event)

