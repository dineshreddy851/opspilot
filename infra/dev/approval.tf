locals {
  stepfunctions_lambda_invoke_arn = "arn:${data.aws_partition.current.partition}:states:::lambda:invoke"
  stepfunctions_callback_arn      = "arn:${data.aws_partition.current.partition}:states:::lambda:invoke.waitForTaskToken"

  approval_workflow_definition = {
    Comment        = "OpsPilot controlled-action approval workflow."
    StartAt        = "RecordPending"
    TimeoutSeconds = var.approval_workflow_timeout_seconds
    States = {
      RecordPending = {
        Type     = "Task"
        Resource = local.stepfunctions_lambda_invoke_arn
        Parameters = {
          FunctionName = aws_lambda_function.approval.arn
          Payload = {
            operation   = "record_pending"
            "request.$" = "$"
          }
        }
        OutputPath = "$.Payload"
        Next       = "IsDuplicate"
      }
      IsDuplicate = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.duplicate"
            BooleanEquals = true
            Next          = "DuplicateRequest"
          }
        ]
        Default = "NotifyAndWaitForApproval"
      }
      NotifyAndWaitForApproval = {
        Type           = "Task"
        Resource       = local.stepfunctions_callback_arn
        TimeoutSeconds = var.approval_timeout_seconds
        Parameters = {
          FunctionName = aws_lambda_function.approval.arn
          Payload = {
            operation      = "notify_and_wait"
            "request.$"    = "$"
            "task_token.$" = "$$.Task.Token"
          }
        }
        Catch = [
          {
            ErrorEquals = ["States.Timeout"]
            ResultPath  = "$.approval_error"
            Next        = "RecordExpired"
          }
        ]
        Next = "ApprovalDecision"
      }
      ApprovalDecision = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.decision"
            StringEquals = "APPROVED"
            Next         = "ExecuteControlledAction"
          },
          {
            Variable     = "$.decision"
            StringEquals = "REJECTED"
            Next         = "RecordRejected"
          }
        ]
        Default = "RecordRejected"
      }
      ExecuteControlledAction = {
        Type     = "Task"
        Resource = local.stepfunctions_lambda_invoke_arn
        Parameters = {
          FunctionName = aws_lambda_function.mutation.arn
          "Payload.$"  = "$"
        }
        ResultPath = "$.mutation"
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.mutation_error"
            Next        = "RecordFailed"
          }
        ]
        Next = "RecordCompleted"
      }
      RecordCompleted = {
        Type     = "Task"
        Resource = local.stepfunctions_lambda_invoke_arn
        Parameters = {
          FunctionName = aws_lambda_function.approval.arn
          Payload = {
            operation      = "record_result"
            "request_id.$" = "$.request_id"
            status         = "COMPLETED"
            "result.$"     = "$.mutation.Payload"
          }
        }
        OutputPath = "$.Payload"
        Next       = "Completed"
      }
      RecordRejected = {
        Type     = "Task"
        Resource = local.stepfunctions_lambda_invoke_arn
        Parameters = {
          FunctionName = aws_lambda_function.approval.arn
          Payload = {
            operation      = "record_result"
            "request_id.$" = "$.request_id"
            status         = "REJECTED"
          }
        }
        OutputPath = "$.Payload"
        Next       = "Rejected"
      }
      RecordExpired = {
        Type     = "Task"
        Resource = local.stepfunctions_lambda_invoke_arn
        Parameters = {
          FunctionName = aws_lambda_function.approval.arn
          Payload = {
            operation      = "record_result"
            "request_id.$" = "$.request_id"
            status         = "EXPIRED"
          }
        }
        OutputPath = "$.Payload"
        Next       = "Expired"
      }
      RecordFailed = {
        Type     = "Task"
        Resource = local.stepfunctions_lambda_invoke_arn
        Parameters = {
          FunctionName = aws_lambda_function.approval.arn
          Payload = {
            operation      = "record_result"
            "request_id.$" = "$.request_id"
            status         = "FAILED"
            "result.$"     = "$.mutation_error"
          }
        }
        OutputPath = "$.Payload"
        Next       = "Failed"
      }
      DuplicateRequest = {
        Type = "Succeed"
      }
      Completed = {
        Type = "Succeed"
      }
      Rejected = {
        Type = "Succeed"
      }
      Expired = {
        Type = "Succeed"
      }
      Failed = {
        Type  = "Fail"
        Error = "ControlledActionFailed"
        Cause = "The approved controlled action failed."
      }
    }
  }
}

data "archive_file" "approval" {
  type             = "zip"
  source_dir       = "${path.module}/../../services/approval"
  output_file_mode = "0666"
  output_path      = "${path.module}/opspilot-approval.zip"
  excludes         = ["__pycache__", "*.pyc"]
}

data "archive_file" "mutation" {
  type             = "zip"
  source_dir       = "${path.module}/../../services/mutation"
  output_file_mode = "0666"
  output_path      = "${path.module}/opspilot-mutation.zip"
  excludes         = ["__pycache__", "*.pyc"]
}

resource "aws_dynamodb_table" "approvals" {
  name         = "${local.name_prefix}-approvals"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"

  attribute {
    name = "request_id"
    type = "S"
  }

  attribute {
    name = "requested_by"
    type = "S"
  }

  attribute {
    name = "updated_at"
    type = "S"
  }

  global_secondary_index {
    name            = "requested-by-updated-at-index"
    projection_type = "ALL"

    key_schema {
      attribute_name = "requested_by"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "updated_at"
      key_type       = "RANGE"
    }
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

resource "aws_sns_topic" "approvals" {
  name = "${local.name_prefix}-approvals"
}

resource "aws_sns_topic_subscription" "approval_email" {
  count = var.approval_email == "" ? 0 : 1

  topic_arn = aws_sns_topic.approvals.arn
  protocol  = "email"
  endpoint  = var.approval_email
}

resource "aws_cloudwatch_log_group" "approval" {
  name              = "/aws/lambda/${local.name_prefix}-approval"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "mutation" {
  name              = "/aws/lambda/${local.name_prefix}-mutation"
  retention_in_days = 14
}

resource "aws_iam_role" "approval_lambda" {
  name               = "${local.name_prefix}-approval-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "approval_lambda" {
  statement {
    sid    = "ManageApprovalRecords"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
    ]
    resources = [aws_dynamodb_table.approvals.arn]
  }

  statement {
    sid       = "PublishApprovalNotifications"
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.approvals.arn]
  }

  statement {
    sid       = "ResumeApprovalCallbacks"
    effect    = "Allow"
    actions   = ["states:SendTaskSuccess"]
    resources = ["*"]
  }

  statement {
    sid    = "WriteApprovalLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${trimsuffix(aws_cloudwatch_log_group.approval.arn, ":*")}:*"]
  }
}

resource "aws_iam_role_policy" "approval_lambda" {
  name   = "${local.name_prefix}-approval-policy"
  role   = aws_iam_role.approval_lambda.id
  policy = data.aws_iam_policy_document.approval_lambda.json
}

resource "aws_lambda_function" "approval" {
  function_name = "${local.name_prefix}-approval"
  description   = "Records and resolves OpsPilot controlled-action approvals."
  role          = aws_iam_role.approval_lambda.arn
  runtime       = "python3.13"
  handler       = "lambda_function.lambda_handler"

  filename         = data.archive_file.approval.output_path
  source_code_hash = data.archive_file.approval.output_base64sha256

  architectures = ["arm64"]
  memory_size   = 256
  timeout       = 15

  environment {
    variables = {
      APPROVAL_TABLE_NAME    = aws_dynamodb_table.approvals.name
      APPROVAL_TOPIC_ARN     = aws_sns_topic.approvals.arn
      CONTROLLED_ACTION_NAME = var.controlled_action_name
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.approval,
    aws_iam_role_policy.approval_lambda,
  ]
}

resource "aws_iam_role" "mutation_lambda" {
  name               = "${local.name_prefix}-mutation-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "mutation_lambda" {
  statement {
    sid    = "WriteMutationLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${trimsuffix(aws_cloudwatch_log_group.mutation.arn, ":*")}:*"]
  }

  dynamic "statement" {
    for_each = var.controlled_action_dry_run ? [] : [1]

    content {
      sid       = "RestartApprovedEcsService"
      effect    = "Allow"
      actions   = ["ecs:UpdateService"]
      resources = [var.controlled_action_ecs_service_arn]
    }
  }
}

resource "aws_iam_role_policy" "mutation_lambda" {
  name   = "${local.name_prefix}-mutation-policy"
  role   = aws_iam_role.mutation_lambda.id
  policy = data.aws_iam_policy_document.mutation_lambda.json
}

resource "aws_lambda_function" "mutation" {
  function_name = "${local.name_prefix}-mutation"
  description   = "Runs one approved OpsPilot controlled action."
  role          = aws_iam_role.mutation_lambda.arn
  runtime       = "python3.13"
  handler       = "lambda_function.lambda_handler"

  filename         = data.archive_file.mutation.output_path
  source_code_hash = data.archive_file.mutation.output_base64sha256

  architectures = ["arm64"]
  memory_size   = 256
  timeout       = 30

  environment {
    variables = {
      CONTROLLED_ACTION_NAME        = var.controlled_action_name
      CONTROLLED_ACTION_ECS_CLUSTER = var.controlled_action_ecs_cluster
      CONTROLLED_ACTION_ECS_SERVICE = var.controlled_action_ecs_service
      DRY_RUN                       = tostring(var.controlled_action_dry_run)
    }
  }

  lifecycle {
    precondition {
      condition     = var.controlled_action_dry_run || var.controlled_action_ecs_service_arn != ""
      error_message = "controlled_action_ecs_service_arn is required when DRY_RUN is false."
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.mutation,
    aws_iam_role_policy.mutation_lambda,
  ]
}

data "aws_iam_policy_document" "stepfunctions_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "approval_workflow" {
  name               = "${local.name_prefix}-approval-workflow-role"
  assume_role_policy = data.aws_iam_policy_document.stepfunctions_assume_role.json
}

data "aws_iam_policy_document" "approval_workflow" {
  statement {
    sid     = "InvokeApprovalAndMutationFunctions"
    effect  = "Allow"
    actions = ["lambda:InvokeFunction"]
    resources = [
      aws_lambda_function.approval.arn,
      aws_lambda_function.mutation.arn,
    ]
  }
}

resource "aws_iam_role_policy" "approval_workflow" {
  name   = "${local.name_prefix}-approval-workflow-policy"
  role   = aws_iam_role.approval_workflow.id
  policy = data.aws_iam_policy_document.approval_workflow.json
}

resource "aws_sfn_state_machine" "approval" {
  name       = "${local.name_prefix}-approval"
  role_arn   = aws_iam_role.approval_workflow.arn
  type       = "STANDARD"
  definition = jsonencode(local.approval_workflow_definition)

  lifecycle {
    precondition {
      condition     = var.approval_workflow_timeout_seconds > var.approval_timeout_seconds
      error_message = "approval_workflow_timeout_seconds must be greater than approval_timeout_seconds so expired requests are recorded."
    }
  }
}
