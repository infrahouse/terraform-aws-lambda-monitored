# Examples

Each example below maps to a runnable directory under
[`examples/`](https://github.com/infrahouse/terraform-aws-lambda-monitored/tree/main/examples)
in the repo. They're also used as the module's integration test fixtures, so they're guaranteed to apply cleanly.

## Immediate alerts

**When to use:** low-traffic or business-critical functions where any error is a page.

[`examples/immediate-alerts`](https://github.com/infrahouse/terraform-aws-lambda-monitored/tree/main/examples/immediate-alerts)

```hcl
module "critical_processor" {
  source  = "registry.infrahouse.com/infrahouse/lambda-monitored/aws"
  version = "1.1.0"

  function_name     = "critical-processor"
  lambda_source_dir = "${path.module}/lambda"

  alert_strategy = "immediate"  # default
  alarm_emails   = ["oncall@example.com"]

  cloudwatch_log_retention_days = 30
  enable_throttle_alarms        = true
}
```

Any single error triggers the `errors_immediate` alarm and fans out through SNS.

## Threshold alerts

**When to use:** high-volume functions where occasional failures are expected and you only want to hear about
sustained elevated error rates.

[`examples/threshold-alerts`](https://github.com/infrahouse/terraform-aws-lambda-monitored/tree/main/examples/threshold-alerts)

```hcl
module "data_ingestion" {
  source  = "registry.infrahouse.com/infrahouse/lambda-monitored/aws"
  version = "1.1.0"

  function_name     = "data-ingestion"
  lambda_source_dir = "${path.module}/lambda"

  alert_strategy                 = "threshold"
  error_rate_threshold           = 5.0  # fire above 5% errors
  error_rate_evaluation_periods  = 2    # over two 5-min windows
  error_rate_datapoints_to_alarm = 2    # both windows must breach

  alarm_emails = ["data-oncall@example.com"]
}
```

The `errors_threshold` alarm uses CloudWatch metric math: `(errors / invocations) * 100`. With `invocations = 0`
the metric is treated as missing, not as a breach — idle functions won't page you.

## Custom permissions

**When to use:** the Lambda needs to read from a bucket, write to a DynamoDB table, call another service, etc.

[`examples/custom-permissions`](https://github.com/infrahouse/terraform-aws-lambda-monitored/tree/main/examples/custom-permissions)

```hcl
resource "aws_iam_policy" "read_reports_bucket" {
  name   = "lambda-read-reports-bucket"
  policy = data.aws_iam_policy_document.reports.json
}

module "report_generator" {
  source  = "registry.infrahouse.com/infrahouse/lambda-monitored/aws"
  version = "1.1.0"

  function_name     = "report-generator"
  lambda_source_dir = "${path.module}/lambda"

  additional_iam_policy_arns = [
    aws_iam_policy.read_reports_bucket.arn,
    "arn:aws:iam::aws:policy/service-role/AWSLambdaDynamoDBExecutionRole",
  ]

  alarm_emails = ["oncall@example.com"]
}
```

The module's baseline logging policy stays in place — your additional policies are *added*, not substituted.

## Fan-out to PagerDuty or Slack

**When to use:** you already have an external incident channel and don't want to duplicate subscribers.

```hcl
module "payment_worker" {
  source  = "registry.infrahouse.com/infrahouse/lambda-monitored/aws"
  version = "1.1.0"

  function_name     = "payment-worker"
  lambda_source_dir = "${path.module}/lambda"

  alarm_emails = ["payments-oncall@example.com"]

  alarm_topic_arns = [
    aws_sns_topic.pagerduty_integration.arn,
    aws_sns_topic.slack_alerts.arn,
  ]
}
```

Every alarm action writes to **both** the module's internal topic and every ARN in `alarm_topic_arns`. See
[Architecture → Alert flow](architecture.md#alert-flow) for the exact mechanism.

## VPC-attached function

**When to use:** the Lambda needs to reach private resources like RDS, ElastiCache, or internal services behind
PrivateLink.

```hcl
module "database_migrator" {
  source  = "registry.infrahouse.com/infrahouse/lambda-monitored/aws"
  version = "1.1.0"

  function_name     = "database-migrator"
  lambda_source_dir = "${path.module}/lambda"

  lambda_subnet_ids         = module.vpc.private_subnet_ids
  lambda_security_group_ids = [aws_security_group.db_clients.id]

  alarm_emails = ["platform@example.com"]
}
```

The private subnets need a NAT gateway (or VPC endpoints) for outbound traffic. The module automatically grants
ENI permissions **scoped to only the specified subnets** — it refuses to hand out broad `ec2:*NetworkInterface*`.

## Duration and memory alarms

**When to use:** the function has tight latency SLOs or you want to catch memory leaks before they start throttling.

```hcl
module "latency_critical" {
  source  = "registry.infrahouse.com/infrahouse/lambda-monitored/aws"
  version = "1.1.0"

  function_name     = "latency-critical"
  lambda_source_dir = "${path.module}/lambda"

  timeout     = 30
  memory_size = 1024

  duration_threshold_percent           = 80  # alarm at 24s (80% of 30s timeout)
  memory_utilization_threshold_percent = 85  # enables Lambda Insights

  alarm_emails = ["perf@example.com"]
}
```

Setting `memory_utilization_threshold_percent` attaches the Lambda Insights extension layer and grants the
matching managed policy — this adds a small per-invocation cost. Leaving it `null` disables both.

## arm64 with Python 3.13

**When to use:** cheaper compute, if your dependencies have arm64 wheels.

```hcl
module "thumbnailer" {
  source  = "registry.infrahouse.com/infrahouse/lambda-monitored/aws"
  version = "1.1.0"

  function_name     = "thumbnailer"
  lambda_source_dir = "${path.module}/lambda"

  architecture   = "arm64"
  python_version = "python3.13"
  memory_size    = 512

  alarm_emails = ["media@example.com"]
}
```

Pillow, numpy, and most popular libraries ship manylinux2014 aarch64 wheels. If pip falls back to a source dist,
the `--only-binary=:all:` flag will fail the build rather than silently shipping a broken artifact.
