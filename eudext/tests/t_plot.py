"""`plot` 시험 (에뮬레이터 + scmodel 유닛 모델 + testing/locmodel): Plotter 가 찍은 좌표·로케이션 상자·유닛·주인·수량을
파이썬 참조 모델(CAPlotIndexed 의미)과 프레임마다 비교한다 — per_tick·delay·size·repeat·스케줄·busy/done·중심 모드·
on_point 변환(pt.rotate = CtrigAsm CA_Rotate 참조 구현)·each() 의 continue/break·capture·props, 상태 없는 부품,
create_shape, 트리거 수가 도형 수·점 수와 무관한지(3.8), 빌드 오류, epScript 예제·인게임 확인 맵의 번역·에뮬레이션·
euddraft 빌드(번들 파이썬에서 lupa 적재).

python tests/t_plot.py
비용 표: python tools/cost.py tests/t_plot.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402

from eudplib import (  # noqa: E402
    P1,
    P8,
    CompressPayload,
    CurrentPlayer,
    EUDBreak,
    EUDContinue,
    EUDEndIf,
    EUDFunc,
    EUDIf,
    EUDVariable,
    GetTriggerCounter,
    LoadMap,
    UnitProperty,
)

import ref_mathx as R  # noqa: E402
from eudext import _compat, plot, shape  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.plot import Plotter  # noqa: E402
from eudext.shape import CX, Shape, ShapeSet  # noqa: E402
from eudext.testing import BASE_MAP, emu, locmodel, scmodel  # noqa: E402
from eudext.testing.harness import Suite, rand32  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
EX = os.path.join(_common.PKG, "examples")
u32, s32 = R.u32, R.s32

CXP = CX(seed=1234)
RING = CXP.call("CSMakeCircle", 6, 32, 0, 37, 0)
STAR = CXP.eval("CSMakeStar(5,144,96,0,CS_Level('Star',5,3),0)")
RAY = CXP.eval("CSMakeLine(1,32,0,6,1)")
FADE = RING.sweep("right", px_per_cycle=32)
SCHED = RING.with_schedule([1, 0, 6, 0, 12])  # 마지막 밴드 12 가 되풀이된다
EDGE = Shape([(-300, 200), (5, -7), (0, 0)], name="edge")
EMPTY = Shape([], name="empty")
BIG = CXP.call("CSMakeCircle", 12, 16, 0, 300, 0)
LIST = [RING, STAR, RAY, FADE, SCHED, EDGE, EMPTY, BIG]
SS = ShapeSet(LIST, name="p_db")
SV = ShapeSet(LIST, storage="varray", name="p_va")
LOC = 26  # 기준 맵의 빈 로케이션 (0,0,0,0)
LOC2 = 27  # (1312, 1216, 1440, 1312) — 중심 (1376, 1264)
PROPS = UnitProperty(hitpoint=50)


# =============================================================================================
# 참조 모델 (plot 모듈 설명의 의사코드 = theSeed CAPlotIndexed.lua 루프)
# =============================================================================================


class Ref:
    """Plotter 의 파이썬 참조. body(x, y, p) → (x, y, 동작) 동작: "ok" | "skip" | "continue" | "break"."""

    def __init__(self, shapes, unit, owner, per_tick=1, delay=1, size=0, repeat=False, count=1, props=None,
                 body=None, loc=LOC):
        self.shapes = list(shapes)
        self.unit, self.owner, self.per_tick, self.delay, self.size = unit, owner, per_tick, delay, size
        self.repeat, self.count, self.props, self.body, self.loc = repeat, count, props, body, loc
        self.active = 0
        self.w = 0
        self.p = 0
        self.n = 0
        self.sptr = 1
        self.sched = None
        self.pts = ()
        self.cx = self.cy = 0
        self.interrupted = 0

    def start(self, sid, cx, cy):
        if self.active:
            self.interrupted += 1
        if 0 <= sid < len(self.shapes):
            s = self.shapes[sid]
            self.pts, self.n, self.sched = s.points, len(s), s.schedule
        else:
            self.pts, self.n, self.sched = (), 0, None
        self.p, self.w, self.sptr = 0, 0, 1
        self.cx, self.cy = cx, cy
        self.active = 1

    def set_center(self, cx, cy):
        self.cx, self.cy = cx, cy

    def stop(self):
        self.active = 0

    def tick(self):
        out = []
        if self.active and self.w == 0:
            if self.sched:
                lim = self.sched[self.sptr - 1]
                if len(self.sched) > self.sptr:
                    self.sptr += 1
            else:
                lim = M32 if self.per_tick == "all" else u32(self.per_tick)
            k = min(lim, self.n - self.p)
            for _ in range(k):
                x, y = self.pts[self.p]
                act = "ok"
                if self.body is not None:
                    x, y, act = self.body(x, y, self.p)
                if act == "break":
                    break
                if act == "ok":
                    X, Y = s32(x + self.cx), s32(y + self.cy)
                    sz = self.size
                    rect = (s32(X - sz), s32(Y - sz), s32(X + sz), s32(Y + sz))
                    out.append((rect, self.unit, self.owner, self.count or 1, self.props))
                self.p += 1
            self.w = self.delay
            if self.p >= self.n:
                if self.repeat:
                    self.p, self.sptr = 0, 1
                else:
                    self.active = 0
        self.w = max(self.w - 1, 0)
        return out


# =============================================================================================
# Plotter 들 (모듈 전역 — 케이스 본문이 쓴다)
# =============================================================================================

G = {}  # 케이스 사이에 나눠 쓰는 변수 (앞 케이스 본문에서 만든다)
VB = {k: EUDVariable() for k in ("unit", "owner", "per_tick", "delay", "size", "count")}

PA = Plotter(SS, unit="Terran Marine", owner=P8, loc=LOC, per_tick=3, delay=1, name="pa")
PB = Plotter(SS, unit=VB["unit"], owner=VB["owner"], loc=LOC, per_tick=VB["per_tick"], delay=VB["delay"],
             size=VB["size"], count=VB["count"], name="pb")
PC = Plotter(SV, unit=37, owner=P1, loc=LOC, per_tick="all", delay=2, size=16, repeat=True, name="pc")
PD = Plotter(SS, unit=40, owner=P1, loc=LOC, per_tick=5, delay=0, repeat=True, props=PROPS, count=3, name="pd")
PE = Plotter(SS, unit=0, owner=P8, loc=LOC, per_tick=4, delay=1, name="pe")
PF = Plotter(SS, unit=0, owner=P8, loc=LOC, per_tick=6, delay=1, name="pf")
PG = Plotter(SS, unit=0, owner=P8, loc=LOC, per_tick=2, delay=1, capture=True, name="pg")
PH = Plotter(SV, unit=0, owner=P8, loc=LOC, per_tick=3, delay=1, size=2, name="ph")
PI = Plotter(SS, unit=0, owner=CurrentPlayer, loc=LOC2, per_tick=5, delay=1, name="pi")
PJ_COUNT = EUDVariable()


@EUDFunc
def _pj_hook():
    # 인자 없는 EUDFunc 콜백: 본문에서 Plotter.pt 를 쓴다 (점 번호 3 이면 건너뛴다)
    PJ_COUNT.__iadd__(1)
    if EUDIf()(PJ.pt.index == 3):
        PJ.pt.skip()
    EUDEndIf()


PJ = Plotter(SS, unit=0, owner=P8, loc=LOC, per_tick=4, delay=1, on_point=_pj_hook, name="pj")


@PE.on_point
def _pe_body(pt):
    pt.rotate(G["pe_ang"])
    pt.move(G["pe_dx"], 3)
    pt.ratio(3, 2, G["pe_my"], G["pe_dy"])
    pt.crop(x1=-100, x2=G["pe_x2"])
    if EUDIf()(pt.index == 2):
        pt.skip()
    EUDEndIf()


def ref_pe(ang, dx, my, dy, x2):
    def body(x, y, p):
        x, y = R.rotate(x, y, ang)
        x, y = u32(x + dx), u32(y + 3)
        x = R.ratio(x, 3, 2, "ctrig")
        y = R.ratio(y, my, dy, "ctrig")
        sx, sy = s32(x), s32(y)
        if sx <= -100 or sx >= s32(x2) or p == 2:
            return sx, sy, "skip"
        return sx, sy, "ok"

    return body


def ref_pf(state):
    def body(x, y, p):
        x, y = R.rotate(x, y, 90)
        if p == 1:
            return s32(x), s32(y), "continue"
        if p == 5 and state["brk"] == 0:
            state["brk"] = 1
            return s32(x), s32(y), "break"
        return s32(x), s32(y), "ok"

    return body


def ref_ph(xy, zx, mx):
    def body(x, y, p):
        X, Y, _Z = R.rotate3d(x, y, xy, 30, zx)
        X = u32(X * mx)
        return s32(X - 5), s32(Y), "ok"

    return body


# =============================================================================================
# 케이스
# =============================================================================================


def _flags(t, pl, tag):
    t.flag("busy", pl.busy)
    t.flag("done", pl.done)
    t.out("idx", pl.index)
    t.watch("intr", pl.interrupted.getValueAddr())


def build_cases(s):
    @s.case("pa_start")
    def _(t):
        PA.start(t.var("sid"), center=(t.var("cx"), t.var("cy")))

    @s.case("pa_tick")
    def _(t):
        PA.tick()
        _flags(t, PA, "pa")

    @s.case("pa_stop")
    def _(t):
        PA.stop()

    @s.case("pb_start")
    def _(t):
        for k, v in VB.items():
            v << t.var(k)
        PB.start(t.var("sid"), center=(t.var("cx"), t.var("cy")))

    @s.case("pb_tick")
    def _(t):
        PB.tick()
        _flags(t, PB, "pb")

    @s.case("pc_start")
    def _(t):
        PC.start(t.var("sid"), center=(t.var("cx"), t.var("cy")))

    @s.case("pc_tick")
    def _(t):
        for _pt in PC.each():
            pass
        _flags(t, PC, "pc")

    @s.case("pc_stop")
    def _(t):
        PC.stop()

    @s.case("pd_start")
    def _(t):
        PD.start(5, center=(1000, 900))

    @s.case("pd_tick")
    def _(t):
        PD.tick()
        _flags(t, PD, "pd")

    @s.case("pe_start")
    def _(t):
        for k in ("ang", "dx", "my", "dy", "x2"):
            G["pe_" + k] = t.var(k)
        PE.start(t.var("sid"), center=(2000, 2000))

    @s.case("pe_tick")
    def _(t):
        PE.tick()
        _flags(t, PE, "pe")

    @s.case("pf_start")
    def _(t):
        G["pf_brk"] = t.var("brk")
        PF.start(t.var("sid"), center=(1500, 1500))

    @s.case("pf_tick")
    def _(t):
        brk = G["pf_brk"]
        for pt in PF.each():
            pt.rotate(90)
            if EUDIf()(pt.index == 1):
                EUDContinue()
            EUDEndIf()
            if EUDIf()([pt.index == 5, brk.Exactly(0)]):
                brk << 1
                EUDBreak()
            EUDEndIf()
        _flags(t, PF, "pf")

    @s.case("pg_start")
    def _(t):
        G["pg_ok"] = t.var("okc")
        G["pg_epd"] = t.var("epd")
        PG.start(t.var("sid"), center=(800, 800))

    @PG.on_created
    def _pg_created(pt):
        if EUDIf()(pt.unit.ok):
            G["pg_ok"] += 1
            G["pg_epd"] << pt.unit.epd
        EUDEndIf()

    @s.case("pg_tick")
    def _(t):
        PG.tick()
        _flags(t, PG, "pg")

    @s.case("ph_start")
    def _(t):
        G["ph_xy"] = t.var("xy")
        G["ph_zx"] = t.var("zx")
        G["ph_mx"] = t.var("mx")
        PH.start(t.var("sid"), center=(t.var("cx"), 700))

    @s.case("ph_tick")
    def _(t):
        for pt in PH.each():
            pt.rotate3d(G["ph_xy"], 30, G["ph_zx"])
            pt.ratio(G["ph_mx"], None, None, None)
            pt.x -= 5
        _flags(t, PH, "ph")

    @s.case("pj_start")
    def _(t):
        PJ_COUNT << 0
        PJ.start(t.var("sid"), center=(640, 480))

    @s.case("pj_tick")
    def _(t):
        PJ.tick()
        _flags(t, PJ, "pj")
        t.out("cnt", PJ_COUNT)

    @s.case("pi_start_loc")
    def _(t):
        PI.start(t.var("sid"))  # 자기 로케이션(LOC2) 지금 중심

    @s.case("pi_start_other")
    def _(t):
        PI.start(t.var("sid"), center=t.var("loc"))  # 번호 변수

    @s.case("pi_start_name")
    def _(t):
        PI.start(t.var("sid"), center="Location 13")  # 이름 (2048, 2048)

    @s.case("pi_set_center")
    def _(t):
        PI.set_center((t.var("cx"), t.var("cy")))

    @s.case("pi_tick")
    def _(t):
        PI.tick()
        _flags(t, PI, "pi")

    # --- create_shape (한 번에 모두) ---
    @s.case("cs_var")
    def _(t):
        plot.create_shape(SS, t.var("sid"), t.var("unit"), LOC2, P8, center=(t.var("cx"), t.var("cy")), size=t.var("sz"),
                          count=2)

    @s.case("cs_const")
    def _(t):
        plot.create_shape(SV, RAY, "Zerg Scourge", LOC2, P1, center="loc", size=4, props=PROPS)

    # --- 상태 없는 부품 ---
    @s.case("st_ratio")
    def _(t):
        plot.ratio(t.var("x"), t.var("y"), t.var("mx"), t.var("dx"), t.var("my"), t.var("dy"), ret=[t.var("rx"), t.var("ry")])

    @s.case("st_ratio_k")
    def _(t):
        rx, ry = plot.ratio(t.var("x"), t.var("y"), 150, 100, -3, 7)
        t.out("rx", rx)
        t.out("ry", ry)

    @s.case("st_ratio_part")
    def _(t):
        rx, ry = plot.ratio(t.var("x"), t.var("y"), mx=t.var("mx"), dy=t.var("dy"))
        t.out("rx", rx)
        t.out("ry", ry)

    @s.case("st_move")
    def _(t):
        rx, ry = plot.move(t.var("x"), t.var("y"), t.var("dx"), -7)
        t.out("rx", rx)
        t.out("ry", ry)

    @s.case("st_rot")
    def _(t):
        rx, ry = plot.rotate(t.var("x"), t.var("y"), t.var("a"))
        t.out("rx", rx)
        t.out("ry", ry)

    @s.case("st_rot_k")
    def _(t):
        plot.rotate(t.var("x"), t.var("y"), 30, ret=[t.var("rx"), t.var("ry")])

    @s.case("st_rot3d")
    def _(t):
        X, Y, Z = plot.rotate3d(t.var("x"), t.var("y"), t.var("xy"), t.var("yz"), t.var("zx"))
        t.out("rx", X)
        t.out("ry", Y)
        t.out("rz", Z)

    @s.case("st_inside")
    def _(t):
        t.flag("f", plot.inside(t.var("x"), t.var("y"), t.var("x1"), t.var("x2"), -50, 50))

    @s.case("st_loc")
    def _(t):
        plot.setloc_box(LOC, t.var("x"), t.var("y"), t.var("s"))
        cx, cy = plot.loc_center(LOC)
        t.out("cx", cx)
        t.out("cy", cy)
        c2x, c2y = plot.loc_center(t.var("loc"))
        t.out("c2x", c2x)
        t.out("c2y", c2y)

    @s.case("st_loc_k")
    def _(t):
        plot.setloc_box(LOC, 100, -40, 8)

    @s.case("st_read")
    def _(t):
        x, y = plot.read_point(SS, t.var("sid"), t.var("i"))
        t.out("x", x)
        t.out("y", y)
        st, _n, _sc = SV.lookup(t.var("sid"))
        plot.read_from(SV, st, t.var("i"), ret=[t.var("vx"), t.var("vy")])

    # --- 빌드 오류 ---
    pr = Plotter(SS, unit=0, owner=P8, loc=LOC, name="pr")

    @pr.on_point
    def _pr(pt):
        pr.tick()

    @s.case("err_reentry_tick", expect_build_error=EudextError, expect_message="재진입")
    def _(t):
        pr.tick()

    pq = Plotter(SS, unit=0, owner=P8, loc=LOC, name="pq")

    @s.case("err_reentry_each", expect_build_error=EudextError, expect_message="재진입")
    def _(t):
        for _pt in pq.each():
            for _pt2 in pq.each():
                pass

    ph2 = Plotter(SS, unit=0, owner=P8, loc=LOC, name="ph2")

    @s.case("err_hook_after", expect_build_error=EudextError, expect_message="콜백을 더할 수 없습니다")
    def _(t):
        ph2.tick()
        ph2.on_point(lambda pt: None)

    for name, fn, msg in (
        ("err_loc0", lambda: Plotter(SS, 0, P8, loc=0), "로케이션"),
        ("err_loc_var", lambda: Plotter(SS, 0, P8, loc=EUDVariable()), "로케이션"),
        ("err_per_tick0", lambda: Plotter(SS, 0, P8, loc=LOC, per_tick=0), "per_tick"),
        ("err_per_tick_name", lambda: Plotter(SS, 0, P8, loc=LOC, per_tick="max"), "per_tick"),
        ("err_repeat", lambda: Plotter(SS, 0, P8, loc=LOC, repeat=1), "repeat"),
        ("err_capture", lambda: Plotter(SS, 0, P8, loc=LOC, capture="y"), "capture"),
        ("err_shapes", lambda: Plotter(5, 0, P8, loc=LOC), "ShapeSet"),
        ("err_delay_neg", lambda: Plotter(SS, 0, P8, loc=LOC, delay=-1), "delay"),
        ("err_count", lambda: Plotter(SS, 0, P8, loc=LOC, count=256), "count"),
        ("err_center", lambda: PA.start(0, center=(1, 2, 3)), "center"),
        ("err_center_type", lambda: PA.start(0, center=1.5), "center"),
        ("err_sid", lambda: PA.start(99), "범위 밖"),
        ("err_pt_outside", lambda: PA.pt.rotate(30), "본문 밖"),
        ("err_on_point", lambda: Plotter(SS, 0, P8, loc=LOC).on_point(5), "부를 수 있는"),
        ("err_setloc_loc", lambda: plot.setloc_box(EUDVariable(), 1, 2), "로케이션"),
        ("err_ratio0", lambda: plot.ratio(EUDVariable(), 1, 3, 0), "0 으로"),
        ("err_read_shapes", lambda: plot.read_point([RING], 0, 0), "ShapeSet"),
        ("err_cs_shapes", lambda: plot.create_shape([RING], 0, 0, LOC, P8), "ShapeSet"),
        ("err_float", lambda: plot.move(1.5, 0), "실수"),
    ):
        s.case(name, expect_build_error=EudextError, expect_message=msg)(lambda t, fn=fn: fn())

    pc2 = Plotter(SS, unit=0, owner=P8, loc=LOC, name="pc2")

    @pc2.on_created
    def _pc2(pt):
        pc2.tick()

    @s.case("err_reentry_created", expect_build_error=EudextError, expect_message="재진입")
    def _(t):
        pc2.tick()

    pc3 = Plotter(SS, unit=0, owner=P8, loc=LOC, name="pc3")

    @pc3.on_created
    def _pc3(pt):
        pt.skip()

    @s.case("err_skip_created", expect_build_error=EudextError, expect_message="on_created")
    def _(t):
        for _pt in pc3.each():
            pass

    ratio_body = Plotter(SS, unit=0, owner=P8, loc=LOC, name="pz")

    @s.case("err_ratio0_body", expect_build_error=EudextError, expect_message="0 으로")
    def _(t):
        for pt in ratio_body.each():
            pt.ratio(1, 0)


# =============================================================================================
# 실행·비교
# =============================================================================================


class Env:
    def __init__(self, s):
        self.s = s
        self.m = s.machine
        self.um = scmodel.unit_model(self.m)
        self.lm = locmodel.loc_model(self.m)
        self.seen = 0

    def fresh(self):
        self.s.reset()
        self.um.clear_log()
        self.um.clear_failures()
        self.lm.clear()
        self.seen = 0

    def new_plots(self):
        out = self.lm.plots[self.seen:]
        self.seen = len(self.lm.plots)
        return out


def cmp_tick(s, env, case, ref, label):
    r = s.run(case)
    got_raw = env.new_plots()
    got = [(p.rect, p.unit, p.player, p.count, p.props) for p in got_raw]
    want = ref.tick()
    ok = got == want and r.error is None
    s.expect_true(case, ok, label, "기록 %r\n기대 %r (오류 %r)" % (got[:6], want[:6], r.error))
    locs = {p.loc for p in got_raw}
    if got_raw:
        s.expect_true(case, locs == {ref.loc}, label + " 로케이션", repr(locs))
    flags = (r.values.get("busy"), r.values.get("done"), r.values.get("idx"), r.values.get("intr"))
    wantf = (ref.active, 1 - ref.active, ref.p, ref.interrupted)
    s.expect_true(case, flags == wantf, label + " busy/done/idx/intr", "%r (기대 %r)" % (flags, wantf))
    return r


def props_id(env):
    ids = {p.props for p in env.lm.plots if p.props is not None}
    return ids.pop() if len(ids) == 1 else None


def run_pa(s, env):
    for sid in range(len(LIST)):
        for cx, cy in ((2048, 2048), (100, 3000)):
            env.fresh()
            ref = Ref(LIST, 0, 7, per_tick=3, delay=1)
            s.run("pa_start", {"sid": sid, "cx": cx, "cy": cy})
            ref.start(sid, cx, cy)
            for k in range(len(LIST[sid]) // 3 + 3):
                cmp_tick(s, env, "pa_tick", ref, "pa sid=%d c=%d k=%d" % (sid, cx, k))
    # 찍는 중 다시 start → interrupted, 범위 밖 sid → 바로 끝, stop
    env.fresh()
    ref = Ref(LIST, 0, 7, per_tick=3, delay=1)
    for k in range(20):
        if k == 0:
            s.run("pa_start", {"sid": 0, "cx": 500, "cy": 500})
            ref.start(0, 500, 500)
        if k == 4:
            s.run("pa_start", {"sid": 1, "cx": 900, "cy": 700})
            ref.start(1, 900, 700)
        if k == 8:
            s.run("pa_start", {"sid": 99, "cx": 1, "cy": 1})
            ref.start(99, 1, 1)
        if k == 10:
            s.run("pa_start", {"sid": 2, "cx": 300, "cy": 300})
            ref.start(2, 300, 300)
        if k == 11:
            s.run("pa_stop")
            ref.stop()
        cmp_tick(s, env, "pa_tick", ref, "pa 재시작 k=%d" % k)


def run_pb(s, env, rng):
    combos = [
        dict(unit=0, owner=7, per_tick=1, delay=0, size=0, count=1),
        dict(unit=37, owner=0, per_tick=4, delay=3, size=16, count=2),
        dict(unit=101, owner=13, per_tick=7, delay=2, size=1, count=0),
        dict(unit=5, owner=3, per_tick=100, delay=1, size=32, count=5),
        dict(unit=1, owner=1, per_tick=0, delay=1, size=0, count=1),  # 0 이면 아무것도 안 찍고 계속 찍는 중
        dict(unit=1, owner=2, per_tick=M32, delay=5, size=0, count=1),
    ]
    for c in combos:
        for sid in (0, 3, 5, 7):
            env.fresh()
            owner = 0 if c["owner"] == 13 else c["owner"]  # CurrentPlayer → 기준 CP(P1)
            ref = Ref(LIST, c["unit"], owner, per_tick=c["per_tick"], delay=c["delay"], size=c["size"], count=c["count"])
            inp = dict(c, sid=sid, cx=rng.randrange(200, 3800), cy=rng.randrange(200, 3800))
            s.run("pb_start", inp)
            ref.start(sid, inp["cx"], inp["cy"])
            for k in range(min(len(LIST[sid]) + 4, 60)):
                cmp_tick(s, env, "pb_tick", ref, "pb %r sid=%d k=%d" % (c, sid, k))


def run_pc(s, env):
    for sid in (0, 3, 4, 5, 6):
        env.fresh()
        ref = Ref(LIST, 37, 0, per_tick="all", delay=2, size=16, repeat=True)
        s.run("pc_start", {"sid": sid, "cx": 1000, "cy": 1200})
        ref.start(sid, 1000, 1200)
        for k in range(26):
            if k == 20:
                s.run("pc_stop")
                ref.stop()
            cmp_tick(s, env, "pc_tick", ref, "pc(varray) sid=%d k=%d" % (sid, k))


def run_pd(s, env):
    env.fresh()
    ref = Ref(LIST, 40, 0, per_tick=5, delay=0, repeat=True, count=3, props="P")
    s.run("pd_start")
    ref.start(5, 1000, 900)
    pid = None
    for k in range(6):
        r = s.run("pd_tick")
        got = env.new_plots()
        want = ref.tick()
        pid = pid if pid is not None else (got[0].props if got else None)
        g = [(p.rect, p.unit, p.player, p.count, "P" if p.props == pid and p.action == "CreateUnitWithProperties" else None)
             for p in got]
        s.expect_true("pd_tick", g == want and r.values["busy"] == 1, "pd props·repeat k=%d" % k, "%r / %r" % (g, want))
    s.expect_true("pd_tick", pid is not None and pid >= 1, "pd UPRP 번호", repr(pid))


def run_pe(s, env, rng):
    cases = [(0, 0, 1, 1, 10000), (90, 5, 1, 1, 10000), (30, -7, 2, 3, 50), (45, 0, -1, 1, 0x7FFFFFFF), (-45, 12, 5, 0, 60),
             (180, 0, 0, 7, 1000), (359, 3, 3, -2, -20)]
    for ang, dx, my, dy, x2 in cases:
        for sid in (0, 1, 5):
            env.fresh()
            ref = Ref(LIST, 0, 7, per_tick=4, delay=1, body=ref_pe(ang, dx, my, dy, x2))
            s.run("pe_start", {"sid": sid, "ang": ang, "dx": dx, "my": my, "dy": dy, "x2": x2})
            ref.start(sid, 2000, 2000)
            for k in range(len(LIST[sid]) // 4 + 3):
                cmp_tick(s, env, "pe_tick", ref, "pe a=%d sid=%d k=%d" % (ang, sid, k))


def run_pf(s, env):
    for sid in (0, 1, 7):
        env.fresh()
        state = {"brk": 0}
        ref = Ref(LIST, 0, 7, per_tick=6, delay=1, body=ref_pf(state))
        s.run("pf_start", {"sid": sid, "brk": 0})
        ref.start(sid, 1500, 1500)
        for k in range(min(len(LIST[sid]) // 6 + 4, 60)):
            cmp_tick(s, env, "pf_tick", ref, "pf sid=%d k=%d" % (sid, k))


def run_pg(s, env):
    env.fresh()
    ref = Ref(LIST, 0, 7, per_tick=2, delay=1)
    env.um.fail_when(lambda rec: rec.loc == LOC and len(env.lm.plots) % 3 == 0)
    s.run("pg_start", {"sid": 0, "okc": 0, "epd": 0})
    ref.start(0, 800, 800)
    for k in range(22):
        cmp_tick(s, env, "pg_tick", ref, "pg capture k=%d" % k)
    okc = env.m.var("pg_start.okc")
    oks = sum(1 for p in env.lm.plots if p.ok)
    last = [p for p in env.lm.plots if p.ok][-1]
    s.expect_true("pg_tick", okc == oks and 0 < oks < 37, "pg ok 수 = 생성 성공 수", "%d / %d" % (okc, oks))
    s.expect_true("pg_tick", env.m.var("pg_start.epd") == scmodel.UnitModel.epd(last.indices[0]), "pg 마지막 epd")
    env.um.clear_failures()


def run_ph(s, env):
    for xy, zx, mx in ((0, 0, 1), (30, 60, 2), (90, -30, -1), (200, 15, 3)):
        for sid in (1, 5, 7):
            env.fresh()
            ref = Ref(LIST, 0, 7, per_tick=3, delay=1, size=2, body=ref_ph(xy, zx, mx))
            s.run("ph_start", {"sid": sid, "xy": xy, "zx": zx, "mx": mx, "cx": 3000})
            ref.start(sid, 3000, 700)
            for k in range(min(len(LIST[sid]) // 3 + 3, 30)):
                cmp_tick(s, env, "ph_tick", ref, "ph(varray) xy=%d sid=%d k=%d" % (xy, sid, k))


def run_pj(s, env):
    for sid in (0, 2, 5):
        env.fresh()
        ref = Ref(LIST, 0, 7, per_tick=4, delay=1, body=lambda x, y, p: (x, y, "skip" if p == 3 else "ok"))
        s.run("pj_start", {"sid": sid})
        ref.start(sid, 640, 480)
        for k in range(len(LIST[sid]) // 4 + 2):
            r = cmp_tick(s, env, "pj_tick", ref, "pj EUDFunc 콜백 sid=%d k=%d" % (sid, k))
        s.expect_true("pj_tick", r["cnt"] == len(LIST[sid]), "pj 콜백 호출 수 sid=%d" % sid, repr(r.values))


def run_pi(s, env):
    lm = env.lm
    # 자기 로케이션 중심 (시작 때 한 번 읽는다 — 찍으면서 로케이션이 움직여도 중심은 그대로)
    for rect in ((1312, 1216, 1440, 1312), (101, 50, 102, 51), (-10, -30, 5, 7)):
        env.fresh()
        lm.set_location(LOC2, *rect)
        cx, cy = int((rect[0] + rect[2]) / 2), int((rect[1] + rect[3]) / 2)  # 0 방향
        ref = Ref(LIST, 0, 0, per_tick=5, delay=1, loc=LOC2)
        s.run("pi_start_loc", {"sid": 1})
        ref.start(1, cx, cy)
        for k in range(9):
            cmp_tick(s, env, "pi_tick", ref, "pi 자기 로케이션 %r k=%d" % (rect, k))
    # 다른 로케이션 (번호 변수), 이름, 중간에 set_center
    env.fresh()
    lm.set_location(20, 3000, 2000, 3001, 2003)
    ref = Ref(LIST, 0, 0, per_tick=5, delay=1, loc=LOC2)
    s.run("pi_start_other", {"sid": 0, "loc": 20})
    ref.start(0, 3000, 2001)
    for k in range(9):
        if k == 3:
            s.run("pi_set_center", {"cx": 77, "cy": 88})
            ref.set_center(77, 88)
        cmp_tick(s, env, "pi_tick", ref, "pi 다른 로케이션 k=%d" % k)
    env.fresh()
    lm.set_location(13, 2048, 2048, 2048, 2048)  # 에뮬레이터 메모리에는 맵의 MRGN 이 없다
    ref = Ref(LIST, 0, 0, per_tick=5, delay=1, loc=LOC2)
    s.run("pi_start_name", {"sid": 2})
    ref.start(2, 2048, 2048)
    for k in range(3):
        cmp_tick(s, env, "pi_tick", ref, "pi 이름 로케이션 k=%d" % k)


def run_create_shape(s, env, rng):
    for sid in (0, 1, 3, 5, 6, 7, 8):
        env.fresh()
        unit, cx, cy, sz = rng.randrange(0, 200), rng.randrange(0, 4000), rng.randrange(0, 4000), rng.choice((0, 1, 16))
        s.run("cs_var", {"sid": sid, "unit": unit, "cx": cx, "cy": cy, "sz": sz})
        pts = LIST[sid].points if sid < len(LIST) else ()
        want = [((x + cx - sz, y + cy - sz, x + cx + sz, y + cy + sz), unit, 7, 2) for x, y in pts]
        got = [(p.rect, p.unit, p.player, p.count) for p in env.new_plots()]
        s.expect_true("cs_var", got == want, "create_shape sid=%d" % sid, "%r / %r" % (got[:4], want[:4]))
    env.fresh()
    env.lm.set_location(LOC2, 1312, 1216, 1440, 1312)
    s.run("cs_const")
    want = [((x + 1376 - 4, y + 1264 - 4, x + 1376 + 4, y + 1264 + 4), 47, 0, "CreateUnitWithProperties") for x, y in RAY.points]
    got = [(p.rect, p.unit, p.player, p.action) for p in env.new_plots()]
    s.expect_true("cs_const", got == want, "create_shape 상수·varray·props·loc 중심", "%r / %r" % (got, want))


def run_stateless(s, env, rng):
    def g_xy(r):
        return rng.choice((rng.randint(-4000, 4000), rand32(r)))

    def g_small(r):
        return r.randint(-20, 20) & M32

    def ratio_ref(x, y, mx, dx, my, dy):
        return {"rx": R.ratio(x, mx, dx, "ctrig"), "ry": R.ratio(y, my, dy, "ctrig")}

    edges = (0, 1, M32, 2, 100, 0xFFFFFF9C, 0x7FFFFFFF, 0x80000000)
    s.diff("st_ratio", ratio_ref, {"x": edges, "y": (0, 7, M32), "mx": (0, 1, M32, 3), "dx": (0, 1, 2, M32),
                                   "my": (1, 5), "dy": (0, 3)}, n=300, max_edges=600)
    s.diff("st_ratio", ratio_ref, {"x": lambda r: g_xy(r), "y": lambda r: g_xy(r), "mx": g_small, "dx": g_small,
                                   "my": g_small, "dy": g_small}, n=300, edges=False, seed=3)
    s.diff("st_ratio_k", lambda x, y: {"rx": R.ratio(x, 150, 100), "ry": R.ratio(y, u32(-3), 7)},
           {"x": edges, "y": edges}, n=200)
    s.diff("st_ratio_part", lambda x, y, mx, dy: {"rx": u32(x * mx), "ry": R.sdiv(y, dy, "ctrig")[0]},
           {"x": edges, "y": edges, "mx": (0, 3, M32), "dy": (0, 2, M32)}, n=200)
    s.diff("st_move", lambda x, y, dx: {"rx": u32(x + dx), "ry": u32(y - 7)}, {"x": edges, "y": edges, "dx": edges}, n=200)
    a_edges = (0, 1, 30, 45, 89, 90, 91, 180, 270, 359, 360, 361, M32, 0xFFFFFFA6, 0x80000000)
    xy_edges = (0, 1, M32, 32, 0xFFFFFFE0, 32767, 0xFFFF8001)
    s.diff("st_rot", lambda x, y, a: dict(zip(("rx", "ry"), R.rotate(x, y, a))),
           {"x": xy_edges, "y": (0, 16, 0xFFFFFFF0), "a": a_edges}, n=300, max_edges=400)
    s.diff("st_rot_k", lambda x, y: dict(zip(("rx", "ry"), R.rotate(x, y, 30))), {"x": xy_edges, "y": xy_edges}, n=100)
    s.diff("st_rot3d", lambda x, y, xy, yz, zx: dict(zip(("rx", "ry", "rz"), R.rotate3d(x, y, xy, yz, zx))),
           {"x": (0, 27, 0xFFFFFFF0), "y": (0, 100, M32), "xy": (0, 30, 359), "yz": (0, 90, 181), "zx": (0, 45, M32)},
           n=100, max_edges=300)

    def inside_ref(x, y, x1, x2):
        sx, sy = s32(x), s32(y)
        return {"f": int(s32(x1) < sx < s32(x2) and -50 < sy < 50)}

    s.diff("st_inside", inside_ref, {"x": (0, 5, M32, 0x80000000, 0x7FFFFFFF, 100), "y": (0, 49, 50, 0xFFFFFFCE, 0xFFFFFFCF),
                                     "x1": (0, M32, 0x80000000), "x2": (1, 100, 0x7FFFFFFF)}, n=300, max_edges=600)
    for x, y, sz, loc, lrect in ((100, 200, 0, 20, (0, 0, 7, 9)), (5, 5, 3, 21, (-7, -9, 0, 0)), (0x7FFFFFF0, 0, 20, 22, (1, 2, 4, 3)),
                                  (0xFFFFFFF0, 0xFFFFFF00, 1, 23, (-3, -3, 2, 2))):
        env.fresh()
        env.lm.set_location(loc, *lrect)
        r = s.run("st_loc", {"x": x, "y": y, "s": sz, "loc": loc})
        X, Y = s32(x), s32(y)
        box = (s32(X - sz), s32(Y - sz), s32(X + sz), s32(Y + sz))
        c = (u32(int((box[0] + box[2]) / 2)), u32(int((box[1] + box[3]) / 2)))
        c2 = (u32(int((lrect[0] + lrect[2]) / 2)), u32(int((lrect[1] + lrect[3]) / 2)))
        s.expect_true("st_loc", env.lm.rect(LOC) == box and (r["cx"], r["cy"]) == c and (r["c2x"], r["c2y"]) == c2,
                      "setloc_box·loc_center %r" % ((x, y, sz),), "%r %r / %r %r %r" % (env.lm.rect(LOC), r.values, box, c, c2))
    env.fresh()
    s.run("st_loc_k")
    s.expect_true("st_loc_k", env.lm.rect(LOC) == (92, -48, 108, -32), "setloc_box 상수", repr(env.lm.rect(LOC)))
    for sid, i in ((0, 0), (0, 36), (1, 5), (7, 299), (5, 2), (9, 0), (6, 0)):
        pts = LIST[sid].points if sid < len(LIST) else ()
        x, y = pts[i] if i < len(pts) else (0, 0)
        want = {"x": u32(x), "y": u32(y)}
        if pts:
            want.update(vx=u32(x), vy=u32(y))
        s.check("st_read", {"sid": sid, "i": i}, want, label="read_point/read_from %d/%d" % (sid, i))


def python_checks(ck):
    LoadMap(BASE_MAP)
    ck.eq("ratio 상수", plot.ratio(7, -9, 3, 2, 1, 1), (10, -9))
    ck.eq("ratio 상수 곱만", plot.ratio(-7, 9, mx=3), (-21, 9))
    ck.eq("ratio 없음", plot.ratio(5, 6), (5, 6))
    ck.eq("move 상수", plot.move(1, 2, 3, -4), (4, -2))
    ck.eq("move 상수 wrap", plot.move(0x7FFFFFFF, 0, 1, 0), (-(1 << 31), 0))
    ck.eq("rotate 상수 (90 = 시계 방향: 12시 → 3시)", plot.rotate(0, -32, 90), (32, 0))
    ck.eq("rotate 상수 = CA_Rotate", plot.rotate(27, -15, 30), tuple(s32(v) for v in R.rotate(27, u32(-15), 30)))
    ck.eq("rotate3d 상수", plot.rotate3d(27, 100, 30, 90, 45), tuple(s32(v) for v in R.rotate3d(27, 100, 30, 90, 45)))
    ck.eq("read_point 상수", plot.read_point(SS, 1, 3), STAR.points[3])
    ck.eq("inside 빈 조건", plot.inside(1, 2), [])
    ck.true("Plotter repr", "pa" in repr(PA) and "loc=26" in repr(PA), repr(PA))
    ck.raises("없는 로케이션 이름", Exception, lambda: Plotter(SS, 0, P8, loc="No Such Loc").loc)
    ck.true("Point repr", "Point" in repr(PA.pt), repr(PA.pt))
    ck.eq("Shape 목록도 받는다", type(Plotter([RING], 0, P8, loc=LOC).shapes).__name__, "ShapeSet")
    ck.eq("per_tick all", Plotter(SS, 0, P8, loc=LOC, per_tick="all")._per_tick, M32)
    ck.eq("로케이션 이름 (맵을 불러온 뒤 번호로)", Plotter(SS, 0, P8, loc="Location 13").loc, 13)
    ck.eq("유닛 이름은 그대로 두었다가 CreateUnit 이 바꾼다", Plotter(SS, "Zerg Scourge", P8, loc=1)._unit, "Zerg Scourge")
    ck.eq("주인 CurrentPlayer", Plotter(SS, 0, CurrentPlayer, loc=1)._owner, 13)
    ck.raises("주인 문자열은 받지 않음", EudextError, Plotter, SS, 0, "Player 8", loc=1)
    ck.eq("주인 P8", Plotter(SS, 0, P8, loc=1)._owner, 7)


def trigger_independence(ck):
    """3.8: 찍기 루프(tick 본문 + 호출 자리)의 트리거 수가 도형 수·점 수와 무관한가."""
    LoadMap(BASE_MAP)
    small = ShapeSet([Shape([(1, 2)])], name="ind_small")
    rng = random.Random(5)
    big = ShapeSet([Shape([(rng.randint(-900, 900), rng.randint(-900, 900)) for _ in range(rng.choice((1, 37, 1700)))])
                    for _ in range(60)], name="ind_big")
    counts = {}
    with _compat.isolated_scope():
        Plotter(small, 0, P8, loc=LOC, per_tick=3, name="warm").tick()  # 공유 본문(점 읽기 등)을 먼저 만든다
        for tag, ss in (("small", small), ("big", big), ("small2", small)):
            for storage in ("db",):
                c0 = GetTriggerCounter()
                pl = Plotter(ss, 0, P8, loc=LOC, per_tick=3, name="ind_" + tag)
                pl.start(0, center=(1, 2))
                pl.tick()
                pl.tick()
                counts[tag] = GetTriggerCounter() - c0
                c0 = GetTriggerCounter()
                pl.start(EUDVariable(), center=(1, 2))
                for _pt in Plotter(ss, 0, P8, loc=LOC, name="ind_e" + tag).each():
                    pass
                counts[tag + "_var"] = GetTriggerCounter() - c0
    print("  트리거 수 (도형 1개·1점 / 60개·%d점): %r" % (big.stored_points, counts))
    ck.eq("tick 트리거 수 무관", counts["small"], counts["big"])
    ck.eq("변수 start + each 트리거 수 무관", counts["small_var"], counts["big_var"])
    ck.eq("같은 조건이면 같은 수", counts["small"], counts["small2"])
    _compat.reset_build_state()


# =============================================================================================
# epScript 예제 · 인게임 맵
# =============================================================================================


def _load_eps(name):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_plot_eps_" + name)
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name + ".eps"), os.path.join(work, name + ".eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, name + ".eps"), {})


def eps_checks(ck):
    src = open(os.path.join(EX, "plot_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("plot_example.eps", src)
    ck.eq("plot_example 번역 오류", nerr, 0)
    for needle in ("plot.Plotter(shapes, unit=", "for pt in pl.each():", "_ATTW(pt, 'x').__iadd__(10)",
                   "EUDContinue()", "pl.start(", "if EUDIf()(pl.done):", "plot.f_create_shape(", "plot.f_rotate("):
        ck.true("eps: " + needle, out is not None and needle in out, "")
    src = open(os.path.join(EX, "plot_ingame.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("plot_ingame.eps", src)
    ck.eq("plot_ingame 번역 오류", nerr, 0)


def eps_emulate(ck):
    mod = _load_eps("plot_example")
    names = ("frame", "made", "skipped", "rounds", "lastIdx", "rx", "ry")
    prog = emu.Program(mod.afterTriggerExec)
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m, units={})
    lm = locmodel.install(m)
    rows = []
    for _ in range(40):
        m.cycle()
        rows.append({n: m.var(n) for n in names})
    got = rows[-1]
    print("  plot epScript 에뮬레이션: 페이로드 %d B, %r, 생성 %d" % (prog.payload_size, got, len(lm.plots)))
    ring = mod.ring
    # 예제: 링을 프레임마다 4점씩, 점 1 은 continue(건너뜀), 매 링 끝에 다시 start (rounds 증가), pt.x += 10
    ck.eq("eps rotate 상수 (0, -32) 90° → (32, 0)", (s32(got["rx"]), s32(got["ry"])), (32, 0))
    want = []
    rounds = 0
    frame = 0
    ref = Ref([ring], 0, 7, per_tick=4, delay=1, body=lambda x, y, p: (x + 10, y, "continue" if p == 1 else "ok"))
    for f in range(40):
        frame += 1
        if not ref.active:
            ref.start(0, 1024 + 100 * rounds, 1024)
            rounds += 1
        want.extend((r[0][0], r[0][1]) for r in ref.tick())
    gotp = [(p.rect[0], p.rect[1]) for p in lm.plots if p.loc == 26]
    ck.eq("eps 찍은 좌표", gotp, want)
    ck.eq("eps 값", (got["frame"], got["rounds"], got["made"], got["skipped"]), (40, rounds, len(want), (rounds - 1) + 1))
    cs = [p for p in lm.plots if p.loc == 27]
    ck.eq("eps create_shape 한 번 (첫 프레임, ray 5점)", [(p.x, p.y) for p in cs], [(2048 + x, 2048 + y) for x, y in mod.ray.points])


def ingame_emulate(ck):
    """인게임 확인 맵을 끝까지 돌린다: 맵의 자체 점검 모두 통과, 단계별로 찍은 좌표 = 참조 모델."""
    from eudplib import EncodeUnit

    mod = _load_eps("plot_ingame")
    names = ("frame", "phase", "made", "checks", "good", "rounds")
    prog = emu.Program(mod.afterTriggerExec)
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m, units={})
    lm = locmodel.install(m)
    err = None
    try:
        m.cycle(mod.TOTAL_FRAMES)
    except emu.EmuError as e:
        err = str(e)
    got = {n: m.var(n) for n in names}
    print("  인게임 맵 에뮬레이션: %r, 페이로드 %d B, 생성 %d" % (got, prog.payload_size, len(lm.plots)))
    ck.eq("ingame emu 오류", err, None)
    ck.eq("ingame 값", got, {"frame": mod.TOTAL_FRAMES, "phase": mod.LAST_PHASE, "made": mod.MADE_TOTAL,
                              "checks": mod.CHECKS, "good": mod.CHECKS, "rounds": 3})
    # 참조: 맵과 같은 순서(A B C D E F G S R)로 프레임마다
    shapes = list(mod.shapes.shapes)
    u = EncodeUnit
    rounds = {"n": 0}

    def rot90(x, y, p):
        X, Y = R.rotate(x, y, 90)
        return s32(X), s32(Y), "ok"

    def body_r(x, y, p):
        if p == 0:
            rounds["n"] += 1
        return x, y, "ok"

    plans = [
        (1, 0, (1850, 1880), u("Zerg Scourge"), 1, 4, False, None),
        (1, 1, (2230, 1880), u("Zerg Mutalisk"), 1, 4, False, None),
        (1, 2, (1800, 2260), u("Terran Wraith"), 1, 4, False, None),
        (1, 3, (1950, 2230), u("Protoss Scout"), 1, 4, False, None),
        (1, 2, (2150, 2230), u("Protoss Corsair"), 1, 4, False, rot90),
        (mod.PH2, 0, (1850, 2048), u("Zerg Scourge"), 6, 1, False, None),
        (mod.PH2, 0, (2230, 2048), u("Zerg Mutalisk"), 6, 8, False, None),
        (mod.PH3, 4, (2048, 2048), u("Zerg Scourge"), 1, 4, False, None),
        (mod.PH4, 0, (2048, 2048), u("Terran Wraith"), 2, 2, True, body_r),
    ]
    refs = [Ref(shapes, unit, 0, per_tick=pt_, delay=d, repeat=rep, body=b) for _f, _s, _c, unit, pt_, d, rep, b in plans]
    want = []
    for frame in range(1, mod.TOTAL_FRAMES + 1):
        for (f0, sid, (cx, cy), *_rest), ref in zip(plans, refs):
            if frame == f0:
                ref.start(sid, cx, cy)
        if refs[-1].p == 0 and rounds["n"] == 3:
            refs[-1].stop()
        for ref in refs:
            want.extend((frame - 1, r[1], r[0][0], r[0][1]) for r in ref.tick())
    gotp = [(p.cycle, p.unit, p.x, p.y) for p in lm.plots if p.loc == 26]
    ck.eq("ingame 찍은 점 수", len(gotp), len(want))
    ck.eq("ingame 찍은 좌표·유닛·프레임", gotp, want)
    first = [(p.x - 1850, p.y - 1880) for p in lm.plots if p.unit == u("Zerg Scourge")][:8]
    ck.eq("ingame 원 순서 (가운데 → 12시 → 시계 방향)", first,
          [(0, 0), (0, -32), (27, -15), (27, 15), (0, 32), (-27, 15), (-27, -16), (0, -64)])
    e = [(p.x - 2150, p.y - 2230) for p in lm.plots if p.unit == u("Protoss Corsair")]
    d = [(p.x - 1950, p.y - 2230) for p in lm.plots if p.unit == u("Protoss Scout")]
    ck.eq("ingame 실행 회전 = 정적 회전 (3시 방향)", (e, d), ([(32 * k, 0) for k in range(1, 6)],) * 2)
    texts = [x for x in m.log if x[0] == "act" and x[1] == 9]
    ck.true("ingame 출력 줄 (다름 줄 없음)", len(texts) == 11, len(texts))


def euddraft_builds(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("plot_example", "plot_ingame"):
        work = os.path.join(_common.WORK, "t_plot_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")
        ck.true("boot preload " + name, "preload=shape,plot" in r.log, r.log[:600])
        ck.true("freeze off " + name, not r.freeze)


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

C_SS = ShapeSet([BIG, RING], name="cost_p")
C_SV = ShapeSet([BIG, RING], storage="varray", name="cost_pv")
C_ONE = ShapeSet([Shape([(0, 0)])], name="cost_one")


def _cost_tick(ss, per_tick, **kw):
    pl = Plotter(ss, unit=0, owner=P8, loc=LOC, per_tick=per_tick, delay=1, **kw)

    def setup(t):
        pl.start(0, center=(2000, 2000))

    def build(t):
        pl.tick()

    return dict(build=build, setup=setup, funcs=[shape._db_reader()])


def _cost_rot(per_tick):
    pl = Plotter(C_SS, unit=0, owner=P8, loc=LOC, per_tick=per_tick, delay=1)
    ang = EUDVariable(30)

    @pl.on_point
    def _(pt):
        pt.rotate(ang)

    def setup(t):
        pl.start(0, center=(2000, 2000))

    return dict(build=lambda t: pl.tick(), setup=setup)


_idle = Plotter(C_SS, unit=0, owner=P8, loc=LOC, per_tick=1)
_VS = EUDVariable(16)
_VC = EUDVariable(1)
_st = Plotter(C_SS, unit=0, owner=P8, loc=LOC, per_tick=1)

COST_CASES = [
    CostCase("tick — 찍지 않을 때(빈 프레임)", lambda t: _idle.tick(), note="호출 자리 칸은 첫 호출이 만든 본문(서브루틴) 포함, 뒤 호출은 1"),
    CostCase("tick db per_tick=1 (한 점)", **_cost_tick(C_SS, 1)),
    CostCase("tick db per_tick=10 (열 점)", **_cost_tick(C_SS, 10), note="(10점 − 1점)/9 = 점당 실행"),
    CostCase("tick varray per_tick=1", **_cost_tick(C_SV, 1)),
    CostCase("tick varray per_tick=10", **_cost_tick(C_SV, 10)),
    CostCase("tick db per_tick=10, size=16", **_cost_tick(C_SS, 10, size=16)),
    CostCase("tick db per_tick=10, 인자 모두 변수", **_cost_tick(C_SS, 10, size=_VS, count=_VC), note="unit/owner 도 변수면 +2~3/점"),
    CostCase("tick db per_tick=10, capture=True", **_cost_tick(C_SS, 10, capture=True)),
    CostCase("tick db per_tick=1, 도형 1개·1점 ShapeSet", **_cost_tick(C_ONE, 1), note="본문 크기가 도형 수와 무관"),
    CostCase("tick + pt.rotate(변수 각) per_tick=10", **_cost_rot(10), note="각이 같은 점은 Rotator 89"),
    CostCase("start(상수 sid, (상수, 상수))", lambda t: _st.start(1, center=(10, 20))),
    CostCase("start(변수 sid, (상수, 상수))", lambda t: _st.start(t.var("s"), center=(10, 20)), {"s": 1}),
    CostCase("start(상수 sid, center=\"loc\")", lambda t: _st.start(1)),
    CostCase("create_shape(변수 sid) 37점", lambda t: plot.create_shape(C_SS, t.var("s"), 0, LOC, P8, center=(9, 9)),
             {"s": 1}, note="37점, 인자가 모두 변수(EUDFunc 인자) — 점마다 약 80"),
    CostCase("plot.ratio(변수×6)", lambda t: plot.ratio(*[t.var(k) for k in ("x", "y", "a", "b", "c", "d")]),
             {"x": 100, "y": 7, "a": 3, "b": 2, "c": 5, "d": 4}),
    CostCase("plot.move(변수, 변수, 변수, 상수)", lambda t: plot.move(t.var("x"), t.var("y"), t.var("d"), 3)),
    CostCase("plot.loc_center(상수 loc)", lambda t: plot.loc_center(LOC2)),
    CostCase("plot.setloc_box(상수 loc, 변수, 변수, 16)", lambda t: plot.setloc_box(LOC, t.var("x"), t.var("y"), 16)),
]


def main():
    rng = random.Random(21)
    ck = Checker("t_plot (python)")
    python_checks(ck)
    trigger_independence(ck)

    s = Suite("t_plot", memory={"units": {}}, prep=lambda m: locmodel.install(m))
    build_cases(s)
    s.build()
    env = Env(s)
    run_pa(s, env)
    run_pb(s, env, rng)
    run_pc(s, env)
    run_pd(s, env)
    run_pe(s, env, rng)
    run_pf(s, env)
    run_pg(s, env)
    run_ph(s, env)
    run_pj(s, env)
    run_pi(s, env)
    run_create_shape(s, env, rng)
    run_stateless(s, env, rng)
    ok1 = s.report()

    cke = Checker("t_plot (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    ingame_emulate(cke)
    euddraft_builds(cke)
    finish(ok1, ck.report(), cke.report())


if __name__ == "__main__":
    main()
