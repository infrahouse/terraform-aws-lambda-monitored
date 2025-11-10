import logging
from pathlib import Path
from textwrap import dedent

import pytest
from infrahouse_core.logging import setup_logging

LOG = logging.getLogger(__name__)

setup_logging(LOG, debug=True, debug_botocore=False)


# Pytest hooks
# More details on
# https://pytest-with-eric.com/hooks/pytest-hooks/#Test-Running-runtest-Hooks
def pytest_runtest_logstart(nodeid, location):
    """Log when a test starts."""
    LOG.info(f"TEST STARTED: {nodeid}")


def pytest_runtest_logfinish(nodeid, location):
    """Log when a test finishes."""
    LOG.info(f"TEST ENDED: {nodeid}")


def create_terraform_config(
    module_dir: Path,
    lambda_source_dir: Path,
    function_name: str,
    alarm_email: str,
    aws_provider_version: str,
    python_version: str = "python3.12",
    architecture: str = "x86_64",
    alert_strategy: str = "immediate",
    aws_region: str = "us-west-2",
    role_arn: str = None,
    subnet_ids: list = None,
    security_group_ids: list = None,
):
    """
    Create Terraform configuration files for testing the module.

    Generates a complete Terraform configuration that instantiates the
    lambda-monitored module with specified parameters.

    :param Path module_dir: Directory to create Terraform files in
    :param Path lambda_source_dir: Path to Lambda source code
    :param str function_name: Name for the Lambda function
    :param str alarm_email: Email address for alarm notifications
    :param str aws_provider_version: AWS provider version constraint
    :param str python_version: Python runtime version
    :param str architecture: Lambda architecture (x86_64 or arm64)
    :param str alert_strategy: Alert strategy (immediate or threshold)
    :param str aws_region: AWS region for deployment
    :param str role_arn: IAM role ARN to assume for testing (optional)
    :param list subnet_ids: List of subnet IDs for VPC configuration (optional)
    :param list security_group_ids: List of security group IDs for VPC configuration (optional)
    """
    LOG.info("Creating Terraform root module in %s", module_dir)

    # Clean up lock file to allow different provider versions between test runs
    lock_file = module_dir / ".terraform.lock.hcl"
    try:
        lock_file.unlink()
        LOG.info(
            "Removed existing .terraform.lock.hcl to allow provider version change"
        )
    except FileNotFoundError:
        pass

    # Create terraform.tf
    terraform_tf = dedent(
        f"""
        terraform {{
          required_version = "~> 1.0"

          required_providers {{
            aws = {{
              source  = "hashicorp/aws"
              version = "{aws_provider_version}"
            }}
          }}
        }}
        """
    )
    (module_dir / "terraform.tf").write_text(terraform_tf)

    # Create variables.tf with optional VPC variables
    vpc_variables = ""
    if subnet_ids and security_group_ids is None:
        vpc_variables = dedent(
            """
            variable "subnet_ids" {
              description = "List of subnet IDs for Lambda VPC configuration"
              type        = list(string)
            }

            variable "function_name" {
              description = "Lambda function name"
              type        = string
            }
            """
        )

    variables_tf = dedent(
        f"""
        variable "region" {{
          description = "AWS region"
          type        = string
        }}

        variable "role_arn" {{
          description = "IAM role ARN to assume"
          type        = string
          default     = null
        }}

        {vpc_variables}
        """
    )
    (module_dir / "variables.tf").write_text(variables_tf)

    # Create provider.tf
    provider_tf = dedent(
        """
        provider "aws" {
          region = var.region
          dynamic "assume_role" {
            for_each = var.role_arn != null ? [1] : []
            content {
              role_arn = var.role_arn
            }
          }
          default_tags {
            tags = {
              "created_by" : "infrahouse/terraform-aws-lambda-monitored"
            }
          }
        }
        """
    )
    (module_dir / "provider.tf").write_text(provider_tf)

    # Create main.tf with optional VPC configuration
    import json

    # Create security group resource if VPC is configured
    sg_resource = ""
    vpc_config = ""
    if subnet_ids and security_group_ids is None:
        # Create security group in Terraform when VPC is configured
        sg_resource = dedent(
            """
            # Get VPC ID from subnet
            data "aws_subnet" "selected" {
              id = var.subnet_ids[0]
            }

            # Security group for Lambda
            resource "aws_security_group" "lambda" {
              name_prefix = "${var.function_name}-"
              description = "Security group for ${var.function_name} Lambda function"
              vpc_id      = data.aws_subnet.selected.vpc_id

              egress {
                from_port   = 0
                to_port     = 0
                protocol    = "-1"
                cidr_blocks = ["0.0.0.0/0"]
              }

              tags = {
                Name       = "${var.function_name}-sg"
                created_by = "terraform-aws-lambda-monitored-test"
              }
            }
            """
        )
        vpc_config = """
          # VPC Configuration
          lambda_subnet_ids         = var.subnet_ids
          lambda_security_group_ids = [aws_security_group.lambda.id]
        """
    elif subnet_ids and security_group_ids:
        vpc_config = f"""
          # VPC Configuration
          lambda_subnet_ids         = {json.dumps(subnet_ids)}
          lambda_security_group_ids = {json.dumps(security_group_ids)}
        """

    main_tf = dedent(
        f'''
        {sg_resource}
        module "lambda_monitored" {{
          source = "./.."  # Points to the root module

          function_name     = "{function_name}"
          lambda_source_dir = "{str(lambda_source_dir).replace('\\', '/')}"
          python_version    = "{python_version}"
          architecture      = "{architecture}"
          alert_strategy    = "{alert_strategy}"

          alarm_emails = ["{alarm_email}"]

          # Threshold-specific settings
          error_rate_threshold            = 5.0
          error_rate_evaluation_periods   = 2
          error_rate_datapoints_to_alarm  = 2
          {vpc_config}
          tags = {{
            Environment = "test"
            ManagedBy   = "terraform"
          }}
        }}
        '''
    )
    (module_dir / "main.tf").write_text(main_tf)

    # Create outputs.tf
    outputs_tf = dedent(
        """
        output "lambda_function_arn" {
          value = module.lambda_monitored.lambda_function_arn
        }

        output "lambda_function_name" {
          value = module.lambda_monitored.lambda_function_name
        }

        output "lambda_role_arn" {
          value = module.lambda_monitored.lambda_role_arn
        }

        output "cloudwatch_log_group_name" {
          value = module.lambda_monitored.cloudwatch_log_group_name
        }

        output "sns_topic_arn" {
          value = module.lambda_monitored.sns_topic_arn
        }

        output "error_alarm_arn" {
          value = module.lambda_monitored.error_alarm_arn
        }

        output "s3_bucket_name" {
          value = module.lambda_monitored.s3_bucket_name
        }

        output "requirements_file_used" {
          value = module.lambda_monitored.requirements_file_used
        }

        output "vpc_config_subnet_ids" {
          value = module.lambda_monitored.vpc_config_subnet_ids
        }

        output "vpc_config_security_group_ids" {
          value = module.lambda_monitored.vpc_config_security_group_ids
        }
        """
    )
    (module_dir / "outputs.tf").write_text(outputs_tf)

    # Create terraform.tfvars
    tfvars_content = f'region = "{aws_region}"\n'
    if role_arn:
        tfvars_content += f'role_arn = "{role_arn}"\n'
    if subnet_ids and security_group_ids is None:
        tfvars_content += f"subnet_ids = {json.dumps(subnet_ids)}\n"
        tfvars_content += f'function_name = "{function_name}"\n'
    (module_dir / "terraform.tfvars").write_text(tfvars_content)


# Parameterization for different test configurations
@pytest.fixture(params=["~> 5.31", "~> 6.0"], ids=["provider-5.x", "provider-6.x"])
def aws_provider_version(request):
    """
    AWS provider version to test.

    :param request: Pytest request object
    :return: AWS provider version constraint
    :rtype: str
    """
    return request.param


@pytest.fixture(params=["x86_64", "arm64"], ids=["x86", "arm64"])
def architecture(request):
    """
    Lambda function architecture to test.

    :param request: Pytest request object
    :return: Architecture type (x86_64 or arm64)
    :rtype: str
    """
    return request.param


@pytest.fixture(
    params=["python3.11", "python3.12", "python3.13"],
    ids=["py3.11", "py3.12", "py3.13"],
)
def python_version(request):
    """
    Python runtime version to test.

    :param request: Pytest request object
    :return: Python version string
    :rtype: str
    """
    return request.param


@pytest.fixture(params=["immediate", "threshold"], ids=["immediate", "threshold"])
def alert_strategy(request):
    """
    CloudWatch alarm alert strategy to test.

    :param request: Pytest request object
    :return: Alert strategy (immediate or threshold)
    :rtype: str
    """
    return request.param


@pytest.fixture
def test_module_dir():
    """
    Create Terraform module directory for testing.

    Uses a consistent directory location to preserve Terraform state across
    test runs. This allows --keep-after to work properly by maintaining state
    between debugging sessions.

    :return: Path to test module directory
    :rtype: Path
    """
    # Use consistent directory in project root for state persistence
    module_dir = Path(__file__).parent.parent / "test_data"
    module_dir.mkdir(exist_ok=True)
    return module_dir


@pytest.fixture
def fixtures_dir():
    """
    Get path to test fixtures directory.

    :return: Path to fixtures directory containing Lambda code
    :rtype: Path
    """
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def lambda_client(boto3_session, aws_region):
    """
    Create boto3 Lambda client from pytest-infrahouse boto3_session.

    :param boto3_session: Boto3 session from pytest-infrahouse
    :param str aws_region: AWS region for the client
    :return: Boto3 Lambda client
    """
    return boto3_session.client("lambda", region_name=aws_region)


@pytest.fixture
def cloudwatch_client(boto3_session, aws_region):
    """
    Create boto3 CloudWatch client from pytest-infrahouse boto3_session.

    :param boto3_session: Boto3 session from pytest-infrahouse
    :param str aws_region: AWS region for the client
    :return: Boto3 CloudWatch client
    """
    return boto3_session.client("cloudwatch", region_name=aws_region)


@pytest.fixture
def sns_client(boto3_session, aws_region):
    """
    Create boto3 SNS client from pytest-infrahouse boto3_session.

    :param boto3_session: Boto3 session from pytest-infrahouse
    :param str aws_region: AWS region for the client
    :return: Boto3 SNS client
    """
    return boto3_session.client("sns", region_name=aws_region)
