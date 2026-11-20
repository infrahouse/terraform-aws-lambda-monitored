# Tests for terraform-aws-lambda-monitored

This directory contains comprehensive integration tests for the `terraform-aws-lambda-monitored` Terraform module.

## Overview

The test suite validates the module across:
- **AWS Provider Versions**: 5.x and 6.x
- **Architectures**: x86_64 and arm64
- **Python Versions**: 3.11, 3.12, and 3.13
- **Alert Strategies**: immediate and threshold

## Prerequisites

1. **AWS Credentials**: Configure AWS credentials with permissions to create Lambda functions, IAM roles, CloudWatch alarms, SNS topics, and S3 buckets.

2. **Python**: Python 3.9 or higher

3. **Terraform**: Terraform 1.0 or higher

4. **Test Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Test Structure

```
tests/
├── fixtures/               # Lambda function test fixtures
│   ├── simple_lambda/     # Basic Lambda without dependencies
│   ├── lambda_with_deps/  # Lambda with external packages (requests)
│   ├── lambda_with_errors/ # Lambda that can simulate errors
│   └── lambda_logs_continuously/ # Lambda that logs every half second, for the destroy test
├── test_module.py         # Main test suite
├── test_error_monitoring.py # Error alarm tests (immediate/threshold, late and sparse errors)
├── test_log_group.py      # Log group tests: no CreateLogGroup on the role, group stays deleted after destroy
├── tools/                  # Diagnostics, not collected by pytest
│   ├── probe_alarm_range.py # Measures how far back CloudWatch alarms look for datapoints
│   └── probe_single_datapoint.py # Checks datapoints_to_alarm against breaching/missing periods
├── requirements.txt       # Test dependencies
└── README.md             # This file
```

## Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test Classes

```bash
# Test simple Lambda deployment
pytest tests/test_module.py::TestSimpleLambda

# Test dependency packaging
pytest tests/test_module.py::TestLambdaWithDependencies

# Test error monitoring
pytest tests/test_error_monitoring.py::TestErrorMonitoring

# Test SNS integration
pytest tests/test_module.py::TestSNSIntegration

# Test the log group's permissions and destroy behavior
pytest tests/test_log_group.py::TestLogGroup
```

### Run Tests with Specific Parameters

```bash
# Test only x86_64 architecture
pytest tests/ -k "x86"

# Test only arm64 architecture
pytest tests/ -k "arm64"

# Test only Python 3.12
pytest tests/ -k "py3.12"

# Test only immediate alert strategy
pytest tests/ -k "immediate"
```

### pytest-infrahouse Options

The tests use the `pytest-infrahouse` plugin which provides additional command-line options:

```bash
# Specify AWS region
pytest tests/ --aws-region=us-east-1

# Keep resources after test (for debugging)
pytest tests/ --keep-after

# Assume a specific IAM role
pytest tests/ --test-role-arn=arn:aws:iam::123456789012:role/test-role

# Set DNS zone for tests (if needed)
pytest tests/ --test-zone-name=test.example.com
```

### Test State Persistence

Tests use a consistent `test_data/` directory in the project root to store Terraform state. This enables:

1. **Debugging workflow**: Run tests with `--keep-after` to preserve resources
2. **Incremental testing**: Re-run tests against the same infrastructure
3. **Manual inspection**: Resources remain available for inspection between test runs
4. **Clean destruction**: Running without `--keep-after` later will destroy the preserved resources

```bash
# First run - create and keep resources
pytest tests/ --keep-after

# Inspect AWS resources, make code changes...

# Second run - update existing resources
pytest tests/ --keep-after

# Final run - destroy resources
pytest tests/

# Or manually clean everything
make clean  # Removes test_data/ directory
```

## Test Fixtures

### simple_lambda
A minimal Lambda function that returns a success message. Used for basic deployment and invocation tests.

**File**: `fixtures/simple_lambda/main.py`

### lambda_with_deps
A Lambda function that uses the `requests` library to make HTTP calls. Used to test platform-specific dependency packaging.

**Files**:
- `fixtures/lambda_with_deps/main.py`
- `fixtures/lambda_with_deps/requirements.txt`

### lambda_with_errors
A Lambda function that can simulate errors when invoked with `force_error: true`. Used to test CloudWatch alarm triggering.

**File**: `fixtures/lambda_with_errors/main.py`

### lambda_logs_continuously
A Lambda function that prints a line every half second for `event["seconds"]` seconds. The destroy test deletes the
function while it runs, so Lambda writes the invocation's last lines after the function is gone (issue #26).

**File**: `fixtures/lambda_logs_continuously/main.py`

## Test Cases

### TestSimpleLambda

**test_lambda_deployment**: Verifies Lambda function deploys successfully with correct configuration across all parameter combinations.

**test_lambda_invocation**: Tests that the Lambda function executes successfully and returns expected output.

**test_role_name_prefix_set**: Applies with a 38-character `role_name_prefix` and checks that the role the function
runs as, as AWS reports it, is the prefix plus Terraform's 26-character suffix.

**test_role_name_prefix_unset**: Without `role_name_prefix`, checks the role keeps the default name (function name cut
to 37 characters plus `-`) for a short and a long function name, with the full name in the `function_name` tag.

**test_role_name_prefix_validation_accepts** / **test_role_name_prefix_validation_rejects**: Run `terraform plan`
only, creating nothing. `null` and a 38-character prefix pass; an empty string, 39 characters and `*` fail on the
variable's validation rule.

### TestLambdaWithDependencies

**test_dependency_packaging**: Validates that platform-specific dependencies are packaged correctly for the target architecture.

**test_dependency_execution**: Verifies that packaged dependencies work correctly when Lambda executes.

### TestErrorMonitoring

**test_immediate_alert_strategy**: Tests that CloudWatch alarm triggers on any error with immediate strategy.

**test_threshold_alert_strategy**: Validates that threshold-based alarm only triggers when error rate exceeds configured threshold.

### TestSNSIntegration

**test_sns_topic_creation**: Verifies SNS topic and email subscriptions are created correctly.

### TestLogGroup

Lives in `test_log_group.py`; `make test-log-group` runs it (issue #26).

**test_logging_policy_without_create_log_group**: Applies the module and reads the role's inline logging policy from
IAM. No `Allow` statement may grant `logs:CreateLogGroup`, wildcards included, while `logs:CreateLogStream` and
`logs:PutLogEvents` stay. Then invokes the function and waits for a log event in the module's log group, so logging
still works without the permission.

**test_log_group_stays_deleted_after_destroy**: Deploys `lambda_logs_continuously`, starts a 90-second async
invocation, waits for its first line, and destroys while it runs. Deleting the function stops the invocation, and
Lambda flushes the lines it still holds right after, which on the unfixed module re-created the group every time.
Then checks every 5 seconds for 60 seconds that `/aws/lambda/<function_name>` hasn't come back. A group that reappears
is deleted, so the next run's apply isn't blocked, and the test fails with its creation time and retention. It
destroys even with `--keep-after`.

**test_log_group_destroy_delay_validation_accepts** / **test_log_group_destroy_delay_validation_rejects**: Run
`terraform plan` only, creating nothing. `0` and `10` pass; `-1` and `1.5` fail on the variable's validation rule.

## Environment Variables

- `AWS_DEFAULT_REGION`: AWS region for running tests (default: us-west-2)
- `AWS_PROFILE`: AWS profile to use for credentials
- `TEST_ALARM_EMAIL`: Email address for alarm notification tests

## Expected Test Duration

- Full test suite: 30-45 minutes (due to Terraform apply/destroy cycles)
- Single test class: 5-10 minutes
- Individual test: 2-5 minutes

## Troubleshooting

### Tests Timing Out

Increase the timeout in `pytest.ini`:
```ini
timeout = 1200  # 20 minutes
```

### Resources Not Cleaned Up

If tests fail and resources remain:

1. Check the `test_data/` directory for Terraform state
2. Manually destroy with:
   ```bash
   cd test_data/
   terraform destroy
   ```
3. Or clean everything with: `make clean`

### AWS Credentials Issues

Ensure your AWS credentials have the following permissions:
- `lambda:*`
- `iam:CreateRole`, `iam:DeleteRole`, `iam:AttachRolePolicy`, etc.
- `s3:CreateBucket`, `s3:DeleteBucket`, `s3:PutObject`, etc.
- `cloudwatch:PutMetricAlarm`, `cloudwatch:DeleteAlarms`
- `sns:CreateTopic`, `sns:Subscribe`, `sns:DeleteTopic`
- `logs:CreateLogGroup`, `logs:DeleteLogGroup`

### Alarm State Validation

CloudWatch alarms evaluate every 60 seconds. Tests include appropriate wait times, but flaky results may occur due to timing. Consider the alarm state as informational rather than strictly asserting ALARM state.

## Contributing

When adding new tests:

1. Use RST-style docstrings for all functions and classes
2. Follow the existing test structure and naming conventions
3. Add appropriate pytest markers for test categorization
4. Ensure tests clean up resources (use `destroy_after=True`)
5. Document any new test fixtures in this README

## CI/CD Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  env:
    AWS_REGION: us-west-2
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: |
    pip install -r tests/requirements.txt
    pytest tests/ -v
```

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-infrahouse](https://github.com/infrahouse/pytest-infrahouse)
- [boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Terraform Testing Best Practices](https://www.terraform.io/docs/language/modules/testing-experiment.html)
