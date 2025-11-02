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
