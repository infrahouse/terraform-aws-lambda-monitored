
# Development Plan for terraform-aws-lambda-monitored

**Legend**: ✅ Completed | 🔄 In Progress | ⏳ Pending

## Progress Summary

**Overall Status**: Core module fully tested and ready for production use

- ✅ **Phase 1: Core Module Structure** - COMPLETED
- ✅ **Phase 2: Monitoring & Alerting** - COMPLETED
- ✅ **Phase 3: Advanced Packaging & Build** - COMPLETED
- ✅ **Phase 4: IAM & Permissions** - COMPLETED (with modification)
- ✅ **Phase 5: Testing Infrastructure** - COMPLETED
- ✅ **Phase 6: Documentation & Examples** - COMPLETED
- ⏳ **Phase 7: Advanced Features** - PENDING (optional)

**Key Implementation Notes**:
- Module supports Python 3.9-3.13, x86_64/arm64 architectures
- Multi-architecture packaging with manylinux wheels
- ISO27001-compliant error monitoring (immediate and threshold strategies)
- Simplified IAM model (removed inline_policy per user decision)
- Email alerts required (minimum 1 email for compliance)
- VPC support with automatic ENI permissions
- Comprehensive README with usage examples

---

## Phase 1: Core Module Structure ✅

  Status: **COMPLETED**

  Goal: Create a reusable, configurable lambda module

  Tasks:
  1. Module inputs (variables.tf):
    - python_version (support 3.9, 3.10, 3.11, 3.12, 3.13)
    - architecture (x86_64 or arm64)
    - function_name
    - handler (default: "main.lambda_handler")
    - timeout (default: 60)
    - memory_size (default: 128)
    - environment_variables (map)
    - lambda_source_dir (path to user's lambda code)
    - requirements_file (path to requirements.txt)
    - s3_bucket (for deployment package)
    - cloudwatch_log_retention_days (default: 365)
    - tags
  2. Core lambda resources (lambda.tf):
    - aws_lambda_function with configurable runtime & architecture
    - aws_iam_role for lambda execution
    - aws_iam_role_policy_attachment for basic execution
    - aws_lambda_function_event_invoke_config (no retries by default)
    - S3 object for deployment package
  3. CloudWatch logs (cloudwatch.tf):
    - Log group with configurable retention
    - Proper naming convention: /aws/lambda/${function_name}

## Phase 2: Monitoring & Alerting (ISO27001 Compliance) ✅

  Status: **COMPLETED**

  Goal: Implement flexible error monitoring strategies

  Implementation Notes:
  - `alarm_emails` is required (minimum 1 email) per user request for ISO27001 compliance
  - SNS topic always created (no conditional creation)
  - Supports both immediate and threshold alert strategies
  - Includes throttle monitoring

  Tasks:
4. SNS configuration variables:
```hcl
   variable "alarm_emails" {
    description = "List of email addresses to receive alarm notifications"
    type        = list(string)
    default     = []
   }

    variable "alarm_topic_arns" { 
      
      description = "List of existing SNS topic ARNs to send alarms to"
      type        = list(string)
      default     = []
    }

    variable "create_sns_topic" {
      description = "Whether to create an SNS topic for alarms (auto-enabled if alarm_emails provided)"
      type        = bool
      default     = true
    }

    variable "sns_topic_name" {
      description = "Name for the SNS topic (defaults to <function_name>-alarms)"
      type        = string
      default     = null
    }
```
5. SNS resources (sns.tf):
# Create SNS topic if emails are provided
```hcl

resource "aws_sns_topic" "alarms" {
count = length(var.alarm_emails) > 0 ? 1 : 0

    name = var.sns_topic_name != null ? var.sns_topic_name : "${var.function_name}-alarms"
    tags = var.tags
}
```

# Create email subscriptions

```hcl
resource "aws_sns_topic_subscription" "alarm_emails" {
for_each = toset(var.alarm_emails)

    topic_arn = aws_sns_topic.alarms[0].arn
    protocol  = "email"
    endpoint  = each.value
}
```


# Combine module-created topic + external topics
```hcl
locals {
all_alarm_topic_arns = concat(
length(var.alarm_emails) > 0 ? [aws_sns_topic.alarms[0].arn] : [],
var.alarm_topic_arns
)
}
```
6. CloudWatch alarms update:
```hcl
   resource "aws_cloudwatch_metric_alarm" "errors_immediate" {
   count = var.enable_error_alarms && var.alert_strategy == "immediate" ? 1 : 0

    alarm_name          = "${var.function_name}-errors-immediate"
    comparison_operator = "GreaterThanThreshold"
    evaluation_periods  = 1
    metric_name         = "Errors"
    namespace           = "AWS/Lambda"
    period              = 60
    statistic           = "Sum"
    threshold           = 0
    treat_missing_data  = "notBreaching"

    # Send to all configured topics
    alarm_actions = local.all_alarm_topic_arns

    dimensions = {
      FunctionName = aws_lambda_function.this.function_name
    }
}


```

## Phase 3: Advanced Packaging & Build ✅

  Status: **COMPLETED**

  Goal: Support multi-architecture builds

  Implementation Notes:
  - Created scripts/package.sh for cross-platform packaging
  - Uses manylinux2014 platform tags (x86_64 and aarch64)
  - pip install with --only-binary=:all: ensures Lambda compatibility
  - null_resource triggers on source hash, requirements hash, architecture, and Python version
  - Automatic Python cache cleanup (__pycache__, .pyc, .pyo)

  Tasks:
  7. Packaging script (scripts/package.sh):
  - Based on record_metric's advanced script
  - Architecture detection and normalization
  - Platform-specific manylinux tags:
    - manylinux2014_x86_64 for x86_64
    - manylinux2014_aarch64 for arm64
  - --only-binary=:all: for pre-compiled wheels
  - Python version matching
  - Cleanup of __pycache__
  - ZIP creation with proper permissions

  8. Archive data source (packaging.tf):
    - data.archive_file for lambda code
    - aws_s3_object for package upload
    - Source hash for change detection
    - Null resource to trigger packaging script

## Phase 4: IAM & Permissions ✅

  Status: **COMPLETED**

  Goal: Flexible permission model

  Implementation Notes:
  - ✅ Base execution role with CloudWatch Logs (scoped to specific log group)
  - ✅ Variable `additional_iam_policy_arns` for user-specific permissions
  - ❌ Inline policy support **REMOVED** per user decision for simplicity
  - ✅ Output `lambda_role_arn` and `lambda_role_name` for external policy attachments

  Design Decision:
  Originally planned to support both `additional_iam_policy_arns` and `inline_policy_json`.
  User asked: "Do I actually need two sources of Lambda permissions?"
  Decision: Keep only `additional_iam_policy_arns` for cleaner interface and better Terraform practices.
  Users can create separate aws_iam_policy resources and attach them via additional_iam_policy_arns.

  Tasks:
  9. IAM configuration:
  - ✅ Base execution role with CloudWatch Logs
  - ✅ Variable additional_policy_arns for user-specific permissions
  - ❌ Optional inline policy via inline_policy_json variable (REMOVED)
  - ✅ Output the role ARN for external policy attachments

## Phase 5: Testing Infrastructure ✅

  Status: **COMPLETED**

  Goal: Comprehensive testing for provider versions 5 & 6

  Implementation Notes:
  - Created comprehensive test suite using pytest-infrahouse
  - Parameterized tests cover all combinations of provider versions, architectures, Python versions
  - Three test fixtures: simple_lambda, lambda_with_deps, lambda_with_errors
  - Test state persistence in test_data/ directory for debugging workflow
  - Complete test documentation in tests/README.md

  Tasks:
  10. Test structure (tests/):
      - conftest.py with pytest fixtures
      - test_module.py with parameterized tests
      - Test fixtures for:
        - Simple lambda (hello world)
        - Lambda with dependencies
        - Lambda with errors (to test alarms)

  11. Test cases:
    - Parameterize AWS provider: ["~> 5.31", "~> 6.0"]
    - Parameterize architecture: ["x86_64", "arm64"]
    - Parameterize Python version: ["python3.11", "python3.12", "python3.13"]
    - Parameterize alert strategy: ["immediate", "threshold"]
  12. Test validations:
    - Lambda deploys successfully
    - CloudWatch log group created
    - Error alarms created based on strategy
    - Lambda executes correctly
    - Invoke with error triggers alarm (immediate mode)
    - Multiple errors trigger alarm (threshold mode)
    - Test both architectures work
 
## Phase 6: Documentation & Examples ✅

  Status: **COMPLETED**

  Goal: Clear usage documentation

  Completed:
  - ✅ README.md with comprehensive documentation
  - ✅ outputs.tf with all important outputs
  - ✅ versions.tf with provider constraints
  - ✅ .bumpversion.cfg for version management
  - ✅ .gitignore
  - ✅ CHANGELOG.md with detailed version history
  - ✅ examples/immediate-alerts/ - Lambda with immediate error notification
  - ✅ examples/threshold-alerts/ - Lambda with error rate threshold
  - ✅ examples/custom-permissions/ - Lambda with S3 and DynamoDB access
  - ✅ .github/workflows/terraform-CI.yml - Automated testing on pull requests

  Tasks:
  13. README.md:
      - ✅ Module description & purpose
      - ✅ ISO27001 compliance notes
      - ✅ Requirements (Terraform version, AWS provider)
      - ✅ Usage examples for both alert strategies
      - ✅ Variable reference (auto-generated from terraform-docs)
      - ✅ Output reference (auto-generated from terraform-docs)

  14. Examples directory:
    - ✅ examples/immediate-alerts/ - Lambda with immediate error notification
      - Complete with Lambda code (main.py)
      - Terraform configuration (main.tf, variables.tf, outputs.tf)
      - Comprehensive README with architecture, usage, troubleshooting
    - ✅ examples/threshold-alerts/ - Lambda with error rate threshold
      - Complete with Lambda code (main.py)
      - Terraform configuration (main.tf, variables.tf, outputs.tf)
      - Comprehensive README with alert logic explanation
    - ✅ examples/custom-permissions/ - Lambda with additional IAM policies
      - Complete with Lambda code (main.py, requirements.txt)
      - Terraform configuration with S3 and DynamoDB resources
      - IAM policies for S3 read and DynamoDB write
      - Comprehensive README with permission patterns

  15. Additional files:
    - ✅ outputs.tf - Export function ARN, role ARN, log group name, alarm ARNs
    - ✅ versions.tf - Terraform and provider version constraints
    - ✅ CHANGELOG.md - Version history following Keep a Changelog format
      - Initial release v0.1.0 documented
      - Unreleased section for VPC features
      - Semantic versioning compliance

## Phase 7: Advanced Features (Optional) 🔄

  Status: **PARTIALLY COMPLETED**

  Goal: Additional enterprise requirements

  Completed:
  - ✅ VPC configuration support (lambda_subnet_ids, lambda_security_group_ids)
  - ✅ Automatic EC2 ENI permissions for VPC-attached functions

  Tasks:
  16. Optional enhancements:
      - Dead Letter Queue (DLQ) configuration
      - ✅ VPC configuration support
      - Reserved concurrent executions
      - Provisioned concurrency
      - Lambda Insights support
      - X-Ray tracing
      - Multiple runtime support (if needed beyond Python)

---

  Recommended Implementation Order

  1. Start with Phase 1 - Get basic lambda working with variable architecture/Python version
  2. Add Phase 3 - Packaging is critical for multi-arch support
  3. Implement Phase 2 - Core value proposition (monitoring)
  4. Add Phase 4 - IAM flexibility
  5. Build Phase 5 - Comprehensive testing
  6. Document Phase 6 - Make it usable
  7. Enhance Phase 7 - Based on feedback

  Key Design Decisions

  Alert Strategy Choice:
  module "lambda" {
    source = "infrahouse/lambda-monitored/aws"

    # For critical operations - immediate alerts
    alert_strategy = "immediate"
    alarm_actions  = [aws_sns_topic.critical.arn]

    # OR for fault-tolerant operations
    alert_strategy           = "threshold"
    error_rate_threshold     = 5.0  # 5% error rate
    error_rate_eval_periods  = 2    # Over 2 periods
  }

  Architecture Flexibility:
  # Cost optimization with ARM
  architecture = "arm64"

  # Compatibility requirements
  architecture = "x86_64"
