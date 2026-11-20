"""
Lambda function that keeps writing log lines for a while.

Used to delete a function in the middle of an invocation (issue #26): Lambda stops the
invocation and flushes the lines it still holds a moment after the function is gone.
"""

import time


def lambda_handler(event: dict, context: object) -> dict:
    """
    Print a line every half second until ``event["seconds"]`` have passed.

    :param dict event: Lambda event; ``seconds`` sets how long to run (default 60)
    :param LambdaContext context: Lambda context object with runtime information
    :return: Response dictionary with the number of lines printed
    :rtype: dict
    """
    deadline = time.time() + event.get("seconds", 60)
    tick = 0
    while time.time() < deadline:
        print(f"tick {tick}", flush=True)
        tick += 1
        time.sleep(0.5)
    return {"statusCode": 200, "ticks": tick}
