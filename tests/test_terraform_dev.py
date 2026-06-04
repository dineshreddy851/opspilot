import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INFRA = ROOT / "infra" / "dev"


class TerraformDevelopmentStackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (INFRA / "main.tf").read_text(encoding="utf-8")
        cls.versions = (INFRA / "versions.tf").read_text(encoding="utf-8")
        cls.variables = (INFRA / "variables.tf").read_text(encoding="utf-8")
        cls.outputs = (INFRA / "outputs.tf").read_text(encoding="utf-8")
        cls.approval = (INFRA / "approval.tf").read_text(encoding="utf-8")
        cls.web = (INFRA / "web.tf").read_text(encoding="utf-8")
        cls.operations = (INFRA / "operations.tf").read_text(encoding="utf-8")
        cls.all_terraform = "\n".join(
            (
                cls.main,
                cls.versions,
                cls.variables,
                cls.outputs,
                cls.approval,
                cls.web,
                cls.operations,
            )
        )

    def test_required_checkpoint_resources_exist(self):
        for resource in (
            'resource "aws_apigatewayv2_api" "api"',
            'resource "aws_apigatewayv2_route" "requests"',
            'resource "aws_lambda_function" "api"',
            'resource "aws_dynamodb_table" "audit"',
            'resource "aws_cloudwatch_log_group" "api"',
            'resource "aws_cloudwatch_metric_alarm" "lambda_errors"',
            'resource "aws_cognito_user_pool" "api"',
            'resource "aws_cognito_resource_server" "api"',
            'resource "aws_cognito_user_pool_client" "web"',
            'resource "aws_apigatewayv2_authorizer" "jwt"',
            'resource "aws_apigatewayv2_route" "health"',
        ):
            self.assertIn(resource, self.main)

    def test_lambda_runtime_route_and_retention(self):
        self.assertIn('runtime       = "python3.13"', self.main)
        self.assertRegex(self.main, r'route_key\s+=\s+"POST /requests"')
        self.assertRegex(self.main, r'route_key\s+=\s+"GET /health"')
        self.assertIn("retention_in_days = var.log_retention_days", self.main)
        self.assertIn("retention_in_days = var.log_retention_days", self.approval)
        self.assertIn('billing_mode = "PAY_PER_REQUEST"', self.main)

    def test_lambda_permissions_are_narrow(self):
        expected_actions = {
            "cloudwatch:DescribeAlarms",
            "ec2:DescribeInstances",
            "dynamodb:PutItem",
            "dynamodb:GetItem",
            "dynamodb:Query",
            "logs:CreateLogStream",
            "logs:PutLogEvents",
            "bedrock:InvokeModel",
            "states:StartExecution",
        }
        lambda_policy = self.main.split(
            'data "aws_iam_policy_document" "lambda" {', 1
        )[1].split('resource "aws_iam_role_policy" "lambda"', 1)[0]
        actions = set(re.findall(r'"([a-z0-9]+:[A-Za-z0-9*]+)"', lambda_policy))
        self.assertEqual(actions, expected_actions)
        self.assertIn("resources = [aws_dynamodb_table.audit.arn]", lambda_policy)
        self.assertIn("actor-subject-timestamp-index", lambda_policy)
        self.assertIn("requested-by-updated-at-index", lambda_policy)
        self.assertIn("resources = [aws_sfn_state_machine.approval.arn]", lambda_policy)
        self.assertIn("aws_cloudwatch_log_group.api.arn", lambda_policy)
        self.assertIn("resources = [local.bedrock_model_arn]", lambda_policy)
        self.assertNotIn("bedrock:InvokeModelWithResponseStream", lambda_policy)
        self.assertNotIn('"Action": "*"', self.all_terraform)
        self.assertNotRegex(self.all_terraform, r'"[a-z0-9]+:\*"')

    def test_common_tags_are_defined(self):
        for tag in ("Project", "Environment", "Owner", "ManagedBy"):
            self.assertRegex(self.main, rf"(?m)^\s*{tag}\s*=")

    def test_service_is_packaged_and_expected_outputs_exist(self):
        self.assertIn('source_dir       = "${path.module}/../../services/api"', self.main)
        for output in (
            'output "api_url"',
            'output "audit_table_name"',
            'output "lambda_function_name"',
        ):
            self.assertIn(output, self.outputs)
        self.assertIn('trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")', self.outputs)

    def test_bedrock_is_configurable_and_disabled_by_default(self):
        self.assertIn('variable "bedrock_enabled"', self.variables)
        self.assertIn('variable "bedrock_model_id"', self.variables)
        self.assertRegex(
            self.variables,
            r'(?s)variable "bedrock_enabled" \{.*?default\s+=\s+false',
        )
        self.assertRegex(
            self.main,
            r"BEDROCK_ENABLED\s+=\s+tostring\(var\.bedrock_enabled\)",
        )
        self.assertRegex(
            self.main,
            r"BEDROCK_MODEL_ID\s+=\s+var\.bedrock_model_id",
        )
        self.assertIn("for_each = var.bedrock_enabled ? [1] : []", self.main)
        self.assertIn(
            '":bedrock:",\n    var.aws_region,\n    "::foundation-model/"',
            self.main,
        )

    def test_cognito_public_client_and_scopes_exist(self):
        self.assertRegex(self.main, r"generate_secret\s+=\s+false")
        self.assertIn('scope_name        = "read"', self.main)
        self.assertIn('scope_name        = "apply"', self.main)
        self.assertRegex(self.main, r'allowed_oauth_flows\s+=\s+\["code"\]')
        self.assertRegex(self.main, r"allowed_oauth_scopes\s+=\s+concat")
        self.assertRegex(
            self.main,
            r'cognito_resource_identifier\s+=\s+"opspilot"',
        )

    def test_requests_route_requires_jwt_read_scope_and_health_is_public(self):
        requests_route = self.main.split(
            'resource "aws_apigatewayv2_route" "requests" {', 1
        )[1].split('resource "aws_apigatewayv2_route" "health"', 1)[0]
        health_route = self.main.split(
            'resource "aws_apigatewayv2_route" "health" {', 1
        )[1].split('resource "aws_apigatewayv2_stage" "default"', 1)[0]

        self.assertIn('authorization_type   = "JWT"', requests_route)
        self.assertIn("authorizer_id", requests_route)
        self.assertIn(
            'authorization_scopes = ["${local.cognito_resource_identifier}/read"]',
            requests_route,
        )
        self.assertIn('authorization_type = "NONE"', health_route)
        self.assertNotIn("authorizer_id", health_route)
        self.assertNotIn("authorization_scopes", health_route)

    def test_jwt_authorizer_uses_cognito_issuer_and_public_client_audience(self):
        authorizer = self.main.split(
            'resource "aws_apigatewayv2_authorizer" "jwt" {', 1
        )[1].split('resource "aws_apigatewayv2_integration" "api"', 1)[0]
        self.assertIn('authorizer_type  = "JWT"', authorizer)
        self.assertIn('identity_sources = ["$request.header.Authorization"]', authorizer)
        self.assertIn("audience = [aws_cognito_user_pool_client.web.id]", authorizer)
        self.assertIn("issuer   = aws_cognito_user_pool.api.endpoint", authorizer)

    def test_controlled_action_workflow_resources_exist(self):
        for resource in (
            'resource "aws_sfn_state_machine" "approval"',
            'resource "aws_sns_topic" "approvals"',
            'resource "aws_dynamodb_table" "approvals"',
            'resource "aws_lambda_function" "approval"',
            'resource "aws_lambda_function" "mutation"',
        ):
            self.assertIn(resource, self.approval)

    def test_standard_workflow_handles_approval_rejection_expiry_and_duplicates(self):
        self.assertIn('type       = "STANDARD"', self.approval)
        self.assertIn("lambda:invoke.waitForTaskToken", self.approval)
        self.assertIn('ErrorEquals = ["States.Timeout"]', self.approval)
        self.assertIn(
            "var.approval_workflow_timeout_seconds > var.approval_timeout_seconds",
            self.approval,
        )
        for state in (
            "IsDuplicate",
            "DuplicateRequest",
            "ExecuteControlledAction",
            "RecordRejected",
            "RecordExpired",
        ):
            self.assertIn(state, self.approval)
        self.assertRegex(
            self.approval,
            r'(?s)StringEquals\s+=\s+"APPROVED".*?Next\s+=\s+"ExecuteControlledAction"',
        )
        self.assertRegex(
            self.approval,
            r'(?s)StringEquals\s+=\s+"REJECTED".*?Next\s+=\s+"RecordRejected"',
        )

    def test_mutation_lambda_is_only_called_on_approved_workflow_branch(self):
        definition = self.approval.split('data "archive_file" "approval"', 1)[0]
        self.assertEqual(
            definition.count("FunctionName = aws_lambda_function.mutation.arn"),
            1,
        )
        self.assertRegex(
            definition,
            r'(?s)ExecuteControlledAction\s+=\s+\{.*?aws_lambda_function\.mutation\.arn',
        )

    def test_controlled_action_starts_in_dry_run_mode(self):
        self.assertRegex(
            self.variables,
            r'(?s)variable "controlled_action_dry_run" \{.*?default\s+=\s+true',
        )
        self.assertIn(
            "DRY_RUN                       = tostring(var.controlled_action_dry_run)",
            self.approval,
        )
        mutation_policy = self.approval.split(
            'data "aws_iam_policy_document" "mutation_lambda" {', 1
        )[1].split('resource "aws_iam_role_policy" "mutation_lambda"', 1)[0]
        self.assertIn("for_each = var.controlled_action_dry_run ? [] : [1]", mutation_policy)
        self.assertIn('actions   = ["ecs:UpdateService"]', mutation_policy)

    def test_orchestrators_have_no_mutating_aws_permissions(self):
        api_policy = self.main.split(
            'data "aws_iam_policy_document" "lambda" {', 1
        )[1].split('resource "aws_iam_role_policy" "lambda"', 1)[0]
        workflow_policy = self.approval.split(
            'data "aws_iam_policy_document" "approval_workflow" {', 1
        )[1].split('resource "aws_iam_role_policy" "approval_workflow"', 1)[0]

        self.assertNotIn("ecs:", api_policy)
        self.assertNotIn("ecs:", workflow_policy)
        self.assertEqual(
            set(re.findall(r'"([a-z0-9]+:[A-Za-z0-9*]+)"', workflow_policy)),
            {"lambda:InvokeFunction"},
        )
        self.assertIn("aws_lambda_function.approval.arn", workflow_policy)
        self.assertIn("aws_lambda_function.mutation.arn", workflow_policy)

    def test_web_interface_uses_private_s3_and_cloudfront_oac(self):
        for resource in (
            'resource "aws_s3_bucket" "web"',
            'resource "aws_s3_bucket_public_access_block" "web"',
            'resource "aws_cloudfront_origin_access_control" "web"',
            'resource "aws_cloudfront_distribution" "web"',
            'resource "aws_s3_bucket_policy" "web"',
        ):
            self.assertIn(resource, self.web)
        for setting in (
            "block_public_acls       = true",
            "block_public_policy     = true",
            "ignore_public_acls      = true",
            "restrict_public_buckets = true",
        ):
            self.assertIn(setting, self.web)
        self.assertIn('signing_behavior                  = "always"', self.web)
        self.assertIn('signing_protocol                  = "sigv4"', self.web)
        self.assertIn('identifiers = ["cloudfront.amazonaws.com"]', self.web)
        self.assertIn("values   = [aws_cloudfront_distribution.web.arn]", self.web)
        self.assertIn("content_security_policy", self.web)
        self.assertIn("frame-ancestors 'none'", self.web)
        self.assertNotIn("aws_s3_bucket_website", self.web)
        self.assertNotRegex(self.web, r'acl\s*=\s*"public-read"')

    def test_web_assets_and_public_runtime_config_are_hosted(self):
        for resource in (
            'resource "aws_s3_object" "web_index"',
            'resource "aws_s3_object" "web_styles"',
            'resource "aws_s3_object" "web_app"',
            'resource "aws_s3_object" "web_config"',
        ):
            self.assertIn(resource, self.web)
        self.assertIn('source        = "${local.web_source_dir}/src/main.ts"', self.web)
        self.assertIn("aws_cognito_user_pool_client.web.id", self.web)
        self.assertIn('trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")', self.web)
        self.assertNotRegex(
            self.web.lower(),
            r"aws_(access|secret)_key|secret_access_key|task_token|tasktoken",
        )

    def test_cognito_hosted_ui_uses_cloudfront_callback(self):
        self.assertIn('resource "aws_cognito_user_pool_domain" "web"', self.web)
        self.assertIn(
            '"https://${aws_cloudfront_distribution.web.domain_name}/callback"',
            self.main,
        )
        self.assertIn(
            '"https://${aws_cloudfront_distribution.web.domain_name}"',
            self.main,
        )
        self.assertIn('"${local.cognito_resource_identifier}/apply"', self.web)
        self.assertIn('"${local.cognito_resource_identifier}/read"', self.web)

    def test_browser_api_routes_have_narrow_cognito_scopes(self):
        controlled = self.main.split(
            'resource "aws_apigatewayv2_route" "controlled_requests" {', 1
        )[1].split('resource "aws_apigatewayv2_route" "timeline"', 1)[0]
        timeline = self.main.split(
            'resource "aws_apigatewayv2_route" "timeline" {', 1
        )[1].split('resource "aws_apigatewayv2_route" "approval_status"', 1)[0]
        approval_status = self.main.split(
            'resource "aws_apigatewayv2_route" "approval_status" {', 1
        )[1].split('resource "aws_apigatewayv2_route" "health"', 1)[0]

        self.assertIn('route_key            = "POST /controlled-requests"', controlled)
        self.assertIn(
            'authorization_scopes = ["${local.cognito_resource_identifier}/apply"]',
            controlled,
        )
        self.assertIn('route_key            = "GET /timeline"', timeline)
        self.assertIn(
            'authorization_scopes = ["${local.cognito_resource_identifier}/read"]',
            timeline,
        )
        self.assertIn('route_key            = "GET /approvals/{request_id}"', approval_status)
        self.assertIn(
            'authorization_scopes = ["${local.cognito_resource_identifier}/read"]',
            approval_status,
        )
        self.assertIn(
            'allow_origins = distinct(concat(var.web_allowed_origins, ["https://${aws_cloudfront_distribution.web.domain_name}"]))',
            self.main,
        )

    def test_timeline_indexes_are_user_scoped(self):
        self.assertIn('name            = "actor-subject-timestamp-index"', self.main)
        self.assertIn('attribute_name = "actor_subject"', self.main)
        self.assertIn('key_type       = "HASH"', self.main)
        self.assertIn('name            = "requested-by-updated-at-index"', self.approval)
        self.assertIn('attribute_name = "requested_by"', self.approval)
        self.assertIn('key_type       = "RANGE"', self.approval)

    def test_company_ready_observability_resources_exist(self):
        for resource in (
            'resource "aws_cloudwatch_dashboard" "operations"',
            'resource "aws_cloudwatch_metric_alarm" "api_lambda_throttles"',
            'resource "aws_cloudwatch_metric_alarm" "approval_lambda_errors"',
            'resource "aws_cloudwatch_metric_alarm" "approval_lambda_throttles"',
            'resource "aws_cloudwatch_metric_alarm" "mutation_lambda_errors"',
            'resource "aws_cloudwatch_metric_alarm" "mutation_lambda_throttles"',
            'resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx"',
            'resource "aws_sns_topic" "operations_alerts"',
        ):
            self.assertIn(resource, self.operations)
        self.assertIn("aws_sns_topic.operations_alerts.arn", self.operations)
        self.assertIn("aws_sns_topic.operations_alerts.arn", self.main)

    def test_cloudtrail_is_multi_region_private_and_retained(self):
        for resource in (
            'resource "aws_cloudtrail" "management"',
            'resource "aws_s3_bucket" "cloudtrail"',
            'resource "aws_s3_bucket_public_access_block" "cloudtrail"',
            'resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail"',
            'resource "aws_s3_bucket_policy" "cloudtrail"',
        ):
            self.assertIn(resource, self.operations)
        self.assertIn("is_multi_region_trail         = true", self.operations)
        self.assertIn("include_global_service_events = true", self.operations)
        self.assertIn("enable_log_file_validation    = true", self.operations)
        self.assertIn("include_management_events = true", self.operations)
        self.assertNotIn("data_resource", self.operations)
        self.assertIn("days = var.cloudtrail_retention_days", self.operations)
        self.assertIn("force_destroy = false", self.operations)
        for setting in (
            "block_public_acls       = true",
            "block_public_policy     = true",
            "ignore_public_acls      = true",
            "restrict_public_buckets = true",
        ):
            self.assertIn(setting, self.operations)

    def test_api_access_logs_have_explicit_retention(self):
        self.assertIn(
            'resource "aws_cloudwatch_log_group" "api_access"',
            self.main,
        )
        stage = self.main.split(
            'resource "aws_apigatewayv2_stage" "default" {', 1
        )[1].split('resource "aws_lambda_permission" "api_gateway"', 1)[0]
        self.assertIn("access_log_settings", stage)
        self.assertIn("aws_cloudwatch_log_group.api_access.arn", stage)
        self.assertIn(
            'resource "aws_cloudwatch_log_group" "approval_workflow"',
            self.approval,
        )
        self.assertIn("include_execution_data = false", self.approval)
        self.assertIn('level                  = "ERROR"', self.approval)
        self.assertIn(
            "aws_cloudwatch_log_group.approval_workflow.arn",
            self.approval,
        )
        self.assertIn('variable "log_retention_days"', self.variables)
        self.assertIn('variable "cloudtrail_retention_days"', self.variables)

    def test_company_ready_outputs_exist(self):
        for output in (
            'output "operations_dashboard_name"',
            'output "operations_alert_topic_arn"',
            'output "cloudtrail_name"',
            'output "cloudtrail_bucket_name"',
        ):
            self.assertIn(output, self.outputs)


if __name__ == "__main__":
    unittest.main()
