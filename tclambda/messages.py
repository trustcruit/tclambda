import json
from dataclasses import dataclass
from typing import Optional

import boto3

s3client = boto3.client("s3")


@dataclass(init=False)
class Message:
    func_name: Optional[str]
    args: tuple
    kwargs: dict
    result_store: Optional[str]
    s3_bucket: str

    def __init__(self, message_dict: dict, s3_bucket: str):
        self.s3_bucket = s3_bucket

        if "proxy" in message_dict:
            obj = s3client.get_object(Bucket=self.s3_bucket, Key=message_dict["proxy"])
            message_dict = json.load(obj["Body"])

        self.func_name = message_dict.get("function")
        self.args = message_dict.get("args", ())
        self.kwargs = message_dict.get("kwargs", {})
        self.result_store = message_dict.get("result_store")

    def store_result(self, result: dict, json_encoder_class=json.JSONEncoder):
        """Serialize result to a JSON formatted string and save the string in S3"""

        result_body = json.dumps(result, cls=json_encoder_class)

        if self.result_store:
            s3client.put_object(
                Bucket=self.s3_bucket, Key=self.result_store, Body=result_body
            )
