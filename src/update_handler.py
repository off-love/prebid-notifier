"""
텔레그램 명령어 수집 (Long Polling 방식)

GitHub Actions에서 주기적으로 실행되어 사용자의 텔레그램 명령어를 처리합니다.
/start, /subscribe, /search, /keywords 등의 명령어를 처리합니다.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import requests

from src.storage.state_manager import load_state, save_state
from src.storage.subscriber_manager import add_subscriber, load_subscribers
from src.storage.profile_manager import get_profile_keywords

logger = logging.getLogger(__name__)

STATE_PATH = Path(__file__).parent.parent / "data" / "state.json"


def _get_bot_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
    return token


def _sanitize_error(error: object) -> str:
    """로그에 텔레그램 토큰이 노출되지 않도록 오류 문자열을 정리합니다."""
    message = str(error)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        message = message.replace(token, "[REDACTED]")
    return message


def _send_reply(chat_id: str, text: str) -> bool:
    """텔레그램 메시지 응답"""
    token = _get_bot_token()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        return data.get("ok", False)
    except Exception as e:
        logger.error("응답 전송 실패 [%s]: %s", chat_id, _sanitize_error(e))
        return False


def _get_updates(offset: int | None = None, timeout: int = 5) -> list[dict]:
    """텔레그램 업데이트 가져오기"""
    token = _get_bot_token()
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": timeout}
    if offset:
        params["offset"] = offset

    try:
        resp = requests.get(url, params=params, timeout=timeout + 5)
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    except Exception as e:
        logger.error("업데이트 가져오기 실패: %s", _sanitize_error(e))

    return []


def _handle_command(chat_id: str, text: str, mode: str = "prebid") -> None:
    """명령어 처리"""
    cmd = text.strip().lower().split()[0] if text.strip() else ""

    if cmd == "/start":
        add_subscriber(str(chat_id), mode=mode)
        _send_reply(chat_id,
            "안녕하세요! 🏗️ <b>나라장터 입찰 알림 봇</b>입니다.\n\n"
            "• 주간에는 30분마다, 야간/주말에는 2시간마다 새 공고를 확인합니다.\n"
            "• 사전규격, 입찰공고 알림을 받을 수 있습니다.\n\n"
            "<b>명령어:</b>\n"
            "/subscribe - 알림 구독\n"
            "/keywords - 현재 검색 키워드 보기\n"
            "/help - 도움말"
        )

    elif cmd == "/subscribe":
        was_new = add_subscriber(str(chat_id), mode=mode)
        if was_new:
            _send_reply(chat_id, "✅ 알림 구독이 완료되었습니다!")
        else:
            _send_reply(chat_id, "이미 구독 중입니다. 😊")

    elif cmd == "/keywords":
        keywords = get_profile_keywords("지적측량 용역")
        if keywords:
            kw_list = "\n".join(f"  • {kw}" for kw in keywords)
            _send_reply(chat_id,
                f"🔍 <b>현재 검색 키워드:</b>\n{kw_list}"
            )
        else:
            _send_reply(chat_id, "등록된 키워드가 없습니다.")

    elif cmd == "/help":
        _send_reply(chat_id,
            "📖 <b>도움말</b>\n\n"
            "/start - 봇 시작 & 구독\n"
            "/subscribe - 알림 구독\n"
            "/keywords - 검색 키워드 보기\n"
            "/help - 이 도움말"
        )

    else:
        # 알 수 없는 명령어는 무시
        pass


def process_updates(mode: str = "prebid") -> int:
    """텔레그램 업데이트를 처리합니다.

    Returns:
        처리된 업데이트 수
    """
    state = load_state()
    offset_key = f"telegram_offset_{mode}" if mode != "prebid" else "telegram_offset_prebid"
    offset = state.get(offset_key)

    updates = _get_updates(offset=offset)
    processed = 0

    for update in updates:
        update_id = update.get("update_id", 0)

        # 메시지 처리
        message = update.get("message", {})
        if message:
            chat_id = str(message.get("chat", {}).get("id", ""))
            text = message.get("text", "")

            if text and text.startswith("/"):
                logger.info("명령어 수신 [%s]: %s", chat_id, text)
                _handle_command(chat_id, text, mode)
                processed += 1
            elif chat_id:
                # /start 를 보내지 않은 사용자도 자동 구독
                add_subscriber(chat_id, mode=mode)

        # 다음 offset 업데이트
        state[offset_key] = update_id + 1

    if processed > 0:
        logger.info("텔레그램 명령어 %d건 처리 완료", processed)

    save_state(state)
    return processed


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    process_updates(mode="prebid")
