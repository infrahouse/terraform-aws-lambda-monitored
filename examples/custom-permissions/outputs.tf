output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = module.file_processor.lambda_function_arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = module.file_processor.lambda_function_name
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = module.file_processor.lambda_role_arn
}

output "lambda_role_name" {
  description = "Name of the Lambda execution role"
  value       = module.file_processor.lambda_role_name
}

output "s3_bucket_name" {
  description = "Name of the S3 uploads bucket"
  value       = aws_s3_bucket.uploads.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 uploads bucket"
  value       = aws_s3_bucket.uploads.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB metadata table"
  value       = aws_dynamodb_table.file_metadata.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB metadata table"
  value       = aws_dynamodb_table.file_metadata.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch Log Group name"
  value       = module.file_processor.cloudwatch_log_group_name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications"
  value       = module.file_processor.sns_topic_arn
}

output "error_alarm_arn" {
  description = "CloudWatch alarm ARN for Lambda errors"
  value       = module.file_processor.error_alarm_arn
}

output "s3_access_policy_arn" {
  description = "ARN of the S3 access IAM policy"
  value       = aws_iam_policy.lambda_s3_access.arn
}

output "dynamodb_access_policy_arn" {
  description = "ARN of the DynamoDB access IAM policy"
  value       = aws_iam_policy.lambda_dynamodb_access.arn
}