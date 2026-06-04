# OpsPilot Cost Controls

## Cost posture

OpsPilot is designed as a low-traffic development portfolio environment.
Serverless and on-demand services avoid always-on compute, but they do not make
the environment free. Review AWS billing before and after every demonstration.

## Implemented controls

| Service | Control |
| --- | --- |
| Lambda | Small ARM64 functions, short timeouts, error and throttle alarms |
| DynamoDB | On-demand billing; no provisioned capacity |
| Bedrock | Disabled by default; one configured model permission when enabled |
| Step Functions | One Standard workflow, bounded approval and workflow timeouts |
| Mutation | `DRY_RUN=true` by default; no demo ECS service is created by this stack |
| CloudWatch Logs | Explicit configurable retention, default 14 days |
| CloudTrail | Management events only, no high-volume data events; S3 lifecycle expiry, default 90 days |
| CloudFront | `PriceClass_100` and static assets from private S3 |
| S3 | Lifecycle expiry for trail logs; no public access |
| Alerts | CloudWatch alarm transitions publish to one operations SNS topic |

## Cost drivers to watch

1. **CloudTrail and S3:** Multi-Region management-event delivery and stored
   versions accumulate. The lifecycle policy limits retention, but the bucket
   deliberately uses `force_destroy=false`.
2. **CloudWatch:** Dashboard metrics, alarms, log ingestion, and retained logs
   create recurring costs.
3. **Bedrock:** Every enabled Converse request is metered. Keep
   `bedrock_enabled=false` unless demonstrating model selection.
4. **Step Functions:** Standard workflow transitions are metered. Do not create
   repeated unattended approval requests.
5. **NAT Gateway:** None is created by this architecture. Adding one would
   introduce a meaningful fixed hourly cost.
6. **Demo ECS service:** Not created by this stack. Creating an always-on demo
   service would add compute and networking cost.

## Operating routine

Before a demo:

```bash
cd ~/projects/opspilot/infra/dev
terraform plan
terraform output
```

After a demo:

```bash
aws stepfunctions list-executions \
  --state-machine-arn "$(terraform output -raw approval_state_machine_arn)" \
  --max-results 20

aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/opspilot-
```

Review the AWS Billing console and Cost Explorer using the project tags:
`Project=OpsPilot`, `Environment=dev`, `Owner`, and `ManagedBy=Terraform`.

## Retention decisions

- Application logs default to 14 days through `log_retention_days`.
- CloudTrail S3 records default to 90 days through
  `cloudtrail_retention_days`.
- DynamoDB audit and approval tables currently have no automatic expiry because
  evidence retention policy has not been finalized.

## Limitations and next controls

The stack does not yet provision an AWS Budget, Cost Anomaly Detection monitor,
or automated teardown schedule. Those are recommended before broader use.
Production should use a separate log archive account and retention requirements
approved by security and compliance teams.
