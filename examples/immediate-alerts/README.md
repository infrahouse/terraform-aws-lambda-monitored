# Immediate Alerts Example

This example demonstrates using the `terraform-aws-lambda-monitored` module with the **immediate alert strategy** for critical Lambda functions.

## Overview

The immediate alert strategy triggers a CloudWatch alarm on **any Lambda error**, making it ideal for:
- Critical business operations
- Payment processing
- Order fulfillment
- Security-related functions
- Any operation where even a single failure requires immediate attention

## Use Case

This example implements an order processor Lambda function that:
- Validates order data
- Processes payments
- Returns success/failure responses
- Triggers immediate alerts on any error

## Architecture

```
┌─────────────┐
│   Lambda    │
│   Function  │──────┐
└─────────────┘      │
                     │ Error occurs
                     ▼
┌─────────────────────────────┐
│   CloudWatch Alarm          │
│   (immediate strategy)      │
│   Threshold: > 0 errors     │
└─────────────────────────────┘
                     │
                     │ Publishes to
                     ▼
         ┌──────────────────┐
         │    SNS Topic     │
         └──────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Email 1      Email 2     PagerDuty
                            (optional)
```

## Features Demonstrated

- **Immediate error alerting**: CloudWatch alarm configured with threshold of 0 errors
- **ARM64 architecture**: Cost-optimized Lambda using arm64
- **Environment variables**: Configurable runtime behavior
- **CloudWatch Logs**: Structured logging for debugging
- **Email notifications**: SNS subscriptions for alarm delivery
- **Python 3.12**: Latest Python runtime

## Prerequisites

- Terraform ~> 1.0
- AWS credentials configured
- At least one valid email address for alerts

## Usage

1. **Create `terraform.tfvars`**:

```hcl
aws_region = "us-west-2"

alarm_emails = [
  "oncall@example.com",
  "team-lead@example.com"
]
```

2. **Deploy the infrastructure**:

```bash
terraform init
terraform plan
terraform apply
```

3. **Confirm email subscriptions**:

After applying, AWS will send confirmation emails to all addresses in `alarm_emails`. Recipients **must click the confirmation link** to receive alerts.

4. **Test the Lambda function**:

Successful invocation:
```bash
aws lambda invoke \
  --function-name order-processor-immediate \
  --payload '{"order_id": "123", "amount": "99.99"}' \
  response.json
```

Trigger an error (missing required field):
```bash
aws lambda invoke \
  --function-name order-processor-immediate \
  --payload '{"order_id": "123"}' \
  response.json
```

5. **Verify alarm triggers**:

After an error, the CloudWatch alarm will enter ALARM state within 1-2 minutes and send notifications to all confirmed email subscribers.

## Configuration Options

### Alert Strategy

The immediate strategy is configured in `main.tf`:

```hcl
alert_strategy = "immediate"
```

This creates a CloudWatch alarm with:
- **Metric**: Lambda Errors
- **Threshold**: Greater than 0
- **Evaluation Period**: 1 period (60 seconds)
- **Datapoints to Alarm**: 1

### Lambda Settings

Customize Lambda configuration in `main.tf`:

```hcl
module "order_processor" {
  # ... other configuration

  python_version = "python3.12"  # Python 3.9-3.13 supported
  architecture   = "arm64"        # or "x86_64"
  timeout        = 30             # seconds
  memory_size    = 256            # MB
}
```

### Additional SNS Topics

Send alerts to external services like PagerDuty or Slack:

```hcl
module "order_processor" {
  # ... other configuration

  alarm_topic_arns = [
    aws_sns_topic.pagerduty.arn,
    aws_sns_topic.slack_alerts.arn
  ]
}
```

## Monitoring

### CloudWatch Logs

View function logs:
```bash
aws logs tail /aws/lambda/order-processor-immediate --follow
```

### CloudWatch Alarms

Check alarm status:
```bash
aws cloudwatch describe-alarms --alarm-names order-processor-immediate-errors-immediate
```

### SNS Subscriptions

List email subscriptions:
```bash
aws sns list-subscriptions
```

## Cost Estimation

Approximate monthly costs (us-west-2):
- Lambda (arm64, 10K invocations, 256MB, 5s avg): ~$0.20
- CloudWatch Logs (5GB): ~$2.50
- CloudWatch Alarms (1 alarm): ~$0.10
- SNS (100 notifications): ~$0.02
- S3 (deployment package storage): ~$0.02

**Total: ~$2.84/month** for 10,000 invocations

## Cleanup

Remove all resources:

```bash
terraform destroy
```

**Note**: S3 buckets with versioning enabled may require manual cleanup.

## When to Use Immediate Alerts

✅ **Use immediate alerts for**:
- Payment processing
- Financial transactions
- Security operations
- Critical data updates
- User account management
- Legal/compliance operations

❌ **Don't use immediate alerts for**:
- Batch processing jobs
- Retry-tolerant operations
- Non-critical background tasks
- High-volume data ingestion
→ *Use threshold strategy instead*

## Troubleshooting

### Emails not received

1. Check spam/junk folders
2. Verify SNS subscription status:
   ```bash
   aws sns list-subscriptions-by-topic --topic-arn <topic-arn>
   ```
3. Look for `PendingConfirmation` status

### Alarm not triggering

1. Verify Lambda errors in CloudWatch Logs
2. Check alarm metric data:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/Lambda \
     --metric-name Errors \
     --dimensions Name=FunctionName,Value=order-processor-immediate \
     --start-time <timestamp> \
     --end-time <timestamp> \
     --period 60 \
     --statistics Sum
   ```
3. Alarms evaluate every 60 seconds - allow 1-2 minutes for state change

## Related Examples

- [Threshold Alerts](../threshold-alerts/) - For fault-tolerant operations
- [Custom Permissions](../custom-permissions/) - Lambda with additional IAM policies

## References

- [Module Documentation](../../README.md)
- [AWS Lambda Error Handling](https://docs.aws.amazon.com/lambda/latest/dg/invocation-retries.html)
- [CloudWatch Alarm States](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)