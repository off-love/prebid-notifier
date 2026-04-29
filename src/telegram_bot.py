"""
텔레그램 봇 — 메시지 발송

텔레그램 Bot API를 통해 알림 메시지를 전송합니다.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from src.core.models import BroadcastResult

logger = logging.getLogger(__name__)


# ─── 적응형 스로틀링 ────────────────────────────────────────

class AdaptiveThrottle:
    """429 응답에 따라 발송 간격을 자동 조절합니다."""

    def __init__(self, initial_delay: float = 0.04, max_delay: float = 1.0):
        self.delay = initial_delay
        self.initial_delay = initial_delay
        self.max_delay = max_delay

    def wait(self) -> None:
        time.sleep(self.delay)

    def on_success(self) -> None:
        self.delay = max(self.delay * 0.95, self.initial_delay)

    def on_rate_limit(self, retry_after: int = 5) -> None:
        self.delay = min(self.delay * 2, self.max_delay)
        logger.warning("스로틀 감속: 발송 간격 %.3f초로 증가", self.delay)


# ─── 내부 유틸 ────────────────────────────────────────────────

def _get_bot_token(mode: str = "prebid") -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
    return token


def _get_chat_id(mode: str = "prebid") -> str:
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID 환경변수가 설정되지 않았습니다.")
    return chat_id


def _sanitize_error(error: object) -> str:
    """로그에 텔레그램 토큰이 노출되지 않도록 오류 문자열을 정리합니다."""
    message = str(error)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        message = message.replace(token, "[REDACTED]")
    return message


def _split_text(text: str, max_length: int) -> list[str]:
    """텍스트를 줄 단위로 분할"""
    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_length and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def _send_with_retry(
    url: str,
    payload: dict,
    max_retries: int = 3,
    throttle: AdaptiveThrottle | None = None,
) -> tuple[dict | None, str | None]:
    """429 Rate Limit 자동 재시도"""
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            data = resp.json()

            if data.get("ok"):
                if throttle:
                    throttle.on_success()
                return data, None

            if resp.status_code == 429:
                retry_after = data.get("parameters", {}).get("retry_after", 5)
                logger.warning(
                    "Rate limit! %d초 대기 후 재시도 (%d/%d)",
                    retry_after, attempt + 1, max_retries,
                )
                if throttle:
                    throttle.on_rate_limit(retry_after)
                time.sleep(retry_after)
                continue

            return data, data.get("description", "Unknown error")

        except requests.RequestException as e:
            safe_error = _sanitize_error(e)
            logger.error("텔레그램 API 호출 실패 (시도 %d/%d): %s", attempt + 1, max_retries, safe_error)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None, safe_error

    return None, "Max retries exceeded"


# ─── 단일 메시지 전송 ─────────────────────────────────────────

def send_message(
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    chat_id: str | None = None,
    reply_markup: dict | None = None,
    mode: str = "prebid",
) -> bool:
    """텔레그램 메시지 전송"""
    token = _get_bot_token(mode)
    if chat_id is None:
        chat_id = _get_chat_id(mode)

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    data, error = _send_with_retry(url, payload)

    if error is None:
        logger.info("텔레그램 메시지 전송 성공")
        return True

    logger.error("텔레그램 전송 실패: %s", error)

    if error and "message is too long" in error.lower():
        return _send_long_message(text, parse_mode, chat_id, mode=mode)

    return False


def _send_long_message(
    text: str,
    parse_mode: str,
    chat_id: str,
    max_length: int = 4000,
    mode: str = "prebid",
) -> bool:
    """긴 메시지를 분할하여 전송"""
    token = _get_bot_token(mode)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = _split_text(text, max_length)
    all_ok = True

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        data, error = _send_with_retry(url, payload)
        if error:
            logger.error("분할 전송 실패 (%d/%d): %s", i + 1, len(chunks), error)
            all_ok = False

        if i < len(chunks) - 1:
            time.sleep(0.5)

    return all_ok


# ─── 단일 수신자 순차 전송 ──────────────────────────────────

def send_notifications(
    messages: list[dict[str, Any]] | list[str],
    mode: str = "prebid",
    chat_id: str | None = None,
) -> int:
    """여러 알림 메시지를 순차 전송"""
    success_count = 0
    for i, msg in enumerate(messages):
        if isinstance(msg, dict):
            text = msg.get("text", "")
            reply_markup = msg.get("reply_markup")
            is_success = send_message(text, reply_markup=reply_markup, chat_id=chat_id, mode=mode)
        else:
            is_success = send_message(msg, chat_id=chat_id, mode=mode)

        if is_success:
            success_count += 1

        if i < len(messages) - 1:
            time.sleep(1)
    return success_count


# ─── 다중 수신자 브로드캐스트 ──────────────────────────────────

def broadcast_message(
    text: str,
    target_chat_ids: set[str],
    reply_markup: dict | None = None,
    mode: str = "prebid",
    progress_interval: int = 50,
) -> BroadcastResult:
    """하나의 메시지를 다수에게 발송합니다."""
    start_time = time.time()
    result = BroadcastResult(total=len(target_chat_ids))
    throttle = AdaptiveThrottle()

    token = _get_bot_token(mode)
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    chunks = _split_text(text, 4000)
    sent_count = 0

    for chunk in chunks:
        base_payload = {
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if chunk == chunks[-1] and reply_markup is not None:
            base_payload["reply_markup"] = reply_markup

        for chat_id in target_chat_ids:
            if chat_id in result.blocked_ids or chat_id in result.error_ids:
                continue

            payload = {**base_payload, "chat_id": chat_id}
            data, error = _send_with_retry(url, payload, max_retries=3, throttle=throttle)

            if error is None:
                result.success_count += 1
            else:
                desc = (error or "").lower()
                if any(err in desc for err in ["forbidden", "chat not found", "bot was blocked", "deactivated"]):
                    result.blocked_ids.append(chat_id)
                    result.fail_count += 1
                    logger.warning("유효하지 않은 사용자 감지(차단/탈퇴): %s", chat_id)
                elif "429" in str(error) or "max retries" in desc:
                    result.rate_limited_count += 1
                    result.fail_count += 1
                    logger.error("Rate limit 초과로 발송 실패 [%s]", chat_id)
                else:
                    result.error_ids.append(chat_id)
                    result.fail_count += 1
                    logger.error("메시지 전송 실패 [%s]: %s", chat_id, error)

            sent_count += 1
            if progress_interval > 0 and sent_count % progress_interval == 0:
                pct = sent_count / result.total * 100
                logger.info("발송 진행: %d/%d (%.1f%%)", sent_count, result.total, pct)

            throttle.wait()

    result.elapsed_seconds = round(time.time() - start_time, 2)
    return result


def broadcast_notifications(
    messages: list[dict[str, Any] | str],
    target_chat_ids: set[str],
    mode: str = "prebid",
) -> BroadcastResult:
    """여러 알림 메시지 목록을 다수에게 순차적으로 발송합니다."""
    combined = BroadcastResult(total=len(target_chat_ids))
    current_chat_ids = set(target_chat_ids)

    for i, msg in enumerate(messages):
        if not current_chat_ids:
            break

        if isinstance(msg, dict):
            text = msg.get("text", "")
            markup = msg.get("reply_markup")
        else:
            text = msg
            markup = None

        partial = broadcast_message(text, current_chat_ids, reply_markup=markup, mode=mode)
        combined.merge(partial)

        for inv_id in partial.invalid_ids:
            current_chat_ids.discard(inv_id)

        if i < len(messages) - 1:
            time.sleep(1)

    return combined
