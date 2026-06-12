"""Lambda fixture that imports pyarrow (manylinux_2_28-only wheels >= 21)."""

import json

import pyarrow


def lambda_handler(event, context):
    """Return the installed pyarrow version to prove the wheel loads at runtime."""
    return {
        "statusCode": 200,
        "body": json.dumps({"success": True, "pyarrow_version": pyarrow.__version__}),
    }
