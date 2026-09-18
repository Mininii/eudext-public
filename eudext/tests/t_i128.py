"""`i128`(WP20) 차등 시험 (에뮬레이터): 128비트 대입·덧셈·wrap/포화 뺄셈·비교·곱셈·나눗셈·10진·내리기·배열·epScript.

- 변수끼리: 경계값 24개 전 쌍(576) + 무작위 쌍(비트 폭·제수 모양을 섞음 — 32비트 제수 > 2^31, 64비트 제수 ≥ 2^63(넘침 비트),
  128비트 제수, D ≥ 2^127, N < D, 0) × 모든 연산(연산자·메서드·모듈 함수·DPS 별칭·`.v` 통로·인라인/공유 함수).
  같은 객체끼리, 칸이 엇갈려 겹치는 경우, Int64·32비트 변수 섞기(0 확장, 64×64·64×32·32×32 전체 곱).
- 상수: KS 개 × (경계값 + 상수 근처 + 무작위) × (오른쪽·왼쪽, 정수·음수·10진 문자열 표기) × 모든 연산.
- 비교 문맥(EUDIf·neg·EUDNot·RawTrigger·EUDSCAnd/Or ± neg·목록·EUDTernary ± neg·EUDElseIf), EUDWhile 조건 재계산,
  Int128Array(상수·변수 칸 × 상수·변수 값), 생성 규칙, 10진 출력 바이트(fmt·lidec_to 상수/변수 dst), to64/to32.
- DPS math128 호출 모양 재현(CallTriggers·mine·money·damage_check·GlobalBoss·token·sell_refactored·TBL),
  이식판 `eud/tests/t_war.py`(a7aad90) 128비트 기대값(D128 11쌍·K128 6개·M128 9쌍).
- epScript 예제(examples/i128_example.eps) 번역·에뮬레이터·euddraft 빌드, 인게임 확인 맵(i128_ingame) 에뮬레이션·빌드,
  빌드 오류여야 하는 모양, 실행 트리거 수(COST_CASES), 파이썬 쪽 판정.

python tests/t_i128.py                     (기본: 무작위 쌍 600 — 234,778 판정, 약 2분 15초)
EUDEXT_I128_FULL=1 python tests/t_i128.py  (전체: 무작위 쌍 4,000, 상수 값·10진 값 늘림 — 872,888 판정, 약 9분)
EUDEXT_I128_ONLY=vars,const,misc,eps,py,ingame,build,bad  (묶음 고르기)
비용 표: python tools/cost.py tests/t_i128.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import types  # noqa: E402

from eudplib import (  # noqa: E402
    EPD,
    AtLeast,
    AtMost,
    CompressPayload,
    Condition,
    Db,
    DoActions,
    EPSLoader,
    EUDBreakIf,
    EUDElse,
    EUDElseIf,
    EUDEndIf,
    EUDEndWhile,
    EUDIf,
    EUDLightBool,
    EUDLightVariable,
    EUDNot,
    EUDSCAnd,
    EUDSCOr,
    EUDTernary,
    EUDTypedFunc,
    EUDVariable,
    EUDWhile,
    Exactly,
    Forward,
    LoadMap,
    RawTrigger,
    SeqCompute,
    SetTo,
    Trigger,
    f_dbstr_print,
    f_sprintf,
)

from eudext import _compat, i64, i128  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.i64 import Int64  # noqa: E402
from eudext.i128 import Int128, Int128Array  # noqa: E402
from eudext.testing import emu  # noqa: E402
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
M96 = (1 << 96) - 1
M128 = (1 << 128) - 1
S63 = 1 << 63
S127 = 1 << 127
EX = os.path.join(_common.PKG, "examples")
FULL = os.environ.get("EUDEXT_I128_FULL") == "1"
NRAND = 4000 if FULL else 600
NKVAL = 30 if FULL else 10
INGAME_TOTAL = 46  # examples/i128_ingame.eps 의 점검 수

# 경계값 24개 — 칸 경계(2^32·2^64·2^96)의 올림·빌림, 2^127, 10진 자리 경계, 칸마다 다른 무늬
EDGES = (
    0, 1, 2, 0x7FFFFFFF, M32, 1 << 32, (1 << 32) + 1, S63, M64, 1 << 64, (1 << 64) + 1, 1 << 95,
    M96, 1 << 96, (1 << 96) + M32, S127 - 1, S127, S127 + 1, M128 - 1, M128,
    10**19, 10**38, 0xFFFFFFFF00000000FFFFFFFF00000000, 0x123456789ABCDEF0FEDCBA9876543210,
)  # fmt: skip
assert len(EDGES) == 24 and len(set(EDGES)) == 24


def rand_pairs(n, seed):
    """비트 폭·제수 모양을 섞은 무작위 쌍 (나눗셈 경로가 고루 나오게)."""
    rng = random.Random(seed)
    out = []
    widths = (1, 8, 31, 32, 33, 48, 63, 64, 65, 80, 95, 96, 97, 110, 127, 128)
    for _ in range(n):
        a, b = rng.getrandbits(rng.choice(widths)), rng.getrandbits(rng.choice(widths))
        r = rng.random()
        if r < 0.06:
            b = 0
        elif r < 0.14:
            b = a >> rng.randrange(0, 70) or 1
        elif r < 0.22:
            b = (1 << 63) | rng.getrandbits(63)  # 64비트 제수 ≥ 2^63 (넘침 비트)
        elif r < 0.30:
            b = (1 << 31) | rng.getrandbits(31)  # 32비트 제수 > 2^31
        elif r < 0.36:
            b = (1 << 127) | rng.getrandbits(127)  # D ≥ 2^127
        elif r < 0.46:
            b = (1 << rng.randrange(64, 127)) | rng.getrandbits(64)  # 128비트 제수
        elif r < 0.50:
            b = rng.getrandbits(64) << 64
        elif r < 0.55:
            b = a
        elif r < 0.62:
            b = (a & (M128 ^ M32)) | rng.getrandbits(32)  # 위 칸이 같음
        if rng.random() < 0.15:
            a = M128 - rng.getrandbits(rng.choice((8, 64, 100)))
        if rng.random() < 0.1:
            a, b = b, a
        out.append((a & M128, b & M128))
    return out


PAIRS = [(a, b) for a in EDGES for b in EDGES] + rand_pairs(NRAND, 20)


def ref_div(a, b):
    return (a // b, a % b) if b else (M128, a)


PYCMP = {
    "ge": lambda x, y: x >= y,
    "gt": lambda x, y: x > y,
    "le": lambda x, y: x <= y,
    "lt": lambda x, y: x < y,
    "eq": lambda x, y: x == y,
    "ne": lambda x, y: x != y,
}
CMP_OPS = tuple(PYCMP)


# ---------------------------------------------------------------------------------------------
# 도우미
# ---------------------------------------------------------------------------------------------


def q(t, name):
    """128비트 입력·출력 칸 (name.0 ~ name.3)."""
    return Int128.wrap(*(t.var("%s.%d" % (name, k)) for k in range(4)))


def q64(t, name):
    """64비트 입력·출력 칸 (name.0, name.1 — 128비트 판정은 위 칸이 없으면 64비트로 읽는다)."""
    return Int64.wrap(t.var(name + ".0"), t.var(name + ".1"))


def put(d, name, v):
    for k in range(4):
        d["%s.%d" % (name, k)] = (v >> (32 * k)) & M32
    return d


def put64(d, name, v):
    d[name + ".0"] = v & M32
    d[name + ".1"] = (v >> 32) & M32
    return d


def judge(s, case, inputs, expect, label, fresh=False):
    """케이스를 한 번 돌리고 출력마다 판정을 하나씩 기록한다. 이름.0 이 있으면 128비트(또는 64비트) 값."""
    r = s.run(case, inputs, fresh=fresh)
    if r.error:
        s.expect_true(case, False, label, r.error)
        return r
    vals = r.values
    for k, want in expect.items():
        if k + ".0" in vals:
            n = sum(1 for j in range(4) if "%s.%d" % (k, j) in vals)
            got = sum(vals["%s.%d" % (k, j)] << (32 * j) for j in range(n))
            want &= (1 << (32 * n)) - 1
            fmt = "0x%X"
        else:
            got = vals.get(k)
            want &= M32
            fmt = "0x%X"
        if got == want:
            s.expect_true(case, True, label)
        else:
            s.expect_true(case, False, "%s %s" % (label, k), ("got " + fmt + " want " + fmt) % (got if got is not None else -1, want))
    return r


def ifval(t, name, mk, neg=False):
    v = t.var(name)
    if EUDIf()(mk(), neg=neg):
        v << 1
    if EUDElse()():
        v << 0
    EUDEndIf()


def contexts(t, tag, mk):
    """mk() 는 부를 때마다 새 조건을 만든다. 결과 이름: tag + 접미사 (i64 시험과 같은 12 문맥)."""
    z = t.var("z")
    ifval(t, tag + "_if", mk)
    ifval(t, tag + "_neg", mk, neg=True)
    nv = EUDNot(mk())
    ifval(t, tag + "_not", lambda: nv)
    rr = t.var(tag + "_raw")
    DoActions(rr.SetNumber(0))
    RawTrigger(conditions=mk(), actions=rr.SetNumber(1))
    ifval(t, tag + "_and", lambda: EUDSCAnd()(z.Exactly(0))(mk())())
    ifval(t, tag + "_andn", lambda: EUDSCAnd()(z.Exactly(0))(mk(), neg=True)())
    ifval(t, tag + "_or", lambda: EUDSCOr()(z.Exactly(1))(mk())())
    ifval(t, tag + "_orn", lambda: EUDSCOr()(z.Exactly(1))(mk(), neg=True)())
    ifval(t, tag + "_list", lambda: [z.Exactly(0), [mk()]])
    t.out(tag + "_tern", EUDTernary(mk())(1)(0))
    t.out(tag + "_ternn", EUDTernary(mk(), neg=True)(1)(0))
    re_ = t.var(tag + "_elif")
    if EUDIf()(z.Exactly(1)):
        re_ << 2
    if EUDElseIf()(mk()):
        re_ << 1
    if EUDElse()():
        re_ << 0
    EUDEndIf()


def ctx_expect(tag, r0):
    e = {tag + "_if": r0, tag + "_neg": 1 - r0, tag + "_not": 1 - r0, tag + "_raw": r0}
    e.update({tag + s: r0 for s in ("_and", "_or", "_list", "_tern", "_elif")})
    e.update({tag + s: 1 - r0 for s in ("_andn", "_orn", "_ternn")})
    return e


def sw(x):
    """칸을 엇갈려 감싼 값 (w1, w0, w3, w2)."""
    return Int128.wrap(x.w1, x.w0, x.w3, x.w2)


def swv(v):
    w = [(v >> (32 * k)) & M32 for k in range(4)]
    return w[1] | (w[0] << 32) | (w[3] << 64) | (w[2] << 96)


# ---------------------------------------------------------------------------------------------
# 묶음 1: 변수끼리
# ---------------------------------------------------------------------------------------------

ADD_NAMES = ("add1", "add2", "add3", "add4", "add5", "add6", "add7", "add8", "add9")
SUB_NAMES = ("sub1", "sub2", "sub3", "sub4", "sub5", "sub6", "sub7")
SAT_NAMES = ("ss1", "ss2", "ss3", "ss4", "ss5", "ss6", "ss7", "ss8")


def build_vars(s):
    @s.case("addsub")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        q(t, "add1") << a + b
        q(t, "add2") << i128.add(a, b)
        q(t, "add3") << i128.add(a, b, inline=True)
        x = q(t, "add4")
        x << a
        x += b
        x = q(t, "add5")
        x << a
        x.iadd(b, inline=True)
        x = q(t, "add6")
        x << a
        x.iaddattr("v", b)
        x = q(t, "add7")
        x.assign(a)
        i128.iadd(x, b, inline=False)
        q(t, "add8") << i128.LAdd128(a, b)
        q(t, "add9") << b + a
        q(t, "sub1") << a - b
        q(t, "sub2") << i128.sub(a, b)
        q(t, "sub3") << i128.sub(a, b, inline=True)
        x = q(t, "sub4")
        x << a
        x -= b
        x = q(t, "sub5")
        x << a
        x.isub(b, inline=True)
        x = q(t, "sub6")
        x.v = a
        x.isubattr("v", b)
        q(t, "sub7") << -(b - a)
        q(t, "neg1") << -a
        q(t, "neg2") << i128.neg(a)
        x = q(t, "neg3")
        x << a
        x.ineg()
        q(t, "ss1") << i128.sub_sat(a, b)
        q(t, "ss2") << i128.sub_sat(a, b, inline=True)
        x = q(t, "ss3")
        x << a
        x.isub_sat(b)
        x = q(t, "ss4")
        x << a
        x.isub_sat(b, inline=True)
        x = q(t, "ss5")
        x << a
        x.isubtractattr("v", b)
        x = q(t, "ss6")
        x << a
        i128.isub_sat(x, b)
        q(t, "ss7") << i128.LSub128(a, b)
        x = q(t, "ss8")
        x << a
        i128.isub_sat(x, b, inline=True)
        i128.LMov128(q(t, "mov"), a)

    @s.case("cmp")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        ops = {
            "ge": lambda: a >= b,
            "gt": lambda: a > b,
            "le": lambda: a <= b,
            "lt": lambda: a < b,
            "eq": lambda: a == b,
            "ne": lambda: a != b,
        }
        for op, mk in ops.items():
            t.flag(op + "1", mk())
            t.flag(op + "2", getattr(i128, op)(a, b))
            t.flag(op + "3", getattr(i128, "f_" + op)(b, a))  # 뒤집은 쪽
        for op, sym in (("ge", ">="), ("gt", ">"), ("le", "<="), ("lt", "<"), ("eq", "=="), ("ne", "!=")):
            t.flag(op + "4", i128.LCmp128(a, sym, b))
        t.flag("ge5", i128.Compare_128(a, AtLeast, b))
        t.flag("le5", i128.LCmp128(a, AtMost, b))
        t.flag("eq5", i128.LCmp128(a, Exactly, b))
        contexts(t, "cge", lambda: a >= b)
        contexts(t, "cgt", lambda: a > b)
        contexts(t, "ceq", lambda: a == b)

    @s.case("mul")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        q(t, "m1") << a * b
        q(t, "m2") << i128.mul(a, b)
        x = q(t, "m3")
        x << a
        x *= b
        x = q(t, "m4")
        x << a
        x.imul(b)
        x = q(t, "m5")
        x << a
        x.imulattr("v", b)
        x = q(t, "m6")
        x << a
        i128.imul(x, b)
        q(t, "m7") << b * a

    @s.case("div")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        q(t, "d1") << a // b
        q(t, "r1") << a % b
        qq, rr = i128.divmod(a, b)
        q(t, "d2") << qq
        q(t, "r2") << rr
        qq, rr = divmod(a, b)
        q(t, "d3") << qq
        q(t, "r3") << rr
        x = q(t, "d4")
        x << a
        x //= b
        x = q(t, "r4")
        x << a
        x %= b
        x = q(t, "d5")
        x << a
        x.idiv(b)
        x = q(t, "r5")
        x << a
        x.imod(b)
        x = q(t, "d6")
        x << a
        x.ifloordivattr("v", b)
        x = q(t, "r6")
        x << a
        x.imodattr("v", b)
        qq, rr = i128.LDiv128(a, b)
        q(t, "d7") << qq
        q(t, "r7") << rr
        q(t, "d8") << i128.div(a, b)
        q(t, "r8") << i128.mod(a, b)
        x = q(t, "d9")
        x << a
        i128.idiv(x, b)
        x = q(t, "r9")
        x << a
        i128.imod(x, b)

    @s.case("conv")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        q64(t, "t64s") << a.to64()
        q64(t, "t64w") << i128.to64(a, saturate=False)
        t.out("t32s", a.to32())
        t.out("t32w", i128.to32(a, saturate=False))
        q(t, "pair") << Int128(a.lo, b.hi)
        q(t, "pair2") << Int128(b.hi, a.lo)
        q(t, "copy") << Int128(a)
        q(t, "lohi") << Int128.wrap(a.hi, a.lo)
        q64(t, "lo") << a.lo
        q64(t, "hi") << a.hi
        q(t, "up64") << Int128(b.lo)
        q(t, "up32") << Int128(b.w0)
        q(t, "w32") << Int128(a.w3, b.w2)

    @s.case("mixed")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        b64, b32 = b.lo, b.w0
        q(t, "add64") << a + b64
        q(t, "radd64") << i128.add(b64, a)  # Int64 가 왼쪽이면 i64 연산자가 먼저 불린다 → 모듈 함수
        q(t, "sub64") << a - b64
        q(t, "rsub64") << i128.sub(b64, a)
        q(t, "ss64") << i128.sub_sat(a, b64)
        q(t, "rss64") << i128.sub_sat(b64, a)
        q(t, "mul64") << a * b64
        q(t, "div64") << a // b64
        q(t, "mod64") << a % b64
        q(t, "rdiv64") << i128.div(b64, a)
        q(t, "rmod64") << i128.mod(b64, a)
        t.flag("ge64", a >= b64)
        t.flag("rge64", i128.ge(b64, a))
        t.flag("eq64", a == b64)
        q(t, "add32") << a + b32
        x = q(t, "iadd32")
        x << a
        x += b32
        x = q(t, "isub32")
        x << a
        x -= b32
        x = q(t, "iss32")
        x << a
        x.isub_sat(b32)
        q(t, "mul32") << i128.mul(b32, a)
        q(t, "div32") << a // b32
        q(t, "mod32") << a % b32
        q(t, "rdiv32") << i128.div(b32, a)
        t.flag("rgt32", i128.gt(b32, a))
        t.flag("lt32", a < b32)
        q(t, "p6464") << i128.mul64(a.lo, b64)
        q(t, "p6432") << i128.mul64(a.lo, b32)
        q(t, "p3264") << i128.LMul128(b32, a.hi)
        q(t, "p3232") << i128.LMul128_2(a.w1, b32)
        q(t, "p128_32") << a * b32

    @s.case("same")
    def _(t):
        a = q(t, "a")
        q(t, "b")  # 입력 칸만
        x = q(t, "dbl")
        x << a
        x += x
        q(t, "dbl2") << a + a
        x = q(t, "zero1")
        x << a
        x -= x
        x = q(t, "zero2")
        x << a
        x.isub_sat(x)
        q(t, "zero3") << i128.sub_sat(a, a)
        q(t, "zero4") << a - a
        x = q(t, "sq")
        x << a
        x *= x
        q(t, "sq2") << a * a
        x = q(t, "one")
        x << a
        x //= x
        x = q(t, "rem")
        x << a
        x %= x
        qq, rr = i128.divmod(a, a)
        q(t, "one2") << qq
        q(t, "rem2") << rr
        for op in CMP_OPS:
            t.flag("s" + op, getattr(i128, op)(a, a))

    @s.case("alias")
    def _(t):
        a = q(t, "a")
        q(t, "b")  # 입력 칸만
        for name, fn in (
            ("xa", lambda x: x.__iadd__(sw(x))),
            ("xs", lambda x: x.__isub__(sw(x))),
            ("xss", lambda x: x.isub_sat(sw(x))),
            ("xssi", lambda x: x.isub_sat(sw(x), inline=True)),
            ("xm", lambda x: x.__imul__(sw(x))),
            ("xd", lambda x: x.__ifloordiv__(sw(x))),
            ("xr", lambda x: x.__imod__(sw(x))),
            ("xmov", lambda x: i128.LMov128(x, sw(x))),
            ("xl", lambda x: x.__iadd__(Int128.wrap(x.w3, x.w3, x.w0, x.w1))),
        ):
            x = q(t, name)
            x << a
            fn(x)

    def ref_addsub(a, b):
        e = {}
        for n in ADD_NAMES:
            e[n] = (a + b) & M128
        for n in SUB_NAMES:
            e[n] = (a - b) & M128
        for n in SAT_NAMES:
            e[n] = max(a - b, 0)
        e.update({"neg1": -a & M128, "neg2": -a & M128, "neg3": -a & M128, "mov": a})
        return e

    def ref_cmp(a, b):
        e = {}
        for op, f in PYCMP.items():
            e[op + "1"] = int(f(a, b))
            e[op + "2"] = int(f(a, b))
            e[op + "3"] = int(f(b, a))
            e[op + "4"] = int(f(a, b))
        e.update({"ge5": int(a >= b), "le5": int(a <= b), "eq5": int(a == b)})
        e.update(ctx_expect("cge", int(a >= b)))
        e.update(ctx_expect("cgt", int(a > b)))
        e.update(ctx_expect("ceq", int(a == b)))
        return e

    def ref_mul(a, b):
        return {"m%d" % k: (a * b) & M128 for k in range(1, 8)}

    def ref_divs(a, b):
        qq, rr = ref_div(a, b)
        e = {}
        for k in range(1, 10):
            e["d%d" % k] = qq
            e["r%d" % k] = rr
        return e

    def ref_conv(a, b):
        return {
            "t64s": min(a, M64),
            "t64w": a & M64,
            "t32s": min(a, M32),
            "t32w": a & M32,
            "pair": (a & M64) | ((b >> 64) << 64),
            "pair2": (b >> 64) | ((a & M64) << 64),
            "copy": a,
            "lohi": (a >> 64) | ((a & M64) << 64),
            "lo": a & M64,
            "hi": a >> 64,
            "up64": b & M64,
            "up32": b & M32,
            "w32": (a >> 96) | (((b >> 64) & M32) << 64),
        }

    def ref_mixed(a, b):
        b64, b32 = b & M64, b & M32
        return {
            "add64": (a + b64) & M128,
            "radd64": (a + b64) & M128,
            "sub64": (a - b64) & M128,
            "rsub64": (b64 - a) & M128,
            "ss64": max(a - b64, 0),
            "rss64": max(b64 - a, 0),
            "mul64": (a * b64) & M128,
            "div64": ref_div(a, b64)[0],
            "mod64": ref_div(a, b64)[1],
            "rdiv64": ref_div(b64, a)[0],
            "rmod64": ref_div(b64, a)[1],
            "ge64": int(a >= b64),
            "rge64": int(b64 >= a),
            "eq64": int(a == b64),
            "add32": (a + b32) & M128,
            "iadd32": (a + b32) & M128,
            "isub32": (a - b32) & M128,
            "iss32": max(a - b32, 0),
            "mul32": (a * b32) & M128,
            "div32": ref_div(a, b32)[0],
            "mod32": ref_div(a, b32)[1],
            "rdiv32": ref_div(b32, a)[0],
            "rgt32": int(b32 > a),
            "lt32": int(a < b32),
            "p6464": (a & M64) * b64,
            "p6432": (a & M64) * b32,
            "p3264": b32 * (a >> 64),
            "p3232": ((a >> 32) & M32) * b32,
            "p128_32": (a * b32) & M128,
        }

    def ref_same(a, b):
        del b
        qq, rr = ref_div(a, a)
        e = {
            "dbl": (2 * a) & M128,
            "dbl2": (2 * a) & M128,
            "zero1": 0,
            "zero2": 0,
            "zero3": 0,
            "zero4": 0,
            "sq": (a * a) & M128,
            "sq2": (a * a) & M128,
            "one": qq,
            "rem": rr,
            "one2": qq,
            "rem2": rr,
        }
        for op, f in PYCMP.items():
            e["s" + op] = int(f(a, a))
        return e

    def ref_alias(a, b):
        del b
        s = swv(a)
        w = [(a >> (32 * k)) & M32 for k in range(4)]
        l_ = w[3] | (w[3] << 32) | (w[0] << 64) | (w[1] << 96)
        return {
            "xa": (a + s) & M128,
            "xs": (a - s) & M128,
            "xss": max(a - s, 0),
            "xssi": max(a - s, 0),
            "xm": (a * s) & M128,
            "xd": ref_div(a, s)[0],
            "xr": ref_div(a, s)[1],
            "xmov": s,
            "xl": (a + l_) & M128,
        }

    return {
        "addsub": ref_addsub,
        "cmp": ref_cmp,
        "mul": ref_mul,
        "div": ref_divs,
        "conv": ref_conv,
        "mixed": ref_mixed,
        "same": ref_same,
        "alias": ref_alias,
    }


def suite_vars():
    s = Suite("t_i128 변수끼리")
    refs = build_vars(s)
    s.build()
    once = {"same", "alias", "conv"}
    for n, (a, b) in enumerate(PAIRS):
        d = put(put({}, "a", a), "b", b)
        for case, ref in refs.items():
            if case in once and n % 3:
                continue
            judge(s, case, d, ref(a, b), "a=0x%X b=0x%X" % (a, b))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 2: 상수
# ---------------------------------------------------------------------------------------------

KS = (
    0, 1, 2, 3, 7, 10, 100, 1000, 5000, 10**8, 0x7FFFFFFF, 0x80000001, M32, 1 << 32, 0x100000001,
    6500000000000, 10**16, S63, M64, 1 << 64, 10**20, 10**30, S127, S127 + 12345, M128, 1 << 100,
)  # fmt: skip


def literal(k, form):
    """상수 k 의 표기: 0 = 정수, 1 = 음수(2^127 이상) 또는 10진 문자열, 2 = 10진 문자열."""
    if form == 1 and k >= S127:
        return k - (1 << 128)
    if form >= 1:
        return "{:,}".format(k) if form == 1 else str(k)
    return k


def build_k(s, idx, K):
    kf = literal(K, idx % 3)

    @s.case("k%d" % idx)
    def _(t):
        a = q(t, "a")
        q(t, "add") << a + kf
        q(t, "radd") << kf + a
        q(t, "sub") << a - kf
        q(t, "rsub") << kf - a
        q(t, "ss") << i128.sub_sat(a, kf)
        q(t, "rss") << i128.sub_sat(kf, a)
        x = q(t, "iadd")
        x << a
        x += kf
        x = q(t, "isub")
        x << a
        x -= kf
        x = q(t, "iss")
        x << a
        x.isub_sat(kf)
        q(t, "mul") << a * kf
        q(t, "rmul") << kf * a
        x = q(t, "imul")
        x << a
        x *= kf
        q(t, "div") << a // kf
        q(t, "mod") << a % kf
        q(t, "rdiv") << i128.div(kf, a)
        q(t, "rmod") << i128.mod(kf, a)
        x = q(t, "idiv")
        x << a
        x //= kf
        x = q(t, "imod")
        x << a
        x %= kf
        qq, rr = i128.divmod(a, kf)
        q(t, "qd") << qq
        q(t, "qr") << rr
        for op in CMP_OPS:
            t.flag(op, getattr(i128, op)(a, kf))
            t.flag("r" + op, getattr(i128, op)(kf, a))
        if K <= M64:
            q(t, "mul64k") << i128.mul64(a.lo, kf)
        q(t, "cmul") << Int128(a.w0) * kf  # 32비트 × 상수

    def ref(a):
        dq, dr = ref_div(a, K)
        rq, rr = ref_div(K, a)
        e = {
            "add": (a + K) & M128,
            "radd": (a + K) & M128,
            "sub": (a - K) & M128,
            "rsub": (K - a) & M128,
            "ss": max(a - K, 0),
            "rss": max(K - a, 0),
            "iadd": (a + K) & M128,
            "isub": (a - K) & M128,
            "iss": max(a - K, 0),
            "mul": (a * K) & M128,
            "rmul": (a * K) & M128,
            "imul": (a * K) & M128,
            "div": dq,
            "mod": dr,
            "rdiv": rq,
            "rmod": rr,
            "idiv": dq,
            "imod": dr,
            "qd": dq,
            "qr": dr,
            "cmul": ((a & M32) * K) & M128,
        }
        if K <= M64:
            e["mul64k"] = (a & M64) * K
        for op, f in PYCMP.items():
            e[op] = int(f(a, K))
            e["r" + op] = int(f(K, a))
        return e

    return ref


def suite_const():
    s = Suite("t_i128 상수")
    refs = [build_k(s, idx, K) for idx, K in enumerate(KS)]
    s.build()
    rng = random.Random(77)
    for idx, K in enumerate(KS):
        vals = list(EDGES) + [(K + d) & M128 for d in (-2, -1, 0, 1, 2)] + [K * 7 // 3 & M128, (K << 1) & M128]
        for _ in range(NKVAL):
            vals.append(rng.getrandbits(rng.choice((16, 32, 64, 96, 128))))
        for a in vals:
            judge(s, "k%d" % idx, put({}, "a", a), refs[idx](a), "K=0x%X a=0x%X" % (K, a))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 3: 루프·배열·생성·출력·DPS 모양·이식판 기대값
# ---------------------------------------------------------------------------------------------

FMT_VALS = (
    tuple(EDGES)
    + tuple(10**k for k in range(39))
    + tuple(10**k - 1 for k in range(1, 39))
    + tuple(2**k for k in (63, 64, 65, 95, 96, 97, 126))
    + (5, 100, 12800000000, 10**19 + 5, 10**20 - 1, 10**20 + 10**19)
)  # fmt: skip

ARR_K = (5, M32, 1 << 32, 1 << 64, (1 << 96) + 7, M128, S127)


def load_eps(name):
    """예제 eps 를 작업 폴더에 복사해 EPSLoader 로 불러온다(__epspy__ 가 작업 폴더에 생긴다)."""
    d = os.path.join(_common.WORK, "t_i128", "eps")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name + ".eps")
    shutil.copy2(os.path.join(EX, name + ".eps"), p)
    mname = name + "_eps"
    mod = types.ModuleType(mname)
    loader = EPSLoader(mname, p)
    mod.__loader__ = loader
    sys.modules[mname] = mod
    loader.exec_module(mod)
    return mod


def dps_ref(a, b, c):
    """DPS math128 호출 모양 재현의 파이썬 참조 (a, b, c = 64비트 입력)."""
    seam, incm, awak = a, b, c & M32
    x = (seam * incm) // 100  # CallTriggers.lua:397~400
    ff = (((awak + 1000) & M64) * x) & M128  # :404 f_LMul128X({_LAdd(W,"1000"),"0"}, XRet)
    x2 = ff // 1000
    fx, dps, lvl, stat = a & M32, b, c & 0xFFFF, (a >> 32) & 0xFFFF
    mine = (((fx + 1) * dps) & M64) * ((lvl + stat) & M64)  # mine.lua:55
    r_lo = b % 1000
    money = ((a << 64 | c) + r_lo * 6500000000000) & M128  # money.lua:157~158
    tmp = (a * ((c + 1000) & M64)) // 5000  # damage_check.lua:125~126
    up, base = (c & 0xFF) + 10, b
    rm = up * base
    dmg = (rm // 5, rm // 20, rm // 10)  # damage_check.lua:157~164
    tot, used = (a << 64) | b, (b << 64) | c
    boss = max(tot - used, 0)  # GlobalBoss.lua:614 f_LSub128
    credit = (a << 64) | b
    cost = ((c & 0xFFFF) << 64) | (b | 1)
    sell = ref_div(credit, cost)  # sell_refactored.lua:279 (128 ÷ 128)
    tbl = credit // 32  # TBL.lua:879
    mr = a * b  # mine.lua:95 f_LMul128
    return {
        "x": x, "x2": x2, "mine": mine, "money": money, "tmp": tmp, "dmg5": dmg[0], "dmg20": dmg[1], "dmg10": dmg[2],
        "boss": boss, "c1": int(tot >= used), "c2": int(tot == used), "c3": int(tot > used),
        "sq": sell[0], "sr": sell[1], "tbl": tbl, "mrlo": mr & M64, "mrhi": mr >> 64,
    }  # fmt: skip


# 이식판 eud/tests/t_war.py(a7aad90) 의 128비트 기대값
PORT_D128 = [
    (123456789, 1000), (2**64 + 5, 7), ((2**64 - 1) * (2**64 - 1), 2**64 - 1), (2**127 + 12345, 0x123456789ABCDEF),
    (2**100 + 3, 2**70 + 1), (2**64 + 1, 2**64 + 2), (2**128 - 1, 2**128 - 1), (2**128 - 1, 2**64),
    (2**128 - 2, 2**127 + 1), (5000 * 10**25 + 4999, 5000), (2**128 - 1, 3),
]  # fmt: skip
PORT_K128 = [(2**128 - 1, 5000), (2**100 + 12345, 100), (99, 5), (2**64 * 3 + 7, 0xFFFFFFFF), (2**127 + 5, 0x80000001), (0, 7)]
PORT_M128 = [
    (0, 5), (7, 9), (0xFFFFFFFF, 0xFFFFFFFF), (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF), (0x100000000, 0x100000000),
    (0x123456789ABCDEF0, 0x0FEDCBA987654321), (0xFFFFFFFF00000000, 3), (1, 0xFFFFFFFFFFFFFFFF), (10**18, 6500000000000),
]  # fmt: skip


def suite_misc():
    s = Suite("t_i128 루프·배열·생성·출력·DPS")
    checks = []  # (case, inputs, expect, label)
    rng = random.Random(99)

    # --- EUDWhile 조건 재계산 ---
    @s.case("loop")
    def _(t):
        x, y, st = q(t, "x"), q(t, "y"), q(t, "st")
        n = t.var("n")
        n << 0
        if EUDWhile()(x >= y):
            n += 1
            EUDBreakIf(n.AtLeast(12))
            x.isub_sat(st)
        EUDEndWhile()
        m, w = t.var("m"), q(t, "w")
        m << 0
        w << y
        if EUDWhile()(i128.lt(w, x)):
            m += 1
            EUDBreakIf(m.AtLeast(12))
            w += st
        EUDEndWhile()
        k = t.var("k")
        k << 0
        if EUDWhile()(x != 0):
            k += 1
            EUDBreakIf(k.AtLeast(5))
            x //= 1000
        EUDEndWhile()

    def loop_ref(x, y, st):
        n = 0
        while x >= y:
            n += 1
            if n >= 12:
                break
            x = max(x - st, 0)
        m, w = 0, y
        while w < x:
            m += 1
            if m >= 12:
                break
            w = (w + st) & M128
        k = 0
        while x != 0:
            k += 1
            if k >= 5:
                break
            x //= 1000
        return {"n": n, "m": m, "w": w, "k": k, "x": x}

    for x, y, st in [(10**30, 10**29, 10**29), (5, 5, 1), (M128, 1 << 127, 1 << 125), (0, 0, 0), (10**20, 0, 10**19)] + [
        (rng.getrandbits(128), rng.getrandbits(126), rng.getrandbits(124)) for _ in range(15)
    ]:
        d = put(put(put({}, "x", x), "y", y), "st", st)
        checks.append(("loop", d, loop_ref(x, y, st), "loop x=0x%X" % x))

    # --- 상수 조건 문맥 ---
    @s.case("kctx")
    def _(t):
        a = q(t, "a")
        contexts(t, "k1", lambda: a >= 10**30)
        contexts(t, "k2", lambda: a == (1 << 64))
        contexts(t, "k3", lambda: a != M128)
        contexts(t, "k4", lambda: i128.lt(a, 5))
        contexts(t, "k5", lambda: a > (1 << 96))

    for a in EDGES + (10**30, 10**30 - 1, 5, 4, (1 << 96) + 1):
        e = {}
        for tag, f in (("k1", a >= 10**30), ("k2", a == 1 << 64), ("k3", a != M128), ("k4", a < 5), ("k5", a > 1 << 96)):
            e.update(ctx_expect(tag, int(f)))
        checks.append(("kctx", put({}, "a", a), e, "kctx a=0x%X" % a))

    # --- Int128Array ---
    arr = Int128Array(8)
    arr_init = Int128Array([1, 10**30, "340282366920938463463374607431768211455", S127])

    @s.case("arr_var")
    def _(t):
        a, b, i = q(t, "a"), q(t, "b"), t.var("i")
        arr[i] = a
        arr[i] += b
        q(t, "r1") << arr[i]
        arr[i] -= 5
        arr.isub_sat(i, b)
        q(t, "r2") << arr[i]
        arr[i] *= b
        q(t, "r3") << arr[i]
        arr[i] = a
        arr.idiv(i, 7)
        q(t, "r4") << arr.get(i)
        arr.imod(i, b)
        q(t, "r5") << arr[i]
        arr.isubitem(i, a)
        q(t, "r6") << arr[i]
        arr.set(i, b)
        arr.isubtractitem(i, a)
        q(t, "r7") << arr[i]
        for op in CMP_OPS:
            t.flag("v" + op, getattr(arr, op + "item")(i, a))
            t.flag("w" + op, getattr(arr[i], "__%s__" % op)(a))
        arr.iadditem(i, 1 << 64)
        arr.imulitem(i, 3)
        arr.ifloordivitem(i, b)
        arr.imoditem(i, 10**20)
        q(t, "r8") << arr[i]
        q(t, "i0") << arr_init[0]
        q(t, "i1") << arr_init[t.var("one")]
        q(t, "i2") << arr_init[2]
        q(t, "i3") << arr_init.get(3)

    def arr_var_ref(a, b):
        x = (a + b) & M128
        r1 = x
        x = max(((x - 5) & M128) - b, 0)
        r2 = x
        x = (x * b) & M128
        r3 = x
        x = a // 7
        r4 = x
        x = ref_div(x, b)[1]
        r5 = x
        x = (x - a) & M128
        r6 = x
        x = max(b - a, 0)
        r7 = x
        e = {"r1": r1, "r2": r2, "r3": r3, "r4": r4, "r5": r5, "r6": r6, "r7": r7}
        for op, f in PYCMP.items():
            e["v" + op] = int(f(x, a))
            e["w" + op] = int(f(x, a))
        x = (x + (1 << 64)) & M128
        x = (x * 3) & M128
        x = ref_div(x, b)[0]
        x %= 10**20
        e.update({"r8": x, "i0": 1, "i1": 10**30, "i2": M128, "i3": S127})
        return e

    for n_ in range(60):
        a, b = PAIRS[n_ * 37 % len(PAIRS)]
        i = rng.randrange(8)
        checks.append(("arr_var", put(put({"i": i, "one": 1}, "a", a), "b", b), arr_var_ref(a, b), "arr i=%d a=0x%X b=0x%X" % (i, a, b)))

    for kk, K in enumerate(ARR_K):

        @s.case("arr_const%d" % kk)
        def _(t, K=K):
            a, b = q(t, "a"), q(t, "b")
            arr[5] = a
            arr.iadd(5, K)
            q(t, "r1") << arr[5]
            arr.isub(5, (K + 7) & M128)
            q(t, "r2") << arr[5]
            arr.isub_sat(5, K)
            q(t, "r3") << arr[5]
            for op in CMP_OPS:
                t.flag(op, getattr(arr, op + "item")(5, K))
                t.flag("v" + op, getattr(arr, op + "item")(5, b))
            arr[2] = K
            arr[2] += b
            arr.isub_sat(2, a)
            q(t, "r4") << arr[2]

        def arr_const_ref(a, b, K=K):
            x = (a + K) & M128
            r1 = x
            x = (x - K - 7) & M128
            r2 = x
            x = max(x - K, 0)
            e = {"r1": r1, "r2": r2, "r3": x, "r4": max(((K + b) & M128) - a, 0)}
            for op, f in PYCMP.items():
                e[op] = int(f(x, K))
                e["v" + op] = int(f(x, b))
            return e

        for a in EDGES[::2] + (K, (K + 1) & M128, (K - 1) & M128, rng.getrandbits(128)):
            b = rng.choice((a, K, rng.getrandbits(128), 0, M128))
            checks.append(("arr_const%d" % kk, put(put({}, "a", a), "b", b), arr_const_ref(a, b), "K=0x%X a=0x%X" % (K, a)))

    # --- 생성·대입 (3.2-3) ---
    lv = EUDLightVariable()
    fw = Forward()
    fw << 0x1234

    @s.case("ctor")
    def _(t):
        c, h = t.var("c"), t.var("h")
        a = q(t, "a")
        q(t, "up") << Int128(c)
        q(t, "pair") << Int128(c, h)
        q(t, "pair_k1") << Int128(c, 5)
        q(t, "pair_k2") << Int128(-1, h)
        q(t, "pair_k3") << Int128("12800000000", a.lo)
        q(t, "pair64") << Int128(Int64(c, h), Int64(h, c))
        q(t, "copy") << Int128(a)
        q(t, "from64") << Int128(a.hi)
        SeqCompute([(EPD(lv.getValueAddr()), SetTo, c)])
        q(t, "light") << Int128(lv)
        q(t, "light2") << a + lv
        q(t, "fw") << Int128(fw)
        q(t, "str") << Int128("340,282,366,920,938,463,463,374,607,431,768,211,455")
        q(t, "neg1") << Int128(-1)
        q(t, "big") << Int128(1 << 100)
        # 초기값만(3.2-3): 첫 실행 7, 두 번째 8
        k = Int128(7)
        q(t, "init") << k
        k += 1
        # 실행 시 대입: 매번 위 칸 ← 0 을 다시 한다
        y = Int128(c)
        q(t, "rt") << y
        y += 1 << 100

    def ctor_ref(c, h, a, run):
        return {
            "up": c, "pair": c | (h << 64), "pair_k1": c | (5 << 64), "pair_k2": M64 | (h << 64),
            "pair_k3": 12800000000 | ((a & M64) << 64), "pair64": c | (h << 32) | (h << 64) | (c << 96), "copy": a,
            "from64": a >> 64, "light": c, "light2": (a + c) & M128, "fw": 0x1234, "str": M128, "neg1": M128,
            "big": 1 << 100, "init": 7 + run, "rt": c,
        }  # fmt: skip

    # --- DPS math128 호출 모양 ---
    @s.case("dps")
    def _(t):
        a, b, c = q64(t, "a"), q64(t, "b"), q64(t, "c")
        # CallTriggers.lua:397~406
        x = q(t, "x")
        ffret = i128.LMul128_2(a, b)
        dret, _r = i128.LDiv128(ffret, 100)
        i128.LMov128(x, dret)
        ff = i128.mul(Int128(i64.add(c.lo, 1000)), x)
        d2, _r2 = i128.LDiv128(ff, "1000")
        i128.LMov128(q(t, "x2"), d2)
        # mine.lua:55
        f64 = i64.mul(i64.add(Int64(a.lo), 1), b)
        cc = EUDVariable()
        cc << c.lo
        cc &= 0xFFFF
        st = EUDVariable()
        st << a.hi
        st &= 0xFFFF
        q(t, "mine") << i128.mul64(f64, i64.add(cc, st))
        # money.lua:157~158
        _q, r = i128.divmod(b, 1000)
        retmul = i128.LMul128_2(r.lo, "6500000000000")
        q(t, "money") << i128.LAdd128(i128.wrap(c, a), retmul)
        # damage_check.lua:125~126
        rm = i128.LMul128_2(a, i64.add(c, "1000"))
        rd, _r3 = i128.LDiv128(rm, 5000)
        q(t, "tmp") << rd
        # damage_check.lua:157~164
        up = EUDVariable()
        up << c.lo
        up &= 0xFF
        up += 10
        rm2 = i128.LMul128_2(Int64(up), b)
        q(t, "dmg5") << i128.LDiv128(rm2, 5)[0]
        q(t, "dmg20") << rm2 // 20
        q(t, "dmg10") << i128.div(rm2, "10")
        # GlobalBoss.lua:614, 700 / token.lua:150~151
        tot = i128.wrap(b, a)
        used = i128.wrap(c, b)
        q(t, "boss") << i128.LSub128(tot, used)
        t.flag("c1", i128.Compare_128(tot, AtLeast, used))
        t.flag("c2", i128.LCmp128(tot, Exactly, used))
        t.flag("c3", i128.LCmp128(tot, ">", used))
        # sell_refactored.lua:279 (128 ÷ 128) / TBL.lua:879
        credit = i128.wrap(b, a)
        chi = EUDVariable()
        chi << c.lo
        chi &= 0xFFFF
        clo = Int64(b)
        clo.v |= 1
        cost = Int128(clo, Int64(chi))
        sq, sr = i128.LDiv128(credit, cost)
        q(t, "sq") << sq
        q(t, "sr") << sr
        q(t, "tbl") << i128.LDiv128(credit, 32)[0]
        # mine.lua:95 (Mullo, Mulhi = f_LMul128(A, B))
        mr = i128.LMul128(a, b)
        q64(t, "mrlo") << mr.lo
        q64(t, "mrhi") << mr.hi

    dps_vals = [(M64, M64, M64), (0, 0, 0), (10**18, 12345, 777), (S63, 2, M32)] + [
        (rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64)) for _ in range(40)
    ]
    for a, b, c in dps_vals:
        d = put64(put64(put64({}, "a", a), "b", b), "c", c)
        checks.append(("dps", d, dps_ref(a, b, c), "dps a=0x%X b=0x%X c=0x%X" % (a, b, c)))

    # --- 이식판 t_war.py 128비트 기대값 ---
    @s.case("port")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        qq, rr = i128.divmod(a, b)
        q(t, "q") << qq
        q(t, "r") << rr
        q(t, "m") << i128.mul64(a.lo, b.lo)

    for a, b in PORT_D128:
        qq, rr = divmod(a, b)
        checks.append(("port", put(put({}, "a", a), "b", b), {"q": qq, "r": rr, "m": (a & M64) * (b & M64)}, "port D128 %d/%d" % (a, b)))
    for a, b in PORT_M128:
        checks.append(("port", put(put({}, "a", a), "b", b), {"m": a * b, "q": a // b if b else M128}, "port M128 %d*%d" % (a, b)))
    for kk, (x, c) in enumerate(PORT_K128):

        @s.case("portk%d" % kk)
        def _(t, c=c):
            a = q(t, "a")
            qq, rr = i128.LDiv128(a, "%d" % c)
            q(t, "q") << qq
            q(t, "r") << rr

        qq, rr = divmod(x, c)
        checks.append(("portk%d" % kk, put({}, "a", x), {"q": qq, "r": rr}, "port K128 %d/%d" % (x, c)))

    @s.case("portz")
    def _(t):
        a = q(t, "a")
        z = Int128(0)
        qq, rr = i128.LDiv128(a, z)
        q(t, "q") << qq
        q(t, "r") << rr
        qq, rr = i128.divmod(a, 0)
        q(t, "q2") << qq
        q(t, "r2") << rr

    zx = (0x1111111122222222 << 64) | 0x3333333344444444
    checks.append(("portz", put({}, "a", zx), {"q": M128, "r": zx, "q2": M128, "r2": zx}, "port 0 제수 (eudext 규칙)"))

    # --- 10진 출력 ---
    buf = Db(256)
    buf2 = Db(96)
    buf3 = Db(44)
    buf4 = Db(44)
    epd4 = EUDVariable(EPD(buf4))

    @s.case("fmt")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        t.watch("buf", buf)
        t.watch("buf2", buf2)
        t.watch("buf3", buf3)
        t.watch("buf4", buf4)
        f_dbstr_print(buf, "[", a.fmt(), "|", a, "|", i128.fmt(t.var("c")), "|", i128.fmt(b.lo), "|", i128.fmt(M128), "|",
                      i128.fmt(-5), "]")  # fmt: skip
        f_sprintf(buf2, "{} {}", a.fmt(), i128.fmt(b))
        t.out("lead3", i128.lidec_to(EPD(buf3), a))
        t.out("lead4", i128.lidec_to(epd4, b))

    s.build()
    m = s.machine
    for name, d, e, label in checks:
        judge(s, name, d, e, label)
    for run, (c, h, a) in enumerate(((5, 7, 0x123456789ABCDEF0FEDCBA9876543210), (M32, 0, M128), (0, M32, 0))):
        d = put({"c": c, "h": h}, "a", a)
        judge(s, "ctor", d, ctor_ref(c, h, a, run), "ctor run%d c=0x%X" % (run, c))
    fvals = list(FMT_VALS) + [rng.getrandbits(rng.choice((32, 64, 65, 96, 100, 128))) for _ in range(120 if FULL else 60)]
    for v in fvals:
        w = rng.getrandbits(rng.choice((64, 128))) if rng.random() < 0.7 else rng.choice(fvals)
        c = rng.getrandbits(32)
        r = s.run("fmt", put(put({"c": c}, "a", v), "b", w))
        if r.error:
            s.expect_true("fmt", False, "fmt 0x%X" % v, r.error)
            continue
        got = m.read_bytes(m.addr("fmt.buf"), 256).split(b"\0")[0]
        want = ("[%d|%d|%d|%d|%d|%d]" % (v, v, c, w & M64, M128, M128 - 4)).encode()
        s.expect_true("fmt", got == want, "fmt 0x%X" % v, "%r != %r" % (got, want))
        got = m.read_bytes(m.addr("fmt.buf2"), 96).split(b"\0")[0]
        want = ("%d %d" % (v, w)).encode()
        s.expect_true("fmt", got == want, "fmt2 0x%X" % v, "%r != %r" % (got, want))
        for key, val in (("buf3", v), ("buf4", w)):
            raw = m.read_bytes(m.addr("fmt." + key), 44)
            digits = ("%040d" % val).encode()
            lead = min(40 - len(str(val)), 39)
            ok = raw[:40] == digits and r.values["lead" + key[-1]] == lead and raw[40:] == b"\0" * 4
            s.expect_true("fmt", ok, "lidec_to %s 0x%X" % (key, val), "%r lead=%d (기대 %r %d)" % (raw, r.values["lead" + key[-1]], digits, lead))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 4: epScript 예제
# ---------------------------------------------------------------------------------------------


def suite_eps(eps):
    s = Suite("t_i128 epScript 예제")
    for fn in ("wsum", "wdiff", "sat", "lsub", "prod"):

        @s.case("eps_" + fn)
        def _(t, fn=fn):
            a, b = q(t, "a"), q(t, "b")
            r = getattr(eps, "f_" + fn)(*a.words, *b.words)
            q(t, "r") << Int128.wrap(*r)

    for fn in ("qr", "vdivmod"):

        @s.case("eps_" + fn)
        def _(t, fn=fn):
            a, b = q(t, "a"), q(t, "b")
            r = getattr(eps, "f_" + fn)(*a.words, *b.words)
            q(t, "q") << Int128.wrap(*r[:4])
            q(t, "r") << Int128.wrap(*r[4:])

    for fn in ("less", "atleast"):

        @s.case("eps_" + fn)
        def _(t, fn=fn):
            a, b = q(t, "a"), q(t, "b")
            t.out("r", getattr(eps, "f_" + fn)(*a.words, *b.words))

    @s.case("eps_prod64")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        r = eps.f_prod64(a.w0, a.w1, b.w0, b.w1)
        q(t, "r") << Int128.wrap(*r)
        r = eps.f_percent(a.w0, a.w1, b.w0, b.w1)
        q(t, "pq") << Int128.wrap(*r[:4])
        t.out("pr", r[4])

    @s.case("eps_arr")
    def _(t):
        r = eps.f_arr_ops(t.var("p"), t.var("c"))
        q(t, "r") << Int128.wrap(*r)

    @s.case("eps_lower")
    def _(t):
        a = q(t, "a")
        q(t, "b")  # 입력 칸만 (쓰지 않음)
        r = eps.f_lower(*a.words)
        q64(t, "s") << Int64.wrap(r[0], r[1])
        q64(t, "w") << Int64.wrap(r[2], r[3])
        t.out("t", r[4])
        t.out("u", r[5])

    @s.case("eps_count")
    def _(t):
        a = q(t, "a")
        q(t, "b")  # 입력 칸만 (쓰지 않음)
        t.out("r", eps.f_count_down(*a.words))

    pbuf = Db(64)

    @s.case("eps_print")
    def _(t):
        a = q(t, "a")
        q(t, "b")  # 입력 칸만 (쓰지 않음)
        t.watch("buf", pbuf)
        eps.f_print_to(pbuf, *a.words)

    @s.case("eps_main")
    def _(t):
        eps.afterTriggerExec()
        q(t, "total") << eps.total
        t.out("hits", eps.hits)

    s.build()
    m = s.machine
    refs = {
        "wsum": lambda a, b: (a + b) & M128,
        "wdiff": lambda a, b: (a - b) & M128,
        "sat": lambda a, b: max(a - b, 0),
        "lsub": lambda a, b: max(a - b, 0),
        "prod": lambda a, b: (a * b) & M128,
    }
    for n_, (a, b) in enumerate(PAIRS[:: 4 if not FULL else 1]):
        d = put(put({}, "a", a), "b", b)
        for fn, f in refs.items():
            judge(s, "eps_" + fn, d, {"r": f(a, b)}, "%s 0x%X 0x%X" % (fn, a, b))
        qq, rr = ref_div(a, b)
        judge(s, "eps_qr", d, {"q": qq, "r": rr}, "qr 0x%X 0x%X" % (a, b))
        judge(s, "eps_vdivmod", d, {"q": qq, "r": rr}, "vdivmod 0x%X 0x%X" % (a, b))
        judge(s, "eps_less", d, {"r": int(a < b)}, "less")
        judge(s, "eps_atleast", d, {"r": int(a >= b)}, "atleast")
        p = (a & M64) * (b & M64)
        judge(s, "eps_prod64", d, {"r": p, "pq": p // 100, "pr": p % 100}, "prod64")
        judge(s, "eps_lower", d, {"s": min(a, M64), "w": a & M64, "t": min(a, M32), "u": a & M32}, "lower")
        n = 0
        x = a
        while x >= 10**20:
            x = max(x - 333333333333333333333333, 0)
            n += 1
            if n >= 20:
                break
        judge(s, "eps_count", d, {"r": n}, "count 0x%X" % a)
        if n_ % 7 == 0:
            r = s.run("eps_print", d)
            got = m.read_bytes(m.addr("eps_print.buf"), 64).split(b"\0")[0]
            s.expect_true("eps_print", not r.error and got == ("[%d]" % a).encode(), "print 0x%X" % a, "%r %r" % (got, r.error))
    for p_, c in ((0, 5), (3, M32), (7, 0), (1, 12345)):
        x = (c + c * (1 << 32) - 1) & M128
        x = max(x - 5, 0)
        x = ((x * 3) & M128) // 2 % 10**21
        judge(s, "eps_arr", {"p": p_, "c": c}, {"r": x}, "arr p=%d c=%d" % (p_, c))
    total = 0
    for k in range(3):
        total += 123456789 * 1000000007
        judge(s, "eps_main", {}, {"total": total, "hits": k + 1}, "main %d" % k)
    return s.report()


# ---------------------------------------------------------------------------------------------
# 인게임 확인 맵 (에뮬레이터) · euddraft 빌드 · epScript 번역 · 빌드 오류 · 파이썬 쪽 판정
# ---------------------------------------------------------------------------------------------


def ingame_emulate(ck):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_i128_ingame")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, "i128_ingame.eps"), os.path.join(work, "i128_ingame.eps"))
    _compat.reset_build_state()
    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(work, "i128_ingame.eps"), {})
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
    print("  인게임 맵 에뮬레이션: %r, 첫 사이클 실행 %d, 그 뒤 최대 %d" % (got, steps[0] if steps else -1, max(steps[1:] or [-1])))
    ck.eq("ingame emu 오류", err, None)
    ck.eq("ingame emu 값", got, {"frame": 130, "okCount": INGAME_TOTAL, "total": INGAME_TOTAL, "ti": INGAME_TOTAL})


def euddraft_builds(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("i128_example", "i128_ingame"):
        work = os.path.join(_common.WORK, "t_i128_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("euddraft freeze off " + name, not r.freeze)
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, r.log[-1000:])
        ck.true("boot preload " + name, "i128" in r.log, "")


def eps_checks(ck):
    for name in ("i128_example", "i128_ingame"):
        with open(os.path.join(EX, name + ".eps"), encoding="utf-8") as f:
            src = f.read()
        out, nerr = _compat.eps_compile(name + ".eps", src)
        ck.eq("eps 오류 수 " + name, nerr, 0)
        ck.true("eps 번역 " + name, out is not None)
        if name != "i128_example" or not out:
            continue
        for needle in (
            "from eudext import i128 as i128",
            "total = _CGFW(lambda: [i128.Int128(0)], 1)[0]",
            "_ATTW(total, 'v').__iadd__(",
            "i128.f_mul64(",
            "EUDIf()(total >= cap)",
            "f_printAll('total {}', total.fmt())",
            "_ATTW(a, 'v').__isub__(i128.f_wrap(",
            "a.isub_sat(i128.f_wrap(",
            "i128.LSub128(",
            "_ATTW(a, 'v').__imul__(",
            "_ATTW(q, 'v').__ifloordiv__(",
            "_ATTW(r, 'v').__imod__(",
            "i128.f_divmod(",
            "i128.LCmp128(",
            "_ARRW(dps, p) << (v)",
            "_ARRW(dps, p).__iadd__(",
            "_ARRW(dps, p).__isub__(1)",
            "dps.isub_sat(p, 5)",
            "_ARRW(dps, p).__imul__(3)",
            "_ARRW(dps, p).__ifloordiv__(2)",
            "_ARRW(dps, p).__imod__(",
            "a.to64(saturate=False)",
            "i128.f_to32(a, saturate=False)",
            "EUDWhile()(x >= 100000000000000000000)",
        ):
            ck.true("eps 번역에 %s" % needle, needle.replace("'", '"') in out or needle in out, needle)


def bad_builds(ck):
    """문서 안내 확인: 빌드 오류여야 하는 epScript·파이썬 모양 (모든 에뮬레이터 시험 뒤에 부른다)."""
    src = (
        "import eudext.i128 as i128;\n"
        "const x = i128.Int128(5);\n"
        "function bshift() { const q = x << 3; }\n"
        "function bvar() { var y = i128.Int128(5); y += 1; }\n"
        "function bret() { return x >= 1; }\n"
        "function belem() { const g = i128.Int128Array(2); const e = g[0]; e.v += 1; }\n"
        "var v;\n"
        "function bvmul() { const r = v * x; }\n"
        "function bvdiv() { const r = v / x; }\n"
        "function bvmod() { const r = v % x; }\n"
        "function bbits() { const r = x & 5; }\n"
        "function bshr() { x.v >>= 1; }\n"
    )
    out, nerr = _compat.eps_compile("bad_i128.eps", src)
    ck.true("bad eps 번역", out is not None and nerr == 0, str(nerr))
    ns = {}
    exec(compile(out, "bad_i128.eps.py", "exec"), ns)  # noqa: S102 — 시험용 번역문
    want = {
        "f_bshift": "대입",
        "f_bvar": "",
        "f_bret": "",
        "f_belem": "사본",
        "f_bvmul": "왼쪽",
        "f_bvdiv": "왼쪽",
        "f_bvmod": "왼쪽",
        "f_bbits": "비트",
        "f_bshr": "시프트",
    }

    @EUDTypedFunc([Int128])
    def typed(a):
        pass

    ns["f_typed"] = lambda: typed(EUDVariable())
    want["f_typed"] = "네 인자"
    for fn, needle in want.items():
        _compat.reset_build_state()
        LoadMap(BASE_MAP)
        CompressPayload(True)
        try:
            emu.Program(lambda fn=fn: ns[fn]()).build()
            ck.true("%s 빌드 오류" % fn, False, "빌드가 됐다")
        except Exception as e:  # noqa: BLE001
            ck.true("%s 빌드 오류" % fn, needle in str(e), repr(e))


def python_checks(ck):
    with _compat.isolated_scope():  # 트리거를 내는 호출이 있으므로 버려지는 트리거 범위 안에서
        _python_checks(ck)


def _python_checks(ck):
    x, y = Int128(0), Int128(0)
    v = EUDVariable()
    # 상수 접기
    ck.eq("add const", i128.add(1, 2), 3)
    ck.eq("add wrap", i128.add(M128, 2), 1)
    ck.eq("sub const", i128.sub(0, 1), M128)
    ck.eq("sub_sat const", i128.sub_sat(1, 2), 0)
    ck.eq("sub_sat str", i128.sub_sat("100000000000000000000", 1 << 64), 10**20 - (1 << 64))
    ck.eq("neg const", i128.neg(1), M128)
    ck.eq("mul const", i128.mul(M64, M64), M64 * M64)
    ck.eq("mul wrap", i128.mul(M128, M128), 1)
    ck.eq("mul64 const", i128.mul64(M64, M64), M64 * M64)
    ck.eq("div const", i128.div(M128, 10), M128 // 10)
    ck.eq("div0 const", i128.div(5, 0), M128)
    ck.eq("mod0 const", i128.mod(5, 0), 5)
    ck.eq("divmod const", i128.divmod(10**30, 7), divmod(10**30, 7))
    ck.eq("fmt const", i128.fmt(M128), str(M128))
    ck.eq("fmt const int64", i128.fmt(-1), str(M128))
    ck.eq("to64 const", i128.to64(1 << 64), M64)
    ck.eq("to64 const w", i128.to64((1 << 64) + 5, saturate=False), 5)
    ck.eq("to32 const", i128.to32(1 << 40), M32)
    for op in CMP_OPS:
        for a, b in ((5, 3), (3, 5), (M128, 0), (0, M128), (7, 7), (1 << 100, (1 << 100) + 1)):
            c = getattr(i128, op)(a, b)
            ck.true("fold %s(%d, %d)" % (op, a, b), isinstance(c, Condition) and c.fields[5] == (22 if PYCMP[op](a, b) else 23))
        c = getattr(i128, op)(x, x)
        ck.true("same %s" % op, isinstance(c, Condition) and c.fields[5] == (22 if PYCMP[op](1, 1) else 23))
        ck.true("alias %s" % op, getattr(i128, op) is getattr(i128, "f_" + op))
        ck.true("fresh %s" % op, getattr(i128, op)(x, 5) is not getattr(i128, op)(x, 5))
    ck.true("alias sub_sat", i128.sub_sat is i128.f_sub_sat and i128.isub_sat is i128.f_isub_sat)
    ck.true("alias DPS", i128.LSub128 is i128.f_LSub128 and i128.LMul128_2 is i128.f_LMul128 and i128.Compare_128 is i128.f_LCmp128)
    ck.true("alias parse/fmt/lidec", i128.parse is i128.f_parse and i128.fmt is i128.f_fmt and i128.lidec_to is i128.f_lidec_to)
    ck.eq("__all__ 중복", sorted(i128.__all__), sorted(set(i128.__all__)))
    for name in i128.__all__:
        ck.true("__all__ %s" % name, hasattr(i128, name))
        obj = getattr(i128, name)
        if callable(obj) and not isinstance(obj, type):
            ck.true("docstring %s" % name, bool(getattr(obj, "__doc__", None)), name)
    ck.true("divmod·abs 는 __all__ 밖", "divmod" not in i128.__all__ and hasattr(i128, "divmod"))
    # 뺄셈 두 의미의 이름 (3.5): SubtractNumber/AddNumber 는 없다
    ck.true("Int128.SubtractNumber 없음", not hasattr(Int128, "SubtractNumber") and not hasattr(Int128, "AddNumber"))
    ck.true("isubtractitem = 포화", Int128Array.isubtractitem is Int128Array.isub_sat and Int128Array.isubitem is Int128Array.isub)
    # parse
    ck.eq("parse 쉼표", i128.parse("340,282,366,920,938,463,463,374,607,431,768,211,455"), M128)
    ck.eq("parse 밑줄", i128.parse("1_000_000_000_000_000_000_000"), 10**21)
    ck.eq("parse -1", i128.parse("-1"), M128)
    ck.eq("parse 0x", i128.parse("0x80000000000000000000000000000000"), S127)
    ck.eq("parse min", i128.parse("-170141183460469231731687303715884105728"), S127)
    for bad in ("abc", "1.5", "340282366920938463463374607431768211456", "-170141183460469231731687303715884105729", "", None, 1.5):
        ck.raises("parse %r" % (bad,), EudextError, i128.parse, bad)
    # 생성 오류
    ck.raises("Int128(2^128)", EudextError, Int128, 1 << 128)
    ck.raises("Int128(-2^127-1)", EudextError, Int128, -(1 << 127) - 1)
    ck.raises("Int128(lo 넘침, hi)", EudextError, Int128, 1 << 64, 1)
    ck.raises("Int128(lo, hi 넘침)", EudextError, Int128, 1, 1 << 64)
    ck.raises("Int128(Int128, 1)", EudextError, Int128, x, 1)
    ck.raises("Int128(1, Int128)", EudextError, Int128, 1, x)
    ck.raises("Int128(1.5)", EudextError, Int128, 1.5)
    ck.raises("Int128(None)", EudextError, Int128, None)
    ck.raises("Int128(LightBool)", EudextError, Int128, EUDLightBool())
    ck.raises("wrap 정수", EudextError, Int128.wrap, 1, 2)
    ck.raises("wrap 셋", EudextError, Int128.wrap, v, v, v)
    ck.raises("wrap Light", EudextError, Int128.wrap, EUDLightVariable(), v, v, v)
    ck.raises("wrap Int64+var", EudextError, Int128.wrap, Int64(0), v)
    ck.raises("Array 0", EudextError, Int128Array, 0)
    ck.raises("Array str", EudextError, Int128Array, "8")
    ck.raises("Array 범위", EudextError, Int128Array(3).get, 3)
    ck.raises("Array 번호 str", EudextError, Int128Array(3).get, "0")
    ck.raises("Array 빈 목록", EudextError, Int128Array, [])
    ck.raises("mul64 Int128", EudextError, i128.mul64, x, 1)
    ck.raises("mul64 큰 상수", EudextError, i128.mul64, 1 << 64, v)
    # 실수 막기 (3.2-2)
    ck.raises("bool", EudextError, bool, x)
    ck.raises("format", EudextError, format, x, "")
    ck.raises("sprintf {}", EudextError, f_sprintf, Db(8), "{}", x)
    ck.raises("iter", EudextError, list, x)
    ck.raises("len", EudextError, len, x)
    ck.raises("cast", EudextError, Int128.cast, v)
    ck.true("repr 안내", "const" in repr(x))
    ck.true("hash", hash(x) == id(x))
    ck.true("== None", (x == None) is False and (x != None) is True)  # noqa: E711
    ck.raises(">= None", EudextError, lambda: x >= None)
    ck.raises("+ 1.5", EudextError, lambda: x + 1.5)
    ck.raises("+ Condition", EudextError, lambda: x + v.Exactly(1))
    ck.raises("- LightBool", EudextError, lambda: x - EUDLightBool())
    for label, fn in (
        ("pow", lambda: x**2),
        ("truediv", lambda: x / 2),
        ("rlshift", lambda: 1 << x),
        ("and", lambda: x & 1),
        ("or", lambda: x | 1),
        ("xor", lambda: x ^ 1),
        ("invert", lambda: ~x),
        ("rshift", lambda: x >> 1),
    ):
        ck.raises("안 됨 " + label, EudextError, fn)
    # Int64 가 왼쪽인 산술·비교는 i64 연산자가 먼저 불려 오류 (i128 모듈 함수를 쓴다 — 모듈 설명)
    ck.raises("Int64 + Int128", EudextError, lambda: Int64(0) + x)
    ck.raises("Int64 >= Int128", EudextError, lambda: Int64(0) >= x)
    ck.true("i128.add(Int64, Int128)", isinstance(i128.add(Int64(0), x), Int128))
    ck.true("새 값", isinstance(x * y, Int128) and isinstance(i128.divmod(x, 3), tuple) and isinstance(x % 3, Int128))
    ck.true("lo/hi = Int64", isinstance(x.lo, Int64) and x.lo.lo is x.w0 and x.hi.hi is x.w3 and x.words == (x.w0, x.w1, x.w2, x.w3))
    ck.true("to64 = Int64", isinstance(x.to64(), Int64) and isinstance(x.to32(), EUDVariable))
    # 배열 원소 사본에 쓰기 → 오류
    arr = Int128Array(4)
    e = arr[1]
    for label, fn in (
        ("+=", lambda: e.iadd(1)),
        ("-=", lambda: e.isub(1)),
        ("isub_sat", lambda: e.isub_sat(1)),
        ("<<", lambda: e.assign(1)),
        (".v =", lambda: setattr(e, "v", 1)),
        (".v +=", lambda: e.iaddattr("v", 1)),
        ("ineg", lambda: e.ineg()),
        ("imul", lambda: e.imul(2)),
        ("idiv", lambda: e.idiv(2)),
        ("imod", lambda: e.imod(2)),
        ("lo 사본", lambda: e.lo.iadd(1)),
    ):
        ck.raises("사본 " + label, EudextError, fn)
    ck.true("사본 → Int128 복사는 됨", isinstance(Int128(e), Int128) and isinstance(e + 1, Int128))
    e2 = arr[2]
    e2 += 1  # 파이썬 연산자는 되쓰기 전제라 막지 않는다
    e2 -= 1
    arr[2] = e2
    ck.raises("iaddattr 다른 이름", AttributeError, x.iaddattr, "w", 1)
    ck.raises("제자리 대상", EudextError, i128.isub_sat, v, 1)
    ck.raises("LMov128 대상", EudextError, i128.LMov128, 5, x)
    ck.raises("LCmp128 종류", EudextError, i128.LCmp128, x, "=>", y)
    ck.raises("lidec lead", EudextError, i128.lidec_to, 0, x, lead=5)
    ck.raises("to64 saturate", EudextError, i128.to64, x, saturate=1)
    ck.raises("add inline", EudextError, i128.add, x, y, inline=1)
    ck.raises("iadd inline", EudextError, x.iadd, y, inline="yes")
    # 반환 모양·제자리 부정 (3.4): 채운 조건은 amount 가 정수가 아니다
    c = x >= y
    ck.true("ge 변수 = 목록", isinstance(c, list) and all(isinstance(k, Condition) for k in c))
    filled = [k for k in c if not isinstance(k.fields[2], int)]
    ck.true("ge 변수 채운 조건 있음", len(filled) >= 1)
    ck.true("eq 상수 = 조건 목록(트리거 0)", isinstance(x == 5, list))
    ck.true("반환 self", all(r is x for r in (x.iadd(1), x.isub(1), x.isub_sat(1), x.assign(1), x.imul(3), x.idiv(3), x.imod(3))))
    ck.true("v 통로", x.v is x)
    # 비공개 API 는 _compat 에서만 (3.9)
    with open(i128.__file__, encoding="utf-8") as f:
        text = f.read()
    ck.true("_compat 밖 비공개 API 없음", "from eudplib." not in text and "import eudplib." not in text)
    ck.true("P1 마린 칸 안 씀", "0x58A364" not in text)
    ck.true("마스크 Add/Subtract 안 씀", "AddNumberX" not in text and "SubtractNumberX" not in text)


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py)
# ---------------------------------------------------------------------------------------------


def _p(d, name, v):
    return put(d, name, v)


AB = [
    _p(_p({}, "a", 5), "b", 3),
    _p(_p({}, "a", M128), "b", M128),
    _p(_p({}, "a", 1 << 96), "b", (1 << 64) + 5),
    _p(_p({}, "a", 0x123456789ABCDEF0FEDCBA9876543210), "b", 0xFEDCBA98765432100123456789ABCDEF),
]
A1 = [_p({}, "a", 5), _p({}, "a", 1 << 64), _p({}, "a", M128), _p({}, "a", 0x123456789ABCDEF0FEDCBA9876543210)]
AB64 = [_p(_p({}, "a", M64), "b", M64), _p(_p({}, "a", 12345), "b", 777), _p(_p({}, "a", 10**18), "b", 6500000000000)]
AB64H = [put64(put64({}, "a", M64), "b", M64), put64(put64({}, "a", 12345), "b", 777)]
AB32 = [_p(_p({}, "a", M32), "b", M32), _p(_p({}, "a", 12345), "b", 777)]
DIV32 = [_p(_p({}, "a", M128), "b", 10), _p(_p({}, "a", M128), "b", 0x80000001), _p(_p({}, "a", 12345), "b", 7)]
DIV64 = [_p(_p({}, "a", M128), "b", M64), _p(_p({}, "a", M128), "b", 0x123456789), _p(_p({}, "a", S127 + 12345), "b", 0x123456789ABCDEF)]
DIV128 = [
    _p(_p({}, "a", (1 << 100) + 3), "b", (1 << 70) + 1),
    _p(_p({}, "a", M128), "b", (1 << 64) + 1),
    _p(_p({}, "a", M128), "b", (1 << 126) + 1),
    _p(_p({}, "a", 5), "b", 1 << 100),
]
FMTV = [_p({}, "a", 5), _p({}, "a", M64), _p({}, "a", 1 << 64), _p({}, "a", 10**30), _p({}, "a", M128)]


def _q(t, n):
    return q(t, n)


def _op(fn):
    def build(t):
        fn(t, _q(t, "a"), _q(t, "b"))

    return build


def _cc(fn):
    def build(t):
        Trigger(conditions=fn(t, _q(t, "a"), _q(t, "b")))

    return build


COST_CASES = [
    CostCase("x += y (변수, 공유 함수 — 기본)", _op(lambda t, a, b: a.iadd(b)), AB, funcs=[i128._addsub_fn("add")]),
    CostCase("x.iadd(y, inline=True) (펼침)", _op(lambda t, a, b: a.iadd(b, inline=True)), AB, note="한 줄 + 올림 깃발 트리거 8"),
    CostCase("x += Int64 (64비트 변수, 공유 함수 — 기본)", _op(lambda t, a, b: a.iadd(b.lo)), AB),
    CostCase("x.iadd(Int64, inline=True)", _op(lambda t, a, b: a.iadd(b.lo, inline=True)), AB),
    CostCase("x += v32 (32비트 변수 — 기본 펼침)", _op(lambda t, a, b: a.iadd(b.w0)), AB),
    CostCase("x += 5 (작은 상수)", _op(lambda t, a, b: a.iadd(5)), A1, note="위 칸부터 올림 조건 묶음"),
    CostCase("x += 10^30 (큰 상수)", _op(lambda t, a, b: a.iadd(10**30)), A1),
    CostCase("x += x (같은 객체)", _op(lambda t, a, b: a.iadd(a)), A1),
    CostCase("r = x + y (새 값, 기본)", _op(lambda t, a, b: a + b), AB),
    CostCase("r = add(x, y, inline=True)", _op(lambda t, a, b: i128.add(a, b, inline=True)), AB),
    CostCase("x -= y (변수 wrap, 공유 함수 — 기본)", _op(lambda t, a, b: a.isub(b)), AB, funcs=[i128._addsub_fn("sub")]),
    CostCase("x.isub(y, inline=True) (펼침)", _op(lambda t, a, b: a.isub(b, inline=True)), AB),
    CostCase("x -= v32 (32비트 변수 — 기본 펼침)", _op(lambda t, a, b: a.isub(b.w0)), AB),
    CostCase("x -= 5 (상수 wrap)", _op(lambda t, a, b: a.isub(5)), A1),
    CostCase("r = x - y (새 값 wrap)", _op(lambda t, a, b: a - b), AB),
    CostCase("x.isub_sat(y) (변수 포화, 공유 함수 — 기본)", _op(lambda t, a, b: a.isub_sat(b)), AB,
             funcs=[i128._addsub_fn("ssub")]),  # fmt: skip
    CostCase("x.isub_sat(y, inline=True)", _op(lambda t, a, b: a.isub_sat(b, inline=True)), AB),
    CostCase("x.isub_sat(5) (상수 포화)", _op(lambda t, a, b: a.isub_sat(5)), A1),
    CostCase("x.isub_sat(10^30) (큰 상수 포화)", _op(lambda t, a, b: a.isub_sat(10**30)), A1),
    CostCase("r = sub_sat(x, y) (새 값, 기본)", _op(lambda t, a, b: i128.sub_sat(a, b)), AB),
    CostCase("LSub128(x, y) (DPS 별칭)", _op(lambda t, a, b: i128.LSub128(a, b)), AB),
    CostCase("x.ineg()", _op(lambda t, a, b: a.ineg()), A1),
    CostCase("x << y (대입)", _op(lambda t, a, b: a << b), AB),
    CostCase("x << 5 (상수 대입)", _op(lambda t, a, b: a << 5), A1),
    CostCase("참고: 소비 트리거만 (Trigger(Always))", lambda t: Trigger(conditions=[])),
    CostCase("x >= y (변수)", _cc(lambda t, a, b: a >= b), AB, note="채우기 7 + 깃발 트리거 3 (+소비 1)"),
    CostCase("x > y (변수)", _cc(lambda t, a, b: a > b), AB),
    CostCase("x == y (변수)", _cc(lambda t, a, b: a == b), AB),
    CostCase("x != y (변수)", _cc(lambda t, a, b: a != b), AB),
    CostCase("x >= Int64", _cc(lambda t, a, b: a >= b.lo), AB),
    CostCase("x >= 10^30 (상수)", _cc(lambda t, a, b: a >= 10**30), A1),
    CostCase("x >= 2^64 (상수, 아래 칸 0)", _cc(lambda t, a, b: a >= 1 << 64), A1),
    CostCase("x == 5 (상수)", _cc(lambda t, a, b: a == 5), A1),
    CostCase("mul64(Int64, Int64) (64×64 → 128)", lambda t: i128.mul64(_q(t, "a").lo, _q(t, "b").lo), AB64,
             funcs=[i128._mulf_fn(True)], target={"exec": 1000}),  # fmt: skip
    CostCase("mul64(Int64, v32) (64×32)", lambda t: i128.mul64(_q(t, "a").lo, _q(t, "b").w0), AB64,
             funcs=[i128._mulf_fn(False)], target={"exec": 1000}),  # fmt: skip
    CostCase("mul64(v32, v32) (32×32, i64 본문)", lambda t: i128.mul64(_q(t, "a").w0, _q(t, "b").w0), AB32,
             funcs=[i64._mul_fn(False, False)]),  # fmt: skip
    CostCase("x * y (128×128 wrap)", _op(lambda t, a, b: a * b), AB, funcs=[i128._mulbig_fn(4)]),
    CostCase("x * Int64 (128×64)", _op(lambda t, a, b: a * b.lo), AB, funcs=[i128._mulbig_fn(2)]),
    CostCase("x *= 10 (상수 128비트 x)", _op(lambda t, a, b: a.imul(10)), A1, funcs=[i128._mulk_fn(10, 4)]),
    CostCase("mul64(Int64, 6500000000000) (상수)", lambda t: i128.mul64(_q(t, "a").lo, 6500000000000), A1,
             funcs=[i128._mulk_fn(6500000000000, 2)]),  # fmt: skip
    CostCase("x * 10^16 (상수 128비트 x)", _op(lambda t, a, b: a * 10**16), A1, funcs=[i128._mulk_fn(10**16, 4)]),
    CostCase("x // v32 (32비트 제수)", _op(lambda t, a, b: a // b.w0), DIV32, funcs=[i128._udiv_fn(1)],
             note="i64 64÷64 본문 1~3번", target={"exec": 1300}),  # fmt: skip
    CostCase("divmod(x, Int64) (64비트 제수)", _op(lambda t, a, b: i128.divmod(a, b.lo)), DIV32 + DIV64,
             funcs=[i128._udiv_fn(2), i128._d9664_fn()], target={"exec": 1300}),  # fmt: skip
    CostCase("divmod(x, y) (128비트 제수)", _op(lambda t, a, b: i128.divmod(a, b)), DIV128,
             funcs=[i128._udiv_fn(4), i128._d128_fn()], target={"exec": 1600}),  # fmt: skip
    CostCase("x // 100 (상수 제수)", _op(lambda t, a, b: a // 100), A1, funcs=[i128._cdiv_fn(100)]),
    CostCase("divmod(x, 5000) (상수 제수)", _op(lambda t, a, b: i128.divmod(a, 5000)), A1, funcs=[i128._cdiv_fn(5000)]),
    CostCase("x // 10^19 (64비트 상수 제수 — 변수 본문)", _op(lambda t, a, b: a // 10**19), A1),
    CostCase("fmt(x) (10진 39자리)", _op(lambda t, a, b: a.fmt()), FMTV, funcs=[i128._dec128_hi, i64._lidec_body],
             note="값 < 2^64 는 윗 자리 본문을 건너뜀"),  # fmt: skip
    CostCase("fmt(Int64) (64비트 이하)", _op(lambda t, a, b: i128.fmt(a.lo)), FMTV[:2], funcs=[i64._lidec_body]),
    CostCase("lidec_to(상수 EPD, x)", _op(lambda t, a, b: i128.lidec_to(EPD(Db(44)), a)), FMTV),
    CostCase("x.to64() (포화)", _op(lambda t, a, b: a.to64()), A1),
    CostCase("x.to32() (포화)", _op(lambda t, a, b: a.to32()), A1),
    CostCase("arr[i] 읽기 (변수 칸)", lambda t: Int128Array(8)[t.var("i")], [{"i": 2}]),
    CostCase("arr[i] = y (변수 칸)", lambda t: Int128Array(8).set(t.var("i"), _q(t, "b")), [_p({"i": 2}, "b", 5)]),
    CostCase("arr[i] += y (변수 칸, 읽고 쓰기)", lambda t: Int128Array(8).iadd(t.var("i"), _q(t, "b")), [_p({"i": 2}, "b", 5)]),
    CostCase("arr[3] += 5 (상수 칸·상수 값)", lambda t: Int128Array(8).iadd(3, 5)),
    CostCase("arr[3] >= 10^30 (상수 칸)", lambda t: Trigger(conditions=Int128Array(8).geitem(3, 10**30))),
    CostCase("참고: i64 x += y", lambda t: q64(t, "a").iadd(q64(t, "b")), AB64H),
    CostCase("참고: i64 x * y", lambda t: q64(t, "a") * q64(t, "b"), AB64H, funcs=[i64._mul_fn(True, True)]),
]


def repo_artifacts():
    found = []
    for dirpath, dirnames, filenames in os.walk(_common.PKG):
        rel = os.path.relpath(dirpath, _common.PKG)
        if rel.startswith("docs"):
            continue
        for d in dirnames:
            if d in ("__pycache__", "__epspy__"):
                found.append(os.path.join(rel, d))
        for f in filenames:
            if f.endswith((".scx", ".pyc")) and not (rel == "testing" and f.startswith("base")):
                found.append(os.path.join(rel, f))
    return found


def main():
    before = set(repo_artifacts())
    ck = Checker("t_i128 (python)")
    only = os.environ.get("EUDEXT_I128_ONLY", "")
    parts = only.split(",") if only else ["vars", "const", "misc", "eps", "py", "ingame", "build", "bad"]
    oks = []
    if "vars" in parts:
        oks.append(suite_vars())
    if "const" in parts:
        oks.append(suite_const())
    if "misc" in parts:
        oks.append(suite_misc())
    if "eps" in parts:
        oks.append(suite_eps(load_eps("i128_example")))
    if "py" in parts:
        python_checks(ck)
        eps_checks(ck)
    if "ingame" in parts:
        ingame_emulate(ck)
    if "build" in parts:
        euddraft_builds(ck)
    if "bad" in parts:
        bad_builds(ck)
    # 같은 작업 트리에서 다른 시험이 동시에 돌 수 있어, 이 시험이 만들 수 있는 것(i128·epScript 번역·맵)만 본다
    mine = [p for p in set(repo_artifacts()) - before if "i128" in p or "__epspy__" in p or p.endswith(".scx")]
    ck.eq("repo clean", sorted(mine), [])
    oks.append(ck.report())
    finish(*oks)


if __name__ == "__main__":
    main()
