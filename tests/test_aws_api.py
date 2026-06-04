import json
import os
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from services.api.lambda_function import AwsApiApplication, lambda_handler


class FakeCloudWatch:
    def __init__(self, response=None, error=None):
        self.response = response or {"MetricAlarms": []}
        self.error = error
        self.calls = []

    def describe_alarms(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeEc2:
    def __init__(self, response=None):
        self.response = response or {"Reservations": []}
        self.calls = []

    def describe_instances(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeAuditTable:
    def __init__(self):
        self.items = []

    def put_item(self, *, Item):
        self.items.append(Item)


class FakeDynamoDb:
    def __init__(self, table):
        self.table = table
        self.table_names = []

    def Table(self, table_name):
        self.table_names.append(table_name)
        return self.table


class AwsApiApplicationTests(unittest.TestCase):
    def setUp(self):
        self.cloudwatch = FakeCloudWatch()
        self.ec2 = FakeEc2()
        self.audit = FakeAuditTable()
        self.application = AwsApiApplication(
            cloudwatch_client=self.cloudwatch,
            ec2_client=self.ec2,
            audit_table=self.audit,
        )

    def body(self, response):
        return json.loads(response["body"])

    def test_lists_cloudwatch_alarms_as_simple_json_and_audits(self):
        self.cloudwatch.response = {
            "MetricAlarms": [
                {
                    "AlarmName": "opspilot-errors",
                    "StateValue": "ALARM",
                    "StateReason": "Threshold crossed",
                    "StateUpdatedTimestamp": datetime(2026, 6, 4, tzinfo=UTC),
                    "IgnoredAwsField": {"complex": "value"},
                }
            ]
        }

        response = self.application.handle("show CloudWatch alarms")
        body = self.body(response)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["tool"], "list_cloudwatch_alarms")
        self.assertEqual(body["result"]["alarm_count"], 1)
        self.assertEqual(body["result"]["alarms"][0]["name"], "opspilot-errors")
        self.assertEqual(
            self.cloudwatch.calls,
            [{"StateValue": "ALARM", "MaxRecords": 50}],
        )
        self.assertEqual(self.audit.items[0]["status"], "succeeded")

    def test_lists_only_project_tagged_ec2_instances_and_audits(self):
        self.ec2.response = {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-0123456789abcdef0",
                            "InstanceType": "t3.micro",
                            "State": {"Name": "running"},
                            "PrivateIpAddress": "10.0.0.10",
                            "Tags": [{"Key": "Name", "Value": "demo"}],
                        }
                    ]
                }
            ]
        }

        response = self.application.handle("list OpsPilot EC2 instances")
        body = self.body(response)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["result"]["instance_count"], 1)
        self.assertEqual(body["result"]["instances"][0]["name"], "demo")
        self.assertEqual(
            self.ec2.calls,
            [{"Filters": [{"Name": "tag:Project", "Values": ["OpsPilot"]}]}],
        )
        self.assertEqual(len(self.audit.items), 1)

    def test_refuses_destructive_request_without_aws_read_calls(self):
        response = self.application.handle("delete every EC2 instance")
        body = self.body(response)

        self.assertEqual(response["statusCode"], 403)
        self.assertEqual(body["status"], "refused")
        self.assertEqual(body["reason"], "mutating_or_destructive_request")
        self.assertEqual(self.cloudwatch.calls, [])
        self.assertEqual(self.ec2.calls, [])
        self.assertEqual(self.audit.items[0]["status"], "refused")

    def test_refuses_unknown_request_and_audits(self):
        response = self.application.handle("tell me a joke")
        body = self.body(response)

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body["reason"], "unknown_request")
        self.assertEqual(self.cloudwatch.calls, [])
        self.assertEqual(self.ec2.calls, [])
        self.assertEqual(len(self.audit.items), 1)

    def test_audits_tool_failure(self):
        self.cloudwatch.error = RuntimeError("service unavailable")

        with self.assertLogs(level="ERROR"):
            response = self.application.handle("show alarms")
        body = self.body(response)

        self.assertEqual(response["statusCode"], 500)
        self.assertEqual(body["status"], "failed")
        self.assertEqual(self.audit.items[0]["status"], "failed")
        self.assertEqual(self.audit.items[0]["tool"], "list_cloudwatch_alarms")

    def test_lambda_handler_reads_api_gateway_body_without_real_aws_calls(self):
        dynamodb = FakeDynamoDb(self.audit)

        def client(service_name):
            return {"cloudwatch": self.cloudwatch, "ec2": self.ec2}[service_name]

        event = {"body": json.dumps({"request": "show alarms"})}
        with (
            patch.dict(os.environ, {"AUDIT_TABLE_NAME": "opspilot-audit-dev"}),
            patch("services.api.lambda_function.boto3.client", side_effect=client),
            patch("services.api.lambda_function.boto3.resource", return_value=dynamodb),
        ):
            response = lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(dynamodb.table_names, ["opspilot-audit-dev"])
        self.assertEqual(len(self.audit.items), 1)


if __name__ == "__main__":
    unittest.main()
