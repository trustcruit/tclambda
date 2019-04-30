**DO NOT USE, THIS IS PRE-ALPHA, HAS NO TESTS, NO MONITORING, BAD LOGGING**

# tclambda
AWS Lambda calling library

Works together with functions defined in [tc-sam-cli](https://pypi.org/project/tc-sam-cli/)

## Configuration of AWS Lambda

```python
# app.py
import tclambda

from numpy.polynomial.polynomial import polyfit as np_polyfit

handler = tclambda.LambdaHandler()


@handler.register()
def polyfit(*args, **kwargs):
    return list(np_polyfit(*args, **kwargs))
```

The registered handler must return something that is json serializable.


## Usage in other projects

Configuration is primarely done by environmental variables.

```sh
TC_NUMPY_QUEUE="https://sqs.eu-west-1.amazonaws.com/12345/NumpySqs"
TC_NUMPY_BUCKET="s3-result-bucket"
```

```python
from tclambda.auto_functions import numpy

lambda_result = numpy.polyfit([1, 2], [2, 1], 1)
print(lambda_result.result())
# Output: [2.999999999999998, -0.9999999999999992]
```
