**DO NOT USE, THIS IS PRE-ALPHA, HAS NO TESTS, NO MONITORING, BAD LOGGING**

# tclambda
AWS Lambda calling library

Works together with functions defined in [tc-sam-cli](https://pypi.org/project/tc-sam-cli/)

## Configuration

Configuration is primarely done by environmental variables.

```sh
TC_NUMPY_QUEUE="https://sqs.eu-west-1.amazonaws.com/12345/NumpySqs"
TC_NUMPY_BUCKET="s3-result-bucket"
```

```python
from tclambda.auto_functions import numpy

assert numpy.ping().result() == "pong"  # check if the sqs and s3 are accessible
```
