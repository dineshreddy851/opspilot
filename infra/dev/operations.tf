locals {
  cloudtrail_name = "${local.name_prefix}-management"
  cloudtrail_arn = join("", [
    "arn:",
    data.aws_partition.current.partition,
    ":cloudtrail:",
    var.aws_region,
    ":",
    data.aws_caller_identity.current.account_id,
    ":trail/",
    local.cloudtrail_name,
  ])
}

resource "aws_sns_topic" "operations_alerts" {
  name = "${local.name_prefix}-operations-alerts"
}

resource "aws_sns_topic_subscription" "operations_email" {
  count = var.operations_alert_email == "" ? 0 : 1

  topic_arn = aws_sns_topic.operations_alerts.arn
  protocol  = "email"
  endpoint  = var.operations_alert_email
}

resource "aws_cloudwatch_metric_alarm" "api_lambda_throttles" {
  alarm_name          = "${local.name_prefix}-api-throttles"
  alarm_description   = "OpsPilot API Lambda was throttled."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]
  ok_actions          = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "approval_lambda_errors" {
  alarm_name          = "${local.name_prefix}-approval-errors"
  alarm_description   = "OpsPilot approval Lambda reported at least one error."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]
  ok_actions          = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.approval.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "approval_lambda_throttles" {
  alarm_name          = "${local.name_prefix}-approval-throttles"
  alarm_description   = "OpsPilot approval Lambda was throttled."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]
  ok_actions          = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.approval.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "mutation_lambda_errors" {
  alarm_name          = "${local.name_prefix}-mutation-errors"
  alarm_description   = "OpsPilot mutation Lambda reported at least one error."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]
  ok_actions          = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.mutation.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "mutation_lambda_throttles" {
  alarm_name          = "${local.name_prefix}-mutation-throttles"
  alarm_description   = "OpsPilot mutation Lambda was throttled."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]
  ok_actions          = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    FunctionName = aws_lambda_function.mutation.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx" {
  alarm_name          = "${local.name_prefix}-api-5xx"
  alarm_description   = "OpsPilot HTTP API returned at least one server error."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "5xx"
  namespace           = "AWS/ApiGateway"
  period              = 60
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.operations_alerts.arn]
  ok_actions          = [aws_sns_topic.operations_alerts.arn]

  dimensions = {
    ApiId = aws_apigatewayv2_api.api.id
    Stage = aws_apigatewayv2_stage.default.name
  }
}

resource "aws_cloudwatch_dashboard" "operations" {
  dashboard_name = "${local.name_prefix}-operations"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 2
        properties = {
          markdown = "# OpsPilot operational health\nReview alarms first, then use `docs/runbook.md` to investigate."
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 12
        height = 6
        properties = {
          title  = "Lambda errors and throttles"
          view   = "timeSeries"
          region = var.aws_region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.api.function_name],
            ["AWS/Lambda", "Throttles", "FunctionName", aws_lambda_function.api.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.approval.function_name],
            ["AWS/Lambda", "Throttles", "FunctionName", aws_lambda_function.approval.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.mutation.function_name],
            ["AWS/Lambda", "Throttles", "FunctionName", aws_lambda_function.mutation.function_name],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 2
        width  = 12
        height = 6
        properties = {
          title  = "HTTP API requests and 5xx"
          view   = "timeSeries"
          region = var.aws_region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiId", aws_apigatewayv2_api.api.id, "Stage", aws_apigatewayv2_stage.default.name],
            ["AWS/ApiGateway", "5xx", "ApiId", aws_apigatewayv2_api.api.id, "Stage", aws_apigatewayv2_stage.default.name],
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "Step Functions outcomes"
          view   = "timeSeries"
          region = var.aws_region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/States", "ExecutionsSucceeded", "StateMachineArn", aws_sfn_state_machine.approval.arn],
            ["AWS/States", "ExecutionsFailed", "StateMachineArn", aws_sfn_state_machine.approval.arn],
            ["AWS/States", "ExecutionsTimedOut", "StateMachineArn", aws_sfn_state_machine.approval.arn],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 8
        width  = 12
        height = 6
        properties = {
          title  = "DynamoDB request activity"
          view   = "timeSeries"
          region = var.aws_region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.audit.name],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.audit.name],
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.approvals.name],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.approvals.name],
          ]
        }
      },
    ]
  })
}

resource "aws_s3_bucket" "cloudtrail" {
  bucket        = "${local.name_prefix}-cloudtrail-${var.aws_region}-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  rule {
    id     = "expire-cloudtrail-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = var.cloudtrail_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.cloudtrail_retention_days
    }
  }
}

data "aws_iam_policy_document" "cloudtrail_bucket" {
  statement {
    sid       = "CloudTrailAclCheck"
    effect    = "Allow"
    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.cloudtrail.arn]

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [local.cloudtrail_arn]
    }
  }

  statement {
    sid     = "CloudTrailWrite"
    effect  = "Allow"
    actions = ["s3:PutObject"]
    resources = [
      "${aws_s3_bucket.cloudtrail.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*",
    ]

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [local.cloudtrail_arn]
    }
  }
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id
  policy = data.aws_iam_policy_document.cloudtrail_bucket.json
}

resource "aws_cloudtrail" "management" {
  name                          = local.cloudtrail_name
  s3_bucket_name                = aws_s3_bucket.cloudtrail.bucket
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true

  event_selector {
    include_management_events = true
    read_write_type           = "All"
  }

  depends_on = [aws_s3_bucket_policy.cloudtrail]
}
