# IAM policy document for Lambda assume role
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# IAM role for Lambda execution
resource "aws_iam_role" "lambda" {
  name_prefix = "${var.function_name}-role-"

  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = local.tags
}

# IAM policy document for CloudWatch Logs
data "aws_iam_policy_document" "lambda_logging" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["${aws_cloudwatch_log_group.lambda.arn}:*"]
  }
}

# IAM policy for CloudWatch Logs
resource "aws_iam_role_policy" "lambda_logging" {
  name = "${var.function_name}-logging"
  role = aws_iam_role.lambda.id

  policy = data.aws_iam_policy_document.lambda_logging.json
}

# Attach additional IAM policies to Lambda role
resource "aws_iam_role_policy_attachment" "additional" {
  for_each = toset(var.additional_iam_policy_arns)

  role       = aws_iam_role.lambda.name
  policy_arn = each.value
}

# S3 bucket for Lambda deployment packages
module "lambda_bucket" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.2.0"

  bucket_prefix = "${var.function_name}-lambda-packages"
  tags          = local.tags
}

# Generate hash of source directory for change detection
data "archive_file" "lambda_source_hash" {
  type        = "zip"
  source_dir  = var.lambda_source_dir
  output_path = "${path.module}/.build/${var.function_name}-source-hash.zip"
  excludes    = ["__pycache__", "*.pyc", "*.pyo"]
}

# Package Lambda function with dependencies using custom script
resource "null_resource" "lambda_package" {
  triggers = {
    source_hash       = data.archive_file.lambda_source_hash.output_base64sha256
    requirements_hash = local.requirements_file != "none" ? filemd5(local.requirements_file) : ""
    architecture      = var.architecture
    python_version    = var.python_version
  }

  provisioner "local-exec" {
    command = join(
      " ",
      [
        "${path.module}/scripts/package.sh",
        "'${var.lambda_source_dir}'",
        "'${local.requirements_file}'",
        "'${path.module}/.build/${var.function_name}.zip'",
        "'${var.architecture}'",
        "'${var.python_version}'"
      ]
    )
  }
}

# Upload Lambda package to S3
resource "aws_s3_object" "lambda_package" {
  bucket = module.lambda_bucket.bucket_name
  key    = "${var.function_name}/${data.archive_file.lambda_source_hash.output_md5}.zip"
  source = "${path.module}/.build/${var.function_name}.zip"
  etag   = filemd5("${path.module}/.build/${var.function_name}.zip")

  depends_on = [null_resource.lambda_package]

  tags = local.tags
}

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
