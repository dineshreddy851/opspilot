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
        ):
            self.assertIn(resource, self.main)

    def test_lambda_runtime_route_and_retention(self):
        self.assertIn('runtime       = "python3.13"', self.main)
        self.assertIn('route_key = "POST /requests"', self.main)
        self.assertIn("retention_in_days = 14", self.main)
        self.assertIn('billing_mode = "PAY_PER_REQUEST"', self.main)

    def test_lambda_permissions_are_narrow(self):
        expected_actions = {
            "cloudwatch:DescribeAlarms",
            "ec2:DescribeInstances",
            "dynamodb:PutItem",
            "logs:CreateLogStream",
            "logs:PutLogEvents",
        }
        lambda_policy = self.main.split(
            'data "aws_iam_policy_document" "lambda" {', 1
        )[1].split('resource "aws_iam_role_policy" "lambda"', 1)[0]
        actions = set(re.findall(r'"([a-z0-9]+:[A-Za-z0-9*]+)"', lambda_policy))
        self.assertEqual(actions, expected_actions)
        self.assertIn("resources = [aws_dynamodb_table.audit.arn]", lambda_policy)
        self.assertIn("aws_cloudwatch_log_group.api.arn", lambda_policy)
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


if __name__ == "__main__":
    unittest.main()
