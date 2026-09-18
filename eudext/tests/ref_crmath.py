"""정확 반올림 수학의 고정밀 기준값 (eudext._crmath 와 다른 알고리즘) — tests/t_shape.py 가 쓴다.

`_crmath` 는 π/2 단위 줄이기 + 반각 atan 급수 + decimal exp/ln + Ziv 반올림이다. 여기서는 일부러 다르게 짰다:
- π: decimal 문서의 급수 레시피, sin/cos: 2π 단위로 줄인 뒤 [−π, π] 에서 테일러 급수, tan = sin/cos
- atan: 파이썬 `math.atan` 을 첫 값으로 한 뉴턴 반복(sin·cos 급수로 tan(a) = t 풀기), |t| > 1 은 π/2 − atan(1/t)
- asin/acos: atan 과 √ 로, acos = π/2 − asin (자리를 넉넉히 잡아 뺄셈 손실을 덮는다)
- exp: 인자를 2^k 로 나눈 테일러 급수를 k 번 제곱, log: exp 로 하는 핼리 반복, log2/log10 = log(x)/log(2|10)
결과는 `PREC`(기본 90)자리 근삿값을 문자열 → float 로 반올림한다(double 의 가장 까다로운 인자도 40자리 안팎이면 충분).
특수값(±0·inf·NaN·정의역 밖)은 다루지 않는다 — 시험이 따로 적은 표로 본다.

python tests/ref_crmath.py 로 자체 점검(이 플랫폼 math 와 1ulp 이내인지)을 돌린다.
"""

import math
from decimal import Decimal as D
from decimal import localcontext

PREC = 90


def _pi_recipe(prec):
    with localcontext() as c:
        c.prec = prec + 2
        three = D(3)
        lasts, t, s, n, na, d, da = 0, three, 3, 1, 0, 0, 24
        while s != lasts:
            lasts = s
            n, na = n + na, na + 8
            d, da = d + da, da + 32
            t = (t * n) / d
            s += t
        return +s


_PI = {}


def pi(prec):
    if prec not in _PI:
        _PI[prec] = _pi_recipe(prec)
    return _PI[prec]


def _prec_for(x):
    e = D(x).adjusted() if x else 0
    return PREC + max(0, e) + 30


def _sin_cos(x):
    """x(float) → (sin, cos) Decimal (문맥 정밀도 = _prec_for)."""
    p = _prec_for(x)
    with localcontext() as c:
        c.prec = p
        tp = 2 * pi(p + 5)
        r = D(x)
        k = (r / tp).to_integral_value()
        r = r - k * tp
        r2 = r * r
        # sin
        s, term, i = r, r, 1
        while True:
            term = -term * r2 / ((i + 1) * (i + 2))
            i += 2
            if s + term == s:
                break
            s += term
        co, term, i = D(1), D(1), 0
        while True:
            term = -term * r2 / ((i + 1) * (i + 2))
            i += 2
            if co + term == co:
                break
            co += term
        return +s, +co


def _flt(v):
    return float(format(v, "e"))


def sin(x):
    return _flt(_sin_cos(x)[0])


def cos(x):
    return _flt(_sin_cos(x)[1])


def tan(x):
    s, c = _sin_cos(x)
    with localcontext() as ctx:
        ctx.prec = PREC
        return _flt(s / c)


def _sc_dec(a, prec):
    """Decimal 각 a 의 (sin, cos) — |a| ≤ 2 정도, 문맥 prec."""
    with localcontext() as c:
        c.prec = prec
        a2 = a * a
        s, term, i = a, a, 1
        while True:
            term = -term * a2 / ((i + 1) * (i + 2))
            i += 2
            if s + term == s:
                break
            s += term
        co, term, i = D(1), D(1), 0
        while True:
            term = -term * a2 / ((i + 1) * (i + 2))
            i += 2
            if co + term == co:
                break
            co += term
        return s, co


def atan_dec(t, prec):
    """Decimal t → atan(t) Decimal (뉴턴)."""
    with localcontext() as c:
        c.prec = prec + 10
        if t == 0:
            return t
        if abs(t) > 1:
            base = pi(prec + 10) / 2
            r = base - atan_dec(1 / abs(t), prec)
            return r if t > 0 else -r
        a = D(math.atan(float(t)))
        if a == 0:  # float 로 0 이 될 만큼 작다 → atan(t) ≈ t − t³/3
            return t - t * t * t / 3
        for _ in range(60):
            s, co = _sc_dec(a, prec + 10)
            f = s - t * co
            na = a - f / (co + t * s)
            if abs(na - a) <= abs(a) * D(10) ** (-(prec + 5)):
                a = na
                break
            a = na
        return +a


def atan2(y, x):
    with localcontext() as c:
        c.prec = PREC + 10
        a = atan_dec(D(y) / D(x), PREC + 10)
        if x < 0:
            a = a + pi(PREC + 10) if y > 0 else a - pi(PREC + 10)
        return _flt(a)


def asin(v):
    with localcontext() as c:
        c.prec = PREC + 40
        d = D(v)
        if abs(d) == 1:
            return _flt(pi(PREC + 40) / 2 * d)
        return _flt(atan_dec(d / (1 - d * d).sqrt(), PREC + 40))


def acos(v):
    with localcontext() as c:
        c.prec = PREC + 40
        d = D(v)
        if abs(d) == 1:
            return _flt(pi(PREC + 40) / 2 * (1 - d))
        a = atan_dec(d / (1 - d * d).sqrt(), PREC + 40)
        return _flt(pi(PREC + 40) / 2 - a)


def exp_dec(x, prec):
    with localcontext() as c:
        c.prec = prec + 30
        r = D(x)
        k = 0
        while abs(r) > D("0.001"):
            r /= 2
            k += 1
        s, term, i = D(1), D(1), 0
        while True:
            i += 1
            term = term * r / i
            if s + term == s:
                break
            s += term
        for _ in range(k):
            s = s * s
        return +s


def exp(x):
    return _flt(exp_dec(x, PREC))


def log_dec(x, prec):
    with localcontext() as c:
        c.prec = prec + 20
        dx = D(x)
        m, e = math.frexp(x)
        y = D(math.log(m)) + e * _LN2(prec + 20)
        for _ in range(60):
            ey = exp_dec(y, prec + 20)
            ny = y + 2 * (dx - ey) / (dx + ey)
            if abs(ny - y) <= D(10) ** (-(prec + 5)) * max(abs(ny), D(1)):
                y = ny
                break
            y = ny
        return +y


_LN2C = {}


def _LN2(prec):  # noqa: N802
    if prec not in _LN2C:
        with localcontext() as c:
            c.prec = prec + 10
            # ln 2 = Σ 1/(k·2^k)
            s, k, p = D(0), 1, D(1)
            while True:
                p /= 2
                t = p / k
                if s + t == s:
                    break
                s += t
                k += 1
            _LN2C[prec] = +s
    return _LN2C[prec]


def log(x):
    return _flt(log_dec(x, PREC))


def log2(x):
    with localcontext() as c:
        c.prec = PREC
        return _flt(log_dec(x, PREC + 10) / _LN2(PREC + 10))


def log10(x):
    with localcontext() as c:
        c.prec = PREC
        return _flt(log_dec(x, PREC + 10) / log_dec(10.0, PREC + 10))


FUNCS = {"sin": sin, "cos": cos, "tan": tan, "asin": asin, "acos": acos, "exp": exp, "log": log, "log2": log2,
         "log10": log10}


if __name__ == "__main__":
    import random

    rng = random.Random(1)
    far = 0
    for _ in range(300):
        a = rng.uniform(-10, 10)
        v = rng.uniform(-1, 1)
        p = abs(a) + 0.1
        pairs = [(sin(a), math.sin(a)), (cos(a), math.cos(a)), (tan(a), math.tan(a)), (asin(v), math.asin(v)),
                 (acos(v), math.acos(v)), (exp(a), math.exp(a)), (log(p), math.log(p)), (log2(p), math.log2(p)),
                 (log10(p), math.log10(p)), (atan2(a, v), math.atan2(a, v))]
        for r, m in pairs:
            if abs(r - m) > abs(m) * 3e-16:
                far += 1
                print("멀다", a, v, r, m)
    print("ref_crmath 자체 점검: 1ulp 넘게 먼 값", far)
