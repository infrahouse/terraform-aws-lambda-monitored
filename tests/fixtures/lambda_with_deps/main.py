"""
Lambda function with external dependencies for testing.

This module demonstrates a Lambda function that uses the requests library
to make HTTP calls. Used for testing dependency packaging with platform-specific wheels.
"""

import json
import requests


def lambda_handler(event, context):
    """
    Handle Lambda invocation with HTTP request to external API.

    Makes a test HTTP request to httpbin.org to verify that the requests
    library is properly packaged with platform-specific wheels.

    :param dict event: Lambda event object containing request data
    :param LambdaContext context: Lambda context object with runtime information
    :return: Response dictionary with status code and API response
    :rtype: dict
    :raises requests.RequestException: If HTTP request fails

    :Example:

    >>> lambda_handler({}, None)  # doctest: +SKIP
    {'statusCode': 200, 'body': '{"success": true, "requests_version": "2.31.0"}'}
    """
    try:
        # Make a simple GET request to verify requests library works
        response = requests.get("https://httpbin.org/get", timeout=5)
        response.raise_for_status()

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "success": True,
                    "requests_version": requests.__version__,
                    "status_code": response.status_code,
                }
            ),
        }
    except requests.RequestException as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"success": False, "error": str(e)}),
        }
