"""
텔레그램 명령어 수집 (Long Polling 방식)

GitHub Actions에서 주기적으로 실행되어 사용자의 텔레그램 명령어를 처리합니다.
/start, /subscribe, /keywords, 관리자 키워드 명령 등을 처리합니다.
"""

from __future__ import annotations

import html
import logging
import os

import requests

from src.storage.state_manager import load_state, save_state
from src.storage.subscriber_manager import (
    add_subscriber,
    get_subscriber_count,
    remove_subscriber,
)
from src.storage.profile_manager import (
    add_profile_keyword,
    get_profile_keywords,
    remove_profile_keyword,
)
from src.storage.admin_manager import (
    add_admin,
    is_admin,
    is_super_admin,
    list_admins,
    remove_admin,
)

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_NAME = "지적측량 용역"


def _escape_html(value: object) -> str:
    """텔레그램 HTML 메시지용 문자열 이스케이프"""
    return html.escape(str(value), quote=True)


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


def _parse_command(text: str) -> tuple[str, str]:
    """명령어와 인자를 분리합니다."""
    parts = text.strip().split(maxsplit=1)
    if not parts:
        return "", ""
    command = parts[0].split("@", 1)[0].lower()
    argument = parts[1].strip() if len(parts) > 1 else ""
    return command, argument


def _require_admin(chat_id: str) -> bool:
    """관리자 권한이 없으면 안내 메시지를 전송합니다."""
    if is_admin(chat_id):
        return True
    _send_reply(chat_id, "⛔ 관리자 전용 명령어입니다.")
    return False


def _format_keywords() -> str:
    keywords = get_profile_keywords(DEFAULT_PROFILE_NAME)
    if not keywords:
        return "등록된 키워드가 없습니다."
    return "\n".join(f"  • {_escape_html(kw)}" for kw in keywords)


def _send_help(chat_id: str) -> None:
    """권한에 맞는 도움말을 전송합니다."""
    lines = [
        "📖 <b>도움말</b>",
        "",
        "/start - 봇 시작 & 구독",
        "/subscribe - 알림 구독",
        "/unsubscribe - 알림 구독 취소",
        "/keywords - 현재 검색 키워드 보기",
        "/help - 이 도움말",
    ]

    if is_admin(chat_id):
        lines.extend([
            "",
            "<b>관리자 명령어</b>",
            "/addkeyword 키워드 - 검색 키워드 추가",
            "/delkeyword 키워드 - 검색 키워드 삭제",
            "/report - 운영 상태 리포트",
            "/admins - 관리자 목록 보기",
        ])

    if is_super_admin(chat_id):
        lines.extend([
            "/addadmin chat_id - 관리자 추가",
            "/deladmin chat_id - 관리자 삭제",
        ])

    _send_reply(chat_id, "\n".join(lines))


def _handle_keyword_add(chat_id: str, keyword: str) -> None:
    if not _require_admin(chat_id):
        return
    if not keyword:
        _send_reply(chat_id, "사용법: /addkeyword 키워드")
        return

    if add_profile_keyword(DEFAULT_PROFILE_NAME, keyword):
        _send_reply(chat_id, f"✅ 키워드 추가 완료: <b>{_escape_html(keyword)}</b>")
    else:
        _send_reply(chat_id, f"이미 있거나 추가할 수 없는 키워드입니다: <b>{_escape_html(keyword)}</b>")


def _handle_keyword_remove(chat_id: str, keyword: str) -> None:
    if not _require_admin(chat_id):
        return
    if not keyword:
        _send_reply(chat_id, "사용법: /delkeyword 키워드")
        return

    if remove_profile_keyword(DEFAULT_PROFILE_NAME, keyword):
        _send_reply(chat_id, f"✅ 키워드 삭제 완료: <b>{_escape_html(keyword)}</b>")
    else:
        _send_reply(chat_id, f"없는 키워드이거나 삭제할 수 없습니다: <b>{_escape_html(keyword)}</b>")


def _handle_admin_add(chat_id: str, target_chat_id: str) -> None:
    if not is_super_admin(chat_id):
        _send_reply(chat_id, "⛔ 슈퍼 관리자 전용 명령어입니다.")
        return
    if not target_chat_id:
        _send_reply(chat_id, "사용법: /addadmin chat_id")
        return

    if add_admin(target_chat_id):
        _send_reply(chat_id, f"✅ 관리자 추가 완료: <code>{_escape_html(target_chat_id)}</code>")
    else:
        _send_reply(chat_id, f"이미 관리자이거나 추가할 수 없습니다: <code>{_escape_html(target_chat_id)}</code>")


def _handle_admin_remove(chat_id: str, target_chat_id: str) -> None:
    if not is_super_admin(chat_id):
        _send_reply(chat_id, "⛔ 슈퍼 관리자 전용 명령어입니다.")
        return
    if not target_chat_id:
        _send_reply(chat_id, "사용법: /deladmin chat_id")
        return

    if remove_admin(target_chat_id):
        _send_reply(chat_id, f"✅ 관리자 삭제 완료: <code>{_escape_html(target_chat_id)}</code>")
    else:
        _send_reply(chat_id, f"관리자 목록에 없습니다: <code>{_escape_html(target_chat_id)}</code>")


def _send_admins(chat_id: str) -> None:
    if not _require_admin(chat_id):
        return

    admins = list_admins()
    lines = ["👮 <b>관리자 목록</b>"]
    if is_super_admin(chat_id):
        lines.append(f"슈퍼 관리자: <code>{_escape_html(chat_id)}</code>")
    if admins:
        lines.append("일반 관리자:")
        lines.extend(f"  • <code>{_escape_html(admin)}</code>" for admin in admins)
    else:
        lines.append("일반 관리자 없음")
    _send_reply(chat_id, "\n".join(lines))


def _send_report(chat_id: str, mode: str = "prebid") -> None:
    if not _require_admin(chat_id):
        return

    state = load_state()
    keywords = get_profile_keywords(DEFAULT_PROFILE_NAME)
    lines = [
        "📊 <b>운영 리포트</b>",
        f"구독자 수: <b>{get_subscriber_count(mode)}</b>",
        f"키워드 수: <b>{len(keywords)}</b>",
        f"마지막 성공 체크: <code>{_escape_html(state.get('last_check') or '-')}</code>",
        f"입찰공고 알림 기록: <b>{len(state.get('notified_bids', {}))}</b>",
        f"사전규격 알림 기록: <b>{len(state.get('notified_prebids', {}))}</b>",
        f"텔레그램 offset: <code>{_escape_html(state.get('telegram_offset_prebid', 0))}</code>",
    ]
    _send_reply(chat_id, "\n".join(lines))


def _handle_command(chat_id: str, text: str, mode: str = "prebid") -> None:
    """명령어 처리"""
    cmd, argument = _parse_command(text)

    if cmd == "/start":
        add_subscriber(str(chat_id), mode=mode)
        _send_reply(chat_id,
            "안녕하세요! 🏗️ <b>나라장터 입찰 알림 봇</b>입니다.\n\n"
            "• 주간에는 30분마다, 야간/주말에는 2시간마다 새 공고를 확인합니다.\n"
            "• 사전규격, 입찰공고 알림을 받을 수 있습니다.\n\n"
            "<b>명령어:</b>\n"
            "/subscribe - 알림 구독\n"
            "/unsubscribe - 알림 구독 취소\n"
            "/keywords - 현재 검색 키워드 보기\n"
            "/help - 도움말"
        )

    elif cmd == "/subscribe":
        was_new = add_subscriber(str(chat_id), mode=mode)
        if was_new:
            _send_reply(chat_id, "✅ 알림 구독이 완료되었습니다!")
        else:
            _send_reply(chat_id, "이미 구독 중입니다. 😊")

    elif cmd == "/unsubscribe":
        if remove_subscriber(str(chat_id), mode=mode):
            _send_reply(chat_id, "✅ 알림 구독을 취소했습니다.")
        else:
            _send_reply(chat_id, "현재 구독 중이 아닙니다.")

    elif cmd == "/keywords":
        _send_reply(chat_id, f"🔍 <b>현재 검색 키워드:</b>\n{_format_keywords()}")

    elif cmd == "/help":
        _send_help(chat_id)

    elif cmd in {"/addkeyword", "/addkw"}:
        _handle_keyword_add(chat_id, argument)

    elif cmd in {"/delkeyword", "/deletekeyword", "/removekeyword", "/delkw"}:
        _handle_keyword_remove(chat_id, argument)

    elif cmd == "/admins":
        _send_admins(chat_id)

    elif cmd == "/addadmin":
        _handle_admin_add(chat_id, argument)

    elif cmd in {"/deladmin", "/removeadmin"}:
        _handle_admin_remove(chat_id, argument)

    elif cmd in {"/report", "/status"}:
        _send_report(chat_id, mode=mode)

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
