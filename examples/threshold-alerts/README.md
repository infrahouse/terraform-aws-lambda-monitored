# Threshold Alerts Example

This example demonstrates using the `terraform-aws-lambda-monitored` module with the **threshold alert strategy** for fault-tolerant Lambda functions.

## Overview

The threshold alert strategy triggers a CloudWatch alarm only when the **error rate exceeds a configured percentage** over multiple evaluation periods, making it ideal for:
- Batch data processing
- External API integration
- Data ingestion from unreliable sources
- Background job processing
- Any operation where occasional failures are expected and acceptable

## Use Case

This example implements a data ingestion Lambda function that:
- Fetches data from external APIs
- Handles network timeouts gracefully
- Tolerates occasional HTTP errors
- Only alerts when error rate exceeds 5% over 2 consecutive periods

## Architecture

```
┌─────────────┐
│   Lambda    │
│   Function  │──────┐
└─────────────┘      │
                     │ Some errors occur (< 5%)
                     │ No alarm triggered ✓
                     │
                     │ Error rate > 5% for 2 periods
                     ▼
┌─────────────────────────────────┐
│   CloudWatch Alarm              │
│   (threshold strategy)          │
│   Metric: Error Rate %          │
│   Threshold: > 5%               │
│   Periods: 2 consecutive        │
└─────────────────────────────────┘
                     │
                     │ Publishes to
                     ▼
         ┌──────────────────┐
         │    SNS Topic     │
         └──────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Email 1      Email 2      Slack
                            (optional)
```

## Features Demonstrated

- **Threshold-based alerting**: CloudWatch alarm using metric math for error rate calculation
- **Error tolerance**: Accepts occasional failures without triggering alarms
- **Multiple evaluation periods**: Requires sustained high error rate before alerting
- **Throttle monitoring**: Separate alarm for Lambda throttling
- **Extended log retention**: 90 days of CloudWatch Logs
- **Python 3.12**: Latest Python runtime

## Alert Logic

The alarm uses CloudWatch metric math to calculate error rate:

```
Error Rate (%) = (Errors / Invocations) * 100
```

**Alarm triggers when**:
- Error rate > 5% for 2 consecutive 60-second periods
- Both periods must breach the threshold

**Example scenarios**:

| Invocations | Errors | Error Rate | Alarm? |
|-------------|--------|------------|--------|
| 100         | 2      | 2%         | ✗ No   |
| 100         | 5      | 5%         | ✗ No (= threshold) |
| 100         | 6      | 6%         | ✓ Yes (if sustained for 2 periods) |
| 20          | 2      | 10%        | ✓ Yes (if sustained for 2 periods) |

## Prerequisites

- Terraform ~> 1.0
- AWS credentials configured
- At least one valid email address for alerts

## Usage

1. **Create `terraform.tfvars`**:

```hcl
aws_region = "us-west-2"

alarm_emails = [
  "data-team@example.com",
  "ops@example.com"
]
```

2. **Deploy the infrastructure**:

```bash
terraform init
terraform plan
terraform apply
```

3. **Confirm email subscriptions**:

After applying, AWS will send confirmation emails. Recipients **must click the confirmation link** to receive alerts.

4. **Test the Lambda function**:

Successful invocation:
```bash
aws lambda invoke \
  --function-name data-ingestion-threshold \
  --payload '{"url": "https://httpbin.org/json", "timeout": 10}' \
  response.json
```

Trigger an error (invalid URL):
```bash
aws lambda invoke \
  --function-name data-ingestion-threshold \
  --payload '{"url": "invalid-url"}' \
  response.json
```

5. **Test threshold behavior**:

The alarm will only trigger if the error rate exceeds 5% for 2 consecutive 60-second periods.

To test:
```bash
# Generate mixed workload: 95 successes + 6 failures = 6% error rate
for i in {1..95}; do
  aws lambda invoke \
    --function-name data-ingestion-threshold \
    --payload '{"url": "https://httpbin.org/json"}' \
    --no-cli-pager \
    response-$i.json &
done

for i in {1..6}; do
  aws lambda invoke \
    --function-name data-ingestion-threshold \
    --payload '{"url": "invalid"}' \
    --no-cli-pager \
    error-$i.json &
done

wait
```

Wait 2-3 minutes for alarm to evaluate and trigger.

## Configuration Options

### Threshold Settings

Customize alert thresholds in `main.tf`:

```hcl
# Alert when error rate exceeds 10% over 3 periods
error_rate_threshold           = 10.0  # 10% error rate
error_rate_evaluation_periods  = 3     # Evaluate over 3 periods
error_rate_datapoints_to_alarm = 2     # Must breach in at least 2 periods

# Alert when error rate exceeds 5% and ALL 2 periods breach
error_rate_threshold           = 5.0
error_rate_evaluation_periods  = 2
error_rate_datapoints_to_alarm = 2  # All periods must breach
```

**Datapoints to Alarm vs Evaluation Periods**:
- `evaluation_periods = 3, datapoints_to_alarm = 2`: Alarm if **at least 2 out of 3** periods breach
- `evaluation_periods = 3, datapoints_to_alarm = 3`: Alarm if **all 3** periods breach

### Lambda Settings

Customize Lambda configuration:

```hcl
module "data_ingestion" {
  # ... other configuration

  python_version = "python3.12"  # Python 3.9-3.13 supported
  architecture   = "x86_64"       # or "arm64"
  timeout        = 30             # seconds
  memory_size    = 512            # MB
}
```

### Disable Throttle Alerts

If throttling is expected and acceptable:

```hcl
module "data_ingestion" {
  # ... other configuration

  enable_throttle_alarms = false
}
```

## Monitoring

### CloudWatch Logs

View function logs:
```bash
aws logs tail /aws/lambda/data-ingestion-threshold --follow
```

### CloudWatch Metrics

View error rate:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=data-ingestion-threshold \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T01:00:00Z \
  --period 60 \
  --statistics Sum
```

### CloudWatch Alarms

Check alarm status:
```bash
aws cloudwatch describe-alarms \
  --alarm-names data-ingestion-threshold-errors-threshold
```

View alarm history:
```bash
aws cloudwatch describe-alarm-history \
  --alarm-name data-ingestion-threshold-errors-threshold \
  --max-records 10
```

## Understanding Metric Math

The threshold alarm uses CloudWatch metric math:

```hcl
# Calculate error rate percentage
metric_query {
  id          = "error_rate"
  expression  = "(errors / invocations) * 100"
  label       = "Error Rate (%)"
  return_data = true
}

metric_query {
  id = "errors"
  metric {
    metric_name = "Errors"
    namespace   = "AWS/Lambda"
    period      = 60
    stat        = "Sum"
  }
}

metric_query {
  id = "invocations"
  metric {
    metric_name = "Invocations"
    namespace   = "AWS/Lambda"
    period      = 60
    stat        = "Sum"
  }
}
```

View the calculated metric:
```bash
aws cloudwatch get-metric-data \
  --metric-data-queries '[
    {
      "Id": "error_rate",
      "Expression": "(errors/invocations)*100"
    },
    {
      "Id": "errors",
      "MetricStat": {
        "Metric": {
          "Namespace": "AWS/Lambda",
          "MetricName": "Errors",
          "Dimensions": [{"Name": "FunctionName", "Value": "data-ingestion-threshold"}]
        },
        "Period": 60,
        "Stat": "Sum"
      }
    },
    {
      "Id": "invocations",
      "MetricStat": {
        "Metric": {
          "Namespace": "AWS/Lambda",
          "MetricName": "Invocations",
          "Dimensions": [{"Name": "FunctionName", "Value": "data-ingestion-threshold"}]
        },
        "Period": 60,
        "Stat": "Sum"
      }
    }
  ]' \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T01:00:00Z
```

## Cost Estimation

Approximate monthly costs (us-west-2):
- Lambda (x86_64, 100K invocations, 512MB, 5s avg): ~$8.40
- CloudWatch Logs (10GB): ~$5.00
- CloudWatch Alarms (2 alarms): ~$0.20
- SNS (100 notifications): ~$0.02
- S3 (deployment package storage): ~$0.02

**Total: ~$13.64/month** for 100,000 invocations

## Cleanup

Remove all resources:

```bash
terraform destroy
```

## When to Use Threshold Alerts

✅ **Use threshold alerts for**:
- Batch data processing
- External API integration
- Data ingestion pipelines
- Background jobs
- Retry-tolerant operations
- High-volume processing

❌ **Don't use threshold alerts for**:
- Payment processing
- Critical transactions
- Security operations
- Real-time user operations
- Single-failure-sensitive operations
→ *Use immediate strategy instead*

## Choosing the Right Threshold

| Error Rate | Recommendation | Use Case |
|------------|---------------|-----------|
| 1-2%       | Very strict   | Important batch jobs |
| 5%         | **Recommended** | General fault-tolerant operations |
| 10%        | Lenient       | Highly unreliable external sources |
| 20%+       | Very lenient  | Experimental/optional operations |

**Consider**:
- Source reliability (external APIs vs internal services)
- Business impact of errors
- Natural error rate of the data source
- Cost of false positives (alert fatigue)

## Troubleshooting

### Alarm triggers too often

1. Increase error rate threshold:
   ```hcl
   error_rate_threshold = 10.0  # Increase from 5%
   ```

2. Require more periods:
   ```hcl
   error_rate_evaluation_periods  = 3  # Increase from 2
   error_rate_datapoints_to_alarm = 3  # All must breach
   ```

### Alarm doesn't trigger when expected

1. Check if error rate actually exceeds threshold:
   ```bash
   # View recent errors and invocations
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Errors \
     --dimensions Name=FunctionName,Value=data-ingestion-threshold \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 60 \
     --statistics Sum
   ```

2. Verify alarm configuration:
   ```bash
   aws cloudwatch describe-alarms \
     --alarm-names data-ingestion-threshold-errors-threshold
   ```

3. Check for insufficient data (very low invocation rate)

### No invocation data

If invocation rate is very low (< 1/minute), consider:
- Increasing evaluation period to 300 seconds (5 minutes)
- Using immediate strategy instead

## Related Examples

- [Immediate Alerts](../immediate-alerts/) - For critical operations
- [Custom Permissions](../custom-permissions/) - Lambda with additional IAM policies

## References

- [Module Documentation](../../README.md)
- [CloudWatch Metric Math](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/using-metric-math.html)
- [AWS Lambda Metrics](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics.html)