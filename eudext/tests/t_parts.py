"""`_parts` 부품 차등 시험 (에뮬레이터): 분기·1회 분기·마스크 쓰기·and_const·32비트 뺄셈·CP 캐시·서브루틴.

python tests/t_parts.py
비용 표: python tools/cost.py tests/t_parts.py [--append --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: F401,E402
from _common import Checker, finish  # noqa: E402

from eudplib import (  # noqa: E402
    EPD,
    Add,
    DoActions,
    EUDLightVariable,
    EUDVariable,
    Forward,
    NextTrigger,
    RawTrigger,
    SetMemory,
    SetMemoryX,
    SeqCompute,
    SetTo,
    f_dwread_epd,
    f_getcurpl,
    f_setcurpl,
)

from eudext import _compat, _parts  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing.harness import EDGES32, Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
CONST_MASK = 0x00FF0F0F
PROBE_ADDR = 0x58A364 + 4 * 200  # 데스 표 빈 칸 (write_addr 시험용)


# ---------------------------------------------------------------------------------------------
# 분기 도우미: 경로를 path 칸에 남긴다 (1 = 참 경로, 2 = 거짓 경로)
# ---------------------------------------------------------------------------------------------


def _targets(path):
    T, F, E = Forward(), Forward(), Forward()
    return T, F, E


def _land(T, F, E, path):
    T << RawTrigger(nextptr=E, actions=path.SetNumber(1))
    F << RawTrigger(actions=path.SetNumber(2))
    E << NextTrigger()


def build_cases(s, py_errors):
    # --- branch ---
    @s.case("branch_const")
    def _(t):
        c, path, acted = t.var("c"), t.var("path"), t.var("acted")
        T, F, E = _targets(path)
        DoActions(acted.SetNumber(0))
        _parts.branch(c.Exactly(1), T, F, acts=[acted.SetNumber(7)])
        _land(T, F, E, path)

    @s.case("branch_var")
    def _(t):
        c, v, path, acted = t.var("c"), t.var("v"), t.var("path"), t.var("acted")
        T, F, E = _targets(path)
        DoActions(acted.SetNumber(0))
        _parts.branch(c.Exactly(1), T, F, acts=[acted.SetNumber(v)])
        _land(T, F, E, path)

    @s.case("branch_17conds")
    def _(t):
        c, path = t.var("c"), t.var("path")
        T, F, E = _targets(path)
        conds = [c.AtMost(100) for _ in range(16)] + [c.AtLeast(5)]  # 17개 → 두 덩어리
        _parts.branch(conds, T, F)
        _land(T, F, E, path)

    @s.case("branch_varcond")
    def _(t):
        c, k, path = t.var("c"), t.var("k"), t.var("path")
        T, F, E = _targets(path)
        _parts.branch(c.Exactly(k), T, F)  # 조건 필드가 변수 → 패치
        _land(T, F, E, path)

    @s.case("jump_if_var")
    def _(t):
        c, v, path, acted = t.var("c"), t.var("v"), t.var("path"), t.var("acted")
        skip = Forward()
        DoActions([acted.SetNumber(0), path.SetNumber(2)])
        _parts.jump_if(c.Exactly(1), skip, acts=[acted.SetNumber(v)])
        DoActions(path.SetNumber(3))  # 거짓이면 여기를 지난다
        skip << NextTrigger()

    @s.case("jump_if_not_const")
    def _(t):
        c, path, acted = t.var("c"), t.var("path"), t.var("acted")
        skip = Forward()
        DoActions([acted.SetNumber(0), path.SetNumber(2)])
        _parts.jump_if_not(c.Exactly(1), skip, acts=[acted.SetNumber(9)])
        DoActions(path.SetNumber(1))  # 참이면 여기를 지난다
        skip << NextTrigger()

    @s.case("jump_if_not_var")
    def _(t):
        c, v, path, acted = t.var("c"), t.var("v"), t.var("path"), t.var("acted")
        skip = Forward()
        DoActions([acted.SetNumber(0), path.SetNumber(2)])
        _parts.jump_if_not(c.Exactly(1), skip, acts=[acted.SetNumber(v)])
        DoActions(path.SetNumber(1))
        skip << NextTrigger()

    # --- once_branch ---
    def once_case(name, with_cond, var_acts):
        @s.case(name)
        def _(t):
            c, v, cnt, tc, fc = t.var("c"), t.var("v"), t.var("cnt"), t.var("tc"), t.var("fc")
            T, F, E = Forward(), Forward(), Forward()
            acts = [cnt.SetNumber(v)] if var_acts else [cnt.AddNumber(1)]
            conds = [c.Exactly(1)] if with_cond else []
            _parts.once_branch(conds, T, F, acts=acts)
            T << RawTrigger(nextptr=E, actions=tc.AddNumber(1))
            F << RawTrigger(actions=fc.AddNumber(1))
            E << NextTrigger()

    once_case("once_cond_const", True, False)
    once_case("once_cond_var", True, True)
    once_case("once_nocond_const", False, False)
    once_case("once_nocond_var", False, True)

    # --- set_masked / write_addr ---
    @s.case("set_masked_var_var")
    def _(t):
        _parts.set_masked(t.var("d"), t.var("v"), t.var("m"))

    @s.case("set_masked_var_const")
    def _(t):
        _parts.set_masked(t.var("d"), t.var("v"), CONST_MASK)

    @s.case("set_masked_const_var")
    def _(t):
        _parts.set_masked(t.var("d"), 0xA5A5A5A5, t.var("m"))

    @s.case("set_masked_const_const")
    def _(t):
        _parts.set_masked(t.var("d"), 0xA5A5A5A5, CONST_MASK)

    @s.case("set_masked_full")
    def _(t):
        _parts.set_masked(t.var("d"), t.var("v"), M32)

    @s.case("write_addr_var")
    def _(t):
        t.watch("mem", PROBE_ADDR)
        v = t.var("v")
        DoActions(SetMemory(PROBE_ADDR, SetTo, 0x12345678))
        _parts.write_addr(PROBE_ADDR, v, 0xFF00FF00)

    @s.case("write_addr_var_full")
    def _(t):
        t.watch("mem", PROBE_ADDR)
        _parts.write_addr(PROBE_ADDR, t.var("v"))

    @s.case("write_addr_cp")
    def _(t):
        v = t.var("v")
        _parts.write_addr(0x6509B0, v)
        t.out("got", f_getcurpl())
        f_setcurpl(0)
        try:
            _parts.write_addr(0x6509B0, v, 0xFF)
        except EudextError:
            py_errors.append("cp_mask_write")

    # --- and_const ---
    for mask in (0, M32, 0xF0F0F0F0, 0x80000001, 0x0000FFFF):

        @s.case("and_const_%08X" % mask)
        def _(t, mask=mask):
            a = t.var("a")
            t.out("r", _parts.and_const(a, mask))
            t.out("a_after", a)  # a 는 바뀌지 않아야 한다

    # --- 32비트 뺄셈 (S8: wrap / 포화, 같은 객체) ---
    def _light(t, name, src):
        lv = EUDLightVariable()
        t.watch(name, lv.getValueAddr())
        SeqCompute([(EPD(lv.getValueAddr()), SetTo, src)])
        return lv

    @s.case("isub32_var")
    def _(t):
        _parts.isub32(t.var("a"), t.var("b"))

    @s.case("isub_sat32_var")
    def _(t):
        _parts.isub_sat32(t.var("a"), t.var("b"))

    for k in (0, 1, 0x80000000, M32):

        @s.case("isub32_const_%08X" % k)
        def _(t, k=k):
            _parts.isub32(t.var("a"), k)

        @s.case("isub_sat32_const_%08X" % k)
        def _(t, k=k):
            _parts.isub_sat32(t.var("a"), k)

    @s.case("isub32_same")
    def _(t):
        a = t.var("a")
        _parts.isub32(a, a)
        lv = _light(t, "la", a)
        _parts.isub32(lv, lv)

    @s.case("isub_sat32_same")
    def _(t):
        a = t.var("a")
        _parts.isub_sat32(a, a)
        lv = _light(t, "la", a)
        _parts.isub_sat32(lv, lv)

    @s.case("eudplib_self_isub")
    def _(t):
        a = t.var("a")
        a -= a  # eudplib 버그 확인용 (0.81.0: 0xFFFFFFFF)

    @s.case("isub32_light")
    def _(t):
        a, b = t.var("a"), t.var("b")
        lv = _light(t, "la", a)
        _parts.isub32(lv, b)  # EUDLightVariable 의 eudplib `-=` 는 포화 → wrap 으로
        lk = _light(t, "lk", a)
        _parts.isub32(lk, 7)
        lr = _light(t, "lr", a)
        lr -= 7  # 참고: eudplib EUDLightVariable -= 상수는 포화 (-= 변수는 0.81 에서 빌드 오류)

    @s.case("isub_sat32_light")
    def _(t):
        a, b = t.var("a"), t.var("b")
        lv = _light(t, "la", a)
        _parts.isub_sat32(lv, b)
        lk = _light(t, "lk", a)
        _parts.isub_sat32(lk, 7)

    # --- cp_fix ---
    cache = _compat.cpcache_var()

    @s.case("cp_fix_on")
    def _(t):
        t.watch("cp", 0x6509B0)
        t.watch("cache", cache.getValueAddr())
        f_setcurpl(1)
        DoActions(_parts.cp_fix([SetMemory(0x6509B0, SetTo, 5), SetMemory(0x6509B0, Add, 2)]))
        t.out("rd", f_dwread_epd(EPD(0x58A364)))  # 끝에서 CP 를 캐시로 되돌리는 함수

    @s.case("cp_fix_off")
    def _(t):
        t.watch("cp", 0x6509B0)
        t.watch("cache", cache.getValueAddr())
        f_setcurpl(1)
        DoActions(SetMemory(0x6509B0, SetTo, 5))  # 캐시를 고치지 않은 원시 CP 쓰기
        t.out("rd", f_dwread_epd(EPD(0x58A364)))

    # --- call_sub ---
    @s.case("call_sub")
    def _(t):
        c, v = t.var("c"), t.var("v")
        hits, seq, x = t.var("hits"), t.var("seq"), t.var("x")
        sub = _parts.SubLabel("inc")
        late = _parts.SubLabel("late")  # 정의보다 호출이 먼저
        with sub.define():
            DoActions(hits.AddNumber(1))
        DoActions(seq.SetNumber(0))
        _parts.call_sub(sub)
        DoActions(seq.AddNumber(1))
        _parts.call_sub(sub, conds=c.Exactly(1))
        DoActions(seq.AddNumber(10))
        _parts.call_sub(sub, preserved=False)
        DoActions(seq.AddNumber(100))
        _parts.call_sub(late, acts=[x.SetNumber(v)])
        DoActions(seq.AddNumber(1000))
        with late.define():
            DoActions(x.AddNumber(1))
        try:
            with sub.define():
                pass
        except EudextError:
            py_errors.append("double_define")


def run_checks(s, py_errors):
    rng_inputs = {"d": None, "v": None, "m": None}

    # branch
    for name in ("branch_const", "branch_var"):
        for c in (0, 1, 2, M32):
            want_acted = (7 if name == "branch_const" else 0xDEADBEEF) if c == 1 else 0
            s.check(name, {"c": c, "v": 0xDEADBEEF} if name == "branch_var" else {"c": c},
                    {"path": 1 if c == 1 else 2, "acted": want_acted})
    for c in (0, 4, 5, 100, 101, M32):
        s.check("branch_17conds", {"c": c}, {"path": 1 if 5 <= c <= 100 else 2})
    for c, k in ((0, 0), (3, 3), (3, 4), (M32, M32), (0, M32)):
        s.check("branch_varcond", {"c": c, "k": k}, {"path": 1 if c == k else 2})
    for c in (0, 1):
        s.check("jump_if_var", {"c": c, "v": 0x13579BDF}, {"path": 2 if c == 1 else 3, "acted": 0x13579BDF if c == 1 else 0})
        s.check("jump_if_not_const", {"c": c}, {"path": 1 if c == 1 else 2, "acted": 9 if c == 1 else 0})
        s.check("jump_if_not_var", {"c": c, "v": 0x2468ACE0}, {"path": 1 if c == 1 else 2, "acted": 0x2468ACE0 if c == 1 else 0})

    # once_branch: 여러 사이클
    seq_c = [0, 1, 1, 0, 1]
    for name in ("once_cond_const", "once_cond_var", "once_nocond_const", "once_nocond_var"):
        s.reset()
        with_cond = "nocond" not in name
        rs = s.trace(name, [{"c": c, "v": 40 + i} for i, c in enumerate(seq_c)])
        first = seq_c.index(1) if with_cond else 0
        last = rs[-1].values
        want_cnt = (40 + first) if name.endswith("_var") else 1
        s.expect_true(name, last["cnt"] == want_cnt, "cnt", "cnt=%d 기대 %d" % (last["cnt"], want_cnt))
        s.expect_true(name, last["tc"] == 1, "tc", "tc=%d 기대 1" % last["tc"])
        s.expect_true(name, last["fc"] == len(seq_c) - 1, "fc", "fc=%d 기대 %d" % (last["fc"], len(seq_c) - 1))
        for i, r in enumerate(rs):
            s.expect_true(name, r.error is None, "cycle %d" % i, str(r.error))

    # set_masked
    def ref_mask(d, v, m):
        return {"d": (d & ~m | v & m) & M32}

    s.diff("set_masked_var_var", ref_mask, rng_inputs, n=120)
    s.diff("set_masked_var_const", lambda d, v: ref_mask(d, v, CONST_MASK), {"d": None, "v": None}, n=60)
    s.diff("set_masked_const_var", lambda d, m: ref_mask(d, 0xA5A5A5A5, m), {"d": None, "m": None}, n=60)
    s.diff("set_masked_const_const", lambda d: ref_mask(d, 0xA5A5A5A5, CONST_MASK), {"d": EDGES32}, n=20)
    s.diff("set_masked_full", lambda d, v: {"d": v}, {"d": None, "v": None}, n=40)
    s.diff("write_addr_var", lambda v: {"mem": (0x12345678 & ~0xFF00FF00 | v & 0xFF00FF00) & M32}, {"v": EDGES32}, n=40)
    s.diff("write_addr_var_full", lambda v: {"mem": v}, {"v": EDGES32}, n=20)
    for v in (0, 3, 7):
        s.check("write_addr_cp", {"v": v}, {"got": v}, fresh=True)
    s.reset()

    # and_const
    for mask in (0, M32, 0xF0F0F0F0, 0x80000001, 0x0000FFFF):
        s.diff("and_const_%08X" % mask, lambda a, mask=mask: {"r": a & mask, "a_after": a}, {"a": None}, n=60)

    # 32비트 뺄셈
    def wrap(a, b):
        return (a - b) & M32

    def sat(a, b):
        return max(a - b, 0)

    ab = {"a": EDGES32, "b": EDGES32}
    s.diff("isub32_var", lambda a, b: {"a": wrap(a, b)}, ab, n=150)
    s.diff("isub_sat32_var", lambda a, b: {"a": sat(a, b)}, ab, n=150)
    for k in (0, 1, 0x80000000, M32):
        s.diff("isub32_const_%08X" % k, lambda a, k=k: {"a": wrap(a, k)}, {"a": EDGES32}, n=30)
        s.diff("isub_sat32_const_%08X" % k, lambda a, k=k: {"a": sat(a, k)}, {"a": EDGES32}, n=30)
    for a in (0, 1, 5, 0x80000000, M32):
        s.check("isub32_same", {"a": a}, {"a": 0, "la": 0}, label="x -= x (a=0x%X)" % a)
        s.check("isub_sat32_same", {"a": a}, {"a": 0, "la": 0}, label="sat x -= x (a=0x%X)" % a)
        s.check("eudplib_self_isub", {"a": a}, {"a": M32}, label="eudplib v -= v 버그 (a=0x%X)" % a)
    # 경계: 0 − 1, 0xFFFFFFFF
    for a, b in ((0, 1), (0, M32), (M32, M32), (5, M32), (M32, 1), (1, 0), (0x80000000, 0x80000001)):
        s.check("isub32_var", {"a": a, "b": b}, {"a": wrap(a, b)}, label="wrap 0x%X-0x%X" % (a, b))
        s.check("isub_sat32_var", {"a": a, "b": b}, {"a": sat(a, b)}, label="sat 0x%X-0x%X" % (a, b))
    s.diff("isub32_light", lambda a, b: {"la": wrap(a, b), "lk": wrap(a, 7), "lr": sat(a, 7)}, ab, n=80)
    s.diff("isub_sat32_light", lambda a, b: {"la": sat(a, b), "lk": sat(a, 7)}, ab, n=80)

    # cp_fix: 고치면 CP=7(5+2) 유지, 안 고치면 읽기 함수가 CP 를 옛 캐시(1)로 되돌린다
    s.check("cp_fix_on", {}, {"cp": 7, "cache": 7}, fresh=True)
    s.check("cp_fix_off", {}, {"cp": 1, "cache": 1}, fresh=True)
    s.reset()

    # call_sub: 사이클 1 = 조건 없음 1 + 조건(c) + 1회 1 = hits, seq 는 복귀가 맞으면 1111
    s.reset()
    rs = s.trace("call_sub", [{"c": 1, "v": 50}, {"c": 0, "v": 60}, {"c": 1, "v": 70}])
    want_hits = [3, 4, 6]
    for i, r in enumerate(rs):
        s.expect_true("call_sub", r.error is None, "cycle %d err" % i, str(r.error))
        if r.error is None:
            s.expect_true("call_sub", r.values["hits"] == want_hits[i], "hits %d" % i, "hits=%d 기대 %d" % (r.values["hits"], want_hits[i]))
            s.expect_true("call_sub", r.values["seq"] == 1111, "seq %d" % i, "seq=%d" % r.values["seq"])
            s.expect_true("call_sub", r.values["x"] == 50 + 10 * i + 1, "x %d" % i, "x=%d" % r.values["x"])
    s.reset()


def python_checks(ck, py_errors):
    ck.true("cp mask write → EudextError", "cp_mask_write" in py_errors)
    ck.true("double define → EudextError", "double_define" in py_errors)
    ck.raises("cp_fix mask", EudextError, _parts.cp_fix, [SetMemoryX(0x6509B0, SetTo, 1, 0xFF)])
    acts = [SetMemory(0x58A364, SetTo, 1)]
    fixed = _parts.cp_fix(acts)
    ck.true("cp_fix passthrough", len(fixed) == 1 and fixed[0] is acts[0])
    ck.eq("cp_fix adds 2", len(_parts.cp_fix([SetMemory(0x6509B0, SetTo, 3)])), 3)
    v = EUDVariable()
    ck.true("all_const const", _parts.all_const([SetMemory(0x58A364, SetTo, 1)]))
    ck.true("all_const var", not _parts.all_const([SetMemory(0x58A364, SetTo, v)]))
    ck.eq("and_const const", _parts.and_const(0x1234, 0xFF), 0x34)
    ck.raises("and_const var mask", EudextError, _parts.and_const, v, v)
    ck.raises("set_masked non-var dst", EudextError, _parts.set_masked, 5, 1, 0xFF)
    ck.raises("isub32 non-var dst", EudextError, _parts.isub32, 5, 1)
    ck.raises("isub_sat32 non-var dst", EudextError, _parts.isub_sat32, 5, v)
    ck.eq("f_ aliases", (_parts.f_and_const, _parts.f_set_masked), (_parts.and_const, _parts.set_masked))
    ck.eq("EPD_CP", _parts.EPD_CP, EPD(0x6509B0))
    ck.eq("split64", _compat.split64_const(0x123456789), (0x23456789, 1))
    ck.eq("split64 neg", _compat.split64_const(-1), (M32, M32))
    ck.true("is_const/is_var", _compat.is_const(3) and not _compat.is_const(v) and _compat.is_var(v))


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py)
# ---------------------------------------------------------------------------------------------


def _cost_branch(var_acts):
    def build(t):
        c, v = t.var("c"), t.var("v")
        T, F = Forward(), Forward()
        _parts.branch(c.Exactly(1), T, F, acts=[t.var("a").SetNumber(v if var_acts else 7)])
        T << NextTrigger()
        F << NextTrigger()

    return build


def _cost_jump_if_not(var_acts):
    def build(t):
        c, v = t.var("c"), t.var("v")
        skip = Forward()
        _parts.jump_if_not(c.Exactly(1), skip, acts=[t.var("a").SetNumber(v if var_acts else 7)])
        skip << NextTrigger()

    return build


def _cost_once(with_cond):
    def build(t):
        c = t.var("c")
        T, F = Forward(), Forward()
        _parts.once_branch([c.Exactly(1)] if with_cond else [], T, F, acts=[t.var("a").AddNumber(1)])
        T << NextTrigger()
        F << NextTrigger()

    return build


def _cost_call_sub(t):
    sub = _parts.SubLabel("cost")
    with sub.define():
        DoActions(t.var("a").AddNumber(1))
    _parts.call_sub(sub)


def _cost_eud_and(t):
    t.var("a") & 0xF0F0F0F0


COST_CASES = [
    CostCase("branch (상수 액션)", _cost_branch(False), [{"c": 0}, {"c": 1}], note="거짓~참"),
    CostCase("branch (변수 액션)", _cost_branch(True), [{"c": 0}, {"c": 1}], note="거짓~참"),
    CostCase("jump_if_not (상수 액션)", _cost_jump_if_not(False), [{"c": 0}, {"c": 1}]),
    CostCase("jump_if_not (변수 액션)", _cost_jump_if_not(True), [{"c": 0}, {"c": 1}]),
    CostCase("once_branch (조건 있음)", _cost_once(True), [{"c": 0}, {"c": 1}], note="첫 참 사이클 기준"),
    CostCase("once_branch (조건 없음)", _cost_once(False), [{}], note="첫 사이클"),
    CostCase("set_masked (변수 값, 상수 마스크)", lambda t: _parts.set_masked(t.var("d"), t.var("v"), CONST_MASK)),
    CostCase("set_masked (변수 값, 변수 마스크)", lambda t: _parts.set_masked(t.var("d"), t.var("v"), t.var("m"))),
    CostCase("set_masked (상수 값, 상수 마스크)", lambda t: _parts.set_masked(t.var("d"), 5, CONST_MASK)),
    CostCase("write_addr (변수 값, 전체 마스크)", lambda t: _parts.write_addr(PROBE_ADDR, t.var("v"))),
    CostCase("and_const (0.81 `v & 상수` 감싸기)", lambda t: _parts.and_const(t.var("a"), 0xF0F0F0F0),
             note="DPS 판(마스크 칸 임시 변경)도 트리거 2 / 실행 3 으로 같음"),
    CostCase("참고: eudplib `v & 상수`", _cost_eud_and),
    CostCase("isub32 (변수)", lambda t: _parts.isub32(t.var("a"), t.var("b")), {"a": 3, "b": 5},
             note="eudplib `a -= b`"),
    CostCase("isub32 (상수)", lambda t: _parts.isub32(t.var("a"), 5), {"a": 3}),
    CostCase("isub32 (같은 객체)", lambda t: _parts.isub32(t.var("a"), t.var("a")), {"a": 3}, note="`a << 0`"),
    CostCase("isub32 (EUDLightVariable, 변수)", lambda t: _parts.isub32(EUDLightVariable(), t.var("b")), {"b": 5},
             note="임시 변수에 −b"),
    CostCase("isub_sat32 (변수)", lambda t: _parts.isub_sat32(t.var("a"), t.var("b")), {"a": 3, "b": 5}),
    CostCase("isub_sat32 (상수)", lambda t: _parts.isub_sat32(t.var("a"), 5), {"a": 3}),
    CostCase("cp_fix (CP 쓰기 1개)", lambda t: DoActions(_parts.cp_fix([SetMemory(0x6509B0, SetTo, 0)])),
             note="액션 +2"),
    CostCase("call_sub (조건 없음, 본문 1트리거)", _cost_call_sub, note="본문 1 + 끝 1 포함"),
]


def main():
    ck = Checker("t_parts (python)")
    py_errors = []
    s = Suite("t_parts")
    build_cases(s, py_errors)
    s.build()
    run_checks(s, py_errors)
    ok1 = s.report()
    python_checks(ck, py_errors)
    ok2 = ck.report()
    finish(ok1, ok2)


if __name__ == "__main__":
    main()
