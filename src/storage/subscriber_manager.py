"""
구독자 관리자 (Subscriber Manager)

알림을 받을 일반 사용자(구독자) 목록을 관리합니다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _get_path(mode: str) -> Path:
    """모드별 구독자 파일 경로 반환"""
    return _DATA_DIR / f"subscribers_{mode}.json"


def load_subscribers(mode: str = "prebid") -> set[str]:
    """구독자 Chat ID 목록을 로드합니다."""
    path = _get_path(mode)
    legacy_path = _DATA_DIR / "subscribers.json"

    if not path.exists():
        if legacy_path.exists():
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                legacy_subs = set(str(item) for item in data.get("subscribers", []))
                if legacy_subs:
                    logger.info("기존 subscribers.json에서 %s으로 마이그레이션", path.name)
                    save_subscribers(legacy_subs, mode=mode)
                    return legacy_subs
            except Exception as e:
                logger.error("기존 구독자 데이터 마이그레이션 실패: %s", e)
        return set()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(str(item) for item in data.get("subscribers", []))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("%s 로드 실패: %s", path.name, e)
        return set()


def save_subscribers(subscribers: set[str], mode: str = "prebid") -> None:
    """구독자 목록을 저장합니다."""
    path = _get_path(mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"subscribers": sorted(list(subscribers))}, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("%s 저장 실패: %s", path.name, e)


def add_subscriber(chat_id: str, mode: str = "prebid") -> bool:
    """새로운 구독자를 추가합니다."""
    chat_id = str(chat_id)
    subscribers = load_subscribers(mode)
    if chat_id in subscribers:
        return False
    subscribers.add(chat_id)
    save_subscribers(subscribers, mode)
    logger.info("새로운 구독자 자동 등록 (%s): %s", mode, chat_id)
    return True


def remove_subscriber(chat_id: str, mode: str = "prebid") -> bool:
    """구독자를 제거합니다."""
    chat_id = str(chat_id)
    subscribers = load_subscribers(mode)
    if chat_id not in subscribers:
        return False
    subscribers.discard(chat_id)
    save_subscribers(subscribers, mode)
    logger.info("구독 취소 (%s): %s", mode, chat_id)
    return True


def get_subscriber_count(mode: str = "prebid") -> int:
    """현재 등록된 총 구독자 수를 반환합니다."""
    return len(load_subscribers(mode))
