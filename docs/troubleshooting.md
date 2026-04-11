# Troubleshooting

Symptoms and fixes for the things that actually go wrong in practice.

## Packaging

### `pip: command not found` or `jq: command not found` during apply

The packaging script runs on whichever machine invokes `terraform apply` — a CI runner, a laptop, a bastion.
It needs `python3`, `pip3`, and `jq` on that host. See [Getting Started → Prerequisites](getting-started.md#host-tools).

The script fails fast with the exact install command for your OS, so the error message tells you what to run.

### `No matching distribution found` / `Could not find a version that satisfies the requirement`

`scripts/package.sh` uses `--only-binary=:all:` with `--platform manylinux2014_${ARCH}`. If a package in your
`requirements.txt` doesn't publish a manylinux wheel for the target architecture, pip will refuse rather than
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

### PagerDuty / Slack topic in `alarm_topic_arns` doesn't receive events

Cross-account SNS topics need a **resource policy** on the target topic allowing `sns:Publish` from the source
account. This module doesn't manage topics it didn't create — the external topic's policy is your responsibility.

Confirm with:

```bash
aws sns get-topic-attributes --topic-arn <external-arn> --query 'Attributes.Policy'
```

## IAM

### `The role defined for the function cannot be assumed by Lambda`

Usually means Terraform raced ahead of IAM eventual consistency. The module has a built-in `depends_on` chain,
but if you've wired the Lambda into a custom role, re-apply — the second run almost always succeeds.

### Role name shows up truncated

Expected. The execution role uses `name_prefix = substr(function_name, 0, 37)`. See
[Architecture → IAM role naming](architecture.md#iam-role-naming). The full function name is preserved in
tags, and downstream callers should use the `lambda_role_arn` / `lambda_role_name` outputs rather than
reconstructing the name from `function_name`.

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

The role needs `lambda:*`, `iam:*Role*`/`*Policy*` on `${function_name}-*`, `s3:*` on the deployment bucket,
`logs:*`, `cloudwatch:*Alarm*`, `sns:*`, and `ec2:*NetworkInterface*` for VPC tests.

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
