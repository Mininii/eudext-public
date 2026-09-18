"""`i64` 2차(WP4) 차등 시험 (에뮬레이터): 곱셈·나눗셈(부호 없음·있음)·비트·시프트·to32·abs·난수·배열 원소 연산·epScript.

- 변수끼리: 경계값 24개 전 쌍(576) + 무작위 쌍(비트 폭 섞음 — 나눗셈 경로 A/B·64비트 제수·n < d 가 모두 나오게) ×
  새 연산 전부(연산자·메서드·모듈 함수·CtrigAsm 별칭·`.v` 통로·제자리 연산자). 같은 객체(`x * x`, `x // x` …),
  반쪽이 엇갈려 겹치는 경우, 32비트 변수 올리기(왼쪽·오른쪽), 0 나눗셈, 부호 나눗셈의 부호 조합(div0 두 규칙).
- 상수: 곱하는 수·제수 KS 개 × (경계값 + 근처 + 무작위) × (오른쪽·왼쪽, 정수·음수·10진 문자열 표기).
  0·1·2의 거듭제곱·−1·2^32 이상 제수·작은 상수(배가·덧셈)·큰 상수(비트 누적).
- 시프트: 상수 n(0~100) × 값, 변수 n(0~66, 100, 2^31, 2^32−1) × 값, 새 값·제자리·`<<=`·`>>=`·`>>`·`.v` 통로.
- Int64Array 원소 연산(변수·상수 칸 × 변수·상수 값), 난수(eudplib LCG 모형과 비교),
  이식판 `eud/tests/t_war.py`(a7aad90) 기대값(곱셈 12쌍·변수 나눗셈 17쌍·상수 제수 7×6·B4~B9·C1~C3·C8~C9).
- epScript 예제(examples/i64_ops_example.eps) 번역·에뮬레이터 실행·euddraft 빌드, 인게임 확인 맵(i64_ops_ingame)
  에뮬레이션(점검 56 / 56)·빌드, 빌드 오류여야 하는 모양, 실행 트리거 수(DESIGN 3.8 목표 대조), 파이썬 쪽 판정.

python tests/t_i64_ops.py
비용 표: python tools/cost.py tests/t_i64_ops.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import math  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
from fractions import Fraction  # noqa: E402

from eudplib import CompressPayload, EUDVariable, LoadMap, f_div, f_dwrand, f_getseed, f_mul  # noqa: E402

import t_i64  # noqa: E402 — 도우미(q, put, judge, EDGES …)를 같이 쓴다
from eudext import _compat, i64  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.i64 import Int64, Int64Array  # noqa: E402
from eudext.testing import emu  # noqa: E402
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
S63 = 1 << 63
EX = t_i64.EX
EDGES = t_i64.EDGES
s64, q, put, judge = t_i64.s64, t_i64.q, t_i64.put, t_i64.judge
INGAME_TOTAL = 56  # examples/i64_ops_ingame.eps 의 점검 수


# ---------------------------------------------------------------------------------------------
# 파이썬 참조 (i64 구현과 따로 짠다)
# ---------------------------------------------------------------------------------------------


def ref_div(a, b):
    return (a // b, a % b) if b else (M64, a)


def ref_sdiv(a, b, div0="eudplib"):
    sa, sb = s64(a), s64(b)
    if sb == 0:
        if div0 == "ctrig":
            qq = -S63 if sa < 0 else S63 - 1
        else:
            qq = 1 if sa < 0 else -1
        return qq & M64, a & M64
    qq = math.trunc(Fraction(sa, sb))
    return qq & M64, (sa - qq * sb) & M64


def ref_to32(a, saturate=True, signed=False):
    if not saturate:
        return a & M32
    if signed:
        return min(max(s64(a), -(1 << 31)), (1 << 31) - 1) & M32
    return min(a, M32)


def ref_abs(a):
    return abs(s64(a)) & M64


def ref_shl(a, n):
    return 0 if n >= 64 else (a << n) & M64


def ref_shr(a, n):
    return 0 if n >= 64 else a >> n


def swp(v):
    return ((v & M32) << 32) | (v >> 32)


def rand_pairs(n, seed):
    """비트 폭을 섞은 무작위 쌍 (나눗셈 경로가 고루 나오게)."""
    rng = random.Random(seed)
    out = []
    widths = (1, 2, 8, 16, 31, 32, 33, 40, 48, 62, 63, 64)
    for k in range(n):
        a = rng.getrandbits(rng.choice(widths))
        b = rng.getrandbits(rng.choice(widths))
        r = rng.random()
        if r < 0.08:
            b = 0
        elif r < 0.16:
            b = (1 << 31) + rng.getrandbits(31)  # 32비트 제수 > 2^31 (경로 B)
        elif r < 0.24:
            b = (rng.getrandbits(31) | 1) << 32 | rng.getrandbits(32)  # 64비트 제수, 상위 < 2^31
        elif r < 0.30:
            b = (1 << 63) | rng.getrandbits(63)  # 상위 ≥ 2^31 (몫 0 또는 1)
        elif r < 0.36:
            b = a
        elif r < 0.42:
            b = (a >> rng.randrange(1, 40)) | 1
        if rng.random() < 0.15:
            a = (1 << 64) - 1 - rng.getrandbits(rng.choice(widths))
        if rng.random() < 0.1:
            a, b = (-a) & M64, b
        if rng.random() < 0.1:
            b = (-b) & M64
        out.append((a & M64, b & M64))
    return out


VPAIRS = [(a, b) for a in EDGES for b in EDGES] + rand_pairs(700, 41)


# ---------------------------------------------------------------------------------------------
# 묶음 1: 변수끼리
# ---------------------------------------------------------------------------------------------


def sw(x):
    return Int64.wrap(x.hi, x.lo)


def build_vars(s):
    @s.case("mul")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        q(t, "m1") << a * b
        q(t, "m2") << i64.mul(a, b)
        x = q(t, "m3")
        x << a
        x.imul(b)
        x = q(t, "m4")
        x << a
        x.imulattr("v", b)
        x = q(t, "m5")
        x << a
        x *= b
        i64.LMul(q(t, "m6"), a, b)
        i64.LiMul(q(t, "m7"), b, a)
        x = q(t, "m8")
        x << a
        i64.imul(x, b)
        q(t, "m9") << b * a

    @s.case("div")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        q(t, "d1") << a // b
        q(t, "r1") << a % b
        qq, rr = i64.divmod(a, b)
        q(t, "d2") << qq
        q(t, "r2") << rr
        qq, rr = divmod(a, b)
        q(t, "d3") << qq
        q(t, "r3") << rr
        x = q(t, "d4")
        x << a
        x.idiv(b)
        x = q(t, "r4")
        x << a
        x.imod(b)
        x = q(t, "d5")
        x << a
        x //= b
        x = q(t, "r5")
        x << a
        x %= b
        x = q(t, "d6")
        x << a
        x.ifloordivattr("v", b)
        x = q(t, "r6")
        x << a
        x.imodattr("v", b)
        i64.LDiv(q(t, "d7"), a, b)
        i64.LMod(q(t, "r7"), a, b)
        q(t, "d8") << i64.div(a, b)
        q(t, "r8") << i64.mod(a, b)
        x = q(t, "d9")
        x << a
        i64.idiv(x, b)

    @s.case("sdiv")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        for tag, d0 in (("e", "eudplib"), ("c", "ctrig")):
            qq, rr = i64.sdivmod(a, b, div0=d0)
            q(t, "q1" + tag) << qq
            q(t, "r1" + tag) << rr
            q(t, "q2" + tag) << i64.sdiv(a, b, div0=d0)
            q(t, "r2" + tag) << a.smod(b, div0=d0)
        q(t, "q3e") << a.sdiv(b)
        q(t, "r3e") << i64.smod(a, b)
        i64.LiDiv(q(t, "q4c"), a, b)
        i64.LiMod(q(t, "r4c"), a, b)

    @s.case("bits")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        for op, sym in (("and", "__and__"), ("or", "__or__"), ("xor", "__xor__")):
            q(t, op + "1") << getattr(a, sym)(b)
            q(t, op + "2") << getattr(i64, "bit" + op)(a, b)
            x = q(t, op + "3")
            x << a
            getattr(x, "__i" + op + "__")(b)
            x = q(t, op + "4")
            x << a
            getattr(x, "i" + op)(b)
            x = q(t, op + "5")
            x << a
            getattr(x, "i" + op + "attr")("v", b)
            getattr(i64, "L" + op.capitalize())(q(t, op + "6"), b, a)
            x = q(t, op + "7")
            x << a
            getattr(i64, "i" + op)(x, b)
        q(t, "not1") << ~a
        q(t, "not2") << a.invert()
        x = q(t, "not3")
        x << a
        x.iinvert()
        i64.LNot(q(t, "not4"), a)
        q(t, "not5") << i64.bitnot(a)
        x = q(t, "not6")
        x << a
        i64.iinvert(x)

    @s.case("misc")
    def _(t):
        a = q(t, "a")
        q(t, "abs1") << a.abs()
        q(t, "abs2") << i64.abs(a)
        x = q(t, "abs3")
        x << a
        x.iabs()
        i64.LAbs(q(t, "abs4"), a)
        x = q(t, "abs5")
        x << a
        i64.iabs(x)
        t.out("t1", a.to32())
        t.out("t2", a.to32(signed=True))
        t.out("t3", a.to32(saturate=False))
        t.out("t4", i64.to32(a, saturate=False, signed=True))
        t.out("t5", i64.f_to32(a, signed=False))

    @s.case("v32")
    def _(t):
        a, c, e = q(t, "a"), t.var("c"), t.var("e")
        q(t, "mc") << a * c
        q(t, "cm") << i64.mul(c, a)
        q(t, "ce") << i64.mul32(c, e)
        q(t, "ce2") << i64.mul(c, e)
        x = q(t, "mci")
        x << a
        x *= c
        q(t, "dc") << a // c
        q(t, "rc") << a % c
        q(t, "cd") << i64.div(c, a)
        q(t, "cr") << i64.mod(c, a)
        q(t, "ced") << i64.div(c, e)
        q(t, "cer") << i64.mod(c, e)
        q(t, "sdc") << i64.sdiv(a, c)
        q(t, "src") << i64.smod(a, c)
        q(t, "andc") << (a & c)
        q(t, "orc") << (a | c)
        q(t, "xorc") << (a ^ c)
        q(t, "cand") << i64.bitand(c, a)
        q(t, "notc") << i64.bitnot(c)
        t.out("to32c", i64.to32(c))
        q(t, "absc") << i64.abs(c)
        q(t, "up") << Int64(c) * Int64(e)

    @s.case("same")
    def _(t):
        a = q(t, "a")
        q(t, "sq") << a * a
        q(t, "sd") << a // a
        q(t, "sr") << a % a
        qq, rr = i64.divmod(a, a)
        q(t, "sd2") << qq
        q(t, "sr2") << rr
        q(t, "ssd") << i64.sdiv(a, a)
        q(t, "ssr") << i64.smod(a, a)
        q(t, "sand") << (a & a)
        q(t, "sor") << (a | a)
        q(t, "sxor") << (a ^ a)
        for nm, meth in (("imx", "imul"), ("idx", "idiv"), ("irx", "imod"), ("iax", "iand"), ("iox", "ior"), ("ixx", "ixor")):
            x = q(t, nm)
            x << a
            getattr(x, meth)(x)
        x = q(t, "vmx")
        x << a
        x.v *= x
        for nm, fn in (("lmx", i64.LMul), ("ldx", i64.LDiv), ("lrx", i64.LMod), ("lix", i64.LiDiv), ("lxx", i64.LXor)):
            x = q(t, nm)
            x << a
            fn(x, x, x)
        c = t.var("c")
        q(t, "cc") << i64.mul(c, c)
        q(t, "ccd") << i64.div(c, c)

    @s.case("alias")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        for nm, meth in (("am", "imul"), ("ad", "idiv"), ("ar", "imod"), ("aa", "iand"), ("ao", "ior"), ("ax", "ixor")):
            x = q(t, nm)
            x << a
            getattr(x, meth)(sw(x))
        d = q(t, "lm")
        d << b
        i64.LMul(d, a, d)
        d = q(t, "ld")
        d << b
        i64.LDiv(d, a, d)
        d = q(t, "lr")
        d << b
        i64.LMod(d, d, a)
        d = q(t, "lsd")
        d << b
        i64.LiDiv(d, sw(d), a)
        d = q(t, "lx")
        d << b
        i64.LXor(d, sw(d), a)
        d = q(t, "ln")
        d << b
        i64.LNot(d, sw(d))
        d = q(t, "lab")
        d << b
        i64.LAbs(d, sw(d))
        x = q(t, "lo_only")
        x << a
        x.imul(Int64.wrap(x.lo, b.hi))
        x = q(t, "hi_only")
        x << a
        x.iand(Int64.wrap(b.lo, x.hi))
        x = q(t, "dv_lo")
        x << a
        x.idiv(Int64.wrap(b.lo, x.lo))

    def e_mul(a, b):
        v = (a * b) & M64
        return {"m%d" % k: v for k in range(1, 10)}

    def e_div(a, b):
        qq, rr = ref_div(a, b)
        e = {}
        for k in range(1, 10):
            e["d%d" % k] = qq
            if k < 9:
                e["r%d" % k] = rr
        return e

    def e_sdiv(a, b):
        qe, re_ = ref_sdiv(a, b, "eudplib")
        qc, rc = ref_sdiv(a, b, "ctrig")
        return {"q1e": qe, "r1e": re_, "q2e": qe, "r2e": re_, "q1c": qc, "r1c": rc, "q2c": qc, "r2c": rc,
                "q3e": qe, "r3e": re_, "q4c": qc, "r4c": rc}  # fmt: skip

    def e_bits(a, b):
        e = {}
        for op, f in (("and", a & b), ("or", a | b), ("xor", a ^ b)):
            for k in range(1, 8):
                e[op + str(k)] = f
        for k in range(1, 7):
            e["not%d" % k] = a ^ M64
        return e

    def e_misc(a):
        e = {"abs%d" % k: ref_abs(a) for k in range(1, 6)}
        e.update(t1=ref_to32(a), t2=ref_to32(a, signed=True), t3=ref_to32(a, False), t4=ref_to32(a, False, True),
                 t5=ref_to32(a))  # fmt: skip
        return e

    def e_v32(a, c, e_):
        qa, ra = ref_div(a, c)
        qc, rcc = ref_div(c, a)
        qe, re_ = ref_div(c, e_)
        sq, sr = ref_sdiv(a, c)
        return {"mc": a * c, "cm": a * c, "ce": c * e_, "ce2": c * e_, "mci": a * c, "dc": qa, "rc": ra, "cd": qc,
                "cr": rcc, "ced": qe, "cer": re_, "sdc": sq, "src": sr, "andc": a & c, "orc": a | c, "xorc": a ^ c,
                "cand": a & c, "notc": c ^ M64, "to32c": c, "absc": c, "up": c * e_}  # fmt: skip

    def e_same(a, c):
        qq, rr = ref_div(a, a)
        sq, sr = ref_sdiv(a, a)
        cq, cr = ref_sdiv(a, a, "ctrig")
        return {"sq": a * a, "sd": qq, "sr": rr, "sd2": qq, "sr2": rr, "ssd": sq, "ssr": sr, "sand": a, "sor": a,
                "sxor": 0, "imx": a * a, "idx": qq, "irx": rr, "iax": a, "iox": a, "ixx": 0, "vmx": a * a,
                "lmx": a * a, "ldx": qq, "lrx": rr, "lix": cq, "lxx": 0, "cc": c * c, "ccd": ref_div(c, c)[0]}  # fmt: skip

    def e_alias(a, b):
        sa, sb = swp(a), swp(b)
        lo_only = (a & M32) | ((b >> 32) << 32)
        hi_only = (b & M32) | ((a >> 32) << 32)
        dv = (b & M32) | ((a & M32) << 32)
        return {"am": a * sa, "ad": ref_div(a, sa)[0], "ar": ref_div(a, sa)[1], "aa": a & sa, "ao": a | sa,
                "ax": a ^ sa, "lm": a * b, "ld": ref_div(a, b)[0], "lr": ref_div(b, a)[1],
                "lsd": ref_sdiv(sb, a, "ctrig")[0], "lx": sb ^ a, "ln": sb ^ M64, "lab": ref_abs(sb),
                "lo_only": a * lo_only, "hi_only": a & hi_only, "dv_lo": ref_div(a, dv)[0]}  # fmt: skip

    return e_mul, e_div, e_sdiv, e_bits, e_misc, e_v32, e_same, e_alias


def suite_vars():
    s = Suite("t_i64_ops 변수끼리")
    e_mul, e_div, e_sdiv, e_bits, e_misc, e_v32, e_same, e_alias = build_vars(s)
    s.build()
    rng = random.Random(17)
    for a, b in VPAIRS:
        d = put(put({}, "a", a), "b", b)
        label = "a=0x%X b=0x%X" % (a, b)
        judge(s, "mul", d, e_mul(a, b), label)
        judge(s, "div", d, e_div(a, b), label)
        judge(s, "sdiv", d, e_sdiv(a, b), label)
        judge(s, "bits", d, e_bits(a, b), label)
    for a, b in VPAIRS[::2]:
        c = b & M32 if rng.random() < 0.7 else rng.choice((0, 1, 2, 7, M32, 0x80000000, 0x80000001, a & M32))
        e_ = rng.choice((0, 1, 3, 10, M32, 0x80000000, 0x80000001, rng.getrandbits(32), c))
        label = "a=0x%X c=0x%X e=0x%X" % (a, c, e_)
        judge(s, "misc", put({}, "a", a), e_misc(a), label)
        judge(s, "v32", put({"c": c, "e": e_}, "a", a), e_v32(a, c, e_), label)
        judge(s, "same", put({"c": c}, "a", a), e_same(a, c), label)
        judge(s, "alias", put(put({}, "a", a), "b", b), e_alias(a, b), "a=0x%X b=0x%X" % (a, b))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 2: 상수
# ---------------------------------------------------------------------------------------------

KS = (0, 1, 2, 3, 5, 7, 10, 255, 256, 500, 1000, 10000, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, 0x80000001, M32,
      1 << 32, (1 << 32) + 1, 0x123456789, 10**16, 10**19, 0x9E3779B97F4A7C15, S63, S63 - 1, M64, M64 - 1,
      0xFFFFFFFF00000000, 12800000000)  # fmt: skip


def literal(k, idx):
    if idx % 3 == 1 and k >> 63:
        return k - (1 << 64)
    if idx % 3 == 2:
        return str(k)
    return k


def build_k(s, idx, k):
    lit = literal(k, idx)
    name = "k%02d_%X" % (idx, k)

    @s.case(name)
    def _(t):
        a, c = q(t, "a"), t.var("c")
        q(t, "mr") << a * lit
        q(t, "ml") << i64.mul(lit, a)
        x = q(t, "mi")
        x << a
        x *= lit
        q(t, "mc") << i64.mul(c, lit)
        q(t, "d") << a // lit
        q(t, "r") << a % lit
        qq, rr = i64.divmod(a, lit)
        q(t, "d2") << qq
        q(t, "r2") << rr
        x = q(t, "di")
        x << a
        x.idiv(lit)
        x = q(t, "ri")
        x << a
        x.imod(lit)
        q(t, "kd") << i64.div(lit, a)
        q(t, "kr") << i64.mod(lit, a)
        q(t, "cd") << i64.div(c, lit)
        qq, rr = i64.sdivmod(a, lit)
        q(t, "sd") << qq
        q(t, "sr") << rr
        qq, rr = i64.sdivmod(a, lit, div0="ctrig")
        q(t, "sdc") << qq
        q(t, "src") << rr
        q(t, "ksd") << i64.sdiv(lit, a)
        q(t, "and") << (a & lit)
        q(t, "or") << (lit | a)
        q(t, "xor") << (a ^ lit)
        x = q(t, "iand")
        x << a
        x &= lit
        x = q(t, "ixor")
        x << a
        x.ixor(lit)
        x = q(t, "ior")
        x << a
        x.ior(lit)

    def expect(a, c):
        d, r = ref_div(a, k)
        kd, kr = ref_div(k, a)
        sd, sr = ref_sdiv(a, k)
        sdc, src = ref_sdiv(a, k, "ctrig")
        return {"mr": a * k, "ml": a * k, "mi": a * k, "mc": c * k, "d": d, "r": r, "d2": d, "r2": r, "di": d,
                "ri": r, "kd": kd, "kr": kr, "cd": ref_div(c, k)[0], "sd": sd, "sr": sr, "sdc": sdc, "src": src,
                "ksd": ref_sdiv(k, a)[0], "and": a & k, "or": a | k, "xor": a ^ k, "iand": a & k, "ixor": a ^ k,
                "ior": a | k}  # fmt: skip

    return name, expect


def suite_const():
    s = Suite("t_i64_ops 상수")
    cases = [(k, build_k(s, i, k)) for i, k in enumerate(KS)]
    s.build()
    rng = random.Random(29)
    for k, (name, expect) in cases:
        near = {(k - 1) & M64, k, (k + 1) & M64, k ^ S63, (k * 3) & M64, (k * 7 + 5) & M64, (-k) & M64}
        vals = list(EDGES) + sorted(near) + [rng.getrandbits(rng.choice((16, 32, 48, 64))) for _ in range(24)]
        for a in vals:
            c = rng.choice((0, 1, M32, rng.getrandbits(32), a & M32))
            judge(s, name, put({"c": c}, "a", a), expect(a, c), "K=0x%X a=0x%X c=0x%X" % (k, a, c))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 3: 시프트
# ---------------------------------------------------------------------------------------------

NS = (0, 1, 2, 3, 5, 7, 8, 12, 13, 15, 16, 17, 20, 26, 27, 28, 30, 31, 32, 33, 40, 47, 48, 62, 63, 64, 65, 100)
SHIFT_VALS = EDGES + (0x8000000000000001, 0x0123456789ABCDEF, 0xAAAAAAAA55555555, 1, 3 << 62)


def build_shift(s):
    for n in NS:

        @s.case("shk%d" % n)
        def _(t, n=n):
            a = q(t, "a")
            q(t, "l1") << a.shl(n)
            q(t, "r1") << a.shr(n)
            q(t, "r2") << (a >> n)
            q(t, "l2") << i64.shl(a, n)
            q(t, "r3") << i64.shr(a, n)
            x = q(t, "l3")
            x << a
            x <<= n
            x = q(t, "r4")
            x << a
            x >>= n
            x = q(t, "l4")
            x << a
            x.ilshiftattr("v", n)
            x = q(t, "r5")
            x << a
            x.irshiftattr("v", n)
            x = q(t, "l5")
            x << a
            x.ishl(n)
            x = q(t, "r6")
            x << a
            i64.ishr(x, n)
            q(t, "c1") << i64.shl(t.var("c"), n)
            q(t, "c2") << i64.shr(t.var("c"), n)

    @s.case("shv")
    def _(t):
        a, n = q(t, "a"), t.var("n")
        q(t, "l1") << a.shl(n)
        q(t, "r1") << a.shr(n)
        q(t, "r2") << (a >> n)
        x = q(t, "l2")
        x << a
        x <<= n
        x = q(t, "r3")
        x << a
        x.v >>= n
        x = q(t, "l3")
        x << a
        i64.ishl(x, n)
        q(t, "c1") << i64.shl(t.var("c"), n)
        q(t, "c2") << i64.shr(t.var("c"), n)
        x = q(t, "self")  # 시프트 양이 자기 반쪽
        x << a
        x.ishr(x.lo)


def suite_shift():
    s = Suite("t_i64_ops 시프트")
    build_shift(s)
    s.build()
    rng = random.Random(37)
    for n in NS:
        for a in SHIFT_VALS + tuple(rng.getrandbits(64) for _ in range(6)):
            c = rng.getrandbits(32)
            e = {"l%d" % k: ref_shl(a, n) for k in range(1, 6)}
            e.update({"r%d" % k: ref_shr(a, n) for k in range(1, 7)})
            e.update(c1=ref_shl(c, n), c2=ref_shr(c, n))
            judge(s, "shk%d" % n, put({"c": c}, "a", a), e, "n=%d a=0x%X" % (n, a))
    vns = list(range(0, 67)) + [100, 127, 128, 255, 1 << 31, M32, 0x100000000 - 64]
    for n in vns:
        for a in SHIFT_VALS[::2] + tuple(rng.getrandbits(64) for _ in range(3)):
            c = rng.getrandbits(32)
            e = {"l1": ref_shl(a, n), "l2": ref_shl(a, n), "l3": ref_shl(a, n), "r1": ref_shr(a, n), "r2": ref_shr(a, n),
                 "r3": ref_shr(a, n), "c1": ref_shl(c, n), "c2": ref_shr(c, n), "self": ref_shr(a, a & M32)}  # fmt: skip
            judge(s, "shv", put({"c": c, "n": n}, "a", a), e, "n=%d a=0x%X" % (n, a))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 4: 배열 원소 · 난수 · 이식판 t_war 기대값
# ---------------------------------------------------------------------------------------------

LCG_A, LCG_C = 1103515245, 12345


def ref_dwrand(seed):
    s1 = (seed * LCG_A + LCG_C) & M32
    s2 = (s1 * LCG_A + LCG_C) & M32
    return (s1 & 0xFFFF0000) | (s2 >> 16), s2


# eud/tests/t_war.py (DPS_Enhance eudplib-port a7aad90) 의 기대값
WAR_MUL = [
    (0, 12345), (1, 0xFFFFFFFF), (0xFFFFFFFF, 0xFFFFFFFF), (1000, 10000), (0x80000000, 2), (0x12345678, 0x9ABCDEF0),
    (0x123456789, 3), (7, 0x123456789ABCDEF), (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF), (0x100000000, 0x100000000),
    (0xDEADBEEFCAFEBABE, 0x0123456789ABCDEF), (123456789012, 987654321),
]  # fmt: skip
WAR_DIV = [
    (1000, 7), (0xFFFFFFFF, 0xFFFFFFFF), (0xFFFFFFFF, 0x80000001),
    (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFF), (0xFFFFFFFFFFFFFFFE, 0xFFFFFFFF), (0x8000000000000000, 0x80000001),
    (0x123456789ABCDEF0, 3), (0x00000001FFFFFFFF, 0x80000000),
    (0x123456789ABCDEF0, 0x100000001), (0x100000000, 0x100000001), (0x500000003, 0x500000004),
    (0x500000004, 0x500000004), (0xFFFFFFFFFFFFFFFF, 0x7FFFFFFFFFFFFFFF), (0xFEDCBA9876543210, 0x0000000123456789),
    (0x7FFFFFFFFFFFFFFF, 0x8000000000000000), (0, 0x100000000), (5, 0),
]  # fmt: skip
WAR_CDIV = [10000, 3, 5000, 0xFFFFFFFF, 0x80000001, 7, 1]
WAR_CDIV_X = [0, 5, 0x123456789ABCDEF0, 0xFFFFFFFFFFFFFFFF, 0x80000000FFFFFFFF, 123456789012345]
# (이름, a, b, 연산, 기대값) — t_war.py CASES 의 곱셈·나눗셈 항목
WAR_CASES = [
    ("B4", 0xFFFFFFFF, 0xFFFFFFFF, "mul", 0xFFFFFFFE00000001),
    ("B5", 0x100000000, 0x100000000, "mul", 0),
    ("B6", 100, 0, "div", 0xFFFFFFFFFFFFFFFF),
    ("B7", 100, 0, "mod", 100),
    ("B8", 0xFFFFFFFFFFFFFFFF, 10, "div", 1844674407370955161),
    ("B9", 0xFFFFFFFFFFFFFFFF, 10, "mod", 5),
    ("C1", 0xFFFFFFFF, 0xFFFFFFFF, "mul", 0xFFFFFFFE00000001),
    ("C2", 123456789012345, 1000, "div", 123456789012),
    ("C3", 123456789012345, 1000, "mod", 345),
    ("C8", 0xFFFFFFFFFFFFFFFF, 0x8000000000000000, "div", 1),
    ("C9", 0xFFFFFFFFFFFFFFFF, 0x8000000000000000, "mod", 0x7FFFFFFFFFFFFFFF),
]


def suite_misc():
    s = Suite("t_i64_ops 배열·난수·t_war")
    arr = Int64Array(8)

    @s.case("arr_var")
    def _(t):
        i, a, b, c = t.var("i"), q(t, "a"), q(t, "b"), t.var("c")
        arr[i] = a
        arr[i] *= b
        q(t, "r1") << arr[i]
        arr.imul(i, 3)
        arr.imulitem(i, c)
        q(t, "r2") << arr[i]
        arr[i] //= c
        arr.idiv(i, 7)
        q(t, "r3") << arr[i]
        arr.ifloordivitem(i, b)
        q(t, "r4") << arr[i]
        arr[i] = a
        arr.imod(i, b)
        q(t, "r5") << arr[i]
        arr[i] = a
        arr.imoditem(i, 1000)
        arr.iand(i, b)
        arr.ior(i, 0x100000000)
        arr.ixor(i, a)
        q(t, "r6") << arr[i]
        arr[i] = a
        arr.ianditem(i, 0xFFFF0000FFFF)
        arr.ioritem(i, c)
        arr.ixoritem(i, 0xF0F0F0F0F0F0F0F0)
        arr.ilshiftitem(i, 3)
        arr.irshiftitem(i, c)
        q(t, "r7") << arr[i]
        arr[i] = a
        arr.ishl(i, c)
        arr.ishr(i, 5)
        q(t, "r8") << arr[i]

    def arr_var_ref(a, b, c):
        x = (a * b) & M64
        r1 = x
        x = (x * 3 * c) & M64
        r2 = x
        x = ref_div(ref_div(x, c)[0], 7)[0]
        r3 = x
        x = ref_div(x, b)[0]
        r4 = x
        r5 = ref_div(a, b)[1]
        x = (((a % 1000) & b) | 0x100000000) ^ a
        r6 = x
        x = (((a & 0xFFFF0000FFFF) | c) ^ 0xF0F0F0F0F0F0F0F0)
        x = ref_shr(ref_shl(x, 3), c)
        r7 = x
        r8 = ref_shr(ref_shl(a, c), 5)
        return {"r1": r1, "r2": r2, "r3": r3, "r4": r4, "r5": r5, "r6": r6, "r7": r7, "r8": r8}

    @s.case("arr_const")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        arr[5] = a
        arr.iand(5, 0xFF00FF00FF00FF00)
        arr.ior(5, 0x0000000F0000000F)
        q(t, "r1") << arr[5]
        arr.iand(5, M64)
        arr.ior(5, 0)
        arr.iand(5, b)
        q(t, "r2") << arr[5]
        arr.imul(5, 10**16)
        arr.idiv(5, 12345)
        q(t, "r3") << arr[5]
        arr.imod(5, 0x100000001)
        arr.ixor(5, b)
        arr.ishl(5, 7)
        arr.ishr(5, 3)
        q(t, "r4") << arr[5]

    def arr_const_ref(a, b):
        x = (a & 0xFF00FF00FF00FF00) | 0x0000000F0000000F
        r1 = x
        x &= b
        r2 = x
        x = ((x * 10**16) & M64) // 12345
        r3 = x
        x = ((x % 0x100000001) ^ b)
        x = ref_shr(ref_shl(x, 7), 3)
        return {"r1": r1, "r2": r2, "r3": r3, "r4": x}

    @s.case("rand")
    def _(t):
        t.out("seed", f_getseed())
        r = i64.rand()
        q(t, "r") << r
        d = q(t, "d")
        i64.LRand(d)

    wcases = {}
    for idx, (x, y) in enumerate(WAR_MUL):
        wcases["MU%d" % idx] = (x, y, "mul", (x * y) & M64)
    for idx, (x, y) in enumerate(WAR_DIV):
        qq, rr = ref_div(x, y)
        wcases["DQ%d" % idx] = (x, y, "div", qq)
        wcases["DR%d" % idx] = (x, y, "mod", rr)
    for name, x, y, op, want in WAR_CASES:
        wcases[name] = (x, y, op, want)

    @s.case("war_var")
    def _(t):
        p, qv = q(t, "p"), q(t, "q")
        i64.LMul(q(t, "mul"), p, qv)
        i64.LDiv(q(t, "div"), p, qv)
        i64.LMod(q(t, "mod"), p, qv)

    for ci, cst in enumerate(WAR_CDIV):

        @s.case("war_k%d" % ci)
        def _(t, cst=cst):
            p = q(t, "p")
            i64.LDiv(q(t, "div"), p, str(cst))
            i64.LMod(q(t, "mod"), p, str(cst))
            x = q(t, "div2")  # 대상 = 원천 (이식판 KQ 형태)
            x << p
            i64.LDiv(x, x, cst)

    s.build()
    rng = random.Random(53)
    for k in range(60):
        a, b = rng.getrandbits(64), rng.getrandbits(rng.choice((8, 32, 64)))
        c = rng.choice((0, 1, 3, 64, rng.getrandbits(6), rng.getrandbits(32)))
        if k < 12:
            a, b = EDGES[k * 2], EDGES[23 - k]
        d = put(put({"i": rng.randrange(8), "c": c}, "a", a), "b", b)
        judge(s, "arr_var", d, arr_var_ref(a, b, c), "arr i a=0x%X b=0x%X c=%d" % (a, b, c))
    for a in EDGES:
        b = rng.getrandbits(64)
        judge(s, "arr_const", put(put({}, "a", a), "b", b), arr_const_ref(a, b), "arr 5 a=0x%X" % a)
    m = s.machine
    for k in range(20):
        r = s.run("rand", {})
        seed = r.values["seed"]
        v1, s1 = ref_dwrand(seed)
        v2, s2 = ref_dwrand(s1)
        v3, s3 = ref_dwrand(s2)
        v4, _s4 = ref_dwrand(s3)
        got = (r.values["r.lo"], r.values["r.hi"], r.values["d.lo"], r.values["d.hi"])
        s.expect_true("rand", r.error is None and got == (v1, v2, v3, v4), "rand #%d" % k, "%r != %r" % (got, (v1, v2, v3, v4)))
    for name, (x, y, op, want) in wcases.items():
        r = s.run("war_var", put(put({}, "p", x), "q", y))
        got = r.values[op + ".lo"] | (r.values[op + ".hi"] << 32)
        s.expect_true("war_var", r.error is None and got == want, "t_war %s" % name, "got 0x%X want 0x%X" % (got, want))
    for ci, cst in enumerate(WAR_CDIV):
        for j, x in enumerate(WAR_CDIV_X):
            judge(s, "war_k%d" % ci, put({}, "p", x), {"div": x // cst, "mod": x % cst, "div2": x // cst},
                  "t_war KQ%d_%d/KR%d_%d" % (ci, j, ci, j))  # fmt: skip
    del m
    return s.report()


# ---------------------------------------------------------------------------------------------
# epScript 예제 · 인게임 맵 · euddraft 빌드 · 빌드 오류 · 파이썬 쪽 판정
# ---------------------------------------------------------------------------------------------


def suite_eps(eps):
    s = Suite("t_i64_ops epScript 예제")
    two = ("mul", "mul_ip", "div_ip", "bitmix", "bitmix_ip")
    for fn in two:

        @s.case("eps_" + fn)
        def _(t, fn=fn):
            a, b = q(t, "a"), q(t, "b")
            lo, hi = getattr(eps, "f_" + fn)(a.lo, a.hi, b.lo, b.hi)
            q(t, "r") << Int64.wrap(lo, hi)

    for fn in ("qr", "sdiv", "sdiv_ct"):

        @s.case("eps_" + fn)
        def _(t, fn=fn):
            a, b = q(t, "a"), q(t, "b")
            r = getattr(eps, "f_" + fn)(a.lo, a.hi, b.lo, b.hi)
            q(t, "q") << Int64.wrap(r[0], r[1])
            q(t, "r") << Int64.wrap(r[2], r[3])

    for fn in ("mul_k", "mod_k", "sdiv_k", "absval", "lcl"):

        @s.case("eps_" + fn)
        def _(t, fn=fn):
            a = q(t, "a")
            lo, hi = getattr(eps, "f_" + fn)(a.lo, a.hi)
            q(t, "r") << Int64.wrap(lo, hi)

    @s.case("eps_mul32")
    def _(t):
        lo, hi = eps.f_mul32(t.var("c"), t.var("e"))
        q(t, "r") << Int64.wrap(lo, hi)
        a = q(t, "a")
        lo, hi = eps.f_mul_left32(t.var("c"), a.lo, a.hi)
        q(t, "r2") << Int64.wrap(lo, hi)
        lo, hi = eps.f_div_left32(t.var("c"), a.lo, a.hi)
        q(t, "r3") << Int64.wrap(lo, hi)

    @s.case("eps_shifts")
    def _(t):
        a = q(t, "a")
        lo, hi = eps.f_shifts(a.lo, a.hi, t.var("n"))
        q(t, "r") << Int64.wrap(lo, hi)

    @s.case("eps_narrow")
    def _(t):
        a = q(t, "a")
        r = eps.f_narrow(a.lo, a.hi)
        for k in range(3):
            t.out("t%d" % k, r[k])

    @s.case("eps_arr")
    def _(t):
        lo, hi = eps.f_arr_ops(t.var("p"), t.var("c"))
        q(t, "r") << Int64.wrap(lo, hi)

    @s.case("eps_price")
    def _(t):
        lo, hi = eps.f_price_of(t.var("c"))
        q(t, "r") << Int64.wrap(lo, hi)

    @s.case("eps_main")
    def _(t):
        eps.afterTriggerExec()
        q(t, "gold") << eps.gold

    s.build()

    def bits_ref(a, b):
        return (a & b) | ((a ^ M64) ^ b)

    def bits_ip_ref(a, b):
        return ((((a & b) | 0xF0000000F) ^ b) ^ M64)

    def shifts_ref(a, n):
        r = ref_shl(a, n) ^ (a >> 3)
        r = ref_shr(ref_shl(r, 1), n)
        return r >> 29

    def lcl_ref(a):
        d = (a * 3) & M64
        d //= 2
        d ^= a
        return ref_sdiv(d, (-5) & M64, "ctrig")[0]

    rng = random.Random(61)
    pairs2 = [(a, b) for a in EDGES[::3] for b in EDGES[::2]] + t_i64.PAIRS[576::25]
    ref2 = {"mul": lambda a, b: a * b, "mul_ip": lambda a, b: a * b, "div_ip": lambda a, b: ref_div(a, b)[0],
            "bitmix": bits_ref, "bitmix_ip": bits_ip_ref}  # fmt: skip
    for a, b in pairs2:
        for fn, f in ref2.items():
            judge(s, "eps_" + fn, put(put({}, "a", a), "b", b), {"r": f(a, b)}, "%s a=0x%X b=0x%X" % (fn, a, b))
        qq, rr = ref_div(a, b)
        judge(s, "eps_qr", put(put({}, "a", a), "b", b), {"q": qq, "r": rr}, "qr a=0x%X b=0x%X" % (a, b))
        qq, rr = ref_sdiv(a, b)
        judge(s, "eps_sdiv", put(put({}, "a", a), "b", b), {"q": qq, "r": rr}, "sdiv a=0x%X b=0x%X" % (a, b))
        qq, rr = ref_sdiv(a, b, "ctrig")
        judge(s, "eps_sdiv_ct", put(put({}, "a", a), "b", b), {"q": qq, "r": rr}, "sdiv_ct a=0x%X b=0x%X" % (a, b))
    for a in EDGES + tuple(rng.getrandbits(64) for _ in range(20)):
        judge(s, "eps_mul_k", put({}, "a", a), {"r": a * 10**16}, "mul_k 0x%X" % a)
        judge(s, "eps_mod_k", put({}, "a", a), {"r": a % 1000}, "mod_k 0x%X" % a)
        judge(s, "eps_sdiv_k", put({}, "a", a), {"r": ref_sdiv(a, (-7) & M64)[0]}, "sdiv_k 0x%X" % a)
        judge(s, "eps_absval", put({}, "a", a), {"r": ref_abs(a)}, "abs 0x%X" % a)
        judge(s, "eps_lcl", put({}, "a", a), {"r": lcl_ref(a)}, "lcl 0x%X" % a)
        c, e_ = rng.getrandbits(32), rng.choice((0, 1, rng.getrandbits(32), M32))
        judge(s, "eps_mul32", put({"c": c, "e": e_}, "a", a), {"r": c * e_, "r2": a * c, "r3": ref_div(c, a)[0]},
              "mul32 c=0x%X a=0x%X" % (c, a))  # fmt: skip
        n = rng.choice((0, 1, 3, 29, 31, 32, 33, 63, 64, 70, rng.getrandbits(6)))
        judge(s, "eps_shifts", put({"n": n}, "a", a), {"r": shifts_ref(a, n)}, "shifts a=0x%X n=%d" % (a, n))
        judge(s, "eps_narrow", put({}, "a", a), {"t0": ref_to32(a), "t1": ref_to32(a, signed=True), "t2": a & M32},
              "narrow 0x%X" % a)  # fmt: skip
    gold = 12800000000
    for c in (0, 1, 2, 5, 7, 12, 0x80000000, M32):
        x = (((((gold * c) % (1 << 64)) // 7) % 1000000000000) & 0xFFFFFFFFFF | 1) ^ c
        x = ref_shr(ref_shl(x, 2), 1)
        judge(s, "eps_arr", {"p": rng.randrange(8), "c": c}, {"r": x}, "arr c=0x%X" % c)
        judge(s, "eps_price", {"c": c}, {"r": ((gold * c * c) & M64) // 100}, "price lv=%d" % c)
    for k in range(4):  # 사이클마다 level += 1, gold × level ≥ 38400000000 이면 gold //= 2
        lv = k + 1
        if gold * lv >= 38400000000:
            gold //= 2
        judge(s, "eps_main", {}, {"gold": gold}, "main %d" % k)
    return s.report()


def ingame_emulate(ck):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_i64_ops_ingame")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, "i64_ops_ingame.eps"), os.path.join(work, "i64_ops_ingame.eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(work, "i64_ops_ingame.eps"), {})
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "okCount", "total", "ti")
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    err = None
    steps = []
    try:
        for _ in range(130):
            m.cycle()
            steps.append(m.last_steps())
    except emu.EmuError as e:
        err = str(e)
    got = {n: m.var(n) for n in names}
    print("  인게임 맵 에뮬레이션: %r, 첫 사이클 실행 %d, 그 밖 최대 %d" % (got, steps[0] if steps else -1, max(steps[1:] or [-1])))
    ck.eq("ingame emu 오류", err, None)
    ck.eq("ingame emu 값", got, {"frame": 130, "okCount": INGAME_TOTAL, "total": INGAME_TOTAL, "ti": INGAME_TOTAL})


def euddraft_builds(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("i64_ops_example", "i64_ops_ingame"):
        work = os.path.join(_common.WORK, "t_i64_ops_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("euddraft freeze off " + name, not r.freeze)
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, r.log[-1000:])


def eps_checks(ck):
    for name in ("i64_ops_example", "i64_ops_ingame"):
        with open(os.path.join(EX, name + ".eps"), encoding="utf-8") as f:
            src = f.read()
        out, nerr = _compat.eps_compile(name + ".eps", src)
        ck.eq("eps 오류 수 " + name, nerr, 0)
        ck.true("eps 번역 " + name, out is not None)
        if name != "i64_ops_example" or not out:
            continue
        for needle in (
            "i64.f_wrap(alo, ahi) * i64.f_wrap(blo, bhi)",
            "_ATTW(a, 'v').__imul__(i64.f_wrap(blo, bhi))",
            "i64.f_mul32(v, w)",
            "i64.f_mul(v, i64.f_wrap(alo, ahi))",
            "* 10000000000000000",
            "List2Assignable([i64.f_divmod(",
            "_ATTW(a, 'v').__ifloordiv__(",
            "i64.f_wrap(alo, ahi) % 1000",
            "i64.f_div(v, i64.f_wrap(blo, bhi))",
            "i64.f_sdiv(i64.f_wrap(alo, ahi), i64.f_wrap(blo, bhi), div0='ctrig')",
            "a.smod(i64.f_wrap(blo, bhi), div0='ctrig')",
            "i64.f_sdiv(i64.f_wrap(alo, ahi), -7)",
            "(a & b) | (~a ^ b)",
            "_ATTW(a, 'v').__iand__(b)",
            "_ATTW(a, 'v').__ior__(0xF0000000F)",
            "_ATTW(a, 'v').__ixor__(b)",
            "a.iinvert()",
            "a.shl(n) ^ (a >> 3)",
            "_ATTW(r, 'v').__ilshift__(1)",
            "_ATTW(r, 'v').__irshift__(n)",
            "i64.f_to32(a, signed=True)",
            "a.to32(saturate=False)",
            "_ARRW(bag, p).__imul__(v)",
            "_ARRW(bag, p).__ifloordiv__(7)",
            "_ARRW(bag, p).__imod__(1000000000000)",
            "_ARRW(bag, p).__ilshift__(2)",
            "i64.LMul(d, a, 3)",
            "i64.LiDiv(d, d, -5)",
            "i64.f_rand()",
        ):
            ck.true("eps 번역에 %s" % needle, needle.replace("'", '"') in out or needle in out, needle)


def bad_builds(ck):
    """빌드 오류여야 하는 모양 (에뮬레이터 시험 뒤에 부른다 — 실패한 빌드가 뒤 빌드에 영향을 주지 않게)."""
    src = (
        "import eudext.i64 as i64;\n"
        "const hp = i64.Int64(5);\n"
        "var v;\n"
        "function bmul() { const z = v * hp; }\n"
        "function bdiv() { const z = v / hp; }\n"
        "function bmod() { const z = v % hp; }\n"
        "function bshr() { const z = v >> hp; }\n"
        "function bshift() { const z = hp << 3; }\n"
        "function belem() { const g = i64.Int64Array(2); const e = g[0]; e.v *= 3; }\n"
        "function bdiv0() { const z = i64.sdiv(hp, 3, div0=\"c\"); }\n"
        "function bshn() { const z = hp.shl(-1); }\n"
        "function bshi() { const z = hp.shr(hp); }\n"
    )
    out, nerr = _compat.eps_compile("bad_i64_ops.eps", src)
    ck.true("bad eps 번역", out is not None and nerr == 0, str(nerr))
    ns = {}
    exec(compile(out, "bad_i64_ops.eps.py", "exec"), ns)  # noqa: S102 — 시험용 번역문
    want = {
        "f_bmul": "모듈 함수",
        "f_bdiv": "모듈 함수",
        "f_bmod": "모듈 함수",
        "f_bshr": "",  # eudplib 이 Int64 == 0 을 조건으로 만든다 → 조건이 남아 빌드 오류
        "f_bshift": "시프트",
        "f_belem": "사본",
        "f_bdiv0": "div0",
        "f_bshn": "0 이상",
        "f_bshi": "32비트",
    }
    for fn, needle in want.items():
        if fn not in ns:
            ck.true("%s 번역됨" % fn, False, "")
            continue
        LoadMap(BASE_MAP)
        CompressPayload(True)
        try:
            emu.Program(lambda fn=fn: ns[fn]()).build()
            ck.true("%s 빌드 오류" % fn, False, "빌드가 됐다")
        except Exception as e:  # noqa: BLE001
            ck.true("%s 빌드 오류" % fn, needle in str(e), repr(e))


def python_checks(ck):
    with _compat.isolated_scope():
        _python_checks(ck)


def _python_checks(ck):
    x, y = Int64(0), Int64(0)
    v = EUDVariable()
    # 상수 접기
    ck.eq("mul const", i64.mul(M64, M64), 1)
    ck.eq("mul str", i64.mul("12800000000", 3), 38400000000)
    ck.eq("mul neg", i64.mul(-1, 5), (-5) & M64)
    ck.eq("mul32 const", i64.mul32(M32, M32), M32 * M32)
    ck.eq("div const", i64.div(100, 7), 14)
    ck.eq("div0 const", i64.div(100, 0), M64)
    ck.eq("mod0 const", i64.mod(100, 0), 100)
    ck.eq("divmod const", i64.divmod(M64, 10), (M64 // 10, 5))
    ck.eq("sdiv const", i64.sdiv(-7, 2), (-3) & M64)
    ck.eq("smod const", i64.smod(-7, 2), M64)
    ck.eq("sdiv0 eud", i64.sdiv(-7, 0), 1)
    ck.eq("sdiv0 eud+", i64.sdiv(7, 0), M64)
    ck.eq("sdiv0 ct", i64.sdiv(-7, 0, div0="ctrig"), S63)
    ck.eq("sdiv0 ct+", i64.sdiv(7, 0, div0="ctrig"), S63 - 1)
    ck.eq("sdiv min", i64.sdiv(-S63, -1), S63)
    ck.eq("sdivmod const", i64.sdivmod(7, -2), ((-3) & M64, 1))
    ck.eq("and/or/xor/not const", (i64.bitand(12, 10), i64.bitor(12, 10), i64.bitxor(12, 10), i64.bitnot(0)), (8, 14, 6, M64))
    ck.eq("shl const", (i64.shl(1, 63), i64.shl(1, 64), i64.shl(3, 0)), (S63, 0, 3))
    ck.eq("shr const", (i64.shr(M64, 63), i64.shr(M64, 64), i64.shr(M64, 100)), (1, 0, 0))
    ck.eq("to32 const", (i64.to32(1 << 40), i64.to32(-1, signed=True), i64.to32(-(1 << 40), signed=True), i64.to32(1 << 40, saturate=False)),
          (M32, M32, 0x80000000, 0))  # fmt: skip
    ck.eq("abs const", (i64.abs(-5), i64.abs(S63), i64.abs(7)), (5, S63, 7))
    # 모양
    ck.true("mul 새 값", isinstance(x * y, Int64) and isinstance(x * 3, Int64) and isinstance(3 * x, Int64))
    ck.true("div 새 값", isinstance(x // y, Int64) and isinstance(x % 3, Int64) and isinstance(7 // x, Int64))
    qq, rr = divmod(x, y)
    ck.true("divmod 튜플", isinstance(qq, Int64) and isinstance(rr, Int64))
    qq, rr = i64.sdivmod(x, y)
    ck.true("sdivmod 튜플", isinstance(qq, Int64) and isinstance(rr, Int64))
    ck.true("bit 새 값", all(isinstance(z, Int64) for z in (x & y, x | 1, 1 ^ x, ~x, x.invert(), x >> 3, x.shl(v), x.shr(2))))
    ck.true("to32 변수", isinstance(x.to32(), EUDVariable) and isinstance(i64.to32(x, signed=True), EUDVariable))
    ck.true("rand", isinstance(i64.rand(), Int64))
    ck.true("반환 self", all(r is x for r in (x.imul(2), x.idiv(y), x.imod(3), x.iand(y), x.ior(1), x.ixor(y), x.ishl(1),
                                              x.ishr(v), x.iinvert(), x.iabs())))  # fmt: skip
    z = x
    z *= 3
    z //= y
    z %= 5
    z &= y
    z |= 1
    z ^= y
    z <<= 2
    z >>= v
    ck.true("제자리 연산자는 self", z is x)
    ck.true("LMul 반환 dst", i64.LMul(x, x, y) is x and i64.LiDiv(y, x, 3) is y and i64.LRand(x) is x)
    # 오류
    ck.raises("truediv", EudextError, lambda: x / y)
    ck.raises("rtruediv", EudextError, lambda: 3 / x)
    ck.raises("pow", EudextError, lambda: x ** 2)
    ck.raises("rlshift", EudextError, lambda: 3 << x)
    ck.raises("rrshift", EudextError, lambda: 3 >> x)
    ck.raises("shl 음수", EudextError, x.shl, -1)
    ck.raises("shl Int64", EudextError, x.shl, y)
    ck.raises("shl 실수", EudextError, x.shl, 1.5)
    ck.raises("div0 규칙", EudextError, i64.sdiv, x, y, div0="x")
    ck.raises("div0 규칙 상수", EudextError, i64.smod, 1, 2, div0="C")
    ck.raises("to32 인자", EudextError, i64.to32, x, saturate=1)
    ck.raises("mul32 Int64", EudextError, i64.mul32, x, 3)
    ck.raises("mul32 범위", EudextError, i64.mul32, 1 << 32, 3)
    ck.raises("mul 실수", EudextError, lambda: x * 1.5)
    ck.raises("div 조건", EudextError, lambda: x // v.Exactly(1))
    ck.raises("imul 대상", EudextError, i64.imul, v, 3)
    ck.raises("LMul 대상", EudextError, i64.LMul, 5, x, y)
    ck.raises("v * x", EudextError, lambda: v * x)
    ck.raises("v // x", EudextError, lambda: v // x)
    ck.raises("v % x", EudextError, lambda: v % x)
    arr = Int64Array(4)
    e = arr[1]
    for label, fn in (("imul", lambda: e.imul(2)), ("idiv", lambda: e.idiv(2)), ("imod", lambda: e.imod(2)),
                      ("iand", lambda: e.iand(2)), ("ior", lambda: e.ior(2)), ("ixor", lambda: e.ixor(2)),
                      ("ishl", lambda: e.ishl(2)), ("ishr", lambda: e.ishr(2)), ("iinvert", e.iinvert),
                      ("iabs", e.iabs), (".v *=", lambda: e.imulattr("v", 2)), (".v <<=", lambda: e.ilshiftattr("v", 1))):  # fmt: skip
        ck.raises("사본 " + label, EudextError, fn)
    ck.true("사본 → 새 값은 됨", isinstance(e * 2, Int64) and isinstance(e.shl(1), Int64) and isinstance(e.abs(), Int64))
    for nm in ("imulattr", "ifloordivattr", "imodattr", "iandattr", "iorattr", "ixorattr", "ilshiftattr", "irshiftattr"):
        ck.raises("%s 다른 이름" % nm, AttributeError, getattr(x, nm), "w", 1)
    # 이름·별칭 (3.1)
    for nm in ("mul", "mul32", "div", "mod", "divmod", "sdiv", "smod", "sdivmod", "bitand", "bitor", "bitxor", "bitnot", "shl",
               "shr", "to32", "abs", "rand", "imul", "idiv", "imod", "iand", "ior", "ixor", "ishl", "ishr", "iabs", "iinvert"):  # fmt: skip
        ck.true("alias %s" % nm, getattr(i64, nm) is getattr(i64, "f_" + nm))
    for nm in ("LMul", "LDiv", "LMod", "LiDiv", "LiMod", "LAnd", "LOr", "LXor", "LNot", "LAbs", "LRand"):
        ck.true("alias %s" % nm, getattr(i64, nm) is getattr(i64, "f_" + nm))
    ck.true("LiMul = LMul", i64.LiMul is i64.LMul and i64.f_LiMul is i64.f_LMul)
    ck.true("builtins 가리지 않음", "abs" not in i64.__all__ and "divmod" not in i64.__all__)
    ck.eq("__all__ 중복", sorted(i64.__all__), sorted(set(i64.__all__)))
    for name in i64.__all__:
        ck.true("__all__ %s" % name, hasattr(i64, name))
    for name in ("f_mul", "f_div", "f_sdiv", "f_bitand", "f_bitxor", "f_shl", "f_to32", "f_abs", "f_rand", "f_mul32"):
        ck.true("__all__ 에 %s" % name, name in i64.__all__)
    ck.true("배열 별칭", Int64Array.imulitem is Int64Array.imul and Int64Array.ifloordivitem is Int64Array.idiv
            and Int64Array.irshiftitem is Int64Array.ishr)  # fmt: skip
    # docstring 3.12
    for fn in (i64.f_mul, i64.f_mul32, i64.f_div, i64.f_mod, i64.f_divmod, i64.f_sdiv, i64.f_smod, i64.f_bitand, i64.f_bitor,
               i64.f_bitxor, i64.f_bitnot, i64.f_shl, i64.f_shr, i64.f_to32, i64.f_abs, i64.f_rand, Int64.imul, Int64.idiv,
               Int64.shl, Int64.shr):  # fmt: skip
        doc = fn.__doc__ or ""
        ck.true("docstring %s" % fn.__name__, all(k in doc for k in ("비용", "CP", "로컬", "epScript")), doc[:80])
    # 비공개 API 는 _compat 에서만 (3.9)
    with open(i64.__file__, encoding="utf-8") as f:
        text = f.read()
    ck.true("_compat 밖 비공개 API 없음", "from eudplib." not in text and "import eudplib." not in text and "._frets" not in text)
    ck.true("마스크 Add/Subtract 안 씀", "AddNumberX" not in text and "SubtractNumberX" not in text and "AddX" not in text)
    ck.true("P1 마린 칸 안 씀", "0x58A364" not in text)
    ck.true("_compat 접근자", callable(_compat.eudplib_calc_caller) and hasattr(_compat, "_WP4_REQUIRED"))
    for modname, attr in _compat._WP4_REQUIRED:
        ck.true("WP4 비공개 이름 %s.%s" % (modname, attr), hasattr(__import__(modname, fromlist=[attr]), attr))


# ---------------------------------------------------------------------------------------------
# 실행 트리거 수 (DESIGN 3.8 목표) — 최악 입력
# ---------------------------------------------------------------------------------------------


def steps_checks(ck):
    s = Suite("t_i64_ops 실행 수", verbose=False)
    cases = {
        "mul6464": lambda t, a, b: q(t, "r") << a * b,
        "mul6432": lambda t, a, b: q(t, "r") << a * t.var("c"),
        "mul3232": lambda t, a, b: q(t, "r") << i64.mul32(t.var("c"), t.var("e")),
        "mulk": lambda t, a, b: q(t, "r") << a * 0x9E3779B97F4A7C15,
        "div": lambda t, a, b: i64.LDiv(q(t, "r"), a, b),
        "sdiv": lambda t, a, b: i64.LiDiv(q(t, "r"), a, b),
        "shlv": lambda t, a, b: q(t, "r") << a.shl(t.var("n")),
        "shrv": lambda t, a, b: q(t, "r") << a.shr(t.var("n")),
    }
    for name, fn in cases.items():
        s.case(name)(lambda t, fn=fn: (t.var("c"), t.var("e"), t.var("n"), fn(t, q(t, "a"), q(t, "b"))))
    s.build()
    rng = random.Random(71)
    worst = {k: 0 for k in cases}
    vals = [(M64, M64), (M64, M32), (M64, 0x80000001), (M64, 0x80000000), (M64, 0x100000001), (M64, 0x7FFFFFFFFFFFFFFF),
            (M64, (1 << 63) + 1), (M64, 3), (M64, 1)] + [(rng.getrandbits(64), rng.getrandbits(rng.choice((16, 32, 33, 64))))
                                                         for _ in range(40)]  # fmt: skip
    for name in cases:
        for a, b in vals:
            for n in ((1, 31, 33, 63) if name in ("shlv", "shrv") else (1,)):
                r = s.run(name, put(put({"c": M32, "e": M32, "n": n}, "a", a), "b", b))
                worst[name] = max(worst[name], r.steps[0])
    print("  최악 실행 트리거 수: %s" % ", ".join("%s %d" % kv for kv in worst.items()))
    for name in ("mul6464", "mul6432", "mul3232", "mulk"):
        ck.true("곱셈 실행 ≤ 1,000 (%s)" % name, worst[name] <= 1000, str(worst[name]))
    for name in ("div", "sdiv"):
        ck.true("나눗셈 실행 ≤ 711 (%s)" % name, worst[name] <= 711, str(worst[name]))
    ck.true("곱셈이 war.py 비트 루프(2,268)보다 적음", worst["mul6464"] < 2268, str(worst["mul6464"]))
    ck.true("시프트 변수 실행 ≤ 250", max(worst["shlv"], worst["shrv"]) <= 250, str(worst))


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py)
# ---------------------------------------------------------------------------------------------

ABW = [put(put({}, "a", M64), "b", M64), put(put({}, "a", 12800000000), "b", 1000003), put(put({}, "a", 5), "b", 3)]
ADIV = [put(put({}, "a", M64), "b", 10), put(put({}, "a", M64), "b", 0x80000001), put(put({}, "a", M64), "b", 0x100000001),
        put(put({}, "a", M64), "b", (1 << 63) + 1), put(put({}, "a", 12800000000), "b", 3), put(put({}, "a", 5), "b", 0)]  # fmt: skip
A1W = [put({}, "a", M64), put({}, "a", 12800000000), put({}, "a", 5)]
AC = [put({"c": M32}, "a", M64), put({"c": 1000}, "a", 12800000000)]
C1 = [{"c": M32}, {"c": 1000}]
T_MUL = {"exec": 1000}
T_DIV = {"exec": 711}


def _q(t, n):
    return q(t, n)


def _op(fn):
    def build(t):
        fn(t, _q(t, "a"), _q(t, "b"))

    return build


COST_CASES = [
    CostCase("r = x * y (64×64)", _op(lambda t, a, b: a * b), ABW, funcs=[i64._mul_fn(True, True)], target=T_MUL,
             note="16비트 쪼개기. war.py _mul64 2,268~4,626"),  # fmt: skip
    CostCase("x *= y (64×64 제자리)", _op(lambda t, a, b: a.imul(b)), ABW, target=T_MUL),
    CostCase("r = x * v32 (64×32)", lambda t: _q(t, "a") * t.var("c"), AC, funcs=[i64._mul_fn(True, False)], target=T_MUL),
    CostCase("r = mul32(v, w) (32×32)", lambda t: i64.mul32(t.var("c"), t.var("c")), C1, funcs=[i64._mul_fn(False, False)],
             target=T_MUL),  # fmt: skip
    CostCase("r = x * 10^16 (상수, 비트 누적)", _op(lambda t, a, b: a * 10**16), A1W,
             funcs=[i64._mulk_fn(10**16, True, "bt")], target=T_MUL, note="이식판 DPS 에서 가장 흔한 상수 곱"),  # fmt: skip
    CostCase("r = x * 0x9E3779B97F4A7C15 (상수, 비트 누적)", _op(lambda t, a, b: a * 0x9E3779B97F4A7C15), A1W,
             funcs=[i64._mulk_fn(0x9E3779B97F4A7C15, True, "bt")], target=T_MUL),  # fmt: skip
    CostCase("r = x * 10 (작은 상수, 배가·덧셈)", _op(lambda t, a, b: a * 10), A1W, funcs=[i64._mulk_fn(10, True, "sa")],
             target=T_MUL),  # fmt: skip
    CostCase("r = mul(v32, 500) (32비트 × 상수)", lambda t: i64.mul(t.var("c"), 500), C1,
             funcs=[i64._mulk_fn(500, False, "bt")], target=T_MUL),  # fmt: skip
    CostCase("r = x * 2^20 (시프트)", _op(lambda t, a, b: a * (1 << 20)), A1W, funcs=[i64._shk_fn("shl", 20)], target=T_MUL),
    CostCase("r = x * 1", _op(lambda t, a, b: a * 1), A1W),
    CostCase("q, r = divmod(x, y) (변수)", _op(lambda t, a, b: i64.divmod(a, b)), ADIV, funcs=[i64._udiv_fn()], target=T_DIV,
             note="32비트 제수 A/B·64비트 제수·몫 0/1·0 나눗셈 섞음. war.py 약 711"),  # fmt: skip
    CostCase("r = x // y (변수)", _op(lambda t, a, b: a // b), ADIV, target=T_DIV),
    CostCase("x //= y (제자리)", _op(lambda t, a, b: a.idiv(b)), ADIV, target=T_DIV),
    CostCase("r = x // v32", lambda t: _q(t, "a") // t.var("c"), AC, target=T_DIV),
    CostCase("r = x // 10 (상수 < 2^32)", _op(lambda t, a, b: a // 10), A1W, funcs=[i64._cdiv_fn(10, "q")], target=T_DIV),
    CostCase("r = x % 10000 (상수 나머지)", _op(lambda t, a, b: a % 10000), A1W, funcs=[i64._cdiv_fn(10000, "r")],
             target=T_DIV, note="이식판 f_LMod(…, \"10000\") 171 → 74"),  # fmt: skip
    CostCase("q, r = divmod(x, 0x123456789) (상수 ≥ 2^32)", _op(lambda t, a, b: i64.divmod(a, 0x123456789)), A1W,
             funcs=[i64._cdiv_fn(0x123456789, "qr")], target=T_DIV),  # fmt: skip
    CostCase("r = x // 1024 (시프트)", _op(lambda t, a, b: a // 1024), A1W, funcs=[i64._shk_fn("shr", 10)], target=T_DIV),
    CostCase("q, r = sdivmod(x, y) (부호 있음)", _op(lambda t, a, b: i64.sdivmod(a, b)), ADIV,
             funcs=[i64._sdiv_fn("eudplib")], target={"exec": 800}, note="부호 없는 나눗셈 + 부호 떼기·붙이기"),  # fmt: skip
    CostCase("r = sdiv(x, -7) (상수)", _op(lambda t, a, b: i64.sdiv(a, -7)), A1W, funcs=[i64._sdivk_fn((-7) & M64, "eudplib")]),
    CostCase("r = x & y", _op(lambda t, a, b: a & b), ABW),
    CostCase("r = x | y", _op(lambda t, a, b: a | b), ABW),
    CostCase("r = x ^ y", _op(lambda t, a, b: a ^ b), ABW, note="(a|b) ⊖ (a&b)"),
    CostCase("x ^= y (제자리)", _op(lambda t, a, b: a.ixor(b)), ABW),
    CostCase("x &= 0xFFFF (상수)", _op(lambda t, a, b: a.iand(0xFFFF)), A1W),
    CostCase("x ^= 0xF0F0F0F0F0F0F0F0 (상수)", _op(lambda t, a, b: a.ixor(0xF0F0F0F0F0F0F0F0)), A1W),
    CostCase("r = ~x", _op(lambda t, a, b: ~a), A1W),
    CostCase("x.iinvert()", _op(lambda t, a, b: a.iinvert()), A1W),
    CostCase("r = x.shl(1) (인라인)", _op(lambda t, a, b: a.shl(1)), A1W),
    CostCase("x <<= 7 (상수)", _op(lambda t, a, b: a.ishl(7)), A1W, funcs=[i64._shk_fn("shl", 7)]),
    CostCase("x <<= 20 (상수, 비트 옮기기)", _op(lambda t, a, b: a.ishl(20)), A1W, funcs=[i64._shk_fn("shl", 20)]),
    CostCase("x >>= 5 (상수, 비트 옮기기)", _op(lambda t, a, b: a.ishr(5)), A1W, funcs=[i64._shk_fn("shr", 5)]),
    CostCase("x >>= 30 (상수, 96비트 창)", _op(lambda t, a, b: a.ishr(30)), A1W, funcs=[i64._shk_fn("shr", 30)]),
    CostCase("x >>= 32 (인라인)", _op(lambda t, a, b: a.ishr(32)), A1W),
    CostCase("x <<= n (변수, n = 63)", lambda t: _q(t, "a").ishl(t.var("n")), [put({"n": 63}, "a", M64), put({"n": 5}, "a", M64)],
             funcs=[i64._shv_fn("shl")]),  # fmt: skip
    CostCase("x >>= n (변수, n = 33·1)", lambda t: _q(t, "a").ishr(t.var("n")), [put({"n": 33}, "a", M64), put({"n": 1}, "a", M64)],
             funcs=[i64._shv_fn("shr")]),  # fmt: skip
    CostCase("v = x.to32()", _op(lambda t, a, b: a.to32()), A1W),
    CostCase("v = x.to32(signed=True)", _op(lambda t, a, b: a.to32(signed=True)), A1W),
    CostCase("r = x.abs()", _op(lambda t, a, b: a.abs()), A1W + [put({}, "a", 1 << 63)], funcs=[i64._abs_fn()]),
    CostCase("r = rand()", lambda t: i64.rand(), [{}], funcs=[f_dwrand], note="f_dwrand × 2"),
    CostCase("arr[i] *= y (변수 칸)", lambda t: Int64Array(8).imul(t.var("i"), _q(t, "b")), [put({"i": 2}, "b", M64)]),
    CostCase("arr[3] &= 0xFFFF (상수 칸·상수 값)", lambda t: Int64Array(8).iand(3, 0xFFFF)),
    CostCase("참고: eudplib f_mul(v, w) (32비트, 하위만)", lambda t: f_mul(t.var("c"), t.var("e")),
             [{"c": M32, "e": M32}, {"c": 1000, "e": 7}], note="64비트 곱이 필요해 쓰지 않음"),  # fmt: skip
    CostCase("참고: eudplib f_div(v, w) (32비트)", lambda t: f_div(t.var("c"), t.var("e")),
             [{"c": M32, "e": 1}, {"c": M32, "e": 0x80000001}, {"c": 1000, "e": 7}], note="제수 배수 표를 매번 만든다"),  # fmt: skip
    CostCase("참고: i64.div(v, w) (32비트 둘)", lambda t: i64.div(t.var("c"), t.var("e")),
             [{"c": M32, "e": 1}, {"c": M32, "e": 0x80000001}, {"c": 1000, "e": 7}]),  # fmt: skip
]


def main():
    before = set(t_i64.repo_artifacts())
    ck = Checker("t_i64_ops (python)")
    eps = t_i64.load_eps("i64_ops_example")
    oks = [suite_vars(), suite_const(), suite_shift(), suite_misc(), suite_eps(eps)]
    python_checks(ck)
    eps_checks(ck)
    steps_checks(ck)
    ingame_emulate(ck)
    euddraft_builds(ck)
    bad_builds(ck)
    mine = [p for p in set(t_i64.repo_artifacts()) - before if "i64" in p or "__epspy__" in p or p.endswith(".scx")]
    ck.eq("repo clean", sorted(mine), [])
    oks.append(ck.report())
    finish(*oks)


if __name__ == "__main__":
    main()
