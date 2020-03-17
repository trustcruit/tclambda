# https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html
import asyncio
import json
import logging
import os
import traceback
from io import StringIO

import boto3

from .exceptions import RetryException
from .extras import sentry_init
from .messages import Message

sentry_init()
logging.basicConfig(level=logging.INFO)

s3client = boto3.client("s3")
cloudwatch = boto3.client("cloudwatch")

TC_THIS_BUCKET = os.getenv("TC_THIS_BUCKET")


class LambdaHandler:
    def __init__(self, json_encoder_class=json.JSONEncoder):
        self.logger = logging.getLogger("tclambda.LambdaHandler")
        self.functions = {"ping": lambda: "pong"}
        self.json_encoder_class = json_encoder_class

    def register(self, name=None):
        def wrapper(func):
            nonlocal name
            if name is None:
                name = func.__name__
            self.logger.debug(f"Registering function {func} with name {name}")
            self.functions[name] = func
            return func

        return wrapper

    def __call__(self, event, context):
        self.context = context
        self.logger.info(event)
        if "Records" in event:
            return asyncio.run(self.handle_sqs_event(event, context))
        elif "function" in event or "proxy" in event:
            return asyncio.run(self.handle_message(event, context))

    async def handle_sqs_event(self, event, context):
        handlers = []
        for record in event["Records"]:
            body = record["body"]
            try:
                message = json.loads(body)
            except json.JSONDecodeError:
                self.logger.exception(f'Couldn\'t decode body "{body}"')
            else:
                future = asyncio.ensure_future(self.handle_message(message, context))
                handlers.append(future)
        await asyncio.gather(*handlers)

    async def handle_message(self, message_dict, context):
        message = Message(message_dict, s3_bucket=TC_THIS_BUCKET)

        try:
            if not message.func_name:
                self.logger.error(
                    f'Message does not contain key "function" {message_dict}'
                )
                raise TypeError(
                    f'Message does not contain key "function" {message_dict}'
                )
            func = self.functions.get(message.func_name)
            if not func:
                available_functions = sorted(self.functions.keys())
                self.logger.error(
                    f"Function {message.func_name} is not a registered function in {available_functions}"
                )
                raise TypeError(f"Function {message.func_name} does not exist")

            if asyncio.iscoroutinefunction(func):
                result = {"result": await func(*message.args, **message.kwargs)}
            else:
                result = {"result": func(*message.args, **message.kwargs)}
        except RetryException:
            raise
        except Exception as e:
            self.logger.exception(f"An exception occured while executing {message}")
            s = StringIO()
            traceback.print_exc(file=s)
            result = {"exception": repr(e), "traceback": s.getvalue()}
        finally:
            put_metric_data(
                remaining_time_in_millis=context.get_remaining_time_in_millis(),
                TcFunctionName=message.func_name,
                LambdaFunctionName=context.function_name,
            )

        try:
            message.store_result(result, self.json_encoder_class)
        except TypeError as e:
            self.logger.exception(f"Couldn't encode result {result}")
            s = StringIO()
            traceback.print_exc(file=s)

            message.store_result(
                {"exception": repr(e), "traceback": s.getvalue()},
                self.json_encoder_class,
            )


def put_metric_data(*, remaining_time_in_millis: int, **dimensions):
    metric_dimensions = [
        {"Name": key, "Value": value}
        for key, value in dimensions.items()
        if key and value
    ]
    cloudwatch.put_metric_data(
        Namespace="tclambda",
        MetricData=[
            {
                "MetricName": "Count",
                "Value": 1,
                "Unit": "Count",
                "Dimensions": metric_dimensions,
            },
            {
                "MetricName": "RemainingMilliseconds",
                "Value": remaining_time_in_millis,
                "Unit": "Milliseconds",
                "Dimensions": metric_dimensions,
            },
        ],
    )
