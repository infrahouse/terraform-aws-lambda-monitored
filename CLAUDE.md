# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First Steps

**Your first tool call in this repository MUST be reading .claude/CODING_STANDARD.md.
Do not read any other files, search, or take any actions until you have read it.**
This contains InfraHouse's comprehensive coding standards for Terraform, Python, and general formatting rules.

## Repository Purpose

Terraform module (`infrahouse/lambda-monitored/aws`) that provisions an AWS Lambda function plus its monitoring
stack: CloudWatch log group, SNS topic with email subscriptions, and CloudWatch alarms for errors, throttles, and
duration. Designed to meet ISO27001 error-rate monitoring requirements.

## Common Commands

All day-to-day tasks go through the Makefile (`make help` lists targets):

- `make bootstrap` — install Python deps from `tests/requirements.txt` (pip/setuptools pinned)
- `make lint` — `yamllint .github/workflows` + `terraform fmt -check -recursive`
- `make format` — `terraform fmt -recursive` + `black tests/`
- `make test` — runs the full integration suite (`test-simple`, `test-deps`, `test-monitoring`, `test-sns`, `test-vpc`)
- `make test-<suite>` — run one suite (e.g. `make test-simple`); suites map to `Test*` classes in `tests/test_module.py`
- `make release-{patch,minor,major}` — bumps version via `.bumpversion.cfg`, edits `CHANGELOG.md`, commits, tags;
  requires being on `main`

### Running a single test

Tests are filtered via `TEST_SELECTOR`, which is combined with the suite's class filter using `and`:

```bash
make test-simple TEST_SELECTOR="test_lambda_deployment"
make test-deps TEST_SELECTOR="provider-6.x and py3.13"
make test-simple TEST_REGION=eu-west-1 KEEP_AFTER=1
```

Defaults: `TEST_REGION=us-west-2`, `TEST_ROLE=arn:aws:iam::303467602807:role/lambda-monitored-tester`. `KEEP_AFTER=1`
preserves provisioned AWS resources after the test run (useful for alarm/SNS debugging). Test output is tee'd to
`pytest-<timestamp>-output.log`.

**Tests are real integration tests** — they assume STS `AssumeRole` on the test role and will apply/destroy real AWS
infrastructure in the target account.

## Architecture

### Terraform module layout

The root module is flat (not split into submodules). Files are grouped by concern rather than resource type:

- `lambda.tf` — `aws_lambda_function` + `aws_lambda_function_event_invoke_config` (retries disabled by default)
- `lambda_code.tf` — packaging pipeline: computes `package_hash` from source files + requirements + arch + python
  version + module version, then invokes `scripts/package.sh` via `null_resource.lambda_package`. The hash flows into
  `source_code_hash` so Lambda updates only when inputs actually change.
- `lambda_s3.tf` — uses `registry.infrahouse.com/infrahouse/s3-bucket/aws` submodule for the deployment bucket;
  filename embeds `package_hash`.
- `lambda_iam.tf` — execution role (assume-role policy, logging policy, VPC ENI policy when `lambda_subnet_ids` is
  set, user-supplied `additional_iam_policy_arns`). **IAM role uses `name_prefix`**, truncated if `function_name` > 37
  chars to stay under AWS's 38-char limit; full name is preserved in tags. Downstream callers must use
  `lambda_role_arn`/`lambda_role_name` outputs rather than reconstructing the name.
- `alarms.tf` — four CloudWatch alarms: `errors_immediate` (fires on any error) **or** `errors_threshold` (error-rate
  metric-math, `(errors / invocations) * 100`) depending on `alert_strategy`; always-on `throttles`; optional
  `duration` (only when `duration_threshold_percent` is set, computed against `var.timeout`).
- `sns.tf` / `cloudwatch.tf` — SNS topic + email subscriptions; log group with retention. Alarms fan out to
  `local.all_alarm_topic_arns` which merges the created topic with user-supplied `alarm_topic_arns` for
  PagerDuty/Slack integrations.
- `locals.tf` — owns `module_version` (must be bumped manually via bumpversion; also referenced in `lambda_code.tf`
  so module upgrades trigger a repackage), requirements-file auto-detection, and `source_files_hash`.
- `variables.tf` / `outputs.tf` / `terraform.tf` — inputs, outputs, provider constraints.

### Packaging pipeline — non-obvious details

- Builds happen in `${path.root}/.build/${var.function_name}` (inside the *consumer's* root module, not this module).
  `make clean` removes it.
- `source_code_files` defaults to `["main.py"]` — **only these patterns are hashed for change detection**. Installed
  dependencies are explicitly excluded to prevent spurious rebuilds after `.terraform` is recreated. Dependencies are
  tracked separately via `filemd5(requirements_file)`.
- `scripts/package.sh` installs with `--only-binary=:all:` and `--platform manylinux2014_{x86_64,aarch64}` to
  guarantee Lambda-compatible wheels; it requires `python3`, `pip3`, and `jq` on the host running `terraform apply`.
- `package_hash` is md5 of: source-files hash + requirements hash + architecture + python version + function name +
  `module_version`. Changing any of these causes a repackage and a new S3 object key.

### Test harness

- `tests/conftest.py::create_terraform_config` generates a throwaway root module in a temp directory per test,
  templated with the desired `aws_provider_version`, `python_version`, `architecture`, and `alert_strategy`. It
  deletes `.terraform.lock.hcl` between runs so the AWS provider version can vary.
- `tests/fixtures/` contains the Lambda source dirs (e.g. `simple_lambda`, plus fixtures exercising
  requirements/VPC/monitoring).
- The suite uses `pytest_infrahouse.terraform_apply` as a context manager — the `destroy_after` flag is driven by
  `KEEP_AFTER`. `TestErrorMonitoring` intentionally defaults to keeping resources so alarms can fire and be observed.
- Parametrization covers AWS provider 5.x/6.x × arch × python version; filter with
  `TEST_SELECTOR="provider-6.x and py3.12"`.

### Release flow

Version lives in three places that must stay in sync: `.bumpversion.cfg`, `locals.tf` (`module_version`), and
`README.md` usage examples. `make release-*` handles `.bumpversion.cfg` and `CHANGELOG.md`; bumpversion's config
updates the rest. Releases must be cut from `main`.

### Pre-commit hook

`make install-hooks` (run transitively by `make help`) symlinks `hooks/pre-commit` into `.git/hooks/`. The README
block between `<!-- BEGIN_TF_DOCS -->` and `<!-- END_TF_DOCS -->` is auto-generated via `terraform-docs` (config in
`.terraform-docs.yml`) — do not hand-edit that section.
