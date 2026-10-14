"""AgendaAgent — voice-friendly daily schedule summary agent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from openjarvis.agents._stubs import AgentContext, AgentResult, BaseAgent
from openjarvis.core.registry import AgentRegistry

logger = logging.getLogger(__name__)

_DEFAULT_TIMEZONE = "America/Fortaleza"
_DEFAULT_SYSTEM_PROMPT = (
    "Você é um assistente pessoal prestativo e amigável. "
    "Responda sempre em português do Brasil, de forma concisa e natural para voz. "
    "Nunca use o termo 'Sir' nem formalidades excessivas."
)

_IGNORED_CALENDAR_ID_SUBSTRINGS = (
    "#contacts@group.v.calendar.google.com",
    "#holiday",
)


def is_agenda_request(text: str) -> bool:
    """Return True if the text asks for a daily agenda/calendar summary."""
    t = text.lower()
    patterns = [
        r"\bresum(a|e|ir|o)\b.*\b(dia|hoje|amanh[aã]|agenda)\b",
        r"\b(o que|qual)\b.*(tenho|temos|tem|h[aá]).*\b(hoje|amanh[aã]|programado|agendado)\b",
        r"\bminha agenda\b",
        r"\bagenda\b.*\b(de hoje|de amanh[aã]|para hoje|para amanh[aã]|pra hoje|pra amanh[aã])\b",
        r"\b(meus )?compromissos\b",
        r"\b(meus )?eventos\b",
        r"\bprograma[cç][aã]o\b.*\b(de hoje|de amanh[aã]|hoje|amanh[aã])\b",
        r"^\s*agenda\s*$",
    ]
    return any(re.search(p, t) for p in patterns)


def is_tomorrow_request(text: str) -> bool:
    """Return True if the request specifically refers to tomorrow."""
    t = text.lower()
    return bool(re.search(r"\bamanh[aã]\b", t))


def is_ignored_calendar(cal_id: str, summary: str = "", description: str = "") -> bool:
    """Check if calendar is a birthday or holiday calendar by its ID."""
    cal_id_lower = cal_id.lower()
    return any(sub in cal_id_lower for sub in _IGNORED_CALENDAR_ID_SUBSTRINGS)


def is_ignored_event(title: str = "", event_type: str = "") -> bool:
    """Check if an individual event is a system birthday event by eventType."""
    return event_type.lower() == "birthday"




def format_agenda_phrase(events: List[Dict[str, Any]], is_tomorrow: bool) -> str:
    """Format the list of events into a concise spoken sentence in Portuguese."""
    day_label = "amanhã" if is_tomorrow else "hoje"
    if not events:
        return f"Você não tem nenhum compromisso na agenda {day_label}."

    items_str: List[str] = []
    for ev in events:
        title = ev.get("title", "(Sem título)")
        if ev.get("is_all_day"):
            items_str.append(f"o dia todo, {title}")
        else:
            time_str = ev.get("time_str", "")
            if time_str:
                items_str.append(f"às {time_str}, {title}")
            else:
                items_str.append(title)

    count = len(events)
    termo = "compromisso" if count == 1 else "compromissos"
    if count == 1:
        return f"Para {day_label}, você tem 1 {termo}: {items_str[0]}."
    elif count == 2:
        return f"Para {day_label}, você tem 2 {termo}: {items_str[0]} e {items_str[1]}."
    else:
        all_but_last = "; ".join(items_str[:-1])
        return f"Para {day_label}, você tem {count} {termo}: {all_but_last}; e {items_str[-1]}."


@AgentRegistry.register("agenda")
class AgendaAgent(BaseAgent):
    """Personal agenda agent that summarizes Google Calendar events in Portuguese."""

    agent_id = "agenda"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._timezone_name = kwargs.pop("timezone", _DEFAULT_TIMEZONE)
        super().__init__(*args, **kwargs)

    def _fetch_events_for_date(
        self,
        target_date: Any,
        tz: ZoneInfo,
    ) -> List[Dict[str, Any]]:
        """Fetch and filter events for a specific calendar date."""
        from openjarvis.connectors.gcalendar import (
            GCalendarConnector,
            _gcal_api_calendars_list,
            _gcal_api_events_list,
        )
        from openjarvis.connectors.google_auth import call_with_refresh

        connector = GCalendarConnector()
        if not connector.is_connected():
            raise RuntimeError("gcalendar_not_connected")

        try:
            calendars_resp = call_with_refresh(
                _gcal_api_calendars_list, connector._credentials_path
            )
        except Exception as exc:
            logger.error("Failed to fetch calendar list: %s", exc)
            raise

        calendars = calendars_resp.get("items", [])
        start_of_day = datetime(
            target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=tz
        )
        time_min_str = start_of_day.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        matching_events: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()

        for cal in calendars:
            cal_id = cal.get("id", "")
            if not cal_id:
                continue
            if is_ignored_calendar(
                cal_id, cal.get("summary", ""), cal.get("description", "")
            ):
                continue

            try:
                events_resp = call_with_refresh(
                    _gcal_api_events_list,
                    connector._credentials_path,
                    cal_id,
                    time_min=time_min_str,
                )
            except Exception as exc:
                logger.warning("Failed to fetch events for calendar %s: %s", cal_id, exc)
                continue

            for item in events_resp.get("items", []):
                evt_id = item.get("id", "")
                if evt_id and evt_id in seen_ids:
                    continue
                if item.get("status") == "cancelled":
                    continue

                title = item.get("summary", "").strip() or "(Sem título)"
                event_type = item.get("eventType", "")
                if is_ignored_event(title, event_type):
                    continue

                start = item.get("start", {})
                end = item.get("end", {})

                # All-day event check
                if "date" in start:
                    try:
                        start_d = datetime.strptime(start["date"], "%Y-%m-%d").date()
                        end_d = (
                            datetime.strptime(end["date"], "%Y-%m-%d").date()
                            if "date" in end
                            else start_d + timedelta(days=1)
                        )
                    except (ValueError, TypeError):
                        continue

                    if start_d <= target_date < end_d:
                        if evt_id:
                            seen_ids.add(evt_id)
                        matching_events.append({
                            "title": title,
                            "is_all_day": True,
                            "time_str": "",
                            "sort_dt": datetime(
                                target_date.year,
                                target_date.month,
                                target_date.day,
                                0,
                                0,
                                tzinfo=tz,
                            ),
                        })
                elif "dateTime" in start:
                    dt_str = start["dateTime"].replace("Z", "+00:00")
                    try:
                        dt = datetime.fromisoformat(dt_str)
                    except (ValueError, TypeError):
                        continue

                    dt_local = dt.astimezone(tz)
                    if dt_local.date() == target_date:
                        if evt_id:
                            seen_ids.add(evt_id)
                        matching_events.append({
                            "title": title,
                            "is_all_day": False,
                            "time_str": dt_local.strftime("%H:%M"),
                            "sort_dt": dt_local,
                        })

        # Sort chronologically by start time
        matching_events.sort(key=lambda x: x["sort_dt"])
        return matching_events[:5]

    def run(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        """Handle request: summarize agenda or fallback to normal conversation."""
        self._emit_turn_start(input)

        if is_agenda_request(input):
            is_tomorrow = is_tomorrow_request(input)
            try:
                tz = ZoneInfo(self._timezone_name)
            except Exception:
                tz = ZoneInfo(_DEFAULT_TIMEZONE)

            now = datetime.now(tz)
            target_date = (now + timedelta(days=1)).date() if is_tomorrow else now.date()

            try:
                events = self._fetch_events_for_date(target_date, tz)
                content = format_agenda_phrase(events, is_tomorrow)
            except RuntimeError as exc:
                if str(exc) == "gcalendar_not_connected":
                    content = (
                        "O Google Calendar não está conectado. "
                        "Conecte com o comando: jarvis connect gcalendar."
                    )
                else:
                    content = "Não foi possível carregar seus compromissos no momento."
            except Exception as exc:
                logger.error("Error retrieving agenda: %s", exc)
                content = "Não foi possível carregar seus compromissos no momento."

            self._emit_turn_end(content_length=len(content))
            return AgentResult(content=content, turns=1)

        # Non-agenda request: respond as normal conversation
        messages = self._build_messages(
            input, context, system_prompt=_DEFAULT_SYSTEM_PROMPT
        )
        result = self._generate(messages)
        content = result.get("content", "")
        self._emit_turn_end(content_length=len(content))
        return AgentResult(content=content, turns=1)


__all__ = [
    "AgendaAgent",
    "format_agenda_phrase",
    "is_agenda_request",
    "is_ignored_calendar",
    "is_ignored_event",
    "is_tomorrow_request",
]
