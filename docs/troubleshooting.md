# Troubleshooting

Symptoms and fixes for the things that actually go wrong in practice.

## Packaging

### `pip: command not found` or `jq: command not found` during apply

The packaging script runs on whichever machine invokes `terraform apply` — a CI runner, a laptop, a bastion.
It needs `python3`, `pip3`, and `jq` on that host. See [Getting Started → Prerequisites](getting-started.md#host-tools).

The script fails fast with the exact install command for your OS, so the error message tells you what to run.

### `No matching distribution found` / `Could not find a version that satisfies the requirement`

`scripts/package.sh` uses `--only-binary=:all:` with the manylinux platform ladder
(`manylinux_2_28_${ARCH}` → `manylinux_2_17_${ARCH}` → `manylinux2014_${ARCH}`). If a package in your
`requirements.txt` doesn't publish *any* of those manylinux wheels for the target architecture, pip will refuse rather than
silently falling back to a source dist that won't run on Lambda.

Options:

- **Pin to a version that does have wheels.** Check `pip install <pkg>==X --dry-run` on a real amd64/arm64 box.
- **Switch architectures.** arm64 wheels are less common than x86_64 for legacy packages — try flipping
  `architecture = "x86_64"`.
- **Replace the dependency.** There's often a pure-Python alternative (e.g., `requests` instead of something
  that wraps a C HTTP client).

### Terraform keeps re-uploading the zip even though nothing changed

The module's hash input is: files matching `source_code_files` (default `["main.py"]`) + `requirements.txt`
+ architecture + python version + function name + module version.

If you rename your handler file or add new source files, extend `source_code_files`:

```hcl
source_code_files = ["main.py", "handlers/*.py", "utils.py"]
```

Otherwise those files won't contribute to the hash and changes to them won't trigger a repackage.

The hash deliberately does **not** include the installed `.build/` directory, so wiping `.terraform` or
switching branches doesn't cause spurious re-uploads. If you *are* seeing a re-upload on every apply, check
whether `locals.tf` `module_version` was bumped — upgrading the module is meant to force a repackage.

## SNS and alerts

### Alarms fire but no email arrives

Email subscribers must click the **AWS SNS confirmation link** before they receive any messages. Subscriptions
sit in `PendingConfirmation` state indefinitely until confirmed.

Check with:

```bash
aws sns list-subscriptions-by-topic --topic-arn <topic-arn>
```

Look for `SubscriptionArn: PendingConfirmation`. Re-request the email via the console or `aws sns subscribe`.

### `errors-immediate` stays in ALARM for minutes after a single error

Expected. The alarm evaluates `ceil(timeout / 60) + 5` one-minute periods so it can catch errors that Lambda
reports late in a long invocation, and it returns to `OK` only once the error's minute leaves that window: about
6 minutes for a 60-second function, 20 minutes for a 900-second one. Errors inside that window don't send a new
notification. See [Monitoring → Long-running invocations](monitoring.md#long-running-invocations).

### `errors-threshold` stays OK although the function keeps failing

Most often the function runs less often than `error_rate_period`. The threshold alarm needs M breaching datapoints,
and a function scheduled every 30 minutes produces one datapoint per run, so with the default 60-second period the
alarm can't collect two. Long runs have a similar effect: a run that ends many minutes after it started reports its
errors too late to be judged.

Set `error_rate_period` to at least the longest gap between invocations and at least `timeout`, or switch to
`alert_strategy = "immediate"`. See [Monitoring → Sparse invocations](monitoring.md#sparse-invocations).

### PagerDuty / Slack topic in `alarm_topic_arns` doesn't receive events

Cross-account SNS topics need a **resource policy** on the target topic allowing `sns:Publish` from the source
account. This module doesn't manage topics it didn't create — the external topic's policy is your responsibility.

Confirm with:

```bash
aws sns get-topic-attributes --topic-arn <external-arn> --query 'Attributes.Policy'
```

## Log group

### `ResourceAlreadyExistsException` creating `/aws/lambda/<function_name>`

The log group already exists outside Terraform's state. The usual cause is an orphan from an earlier destroy: Lambda
wrote the function's last log lines a few seconds after the function was deleted, found the group gone, and the
execution role re-created it. Such a group has no retention (`retentionInDays` unset) and usually `storedBytes: 0`, and
CloudTrail shows its `CreateLogGroup` made by the function's execution role with user agent `awslambda-worker/1.0`.
See [Architecture → Log group lifecycle](architecture.md#log-group-lifecycle) and
[#26](https://github.com/infrahouse/terraform-aws-lambda-monitored/issues/26).

The module now prevents this: the role can't create log groups, and destroy waits `log_group_destroy_delay_seconds`
before deleting the group. An orphan can still be left by a destroy that ran an older module version, or when a policy
in `additional_iam_policy_arns` grants `logs:CreateLogGroup` again (`AWSLambdaBasicExecutionRole` does, on `*`); then
only the wait protects the group.

Check the group, then either delete it if it holds nothing you need, or import it so Terraform manages it again:

```bash
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/<function_name>
aws logs delete-log-group --log-group-name /aws/lambda/<function_name>
# or
terraform import 'module.<name>.aws_cloudwatch_log_group.lambda' /aws/lambda/<function_name>
```

After an import, the next apply sets the module's retention and tags on the group.

### `terraform destroy` pauses before deleting the log group

Expected. Destroy waits `log_group_destroy_delay_seconds` (10 by default) between deleting the function and deleting
its log group, so Lambda's last log lines can't re-create the group. Set it to `0` to turn the wait off.

### `terraform init` can't find `hashicorp/time`

The module uses `time_sleep` from the `hashicorp/time` provider (`~> 0.9`) for the destroy-time wait. If your
`terraform init` installs providers from a mirror (`provider_installation` in the CLI configuration, or
`-plugin-dir`), add `hashicorp/time` to it.

## IAM

### `The role defined for the function cannot be assumed by Lambda`

Usually means Terraform raced ahead of IAM eventual consistency. The module has a built-in `depends_on` chain,
but if you've wired the Lambda into a custom role, re-apply — the second run almost always succeeds.

### Role name shows up truncated

Expected when `role_name_prefix` is unset: the execution role's `name_prefix` is then the first 37 characters of
`function_name` plus `-`. See [Architecture → IAM role naming](architecture.md#iam-role-naming). The full function
name is preserved in tags. To choose how the role name starts, set `role_name_prefix`. Either way, downstream callers
should use the `lambda_role_arn` / `lambda_role_name` outputs rather than reconstructing the name.

### `Invalid value for variable` on `role_name_prefix`

The plan fails before anything is created when `role_name_prefix` is not 1–38 characters from the IAM role name set
(letters, digits and `+=,.@_-`). Common causes:

- An empty string. Use `null` to get the default prefix derived from `function_name`.
- More than 38 characters. AWS caps role names at 64 and Terraform appends 26.
- A character IAM doesn't allow in names, such as `*` copied from an `ArnLike` pattern, or `/` from a role path.

### Setting `role_name_prefix` replaces the execution role

Expected. Role names can't change in place, so setting, changing or removing `role_name_prefix` on an existing
deployment makes Terraform replace `aws_iam_role.lambda` and update the function to use the new role. Leave it unset
to keep the existing role.

## VPC

### Lambda creation times out or returns `Lambda was unable to configure access to your environment`

The Lambda ENI lifecycle needs:

1. Subnets with outbound connectivity (NAT gateway **or** VPC endpoints for the services the Lambda calls).
2. Enough free IP addresses in each subnet for ENIs.
3. Security groups that allow *outbound* traffic (Lambdas typically don't need inbound rules at all).

Check:

```bash
aws ec2 describe-subnets --subnet-ids <ids> \
  --query 'Subnets[].[SubnetId,AvailableIpAddressCount]'
```

### Lambda can't reach the internet even though subnets are "private"

"Private with NAT" vs "private without NAT" are different. Isolated private subnets (no NAT, no IGW route) can
only reach services accessible via VPC endpoints. If your Lambda needs `pypi`, external APIs, or `sts:AssumeRole`
in another region, you need a NAT gateway or a VPC endpoint for that specific service.

## Integration tests

### `AccessDenied` on `sts:AssumeRole`

The test harness assumes `arn:aws:iam::303467602807:role/lambda-monitored-tester` by default. To use a different
role:

```bash
make test-simple TEST_ROLE=arn:aws:iam::<your-account>:role/<your-tester-role>
```

The role needs `lambda:*`, `iam:*Role*`/`*Policy*` on the execution role (`${function_name}-*` by default, with
the first 37 characters of the name, or `${role_name_prefix}*` when the input is set), `s3:*` on the deployment
bucket, `logs:*`, `cloudwatch:*Alarm*`, `sns:*`, and `ec2:*NetworkInterface*` for VPC tests.

### Tests leave resources behind

Run with `KEEP_AFTER=1` intentionally preserves resources so you can watch alarms fire. Without `KEEP_AFTER`,
cleanup happens in the test's teardown unless the test crashed between `apply` and `destroy`.

To clean up orphans manually:

```bash
aws lambda list-functions \
  --query 'Functions[?starts_with(FunctionName,`test-`)].FunctionName' \
  --output text
```

Then `aws lambda delete-function` each one, or use `terraform destroy` against the throwaway module in the
test's temp directory (the path is in `pytest-<timestamp>-output.log`).

### Provider version matrix takes forever

The suite parametrizes over AWS provider 5.x/6.x × architectures × python versions. Filter with:

```bash
make test-simple TEST_SELECTOR="provider-6.x and py3.12"
```

## Still stuck?

- Open an issue: <https://github.com/infrahouse/terraform-aws-lambda-monitored/issues>
- Commercial support: <https://infrahouse.com/contact>
