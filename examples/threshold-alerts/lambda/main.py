"""
Lambda function for threshold alert strategy demonstration.

This example shows how the threshold alert strategy only triggers CloudWatch
alarms when the error rate exceeds a configured percentage, making it suitable
for fault-tolerant operations where occasional failures are acceptable.
"""

import json
import logging
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Fetch and process data from external APIs.

    This represents a fault-tolerant batch processing function where
    occasional failures (network timeouts, temporary API issues) are expected
    and acceptable. Alerts should only trigger when the error rate exceeds
    a threshold (e.g., 5% of invocations failing).

    Args:
        event: Lambda event object containing:
            - url: URL to fetch data from
            - timeout: Request timeout in seconds (default: 10)
        context: Lambda context object

    Returns:
        dict: Response with statusCode and body

    Raises:
        ValueError: If URL is missing or invalid
        HTTPError: If HTTP request fails
        URLError: If network error occurs
    """
    logger.info(f"Processing data fetch request: {json.dumps(event)}")

    try:
        # Validate input
        url = event.get("url")
        if not url:
            raise ValueError("Missing required field: url")

        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL protocol: {url}")

        timeout = int(event.get("timeout", 10))

        # Fetch data from external API
        logger.info(f"Fetching data from: {url}")

        request = Request(
            url,
            headers={"User-Agent": "DataIngestionLambda/1.0"}
        )

        with urlopen(request, timeout=timeout) as response:
            status_code = response.getcode()
            data = response.read().decode("utf-8")

            logger.info(f"Successfully fetched data: {status_code}, {len(data)} bytes")

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "success": True,
                    "url": url,
                    "status_code": status_code,
                    "data_size": len(data),
                    "message": "Data fetched successfully"
                })
            }

    except ValueError as e:
        # Validation errors - these are NOT expected, count as errors
        logger.error(f"Validation error: {str(e)}")
        raise

    except HTTPError as e:
        # HTTP errors (4xx, 5xx) - expected occasionally, will be retried
        logger.warning(f"HTTP error fetching {url}: {e.code} {e.reason}")
        raise

    except URLError as e:
        # Network errors - expected occasionally in distributed systems
        logger.warning(f"Network error fetching {url}: {str(e.reason)}")
        raise

    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error: {str(e)}")
        raise