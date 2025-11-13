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

    Makes a test HTTP request to verify that the requests library is properly
    packaged with platform-specific wheels. Tries multiple HTTP testing endpoints
    for resilience against service outages.

    :param dict event: Lambda event object containing request data
    :param LambdaContext context: Lambda context object with runtime information
    :return: Response dictionary with status code and API response
    :rtype: dict

    :Example:

    >>> lambda_handler({}, None)  # doctest: +SKIP
    {'statusCode': 200, 'body': '{"success": true, "requests_version": "2.31.0"}'}
    """
    # List of HTTP testing endpoints to try (for resilience)
    endpoints = [
        "https://httpbin.org/get",
        "https://httpbun.com/get",
    ]

    errors = []

    # Try each endpoint until one succeeds
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=5)
            response.raise_for_status()

            # Success! Return immediately
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "success": True,
                        "requests_version": requests.__version__,
                        "endpoint_used": endpoint,
                        "status_code": response.status_code,
                    }
                ),
            }
        except requests.RequestException as e:
            # Record error and try next endpoint
            errors.append({"endpoint": endpoint, "error": str(e)})
            continue

    # All endpoints failed
    return {
        "statusCode": 500,
        "body": json.dumps(
            {
                "success": False,
                "error": "All HTTP test endpoints failed",
                "attempts": errors,
            }
        ),
    }
