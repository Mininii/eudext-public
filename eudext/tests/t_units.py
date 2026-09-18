"""`units` 시험 (에뮬레이터 + scmodel 유닛 모델): capture·실패 주입·index/slot·UnitData·new_units·clear_on_death·
dying, CUnit 표 스텁, epScript 예제 번역·에뮬레이터 실행·euddraft 빌드.

python tests/t_units.py            (--scx: scx 증가분만 재서 출력)
비용 표: python tools/cost.py tests/t_units.py [--append --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402

from eudplib import (  # noqa: E402
    Attack,
    CompressPayload,
    CreateUnit,
    DoActions,
    EUDBreak,
    EUDContinue,
    EUDDoEvents,
    EUDEndIf,
    EUDEndInfLoop,
    EUDIf,
    EUDInfLoop,
    EUDLoopNewUnit,
    EUDVariable,
    KillUnit,
    KillUnitAt,
    LoadMap,
    Order,
    P3,
    P8,
    RemoveUnit,
    RemoveUnitAt,
    SaveMap,
    ShufflePayload,
    UnitProperty,
    f_getcurpl,
    f_setcurpl,
)

from eudext import _compat, units  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import BASE_MAP, emu, scmodel  # noqa: E402
from eudext.testing.harness import Suite, rand32  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
TABLE = 0x59CCA8
EPD0 = 19025
SLOTS = 1701
PTR_MAX = TABLE + 336 * 1699
EPD_MAX = EPD0 + 84 * 1699
MASKS = {"dword": M32, "word": 0xFFFF, "byte": 0xFF}

# 시험용 표 (케이스 사이에 공유 — 주소는 probe 케이스가 잰다)
D = units.UnitData(dw="dword", w="word", b="byte", z=("dword", 0x12345678), wd=("word", 7))
D2 = units.UnitData(mark="dword", fl="byte")
D3 = units.UnitData(a="dword", k="byte", c=("word", 5))
D4 = units.UnitData(alive="byte", val="dword")
L = units.UnitData(v="dword")  # 순회 기록용
TABLES = {"D": D, "D2": D2, "D3": D3, "D4": D4, "L": L}


def ref_index(x):
    x &= M32
    if TABLE <= x <= PTR_MAX:
        return (x - TABLE) // 336
    if EPD0 <= x <= EPD_MAX:
        return (x - EPD0) // 84
    return 1700


# =============================================================================================
# 도우미: 표 메모리 읽기·쓰기
# =============================================================================================


class Env:
    def __init__(self, s):
        self.s = s
        self.m = s.machine
        self.model = scmodel.unit_model(self.m)
        self.base = {name: self.m.addr("probe.db_" + name) for name in TABLES}

    def fresh(self):
        self.s.reset()
        self.model.clear_log()
        self.model.clear_failures()

    def addr(self, tname, fname, i):
        data = TABLES[tname]
        k = data.fields.index(fname)
        return self.base[tname] + 4 * (k * SLOTS + i)

    def get(self, tname, fname, i):
        return self.m.dw(self.addr(tname, fname, i))

    def put(self, tname, fname, i, v):
        self.m.setdw(self.addr(tname, fname, i), v)

    def region(self, tname):
        data = TABLES[tname]
        out = {}
        for k, f in enumerate(data.fields):
            dflt = data.field(f).default
            for i in range(SLOTS):
                v = self.m.dw(self.base[tname] + 4 * (k * SLOTS + i))
                if v != dflt:
                    out[(f, i)] = v
        return out

    def log(self, n):
        return [self.get("L", "v", j) for j in range(n)]


# =============================================================================================
# 케이스
# =============================================================================================


def build_cases(s):
    @s.case("probe")
    def _(t):
        for name, data in TABLES.items():
            t.watch("db_" + name, data._db)

    # --- capture ---
    @s.case("cap")
    def _(t):
        cpin, unit = t.var("cpin"), t.var("unit")
        f_setcurpl(cpin)
        with units.capture() as u:
            D.dw.set(u.index_before, 0xABCD)  # on_create 자리
            DoActions(CreateUnit(1, unit, "Anywhere", P8))
        t.out("ptr", u.ptr)
        t.out("epd", u.epd)
        t.out("idx", u.index)
        t.flag("ok", u.ok)
        t.flag("failed", u.failed)
        t.out("cpout", f_getcurpl())
        t.watch("rawcp", 0x6509B0)

    @s.case("cap_multi")
    def _(t):
        cnt = t.var("cnt")
        u = units.Capture()
        u.begin()
        DoActions(CreateUnit(cnt, "Terran Marine", "Anywhere", P3))
        u.end()
        t.out("idx", u.index)
        t.flag("ok", u.ok)

    @s.case("cap_member")
    def _(t):
        with units.capture() as u:
            DoActions(CreateUnit(1, "Terran Marine", "Anywhere", P8))
        if EUDIf()(u.ok):
            u.cunit.removeTimer = 777
            t.out("owner", u.cunit.playerID)
        EUDEndIf()

    @s.case("create_props")
    def _(t):
        u = units.create(1, "Terran Marine", 1, P3, props=UnitProperty(hitpoint=50), on_create=D)
        t.out("idx", u.index)
        t.flag("ok", u.ok)

    @s.case("create_fn")
    def _(t):
        v = t.var("v")
        u = units.create(1, "Terran Marine", "Anywhere", P8, on_create=lambda i: D2.mark.set(i, v))
        t.out("idx", u.index)
        into = units.Capture()
        u2 = units.create(1, "Terran Marine", "Anywhere", P8, on_create=[D2], into=into)
        t.out("same", 1 if u2 is into else 0)
        t.out("idx2", u2.index)

    @s.case("next_slot")
    def _(t):
        p, e, i = units.next_slot()
        t.out("p", p)
        t.out("e", e)
        t.out("i", i)

    # --- index / slot ---
    @s.case("index")
    def _(t):
        t.out("r", units.index(t.var("x")))

    @s.case("index_cunit")
    def _(t):
        t.out("r", units.index(units.CUnit(t.var("x"))))

    @s.case("slot")
    def _(t):
        p, e = units.slot(t.var("i"))
        t.out("p", p)
        t.out("e", e)

    # --- UnitField ---
    for fname in ("dw", "w", "b"):
        f = D.field(fname)

        @s.case("set_" + fname)
        def _(t, f=f):
            i, v = t.var("i"), t.var("v")
            f.set(i, v)
            t.out("r", f.get(i))

        @s.case("iadd_" + fname)
        def _(t, f=f):
            f.iadd(t.var("i"), t.var("v"))

        @s.case("isub_" + fname)
        def _(t, f=f):
            f.isub(t.var("i"), t.var("v"))

        @s.case("isubsat_" + fname)
        def _(t, f=f):
            f.isub_sat(t.var("i"), t.var("v"))

        @s.case("cconst_" + fname)
        def _(t, f=f):
            # 상수 칸·상수 값·변수 칸+상수 값 조합: 칸 3 ← v, 칸 i += 1000003, 칸 i -= 7, 칸 5 포화 −9, 칸 6 set 상수
            f.set(3, t.var("v"))
            f.iadd(t.var("i"), 1000003)
            f.isub(t.var("i"), 7)
            f.isub_sat(5, 9)
            f.set(6, 0x12345)
            f.iadd(7, t.var("v"))
            f.isub(8, t.var("v"))

        @s.case("bits_" + fname)
        def _(t, f=f):
            i = t.var("i")
            f.iand(i, 0xF0F0F0F0)
            f.ior(i, 0x0000030C)
            f.iand(9, 0x0FF0)
            f.ior(10, 0x10001)

        @s.case("cond_" + fname)
        def _(t, f=f):
            i, v = t.var("i"), t.var("v")
            t.flag("eq", f.eq(i, v))
            t.flag("ne", f.ne(i, v))
            t.flag("le", f.le(i, v))
            t.flag("ge", f.ge(i, v))
            t.flag("lt", f.lt(i, v))
            t.flag("gt", f.gt(i, v))
            t.flag("eqc", f.eq(i, 300))
            t.flag("gec", f.ge(i, 300))
            t.flag("eq4", f.eq(4, v))
            t.flag("lt4", f.lt(4, v))

    @s.case("pyop")
    def _(t):
        i, v = t.var("i"), t.var("v")
        D.w[i] += v  # 읽고 쓰기 (비싼 모양이지만 맞아야 한다)
        D.b[i] = D.b[i] + v

    @s.case("same_var")
    def _(t):
        i = t.var("i")
        D.dw[i] = i
        D.w.iadd(i, i)
        t.flag("eq", D.dw.eq(i, i))

    # --- UnitRow ---
    @s.case("row")
    def _(t):
        e, v = t.var("e"), t.var("v")
        r = D.of(e)
        r.w = v
        r.b += 3
        r.iaddattr("dw", v)
        r.isubattr("z", 1)
        r.isub_sat("wd", 100)
        t.out("rw", r.w)
        t.flag("eq", r.eqattr("w", v & 0xFFFF))
        t.flag("gt", r.gtattr("b", 2))
        t.out("idx", r.index)

    @s.case("row_at")
    def _(t):
        r = D.at(t.var("i"))
        r.dw = 0x55
        t.out("r", r.dw)
        r2 = D.at(12)
        r2.b = 0x1FF
        r2.clear()

    # --- clear ---
    @s.case("clear")
    def _(t):
        D.clear(t.var("i"))
        D.clear(11)
        D.clear(1700)

    @s.case("cp_ops")
    def _(t):
        i, v = t.var("i"), t.var("v")
        f_setcurpl(t.var("cpin"))
        D.w.iadd(i, v)
        D.b.set(i, v)
        D.clear(t.var("j"))
        D.w.iadd(i, 3)
        t.out("cpout", f_getcurpl())
        t.watch("rawcp", 0x6509B0)

    # --- new_units ---
    @s.case("newu")
    def _(t):
        n, sm, se, sp = t.var("n"), t.var("sum"), t.var("se"), t.var("sp")
        DoActions(n.SetNumber(0), sm.SetNumber(0), se.SetNumber(0), sp.SetNumber(0))
        for nu in units.new_units(clear=D2):
            L.v.set(n, nu.index)
            n += 1
            sm += nu.index
            se += nu.epd
            sp += nu.ptr
            D2.fl.set(nu, 1)

    @s.case("newu_unpack")
    def _(t):
        n = t.var("n")
        DoActions(n.SetNumber(0))
        for _ptr, epd, i in units.new_units(allowance=3):
            L.v.set(n, i)
            n += 1

    @s.case("eud_newunit")
    def _(t):
        n = t.var("n")
        DoActions(n.SetNumber(0))
        for _ptr, _epd in EUDLoopNewUnit():
            n += 1

    # --- clear_on_death / dying ---
    @s.case("cod20")
    def _(t):
        units.clear_on_death(D3)

    @s.case("cod17")
    def _(t):
        units.clear_on_death(D3, chunk=17)

    @s.case("cod1")
    def _(t):
        units.clear_on_death(D3, chunk=1)

    @s.case("codkey")
    def _(t):
        units.clear_on_death(D3, key="k", chunk=50)

    @s.case("cod2")
    def _(t):
        units.clear_on_death(D3, D2)

    for label, chunk, mode, limit in (("dying", 20, None, None), ("dying50", 50, None, None), ("dying1", 1, None, None),
                                      ("dying_break", 20, "break", None), ("dying_cont", 20, "cont", None),
                                      ("dying_limit", 34, None, 2)):

        @s.case(label)
        def _(t, chunk=chunk, mode=mode, limit=limit):
            n, se, sp, sv = t.var("n"), t.var("se"), t.var("sp"), t.var("sv")
            DoActions(n.SetNumber(0), se.SetNumber(0), sp.SetNumber(0), sv.SetNumber(0))
            for d in units.dying(D4, key="alive", chunk=chunk, limit=limit):
                L.v.set(n, d.index)
                n += 1
                se += d.epd
                sp += d.ptr
                sv += D4.val[d]
                if mode == "break":
                    EUDBreak()
                elif mode == "cont":
                    if EUDIf()(n.AtLeast(1)):
                        EUDContinue()
                    EUDEndIf()
                    sv += 1000000  # 건너뛰는 자리

    # --- 유닛 액션 ---
    @s.case("kill")
    def _(t):
        DoActions(KillUnit("Terran Marine", P8))

    @s.case("killat")
    def _(t):
        DoActions(KillUnitAt(2, "Terran Marine", 1, P8))

    @s.case("remove")
    def _(t):
        DoActions(RemoveUnit("Any unit", P3))

    @s.case("removeat")
    def _(t):
        DoActions(RemoveUnitAt(0, "Any unit", 1, P3))

    @s.case("order")
    def _(t):
        DoActions(Order("Terran Marine", P8, 1, Attack, 2))


# =============================================================================================
# 판정
# =============================================================================================


def run_capture(s, env, rng):
    model = env.model
    name = "cap"

    def scenario(label, head, unit=0, fail=False, fill=False, short=False, cp=0):
        env.fresh()
        if fill:
            model.fill()
        elif short:
            model.set_free([head])
        else:
            model.set_free(list(range(head, 1700)) + list(range(0, head)))
        if fail:
            model.fail_next(1)
        active0 = model.active_list()
        before = env.region("D")
        r = s.run(name, {"cpin": cp, "unit": unit})
        if r.error:
            s.expect_true(name, False, label, r.error)
            return
        v = r.values
        rec = model.created[-1] if model.created else None
        has_slot = not fill
        created = has_slot and not fail and not (short and unit in scmodel.DEFAULT_SUBUNITS)
        want_ptr = TABLE + 336 * head if has_slot else 0
        want = {
            "ptr": want_ptr,
            "epd": EPD0 + 84 * head if has_slot else 0,
            "idx": head if has_slot else 1700,
            "ok": 1 if created else 0,
            "failed": 0 if created else 1,
            "cpout": cp,
            "rawcp": cp,
        }
        bad = {k: (v[k], w) for k, w in want.items() if v[k] != w}
        s.expect_true(name, not bad, label, "틀림 %r" % bad)
        s.expect_true(name, rec is not None and rec.ok == created and rec.player == 7 and rec.loc == 64
                      and rec.unit == unit, label + " 기록", repr(rec))
        widx = head if has_slot else 1700
        after = env.region("D")
        want_region = dict(before)
        want_region[("dw", widx)] = 0xABCD
        s.expect_true(name, after == want_region, label + " on_create 칸", "%r" % (set(after.items()) ^ set(want_region.items())))
        if created:
            nxt = head + (2 if unit in scmodel.DEFAULT_SUBUNITS else 1)
            nxt = None if short else (nxt if nxt < 1700 else nxt - 1700)
            s.expect_true(name, model.next_free() == nxt, label + " 0x628438 이동",
                          "next=%r" % model.next_free())
            s.expect_true(name, model.unit_type(head) == unit and model.owner(head) == 7 and model.alive(head),
                          label + " CUnit", "type=%d owner=%d" % (model.unit_type(head), model.owner(head)))
            s.expect_true(name, rec.indices == (head,), label + " indices", repr(rec))
            if unit in scmodel.DEFAULT_SUBUNITS:
                sub = rec.subs[0]
                s.expect_true(name, model.sub_unit(head) == model.ptr(sub) and model.unit_type(sub) == scmodel.DEFAULT_SUBUNITS[unit],
                              label + " 터렛", repr(rec))
        else:
            s.expect_true(name, model.active_list() == active0, label + " 활성 목록 그대로", repr(model.active_list()))
            s.expect_true(name, (model.next_free() if has_slot else None) == (head if has_slot else None),
                          label + " 0x628438 그대로", repr(model.next_free()))

    scenario("정상 0", 0)
    scenario("정상 1699", 1699)
    scenario("CP 5", 17, cp=5)
    scenario("실패 주입", 40, fail=True)
    scenario("빈 칸 없음", 0, fill=True)
    scenario("골리앗", 100, unit=3)
    scenario("탱크 끝", 1698, unit=5)
    scenario("골리앗 칸 부족", 33, unit=3, short=True)
    scenario("마린 칸 하나", 33, unit=0, short=True)
    for k in range(40):
        scenario("무작위 %d" % k, rng.randrange(1700), unit=rng.choice((0, 0, 7, 3)), fail=rng.random() < 0.3,
                 cp=rng.randrange(8))

    # 조건부 실패 주입: 유닛 7 만 실패
    env.fresh()
    model.fail_when(lambda rec: rec.unit == 7)
    r1 = s.run(name, {"unit": 7})
    r2 = s.run(name, {"unit": 0})
    s.expect_true(name, r1.values["ok"] == 0 and r2.values["ok"] == 1 and r1.values["idx"] == 0 and r2.values["idx"] == 0,
                  "fail_when", "%r %r" % (r1.values, r2.values))
    # 연달아 생성: 칸이 차례로
    env.fresh()
    idxs = [s.run(name, {"unit": 0}).values["idx"] for _ in range(5)]
    s.expect_true(name, idxs == [0, 1, 2, 3, 4], "연속 생성", repr(idxs))

    # 여러 마리
    env.fresh()
    model.set_free(range(10, 1700))
    r = s.run("cap_multi", {"cnt": 3})
    rec = model.created[-1]
    s.expect_true("cap_multi", r.values == {"cnt": 3, "idx": 10, "ok": 1} and rec.indices == (10, 11, 12) and rec.player == 2,
                  "3마리", "%r %r" % (r.values, rec))
    model.set_free([500])
    r = s.run("cap_multi", {"cnt": 3})
    rec = model.created[-1]
    s.expect_true("cap_multi", r.values["idx"] == 500 and r.values["ok"] == 1 and rec.indices == (500,),
                  "칸 하나에 3마리", "%r %r" % (r.values, rec))

    # CUnit 멤버 쓰기·읽기
    env.fresh()
    model.set_free(range(50, 1700))
    r = s.run("cap_member")
    s.expect_true("cap_member", not r.error and model.get(50, 0x110, 2) == 777 and r.values["owner"] == 7,
                  "removeTimer/playerID", "%r timer=%d" % (r.values, model.get(50, 0x110, 2)))

    # create + props + on_create=UnitData + 로케이션 중심
    env.fresh()
    model.set_location(1, 64, 96, 128, 160)
    for f in D.fields:
        env.put("D", f, 0, 0xFFFF)
        env.put("D", f, 1, 0xEEEE)
    r = s.run("create_props")
    rec = model.created[-1]
    row0 = {f: env.get("D", f, 0) for f in D.fields}
    s.expect_true("create_props", r.values == {"idx": 0, "ok": 1}, "결과", repr(r.values))
    s.expect_true("create_props", rec.action == "CreateUnitWithProperties" and rec.props is not None and rec.loc == 1 and rec.player == 2,
                  "기록", repr(rec))
    s.expect_true("create_props", model.pos(0) == (96, 128), "로케이션 중심", repr(model.pos(0)))
    s.expect_true("create_props", row0 == {"dw": 0, "w": 0, "b": 0, "z": 0x12345678, "wd": 7}, "on_create=UnitData 초기화",
                  repr(row0))
    s.expect_true("create_props", env.get("D", "w", 1) == 0xEEEE, "옆 칸 그대로")

    env.fresh()
    env.put("D2", "fl", 1, 0x99)
    r = s.run("create_fn", {"v": 0x5151})
    s.expect_true("create_fn", r.values["idx"] == 0 and r.values["idx2"] == 1 and r.values["same"] == 1
                  and env.get("D2", "mark", 0) == 0x5151 and env.get("D2", "fl", 1) == 0,
                  "on_create 함수·목록·into", "%r fl1=%d" % (r.values, env.get("D2", "fl", 1)))

    env.fresh()
    for head in (0, 1, 1024, 1699):
        model.set_free([head])
        r = s.run("next_slot")
        s.expect_true("next_slot", r.values == {"p": TABLE + 336 * head, "e": EPD0 + 84 * head, "i": head},
                      "head %d" % head, repr(r.values))
    model.fill()
    r = s.run("next_slot")
    s.expect_true("next_slot", r.values == {"p": 0, "e": 0, "i": 1700}, "빈 칸 없음", repr(r.values))
    env.fresh()


def run_index(s, env, rng):
    edges = [0, 1, TABLE - 1, TABLE, TABLE + 1, TABLE + 335, TABLE + 336, PTR_MAX, PTR_MAX + 1, PTR_MAX + 336,
             EPD0 - 1, EPD0, EPD0 + 83, EPD0 + 84, EPD_MAX, EPD_MAX + 1, EPD_MAX + 84, 0x7FFFFFFF, M32,
             TABLE + 336 * 1024, EPD0 + 84 * 1023]

    def gen(rng):
        r = rng.random()
        if r < 0.4:
            return TABLE + 336 * rng.randrange(1700)
        if r < 0.8:
            return EPD0 + 84 * rng.randrange(1700)
        return rand32(rng)

    s.diff("index", lambda x: {"r": ref_index(x)}, {"x": edges}, n=300)
    for x in [EPD0, EPD0 + 84 * 5, EPD_MAX]:
        s.check("index_cunit", {"x": x}, {"r": ref_index(x)})
    s.diff("index", lambda x: {"r": ref_index(x)}, {"x": gen}, n=300, edges=False, seed=7)
    slot_ref = lambda i: {"p": TABLE + 336 * i, "e": EPD0 + 84 * i}  # noqa: E731
    s.diff("slot", slot_ref, {"i": [0, 1, 2, 511, 512, 1023, 1024, 1698, 1699]}, n=0)
    s.diff("slot", slot_ref, {"i": lambda rng: rng.randrange(1700)}, n=200, edges=False, seed=3)


def _field_cases(env, rng, kind):
    mask = MASKS[kind]
    idxs = [0, 1, 2, 1698, 1699, 1700]
    vals = [0, 1, 2, 0xFF, 0x100, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, M32]
    olds = [0, 1, mask, mask - 1, mask >> 1]
    combos = []
    for i in idxs:
        for v in vals:
            combos.append((i, v, rng.choice(olds)))
    for _ in range(60):
        combos.append((rng.randrange(1701), rand32(rng), rng.randrange(mask + 1) if mask != M32 else rand32(rng)))
    return combos


def run_fields(s, env, rng):
    for fname, kind in (("dw", "dword"), ("w", "word"), ("b", "byte")):
        mask = MASKS[kind]
        refs = {
            "set": lambda old, v: v & mask,
            "iadd": lambda old, v: (old + v) & mask,
            "isub": lambda old, v: (old - v) & mask,
            "isubsat": lambda old, v: max(old - v, 0),
        }
        for op, ref in refs.items():
            name = "%s_%s" % (op, fname)
            for n, (i, v, old) in enumerate(_field_cases(env, rng, kind)):
                env.fresh()
                env.put("D", fname, i, old)
                full = n % 3 == 0  # 셋에 하나는 표 전체, 나머지는 이웃 칸만 본다(시간)
                near = [(f, j) for f in D.fields for j in (i - 1, i, i + 1) if 0 <= j <= 1700]
                before = env.region("D") if full else {k: env.get("D", *k) for k in near}
                r = s.run(name, {"i": i, "v": v})
                label = "i=%d v=0x%X old=0x%X" % (i, v, old)
                if r.error:
                    s.expect_true(name, False, label, r.error)
                    continue
                want = ref(old, v)
                got = env.get("D", fname, i)
                ok = got == want
                if op == "set":
                    ok = ok and r.values["r"] == want
                after = env.region("D") if full else {k: env.get("D", *k) for k in near}
                exp = dict(before)
                if full:
                    exp.pop((fname, i), None)
                    if want != 0:
                        exp[(fname, i)] = want
                else:
                    exp[(fname, i)] = want
                ok = ok and after == exp
                s.expect_true(name, ok, label, "got=0x%X want=0x%X diff=%r" % (got, want, set(after.items()) ^ set(exp.items())))

        # 상수 칸·상수 값 조합
        name = "cconst_" + fname
        for i, v in ((0, 5), (100, 0xFFFFFFF0), (1699, 0x12345678), (1700, 3)):
            env.fresh()
            for c in (3, 5, 6, 7, 8):
                env.put("D", fname, c, 4 & mask)
            env.put("D", fname, i, 0x10 & mask)
            r = s.run(name, {"i": i, "v": v})
            exp = {3: v & mask, 5: 0, 6: 0x12345 & mask, 7: (4 + v) & mask, 8: (4 - v) & mask}
            if i not in exp:
                exp[i] = ((0x10 & mask) + 1000003 - 7) & mask
            got = {c: env.get("D", fname, c) for c in exp}
            s.expect_true(name, not r.error and got == exp, "i=%d v=0x%X" % (i, v), "%r vs %r %s" % (got, exp, r.error))

        # 비트
        name = "bits_" + fname
        for i in (0, 9, 10, 1699, 1700):
            for old in (0, mask, 0x1234 & mask, 0x0F0F0F0F & mask):
                env.fresh()
                env.put("D", fname, i, old)
                env.put("D", fname, 9, old)
                env.put("D", fname, 10, old)
                r = s.run(name, {"i": i})
                w9 = old & 0x0FF0
                w10 = old | (0x10001 & mask)
                wi = ((old & 0xF0F0F0F0) | (0x30C & mask)) & mask
                if i == 9:
                    w9 = wi & 0x0FF0
                elif i == 10:
                    w10 = wi | (0x10001 & mask)
                got = (env.get("D", fname, i), env.get("D", fname, 9), env.get("D", fname, 10))
                want = (w9 if i == 9 else w10 if i == 10 else wi, w9, w10)
                s.expect_true(name, not r.error and got == want, "i=%d old=0x%X" % (i, old), "%r vs %r" % (got, want))

        # 조건
        name = "cond_" + fname
        combos = []
        for old in (0, 1, 299, 300, 301, mask):
            for v in (0, 1, 299, 300, 301, mask, M32):
                combos.append((rng.choice((0, 4, 77, 1699, 1700)), v, old))
        for _ in range(40):
            combos.append((rng.randrange(1701), rand32(rng) & mask if rng.random() < 0.5 else rand32(rng), rng.randrange(mask + 1) if mask != M32 else rand32(rng)))
        for i, v, old in combos:
            env.fresh()
            env.put("D", fname, i, old)
            if i != 4:
                env.put("D", fname, 4, (old + 1) & mask)
            o4 = env.get("D", fname, 4)
            r = s.run(name, {"i": i, "v": v})
            want = {"eq": old == v, "ne": old != v, "le": old <= v, "ge": old >= v, "lt": old < v, "gt": old > v,
                    "eqc": old == 300, "gec": old >= 300, "eq4": o4 == v, "lt4": o4 < v}
            got = {k: bool(r.values.get(k)) for k in want}
            s.expect_true(name, not r.error and got == want, "i=%d v=0x%X old=0x%X" % (i, v, old),
                          "%r %s" % ({k for k in want if got[k] != want[k]}, r.error))

    # 파이썬 연산자 모양
    for i, v, old in ((0, 5, 0xFFFE), (1699, 0x10003, 7), (33, M32, 1)):
        env.fresh()
        env.put("D", "w", i, old)
        env.put("D", "b", i, old & 0xFF)
        r = s.run("pyop", {"i": i, "v": v})
        got = (env.get("D", "w", i), env.get("D", "b", i))
        want = ((old + v) & 0xFFFF, ((old & 0xFF) + v) & 0xFF)
        s.expect_true("pyop", not r.error and got == want, "i=%d" % i, "%r vs %r" % (got, want))
    # 같은 변수를 칸 번호와 값에 함께
    for i in (0, 7, 1699):
        env.fresh()
        env.put("D", "w", i, 0xFFFF)
        r = s.run("same_var", {"i": i})
        got = (env.get("D", "dw", i), env.get("D", "w", i), r.values["eq"])
        s.expect_true("same_var", not r.error and got == (i, (0xFFFF + i) & 0xFFFF, 1), "i=%d" % i, repr(got))


def run_rows(s, env, rng):
    for e, i in ((EPD0, 0), (EPD0 + 84 * 9, 9), (EPD_MAX, 1699), (TABLE + 336 * 44, 44), (5, 1700), (0, 1700)):
        for v in (0, 7, 0x1FFFF):
            env.fresh()
            env.put("D", "b", i, 2)
            env.put("D", "dw", i, 10)
            r = s.run("row", {"e": e, "v": v})
            got = {f: env.get("D", f, i) for f in D.fields}
            want = {"dw": (10 + v) & M32, "w": v & 0xFFFF, "b": 5, "z": 0x12345677, "wd": 0}
            ok = not r.error and got == want and r.values["rw"] == v & 0xFFFF and r.values["eq"] == 1 \
                and r.values["gt"] == 1 and r.values["idx"] == i
            s.expect_true("row", ok, "e=0x%X v=0x%X" % (e, v), "%r %r %s" % (got, r.values, r.error))
    for i in (0, 13, 1699):
        env.fresh()
        r = s.run("row_at", {"i": i})
        ok = not r.error and r.values["r"] == 0x55 and env.get("D", "dw", i) == 0x55 and env.get("D", "b", 12) == 0 \
            and env.get("D", "wd", 12) == 7
        s.expect_true("row_at", ok, "i=%d" % i, "%r" % r.values)

    # clear
    for i in (0, 1, 11, 1698, 1699, 1700, 500):
        env.fresh()
        for j in (i - 1, i, i + 1, 11, 1700):
            if 0 <= j <= 1700:
                for f in D.fields:
                    env.put("D", f, j, 0xAAAA0000 + j)
        r = s.run("clear", {"i": i})
        reg = env.region("D")
        want = {}
        for j in (i - 1, i + 1):
            if 0 <= j <= 1700 and j not in (i, 11, 1700):
                for f in D.fields:
                    want[(f, j)] = 0xAAAA0000 + j
        s.expect_true("clear", not r.error and reg == want, "i=%d" % i, "%r" % (set(reg.items()) ^ set(want.items())))

    for cp in (0, 3, 7):
        env.fresh()
        r = s.run("cp_ops", {"i": 40, "v": 0x1FF, "cpin": cp, "j": 41})
        got = (r.values["cpout"], r.values["rawcp"], env.get("D", "w", 40), env.get("D", "b", 40))
        s.expect_true("cp_ops", not r.error and got == (cp, cp, 0x202, 0xFF), "cp=%d" % cp, repr(got))


def ref_new_units(model, shadow, allowance=2):
    out, tos = [], 0
    for i in model.active_list():
        u = model.uniq(i)
        if u != shadow.get(i, 0):
            shadow[i] = u
            out.append(i)
        else:
            tos += 1
            if tos >= allowance:
                break
    return out


def run_new_units(s, env, rng):
    model = env.model
    name = "newu"
    env.fresh()
    shadow = {}

    def step(label, check_clear=()):
        want = ref_new_units(model, shadow)
        for i in check_clear:
            env.put("D2", "mark", i, 0x77)
        r = s.run(name)
        n = r.values["n"]
        got = env.log(min(n, 64))
        ok = not r.error and got == want and r.values["sum"] == sum(want) \
            and r.values["se"] == sum(EPD0 + 84 * i for i in want) & M32 \
            and r.values["sp"] == sum(TABLE + 336 * i for i in want) & M32
        ok = ok and all(env.get("D2", "fl", i) == 1 for i in want)
        ok = ok and all(env.get("D2", "mark", i) == (0 if i in want else 0x77) for i in check_clear)
        s.expect_true(name, ok, label, "got=%r want=%r %r %s" % (got, want, r.values, r.error))

    step("빈 표")
    a = model.spawn(0, 7)
    b = model.spawn(0, 7)
    c = model.spawn(0, 7)
    step("셋 생성", check_clear=(a, b))
    step("변화 없음")
    d = model.spawn(1, 0)
    step("하나 더")
    model.kill(c)
    step("죽는 중 (새 유닛 아님)")
    model.process_deaths()
    e = model.spawn(0, 7)
    step("죽은 뒤 생성")
    model.set_free([c] + [i for i in model.free_list() if i != c])
    f = model.spawn(0, 7)
    s.expect_true(name, f == c and model.uniq(c) == 2, "칸 재사용 준비", "f=%d uniq=%d" % (f, model.uniq(c)))
    step("칸 재사용 (고유 바이트 +1)", check_clear=(c,))
    for _ in range(12):
        model.spawn(0, 7)
    step("12마리 한꺼번에")
    # CreateUnit 액션으로 만든 유닛도 다음 사이클에 나온다
    s.run("cap", {"unit": 0})
    step("트리거 생성 뒤")
    # 무작위
    for k in range(30):
        for _ in range(rng.randrange(4)):
            alive = model.units()
            r = rng.random()
            if r < 0.5 or not alive:
                if model.next_free() is not None:
                    model.spawn(rng.choice((0, 3)), rng.randrange(8))
            elif r < 0.8:
                model.kill(rng.choice(alive))
            else:
                model.process_deaths()
        step("무작위 %d" % k)
    _ = (d, e)

    # 풀어 쓰기 + allowance 3
    env.fresh()
    shadow = {}
    for _ in range(3):
        model.spawn(0, 1)
    want = ref_new_units(model, shadow, allowance=3)
    r = s.run("newu_unpack")
    s.expect_true("newu_unpack", not r.error and env.log(r.values["n"]) == want, "3마리", "%r %r" % (r.values, want))

    # eudplib 원본 순회와 같은 수 (모델 검증)
    env.fresh()
    shadow = {}
    for _ in range(5):
        model.spawn(0, 1)
    want = ref_new_units(model, shadow)
    r = s.run("eud_newunit")
    s.expect_true("eud_newunit", not r.error and r.values["n"] == len(want), "5마리", repr(r.values))
    env.fresh()


def _death_setup(env, rng, nunits=60):
    """유닛을 흩어 놓고 일부를 죽인다. 반환: {칸: 상태} 상태 = alive | dying | dead."""
    model = env.model
    order = list(range(1700))
    rng.shuffle(order)
    model.set_free(order)
    state = {}
    for _ in range(nunits):
        i = model.spawn(rng.choice((0, 1, 3)), rng.randrange(8))
        state[i] = "alive"
    for i in list(state):
        if rng.random() < 0.35:
            model.kill(i)
            state[i] = "dying"
    if rng.random() < 0.5:
        for i in model.process_deaths():
            state[i] = "dead"
    return state


def run_deaths(s, env, rng):
    model = env.model
    probes = (0, 19, 20, 21, 1679, 1680, 1699)
    for label in ("cod20", "cod17", "cod1", "codkey", "cod2"):
        for rep in range(4 if label != "cod1" else 2):
            env.fresh()
            state = _death_setup(env, rng)
            slots = set(state) | set(probes) | {rng.randrange(1700) for _ in range(20)} | {1700}
            for i in slots:
                env.put("D3", "a", i, 0xA000 + i)
                env.put("D3", "k", i, (i & 1) if i != 1700 else 1)
                env.put("D3", "c", i, 0xCC)
                env.put("D2", "mark", i, 0xB000 + i)
            cunit_before = {i: [model.get(i, off) for off in (0x0C, 0x4C, 0x64)] for i in slots if i < 1700}
            r = s.run(label)
            reg3, reg2 = env.region("D3"), env.region("D2")
            want3, want2 = {}, {}
            for i in slots:
                if i < 1700:
                    dead_like = model.order(i) == 0
                else:
                    dead_like = False
                key_ok = (i & 1) == 1 if label == "codkey" else True
                cleared = dead_like and key_ok
                if not cleared:
                    want3[("a", i)] = 0xA000 + i
                    k = (i & 1) if i != 1700 else 1
                    if k:
                        want3[("k", i)] = k
                    want3[("c", i)] = 0xCC
                if not (dead_like and label == "cod2"):
                    want2[("mark", i)] = 0xB000 + i
            ok = not r.error and reg3 == want3 and reg2 == want2
            ok = ok and all([model.get(i, off) for off in (0x0C, 0x4C, 0x64)] == v for i, v in cunit_before.items())
            s.expect_true(label, ok, "rep %d" % rep,
                          "%s d3=%r d2=%r" % (r.error, sorted(set(reg3.items()) ^ set(want3.items()))[:6],
                                              sorted(set(reg2.items()) ^ set(want2.items()))[:6]))

    for label in ("dying", "dying50", "dying1", "dying_break", "dying_cont", "dying_limit"):
        for rep in range(4 if label != "dying1" else 2):
            env.fresh()
            state = _death_setup(env, rng)
            marked = set()
            for i in list(state) + [rng.randrange(1700) for _ in range(10)] + [0, 1699]:
                if rng.random() < 0.7:
                    env.put("D4", "alive", i, 1)
                    marked.add(i)
                env.put("D4", "val", i, 3 + i)
            hits = sorted(i for i in marked if model.order(i) == 0)
            for cyc in range(3):
                r = s.run(label)
                n = r.values["n"]
                if label == "dying_break":
                    exp = hits[:1]  # 걸린 첫 칸만 내주고 지우지 않는다 → 다음 사이클에도 같은 칸
                elif label == "dying_limit":
                    exp = hits[:2]
                else:
                    exp = hits
                got = env.log(min(n, 64)) if n <= 64 else None
                sv_want = sum(3 + i for i in exp)  # dying_cont 는 +1000000 자리를 건너뛴다
                ok = not r.error and got == exp and r.values["se"] == sum(EPD0 + 84 * i for i in exp) & M32 \
                    and r.values["sp"] == sum(TABLE + 336 * i for i in exp) & M32 and r.values["sv"] == sv_want
                done = [] if label == "dying_break" else exp
                cleared_ok = all(env.get("D4", "alive", i) == 0 and env.get("D4", "val", i) == 0 for i in done)
                kept_ok = all(env.get("D4", "alive", i) == 1 for i in marked if i not in done)
                s.expect_true(label, ok and cleared_ok and kept_ok, "rep %d 사이클 %d" % (rep, cyc),
                              "got=%r exp=%r %r %s" % (got, exp, r.values, r.error))
                hits = [i for i in hits if i not in done]
                marked -= set(done)
                if not hits and cyc >= 1:
                    break


def run_actions(s, env, rng):
    model = env.model
    env.fresh()
    model.set_location(1, 0, 0, 100, 100)
    m1 = model.spawn(0, 7, 50, 50)
    m2 = model.spawn(0, 7, 500, 500)
    m3 = model.spawn(0, 7, 10, 10)
    z = model.spawn(37, 7, 50, 50)
    o = model.spawn(0, 2, 50, 50)
    snap = s.machine.snapshot()
    r = s.run("kill")
    rec = model.killed[-1]
    s.expect_true("kill", not r.error and rec.action == "KillUnit" and set(rec.indices) == {m1, m2, m3}
                  and all(model.dying(i) for i in (m1, m2, m3)) and model.alive(z) and model.alive(o),
                  "KillUnit 마린 P8", repr(rec))
    done = model.process_deaths()
    s.expect_true("kill", set(done) == {m1, m2, m3} and model.free_list()[-3:] == done
                  and all(model.get(i, "sprite") == 0 and model.order(i) == 0 for i in done)
                  and m1 not in model.active_list(), "process_deaths", repr(done))
    s.machine.restore(snap)
    r = s.run("killat")
    rec = model.killed[-1]
    s.expect_true("killat", not r.error and rec.action == "KillUnitAt" and rec.loc == 1 and rec.count == 2
                  and len(rec.indices) == 2 and set(rec.indices) <= {m1, m3} and model.alive(m2), "KillUnitAt 2마리", repr(rec))
    s.machine.restore(snap)
    r = s.run("remove")
    rec = model.killed[-1]
    s.expect_true("remove", not r.error and rec.action == "RemoveUnit" and rec.indices == (o,) and model.dying(o),
                  "RemoveUnit Any unit P3", repr(rec))
    s.machine.restore(snap)
    r = s.run("removeat")
    rec = model.killed[-1]
    s.expect_true("removeat", not r.error and rec.action == "RemoveUnitAt" and rec.indices == (o,) and rec.count == 0,
                  "RemoveUnitAt 전부", repr(rec))
    s.machine.restore(snap)
    r = s.run("order")
    rec = model.orders[-1]
    s.expect_true("order", not r.error and rec == scmodel.OrderRecord(0, 7, 1, rec.order, 2, rec.cycle) and rec.order != 0,
                  "Order 기록", repr(rec))
    env.fresh()


# =============================================================================================
# 파이썬 쪽 판정 (에뮬레이터 밖): API 검사, CUnit 표 스텁
# =============================================================================================


def python_checks(ck):
    ck.eq("index ptr", units.index(TABLE + 336 * 7), 7)
    ck.eq("index epd", units.index(EPD0 + 84 * 1699), 1699)
    ck.eq("index CUnit const", units.index(units.CUnit(EPD0 + 84 * 3)), 3)
    ck.raises("index misaligned", EudextError, units.index, TABLE + 1)
    ck.raises("index out", EudextError, units.index, 0)
    ck.raises("index bool", EudextError, units.index, True)
    ck.raises("index str", EudextError, units.index, "x")
    ck.eq("slot const", units.slot(2), (TABLE + 672, EPD0 + 168))
    ck.raises("slot out", EudextError, units.slot, 1700)
    ck.eq("NO_INDEX", units.NO_INDEX, 1700)
    ck.true("CUnit re-export", units.CUnit is __import__("eudplib").CUnit)
    for a, b in (("capture", "f_capture"), ("create", "f_create"), ("index", "f_index"), ("slot", "f_slot"),
                 ("new_units", "f_new_units"), ("clear_on_death", "f_clear_on_death"), ("dying", "f_dying"),
                 ("next_slot", "f_next_slot")):
        ck.true("alias " + a, getattr(units, a) is getattr(units, b))
    ck.true("epScript hooks", units.UnitField.iadditem is units.UnitField.iadd
            and units.UnitField.isubitem is units.UnitField.isub
            and units.UnitField.isubtractitem is units.UnitField.isub_sat
            and units.UnitField.eqitem is units.UnitField.eq)
    ck.true("UnitField is ExprProxy", isinstance(D.w, __import__("eudplib").ExprProxy))
    ck.eq("fields", D.fields, ("dw", "w", "b", "z", "wd"))
    ck.eq("nbytes", D.nbytes, 5 * 1701 * 4)
    ck.eq("len", len(D.w), 1700)
    ck.eq("Db size", len(D._db.content), 5 * 1701 * 4)
    ck.eq("default blob", D._db.content[4 * 3 * 1701:4 * 3 * 1701 + 4], (0x12345678).to_bytes(4, "little"))
    ck.raises("no fields", EudextError, units.UnitData)
    ck.raises("bad kind", EudextError, units.UnitData, a="qword")
    ck.raises("reserved", EudextError, units.UnitData, of="dword")
    ck.raises("underscore", EudextError, units.UnitData, _x="dword")
    ck.raises("default range", EudextError, units.UnitData, a=("byte", 256))
    ck.raises("default bool", EudextError, units.UnitData, a=("byte", True))
    ck.raises("bad spec", EudextError, units.UnitData, a=5)
    ck.raises("too many", EudextError, units.UnitData, **{"f%d" % k: "byte" for k in range(61)})
    ck.raises("setattr", EudextError, setattr, D, "w", 1)
    ck.raises("unknown field", AttributeError, getattr, D, "nope")
    ck.raises("field()", EudextError, D.field, "nope")
    ck.raises("index 1701", EudextError, D.w.set, 1701, 1)
    ck.raises("index -1", EudextError, D.clear, -1)
    ck.raises("iter", EudextError, iter, D.w)
    ck.raises("value str", EudextError, D.w.set, 3, "x")
    ck.raises("iand var", AttributeError, D.w.iand, 3, EUDVariable())
    u = units.Capture()
    ck.raises("end before begin", EudextError, u.end)
    ck.raises("Capture bad var", EudextError, units.Capture, ptr=5)
    v = EUDVariable()
    ck.raises("Capture same var", EudextError, units.Capture, ptr=v, epd=v)
    ck.raises("create into", EudextError, units.create, 1, 0, 64, 7, into=5)
    ck.raises("chunk", EudextError, units.clear_on_death, D3, chunk=3)
    ck.raises("no data", EudextError, units.clear_on_death)
    ck.raises("key missing", EudextError, units.clear_on_death, D3, key="nope")
    ck.raises("key default", EudextError, units.clear_on_death, D3, key="c")
    ck.raises("key type", EudextError, units.clear_on_death, D3, key=5)
    ck.raises("dying no key", EudextError, lambda: list(units.dying(D4, key=None)))
    ck.raises("dying limit", EudextError, lambda: list(units.dying(D4, key="alive", limit=0)))
    ck.raises("not data", EudextError, units.clear_on_death, 5)
    ck.true("repr", "dw:dword" in repr(D) and "w:word" in repr(D.w) and "닫힘" in repr(u))


def model_checks(ck):
    """CUnit 표 스텁·빈 칸 목록·액션 처리기 (에뮬레이터 없이 Machine 만)."""
    Model = scmodel.UnitModel

    def machine():
        return emu.Machine(bytes(4), emu.BASE, {"__root__": 0})

    m = machine()
    model = scmodel.install_units(m)
    ck.true("installed", scmodel.unit_model(m) is model and m.act_handlers[44] and m.act_handlers[11] and m.act_handlers[46])
    ck.eq("free list", model.free_list()[:3] + model.free_list()[-2:], [0, 1, 2, 1698, 1699])
    ck.eq("free count", len(model.free_list()), 1700)
    ck.eq("0x628438", m.dw(scmodel.FIRST_UNUSED), TABLE)
    ck.eq("0x628430", m.dw(scmodel.FIRST_UNIT), 0)
    ck.eq("ptr/epd", (Model.ptr(3), Model.epd(3)), (TABLE + 1008, EPD0 + 252))
    ck.eq("index_of", (Model.index_of(TABLE + 336 * 9), Model.index_of(EPD0 + 84 * 9)), (9, 9))
    ck.raises("index_of bad", ValueError, Model.index_of, TABLE + 3)
    a = model.spawn(0, 7, 100, 200)
    b = model.spawn(1, 6)
    c = model.spawn(2, 5)
    ck.eq("active second", model.active_list(), [a, c, b])
    ck.eq("fields", (model.unit_type(a), model.owner(a), model.pos(a), model.hp(a), model.uniq(a), model.alive(a)),
          (0, 7, (100, 200), 100 << 8, 1, True))
    ck.eq("order/status", (model.order(a), model.get(a, "status") & 1), (scmodel.ORDER_ON_CREATE, 1))
    ck.eq("next free", model.next_free(), 3)
    g = model.spawn(3, 1)
    ck.eq("goliath", (g, model.sub_unit(g), model.unit_type(4), model.sub_unit(4), model.next_free()), (3, Model.ptr(4), 4, Model.ptr(3), 5))
    ck.eq("units()", (model.units(player=7), model.units(unit=4), len(model.units())), ([a], [4], 5))
    model.kill(b)
    ck.eq("dying", (model.dying(b), model.alive(b), model.hp(b), model.order(b)), (True, False, 0, 0))
    ck.eq("units alive", b in model.units(), False)
    ck.eq("process", model.process_deaths(), [b])
    ck.eq("freed back", (model.free_list()[-1], b in model.active_list(), model.get(b, "sprite")), (b, False, 0))
    ck.eq("stale fields kept", (model.unit_type(b), model.owner(b), model.uniq(b)), (1, 6, 1))
    model.set_free([b])
    ck.eq("reuse uniq", (model.spawn(9, 0), model.uniq(b), model.unit_type(b)), (b, 2, 9))
    ck.eq("free empty", (model.next_free(), m.dw(scmodel.FIRST_UNUSED)), (None, 0))
    ck.raises("spawn no slot", RuntimeError, model.spawn, 0, 0)
    ck.raises("spawn taken", RuntimeError, model.spawn, 0, 0, index=a)

    # head 삽입·앞으로 돌려주기·지정 칸·fill
    m2 = machine()
    md = scmodel.install_units(m2, insert="head", free_to="front", free=[5, 4, 3, 2, 1, 0], subunits={}, hp={0: 40})
    x = md.spawn(0, 0)
    y = md.spawn(3, 0)
    ck.eq("head insert", (x, y, md.active_list(), md.hp(x), md.sub_unit(y)), (5, 4, [4, 5], 40 << 8, 0))
    z = md.spawn(0, 1, index=1)
    ck.eq("index spawn", (z, md.free_list()), (1, [3, 2, 0]))
    md.kill(x)
    md.process_deaths()
    ck.eq("front free", md.free_list(), [5, 3, 2, 0])
    ck.eq("fill 2", (md.fill(2), md.free_list()), ([5, 3], [2, 0]))
    ck.eq("fill all", (md.fill(), md.next_free()), ([2, 0], None))
    ck.raises("bad insert", ValueError, Model, m2, insert="x")
    ck.raises("bad free_to", ValueError, Model, m2, free_to="x")

    # 액션 처리기 (fields 튜플 직접)
    m3 = machine()
    mm = scmodel.install_units(m3)
    mm.set_location(3, 10, 20, 30, 41)
    ck.eq("loc", (mm.loc_rect(3), mm.loc_center(3)), ((10, 20, 30, 41), (20, 30)))
    mm.set_location(4, -10 & M32, 0, 10, 0)
    ck.eq("loc signed", mm.loc_center(4), (0, 0))

    def act(atype, loc=0, p1=0, p2=0, unit=0, amount=0):
        m3.act_handlers[atype](m3, (loc, 0, 0, 0, p1, p2, unit, atype, amount, 0, 0))

    act(44, loc=3, p1=4, unit=7, amount=2)
    rec = mm.created[-1]
    ck.eq("create rec", (rec.action, rec.count, rec.unit, rec.loc, rec.player, rec.props, rec.ok, rec.indices, rec.subs),
          ("CreateUnit", 2, 7, 3, 4, None, True, (0, 1), ()))
    ck.eq("create pos", mm.pos(1), (20, 30))
    m3.setdw(emu.CP_ADDR, 6)
    act(11, loc=64, p1=13, p2=5, unit=5, amount=0)
    rec = mm.created[-1]
    ck.eq("props rec", (rec.action, rec.count, rec.player, rec.props, rec.indices, rec.subs), ("CreateUnitWithProperties", 1, 6, 5, (2,), (3,)))
    mm.fail_next(2)
    act(44, p1=1)
    act(44, p1=1)
    act(44, p1=1)
    ck.eq("fail_next", [r.ok for r in mm.created[-3:]], [False, False, True])
    mm.fail_when(lambda r: r.player == 3)
    act(44, p1=3)
    act(44, p1=2)
    ck.eq("fail_when", [r.ok for r in mm.created[-2:]], [False, True])
    mm.clear_failures()
    act(44, p1=3)
    ck.eq("clear_failures", mm.created[-1].ok, True)
    ck.raises("create force", emu.EmuError, act, 44, p1=18)
    head = mm.next_free()
    m3.setdw(scmodel.FIRST_UNUSED, 0)
    act(44, p1=17)  # eudplib 로케일 판별 흉내: 빈 칸 없음 → 실패로 기록
    ck.eq("empty create", (mm.created[-1].ok, mm.created[-1].player), (False, 17))
    m3.setdw(scmodel.FIRST_UNUSED, Model.ptr(head))
    # 킬
    act(22, p1=17, unit=229)
    rec = mm.killed[-1]
    ck.eq("kill all", (rec.action, rec.player, sorted(rec.indices)), ("KillUnit", 17, sorted(i for i in mm.active_list())))
    ck.eq("kill again empty", (act(22, p1=4, unit=7), mm.killed[-1].indices), (None, ()))
    ck.raises("kill class", emu.EmuError, act, 22, p1=4, unit=230)
    act(46, loc=3, p1=13, p2=9, unit=0, amount=2)
    ck.eq("order rec", mm.orders[-1][:5], (0, 6, 3, 2, 9))
    mm.clear_log()
    ck.eq("clear_log", (mm.created, mm.killed, mm.orders), ([], [], []))

    # snapshot/restore 에 모델 메모리가 같이 따라간다
    snap = m3.snapshot()
    k = mm.spawn(0, 0)
    ck.eq("spawn after kill", (k, k in mm.active_list(), mm.next_free()), (head, True, head + 1))
    m3.restore(snap)
    ck.eq("restore", (k in mm.active_list(), mm.next_free(), mm.uniq(k)), (False, head, 0))

    # install() 의 units 인자
    m4 = machine()
    scmodel.install(m4, units=True)
    m5 = machine()
    scmodel.install(m5)
    m6 = machine()
    scmodel.install(m6, units={"free": [7]})
    ck.eq("install units", (scmodel.unit_model(m4) is not None, scmodel.unit_model(m5), scmodel.unit_model(m6).next_free()),
          (True, None, 7))


# =============================================================================================
# epScript 예제
# =============================================================================================


EX = os.path.join(_common.PKG, "examples")


def eps_checks(ck):
    src = open(os.path.join(EX, "units_ingame.eps"), encoding="utf-8").read()
    ck.eq("ingame eps errors", _compat.eps_compile("units_ingame.eps", src)[1], 0)
    src = open(os.path.join(EX, "units_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("units_example.eps", src)
    ck.eq("eps errors", nerr, 0)
    for needle in ("units.UnitData(hp2=", "units.Capture()", "u.begin()", "u.end()", "if EUDIf()(u.ok):",
                   "_ARRW(data.hp2, u.index).__iadd__(5)", "_ARRW(data.stack, u.index) << (70000)",
                   "units.f_create(1, \"Terran Marine\", \"Anywhere\", P8, on_create=data)",
                   "_ARRW(data.hp2, c.index).__isub__(1)", "for nu in units.f_new_units():",
                   "_ATTW(row, 'stack').__iadd__(1)", "_ATTC(row, 'stack') == 4465",
                   "for d in units.f_dying(data, key=\"alive\"):", "units.CUnit(u.epd)"):
        ck.true("eps: " + needle, out is not None and needle in out, "")


def eps_emulate(ck):
    """예제를 작업 폴더로 복사해 EPSLoader 로 싣고 에뮬레이터에서 3 사이클 돌린다."""
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_units_eps")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, "units_example.eps"), os.path.join(work, "units_example.eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(work, "units_example.eps"), {})
    prog = emu.Program(mod.afterTriggerExec)
    names = ("made", "lastIndex", "newCount", "deadCount", "hpOut", "rowHits", "failCount", "timerOut")
    for n in names:
        prog.watch(n, getattr(mod, n))
    prog.watch("db", mod.data._db)
    m = prog.build()
    scmodel.install(m, units={})
    model = scmodel.unit_model(m)
    for i in range(10):
        model.set(i, 0x110, 0x1234, 2)  # removeTimer — 예제가 0 으로 쓰는지 본다
    rows = []
    for cyc in range(4):
        if cyc == 2:
            for i in model.units():
                model.kill(i)
        if cyc == 3:
            model.process_deaths()
            model.fill()
        m.cycle()
        rows.append({n: m.var(n) for n in names})
    print("  epScript 에뮬레이션: %r" % rows)
    # 사이클마다 makeOne(칸 2k) + create(칸 2k+1). new_units 는 두 마리씩, 사이클 2 앞에서 모두 죽임 → dying 4,
    # 사이클 3 앞에서 빈 칸을 모두 채움 → 생성 실패 1 (row 는 버리는 칸을 가리켜 rowHits 그대로)
    base = {"deadCount": 0, "hpOut": 5, "failCount": 0, "timerOut": 0}
    want = [
        dict(base, made=1, lastIndex=0, newCount=2, rowHits=1),
        dict(base, made=2, lastIndex=2, newCount=4, rowHits=2),
        dict(base, made=3, lastIndex=4, newCount=6, rowHits=3, deadCount=4),
        dict(base, made=3, lastIndex=4, newCount=6, rowHits=3, deadCount=4, failCount=1),
    ]
    for cyc, (got, exp) in enumerate(zip(rows, want)):
        ck.eq("eps 사이클 %d" % cyc, got, exp)
    ck.eq("eps create 칸 removeTimer 그대로", model.get(1, 0x110, 2), 0x1234)
    db = m.addr("db")

    def cell(k, i):
        return m.dw(db + 4 * (k * 1701 + i))

    # 필드 순서 hp2, stack, alive. 칸 0~3 은 dying 이 지웠고 칸 4(makeOne)·5(create) 는 살아 있다
    ck.eq("eps 표", ([cell(k, i) for k in range(3) for i in range(4)], cell(0, 4), cell(1, 4), cell(2, 4),
                     cell(0, 5), cell(2, 5), cell(1, 1700)),
          ([0] * 12, 5, 4465, 1, M32, 1, 1))
    ck.eq("eps 기록", [r.ok for r in model.created][-8:], [True, True, True, True, True, True, False, False])
    return rows


def ingame_emulate(ck):
    """인게임 확인 맵(examples/units_ingame.eps)을 에뮬레이터에서 55 사이클 돌린다(실행 오류·흐름 확인)."""
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_units_ingame")
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, "units_ingame.eps"), os.path.join(work, "units_ingame.eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(work, "units_ingame.eps"), {})
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "ccSlot", "ccDeaths", "deadSeen", "fillMade", "t8Slot", "killSlot")
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m, units={})
    model = scmodel.unit_model(m)
    for i in range(66):  # 기준 맵처럼 P1 맵 리빌러 64 + 시작 위치 2
        model.spawn(101 if i < 64 else 214, 0)
    # 겹쳐 짓는 CC 는 실패 (모델에는 자리 검사가 없다)
    model.fail_when(lambda rec: rec.unit == 106 and any(model.unit_type(i) == 106 for i in model.units()))
    err = None
    try:
        for cyc in range(55):
            if cyc in (12, 36):
                model.process_deaths()
            m.cycle()
    except emu.EmuError as e:
        err = str(e)
    got = {n: m.var(n) for n in names}
    print("  인게임 맵 에뮬레이션: %r, 기록 %d" % (got, len(model.created)))
    ck.eq("ingame emu 오류", err, None)
    # 모델 가정(두 번째 자리 삽입, 죽은 칸은 빈 칸 목록 끝) 아래의 값: 칸 0~65 미리 놓임, T1 66, 골리앗 67+68, T3 69~71,
    # CC 72(겹친 CC 실패), F6 마린 73·74 → T8 은 머리 75. F8 에 마린 6마리 죽음(알림 6) + F26 CC(1).
    # F30 채움 = 1700 − 76 + 돌려받은 6 = 1630. F32 이후 사이클마다 죽음 알림 40(limit) × 24 사이클
    ck.eq("ingame emu 값", got, {"frame": 55, "ccSlot": 72, "ccDeaths": 1, "deadSeen": 7 + 40 * 24, "fillMade": 1630,
                                  "t8Slot": 75, "killSlot": 66})
    ck.eq("ingame emu 겹친 CC 실패", [r.ok for r in model.created if r.unit == 106], [True, False])


def eps_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("units_example", "units_ingame"):
        work = os.path.join(_common.WORK, "t_units_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")
        ck.true("boot preload " + name, "units" in r.log, "")


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

C1 = units.UnitData(a="dword", w="word", b="byte")


def _cost_capture(t):
    with units.capture() as u:
        DoActions(CreateUnit(1, "Terran Marine", "Anywhere", P8))
    t.flag("ok", u.ok)


def _cost_if(cond, t):
    if EUDIf()(cond):
        DoActions(t.var("f").AddNumber(1))
    EUDEndIf()


def _cost_unitdata(n):
    def build(t):
        d = units.UnitData(**{"f%d" % k: "dword" for k in range(n)})
        d.f0.set(0, 0)

    return build


COST_CASES = [
    CostCase("capture (begin + CreateUnit + end + ok 조건)", _cost_capture, funcs=[units._next_slot_func()],
             note="ok 를 변수로 옮기는 몫(2~3) 포함"),
    CostCase("capture begin 만 (next_slot)", lambda t: units.next_slot(), funcs=[units._next_slot_func()]),
    CostCase("index (변수)", lambda t: units.index(t.var("x")), [{"x": TABLE}, {"x": EPD_MAX}, {"x": 0}],
             funcs=[units._index_func()], note="포인터·EPD·범위 밖"),
    CostCase("slot (변수)", lambda t: units.slot(t.var("i")), [{"i": 0}, {"i": 1699}], funcs=[units._slot_func()]),
    CostCase("dword set (변수 칸, 상수 값)", lambda t: C1.a.set(t.var("i"), 5)),
    CostCase("dword set (변수 칸, 변수 값)", lambda t: C1.a.set(t.var("i"), t.var("v"))),
    CostCase("dword iadd (변수 칸, 상수 값)", lambda t: C1.a.iadd(t.var("i"), 5)),
    CostCase("dword isub (변수 칸, 변수 값)", lambda t: C1.a.isub(t.var("i"), t.var("v")), note="−v 임시 변수"),
    CostCase("dword isub_sat (변수 칸, 변수 값)", lambda t: C1.a.isub_sat(t.var("i"), t.var("v"))),
    CostCase("word iadd (변수 칸, 상수 값)", lambda t: C1.w.iadd(t.var("i"), 5), note="CP 방식"),
    CostCase("word iadd (변수 칸, 변수 값)", lambda t: C1.w.iadd(t.var("i"), t.var("v"))),
    CostCase("word set (변수 칸, 변수 값)", lambda t: C1.w.set(t.var("i"), t.var("v"))),
    CostCase("byte set (상수 칸, 상수 값)", lambda t: C1.b.set(5, 1)),
    CostCase("word iadd (상수 칸, 상수 값)", lambda t: C1.w.iadd(5, 1)),
    CostCase("dword get (변수 칸)", lambda t: C1.a.get(t.var("i")), [{"i": 0}, {"i": 1699}]),
    CostCase("word get (변수 칸)", lambda t: C1.w.get(t.var("i"))),
    CostCase("byte get (변수 칸)", lambda t: C1.b.get(t.var("i"))),
    CostCase("dword eq 조건 (변수 칸, 변수 값)", lambda t: _cost_if(C1.a.eq(t.var("i"), t.var("v")), t),
             [{"i": 3, "v": 0}, {"i": 3, "v": 1}], note="EUDIf + 참 경로 액션 1 포함"),
    CostCase("dword ne 조건 (변수 칸, 변수 값)", lambda t: _cost_if(C1.a.ne(t.var("i"), t.var("v")), t),
             [{"i": 3, "v": 0}, {"i": 3, "v": 1}], note="1비트에 받아 뒤집음"),
    CostCase("iand (변수 칸, 상수)", lambda t: C1.w.iand(t.var("i"), 0xFF)),
    CostCase("clear (변수 칸, 필드 3)", lambda t: C1.clear(t.var("i"))),
    CostCase("clear (상수 칸, 필드 3)", lambda t: C1.clear(7)),
    CostCase("of(epd).w 읽기", lambda t: C1.of(t.var("e")).w, {"e": EPD0 + 84 * 5}),
    CostCase("new_units (본문 비움, 유닛 없음)", lambda t: [None for _nu in units.new_units()],
             note="eudplib 그림자 표 571KB 포함"),
    CostCase("참고: EUDLoopNewUnit (본문 비움)", lambda t: [None for _p in EUDLoopNewUnit()]),
    CostCase("clear_on_death (필드 3, chunk 20)", lambda t: units.clear_on_death(C1)),
    CostCase("clear_on_death (필드 3, chunk 50)", lambda t: units.clear_on_death(C1, chunk=50)),
    CostCase("clear_on_death (필드 3, key, chunk 20)", lambda t: units.clear_on_death(C1, key="b")),
    CostCase("dying (걸린 칸 없음, chunk 20)", lambda t: [None for _d in units.dying(C1, key="b")]),
    CostCase("UnitData 1700×1 (dword)", _cost_unitdata(1), note="페이로드 = 필드당 6,804B + 트리거 1"),
    CostCase("UnitData 1700×6 (dword)", _cost_unitdata(6)),
]


def measure_scx(fields_list=(1, 6, 20)):
    """scx 증가분(압축 뒤): UnitData(필드 N개) 와 new_units 순회 1곳. 빈 빌드와 파일 크기 차이."""
    rows = []

    def build(tag, extra):
        _compat.reset_build_state()
        LoadMap(BASE_MAP)
        CompressPayload(True)
        ShufflePayload(False)
        v = EUDVariable()

        def main():
            if EUDInfLoop()():
                _compat.set_game_loop_start()
                DoActions(v.AddNumber(1))
                extra()
                EUDDoEvents()
            EUDEndInfLoop()

        out = os.path.join(_common.WORK, "t_units_scx_%s.scx" % tag)
        SaveMap(out, main)
        ShufflePayload(True)
        return os.path.getsize(out)

    empty = build("empty", lambda: None)
    for n in fields_list:
        size = build("data%d" % n, lambda n=n: units.UnitData(**{"f%d" % k: "dword" for k in range(n)}).f0.set(0, 0))
        rows.append(("UnitData 1700×%d" % n, size - empty))
    size = build("newu", lambda: [None for _ in units.new_units()])
    rows.append(("new_units 1곳 (그림자 표 571KB 포함)", size - empty))
    size = build("cod", lambda: units.clear_on_death(units.UnitData(a="dword", b="dword", c="dword")))
    rows.append(("clear_on_death (UnitData 1700×3 포함)", size - empty))
    for name, d in rows:
        print("  scx 증가 %-40s %+d B" % (name, d))
    return rows


def main():
    if "--scx" in sys.argv:
        measure_scx()
        return
    rng = random.Random(10)
    ck = Checker("t_units (python)")
    python_checks(ck)
    ckm = Checker("t_units (model)")
    model_checks(ckm)

    s = Suite("t_units", memory={"units": {}})
    build_cases(s)
    s.build()
    env = Env(s)
    run_capture(s, env, rng)
    run_index(s, env, rng)
    run_fields(s, env, rng)
    run_rows(s, env, rng)
    run_new_units(s, env, rng)
    run_deaths(s, env, rng)
    run_actions(s, env, rng)
    ok1 = s.report()

    cke = Checker("t_units (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    ingame_emulate(cke)
    eps_build(cke)
    rows = measure_scx()
    ck.true("scx UnitData 1700×6 < 1KB", dict(rows)["UnitData 1700×6"] < 1024, repr(rows))
    finish(ok1, ck.report(), ckm.report(), cke.report())


if __name__ == "__main__":
    main()
