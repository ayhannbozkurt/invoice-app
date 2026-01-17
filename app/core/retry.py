"""Retry and fallback decorators for resilient operations."""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Optional, Type, TypeVar, Union
import time

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry

    Example:
        @with_retry(max_attempts=3, delay=1.0)
        def flaky_operation():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )

            raise last_exception

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            current_delay = delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"{func.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )

            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def with_fallback(
    fallback_fn: Callable[..., T],
    exceptions: tuple = (Exception,),
    log_fallback: bool = True,
) -> Callable:
    """
    Fallback decorator - calls fallback function if main function fails.

    Args:
        fallback_fn: Function to call if main function fails
        exceptions: Tuple of exceptions to catch
        log_fallback: Whether to log when fallback is used

    Example:
        def backup_ocr(image_path):
            # Alternative OCR implementation
            ...

        @with_fallback(backup_ocr)
        def primary_ocr(image_path):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_fallback:
                    logger.warning(
                        f"{func.__name__} failed: {e}. Using fallback: {fallback_fn.__name__}"
                    )
                return fallback_fn(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                if log_fallback:
                    logger.warning(
                        f"{func.__name__} failed: {e}. Using fallback: {fallback_fn.__name__}"
                    )
                if asyncio.iscoroutinefunction(fallback_fn):
                    return await fallback_fn(*args, **kwargs)
                return fallback_fn(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
