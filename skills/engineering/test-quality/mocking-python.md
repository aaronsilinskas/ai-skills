# Mocking in Python

## Patch where it's looked up, not where it's defined

`unittest.mock.patch` (and `pytest-mock`'s `mocker.patch`) replace a name in
the *importing* module's namespace, not in the module where the name was
originally defined. Patching the definition site silently does nothing if the
caller imported the name directly.

```python
# payments.py
from stripe_client import StripeClient

def process_payment(order):
    client = StripeClient()
    return client.charge(order.total)
```

```python
# WRONG: patches stripe_client.StripeClient, but payments.py already
# holds its own reference via `from stripe_client import StripeClient`
mocker.patch("stripe_client.StripeClient")

# RIGHT: patch the name where it's used
mocker.patch("payments.StripeClient")
```
