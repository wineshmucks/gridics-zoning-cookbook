"""Compatibility helpers for third-party constructor differences."""

from __future__ import annotations

import re
from typing import Any


def build_with_supported_kwargs(factory, **kwargs: Any):
    """Instantiate a class or callable, dropping unsupported keyword args."""
    filtered_kwargs = dict(kwargs)
    while True:
        try:
            return factory(**filtered_kwargs)
        except TypeError as exc:
            match = re.search(r"unexpected keyword argument '([^']+)'", str(exc))
            if not match:
                raise
            unsupported_key = match.group(1)
            if unsupported_key not in filtered_kwargs:
                raise
            filtered_kwargs.pop(unsupported_key)
