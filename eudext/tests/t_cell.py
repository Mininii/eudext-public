"""eudext.cell 시험 (WP2, DESIGN 4.3).

python tests/t_cell.py

- 쓰기: 대입·덧셈·wrap 뺄셈·포화 뺄셈(연산자·메서드·epScript 통로·CtrigAsm 이름 액션)을 값 종류
  (정수 K·주소식 E·변수 V·EUDLightVariable M·Cell C·같은 칸 S)마다 파이썬 참조와 경계값·무작위 차등.
- 읽기·생성: read/v/ret, Cell(상수·주소식·변수·칸), Cell.at, CreateCcode(s), 트리거 수.
- 조건: 비교 연산자·AtLeast 류·CD·…attr 을 문맥(EUDIf, neg, EUDNot, RawTrigger, EUDSCAnd/EUDSCOr ± neg, 목록,
  EUDTernary, EUDElseIf)에서. CDX(마스크)·SetCDX.
- CellArray: 상수 색인(Cell 뷰)·변수 색인 쓰기·읽기·비교(값이 색인 변수 자신인 경우 포함), 파이썬 `arr[i] += v`.
- PCell: P 상수·정수·CurrentPlayer·변수 색인, 12칸, CP 복구. players.PerPlayer(Cell).
- CtrigAsm 별칭 의미(SubCD 포화, `Cell -=` wrap 대 `EUDLightVariable -=` 포화), 빌드 오류(harness expect_build_error).
- epScript 예제(examples/cell_example.eps)의 번역·에뮬레이터 실행(점검 18/18)·euddraft 빌드, 안 되는 모양 확인.
- COST_CASES (tools/cost.py).
"""

import sys

sys.dont_write_bytecode = True
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import inspect  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import types  # noqa: E402

from eudplib import (  # noqa: E402
    EPD,
    Action,
    Add,
    AllPlayers,
    AtLeast,
    AtMost,
    Condition,
    CurrentPlayer,
    DoActions,
    EPSLoader,
    EUDArray,
    EUDElse,
    EUDElseIf,
    EUDEndIf,
    EUDIf,
    EUDLightBool,
    EUDLightVariable,
    EUDNot,
    EUDSCAnd,
    EUDSCOr,
    EUDTernary,
    EUDVariable,
    Exactly,
    ExprProxy,
    Forward,
    GetTriggerCounter,
    Memory,
    P1,
    P3,
    P9,
    P12,
    PopTriggerScope,
    PushTriggerScope,
    RawTrigger,
    SeqCompute,
    SetTo,
    Subtract,
    Trigger,
    f_getcurpl,
    f_setcurpl,
    f_setcurpl2cpcache,
)

from eudext import _compat, cell, players  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing.harness import EDGES32, Suite, rand32  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
SIGN = 0x80000000
CP = 0x6509B0
EX = os.path.join(_common.PKG, "examples")
AT_ADDR = 0x58A364 + 4 * 12 * 201  # 데스 표 유닛 201·P1 (Cell.at 시험용 빈 칸)


def s32(x):
    x &= M32
    return x - (1 << 32) if x & SIGN else x


def u32(x):
    return x & M32


_RNG = random.Random(20260917)
RND = tuple(rand32(_RNG) for _ in range(12))  # 색인 입력이 있는 차등은 이 풀에서 무작위 조합을 뽑는다
POOL = EDGES32 + RND


def kname(k):
    """케이스 이름용 (음수 리터럴은 따로)."""
    return "_" if k is None else ("_m%X" % -k if k < 0 else "_%X" % k)


REF = {
    "assign": lambda a, b: b,
    "iadd": lambda a, b: (a + b) & M32,
    "isub": lambda a, b: (a - b) & M32,
    "sat": lambda a, b: max(a - b, 0),
}
PYOP = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "le": lambda a, b: a <= b,
    "lt": lambda a, b: a < b,
    "ge": lambda a, b: a >= b,
    "gt": lambda a, b: a > b,
}


def cref(op, a, b):
    return int(PYOP[op](a & M32, b & M32))


# ---------------------------------------------------------------------------------------------
# 값 만들기
# ---------------------------------------------------------------------------------------------


def _fw(k):
    """정수 k 로 정한 Forward (0.81 상수식 오프셋은 i32 → 2^31 이상은 음수로 넣는다, DESIGN 3.9)."""
    f = Forward()
    f << s32(k)
    return f


def _setv(h, src):
    """칸(EUDLightVariable/Cell) 또는 변수에 SeqCompute 로 넣는다 (Cell 연산과 독립)."""
    dst = h if isinstance(h, EUDVariable) else EPD(h.getValueAddr())
    SeqCompute([(dst, SetTo, src)])


def value_of(t, kind, target, k=None, name="b"):
    """K: 정수 리터럴, E: Forward, V: 입력 변수, M: EUDLightVariable, C: Cell, S: 대상 칸 자신."""
    if kind == "K":
        return k
    if kind == "E":
        return _fw(k)
    if kind == "V":
        return t.var(name)
    if kind == "M":
        lv = EUDLightVariable()
        _setv(lv, t.var(name))
        return lv
    if kind == "C":
        c = cell.Cell(0)
        _setv(c, t.var(name))
        return c
    if kind == "S":
        return target
    raise ValueError(kind)


def _ifval(t, name, fn, neg=False):
    v = t.var(name)
    if EUDIf()(fn(), neg=neg):
        v << 1
    if EUDElse()():
        v << 0
    EUDEndIf()


def contexts(t, mk, level):
    """mk() 는 부를 때마다 새 조건을 만든다. level 0 = EUDIf, 1 = +neg·EUDNot·RawTrigger, 2 = 전부 (t_cmp 와 같은 틀)."""
    z = t.var("z")
    _ifval(t, "r", mk)
    if level == 0:
        return
    _ifval(t, "rn", mk, neg=True)
    nv = EUDNot(mk())
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


def ctx_expect(r0, level):
    e = {"r": r0}
    if level >= 1:
        e.update(rn=1 - r0, rnot=1 - r0, rraw=r0)
    if level >= 2:
        e.update(rand=r0, randn=1 - r0, rand2=r0, rand2n=1 - r0, ror=r0, rorn=1 - r0, rlist=r0, rt=r0, rtn=1 - r0, relif=r0)
    return e


# ---------------------------------------------------------------------------------------------
# 1. Cell 쓰기
# ---------------------------------------------------------------------------------------------


def _op_lshift(c, v):
    c << v


def _op_iadd(c, v):
    c += v  # 파이썬 연산자 그대로 (__iadd__ 가 self 를 돌려줘야 c 가 그대로다)
    assert isinstance(c, cell.Cell)


def _op_isub(c, v):
    c -= v
    assert isinstance(c, cell.Cell)


WRITE_OPS = {
    "lshift": ("assign", _op_lshift),
    "Assign": ("assign", lambda c, v: c.Assign(v)),
    "assign": ("assign", lambda c, v: c.assign(v)),
    "v_set": ("assign", lambda c, v: setattr(c, "v", v)),
    "setcd": ("assign", lambda c, v: DoActions(cell.SetCD(c, v))),
    "setcd_mod": ("assign", lambda c, v: DoActions(cell.SetCD(c, SetTo, v))),
    "set_cd_trig": ("assign", lambda c, v: Trigger(actions=cell.set_cd(c, v))),
    "iadd": ("iadd", _op_iadd),
    "iadd_m": ("iadd", lambda c, v: c.iadd(v)),
    "iaddattr": ("iadd", lambda c, v: c.iaddattr("v", v)),
    "addcd": ("iadd", lambda c, v: DoActions(cell.AddCD(c, v))),
    "setcd_add": ("iadd", lambda c, v: DoActions(cell.SetCD(c, Add, v))),
    "isub": ("isub", _op_isub),
    "isub_m": ("isub", lambda c, v: c.isub(v)),
    "isubattr": ("isub", lambda c, v: c.isubattr("v", v)),
    "sat": ("sat", lambda c, v: c.isub_sat(v)),
    "isubtractattr": ("sat", lambda c, v: c.isubtractattr("v", v)),
    "subcd": ("sat", lambda c, v: DoActions(cell.SubCD(c, v))),
    "subtract_cd": ("sat", lambda c, v: DoActions(cell.f_subtract_cd(c, v))),
    "setcd_sub": ("sat", lambda c, v: DoActions(cell.SetCD(c, Subtract, v))),
    "subnum": ("sat", lambda c, v: DoActions(c.SubtractNumber(v))),  # eudplib 그대로 (K·E·V 만)
}
K_W = (0, 1, 5, 0x7FFFFFFF, 0x80000000, M32, -1, -0x80000000)
E_W = (0, 0x80000000, M32)


def write_case(s, opname, kind, k=None):
    refk, fn = WRITE_OPS[opname]
    name = "w_%s_%s%s" % (opname, kind, kname(k))

    @s.case(name)
    def _(t):
        c = cell.Cell(0)
        _setv(c, t.var("a"))
        v = value_of(t, kind, c, k)
        fn(c, v)
        t.watch("c", c.addr)

    def expect(a, b=None):
        bb = a if kind == "S" else (u32(k) if kind in "KE" else b)
        return {"c": REF[refk](a, bb)}

    return name, expect


def suite_write():
    s = Suite("t_cell 쓰기")
    cases = []
    for op in WRITE_OPS:
        kinds = ["V"] + ([] if op == "subnum" else ["M", "C", "S"])
        for kind in kinds:
            cases.append((write_case(s, op, kind), kind, None))
        for k in K_W:
            cases.append((write_case(s, op, "K", k), "K", k))
        for k in E_W:
            cases.append((write_case(s, op, "E", k), "E", k))
    s.build()
    for (name, expect), kind, k in cases:
        if kind in "KE":
            kk = u32(k)
            extra = tuple(sorted({kk, (kk - 1) & M32, (kk + 1) & M32}))
            s.diff(name, expect, {"a": EDGES32 + extra}, n=8)
        elif kind == "S":
            s.diff(name, expect, {"a": EDGES32}, n=8)
        else:
            s.diff(name, expect, {"a": EDGES32, "b": EDGES32}, n=40)
    return s.report()


# ---------------------------------------------------------------------------------------------
# 2. 읽기·생성·뷰, CtrigAsm 의미 대조, PerPlayer, Flag
# ---------------------------------------------------------------------------------------------


def suite_misc(py):
    s = Suite("t_cell 읽기·생성")

    @s.case("read")
    def _(t):
        c = cell.Cell(0)
        _setv(c, t.var("a"))
        t.out("r1", c.read())
        r2 = t.var("r2")
        got = c.read(ret=[r2])
        py["read_ret_same"] = got is r2
        t.out("r3", c.v)
        m = cell.Cell(c)  # 칸 → 새 Cell (실행 중 대입)
        t.watch("m", m.addr)

    @s.case("init_var")
    def _(t):
        n0 = GetTriggerCounter()
        c = cell.Cell(t.var("a"))
        py["init_var_trig"] = GetTriggerCounter() - n0
        t.watch("c", c.addr)

    consts = (0, 1, 0x7FFFFFFF, 0x80000000, M32, -1, -5, -0x80000000, True, False)

    @s.case("init_const")
    def _(t):
        n0 = GetTriggerCounter()
        cs = [cell.Cell(k) for k in consts]
        es = [cell.Cell(_fw(u32(k))) for k in consts]
        c0 = cell.CreateCcode()
        c5 = cell.CreateCcode(5)
        one = cell.CreateCcodes(1, 7)
        many = cell.CreateCcodes(3, -2)
        py["init_const_trig"] = GetTriggerCounter() - n0
        py["one_is_cell"] = isinstance(one, cell.Cell)
        py["many"] = (type(many).__name__, len(many), len({id(x) for x in many}))
        for i, c in enumerate(cs):
            t.watch("k%d" % i, c.addr)
        for i, c in enumerate(es):
            t.watch("e%d" % i, c.addr)
        for nm, c in (("c0", c0), ("c5", c5), ("one", one), ("m0", many[0]), ("m2", many[2])):
            t.watch(nm, c.addr)

    @s.case("at")
    def _(t):
        c = cell.Cell.at(AT_ADDR)
        py["at_addr"] = c.addr
        c << t.var("a")
        c.isub_sat(3)
        t.watch("raw", AT_ADDR)
        t.flag("ge", c >= t.var("a"))

    @s.case("contrast")
    def _(t):
        # eudplib EUDLightVariable -= 는 포화, Cell -= 는 wrap (DESIGN 3.5-4 경고가 맞는지)
        lv = EUDLightVariable()
        c = cell.Cell(0)
        a = t.var("a")
        _setv(lv, a)
        _setv(c, a)
        lv -= 5
        c -= 5
        t.watch("lv", lv.getValueAddr())
        t.watch("c", c.addr)
        d = cell.Cell(0)
        _setv(d, a)
        DoActions(d.SubtractNumber(5))  # eudplib 이름 그대로 = 포화 액션
        t.watch("d", d.addr)

    @s.case("perplayer")
    def _(t):
        pp = players.PerPlayer(cell.Cell)
        p, v = t.var("p"), t.var("v")
        for k, c in enumerate(pp):
            DoActions(c.SetNumber(100 * k))
        pp.set(p, v)
        pp.iadditem(p, 3)
        pp.isubitem(p, 10)
        pp[P3] += 1
        for k, c in enumerate(pp):
            t.watch("e%d" % k, c.addr)

    @s.case("flag")
    def _(t):
        f = cell.Flag()
        g = cell.Flag(True)
        h = cell.Flag(0)
        a = t.var("a")
        RawTrigger(conditions=a.AtLeast(1), actions=f.Set())
        RawTrigger(conditions=a.Exactly(0), actions=f.Clear())
        t.flag("f", f)
        t.flag("fs", f.IsSet())
        t.flag("g", g.IsSet())
        t.flag("h", h.IsCleared())
        DoActions(g.Toggle())
        t.flag("g2", g.IsSet())
        DoActions(g.Toggle())

    @s.case("truthy")
    def _(t):
        # EUDIf()(c) = c ≠ 0 (eudplib 이 EUDLightVariable 을 [칸 ≥ 1] 로 바꾼다). RawTrigger 는 칸 자체를 받지 않는다.
        c = cell.Cell(0)
        _setv(c, t.var("a"))
        _ifval(t, "r", lambda: c)
        _ifval(t, "rn", lambda: c, neg=True)
        _ifval(t, "rnot", lambda: EUDNot(c))

    s.build()
    ab = {"a": EDGES32}
    s.diff("read", lambda a: {"r1": a, "r2": a, "r3": a, "m": a}, ab, n=20)
    s.diff("init_var", lambda a: {"c": a}, ab, n=10)
    exp = {}
    for i, k in enumerate(consts):
        exp["k%d" % i] = u32(int(k))
        exp["e%d" % i] = u32(int(k))
    exp.update(c0=0, c5=5, one=7, m0=M32 - 1, m2=M32 - 1)
    s.check("init_const", {}, exp, fresh=True)
    s.diff("at", lambda a: {"raw": max(a - 3, 0), "ge": int(max(a - 3, 0) >= a)}, ab, n=10)
    s.diff("contrast", lambda a: {"lv": max(a - 5, 0), "c": (a - 5) & M32, "d": max(a - 5, 0)}, {"a": EDGES32 + (3, 5, 6)}, n=10)

    def pp_ref(p, v):
        e = [100 * k for k in range(8)]
        if p < 8:
            e[p] = (v + 3 - 10) & M32
        e[2] = (e[2] + 1) & M32
        return {"e%d" % k: e[k] for k in range(8)}

    s.diff("perplayer", pp_ref, {"p": list(range(8)) + [8, M32], "v": EDGES32}, n=20)
    s.diff("flag", lambda a: {"f": int(a != 0), "fs": int(a != 0), "g": 1, "h": 1, "g2": 0}, ab, n=5)
    s.diff("truthy", lambda a: {"r": int(a != 0), "rn": int(a == 0), "rnot": int(a == 0)}, ab, n=10)
    s.expect_true("read", py.get("read_ret_same") is True, "read(ret=[r]) 는 r")
    s.expect_true("init_var", py.get("init_var_trig") in (1, 2), "Cell(변수) 호출 자리", repr(py.get("init_var_trig")))
    s.expect_true("init_const", py.get("init_const_trig") == 0, "상수·주소식 초기값 트리거 0", repr(py.get("init_const_trig")))
    s.expect_true("init_const", py.get("one_is_cell") is True, "CreateCcodes(1) = Cell")
    s.expect_true("init_const", py.get("many") == ("list", 3, 3), "CreateCcodes(3) = 목록", repr(py.get("many")))
    s.expect_true("at", py.get("at_addr") == AT_ADDR, "Cell.at 주소")
    return s.report()


# ---------------------------------------------------------------------------------------------
# 3. 조건
# ---------------------------------------------------------------------------------------------

COND_OPS = {
    "eq": ("eq", lambda c, v: c == v),
    "ne": ("ne", lambda c, v: c != v),
    "le": ("le", lambda c, v: c <= v),
    "lt": ("lt", lambda c, v: c < v),
    "ge": ("ge", lambda c, v: c >= v),
    "gt": ("gt", lambda c, v: c > v),
    "AtLeast": ("ge", lambda c, v: c.AtLeast(v)),
    "AtMost": ("le", lambda c, v: c.AtMost(v)),
    "Exactly": ("eq", lambda c, v: c.Exactly(v)),
    "cd": ("eq", lambda c, v: cell.CD(c, v)),
    "cd_ge": ("ge", lambda c, v: cell.CD(c, v, AtLeast)),
    "cd_le": ("le", lambda c, v: cell.CD(c, v, AtMost)),
    "cd_design": ("ge", lambda c, v: cell.CD(c, AtLeast, v)),
    "f_cd": ("le", lambda c, v: cell.f_cd(c, v, type=AtMost)),
    "eqattr": ("eq", lambda c, v: c.eqattr("v", v)),
    "neattr": ("ne", lambda c, v: c.neattr("v", v)),
    "leattr": ("le", lambda c, v: c.leattr("v", v)),
    "ltattr": ("lt", lambda c, v: c.ltattr("v", v)),
    "geattr": ("ge", lambda c, v: c.geattr("v", v)),
    "gtattr": ("gt", lambda c, v: c.gtattr("v", v)),
}
MAIN_COND = ("eq", "ne", "le", "lt", "ge", "gt")
K_C = EDGES32 + (5,)
E_C = (0, 5, 0x80000000, M32)
REFLECT = {"lt": ("gt", lambda k, c: k < c), "ge": ("le", lambda k, c: k >= c), "ne": ("ne", lambda k, c: k != c)}


def cond_case(s, opname, kind, k=None, level=1):
    refop, fn = COND_OPS[opname]
    name = "c_%s_%s%s" % (opname, kind, kname(k))

    @s.case(name)
    def _(t):
        c = cell.Cell(0)
        _setv(c, t.var("a"))
        v = value_of(t, kind, c, k)
        contexts(t, lambda: fn(c, v), level)

    def expect(a, b=None):
        bb = a if kind == "S" else (u32(k) if kind in "KE" else b)
        return ctx_expect(cref(refop, a, bb), level)

    return name, expect


def reflect_case(s, opname, k):
    refop, fn = REFLECT[opname]
    name = "rc_%s%s" % (opname, kname(k))

    @s.case(name)
    def _(t):
        c = cell.Cell(0)
        _setv(c, t.var("a"))
        contexts(t, lambda: fn(k, c), 1)

    return name, lambda a: ctx_expect(cref(refop, a, u32(k)), 1)


CDX_MASKS = (0xFF, 0xF0F0, M32)


def cdx_values(m):
    return sorted({0, 1, m, (m + 1) & M32, 0x100, M32, 0x30, 0x1000})


def cdx_case(s, op, m, kind, k=None):
    tp = {"eq": Exactly, "ge": AtLeast, "le": AtMost}[op]
    name = "cdx_%s_%X_%s%s" % (op, m, kind, "" if k is None else "_%X" % k)

    @s.case(name)
    def _(t):
        c = cell.Cell(0)
        _setv(c, t.var("a"))
        v = value_of(t, kind, c, k)
        if op == "eq":
            mk = lambda: cell.CDX(c, v, m)  # noqa: E731 — 기본 비교 Exactly
        else:
            mk = lambda: cell.cdx(c, v, m, tp)  # noqa: E731
        contexts(t, mk, 1)

    def expect(a, b=None):
        bb = u32(k) if kind == "K" else b
        return ctx_expect(cref(op, a & m, bb), 1)

    return name, expect


def setcdx_case(s, vkind, mkind, k=None, mconst=None):
    name = "setcdx_%s%s_%s%s" % (vkind, "" if k is None else "_%X" % k, mkind, "" if mconst is None else "_%X" % mconst)

    @s.case(name)
    def _(t):
        c = cell.Cell(0)
        _setv(c, t.var("a"))
        bv, mv = t.var("b"), t.var("m")
        v = k if vkind == "K" else bv
        mm = mconst if mkind == "K" else mv
        DoActions(cell.SetCDX(c, v, mm))
        t.watch("c", c.addr)

    def expect(a, b, m):
        vv = k if vkind == "K" else b
        mv = mconst if mkind == "K" else m
        return {"c": (a & ~mv & M32) | (vv & mv)}

    return name, expect


def suite_cond():
    s = Suite("t_cell 조건")
    cases = []
    for op in COND_OPS:
        level = 2 if op in MAIN_COND else 1
        for kind in "VMCS":
            cases.append((cond_case(s, op, kind, level=level), kind, None))
        for k in K_C if op in MAIN_COND else (0, 5, M32):
            cases.append((cond_case(s, op, "K", k, level), "K", k))
        for k in E_C if op in MAIN_COND else (5,):
            cases.append((cond_case(s, op, "E", k, 1), "E", k))
    refl = [reflect_case(s, op, k) for op in REFLECT for k in (0, 5, M32)]
    cdx = []
    for m in CDX_MASKS:
        for op in ("eq", "ge", "le"):
            for k in cdx_values(m):
                cdx.append((cdx_case(s, op, m, "K", k), "K"))
            cdx.append((cdx_case(s, op, m, "V"), "V"))
    setcdx = [setcdx_case(s, "K", "K", 0x1234, mconst=0xFF00), setcdx_case(s, "V", "K", mconst=0xF0F0),
              setcdx_case(s, "K", "V", k=0xABCD), setcdx_case(s, "V", "V")]
    s.build()
    for (name, expect), kind, k in cases:
        if kind in "KE":
            kk = u32(k)
            extra = tuple(sorted({kk, (kk - 1) & M32, (kk + 1) & M32}))
            s.diff(name, expect, {"a": EDGES32 + extra}, n=6)
        elif kind == "S":
            s.diff(name, expect, {"a": EDGES32}, n=4)
        else:
            s.diff(name, expect, {"a": EDGES32, "b": EDGES32}, n=30)
    for name, expect in refl:
        s.diff(name, expect, {"a": EDGES32 + (4, 5, 6)}, n=4)
    masked = (0, 0x30, 0xFF, 0x100, 0x1234, 0xF0F0, 0xFF30, M32)
    for (name, expect), kind in cdx:
        if kind == "K":
            s.diff(name, expect, {"a": EDGES32 + masked}, n=6)
        else:
            s.diff(name, expect, {"a": EDGES32 + masked, "b": EDGES32 + masked}, n=30)
    for name, expect in setcdx:
        s.diff(name, expect, {"a": EDGES32, "b": EDGES32 + (0xABCD,), "m": (0, 0xFF, 0xF0F0, M32)}, n=20)
    return s.report()


# ---------------------------------------------------------------------------------------------
# 4. CellArray / PCell
# ---------------------------------------------------------------------------------------------

N_ARR = 4


def _arr_init(t, arr):
    t.var("i")  # 상수 색인 케이스에도 입력 칸을 둔다 (diff 가 i 를 넣는다)
    for k in range(N_ARR):
        SeqCompute([(arr.epd + k, SetTo, t.var("e%d" % k))])
    for k in range(N_ARR):
        t.watch("o%d" % k, arr.addr + 4 * k)


def _py_iadd(arr, i, v):
    arr[i] += v  # 파이썬: 읽기 → += → 쓰기 (변수 색인), 상수 색인은 뷰


def _py_isub(arr, i, v):
    arr[i] -= v


def _setitem(arr, i, v):
    arr[i] = v


ARR_OPS = {
    "setitem": ("assign", _setitem),
    "set": ("assign", lambda arr, i, v: arr.set(i, v)),
    "iadditem": ("iadd", lambda arr, i, v: arr.iadditem(i, v)),
    "iadd": ("iadd", lambda arr, i, v: arr.iadd(i, v)),
    "py_iadd": ("iadd", _py_iadd),
    "isubitem": ("isub", lambda arr, i, v: arr.isubitem(i, v)),
    "isub": ("isub", lambda arr, i, v: arr.isub(i, v)),
    "py_isub": ("isub", _py_isub),
    "isub_sat": ("sat", lambda arr, i, v: arr.isub_sat(i, v)),
    "isubtractitem": ("sat", lambda arr, i, v: arr.isubtractitem(i, v)),
}
K_A = (0, 1, 0x80000000, M32, -3)
IK = 2  # 상수 색인


def arr_write_case(s, opname, ikind, vkind, k=None):
    refk, fn = ARR_OPS[opname]
    name = "a_%s_%s_%s%s" % (opname, ikind, vkind, kname(k))

    @s.case(name)
    def _(t):
        arr = cell.CellArray(N_ARR)
        _arr_init(t, arr)
        i = t.var("i") if ikind == "iv" else IK
        if vkind == "I":
            v = t.var("i")
        else:
            v = value_of(t, vkind, None, k)
        fn(arr, i, v)

    def expect(i=IK, b=None, **e):
        e = [e["e%d" % q] for q in range(N_ARR)]
        idx = i if ikind == "iv" else IK
        bb = {"K": u32(k) if k is not None else None, "E": u32(k) if k is not None else None, "I": i}.get(vkind, b)
        e[idx] = REF[refk](e[idx], bb)
        return {"o%d" % q: e[q] for q in range(N_ARR)}

    return name, expect


def arr_read_case(s, how):
    name = "ar_%s" % how

    @s.case(name)
    def _(t):
        arr = cell.CellArray(N_ARR)
        _arr_init(t, arr)
        i = t.var("i")
        if how == "get":
            t.out("r", arr.get(i))
        elif how == "getitem":
            t.out("r", arr[i])
        elif how == "ret":
            r = t.var("r")
            arr.get(i, ret=[r])
        elif how == "const":
            t.out("r", arr.get(IK))
            t.out("r2", arr[1].read())
            t.out("r3", arr[3].v)

    def expect(i, **e):
        if how == "const":
            return {"r": e["e%d" % IK], "r2": e["e1"], "r3": e["e3"]}
        return {"r": e["e%d" % i]}

    return name, expect


ARR_COND = {op: getattr(cell.CellArray, op + "item") for op in PYOP}
K_AC = EDGES32 + (5,)


def arr_cond_case(s, op, ikind, vkind, k=None, level=1):
    fn = ARR_COND[op]
    name = "ac_%s_%s_%s%s" % (op, ikind, vkind, kname(k))

    @s.case(name)
    def _(t):
        arr = cell.CellArray(N_ARR)
        _arr_init(t, arr)
        i = t.var("i") if ikind == "iv" else IK
        v = t.var("i") if vkind == "I" else value_of(t, vkind, None, k)
        contexts(t, lambda: fn(arr, i, v), level)

    def expect(i=IK, b=None, **e):
        idx = i if ikind == "iv" else IK
        bb = {"K": u32(k) if k is not None else None, "E": u32(k) if k is not None else None, "I": i}.get(vkind, b)
        return ctx_expect(cref(op, e["e%d" % idx], bb), level)

    return name, expect


def pcell_case(s, how, ikind):
    name = "p_%s_%s" % (how, ikind)
    count = 12 if ikind == "P12" else 8

    @s.case(name)
    def _(t):
        pc = cell.PCell(init=[100 + q for q in range(count)], count=count)
        p, v = t.var("p"), t.var("v")
        DoActions([pc[q].SetNumber(100 + q) for q in range(count)])  # 매 실행 같은 시작값 (diff 는 메모리를 되돌리지 않는다)
        old = EUDVariable()
        old << f_getcurpl()
        if ikind == "cp":
            f_setcurpl(p)
        idx = {"P3": P3, "int": 5, "cp": CurrentPlayer, "var": p, "P12": P12}[ikind]
        if how == "set":
            pc[idx] = v
        elif how == "iadd":
            pc.iadditem(idx, v)
        elif how == "py_iadd":
            pc[idx] += v
        elif how == "isub":
            pc.isubitem(idx, v)
        elif how == "sat":
            pc.isub_sat(idx, v)
        elif how == "get":
            t.out("r", pc.get(idx))
        elif how == "eq":
            t.flag("r", pc.eqitem(idx, v))
        elif how == "lt":
            t.flag("r", pc.ltitem(idx, v))
        if ikind == "cp":
            f_setcurpl2cpcache()  # CP 캐시가 그대로인지 (캐시 변수의 수정자가 바뀌었으면 여기서 CP 가 틀어진다)
            t.flag("cpok", Memory(CP, Exactly, p))
            f_setcurpl(old)
        for q in range(count):
            t.watch("o%d" % q, pc.addr + 4 * q)
        t.watch("rawcp", CP)
        t.watch("cache", _compat.cpcache_var().getValueAddr())

    def expect(p, v):
        e = [100 + q for q in range(count)]
        idx = {"P3": 2, "int": 5, "cp": p, "var": p, "P12": 11}[ikind]
        out = {}
        if how in ("set", "iadd", "py_iadd", "isub", "sat"):
            rk = {"set": "assign", "iadd": "iadd", "py_iadd": "iadd", "isub": "isub", "sat": "sat"}[how]
            e[idx] = REF[rk](e[idx], v)
        elif how == "get":
            out["r"] = e[idx]
        elif how == "eq":
            out["r"] = int(e[idx] == v)
        elif how == "lt":
            out["r"] = int(e[idx] < v)
        out.update({"o%d" % q: e[q] for q in range(count)})
        if ikind == "cp":
            out["cpok"] = 1
        return out

    return name, expect


def suite_array(py):
    s = Suite("t_cell 배열")
    writes = []
    for op in ARR_OPS:
        for ikind in ("iv", "ik"):
            vkinds = ("V", "M", "C", "I") if ikind == "iv" else ("V", "M", "C")
            if ikind == "iv" and op.startswith("py_"):
                vkinds = ("V", "I")  # 파이썬 읽고-쓰기: 읽은 값은 EUDVariable 이라 칸(M·C) 값은 eudplib 이 못 받는다
            for vk in vkinds:
                writes.append((arr_write_case(s, op, ikind, vk), vk))
            for k in K_A:
                writes.append((arr_write_case(s, op, ikind, "K", k), "K"))
            writes.append((arr_write_case(s, op, ikind, "E", 0x80000000), "K"))
    reads = [arr_read_case(s, h) for h in ("get", "getitem", "ret", "const")]
    conds = []
    for op in PYOP:
        for vk in ("V", "M", "I"):
            conds.append((arr_cond_case(s, op, "iv", vk, level=2), vk))
        conds.append((arr_cond_case(s, op, "ik", "V", level=1), "V"))
        for k in K_AC:
            conds.append((arr_cond_case(s, op, "iv", "K", k, level=2 if k in (0, 5, M32) else 1), "K"))
        for k in (0, 5, M32):
            conds.append((arr_cond_case(s, op, "ik", "K", k, level=1), "K"))
            conds.append((arr_cond_case(s, op, "iv", "E", k, level=1), "K"))
    pcs = []
    for how in ("set", "iadd", "py_iadd", "isub", "sat", "get", "eq", "lt"):
        for ikind in ("P3", "int", "cp", "var"):
            pcs.append((pcell_case(s, how, ikind), ikind))
    for how in ("set", "get"):
        pcs.append((pcell_case(s, how, "P12"), "P12"))

    @s.case("views")
    def _(t):
        arr = cell.CellArray([7, -1, _fw(0x80000000), 3])
        py["view_same"] = arr[1] is arr.cell(1) and arr[P1] is arr[0]
        py["iter"] = [type(x).__name__ for x in arr]
        n0 = GetTriggerCounter()
        arr[2] += 5  # 파이썬: 뷰 += 5 뒤 arr[2] = 뷰 → 다시 쓰지 않아야 한다
        py["view_iadd_trig"] = GetTriggerCounter() - n0
        n0 = GetTriggerCounter()
        arr[3] -= arr[3]  # 다른 뷰 객체라도 같은 칸 → 읽고 뺀다 = 0
        arr[0] << arr[1]
        arr[1].isub_sat(arr[0])
        py["view_misc_trig"] = GetTriggerCounter() - n0
        for k in range(4):
            t.watch("o%d" % k, arr.addr + 4 * k)

    s.build()
    # 색인 입력은 목록이어야 하므로 무작위 단계(n)는 쓰지 않고, 경계값 + 난수 풀에서 무작위 조합(max_edges)을 뽑는다
    einp = {"e%d" % q: POOL for q in range(N_ARR)}
    for (name, expect), vk in writes:
        inp = dict(einp)
        inp["i"] = list(range(N_ARR))
        if vk not in ("K", "I"):
            inp["b"] = POOL
        s.diff(name, expect, inp, n=0, max_edges=60)
    for name, expect in reads:
        s.diff(name, expect, dict(einp, i=list(range(N_ARR))), n=0, max_edges=40)
    for (name, expect), vk in conds:
        inp = dict(einp)
        inp["i"] = list(range(N_ARR))
        if vk not in ("K", "I"):
            inp["b"] = POOL
        s.diff(name, expect, inp, n=0, max_edges=70)
    for (name, expect), ikind in pcs:
        ps = list(range(12 if ikind in ("P12",) else 8))
        s.diff(name, expect, {"p": ps, "v": POOL + (100, 102, 105, 111)}, n=0, max_edges=60)
    s.check("views", {}, {"o0": M32, "o1": 0, "o2": 0x80000005, "o3": 0}, fresh=True)
    s.expect_true("views", py.get("view_same") is True, "같은 k 는 같은 뷰")
    s.expect_true("views", py.get("iter") == ["Cell"] * 4, "순회 = Cell 뷰", repr(py.get("iter")))
    s.expect_true("views", py.get("view_iadd_trig") == 1, "arr[k] += 상수 는 트리거 1 (되쓰기 없음)", repr(py.get("view_iadd_trig")))
    return s.report()


# ---------------------------------------------------------------------------------------------
# 5. 빌드 오류 (harness expect_build_error)
# ---------------------------------------------------------------------------------------------

BAD = [
    ("cell_big", lambda: cell.Cell(1 << 32), "32비트"),
    ("cell_small", lambda: cell.Cell(-(1 << 31) - 1), "32비트"),
    ("cell_flag", lambda: cell.Cell(cell.Flag()), "Flag"),
    ("cell_lightbool", lambda: cell.Cell(EUDLightBool()), "EUDLightBool"),
    ("cell_cond", lambda: cell.Cell(Memory(0x58A364, AtLeast, 1)), "조건"),
    ("cell_str", lambda: cell.Cell("3"), "정수"),
    ("cell_cmp_const", lambda: cell.Cell(0) << AtLeast, "비교·수정자"),
    ("assign_big", lambda: cell.Cell(0) << (1 << 32), "32비트"),
    ("iadd_list", lambda: cell.Cell(0).__iadd__([1]), "목록"),
    ("isub_flag", lambda: cell.Cell(0).__isub__(cell.Flag()), "Flag"),
    ("sat_cond", lambda: cell.Cell(0).isub_sat(Memory(0x58A364, AtLeast, 1)), "조건"),
    ("bool", lambda: bool(cell.Cell(0)), "파이썬 if"),
    ("at_p1marine", lambda: cell.Cell.at(0x58A364), "P1 마린"),
    ("at_align", lambda: cell.Cell.at(0x58A365), "4의 배수"),
    ("at_var", lambda: cell.Cell.at(EUDVariable()), "상수"),
    ("at_range", lambda: cell.Cell.at(1 << 32), "32비트"),
    ("read_ret", lambda: cell.Cell(0).read(ret=5), "ret"),
    ("cmp_flag", lambda: cell.Cell(0) >= cell.Flag(), "EUDLightBool"),
    ("arr_zero", lambda: cell.CellArray(0), "1 이상"),
    ("arr_empty", lambda: cell.CellArray([]), "비었"),
    ("arr_var_init", lambda: cell.CellArray([EUDVariable()]), "상수"),
    ("arr_bool", lambda: cell.CellArray(True), "정수"),
    ("arr_str", lambda: cell.CellArray("4"), "개수"),
    ("arr_index", lambda: cell.CellArray(4)[4], "범위"),
    ("arr_index_neg", lambda: cell.CellArray(4).set(-1, 0), "범위"),
    ("arr_index_str", lambda: cell.CellArray(4).iadditem("x", 1), "색인"),
    ("arr_cell_var", lambda: cell.CellArray(4).cell(EUDVariable()), "상수 색인"),
    ("arr_get_ret", lambda: cell.CellArray(4).get(EUDVariable(), ret=[1]), "ret"),
    ("arr_value", lambda: cell.CellArray(4).set(EUDVariable(), cell.Flag()), "Flag"),
    ("pcell_count", lambda: cell.PCell(count=13), "count"),
    ("pcell_count0", lambda: cell.PCell(count=0), "count"),
    ("pcell_list", lambda: cell.PCell(init=[0] * 3), "길이"),
    ("pcell_all", lambda: cell.PCell()[AllPlayers], "묶음"),
    ("pcell_p9", lambda: cell.PCell().iadditem(P9, 1), "없습니다"),
    ("pcell_bool", lambda: cell.PCell()[True], "bool"),
    ("pcell_str", lambda: cell.PCell().get(object()), "플레이어"),
    ("cd_type", lambda: cell.CD(cell.Cell(0), 3, SetTo), "비교"),
    ("cd_type_str", lambda: cell.CD(cell.Cell(0), 3, "Foo"), "비교"),
    ("cd_arr", lambda: cell.CD(cell.CellArray(2), 3), "CellArray"),
    ("cd_int", lambda: cell.CD(5, 3), "Ccode"),
    ("cdx_varmask", lambda: cell.CDX(cell.Cell(0), 3, EUDVariable()), "마스크"),
    ("cdx_order", lambda: cell.CDX(cell.Cell(0), AtLeast, 3), "순서"),
    ("setcd_extra", lambda: cell.SetCD(cell.Cell(0), 1, 2), "인자"),
    ("setcd_cmp", lambda: cell.SetCD(cell.Cell(0), AtLeast, 1), "인자"),
    ("setcdx_mask", lambda: cell.SetCDX(cell.Cell(0), 1, "m"), "마스크"),
    ("subcd_flag", lambda: cell.SubCD(cell.Cell(0), cell.Flag()), "Flag"),
    ("addcd_code", lambda: cell.AddCD(cell.Flag(), 1), "Ccode"),
    ("ccodes_zero", lambda: cell.CreateCcodes(0), "개수"),
    ("flag_init", lambda: cell.Flag(5), "True/False"),
]


def suite_errors():
    s = Suite("t_cell 빌드 오류")
    for name, fn, msg in BAD:

        @s.case("bad_" + name, expect_build_error=EudextError, expect_message=msg)
        def _(t, fn=fn):
            fn()

    @s.case("bad_attr", expect_build_error=AttributeError)
    def _(t):
        cell.Cell(0).iaddattr("x", 1)  # epScript _ATTW 는 AttributeError 를 받아 읽고-쓰기로 넘어간다

    @s.case("ok_after_errors")
    def _(t):
        c = cell.Cell(0)
        c << t.var("a")
        c -= 1
        t.watch("c", c.addr)

    s.build()
    s.diff("ok_after_errors", lambda a: {"c": (a - 1) & M32}, {"a": EDGES32}, n=5)
    return s.report()


# ---------------------------------------------------------------------------------------------
# 6. 파이썬 쪽 검사 (에뮬레이터 밖)
# ---------------------------------------------------------------------------------------------

DOC_KEYS = ("비용:", "CP:", "로컬:", "epScript:", "출처:")


def python_checks(ck):
    ck.true("__all__ 이름", all(hasattr(cell, n) for n in cell.__all__))
    for alias, fn in (("CD", "f_cd"), ("CDX", "f_cdx"), ("SetCD", "f_set_cd"), ("SetCDX", "f_set_cdx"),
                      ("AddCD", "f_add_cd"), ("SubCD", "f_subtract_cd"), ("cd", "f_cd"), ("cdx", "f_cdx"),
                      ("set_cd", "f_set_cd"), ("set_cdx", "f_set_cdx"), ("add_cd", "f_add_cd"),
                      ("subtract_cd", "f_subtract_cd")):
        ck.true("별칭 %s" % alias, getattr(cell, alias) is getattr(cell, fn))
    # 이름 규칙 3.5: sub 만 든 포화 이름을 두지 않는다
    ck.true("sub_cd 없음", not any(hasattr(cell, n) for n in ("sub_cd", "f_sub_cd", "f_subcd")))
    for obj in (cell.Cell, cell.Cell.at, cell.Cell.isub_sat, cell.Cell.read, cell.Flag, cell.CellArray, cell.PCell,
                cell.CreateCcode, cell.CreateCcodes, cell.CreateCcodeArr, cell.f_cd, cell.f_cdx, cell.f_set_cd,
                cell.f_set_cdx, cell.f_add_cd, cell.f_subtract_cd):
        doc = inspect.getdoc(obj) or ""
        miss = [k for k in DOC_KEYS if k not in doc]
        if obj in (cell.Cell.isub_sat, cell.Cell.read):
            miss = [k for k in miss if k not in ("CP:", "로컬:", "출처:")]
        ck.eq("docstring %s" % getattr(obj, "__qualname__", obj), miss, [])
    for word in ("wrap", "포화", "f_dwread_epd", "EUDLightVariable -= x"):
        ck.true("모듈 문서에 %s" % word, word in (cell.__doc__ or ""))
    # 비공개 eudplib 이름을 쓰지 않는다 (_compat 경유만)
    src = open(cell.__file__, encoding="utf-8").read()
    for bad in ("_memaddr", "eudplib.core", "eudplib.utils", "._mask", "import eudplib."):
        ck.true("cell.py 에 %s 없음" % bad, bad not in src)
    ck.true("cell.py P1 마린 주소는 금지 검사에만", src.count("P1_MARINE_ADDR") == 2)

    PushTriggerScope()
    try:
        c = cell.Cell(3)
        ck.true("Cell 은 EUDLightVariable", isinstance(c, EUDLightVariable) and _compat.is_varbase(c) and not _compat.is_var(c))
        ck.true("hash", c in {c: 1})
        ck.true("repr 안내", "c.read()" in repr(c) and "const" in repr(c))
        ck.raises("bool", EudextError, bool, c)
        ck.true("<< 는 self", (c << 5) is c)
        ck.true("iadd 는 self", c.__iadd__(1) is c and c.iadd(1) is c)
        ck.true("isub 는 self", c.__isub__(1) is c and c.isub(1) is c)
        ck.true("isub_sat 는 self", c.isub_sat(1) is c)
        ck.true("assign 는 self", c.assign(2) is c)
        ck.true("addr = getValueAddr", c.addr is c.getValueAddr())
        cond = cell.CD(c, 3)
        ck.true("CD 상수 = Condition", isinstance(cond, Condition) and cond.fields[4] == 10 and cond.fields[2] == 3)
        d1 = cell.CD(c)
        ck.true("CD 기본 = Exactly 1", d1.fields[4] == 10 and d1.fields[2] == 1)
        d2 = cell.CD(c, AtLeast)
        ck.true("CD(c, AtLeast) = AtLeast 1", d2.fields[4] == 0 and d2.fields[2] == 1)
        d3 = cell.CD(c, AtMost, 7)
        ck.true("CD(c, AtMost, 7)", d3.fields[4] == 1 and d3.fields[2] == 7)
        ck.true("CD(c, 0, AtLeast) = Always", cell.CD(c, 0, AtLeast).fields[5] == 22)
        ck.true("CD(c, 0) = 조건 하나", isinstance(cell.CD(c, 0), Condition))
        for fn, mod, val in ((cell.SetCD(c), 7, 1), (cell.SetCD(c, 9), 7, 9), (cell.AddCD(c), 8, 1),
                             (cell.AddCD(c, -1), 8, M32), (cell.SubCD(c), 9, 1), (cell.SubCD(c, 4), 9, 4),
                             (cell.SetCD(c, Subtract, 2), 9, 2), (cell.SetCD(c, Add), 8, 1)):
            ck.true("액션 수정자 %d 값 %d" % (mod, val), isinstance(fn, Action) and fn.fields[8] == mod and u32(fn.fields[5]) == val,
                    repr(fn.fields))
        x = cell.SetCDX(c, 0x30, 0xF0)
        ck.true("SetCDX = 마스크 SetTo", x.fields[8] == 7 and x.fields[11] == 0x4353 and x.fields[0] == 0xF0)
        v = EUDVariable()
        ck.true("SetCD 변수 값 = 변수 필드", cell.SetCD(c, v).fields[5] is v)
        ck.true("CDX 접기", cell.CDX(c, 0, 0xFF, AtLeast).fields[5] == 22 and cell.CDX(c, 0x100, 0xFF).fields[5] == 23
                and cell.CDX(c, 0xFF, 0xFF, AtMost).fields[5] == 22 and cell.CDX(c, 0x100, 0xFF, AtLeast).fields[5] == 23)
        ck.true("CDX 상수 = 마스크 조건", cell.CDX(c, 0x10, 0xF0).fields[8] == 0x4353)
        n0 = GetTriggerCounter()
        c2 = cell.Cell(7)
        cell.Cell(_fw(0x80000000))
        arr = cell.CreateCcodeArr(5)
        pc = cell.PCell()
        cell.PCell(3, count=12)
        f = cell.Flag(True)
        ck.eq("만들기 트리거 0", GetTriggerCounter() - n0, 0)
        ck.true("c2 칸", c2.addr is not c.addr)
        ck.true("CellArray 형", isinstance(arr, cell.CellArray) and isinstance(arr, ExprProxy) and len(arr) == 5 and arr.length == 5)
        ck.true("CellArray array", isinstance(arr.array, EUDArray) and arr.epd is _compat.eudarray_epd(arr.array))
        ck.true("CellArray repr", "CellArray" in repr(arr) and "5" in repr(arr))
        ck.true("PCell 형", isinstance(pc, cell.CellArray) and len(pc) == 8)
        ck.true("PCell 12", len(cell.PCell(count=12)) == 12)
        ck.true("PCell 뷰", pc[P3] is pc[2] and pc[P1] is pc.cell(0))
        ck.true("Flag 형", isinstance(f, EUDLightBool) and "IsSet" in repr(f))
        ck.true("CreateCcodes 목록", isinstance(cell.CreateCcodes(2), list))
    finally:
        PopTriggerScope()


# ---------------------------------------------------------------------------------------------
# 7. epScript
# ---------------------------------------------------------------------------------------------


def load_eps_example():
    """예제 eps 를 작업 폴더에 복사해 EPSLoader 로 불러온다(__epspy__ 가 작업 폴더에 생긴다)."""
    d = os.path.join(_common.WORK, "t_cell", "eps")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "cell_example.eps")
    shutil.copy2(os.path.join(EX, "cell_example.eps"), p)
    name = "cell_example_eps"
    mod = types.ModuleType(name)
    loader = EPSLoader(name, p)
    mod.__loader__ = loader
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


def suite_eps(eps):
    s = Suite("t_cell epScript 예제")

    def with_hp(t, fn):
        _setv(eps.hp, t.var("a"))
        fn()

    @s.case("damage")
    def _(t):
        _setv(eps.hp, t.var("a"))
        eps.f_damage(t.var("b"))
        t.out("r", eps.f_hp_value())

    @s.case("tick_down")
    def _(t):
        _setv(eps.timer, t.var("a"))
        eps.f_tick_down(t.var("b"))
        t.out("r", eps.f_timer_value())

    @s.case("compare")
    def _(t):
        _setv(eps.hp, t.var("a"))
        b = t.var("b")
        t.out("ge", eps.f_at_least(b))
        t.out("lt", eps.f_below(b))
        t.out("ne", eps.f_not_equal(b))

    @s.case("items")
    def _(t):
        i, b, j = t.var("i"), t.var("b"), t.var("j")
        for q in range(4):
            SeqCompute([(eps.arr.epd + q, SetTo, t.var("e%d" % q))])
        eps.f_add_item(i, b)
        eps.f_sub_item(j, 3)
        eps.f_sat_item(i, 7)
        t.out("g", eps.f_get_item(j))
        t.out("is", eps.f_item_is(i, b))
        t.out("below", eps.f_item_below(j, b))
        eps.f_set_item(3, b)
        for q in range(4):
            t.watch("o%d" % q, eps.arr.addr + 4 * q)

    @s.case("kills")
    def _(t):
        p = t.var("p")
        for q in range(8):
            DoActions(eps.kills[q].SetNumber(q))
        old = EUDVariable()
        old << f_getcurpl()
        eps.f_add_kill(p)
        f_setcurpl(t.var("c"))
        eps.f_add_kill_cp()
        f_setcurpl(old)
        t.out("r", eps.f_kills_of(p))
        for q in range(8):
            t.watch("o%d" % q, eps.kills.addr + 4 * q)

    @s.case("ctrig")
    def _(t):
        t.out("r", eps.f_ctrig(t.var("a"), t.var("b")))
        t.watch("A", eps.a.addr)
        t.watch("B", eps.b.addr)

    @s.case("selftest")
    def _(t):
        t.out("n", eps.f_selftest())

    @s.case("flag")
    def _(t):
        t.out("r", eps.f_flag_demo())

    @s.case("after")
    def _(t):
        eps.afterTriggerExec()

    s.build()
    ab = {"a": EDGES32 + (3, 5, 7), "b": EDGES32 + (3, 5, 7)}
    s.diff("damage", lambda a, b: {"r": max(a - b, 0)}, ab, n=40)
    s.diff("tick_down", lambda a, b: {"r": (a - b) & M32}, ab, n=40)
    s.diff("compare", lambda a, b: {"ge": int(a >= b), "lt": int(a < b), "ne": int(a != b)}, ab, n=60)

    def items_ref(i, j, b, **e):
        e = [e["e%d" % q] for q in range(4)]
        e[i] = (e[i] + b) & M32
        e[j] = (e[j] - 3) & M32
        e[i] = max(e[i] - 7, 0)
        out = {"g": e[j], "is": int(e[i] == b), "below": int(e[j] < b)}
        e[3] = b
        out.update({"o%d" % q: e[q] for q in range(4)})
        return out

    s.diff("items", items_ref, dict({"e%d" % q: POOL + (7, 10) for q in range(4)}, i=[0, 1, 2, 3], j=[0, 1, 2, 3],
                                    b=POOL + (3, 7)), n=0, max_edges=150)

    def kills_ref(p, c):
        e = list(range(8))
        e[p] += 1
        e[c] += 1
        return dict({"o%d" % q: e[q] for q in range(8)}, r=e[p])

    s.diff("kills", kills_ref, {"p": list(range(8)), "c": list(range(8))}, n=0, max_edges=64)

    def ctrig_ref(a, b):
        ca = (a + 1) & M32
        cb = max(b - a, 0)
        return {"r": int(ca >= 1) + 10 * int(cb == 0) + 100 * int(ca <= b), "A": ca, "B": cb}

    s.diff("ctrig", ctrig_ref, ab, n=40)
    s.check("selftest", {}, {"n": 18}, fresh=True)
    s.check("flag", {}, {"r": 1}, fresh=True)
    # 인게임 맵 흐름: 24 사이클째에 한 번 점검하고 DisplayText 를 낸다 (값은 selftest 케이스가 본다)
    s.reset()
    r = s.run("after", cycles=30)
    texts = [e for e in r.log if e[0] == "act" and e[1] == 9]
    s.expect_true("after", r.error is None, "실행 오류", str(r.error))
    s.expect_true("after", len(texts) == 1, "DisplayText 한 번", repr(texts))
    s.expect_true("after", len(r.steps) == 30 and max(r.steps) > 300 > r.steps[0], "24 사이클째에만 점검", repr(r.steps))
    return s.report()


EPS_NEEDLES = (
    "from eudext import cell as cell",
    "hp = _CGFW(lambda: [cell.Cell(100)], 1)[0]",
    "a, b = List2Assignable(_CGFW(lambda: [cell.CreateCcodes(2)], 2))",
    "hp.isub_sat(x)",
    "_ATTW(timer, 'v').__isub__(x)",
    "_ARRW(arr, i) << (v)",
    "_ARRW(arr, i).__iadd__(v)",
    "_ARRW(arr, i).__isub__(v)",
    "arr.isub_sat(i, v)",
    "_ARRC(arr, i) == v",
    "_ARRC(arr, i) >= v, neg=True",
    "_ARRW(kills, CurrentPlayer).__iadd__(1)",
    "cell.SetCD(a, x)",
    "cell.SubCD(b, x)",
    "cell.CD(a, 1, AtLeast)",
    "cell.f_cd(a, y, AtMost)",
    "timer.isub(timer)",
    "EUDTernary(hp >= x)",
    "hp.v",
)


def eps_checks(ck):
    with open(os.path.join(EX, "cell_example.eps"), encoding="utf-8") as f:
        src = f.read()
    out, nerr = _compat.eps_compile("cell_example.eps", src)
    ck.eq("eps 오류 수", nerr, 0)
    ck.true("eps 번역", out is not None)
    if out:
        for needle in EPS_NEEDLES:
            ck.true("eps 번역에 %s" % needle, needle in out)
    # 문서 안내 확인: const Cell 에 `-=`·`=` 는 번역 오류, `var y = c;` 는 번역은 되지만 빌드 때 오류
    for label, body in (("c -= 1", "c -= 1;"), ("c = 1", "c = 1;")):
        bad = "import eudext.cell as cell;\nconst c = cell.Cell(0);\nfunction f() { %s }\n" % body
        o, n = _compat.eps_compile("bad.eps", bad)
        ck.true("eps %s 는 번역 오류" % label, n > 0, repr((n, o)))
    good = ("import eudext.cell as cell;\nconst c = cell.Cell(0);\n"
            "function f(x) { c.v -= x; c.v = x; c.isub(x); c.assign(x); c.iadd(x); var y = c.v; return y; }\n")
    o, n = _compat.eps_compile("good.eps", good)
    ck.true("eps 통로 번역", n == 0 and o is not None and "c.assign(x)" in o and "_ATTW(c, 'v') << (x)" in o, repr(o))


def bad_var_build(ck):
    """`var y = c;`(const Cell 을 var 에 담기)는 빌드 때 오류이고 메시지에 Cell 안내(repr)가 보이는지."""
    from eudplib import CompressPayload, LoadMap

    from eudext.testing import emu
    from eudext.testing.harness import BASE_MAP

    src = "import eudext.cell as cell;\nconst c = cell.Cell(0);\nfunction f() { var y = c; return y; }\n"
    out, nerr = _compat.eps_compile("bad_var.eps", src)
    ck.true("bad var eps 번역", out is not None and nerr == 0)
    if not out:
        return
    ns = {}
    exec(compile(out, "bad_var.eps.py", "exec"), ns)  # noqa: S102 — 시험용 번역문
    LoadMap(BASE_MAP)
    CompressPayload(True)
    try:
        emu.Program(lambda: ns["f_f"]()).build()
        ck.true("var y = c 빌드 오류", False, "빌드가 됐다")
    except Exception as e:  # noqa: BLE001
        ck.true("var y = c 빌드 오류 안내", "c.read()" in str(e) or "const" in str(e), repr(e)[:300])


def euddraft_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    work = os.path.join(_common.WORK, "t_cell", "euddraft")
    eds, out_map = build.prepare_eds(os.path.join(EX, "cell_example.eds"), work)
    r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, "cell_example.log"))
    print("  " + r.summary())
    ck.true("euddraft ok", r.ok, r.log[-2000:])
    ck.true("euddraft freeze off", not r.freeze)
    ck.true("euddraft eps", '[epScript] Compiling "cell_example.eps"' in r.log, r.log[-1000:])
    ck.true("epspy in work", os.path.isfile(os.path.join(work, "__epspy__", "cell_example.py")))


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
            if f.endswith((".scx", ".pyc")) and not (rel == "testing" and f.startswith("base")):
                found.append(os.path.join(rel, f))
    return found


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py) — 조건 항목은 조건을 담는 소비 트리거 1개(Trigger)가 들어 있다
# ---------------------------------------------------------------------------------------------


def _mk_cell(t):
    return cell.Cell(0)


def _cw(fn, vk):
    def build(t):
        c = cell.Cell(0)
        v = {"k": 5, "v": None, "c": None, "s": c}[vk]
        if vk == "v":
            v = t.var("b")
        elif vk == "c":
            v = cell.Cell(3)
        fn(c, v)

    return build


def _cc(fn, vk):
    def build(t):
        c = cell.Cell(0)
        v = 5 if vk == "k" else t.var("b")
        Trigger(conditions=fn(c, v))

    return build


def _aw(fn, vk):
    def build(t):
        arr = cell.CellArray(8)
        i = t.var("i")
        v = 5 if vk == "k" else t.var("b")
        fn(arr, i, v)

    return build


def _ac(op, vk):
    def build(t):
        arr = cell.CellArray(8)
        i = t.var("i")
        v = 5 if vk == "k" else t.var("b")
        Trigger(conditions=getattr(arr, op)(i, v))

    return build


def _plain(fn):
    def build(t):
        fn(t)

    return build


K1 = {"call": 1}
V2 = {"call": 2}
C0 = {"call": 1}
C2 = {"call": 3}
V3 = {"call": 4}
AB = [{"b": 3}, {"b": 0xFFFFFFF0}]
IB = [{"i": 1, "b": 3}, {"i": 7, "b": 0xFFFFFFF0}]
I1 = [{"i": 1}, {"i": 7}]


def _pc_cp(t):
    pc = cell.PCell()
    pc.iadditem(CurrentPlayer, 1)


def _lv_isub(t):
    lv = EUDLightVariable()
    lv -= 5


def _v_isub(t):
    a = t.var("a")
    a -= t.var("b")


def _arr_ref_set(t):
    arr = EUDArray(8)
    arr[t.var("i")] = t.var("b")


def _arr_ref_isub(t):
    arr = EUDArray(8)
    arr.isubitem(t.var("i"), t.var("b"))


def _arr_ref_get(t):
    arr = EUDArray(8)
    t.out("r", arr[t.var("i")])


COST_CASES = [
    CostCase("Cell(상수) 만들기", _plain(lambda t: cell.Cell(5)), target={"call": 0}, note="4바이트 Db, 트리거 0"),
    CostCase("c << 상수", _cw(lambda c, v: c << v, "k"), target=K1),
    CostCase("c << 변수", _cw(lambda c, v: c << v, "v"), AB, target=V2),
    CostCase("c << 칸(Cell)", _cw(lambda c, v: c << v, "c"), note="칸을 f_dwread_epd 로 읽음"),
    CostCase("c += 상수", _cw(lambda c, v: c.__iadd__(v), "k"), target=K1),
    CostCase("c += 변수", _cw(lambda c, v: c.__iadd__(v), "v"), AB, target=V2),
    CostCase("c -= 상수 (wrap)", _cw(lambda c, v: c.__isub__(v), "k"), target=K1),
    CostCase("c -= 변수 (wrap)", _cw(lambda c, v: c.__isub__(v), "v"), AB, target={"call": 3},
             note="_parts.isub32 (EUDLightVariable 경로: 임시 변수에 −b)"),
    CostCase("c -= c (같은 칸)", _cw(lambda c, v: c.__isub__(v), "s"), target=K1, note="0 대입으로 접음"),
    CostCase("c.isub_sat(상수)", _cw(lambda c, v: c.isub_sat(v), "k"), target=K1),
    CostCase("c.isub_sat(변수)", _cw(lambda c, v: c.isub_sat(v), "v"), AB, target=V2),
    CostCase("c.read()", _plain(lambda t: t.out("r", cell.Cell(3).read())), note="eudplib f_dwread_epd (공유 본문은 이미 있음) + 대입"),
    CostCase("참고: EUDLightVariable -= 상수 (포화)", _plain(_lv_isub)),
    CostCase("참고: EUDVariable -= 변수 (wrap)", _plain(_v_isub), [{"a": 5, "b": 3}]),
    CostCase("c == 상수", _cc(lambda c, v: c == v, "k"), target=C0),
    CostCase("c != 5", _cc(lambda c, v: c != v, "k"), target=C2, note="자기 칸 깃발"),
    CostCase("c >= 변수", _cc(lambda c, v: c >= v, "v"), AB, target=V3),
    CostCase("c < 변수", _cc(lambda c, v: c < v, "v"), AB, target=V3),
    CostCase("c != 변수", _cc(lambda c, v: c != v, "v"), AB, target=V3, note="자기 칸 깃발"),
    CostCase("CD(c, 3, AtLeast)", _cc(lambda c, v: cell.CD(c, 3, AtLeast), "k"), target=C0),
    CostCase("CD(c, 변수)", _cc(lambda c, v: cell.CD(c, v), "v"), AB, target=V3),
    CostCase("CDX(c, 변수, 0xFF)", _cc(lambda c, v: cell.CDX(c, v, 0xFF), "v"), AB, target=V3),
    CostCase("DoActions(SetCD(c, 상수))", _cw(lambda c, v: DoActions(cell.SetCD(c, v)), "k"), target=K1),
    CostCase("DoActions(SetCD(c, 변수))", _cw(lambda c, v: DoActions(cell.SetCD(c, v)), "v"), AB, target=V2),
    CostCase("DoActions(SubCD(c, 변수))", _cw(lambda c, v: DoActions(cell.SubCD(c, v)), "v"), AB, target=V2),
    CostCase("arr[상수] << 변수", _aw(lambda arr, i, v: arr[3] << v, "v"), IB, target=V2),
    CostCase("arr[i] = 상수", _aw(lambda arr, i, v: arr.set(i, v), "k"), I1),
    CostCase("arr[i] = 변수", _aw(lambda arr, i, v: arr.set(i, v), "v"), IB),
    CostCase("arr.iadditem(i, 변수)", _aw(lambda arr, i, v: arr.iadditem(i, v), "v"), IB),
    CostCase("arr.isubitem(i, 상수) (wrap)", _aw(lambda arr, i, v: arr.isubitem(i, v), "k"), I1),
    CostCase("arr.isubitem(i, 변수) (wrap)", _aw(lambda arr, i, v: arr.isubitem(i, v), "v"), IB,
             note="−v 를 임시 변수로 만들고 더한다(마스크 Add 반전 기법을 쓰지 않음)"),
    CostCase("arr.isub_sat(i, 변수)", _aw(lambda arr, i, v: arr.isub_sat(i, v), "v"), IB),
    CostCase("arr[i] 읽기", _aw(lambda arr, i, v: arr.get(i), "k"), I1, note="EUDArray 와 같음"),
    CostCase("arr.eqitem(i, 상수)", _ac("eqitem", "k"), I1, target=V3),
    CostCase("arr.neitem(i, 5)", _ac("neitem", "k"), I1, target=V3, note="자기 칸 깃발"),
    CostCase("arr.geitem(i, 변수)", _ac("geitem", "v"), IB, target=V3),
    CostCase("arr.gtitem(i, 변수)", _ac("gtitem", "v"), IB, target=V3),
    CostCase("arr.neitem(i, 변수)", _ac("neitem", "v"), IB, target=V3, note="자기 칸 깃발"),
    CostCase("pc.iadditem(CurrentPlayer, 1)", _plain(_pc_cp), note="f_getcurpl() (캐시 확인 + 사본)"),
    CostCase("참고: EUDArray[i] = 변수", _plain(_arr_ref_set), IB),
    CostCase("참고: EUDArray.isubitem(i, 변수)", _plain(_arr_ref_isub), IB, note="eudplib: CP 옮기고 마스크 Add 반전"),
    CostCase("참고: EUDArray[i] 읽기", _plain(_arr_ref_get), I1),
]


def main():
    before = set(repo_artifacts())
    ck = Checker("t_cell (python)")
    eps = load_eps_example()
    py = {}
    oks = [suite_write(), suite_misc(py), suite_cond(), suite_array({}), suite_errors(), suite_eps(eps)]
    python_checks(ck)
    eps_checks(ck)
    euddraft_build(ck)
    bad_var_build(ck)
    ck.eq("repo clean", sorted(set(repo_artifacts()) - before), [])
    oks.append(ck.report())
    finish(*oks)


if __name__ == "__main__":
    main()
