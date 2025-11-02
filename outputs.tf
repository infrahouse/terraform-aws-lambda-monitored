output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.this.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.this.function_name
}

output "lambda_function_invoke_arn" {
  description = "Invoke ARN of the Lambda function (for use with API Gateway, etc.)"
  value       = aws_lambda_function.this.invoke_arn
}

output "lambda_function_qualified_arn" {
  description = "Qualified ARN of the Lambda function (includes version)"
  value       = aws_lambda_function.this.qualified_arn
}

output "lambda_role_arn" {
  description = "ARN of the IAM role used by the Lambda function"
  value       = aws_iam_role.lambda.arn
}

output "lambda_role_name" {
  description = "Name of the IAM role used by the Lambda function"
  value       = aws_iam_role.lambda.name
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.lambda.name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch Log Group"
  value       = aws_cloudwatch_log_group.lambda.arn
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket storing Lambda packages"
  value       = module.lambda_bucket.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket storing Lambda packages"
  value       = module.lambda_bucket.bucket_arn
}

output "requirements_file_used" {
  description = "Path to the requirements.txt file used for packaging (or 'none' if no dependencies)"
  value       = local.requirements_file
}

# Monitoring outputs

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = aws_sns_topic.alarms.arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic for alarm notifications"
  value       = aws_sns_topic.alarms.name
}

output "pending_email_confirmations" {
  description = "List of email addresses pending SNS subscription confirmation"
  value       = var.alarm_emails
}

output "error_alarm_arn" {
  description = "ARN of the error CloudWatch alarm (if enabled)"
  value = var.enable_error_alarms && var.alert_strategy == "immediate" ? try(
    aws_cloudwatch_metric_alarm.errors_immediate[0].arn, null
    ) : var.enable_error_alarms && var.alert_strategy == "threshold" ? try(
    aws_cloudwatch_metric_alarm.errors_threshold[0].arn, null
  ) : null
}

output "throttle_alarm_arn" {
  description = "ARN of the throttle CloudWatch alarm (if enabled)"
  value = var.enable_throttle_alarms ? try(
    aws_cloudwatch_metric_alarm.throttles[0].arn, null
  ) : null
}

# VPC outputs

output "vpc_config_subnet_ids" {
  description = "List of subnet IDs for Lambda VPC configuration (if configured)"
  value       = var.lambda_subnet_ids
}

output "vpc_config_security_group_ids" {
  description = "List of security group IDs for Lambda VPC configuration (if configured)"
  value       = var.lambda_security_group_ids
}
