"""Default directory allow-list for the filesystem tools."""

from __future__ import annotations

import os
from typing import List, Optional


def resolve_allowed_dirs(allowed_dirs: Optional[List[str]]) -> List[str]:
    """Return *allowed_dirs*, or ``[security] allowed_dirs`` from the config.

    An explicit empty list keeps the historical unrestricted behaviour. Invalid
    or unreadable configuration must never silently remove a restriction.
    """
    if allowed_dirs is None:
        from openjarvis.core.config import load_config

        allowed_dirs = load_config().security.allowed_dirs
    if not isinstance(allowed_dirs, (list, tuple)) or any(
        not isinstance(directory, (str, os.PathLike))
        or not isinstance(os.fspath(directory), str)
        or not os.fspath(directory).strip()
        for directory in allowed_dirs
    ):
        raise ValueError("security.allowed_dirs must be a list of non-empty paths")
    return [os.fspath(directory) for directory in allowed_dirs]
