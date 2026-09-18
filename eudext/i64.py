"""64비트 정수 값 타입 `Int64` 와 배열 `Int64Array` (DESIGN 4.4, 3.2, 3.3, 3.5) — 1차(WP3) + 2차(WP4).

    from eudext import i64
    from eudext.i64 import Int64, Int64Array

    gold = Int64(12_800_000_000)       # 초기값만 (트리거 0)
    gold += v32                         # 32비트 값을 더하기 (hi 는 0)
    gold -= 5                           # wrap (한 바퀴 돎)
    gold.isub_sat(price)                # 포화 (0 에서 멈춤, 64비트 전체 기준 = CtrigAsm f_LSub)
    if EUDIf()(gold >= 10 ** 10): ...   # 부호 없는 사전식 비교 → 조건
    f_dbstr_print(buf, "골드 ", gold)   # 10진 출력 (fmt 훅)
    price = gold * level // 100         # 곱셈(wrap)·나눗셈(부호 없음) — 2차
    q, r = i64.sdivmod(x, -7)           # 부호 있는 나눗셈 (0 방향 자르기)
    mask = (x & 0xFFFF) | y.shl(3)      # 비트·시프트 (`<<` 는 대입, `<<=`·`>>=`·`>>`·shl/shr 는 시프트)

epScript (`import eudext.i64 as i64;`, 값 타입은 const 로 묶는다 — 3.11):

    const hp = i64.Int64(0x100000000);
    hp.v += 5;                          // 제자리 연산은 .v 통로 (iaddattr/isubattr)
    hp.isub_sat(dmg);                   // 포화
    if (hp >= 0x100000005) printAll("HP {}", hp.fmt());
    hp.v *= 3; hp.v /= 7; hp.v <<= 2;   // 2차: 제자리 곱·나눗셈·시프트 (epScript `/` 는 `//`)

## 뺄셈의 두 의미 (DESIGN 3.5 — 사용자가 가장 중요하다고 한 대목)

| 이름 | 의미 |
|---|---|
| `x -= y`, `x - y`, `-x`, `x.isub(y)`, `x.v -= y`, `i64.sub(a, b)`, `arr[i] -= v`(isubitem), `f_LiSub`, `f_LNeg`, `x.neg()` | **wrap** `(a − b) mod 2^64` |
| `x.isub_sat(y)`, `i64.sub_sat(a, b)`, `i64.isub_sat(x, y)`, `arr.isub_sat(i, v)`(= `isubtractitem`), `x.isubtractattr("v", y)`, `f_LSub` | **포화** `a ≥ b ? a − b : 0`, **64비트 전체 기준** |

- 반쪽별 포화(CtrigAsm `SetNWar(Subtract)` 식)는 만들지 않는다(2^32 − 1 빼기에서 틀린다).
- `Int64.SubtractNumber`/`AddNumber` 는 두지 않는다(64비트 포화는 조건 트리거가 필요해 액션 하나가 될 수 없다).
- 같은 객체끼리 `x -= x`·`sub_sat(x, x)` 는 컴파일 시점에 0 으로 접는다(eudplib `v -= v` 버그를 물려받지 않는다).
- SC `Subtract` 액션은 3.5-7 의 "써도 되는 곳"에만 쓴다: `~y`(0xFFFFFFFF ⊖ y), 포화 뺄셈의 hi 반쪽(lo 보정 트리거와 함께),
  앞 조건이 `값 ≥ 빼는 값` 을 보장한 곳(10진 변환, 상수 포화의 빌림).

## 피연산자

`Int64`, 정수 상수(−2^63 ~ 2^64−1, 음수는 2의 보수), 10진 문자열(`"12800000000"`, `parse` 와 같음),
32비트 `EUDVariable`(0 확장 — hi 는 0), `EUDLightVariable`·읽기 전용 값 칸(읽어서 씀, `f_dwread_epd` 비용),
주소식 상수(임시 변수에 옮김). `EUDLightBool`·`Condition`·실수는 오류.

## 값 타입 규약 (3.2)

- `Int64(상수)` = 초기값만. `Int64(변수)`·`Int64(a, b)`·`Int64(Int64)` = 실행 시 대입. `Int64.wrap(lo, hi)` = 복사 없이 감싸기.
- 이항 연산(`+ - 단항-`)은 새 임시 `Int64` 를, 제자리 연산은 self 를 돌려준다. 상수끼리는 파이썬 `int`.
- `<<` 는 **대입**이다(epScript 식 `x << 3` 은 시프트로 번역되므로 빌드 오류로 막는다). 시프트는 `x.shl(n)`·`x.shr(n)`·
  `x >> n`(새 값), `x <<= n`·`x >>= n`·`x.v <<= n`(제자리 — eudplib `EUDVariable` 과 같게 `<<=` 는 시프트).
- 32비트 변수가 **왼쪽**인 `v * x`·`v // x`·`v % x`·`v >> x` 는 eudplib 연산자가 먼저 불려 안내 오류 → `i64.mul(v, x)` 등.
- `__bool__`·`__format__`·`__iter__`·`cast` 는 안내 오류. `EUDTypedFunc([Int64])` 는 한 칸에 못 넘기므로 오류 → `(lo, hi)` 두 인자.
- 인쇄: `x.fmt()` → 호출 자리마다 24바이트 버퍼에 10진을 쓰고 `ptr2s` 를 돌려준다. `f_dbstr_print(buf, x)` 처럼
  `Int64` 를 그대로 넘겨도 된다. `f_sprintf("{}", x)`·`printAll("{}", x)` 는 `__format__` 에서 막으니 `x.fmt()` 를 쓴다.

## 알고리즘과 비용 (에뮬레이터 실측, docs/COSTS.md "i64 (WP3)", 2026-09-17)

- 덧셈 `x += y`: 변수 = 채우기 한 줄(`x.lo += y.lo`, `x.hi += y.hi`, 올림 조건 amount ← 새 lo + 1) + 올림 트리거
  `[y.lo ≥ 채움] ∧ [채움 ≥ 1]` → 호출 2 / 실행 5. 상수 = 호출 2 / 실행 2. (war.py `_add64_inline` 과 같은 생각, 복사 없음)
- wrap 뺄셈 `x -= y`: `x.lo += ~y.lo + 1`, `x.hi += ~y.hi + 1` 을 한 줄에 하고, 빌림은 **새 lo 와 ~y.lo 로** 판정한다
  (`빌림 ⇔ 새 lo > ~y.lo`) → 기본 인라인 호출 2 / 실행 7 (S8 WVb 6 / 12 보다 싸고, 호출 자리 바이트가 공유 함수 호출과
  같아서 인라인을 기본으로 했다). `inline=False` = 공유 EUDFunc(본문 4, 호출 1 / 실행 18). 상수 = S8 WK 와 같은 2 / 2.
- 포화 뺄셈 `x.isub_sat(y)`: 변수끼리는 기본이 공유 EUDFunc(본문 5, 호출 1 / 실행 19 — DESIGN 3.3). `inline=True` 면
  한 줄(lo wrap, hi 는 SC Subtract, 빌림·hi 비교 채우기) + 트리거 2 → 호출 3 / 실행 8 (호출 자리가 약 1KB 크다).
  빌림 트리거가 hi 를 wrap 으로 1 빼고, "hi 가 작거나 같음" 조건의 비교값을 1 낮추며, 그 조건의 넘침 막이 조건을
  Always 로 바꾼다(준비 트리거가 매번 되살림). S8 SVa(7 / 14)·SVf(본문 9 / 실행 25)·war.py `_subsat64`(본문 27,
  실행 51)보다 싸다. 상수 = S8 **SK**(분기 없음, 2~4).
- 비교: DPS 이식판 a7aad90 "비교 계획"(`tlib.py:204~`) — `x ≥ y = [xh ≥ yh] ∧ ¬([xh ≤ yh] ∧ [xl < yl])`.
  변수 값은 조건 amount 칸에 채우고(`_parts.Plan`), 부정 부분은 자기 칸 깃발을 끄는 조건 트리거 하나.
  변수끼리 = 호출 2 / 실행 5, 상수 = 0~2 / 0~2. 부호 있는 비교는 hi 에 2^31 을 더한 자기 칸(호출 3 / 실행 7).
- 10진 출력: `b·10^i` 복원 뺄셈 77단(한 단 = 서로 배타인 트리거 1~2, hi 가 0 인 뒤로는 1) + 앞자리 0 세기 19
  → 본문 약 140 / 실행 약 150 (목표 620 / 450).

## 2차(WP4): 곱셈·나눗셈·부호 연산·비트·시프트·난수·to32 (docs/COSTS.md "i64 2차 (WP4)", 2026-09-17)

- 곱셈(wrap, 부호 없음·있음 결과 같음): 곱해지는 수의 하위 반쪽을 16비트 두 조각으로 나누고, 곱하는 수의 비트마다
  조건 트리거 하나가 두 배씩 느는 조각(변수 트리거 사슬)을 넘치지 않는 누적기에 더한다(16비트 쪼개기, G3 1.10).
  변수끼리 최악 실행 약 360(64×64) / 280(64×32) / 210(32×32) — 목표 ≤ 1,000, war.py 비트 루프 2,268~4,626.
  상수 곱은 상수마다 공유 본문: 비트 누적(곱해지는 수의 비트마다 상수 조각을 더함, 최악 약 95) 또는 배가·덧셈(NAF, 작은 상수).
- 나눗셈(부호 없음, 0 나눗셈 = 몫 2^64 − 1·나머지 = 피제수): 이식판 3경로(0 / 32비트 제수 / 64비트 제수)를 한 공유 본문에,
  한 단을 공유 비교 트리거(제수를 조건 amount 칸에 한 번만 채움)로 줄였다. 최악 실행 약 390 — 목표 ≤ 711.
  상수 제수는 이식판 `_cdiv`(결정 나무로 들어갈 단을 고르는 복원 나눗셈, a41d2ed)를 옮겼고(2^32 이상 제수는 같은 방식의
  64비트 판), 2의 거듭제곱은 시프트·마스크. 실행 약 20~95.
- 부호 있는 나눗셈 `sdiv/smod/sdivmod`: 0 방향 자르기, 나머지 부호 = 피제수(CtrigAsm f_LiDiv/f_LiMod·C 와 같음).
  0 나눗셈 `div0="eudplib"`(기본: eudplib f_div_towards_zero 처럼 몫 = 피제수 < 0 이면 1 아니면 −1) / `"ctrig"`(±(2^63 − 1) 쪽).
- 비트: 마스크 SetTo(`&`·`|` — eudplib 0.81 과 같은 마스크 칸 채우기)와 `(a | b) ⊖ (a & b)`(`^`), `0xFFFFFFFF ⊖ a`(`~`).
  마스크 Add/Subtract 식(인게임 확인 전, S8 A-1)은 쓰지 않는다.
- 시프트(논리, n ≥ 64 → 0): 상수 n 은 64비트 두 배(실행 4)·비트 옮기기·96비트 창 중 싼 것, 변수 n 은 결정 나무로 두 배
  단계에 들어간다(최악 150 / 210). to32(포화·부호), abs, rand(`f_dwrand` 2번)도 이 절.

출처: DESIGN 4.4, docs/spec/S8_subtract.md 6·7절, docs/proto/i64_proto.py(시제품), DPS_Enhance eudplib-port a7aad90
`eud/ctrig/war.py`(`_add64_inline`, `_inplace64`, `_subsat64_inline`), `eud/ctrig/tlib.py:204~`(비교 계획),
`eud/ctrig/text.py:370~`(`_lt64c`·`_lidec_ops` 10진 변환), CtrigAsm `f_LAdd`/`f_LSub`/`f_LiSub`/`f_LNeg`.
2차: DPS_Enhance eudplib-port a7aad90(받아 둔 사본 HEAD 는 e7efff2 — 옮긴 부분·divide.py·t_war.py 는 두 판이 같다)
`eud/ctrig/war.py:305~420`(`_mul3232`·`_mul64`·`_div6432`·`_div64big`·`_divmod64`)·`:483~642`(`_cdiv`, 결정 나무)·
`eud/ctrig/arith.py:275`(`_mul_small`)·`eud/ctrig/divide.py`, `eud/tests/t_war.py` 기대값, CtrigAsm v5.5
`f_LMul`/`f_LDiv`/`f_LMod`/`f_LiDiv`/`f_LiMod`/`f_LAnd`/`f_LOr`/`f_LXor`/`f_LNot`/`f_LAbs`/`f_LRand`,
eudplib 0.81 `core/calcf/muldiv.py`(`_eud_mul`·`_eud_div` 자기 수정 기법)·`eudlib/mathf/div.py`(부호 나눗셈 0 나눗셈 규칙).
"""

import functools

from eudplib import (
    EPD,
    Add,
    Always,
    AtLeast,
    AtMost,
    Condition,
    Db,
    EUDArray,
    EUDElse,
    EUDEndIf,
    EUDFunc,
    EUDIf,
    EUDLightBool,
    EUDReturn,
    EUDVariable,
    Exactly,
    ExprProxy,
    Forward,
    MemoryEPD,
    Never,
    NextTrigger,
    RawTrigger,
    SeqCompute,
    SetMemoryEPD,
    SetMemoryXEPD,
    SetNextPtr,
    SetNextTrigger,
    SetTo,
    Subtract,
    f_bwrite,
    f_dwrand,
    f_dwread_epd,
    f_dwwrite_epd,
    ptr2s,
    unProxy,
)

from eudext import _compat
from eudext._parts import (
    DLeaf,
    DNode,
    Plan,
    SelfFrame,
    add_modifiers,
    dgoto,
    dlabel,
    dpresets,
    dspine,
    dtree,
    emit_dtree,
    flag_cond,
    placeholder,
    selfcond,
    var_chain,
)
from eudext.errors import EudextError, fail

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
SIGN = 0x80000000
S64MIN = -(1 << 63)

_ALWAYS_W = 22 << 24  # 조건 +12 칸: 유닛 0·비교 0·종류 Always
_MEMGE_W = 15 << 24  # 같은 칸: 유닛 0·비교 AtLeast(0)·종류 Memory(15)

__all__ = [
    "Int64",
    "Int64Array",
    "LAbs",
    "LAdd",
    "LAnd",
    "LDiv",
    "LMod",
    "LMul",
    "LNeg",
    "LNot",
    "LOr",
    "LRand",
    "LSub",
    "LXor",
    "LiDiv",
    "LiMod",
    "LiMul",
    "LiSub",
    "add",
    "bitand",
    "bitnot",
    "bitor",
    "bitxor",
    "div",
    "eq",
    "f_LAbs",
    "f_LAdd",
    "f_LAnd",
    "f_LDiv",
    "f_LMod",
    "f_LMul",
    "f_LNeg",
    "f_LNot",
    "f_LOr",
    "f_LRand",
    "f_LSub",
    "f_LXor",
    "f_LiDiv",
    "f_LiMod",
    "f_LiMul",
    "f_LiSub",
    "f_abs",
    "f_add",
    "f_bitand",
    "f_bitnot",
    "f_bitor",
    "f_bitxor",
    "f_div",
    "f_divmod",
    "f_eq",
    "f_fmt",
    "f_ge",
    "f_gt",
    "f_iabs",
    "f_iadd",
    "f_iand",
    "f_idiv",
    "f_iinvert",
    "f_imod",
    "f_imul",
    "f_ior",
    "f_ishl",
    "f_ishr",
    "f_isub",
    "f_isub_sat",
    "f_ixor",
    "f_le",
    "f_lidec_to",
    "f_lt",
    "f_mod",
    "f_mul",
    "f_mul32",
    "f_ne",
    "f_neg",
    "f_parse",
    "f_rand",
    "f_sdiv",
    "f_sdivmod",
    "f_sge",
    "f_sgt",
    "f_shl",
    "f_shr",
    "f_sle",
    "f_slt",
    "f_smod",
    "f_sub",
    "f_sub_sat",
    "f_to32",
    "f_wrap",
    "fmt",
    "ge",
    "gt",
    "iabs",
    "iadd",
    "iand",
    "idiv",
    "iinvert",
    "imod",
    "imul",
    "ior",
    "ishl",
    "ishr",
    "isub",
    "isub_sat",
    "ixor",
    "le",
    "lidec_to",
    "lt",
    "mod",
    "mul",
    "mul32",
    "ne",
    "neg",
    "parse",
    "rand",
    "sdiv",
    "sdivmod",
    "sge",
    "sgt",
    "shl",
    "shr",
    "sle",
    "slt",
    "smod",
    "sub",
    "sub_sat",
    "to32",
    "wrap",
]


# =============================================================================================
# 상수
# =============================================================================================


def f_parse(s):
    """10진(또는 `0x` 16진) 문자열 상수를 64비트 정수로 바꾼다(컴파일 시점).

    `_`·`,`·공백은 무시한다. 음수는 2의 보수(`"-1"` = 2^64 − 1). 범위(−2^63 ~ 2^64−1) 밖·형식 오류는 EPError.
    인자: s(str) — 정수를 넘기면 범위만 검사해 그대로
    반환: int (0 ~ 2^64−1)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const k = i64.parse("12800000000");` (→ `i64.f_parse`)
    출처: CtrigAsm `I64("…")`(DPS war.py `i64` — Lua tonumber 규칙) 대체. 실수 문자열은 받지 않는다
    """
    if isinstance(s, bool):
        s = int(s)
    if isinstance(s, int):
        return _check_int(s, "i64.parse")
    if isinstance(s, bytes):
        s = s.decode("ascii", "replace")
    if not isinstance(s, str):
        fail("i64.parse: 문자열이 아닙니다 (%r)", s)
    t = s.strip().replace("_", "").replace(",", "").replace(" ", "")
    try:
        v = int(t, 0) if t.lower().lstrip("+-").startswith(("0x", "0b", "0o")) else int(t, 10)
    except ValueError:
        fail("i64.parse: 정수 문자열이 아닙니다 (%r)", s)
    return _check_int(v, "i64.parse")


parse = f_parse


def _check_int(v, fname):
    if not S64MIN <= v <= M64:
        fail("%s: 64비트 범위(−2^63 ~ 2^64−1) 밖의 상수 %d", fname, v)
    return v & M64


def _split(v):
    return v & M32, v >> 32


def _join(lo, hi):
    return (hi << 32) | lo


# =============================================================================================
# 피연산자 → (lo, hi) 반쪽. 반쪽은 32비트 int 또는 EUDVariable (배열 상수 칸은 _Cell)
# =============================================================================================


class _Cell:
    """메모리 칸 하나(EPD 상수식). 조건으로 읽고 상수 액션으로 쓸 수 있지만 SeqCompute 원천은 아니다."""

    __slots__ = ("epd",)

    def __init__(self, epd):
        self.epd = epd


def _isvar(h):
    return isinstance(h, EUDVariable)


def _isconst(h):
    return isinstance(h, int)


def _epd(h):
    if isinstance(h, _Cell):
        return h.epd
    return EPD(h.getValueAddr())


def _rd(h, cmp_, amount):
    return MemoryEPD(_epd(h), cmp_, amount)


def _act(h, mod, value):
    return SetMemoryEPD(_epd(h), mod, value)


def _dst(h):
    return h if _isvar(h) else _epd(h)


def _read_tmp(epd):
    t = EUDVariable()
    t << f_dwread_epd(epd)
    return t


def _halves(o, fname, what="피연산자"):
    """o → (lo, hi). 필요하면 임시 변수로 옮기는 트리거를 이 자리에 낸다."""
    if isinstance(o, Int64):
        return o.lo, o.hi
    u = unProxy(o)
    if isinstance(u, Int64):
        return u.lo, u.hi
    if isinstance(u, bool):
        u = int(u)
    if isinstance(u, int):
        return _split(_check_int(u, fname))
    if isinstance(u, (str, bytes)):
        return _split(f_parse(u))
    if u is None or isinstance(u, (float, EUDLightBool, Condition, list, tuple)):
        fail("%s: %s 로 쓸 수 없는 값입니다 (%r)", fname, what, u)
    if _compat.is_var(u):
        return unProxy(u), 0
    if _compat.is_varbase(u) or (hasattr(u, "getValueAddr") and not _compat.is_const(u)):
        return _read_tmp(EPD(u.getValueAddr())), 0
    if _compat.is_const(u):
        t = EUDVariable()
        t << u
        return t, 0
    fail("%s: %s 로 쓸 수 없는 값입니다 (%r)", fname, what, u)
    return None  # fail 은 돌아오지 않는다


def _half32(o, fname, what):
    """32비트 반쪽 하나 (정수는 −2^31 ~ 2^32−1)."""
    u = unProxy(o)
    if isinstance(u, Int64):
        fail("%s: %s 에 Int64 를 넣을 수 없습니다", fname, what)
    if isinstance(u, bool):
        u = int(u)
    if isinstance(u, int):
        if not -(1 << 31) <= u <= M32:
            fail("%s: %s 는 32비트 값이어야 합니다 (%d)", fname, what, u)
        return u & M32
    h, _z = _halves(u, fname, what)
    return h


def _both_const(p):
    return _isconst(p[0]) and _isconst(p[1])


def _same(p, q):
    return p[0] is q[0] and p[1] is q[1]


def _alias(dst, src):
    """dst 반쪽(변수)이 src 반쪽 중 어느 것과 같은 객체인가 (정확히 같은 쌍은 제외하고 부르는 쪽이 따로 본다)."""
    return any(d is s for d in dst for s in src if not _isconst(s))


# =============================================================================================
# 임시 변수 (빌드마다 새로. 인라인 연산 한 번 안에서만 쓰고, 조건이 읽지 않는다)
# =============================================================================================

_scr = []


def _scratch(n):
    while len(_scr) < n:
        _scr.append(EUDVariable())
    return _scr[:n]


@_compat.register_build_reset
def _reset_scratch():
    del _scr[:]


def _copy_pair(p, tmps):
    """p 를 tmps 두 변수로 옮기고 (tl, th) 반환 (상수 반쪽은 그대로)."""
    out, pairs = [], []
    for h, t in zip(p, tmps):
        if _isconst(h):
            out.append(h)
        else:
            pairs.append((t, SetTo, h))
            out.append(t)
    if pairs:
        SeqCompute(pairs)
    return tuple(out)


# =============================================================================================
# 대입
# =============================================================================================


def _assign(dl, dh, sl, sh):
    """(dl, dh) ← (sl, sh). dl, dh 는 EUDVariable. 반쪽이 서로 엇갈려도 맞게."""
    if sl is dl and sh is dh:
        return
    if sl is dh and sh is dl:
        (t,) = _scratch(1)
        SeqCompute([(t, SetTo, dl), (dl, SetTo, dh), (dh, SetTo, t)])
        return
    items = [(dl, sl), (dh, sh)]
    deps = sh is dl or sl is dh
    if sh is dl:
        items.reverse()  # dh ← (옛) dl 을 먼저
    pairs = [(d, SetTo, s) for d, s in items if s is not d]
    if not deps:
        pairs.sort(key=lambda p: 0 if _isconst(p[2]) else 1)
    for i, (d, m, s) in enumerate(pairs):
        if _isconst(s):
            pairs[i] = (d, m, s & M32)
    if pairs:
        SeqCompute(pairs)


# =============================================================================================
# 덧셈
# =============================================================================================


def _add_const(xl, xh, kl, kh):
    """x += K (x 반쪽은 변수 또는 _Cell). 호출 1~2 / 실행 1~2."""
    acts = []
    if kl:
        acts.append(_act(xl, Add, kl))
    if kh:
        acts.append(_act(xh, Add, kh))
    if acts:
        RawTrigger(actions=acts)
    if kl:
        RawTrigger(conditions=_rd(xl, AtMost, kl - 1), actions=_act(xh, Add, 1))  # 새 lo < kl → 올림


def _double(xl, xh):
    """x += x (같은 객체). hi 를 먼저 두 배로, 옛 lo 의 최상위 비트를 올리고, lo 를 두 배로. 호출 3 / 실행 5."""
    SeqCompute([(xh, Add, xh)])
    RawTrigger(conditions=xl.AtLeast(SIGN), actions=xh.AddNumber(1))
    SeqCompute([(xl, Add, xl)])


def _carry_fill(consts, vars_, rl, bl):
    """[bl > 새 rl] 올림 조건 (rl 이 채워진 뒤 읽음). 반환: 조건 목록."""
    c = MemoryEPD(_epd(bl), AtLeast, placeholder())
    amt = EPD(c) + 2
    consts.append((amt, SetTo, 1))
    vars_.append((amt, Add, rl))  # amt = 새 rl + 1 (rl = 0xFFFFFFFF 면 0 으로 돈다 → 막이 조건)
    return [c, MemoryEPD(amt, AtLeast, 1)]


def _iadd(xl, xh, yl, yh):
    """x += y (x 반쪽은 변수). 호출 2 / 실행 3~5."""
    if _isconst(yl) and _isconst(yh):
        _add_const(xl, xh, yl, yh)
        return
    if yl is xl and yh is xh:
        _double(xl, xh)
        return
    if _alias((xl, xh), (yl, yh)):
        yl, yh = _copy_pair((yl, yh), _scratch(2))
    consts, vars_ = [], []
    for d, s in ((xl, yl), (xh, yh)):
        if _isconst(s):
            if s:
                consts.append((d, Add, s))
        else:
            vars_.append((d, Add, s))
    if _isconst(yl):
        SeqCompute(consts + vars_)
        if yl:
            RawTrigger(conditions=xl.AtMost(yl - 1), actions=xh.AddNumber(1))
        return
    carry = _carry_fill(consts, vars_, xl, yl)
    SeqCompute(consts + vars_)
    RawTrigger(conditions=carry, actions=xh.AddNumber(1))


def _terms(consts, vars_, d, terms):
    """d ← terms 의 합 (정수는 SetTo 한 번에, 변수는 Add). d 는 새 변수(원천과 겹치지 않음)."""
    k = sum(t for t in terms if _isconst(t)) & M32
    vs = [t for t in terms if not _isconst(t)]
    consts.append((d, SetTo, k))
    for v in vs:
        vars_.append((d, Add, v))


def _add3(rl, rh, a, b):
    """r ← a + b (r 은 a, b 와 겹치지 않는 변수). 호출 2 / 실행 4~7."""
    al, ah = a
    bl, bh = b
    if _isconst(bl) and not _isconst(al):
        al, bl = bl, al
    # 이제 bl 이 변수이거나 둘 다 상수
    consts, vars_ = [], []
    if _isconst(al) and _isconst(bl):
        s = al + bl
        _terms(consts, vars_, rl, [s & M32])
        _terms(consts, vars_, rh, [ah, bh, s >> 32])
        SeqCompute(consts + vars_)
        return
    _terms(consts, vars_, rl, [al, bl])
    _terms(consts, vars_, rh, [ah, bh])
    if _isconst(al):
        SeqCompute(consts + vars_)
        if al:
            RawTrigger(conditions=rl.AtMost(al - 1), actions=rh.AddNumber(1))
        return
    carry = _carry_fill(consts, vars_, rl, bl)
    SeqCompute(consts + vars_)
    RawTrigger(conditions=carry, actions=rh.AddNumber(1))


# =============================================================================================
# wrap 뺄셈
# =============================================================================================


def _wsub_emit(rl, rh, init, yl, yh, tmps):
    """r ← (init 또는 r) − y (wrap). init = None(제자리) 또는 (lo 항 목록, hi 항 목록).

    lo: r.lo += ~y.lo + 1, 빌림 ⇔ 새 lo > ~y.lo (y.lo = 0 이면 ~y.lo = 0xFFFFFFFF 라 늘 거짓, 새 lo = 0 도 거짓).
    hi: r.hi += ~y.hi + 1, 빌림이면 −1. y 반쪽이 상수면 ~y + 1 을 상수로.
    """
    n, m = tmps
    consts, vars_, post = [], [], []
    if init is not None:
        lo_terms, hi_terms = init
        lo_terms = list(lo_terms)
        hi_terms = list(hi_terms)
    borrow = None
    # lo
    if _isconst(yl):
        k = (-yl) & M32
        if init is not None:
            lo_terms.append(k)
        elif k:
            consts.append((rl, Add, k))
        if yl:
            borrow = [rl.AtLeast((1 << 32) - yl)]  # 새 lo ≥ 2^32 − yl ⇔ 빌림
    else:
        if init is not None:
            lo_terms.append(1)
        else:
            consts.append((rl, Add, 1))
        consts.append((n, SetTo, M32))
        vars_.append((n, Subtract, yl))  # n = ~y.lo (0xFFFFFFFF ⊖ y 는 포화하지 않는다)
        c = MemoryEPD(EPD(n.getValueAddr()), AtMost, placeholder())
        amt = EPD(c) + 2
        consts.append((amt, SetTo, M32))
        post.append((rl, Add, n))
        post.append((amt, Add, rl))  # amt = 새 lo − 1
        borrow = [c, rl.AtLeast(1)]
    # hi
    if _isconst(yh):
        k = (-yh) & M32
        if init is not None:
            hi_terms.append(k)
        elif k:
            consts.append((rh, Add, k))
    else:
        if init is not None:
            hi_terms.append(1)
        else:
            consts.append((rh, Add, 1))
        consts.append((m, SetTo, M32))
        vars_.append((m, Subtract, yh))
        post.insert(0, (rh, Add, m))
    head_c, head_v = [], []
    if init is not None:
        _terms(head_c, head_v, rl, lo_terms)
        _terms(head_c, head_v, rh, hi_terms)
    pairs = head_c + consts + head_v + vars_ + post
    if pairs:
        SeqCompute(pairs)
    if borrow is not None:
        RawTrigger(conditions=borrow, actions=rh.AddNumber(M32))


@EUDFunc
def _wsub_fn(xl, xh, yl, yh):
    """공유 본문: (xl, xh) − (yl, yh) wrap."""
    _wsub_emit(xl, xh, None, yl, yh, (EUDVariable(), EUDVariable()))
    EUDReturn(xl, xh)


def _isub(xl, xh, yl, yh, inline=True):
    """x −= y (wrap, x 반쪽은 변수)."""
    if _isconst(yl) and _isconst(yh):
        k = (-_join(yl, yh)) & M64
        _add_const(xl, xh, *_split(k))
        return
    if yl is xl and yh is xh:
        _assign(xl, xh, 0, 0)
        return
    if not inline:
        _wsub_fn(xl, xh, yl, yh, ret=[xl, xh])
        return
    if _alias((xl, xh), (yl, yh)):
        yl, yh = _copy_pair((yl, yh), _scratch(4)[2:])
    _wsub_emit(xl, xh, None, yl, yh, _scratch(2))


def _ineg(xl, xh):
    """x ← −x 제자리: x ← ~x (0xFFFFFFFF ⊖ 반쪽 — 포화하지 않음), lo 가 0xFFFFFFFF 면 hi 올림, lo += 1. 호출 3 / 실행 7."""
    _ineg_with(xl, xh, *_scratch(2))


def _ineg_with(xl, xh, n, m):
    SeqCompute([(n, SetTo, M32), (m, SetTo, M32), (n, Subtract, xl), (m, Subtract, xh), (xl, SetTo, n), (xh, SetTo, m)])
    RawTrigger(conditions=xl.Exactly(M32), actions=xh.AddNumber(1))
    RawTrigger(actions=xl.AddNumber(1))


def _sub3(rl, rh, a, b, inline=True):
    """r ← a − b (wrap, r 은 a, b 와 겹치지 않는 변수)."""
    bl, bh = b
    if _isconst(bl) and _isconst(bh):
        _add3(rl, rh, a, _split((-_join(bl, bh)) & M64))
        return
    if _same(a, b):
        _assign(rl, rh, 0, 0)
        return
    if not inline:
        _wsub_fn(a[0], a[1], bl, bh, ret=[rl, rh])
        return
    _wsub_emit(rl, rh, ([a[0]], [a[1]]), bl, bh, _scratch(2))


# =============================================================================================
# 포화 뺄셈 (64비트 전체 기준)
# =============================================================================================


def _ssub_const(xl, xh, kl, kh):
    """x ← max(x − K, 0), K 상수 (S8 6.2 SK — 분기 없음, x 반쪽은 변수 또는 _Cell). 호출·실행 0~4."""
    if kl:  # x < K (hi 가 같거나 작고 빌림): 뒤 단계가 0 을 만들게 x ← (0, kl)
        RawTrigger(
            conditions=[_rd(xh, AtMost, kh), _rd(xl, AtMost, kl - 1)],
            actions=[_act(xh, SetTo, 0), _act(xl, SetTo, kl)],
        )
    if kh:  # hi 가 작음
        RawTrigger(conditions=_rd(xh, AtMost, kh - 1), actions=[_act(xh, SetTo, 0), _act(xl, SetTo, kl)])
    if kl:  # 빌림: 여기까지 오면 hi > kh 라 정확한 뺄셈
        RawTrigger(conditions=_rd(xl, AtMost, kl - 1), actions=_act(xh, Subtract, 1))
    acts = []
    if kl:
        acts.append(_act(xl, Add, (-kl) & M32))
    if kh:
        acts.append(_act(xh, Subtract, kh))  # hi ≥ kh 이거나 0 — 0 에서 멈추는 것이 곧 정답
    if acts:
        RawTrigger(actions=acts)


def _ssub_emit(xl, xh, yl, yh, tmps):
    """x ← max(x − y, 0) 제자리 (x 반쪽 변수, y 반쪽 변수 또는 상수 — 상수는 tmps 에 싣는다). 호출 3 / 실행 8~10.

    한 줄: amt2 ← 옛 x.hi + 1, x.hi ⊖= y.hi (포화), n ← ~y.lo, x.lo += n + 1 (wrap), amt1 ← 새 x.lo − 1.
    T_a [n ≤ amt1 ∧ 새 lo ≥ 1] (= 빌림) → x.hi −= 1 (wrap), amt2 −= 1 (wrap), 막이 조건 G 를 Always 로.
    T_c [y.hi ≥ amt2 ∧ G] → x ← 0.
      빌림 없음: amt2 = x.hi + 1, G = [amt2 ≥ 1] → x.hi < y.hi 일 때만 (x.hi = 0xFFFFFFFF 면 amt2 가 0 으로 돌아 G 가 막는다)
      빌림: amt2 = x.hi, G = Always → x.hi ≤ y.hi 일 때 (그때 x.hi(포화) = 0 이 wrap −1 로 0xFFFFFFFF 가 됐으니 0 으로)
    """
    n, sl, sh = tmps
    consts, vars_ = [], []
    if _isconst(yl):
        consts.append((sl, SetTo, yl))
        yl = sl
    if _isconst(yh):
        consts.append((sh, SetTo, yh))
        yh = sh
    c1 = MemoryEPD(EPD(n.getValueAddr()), AtMost, placeholder())
    amt1 = EPD(c1) + 2
    c2 = MemoryEPD(EPD(yh.getValueAddr()), AtLeast, placeholder())
    amt2 = EPD(c2) + 2
    guard = MemoryEPD(amt2, AtLeast, 1)
    consts += [
        (xl, Add, 1),
        (n, SetTo, M32),
        (amt1, SetTo, M32),
        (amt2, SetTo, 1),
        (EPD(guard) + 3, SetTo, _MEMGE_W),  # 막이 조건 되살림 (Memory, AtLeast)
    ]
    vars_ += [
        (amt2, Add, xh),  # 옛 hi
        (xh, Subtract, yh),  # 포화: 64비트 포화의 hi 반쪽 (3.5-7)
        (n, Subtract, yl),
        (xl, Add, n),
        (amt1, Add, xl),
    ]
    SeqCompute(consts + vars_)
    RawTrigger(
        conditions=[c1, xl.AtLeast(1)],
        actions=[xh.AddNumber(M32), SetMemoryEPD(amt2, Add, M32), SetMemoryEPD(EPD(guard) + 3, SetTo, _ALWAYS_W)],
    )
    RawTrigger(conditions=[c2, guard], actions=[xl.SetNumber(0), xh.SetNumber(0)])


@EUDFunc
def _ssub_fn(xl, xh, yl, yh):
    """공유 본문: max((xl, xh) − (yl, yh), 0)."""
    _ssub_emit(xl, xh, yl, yh, (EUDVariable(), EUDVariable(), EUDVariable()))
    EUDReturn(xl, xh)


def _isub_sat(xl, xh, yl, yh, inline=False):
    """x ← max(x − y, 0) (x 반쪽은 변수)."""
    if _isconst(yl) and _isconst(yh):
        _ssub_const(xl, xh, yl, yh)
        return
    if yl is xl and yh is xh:
        _assign(xl, xh, 0, 0)
        return
    if not inline:
        _ssub_fn(xl, xh, yl, yh, ret=[xl, xh])
        return
    if _alias((xl, xh), (yl, yh)):
        yl, yh = _copy_pair((yl, yh), _scratch(6)[4:])
    _ssub_emit(xl, xh, yl, yh, _scratch(3))


def _sub_sat3(rl, rh, a, b, inline=False):
    """r ← max(a − b, 0) (r 은 a, b 와 겹치지 않는 변수)."""
    bl, bh = b
    if _same(a, b):
        _assign(rl, rh, 0, 0)
        return
    if not inline and not (_isconst(bl) and _isconst(bh)):
        _ssub_fn(a[0], a[1], bl, bh, ret=[rl, rh])
        return
    _assign(rl, rh, *a)
    _isub_sat(rl, rh, bl, bh, inline=True)


# =============================================================================================
# 비교 (DPS_Enhance eudplib-port a7aad90 eud/ctrig/tlib.py:204~ "비교 계획")
#   원자: ("k", h, 비교, 상수) / ("vv", h1, 비교, h2) / ("gt", h1, h2).  목록 = AND, [] = 참, None = 거짓.
#   h = EUDVariable | _Cell(읽기만) | _Flip(값 + 2^31 을 자기 칸에 채워 읽음 — 부호 있는 비교의 hi)
# =============================================================================================

GE, LE, EQ = "ge", "le", "eq"
_SC = {GE: AtLeast, LE: AtMost, EQ: Exactly}
_SWAP = {GE: LE, LE: GE, EQ: EQ}


class _Flip:
    __slots__ = ("epd", "var")

    def __init__(self, var):
        self.var = var
        self.epd = None


def _pyop(x, c, y):
    return x >= y if c == GE else x <= y if c == LE else x == y


def _cmp(x, c, y):
    if _isconst(x) and _isconst(y):
        return [] if _pyop(x, c, y) else None
    if _isconst(x):
        x, y, c = y, x, _SWAP[c]
    if _isconst(y):
        if (c == GE and y == 0) or (c == LE and y == M32):
            return []
        return [("k", x, c, y)]
    if x is y:
        return []
    return [("vv", x, c, y)]


def _gt(x, y):
    if _isconst(x) and _isconst(y):
        return [] if x > y else None
    if _isconst(y):
        return None if y == M32 else [("k", x, GE, y + 1)]
    if _isconst(x):
        return None if x == 0 else [("k", y, LE, x - 1)]
    return None if x is y else [("gt", x, y)]


def _and(*parts):
    out = []
    for p in parts:
        if p is None:
            return None
        out += p
    return out


def _negate(a):
    if a[0] == "k":
        _, x, c, k = a
        if c == GE:
            return ("k", x, LE, k - 1) if k else None
        if c == LE:
            return ("k", x, GE, k + 1) if k != M32 else None
        return ("k", x, GE, 1) if k == 0 else ("k", x, LE, M32 - 1) if k == M32 else None
    if a[0] == "vv":
        _, x, c, y = a
        return ("gt", y, x) if c == GE else ("gt", x, y) if c == LE else None
    return ("vv", a[1], LE, a[2])


def _simplify(atoms):
    """같은 칸의 상수 비교를 한 구간으로 합친다. 빈 구간이면 None."""
    rng, order, rest = {}, [], []
    strict = {(id(a[1]), id(a[2])) for a in atoms if a[0] == "gt"}
    for a in atoms:
        if a[0] == "vv" and a[2] != EQ:
            x, y = (a[1], a[3]) if a[2] == GE else (a[3], a[1])
            if (id(x), id(y)) in strict:  # x ≥ y 는 x > y 에 들어 있다
                continue
        if a[0] != "k":
            rest.append(a)
            continue
        _, x, c, k = a
        if id(x) not in rng:
            rng[id(x)] = [x, 0, M32]
            order.append(id(x))
        r = rng[id(x)]
        if c != LE:
            r[1] = max(r[1], k)
        if c != GE:
            r[2] = min(r[2], k)
    out = []
    for key in order:
        x, lo, hi = rng[key]
        if lo > hi:
            return None
        if lo == hi:
            out.append(("k", x, EQ, lo))
            continue
        if lo:
            out.append(("k", x, GE, lo))
        if hi != M32:
            out.append(("k", x, LE, hi))
    return out + rest


def _source(h):
    """채우기 원천: (변수, 더할 상수) 또는 None(읽기만 되는 칸)."""
    if isinstance(h, _Flip):
        return h.var, SIGN
    if _isvar(h):
        return h, 0
    return None


def _read(plan, h, c, amount):
    """[h c amount] 조건 하나. _Flip 이면 첫 사용 때 자기 칸 조건을 만들고 채운다."""
    if isinstance(h, _Flip):
        if h.epd is None:
            cond = selfcond(_SC[c], amount)
            h.epd = EPD(cond)
            plan.fill(h.epd, h.var, SIGN)
            return cond
        return MemoryEPD(h.epd, _SC[c], amount)
    return MemoryEPD(_epd(h), _SC[c], amount)


def _pick(plan, x, y):
    """x 를 읽고 y 를 채울지(True), 반대로 할지(False). 둘 다 원천이 없으면 None."""
    sx, sy = _source(x), _source(y)
    if sy is None and sx is None:
        return None
    if sy is None:
        return False
    if sx is None:
        return True
    if plan.uses(sy[0]) and not plan.uses(sx[0]):
        return False
    if isinstance(x, _Flip) and x.epd is None and not (isinstance(y, _Flip) and y.epd is None):
        return False  # 이미 칸이 있는 쪽(또는 변수)을 읽는다
    return True


def _conds(plan, atoms):
    out = []
    for a in atoms:
        if a[0] == "k":
            out.append(_read(plan, a[1], a[2], a[3]))
            continue
        x, y = a[1], a[-1]
        way = _pick(plan, x, y)
        if way is None:  # 둘 다 읽기 전용 칸: 한쪽을 읽어 온다
            y = _read_tmp(_epd(y))
            way = True
        if a[0] == "vv":
            c = a[2]
            if way:
                cond = _read(plan, x, c, placeholder())
                src, add = _source(y)
            else:
                cond = _read(plan, y, _SWAP[c], placeholder())
                src, add = _source(x)
            plan.fill(EPD(cond) + 2, src, add)
            out.append(cond)
        elif way:  # x ≥ y + 1, 막이 [채움 ≥ 1] (y 가 최대값이면 0 으로 돈다)
            cond = _read(plan, x, GE, placeholder())
            src, add = _source(y)
            plan.fill(EPD(cond) + 2, src, add + 1)
            out += [cond, MemoryEPD(EPD(cond) + 2, AtLeast, 1)]
        else:  # y ≤ x − 1, 막이 [채움 ≤ 0xFFFFFFFE] (x 가 0 이면 돈다)
            cond = _read(plan, y, LE, placeholder())
            src, add = _source(x)
            plan.fill(EPD(cond) + 2, src, add + M32)
            out += [cond, MemoryEPD(EPD(cond) + 2, AtMost, M32 - 1)]
    return out


def _result(plan, base, neg):
    """결과 = base ∧ ¬neg → 조건 목록 (부정 부분은 자기 칸 깃발을 끄는 조건 트리거)."""
    if neg is not None:
        neg = _simplify(neg)
    if base is not None and neg is not None and len(neg) == 1:
        n = _negate(neg[0])
        if n is not None:
            base, neg = base + [n], None
    if base is not None:
        base = _simplify(base)
    if base is None or neg == []:
        return [Never()]
    conds = _conds(plan, base)
    if neg is None:
        return conds or [Always()]
    k, kepd = flag_cond(plan, 1)
    plan.trig(_conds(plan, neg), [SetMemoryEPD(kepd, SetTo, 0)])
    return conds + [k]


_MIRROR = {"le": "ge", "lt": "gt", "sle": "sge", "slt": "sgt"}
_REFLEXIVE = {"ge", "le", "eq", "sge", "sle"}


def _plan64(op, a, b):
    """op ∈ ge/gt/eq/ne/sge/sgt (le/lt 는 뒤집어서) → (base, neg)."""
    al, ah = a
    bl, bh = b
    signed = op[0] == "s"
    core = op[1:] if signed else op
    if core == "eq":
        return _and(_cmp(ah, EQ, bh), _cmp(al, EQ, bl)), None
    if core == "ne":
        return [], _and(_cmp(ah, EQ, bh), _cmp(al, EQ, bl))
    flips = {}

    def flip(h):
        if _isconst(h):
            return h ^ SIGN
        if not (_isvar(h)):
            h = _read_tmp(_epd(h))
        f = flips.get(id(h))
        if f is None:
            f = flips[id(h)] = _Flip(h)
        return f

    if signed:
        base = _cmp(flip(ah), GE, flip(bh))
        nh = _cmp(ah, EQ, bh)  # base 아래에서 [ah' ≤ bh'] ⇔ ah = bh
    else:
        base = _cmp(ah, GE, bh)
        nh = _cmp(ah, LE, bh)
    nl = _gt(bl, al) if core == "ge" else _cmp(al, LE, bl)
    return base, _and(nh, nl)


def _compare(op, a, b, fname):
    if op in _MIRROR:
        op, a, b = _MIRROR[op], b, a
    pa = _halves(a, fname, "a")
    pb = _halves(b, fname, "b")
    if _same(pa, pb) and not _both_const(pa):
        return Always() if op in _REFLEXIVE else Never()
    if _both_const(pa) and _both_const(pb):
        x, y = _join(*pa), _join(*pb)
        if op[0] == "s":
            x, y = x ^ (1 << 63), y ^ (1 << 63)
            op = op[1:]
        ok = {"ge": x >= y, "gt": x > y, "eq": x == y, "ne": x != y}[op]
        return Always() if ok else Never()
    plan = Plan()
    conds = _result(plan, *_plan64(op, pa, pb))
    plan.emit()
    return conds[0] if len(conds) == 1 else conds


def _cmpdoc(op, sign, sym):
    return (
        "a %s b (%s 64비트, 사전식 — hi 먼저). 모든 경계에서 정확하다.\n\n"
        "    인자: a, b — Int64, 정수 상수(−2^63 ~ 2^64−1), 10진 문자열, 32비트 변수(0 확장)\n"
        "    반환: 새 Condition 또는 조건 목록(AND). 상수끼리·같은 객체끼리는 Always()/Never().\n"
        "          앞 계산은 부르는 순간 낸다 → 돌려받은 조건은 꼭 한 번 트리거에 놓는다. 루프 조건은 조건 자리에서 부른다.\n"
        "    비용: 상수 = 호출 0~2 / 실행 0~2. 변수끼리 = 호출 2 / 실행 5%s (2026-09-17, docs/COSTS.md)\n"
        "    CP: 바꾸지 않음\n"
        "    로컬: 공유 안전\n"
        "    epScript: `if (i64.%s(a, b)) { … }` · `return i64.%s(a, b) ? 1 : 0;`%s\n"
        "    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/tlib.py:204 비교 계획, CtrigAsm TTNWar%s\n"
    ) % (
        sym,
        sign,
        " (부호 있음 = 호출 3 / 실행 7)" if sign == "부호 있는" else " (eq = 1 / 3)",
        op,
        op,
        "" if sign == "부호 있는" else " (Int64 끼리는 `a %s b` 연산자도 같다)" % sym,
        "(i>= 계열)" if sign == "부호 있는" else "",
    )


def f_ge(a, b):
    return _compare("ge", a, b, "i64.ge")


def f_le(a, b):
    return _compare("le", a, b, "i64.le")


def f_gt(a, b):
    return _compare("gt", a, b, "i64.gt")


def f_lt(a, b):
    return _compare("lt", a, b, "i64.lt")


def f_eq(a, b):
    return _compare("eq", a, b, "i64.eq")


def f_ne(a, b):
    return _compare("ne", a, b, "i64.ne")


def f_sge(a, b):
    return _compare("sge", a, b, "i64.sge")


def f_sle(a, b):
    return _compare("sle", a, b, "i64.sle")


def f_sgt(a, b):
    return _compare("sgt", a, b, "i64.sgt")


def f_slt(a, b):
    return _compare("slt", a, b, "i64.slt")


for _f, _o, _s, _y in (
    (f_ge, "ge", "부호 없는", "≥"),
    (f_le, "le", "부호 없는", "≤"),
    (f_gt, "gt", "부호 없는", ">"),
    (f_lt, "lt", "부호 없는", "<"),
    (f_eq, "eq", "부호 없는", "="),
    (f_ne, "ne", "부호 없는", "≠"),
    (f_sge, "sge", "부호 있는", "≥"),
    (f_sle, "sle", "부호 있는", "≤"),
    (f_sgt, "sgt", "부호 있는", ">"),
    (f_slt, "slt", "부호 있는", "<"),
):
    _f.__doc__ = _cmpdoc(_o, _s, _y)
del _f, _o, _s, _y


# =============================================================================================
# 10진 출력 (DPS_Enhance eudplib-port a7aad90 eud/ctrig/text.py:381 `_lidec_ops` 를 부호 없는 판으로 다시 짬)
# =============================================================================================

_LIDEC_WORDS = [EUDVariable() for _ in range(5)]
_LIDEC_LEAD = EUDVariable()
_SLIDEC_WORDS = [EUDVariable() for _ in range(5)]
_SLIDEC_LEAD = EUDVariable()


def _lidec_steps():
    """(자리 i, 비트 b, 상수 c = b·10^i, hi 가 0 인가) 목록. 단 시작 때 값 < 2c 가 늘 성립한다."""
    out = []
    for i in range(19, -1, -1):
        for b in (8, 4, 2, 1):
            c = b * 10**i
            if c > M64:
                continue
            out.append((i, b, c, 2 * c - 1 <= M32))
    return out


def _lidec_code(lo, hi, w, lead):
    """lo·hi(소모됨) → w0~w4(20자리 10진 ASCII, 앞은 '0'), lead(앞자리 '0' 수 0~19). 트리거 약 136."""
    RawTrigger(actions=[x.SetNumber(0x30303030) for x in w] + [lead.SetNumber(0)])
    for i, b, c, hizero in _lidec_steps():
        pos = 19 - i  # 바이트 위치 (0 = 10^19 자리)
        word, sh = w[pos // 4], 8 * (pos % 4)
        cl, ch = _split(c)
        if hizero:  # 값 < 2^32 (hi = 0)
            RawTrigger(conditions=lo.AtLeast(cl), actions=[lo.SubtractNumber(cl), word.AddNumber(b << sh)])
            continue
        # 값 ≥ c 를 둘로 나눈 배타 트리거 (한쪽이 빼면 값 < c 라 다른 쪽은 거짓). 조건이 값 ≥ 빼는 값을 보장한다(3.5-7)
        conds = [lo.AtLeast(cl)] if cl else []
        if ch:
            conds.insert(0, hi.AtLeast(ch))
        acts = [lo.SubtractNumber(cl)] if cl else []
        if ch:
            acts.append(hi.SubtractNumber(ch))
        RawTrigger(conditions=conds, actions=acts + [word.AddNumber(b << sh)])
        if cl and ch < M32:  # 빌림: hi ≥ ch + 1, lo < cl (이 표에서 ch 는 늘 0x8AC72304 이하)
            RawTrigger(
                conditions=[hi.AtLeast(ch + 1), lo.AtMost(cl - 1)],
                actions=[hi.SubtractNumber(ch + 1), lo.AddNumber((-cl) & M32), word.AddNumber(b << sh)],
            )
    for j in range(19):
        word, sh = w[j // 4], 8 * (j % 4)
        RawTrigger(
            conditions=[lead.Exactly(j), word.ExactlyX(0x30 << sh, 0xFF << sh)],
            actions=lead.AddNumber(1),
        )


@EUDFunc
def _lidec_body(lo, hi):
    """lo·hi(인자 사본, 소모됨) → 반환 w0~w4(20자리 10진 ASCII, 앞은 '0'), lead(앞자리 '0' 수 0~19)."""
    _lidec_code(lo, hi, _LIDEC_WORDS, _LIDEC_LEAD)


@EUDFunc
def _slidec_body(lo, hi):
    """부호 있는 판: 음수면 절댓값을 바꾸고, 첫 숫자 바로 앞의 '0' 을 '-' 로 바꾼 뒤 lead 를 1 줄인다.

    |x| ≤ 2^63 은 19자리 이하라 lead ≥ 1 이다. '0'(0x30) → '-'(0x2D) 는 그 바이트에 −3 을 더한다(빌림 없음).
    """
    w, lead = _SLIDEC_WORDS, _SLIDEC_LEAD
    sg, n, m = EUDVariable(), EUDVariable(), EUDVariable()
    RawTrigger(actions=sg.SetNumber(0))
    if EUDIf()(hi.AtLeast(SIGN)):
        _ineg_with(lo, hi, n, m)
        RawTrigger(actions=sg.SetNumber(1))
    EUDEndIf()
    _lidec_code(lo, hi, w, lead)
    for j in range(1, 20):  # 오름차순: 한 번 바꾸면 sg ← 0
        word, sh = w[(j - 1) // 4], 8 * ((j - 1) % 4)
        RawTrigger(
            conditions=[sg.Exactly(1), lead.Exactly(j)],
            actions=[word.AddNumber((-3 << sh) & M32), lead.AddNumber(M32), sg.SetNumber(0)],
        )


_compat.predefine_returns(_lidec_body, _LIDEC_WORDS + [_LIDEC_LEAD])
_compat.predefine_returns(_slidec_body, _SLIDEC_WORDS + [_SLIDEC_LEAD])


def f_lidec_to(dst_epd, lo, hi, *, signed=False, lead=None):
    """64비트 값(lo, hi)을 20자리 10진 ASCII(앞을 '0' 으로 채움)로 dst_epd 부터 5칸(20바이트)에 쓴다.

    numfmt(WP5)가 쓰는 공용 본문의 경계다. 앞자리 수 lead(0~19)를 돌려준다 → 숫자 시작 = dst + lead 바이트.
    signed=True 면 hi 의 최상위 비트를 부호로 읽어 절댓값을 쓰고, 음수면 첫 숫자 바로 앞 바이트를 '-' 로 바꿔
    lead 가 그 '-' 를 가리킨다(|x| ≤ 2^63 은 19자리 이하라 자리가 늘 있다).
    dst_epd 뒤의 21번째 바이트 이후는 건드리지 않는다(NUL 은 부르는 쪽이 둔다).
    인자: dst_epd(상수 EPD — 칸 0~4 에 결과 변수가 바로 쓴다. 변수면 f_dwwrite_epd 5번), lo, hi(상수·변수),
          signed(bool), lead(선택: 결과를 받을 EUDVariable)
    반환: EUDVariable (lead)
    비용: 본문 약 140(부호 있음 약 170, 1벌) / 호출 1 / 실행 약 150(부호 있음 +7~30) (2026-09-17, docs/COSTS.md).
          변수 dst 는 + f_dwwrite_epd × 5
    CP: 바꾸지 않음 (변수 dst 는 f_dwwrite_epd 가 잠깐 옮기고 되돌림)
    로컬: 공유 안전 (버퍼가 로컬 전용이면 로컬 블록 안에서)
    epScript: `const n = i64.lidec_to(EPD(buf), x.lo, x.hi);`
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/text.py:381 `_lidec_ops`(부호 있는 20바이트 고정 폭)를
          배타 트리거 두 개 단·앞자리 수 반환으로 다시 짬
    """
    if not isinstance(signed, bool):
        fail("i64.lidec_to: signed 는 True/False 여야 합니다 (%r)", signed)
    if lead is None:
        lead = EUDVariable()
    elif not _isvar(unProxy(lead)):
        fail("i64.lidec_to: lead 는 EUDVariable 이어야 합니다 (%r)", lead)
    body = _slidec_body if signed else _lidec_body
    lo, hi = unProxy(lo), unProxy(hi)
    dst = unProxy(dst_epd)
    if _compat.is_const(dst) and not _isvar(dst):
        body(lo, hi, ret=[dst + k for k in range(5)] + [lead])
        return lead
    words = [EUDVariable() for _ in range(5)]
    body(lo, hi, ret=words + [lead])
    for k, wv in enumerate(words):
        f_dwwrite_epd(dst + k, wv)
    return lead


lidec_to = f_lidec_to


def f_fmt(x, signed=False):
    """Int64(또는 64비트 값)의 10진 문자열을 이 호출 자리의 24바이트 버퍼에 쓰고 `ptr2s` 를 돌려준다.

    eudplib 인쇄 함수(`f_dbstr_print`, `f_sprintf`, `f_cpstr_print`, `f_eprintln`, `StringBuffer.printf`,
    `printAll`)가 그대로 받는다. 한 print 에 `fmt()` 가 여러 개여도 버퍼가 따로라 맞다(epScript 는 인자를 먼저 계산한다).
    상수는 컴파일 시점에 문자열로 바꿔 돌려준다(트리거 0).
    인자: x(Int64·상수·문자열·32비트 변수), signed(bool: True 면 hi 의 최상위 비트를 부호로 — "-5")
    반환: ptr2s(버퍼 + 앞자리 수) 또는 str(상수)
    비용: 호출 2 / 실행 약 150 (부호 있음 약 160~180), 버퍼 24B. 본문 `lidec_to` 1벌씩 (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전 (인쇄는 eudplib 규칙대로)
    epScript: `printAll("HP {}", hp.fmt());` · `printAll("{}", i64.fmt(x, signed=True));`
    출처: DESIGN 3.2-7, eudplib 0.81 `string/eudprint.py:230` (fmt 훅)
    """
    if not isinstance(signed, bool):
        fail("i64.fmt: signed 는 True/False 여야 합니다 (%r)", signed)
    lo, hi = _halves(x, "i64.fmt")
    if _isconst(lo) and _isconst(hi):
        v = _join(lo, hi)
        return str(v - (1 << 64) if signed and v >> 63 else v)
    buf = Db(24)
    e = EPD(buf)
    p = EUDVariable()
    (_slidec_body if signed else _lidec_body)(lo, hi, ret=[e + k for k in range(5)] + [p])
    RawTrigger(actions=p.AddNumber(buf))
    return ptr2s(p)


fmt = f_fmt


# =============================================================================================
# 2차(WP4) 공용: 곱셈·나눗셈·시프트 본문은 단계마다 조건 트리거 하나와 변수 트리거 사슬로 짠다
# (`_parts.SelfFrame`·`var_chain`·결정 나무). 조건이 참인 트리거는 액션으로 자기 next 를 사슬 첫 변수 트리거로 바꾸고
# (방문 1), 그 사슬의 끝은 다음 단계로 간다. 바뀐 next 는 매 호출 첫머리의 되돌림 묶음이 제자리로 돌린다. 쓰는 기법은
# eudplib 자신이 쓰는 것뿐이다(`_eud_mul`·`_eud_div` 의 SetNextPtr 자기 수정, 조건 amount·액션 값 칸 채우기,
# VProc 의 변수 트리거 사슬) — 인게임 새 가정 없음.
# =============================================================================================

M16 = 0xFFFF
S63 = 1 << 63
_DIV0 = ("eudplib", "ctrig")


def _pairs(*ps):
    """원천·목적지가 모두 있는 (원천, 목적지) 쌍만."""
    return [p for p in ps if p[0] is not None and p[1] is not None]


# 공용 부품 (`_parts`, WP4 에서 더함): 짧은 이름으로 쓴다
_addmods = add_modifiers
_chain = var_chain
_Frame = SelfFrame
_TNode = DNode
_TLeaf = DLeaf
_tlab = dlabel
_tgoto = dgoto
_spine = dspine
_presets = dpresets
_tree = dtree
_emit_tree = emit_dtree


def _dbl64(xl, xh):
    """x ← 2x (64비트 wrap) 제자리. 실행 4: 준비 → xh 변수 → [옛 xl 최상위 비트] xh += 1 → xl 변수. 트리거 2."""
    tm, nxt = Forward(), Forward()
    RawTrigger(
        nextptr=xh.GetVTable(),
        actions=[
            xh.SetDest(xh),
            xh.SetModifier(Add),
            SetNextPtr(xh.GetVTable(), tm),
            xl.SetDest(xl),
            xl.SetModifier(Add),
            SetNextPtr(xl.GetVTable(), nxt),
        ],
    )
    tm << RawTrigger(nextptr=xl.GetVTable(), conditions=xl.AtLeastX(1, SIGN), actions=xh.AddNumber(1))
    nxt << NextTrigger()


def _new_vars(n):
    return tuple(EUDVariable() for _ in range(n))


def _const_pair(p):
    return _join(*p) if _both_const(p) else None


def _put(dl, dh, p):
    """(dl, dh) ← p (반쪽 상수·변수). `_assign` 과 같다."""
    _assign(dl, dh, *p)


# =============================================================================================
# 곱셈 (DESIGN 4.4 — 16비트 쪼개기, G3 1.10 제안)
#
# a × b mod 2^64, a = (al, ah), al = a0 + a1·2^16 (16비트 두 조각), b = (bl, bh), bh = c0 + c1·2^16.
#   al·bl = a0·b0 + (a1·b0 + a0·b1)·2^16 + a1·b1·2^32,  (ah·bl + al·bh)·2^32 은 하위 32비트만 쓴다.
# 곱하는 수의 비트 i 마다(조건 트리거 하나) 두 배씩 늘어나는 t0 = a0·2^i, t1 = a1·2^i, h0 = ah·2^i 를 누적기에 더한다:
#   bl 비트 i    → rl += t0, m0 += t1, rh += h0       bl 비트 16+i → m1 += t0, rh += t1, z += h0
#   bh 비트 i    → rh += t0, z += t1                   bh 비트 16+i → z += t0
# t0·t1 < 2^32 이고 m0 = a1·b0, m1 = a0·b1, a0·b0 < 2^32 라 넘치지 않는다. rh(가중치 2^32)·z(2^48, 하위 16비트만)는 wrap.
# 끝에서 m0 + m1(33비트, 가중치 2^16)을 rl·rh 로, z 의 하위 16비트를 rh 로 옮긴다. 남은 비트가 없으면 일찍 끝낸다.
# war.py `_mul64`(a7aad90: 32×32 비트 루프 + f_mul 2번) 은 올림을 단계마다 처리했다 — 여기서는 누적기가 넘치지 않게 나눠
# 단계마다 조건 트리거 + 변수 사슬만 돈다.
# =============================================================================================


def _split16(fr, t0, t1):
    """t0 → t0(하위 16비트), t1(상위 16비트, 처음 0). t0 < 2^16 이면 건너뛴다(실행 1). 그 밖에 실행 1 + 16."""
    skip = Forward()
    fr.node([t0.AtMost(M16)], skip)
    for j in range(31, 15, -1):
        RawTrigger(conditions=t0.AtLeastX(1, 1 << j), actions=[t1.AddNumber(1 << (j - 16)), t0.SetNumberX(0, 1 << j)])
    skip << NextTrigger()


def _mul_tail(fr, rl, rh, m0, m1, z, L, c2, amt2):
    """m0 + m1 (가중치 2^16) 과 z (가중치 2^48, 하위 16비트) 를 rl·rh 에 더한다.

    m1 → m0 (올림 → rh += 2^16), m0 상위 16비트 → rh, m0 하위 16비트 << 16 → L, rl += L (올림 → rh += 1: 조건 c2 =
    [rl ≤ L − 1] 의 amount 칸 amt2 를 M32 에서 시작해 L 과 같이 더해 둔다), z 비트 0~15 → rh += 2^(16+j).
    실행: m1 = 0 이면 1, 아니면 1 + 4 / m0 = 0 이면 1, 아니면 1 + 16 + 1 + 16 + 3 / z 하위 = 0 이면 1, 아니면 1 + 16.
    """
    if m1 is not None and m0 is not None:
        skip = Forward()
        fr.node([m1.Exactly(0)], skip)
        c = MemoryEPD(EPD(m1.getValueAddr()), AtLeast, placeholder())
        amt = EPD(c) + 2
        SeqCompute([(amt, SetTo, 1), (m0, Add, m1), (amt, Add, m0)])
        RawTrigger(conditions=[c, MemoryEPD(amt, AtLeast, 1)], actions=rh.AddNumber(0x10000))
        skip << NextTrigger()
    m = m0 if m0 is not None else m1
    if m is not None:
        skip = Forward()
        fr.node([m.Exactly(0)], skip)
        for j in range(31, 15, -1):
            RawTrigger(conditions=m.AtLeastX(1, 1 << j), actions=rh.AddNumber(1 << (j - 16)))
        skip2 = Forward()
        fr.node([m.ExactlyX(0, M16)], skip2)
        for j in range(15, -1, -1):
            RawTrigger(
                conditions=m.AtLeastX(1, 1 << j),
                actions=[L.AddNumber(1 << (j + 16)), SetMemoryEPD(amt2, Add, 1 << (j + 16))],
            )
        SeqCompute([(rl, Add, L)])
        RawTrigger(conditions=[c2, L.AtLeast(1)], actions=rh.AddNumber(1))
        skip2 << NextTrigger()
        skip << NextTrigger()
    if z is not None:
        skip = Forward()
        fr.node([z.ExactlyX(0, M16)], skip)
        for j in range(15, -1, -1):
            RawTrigger(conditions=z.AtLeastX(1, 1 << j), actions=rh.AddNumber(1 << (j + 16)))
        skip << NextTrigger()


def _mul_emit(t0, h0, bl, bh, rl, rh):
    """변수 × 변수 곱 본문. t0·h0 = 곱해지는 수 lo·hi(소모, h0 없으면 None), bl·bh = 곱하는 수(bh 없으면 None).

    rl, rh 는 목적지로만 쓴다(미리 정한 반환 변수). 실행(에뮬레이터, 2026-09-17): 64×64 최악 약 300.
    """
    has_h, has_b = h0 is not None, bh is not None
    t1, m0, m1, L = _new_vars(4)
    z = EUDVariable() if (has_h or has_b) else None
    c2 = MemoryEPD(EPD(rl.getValueAddr()), AtMost, placeholder())
    amt2 = EPD(c2) + 2
    init = [rl.SetNumber(0), rh.SetNumber(0), t1.SetNumber(0), m0.SetNumber(0), m1.SetNumber(0), L.SetNumber(0)]
    init += [SetMemoryEPD(amt2, SetTo, M32), *_addmods(t0, t1, h0)]
    if z is not None:
        init.append(z.SetNumber(0))
    fr = _Frame(init)
    _split16(fr, t0, t1)
    exit_ = Forward()
    for i in range(16):
        fr.test([bl.AtLeastX(1, 1 << i)], _pairs((t0, rl), (t1, m0), (h0, rh)))
        fr.test([bl.AtLeastX(1, 1 << (i + 16))], _pairs((t0, m1), (t1, rh), (h0, z)))
        if has_b:
            fr.test([bh.AtLeastX(1, 1 << i)], [(t0, rh), (t1, z)])
            fr.test([bh.AtLeastX(1, 1 << (i + 16))], [(t0, z)])
        if i == 15:
            break
        rest = ((M16 << (i + 1)) & M16) * 0x10001  # 남은 비트: i+1~15, 17+i~31
        dbl = _pairs((t0, t0), (t1, t1), (h0, h0))
        nxt = Forward()
        first, acts = _chain(dbl, nxt)
        if has_b:
            d2 = Forward()
            fr.node([bl.AtLeastX(1, rest)], first, acts, false_next=d2)
            d2 << NextTrigger()
            first2, acts2 = _chain(dbl, nxt)
            fr.node([bh.AtLeastX(1, rest)], first2, acts2, false_next=exit_)
        else:
            fr.node([bl.AtLeastX(1, rest)], first, acts, false_next=exit_)
        nxt << NextTrigger()
    exit_ << NextTrigger()
    _mul_tail(fr, rl, rh, m0, m1, z, L, c2, amt2)
    fr.finish()


@functools.cache
def _mul_fn(has_h, has_b):
    """변수 × 변수 공유 본문 (has_h: 곱해지는 수에 hi 가 있음, has_b: 곱하는 수에 hi 가 있음). 반환 (lo, hi)."""
    rl, rh = EUDVariable(), EUDVariable()
    if has_h and has_b:

        def i64_mul_6464(al, ah, bl, bh):
            _mul_emit(al, ah, bl, bh, rl, rh)

        f = i64_mul_6464
    elif has_h:

        def i64_mul_6432(al, ah, bl):
            _mul_emit(al, ah, bl, None, rl, rh)

        f = i64_mul_6432
    else:

        def i64_mul_3232(al, bl):
            _mul_emit(al, None, bl, None, rl, rh)

        f = i64_mul_3232
    f = EUDFunc(f)
    _compat.predefine_returns(f, [rl, rh])
    return f


# --- 상수 곱 ---
# (1) 비트 누적(BT): x 의 비트 i 마다 조건 트리거 하나가 상수 T_i = K·2^i mod 2^64 의 조각을 더한다.
#     rl += (T_i 하위 32비트의 하위 27비트), F += (하위 32비트 >> 27), rh += (T_i 상위 32비트).
#     x 의 하위 32비트만 하위 조각이 있으므로 rl < 32·2^27 = 2^32, F < 2^10 로 넘치지 않는다.
#     끝에서 F·2^27 을 rl(올림 → rh)·rh 로 옮긴다. K 와 무관하게 실행 약 80(64비트 x), 50(32비트 x).
# (2) 배가·덧셈(SA): K 가 작으면 NAF(부호 있는 이진) 자릿수대로 r = 2r ± x. 이식판 `arith.py` `_mul_small` 을 64비트로.
# 둘 중 최악 실행 추정이 작은 쪽을 고른다. 0·1·2^s·−1 은 따로(트리거 0~몇 개).


def _bt_cost(K, has_h):
    words = 2 if has_h else 1
    trig = sum(1 for i in range(32 * words) if (K << i) & M64)
    fcount = any(((K << i) & M32) >> 27 for i in range(32))
    return 3 + 2 * words + trig + (14 if fcount else 0)


def _naf(k):
    """k 의 NAF 자릿수 (아래 자리부터, −1/0/1)."""
    out = []
    while k:
        if k & 1:
            d = 2 - (k & 3)
            k -= d
        else:
            d = 0
        out.append(d)
        k >>= 1
    return out


def _sa_digits(k1):
    """홀수 k1 → 윗자리부터 자릿수(첫 자리 1). 이진·NAF 중 실행이 적은 쪽."""
    binary = [int(c) for c in bin(k1)[2:]]
    naf = _naf(k1)[::-1]

    def cost(ds):
        return 4 * (len(ds) - 1) + sum(5 if d == 1 else 7 if d == -1 else 0 for d in ds[1:])

    return min((binary, naf), key=cost)


def _shl_cost(s):
    if s == 0:
        return 0
    if s >= 32:
        m = s - 32
        return 3 + min(2 * m, 33 - m if m else 0)
    return min(4 * s, 65 - s)


def _sa_cost(K):
    s = (K & -K).bit_length() - 1
    ds = _sa_digits(K >> s)
    return 6 + 4 * (len(ds) - 1) + sum(5 if d == 1 else 7 if d == -1 else 0 for d in ds[1:]) + _shl_cost(s)


def _mulk_bt_emit(xl, xh, K, rl, rh):
    use_f = any(((K << i) & M32) >> 27 for i in range(32))
    init = [rl.SetNumber(0), rh.SetNumber(0)]
    if use_f:
        F, L = EUDVariable(), EUDVariable()
        c2 = MemoryEPD(EPD(rl.getValueAddr()), AtMost, placeholder())
        amt2 = EPD(c2) + 2
        init += [F.SetNumber(0), L.SetNumber(0), SetMemoryEPD(amt2, SetTo, M32)]
    fr = _Frame(init)
    for word, base in ((xh, 32), (xl, 0)):
        if word is None:
            continue
        for half in (1, 0):
            trigs = []
            for j in range(15, -1, -1):
                bit = 16 * half + j
                t = (K << (base + bit)) & M64
                lo, hi = t & M32, t >> 32
                acts = []
                if lo & 0x7FFFFFF:
                    acts.append(rl.AddNumber(lo & 0x7FFFFFF))
                if lo >> 27:
                    acts.append(F.AddNumber(lo >> 27))
                if hi:
                    acts.append(rh.AddNumber(hi))
                if acts:
                    trigs.append((bit, acts))
            if not trigs:
                continue
            skip = Forward()
            fr.node([word.ExactlyX(0, M16 << (16 * half))], skip)
            for bit, acts in trigs:
                RawTrigger(conditions=word.AtLeastX(1, 1 << bit), actions=acts)
            skip << NextTrigger()
    if use_f:
        skip = Forward()
        fr.node([F.Exactly(0)], skip)
        for j in range(9, 4, -1):
            RawTrigger(conditions=F.AtLeastX(1, 1 << j), actions=rh.AddNumber(1 << (j - 5)))
        for j in range(4, -1, -1):
            RawTrigger(
                conditions=F.AtLeastX(1, 1 << j),
                actions=[L.AddNumber(1 << (27 + j)), SetMemoryEPD(amt2, Add, 1 << (27 + j))],
            )
        SeqCompute([(rl, Add, L)])
        RawTrigger(conditions=[c2, L.AtLeast(1)], actions=rh.AddNumber(1))
        skip << NextTrigger()
    fr.finish()


def _mulk_sa_emit(xl, xh, K):
    s = (K & -K).bit_length() - 1
    ds = _sa_digits(K >> s)
    rl, rh = EUDVariable(), EUDVariable()
    SeqCompute([(rl, SetTo, xl), (rh, SetTo, 0 if xh is None else xh)])
    yh = 0 if xh is None else xh
    for d in ds[1:]:
        _dbl64(rl, rh)
        if d == 1:
            _iadd(rl, rh, xl, yh)
        elif d == -1:
            _isub(rl, rh, xl, yh)
    _shl_k_emit(rl, rh, s)
    EUDReturn(rl, rh)


@functools.cache
def _mulk_fn(K, has_h, method):
    """상수 K 곱 공유 본문 (K 마다 한 벌). method = "bt" | "sa"."""
    if method == "bt":
        rl, rh = EUDVariable(), EUDVariable()
        if has_h:

            def i64_mulk(xl, xh):
                _mulk_bt_emit(xl, xh, K, rl, rh)

        else:

            def i64_mulk(xl):
                _mulk_bt_emit(xl, None, K, rl, rh)

        f = EUDFunc(i64_mulk)
        _compat.predefine_returns(f, [rl, rh])
        return f
    if has_h:

        def i64_mulk_sa(xl, xh):
            _mulk_sa_emit(xl, xh, K)

    else:

        def i64_mulk_sa(xl):
            _mulk_sa_emit(xl, None, K)

    return EUDFunc(i64_mulk_sa)


def _mul_into(dl, dh, pa, pb):
    """(dl, dh) ← a × b mod 2^64. dl, dh 는 변수(a·b 반쪽과 같아도 된다 — 공유 함수는 인자를 먼저 복사한다)."""
    ka, kb = _const_pair(pa), _const_pair(pb)
    if ka is not None and kb is not None:
        _put(dl, dh, _split((ka * kb) & M64))
        return
    if ka is not None:
        pa, pb, kb = pb, pa, ka
    al, ah = pa
    if kb is not None:
        _mulk_into(dl, dh, al, ah, kb)
        return
    bl, bh = pb
    has_h = not (_isconst(ah) and ah == 0)
    has_b = not (_isconst(bh) and bh == 0)
    if has_b and not has_h:
        al, ah, bl, bh = bl, bh, al, ah
        has_h, has_b = True, False
    args = [al] + ([ah] if has_h else []) + [bl] + ([bh] if has_b else [])
    _mul_fn(has_h, has_b)(*args, ret=[dl, dh])


def _mulk_into(dl, dh, xl, xh, K):
    K &= M64
    if K == 0:
        _put(dl, dh, (0, 0))
        return
    if K == 1:
        _put(dl, dh, (xl, xh))
        return
    if K == M64:
        if dl is xl and dh is xh:
            _ineg(dl, dh)
        else:
            _sub_into(dl, dh, (0, 0), (xl, xh))
        return
    if K & (K - 1) == 0:
        _shift_into("shl", dl, dh, (xl, xh), K.bit_length() - 1)
        return
    if _isconst(xl):  # 하위가 상수, 상위만 변수: 상위 쪽 곱만 변수
        xl, xh = _var_or_tmp(xl), xh
    has_h = not (_isconst(xh) and xh == 0)
    if _isconst(xh) and has_h:
        xh = _var_or_tmp(xh)
    method = "sa" if _sa_cost(K) < _bt_cost(K, has_h) else "bt"
    args = [xl] + ([xh] if has_h else [])
    _mulk_fn(K, has_h, method)(*args, ret=[dl, dh])


def _var_or_tmp(h):
    if not _isconst(h):
        return h
    t = EUDVariable()
    t << h
    return t


def _sub_into(dl, dh, pa, pb):
    """(dl, dh) ← a − b (wrap). 겹치면 새 변수를 거친다."""
    if _alias((dl, dh), pa + pb):
        tl, th = _new_pair()
        _sub3(tl, th, pa, pb)
        _assign(dl, dh, tl, th)
        return
    _sub3(dl, dh, pa, pb)


# =============================================================================================
# 나눗셈 (부호 없음) — DPS_Enhance eudplib-port a7aad90 `eud/ctrig/war.py:347~420` `_divmod64` 3경로
# (제수 0 / 32비트 제수 / 64비트 제수)와 `divide.py`·`_cdiv`(상수 제수, a41d2ed 다시 짠 판)를 옮기고,
# 변수 제수의 한 단을 "공유 비교 트리거"로 줄였다(war.py `_div6432` 단당 약 11 → 4~5, `_div64big` 약 16 → 6~11).
#
# 32비트 제수 d (1 ≤ d < 2^32): 나머지 r(< d)에 피제수 비트를 하나씩 밀어 넣고(r = 2r + 비트) r ≥ d 면 뺀다.
#   d ≤ 2^31 이면 2r + 1 < 2^32 라 넘치지 않는다(단계 A). d > 2^31 은 옛 r ≥ 2^31 을 먼저 보고(넘침 = 반드시 뺌)
#   하위 32단만 돈다 — 상위 몫은 nh ≥ d 면 1(단계 B).
#   한 단 = 준비(공유 트리거 CMP·ND·R 의 next 와 CMP 몫 액션 칸을 이 단으로) → R(r += r) → S0([비트] r += 1)
#   → CMP([r ≥ d] 몫 += 비트, next → ND) → ND(r += −d) → 다음 단. d 는 CMP 조건 amount 칸에 한 번만 채운다.
#   r = 0 에서 시작하는 단어는 결정 나무로 최상위 비트 단계부터 들어간다(앞 0 비트 건너뛰기).
# 64비트 제수 D (dh ≥ 1): 몫 < 2^32. R = (0, nh) 에서 nl 의 32비트를 밀어 넣는다. dh < 2^31 이면 R < 2^63 라 넘치지 않는다.
#   한 단 = 준비 → RH(rh += rh) → TC([옛 rl ≥ 2^31] rh += 1) → RL(rl += rl) → S0 → K0([rh ≤ dh−1] → 다음 단)
#   → K1([rh ≥ dh+1][rl ≥ dl] → VA·VB) → K2([rh ≥ dh+1][rl ≤ dl−1] → VA·VC(빌림)) → K3([rl ≥ dl] → VA·VB) → 다음 단.
#   dh ≥ 2^31 이면 몫은 0 또는 1 이다(n < 2^64 ≤ 2D).
# 0 나눗셈: 몫 2^64 − 1, 나머지 = 피제수 (war.py·eudplib f_div·CtrigAsm f_LDiv 와 같음).
# =============================================================================================


def _udiv_emit(nl, nh, dl, dh, QL, QH, RL, RH):
    r, nd = _new_vars(2)
    wl, wh, ndl, ndh, ndh1 = _new_vars(5)
    rv, ndv = r.GetVTable(), nd.GetVTable()
    whv, wlv, av, bv, cv = (v.GetVTable() for v in (wh, wl, ndl, ndh, ndh1))
    CMP, K0, K1, K2, K3, TC = (Forward() for _ in range(6))
    cmp_c = MemoryEPD(EPD(r.getValueAddr()), AtLeast, placeholder())  # r ≥ d
    qact = SetMemoryEPD(EPD(QH.getValueAddr()), Add, placeholder())  # CMP 의 몫 액션 (칸·값을 단마다 고침)
    ge_c = MemoryEPD(EPD(nh.getValueAddr()), AtLeast, placeholder())  # nh ≥ d
    k0c = MemoryEPD(EPD(wh.getValueAddr()), AtMost, placeholder())  # rh ≤ dh − 1
    k1h = MemoryEPD(EPD(wh.getValueAddr()), AtLeast, placeholder())  # rh ≥ dh + 1
    k1l = MemoryEPD(EPD(wl.getValueAddr()), AtLeast, placeholder())  # rl ≥ dl
    k2h = MemoryEPD(EPD(wh.getValueAddr()), AtLeast, placeholder())
    k2l = MemoryEPD(EPD(wl.getValueAddr()), AtMost, placeholder())  # rl ≤ dl − 1
    k3l = MemoryEPD(EPD(wl.getValueAddr()), AtLeast, placeholder())
    k0act = SetNextPtr(K0, placeholder())  # 값 칸 = 이 단의 다음 단
    q1, q2, q3 = (SetMemoryEPD(EPD(QL.getValueAddr()), Add, placeholder()) for _ in range(3))
    amt = lambda c: EPD(c) + 2  # noqa: E731

    init = [QL.SetNumber(0), QH.SetNumber(0), RL.SetNumber(0), RH.SetNumber(0)]
    init += [r.SetDest(r), nd.SetDest(r), *_addmods(r, nd)]
    init += [wh.SetDest(wh), wl.SetDest(wl), ndl.SetDest(wl), ndh.SetDest(wh), ndh1.SetDest(wh)]
    init += [*_addmods(wh, wl, ndl, ndh, ndh1), SetNextPtr(whv, TC)]
    fr = _Frame(init)
    P64, ZERO, GE, GE_B, FIN32 = (Forward() for _ in range(5))
    STEP_A = [Forward() for _ in range(64)]
    STEP_B = [Forward() for _ in range(32)]

    # --- 경로 고르기 ---
    fr.node([dh.AtLeast(1)], P64)
    fr.node([dl.Exactly(0)], ZERO)
    # --- 32비트 제수 ---
    SeqCompute([(nd, SetTo, M32), (amt(cmp_c), SetTo, dl), (amt(ge_c), SetTo, dl), (nd, Subtract, dl)])  # nd = ~d
    fr.node([ge_c], GE)
    # nh < d: 상위 몫 0, r = nh
    SeqCompute([(nd, Add, 1), (r, SetTo, nh)])
    fr.node([dl.AtLeast(SIGN + 1)], STEP_B[0])
    fr.node([nh.AtLeast(1)], STEP_A[32])
    root_l = _tree(nl, [(1 << t, STEP_A[63 - t]) for t in range(32)])
    fr.tree(root_l)
    fr.node([nl.AtLeast(1)], _tlab(root_l))
    SetNextTrigger(FIN32)  # n = 0
    GE << NextTrigger()
    fr.node([dl.AtLeast(SIGN + 1)], GE_B)
    SeqCompute([(nd, Add, 1), (r, SetTo, 0)])
    root_h = _tree(nh, [(1 << t, STEP_A[31 - t]) for t in range(32)])
    fr.tree(root_h)
    SetNextTrigger(_tlab(root_h))
    GE_B << NextTrigger()
    SeqCompute([(nd, Add, 1), (QH, SetTo, 1), (r, SetTo, nh), (r, Add, nd)])
    SetNextTrigger(STEP_B[0])

    def dstep(label, W, k, Q, back, ovf):
        s0 = Forward()
        if ovf:
            label << RawTrigger(conditions=r.AtLeast(SIGN), actions=[Q.AddNumber(1 << k), SetNextPtr(s0, ndv)])
            fr.resets.append(SetNextPtr(s0, CMP))
        setup = RawTrigger(
            nextptr=rv,
            actions=[
                SetNextPtr(rv, s0),
                SetNextPtr(CMP, back),
                SetNextPtr(ndv, back),
                SetMemoryEPD(EPD(qact) + 4, SetTo, EPD(Q.getValueAddr())),
                SetMemoryEPD(EPD(qact) + 5, SetTo, 1 << k),
            ],
        )
        if not ovf:
            label << setup
        s0 << RawTrigger(nextptr=CMP, conditions=W.AtLeastX(1, 1 << k), actions=r.AddNumber(1))

    for s in range(64):
        dstep(STEP_A[s], nh if s < 32 else nl, 31 - s % 32, QH if s < 32 else QL, STEP_A[s + 1] if s < 63 else FIN32, False)
    for s in range(32):
        dstep(STEP_B[s], nl, 31 - s, QL, STEP_B[s + 1] if s < 31 else FIN32, True)
    FIN32 << NextTrigger()
    SeqCompute([(RL, SetTo, r)])
    SetNextTrigger(fr.end)

    # --- 제수 0 ---
    ZERO << NextTrigger()
    SeqCompute([(QL, SetTo, M32), (QH, SetTo, M32), (RL, SetTo, nl), (RH, SetTo, nh)])
    SetNextTrigger(fr.end)

    # --- 64비트 제수 ---
    P64 << NextTrigger()
    LESS, TRIV, FIN64 = Forward(), Forward(), Forward()
    plan = Plan()
    lt = _result(plan, *_plan64("gt", (dl, dh), (nl, nh)))  # d > n
    plan.emit()
    fr.node(lt, LESS)
    fr.node([dh.AtLeast(SIGN)], TRIV)
    SeqCompute(
        [
            (amt(k0c), SetTo, M32),
            (amt(k1h), SetTo, 1),
            (amt(k2h), SetTo, 1),
            (amt(k2l), SetTo, M32),
            (ndh1, SetTo, M32),
            (ndh, SetTo, M32),
            (ndl, SetTo, M32),
            (amt(k0c), Add, dh),
            (amt(k1l), SetTo, dl),
            (amt(k1h), Add, dh),
            (amt(k2l), Add, dl),
            (amt(k2h), Add, dh),
            (amt(k3l), SetTo, dl),
            (ndh1, Subtract, dh),
            (ndl, Subtract, dl),
            (ndh, Subtract, dh),
        ]
    )
    SeqCompute([(ndh, Add, 1), (ndl, Add, 1), (wh, SetTo, 0), (wl, SetTo, nh)])
    STEP64 = [Forward() for _ in range(32)]
    SetNextTrigger(STEP64[0])
    for idx in range(32):
        k = 31 - idx
        back = STEP64[idx + 1] if idx < 31 else FIN64
        s0 = Forward()
        STEP64[idx] << RawTrigger(
            nextptr=whv,
            actions=[
                SetNextPtr(wlv, s0),
                SetMemoryEPD(EPD(k0act) + 5, SetTo, back),
                SetNextPtr(K0, K1),
                SetNextPtr(K1, K2),
                SetNextPtr(K2, K3),
                SetNextPtr(K3, back),
                SetNextPtr(bv, back),
                SetNextPtr(cv, back),
                SetMemoryEPD(EPD(q1) + 5, SetTo, 1 << k),
                SetMemoryEPD(EPD(q2) + 5, SetTo, 1 << k),
                SetMemoryEPD(EPD(q3) + 5, SetTo, 1 << k),
            ],
        )
        s0 << RawTrigger(nextptr=K0, conditions=nl.AtLeastX(1, 1 << k), actions=wl.AddNumber(1))
    FIN64 << NextTrigger()
    SeqCompute([(RL, SetTo, wl), (RH, SetTo, wh)])
    SetNextTrigger(fr.end)
    LESS << NextTrigger()
    SeqCompute([(RL, SetTo, nl), (RH, SetTo, nh)])
    SetNextTrigger(fr.end)
    TRIV << NextTrigger()  # D ≥ 2^63, n ≥ D → 몫 1, 나머지 n − D
    bc = MemoryEPD(EPD(nl.getValueAddr()), AtMost, placeholder())
    t1, t2 = _new_vars(2)
    SeqCompute(
        [
            (QL, SetTo, 1),
            (RL, SetTo, 1),
            (RH, SetTo, 1),
            (t1, SetTo, M32),
            (t2, SetTo, M32),
            (amt(bc), SetTo, M32),
            (RL, Add, nl),
            (RH, Add, nh),
            (t1, Subtract, dl),
            (t2, Subtract, dh),
            (amt(bc), Add, dl),
            (RL, Add, t1),
            (RH, Add, t2),
        ]
    )
    RawTrigger(conditions=[bc, dl.AtLeast(1)], actions=RH.AddNumber(M32))
    SetNextTrigger(fr.end)

    # --- 흐름 밖 공유 트리거 ---
    CMP << RawTrigger(nextptr=fr.end, conditions=cmp_c, actions=[qact, SetNextPtr(CMP, ndv)])
    TC << RawTrigger(nextptr=wlv, conditions=wl.AtLeastX(1, SIGN), actions=wh.AddNumber(1))
    K0 << RawTrigger(nextptr=K1, conditions=k0c, actions=k0act)
    K1 << RawTrigger(nextptr=K2, conditions=[k1h, k1l], actions=[q1, SetNextPtr(K1, av), SetNextPtr(av, bv)])
    K2 << RawTrigger(nextptr=K3, conditions=[k2h, k2l], actions=[q2, SetNextPtr(K2, av), SetNextPtr(av, cv)])
    K3 << RawTrigger(nextptr=fr.end, conditions=k3l, actions=[q3, SetNextPtr(K3, av), SetNextPtr(av, bv)])
    done = set()
    _emit_tree(root_h, done)
    _emit_tree(root_l, done)
    fr.finish()


@functools.cache
def _udiv_fn():
    """부호 없는 64비트 몫·나머지 공유 본문 (nl, nh, dl, dh) → (ql, qh, rl, rh)."""
    rets = _new_vars(4)

    def i64_udiv(nl, nh, dl, dh):
        _udiv_emit(nl, nh, dl, dh, *rets)

    f = EUDFunc(i64_udiv)
    _compat.predefine_returns(f, list(rets))
    return f


# --- 상수 제수 (DPS_Enhance eudplib-port a7aad90 `eud/ctrig/war.py:483~642` `_cdiv_body` 를 옮김, c < 2^32) ---
# n 칸 수 ÷ c 를 위 칸부터: 칸마다 값 (r·2^32 + x) ÷ c (r < c, r = 윗 칸의 나머지)를 복원 나눗셈 단 j = 31…0 으로.
#   단 j: 값 ≥ c·2^j = (hi_j, lo_j) 면 값 −= c·2^j, 몫 += 2^j. 한 단은 트리거 둘(빌림 T2, 빌림 없음 T1 — 서로 배타,
#   한쪽이 빼면 값 < c·2^j 라 다른 쪽은 거짓). c·2^j < 2^32 인 가장 큰 j = j0 — j0 단을 지나면 r = 0 이라 그 아래는 T1 만.
#   들어가는 단은 이분 탐색으로 고른다: r = 0 이면 x 로(c·2^j ≤ x 인 가장 큰 j — 그 단은 반드시 빼므로 갈림 트리거가
#   바로 빼고 다음 단으로), r ≥ 1 이면 r 로(hi_j ≤ r 인 가장 큰 j). 나머지는 x 에 남는다.
#   SC Subtract 는 조건이 "값 ≥ 빼는 값" 을 보장한 곳에만 쓴다(DESIGN 3.5-7).


def _cdiv_emit(c, a, q, end):
    n = len(a)
    j0 = max(j for j in range(32) if (c << j) <= M32)
    t1 = [[Forward() for _ in range(32)] for _ in range(n)]
    t2 = [[Forward() for _ in range(32)] for _ in range(n)]
    entry, xroot, rroot = [None] * n, [None] * n, [None] * n

    def step_acts(k, j):
        lo, hi = (c << j) & M32, (c << j) >> 32
        acts = [a[k].SubtractNumber(lo)] if lo else []
        acts += [a[k + 1].SubtractNumber(hi)] if hi else []
        return acts + ([q[k].AddNumber(1 << j)] if q[k] is not None else [])

    for k in range(n):
        x = a[k]
        after0 = entry[k - 1] if k else end
        items = [(c << j, _TLeaf(t1[k][j], step_acts(k, j), t1[k][j - 1] if j else after0)) for j in range(j0 + 1)]
        if k:
            xroot[k] = _TNode(x.AtLeast(1), _tree(x, [(1, rroot[k - 1])] + items), xroot[k - 1])
        else:
            xroot[k] = _tree(x, [(0, end)] + items)
        if k + 1 < n:
            r = a[k + 1]
            ritems = {1: t2[k][j0]}
            for j in range(j0 + 1, 32):
                ritems[(c << j) >> 32] = t2[k][j] if (c << j) & M32 else t1[k][j]
            rroot[k] = _tree(r, sorted(ritems.items()))
            entry[k] = _TNode(r.AtLeast(1), rroot[k], xroot[k])
        else:
            entry[k] = xroot[k]
    nodes, seen = [], set()
    for e in [entry[n - 1]] + entry[: n - 1]:
        for x in _spine(e):
            if id(x) not in seen:
                seen.add(id(x))
                nodes.append(x)
    RawTrigger(nextptr=_tlab(entry[n - 1]), actions=[v.SetNumber(0) for v in q if v is not None] + _presets(nodes))
    done = set()
    for k in range(n - 1, -1, -1):
        _emit_tree(entry[k], done)
    for k in range(n - 1, -1, -1):
        x = a[k]
        r = a[k + 1] if k + 1 < n else None
        for j in range(31 if r is not None else j0, -1, -1):
            lo, hi = (c << j) & M32, (c << j) >> 32
            qa = [q[k].AddNumber(1 << j)] if q[k] is not None else []
            if r is not None and lo and j >= j0:
                t2[k][j] << RawTrigger(
                    conditions=[r.AtLeast(hi + 1), x.AtMost(lo - 1)],
                    actions=[x.AddNumber((-lo) & M32), r.SubtractNumber(hi + 1), *qa],
                )
            conds = ([r.AtLeast(hi)] if hi else []) + ([x.AtLeast(lo)] if lo else [])
            t1[k][j] << RawTrigger(
                conditions=conds,
                actions=step_acts(k, j),
                nextptr=_tlab(entry[k - 1] if k else end) if j == 0 else None,
            )


def _cdiv64_emit(K, wl, wh, q0, end):
    """64비트 값 (wh, wl) ÷ 상수 K (2^32 ≤ K < 2^64) → 몫 q0 (< 2^32), 나머지는 (wh, wl) 에 남는다.

    단 j (K·2^j < 2^64 인 가장 큰 j 부터 0 까지): 값 ≥ K·2^j 면 뺀다(`_cdiv` 와 같은 배타 트리거 둘). 들어가는 단은
    wh 로 이분 탐색(hi(K·2^j) ≤ wh 인 가장 큰 j — 값 < hi(K·2^(j+1))·2^32 ≤ K·2^(j+1) 라 윗 단은 할 일이 없다).
    """
    jmax = max(j for j in range(32) if (K << j) <= M64)
    steps = [Forward() for _ in range(jmax + 1)]
    root = _tree(wh, [(0, end)] + [((K << j) >> 32, steps[j]) for j in range(jmax + 1)])
    RawTrigger(nextptr=_tlab(root), actions=([q0.SetNumber(0)] if q0 is not None else []) + _presets(_spine(root)))
    _emit_tree(root)
    for j in range(jmax, -1, -1):
        t = K << j
        lo, hi = t & M32, t >> 32
        def qa():
            return [q0.AddNumber(1 << j)] if q0 is not None else []

        first = None
        if lo and hi < M32:
            first = RawTrigger(
                conditions=[wh.AtLeast(hi + 1), wl.AtMost(lo - 1)],
                actions=[wl.AddNumber((-lo) & M32), wh.SubtractNumber(hi + 1), *qa()],
            )
        conds = [wh.AtLeast(hi)] + ([wl.AtLeast(lo)] if lo else [])
        acts = ([wl.SubtractNumber(lo)] if lo else []) + [wh.SubtractNumber(hi), *qa()]
        t1 = RawTrigger(conditions=conds, actions=acts, nextptr=end if j == 0 else None)
        steps[j] << (first if first is not None else t1)


@functools.cache
def _cdiv_fn(K, want):
    """상수 K (2 ≤ K < 2^64, 2의 거듭제곱 아님) 로 나누는 공유 본문. want: "q" | "r" | "qr".

    반환: q → (ql, qh) / r → (rl, rh) / qr → (ql, qh, rl, rh). K ≥ 2^32 이면 몫 상위는 0 (반환 칸은 있음).
    """
    wq, wr = "q" in want, "r" in want
    big = K > M32
    ql, qh = (EUDVariable(), EUDVariable()) if wq else (None, None)
    rl, rh = (EUDVariable(), EUDVariable()) if wr else (None, None)

    def i64_cdiv(x0, x1):
        end = Forward()
        lo, hi = x0, x1
        if wr:
            SeqCompute([(rl, SetTo, x0), (rh, SetTo, x1)])
            lo, hi = rl, rh
        if big:
            if wq:
                RawTrigger(actions=qh.SetNumber(0))
            _cdiv64_emit(K, lo, hi, ql, end)
        else:
            _cdiv_emit(K, [lo, hi], [ql, qh], end)
            if wr:
                RawTrigger(actions=rh.SetNumber(0))  # 나머지 < K < 2^32
        end << NextTrigger()

    i64_cdiv.__name__ = i64_cdiv.__qualname__ = "i64_cdiv_%d_%s" % (K, want)
    f = EUDFunc(i64_cdiv)
    rets = ([ql, qh] if wq else []) + ([rl, rh] if wr else [])
    _compat.predefine_returns(f, rets)
    return f


def _divmod_into(q, r, pa, pb):
    """q ← a // b, r ← a % b (부호 없음). q·r 는 (lo, hi) 변수 쌍 또는 None(버림). 반쪽이 겹쳐도 된다."""
    ka, kb = _const_pair(pa), _const_pair(pb)
    if ka is not None and kb is not None:
        qq, rr = (ka // kb, ka % kb) if kb else (M64, ka)
        if q is not None:
            _put(*q, _split(qq))
        if r is not None:
            _put(*r, _split(rr))
        return
    if kb is not None:
        if kb == 0:
            _put_both(q, (M32, M32), r, pa)
            return
        if kb == 1:
            _put_both(q, pa, r, (0, 0))
            return
        if kb & (kb - 1) == 0:  # 몫 = 오른쪽 시프트, 나머지 = 하위 비트 (둘 다면 새 변수에 셈하고 옮긴다 — a 와 겹칠 수 있다)
            s = kb.bit_length() - 1
            if q is None:
                _bit_into("and", r[0], r[1], pa, _split(kb - 1))
                return
            if r is None:
                _shift_into("shr", q[0], q[1], pa, s)
                return
            tq, tr = _new_pair(), _new_pair()
            _bit_into("and", tr[0], tr[1], pa, _split(kb - 1))
            _shift_into("shr", tq[0], tq[1], pa, s)
            _assign(*q, *tq)
            _assign(*r, *tr)
            return
        want = ("q" if q is not None else "") + ("r" if r is not None else "")
        if not want:
            return
        al, ah = pa
        rets = (list(q) if q is not None else []) + (list(r) if r is not None else [])
        _cdiv_fn(kb, want)(al, ah, ret=rets)
        return
    tmp = _scratch_rets()
    rets = (list(q) if q is not None else tmp[:2]) + (list(r) if r is not None else tmp[2:])
    _udiv_fn()(pa[0], pa[1], pb[0], pb[1], ret=rets)


def _put_both(q, qv, r, rv):
    """q ← qv, r ← rv 를 겹침 없이 (q·r 가 a 반쪽과 겹칠 수 있다)."""
    if q is not None and r is not None and _alias(q, rv):
        tl, th = _new_pair()
        _assign(tl, th, *rv)
        rv = (tl, th)
    if q is not None:
        _put(*q, qv)
    if r is not None:
        _put(*r, rv)


_rets_scr = []


def _scratch_rets():
    """버리는 반환 칸 4개 (빌드마다 새로)."""
    while len(_rets_scr) < 4:
        _rets_scr.append(EUDVariable())
    return _rets_scr[:4]


@_compat.register_build_reset
def _reset_rets_scr():
    del _rets_scr[:]


# --- 부호 있는 나눗셈 (0 방향 자르기 — CtrigAsm f_LiDiv/f_LiMod, eudplib f_div_towards_zero 와 같음) ---
# 부호를 떼고 부호 없는 나눗셈을 한 뒤, 몫은 두 부호가 다르면, 나머지는 피제수가 음수면 부호를 바꾼다.
# 0 나눗셈: div0="eudplib"(기본) = 부호 없는 결과(몫 2^64 − 1)에 같은 부호 규칙 → 몫 = 피제수 < 0 이면 1, 아니면 −1,
#   나머지 = 피제수 (eudplib 0.81 `f_div_towards_zero` 의 32비트 동작과 같음).
#   div0="ctrig" = CtrigAsm f_LiDiv(CtrigAsm v5.5.lua:91470~91515): 몫 = 피제수 < 0 이면 −2^63, 아니면 2^63 − 1, 나머지 = 피제수.
# −2^63 ÷ −1 = 2^63(wrap, 곧 −2^63) 이다(CtrigAsm 과 같음).


def _py_sdivmod(x, y, div0):
    sx = x - (1 << 64) if x >> 63 else x
    sy = y - (1 << 64) if y >> 63 else y
    if sy == 0:
        if div0 == "ctrig":
            qq = S63 if sx < 0 else S63 - 1
        else:
            qq = 1 if sx < 0 else M64
        return qq & M64, x
    ax, ay = (-sx if sx < 0 else sx), (-sy if sy < 0 else sy)
    qq = ax // ay
    if (sx < 0) != (sy < 0):
        qq = -qq
    return qq & M64, (sx - qq * sy) & M64


def _sdiv_body(al, ah, bpair, div0):
    """부호 있는 몫·나머지 (bpair = (bl, bh) 변수 또는 상수 K). EUDReturn(ql, qh, rl, rh)."""
    nq, sa, t1, t2 = _new_vars(4)
    ql, qh, rl, rh = _new_vars(4)
    kb = _const_pair(bpair)
    sb = 0 if kb is None else kb >> 63
    RawTrigger(actions=[nq.SetNumber(sb), sa.SetNumber(0)])
    if EUDIf()(ah.AtLeast(SIGN)):
        _ineg_with(al, ah, t1, t2)
        RawTrigger(actions=[nq.AddNumber(1), sa.SetNumber(1)])
    EUDEndIf()
    if kb is None:
        bl, bh = bpair
        if EUDIf()(bh.AtLeast(SIGN)):
            _ineg_with(bl, bh, t1, t2)
            RawTrigger(actions=nq.AddNumber(1))
        EUDEndIf()
        _udiv_fn()(al, ah, bl, bh, ret=[ql, qh, rl, rh])
    else:
        mag = ((-kb) & M64) if sb else kb
        _divmod_into((ql, qh), (rl, rh), (al, ah), _split(mag))
    if EUDIf()(nq.Exactly(1)):
        _ineg_with(ql, qh, t1, t2)
    EUDEndIf()
    if EUDIf()(sa.Exactly(1)):
        _ineg_with(rl, rh, t1, t2)
    EUDEndIf()
    if div0 == "ctrig" and (kb is None or kb == 0):
        zero = [bpair[0].Exactly(0), bpair[1].Exactly(0)] if kb is None else []
        if EUDIf()(zero):
            SeqCompute([(ql, SetTo, M32), (qh, SetTo, SIGN - 1)])
            RawTrigger(conditions=sa.Exactly(1), actions=[ql.SetNumber(0), qh.SetNumber(SIGN)])
        EUDEndIf()
    EUDReturn(ql, qh, rl, rh)


@functools.cache
def _sdiv_fn(div0):
    def i64_sdiv(al, ah, bl, bh):
        _sdiv_body(al, ah, (bl, bh), div0)

    i64_sdiv.__name__ = i64_sdiv.__qualname__ = "i64_sdiv_" + div0
    return EUDFunc(i64_sdiv)


@functools.cache
def _sdivk_fn(K, div0):
    def i64_sdivk(al, ah):
        _sdiv_body(al, ah, _split(K), div0)

    i64_sdivk.__name__ = i64_sdivk.__qualname__ = "i64_sdivk_%d_%s" % (K, div0)
    return EUDFunc(i64_sdivk)


def _sdivmod_into(q, r, pa, pb, div0):
    ka, kb = _const_pair(pa), _const_pair(pb)
    if ka is not None and kb is not None:
        qq, rr = _py_sdivmod(ka, kb, div0)
        _put_both(q, _split(qq), r, _split(rr))
        return
    tmp = _scratch_rets()
    rets = (list(q) if q is not None else tmp[:2]) + (list(r) if r is not None else tmp[2:])
    al, ah = pa
    if kb is not None and kb != 0:
        _sdivk_fn(kb, div0)(al, ah, ret=rets)
        return
    _sdiv_fn(div0)(al, ah, pb[0], pb[1], ret=rets)


# =============================================================================================
# 비트 연산 (마스크 SetTo 와 조건만 쓴다 — 마스크 Add/Subtract 식(인게임 확인 전, S8 A-1)은 쓰지 않는다)
#   a & b: d ← a, 마스크 칸 ← ~b(0xFFFFFFFF ⊖ b), d.SetNumberX(0, 마스크)   (eudplib 0.81 `EUDVariable.__and__` 와 같음)
#   a | b: d ← a, 마스크 칸 ← b, d.SetNumberX(0xFFFFFFFF, 마스크)            (eudplib 0.81 `__or__` 와 같음)
#   a ^ b: (a | b) ⊖ (a & b) — 뒤가 앞의 부분집합이라 SC Subtract 가 정확하다 (eudplib `__xor__` 의 마스크 Add 대신)
#   ~a  : 0xFFFFFFFF ⊖ a
# =============================================================================================


def _bit_into(op, dl, dh, pa, pb):
    """(dl, dh) ← a op b. op = "and" | "or" | "xor". dl, dh 는 변수(같은 반쪽의 a 와 같으면 제자리)."""

    def clash(d, k):
        for j, x in enumerate(pa):
            if x is d and j != k:
                return True
        for j, x in enumerate(pb):
            if x is d and not (j == k and pa[k] is x):
                return True
        return False

    if clash(dl, 0) or clash(dh, 1):
        tl, th = _new_pair()
        _bit_into(op, tl, th, pa, pb)
        _assign(dl, dh, tl, th)
        return
    pre_c, pre_v, acts, post = [], [], [], []
    for d, a, b in ((dl, pa[0], pb[0]), (dh, pa[1], pb[1])):
        if _isconst(a) and not _isconst(b):
            a, b = b, a
        if _isconst(a):
            pre_c.append((d, SetTo, (a & b) if op == "and" else (a | b) if op == "or" else (a ^ b)))
            continue
        copy = [] if d is a else [(d, SetTo, a)]
        if _isconst(b):
            if op == "and":
                if b == 0:
                    pre_c.append((d, SetTo, 0))
                    continue
                if b != M32:
                    acts.append(d.SetNumberX(0, ~b & M32))
            elif op == "or":
                if b == M32:
                    pre_c.append((d, SetTo, M32))
                    continue
                if b:
                    acts.append(d.SetNumberX(M32, b))
            elif b == M32:  # xor 0xFFFFFFFF = not
                if d is a:
                    t = EUDVariable()
                    pre_c.append((t, SetTo, M32))
                    pre_v.append((t, Subtract, a))
                    post.append((d, SetTo, t))
                else:
                    pre_c.append((d, SetTo, M32))
                    pre_v.append((d, Subtract, a))
                continue
            elif b:
                n = EUDVariable()
                pre_v.append((n, SetTo, a))
                acts += [d.SetNumberX(M32, b), n.SetNumberX(0, ~b & M32)]
                post.append((d, Subtract, n))
            pre_v += copy
            continue
        if a is b:
            if op == "xor":
                pre_c.append((d, SetTo, 0))
            else:
                pre_v += copy
            continue
        if op == "and":
            w = d.SetNumberX(0, placeholder())
            pre_c.append((EPD(w), SetTo, M32))
            pre_v.append((EPD(w), Subtract, b))
            acts.append(w)
        elif op == "or":
            w = d.SetNumberX(M32, placeholder())
            pre_v.append((EPD(w), SetTo, b))
            acts.append(w)
        else:
            n = EUDVariable()
            wo = d.SetNumberX(M32, placeholder())
            wn = n.SetNumberX(0, placeholder())
            pre_c.append((EPD(wn), SetTo, M32))
            pre_v += [(EPD(wo), SetTo, b), (EPD(wn), Subtract, b), (n, SetTo, a)]
            acts += [wo, wn]
            post.append((d, Subtract, n))
        pre_v += copy
    if pre_c or pre_v:
        SeqCompute(pre_c + pre_v)
    if acts:
        RawTrigger(actions=acts)
    if post:
        SeqCompute(post)


def _not_into(dl, dh, pa):
    """(dl, dh) ← ~a."""
    _bit_into("xor", dl, dh, pa, (M32, M32))


# =============================================================================================
# 시프트 (논리 시프트, n ≥ 64 → 0). 제자리 조각: 64비트 두 배(`_dbl64`, 실행 4), 비트 옮기기(조건 트리거 하나가 비트를
# 지우고 새 자리에 더한다 — 새 자리는 이미 비어 있다), 오른쪽은 96비트 창을 (32 − n)번 두 배 해서 윗 두 칸을 읽는 방법도
# 비교한다. 상수 n 은 n 마다 공유 함수(작으면 인라인), 변수 n 은 결정 나무로 두 배 단계에 들어가는 공유 함수.
# =============================================================================================


def _shl_move(xl, xh, n):
    """(xl, xh) <<= n 제자리 비트 옮기기 (1 ≤ n ≤ 31). 실행 1 + (32 − n) + 32."""
    RawTrigger(actions=xh.SetNumberX(0, (M32 << (32 - n)) & M32))
    for j in range(31 - n, -1, -1):
        RawTrigger(conditions=xh.AtLeastX(1, 1 << j), actions=[xh.SetNumberX(0, 1 << j), xh.AddNumber(1 << (j + n))])
    for j in range(31, -1, -1):
        tgt = xh.AddNumber(1 << (j + n - 32)) if j + n >= 32 else xl.AddNumber(1 << (j + n))
        RawTrigger(conditions=xl.AtLeastX(1, 1 << j), actions=[xl.SetNumberX(0, 1 << j), tgt])


def _shl32_emit(v, m):
    """v <<= m (32비트, 0 ≤ m ≤ 31) 제자리."""
    if m == 0:
        return
    if 2 * m <= 33 - m:
        for _ in range(m):
            SeqCompute([(v, Add, v)])
        return
    RawTrigger(actions=v.SetNumberX(0, (M32 << (32 - m)) & M32))
    for j in range(31 - m, -1, -1):
        RawTrigger(conditions=v.AtLeastX(1, 1 << j), actions=[v.SetNumberX(0, 1 << j), v.AddNumber(1 << (j + m))])


def _shr32_emit(v, m):
    """v >>= m (32비트 논리, 0 ≤ m ≤ 31) 제자리. 실행 1 + (32 − m)."""
    if m == 0:
        return
    RawTrigger(actions=v.SetNumberX(0, (1 << m) - 1))
    for j in range(m, 32):
        RawTrigger(conditions=v.AtLeastX(1, 1 << j), actions=[v.SetNumberX(0, 1 << j), v.AddNumber(1 << (j - m))])


def _shl_k_emit(xl, xh, n):
    """(xl, xh) <<= n 제자리 (0 ≤ n ≤ 63)."""
    if n == 0:
        return
    if n >= 32:
        SeqCompute([(xh, SetTo, xl)])
        RawTrigger(actions=xl.SetNumber(0))
        _shl32_emit(xh, n - 32)
        return
    if 4 * n <= 65 - n:
        for _ in range(n):
            _dbl64(xl, xh)
        return
    _shl_move(xl, xh, n)


def _shr_k_emit(xl, xh, n, w2=None):
    """(xl, xh) >>= n 제자리 (0 ≤ n ≤ 63). w2: 96비트 창 방법에 쓸 임시 변수(없으면 비트 옮기기만)."""
    if n == 0:
        return
    if n >= 32:
        SeqCompute([(xl, SetTo, xh)])
        RawTrigger(actions=xh.SetNumber(0))
        _shr32_emit(xl, n - 32)
        return
    if w2 is not None and 6 * (32 - n) + 4 < 65 - n:
        # 96비트 창 (w2, xh, xl) 을 (32 − n) 번 두 배 → 몫 = (w2, xh)
        t1, t0 = Forward(), Forward()
        for i in range(32 - n):
            nxt = Forward()
            acts = [SetNextPtr(xl.GetVTable(), nxt)]
            if i == 0:
                acts = [w2.SetNumber(0), *_addmods(w2, xh, xl), w2.SetDest(w2), xh.SetDest(xh), xl.SetDest(xl)]
                acts += [SetNextPtr(w2.GetVTable(), t1), SetNextPtr(xh.GetVTable(), t0), SetNextPtr(xl.GetVTable(), nxt)]
            RawTrigger(nextptr=w2.GetVTable(), actions=acts)
            nxt << NextTrigger()
        SeqCompute([(xl, SetTo, xh), (xh, SetTo, w2)])
        after = Forward()
        SetNextTrigger(after)
        t1 << RawTrigger(nextptr=xh.GetVTable(), conditions=xh.AtLeastX(1, SIGN), actions=w2.AddNumber(1))
        t0 << RawTrigger(nextptr=xl.GetVTable(), conditions=xl.AtLeastX(1, SIGN), actions=xh.AddNumber(1))
        after << NextTrigger()
        return
    RawTrigger(actions=xl.SetNumberX(0, (1 << n) - 1))
    for j in range(n, 32):
        RawTrigger(conditions=xl.AtLeastX(1, 1 << j), actions=[xl.SetNumberX(0, 1 << j), xl.AddNumber(1 << (j - n))])
    for j in range(32):
        tgt = xl.AddNumber(1 << (32 - n + j)) if j < n else xh.AddNumber(1 << (j - n))
        RawTrigger(conditions=xh.AtLeastX(1, 1 << j), actions=[xh.SetNumberX(0, 1 << j), tgt])


def _shift_k_triggers(d, n):
    """상수 시프트가 호출 자리에 낼 트리거 수 (인라인 판단)."""
    if n == 0:
        return 0
    if n >= 32:
        return 2 + (0 if n == 32 else 99)
    if d == "shl" and n == 1:
        return 2
    return 99


@functools.cache
def _shk_fn(d, n):
    def i64_shk(xl, xh):
        if d == "shl":
            _shl_k_emit(xl, xh, n)
        else:
            _shr_k_emit(xl, xh, n, EUDVariable())
        EUDReturn(xl, xh)

    i64_shk.__name__ = i64_shk.__qualname__ = "i64_%s_%d" % (d, n)
    return EUDFunc(i64_shk)


@functools.cache
def _shv_fn(d):
    """변수 n 시프트 공유 본문: n ≥ 64 → 0, n ≥ 32 → 칸 옮기고 n −= 32, 나머지 m(1~31)은 결정 나무로 두 배 단계에 들어간다.

    왼쪽: 64비트 두 배 m 번(단계 = 준비 → xh → TM → xl, 실행 4). 오른쪽: 96비트 창 (w2, xh, xl) 을 (32 − m)번 두 배 하고
    (w2, xh) 를 읽는다(단계 실행 6).
    """
    if d == "shl":

        def i64_shl_var(xl, xh, n):
            tm = Forward()
            steps = [Forward() for _ in range(33)]
            ZERO, SMALL = Forward(), Forward()
            fr = _Frame([*_addmods(xl, xh), xl.SetDest(xl), xh.SetDest(xh), SetNextPtr(xh.GetVTable(), tm)])
            fr.node([n.AtLeast(64)], ZERO)
            fr.node([n.AtMost(31)], SMALL)
            SeqCompute([(n, Add, (-32) & M32), (xh, SetTo, xl)])
            RawTrigger(actions=[xl.SetNumber(0), xl.SetDest(xl), xl.SetModifier(Add)])
            SMALL << NextTrigger()
            fr.node([n.Exactly(0)], steps[32])
            root = _tree(n, [(t, steps[32 - t]) for t in range(1, 32)])
            fr.tree(root)
            SetNextTrigger(_tlab(root))
            for s in range(1, 32):
                steps[s] << RawTrigger(nextptr=xh.GetVTable(), actions=SetNextPtr(xl.GetVTable(), steps[s + 1]))
            steps[32] << NextTrigger()
            EUDReturn(xl, xh)
            ZERO << NextTrigger()
            EUDReturn(0, 0)
            tm << RawTrigger(nextptr=xl.GetVTable(), conditions=xl.AtLeastX(1, SIGN), actions=xh.AddNumber(1))
            _emit_tree(root)
            fr.finish()

        return EUDFunc(i64_shl_var)

    def i64_shr_var(xl, xh, n):
        w2 = EUDVariable()
        t1, t0 = Forward(), Forward()
        steps = [Forward() for _ in range(33)]
        ZERO, SMALL, ASIS = Forward(), Forward(), Forward()
        init = [w2.SetNumber(0), *_addmods(w2, xh, xl), w2.SetDest(w2), xh.SetDest(xh), xl.SetDest(xl)]
        init += [SetNextPtr(w2.GetVTable(), t1), SetNextPtr(xh.GetVTable(), t0)]
        fr = _Frame(init)
        fr.node([n.AtLeast(64)], ZERO)
        fr.node([n.AtMost(31)], SMALL)
        SeqCompute([(n, Add, (-32) & M32), (xl, SetTo, xh)])
        RawTrigger(actions=[xh.SetNumber(0), xh.SetDest(xh), xh.SetModifier(Add), SetNextPtr(xh.GetVTable(), t0)])
        SMALL << NextTrigger()
        fr.node([n.Exactly(0)], ASIS)
        root = _tree(n, [(t, steps[t]) for t in range(1, 32)])
        fr.tree(root)
        SetNextTrigger(_tlab(root))
        for s in range(1, 32):
            steps[s] << RawTrigger(nextptr=w2.GetVTable(), actions=SetNextPtr(xl.GetVTable(), steps[s + 1]))
        steps[32] << NextTrigger()
        EUDReturn(xh, w2)
        ASIS << NextTrigger()
        EUDReturn(xl, xh)
        ZERO << NextTrigger()
        EUDReturn(0, 0)
        t1 << RawTrigger(nextptr=xh.GetVTable(), conditions=xh.AtLeastX(1, SIGN), actions=w2.AddNumber(1))
        t0 << RawTrigger(nextptr=xl.GetVTable(), conditions=xl.AtLeastX(1, SIGN), actions=xh.AddNumber(1))
        _emit_tree(root)
        fr.finish()

    return EUDFunc(i64_shr_var)


def _shift_amount(n, fname):
    """시프트 양 → int(0 이상) 또는 EUDVariable."""
    u = unProxy(n)
    if isinstance(u, bool):
        u = int(u)
    if isinstance(u, int):
        if u < 0:
            fail("%s: 시프트 양은 0 이상이어야 합니다 (%d)", fname, u)
        return u
    if isinstance(u, Int64):
        fail("%s: 시프트 양은 32비트 값이어야 합니다 (Int64 는 x.lo 를 넘기세요)", fname)
    h, _z = _halves(u, fname, "시프트 양")
    return h


def _shift_into(d, dl, dh, pa, n):
    """(dl, dh) ← a << n 또는 a >> n (d = "shl"/"shr", 논리 시프트, n ≥ 64 → 0)."""
    ka = _const_pair(pa)
    if isinstance(n, int):
        if ka is not None:
            v = 0 if n >= 64 else ((ka << n) & M64 if d == "shl" else ka >> n)
            _put(dl, dh, _split(v))
            return
        if n >= 64:
            _put(dl, dh, (0, 0))
            return
        if n == 0:
            _put(dl, dh, pa)
            return
        al, ah = pa
        if _shift_k_triggers(d, n) <= 3:
            if not (dl is al and dh is ah):
                tl, th = _new_pair() if _alias((dl, dh), pa) else (dl, dh)
                _assign(tl, th, al, ah)
                (_shl_k_emit if d == "shl" else _shr_k_emit)(tl, th, n)
                if tl is not dl:
                    _assign(dl, dh, tl, th)
                return
            (_shl_k_emit if d == "shl" else _shr_k_emit)(dl, dh, n)
            return
        _shk_fn(d, n)(al, ah, ret=[dl, dh])
        return
    al, ah = pa
    _shv_fn(d)(al, ah, n, ret=[dl, dh])


# =============================================================================================
# to32 · abs · 난수
# =============================================================================================


def _kcond(h, lo_k, hi_k):
    """lo_k ≤ h ≤ hi_k 조건 목록 (h 가 상수면 [] = 참, None = 거짓)."""
    if _isconst(h):
        return [] if lo_k <= h <= hi_k else None
    out = []
    if lo_k > 0:
        out.append(h.AtLeast(lo_k))
    if hi_k < M32:
        out.append(h.AtMost(hi_k))
    return out


def _to32_into(dst, pa, saturate, signed):
    """dst ← a 의 32비트 값. saturate: 부호 없음 = min(a, 2^32 − 1), 부호 있음 = [−2^31, 2^31 − 1] 로 자름. 아니면 하위 반쪽."""
    lo, hi = pa
    k = _const_pair(pa)
    if k is not None:
        if not saturate:
            v = k & M32
        elif signed:
            sv = k - (1 << 64) if k >> 63 else k
            v = min(max(sv, -(1 << 31)), (1 << 31) - 1) & M32
        else:
            v = min(k, M32)
        SeqCompute([(dst, SetTo, v)])
        return
    SeqCompute([(dst, SetTo, lo)])
    if not saturate:
        return
    if signed:
        rules = [
            (_kcond(hi, 1, SIGN - 1), SIGN - 1),  # hi 가 양수 → 위로 넘침
            (_and(_kcond(hi, 0, 0), _kcond(lo, SIGN, M32)), SIGN - 1),
            (_kcond(hi, SIGN, M32 - 1), SIGN),  # hi 가 −1 보다 작음 → 아래로 넘침
            (_and(_kcond(hi, M32, M32), _kcond(lo, 0, SIGN - 1)), SIGN),
        ]
    else:
        rules = [(_kcond(hi, 1, M32), M32)]
    for conds, v in rules:
        if conds is None:
            continue
        RawTrigger(conditions=conds, actions=dst.SetNumber(v))


@functools.cache
def _abs_fn():
    def i64_abs(lo, hi):
        n, m = EUDVariable(), EUDVariable()
        if EUDIf()(hi.AtLeast(SIGN)):
            _ineg_with(lo, hi, n, m)
        EUDEndIf()
        EUDReturn(lo, hi)

    return EUDFunc(i64_abs)


def _abs_into(dl, dh, pa):
    k = _const_pair(pa)
    if k is not None:
        _put(dl, dh, _split(((-k) & M64) if k >> 63 else k))
        return
    if _isconst(pa[1]) and pa[1] < SIGN:
        _put(dl, dh, pa)
        return
    _abs_fn()(pa[0], pa[1], ret=[dl, dh])


# =============================================================================================
# Int64
# =============================================================================================


class Int64:
    """64비트 정수 값 타입 (파이썬 객체 + EUDVariable 두 개). 기본 해석은 부호 없음.

    생성: `Int64()`/`Int64(상수)`/`Int64("10진")` = 초기값만(트리거 0), `Int64(변수)` = 실행 시 lo ← 변수, hi ← 0,
          `Int64(lo, hi)`·`Int64(Int64)` = 실행 시 대입, `Int64.wrap(lo, hi)` = 두 변수를 복사 없이 감싸기.
    대입: `x << y`, `x.assign(y)`, `x.v = y`(epScript).
    덧셈: `x += y`, `x.iadd(y)`, `x.v += y`, `x + y`(새 값). 32비트 변수는 0 확장.
    뺄셈(**wrap**): `x -= y`, `x.isub(y)`, `x.v -= y`, `x - y`, `-x`, `x.neg()`, `x.ineg()`.
    뺄셈(**포화**, 64비트 전체 기준 = CtrigAsm f_LSub): `x.isub_sat(y)`, `x.isubtractattr("v", y)`, `i64.sub_sat(x, y)`.
    비교: `>= <= > < == !=` (부호 없는 사전식) → 조건. 부호 있는 비교는 `x.sge(y)` 등, `i64.sge(x, y)`.
    출력: `x.fmt()`, `x.fmt(signed=True)`. 반쪽: `x.lo`, `x.hi`.
    인자: value(상수·문자열·변수·Int64), hi(선택: hi 반쪽 — 주면 value 는 lo 반쪽)
    반환: -
    비용: 연산별(모듈 설명). 객체 하나 = 변수 2개(72B × 2)
    CP: 바꾸지 않음
    로컬: 공유 안전 (로컬 값을 넣으면 결과도 로컬)
    epScript: `const x = i64.Int64(0);` (var 가 아니라 const), `x.v += 5;`, `if (x >= 10) { … }`
    출처: docs/proto/i64_proto.py(R3 1.2), CtrigAsm CreateWar/f_LMov/f_LAdd/f_LSub/f_LiSub/TTNWar
    """

    __slots__ = ("_elem", "hi", "lo")
    dont_flatten = True

    def __init__(self, value=0, hi=None):
        self._elem = False
        if hi is None:
            if isinstance(value, Int64):
                self.lo, self.hi = EUDVariable(), EUDVariable()
                _assign(self.lo, self.hi, value.lo, value.hi)
                return
            u = unProxy(value)
            if isinstance(u, (bool, int, str, bytes)):
                lo, h = _halves(u, "Int64")
                self.lo, self.hi = EUDVariable(lo), EUDVariable(h)
                return
            if _compat.is_const(u) and not _compat.is_var(u) and not _compat.is_varbase(u):
                self.lo, self.hi = EUDVariable(u), EUDVariable(0)  # 주소식 = 32비트 초기값
                return
            sl, sh = _halves(u, "Int64")
            self.lo, self.hi = EUDVariable(), EUDVariable()
            _assign(self.lo, self.hi, sl, sh)
            return
        sl = _half32(value, "Int64(lo, hi)", "lo")
        sh = _half32(hi, "Int64(lo, hi)", "hi")
        self.lo, self.hi = EUDVariable(), EUDVariable()
        _assign(self.lo, self.hi, sl, sh)

    @classmethod
    def wrap(cls, lo, hi):
        """이미 있는 EUDVariable 두 개(lo, hi)를 복사 없이 Int64 로 감싼다(EUDFunc 인자·반환값 받기, 3.2-8).

        인자: lo, hi(EUDVariable)
        반환: Int64 (반쪽이 그 변수들)
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `function f(lo, hi) { const x = i64.Int64.wrap(lo, hi); … }`
        출처: docs/proto/i64_proto.py `Int64.wrap`
        """
        lo, hi = unProxy(lo), unProxy(hi)
        if not (_isvar(lo) and _isvar(hi)):
            fail("Int64.wrap: lo, hi 는 EUDVariable 이어야 합니다 (%r, %r)", lo, hi)
        obj = cls.__new__(cls)
        obj.lo, obj.hi, obj._elem = lo, hi, False
        return obj

    @classmethod
    def cast(cls, _from):
        """EUDTypedFunc 호환 자리 — 64비트는 변수 한 칸으로 넘길 수 없어 늘 오류(3.2-8)."""
        fail(
            "Int64 는 함수 인자 한 칸으로 넘길 수 없습니다(EUDTypedFunc([Int64]) 불가). "
            "(x.lo, x.hi) 두 인자로 넘기고 본문에서 Int64.wrap(lo, hi) 로 감싸세요."
        )

    # --- 실수 막기 (3.2-2) ---
    def __repr__(self):
        return (
            "<eudext.i64.Int64 — 값 타입(변수 2개). epScript 에서는 'var x = …' 대신 "
            "'const x = i64.Int64(…);' 로 선언하고 x.v = …, x.v += … 로 고치세요>"
        )

    def __hash__(self):
        return id(self)

    def __bool__(self):
        fail("Int64 를 파이썬 if/and/or 에 넣을 수 없습니다. 조건은 EUDIf()(x != 0) 처럼 쓰세요.")

    def __iter__(self):
        fail("Int64 는 나열할 수 없습니다: %s", self.__repr__())

    def __format__(self, spec):
        fail("f_sprintf/printAll 의 {} 에는 x.fmt() 를 넘기세요 (Int64 자체는 서식에 넣을 수 없습니다).")

    def __len__(self):
        fail("Int64 에는 길이가 없습니다: %s", self.__repr__())

    def _check_write(self, what):
        if self._elem:
            fail(
                "Int64Array 원소 읽기(arr[i])는 사본입니다 — %s 가 배열에 쓰이지 않습니다. "
                "arr[i] += v / arr[i] -= v / arr.isub_sat(i, v) / arr[i] = v 를 쓰거나, 사본이 필요하면 Int64(arr[i]) 로 만드세요.",
                what,
            )

    def _pair(self):
        return self.lo, self.hi

    # --- 대입 ---
    def __lshift__(self, other):
        if _compat.eps_lshift_caller():
            fail(
                "epScript 식 `x << n` 은 시프트로 번역되지만 Int64 의 `<<` 는 대입입니다. "
                "대입은 x.v = y; 로, 시프트는 x.shl(n) (새 값) 또는 x.v <<= n; (제자리) 으로 쓰세요."
            )
        self._check_write("대입")
        _assign(self.lo, self.hi, *_halves(other, "Int64 <<"))
        return self

    def assign(self, other):
        """x ← other (실행 시 대입). 반환 self. 비용: 상수 = 호출 1 / 실행 1, 변수 = 1 / 3. epScript: `x.assign(y);`"""
        self._check_write("대입")
        _assign(self.lo, self.hi, *_halves(other, "Int64.assign"))
        return self

    @property
    def v(self):
        """epScript 통로(3.2-6): `x.v = y;`(대입) `x.v += y;` `x.v -= y;`(wrap). 읽으면 self."""
        return self

    @v.setter
    def v(self, value):
        if value is self:  # 파이썬 `x.v += y` 의 되쓰기
            return
        self._check_write("x.v = …")
        _assign(self.lo, self.hi, *_halves(value, "Int64.v"))

    def iaddattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self._check_write("x.v += …")
        self.iadd(value)

    def isubattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self._check_write("x.v -= …")
        self.isub(value)

    def isubtractattr(self, name, value):
        """포화 별칭(S8 7.1-3, eudplib `isubtractattr` 관례): `x.isubtractattr("v", y)` = `x.isub_sat(y)`."""
        if name != "v":
            raise AttributeError(name)
        self.isub_sat(value)

    # --- 덧셈 ---
    def iadd(self, other):
        """x ← x + other (64비트 wrap). 반환 self.

        인자: other — Int64·상수·문자열·32비트 변수(0 확장)
        반환: self
        비용: 상수 = 호출 2 / 실행 2 (lo 가 0 이면 1 / 1). 변수 = 호출 2 / 실행 5 (32비트 변수 4). 같은 객체 = 3 / 5
              (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `x.v += y;` · `x.iadd(y);`
        출처: CtrigAsm f_LAdd, DPS_Enhance eudplib-port a7aad90 eud/ctrig/war.py:780 `_inplace64`("f_LAdd")
        """
        self._check_write("+=")
        _iadd(self.lo, self.hi, *_halves(other, "Int64 +="))
        return self

    def __iadd__(self, other):
        # 파이썬 `arr[i] += v` 는 읽은 사본에 더하고 `arr[i] = 사본` 으로 되쓰므로 사본이어도 막지 않는다
        _iadd(self.lo, self.hi, *_halves(other, "Int64 +="))
        return self

    def __add__(self, other):
        return f_add(self, other)

    def __radd__(self, other):
        return f_add(other, self)

    # --- 뺄셈 ---
    def isub(self, other, inline=True):
        """x ← x − other (64비트 **wrap**). 반환 self. `x -= x` 는 0 으로 접는다.

        인자: other — Int64·상수·문자열·32비트 변수, inline(False 면 공유 EUDFunc — 호출 자리 1)
        반환: self
        비용: 상수 = 호출 2 / 실행 2 (S8 WK). 변수 = 호출 2 / 실행 7 (32비트 변수 5). inline=False = 호출 1 / 실행 18, 본문 4
              (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `x.v -= y;` · `x.isub(y);`
        출처: CtrigAsm f_LiSub, docs/spec/S8_subtract.md 6.2 (WK/WVb 를 줄인 판)
        """
        self._check_write("-=")
        _isub(self.lo, self.hi, *_halves(other, "Int64 -="), inline=bool(inline))
        return self

    def __isub__(self, other):
        _isub(self.lo, self.hi, *_halves(other, "Int64 -="))  # wrap (사본이어도 됨 — `__iadd__` 참고)
        return self

    def __sub__(self, other):
        if _compat.eudplib_calc_caller():
            _left32_error("// (또는 %)")
        return f_sub(self, other)

    def __rsub__(self, other):
        return f_sub(other, self)

    def isub_sat(self, other, inline=False):
        """x ← max(x − other, 0) (**포화**, 64비트 전체 기준 — CtrigAsm f_LSub 와 같음). 반환 self.

        반쪽별 포화가 아니다: 2^32 − 1 = (1:0) − (0:1) 도 맞다. `x.isub_sat(x)` 는 0 으로 접는다.
        인자: other — Int64·상수·문자열·32비트 변수, inline(True 면 공유 함수 대신 호출 자리에 펼침)
        반환: self
        비용: 상수 = 호출·실행 2~4 (S8 SK, 분기 없음). 변수 = 호출 1 / 실행 19, 본문 5 (공유 EUDFunc, 기본).
              inline=True = 호출 3 / 실행 8 (호출 자리 바이트 약 +1KB) (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `x.isub_sat(dmg);` · `x.isub_sat(dmg, inline=True);`
        출처: CtrigAsm f_LSub(CtrigAsm v5.5.lua:72945), docs/spec/S8_subtract.md 6.2 (SK, SVa 를 줄인 판)
        """
        self._check_write("isub_sat")
        _isub_sat(self.lo, self.hi, *_halves(other, "Int64.isub_sat"), inline=bool(inline))
        return self

    def ineg(self):
        """x ← −x (64비트 wrap, 2의 보수). 반환 self. 비용: 호출 3 / 실행 7. epScript: `x.ineg();`. 출처: CtrigAsm f_LNeg"""
        self._check_write("ineg")
        _ineg(self.lo, self.hi)
        return self

    def neg(self):
        """−x 를 새 Int64 로 (wrap). 비용: 호출 2 / 실행 7. epScript: `const y = x.neg();` (`-x` 와 같음)"""
        return f_neg(self)

    def __neg__(self):
        return f_neg(self)

    def __pos__(self):
        return self

    # --- 비교 (부호 없음) ---
    def __ge__(self, other):
        return _compare("ge", self, other, "Int64 >=")

    def __le__(self, other):
        return _compare("le", self, other, "Int64 <=")

    def __gt__(self, other):
        return _compare("gt", self, other, "Int64 >")

    def __lt__(self, other):
        return _compare("lt", self, other, "Int64 <")

    def __eq__(self, other):
        if unProxy(other) is None:
            return NotImplemented
        if _compat.eudplib_calc_caller():
            _left32_error(">> (또는 <<=, >>=)")
        return _compare("eq", self, other, "Int64 ==")

    def __ne__(self, other):
        if unProxy(other) is None:
            return NotImplemented
        return _compare("ne", self, other, "Int64 !=")

    # --- 비교 (부호 있음) ---
    def sge(self, other):
        """self ≥ other (부호 있는 64비트). i64.sge 와 같다. epScript: `if (x.sge(-5)) { … }`"""
        return _compare("sge", self, other, "Int64.sge")

    def sle(self, other):
        """self ≤ other (부호 있는 64비트)."""
        return _compare("sle", self, other, "Int64.sle")

    def sgt(self, other):
        """self > other (부호 있는 64비트)."""
        return _compare("sgt", self, other, "Int64.sgt")

    def slt(self, other):
        """self < other (부호 있는 64비트)."""
        return _compare("slt", self, other, "Int64.slt")

    # --- 출력 ---
    def fmt(self, signed=False):
        """10진 출력용 값(`ptr2s`). `i64.fmt(self, signed)` 와 같다. epScript: `printAll("HP {}", hp.fmt());`"""
        return f_fmt(self, signed)

    # --- 곱셈·나눗셈·비트·시프트 (2차, WP4) ---
    def _op_inplace(self, what, fname, fn, other):
        self._check_write(what)
        fn(self.lo, self.hi, self._pair(), _halves(other, fname))
        return self

    def imul(self, other):
        """x ← x × other (64비트 wrap — 부호 없음·있음 결과가 같다). 반환 self.

        인자: other — Int64·상수·문자열·32비트 변수(0 확장)
        반환: self
        비용: 변수 = 호출 1 / 실행 64×64 35~355, 곱하는 수가 32비트 변수 140~273, 32×32 72~209 (본문 1벌씩 171·123·106).
              상수 = 호출 1 / 상수마다 공유 본문(비트 누적 — 실행 최악 약 90, 작은 상수는 배가·덧셈 — ×10 은 29).
              0·1·−1·2^s 는 인라인·시프트 (2026-09-17, docs/COSTS.md "i64 2차 (WP4)")
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `x.v *= y;` · `x.imul(y);`
        출처: CtrigAsm f_LMul/f_LiMul, DESIGN 4.4(16비트 쪼개기), DPS_Enhance eudplib-port a7aad90
              eud/ctrig/war.py:334 `_mul64`, eud/ctrig/arith.py:275 `_mul_small`
        """
        return self._op_inplace("*=", "Int64 *=", _mul_into, other)

    def __imul__(self, other):
        _mul_into(self.lo, self.hi, self._pair(), _halves(other, "Int64 *="))
        return self

    def __mul__(self, other):
        return f_mul(self, other)

    def __rmul__(self, other):
        return f_mul(other, self)

    def idiv(self, other):
        """x ← x // other (부호 없음, 0 나눗셈 = 2^64 − 1). 반환 self.

        인자: other — Int64·상수·문자열·32비트 변수
        반환: self
        비용: `i64.div` 와 같음 (변수 = 호출 1 / 실행 17~391, 상수 제수 = 1 / 12~83)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `x.v /= y;` (epScript `/` 는 `//` 로 번역된다) · `x.idiv(y);`
        출처: CtrigAsm f_LDiv
        """
        self._check_write("//=")
        _divmod_into(self._pair(), None, self._pair(), _halves(other, "Int64 //="))
        return self

    def __ifloordiv__(self, other):
        _divmod_into(self._pair(), None, self._pair(), _halves(other, "Int64 //="))
        return self

    def __floordiv__(self, other):
        return f_div(self, other)

    def __rfloordiv__(self, other):
        return f_div(other, self)

    def imod(self, other):
        """x ← x % other (부호 없음, 0 나눗셈 = x 그대로). 반환 self. epScript: `x.v %= y;` · `x.imod(y);`. 출처: CtrigAsm f_LMod"""
        self._check_write("%=")
        _divmod_into(None, self._pair(), self._pair(), _halves(other, "Int64 %="))
        return self

    def __imod__(self, other):
        _divmod_into(None, self._pair(), self._pair(), _halves(other, "Int64 %="))
        return self

    def __mod__(self, other):
        return f_mod(self, other)

    def __rmod__(self, other):
        return f_mod(other, self)

    def __divmod__(self, other):
        return f_divmod(self, other)

    def __rdivmod__(self, other):
        return f_divmod(other, self)

    def __truediv__(self, other):
        fail("Int64 는 정수 나눗셈만 됩니다: 파이썬은 x // y, epScript 는 x / y (// 로 번역된다)")

    __rtruediv__ = __itruediv__ = __truediv__

    def sdiv(self, other, div0="eudplib"):
        """부호 있는 몫(0 방향 자르기)을 새 Int64 로. `i64.sdiv(self, other, div0)` 와 같다."""
        return f_sdiv(self, other, div0=div0)

    def smod(self, other, div0="eudplib"):
        """부호 있는 나머지(피제수 부호)를 새 Int64 로. `i64.smod(self, other, div0)` 와 같다."""
        return f_smod(self, other, div0=div0)

    def iand(self, other):
        """x ← x & other. 반환 self. 비용: 변수 = 호출 2 / 실행 6, 상수 = 1~2 / 1~2. epScript: `x.v &= y;`"""
        return self._op_inplace("&=", "Int64 &=", lambda dl, dh, pa, pb: _bit_into("and", dl, dh, pa, pb), other)

    def ior(self, other):
        """x ← x | other. 반환 self. 비용: 변수 = 호출 2 / 실행 6, 상수 = 1~2 / 1~2. epScript: `x.v |= y;`"""
        return self._op_inplace("|=", "Int64 |=", lambda dl, dh, pa, pb: _bit_into("or", dl, dh, pa, pb), other)

    def ixor(self, other):
        """x ← x ^ other. 반환 self. 비용: 변수 = 호출 5 / 실행 13, 상수 = 3 / 7. epScript: `x.v ^= y;`"""
        return self._op_inplace("^=", "Int64 ^=", lambda dl, dh, pa, pb: _bit_into("xor", dl, dh, pa, pb), other)

    def __iand__(self, other):
        if _compat.eudplib_calc_caller():
            _left32_error("* (또는 // %)")
        _bit_into("and", self.lo, self.hi, self._pair(), _halves(other, "Int64 &="))
        return self

    def __ior__(self, other):
        _bit_into("or", self.lo, self.hi, self._pair(), _halves(other, "Int64 |="))
        return self

    def __ixor__(self, other):
        _bit_into("xor", self.lo, self.hi, self._pair(), _halves(other, "Int64 ^="))
        return self

    def __and__(self, other):
        return f_bitand(self, other)

    __rand__ = __and__

    def __or__(self, other):
        return f_bitor(self, other)

    __ror__ = __or__

    def __xor__(self, other):
        return f_bitxor(self, other)

    __rxor__ = __xor__

    def invert(self):
        """~x 를 새 Int64 로 (비트 반전). 비용: 호출 1 / 실행 3. epScript: `const y = x.invert();` (`~x` 와 같음)"""
        return f_bitnot(self)

    def __invert__(self):
        return f_bitnot(self)

    def iinvert(self):
        """x ← ~x 제자리. 반환 self. 비용: 호출 2 / 실행 4. epScript: `x.iinvert();`. 출처: CtrigAsm f_LNot"""
        self._check_write("iinvert")
        _not_into(self.lo, self.hi, self._pair())
        return self

    def shl(self, n):
        """x << n (논리 시프트, n ≥ 64 → 0) 를 새 Int64 로. `<<` 는 대입이라 시프트는 이 메서드나 `<<=` 로 쓴다(DESIGN 3.2-5).

        인자: n — 0 이상 정수 또는 32비트 변수(부호 없음으로 읽음)
        반환: 새 Int64
        비용: 상수 n = 1 은 인라인(제자리 호출 2 / 실행 4), 32 는 인라인(2 / 3), 그 밖은 n 마다 공유 본문(호출 1 /
              실행 최대 약 55 — n = 7 은 37, 20 은 54). 변수 n = 공유 본문 1벌(본문 72, 실행 최악 147) (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const y = x.shl(3);` · `x.v <<= n;`(제자리)
        출처: CtrigAsm f_LlShift(원본은 시프트 양을 64 로 나눈 나머지로 본다 — eudext 는 64 이상 = 0)
        """
        return f_shl(self, n)

    def shr(self, n):
        """x >> n (논리 시프트, n ≥ 64 → 0) 를 새 Int64 로 (`x >> n` 과 같다).

        인자: n — 0 이상 정수 또는 32비트 변수
        반환: 새 Int64
        비용: 상수 n = 32 인라인(2 / 3), 그 밖은 n 마다 공유 본문(호출 1 / 실행 최대 약 70 — n = 5 는 69, n ≥ 27 은
              96비트 창 방법으로 더 적음 — 30 은 24). 변수 n = 공유 본문 1벌(본문 74, 실행 최악 208) (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const y = x.shr(3);` · `const y = x >> 3;` · `x.v >>= n;`(제자리)
        출처: 없음(CtrigAsm 에 64비트 오른쪽 시프트 없음)
        """
        return f_shr(self, n)

    def ishl(self, n):
        """x ← x << n 제자리 (논리, n ≥ 64 → 0). 반환 self. epScript: `x.v <<= n;` · `x.ishl(n);`"""
        self._check_write("<<=")
        _shift_into("shl", self.lo, self.hi, self._pair(), _shift_amount(n, "Int64.ishl"))
        return self

    def ishr(self, n):
        """x ← x >> n 제자리 (논리, n ≥ 64 → 0). 반환 self. epScript: `x.v >>= n;` · `x.ishr(n);`"""
        self._check_write(">>=")
        _shift_into("shr", self.lo, self.hi, self._pair(), _shift_amount(n, "Int64.ishr"))
        return self

    def __ilshift__(self, n):
        # `x <<= n` 은 시프트다(eudplib EUDVariable 과 같음). `x << y` 는 대입.
        _shift_into("shl", self.lo, self.hi, self._pair(), _shift_amount(n, "Int64 <<="))
        return self

    def __irshift__(self, n):
        _shift_into("shr", self.lo, self.hi, self._pair(), _shift_amount(n, "Int64 >>="))
        return self

    def __rshift__(self, n):
        return f_shr(self, n)

    def __rlshift__(self, other):
        fail("정수·32비트 값 << Int64 는 지원하지 않습니다 (시프트 양은 32비트 값이어야 합니다)")

    def __rrshift__(self, other):
        fail("정수·32비트 값 >> Int64 는 지원하지 않습니다 (시프트 양은 32비트 값이어야 합니다)")

    def imulattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self.imul(value)

    def ifloordivattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self.idiv(value)

    def imodattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self.imod(value)

    def iandattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self.iand(value)

    def iorattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self.ior(value)

    def ixorattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self.ixor(value)

    def ilshiftattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self.ishl(value)

    def irshiftattr(self, name, value):
        if name != "v":
            raise AttributeError(name)
        self.ishr(value)

    def __pow__(self, other):
        fail("Int64 거듭제곱(**)은 지원하지 않습니다. 곱셈을 이어 쓰세요 (x * x * x).")

    __rpow__ = __ipow__ = __pow__

    def to32(self, saturate=True, signed=False):
        """32비트 값(새 EUDVariable)으로. `i64.to32(self, saturate, signed)` 와 같다. epScript: `var v = x.to32();`"""
        return f_to32(self, saturate=saturate, signed=signed)

    def abs(self):
        """|x| 를 새 Int64 로 (부호 있는 64비트로 읽음, |−2^63| = 2^63). 비용: 호출 1 / 실행 10~18. epScript: `const a = x.abs();`"""
        return f_abs(self)

    def iabs(self):
        """x ← |x| 제자리. 반환 self. epScript: `x.iabs();`. 출처: CtrigAsm f_LAbs"""
        self._check_write("iabs")
        _abs_into(self.lo, self.hi, self._pair())
        return self


# =============================================================================================
# 모듈 함수 (epScript: m.foo() → m.f_foo())
# =============================================================================================


def _target(x, fname):
    x = unProxy(x)
    if not isinstance(x, Int64):
        fail("%s: 제자리 연산의 대상은 Int64 여야 합니다 (%r)", fname, x)
    return x


def _new_pair():
    return EUDVariable(), EUDVariable()


def f_wrap(lo, hi):
    """`Int64.wrap(lo, hi)` 와 같다 (epScript: `const x = i64.wrap(lo, hi);`)."""
    return Int64.wrap(lo, hi)


wrap = f_wrap


def f_add(a, b):
    """a + b 를 새 Int64 로 (64비트 wrap). 상수끼리는 파이썬 int.

    인자: a, b — Int64·상수·문자열·32비트 변수
    반환: 새 Int64 (또는 int)
    비용: 변수끼리 = 호출 2 / 실행 7, 한쪽 상수 = 호출 2 / 실행 4 (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const s = i64.add(x, y);` (Int64 끼리는 `x + y` 도 된다)
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/war.py:427 `_add64_inline`
    """
    pa, pb = _halves(a, "i64.add", "a"), _halves(b, "i64.add", "b")
    if _both_const(pa) and _both_const(pb):
        return (_join(*pa) + _join(*pb)) & M64
    rl, rh = _new_pair()
    if _same(pa, pb):
        _assign(rl, rh, *pa)
        _double(rl, rh)
    else:
        _add3(rl, rh, pa, pb)
    return Int64.wrap(rl, rh)


add = f_add


def f_sub(a, b, inline=True):
    """a − b 를 새 Int64 로 (64비트 **wrap**). 상수끼리는 파이썬 int. `sub(x, x)` = 0.

    인자: a, b — Int64·상수·문자열·32비트 변수, inline(False 면 공유 EUDFunc — 결과 변수에 바로 받음)
    반환: 새 Int64 (또는 int)
    비용: 변수끼리 = 호출 2 / 실행 9 (inline=False = 1 / 18), b 상수 = 2 / 4 (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const d = i64.sub(x, y);` (Int64 끼리는 `x - y` 도 된다)
    출처: CtrigAsm f_LiSub, docs/spec/S8_subtract.md 6.2
    """
    pa, pb = _halves(a, "i64.sub", "a"), _halves(b, "i64.sub", "b")
    if _both_const(pa) and _both_const(pb):
        return (_join(*pa) - _join(*pb)) & M64
    rl, rh = _new_pair()
    _sub3(rl, rh, pa, pb, inline=bool(inline))
    return Int64.wrap(rl, rh)


sub = f_sub


def f_sub_sat(a, b, inline=False):
    """max(a − b, 0) 를 새 Int64 로 (**포화**, 64비트 전체 기준). 상수끼리는 파이썬 int. `sub_sat(x, x)` = 0.

    인자: a, b — Int64·상수·문자열·32비트 변수, inline(True 면 복사 + 펼친 포화 뺄셈)
    반환: 새 Int64 (또는 int)
    비용: 변수끼리 = 호출 1 / 실행 19 (공유 EUDFunc 가 결과 변수에 바로 씀, 기본), inline=True = 호출 4 / 실행 11,
          b 상수 = 호출·실행 1 + 2~4 (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const r = i64.sub_sat(hp, dmg);`
    출처: CtrigAsm f_LSub, docs/spec/S8_subtract.md 6.2
    """
    pa, pb = _halves(a, "i64.sub_sat", "a"), _halves(b, "i64.sub_sat", "b")
    if _both_const(pa) and _both_const(pb):
        x, y = _join(*pa), _join(*pb)
        return x - y if x >= y else 0
    rl, rh = _new_pair()
    _sub_sat3(rl, rh, pa, pb, inline=bool(inline))
    return Int64.wrap(rl, rh)


sub_sat = f_sub_sat


def f_neg(a):
    """−a 를 새 Int64 로 (64비트 wrap). 상수는 파이썬 int. 비용: 호출 2 / 실행 7. epScript: `const n = i64.neg(x);`"""
    pa = _halves(a, "i64.neg")
    if _both_const(pa):
        return (-_join(*pa)) & M64
    rl, rh = _new_pair()
    _sub3(rl, rh, (0, 0), pa)
    return Int64.wrap(rl, rh)


neg = f_neg


def f_iadd(x, b):
    """x ← x + b (x 는 Int64). `x.iadd(b)` 와 같다. epScript: `i64.iadd(x, b);`"""
    return _target(x, "i64.iadd").iadd(b)


def f_isub(x, b, inline=True):
    """x ← x − b (**wrap**, x 는 Int64). `x.isub(b)` 와 같다. epScript: `i64.isub(x, b);`"""
    return _target(x, "i64.isub").isub(b, inline=inline)


def f_isub_sat(x, b, inline=False):
    """x ← max(x − b, 0) (**포화**, x 는 Int64). `x.isub_sat(b, inline)` 와 같다. epScript: `i64.isub_sat(x, b);`"""
    return _target(x, "i64.isub_sat").isub_sat(b, inline=inline)


iadd = f_iadd
isub = f_isub
isub_sat = f_isub_sat


def _into(dst, fname, pa, pb, op):
    """dst ← a op b (CtrigAsm 3인자 모양, op = add/wsub/ssub). dst 가 a·b 와 겹쳐도 맞게."""
    d = _target(dst, fname)
    d._check_write(fname)
    pd = d._pair()
    if op == "add" and _same(pd, pb):
        pa, pb = pb, pa
    if _same(pd, pa):
        {"add": _iadd, "wsub": _isub, "ssub": _isub_sat}[op](*pd, *pb)
        return d
    if _both_const(pa) and _both_const(pb):
        x, y = _join(*pa), _join(*pb)
        r = x + y if op == "add" else x - y if op == "wsub" else max(x - y, 0)
        _assign(*pd, *_split(r & M64))
        return d
    three = {"add": _add3, "wsub": _sub3, "ssub": _sub_sat3}[op]
    if _alias(pd, pa + pb):  # dst 반쪽이 원천과 엇갈려 겹침 → 새 변수에 셈하고 옮긴다
        tl, th = _new_pair()
        three(tl, th, pa, pb)
        _assign(*pd, tl, th)
        return d
    three(*pd, pa, pb)
    return d


def f_LAdd(dst, a, b):
    """CtrigAsm `f_LAdd` 별칭: dst ← a + b (64비트 wrap). dst 는 Int64 (a·b 와 같아도 된다). 반환 dst.

    epScript: `i64.LAdd(x, x, 5);`. 비용: `iadd`/`add` 와 같음. 출처: CtrigAsm f_LAdd (PlayerID 인자는 없다)
    """
    return _into(dst, "i64.LAdd", _halves(a, "i64.LAdd", "Source"), _halves(b, "i64.LAdd", "Operand"), "add")


def f_LiSub(dst, a, b):
    """CtrigAsm `f_LiSub` 별칭: dst ← a − b (64비트 **wrap**). 반환 dst. epScript: `i64.LiSub(x, x, y);`"""
    return _into(dst, "i64.LiSub", _halves(a, "i64.LiSub", "Source"), _halves(b, "i64.LiSub", "Operand"), "wsub")


def f_LSub(dst, a, b):
    """CtrigAsm `f_LSub` 별칭: dst ← max(a − b, 0) (**포화**, 64비트 전체 기준). 반환 dst.

    CtrigAsm 원본과 같은 의미다(`S ≥ O ? S − O : 0`, 빌림 처리 포함). `SetNWar(Subtract)` 식 반쪽별 포화가 아니다.
    epScript: `i64.LSub(hp, hp, dmg);`. 비용: `isub_sat`/`sub_sat` 와 같음. 출처: CtrigAsm v5.5.lua:72945 f_LSub
    """
    return _into(dst, "i64.LSub", _halves(a, "i64.LSub", "Source"), _halves(b, "i64.LSub", "Operand"), "ssub")


def f_LNeg(dst, a):
    """CtrigAsm `f_LNeg` 별칭: dst ← −a (64비트 wrap). 반환 dst. epScript: `i64.LNeg(x, y);`"""
    d = _target(dst, "i64.LNeg")
    pa = _halves(a, "i64.LNeg", "Source")
    if _same(d._pair(), pa):
        return d.ineg()
    return _into(d, "i64.LNeg", (0, 0), pa, "wsub")


LAdd = f_LAdd
LiSub = f_LiSub
LSub = f_LSub
LNeg = f_LNeg

ge = f_ge
le = f_le
gt = f_gt
lt = f_lt
eq = f_eq
ne = f_ne
sge = f_sge
sle = f_sle
sgt = f_sgt
slt = f_slt


def _left32_error(sym):
    fail(
        "32비트 변수가 왼쪽인 %s 는 eudplib 연산자가 먼저 불려 Int64 를 상수처럼 다룹니다 — "
        "i64.mul(v, x) / i64.div(v, x) / i64.mod(v, x) / i64.shr(…) 처럼 모듈 함수를 쓰세요 (DESIGN 3.2).",
        sym,
    )


def _div0_arg(div0, fname):
    if div0 not in _DIV0:
        fail('%s: div0 는 "eudplib" 또는 "ctrig" 여야 합니다 (%r)', fname, div0)
    return div0


def _new_value(fill):
    """새 Int64 를 만들고 fill(dl, dh) 로 채운다."""
    rl, rh = _new_pair()
    fill(rl, rh)
    return Int64.wrap(rl, rh)


def f_mul(a, b):
    """a × b 를 새 Int64 로 (64비트 wrap). 상수끼리는 파이썬 int.

    곱해지는 수의 하위 반쪽을 16비트 두 조각으로 나눠, 곱하는 수의 비트마다 조건 트리거 하나 + 변수 트리거 사슬로
    누적한다(넘침 없는 누적기 5개). 상수 곱은 상수마다 공유 본문(비트 누적 또는 배가·덧셈 중 싼 쪽).
    인자: a, b — Int64·상수(−2^63 ~ 2^64−1)·10진 문자열·32비트 변수(0 확장)
    반환: 새 Int64 (또는 int)
    비용: 변수끼리 = 호출 1 / 실행 64×64 35~355 (hi 가 상수 0 인 쪽이 있으면 140~273, 둘 다 32비트 72~209),
          본문 1벌(64×64 171 트리거, 64×32 123, 32×32 106). 상수 = 호출 1 / 실행 최악 약 90 (10^16 은 41~73, 본문 67)
          (2026-09-17, docs/COSTS.md) — 3.8 목표 ≤ 1,000 (war.py `_mul64` 비트 루프 2,268~4,626)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const p = i64.mul(x, y);` · `const p = x * 10;` (Int64 가 왼쪽이면 연산자도 된다)
    출처: CtrigAsm f_LMul, DESIGN 4.4(16비트 쪼개기 — G3 1.10 제안), DPS_Enhance eudplib-port a7aad90
          eud/ctrig/war.py:334 `_mul64`·eud/ctrig/arith.py:275 `_mul_small`
    """
    pa, pb = _halves(a, "i64.mul", "a"), _halves(b, "i64.mul", "b")
    ka, kb = _const_pair(pa), _const_pair(pb)
    if ka is not None and kb is not None:
        return (ka * kb) & M64
    return _new_value(lambda rl, rh: _mul_into(rl, rh, pa, pb))


def f_mul32(a, b):
    """32비트 × 32비트 → 64비트 곱 (새 Int64). a, b 는 32비트 값(정수 −2^31 ~ 2^32−1, 변수·칸).

    인자: a, b — 32비트 값 (Int64 는 오류)
    반환: 새 Int64 (상수끼리는 int)
    비용: 호출 2 / 실행 72~209 (32×32 본문 1벌 106) (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const p = i64.mul32(hp, 100000);`
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/war.py:305 `_mul3232` 대체
    """
    x = _half32(a, "i64.mul32", "a")
    y = _half32(b, "i64.mul32", "b")
    if _isconst(x) and _isconst(y):
        return x * y
    return _new_value(lambda rl, rh: _mul_into(rl, rh, (x, 0), (y, 0)))


def f_div(a, b):
    """a // b (부호 없는 64비트 몫)을 새 Int64 로. 0 나눗셈 = 2^64 − 1. 상수끼리는 int.

    인자: a, b — Int64·상수·10진 문자열·32비트 변수
    반환: 새 Int64 (또는 int)
    비용: 변수 제수 = 호출 1 / 실행 17~391 (32비트 제수는 피제수 비트 수 × 4~5 + 들어가기 약 20, 64비트 제수는
          32단 × 7~11) / 본문 1벌(389 트리거, 몫·나머지 공용). 상수 제수 = 상수마다 공유 본문(2^32 미만은 이식판 `_cdiv` —
          본문 약 120 / 실행 12~81, 그 이상은 본문 약 100 / 실행 18~83), 2^s 는 시프트(인라인 아님, 실행 약 64)
          (2026-09-17, docs/COSTS.md) — 3.8 목표 ≤ 711
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const q = i64.div(x, y);` · `const q = x / 1000;` (epScript `/` 는 `//`)
    출처: CtrigAsm f_LDiv, DPS_Enhance eudplib-port a7aad90 eud/ctrig/war.py:347~420(3경로)·:483~642(`_cdiv`)·divide.py
    """
    return _divop(a, b, "q", "i64.div")


def f_mod(a, b):
    """a % b (부호 없는 64비트 나머지)를 새 Int64 로. 0 나눗셈 = a. 상수끼리는 int.

    인자·비용: `i64.div` 와 같음 (나머지만 쓰는 상수 본문은 몫을 셈하지 않는다)
    반환: 새 Int64 (또는 int)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const r = i64.mod(x, 10);` · `const r = x % y;`
    출처: CtrigAsm f_LMod
    """
    return _divop(a, b, "r", "i64.mod")


def f_divmod(a, b):
    """(a // b, a % b) 를 새 Int64 두 개로 (부호 없음, 0 나눗셈 = (2^64 − 1, a)). 상수끼리는 int 두 개.

    인자·비용: `i64.div` 와 같음 (한 번의 나눗셈으로 둘 다)
    반환: (Int64, Int64) 튜플
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const q, r = i64.divmod(x, y);`
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/war.py:398 `_divmod64`
    """
    return _divop(a, b, "qr", "i64.divmod")


def _divop(a, b, want, fname):
    pa, pb = _halves(a, fname, "a"), _halves(b, fname, "b")
    ka, kb = _const_pair(pa), _const_pair(pb)
    if ka is not None and kb is not None:
        qq, rr = (ka // kb, ka % kb) if kb else (M64, ka)
        return {"q": qq, "r": rr, "qr": (qq, rr)}[want]
    q = _new_pair() if "q" in want else None
    r = _new_pair() if "r" in want else None
    _divmod_into(q, r, pa, pb)
    out = tuple(Int64.wrap(*p) for p in (q, r) if p is not None)
    return out[0] if len(out) == 1 else out


def f_sdiv(a, b, div0="eudplib"):
    """부호 있는 64비트 몫(0 방향으로 자름 — C·JavaScript·CtrigAsm f_LiDiv 와 같음)을 새 Int64 로.

    인자: a, b — Int64·상수(음수 = 2의 보수)·문자열·32비트 변수(0 확장 — 음수 32비트는 Int64 로 올려 부호를 넣는다),
          div0 — 0 나눗셈 규칙: "eudplib"(기본, 몫 = a < 0 이면 1 아니면 −1 — eudplib f_div_towards_zero 와 같음),
          "ctrig"(CtrigAsm f_LiDiv: a < 0 이면 −2^63, 아니면 2^63 − 1)
    반환: 새 Int64 (상수끼리는 int, 0 ~ 2^64−1 표기)
    비용: 변수 = 호출 1 / 실행 37~368 (부호 없는 나눗셈 + 부호 떼기·붙이기 약 20~30), 본문 div0 마다 1벌(26 + 부호 없는 본문).
          상수 제수 = 제수마다 공유 본문(÷ −7 은 본문 20 / 실행 42~76) (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const q = i64.sdiv(x, -7);` · `const q = i64.sdiv(x, y, div0="ctrig");`
    출처: CtrigAsm f_LiDiv(CtrigAsm v5.5.lua:70293, 본문 91309~91527·92377~92447), eudplib 0.81 eudlib/mathf/div.py:14
    """
    return _sdivop(a, b, "q", div0, "i64.sdiv")


def f_smod(a, b, div0="eudplib"):
    """부호 있는 64비트 나머지(부호 = 피제수 부호, a = q·b + r)를 새 Int64 로. 0 나눗셈 = a (두 규칙 같음).

    인자·비용: `i64.sdiv` 와 같음
    반환: 새 Int64 (또는 int)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const r = i64.smod(x, 10);`
    출처: CtrigAsm f_LiMod(CtrigAsm v5.5.lua:70811, 본문 91528~91743·92306~92375)
    """
    return _sdivop(a, b, "r", div0, "i64.smod")


def f_sdivmod(a, b, div0="eudplib"):
    """(부호 있는 몫, 나머지) 를 새 Int64 두 개로. `i64.sdiv`·`i64.smod` 를 한 번에. epScript: `const q, r = i64.sdivmod(x, y);`"""
    return _sdivop(a, b, "qr", div0, "i64.sdivmod")


def _sdivop(a, b, want, div0, fname):
    div0 = _div0_arg(div0, fname)
    pa, pb = _halves(a, fname, "a"), _halves(b, fname, "b")
    ka, kb = _const_pair(pa), _const_pair(pb)
    if ka is not None and kb is not None:
        qq, rr = _py_sdivmod(ka, kb, div0)
        return {"q": qq, "r": rr, "qr": (qq, rr)}[want]
    q = _new_pair() if "q" in want else None
    r = _new_pair() if "r" in want else None
    _sdivmod_into(q, r, pa, pb, div0)
    out = tuple(Int64.wrap(*p) for p in (q, r) if p is not None)
    return out[0] if len(out) == 1 else out


def _bitop(op, fname):
    def f(a, b):
        pa, pb = _halves(a, fname, "a"), _halves(b, fname, "b")
        ka, kb = _const_pair(pa), _const_pair(pb)
        if ka is not None and kb is not None:
            return (ka & kb) if op == "and" else (ka | kb) if op == "or" else (ka ^ kb)
        return _new_value(lambda rl, rh: _bit_into(op, rl, rh, pa, pb))

    return f


f_bitand = _bitop("and", "i64.bitand")
f_bitand.__name__ = "f_bitand"
f_bitand.__doc__ = """a & b 를 새 Int64 로. 상수끼리는 int.

    인자: a, b — Int64·상수·문자열·32비트 변수
    반환: 새 Int64 (또는 int)
    비용: 변수끼리 = 호출 2 / 실행 6, 한쪽 상수 = 1~2 / 1~3 (마스크 SetTo 1액션) (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const m = x & 0xFFFF;` · `const m = i64.bitand(x, y);`
    출처: CtrigAsm f_LAnd, eudplib 0.81 core/variable/eudv.py:400 `__and__`(마스크 칸 채우기)
    """
f_bitor = _bitop("or", "i64.bitor")
f_bitor.__name__ = "f_bitor"
f_bitor.__doc__ = """a | b 를 새 Int64 로. 상수끼리는 int.

    인자: a, b — Int64·상수·문자열·32비트 변수
    반환: 새 Int64 (또는 int)
    비용: 변수끼리 = 호출 2 / 실행 6, 한쪽 상수 = 1~2 / 1~3 (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const m = x | y;` · `const m = i64.bitor(x, 1);`
    출처: CtrigAsm f_LOr, eudplib 0.81 core/variable/eudv.py:443 `__or__`
    """
f_bitxor = _bitop("xor", "i64.bitxor")
f_bitxor.__name__ = "f_bitxor"
f_bitxor.__doc__ = """a ^ b 를 새 Int64 로 (= (a | b) ⊖ (a & b) — 마스크 Add 를 쓰지 않는다). 상수끼리는 int.

    인자: a, b — Int64·상수·문자열·32비트 변수
    반환: 새 Int64 (또는 int)
    비용: 변수끼리 = 호출 7 / 실행 17 (호출 자리 바이트가 공유 함수 호출과 비슷해 인라인), 한쪽 상수 = 3~4 / 7~10
          (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const m = x ^ y;`
    출처: CtrigAsm f_LXor (eudplib 0.81 `__xor__` 은 마스크 Add 식(인게임 확인 전, S8 A-1)에 기대므로 쓰지 않음)
    """


def f_bitnot(a):
    """~a (비트 반전)를 새 Int64 로 (0xFFFFFFFF ⊖ 반쪽 — 포화하지 않는 곳). 상수는 int.

    인자: a — Int64·상수·문자열·32비트 변수(0 확장 — 상위 반쪽은 0xFFFFFFFF)
    반환: 새 Int64 (또는 int)
    비용: 호출 1 / 실행 3 (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const y = ~x;` · `const y = i64.bitnot(x);`
    출처: CtrigAsm f_LNot
    """
    pa = _halves(a, "i64.bitnot")
    ka = _const_pair(pa)
    if ka is not None:
        return ka ^ M64
    return _new_value(lambda rl, rh: _not_into(rl, rh, pa))


def f_shl(a, n):
    """a << n (논리, n ≥ 64 → 0)를 새 Int64 로. `Int64.shl` 참고. epScript: `const y = i64.shl(x, n);`

    인자: a — 64비트 값, n — 0 이상 정수 또는 32비트 변수
    반환: 새 Int64 (상수끼리는 int)
    비용: `Int64.shl` 과 같음
    CP: 바꾸지 않음
    로컬: 공유 안전
    출처: CtrigAsm f_LlShift (시프트 양 해석이 다름 — 원본은 64 로 나눈 나머지)
    """
    pa = _halves(a, "i64.shl", "a")
    k = _shift_amount(n, "i64.shl")
    ka = _const_pair(pa)
    if ka is not None and isinstance(k, int):
        return 0 if k >= 64 else (ka << k) & M64
    return _new_value(lambda rl, rh: _shift_into("shl", rl, rh, pa, k))


def f_shr(a, n):
    """a >> n (논리, n ≥ 64 → 0)를 새 Int64 로. `Int64.shr` 참고. epScript: `const y = i64.shr(x, n);`

    인자: a — 64비트 값, n — 0 이상 정수 또는 32비트 변수
    반환: 새 Int64 (상수끼리는 int)
    비용: `Int64.shr` 과 같음
    CP: 바꾸지 않음
    로컬: 공유 안전
    출처: 없음(새 기능)
    """
    pa = _halves(a, "i64.shr", "a")
    k = _shift_amount(n, "i64.shr")
    ka = _const_pair(pa)
    if ka is not None and isinstance(k, int):
        return 0 if k >= 64 else ka >> k
    return _new_value(lambda rl, rh: _shift_into("shr", rl, rh, pa, k))


def f_to32(a, saturate=True, signed=False):
    """64비트 값을 32비트 값(새 EUDVariable)으로 줄인다.

    인자: a — 64비트 값, saturate — True(기본)면 범위를 넘을 때 끝값으로 멈춤, False 면 하위 32비트 그대로,
          signed — True 면 부호 있는 64비트로 읽어 [−2^31, 2^31 − 1] 로 (결과는 32비트 2의 보수)
    반환: EUDVariable (a 가 상수면 int)
    비용: 부호 없음 = 호출 2 / 실행 3, 부호 있음 = 호출 5 / 실행 6, saturate=False = 1 / 2 (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `var hp32 = i64.to32(hp);` · `var s = x.to32(signed=True);`
    출처: CtrigAsm f_Cast(_Cast(0, W) — 하위 반쪽) 대체 + 포화
    """
    if not isinstance(saturate, bool) or not isinstance(signed, bool):
        fail("i64.to32: saturate·signed 는 True/False 여야 합니다 (%r, %r)", saturate, signed)
    pa = _halves(a, "i64.to32")
    k = _const_pair(pa)
    if k is not None:
        if not saturate:
            return k & M32
        if signed:
            sv = k - (1 << 64) if k >> 63 else k
            return min(max(sv, -(1 << 31)), (1 << 31) - 1) & M32
        return min(k, M32)
    r = EUDVariable()
    _to32_into(r, pa, saturate, signed)
    return r


def f_abs(a):
    """|a| (부호 있는 64비트로 읽음, |−2^63| = 2^63 wrap)를 새 Int64 로. 상수는 int.

    인자: a — 64비트 값 (32비트 변수는 0 확장이라 그대로)
    반환: 새 Int64 (또는 int)
    비용: 호출 1 / 실행 10~18 (공유 본문 1벌 7, 음수면 부호 반전 +4~8) (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const d = i64.abs(i64.sub(a, b));`
    출처: CtrigAsm f_LAbs
    """
    pa = _halves(a, "i64.abs")
    k = _const_pair(pa)
    if k is not None:
        return ((-k) & M64) if k >> 63 else k
    return _new_value(lambda rl, rh: _abs_into(rl, rh, pa))


def f_rand():
    """64비트 난수 (eudplib `f_dwrand()` 두 번 — 하위·상위). 공유 상태(eudplib 시드)를 쓰므로 모든 클라이언트가 같은 값을 얻는다.

    인자: 없음
    반환: 새 Int64
    비용: 호출 약 8 / 실행 194 (f_dwrand 두 번 — eudplib 본문 공유) (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전 (로컬 블록 안에서 부르면 시드가 갈라져 디싱크 — eudplib f_dwrand 와 같음)
    epScript: `const r = i64.rand();`
    출처: CtrigAsm f_LRand(원본은 시드 스위치 64번), G3 1.10 "eudplib f_dwrand() 2회"
    """
    lo = f_dwrand()
    hi = f_dwrand()
    return Int64.wrap(lo.makeL(), hi.makeL())


_INPLACE_DOC = {
    "imul": "x ← x × b (64비트 wrap)",
    "idiv": "x ← x // b (부호 없음)",
    "imod": "x ← x % b (부호 없음)",
    "iand": "x ← x & b",
    "ior": "x ← x | b",
    "ixor": "x ← x ^ b",
    "ishl": "x ← x << n (논리, n ≥ 64 → 0)",
    "ishr": "x ← x >> n (논리, n ≥ 64 → 0)",
    "iabs": "x ← |x| (부호 있는 64비트)",
    "iinvert": "x ← ~x",
}


def _inplace_fn(method, what):
    def f(x, *args, **kw):
        return getattr(_target(x, "i64." + what), method)(*args, **kw)

    f.__name__ = "f_" + what
    f.__doc__ = "%s 제자리 (x 는 Int64, 반환 x). `x.%s(…)` 와 같다(비용도 같음). epScript: `i64.%s(x, …);`" % (
        _INPLACE_DOC[what],
        method,
        what,
    )
    return f


f_imul = _inplace_fn("imul", "imul")
f_idiv = _inplace_fn("idiv", "idiv")
f_imod = _inplace_fn("imod", "imod")
f_iand = _inplace_fn("iand", "iand")
f_ior = _inplace_fn("ior", "ior")
f_ixor = _inplace_fn("ixor", "ixor")
f_ishl = _inplace_fn("ishl", "ishl")
f_ishr = _inplace_fn("ishr", "ishr")
f_iabs = _inplace_fn("iabs", "iabs")
f_iinvert = _inplace_fn("iinvert", "iinvert")


def _into2(dst, fname, a, b, fill):
    """CtrigAsm 3인자 모양: dst ← f(a, b). dst 가 a·b 와 겹쳐도 된다(공유 함수·임시 변수가 먼저 읽는다)."""
    d = _target(dst, fname)
    d._check_write(fname)
    pa = _halves(a, fname, "Source")
    pb = None if b is None else _halves(b, fname, "Operand")
    fill(d.lo, d.hi, pa, pb)
    return d


def f_LMul(dst, a, b):
    """CtrigAsm `f_LMul`/`f_LiMul` 별칭: dst ← a × b (64비트 wrap). 반환 dst. epScript: `i64.LMul(x, x, 10);`"""
    return _into2(dst, "i64.LMul", a, b, _mul_into)


def f_LDiv(dst, a, b):
    """CtrigAsm `f_LDiv` 별칭: dst ← a // b (부호 없음, 0 나눗셈 = 2^64 − 1). 반환 dst. epScript: `i64.LDiv(x, x, 10);`"""
    return _into2(dst, "i64.LDiv", a, b, lambda dl, dh, pa, pb: _divmod_into((dl, dh), None, pa, pb))


def f_LMod(dst, a, b):
    """CtrigAsm `f_LMod` 별칭: dst ← a % b (부호 없음, 0 나눗셈 = a). 반환 dst. epScript: `i64.LMod(r, x, 10);`"""
    return _into2(dst, "i64.LMod", a, b, lambda dl, dh, pa, pb: _divmod_into(None, (dl, dh), pa, pb))


def f_LiDiv(dst, a, b):
    """CtrigAsm `f_LiDiv` 별칭: dst ← 부호 있는 몫(0 방향). 0 나눗셈은 CtrigAsm 규칙(div0="ctrig"). 반환 dst."""
    return _into2(dst, "i64.LiDiv", a, b, lambda dl, dh, pa, pb: _sdivmod_into((dl, dh), None, pa, pb, "ctrig"))


def f_LiMod(dst, a, b):
    """CtrigAsm `f_LiMod` 별칭: dst ← 부호 있는 나머지(피제수 부호, 0 나눗셈 = a). 반환 dst."""
    return _into2(dst, "i64.LiMod", a, b, lambda dl, dh, pa, pb: _sdivmod_into(None, (dl, dh), pa, pb, "ctrig"))


def f_LAnd(dst, a, b):
    """CtrigAsm `f_LAnd` 별칭: dst ← a & b. 반환 dst."""
    return _into2(dst, "i64.LAnd", a, b, lambda dl, dh, pa, pb: _bit_into("and", dl, dh, pa, pb))


def f_LOr(dst, a, b):
    """CtrigAsm `f_LOr` 별칭: dst ← a | b. 반환 dst."""
    return _into2(dst, "i64.LOr", a, b, lambda dl, dh, pa, pb: _bit_into("or", dl, dh, pa, pb))


def f_LXor(dst, a, b):
    """CtrigAsm `f_LXor` 별칭: dst ← a ^ b. 반환 dst."""
    return _into2(dst, "i64.LXor", a, b, lambda dl, dh, pa, pb: _bit_into("xor", dl, dh, pa, pb))


def f_LNot(dst, a):
    """CtrigAsm `f_LNot` 별칭: dst ← ~a. 반환 dst."""
    return _into2(dst, "i64.LNot", a, None, lambda dl, dh, pa, pb: _not_into(dl, dh, pa))


def f_LAbs(dst, a):
    """CtrigAsm `f_LAbs` 별칭: dst ← |a| (부호 있는 64비트). 반환 dst."""
    return _into2(dst, "i64.LAbs", a, None, lambda dl, dh, pa, pb: _abs_into(dl, dh, pa))


def f_LRand(dst):
    """CtrigAsm `f_LRand` 별칭: dst ← 64비트 난수 (eudplib f_dwrand 두 번 — 원본의 시드 스위치 방식과 값은 다르다). 반환 dst."""
    d = _target(dst, "i64.LRand")
    d._check_write("i64.LRand")
    r = f_rand()
    _assign(d.lo, d.hi, r.lo, r.hi)
    return d


f_LiMul = f_LMul

mul = f_mul
mul32 = f_mul32
div = f_div
mod = f_mod
divmod = f_divmod  # noqa: A001 — 모듈 안에서 파이썬 divmod 를 쓰지 않는다 (__all__ 에는 f_divmod 만)
sdiv = f_sdiv
smod = f_smod
sdivmod = f_sdivmod
bitand = f_bitand
bitor = f_bitor
bitxor = f_bitxor
bitnot = f_bitnot
shl = f_shl
shr = f_shr
to32 = f_to32
abs = f_abs  # noqa: A001 — 모듈 안에서 파이썬 abs 를 쓰지 않는다 (__all__ 에는 f_abs 만)
rand = f_rand
imul = f_imul
idiv = f_idiv
imod = f_imod
iand = f_iand
ior = f_ior
ixor = f_ixor
ishl = f_ishl
ishr = f_ishr
iabs = f_iabs
iinvert = f_iinvert
LMul = f_LMul
LiMul = f_LiMul
LDiv = f_LDiv
LMod = f_LMod
LiDiv = f_LiDiv
LiMod = f_LiMod
LAnd = f_LAnd
LOr = f_LOr
LXor = f_LXor
LNot = f_LNot
LAbs = f_LAbs
LRand = f_LRand


# =============================================================================================
# Int64Array
# =============================================================================================


class Int64Array(ExprProxy):
    """64비트 값 n 개 배열 = lo `EUDArray` + hi `EUDArray` (원소당 8B). 배열처럼 쓴다(ExprProxy — 3.11).

    - 읽기 `arr[i]` = 새 Int64 **사본**. 사본에 메서드·`.v` 로 제자리 연산을 하면 배열에 쓰이지 않으므로 오류로 알린다
      (epScript `arr[i].v += 1;` 함정). 파이썬 `arr[i] += v` 는 읽고-더하고-되쓰므로 맞지만 비싸다 → `arr.iadd(i, v)`.
    - 쓰기 `arr[i] = v`, 덧셈 `arr[i] += v`(iadditem), 뺄셈 `arr[i] -= v`(isubitem, **wrap**),
      포화 `arr.isub_sat(i, v)`(= `isubtractitem`, 64비트 전체 기준).
    - 비교 `arr[i] >= v` 등(epScript `_ARRC` → `geitem` …). 부호 있는 비교는 `i64.sge(arr[i], v)`.
    - 반쪽 배열: `arr.lo`, `arr.hi` (32비트 EUDArray). 칸 번호 i 의 칸 EPD = `arr.epd_lo + i`.
    - 칸 번호가 상수이고 값도 상수면 읽지 않고 칸을 바로 고친다(덧셈·wrap 뺄셈 2 트리거, 포화 2~4, 비교 0~2).
      그 밖에는 읽고(`f_dwread_epd` 두 번) 셈하고 다시 쓴다.
    인자: n_or_values — 원소 수(int) 또는 초기값 목록(64비트 정수·문자열)
    반환: -
    비용: 상수 칸·상수 값 = 위와 같음. 변수 칸 읽기 = f_dwread_epd × 2 (호출 4 / 실행 76), 쓰기 = 호출 2 / 실행 6,
          변수 칸 `arr[i] += y` = 호출 8 / 실행 87
          (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음 (eudplib 읽기·쓰기가 잠깐 옮기고 되돌림)
    로컬: 공유 안전
    epScript: `const gold = i64.Int64Array(8); gold[p] += 100; if (gold[p] >= 10000) { … }`
    출처: CtrigAsm CreateWArr 대체(원소 = 72B 변수 트리거 두 개 → 4B 칸 두 개), DESIGN 3.8·3.11
    """

    __slots__ = ("_hi", "_lo", "_n")

    def __init__(self, n_or_values):
        v = unProxy(n_or_values)
        if isinstance(v, bool) or not isinstance(v, (int, list, tuple)):
            fail("Int64Array: 원소 수(int) 또는 초기값 목록이 필요합니다 (%r)", n_or_values)
        if isinstance(v, int):
            if v <= 0:
                fail("Int64Array: 원소 수는 1 이상이어야 합니다 (%d)", v)
            lo, hi = EUDArray(v), EUDArray(v)
            n = v
        else:
            vals = [f_parse(x) for x in v]
            if not vals:
                fail("Int64Array: 빈 초기값 목록")
            lo = EUDArray([x & M32 for x in vals])
            hi = EUDArray([x >> 32 for x in vals])
            n = len(vals)
        super().__init__(lo)
        object.__setattr__(self, "_lo", lo)
        object.__setattr__(self, "_hi", hi)
        object.__setattr__(self, "_n", n)

    def __repr__(self):
        return "<eudext.i64.Int64Array n=%d>" % self._n

    def __len__(self):
        return self._n

    def __iter__(self):
        fail("Int64Array 는 파이썬에서 나열할 수 없습니다 (EUDLoopRange 로 번호를 돌리세요)")

    def __hash__(self):
        return id(self)

    @property
    def length(self):
        return self._n

    @property
    def lo(self):
        """하위 32비트 EUDArray."""
        return self._lo

    @property
    def hi(self):
        """상위 32비트 EUDArray."""
        return self._hi

    @property
    def epd_lo(self):
        return _compat.eudarray_epd(self._lo)

    @property
    def epd_hi(self):
        return _compat.eudarray_epd(self._hi)

    def _index(self, i, fname):
        i = unProxy(i)
        if isinstance(i, bool):
            i = int(i)
        if isinstance(i, int):
            if not 0 <= i < self._n:
                fail("%s: 칸 번호 %d 가 범위(0~%d) 밖입니다", fname, i, self._n - 1)
            return i
        if _compat.is_var(i):
            return i
        fail("%s: 칸 번호는 정수 또는 EUDVariable 이어야 합니다 (%r)", fname, i)
        return None

    def _cells(self, i):
        return _Cell(self.epd_lo + i), _Cell(self.epd_hi + i)

    # --- 읽기·쓰기 ---
    def get(self, i):
        """원소 i 를 새 Int64 사본으로 읽는다(제자리 연산 금지 표시). 비용: f_dwread_epd × 2."""
        i = self._index(i, "Int64Array.get")
        x = Int64.wrap(self._lo[i], self._hi[i])
        x._elem = True
        return x

    def __getitem__(self, i):
        return self.get(i)

    def set(self, i, value):
        """원소 i ← value (Int64·상수·32비트 변수). 비용: 상수 칸 = 호출 1, 변수 칸 = eudplib 쓰기 2번."""
        i = self._index(i, "Int64Array.set")
        vl, vh = _halves(value, "Int64Array.set")
        if isinstance(i, int):
            pairs = [(self.epd_lo + i, SetTo, vl), (self.epd_hi + i, SetTo, vh)]
            pairs.sort(key=lambda p: 0 if _isconst(p[2]) else 1)
            SeqCompute(pairs)
            return
        self._lo[i] = vl
        self._hi[i] = vh

    def __setitem__(self, i, value):
        self.set(i, value)

    def _modify(self, i, fname, fn):
        x = self.get(i)
        x._elem = False
        fn(x)
        self.set(i, x)

    def iadd(self, i, value):
        """원소 i += value (64비트 wrap). epScript `arr[i] += v;` (iadditem)."""
        i = self._index(i, "Int64Array.iadd")
        p = _halves(value, "Int64Array.iadd")
        if isinstance(i, int) and _both_const(p):
            _add_const(*self._cells(i), *p)
            return
        self._modify(i, "Int64Array.iadd", lambda x: _iadd(x.lo, x.hi, *p))

    def isub(self, i, value):
        """원소 i −= value (64비트 **wrap**). epScript `arr[i] -= v;` (isubitem)."""
        i = self._index(i, "Int64Array.isub")
        p = _halves(value, "Int64Array.isub")
        if isinstance(i, int) and _both_const(p):
            _add_const(*self._cells(i), *_split((-_join(*p)) & M64))
            return
        self._modify(i, "Int64Array.isub", lambda x: _isub(x.lo, x.hi, *p))

    def isub_sat(self, i, value):
        """원소 i ← max(원소 − value, 0) (**포화**, 64비트 전체 기준). epScript `arr.isub_sat(i, v);`."""
        i = self._index(i, "Int64Array.isub_sat")
        p = _halves(value, "Int64Array.isub_sat")
        if isinstance(i, int) and _both_const(p):
            _ssub_const(*self._cells(i), *p)
            return
        self._modify(i, "Int64Array.isub_sat", lambda x: _isub_sat(x.lo, x.hi, *p))

    iadditem = iadd
    isubitem = isub
    isubtractitem = isub_sat  # eudplib 관례: 이름에 Subtract = 포화 (S8 7.1-3)

    # --- 비교 (epScript arr[i] op v → _ARRC → *item) ---
    def _cmpitem(self, op, i, value):
        fname = "Int64Array." + op
        i = self._index(i, fname)
        if isinstance(i, int):
            pv = _halves(value, fname)
            if op in _MIRROR:
                o, a, b = _MIRROR[op], pv, self._cells(i)
            else:
                o, a, b = op, self._cells(i), pv
            plan = Plan()
            conds = _result(plan, *_plan64(o, a, b))
            plan.emit()
            return conds[0] if len(conds) == 1 else conds
        return _compare(op, self.get(i), value, fname)

    def eqitem(self, i, value):
        return self._cmpitem("eq", i, value)

    def neitem(self, i, value):
        return self._cmpitem("ne", i, value)

    def geitem(self, i, value):
        return self._cmpitem("ge", i, value)

    def leitem(self, i, value):
        return self._cmpitem("le", i, value)

    def gtitem(self, i, value):
        return self._cmpitem("gt", i, value)

    def ltitem(self, i, value):
        return self._cmpitem("lt", i, value)

    # --- 곱셈·나눗셈·비트·시프트 (2차, WP4): 원소를 읽고 셈하고 다시 쓴다 (D26 전까지) ---
    # 상수 칸 & | 상수 값만 칸에 바로 마스크 SetTo (읽기 없음).

    def _pairop(self, i, value, fname, fn):
        i = self._index(i, fname)
        p = _halves(value, fname)
        self._modify(i, fname, lambda x: fn(x.lo, x.hi, x._pair(), p))

    def imul(self, i, value):
        """원소 i ← 원소 × value (64비트 wrap). epScript `arr[i] *= v;` (imulitem). 비용: 읽기 + `Int64.imul` + 쓰기."""
        self._pairop(i, value, "Int64Array.imul", _mul_into)

    def idiv(self, i, value):
        """원소 i ← 원소 // value (부호 없음). epScript `arr[i] /= v;` (ifloordivitem)."""
        self._pairop(i, value, "Int64Array.idiv", lambda dl, dh, pa, pb: _divmod_into((dl, dh), None, pa, pb))

    def imod(self, i, value):
        """원소 i ← 원소 % value (부호 없음). epScript `arr[i] %= v;` (imoditem)."""
        self._pairop(i, value, "Int64Array.imod", lambda dl, dh, pa, pb: _divmod_into(None, (dl, dh), pa, pb))

    def _maskop(self, i, value, op):
        fname = "Int64Array.i" + op
        i = self._index(i, fname)
        p = _halves(value, fname)
        if isinstance(i, int) and _both_const(p):
            acts = []
            for epd, k in ((self.epd_lo + i, p[0]), (self.epd_hi + i, p[1])):
                if op == "and" and k != M32:
                    acts.append(SetMemoryXEPD(epd, SetTo, 0, ~k & M32))
                elif op == "or" and k:
                    acts.append(SetMemoryXEPD(epd, SetTo, M32, k))
            if acts:
                RawTrigger(actions=acts)
            return
        self._modify(i, fname, lambda x: _bit_into(op, x.lo, x.hi, x._pair(), p))

    def iand(self, i, value):
        """원소 i ← 원소 & value. 상수 칸·상수 값은 칸에 바로 (호출 1 / 실행 1). epScript `arr[i] &= v;` (ianditem)."""
        self._maskop(i, value, "and")

    def ior(self, i, value):
        """원소 i ← 원소 | value. 상수 칸·상수 값은 칸에 바로 (호출 1 / 실행 1). epScript `arr[i] |= v;` (ioritem)."""
        self._maskop(i, value, "or")

    def ixor(self, i, value):
        """원소 i ← 원소 ^ value. epScript `arr[i] ^= v;` (ixoritem)."""
        self._pairop(i, value, "Int64Array.ixor", lambda dl, dh, pa, pb: _bit_into("xor", dl, dh, pa, pb))

    def ishl(self, i, n):
        """원소 i ← 원소 << n (논리). epScript `arr[i] <<= n;` (ilshiftitem)."""
        i = self._index(i, "Int64Array.ishl")
        k = _shift_amount(n, "Int64Array.ishl")
        self._modify(i, "Int64Array.ishl", lambda x: _shift_into("shl", x.lo, x.hi, x._pair(), k))

    def ishr(self, i, n):
        """원소 i ← 원소 >> n (논리). epScript `arr[i] >>= n;` (irshiftitem)."""
        i = self._index(i, "Int64Array.ishr")
        k = _shift_amount(n, "Int64Array.ishr")
        self._modify(i, "Int64Array.ishr", lambda x: _shift_into("shr", x.lo, x.hi, x._pair(), k))

    imulitem = imul
    ifloordivitem = idiv
    imoditem = imod
    ianditem = iand
    ioritem = ior
    ixoritem = ixor
    ilshiftitem = ishl
    irshiftitem = ishr
