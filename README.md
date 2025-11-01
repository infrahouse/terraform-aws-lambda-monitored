# terraform-aws-lambda-monitored

AWS Lambda function module with built-in monitoring and alerting capabilities.

This module creates a Lambda function with CloudWatch Logs, configurable error monitoring, and SNS-based alerting.
Designed to meet ISO27001 compliance requirements for error rate monitoring.

## Features

- Multi-architecture support (x86_64, arm64) with automatic platform-specific dependency packaging
- Multi-Python version support (3.9, 3.10, 3.11, 3.12, 3.13)
- Intelligent dependency packaging with manylinux wheels for target architecture
- CloudWatch Logs with configurable retention and encryption
- Flexible IAM permissions (attach custom policies)
- S3-based deployment with secure bucket management
- Error monitoring and alerting with SNS email notifications
- Configurable alert strategies (immediate or threshold-based)
- Throttle monitoring and alerts
- Automatic change detection (re-packages only when code or dependencies change)

## Usage

```hcl
module "lambda" {
  source  = "infrahouse/lambda-monitored/aws"
  version = "0.1.0"

  function_name     = "my-lambda-function"
  lambda_source_dir = "${path.module}/lambda"

  # Optional: Python version and architecture
  python_version = "python3.12"
  architecture   = "arm64"

  # Optional: Lambda configuration
  timeout     = 60
  memory_size = 256
  description = "My Lambda function"

  # Optional: Environment variables
  environment_variables = {
    ENV = "production"
  }

  # Optional: Additional IAM permissions
  additional_iam_policy_arns = [
    aws_iam_policy.lambda_custom_permissions.arn
  ]

  # Required: Email addresses for alarm notifications
  alarm_emails = ["team@example.com", "oncall@example.com"]

  # Optional: Alert strategy
  alert_strategy = "immediate"  # or "threshold"

  # Optional: For threshold strategy
  error_rate_threshold           = 5.0  # 5% error rate
  error_rate_evaluation_periods  = 2
  error_rate_datapoints_to_alarm = 2

  # Optional: CloudWatch Logs retention
  cloudwatch_log_retention_days = 365

  tags = {
    Environment = "production"
    Project     = "my-project"
  }
}

# Example: Custom IAM policy
resource "aws_iam_policy" "lambda_custom_permissions" {
  name = "my-lambda-permissions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "arn:aws:s3:::my-bucket/*"
      }
    ]
  })
}
```

## Dependencies and Packaging

The module uses an intelligent packaging system that automatically handles Python dependencies:

**With Dependencies:**
```hcl
module "lambda" {
  source  = "infrahouse/lambda-monitored/aws"
  version = "0.1.0"

  function_name      = "my-function"
  lambda_source_dir  = "${path.module}/lambda"
  requirements_file  = "${path.module}/lambda/requirements.txt"  # Optional
  architecture       = "arm64"  # Dependencies installed for ARM64
  python_version     = "python3.12"
  alarm_emails       = ["team@example.com"]
}
```

**How it works:**
1. The module uses platform-specific manylinux wheels (`manylinux2014_x86_64` or `manylinux2014_aarch64`)
2. Dependencies are installed with `--only-binary=:all:` to ensure AWS Lambda compatibility
3. Only re-packages when source code, dependencies, architecture, or Python version changes
4. Automatically cleans up Python cache files (`__pycache__`, `.pyc`)

**Requirements:**
- Python 3 must be installed locally (used by packaging script)
- The `pip` module must be available
- For cross-architecture builds, ensure pip can download the correct platform wheels

## Notes

### Email Subscription Confirmation

When you specify `alarm_emails`, AWS will send a confirmation email to each address.
Recipients **must click the confirmation link** to receive alerts. The Terraform apply
will complete successfully, but **notifications won't be sent until subscriptions are confirmed**.

**Important:** If you destroy and recreate the module, new confirmation emails will be sent
even to previously confirmed addresses.

### S3 Bucket Security

The module uses the InfraHouse S3 bucket module which automatically configures:
- Server-side encryption
- Versioning
- Public access blocking
- Secure bucket policies

## License

Apache 2.0

## Requirements

| Name | Version |
|------|---------|
| terraform | ~> 1.0 |
| aws | >= 5.31 |

## Providers

| Name | Version |
|------|---------|
| aws | >= 5.31 |
| archive | ~> 2.0 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| function_name | Name of the Lambda function | `string` | n/a | yes |
| lambda_source_dir | Path to the directory containing Lambda function source code | `string` | n/a | yes |
| alarm_emails | List of email addresses for alarm notifications | `list(string)` | n/a | yes |
| python_version | Python runtime version | `string` | `"python3.12"` | no |
| architecture | Instruction set architecture (x86_64 or arm64) | `string` | `"x86_64"` | no |
| requirements_file | Path to requirements.txt for Python dependencies | `string` | `""` | no |
| handler | Lambda function handler | `string` | `"main.lambda_handler"` | no |
| timeout | Lambda function timeout in seconds | `number` | `60` | no |
| memory_size | Lambda function memory size in MB | `number` | `128` | no |
| description | Description of the Lambda function | `string` | `null` | no |
| environment_variables | Map of environment variables | `map(string)` | `{}` | no |
| additional_iam_policy_arns | List of IAM policy ARNs to attach | `list(string)` | `[]` | no |
| cloudwatch_log_retention_days | Number of days to retain CloudWatch logs | `number` | `365` | no |
| alarm_topic_arns | List of existing SNS topic ARNs for alarms | `list(string)` | `[]` | no |
| sns_topic_name | Name for the SNS topic | `string` | `null` | no |
| enable_error_alarms | Enable CloudWatch alarms for Lambda errors | `bool` | `true` | no |
| alert_strategy | Alert strategy: 'immediate' or 'threshold' | `string` | `"immediate"` | no |
| error_rate_threshold | Error rate percentage threshold (0-100) | `number` | `5.0` | no |
| error_rate_evaluation_periods | Number of evaluation periods for error rate alarm | `number` | `2` | no |
| error_rate_datapoints_to_alarm | Number of datapoints that must breach to trigger alarm | `number` | `2` | no |
| enable_throttle_alarms | Enable CloudWatch alarms for Lambda throttling | `bool` | `true` | no |
| tags | Map of tags to assign to resources | `map(string)` | `{}` | no |

## Outputs

| Name | Description |
|------|-------------|
| lambda_function_arn | ARN of the Lambda function |
| lambda_function_name | Name of the Lambda function |
| lambda_function_invoke_arn | Invoke ARN of the Lambda function |
| lambda_role_arn | ARN of the IAM role used by the Lambda function |
| lambda_role_name | Name of the IAM role used by the Lambda function |
| cloudwatch_log_group_name | Name of the CloudWatch Log Group |
| cloudwatch_log_group_arn | ARN of the CloudWatch Log Group |
| s3_bucket_name | Name of the S3 bucket storing Lambda packages |
| s3_bucket_arn | ARN of the S3 bucket storing Lambda packages |
| sns_topic_arn | ARN of the SNS topic for alarm notifications |
| sns_topic_name | Name of the SNS topic for alarm notifications |
| pending_email_confirmations | List of emails pending SNS subscription confirmation |
| error_alarm_arn | ARN of the error CloudWatch alarm (if enabled) |
| throttle_alarm_arn | ARN of the throttle CloudWatch alarm (if enabled) |
