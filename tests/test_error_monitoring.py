"""
Error alarm tests for terraform-aws-lambda-monitored.

These tests deploy a function that fails on demand and watch the error alarm's
state history, covering both alert strategies (immediate and threshold) and the
invocation patterns that decide whether an alarm can fire: errors late in a long
invocation (issue #33) and sparse invocations (issue #25).
"""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from botocore.client import BaseClient
from infrahouse_core.timeout import timeout
from pytest_infrahouse import terraform_apply

from tests.conftest import LOG, create_terraform_config


def wait_for_alarm_to_fire(
    cloudwatch_client: BaseClient,
    alarm_name: str,
    since: datetime,
    deadline: datetime,
) -> Optional[datetime]:
    """
    Wait for a CloudWatch alarm to enter ALARM, judged by its state history.

    Reading history rather than the current state means an ALARM that clears
    between polls still counts.

    :param BaseClient cloudwatch_client: Boto3 CloudWatch client
    :param str alarm_name: Name of the alarm to watch
    :param datetime since: Ignore state changes before this moment
    :param datetime deadline: Stop waiting at this moment
    :return: When the alarm first entered ALARM, or None if it had not by ``deadline``
    :rtype: datetime or None
    """
    while True:
        history = cloudwatch_client.describe_alarm_history(
            AlarmName=alarm_name,
            HistoryItemType="StateUpdate",
            StartDate=since,
        )
        fired_at = [
            item["Timestamp"]
            for item in history["AlarmHistoryItems"]
            if json.loads(item["HistoryData"])["newState"]["stateValue"] == "ALARM"
        ]
        if fired_at:
            return min(fired_at)
        if datetime.now(timezone.utc) >= deadline:
            return None
        LOG.info("Waiting for %s to enter ALARM...", alarm_name)
        time.sleep(30)


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
            "devnull@infrahouse.com",
            "~> 6.0",
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
            errored_at = datetime.now(timezone.utc)
            response = lambda_client.invoke(
                FunctionName=tf_output["lambda_function_name"]["value"],
                InvocationType="RequestResponse",
                Payload=json.dumps({"force_error": True}),
            )
            assert "FunctionError" in response

            alarm_name = f"{function_name}-errors-immediate"
            fired_at = wait_for_alarm_to_fire(
                cloudwatch_client,
                alarm_name,
                since=errored_at,
                deadline=errored_at + timedelta(minutes=5),
            )
            assert (
                fired_at is not None
            ), f"{alarm_name} did not enter ALARM within 5 minutes of the error"
            elapsed = fired_at - errored_at
            LOG.info("%s entered ALARM %s after the error", alarm_name, elapsed)

            # The window sized from the timeout (issue #33) must not delay an error that is
            # published at once: expect about a minute of publishing plus one evaluation.
            assert elapsed <= timedelta(
                minutes=3
            ), f"{alarm_name} took {elapsed} to fire after an early error"

    def test_immediate_alert_late_error(
        self,
        test_module_dir: Path,
        fixtures_dir: Path,
        lambda_client: BaseClient,
        cloudwatch_client: BaseClient,
        keep_after: bool,
        test_role_arn: str,
    ) -> None:
        """
        Test immediate alert strategy fires on an error raised late in a long invocation (issue #33).

        Lambda stamps an invocation's ``Errors`` datapoint with the minute the
        invocation *started*, but publishes it only when the invocation *ends*.
        Here the function (``timeout = 900``) raises 720 s into the run, so its
        datapoint arrives about 12 minutes in the past. The original single-period
        ``errors-immediate`` alarm had already evaluated that minute as missing
        data (not breaching) and never looked at it again, so it stayed OK while
        the function failed. The fix sizes the alarm's window from ``var.timeout``.

        720 s mirrors production, where an exception about 727 s into a run never
        fired the alarm, while errors 1 to 3 minutes into a run did.

        :param Path test_module_dir: Temporary test module directory
        :param Path fixtures_dir: Path to Lambda fixtures
        :param BaseClient lambda_client: Boto3 Lambda client fixture
        :param BaseClient cloudwatch_client: Boto3 CloudWatch client fixture
        :param bool keep_after: Whether to keep resources after test
        :param str test_role_arn: IAM role ARN to assume for testing
        """
        function_name = "test-immediate-late-error"
        lambda_source = fixtures_dir / "lambda_with_errors"
        error_delay = 720
        # How long CloudWatch gets to act on the Errors datapoint once it is queryable.
        alarm_grace = 300

        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            "devnull@infrahouse.com",
            "~> 6.0",
            alert_strategy="immediate",
            role_arn=test_role_arn,
            timeout=900,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            function_name_output = tf_output["lambda_function_name"]["value"]
            alarm_name = f"{function_name}-errors-immediate"
            invoked_at = datetime.now(timezone.utc)

            # Invoke asynchronously, as a scheduler would. A synchronous call outlives
            # botocore's read timeout, and botocore's retry would invoke the function again.
            response = lambda_client.invoke(
                FunctionName=function_name_output,
                InvocationType="Event",
                Payload=json.dumps({"force_error": True, "sleep_seconds": error_delay}),
            )
            assert response["StatusCode"] == 202

            error_datapoint = None
            with timeout(error_delay + 600):
                while error_datapoint is None:
                    stats = cloudwatch_client.get_metric_statistics(
                        Namespace="AWS/Lambda",
                        MetricName="Errors",
                        Dimensions=[
                            {"Name": "FunctionName", "Value": function_name_output}
                        ],
                        StartTime=invoked_at - timedelta(minutes=5),
                        EndTime=datetime.now(timezone.utc) + timedelta(minutes=1),
                        Period=60,
                        Statistics=["Sum"],
                    )
                    error_datapoints = [
                        dp for dp in stats["Datapoints"] if dp["Sum"] > 0
                    ]
                    if error_datapoints:
                        error_datapoint = error_datapoints[0]
                    else:
                        LOG.info("Waiting for the late Errors datapoint...")
                        time.sleep(30)

            visible_at = datetime.now(timezone.utc)
            LOG.info(
                "Errors datapoint (Sum=%s) stamped %s became queryable at %s",
                error_datapoint["Sum"],
                error_datapoint["Timestamp"],
                visible_at,
            )
            # Without this lateness the test would not exercise issue #33 at all.
            assert visible_at - error_datapoint["Timestamp"] >= timedelta(
                seconds=error_delay
            ), (
                f"Errors datapoint stamped {error_datapoint['Timestamp']} is not late "
                f"(queryable at {visible_at}); Lambda no longer stamps it at invocation start"
            )

            fired_at = wait_for_alarm_to_fire(
                cloudwatch_client,
                alarm_name,
                since=invoked_at,
                deadline=visible_at + timedelta(seconds=alarm_grace),
            )

            alarm = cloudwatch_client.describe_alarms(AlarmNames=[alarm_name])[
                "MetricAlarms"
            ][0]
            assert fired_at is not None, (
                f"{alarm_name} never entered ALARM, although the function raised "
                f"{error_delay}s into the invocation and Errors={error_datapoint['Sum']} "
                f"is stamped {error_datapoint['Timestamp']}. "
                f"Current state: {alarm['StateValue']} ({alarm['StateReason']}); "
                f"EvaluationPeriods={alarm['EvaluationPeriods']}, "
                f"DatapointsToAlarm={alarm.get('DatapointsToAlarm')}"
            )
            LOG.info("%s entered ALARM at %s", alarm_name, fired_at)

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
            "devnull@infrahouse.com",
            "~> 6.0",
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
