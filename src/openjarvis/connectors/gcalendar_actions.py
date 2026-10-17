"""gcalendar_actions — Google Calendar event creation and duplicate checking.

Isolates write actions for Google Calendar to keep read-only sync modules intact.
The only write API call performed is events.insert (POST).
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

import httpx

from openjarvis.connectors.gcalendar import (
    _DEFAULT_CREDENTIALS_PATH,
    _GCAL_API_BASE,
    _gcal_api_events_list,
    resolve_google_credentials,
)
from openjarvis.connectors.google_auth import call_with_refresh

logger = logging.getLogger(__name__)


def _gcal_api_event_insert(
    token: str,
    calendar_id: str,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """Insert a new calendar event resource via Calendar API v3 events.insert (POST)."""
    resp = httpx.post(
        f"{_GCAL_API_BASE}/calendars/{calendar_id}/events",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def create_calendar_event(
    body: Dict[str, Any],
    credentials_path: Optional[str] = None,
    calendar_id: str = "primary",
) -> Dict[str, Any]:
    """Create a new calendar event using call_with_refresh and events.insert."""
    path = resolve_google_credentials(credentials_path or _DEFAULT_CREDENTIALS_PATH)
    return call_with_refresh(
        _gcal_api_event_insert,
        path,
        calendar_id,
        body,
    )


def check_duplicate_event(
    title: str,
    target_dt: datetime,
    credentials_path: Optional[str] = None,
    calendar_id: str = "primary",
) -> Optional[Dict[str, Any]]:
    """Check if an active event with the same title and start time exists on that day.

    Returns the matching event dict if found, or None if no duplicate exists.
    """
    path = resolve_google_credentials(credentials_path or _DEFAULT_CREDENTIALS_PATH)
    tz = target_dt.tzinfo
    start_of_day = datetime(
        target_dt.year, target_dt.month, target_dt.day, 0, 0, 0, tzinfo=tz
    )
    time_min_str = start_of_day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        events_resp = call_with_refresh(
            _gcal_api_events_list,
            path,
            calendar_id,
            time_min=time_min_str,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 403:
            raise
        logger.warning("Failed to check duplicate events: %s", type(exc).__name__)
        return None
    except Exception as exc:
        logger.warning("Failed to check duplicate events: %s", type(exc).__name__)
        return None

    norm_title = title.strip().lower()

    for item in events_resp.get("items", []):
        if item.get("status") == "cancelled":
            continue

        item_summary = item.get("summary", "").strip().lower()
        if item_summary != norm_title:
            continue

        start = item.get("start", {})
        if "dateTime" in start:
            dt_str = start["dateTime"].replace("Z", "+00:00")
            try:
                item_dt = datetime.fromisoformat(dt_str)
                if tz is not None:
                    item_dt_local = item_dt.astimezone(tz)
                else:
                    item_dt_local = item_dt
                if item_dt_local == target_dt:
                    return item
            except (ValueError, TypeError):
                continue

    return None


__all__ = [
    "check_duplicate_event",
    "create_calendar_event",
]
