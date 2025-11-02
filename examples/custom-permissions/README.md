# Custom Permissions Example

This example demonstrates how to use the `terraform-aws-lambda-monitored` module with **additional IAM permissions** for Lambda functions that need to access AWS services beyond CloudWatch Logs.

## Overview

The module provides a base execution role with CloudWatch Logs permissions. For Lambda functions that need access to other AWS services (S3, DynamoDB, SQS, etc.), you can attach custom IAM policies using the `additional_iam_policy_arns` variable.

## Use Case

This example implements a file processor Lambda function that:
- Reads file metadata from S3
- Stores metadata records in DynamoDB
- Requires custom IAM policies for S3 read and DynamoDB write access
- Demonstrates the flexible permission model

## Architecture

```
┌─────────────────────┐
│   S3 Bucket         │
│   (File Storage)    │
└─────────────────────┘
           │
           │ Read metadata
           ▼
┌─────────────────────────┐        ┌─────────────────────┐
│   Lambda Function       │───────▶│   DynamoDB Table    │
│   + Base permissions    │ Write  │   (Metadata)        │
│   + S3 read policy      │        └─────────────────────┘
│   + DynamoDB write      │
└─────────────────────────┘
           │
           │ Logs & Errors
           ▼
┌─────────────────────────┐
│   CloudWatch            │
│   Logs + Alarms         │
└─────────────────────────┘
```

## Features Demonstrated

- **Custom IAM policies**: Separate policies for S3 and DynamoDB access
- **Least privilege**: Scoped permissions to specific resources
- **Module flexibility**: Using `additional_iam_policy_arns` to extend permissions
- **Multi-service Lambda**: Accessing both S3 and DynamoDB
- **Environment variables**: Passing resource names to Lambda
- **Infrastructure as Code**: All resources (Lambda, S3, DynamoDB, IAM) in Terraform

## Prerequisites

- Terraform ~> 1.0
- AWS credentials configured
- At least one valid email address for alerts

## Usage

1. **Create `terraform.tfvars`**:

```hcl
aws_region = "us-west-2"
environment = "dev"

alarm_emails = [
  "backend-team@example.com"
]

alert_strategy = "immediate"  # or "threshold"
```

2. **Deploy the infrastructure**:

```bash
terraform init
terraform plan
terraform apply
```

3. **Confirm email subscriptions**:

AWS will send confirmation emails. Recipients must click the confirmation link to receive alerts.

4. **Upload a test file to S3**:

```bash
# Get bucket name from Terraform outputs
BUCKET=$(terraform output -raw s3_bucket_name)

# Upload a test file
echo "Hello World" > test.txt
aws s3 cp test.txt s3://$BUCKET/test.txt
```

5. **Test the Lambda function**:

```bash
# Get function name from Terraform outputs
FUNCTION=$(terraform output -raw lambda_function_name)
TABLE=$(terraform output -raw dynamodb_table_name)

# Invoke Lambda to process the file
aws lambda invoke \
  --function-name $FUNCTION \
  --payload "{\"bucket\":\"$BUCKET\",\"key\":\"test.txt\",\"table_name\":\"$TABLE\"}" \
  response.json

# View response
cat response.json
```

6. **Verify metadata in DynamoDB**:

```bash
TABLE=$(terraform output -raw dynamodb_table_name)

aws dynamodb get-item \
  --table-name $TABLE \
  --key "{\"file_id\":{\"S\":\"$BUCKET/test.txt\"}}"
```

## IAM Permissions Model

### Base Permissions (provided by module)

The module automatically creates:

```hcl
# CloudWatch Logs permissions
{
  "Effect": "Allow",
  "Action": [
    "logs:CreateLogGroup",
    "logs:CreateLogStream",
    "logs:PutLogEvents"
  ],
  "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/function-name:*"
}
```

### Custom Permissions (added in this example)

**S3 Read Policy** (defined in `main.tf`):

```hcl
resource "aws_iam_policy" "lambda_s3_access" {
  policy = jsonencode({
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:HeadObject"
        ]
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      },
      {
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = aws_s3_bucket.uploads.arn
      }
    ]
  })
}
```

**DynamoDB Write Policy**:

```hcl
resource "aws_iam_policy" "lambda_dynamodb_access" {
  policy = jsonencode({
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.file_metadata.arn
      }
    ]
  })
}
```

### Attaching Custom Policies

Use `additional_iam_policy_arns` to attach policies:

```hcl
module "file_processor" {
  source = "infrahouse/lambda-monitored/aws"

  # ... other configuration

  additional_iam_policy_arns = [
    aws_iam_policy.lambda_s3_access.arn,
    aws_iam_policy.lambda_dynamodb_access.arn
  ]
}
```

## Common Permission Patterns

### S3 Access

**Read Only**:
```hcl
{
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": ["bucket-arn", "bucket-arn/*"]
}
```

**Write Only**:
```hcl
{
  "Action": ["s3:PutObject"],
  "Resource": "bucket-arn/*"
}
```

**Full Access**:
```hcl
{
  "Action": ["s3:*"],
  "Resource": ["bucket-arn", "bucket-arn/*"]
}
```

### DynamoDB Access

**Read Only**:
```hcl
{
  "Action": ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"],
  "Resource": "table-arn"
}
```

**Write Only**:
```hcl
{
  "Action": ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem"],
  "Resource": "table-arn"
}
```

### SQS Access

**Send Messages**:
```hcl
{
  "Action": ["sqs:SendMessage"],
  "Resource": "queue-arn"
}
```

**Receive & Delete**:
```hcl
{
  "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"],
  "Resource": "queue-arn"
}
```

### Secrets Manager

**Read Secrets**:
```hcl
{
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": "secret-arn"
}
```

### SNS

**Publish Messages**:
```hcl
{
  "Action": ["sns:Publish"],
  "Resource": "topic-arn"
}
```

## Security Best Practices

### 1. Least Privilege Principle

✅ **Do**: Scope permissions to specific resources
```hcl
Resource = "arn:aws:s3:::my-specific-bucket/*"
```

❌ **Don't**: Use wildcards for all resources
```hcl
Resource = "*"  # Too permissive!
```

### 2. Separate Policies by Service

✅ **Do**: Create one policy per service
```hcl
aws_iam_policy.lambda_s3_access
aws_iam_policy.lambda_dynamodb_access
```

✅ Benefits:
- Easier to audit
- Reusable across functions
- Clear permission boundaries

### 3. Use Specific Actions

✅ **Do**: List only required actions
```hcl
Action = ["s3:GetObject", "s3:HeadObject"]
```

❌ **Don't**: Use wildcards
```hcl
Action = "s3:*"  # Too broad!
```

### 4. Resource-Level Restrictions

Use conditions to further restrict access:

```hcl
{
  "Effect": "Allow",
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::bucket/*",
  "Condition": {
    "StringEquals": {
      "s3:ExistingObjectTag/Environment": "production"
    }
  }
}
```

## Monitoring

### View IAM Role Permissions

Check attached policies:
```bash
ROLE=$(terraform output -raw lambda_role_name)

aws iam list-attached-role-policies --role-name $ROLE
```

View inline policies:
```bash
aws iam list-role-policies --role-name $ROLE
```

### Test Permissions

Test S3 access:
```bash
# This should succeed (Lambda has GetObject permission)
aws s3api head-object --bucket $BUCKET --key test.txt

# This should fail (Lambda doesn't have DeleteObject permission)
aws s3api delete-object --bucket $BUCKET --key test.txt
```

### CloudWatch Logs for Permission Errors

Permission denied errors appear as:

```
[ERROR] ClientError: An error occurred (AccessDenied) when calling the GetObject operation: Access Denied
```

Check logs:
```bash
aws logs tail /aws/lambda/$(terraform output -raw lambda_function_name) --follow
```

## Cost Estimation

Approximate monthly costs (us-west-2):
- Lambda (arm64, 10K invocations, 256MB, 2s avg): ~$0.17
- DynamoDB (PAY_PER_REQUEST, 10K writes): ~$1.25
- S3 (1GB storage, 10K GET requests): ~$0.03
- CloudWatch Logs (1GB): ~$0.50
- CloudWatch Alarms (1 alarm): ~$0.10

**Total: ~$2.05/month** for 10,000 invocations

## Cleanup

Remove all resources:

```bash
# Empty S3 bucket first (if versioning enabled)
aws s3 rm s3://$(terraform output -raw s3_bucket_name) --recursive

# Destroy infrastructure
terraform destroy
```

**Note**: DynamoDB tables are deleted immediately. Enable point-in-time recovery for production use.

## Extending This Example

### Add More Services

Add policies for additional services:

```hcl
# SQS policy
resource "aws_iam_policy" "lambda_sqs_access" {
  policy = jsonencode({
    Statement = [{
      Effect = "Allow"
      Action = ["sqs:SendMessage"]
      Resource = aws_sqs_queue.notifications.arn
    }]
  })
}

# Attach to Lambda
module "file_processor" {
  additional_iam_policy_arns = [
    aws_iam_policy.lambda_s3_access.arn,
    aws_iam_policy.lambda_dynamodb_access.arn,
    aws_iam_policy.lambda_sqs_access.arn  # Add SQS
  ]
}
```

### Use Existing Policies

Attach AWS managed policies:

```hcl
module "file_processor" {
  additional_iam_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonDynamoDBReadOnlyAccess"
  ]
}
```

**Warning**: AWS managed policies are often overly permissive. Prefer custom policies.

### Cross-Account Access

Access resources in another AWS account:

```hcl
resource "aws_iam_policy" "cross_account_s3" {
  policy = jsonencode({
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject"]
      Resource = "arn:aws:s3:::other-account-bucket/*"
    }]
  })
}

# Also need to configure bucket policy in the other account
```

## Troubleshooting

### Access Denied Errors

1. **Check IAM policy is attached**:
   ```bash
   aws iam list-attached-role-policies --role-name $(terraform output -raw lambda_role_name)
   ```

2. **Verify policy document**:
   ```bash
   aws iam get-policy-version \
     --policy-arn <policy-arn> \
     --version-id v1
   ```

3. **Test with IAM Policy Simulator**:
   ```bash
   aws iam simulate-principal-policy \
     --policy-source-arn $(terraform output -raw lambda_role_arn) \
     --action-names s3:GetObject \
     --resource-arns arn:aws:s3:::bucket/key
   ```

### Policy Too Large

IAM role policy size limits:
- Managed policies: 10 per role
- Inline policies: Not used by this module
- Policy document: 6,144 characters max per policy

If hitting limits, consolidate policies.

### Dependency Issues

Ensure policies exist before Lambda:

```hcl
module "file_processor" {
  # ... configuration

  depends_on = [
    aws_iam_policy.lambda_s3_access,
    aws_iam_policy.lambda_dynamodb_access
  ]
}
```

## Related Examples

- [Immediate Alerts](../immediate-alerts/) - For critical operations
- [Threshold Alerts](../threshold-alerts/) - For fault-tolerant operations

## References

- [Module Documentation](../../README.md)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [Lambda Execution Role](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html)
- [IAM Policy Examples](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_examples.html)