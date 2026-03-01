"""
Google Calendar reader/writer cho Zertdoo.
Doc va quan ly su kien tren Google Calendar.
"""

import logging
from datetime import datetime, timedelta

from models.schemas import CalendarEvent
from services.google_auth import build_service
from utils.time_utils import VN_TZ, now_vn

logger = logging.getLogger("zertdoo.google_calendar")


def _get_calendar_service():
    """Tao Google Calendar API service."""
    return build_service("calendar", "v3")


# ============================================================
# READ
# ============================================================

def get_upcoming_events(
    days: int = 7,
    calendar_id: str = "primary",
    max_results: int = 50,
) -> list[CalendarEvent]:
    """
    Doc cac su kien sap toi trong N ngay.

    Args:
        days: So ngay phia truoc (mac dinh 7)
        calendar_id: ID calendar (mac dinh 'primary')
        max_results: So event toi da

    Returns:
        list[CalendarEvent]
    """
    service = _get_calendar_service()

    time_min = now_vn().replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = time_min + timedelta(days=days)

    result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events_data = result.get("items", [])
    events = []

    for item in events_data:
        start_info = item.get("start", {})
        end_info = item.get("end", {})

        # Su kien ca ngay dung 'date', su kien co gio dung 'dateTime'
        is_all_day = "date" in start_info and "dateTime" not in start_info
        start_str = start_info.get("dateTime") or start_info.get("date", "")
        end_str = end_info.get("dateTime") or end_info.get("date", "")

        events.append(CalendarEvent(
            event_id=item["id"],
            summary=item.get("summary", "(Không có tiêu đề)"),
            description=item.get("description", ""),
            start=start_str,
            end=end_str,
            location=item.get("location", ""),
            is_all_day=is_all_day,
            status=item.get("status", "confirmed"),
        ))

    logger.info("Calendar: %d su kien trong %d ngay toi.", len(events), days)
    return events


def get_today_events(calendar_id: str = "primary") -> list[CalendarEvent]:
    """Doc cac su kien hom nay."""
    return get_upcoming_events(days=1, calendar_id=calendar_id)


def read_calendar_summary(days: int = 7) -> str:
    """
    Doc su kien va tra ve dang text tom tat cho LLM.

    Returns:
        str
    """
    events = get_upcoming_events(days=days)

    if not events:
        return f"Không có sự kiện nào trong {days} ngày tới."

    lines = [f"Sự kiện trong {days} ngày tới ({len(events)} sự kiện):"]

    # Nhom theo ngay
    by_date: dict[str, list[CalendarEvent]] = {}
    for e in events:
        # Lay phan ngay tu start string
        date_str = e.start[:10] if len(e.start) >= 10 else e.start
        by_date.setdefault(date_str, []).append(e)

    for date_str, day_events in by_date.items():
        lines.append(f"\n  {date_str}:")
        for e in day_events:
            if e.is_all_day:
                time_str = "Cả ngày"
            else:
                # Lay phan gio tu ISO datetime
                start_time = e.start[11:16] if len(e.start) > 11 else ""
                end_time = e.end[11:16] if len(e.end) > 11 else ""
                time_str = f"{start_time} - {end_time}"
            loc_str = f" @ {e.location}" if e.location else ""
            lines.append(f"    [{time_str}] {e.summary}{loc_str}")

    return "\n".join(lines)


# ============================================================
# WRITE (se dung o Giai doan 3+)
# ============================================================

def create_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    calendar_id: str = "primary",
) -> dict:
    """
    Tao su kien moi tren Calendar.

    Args:
        summary: Tieu de
        start: Thoi gian bat dau (ISO format voi timezone)
        end: Thoi gian ket thuc
        description: Mo ta
        location: Dia diem
        calendar_id: ID calendar

    Returns:
        dict voi id, summary, start, end
    """
    service = _get_calendar_service()

    body = {
        "summary": summary,
        "start": {"dateTime": start, "timeZone": "Asia/Ho_Chi_Minh"},
        "end": {"dateTime": end, "timeZone": "Asia/Ho_Chi_Minh"},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    result = service.events().insert(calendarId=calendar_id, body=body).execute()
    logger.info("Da tao event: '%s' (%s)", summary, result["id"])
    return {
        "id": result["id"],
        "summary": result.get("summary", summary),
        "start": start,
        "end": end,
    }


def update_event(
    event_id: str,
    updates: dict,
    calendar_id: str = "primary",
) -> dict:
    """
    Cap nhat 1 su kien.

    Args:
        event_id: ID event
        updates: dict chua cac truong can cap nhat
        calendar_id: ID calendar

    Returns:
        dict event da cap nhat
    """
    service = _get_calendar_service()

    # Lay event hien tai
    event = service.events().get(
        calendarId=calendar_id, eventId=event_id
    ).execute()

    # Merge updates
    for key, value in updates.items():
        if key in ("start", "end") and isinstance(value, str):
            event[key] = {"dateTime": value, "timeZone": "Asia/Ho_Chi_Minh"}
        else:
            event[key] = value

    result = service.events().update(
        calendarId=calendar_id, eventId=event_id, body=event
    ).execute()
    logger.info("Da cap nhat event: %s", event_id)
    return result


def delete_event(event_id: str, calendar_id: str = "primary") -> bool:
    """Xoa 1 su kien."""
    service = _get_calendar_service()
    service.events().delete(
        calendarId=calendar_id, eventId=event_id
    ).execute()
    logger.info("Da xoa event: %s", event_id)
    return True
