# CloudWatch Log Group for Lambda function
# Encrypted at rest:
# - With customer-managed KMS key if var.kms_key_id is provided
# - With AWS-managed encryption keys if var.kms_key_id is null (default)
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.cloudwatch_log_retention_days
  kms_key_id        = var.kms_key_id

  tags = local.tags
}
