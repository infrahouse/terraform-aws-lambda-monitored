# CloudWatch Log Group for Lambda function
# Encrypted at rest using AWS managed encryption keys
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = local.tags
}
