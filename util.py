from typing import Never


def assert_never(arg: Never) -> Never:
    raise AssertionError("Expected code to be unreachable")
