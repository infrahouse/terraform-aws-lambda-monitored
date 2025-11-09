# Data source to get current AWS region
data "aws_region" "current" {}

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
  name_prefix = "${substr(var.function_name, 0, min(length(var.function_name), 37))}-"

  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = merge(
    local.tags,
    {
      function_name = var.function_name
    }
  )
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

  # Statement 1: DescribeNetworkInterfaces requires wildcard (AWS requirement)
  statement {
    sid    = "DescribeNetworkInterfaces"
    effect = "Allow"
    actions = [
      "ec2:DescribeNetworkInterfaces"
    ]
    resources = ["*"]
  }

  # Statement 2: CreateNetworkInterface scoped to specific subnets
  statement {
    sid    = "CreateNetworkInterface"
    effect = "Allow"
    actions = [
      "ec2:CreateNetworkInterface"
    ]
    resources = concat(
      # Allow ENI creation in specified subnets
      [for subnet_id in var.lambda_subnet_ids :
        "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:subnet/${subnet_id}"
      ],
      # Allow ENI creation in security groups
      [for sg_id in var.lambda_security_group_ids :
        "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:security-group/${sg_id}"
      ],
      # Allow creation of the network interface resource itself
      ["arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:network-interface/*"]
    )
  }

  # Statement 3: Delete network interfaces
  # Lambda validates this permission at function creation time (before any ENIs exist),
  # and checks it against arn:aws:ec2:region:account:*/* pattern. We cannot use:
  # - network-interface/* (too specific, validation fails)
  # - subnet conditions (no ENIs exist yet at validation time)
  # This is still much better than resources = ["*"] because it's scoped to:
  # - Specific AWS account (not cross-account)
  # - Specific region (not global)
  # - EC2 service only (not all AWS services)
  statement {
    sid    = "DeleteNetworkInterface"
    effect = "Allow"
    actions = [
      "ec2:DeleteNetworkInterface"
    ]
    resources = [
      "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*/*"
    ]
  }

  # Statement 4: Manage IP addresses on network interfaces
  statement {
    sid    = "ManageNetworkInterfaceIPs"
    effect = "Allow"
    actions = [
      "ec2:AssignPrivateIpAddresses",
      "ec2:UnassignPrivateIpAddresses"
    ]
    resources = [
      "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:network-interface/*"
    ]

    # Only allow operations on ENIs in specified subnets
    condition {
      test     = "StringEquals"
      variable = "ec2:Subnet"
      values = [for subnet_id in var.lambda_subnet_ids :
        "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:subnet/${subnet_id}"
      ]
    }
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
