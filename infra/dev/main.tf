locals {
  project_name                = "OpsPilot"
  name_prefix                 = "${lower(local.project_name)}-${var.environment}"
  cognito_resource_identifier = "opspilot"
  bedrock_model_arn = join("", [
    "arn:",
    data.aws_partition.current.partition,
    ":bedrock:",
    var.aws_region,
    "::foundation-model/",
    var.bedrock_model_id,
  ])

  common_tags = {
    Project     = local.project_name
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "Terraform"
  }
}

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}

data "archive_file" "api" {
  type             = "zip"
  source_dir       = "${path.module}/../../services/api"
  output_file_mode = "0666"
  output_path      = "${path.module}/opspilot-api.zip"
  excludes         = ["__pycache__", "*.pyc"]
}

resource "aws_dynamodb_table" "audit" {
  name         = "${local.name_prefix}-audit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"

  attribute {
    name = "request_id"
    type = "S"
  }

  attribute {
    name = "actor_subject"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  global_secondary_index {
    name            = "actor-subject-timestamp-index"
    projection_type = "ALL"

    key_schema {
      attribute_name = "actor_subject"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "timestamp"
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

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = 14
}

resource "aws_cognito_user_pool" "api" {
  name = "${local.name_prefix}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  mfa_configuration        = "OPTIONAL"

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  software_token_mfa_configuration {
    enabled = true
  }
}

resource "aws_cognito_resource_server" "api" {
  identifier = local.cognito_resource_identifier
  name       = "${local.name_prefix}-api"

  scope {
    scope_name        = "read"
    scope_description = "Run approved read-only OpsPilot requests."
  }

  scope {
    scope_name        = "apply"
    scope_description = "Approve controlled OpsPilot changes in a future checkpoint."
  }

  user_pool_id = aws_cognito_user_pool.api.id
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "${local.name_prefix}-web"
  user_pool_id = aws_cognito_user_pool.api.id

  generate_secret                      = false
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = concat(["openid", "email", "profile"], aws_cognito_resource_server.api.scope_identifiers)
  callback_urls                        = distinct(concat(var.cognito_callback_urls, ["https://${aws_cloudfront_distribution.web.domain_name}/callback"]))
  logout_urls                          = distinct(concat(var.cognito_logout_urls, ["https://${aws_cloudfront_distribution.web.domain_name}"]))
  supported_identity_providers         = ["COGNITO"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_SRP_AUTH"]
  access_token_validity                = 60
  id_token_validity                    = 60
  refresh_token_validity               = 30

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name_prefix}-api-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid       = "ReadCloudWatchAlarms"
    effect    = "Allow"
    actions   = ["cloudwatch:DescribeAlarms"]
    resources = ["*"]
  }

  statement {
    sid       = "DescribeEc2Instances"
    effect    = "Allow"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]
  }

  statement {
    sid       = "WriteAuditEvents"
    effect    = "Allow"
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.audit.arn]
  }

  statement {
    sid       = "ReadUserAuditTimeline"
    effect    = "Allow"
    actions   = ["dynamodb:Query"]
    resources = ["${aws_dynamodb_table.audit.arn}/index/actor-subject-timestamp-index"]
  }

  statement {
    sid    = "ReadUserApprovalStatus"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:Query",
    ]
    resources = [
      aws_dynamodb_table.approvals.arn,
      "${aws_dynamodb_table.approvals.arn}/index/requested-by-updated-at-index",
    ]
  }

  statement {
    sid       = "StartControlledApprovalWorkflow"
    effect    = "Allow"
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.approval.arn]
  }

  statement {
    sid    = "WriteFunctionLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${trimsuffix(aws_cloudwatch_log_group.api.arn, ":*")}:*"]
  }

  dynamic "statement" {
    for_each = var.bedrock_enabled ? [1] : []

    content {
      sid       = "InvokeConfiguredBedrockModel"
      effect    = "Allow"
      actions   = ["bedrock:InvokeModel"]
      resources = [local.bedrock_model_arn]
    }
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.name_prefix}-api-policy"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name_prefix}-api"
  description   = "Safety-first OpsPilot read-only AWS API."
  role          = aws_iam_role.lambda.arn
  runtime       = "python3.13"
  handler       = "lambda_function.lambda_handler"

  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256

  architectures = ["arm64"]
  memory_size   = 256
  timeout       = 15

  environment {
    variables = {
      APPROVAL_STATE_MACHINE_ARN = aws_sfn_state_machine.approval.arn
      APPROVAL_TABLE_NAME        = aws_dynamodb_table.approvals.name
      AUDIT_TABLE_NAME           = aws_dynamodb_table.audit.name
      BEDROCK_ENABLED            = tostring(var.bedrock_enabled)
      BEDROCK_MODEL_ID           = var.bedrock_model_id
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.api,
    aws_iam_role_policy.lambda,
  ]
}

resource "aws_apigatewayv2_api" "api" {
  name          = "${local.name_prefix}-api"
  protocol_type = "HTTP"
  description   = "HTTP API for the OpsPilot development environment."

  cors_configuration {
    allow_headers = ["authorization", "content-type"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_origins = distinct(concat(var.web_allowed_origins, ["https://${aws_cloudfront_distribution.web.domain_name}"]))
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.api.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${local.name_prefix}-jwt"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.web.id]
    issuer   = aws_cognito_user_pool.api.endpoint
  }
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
  timeout_milliseconds   = 15000
}

resource "aws_apigatewayv2_route" "requests" {
  api_id               = aws_apigatewayv2_api.api.id
  route_key            = "POST /requests"
  target               = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type   = "JWT"
  authorizer_id        = aws_apigatewayv2_authorizer.jwt.id
  authorization_scopes = ["${local.cognito_resource_identifier}/read"]
}

resource "aws_apigatewayv2_route" "controlled_requests" {
  api_id               = aws_apigatewayv2_api.api.id
  route_key            = "POST /controlled-requests"
  target               = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type   = "JWT"
  authorizer_id        = aws_apigatewayv2_authorizer.jwt.id
  authorization_scopes = ["${local.cognito_resource_identifier}/apply"]
}

resource "aws_apigatewayv2_route" "timeline" {
  api_id               = aws_apigatewayv2_api.api.id
  route_key            = "GET /timeline"
  target               = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type   = "JWT"
  authorizer_id        = aws_apigatewayv2_authorizer.jwt.id
  authorization_scopes = ["${local.cognito_resource_identifier}/read"]
}

resource "aws_apigatewayv2_route" "approval_status" {
  api_id               = aws_apigatewayv2_api.api.id
  route_key            = "GET /approvals/{request_id}"
  target               = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type   = "JWT"
  authorizer_id        = aws_apigatewayv2_authorizer.jwt.id
  authorization_scopes = ["${local.cognito_resource_identifier}/read"]
}

resource "aws_apigatewayv2_route" "health" {
  api_id             = aws_apigatewayv2_api.api.id
  route_key          = "GET /health"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "NONE"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/POST/requests"
}

resource "aws_lambda_permission" "api_gateway_health" {
  statement_id  = "AllowApiGatewayHealthInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/GET/health"
}

resource "aws_lambda_permission" "api_gateway_controlled_requests" {
  statement_id  = "AllowApiGatewayControlledRequests"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/POST/controlled-requests"
}

resource "aws_lambda_permission" "api_gateway_timeline" {
  statement_id  = "AllowApiGatewayTimeline"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/GET/timeline"
}

resource "aws_lambda_permission" "api_gateway_approval_status" {
  statement_id  = "AllowApiGatewayApprovalStatus"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/GET/approvals/*"
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name_prefix}-api-errors"
  alarm_description   = "OpsPilot API Lambda reported at least one error."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}
