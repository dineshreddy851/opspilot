# OpsPilot

OpsPilot is a small, safety-first DevOps agent bot. It turns a natural-language
request into one curated command, shows the exact plan, enforces a command
policy, executes without a shell, and records an audit event.

The MVP supports:

- Git status and recent commits
- Docker containers, Compose status, and container logs
- Kubernetes pods, events, pod logs, and controlled deployment restarts
- Terraform validation, formatting checks, and plans

It intentionally does **not** accept arbitrary shell commands. Destructive
operations such as `delete`, `destroy`, and `prune` are blocked. Read-only
operations run normally; the built-in deployment restart requires `--apply`
and confirmation.

## Quick start

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --editable .
opspilot doctor
opspilot tools
```

On macOS or Linux, activate the environment with:

```bash
source .venv/bin/activate
```

## Examples

Preview any operation without running it:

```bash
opspilot ask "show docker container status" --plan-only
opspilot ask "show k8s pods in namespace production" --plan-only
opspilot ask "terraform plan" --plan-only
```

Run read-only diagnostics:

```bash
opspilot ask "show git status"
opspilot ask "show logs for docker container api"
opspilot ask "show kubernetes events in namespace production"
```

Run the controlled mutating operation:

```bash
opspilot ask "restart deployment api in namespace production" --apply
```

For non-interactive CI usage, add `--yes` after reviewing the exact operation:

```bash
opspilot ask "restart deployment api in namespace staging" --apply --yes
```

Every executed command writes an audit event to `.opspilot/audit.jsonl`.

## Test

```bash
python -m unittest discover -s tests -v
```

## Architecture

```text
Natural-language request
        |
        v
DevOpsAgent intent router
        |
        v
Curated Operation -> CommandPolicy -> CommandExecutor -> Audit log
```

Add a new capability by creating an operation in `src/opspilot/tools.py`,
routing a phrase to it in `src/opspilot/agent.py`, and adding policy-focused
tests. Keep commands narrow and prefer read-only diagnostics.

## Security model

- Commands are fixed argument lists and run with `shell=False`.
- Only `git`, `docker`, `kubectl`, and `terraform` are allowed.
- User-provided resource names use a restrictive Kubernetes-style name format.
- Destructive command tokens remain blocked even when `--apply` is supplied.
- Mutating operations require explicit authorization and confirmation.

This is a starter project, not a replacement for production authorization,
RBAC, secret management, or change-management controls.

## Continue building with Codex

The included `AGENTS.md` gives Codex the project's safety rules. Useful next
requests include:

```text
Add a read-only operation that describes a Kubernetes pod.
Add JSON output for CI pipelines without changing the default text output.
Add a Slack adapter that can only run read-only operations.
```

## AWS portfolio version

The next version turns OpsPilot into a portfolio-grade AWS application using
Amazon Bedrock, Lambda, API Gateway, Cognito, Step Functions, DynamoDB,
CloudWatch, CloudTrail, Terraform, and GitHub Actions OIDC.

- [Start with the first-session checklist](docs/START_HERE.md)
- [Build the project on AWS from scratch](docs/FROM_SCRATCH_AWS_GUIDE.md)
- [Use the Linux-specific setup and commands](docs/LINUX_FROM_SCRATCH_GUIDE.md)
- [Follow the step-by-step AWS roadmap](docs/AWS_PORTFOLIO_ROADMAP.md)
- [Use the company portfolio demo guide](docs/PORTFOLIO_DEMO.md)

## Company-ready evidence

A reviewer can understand the AWS architecture and its safety boundaries in
about two minutes by starting with:

- [Architecture and engineering decisions](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Operations runbook](docs/runbook.md)
- [Five-minute recording script](docs/demo-script.md)
- [Cost controls and limitations](docs/cost-controls.md)

The development stack includes Cognito authentication, a deterministic
read-only policy, a human approval workflow, private web hosting, application
audit records, a CloudWatch dashboard and alarms, and a multi-Region CloudTrail
trail. All application resources are declared in `infra/dev`.
