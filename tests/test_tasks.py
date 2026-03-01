"""Test Google Tasks reader."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

print("=== Google Tasks Reader ===")
from services.google_tasks import get_all_task_lists, read_all_tasks

lists = get_all_task_lists()
print(f"Task lists: {len(lists)}")
for tl in lists:
    print(f"  - {tl['title']}")

tasks = read_all_tasks()
print(f"Tong tasks: {len(tasks)}")
for t in tasks[:10]:
    s = "[x]" if t.status == "completed" else "[ ]"
    print(f"  {s} [{t.task_list_title}] {t.title}")
if len(tasks) > 10:
    print(f"  ... va {len(tasks) - 10} tasks nua")
print("DONE")
