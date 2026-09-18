"""chat — 채팅 줄 주소·판정과 타자기 효과 (DESIGN 4.8, 정본 명세 docs/spec/S6_chat.md 1절·4.2).

SC 채팅 버퍼 사실(R4a E.1): 줄 11개(slot 0~10), 줄 k 원문 = `0x640B60 + 218·k`(218바이트, NUL 로 끝남),
다음에 쓸 slot = `[0x640B58]`, 줄이 꺼지면 첫 바이트가 0. 218 = 4·54 + 2 라서 **홀수 slot 은 원문 +2 바이트부터
dword 정렬**이다(셀 54개 = 글자 53 + NUL). 셀 배치는 `eudext.textfx`.

    from eudext import chat, players
    chat.f_line_ptr(3), chat.f_line_epd(3)      # 원문 주소, 셀 시작 EPD (홀수 slot 은 +2 바이트 정렬)
    with local.only():
        if EUDIf()(chat.line_active(3)): …      # 첫 바이트 ≠ 0 (로컬 조건)
        s = chat.f_slot_of_row(0)               # 화면 맨 위 줄의 slot (CtrigAsm CD__GetLine)

    tw = chat.Typewriter()                      # "\\r\\r!H" 로 시작하는 줄을 한 글자씩 드러낸다 (원본 HTextEff + CDPrint)
    DoActions(DisplayText(tw.mark("\\x13\\x04가사 한 줄")))
    tw.tick()                                   # 매 프레임 한 번 (어디서 불러도 된다 — 안에서 로컬 분기)

epScript:

    import eudext.chat as chat;
    const tw = chat.Typewriter(speed=1, sound="sound\\\\glue\\\\bnetclick.wav");
    function afterTriggerExec() { tw.tick(); }

## 타자기 (`Typewriter`) 동작 — S6 1.2 를 옮김, 모두 로컬

이 PC 가 `targets` 에 있고 `enable` 이 참인 프레임마다 slot 0..10 을 차례로:
1. 셀 0 이 표식(U+200B)이고 그 줄이 진행 중이면 → 줄이 떠 있을 때(첫 바이트 ≠ 0) 드러내기:
   아직 안 쓴 셀을 보관소에서 줄로 옮기고(셀 1..k = 보관 셀 0..k−1), 차례가 되면(`every`) k 를 `speed` 만큼 늘린다(최대 52).
   **원본처럼 쓰고 나서 늘린다** — 늘린 셀은 다음 프레임에 보인다. `sound` 가 있으면 늘리기 전에 셀 k 가 빈칸·공백이 아닐 때 소리.
2. 아니면 진행 상태를 지우고, 원문 앞 바이트가 `marker` 와 같으면(바이트 비교 — 홀수 slot 도 맞다) 변환한다:
   원문을 `textfx` 규칙(`rule`)으로 셀 최대 52개로 바꿔 보관(나머지 빈칸), 앞 `erase` 셀을 빈칸으로(`!H` 지우기),
   줄 = 셀 0 표식 + 빈칸 52 + 셀 53 NUL. k = 0. 변환한 프레임에는 드러내지 않는다.
3. `nul_cell` 이면 11줄 모두 셀 53 을 0 으로 쓴다(원본과 같은 부수효과 — 짝수 줄 212, 홀수 줄 214 바이트 뒤가 잘린다).

원본과 다른 점:
- 스테이징 셀·마스크(CDPrint)가 없다. 이 PC 에서만 돌므로 채팅 버퍼에 **직접** 쓴다.
- 원본은 드러내는 줄의 셀 1..52 를 **매 프레임 다시** 썼다. eudext 는 **새로 드러낼 셀만** 쓴다(보관소가 트리거가 아니라
  `Db` 라서 셀 하나 옮기는 데 약 40 트리거) — 다른 코드가 그 줄의 셀을 고치면 원본은 되살리고 eudext 는 두지 않는다.
- 다 드러낸 줄(k = 52)은 더 보지 않는다(원본은 계속 같은 값을 썼다 — 화면은 같다).
- U+2008 표식 경로·이름 줄(HCheck 4~6)은 넣지 않았다(도달 0 / 실험 코드, S6 1.2·1.4).
- 원본 HVA3/EffCV/EffCV2(공유 트리거 메모리)와 달리 상태는 eudext 전용 변수(로컬 오염 허용 — 공유 로직이 읽지 않는다).
- **한 맵에 Typewriter 는 하나만** 돌린다. 둘이면 서로의 표식 줄을 자기 줄로 볼 수 있다(원본도 블록 하나).

출처: 원본 블록 MSF_Respect_V/GunData.lua:2879~2936(5맵 복붙, S6 1.1), UERE MSF_UE_RE/CallTriggers.lua:942~1028(속도·소리),
CtrigAsm v5.5.lua `CDPrint`(52633~53039), `TTDisplay`(49745), `f_ChatOffset`(49579), `CD__GetLine`(53041),
eudplib 0.81 `string/cpprint.py`(`f_getnextchatdst` 의 `ceil(slot·54.5)`, `f_gettextptr`), `string/pname.py:196`(11줄 순회 선례).
DPS_Enhance eudplib-port(a7aad90)에는 채팅 효과 코드가 없다.
"""

import functools

from eudplib import (
    EPD,
    AtLeast,
    CurrentPlayer,
    Db,
    DeathsX,
    EUDElse,
    EUDEndIf,
    EUDFunc,
    EUDIf,
    EUDJump,
    EUDLightBool,
    EUDLightVariable,
    EUDVariable,
    EUDWhile,
    EUDEndWhile,
    Exactly,
    Forward,
    MemoryX,
    NextTrigger,
    PlayWAVAll,
    PopTriggerScope,
    PushTriggerScope,
    RawTrigger,
    SeqCompute,
    SetDeaths,
    SetMemory,
    SetNextPtr,
    SetTo,
    Subtract,
    Add,
    VProc,
    f_dwread_epd,
    f_dwwrite_epd,
    f_setcurpl2cpcache,
)

from eudext import _compat, cmp, local, players
from eudext import textfx as tfx
from eudext.errors import EudextError, check_choice, fail

__all__ = [
    "ARCHIVE_CELLS",
    "CELLS_PER_LINE",
    "CHAT_BUF",
    "CHAT_EPD",
    "DEFAULT_MARKER",
    "LINES",
    "LINE_BYTES",
    "NEXT_LINE_ADDR",
    "Typewriter",
    "f_line_active",
    "f_line_epd",
    "f_line_ptr",
    "f_slot_of_row",
    "line_active",
    "line_cell_addr",
    "line_epd",
    "line_ptr",
    "slot_of_row",
]

M32 = 0xFFFFFFFF
EPD0 = 0x58A364
CP_ADDR = 0x6509B0
CP_EPD = 203155

CHAT_BUF = 0x640B60
"""채팅 줄 0 원문 주소. 줄 k = CHAT_BUF + 218·k (R4a E.1)."""
CHAT_EPD = (CHAT_BUF - EPD0) // 4
NEXT_LINE_ADDR = 0x640B58
"""다음에 쓸 slot (로컬). 화면 맨 위 줄의 slot 이기도 하다."""
LINE_BYTES = 218
LINES = 11
CELLS_PER_LINE = 54
"""줄 하나의 셀 수 = 글자 53 + NUL (GB 7140)."""
ARCHIVE_CELLS = 52
"""타자기가 한 줄에서 드러내는 최대 셀 수 (셀 1..52)."""
DEFAULT_MARKER = b"\r\r!H"
"""원본 채팅 효과 블록의 표식 (`"\x0D\x0D!H"`). `Typewriter` 기본값."""


def _slot_const(fname, slot, hi=LINES - 1):
    if isinstance(slot, bool) or not isinstance(slot, int):
        fail("%s: slot 은 정수 상수 또는 EUDVariable 이어야 합니다 (%r)", fname, slot)
    if not 0 <= slot <= hi:
        fail("%s: slot 범위 밖 %d (허용 0 ~ %d)", fname, slot, hi)
    return slot


def _ceil545(s):
    return (109 * s + 1) // 2


def line_ptr(slot):
    """slot 의 원문 주소 `0x640B60 + 218·slot` — 컴파일 시점 (`f_line_ptr` 의 상수판).

    인자: slot(상수 0~10)
    반환: int
    비용: 트리거 0
    CP: 해당 없음
    로컬: 해당 없음 (주소 계산만)
    epScript: `chat.line_ptr(3)` 은 `f_line_ptr` 로 번역된다(상수면 같은 값)
    출처: CtrigAsm `f_ChatOffset`(v5.5.lua:49579), R4a E.1
    """
    return CHAT_BUF + LINE_BYTES * _slot_const("line_ptr", slot)


def line_epd(slot):
    """slot 의 셀 시작 EPD `EPD(0x640B60) + ceil(slot·54.5)` — 컴파일 시점 (`f_line_epd` 의 상수판).

    인자: slot(상수 0~10)
    반환: int
    비용: 트리거 0
    CP: 해당 없음
    로컬: 해당 없음 (주소 계산만)
    epScript: `chat.line_epd(3)` 은 `f_line_epd` 로 번역된다(상수면 같은 값)
    출처: eudplib 0.81 `string/cpprint.py:101` f_getnextchatdst
    """
    return CHAT_EPD + _ceil545(_slot_const("line_epd", slot))


def line_cell_addr(slot, i):
    """slot 의 셀 i(0~53) 주소 — 컴파일 시점.

    인자: slot(0~10), i(0~53)
    반환: int
    비용: 트리거 0
    CP: 해당 없음
    로컬: 해당 없음 (주소 계산만)
    epScript: 쓰지 않는다
    출처: S6 4.2, R4a E.1
    """
    if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < CELLS_PER_LINE:
        fail("line_cell_addr: 셀 번호 범위 밖 %r (허용 0 ~ 53)", i)
    return EPD0 + 4 * (line_epd(slot) + i)


@functools.cache
def _line_ptr_func():
    @EUDFunc
    def line_ptr_var(slot):
        ret = EUDVariable()
        ret << CHAT_BUF
        for i in range(3, -1, -1):
            RawTrigger(conditions=slot.AtLeastX(1, 1 << i), actions=ret.AddNumber(LINE_BYTES << i))
        return ret

    return line_ptr_var


@functools.cache
def _line_epd_func():
    @EUDFunc
    def line_epd_var(slot):
        ret = EUDVariable()
        ret << CHAT_EPD
        for i in range(3, -1, -1):
            RawTrigger(conditions=slot.AtLeastX(1, 1 << i), actions=ret.AddNumber(_ceil545(1 << i)))
        return ret

    return line_epd_var


def f_line_ptr(slot):
    """slot 의 원문 시작 주소 `0x640B60 + 218·slot`.

    인자: slot(상수 0~10 또는 EUDVariable — 변수는 0~15 까지 계산)
    반환: 상수 slot → int, 변수 → 새 EUDVariable
    비용: 상수 = 트리거 0. 변수 = 본문 6(1벌) / 호출 자리 2 / 실행 약 10 (docs/COSTS.md "chat (WP17)")
    CP: 바꾸지 않음
    로컬: 공유 안전 (주소 계산만. 그 주소의 내용은 로컬 값)
    epScript: `const p = chat.line_ptr(k);` (→ `f_line_ptr`)
    출처: CtrigAsm `f_ChatOffset`(v5.5.lua:49579), R4a E.1
    """
    if _compat.is_var(slot):
        return _line_ptr_func()(slot)
    return line_ptr(slot)


def f_line_epd(slot):
    """slot 의 셀 시작 EPD `EPD(0x640B60) + ceil(slot·54.5)` (홀수 slot 은 원문 +2 바이트).

    인자: slot(상수 0~10 또는 EUDVariable — 변수는 0~15 까지 계산)
    반환: 상수 slot → int, 변수 → 새 EUDVariable
    비용: 상수 = 트리거 0. 변수 = 본문 6 / 호출 자리 2 / 실행 약 10
    CP: 바꾸지 않음
    로컬: 공유 안전 (주소 계산만)
    epScript: `const e = chat.line_epd(k);` (→ `f_line_epd`)
    출처: eudplib 0.81 `string/cpprint.py:101` f_getnextchatdst(같은 식), CtrigAsm CDPrint 0x640B62 정렬(GB 7126)
    """
    if _compat.is_var(slot):
        return _line_epd_func()(slot)
    return line_epd(slot)


def _active_cond(slot):
    p = line_ptr(slot)
    if slot % 2 == 0:
        return MemoryX(p, AtLeast, 1, 0xFF)
    return MemoryX(p - 2, AtLeast, 1, 0xFF0000)


@functools.cache
def _active_func():
    @EUDFunc
    def line_active_var(slot):
        ret = EUDVariable()
        ret << 0
        for k in range(LINES):
            RawTrigger(conditions=[slot.Exactly(k), _active_cond(k)], actions=ret.SetNumber(1))
        return ret

    return line_active_var


def line_active(slot):
    """slot 의 줄이 떠 있는가(원문 첫 바이트 ≠ 0) — **로컬 조건**.

    짝수 slot 은 원문 dword 의 가장 낮은 바이트, 홀수 slot 은 원문 −2 주소 dword 의 셋째 바이트(마스크 0x00FF0000)를 본다.
    인자: slot(상수 0~10 또는 EUDVariable)
    반환: `local.LocalCondition` (상수 = 조건 1개, 트리거 0 / 변수 = 판정 함수 호출 뒤 1비트 조건). 매 호출 새 객체
    비용: 상수 = 0. 변수 = 본문 12 / 호출 자리 2 / 실행 약 14
    CP: 바꾸지 않음
    로컬: **로컬 전용** — `local.only()`/`begin()`/`allow()` 밖에서 트리거에 놓이면 빌드 경고
    epScript: `local.begin(); if (chat.line_active(3)) { … } local.end();` (→ `f_line_active`)
    출처: CtrigAsm `TTDisplay(L,"On")`(v5.5.lua:49745, 본문 90258~90279), R4a E.1
    """
    if _compat.is_var(slot):
        v = _active_func()(slot)
        return local.LocalCondition.wrap(v.AtLeast(1))
    _slot_const("line_active", slot)
    return local.LocalCondition.wrap(_active_cond(slot))


f_line_active = line_active


@functools.cache
def _slot_of_row_func():
    @EUDFunc
    def slot_of_row_var(row):
        t = EUDVariable()
        t << row
        for i in range(3, -1, -1):
            RawTrigger(conditions=MemoryX(NEXT_LINE_ADDR, AtLeast, 1, 1 << i), actions=t.AddNumber(1 << i))
        RawTrigger(conditions=t.AtLeast(2 * LINES), actions=t.SubtractNumber(2 * LINES))
        RawTrigger(conditions=t.AtLeast(LINES), actions=t.SubtractNumber(LINES))
        return t

    return slot_of_row_var


def f_slot_of_row(row):
    """화면 위치 row(0 = 맨 위 = 가장 오래된 줄, 10 = 맨 아래)의 slot `(row + [0x640B58]) % 11`.

    인자: row(상수 0~10 또는 EUDVariable 0~21)
    반환: 새 EUDVariable (로컬 값)
    비용: 본문 9(1벌) / 호출 자리 2 / 실행 약 13
    CP: 바꾸지 않음
    로컬: **로컬 전용** — 0x640B58 을 읽는다. 구역 밖이면 빌드 경고
    epScript: `local.begin(); const s = chat.slot_of_row(0); local.end();` (→ `f_slot_of_row`)
    출처: CtrigAsm `CD__GetLine`(v5.5.lua:53041), eudplib `f_gettextptr`(string/cpprint.py:89 — 4비트 읽기)
    """
    if not _compat.is_var(row):
        _slot_const("slot_of_row", row)
    tfx.warn_outside_local("chat.slot_of_row")
    return _slot_of_row_func()(row)


slot_of_row = f_slot_of_row


# =============================================================================================
# 타자기
# =============================================================================================


def _flat(items):
    if items is None:
        return []
    if isinstance(items, (list, tuple)):
        out = []
        for x in items:
            out.extend(_flat(x))
        return out
    return [items]


def _check_marker(marker):
    if isinstance(marker, str):
        marker = marker.encode("utf-8")
    if not isinstance(marker, (bytes, bytearray)):
        fail("Typewriter: marker 는 bytes 또는 str 이어야 합니다 (%r)", marker)
    marker = bytes(marker)
    if not 3 <= len(marker) <= 16:
        fail("Typewriter: marker 길이는 3~16 바이트여야 합니다 (%r)", marker)
    if 0 in marker:
        fail("Typewriter: marker 에 NUL 이 들어 있습니다 (%r)", marker)

    def looks_like_mark(m):
        # 변환한 줄의 셀 0(0D E2 80 8x)과 겹칠 수 있는가 → 매 프레임 다시 변환한다
        pat = (lambda b: b == 0x0D, lambda b: b == 0xE2, lambda b: b == 0x80, lambda b: b & 0xF0 == 0x80)
        return all(pat[i](m[i]) for i in range(min(4, len(m))))

    if looks_like_mark(marker[:4]) or looks_like_mark(marker[2:6]):
        fail("Typewriter: marker %r 는 변환한 줄의 표식 셀(0D E2 80 8B)과 겹쳐 같은 줄을 매 프레임 다시 변환합니다", marker)
    return marker


def _raw_marker_conds(slot, marker):
    p = line_ptr(slot)
    groups = {}
    for i, b in enumerate(marker):
        a = p + i
        base = a & ~3
        sh = 8 * (a & 3)
        v, m = groups.get(base, (0, 0))
        groups[base] = (v | (b << sh), m | (0xFF << sh))
    return [MemoryX(base, Exactly, v, m) for base, (v, m) in sorted(groups.items())]


def _mark_cell_cond(slot):
    return MemoryX(line_cell_addr(slot, 0), Exactly, tfx.MARK_U200B & tfx.MARK_MASK, tfx.MARK_MASK)


class Typewriter:
    """채팅 효과 블록(원본 `HTextEff` + `CDPrint`) 대체 — 표식으로 시작하는 채팅 줄을 한 글자씩 드러낸다.

    인자:
      marker(원문 표식 바이트, 기본 b"\\r\\r!H" — 3~16 바이트, NUL 없음, 변환한 줄의 표식 셀과 겹치면 오류),
      targets(효과를 낼 PC — `players` 대상, 기본 `players.Everyone` = 사람 + 관전자),
      speed(차례마다 드러낼 셀 수 — 상수 1~52 또는 EUDVariable),
      erase(변환 때 지울 앞 셀 수 0~52. 기본 None = 표식만 스캔한 셀 수 — 기본 표식·"ctrig" 이면 2("!H", 원본과 같음),
            "eudplib" 이면 4(0x0D 도 셀이 된다, S6 1.7)),
      sound(드러낸 셀이 빈칸·공백이 아니면 낼 WAV 이름, 기본 None — UERE),
      nul_cell(매 프레임 11줄의 셀 53 = 0, 기본 True — 원본 부수효과. False 여도 변환한 줄의 셀 53 은 한 번 쓴다),
      rule(`textfx` 스캐너 규칙, 기본 "ctrig"),
      enable(None | 조건 | EUDVariable/EUDLightVariable/EUDLightBool | 조건을 돌려주는 함수 — 참일 때만 동작.
             조건 객체는 `tick()` 을 한 번만 부를 때 쓴다. 여러 번이면 함수로 넘긴다),
      every(None | 상수 ≥ 1 | EUDVariable — N 프레임마다 한 번 드러낸다. UERE `TalkTimer` 와 같은 순서:
            매 프레임 1 줄이고 0 이면 드러낸 뒤 N 으로)
    반환: -
    비용: 본문 77(1벌, 이 인스턴스) + `textfx` 스캐너 94(규칙마다 1벌, f_scan_cells 와 공유) + 빈칸 루프 7(모든 타자기 공유)
          + 보관소 Db 2,288B + 칸 변수 22개 / `tick()` 호출 자리 3 /
          실행: 빈 프레임 39(11줄 × 판정 3 + 6), 드러내는 줄마다 +65(셀 하나 옮기기), 변환 프레임 약 980(표식 줄 16글자 —
          원문 바이트당 약 16 + 글자당 약 10). 페이로드: 첫 타자기 +67KB(스캐너 포함, scx +6.5KB), 둘째부터 +38KB(scx +3.6KB).
          측정 2026-09-17, docs/COSTS.md "chat (WP17)"
    CP: 바꾸지 않음 (안에서 잠깐 옮겨 쓰고 캐시 값으로 되돌린다)
    로컬: **로컬 전용** 효과. `tick()` 이 안에서 로컬 분기를 하므로 공유 흐름 어디서 불러도 된다.
          상태 변수·보관소는 이 PC 에서만 바뀐다 — 공유 로직이 읽지 않는다
    epScript: `const tw = chat.Typewriter(); … tw.tick();` / 문구 `DisplayTextAll(tw.mark("…"))`
    출처: MSF_Respect_V/GunData.lua:2879~2936, MSF_UE_RE/CallTriggers.lua:942~1028, CtrigAsm `CDPrint`, S6 4.2
    """

    def __init__(self, marker=DEFAULT_MARKER, targets=None, speed=1, erase=None, sound=None, nul_cell=True, rule="ctrig",
                 enable=None, every=None):
        self.marker = _check_marker(marker)
        self.targets = players.Everyone if targets is None else targets
        if not _compat.is_var(speed):
            if isinstance(speed, bool) or not isinstance(speed, int) or not 1 <= speed <= ARCHIVE_CELLS:
                fail("Typewriter: speed 는 1~52 정수 또는 EUDVariable 이어야 합니다 (%r)", speed)
        self.speed = speed
        self.rule = check_choice("Typewriter: rule", rule, tfx.RULES)
        if erase is None:
            # 표식만 스캔한 셀 수 — 기본 표식·ctrig 규칙이면 2("!H", 원본과 같음), eudplib 규칙이면 4
            erase = len(tfx.scan_const(self.marker, ARCHIVE_CELLS, self.rule).cells)
        if isinstance(erase, bool) or not isinstance(erase, int) or not 0 <= erase <= ARCHIVE_CELLS:
            fail("Typewriter: erase 는 0~52 정수 또는 None 이어야 합니다 (%r)", erase)
        self.erase = erase
        if sound is not None and not isinstance(sound, (str, bytes)):
            fail("Typewriter: sound 는 WAV 이름(str) 또는 None 이어야 합니다 (%r)", sound)
        self.sound = sound
        self.nul_cell = bool(nul_cell)
        if every is not None and not _compat.is_var(every):
            if isinstance(every, bool) or not isinstance(every, int) or every < 1:
                fail("Typewriter: every 는 1 이상 정수·EUDVariable·None 이어야 합니다 (%r)", every)
        self.every = every
        self.enable = enable
        self._enable_used = False
        # 저장소 (모두 로컬 오염 허용 — 공유 로직이 읽지 않는다)
        self.archive = Db(4 * LINES * ARCHIVE_CELLS)
        """보관소: slot k 의 보관 셀 i = archive + 4·(52·k + i)."""
        self.rem_vars = [EUDVariable() for _ in range(LINES)]
        """slot 별 남은 일 = (52 − k) + lag. 0 이면 진행 중이 아니다."""
        self.lag_vars = [EUDVariable() for _ in range(LINES)]
        """slot 별 아직 줄에 옮기지 않은 셀 수 (k − 쓴 셀 수)."""
        self.timer = EUDVariable() if every is not None else None
        self._due = EUDLightVariable() if every is not None else None
        self._body = None
        _compat.register_build_reset(self._reset_build)

    def _reset_build(self):
        self._enable_used = False

    def __repr__(self):
        return "<Typewriter marker=%r rule=%s speed=%r every=%r>" % (self.marker, self.rule, self.speed, self.every)

    # --- 문구 ---
    def mark(self, text):
        """문구 앞에 표식을 붙인다. 문구 안의 줄바꿈(`\\n`) 뒤에도 붙인다(끝의 줄바꿈 뒤는 빼고).

        인자: text(str 또는 bytes)
        반환: text 와 같은 형(str 이면 str)
        비용: 트리거 0 (컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `DisplayTextAll(tw.mark("\\x13\\x04안녕"));`
        출처: 원본 문구 표의 `"\\x0D\\x0D!H"..` 붙이기, UERE Destr0yer.lua:11 (줄마다 표식)
        """
        if isinstance(text, str):
            try:
                mk = self.marker.decode("utf-8")
            except UnicodeDecodeError:
                fail("Typewriter.mark: marker %r 가 UTF-8 이 아니라 str 문구에 붙일 수 없습니다 (bytes 로 넘기세요)",
                     self.marker)
            nl = "\n"
        elif isinstance(text, (bytes, bytearray)):
            text = bytes(text)
            mk = self.marker
            nl = b"\n"
        else:
            fail("Typewriter.mark: 문구는 str 또는 bytes 여야 합니다 (%r)", text)
        lines = text.split(nl)
        out = [mk + lines[0]]
        for i, ln in enumerate(lines[1:], 1):
            last = i == len(lines) - 1
            out.append(ln if (last and not ln) else mk + ln)
        return nl.join(out)

    f_mark = mark

    # --- 매 프레임 ---
    def _enable_conds(self):
        en = self.enable
        if en is None:
            return []
        if callable(en) and not _compat.is_var(en) and not isinstance(en, (EUDLightVariable, EUDLightBool)):
            en = en()
        elif self._enable_used and not (_compat.is_var(en) or isinstance(en, (EUDLightVariable, EUDLightBool))):
            raise EudextError("[eudext] Typewriter.tick: enable 조건 객체는 한 번만 쓸 수 있습니다 — tick() 을 여러 번 부르면 "
                              "enable 에 조건을 돌려주는 함수를 넘기세요")
        self._enable_used = True
        out = []
        for c in _flat(en):
            if isinstance(c, EUDLightBool):
                out.append(c.IsSet())
            elif _compat.is_var(c) or isinstance(c, EUDLightVariable):
                out.append(c.AtLeast(1))
            else:
                out.append(c)
        return out

    def tick(self):
        """한 프레임 분량: 이 PC 가 대상이고 enable 이 참이면 11줄을 처리한다. 매 프레임 한 번 부른다.

        인자: 없음
        반환: None
        비용: 호출 자리 약 3 + 대상 판정(players.contains_user). 본문·실행은 클래스 docstring
        CP: 바꾸지 않음
        로컬: 안에서 로컬 분기 (공유 흐름 어디서 불러도 된다)
        epScript: `tw.tick();`
        출처: CtrigAsm `CDPrint(0, 11, {"\\x0D",0,0}, 대상, {1,0,0,0,1,1,0,0}, "HTextEff", FP)` 한 번
        """
        body = self._get_body()
        conds = _flat(players.contains_user(self.targets)) + self._enable_conds()
        if EUDIf()(conds):
            body()
        EUDEndIf()

    f_tick = tick

    # --- 본문 ---
    def _get_body(self):
        if self._body is None:
            @EUDFunc
            def typewriter_body():
                with local.f_allow():
                    self._emit_body()

            self._body = typewriter_body
        return self._body

    def _consts(self, k):
        p = line_ptr(k)
        sub = p & 3
        src_epd = (p - sub - EPD0) // 4
        return src_epd, sub, line_epd(k), EPD(self.archive) + ARCHIVE_CELLS * k

    def _emit_body(self):
        cur_src, cur_sub, cur_line, cur_arch = (EUDVariable() for _ in range(4))
        conv = _Routine()
        rev = _Routine()
        loader = _Loader(2)

        if self.every is not None:
            RawTrigger(actions=[self.timer.SubtractNumber(1), self._due.SetNumber(0)])  # 0 에서 멈춤(포화) — UERE SubCD
            RawTrigger(conditions=self.timer.Exactly(0), actions=self._due.SetNumber(1))

        # 칸별 판정: A(진행 중 ∧ 표식 → R 로) / B(진행 상태 지움) / C(원문 표식 → 변환 호출).
        # A·C·R 은 조건이 참이면 자기 next 를 고쳐 갈라진다(eudplib EUDBranch 와 같은 원리) → 프레임 첫 트리거가 되돌린다.
        slots = [tuple(Forward() for _ in range(4)) for _ in range(LINES)]  # a, b, c, r
        after = Forward()
        heads = [s_[0] for s_ in slots] + [after]
        RawTrigger(actions=[act for k, (a, b, c, r) in enumerate(slots)
                            for act in (SetNextPtr(a, b), SetNextPtr(c, heads[k + 1]), SetNextPtr(r, heads[k + 1]),
                                        *loader.chain_acts([self.rem_vars[k], self.lag_vars[k]]))])
        for k, (a, b, c, r) in enumerate(slots):
            nxt = heads[k + 1]
            src_epd, sub, lepd, aepd = self._consts(k)
            a << RawTrigger(conditions=[self.rem_vars[k].AtLeast(1), _mark_cell_cond(k)], actions=SetNextPtr(a, r))
            b << RawTrigger(actions=self.rem_vars[k].SetNumber(0))
            # C: 원문이 표식으로 시작하면 이 칸의 상수를 싣고 변환 루틴으로 (루틴 끝이 다음 칸으로 돌아온다)
            c << RawTrigger(conditions=_raw_marker_conds(k, self.marker), actions=[
                cur_src.SetNumber(src_epd), cur_sub.SetNumber(sub), cur_line.SetNumber(lepd), cur_arch.SetNumber(aepd),
                self.rem_vars[k].SetNumber(ARCHIVE_CELLS), self.lag_vars[k].SetNumber(0),
                SetNextPtr(conv.ret, nxt), SetNextPtr(c, conv.entry),
            ])
        after << NextTrigger()
        if self.nul_cell:
            RawTrigger(actions=[SetMemory(line_cell_addr(k, 53), SetTo, 0) for k in range(LINES)])
        if self.every is not None:
            if _compat.is_var(self.every):
                if EUDIf()(self.timer.Exactly(0)):
                    self.timer << self.every
                EUDEndIf()
            else:
                RawTrigger(conditions=self.timer.Exactly(0), actions=self.timer.SetNumber(self.every))
        end = Forward()
        EUDJump(end)

        # R: 진행 중인 줄이 떠 있으면 칸 변수를 루틴 변수로 읽어 드러내기 루틴으로 (흐름 밖, A 가 뛰어 온다)
        PushTriggerScope()
        for k, (a, b, c, r) in enumerate(slots):
            nxt = heads[k + 1]
            _src_epd, _sub, lepd, aepd = self._consts(k)
            r << RawTrigger(nextptr=nxt, conditions=_active_cond(k), actions=[
                cur_line.SetNumber(lepd), cur_arch.SetNumber(aepd),
                *loader.call_acts([self.rem_vars[k], self.lag_vars[k]]),
                SetNextPtr(rev.ret, nxt), SetNextPtr(r, rev.entry),
            ])
        PopTriggerScope()

        with conv.define():
            self._emit_convert(cur_src, cur_sub, cur_line, cur_arch)
        with rev.define():
            loader.load()
            self._emit_reveal(loader.cur[0], loader.cur[1], cur_line, cur_arch)
            loader.save()

        end << NextTrigger()

    def _emit_convert(self, cur_src, cur_sub, cur_line, cur_arch):
        blank_run = _blank_run_func()
        # 보관 줄을 빈칸 52 로
        SeqCompute([(CP_EPD, SetTo, cur_arch)])
        blank_run(ARCHIVE_CELLS)
        # 원문 → 보관 셀 (최대 52)
        tfx._scanner(self.rule, False)(cur_src, cur_sub, cur_arch, ARCHIVE_CELLS)
        if self.erase:
            SeqCompute([(CP_EPD, SetTo, cur_arch)])
            blank_run(self.erase)
        # 줄 = 표식 + 빈칸 52 + NUL
        SeqCompute([(CP_EPD, SetTo, cur_line)])
        RawTrigger(actions=[SetDeaths(CurrentPlayer, SetTo, tfx.MARK_U200B, 0), SetMemory(CP_ADDR, Add, 1)])
        blank_run(ARCHIVE_CELLS)
        RawTrigger(actions=SetDeaths(CurrentPlayer, SetTo, 0, 0))
        f_setcurpl2cpcache()

    def _emit_reveal(self, cr, cl, cur_line, cur_arch):
        src = EUDVariable()
        dst = EUDVariable()
        if EUDIf()(cl.AtLeast(1)):
            # 다음에 옮길 보관 셀 = 52 − cr, 줄 셀 = 53 − cr   (cr ≤ 52 라 Subtract 가 정확하다 — 3.5-7)
            SeqCompute([(src, SetTo, cur_arch), (src, Add, ARCHIVE_CELLS), (src, Subtract, cr),
                        (dst, SetTo, cur_line), (dst, Add, ARCHIVE_CELLS + 1), (dst, Subtract, cr)])
            if EUDWhile()(cl.AtLeast(1)):
                f_dwwrite_epd(dst, f_dwread_epd(src))
                RawTrigger(actions=[src.AddNumber(1), dst.AddNumber(1), cl.SubtractNumber(1), cr.SubtractNumber(1)])
            EUDEndWhile()
        EUDEndIf()
        due = [cr.AtLeast(1)]
        if self._due is not None:
            due.append(self._due.Exactly(1))
        if EUDIf()(due):
            if self.sound is not None:
                self._emit_sound(cr, cur_arch, src)
            if _compat.is_var(self.speed):
                cl << self.speed
                if EUDIf()(cmp.gt(cl, cr)):
                    cl << cr
                EUDEndIf()
            else:
                if EUDIf()(cr.AtLeast(self.speed)):
                    RawTrigger(actions=cl.SetNumber(self.speed))
                if EUDElse()():
                    cl << cr
                EUDEndIf()
        EUDEndIf()

    def _emit_sound(self, cr, cur_arch, src):
        # 늘리기 전 k = 52 − cr (k ≥ 1 ⇔ cr ≤ 51). 셀 k = 보관 셀 k−1 = arch + 51 − cr
        if EUDIf()(cr.AtMost(ARCHIVE_CELLS - 1)):
            snd = EUDLightVariable()
            SeqCompute([(src, SetTo, cur_arch), (src, Add, ARCHIVE_CELLS - 1), (src, Subtract, cr), (CP_EPD, SetTo, src)])
            RawTrigger(actions=snd.SetNumber(1))
            RawTrigger(conditions=DeathsX(CurrentPlayer, Exactly, 0x0D0D0D00, 0, 0xFFFFFF00), actions=snd.SetNumber(0))
            RawTrigger(conditions=DeathsX(CurrentPlayer, Exactly, 0x00002000, 0, 0x0000FF00), actions=snd.SetNumber(0))
            f_setcurpl2cpcache()
            if EUDIf()(snd.Exactly(1)):
                RawTrigger(actions=PlayWAVAll(self.sound))
                f_setcurpl2cpcache()
            EUDEndIf()
        EUDEndIf()


@functools.cache
def _blank_run_func():
    """CP 칸부터 빈칸 셀 n 개를 쓰고 CP 를 n 칸 뒤로 둔다(원시 CP — 캐시는 부르는 쪽이 되돌린다). 여러 타자기가 함께 쓴다."""

    @EUDFunc
    def blank_run(n):
        four = []
        for _ in range(4):
            four += [SetDeaths(CurrentPlayer, SetTo, tfx.BLANK, 0), SetMemory(CP_ADDR, Add, 1)]
        if EUDWhile()(n.AtLeast(4)):
            RawTrigger(actions=[*four, n.SubtractNumber(4)])  # n ≥ 4 (3.5-7)
        EUDEndWhile()
        if EUDWhile()(n.AtLeast(1)):
            RawTrigger(actions=[SetDeaths(CurrentPlayer, SetTo, tfx.BLANK, 0), SetMemory(CP_ADDR, Add, 1),
                                n.SubtractNumber(1)])
        EUDEndWhile()

    return blank_run


class _Routine:
    """인자 없는 공유 루틴: entry … ret(RawTrigger — next 는 부르는 트리거가 고친다). 재진입 금지."""

    def __init__(self):
        self.entry = Forward()
        self.ret = Forward()

    def define(self):
        import contextlib

        @contextlib.contextmanager
        def ctx():
            with _compat.isolated_scope():
                self.entry << NextTrigger()
                yield
                self.ret << RawTrigger()

        return ctx()


class _Loader:
    """칸 변수 n 개를 루틴 변수로 읽어 오고(load) 루틴 끝에서 되돌려 쓴다(save). 칸마다의 준비는 상수 액션뿐이다.

    부르는 트리거 액션(`call_acts`): 칸 변수 j 의 dest = 루틴 변수 j, 점프 트리거의 next = 칸 변수 0,
    저장 목적지(EPD) 변수 = 칸 변수 j 의 값 칸. 칸 변수의 next 사슬(칸 변수 j → j+1 … → 읽기 끝)은 상수라
    프레임 첫 트리거가 싣는다(`chain_acts`).
    칸 변수는 이 로더만 원천으로 쓰므로 수정자는 eudplib 기본값 SetTo 그대로다(core/variable/vbuf.py:81, 0x07).
    eudplib `VProc`(core/variable/eudv.py:665)와 같은 필드만 쓴다(SetDest·SetModifier·SetNextPtr).
    """

    def __init__(self, n):
        self.cur = [EUDVariable() for _ in range(n)]
        self.sdst = [EUDVariable() for _ in range(n)]
        self.jump = Forward()
        self.loaded = Forward()

    def call_acts(self, slot_vars):
        acts = []
        for j, v in enumerate(slot_vars):
            acts += [v.SetDest(self.cur[j]), self.sdst[j].SetNumber(EPD(v.getValueAddr()))]
        acts.append(SetNextPtr(self.jump, slot_vars[0].GetVTable()))
        return acts

    def chain_acts(self, slot_vars):
        chain = [v.GetVTable() for v in slot_vars] + [self.loaded]
        return [SetNextPtr(v.GetVTable(), chain[j + 1]) for j, v in enumerate(slot_vars)]

    def load(self):
        self.jump << RawTrigger(nextptr=self.loaded)
        self.loaded << NextTrigger()

    def save(self):
        acts = [s.QueueAssignTo(EPD(c.getDestAddr())) for s, c in zip(self.sdst, self.cur)]
        acts += [c.SetModifier(SetTo) for c in self.cur]
        VProc(self.sdst + self.cur, acts)
