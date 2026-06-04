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
        cls.all_terraform = "\n".join(
            (cls.main, cls.versions, cls.variables, cls.outputs)
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
        self.assertIn("retention_in_days = 14", self.main)
        self.assertIn('billing_mode = "PAY_PER_REQUEST"', self.main)

    def test_lambda_permissions_are_narrow(self):
        expected_actions = {
            "cloudwatch:DescribeAlarms",
            "ec2:DescribeInstances",
            "dynamodb:PutItem",
            "logs:CreateLogStream",
            "logs:PutLogEvents",
            "bedrock:InvokeModel",
        }
        lambda_policy = self.main.split(
            'data "aws_iam_policy_document" "lambda" {', 1
        )[1].split('resource "aws_iam_role_policy" "lambda"', 1)[0]
        actions = set(re.findall(r'"([a-z0-9]+:[A-Za-z0-9*]+)"', lambda_policy))
        self.assertEqual(actions, expected_actions)
        self.assertIn("resources = [aws_dynamodb_table.audit.arn]", lambda_policy)
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


if __name__ == "__main__":
    unittest.main()
