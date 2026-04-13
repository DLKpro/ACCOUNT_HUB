from __future__ import annotations

import uuid

from fastapi import HTTPException, status


def parse_uuid(value: str, label: str = "ID") -> uuid.UUID:
    """Parse a string as UUID or raise HTTP 400."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {label}",
        )
