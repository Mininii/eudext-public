"""textfx — 글자 셀 상수와 채팅 줄 스캐너 (DESIGN 4.8, 정본 명세 docs/spec/S6_chat.md 1.7·4.1).

채팅 버퍼(0x640B60~)의 줄은 **셀**(4바이트 dword) 54개로 볼 수 있다. 셀 하나 = 보이는 글자 하나(+ 앞 색 코드).
eudext 는 eudplib 배치를 쓴다(`[C][b0][b1][b2]`, 빈 바이트는 0x0D — 화면에 보이지 않는다).

| 글자 | CtrigAsm iutf8 (`cell_const_ctrig`) | eudplib (`cell_const`, 이 모듈의 스캐너) |
|---|---|---|
| 1바이트 `c` | `[C][0D][0D][c]` | `[C][c][0D][0D]` |
| 2바이트 `b0 b1` | `[C][0D][b0][b1]` | `[C][b0][b1][0D]` |
| 3바이트 `b0 b1 b2` | `[C][b0][b1][b2]` | 같음 |

C 는 색 코드(없으면 0x0D). dword 값은 리틀 엔디언이다(`[C]` 가 가장 낮은 바이트).

    from eudext import textfx as tfx
    tfx.cell_const("가")               # 0x80B0EA0D
    tfx.cell_const("a", 0x07)          # 0x0D0D6107
    tfx.BLANK, tfx.MARK_U200B          # 0x0D0D0D0D, 0x8B80E20D (두 배치 공통)
    with local.only():                 # 스캐너는 로컬 분기 안에서만 (DESIGN 3.7)
        n = tfx.f_scan_cells(0x640B60, EPD(buf), 52)          # 채팅 줄 0 → 셀 버퍼, n = 셀 수
    tfx.scan_const(b"\\r\\r!H\\x13\\x07\\xeb\\xb3\\xb4").cells     # 컴파일 시점 참조 구현 (같은 규칙)

## 스캐너 규칙 (`rule=`)

`"ctrig"`(기본) — CtrigAsm `CD__ScanChat` 의 묶음 규칙(원본 코드 읽기: CtrigAsm v5.5.lua:87607~88980) + 2바이트 수정:
- 색 코드(0x01~0x08, 0x0E~0x11, 0x14~0x1F)는 **다음 글자 셀의 C** 로 합친다(연속이면 마지막 것).
  정확히는 "그 색 코드를 만났을 때의 출력 위치" 셀의 C 에 글자를 쓴 뒤 덮어쓴다 → 색 코드와 글자 사이에
  0x0D×4 빈칸 셀이 끼면 색은 그 빈칸 셀에 들어간다(보이는 결과는 같다).
- 색 코드 바로 뒤가 0x0D 세 개면 `[C][0D][0D][0D]` 셀 하나(색 있는 빈칸, 4바이트 소비).
- 0x0D 는 **4개 연속일 때만** 빈칸 셀 `BLANK` 하나(4바이트 소비), 모자라면 1바이트 건너뜀.
- 0x0A 는 셀 `0x0D0D0A0D`. 바로 뒤가 NUL 이거나 셀 한도의 마지막 칸이면 쓰지 않는다(한도는 줄어든다).
  이때 대기 중인 색 코드는 쓰지 않은 그 칸(반환 수 바로 뒤)의 C 에 들어간다(원본과 같음, 보이지 않음).
- 그 밖의 0x7F 이하(0x09·0x0B·0x0C·0x12·0x13·0x7F 포함)는 1바이트 셀, **0xC0~0xDF 는 2바이트 셀(원본은 3바이트로
  잘못 읽었다 — 고침)**, 0xF0 이상(4바이트 글자)은 4바이트를 먹고 `'?'` 셀, 그 밖(0x80~0xBF·0xE0~0xEF)은 3바이트 셀.
- NUL(글자 머리 자리)에서 멈추고 NUL 셀은 쓰지 않는다. 여러 바이트 글자의 뒤 바이트가 NUL 이면 그 글자를 쓰지 않고 멈춘다
  (원본은 그대로 읽어 넘어갔다 — 줄 끝이 잘린 글자에서만 다르다).
- 셀 한도(`max_cells`)는 글자·빈칸·줄바꿈 셀마다 1 줄어든다(색 코드·건너뛴 0x0D 는 안 줄어듦).

`"eudplib"` — eudplib `_cpchar_addstr`(string/texteffect.py:28) 와 같은 묶음: 0x7F 이하는 모두 1바이트 셀(색 코드·0x0D·0x0A 포함),
0x80~0xDF 는 2바이트, 0xE0 이상은 3바이트 셀. 다른 점: C 는 0x0D 다(eudplib 은 런타임 색 변수 `color_v`, 기본 0x02),
셀 한도가 있고, 뒤 바이트가 NUL 이면 멈춘다.

`skip_odd_head=True`: 첫 두 바이트가 0x0D 0x0D 면 건너뛴다(원본 `SkipInit` 의 홀수 줄 동작). 표식 줄 `"\\r\\r!H…"` 은
이 옵션과 상관없이 결과가 같다(0x0D 한 개씩은 어차피 건너뛴다).

`convert_color`·`reveal`·`blit`·`convert_letter`(CtrigAsm `CA__ConvertColor`·`CA__MoveXY` 등)는 맵 사용이 0회라
설계만 남겼다(S6 7-3, DESIGN 4.8). 필요하면 요청한다.

출처: CtrigAsm v5.5.lua `str_to_iutf8`(45778~45863), `CD__ScanChat`(54918~55051, 공용 본문 87607~88980),
eudplib 0.81 `string/texteffect.py`(`_cpchar_addstr`, `f_cpchar_print`), `memio/cpbyterw.py`(뒤를 0x0D 로 채움),
`memio/readtable.py`(CP 기준 비트 읽기 방식). DPS_Enhance eudplib-port(a7aad90)에는 같은 일을 하는 코드가 없다.
"""

import collections
import functools

import sys

from eudplib import (
    EPD,
    Add,
    AtLeast,
    CurrentPlayer,
    DeathsX,
    EUDBreak,
    EUDElse,
    EUDElseIf,
    EUDEndIf,
    EUDEndWhile,
    EUDFunc,
    EUDIf,
    EUDJump,
    EUDLightVariable,
    EUDSCOr,
    EUDVariable,
    EUDWhile,
    Forward,
    NextTrigger,
    RawTrigger,
    SeqCompute,
    SetMemory,
    SetMemoryXEPD,
    SetNextPtr,
    SetTo,
    VProc,
    f_setcurpl2cpcache,
)

from eudext import _compat
from eudext.errors import check_choice, fail, warn

__all__ = [
    "BLANK",
    "CELL_NEWLINE",
    "CELL_UNKNOWN",
    "COLOR_CODES",
    "MARK_U200B",
    "RULES",
    "ScanResult",
    "cell_const",
    "cell_const_ctrig",
    "f_cell_const",
    "f_cell_const_ctrig",
    "f_scan_cells",
    "f_scan_cells_epd",
    "f_scan_const",
    "is_marker_cell",
    "scan_cells",
    "scan_cells_epd",
    "scan_const",
    "warn_outside_local",
]

M32 = 0xFFFFFFFF
EPD0 = 0x58A364
CP_ADDR = 0x6509B0
CP_EPD = 203155  # EPD(0x6509B0)

BLANK = 0x0D0D0D0D
"""빈칸 셀 (보이지 않는 0x0D 네 개). CtrigAsm·eudplib 배치 공통."""
MARK_U200B = 0x8B80E20D
"""보이지 않는 표식 셀: U+200B(E2 80 8B) + C 0x0D. 타자기가 변환한 줄의 셀 0. 두 배치 공통."""
MARK_MASK = 0xFFFFFF00
"""표식 셀 비교 마스크 (C 바이트는 보지 않는다 — 줄이 꺼지면 SC 가 첫 바이트를 0 으로 만든다)."""
CELL_NEWLINE = 0x0D0D0A0D
"""줄바꿈 셀 (eudplib 배치). CtrigAsm 배치는 0x0A0D0D0D."""
CELL_UNKNOWN = 0x0D0D3F0D
"""4바이트 글자를 대신하는 '?' 셀 (eudplib 배치)."""
COLOR_CODES = frozenset(list(range(0x01, 0x09)) + list(range(0x0E, 0x12)) + list(range(0x14, 0x20)))
"""CtrigAsm `CD__ScanChat` 이 색 코드로 보는 바이트 (CtrigAsm v5.5.lua:88132)."""
RULES = ("ctrig", "eudplib")

_REP = 0x01010101


# =============================================================================================
# 셀 상수 (컴파일 시점)
# =============================================================================================


def _char_bytes(fname, ch):
    if isinstance(ch, (bytes, bytearray)):
        b = bytes(ch)
        try:
            s = b.decode("utf-8")
        except UnicodeDecodeError:
            fail("%s: UTF-8 글자 하나가 아닙니다 (%r)", fname, ch)
    elif isinstance(ch, str):
        s = ch
        b = s.encode("utf-8")
    else:
        fail("%s: 글자는 str 또는 bytes 한 글자여야 합니다 (%r)", fname, ch)
    if len(s) != 1:
        fail("%s: 글자 하나만 받습니다 (%r, %d 글자)", fname, ch, len(s))
    if len(b) > 3:
        fail("%s: 4바이트 UTF-8 글자(%r)는 셀 하나에 넣을 수 없습니다", fname, ch)
    return b


def _color_byte(fname, color):
    if color is None:
        return 0x0D
    if isinstance(color, (str, bytes, bytearray)):
        b = color.encode("utf-8") if isinstance(color, str) else bytes(color)
        if len(b) != 1:
            fail("%s: 색 코드는 1바이트여야 합니다 (%r)", fname, color)
        return b[0]
    if isinstance(color, bool) or not isinstance(color, int) or not 0 <= color <= 0xFF:
        fail("%s: 색 코드는 0~255 정수 또는 1바이트 문자여야 합니다 (%r)", fname, color)
    return color


def f_cell_const(ch, color=None):
    """글자 하나의 셀 dword (eudplib 배치): 1바이트 `[C][c][0D][0D]`, 2바이트 `[C][b0][b1][0D]`, 3바이트 `[C][b0][b1][b2]`.

    인자: ch(str/bytes 한 글자, 4바이트 글자는 오류), color(None = 0x0D, 0~255 또는 "\\x07" 같은 1바이트)
    반환: int (dword, 리틀 엔디언 — C 가 가장 낮은 바이트)
    비용: 트리거 0 (컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const c = tfx.cell_const("가");` (→ `f_cell_const`)
    출처: eudplib 0.81 `string/texteffect.py:98` f_cpchar_print(글자 뒤를 0x0D 로 채움), S6 1.7 표
    """
    b = _char_bytes("cell_const", ch)
    c = _color_byte("cell_const", color)
    body = b + b"\r" * (3 - len(b))
    return c | (body[0] << 8) | (body[1] << 16) | (body[2] << 24)


def f_cell_const_ctrig(ch, color=None):
    """글자 하나의 셀 dword (CtrigAsm iutf8 배치 — 옛 데이터 비교용): 1바이트 `[C][0D][0D][c]`, 2바이트 `[C][0D][b0][b1]`.

    인자: ch(str/bytes 한 글자), color(None = 0x0D)
    반환: int
    비용: 트리거 0 (컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const c = tfx.cell_const_ctrig("a", 7);` (→ `f_cell_const_ctrig`)
    출처: CtrigAsm v5.5.lua:45814~45843 str_to_iutf8, S6 1.7 표
    """
    b = _char_bytes("cell_const_ctrig", ch)
    c = _color_byte("cell_const_ctrig", color)
    body = b"\r" * (3 - len(b)) + b
    return c | (body[0] << 8) | (body[1] << 16) | (body[2] << 24)


cell_const = f_cell_const
cell_const_ctrig = f_cell_const_ctrig


def is_marker_cell(value):
    """셀 값이 보이지 않는 표식(U+200B, C 는 무시)인가 — 컴파일 시점 판정.

    인자: value(int)
    반환: bool
    비용: 트리거 0
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: S6 1.2 S7 (`TTDisplayX(L,0,Exactly,0x8B80E200,0xFFFFFF00)`)
    """
    return (value & MARK_MASK) == (MARK_U200B & MARK_MASK)


# =============================================================================================
# 컴파일 시점 참조 스캐너 (시험의 기대값, 상수 문자열의 셀 미리 계산)
# =============================================================================================

ScanResult = collections.namedtuple("ScanResult", "cells extra")
ScanResult.__doc__ = """`scan_const` 결과.

cells: 셀 dword 목록(길이 = 반환 수), extra: {칸 번호: C 바이트} — 반환 수 **뒤** 칸의 C 에 쓰는 것(대기 색 코드 + 무시한
줄바꿈, 원본과 같은 부수효과). 런타임 스캐너는 그 칸의 가장 낮은 바이트만 바꾼다.
"""


def _check_rule(fname, rule):
    return check_choice(fname + ": rule", rule, RULES)


def f_scan_const(data, max_cells=52, rule="ctrig", skip_odd_head=False):
    """UTF-8 바이트열을 셀로 바꾼다 — `f_scan_cells` 와 같은 규칙의 **컴파일 시점** 판(참조 구현).

    data 는 원문 바이트열이다. 끝(또는 첫 NUL 뒤)은 NUL 로 본다. 앞보기(0x0D 네 개, 줄바꿈 뒤 NUL)는 NUL 뒤의
    바이트까지 본다(런타임 스캐너가 메모리를 그대로 읽는 것과 같게) — 시험에서 NUL 뒤 바이트를 흉내 낼 때 넘긴다.
    인자: data(bytes 또는 str — str 은 UTF-8), max_cells(정수 ≥ 0), rule("ctrig"|"eudplib"), skip_odd_head(bool)
    반환: ScanResult(cells, extra)
    비용: 트리거 0
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (컴파일 시점 도구)
    출처: 모듈 docstring 의 규칙 (CtrigAsm v5.5.lua:87607~88980 을 읽고 정리)
    """
    _check_rule("scan_const", rule)
    if isinstance(data, str):
        data = data.encode("utf-8")
    data = bytes(data)
    if isinstance(max_cells, bool) or not isinstance(max_cells, int) or max_cells < 0:
        fail("scan_const: max_cells 는 0 이상 정수여야 합니다 (%r)", max_cells)

    def at(i):
        return data[i] if 0 <= i < len(data) else 0

    cells = []
    extra = {}
    pos = 0
    budget = max_cells
    armed = False
    pend = None  # [color, dest index]

    def after_glyph():
        nonlocal pend
        # 원본: 글자 경로가 깃발 8 을 지운 뒤 반복 끝에서 대기 색을 그 칸의 C 에 쓴다
        if pend is not None and not armed:
            color, dest = pend
            if dest < len(cells):
                cells[dest] = (cells[dest] & ~0xFF) | color
            else:
                extra[dest] = color
            pend = None

    def emit(cell):
        nonlocal budget
        cells.append(cell)
        budget -= 1

    if skip_odd_head and at(0) == 0x0D and at(1) == 0x0D:
        pos = 2
    while budget > 0:
        b = at(pos)
        if b == 0:
            break
        if rule == "eudplib":
            if b <= 0x7F:
                emit(0x0D0D000D | (b << 8))
                pos += 1
            elif b <= 0xDF:
                b1 = at(pos + 1)
                if b1 == 0:
                    break
                emit(0x0D00000D | (b << 8) | (b1 << 16))
                pos += 2
            else:
                b1, b2 = at(pos + 1), at(pos + 2)
                if b1 == 0 or b2 == 0:
                    break
                emit(0x0D | (b << 8) | (b1 << 16) | (b2 << 24))
                pos += 3
            continue
        # --- rule == "ctrig" ---
        if b == 0x0A:
            armed = False
            ignore = at(pos + 1) == 0 or budget == 1
            if ignore:
                budget -= 1
            else:
                emit(CELL_NEWLINE)
            pos += 1
            after_glyph()
        elif b == 0x0D:
            if at(pos + 1) == 0x0D and at(pos + 2) == 0x0D and at(pos + 3) == 0x0D:
                emit(BLANK)
                pos += 4
            else:
                pos += 1
        elif b in COLOR_CODES:
            if armed:
                pend[0] = b
                pos += 1
            elif at(pos + 1) == 0x0D and at(pos + 2) == 0x0D and at(pos + 3) == 0x0D:
                emit((BLANK & ~0xFF) | b)
                pos += 4
            else:
                pend = [b, len(cells)]
                armed = True
                pos += 1
        elif b <= 0x7F:
            armed = False
            emit(0x0D0D000D | (b << 8))
            pos += 1
            after_glyph()
        elif b & 0xE0 == 0xC0:
            b1 = at(pos + 1)
            if b1 == 0:
                break
            armed = False
            emit(0x0D00000D | (b << 8) | (b1 << 16))
            pos += 2
            after_glyph()
        elif b & 0xF0 == 0xF0:
            if at(pos + 1) == 0 or at(pos + 2) == 0 or at(pos + 3) == 0:
                break
            armed = False
            emit(CELL_UNKNOWN)
            pos += 4
            after_glyph()
        else:
            b1, b2 = at(pos + 1), at(pos + 2)
            if b1 == 0 or b2 == 0:
                break
            armed = False
            emit(0x0D | (b << 8) | (b1 << 16) | (b2 << 24))
            pos += 3
            after_glyph()
    return ScanResult(cells, extra)


scan_const = f_scan_const


# =============================================================================================
# 런타임 스캐너
# =============================================================================================
#
# 구조 (EUDFunc 한 벌, 규칙·옵션마다):
# - 앞보기 창 q0..q3 = 다음 네 바이트. 각 변수 값은 "바이트 × 0x01010101"(네 칸에 같은 바이트) — 마스크 SetTo 한 번으로
#   셀의 어느 칸에든 넣을 수 있다(원본 FCHAT[4] 와 같은 방법, CtrigAsm v5.5.lua:87706).
# - 새 바이트 읽기: CP = 원문 dword EPD. 바이트 칸 `sub` 에 맞춰 비트 조건 8개의 마스크를 고치고(분기 트리거 4개 중 하나)
#   `DeathsX(CurrentPlayer, AtLeast, 1, 0, 1<<(8·sub+x))` 가 참이면 q3 에 더한다(eudplib memio/readtable.py 방식).
#   CP 는 잠깐 옮겨 쓰고 끝에서 `f_setcurpl2cpcache()` 로 되돌린다(DESIGN 3.6 — R3 1.5-1 잠깐 옮기기).
# - 셀 쓰기: 쓰기 트리거 W 하나(마스크 SetTo 액션 5개: 전체 BLANK, 칸 1·2·3, 칸 0). 글자 경로가 값 칸을 채우고
#   W 가 쓴 뒤 값 칸을 BLANK 로 되돌린다. 목적지(player 필드 5개)는 셀마다 Add 1.
# - 대기 색: 트리거 WP(조건 pending ∧ ¬armed)의 값·목적지 칸을 색 코드를 만났을 때 채운다(원본 CAPrintVarAlloc 트리거).
# - 마스크 Add/Subtract(인게임 미확인, DESIGN 5.1)는 쓰지 않는다. 마스크는 SetTo 와 조건에만 쓴다.


def _act_field(trig, i, off):
    """트리거 주소식의 액션 i 필드 주소: +0 locid(마스크), +16 player, +20 amount(값)."""
    return trig + 328 + 32 * i + off


def _cond_field(trig, i, off):
    """트리거 주소식의 조건 i 필드 주소: +0 locid(마스크), +4 player, +8 amount."""
    return trig + 8 + 20 * i + off


@functools.cache
def _scanner(rule, skip):
    ctrig = rule == "ctrig"

    @EUDFunc
    def scan_body(src_epd, src_sub, dst_epd, max_cells):
        q0, q1, q2, q3 = (EUDVariable() for _ in range(4))
        sub = EUDVariable()
        count = EUDVariable()
        budget = EUDVariable()
        dst = EUDVariable()
        adv = EUDVariable()
        armed = EUDLightVariable()
        pending = EUDLightVariable()
        first = EUDLightVariable()
        readers = [Forward() for _ in range(8)]
        w = Forward()  # 셀 쓰기 트리거 (= emit 자리)
        wp = Forward()  # 대기 색 쓰기 트리거
        adv_lbl = Forward()
        w_player = [EPD(_act_field(w, i, 16)) for i in range(5)]
        w_value = [_act_field(w, i, 20) for i in range(5)]  # 0 전체, 1~3 칸, 4 칸 0(C)

        # --- 준비: 창을 네 바이트 채우러 간다 ---
        # 읽기 한 번 = sub += 1 뒤 sub 칸을 읽는다. sub == 4 는 "다음 dword 의 칸 0"(CP += 1) 이다.
        # 첫 바이트가 칸 0 이면 "앞 dword 의 칸 3 다음" 으로 둔다(sub = 3, CP = src_epd − 1), 아니면 sub = src_sub − 1.
        RawTrigger(actions=[count.SetNumber(0), adv.SetNumber(4), armed.SetNumber(0), pending.SetNumber(0),
                            first.SetNumber(1), sub.SetNumber(3)])
        SeqCompute([(budget, SetTo, max_cells), (dst, SetTo, dst_epd), (sub, Add, src_sub)]
                   + [(f, SetTo, dst_epd) for f in w_player] + [(CP_EPD, SetTo, src_epd)])
        RawTrigger(conditions=sub.AtMost(3), actions=SetMemory(CP_ADDR, Add, M32))
        RawTrigger(conditions=sub.AtLeast(4), actions=sub.SubtractNumber(4))  # sub ≥ 4 가 보장됨 (3.5-7)
        EUDJump(adv_lbl)

        if EUDWhile()(budget.AtLeast(1)):
            if ctrig:
                _classify_ctrig(q0, q1, q2, q3, budget, adv, armed, pending, dst, w_value, w, wp)
            else:
                _classify_eudplib(q0, q1, q2, adv, w_value, w)
            EUDJump(adv_lbl)

            # --- 셀 쓰기 ---
            w << RawTrigger(actions=[
                SetMemoryXEPD(0, SetTo, BLANK, M32),
                SetMemoryXEPD(0, SetTo, BLANK, 0x0000FF00),
                SetMemoryXEPD(0, SetTo, BLANK, 0x00FF0000),
                SetMemoryXEPD(0, SetTo, BLANK, 0xFF000000),
                SetMemoryXEPD(0, SetTo, BLANK, 0x000000FF),
                *[SetMemory(v, SetTo, BLANK) for v in w_value[1:]],
                count.AddNumber(1),
                budget.SubtractNumber(1),  # 여기서 budget ≥ 1 (DESIGN 3.5-7: 앞 단계가 보장)
                dst.AddNumber(1),
                *[SetMemory(_act_field(w, i, 16), Add, 1) for i in range(5)],
            ])
            wp << RawTrigger(
                conditions=[pending.Exactly(1), armed.Exactly(0)],
                actions=[SetMemoryXEPD(0, SetTo, 0, 0x000000FF), pending.SetNumber(0)],
            )

            # --- 바이트 소비 (adv 번, adv ≥ 1 이 보장된 do-while) ---
            # 끝 트리거가 참이면 자기 next 를 머리로 고치고, 머리가 매번 되돌린다(EUDBranch 원리, 반복당 판정 1).
            loop_end = Forward()
            loop_exit = Forward()
            adv_lbl << NextTrigger()
            # 창을 한 칸 민다: q0←q1←q2←q3, sub += 1, adv −= 1
            VProc([q1, q2, q3], [q1.QueueAssignTo(q0), q2.QueueAssignTo(q1), q3.QueueAssignTo(q2),
                                 sub.AddNumber(1), adv.SubtractNumber(1), SetNextPtr(loop_end, loop_exit)])
            RawTrigger(
                conditions=sub.Exactly(4),
                actions=[sub.SetNumber(0), SetMemory(CP_ADDR, Add, 1), q3.SetNumber(0)]
                + [SetMemory(_cond_field(readers[x], 0, 0), SetTo, 1 << x) for x in range(8)],
            )
            for s in range(1, 4):
                RawTrigger(
                    conditions=sub.Exactly(s),
                    actions=[q3.SetNumber(0)]
                    + [SetMemory(_cond_field(readers[x], 0, 0), SetTo, 1 << (8 * s + x)) for x in range(8)],
                )
            for x in range(8):
                readers[x] << RawTrigger(
                    conditions=DeathsX(CurrentPlayer, AtLeast, 1, 0, 1 << x),
                    actions=q3.AddNumber(_REP << x),
                )
            loop_end << RawTrigger(nextptr=loop_exit, conditions=adv.AtLeast(1),
                                   actions=SetNextPtr(loop_end, adv_lbl))
            loop_exit << NextTrigger()
            if skip:
                # 창을 처음 채운 뒤 한 번: 머리 0x0D 0x0D 건너뛰기 (원본 SkipInit)
                if EUDIf()([first.Exactly(1), q0.ExactlyX(0x0D, 0xFF), q1.ExactlyX(0x0D, 0xFF)]):
                    RawTrigger(actions=[first.SetNumber(0), adv.SetNumber(2)])
                    EUDJump(adv_lbl)
                EUDEndIf()
                RawTrigger(conditions=first.Exactly(1), actions=first.SetNumber(0))
        EUDEndWhile()
        f_setcurpl2cpcache()
        return count

    return scan_body


def _classify_ctrig(q0, q1, q2, q3, budget, adv, armed, pending, dst, w_value, w, wp):
    def lane(k, v):  # 창 바이트 k == v
        return k.ExactlyX(v, 0xFF)

    def glyph(vars_, n):  # vars_[j] → 셀 칸 j+1, n 바이트 소비
        acts = [armed.SetNumber(0), adv.SetNumber(n)]
        acts += [v.QueueAssignTo(EPD(w_value[j + 1])) for j, v in enumerate(vars_)]
        VProc(list(vars_), acts)
        EUDJump(w)

    blank3 = [lane(q1, 0x0D), lane(q2, 0x0D), lane(q3, 0x0D)]
    if EUDIf()(q0.ExactlyX(0, 0x80)):  # 0x00~0x7F
        if EUDIf()(q0.ExactlyX(0, 0xE0)):  # 0x00~0x1F
            if EUDIf()(lane(q0, 0)):
                EUDBreak()
            if EUDElseIf()(lane(q0, 0x0A)):
                if EUDIf()(EUDSCOr()(lane(q1, 0))(budget.Exactly(1))()):  # 무시하는 줄바꿈
                    RawTrigger(actions=[budget.SubtractNumber(1), armed.SetNumber(0), adv.SetNumber(1)])
                    EUDJump(wp)
                EUDEndIf()
                RawTrigger(actions=[SetMemory(w_value[1], SetTo, 0x0A * _REP), armed.SetNumber(0),
                                    adv.SetNumber(1)])
                EUDJump(w)
            if EUDElseIf()(lane(q0, 0x0D)):
                if EUDIf()([lane(q1, 0x0D), lane(q2, 0x0D), lane(q3, 0x0D)]):  # 빈칸 셀
                    RawTrigger(actions=adv.SetNumber(4))
                    EUDJump(w)
                EUDEndIf()
                RawTrigger(actions=adv.SetNumber(1))
            if EUDElseIf()(EUDSCOr()(lane(q0, 0x09))(q0.ExactlyX(0x0A, 0xFE))(lane(q0, 0x0C))(q0.ExactlyX(0x12, 0xFE))()):
                glyph([q0], 1)  # 0x09 0x0B 0x0C 0x12 0x13 — 색 코드가 아닌 제어 문자
            if EUDElse()():  # 색 코드
                if EUDIf()(armed.Exactly(1)):  # 연속 색: 값만 바꾼다
                    VProc(q0, [q0.QueueAssignTo(EPD(_act_field(wp, 0, 20))), adv.SetNumber(1)])
                if EUDElseIf()(blank3):  # 색 있는 빈칸
                    VProc(q0, [q0.QueueAssignTo(EPD(w_value[4])), adv.SetNumber(4)])
                    EUDJump(w)
                if EUDElse()():
                    VProc([q0, dst], [q0.QueueAssignTo(EPD(_act_field(wp, 0, 20))),
                                      dst.QueueAssignTo(EPD(_act_field(wp, 0, 16))),
                                      armed.SetNumber(1), pending.SetNumber(1), adv.SetNumber(1)])
                EUDEndIf()
            EUDEndIf()
        if EUDElse()():  # 0x20~0x7F
            glyph([q0], 1)
        EUDEndIf()
    if EUDElseIf()(q0.ExactlyX(0xC0, 0xE0)):  # 2바이트 머리 (원본 버그 수정)
        if EUDIf()(lane(q1, 0)):
            EUDBreak()
        EUDEndIf()
        glyph([q0, q1], 2)
    if EUDElseIf()(q0.ExactlyX(0xF0, 0xF0)):  # 4바이트 글자 → '?'
        for k in (q1, q2, q3):
            if EUDIf()(lane(k, 0)):
                EUDBreak()
            EUDEndIf()
        RawTrigger(actions=[SetMemory(w_value[1], SetTo, ord("?") * _REP), armed.SetNumber(0), adv.SetNumber(4)])
        EUDJump(w)
    if EUDElse()():  # 3바이트 (0x80~0xBF 머리도 원본처럼 3바이트로)
        for k in (q1, q2):
            if EUDIf()(lane(k, 0)):
                EUDBreak()
            EUDEndIf()
        glyph([q0, q1, q2], 3)
    EUDEndIf()


def _classify_eudplib(q0, q1, q2, adv, w_value, w):
    def glyph(vars_, n):
        acts = [adv.SetNumber(n)]
        acts += [v.QueueAssignTo(EPD(w_value[j + 1])) for j, v in enumerate(vars_)]
        VProc(list(vars_), acts)
        EUDJump(w)

    if EUDIf()(q0.ExactlyX(0, 0xFF)):
        EUDBreak()
    if EUDElseIf()(q0.ExactlyX(0, 0x80)):  # 0x01~0x7F (제어 문자 포함)
        glyph([q0], 1)
    if EUDElseIf()(q0.ExactlyX(0xE0, 0xE0)):  # 0xE0~0xFF → 3바이트
        for k in (q1, q2):
            if EUDIf()(k.ExactlyX(0, 0xFF)):
                EUDBreak()
            EUDEndIf()
        glyph([q0, q1, q2], 3)
    if EUDElse()():  # 0x80~0xDF → 2바이트
        if EUDIf()(q1.ExactlyX(0, 0xFF)):
            EUDBreak()
        EUDEndIf()
        glyph([q0, q1], 2)
    EUDEndIf()


@functools.cache
def _ptr_split_func():
    # 주소 → (EPD, 바이트 칸). EPD = (ptr − 0x58A364) 의 부호 있는 4 나누기
    @EUDFunc
    def ptr_split(ptr):
        t = EUDVariable()
        epd = EUDVariable()
        sub = EUDVariable()
        SeqCompute([(t, SetTo, ptr), (t, Add, (-EPD0) & M32)])
        RawTrigger(actions=[epd.SetNumber(0), sub.SetNumber(0)])
        for i in range(31, 1, -1):
            RawTrigger(conditions=t.AtLeastX(1, 1 << i), actions=epd.AddNumber(1 << (i - 2)))
        RawTrigger(conditions=t.AtLeastX(1, 1 << 31), actions=epd.AddNumber(0xC0000000))
        for i in (1, 0):
            RawTrigger(conditions=t.AtLeastX(1, 1 << i), actions=sub.AddNumber(1 << i))
        return epd, sub

    return ptr_split


# --- 로컬 구역 밖 경고 (DESIGN 3.7) ---

_warned = set()
_compat.register_build_reset(_warned.clear)
_HERE = __file__.replace("\\", "/").rsplit("/", 1)[0] + "/"


def _caller_site():
    f = sys._getframe(2)
    while f is not None:
        fn = f.f_code.co_filename.replace("\\", "/")
        if "/eudplib/" not in fn and not (fn.startswith(_HERE) and "/tests/" not in fn and "/examples/" not in fn):
            return fn, f.f_lineno
        f = f.f_back
    return "?", 0


def warn_outside_local(what):
    """지금 `local.only()/begin()/allow()` 구역 밖에서 코드를 만들고 있으면 빌드 경고(EPWarning)를 낸다(호출 자리마다 한 번).

    인자: what(경고에 적을 이름)
    반환: bool — 경고를 냈으면(또는 이미 낸 자리면) True
    비용: 트리거 0
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (textfx·chat 내부용)
    출처: eudext `local._check_region`(WP13)과 같은 뜻 — 공개 API `local.f_in_region()` 으로 판정
    """
    from eudext import local

    if local.f_in_region():
        return False
    site = _caller_site()
    key = (what, site)
    if key not in _warned:
        _warned.add(key)
        warn("%s 이(가) local.only()/begin()/allow() 구역 밖에서 쓰였습니다 (%s:%d). 채팅 버퍼는 PC 마다 다른 "
             "로컬 값이라 결과로 공유 상태를 바꾸면 디싱크입니다 — 표시 전용 구역으로 감싸세요.",
             what, site[0].rsplit("/", 1)[-1], site[1])
    return True


def _check_const_range(fname, name, v, lo, hi):
    if _compat.is_var(v):
        return v
    if isinstance(v, bool) or not isinstance(v, int):
        fail("%s: %s 는 정수 상수 또는 EUDVariable 이어야 합니다 (%r)", fname, name, v)
    if not lo <= v <= hi:
        fail("%s: %s 범위 밖 %d (허용 %d ~ %d)", fname, name, v, lo, hi)
    return v


def f_scan_cells_epd(src_epd, dst_epd, max_cells, *, src_sub=0, rule="ctrig", skip_odd_head=False):
    """`f_scan_cells` 의 EPD 판: 원문 위치를 (EPD, 바이트 칸 0~3) 으로 받는다(주소 나누기가 없어 싸다).

    인자: src_epd(원문 첫 바이트가 든 dword 의 EPD — 상수·변수), dst_epd(셀 출력 EPD), max_cells(셀 한도 ≥ 0),
          src_sub(원문 첫 바이트의 dword 안 칸 0~3 — 홀수 채팅 줄은 2), rule("ctrig"|"eudplib"), skip_odd_head(bool)
    반환: EUDVariable — 쓴 셀 수
    비용: 본문 94(ctrig)·45(eudplib) — 규칙·옵션마다 1벌 / 호출 자리 1~2 / 실행: 빈 원문 101, 원문 바이트당 약 16 +
          글자당 약 10 (ASCII 글자당 26, 한글 글자당 64 — 2026-09-17, docs/COSTS.md "textfx (WP17)")
    CP: 바꾸지 않음 (안에서 잠깐 옮겨 읽고 캐시 값으로 되돌린다)
    로컬: **로컬 전용** — 로컬 분기(`local.only`/`IsUserCP`) 안에서만. 밖이면 빌드 경고
    epScript: `const n = tfx.scan_cells_epd(EPD(0x640B60), EPD(buf), 52);` (→ `f_scan_cells_epd`)
    출처: CtrigAsm `CD__ScanChat`(v5.5.lua:54918, 공용 본문 87607~88980), 모듈 docstring 의 규칙
    """
    _check_rule("scan_cells_epd", rule)
    _check_const_range("scan_cells_epd", "src_sub", src_sub, 0, 3)
    _check_const_range("scan_cells_epd", "max_cells", max_cells, 0, 0x7FFFFFFF)
    warn_outside_local("textfx.scan_cells")
    return _scanner(rule, bool(skip_odd_head))(src_epd, src_sub, dst_epd, max_cells)


def f_scan_cells(src_ptr, dst_epd, max_cells, *, rule="ctrig", skip_odd_head=False):
    """런타임 UTF-8 원문 → 글자 셀 (CtrigAsm `CD__ScanChat` 대체). 셀 배치는 eudplib, 묶음 규칙은 `rule`(모듈 docstring).

    원문은 NUL 에서 끝난다. 셀을 dst_epd 부터 연속으로 쓰고(한 셀 = dword), 최대 max_cells 개. NUL 셀은 쓰지 않는다.
    rule="ctrig" 는 반환 수 바로 뒤 칸의 가장 낮은 바이트를 바꿀 수 있다(대기 색 + 무시한 줄바꿈, 원본과 같음).
    인자: src_ptr(원문 주소 — 상수·변수·주소식), dst_epd(출력 EPD), max_cells(셀 한도 ≥ 0 — 상수·변수),
          rule("ctrig" 기본 | "eudplib"), skip_odd_head(첫 0x0D 0x0D 건너뛰기, 기본 False)
    반환: EUDVariable — 쓴 셀 수
    비용: 본문 94(ctrig)·45(eudplib) — 규칙·옵션마다 1벌 / 호출 자리 1(상수 주소)·2(변수 주소 — + 주소 나누기 본문 38, 실행 약 40) /
          실행: 빈 원문 101, 원문 바이트당 약 16 + 글자당 약 10 (ASCII 글자당 26, 한글 글자당 64 — 2026-09-17,
          docs/COSTS.md "textfx (WP17)")
    CP: 바꾸지 않음 (안에서 잠깐 옮겨 읽고 `f_setcurpl2cpcache()` 로 되돌린다)
    로컬: **로컬 전용** — 채팅 버퍼 같은 로컬 원문을 읽으므로 로컬 분기 안에서만 부른다. 밖이면 빌드 경고
    epScript: `local.begin(); const n = tfx.scan_cells(0x640B60, EPD(buf), 52); local.end();` (→ `f_scan_cells`)
    출처: CtrigAsm `CD__ScanChat`(v5.5.lua:54918), eudplib `_cpchar_addstr`(string/texteffect.py:28)
    """
    _check_rule("scan_cells", rule)
    _check_const_range("scan_cells", "max_cells", max_cells, 0, 0x7FFFFFFF)
    if isinstance(src_ptr, int) and not isinstance(src_ptr, bool):
        p = src_ptr & M32
        sub = p & 3
        epd = ((p - sub - EPD0) // 4) & M32
        warn_outside_local("textfx.scan_cells")
        return _scanner(rule, bool(skip_odd_head))(epd, sub, dst_epd, max_cells)
    if _compat.is_var(src_ptr):
        pv = src_ptr
    elif _compat.is_const(src_ptr):
        pv = EUDVariable()
        pv << src_ptr
    else:
        fail("scan_cells: src_ptr 는 주소 상수·주소식·EUDVariable 이어야 합니다 (%r)", src_ptr)
    epd, sub = _ptr_split_func()(pv)
    warn_outside_local("textfx.scan_cells")
    return _scanner(rule, bool(skip_odd_head))(epd, sub, dst_epd, max_cells)


scan_cells = f_scan_cells
scan_cells_epd = f_scan_cells_epd
