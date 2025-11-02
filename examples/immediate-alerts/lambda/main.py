"""
Lambda function for immediate alert strategy demonstration.

This example shows how the immediate alert strategy triggers CloudWatch alarms
on any Lambda error, making it suitable for critical operations where even a
single failure needs immediate attention.
"""

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Process critical order transactions.

    This represents a critical business function where any error should
    trigger immediate notification to the operations team.

    Args:
        event: Lambda event object containing order data
        context: Lambda context object

    Returns:
        dict: Response with statusCode and body

    Raises:
        ValueError: If order validation fails
        RuntimeError: If payment processing fails
    """
    logger.info(f"Processing order request: {json.dumps(event)}")

    try:
        # Validate order data
        if not event.get("order_id"):
            raise ValueError("Missing required field: order_id")

        if not event.get("amount"):
            raise ValueError("Missing required field: amount")

        amount = float(event["amount"])
        if amount <= 0:
            raise ValueError(f"Invalid amount: {amount}")

        # Simulate payment processing
        order_id = event["order_id"]
        logger.info(f"Processing payment for order {order_id}: ${amount}")

        # Return success response
        response = {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "order_id": order_id,
                "amount": amount,
                "status": "processed",
                "message": "Order processed successfully"
            })
        }

        logger.info(f"Order {order_id} processed successfully")
        return response

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise  # Re-raise to trigger CloudWatch alarm

    except Exception as e:
        logger.error(f"Unexpected error processing order: {str(e)}")
        raise RuntimeError(f"Payment processing failed: {str(e)}")