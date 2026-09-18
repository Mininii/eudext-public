"""auto_all 공용 — 디버그 브리지 설정, 진행 표식, CP·정리·채팅 줄 도우미 (classification.md 5.3·5.4).

**모든 aa_ 모듈보다 먼저 import 한다**(auto_all.eps 첫 줄). 모듈 본문에서 `dbg.setup` 을 부르므로 뒤에 불러오는
단계 모듈의 모듈 전역 `dbg.snapshot`·`dbg.watch` 가 이 블록에 들어간다(원래 확인 맵은 이 모듈을 부르지 않으므로
dbg 가 꺼져 있다 — 트리거 0).

epScript 에서 부를 함수는 `f_` 이름이다(`aa.cp_ok()` → `aa.f_cp_ok()`).
"""

from eudplib import (
    EPD,
    Command,
    Db,
    EUDBreak,
    EUDEndIf,
    EUDEndWhile,
    EUDFunc,
    EUDIf,
    EUDVariable,
    EUDWhile,
    Exactly,
    Forward,
    Memory,
    RawTrigger,
    VProc,
    f_bread,
    f_dwread,
    f_dwread_epd,
    f_printAll,
)

from eudext import _compat, dbg

MAP_NAME = "00_auto_all"
WATCH_SLOTS = 1400
PROBES = 1024
bridge = dbg.setup(map_name=MAP_NAME, watch_slots=WATCH_SLOTS, probes=PROBES)

# 단계 번호·이름 (auto_all.eps 와 명세 생성기 tools/make_ingame_specs.py 가 같이 쓴다)
PHASES = [
    (1, "units"), (2, "pool"), (3, "switch"), (4, "s8"), (5, "datpatch"), (6, "i64"), (7, "i64_ops"), (8, "i128"),
    (9, "numfmt"), (10, "cmp_cell"), (11, "mathx"), (12, "players"), (13, "plot"), (14, "spawn"), (15, "bullet"),
    (16, "display"), (17, "chat"), (18, "final"), (19, "assist"),
]

quiet = EUDVariable(0)  # 1 이면 진행기 안내 줄을 내지 않는다 (chat 창 — D17-4·5 판정이 흔들리지 않게)
cpbad = EUDVariable(0)  # 단계 끝에서 CP 가 eudplib CP 캐시와 다르면 +1
dbg.watch("aa.cpbad", cpbad)

CHAT_NEXT = 0x640B58
CHAT_BUF = 0x640B60
LINE_BYTES = 218
BLANK = 0x0D0D0D0D  # textfx 빈칸 셀


def f_say(fmt, *args):
    """진행 안내 줄(모두에게). quiet 이면 내지 않는다. (파이썬 함수 — 호출 자리에 펼쳐진다)"""
    if EUDIf()(quiet == 0):
        f_printAll(fmt, *args)
    EUDEndIf()


@EUDFunc
def _cp_ok():
    ok = EUDVariable()
    t = Forward()
    cache = _compat.cpcache_var()
    VProc(cache, [ok.SetNumber(0), cache.QueueAssignTo(EPD(t) + 4)])
    t << RawTrigger(conditions=Memory(0x6509B0, Exactly, 0), actions=ok.SetNumber(1))
    return ok


def f_cp_ok():
    """실제 CP(0x6509B0) 가 eudplib CP 캐시와 같으면 1 (DESIGN 3.6). 비용: 공유 본문 3 / 호출 1."""
    return _cp_ok()


def f_check_cp():
    """단계 끝: CP 가 캐시와 다르면 cpbad += 1."""
    if EUDIf()(_cp_ok() == 0):
        cpbad.__iadd__(1)
    EUDEndIf()


def f_count_is(player, unit, n):
    """유닛 수 조건 `Command(player, Exactly, n, unit)` (정리 확인용)."""
    return Command(player, Exactly, n, unit)


def f_line_ptr(slot):
    """채팅 줄 slot 의 원문 주소 (0x640B60 + 218·slot)."""
    return CHAT_BUF + slot * LINE_BYTES


def f_next_slot():
    """다음에 쓸 채팅 slot (0x640B58, 로컬 값)."""
    return f_dwread(CHAT_NEXT)


@EUDFunc
def _front(slot):
    """채팅 줄 slot 에서 셀 1..52 가운데 빈칸이 아닌 가장 큰 셀 번호(없으면 0). 홀수 slot 은 +2 바이트 정렬."""
    p = EUDVariable()
    p << CHAT_BUF
    p += slot * LINE_BYTES
    if EUDIf()(slot % 2 == 1):
        p += 2
    EUDEndIf()
    epd = EUDVariable()
    epd << EPD(p)
    i = EUDVariable()
    i << 52
    r = EUDVariable()
    r << 0
    if EUDWhile()(i >= 1):
        c = EUDVariable()
        c << f_dwread_epd(epd + i)
        if EUDIf()(c != BLANK):
            r << i
            EUDBreak()
        EUDEndIf()
        i -= 1
    EUDEndWhile()
    return r


def f_front(slot):
    """타자기가 드러낸 앞끝 셀 번호 (D17 판정용, 로컬 읽기). 비용: 공유 본문 / 실행 셀당 약 40."""
    return _front(slot)


@EUDFunc
def _name_eq(a, b, n):
    """주소 a, b 의 글을 보이는 글자만(0x01~0x1F 건너뜀) 앞에서 n 바이트까지 비교 — 같으면 1. NUL 을 만나면 끝."""
    r = EUDVariable()
    r << 1
    k = EUDVariable()
    k << 0
    ca = EUDVariable()
    cb = EUDVariable()
    if EUDWhile()(k < n):
        ca << f_bread(a)
        if EUDWhile()([ca >= 1, ca <= 0x1F]):
            a += 1
            ca << f_bread(a)
        EUDEndWhile()
        cb << f_bread(b)
        if EUDWhile()([cb >= 1, cb <= 0x1F]):
            b += 1
            cb << f_bread(b)
        EUDEndWhile()
        if EUDIf()(ca != cb):
            r << 0
            EUDBreak()
        EUDEndIf()
        if EUDIf()(ca == 0):
            EUDBreak()
        EUDEndIf()
        a += 1
        b += 1
        k += 1
    EUDEndWhile()
    return r


def f_name_eq(a, b, n=16):
    """이름 글 비교(색·0x0D 건너뜀, n 바이트까지) → 1/0. a·b 는 주소(상수·변수)."""
    return _name_eq(a, b, n)


def text_db(size):
    """글 버퍼(0 으로 찬 Db)."""
    return Db(size)
