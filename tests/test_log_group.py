"""
Log group lifecycle tests for terraform-aws-lambda-monitored (issue #26).

After ``terraform destroy``, ``/aws/lambda/<function_name>`` could reappear seconds later,
created outside Terraform without a retention policy, and the next apply then failed with
``ResourceAlreadyExistsException``. These tests check the two parts of the fix: the execution
role can't create log groups, and the group stays deleted after destroy.
"""

import json
import time
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Dict, List, Optional

from botocore.client import BaseClient
from infrahouse_core.timeout import timeout
from pytest_infrahouse import terraform_apply

from tests.conftest import LOG, create_terraform_config

# After terraform destroy, how long to watch for the function's log group to come back.
# In the issue the orphan appeared 7 seconds after the function was deleted.
LOG_GROUP_WATCH_SECONDS = 60
LOG_GROUP_POLL_SECONDS = 5

# How long to wait for an invocation's log events to become readable.
LOG_EVENTS_TIMEOUT_SECONDS = 180


def allowed_actions(policy_document: Dict[str, Any]) -> List[str]:
    """
    List the actions that the ``Allow`` statements of an IAM policy document grant.

    :param dict policy_document: Policy document as boto3 returns it, already URL-decoded
    :return: Every action of every ``Allow`` statement, as written in the policy
    :rtype: list
    """
    statements = policy_document["Statement"]
    if isinstance(statements, dict):
        statements = [statements]

    actions = []
    for statement in statements:
        if statement["Effect"] != "Allow":
            continue
        statement_actions = statement.get("Action", [])
        if isinstance(statement_actions, str):
            statement_actions = [statement_actions]
        actions.extend(statement_actions)
    return actions


def grants_action(actions: List[str], action: str) -> bool:
    """
    Tell whether any of the given action patterns matches an action.

    IAM compares action names case-insensitively and allows ``*`` and ``?`` wildcards,
    so ``logs:*`` and ``logs:Create*`` both grant ``logs:CreateLogGroup``.

    :param list actions: Action patterns from a policy
    :param str action: Action to look for, e.g. ``logs:CreateLogGroup``
    :return: True if at least one pattern matches the action
    :rtype: bool
    """
    return any(fnmatchcase(action.lower(), pattern.lower()) for pattern in actions)


def find_log_group(
    logs_client: BaseClient, log_group_name: str
) -> Optional[Dict[str, Any]]:
    """
    Look up a CloudWatch Logs log group by its exact name.

    :param BaseClient logs_client: Boto3 CloudWatch Logs client
    :param str log_group_name: Name of the log group
    :return: The log group as ``describe_log_groups`` describes it, or None if there is no such group
    :rtype: dict
    """
    paginator = logs_client.get_paginator("describe_log_groups")
    for page in paginator.paginate(logGroupNamePrefix=log_group_name):
        for log_group in page["logGroups"]:
            if log_group["logGroupName"] == log_group_name:
                return log_group
    return None


def invoke_once(lambda_client: BaseClient, function_name: str) -> None:
    """
    Invoke the function synchronously and check that it succeeded.

    :param BaseClient lambda_client: Boto3 Lambda client
    :param str function_name: Name of the function to invoke
    :raise AssertionError: If the invocation fails or the function raises
    """
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({}),
    )
    assert response["StatusCode"] == 200, response
    assert "FunctionError" not in response, response


def write_simple_lambda_config(
    test_module_dir: Path,
    fixtures_dir: Path,
    function_name: str,
    aws_provider_version: str,
    aws_region: str,
    test_role_arn: str,
) -> None:
    """
    Write a root module that deploys the ``simple_lambda`` fixture with the module's defaults.

    :param Path test_module_dir: Directory to write the root module to
    :param Path fixtures_dir: Path to Lambda fixtures
    :param str function_name: Name of the Lambda function
    :param str aws_provider_version: AWS provider version constraint
    :param str aws_region: AWS region to deploy to
    :param str test_role_arn: IAM role ARN Terraform assumes
    """
    create_terraform_config(
        test_module_dir,
        fixtures_dir / "simple_lambda",
        function_name,
        "devnull@infrahouse.com",
        aws_provider_version,
        aws_region=aws_region,
        role_arn=test_role_arn,
    )


class TestLogGroup:
    """The function's log group: who may create it, and that it stays deleted after destroy."""

    def test_logging_policy_without_create_log_group(
        self,
        test_module_dir: Path,
        fixtures_dir: Path,
        aws_provider_version: str,
        aws_region: str,
        iam_client: BaseClient,
        lambda_client: BaseClient,
        logs_client: BaseClient,
        keep_after: bool,
        test_role_arn: str,
    ) -> None:
        """
        Test that the execution role can't create log groups, yet still logs to the module's group.

        The module creates ``/aws/lambda/<function_name>`` before the function, so the role never
        needs ``logs:CreateLogGroup``. Without it, a late write after ``terraform destroy`` can't
        bring the group back. The invocation checks that logging still works: a log event must
        reach the module's log group.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str aws_provider_version: AWS provider version to test
        :param str aws_region: AWS region to deploy to
        :param BaseClient iam_client: Boto3 IAM client fixture
        :param BaseClient lambda_client: Boto3 Lambda client fixture
        :param BaseClient logs_client: Boto3 CloudWatch Logs client fixture
        :param bool keep_after: Whether to keep resources after test
        :param str test_role_arn: IAM role ARN for testing
        """
        function_name = "test-logging-policy"
        write_simple_lambda_config(
            test_module_dir,
            fixtures_dir,
            function_name,
            aws_provider_version,
            aws_region,
            test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            role_name = tf_output["lambda_role_name"]["value"]
            policy = iam_client.get_role_policy(
                RoleName=role_name, PolicyName=f"{function_name}-logging"
            )
            actions = allowed_actions(policy["PolicyDocument"])
            LOG.info("Inline logging policy of %s allows %s", role_name, actions)

            assert not grants_action(actions, "logs:CreateLogGroup"), actions
            assert grants_action(actions, "logs:CreateLogStream"), actions
            assert grants_action(actions, "logs:PutLogEvents"), actions

            invoke_once(lambda_client, function_name)

            log_group_name = tf_output["cloudwatch_log_group_name"]["value"]
            events = []
            with timeout(LOG_EVENTS_TIMEOUT_SECONDS):
                while not events:
                    events = logs_client.filter_log_events(
                        logGroupName=log_group_name, limit=1
                    )["events"]
                    if not events:
                        LOG.info("Waiting for log events in %s", log_group_name)
                        time.sleep(5)
            LOG.info("First log event in %s: %s", log_group_name, events[0]["message"])

    def test_log_group_stays_deleted_after_destroy(
        self,
        test_module_dir: Path,
        fixtures_dir: Path,
        aws_provider_version: str,
        aws_region: str,
        lambda_client: BaseClient,
        logs_client: BaseClient,
        test_role_arn: str,
    ) -> None:
        """
        Test that ``/aws/lambda/<function_name>`` doesn't come back after ``terraform destroy``.

        Applies the module and invokes the function once, so a warm execution environment exists
        when the function is deleted. Destroys, then watches the log group name for 60 seconds.
        If the group reappears, the test deletes it, so the next apply isn't blocked by
        ``ResourceAlreadyExistsException``, and fails.

        The race is intermittent, so a pass doesn't prove the bug is gone; the test must pass
        reliably with the fix in place. It destroys even with ``--keep-after``, because the
        destroy is what it tests.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str aws_provider_version: AWS provider version to test
        :param str aws_region: AWS region to deploy to
        :param BaseClient lambda_client: Boto3 Lambda client fixture
        :param BaseClient logs_client: Boto3 CloudWatch Logs client fixture
        :param str test_role_arn: IAM role ARN for testing
        """
        function_name = "test-log-group-destroy"
        log_group_name = f"/aws/lambda/{function_name}"

        # A group an earlier failed run left behind would make the apply fail.
        leftover = find_log_group(logs_client, log_group_name)
        if leftover:
            LOG.warning(
                "Deleting %s left from an earlier run: %s", log_group_name, leftover
            )
            logs_client.delete_log_group(logGroupName=log_group_name)

        write_simple_lambda_config(
            test_module_dir,
            fixtures_dir,
            function_name,
            aws_provider_version,
            aws_region,
            test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=True,
            json_output=True,
        ) as tf_output:
            assert tf_output["cloudwatch_log_group_name"]["value"] == log_group_name
            invoke_once(lambda_client, function_name)

        destroyed_at = datetime.now(timezone.utc)
        LOG.info(
            "Destroy finished at %s, watching %s for %d seconds",
            destroyed_at.isoformat(),
            log_group_name,
            LOG_GROUP_WATCH_SECONDS,
        )
        deadline = time.monotonic() + LOG_GROUP_WATCH_SECONDS
        while True:
            reappeared = find_log_group(logs_client, log_group_name)
            if reappeared or time.monotonic() >= deadline:
                break
            time.sleep(LOG_GROUP_POLL_SECONDS)

        if reappeared:
            LOG.error("%s reappeared after destroy: %s", log_group_name, reappeared)
            logs_client.delete_log_group(logGroupName=log_group_name)

        assert reappeared is None, (
            f"{log_group_name} reappeared after terraform destroy finished at "
            f"{destroyed_at.isoformat()}: created at "
            f"{datetime.fromtimestamp(reappeared['creationTime'] / 1000, tz=timezone.utc).isoformat()}, "
            f"retentionInDays={reappeared.get('retentionInDays')}, "
            f"storedBytes={reappeared.get('storedBytes')}"
        )
