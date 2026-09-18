"""128비트 부호 없는 정수 값 타입 `Int128` 과 배열 `Int128Array` (DESIGN 4.4b, 3.2, 3.3, 3.5) — WP20.

    from eudext import i128
    from eudext.i128 import Int128, Int128Array

    dps = Int128(0)                       # 초기값만 (트리거 0). Int128("340282366920938463463374607431768211455") 도 된다
    dps += dmg                            # 128비트 덧셈 (Int64·32비트 변수는 0 확장)
    dps.isub_sat(used)                    # 포화 뺄셈 — 128비트 전체 기준 (반쪽별 포화가 아니다)
    p = i128.mul64(a64, b64)              # 64×64 → 128 전체 곱 (DPS f_LMul128)
    q, r = i128.divmod(p, 100)            # 128 ÷ 64 (몫 128비트, 나머지 < 제수)
    if EUDIf()(dps >= 10 ** 30): ...      # 부호 없는 사전식 비교 → 조건
    f_dbstr_print(buf, dps.fmt())         # 10진 출력 (최대 39자리)
    lo = dps.to64()                       # 64비트로 내리기 (포화)

epScript (`import eudext.i128 as i128;` — 값 타입은 const 로 묶는다, 3.11):

    const dps = i128.Int128(0);
    dps.v += i128.mul64(a, b);            // 제자리 연산은 .v 통로 (iaddattr/isubattr/imulattr/ifloordivattr/imodattr)
    dps.isub_sat(used);                   // 포화
    if (dps >= 1000000000000000000000) printAll("DPS {}", dps.fmt());

## 무엇을 주는가 (DPS `math128.lua` 가 쓰는 연산만 — 설계 4.4b, 7절 D12)

| 연산 | 이름 | 의미 |
|---|---|---|
| 생성·대입 | `Int128(상수)`·`Int128(Int64)`·`Int128(lo64, hi64)`·`Int128.wrap(lo, hi)`·`x << y`·`x.v = y` | 3.2 값 타입 규약 |
| 덧셈 | `x + y`, `x += y`, `x.iadd(y)`, `i128.add(a, b)` | 128비트 **wrap** |
| 뺄셈 | `x - y`, `x -= y`, `-x`, `x.isub(y)`, `i128.sub(a, b)`, `i128.neg(a)` | 128비트 **wrap** |
| 포화 뺄셈 | `x.isub_sat(y)`, `i128.sub_sat(a, b)`, `x.isubtractattr("v", y)`, `LSub128` | **128비트 전체 기준**, 0 에서 멈춤 |
| 비교 | `>= <= > < == !=`, `i128.ge(a, b)` … | 부호 없는 사전식 → 조건 |
| 곱셈 | `x * y`, `x *= y`, `i128.mul(a, b)`, `i128.mul64(a, b)`, `LMul128` | 128비트 **wrap** (64×64 는 전체 곱) |
| 나눗셈 | `x // y`, `x % y`, `divmod(x, y)`, `i128.div/mod/divmod`, `LDiv128` | 부호 없음. 제수는 128비트까지. 0 나눗셈 = 몫 2^128 − 1, 나머지 = 피제수 |
| 10진 | `x.fmt()`, `i128.fmt(x)`, `i128.lidec_to(dst_epd, x)` | 최대 39자리 (40칸 고정 폭 + 앞자리 수) |
| 내리기 | `x.to64(saturate=True)`, `x.to32(saturate=True)` | 포화 = 최댓값에서 멈춤, 아니면 하위 비트 |
| 배열 | `Int128Array(n)` | 원소 16B (EUDArray 넷) — DPS 의 플레이어별 128비트 값(PVWArrX 쌍) |

부호 있는 128비트·비트 연산·시프트는 DPS 가 쓰지 않아 만들지 않았다(DESIGN 4.4b).

## 뺄셈의 두 의미 (DESIGN 3.5)

- wrap: `x -= y`, `x - y`, `-x`, `x.isub(y)`, `x.v -= y`, `i128.sub`, `i128.neg`, `arr[i] -= v`(isubitem).
- 포화: `x.isub_sat(y)`, `i128.sub_sat`, `i128.isub_sat`, `arr.isub_sat(i, v)`(= `isubtractitem`), `x.isubtractattr("v", y)`,
  `i128.LSub128` — **128비트 전체 기준**(`a ≥ b ? a − b : 0`). DPS `math128.f_LSub128` 은 상위 64비트를 먼저 포화로 빼고
  하위를 보정해 `a < b` 인데 0 이 아닌 값을 내는 경우가 있다(상위가 작고 하위가 클 때) — 그 반쪽별 포화는 옮기지 않았다.
- 같은 객체끼리 `x -= x`·`sub_sat(x, x)` 는 0 으로 접는다(eudplib `v -= v` 버그를 물려받지 않는다).

## 피연산자

`Int128`, `Int64`(0 확장), 정수 상수(−2^127 ~ 2^128 − 1, 음수는 2의 보수), 10진 문자열(`parse` 와 같음),
32비트 `EUDVariable`(0 확장), `EUDLightVariable`·읽기 전용 값 칸(읽어서 씀). 32비트 변수가 **왼쪽**인 `v * x`·`v // x`·
`v % x` 는 eudplib 연산자가 먼저 불려 안내 오류 → `i128.mul(v, x)` 등 모듈 함수. **Int64 가 왼쪽**인 `i64값 + x`·
`i64값 >= x` 도 i64 연산자가 먼저 불려 오류다 → `i128.add(i64값, x)`·`i128.ge(i64값, x)`. 반쪽: `x.lo`·`x.hi`(Int64 — 복사 없이
같은 변수), 칸: `x.w0`~`x.w3`(32비트 EUDVariable, w0 이 최하위). 나머지(`%`·`divmod`)도 Int128 이다(제수가 64비트 이하면
위 64비트는 0 — `r.lo` 가 Int64. 0 나눗셈이면 피제수 그대로라서 128비트).

## 알고리즘과 비용 (에뮬레이터 실측 — docs/COSTS.md "i128 (WP20)", 2026-09-17. 호출 자리 / 실행)

- 덧셈(변수): 네 칸을 한 줄에 더하고, 칸마다 올림을 깃발로 전파한다 — 생성 `[y_k > 새 x_k]`(조건 amount 에 새 x_k + 1 을
  채움), 넘김 `[올림 들어옴][x_k = 0xFFFFFFFF] → x_k ← 0, 깃발 2`, 더함 `[올림 들어옴][깃발 ≤ 1] → x_k += 1`(DPS 이식판
  `war.AddWords` 와 같은 생각). 펼치면 9 / 16 이지만 호출 자리 바이트가 공유 함수 호출의 1.6배(4.5KB / 2.8KB)라, 변수끼리는
  **공유 함수가 기본**(1 / 35, DESIGN 3.3)이고 32비트 값은 펼친다(7 / 9). `inline=True/False` 로 고른다.
  wrap 뺄셈은 `x + ~y + 1`(~ = 0xFFFFFFFF ⊖ — 포화하지 않음, 1 / 39 · 펼침 9 / 20), 포화 뺄셈은 거기에 마지막 올림이
  없으면(= 빌림) 0(공유 함수 1 / 43 · 펼침 12 / 24). 상수는 위 칸부터 "올림이 들어오는 경우"를 서로 배타인 조건 묶음으로
  펼쳐 깃발 없이 4~7 / 4~7, 상수 포화는 `x < K → x ← K` 묶음 + 상수 뺄셈(8~11).
- 비교: i64 의 비교 계획(DPS a7aad90 `tlib.py:204`)을 칸 넷으로 넓혔다 — `x ≥ y = [x3 ≥ y3] ∧ ¬([x3 ≤ y3] ∧ (y 나머지 > x 나머지))`
  를 재귀로, 부정 부분마다 자기 칸 깃발을 끄는 조건 트리거 하나. 변수끼리 5 / 12, `==` 2 / 6, 상수 1~5 / 1~5.
- 곱셈(변수 64×64 → 128 전체): 곱해지는 수를 16비트 조각 넷으로, 곱하는 수의 비트마다 조건 트리거 하나가 두 배씩 느는 조각을
  16개의 넘치지 않는 누적기(조각 쌍마다)에 더한다(i64 16비트 쪼개기의 전체 곱 판). 끝에서 홀수 가중치 누적기를 합쳐 16비트로
  가르고 칸마다 올림을 세며 더한다. 1 / 165~585 (본문 251). 128비트가 끼면 `하위 64비트 전체 곱 + (상위 × 하위 mod 2^64) << 64`
  (i64 곱셈 본문) — 128×64 104~963, 128×128 108~1,326. 상수 곱은 곱해지는 수의 비트마다 상수 조각을 칸별 누적기(넘치지 않게
  하위·상위 비트로 나눔)에 더하는 비트 누적(상수마다 본문 117~184, 실행 20~196).
- 나눗셈: 32비트 제수는 i64 64÷64 본문을 칸마다(몫 칸 < 2^32 — 124~703), 64비트 제수는 "나머지 < D 인 96÷64 한 칸" 본문
  (32단 복원 나눗셈 — i64 의 64비트 제수 단 + 넘침 비트)을 위 칸부터(127~약 1,050), 128비트 제수는 몫 < 2^64 인 64단 복원 나눗셈
  (빌림 조합 8가지 조건 트리거가 맞는 뺄셈 사슬로 — 48~약 1,270). 상수 제수 < 2^32 는 i64 상수 제수 본문(이식판 a41d2ed `_cdiv`)을
  위 칸부터 세 번(40~231 — 칸 넷 한 번에 나누는 본문보다 한 번 페이로드가 절반 이하이고 i64 와 같이 쓴다), 그 이상 상수는
  변수 제수 본문.
- 10진: 39자리 중 10^38 ~ 10^19 자리는 `b·10^i`(b = 8·4·2·1) 복원 뺄셈을 빌림 조합마다 배타 트리거로(값 < 2c 불변식 — 한 단에서
  하나만 참), 남은 값(< 10^19)은 i64 10진 본문(`_lidec_body`)을 그대로 부른다. 값 < 2^64 면 윗 단을 건너뛴다.
  호출 7 / 실행 176~536 (본문 372 + i64 137).
- 한 번 페이로드(빈 빌드 대비, 호출 하나 포함): 덧셈 공유 함수 약 8KB, 64×64 곱 약 123KB, 128×128 곱 약 198KB, 상수 곱 상수마다
  약 36~48KB, 상수 나눗셈 상수마다 약 45KB(그중 약 36KB 는 i64 상수 본문), 32비트 제수 나눗셈 약 153KB(i64 나눗셈 본문 포함),
  64비트 제수 약 222KB, 128비트 제수 약 374KB, 10진 약 213KB(i64 10진 본문 48KB 포함).

출처: DESIGN 4.4b, DPS_Enhance `CallTriggers/utils/math128.lua`·`converter.lua`(호출 모양·0 나눗셈 규칙),
DPS_Enhance eudplib-port a7aad90(받아 둔 사본 HEAD e7efff2) `eud/ctrig/war.py:1075~1260`(`_div128`·`_mul6464`·`Div128`·`Mul128`·
`AddWords`·`SubWords`), `eud/tests/t_war.py:89~138` 기대값, eudext.i64(WP3·WP4)의 비교 계획·곱셈·나눗셈·10진 본문.
"""

import functools

from eudplib import (
    EPD,
    Add,
    Always,
    AtLeast,
    AtMost,
    Db,
    EUDArray,
    EUDElse,
    EUDElseIf,
    EUDEndIf,
    EUDFunc,
    EUDIf,
    EUDJumpIf,
    EUDLightVariable,
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
    SetNextPtr,
    SetNextTrigger,
    SetTo,
    Subtract,
    f_dwwrite_epd,
    ptr2s,
    unProxy,
)

from eudext import _compat
from eudext import i64 as _i64
from eudext._parts import (
    Plan,
    SelfFrame,
    add_modifiers,
    flag_cond,
    placeholder,
    var_chain,
)
from eudext.errors import fail
from eudext.i64 import Int64

M16 = 0xFFFF
M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
M128 = (1 << 128) - 1
SIGN = 0x80000000
S127 = 1 << 127
S128MIN = -(1 << 127)

# i64 내부 부품 (같은 패키지 — 고치지 않고 쓴다. 목록은 DESIGN 4.4b 위험 ③)
_Cell = _i64._Cell
_isvar = _i64._isvar
_isconst = _i64._isconst
_epd = _i64._epd
_rd = _i64._rd
_act = _i64._act
_read_tmp = _i64._read_tmp
GE, LE, EQ = _i64.GE, _i64.LE, _i64.EQ
_cmp = _i64._cmp
_gt = _i64._gt
_and = _i64._and
_negate = _i64._negate
_simplify = _i64._simplify
_conds = _i64._conds

__all__ = [
    "Compare_128",
    "Int128",
    "Int128Array",
    "LAdd128",
    "LCmp128",
    "LDiv128",
    "LMov128",
    "LMul128",
    "LMul128_2",
    "LSub128",
    "add",
    "div",
    "eq",
    "f_LAdd128",
    "f_LCmp128",
    "f_LDiv128",
    "f_LMov128",
    "f_LMul128",
    "f_LSub128",
    "f_add",
    "f_div",
    "f_divmod",
    "f_eq",
    "f_fmt",
    "f_ge",
    "f_gt",
    "f_iadd",
    "f_idiv",
    "f_imod",
    "f_imul",
    "f_isub",
    "f_isub_sat",
    "f_le",
    "f_lidec_to",
    "f_lt",
    "f_mod",
    "f_mul",
    "f_mul64",
    "f_ne",
    "f_neg",
    "f_parse",
    "f_sub",
    "f_sub_sat",
    "f_to32",
    "f_to64",
    "f_wrap",
    "fmt",
    "ge",
    "gt",
    "iadd",
    "idiv",
    "imod",
    "imul",
    "isub",
    "isub_sat",
    "le",
    "lidec_to",
    "lt",
    "mod",
    "mul",
    "mul64",
    "ne",
    "neg",
    "parse",
    "sub",
    "sub_sat",
    "to32",
    "to64",
    "wrap",
]


# =============================================================================================
# 상수
# =============================================================================================


def _check_int(v, fname):
    if not S128MIN <= v <= M128:
        fail("%s: 128비트 범위(−2^127 ~ 2^128−1) 밖의 상수 %d", fname, v)
    return v & M128


def f_parse(s):
    """10진(또는 `0x` 16진) 문자열 상수를 128비트 정수로 바꾼다(컴파일 시점).

    `_`·`,`·공백은 무시한다. 음수는 2의 보수(`"-1"` = 2^128 − 1). 범위(−2^127 ~ 2^128−1) 밖·형식 오류는 EPError.
    인자: s(str) — 정수를 넘기면 범위만 검사해 그대로
    반환: int (0 ~ 2^128−1)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const k = i128.parse("100000000000000000000000");` (→ `i128.f_parse`)
    출처: DPS math128 의 10진 문자열 칸 상수(`{"100", "0"}`) 대체, eudext.i64.parse 와 같은 규칙
    """
    if isinstance(s, bool):
        s = int(s)
    if isinstance(s, int):
        return _check_int(s, "i128.parse")
    if isinstance(s, bytes):
        s = s.decode("ascii", "replace")
    if not isinstance(s, str):
        fail("i128.parse: 문자열이 아닙니다 (%r)", s)
    t = s.strip().replace("_", "").replace(",", "").replace(" ", "")
    try:
        v = int(t, 0) if t.lower().lstrip("+-").startswith(("0x", "0b", "0o")) else int(t, 10)
    except ValueError:
        fail("i128.parse: 정수 문자열이 아닙니다 (%r)", s)
    return _check_int(v, "i128.parse")


parse = f_parse


def _split4(v):
    v &= M128
    return (v & M32, (v >> 32) & M32, (v >> 64) & M32, v >> 96)


def _join4(ws):
    return ws[0] | (ws[1] << 32) | (ws[2] << 64) | (ws[3] << 96)


# =============================================================================================
# 피연산자 → 칸 넷 (w0 이 최하위). 칸은 32비트 int 또는 EUDVariable (배열 상수 칸은 _Cell)
# =============================================================================================


def _words(o, fname, what="피연산자"):
    """o → (w0, w1, w2, w3). 필요하면 임시 변수로 옮기는 트리거를 이 자리에 낸다."""
    if isinstance(o, Int128):
        return o._w
    u = unProxy(o)
    if isinstance(u, Int128):
        return u._w
    if isinstance(u, Int64):
        return (u.lo, u.hi, 0, 0)
    if isinstance(u, bool):
        u = int(u)
    if isinstance(u, int):
        return _split4(_check_int(u, fname))
    if isinstance(u, (str, bytes)):
        return _split4(f_parse(u))
    lo, hi = _i64._halves(u, fname, what)
    return (lo, hi, 0, 0)


def _half64(o, fname, what):
    """Int128(lo, hi) 의 반쪽 하나 → (w, w). Int128 은 오류, 정수는 −2^63 ~ 2^64−1."""
    u = unProxy(o)
    if isinstance(u, Int128):
        fail("%s: %s 에 Int128 을 넣을 수 없습니다 (64비트 값이어야 합니다)", fname, what)
    return _i64._halves(u, fname, what)


def _all_const(p):
    return all(_isconst(h) for h in p)


def _const4(p):
    return _join4(p) if _all_const(p) else None


def _same(p, q):
    return all(a is b for a, b in zip(p, q))


def _overlap(dst, src):
    """dst 칸이 src 칸 어디와든 같은 객체인가."""
    return any(d is s for d in dst for s in src if not _isconst(s))


def _width(p):
    """상위 칸이 상수 0 인 것을 뺀 칸 수 (0~4)."""
    n = 4
    while n and _isconst(p[n - 1]) and p[n - 1] == 0:
        n -= 1
    return n


# =============================================================================================
# 임시 변수·깃발 (빌드마다 새로. 인라인 연산 한 번 안에서만 쓴다)
# =============================================================================================

_scr = []
_flg = []


def _scratch(n):
    while len(_scr) < n:
        _scr.append(EUDVariable())
    return _scr[:n]


def _flags():
    while len(_flg) < 4:
        _flg.append(EUDLightVariable())
    return _flg[:4]


@_compat.register_build_reset
def _reset_scratch():
    del _scr[:]
    del _flg[:]


def _new4():
    return tuple(EUDVariable() for _ in range(4))


def _copy4(p, tmps):
    """p 를 tmps 로 옮기고 새 칸 넷 반환 (상수 칸은 그대로)."""
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


def _dest(d):
    return d.epd if isinstance(d, _Cell) else d


def _assign4(dw, sw):
    """dw ← sw (dw 칸은 변수 또는 _Cell, sw 칸은 int 또는 변수). 칸이 엇갈려 겹쳐도 맞게."""
    sw = list(sw)
    pos = {id(d): i for i, d in enumerate(dw)}
    need = [i for i, s in enumerate(sw) if not _isconst(s) and pos.get(id(s), i) != i]
    if need:
        tm = _scratch(4)
        SeqCompute([(tm[i], SetTo, sw[i]) for i in need])
        for i in need:
            sw[i] = tm[i]
    pairs = [(_dest(d), SetTo, (s & M32) if _isconst(s) else s) for d, s in zip(dw, sw) if s is not d]
    pairs.sort(key=lambda p: 0 if _isconst(p[2]) else 1)
    if pairs:
        SeqCompute(pairs)


# =============================================================================================
# 덧셈·뺄셈
# =============================================================================================


def _addk_emit(xw, K):
    """x += K (mod 2^128), K 상수. x 칸은 변수 또는 _Cell. 트리거 1 + 올림 0~6 (위 칸부터 — 깃발 없음).

    칸 j 로 올림이 들어오는 경우 = `[s_(j−1) ≤ k_(j−1) − 1]` 또는 `[s_(j−1) = 0xFFFFFFFF] ∧ (칸 j−1 로 올림)` — 서로 배타인
    조건 묶음으로 펼친다. 위 칸의 묶음이 아래 칸을 읽으므로 위 칸부터 더한다(아래 칸은 아직 그대로다).
    """
    K &= M128
    if not K:
        return
    k = _split4(K)
    RawTrigger(actions=[_act(x, Add, kk) for x, kk in zip(xw, k) if kk])
    pats = [[]]  # pats[j] = 칸 j 로 올림이 들어오는 경우들 (각각 원자 목록)
    for j in range(3):
        cur = [[(j, AtMost, k[j] - 1)]] if k[j] else []
        cur += [[(j, Exactly, M32)] + p for p in pats[j]]
        pats.append(cur)
    for j in (3, 2, 1):
        for p in pats[j]:
            RawTrigger(conditions=[_rd(xw[i], c, v) for i, c, v in p], actions=_act(xw[j], Add, 1))


def _ssubk_emit(xw, K):
    """x ← max(x − K, 0), K 상수 (x 칸은 변수 또는 _Cell). x < K 면 먼저 x ← K 로 두고(서로 배타인 조건 묶음 0~4) K 를 뺀다."""
    K &= M128
    if not K:
        return
    k = _split4(K)
    for j in (3, 2, 1, 0):
        if not k[j]:
            continue
        conds = [_rd(xw[i], Exactly, k[i]) for i in range(3, j, -1)] + [_rd(xw[j], AtMost, k[j] - 1)]
        RawTrigger(conditions=conds, actions=[_act(x, SetTo, kk) for x, kk in zip(xw, k)])
    _addk_emit(xw, (-K) & M128)


def _complement(yw, tmps):
    """~y 칸 (0xFFFFFFFF ⊖ y — 포화하지 않는다, 3.5-7). → (pre_c, pre_v, 칸 넷)."""
    pre_c, pre_v, out = [], [], []
    for y, t in zip(yw, tmps):
        if _isconst(y):
            out.append(~y & M32)
            continue
        pre_c.append((t, SetTo, M32))
        pre_v.append((t, Subtract, y))
        out.append(t)
    return pre_c, pre_v, tuple(out)


def _addv_emit(xw, yw, cin=0, cout=False, init=None, pre=((), ()), flags=None):
    """x ← (init 또는 x) + y + cin (128비트 wrap). 호출 자리에 펼친다.

    xw: 변수 넷(목적지). yw: int·변수 넷(xw 와 겹치지 않음). init: None(제자리) 또는 원천 넷(같은 자리의 x 는 제자리).
    cout=True 면 마지막 올림 깃발(EUDLightVariable, 0 = 올림 없음)을 돌려준다.
    한 줄: x_k ← … + y_k, 채움 amt_k ← 새 x_k (+1). 그 뒤 칸마다 생성 G_k `[y_k > 새 x_k]`(또는 cin 이 있는 칸 0 은 `[y_0 ≥ 새 x_0]`),
    넘김 W_k `[c_k ≥ 1][x_k = M32] → x_k ← 0, c_(k+1) ← 2`, 더함 I_k `[c_k ≥ 1][c_(k+1) ≤ 1] → x_k += 1`.
    G_k 가 참이면 x_k < y_k ≤ M32 라 W_k 는 거짓이고 I_k 는 넘치지 않는다. W_k 가 참이면 c_(k+1) = 2 라 I_k 는 거짓이다.
    """
    c = flags if flags is not None else _flags()
    consts = list(pre[0])
    vars_ = list(pre[1])
    trigs = []
    possible = False  # 칸 k 로 올림이 들어올 수 있는가
    for k in range(4):
        x, y = xw[k], yw[k]
        addk = cin if k == 0 else 0
        s = None if init is None else init[k]
        setting = s is not None and s is not x
        cterm = addk + (y if _isconst(y) else 0)
        vterms = []
        if setting:
            if _isconst(s):
                cterm += s
            else:
                vterms.append(s)
        if not _isconst(y):
            vterms.append(y)
        if setting:
            consts.append((x, SetTo, cterm & M32))
        elif cterm & M32:
            consts.append((x, Add, cterm & M32))
        vars_ += [(x, Add, v) for v in vterms]
        need_out = k < 3 or cout
        gen = None  # None = 올림이 생기지 않음, [] = 늘 생김
        if need_out:
            if _isconst(y):
                t = y + addk
                if t >> 32:
                    gen = []
                elif t:
                    gen = [x.AtMost(t - 1)]
            else:
                cond = MemoryEPD(_epd(y), AtLeast, placeholder())
                amt = EPD(cond) + 2
                if addk:  # 올림 ⇔ y ≥ 새 x
                    vars_.append((amt, SetTo, x))
                    gen = [cond]
                else:  # 올림 ⇔ y ≥ 새 x + 1 (새 x = M32 면 채움이 0 으로 돈다 → 막이)
                    consts.append((amt, SetTo, 1))
                    vars_.append((amt, Add, x))
                    gen = [cond, MemoryEPD(amt, AtLeast, 1)]
            nf = c[k]
            consts.append((EPD(nf.getValueAddr()), SetTo, 1 if gen == [] else 0))
            if gen:
                trigs.append((gen, [nf.SetNumber(1)]))
        if k and possible:
            inf = c[k - 1]
            if need_out:
                nf = c[k]
                trigs.append(([inf.AtLeast(1), x.Exactly(M32)], [x.SetNumber(0), nf.SetNumber(2)]))
                trigs.append(([inf.AtLeast(1), nf.AtMost(1)], [x.AddNumber(1)]))
            else:
                trigs.append(([inf.AtLeast(1)], [x.AddNumber(1)]))
        possible = need_out and (gen is not None or possible)
    if consts or vars_:
        SeqCompute(consts + vars_)
    for conds, acts in trigs:
        RawTrigger(conditions=conds, actions=acts)
    return c[3] if cout else None


@functools.cache
def _addsub_fn(op):
    """변수끼리 공유 본문 (op = add | sub | ssub): (x0..x3, y0..y3) → x op y."""

    def body(x0, x1, x2, x3, y0, y1, y2, y3):
        xw, yw = (x0, x1, x2, x3), (y0, y1, y2, y3)
        fl = [EUDLightVariable() for _ in range(4)]
        if op == "add":
            _addv_emit(xw, yw, flags=fl)
        else:
            pc, pv, nw = _complement(yw, _new4())
            cf = _addv_emit(xw, nw, cin=1, cout=op == "ssub", pre=(pc, pv), flags=fl)
            if op == "ssub":
                RawTrigger(conditions=cf.Exactly(0), actions=[x.SetNumber(0) for x in xw])
        EUDReturn(*xw)

    body.__name__ = body.__qualname__ = "i128_" + op
    return EUDFunc(body)


def _nvar(p):
    return sum(1 for h in p if not _isconst(h))


def _auto_inline(inline, yw):
    """inline=None(기본) → 변수 칸이 하나 이하(32비트 값)면 펼치고, 그 밖은 공유 함수 (DESIGN 3.3 — 호출 자리 바이트)."""
    if inline is None:
        return _nvar(yw) <= 1
    return bool(inline)


def _iadd4(xw, yw, inline=None):
    """x += y (x 칸은 변수)."""
    inline = _auto_inline(inline, yw)
    K = _const4(yw)
    if K is not None:
        _addk_emit(xw, K)
        return
    if _overlap(xw, yw):
        yw = _copy4(yw, _scratch(8)[4:])
    if not inline:
        _addsub_fn("add")(*xw, *yw, ret=list(xw))
        return
    _addv_emit(xw, yw)


def _isub4(xw, yw, inline=None):
    """x −= y (wrap)."""
    inline = _auto_inline(inline, yw)
    K = _const4(yw)
    if K is not None:
        _addk_emit(xw, (-K) & M128)
        return
    if _same(xw, yw):
        _assign4(xw, (0, 0, 0, 0))
        return
    if _overlap(xw, yw):
        yw = _copy4(yw, _scratch(8)[4:])
    if not inline:
        _addsub_fn("sub")(*xw, *yw, ret=list(xw))
        return
    pc, pv, nw = _complement(yw, _scratch(4))
    _addv_emit(xw, nw, cin=1, pre=(pc, pv))


def _isub_sat4(xw, yw, inline=False):
    """x ← max(x − y, 0) (128비트 전체 기준). inline=None 은 False(공유 함수)."""
    inline = bool(inline)
    K = _const4(yw)
    if K is not None:
        _ssubk_emit(xw, K)
        return
    if _same(xw, yw):
        _assign4(xw, (0, 0, 0, 0))
        return
    if _overlap(xw, yw):
        yw = _copy4(yw, _scratch(8)[4:])
    if not inline:
        _addsub_fn("ssub")(*xw, *yw, ret=list(xw))
        return
    pc, pv, nw = _complement(yw, _scratch(4))
    cf = _addv_emit(xw, nw, cin=1, cout=True, pre=(pc, pv))
    RawTrigger(conditions=cf.Exactly(0), actions=[x.SetNumber(0) for x in xw])


def _op3(rw, pa, pb, op, inline):
    """r ← a op b (op = add | sub | ssub). r 은 a·b 와 겹치지 않는 새 변수 넷. inline=None 은 add·sub 자동, ssub 공유 함수."""
    ka, kb = _const4(pa), _const4(pb)
    if op == "add" and ka is None and kb is None and _nvar(pb) > _nvar(pa):
        pa, pb = pb, pa  # 더하는 쪽(채움 원천)을 좁은 값으로
    if inline is None:
        inline = False if op == "ssub" else _auto_inline(None, pb)
    if ka is not None and kb is not None:
        v = ka + kb if op == "add" else ka - kb if op == "sub" else max(ka - kb, 0)
        _assign4(rw, _split4(v))
        return
    if op == "add" and kb is None and ka is not None:
        pa, pb, ka, kb = pb, pa, kb, ka
    if kb is not None:
        _assign4(rw, pa)
        if op == "add":
            _addk_emit(rw, kb)
        elif op == "sub":
            _addk_emit(rw, (-kb) & M128)
        else:
            _ssubk_emit(rw, kb)
        return
    if op != "add" and _same(pa, pb):
        _assign4(rw, (0, 0, 0, 0))
        return
    if not inline:
        _addsub_fn(op)(*pa, *pb, ret=list(rw))
        return
    if op == "add":
        _addv_emit(rw, pb, init=pa)
        return
    pc, pv, nw = _complement(pb, _scratch(4))
    cf = _addv_emit(rw, nw, cin=1, cout=op == "ssub", init=pa, pre=(pc, pv))
    if op == "ssub":
        RawTrigger(conditions=cf.Exactly(0), actions=[x.SetNumber(0) for x in rw])


def _into3(dw, pa, pb, op, inline):
    """dw ← a op b. dw 가 a·b 와 겹쳐도 맞게 (제자리·임시 변수)."""
    if _same(dw, pa):
        {"add": _iadd4, "sub": _isub4, "ssub": _isub_sat4}[op](dw, pb, inline=inline)
        return
    if op == "add" and _same(dw, pb):
        _iadd4(dw, pa, inline=inline)
        return
    if _overlap(dw, pa + pb):
        t = _new4()
        _op3(t, pa, pb, op, inline)
        _assign4(dw, t)
        return
    _op3(dw, pa, pb, op, inline)


# =============================================================================================
# 비교 (i64 비교 계획을 칸 넷으로 — 사전식, 부호 없음)
# =============================================================================================


def _res(plan, base, neg, extra=()):
    """base ∧ ¬(neg ∧ extra) → None(거짓) | [](참) | 조건 목록.

    base·neg = 원자 목록(None = 거짓). extra = 이미 만든 조건 목록(부정 부분에 함께 들어감, 빈 목록 = 참).
    """
    extra = list(extra)
    if neg is not None:
        neg = _simplify(neg)
    if base is not None and neg is not None and not extra and len(neg) == 1:
        n = _negate(neg[0])
        if n is not None:
            base, neg = base + [n], None
    if base is not None:
        base = _simplify(base)
    if base is None:
        return None
    if neg == [] and not extra:
        return None
    conds = _conds(plan, base)
    if neg is None:
        return conds
    k, kepd = flag_cond(plan, 1)
    plan.trig(_conds(plan, neg) + extra, [SetMemoryEPD(kepd, SetTo, 0)])
    return conds + [k]


def _lex(plan, xs, ys, strict):
    """xs > ys (strict) 또는 xs ≥ ys. xs·ys = 위 칸부터의 칸 목록. → None | [] | 조건 목록."""
    if len(xs) == 1:
        return _res(plan, _gt(xs[0], ys[0]) if strict else _cmp(xs[0], GE, ys[0]), None)
    base = _cmp(xs[0], GE, ys[0])
    if base is None:
        return None
    top_le = _cmp(xs[0], LE, ys[0])
    if top_le is None:  # 맨 위 칸이 반드시 크다
        return _res(plan, base, None)
    if len(xs) == 2:
        inner = _cmp(ys[1], GE, xs[1]) if strict else _gt(ys[1], xs[1])
        return _res(plan, base, _and(top_le, inner))
    if top_le == [] and base == []:  # 맨 위 칸이 같다고 알려짐 → 나머지만
        return _lex(plan, xs[1:], ys[1:], strict)
    inner = _lex(plan, ys[1:], xs[1:], not strict)
    if inner is None:
        return _res(plan, base, None)
    return _res(plan, base, top_le, inner)


_MIRROR = {"le": "ge", "lt": "gt"}
_REFLEXIVE = {"ge", "le", "eq"}
_PYOP = {
    "ge": lambda x, y: x >= y,
    "gt": lambda x, y: x > y,
    "eq": lambda x, y: x == y,
    "ne": lambda x, y: x != y,
}


def _cmp_plan(plan, op, pa, pb):
    if op == "eq":
        return _res(plan, _and(*[_cmp(pa[k], EQ, pb[k]) for k in range(4)]), None)
    if op == "ne":
        return _res(plan, [], _and(*[_cmp(pa[k], EQ, pb[k]) for k in range(4)]))
    return _lex(plan, pa[::-1], pb[::-1], op == "gt")


def _compare(op, a, b, fname):
    if op in _MIRROR:
        op, a, b = _MIRROR[op], b, a
    pa = _words(a, fname, "a")
    pb = _words(b, fname, "b")
    return _compare_words(op, pa, pb)


def _compare_words(op, pa, pb):
    if _same(pa, pb) and not _all_const(pa):
        return Always() if op in _REFLEXIVE else Never()
    ka, kb = _const4(pa), _const4(pb)
    if ka is not None and kb is not None:
        return Always() if _PYOP[op](ka, kb) else Never()
    plan = Plan()
    conds = _cmp_plan(plan, op, pa, pb)
    plan.emit()
    if conds is None:
        return Never()
    if not conds:
        return Always()
    return conds[0] if len(conds) == 1 else conds


def _cmpdoc(op, sym):
    return (
        "a %s b (부호 없는 128비트, 사전식 — 위 칸 먼저). 모든 경계에서 정확하다.\n\n"
        "    인자: a, b — Int128·Int64·정수 상수(−2^127 ~ 2^128−1)·10진 문자열·32비트 변수(0 확장)\n"
        "    반환: 새 Condition 또는 조건 목록(AND). 상수끼리·같은 객체끼리는 Always()/Never().\n"
        "          앞 계산은 부르는 순간 낸다 → 돌려받은 조건은 꼭 한 번 트리거에 놓는다. 루프 조건은 조건 자리에서 부른다.\n"
        "    비용: 변수끼리 = 호출 5 / 실행 12 (eq 2 / 6, ne 3 / 7), 상수 = 호출 1~5 / 실행 1~5 (2026-09-17, docs/COSTS.md \"i128 (WP20)\")\n"
        "    CP: 바꾸지 않음\n"
        "    로컬: 공유 안전\n"
        "    epScript: `if (i128.%s(a, b)) { … }` · `return i128.%s(a, b) ? 1 : 0;` (Int128 끼리는 `a %s b` 도 같다)\n"
        "    출처: DPS math128.lua `Compare_128`/`f_LCmp128`, DPS_Enhance eudplib-port a7aad90 eud/ctrig/tlib.py:204 비교 계획\n"
    ) % (sym, op, op, sym)


def f_ge(a, b):
    return _compare("ge", a, b, "i128.ge")


def f_le(a, b):
    return _compare("le", a, b, "i128.le")


def f_gt(a, b):
    return _compare("gt", a, b, "i128.gt")


def f_lt(a, b):
    return _compare("lt", a, b, "i128.lt")


def f_eq(a, b):
    return _compare("eq", a, b, "i128.eq")


def f_ne(a, b):
    return _compare("ne", a, b, "i128.ne")


for _f, _o, _y in (
    (f_ge, "ge", "≥"),
    (f_le, "le", "≤"),
    (f_gt, "gt", ">"),
    (f_lt, "lt", "<"),
    (f_eq, "eq", "="),
    (f_ne, "ne", "≠"),
):
    _f.__doc__ = _cmpdoc(_o, _y)
del _f, _o, _y

ge = f_ge
le = f_le
gt = f_gt
lt = f_lt
eq = f_eq
ne = f_ne


# =============================================================================================
# 곱셈 — 변수 64×64 → 128 전체 곱 (i64 16비트 쪼개기의 전체 곱 판)
#
# 곱해지는 수 a = (al, ah) 를 16비트 조각 t0·t1(al)·t2·t3(ah) 로, 곱하는 수 b 의 16비트 조각 m = 0..3 의 비트 i 마다
# 조건 트리거 하나가 t_k·2^i 를 누적기 A[k][m] 에 더한다(변수 트리거 사슬). A[k][m] = a_k·b_m < 2^32 라 넘치지 않는다.
# 누적기의 가중치는 2^(16(k+m)): k+m 이 짝수면 칸 (k+m)/2 에 바로, 홀수면 16비트 걸친다.
# 끝: 홀수 무리 합(올림 → H += 2^16) → 16비트로 갈라 H(윗 칸)·L(아랫 칸)에 → 칸마다 올림을 세며 더한다.
#   칸 w = A(짝수 무리 첫째 — 곧 반환 변수 R_w) + 나머지 짝수 무리 + H_w + L_w, 올림 → R_(w+1) += 1
#   (R_(w+1) ≤ 2^32 − 2^17 + 1 이라 작은 올림 몇 개는 넘치지 않는다).
# 올림 판정 `[R_w ≤ V − 1] ∧ [V ≥ 1]` 의 amount(V − 1)는 누적기면 미리 채우고, H·L 이면 비트를 옮길 때 같이 더해 둔다
# (i64 `_mul_tail` 과 같은 방법) — 반환 변수 R 은 원천으로 쓰지 않는다(eudplib 반환 변수 규칙).
# =============================================================================================


def _mulf_emit(t0, t2, bl, bh, R):
    has_h, has_b = t2 is not None, bh is not None
    t1 = EUDVariable()
    t3 = EUDVariable() if has_h else None
    ts = [t0, t1] + ([t2, t3] if has_h else [])
    nm = 4 if has_b else 2
    groups = {}
    for k in range(len(ts) - 1, -1, -1):
        for m in range(nm):
            groups.setdefault(k + m, []).append((k, m))
    A = {}
    for s, members in groups.items():
        for idx, km in enumerate(members):
            A[km] = R[s // 2] if (s % 2 == 0 and idx == 0) else EUDVariable()
    maxs = max(groups)
    H, L = {}, {}  # 칸 → (변수, 판정 조건 — 맨 위 칸은 None)

    def det(w):
        return MemoryEPD(EPD(R[w].getValueAddr()), AtMost, placeholder()) if w < 3 else None

    for s in groups:
        if s % 2:
            H[(s + 1) // 2] = (EUDVariable(), det((s + 1) // 2))
            L[(s - 1) // 2] = (EUDVariable(), det((s - 1) // 2))
    hl = list(H.values()) + list(L.values())
    init = [r.SetNumber(0) for r in R] + [v.SetNumber(0) for v in A.values() if not any(v is r for r in R)]
    init += [t1.SetNumber(0)] + ([t3.SetNumber(0)] if t3 is not None else [])
    init += [v.SetNumber(0) for v, _c in hl]
    init += [SetMemoryEPD(EPD(c) + 2, SetTo, M32) for _v, c in hl if c is not None]
    init += add_modifiers(*ts)
    fr = SelfFrame(init)
    _i64._split16(fr, t0, t1)
    if has_h:
        _i64._split16(fr, t2, t3)
    exit_ = Forward()
    for i in range(16):
        for m in range(nm):
            word = bl if m < 2 else bh
            fr.test([word.AtLeastX(1, 1 << (i + 16 * (m % 2)))], [(t, A[(k, m)]) for k, t in enumerate(ts)])
        if i == 15:
            break
        rest = ((M16 << (i + 1)) & M16) * 0x10001
        dbl = [(t, t) for t in ts]
        nxt = Forward()
        first, acts = var_chain(dbl, nxt)
        if has_b:
            d2 = Forward()
            fr.node([bl.AtLeastX(1, rest)], first, acts, false_next=d2)
            d2 << NextTrigger()
            first2, acts2 = var_chain(dbl, nxt)
            fr.node([bh.AtLeastX(1, rest)], first2, acts2, false_next=exit_)
        else:
            fr.node([bl.AtLeastX(1, rest)], first, acts, false_next=exit_)
        nxt << NextTrigger()
    exit_ << NextTrigger()

    # --- 끝: 누적기 덧셈 판정 amount 채우기 (누적기 = V − 1) ---
    odd_adds = []  # (S, X, 판정 조건, 올림 액션 만들기)
    word_adds = [[] for _ in range(4)]  # 칸 w: (V, 판정 조건 또는 None)
    fills = []
    for s in sorted(groups):
        members = [A[km] for km in groups[s]]
        head, rest_ = members[0], members[1:]
        if s % 2:
            hv, hc = H[(s + 1) // 2]
            for X in rest_:
                c = MemoryEPD(EPD(head.getValueAddr()), AtMost, placeholder())
                fills += [(EPD(c) + 2, SetTo, M32), (EPD(c) + 2, Add, X)]
                odd_adds.append((head, X, c, (hv, None if hc is None else EPD(hc) + 2)))
        else:
            w = s // 2
            for X in rest_:
                c = None
                if w < 3:
                    c = MemoryEPD(EPD(R[w].getValueAddr()), AtMost, placeholder())
                    fills += [(EPD(c) + 2, SetTo, M32), (EPD(c) + 2, Add, X)]
                word_adds[w].append((X, c))
    for w in range(4):
        for d in (H, L):
            if w in d:
                v, c = d[w]
                word_adds[w].append((v, c))
    if fills:
        fills.sort(key=lambda p: 0 if _isconst(p[2]) else 1)
        SeqCompute(fills)

    # --- 홀수 무리 합 (올림 → H += 2^16) ---
    if odd_adds:
        end = Forward()
        prep = []
        dets = []
        for j, (S, X, c, (hv, hamt)) in enumerate(odd_adds):
            d = Forward()
            prep += [X.SetDest(S), X.SetModifier(Add), SetNextPtr(X.GetVTable(), d)]
            nxt = odd_adds[j + 1][1].GetVTable() if j + 1 < len(odd_adds) else end
            acts = [hv.AddNumber(0x10000)] + ([] if hamt is None else [SetMemoryEPD(hamt, Add, 0x10000)])
            dets.append((d, nxt, [c, X.AtLeast(1)], acts))
        RawTrigger(nextptr=odd_adds[0][1].GetVTable(), actions=prep)
        for d, nxt, conds, acts in dets:
            d << RawTrigger(nextptr=nxt, conditions=conds, actions=acts)
        end << NextTrigger()

    # --- 홀수 무리 합을 16비트로 가르기 ---
    for s in sorted(groups):
        if not s % 2:
            continue
        S = A[groups[s][0]]
        hv, hc = H[(s + 1) // 2]
        lv, lc = L[(s - 1) // 2]
        skip = Forward()
        fr.node([S.ExactlyX(0, 0xFFFF0000)], skip)
        for j in range(31, 15, -1):
            v = 1 << (j - 16)
            acts = [hv.AddNumber(v)] + ([] if hc is None else [SetMemoryEPD(EPD(hc) + 2, Add, v)])
            RawTrigger(conditions=S.AtLeastX(1, 1 << j), actions=acts)
        skip << NextTrigger()
        skip = Forward()
        fr.node([S.ExactlyX(0, M16)], skip)
        for j in range(15, -1, -1):
            v = 1 << (j + 16)
            RawTrigger(conditions=S.AtLeastX(1, 1 << j), actions=[lv.AddNumber(v), SetMemoryEPD(EPD(lc) + 2, Add, v)])
        skip << NextTrigger()

    # --- 칸마다 더하기 (올림 → R_(w+1) += 1) ---
    chain = [(w, V, c) for w in range(4) for V, c in word_adds[w]]
    if chain:
        end = Forward()
        prep = []
        dets = []
        for j, (w, V, c) in enumerate(chain):
            nxt = chain[j + 1][1].GetVTable() if j + 1 < len(chain) else end
            if c is None:
                prep += [V.SetDest(R[w]), V.SetModifier(Add), SetNextPtr(V.GetVTable(), nxt)]
                continue
            d = Forward()
            prep += [V.SetDest(R[w]), V.SetModifier(Add), SetNextPtr(V.GetVTable(), d)]
            dets.append((d, nxt, [c, V.AtLeast(1)], [R[w + 1].AddNumber(1)]))
        RawTrigger(nextptr=chain[0][1].GetVTable(), actions=prep)
        for d, nxt, conds, acts in dets:
            d << RawTrigger(nextptr=nxt, conditions=conds, actions=acts)
        end << NextTrigger()
    fr.finish()


@functools.cache
def _mulf_fn(has_b):
    """64×64(has_b) / 64×32 → 128 전체 곱 공유 본문. 반환 (r0, r1, r2, r3)."""
    R = _new4()
    if has_b:

        def i128_mul_6464(al, ah, bl, bh):
            _mulf_emit(al, ah, bl, bh, R)

        f = EUDFunc(i128_mul_6464)
    else:

        def i128_mul_6432(al, ah, bl):
            _mulf_emit(al, ah, bl, None, R)

        f = EUDFunc(i128_mul_6432)
    _compat.predefine_returns(f, list(R))
    return f


def _mul64_into(rw, pa, pb):
    """rw ← a × b (a, b 는 칸 둘 — 64비트, 전체 곱). rw 는 새 변수 넷(a·b 와 겹쳐도 됨 — 공유 함수는 인자를 먼저 복사)."""
    pa, pb = tuple(pa), tuple(pb)
    ka, kb = _i64._const_pair(pa), _i64._const_pair(pb)
    if ka is not None and kb is not None:
        _assign4(rw, _split4(ka * kb))
        return
    if ka is not None:
        pa, pb, kb = pb, pa, ka
    if kb is not None:
        _mulk_into4(rw, pa + (0, 0), kb)
        return
    wa, wb = _width(pa + (0, 0)), _width(pb + (0, 0))
    if wa < wb:
        pa, pb, wa, wb = pb, pa, wb, wa
    if wa <= 1:  # 32×32 → 64 (i64 본문)
        _i64._mul_fn(False, False)(pa[0], pb[0], ret=list(rw[:2]))
        SeqCompute([(rw[2], SetTo, 0), (rw[3], SetTo, 0)])
        return
    if wb <= 1:
        _mulf_fn(False)(pa[0], pa[1], pb[0], ret=list(rw))
        return
    _mulf_fn(True)(pa[0], pa[1], pb[0], pb[1], ret=list(rw))


@functools.cache
def _mulbig_fn(nb):
    """128비트 × (nb 칸) → 128 wrap 공유 본문 (a 는 칸 넷). 하위 64비트 전체 곱 + (a 상위 × b 하위 + a 하위 × b 상위) << 64."""

    def body(a0, a1, a2, a3, *bs):
        b = tuple(bs) + (0,) * (4 - nb)
        P = _new4()
        _mul64_into(P, (a0, a1), b[:2])
        ql, qh = EUDVariable(), EUDVariable()
        if EUDIf()([a2.Exactly(0), a3.Exactly(0)], neg=True):
            _i64._mul_into(ql, qh, (a2, a3), b[:2])
            _i64._iadd(P[2], P[3], ql, qh)
        EUDEndIf()
        if nb == 4:
            if EUDIf()([b[2].Exactly(0), b[3].Exactly(0)], neg=True):
                _i64._mul_into(ql, qh, (a0, a1), b[2:])
                _i64._iadd(P[2], P[3], ql, qh)
            EUDEndIf()
        EUDReturn(*P)

    if nb == 1:

        def i128_mul_big1(a0, a1, a2, a3, b0):
            body(a0, a1, a2, a3, b0)

        return EUDFunc(i128_mul_big1)
    if nb == 2:

        def i128_mul_big2(a0, a1, a2, a3, b0, b1):
            body(a0, a1, a2, a3, b0, b1)

        return EUDFunc(i128_mul_big2)

    def i128_mul_big4(a0, a1, a2, a3, b0, b1, b2, b3):
        body(a0, a1, a2, a3, b0, b1, b2, b3)

    return EUDFunc(i128_mul_big4)


# --- 상수 곱: 비트 누적 (i64 `_mulk_bt_emit` 을 칸 넷으로) ---
# x 의 비트 i 마다 조건 트리거 하나가 T_i = K·2^i mod 2^128 의 칸들을 누적기에 더한다. 칸 w 누적기에 더해지는 횟수 N_w 로
# 나눔 비트 S_w = 32 − ⌈log2 N_w⌉ 를 정해 하위 S_w 비트는 R_w 에, 나머지는 F_w 에 더한다(둘 다 넘치지 않는다).
# 끝에서 F_w·2^(S_w) 를 비트마다 Lx_w(칸 w 의 32비트 안쪽)와 Lx_(w+1)(밖)로 옮기고, R_w += Lx_w(올림 → Lx_(w+1) += 1).
# 판정 amount(Lx_w − 1)는 Lx 에 더할 때 같이 더해 둔다. 맨 위 칸(w = 3)은 wrap 으로 바로 더한다.


def _mulk_emit(xs, K, R):
    nx = len(xs)
    T = [(K << i) & M128 for i in range(32 * nx)]
    N = [sum(1 for t in T if (t >> (32 * w)) & M32) for w in range(4)]
    S = [32 - (n - 1).bit_length() if n > 1 else 32 for n in N[:3]]
    F = [EUDVariable() if S[w] < 32 else None for w in range(3)]
    Lx = [EUDVariable() for _ in range(3)]
    det = [MemoryEPD(EPD(R[w].getValueAddr()), AtMost, placeholder()) for w in range(3)]
    amt = [EPD(c) + 2 for c in det]
    init = [r.SetNumber(0) for r in R] + [f.SetNumber(0) for f in F if f is not None]
    init += [v.SetNumber(0) for v in Lx] + [SetMemoryEPD(a, SetTo, M32) for a in amt]
    fr = SelfFrame(init)
    for j in range(nx - 1, -1, -1):
        for half in (1, 0):
            trigs = []
            for b in range(15, -1, -1):
                t = T[32 * j + 16 * half + b]
                acts = []
                for w in range(4):
                    v = (t >> (32 * w)) & M32
                    if not v:
                        continue
                    if w < 3 and S[w] < 32:
                        lo, hi = v & ((1 << S[w]) - 1), v >> S[w]
                        if lo:
                            acts.append(R[w].AddNumber(lo))
                        if hi:
                            acts.append(F[w].AddNumber(hi))
                    else:
                        acts.append(R[w].AddNumber(v))
                if acts:
                    trigs.append((1 << (16 * half + b), acts))
            if not trigs:
                continue
            skip = Forward()
            fr.node([xs[j].ExactlyX(0, M16 << (16 * half))], skip)
            for bit, acts in trigs:
                RawTrigger(conditions=xs[j].AtLeastX(1, bit), actions=acts)
            skip << NextTrigger()
    for w in range(3):
        if F[w] is not None:
            fmax = N[w] * ((1 << (32 - S[w])) - 1)
            skip = Forward()
            fr.node([F[w].Exactly(0)], skip)
            for jb in range(fmax.bit_length() - 1, -1, -1):
                p = S[w] + jb
                if p < 32:
                    acts = [Lx[w].AddNumber(1 << p), SetMemoryEPD(amt[w], Add, 1 << p)]
                elif w + 1 < 3:
                    v = 1 << (p - 32)
                    acts = [Lx[w + 1].AddNumber(v), SetMemoryEPD(amt[w + 1], Add, v)]
                else:
                    acts = [R[3].AddNumber(1 << (p - 32))]
                RawTrigger(conditions=F[w].AtLeastX(1, 1 << jb), actions=acts)
            skip << NextTrigger()
        skip = Forward()
        fr.node([Lx[w].Exactly(0)], skip)
        SeqCompute([(R[w], Add, Lx[w])])
        carry = [Lx[w + 1].AddNumber(1), SetMemoryEPD(amt[w + 1], Add, 1)] if w + 1 < 3 else [R[3].AddNumber(1)]
        RawTrigger(conditions=det[w], actions=carry)
        skip << NextTrigger()
    fr.finish()


@functools.cache
def _mulk_fn(K, nx):
    """상수 K 곱 공유 본문 (K·x mod 2^128, x 는 칸 nx 개). 반환 (r0..r3)."""
    R = _new4()
    if nx == 1:

        def i128_mulk(x0):
            _mulk_emit((x0,), K, R)

    elif nx == 2:

        def i128_mulk(x0, x1):
            _mulk_emit((x0, x1), K, R)

    else:

        def i128_mulk(x0, x1, x2, x3):
            _mulk_emit((x0, x1, x2, x3), K, R)

    i128_mulk.__name__ = i128_mulk.__qualname__ = "i128_mulk_%d_%d" % (K, nx)
    f = EUDFunc(i128_mulk)
    _compat.predefine_returns(f, list(R))
    return f


def _mulk_into4(rw, pa, K):
    """rw ← a × K mod 2^128 (K 상수, a 는 변수 칸이 있다)."""
    K &= M128
    if K == 0:
        _assign4(rw, (0, 0, 0, 0))
        return
    if K == 1:
        _assign4(rw, pa)
        return
    wa = max(_width(pa), 1)
    nx = 1 if wa == 1 else 2 if wa == 2 else 4
    _mulk_fn(K, nx)(*pa[:nx], ret=list(rw))


def _mul_into4(rw, pa, pb):
    """rw ← a × b mod 2^128. rw 는 변수 넷(a·b 와 겹쳐도 됨 — 공유 함수가 인자를 먼저 복사하거나 새 변수를 거친다)."""
    ka, kb = _const4(pa), _const4(pb)
    if ka is not None and kb is not None:
        _assign4(rw, _split4(ka * kb))
        return
    if ka is not None:
        pa, pb, kb = pb, pa, ka
    if kb is not None:
        _mulk_into4(rw, pa, kb)
        return
    wa, wb = _width(pa), _width(pb)
    if wa < wb:
        pa, pb, wa, wb = pb, pa, wb, wa
    if wa <= 2:
        _mul64_into(rw, pa[:2], pb[:2])
        return
    nb = 1 if wb <= 1 else 2 if wb == 2 else 4
    _mulbig_fn(nb)(*pa, *pb[:nb], ret=list(rw))


# =============================================================================================
# 나눗셈 (부호 없음). 0 나눗셈: 몫 2^128 − 1, 나머지 = 피제수 (i64·eudplib f_div 와 같은 규칙).
# - 32비트 제수 d: i64 64÷64 공유 본문을 위 칸부터 (몫 칸 < 2^32 — 나머지 < d 라서).
# - 64비트 제수 D (≥ 2^32): "나머지 R < D 인 (R·2^32 + x) ÷ D" 한 칸 본문(_d9664)을 위 칸부터. 한 칸 = 32단 복원 나눗셈 —
#   i64 `_udiv_emit` 의 64비트 제수 단(K0~K3, 공유 비교 트리거)에 넘침 비트(OV: 옛 R ≥ 2^63 이면 반드시 뺌)를 더했다.
# - 128비트 제수 D (≥ 2^64): N < D 면 몫 0, D ≥ 2^127 이면 몫 1, 그 밖은 몫 < 2^64 인 64단 복원 나눗셈(_d128) —
#   R = N >> 64 에서 N 의 아래 64비트를 밀어 넣는다. 한 단의 R ≥ D 비교·뺄셈은 빌림 조합 8가지 조건 트리거(서로 배타)가
#   맞는 뺄셈 사슬(칸마다 −D_k 또는 −D_k − 1 을 더하는 변수 트리거)로 보낸다.
# - 상수 제수 K < 2^32: i64(이식판 a41d2ed `_cdiv`)의 n 칸 상수 나눗셈을 칸 넷으로. 그 이상 상수는 변수 제수 본문.
# =============================================================================================


def _d9664_emit(wl, wh, x, dl, dh, Q, RL, RH):
    """(wh:wl)·2^32 + x ÷ D(dh:dl, dh ≥ 1) → Q(< 2^32), 나머지 (RH:RL). 전제 (wh:wl) < D."""
    ndl, ndh, ndh1 = EUDVariable(), EUDVariable(), EUDVariable()
    whv, wlv, av, bv, cv = (v.GetVTable() for v in (wh, wl, ndl, ndh, ndh1))
    K0, K1, K2, K3, TC, OV1, OV2 = (Forward() for _ in range(7))

    def cnd(v, c):
        return MemoryEPD(EPD(v.getValueAddr()), c, placeholder())

    k0c = cnd(wh, AtMost)  # wh ≤ dh − 1
    k1h = cnd(wh, AtLeast)  # wh ≥ dh + 1
    k1g = MemoryEPD(EPD(k1h) + 2, AtLeast, 1)  # dh + 1 ≠ 0
    k1l = cnd(wl, AtLeast)  # wl ≥ dl
    k2h = cnd(wh, AtLeast)
    k2g = MemoryEPD(EPD(k2h) + 2, AtLeast, 1)
    k2l = cnd(wl, AtMost)  # wl ≤ dl − 1
    k3l = cnd(wl, AtLeast)
    o1l = cnd(wl, AtLeast)
    k0act = SetNextPtr(K0, placeholder())
    qs = [SetMemoryEPD(EPD(Q.getValueAddr()), Add, placeholder()) for _ in range(5)]

    def amt(c):
        return EPD(c) + 2

    init = [Q.SetNumber(0), wh.SetDest(wh), wl.SetDest(wl), ndl.SetDest(wl), ndh.SetDest(wh), ndh1.SetDest(wh)]
    init += [*add_modifiers(wh, wl, ndl, ndh, ndh1), SetNextPtr(whv, TC)]
    fr = SelfFrame(init)
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
            (amt(o1l), SetTo, dl),
            (ndh1, Subtract, dh),
            (ndl, Subtract, dl),
            (ndh, Subtract, dh),
        ]
    )
    SeqCompute([(ndh, Add, 1), (ndl, Add, 1)])
    STEP = [Forward() for _ in range(32)]
    FIN = Forward()
    SetNextTrigger(STEP[0])
    for idx in range(32):
        k = 31 - idx
        back = STEP[idx + 1] if idx < 31 else FIN
        s0, setup = Forward(), Forward()
        STEP[idx] << RawTrigger(nextptr=setup, conditions=wh.AtLeast(SIGN), actions=SetNextPtr(s0, OV1))
        setup << RawTrigger(
            nextptr=whv,
            actions=[
                SetNextPtr(wlv, s0),
                SetMemoryEPD(EPD(k0act) + 5, SetTo, back),
                SetNextPtr(K0, K1),
                SetNextPtr(K1, K2),
                SetNextPtr(K2, K3),
                SetNextPtr(K3, back),
                SetNextPtr(OV1, OV2),
                SetNextPtr(bv, back),
                SetNextPtr(cv, back),
                *[SetMemoryEPD(EPD(q) + 5, SetTo, 1 << k) for q in qs],
            ],
        )
        s0 << RawTrigger(nextptr=K0, conditions=x.AtLeastX(1, 1 << k), actions=wl.AddNumber(1))
        fr.resets.append(SetNextPtr(s0, K0))
    FIN << NextTrigger()
    SeqCompute([(RL, SetTo, wl), (RH, SetTo, wh)])
    SetNextTrigger(fr.end)
    TC << RawTrigger(nextptr=wlv, conditions=wl.AtLeastX(1, SIGN), actions=wh.AddNumber(1))
    K0 << RawTrigger(nextptr=K1, conditions=k0c, actions=k0act)
    K1 << RawTrigger(nextptr=K2, conditions=[k1h, k1g, k1l], actions=[qs[0], SetNextPtr(K1, av), SetNextPtr(av, bv)])
    K2 << RawTrigger(nextptr=K3, conditions=[k2h, k2g, k2l], actions=[qs[1], SetNextPtr(K2, av), SetNextPtr(av, cv)])
    K3 << RawTrigger(nextptr=fr.end, conditions=k3l, actions=[qs[2], SetNextPtr(K3, av), SetNextPtr(av, bv)])
    OV1 << RawTrigger(nextptr=OV2, conditions=o1l, actions=[qs[3], SetNextPtr(OV1, av), SetNextPtr(av, bv)])
    OV2 << RawTrigger(nextptr=av, actions=[qs[4], SetNextPtr(av, cv)])
    fr.finish()


@functools.cache
def _d9664_fn():
    """(rl, rh, x, dl, dh) → (q, rl', rh') 공유 본문 (전제 R < D, dh ≥ 1)."""
    rets = _new4()[:3]

    def i128_div9664(wl, wh, x, dl, dh):
        _d9664_emit(wl, wh, x, dl, dh, *rets)

    f = EUDFunc(i128_div9664)
    _compat.predefine_returns(f, list(rets))
    return f


def _d128_emit(n, d, Q0, Q1, R):
    """N ÷ D, 2^64 ≤ D < 2^127, N ≥ D → 몫 (Q1:Q0) < 2^64, 나머지 R(칸 넷). n·d = 인자 변수 넷씩.

    R = N >> 64 (< 2^64 ≤ D) 에서 N 의 아래 64비트를 밀어 넣는 64단. 2R + 1 < 2D < 2^128 이라 넘치지 않는다.
    한 단 = 준비 → R 두 배(칸 넷 변수 트리거 + 올림 셋) → S0([비트] r0 += 1) → K0a/K0b(R 윗 칸이 D 보다 작으면 다음 단)
    → P(b1,b2,b3) 8개(R − D 의 빌림 조합 — 참인 것은 하나뿐, 참이면 몫 비트를 더하고 뺄셈 사슬로) → 다음 단.
    """
    r0, r1, r2, r3 = R
    nd = [EUDVariable() for _ in range(4)]  # −d_k
    nd1 = [EUDVariable() for _ in range(4)]  # −d_k − 1 (칸 1~3)
    rv = [r.GetVTable() for r in R]
    ndv = [v.GetVTable() for v in nd]
    nd1v = [v.GetVTable() for v in nd1]
    T1, T2, T3, K0a, K0b = (Forward() for _ in range(5))
    P = [Forward() for _ in range(8)]
    fills_c, fills_v = [], []

    def filled(v, c, src, add):
        cond = MemoryEPD(EPD(v.getValueAddr()), c, placeholder())
        a = EPD(cond) + 2
        if add:
            fills_c.append((a, SetTo, add & M32))
            fills_v.append((a, Add, src))
        else:
            fills_v.append((a, SetTo, src))
        return cond

    # K0a: [r3 ≤ d3 − 1] ∧ [d3 ≥ 1],  K0b: [d3 = 0][r3 = 0][r2 ≤ d2 − 1] (D ≥ 2^64 이라 d3 = 0 이면 d2 ≥ 1)
    k0a = [filled(r3, AtMost, d[3], M32), d[3].AtLeast(1)]
    k0b = [d[3].Exactly(0), r3.Exactly(0), filled(r2, AtMost, d[2], M32)]
    k0acts = [SetNextPtr(K0a, placeholder()), SetNextPtr(K0b, placeholder())]
    qact = [SetMemoryEPD(EPD(Q1.getValueAddr()), Add, placeholder()) for _ in range(8)]
    pats = []
    for bits in range(8):
        b = [0, bits & 1, (bits >> 1) & 1, (bits >> 2) & 1, 0]  # b[k] = 칸 k 로 들어오는 빌림, b[4] = 0 (끝에 빌림 없음)
        conds = []
        for k in range(4):
            bin_, bout = b[k], b[k + 1]
            if not bout:  # r_k ≥ d_k + b_in
                if bin_:
                    c = filled(R[k], AtLeast, d[k], 1)
                    conds += [c, MemoryEPD(EPD(c) + 2, AtLeast, 1)]
                else:
                    conds.append(filled(R[k], AtLeast, d[k], 0))
            else:  # r_k ≤ d_k + b_in − 1
                if bin_:
                    conds.append(filled(R[k], AtMost, d[k], 0))
                else:
                    c = filled(R[k], AtMost, d[k], M32)
                    conds += [c, MemoryEPD(EPD(c) + 2, AtMost, M32 - 1)]
        srcs = [ndv[0]] + [nd1v[k] if b[k] else ndv[k] for k in (1, 2, 3)]
        acts = [qact[bits], SetNextPtr(P[bits], srcs[0])] + [SetNextPtr(srcs[k], srcs[k + 1]) for k in range(3)]
        pats.append((conds, acts))
    init = [Q0.SetNumber(0), Q1.SetNumber(0)]
    init += [r.SetDest(r) for r in R] + [nd[0].SetDest(r0)] + [nd[k].SetDest(R[k]) for k in (1, 2, 3)]
    init += [nd1[k].SetDest(R[k]) for k in (1, 2, 3)]
    init += add_modifiers(*R, *nd, *nd1[1:])
    init += [SetNextPtr(rv[3], T3), SetNextPtr(rv[2], T2), SetNextPtr(rv[1], T1)]
    fr = SelfFrame(init)
    negs_c = [(v, SetTo, M32) for v in nd + nd1[1:]]
    negs_v = [(nd[k], Subtract, d[k]) for k in range(4)] + [(nd1[k], Subtract, d[k]) for k in (1, 2, 3)]
    SeqCompute(fills_c + negs_c + [(r2, SetTo, 0), (r3, SetTo, 0), (r0, SetTo, n[2]), (r1, SetTo, n[3])] + fills_v + negs_v)
    SeqCompute([(v, Add, 1) for v in nd])
    STEP = [Forward() for _ in range(64)]
    FIN = Forward()
    SetNextTrigger(STEP[0])
    for idx in range(64):
        k = 31 - idx % 32
        src = n[1] if idx < 32 else n[0]
        Q = Q1 if idx < 32 else Q0
        back = STEP[idx + 1] if idx < 63 else FIN
        s0 = Forward()
        acts = [
            SetNextPtr(rv[0], s0),
            *[SetMemoryEPD(EPD(a) + 5, SetTo, back) for a in k0acts],
            SetNextPtr(K0a, K0b),
            SetNextPtr(K0b, P[0]),
            *[SetNextPtr(P[j], P[j + 1] if j < 7 else back) for j in range(8)],
            SetNextPtr(nd1v[3], back),
            SetNextPtr(ndv[3], back),
        ]
        if idx in (0, 32):
            acts += [SetMemoryEPD(EPD(q) + 4, SetTo, EPD(Q.getValueAddr())) for q in qact]
        acts += [SetMemoryEPD(EPD(q) + 5, SetTo, 1 << k) for q in qact]
        STEP[idx] << RawTrigger(nextptr=rv[3], actions=acts)
        s0 << RawTrigger(nextptr=K0a, conditions=src.AtLeastX(1, 1 << k), actions=r0.AddNumber(1))
    FIN << NextTrigger()
    SetNextTrigger(fr.end)
    T3 << RawTrigger(nextptr=rv[2], conditions=r2.AtLeastX(1, SIGN), actions=r3.AddNumber(1))
    T2 << RawTrigger(nextptr=rv[1], conditions=r1.AtLeastX(1, SIGN), actions=r2.AddNumber(1))
    T1 << RawTrigger(nextptr=rv[0], conditions=r0.AtLeastX(1, SIGN), actions=r1.AddNumber(1))
    K0a << RawTrigger(nextptr=K0b, conditions=k0a, actions=k0acts[0])
    K0b << RawTrigger(nextptr=P[0], conditions=k0b, actions=k0acts[1])
    for j, (conds, acts) in enumerate(pats):
        P[j] << RawTrigger(nextptr=P[j + 1] if j < 7 else fr.end, conditions=conds, actions=acts)
    fr.finish()


@functools.cache
def _d128_fn():
    """(n0..n3, d0..d3) → (q0, q1, r0..r3) 공유 본문 (전제 2^64 ≤ D < 2^127, N ≥ D).

    나머지 변수는 두 배 단계에서 원천으로도 쓰이므로 반환 변수를 미리 정하지 않는다(EUDReturn).
    """

    def i128_div128(n0, n1, n2, n3, d0, d1, d2, d3):
        q0, q1 = EUDVariable(), EUDVariable()
        R = _new4()
        _d128_emit((n0, n1, n2, n3), (d0, d1, d2, d3), q0, q1, R)
        EUDReturn(q0, q1, *R)

    return EUDFunc(i128_div128)


def _div32_part(n, d, q, r):
    """32비트 제수 d(≥ 1): i64 본문을 위 칸부터."""
    f = _i64._udiv_fn()
    j1, j2, j3 = EUDVariable(), EUDVariable(), EUDVariable()
    if EUDIf()([n[3].Exactly(0), n[2].Exactly(0)]):
        f(n[0], n[1], d, 0, ret=[q[0], q[1], r[0], j1])
        SeqCompute([(q[2], SetTo, 0), (q[3], SetTo, 0)])
    if EUDElse()():
        rt = EUDVariable()
        f(n[2], n[3], d, 0, ret=[q[2], q[3], rt, j1])
        f(n[1], rt, d, 0, ret=[q[1], j2, rt, j3])
        f(n[0], rt, d, 0, ret=[q[0], j2, r[0], j3])
    EUDEndIf()
    SeqCompute([(r[1], SetTo, 0), (r[2], SetTo, 0), (r[3], SetTo, 0)])


def _div64_part(n, d0, d1, q, r):
    """64비트 제수 (d1 ≥ 1): 96÷64 한 칸 본문을 위 칸부터."""
    g = _d9664_fn()
    rl, rh = EUDVariable(), EUDVariable()
    if EUDIf()(n[3].AtLeast(1)):
        g(n[3], 0, n[2], d0, d1, ret=[q[2], rl, rh])
        g(rl, rh, n[1], d0, d1, ret=[q[1], rl, rh])
        g(rl, rh, n[0], d0, d1, ret=[q[0], rl, rh])
        SeqCompute([(q[3], SetTo, 0)])
    if EUDElseIf()(n[2].AtLeast(1)):
        g(n[2], 0, n[1], d0, d1, ret=[q[1], rl, rh])
        g(rl, rh, n[0], d0, d1, ret=[q[0], rl, rh])
        SeqCompute([(q[2], SetTo, 0), (q[3], SetTo, 0)])
    if EUDElse()():
        g(n[1], 0, n[0], d0, d1, ret=[q[0], rl, rh])
        SeqCompute([(q[1], SetTo, 0), (q[2], SetTo, 0), (q[3], SetTo, 0)])
    EUDEndIf()
    SeqCompute([(r[0], SetTo, rl), (r[1], SetTo, rh), (r[2], SetTo, 0), (r[3], SetTo, 0)])


def _udiv_body(n, d, nd):
    q, r = _new4(), _new4()

    def zero_rule():
        SeqCompute([(v, SetTo, M32) for v in q] + [(r[k], SetTo, n[k]) for k in range(4)])

    if nd == 1:
        if EUDIf()(d[0].Exactly(0)):
            zero_rule()
        if EUDElse()():
            _div32_part(n, d[0], q, r)
        EUDEndIf()
        EUDReturn(*q, *r)
        return

    def low():
        return [d[3].Exactly(0), d[2].Exactly(0)] if nd == 4 else []

    if EUDIf()(low() + [d[1].Exactly(0), d[0].Exactly(0)]):
        zero_rule()
    if EUDElseIf()(low() + [d[1].Exactly(0)]):
        _div32_part(n, d[0], q, r)
    if nd == 4:
        if EUDElseIf()(low()):
            _div64_part(n, d[0], d[1], q, r)
        if EUDElseIf()(_compare_words("gt", d, n)):
            SeqCompute([(v, SetTo, 0) for v in q] + [(r[k], SetTo, n[k]) for k in range(4)])
        if EUDElseIf()(d[3].AtLeast(SIGN)):  # D ≥ 2^127, N ≥ D → 몫 1, 나머지 N − D
            SeqCompute([(q[0], SetTo, 1), (q[1], SetTo, 0), (q[2], SetTo, 0), (q[3], SetTo, 0)])
            _op3(r, n, d, "sub", True)
        if EUDElse()():
            _d128_fn()(*n, *d, ret=[q[0], q[1], *r])
            SeqCompute([(q[2], SetTo, 0), (q[3], SetTo, 0)])
    else:
        if EUDElse()():
            _div64_part(n, d[0], d[1], q, r)
    EUDEndIf()
    EUDReturn(*q, *r)


@functools.cache
def _udiv_fn(nd):
    """부호 없는 128비트 몫·나머지 공유 본문 (피제수 칸 넷, 제수 칸 nd 개 = 1 | 2 | 4) → (q0..q3, r0..r3)."""
    if nd == 1:

        def i128_udiv1(n0, n1, n2, n3, d0):
            _udiv_body((n0, n1, n2, n3), (d0,), 1)

        return EUDFunc(i128_udiv1)
    if nd == 2:

        def i128_udiv2(n0, n1, n2, n3, d0, d1):
            _udiv_body((n0, n1, n2, n3), (d0, d1), 2)

        return EUDFunc(i128_udiv2)

    def i128_udiv4(n0, n1, n2, n3, d0, d1, d2, d3):
        _udiv_body((n0, n1, n2, n3), (d0, d1, d2, d3), 4)

    return EUDFunc(i128_udiv4)


@functools.cache
def _cdiv_fn(K):
    """상수 K (2 ≤ K < 2^32) 로 나누는 공유 본문 (x0..x3) → (q0..q3, r0..r3).

    i64 의 상수 제수 본문(`i64._cdiv_fn(K, "qr")` — 이식판 a41d2ed `_cdiv`, 64비트 값 ÷ K)을 위 칸부터 부른다:
    (x3:x2) ÷ K → 몫 위 두 칸, 나머지 r < K → (r:x1) ÷ K → 몫 칸 1 (< 2^32) → (r:x0) ÷ K → 몫 칸 0, 나머지.
    칸 넷을 한 번에 나누는 본문(`_cdiv_emit` n = 4, 상수마다 약 84KB)보다 한 번 페이로드가 절반 이하이고(약 37KB),
    같은 상수로 64비트 값을 나누는 i64 코드와 본문을 같이 쓴다. 위 두 칸이 0 이면 한 번만 부른다.
    """
    q = _new4()
    rr, j1, j2 = EUDVariable(), EUDVariable(), EUDVariable()

    def i128_cdiv(x0, x1, x2, x3):
        f = _i64._cdiv_fn(K, "qr")
        if EUDIf()([x3.Exactly(0), x2.Exactly(0)]):
            f(x0, x1, ret=[q[0], q[1], rr, j1])
            SeqCompute([(q[2], SetTo, 0), (q[3], SetTo, 0)])
        if EUDElse()():
            f(x2, x3, ret=[q[2], q[3], rr, j1])
            f(x1, rr, ret=[q[1], j1, rr, j2])
            f(x0, rr, ret=[q[0], j1, rr, j2])
        EUDEndIf()
        EUDReturn(*q, rr, 0, 0, 0)

    i128_cdiv.__name__ = i128_cdiv.__qualname__ = "i128_cdiv_%d" % K
    return EUDFunc(i128_cdiv)


_junk = []


def _junk8():
    while len(_junk) < 8:
        _junk.append(EUDVariable())
    return _junk[:8]


@_compat.register_build_reset
def _reset_junk():
    del _junk[:]


def _divmod_into4(q, r, pa, pb):
    """q ← a // b, r ← a % b (부호 없음). q·r 는 변수 넷 또는 None(버림). a·b 와 겹쳐도 된다."""
    ka, kb = _const4(pa), _const4(pb)
    if ka is not None and kb is not None:
        qq, rr = (ka // kb, ka % kb) if kb else (M128, ka)
        if q is not None and r is not None and _overlap(q, pa):
            t = _new4()
            _assign4(t, _split4(qq))
            _assign4(r, _split4(rr))
            _assign4(q, t)
            return
        if q is not None:
            _assign4(q, _split4(qq))
        if r is not None:
            _assign4(r, _split4(rr))
        return
    junk = _junk8()
    rets = (list(q) if q is not None else junk[:4]) + (list(r) if r is not None else junk[4:])
    if kb is not None:
        if kb == 0 or kb == 1:
            qv, rv = (_split4(M128), pa) if kb == 0 else (pa, (0, 0, 0, 0))
            if q is not None and r is not None and _overlap(q, rv):
                t = _new4()
                _assign4(t, rv)
                rv = t
            if q is not None:
                _assign4(q, qv)
            if r is not None:
                _assign4(r, rv)
            return
        if kb <= M32:
            _cdiv_fn(kb)(*pa, ret=rets)
            return
        nd = 2 if kb <= M64 else 4
        _udiv_fn(nd)(*pa, *_split4(kb)[:nd], ret=rets)
        return
    wb = _width(pb)
    nd = 1 if wb <= 1 else 2 if wb == 2 else 4
    _udiv_fn(nd)(*pa, *pb[:nd], ret=rets)


# =============================================================================================
# 10진 출력: 윗 20자리(10^39 ~ 10^20 자리)는 128비트 복원 뺄셈, 아래 20자리는 i64 10진 본문
# =============================================================================================


def _ksub_emit(words, c, n, extra):
    """값(words 의 아래 n 칸) ≥ c 이면 값 −= c 하고 extra() 액션. 빌림 조합마다 조건 트리거 하나(서로 배타).

    전제: 값 < 2c (한 번 빼면 c 보다 작아져 다른 조합은 거짓이다). SC Subtract 는 조건이 "칸 ≥ 빼는 값" 을 보장한
    곳에만 쓴다(3.5-7), 빌림 칸은 wrap 더하기.
    """
    cw = _split4(c)
    pats = []  # 조합마다 [(칸, 없음 = 빌림 없음 t | 빌림 t)] — 조건·액션 객체는 트리거마다 새로 만든다

    def rec(k, b, spec):
        t = cw[k] + b
        if k == n - 1:
            if t <= M32:
                pats.append(spec + [(k, False, t)])
            return
        if t <= M32:
            rec(k + 1, 0, spec + [(k, False, t)])
        if t >= 1:
            rec(k + 1, 1, spec + [(k, True, t)])

    rec(0, 0, [])
    for spec in pats:
        conds, acts = [], []
        for k, borrow, t in spec:
            if not borrow:
                if t:
                    conds.append(words[k].AtLeast(t))
                    acts.append(words[k].SubtractNumber(t))
            elif not t >> 32:  # t = 2^32 이면 늘 빌리고 더할 것도 없다
                conds.append(words[k].AtMost(t - 1))
                acts.append(words[k].AddNumber((-t) & M32))
        RawTrigger(conditions=conds, actions=acts + extra())


def _dec_steps():
    """(자리 i, 비트 b, c = b·10^i, 칸 수 n) — 10^38 ~ 10^19 자리. n = 2c − 1 을 담는 칸 수 (값 < 2c 불변식)."""
    out = []
    for i in range(38, 18, -1):
        for b in (8, 4, 2, 1):
            c = b * 10**i
            if c > M128:
                continue
            out.append((i, b, c, min(4, ((2 * c - 1).bit_length() + 31) // 32)))
    return out


_DECH_OUT = [EUDVariable() for _ in range(5)]
_DECH_LO = EUDVariable()
_DECH_HI = EUDVariable()
_DECH_LEAD = EUDVariable()
_DECH_D19 = EUDVariable()


@EUDFunc
def _dec128_hi(a0, a1, a2, a3):
    """(a0..a3) → 윗 20자리 ASCII(칸 5개 = 10^39 ~ 10^20 자리, 앞은 '0'), 남은 값 (lo, hi) < 10^19,
    윗 자리의 앞 '0' 수 lead, 10^19 자리 숫자 d19.

    값 < 2^64 면 윗 단을 건너뛰고 lead = 21(표시 — 부르는 쪽이 20 + 아래 자리 앞 '0' 수로 바꾼다), d19 = 0.
    그 밖은 lead = 1~20 (20 = 윗 20자리가 모두 0 — 그때 값 ≥ 2^64 라 d19 ≥ 1 이다).
    """
    out, lo, hi, lead, d19 = _DECH_OUT, _DECH_LO, _DECH_HI, _DECH_LEAD, _DECH_D19
    RawTrigger(actions=[w.SetNumber(0x30303030) for w in out] + [lead.SetNumber(0), d19.SetNumber(0)])
    SeqCompute([(lo, SetTo, a0), (hi, SetTo, a1)])
    words = [lo, hi, a2, a3]
    steps = _dec_steps()
    labels = [Forward() for _ in steps]
    done = Forward()
    e2 = next(j for j, st in enumerate(steps) if st[2] < 1 << 96)
    EUDJumpIf(a3.AtLeast(1), labels[0])
    EUDJumpIf(a2.AtLeast(1), labels[e2])
    RawTrigger(nextptr=done, actions=lead.SetNumber(21))
    for idx, (i, b, c, n) in enumerate(steps):
        labels[idx] << NextTrigger()
        if i == 19:  # 10^19 자리는 아래 칸(i64 본문이 쓰는 칸)에 있다 → 따로 돌려준다
            _ksub_emit(words, c, n, lambda b=b: [d19.AddNumber(b)])
            continue
        pos = 39 - i
        word, sh = out[pos // 4], 8 * (pos % 4)
        _ksub_emit(words, c, n, lambda word=word, b=b, sh=sh: [word.AddNumber(b << sh)])
    for j in range(20):
        word, sh = out[j // 4], 8 * (j % 4)
        RawTrigger(conditions=[lead.Exactly(j), word.ExactlyX(0x30 << sh, 0xFF << sh)], actions=lead.AddNumber(1))
    done << NextTrigger()


_compat.predefine_returns(_dec128_hi, _DECH_OUT + [_DECH_LO, _DECH_HI, _DECH_LEAD, _DECH_D19])


def _dec_to(dst, pa, lead):
    """dst(상수 EPD 또는 변수 10개)에 40자리 10진 ASCII 를 쓰고 lead(앞자리 '0' 수 1~39)를 채운다."""
    lo, hi, ll = EUDVariable(), EUDVariable(), EUDVariable()
    if _width(pa) <= 2:  # 64비트 이하: 윗 20자리는 '0'
        SeqCompute([(e, SetTo, 0x30303030) for e in dst[:5]])
        _i64._lidec_body(pa[0], pa[1], ret=list(dst[5:]) + [ll])
        SeqCompute([(lead, SetTo, 20), (lead, Add, ll)])
        return
    d19, w5 = EUDVariable(), EUDVariable()
    _dec128_hi(*pa, ret=list(dst[:5]) + [lo, hi, lead, d19])
    _i64._lidec_body(lo, hi, ret=[w5] + list(dst[6:]) + [ll])
    SeqCompute([(dst[5], SetTo, w5), (dst[5], Add, d19)])  # 10^19 자리 (w5 의 첫 바이트는 '0')
    if EUDIf()(lead.Exactly(21)):
        SeqCompute([(lead, Add, M32), (lead, Add, ll)])
    EUDEndIf()


def f_lidec_to(dst_epd, x, *, lead=None):
    """128비트 값 x 를 40자리 10진 ASCII(앞을 '0' 으로 채움 — 첫 바이트는 늘 '0')로 dst_epd 부터 10칸(40바이트)에 쓴다.

    numfmt 가 128비트 서식(DPS `SetNumX128` 한글 단위 등)을 만들 때 쓰는 경계다. 앞자리 수 lead(1~39)를 돌려준다 →
    숫자 시작 = dst + lead 바이트. 41번째 바이트 이후는 건드리지 않는다(NUL 은 부르는 쪽이 둔다).
    인자: dst_epd(상수 EPD — 칸 0~9 에 결과 변수가 바로 쓴다. 변수면 f_dwwrite_epd 10번), x(128비트 피연산자),
          lead(선택: 결과를 받을 EUDVariable)
    반환: EUDVariable (lead)
    비용: 윗 자리 본문 372(1벌) + i64 10진 본문 137(i64 와 공유) / 호출 6 (64비트 이하 3) / 실행 175~535
          (값 < 2^64 약 150~180) (2026-09-17, docs/COSTS.md "i128 (WP20)")
    CP: 바꾸지 않음 (변수 dst 는 f_dwwrite_epd 가 잠깐 옮기고 되돌림)
    로컬: 공유 안전 (버퍼가 로컬 전용이면 로컬 블록 안에서)
    epScript: `const n = i128.lidec_to(EPD(buf), x);`
    출처: eudext.i64.lidec_to(DPS_Enhance eudplib-port a7aad90 text.py:381 `_lidec_ops` 를 다시 짠 것)를 128비트로
    """
    if lead is None:
        lead = EUDVariable()
    elif not _isvar(unProxy(lead)):
        fail("i128.lidec_to: lead 는 EUDVariable 이어야 합니다 (%r)", lead)
    pa = _words(x, "i128.lidec_to")
    dst = unProxy(dst_epd)
    if _compat.is_const(dst) and not _isvar(dst):
        _dec_to([dst + k for k in range(10)], pa, lead)
        return lead
    words = [EUDVariable() for _ in range(10)]
    _dec_to(words, pa, lead)
    for k, wv in enumerate(words):
        f_dwwrite_epd(dst + k, wv)
    return lead


lidec_to = f_lidec_to


def f_fmt(x):
    """Int128(또는 128비트 값)의 10진 문자열(최대 39자리)을 이 호출 자리의 44바이트 버퍼에 쓰고 `ptr2s` 를 돌려준다.

    eudplib 인쇄 함수(`f_dbstr_print`, `f_sprintf`, `f_eprintln`, `StringBuffer.printf`, `printAll`)가 그대로 받는다.
    한 print 에 `fmt()` 가 여러 개여도 버퍼가 따로라 맞다. 상수는 컴파일 시점에 문자열로 바꿔 돌려준다(트리거 0).
    인자: x(Int128·Int64·상수·문자열·32비트 변수)
    반환: ptr2s(버퍼 + 앞자리 수) 또는 str(상수)
    비용: 호출 7 (64비트 이하 4) / 실행 176~536, 버퍼 44B. 본문은 `lidec_to` 와 같음 (2026-09-17, docs/COSTS.md "i128 (WP20)")
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `printAll("DPS {}", dps.fmt());` · `printAll("{}", i128.fmt(x));`
    출처: DESIGN 3.2-7, DPS converter.lua `SetNumX128`(단위 표기는 numfmt 몫), eudplib 0.81 `string/eudprint.py` fmt 훅
    """
    pa = _words(x, "i128.fmt")
    if _all_const(pa):
        return str(_join4(pa))
    buf = Db(44)
    e = EPD(buf)
    p = EUDVariable()
    _dec_to([e + k for k in range(10)], pa, p)
    RawTrigger(actions=p.AddNumber(buf))
    return ptr2s(p)


fmt = f_fmt


# =============================================================================================
# 32·64비트로 내리기
# =============================================================================================


def _to64_into(dl, dh, pa, saturate):
    k = _const4(pa)
    if k is not None:
        v = min(k, M64) if saturate else k & M64
        SeqCompute([(dl, SetTo, v & M32), (dh, SetTo, v >> 32)])
        return
    _i64._assign(dl, dh, pa[0], pa[1])
    if not saturate:
        return
    for h in pa[2:]:
        if _isconst(h):
            if h:
                SeqCompute([(dl, SetTo, M32), (dh, SetTo, M32)])
            continue
        RawTrigger(conditions=h.AtLeast(1), actions=[dl.SetNumber(M32), dh.SetNumber(M32)])


def _to32_into(dst, pa, saturate):
    k = _const4(pa)
    if k is not None:
        SeqCompute([(dst, SetTo, min(k, M32) if saturate else k & M32)])
        return
    SeqCompute([(dst, SetTo, pa[0])])
    if not saturate:
        return
    for h in pa[1:]:
        if _isconst(h):
            if h:
                SeqCompute([(dst, SetTo, M32)])
            continue
        RawTrigger(conditions=h.AtLeast(1), actions=dst.SetNumber(M32))


def f_to64(a, saturate=True):
    """128비트 값을 64비트(새 Int64)로 내린다.

    인자: a(128비트 피연산자), saturate(True = min(a, 2^64 − 1) — 포화, False = 하위 64비트)
    반환: 새 Int64 (상수면 int)
    비용: 호출 3 / 실행 5 (2026-09-17, docs/COSTS.md "i128 (WP20)")
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const lo = i128.to64(x);` · `const lo = x.to64(saturate=False);`
    출처: DPS math128 의 `{Div_Q1, …}` 하위 칸 쓰기 대체
    """
    if not isinstance(saturate, bool):
        fail("i128.to64: saturate 는 True/False 여야 합니다 (%r)", saturate)
    pa = _words(a, "i128.to64")
    k = _const4(pa)
    if k is not None:
        return min(k, M64) if saturate else k & M64
    dl, dh = EUDVariable(), EUDVariable()
    _to64_into(dl, dh, pa, saturate)
    return Int64.wrap(dl, dh)


def f_to32(a, saturate=True):
    """128비트 값을 32비트(새 EUDVariable)로 내린다. saturate=True = min(a, 2^32 − 1), False = 하위 32비트.

    비용: 호출 4 / 실행 5. epScript: `var v = i128.to32(x);` · `var v = x.to32();`
    """
    if not isinstance(saturate, bool):
        fail("i128.to32: saturate 는 True/False 여야 합니다 (%r)", saturate)
    pa = _words(a, "i128.to32")
    k = _const4(pa)
    if k is not None:
        return min(k, M32) if saturate else k & M32
    dst = EUDVariable()
    _to32_into(dst, pa, saturate)
    return dst


to64 = f_to64
to32 = f_to32


# =============================================================================================
# Int128
# =============================================================================================


def _inl(v, fname):
    if v is None or isinstance(v, bool):
        return v
    fail("%s: inline 은 None/True/False 여야 합니다 (%r)", fname, v)
    return None


def _left32_error(sym):
    fail(
        "32비트 변수가 왼쪽인 %s 는 eudplib 연산자가 먼저 불려 Int128 을 상수처럼 다룹니다 — "
        "i128.mul(v, x) / i128.div(v, x) / i128.mod(v, x) 처럼 모듈 함수를 쓰세요 (DESIGN 3.2).",
        sym,
    )


class Int128:
    """128비트 부호 없는 정수 값 타입 (파이썬 객체 + EUDVariable 네 개, w0 이 최하위).

    생성: `Int128()`/`Int128(상수)`/`Int128("10진")` = 초기값만(트리거 0), `Int128(Int64)`·`Int128(변수)` = 실행 시 대입(0 확장),
          `Int128(lo, hi)`(각 반쪽 = Int64·64비트 상수·32비트 변수)·`Int128(Int128)` = 실행 시 대입,
          `Int128.wrap(lo, hi)`(Int64 둘)·`Int128.wrap(w0, w1, w2, w3)`(EUDVariable 넷) = 복사 없이 감싸기.
    대입: `x << y`, `x.assign(y)`, `x.v = y`(epScript).
    덧셈: `x += y`, `x.iadd(y)`, `x.v += y`, `x + y`. 뺄셈(**wrap**): `x -= y`, `x.isub(y)`, `x.v -= y`, `x - y`, `-x`, `x.neg()`, `x.ineg()`.
    뺄셈(**포화**, 128비트 전체 기준): `x.isub_sat(y)`, `x.isubtractattr("v", y)`, `i128.sub_sat(x, y)`.
    비교: `>= <= > < == !=`(부호 없는 사전식) → 조건. 곱셈(wrap): `x * y`, `x *= y`, `x.imul(y)`, `x.v *= y`.
    나눗셈(부호 없음): `x // y`, `x % y`, `divmod(x, y)`, `x.idiv(y)`, `x.imod(y)`, `x.v /= y`, `x.v %= y`.
    출력: `x.fmt()`. 내리기: `x.to64(saturate=True)`, `x.to32(saturate=True)`. 반쪽: `x.lo`, `x.hi`(Int64), 칸: `x.w0`~`x.w3`.
    인자: value(상수·문자열·변수·Int64·Int128), hi(선택: 상위 64비트 — 주면 value 는 하위 64비트)
    반환: -
    비용: 연산별(모듈 설명·docs/COSTS.md "i128 (WP20)"). 객체 하나 = 변수 4개(72B × 4)
    CP: 바꾸지 않음
    로컬: 공유 안전 (로컬 값을 넣으면 결과도 로컬)
    epScript: `const x = i128.Int128(0);` (var 가 아니라 const), `x.v += 5;`, `if (x >= 10) { … }`
    출처: DPS math128.lua 의 W 두 칸 128비트 값({lo, hi}) 대체, eudext.i64.Int64(3.2 기준 구현)
    """

    __slots__ = ("_elem", "_w")
    dont_flatten = True

    def __init__(self, value=0, hi=None):
        self._elem = False
        if hi is None:
            if isinstance(value, (Int128, Int64)):
                self._w = _new4()
                _assign4(self._w, _words(value, "Int128"))
                return
            u = unProxy(value)
            if isinstance(u, (bool, int, str, bytes)):
                self._w = tuple(EUDVariable(k) for k in _words(u, "Int128"))
                return
            if _compat.is_const(u) and not _compat.is_var(u) and not _compat.is_varbase(u):
                self._w = (EUDVariable(u), EUDVariable(0), EUDVariable(0), EUDVariable(0))  # 주소식 = 32비트 초기값
                return
            src = _words(u, "Int128")
            self._w = _new4()
            _assign4(self._w, src)
            return
        lo = _half64(value, "Int128(lo, hi)", "lo")
        hh = _half64(hi, "Int128(lo, hi)", "hi")
        self._w = _new4()
        _assign4(self._w, tuple(lo) + tuple(hh))

    @classmethod
    def wrap(cls, *parts):
        """이미 있는 변수를 복사 없이 Int128 로 감싼다(EUDFunc 인자·반환값 받기, 3.2-8).

        인자: (lo, hi) — Int64 둘, 또는 (w0, w1, w2, w3) — EUDVariable 넷 (w0 이 최하위)
        반환: Int128 (칸이 그 변수들)
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `function f(a0, a1, a2, a3) { const x = i128.Int128.wrap(a0, a1, a2, a3); … }` · `i128.wrap(lo64, hi64)`
        출처: eudext.i64.Int64.wrap
        """
        us = [unProxy(p) for p in parts]
        if len(us) == 2 and all(isinstance(p, Int64) for p in us):
            ws = (us[0].lo, us[0].hi, us[1].lo, us[1].hi)
        elif len(us) == 4 and all(_isvar(p) for p in us):
            ws = tuple(us)
        else:
            fail("Int128.wrap: (Int64, Int64) 또는 EUDVariable 넷이 필요합니다 (%r)", parts)
        obj = cls.__new__(cls)
        obj._w, obj._elem = ws, False
        return obj

    @classmethod
    def cast(cls, _from):
        """EUDTypedFunc 호환 자리 — 128비트는 변수 한 칸으로 넘길 수 없어 늘 오류(3.2-8)."""
        fail(
            "Int128 은 함수 인자 한 칸으로 넘길 수 없습니다(EUDTypedFunc([Int128]) 불가). "
            "x.w0, x.w1, x.w2, x.w3 네 인자로 넘기고 본문에서 Int128.wrap(w0, w1, w2, w3) 로 감싸세요."
        )

    # --- 실수 막기 (3.2-2) ---
    def __repr__(self):
        return (
            "<eudext.i128.Int128 — 값 타입(변수 4개). epScript 에서는 'var x = …' 대신 "
            "'const x = i128.Int128(…);' 로 선언하고 x.v = …, x.v += … 로 고치세요>"
        )

    def __hash__(self):
        return id(self)

    def __bool__(self):
        fail("Int128 을 파이썬 if/and/or 에 넣을 수 없습니다. 조건은 EUDIf()(x != 0) 처럼 쓰세요.")

    def __iter__(self):
        fail("Int128 은 나열할 수 없습니다: %s", self.__repr__())

    def __format__(self, spec):
        fail("f_sprintf/printAll 의 {} 에는 x.fmt() 를 넘기세요 (Int128 자체는 서식에 넣을 수 없습니다).")

    def __len__(self):
        fail("Int128 에는 길이가 없습니다: %s", self.__repr__())

    def _check_write(self, what):
        if self._elem:
            fail(
                "Int128Array 원소 읽기(arr[i])는 사본입니다 — %s 가 배열에 쓰이지 않습니다. "
                "arr[i] += v / arr[i] -= v / arr.isub_sat(i, v) / arr[i] = v 를 쓰거나, 사본이 필요하면 Int128(arr[i]) 로 만드세요.",
                what,
            )

    # --- 칸 ---
    @property
    def w0(self):
        return self._w[0]

    @property
    def w1(self):
        return self._w[1]

    @property
    def w2(self):
        return self._w[2]

    @property
    def w3(self):
        return self._w[3]

    @property
    def words(self):
        """칸 넷 (w0, w1, w2, w3) — EUDVariable, w0 이 최하위."""
        return self._w

    def _half(self, a, b):
        x = Int64.wrap(self._w[a], self._w[b])
        x._elem = self._elem
        return x

    @property
    def lo(self):
        """하위 64비트 (복사 없이 같은 변수를 감싼 Int64)."""
        return self._half(0, 1)

    @property
    def hi(self):
        """상위 64비트 (복사 없이 같은 변수를 감싼 Int64)."""
        return self._half(2, 3)

    # --- 대입 ---
    def __lshift__(self, other):
        if _compat.eps_lshift_caller():
            fail(
                "epScript 식 `x << n` 은 시프트로 번역되지만 Int128 의 `<<` 는 대입입니다(시프트는 없습니다). "
                "대입은 x.v = y; 로 쓰세요."
            )
        self._check_write("대입")
        _assign4(self._w, _words(other, "Int128 <<"))
        return self

    def assign(self, other):
        """x ← other (실행 시 대입). 반환 self. 비용: 상수 = 호출 1 / 실행 1, 변수 = 1 / 5. epScript: `x.assign(y);`"""
        self._check_write("대입")
        _assign4(self._w, _words(other, "Int128.assign"))
        return self

    @property
    def v(self):
        """epScript 통로(3.2-6): `x.v = y;` `x.v += y;` `x.v -= y;`(wrap) `x.v *= y;` `x.v /= y;` `x.v %= y;`. 읽으면 self."""
        return self

    @v.setter
    def v(self, value):
        if value is self:  # 파이썬 `x.v += y` 의 되쓰기
            return
        self._check_write("x.v = …")
        _assign4(self._w, _words(value, "Int128.v"))

    def _attr(self, name):
        if name != "v":
            raise AttributeError(name)

    def iaddattr(self, name, value):
        self._attr(name)
        self._check_write("x.v += …")
        self.iadd(value)

    def isubattr(self, name, value):
        self._attr(name)
        self._check_write("x.v -= …")
        self.isub(value)

    def isubtractattr(self, name, value):
        """포화 별칭(eudplib `isubtractattr` 관례): `x.isubtractattr("v", y)` = `x.isub_sat(y)`."""
        self._attr(name)
        self.isub_sat(value)

    def imulattr(self, name, value):
        self._attr(name)
        self.imul(value)

    def ifloordivattr(self, name, value):
        self._attr(name)
        self.idiv(value)

    def imodattr(self, name, value):
        self._attr(name)
        self.imod(value)

    # --- 덧셈 ---
    def iadd(self, other, inline=None):
        """x ← x + other (128비트 wrap). 반환 self.

        인자: other — Int128·Int64·상수·문자열·32비트 변수(0 확장),
              inline(None = 32비트 이하 값이면 펼치고 그 밖은 공유 EUDFunc — DESIGN 3.3 / True = 펼침 / False = 공유 함수)
        반환: self
        비용: 변수(기본 공유 함수) = 호출 1 / 실행 35 (본문 11 — Int64 는 33), inline=True = 호출 9 / 실행 16 (Int64 8 / 12),
              32비트 변수 = 펼침 7 / 9, 상수 = 호출·실행 4~7 (2026-09-17, docs/COSTS.md "i128 (WP20)")
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `x.v += y;` · `x.iadd(y);`
        출처: DPS math128.lua `f_LAdd128`(Call_Add Size 2), DPS_Enhance eudplib-port a7aad90 eud/ctrig/war.py:1458 `AddWords`
        """
        self._check_write("+=")
        _iadd4(self._w, _words(other, "Int128 +="), inline=_inl(inline, "Int128.iadd"))
        return self

    def __iadd__(self, other):
        # 파이썬 `arr[i] += v` 는 읽은 사본에 더하고 `arr[i] = 사본` 으로 되쓰므로 사본이어도 막지 않는다
        _iadd4(self._w, _words(other, "Int128 +="))
        return self

    def __add__(self, other):
        return f_add(self, other)

    def __radd__(self, other):
        return f_add(other, self)

    # --- 뺄셈 ---
    def isub(self, other, inline=None):
        """x ← x − other (128비트 **wrap**). 반환 self. `x -= x` 는 0 으로 접는다.

        인자: other — Int128·Int64·상수·문자열·32비트 변수, inline(None·True·False — `iadd` 와 같음)
        반환: self
        비용: 변수(기본 공유 함수) = 호출 1 / 실행 39 (본문 11), inline=True = 호출 9 / 실행 20, 32비트 변수 = 펼침 9 / 12,
              상수 = 호출·실행 7 (2026-09-17, docs/COSTS.md "i128 (WP20)")
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `x.v -= y;` · `x.isub(y);`
        출처: DPS math128.lua `f_LSub128_Simple`(wrap 쪽), DPS_Enhance eudplib-port a7aad90 eud/ctrig/war.py:1537 `SubWords`
        """
        self._check_write("-=")
        _isub4(self._w, _words(other, "Int128 -="), inline=_inl(inline, "Int128.isub"))
        return self

    def __isub__(self, other):
        _isub4(self._w, _words(other, "Int128 -="))
        return self

    def __sub__(self, other):
        if _compat.eudplib_calc_caller():
            _left32_error("// (또는 %)")
        return f_sub(self, other)

    def __rsub__(self, other):
        return f_sub(other, self)

    def isub_sat(self, other, inline=False):
        """x ← max(x − other, 0) (**포화**, 128비트 전체 기준). 반환 self. `x.isub_sat(x)` 는 0 으로 접는다.

        반쪽별 포화가 아니다: 2^64 − 1 = (1:0) − (0:1) 도 맞다(DPS f_LSub128 은 이 경계에서 다르다 — 모듈 설명).
        인자: other — Int128·Int64·상수·문자열·32비트 변수, inline(True 면 공유 함수 대신 호출 자리에 펼침)
        반환: self
        비용: 변수 = 호출 1 / 실행 43 (공유 EUDFunc, 기본 — 본문 14), inline=True = 호출 12 / 실행 24,
              상수 = 호출·실행 8~11 (2026-09-17, docs/COSTS.md "i128 (WP20)")
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `x.isub_sat(dmg);` · `x.isub_sat(dmg, inline=True);`
        출처: DPS math128.lua `f_LSub128`(의도 = 0 에서 멈춤), DESIGN 3.5
        """
        self._check_write("isub_sat")
        _isub_sat4(self._w, _words(other, "Int128.isub_sat"), inline=_inl(inline, "Int128.isub_sat"))
        return self

    def ineg(self):
        """x ← −x (128비트 wrap, 2의 보수). 반환 self. 비용: 호출 1 / 실행 약 37 (wrap 뺄셈 공유 함수). epScript: `x.ineg();`"""
        self._check_write("ineg")
        _addsub_fn("sub")(0, 0, 0, 0, *self._w, ret=list(self._w))
        return self

    def neg(self):
        """−x 를 새 Int128 로 (wrap). epScript: `const y = x.neg();` (`-x` 와 같음)"""
        return f_neg(self)

    def __neg__(self):
        return f_neg(self)

    def __pos__(self):
        return self

    # --- 비교 (부호 없음) ---
    def __ge__(self, other):
        return _compare("ge", self, other, "Int128 >=")

    def __le__(self, other):
        return _compare("le", self, other, "Int128 <=")

    def __gt__(self, other):
        return _compare("gt", self, other, "Int128 >")

    def __lt__(self, other):
        return _compare("lt", self, other, "Int128 <")

    def __eq__(self, other):
        if unProxy(other) is None:
            return NotImplemented
        if _compat.eudplib_calc_caller():
            _left32_error(">>")
        return _compare("eq", self, other, "Int128 ==")

    def __ne__(self, other):
        if unProxy(other) is None:
            return NotImplemented
        return _compare("ne", self, other, "Int128 !=")

    # --- 출력·내리기 ---
    def fmt(self):
        """10진 출력용 값(`ptr2s`). `i128.fmt(self)` 와 같다. epScript: `printAll("DPS {}", x.fmt());`"""
        return f_fmt(self)

    def to64(self, saturate=True):
        """64비트 값(새 Int64)으로. `i128.to64(self, saturate)` 와 같다. epScript: `const lo = x.to64();`"""
        return f_to64(self, saturate=saturate)

    def to32(self, saturate=True):
        """32비트 값(새 EUDVariable)으로. `i128.to32(self, saturate)` 와 같다. epScript: `var v = x.to32();`"""
        return f_to32(self, saturate=saturate)

    # --- 곱셈·나눗셈 ---
    def imul(self, other):
        """x ← x × other (128비트 wrap). 반환 self.

        인자: other — Int128·Int64·상수·문자열·32비트 변수(0 확장)
        반환: self
        비용: `i128.mul` 과 같음 (128×128 = 호출 1 / 실행 108~1,326, 128×64 = 104~963, 상수 = 42~196)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `x.v *= y;` · `x.imul(y);`
        출처: DPS math128.lua `f_LMul128X`(wrap 판)
        """
        self._check_write("*=")
        _mul_into4(self._w, self._w, _words(other, "Int128 *="))
        return self

    def __imul__(self, other):
        _mul_into4(self._w, self._w, _words(other, "Int128 *="))
        return self

    def __mul__(self, other):
        return f_mul(self, other)

    def __rmul__(self, other):
        return f_mul(other, self)

    def idiv(self, other):
        """x ← x // other (부호 없음, 0 나눗셈 = 2^128 − 1). 반환 self. epScript: `x.v /= y;` · `x.idiv(y);`"""
        self._check_write("//=")
        _divmod_into4(self._w, None, self._w, _words(other, "Int128 //="))
        return self

    def __ifloordiv__(self, other):
        _divmod_into4(self._w, None, self._w, _words(other, "Int128 //="))
        return self

    def __floordiv__(self, other):
        return f_div(self, other)

    def __rfloordiv__(self, other):
        return f_div(other, self)

    def imod(self, other):
        """x ← x % other (부호 없음, 0 나눗셈 = x 그대로). 반환 self. epScript: `x.v %= y;` · `x.imod(y);`"""
        self._check_write("%=")
        _divmod_into4(None, self._w, self._w, _words(other, "Int128 %="))
        return self

    def __imod__(self, other):
        _divmod_into4(None, self._w, self._w, _words(other, "Int128 %="))
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
        fail("Int128 은 정수 나눗셈만 됩니다: 파이썬은 x // y, epScript 는 x / y (// 로 번역된다)")

    __rtruediv__ = __itruediv__ = __truediv__

    # --- 없는 연산 (DPS math128 이 쓰지 않음) ---
    def __iand__(self, other):
        if _compat.eudplib_calc_caller():
            _left32_error("* (또는 // %)")
        fail("Int128 에는 비트 연산이 없습니다 (DESIGN 4.4b — DPS math128 이 쓰지 않음). 64비트는 i64 를 쓰세요.")

    def _nobits(self, *_a):
        fail("Int128 에는 비트 연산·시프트가 없습니다 (DESIGN 4.4b — DPS math128 이 쓰지 않음). 64비트는 i64 를 쓰세요.")

    __and__ = __rand__ = __or__ = __ror__ = __ior__ = __xor__ = __rxor__ = __ixor__ = _nobits
    __invert__ = __rshift__ = __rrshift__ = __irshift__ = __ilshift__ = __rlshift__ = _nobits

    def __pow__(self, other):
        fail("Int128 거듭제곱(**)은 지원하지 않습니다. 곱셈을 이어 쓰세요 (x * x * x).")

    __rpow__ = __ipow__ = __pow__


# =============================================================================================
# 모듈 함수 (epScript: m.foo() → m.f_foo())
# =============================================================================================


def _target(x, fname):
    x = unProxy(x)
    if not isinstance(x, Int128):
        fail("%s: 대상은 Int128 이어야 합니다 (%r)", fname, x)
    return x


def _new_value(fill):
    w = _new4()
    fill(w)
    return Int128.wrap(*w)


def f_wrap(*parts):
    """`Int128.wrap(…)` 와 같다 (epScript: `const x = i128.wrap(lo64, hi64);` · `i128.wrap(w0, w1, w2, w3)`)."""
    return Int128.wrap(*parts)


wrap = f_wrap


def _binop3(op, a, b, fname, inline):
    pa, pb = _words(a, fname, "a"), _words(b, fname, "b")
    ka, kb = _const4(pa), _const4(pb)
    if ka is not None and kb is not None:
        v = ka + kb if op == "add" else ka - kb if op == "sub" else max(ka - kb, 0)
        return v & M128
    return _new_value(lambda w: _op3(w, pa, pb, op, inline))


def f_add(a, b, inline=None):
    """a + b 를 새 Int128 로 (128비트 wrap). 상수끼리는 파이썬 int.

    인자: a, b — Int128·Int64·상수·문자열·32비트 변수, inline(None·True·False — `Int128.iadd` 와 같음)
    반환: 새 Int128 (또는 int)
    비용: 변수끼리(기본 공유 함수) = 호출 1 / 실행 35, inline=True = 호출 9 / 실행 20, 한쪽 상수 = 호출 2~8 / 실행 2~8
          (2026-09-17, docs/COSTS.md "i128 (WP20)")
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const s = i128.add(x, y);` (Int128 끼리는 `x + y` 도 된다)
    출처: DPS math128.lua `f_LAdd128`
    """
    return _binop3("add", a, b, "i128.add", _inl(inline, "i128.add"))


def f_sub(a, b, inline=None):
    """a − b 를 새 Int128 로 (128비트 **wrap**). 상수끼리는 파이썬 int. `sub(x, x)` = 0.

    비용: 변수끼리(기본 공유 함수) = 호출 1 / 실행 39, inline=True = 호출 9 / 실행 약 24, b 상수 = 호출 2~8.
    epScript: `const d = i128.sub(x, y);`
    출처: DPS math128.lua `f_LSub128_Simple`(wrap 쪽)
    """
    return _binop3("sub", a, b, "i128.sub", _inl(inline, "i128.sub"))


def f_sub_sat(a, b, inline=False):
    """max(a − b, 0) 를 새 Int128 로 (**포화**, 128비트 전체 기준). 상수끼리는 파이썬 int. `sub_sat(x, x)` = 0.

    인자: a, b — Int128·Int64·상수·문자열·32비트 변수, inline(True 면 호출 자리에 펼침)
    반환: 새 Int128 (또는 int)
    비용: 변수끼리 = 호출 1 / 실행 43 (공유 EUDFunc, 기본), inline=True = 호출 12 / 실행 약 28,
          b 상수 = 호출·실행 2~12 (2026-09-17, docs/COSTS.md "i128 (WP20)")
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const r = i128.sub_sat(total, used);`
    출처: DPS math128.lua `f_LSub128`(0 에서 멈추는 뺄셈 — 반쪽별 보정 판 대신 128비트 전체 기준), DESIGN 3.5
    """
    return _binop3("ssub", a, b, "i128.sub_sat", _inl(inline, "i128.sub_sat"))


def f_neg(a):
    """−a 를 새 Int128 로 (128비트 wrap). 상수는 파이썬 int. 비용: 호출 1 / 실행 약 37 (32비트 값은 펼침). epScript: `const n = i128.neg(x);`"""
    pa = _words(a, "i128.neg")
    k = _const4(pa)
    if k is not None:
        return (-k) & M128
    return _new_value(lambda w: _op3(w, (0, 0, 0, 0), pa, "sub", None))


def f_iadd(x, b, inline=None):
    """x ← x + b (x 는 Int128). `x.iadd(b)` 와 같다. epScript: `i128.iadd(x, b);`"""
    return _target(x, "i128.iadd").iadd(b, inline=inline)


def f_isub(x, b, inline=None):
    """x ← x − b (**wrap**, x 는 Int128). `x.isub(b)` 와 같다. epScript: `i128.isub(x, b);`"""
    return _target(x, "i128.isub").isub(b, inline=inline)


def f_isub_sat(x, b, inline=False):
    """x ← max(x − b, 0) (**포화**, x 는 Int128). `x.isub_sat(b, inline)` 와 같다. epScript: `i128.isub_sat(x, b);`"""
    return _target(x, "i128.isub_sat").isub_sat(b, inline=inline)


def f_mul(a, b):
    """a × b 를 새 Int128 로 (128비트 wrap). 상수끼리는 파이썬 int. 64비트 이하끼리는 전체 곱(넘치지 않는다).

    곱해지는 수를 16비트 조각 넷으로 나눠, 곱하는 수의 비트마다 조건 트리거 하나 + 변수 트리거 사슬로 넘치지 않는
    누적기 16개에 더한다(64×64 → 128). 128비트가 끼면 하위 전체 곱에 i64 64비트 곱(상위 × 하위)을 더한다.
    상수 곱은 상수마다 공유 본문(비트 누적 — 곱해지는 수의 비트마다 트리거 하나).
    인자: a, b — Int128·Int64·상수(−2^127 ~ 2^128−1)·10진 문자열·32비트 변수(0 확장)
    반환: 새 Int128 (또는 int)
    비용: 변수 64×64 = 호출 1 / 실행 165~585 (본문 251, 한 번 페이로드 약 123KB), 64×32 = 119~368 (본문 162),
          32×32 = i64 본문(68~209, 본문 106), 128×64 = 104~963, 128×128 = 108~1,326 (본문 13 + 64×64 본문 + i64 64×64 본문 171).
          상수 = 호출 1 / 실행 20~196 (상수마다 본문 117~184, 한 번 페이로드 약 36~48KB) (2026-09-17, docs/COSTS.md "i128 (WP20)")
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const p = i128.mul(x, y);` · `const p = x * 100000000;` (Int128 이 왼쪽이면 연산자도 된다)
    출처: DPS math128.lua `f_LMul128`·`f_LMul128_2`·`f_LMul128X`(wrap 판), DESIGN 4.4(16비트 쪼개기), DPS_Enhance
          eudplib-port a7aad90 eud/ctrig/war.py:1220 `_mul6464`
    """
    pa, pb = _words(a, "i128.mul", "a"), _words(b, "i128.mul", "b")
    ka, kb = _const4(pa), _const4(pb)
    if ka is not None and kb is not None:
        return (ka * kb) & M128
    return _new_value(lambda w: _mul_into4(w, pa, pb))


def f_mul64(a, b):
    """64비트 × 64비트 → 128비트 전체 곱 (새 Int128). a, b 는 64비트 값(Int64·64비트 상수·32비트 변수 — Int128 은 오류).

    인자: a, b — 64비트 값
    반환: 새 Int128 (상수끼리는 int)
    비용: `i128.mul` 과 같음 (64×64 = 호출 1 / 실행 165~585, 64×32 = 119~368, 32×32 = 68~209)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const p = i128.mul64(dmg, rate);`
    출처: DPS math128.lua `f_LMul128(A, B)`·`f_LMul128_2(A, B)`, DPS_Enhance eudplib-port a7aad90 war.py:1242 `Mul128`
    """
    pa = tuple(_half64(a, "i128.mul64", "a")) + (0, 0)
    pb = tuple(_half64(b, "i128.mul64", "b")) + (0, 0)
    ka, kb = _const4(pa), _const4(pb)
    if ka is not None and kb is not None:
        return ka * kb
    return _new_value(lambda w: _mul_into4(w, pa, pb))


def f_div(a, b):
    """a // b (부호 없는 128비트 몫)을 새 Int128 로. 0 나눗셈 = 2^128 − 1. 상수끼리는 int.

    인자: a, b — Int128·Int64·상수·10진 문자열·32비트 변수 (제수도 128비트까지)
    반환: 새 Int128 (또는 int)
    비용: 32비트 제수 = 호출 1 / 실행 124~703 (본문 13 + i64 64÷64 본문 389), 64비트 제수 = 127~약 1,050
          (최악 추정 약 1,270 — 본문 143), 128비트 제수 = 48~약 1,270 (최악 추정 약 1,520 — 본문 209),
          상수 제수 < 2^32 = 40~231 (상수마다 본문 9 + i64 상수 본문 약 120 — i64 와 공유), 그 이상 상수 = 변수 제수 본문
          (2026-09-17, docs/COSTS.md "i128 (WP20)")
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const q = i128.div(x, y);` · `const q = x / 100;` (epScript `/` 는 `//`)
    출처: DPS math128.lua `f_LDiv128`(Call_div128), DPS_Enhance eudplib-port a7aad90 war.py:1136 `_div128`·`Div128`
    """
    return _divop(a, b, "q", "i128.div")


def f_mod(a, b):
    """a % b (부호 없는 나머지)를 새 Int128 로(제수가 64비트 이하면 상위 64비트는 0 — `.lo` 가 Int64). 0 나눗셈 = a.

    비용: `i128.div` 와 같다(한 본문이 몫과 나머지를 같이 낸다). epScript: `const r = i128.mod(x, 1000);` · `x % 1000`
    출처: DPS math128.lua `f_LDiv128` 의 `Div_R1`·`Div_R2`
    """
    return _divop(a, b, "r", "i128.mod")


def f_divmod(a, b):
    """(a // b, a % b) 를 새 Int128 두 개로. epScript: `const q, r = i128.divmod(x, y);`"""
    return _divop(a, b, "qr", "i128.divmod")


def _divop(a, b, want, fname):
    pa, pb = _words(a, fname, "a"), _words(b, fname, "b")
    ka, kb = _const4(pa), _const4(pb)
    if ka is not None and kb is not None:
        qq, rr = (ka // kb, ka % kb) if kb else (M128, ka)
        return {"q": qq, "r": rr, "qr": (qq, rr)}[want]
    q = _new4() if "q" in want else None
    r = _new4() if "r" in want else None
    _divmod_into4(q, r, pa, pb)
    out = [Int128.wrap(*v) for v in (q, r) if v is not None]
    return out[0] if len(out) == 1 else tuple(out)


def _inplace_fn(method, what):
    def f(x, *args, **kw):
        return getattr(_target(x, "i128." + what), method)(*args, **kw)

    f.__name__ = f.__qualname__ = "f_" + what
    f.__doc__ = "x ← x %s b 제자리 (x 는 Int128). `x.%s(b)` 와 같다. epScript: `i128.%s(x, b);`" % (
        {"imul": "×", "idiv": "//", "imod": "%"}[what],
        method,
        what,
    )
    return f


f_imul = _inplace_fn("imul", "imul")
f_idiv = _inplace_fn("idiv", "idiv")
f_imod = _inplace_fn("imod", "imod")

add = f_add
sub = f_sub
sub_sat = f_sub_sat
neg = f_neg
iadd = f_iadd
isub = f_isub
isub_sat = f_isub_sat
mul = f_mul
mul64 = f_mul64
div = f_div
mod = f_mod
divmod = f_divmod  # noqa: A001 — 모듈 안에서 파이썬 divmod 를 쓰지 않는다 (__all__ 에는 f_divmod 만)
imul = f_imul
idiv = f_idiv
imod = f_imod


# --- DPS math128 이름 별칭 (호출 모양만 — PlayerID 인자는 없다) ---


def f_LMov128(dst, src):
    """DPS `f_LMov128(FP, Dest, Source)` 별칭: dst ← src (dst 는 Int128). 반환 dst. epScript: `i128.LMov128(d, x);`"""
    return _target(dst, "i128.LMov128").assign(src)


def f_LAdd128(a, b):
    """DPS `Math128.f_LAdd128({a1, a2}, {b1, b2})` 별칭: 새 Int128 = a + b (wrap). epScript: `const s = i128.LAdd128(a, b);`"""
    return f_add(a, b)


def f_LSub128(a, b):
    """DPS `Math128.f_LSub128` 별칭: 새 Int128 = max(a − b, 0) — **128비트 전체 기준 포화**.

    원본은 상위 64비트를 먼저 포화로 빼서 `a < b` 인데 0 이 아닌 값을 내는 경우(상위 a < b 이고 하위 a > b)가 있다 —
    그 동작은 옮기지 않았다(DESIGN 3.5: 반쪽별 포화 금지). epScript: `const r = i128.LSub128(total, used);`
    """
    return f_sub_sat(a, b)


def f_LMul128(a, b):
    """DPS `f_LMul128(A, B)`/`f_LMul128_2(A, B)` 별칭: 64×64 → 새 Int128 (`.lo`, `.hi` 가 원본의 Retlo, Rethi).

    epScript: `const p = i128.LMul128(a, b);`. 128비트가 끼는 `f_LMul128X` 는 `a * b`(wrap — 원본의 "두 상위가 모두 0 이
    아니면 최댓값" 규칙은 옮기지 않았다).
    """
    return f_mul64(a, b)


def f_LDiv128(a, d):
    """DPS `f_LDiv128({a1, a2}, {d1, d2})` 별칭: (몫, 나머지) 새 Int128 두 개. 0 나눗셈 = eudext 규칙(몫 2^128 − 1, 나머지 = a).

    원본 math128 의 0 나눗셈은 나머지 반쪽이 뒤바뀐다(R1 ← a2, R2 ← a1) — 옮기지 않았다.
    epScript: `const q, r = i128.LDiv128(a, 100);`
    """
    return f_divmod(a, d)


_CMP_TYPES = {">": "gt", "<": "lt", "==": "eq", ">=": "ge", "<=": "le", "!=": "ne"}


def f_LCmp128(a, op, b):
    """DPS `Compare_128(A, Type, B)`/`Math128.f_LCmp128` 별칭: 조건(부호 없는 128비트)을 돌려준다(원본은 Ccode 에 0/1).

    인자: op — ">"·"<"·"=="·">="·"<="·"!=" 또는 eudplib `AtLeast`/`AtMost`/`Exactly`
    epScript: `if (i128.LCmp128(a, ">=", b)) { … }`
    """
    if op is AtLeast:
        name = "ge"
    elif op is AtMost:
        name = "le"
    elif op is Exactly:
        name = "eq"
    elif isinstance(op, str) and op in _CMP_TYPES:
        name = _CMP_TYPES[op]
    else:
        fail("i128.LCmp128: 비교 종류는 >, <, ==, >=, <=, != 또는 AtLeast/AtMost/Exactly 여야 합니다 (%r)", op)
    return _compare(name, a, b, "i128.LCmp128")


LMov128 = f_LMov128
LAdd128 = f_LAdd128
LSub128 = f_LSub128
LMul128 = f_LMul128
LMul128_2 = f_LMul128
LDiv128 = f_LDiv128
LCmp128 = f_LCmp128
Compare_128 = f_LCmp128


# =============================================================================================
# Int128Array
# =============================================================================================


class Int128Array(ExprProxy):
    """128비트 값 n 개 배열 = EUDArray 넷(칸 w0~w3, 원소당 16B). 배열처럼 쓴다(ExprProxy — 3.11).

    - 읽기 `arr[i]` = 새 Int128 **사본**(메서드·`.v` 로 제자리 연산하면 오류 — epScript `arr[i].v += 1;` 함정).
      파이썬 `arr[i] += v` 는 읽고-더하고-되쓰므로 맞지만 비싸다 → `arr.iadd(i, v)`.
    - 쓰기 `arr[i] = v`, 덧셈 `arr[i] += v`(iadditem), 뺄셈 `arr[i] -= v`(isubitem, **wrap**),
      포화 `arr.isub_sat(i, v)`(= `isubtractitem`, 128비트 전체 기준), 곱셈·나눗셈 `arr[i] *= v`, `/=`, `%=`.
    - 비교 `arr[i] >= v` 등(epScript `_ARRC` → `geitem` …).
    - 칸 배열: `arr.w0`~`arr.w3`(32비트 EUDArray), 칸 번호 i 의 칸 EPD = `arr.epd(k) + i`. 반쪽: `arr.get(i).lo`.
    - 칸 번호·값이 모두 상수면 읽지 않고 칸을 바로 고친다(덧셈·wrap 뺄셈 1~7 트리거, 포화 1~11, 비교 0~4).
      그 밖은 읽고(`f_dwread_epd` 네 번) 셈하고 다시 쓴다.
    인자: n_or_values — 원소 수(int) 또는 초기값 목록(128비트 정수·문자열)
    반환: -
    비용: 변수 칸 읽기 = 호출 9 / 실행 154 (f_dwread_epd × 4), 쓰기 = 호출 5 / 실행 14, `arr[i] += y` = 15 / 203,
          상수 칸·상수 값 = 덧셈 4 / 4, 비교 5 / 5 (2026-09-17, docs/COSTS.md "i128 (WP20)")
    CP: 바꾸지 않음 (eudplib 읽기·쓰기가 잠깐 옮기고 되돌림)
    로컬: 공유 안전
    epScript: `const dps = i128.Int128Array(8); dps[p] += dmg; if (dps[p] >= 100) { … }`
    출처: DPS 의 플레이어별 128비트 값(`PVWArrX(iv.X)`·`PVWArrX(iv.Xhi)` 쌍) 대체
    """

    __slots__ = ("_arrs", "_n")

    def __init__(self, n_or_values):
        v = unProxy(n_or_values)
        if isinstance(v, bool) or not isinstance(v, (int, list, tuple)):
            fail("Int128Array: 원소 수(int) 또는 초기값 목록이 필요합니다 (%r)", n_or_values)
        if isinstance(v, int):
            if v <= 0:
                fail("Int128Array: 원소 수는 1 이상이어야 합니다 (%d)", v)
            arrs = tuple(EUDArray(v) for _ in range(4))
            n = v
        else:
            vals = [f_parse(x) for x in v]
            if not vals:
                fail("Int128Array: 빈 초기값 목록")
            arrs = tuple(EUDArray([_split4(x)[k] for x in vals]) for k in range(4))
            n = len(vals)
        super().__init__(arrs[0])
        object.__setattr__(self, "_arrs", arrs)
        object.__setattr__(self, "_n", n)

    def __repr__(self):
        return "<eudext.i128.Int128Array n=%d>" % self._n

    def __len__(self):
        return self._n

    def __iter__(self):
        fail("Int128Array 는 파이썬에서 나열할 수 없습니다 (EUDLoopRange 로 번호를 돌리세요)")

    def __hash__(self):
        return id(self)

    @property
    def length(self):
        return self._n

    @property
    def w0(self):
        return self._arrs[0]

    @property
    def w1(self):
        return self._arrs[1]

    @property
    def w2(self):
        return self._arrs[2]

    @property
    def w3(self):
        return self._arrs[3]

    def epd(self, k):
        """칸 배열 k(0~3)의 EPD (원소 i 의 칸 = epd(k) + i)."""
        return _compat.eudarray_epd(self._arrs[k])

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
        return tuple(_Cell(self.epd(k) + i) for k in range(4))

    # --- 읽기·쓰기 ---
    def get(self, i):
        """원소 i 를 새 Int128 사본으로 읽는다(제자리 연산 금지 표시). 비용: f_dwread_epd × 4 (상수 칸은 복사 한 줄)."""
        i = self._index(i, "Int128Array.get")
        if not isinstance(i, int):
            idx = EUDVariable()  # 받은 값이 rvalue 면 eudplib 색인 읽기가 제자리에서 고친다 (3.9) → 복사
            idx << i
            i = idx
        x = Int128.wrap(*(self._arrs[k][i] for k in range(4)))
        x._elem = True
        return x

    def __getitem__(self, i):
        return self.get(i)

    def set(self, i, value):
        """원소 i ← value (128비트 피연산자). 비용: 상수 칸 = 호출 1, 변수 칸 = eudplib 쓰기 4번."""
        i = self._index(i, "Int128Array.set")
        vw = _words(value, "Int128Array.set")
        if isinstance(i, int):
            _assign4(self._cells(i), vw)
            return
        idx = EUDVariable()
        idx << i
        for k in range(4):
            self._arrs[k][idx] = vw[k]

    def __setitem__(self, i, value):
        self.set(i, value)

    def _modify(self, i, fn):
        x = self.get(i)
        x._elem = False
        fn(x._w)
        self.set(i, x)

    def iadd(self, i, value):
        """원소 i += value (128비트 wrap). epScript `arr[i] += v;` (iadditem)."""
        i = self._index(i, "Int128Array.iadd")
        p = _words(value, "Int128Array.iadd")
        k = _const4(p)
        if isinstance(i, int) and k is not None:
            _addk_emit(self._cells(i), k)
            return
        self._modify(i, lambda w: _iadd4(w, p))

    def isub(self, i, value):
        """원소 i −= value (128비트 **wrap**). epScript `arr[i] -= v;` (isubitem)."""
        i = self._index(i, "Int128Array.isub")
        p = _words(value, "Int128Array.isub")
        k = _const4(p)
        if isinstance(i, int) and k is not None:
            _addk_emit(self._cells(i), (-k) & M128)
            return
        self._modify(i, lambda w: _isub4(w, p))

    def isub_sat(self, i, value):
        """원소 i ← max(원소 − value, 0) (**포화**, 128비트 전체 기준). epScript `arr.isub_sat(i, v);`."""
        i = self._index(i, "Int128Array.isub_sat")
        p = _words(value, "Int128Array.isub_sat")
        k = _const4(p)
        if isinstance(i, int) and k is not None:
            _ssubk_emit(self._cells(i), k)
            return
        self._modify(i, lambda w: _isub_sat4(w, p))

    def imul(self, i, value):
        """원소 i ← 원소 × value (128비트 wrap). epScript `arr[i] *= v;` (imulitem)."""
        i = self._index(i, "Int128Array.imul")
        p = _words(value, "Int128Array.imul")
        self._modify(i, lambda w: _mul_into4(w, w, p))

    def idiv(self, i, value):
        """원소 i ← 원소 // value (부호 없음). epScript `arr[i] /= v;` (ifloordivitem)."""
        i = self._index(i, "Int128Array.idiv")
        p = _words(value, "Int128Array.idiv")
        self._modify(i, lambda w: _divmod_into4(w, None, w, p))

    def imod(self, i, value):
        """원소 i ← 원소 % value (부호 없음). epScript `arr[i] %= v;` (imoditem)."""
        i = self._index(i, "Int128Array.imod")
        p = _words(value, "Int128Array.imod")
        self._modify(i, lambda w: _divmod_into4(None, w, w, p))

    iadditem = iadd
    isubitem = isub
    isubtractitem = isub_sat  # eudplib 관례: 이름에 Subtract = 포화 (S8 7.1-3)
    imulitem = imul
    ifloordivitem = idiv
    imoditem = imod

    # --- 비교 (epScript arr[i] op v → _ARRC → *item) ---
    def _cmpitem(self, op, i, value):
        fname = "Int128Array." + op
        i = self._index(i, fname)
        if isinstance(i, int):
            pv = _words(value, fname)
            if op in _MIRROR:
                o, pa, pb = _MIRROR[op], pv, self._cells(i)
            else:
                o, pa, pb = op, self._cells(i), pv
            return _compare_words(o, pa, pb)
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
