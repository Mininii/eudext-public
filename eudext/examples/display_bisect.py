"""25b 좁히기 맵: display 의 13번째 줄·TBL 쓰기 가운데 **어느 쓰기에서 게임이 멈추는지** 한 번에 좁힌다.

2026-09-18 인게임(통합 맵 `00_auto_all`): `display` 단계에서 게임이 EUD ERROR(0xFF9BE98B — "이 EUD 지도는 지원되지
않습니다")로 멈췄다. 마지막 프레임 2800(= 자체 점검이 끝난 프레임), 다음 프레임 2801 에서 1쪽 `dp.show_line13(...)` 의
**줄 버퍼 쓰기까지는 끝났고**(13번째 줄 스냅숏에 글이 남았다) 그 뒤 `dbg.mark` 부터 기록이 없다. 즉 멈춘 자리는
"13번째 줄에 긴 글 쓰기" 와 "그 뒤 TBL 쓰기" 사이다. 이 맵은 그 구간을 **한 단계에 한 가지만** 해 보고 단계마다 표식을
남긴다 — 게임이 멈추면 그대로 두고(또는 끄고) `RUN.bat --once` 를 돌려 `bx.stage`(마지막 시작)·`bx.ok`(마지막 성공)와
단계(suite) 상태를 읽으면 범인이 나온다.

단계 표 (한 단계 = 약 1초, 24프레임 간격 — 터보 기준):

    N   이름          하는 일                                                     건드리는 주소
    1   noop          아무 쓰기 없음 (브리지·터보만)                              (블록만)
    2   read13        13번째 줄 56바이트 **읽기**                                  0x641598 읽기
    3   readhead      빈 유닛 칸 머리 **읽기**                                     0x628438 읽기
    4   ccmu          `f_raise_CCMU(P1)` 만 — 줄 버퍼를 쓰지 않는다                0x628438 쓰기 + CreateUnit 실패
    5   line13_4      13번째 줄 4바이트 (상수 "A")                                 0x641598 +0..3
    6   line13_16     13번째 줄 16바이트 (상수)                                    +0..15
    7   line13_32     13번째 줄 32바이트 (상수 20 + 변수 자리 12 — 자체 점검 판)   +0..31
    8   line13_93     13번째 줄 93바이트 — **멈춘 통합 맵 1쪽과 같은 틀**          +0..95
    9   line13_212    13번째 줄 212바이트 (마지막 dword = +208, 줄 안)             +0..215
    10  line13_216    13번째 줄 216바이트 (마지막 **마스크** dword = +216)         +0..219 창(줄 밖 2바이트 보존)
    11  cp13_93       같은 93바이트를 **CP 방식**(f_repmovsd_epd)으로 13번째 줄에  0x641598 (eudplib 식 쓰기)
    12  line10_93     11번째 줄(k=10)에 같은 93바이트                              0x6413E4..
    13  line14_93     15번째 줄(k=14)에 같은 93바이트                              0x64174C..
    14  tbl_read      TBL 문자열 1 을 64바이트 **읽기**                            GetTBLAddr(1) 읽기
    15  tbl_const     `set_tbl(1, 상수)`                                           GetTBLAddr(1) 쓰기
    16  tbl_var       `set_tbl(1, 상수, 변수)` — E6-4 판(tail U+2009 + NUL)        GetTBLAddr(1) 쓰기
    17  tbl_raw       `set_tbl(1, 상수, eos=False, tail=False)` — E6-4b 판          GetTBLAddr(1) 쓰기
    18  done          끝 표식 (`bx.done`)                                          (블록만)

읽기(2·3·14)는 **쓰기와 나누기 위한** 단계다. 5~10 은 길이를, 11~13 은 "쓰는 방식·줄 번호"를 가른다:
- 8 에서 멈추고 11 은 지나가면 → 문제는 **상수 주소 `SetMemory` 로 줄 버퍼를 쓰는 방식**(eudext `show_line13`).
- 10 에서만 멈추면 → 줄 끝(+216 마스크 dword 가 0x641672~3 = 줄 밖 2바이트를 창에 넣는다)이 원인 → `LINE13_MAX` 를 줄인다.
- 4 에서 멈추면 → CreateUnit 실패 트릭(CCMU) 자체.
- 15~17 에서 멈추면 → TBL 쓰기(사용자 맵은 euddraft `CopyTBL`·theSeed eds 로 한다).

빌드: python eudext/tools/ingame_maps.py --out <폴더> bisect
"""

from eudplib import (
    EPD,
    Db,
    DisplayTextAll,
    DoActions,
    EUDEndIf,
    EUDIf,
    EUDVariable,
    P1,
    f_dwread,
    f_getuserplayerid,
    f_raise_CCMU,
    f_repmovsd_epd,
    f_setcurpl2cpcache,
    GetTBLAddr,
)

from eudext import dbg
from eudext import display as dp

LINE_BASE = 0x640B60
LINE_BYTES = 218
LINE13 = LINE_BASE + LINE_BYTES * 12  # 0x641598 — 오류(상태) 줄
LINE10 = LINE_BASE + LINE_BYTES * 10  # 0x6413E4 — 4의 배수
LINE14 = LINE_BASE + LINE_BYTES * 14  # 0x64174C — 4의 배수

FIRST = 12   # 첫 단계 프레임
EVERY = 24   # 단계 간격 (터보면 약 1초)

frame = EUDVariable()
v42 = EUDVariable()
head = EUDVariable()

# 멈춘 통합 맵 1쪽과 같은 틀(상수 23바이트 → 24 정렬 + 변수 자리 12 + 상수 57 = 93바이트, + NUL → 96 = 24 dword)
LONG_HEAD = "\x08[E6-3] \x0413번째 줄 \x1F"
LONG_TAIL = "\x04 — 오류 소리 없이 이 글이 보여야 합니다"

_long_db = Db(LONG_HEAD.encode("utf-8") + b"\r" * 13 + LONG_TAIL.encode("utf-8") + b"\0" * 3)
_tbl_buf = Db(72)

dbg.f_snapshot_text("bx.line13", LINE13, 56, every=0)
dbg.f_snapshot_text("bx.tbl", _tbl_buf, 16, every=0)


def _say(n, text):
    DoActions(DisplayTextAll("\x07[25b] 단계 %d %s" % (n, text)))


def s_noop():
    pass


def s_read13():
    dbg.f_capture("bx.line13")


def s_readhead():
    head << f_dwread(0x628438)
    dbg.f_mark("bx.head", head)


def s_ccmu():
    f_raise_CCMU(P1)


def s_line13_4():
    dp.f_show_line13(P1, "A")


def s_line13_16():
    dp.f_show_line13(P1, "[25b] 16 bytes")


def s_line13_32():
    dp.f_show_line13(P1, "[E6-3] 13번째 줄 ", v42)


def s_line13_93():
    dp.f_show_line13(P1, LONG_HEAD, v42, LONG_TAIL)


def s_line13_212():
    dp.f_show_line13(P1, "2" * 212)


def s_line13_216():
    dp.f_show_line13(P1, "6" * 216)


def s_cp13_93():
    f_repmovsd_epd(EPD(LINE13), EPD(_long_db), 24)


def s_line10_93():
    f_repmovsd_epd(EPD(LINE10), EPD(_long_db), 24)


def s_line14_93():
    f_repmovsd_epd(EPD(LINE14), EPD(_long_db), 24)


def s_tbl_read():
    f_repmovsd_epd(EPD(_tbl_buf), EPD(GetTBLAddr(1)), 16)
    dbg.f_capture("bx.tbl")


def s_tbl_const():
    dp.f_set_tbl(1, "[25b] TBL")


def s_tbl_var():
    dp.f_set_tbl(1, "\x04[E6-4] 마린 ", v42)


def s_tbl_raw():
    dp.f_set_tbl(1, "[E6-4b]", eos=False, tail=False)


def s_done():
    dbg.f_mark("bx.done", 1)


STAGES = [
    (1, "noop", "쓰기 없음", s_noop),
    (2, "read13", "13번째 줄 읽기", s_read13),
    (3, "readhead", "0x628438 읽기", s_readhead),
    (4, "ccmu", "CCMU 만", s_ccmu),
    (5, "line13_4", "13번째 줄 4바이트", s_line13_4),
    (6, "line13_16", "13번째 줄 16바이트", s_line13_16),
    (7, "line13_32", "13번째 줄 32바이트(변수)", s_line13_32),
    (8, "line13_93", "13번째 줄 93바이트(멈춘 틀)", s_line13_93),
    (9, "line13_212", "13번째 줄 212바이트", s_line13_212),
    (10, "line13_216", "13번째 줄 216바이트(줄 끝 마스크)", s_line13_216),
    (11, "cp13_93", "13번째 줄 93바이트 CP 방식", s_cp13_93),
    (12, "line10_93", "11번째 줄 93바이트", s_line10_93),
    (13, "line14_93", "15번째 줄 93바이트", s_line14_93),
    (14, "tbl_read", "TBL 읽기", s_tbl_read),
    (15, "tbl_const", "TBL 상수 쓰기", s_tbl_const),
    (16, "tbl_var", "TBL 변수+NUL 쓰기", s_tbl_var),
    (17, "tbl_raw", "TBL NUL·tail 없이", s_tbl_raw),
    (18, "done", "끝", s_done),
]

STAGE_NAMES = [name for _n, name, _t, _f in STAGES]
LAST_FRAME = FIRST + EVERY * (len(STAGES) - 1) + 4


def onPluginStart():
    DoActions([v42.SetNumber(42), frame.SetNumber(0)])


def afterTriggerExec():
    DoActions(frame.AddNumber(1))   # `frame += 1` 은 파이썬이 지역 변수로 보아 UnboundLocalError
    if EUDIf()(frame == 1):
        f_setcurpl2cpcache()
        dbg.f_mark("bx.local", f_getuserplayerid())
        DoActions(DisplayTextAll("\x07[25b] display 좁히기 맵 — 단계 18개를 1초에 하나씩 합니다. "
                                 "게임이 멈추면 그 상태에서 RUN.bat --once 를 돌려 주세요"))
    EUDEndIf()
    for n, name, text, fn in STAGES:
        f0 = FIRST + EVERY * (n - 1)
        if EUDIf()(frame == f0):
            dbg.f_suite_begin(name, phase=n)
            dbg.f_mark("bx.stage", n)
            _say(n, text)
        EUDEndIf()
        if EUDIf()(frame == f0 + 1):
            fn()
            dbg.f_mark("bx.ok", n)
        EUDEndIf()
        if EUDIf()(frame == f0 + 3):
            dbg.f_suite_end(name)
        EUDEndIf()
    if EUDIf()(frame == LAST_FRAME):
        DoActions(DisplayTextAll("\x07[25b] 끝 — 18단계 모두 지났습니다. RUN.bat 결과를 알려 주세요"))
    EUDEndIf()
