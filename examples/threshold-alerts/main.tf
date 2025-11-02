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
      Project     = "lambda-monitored-threshold-alerts"
      ManagedBy   = "terraform"
    }
  }
}

# Use the lambda-monitored module with threshold alert strategy
module "data_ingestion" {
  source = "../../" # Use published version: source = "infrahouse/lambda-monitored/aws"

  function_name     = "data-ingestion-threshold"
  lambda_source_dir = "${path.module}/lambda"

  # Lambda configuration
  python_version = "python3.12"
  architecture   = "x86_64"
  timeout        = 30
  memory_size    = 512
  description    = "Data ingestion Lambda with threshold-based error alerts"

  # Environment variables
  environment_variables = {
    ENVIRONMENT = "production"
    LOG_LEVEL   = "INFO"
  }

  # Threshold alert strategy - only alert when error rate exceeds threshold
  alert_strategy = "threshold"

  # Alert when error rate exceeds 5% over 2 consecutive periods
  error_rate_threshold           = 5.0 # 5% error rate
  error_rate_evaluation_periods  = 2   # Number of periods to evaluate
  error_rate_datapoints_to_alarm = 2   # Must breach in both periods

  # Email addresses for alerts
  alarm_emails = var.alarm_emails

  # CloudWatch Logs retention
  cloudwatch_log_retention_days = 90

  # Enable throttle monitoring
  enable_throttle_alarms = true

  tags = {
    CriticalityLevel = "medium"
    Team             = "data-engineering"
    DataSource       = "external-apis"
  }
}