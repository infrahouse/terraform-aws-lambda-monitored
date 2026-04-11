# Getting Started

This page walks you through the prerequisites and a minimal first deployment.

## Prerequisites

### Host tools

The module's packaging script runs on the machine where `terraform apply` executes, so that host needs:

| Tool | Purpose | Install |
|------|---------|---------|
| `python3` | Build virtualenv, install deps | `brew install python3` / `apt install python3` |
| `pip3` | Install Python dependencies | `python3 -m ensurepip` |
| `jq` | Parse AWS CLI JSON output | `brew install jq` / `apt install jq` |
| `terraform` | `~> 1.0` | <https://developer.hashicorp.com/terraform/install> |
| `aws` CLI | Used by the S3 upload wait loop | <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html> |

Linux/macOS only — `infrahouse-core` doesn't support Windows.

The packaging script fails fast with an install hint if any of these are missing.

### AWS permissions

The role that runs Terraform needs enough permissions to manage:

- `lambda:*` on the target function
- `iam:*Role*` and `iam:*Policy*` on `${function_name}-*` roles
- `s3:*` on the deployment bucket (the module creates it via `infrahouse/s3-bucket/aws`)
- `logs:*` on `/aws/lambda/${function_name}`
- `cloudwatch:PutMetricAlarm` / `DeleteAlarms`
- `sns:*` on the alarm topic
- `ec2:Describe*` + `ec2:*NetworkInterface*` when `lambda_subnet_ids` is set

For development, an account-scoped `AdministratorAccess` role is simplest. For production, use
least-privilege and scope by resource prefix.

## First deployment

### 1. Lay out your Lambda source

```
my-project/
├── main.tf
└── lambda/
    ├── main.py          # handler entrypoint
    └── requirements.txt # optional, only if you have deps
```

`main.py` should export a handler function — by default the module looks for `main.lambda_handler` (override
via the `handler` variable if you want a different name):

```python
def lambda_handler(event, context):
    return {"statusCode": 200, "body": "hello"}
```

### 2. Wire up the module

```hcl
terraform {
  required_version = "~> 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "us-west-2"
}

module "lambda" {
  source  = "registry.infrahouse.com/infrahouse/lambda-monitored/aws"
  version = "1.0.4"

  function_name     = "hello-lambda"
  lambda_source_dir = "${path.module}/lambda"

  alarm_emails = ["oncall@example.com"]
}
```

### 3. Apply

```bash
terraform init
terraform apply
```

On first apply the module will:

1. Install dependencies into `.build/hello-lambda/` with manylinux wheels.
2. Zip the package and upload it to the deployment S3 bucket.
3. Create the Lambda function, IAM role, log group, SNS topic, and alarms.
4. Send a confirmation email to every address in `alarm_emails` — you must click the SNS confirmation link
   before alarms can deliver.

### 4. Verify

```bash
aws lambda invoke --function-name hello-lambda --payload '{}' /tmp/out.json
cat /tmp/out.json
```

The first invocation creates a log stream in `/aws/lambda/hello-lambda`; subsequent errors will populate
the `hello-lambda-errors-immediate` CloudWatch alarm and (once you confirm the subscription) fan out to
the configured email addresses.

## Running the module's tests

The integration suite applies real AWS infrastructure in `us-west-2` using an STS-assumed tester role:

```bash
make bootstrap      # install Python deps
make test-simple    # run the simple-Lambda suite only
make test           # run the full matrix
```

See [Troubleshooting](troubleshooting.md) if tests fail locally with permissions errors.
