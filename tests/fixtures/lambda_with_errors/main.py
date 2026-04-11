"""
Lambda function that can trigger errors for alarm testing.

This module provides a Lambda handler that can be configured to fail
on demand, used for testing CloudWatch alarm functionality.
"""

import json


class IntentionalTestError(Exception):
    """
    Custom exception raised for testing error monitoring.

    This exception is intentionally raised when the Lambda function
    receives a request to simulate an error condition.
    """

    pass


def lambda_handler(event, context):
    """
    Handle Lambda invocation with optional error simulation.

    This handler checks the event for a 'force_error' flag and raises
    an exception if present. Used for testing error monitoring and
    CloudWatch alarm triggering.

    :param dict event: Lambda event object containing request data
    :param LambdaContext context: Lambda context object with runtime information
    :return: Response dictionary with status code and message
    :rtype: dict
    :raises IntentionalTestError: If event contains 'force_error': True

    :Example:

    Success case:

    >>> lambda_handler({'message': 'hello'}, None)
    {'statusCode': 200, 'body': '{"success": true, "message": "Function executed successfully"}'}

    Error case:

    >>> lambda_handler({'force_error': True}, None)  # doctest: +SKIP
    Traceback (most recent call last):
        ...
    IntentionalTestError: Intentional error for testing alarm functionality
    """
    # Check if we should force an error
    if event.get("force_error", False):
        raise IntentionalTestError("Intentional error for testing alarm functionality")

    # Normal successful execution
    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "success": True,
                "message": "Function executed successfully",
                "event": event,
            }
        ),
    }
