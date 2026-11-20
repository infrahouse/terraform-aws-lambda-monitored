"""
Log group lifecycle tests for terraform-aws-lambda-monitored (issue #26).

After ``terraform destroy``, ``/aws/lambda/<function_name>`` could reappear seconds later,
created outside Terraform without a retention policy, and the next apply then failed with
``ResourceAlreadyExistsException``. These tests check the two parts of the fix: the execution
role can't create its log group, whatever other policies it has, and the group stays deleted
after destroy. The destroy-time wait between the function and its log group is an input, whose
validation is checked at plan.
"""

import json
import time
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from botocore.client import BaseClient
from infrahouse_core.timeout import timeout
from pytest_infrahouse import terraform_apply

from tests.conftest import LOG, create_terraform_config
from tests.test_module import terraform_plan, variable_validation_errors

# After terraform destroy, how long to watch for the function's log group to come back.
# In the issue the orphan appeared 7 seconds after the function was deleted.
LOG_GROUP_WATCH_SECONDS = 60
LOG_GROUP_POLL_SECONDS = 5

# How long to wait for an invocation's log events to become readable.
LOG_EVENTS_TIMEOUT_SECONDS = 180

# The destroy test deletes the function while an invocation of lambda_logs_continuously is still
# running: the invocation is asked to log for this long, well past the time destroy needs to
# reach the function, and the function's timeout leaves room for it.
LONG_INVOCATION_SECONDS = 90
LONG_INVOCATION_TIMEOUT = 120

# How long to retry the IAM policy simulation while a role's new policies propagate.
IAM_SETTLE_SECONDS = 120

# Module inputs that change what the execution role may do. With the memory alarm on, the module
# attaches CloudWatchLambdaInsightsExecutionRolePolicy, which allows logs:CreateLogGroup on "*".
MEMORY_ALARM_INPUTS = {"memory_utilization_threshold_percent": 80}


def allowed_actions(
    policy_document: Dict[str, Any], effect: str = "Allow"
) -> List[str]:
    """
    List the actions of an IAM policy document's statements with the given effect.

    :param dict policy_document: Policy document as boto3 returns it, already URL-decoded
    :param str effect: ``Allow`` or ``Deny``
    :return: Every action of every statement with that effect, as written in the policy
    :rtype: list
    """
    statements = policy_document["Statement"]
    if isinstance(statements, dict):
        statements = [statements]

    actions = []
    for statement in statements:
        if statement["Effect"] != effect:
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


def wait_for_log_event(
    logs_client: BaseClient, log_group_name: str, filter_pattern: str = ""
) -> Dict[str, Any]:
    """
    Wait until a log event matching the pattern is readable in the log group.

    :param BaseClient logs_client: Boto3 CloudWatch Logs client
    :param str log_group_name: Name of the log group
    :param str filter_pattern: CloudWatch Logs filter pattern; empty matches any event
    :return: The first matching event as ``filter_log_events`` returns it
    :rtype: dict
    :raise TimeoutError: If no such event shows up within ``LOG_EVENTS_TIMEOUT_SECONDS``
    """
    with timeout(LOG_EVENTS_TIMEOUT_SECONDS):
        while True:
            events = logs_client.filter_log_events(
                logGroupName=log_group_name, filterPattern=filter_pattern, limit=1
            )["events"]
            if events:
                return events[0]
            LOG.info("Waiting for log events in %s", log_group_name)
            time.sleep(5)


def simulate_role(
    iam_client: BaseClient,
    role_arn: str,
    expected: Dict[Tuple[str, str], str],
) -> Dict[Tuple[str, str], str]:
    """
    Ask IAM what the role may do, retrying until the answers match or IAM_SETTLE_SECONDS pass.

    ``simulate_principal_policy`` evaluates every policy on the role, inline and attached, so it
    gives the role's effective permission rather than what one policy document says. A new role's
    policies can take a while to show up in it, hence the retries.

    :param BaseClient iam_client: Boto3 IAM client
    :param str role_arn: ARN of the role to simulate
    :param dict expected: ``(action, resource ARN)`` to the expected ``EvalDecision``
        (``allowed``, ``explicitDeny`` or ``implicitDeny``)
    :return: ``(action, resource ARN)`` to the decision IAM gave on the last try
    :rtype: dict
    """
    deadline = time.monotonic() + IAM_SETTLE_SECONDS
    while True:
        decisions = {}
        for action, resource in expected:
            response = iam_client.simulate_principal_policy(
                PolicySourceArn=role_arn, ActionNames=[action], ResourceArns=[resource]
            )
            decisions[(action, resource)] = response["EvaluationResults"][0][
                "EvalDecision"
            ]
        if decisions == expected or time.monotonic() >= deadline:
            return decisions
        LOG.info("IAM simulation not settled yet: %s", decisions)
        time.sleep(10)


def write_lambda_config(
    test_module_dir: Path,
    fixtures_dir: Path,
    function_name: str,
    aws_provider_version: str,
    aws_region: str,
    test_role_arn: str,
    fixture: str = "simple_lambda",
    function_timeout: int = None,
    log_group_destroy_delay_seconds: float = None,
    memory_utilization_threshold_percent: int = None,
) -> None:
    """
    Write a root module that deploys a fixture with the module's defaults.

    :param Path test_module_dir: Directory to write the root module to
    :param Path fixtures_dir: Path to Lambda fixtures
    :param str function_name: Name of the Lambda function
    :param str aws_provider_version: AWS provider version constraint
    :param str aws_region: AWS region to deploy to
    :param str test_role_arn: IAM role ARN Terraform assumes
    :param str fixture: Directory under ``fixtures_dir`` with the function's source
    :param int function_timeout: Function timeout in seconds (optional; module default when None)
    :param float log_group_destroy_delay_seconds: Value for the module input of that name
        (optional; when None the argument is omitted and the module uses its default)
    :param int memory_utilization_threshold_percent: Value for the module input of that name
        (optional; when None the memory alarm and Lambda Insights stay off)
    """
    create_terraform_config(
        test_module_dir,
        fixtures_dir / fixture,
        function_name,
        "devnull@infrahouse.com",
        aws_provider_version,
        aws_region=aws_region,
        role_arn=test_role_arn,
        timeout=function_timeout,
        log_group_destroy_delay_seconds=log_group_destroy_delay_seconds,
        memory_utilization_threshold_percent=memory_utilization_threshold_percent,
    )


class TestLogGroup:
    """The function's log group: who may create it, and that it stays deleted after destroy."""

    @pytest.mark.parametrize(
        "name_suffix, module_inputs",
        [("", {}), ("-insights", MEMORY_ALARM_INPUTS)],
        ids=["default", "memory-alarm"],
    )
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
        name_suffix: str,
        module_inputs: Dict[str, Any],
    ) -> None:
        """
        Test that the execution role can't create its log group, yet still logs to it.

        The module creates ``/aws/lambda/<function_name>`` before the function, so the role never
        needs ``logs:CreateLogGroup``. Without it, a late write after ``terraform destroy`` can't
        bring the group back.

        The inline logging policy must not allow ``logs:CreateLogGroup`` and must deny it on the
        module's group. Then the IAM policy simulator, which evaluates every policy on the role,
        must answer ``explicitDeny`` for it, also with the memory alarm on: that attaches
        ``CloudWatchLambdaInsightsExecutionRolePolicy``, which allows ``logs:CreateLogGroup`` on
        ``*``. Creating streams and writing events must stay ``allowed``, and an invocation's log
        event must reach the module's group.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str aws_provider_version: AWS provider version to test
        :param str aws_region: AWS region to deploy to
        :param BaseClient iam_client: Boto3 IAM client fixture
        :param BaseClient lambda_client: Boto3 Lambda client fixture
        :param BaseClient logs_client: Boto3 CloudWatch Logs client fixture
        :param bool keep_after: Whether to keep resources after test
        :param str test_role_arn: IAM role ARN for testing
        :param str name_suffix: Appended to the function name, so the cases don't share names
        :param dict module_inputs: Extra module inputs for the case
        """
        function_name = f"test-logging-policy{name_suffix}"
        write_lambda_config(
            test_module_dir,
            fixtures_dir,
            function_name,
            aws_provider_version,
            aws_region,
            test_role_arn,
            **module_inputs,
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
            denied = allowed_actions(policy["PolicyDocument"], effect="Deny")
            LOG.info(
                "Inline logging policy of %s allows %s, denies %s",
                role_name,
                actions,
                denied,
            )

            group_arn = tf_output["cloudwatch_log_group_arn"]["value"]
            stream_arn = f"{group_arn}:log-stream:simulated"
            expected = {
                ("logs:CreateLogGroup", group_arn): "explicitDeny",
                ("logs:CreateLogGroup", f"{group_arn}:*"): "explicitDeny",
                ("logs:CreateLogStream", stream_arn): "allowed",
                ("logs:PutLogEvents", stream_arn): "allowed",
            }
            decisions = simulate_role(
                iam_client, tf_output["lambda_role_arn"]["value"], expected
            )
            LOG.info("IAM simulation for %s: %s", role_name, decisions)
            assert decisions == expected

            assert not grants_action(actions, "logs:CreateLogGroup"), actions
            assert grants_action(actions, "logs:CreateLogStream"), actions
            assert grants_action(actions, "logs:PutLogEvents"), actions
            assert grants_action(denied, "logs:CreateLogGroup"), denied

            invoke_once(lambda_client, function_name)

            log_group_name = tf_output["cloudwatch_log_group_name"]["value"]
            event = wait_for_log_event(logs_client, log_group_name)
            LOG.info("First log event in %s: %s", log_group_name, event["message"])

    @pytest.mark.parametrize(
        "name_suffix, module_inputs",
        [
            ("", {}),
            # Lambda Insights' policy allows logs:CreateLogGroup on "*" and there is no wait,
            # so only the logging policy's deny keeps the group from coming back.
            (
                "-insights",
                {**MEMORY_ALARM_INPUTS, "log_group_destroy_delay_seconds": 0},
            ),
        ],
        ids=["default", "memory-alarm-no-wait"],
    )
    def test_log_group_stays_deleted_after_destroy(
        self,
        test_module_dir: Path,
        fixtures_dir: Path,
        aws_provider_version: str,
        aws_region: str,
        lambda_client: BaseClient,
        logs_client: BaseClient,
        test_role_arn: str,
        name_suffix: str,
        module_inputs: Dict[str, Any],
    ) -> None:
        """
        Test that ``/aws/lambda/<function_name>`` doesn't come back after ``terraform destroy``.

        Starts an invocation of ``lambda_logs_continuously`` that logs for 90 seconds and destroys
        while it runs. Deleting the function stops the invocation, and Lambda flushes the lines it
        still holds about half a second later. Without the fix that flush lands after Terraform
        deleted the group and, through the role's ``logs:CreateLogGroup``, creates it again: the
        late write the issue saw by chance happens on every run. Then watches the log group name
        for 60 seconds. If the group reappears, the test deletes it, so the next apply isn't
        blocked by ``ResourceAlreadyExistsException``, and fails.

        Lambda's teardown timing isn't documented, so a pass doesn't prove no late write can ever
        recreate the group; the test must pass reliably with the fix in place. It destroys even
        with ``--keep-after``, because the destroy is what it tests.

        The ``memory-alarm-no-wait`` case turns on Lambda Insights, whose managed policy allows
        ``logs:CreateLogGroup`` on ``*``, and sets the wait to 0, so only the deny in the module's
        logging policy stands between the late flush and a new group.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str aws_provider_version: AWS provider version to test
        :param str aws_region: AWS region to deploy to
        :param BaseClient lambda_client: Boto3 Lambda client fixture
        :param BaseClient logs_client: Boto3 CloudWatch Logs client fixture
        :param str test_role_arn: IAM role ARN for testing
        :param str name_suffix: Appended to the function name, so the cases don't share names
        :param dict module_inputs: Extra module inputs for the case
        """
        function_name = f"test-log-group-destroy{name_suffix}"
        log_group_name = f"/aws/lambda/{function_name}"

        # A group an earlier failed run left behind would make the apply fail.
        leftover = find_log_group(logs_client, log_group_name)
        if leftover:
            LOG.warning(
                "Deleting %s left from an earlier run: %s", log_group_name, leftover
            )
            logs_client.delete_log_group(logGroupName=log_group_name)

        write_lambda_config(
            test_module_dir,
            fixtures_dir,
            function_name,
            aws_provider_version,
            aws_region,
            test_role_arn,
            fixture="lambda_logs_continuously",
            function_timeout=LONG_INVOCATION_TIMEOUT,
            **module_inputs,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=True,
            json_output=True,
        ) as tf_output:
            assert tf_output["cloudwatch_log_group_name"]["value"] == log_group_name

            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="Event",
                Payload=json.dumps({"seconds": LONG_INVOCATION_SECONDS}),
            )
            assert response["StatusCode"] == 202, response

            # Its first line proves the invocation is running; destroy then deletes the function under it.
            event = wait_for_log_event(logs_client, log_group_name, '"tick"')
            LOG.info("Invocation is logging (%s), destroying", event["message"].strip())

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

    @pytest.mark.parametrize("delay", [0, 10], ids=["zero", "ten"])
    def test_log_group_destroy_delay_validation_accepts(
        self,
        test_module_dir: Path,
        fixtures_dir: Path,
        aws_provider_version: str,
        aws_region: str,
        test_role_arn: str,
        delay: float,
    ) -> None:
        """
        Test that terraform plan accepts 0, which turns the wait off, and the default of 10 seconds.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str aws_provider_version: AWS provider version to test
        :param str aws_region: AWS region to plan against
        :param str test_role_arn: IAM role ARN for testing
        :param float delay: Value under test
        """
        write_lambda_config(
            test_module_dir,
            fixtures_dir,
            "test-log-group-delay-plan",
            aws_provider_version,
            aws_region,
            test_role_arn,
            log_group_destroy_delay_seconds=delay,
        )

        plan = terraform_plan(test_module_dir)

        assert plan.returncode == 0, plan.stdout + plan.stderr
        assert not variable_validation_errors(
            plan.stdout, "log_group_destroy_delay_seconds"
        )

    @pytest.mark.parametrize("delay", [-1, 1.5], ids=["negative", "fraction"])
    def test_log_group_destroy_delay_validation_rejects(
        self,
        test_module_dir: Path,
        fixtures_dir: Path,
        aws_provider_version: str,
        aws_region: str,
        test_role_arn: str,
        delay: float,
    ) -> None:
        """
        Test that terraform plan fails on the module's rule for log_group_destroy_delay_seconds.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param str aws_provider_version: AWS provider version to test
        :param str aws_region: AWS region to plan against
        :param str test_role_arn: IAM role ARN for testing
        :param float delay: Value under test
        """
        write_lambda_config(
            test_module_dir,
            fixtures_dir,
            "test-log-group-delay-plan",
            aws_provider_version,
            aws_region,
            test_role_arn,
            log_group_destroy_delay_seconds=delay,
        )

        plan = terraform_plan(test_module_dir)

        assert plan.returncode != 0, plan.stdout
        assert variable_validation_errors(
            plan.stdout, "log_group_destroy_delay_seconds"
        ), plan.stdout
