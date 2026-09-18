"""정확 반올림(correctly rounded) 수학 함수 — `shape` 의 lupa Lua `math` 표에 넣는다 (DESIGN 4.13 "수학 함수").

왜: CB Paint 도형 좌표는 `int()` 자르기(D6)라 C 라이브러리 `sin`/`tan` 의 1ulp 차이가 점 하나를 바꾼다.
star(`CSMakeStar(5,144,96,0,CS_Level('Star',5,3),0)`) 6번째 점 y 의 참값은 정확히 48 인데 double 연쇄 계산은 48 의 위아래
몇 ulp 이고, 어느 쪽인지가 플랫폼마다 달랐다(2026-09-17 Windows 조사 — 정확 반올림·Windows x64/x86 ucrt·**원본 플러그인
TrigEditPlus3.0.sdp(32비트 정적 CRT)** = 47, glibc(Ubuntu 기록)·mingw(tepc) = 48). 원본 플러그인과 같은 값을 모든 OS 에서 내려고
IEEE 가 정확 반올림을 보장하지 않는 함수만 여기의 구현으로 바꾼다. 표본(맵 소스 리터럴 도형식 426개·매개변수 격자 1,166개)에서
정확 반올림은 원본 플러그인과 좌표 차이 0점이었다.

바꾸는 것 (Lua 5.4.4 `lmathlib.c` 와 같은 뜻):
    math.sin, math.cos, math.tan, math.asin, math.acos     C 의 같은 이름 함수
    math.atan(y [, x = 1])                                  C `atan2(y, x)`
    math.exp                                                C `exp`
    math.log(x [, b])                                       b 없음 `log`, b == 2 `log2`, b == 10 `log10`, 그 밖 `log(x)/log(b)`(double 나눗셈)
그대로 두는 것 (모든 플랫폼에서 비트가 같다):
    math.sqrt(IEEE 정확 반올림), floor/ceil/fmod/modf/abs/max/min/tointeger/ult/type(정확한 연산),
    math.rad·math.deg = `x * (PI/180.0)`·`x * (180.0/PI)` 곱셈 한 번(상수는 컴파일 때 double 로 접힌다 — 원본 플러그인 기계어가
    0x3F91DF46A2529D39 = 0.017453292519943295, 0x404CA5DC1A63C1F8 = 57.29577951308232 를 곱한다, 2026-09-17 역어셈블 확인),
    math.random/randomseed(xoshiro256**, 정수 연산), `+ - * /`.
    `^` 는 Lua 5.4 `luai_numpow` = `(b == 2) ? a*a : pow(a, b)` 이고 숫자끼리는 메타 방법이 없어 바꿀 수 없다. CB Paint·CSMakeSpiral·
    CS_Addon 의 `^` 는 `^2`(곱셈 — 정확) 뿐이고, 예외는 `CS_Round`·`CXRound` 의 `10^Digit` 하나다(정수 Digit 0~22 는 결과가 double 로
    정확히 표현되어 ucrt·glibc·mingw 모두 같은 값 — 시험함. 음수·소수 Digit 은 플랫폼 pow 에 맡긴다).

방식: 파이썬 `decimal`(표준 모듈 — euddraft 0.11 번들 3.14 에도 `_decimal` 이 있다)로 고정밀 근삿값을 구하고, 근삿값 ± 오차 한계의
두 끝이 같은 double 로 반올림될 때까지 정밀도를 올린다(Ziv 방식, 36 → 72 → 144 → 288 → 576 자리). `math`·C 라이브러리 결과에는
기대지 않는다(특수값 판정만 `math.isnan`/`isinf`). 특수값은 C99 부록 F 규칙(±0 부호 유지, 극점 ±inf, 정의역 밖은 NaN — x86 기본
NaN 과 같은 부호 비트 1 의 quiet NaN, NaN 입력은 그대로 돌려줌).

캐시: 파이썬 쪽은 함수별 dict(프로세스 전체 공유), Lua 쪽은 런타임마다 인자 → 결과 표(파이썬 호출을 건너뛴다). ±0·NaN 은
Lua 표 열쇠로 쓸 수 없어(-0.0 이 0 으로 정규화된다) 캐시를 거치지 않는다.

출처: TrigEditPlus v3.0 `Encoder/Lua/lmathlib.c`(Lua 5.4.4 — math_sin~math_log, math_rad), `llimits.h:326` luai_numpow,
2026-09-17 Windows 조사 스크립트 `fpx/crmath.py`(이 모듈의 원형)·`plugcalc.py`(원본 플러그인 CRT 기계어 호출) — 세션 임시 폴더에 있었고
저장소에는 두지 않았다(결과는 tests/t_shape.py PLUGIN_MEASURED), C99 부록 F.9.
"""

import math
import struct
import threading
from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    ROUND_HALF_EVEN,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)

__all__ = [
    "LUA_GLUE",
    "acos",
    "asin",
    "atan",
    "atan2",
    "cache_info",
    "clear_cache",
    "cos",
    "exp",
    "install_lua",
    "log",
    "log10",
    "log2",
    "sin",
    "tan",
]

# 정의역 밖 결과: x86 기본 NaN(부호 비트 1, quiet) — MSVC ucrt·glibc x86-64 가 내는 것과 같은 비트
NAN_INVALID = struct.unpack("<d", struct.pack("<Q", 0xFFF8000000000000))[0]
_INF = float("inf")

# Ziv 단계(유효 자리 수). 첫 단계에서 거의 모두 끝난다(정확 반올림이 까다로운 인자라도 double 에는 약 40자리면 충분)
_LEVELS = (36, 72, 144, 288, 576)
_GUARD = 15  # 급수·나눗셈의 반올림 오차 누적 여유(자리)
_REDUCE_GUARD = 25  # π/2 배수에 가장 가까운 double 도 4.7e-19 이상 떨어져 있다(Kahan) → 빼기에서 잃는 자리 + 여유

_D005 = Decimal("0.05")
_lock = threading.Lock()


def _ctx(prec):
    # 사용자 전역 decimal 문맥(반올림 방식 등)에 흔들리지 않게 늘 새 문맥을 쓴다
    return localcontext(Context(prec=prec, rounding=ROUND_HALF_EVEN, Emax=MAX_EMAX, Emin=MIN_EMIN,
                                traps=[InvalidOperation, DivisionByZero, Overflow], flags=[]))


# ---------------------------------------------------------------------------------------------
# π (Machin 공식, 정수 고정소수점) — 필요한 자리만큼 늘려 둔다
# ---------------------------------------------------------------------------------------------

_pi_cache = [0, None]  # [자리 수, Decimal]


def _arctan_inv(n, scale):
    # atan(1/n) · scale (정수, 항마다 1 이하 오차)
    total = term = scale // n
    n2 = n * n
    k = 1
    sign = -1
    while term:
        term //= n2
        k += 2
        total += sign * (term // k)
        sign = -sign
    return total


def _pi(prec):
    """π 를 prec 자리 이상으로(쓰는 쪽 문맥에서 연산할 때 반올림된다)."""
    if _pi_cache[0] < prec:
        with _lock:
            if _pi_cache[0] < prec:
                digits = max(prec + 20, 2 * _pi_cache[0])
                guard = 12
                scale = 10 ** (digits + guard)
                v = 16 * _arctan_inv(5, scale) - 4 * _arctan_inv(239, scale)
                # scaleb 는 문맥 정밀도로 반올림한다 — 호출자 문맥(기본 28자리일 수도 있다)이 아니라 전용 문맥으로
                _pi_cache[1] = Decimal(v).scaleb(-(digits + guard), context=Context(prec=digits + guard + 10))
                _pi_cache[0] = digits
    return _pi_cache[1]


# ---------------------------------------------------------------------------------------------
# 고정밀 근삿값 (문맥 정밀도 안에서 계산)
# ---------------------------------------------------------------------------------------------


def _sin_ser(r):
    r2 = r * r
    s = term = r
    n = 1
    while True:
        term = -term * r2 / ((n + 1) * (n + 2))
        n += 2
        t = s + term
        if t == s:
            return s
        s = t


def _cos_ser(r):
    r2 = r * r
    s = term = Decimal(1)
    n = 0
    while True:
        term = -term * r2 / ((n + 1) * (n + 2))
        n += 2
        t = s + term
        if t == s:
            return s
        s = t


def _reduce(dx, w):
    """정확한 Decimal x → (q mod 4, r): x = q·π/2 + r, |r| ≲ π/4. r 의 상대 오차 < 10^-(w+4)."""
    wr = w + max(0, dx.adjusted()) + _REDUCE_GUARD
    with _ctx(wr):
        hp = +_pi(wr) / 2
        q = (dx / hp).to_integral_value()
        r = dx - q * hp
    return int(q) % 4, r


def _atan_d(t, pi):
    """Decimal t → atan(t) (현재 문맥 정밀도). pi: 문맥보다 긴 π."""
    if not t:
        return t
    neg = t < 0
    t = abs(t)
    inv = t > 1
    if inv:
        t = 1 / t
    k = 0
    while t > _D005:  # 반각 공식 atan(t) = 2·atan(t / (1 + √(1+t²)))
        t = t / (1 + (1 + t * t).sqrt())
        k += 1
    t2 = t * t
    s = pw = t
    n = 1
    sign = 1
    while True:
        pw = pw * t2
        n += 2
        sign = -sign
        u = s + sign * pw / n
        if u == s:
            break
        s = u
    s = s * (1 << k)
    if inv:
        s = +pi / 2 - s  # 단항 + 로 문맥 정밀도에 맞춘다
    return -s if neg else s


def _ax_sin(x, p):
    q, r = _reduce(Decimal(x), p + _GUARD)
    with _ctx(p + _GUARD):
        v = _cos_ser(r) if q & 1 else _sin_ser(r)
        return -v if q >= 2 else v


def _ax_cos(x, p):
    q, r = _reduce(Decimal(x), p + _GUARD)
    with _ctx(p + _GUARD):
        v = _sin_ser(r) if q & 1 else _cos_ser(r)
        return -v if q in (1, 2) else v


def _ax_tan(x, p):
    q, r = _reduce(Decimal(x), p + _GUARD)
    with _ctx(p + _GUARD + 5):
        s, c = _sin_ser(r), _cos_ser(r)
        return -c / s if q & 1 else s / c


def _ax_atan2(yx, p):
    y, x = yx
    w = p + _GUARD + 5
    pi = _pi(w)
    with _ctx(w):
        a = _atan_d(Decimal(y) / Decimal(x), pi)
        if x < 0:
            a = a + pi if y > 0 else a - pi
        return a


def _ax_asin(v, p):
    w = p + _GUARD + 20  # 1 − v² 의 자리 손실 여유
    pi = _pi(w)
    with _ctx(w):
        d = Decimal(v)
        return _atan_d(d / ((1 - d) * (1 + d)).sqrt(), pi)


def _ax_acos(v, p):
    w = p + _GUARD + 20
    pi = _pi(w)
    with _ctx(w):
        d = Decimal(v)
        return 2 * _atan_d(((1 - d) / (1 + d)).sqrt(), pi)  # 뺄셈 없는 식 (v → ±1 에서도 자리 손실 없음)


def _ax_exp(x, p):
    with _ctx(p + 5):
        return Decimal(x).exp()  # decimal 의 exp/ln/log10 은 문맥 정밀도에서 정확 반올림


def _ax_log(x, p):
    with _ctx(p + 5):
        return Decimal(x).ln()


def _ax_log2(x, p):
    with _ctx(p + _GUARD):
        return Decimal(x).ln() / Decimal(2).ln()


def _ax_log10(x, p):
    with _ctx(p + 5):
        return Decimal(x).log10()


def _ax_const(k, p):
    # k: "pi" | "pi/2" | "pi/4" | "3pi/4"
    w = p + _GUARD
    with _ctx(w):
        pi = +_pi(w)
        return {"pi": pi, "pi/2": pi / 2, "pi/4": pi / 4, "3pi/4": 3 * pi / 4}[k]


def _ziv(approx, arg):
    """approx(arg, p) 의 두 끝(± 10^-(p-2) 상대)이 같은 double 로 반올림될 때까지 p 를 올린다."""
    y = None
    for p in _LEVELS:
        y = approx(arg, p)
        if not y:
            return 0.0
        with _ctx(p + 10):
            e = abs(y).scaleb(-(p - 2))
            lo = float(y - e)  # Decimal → float 는 문자열 경유 정확 반올림(round-half-even, 비정규·넘침 포함)
            hi = float(y + e)
        if lo == hi:
            return lo
    return float(y)


# ---------------------------------------------------------------------------------------------
# 공개(모듈 안) 함수 — 인자 int/float, 결과 float
# ---------------------------------------------------------------------------------------------

_caches = {}


def _cache(name):
    c = _caches.get(name)
    if c is None:
        c = _caches[name] = {}
    return c


def _memo(name, approx, x):
    c = _cache(name)
    r = c.get(x)
    if r is None:
        r = c[x] = _ziv(approx, x)
    return r


def _const(k):
    return _memo("const", _ax_const, k)


def sin(x):
    """정확 반올림 sin. 인자: 수(int·float). 반환: float. 특수값: NaN → 그대로, ±inf → NaN, ±0 → ±0."""
    x = float(x)
    if x != x:
        return x
    if x == 0:
        return x
    if math.isinf(x):
        return NAN_INVALID
    return _memo("sin", _ax_sin, x)


def cos(x):
    """정확 반올림 cos. 특수값: NaN → 그대로, ±inf → NaN, ±0 → 1."""
    x = float(x)
    if x != x:
        return x
    if x == 0:
        return 1.0
    if math.isinf(x):
        return NAN_INVALID
    return _memo("cos", _ax_cos, x)


def tan(x):
    """정확 반올림 tan. 특수값: NaN → 그대로, ±inf → NaN, ±0 → ±0."""
    x = float(x)
    if x != x:
        return x
    if x == 0:
        return x
    if math.isinf(x):
        return NAN_INVALID
    return _memo("tan", _ax_tan, x)


def asin(v):
    """정확 반올림 asin. 특수값: NaN → 그대로, |v| > 1 → NaN, ±0 → ±0, ±1 → ±π/2."""
    v = float(v)
    if v != v:
        return v
    if v == 0:
        return v
    if not -1.0 <= v <= 1.0:
        return NAN_INVALID
    if v == 1.0:
        return _const("pi/2")
    if v == -1.0:
        return -_const("pi/2")
    return _memo("asin", _ax_asin, v)


def acos(v):
    """정확 반올림 acos. 특수값: NaN → 그대로, |v| > 1 → NaN, 1 → +0, −1 → π."""
    v = float(v)
    if v != v:
        return v
    if not -1.0 <= v <= 1.0:
        return NAN_INVALID
    if v == 1.0:
        return 0.0
    if v == -1.0:
        return _const("pi")
    if v == 0:
        return _const("pi/2")
    return _memo("acos", _ax_acos, v)


def atan2(y, x):
    """정확 반올림 atan2(y, x) — C99 F.9.1.4 특수값(±0·±inf 조합) 그대로. NaN 이 있으면 그 NaN(y 먼저)."""
    y = float(y)
    x = float(x)
    if y != y:
        return y
    if x != x:
        return x
    neg_x = math.copysign(1.0, x) < 0
    if y == 0:
        if neg_x:
            return math.copysign(_const("pi"), y)
        return y  # ±0
    if math.isinf(y):
        if math.isinf(x):
            return math.copysign(_const("3pi/4") if neg_x else _const("pi/4"), y)
        return math.copysign(_const("pi/2"), y)
    if x == 0:
        return math.copysign(_const("pi/2"), y)
    if math.isinf(x):
        return math.copysign(_const("pi"), y) if neg_x else math.copysign(0.0, y)
    return _memo("atan2", _ax_atan2, (y, x))


def atan(y):
    """정확 반올림 atan(y) = atan2(y, 1) (Lua 5.4 math.atan 의 인자 하나 꼴)."""
    return atan2(y, 1.0)


def exp(x):
    """정확 반올림 exp. 특수값: NaN → 그대로, +inf → +inf, −inf → +0, ±0 → 1, 넘침 → +inf, 아래 넘침 → +0."""
    x = float(x)
    if x != x:
        return x
    if x == 0:
        return 1.0
    if x > 710.0:  # ln(DBL_MAX) ≈ 709.7827 — 그 사이는 decimal → float 반올림이 inf 를 낸다
        return _INF
    if x < -746.0:  # exp(−746) < 최소 비정규 수의 절반 → +0
        return 0.0
    return _memo("exp", _ax_exp, x)


def _log_special(x):
    if x != x:
        return x
    if x < 0:
        return NAN_INVALID
    if x == 0:
        return -_INF
    if math.isinf(x):
        return x
    if x == 1.0:
        return 0.0
    return None


def log(x):
    """정확 반올림 자연로그. 특수값: NaN → 그대로, x < 0 → NaN, ±0 → −inf, +inf → +inf, 1 → +0."""
    x = float(x)
    r = _log_special(x)
    return _memo("log", _ax_log, x) if r is None else r


def log2(x):
    """정확 반올림 log2 (2 의 거듭제곱은 정확한 정수). 특수값은 `log` 와 같다."""
    x = float(x)
    r = _log_special(x)
    return _memo("log2", _ax_log2, x) if r is None else r


def log10(x):
    """정확 반올림 log10 (10 의 거듭제곱은 정확한 정수). 특수값은 `log` 와 같다."""
    x = float(x)
    r = _log_special(x)
    return _memo("log10", _ax_log10, x) if r is None else r


def cache_info():
    """함수별 캐시에 든 인자 수 {이름: 개수} (측정용)."""
    return {k: len(v) for k, v in _caches.items()}


def clear_cache():
    """파이썬 쪽 캐시(결과·π)를 비운다(측정·시험용 — Lua 런타임 쪽 표는 런타임마다 따로라 그대로)."""
    with _lock:
        _caches.clear()
        _pi_cache[:] = [0, None]


# ---------------------------------------------------------------------------------------------
# Lua 연결
# ---------------------------------------------------------------------------------------------

# 인자 검사는 luaL_checknumber/luaL_optnumber 와 같게(수, 수로 바뀌는 문자열) — 오류 문구도 원본 꼴
LUA_GLUE = r"""
local psin, pcos, ptan, pasin, pacos, patan2, pexp, plog, plog2, plog10 = ...
local type, tonumber, select, error, format = type, tonumber, select, error, string.format
local M = math

-- 수가 아닌 인자: 수로 바뀌는 문자열이면 수, 아니면 "bad argument" (error 수준 3 = math.* 를 부른 곳)
local function tonum(nargs, v, i, fname)
    if type(v) == "string" then
        local r = tonumber(v)
        if r then return r end
    end
    local got = (nargs < i) and "no value" or type(v)
    error(format("bad argument #%d to '%s' (number expected, got %s)", i, fname, got), 3)
end

-- 인자 하나 함수 + 결과 표. ±0 은 표 열쇠가 0 으로 정규화되고 NaN 은 열쇠가 될 수 없어 캐시를 건너뛴다
local function memo1(f)
    local memo = {}
    return function(x)
        if x == 0 or x ~= x then return f(x) end
        local r = memo[x]
        if r == nil then
            r = f(x)
            memo[x] = r
        end
        return r
    end
end

local function wrap1(fname, f)
    local g = memo1(f)
    return function(...)
        local x = ...
        if type(x) ~= "number" then x = tonum(select("#", ...), x, 1, fname) end
        return g(x)
    end
end

local memo2 = {}
local function atan2m(y, x)
    if y == 0 or x == 0 or y ~= y or x ~= x then return patan2(y, x) end
    local t = memo2[y]
    if t == nil then
        t = {}
        memo2[y] = t
    end
    local r = t[x]
    if r == nil then
        r = patan2(y, x)
        t[x] = r
    end
    return r
end

M.sin = wrap1("sin", psin)
M.cos = wrap1("cos", pcos)
M.tan = wrap1("tan", ptan)
M.asin = wrap1("asin", pasin)
M.acos = wrap1("acos", pacos)
M.exp = wrap1("exp", pexp)

-- math_atan: atan2(y, luaL_optnumber(2, 1))
M.atan = function(...)
    local y, x = ...
    if type(y) ~= "number" then y = tonum(select("#", ...), y, 1, "atan") end
    if x == nil then
        x = 1.0
    elseif type(x) ~= "number" then
        x = tonum(2, x, 2, "atan")
    end
    return atan2m(y, x)
end

-- math_log: 밑 없음 log, 2 → log2, 10 → log10, 그 밖 log(x)/log(b)
local mlog, mlog2, mlog10 = memo1(plog), memo1(plog2), memo1(plog10)
M.log = function(...)
    local x, b = ...
    if type(x) ~= "number" then x = tonum(select("#", ...), x, 1, "log") end
    if b == nil then return mlog(x) end
    if type(b) ~= "number" then b = tonum(2, b, 2, "log") end
    if b == 2 then return mlog2(x) end
    if b == 10 then return mlog10(x) end
    return mlog(x) / mlog(b)
end
return true
"""


def install_lua(L):
    """lupa Lua 5.4 런타임 L 의 `math` 표에 정확 반올림 함수를 넣는다(모듈 설명의 "바꾸는 것").

    인자: L(`lupa.lua54.LuaRuntime` — 부르는 쪽이 `tools/lua_consts.lua_c_locale()` 가드 안에서 부른다)
    반환: None
    비용: 없음(컴파일 시점). 처음 보는 인자는 decimal 계산(호출당 수십~수백 µs), 이후는 Lua 표에서 바로
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다 (`shape.new_lua_runtime()` 이 부른다)
    출처: TrigEditPlus v3.0 `Encoder/Lua/lmathlib.c`(math_sin~math_log), `lauxlib.c` luaL_checknumber·luaL_typeerror
    """
    # 한글 주석이 있어 UTF-8 바이트로 넘긴다(shape 런타임은 latin-1 이라 str 은 인코딩 오류)
    L.execute(LUA_GLUE.encode("utf-8"), sin, cos, tan, asin, acos, atan2, exp, log, log2, log10)
