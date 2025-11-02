"""
Lambda function demonstrating custom IAM permissions.

This example shows how to create a Lambda function that needs additional
IAM permissions beyond the basic execution role (CloudWatch Logs).
This function requires S3 and DynamoDB access.
"""

import json
import logging
import os
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')


def lambda_handler(event, context):
    """
    Process file uploads and record metadata in DynamoDB.

    This function demonstrates a Lambda that requires multiple AWS service
    permissions: S3 for file operations and DynamoDB for metadata storage.

    Args:
        event: Lambda event object containing:
            - bucket: S3 bucket name
            - key: S3 object key
            - table_name: DynamoDB table name
        context: Lambda context object

    Returns:
        dict: Response with statusCode and body

    Raises:
        ValueError: If required parameters are missing
        ClientError: If AWS API calls fail
    """
    logger.info(f"Processing file upload event: {json.dumps(event)}")

    try:
        # Validate inputs
        bucket = event.get("bucket")
        key = event.get("key")
        table_name = event.get("table_name") or os.environ.get("TABLE_NAME")

        if not bucket:
            raise ValueError("Missing required field: bucket")
        if not key:
            raise ValueError("Missing required field: key")
        if not table_name:
            raise ValueError("Missing required field: table_name or TABLE_NAME env var")

        # Get file metadata from S3
        logger.info(f"Fetching metadata for s3://{bucket}/{key}")

        try:
            s3_response = s3_client.head_object(Bucket=bucket, Key=key)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise ValueError(f"Object not found: s3://{bucket}/{key}")
            raise

        # Extract metadata
        file_size = s3_response['ContentLength']
        content_type = s3_response.get('ContentType', 'unknown')
        last_modified = s3_response['LastModified'].isoformat()
        etag = s3_response['ETag'].strip('"')

        logger.info(f"File metadata: size={file_size}, type={content_type}")

        # Store metadata in DynamoDB
        logger.info(f"Storing metadata in DynamoDB table: {table_name}")

        table = dynamodb.Table(table_name)
        item = {
            'file_id': f"{bucket}/{key}",
            'bucket': bucket,
            'key': key,
            'size': file_size,
            'content_type': content_type,
            'last_modified': last_modified,
            'etag': etag,
            'processed_at': datetime.utcnow().isoformat(),
            'processed_by': context.function_name
        }

        table.put_item(Item=item)

        logger.info(f"Successfully processed file: {bucket}/{key}")

        # Return success response
        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "file_id": item['file_id'],
                "metadata": {
                    "size": file_size,
                    "content_type": content_type,
                    "etag": etag
                },
                "message": "File metadata processed and stored successfully"
            })
        }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "success": False,
                "error": str(e)
            })
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"AWS API error ({error_code}): {error_message}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise