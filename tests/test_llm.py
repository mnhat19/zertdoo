"""
Test LLM service: Gemini + Groq + retry + fallback + validation.
Chay: python tests/test_llm.py
"""

import asyncio
import sys
import os
import logging

# Them root vao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")

from services.llm import call_llm, call_llm_text, _extract_json, _parse_and_validate
from models.schemas import DailyPlanOutput


def test_extract_json():
    """Test trich xuat JSON tu cac dang response khac nhau."""
    print("\n=== Test _extract_json ===")

    # 1. JSON thuan tuy
    raw1 = '{"key": "value"}'
    assert _extract_json(raw1) == '{"key": "value"}'
    print("[OK] JSON thuan tuy")

    # 2. JSON trong code block
    raw2 = '```json\n{"key": "value"}\n```'
    assert '"key"' in _extract_json(raw2)
    print("[OK] JSON trong code block")

    # 3. JSON voi text xung quanh
    raw3 = 'Day la ket qua: {"key": "value"} xong.'
    result3 = _extract_json(raw3)
    assert '"key"' in result3
    print("[OK] JSON voi text xung quanh")

    # 4. Code block khong co json label
    raw4 = '```\n{"key": "value"}\n```'
    assert '"key"' in _extract_json(raw4)
    print("[OK] Code block khong label")

    print("--- _extract_json: TAT CA OK ---")


def test_parse_and_validate():
    """Test parse JSON va validate Pydantic model."""
    print("\n=== Test _parse_and_validate ===")

    # 1. Parse thanh dict (khong co model)
    raw = '{"daily_tasks": [], "risks": ["test"]}'
    result = _parse_and_validate(raw)
    assert isinstance(result, dict)
    assert result["risks"] == ["test"]
    print("[OK] Parse thanh dict")

    # 2. Parse + validate DailyPlanOutput
    raw_plan = '''{
        "daily_tasks": [
            {
                "title": "Hoc Toan",
                "source": "In_class/Toan",
                "priority_rank": 1,
                "time_slot": "08:00 - 09:30",
                "duration_minutes": 90,
                "reasoning": "Sap deadline"
            }
        ],
        "events_to_create": [],
        "risks": ["Qua nhieu task"],
        "questions_for_user": [],
        "overall_reasoning": "Lich hop ly"
    }'''
    result2 = _parse_and_validate(raw_plan, DailyPlanOutput)
    assert isinstance(result2, DailyPlanOutput)
    assert len(result2.daily_tasks) == 1
    assert result2.daily_tasks[0].title == "Hoc Toan"
    print("[OK] Parse + validate DailyPlanOutput")

    # 3. JSON khong hop le -> raise ValueError
    try:
        _parse_and_validate("khong phai json")
        assert False, "Phai raise loi"
    except ValueError:
        print("[OK] Raise ValueError cho JSON khong hop le")

    print("--- _parse_and_validate: TAT CA OK ---")


async def test_gemini_call():
    """Test goi Gemini that voi JSON output."""
    print("\n=== Test Gemini call (JSON) ===")

    system = """Ban la AI test. Tra ve JSON voi format:
{"daily_tasks": [], "events_to_create": [], "risks": [], "questions_for_user": [], "overall_reasoning": "test thanh cong"}"""

    user = "Hom nay la ngay test. Khong co task nao. Tra ve JSON rong voi overall_reasoning = 'test thanh cong'."

    result = await call_llm(
        system_prompt=system,
        user_content=user,
        response_model=DailyPlanOutput,
        agent_name="test",
        log_to_db=False,
    )

    assert isinstance(result, DailyPlanOutput)
    print(f"  daily_tasks: {len(result.daily_tasks)}")
    print(f"  overall_reasoning: {result.overall_reasoning}")
    print("[OK] Gemini tra ve DailyPlanOutput hop le")


async def test_groq_call():
    """Test goi Groq truc tiep (dat Gemini key = rong de force fallback)."""
    print("\n=== Test Groq fallback ===")
    from config import settings

    # Tam thoi xoa Gemini key de force dung Groq
    original_key = settings.gemini_api_key
    settings.gemini_api_key = ""

    try:
        system = """Tra ve JSON voi format chinh xac:
{"daily_tasks": [], "events_to_create": [], "risks": [], "questions_for_user": [], "overall_reasoning": "groq test ok"}"""

        user = "Day la test Groq. Tra ve JSON rong voi overall_reasoning = 'groq test ok'."

        result = await call_llm(
            system_prompt=system,
            user_content=user,
            response_model=DailyPlanOutput,
            agent_name="test_groq",
            log_to_db=False,
        )

        assert isinstance(result, DailyPlanOutput)
        print(f"  overall_reasoning: {result.overall_reasoning}")
        print("[OK] Groq tra ve DailyPlanOutput hop le")

    finally:
        settings.gemini_api_key = original_key


async def test_llm_text_call():
    """Test call_llm_text (plain text, khong JSON)."""
    print("\n=== Test call_llm_text ===")

    system = "Ban la tro ly. Tra loi ngan gon bang tieng Viet, khong emoji."
    user = "1 + 1 = ?"

    result = await call_llm_text(
        system_prompt=system,
        user_content=user,
        agent_name="test_text",
        log_to_db=False,
    )

    assert isinstance(result, str)
    assert len(result) > 0
    print(f"  Response: {result.strip()[:100]}")
    print("[OK] call_llm_text tra ve text")


async def main():
    print("=" * 50)
    print("TEST LLM SERVICE")
    print("=" * 50)

    # Unit tests (khong can API)
    test_extract_json()
    test_parse_and_validate()

    # Integration tests (can API keys)
    from config import settings
    if not settings.gemini_api_key and not settings.groq_api_key:
        print("\n[SKIP] Khong co API key, bo qua integration tests")
        return

    if settings.gemini_api_key:
        await test_gemini_call()
    else:
        print("\n[SKIP] Khong co GEMINI_API_KEY")

    if settings.groq_api_key:
        await test_groq_call()
    else:
        print("\n[SKIP] Khong co GROQ_API_KEY")

    await test_llm_text_call()

    print("\n" + "=" * 50)
    print("TAT CA TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
