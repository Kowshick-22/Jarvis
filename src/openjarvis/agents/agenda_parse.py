"""Pure parser functions for agenda event creation.

Extracts dates, times, titles, and confirmation intents from voice phrases
in Brazilian Portuguese.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import re
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

_DEFAULT_TIMEZONE = "America/Fortaleza"

WEEKDAYS_PT = [
    "segunda",
    "terça",
    "quarta",
    "quinta",
    "sexta",
    "sábado",
    "domingo",
]

_WEEKDAY_MAP = {
    "segunda": 0,
    "segunda-feira": 0,
    "terça": 1,
    "terca": 1,
    "terça-feira": 1,
    "terca-feira": 1,
    "quarta": 2,
    "quarta-feira": 2,
    "quinta": 3,
    "quinta-feira": 3,
    "sexta": 4,
    "sexta-feira": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}

_MONTH_MAP = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

_SHORT_AFFIRMATIVES = frozenset({
    "sim",
    "confirma",
    "pode marcar",
    "isso",
})

_CREATE_TRIGGER_VERBS = [
    r"\b(marcar?|marque)\b",
    r"\b(criar?|crie)\b",
    r"\b(agendar?|agende)\b",
    r"\b(adicionar?|adicione)\b",
    r"\bnov(o|a)\b",
]

_TARGET_NOUN_KEYWORDS = [
    r"\bevento(s)?\b",
    r"\bcompromisso(s)?\b",
    r"\breuni[aã]o\b|\breuni[oõ]es\b",
    r"\bconsulta(s)?\b",
    r"\balmo[cç]o(s)?\b",
    r"\bjantar(es)?\b",
    r"\btreino(s)?\b",
    r"\bcall(s)?\b",
]

_DATETIME_SIGNALS = [
    r"\bhoje\b",
    r"\bamanh[aã]\b",
    r"\bdepois\s+de\s+amanh[aã]\b",
    r"\b(segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)(?:-feira)?\b",
    r"\bdia\s+\d{1,2}\b",
    r"\b\d{1,2}/\d{1,2}\b",
    r"\b[àa]s\s+\d{1,2}\b",
    r"\b\d{1,2}h(?:\d{2})?\b",
    r"\b\d{1,2}:\d{2}\b",
    r"\bmeio[- ]?dia\b",
    r"\bmeia[- ]?noite\b",
    r"\bda\s+(?:manh[aã]|tarde|noite|madrugada)\b",
    r"\b(vinte e (?:quatro|tr[eê]s|dois|duas|um|uma)|vinte|dezenove|dezanove|dezoito|dezessete|dezassete|dezesseis|dezasseis|quinze|quatorze|catorze|treze|doze|onze|dez|nove|oito|sete|seis|cinco|quatro|tr[eê]s|duas|dois|uma|um)\s+horas?\b",
    r"\b[àa]s\s+(vinte e (?:quatro|tr[eê]s|dois|duas|um|uma)|vinte|dezenove|dezanove|dezoito|dezessete|dezassete|dezesseis|dezasseis|quinze|quatorze|catorze|treze|doze|onze|dez|nove|oito|sete|seis|cinco|quatro|tr[eê]s|duas|dois|uma|um)\b",
]

_SUMMARY_EXCLUDE_PATTERNS = [
    r"\b(o que|qual)\b.*(tenho|temos|tem|h[aá])",
    r"\bresum(a|e|ir|o)\b",
    r"\bminha agenda\b",
    r"\bagenda\s+(de hoje|de amanh[aã]|para hoje|para amanh[aã]|pra hoje|pra amanh[aã])\b",
]

_WRITTEN_HOURS = [
    ("vinte e quatro", "24"),
    ("vinte e três", "23"),
    ("vinte e tres", "23"),
    ("vinte e duas", "22"),
    ("vinte e dois", "22"),
    ("vinte e uma", "21"),
    ("vinte e um", "21"),
    ("vinte", "20"),
    ("dezenove", "19"),
    ("dezanove", "19"),
    ("dezoito", "18"),
    ("dezessete", "17"),
    ("dezassete", "17"),
    ("dezesseis", "16"),
    ("dezasseis", "16"),
    ("quinze", "15"),
    ("quatorze", "14"),
    ("catorze", "14"),
    ("treze", "13"),
    ("doze", "12"),
    ("onze", "11"),
    ("dez", "10"),
    ("nove", "9"),
    ("oito", "8"),
    ("sete", "7"),
    ("seis", "6"),
    ("cinco", "5"),
    ("quatro", "4"),
    ("três", "3"),
    ("tres", "3"),
    ("duas", "2"),
    ("dois", "2"),
    ("uma", "1"),
    ("um", "1"),
]


@dataclass(slots=True)
class ParseTimeResult:
    """Result of parsing time from text."""

    time: Optional[time] = None
    is_ambiguous: bool = False
    ambiguous_hour: Optional[int] = None
    ambiguous_minute: int = 0
    is_past: bool = False
    is_12_night: bool = False
    raw_match: Optional[str] = None


@dataclass(slots=True)
class AgendaCreateParseResult:
    """Complete structured parse of an event creation voice request."""

    is_create: bool = False
    title: str = ""
    target_date: Optional[date] = None
    target_time: Optional[time] = None
    target_dt: Optional[datetime] = None
    is_ambiguous_time: bool = False
    ambiguous_hour: Optional[int] = None
    ambiguous_minute: int = 0
    is_past_time: bool = False
    missing_title: bool = False
    missing_time: bool = False
    missing_date: bool = False
    raw_date_str: Optional[str] = None
    raw_time_str: Optional[str] = None


def convert_written_numbers_in_time(text: str) -> str:
    """Convert spoken numbers (Whisper output) in time expressions to digits."""
    t = text

    # Minutes conversion
    t = re.sub(r"\bquarenta\s+e\s+cinco\b", "45", t, flags=re.IGNORECASE)
    t = re.sub(r"\btrinta\b", "30", t, flags=re.IGNORECASE)
    t = re.sub(r"\be\s+meia\b", "e 30", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(e\s+)quinze\b", r"\g<1>15", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(e\s+)dez\b", r"\g<1>10", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(e\s+)vinte\b", r"\g<1>20", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(e\s+)vinte\s+e\s+cinco\b", r"\g<1>25", t, flags=re.IGNORECASE)

    # Hours conversion
    for word, num in _WRITTEN_HOURS:
        # 1. Preceded by time prepositions: às, as, à, pras, pra, para, para as, etc.
        prep_pat = (
            r"(?i)(\b(?:[àa]s|pras?|para\s+[àa]s|pra\s+[àa]s|para|pra|[àa]|das?|de|pelas?)\s+)\b"
            + word
            + r"\b"
        )
        t = re.sub(prep_pat, r"\g<1>" + num, t)

        # 2. Followed by time markers: horas, h, da tarde, da manhã, da noite, e meia, etc.
        marker_pat = (
            r"(?i)\b"
            + word
            + r"\b(\s+(?:horas?|h\b|da\s+tarde|pela\s+tarde|de\s+tarde|[àa]\s+tarde|da\s+manh[aã]|pela\s+manh[aã]|de\s+manh[aã]|da\s+noite|pela\s+noite|de\s+noite|[àa]\s+noite|da\s+madrugada|e\s+meia|e\s+\d+))"
        )
        t = re.sub(marker_pat, num + r"\1", t)

        # 3. Standalone answer (e.g. user just said "três" or "três da tarde")
        standalone_pat = (
            r"(?i)^(\s*(?:(?:[àa]s|pras?|para\s+[àa]s|pra\s+[àa]s|para|pra|[àa]|das?|de)\s+)?)("
            + word
            + r")(\s*(?:da\s+tarde|pela\s+tarde|de\s+tarde|[àa]\s+tarde|da\s+manh[aã]|pela\s+manh[aã]|de\s+manh[aã]|da\s+noite|pela\s+noite|de\s+noite|[àa]\s+noite|da\s+madrugada|horas?|h\b|e\s+meia|e\s+\d+)?\s*(?:por\s+favor)?\s*[.!?]?)$"
        )
        t = re.sub(standalone_pat, r"\g<1>" + num + r"\3", t)

    return t


def is_short_affirmative(text: str) -> bool:
    """Return True if the text is an exact short affirmative confirmation.

    Allowed: 'sim', 'confirma', 'pode marcar', 'isso'.
    Any extra qualification like 'sim, mas...' returns False.
    """
    cleaned = re.sub(r"[.!?,;:~]+$", "", text.strip().lower()).strip()
    return cleaned in _SHORT_AFFIRMATIVES


def is_create_intent(text: str) -> bool:
    """Check if text expresses intent to create a calendar event.

    Requires a creation trigger verb AND (a date/time signal OR one of the
    target keywords: evento, compromisso, reunião, consulta, almoço, jantar, treino, call).
    Prevents queries like 'Que marca de tênis você recomenda?' from matching.
    """
    t = text.lower().strip()

    # Must contain a creation verb
    if not any(bool(re.search(pat, t)) for pat in _CREATE_TRIGGER_VERBS):
        return False

    # Must not match summary/query exclusion patterns
    for excl in _SUMMARY_EXCLUDE_PATTERNS:
        if re.search(excl, t):
            return False

    # Must contain either a target noun keyword or a date/time signal
    has_noun = any(bool(re.search(pat, t)) for pat in _TARGET_NOUN_KEYWORDS)
    has_dt = any(bool(re.search(pat, t)) for pat in _DATETIME_SIGNALS)

    return has_noun or has_dt


def parse_date(
    text: str,
    now: Optional[datetime] = None,
    tz: Optional[ZoneInfo] = None,
) -> Tuple[Optional[date], Optional[str]]:
    """Parse date from text.

    If the day of the week equals today's day of the week, the date for next
    week is chosen.
    """
    if now is None:
        tz_info = tz or ZoneInfo(_DEFAULT_TIMEZONE)
        now = datetime.now(tz_info)

    t = text.lower()

    # 1. Depois de amanhã
    m = re.search(r"\b(depois\s+de\s+amanh[aã])\b", t)
    if m:
        return (now + timedelta(days=2)).date(), m.group(1)

    # 2. Amanhã
    m = re.search(r"\b(amanh[aã])\b", t)
    if m:
        return (now + timedelta(days=1)).date(), m.group(1)

    # 3. Hoje
    m = re.search(r"\b(hoje)\b", t)
    if m:
        return now.date(), m.group(1)

    # 4. Weekdays
    weekday_regex = (
        r"\b(?:na\s+|no\s+|pra\s+|para\s+|nesta\s+|pr[oó]xima\s+)?"
        r"(segunda(?:-feira)?|ter[cç]a(?:-feira)?|quarta(?:-feira)?|quinta(?:-feira)?|sexta(?:-feira)?|s[aá]bado|domingo)\b"
    )
    m = re.search(weekday_regex, t)
    if m:
        raw_weekday = m.group(1)
        normalized = raw_weekday.replace("á", "a").replace("ç", "c")
        if normalized in _WEEKDAY_MAP:
            target_weekday = _WEEKDAY_MAP[normalized]
            today_weekday = now.weekday()
            if target_weekday == today_weekday:
                # Rule: Day of the week equal to today -> use next week's
                days_ahead = 7
            else:
                days_ahead = (target_weekday - today_weekday) % 7
            return (now + timedelta(days=days_ahead)).date(), m.group(0)

    # 5. Explicit date: DD/MM or DD/MM/YYYY
    m = re.search(r"\b(?:dia\s+)?(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year_str = m.group(3)
        year = int(year_str) if year_str else now.year
        if year < 100:
            year += 2000
        try:
            return date(year, month, day), m.group(0)
        except ValueError:
            pass

    # 6. Explicit date: "dia DD de <mês>" or "dia DD"
    m = re.search(r"\bdia\s+(\d{1,2})(?:\s+de\s+([a-zç]+))?\b", t)
    if m:
        day = int(m.group(1))
        month_name = m.group(2)
        if month_name:
            norm_month = month_name.replace("ç", "c")
            month = _MONTH_MAP.get(norm_month, now.month)
        else:
            month = now.month
            if day < now.day:
                month = month + 1 if month < 12 else 1
        year = now.year
        try:
            return date(year, month, day), m.group(0)
        except ValueError:
            pass

    return None, None


def parse_time(
    text: str,
    now: Optional[datetime] = None,
    target_date: Optional[date] = None,
    tz: Optional[ZoneInfo] = None,
) -> ParseTimeResult:
    """Parse time from text.

    Converts written numbers to digits, detects ambiguous 12-hour values,
    handles '12 da noite' (00:00 next day) and '12 da tarde' (12:00),
    and checks if the time has already passed today.
    """
    if now is None:
        tz_info = tz or ZoneInfo(_DEFAULT_TIMEZONE)
        now = datetime.now(tz_info)

    # Convert written numbers to digits
    t = convert_written_numbers_in_time(text).lower()

    # 1. Meio-dia
    m = re.search(r"\b(?:ao\s+|o\s+)?meio[- ]?dia\b", t)
    if m:
        t_val = time(12, 0)
        is_past = False
        if target_date is None or target_date == now.date():
            target_dt = datetime(
                now.year, now.month, now.day, 12, 0, tzinfo=now.tzinfo
            )
            if target_dt <= now:
                is_past = True
        return ParseTimeResult(time=t_val, is_past=is_past, raw_match=m.group(0))

    # 2. Meia-noite
    m = re.search(r"\b(?:[aà]\s+|a\s+)?meia[- ]?noite\b", t)
    if m:
        t_val = time(0, 0)
        is_past = False
        if target_date is None or target_date == now.date():
            target_dt = datetime(
                now.year, now.month, now.day, 0, 0, tzinfo=now.tzinfo
            )
            if target_dt <= now:
                is_past = True
        return ParseTimeResult(time=t_val, is_past=is_past, raw_match=m.group(0))

    # 3. Numeric time with optional minutes, h/horas, and period
    time_regex = (
        r"(?:\b[àa]s\s+|\bpara\s+[àa]s\s+|\bpra\s+[àa]s\s+|\bpras?\s+|\bpara\s+|\bpra\s+)?"
        r"\b(\d{1,2})(?:[h:](\d{2})|h\b|\s*horas?\b|\s+e\s+(meia|\d{1,2}))?"
        r"(?:\s+(da\s+manh[aã]|pela\s+manh[aã]|de\s+manh[aã]|da\s+tarde|pela\s+tarde|de\s+tarde|da\s+noite|pela\s+noite|de\s+noite|da\s+madrugada|am|pm))?\b"
    )

    matches = list(re.finditer(time_regex, t))
    if not matches:
        return ParseTimeResult()

    # Prefer matches that include indicators
    chosen_match = None
    for match in matches:
        raw = match.group(0).strip()
        h_str = match.group(1)
        m_str = match.group(2)
        e_str = match.group(3)
        period_str = match.group(4)
        if (
            "à" in raw
            or "as" in raw
            or "h" in raw
            or "hora" in raw
            or m_str
            or e_str
            or period_str
        ):
            chosen_match = match
            break

    if not chosen_match:
        for match in matches:
            if re.match(r"^[àa]s\s+\d{1,2}", match.group(0).strip()):
                chosen_match = match
                break

    if not chosen_match:
        standalone_check = re.match(
            r"^\s*(?:[àa]s\s+)?(\d{1,2})(?:[h:](\d{2})|h\b|\s*horas?\b|\s+e\s+(meia|\d{1,2}))?"
            r"(?:\s+(da\s+manh[aã]|pela\s+manh[aã]|de\s+manh[aã]|da\s+tarde|pela\s+tarde|de\s+tarde|da\s+noite|pela\s+noite|de\s+noite|da\s+madrugada|am|pm))?\s*[.!?]?$",
            t,
            flags=re.IGNORECASE,
        )
        if standalone_check and matches:
            chosen_match = matches[0]

    if not chosen_match:
        return ParseTimeResult()

    raw_str = chosen_match.group(0).strip()
    hour = int(chosen_match.group(1))
    min_str = chosen_match.group(2)
    extra_min_str = chosen_match.group(3)
    period = chosen_match.group(4)

    minute = 0
    if min_str:
        minute = int(min_str)
    elif extra_min_str:
        if extra_min_str.lower() == "meia":
            minute = 30
        elif extra_min_str.isdigit():
            minute = int(extra_min_str)

    if minute < 0 or minute > 59:
        return ParseTimeResult()

    is_12_night = False

    if hour == 24 and minute == 0:
        hour = 0
        is_12_night = True
    elif hour > 23:
        return ParseTimeResult()

    if 1 <= hour <= 12:
        if not period:
            # Rule 3: Ambiguous hour without morning/afternoon/night -> ask
            return ParseTimeResult(
                time=None,
                is_ambiguous=True,
                ambiguous_hour=hour,
                ambiguous_minute=minute,
                raw_match=raw_str,
            )
        period_lower = period.lower()
        if "noite" in period_lower or "madrugada" in period_lower:
            if hour == 12:
                # 12 da noite = 00:00 do dia seguinte
                hour = 0
                is_12_night = True
            elif hour < 12 and "noite" in period_lower:
                hour += 12
        elif "tarde" in period_lower or "pm" in period_lower:
            if hour < 12:
                hour += 12
            elif hour == 12:
                # 12 da tarde = 12:00
                hour = 12
        elif "manh" in period_lower or "am" in period_lower:
            if hour == 12:
                hour = 0

    t_val = time(hour, minute)

    # Check if time has already passed today
    is_past = False
    check_date = target_date if target_date is not None else now.date()
    if is_12_night:
        # 12 da noite applies to next day's 00:00
        check_date = check_date + timedelta(days=1)

    if check_date < now.date():
        is_past = True
    elif check_date == now.date():
        target_dt = datetime(
            check_date.year,
            check_date.month,
            check_date.day,
            t_val.hour,
            t_val.minute,
            tzinfo=now.tzinfo,
        )
        if target_dt <= now:
            is_past = True

    return ParseTimeResult(
        time=t_val,
        is_past=is_past,
        is_12_night=is_12_night,
        raw_match=raw_str,
    )


def parse_title(
    text: str,
    raw_date: Optional[str] = None,
    raw_time: Optional[str] = None,
) -> str:
    """Extract event title by removing triggers, date references, and time references."""
    t = text

    # Remove matched date substring
    if raw_date:
        t = re.sub(re.escape(raw_date), " ", t, flags=re.IGNORECASE)

    # Remove matched time substring
    if raw_time:
        t = re.sub(re.escape(raw_time), " ", t, flags=re.IGNORECASE)

    # Remove standalone date / time expressions that may still linger
    dt_cleanups = [
        r"\bdepois\s+de\s+amanh[aã]\b",
        r"\bamanh[aã]\b",
        r"\bhoje\b",
        r"\b(?:ao\s+)?meio[- ]?dia\b",
        r"\b(?:[aà]\s+)?meia[- ]?noite\b",
        r"\b[àa]s\s+\d{1,2}(?:[h:]\d{2}|h)?(?:\s+da\s+(?:manh[aã]|tarde|noite|madrugada))?\b",
    ]
    for pat in dt_cleanups:
        t = re.sub(pat, " ", t, flags=re.IGNORECASE)

    # Remove polite words
    polite_patterns = [
        r"\bpor\s+favor\b",
        r"\bpor\s+gentileza\b",
        r"\bjarvis\b",
        r"\bquero\b",
        r"\bgostaria\s+de\b",
        r"\bpreciso\b",
    ]
    for pat in polite_patterns:
        t = re.sub(pat, " ", t, flags=re.IGNORECASE)

    # If an explicit naming marker is present (e.g. 'chamado estudar', 'com o nome alinhamento'),
    # the title is specifically whatever comes after that marker.
    marker_m = re.search(
        r"\b(?:chamad[oa](?:s)?(?:\s+de)?|com\s+o\s+nome(?:\s+de)?|com\s+o\s+t[ií]tulo(?:\s+de)?|de\s+nome)\s+(.+)$",
        t,
        flags=re.IGNORECASE,
    )
    if marker_m:
        t = marker_m.group(1)

    # Remove triggers: "marca", "cria um evento", etc.
    trigger_patterns = [
        r"\b(cria(r|e)?|marca(r|que)?|agenda(r|e)?|adiciona(r|e)?)\s+(um\s+|o\s+|uma\s+|a\s+)?(evento|compromisso)\b",
        r"\b(cria(r|e)?|marca(r|que)?|agenda(r|e)?|adiciona(r|e)?)\s+(pra\s+mim|para\s+mim)\b",
        r"\b(cria(r|e)?|marca(r|que)?|agenda(r|e)?|adiciona(r|e)?)\b",
        r"\bnov(o|a)\s+(evento|compromisso)\b",
        r"\b(um\s+|o\s+|uma\s+|a\s+)(evento|compromisso)\b",
    ]
    for pat in trigger_patterns:
        t = re.sub(pat, " ", t, flags=re.IGNORECASE)

    # Clean leading / trailing prepositions and punctuation
    t = re.sub(r"^[,\s.?!:;]+", "", t)
    t = re.sub(r"[,\s.?!:;]+$", "", t)

    leading_prep = r"^(para\s+|pra\s+|de\s+|do\s+|da\s+|um\s+|uma\s+|o\s+|a\s+)"
    while re.search(leading_prep, t, flags=re.IGNORECASE):
        t = re.sub(leading_prep, "", t, flags=re.IGNORECASE).strip()

    trailing_prep = r"(\s+para|\s+pra|\s+no|\s+na|\s+em|\s+de|\s+às|\s+as)$"
    while re.search(trailing_prep, t, flags=re.IGNORECASE):
        t = re.sub(trailing_prep, "", t, flags=re.IGNORECASE).strip()

    t = re.sub(r"\s+", " ", t).strip()

    # Rule 4: Limit title length (max 100 characters)
    t = t[:100].strip()

    if not t:
        return ""

    return t[0].upper() + t[1:]


def format_confirmation_prompt(title: str, target_dt: datetime) -> str:
    """Format short voice confirmation prompt repeating weekday, day/month, and time."""
    weekday = WEEKDAYS_PT[target_dt.weekday()]
    day_month = f"{target_dt.day:02d}/{target_dt.month:02d}"
    if target_dt.minute == 0:
        time_str = f"{target_dt.hour}h"
    else:
        time_str = f"{target_dt.hour}h{target_dt.minute:02d}"

    return f"Marcar {title} para {weekday}, {day_month}, {time_str}? Confirma?"


def build_event_payload(
    title: str,
    target_dt: datetime,
    duration_minutes: int = 60,
) -> Dict[str, Any]:
    """Build Google Calendar event payload with 10-minute popup reminder."""
    end_dt = target_dt + timedelta(minutes=duration_minutes)
    return {
        "summary": title,
        "start": {
            "dateTime": target_dt.isoformat(),
        },
        "end": {
            "dateTime": end_dt.isoformat(),
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},
            ],
        },
    }


def parse_create_event(
    text: str,
    now: Optional[datetime] = None,
    tz: Optional[ZoneInfo] = None,
) -> AgendaCreateParseResult:
    """Parse creation request into structured parameters with pure logic."""
    if now is None:
        tz_info = tz or ZoneInfo(_DEFAULT_TIMEZONE)
        now = datetime.now(tz_info)
    else:
        tz_info = now.tzinfo or tz or ZoneInfo(_DEFAULT_TIMEZONE)

    if not is_create_intent(text):
        return AgendaCreateParseResult(is_create=False)

    converted_text = convert_written_numbers_in_time(text)

    parsed_d, raw_d = parse_date(converted_text, now, tz=tz_info)
    target_date = parsed_d if parsed_d is not None else now.date()
    missing_date = parsed_d is None

    time_res = parse_time(converted_text, now, target_date=target_date, tz=tz_info)

    title = parse_title(converted_text, raw_date=raw_d, raw_time=time_res.raw_match)
    missing_title = not bool(title)

    if time_res.is_ambiguous:
        return AgendaCreateParseResult(
            is_create=True,
            title=title,
            target_date=target_date,
            is_ambiguous_time=True,
            ambiguous_hour=time_res.ambiguous_hour,
            ambiguous_minute=time_res.ambiguous_minute,
            missing_title=missing_title,
            raw_date_str=raw_d,
            raw_time_str=time_res.raw_match,
        )

    if time_res.is_past:
        return AgendaCreateParseResult(
            is_create=True,
            title=title,
            target_date=target_date,
            target_time=time_res.time,
            is_past_time=True,
            missing_title=missing_title,
            raw_date_str=raw_d,
            raw_time_str=time_res.raw_match,
        )

    if time_res.time is None:
        return AgendaCreateParseResult(
            is_create=True,
            title=title,
            target_date=target_date,
            missing_time=True,
            missing_title=missing_title,
            missing_date=missing_date,
            raw_date_str=raw_d,
        )

    # If '12 da noite', target_date advances by 1 day
    if time_res.is_12_night:
        target_date = target_date + timedelta(days=1)

    target_dt = datetime.combine(target_date, time_res.time, tzinfo=tz_info)

    return AgendaCreateParseResult(
        is_create=True,
        title=title,
        target_date=target_date,
        target_time=time_res.time,
        target_dt=target_dt,
        missing_title=missing_title,
        missing_date=missing_date,
        raw_date_str=raw_d,
        raw_time_str=time_res.raw_match,
    )


__all__ = [
    "AgendaCreateParseResult",
    "ParseTimeResult",
    "WEEKDAYS_PT",
    "build_event_payload",
    "convert_written_numbers_in_time",
    "format_confirmation_prompt",
    "is_create_intent",
    "is_short_affirmative",
    "parse_create_event",
    "parse_date",
    "parse_time",
    "parse_title",
]
