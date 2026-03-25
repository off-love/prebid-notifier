"""
메인 실행 스크립트

GitHub Actions cron 에 의해 30분마다 실행됩니다.
프로필별로 사전규격을 조회하고, 필터링 후 텔레그램으로 알림을 보냅니다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from src.api.prebid_client import fetch_prebid_notices
from src.core.filter import filter_notices
from src.core.formatter import (
    format_notice,
    format_summary,
)
from src.core.models import AlertProfile, BidType
from src.storage.profile_manager import load_profiles
from src.storage.state_manager import (
    cleanup_old_records,
    is_notified,
    load_state,
    mark_notified,
    save_state,
    update_last_check,
)
from src.telegram_bot import send_message
from src.utils.time_utils import now_kst

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def process_profile(profile: AlertProfile, state: dict, settings: dict) -> int:
    """단일 프로필을 처리합니다.

    Args:
        profile: 알림 프로필
        state: 상태 데이터
        settings: 전역 설정

    Returns:
        사전규격 알림 수
    """
    logger.info("━━━ 프로필 처리: %s ━━━", profile.name)

    prebid_messages: list[Any] = []
    buffer_hours = settings.get("query_buffer_hours", 1)
    max_results = settings.get("max_results_per_page", 999)
    def fetch_all_prebids():
        messages = []
        seen_keys = set()
        for bid_type in profile.bid_types:
            keywords = profile.keywords.or_keywords or [""]
            for kw in keywords:
                raw_prebids = fetch_prebid_notices(
                    bid_type=bid_type,
                    keyword=kw,
                    buffer_hours=buffer_hours,
                    max_results=max_results,
                )
                filtered = filter_notices(raw_prebids, profile)
                for prebid in filtered:
                    if prebid.unique_key in seen_keys: continue
                    seen_keys.add(prebid.unique_key)
                    if is_notified(state, prebid.unique_key, "prebid"): continue
                    msg = format_notice(prebid, profile.name, matched_keyword=kw)
                    messages.append({"text": msg})
                    mark_notified(state, prebid.unique_key, profile.name, "prebid")
        return messages

    prebid_messages = fetch_all_prebids()

    # ── 3. 텔레그램 발송 ──
    all_messages = prebid_messages

    if all_messages:
        logger.info(
            "알림 발송: 사전규격 %d건",
            len(prebid_messages),
        )
        from src.telegram_bot import broadcast_notifications
        sent = broadcast_notifications(all_messages)
        logger.info("방송 완료: %d/%d건", sent, len(all_messages))
    else:
        logger.info("신규 알림 없음")

    # 요약 메시지 (알림이 있을 때만)
    if all_messages:
        summary = format_summary(
            profile_name=profile.name,
            prebid_count=len(prebid_messages),
            check_time=now_kst().strftime("%H:%M"),
        )
        from src.telegram_bot import broadcast_message
        broadcast_message(summary)

    return len(prebid_messages)


def main() -> None:
    """메인 실행"""
    logger.info("=" * 50)
    logger.info("나라장터 알림 서비스 시작 (사전규격 전용)")
    logger.info("=" * 50)

    try:
        # 프로필 로드
        profiles, settings_obj = load_profiles()
        settings = {
            "query_buffer_hours": settings_obj.query_buffer_hours,
            "max_results_per_page": settings_obj.max_results_per_page,
        }

        if not profiles:
            logger.warning("활성 프로필이 없습니다. profiles.yaml을 확인하세요.")
            return

        logger.info("활성 프로필 %d개 로드 완료", len(profiles))

        # 상태 로드
        state = load_state()

        # 오래된 기록 정리
        cleanup_old_records(state)

        total_prebids = 0

        # 프로필별 처리
        for profile in profiles:
            try:
                prebid_count = process_profile(profile, state, settings)
                total_prebids += prebid_count
            except Exception as e:
                logger.error("프로필 '%s' 처리 오류: %s", profile.name, e, exc_info=True)
                # 오류 알림
                try:
                    send_message(
                        f"⚠️ 프로필 '{profile.name}' 처리 중 오류 발생: {e}"
                    )
                except Exception:
                    pass

        # 상태 저장
        update_last_check(state)
        save_state(state)

        logger.info("=" * 50)
        logger.info(
            "전체 완료: 사전규격 %d건 알림",
            total_prebids,
        )
        logger.info("=" * 50)

    except Exception as e:
        logger.critical("치명적 오류: %s", e, exc_info=True)
        try:
            send_message(f"🚨 나라장터 알림 서비스 오류: {e}")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
