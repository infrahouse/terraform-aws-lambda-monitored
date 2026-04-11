# Architecture

This page describes what the module creates and why. Solid lines in the diagram are always created,
dashed lines are optional or conditional on variable values.

![Architecture](assets/architecture.svg)

## Resource inventory

| Resource | File | Count | Purpose |
|----------|------|-------|---------|
| `aws_lambda_function.this` | `lambda.tf` | 1 | The function itself. Source code lives in S3. |
| `aws_lambda_function_event_invoke_config.this` | `lambda.tf` | 1 | Disables async retries by default. |
| `module.lambda_bucket` | `lambda_s3.tf` | 1 | S3 bucket for deployment packages (via `infrahouse/s3-bucket`). |
| `aws_s3_object.lambda_package` | `lambda_s3.tf` | 1 | Uploaded zip. Key includes a content hash so uploads are immutable. |
| `aws_iam_role.lambda` | `lambda_iam.tf` | 1 | Execution role, `name_prefix`-ed so long function names still fit in 38 chars. |
| `aws_iam_role_policy.lambda_logging` | `lambda_iam.tf` | 1 | Write logs to the function's log group only. |
| `aws_iam_role_policy.lambda_vpc_access` | `lambda_iam.tf` | 0 or 1 | ENI lifecycle in specified subnets only, when `lambda_subnet_ids` is set. |
| `aws_iam_role_policy_attachment.additional` | `lambda_iam.tf` | N | One per ARN in `additional_iam_policy_arns`. |
| `aws_iam_role_policy_attachment.lambda_insights` | `lambda_iam.tf` | 0 or 1 | Attaches `CloudWatchLambdaInsightsExecutionRolePolicy` when memory alarm is enabled. |
| `aws_cloudwatch_log_group.lambda` | `cloudwatch.tf` | 1 | `/aws/lambda/${function_name}` with configurable retention. |
| `aws_sns_topic.alarms` | `sns.tf` | 1 | Fan-out point for all alarms. |
| `aws_sns_topic_subscription.alarm_emails` | `sns.tf` | N | One per email in `alarm_emails`. |
| `aws_cloudwatch_metric_alarm.errors_immediate` | `alarms.tf` | 0 or 1 | Fires on any error when `alert_strategy = "immediate"`. |
| `aws_cloudwatch_metric_alarm.errors_threshold` | `alarms.tf` | 0 or 1 | Fires when `errors/invocations * 100 > threshold` (threshold strategy). |
| `aws_cloudwatch_metric_alarm.throttles` | `alarms.tf` | 0 or 1 | Fires on any throttle. |
| `aws_cloudwatch_metric_alarm.duration` | `alarms.tf` | 0 or 1 | Created only when `duration_threshold_percent` is set. |
| `aws_cloudwatch_metric_alarm.memory` | `alarms.tf` | 0 or 1 | Created only when `memory_utilization_threshold_percent` is set (requires Lambda Insights). |

## Packaging pipeline

Lambda source goes through a dedicated build pipeline before being uploaded to S3. Each function gets its
own build directory inside the **caller's** root module (`${path.root}/.build/${function_name}/`), never
inside this module.

### Hashing

`package_hash` (in `locals.tf`) is the MD5 of:

- `source_files_hash` — MD5 of all files matching `source_code_files` (default: `["main.py"]`)
- `filemd5(requirements_file)` — hash of the pinned deps
- `var.architecture` — `x86_64` or `arm64`
- `var.python_version` — `python3.11`, `python3.12`, …
- `var.function_name`
- `module_version` — bumped manually in `locals.tf` during releases

Any change to these triggers a repackage. Critically, the hash does **not** include files in `.build/`,
so wiping `.terraform` and rebuilding doesn't cause a spurious re-upload.

### Build

`scripts/package.sh` runs via `null_resource.lambda_package` with these flags:

```bash
pip install \
  --only-binary=:all: \
  --platform manylinux2014_${ARCH} \
  --target ./.build/${function_name}/ \
  -r requirements.txt
```

The `--only-binary=:all:` flag forces pip to reject source distributions so you can't accidentally
ship a package that only builds on your Mac. The target platform matches the Lambda runtime, not
the host.

### Upload

The zip is uploaded to `${bucket}/${function_name}/${package_hash}.zip`. The `local-exec` provisioner
on `aws_s3_object.lambda_package` runs `wait_for_s3_object.sh` to poll `s3api head-object` until the
object is visible — this avoids race conditions where Lambda creation races ahead of S3 eventual
consistency.

## Alert flow

```
Lambda metric → CloudWatch alarm → SNS topic → {email subs, external topics}
```

`local.all_alarm_topic_arns` (in `sns.tf`) combines the module-created topic with user-supplied
`alarm_topic_arns`, and **every** alarm action writes to that combined list. So if you pass in a
PagerDuty topic ARN, all four alarms will fan out to both the email subs and PagerDuty.

## IAM role naming

The execution role uses `name_prefix = "${substr(var.function_name, 0, 37)}-"`. This is because:

- AWS limits IAM role names to 64 characters
- `name_prefix` appends a 26-character unique suffix
- So the prefix must fit in `64 - 26 = 38` characters, including the trailing `-`

Function names longer than 37 characters still work — the role is created under a truncated prefix —
but **the full function name is preserved in tags**. Downstream callers should always use the
`lambda_role_arn` / `lambda_role_name` outputs rather than trying to reconstruct the role name
from `function_name`.
