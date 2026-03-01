"""Test Google Calendar reader."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

print("=== Google Calendar Reader ===")
from services.google_calendar import get_upcoming_events, read_calendar_summary

events = get_upcoming_events(days=7)
print(f"Su kien 7 ngay toi: {len(events)}")
for e in events[:10]:
    time_str = e.start[:16] if len(e.start) > 10 else e.start
    print(f"  [{time_str}] {e.summary}")

print("\n--- Summary cho LLM ---")
print(read_calendar_summary(days=7))
print("DONE")
