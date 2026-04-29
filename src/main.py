"""
나라장터 입찰 알림 서비스 — 메인 실행 스크립트

GitHub Actions에서 주기적으로 실행되어:
1. 프로필 설정을 로드
2. 프로필별 사전규격/입찰공고를 API에서 조회
3. 키워드/조건 필터링
4. 중복 확인 (state.json)
5. 신규 공고를 텔레그램으로 발송
6. 상태 저장
"""

from __future__ import annotations

import logging
import os
import sys

from src.api.prebid_client import fetch_prebid_notices
from src.api.bid_client import fetch_bid_notices
from src.core.filter import filter_notices
from src.core.formatter import format_prebid_notice, format_bid_notice, format_summary
from src.core.models import PreBidNotice, BidNotice
from src.storage.profile_manager import load_profiles
from src.storage.state_manager import (
    load_state,
    save_state,
    is_notified,
    mark_notified,
    update_last_check,
    cleanup_old_records,
)
from src.storage.subscriber_manager import load_subscribers
from src.telegram_bot import send_message, broadcast_message
from src.utils.time_utils import now_kst

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def process_profile(profile, settings, state):
    """단일 프로필에 대해 사전규격 + 입찰공고를 조회하고 알림을 발송합니다."""
    logger.info("=" * 50)
    logger.info("프로필 처리: %s (업종: %s)",
                profile.name,
                ", ".join(bt.display_name for bt in profile.bid_types))
    logger.info("=" * 50)

    all_prebid_notices = []
    all_bid_notices = []
    or_keywords = profile.keywords.include_or

    # 키워드가 없으면 전체 조회
    keywords_to_search = or_keywords if or_keywords else [""]

    for bid_type in profile.bid_types:
        for keyword in keywords_to_search:
            # ── 사전규격 조회 ──
            try:
                prebid_notices = fetch_prebid_notices(
                    bid_type=bid_type,
                    keyword=keyword,
                    buffer_hours=settings.query_buffer_hours,
                    max_results=settings.max_results_per_page,
                )
                all_prebid_notices.extend(prebid_notices)
            except Exception as e:
                logger.error("사전규격 조회 실패 (%s/%s): %s", bid_type.display_name, keyword, e)

            # ── 입찰공고 조회 ──
            try:
                bid_notices = fetch_bid_notices(
                    bid_type=bid_type,
                    keyword=keyword,
                    buffer_hours=settings.query_buffer_hours,
                    max_results=settings.max_results_per_page,
                )
                all_bid_notices.extend(bid_notices)
            except Exception as e:
                logger.error("입찰공고 조회 실패 (%s/%s): %s", bid_type.display_name, keyword, e)

    # 중복 제거 (같은 공고번호가 여러 키워드에 의해 조회될 수 있음)
    seen_prebid = set()
    unique_prebid = []
    for n in all_prebid_notices:
        if n.unique_key not in seen_prebid:
            seen_prebid.add(n.unique_key)
            unique_prebid.append(n)

    seen_bid = set()
    unique_bid = []
    for n in all_bid_notices:
        if n.unique_key not in seen_bid:
            seen_bid.add(n.unique_key)
            unique_bid.append(n)

    logger.info("조회 결과: 사전규격 %d건, 입찰공고 %d건 (중복 제거 후)",
                len(unique_prebid), len(unique_bid))

    # ── 프로필 조건 필터링 ──
    filtered_prebid = filter_notices(unique_prebid, profile)
    filtered_bid = filter_notices(unique_bid, profile)

    logger.info("필터링 결과: 사전규격 %d건, 입찰공고 %d건",
                len(filtered_prebid), len(filtered_bid))

    # ── 중복 확인 (이미 알림 보낸 공고 제외) ──
    new_prebid = []
    for notice in filtered_prebid:
        if not is_notified(state, notice.unique_key, "prebid"):
            new_prebid.append(notice)

    new_bid = []
    for notice in filtered_bid:
        if not is_notified(state, notice.unique_key, "bid"):
            new_bid.append(notice)

    logger.info("신규 공고: 사전규격 %d건, 입찰공고 %d건", len(new_prebid), len(new_bid))

    # ── 알림 발송 ──
    sent_prebid = 0
    sent_bid = 0

    # 구독자 목록 로드 (prebid 모드)
    subscribers = load_subscribers(mode="prebid")

    # 기본 chat_id (TELEGRAM_CHAT_ID)
    default_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if default_chat_id:
        subscribers.add(default_chat_id)

    if not subscribers:
        logger.warning("구독자가 없습니다. 알림을 건너뜁니다.")
        return sent_prebid, sent_bid

    # 사전규격 알림 발송
    for notice in new_prebid:
        matched_kw = getattr(notice, "matched_keyword", "")
        msg = format_prebid_notice(notice, profile.name, matched_kw)

        if len(subscribers) == 1:
            # 단일 수신자: 간단 전송
            success = send_message(msg, chat_id=list(subscribers)[0])
        else:
            # 다중 수신자: 브로드캐스트
            result = broadcast_message(msg, subscribers)
            success = result.success_count > 0

        if success:
            mark_notified(state, notice.unique_key, profile.name, "prebid")
            sent_prebid += 1

    # 입찰공고 알림 발송
    for notice in new_bid:
        matched_kw = getattr(notice, "matched_keyword", "")
        msg = format_bid_notice(notice, profile.name, matched_kw)

        if len(subscribers) == 1:
            success = send_message(msg, chat_id=list(subscribers)[0])
        else:
            result = broadcast_message(msg, subscribers)
            success = result.success_count > 0

        if success:
            mark_notified(state, notice.unique_key, profile.name, "bid")
            sent_bid += 1

    # ── 결과 요약 발송 ──
    check_time = now_kst().strftime("%m/%d %H:%M")
    summary = format_summary(profile.name, sent_prebid, sent_bid, check_time)
    send_message(summary, chat_id=default_chat_id or list(subscribers)[0])

    return sent_prebid, sent_bid


def main():
    """메인 실행 함수"""
    logger.info("=" * 60)
    logger.info("나라장터 입찰 알림 서비스 시작")
    logger.info("=" * 60)

    # 필수 환경변수 확인
    required_vars = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        logger.error("필수 환경변수 누락: %s", ", ".join(missing))
        sys.exit(1)

    # API 키 확인
    has_prebid_key = bool(os.environ.get("G2B_PREBID_API_KEY"))
    has_bid_key = bool(os.environ.get("G2B_API_KEY"))

    if not has_prebid_key and not has_bid_key:
        logger.error("G2B_PREBID_API_KEY 또는 G2B_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    logger.info("API 키 상태: 사전규격=%s, 입찰공고=%s",
                "✅" if has_prebid_key else "❌",
                "✅" if has_bid_key else "❌")

    # 프로필 로드
    try:
        profiles, settings = load_profiles()
    except Exception as e:
        logger.error("프로필 로드 실패: %s", e)
        sys.exit(1)

    if not profiles:
        logger.warning("활성 프로필이 없습니다.")
        return

    logger.info("활성 프로필 %d개 로드", len(profiles))

    # 상태 로드
    state = load_state()

    # 오래된 기록 정리
    cleanup_old_records(state)

    # 프로필별 처리
    total_prebid = 0
    total_bid = 0

    for profile in profiles:
        try:
            p_count, b_count = process_profile(profile, settings, state)
            total_prebid += p_count
            total_bid += b_count
        except Exception as e:
            logger.error("프로필 '%s' 처리 중 오류: %s", profile.name, e, exc_info=True)

    # 마지막 체크 시각 업데이트 및 상태 저장
    update_last_check(state)
    save_state(state)

    logger.info("=" * 60)
    logger.info("실행 완료: 사전규격 %d건, 입찰공고 %d건 알림 발송", total_prebid, total_bid)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
