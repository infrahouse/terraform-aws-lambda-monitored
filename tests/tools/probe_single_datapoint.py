"""
Does one breaching datapoint trip a 2-of-2 error-rate alarm when its neighbours are missing?

Four alarms shaped like the module's errors_threshold (2 of 2, notBreaching), fed backdated
custom metrics, differing only in period and in how many periods breach. Run it when a
threshold alarm fires or stays quiet for reasons that don't match datapoints_to_alarm.

Measured 2026-09-11 in us-west-2: datapoints_to_alarm is honoured at both periods. Only the
pair cases fired (60 s adjacent +28 s, 540 s nine minutes apart +49 s, counting "2 out of
the last 2 datapoints"), and the 540 s case shows the window still counting a datapoint
18 minutes old. Both single cases stayed OK.

That result is what identified the real cause of a green #25 test run firing one minute
after its first failure: CloudWatch metrics outlive terraform destroy, so a rerun under the
same function name was judged partly on the previous run's errors. Tests that assert alarm
state now take a unique function name.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import boto3
from botocore.client import BaseClient

ROLE_ARN = os.environ.get(
    "TEST_ROLE", "arn:aws:iam::303467602807:role/lambda-monitored-tester"
)
REGION = os.environ.get("TEST_REGION", "us-west-2")
NAMESPACE = "InfraHouse/AlarmSingleDatapointProbe"
WATCH_SECONDS = 240

# label -> (period seconds, minutes back of each breaching datapoint)
CASES = {
    "p60-single": (60, [1]),
    "p60-pair-adjacent": (60, [1, 2]),
    "p540-single": (540, [1]),
    "p540-pair-9min-apart": (540, [1, 10]),
}


def cloudwatch_client() -> BaseClient:
    """
    Build a CloudWatch client that assumes the module's tester role.

    :return: Boto3 CloudWatch client in the test region
    """
    creds = boto3.client("sts").assume_role(
        RoleArn=ROLE_ARN, RoleSessionName="single-datapoint-probe"
    )["Credentials"]
    session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
    return session.client("cloudwatch", region_name=REGION)


def create_alarm(cloudwatch: BaseClient, name: str, period: int) -> None:
    """
    Create one alarm shaped like errors_threshold: (errors / invocations) * 100 > 5, 2 of 2.

    :param BaseClient cloudwatch: CloudWatch client
    :param str name: Alarm name, also the probe dimension value
    :param int period: Period in seconds
    """
    dimensions = [{"Name": "Probe", "Value": name}]
    cloudwatch.put_metric_alarm(
        AlarmName=name,
        ComparisonOperator="GreaterThanThreshold",
        EvaluationPeriods=2,
        DatapointsToAlarm=2,
        Threshold=5.0,
        TreatMissingData="notBreaching",
        Metrics=[
            {
                "Id": "error_rate",
                "Expression": "(errors / invocations) * 100",
                "ReturnData": True,
            },
            {
                "Id": "errors",
                "MetricStat": {
                    "Metric": {
                        "Namespace": NAMESPACE,
                        "MetricName": "Errors",
                        "Dimensions": dimensions,
                    },
                    "Period": period,
                    "Stat": "Sum",
                },
                "ReturnData": False,
            },
            {
                "Id": "invocations",
                "MetricStat": {
                    "Metric": {
                        "Namespace": NAMESPACE,
                        "MetricName": "Invocations",
                        "Dimensions": dimensions,
                    },
                    "Period": period,
                    "Stat": "Sum",
                },
                "ReturnData": False,
            },
        ],
    )


def fired_at(cloudwatch: BaseClient, name: str, since: datetime) -> Optional[datetime]:
    """
    Return when an alarm first entered ALARM since a moment, per its history.

    :param BaseClient cloudwatch: CloudWatch client
    :param str name: Alarm name
    :param datetime since: Ignore state changes before this moment
    :return: Timestamp of the first ALARM transition, or None
    """
    items = cloudwatch.describe_alarm_history(
        AlarmName=name, HistoryItemType="StateUpdate", StartDate=since
    )["AlarmHistoryItems"]
    stamps = [
        i["Timestamp"]
        for i in items
        if json.loads(i["HistoryData"])["newState"]["stateValue"] == "ALARM"
    ]
    return min(stamps) if stamps else None


def main() -> None:
    """Feed each case its datapoints, then report which alarms fired and why CloudWatch says so."""
    cloudwatch = cloudwatch_client()
    prefix = f"single-dp-probe-{int(time.time())}"
    names = {label: f"{prefix}-{label}" for label in CASES}
    for label, (period, _) in CASES.items():
        create_alarm(cloudwatch, names[label], period)
    try:
        print(f"Created {len(names)} alarms; letting them settle for 90 s")
        time.sleep(90)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        feed_at = datetime.now(timezone.utc)
        for label, case in CASES.items():
            minutes_back = case[1]
            data = [
                {
                    "MetricName": metric,
                    "Dimensions": [{"Name": "Probe", "Value": names[label]}],
                    "Timestamp": now - timedelta(minutes=back),
                    "Value": 1.0,
                    "Unit": "Count",
                }
                for back in minutes_back
                for metric in ("Errors", "Invocations")
            ]
            cloudwatch.put_metric_data(Namespace=NAMESPACE, MetricData=data)
        print(
            f"Fed datapoints at {feed_at:%H:%M:%S} UTC; watching for {WATCH_SECONDS} s"
        )
        results: Dict[str, Optional[datetime]] = {label: None for label in CASES}
        deadline = time.time() + WATCH_SECONDS
        while time.time() < deadline and not all(results.values()):
            time.sleep(20)
            for label in CASES:
                if results[label] is None:
                    results[label] = fired_at(cloudwatch, names[label], feed_at)
        print(
            f"\n{'case':<24}  {'breaching periods':<18}  {'result':<18}  state reason"
        )
        for label, (_, minutes_back) in CASES.items():
            alarm = cloudwatch.describe_alarms(AlarmNames=[names[label]])[
                "MetricAlarms"
            ][0]
            stamp = results[label]
            outcome = f"ALARM +{(stamp - feed_at).seconds}s" if stamp else "stayed OK"
            print(
                f"{label:<24}  {len(minutes_back):<18}  {outcome:<18}  {alarm['StateReason']}"
            )
    finally:
        cloudwatch.delete_alarms(AlarmNames=list(names.values()))
        print(f"\nDeleted {len(names)} alarms")


if __name__ == "__main__":
    main()
