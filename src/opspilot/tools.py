from __future__ import annotations

import re

from opspilot.models import Operation, Risk

RESOURCE_NAME = re.compile(r"^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$")


def _validated_resource(value: str, kind: str) -> str:
    normalized = value.strip().lower()
    if not RESOURCE_NAME.fullmatch(normalized):
        raise ValueError(f"Invalid {kind} name: {value!r}")
    return normalized


def git_status() -> Operation:
    return Operation(
        name="git-status",
        description="Show the repository working tree status.",
        command=("git", "status", "--short", "--branch"),
    )


def git_recent_commits() -> Operation:
    return Operation(
        name="git-recent-commits",
        description="Show the five most recent commits.",
        command=("git", "log", "-5", "--oneline", "--decorate"),
    )


def docker_containers() -> Operation:
    return Operation(
        name="docker-containers",
        description="List running Docker containers.",
        command=("docker", "ps"),
    )


def docker_compose_status() -> Operation:
    return Operation(
        name="docker-compose-status",
        description="Show Docker Compose service status.",
        command=("docker", "compose", "ps"),
    )


def docker_logs(container: str) -> Operation:
    container = _validated_resource(container, "container")
    return Operation(
        name="docker-logs",
        description=f"Show the last 100 log lines for Docker container {container}.",
        command=("docker", "logs", "--tail", "100", container),
    )


def kubernetes_pods(namespace: str | None = None) -> Operation:
    command = ["kubectl", "get", "pods"]
    description = "List Kubernetes pods."
    if namespace:
        namespace = _validated_resource(namespace, "namespace")
        command.extend(("-n", namespace))
        description = f"List Kubernetes pods in namespace {namespace}."
    else:
        command.append("--all-namespaces")

    return Operation(
        name="kubernetes-pods",
        description=description,
        command=tuple(command),
    )


def kubernetes_events(namespace: str | None = None) -> Operation:
    command = ["kubectl", "get", "events", "--sort-by=.metadata.creationTimestamp"]
    description = "Show Kubernetes events from all namespaces."
    if namespace:
        namespace = _validated_resource(namespace, "namespace")
        command.extend(("-n", namespace))
        description = f"Show Kubernetes events in namespace {namespace}."
    else:
        command.append("--all-namespaces")

    return Operation(
        name="kubernetes-events",
        description=description,
        command=tuple(command),
    )


def kubernetes_logs(pod: str, namespace: str | None = None) -> Operation:
    pod = _validated_resource(pod, "pod")
    command = ["kubectl", "logs", pod, "--tail=100"]
    description = f"Show the last 100 log lines for Kubernetes pod {pod}."
    if namespace:
        namespace = _validated_resource(namespace, "namespace")
        command.extend(("-n", namespace))
        description = (
            f"Show the last 100 log lines for Kubernetes pod {pod} "
            f"in namespace {namespace}."
        )

    return Operation(
        name="kubernetes-logs",
        description=description,
        command=tuple(command),
    )


def restart_deployment(deployment: str, namespace: str | None = None) -> Operation:
    deployment = _validated_resource(deployment, "deployment")
    command = ["kubectl", "rollout", "restart", f"deployment/{deployment}"]
    description = f"Restart Kubernetes deployment {deployment}."
    if namespace:
        namespace = _validated_resource(namespace, "namespace")
        command.extend(("-n", namespace))
        description = f"Restart Kubernetes deployment {deployment} in namespace {namespace}."

    return Operation(
        name="restart-deployment",
        description=description,
        command=tuple(command),
        risk=Risk.MUTATING,
    )


def terraform_validate() -> Operation:
    return Operation(
        name="terraform-validate",
        description="Validate the Terraform configuration.",
        command=("terraform", "validate"),
    )


def terraform_plan() -> Operation:
    return Operation(
        name="terraform-plan",
        description="Create a Terraform execution plan without applying it.",
        command=("terraform", "plan", "-input=false"),
        timeout_seconds=300,
    )


def terraform_format_check() -> Operation:
    return Operation(
        name="terraform-format-check",
        description="Check Terraform formatting without changing files.",
        command=("terraform", "fmt", "-check", "-recursive"),
    )


def catalog() -> tuple[Operation, ...]:
    return (
        git_status(),
        git_recent_commits(),
        docker_containers(),
        docker_compose_status(),
        kubernetes_pods(),
        kubernetes_events(),
        terraform_validate(),
        terraform_plan(),
        terraform_format_check(),
    )

