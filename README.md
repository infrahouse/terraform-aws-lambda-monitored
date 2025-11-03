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

## Prerequisites

The module's packaging script requires the following tools to be installed on the system where Terraform runs:

- **Python 3** - For installing dependencies
  - Ubuntu/Debian: `sudo apt-get install python3 python3-pip`
  - macOS: `brew install python3`
  - Amazon Linux: `sudo yum install python3 python3-pip`
  - Windows: [Download from python.org](https://www.python.org/downloads/)

- **pip3** - For managing Python packages
  - Ubuntu/Debian: `sudo apt-get install python3-pip`
  - macOS: `python3 -m ensurepip`
  - Amazon Linux: `sudo yum install python3-pip`
  - Windows: `python -m ensurepip`

- **jq** - For parsing JSON responses
  - Ubuntu/Debian: `sudo apt-get install jq`
  - macOS: `brew install jq`
  - Amazon Linux: `sudo yum install jq`
  - Windows: [Download from stedolan.github.io/jq](https://stedolan.github.io/jq/download/)

The packaging and deployment scripts will check for these dependencies and provide installation instructions if any are missing.

## Usage

```hcl
module "lambda" {
  source  = "infrahouse/lambda-monitored/aws"
  version = "0.3.0"

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
  version = "0.3.0"

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

## VPC Configuration

Lambda functions can be attached to a VPC to access resources in private subnets (databases, internal APIs, etc.).

**With VPC Configuration:**
```hcl
module "lambda" {
  source  = "infrahouse/lambda-monitored/aws"
  version = "0.3.0"

  function_name     = "my-vpc-function"
  lambda_source_dir = "${path.module}/lambda"
  alarm_emails      = ["team@example.com"]

  # VPC configuration
  lambda_subnet_ids         = ["subnet-abc123", "subnet-def456"]
  lambda_security_group_ids = [aws_security_group.lambda.id]
}
```

**Important VPC Considerations:**

1. **NAT Gateway Required**: Subnets must have a NAT gateway or NAT instance for internet access (AWS API calls, external dependencies, etc.)

2. **Security Groups**: Configure security group rules to allow:
   - Outbound traffic to required services (databases, APIs, etc.)
   - Inbound traffic if Lambda needs to receive requests from within VPC

3. **IAM Permissions**: The module automatically adds required EC2 network interface permissions:
   - `ec2:CreateNetworkInterface`
   - `ec2:DescribeNetworkInterfaces`
   - `ec2:DeleteNetworkInterface`
   - `ec2:AssignPrivateIpAddresses`
   - `ec2:UnassignPrivateIpAddresses`

4. **Cold Start**: VPC-attached Lambda functions have longer cold start times (~1-3 seconds additional) due to ENI creation

5. **ENI Limits**: Each Lambda function in a VPC creates elastic network interfaces (ENIs). Monitor your ENI limits in the AWS account

**When to Use VPC:**
- ✅ Access RDS databases in private subnets
- ✅ Connect to internal APIs or services
- ✅ Use AWS PrivateLink endpoints
- ✅ Access resources that require private IP addresses

**When NOT to Use VPC:**
- ❌ Public API calls only (no VPC needed, better performance)
- ❌ Pure compute functions with no external connections
- ❌ Functions requiring minimal cold start latency

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

## Development and Testing

This module includes a comprehensive test suite using pytest. The Makefile provides convenient targets for running tests.

### Running Tests

The module provides several test targets:

```bash
# Run all tests
make test

# Run specific test suites
make test-simple          # Test simple Lambda deployment
make test-deps            # Test Lambda with dependencies
make test-monitoring      # Test error monitoring (keeps resources)
make test-sns             # Test SNS integration

# Run architecture-specific tests
make test-x86             # Test x86_64 architecture only
make test-arm             # Test arm64 architecture only
```

### Filtering Tests

You can filter tests using the `TEST_SELECTOR` variable:

```bash
# Run specific test
make test-simple TEST_SELECTOR="test_lambda_deployment"

# Run tests for specific provider version
make test-simple TEST_SELECTOR="provider-6.x"

# Run tests for specific Python version
make test-deps TEST_SELECTOR="py3.13"

# Combine filters (AND logic)
make test-simple TEST_SELECTOR="provider-6.x and py3.12"
```

### Customizing Test Configuration

Override test configuration variables:

```bash
# Use different AWS region
make test-simple TEST_REGION="us-east-1"

# Use different IAM role
make test-simple TEST_ROLE="arn:aws:iam::123456789:role/my-test-role"

# Keep resources after test (for inspection/debugging)
make test-simple KEEP_AFTER=1

# Don't keep resources (destroy after test)
make test-monitoring KEEP_AFTER=

# Combine multiple overrides
make test-simple \
  TEST_SELECTOR="test_lambda_deployment" \
  TEST_REGION="eu-west-1" \
  TEST_ROLE="arn:aws:iam::123456789:role/my-role" \
  KEEP_AFTER=1
```

### Default Test Configuration

The following defaults are used when variables are not specified:

- `TEST_REGION`: `us-west-2`
- `TEST_ROLE`: `arn:aws:iam::303467602807:role/lambda-monitored-tester`
- `TEST_SELECTOR`: `test_` (runs all tests)
- `KEEP_AFTER`: empty (destroys resources after test)

**Note:** The `test-monitoring` target keeps resources by default for alarm observation.

### Other Make Targets

```bash
make bootstrap            # Install development dependencies
make lint                 # Check code style
make format              # Format Terraform and Python files
make clean               # Clean temporary files and test data
```

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
