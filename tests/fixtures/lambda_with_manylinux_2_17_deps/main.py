"""Lambda fixture that imports cffi (manylinux_2_17-only wheels) — issue #31."""

import json

import cffi


def lambda_handler(event, context):
    """Return the installed cffi version to prove the compiled wheel loads.

    Importing cffi and instantiating ``FFI`` requires the compiled
    ``_cffi_backend`` extension, so a successful invocation proves the
    manylinux_2_17 binary wheel was installed and runs on the Amazon Linux
    2023 runtime (glibc 2.34).
    """
    ffi = cffi.FFI()
    ffi.cdef("int add(int, int);")  # exercises the compiled _cffi_backend extension
    return {
        "statusCode": 200,
        "body": json.dumps({"success": True, "cffi_version": cffi.__version__}),
    }
