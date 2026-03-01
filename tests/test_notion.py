"""Test Notion reader."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

print("=== Notion Reader ===")
from services.notion import get_all_databases, read_all_notes

dbs = get_all_databases()
print(f"Databases: {len(dbs)}")
for db in dbs:
    print(f"  - {db['title']} (id: {db['id'][:20]}...)")

notes = read_all_notes(fetch_content=False)
print(f"\nTong notes: {len(notes)}")
for n in notes[:10]:
    props_str = ""
    if n.properties:
        important = {k: v for k, v in n.properties.items() if v and v not in (False, [], None, "")}
        if important:
            props_str = " | " + str(important)[:60]
    print(f"  [{n.database_name}] {n.title}{props_str}")
if len(notes) > 10:
    print(f"  ... va {len(notes) - 10} notes nua")
print("DONE")
