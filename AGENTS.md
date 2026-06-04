# OpsPilot Agent Guide

## Project goal

Build a safety-first DevOps assistant that maps natural-language requests to
small, curated operations. The bot should help operators investigate systems
without becoming an arbitrary remote shell.

## Safety invariants

- Keep `shell=False` for every command execution.
- Do not add arbitrary command execution or user-provided command arguments.
- Keep destructive tokens blocked in `src/opspilot/policy.py`.
- Default new operations to read-only.
- Require `Risk.MUTATING`, `--apply`, and confirmation for any operation that
  changes infrastructure.
- Validate every user-provided resource name before adding it to a command.
- Add tests for routing, the exact command arguments, and policy behavior.

## AWS portfolio version

- Use Boto3 and structured AWS API calls for cloud-hosted tools.
- Do not deploy the local shell executor to Lambda.
- Bedrock may propose an operation, but the deterministic policy engine must
  authorize it before execution.
- Restrict IAM roles to the smallest set of actions and resources possible.
- Require project tags and explicit environment configuration for operated
  resources.
- Keep read-only and mutating tools in separate Lambda functions and IAM roles.
- Route every mutating operation through a human approval workflow.
- Use temporary credentials for people, workloads, and CI/CD.
- Do not store long-lived AWS access keys in the repository or GitHub Secrets.
- Add audit events, structured logs, alarms, and rollback notes for each new
  cloud capability.

## Development workflow

```bash
python -m pip install --editable .
python -m unittest discover -s tests -v
opspilot tools
```

When adding a capability:

1. Add a narrow operation factory in `src/opspilot/tools.py`.
2. Route an explicit phrase to it in `src/opspilot/agent.py`.
3. Confirm the operation's risk level in `src/opspilot/models.py`.
4. Add policy and routing tests before running the full suite.
