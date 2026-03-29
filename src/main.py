"""
메인 실행 스크립트

GitHub Actions cron 에 의해 30분마다 실행됩니다.
프로필별로 사전규격을 조회하고, 필터링 후 텔레그램으로 알림을 보냅니다.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from src.api.prebid_client import fetch_prebid_notices
from src.core.filter import filter_notices
from src.core.formatter import (
    format_notice,
    format_summary,
)
from src.core.models import AlertProfile, BroadcastResult
from src.storage.profile_manager import load_profiles
from src.storage.state_manager import (
    cleanup_old_records,
    is_notified,
    load_state,
    mark_notified,
    save_state,
    update_last_check,
)
from src.storage.admin_manager import get_all_admins
from src.storage.subscriber_manager import load_subscribers, remove_subscriber, get_subscriber_count
from src.telegram_bot import (
    send_message,
    broadcast_message,
    broadcast_notifications,
)
from src.utils.time_utils import now_kst

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _log_broadcast_report(result: BroadcastResult) -> None:
    """브로드캐스트 결과를 구조화하여 로깅합니다."""
    logger.info(
        "📊 발송 리포트: 대상 %d명 | 성공 %d | 차단/탈퇴 %d | 오류 %d | "
        "Rate Limit 재시도 %d회 | 소요 %.1f초",
        result.total,
        result.success_count,
        result.blocked_count,
        result.error_count,
        result.rate_limited_count,
        result.elapsed_seconds,
    )


def _format_admin_dashboard(
    profile_name: str,
    prebid_count: int,
    result: BroadcastResult,
    check_time: str,
    remaining_subscribers: int,
) -> str:
    """슈퍼관리자용 대시보드 메시지를 생성합니다."""
    lines = [
        f"📊 <b>사전규격 알림 리포트</b> ({check_time})",
        f"├── 프로필: {profile_name}",
        f"├── 신규 공고: {prebid_count}건",
        f"├── 발송 대상: {result.total}명",
        f"├── 성공: {result.success_count}건 / 실패: {result.fail_count}건",
        f"├── 소요 시간: {result.elapsed_seconds}초",
    ]

    if result.rate_limited_count > 0:
        lines.append(f"├── ⚠️ Rate Limit 재시도: {result.rate_limited_count}회")

    if result.blocked_count > 0:
        lines.append(f"├── 🚫 자동 정리: 차단/탈퇴 {result.blocked_count}명")

    lines.append(f"└── 활성 구독자: {remaining_subscribers}명")

    return "\n".join(lines)


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
                raw_notices = fetch_prebid_notices(
                    bid_type=bid_type,
                    keyword=kw,
                    buffer_hours=buffer_hours,
                    max_results=max_results,
                )
                filtered = filter_notices(raw_notices, profile)
                for notice in filtered:
                    if notice.unique_key in seen_keys: continue
                    seen_keys.add(notice.unique_key)
                    if is_notified(state, notice.unique_key, "prebid"): continue
                    msg = format_notice(notice, profile.name, matched_keyword=kw)
                    messages.append({"text": msg})
                    mark_notified(state, notice.unique_key, profile.name, "prebid")
        return messages

    prebid_messages = fetch_all_prebids()

    # ── 텔레그램 발송 ──
    if prebid_messages:
        logger.info("알림 발송: 사전규격 %d건", len(prebid_messages))

        # 전송 대상 수집: 슈퍼관리자 + 일반관리자 + 구독자 (중복 제거)
        super_admin = os.environ.get("SUPER_ADMIN_CHAT_ID", "")
        admin_ids = get_all_admins()
        subscribers = load_subscribers(mode="prebid")

        target_chat_ids = set()
        if super_admin:
            target_chat_ids.add(str(super_admin))
        for aid in admin_ids:
            target_chat_ids.add(str(aid))
        for sub_id in subscribers:
            target_chat_ids.add(str(sub_id))

        # 브로드캐스트 발송 (BroadcastResult 반환)
        result: BroadcastResult = broadcast_notifications(
            prebid_messages, target_chat_ids=target_chat_ids, mode="prebid"
        )

        # ── 상세 발송 리포트 로깅 ──
        _log_broadcast_report(result)

        # ── 차단/탈퇴 사용자 자동 정리 ──
        if result.blocked_ids:
            for inv_id in result.blocked_ids:
                if inv_id in subscribers:
                    remove_subscriber(inv_id, mode="prebid")
                    logger.info("차단/탈퇴한 구독자 자동 삭제 완료: %s", inv_id)

            # 관리자에게 정리 알림
            remaining = get_subscriber_count(mode="prebid")
            cleanup_msg = (
                f"⚠️ <b>자동 정리된 구독자:</b> {result.blocked_count}명\n"
                f"현재 활성 구독자: {remaining}명"
            )
            if super_admin:
                send_message(cleanup_msg, chat_id=super_admin, mode="prebid")

        # ── 요약 메시지 ──
        check_time = now_kst().strftime("%H:%M")
        summary = format_summary(
            profile_name=profile.name,
            prebid_count=len(prebid_messages),
            check_time=check_time,
        )
        filtered_targets = target_chat_ids - set(result.invalid_ids)
        if filtered_targets:
            broadcast_message(summary, target_chat_ids=filtered_targets, mode="prebid")

        # ── 관리자 대시보드 메시지 (슈퍼관리자 + 일반관리자) ──
        admin_ids_for_dashboard = set(str(aid) for aid in get_all_admins())
        if admin_ids_for_dashboard:
            remaining = get_subscriber_count(mode="prebid")
            dashboard = _format_admin_dashboard(
                profile_name=profile.name,
                prebid_count=len(prebid_messages),
                result=result,
                check_time=check_time,
                remaining_subscribers=remaining,
            )
            broadcast_message(dashboard, target_chat_ids=admin_ids_for_dashboard, mode="prebid")
    else:
        logger.info("신규 알림 없음")

    return len(prebid_messages)


def main() -> None:
    """메인 실행"""
    logger.info("=" * 50)
    logger.info("나라장터 사전규격 알림 서비스 시작")
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
                try:
                    send_message(
                        f"⚠️ 프로필 '{profile.name}' 처리 중 오류 발생: {e}", mode="prebid"
                    )
                except Exception:
                    pass

        # 상태 저장
        update_last_check(state)
        save_state(state)

        logger.info("=" * 50)
        logger.info("전체 완료: 사전규격 %d건 알림", total_prebids)
        logger.info("=" * 50)

    except Exception as e:
        logger.critical("치명적 오류: %s", e, exc_info=True)
        try:
            send_message(f"🚨 나라장터 사전규격 알림 서비스 오류: {e}", mode="prebid")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
