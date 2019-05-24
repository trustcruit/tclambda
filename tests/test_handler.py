import json
import os
import unittest
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

import boto3

import tclambda

s3client = boto3.client("s3")

TC_THIS_BUCKET = os.getenv("TC_THIS_BUCKET")


class FunctionBuilder:
    def __init__(self, function, *args, **kwargs):
        key = f"tests/{function}/{datetime.utcnow():%Y/%m/%d/%H%M%S}/{uuid4()}.json"
        self.message_body = {
            "function": function,
            "args": args,
            "kwargs": kwargs,
            "result_store": key,
        }
        self.result = tclambda.function.LambdaResult(TC_THIS_BUCKET, key)

    @property
    def sqs(self):
        return {"Records": [{"body": json.dumps(self.message_body)}]}


class ProxyFunctionBuilder:
    def __init__(self, function, *args, **kwargs):
        key = f"{function}/{datetime.utcnow():%Y/%m/%d/%H%M%S}/{uuid4()}.json"
        result_store = f"tests/results/{key}"
        proxy_store = f"tests/proxy/{key}"
        self.message_body = {
            "function": function,
            "args": args,
            "kwargs": kwargs,
            "result_store": result_store,
        }
        self.proxy_body = {"proxy": proxy_store}
        s3client.put_object(
            Bucket=TC_THIS_BUCKET, Key=proxy_store, Body=json.dumps(self.message_body)
        )
        self.result = tclambda.function.LambdaResult(TC_THIS_BUCKET, result_store)

    @property
    def sqs(self):
        return {"Records": [{"body": json.dumps(self.proxy_body)}]}


@dataclass
class LambdaContext:
    function_name: str

    def get_remaining_time_in_millis(self):
        return 100000


def my_test_function():
    return "success"


async def my_async_test_function():
    return "async success"


def my_test_exception():
    raise ValueError("This is a value error")


def my_invalid_return_value():
    return datetime(2019, 5, 3)


class TestHandler(unittest.TestCase):
    def setUp(self):
        self.app = tclambda.LambdaHandler()

    def test_has_ping(self):
        self.assertIn("ping", self.app.functions)

    def test_register(self):
        function_after_register = self.app.register()(my_test_function)
        self.assertIs(function_after_register, my_test_function)
        self.assertIn("my_test_function", self.app.functions)

    def test_register_name(self):
        self.app.register("a_function")(my_test_function)
        self.assertIn("a_function", self.app.functions)
        self.assertNotIn("my_test_function", self.app.functions)

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_call_handler_sqs_ping(self):
        f = FunctionBuilder("ping")
        self.app(f.sqs, LambdaContext(function_name="tclambda-test"))
        self.assertEqual(f.result.result(delay=1, max_attempts=3), "pong")

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_call_handler_message(self):
        f = FunctionBuilder("ping")
        self.app(f.message_body, LambdaContext(function_name="tclambda-test"))
        self.assertEqual(f.result.result(delay=1, max_attempts=3), "pong")

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_async_function(self):
        self.app.register()(my_async_test_function)
        f = FunctionBuilder("my_async_test_function")
        self.app(f.message_body, LambdaContext(function_name="tclambda-test"))
        self.assertEqual(f.result.result(delay=1, max_attempts=3), "async success")

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_timeout_error(self):
        with self.assertRaises(TimeoutError):
            f = FunctionBuilder("my_async_test_function")
            f.result.result(delay=0.01, max_attempts=1)

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_cached_result(self):
        f = FunctionBuilder("ping")
        self.app(f.message_body, LambdaContext(function_name="tclambda-test"))
        self.assertEqual(f.result.result(delay=1, max_attempts=3), "pong")
        self.assertEqual(f.result.result(delay=1, max_attempts=0), "pong")

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_exception(self):
        self.app.register()(my_test_exception)
        f = FunctionBuilder("my_test_exception")
        self.app(f.message_body, LambdaContext(function_name="tclambda-test"))
        with self.assertRaisesRegex(Exception, "ValueError.*This is a value error"):
            f.result.result(delay=1, max_attempts=3)

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_typeerror_result(self):
        self.app.register()(my_invalid_return_value)
        f = FunctionBuilder("my_invalid_return_value")
        self.app(f.message_body, LambdaContext(function_name="tclambda-test"))
        with self.assertRaisesRegex(
            Exception, "TypeError.*Object of type datetime is not JSON serializable"
        ):
            f.result.result(delay=1, max_attempts=3)

    def test_sqs_decode_error(self):
        self.app(
            {"Records": [{"body": "invalid json"}]},
            LambdaContext(function_name="tclambda-test"),
        )

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_missing_function(self):
        f = FunctionBuilder("missing_function")
        self.app(f.message_body, LambdaContext(function_name="tclambda-test"))
        with self.assertRaisesRegex(
            Exception, "TypeError.*Function missing_function does not exist"
        ):
            f.result.result(delay=1, max_attempts=3)

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_missing_function_key(self):
        f = FunctionBuilder("missing_function")
        f.message_body.pop("function")
        self.app(f.sqs, LambdaContext(function_name="tclambda-test"))
        with self.assertRaisesRegex(
            Exception, 'TypeError.*Message does not contain key "function"'
        ):
            f.result.result(delay=1, max_attempts=3)

    @unittest.skipIf(TC_THIS_BUCKET is None, "TC_THIS_BUCKET is None")
    def test_proxy_result(self):
        f = ProxyFunctionBuilder("ping")
        self.app(f.message_body, LambdaContext(function_name="tclambda-test"))
        self.assertEqual(f.result.result(delay=1, max_attempts=3), "pong")
