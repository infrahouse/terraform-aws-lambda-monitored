output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.order_processor.lambda_function_arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.order_processor.lambda_function_name
}

output "lambda_invoke_arn" {
  description = "Invoke ARN for use with API Gateway"
  value       = module.order_processor.lambda_function_invoke_arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group name"
  value       = module.order_processor.cloudwatch_log_group_name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications"
  value       = module.order_processor.sns_topic_arn
}

output "error_alarm_arn" {
  description = "CloudWatch alarm ARN for Lambda errors"
  value       = module.order_processor.error_alarm_arn
}

output "pending_email_confirmations" {
  description = "Emails that need to confirm SNS subscription"
  value       = module.order_processor.pending_email_confirmations
}