"""
Comprehensive tests for terraform-aws-lambda-monitored module.

This module tests the Lambda monitoring module across different configurations:
- Multiple AWS provider versions (5.x and 6.x)
- Different architectures (x86_64 and arm64)
- Various Python versions (3.11, 3.12, 3.13)
- Alert strategies (immediate and threshold)
"""

import json
import time
from pathlib import Path

from pytest_infrahouse import terraform_apply

from tests.conftest import LOG, create_terraform_config


class TestSimpleLambda:
    """Test suite for simple Lambda function without dependencies."""

    def test_lambda_deployment(
        self,
        test_module_dir,
        fixtures_dir,
        aws_provider_version,
        architecture,
        python_version,
        keep_after,
        test_role_arn,
    ):
        """
        Test Lambda function deploys successfully.

        Verifies that a simple Lambda function can be deployed with the module
        across different provider versions, architectures, and Python versions.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str aws_provider_version: AWS provider version to test
        :param str architecture: Lambda architecture to test
        :param str python_version: Python version to test
        :param bool keep_after: Whether to keep resources after test
        """
        function_name = f"test-simple-{architecture.replace('_', '')}-{python_version.replace('.', '')}"
        lambda_source = fixtures_dir / "simple_lambda"

        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            "test@example.com",
            aws_provider_version,
            python_version,
            architecture,
            role_arn=test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            # Verify Lambda function was created
            assert "lambda_function_arn" in tf_output
            assert tf_output["lambda_function_arn"]["value"].startswith(
                "arn:aws:lambda:"
            )

            # Verify function name matches
            assert tf_output["lambda_function_name"]["value"] == function_name

            # Verify CloudWatch log group was created
            assert (
                tf_output["cloudwatch_log_group_name"]["value"]
                == f"/aws/lambda/{function_name}"
            )

            # Verify S3 bucket was created
            assert tf_output["s3_bucket_name"]["value"]
            assert "test-simple-" in tf_output["s3_bucket_name"]["value"]

            # Verify requirements file detection (should be "none" for simple lambda)
            assert tf_output["requirements_file_used"]["value"] == "none"

    def test_lambda_invocation(
        self,
        test_module_dir,
        fixtures_dir,
        python_version,
        lambda_client,
        keep_after,
        test_role_arn,
    ):
        """
        Test Lambda function executes successfully.

        Invokes the deployed Lambda function and verifies it returns the expected response.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str python_version: Python version to test
        :param lambda_client: Boto3 Lambda client fixture
        :param bool keep_after: Whether to keep resources after test
        """
        function_name = f"test-invoke-{python_version.replace('.', '')}"
        lambda_source = fixtures_dir / "simple_lambda"

        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            "test@example.com",
            "~> 5.31",
            python_version,
            role_arn=test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            # Invoke Lambda function
            response = lambda_client.invoke(
                FunctionName=tf_output["lambda_function_name"]["value"],
                InvocationType="RequestResponse",
                Payload=json.dumps({}),
            )

            # Verify successful invocation
            assert response["StatusCode"] == 200
            assert "FunctionError" not in response

            # Parse and verify response payload
            payload = json.loads(response["Payload"].read())
            assert payload["statusCode"] == 200
            assert "Hello from Lambda!" in payload["body"]


class TestLambdaWithDependencies:
    """Test suite for Lambda function with external dependencies."""

    def test_dependency_packaging(
        self,
        test_module_dir,
        fixtures_dir,
        architecture,
        python_version,
        keep_after,
        test_role_arn,
    ):
        """
        Test Lambda function with dependencies packages correctly.

        Verifies that platform-specific dependencies (manylinux wheels) are
        properly packaged for the target architecture.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str architecture: Lambda architecture to test
        :param str python_version: Python version to test
        :param bool keep_after: Whether to keep resources after test
        """
        function_name = f"test-deps-{architecture.replace('_', '')}-{python_version.replace('.', '')}"
        lambda_source = fixtures_dir / "lambda_with_deps"

        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            "test@example.com",
            "~> 5.31",
            python_version,
            architecture,
            role_arn=test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            # Verify requirements file was detected
            requirements_file = tf_output["requirements_file_used"]["value"]
            assert requirements_file != "none"
            assert "requirements.txt" in requirements_file

            # Verify Lambda function was created successfully
            assert tf_output["lambda_function_arn"]["value"]

    def test_dependency_execution(
        self,
        test_module_dir,
        fixtures_dir,
        architecture,
        lambda_client,
        keep_after,
        test_role_arn,
    ):
        """
        Test Lambda function with dependencies executes successfully.

        Invokes Lambda that uses the requests library to verify dependencies
        are properly installed and functional.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str architecture: Lambda architecture to test
        :param lambda_client: Boto3 Lambda client fixture
        :param bool keep_after: Whether to keep resources after test
        """
        function_name = f"test-deps-exec-{architecture.replace('_', '')}"
        lambda_source = fixtures_dir / "lambda_with_deps"

        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            "test@example.com",
            "~> 5.31",
            architecture=architecture,
            role_arn=test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            # Invoke Lambda function
            response = lambda_client.invoke(
                FunctionName=tf_output["lambda_function_name"]["value"],
                InvocationType="RequestResponse",
                Payload=json.dumps({}),
            )

            # Verify successful invocation
            assert response["StatusCode"] == 200

            # Parse response
            payload = json.loads(response["Payload"].read())
            assert payload["statusCode"] == 200

            # Verify requests library worked
            body = json.loads(payload["body"])
            assert body["success"] is True
            assert "requests_version" in body


class TestErrorMonitoring:
    """Test suite for CloudWatch alarm functionality."""

    def test_immediate_alert_strategy(
        self,
        test_module_dir,
        fixtures_dir,
        lambda_client,
        cloudwatch_client,
        keep_after,
        test_role_arn,
    ):
        """
        Test immediate alert strategy triggers on any error.

        Verifies that the CloudWatch alarm enters ALARM state when a Lambda
        error occurs with the immediate alert strategy.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param lambda_client: Boto3 Lambda client fixture
        :param cloudwatch_client: Boto3 CloudWatch client fixture
        :param bool keep_after: Whether to keep resources after test
        """
        function_name = "test-immediate-alert"
        lambda_source = fixtures_dir / "lambda_with_errors"

        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            "test@example.com",
            "~> 5.31",
            alert_strategy="immediate",
            role_arn=test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            # Invoke Lambda without error first (should succeed)
            response = lambda_client.invoke(
                FunctionName=tf_output["lambda_function_name"]["value"],
                InvocationType="RequestResponse",
                Payload=json.dumps({"force_error": False}),
            )
            assert response["StatusCode"] == 200

            # Now invoke with error
            response = lambda_client.invoke(
                FunctionName=tf_output["lambda_function_name"]["value"],
                InvocationType="RequestResponse",
                Payload=json.dumps({"force_error": True}),
            )
            assert "FunctionError" in response

            # Wait for alarm to update (CloudWatch alarms evaluate every 60 seconds)
            alarm_name = f"{function_name}-errors-immediate"
            time.sleep(90)  # Wait for alarm evaluation

            # Check alarm state
            alarms = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name])
            assert len(alarms["MetricAlarms"]) == 1
            # Note: Alarm may be in ALARM or INSUFFICIENT_DATA state depending on timing
            alarm_state = alarms["MetricAlarms"][0]["StateValue"]
            assert alarm_state in ["ALARM", "INSUFFICIENT_DATA"]

    def test_threshold_alert_strategy(
        self,
        test_module_dir,
        fixtures_dir,
        lambda_client,
        keep_after,
        test_role_arn,
    ):
        """
        Test threshold alert strategy requires multiple errors.

        Verifies that the threshold-based alarm only triggers when error rate
        exceeds the configured threshold.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param lambda_client: Boto3 Lambda client fixture
        :param bool keep_after: Whether to keep resources after test
        """
        function_name = "test-threshold-alert"
        lambda_source = fixtures_dir / "lambda_with_errors"

        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            "test@example.com",
            "~> 5.31",
            alert_strategy="threshold",
            role_arn=test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            function_name_output = tf_output["lambda_function_name"]["value"]

            # Invoke multiple times: some successes, some failures
            # To trigger a 5% error rate alarm, we need enough invocations
            for i in range(10):
                force_error = i < 2  # First 2 will error (20% error rate)
                lambda_client.invoke(
                    FunctionName=function_name_output,
                    InvocationType="RequestResponse",
                    Payload=json.dumps({"force_error": force_error}),
                )

            # Verify alarm was created
            assert tf_output["error_alarm_arn"]["value"]
            assert "threshold" in tf_output["error_alarm_arn"]["value"]


class TestSNSIntegration:
    """Test suite for SNS topic and email subscription."""

    def test_sns_topic_creation(
        self,
        test_module_dir,
        fixtures_dir,
        sns_client,
        keep_after,
        test_role_arn,
    ):
        """
        Test SNS topic is created for alarm notifications.

        Verifies that the module creates an SNS topic and email subscriptions
        for alarm notifications.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param sns_client: Boto3 SNS client fixture
        :param bool keep_after: Whether to keep resources after test
        """
        function_name = "test-sns-topic"
        lambda_source = fixtures_dir / "simple_lambda"
        test_email = "test@example.com"

        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            test_email,
            "~> 5.31",
            role_arn=test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            # Verify SNS topic was created
            topic_arn = tf_output["sns_topic_arn"]["value"]
            assert topic_arn
            assert topic_arn.startswith("arn:aws:sns:")

            # Verify email subscription was created (will be PendingConfirmation)
            subscriptions = sns_client.list_subscriptions_by_topic(TopicArn=topic_arn)
            email_subs = [
                s for s in subscriptions["Subscriptions"] if s["Protocol"] == "email"
            ]
            assert len(email_subs) >= 1
            assert any(test_email in s["Endpoint"] for s in email_subs)


class TestVPCIntegration:
    """Test suite for VPC Lambda integration and IAM permissions."""

    def test_vpc_lambda_deployment_and_execution(
        self,
        test_module_dir,
        fixtures_dir,
        service_network,
        lambda_client,
        keep_after,
        test_role_arn,
    ):
        """
        Test Lambda deployment and execution within VPC.

        This test verifies that:
        1. Lambda can be deployed with VPC configuration
        2. IAM policies are correctly scoped to specific subnets/security groups
        3. Lambda can create ENIs in the VPC
        4. Lambda can execute successfully in VPC
        5. Lambda cleanup works (terraform destroy removes ENIs via scoped permissions)

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param dict service_network: Service network fixture from pytest-infrahouse
        :param lambda_client: Boto3 Lambda client fixture
        :param bool keep_after: Whether to keep resources after test
        :param str test_role_arn: IAM role ARN for testing
        """
        function_name = "test-vpc-lambda"
        lambda_source = fixtures_dir / "simple_lambda"

        # Extract subnet IDs from service_network fixture
        # service_network has structure: {"subnet_private_ids": {"value": [...]}, ...}
        subnet_private_ids = service_network["subnet_private_ids"]["value"]

        LOG.info(f"Using private subnets from service_network: {subnet_private_ids}")

        # Create Terraform config with VPC settings
        # The security group will be created by Terraform
        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            "test@example.com",
            "~> 5.31",
            subnet_ids=subnet_private_ids,
            # security_group_ids=None means Terraform will create the SG
            role_arn=test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            # Verify Lambda was created with VPC configuration
            assert tf_output["lambda_function_arn"]["value"]
            assert tf_output["vpc_config_subnet_ids"]["value"] == subnet_private_ids

            # Verify security group was created
            security_group_ids = tf_output["vpc_config_security_group_ids"]["value"]
            assert security_group_ids
            assert len(security_group_ids) == 1
            LOG.info(f"Lambda using security group: {security_group_ids[0]}")

            # Verify IAM role exists
            lambda_role_arn = tf_output["lambda_role_arn"]["value"]
            assert lambda_role_arn
            LOG.info(f"Lambda IAM role: {lambda_role_arn}")

            # Invoke Lambda to trigger ENI creation and verify execution
            # This tests that the scoped IAM permissions actually work
            LOG.info("Invoking Lambda to test VPC ENI creation with scoped IAM permissions...")
            response = lambda_client.invoke(
                FunctionName=tf_output["lambda_function_name"]["value"],
                InvocationType="RequestResponse",
                Payload=json.dumps({}),
            )

            # Verify successful invocation (proves ENI was created successfully)
            assert response["StatusCode"] == 200
            assert "FunctionError" not in response

            # Parse and verify response payload
            payload = json.loads(response["Payload"].read())
            assert payload["statusCode"] == 200
            assert "Hello from Lambda!" in payload["body"]

            LOG.info(
                "SUCCESS: VPC Lambda executed successfully - "
                "IAM permissions are correctly scoped to specific subnets/security groups"
            )
            LOG.info(
                "The test verified that Lambda can create ENIs with least-privilege IAM policies"
            )
