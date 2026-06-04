output "api_url" {
  description = "Base URL for the OpsPilot development HTTP API."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "requests_url" {
  description = "POST endpoint for OpsPilot requests."
  value       = "${aws_apigatewayv2_stage.default.invoke_url}/requests"
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

