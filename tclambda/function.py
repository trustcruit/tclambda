# https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from .extras import timeme

s3client = boto3.client("s3")
sqsclient = boto3.client("sqs")

TC_QUEUE = os.getenv("TC_THIS_QUEUE")
TC_BUCKET = os.getenv("TC_THIS_BUCKET")


class LambdaFunction:
    def __init__(self, queue_url=TC_QUEUE, s3_bucket=TC_BUCKET):
        self.queue_url = queue_url
        self.s3_bucket = s3_bucket

    def __getattr__(self, function_name):
        return LambdaWrapperFunction(self.queue_url, self.s3_bucket, function_name)


class LambdaWrapperFunction:
    def __init__(self, queue_url, s3_bucket, function_name):
        self.logger = logging.getLogger("tclambda.function.LambdaFunction")
        self.queue_url = queue_url
        self.s3_bucket = s3_bucket
        self.function_name = function_name

    def __call__(self, *args, **kwargs) -> LambdaResult:
        key = f"{self.function_name}/{datetime.utcnow():%Y/%m/%d/%H%M%S}/{uuid4()}.json"
        result_store = f"results/{key}"
        proxy_store = f"proxy/{key}"
        message_body = json.dumps(
            {
                "function": self.function_name,
                "args": args,
                "kwargs": kwargs,
                "result_store": result_store,
            }
        )
        self.logger.info(
            f'Enqueing function "{self.function_name}", '
            f'result_store: "{result_store}", '
            f"message_body size: {sizeof_fmt(len(message_body))}"
        )
        if len(message_body) > 250000:  # current maximum is 262144 bytes
            self.logger.info(f"Uploading message_body as a proxy {proxy_store}")
            with timeme() as dt:
                s3client.put_object(
                    Bucket=self.s3_bucket, Key=proxy_store, Body=message_body
                )
            self.logger.info(f"Uploaded proxy in {dt.value}s")
            proxy_body = json.dumps({"proxy": proxy_store})
            sqsclient.send_message(QueueUrl=self.queue_url, MessageBody=proxy_body)
        else:
            sqsclient.send_message(QueueUrl=self.queue_url, MessageBody=message_body)
        return LambdaResult(s3_bucket=self.s3_bucket, key=result_store)


class LambdaResult:
    def __init__(self, s3_bucket, key):
        self.logger = logging.getLogger("tclambda.function.LambdaFunction")
        self.s3_bucket = s3_bucket
        self.key = key
        self.waited = False
        self._result = {}

    def _iter_wait(self, delay: float, max_attempts: int):
        if self.waited:
            return
        obj = None
        start_time = time.monotonic()
        for i in range(max_attempts):
            try:
                obj = s3client.get_object(Bucket=self.s3_bucket, Key=self.key)
                end_time = time.monotonic()
                self.logger.debug(
                    f"Found key {self.key} on {i+1} attempts and {end_time - start_time} seconds"
                )
                break
            except ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    yield i
                    continue
                raise
        if not obj:
            raise TimeoutError(
                f"Result {self.key} not found within {delay*max_attempts} seconds"
            )
        self._result = json.load(obj["Body"])
        self.waited = True

    def wait(self, delay: int = 5, max_attempts=20):
        for _ in self._iter_wait(delay, max_attempts):
            time.sleep(delay)

    async def async_wait(self, delay=5, max_attempts: int = 20):
        for _ in self._iter_wait(delay, max_attempts):
            await asyncio.sleep(delay)

    def result(self, delay: int = 5, max_attempts: int = 20):
        self.wait(delay, max_attempts)
        try:
            return self._result["result"]
        except KeyError:
            raise Exception(self._result["exception"])

    async def async_result(self, delay: int = 5, max_attempts: int = 20):
        await self.async_wait(delay, max_attempts)
        try:
            return self._result["result"]
        except KeyError:
            raise Exception(self._result["exception"])


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)
