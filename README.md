# terraform-aws-lambda-monitored

[![InfraHouse](https://img.shields.io/badge/InfraHouse-Terraform_Module-blue?logo=terraform)](https://registry.terraform.io/modules/infrahouse/lambda-monitored/aws/latest)
[![License](https://img.shields.io/github/license/infrahouse/terraform-aws-lambda-monitored)](LICENSE)
[![CI](https://github.com/infrahouse/terraform-aws-lambda-monitored/actions/workflows/terraform-CI.yml/badge.svg)](https://github.com/infrahouse/terraform-aws-lambda-monitored/actions/workflows/terraform-CI.yml)
[![AWS Lambda](https://img.shields.io/badge/AWS-Lambda-orange?logo=awslambda)](https://aws.amazon.com/lambda/)

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
  version = "1.0.2"

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
  version = "1.0.2"

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

**Tracking Source Code Changes:**

The module tracks changes to your source code to determine when to rebuild. By default, it only tracks `main.py` to avoid hashing installed dependencies. You can customize this with the `source_code_files` variable:

```hcl
# Default - tracks only main.py
module "lambda" {
  source            = "infrahouse/lambda-monitored/aws"
  lambda_source_dir = "${path.module}/lambda"
  # source_code_files defaults to ["main.py"]
  ...
}

# Track multiple specific files
module "lambda" {
  source            = "infrahouse/lambda-monitored/aws"
  lambda_source_dir = "${path.module}/lambda"
  source_code_files = ["main.py", "utils.py", "config.py"]
  ...
}

# Track all root-level .py files (useful if you have multiple source files)
module "lambda" {
  source            = "infrahouse/lambda-monitored/aws"
  lambda_source_dir = "${path.module}/lambda"
  source_code_files = ["*.py"]
  ...
}
```

**Important:** Dependencies are tracked separately via `requirements_file` hash. Only list your actual source code files in `source_code_files`, not installed packages. This prevents unnecessary rebuilds when `.terraform` is recreated.

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
  version = "1.0.2"

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

### IAM Role Naming

If your `function_name` exceeds 37 characters, the IAM role name will be truncated to comply with AWS's 38-character `name_prefix` limit. The full function name is always preserved in the IAM role's `function_name` tag for identification purposes.

**Best Practice:** Reference the IAM role using the module outputs (`lambda_role_arn` or `lambda_role_name`) rather than constructing the role name manually.

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

---

<!-- BEGIN_TF_DOCS -->

## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | ~> 1.0 |
| <a name="requirement_archive"></a> [archive](#requirement\_archive) | ~> 2.0 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | >= 5.31, < 7.0 |
| <a name="requirement_null"></a> [null](#requirement\_null) | ~> 3.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_archive"></a> [archive](#provider\_archive) | ~> 2.0 |
| <a name="provider_aws"></a> [aws](#provider\_aws) | >= 5.31, < 7.0 |
| <a name="provider_null"></a> [null](#provider\_null) | ~> 3.0 |

## Modules

| Name | Source | Version |
|------|--------|---------|
| <a name="module_lambda_bucket"></a> [lambda\_bucket](#module\_lambda\_bucket) | registry.infrahouse.com/infrahouse/s3-bucket/aws | 0.2.0 |

## Resources

| Name | Type |
|------|------|
| [aws_cloudwatch_log_group.lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_log_group) | resource |
| [aws_cloudwatch_metric_alarm.duration](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_cloudwatch_metric_alarm.errors_immediate](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_cloudwatch_metric_alarm.errors_threshold](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_cloudwatch_metric_alarm.throttles](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm) | resource |
| [aws_iam_role.lambda](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role) | resource |
| [aws_iam_role_policy.lambda_logging](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy.lambda_vpc_access](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy) | resource |
| [aws_iam_role_policy_attachment.additional](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/iam_role_policy_attachment) | resource |
| [aws_lambda_function.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function) | resource |
| [aws_lambda_function_event_invoke_config.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_function_event_invoke_config) | resource |
| [aws_s3_object.lambda_package](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_object) | resource |
| [aws_sns_topic.alarms](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic) | resource |
| [aws_sns_topic_subscription.alarm_emails](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/sns_topic_subscription) | resource |
| [null_resource.install_python_dependencies](https://registry.terraform.io/providers/hashicorp/null/latest/docs/resources/resource) | resource |
| [archive_file.lambda_source_hash](https://registry.terraform.io/providers/hashicorp/archive/latest/docs/data-sources/file) | data source |
| [aws_caller_identity.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/caller_identity) | data source |
| [aws_iam_policy_document.lambda_assume_role](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.lambda_logging](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_iam_policy_document.lambda_vpc_access](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/iam_policy_document) | data source |
| [aws_region.current](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/region) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_additional_iam_policy_arns"></a> [additional\_iam\_policy\_arns](#input\_additional\_iam\_policy\_arns) | List of IAM policy ARNs to attach to the Lambda execution role | `list(string)` | `[]` | no |
| <a name="input_alarm_emails"></a> [alarm\_emails](#input\_alarm\_emails) | List of email addresses to receive alarm notifications. AWS will send confirmation emails that must be accepted. At least one email is required. | `list(string)` | n/a | yes |
| <a name="input_alarm_topic_arns"></a> [alarm\_topic\_arns](#input\_alarm\_topic\_arns) | List of existing SNS topic ARNs to send alarms to (for advanced integrations like PagerDuty, Slack, etc.) | `list(string)` | `[]` | no |
| <a name="input_alert_strategy"></a> [alert\_strategy](#input\_alert\_strategy) | Alert strategy: 'immediate' (alert on any error) or 'threshold' (alert when error rate exceeds threshold) | `string` | `"immediate"` | no |
| <a name="input_architecture"></a> [architecture](#input\_architecture) | Instruction set architecture for the Lambda function. Valid values: x86\_64 or arm64 | `string` | `"x86_64"` | no |
| <a name="input_cloudwatch_log_retention_days"></a> [cloudwatch\_log\_retention\_days](#input\_cloudwatch\_log\_retention\_days) | Number of days to retain CloudWatch logs | `number` | `365` | no |
| <a name="input_description"></a> [description](#input\_description) | Description of the Lambda function | `string` | `null` | no |
| <a name="input_duration_threshold_percent"></a> [duration\_threshold\_percent](#input\_duration\_threshold\_percent) | Percentage of function timeout that triggers duration alarm (1-100). If not specified, duration alarm is disabled. For example, 80 means alarm when execution duration exceeds 80% of the configured timeout. | `number` | `null` | no |
| <a name="input_enable_error_alarms"></a> [enable\_error\_alarms](#input\_enable\_error\_alarms) | Enable CloudWatch alarms for Lambda errors | `bool` | `true` | no |
| <a name="input_enable_throttle_alarms"></a> [enable\_throttle\_alarms](#input\_enable\_throttle\_alarms) | Enable CloudWatch alarms for Lambda throttling | `bool` | `true` | no |
| <a name="input_environment_variables"></a> [environment\_variables](#input\_environment\_variables) | Map of environment variables for the Lambda function | `map(string)` | `{}` | no |
| <a name="input_error_rate_datapoints_to_alarm"></a> [error\_rate\_datapoints\_to\_alarm](#input\_error\_rate\_datapoints\_to\_alarm) | Number of datapoints that must breach threshold to trigger alarm | `number` | `2` | no |
| <a name="input_error_rate_evaluation_periods"></a> [error\_rate\_evaluation\_periods](#input\_error\_rate\_evaluation\_periods) | Number of evaluation periods for error rate alarm | `number` | `2` | no |
| <a name="input_error_rate_threshold"></a> [error\_rate\_threshold](#input\_error\_rate\_threshold) | Error rate percentage threshold for 'threshold' alert strategy (0-100) | `number` | `5` | no |
| <a name="input_function_name"></a> [function\_name](#input\_function\_name) | Name of the Lambda function | `string` | n/a | yes |
| <a name="input_handler"></a> [handler](#input\_handler) | Lambda function handler (format: file.function\_name) | `string` | `"main.lambda_handler"` | no |
| <a name="input_kms_key_id"></a> [kms\_key\_id](#input\_kms\_key\_id) | ARN of the KMS key for encrypting CloudWatch Logs and SNS topic.<br/>If not specified, AWS-managed encryption keys are used.<br/>The key must allow the CloudWatch Logs and SNS services to use it. | `string` | `null` | no |
| <a name="input_lambda_security_group_ids"></a> [lambda\_security\_group\_ids](#input\_lambda\_security\_group\_ids) | List of security group IDs for Lambda VPC configuration. Required if lambda\_subnet\_ids is specified. | `list(string)` | `null` | no |
| <a name="input_lambda_source_dir"></a> [lambda\_source\_dir](#input\_lambda\_source\_dir) | Path to the directory containing Lambda function source code | `string` | n/a | yes |
| <a name="input_lambda_subnet_ids"></a> [lambda\_subnet\_ids](#input\_lambda\_subnet\_ids) | List of subnet IDs for Lambda VPC configuration. The subnets must have NAT gateway for internet access. If not specified, Lambda will not be attached to a VPC. | `list(string)` | `null` | no |
| <a name="input_memory_size"></a> [memory\_size](#input\_memory\_size) | Lambda function memory size in MB | `number` | `128` | no |
| <a name="input_python_version"></a> [python\_version](#input\_python\_version) | Python runtime version. Must be one of https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html | `string` | `"python3.12"` | no |
| <a name="input_requirements_file"></a> [requirements\_file](#input\_requirements\_file) | Path to requirements.txt file for Python dependencies.<br/>Dependencies will be installed with platform-specific wheels for the target architecture.<br/>If not specified, the module will automatically look for requirements.txt in var.lambda\_source\_dir.<br/>Set to null to explicitly skip dependency installation. | `string` | `null` | no |
| <a name="input_sns_topic_name"></a> [sns\_topic\_name](#input\_sns\_topic\_name) | Name for the SNS topic. If not provided, defaults to '<function\_name>-alarms' | `string` | `null` | no |
| <a name="input_source_code_files"></a> [source\_code\_files](#input\_source\_code\_files) | List of source code file patterns to track for changes (relative to lambda\_source\_dir).<br/>Only these files will trigger repackaging. Installed dependencies are tracked separately via requirements\_file.<br/>Use glob patterns like "*.py" for root-level files or specific files like "main.py", "utils.py".<br/>Default tracks only main.py to avoid hashing installed dependencies. | `list(string)` | <pre>[<br/>  "main.py"<br/>]</pre> | no |
| <a name="input_tags"></a> [tags](#input\_tags) | Map of tags to assign to resources | `map(string)` | `{}` | no |
| <a name="input_timeout"></a> [timeout](#input\_timeout) | Lambda function timeout in seconds | `number` | `60` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_cloudwatch_log_group_arn"></a> [cloudwatch\_log\_group\_arn](#output\_cloudwatch\_log\_group\_arn) | ARN of the CloudWatch Log Group |
| <a name="output_cloudwatch_log_group_name"></a> [cloudwatch\_log\_group\_name](#output\_cloudwatch\_log\_group\_name) | Name of the CloudWatch Log Group |
| <a name="output_duration_alarm_arn"></a> [duration\_alarm\_arn](#output\_duration\_alarm\_arn) | ARN of the duration CloudWatch alarm (if enabled) |
| <a name="output_error_alarm_arn"></a> [error\_alarm\_arn](#output\_error\_alarm\_arn) | ARN of the error CloudWatch alarm (if enabled) |
| <a name="output_kms_key_id"></a> [kms\_key\_id](#output\_kms\_key\_id) | ARN of the KMS key used for encrypting CloudWatch Logs and SNS topic (null if using AWS-managed encryption) |
| <a name="output_lambda_function_arn"></a> [lambda\_function\_arn](#output\_lambda\_function\_arn) | ARN of the Lambda function |
| <a name="output_lambda_function_invoke_arn"></a> [lambda\_function\_invoke\_arn](#output\_lambda\_function\_invoke\_arn) | Invoke ARN of the Lambda function (for use with API Gateway, etc.) |
| <a name="output_lambda_function_name"></a> [lambda\_function\_name](#output\_lambda\_function\_name) | Name of the Lambda function |
| <a name="output_lambda_function_qualified_arn"></a> [lambda\_function\_qualified\_arn](#output\_lambda\_function\_qualified\_arn) | Qualified ARN of the Lambda function (includes version) |
| <a name="output_lambda_role_arn"></a> [lambda\_role\_arn](#output\_lambda\_role\_arn) | ARN of the IAM role used by the Lambda function |
| <a name="output_lambda_role_name"></a> [lambda\_role\_name](#output\_lambda\_role\_name) | Name of the IAM role used by the Lambda function |
| <a name="output_pending_email_confirmations"></a> [pending\_email\_confirmations](#output\_pending\_email\_confirmations) | List of email addresses pending SNS subscription confirmation |
| <a name="output_requirements_file_used"></a> [requirements\_file\_used](#output\_requirements\_file\_used) | Path to the requirements.txt file used for packaging (or 'none' if no dependencies) |
| <a name="output_s3_bucket_arn"></a> [s3\_bucket\_arn](#output\_s3\_bucket\_arn) | ARN of the S3 bucket storing Lambda packages |
| <a name="output_s3_bucket_name"></a> [s3\_bucket\_name](#output\_s3\_bucket\_name) | Name of the S3 bucket storing Lambda packages |
| <a name="output_sns_topic_arn"></a> [sns\_topic\_arn](#output\_sns\_topic\_arn) | ARN of the SNS topic for alarm notifications |
| <a name="output_sns_topic_name"></a> [sns\_topic\_name](#output\_sns\_topic\_name) | Name of the SNS topic for alarm notifications |
| <a name="output_throttle_alarm_arn"></a> [throttle\_alarm\_arn](#output\_throttle\_alarm\_arn) | ARN of the throttle CloudWatch alarm (if enabled) |
| <a name="output_vpc_config_security_group_ids"></a> [vpc\_config\_security\_group\_ids](#output\_vpc\_config\_security\_group\_ids) | List of security group IDs for Lambda VPC configuration (if configured) |
| <a name="output_vpc_config_subnet_ids"></a> [vpc\_config\_subnet\_ids](#output\_vpc\_config\_subnet\_ids) | List of subnet IDs for Lambda VPC configuration (if configured) |
<!-- END_TF_DOCS -->
