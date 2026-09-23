"""삼각·정수 수학 — 결과 값까지 CtrigAsm 과 같은 lengthdir·회전·atan2, 부호 나눗셈, 정수 제곱근·로그 (DESIGN 4.5).

    from eudext import mathx as mx
    c, s = mx.lengthdir(r, a)              # (r·cos a, r·sin a) — CtrigAsm f_Lengthdir 와 같은 값
    rot = mx.Rotator(ang)                  # 고정각 회전 (각을 바꾸면 rot.set(새 각))
    x2, y2 = rot(x, y)                     # CtrigAsm CA_Rotate 와 같은 값 (항별 자르기)
    X, Y, Z = mx.rotate3d(x, y, xy, yz, zx)
    a = mx.atan2(dy, dx)                   # CtrigAsm f_Atan2 와 같은 값 (0 ~ cycle−1, 올림 성격)
    d = mx.atan2_sc(dy, dx)                # CtrigAsm f_Atan2X (SC 256 방향, 0 = 위쪽)
    d = mx.to_dir256(a)                    # 360 주기 각 → SC 256 방향
    q = mx.sdiv(a, b); m = mx.smod(a, b)   # 0 방향 부호 나눗셈 (0 나눗셈 정책 div0="eudplib"|"ctrig")
    v = mx.ratio(x, mul, div)              # x·mul/div 부호 있음 (CA_RatioXY)
    k = mx.isqrt(n); e = mx.ilog2(n)

epScript: `import eudext.mathx as mx;` → `const c, s = mx.lengthdir(r, a);`, `const rot = mx.Rotator(ang);`,
`const x2, y2 = rot(x, y);`, `rot.set(ang2);`, `var d = mx.atan2(dy, dx);` (함수 이름은 `f_` 가 붙어 번역된다 — 3.1).

## 각도 기준과 결과 (사용자 결정 D5 — 옵션 없음)

- 런타임 각도 0 = +x, y 가 아래로 커지므로 각이 늘면 화면에서 **시계 방향**. `cycle` 은 한 바퀴(4의 배수, 기본 360).
- lengthdir: 표 `T[i] = trunc(0x10000·sin(i·90/Q °))`(Q = cycle/4, T[30] = 32767), 결과 = `R·T ÷ 0x10000` 을
  **0 방향으로 자른 부호 나눗셈**(CiDiv). 곱은 32비트(R 범위 −32768 ~ 32767 에서 넘치지 않음, 그 밖은 원본처럼 한 바퀴 돈 값).
- 음수·cycle 이상 각은 `a mod cycle`(CtrigAsm: CiMod 뒤 음수면 +cycle — 파이썬 `%` 와 같다).
- 회전: `x' = lx.cos − ly.sin`, `y' = lx.sin + ly.cos`(lx = lengthdir(x, θ)) — 항마다 따로 잘라서 실수 회전과 최대 ±2 다르다.
- atan2: 사분면으로 나눠 |dy|·0x10000 ÷ |dx| 비율을 표 `A[i] = trunc(0x10000·tan(i·90/Q °))` 와 비교해
  `비율 ≤ A[i]` 인 첫 i(없으면 Q). tan 45° 표가 65535 라 (1, 1) → 46 (**올림 성격**). 입력 −32768 ~ 32767(그 밖은 원본처럼
  |dy|<<16 이 한 바퀴 돈 값). dx = 0 이면 비율 0xFFFFFFFF(dy = 0 이어도 → 90). 출력 0 ~ cycle−1.
- 표 값은 정확 반올림 sin/tan 으로 만든다(`mathx_tables` — 플랫폼 무관). eudplib `f_lengthdir`/`f_atan2` 는 음수 반지름·음수 각,
  반올림 표가 달라서 **쓰지 않는다**(R4b C5).
- 고정밀(`precise=True`, CtrigAsm LengthdirX): 표 칸 (l, k) = trunc(k·sin(l·90/Q °)) 를 파일 표(Db)로 싣고 |R| 의 하위
  15비트로 읽는다. **표 크기 (Q+1)×32768×4 바이트 — cycle 360 이면 11,927,552 바이트(11.9MB)**, 빌드 때 경고한다.
- 반지름을 줄인 고정밀(`precise=bits`, 정수 1~14): 각 열의 앞 2^bits 칸만 싣는다(칸 값은 원본 표와 같다). |R| < 2^bits 이면
  원본 고정밀과 **같은 값**, 그 밖이면 표 없는 lengthdir(아래 첫 줄의 식)로 계산한다. bits 13 이면 표 2,981,888 바이트.
  표가 거의 압축되지 않아 freeze 블록 테이블(SC:R 한도 4MiB)을 넘기 쉬운 맵에서 쓴다 (Memory_2, 2026-09-24).

## 0 나눗셈 (DESIGN 7절 D4 권장안)

- `div0="eudplib"`(기본): eudplib `f_div_towards_zero` 와 같다 — 몫 = a ≥ 0 이면 0xFFFFFFFF(−1), a < 0 이면 1, 나머지 = a.
  (부호 없는 f_div 의 "몫 전부 1, 나머지 = 피제수" 에 부호 보정을 한 값)
- `div0="ctrig"`: CtrigAsm `f_iDiv`/`f_iMod` 와 같다 — 몫 = a ≥ 0 이면 0x7FFFFFFF, a < 0 이면 0x80000000, 나머지 = a.
  (상수 0 으로 나누는 CtrigAsm `CiDiv(X, 0)` 은 ±1 이 되지만 이것은 따르지 않는다 — 상수·변수 제수 모두 f_iDiv 규칙)
- b ≠ 0 이면 두 정책 모두 0 방향 몫, 피제수 부호 나머지(C 방식)이고 −2³¹ ÷ −1 = −2³¹(wrap).

## 피연산자와 반환 (DESIGN 3.3)

- 인자: 정수 상수(−2³¹ ~ 2³²−1, 32비트로 읽는다), `EUDVariable`, 읽기 전용 값 칸(`EUDLightVariable`·`cell.Cell` — `f_dwread_epd` 로
  읽음, 실행 +36), 주소식(임시 변수로 복사). 실수·범위 밖 정수는 `EudextError`.
- **모두 상수면 파이썬 정수**(트리거 0): 부호 있는 결과(lengthdir·회전·sdiv·smod·ratio)는 음수 정수,
  atan2·to_dir256·isqrt·ilog2 는 0 이상 정수. `ret=[변수…]` 를 주면 그 변수에 넣는다(트리거 1).
- 변수가 있으면 EUDFunc 호출(여러 값이면 eudplib 관례대로 변수 튜플, `ret=` 가능).
  - 각이 상수: 각(정규화 값)마다 한 벌 본문(곱이 상수 액션이 된다).
  - 각이 변수: 주기·정밀도마다 **공유 본문 한 벌**(lengthdir·Rotator·rotate3d 가 같이 씀) + "마지막으로 준비한 각" 기억.
    같은 각이 이어지면 표 준비(실행 약 125)를 건너뛴다. 각이 다른 호출을 점마다 번갈아 하면 매번 준비한다 —
    그런 곳은 `Rotator(…, own=True)`·`rotate3d(…, own=True)` 로 전용 본문을 둔다(페이로드 약 +54KB·+150KB).
- 64비트·128비트, `Delta`(f_Diff), `Table`(CMathFunc)은 만들지 않았다(사용 0, DESIGN 0.2).

## 알고리즘 요약 (비용은 docs/COSTS.md "mathx (WP9)")

- lengthdir 빠른 길(|R| ≤ 32767): |R| 의 비트 15개마다 조건 트리거 하나가 `cos칸 += Tc·2^i`, `sin칸 += Ts·2^i` 를 더하고
  (각이 변수면 두 값을 준비 때 액션 값 칸에 써 둔다), `>> 16`(eudplib 시프트 트리거 1) 뒤 부호(R 부호 XOR 사분면 부호)를 뒤집는다.
  느린 길(|R| > 32767): 32비트 곱 + 부호 나눗셈(원본과 같은 넘침 값).
- 표 준비(변수 각): 정규화 → 사분면(트리거 4) → sin·cos 를 한 칸에 담은 표(`EUDVArray`, Q+1 칸) 읽기 → 두 값을 2배씩 늘리며 30칸에 쓰기.
- atan2: |dx| ≤ 65535 면 짧은 긴 나눗셈 사슬(제수 배수 L칸, 360 은 8칸) 하나를 세 번(정수 부분·소수 두 바이트).
  |dy| > 65535 는 원본 `<<16` 이 하위 16비트만 남기므로 같은 길, |dx| > 65535 만 32비트 나눗셈(DPS `div3232`, sdiv 와 공유).
  비율 → 각은 "A[i] < 비율 인 i 의 개수"(표가 단조라 '처음 참인 i' 와 같다)를 이진 결정 나무(버킷 6칸) + 버킷 안 셈으로.
  원본의 거친 8갈래 점프는 결과를 바꾸지 않는다(참조 구현으로 확인).
- isqrt: 두 비트씩 내리는 자릿수 방식(곱셈 없음), 앞쪽 0 쌍은 건너뛴다. ilog2: 2¹⁶ 로 가른 뒤 문턱 15개 세기.
- sdiv: 부호 떼기 → 부호 없는 나눗셈(변수 제수 = DPS 이식판 `div3232` — 같은 제수 표 재사용, 상수 제수 = 긴 나눗셈 사슬
  또는 시프트) → 부호 붙이기. ratio 의 곱은 절댓값 곱(eudplib 곱셈이 작은 쪽 비트만 돌게) 또는 eudplib 상수 곱.

## 주의

- CP: 바꾸지 않음(고정밀 표 읽기는 eudplib `f_dwread_epd` 가 CP 캐시를 되돌린다). 로컬: 공유 안전(입력이 로컬 값이면 결과도 로컬).
- eudplib 의 시프트(`>>=`, `<<=` 11 이상)·부호 반전(`ineg`)과 atan2 의 `<< 8` 액션(`_shl_acts`, eudplib 식 복사)은
  마스크 SetTo/Add/Subtract 를 쓴다(인게임 A-1 로 식 확인 중, C9-2 가 함께 본다).
- 공유 본문은 재진입하지 않는다(EUDFunc). 콜백이 없으므로 mathx 안에서는 문제가 없다.

출처: CtrigAsm v5.5 `f_Lengthdir`(CA:84377~84638), `f_Atan2`/`f_Atan2X`(CA:84640~85048), `CiDiv`(CA:25314), `CiMod`(CA:26882),
`f_iDiv`/`f_iMod`(CA:30465~31105), `f_Sqrt`(CA:84231), `f_Log2`(CA:85121), CB Paint v2.5 `CA_Rotate`/`CA_Rotate3D`/`CA_RatioXY`
(CBP:9718, 9865, 9883), DPS_Enhance eudplib-port a7aad90 `eud/ctrig/divide.py`(`_div3232`),
eudplib 0.81 `eudlib/mathf/div.py`(0 나눗셈 부호 규칙). 참조 구현: `tests/ref_mathx.py`.
"""

import functools
import math

from eudplib import (
    EPD,
    Add,
    AtMost,
    Db,
    EUDElse,
    EUDElseIf,
    EUDEndIf,
    EUDFunc,
    EUDIf,
    EUDJump,
    EUDJumpIf,
    EUDReturn,
    EUDVArray,
    EUDVariable,
    Forward,
    MemoryEPD,
    NextTrigger,
    RawTrigger,
    SeqCompute,
    SetMemory,
    SetNextPtr,
    SetTo,
    Subtract,
    f_dwread_epd,
    f_mul,
    unProxy,
)

from eudext import _compat, _parts, cmp
from eudext import mathx_tables as tables
from eudext.errors import check_choice, fail, warn

M32 = 0xFFFFFFFF
SIGN = 0x80000000
SMAX = 0x7FFFFFFF
FAST_MAX = 32767  # lengthdir 빠른 길: |R| 이 이 값 이하 (R·T 가 부호 있는 32비트에 들어감)
FAST_BITS = 15
DIV0 = ("eudplib", "ctrig")

__all__ = [
    "DIV0",
    "Rotator",
    "atan2",
    "atan2_sc",
    "f_atan2",
    "f_atan2_sc",
    "f_ilog2",
    "f_isqrt",
    "f_lengthdir",
    "f_ratio",
    "f_rotate3d",
    "f_sdiv",
    "f_sdivmod",
    "f_smod",
    "f_to_dir256",
    "ilog2",
    "isqrt",
    "lengthdir",
    "ratio",
    "rotate3d",
    "sdiv",
    "sdivmod",
    "smod",
    "to_dir256",
]


# =============================================================================================
# 파이썬 쪽 계산 (상수 접기) — CtrigAsm 의미 그대로 (tests/ref_mathx.py 와 따로 짠 것)
# =============================================================================================


def _u32(x):
    return x & M32


def _s32(x):
    x &= M32
    return x - (1 << 32) if x & SIGN else x


def _norm(a, cycle):
    """a(32비트) 를 부호 있게 읽어 cycle 로 나눈 나머지(0 ~ cycle−1) — CiMod 뒤 음수면 +cycle 과 같다."""
    return _s32(a) % cycle


def _quad(t, cycle):
    """정규화한 각 → (cos 부호, sin 부호, sin 표 색인, cos 표 색인). CA:84428~84456."""
    q = cycle // 4
    if t < q:
        return 0, 0, t, q - t
    if t < 2 * q:
        return 1, 0, 2 * q - t, t - q
    if t < 3 * q:
        return 1, 1, t - 2 * q, 3 * q - t
    return 0, 1, 4 * q - t, t - 3 * q


def _tdiv(a, b):
    """0 방향 정수 나눗셈 (b ≠ 0)."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _term_py(v, t, flip):
    """CiDiv(v·t mod 2³², 0x10000), flip 이면 부호 반전 (32비트 부호 없는 값)."""
    p = _s32(v * t)
    r = _tdiv(p, 0x10000)
    return _u32(-r if flip else r)


def _ld_py(r, a, cycle, precise):
    cs, ss, si, ci = _quad(_norm(a, cycle), cycle)
    if not precise:
        tbl = tables.sin_table(cycle)
        return _term_py(r, tbl[ci], cs), _term_py(r, tbl[si], ss)
    rr = _u32(r)
    neg = rr >= SIGN
    bits = _pbits(precise)
    if bits < 15 and (_u32(-rr) if neg else rr) >= (1 << bits):
        return _ld_py(r, a, cycle, False)          # 줄인 표 밖 — 표 없는 길
    k = (_u32(-rr) if neg else rr) & 0x7FFF
    q = cycle // 4
    c = int(k * tables.cr_sin(ci * 90, q))
    s = int(k * tables.cr_sin(si * 90, q))
    return _u32(-c if cs != neg else c), _u32(-s if ss != neg else s)


def _rot_py(x, y, a, cycle, precise):
    xc, xs = _ld_py(x, a, cycle, precise)
    yc, ys = _ld_py(y, a, cycle, precise)
    return _u32(xc - ys), _u32(xs + yc)


def _rot3d_py(x, y, xy, yz, zx, cycle, precise):
    X, Y, Z = _u32(x), _u32(y), 0
    if xy is not None:
        c11, c12 = _ld_py(X, xy, cycle, precise)
        c13, c14 = _ld_py(Y, xy, cycle, precise)
        X, Y = _u32(c11 - c14), _u32(c12 + c13)
    if yz is not None:
        Y, Z = _ld_py(Y, yz, cycle, precise)
    if zx is not None:
        c11 = _ld_py(X, zx, cycle, precise)[0]
        c14 = _ld_py(Z, zx, cycle, precise)[1]
        X = _u32(c11 - c14)
    return X, Y, Z


def _atan2_py(dy, dx, cycle):
    q = cycle // 4
    y, x = _u32(dy), _u32(dx)
    ny, nx = y >= SIGN, x >= SIGN
    if ny:
        y = _u32(-y)
    if nx:
        x = _u32(-x)
    ratio = _u32(y << 16) // x if x else M32
    th = sum(1 for t in tables.atan_thresholds(cycle) if t < ratio)
    if nx and not ny:
        th = 2 * q - th
    elif nx and ny:
        th += 2 * q
    elif ny:
        th = 4 * q - th
    return _u32(th)


def _sdivmod_py(a, b, div0):
    sa, sb = _s32(a), _s32(b)
    if sb == 0:
        if div0 == "ctrig":
            return (SMAX if sa >= 0 else SIGN), _u32(sa)
        return (M32 if sa >= 0 else 1), _u32(sa)
    q = _tdiv(sa, sb)
    return _u32(q), _u32(sa - q * sb)


def _dir256_py(a, cycle):
    return (_norm(a, cycle) * 256 // cycle + 64) % 256


# =============================================================================================
# 인자
# =============================================================================================


def _val(x, fname, what):
    """정수 상수 → 32비트 int, EUDVariable → 그대로, 읽기 전용 값 칸 → 읽은 새 변수, 주소식 → 새 변수에 복사."""
    x = unProxy(x)
    if isinstance(x, bool):
        x = int(x)
    if isinstance(x, int):
        if not -(1 << 31) <= x < (1 << 32):
            fail("%s: %s 상수 %d 가 32비트 범위(−2³¹ ~ 2³²−1) 밖입니다", fname, what, x)
        return x & M32
    if isinstance(x, float):
        fail("%s: %s 에 실수 %r 는 쓸 수 없습니다 (정수로 바꾸세요)", fname, what, x)
    if _compat.is_var(x):
        return x
    if _compat.is_varbase(x) or hasattr(x, "getValueAddr"):
        # 읽기 전용 값 칸(EUDLightVariable, cell.Cell …): 칸을 읽어 새 변수로 (eudplib 읽기, 실행 약 36)
        return f_dwread_epd(EPD(x.getValueAddr()))
    if _compat.is_const(x):
        v = EUDVariable()
        v << x
        return v
    fail("%s: %s 로 쓸 수 없는 값입니다 (%r)", fname, what, x)


def _is_int(x):
    return isinstance(x, int)


def _check_bool(fname, name, v):
    if not isinstance(v, bool):
        fail("%s: %s 는 True/False 여야 합니다 (%r)", fname, name, v)
    return v


def _check_precise(fname, v):
    """precise = False(표 없음) · True(원본 고정밀 표, 반지름 15비트) · 정수 1~15(표에 싣는 반지름 비트 수)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int) and 1 <= v <= 15:
        return True if v == 15 else v
    fail("%s: precise 는 True/False 또는 반지름 비트 수 1~15 여야 합니다 (%r)", fname, v)


def _pbits(precise):
    """precise 값 → 표 반지름 비트 수 (True = 15, False = 0)."""
    if precise is True:
        return 15
    return int(precise) if precise else 0


def _check_ret(fname, ret, n):
    if ret is None:
        return None
    if _compat.is_var(ret):
        ret = [ret]
    if not isinstance(ret, (list, tuple)) or len(ret) != n:
        fail("%s: ret 은 EUDVariable %d개의 목록이어야 합니다 (%r)", fname, n, ret)
    for r in ret:
        if not _compat.is_varbase(unProxy(r)):
            fail("%s: ret 에 변수가 아닌 값이 있습니다 (%r)", fname, r)
    return [unProxy(r) for r in ret]


def _const_out(values, ret, signed):
    """상수 결과: ret 이 없으면 파이썬 정수(튜플), 있으면 그 변수에 넣는다(트리거 1)."""
    vals = [(_s32(v) if signed else _u32(v)) for v in values]
    if ret is None:
        return vals[0] if len(vals) == 1 else tuple(vals)
    SeqCompute([(r, SetTo, _u32(v)) for r, v in zip(ret, vals)])
    return ret[0] if len(ret) == 1 else tuple(ret)


def _call(fn, args, ret):
    if ret is None:
        return fn(*args)
    out = fn(*args, ret=ret)
    return out


# =============================================================================================
# 공유 부품 (EUDFunc 한 벌씩)
# =============================================================================================


def _ineg(v):
    return v.ineg(action=True)


def _emit_urem(th, c, maxval):
    """th ← th mod c (부호 없음, th ≤ maxval). c·2^i 를 큰 것부터 빼는 긴 나눗셈 사슬."""
    top = 0
    while c << (top + 1) <= maxval:
        top += 1
    for i in range(top, -1, -1):
        k = c << i
        RawTrigger(conditions=th.AtLeast(k), actions=th.AddNumber(-k & M32))


def _emit_norm(th, cycle):
    """th(제자리) ← th 를 부호 있게 읽은 값 mod cycle. 흔한 [cycle, 2·cycle), [−cycle, 0) 은 트리거 2개로 끝난다."""
    c = cycle
    RawTrigger(conditions=[th.AtLeast(c), th.AtMost(2 * c - 1)], actions=th.AddNumber(-c & M32))
    RawTrigger(conditions=th.AtLeast((1 << 32) - c), actions=th.AddNumber(c))
    if EUDIf()(th.AtLeast(c)):
        neg = EUDVariable()
        RawTrigger(actions=neg.SetNumber(0))
        RawTrigger(conditions=th.AtLeast(SIGN), actions=[*_ineg(th), neg.SetNumber(1)])  # |th| ≤ 2³¹
        _emit_urem(th, c, SIGN)
        RawTrigger(conditions=[neg.Exactly(1), th.AtLeast(1)], actions=[*_ineg(th), th.AddNumber(c)])
    EUDEndIf()


def _emit_flip(neg, x, sign_flag):
    """x 를 (neg XOR sign_flag) 이면 부호 반전. sign_flag 는 상수 0/1."""
    RawTrigger(conditions=neg.Exactly(1 - sign_flag), actions=_ineg(x))


@functools.lru_cache(maxsize=None)
def _sdiv16_fn():
    @EUDFunc
    def _sdiv16(p):
        """CiDiv(p, 0x10000): 부호 떼기 → >> 16 → 부호 붙이기."""
        neg = EUDVariable()
        RawTrigger(actions=neg.SetNumber(0))
        RawTrigger(conditions=p.AtLeast(SIGN), actions=[*_ineg(p), neg.SetNumber(1)])
        p >>= 16
        RawTrigger(conditions=neg.Exactly(1), actions=_ineg(p))
        return p

    return _sdiv16


@functools.lru_cache(maxsize=None)
def _smul_fn():
    @EUDFunc
    def _smul(a, b):
        """a·b mod 2³² — 절댓값끼리 곱해(eudplib 곱셈은 a 의 비트만 돈다) 부호를 붙인다."""
        flag = EUDVariable()
        RawTrigger(actions=flag.SetNumber(0))
        RawTrigger(conditions=a.AtLeast(SIGN), actions=[*_ineg(a), flag.AddNumber(1)])
        RawTrigger(conditions=b.AtLeast(SIGN), actions=[*_ineg(b), flag.AddNumber(1)])
        p = f_mul(a, b)
        RawTrigger(conditions=flag.Exactly(1), actions=_ineg(p))
        return p

    return _smul


def _mul_var_const(x, c):
    """x·c mod 2³² (x 변수, c 32비트 상수) → 새 변수. eudplib 상수 곱(상수마다 본문 1벌, 호출 자리 1)을 쓴다.

    DPS 이식판 `_mul_small`(a7aad90 arith.py:275, 배가·덧셈 인라인 펼치기)은 실행은 조금 적지만 호출 자리마다
    트리거 수십 개(예: ×150 → 약 40개, 4KB)를 내서 용량 원칙(DESIGN 3.8)에 맞지 않아 쓰지 않는다.
    """
    c &= M32
    r = EUDVariable()
    if c == 0:
        r << 0
        return r
    if c == 1:
        r << x
        return r
    return f_mul(x, c, ret=[r])


@functools.lru_cache(maxsize=None)
def _udivmod_fn():
    @EUDFunc
    def _div3232(n, d):
        """32비트 부호 없는 (몫, 나머지). 제수 0 → (0xFFFFFFFF, n). 마지막 제수의 배수 표를 기억해 같은 제수면 재사용.

        출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/divide.py:26` _div3232 (eudplib 0.81 그대로 동작, 이름만 바꿈)
        """
        q, x = EUDVariable(), EUDVariable()
        cached = EUDVariable()  # 표를 만든 제수 (0 = 아직 없음)
        zero, run, entry = Forward(), Forward(), Forward()
        chain = [Forward() for _ in range(32)]
        conds = [Forward() for _ in range(32)]
        acts = [Forward() for _ in range(32)]

        q << 0
        EUDJumpIf(d.Exactly(0), zero)
        # 같은 제수면 표를 건너뛴다: d 를 비교 조건의 값 칸에 써 넣고 cached 와 견준다 (이 조건은 부정되지 않는다)
        hit = Forward()
        SeqCompute([(EPD(hit) + 2, SetTo, d)])
        EUDJumpIf(hit << cached.Exactly(0), entry)

        # 표 만들기 (eudplib _eud_div 와 같다). 넘치기 직전 단 i 에서 사슬 i 로 가고, 시작점도 i 로 고쳐 둔다
        SeqCompute([(x, SetTo, d), (cached, SetTo, d)])
        for i in range(32):
            SeqCompute([(EPD(conds[i]) + 2, SetTo, x), (EPD(acts[i]) + 5, SetTo, x)])
            p1, p2, p3 = Forward(), Forward(), Forward()
            p1 << RawTrigger(nextptr=p2, conditions=x.AtLeastX(1, SIGN), actions=SetNextPtr(p1, p3))
            p3 << RawTrigger(nextptr=chain[i], actions=[SetNextPtr(p1, p2), SetNextPtr(entry, chain[i])])
            p2 << NextTrigger()
            if i < 31:
                SeqCompute([(x, Add, x)])
        # d ≠ 0 이면 위 어딘가에서 반드시 사슬로 간다 (i = 31 이면 x = d·2^31 ≥ 2^31)

        entry << RawTrigger(nextptr=chain[31])
        for i in range(31, -1, -1):
            chain[i] << RawTrigger(
                conditions=[conds[i] << n.AtLeast(0)],
                actions=[acts[i] << n.SubtractNumber(0), q.AddNumber(1 << i)],
            )
        EUDJump(run)
        zero << RawTrigger(nextptr=run, actions=[q.SetNumber(M32)])
        run << NextTrigger()
        EUDReturn(q, n)

    return _div3232


# =============================================================================================
# lengthdir 항 (한 값에 cos·sin 곱을 한꺼번에)
# =============================================================================================


def _emit_fast_bits(v, c, s, cvals, svals):
    """v(0 ~ 32767)의 비트 i 마다 c += cvals[i], s += svals[i]. 값이 Forward 짝이면 (Forward, 초기값) — 준비 때 고쳐 쓴다."""
    for i in range(FAST_BITS):
        acts = []
        for dst, vals in ((c, cvals), (s, svals)):
            if vals is None:
                continue
            item = vals[i]
            if isinstance(item, tuple):
                fwd, init = item
                acts.append(fwd << dst.AddNumber(init))
            elif item:
                acts.append(dst.AddNumber(item))
        if acts:
            RawTrigger(conditions=v.AtLeastX(1, 1 << i), actions=acts)


def _emit_slow(v, neg, c, s, tc, ts):
    """|R| > 32767: 원래 R 로 되돌려 32비트 곱 + CiDiv(·, 0x10000). 부호는 곱에서 나오므로 neg ← 0."""
    RawTrigger(conditions=neg.Exactly(1), actions=[*_ineg(v), neg.SetNumber(0)])
    smul, sdiv16 = _smul_fn(), _sdiv16_fn()
    for t, dst in ((tc, c), (ts, s)):
        if _is_int(t) and t == 0:
            continue
        sdiv16(smul(t, v), ret=[dst])


@functools.lru_cache(maxsize=None)
def _const_ld_fn(cycle, precise, t):
    """정규화한 상수 각 t 의 lengthdir 본문 (v → (cos, sin))."""
    cs, ss, si, ci = _quad(t, cycle)
    if precise:
        bits = _pbits(precise)
        base = EPD(_precise_db(cycle, bits))
        fb = _const_ld_fn(cycle, False, t) if bits < 15 else None

        def table_part(v, neg, c, s):
            f_dwread_epd(v + (base + (ci << bits)), ret=[c])
            f_dwread_epd(v + (base + (si << bits)), ret=[s])
            if ci != 0:
                _emit_flip(neg, c, cs)
            if si != 0:
                _emit_flip(neg, s, ss)

        @EUDFunc
        def ld_p(v):
            c, s, neg = EUDVariable(), EUDVariable(), EUDVariable()
            RawTrigger(actions=neg.SetNumber(0))
            RawTrigger(conditions=v.AtLeast(SIGN), actions=[*_ineg(v), neg.SetNumber(1)])
            if fb is None:
                RawTrigger(actions=v.SetNumberX(0, 0xFFFF8000))
                table_part(v, neg, c, s)
                return c, s
            if EUDIf()(v.AtLeast(1 << bits)):              # 줄인 표 밖 — 부호를 되돌려 표 없는 길
                RawTrigger(conditions=neg.Exactly(1), actions=_ineg(v))
                fc, fs = fb(v)
                SeqCompute([(c, SetTo, fc), (s, SetTo, fs)])
            if EUDElse()():
                table_part(v, neg, c, s)
            EUDEndIf()
            return c, s

        return ld_p

    tbl = tables.sin_table(cycle)
    tc, ts = tbl[ci], tbl[si]

    def vals(t_):
        if t_ in (0, 0x10000):
            return None
        return [t_ << i for i in range(FAST_BITS)]

    @EUDFunc
    def ld(v):
        c, s, neg = EUDVariable(), EUDVariable(), EUDVariable()
        RawTrigger(actions=[c.SetNumber(0), s.SetNumber(0), neg.SetNumber(0)])
        RawTrigger(conditions=v.AtLeast(SIGN), actions=[*_ineg(v), neg.SetNumber(1)])
        if EUDIf()(v.AtMost(FAST_MAX)):
            _emit_fast_bits(v, c, s, vals(tc), vals(ts))
            ops = []
            for t_, dst in ((tc, c), (ts, s)):
                if t_ == 0x10000:
                    ops.append((dst, SetTo, v))
            if ops:
                SeqCompute(ops)
            for t_, dst in ((tc, c), (ts, s)):
                if t_ not in (0, 0x10000):
                    dst >>= 16
        if EUDElse()():
            _emit_slow(v, neg, c, s, tc, ts)
        EUDEndIf()
        if tc:
            _emit_flip(neg, c, cs)
        if ts:
            _emit_flip(neg, s, ss)
        return c, s

    return ld


@functools.lru_cache(maxsize=None)
def _const_rot_fn(cycle, precise, t):
    ld = _const_ld_fn(cycle, precise, t)

    @EUDFunc
    def rot(x, y):
        xc, xs = ld(x)
        yc, ys = ld(y)
        _parts.isub32(xc, ys)
        xs += yc
        return xc, xs

    return rot


_precise_dbs = {}
_precise_warned = set()


def _precise_warn(cycle, bits=15):
    if (cycle, bits) not in _precise_warned:
        _precise_warned.add((cycle, bits))
        size = tables.precise_table_size(cycle, bits)
        warn(
            "mathx: 고정밀 lengthdir(precise=%s, cycle %d) 표를 싣습니다 — %d 바이트 (%.1fMB). "
            "맵 용량에 주의하세요 (CtrigAsm LengthdirX 와 같은 표%s)",
            "True" if bits == 15 else bits,
            cycle,
            size,
            size / 1048576,
            "" if bits == 15 else ", |R| < %d 칸만" % (1 << bits),
        )


def _precise_db(cycle, bits=15):
    db = _precise_dbs.get((cycle, bits))
    if db is None:
        _precise_warn(cycle, bits)
        db = Db(tables.precise_table_bytes(cycle, bits))
        _precise_dbs[(cycle, bits)] = db
    return db


class _Engine:
    """변수 각 lengthdir 엔진: 마지막으로 준비한 각의 상태(곱 액션 값·부호 조건)를 들고 있는 본문 한 벌.

    `ld(angle, v)` 가 angle ≠ 마지막 각이면 `load(angle)` 로 상태를 고친 뒤 항을 계산한다. 첫 상태는 각 0.
    """

    def __init__(self, cycle, precise, name):
        self.cycle = cycle
        self.precise = precise
        self.name = name
        self._ld = None
        self._load = None
        self._rot = None
        self._state = None

    # 상태는 처음 쓸 때 만든다 (빌드 안에서)
    def _mk_state(self):
        if self._state is not None:
            return self._state
        q = self.cycle // 4
        st = {"loaded": EUDVariable(0), "flipc": Forward(), "flips": Forward()}
        if self.precise:
            bits = _pbits(self.precise)
            base = EPD(_precise_db(self.cycle, bits))
            st["basec"] = EUDVariable(base + (q << bits))  # 각 0: cos 색인 Q
            st["bases"] = EUDVariable(base)  # sin 색인 0
        else:
            st["tc"] = EUDVariable(0x10000)
            st["ts"] = EUDVariable(0)
            st["fc"] = [(Forward(), 0x10000 << i) for i in range(FAST_BITS)]
            st["fs"] = [(Forward(), 0) for _ in range(FAST_BITS)]
            st["parr"] = EUDVArray(q + 1)(list(tables.packed_sin_table(self.cycle)))
        self._state = st
        return st

    def load_func(self):
        if self._load is not None:
            return self._load
        st = self._mk_state()
        cycle, q = self.cycle, self.cycle // 4
        flipc, flips = st["flipc"], st["flips"]

        @EUDFunc
        def load(th):
            _emit_norm(th, cycle)
            # 사분면: 부호 조건의 비교값 = 1 − 부호 (neg == 1 − cs 이면 뒤집음). 1사분면이 기본
            RawTrigger(actions=[SetMemory(flipc + 8, SetTo, 1), SetMemory(flips + 8, SetTo, 1)])
            RawTrigger(
                conditions=[th.AtLeast(2 * q), th.AtMost(3 * q - 1)],
                actions=[th.AddNumber(-2 * q & M32), SetMemory(flipc + 8, SetTo, 0), SetMemory(flips + 8, SetTo, 0)],
            )
            RawTrigger(
                conditions=[th.AtLeast(q), th.AtMost(2 * q - 1)],
                actions=[*_ineg(th), th.AddNumber(2 * q), SetMemory(flipc + 8, SetTo, 0)],
            )
            RawTrigger(
                conditions=th.AtLeast(3 * q),
                actions=[*_ineg(th), th.AddNumber(4 * q), SetMemory(flips + 8, SetTo, 0)],
            )
            # 이제 th = sin 색인 si (cos 색인 = Q − si)
            if self.precise:
                basec, bases = st["basec"], st["bases"]
                # basec = Q − si: SC Subtract (Q ≥ si 가 보장되어 포화하지 않음, DESIGN 3.5-7)
                SeqCompute([(bases, SetTo, th), (basec, SetTo, q), (basec, Subtract, th)])
                bits = _pbits(self.precise)
                bases <<= bits
                basec <<= bits
                base = EPD(_precise_db(cycle, bits))
                RawTrigger(actions=[bases.AddNumber(base), basec.AddNumber(base)])
                return
            vc, vs = EUDVariable(), EUDVariable()
            p = st["parr"][th]
            SeqCompute([(vc, SetTo, p), (vs, SetTo, p)])
            vs <<= 16
            vs >>= 16
            vc >>= 16
            RawTrigger(conditions=th.Exactly(0), actions=vc.SetNumber(0x10000))
            RawTrigger(conditions=th.Exactly(q), actions=[vs.SetNumber(0x10000), vc.SetNumber(0)])
            ops = [(st["tc"], SetTo, vc), (st["ts"], SetTo, vs)]
            for i in range(FAST_BITS):
                ops.append((EPD(st["fc"][i][0]) + 5, SetTo, vc))
                ops.append((EPD(st["fs"][i][0]) + 5, SetTo, vs))
                if i < FAST_BITS - 1:
                    ops.append((vc, Add, vc))
                    ops.append((vs, Add, vs))
            SeqCompute(ops)

        self._load = load
        return load

    def ld_func(self):
        if self._ld is not None:
            return self._ld
        st = self._mk_state()
        load = self.load_func()
        loaded, flipc, flips = st["loaded"], st["flipc"], st["flips"]

        if self.precise:
            bits = _pbits(self.precise)
            # 줄인 표 밖은 표 없는 엔진(따로 된 한 벌 — 준비한 각 상태가 섞이지 않게)
            fb = _shared_engine(self.cycle, False, self.name + "_fb").ld_func() if bits < 15 else None

            @EUDFunc
            def ld_p(angle, v):
                if EUDIf()(cmp.ne(angle, loaded)):
                    loaded << angle
                    load(angle)
                EUDEndIf()
                c, s, neg = EUDVariable(), EUDVariable(), EUDVariable()
                RawTrigger(actions=neg.SetNumber(0))
                RawTrigger(conditions=v.AtLeast(SIGN), actions=[*_ineg(v), neg.SetNumber(1)])
                if fb is not None:
                    if EUDIf()(v.AtLeast(1 << bits)):
                        RawTrigger(conditions=neg.Exactly(1), actions=_ineg(v))
                        fc, fs = fb(angle, v)
                        SeqCompute([(c, SetTo, fc), (s, SetTo, fs)])
                    if EUDElse()():
                        f_dwread_epd(st["basec"] + v, ret=[c])
                        f_dwread_epd(st["bases"] + v, ret=[s])
                        RawTrigger(conditions=flipc << neg.Exactly(1), actions=_ineg(c))
                        RawTrigger(conditions=flips << neg.Exactly(1), actions=_ineg(s))
                    EUDEndIf()
                    return c, s
                RawTrigger(actions=v.SetNumberX(0, 0xFFFF8000))
                f_dwread_epd(st["basec"] + v, ret=[c])
                f_dwread_epd(st["bases"] + v, ret=[s])
                # 부호 조건의 비교값은 load 가 고친다 (RawTrigger 에만 쓰므로 eudplib 제자리 부정과 무관 — 3.4)
                RawTrigger(conditions=flipc << neg.Exactly(1), actions=_ineg(c))
                RawTrigger(conditions=flips << neg.Exactly(1), actions=_ineg(s))
                return c, s

            self._ld = ld_p
            return ld_p

        @EUDFunc
        def ld(angle, v):
            if EUDIf()(cmp.ne(angle, loaded)):
                loaded << angle
                load(angle)
            EUDEndIf()
            c, s, neg = EUDVariable(), EUDVariable(), EUDVariable()
            RawTrigger(actions=[c.SetNumber(0), s.SetNumber(0), neg.SetNumber(0)])
            RawTrigger(conditions=v.AtLeast(SIGN), actions=[*_ineg(v), neg.SetNumber(1)])
            if EUDIf()(v.AtMost(FAST_MAX)):
                _emit_fast_bits(v, c, s, st["fc"], st["fs"])
                c >>= 16
                s >>= 16
            if EUDElse()():
                _emit_slow(v, neg, c, s, st["tc"], st["ts"])
            EUDEndIf()
            RawTrigger(conditions=flipc << neg.Exactly(1), actions=_ineg(c))
            RawTrigger(conditions=flips << neg.Exactly(1), actions=_ineg(s))
            return c, s

        self._ld = ld
        return ld

    def rot_func(self):
        if self._rot is not None:
            return self._rot
        ld = self.ld_func()

        @EUDFunc
        def rot(angle, x, y):
            xc, xs = ld(angle, x)
            yc, ys = ld(angle, y)
            _parts.isub32(xc, ys)
            xs += yc
            return xc, xs

        self._rot = rot
        return rot


_engines = {}


def _shared_engine(cycle, precise, name="shared"):
    """주기·정밀도마다 하나인 공유 엔진(lengthdir·Rotator·rotate3d 기본). name 을 주면 따로 된 엔진."""
    key = (cycle, precise, name)
    e = _engines.get(key)
    if e is None:
        e = _Engine(cycle, precise, name)
        _engines[key] = e
    return e


# =============================================================================================
# 공개 API — lengthdir·회전
# =============================================================================================


def f_lengthdir(r, a, cycle=360, precise=False, *, ret=None):
    """(r·cos a, r·sin a) — CtrigAsm `f_Lengthdir` 와 같은 값.

    인자: r(반지름, 부호 있음 — 정확한 원본 범위 −32768 ~ 32767, 그 밖은 원본처럼 32비트 곱이 넘친 값),
          a(각, 부호 있음·cycle 이상 가능 — a mod cycle 로 읽음), cycle(4의 배수, 4 ~ 65536, 기본 360),
          precise(True = CtrigAsm LengthdirX 고정밀 표 — 표 크기 (cycle/4+1)×131072 바이트, 360 이면 11.9MB),
          ret([cos 변수, sin 변수], 선택)
    반환: (cos, sin) — 모두 상수면 파이썬 정수(음수 가능), 아니면 EUDVariable 두 개
    비용: 상수 각 = 본문 30(각마다 1벌) / 호출 1 / 실행 31. 변수 각 = 공유 본문 108 + 준비 본문(주기마다 1벌,
          Rotator·rotate3d 와 같이 씀) / 호출 1 / 실행 36(마지막으로 준비한 각과 같음) · 160~186(각 준비).
          precise(주기 8) = 본문 62 / 실행 116. 느린 길(|r| > 32767) + 약 210.
          한 번 드는 페이로드 약 98KB(변수 각, eudplib f_mul 38KB 포함)·54KB(상수 각) (2026-09-17, docs/COSTS.md "mathx (WP9)")
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const c, s = mx.lengthdir(r, a);` / `mx.lengthdir(r, a, 360, ret=list(cx, cy));`
    출처: CtrigAsm f_Lengthdir(CA:84377~84638), R4b C1
    """
    fname = "mathx.lengthdir"
    tables.check_cycle(cycle, fname)
    precise = _check_precise(fname, precise)
    ret = _check_ret(fname, ret, 2)
    rv = _val(r, fname, "r")
    av = _val(a, fname, "a")
    if _is_int(rv) and _is_int(av):
        if precise:
            _precise_warn(cycle, _pbits(precise))  # 상수 접기는 표를 싣지 않지만, 변수를 넣는 순간 표가 실린다는 것을 미리 알린다
        return _const_out(_ld_py(rv, av, cycle, precise), ret, True)
    if _is_int(av):
        return _call(_const_ld_fn(cycle, precise, _norm(av, cycle)), (rv,), ret)
    return _call(_shared_engine(cycle, precise).ld_func(), (av, rv), ret)


class Rotator:
    """고정각 회전 — CtrigAsm `CA_Rotate` 와 같은 값: `x' = lx.cos − ly.sin`, `y' = lx.sin + ly.cos` (항별 자르기).

    인자: angle(상수 = 컴파일 시점에 고정, 변수 = 만들 때 그 값을 복사(트리거 1), None = 변수 각·초기값 0(트리거 0)),
          cycle(기본 360), precise(True = 고정밀 표로 회전 — Memory_2 처럼 LengthdirX 를 켠 맵과 같은 값),
          own(False = 같은 주기의 lengthdir·다른 Rotator 와 변수 각 본문 하나를 같이 씀(기본, 용량 절약).
              True = 이 Rotator 만의 본문(페이로드 약 +60KB) — 각이 다른 Rotator 들을 점마다 번갈아 부를 때)
    쓰는 법: `rot(x, y)`/`rot.rotate(x, y)` → (x', y'), `rot.lengthdir(r)` → (cos, sin), `rot.set(a)` 각 바꾸기(변수 각만),
             `rot.angle` → 각 변수(변수 각) 또는 정수(상수 각)
    반환: 상수 각·상수 점이면 파이썬 정수, 아니면 EUDVariable 튜플
    비용: 상수 각 = 본문 6 + lengthdir 상수 각 본문(각마다 1벌) / 호출 1 / 점마다 실행 76.
          변수 각 = 공유 본문(주기마다 1벌, lengthdir 와 같음) / 호출 1~2 / 점마다 실행 89,
          마지막으로 준비한 각과 다르면 그 점이 213~240 (공유 본문에서 각이 다른 lengthdir·Rotator 를 섞어 부를 때도).
          own=True 는 인스턴스마다 본문(페이로드 약 +54KB).
          (docs/COSTS.md "mathx (WP9)" — S1 8.6 "회전 +120" 목표 안)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const rot = mx.Rotator(ang);` → `const x2, y2 = rot(x, y);` → `rot.set(ang2);`
    출처: CB Paint CA_Rotate(CBP:9865), S1 6.3·11-5
    """

    __slots__ = ("_angle", "_const", "_engine", "cycle", "precise")

    def __init__(self, angle=None, cycle=360, precise=False, own=False):
        fname = "mathx.Rotator"
        self.cycle = tables.check_cycle(cycle, fname)
        self.precise = precise = _check_precise(fname, precise)
        self._engine = None
        self._angle = None
        self._const = None
        if angle is not None:
            av = _val(angle, fname, "angle")
            if _is_int(av):
                self._const = _norm(av, cycle)
                return
        _check_bool(fname, "own", own)
        self._engine = _Engine(cycle, precise, "rotator") if own else _shared_engine(cycle, precise)
        self._angle = EUDVariable()
        if angle is not None:
            self._angle << av

    def __repr__(self):
        if self._const is not None:
            return "<mathx.Rotator 상수 각 %d/%d>" % (self._const, self.cycle)
        return "<mathx.Rotator 변수 각 (cycle %d)>" % self.cycle

    @property
    def angle(self):
        """각: 상수 각이면 정규화한 정수, 변수 각이면 그 EUDVariable(직접 고쳐도 된다 — `rot.angle += 1`)."""
        return self._const if self._const is not None else self._angle

    @angle.setter
    def angle(self, value):
        if value is self._angle and value is not None:  # `rot.angle += 1` 이 제자리에서 고친 뒤 다시 넣는 경우
            return
        self.set(value)

    def set(self, angle):
        """각을 바꾼다(변수 각 Rotator 만). 표 준비는 다음 점을 계산할 때 한다. 비용: 호출 1~2 / 실행 1~2."""
        if self._engine is None:
            fail("mathx.Rotator.set: 상수 각으로 만든 Rotator 입니다 — 각을 바꾸려면 Rotator(변수) 또는 Rotator(None) 으로 만드세요")
        av = _val(angle, "mathx.Rotator.set", "angle")
        self._angle << av

    def rotate(self, x, y, *, ret=None):
        """(x, y) 를 돌린 (x', y'). 비용·반환은 클래스 설명."""
        fname = "mathx.Rotator"
        ret = _check_ret(fname, ret, 2)
        xv = _val(x, fname, "x")
        yv = _val(y, fname, "y")
        if self._const is not None:
            if _is_int(xv) and _is_int(yv):
                return _const_out(_rot_py(xv, yv, self._const, self.cycle, self.precise), ret, True)
            return _call(_const_rot_fn(self.cycle, self.precise, self._const), (xv, yv), ret)
        return _call(self._engine.rot_func(), (self._angle, xv, yv), ret)

    __call__ = rotate

    def lengthdir(self, r, *, ret=None):
        """이 각의 (r·cos, r·sin) — `f_lengthdir(r, rot.angle)` 와 같다(변수 각은 이 Rotator 의 상태를 쓴다)."""
        fname = "mathx.Rotator.lengthdir"
        ret = _check_ret(fname, ret, 2)
        rv = _val(r, fname, "r")
        if self._const is not None:
            if _is_int(rv):
                return _const_out(_ld_py(rv, self._const, self.cycle, self.precise), ret, True)
            return _call(_const_ld_fn(self.cycle, self.precise, self._const), (rv,), ret)
        return _call(self._engine.ld_func(), (self._angle, rv), ret)


def _kind(a, fname, what, cycle):
    if a is None:
        return None, None
    av = _val(a, fname, what)
    if _is_int(av):
        return ("c", _norm(av, cycle)), None
    return ("v",), av


@functools.lru_cache(maxsize=None)
def _rot3d_fn(cycle, precise, own, kxy, kyz, kzx):
    kinds = (("xy", kxy), ("yz", kyz), ("zx", kzx))
    nvar = sum(1 for _n, k in kinds if k == ("v",))

    def body(x, y, *angles):
        it = iter(angles)
        avar = {n: (next(it) if k == ("v",) else None) for n, k in kinds if k is not None}

        def ld(step, kind, v):
            if kind[0] == "c":
                return _const_ld_fn(cycle, precise, kind[1])(v)
            eng = _shared_engine(cycle, precise, "r3_" + step) if own else _shared_engine(cycle, precise)
            return eng.ld_func()(avar[step], v)

        X, Y, Z = x, y, None
        if kxy is not None:
            c11, c12 = ld("xy", kxy, X)
            c13, c14 = ld("xy", kxy, Y)
            _parts.isub32(c11, c14)
            c12 += c13
            X, Y = c11, c12
        if kyz is not None:
            Y, Z = ld("yz", kyz, Y)
        if kzx is not None:
            c11, _c12 = ld("zx", kzx, X)
            if Z is not None:  # Z 가 0 이면 lengthdir(0) = (0, 0) 이라 빼기를 건너뛴다
                _c13, c14 = ld("zx", kzx, Z)
                _parts.isub32(c11, c14)
            X = c11
        return X, Y, (Z if Z is not None else 0)

    # EUDFunc 는 인자 수를 함수 서명에서 읽는다 → 변수 각 개수마다 서명을 따로 둔다
    if nvar == 0:

        def _f0(x, y):
            return body(x, y)

        return EUDFunc(_f0)
    if nvar == 1:

        def _f1(x, y, a0):
            return body(x, y, a0)

        return EUDFunc(_f1)
    if nvar == 2:

        def _f2(x, y, a0, a1):
            return body(x, y, a0, a1)

        return EUDFunc(_f2)

    def _f3(x, y, a0, a1, a2):
        return body(x, y, a0, a1, a2)

    return EUDFunc(_f3)


def f_rotate3d(x, y, xy=None, yz=None, zx=None, cycle=360, precise=False, own=False, *, ret=None):
    """3D 회전 — CtrigAsm `CA_Rotate3D` 와 같은 값. Z 는 0 에서 시작하고 None 인 단계는 건너뛴다.

    순서: XY 로 (x, y) 회전 → YZ: (y, z) = lengthdir(y, yz) → ZX: x = lengthdir(x, zx).cos − lengthdir(z, zx).sin.
    인자: x, y(점), xy/yz/zx(각 — 상수·변수·None), cycle, precise,
          own(False = 변수 각은 공유 엔진 하나 — 서로 다른 변수 각이 둘 이상이면 점마다 표를 다시 준비(실행 + 약 125 × 바뀐 수).
              True = rotate3d 전용 엔진 셋(XY·YZ·ZX, 모든 own=True 호출이 같이 씀, 페이로드 약 +150KB) — 점마다 준비 없음),
          ret([X, Y, Z], 선택)
    반환: (X, Y, Z) — 모두 상수면 파이썬 정수, 아니면 EUDVariable 세 개
    비용: 단계마다 lengthdir 1~2번. 상수 각 3단계 실행 174, 한 번 드는 페이로드(변수 각) 약 104KB (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const X, Y, Z = mx.rotate3d(x, y, xy, yz, zx);` (건너뛸 단계는 None)
    출처: CB Paint CA_Rotate3D(CBP:9883), S1 6.3-3
    """
    fname = "mathx.rotate3d"
    tables.check_cycle(cycle, fname)
    precise = _check_precise(fname, precise)
    _check_bool(fname, "own", own)
    ret = _check_ret(fname, ret, 3)
    xv = _val(x, fname, "x")
    yv = _val(y, fname, "y")
    parts = [_kind(a, fname, n, cycle) for a, n in ((xy, "xy"), (yz, "yz"), (zx, "zx"))]
    kinds = tuple(p[0] for p in parts)
    if _is_int(xv) and _is_int(yv) and all(k is None or k[0] == "c" for k in kinds):
        angs = [None if k is None else k[1] for k in kinds]
        return _const_out(_rot3d_py(xv, yv, *angs, cycle, precise), ret, True)
    args = [xv, yv] + [p[1] for p in parts if p[1] is not None]
    return _call(_rot3d_fn(cycle, precise, own, *kinds), tuple(args), ret)


# =============================================================================================
# atan2
# =============================================================================================


def _shl_acts(v, n):
    """v <<= n 을 액션 목록으로 (조건 트리거에 넣을 수 있게). 액션 2·(32−n)+1 개.

    출처: eudplib 0.81 `core/variable/vbase.py:157` VariableBase.__ilshift__ (마스크 SetTo/Add 식 그대로)
    """
    mask = (1 << (n + 1)) - 1
    acts = []
    for t in reversed(range(32 - n)):
        acts.append(v.SetNumberX(0, (mask >> 1) << (t + 1)))
        acts.append(v.AddNumberX((mask >> 1) << t, mask << t))
    acts.append(v.SetNumberX(0, mask >> 1))
    return acts


def _int_bits(thresholds):
    """비율의 정수 부분 비트 수 L: 2^(16+L) > 마지막 문턱 이면 y ≥ x·2^L 인 입력은 모두 cycle/4 가 된다 (최소 8)."""
    top = thresholds[-1] + 1
    return max(8, (top - 1).bit_length() - 16)


def _emit_div_ratio(y, x, out, nbits, early):
    """out ← floor(y·0x10000 / x) (1 ≤ x ≤ 65535, y ≤ 65535). y ≥ x·2^nbits 면 out 을 쓰지 않고 early 로 간다.

    긴 나눗셈 사슬(제수 x·2^k, k = nbits−1..0) 하나를 세 번 부른다: 정수 부분(nbits 비트) → 소수 1바이트 → 소수 1바이트.
    소수 단계는 n < x·256 이라 k ≥ 8 칸이 참이 되지 않는다.
    """
    n, qa, xx = EUDVariable(), EUDVariable(), EUDVariable()
    conds = [Forward() for _ in range(nbits + 1)]
    acts = [Forward() for _ in range(nbits)]
    ops = [(n, SetTo, y), (qa, SetTo, 0), (xx, SetTo, x)]
    for k in range(nbits + 1):
        ops.append((EPD(conds[k]) + 2, SetTo, xx))
        if k < nbits:
            ops.append((EPD(acts[k]) + 5, SetTo, xx))
            ops.append((xx, Add, xx))
    SeqCompute(ops)
    # 조건 값을 실행 중에 채우는 조건들 — 분기(EUDBranch)·RawTrigger 에만 쓰고 부정하지 않는다 (DESIGN 3.4)
    EUDJumpIf(conds[nbits] << n.AtLeast(0), early)
    sub = _parts.SubLabel("mathx.div_ratio")
    with sub.define():
        for k in range(nbits - 1, -1, -1):
            # n ≥ x·2^k 일 때만 빼므로 Subtract 가 포화하지 않는다 (DESIGN 3.5-7)
            RawTrigger(
                conditions=[conds[k] << n.AtLeast(0)],
                actions=[acts[k] << n.SubtractNumber(0), qa.AddNumber(1 << k)],
            )
    _parts.call_sub(sub)  # qa = y // x, n = y % x
    SeqCompute([(out, SetTo, qa)])
    for _ in range(2):
        RawTrigger(actions=[*_shl_acts(n, 8), qa.SetNumber(0)])  # n = 나머지·256 < x·256
        _parts.call_sub(sub)
        RawTrigger(actions=_shl_acts(out, 8))
        SeqCompute([(out, Add, qa)])


def _emit_search(ratio, th, thresholds, leaf=6):
    """th ← #{i : thresholds[i] < ratio} — 이진 결정 나무로 버킷(폭 leaf)을 고르고 버킷 안에서 센다."""
    rng = len(thresholds)
    starts = list(range(0, rng, leaf))

    def leaf_code(j):
        b = starts[j]
        e = starts[j + 1] - 1 if j + 1 < len(starts) else rng
        RawTrigger(actions=th.SetNumber(b))
        for i in range(b, e):
            RawTrigger(conditions=ratio.AtLeast(thresholds[i] + 1), actions=th.AddNumber(1))

    def node(lo, hi):
        if lo == hi:
            leaf_code(lo)
            return
        mid = (lo + hi + 1) // 2
        if EUDIf()(ratio.AtLeast(thresholds[starts[mid] - 1] + 1)):
            node(mid, hi)
        if EUDElse()():
            node(lo, mid - 1)
        EUDEndIf()

    node(0, len(starts) - 1)


@functools.lru_cache(maxsize=None)
def _atan2_fn(cycle, sc):
    q = cycle // 4
    thr = tables.atan_thresholds(cycle)
    nbits = _int_bits(thr)

    @EUDFunc
    def at(dy, dx):
        th, sflag, ratio = EUDVariable(), EUDVariable(), EUDVariable()
        top, found = Forward(), Forward()
        RawTrigger(actions=sflag.SetNumber(0))
        RawTrigger(conditions=dy.AtLeast(SIGN), actions=[*_ineg(dy), sflag.AddNumber(1)])
        RawTrigger(conditions=dx.AtLeast(SIGN), actions=[*_ineg(dx), sflag.AddNumber(2)])
        if EUDIf()(dx.Exactly(0)):
            EUDJump(top)  # f_Div 0 나눗셈 = 0xFFFFFFFF → 모든 문턱보다 크다
        if EUDElseIf()(dx.AtMost(0xFFFF)):
            # 원본 ClShift2(|dy|, 16) 은 한 바퀴 돌아 |dy| 의 하위 16비트만 남는다 → 16비트 나눗셈 그대로
            RawTrigger(conditions=dy.AtLeast(0x10000), actions=dy.SetNumberX(0, 0xFFFF0000))
            _emit_div_ratio(dy, dx, ratio, nbits, top)
        if EUDElse()():
            dy <<= 16  # |dx| > 65535 (원본 범위 밖): 32비트 나눗셈
            _udivmod_fn()(dy, dx, ret=[ratio, EUDVariable()])
        EUDEndIf()
        _emit_search(ratio, th, thr)
        EUDJump(found)
        top << RawTrigger(actions=th.SetNumber(q))
        found << NextTrigger()
        # 사분면: sflag 1 = dy 음수(4사분면), 2 = dx 음수(2사분면), 3 = 둘 다(3사분면)
        RawTrigger(conditions=sflag.Exactly(2), actions=[*_ineg(th), th.AddNumber(2 * q)])
        RawTrigger(conditions=sflag.Exactly(3), actions=th.AddNumber(2 * q))
        RawTrigger(conditions=sflag.Exactly(1), actions=[*_ineg(th), th.AddNumber(4 * q)])
        if sc:
            RawTrigger(actions=th.AddNumber(64))
            RawTrigger(conditions=th.AtLeast(256), actions=th.AddNumber(-256 & M32))
        return th

    return at


def f_atan2(dy, dx, cycle=360, *, ret=None):
    """(dx, dy) 방향의 각 — CtrigAsm `f_Atan2` 와 같은 값 (0 = +x, 화면 시계 방향, 0 ~ cycle−1, 올림 성격).

    인자: dy, dx(부호 있음. 원본 범위 −32768 ~ 32767 — 그 밖은 원본처럼 |dy|<<16 이 넘친 값), cycle(기본 360), ret([변수])
    반환: 각 — 모두 상수면 파이썬 정수, 아니면 EUDVariable. (0, 0) → cycle/4 (원본 0 나눗셈 몫 0xFFFFFFFF), (1, 1) → 46
    비용: 본문 182(주기마다 1벌, 360 기준) / 호출 1 / 실행 약 120 (|dx| ≤ 65535), dx = 0 이면 16,
          |dx| > 65535 는 32비트 나눗셈으로 약 170~290. 한 번 드는 페이로드 약 111KB(div3232 52KB 포함) (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `var a = mx.atan2(ty - y, tx - x);`
    출처: CtrigAsm f_Atan2(CA:84640~84841), R4b C2
    """
    fname = "mathx.atan2"
    tables.check_cycle(cycle, fname)
    ret = _check_ret(fname, ret, 1)
    yv = _val(dy, fname, "dy")
    xv = _val(dx, fname, "dx")
    if _is_int(yv) and _is_int(xv):
        return _const_out((_atan2_py(yv, xv, cycle),), ret, False)
    return _call(_atan2_fn(cycle, False), (yv, xv), ret)


def f_atan2_sc(dy, dx, *, ret=None):
    """SC 256 방향(0 = 위쪽, 시계 방향) — CtrigAsm `f_Atan2X` 와 같은 값: atan2(dy, dx, 256) + 64 (mod 256).

    인자·반환·비용: `f_atan2`(cycle 256)와 같고 실행 +2 (본문 150 / 실행 122~125)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `var d = mx.atan2_sc(dy, dx);`
    출처: CtrigAsm f_Atan2X(CA:84843~85048)
    """
    fname = "mathx.atan2_sc"
    ret = _check_ret(fname, ret, 1)
    yv = _val(dy, fname, "dy")
    xv = _val(dx, fname, "dx")
    if _is_int(yv) and _is_int(xv):
        v = _atan2_py(yv, xv, 256) + 64
        return _const_out((v - 256 if v >= 256 else v,), ret, False)
    return _call(_atan2_fn(256, True), (yv, xv), ret)


@functools.lru_cache(maxsize=None)
def _dir256_fn(cycle):
    @EUDFunc
    def d256(a):
        _emit_norm(a, cycle)
        q = EUDVariable()
        a <<= 11  # a < cycle ≤ 65536 → a·2048 < 2²⁷.  floor(a·2048 / (cycle·8)) = floor(a·256 / cycle)
        d = cycle * 8
        RawTrigger(actions=q.SetNumber(64))
        for k in range(7, -1, -1):
            RawTrigger(conditions=a.AtLeast(d << k), actions=[a.AddNumber(-(d << k) & M32), q.AddNumber(1 << k)])
        RawTrigger(conditions=q.AtLeast(256), actions=q.AddNumber(-256 & M32))
        return q

    return d256


def f_to_dir256(a, cycle=360, *, ret=None):
    """cycle 주기 각(CtrigAsm 기준, 0 = +x) → SC 256 방향(0 = 위쪽): `(floor((a mod cycle)·256/cycle) + 64) mod 256`.

    cycle 360 은 사용자 맵 표 `Angle360to256`(TEP 0 방향 자르기) + 64 와 같다(S4 2.3). 음수 a 는 CiMod 규칙(a mod cycle).
    인자: a(각), cycle(기본 360), ret([변수])
    반환: 0 ~ 255 — 상수면 파이썬 정수
    비용: 본문 43(주기마다 1벌) / 호출 1 / 실행 20 (a 가 [−cycle, 2·cycle) 일 때), 그 밖 약 47
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `var dir = mx.to_dir256(mx.atan2(dy, dx));`
    출처: S4 2.3·9-5, M2 `Var_init.lua:41~44`
    """
    fname = "mathx.to_dir256"
    tables.check_cycle(cycle, fname)
    ret = _check_ret(fname, ret, 1)
    av = _val(a, fname, "a")
    if _is_int(av):
        return _const_out((_dir256_py(av, cycle),), ret, False)
    return _call(_dir256_fn(cycle), (av,), ret)


# =============================================================================================
# 정수 제곱근·로그
# =============================================================================================


@functools.lru_cache(maxsize=None)
def _isqrt_fn():
    @EUDFunc
    def isq(n):
        """floor(√n), n 부호 없는 32비트. 두 비트씩 내리며 rem = rem·4 + 쌍, D = rem − (4r+1) ≥ 0 이면 비트 1.

        m = −(4r+1) 을 들고 다닌다: 매 단계 m ← 2m + 1, 비트가 서면 m −= 4. (+1 은 다음 단계 첫머리에서 — 상수 액션을
        변수 복사 묶음 앞에 둬야 eudplib SeqCompute 가 한 트리거로 묶는다. 그래서 m 의 처음 값은 −2.)
        """
        root, rem, m = EUDVariable(), EUDVariable(), EUDVariable()
        RawTrigger(actions=[root.SetNumber(0), rem.SetNumber(0), m.SetNumber(-2 & M32)])
        labels = [Forward() for _ in range(16)]
        for k in range(15, 0, -1):  # 앞쪽 0 쌍 건너뛰기 (r = 0, rem = 0 이 그대로 유지됨)
            EUDJumpIf(n.AtLeast(1 << (2 * k)), labels[k])
        EUDJump(labels[0])
        for k in range(15, -1, -1):
            labels[k] << NextTrigger()
            dfld = Forward()
            dv = EPD(dfld) + 5  # D 칸 = 아래 트리거의 액션 값 칸. 조건이 같은 칸을 읽는다 (부정되지 않는 조건)
            SeqCompute([
                (m, Add, 1), (rem, Add, rem), (dv, SetTo, m),  # 묶음 1: m+1, rem·2, D ← m
                (rem, Add, rem), (m, Add, m),  # 묶음 2: rem·4, m·2 (D 는 옛 m 을 가짐)
                (dv, Add, rem),  # 묶음 3: D = rem·4 − (4r+1)
            ])
            RawTrigger(conditions=n.AtLeastX(1, 1 << (2 * k + 1)),
                       actions=[rem.AddNumber(2), SetMemory(dfld + 20, Add, 2)])
            RawTrigger(conditions=n.AtLeastX(1, 1 << (2 * k)),
                       actions=[rem.AddNumber(1), SetMemory(dfld + 20, Add, 1)])
            RawTrigger(
                conditions=MemoryEPD(dv, AtMost, SMAX),
                actions=[dfld << rem.SetNumber(0), root.AddNumber(1 << k), m.AddNumber(-4 & M32)],
            )
        return root

    return isq


def f_isqrt(n, *, ret=None):
    """floor(√n) (n 은 부호 없는 32비트, 결과 0 ~ 65535) — CtrigAsm `f_Sqrt` 와 같은 값.

    인자: n, ret([변수])
    반환: 상수면 파이썬 정수, 아니면 EUDVariable
    비용: 본문 129(1벌) / 호출 1 / 실행 33~185 (결과 비트 수에 비례) — eudplib f_sqrt(곱셈 16번, 758~1,478) 대신.
          한 번 드는 페이로드 약 41KB (eudplib f_sqrt 66KB) (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `var d = mx.isqrt(dx * dx + dy * dy);`
    출처: CtrigAsm f_Sqrt(CA:84231, 제곱 이분 탐색 — 결과 같음), 자릿수 방식은 새로 작성
    """
    fname = "mathx.isqrt"
    ret = _check_ret(fname, ret, 1)
    nv = _val(n, fname, "n")
    if _is_int(nv):
        return _const_out((math.isqrt(nv),), ret, False)
    return _call(_isqrt_fn(), (nv,), ret)


@functools.lru_cache(maxsize=None)
def _ilog2_fn(zero):
    def body(n, z=None):
        r = EUDVariable()
        if EUDIf()(n.AtLeast(1 << 16)):
            RawTrigger(actions=r.SetNumber(16))
            for i in range(17, 32):
                RawTrigger(conditions=n.AtLeast(1 << i), actions=r.AddNumber(1))
        if EUDElse()():
            RawTrigger(actions=r.SetNumber(0))
            for i in range(1, 16):
                RawTrigger(conditions=n.AtLeast(1 << i), actions=r.AddNumber(1))
            if z is None:
                RawTrigger(conditions=n.Exactly(0), actions=r.SetNumber(zero))
            else:
                if EUDIf()(n.Exactly(0)):
                    r << z
                EUDEndIf()
        EUDEndIf()
        return r

    if zero is None:

        @EUDFunc
        def lg_v(n, z):
            return body(n, z)

        return lg_v

    @EUDFunc
    def lg(n):
        return body(n)

    return lg


def f_ilog2(n, zero=SIGN, *, ret=None):
    """floor(log₂ n) (n 부호 없는 32비트). n = 0 이면 zero(기본 0x80000000 — CtrigAsm `f_Log2` 와 같음).

    인자: n, zero(상수 또는 변수), ret([변수])
    반환: 0 ~ 31 또는 zero — 상수면 파이썬 정수
    비용: 본문 37(zero 값마다 1벌) / 호출 1 / 실행 24
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `var e = mx.ilog2(n);`, `mx.ilog2(n, 0xFFFFFFFF)`
    출처: CtrigAsm f_Log2(CA:85121~85190)
    """
    fname = "mathx.ilog2"
    ret = _check_ret(fname, ret, 1)
    nv = _val(n, fname, "n")
    zv = _val(zero, fname, "zero")
    if _is_int(nv) and _is_int(zv):
        return _const_out(((nv.bit_length() - 1) if nv else zv,), ret, False)
    if _is_int(zv):
        return _call(_ilog2_fn(zv), (nv,), ret)
    return _call(_ilog2_fn(None), (nv, zv), ret)


# =============================================================================================
# 부호 나눗셈·비율
# =============================================================================================


@functools.lru_cache(maxsize=None)
def _sdiv_vv_fn(div0):
    udiv = _udivmod_fn()

    @EUDFunc
    def sd(a, b):
        q, r, flag = EUDVariable(), EUDVariable(), EUDVariable()
        RawTrigger(actions=flag.SetNumber(0))
        RawTrigger(conditions=a.AtLeast(SIGN), actions=[*_ineg(a), flag.AddNumber(1)])
        RawTrigger(conditions=b.AtLeast(SIGN), actions=[*_ineg(b), flag.AddNumber(2)])
        if div0 == "ctrig":
            if EUDIf()(b.Exactly(0)):
                SeqCompute([(q, SetTo, SMAX), (r, SetTo, a)])
                RawTrigger(conditions=flag.Exactly(1), actions=q.SetNumber(SIGN))  # 아래 부호 반전 뒤에도 0x80000000
            if EUDElse()():
                udiv(a, b, ret=[q, r])
            EUDEndIf()
        else:
            udiv(a, b, ret=[q, r])  # 0 → (0xFFFFFFFF, |a|) — 아래 부호 보정으로 eudplib f_div_towards_zero 와 같아진다
        RawTrigger(conditions=[flag.AtLeast(1), flag.AtMost(2)], actions=_ineg(q))
        RawTrigger(conditions=flag.ExactlyX(1, 1), actions=_ineg(r))
        return q, r

    return sd


@functools.lru_cache(maxsize=None)
def _sdiv_const_fn(k, div0):
    """a(변수) ÷ 상수 k (32비트 값)."""
    sk = _s32(k)
    ak = abs(sk)

    @EUDFunc
    def sdk(a):
        q, r, neg = EUDVariable(), EUDVariable(), EUDVariable()
        if ak == 0:
            zq, nq = (SMAX, SIGN) if div0 == "ctrig" else (M32, 1)
            SeqCompute([(q, SetTo, zq), (r, SetTo, a)])
            RawTrigger(conditions=a.AtLeast(SIGN), actions=q.SetNumber(nq))
            return q, r
        RawTrigger(actions=[neg.SetNumber(0), q.SetNumber(0)])
        RawTrigger(conditions=a.AtLeast(SIGN), actions=[*_ineg(a), neg.SetNumber(1)])
        # 이제 a = |피제수| ≤ 2³¹
        if ak & (ak - 1) == 0:
            sh = ak.bit_length() - 1
            SeqCompute([(q, SetTo, a), (r, SetTo, a)])
            if sh:
                q >>= sh
            RawTrigger(actions=r.SetNumberX(0, ~(ak - 1) & M32))
        else:
            top = 0
            while ak << (top + 1) <= SIGN:
                top += 1
            for i in range(top, -1, -1):
                RawTrigger(conditions=a.AtLeast(ak << i), actions=[a.AddNumber(-(ak << i) & M32), q.AddNumber(1 << i)])
            SeqCompute([(r, SetTo, a)])
        # 몫 부호 = 피제수 부호 XOR 제수 부호, 나머지 부호 = 피제수 부호
        RawTrigger(conditions=neg.Exactly(1 if sk > 0 else 0), actions=_ineg(q))
        RawTrigger(conditions=neg.Exactly(1), actions=_ineg(r))
        return q, r

    return sdk


def f_sdivmod(a, b, div0="eudplib", *, ret=None):
    """(a ÷ b 의 0 방향 몫, 피제수 부호 나머지) — 32비트 부호 있는 값. CtrigAsm `f_iDiv`/`f_iMod`, eudplib `f_div_towards_zero`.

    인자: a, b(부호 있음), div0("eudplib" 기본 | "ctrig" — 모듈 설명 "0 나눗셈"), ret([몫, 나머지])
    반환: (몫, 나머지) — 모두 상수면 파이썬 정수(음수 가능), 아니면 EUDVariable 두 개
    비용: 변수 제수 = 본문 211(정책마다 1벌, 부호 없는 나눗셈 본문 포함) / 호출 1 / 실행 약 270(새 제수)·27(같은 제수가 이어짐 —
          표 재사용). 상수 제수 = 본문 36(상수마다 1벌, 예: 7) / 실행 43, 2의 거듭제곱 본문 10 / 실행 18
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const q, m = mx.sdivmod(a, b);`
    출처: CtrigAsm f_iDiv/f_iMod(CA:30465~31105), CiDiv(CA:25314), DPS a7aad90 divide.py, eudplib 0.81 mathf/div.py
    """
    fname = "mathx.sdivmod"
    check_choice(fname + " div0", div0, DIV0)
    ret = _check_ret(fname, ret, 2)
    av = _val(a, fname, "a")
    bv = _val(b, fname, "b")
    if _is_int(av) and _is_int(bv):
        return _const_out(_sdivmod_py(av, bv, div0), ret, True)
    if _is_int(bv):
        return _call(_sdiv_const_fn(bv, div0 if bv == 0 else None), (av,), ret)
    return _call(_sdiv_vv_fn(div0), (av, bv), ret)


def f_sdiv(a, b, div0="eudplib", *, ret=None):
    """a ÷ b 의 0 방향 몫 (부호 있음). 인자·비용은 `f_sdivmod` 와 같다.

    반환: 몫 — 상수면 파이썬 정수
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `var q = mx.sdiv(a, b);`, `mx.sdiv(a, 0, "ctrig")`
    출처: `f_sdivmod`
    """
    fname = "mathx.sdiv"
    ret = _check_ret(fname, ret, 1)
    out = f_sdivmod(a, b, div0, ret=None if ret is None else [ret[0], EUDVariable()])
    return out[0]


def f_smod(a, b, div0="eudplib", *, ret=None):
    """a ÷ b 의 나머지 (피제수 부호, C 방식 — CtrigAsm `f_iMod`). b = 0 이면 a (두 정책 같음). 인자·비용은 `f_sdivmod`.

    반환: 나머지 — 상수면 파이썬 정수
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `var m = mx.smod(a, b);`
    출처: `f_sdivmod`
    """
    fname = "mathx.smod"
    ret = _check_ret(fname, ret, 1)
    out = f_sdivmod(a, b, div0, ret=None if ret is None else [EUDVariable(), ret[0]])
    return out[1]


def f_ratio(x, mul, div, div0="eudplib", *, ret=None):
    """x·mul ÷ div (곱은 32비트 wrap, 나눗셈은 0 방향 부호 나눗셈) — CtrigAsm `CA_RatioXY` 한 축과 같은 값.

    인자: x, mul, div(부호 있음, 상수·변수), div0(`f_sdivmod` 와 같음), ret([변수])
    반환: 상수면 파이썬 정수, 아니면 EUDVariable
    비용: 곱(상수 = eudplib 상수 곱 — 상수마다 본문 1벌·실행 약 35, 변수 = 절댓값 곱 약 10 + 4·비트) + `f_sdiv`.
          예: ratio(변수, 150, 100) 실행 75, ratio(변수, 변수, 변수) 189~283 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `var sx = mx.ratio(x, size, 100);`
    출처: CB Paint CA_RatioXY(CBP:9718), S1 6.3-1
    """
    fname = "mathx.ratio"
    check_choice(fname + " div0", div0, DIV0)
    ret = _check_ret(fname, ret, 1)
    xv = _val(x, fname, "x")
    mv = _val(mul, fname, "mul")
    dv = _val(div, fname, "div")
    if _is_int(xv) and _is_int(mv):
        p = _u32(xv * mv)
    elif _is_int(mv):
        p = _mul_var_const(xv, mv)
    elif _is_int(xv):
        p = _mul_var_const(mv, xv)
    else:
        p = _smul_fn()(xv, mv)
    if _is_int(p) and _is_int(dv):
        return _const_out((_sdivmod_py(p, dv, div0)[0],), ret, True)
    return f_sdiv(p, dv, div0, ret=ret)


# 파이썬 별칭 (DESIGN 3.1)
lengthdir = f_lengthdir
rotate3d = f_rotate3d
atan2 = f_atan2
atan2_sc = f_atan2_sc
to_dir256 = f_to_dir256
isqrt = f_isqrt
ilog2 = f_ilog2
sdivmod = f_sdivmod
sdiv = f_sdiv
smod = f_smod
ratio = f_ratio
