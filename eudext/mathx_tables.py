"""`mathx` 표 계산 — CtrigAsm `Include_MatheMatics` 가 컴파일할 때 만드는 표를 **플랫폼과 상관없이** 같은 값으로 만든다.

CtrigAsm(TEP, Lua 5.4) 은 `0x10000*math.sin(math.rad(i*90/Range))` 같은 실수를 트리거 값으로 넣고, TEP 가 C `(int)`
캐스트로 0 방향으로 자른다(`TriggerEncode.cpp:85 luaL_checkint_Fix`). 결과는 C 라이브러리의 `sin`/`tan` 이 돌려준
double 에 달려 있다. sin 30° = 0.49999999999999994, tan 45° = 0.9999999999999999 처럼 자르기 경계에 붙은 값이 있어
(T[30] = 32767, 표 45 = 65535 → (1, 1) 의 atan2 가 46), 라이브러리마다 1ulp 만 달라도 결과가 바뀐다.

그래서 여기서는 sin·tan 을 `decimal` 로 50자리까지 구한 뒤 가장 가까운 double 로 반올림한다(= 정확 반올림 라이브러리 값).
Linux glibc 의 `math.sin/tan` 과 같은 값인지는 `tests/t_mathx.py` 가 여러 주기에서 확인한다. Windows(euddraft 번들 파이썬,
MSVC UCRT)에서 빌드해도 표가 같다. 원본 TEP(Win32 UCRT)의 값이 정확 반올림과 같은지는 인게임 항목 C9-1 로 확인한다.

이 모듈은 eudplib 을 쓰지 않는다(컴파일 시점 순수 계산). 다른 모듈(shape·plot·bullet)도 불러 쓸 수 있다.

    from eudext import mathx_tables as mt
    mt.sin_table(360)[30]      # 32767
    mt.atan_thresholds(360)[45] # 65535

출처: CtrigAsm v5.5 `Include_MatheMatics` 표(CA:84385~84410 sin, 84783~84800 tan, 84672~84764 거친 tan,
84481~84497 LengthdirX 파일 표), S4 2.3(`Angle360to256`).
"""

import array
import functools
import math
from decimal import Decimal, localcontext

__all__ = [
    "MAX_CYCLE",
    "SIN_SCALE",
    "atan_thresholds",
    "check_cycle",
    "coarse_thresholds",
    "cr_sin",
    "cr_tan",
    "f_atan_thresholds",
    "f_sin_table",
    "packed_sin_table",
    "precise_table_bytes",
    "precise_table_size",
    "sin_table",
]

SIN_SCALE = 0x10000
MAX_CYCLE = 65536  # 세밀 탐색 문턱이 2³¹ 을 넘지 않는 범위 (cycle/4 = 16384 → tan 최대 약 6.8억)
_PREC = 50


def check_cycle(cycle, fname="mathx"):
    """cycle 이 4 의 배수이고 4 ~ MAX_CYCLE 인 정수인지 검사하고 그대로 돌려준다(오류는 EudextError)."""
    from eudext.errors import fail

    if isinstance(cycle, bool) or not isinstance(cycle, int):
        fail("%s: cycle 은 정수 상수여야 합니다 (%r)", fname, cycle)
    if cycle < 4 or cycle > MAX_CYCLE or cycle % 4:
        fail("%s: cycle 은 4 ~ %d 의 4의 배수여야 합니다 (받은 값 %d)", fname, MAX_CYCLE, cycle)
    return cycle


def _series(x, first, start_n):
    """sin(first=x, n=1) 또는 cos(first=1, n=0) 테일러 급수 (Decimal)."""
    total = Decimal(0)
    term = first
    n = start_n
    eps = Decimal(10) ** -(_PREC + 5)
    while abs(term) > eps:
        total += term
        term = -term * x * x / ((n + 1) * (n + 2))
        n += 2
    return total


def _rad(deg_num, deg_den):
    """Lua `math.rad(i*90/Range)` 와 같은 double: (정수/정수 실수 나눗셈) × (π/180) — 파이썬 math.radians 와 같은 연산."""
    return math.radians(deg_num / deg_den)


@functools.lru_cache(maxsize=None)
def cr_sin(deg_num, deg_den):
    """sin(math.rad(deg_num/deg_den)) 의 정확 반올림 double."""
    x = _rad(deg_num, deg_den)
    with localcontext() as ctx:
        ctx.prec = _PREC
        return float(_series(Decimal(x), Decimal(x), 1))


@functools.lru_cache(maxsize=None)
def cr_tan(deg_num, deg_den):
    """tan(math.rad(deg_num/deg_den)) 의 정확 반올림 double (deg < 90)."""
    x = _rad(deg_num, deg_den)
    with localcontext() as ctx:
        ctx.prec = _PREC
        d = Decimal(x)
        return float(_series(d, d, 1) / _series(d, Decimal(1), 0))


def _tep_int(v):
    """TEP 정수화: 정수값이면 그대로, 아니면 0 방향 자르기 (쓰는 값은 모두 0 이상 2³¹ 미만)."""
    return int(v)


@functools.lru_cache(maxsize=None)
def sin_table(cycle):
    """T[i] = trunc(0x10000·sin(i·90/Q °)), i = 0..Q (Q = cycle/4). 튜플.

    예: sin_table(360)[30] = 32767, [45] = 46340, [90] = 65536.
    출처: CA:84385~84410
    """
    check_cycle(cycle, "sin_table")
    q = cycle // 4
    return tuple(_tep_int(SIN_SCALE * cr_sin(i * 90, q)) for i in range(q + 1))


@functools.lru_cache(maxsize=None)
def atan_thresholds(cycle):
    """A[i] = trunc(0x10000·tan(i·90/Q °)), i = 0..Q−1 — f_Atan2 세밀 탐색 문턱(`비율 ≤ A[i]` 인 첫 i). 튜플.

    예: atan_thresholds(360)[45] = 65535 (그래서 (1, 1) → 46).
    출처: CA:84783~84800
    """
    check_cycle(cycle, "atan_thresholds")
    q = cycle // 4
    out = tuple(_tep_int(SIN_SCALE * cr_tan(i * 90, q)) for i in range(q))
    if any(b < a for a, b in zip(out, out[1:])):  # 계수 방식(eudext)이 '처음 참인 i' 와 같으려면 단조여야 한다
        raise AssertionError("atan_thresholds(%d) 가 단조가 아닙니다" % cycle)
    return out


@functools.lru_cache(maxsize=None)
def coarse_thresholds():
    """f_Atan2 거친 8갈래 문턱 C[k] = trunc(0x10000·tan(k·90/8 °)), k = 1..7 (C[0] = None). 참고용(결과에 영향 없음)."""
    return (None,) + tuple(_tep_int(SIN_SCALE * cr_tan(k * 90, 8)) for k in range(1, 8))


@functools.lru_cache(maxsize=None)
def packed_sin_table(cycle):
    """P[i] = (T[i] + T[Q−i]·0x10000) mod 2³², i = 0..Q — sin·cos 표 값을 한 칸에 담은 것 (i = 0, Q 는 넘쳐서 따로 고친다)."""
    t = sin_table(cycle)
    q = cycle // 4
    return tuple((t[i] + (t[q - i] << 16)) & 0xFFFFFFFF for i in range(q + 1))


def precise_table_size(cycle):
    """LengthdirX 표 바이트 수 = (Q+1) × 32768 × 4. cycle 360 → 11,927,552."""
    check_cycle(cycle, "precise_table_size")
    return (cycle // 4 + 1) * 32768 * 4


@functools.lru_cache(maxsize=4)
def precise_table_bytes(cycle):
    """LengthdirX 파일 표: 칸 (l, k) = trunc(k·sin(l·90/Q °)) (dword, 리틀 엔디언), l = 0..Q, k = 0..32767.

    원본은 `k*math.sin(…)` 을 double 로 곱한 뒤 `bit32.band` 로 자른다 → 여기서도 double 곱(IEEE, 플랫폼 무관) 후 int().
    출처: CA:84481~84497
    """
    q = cycle // 4
    out = array.array("I")
    for l in range(q + 1):
        s = cr_sin(l * 90, q)
        out.extend(int(k * s) for k in range(32768))
    if out.itemsize != 4:
        raise AssertionError("array('I') 가 4바이트가 아닙니다")
    if array.array("I", [1]).tobytes() != b"\x01\x00\x00\x00":
        out.byteswap()
    return out.tobytes()


def f_sin_table(cycle):
    """`sin_table` 의 epScript 이름 (컴파일 시점 계산, 트리거 없음)."""
    return sin_table(cycle)


def f_atan_thresholds(cycle):
    """`atan_thresholds` 의 epScript 이름 (컴파일 시점 계산, 트리거 없음)."""
    return atan_thresholds(cycle)
