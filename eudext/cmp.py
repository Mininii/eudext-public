"""안전 비교와 부호 있는 비교 (DESIGN 4.2, 3.4, 3.5 비교 절).

32비트 비교를 **모든 경계에서 정확하게** 돌려준다. 부호 없는 비교 6종(`ge`·`le`·`gt`·`lt`·`eq`·`ne`),
부호 있는 비교 4종(`sge`·`sle`·`sgt`·`slt`), 구간 검사(`between`), 부호 확장 읽기(`f_wread_signed`·`f_bread_signed`).

    from eudext import cmp
    if EUDIf()(cmp.slt(hp, 0)): ...                    # 파이썬
    if (cmp.slt(hp, 0)) { ... }                        // epScript (import eudext.cmp as cmp;)
    return cmp.lt(a, b) ? 1 : 0;                       // epScript 에서 조건을 값으로 돌려줄 때

## 피연산자

| 종류 | 예 | 처리 |
|---|---|---|
| 정수 상수 | `5`, `-1`, `0xFFFFFFFF` | 32비트로 줄인다(−2³¹ ≤ k < 2³², 음수는 2의 보수). 부호 없는 함수에서 `-1` = `0xFFFFFFFF` |
| 주소식 상수 | `EPD(…)`, `Forward` | 값 칸에 바로 넣을 수 있으면 넣고, 아니면 임시 변수에 옮긴다(트리거 +1) |
| `EUDVariable` | `v`, `arr[i]` 결과 | 조건으로 읽고, 값을 조건 칸에 채울 수 있다 |
| 읽기 전용 칸 | `EUDLightVariable`, (WP2) `Cell` | 조건으로만 읽는다. 채워야 하면 다른 쪽을 채우거나 조건 트리거(자기 칸 깃발)를 쓴다 |

`EUDLightBool` 은 받지 않는다(값이 비트 하나다 — `IsSet()` 을 쓴다).
eudplib 연산자와 다른 점: eudplib 0.81 은 음수 상수를 연산자마다 다르게 읽는다(`x < -1` 은 Never, `x <= -1` 은 늘 참).
cmp 는 모든 함수에서 2³² 나머지로 읽는다.

## 돌려주는 것 (DESIGN 3.4)

- 조건이 하나면 **새 `Condition`**, 여럿이면 **조건 목록(AND)** 이다. 상수끼리는 `Always()`/`Never()`.
- 앞 계산(조건 칸 채우기·깃발 트리거)은 **부르는 순간** 낸다. 그래서
  1. 돌려받은 조건은 **꼭 한 번** 트리거에 놓는다(놓지 않으면 빌드 때 `Orphan condition` 오류).
  2. 값은 부른 자리의 값이다. 루프 조건은 `EUDWhile()(cmp.lt(i, n))` 처럼 **조건 자리에서 부른다**
     (`c = cmp.lt(i, n)` 을 루프 밖에서 만들어 두면 첫 값만 본다).
  3. `RawTrigger(conditions=…)` 에도 넣을 수 있다(조건 필드가 모두 상수식).
- 값 칸을 실행 중에 채우는 조건은 amount 자리에 `Forward` 를 둬서 eudplib 이 **제자리 부정(negate)을 하지 않게** 했다.
  (`EUDNot`·`EUDSCAnd(neg=True)` 는 분기로 처리한다 — 결과는 맞고 트리거가 조금 는다.)
  자기 칸 깃발 조건(`[자기 칸 ≥ 1]`)과 상수 조건은 제자리 부정이 된다.
- epScript: `a < b` 는 `a >= b` 의 부정으로 번역되지만 `cmp.lt(a, b)` 는 함수 호출이라 그대로 불린다.
  `return cmp.lt(a, b);`·`var r = cmp.lt(a, b);` 는 빌드 오류 → `? 1 : 0` 을 쓴다.

## 알고리즘 (비용은 docs/COSTS.md, 2026-09-16 측정)

- 상수 비교: 구간 [lo, hi] 로 바꿔 `[x ≥ lo]`·`[x ≤ hi]` 조건 목록(트리거 0). 부호 있는 구간은 부호가 같으면
  그대로, 0 을 사이에 두면 "틈 [hi+1, lo−1] 밖" 이 된다(OR).
  - OR 은 `EUDVariable` 이면 `자기 칸 ← x − 틈 시작` 한 번 채우고 `[자기 칸 ≥ 틈 길이]` (트리거 1, 조건 하나, 제자리 부정 됨).
    DESIGN 초안의 EUDLightBool(트리거 2)보다 트리거가 하나 적다.
  - 읽기 전용 칸이면 자기 칸 깃발: `깃발 ← 1`, `[틈 안] → 깃발 ← 0` (트리거 2, 조건 `[깃발 ≥ 1]` 을 돌려줌).
- 변수끼리(부호 없음): 한쪽 값을 조건의 amount 칸에 채운다(`[a ≥ b]` = 채우기 트리거 1 / 실행 2).
  `a > b` = `[a ≥ b+1] ∧ [b ≤ 0xFFFFFFFE]`(DPS 이식판 a7aad90 "TT 비교 계획"). `a ≠ b` = `자기 칸 ← ~b + a`,
  `[자기 칸 ≤ 0xFFFFFFFE]`(실행 3, 제자리 부정 됨). eudplib 0.81 연산자(`<` 실행 3, `!=` 호출 2)보다 적다.
- 변수끼리(부호 있음): 조건 하나의 두 칸(비트마스크 칸·amount 칸)에 `a+2³¹`, `b+2³¹` 을 채우고 `[칸0 ≥ 칸8]`.
  `>` 는 칸8 에 `b+2³¹+1` 을 넣고 `[칸8 ≥ 1]` 을 덧붙인다(b = 2³¹−1 이면 0 으로 돈다). 임시 변수 없음, 실행 3.
  한쪽이 읽기 전용 칸이면 부호 없는 비교 + 부호 보정 트리거 2개로 깃발을 만든다.

출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/core.py:723` c_ge~c_eq, `eud/ctrig/tlib.py:171` flip,
`tlib.py:390` cmp32·`tlib.py:204~` 비교 계획(원자·채우기·부정 스위치), `core.py:376` pre_fill;
eudplib 0.81 `core/variable/eudv.py:589` `__lt__`(조건 첫 칸을 스스로 읽는 방식). CtrigAsm TT `iAtLeast` 계열, `f_SHRead`.
"""

import operator

from eudplib import (
    EPD,
    Add,
    Always,
    AtLeast,
    AtMost,
    Condition,
    EUDLightBool,
    EUDVariable,
    Exactly,
    MemoryEPD,
    Never,
    RawTrigger,
    SetMemoryEPD,
    SetTo,
    Subtract,
    f_bread_epd,
    f_dwread_epd,
    f_wread_epd,
    unProxy,
)

from eudext import _compat
from eudext._parts import Plan as _Plan
from eudext._parts import flag_cond as _flag
from eudext._parts import placeholder as _ph
from eudext._parts import selfcond as _selfcond
from eudext.errors import fail

M32 = 0xFFFFFFFF
SIGN = 0x80000000
SMAX = 0x7FFFFFFF

__all__ = [
    "between",
    "bread_signed",
    "eq",
    "f_between",
    "f_bread_signed",
    "f_eq",
    "f_ge",
    "f_gt",
    "f_le",
    "f_lt",
    "f_ne",
    "f_sge",
    "f_sgt",
    "f_sle",
    "f_slt",
    "f_wread_signed",
    "ge",
    "gt",
    "le",
    "lt",
    "ne",
    "sge",
    "sgt",
    "sle",
    "slt",
    "wread_signed",
]

# 피연산자 종류
_K = "상수"  # 정수 상수 (32비트로 줄인 값)
_E = "주소식"  # 정수가 아닌 상수식
_V = "변수"  # EUDVariable: 읽기 + 채우기 원천
_M = "칸"  # 읽기 전용 값 칸 (EUDLightVariable 등)

_MIRROR = {
    "ge": "le",
    "le": "ge",
    "gt": "lt",
    "lt": "gt",
    "eq": "eq",
    "ne": "ne",
    "sge": "sle",
    "sle": "sge",
    "sgt": "slt",
    "slt": "sgt",
}
_PYOP = {
    "ge": operator.ge,
    "le": operator.le,
    "gt": operator.gt,
    "lt": operator.lt,
    "eq": operator.eq,
    "ne": operator.ne,
}
_REFLEXIVE = {"ge", "le", "eq", "sge", "sle"}


def _s32(k):
    return k - (1 << 32) if k & SIGN else k


# ---------------------------------------------------------------------------------------------
# 피연산자 분류
# ---------------------------------------------------------------------------------------------


def _classify(x, fname, what):
    x = unProxy(x)
    if isinstance(x, bool):
        return _K, int(x)
    if isinstance(x, int):
        if not -(1 << 31) <= x < (1 << 32):
            fail("%s: %s 상수 %d 는 32비트 범위(−2^31 ~ 2^32−1) 밖입니다", fname, what, x)
        return _K, x & M32
    if isinstance(x, EUDLightBool):
        fail("%s: %s 에 EUDLightBool 은 넣을 수 없습니다 (IsSet()/IsCleared() 를 쓰세요)", fname, what)
    if isinstance(x, Condition):
        fail("%s: %s 에 조건(Condition)은 넣을 수 없습니다 — 값을 넣으세요", fname, what)
    if _compat.is_var(x):
        return _V, x
    if _compat.is_varbase(x):
        return _M, x
    if x is not None and _compat.is_const(x):
        return _E, x
    if hasattr(x, "getValueAddr"):
        return _M, x
    fail("%s: %s 는 정수·EUDVariable·EUDLightVariable 이어야 합니다 (%r)", fname, what, x)
    return None  # fail 은 돌아오지 않는다


def _cell(x):
    """읽을 수 있는 피연산자(변수·칸)의 값 칸 EPD."""
    return EPD(x.getValueAddr())


def _rd(x, cmp_, amount):
    return MemoryEPD(_cell(x), cmp_, amount)


def _tmp(x):
    """상수식·칸을 새 EUDVariable 로 옮긴다. 상수식 = 트리거 1, 칸 = `f_dwread_epd`."""
    kind, v = x
    t = EUDVariable()
    if kind == _M:
        t << f_dwread_epd(_cell(v))
    else:
        t << v
    return (_V, t)


# ---------------------------------------------------------------------------------------------
# 상수와의 비교 → 구간
# ---------------------------------------------------------------------------------------------


def _urange(x, lo, hi):
    """x ∈ [lo, hi] (부호 없음, x 는 읽을 수 있음) → 조건 목록."""
    if lo > hi:
        return [Never()]
    if lo == hi:
        return [_rd(x, Exactly, lo)]
    out = []
    if lo > 0:
        out.append(_rd(x, AtLeast, lo))
    if hi < M32:
        out.append(_rd(x, AtMost, hi))
    return out or [Always()]


def _unot(plan, x, kx, g1, g2):
    """x ∉ [g1, g2] (부호 없음) → 조건 목록. OR 이면 변수는 자기 칸 뺄셈, 칸은 깃발 트리거."""
    if g1 > g2:
        return [Always()]
    if g1 == 0 and g2 == M32:
        return [Never()]
    if g1 == 0:
        return [_rd(x, AtLeast, g2 + 1)]
    if g2 == M32:
        return [_rd(x, AtMost, g1 - 1)]
    if kx == _V:
        # 칸 ← x − g1 (wrap). x ∈ [g1, g2] ⇔ 칸 ≤ g2 − g1
        c = _selfcond(AtLeast, g2 - g1 + 1)
        plan.fill(EPD(c), x, -g1)
        return [c]
    k, kepd = _flag(plan, 1)
    plan.trig(_urange(x, g1, g2), [SetMemoryEPD(kepd, SetTo, 0)])
    return [k]


def _range(plan, x, kx, lo, hi, signed):
    """x ∈ [lo, hi] (lo, hi 는 32비트 상수 — signed 면 부호 있는 값으로 읽음) → 조건 목록."""
    if not signed:
        return _urange(x, lo, hi)
    slo, shi = _s32(lo), _s32(hi)
    if slo > shi:
        return [Never()]
    if slo >= 0 or shi < 0:
        return _urange(x, lo, hi)
    # 0 을 사이에 둔 구간 = 틈 [shi+1, slo−1] (부호 없는 값) 밖
    return _unot(plan, x, kx, shi + 1, lo - 1)


def _const_interval(op, k):
    """x op k 를 구간 (lo, hi, signed) 로 바꾼다. ne 는 구간 밖이라 None (호출하는 쪽이 _unot 으로)."""
    if op == "ne":
        return None
    if op == "eq":
        return k, k, False
    if op == "ge":
        return k, M32, False
    if op == "le":
        return 0, k, False
    if op == "gt":
        return (k + 1, M32, False) if k < M32 else (1, 0, False)
    if op == "lt":
        return (0, k - 1, False) if k > 0 else (1, 0, False)
    sk = _s32(k)
    if op == "sge":
        return k, SMAX, True
    if op == "sle":
        return SIGN, k, True
    if op == "sgt":
        return ((sk + 1) & M32, SMAX, True) if sk < SMAX else (0, SIGN, True)  # 빈 구간(0 > −2^31)
    # slt
    return (SIGN, (sk - 1) & M32, True) if sk > -(1 << 31) else (0, SIGN, True)


# ---------------------------------------------------------------------------------------------
# 변수끼리
# ---------------------------------------------------------------------------------------------


def _uvv(plan, op, x, y):
    """부호 없는 x op y (op: ge/gt/eq/ne, x·y 는 변수 또는 칸, 서로 다른 객체) → 조건 목록."""
    kx, vx = x
    ky, vy = y
    if kx == _M and ky == _M:
        y = _tmp(y)
        ky, vy = y
    if op in ("ge", "eq"):
        cmp_ = AtLeast if op == "ge" else Exactly
        if ky == _V:
            c = _rd(vx, cmp_, _ph())  # [x op 채운 y]
            plan.fill(EPD(c) + 2, vy)
        else:
            c = _rd(vy, AtMost if op == "ge" else Exactly, _ph())  # [y ≤ 채운 x]
            plan.fill(EPD(c) + 2, vx)
        return [c]
    if op == "gt":
        if ky == _V:
            c = _rd(vx, AtLeast, _ph())  # [x ≥ y+1] ∧ [y ≠ 0xFFFFFFFF]
            plan.fill(EPD(c) + 2, vy, 1)
            return [c, _rd(vy, AtMost, M32 - 1)]
        c = _rd(vy, AtMost, _ph())  # [y ≤ x−1] ∧ [x ≠ 0]
        plan.fill(EPD(c) + 2, vx, M32)
        return [c, _rd(vx, AtLeast, 1)]
    # ne
    if kx == _V and ky == _V:
        c = _selfcond(AtMost, M32 - 1)  # 칸 = ~y + x = x − y − 1 (wrap). x = y ⇔ 칸 = 0xFFFFFFFF
        plan.put(EPD(c), M32)
        plan.op(EPD(c), Subtract, vy)
        plan.op(EPD(c), Add, vx)
        return [c]
    if kx == _V:
        vx, vy = vy, vx  # vx = 칸, vy = 변수
    k, kepd = _flag(plan, 1)
    c = _rd(vx, Exactly, _ph())
    plan.fill(EPD(c) + 2, vy)
    plan.trig([c], [SetMemoryEPD(kepd, SetTo, 0)])
    return [k]


def _svv(plan, op, x, y):
    """부호 있는 x op y (op: sge/sgt, x·y 는 변수 또는 칸, 서로 다른 객체) → 조건 목록."""
    kx, vx = x
    ky, vy = y
    if kx == _M and ky == _M:
        y = _tmp(y)
        ky, vy = y
    if kx == _V and ky == _V:
        c = _selfcond(AtLeast, _ph())  # [x+2^31 ≥ y+2^31 (+1)]
        plan.fill(EPD(c), vx, SIGN)
        if op == "sge":
            plan.fill(EPD(c) + 2, vy, SIGN)
            return [c]
        plan.fill(EPD(c) + 2, vy, SIGN + 1)
        return [c, MemoryEPD(EPD(c) + 2, AtLeast, 1)]  # y = 2^31−1 이면 칸이 0 으로 돈다 → 거짓
    # 한쪽이 칸: 부호 없는 비교 + 부호 보정 (x 음수·y 양수 → 거짓, x 양수·y 음수 → 참)
    k, kepd = _flag(plan, 0)
    u = _uvv(plan, op[1:], x, y)
    plan.trig(u, [SetMemoryEPD(kepd, SetTo, 1)])
    plan.trig([_rd(vx, AtLeast, SIGN), _rd(vy, AtMost, SMAX)], [SetMemoryEPD(kepd, SetTo, 0)])
    plan.trig([_rd(vx, AtMost, SMAX), _rd(vy, AtLeast, SIGN)], [SetMemoryEPD(kepd, SetTo, 1)])
    return [k]


# ---------------------------------------------------------------------------------------------
# 공통 진입
# ---------------------------------------------------------------------------------------------


def _fold(op, a, b):
    if op[0] == "s":
        a, b, op = _s32(a), _s32(b), op[1:]
    return Always() if _PYOP[op](a, b) else Never()


def _build(plan, op, a, b):
    """a op b → 조건 목록. a, b 는 (종류, 값)."""
    ka, va = a
    kb, vb = b
    if ka == _K and kb == _K:
        return [_fold(op, va, vb)]
    if ka != _K and kb != _K and va is vb:
        return [Always() if op in _REFLEXIVE else Never()]
    if ka == _K:
        op, a, b = _MIRROR[op], b, a
        ka, va = a
        kb, vb = b
    # 이제 a 는 상수가 아니다
    if kb == _K:
        if ka == _E:
            a = _tmp(a)
            ka, va = a
        iv = _const_interval(op, vb)
        if iv is None:
            return _unot(plan, va, ka, vb, vb)
        return _range(plan, va, ka, iv[0], iv[1], iv[2])
    # 변수끼리: le/lt/sle/slt 는 뒤집는다
    if op in ("le", "lt", "sle", "slt"):
        op, a, b = _MIRROR[op], b, a
        ka, va = a
        kb, vb = b
    if op in ("ge", "eq") and (ka == _E or kb == _E):
        if ka == _E and kb == _E:
            a = _tmp(a)
            ka, va = a
        if kb == _E:
            return [_rd(va, AtLeast if op == "ge" else Exactly, vb)]
        return [_rd(vb, AtMost if op == "ge" else Exactly, va)]
    if op == "ne" and (ka == _E or kb == _E):
        if ka == _E and kb == _E:
            a = _tmp(a)
            ka, va = a
        if ka == _E:
            va, vb = vb, va
        k, kepd = _flag(plan, 1)
        plan.trig([_rd(va, Exactly, vb)], [SetMemoryEPD(kepd, SetTo, 0)])
        return [k]
    if ka == _E:
        a = _tmp(a)
    if kb == _E:
        b = _tmp(b)
    if op[0] == "s":
        return _svv(plan, op, a, b)
    return _uvv(plan, op, a, b)


def _ret(conds):
    return conds[0] if len(conds) == 1 else conds


def _compare(op, a, b, fname):
    a = _classify(a, fname, "a")
    b = _classify(b, fname, "b")
    plan = _Plan()
    conds = _build(plan, op, a, b)
    plan.emit()
    return _ret(conds)


# ---------------------------------------------------------------------------------------------
# 공개 함수: 부호 없음
# ---------------------------------------------------------------------------------------------


def f_ge(a, b):
    """a ≥ b (부호 없는 32비트). 모든 경계에서 정확하다.

    인자: a, b — 정수 상수(−2^31 ~ 2^32−1, 음수는 2의 보수), 주소식, EUDVariable, EUDLightVariable
    반환: 새 Condition (변수끼리도 조건 하나. 값 칸 채우기라 제자리 부정은 안 됨 — EUDNot 은 분기로 처리)
    비용: 상수 = 트리거 0 / 실행 0. 변수끼리·칸과 변수 = 호출 1 / 실행 2. 칸끼리 = 호출 3 / 실행 39(한쪽을 f_dwread_epd 로 읽음)
          (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음 (칸끼리일 때 f_dwread_epd 가 잠깐 옮기고 되돌림)
    로컬: 공유 안전 (넣은 값이 로컬 값이면 결과도 로컬)
    epScript: `if (cmp.ge(a, b)) { … }` · `return cmp.ge(a, b) ? 1 : 0;`
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/core.py:723 c_ge, tlib.py:204 비교 계획("vv" 원자 채우기)
    """
    return _compare("ge", a, b, "cmp.ge")


def f_le(a, b):
    """a ≤ b (부호 없는 32비트). 모든 경계에서 정확하다.

    인자: a, b — `f_ge` 와 같음
    반환: 새 Condition (`f_ge(b, a)` 와 같은 모양)
    비용: 상수 = 트리거 0. 변수끼리 = 호출 1 / 실행 2 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `while (cmp.le(i, n)) { … }`
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/core.py:737 c_le
    """
    return _compare("le", a, b, "cmp.le")


def f_gt(a, b):
    """a > b (부호 없는 32비트). `gt(x, 0xFFFFFFFF)` = Never, 변수 b = 0xFFFFFFFF 도 정확하다.

    인자: a, b — `f_ge` 와 같음
    반환: 상수 = 새 Condition. 변수끼리 = 조건 목록 2개 `[a ≥ b+1(채움)] ∧ [b ≤ 0xFFFFFFFE]`
    비용: 상수 = 트리거 0. 변수끼리 = 호출 1 / 실행 2 (eudplib 0.81 `a > b` 는 실행 3) (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cmp.gt(a, b)) { … }`
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/core.py:741 c_gt, tlib.py:224 _gt / 204 "gt" 원자
    """
    return _compare("gt", a, b, "cmp.gt")


def f_lt(a, b):
    """a < b (부호 없는 32비트). `lt(x, 0)` = Never, 변수 b = 0 도 정확하다.

    인자: a, b — `f_ge` 와 같음
    반환: 상수 = 새 Condition. 변수끼리 = 조건 목록 2개 (`f_gt(b, a)`)
    비용: 상수 = 트리거 0. 변수끼리 = 호출 1 / 실행 2 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cmp.lt(a, b)) { … }` · `return cmp.lt(a, b) ? 1 : 0;` (`return a < b;` 는 빌드 오류)
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/core.py:761 c_lt
    """
    return _compare("lt", a, b, "cmp.lt")


def f_eq(a, b):
    """a = b (32비트).

    인자: a, b — `f_ge` 와 같음
    반환: 새 Condition (변수끼리는 값 칸 채우기 — 제자리 부정 안 됨)
    비용: 상수 = 트리거 0. 변수끼리 = 호출 1 / 실행 2 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cmp.eq(a, b)) { … }`
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/core.py:765 c_eq
    """
    return _compare("eq", a, b, "cmp.eq")


def f_ne(a, b):
    """a ≠ b (32비트).

    인자: a, b — `f_ge` 와 같음
    반환: 새 Condition. 상수 k 가 0·0xFFFFFFFF 면 조건 하나(트리거 0). 그 밖의 상수·변수끼리는 앞 계산이 있다:
          변수 = 자기 칸 뺄셈 `[칸 ≥ 1]`/`[칸 ≤ 0xFFFFFFFE]`(제자리 부정 됨), 칸(EUDLightVariable) = 자기 칸 깃발
    비용: 상수 = 트리거 0~1 / 실행 0~2 (칸이면 2 / 2). 변수끼리 = 호출 1 / 실행 3. 칸·변수 = 호출 2 / 실행 3
          (eudplib 0.81 `a != b` 는 호출 2 / 실행 4) (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cmp.ne(a, b)) { … }`
    출처: 새로 작성 (eudplib 0.81 `__lt__` 의 자기 칸 방식을 wrap 뺄셈에 적용)
    """
    return _compare("ne", a, b, "cmp.ne")


# ---------------------------------------------------------------------------------------------
# 공개 함수: 부호 있음
# ---------------------------------------------------------------------------------------------


def f_sge(a, b):
    """a ≥ b (부호 있는 32비트: 0x80000000 ~ 0xFFFFFFFF 는 음수).

    인자: a, b — `f_ge` 와 같음 (음수 상수를 그대로 써도 된다: `sge(x, -5)`)
    반환: 상수 k ≥ 0 = 조건 목록 `[x ≥ k] ∧ [x ≤ 0x7FFFFFFF]`(트리거 0). 상수 k < 0 = OR 이라 앞 계산 1개가 있는
          새 Condition(변수) 또는 자기 칸 깃발(칸). 변수끼리 = 새 Condition(두 칸 채우기)
    비용: 상수 = 트리거 0~2 / 실행 0~2. 변수끼리 = 호출 1 / 실행 3. 칸·변수 = 호출 4 / 실행 5 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cmp.sge(hp, -100)) { … }`
    출처: CtrigAsm TT `iAtLeast`, DPS_Enhance eudplib-port a7aad90 eud/ctrig/tlib.py:171 flip·390 cmp32
    """
    return _compare("sge", a, b, "cmp.sge")


def f_sle(a, b):
    """a ≤ b (부호 있는 32비트).

    인자: a, b — `f_ge` 와 같음
    반환: `f_sge(b, a)` 와 같은 모양 (상수 k < 0 = 조건 목록, k ≥ 0 = 앞 계산 1개)
    비용: 상수 = 트리거 0~2. 변수끼리 = 호출 1 / 실행 3 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cmp.sle(dx, 0)) { … }`
    출처: CtrigAsm TT `iAtMost`, DPS_Enhance eudplib-port a7aad90 eud/ctrig/tlib.py:390 cmp32
    """
    return _compare("sle", a, b, "cmp.sle")


def f_sgt(a, b):
    """a > b (부호 있는 32비트). `sgt(x, 0x7FFFFFFF)` = Never.

    인자: a, b — `f_ge` 와 같음
    반환: 상수 = `f_sge(a, b+1)` 모양. 변수끼리 = 조건 목록 2개 `[칸0 ≥ 칸8] ∧ [칸8 ≥ 1]`
    비용: 상수 = 트리거 0~2. 변수끼리 = 호출 1 / 실행 3 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cmp.sgt(dy, 0)) { … }`
    출처: CtrigAsm TT `iAbove`, DPS_Enhance eudplib-port a7aad90 eud/ctrig/tlib.py:390 cmp32
    """
    return _compare("sgt", a, b, "cmp.sgt")


def f_slt(a, b):
    """a < b (부호 있는 32비트). `slt(x, -0x80000000)` = Never.

    인자: a, b — `f_ge` 와 같음
    반환: `f_sgt(b, a)` 와 같은 모양
    비용: 상수 = 트리거 0~2. 변수끼리 = 호출 1 / 실행 3 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cmp.slt(hp, 0)) { … }` · `return cmp.slt(a, b) ? 1 : 0;`
    출처: CtrigAsm TT `iBelow`, DPS_Enhance eudplib-port a7aad90 eud/ctrig/tlib.py:390 cmp32
    """
    return _compare("slt", a, b, "cmp.slt")


# ---------------------------------------------------------------------------------------------
# 구간
# ---------------------------------------------------------------------------------------------


def _drop_always(conds):
    out = [c for c in conds if c.fields[5] != 22]
    return out or [Always()]


def f_between(x, lo, hi, signed=False):
    """lo ≤ x ≤ hi (양 끝 포함). signed=True 면 부호 있는 32비트로 비교한다.

    lo > hi 면 늘 거짓. 부호 있는 상수 구간이 0 을 사이에 두면 OR 이라 앞 계산이 하나 든다.
    인자: x, lo, hi — `f_ge` 의 피연산자와 같음. signed(bool, 컴파일 시점)
    반환: 조건 목록(AND) 또는 새 Condition
    비용: 상수 구간 = 트리거 0 (부호 있음·0 걸침 = 변수 1 / 칸 2). 변수 x + 변수 끝 두 개 = 호출 1 / 실행 3(부호 없음)·4(부호 있음)
          (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cmp.between(dx, -16, 16, signed=True)) { … }`
    출처: 새로 작성 (DPS_Enhance eudplib-port a7aad90 eud/ctrig/tlib.py:258 _simplify 의 구간 합치기와 같은 생각)
    """
    fname = "cmp.between"
    if not isinstance(signed, bool):
        fail("%s: signed 는 True/False 여야 합니다 (%r)", fname, signed)
    x = _classify(x, fname, "x")
    lo = _classify(lo, fname, "lo")
    hi = _classify(hi, fname, "hi")
    ge_op, le_op = ("sge", "sle") if signed else ("ge", "le")
    const_bounds = lo[0] == _K and hi[0] == _K
    distinct = x[1] is not lo[1] and x[1] is not hi[1] and lo[1] is not hi[1]
    fillable = lo[0] in (_V, _E) and hi[0] in (_V, _E)
    plan = _Plan()
    if const_bounds and x[0] != _K:
        if x[0] == _E:
            x = _tmp(x)
        conds = _range(plan, x[1], x[0], lo[1], hi[1], signed)
    elif signed and x[0] == _V and fillable and distinct:
        conds = _sbetween_vars(plan, x[1], lo, hi)
    elif lo[0] != _K and lo[1] is hi[1]:
        conds = _build(plan, "eq", x, lo)  # lo, hi 가 같은 객체
    else:
        conds = _drop_always(_build(plan, ge_op, x, lo) + _build(plan, le_op, x, hi))
    plan.emit()
    return _ret(conds)


def _sbetween_vars(plan, x, lo, hi):
    """부호 있는 변수 구간: x+2^31 을 한 칸에만 채우고 두 조건이 같이 읽는다 (호출 1 / 실행 4)."""
    if lo[0] == _E:
        lo = _tmp(lo)
    if hi[0] == _E:
        hi = _tmp(hi)
    c1 = _selfcond(AtLeast, _ph())  # [x+2^31 ≥ lo+2^31]
    plan.fill(EPD(c1), x, SIGN)
    plan.fill(EPD(c1) + 2, lo[1], SIGN)
    c2 = MemoryEPD(EPD(c1), AtMost, _ph())  # [x+2^31 ≤ hi+2^31]
    plan.fill(EPD(c2) + 2, hi[1], SIGN)
    return [c1, c2]


# ---------------------------------------------------------------------------------------------
# 부호 확장 읽기
# ---------------------------------------------------------------------------------------------


def _check_ret(fname, ret):
    if ret is None:
        return None
    if not isinstance(ret, (list, tuple)) or len(ret) != 1 or not _compat.is_var(ret[0]):
        fail("%s: ret 는 [EUDVariable] 이어야 합니다 (%r)", fname, ret)
    return [unProxy(ret[0])]


def f_wread_signed(epd, subp=0, *, ret=None):
    """EPD 칸의 subp 번째 바이트부터 16비트를 읽어 부호 확장한 32비트 값(−32768 ~ 32767)을 돌려준다.

    eudplib `f_wread_epd(epd, subp)` 뒤에 `값 ≥ 0x8000 이면 += 0xFFFF0000` 트리거 하나를 붙인다.
    CtrigAsm `f_SHRead` 대체: 원본은 dword 의 하위 16비트와 비트 31 로 부호를 정했다(32비트로 저장한 좌표 표).
    그런 표를 eudplib 으로 옮겼다면 `f_dwread_epd` 로 읽으면 된다 — 이 함수는 진짜 16비트 필드(i16)용이다.
    인자: epd(상수·변수), subp(0~3, 상수·변수 — 3 이면 다음 칸 바이트 0 까지), ret([EUDVariable], 선택)
    반환: EUDVariable (ret 를 주면 그 변수)
    비용: f_wread_epd + 호출 1 / 실행 1 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음 (f_wread_epd 가 잠깐 옮기고 캐시로 되돌림)
    로컬: 공유 안전 (읽는 칸이 로컬 값이면 결과도 로컬)
    epScript: `const dx = cmp.wread_signed(epd, 2);` (→ `cmp.f_wread_signed`)
    출처: CtrigAsm `f_SHRead`(CtrigAsm v5.5.lua:35812), DPS_Enhance eudplib-port a7aad90 eud/ctrig/arith.py:540
    """
    ret = _check_ret("cmp.f_wread_signed", ret)
    r = f_wread_epd(epd, subp, ret=ret)
    RawTrigger(conditions=r.AtLeast(0x8000), actions=r.AddNumber(0xFFFF0000))
    return r


def f_bread_signed(epd, subp=0, *, ret=None):
    """EPD 칸의 subp 번째 바이트(8비트)를 읽어 부호 확장한 32비트 값(−128 ~ 127)을 돌려준다.

    인자: epd(상수·변수), subp(0~3, 상수·변수), ret([EUDVariable], 선택)
    반환: EUDVariable (ret 를 주면 그 변수)
    비용: f_bread_epd + 호출 1 / 실행 1 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const b = cmp.bread_signed(epd, 0);` (→ `cmp.f_bread_signed`)
    출처: 새로 작성 (`f_wread_signed` 와 같은 방식)
    """
    ret = _check_ret("cmp.f_bread_signed", ret)
    r = f_bread_epd(epd, subp, ret=ret)
    RawTrigger(conditions=r.AtLeast(0x80), actions=r.AddNumber(0xFFFFFF00))
    return r


# 파이썬 별칭 (DESIGN 3.1)
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
between = f_between
wread_signed = f_wread_signed
bread_signed = f_bread_signed
