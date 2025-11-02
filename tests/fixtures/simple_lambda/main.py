"""
Simple Lambda function for testing.

This module provides a basic Lambda handler that returns a success message.
Used for testing basic module functionality without dependencies.
"""


def lambda_handler(event, context):
    """
    Handle Lambda invocation with a simple success response.

    :param dict event: Lambda event object containing request data
    :param LambdaContext context: Lambda context object with runtime information
    :return: Response dictionary with status code and message
    :rtype: dict

    :Example:

    >>> lambda_handler({}, None)
    {'statusCode': 200, 'body': 'Hello from Lambda!'}
    """
    return {"statusCode": 200, "body": "Hello from Lambda!"}
