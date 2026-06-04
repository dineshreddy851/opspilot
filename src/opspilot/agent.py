from __future__ import annotations

import re

from opspilot.models import Operation
from opspilot import tools

NAME = r"([a-z0-9](?:[-a-z0-9.]*[a-z0-9])?)"


def _namespace(prompt: str) -> str | None:
    match = re.search(rf"(?:in\s+)?namespace\s+{NAME}", prompt)
    return match.group(1) if match else None


def _named_resource(prompt: str, resource: str) -> str | None:
    patterns = (
        rf"{resource}\s+{NAME}",
        rf"{NAME}\s+{resource}",
    )
    for pattern in patterns:
        match = re.search(pattern, prompt)
        if match:
            return match.group(1)
    return None


class DevOpsAgent:
    """Routes a natural-language request to a curated DevOps operation."""

    def plan(self, request: str) -> Operation | None:
        prompt = " ".join(request.lower().strip().split())
        namespace = _namespace(prompt)

        if "restart" in prompt and "deployment" in prompt:
            deployment = _named_resource(prompt, "deployment")
            return tools.restart_deployment(deployment, namespace) if deployment else None

        if ("kubernetes" in prompt or "k8s" in prompt or "kubectl" in prompt) and "log" in prompt:
            pod = _named_resource(prompt, "pod")
            return tools.kubernetes_logs(pod, namespace) if pod else None

        if "docker" in prompt and "log" in prompt:
            container = _named_resource(prompt, "container")
            return tools.docker_logs(container) if container else None

        if "terraform" in prompt:
            if "plan" in prompt:
                return tools.terraform_plan()
            if "validate" in prompt:
                return tools.terraform_validate()
            if "format" in prompt or "fmt" in prompt:
                return tools.terraform_format_check()

        if "docker" in prompt and "compose" in prompt:
            return tools.docker_compose_status()

        if "docker" in prompt and any(word in prompt for word in ("container", "status", "ps")):
            return tools.docker_containers()

        if any(word in prompt for word in ("kubernetes", "k8s", "kubectl")):
            if "event" in prompt:
                return tools.kubernetes_events(namespace)
            if "pod" in prompt:
                return tools.kubernetes_pods(namespace)

        if "git" in prompt or "repository" in prompt or "repo" in prompt:
            if any(word in prompt for word in ("commit", "history", "log")):
                return tools.git_recent_commits()
            if "status" in prompt or "change" in prompt:
                return tools.git_status()

        return None

