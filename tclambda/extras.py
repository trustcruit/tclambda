import time
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class Value:
    value: float


@contextmanager
def timeme():
    start_time = time.monotonic()
    value = Value(0)
    try:
        yield value
    finally:
        value.value = time.monotonic() - start_time
