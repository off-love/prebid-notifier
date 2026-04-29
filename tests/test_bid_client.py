from src.api import bid_client
from src.core.models import BidType


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_bid_notices_uses_official_endpoint_and_query_range(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _Response(
            {
                "response": {
                    "header": {"resultCode": "00"},
                    "body": {
                        "totalCount": 1,
                        "items": [
                            {
                                "bidNtceNo": "R26BK0001",
                                "bidNtceOrd": "000",
                                "bidNtceNm": "지적측량 입찰공고",
                                "ntceInsttNm": "서울특별시",
                                "dmndInsttNm": "서울특별시",
                                "bidNtceDt": "2026-04-30 10:00:00",
                                "bidClseDt": "2026-05-07 18:00:00",
                                "presmptPrce": "100000000",
                                "bidNtceDtlUrl": "https://example.com/bid",
                                "ntceDivNm": "일반",
                            }
                        ],
                    },
                }
            }
        )

    monkeypatch.setenv("G2B_API_KEY", "api-key")
    monkeypatch.setattr(bid_client.requests, "get", fake_get)
    monkeypatch.setattr(bid_client.time, "sleep", lambda seconds: None)

    notices = bid_client.fetch_bid_notices(
        BidType.SERVICE,
        keyword="측량",
        inqry_bgn_dt="202604301000",
        inqry_end_dt="202604301100",
    )

    assert captured["url"].endswith("/getBidPblancListInfoServc")
    assert captured["params"]["inqryBgnDt"] == "202604301000"
    assert captured["params"]["inqryEndDt"] == "202604301100"
    assert captured["params"]["bidNtceNm"] == "측량"
    assert notices[0].unique_key == "R26BK0001-000"
    assert notices[0].dmin_instt_nm == "서울특별시"
