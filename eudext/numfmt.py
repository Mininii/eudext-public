"""숫자 서식 `numfmt` — `Dec`·`Hex`·`Man`·`Per`·`Gauge` 와 DisplayPrint 호환 프리셋 `numfmt.dp` (DESIGN 4.6, S3 7.4) — WP5.

    from eudext.numfmt import Dec, Hex, Man, Per, Gauge
    from eudext import numfmt

    f_sprintf(buf, "HP {}", Dec(hp, width=5, fill="0"))       # "HP 00042"  (fmt() 훅 — 패치 없음)
    sb.printf("{} 골드", Dec(gold, group=(3, ",")))          # "12,800,000,000 골드" (gold 가 Int64 면 64비트)
    f_dbstr_print(buf, Man(money, colors="dps", after=0x04))  # "<1C>1234<04>만<03>5678<04>"
    f_dbstr_print(buf, numfmt.dp.dec16(v))                    # 옛 DisplayPrint V 원소와 바이트까지 같다

epScript (`import eudext.numfmt as nf;`):

    printAll("MP {}", nf.Dec(mp, width=5, fill="0"));        // 키워드 인자는 번역된다 (DESIGN 3.11)
    printAll("{}", nf.dp.man18(gold, color=True));
    nf.enable_format_spec();                                  // 선택: "{:05d}", "{:+,d}", "{:08x}", "{:w}"

## 서식 객체 (`Dec`, `Hex`, `Man`, `Per`, `Gauge`, `numfmt.dp.*`)

- 만들 때는 트리거를 내지 않는다. **`fmt()` 를 부르는 자리**에 변환 호출(트리거 2~3)과 그 자리 전용 버퍼(Db)가 생긴다.
  eudplib 인쇄 함수(`f_dbstr_print`, `f_sprintf`, `f_cpstr_print`, `StringBuffer.print/printf/append`, `f_eprintln`,
  `printAll`)는 인자마다 `fmt()` 를 먼저 부르므로 객체를 그대로 넘기면 된다(DESIGN 3.2-7). 한 인쇄에 여러 개가 있어도
  자리마다 버퍼가 따로라 맞다. 같은 객체를 두 번 인쇄하면 호출 자리도 두 개 생긴다.
- 값은 **인쇄 순간에** 읽는다(객체를 만든 뒤 값이 바뀌어도 된다). 값이 상수면 `fmt()` 는 bytes 를 돌려준다(트리거 0).
- 실수 막기: `format(obj, …)`·f-문자열(`__format__`)과 **`f_cpchar_print`/`TextFX_*`/`StringBuffer.fadeIn` 경로**
  (eudplib 이 `fmt()` 를 부르지 않는 곳)는 안내 오류다 → 그 경로에는 `obj.fmt()` 결과를 넘긴다(R4a C.3).
  (객체는 `ptr2s` 를 상속한 표식이라 서식 문자열을 그대로 통과하고, `f_cpchar_print` 가 `_value` 를 읽는 순간 오류가 난다.)
- `max_len`: 출력 최대 바이트, `fixed_len`: 고정 길이면 그 값(아니면 None), `const_bytes()`: 값이 상수면 출력 바이트 —
  display(WP6)의 버퍼 크기 계산용.

## `Dec(v, width=0, fill="\\r", sign=None, sign_space=False, max_digits=None, cut_low=0, fullwidth=False, colors=None, group=None, glyphs=None, align=None, bits=None)`

v: `EUDVariable`·식·`EUDLightVariable`/`Cell`(인쇄 때 읽음)·정수·10진 문자열·`Int64`(64비트). 기본은 **부호 없음**
(eudplib `{}` 와 같다. display 의 맨 변수는 부호 있음 — DESIGN 7절 D17 은 display 몫).

| 옵션 | 뜻 (파이썬 `format` 과 같은 것은 바이트까지 같다) |
|---|---|
| `width` | 최소 글자 수(부호·구분자 포함). 모자라면 `fill` 로 채운다 |
| `fill` | 채움 글자 한 개. `"0"` 이면 부호 뒤를 0 으로 채운다(`{:05d}` — 구분자도 0 사이에 들어간다, `{:08,d}`). 그 밖(`"\\r"`·`" "`·`"*"`)은 부호 앞을 채운다(`{:\\r>5d}`) |
| `align` | 채움 위치를 직접: `">"`(부호 앞) / `"="`(부호 뒤). None = fill 에 따라 위와 같이 |
| `sign` | None(부호 없는 값) / `"-"`(음수만 `-`) / `"+-"`(양수 `+`) / `" -"`(양수 자리 공백, `{: d}`). 부호 있게 읽는다 |
| `sign_space` | 부호 글자 뒤에 공백 한 칸(CtrigAsm Sign=2 "부호+공백"). 부호가 보일 때만 |
| `max_digits` | 아래 m 자리만 남긴다(CtrigAsm DigitMax). 값이 더 길면 남긴 자리의 0 도 보인다: 12045, 3 → `045` |
| `cut_low` | 아래 c 자리를 `0x0D`(보이지 않음)로 바꾼다(CtrigAsm DigitMin = c+1). 길이는 그대로다 |
| `group` | `(3, ",")`·`","`·`True` = 세 자리 묶음(`{:,d}`). 구분자는 글자 한 개(만 단위는 `Man`) |
| `fullwidth` | 전각 글자 셀 `[0D][EF BC 90+d]`(CtrigAsm ItoDecX). 채움 `"\\r"` 은 `0D×4`, `" "` 은 U+3000, `"0"` 은 `０` |
| `colors` | 자리마다 색(정수 하나 = 모든 자리, 목록 = 1의 자리부터, 모자라면 0x0D). 반각이면 글자마다 `[색][숫자]` 2바이트(다른 글자는 `[0D][글자]`) |
| `glyphs` | 숫자 → 글자 표(10글자 문자열 또는 목록, 예 `"零一二三四五六七八九"`). 등차가 아니면 자리마다 트리거 9개(32비트만) |
| `bits` | 64 면 32비트 값도 64비트 배치로(0 확장) |

## `Hex(v, width=8, lower=False, fill="0")` — 32비트만(Int64 는 2차). `width=0` 이면 앞 0 없이.

## `Man(v, top=2, colors=None, after=None, units="만억조경해자양구간정재극항아나불무", fixed=False)` — 만 단위(SetNumX 일반화)

- 윗덩이 A(단위 t)와 다음 덩이 B(단위 t−1, 0 이면 숨김)만 보인다(원본 "위 두 덩이만"). `top=1` 이면 A 만.
- 배치는 덩이마다 `[색][4자리][after][단위]`(= `numfmt.dp.man18` 의 18B). 앞 0·숨긴 덩이는 `0x0D`.
  `fixed=True` 면 18B 전체와 원본 버릇(값 0 일 때 after 없음)까지 같고, `fixed=False` 면 앞의 `0x0D` 를 건너뛴다.
- colors: None / `"dps"`(S3 4.5-3 표) / 단위별 색 목록(0 = 만 미만) / 단위별 `(색1, 색2)` 목록. after: None / 색 바이트.
- v: 32비트 또는 `Int64`(단위 판정 + 64비트 비교·뺄셈 몫 — i64 나눗셈(WP4)은 쓰지 않는다).

## `Per(v, scale=1000, frac=3, max=None, trim=True, int_min=1, width=0, fill="\\r")` — SetEPer 일반화

v/scale 을 소수 frac 자리까지(아래 자리는 버림), trim 이면 뒤 0 과 점을 `0x0D` 로 가린다, 정수부 최소 int_min 자리.
scale 은 10 의 거듭제곱, frac ≤ log10(scale). max 를 넘는 값은 max 로 자른다.

## `Gauge(n, cells=20, glyph="l", on=0x07, off=0x04)` — 칸마다 `[색][glyph]`, 앞 n 칸이 on 색(GaugeBar).

## `numfmt.dp` — DisplayPrint 호환 프리셋 9개 (옛 화면과 바이트까지 같아야 할 때, S3 4.4·4.5·8.1)

`dec16(v)` V 원소 16B · `decfw48(v)` V.fwc 48B · `hex12(v)` V.hex 12B · `dec20(x64)` W 원소 20B(음수는 `-` + 19자리 0 채움) ·
`name20(p)` PName 원소 20B(0x6D0FDC 표, 0 바이트 → D, p ≥ 7 이면 쓰지 않음) · `man18(v, color=False)` SetNumX 18B ·
`per8(v, permil=False, tbl=False)` SetEPer 8B · `dig2(v)` dpletter2 2B · `gauge40(n)` GaugeBar 40B.

## 직접 쓰기·셀·읽기

- `f_fmt_dec_to(dst_ptr, value, **opts)` → 쓴 길이(NUL 없음). 고정 길이 + 상수 주소(정렬이 맞음)는 단어째 쓰고,
  그 밖은 `f_dbstr_print` 로 바이트 복사(바이트당 실행 약 30).
- `f_fmt_dec_cells(dst_epd, value, color=None, layout="eudplib", **opts)` → 쓴 칸 수. 글자당 4B 셀, 오른쪽 정렬
  (eudplib `[C][c][0D][0D]`, `layout="ctrig"` = CtrigAsm `[C][0D][0D][c]`, S6 1.7). 서식 글자 앞 칸은 빈 셀 `0D×4`.
- `f_scan_dec_cells(src_epd, n, signed=False, layout="eudplib")` → 값(CD__ScanV 대체). 칸 n 개를 읽는다:
  숫자는 이어 붙이고 `,` 는 건너뛰고, 그 밖의 글자를 만나면 처음부터 다시(= 끝에서 거꾸로 읽다 멈춤), signed 면 `-` 뒤의 수를 음수로.
- `enable_format_spec()` / `disable_format_spec()`: 선택 몽키패치 — `"{:05d}"`, `"{:+,d}"`, `"{: d}"`, `"{:08x}"`, `"{:4X}"`,
  `"{:w}"`(전각), `"{:,}"`, `Int64` 의 `"{}"` 를 Dec/Hex 로 바꾼다. `"{:x}"`(8자리 대문자)·`s t c n` 은 eudplib 그대로.

## 알고리즘과 비용 (에뮬레이터 실측, docs/COSTS.md "numfmt (WP5)", 2026-09-17)

- 공용 본문(배치별 1벌): 자릿수 판정 `[a ≥ 10^(n−1)] → 시작 = D[n−1]` 9개 + 자리값 `b·10^k`(b = 8,4,2,1) 비교·뺄셈 39개
  (나눗셈 없음, CtrigAsm ItoDec 과 같은 생각) = **본문 49(끝 트리거 포함) / 실행 48**. 배치 = (자리·구분자 위치, 글자 폭). 반각 연속·세 자리 묶음·
  전각 셀·반각 색 등은 배치마다 본문 1벌(색·채움·부호는 꼬리 몫이라 본문을 가르지 않는다). 64비트 반각 연속은 `i64` 의 10진
  본문(`i64.lidec_to` 와 같은 본문)을 반환 변수만 바꿔 부르고, 그 밖의 64비트 배치는 같은 단 표로 배치에 맞게 다시 만든다.
- 옵션 꼬리(옵션 튜플마다 1벌, EUDFunc — 반환 변수를 미리 정해 호출 자리 버퍼에 바로 쓴다): 단어 초기화 1 + (부호: 절댓값 2~6)
  + 본문 호출 + **시작 위치별 보정 트리거**(앞 채움·부호 글자·시작 포인터 중 필요한 것만, 같은 보정은 한 트리거로) + 자르기/0 가림.
- 호출 자리: 꼬리 호출 1~2 + 포인터 더하기 1, 버퍼 = 출력 최대 길이 + NUL.
- 측정(docs/COSTS.md, 3.8 목표 32비트 본문 ≤ 60 / 실행 ≤ 80, 64비트 본문 ≤ 620 / 실행 ≤ 450 — 모두 안):
  32비트 `Dec` 본문 49 / 호출 2 / 실행 60~78(꼬리 3~42), 64비트 본문 136~137 / 실행 153~175(꼬리 2~43),
  `Hex` 48 / 58~61, `Man` 32비트 실행 83~109·64비트 102~144, `Gauge(20칸)` 36, `dp.name20` 약 190.

CP: 바꾸지 않음(`f_fmt_dec_cells` 변수 주소·`f_scan_dec_cells` 는 잠깐 옮기고 캐시로 되돌림). 로컬: 작업 변수는 numfmt 전용
scratch 라 로컬 분기(StringBuffer) 안에서 불러도 된다(S3 7.1-4, 9-5).
출처: DESIGN 4.6, docs/spec/S3_display.md 4.4·4.5·7.4·8.1, docs/research/R4a_bullet_text.md C, S6 1.7,
DPS_Enhance eudplib-port a7aad90 `eud/ctrig/text.py`(`_itodec16_ops`·`_itodec48_ops`·`_itohex12_ops`·`_lidec_ops`·`_dec_digits`),
CtrigAsm v5.5.lua:58336 `ItoDec`·58911 `ItoDecX`·54357 `CD__ScanV`, DPS `CallTriggers/utils/converter.lua`(SetNumX·SetEPer).
"""

import re

from eudplib import (
    EPD,
    Add,
    AtLeast,
    AtMost,
    Condition,
    CurrentPlayer,
    Db,
    DeathsX,
    EPError,
    EUDElse,
    EUDElseIf,
    EUDEndIf,
    EUDEndWhile,
    EUDFunc,
    EUDIf,
    EUDReturn,
    EUDVariable,
    EUDWhile,
    Exactly,
    MemoryX,
    RawTrigger,
    SeqCompute,
    SetDeaths,
    SetMemory,
    SetMemoryEPD,
    SetMemoryX,
    SetTo,
    Subtract,
    f_dbstr_print,
    f_dwread_epd,
    f_setcurpl2cpcache,
    ptr2s,
    unProxy,
)

from eudext import _compat, _parts, i64
from eudext.errors import EudextError, fail

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
D = 0x0D
SIGN32 = 0x80000000
CP_ADDR = 0x6509B0
CP_PLAYER = 13  # CurrentPlayer
NAME_TABLE = 0x6D0FDC  # DPL 이름 표 (S3 4.4, DESIGN 7절 D15)
DPL_COLORS = (0x08, 0x0E, 0x0F, 0x10, 0x11, 0x15, 0x16, 0x17)  # DPL:1155 ColorCode
# S3 4.5-3 (CONV:282~300): 단위 t 의 (색1, 색2). t = 0 은 (03, 03)
DPS_MAN_COLORS = (
    (0x03, 0x03), (0x1C, 0x03), (0x1D, 0x1C), (0x19, 0x1D), (0x1B, 0x19), (0x15, 0x1B), (0x11, 0x15), (0x18, 0x11),
    (0x1E, 0x18), (0x1F, 0x1E), (0x10, 0x1F), (0x11, 0x10), (0x08, 0x11), (0x06, 0x08), (0x07, 0x06), (0x04, 0x07),
    (0x02, 0x04), (0x01, 0x02),
)  # fmt: skip
MAN_UNITS = "만억조경해자양구간정재극항아나불무"
_POOL_N = 32

__all__ = [
    "DPS_MAN_COLORS",
    "Dec",
    "Gauge",
    "Hex",
    "MAN_UNITS",
    "Man",
    "Per",
    "disable_format_spec",
    "dp",
    "enable_format_spec",
    "f_disable_format_spec",
    "f_enable_format_spec",
    "f_fmt_dec_cells",
    "f_fmt_dec_to",
    "f_format_spec_enabled",
    "f_scan_dec_cells",
    "fmt_dec_cells",
    "fmt_dec_to",
    "format_spec_enabled",
    "scan_dec_cells",
]

# 작업 변수 (numfmt 전용 scratch — 꼬리 EUDFunc 들이 반환 변수로 함께 쓴다. 재진입은 없다)
_POOL = [EUDVariable() for _ in range(_POOL_N)]
_S = EUDVariable()  # 시작 위치 (이미지 안 바이트 위치)


# =============================================================================================
# 작은 도우미
# =============================================================================================


def _u8(s):
    if isinstance(s, (bytes, bytearray)):
        return bytes(s)
    return str(s).encode("utf-8")


def _fw_char(ch):
    """반각 글자 → 전각(CtrigAsm ItoDecX·ItoX 규칙). '\\r' 은 그대로, ' ' 은 U+3000."""
    if ch == "\r":
        return "\r"
    if ch == " ":
        return "　"
    o = ord(ch)
    if 0x21 <= o <= 0x7E:
        return chr(o + 0xFEE0)
    return ch


def _flag(name, v):
    if not isinstance(v, bool):
        fail("numfmt: %s 는 True/False 여야 합니다 (%r)", name, v)
    return v


def _int(name, v, lo, hi, allow_none=False):
    if v is None and allow_none:
        return None
    v = unProxy(v)
    if isinstance(v, bool) or not isinstance(v, int):
        fail("numfmt: %s 는 정수 상수여야 합니다 (%r)", name, v)
    if not lo <= v <= hi:
        fail("numfmt: %s = %d 는 범위 밖입니다 (%d ~ %d)", name, v, lo, hi)
    return v


def _one_char(name, v):
    if isinstance(v, (bytes, bytearray)):
        v = bytes(v).decode("utf-8")
    if not isinstance(v, str) or len(v) != 1:
        fail("numfmt: %s 는 글자 한 개여야 합니다 (%r)", name, v)
    return v


def _seq(v):
    """epScript list(a, b)·파이썬 목록·튜플 → 튜플 (아니면 None)."""
    if isinstance(v, (list, tuple)):
        return tuple(unProxy(x) for x in v)
    return None


def _const_int(x):
    x = unProxy(x)
    if isinstance(x, int) and not isinstance(x, bool):
        return x
    return None


def _word_parts(pos, data, skip=()):
    """위치 pos 부터의 바이트를 단어별 {단어 번호: (값, 마스크)} 로 (skip = 뺄 바이트 순번)."""
    parts = {}
    for i, b in enumerate(data):
        if i in skip:
            continue
        wi, sh = divmod(pos + i, 4)
        val, msk = parts.get(wi, (0, 0))
        parts[wi] = (val | (b << (8 * sh)), msk | (0xFF << (8 * sh)))
    return parts


def _chunked(acts, conds=None):
    if not acts:
        if conds:
            RawTrigger(conditions=conds)
        return
    for i in range(0, len(acts), 64):
        RawTrigger(conditions=conds, actions=acts[i : i + 64])


# =============================================================================================
# 값 가르기 (만들 때 — 트리거 없음) 와 인자 만들기 (fmt() 때)
# =============================================================================================


def _classify(v, fname, bits=None):
    """→ ("c", 값, bits) | ("v", 원본, bits) | ("r", 칸, bits)(읽어야 함) | ("w", (lo, hi), 64)."""
    u = unProxy(v)
    if isinstance(u, (bool, float, Condition)) or u is None:
        fail("%s: 값으로 쓸 수 없습니다 (%r)", fname, v)
    if isinstance(u, str):
        try:
            u = i64.parse(u)
        except EPError as e:
            fail("%s: 10진 문자열이 아닙니다 (%r): %s", fname, v, e)
        if bits is None and u > M32:
            bits = 64
    if isinstance(u, int):
        if bits is None:
            bits = 64 if (u > M32 or u < -(1 << 31)) else 32
        lim = 1 << bits
        if not -(lim >> 1) <= u < lim:
            fail("%s: %d비트 범위 밖 상수 %d", fname, bits, u)
        return ("c", u & (lim - 1), bits)
    if isinstance(u, i64.Int64):
        if bits == 32:
            fail("%s: Int64 는 bits=32 로 찍을 수 없습니다", fname)
        lo, hi = unProxy(u.lo), unProxy(u.hi)
        if isinstance(lo, int) and isinstance(hi, int):
            return ("c", (lo & M32) | ((hi & M32) << 32), 64)
        return ("w", (lo, hi), 64)
    if _compat.is_var(u) or _compat.is_const(u):
        return ("v", u, bits or 32)
    if _compat.is_varbase(u) or hasattr(u, "getValueAddr"):
        return ("r", u, bits or 32)
    fail("%s: 값으로 쓸 수 없습니다 (%r) — EUDVariable·정수·Int64 를 넣으세요", fname, v)


def _args(kind):
    """fmt() 때 꼬리 인자 목록 (읽어야 하는 칸은 여기서 읽는다)."""
    tag, v, bits = kind
    if tag == "w":
        return list(v)
    if tag == "r":
        v = f_dwread_epd(EPD(v.getValueAddr()))
    return [v, 0] if bits == 64 else [v]


# =============================================================================================
# 글자 → 슬롯
# =============================================================================================


class _Render:
    """글자를 슬롯(U 바이트)으로 바꾸는 규칙.

    mode "plain": [접두(있으면)] + 글자 + 0x0D 채움.  "eudplib": [접두][글자][0D…] (4B 셀), "ctrig": [접두][0D…][글자].
    4바이트 글자는 접두 없이 그대로(색을 줄 수 없다). 접두 = 숫자면 그 자리 색, 그 밖은 0x0D. '\\r' 은 슬롯 전체 0x0D.
    """

    def __init__(self, mode, prefix, content_w, fullwidth):
        self.mode = mode
        self.prefix = prefix
        self.fullwidth = fullwidth
        self.cw = content_w
        self.U = 4 if mode != "plain" else content_w + (1 if prefix else 0)

    def key(self):
        return (self.mode, self.prefix, self.cw, self.fullwidth)

    def char(self, ch):
        if self.fullwidth:
            ch = _fw_char(ch)
        return self.slot(_u8(ch), D)

    def slot(self, content, color):
        U = self.U
        if content == b"\r":
            return bytes([D]) * U
        if len(content) == 4 and U == 4 and not (self.mode == "plain" and self.prefix):
            return content
        if self.mode == "plain":
            if len(content) > self.cw:
                fail("numfmt: 글자 %r 가 슬롯(%d바이트)보다 깁니다", content, self.cw)
            head = bytes([color & 0xFF]) if self.prefix else b""
            return (head + content).ljust(U, bytes([D]))
        if len(content) > 3:
            fail("numfmt: 4바이트 글자 %r 에는 색을 줄 수 없습니다", content)
        pad = bytes([D]) * (3 - len(content))
        return bytes([color & 0xFF]) + (content + pad if self.mode == "eudplib" else pad + content)

    def glyph_skip(self, content):
        """본문이 건드리지 않는 접두 바이트 순번."""
        if self.prefix and not (len(content) == 4 and self.U == 4):
            return (0,)
        return ()


# =============================================================================================
# 옵션 정리 (컴파일 시점)
# =============================================================================================


def _norm_sign(sign):
    if sign is None:
        return None
    table = {"-": "-", "+-": "+-", "+": "+-", " -": " -", " ": " -"}
    if sign not in table:
        fail('numfmt: sign 은 None, "-", "+-", " -" 중 하나입니다 (%r)', sign)
    return table[sign]


def _norm_group(group):
    if group is None or group is False:
        return None
    if group is True:
        return (3, ",")
    if isinstance(group, str):
        return (3, _one_char("group 구분자", group))
    t = _seq(group)
    if t is None or len(t) != 2:
        fail('numfmt: group 은 (3, ",") 모양입니다 (%r)', group)
    return (_int("group 자리 수", t[0], 1, 19), _one_char("group 구분자", t[1]))


def _norm_colors(colors, n):
    if colors is None:
        return None
    c = unProxy(colors)
    if isinstance(c, int) and not isinstance(c, bool):
        c = _int("colors", c, 0, 255)
        return tuple([c or D] * n)
    t = _seq(colors)
    if not t:
        fail("numfmt: colors 는 정수 또는 정수 목록입니다 (%r)", colors)
    out = [(_int("colors[%d]" % i, x, 0, 255) or D) for i, x in enumerate(t)]
    return tuple(out + [D] * (n - len(out)))


def _norm_glyphs(glyphs):
    if glyphs is None:
        return None
    t = tuple(glyphs) if isinstance(glyphs, str) else _seq(glyphs)
    if t is None or len(t) != 10:
        fail("numfmt: glyphs 는 글자 10개(문자열 또는 목록)여야 합니다 (%r)", glyphs)
    out = []
    for g in t:
        b = _u8(g)
        if not 1 <= len(b) <= 4 or b == b"\r":
            fail("numfmt: glyphs 의 글자 %r 는 1~4바이트여야 합니다", g)
        out.append(b)
    return tuple(out)


class _Spec:
    """숫자 서식(10진·16진·소수점) 한 벌의 컴파일 시점 옵션. key() 가 꼬리 캐시 키다."""

    _FIELDS = (
        "base", "bits", "width", "fill", "align", "sign", "sign_space", "neg_fill", "neg_align", "max_digits", "cut_low",
        "fullwidth", "group", "colors", "mode", "glyphs", "lower", "prefix", "per_s", "frac", "trim", "int_min", "max",
    )  # fmt: skip

    def key(self):
        return tuple(getattr(self, k) for k in self._FIELDS) + (self.render.key(),)

    @property
    def ndigits(self):
        if self.base == 16:
            return 8
        return 10 if self.bits == 32 else 20

    def glyph(self, d):
        if self.glyphs is not None:
            return self.glyphs[d]
        if d < 10:
            ch = chr(0x30 + d)
        else:
            ch = chr((0x61 if self.lower else 0x41) + d - 10)
        if self.fullwidth:
            ch = _fw_char(ch)
        return _u8(ch)

    def color(self, k):
        if self.colors is not None and k < len(self.colors):
            return self.colors[k]
        return D

    def digit_slot(self, k, d):
        return self.render.slot(self.glyph(d), self.color(k))

    def signed(self):
        return self.sign is not None

    def scen_list(self):
        return ("pos", "neg") if self.signed() else ("pos",)

    def scen(self, name):
        """(부호 글자 목록, fill, align, zero_style)."""
        if name == "neg":
            chars, fill, align = ["-"], self.neg_fill, self.neg_align
        else:
            chars = [] if self.sign in (None, "-") else [self.sign[0]]
            fill, align = self.fill, self.align
        if chars and self.sign_space:
            chars.append(" ")
        return chars, fill, align, (fill == "0" and align == "=")


def _make_spec(kind, bits, *, width=0, fill="\r", sign=None, sign_space=False, max_digits=None, cut_low=0,
               fullwidth=False, colors=None, group=None, glyphs=None, align=None, mode="plain", lower=False,
               neg_fill=None, neg_align=None, prefix=b"", per=None):  # fmt: skip
    s = _Spec()
    s.base = 16 if kind == "hex" else 10
    s.bits = bits
    n = s.ndigits
    s.width = _int("width", width, 0, 160)
    s.fill = _one_char("fill", fill)
    for a in (align, neg_align):
        if a is not None and a not in (">", "="):
            fail('numfmt: align 은 None, ">", "=" 입니다 (%r) — 왼쪽·가운데 정렬은 지원하지 않습니다', a)
    s.align = align if align is not None else ("=" if s.fill == "0" else ">")
    s.sign = _norm_sign(sign)
    s.sign_space = _flag("sign_space", sign_space)
    if s.sign_space and s.sign is None:
        fail("numfmt: sign_space 는 sign 과 함께 씁니다")
    s.neg_fill = s.fill if neg_fill is None else _one_char("fill", neg_fill)
    if neg_align is not None:
        s.neg_align = neg_align
    elif neg_fill is not None:
        s.neg_align = "=" if s.neg_fill == "0" else ">"
    else:
        s.neg_align = s.align
    s.max_digits = _int("max_digits", max_digits, 1, n, allow_none=True)
    if s.max_digits == n:
        s.max_digits = None
    s.cut_low = _int("cut_low", cut_low, 0, n)
    s.fullwidth = _flag("fullwidth", fullwidth)
    s.group = _norm_group(group)
    s.colors = _norm_colors(colors, n)
    if mode not in ("plain", "eudplib", "ctrig"):
        fail('numfmt: layout 은 "eudplib" 또는 "ctrig" 입니다 (%r)', mode)
    s.mode = "eudplib" if (mode == "plain" and s.fullwidth) else mode
    s.glyphs = _norm_glyphs(glyphs)
    s.lower = bool(lower)
    s.prefix = bytes(prefix)
    s.per_s, s.frac, s.trim, s.int_min, s.max = per if per is not None else (0, 0, False, 1, None)
    if kind == "hex" and (s.sign is not None or s.group is not None or s.glyphs is not None or s.colors is not None):
        fail("numfmt: Hex 는 부호·묶음·글자표·색을 쓰지 않습니다 (2차)")
    # 슬롯 폭
    digits = [s.glyph(d) for d in range(s.base)]
    cw = max(len(g) for g in digits)
    others = [s.fill, s.neg_fill, "-"] + list(s.sign or "") + ([" "] if s.sign_space else [])
    if s.group:
        others.append(s.group[1])
    if s.frac:
        others.append(".")
    for ch in others:
        if ch != "\r":
            cw = max(cw, len(_u8(_fw_char(ch) if s.fullwidth else ch)))
    has_prefix = s.colors is not None or s.mode != "plain"
    if s.mode != "plain" and cw == 4 and s.colors is not None:
        fail("numfmt: 4바이트 글자에는 색을 줄 수 없습니다")
    s.render = _Render(s.mode, has_prefix, cw, s.fullwidth)
    if s.render.U > 4:
        fail("numfmt: 글자 폭이 4바이트를 넘습니다 (색 + %d바이트 글자) — fullwidth 또는 셀 배치를 쓰세요", cw)
    if s.prefix and s.width == 0:
        fail("numfmt: 앞 고정 바이트는 고정 폭에만 씁니다")
    return s


# =============================================================================================
# 배치 (본문 영역)와 꼬리 계획
# =============================================================================================


class _Layout:
    """본문 영역(작업 단어 W 개)의 슬롯 배치. 위치는 영역 안 바이트 위치(0 = 첫 단어의 첫 바이트)."""

    def __init__(self, spec):
        N, U = spec.ndigits, spec.render.U
        s, frac, g = spec.per_s, spec.frac, spec.group
        shown = []
        for k in range(N - 1, -1, -1):
            if spec.per_s and k < s - frac:
                break
            shown.append(("d", k))
            if g and k - s > 0 and (k - s) % g[0] == 0:
                shown.append(("s",))
            if frac and k == s:
                shown.append(("dot",))
        hidden = [("d", k) for k in range(s - frac - 1, -1, -1)] if spec.per_s else []
        tail = (U + U * len(hidden)) if hidden else 0
        total = U * len(shown) + tail
        self.W = -(-total // 4)
        if self.W > _POOL_N:
            fail("numfmt: 배치가 너무 깁니다 (단어 %d개 > %d)", self.W, _POOL_N)
        self.U, self.N = U, N
        self.end = 4 * self.W - tail  # 보이는 글자 끝 (NUL 자리)
        self.first = self.end - U * len(shown)  # 첫 실제 슬롯
        self.tokens = []
        self.D = {}
        pos = self.first
        for t in shown:
            self.tokens.append((pos, t))
            if t[0] == "d":
                self.D[t[1]] = pos
            pos += U
        self.nul = self.end if hidden else None
        pos = self.end + U
        for t in hidden:
            self.tokens.append((pos, t))
            self.D[t[1]] = pos
            pos += U
        # 첫 실제 슬롯 왼쪽으로 이어지는 가상 슬롯 (0 채움 무늬: 자리 N, N+1 … 와 그 사이 구분자)
        self.virt = []
        k = N
        while len(self.virt) < 200:
            if g and k - s > 0 and (k - s) % g[0] == 0:
                self.virt.append(("s",))
            self.virt.append(("d", k))
            k += 1

    def body_key(self, spec):
        """본문을 가르는 키: 자리 위치, 슬롯 규칙, 글자표 (색·채움·부호는 꼬리 몫)."""
        return (spec.base, spec.bits, self.W, tuple(sorted(self.D.items())), spec.render.key(), spec.glyphs, spec.lower)


def _put(img, pos, data, base):
    img[pos - base : pos - base + len(data)] = data


class _Plan:
    """옵션 한 벌의 꼬리 계획(파이썬 값). 트리거 생성과 상수 서식(파이썬 흉내)이 같이 쓴다."""

    def __init__(self, spec):
        self.spec = spec
        self.lay = _Layout(spec)
        E = 0
        for _ in range(8):
            self._build(E)
            if self.min_start >= 0:
                break
            E += -(self.min_start // 4)  # 올림 (min_start 는 음수)
        if self.min_start < 0:  # pragma: no cover
            fail("numfmt: 배치 계산 실패 (%d)", self.min_start)

    def _build(self, E):
        spec, lay = self.spec, self.lay
        U, N = lay.U, lay.N
        self.E = E
        off = self.off = 4 * E
        self.T = off + 4 * lay.W
        self.END = off + lay.end
        self.D = {k: off + p for k, p in lay.D.items()}
        grid = {}
        for p, t in lay.tokens:
            if p < lay.end:
                grid[off + p] = ("real", t)
        q = off + lay.first - U
        for t in lay.virt:
            if q < -800:
                break
            grid[q] = ("virt", t)
            q -= U
        self.grid = grid
        # 가능한 자릿수와 첫 유효 자리 위치 F
        n_max = N
        if spec.bits == 64 and spec.signed():
            n_max = 19
        if spec.max is not None:
            n_max = min(n_max, len(str(spec.max)))
        self.n_min = min(spec.per_s + spec.int_min, N) if spec.per_s else 1
        self.n_top = min(n_max, spec.max_digits) if spec.max_digits else n_max
        self.Fs = sorted({self.F_of(n) for n in range(1, n_max + 1)})
        # 초기 이미지
        _chars, pos_fill, _align, pos_zero = spec.scen("pos")
        lo = min(0, min(grid))
        self.img_base = lo
        img = bytearray([D]) * (self.T - lo)
        for q, (kind, t) in grid.items():
            if kind == "real" or pos_zero:
                _put(img, q, self.zero_content(t), lo)
            else:
                _put(img, q, spec.render.char(pos_fill), lo)
        for p, t in lay.tokens:
            if p >= lay.end:
                _put(img, off + p, self.zero_content(t), lo)
        if lay.nul is not None:
            _put(img, off + lay.nul, bytes(U), lo)
        self.init_full = img
        # 상황별 보정
        self.disp = {}
        self.min_start = None
        starts = set()
        for sc in spec.scen_list():
            groups = []
            for F in self.Fs:
                acts, S_new = self._fix(sc, F)
                starts.add(S_new)
                low = S_new - len(spec.prefix)
                self.min_start = low if self.min_start is None else min(self.min_start, low)
                groups.append((F, acts, S_new))
            self.disp[sc] = groups
        self.fixed = len(starts) == 1
        self.start_const = next(iter(starts)) - len(spec.prefix) if self.fixed else None
        if spec.prefix:
            if not self.fixed:
                fail("numfmt: 앞 고정 바이트는 출력 길이가 고정일 때만 씁니다")
            pos = self.start_const
            if pos >= 0:
                _put(img, pos, spec.prefix, lo)

    def F_of(self, n):
        return self.D[max(min(n, self.n_top), self.n_min) - 1]

    def zero_content(self, t):
        spec = self.spec
        if t[0] == "d":
            return spec.digit_slot(t[1], 0)
        if t[0] == "s":
            return spec.render.char(spec.group[1])
        return spec.render.char(".")

    def _zero_at(self, q):
        return self.zero_content(self.grid[q][1])

    def _is_sep(self, q):
        g = self.grid.get(q)
        return g is not None and g[1][0] == "s"

    def _fix(self, sc, F):
        """첫 유효 자리 위치 F 에서 [S, F) 에 쓸 바이트 {위치: 바이트} 와 새 시작 S."""
        spec = self.spec
        U = self.lay.U
        chars, fill, align, zero = spec.scen(sc)
        sg = len(chars) * U
        w = spec.width * U
        targets = {}
        zdigit = set()  # 0 채움으로 들어간 자리 슬롯 (cut_low 대상)
        if align == ">":
            S = min(F - sg, self.END - w)
            for i, ch in enumerate(chars):
                targets[F - sg + i * U] = spec.render.char(ch)
            for q in range(S, F - sg, U):
                targets[q] = spec.render.char(fill)
        else:
            R = min(F, self.END - (w - sg)) if w > sg else F
            if zero and R < F and self._is_sep(R):
                R -= U
            S = R - sg
            for i, ch in enumerate(chars):
                targets[S + i * U] = spec.render.char(ch)
            for q in range(R, F, U):
                if zero:
                    targets[q] = self._zero_at(q)
                    if self.grid[q][1][0] == "d":
                        zdigit.add(q)
                else:
                    targets[q] = spec.render.char(fill)
        blank = bytes([D]) * U
        if spec.mode != "plain":  # 셀 배치: 시작 위치 앞 칸은 모두 빈 셀 (f_fmt_dec_cells 가 이미지 전체를 쓴다)
            for q in range(S - U, -1, -U):
                targets.setdefault(q, blank)
        # 아래 자리 가림 (cut_low): 보이는 자리(F 오른쪽)와 0 채움 자리만 — 부호·채움 글자는 두고
        for k in range(min(spec.cut_low, self.lay.N)):
            q = self.D[k]
            if q >= F or q in zdigit:
                targets[q] = blank
        unknown = set(range(F, self.T))  # F 오른쪽은 자리 글자가 들어가 있다
        m = spec.max_digits
        if m and F == self.D[m - 1]:
            for k in range(m, self.lay.N):
                unknown.update(range(self.D[k], self.D[k] + U))
        acts = {}
        for q, data in targets.items():
            for i, b in enumerate(data):
                p = q + i
                if p < 0 or p in unknown or self.init_full[p - self.img_base] != b:
                    acts[p] = b
        return acts, S

    # ---- 트리거가 쓰는 부분표 ----
    def trim_slots(self):
        """(점 위치, [소수 자리 k — 보이는 가장 아래부터]) 또는 None."""
        spec = self.spec
        if not (spec.trim and spec.frac):
            return None
        dot = next(p for p, t in self.lay.tokens if t[0] == "dot") + self.off
        return dot, list(range(spec.per_s - spec.frac, spec.per_s))

    # ---- 파이썬 흉내 (상수 서식·자체 시험) ----
    def image(self, value):
        """값 → (이미지 바이트 [0, T), 시작 위치 S). 트리거가 만드는 것과 같다."""
        spec = self.spec
        bits = spec.bits
        mask = (1 << bits) - 1
        v = value & mask
        neg = bool(spec.signed() and v >> (bits - 1))
        a = ((1 << bits) - v) & mask if neg else v
        if spec.max is not None:
            a = min(a, spec.max)
        N = self.lay.N
        digits = []
        x = a
        for _ in range(N):
            digits.append(x % spec.base)
            x //= spec.base
        n = max([k + 1 for k in range(N) if digits[k]] + [1])
        img = bytearray(self.init_full)
        b0 = self.img_base
        for k in range(n):
            _put(img, self.D[k], spec.digit_slot(k, digits[k]), b0)
        F = self.F_of(n)
        S = None
        for F2, acts, S_new in self.disp["neg" if neg else "pos"]:
            if F2 == F:
                for p, b in acts.items():
                    img[p - b0] = b
                S = S_new
        ts = self.trim_slots()
        if ts is not None:
            dot, ks = ts
            U = self.lay.U
            blank = bytes([D]) * U
            ok = True
            for k in ks:
                q = self.D[k] - b0
                if ok and bytes(img[q : q + U]) == spec.digit_slot(k, 0):
                    img[q : q + U] = blank
                else:
                    ok = False
            if ok:
                img[dot - b0 : dot - b0 + U] = blank
        if self.fixed:
            S = self.start_const
        return bytes(img[-b0 : self.T - b0]), S

    def simulate(self, value):
        img, S = self.image(value)
        return img[S : self.END]

    @property
    def max_len(self):
        return self.END - self.min_start

    @property
    def fixed_len(self):
        return self.END - self.start_const if self.fixed else None


_plans = {}


def _plan(spec):
    key = spec.key()
    p = _plans.get(key)
    if p is None:
        p = _plans[key] = _Plan(spec)
    return p


# =============================================================================================
# 트리거 생성 도우미
# =============================================================================================


def _word_var(E, extra, wi):
    return extra[wi] if wi < E else _POOL[wi - E]


def _byte_actions(E, extra, targets):
    """{위치: 바이트} → 단어별 마스크 SetTo 액션 (전체 단어면 SetNumber)."""
    words = {}
    for p, b in targets.items():
        wi, sh = divmod(p, 4)
        val, msk = words.get(wi, (0, 0))
        words[wi] = (val | (b << (8 * sh)), msk | (0xFF << (8 * sh)))
    out = []
    for wi in sorted(words):
        val, msk = words[wi]
        var = _word_var(E, extra, wi)
        if msk == M32:
            out.append(var.SetNumber(val))
        else:
            out.append(SetMemoryX(var.getValueAddr(), SetTo, val, msk))
    return out


def _byte_conds(E, extra, targets):
    """{위치: 바이트} → 단어별 마스크 Exactly 조건."""
    words = {}
    for p, b in targets.items():
        wi, sh = divmod(p, 4)
        val, msk = words.get(wi, (0, 0))
        words[wi] = (val | (b << (8 * sh)), msk | (0xFF << (8 * sh)))
    return [MemoryX(_word_var(E, extra, wi).getValueAddr(), Exactly, val, msk) for wi, (val, msk) in sorted(words.items())]


# =============================================================================================
# 공용 본문 (배치마다 1벌)
# =============================================================================================

_bodies = {}


def _digit_steps(spec, lay, k):
    """자리 k 의 글자가 등차면 (단어 번호, 1 증가분, 16진 글자 보정, 0 글자 값, 바뀌는 바이트 마스크) — 아니면 None."""
    pos = lay.D[k]
    nd = spec.base
    parts = []
    for d in range(nd):
        g = spec.glyph(d)
        slot = spec.render.slot(g, D)
        parts.append(_word_parts(pos, slot, spec.render.glyph_skip(g)))
    varying = [wi for wi in parts[0] if any(parts[d].get(wi) != parts[0][wi] for d in range(nd))]
    if len(varying) != 1 or any(set(p) != set(parts[0]) for p in parts):
        return None
    wi = varying[0]
    v = [parts[d][wi][0] for d in range(nd)]
    step = v[1] - v[0]
    if any(v[d] - v[0] != d * step for d in range(10)):
        return None
    adj = 0
    if nd == 16:
        if any(v[d] - v[10] != (d - 10) * step for d in range(10, 16)):
            return None
        adj = v[10] - v[9] - step
    vmask = 0
    for d in range(nd):
        vmask |= v[d] ^ v[0]
    bmask = 0
    for sh in range(4):
        if vmask & (0xFF << (8 * sh)):
            bmask |= 0xFF << (8 * sh)
    return wi, step, adj, v[0] & bmask, bmask


def _dec_bits(k, bits, base):
    """자리 k 에서 비교할 비트 (32비트 10^9 자리는 4·2·1)."""
    if base == 10 and bits == 32 and k == 9:
        return (4, 2, 1)
    return (8, 4, 2, 1)


def _body32(spec, lay):
    """32비트 본문: a(소모) → _S = D[n−1] (꼬리가 D[0] 으로 초기화), 자리 글자를 _POOL 단어에 더한다(등차) / 넣는다(등차 아님).

    비용: 등차 = 트리거 (자릿수−1) + 비교·뺄셈 39(16진 40) = 48(47) / 등차 아님 = 9 + 자리마다 1~9.
    출처: CtrigAsm ItoDec(CA:58448~58608 비교·뺄셈 39), DPS_Enhance eudplib-port a7aad90 text.py:235 `_dec_digits`
    """
    key = ("b32",) + lay.body_key(spec)
    f = _bodies.get(key)
    if f is not None:
        return f
    steps = {k: _digit_steps(spec, lay, k) for k in range(lay.N)}
    linear = all(s is not None for s in steps.values())
    base, N = spec.base, lay.N

    def body(a):
        for n in range(2, N + 1):
            RawTrigger(conditions=a.AtLeast(base ** (n - 1)), actions=_S.SetNumber(lay.D[n - 1]))
        for k in range(N - 1, -1, -1):
            p = base**k
            if linear:
                wi, step, adj, _z, _m = steps[k]
                var = _POOL[wi]
                if base == 16:
                    RawTrigger(conditions=a.AtLeast(10 * p), actions=var.AddNumber(adj & M32))
                for b in _dec_bits(k, 32, base):
                    RawTrigger(
                        conditions=a.AtLeast(b * p),
                        actions=[a.SubtractNumber(b * p), var.AddNumber((b * step) & M32)],
                    )
                continue
            for d in range(min(base - 1, M32 // p), 0, -1):
                g = spec.glyph(d)
                parts = _word_parts(lay.D[k], spec.render.slot(g, D), spec.render.glyph_skip(g))
                acts = [a.SubtractNumber(d * p)]
                for wi, (val, msk) in sorted(parts.items()):
                    acts.append(SetMemoryX(_POOL[wi].getValueAddr(), SetTo, val, msk))
                RawTrigger(conditions=a.AtLeast(d * p), actions=acts)

    body.__name__ = "numfmt_body32"
    f = _bodies[key] = EUDFunc(body)
    return f


def _steps64():
    """64비트 10진 단 표 (i, b, c, 값이 2^32 미만인가). 단 시작 때 값 < 2c.

    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/text.py:381 `_lidec_ops`, eudext.i64 `_lidec_steps`/`_lidec_code`
    (배타 트리거 둘: 빌림 없음 [hi ≥ ch ∧ lo ≥ cl] / 빌림 [hi ≥ ch+1 ∧ lo < cl]).
    """
    out = []
    for i in range(19, -1, -1):
        for b in (8, 4, 2, 1):
            c = b * 10**i
            if c <= M64:
                out.append((i, b, c, 2 * c - 1 <= M32))
    return out


def _sub64_const(lo, hi, c, hizero, extra_acts):
    """값 ≥ c 이면 c 를 빼고 extra_acts 를 한다 (단 시작 때 값 < 2c 전제). 트리거 1~2."""
    cl, ch = c & M32, c >> 32
    if hizero:
        RawTrigger(conditions=lo.AtLeast(cl), actions=[lo.SubtractNumber(cl)] + extra_acts())
        return
    conds = ([hi.AtLeast(ch)] if ch else []) + ([lo.AtLeast(cl)] if cl else [])
    acts = ([lo.SubtractNumber(cl)] if cl else []) + ([hi.SubtractNumber(ch)] if ch else [])
    RawTrigger(conditions=conds, actions=acts + extra_acts())
    if cl and ch < M32:
        RawTrigger(
            conditions=[hi.AtLeast(ch + 1), lo.AtMost(cl - 1)],
            actions=[hi.SubtractNumber(ch + 1), lo.AddNumber((-cl) & M32)] + extra_acts(),
        )


def _body64(spec, lay):
    """64비트 본문(배치 일반): lo·hi(소모) → 자리 글자를 _POOL 에 더하고, 뒤에서 _S 를 첫 유효 자리로 옮긴다
    (꼬리가 _S = D[19] 로 초기화). 비용: 약 116 + 19."""
    key = ("b64",) + lay.body_key(spec)
    f = _bodies.get(key)
    if f is not None:
        return f
    steps = {k: _digit_steps(spec, lay, k) for k in range(lay.N)}
    if not all(s is not None for s in steps.values()):
        fail("numfmt: 64비트 값에는 등차가 아닌 glyphs 를 쓸 수 없습니다 (2차)")

    def body(lo, hi):
        for i, b, c, hizero in _steps64():
            wi, step, _adj, _z, _m = steps[i]
            _sub64_const(lo, hi, c, hizero, lambda wi=wi, v=(b * step) & M32: [_POOL[wi].AddNumber(v)])
        for k in range(lay.N - 1, 0, -1):
            wi, _step, _adj, zval, zmask = steps[k]
            RawTrigger(
                conditions=[_S.Exactly(lay.D[k]), MemoryX(_POOL[wi].getValueAddr(), Exactly, zval, zmask)],
                actions=_S.SetNumber(lay.D[k - 1]),
            )

    body.__name__ = "numfmt_body64"
    f = _bodies[key] = EUDFunc(body)
    return f


def _i64_plain(spec, lay):
    """64비트 반각 연속 배치이면 i64 의 10진 본문(`i64.lidec_to` 와 같은 본문)을 반환 변수만 바꿔 쓴다."""
    if spec.bits != 64 or spec.base != 10 or lay.W != 5 or lay.U != 1 or lay.nul is not None:
        return None
    if spec.render.prefix or spec.glyphs is not None or spec.fullwidth:
        return None
    if any(lay.D[k] != 19 - k for k in range(20)):
        return None
    return getattr(i64, "_lidec_body", None)


# =============================================================================================
# 옵션 꼬리 (옵션 튜플마다 1벌)
# =============================================================================================

_tails = {}


def _tail(spec):
    """→ (꼬리 EUDFunc, 계획, 본문). 꼬리 인자 = 32비트 (x) / 64비트 (lo, hi), 반환 = 덧붙인 단어 + 본문 단어 + 시작 위치."""
    key = spec.key()
    t = _tails.get(key)
    if t is not None:
        return t
    plan = _plan(spec)
    lay = plan.lay
    E = plan.E
    extra = [EUDVariable() for _ in range(E)]
    i64body = _i64_plain(spec, lay)
    body = None
    if i64body is None:
        body = _body32(spec, lay) if spec.bits == 32 else _body64(spec, lay)

    def word(i):
        q = 4 * i - plan.img_base
        return int.from_bytes(plan.init_full[q : q + 4], "little")

    def emit(args):
        # 1. 초기화
        init = [extra[i].SetNumber(word(i)) for i in range(E)]
        if i64body is None:
            init += [_POOL[j].SetNumber(word(E + j)) for j in range(lay.W)]
            init.append(_S.SetNumber(lay.D[0] if spec.bits == 32 else lay.D[lay.N - 1]))
        _chunked(init)
        # 2. 최댓값 자르기 (Per)
        if spec.max is not None:
            if spec.bits == 32:
                RawTrigger(conditions=args[0].AtLeast(spec.max + 1), actions=args[0].SetNumber(spec.max))
            else:
                x = i64.Int64.wrap(args[0], args[1])
                if EUDIf()(i64.gt(x, spec.max)):
                    x.assign(spec.max)
                EUDEndIf()

        def run(body_args, scen):
            # 본문 → 위치 보정 → 윗자리 자르기·정수부 최소 자리 → 시작 위치별 보정
            if i64body is not None:
                i64body(body_args[0], body_args[1], ret=_POOL[:5] + [_S])
            else:
                body(*body_args)
            if plan.off:
                RawTrigger(actions=_S.AddNumber(plan.off))
            if spec.max_digits and plan.n_top < lay.N:
                top = plan.D[plan.n_top - 1]
                RawTrigger(conditions=_S.AtMost(top - 1), actions=_S.SetNumber(top))
            if plan.n_min > 1:
                lowF = plan.D[plan.n_min - 1]
                RawTrigger(conditions=_S.AtLeast(lowF + 1), actions=_S.SetNumber(lowF))
            _emit_disp(plan, extra, plan.disp[scen])

        # 3. 부호: 음수면 절댓값으로 본문을 부르고 음수 보정, 아니면 그대로
        if spec.signed():
            if spec.bits == 32:
                x = args[0]
                if EUDIf()(x.AtLeast(SIGN32)):
                    t = EUDVariable()
                    SeqCompute([(t, SetTo, M32), (t, Subtract, x), (t, Add, 1)])  # −x = ~x + 1 (3.5-7)
                    run([t], "neg")
                if EUDElse()():
                    run(args, "pos")
                EUDEndIf()
            else:
                if EUDIf()(args[1].AtLeast(SIGN32)):
                    i64.Int64.wrap(args[0], args[1]).ineg()
                    run(args, "neg")
                if EUDElse()():
                    run(args, "pos")
                EUDEndIf()
        else:
            run(args, "pos")
        # 4. 뒤 0 가림, 고정 시작 위치 (아래 자리 가림은 3 의 보정에 들어 있다)
        ts = plan.trim_slots()
        if ts is not None:
            dot, ks = ts
            U = lay.U
            blank = [D] * U
            prev = None
            for k in ks:
                q = plan.D[k]
                conds = _byte_conds(E, extra, dict(zip(range(q, q + U), spec.digit_slot(k, 0))))
                if prev is not None:
                    conds += _byte_conds(E, extra, dict(zip(range(prev, prev + U), blank)))
                RawTrigger(conditions=conds, actions=_byte_actions(E, extra, dict(zip(range(q, q + U), blank))))
                prev = q
            RawTrigger(
                conditions=_byte_conds(E, extra, dict(zip(range(prev, prev + U), blank))),
                actions=_byte_actions(E, extra, dict(zip(range(dot, dot + U), blank))),
            )
        if plan.fixed:
            RawTrigger(actions=_S.SetNumber(plan.start_const))

    if spec.bits == 32:

        def fn(x):
            emit([x])

    else:

        def fn(lo, hi):
            emit([lo, hi])

    fn.__name__ = "numfmt_tail"
    f = EUDFunc(fn)
    _compat.predefine_returns(f, extra + _POOL[: lay.W] + [_S])
    t = _tails[key] = (f, plan, body if body is not None else i64body)
    return t


def _emit_disp(plan, extra, groups):
    """(F, 바이트, 새 S) 목록 → 같은 보정이 이어지는 F 끼리 묶고, 묶음이 많으면 F 범위를 반으로 나눠 분기한다.

    한 가지 안에서는 F 오름차순으로 놓는다. S 는 보정 뒤 늘 F 이하라(왼쪽으로만 옮김) 뒤 트리거의 범위에 다시 걸리지 않는다.
    실행 = 분기 깊이 + 잎의 묶음 수 (묶음 10개 → 약 4~5).
    """
    items = []
    for F, acts, S_new in groups:
        sact = None if (plan.fixed or S_new == F) else S_new - F
        items.append((F, tuple(sorted(acts.items())), sact))
    merged = []
    for F, acts, sact in items:
        if merged and merged[-1][2] == acts and merged[-1][3] == sact:
            merged[-1][1] = F
        else:
            merged.append([F, F, acts, sact])
    lo_all, hi_all = items[0][0], items[-1][0]
    _disp_tree(plan, extra, merged, lo_all, hi_all)


def _disp_tree(plan, extra, merged, lo_all, hi_all):
    live = [i for i, g in enumerate(merged) if g[2] or g[3] is not None]
    if not live:
        return
    if len(live) > 3:
        mid = live[len(live) // 2]  # 위쪽 가지의 첫 묶음 (양쪽에 보정 묶음이 2개 이상)
        split = merged[mid][0]
        if EUDIf()(_S.AtLeast(split)):
            _disp_tree(plan, extra, merged[mid:], split, hi_all)
        if EUDElse()():
            _disp_tree(plan, extra, merged[:mid], lo_all, merged[mid - 1][1])
        EUDEndIf()
        return
    for lo, hi, acts, sact in merged:
        if not acts and sact is None:
            continue
        actions = _byte_actions(plan.E, extra, dict(acts))
        if sact is not None:
            actions.append(_S.AddNumber(sact & M32))
        if lo == hi:
            conds = [_S.Exactly(lo)]
        else:
            conds = ([_S.AtLeast(lo)] if lo > lo_all else []) + ([_S.AtMost(hi)] if hi < hi_all else [])
        _chunked(actions, conds)


# =============================================================================================
# 서식 객체
# =============================================================================================

_GUIDE = (
    "numfmt: 이 객체는 fmt() 를 부르는 인쇄 함수(f_dbstr_print·f_sprintf·StringBuffer.print/printf·printAll 등)에만 "
    "그대로 넘길 수 있습니다. f_cpchar_print·TextFX_*·StringBuffer.fadeIn 등에는 obj.fmt() 결과를 넘기세요 (R4a C.3)"
)


class _Fmt(ptr2s):
    """서식 객체의 기반 (eudplib `ptr2s` 표식을 상속 — 서식 문자열을 그대로 통과한다).

    `fmt()` 가 이 자리에 변환 트리거와 버퍼를 만들고 진짜 `ptr2s`(또는 상수 bytes)를 돌려준다.
    """

    dont_flatten = True

    def __init__(self):  # ptr2s.__init__ 을 부르지 않는다 (_value 는 안내 오류)
        pass

    @property
    def _value(self):
        raise EudextError(_GUIDE)

    def __format__(self, spec):
        raise EudextError('numfmt: format()/f-문자열은 쓸 수 없습니다. f_sprintf(buf, "{}", obj) 나 obj.fmt() 를 쓰세요')

    def __bool__(self):
        raise EudextError("numfmt: 서식 객체는 조건으로 쓸 수 없습니다")

    def __iter__(self):
        raise TypeError("numfmt 서식 객체는 펼칠 수 없습니다")

    def __repr__(self):
        return "<eudext.numfmt.%s — 인쇄 함수에 넘기거나 .fmt() (epScript 는 const 로)>" % type(self).__name__

    @property
    def max_len(self):
        """출력 최대 바이트 수(NUL 제외)."""
        return self._max_len()

    @property
    def fixed_len(self):
        """출력 길이가 늘 같으면 그 값, 아니면 None."""
        return self._fixed_len()

    def const_bytes(self):
        """값이 상수면 출력 바이트(트리거 0), 아니면 None."""
        return None

    def fmt(self):  # pragma: no cover — 하위 클래스
        raise NotImplementedError

    def _emit_buf(self, nwords, call):
        """호출 자리 버퍼(단어 nwords + NUL)를 만들고 call(dests) 로 채운 뒤 ptr2s 를 돌려준다."""
        buf = Db(4 * nwords + 4)
        p = EUDVariable()
        call([EPD(buf) + i for i in range(nwords)] + [p])
        RawTrigger(actions=p.AddNumber(buf))
        return ptr2s(p)


class _NumFmt(_Fmt):
    """Dec·Hex·Per 공통."""

    def __init__(self, kind, spec):
        super().__init__()
        self._kind = kind
        self._spec = spec

    def _plan(self):
        return _plan(self._spec)

    def _max_len(self):
        return self._plan().max_len

    def _fixed_len(self):
        return self._plan().fixed_len

    def const_bytes(self):
        if self._kind[0] != "c":
            return None
        return self._plan().simulate(self._kind[1])

    def _call(self, dests):
        f, _plan_, _body = _tail(self._spec)
        f(*_args(self._kind), ret=dests)

    def fmt(self):
        """이 자리 버퍼(출력 최대 길이 + NUL)에 서식 문자열을 쓰고 `ptr2s` 를 돌려준다. 상수 값은 bytes(트리거 0).

        비용: 호출 2 (꼬리 호출 1 + 포인터 1) / 실행 = 본문 + 꼬리 (docs/COSTS.md). CP: 바꾸지 않음.
        """
        c = self.const_bytes()
        if c is not None:
            return c
        plan = self._plan()
        return self._emit_buf(plan.E + plan.lay.W, self._call)


class Dec(_NumFmt):
    """10진 서식 객체 (모듈 docstring 의 옵션 표).

    인자: v(EUDVariable·식·정수·10진 문자열·Int64·EUDLightVariable), width, fill, sign, sign_space, max_digits, cut_low,
          fullwidth, colors, group, glyphs, align, bits(None | 32 | 64)
    반환: 서식 객체 (인쇄 함수에 넘기거나 .fmt())
    비용: 본문 49(32비트 배치당 1벌) — 64비트 반각 연속은 i64 본문 137 공유, 그 밖 64비트 배치 136 / 꼬리 3~43(옵션마다) /
          호출 2 / 실행 32비트 60~78, 64비트 153~175 (2026-09-17, docs/COSTS.md "numfmt (WP5)")
    CP: 바꾸지 않음
    로컬: 공유 안전 (작업 변수는 numfmt 전용 — 로컬 분기에서 불러도 된다)
    epScript: `printAll("MP {}", nf.Dec(mp, width=5, fill="0"));`
    출처: CtrigAsm ItoDec/ItoDecX/CA__ItoCustom, DPS_Enhance eudplib-port a7aad90 text.py `_itodec16_ops`·`_itodec48_ops`
    """

    def __init__(self, v, width=0, fill="\r", sign=None, sign_space=False, max_digits=None, cut_low=0, fullwidth=False,
                 colors=None, group=None, glyphs=None, align=None, bits=None, _mode="plain", _neg_fill=None,
                 _neg_align=None, _prefix=b""):  # fmt: skip
        if bits not in (None, 32, 64):
            fail("Dec: bits 는 None, 32, 64 입니다 (%r)", bits)
        kind = _classify(v, "Dec", bits)
        spec = _make_spec(
            "dec", kind[2], width=width, fill=fill, sign=sign, sign_space=sign_space, max_digits=max_digits,
            cut_low=cut_low, fullwidth=fullwidth, colors=colors, group=group, glyphs=glyphs, align=align, mode=_mode,
            neg_fill=_neg_fill, neg_align=_neg_align, prefix=_prefix,
        )  # fmt: skip
        super().__init__(kind, spec)


class Hex(_NumFmt):
    """16진 서식 객체 (32비트).

    인자: v(32비트 값), width(최소 자리 수, 기본 8), lower(소문자), fill(기본 "0" — 0 채움), align
    반환: 서식 객체
    비용: 본문 48(16진 배치 1벌) / 꼬리 3~5 / 호출 2 / 실행 58~61 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `printAll("{}", nf.Hex(v, width=4));`
    출처: CtrigAsm ItoHex, DPS_Enhance eudplib-port a7aad90 text.py:329 `_itohex12_ops`(니블 비교·뺄셈 + '9' 다음 글자 보정 —
          여기서는 니블을 뽑기 전에 `a ≥ 10·16^k` 로 보정해 마스크 조건을 쓰지 않는다)
    """

    def __init__(self, v, width=8, lower=False, fill="0", align=None, _prefix=b""):
        if isinstance(unProxy(v), i64.Int64):
            fail("Hex: Int64 는 2차입니다 — 지금은 32비트 값만 됩니다")
        kind = _classify(v, "Hex", 32)
        spec = _make_spec("hex", 32, width=width, fill=fill, align=align, lower=_flag("lower", lower), prefix=_prefix)
        super().__init__(kind, spec)


class Per(_NumFmt):
    """소수점 서식 (SetEPer 일반화): v/scale 을 소수 frac 자리까지.

    인자: v(32비트 또는 Int64, 부호 없음), scale(10 의 거듭제곱, 기본 1000), frac(0 ~ log10(scale)), max(자를 최댓값),
          trim(뒤 0·점 가림 — 0x0D), int_min(정수부 최소 자리), width/fill(앞 채움, dp.per8 이 씀)
    반환: 서식 객체
    비용: 본문 49(배치 1벌) / 꼬리 8~13 / 호출 2 / 실행 65~70 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `printAll("확률 {}%", nf.Per(p, max=100000));`
    출처: DPS CallTriggers/utils/converter.lua:59~95·431~458 (SetEPerSTRX/TBLX), S3 4.5
    """

    def __init__(self, v, scale=1000, frac=3, max=None, trim=True, int_min=1, width=0, fill="\r"):  # noqa: A002
        scale = _int("Per scale", scale, 1, 10**19)
        s = len(str(scale)) - 1
        if 10**s != scale:
            fail("Per: scale 은 10 의 거듭제곱이어야 합니다 (%d)", scale)
        kind = _classify(v, "Per", 64 if isinstance(unProxy(v), i64.Int64) else None)
        N = 10 if kind[2] == 32 else 20
        if s >= N:
            fail("Per: scale 이 너무 큽니다 (%d)", scale)
        frac = _int("Per frac", frac, 0, s)
        if s == 0:
            fail("Per: scale 1 은 Dec 를 쓰세요")
        per = (s, frac, _flag("trim", trim), _int("Per int_min", int_min, 1, N - s),
               None if max is None else _int("Per max", max, 0, (1 << kind[2]) - 1))  # fmt: skip
        spec = _make_spec("dec", kind[2], width=width, fill=fill, per=per)
        super().__init__(kind, spec)


# =============================================================================================
# Gauge
# =============================================================================================

_gauges = {}


class Gauge(_Fmt):
    """막대 (GaugeBar): 칸마다 `[색][glyph]`, 앞 n 칸은 on 색, 나머지는 off 색.

    인자: n(32비트 값 — cells 이상이면 모두 on), cells(칸 수 1~60), glyph(글자 1개, 1~3바이트), on/off(색 바이트)
    반환: 서식 객체 (고정 길이 cells × (1 + glyph 바이트))
    비용: 꼬리 = 칸 수 + 2 (옵션마다 1벌, 20칸 22) / 호출 2 / 실행 = 칸 수 + 약 16 (20칸 36)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `printAll("{}", nf.Gauge(hp_percent / 5));`
    출처: DPS function.lua:2378~2410 (GaugeBar·GaugeBarTbl), S3 4.5
    """

    def __init__(self, n, cells=20, glyph="l", on=0x07, off=0x04):
        super().__init__()
        self._cells = _int("Gauge cells", cells, 1, 60)
        g = _u8(_one_char("Gauge glyph", glyph))
        if len(g) > 3:
            fail("Gauge: glyph 는 1~3바이트 글자입니다 (%r)", glyph)
        self._glyph = g
        self._on = _int("Gauge on", on, 0, 255)
        self._off = _int("Gauge off", off, 0, 255)
        self._kind = _classify(n, "Gauge", 32)
        self._U = 1 + len(g)
        self._T = self._U * self._cells
        self._W = -(-self._T // 4)
        if self._W > _POOL_N:
            fail("Gauge: 너무 깁니다")
        self._pad = 4 * self._W - self._T

    def _max_len(self):
        return self._T

    def _fixed_len(self):
        return self._T

    def simulate(self, n):
        out = b""
        for i in range(self._cells):
            out += bytes([self._on if n > i else self._off]) + self._glyph
        return out

    def const_bytes(self):
        return self.simulate(self._kind[1]) if self._kind[0] == "c" else None

    def _tail(self):
        key = (self._cells, self._glyph, self._on, self._off)
        f = _gauges.get(key)
        if f is not None:
            return f
        W, pad, U, cells, on = self._W, self._pad, self._U, self._cells, self._on
        img = bytes([D]) * pad + self.simulate(0)

        def fn(n):
            RawTrigger(
                actions=[_POOL[j].SetNumber(int.from_bytes(img[4 * j : 4 * j + 4], "little")) for j in range(W)]
                + [_S.SetNumber(pad)]
            )
            for i in range(cells):
                wi, sh = divmod(pad + U * i, 4)
                RawTrigger(
                    conditions=n.AtLeast(i + 1),
                    actions=SetMemoryX(_POOL[wi].getValueAddr(), SetTo, on << (8 * sh), 0xFF << (8 * sh)),
                )

        fn.__name__ = "numfmt_gauge"
        f = EUDFunc(fn)
        _compat.predefine_returns(f, _POOL[:W] + [_S])
        _gauges[key] = f
        return f

    def fmt(self):
        """비용: 호출 2 / 실행 칸 수 + 약 4. 상수는 bytes."""
        c = self.const_bytes()
        if c is not None:
            return c
        f = self._tail()
        return self._emit_buf(self._W, lambda dests: f(*_args(self._kind), ret=dests))


# =============================================================================================
# Man (만 단위)
# =============================================================================================


def _man_colors(colors, tmax):
    """→ t 마다 (색1, 색2) 또는 None."""
    if colors is None:
        return None
    if isinstance(colors, str):
        if colors != "dps":
            fail('Man: colors 는 None, "dps", 단위별 색 목록, (색1, 색2) 목록입니다 (%r)', colors)
        return DPS_MAN_COLORS[: tmax + 1]
    t = _seq(colors)
    if not t:
        fail("Man: colors 목록이 필요합니다 (%r)", colors)
    if all(_seq(x) is not None for x in t):
        pairs = []
        for i, x in enumerate(t):
            x = _seq(x)
            if len(x) != 2:
                fail("Man: colors[%d] 는 (색1, 색2) 입니다", i)
            pairs.append(tuple((_int("Man colors", c, 0, 255) or D) for c in x))
        pairs += [(D, D)] * (tmax + 1 - len(pairs))
        return tuple(pairs[: tmax + 1])
    per = [(_int("Man colors[%d]" % i, x, 0, 255) or D) for i, x in enumerate(t)]
    per += [D] * (tmax + 1 - len(per))
    return tuple((per[u], per[u - 1] if u >= 1 else per[0]) for u in range(tmax + 1))


class _ManSpec:
    """Man 옵션 + 파이썬 흉내. 배치 = [pad][A 덩이 CA][B 덩이 CA], 덩이 = [색][4자리][after][단위 UW]."""

    def __init__(self, bits, top, colors, after, units, fixed):
        self.bits = bits
        self.tmax = 2 if bits == 32 else 4
        self.top = _int("Man top", top, 1, 2)
        self.colors = _man_colors(colors, self.tmax)
        self.after = None if after is None else (_int("Man after", after, 0, 255) or D)
        if not isinstance(units, str) or len(units) < self.tmax:
            fail("Man: units 는 단위 글자 %d개 이상인 문자열입니다 (%r)", self.tmax, units)
        self.units = tuple(_u8(u) for u in units[: self.tmax])
        self.UW = max(len(u) for u in self.units)
        self.fixed = _flag("fixed", fixed)
        self.CA = 6 + self.UW
        self.W = -(-(2 * self.CA) // 4)
        self.pad = 4 * self.W - 2 * self.CA
        self.A0 = self.pad
        self.B0 = self.pad + self.CA

    def key(self):
        return (self.bits, self.top, self.colors, self.after, self.units, self.fixed)

    def unit(self, t):
        if t < 1:
            return bytes([D]) * self.UW
        return self.units[t - 1].ljust(self.UW, bytes([D]))

    @staticmethod
    def L(n):
        return bytes(D if ch == " " else ord(ch) for ch in "%4d" % n)

    def image(self, v):
        """값 → (4W 바이트, 시작 위치). 트리거가 만드는 것과 같다."""
        t = 0
        while t < self.tmax and v >= 10 ** (4 * (t + 1)):
            t += 1
        q = v // 10 ** (4 * max(t - 1, 0))
        A, B = divmod(q, 10**4)
        c1, c2 = self.colors[t] if self.colors is not None else (D, D)
        after = D if self.after is None else self.after
        blank = bytes([D]) * self.CA
        if t == 0:
            if v == 0:
                a_area = bytes([c1]) + self.L(0) + bytes([D if self.fixed else after]) + self.unit(0)
            else:
                a_area = blank
            b_area = (bytes([c2]) + self.L(B) + bytes([after]) + self.unit(0)) if v else blank
        else:
            a_area = bytes([c1]) + self.L(A) + bytes([after]) + self.unit(t)
            show_b = B != 0 and self.top == 2
            b_area = (bytes([c2]) + self.L(B) + bytes([after]) + self.unit(t - 1)) if show_b else blank
        img = bytes([D]) * self.pad + a_area + b_area
        S = self.pad
        if not self.fixed:
            a_shown = not (t == 0 and v != 0)
            area0, n = (self.A0, A) if a_shown else (self.B0, B)
            if self.colors is None:
                S = area0 + 1 + (4 - len(str(n)))
            else:
                S = area0
        return img, S


def _man_front32():
    f = _bodies.get("man_front32")
    if f is not None:
        return f

    def front(x):
        """x → (Q, T): T = 단위(0~2), Q = x // 10^(4·max(T−1, 0)) — 10^4·10^8 비교·뺄셈."""
        q, t = EUDVariable(), EUDVariable()
        RawTrigger(actions=[t.SetNumber(0), q.SetNumber(0)])
        RawTrigger(conditions=x.AtLeast(10**4), actions=t.SetNumber(1))
        if EUDIf()(x.AtLeast(10**8)):
            RawTrigger(actions=t.SetNumber(2))
            for i in range(18, -1, -1):
                c = (1 << i) * 10**4
                RawTrigger(conditions=x.AtLeast(c), actions=[x.SubtractNumber(c), q.AddNumber(1 << i)])
        if EUDElse()():
            q << x
        EUDEndIf()
        EUDReturn(q, t)

    front.__name__ = "numfmt_man_front32"
    f = _bodies["man_front32"] = EUDFunc(front)
    return f


def _man_front64():
    f = _bodies.get("man_front64")
    if f is not None:
        return f

    def front(lo, hi):
        """(lo, hi) → (Q, T): T = 단위(0~4), Q = x // 10^(4·max(T−1, 0)) (< 10^8) — 64비트 비교·뺄셈 27단."""
        q, t = EUDVariable(), EUDVariable()
        RawTrigger(actions=[t.SetNumber(0), q.SetNumber(0)])
        for T in range(1, 5):  # 단위 판정: x ≥ 10^(4T) (오름차순, 뒤가 덮는다)
            c = 10 ** (4 * T)
            cl, ch = c & M32, c >> 32
            RawTrigger(conditions=hi.AtLeast(ch + 1), actions=t.SetNumber(T))
            RawTrigger(conditions=[hi.Exactly(ch), lo.AtLeast(cl)], actions=t.SetNumber(T))
        for n, T in enumerate((4, 3, 2)):
            (EUDIf() if n == 0 else EUDElseIf())(t.Exactly(T))
            dv = 10 ** (4 * (T - 1))
            for i in range(26, -1, -1):
                c = (1 << i) * dv
                if c > M64:  # 값 < 2^64 ≤ c 인 단은 건너뛴다 (다음 단에서도 값 < 2c)
                    continue
                _sub64_const(lo, hi, c, 2 * c - 1 <= M32, lambda i=i: [q.AddNumber(1 << i)])
        EUDElse()()
        q << lo
        EUDEndIf()
        EUDReturn(q, t)

    front.__name__ = "numfmt_man_front64"
    f = _bodies["man_front64"] = EUDFunc(front)
    return f


_mantails = {}


def _man_tail(ms):
    key = ms.key()
    f = _mantails.get(key)
    if f is not None:
        return f
    W, CA, A0, B0 = ms.W, ms.CA, ms.A0, ms.B0
    blankA = {A0 + i: D for i in range(CA)}
    blankB = {B0 + i: D for i in range(CA)}
    after = D if ms.after is None else ms.after

    def acts(tg):
        return _byte_actions(0, (), tg)

    def dpos(area0, j):  # j = 0 은 1000 자리
        return area0 + 1 + j

    def area(area0, c, u):
        tg = {area0: c, area0 + 5: after}
        tg.update({area0 + 6 + i: b for i, b in enumerate(u)})
        return {p: b for p, b in tg.items() if b != D}

    def fn(q, t):
        a = EUDVariable()
        img = bytearray([D]) * (4 * W)
        for area0 in (A0, B0):
            for j in range(4):
                img[dpos(area0, j)] = 0x30
        RawTrigger(
            actions=[_POOL[j].SetNumber(int.from_bytes(img[4 * j : 4 * j + 4], "little")) for j in range(W)]
            + [_S.SetNumber(ms.pad), a.SetNumber(0)]
        )
        # A = Q // 10^4 (비교·뺄셈 14단), Q 는 B 가 된다
        for i in range(13, -1, -1):
            c = (1 << i) * 10**4
            RawTrigger(conditions=q.AtLeast(c), actions=[q.SubtractNumber(c), a.AddNumber(1 << i)])
        # 단위별 색·after·단위 글자
        for T in range(ms.tmax + 1):
            c1, c2 = ms.colors[T] if ms.colors is not None else (D, D)
            tg = {}
            if T >= 1:
                tg.update(area(A0, c1, ms.unit(T)))
                if ms.top == 2:
                    tg.update(area(B0, c2, ms.unit(T - 1)))
            else:
                tg.update(area(B0, c2, ms.unit(0)))
            if tg:
                RawTrigger(conditions=t.Exactly(T), actions=acts(tg))
        # T = 0: 값 0 이면 A 덩이에 색1·'0'(fixed 가 아니면 after 도)와 B 숨김, 값 ≠ 0 이면 A 숨김
        zero = dict(blankB)
        if ms.colors is not None and ms.colors[0][0] != D:
            zero[A0] = ms.colors[0][0]
        if not ms.fixed and after != D:
            zero[A0 + 5] = after
        RawTrigger(conditions=[t.Exactly(0), q.Exactly(0)], actions=acts(zero))
        RawTrigger(conditions=[t.Exactly(0), q.AtLeast(1)], actions=acts(blankA))
        # T ≥ 1: B = 0 이면 (또는 top=1 이면) B 숨김
        if ms.top == 1:  # B 숨김 — 자리 글자가 더해지지 않게 B 값도 0 으로
            RawTrigger(conditions=t.AtLeast(1), actions=acts(blankB) + [q.SetNumber(0)])
        else:
            RawTrigger(conditions=[t.AtLeast(1), q.Exactly(0)], actions=acts(blankB))
        # 시작 위치 (fixed=False)
        if not ms.fixed:
            if ms.colors is None:
                for j, lim in ((0, 9999), (1, 999), (2, 99), (3, 9)):
                    RawTrigger(conditions=a.AtMost(lim), actions=_S.SetNumber(dpos(A0, j)))
                for j, lim in ((0, 9999), (1, 999), (2, 99), (3, 9)):
                    RawTrigger(conditions=[t.Exactly(0), q.AtLeast(1), q.AtMost(lim)], actions=_S.SetNumber(dpos(B0, j)))
            else:
                RawTrigger(conditions=[t.Exactly(0), q.AtLeast(1)], actions=_S.SetNumber(B0))
        # 덩이 안 앞 0 → D (끝자리는 늘 보인다)
        for var, area0 in ((a, A0), (q, B0)):
            for j, lim in ((0, 999), (1, 99), (2, 9)):
                RawTrigger(conditions=var.AtMost(lim), actions=acts({dpos(area0, j): D}))
        # 자리 글자 (A 4자리, B 4자리)
        for var, area0 in ((a, A0), (q, B0)):
            for j in range(4):
                wi, sh = divmod(dpos(area0, j), 4)
                for b in (8, 4, 2, 1):
                    c = b * 10 ** (3 - j)
                    RawTrigger(
                        conditions=var.AtLeast(c),
                        actions=[var.SubtractNumber(c), _POOL[wi].AddNumber(b << (8 * sh))],
                    )

    fn.__name__ = "numfmt_man"
    f = EUDFunc(fn)
    _compat.predefine_returns(f, _POOL[:W] + [_S])
    _mantails[key] = f
    return f


class Man(_Fmt):
    """만 단위 서식 (SetNumX 일반화, S3 7.4).

    인자: v(32비트 값 또는 Int64, 부호 없음), top(1 | 2 — 보일 덩이 수), colors(None | "dps" | 단위별 색 | (색1, 색2) 목록),
          after(덩이 뒤 색 바이트 또는 None), units(단위 글자 문자열), fixed(True = man18 바이트 그대로)
    반환: 서식 객체 (최대 2 × (6 + 단위 바이트) = 18B)
    비용: 앞 계산 32비트 본문 27 / 64비트 본문 147(1벌), 꼬리 60~67(옵션마다) / 호출 3 /
          실행 32비트 83~109, 64비트 102~144 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `printAll("{} 원", nf.Man(money, colors="dps", after=0x04));`
    출처: DPS CallTriggers/utils/converter.lua:223~428 (Call_WarLetter), S3 4.5·7.4 ("32비트는 10^4·10^8 비교·뺄셈,
          64비트는 단위 판정 4개 + 몫" — 몫은 i64 나눗셈 대신 64비트 비교·뺄셈 27단, WP5 판단)
    """

    def __init__(self, v, top=2, colors=None, after=None, units=MAN_UNITS, fixed=False):
        super().__init__()
        self._kind = _classify(v, "Man", 64 if isinstance(unProxy(v), i64.Int64) else None)
        self._ms = _ManSpec(self._kind[2], top, colors, after, units, fixed)

    def _max_len(self):
        return 2 * self._ms.CA

    def _fixed_len(self):
        return 2 * self._ms.CA if self._ms.fixed else None

    def simulate(self, v):
        img, S = self._ms.image(v)
        return img[S:]

    def const_bytes(self):
        return self.simulate(self._kind[1]) if self._kind[0] == "c" else None

    def fmt(self):
        """비용: 호출 3 (앞 계산·꼬리·포인터) / 실행 앞 계산 + 꼬리. 상수는 bytes."""
        c = self.const_bytes()
        if c is not None:
            return c
        ms = self._ms
        front = _man_front32() if ms.bits == 32 else _man_front64()
        q, t = front(*_args(self._kind))
        f = _man_tail(ms)
        return self._emit_buf(ms.W, lambda dests: f(q, t, ret=dests))


# =============================================================================================
# 이름 (dp.name20)
# =============================================================================================

_name_fn = []


def _name_tail():
    if _name_fn:
        return _name_fn[0]

    def fn(p):
        e = EUDVariable()
        SeqCompute([(e, SetTo, p), (e, Add, e), (e, Add, e), (e, Add, e), (e, Add, p)])  # 9p
        RawTrigger(actions=e.AddNumber(EPD(NAME_TABLE)))
        for j in range(4):
            if j:
                RawTrigger(actions=e.AddNumber(1))
            f_dwread_epd(e, ret=[_POOL[1 + j]])
        RawTrigger(actions=_POOL[0].SetNumber(0x000D0D0D))
        for i, c in enumerate(DPL_COLORS[:7]):
            RawTrigger(conditions=p.Exactly(i), actions=SetMemoryX(_POOL[0].getValueAddr(), SetTo, c << 24, 0xFF << 24))
        for j in range(4):
            for sh in range(4):
                RawTrigger(
                    conditions=MemoryX(_POOL[1 + j].getValueAddr(), Exactly, 0, 0xFF << (8 * sh)),
                    actions=SetMemoryX(_POOL[1 + j].getValueAddr(), SetTo, D << (8 * sh), 0xFF << (8 * sh)),
                )

    fn.__name__ = "numfmt_name20"
    f = EUDFunc(fn)
    _compat.predefine_returns(f, _POOL[:5])
    _name_fn.append(f)
    return f


class _Name20(_Fmt):
    """dp.name20 — DPL PName 원소 20B `[D D D 색] + 이름 16B`(0 바이트 → D)."""

    def __init__(self, p):
        super().__init__()
        k = _classify(p, "dp.name20", 32)
        if k[0] == "c" and not 0 <= k[1] <= 6:
            fail("dp.name20: 플레이어 번호는 0~6 입니다 (DPL 이름 캐시 — 7 이상은 원본도 쓰지 않음) (%r)", p)
        self._kind = k

    def _max_len(self):
        return 20

    def _fixed_len(self):
        return 20

    def fmt(self):
        """비용: 본문 36 / 호출 3 / 실행 약 190 (이름 읽기 4 + 0 바이트 바꾸기 16). p ≥ 7 이면 버퍼를 그대로 둔다(원본과 같음)."""
        f = _name_tail()
        buf = Db(24)
        dests = [EPD(buf) + i for i in range(5)]
        (arg,) = _args(self._kind)
        if self._kind[0] == "c":
            f(arg, ret=dests)
        else:
            if EUDIf()(arg.AtMost(6)):
                f(arg, ret=dests)
            EUDEndIf()
        return ptr2s(buf)


# =============================================================================================
# numfmt.dp — DisplayPrint 호환 프리셋
# =============================================================================================


class _DP:
    """DisplayPrint 호환 프리셋 9개 (S3 7.4·8.1). 모두 고정 폭, 0x0D 채움. epScript: `nf.dp.dec16(v)`."""

    @staticmethod
    def dec16(v):
        """V 원소(Call_IToDec) 16B: `D×4 [D][부호|D] 10^9..10^0`, 앞 0 → D, 음수는 절댓값과 '-'."""
        return Dec(v, sign="-", width=11, fill="\r", align="=", bits=32, _prefix=b"\r" * 5)

    @staticmethod
    def decfw48(v):
        """V.fwc 원소(Call_IToDecX) 48B: `D×8` + 10칸 `[D, EF, BC, 90+d]`, 앞 칸 `D×4`, 부호 없음."""
        return Dec(v, fullwidth=True, width=12, fill="\r", bits=32)

    @staticmethod
    def hex12(v):
        """V.hex 원소(Call_ItoHex) 12B: `D×4` + 8자리 대문자(앞 0 유지)."""
        return Hex(v, width=8, fill="0", _prefix=b"\r" * 4)

    @staticmethod
    def dec20(x):
        """W 원소(Call_lIToDec) 20B: 양수는 앞 0 → D(첫 바이트 늘 D), 음수는 '-' + 19자리 0 채움."""
        return Dec(x, sign="-", width=20, fill="\r", bits=64, _neg_fill="0", _neg_align="=")

    @staticmethod
    def name20(p):
        """PName 원소 20B: `[D D D 색]` + 이름(0x6D0FDC + 36p) 16B, 0 바이트 → D. p ≥ 7 은 쓰지 않음."""
        return _Name20(p)

    @staticmethod
    def man18(v, color=False):
        """SetNumX/SetNumTBLX/SetNumErX 18B (S3 4.5)."""
        color = _flag("color", color)
        return Man(v, colors="dps" if color else None, after=0x04 if color else None, fixed=True)

    @staticmethod
    def per8(v, permil=False, tbl=False):
        """SetEPerSTRX/TBLX 8B: 최대 100000 (퍼밀이면 STR 5000000 / TBL 1000000)."""
        permil, tbl = _flag("permil", permil), _flag("tbl", tbl)
        mx = (1000000 if tbl else 5000000) if permil else 100000
        return Per(v, scale=1000, frac=3, max=mx, trim=True, int_min=1, width=8, fill="\r")

    @staticmethod
    def dig2(v):
        """dpletter2 2B: 0~9 → `D d`, 10~99 → 두 자리, 100 이상 → 아래 두 자리(0 유지)."""
        return Dec(v, max_digits=2, width=2, fill="\r", bits=32)

    @staticmethod
    def gauge40(n):
        """GaugeBar(Tbl) 40B: `[색][l]`×20, 앞 n 칸 0x07, 나머지 0x04."""
        return Gauge(n, cells=20, glyph="l", on=0x07, off=0x04)

    def __repr__(self):
        return "<eudext.numfmt.dp — DisplayPrint 호환 프리셋>"


dp = _DP()


# =============================================================================================
# 직접 쓰기·셀·읽기
# =============================================================================================


def _write_obj(dst_ptr, obj):
    """서식 객체를 dst_ptr 에 NUL 없이 쓴다 → 쓴 길이 (int | EUDVariable)."""
    const = obj.const_bytes()
    d = _const_int(dst_ptr)
    if const is not None:
        if d is not None and d % 4 == 0 and len(const) % 4 == 0:
            _chunked([SetMemory(d + i, SetTo, int.from_bytes(const[i : i + 4], "little")) for i in range(0, len(const), 4)])
        else:
            f_dbstr_print(dst_ptr, const, EOS=False)
        return len(const)
    plan = obj._plan() if isinstance(obj, _NumFmt) else None
    if d is not None and plan is not None and plan.fixed and plan.lay.nul is None and (d - plan.start_const) % 4 == 0:
        S = plan.start_const
        base = d - S  # 이미지 위치 0 ↔ 주소 base
        dests, partial = [], []
        for i in range(plan.E + plan.lay.W):
            lo_b = 4 * i
            if lo_b + 4 <= S:
                dests.append(EUDVariable())
            elif lo_b >= S:
                dests.append(EPD(base + lo_b))
            else:
                t = EUDVariable()
                dests.append(t)
                msk = 0
                for b in range(S, lo_b + 4):
                    msk |= 0xFF << (8 * (b - lo_b))
                partial.append((base + lo_b, t, msk))
        obj._call(dests + [EUDVariable()])
        for addr, t, msk in partial:
            _parts.write_addr(addr, t, msk)
        return plan.fixed_len
    end = f_dbstr_print(dst_ptr, obj, EOS=False)
    n = EUDVariable()
    n << end
    _parts.isub32(n, dst_ptr)
    return n


def f_fmt_dec_to(dst_ptr, value, **opts):
    """`Dec(value, **opts)` 를 dst_ptr 에 NUL 없이 쓰고 쓴 길이를 돌려준다(고정 배치 직접 쓰기).

    출력 길이가 고정이고 dst_ptr 가 정수 상수이며 바이트 정렬이 맞으면 단어째 쓴다(앞 부분 단어는 마스크 쓰기).
    그 밖은 `f_dbstr_print(dst, obj, EOS=False)` 로 바이트 복사한다. value 가 상수면 상수 바이트를 쓴다.
    인자: dst_ptr(주소 — 상수·변수), value, opts(Dec 옵션)
    반환: int(고정 길이·상수) 또는 EUDVariable(쓴 길이)
    비용: 단어째 = Dec 비용 + 0~2 (호출 3) / 바이트 복사 = Dec 비용 + 바이트당 약 30 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전 (dst 가 공유 메모리면 모든 PC 에서 같은 조건으로)
    epScript: `const n = nf.fmt_dec_to(0x641598, hp, width=5);`
    출처: R4a C.3-3 (고정 배치는 서식 문자열을 거치지 않는다), S3 4.2·4.3
    """
    return _write_obj(dst_ptr, Dec(value, **opts))


fmt_dec_to = f_fmt_dec_to


def _cp_write(epd, words):
    """CP 를 잠깐 epd 로 옮겨 단어들을 차례로 쓰고 캐시로 되돌린다 (DESIGN 3.6-3 의 잠깐 옮기기)."""
    SeqCompute([(_parts.EPD_CP, SetTo, epd)])
    for i, w in enumerate(words):
        if i:
            RawTrigger(actions=SetMemory(CP_ADDR, Add, 1))
        if _compat.is_var(w):
            SeqCompute([(CP_PLAYER, SetTo, w)])
        else:
            RawTrigger(actions=SetDeaths(CurrentPlayer, SetTo, w, 0))
    f_setcurpl2cpcache()


def f_fmt_dec_cells(dst_epd, value, color=None, layout="eudplib", **opts):
    """`Dec(value, **opts)` 를 글자당 4B 셀로 dst_epd 부터 쓴다(오른쪽 정렬, 서식 글자 앞 칸은 빈 셀 `0D×4`). 쓴 칸 수를 돌려준다.

    셀 배치: layout="eudplib" `[C][c][0D][0D]`(TextFX), "ctrig" `[C][0D][0D][c]`(CtrigAsm iutf8, S6 1.7). 3바이트 글자는
    둘 다 `[C][b0][b1][b2]`. 숫자 셀의 C = color(None 이면 0x0D) 또는 opts 의 colors(자리마다), 다른 셀의 C = 0x0D.
    인자: dst_epd(EPD — 상수·변수), value, color, layout, opts(Dec 옵션: width·fill·sign·group·fullwidth·colors …)
    반환: int (쓴 칸 수 = max(width, 최대 글자 수))
    비용: Dec 비용(셀 배치 본문 1벌, 실행 70~73) + 변수 주소면 칸당 약 3 (docs/COSTS.md)
    CP: 바꾸지 않음 (변수 주소는 CP 를 잠깐 옮기고 캐시로 되돌림)
    로컬: 공유 안전 (셀 버퍼가 로컬 전용이면 로컬 분기 안에서)
    epScript: `nf.fmt_dec_cells(EPD(cells), score, color=0x1F, width=8);`
    출처: S6 1.7, CtrigAsm CA__ItoCustom(SVA1 칸), eudplib f_cpchar_adddw
    """
    if layout not in ("eudplib", "ctrig"):
        fail('f_fmt_dec_cells: layout 은 "eudplib" 또는 "ctrig" 입니다 (%r)', layout)
    if color is not None:
        color = _int("color", color, 1, 255)
        if opts.get("colors") is None:
            opts["colors"] = color
    obj = Dec(value, _mode=layout, **opts)
    plan = obj._plan()
    nw = plan.E + plan.lay.W
    cells = (plan.END - plan.min_start) // 4
    first = nw - cells
    e = unProxy(dst_epd)
    const_e = _compat.is_const(e) and not _compat.is_var(e)
    if obj._kind[0] == "c":
        img, _S0 = plan.image(obj._kind[1])
        words = [int.from_bytes(img[4 * i : 4 * i + 4], "little") for i in range(first, nw)]
        if const_e:
            _chunked([SetMemoryEPD(e + i, SetTo, w) for i, w in enumerate(words)])
        else:
            _cp_write(e, words)
        return cells
    if const_e:
        obj._call([EUDVariable() for _ in range(first)] + [e + i for i in range(cells)] + [EUDVariable()])
        return cells
    tmp = [EUDVariable() for _ in range(nw)]
    obj._call(tmp + [EUDVariable()])
    _cp_write(e, tmp[first:])
    return cells


fmt_dec_cells = f_fmt_dec_cells

_scanners = {}


def f_scan_dec_cells(src_epd, n, signed=False, layout="eudplib"):
    """글자 셀 n 칸(src_epd 부터)을 10진 값으로 읽는다 (CtrigAsm CD__ScanV 대체).

    규칙: 숫자 셀은 이어 붙이고(곱하기 10 + 자리), `,` 셀은 건너뛰고, 그 밖의 셀을 만나면 값을 0 으로 되돌린다
    → 끝 칸에서 거꾸로 읽다가 숫자·쉼표가 아닌 글자에서 멈추는 CD__ScanV 와 같은 값. signed 면 `-` 셀 뒤의 수를 음수로
    (CD__ScanV "`-` 가 있으면 부호를 바꾸고 중단"). 32비트 넘침은 한 바퀴 돈다.
    셀 배치: "eudplib" `[C][c][0D][0D]`, "ctrig" `[C][0D][0D][c]` (C 는 보지 않는다).
    인자: src_epd(EPD — 상수·변수), n(칸 수 — 상수·변수), signed(bool), layout
    반환: EUDVariable
    비용: 본문 27(배치·부호마다 1벌) / 호출 1~2 / 실행 칸당 약 8 + 숫자 칸마다 약 12 (빈 칸 12개 106) (docs/COSTS.md)
    CP: 바꾸지 않음 (잠깐 옮기고 캐시로 되돌림)
    로컬: 공유 안전 (읽는 셀이 로컬 값이면 결과도 로컬)
    epScript: `const v = nf.scan_dec_cells(EPD(cells), 10, signed=True);`
    출처: CtrigAsm v5.5.lua:54357 CD__ScanV, 가이드북 26장
    """
    signed = _flag("signed", signed)
    if layout not in ("eudplib", "ctrig"):
        fail('f_scan_dec_cells: layout 은 "eudplib" 또는 "ctrig" 입니다 (%r)', layout)
    key = (signed, layout)
    f = _scanners.get(key)
    if f is None:
        sh = 8 if layout == "eudplib" else 24
        rest = (D << 16 | D << 24) if layout == "eudplib" else (D << 8 | D << 16)
        rmask = (0xFFFF << 16) if layout == "eudplib" else (0xFFFF << 8)
        cmask = 0xFF << sh

        def isdigit():
            return [
                DeathsX(CurrentPlayer, Exactly, rest, 0, rmask),
                DeathsX(CurrentPlayer, AtLeast, 0x30 << sh, 0, cmask),
                DeathsX(CurrentPlayer, AtMost, 0x39 << sh, 0, cmask),
            ]

        def ischar(ch):
            return DeathsX(CurrentPlayer, Exactly, rest | (ch << sh), 0, rmask | cmask)

        def fn(src, cnt):
            v, t, bad, neg = EUDVariable(), EUDVariable(), EUDVariable(), EUDVariable()
            SeqCompute([(v, SetTo, 0), (neg, SetTo, 0), (_parts.EPD_CP, SetTo, src)])
            if EUDWhile()(cnt.AtLeast(1)):
                RawTrigger(actions=bad.SetNumber(1))
                RawTrigger(conditions=isdigit(), actions=bad.SetNumber(0))
                RawTrigger(conditions=ischar(0x2C), actions=bad.SetNumber(0))
                if signed:
                    RawTrigger(conditions=ischar(0x2D), actions=[bad.SetNumber(0), v.SetNumber(0), neg.SetNumber(1)])
                RawTrigger(conditions=bad.Exactly(1), actions=[v.SetNumber(0), neg.SetNumber(0)])
                if EUDIf()(isdigit()):
                    SeqCompute([(t, SetTo, v), (t, Add, t), (v, SetTo, t), (t, Add, t), (t, Add, t), (v, Add, t)])  # v·10
                    for dg in range(9, 0, -1):
                        RawTrigger(conditions=ischar(0x30 + dg), actions=v.AddNumber(dg))
                EUDEndIf()
                RawTrigger(actions=[SetMemory(CP_ADDR, Add, 1), cnt.SubtractNumber(1)])
            EUDEndWhile()
            f_setcurpl2cpcache()
            if signed:
                if EUDIf()(neg.Exactly(1)):
                    SeqCompute([(t, SetTo, M32), (t, Subtract, v), (t, Add, 1), (v, SetTo, t)])  # −v (3.5-7)
                EUDEndIf()
            EUDReturn(v)

        fn.__name__ = "numfmt_scan"
        f = _scanners[key] = EUDFunc(fn)
    return f(src_epd, n)


scan_dec_cells = f_scan_dec_cells


# =============================================================================================
# 서식 지정자 (선택 몽키패치)
# =============================================================================================

_spec_state = {"restore": None}
_SPEC_RE = re.compile(
    r"(?:(?P<fill>.)?(?P<align>[<>=^]))?(?P<sign>[-+ ])?(?P<z>z)?(?P<alt>#)?(?P<zero>0)?(?P<width>\d+)?"
    r"(?P<group>[,_])?(?:\.(?P<prec>\d+))?(?P<type>[dxXw]?)",
    re.S,
)


def _parse_spec(spec):
    """파이썬 서식 지정자 → (kind, 옵션 dict) 또는 None(우리 것이 아님 — eudplib 이 처리)."""
    if spec in ("", "x", "X"):
        return None
    m = _SPEC_RE.fullmatch(spec)
    if m is None:
        return None
    for bad, name in (("z", "z"), ("alt", "#"), ("prec", "정밀도")):
        if m.group(bad) is not None:
            fail("numfmt 서식 지정자 %r: %s 는 지원하지 않습니다", spec, name)
    typ, align, fill = m.group("type"), m.group("align"), m.group("fill")
    if align in ("<", "^"):
        fail("numfmt 서식 지정자 %r: 왼쪽·가운데 정렬은 지원하지 않습니다", spec)
    opts = {"width": int(m.group("width") or 0)}
    if m.group("zero") and not align:
        opts["fill"], opts["align"] = "0", "="
    else:
        opts["fill"] = fill if fill is not None else " "
        if align:
            opts["align"] = align
    s, group = m.group("sign"), m.group("group")
    if typ in ("x", "X"):
        if s:
            fail("numfmt 서식 지정자 %r: 16진에는 부호를 쓰지 않습니다", spec)
        if group:
            fail("numfmt 서식 지정자 %r: 16진 묶음은 2차입니다", spec)
        opts["lower"] = typ == "x"
        return "hex", opts
    if s:
        opts["sign"] = {"-": "-", "+": "+-", " ": " -"}[s]
    if group:
        opts["group"] = (3, group)
    if typ == "w":
        opts["fullwidth"] = True
    return "dec", opts


def _format_hook(value, spec):
    v = unProxy(value)
    if isinstance(v, bool):
        return None
    if not (isinstance(v, (int, i64.Int64)) or _compat.is_var(v) or _compat.is_varbase(v)):
        return None
    if spec == "" and isinstance(v, i64.Int64):
        return Dec(value)
    parsed = _parse_spec(spec)
    if parsed is None:
        return None
    kind, opts = parsed
    return Hex(value, **opts) if kind == "hex" else Dec(value, **opts)


def f_enable_format_spec():
    """eudplib 서식 문자열에서 `{:05d}`·`{:+,d}`·`{: d}`·`{:08x}`·`{:4X}`·`{:w}`·`{:,}` 과 Int64 의 `{}` 를 쓸 수 있게 한다.

    eudplib 내부 `_EUDFormatter.eudformat_field` 를 감싸는 선택 몽키패치다(`_compat.hook_format_field`, 판에 기댄다).
    `{}`·`{:x}`·`{:X}`(8자리 대문자)·`{:s}` 등 eudplib 이 이미 아는 것은 그대로 둔다. 서식 지정자는 파이썬 뜻을 따른다
    (채움 기본 = 공백, `0` = 부호 뒤 0 채움). 부호 글자(`+`·`-`·` `)가 있으면 부호 있는 값, 없으면 부호 없는 값.
    인자: 없음
    반환: None (두 번 불러도 된다)
    비용: 컴파일 시점만 (바뀐 필드는 Dec/Hex 비용)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `nf.enable_format_spec();` 뒤 `printAll("{:05d}", v);`
    출처: R4a C.3-1, eudplib 0.81 `string/fmtprint.py:90` eudformat_field
    """
    if _spec_state["restore"] is None:
        _spec_state["restore"] = _compat.hook_format_field(_format_hook)


def f_disable_format_spec():
    """`enable_format_spec` 을 되돌린다(시험용). 반환: None. 비용: 없음. epScript: `nf.disable_format_spec();`"""
    r = _spec_state["restore"]
    if r is not None:
        r()
        _spec_state["restore"] = None


def f_format_spec_enabled():
    """지금 서식 지정자 확장이 켜져 있는지(bool). 비용: 없음. epScript: `nf.format_spec_enabled()`."""
    return _spec_state["restore"] is not None


enable_format_spec = f_enable_format_spec
disable_format_spec = f_disable_format_spec
format_spec_enabled = f_format_spec_enabled
