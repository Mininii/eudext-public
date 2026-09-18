"""`i64` 차등 시험 (에뮬레이터): 64비트 덧셈·wrap/포화 뺄셈·부호 반전·비교·대입·배열·10진 출력·epScript.

- 경계값 24개 전 쌍(576) + 무작위 1,500쌍 = 2,076쌍 × 변수끼리 모든 연산 (S8 6.2 검증 방식).
  뺄셈 두 의미(wrap / 포화)를 인라인·공유 함수·3인자(CtrigAsm 별칭)·epScript 통로로 따로 본다.
- 상수 24개 × (경계값 24 + 상수 근처 6 + 무작위 30) × 상수 연산(오른쪽·왼쪽, 정수·음수·문자열 표기).
- 32비트 값 올리기(0 확장), 같은 객체끼리(`x -= x`, `sub_sat(x, x)`, `x += x` …), 반쪽이 엇갈려 겹치는 경우,
  2^32 − 1 빌림 경계, 비교를 여러 문맥(EUDIf·neg·EUDNot·RawTrigger·EUDSCAnd/Or·EUDTernary·EUDElseIf)에서,
  EUDWhile 조건 재계산, Int64Array(상수·변수 칸 × 상수·변수 값), 10진 출력 바이트, 시제품 시험 400건.
- epScript 예제(examples/i64_example.eps) 번역·에뮬레이터 실행·euddraft 빌드, 인게임 확인 맵(i64_ingame) 에뮬레이터·빌드.

python tests/t_i64.py
비용 표: python tools/cost.py tests/t_i64.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import importlib.util  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import types  # noqa: E402

from eudplib import (  # noqa: E402
    EPD,
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
    Forward,
    LoadMap,
    RawTrigger,
    SeqCompute,
    SetTo,
    Trigger,
    f_dbstr_print,
    f_sprintf,
)

from eudext import _compat, cmp, i64  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.i64 import Int64, Int64Array  # noqa: E402
from eudext.testing import emu  # noqa: E402
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1
S63 = 1 << 63
EX = os.path.join(_common.PKG, "examples")

# S8 6.2 의 경계값 24개 (docs/spec/S8_subtract.md) — 2^32 − 1 빌림 경계, 2^63 부호 경계, 10진 자리 경계 포함
EDGES = (
    0, 1, 2, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, M32, 1 << 32, (1 << 32) + 1, (1 << 33) - 1,
    2 << 32, S63 - 1, S63, S63 + 1, M64 - 1, M64,
    0x123456789ABCDEF0, 0xFFFFFFFF00000000, 0x0000000180000000, 0x8000000080000000,
    0x7FFFFFFF7FFFFFFF, 0xFFFFFFFE00000001, 10**19, 10**19 - 1,
)  # fmt: skip
assert len(EDGES) == 24 and len(set(EDGES)) == 24


def s64(v):
    v &= M64
    return v - (1 << 64) if v >> 63 else v


def pairs(n_random=1500, seed=7):
    """경계값 전 쌍 + 무작위 (hi 같음·같은 값·±3 섞음)."""
    out = [(a, b) for a in EDGES for b in EDGES]
    rng = random.Random(seed)
    for _ in range(n_random):
        a, b = rng.getrandbits(64), rng.getrandbits(64)
        r = rng.random()
        if r < 0.3:
            b = (a & (M32 << 32)) | rng.getrandbits(32)
        elif r < 0.4:
            b = a
        elif r < 0.5:
            b = a + rng.randrange(-3, 4)
        out.append((a & M64, b & M64))
    return out


PAIRS = pairs()
ORACLE = {
    "add": lambda a, b: (a + b) & M64,
    "sub": lambda a, b: (a - b) & M64,
    "ssub": lambda a, b: a - b if a >= b else 0,
    "ge": lambda a, b: int(a >= b),
    "gt": lambda a, b: int(a > b),
    "le": lambda a, b: int(a <= b),
    "lt": lambda a, b: int(a < b),
    "eq": lambda a, b: int(a == b),
    "ne": lambda a, b: int(a != b),
    "sge": lambda a, b: int(s64(a) >= s64(b)),
    "sgt": lambda a, b: int(s64(a) > s64(b)),
    "sle": lambda a, b: int(s64(a) <= s64(b)),
    "slt": lambda a, b: int(s64(a) < s64(b)),
}
CMP_OPS = ("ge", "gt", "le", "lt", "eq", "ne", "sge", "sgt", "sle", "slt")
PYCMP = {
    "ge": lambda x, y: x >= y,
    "gt": lambda x, y: x > y,
    "le": lambda x, y: x <= y,
    "lt": lambda x, y: x < y,
    "eq": lambda x, y: x == y,
    "ne": lambda x, y: x != y,
}


# ---------------------------------------------------------------------------------------------
# 도우미
# ---------------------------------------------------------------------------------------------


def q(t, name):
    """64비트 입력·출력 칸 (name.lo / name.hi)."""
    return Int64.wrap(t.var(name + ".lo"), t.var(name + ".hi"))


def put(d, name, v):
    d[name + ".lo"] = v & M32
    d[name + ".hi"] = (v >> 32) & M32
    return d


def cmpf(op):
    """비교: 부호 없는 것은 연산자, 부호 있는 것은 메서드 (둘 다 쓰이게 번갈아)."""
    if op[0] == "s":
        return lambda a, b: getattr(a, op)(b)
    return {
        "ge": lambda a, b: a >= b,
        "gt": lambda a, b: a > b,
        "le": lambda a, b: a <= b,
        "lt": lambda a, b: a < b,
        "eq": lambda a, b: a == b,
        "ne": lambda a, b: a != b,
    }[op]


def judge(s, case, inputs, expect, label, fresh=False):
    """케이스를 한 번 돌리고 출력마다 판정을 하나씩 기록한다. expect: {이름: 값} (64비트 이름은 .lo/.hi 가 있는 것)."""
    r = s.run(case, inputs, fresh=fresh)
    if r.error:
        s.expect_true(case, False, label, r.error)
        return r
    vals = r.values
    for k, want in expect.items():
        if k + ".lo" in vals:
            got = vals[k + ".lo"] | (vals[k + ".hi"] << 32)
            want &= M64
            fmt = "0x%016X"
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


def contexts(t, tag, mk, level):
    """mk() 는 부를 때마다 새 조건을 만든다. 결과 이름: tag + 접미사. level 1 = neg·EUDNot·RawTrigger, 2 = 전부."""
    z = t.var("z")  # 늘 0
    ifval(t, tag + "_if", mk)
    ifval(t, tag + "_neg", mk, neg=True)
    nv = EUDNot(mk())
    ifval(t, tag + "_not", lambda: nv)
    rr = t.var(tag + "_raw")
    DoActions(rr.SetNumber(0))
    RawTrigger(conditions=mk(), actions=rr.SetNumber(1))
    if level < 2:
        return
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


def ctx_expect(tag, r0, level):
    e = {tag + "_if": r0, tag + "_neg": 1 - r0, tag + "_not": 1 - r0, tag + "_raw": r0}
    if level >= 2:
        e.update({tag + s: r0 for s in ("_and", "_or", "_list", "_tern", "_elif")})
        e.update({tag + s: 1 - r0 for s in ("_andn", "_orn", "_ternn")})
    return e


# ---------------------------------------------------------------------------------------------
# 묶음 1: 변수끼리 (2,076쌍)
# ---------------------------------------------------------------------------------------------

VV_SUB = ("sub", "subf", "isub", "isubf", "vsub", "lisub", "lisubf")
VV_SSUB = ("ssub", "ssubi", "iss", "issi", "iss2", "lsub", "fiss")
VV_ADD = ("add", "addf", "radd", "iadd", "vadd", "ladd", "fiadd")


def build_vv(s):
    @s.case("vv")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        # 덧셈
        q(t, "add") << a + b
        q(t, "addf") << i64.add(a, b)
        q(t, "radd") << b + a
        x = q(t, "iadd")
        x << a
        x += b
        x = q(t, "vadd")
        x << a
        x.iaddattr("v", b)
        i64.LAdd(q(t, "ladd"), a, b)
        x = q(t, "fiadd")
        x << a
        i64.iadd(x, b)
        # wrap 뺄셈
        q(t, "sub") << a - b
        q(t, "subf") << i64.sub(a, b, inline=False)
        x = q(t, "isub")
        x << a
        x -= b
        x = q(t, "isubf")
        x << a
        x.isub(b, inline=False)
        x = q(t, "vsub")
        x << a
        x.isubattr("v", b)
        i64.LiSub(q(t, "lisub"), a, b)
        x = q(t, "lisubf")
        x << a
        i64.isub(x, b, inline=False)
        # 포화 뺄셈
        q(t, "ssub") << i64.sub_sat(a, b)
        q(t, "ssubi") << i64.sub_sat(a, b, inline=True)
        x = q(t, "iss")
        x << a
        x.isub_sat(b)
        x = q(t, "issi")
        x << a
        x.isub_sat(b, inline=True)
        x = q(t, "iss2")
        x << a
        x.isubtractattr("v", b)
        i64.LSub(q(t, "lsub"), a, b)
        x = q(t, "fiss")
        x << a
        i64.isub_sat(x, b, inline=True)
        # 부호 반전 (wrap)
        q(t, "neg") << -a
        q(t, "negf") << a.neg()
        x = q(t, "ineg")
        x << a
        x.ineg()
        i64.LNeg(q(t, "lneg"), a)
        # 비교
        for op in CMP_OPS:
            t.flag(op, cmpf(op)(a, b))
            t.flag("m" + op, getattr(i64, op)(a, b))

    def expect(a, b):
        e = {}
        for k in VV_ADD:
            e[k] = ORACLE["add"](a, b)
        for k in VV_SUB:
            e[k] = ORACLE["sub"](a, b)
        for k in VV_SSUB:
            e[k] = ORACLE["ssub"](a, b)
        for k in ("neg", "negf", "ineg", "lneg"):
            e[k] = (-a) & M64
        for op in CMP_OPS:
            e[op] = e["m" + op] = ORACLE[op](a, b)
        return e

    return expect


def build_vv_ctx(s):
    @s.case("vv_ctx")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        for op in ("ge", "gt", "eq", "ne", "sge", "slt"):
            f = cmpf(op)
            contexts(t, op, lambda f=f: f(a, b), 2)

    def expect(a, b):
        e = {}
        for op in ("ge", "gt", "eq", "ne", "sge", "slt"):
            e.update(ctx_expect(op, ORACLE[op](a, b), 2))
        return e

    return expect


def build_v32(s):
    """32비트 변수 c 를 올려 쓰기 (0 확장), 왼쪽·오른쪽."""

    @s.case("v32")
    def _(t):
        a, c = q(t, "a"), t.var("c")
        q(t, "add") << a + c
        q(t, "radd") << i64.add(c, a)
        x = q(t, "iadd")
        x << a
        x += c
        q(t, "sub") << a - c
        q(t, "rsub") << i64.sub(c, a)
        x = q(t, "isub")
        x << a
        x -= c
        x = q(t, "isubf")
        x << a
        x.isub(c, inline=False)
        q(t, "ssub") << i64.sub_sat(a, c)
        q(t, "rssub") << i64.sub_sat(c, a)
        q(t, "rssubi") << i64.sub_sat(c, a, inline=True)
        x = q(t, "iss")
        x << a
        x.isub_sat(c)
        x = q(t, "issi")
        x << a
        x.isub_sat(c, inline=True)
        q(t, "up") << Int64(c)
        x = q(t, "asg")
        x << a
        x << c
        x = q(t, "vasg")
        x << a
        x.v = c
        q(t, "neg") << i64.neg(c)
        for op in CMP_OPS:
            t.flag(op, getattr(i64, op)(a, c))
            t.flag("r" + op, getattr(i64, op)(c, a))

    def expect(a, c):
        e = {"add": a + c, "radd": a + c, "iadd": a + c, "sub": a - c, "rsub": c - a, "isub": a - c, "isubf": a - c,
             "ssub": max(a - c, 0), "rssub": max(c - a, 0), "rssubi": max(c - a, 0), "iss": max(a - c, 0),
             "issi": max(a - c, 0), "up": c, "asg": c, "vasg": c, "neg": -c}  # fmt: skip
        for op in CMP_OPS:
            e[op] = ORACLE[op](a, c)
            e["r" + op] = ORACLE[op](c, a)
        return e

    return expect


def build_same(s):
    """같은 객체끼리 — 컴파일 시점에 접거나(0, Always/Never) 따로 처리해야 한다 (eudplib `v -= v` 버그를 물려받지 않음)."""

    @s.case("same")
    def _(t):
        a = q(t, "a")
        x = q(t, "isub")
        x << a
        x -= x
        x = q(t, "vsub")
        x << a
        x.v -= x
        x = q(t, "isubf")
        x << a
        x.isub(x, inline=False)
        x = q(t, "iss")
        x << a
        x.isub_sat(x)
        x = q(t, "issi")
        x << a
        x.isub_sat(x, inline=True)
        x = q(t, "iadd")
        x << a
        x += x
        x = q(t, "vadd")
        x << a
        x.v += x
        x = q(t, "asg")
        x << a
        x << x
        x.v = x
        q(t, "add") << i64.add(a, a)
        q(t, "sub") << a - a
        q(t, "ssub") << i64.sub_sat(a, a)
        q(t, "ssubi") << i64.sub_sat(a, a, inline=True)
        x = q(t, "lsub")
        x << a
        i64.LSub(x, x, x)
        x = q(t, "lisub")
        x << a
        i64.LiSub(x, x, x)
        x = q(t, "ladd")
        x << a
        i64.LAdd(x, x, x)
        x = q(t, "lneg")
        x << a
        i64.LNeg(x, x)
        for op in CMP_OPS:
            t.flag(op, cmpf(op)(a, a))
        # 32비트 변수 같은 객체
        c = t.var("c")
        q(t, "c_sub") << i64.sub(c, c)
        q(t, "c_add") << i64.add(c, c)

    def expect(a, c):
        e = {k: 0 for k in ("isub", "vsub", "isubf", "iss", "issi", "sub", "ssub", "ssubi", "lsub", "lisub")}
        for k in ("iadd", "vadd", "add", "ladd"):
            e[k] = 2 * a
        e["asg"] = a
        e["lneg"] = -a
        for op in CMP_OPS:
            e[op] = ORACLE[op](a, a)
        e["c_sub"] = 0
        e["c_add"] = 2 * c
        return e

    return expect


def build_alias(s):
    """반쪽이 엇갈려 겹치는 경우 (Int64.wrap(x.hi, x.lo) 등)."""

    def sw(x):
        return Int64.wrap(x.hi, x.lo)

    @s.case("alias")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        x = q(t, "swap")
        x << a
        x << sw(x)
        x = q(t, "isub")
        x << a
        x -= sw(x)
        x = q(t, "isubf")
        x << a
        x.isub(sw(x), inline=False)
        x = q(t, "iss")
        x << a
        x.isub_sat(sw(x))
        x = q(t, "issi")
        x << a
        x.isub_sat(sw(x), inline=True)
        x = q(t, "iadd")
        x << a
        x += sw(x)
        x = q(t, "lo_only")  # x − (x.lo, b.hi)
        x << a
        x -= Int64.wrap(x.lo, b.hi)
        x = q(t, "hi_only")  # x ⊖ (b.lo, x.hi)
        x << a
        x.isub_sat(Int64.wrap(b.lo, x.hi), inline=True)
        d = q(t, "lsub_d")  # d ← a ⊖ d
        d << b
        i64.LSub(d, a, d)
        d = q(t, "lisub_d")
        d << b
        i64.LiSub(d, a, d)
        d = q(t, "ladd_d")
        d << b
        i64.LAdd(d, a, d)
        d = q(t, "lsub_sw")  # d ← a ⊖ swap(d)
        d << b
        i64.LSub(d, a, sw(d))
        d = q(t, "lneg_sw")
        d << b
        i64.LNeg(d, sw(d))
        d = q(t, "cross")  # d ← swap(d) − a
        d << b
        i64.LiSub(d, sw(d), a)

    def swp(v):
        return ((v & M32) << 32) | (v >> 32)

    def expect(a, b):
        return {
            "swap": swp(a),
            "isub": a - swp(a),
            "isubf": a - swp(a),
            "iss": max(a - swp(a), 0),
            "issi": max(a - swp(a), 0),
            "iadd": a + swp(a),
            "lo_only": a - ((b & (M32 << 32)) | (a & M32)),
            "hi_only": max(a - ((a & (M32 << 32)) | (b & M32)), 0),
            "lsub_d": max(a - b, 0),
            "lisub_d": a - b,
            "ladd_d": a + b,
            "lsub_sw": max(a - swp(b), 0),
            "lneg_sw": -swp(b),
            "cross": swp(b) - a,
        }

    return expect


def suite_vars():
    s = Suite("t_i64 변수끼리")
    e_vv = build_vv(s)
    e_ctx = build_vv_ctx(s)
    e_v32 = build_v32(s)
    e_same = build_same(s)
    e_alias = build_alias(s)
    s.build()
    for a, b in PAIRS:
        judge(s, "vv", put(put({}, "a", a), "b", b), e_vv(a, b), "a=0x%X b=0x%X" % (a, b))
    for a, b in PAIRS[:576] + PAIRS[576:676]:
        judge(s, "vv_ctx", put(put({}, "a", a), "b", b), e_ctx(a, b), "a=0x%X b=0x%X" % (a, b))
    rng = random.Random(11)
    for a, b in PAIRS:
        c = b & M32 if rng.random() < 0.8 else rng.choice((0, 1, M32, 0x80000000, a & M32))
        judge(s, "v32", put({"c": c}, "a", a), e_v32(a, c), "a=0x%X c=0x%X" % (a, c))
    for a in EDGES + tuple(rng.getrandbits(64) for _ in range(100)):
        c = rng.getrandbits(32)
        judge(s, "same", put({"c": c}, "a", a), e_same(a, c), "a=0x%X c=0x%X" % (a, c))
    for a, b in PAIRS[::3]:
        judge(s, "alias", put(put({}, "a", a), "b", b), e_alias(a, b), "a=0x%X b=0x%X" % (a, b))
    # 2^32 − 1 빌림 경계 (이름 붙여 한 번 더)
    for a, b in ((1 << 32, 1), (1 << 32, M32), ((1 << 32) + 5, (1 << 32) + 7), (5, 1 << 32), (M64, M64), (1 << 32, 0)):
        judge(s, "vv", put(put({}, "a", a), "b", b), e_vv(a, b), "빌림 경계 a=0x%X b=0x%X" % (a, b))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 2: 상수 (24개)
# ---------------------------------------------------------------------------------------------

def literal(k, form):
    if form == 1 and k >> 63:
        return k - (1 << 64)  # 음수 표기
    if form == 2:
        return str(k)  # 10진 문자열
    return k


def build_k(s, idx, k):
    lit = literal(k, idx % 3)
    name = "k%02d_%016X" % (idx, k)

    @s.case(name)
    def _(t):
        a = q(t, "a")
        x = q(t, "iadd")
        x << a
        x += lit
        x = q(t, "isub")
        x << a
        x -= lit
        x = q(t, "iss")
        x << a
        x.isub_sat(lit)
        q(t, "add") << a + lit
        q(t, "radd") << i64.add(lit, a)
        q(t, "sub") << a - lit
        q(t, "rsub") << i64.sub(lit, a)
        q(t, "ssub") << i64.sub_sat(a, lit)
        q(t, "rssub") << i64.sub_sat(lit, a)
        i64.LSub(q(t, "lsub"), a, lit)
        i64.LSub(q(t, "rlsub"), lit, a)
        x = q(t, "vsub")
        x << a
        x.v -= lit
        x = q(t, "fsub")
        x << a
        x.isub(lit, inline=False)
        x = q(t, "issi")
        x << a
        x.isub_sat(lit, inline=True)
        q(t, "ssubi") << i64.sub_sat(a, lit, inline=True)
        q(t, "rssubi") << i64.sub_sat(lit, a, inline=True)
        for op in CMP_OPS:
            t.flag(op, cmpf(op)(a, lit))
            t.flag("r" + op, getattr(i64, op)(lit, a))
        contexts(t, "cg", lambda: a >= lit, 1)
        contexts(t, "cn", lambda: a != lit, 1)
        contexts(t, "cs", lambda: a.slt(lit), 1)

    def expect(a):
        e = {"iadd": a + k, "isub": a - k, "iss": max(a - k, 0), "add": a + k, "radd": a + k, "sub": a - k,
             "rsub": k - a, "ssub": max(a - k, 0), "rssub": max(k - a, 0), "lsub": max(a - k, 0),
             "rlsub": max(k - a, 0), "vsub": a - k, "fsub": a - k, "issi": max(a - k, 0), "ssubi": max(a - k, 0),
             "rssubi": max(k - a, 0)}  # fmt: skip
        for op in CMP_OPS:
            e[op] = ORACLE[op](a, k)
            e["r" + op] = ORACLE[op](k, a)
        e.update(ctx_expect("cg", ORACLE["ge"](a, k), 1))
        e.update(ctx_expect("cn", ORACLE["ne"](a, k), 1))
        e.update(ctx_expect("cs", ORACLE["slt"](a, k), 1))
        return e

    return name, expect


def suite_const():
    s = Suite("t_i64 상수")
    cases = [(k, build_k(s, i, k)) for i, k in enumerate(EDGES)]
    s.build()
    rng = random.Random(23)
    for k, (name, expect) in cases:
        near = {(k - 1) & M64, k, (k + 1) & M64, k ^ S63, (k + (1 << 32)) & M64, (k - (1 << 32)) & M64}
        vals = list(EDGES) + sorted(near) + [rng.getrandbits(64) for _ in range(30)]
        for a in vals:
            judge(s, name, put({}, "a", a), expect(a), "K=0x%X a=0x%X" % (k, a))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 3: 루프·배열·생성·출력·epScript
# ---------------------------------------------------------------------------------------------

ARR_K = (5, M32, 1 << 32, 0x123456789, M64, S63)
FMT_VALS = EDGES + tuple(10**k for k in range(20)) + tuple(10**k - 1 for k in range(1, 20)) + (5, 100, 12800000000)


def load_eps(name):
    """예제 eps 를 작업 폴더에 복사해 EPSLoader 로 불러온다(__epspy__ 가 작업 폴더에 생긴다)."""
    d = os.path.join(_common.WORK, "t_i64", "eps")
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


def suite_misc():
    s = Suite("t_i64 루프·배열·생성·출력·epScript")
    checks = []  # (case, inputs, expect, label)

    # --- EUDWhile 조건 재계산 ---
    @s.case("loop_var")
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
        if EUDWhile()(i64.slt(w, x)):  # 부호 있는 조건, 몸통이 w 를 키운다
            m += 1
            EUDBreakIf(m.AtLeast(12))
            w += st
        EUDEndWhile()

    def loop_ref(x, y, st):
        n = 0
        while x >= y:
            n += 1
            if n >= 12:
                break
            x = max(x - st, 0)
        xf = x
        m, w = 0, y
        while s64(w) < s64(xf):
            m += 1
            if m >= 12:
                break
            w = (w + st) & M64
        return {"n": n, "m": m}

    rng = random.Random(5)
    for x, y, st in (((5 << 32) + 3, 1 << 32, 1 << 32), (10, 3, 3), (M64, M64 - 20, 7), (1 << 32, M32, 1), (0, 1, 1),
                     (S63 + 5, S63 - 5, 2), (3, S63, 1 << 62)) + tuple(
        (rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(62)) for _ in range(30)
    ):  # fmt: skip
        d = put(put(put({}, "x", x), "y", y), "st", st)
        checks.append(("loop_var", d, loop_ref(x, y, st), "x=0x%X y=0x%X st=0x%X" % (x, y, st)))

    @s.case("loop_const")
    def _(t):
        x = q(t, "x")
        n = t.var("n")
        n << 0
        if EUDWhile()(x > 0x100000000):
            n += 1
            EUDBreakIf(n.AtLeast(40))
            x.isub_sat(0x80000000)
        EUDEndWhile()
        q(t, "rest") << x

    for x in (0, 1 << 32, (1 << 32) + 1, 5 << 32, 7 << 32, 0x1234567890):
        n, v = 0, x
        while v > (1 << 32):
            n += 1
            if n >= 40:
                break
            v = max(v - 0x80000000, 0)
        checks.append(("loop_const", put({}, "x", x), {"n": n, "rest": v}, "x=0x%X" % x))

    # --- Int64Array ---
    arr = Int64Array(8)
    arr_init = Int64Array([1, "12800000000", -1, 1 << 63])

    @s.case("arr_var")  # 변수 칸 × 변수 값
    def _(t):
        i, a, b, c = t.var("i"), q(t, "a"), q(t, "b"), q(t, "c")
        arr[i] = a
        arr[i] += b
        q(t, "r1") << arr[i]
        arr[i] -= c
        q(t, "r2") << arr[i]
        arr.isub_sat(i, b)
        q(t, "r3") << arr.get(i)
        arr.isubtractitem(i, 3)
        arr.iadditem(i, 1 << 32)
        arr.isubitem(i, 1)
        q(t, "r4") << arr[i]
        j = t.var("j")
        arr[j] = t.var("v32")
        q(t, "r5") << arr[j]
        for op in ("ge", "gt", "le", "lt", "eq", "ne"):
            t.flag(op, getattr(arr, op + "item")(i, b))
        t.flag("sge", i64.sge(arr[i], b))

    def arr_var_ref(i, a, b, c, j, v32):
        x = (a + b) & M64
        r1 = x
        x = (x - c) & M64
        r2 = x
        x = max(x - b, 0)
        r3 = x
        x = max(x - 3, 0)
        x = (x + (1 << 32) - 1) & M64
        r4 = x
        e = {"r1": r1, "r2": r2, "r3": r3, "r4": r4 if i != j else r4, "r5": v32}
        for op in ("ge", "gt", "le", "lt", "eq", "ne"):
            e[op] = int(PYCMP[op](v32 if i == j else r4, b))
        e["sge"] = int(s64(v32 if i == j else r4) >= s64(b))
        return e

    for n_ in range(80):
        a, b, c = rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64)
        if n_ < 12:
            a, b, c = EDGES[n_], EDGES[(n_ * 7) % 24], EDGES[(n_ * 5) % 24]
        i, j = rng.randrange(8), rng.randrange(8)
        v32 = rng.getrandbits(32)
        d = put(put(put({"i": i, "j": j, "v32": v32}, "a", a), "b", b), "c", c)
        checks.append(("arr_var", d, arr_var_ref(i, a, b, c, j, v32), "arr i=%d j=%d a=0x%X b=0x%X c=0x%X" % (i, j, a, b, c)))

    for kk, K in enumerate(ARR_K):

        @s.case("arr_const%d" % kk)  # 상수 칸 × 상수 값 (읽지 않고 칸을 바로 고친다)
        def _(t, K=K, kk=kk):
            a = q(t, "a")
            arr[kk] = a
            arr.iadd(kk, K)
            q(t, "r1") << arr[kk]
            arr.isub(kk, K + 7 if K + 7 <= M64 else 7)
            q(t, "r2") << arr[kk]
            arr.isub_sat(kk, K)
            q(t, "r3") << arr[kk]
            for op in ("ge", "gt", "le", "lt", "eq", "ne"):
                t.flag(op, getattr(arr, op + "item")(kk, K))
                t.flag("v" + op, getattr(arr, op + "item")(kk, q(t, "b")))
            t.flag("sge", arr[kk].sge(K))

        def arr_const_ref(a, b, K=K):
            k2 = K + 7 if K + 7 <= M64 else 7
            x = (a + K) & M64
            r1 = x
            x = (x - k2) & M64
            r2 = x
            x = max(x - K, 0)
            e = {"r1": r1, "r2": r2, "r3": x, "sge": int(s64(x) >= s64(K))}
            for op in ("ge", "gt", "le", "lt", "eq", "ne"):
                e[op] = int(PYCMP[op](x, K))
                e["v" + op] = int(PYCMP[op](x, b))
            return e

        for a in EDGES[::2] + (K, (K + 1) & M64, (K - 1) & M64, rng.getrandbits(64)):
            b = rng.choice((a, K, rng.getrandbits(64), 0, M64))
            checks.append(("arr_const%d" % kk, put(put({}, "a", a), "b", b), arr_const_ref(a, b), "K=0x%X a=0x%X" % (K, a)))

    @s.case("arr_mix")  # 상수 칸 × 변수 값, 변수 칸 × 상수 값
    def _(t):
        a, b, i = q(t, "a"), q(t, "b"), t.var("i")
        arr[6] = a
        arr.iadd(6, b)
        arr.isub(6, 5)
        arr.isub_sat(6, b)
        q(t, "r1") << arr[6]
        arr[i] = b
        arr.iadd(i, 0x100000001)
        arr.isub_sat(i, a)
        q(t, "r2") << arr[i]
        q(t, "init0") << arr_init[0]
        q(t, "init1") << arr_init[1]
        q(t, "init2") << arr_init[2]
        q(t, "init3") << arr_init[t.var("three")]

    for n_ in range(40):
        a, b = rng.getrandbits(64), rng.getrandbits(64)
        if n_ < 10:
            a, b = EDGES[n_ * 2], EDGES[23 - n_]
        i = rng.randrange(8)
        r1 = max(((a + b - 5) & M64) - b, 0)
        r2 = r1 if i == 6 else None
        r2 = max(((b + 0x100000001) & M64) - (r1 if i == 6 else a), 0) if False else max(((b + 0x100000001) & M64) - a, 0)
        d = put(put({"i": i, "three": 3}, "a", a), "b", b)
        e = {"r1": r1, "r2": r2, "init0": 1, "init1": 12800000000, "init2": M64, "init3": 1 << 63}
        checks.append(("arr_mix", d, e, "mix i=%d a=0x%X b=0x%X" % (i, a, b)))

    # --- 생성·대입 (3.2-3) ---
    lv = EUDLightVariable()
    fw = Forward()
    fw << 0x1234

    @s.case("ctor")
    def _(t):
        c, h = t.var("c"), t.var("h")
        q(t, "up") << Int64(c)
        q(t, "pair") << Int64(c, h)
        q(t, "pair_k1") << Int64(c, 5)
        q(t, "pair_k2") << Int64(-1, h)
        q(t, "copy") << Int64(q(t, "a"))
        SeqCompute([(EPD(lv.getValueAddr()), SetTo, c)])
        q(t, "light") << Int64(lv)
        q(t, "light2") << q(t, "a") + lv
        q(t, "fw") << Int64(fw)
        q(t, "str") << Int64("12,800,000,000")
        q(t, "neg1") << Int64(-1)
        # 초기값만(3.2-3): 첫 실행 7, 두 번째 8
        k = Int64(7)
        q(t, "init") << k
        k += 1
        # 실행 시 대입: 매번 hi ← 0 을 다시 한다
        y = Int64(c)
        q(t, "rt") << y
        y += 1 << 32

    def ctor_ref(c, h, a, run):
        return {"up": c, "pair": c | (h << 32), "pair_k1": c | (5 << 32), "pair_k2": M32 | (h << 32), "copy": a,
                "light": c, "light2": a + c, "fw": 0x1234, "str": 12800000000, "neg1": M64, "init": 7 + run,
                "rt": c}  # fmt: skip

    # --- 10진 출력 ---
    buf = Db(96)
    buf2 = Db(64)
    buf3 = Db(24)
    buf4 = Db(24)
    buf5 = Db(24)
    epd4 = EUDVariable(EPD(buf4))

    @s.case("fmt")
    def _(t):
        a, b = q(t, "a"), q(t, "b")
        t.watch("buf", buf)
        t.watch("buf2", buf2)
        t.watch("buf3", buf3)
        t.watch("buf4", buf4)
        t.watch("buf5", buf5)
        f_dbstr_print(buf, "[", a.fmt(), "|", a.fmt(signed=True), "|", a, "|", i64.fmt(t.var("c")), "|", i64.fmt(-5, signed=True),
                      "|", i64.fmt(12345), "]")  # fmt: skip
        f_sprintf(buf2, "{} {}", a.fmt(), b.fmt())
        t.out("lead3", i64.lidec_to(EPD(buf3), a.lo, a.hi))
        t.out("lead4", i64.lidec_to(epd4, b.lo, b.hi))
        t.out("lead5", i64.lidec_to(EPD(buf5), a.lo, a.hi, signed=True))

    s.build()
    m = s.machine
    for name, d, e, label in checks:
        judge(s, name, d, e, label)
    for run, (c, h, a) in enumerate(((5, 7, 0x123456789ABCDEF0), (M32, 0, M64), (0, M32, 0))):
        d = put({"c": c, "h": h}, "a", a)
        judge(s, "ctor", d, ctor_ref(c, h, a, run), "ctor run%d c=0x%X" % (run, c))
    for v in FMT_VALS + tuple(rng.getrandbits(64) for _ in range(120)):
        w = rng.getrandbits(64) if rng.random() < 0.7 else rng.choice(FMT_VALS)
        c = rng.getrandbits(32)
        r = s.run("fmt", put(put({"c": c}, "a", v), "b", w))
        if r.error:
            s.expect_true("fmt", False, "fmt 0x%X" % v, r.error)
            continue
        got = m.read_bytes(m.addr("fmt.buf"), 96).split(b"\0")[0]
        want = ("[%d|%d|%d|%d|-5|12345]" % (v, s64(v), v, c)).encode()
        s.expect_true("fmt", got == want, "fmt 0x%X" % v, "%r != %r" % (got, want))
        got = m.read_bytes(m.addr("fmt.buf2"), 64).split(b"\0")[0]
        want = ("%d %d" % (v, w)).encode()
        s.expect_true("fmt", got == want, "fmt2 0x%X" % v, "%r != %r" % (got, want))
        for key, val in (("buf3", v), ("buf4", w)):
            raw = m.read_bytes(m.addr("fmt." + key), 24)
            digits = ("%020d" % val).encode()
            lead = min(len(digits) - len(str(val)), 19)
            ok = raw[:20] == digits and r.values["lead" + key[-1]] == lead and raw[20:] == b"\0" * 4
            s.expect_true("fmt", ok, "lidec_to %s 0x%X" % (key, val), "%r lead=%d (기대 %r %d)" % (raw, r.values["lead" + key[-1]], digits, lead))
        sv = s64(v)
        digits = bytearray(("%020d" % abs(sv)).encode())
        lead = min(20 - len(str(abs(sv))), 19)
        if sv < 0:
            lead -= 1
            digits[lead] = 0x2D
        raw = m.read_bytes(m.addr("fmt.buf5"), 24)
        ok = raw[:20] == bytes(digits) and r.values["lead5"] == lead and raw[20:] == b"\0" * 4
        s.expect_true("fmt", ok, "lidec_to signed 0x%X" % v, "%r lead=%d (기대 %r %d)" % (raw, r.values["lead5"], bytes(digits), lead))

    return s.report()


def suite_eps(eps):
    s = Suite("t_i64 epScript 예제")
    fns2 = ("wrap_sub", "sat_sub", "sat_sub_new", "lsub")
    for fn in fns2:

        @s.case("eps_" + fn)
        def _(t, fn=fn):
            a, b = q(t, "a"), q(t, "b")
            lo, hi = getattr(eps, "f_" + fn)(a.lo, a.hi, b.lo, b.hi)
            q(t, "r") << Int64.wrap(lo, hi)

    for fn in ("less", "sless", "differs"):

        @s.case("eps_" + fn)
        def _(t, fn=fn):
            a, b = q(t, "a"), q(t, "b")
            t.out("r", getattr(eps, "f_" + fn)(a.lo, a.hi, b.lo, b.hi))

    @s.case("eps_add32")
    def _(t):
        a = q(t, "a")
        lo, hi = eps.f_add32(a.lo, a.hi, t.var("c"))
        q(t, "r") << Int64.wrap(lo, hi)

    @s.case("eps_over")
    def _(t):
        a = q(t, "a")
        t.out("r", eps.f_over_price(a.lo, a.hi))

    @s.case("eps_arr")
    def _(t):
        lo, hi = eps.f_arr_ops(t.var("p"), t.var("c"))
        q(t, "r") << Int64.wrap(lo, hi)
        t.out("k", eps.f_arr_const(t.var("c")))

    @s.case("eps_count")
    def _(t):
        a = q(t, "a")
        t.out("r", eps.f_count_down(a.lo, a.hi))

    @s.case("eps_neg")
    def _(t):
        a = q(t, "a")
        lo, hi = eps.f_neg(a.lo, a.hi)
        q(t, "r") << Int64.wrap(lo, hi)

    pbuf = Db(64)

    @s.case("eps_print")
    def _(t):
        a = q(t, "a")
        t.watch("buf", pbuf)
        eps.f_print_to(pbuf, a.lo, a.hi)

    @s.case("eps_main")
    def _(t):
        eps.afterTriggerExec()
        q(t, "hp") << eps.hp

    s.build()
    m = s.machine
    ref2 = {"wrap_sub": ORACLE["sub"], "sat_sub": ORACLE["ssub"], "sat_sub_new": ORACLE["ssub"], "lsub": ORACLE["ssub"],
            "less": ORACLE["lt"], "sless": ORACLE["slt"], "differs": ORACLE["ne"]}  # fmt: skip
    for a, b in PAIRS[:576:2] + PAIRS[576::10]:
        for fn, f in ref2.items():
            judge(s, "eps_" + fn, put(put({}, "a", a), "b", b), {"r": f(a, b)}, "a=0x%X b=0x%X" % (a, b))
    rng = random.Random(31)
    for a in EDGES:
        c = rng.getrandbits(32)
        judge(s, "eps_add32", put({"c": c}, "a", a), {"r": a + c}, "a=0x%X" % a)
        judge(s, "eps_over", put({}, "a", a), {"r": int(a > 12800000000)}, "a=0x%X" % a)
        judge(s, "eps_neg", put({}, "a", a), {"r": -a}, "a=0x%X" % a)
        r = s.run("eps_print", put({}, "a", a))
        got = m.read_bytes(m.addr("eps_print.buf"), 64).split(b"\0")[0]
        want = ("%d %d" % (a, s64(a))).encode()
        s.expect_true("eps_print", r.error is None and got == want, "print 0x%X" % a, "%r != %r %s" % (got, want, r.error))
    for c in (0, 1, 5, 7, 8, M32, 0x80000000):
        p = rng.randrange(8)
        x = max(((c + (1 << 32)) - 1) - 7, 0)
        judge(s, "eps_arr", {"p": p, "c": c}, {"r": x, "k": int(c >= 1)}, "arr c=0x%X" % c)
    for a in (0, 2, 3, 5, 9, 29, 31):
        n = 0
        v = a
        while v >= 3:
            v -= 3
            n += 1
        judge(s, "eps_count", put({}, "a", a), {"r": n}, "count a=0x%X" % a)
    for i in range(3):  # 초기값 0x100000000 에서 사이클마다 +5
        judge(s, "eps_main", {}, {"hp": 0x100000000 + 5 * (i + 1)}, "main %d" % i)
    return s.report()


# ---------------------------------------------------------------------------------------------
# 시제품 시험 400건 (docs/proto/t_i64_emu.py 를 새 API 로)
# ---------------------------------------------------------------------------------------------

PROTO_KS = [0, 1, 0xFFFFFFFF, 0x100000000, 0x123456789, (1 << 63), M64, (1 << 63) - 1, 0xFFFFFFFF00000000]
PROTO_K32 = [0, 5, 0x7FFFFFFF, -1, -5, -0x80000000]


def suite_proto400():
    s = Suite("t_i64 시제품 400")

    @s.case("proto")
    def _(t):
        A, B = q(t, "A"), q(t, "B")
        x32, y32 = t.var("x"), t.var("y")
        q(t, "add") << A + B
        q(t, "sub") << A - B
        t.flag("ge", A >= B)
        t.flag("le", A <= B)
        t.flag("lt", A < B)
        t.flag("gt", A > B)
        t.flag("eq", A == B)
        t.flag("ne", A != B)
        t.flag("sge", A.sge(B))
        t.flag("sge32", cmp.sge(x32, y32))  # 시제품 f_sge32 → WP1 cmp.sge
        for j, k in enumerate(PROTO_KS):
            T = q(t, "addk%d" % j)
            T << A
            T += k
            U = q(t, "subk%d" % j)
            U << A
            U -= k
            t.flag("gek%d" % j, A >= k)
            t.flag("lek%d" % j, A <= k)
            t.flag("sgek%d" % j, A.sge(k))
            t.flag("eqk%d" % j, A == k)
        for j, k in enumerate(PROTO_K32):
            t.flag("s32k%d" % j, cmp.sge(x32, k))

    s.build()
    rng = random.Random(1234)
    special = [0, 1, 0xFFFFFFFF, 1 << 32, (1 << 63) - 1, 1 << 63, M64, 0xFFFFFFFF00000000] + PROTO_KS

    def s32(v):
        return v - (1 << 32) if v >> 31 else v

    for it in range(400):
        if it < len(special) ** 2 and it < 200:
            a = special[it // len(special) % len(special)]
            b = special[it % len(special)]
        else:
            a, b = rng.getrandbits(64), rng.getrandbits(64)
            if rng.random() < 0.3:
                b = (a & 0xFFFFFFFF00000000) | rng.getrandbits(32)
            if rng.random() < 0.1:
                b = a
        x, y = rng.getrandbits(32), rng.getrandbits(32)
        if rng.random() < 0.2:
            y = rng.choice([0, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, x])
        d = put(put({"x": x, "y": y}, "A", a), "B", b)
        e = {}
        for nm, v in (("add", (a + b) & M64), ("sub", (a - b) & M64)):
            e[nm + ".lo"], e[nm + ".hi"] = v & M32, v >> 32
        e.update(ge=int(a >= b), le=int(a <= b), lt=int(a < b), gt=int(a > b), eq=int(a == b), ne=int(a != b),
                 sge=int(s64(a) >= s64(b)), sge32=int(s32(x) >= s32(y)))  # fmt: skip
        for j, k in enumerate(PROTO_KS):
            for nm, v in (("addk%d" % j, (a + k) & M64), ("subk%d" % j, (a - k) & M64)):
                e[nm + ".lo"], e[nm + ".hi"] = v & M32, v >> 32
            e["gek%d" % j] = int(a >= k)
            e["lek%d" % j] = int(a <= k)
            e["sgek%d" % j] = int(s64(a) >= s64(k))
            e["eqk%d" % j] = int(a == k)
        for j, k in enumerate(PROTO_K32):
            e["s32k%d" % j] = int(s32(x) >= k)
        s.check("proto", d, e, label="proto#%d a=0x%X b=0x%X" % (it, a, b))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 인게임 확인 맵 (에뮬레이터) · euddraft 빌드 · epScript 번역 · 파이썬 쪽 판정
# ---------------------------------------------------------------------------------------------


def ingame_emulate(ck):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_i64_ingame")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, "i64_ingame.eps"), os.path.join(work, "i64_ingame.eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(work, "i64_ingame.eps"), {})
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "okCount", "total", "ti", "raw1", "raw2", "raw3")
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
    print("  인게임 맵 에뮬레이션: %r, 사이클 최대 실행 %d" % (got, max(steps) if steps else -1))
    ck.eq("ingame emu 오류", err, None)
    ck.eq("ingame emu 값", got, {"frame": 130, "okCount": 23, "total": 23, "ti": 23, "raw1": 0, "raw2": 0, "raw3": 0x7FFFFFFF})


def euddraft_builds(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("i64_example", "i64_ingame"):
        work = os.path.join(_common.WORK, "t_i64_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("euddraft freeze off " + name, not r.freeze)
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, r.log[-1000:])
        ck.true("boot preload " + name, "i64" in r.log, "")


def eps_checks(ck):
    for name in ("i64_example", "i64_ingame"):
        with open(os.path.join(EX, name + ".eps"), encoding="utf-8") as f:
            src = f.read()
        out, nerr = _compat.eps_compile(name + ".eps", src)
        ck.eq("eps 오류 수 " + name, nerr, 0)
        ck.true("eps 번역 " + name, out is not None)
        if name != "i64_example" or not out:
            continue
        for needle in (
            "from eudext import i64 as i64",
            "hp = _CGFW(lambda: [i64.Int64(0x100000000)], 1)[0]",
            "_ATTW(hp, 'v').__iadd__(5)",
            "EUDIf()(hp >= 0x100000005)",
            "f_printAll('HP {}', hp.fmt())",
            "_ATTW(a, 'v').__isub__(i64.f_wrap(blo, bhi))",
            "a.isub_sat(i64.f_wrap(blo, bhi))",
            "i64.f_sub_sat(",
            "i64.LSub(",
            "EUDTernary(i64.f_wrap(alo, ahi) >= i64.f_wrap(blo, bhi), neg=True)",
            "i64.f_slt(",
            "_ARRW(gold, p) << (v)",
            "_ARRW(gold, p).__iadd__(",
            "_ARRW(gold, p).__isub__(1)",
            "gold.isub_sat(p, 7)",
            "EUDWhile()(x >= 3)",
            "i64.f_fmt(x, signed=True)",
        ):
            ck.true("eps 번역에 %s" % needle, needle.replace("'", '"') in out or needle in out, needle)
    # DESIGN 0.3 의 epScript 예 그대로
    src = (
        "import eudext.i64 as i64;\nimport eudext.cmp as cmp;\n"
        "const hp = i64.Int64(0x100000000);\nvar mp;\n"
        "function afterTriggerExec() {\n    hp.v += 5;\n    if (hp >= 0x100000005) {\n"
        '        printAll("HP {}", hp.fmt());\n    }\n}\n'
    )
    out, nerr = _compat.eps_compile("design03.eps", src)
    ck.true("DESIGN 0.3 예 번역", out is not None and nerr == 0)


def bad_builds(ck):
    """문서 안내 확인: epScript `x << 3`(시프트 번역)·`var x = i64.Int64(5)`·`return hp >= 1;` 는 빌드 오류.

    빌드 실패가 뒤 빌드에 영향을 주지 않게 모든 에뮬레이터 시험 뒤에 부른다.
    """
    src = (
        "import eudext.i64 as i64;\n"
        "const hp = i64.Int64(5);\n"
        "function bshift() { const q = hp << 3; }\n"
        "function bvar() { var x = i64.Int64(5); x += 1; }\n"
        "function bret() { return hp >= 1; }\n"
        "function belem() { const g = i64.Int64Array(2); const e = g[0]; e.v += 1; }\n"
        "var v;\n"
        "function bvleft() { if (v >= hp) { v = 1; } }\n"
    )
    out, nerr = _compat.eps_compile("bad_i64.eps", src)
    ck.true("bad eps 번역", out is not None and nerr == 0, str(nerr))
    ns = {}
    exec(compile(out, "bad_i64.eps.py", "exec"), ns)  # noqa: S102 — 시험용 번역문
    want = {
        "f_bshift": "시프트",
        "f_bvar": "",
        "f_bret": "",
        "f_belem": "사본",
        "f_bvleft": "",  # 32비트 변수가 왼쪽이면 eudplib 연산자가 먼저 불려 빌드 오류 → i64.ge(v, x) 로 쓴다
    }

    @EUDTypedFunc([Int64])
    def typed(a):
        pass

    ns["f_typed"] = lambda: typed(EUDVariable())
    want["f_typed"] = "두 인자"
    for fn, needle in want.items():
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
    x, y = Int64(0), Int64(0)
    v = EUDVariable()
    # 상수 접기
    ck.eq("add const", i64.add(1, 2), 3)
    ck.eq("add wrap", i64.add(M64, 2), 1)
    ck.eq("sub const", i64.sub(0, 1), M64)
    ck.eq("sub_sat const", i64.sub_sat(1, 2), 0)
    ck.eq("sub_sat const2", i64.sub_sat("12800000000", 1 << 32), 12800000000 - (1 << 32))
    ck.eq("neg const", i64.neg(1), M64)
    for op in CMP_OPS:
        for a, b in ((5, 3), (3, 5), (M64, 0), (0, M64), (7, 7)):
            c = getattr(i64, op)(a, b)
            ck.true("fold %s(%d, %d)" % (op, a, b), isinstance(c, Condition) and c.fields[5] == (22 if ORACLE[op](a, b) else 23))
        c = getattr(i64, op)(x, x)
        ck.true("same %s" % op, isinstance(c, Condition) and c.fields[5] == (22 if ORACLE[op](1, 1) else 23))
        ck.true("alias %s" % op, getattr(i64, op) is getattr(i64, "f_" + op))
        ck.true("fresh %s" % op, getattr(i64, op)(x, 5) is not getattr(i64, op)(x, 5))
    ck.true("alias sub_sat", i64.sub_sat is i64.f_sub_sat and i64.isub_sat is i64.f_isub_sat)
    ck.true("alias LSub", i64.LSub is i64.f_LSub and i64.LiSub is i64.f_LiSub and i64.LNeg is i64.f_LNeg)
    ck.true("alias parse/fmt/lidec", i64.parse is i64.f_parse and i64.fmt is i64.f_fmt and i64.lidec_to is i64.f_lidec_to)
    ck.eq("__all__ 중복", sorted(i64.__all__), sorted(set(i64.__all__)))
    for name in i64.__all__:
        ck.true("__all__ %s" % name, hasattr(i64, name))
    # 뺄셈 두 의미의 이름 (3.5): SubtractNumber/AddNumber 는 없다
    ck.true("Int64.SubtractNumber 없음", not hasattr(Int64, "SubtractNumber") and not hasattr(Int64, "AddNumber"))
    ck.true("isubtractitem = 포화", Int64Array.isubtractitem is Int64Array.isub_sat and Int64Array.isubitem is Int64Array.isub)
    # parse
    ck.eq("parse 쉼표", i64.parse("12,800,000,000"), 12800000000)
    ck.eq("parse 밑줄", i64.parse("12_800_000_000"), 12800000000)
    ck.eq("parse -1", i64.parse("-1"), M64)
    ck.eq("parse 0x", i64.parse("0x100000000"), 1 << 32)
    ck.eq("parse max", i64.parse("18446744073709551615"), M64)
    ck.eq("parse min", i64.parse("-9223372036854775808"), 1 << 63)
    for bad in ("abc", "1.5", "18446744073709551616", "-9223372036854775809", "", None, 1.5):
        ck.raises("parse %r" % (bad,), EudextError, i64.parse, bad)
    # 생성 오류
    ck.raises("Int64(2^64)", EudextError, Int64, 1 << 64)
    ck.raises("Int64(-2^63-1)", EudextError, Int64, -(1 << 63) - 1)
    ck.raises("Int64(lo, hi 넘침)", EudextError, Int64, 1, 1 << 32)
    ck.raises("Int64(lo 넘침, hi)", EudextError, Int64, 1 << 32, 1)
    ck.raises("Int64(Int64, 1)", EudextError, Int64, x, 1)
    ck.raises("Int64(1.5)", EudextError, Int64, 1.5)
    ck.raises("Int64(None)", EudextError, Int64, None)
    ck.raises("Int64(LightBool)", EudextError, Int64, EUDLightBool())
    ck.raises("wrap 정수", EudextError, Int64.wrap, 1, 2)
    ck.raises("wrap Light", EudextError, Int64.wrap, EUDLightVariable(), v)
    ck.raises("Array 0", EudextError, Int64Array, 0)
    ck.raises("Array str", EudextError, Int64Array, "8")
    ck.raises("Array 범위", EudextError, Int64Array(3).get, 3)
    ck.raises("Array 번호 str", EudextError, Int64Array(3).get, "0")
    # 실수 막기 (3.2-2)
    ck.raises("bool", EudextError, bool, x)
    ck.raises("format", EudextError, format, x, "")
    ck.raises("sprintf {}", EudextError, f_sprintf, Db(8), "{}", x)
    ck.raises("iter", EudextError, list, x)
    ck.raises("len", EudextError, len, x)
    ck.raises("cast", EudextError, Int64.cast, v)
    ck.true("repr 안내", "const" in repr(x))
    ck.true("hash", hash(x) == id(x))
    ck.true("== None", (x == None) is False and (x != None) is True)  # noqa: E711
    ck.raises(">= None", EudextError, lambda: x >= None)
    ck.raises("+ 1.5", EudextError, lambda: x + 1.5)
    ck.raises("+ Condition", EudextError, lambda: x + v.Exactly(1))
    ck.raises("- LightBool", EudextError, lambda: x - EUDLightBool())

    # 2차(WP4) 연산은 tests/t_i64_ops.py 가 본다. 여기서는 여전히 안 되는 것만.
    for label, fn in (("pow", lambda: x ** 2), ("truediv", lambda: x / 2), ("rlshift", lambda: 1 << x)):
        ck.raises("안 됨 " + label, EudextError, fn)
    ck.true("2차 연산은 새 값", isinstance(x * y, Int64) and isinstance(i64.f_divmod(x, 3), tuple))
    # 배열 원소 사본에 쓰기 → 오류
    arr = Int64Array(4)
    e = arr[1]
    ck.raises("사본 +=", EudextError, e.iadd, 1)
    ck.raises("사본 -=", EudextError, e.isub, 1)
    ck.raises("사본 isub_sat", EudextError, e.isub_sat, 1)
    ck.raises("사본 <<", EudextError, e.assign, 1)
    ck.raises("사본 .v =", EudextError, setattr, e, "v", 1)
    ck.raises("사본 .v +=", EudextError, e.iaddattr, "v", 1)
    ck.raises("사본 ineg", EudextError, e.ineg)
    ck.true("사본 → Int64 복사는 됨", isinstance(Int64(e), Int64) and isinstance(e + 1, Int64))
    e2 = arr[2]
    e2 += 1  # 파이썬 연산자는 되쓰기 전제라 막지 않는다
    e2 -= 1
    arr[2] = e2
    ck.true("사본 += 연산자는 됨", True)
    ck.raises("iaddattr 다른 이름", AttributeError, x.iaddattr, "w", 1)
    ck.raises("제자리 대상", EudextError, i64.isub_sat, v, 1)
    ck.raises("LSub 대상", EudextError, i64.LSub, 5, x, y)
    ck.raises("fmt signed", EudextError, i64.fmt, x, signed=1)
    ck.raises("lidec lead", EudextError, i64.lidec_to, 0, x.lo, x.hi, lead=5)
    # 반환 모양·제자리 부정 (3.4): 채운 조건은 amount 가 정수가 아니다
    c = x >= y
    ck.true("ge 변수 = 목록", isinstance(c, list) and all(isinstance(k, Condition) for k in c))
    filled = [k for k in c if not isinstance(k.fields[2], int)]
    ck.true("ge 변수 채운 조건 있음", len(filled) >= 1)
    ck.true("eq 상수 = 조건 목록(트리거 0)", isinstance(x == 5, list))
    ck.true("ge 상수 kl=0 = 조건 하나", isinstance(x >= (5 << 32), Condition))
    ck.true("ge 32비트 변수 = 조건", isinstance(i64.ge(v, x), (Condition, list)))
    ck.true("반환 self", (x.iadd(1) is x) and (x.isub(1) is x) and (x.isub_sat(1) is x) and (x.assign(1) is x))
    ck.true("v 통로", x.v is x)
    # 비공개 API 는 _compat 에서만 (3.9)
    with open(i64.__file__, encoding="utf-8") as f:
        text = f.read()
    ck.true("_compat 밖 비공개 API 없음", "from eudplib." not in text and "import eudplib." not in text)
    ck.true("P1 마린 칸 안 씀", "0x58A364" not in text)


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py)
# ---------------------------------------------------------------------------------------------

AB = [put(put({}, "a", 5), "b", 3), put(put({}, "a", 3), "b", (1 << 32) + 5), put(put({}, "a", 1 << 32), "b", 1)]
A1 = [put({}, "a", 5), put({}, "a", 1 << 32), put({}, "a", M64)]
AC = [put({"c": 3}, "a", 5), put({"c": 7}, "a", 1 << 32)]

T_ADD = {"call": 3}  # 3.8: 덧셈·wrap 뺄셈 호출 자리 ≤ 3
T_SATK = {"call": 4, "exec": 4}  # 3.8: 포화 상수 ≤ 4 인라인
T_SATV = {"call": 3, "exec": 30}  # 3.8: 포화 변수 호출 자리 ≤ 3, 실행 ≤ 30
T_DEC = {"body": 620, "exec": 450}  # 3.8: 64비트 10진 본문 ≤ 620, 실행 ≤ 450


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


def _proto():
    """시제품(docs/proto/i64_proto.py)을 따로 불러 비교용으로 잰다 (eudplib 0.76 시절 코드 — 0.81 에서도 돈다)."""
    p = os.path.join(_common.PKG, "docs", "proto", "i64_proto.py")
    spec = importlib.util.spec_from_file_location("_i64_proto_for_cost", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


try:
    PROTO = _proto()
except Exception:  # noqa: BLE001
    PROTO = None


def _pq(t, n):
    return PROTO.Int64.wrap(t.var(n + ".lo"), t.var(n + ".hi"))


COST_CASES = [
    CostCase("x += 5 (상수 lo)", _op(lambda t, a, b: a.iadd(5)), A1, target=T_ADD),
    CostCase("x += 2^32 (상수 hi 만)", _op(lambda t, a, b: a.iadd(1 << 32)), A1, target=T_ADD),
    CostCase("x += y (변수)", _op(lambda t, a, b: a.iadd(b)), AB, target=T_ADD, note="채우기 한 줄 + 올림 트리거"),
    CostCase("x += v32 (32비트 변수)", lambda t: _q(t, "a").iadd(t.var("c")), AC, target=T_ADD),
    CostCase("x += x (같은 객체)", _op(lambda t, a, b: a.iadd(a)), A1, target=T_ADD),
    CostCase("r = x + y (새 값)", _op(lambda t, a, b: a + b), AB, target=T_ADD),
    CostCase("r = x + 5 (새 값)", _op(lambda t, a, b: a + 5), A1, target=T_ADD),
    CostCase("x -= 5 (상수 wrap, S8 WK)", _op(lambda t, a, b: a.isub(5)), A1, target=T_ADD),
    CostCase("x -= y (변수 wrap, 인라인)", _op(lambda t, a, b: a.isub(b)), AB, target=T_ADD, note="S8 WVb 6 / 12 보다 적음"),
    CostCase("x -= v32 (32비트 변수 wrap)", lambda t: _q(t, "a").isub(t.var("c")), AC, target=T_ADD),
    CostCase("x.isub(y, inline=False) (공유 함수)", _op(lambda t, a, b: a.isub(b, inline=False)), AB, funcs=[i64._wsub_fn],
             target=T_ADD, note="S8 WVf 본문 8 / 실행 23"),  # fmt: skip
    CostCase("r = x - y (새 값 wrap)", _op(lambda t, a, b: a - b), AB, target=T_ADD),
    CostCase("x.isub_sat(5) (상수 kh=0, S8 SK)", _op(lambda t, a, b: a.isub_sat(5)), A1, target=T_SATK),
    CostCase("x.isub_sat(2^32) (상수 kl=0)", _op(lambda t, a, b: a.isub_sat(1 << 32)), A1, target=T_SATK),
    CostCase("x.isub_sat(0x100000005) (상수 둘 다)", _op(lambda t, a, b: a.isub_sat(0x100000005)), A1, target=T_SATK),
    CostCase("x.isub_sat(y) (변수 포화, 공유 함수 — 기본)", _op(lambda t, a, b: a.isub_sat(b)), AB, funcs=[i64._ssub_fn],
             target=T_SATV, note="S8 SVf 본문 9 / 실행 25, war.py _subsat64 본문 27 / 실행 51"),  # fmt: skip
    CostCase("x.isub_sat(y, inline=True) (변수 포화, 인라인)", _op(lambda t, a, b: a.isub_sat(b, inline=True)), AB,
             target=T_SATV, note="S8 SVa 7 / 14"),  # fmt: skip
    CostCase("x.isub_sat(v32) (32비트 변수 포화, 기본)", lambda t: _q(t, "a").isub_sat(t.var("c")), AC, target=T_SATV),
    CostCase("x.isub_sat(v32, inline=True)", lambda t: _q(t, "a").isub_sat(t.var("c"), inline=True), AC, target=T_SATV),
    CostCase("r = sub_sat(x, y) (새 값, 기본)", _op(lambda t, a, b: i64.sub_sat(a, b)), AB, funcs=[i64._ssub_fn],
             target=T_SATV),  # fmt: skip
    CostCase("r = sub_sat(x, y, inline=True)", _op(lambda t, a, b: i64.sub_sat(a, b, inline=True)), AB,
             target={"exec": 30}, note="복사 + 인라인 포화"),  # fmt: skip
    CostCase("LSub(d, x, y) (CtrigAsm 별칭)", _op(lambda t, a, b: i64.LSub(_q(t, "d"), a, b)), AB),
    CostCase("x.ineg()", _op(lambda t, a, b: a.ineg()), A1),
    CostCase("r = -x", _op(lambda t, a, b: -a), A1),
    CostCase("x << y (대입)", _op(lambda t, a, b: a << b), AB),
    CostCase("x << 5 (상수 대입)", _op(lambda t, a, b: a << 5), A1),
    CostCase("참고: 소비 트리거만 (Trigger(Always))", lambda t: Trigger(conditions=[])),
    CostCase("x >= y (변수)", _cc(lambda t, a, b: a >= b), AB, note="준비 1 + 채우기 3 + 깃발 트리거 1 (+소비 1)"),
    CostCase("x > y (변수)", _cc(lambda t, a, b: a > b), AB),
    CostCase("x == y (변수)", _cc(lambda t, a, b: a == b), AB),
    CostCase("x != y (변수)", _cc(lambda t, a, b: a != b), AB),
    CostCase("x.sge(y) (부호 있는 변수)", _cc(lambda t, a, b: a.sge(b)), AB),
    CostCase("x >= v32", _cc(lambda t, a, b: a >= t.var("c")), AC),
    CostCase("x >= 0x100000005 (상수)", _cc(lambda t, a, b: a >= 0x100000005), A1),
    CostCase("x >= 2^32 (상수 lo 0)", _cc(lambda t, a, b: a >= (1 << 32)), A1, note="조건 하나, 트리거 0"),
    CostCase("x == 12800000000 (상수)", _cc(lambda t, a, b: a == 12800000000), A1),
    CostCase("x != 5 (상수)", _cc(lambda t, a, b: a != 5), A1),
    CostCase("x.slt(0) (부호 있는 상수)", _cc(lambda t, a, b: a.slt(0)), A1),
    CostCase("x.sge(-5) (부호 있는 상수)", _cc(lambda t, a, b: a.sge(-5)), A1),
    CostCase("fmt(x) (10진, f_lidec_to 본문 포함)", _op(lambda t, a, b: a.fmt()), A1, funcs=[i64._lidec_body], target=T_DEC,
             note="실행은 값에 따라 조금 다름"),  # fmt: skip
    CostCase("fmt(x, signed=True)", _op(lambda t, a, b: a.fmt(signed=True)), A1 + [put({}, "a", M64 - 4)],
             funcs=[i64._slidec_body], target=T_DEC),  # fmt: skip
    CostCase("lidec_to(상수 EPD, lo, hi)", _op(lambda t, a, b: i64.lidec_to(EPD(Db(24)), a.lo, a.hi)), A1,
             funcs=[i64._lidec_body], target=T_DEC),  # fmt: skip
    CostCase("arr[3] += 5 (상수 칸·상수 값)", lambda t: Int64Array(8).iadd(3, 5)),
    CostCase("arr.isub_sat(3, 0x100000005) (상수 칸·상수 값)", lambda t: Int64Array(8).isub_sat(3, 0x100000005)),
    CostCase("arr[3] >= 0x100000005 (상수 칸)", lambda t: Trigger(conditions=Int64Array(8).geitem(3, 0x100000005))),
    CostCase("arr[i] 읽기 (변수 칸)", lambda t: Int64Array(8)[t.var("i")], [{"i": 2}]),
    CostCase("arr[i] = y (변수 칸)", lambda t: Int64Array(8).set(t.var("i"), _q(t, "b")), [put({"i": 2}, "b", 5)]),
    CostCase("arr[i] += y (변수 칸, 읽고 쓰기)", lambda t: Int64Array(8).iadd(t.var("i"), _q(t, "b")), [put({"i": 2}, "b", 5)]),
    CostCase("arr[3] = y (상수 칸)", lambda t: Int64Array(8).set(3, _q(t, "b")), [put({}, "b", 5)]),
]

if PROTO is not None:
    COST_CASES += [
        CostCase("참고: 시제품 x += y", lambda t: _pq(t, "a").__iadd__(_pq(t, "b")), AB, funcs=[PROTO._add64]),
        CostCase("참고: 시제품 x -= y", lambda t: _pq(t, "a").__isub__(_pq(t, "b")), AB, funcs=[PROTO._sub64]),
        CostCase("참고: 시제품 x >= y (0/1 변수)", lambda t: Trigger(conditions=_pq(t, "a").__ge__(_pq(t, "b")).Exactly(1)), AB,
                 funcs=[PROTO._geu64]),  # fmt: skip
        CostCase("참고: 시제품 x >= 0x100000005", lambda t: Trigger(conditions=_pq(t, "a").__ge__(0x100000005).IsSet()), A1),
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
    ck = Checker("t_i64 (python)")
    eps = load_eps("i64_example")
    oks = [suite_vars(), suite_const()]
    oks.append(suite_misc())
    oks.append(suite_eps(eps))
    oks.append(suite_proto400())
    python_checks(ck)
    eps_checks(ck)
    ingame_emulate(ck)
    euddraft_builds(ck)
    bad_builds(ck)
    # 같은 작업 트리에서 다른 시험이 동시에 돌 수 있어, 이 시험이 만들 수 있는 것(i64·epScript 번역·맵)만 본다
    mine = [p for p in set(repo_artifacts()) - before if "i64" in p or "__epspy__" in p or p.endswith(".scx")]
    ck.eq("repo clean", sorted(mine), [])
    oks.append(ck.report())
    finish(*oks)


if __name__ == "__main__":
    main()
