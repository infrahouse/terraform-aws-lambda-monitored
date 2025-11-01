# terraform-aws-lambda-monitored

AWS Lambda function module with built-in monitoring and alerting capabilities.

This module creates a Lambda function with CloudWatch Logs, configurable error monitoring, and SNS-based alerting.
Designed to meet ISO27001 compliance requirements for error rate monitoring.

## Features

- Multi-architecture support (x86_64, arm64)
- Multi-Python version support (3.9, 3.10, 3.11, 3.12, 3.13)
- CloudWatch Logs with configurable retention and encryption
- Flexible IAM permissions (attach custom policies)
- S3-based deployment with secure bucket management
- Error monitoring and alerting (coming in Phase 2)

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
| python_version | Python runtime version | `string` | `"python3.12"` | no |
| architecture | Instruction set architecture (x86_64 or arm64) | `string` | `"x86_64"` | no |
| handler | Lambda function handler | `string` | `"main.lambda_handler"` | no |
| timeout | Lambda function timeout in seconds | `number` | `60` | no |
| memory_size | Lambda function memory size in MB | `number` | `128` | no |
| description | Description of the Lambda function | `string` | `null` | no |
| environment_variables | Map of environment variables | `map(string)` | `{}` | no |
| additional_iam_policy_arns | List of IAM policy ARNs to attach | `list(string)` | `[]` | no |
| cloudwatch_log_retention_days | Number of days to retain CloudWatch logs | `number` | `365` | no |
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

## Notes

### Email Subscription Confirmation (Phase 2)

When Phase 2 monitoring features are released, if you specify `alarm_emails`, AWS will send a confirmation
email to each address. Recipients must click the confirmation link to receive alerts.
The Terraform apply will complete successfully, but notifications won't be sent until subscriptions are confirmed.

> Note: If you destroy and recreate the module, new confirmation emails will be sent even
> to previously confirmed addresses.

### S3 Bucket Security

The module uses the InfraHouse S3 bucket module which automatically configures:
- Server-side encryption
- Versioning
- Public access blocking
- Secure bucket policies

## License

Apache 2.0
