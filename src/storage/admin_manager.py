"""
관리자 관리 모듈

봇 관리자 권한을 관리합니다.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_ADMIN_FILE = _DATA_DIR / "admins.json"


def get_super_admin_id() -> str:
    """슈퍼 관리자 Chat ID 반환"""
    return os.environ.get("SUPER_ADMIN_CHAT_ID", "")


def is_super_admin(chat_id: str) -> bool:
    """슈퍼 관리자 여부 확인"""
    super_admin = get_super_admin_id()
    return bool(super_admin) and str(chat_id) == super_admin


def is_admin(chat_id: str) -> bool:
    """관리자 여부 확인"""
    if is_super_admin(chat_id):
        return True

    admins = _load_admins()
    return str(chat_id) in admins


def _load_admins() -> set[str]:
    """관리자 목록 로드"""
    if not _ADMIN_FILE.exists():
        return set()
    try:
        with open(_ADMIN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(str(a) for a in data.get("admins", []))
    except Exception:
        return set()


def _save_admins(admins: set[str]) -> None:
    """관리자 목록 저장"""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_ADMIN_FILE, "w", encoding="utf-8") as f:
        json.dump({"admins": sorted(admins)}, f, ensure_ascii=False, indent=2)


def list_admins() -> list[str]:
    """일반 관리자 목록 반환"""
    return sorted(_load_admins())


def add_admin(chat_id: str) -> bool:
    """일반 관리자 추가"""
    chat_id = str(chat_id).strip()
    if not chat_id or is_super_admin(chat_id):
        return False

    admins = _load_admins()
    if chat_id in admins:
        return False

    admins.add(chat_id)
    _save_admins(admins)
    logger.info("관리자 추가: %s", chat_id)
    return True


def remove_admin(chat_id: str) -> bool:
    """일반 관리자 삭제"""
    chat_id = str(chat_id).strip()
    admins = _load_admins()
    if chat_id not in admins:
        return False

    admins.remove(chat_id)
    _save_admins(admins)
    logger.info("관리자 삭제: %s", chat_id)
    return True
