# Configuration

Every input variable, grouped by concern. Defaults are listed where they exist — anything else is required.

The canonical source is [`variables.tf`](https://github.com/infrahouse/terraform-aws-lambda-monitored/blob/main/variables.tf);
this page adds commentary on *when* and *why* you'd override each one.

## Function basics

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `function_name` | `string` | — (required) | Alphanumerics, `-`, `_`. Long names still work, but the IAM role uses a truncated `name_prefix` (see [Architecture](architecture.md#iam-role-naming)). |
| `lambda_source_dir` | `string` | — (required) | Directory containing `main.py` (and optionally `requirements.txt`). Resolved relative to the caller's module. |
| `handler` | `string` | `main.lambda_handler` | Format is `file.function`, so `handler.process` means `handler.py::process`. |
| `description` | `string` | `null` | Shown in the Lambda console. |
| `timeout` | `number` | `60` | 1–900 seconds. Duration alarm (if enabled) fires on a percentage of this. |
| `memory_size` | `number` | `128` | 128–10240 MB. CPU scales with memory. |
| `environment_variables` | `map(string)` | `{}` | Plaintext env vars. Use `kms_key_id` to encrypt at rest. |

## Runtime

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `python_version` | `string` | `python3.12` | One of `python3.9`–`python3.13`. Used for the Lambda runtime and the manylinux pip install. |
| `architecture` | `string` | `x86_64` | Or `arm64`. arm64 is ~20% cheaper but some C extensions lack wheels. |

## Packaging

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `source_code_files` | `list(string)` | `["main.py"]` | Glob patterns the packager hashes. Installed deps are tracked separately via `requirements_file`. Add `"*.py"` or specific files if your handler imports siblings. |
| `requirements_file` | `string` | autodetect | Pass a path to override. Auto-detected as `${lambda_source_dir}/requirements.txt` if unset. Set to `null` to skip dep install entirely. |

See [Architecture → Packaging pipeline](architecture.md#packaging-pipeline) for how the hash is computed.

## IAM

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `additional_iam_policy_arns` | `list(string)` | `[]` | Attach any number of AWS-managed or custom policies. One attachment per ARN. |
| `kms_key_id` | `string` | `null` | KMS key ARN for CloudWatch Logs + SNS encryption. Key policy must allow `logs.<region>.amazonaws.com` and `sns.amazonaws.com`. |

## VPC

Both must be set together. If unset, the Lambda runs in the AWS-managed VPC and uses the public internet.

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `lambda_subnet_ids` | `list(string)` | `null` | Private subnets with a NAT gateway for outbound traffic. |
| `lambda_security_group_ids` | `list(string)` | `null` | Security groups to attach to the Lambda ENIs. |

Setting these flips on a second IAM policy (`aws_iam_role_policy.lambda_vpc_access`) scoped to **only** the specified
subnets — the module refuses to grant broad `ec2:*NetworkInterface*` permissions.

## Logging

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `cloudwatch_log_retention_days` | `number` | `365` | Must be a valid CloudWatch retention value (`1`, `3`, `7`, `14`, `30`, `60`, `90`, …, `3653`, or `0` for never expire). |

## Alerting — recipients

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `alarm_emails` | `list(string)` | — (required, non-empty) | Subscribed to the module's SNS topic. **Each subscriber must manually confirm** the AWS confirmation email before alarms deliver. |
| `alarm_topic_arns` | `list(string)` | `[]` | Additional SNS topics the alarms fan out to. Use for PagerDuty, Slack webhooks via chatbot, or cross-account topics. |
| `sns_topic_name` | `string` | `${function_name}-alarms` | Override only if you need a specific name. |

## Alerting — error strategy

Pick **one** strategy based on expected error volume:

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `enable_error_alarms` | `bool` | `true` | Set to `false` to skip the error alarm entirely. |
| `alert_strategy` | `string` | `immediate` | `immediate` fires on any error; `threshold` fires on error *rate*. |
| `error_rate_threshold` | `number` | `5.0` | Percent. Only used when `alert_strategy = "threshold"`. |
| `error_rate_evaluation_periods` | `number` | `2` | Threshold strategy only. |
| `error_rate_datapoints_to_alarm` | `number` | `2` | Threshold strategy only. |

**Rule of thumb:** use `immediate` for low-traffic or critical-path functions (cron jobs, deploy hooks) where any
error is a page. Use `threshold` for high-volume functions that tolerate occasional failures (webhook ingesters,
retryable workers).

## Alerting — other alarms

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `enable_throttle_alarms` | `bool` | `true` | Fires on any throttle. Usually means concurrency limit hit. |
| `duration_threshold_percent` | `number` | `null` | Set to e.g. `80` to alarm when execution exceeds 80% of `timeout`. `null` disables the alarm. |
| `memory_utilization_threshold_percent` | `number` | `null` | When set, enables the Lambda Insights layer (extra cost) and alarms on `memory_utilization`. |
| `lambda_insights_layer_arn` | `string` | region/arch default | Override only if you need a specific version or region not in the module's defaults. |

## Tagging

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `tags` | `map(string)` | `{}` | Applied to every resource the module creates. Full `function_name` is automatically added so IAM role name truncation is recoverable from tags. |
