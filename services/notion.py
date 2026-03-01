"""
Notion reader cho Zertdoo.
Doc pages tu cac databases duoc share voi integration.
"""

import logging
from datetime import datetime
from typing import Optional

from notion_client import Client

from models.schemas import NotionNote
from config import settings

logger = logging.getLogger("zertdoo.notion")


def _get_notion_client() -> Client:
    """Tao Notion client."""
    if not settings.notion_token:
        raise ValueError("NOTION_TOKEN chua duoc cau hinh trong .env")
    return Client(auth=settings.notion_token)


# ============================================================
# READ
# ============================================================

def get_all_databases() -> list[dict]:
    """
    Tim tat ca databases ma integration co quyen truy cap.

    Returns:
        list[dict] voi keys: id, title
    """
    client = _get_notion_client()
    results = client.search(filter={"property": "object", "value": "database"})

    databases = []
    for item in results.get("results", []):
        title_arr = item.get("title", [])
        title = title_arr[0].get("plain_text", "") if title_arr else "(Khong co ten)"
        databases.append({
            "id": item["id"],
            "title": title,
        })

    logger.info("Tim thay %d databases trong Notion.", len(databases))
    return databases


def _extract_page_title(page: dict) -> str:
    """Trich xuat title tu properties cua 1 Notion page."""
    props = page.get("properties", {})
    for prop_name, prop_data in props.items():
        if prop_data.get("type") == "title":
            title_arr = prop_data.get("title", [])
            if title_arr:
                return "".join(t.get("plain_text", "") for t in title_arr)
    return "(Khong co tieu de)"


def _extract_page_properties(page: dict) -> dict:
    """
    Trich xuat cac properties khac (ngoai title) cua 1 Notion page.
    Tra ve dict dang don gian de LLM doc duoc.
    """
    result = {}
    props = page.get("properties", {})

    for prop_name, prop_data in props.items():
        ptype = prop_data.get("type", "")

        if ptype == "title":
            continue  # Da xu ly rieng

        elif ptype == "rich_text":
            texts = prop_data.get("rich_text", [])
            result[prop_name] = "".join(t.get("plain_text", "") for t in texts)

        elif ptype == "select":
            sel = prop_data.get("select")
            result[prop_name] = sel.get("name", "") if sel else ""

        elif ptype == "multi_select":
            items = prop_data.get("multi_select", [])
            result[prop_name] = [i.get("name", "") for i in items]

        elif ptype == "date":
            date_obj = prop_data.get("date")
            if date_obj:
                result[prop_name] = date_obj.get("start", "")

        elif ptype == "checkbox":
            result[prop_name] = prop_data.get("checkbox", False)

        elif ptype == "number":
            result[prop_name] = prop_data.get("number")

        elif ptype == "status":
            status_obj = prop_data.get("status")
            result[prop_name] = status_obj.get("name", "") if status_obj else ""

        elif ptype == "url":
            result[prop_name] = prop_data.get("url", "")

        # Bo qua cac type phuc tap khac (relation, rollup, formula, ...)

    return result


def _get_page_content(client: Client, page_id: str) -> str:
    """
    Doc noi dung (blocks) cua 1 page, tra ve plain text.
    Chi doc cac block text co ban (paragraph, heading, list).
    """
    blocks = client.blocks.children.list(block_id=page_id)
    texts = []

    for block in blocks.get("results", []):
        btype = block.get("type", "")
        block_data = block.get(btype, {})

        # Cac block co rich_text
        if "rich_text" in block_data:
            rich_texts = block_data.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_texts)
            if text.strip():
                texts.append(text.strip())

        # To-do blocks
        elif btype == "to_do":
            rich_texts = block_data.get("rich_text", [])
            text = "".join(t.get("plain_text", "") for t in rich_texts)
            checked = block_data.get("checked", False)
            mark = "[x]" if checked else "[ ]"
            if text.strip():
                texts.append(f"{mark} {text.strip()}")

    return "\n".join(texts)


def read_database_pages(
    database_id: str,
    database_name: str = "",
    fetch_content: bool = True,
) -> list[NotionNote]:
    """
    Doc tat ca pages tu 1 database.

    Args:
        database_id: ID cua Notion database
        database_name: Ten database (de gan vao model)
        fetch_content: Co doc noi dung chi tiet cua tung page khong
                       (False de tiet kiem API calls)

    Returns:
        list[NotionNote]
    """
    client = _get_notion_client()
    notes = []
    start_cursor = None

    while True:
        kwargs = {"database_id": database_id, "page_size": 100}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor

        response = client.databases.query(**kwargs)

        for page in response.get("results", []):
            title = _extract_page_title(page)
            properties = _extract_page_properties(page)
            last_edited = page.get("last_edited_time")
            url = page.get("url", "")

            content = ""
            if fetch_content:
                try:
                    content = _get_page_content(client, page["id"])
                except Exception as e:
                    logger.warning("Khong doc duoc noi dung page '%s': %s", title, e)

            notes.append(NotionNote(
                page_id=page["id"],
                database_id=database_id,
                database_name=database_name,
                title=title,
                content=content,
                properties=properties,
                last_edited=last_edited,
                url=url,
            ))

        if not response.get("has_more"):
            break
        start_cursor = response.get("next_cursor")

    logger.info("Database '%s': %d pages.", database_name, len(notes))
    return notes


def read_all_notes(fetch_content: bool = True) -> list[NotionNote]:
    """
    Doc tat ca pages tu tat ca databases.

    Args:
        fetch_content: Co doc noi dung chi tiet khong

    Returns:
        list[NotionNote]
    """
    databases = get_all_databases()
    all_notes: list[NotionNote] = []

    for db in databases:
        try:
            notes = read_database_pages(
                database_id=db["id"],
                database_name=db["title"],
                fetch_content=fetch_content,
            )
            all_notes.extend(notes)
        except Exception as e:
            logger.error("Loi khi doc database '%s': %s", db["title"], e)

    logger.info("Tong cong: %d notes tu %d databases.", len(all_notes), len(databases))
    return all_notes


def read_notion_summary(fetch_content: bool = True) -> str:
    """
    Doc tat ca notes va tra ve dang text tom tat cho LLM.

    Returns:
        str
    """
    all_notes = read_all_notes(fetch_content=fetch_content)

    if not all_notes:
        return "Khong co notes nao trong Notion."

    # Nhom theo database
    by_db: dict[str, list[NotionNote]] = {}
    for n in all_notes:
        by_db.setdefault(n.database_name, []).append(n)

    lines = []
    for db_name, notes in by_db.items():
        lines.append(f"\n[Notion DB: {db_name}] ({len(notes)} pages)")
        for n in notes:
            props_str = ""
            if n.properties:
                # Hien thi cac property quan trong
                important = {k: v for k, v in n.properties.items()
                             if v and v not in (False, [], None, "")}
                if important:
                    props_str = " | " + ", ".join(f"{k}: {v}" for k, v in important.items())

            content_preview = ""
            if n.content:
                # Chi hien 100 ky tu dau cua content
                preview = n.content[:100].replace("\n", " ")
                if len(n.content) > 100:
                    preview += "..."
                content_preview = f"\n      {preview}"

            lines.append(f"  - {n.title}{props_str}{content_preview}")

    return "\n".join(lines)
