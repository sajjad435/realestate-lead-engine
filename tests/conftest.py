import os
import pytest

@pytest.fixture(autouse=True)
def set_test_env():
    os.environ["TEST_MODE"] = "1"
    yield
