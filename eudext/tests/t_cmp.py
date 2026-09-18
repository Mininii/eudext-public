"""`cmp` 차등 시험 (에뮬레이터): 부호 없음·부호 있음 비교, 구간, 부호 확장 읽기, epScript 예제.

- 모든 비교 함수 × 피연산자 조합(변수 V, EUDLightVariable M, 정수 K, 주소식 E) × 32비트 경계값 전 쌍 + 무작위.
- 결과를 여러 문맥에서 쓴다: EUDIf, EUDIf(neg), EUDNot(값), RawTrigger, EUDSCAnd/EUDSCOr(neg 포함),
  조건 목록 중첩, EUDTernary(neg 포함), EUDElseIf, EUDWhile(돌 때마다 다시 계산되는지).
- eudplib 0.81 변수끼리 연산자(`<` `>` `<=` `>=` `==` `!=`)의 경계값 확인(참고 묶음).
- epScript 예제(examples/cmp_example.eps)의 번역·에뮬레이터 실행·euddraft 빌드.

python tests/t_cmp.py
비용 표: python tools/cost.py tests/t_cmp.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import operator  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402

from eudplib import (  # noqa: E402
    EPD,
    Add,
    Condition,
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
    EUDVariable,
    EUDWhile,
    Forward,
    RawTrigger,
    SeqCompute,
    SetTo,
    Trigger,
    f_wread_epd,
)

from eudext import _compat, cmp  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing.harness import EDGES32, Suite  # noqa: E402
from eudext.testing import emu  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
SIGN = 0x80000000
OPS = ("ge", "le", "gt", "lt", "eq", "ne", "sge", "sle", "sgt", "slt")
FN = {op: getattr(cmp, op) for op in OPS}
PYOP = {"ge": operator.ge, "le": operator.le, "gt": operator.gt, "lt": operator.lt, "eq": operator.eq, "ne": operator.ne}
K_SET = EDGES32 + (0x12345678, 0xFFFFFF00, 0x00000100)
NEG_LIT = {0xFFFFFFFF, 0x80000001, 0xFFFFFF00}  # 부호 없는 함수에도 음수 리터럴로 넘겨 본다
RD_ADDR = 0x58A364 + 4 * 12 * 200  # 데스 표 유닛 200·P1 (읽기 시험용 빈 칸)
RD_EPD = (RD_ADDR - 0x58A364) // 4
EX = os.path.join(_common.PKG, "examples")


def s32(x):
    x &= M32
    return x - (1 << 32) if x & SIGN else x


def ref(op, a, b):
    a &= M32
    b &= M32
    if op[0] == "s":
        a, b, op = s32(a), s32(b), op[1:]
    return int(PYOP[op](a, b))


def loop_ref(op, seq):
    n = 0
    for x, y in seq:
        if not ref(op, x, y):
            break
        n += 1
    return n


def ctx_expect(r0, level, loop=None):
    e = {"r": r0}
    if level >= 1:
        e.update(rn=1 - r0, rnot=1 - r0, rraw=r0)
    if level >= 2:
        e.update(rand=r0, randn=1 - r0, rand2=r0, rand2n=1 - r0, ror=r0, rorn=1 - r0, rlist=r0, rt=r0, rtn=1 - r0, relif=r0)
    if loop is not None:
        e["loop"] = loop
    return e


# ---------------------------------------------------------------------------------------------
# 케이스 부품
# ---------------------------------------------------------------------------------------------


def _dst(h):
    return h if isinstance(h, EUDVariable) else EPD(h.getValueAddr())


def _set(h, src):
    SeqCompute([(_dst(h), SetTo, src)])


def _addk(h, k):
    SeqCompute([(_dst(h), Add, k)])


def _holder(kind):
    return EUDVariable() if kind == "V" else EUDLightVariable()


def _opd(t, kind, name, k=None):
    """V: 입력 변수, M: 입력을 옮긴 EUDLightVariable, K: 정수 리터럴, E: 정수로 정한 Forward.

    eudplib 0.81 의 상수식 오프셋은 i32 라서 `Forward << 0x80000000` 은 빌드 때 오류다 → 음수로 넣는다.
    """
    if kind == "V":
        return t.var(name)
    if kind == "M":
        lv = EUDLightVariable()
        _set(lv, t.var(name))
        return lv
    if kind == "K":
        return k
    f = Forward()
    f << s32(k)
    return f


def _ifval(t, name, fn, neg=False):
    v = t.var(name)
    if EUDIf()(fn(), neg=neg):  # EUDIf() 를 먼저 만들고 조건을 부른다 (epScript 번역과 같은 순서)
        v << 1
    if EUDElse()():
        v << 0
    EUDEndIf()


def contexts(t, mk, level):
    """mk() 는 부를 때마다 새 조건을 만든다. level 0 = EUDIf 만, 1 = +neg·EUDNot·RawTrigger, 2 = 전부."""
    z = t.var("z")  # 늘 0
    _ifval(t, "r", mk)
    if level == 0:
        return
    _ifval(t, "rn", mk, neg=True)
    nv = EUDNot(mk())  # 값 자리 (epScript `var r = !c ? …`)
    _ifval(t, "rnot", lambda: nv)
    rr = t.var("rraw")
    DoActions(rr.SetNumber(0))
    RawTrigger(conditions=mk(), actions=rr.SetNumber(1))
    if level == 1:
        return
    _ifval(t, "rand", lambda: EUDSCAnd()(z.Exactly(0))(mk())())
    _ifval(t, "randn", lambda: EUDSCAnd()(z.Exactly(0))(mk(), neg=True)())
    _ifval(t, "rand2", lambda: EUDSCAnd()(mk())(z.Exactly(0))())
    _ifval(t, "rand2n", lambda: EUDSCAnd()(mk(), neg=True)(z.Exactly(0))())
    _ifval(t, "ror", lambda: EUDSCOr()(z.Exactly(1))(mk())())
    _ifval(t, "rorn", lambda: EUDSCOr()(z.Exactly(1))(mk(), neg=True)())
    _ifval(t, "rlist", lambda: [z.Exactly(0), [mk()]])
    t.out("rt", EUDTernary(mk())(1)(0))
    t.out("rtn", EUDTernary(mk(), neg=True)(1)(0))
    re_ = t.var("relif")
    if EUDIf()(z.Exactly(1)):
        re_ << 2
    if EUDElseIf()(mk()):
        re_ << 1
    if EUDElse()():
        re_ << 0
    EUDEndIf()


def _loop(t, cond, steps):
    """EUDWhile()(cond()) 를 최대 3번 돈다. steps[i](i=1,2) 가 다음 값을 넣는다. loop = 참이었던 횟수."""
    cnt, i = t.var("loop"), EUDVariable()
    DoActions(cnt.SetNumber(0), i.SetNumber(0))
    steps[0]()
    if EUDWhile()(cond()):
        DoActions(cnt.AddNumber(1), i.AddNumber(1))
        EUDBreakIf(i.Exactly(3))
        for n in (1, 2):
            if EUDIf()(i.Exactly(n)):
                steps[n]()
            EUDEndIf()
    EUDEndWhile()


def pair_case(s, op, kx, ky, level=2):
    fn = FN[op]

    @s.case("pair_%s_%s%s" % (op, kx, ky))
    def _(t):
        x, y = _opd(t, kx, "a"), _opd(t, ky, "b")
        contexts(t, lambda: fn(x, y), level)
        a, b = t.var("a"), t.var("b")
        hx, hy = _holder(kx), _holder(ky)

        def st2():
            _set(hx, a)
            _addk(hx, SIGN)
            _set(hy, b)

        _loop(t, lambda: fn(hx, hy), [lambda: (_set(hx, a), _set(hy, b)), lambda: (_set(hx, b), _set(hy, a)), st2])

    def expect(a, b):
        seq = [(a, b), (b, a), ((a + SIGN) & M32, b)]
        return ctx_expect(ref(op, a, b), level, loop_ref(op, seq))

    return "pair_%s_%s%s" % (op, kx, ky), expect


def same_case(s, op, kx):
    fn = FN[op]
    name = "same_%s_%s" % (op, kx)

    @s.case(name)
    def _(t):
        x = _opd(t, kx, "a")
        contexts(t, lambda: fn(x, x), 1)

    return name, lambda a: ctx_expect(ref(op, a, a), 1)


def const_case(s, op, kv, kc, k, var_left, level):
    fn = FN[op]
    lit = s32(k) if (op[0] == "s" or k in NEG_LIT) else k
    side = "%s%s" % ((kv, kc) if var_left else (kc, kv))
    name = "k_%s_%s_%08X" % (op, side, k)

    @s.case(name)
    def _(t):
        v = _opd(t, kv, "a")
        c = _opd(t, kc, None, lit)
        mk = (lambda: fn(v, c)) if var_left else (lambda: fn(c, v))
        contexts(t, mk, level)
        a = t.var("a")
        h = _holder(kv)

        def st2():
            _set(h, a)
            _addk(h, SIGN)

        cond = (lambda: fn(h, c)) if var_left else (lambda: fn(c, h))
        _loop(t, cond, [lambda: _set(h, a), lambda: _set(h, k), st2])

    def expect(a):
        seq = [(a, k), (k, k), ((a + SIGN) & M32, k)]
        if not var_left:
            seq = [(q, p) for p, q in seq]
        r0 = ref(op, a, k) if var_left else ref(op, k, a)
        return ctx_expect(r0, level, loop_ref(op, seq))

    return name, expect


# ---------------------------------------------------------------------------------------------
# 묶음 1: 변수끼리 + 같은 객체 + eudplib 0.81 참고
# ---------------------------------------------------------------------------------------------

EUDPLIB_OPS = {
    "lt": lambda a, b: a < b,
    "gt": lambda a, b: a > b,
    "le": lambda a, b: a <= b,
    "ge": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
}


def suite_pairs():
    s = Suite("t_cmp 변수끼리")
    pairs, sames = [], []
    for op in OPS:
        for kx in "VM":
            for ky in "VM":
                pairs.append(pair_case(s, op, kx, ky))
            sames.append(same_case(s, op, kx))
    for op, f in EUDPLIB_OPS.items():

        @s.case("eudplib081_" + op)
        def _(t, f=f):
            t.flag("r", f(t.var("a"), t.var("b")))

    s.build()
    ab = {"a": EDGES32, "b": EDGES32}
    for name, expect in pairs:
        s.diff(name, expect, ab, n=100)
    for name, expect in sames:
        s.diff(name, expect, {"a": EDGES32}, n=10)
    for op in EUDPLIB_OPS:
        s.diff("eudplib081_" + op, lambda a, b, op=op: {"r": ref(op, a, b)}, ab, n=40)
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 2: 상수와의 비교 (변수 V·칸 M × 정수 K)
# ---------------------------------------------------------------------------------------------


def suite_const(kv):
    s = Suite("t_cmp 상수(%s)" % kv)
    cases = []
    for op in OPS:
        for k in K_SET:
            cases.append((const_case(s, op, kv, "K", k, True, 2), k))
            cases.append((const_case(s, op, kv, "K", k, False, 1), k))
    s.build()
    for (name, expect), k in cases:
        extra = tuple(sorted({(k - 1) & M32, k, (k + 1) & M32, k ^ SIGN}))
        s.diff(name, expect, {"a": EDGES32 + extra}, n=12)
    return s.report()


# ---------------------------------------------------------------------------------------------
# 묶음 3: 주소식·상수끼리·구간·읽기·epScript
# ---------------------------------------------------------------------------------------------

E_SET = (0, 0x7FFFFFFF, 0x80000000, M32, 0xFFFFFFF0)
BETWEEN_K = (0, 5, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFB)
KK_SET = (0, 1, 0x7FFFFFFF, 0x80000000, M32)
VB = {  # between 변수 끝: (x, lo, hi) 종류. K 는 고정 상수, "x" 는 x 와 같은 객체, "=" 는 lo 와 같은 객체
    "VVV": ("V", "V", "V"),
    "VKV": ("V", "K", "V"),
    "VVK": ("V", "V", "K"),
    "MVV": ("M", "V", "V"),
    "VMV": ("V", "M", "V"),
    "VVM": ("V", "V", "M"),
    "KVV": ("K", "V", "V"),
    "VEV": ("V", "E", "V"),
    "MMM": ("M", "M", "M"),
    "VV=": ("V", "V", "="),
    "VxV": ("V", "x", "V"),
    "VVx": ("V", "V", "x"),
}
VB_K = {False: (5, 0x80000000, 0x1234), True: (0xFFFFFFF0, 16, 0xFFFFFF00)}  # (lo 상수, hi 상수, x 상수)


def between_ref(x, lo, hi, signed):
    if signed:
        x, lo, hi = s32(x), s32(lo), s32(hi)
    return int(lo <= x <= hi)


def load_eps_example():
    """예제 eps 를 작업 폴더에 복사해 EPSLoader 로 불러온다(__epspy__ 가 작업 폴더에 생긴다)."""
    d = os.path.join(_common.WORK, "t_cmp", "eps")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "cmp_example.eps")
    shutil.copy2(os.path.join(EX, "cmp_example.eps"), p)
    name = "cmp_example_eps"
    import types

    mod = types.ModuleType(name)
    loader = EPSLoader(name, p)
    mod.__loader__ = loader
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


def suite_misc(eps):
    s = Suite("t_cmp 주소식·구간·읽기·epScript")
    checks = []  # (name, expect_fn, inputs) — diff 로 볼 것
    once = []  # (name, inputs, expect) — check 로 볼 것

    # 주소식(E) 과 변수·칸
    for op in OPS:
        for k in E_SET:
            for kv in "VM":
                checks.append((*const_case(s, op, kv, "E", k, True, 1), {"a": EDGES32}))
                checks.append((*const_case(s, op, kv, "E", k, False, 1), {"a": EDGES32}))

    # 상수끼리 (K·E 섞기) — 입력 없음
    for op in OPS:
        fn = FN[op]
        for i, (p, q) in enumerate([(p, q) for p in KK_SET for q in KK_SET]):
            for form in ("KK", "EK", "KE", "EE"):
                if form != "KK" and i % 2:
                    continue
                name = "kk_%s_%s_%08X_%08X" % (op, form, p, q)

                @s.case(name)
                def _(t, fn=fn, p=p, q=q, form=form):
                    x = _opd(t, form[0], None, p)
                    y = _opd(t, form[1], None, q)
                    contexts(t, lambda: fn(x, y), 1)

                once.append((name, {}, ctx_expect(ref(op, p, q), 1)))
        for form in ("E", "K"):
            name = "kk_%s_same%s" % (op, form)

            @s.case(name)
            def _(t, fn=fn, form=form):
                x = _opd(t, form, None, 0x80000000)
                contexts(t, lambda: fn(x, x), 1)

            once.append((name, {}, ctx_expect(ref(op, 1, 1), 1)))

    # between: 상수 구간
    for signed in (False, True):
        for kx in "VM":
            for lo in BETWEEN_K:
                for hi in BETWEEN_K:
                    name = "btw_%s_%s_%08X_%08X" % ("s" if signed else "u", kx, lo, hi)
                    L, H = (s32(lo), s32(hi)) if signed else (lo, hi)

                    @s.case(name)
                    def _(t, kx=kx, L=L, H=H, signed=signed):
                        x = _opd(t, kx, "a")
                        contexts(t, lambda: cmp.between(x, L, H, signed=signed), 1)

                    extra = tuple({lo, hi, (lo - 1) & M32, (hi + 1) & M32})
                    checks.append(
                        (name, lambda a, lo=lo, hi=hi, signed=signed: ctx_expect(between_ref(a, lo, hi, signed), 1), {"a": EDGES32 + extra})
                    )
    # between: 변수 끝
    for signed in (False, True):
        klo, khi, kx_ = VB_K[signed]
        for tag, (tx, tl, th) in VB.items():
            name = "btwv_%s_%s" % ("s" if signed else "u", tag)

            @s.case(name)
            def _(t, tx=tx, tl=tl, th=th, signed=signed, klo=klo, khi=khi, kx_=kx_):
                x = _opd(t, tx, "a", s32(kx_) if signed else kx_)
                lo = x if tl == "x" else _opd(t, tl, "l", s32(klo) if signed else klo)
                if th == "=":
                    hi = lo
                elif th == "x":
                    hi = x
                else:
                    hi = _opd(t, th, "h", s32(khi) if signed else khi)
                contexts(t, lambda: cmp.between(x, lo, hi, signed=signed), 2)

            def expect(a=None, l=None, h=None, tx=tx, tl=tl, th=th, signed=signed, klo=klo, khi=khi, kx_=kx_):  # noqa: E741
                xv = kx_ if tx == "K" else a
                lv = xv if tl == "x" else (klo if tl in "KE" else l)
                hv = lv if th == "=" else xv if th == "x" else (khi if th in "KE" else h)
                return ctx_expect(between_ref(xv, lv, hv, signed), 2)

            inputs = {}
            if tx != "K":
                inputs["a"] = EDGES32
            if tl in "VM":
                inputs["l"] = EDGES32
            if th in "VM":
                inputs["h"] = EDGES32
            checks.append((name, expect, inputs))

    # 부호 확장 읽기
    for subp in range(4):
        for fname in ("wread", "bread"):
            name = "%s_c%d" % (fname, subp)
            f = cmp.f_wread_signed if fname == "wread" else cmp.f_bread_signed

            @s.case(name)
            def _(t, f=f, subp=subp):
                t.out("r", f(RD_EPD, subp))

    for fname in ("wread", "bread"):
        f = cmp.wread_signed if fname == "wread" else cmp.bread_signed

        @s.case(fname + "_var")
        def _(t, f=f):
            t.out("r", f(t.var("e"), t.var("sp")))

        @s.case(fname + "_ret")
        def _(t, f=f):
            r = EUDVariable()
            got = f(RD_EPD, t.var("sp"), ret=[r])
            t.out("r", r)
            t.out("same", 1 if got is r else 0)

        @s.case(fname + "_ret_c")
        def _(t, f=f):
            r = EUDVariable()
            got = f(RD_EPD, 1, ret=[r])
            t.out("r", r)
            t.out("same", 1 if got is r else 0)

    @s.case("wread_ref_eudplib")
    def _(t):
        t.out("r", f_wread_epd(RD_EPD, 1))

    # epScript 예제 함수
    @s.case("eps_lt01")
    def _(t):
        t.out("r", eps.f_lt01(t.var("a"), t.var("b")))

    @s.case("eps_sge01")
    def _(t):
        t.out("r", eps.f_sge01(t.var("a"), t.var("b")))

    @s.case("eps_same01")
    def _(t):
        t.out("r", eps.f_same01(t.var("a"), t.var("b")))

    @s.case("eps_clamp")
    def _(t):
        t.out("r", eps.f_clamp_signed(t.var("a"), t.var("l"), t.var("h")))

    @s.case("eps_in_box")
    def _(t):
        t.out("r", eps.f_in_box(t.var("a"), t.var("b")))

    @s.case("eps_count_up")
    def _(t):
        t.out("r", eps.f_count_up(t.var("a")))

    @s.case("eps_selftest")
    def _(t):
        t.out("r", eps.f_selftest())

    @s.case("eps_read")
    def _(t):
        t.out("r16", eps.f_read_i16(t.var("e"), t.var("sp")))
        t.out("r8", eps.f_read_i8(t.var("e"), t.var("sp")))

    s.build()
    for name, expect, inputs in checks:
        s.diff(name, expect, inputs, n=20)
    for name, inputs, expect in once:
        s.check(name, inputs, expect)

    # 읽기: 칸 두 개(RD_ADDR, +4)에 바이트를 쓰고 읽는다
    m = s.machine
    pats = [(0, 0), (0x7F7F7F7F, 0x80808080), (0x80FF7F01, 0x017F80FF), (M32, 0), (0x00800080, 0x80008000), (0x12345678, 0x9ABCDEF0)]
    for d0, d1 in pats:
        m.setdw(RD_ADDR, d0)
        m.setdw(RD_ADDR + 4, d1)
        data = d0.to_bytes(4, "little") + d1.to_bytes(4, "little")

        def w(sp):
            return int.from_bytes(data[sp : sp + 2], "little", signed=True) & M32

        def b(sp):
            return int.from_bytes(data[sp : sp + 1], "little", signed=True) & M32

        for sp in range(4):
            s.check("wread_c%d" % sp, {}, {"r": w(sp)}, label="c%d 0x%08X_%08X" % (sp, d0, d1))
            s.check("bread_c%d" % sp, {}, {"r": b(sp)}, label="c%d 0x%08X_%08X" % (sp, d0, d1))
            s.check("wread_var", {"e": RD_EPD, "sp": sp}, {"r": w(sp)})
            s.check("bread_var", {"e": RD_EPD, "sp": sp}, {"r": b(sp)})
            s.check("wread_ret", {"sp": sp}, {"r": w(sp), "same": 1})
            s.check("bread_ret", {"sp": sp}, {"r": b(sp), "same": 1})
            s.check("eps_read", {"e": RD_EPD, "sp": sp}, {"r16": w(sp), "r8": b(sp)})
        s.check("wread_ret_c", {}, {"r": w(1), "same": 1})
        s.check("bread_ret_c", {}, {"r": b(1), "same": 1})
        s.check("wread_ref_eudplib", {}, {"r": w(1) & 0xFFFF})

    # epScript 예제
    ab = {"a": EDGES32, "b": EDGES32}
    s.diff("eps_lt01", lambda a, b: {"r": ref("lt", a, b)}, ab, n=40)
    s.diff("eps_sge01", lambda a, b: {"r": ref("sge", a, b)}, ab, n=40)
    s.diff("eps_same01", lambda a, b: {"r": ref("eq", a, b)}, ab, n=40)

    def clamp(a, l, h):  # noqa: E741
        if s32(a) < s32(l):
            return {"r": l}
        if s32(a) > s32(h):
            return {"r": h}
        return {"r": a}

    s.diff("eps_clamp", clamp, {"a": EDGES32, "l": (0, 0xFFFFFF9C, 5), "h": (0, 100, 0x7FFFFFFF)}, n=40)
    box = (0, 16, 17, 0xFFFFFFF0, 0xFFFFFFEF, 0x7FFFFFFF, 0x80000000, M32)
    s.diff(
        "eps_in_box",
        lambda a, b: {"r": int(-16 <= s32(a) <= 16 and -16 <= s32(b) <= 16)},
        {"a": box, "b": box},
        n=40,
    )
    for n in (0, 1, 2, 7, 20):
        s.check("eps_count_up", {"a": n}, {"r": n})
    s.check("eps_selftest", {}, {"r": 15}, label="인게임 점검과 같은 값")
    return s.report()


# ---------------------------------------------------------------------------------------------
# 파이썬 쪽 판정
# ---------------------------------------------------------------------------------------------


def is_nagatable_cond(c):
    """eudplib 이 제자리 부정(`negate_cond`)을 시도할 조건인가 — cmp 가 만드는 Memory 조건 기준(amount 가 정수)."""
    return isinstance(c, Condition) and isinstance(c.fields[2], int) and c.fields[4] in (0, 1)


def python_checks(ck):
    with _compat.isolated_scope():  # cmp 가 앞 계산 트리거를 내므로 트리거 범위 안에서 (만든 트리거는 버려진다)
        _python_checks(ck)


def _python_checks(ck):
    v, w = EUDVariable(), EUDVariable()
    lv = EUDLightVariable()
    for op in OPS:
        for p in KK_SET:
            for q in KK_SET:
                c = FN[op](p, q)
                ck.true(
                    "fold %s(0x%X, 0x%X)" % (op, p, q),
                    isinstance(c, Condition) and c.fields[5] == (22 if ref(op, p, q) else 23),
                )
        ck.true("alias %s" % op, FN[op] is getattr(cmp, "f_" + op))
        ck.true("fresh %s" % op, FN[op](v, 5) is not FN[op](v, 5))
    ck.true("alias between", cmp.between is cmp.f_between)
    ck.true("alias wread", cmp.wread_signed is cmp.f_wread_signed and cmp.bread_signed is cmp.f_bread_signed)
    ck.eq("__all__", sorted(cmp.__all__), sorted(set(cmp.__all__)))
    for name in cmp.__all__:
        ck.true("__all__ %s" % name, hasattr(cmp, name))
    # 입력 검사
    ck.raises("K 넘침", EudextError, cmp.ge, v, 1 << 32)
    ck.raises("K 음수 넘침", EudextError, cmp.sge, v, -(1 << 31) - 1)
    ck.raises("None", EudextError, cmp.lt, v, None)
    ck.raises("float", EudextError, cmp.lt, v, 1.5)
    ck.raises("str", EudextError, cmp.eq, "a", v)
    ck.raises("LightBool", EudextError, cmp.ge, EUDLightBool(), 1)
    ck.raises("Condition", EudextError, cmp.ge, v.Exactly(1), 1)
    ck.raises("between signed", EudextError, cmp.between, v, 0, 1, signed=1)
    ck.raises("wread ret", EudextError, cmp.f_wread_signed, 0, 0, ret=[5])
    ck.raises("bread ret", EudextError, cmp.f_bread_signed, 0, 0, ret=v)
    # 경계 접기
    ck.eq("gt(x, M32) = Never", cmp.gt(v, M32).fields[5], 23)
    ck.eq("lt(x, 0) = Never", cmp.lt(v, 0).fields[5], 23)
    ck.eq("ge(x, 0) = Always", cmp.ge(v, 0).fields[5], 22)
    ck.eq("le(x, -1) = Always", cmp.le(v, -1).fields[5], 22)
    ck.eq("sgt(x, INT_MAX) = Never", cmp.sgt(v, 0x7FFFFFFF).fields[5], 23)
    ck.eq("slt(x, INT_MIN) = Never", cmp.slt(v, -(1 << 31)).fields[5], 23)
    ck.eq("sge(x, INT_MIN) = Always", cmp.sge(lv, -(1 << 31)).fields[5], 22)
    ck.eq("between lo>hi = Never", cmp.between(v, 5, 4).fields[5], 23)
    ck.eq("between signed lo>hi = Never", cmp.between(v, 1, -1, signed=True).fields[5], 23)
    ck.eq("between 전체 = Always", cmp.between(v, 0, M32).fields[5], 22)
    ck.eq("same ge", cmp.ge(v, v).fields[5], 22)
    ck.eq("same ne", cmp.ne(lv, lv).fields[5], 23)
    # 모양: 상수는 트리거 없이 조건 목록
    ck.true("sge(x, 5) 목록 2개", isinstance(cmp.sge(v, 5), list) and len(cmp.sge(v, 5)) == 2)
    ck.true("gt 변수끼리 목록 2개", isinstance(cmp.gt(v, w), list))
    # 채운 조건은 제자리 부정이 안 되고, 자기 칸 조건은 된다
    ck.true("ge vv 부정 불가", not is_nagatable_cond(cmp.ge(v, w)))
    ck.true("eq vv 부정 불가", not is_nagatable_cond(cmp.eq(v, w)))
    ck.true("sge vv 부정 불가", not is_nagatable_cond(cmp.sge(v, w)))
    ck.true("ne vv 부정 가능", is_nagatable_cond(cmp.ne(v, w)))
    ck.true("ne vk 부정 가능", is_nagatable_cond(cmp.ne(v, 5)))
    ck.true("sge(x,-5) 부정 가능", is_nagatable_cond(cmp.sge(v, -5)))
    ck.true("sge(lv,-5) 부정 가능(깃발)", is_nagatable_cond(cmp.sge(lv, -5)))
    with open(cmp.__file__, encoding="utf-8") as f:
        ck.true("_compat 밖 비공개 API 없음", "from eudplib." not in f.read())


# ---------------------------------------------------------------------------------------------
# epScript 번역과 euddraft 빌드
# ---------------------------------------------------------------------------------------------

ARTIFACTS = ("__pycache__", "__epspy__")


def repo_artifacts():
    found = []
    for dirpath, dirnames, filenames in os.walk(_common.PKG):
        rel = os.path.relpath(dirpath, _common.PKG)
        if rel.startswith("docs"):
            continue
        for d in dirnames:
            if d in ARTIFACTS:
                found.append(os.path.join(rel, d))
        for f in filenames:
            if f.endswith((".scx", ".pyc")) and not (rel == "testing" and f == "base.scx"):
                found.append(os.path.join(rel, f))
    return found


def eps_checks(ck):
    with open(os.path.join(EX, "cmp_example.eps"), encoding="utf-8") as f:
        src = f.read()
    out, nerr = _compat.eps_compile("cmp_example.eps", src)
    ck.eq("eps 오류 수", nerr, 0)
    ck.true("eps 번역", out is not None)
    if out:
        for needle in (
            "from eudext import cmp as cmp",
            "cmp.f_lt(",
            "cmp.f_sge(",
            "cmp.f_slt(",
            "cmp.f_sgt(",
            "cmp.f_between(",
            "signed=True",
            "cmp.f_ne(",
            "cmp.f_wread_signed(",
            "cmp.f_bread_signed(",
            "EUDTernary(cmp.f_lt(",
        ):
            ck.true("eps 번역에 %s" % needle, needle in out)
    # 안 되는 모양 (문서 안내가 맞는지)
    bad = "import eudext.cmp as cmp;\nfunction f(a, b) { return cmp.lt(a, b); }\n"
    out2, _n = _compat.eps_compile("bad.eps", bad)
    ck.true("return cmp.lt(a, b) 는 조건을 그대로 반환", out2 is not None and "EUDReturn(cmp.f_lt(a, b))" in out2)


def euddraft_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    work = os.path.join(_common.WORK, "t_cmp", "euddraft")
    eds, out_map = build.prepare_eds(os.path.join(EX, "cmp_example.eds"), work)
    r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, "cmp_example.log"))
    print("  " + r.summary())
    ck.true("euddraft ok", r.ok, r.log[-2000:])
    ck.true("euddraft freeze off", not r.freeze)
    ck.true("euddraft eps", '[epScript] Compiling "cmp_example.eps"' in r.log, r.log[-1000:])
    ck.true("epspy in work", os.path.isfile(os.path.join(work, "__epspy__", "cmp_example.py")))


def bad_return_build(ck):
    """문서 안내 확인: epScript `return cmp.lt(a, b);`·`var r = cmp.lt(a, b);` 는 빌드 오류(Orphan condition).

    빌드 실패가 뒤 빌드에 영향을 주지 않게 모든 에뮬레이터 시험 뒤에 부른다.
    """
    src = (
        "import eudext.cmp as cmp;\n"
        "function f(a, b) { return cmp.lt(a, b); }\n"
        "function g(a, b) { var r = cmp.ge(a, b); return r; }\n"
    )
    out, nerr = _compat.eps_compile("bad_return.eps", src)
    ck.true("bad eps 번역", out is not None and nerr == 0)
    ns = {}
    exec(compile(out, "bad_return.eps.py", "exec"), ns)  # noqa: S102 — 시험용 번역문
    for fn in ("f_f", "f_g"):
        from eudplib import CompressPayload, LoadMap

        from eudext.testing.harness import BASE_MAP

        LoadMap(BASE_MAP)
        CompressPayload(True)

        def body(fn=fn):
            ns[fn](EUDVariable(), EUDVariable())

        try:
            emu.Program(body).build()
            ck.true("%s 빌드 오류" % fn, False, "빌드가 됐다")
        except Exception as e:  # noqa: BLE001
            ck.true("%s 빌드 오류" % fn, "Orphan condition" in str(e), repr(e))


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py) — 조건을 담는 소비 트리거 1개(Trigger)가 호출·실행 수에 들어 있다
# ---------------------------------------------------------------------------------------------


def _arg(t, a):
    if a in ("a", "b", "l", "h"):
        return t.var(a)
    if a in ("La", "Lb", "Ll", "Lh"):
        return EUDLightVariable()
    return a


def _cc(fn, *args, **kw):
    def build(t):
        Trigger(conditions=fn(*[_arg(t, a) for a in args], **kw))

    return build


def _cv(fn, *args, **kw):
    def build(t):
        fn(*[_arg(t, a) for a in args], **kw)

    return build


C0 = {"call": 1}  # 상수 비교: 트리거 0 + 소비 1
C2 = {"call": 3}  # 상수 비교 목표 상한: 0~2 + 소비 1
V3 = {"call": 4}  # 변수끼리 목표 상한: 2~3 + 소비 1
AB = [{"a": 3, "b": 5}, {"a": 5, "b": 3}]
A1 = [{"a": 3}, {"a": 0xFFFFFFF0}]

COST_CASES = [
    CostCase("참고: 소비 트리거만 (Trigger(Always))", _cc(lambda: [])),
    CostCase("ge(변수, 상수)", _cc(cmp.ge, "a", 5), A1, target=C0),
    CostCase("gt(변수, 상수)", _cc(cmp.gt, "a", 5), A1, target=C0),
    CostCase("eq(변수, 상수)", _cc(cmp.eq, "a", 5), A1, target=C0),
    CostCase("ne(변수, 0)", _cc(cmp.ne, "a", 0), A1, target=C0),
    CostCase("ne(변수, 5)", _cc(cmp.ne, "a", 5), A1, target=C2, note="자기 칸 ← a−5"),
    CostCase("ne(칸, 5)", _cc(cmp.ne, "La", 5), [{}], target=C2, note="자기 칸 깃발"),
    CostCase("sge(변수, 5)", _cc(cmp.sge, "a", 5), A1, target=C0, note="조건 목록 2개"),
    CostCase("sge(변수, -5)", _cc(cmp.sge, "a", -5), A1, target=C2, note="OR → 자기 칸 ← a−0x80000000"),
    CostCase("sge(칸, -5)", _cc(cmp.sge, "La", -5), [{}], target=C2, note="OR → 자기 칸 깃발"),
    CostCase("slt(변수, 0)", _cc(cmp.slt, "a", 0), A1, target=C0),
    CostCase("between(변수, 5, 100)", _cc(cmp.between, "a", 5, 100), A1, target=C0),
    CostCase("between(변수, -16, 16, signed)", _cc(cmp.between, "a", -16, 16, signed=True), A1, target=C2),
    CostCase("between(칸, -16, 16, signed)", _cc(cmp.between, "La", -16, 16, signed=True), [{}], target=C2),
    CostCase("ge(변수, 변수)", _cc(cmp.ge, "a", "b"), AB, target=V3),
    CostCase("gt(변수, 변수)", _cc(cmp.gt, "a", "b"), AB, target=V3),
    CostCase("lt(변수, 변수)", _cc(cmp.lt, "a", "b"), AB, target=V3),
    CostCase("eq(변수, 변수)", _cc(cmp.eq, "a", "b"), AB, target=V3),
    CostCase("ne(변수, 변수)", _cc(cmp.ne, "a", "b"), AB, target=V3),
    CostCase("sge(변수, 변수)", _cc(cmp.sge, "a", "b"), AB, target=V3),
    CostCase("sgt(변수, 변수)", _cc(cmp.sgt, "a", "b"), AB, target=V3),
    CostCase("ge(칸, 변수)", _cc(cmp.ge, "La", "b"), [{"b": 3}], target=V3),
    CostCase("gt(칸, 변수)", _cc(cmp.gt, "La", "b"), [{"b": 3}], target=V3),
    CostCase("ne(칸, 변수)", _cc(cmp.ne, "La", "b"), [{"b": 3}], target=V3, note="자기 칸 깃발"),
    CostCase("sge(칸, 변수)", _cc(cmp.sge, "La", "b"), [{"b": 3}, {"b": 0xFFFFFFF0}], target=V3,
             note="부호 없는 비교 + 부호 보정 트리거 2 + 깃발 (드문 조합)"),
    CostCase("ge(칸, 칸)", _cc(cmp.ge, "La", "Lb"), [{}], note="한쪽을 f_dwread_epd 로 읽음 (eudplib 읽기 본문은 이미 있음)"),
    CostCase("between(변수, 변수, 변수)", _cc(cmp.between, "a", "l", "h"), [{"a": 3, "l": 1, "h": 5}], target=V3),
    CostCase("between(변수, 변수, 변수, signed)", _cc(cmp.between, "a", "l", "h", signed=True), [{"a": 3, "l": 1, "h": 5}], target=V3),
    CostCase("참고: eudplib f_wread_epd(상수 epd, 0)", _cv(f_wread_epd, RD_EPD, 0)),
    CostCase("참고: eudplib f_wread_epd(변수 epd, 변수 subp)", _cv(f_wread_epd, "a", "b"), [{"a": RD_EPD, "b": 1}],
             note="eudplib 공유 본문(처음 한 번) 포함"),
    CostCase("f_wread_signed(상수 epd, 0)", _cv(cmp.f_wread_signed, RD_EPD, 0), note="읽기 + 부호 확장 1"),
    CostCase("f_wread_signed(변수 epd, 변수 subp)", _cv(cmp.f_wread_signed, "a", "b"), [{"a": RD_EPD, "b": 1}]),
    CostCase("f_bread_signed(상수 epd, 2)", _cv(cmp.f_bread_signed, RD_EPD, 2)),
    CostCase("참고: eudplib `a < b` (변수)", _cc(lambda a, b: a < b, "a", "b"), AB),
    CostCase("참고: eudplib `a >= b` (변수)", _cc(lambda a, b: a >= b, "a", "b"), AB, note="소비 때 채움"),
    CostCase("참고: eudplib `a == b` (변수)", _cc(lambda a, b: a == b, "a", "b"), AB, note="소비 때 채움"),
    CostCase("참고: eudplib `a != b` (변수)", _cc(lambda a, b: a != b, "a", "b"), AB),
    CostCase("참고: eudplib `a != 5`", _cc(lambda a: a != 5, "a"), A1),
]


def main():
    before = set(repo_artifacts())
    ck = Checker("t_cmp (python)")
    eps = load_eps_example()
    oks = [suite_pairs(), suite_const("V"), suite_const("M"), suite_misc(eps)]
    python_checks(ck)
    eps_checks(ck)
    euddraft_build(ck)
    bad_return_build(ck)
    ck.eq("repo clean", sorted(set(repo_artifacts()) - before), [])
    oks.append(ck.report())
    finish(*oks)


if __name__ == "__main__":
    main()
