#!/usr/bin/env bash

set -e

# Check for required commands
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: jq is required but not installed" >&2
    echo "Install jq: https://stedolan.github.io/jq/download/" >&2
    echo "  - Ubuntu/Debian: sudo apt-get install jq" >&2
    echo "  - macOS: brew install jq" >&2
    echo "  - Amazon Linux: sudo yum install jq" >&2
    exit 1
fi

# Display current caller identity
echo "Current AWS identity:"
CURRENT_IDENTITY=$(aws sts get-caller-identity --output json)
echo "$CURRENT_IDENTITY"

# Extract current role ARN from caller identity using jq
CURRENT_ARN=$(echo "$CURRENT_IDENTITY" | jq -r '.Arn')

# Extract provider role information
caller_account_id="${caller_account_id}"
caller_role_name=$(echo "${caller_arn}" | awk -F/ '{ print $2}')
caller_role_arn="arn:aws:iam::$caller_account_id:role/$caller_role_name"

echo "Discovered provider role ARN = $caller_role_arn"

# Check if we need to assume the role
# Only assume if:
# 1. Current ARN doesn't contain the role name (not using a role), OR
# 2. Current ARN contains a different role than expected
NEED_ASSUME=false

if echo "$CURRENT_ARN" | grep -q "assumed-role/$caller_role_name"; then
    echo "Already using the correct role, skipping role assumption"
else
    echo "Current credentials are different from provider role"
    NEED_ASSUME=true
fi

# Assume the provider role if needed
if [ "$NEED_ASSUME" = true ]; then
    echo "Assuming provider role..."
    CREDS=$(aws sts assume-role \
      --role-arn "$caller_role_arn" \
      --role-session-name terraform-s3-wait \
      --output json)

    # Export assumed role credentials using jq
    export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | jq -r '.Credentials.AccessKeyId')
    export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | jq -r '.Credentials.SecretAccessKey')
    export AWS_SESSION_TOKEN=$(echo "$CREDS" | jq -r '.Credentials.SessionToken')

    echo "After assuming role:"
    aws sts get-caller-identity
fi

echo "Waiting for S3 object to become available..."
echo "Bucket: ${bucket_name}"
echo "Key: ${object_key}"

# Wait for S3 object to be available
while true; do
  if aws s3api head-object \
    --bucket "${bucket_name}" \
    --key "${object_key}" \
    >/dev/null 2>&1; then
    echo "S3 object is available"
    break
  fi
  echo "Waiting until the object is available..."
  sleep 1
done

echo "S3 object verification completed successfully"
