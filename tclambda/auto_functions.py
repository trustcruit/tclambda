import os

from .function import LambdaFunction

__path__ = None


def __getattr__(module) -> LambdaFunction:
    queue = os.getenv(f"TC_{module.upper()}_QUEUE")
    bucket = os.getenv(f"TC_{module.upper()}_BUCKET")
    print(f"Looking for lambda function {module}")
    if not queue:
        raise AttributeError(f"Couldn't automatically create LambdaFunction {module}")
    return LambdaFunction(queue, bucket)
