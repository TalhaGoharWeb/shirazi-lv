"""Per-test isolation for the secrets store.

The OS credential store (or its test double) is process-global. Without
isolation, one test's saved key leaks into the next test's get_*_key()
call. This autouse fixture swaps in a fresh in-memory backend before
every test.
"""
import pytest

try:
    from core import secrets_store as _ss
    _HAS_SS = True
except Exception:
    _HAS_SS = False


@pytest.fixture(autouse=True)
def _isolate_secrets():
    if _HAS_SS:
        try:
            _ss.use_memory_backend()
        except Exception:
            pass
    yield
