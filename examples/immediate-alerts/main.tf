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
      Project     = "lambda-monitored-immediate-alerts"
      ManagedBy   = "terraform"
    }
  }
}

# Use the lambda-monitored module with immediate alert strategy
module "order_processor" {
  source = "../../"  # Use published version: source = "infrahouse/lambda-monitored/aws"

  function_name     = "order-processor-immediate"
  lambda_source_dir = "${path.module}/lambda"

  # Lambda configuration
  python_version = "python3.12"
  architecture   = "arm64"  # Use ARM64 for cost optimization
  timeout        = 30
  memory_size    = 256
  description    = "Critical order processor with immediate error alerts"

  # Environment variables
  environment_variables = {
    ENVIRONMENT = "production"
    LOG_LEVEL   = "INFO"
  }

  # Immediate alert strategy - trigger alarm on ANY error
  alert_strategy = "immediate"

  # Email addresses for critical alerts
  alarm_emails = var.alarm_emails

  # Optional: Send alerts to additional SNS topics (e.g., PagerDuty, Slack)
  # alarm_topic_arns = [aws_sns_topic.pagerduty.arn]

  # CloudWatch Logs retention
  cloudwatch_log_retention_days = 30

  tags = {
    CriticalityLevel = "high"
    Team             = "payments"
  }
}