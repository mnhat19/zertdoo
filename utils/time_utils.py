"""
Tien ich xu ly thoi gian cho he thong Zertdoo.
Tat ca thoi gian trong he thong deu dung timezone Asia/Ho_Chi_Minh.
"""

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Timezone mac dinh cua he thong
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Mapping thu trong tuan sang tieng Viet (khong dau de dung trong Tasks/Calendar)
WEEKDAY_NAMES = {
    0: "T2",   # Monday
    1: "T3",
    2: "T4",
    3: "T5",
    4: "T6",
    5: "T7",
    6: "CN",   # Sunday
}

WEEKDAY_NAMES_FULL = {
    0: "Thu Hai",
    1: "Thu Ba",
    2: "Thu Tu",
    3: "Thu Nam",
    4: "Thu Sau",
    5: "Thu Bay",
    6: "Chu Nhat",
}


def now_vn() -> datetime:
    """Tra ve thoi gian hien tai theo gio Viet Nam."""
    return datetime.now(VN_TZ)


def today_vn() -> date:
    """Tra ve ngay hom nay theo gio Viet Nam."""
    return now_vn().date()


def format_date_vn(d: date) -> str:
    """
    Format ngay theo kieu Viet Nam: 'T2 01/03'
    Dung lam ten task list trong Google Tasks.
    """
    weekday = WEEKDAY_NAMES[d.weekday()]
    return f"{weekday} {d.strftime('%d/%m')}"


def format_datetime_vn(dt: datetime) -> str:
    """Format datetime day du: '01/03/2026 08:30'"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=VN_TZ)
    return dt.astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M")


def parse_date_flexible(text: str) -> date | None:
    """
    Phan tich ngay tu nhieu format khac nhau.
    Ho tro: DD/MM/YYYY, DD/MM, YYYY-MM-DD, DD-MM-YYYY
    Tra ve None neu khong parse duoc.
    """
    formats = [
        "%d/%m/%Y",
        "%d/%m",
        "%Y-%m-%d",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(text.strip(), fmt)
            # Neu khong co nam (DD/MM), dung nam hien tai
            if fmt == "%d/%m":
                parsed = parsed.replace(year=today_vn().year)
            return parsed.date()
        except ValueError:
            continue
    return None


def is_today(d: date) -> bool:
    """Kiem tra ngay co phai hom nay khong."""
    return d == today_vn()


def days_until(d: date) -> int:
    """So ngay tu hom nay den ngay d. Am neu da qua."""
    return (d - today_vn()).days
