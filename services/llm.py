"""
LLM service trung tam cho Zertdoo.

Cung cap:
- call_llm(): goi LLM voi system prompt + user content, tra ve dict/text
- Tu dong retry 3 lan voi exponential backoff
- Fallback: Gemini (primary) -> Groq (backup)
- Parse JSON tu response, validate bang Pydantic neu co schema
- Log moi lan goi vao agent_logs (Postgres)

Su dung:
    from services.llm import call_llm
    result = await call_llm(
        system_prompt="Ban la AI scheduler...",
        user_content="Day la danh sach tasks...",
        response_model=DailyPlanOutput,  # Optional: Pydantic model
        agent_name="scheduler",
    )
"""

import json
import logging
import re
import time
import asyncio
from typing import Optional, Type, TypeVar, Union

from pydantic import BaseModel

from config import settings

logger = logging.getLogger("zertdoo.llm")

T = TypeVar("T", bound=BaseModel)


def _is_rate_limit_error(e: Exception) -> bool:
    """Kiem tra xem loi co phai rate limit (HTTP 429) hay khong."""
    error_str = str(e).lower()
    if "429" in error_str or "rate" in error_str or "quota" in error_str:
        return True
    if "resource_exhausted" in error_str or "too many requests" in error_str:
        return True
    # google-genai va groq exceptions
    if hasattr(e, "status_code") and getattr(e, "status_code", 0) == 429:
        return True
    if hasattr(e, "code") and getattr(e, "code", 0) == 429:
        return True
    return False


def _get_backoff_seconds(attempt: int, is_rate_limit: bool) -> int:
    """
    Tinh thoi gian cho giua cac lan retry.
    - Rate limit: doi lau hon (15s, 30s, 60s)
    - Loi khac: exponential backoff ngan (2s, 4s, 8s)
    """
    if is_rate_limit:
        return min(15 * (2 ** (attempt - 1)), 120)  # 15s, 30s, 60s, max 120s
    return 2 ** attempt  # 2s, 4s, 8s

# ============================================================
# GEMINI CLIENT
# ============================================================

def _get_gemini_client():
    """Tao Google GenAI client (SDK moi: google-genai)."""
    from google import genai
    return genai.Client(api_key=settings.gemini_api_key)


def _call_gemini_sync(system_prompt: str, user_content: str) -> str:
    """
    Goi Gemini API (sync) bang google-genai SDK.
    Tra ve raw text response.
    """
    from google.genai import types

    client = _get_gemini_client()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=settings.llm_temperature,
            response_mime_type="application/json",
        ),
    )
    return response.text


# ============================================================
# GROQ CLIENT
# ============================================================

def _call_groq_sync(system_prompt: str, user_content: str) -> str:
    """
    Goi Groq API (sync).
    Tra ve raw text response.
    """
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=settings.llm_temperature,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


# ============================================================
# JSON PARSING + VALIDATION
# ============================================================

def _extract_json(text: str) -> str:
    """
    Trich xuat JSON tu response text.
    LLM doi khi tra ve JSON trong markdown code block.
    """
    # Thu tim JSON trong code block truoc
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Thu tim JSON object hoac array truc tiep
    # Tim { ... } hoac [ ... ] ngoai cung
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return text

    # Tim JSON object bat ky trong text
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)

    return text


def _parse_and_validate(
    raw_text: str,
    response_model: Optional[Type[T]] = None,
) -> Union[dict, T]:
    """
    Parse JSON tu raw text va validate bang Pydantic model (neu co).

    Returns:
        - Dict neu khong co response_model
        - Pydantic model instance neu co response_model
    Raises:
        ValueError neu khong parse duoc JSON
        ValidationError neu khong validate duoc
    """
    json_str = _extract_json(raw_text)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Khong parse duoc JSON tu LLM response.\n"
            f"Raw text (200 ky tu dau): {raw_text[:200]}\n"
            f"Error: {e}"
        )

    if response_model is not None:
        return response_model.model_validate(data)

    return data


# ============================================================
# MAIN CALL FUNCTION
# ============================================================

async def call_llm(
    system_prompt: str,
    user_content: str,
    response_model: Optional[Type[T]] = None,
    agent_name: str = "unknown",
    log_to_db: bool = True,
) -> Union[dict, T, str]:
    """
    Goi LLM voi retry va fallback.

    Flow:
    1. Thu Gemini (max retries lan)
    2. Neu Gemini fail het -> thu Groq (max retries lan)
    3. Neu ca 2 fail -> raise exception

    Args:
        system_prompt: System prompt cho LLM
        user_content: Noi dung nguoi dung / context
        response_model: Pydantic model de validate output (None = tra dict)
        agent_name: Ten agent goi (de log)
        log_to_db: Co ghi log vao DB khong

    Returns:
        dict hoac Pydantic model instance
    """
    max_retries = settings.llm_max_retries
    last_error = None
    start_time = time.time()
    used_model = None
    raw_response = None

    # === Thu Gemini truoc ===
    if settings.gemini_api_key:
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"[{agent_name}] Goi Gemini ({settings.gemini_model}), "
                    f"lan {attempt}/{max_retries}"
                )
                # Chay sync call trong thread pool (google-generativeai la sync)
                raw_response = await asyncio.to_thread(
                    _call_gemini_sync, system_prompt, user_content
                )
                used_model = settings.gemini_model
                result = _parse_and_validate(raw_response, response_model)

                # Log thanh cong
                duration_ms = int((time.time() - start_time) * 1000)
                if log_to_db:
                    await _log_llm_call(
                        agent_name=agent_name,
                        model=used_model,
                        input_summary=_truncate(user_content, 500),
                        output_summary=_truncate(raw_response, 1000),
                        duration_ms=duration_ms,
                    )
                logger.info(
                    f"[{agent_name}] Gemini thanh cong sau {duration_ms}ms"
                )
                return result

            except Exception as e:
                last_error = e
                is_rl = _is_rate_limit_error(e)
                logger.warning(
                    f"[{agent_name}] Gemini lan {attempt} that bai: "
                    f"{type(e).__name__}: {e}"
                    f"{' (RATE LIMIT)' if is_rl else ''}"
                )
                if attempt < max_retries:
                    wait = _get_backoff_seconds(attempt, is_rl)
                    logger.info(f"[{agent_name}] Cho {wait}s truoc khi retry...")
                    await asyncio.sleep(wait)

        logger.warning(
            f"[{agent_name}] Gemini that bai {max_retries} lan. Chuyen sang Groq..."
        )
    else:
        logger.info(f"[{agent_name}] Khong co Gemini API key, dung Groq truc tiep")

    # === Fallback sang Groq ===
    if settings.groq_api_key:
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"[{agent_name}] Goi Groq ({settings.groq_model}), "
                    f"lan {attempt}/{max_retries}"
                )
                raw_response = await asyncio.to_thread(
                    _call_groq_sync, system_prompt, user_content
                )
                used_model = settings.groq_model
                result = _parse_and_validate(raw_response, response_model)

                # Log thanh cong
                duration_ms = int((time.time() - start_time) * 1000)
                if log_to_db:
                    await _log_llm_call(
                        agent_name=agent_name,
                        model=used_model,
                        input_summary=_truncate(user_content, 500),
                        output_summary=_truncate(raw_response, 1000),
                        duration_ms=duration_ms,
                    )
                logger.info(
                    f"[{agent_name}] Groq thanh cong sau {duration_ms}ms"
                )
                return result

            except Exception as e:
                last_error = e
                is_rl = _is_rate_limit_error(e)
                logger.warning(
                    f"[{agent_name}] Groq lan {attempt} that bai: "
                    f"{type(e).__name__}: {e}"
                    f"{' (RATE LIMIT)' if is_rl else ''}"
                )
                if attempt < max_retries:
                    wait = _get_backoff_seconds(attempt, is_rl)
                    await asyncio.sleep(wait)

        logger.error(
            f"[{agent_name}] Groq cung that bai {max_retries} lan."
        )
    else:
        logger.error(f"[{agent_name}] Khong co Groq API key, khong the fallback")

    # === Ca 2 deu fail ===
    duration_ms = int((time.time() - start_time) * 1000)
    if log_to_db:
        await _log_llm_call(
            agent_name=agent_name,
            model=used_model or "none",
            input_summary=_truncate(user_content, 500),
            output_summary=None,
            duration_ms=duration_ms,
            error=str(last_error),
        )

    raise RuntimeError(
        f"[{agent_name}] Tat ca LLM deu that bai sau retry. "
        f"Loi cuoi: {last_error}"
    )


# ============================================================
# CONVENIENCE: call_llm_text (tra ve plain text, khong parse JSON)
# ============================================================

async def call_llm_text(
    system_prompt: str,
    user_content: str,
    agent_name: str = "unknown",
    log_to_db: bool = True,
) -> str:
    """
    Goi LLM va tra ve raw text (khong parse JSON).
    Dung cho ReportAgent hoac khi can free-form text.
    """
    max_retries = settings.llm_max_retries
    last_error = None
    start_time = time.time()
    used_model = None

    # Tao model khong ep JSON
    if settings.gemini_api_key:
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"[{agent_name}] Goi Gemini text ({settings.gemini_model}), "
                    f"lan {attempt}/{max_retries}"
                )
                raw = await asyncio.to_thread(
                    _call_gemini_text_sync, system_prompt, user_content
                )
                used_model = settings.gemini_model
                duration_ms = int((time.time() - start_time) * 1000)
                if log_to_db:
                    await _log_llm_call(
                        agent_name=agent_name,
                        model=used_model,
                        input_summary=_truncate(user_content, 500),
                        output_summary=_truncate(raw, 1000),
                        duration_ms=duration_ms,
                    )
                return raw

            except Exception as e:
                last_error = e
                is_rl = _is_rate_limit_error(e)
                logger.warning(
                    f"[{agent_name}] Gemini text lan {attempt} that bai: {e}"
                    f"{' (RATE LIMIT)' if is_rl else ''}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(_get_backoff_seconds(attempt, is_rl))

    if settings.groq_api_key:
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"[{agent_name}] Goi Groq text ({settings.groq_model}), "
                    f"lan {attempt}/{max_retries}"
                )
                raw = await asyncio.to_thread(
                    _call_groq_text_sync, system_prompt, user_content
                )
                used_model = settings.groq_model
                duration_ms = int((time.time() - start_time) * 1000)
                if log_to_db:
                    await _log_llm_call(
                        agent_name=agent_name,
                        model=used_model,
                        input_summary=_truncate(user_content, 500),
                        output_summary=_truncate(raw, 1000),
                        duration_ms=duration_ms,
                    )
                return raw

            except Exception as e:
                last_error = e
                is_rl = _is_rate_limit_error(e)
                logger.warning(
                    f"[{agent_name}] Groq text lan {attempt} that bai: {e}"
                    f"{' (RATE LIMIT)' if is_rl else ''}"
                )
                if attempt < max_retries:
                    await asyncio.sleep(_get_backoff_seconds(attempt, is_rl))

    raise RuntimeError(
        f"[{agent_name}] call_llm_text that bai. Loi cuoi: {last_error}"
    )


def _call_gemini_text_sync(system_prompt: str, user_content: str) -> str:
    """Goi Gemini tra ve plain text (khong ep JSON)."""
    from google.genai import types

    client = _get_gemini_client()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=settings.llm_temperature,
        ),
    )
    return response.text


def _call_groq_text_sync(system_prompt: str, user_content: str) -> str:
    """Goi Groq tra ve plain text (khong ep JSON)."""
    from groq import Groq
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=settings.llm_temperature,
    )
    return response.choices[0].message.content


# ============================================================
# HELPERS
# ============================================================

def _truncate(text: Optional[str], max_len: int) -> Optional[str]:
    """Cat chuoi de luu vao DB khong qua dai."""
    if text is None:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


async def _log_llm_call(
    agent_name: str,
    model: str,
    input_summary: Optional[str],
    output_summary: Optional[str],
    duration_ms: int,
    error: Optional[str] = None,
):
    """
    Ghi log LLM call vao agent_logs.
    Quiet fail neu DB chua init (VD: khi test local).
    """
    try:
        from services.database import log_agent
        await log_agent(
            agent_name=agent_name,
            input_summary=input_summary,
            output_summary=output_summary,
            llm_model=model,
            duration_ms=duration_ms,
            error=error,
        )
    except Exception as e:
        logger.debug(f"Khong the log LLM call vao DB: {e}")
