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

# Holds the log group's deletion until the function's teardown has settled (issue #26).
# It depends on the log group and the function depends on it, so destroy runs
# function -> this wait -> log group. Lambda can still write the function's last log lines a few
# seconds after DeleteFunction returns, and those writes must not find the group gone.
# Only destroy_duration is set, so apply never waits. The provider reads the duration from state,
# so the wait also happens when the module block is removed from the configuration.
resource "time_sleep" "log_group_destroy_delay" {
  destroy_duration = "${var.log_group_destroy_delay_seconds}s"

  depends_on = [aws_cloudwatch_log_group.lambda]
}
