"""
Measure how far back a CloudWatch alarm reaches for real datapoints (evaluation range).

Creates short-lived alarms on a custom metric, one per gap:

- ``threshold`` alarms mirror the module's errors_threshold: metric math
  ``(errors / invocations) * 100 > 5``, period 60, 2 of 2, notBreaching. Each gets one
  breaching datapoint stamped now and another backdated by the gap, the same data a
  sparse function leaves when its second failure lands.
- ``single`` alarms mirror the pre-#33 errors_immediate: ``Errors > 0``, period 60,
  1 of 1, notBreaching. Each gets only the backdated datapoint.

An alarm goes to ALARM only if its backdated datapoint is still inside the evaluation
range, so the largest gap that fires is the range. All alarms are deleted at the end.

AWS doesn't document the range, and it decides whether an alarm can see a sparse
function's failures (issue #25) or an error reported late in a long invocation (#33).
Re-run this when that number matters; docs/monitoring.md quotes the last result.

Run it with credentials that may assume the tester role, overriding the defaults with
the same variables the Makefile uses::

    python -m tests.tools.probe_alarm_range
    TEST_REGION=eu-west-1 python -m tests.tools.probe_alarm_range

Takes about 7 minutes. Measured 2026-09-11 in us-west-2, period 60: datapoints up to
6 minutes old were used and anything older was ignored, for both alarm shapes.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import boto3
from botocore.client import BaseClient

ROLE_ARN = os.environ.get(
    "TEST_ROLE", "arn:aws:iam::303467602807:role/lambda-monitored-tester"
)
REGION = os.environ.get("TEST_REGION", "us-west-2")
NAMESPACE = "InfraHouse/AlarmRangeProbe"
GAPS_MINUTES = [2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16]
WATCH_SECONDS = 300


def cloudwatch_client() -> BaseClient:
    """
    Build a CloudWatch client that assumes the module's tester role.

    :return: Boto3 CloudWatch client in the test region
    """
    creds = boto3.client("sts").assume_role(
        RoleArn=ROLE_ARN, RoleSessionName="alarm-range-probe"
    )["Credentials"]
    session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
    return session.client("cloudwatch", region_name=REGION)


def metric_stat(name: str, probe: str) -> Dict:
    """
    Describe a 60-second Sum of one probe metric.

    :param str name: Metric name (Errors or Invocations)
    :param str probe: Probe dimension value, unique per alarm
    :return: MetricStat structure for PutMetricAlarm
    """
    return {
        "Metric": {
            "Namespace": NAMESPACE,
            "MetricName": name,
            "Dimensions": [{"Name": "Probe", "Value": probe}],
        },
        "Period": 60,
        "Stat": "Sum",
    }


def create_alarms(cloudwatch: BaseClient, prefix: str) -> List[str]:
    """
    Create one threshold-shaped and one single-period alarm per gap.

    :param BaseClient cloudwatch: CloudWatch client
    :param str prefix: Alarm and probe name prefix, unique per run
    :return: Names of the created alarms
    """
    names = []
    for gap in GAPS_MINUTES:
        threshold = f"{prefix}-threshold-{gap:02d}"
        cloudwatch.put_metric_alarm(
            AlarmName=threshold,
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
                    "MetricStat": metric_stat("Errors", threshold),
                    "ReturnData": False,
                },
                {
                    "Id": "invocations",
                    "MetricStat": metric_stat("Invocations", threshold),
                    "ReturnData": False,
                },
            ],
        )
        single = f"{prefix}-single-{gap:02d}"
        cloudwatch.put_metric_alarm(
            AlarmName=single,
            ComparisonOperator="GreaterThanThreshold",
            EvaluationPeriods=1,
            Threshold=0.0,
            TreatMissingData="notBreaching",
            Namespace=NAMESPACE,
            MetricName="Errors",
            Dimensions=[{"Name": "Probe", "Value": single}],
            Period=60,
            Statistic="Sum",
        )
        names += [threshold, single]
    return names


def feed_datapoints(cloudwatch: BaseClient, prefix: str, now: datetime) -> None:
    """
    Publish the backdated (and, for threshold alarms, current) breaching datapoints.

    :param BaseClient cloudwatch: CloudWatch client
    :param str prefix: Alarm and probe name prefix used by create_alarms()
    :param datetime now: Current minute, the timestamp of the most recent datapoint
    """
    for gap in GAPS_MINUTES:
        backdated = now - timedelta(minutes=gap)
        threshold = f"{prefix}-threshold-{gap:02d}"
        single = f"{prefix}-single-{gap:02d}"
        data = [
            {
                "MetricName": name,
                "Dimensions": [{"Name": "Probe", "Value": threshold}],
                "Timestamp": stamp,
                "Value": 1.0,
                "Unit": "Count",
            }
            for stamp in (backdated, now)
            for name in ("Errors", "Invocations")
        ]
        data.append(
            {
                "MetricName": "Errors",
                "Dimensions": [{"Name": "Probe", "Value": single}],
                "Timestamp": backdated,
                "Value": 1.0,
                "Unit": "Count",
            }
        )
        cloudwatch.put_metric_data(Namespace=NAMESPACE, MetricData=data)


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
    """Run the probe and print, per gap, whether each alarm shape reached back that far."""
    cloudwatch = cloudwatch_client()
    prefix = f"alarm-range-probe-{int(time.time())}"
    names = create_alarms(cloudwatch, prefix)
    try:
        print(f"Created {len(names)} alarms; letting them settle for 90 s")
        time.sleep(90)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        feed_at = datetime.now(timezone.utc)
        feed_datapoints(cloudwatch, prefix, now)
        print(
            f"Fed datapoints at {feed_at:%H:%M:%S} UTC; watching for {WATCH_SECONDS} s"
        )
        results: Dict[str, Optional[datetime]] = {name: None for name in names}
        deadline = time.time() + WATCH_SECONDS
        while time.time() < deadline and not all(results.values()):
            time.sleep(20)
            for name in names:
                if results[name] is None:
                    results[name] = fired_at(cloudwatch, name, feed_at)
        print(f"\n{'gap (min)':>9}  {'threshold, 2 of 2':<22}  {'single, 1 of 1':<22}")
        for gap in GAPS_MINUTES:
            row = []
            for shape in ("threshold", "single"):
                stamp = results[f"{prefix}-{shape}-{gap:02d}"]
                row.append(
                    f"ALARM +{(stamp - feed_at).seconds}s" if stamp else "stayed OK"
                )
            print(f"{gap:>9}  {row[0]:<22}  {row[1]:<22}")
    finally:
        cloudwatch.delete_alarms(AlarmNames=names)
        print(f"\nDeleted {len(names)} alarms")


if __name__ == "__main__":
    main()
