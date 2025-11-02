terraform {
  required_version = "~> 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.31"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "example"
      Project     = "lambda-monitored-custom-permissions"
      ManagedBy   = "terraform"
    }
  }
}

# DynamoDB table for file metadata
resource "aws_dynamodb_table" "file_metadata" {
  name         = "file-metadata-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "file_id"

  attribute {
    name = "file_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = false
  }

  tags = {
    Name        = "file-metadata-${var.environment}"
    Environment = var.environment
  }
}

# S3 bucket for file storage
resource "aws_s3_bucket" "uploads" {
  bucket_prefix = "lambda-uploads-${var.environment}-"

  tags = {
    Name        = "lambda-uploads-${var.environment}"
    Environment = var.environment
  }
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# IAM policy for S3 access
resource "aws_iam_policy" "lambda_s3_access" {
  name_prefix = "lambda-s3-access-"
  description = "Allow Lambda to read from S3 uploads bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:HeadObject"
        ]
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.uploads.arn
      }
    ]
  })

  tags = {
    Environment = var.environment
  }
}

# IAM policy for DynamoDB access
resource "aws_iam_policy" "lambda_dynamodb_access" {
  name_prefix = "lambda-dynamodb-access-"
  description = "Allow Lambda to write to DynamoDB file metadata table"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.file_metadata.arn
      }
    ]
  })

  tags = {
    Environment = var.environment
  }
}

# Use the lambda-monitored module with custom IAM permissions
module "file_processor" {
  source = "../../"  # Use published version: source = "infrahouse/lambda-monitored/aws"

  function_name     = "file-processor-${var.environment}"
  lambda_source_dir = "${path.module}/lambda"
  requirements_file = "${path.module}/lambda/requirements.txt"

  # Lambda configuration
  python_version = "python3.12"
  architecture   = "arm64"
  timeout        = 30
  memory_size    = 256
  description    = "File processor Lambda with S3 and DynamoDB permissions"

  # Environment variables
  environment_variables = {
    ENVIRONMENT = var.environment
    LOG_LEVEL   = "INFO"
    TABLE_NAME  = aws_dynamodb_table.file_metadata.name
    BUCKET_NAME = aws_s3_bucket.uploads.id
  }

  # Attach custom IAM policies for S3 and DynamoDB access
  additional_iam_policy_arns = [
    aws_iam_policy.lambda_s3_access.arn,
    aws_iam_policy.lambda_dynamodb_access.arn
  ]

  # Alert strategy
  alert_strategy = var.alert_strategy

  # Email addresses for alerts
  alarm_emails = var.alarm_emails

  # CloudWatch Logs retention
  cloudwatch_log_retention_days = 30

  tags = {
    Environment = var.environment
    Team        = "backend"
    DataAccess  = "s3-dynamodb"
  }
}