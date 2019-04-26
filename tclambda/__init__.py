"""AWS Lambda Library"""

from .function import LambdaFunction
from .handlers import LambdaHandler

__version__ = "0.0.1"
__all__ = ("LambdaFunction", "LambdaHandler")
