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

# IAM policy document for VPC access (only created when VPC config is specified)
data "aws_iam_policy_document" "lambda_vpc_access" {
  count = var.lambda_subnet_ids != null ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "ec2:CreateNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DeleteNetworkInterface",
      "ec2:AssignPrivateIpAddresses",
      "ec2:UnassignPrivateIpAddresses"
    ]
    resources = ["*"]
  }
}

# IAM policy for VPC access (only created when VPC config is specified)
resource "aws_iam_role_policy" "lambda_vpc_access" {
  count = var.lambda_subnet_ids != null ? 1 : 0

  name = "${var.function_name}-vpc-access"
  role = aws_iam_role.lambda.id

  policy = data.aws_iam_policy_document.lambda_vpc_access[0].json
}

# Attach additional IAM policies to Lambda role
resource "aws_iam_role_policy_attachment" "additional" {
  for_each = toset(var.additional_iam_policy_arns)

  role       = aws_iam_role.lambda.name
  policy_arn = each.value
}
