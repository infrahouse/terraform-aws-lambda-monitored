# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]

## [0.3.3] - 2025-11-09

## [0.3.2] - 2025-11-09

### Fixed
- Fixed IAM role creation failure when `function_name` exceeds 37 characters
- IAM role `name_prefix` now truncates function names longer than 37 characters to comply with AWS's 38-character limit
- Removed redundant "-role-" suffix from IAM role names (now uses up to 37 characters of function name instead of 32)
- Full function name is preserved in the IAM role's `function_name` tag for identification

### Added
- **VPC Configuration Support**: Lambda functions can now be attached to VPC for accessing private resources
  - `lambda_subnet_ids` variable for specifying VPC subnets (must have NAT gateway)
  - `lambda_security_group_ids` variable for specifying security groups
  - Automatic IAM permissions for EC2 network interface management (CreateNetworkInterface, DescribeNetworkInterfaces, DeleteNetworkInterface, AssignPrivateIpAddresses, UnassignPrivateIpAddresses)
  - VPC configuration is optional and controlled via dynamic block
  - VPC-related outputs: `vpc_config_subnet_ids`, `vpc_config_security_group_ids`
  - Comprehensive VPC documentation in README with use cases and considerations

- **CI/CD Workflows**: GitHub Actions workflows for automated testing and deployment
  - **terraform-CI.yml**: Automated testing on pull requests
    - Self-hosted runner configuration
    - AWS OIDC authentication with role assumption
    - Automated Python environment setup, linting, and testing
  - **terraform-CD.yml**: Automated module publishing on tag push
    - Publishes to InfraHouse Terraform Registry
    - Production environment protection
  - Follows InfraHouse CI/CD patterns for consistency across modules

## [0.1.0] - 2025-11-02

### Added

#### Core Features
- Initial release of terraform-aws-lambda-monitored module
- Multi-Python version support (Python 3.9, 3.10, 3.11, 3.12, 3.13)
- Multi-architecture support (x86_64 and arm64)
- Intelligent dependency packaging with platform-specific manylinux wheels
- Automatic change detection for re-packaging (source, dependencies, architecture, Python version)
- S3-based deployment with secure bucket management
- CloudWatch Logs with configurable retention (365 days default) and AES256 encryption
- Lambda function event invoke configuration with zero retries by default

#### Monitoring & Alerting (ISO27001 Compliance)
- Two alert strategies:
  - **Immediate**: Trigger alarm on any Lambda error
  - **Threshold**: Trigger alarm when error rate exceeds configured percentage
- CloudWatch metric math for error rate calculation (errors/invocations * 100)
- Configurable evaluation periods and datapoints to alarm
- Throttle monitoring with separate CloudWatch alarm
- SNS topic creation and email subscription management
- Support for external SNS topic ARNs (for PagerDuty, Slack, etc.)
- Required `alarm_emails` variable with validation (minimum 1 email)

#### IAM & Permissions
- Base execution role with CloudWatch Logs permissions (scoped to function's log group)
- `additional_iam_policy_arns` variable for attaching custom IAM policies
- IAM role name_prefix to prevent naming collisions
- Output Lambda role ARN and name for external policy attachments

#### Packaging & Build
- `scripts/package.sh` for cross-platform Lambda packaging
- Architecture normalization (arm64→aarch64, x86_64)
- Manylinux platform tag mapping (manylinux2014_x86_64, manylinux2014_aarch64)
- pip install with `--only-binary=:all:` for Lambda compatibility
- Python version matching for dependency installation
- Automatic cleanup of Python cache files (`__pycache__`, `.pyc`, `.pyo`)
- null_resource with triggers for intelligent re-packaging

#### Documentation
- Comprehensive README with usage examples, features, and configuration options
- Module inputs and outputs documentation
- Email subscription confirmation notes
- S3 bucket security details
- Dependencies and packaging documentation

#### Testing
- Complete test suite using pytest-infrahouse
- Parameterized tests for AWS provider versions 5.x and 6.x
- Parameterized tests for architectures (x86_64, arm64)
- Parameterized tests for Python versions (3.11, 3.12, 3.13)
- Parameterized tests for alert strategies (immediate, threshold)
- Three test fixtures: simple_lambda, lambda_with_deps, lambda_with_errors
- Test state persistence for debugging workflow
- Complete test documentation in tests/README.md

#### Examples
- **immediate-alerts**: Demonstrates immediate error alerting for critical operations
- **threshold-alerts**: Demonstrates threshold-based alerting for fault-tolerant operations
- **custom-permissions**: Demonstrates adding S3 and DynamoDB permissions
- Each example includes Lambda code, Terraform configuration, and comprehensive README

#### CI/CD
- GitHub Actions workflow for automated testing
- Matrix testing across AWS provider versions
- Scheduled weekly test runs
- Manual workflow dispatch support

#### Infrastructure
- terraform.tf with required providers (AWS >= 5.31, AWS ~> 6.0, archive ~> 2.0)
- versions.tf constraining Terraform ~> 1.0
- .bumpversion.cfg for automated version management
- .gitignore for build artifacts and Terraform state
- locals.tf with module metadata and InfraHouse tagging pattern

### Design Decisions
- **Removed inline_policy support**: Simplified IAM model to use only `additional_iam_policy_arns` for cleaner interface and better Terraform practices (users create separate aws_iam_policy resources)
- **Required alarm_emails**: Made `alarm_emails` required with minimum 1 email for ISO27001 compliance (no optional/default empty list)
- **SNS topic always created**: SNS topic is always created (no conditional creation logic)
- **Zero retry default**: Lambda function configured with zero retry attempts by default

### Security
- CloudWatch Log Group encryption with AWS managed keys (AES256)
- S3 bucket encryption, versioning, and public access blocking (via infrahouse/s3-bucket module)
- Scoped IAM permissions (CloudWatch Logs policy limited to function's specific log group)
- Least privilege IAM model (base permissions only, custom permissions via explicit policy attachments)

[Unreleased]: https://github.com/infrahouse/terraform-aws-lambda-monitored/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/infrahouse/terraform-aws-lambda-monitored/releases/tag/v0.1.0
