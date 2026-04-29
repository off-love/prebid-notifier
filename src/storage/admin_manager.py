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


def is_admin(chat_id: str) -> bool:
    """관리자 여부 확인"""
    super_admin = get_super_admin_id()
    if str(chat_id) == super_admin:
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
