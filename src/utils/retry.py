import time
from typing import Callable, TypeVar


T = TypeVar("T")


def with_retry(func: Callable[[], T], retries: int = 3, base_delay: float = 1.0) -> T:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            time.sleep(base_delay * (2 ** attempt))
    if last_error:
        raise last_error
    raise RuntimeError("Retry failed without exception")
