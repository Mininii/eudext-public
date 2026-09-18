"""`mathx` 파이썬 참조 구현 — CtrigAsm v5.5 원본 트리거가 내는 값을 줄 단위로 옮긴 것 (DESIGN 4.5 시험).

`eudext.mathx` 와 **따로** 짠다(표 계산도 따로: 여기서는 원본처럼 플랫폼 `math.sin/tan`, mathx 는 Decimal 정확 반올림).
t_mathx.py 가 두 표가 같은지, 그리고 에뮬레이터 결과가 이 참조와 같은지를 본다.

원문: `reference/MapSource/Library/CtrigAsm v5.5.lua` (줄 번호는 이 사본 기준, 약칭 CA)
- `f_Lengthdir` 본체 CA:84377~84638 (보통 모드 84383~84479, LengthdirX 84480~84637), 호출 틀 CA:35153~35343
- `f_Atan2` 본체 CA:84640~84841, `f_Atan2X` CA:84843~85048, 호출 틀 CA:34879~35151
- `CiDiv` 상수 제수 CA:25314~25489, `CiMod` 상수 제수 CA:26882~27060, `CNeg` CA:22466~22520 (−x, wrap)
- `f_Div` CA:30749~30781(/0 → 몫 0xFFFFFFFF), `f_iDiv` CA:30465~30609 + 31053~31105, `f_iMod` CA:30611~30746 + 30999~31050
- `f_Log2` CA:85121~85190, `f_Sqrt` CA:84231~84375(제곱 이분 탐색 = floor √x)
- `CA_Rotate`·`CA_Rotate3D`·`CA_RatioXY` = `CB Paint v2.5.lua` 9865~9932, 9718~9751
- TEP 정수화: TrigEditPlus v3.0 `Encoder/TriggerEncode.cpp:85` `luaL_checkint_Fix` = `(int)lua_tointegerx` → 실패하면
  `(int)lua_tonumberx` (C 캐스트 = 0 방향 자르기). `bit32.band` 도 `(lua_Integer)` 캐스트(`src/linit.c:37`).
- 각 변환: Lua 5.4 `math.rad(x) = x * (PI/180.0)` = 파이썬 `math.radians`. `i*90/Range` 는 두 정수(정확히 표현됨)의
  실수 나눗셈이라 파이썬 참 나눗셈과 같은 double 이다.
"""

import math

M32 = 0xFFFFFFFF
SIGN = 0x80000000


def u32(x):
    return x & M32


def s32(x):
    x &= M32
    return x - (1 << 32) if x & SIGN else x


def tep_int(v):
    """TEP 가 조건·액션 값(실수)을 정수로 바꾸는 규칙: 정수값이면 그대로, 아니면 C `(int)` 캐스트(0 방향)."""
    if isinstance(v, int):
        return u32(v)
    if v == int(v):
        return u32(int(v))
    t = int(v)  # 0 방향
    if not -(1 << 31) <= t < (1 << 31):
        return SIGN  # MSVC x86 의 정수 무한대 값 (쓰이는 범위 밖)
    return u32(t)


# ---------------------------------------------------------------------------------------------
# 표 (Include_MatheMatics — AngleCycle, Range = AngleCycle/4)
# ---------------------------------------------------------------------------------------------

_cache = {}


def sin_table(cycle):
    """CA:84385~84410 `SetDeathsX(0,SetTo,0x10000*math.sin(math.rad(i*90/Range)),0,0xFFFFFFFF)`, i = 0..Range."""
    key = ("sin", cycle)
    if key not in _cache:
        rng = cycle / 4
        _cache[key] = [tep_int(0x10000 * math.sin(math.radians(i * 90 / rng))) for i in range(int(rng) + 1)]
    return _cache[key]


def tan_table(cycle):
    """CA:84783~84800 세밀 탐색 조건 `CVar(FATAN[1],AtMost,0x10000*math.tan(math.rad(i*90/Range)))`, i = 0..Range−1."""
    key = ("tan", cycle)
    if key not in _cache:
        rng = cycle / 4
        _cache[key] = [tep_int(0x10000 * math.tan(math.radians(i * 90 / rng))) for i in range(int(rng))]
    return _cache[key]


def coarse_table():
    """CA:84672~84764 거친 8갈래 조건 `0x10000*math.tan(math.rad(k*90/8))`, k = 1..7 (주기와 무관)."""
    if "coarse" not in _cache:
        _cache["coarse"] = [None] + [tep_int(0x10000 * math.tan(math.radians(k * 90 / 8))) for k in range(1, 8)]
    return _cache["coarse"]


def precise_value(cycle, l, k):
    """CA:84481~84497 LengthdirX 파일 표 칸 (l, k): `Ret = k*math.sin(math.rad(l*90/Range))` → `bit32.band(Ret, …)` 4바이트."""
    rng = cycle / 4
    return u32(int(k * math.sin(math.radians(l * 90 / rng))))


# ---------------------------------------------------------------------------------------------
# 32비트 부품
# ---------------------------------------------------------------------------------------------


def cneg(x):
    """CA:22466 CNeg: CRet1 ← 0xFFFFFFFF, CRet1 −= X(포화지만 넘치지 않음), +1, X ← CRet1 → −X (wrap)."""
    return u32(-x)


def ci_div_const(x, d):
    """CA:25371~25489 CiDiv(Dest, 상수 d): 부호 플래그 + |Dest| 긴 나눗셈(비트 Block..0) + 부호 되돌림.

    Block = d·2^i 가 처음 2³¹ 이상이 되는 i (d 가 음수면 d = −d, 플래그 +1). d = 0 이면 Block = 0 이고
    조건 `|x| ≥ 0` 이 늘 참이라 몫 1.
    """
    x = u32(x)
    sflag = 1 if x >= SIGN else 0
    ax = cneg(x) if sflag else x
    dd = d
    if u32(dd) >= SIGN:
        dd = -dd
        sflag += 1
    block = 0
    for i in range(32):
        if u32(dd * (1 << i)) >= SIGN:
            block = i
            break
    q = 0
    rem = ax
    for i in range(block, -1, -1):
        c = dd * (1 << i)
        if rem >= c:  # CtrigX AtLeast (c < 2³² 는 위에서 보장)
            rem -= c  # Subtract (rem ≥ c 라 포화 없음)
            q += 1 << i
    q = u32(q)
    return cneg(q) if sflag & 1 else q


def ci_mod_const(x, d):
    """CA:26939~27060 CiMod(Dest, 상수 d): |Dest| 의 긴 나눗셈 나머지에 피제수 부호 (C++ 방식)."""
    x = u32(x)
    sflag = 1 if x >= SIGN else 0
    rem = cneg(x) if sflag else x
    dd = d
    if u32(dd) >= SIGN:
        dd = -dd
    block = 0
    for i in range(32):
        if u32(dd * (1 << i)) >= SIGN:
            block = i
            break
    for i in range(block, -1, -1):
        c = dd * (1 << i)
        if rem >= c:
            rem -= c
    rem = u32(rem)
    return cneg(rem) if sflag else rem


def f_div(x, y):
    """CA:30749 f_Div: 부호 없는 몫, 제수 0 이면 몫 0xFFFFFFFF."""
    x, y = u32(x), u32(y)
    return x // y if y else M32


def f_idiv(x, y):
    """CA:30465 f_iDiv (피제수 x, 제수 y): 0 방향 몫. 제수 0 → 피제수 부호로 0x7FFFFFFF / 0x80000000 (부호 보정 건너뜀)."""
    sx, sy = s32(x), s32(y)
    if sy == 0:
        return 0x7FFFFFFF if sx >= 0 else SIGN
    ax, ay = abs(sx), abs(sy)
    q = ax // ay
    return u32(-q if (sx < 0) != (sy < 0) else q)


def f_imod(x, y):
    """CA:30611 f_iMod: 나머지에 피제수 부호. 제수 0 → 피제수 그대로."""
    sx, sy = s32(x), s32(y)
    if sy == 0:
        return u32(sx)
    r = abs(sx) % abs(sy)
    return u32(-r if sx < 0 else r)


def eud_div_towards_zero(x, y):
    """eudplib 0.81 `f_div_towards_zero`(eudlib/mathf/div.py:53) — 제수 0 이면 |x| 를 부호 없는 f_div(몫 0xFFFFFFFF,
    나머지 |x|) 한 뒤 부호 보정: 몫 = x ≥ 0 이면 0xFFFFFFFF, 음수면 1 / 나머지 = x."""
    sx, sy = s32(x), s32(y)
    ax = u32(-sx) if sx < 0 else sx
    ay = u32(-sy) if sy < 0 else sy
    if ay == 0:
        q, r = M32, ax
    else:
        q, r = ax // ay, ax % ay
    flag = (1 if sx < 0 else 0) + (2 if sy < 0 else 0)
    if flag in (1, 2):
        q = u32(-q)
    if flag & 1:
        r = u32(-r)
    return u32(q), u32(r)


# ---------------------------------------------------------------------------------------------
# f_Lengthdir
# ---------------------------------------------------------------------------------------------


def norm_angle(a, cycle):
    """CA:84420~84426: `θ ≥ Cycle`(부호 없음)이면 CiMod(θ, Cycle), 그다음 `θ ≥ 0x80000000` 이면 θ += Cycle."""
    t = u32(a)
    if t >= cycle:
        t = ci_mod_const(t, cycle)
    if t >= SIGN:
        t = u32(t + cycle)
    return t


def quadrant(t, cycle):
    """CA:84428~84456 → (cos 부호, sin 부호, sin 색인, cos 색인)."""
    r = cycle // 4
    if t <= r - 1:
        return 0, 0, t, r - t
    if t <= r * 2 - 1:
        return 1, 0, r * 2 - t, t - r
    if t <= r * 3 - 1:
        return 1, 1, t - r * 2, r * 3 - t
    return 0, 1, r * 4 - t, t - r * 3


def lengthdir(r, a, cycle=360):
    """CA:84458~84472: 표 → f_Mul(32비트) → CiDiv(·, 0x10000) → 부호 플래그면 CNeg. 반환 (cos, sin) 부호 없는 32비트."""
    tbl = sin_table(cycle)
    cs, ss, si, ci = quadrant(norm_angle(a, cycle), cycle)
    s = u32(tbl[si] * r)
    c = u32(tbl[ci] * r)
    s = ci_div_const(s, 0x10000)
    c = ci_div_const(c, 0x10000)
    if cs == 1:
        c = cneg(c)
    if ss == 1:
        s = cneg(s)
    return c, s


def lengthdir_precise(r, a, cycle=360):
    """CA:84499~84637 LengthdirX: R 음수면 깃발·CNeg, R 의 하위 15비트(`SetCVar(…,0,0xFFFF8000)`)와 색인<<15 로
    파일 표를 읽고, 사분면 부호 → R 부호 순으로 CNeg."""
    rr = u32(r)
    flag9 = 0
    if rr >= SIGN:
        flag9 = 1
        rr = cneg(rr)
    cs, ss, si, ci = quadrant(norm_angle(a, cycle), cycle)
    k = rr & 0x7FFF
    c = precise_value(cycle, ci, k)
    s = precise_value(cycle, si, k)
    if cs == 1:
        c = cneg(c)
    if ss == 1:
        s = cneg(s)
    if flag9 == 1:
        c = cneg(c)
        s = cneg(s)
    return c, s


# ---------------------------------------------------------------------------------------------
# f_Atan2 / f_Atan2X
# ---------------------------------------------------------------------------------------------


def _atan2_core(dy, dx, rng, fine):
    """CA:84650~84834 (f_Atan2X 는 같은 모양에 Range = 64)."""
    y, x = u32(dy), u32(dx)
    if y >= SIGN:
        if x >= SIGN:
            q = 3
            y, x = cneg(y), cneg(x)
        else:
            q = 4
            y = cneg(y)
    else:
        if x >= SIGN:
            q = 2
            x = cneg(x)
        else:
            q = 1
    y = u32(y << 16)  # ClShift2(Y, 16)
    ratio = f_div(y, x)
    # 거친 8갈래: 처음 참인 k 에서 FuncAlloc 라벨 + 거리로 점프 (거리 0 = 빈 라벨 트리거 → i = 0 부터)
    coarse = coarse_table()
    dist = math.floor(7 * rng / 8)
    for k in range(1, 8):
        if ratio <= coarse[k]:
            dist = 1 if k == 1 else math.floor((k - 1) * rng / 8)
            break
    start = max(dist - 1, 0)
    th = rng  # 마지막 트리거: SetCVar(θ, SetTo, Range)
    for i in range(start, rng):
        if ratio <= fine[i]:
            th = i
            break
    if q == 2:
        th = u32(rng * 2 - th)  # _Sub(_Mov(Range*2), θ) — wrap
    elif q == 3:
        th = u32(th + rng * 2)
    elif q == 4:
        th = u32(rng * 4 - th)
    return th


def atan2(dy, dx, cycle=360):
    return _atan2_core(dy, dx, cycle // 4, tan_table(cycle))


def atan2_x(dy, dx):
    """CA:85038~85039: θ(256 주기) + 64, 256 이상이면 −256 (SC 방향, 0 = 위쪽)."""
    th = _atan2_core(dy, dx, 64, tan_table(256))
    v = th + 64
    if v >= 256:
        v -= 256  # Subtract (v ≥ 256 이라 포화 없음)
    return u32(v)


def atan2_first(dy, dx, cycle=360):
    """거친 탐색 없이 '처음 참인 i' 만으로 계산한 값 (atan2 와 같아야 한다 — 거친 점프가 결과를 바꾸지 않는다는 확인용)."""
    rng = cycle // 4
    fine = tan_table(cycle)
    y, x = u32(dy), u32(dx)
    q = 1
    if y >= SIGN and x >= SIGN:
        q, y, x = 3, cneg(y), cneg(x)
    elif y >= SIGN:
        q, y = 4, cneg(y)
    elif x >= SIGN:
        q, x = 2, cneg(x)
    ratio = f_div(u32(y << 16), x)
    th = next((i for i in range(rng) if ratio <= fine[i]), rng)
    return u32({1: th, 2: rng * 2 - th, 3: th + rng * 2, 4: rng * 4 - th}[q])


# ---------------------------------------------------------------------------------------------
# 회전·비율 (CB Paint CA_)
# ---------------------------------------------------------------------------------------------


def rotate(x, y, a, cycle=360, precise=False):
    """CBP:9865 CA_Rotate: (xc, xs) = LD(x), (yc, ys) = LD(y), x' = xc − ys (_iSub, wrap), y' = xs + yc (_Add)."""
    ld = lengthdir_precise if precise else lengthdir
    xc, xs = ld(x, a, cycle)
    yc, ys = ld(y, a, cycle)
    return u32(xc - ys), u32(xs + yc)


def rotate3d(x, y, xy=None, yz=None, zx=None, cycle=360, precise=False):
    """CBP:9883 CA_Rotate3D. Z 는 0 에서 시작, 각이 nil 인 단계는 건너뛴다. 반환 (X, Y, Z)."""
    ld = lengthdir_precise if precise else lengthdir
    X, Y, Z = u32(x), u32(y), 0
    if xy is not None:
        c11, c12 = ld(X, xy, cycle)
        c13, c14 = ld(Y, xy, cycle)
        X, Y = u32(c11 - c14), u32(c12 + c13)
    if yz is not None:
        c13, c14 = ld(Y, yz, cycle)
        Y, Z = c13, c14
    if zx is not None:
        c11, _c12 = ld(X, zx, cycle)
        _c13, c14 = ld(Z, zx, cycle)
        X = u32(c11 - c14)
    return X, Y, Z


def ratio(x, mul, div, div0="eudplib"):
    """CBP:9718 CA_RatioXY: X ← X·mul (32비트) → 부호 나눗셈. 제수 0 은 sdiv 의 정책."""
    return sdiv(u32(x * mul), div, div0)[0]


def sdiv(a, b, div0="eudplib"):
    """부호 나눗셈 (몫, 나머지). b ≠ 0 이면 CiDiv/f_iDiv/f_iMod/eudplib 모두 0 방향 몫·피제수 부호 나머지로 같다.
    b = 0: "eudplib" = eudplib f_div_towards_zero, "ctrig" = CtrigAsm f_iDiv·f_iMod."""
    if u32(b) == 0:
        if div0 == "eudplib":
            return eud_div_towards_zero(a, b)
        return f_idiv(a, b), f_imod(a, b)
    q1, r1 = eud_div_towards_zero(a, b)
    assert (q1, r1) == (f_idiv(a, b), f_imod(a, b))
    return q1, r1


def to_dir256(a, cycle=360):
    """S4 2.3: (floor((a mod cycle)·256/cycle) + 64) mod 256, a mod cycle 는 CiMod 규칙(norm_angle)."""
    return (norm_angle(a, cycle) * 256 // cycle + 64) % 256


def to_dir256_tep(a):
    """S4 2.3 사용자 표 `Angle360to256[i+1] = (i/360)*256` → bit32.band 자르기, + 64, f_Mod 256 (cycle 360 전용)."""
    t = norm_angle(a, 360)
    return (int((t / 360) * 256) + 64) % 256


def isqrt(n):
    return math.isqrt(u32(n))


def ilog2(n, zero=SIGN):
    """CA:85121 f_Log2: 0 → 0x80000000, 1 → 0, 그 밖 floor(log2 n)."""
    n = u32(n)
    if n == 0:
        return u32(zero)
    return n.bit_length() - 1
