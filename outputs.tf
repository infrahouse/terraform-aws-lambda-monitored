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