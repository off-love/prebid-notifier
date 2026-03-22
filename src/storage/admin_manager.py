"""
관리자 권한 관리자 (Admin Manager)

슈퍼 관리자(환경변수)와 일반 관리자(JSON 파일)를 구분하여 관리합니다.

- 슈퍼 관리자: SUPER_ADMIN_CHAT_ID 환경변수로 지정 (1명)
- 일반 관리자: config/admins.json 에 저장 (슈퍼 관리자가 추가/제거 가능)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# admins.json 경로 (프로젝트 루트/config/admins.json)
_ADMINS_PATH = Path(__file__).parent.parent.parent / "config" / "admins.json"


def _get_super_admin_id() -> str | None:
    """환경변수에서 슈퍼 관리자 Chat ID를 가져옵니다."""
    return os.environ.get("SUPER_ADMIN_CHAT_ID", "").strip() or None


def load_admins() -> set[str]:
    """admins.json에서 일반 관리자 Chat ID 목록을 로드합니다.

    Returns:
        관리자 Chat ID의 집합 (str). 파일이 없으면 빈 집합 반환.
    """
    if not _ADMINS_PATH.exists():
        return set()

    try:
        with open(_ADMINS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(str(item) for item in data.get("admins", []))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("admins.json 로드 실패: %s", e)
        return set()


def save_admins(admins: set[str]) -> None:
    """관리자 목록을 admins.json에 저장합니다.

    Args:
        admins: 저장할 관리자 Chat ID 집합
    """
    _ADMINS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_ADMINS_PATH, "w", encoding="utf-8") as f:
            json.dump({"admins": sorted(admins)}, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("admins.json 저장 실패: %s", e)


def is_super_admin(chat_id: str) -> bool:
    """주어진 chat_id가 슈퍼 관리자인지 확인합니다.

    Args:
        chat_id: 확인할 텔레그램 Chat ID (문자열)

    Returns:
        슈퍼 관리자이면 True
    """
    super_id = _get_super_admin_id()
    if not super_id:
        return False
    return str(chat_id) == super_id


def is_admin(chat_id: str) -> bool:
    """주어진 chat_id가 관리자(슈퍼 관리자 포함)인지 확인합니다.

    Args:
        chat_id: 확인할 텔레그램 Chat ID (문자열)

    Returns:
        관리자이면 True
    """
    if is_super_admin(chat_id):
        return True
    return str(chat_id) in load_admins()


def add_admin(chat_id: str) -> bool:
    """일반 관리자를 추가합니다.

    Args:
        chat_id: 추가할 텔레그램 Chat ID

    Returns:
        추가 성공 시 True, 이미 존재하면 False
    """
    chat_id = str(chat_id)
    admins = load_admins()

    if chat_id in admins:
        return False

    admins.add(chat_id)
    save_admins(admins)
    logger.info("관리자 추가: %s", chat_id)
    return True


def remove_admin(chat_id: str) -> bool:
    """일반 관리자를 제거합니다. 슈퍼 관리자는 제거 불가.

    Args:
        chat_id: 제거할 텔레그램 Chat ID

    Returns:
        제거 성공 시 True, 존재하지 않으면 False
    """
    chat_id = str(chat_id)

    # 슈퍼 관리자는 이 방법으로 제거 불가
    if is_super_admin(chat_id):
        logger.warning("슈퍼 관리자 제거 시도 차단: %s", chat_id)
        return False

    admins = load_admins()
    if chat_id not in admins:
        return False

    admins.discard(chat_id)
    save_admins(admins)
    logger.info("관리자 제거: %s", chat_id)
    return True


def get_all_admins() -> list[str]:
    """슈퍼 관리자 포함 전체 관리자 목록을 반환합니다.

    Returns:
        관리자 Chat ID 목록 (슈퍼 관리자가 있으면 맨 앞에 위치)
    """
    result: list[str] = []
    super_id = _get_super_admin_id()
    if super_id:
        result.append(super_id)

    regular = sorted(load_admins() - ({super_id} if super_id else set()))
    result.extend(regular)
    return result
