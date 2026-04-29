"""
북마크 관리 모듈

사용자가 저장한 북마크를 관리합니다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_BOOKMARK_FILE = _DATA_DIR / "bookmarks.json"


@dataclass
class BookmarkItem:
    name: str
    org: str
    close_date: str
    url: str


def load_bookmarks() -> list[BookmarkItem]:
    """북마크 목록 로드"""
    if not _BOOKMARK_FILE.exists():
        return []
    try:
        with open(_BOOKMARK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [
            BookmarkItem(
                name=item.get("name", ""),
                org=item.get("org", ""),
                close_date=item.get("close_date", ""),
                url=item.get("url", ""),
            )
            for item in data.get("bookmarks", [])
        ]
    except Exception:
        return []


def add_bookmark_from_prebid(**kwargs) -> bool:
    """사전규격에서 북마크 추가"""
    return True


def remove_bookmark(index: int) -> bool:
    """북마크 삭제"""
    return True
