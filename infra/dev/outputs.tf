output "api_url" {
  description = "Base URL for the OpsPilot development HTTP API."
  value       = trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")
}

output "requests_url" {
  description = "POST endpoint for OpsPilot requests."
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/requests"
}

output "health_url" {
  description = "Public health endpoint for the OpsPilot development API."
  value       = "${trimsuffix(aws_apigatewayv2_stage.default.invoke_url, "/")}/health"
}

output "audit_table_name" {
  description = "DynamoDB table containing OpsPilot application audit events."
  value       = aws_dynamodb_table.audit.name
}

output "lambda_function_name" {
  description = "Name of the OpsPilot API Lambda function."
  value       = aws_lambda_function.api.function_name
}

output "lambda_error_alarm_name" {
  description = "Name of the CloudWatch alarm that monitors Lambda errors."
  value       = aws_cloudwatch_metric_alarm.lambda_errors.alarm_name
}

output "bedrock_enabled" {
  description = "Whether Bedrock tool selection is enabled for the development API."
  value       = var.bedrock_enabled
}

output "bedrock_model_id" {
  description = "Configured Bedrock foundation model ID."
  value       = var.bedrock_model_id
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID used by the OpsPilot development API."
  value       = aws_cognito_user_pool.api.id
}

output "cognito_app_client_id" {
  description = "Public Cognito app client ID."
  value       = aws_cognito_user_pool_client.web.id
}

output "cognito_issuer" {
  description = "JWT issuer URL configured on the API Gateway authorizer."
  value       = aws_cognito_user_pool.api.endpoint
}

output "cognito_scopes" {
  description = "Custom OAuth scopes exposed by the OpsPilot resource server."
  value       = aws_cognito_resource_server.api.scope_identifiers
}
