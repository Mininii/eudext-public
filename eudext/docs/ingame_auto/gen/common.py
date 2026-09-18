"""분류 항목 생성 도우미 (dbg_plan 전용, 저장소와 무관)."""

CATS = ["AUTO", "AUTO_ASSIST", "VISUAL", "MULTI", "CRASH_RISK", "EXTERNAL"]


def E(id, sec, mp, cat, extra=(), read=(), expect="", done="", instr="", risk="", notes="",
      req=False, bundle=""):
    assert cat in CATS, (id, cat)
    for x in extra:
        assert x in CATS, (id, x)
    return dict(id=id, doc_section=sec, map=mp, category=cat, extra=list(extra), read=list(read),
                expect=expect, done_marker=done, instrument=instr, risk=risk, notes=notes,
                required=req, bundle=bundle)


# 자주 쓰는 표현
PEEK = "peek"      # 1.16.1 미러 구역(EUD 0x57F0E0~0x59F0E0) 직접 읽기 — 맵 계측 불필요, dbg 블록(또는 다른 시그니처)만 있으면 됨
W = "watch"        # eudext.dbg 감시 슬롯 (맵이 매 프레임 복사)
R = "result"       # eudext.dbg 결과 카운터 (통과 수/전체 수/틀린 번호)
CHAT = "chat"      # 채팅 버퍼 0x640B58 스냅숏 (11줄 x 218B, 맵이 복사)
HDR = "hdr"        # 블록 헤더 (seq, 게임 프레임 0x57F23C 사본, 로컬 플레이어)
WALL = "wall"      # 리더 벽시계 (seq 증가율 = 프레임/초, 멈춤 감지)
WATCHDOG = "hdr:seq 증가 + wall (2초 이상 seq 정지 = 멈춤, 블록 사라짐 = 게임 종료/튕김)"
