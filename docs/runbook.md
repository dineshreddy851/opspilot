# OpsPilot Operations Runbook

## Purpose

Use this runbook to investigate OpsPilot failures without bypassing its safety
controls. Do not invoke the mutation Lambda directly, edit approval records, or
change resources in the AWS console as a first response.

## Prepare access

```bash
export AWS_PROFILE=opspilot-dev
export AWS_REGION=us-east-1
aws sso login --profile "$AWS_PROFILE"
aws sts get-caller-identity

cd ~/projects/opspilot/infra/dev
terraform output
```

Record the incident time, authenticated identity, failing request ID, and the
current Git commit before changing anything.

## First five minutes

1. Open the CloudWatch dashboard named by:

   ```bash
   terraform output -raw operations_dashboard_name
   ```

2. Inspect alarms:

   ```bash
   aws cloudwatch describe-alarms \
     --state-value ALARM \
     --query 'MetricAlarms[?starts_with(AlarmName, `opspilot-`)].{Name:AlarmName,Reason:StateReason}'
   ```

3. Confirm public health:

   ```bash
   curl -fsS "$(terraform output -raw health_url)"
   ```

4. Do not approve a controlled request while API, approval, mutation, or
   Step Functions failures are unexplained.

## Investigate API 5xx or API Lambda errors

```bash
aws logs tail /aws/lambda/opspilot-dev-api --since 30m --format short
aws logs tail /aws/apigateway/opspilot-dev-api --since 30m --format short
```

Correlate API Gateway `requestId`, HTTP status, route, Lambda error, and the
DynamoDB audit `request_id`.

Inspect a known audit event:

```bash
aws dynamodb get-item \
  --table-name "$(terraform output -raw audit_table_name)" \
  --key '{"request_id":{"S":"REPLACE_REQUEST_ID"}}'
```

Expected safe failures include `mutating_or_destructive_request`,
`invalid_tool_proposal`, and `approval_workflow_start_failed`. Unexpected 5xx
responses require code and dependency investigation.

## Investigate Lambda throttling

Confirm which function is throttled on the dashboard, then inspect concurrency:

```bash
aws lambda get-function-concurrency \
  --function-name "$(terraform output -raw lambda_function_name)"
```

Do not immediately raise concurrency. First check for request loops, abusive
clients, repeated browser polling, or an unavailable dependency. Raising
concurrency can increase downstream load and cost.

## Investigate a stuck approval

```bash
aws dynamodb get-item \
  --table-name "$(terraform output -raw approval_table_name)" \
  --key '{"request_id":{"S":"REPLACE_REQUEST_ID"}}'

aws stepfunctions list-executions \
  --state-machine-arn "$(terraform output -raw approval_state_machine_arn)" \
  --max-results 20

aws logs tail /aws/vendedlogs/states/opspilot-dev-approval \
  --since 30m --format short
```

Check whether the request is `WAITING_APPROVAL`, rejected, expired, completed,
or failed. Workflow logs are error-only and exclude execution data. Never copy
a task token into chat, a ticket, or the browser. A timed out request should
become `EXPIRED`; a rejected request must never invoke the mutation Lambda.

## Investigate mutation failure

```bash
aws logs tail /aws/lambda/opspilot-dev-mutation --since 30m --format short
aws logs tail /aws/lambda/opspilot-dev-approval --since 30m --format short
```

Confirm `controlled_action_dry_run`:

```bash
terraform output -raw controlled_action_dry_run
```

If dry-run is false, use CloudTrail to verify the exact caller, service ARN, and
`UpdateService` event before retrying.

## Investigate CloudTrail

```bash
aws cloudtrail describe-trails \
  --trail-name-list "$(terraform output -raw cloudtrail_name)"

aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=UpdateService \
  --max-results 20
```

The trail is multi-Region and records management events. Logs are stored in the
private bucket from `terraform output -raw cloudtrail_bucket_name` and expire
according to `cloudtrail_retention_days`.

## Controlled failure verification

Run the local controlled failure test:

```bash
cd ~/projects/opspilot
python -m unittest tests.test_controlled_failure -v
```

It simulates Step Functions failing to start and proves the API reports and
audits the failure without reaching a mutation.

## Recovery and change process

1. Reproduce with a test or a safe read-only request.
2. Make the smallest code or Terraform change.
3. Run the complete test suite and Terraform validation.
4. Review `terraform plan`; do not apply an unexpected replacement or deletion.
5. Deploy through the protected GitHub development environment.
6. Verify alarms return to `OK` and record the incident outcome.

## Current limitations

There is no automated pager, WAF, production SLO, cross-account log archive, or
automated rollback. The CloudTrail bucket intentionally has
`force_destroy=false`; cleanup requires an explicit evidence-retention decision.
