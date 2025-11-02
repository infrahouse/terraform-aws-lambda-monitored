# Lambda function
resource "aws_lambda_function" "this" {
  function_name = var.function_name
  description   = var.description != null ? var.description : "Lambda function ${var.function_name}"
  role          = aws_iam_role.lambda.arn
  handler       = var.handler
  runtime       = var.python_version
  architectures = [var.architecture]
  timeout       = var.timeout
  memory_size   = var.memory_size

  s3_bucket = aws_s3_object.lambda_package.bucket
  s3_key    = aws_s3_object.lambda_package.key

  source_code_hash = data.archive_file.lambda_source_hash.output_base64sha256

  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_logging,
    aws_cloudwatch_log_group.lambda
  ]

  tags = merge(
    {
      module_version = local.module_version
    },
    local.tags
  )
}

# Lambda invocation configuration (no retries by default)
resource "aws_lambda_function_event_invoke_config" "this" {
  function_name          = aws_lambda_function.this.function_name
  maximum_retry_attempts = 0
}
