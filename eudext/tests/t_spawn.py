"""`spawn` 시험 1 (에뮬레이터 + scmodel 유닛·글 모델 + testing/locmodel): 대기열 동작.

- S1 9.1 표 A~P (프레임별 소환 수·좌표·반납 시점 = 참조 모델 `ref_spawn` — 참조 모델이 먼저 표 기대값과 같은지 확인)
- 여러 작업 동시·층 사이 빈 프레임·LM 스케줄·delay·넘침(J·K·L — 표 밖 쓰기 없음)·tick 중 push(M)·clear(O)
- rtype 등록·내장 핸들러 10종·사용자 핸들러(파이썬·EUDFunc 5인자)·명령 속성(Order 상자·목표)·중심 모드 5종·
  명령 목표 모드·spawn_now·scan_effect·on_create·생성 실패·등록 안 한 rtype·CP 보존·debug 문구
- 빌드 오류(점 0개 상수 도형·유닛/도형 수 불일치·로케이션 번호·재진입·2단계 자리 …)·표 복사(받은 목록을 고치지 않음)
- 트리거 수가 도형 수·점 수와 무관(3.8), epScript 예제·인게임 확인 맵의 번역·에뮬레이션·euddraft 빌드, COST_CASES

좌표 변환 벡터(S1 9.2)와 무작위 차등은 `t_spawn_xform.py`.

python tests/t_spawn.py
비용 표: python tools/cost.py tests/t_spawn.py [--append --out <파일> --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402

from eudplib import (  # noqa: E402
    Exactly,
    Memory,
    RawTrigger,
    P2,
    P8,
    Attack,
    CompressPayload,
    CurrentPlayer,
    DoActions,
    EUDEndIf,
    EUDFunc,
    EUDIf,
    EUDVariable,
    GetTriggerCounter,
    LoadMap,
    Move,
    SetMemory,
    SetTo,
    f_getcurpl,
    f_setcurpl,
)

import ref_mathx as RM  # noqa: E402
import ref_spawn as RS  # noqa: E402
from eudext import _compat, spawn, units  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.shape import CX, Shape, ShapeSet  # noqa: E402
from eudext.spawn import Effect, Order, Spawner, at_unit  # noqa: E402
from eudext.testing import BASE_MAP, emu, locmodel, scmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
EX = os.path.join(_common.PKG, "examples")
u32, s32 = RM.u32, RM.s32
LOC, LOC2 = 26, 27  # 기준 맵: 26 = "Location 0" (0,0,0,0), 27 = (1312,1216,1440,1312)
HOME = 13  # (2048, 2048)
SCAN_IMG = spawn.SCAN_SPRITE_IMAGE
N_EVERYONE = 5  # players.Everyone 대상 수(사람 1 + 관전자 4) — 글 모델은 대상마다 한 줄씩 기록
DRAW = spawn.DRAW_FUNC


def rpts(n, seed, span=200):
    rng = random.Random(seed)
    return [(rng.randint(-span, span), rng.randint(-span, span)) for _ in range(n)]


SH41 = Shape(rpts(41, 1), name="sh41")
SH41B = Shape(rpts(41, 2), name="sh41b")
SH300 = Shape(rpts(300, 3), name="sh300")
SH255 = Shape(rpts(255, 4), name="sh255")
SH256 = Shape(rpts(256, 5), name="sh256")
SH12S = Shape(rpts(12, 6), schedule=[5, 0, 7], name="sh12s")
SH1 = Shape([(0, 0)], name="one")
SH3 = Shape([(-5, 0), (0, 0), (5, 0)], name="three")
EMPTY = Shape([], name="empty")
RING = CX(seed=1234).call("CSMakeCircle", 6, 32, 0, 37, 0)

TABLE = ["A", "B", "C", "C'", "D", "E", "F", "G", "H", "I"]
TSHAPE = {41: SH41, 300: SH300, 255: SH255, 256: SH256, 12: SH12S}


def table_layers(name):
    layers, _want, _end = RS.TABLE_91[name]
    out = []
    for k, (n, lm, d, _sc) in enumerate(layers):
        sh = TSHAPE[n] if not (n == 41 and k == 1) else SH41B
        out.append((37 + k, sh, lm, d))
    return out


# =============================================================================================
# Spawner 들 (모듈 전역 — 케이스 본문이 쓴다)
# =============================================================================================

G = {k: EUDVariable() for k in ("chain", "hx", "hy", "hpx", "hpy", "hcx", "hcy", "hepd", "hunit", "howner", "hcount",
                                "ef_epd", "ef_unit", "ef_owner", "ef_x", "ef_y", "ef_n", "oc_idx", "oc_n")}

SA = Spawner(capacity=8, loc=LOC, loc2=LOC2, default_target=HOME, debug=True, name="sa")
SA_EMPTY_SID = SA.shapes.add(EMPTY)
SJ = Spawner(capacity=4, loc=LOC, loc2=LOC2, on_full="report", name="sj")
SM = Spawner(capacity=8, loc=LOC, loc2=LOC2, name="sm")
SR = Spawner(capacity=16, loc=LOC, loc2=LOC2, default_target=HOME, debug=True, name="sr")
SE = Spawner(capacity=4, loc=LOC, loc2=LOC2, name="se")
DATA = units.UnitData(hp2="dword", tag=("byte", 9))
SO = Spawner(capacity=4, loc=LOC, loc2=LOC2, on_create=DATA, name="so")
SO2 = Spawner(capacity=4, loc=LOC, loc2=LOC2, props=None, name="so2")
SV = Spawner(capacity=6, loc=LOC, loc2=LOC2, storage="varray", name="sv")


@SM.rtype("Chain")
def _chain(s):
    # 첫 소환 때 한 번: 그 점을 중심으로 1점 작업을 넣는다 (M — 다음 tick 부터 돌아야 한다)
    if EUDIf()(G["chain"].Exactly(1)):
        DoActions(G["chain"].SetNumber(0))
        SM.push(40, SH1, center=(s.px, s.py), owner=P8)
    EUDEndIf()


SR.rtype("Home", SR.builtin.attack_default, id=1)
SR.rtype("Kill", SR.builtin.kill_all_of_type, id=3)
SR.rtype("RT", SR.builtin.remove_timer(77), id=5)
SR.rtype("Nothing", id=6)
SR.rtype("Center", SR.builtin.attack_center, id=7)
SR.rtype("Skill", SR.builtin.skill_unit, id=8)
SR.rtype("NX", SR.builtin.nxct, id=106)
SR.rtype("NSpA", SR.builtin.nspeed(attack=True), id=147)
SR.rtype("NSpW", SR.builtin.nspeed(attack=False), id=148)
SR.rtype("Vis", SR.builtin.vision, id=180)
SR.rtype("JYD", SR.builtin.force_order(), id=187)
SR.rtype("NoSp", SR.builtin.no_speed, id=201)


@SR.rtype("Py", id=50)
def _py_handler(s):
    x, y = s.pos()
    DoActions([G["hcount"].AddNumber(1)])
    G["hx"] << x
    G["hy"] << y
    G["hpx"] << s.px
    G["hpy"] << s.py
    G["hcx"] << s.cx
    G["hcy"] << s.cy
    G["hepd"] << s.epd
    G["hunit"] << s.unit
    G["howner"] << s.owner
    s.set_invincible()
    s.order(Move, 500, 600)


@EUDFunc
def _ef_handler(epd, unit, owner, x, y):
    G["ef_epd"] << epd
    G["ef_unit"] << unit
    G["ef_owner"] << owner
    G["ef_x"] << x
    G["ef_y"] << y
    DoActions(G["ef_n"].AddNumber(1))


@EUDFunc
def _ef_zero():
    DoActions(G["ef_n"].AddNumber(100))


SR.rtype_func("EF", _ef_handler, _ef_zero, id=51)
SR.default_rtype = None

SO2.rtype("Home2", lambda s: s.default_order(Attack, (321, 654)), id=2)

# 재진입·늦은 등록 (빌드 오류 케이스용 — 다른 Spawner)
SX1 = Spawner(capacity=2, loc=LOC, loc2=LOC2, name="sx1")
SX1.rtype("Bad", lambda s: SX1.tick())
SX2 = Spawner(capacity=2, loc=LOC, loc2=LOC2, name="sx2")
SX2.rtype("Bad", lambda s: SX2.spawn_now(1))
SX3 = Spawner(capacity=2, loc=LOC, loc2=LOC2, name="sx3")
SX3.rtype("Bad", lambda s: SX3.clear())
SX4 = Spawner(capacity=2, loc=LOC, loc2=LOC2, name="sx4")  # default_target 없음
SX4.rtype("Home", SX4.builtin.attack_default)
SX5 = Spawner(capacity=2, loc=LOC, loc2=LOC2, name="sx5")


def _oc_hook(i):
    G["oc_idx"] << i
    DoActions(G["oc_n"].AddNumber(1))


SO3 = Spawner(capacity=4, loc=LOC, loc2=LOC2, on_create=_oc_hook, name="so3")

# 전역 회전을 점마다 읽는지 (핸들러가 소환마다 90° 씩 돌린다 — 원본 G_CB_RotateV 를 매 점 읽는 것)
SG = Spawner(capacity=2, loc=LOC, loc2=LOC2, name="sg")
SH4 = Shape([(0, -32)] * 4, name="ray4")


@SG.rtype("Turn")
def _turn(s):
    SG.rotation += 90


# =============================================================================================
# 케이스
# =============================================================================================


def build_cases(s):
    # ---------------------------------------------------------------- 9.1 표 (SA)
    @s.case("sa_push")
    def _(t):
        sc = t.var("sc")
        for idx, name in enumerate(TABLE):
            if EUDIf()(sc.Exactly(idx + 1)):
                job = SA.job(center=(1000 + 10 * idx, 1000), owner=P8)
                for unit, sh, lm, d in table_layers(name):
                    job.layer(unit, sh, lm=lm, delay=d)
                job.push()
            EUDEndIf()

    @s.case("sa_push_var")
    def _(t):
        # P: 변수 sid 가 점 0개 도형(또는 범위 밖) → 바로 끝 + debug 문구
        SA.push(1, t.var("sid"), center=(500, 500), lm=t.var("lm"))

    @s.case("sa_tick")
    def _(t):
        SA.tick()
        t.out("live", SA.live)
        t.out("ovf", SA.overflow)

    @s.case("sa_clear")
    def _(t):
        SA.clear()
        t.out("live", SA.live)

    @s.case("sa_storage")
    def _(t):
        t.watch("S", SA.pool._S)

    # ---------------------------------------------------------------- J·K·L (SJ, capacity 4)
    @s.case("sj_push")
    def _(t):
        n = t.var("n")
        if EUDIf()(n.Exactly(1)):
            SJ.push(37, SH41, center=(t.var("cx"), 1200), lm=10)
        EUDEndIf()
        if EUDIf()(n.Exactly(3)):
            SJ.job(center=(1500, 1500)).layer(37, SH41, lm=10).layer(38, SH41B, lm=10).layer(39, SH3).push()
        EUDEndIf()
        if EUDIf()(n.Exactly(2)):
            SJ.job(center=(1700, 1700)).layer(40, SH3).layer(41, SH3).push()
        EUDEndIf()
        t.out("live", SJ.live)
        t.out("ovf", SJ.overflow)

    @s.case("sj_tick")
    def _(t):
        SJ.tick()
        t.out("live", SJ.live)
        t.watch("S", SJ.pool._S)
        t.watch("TRASH", SJ.pool._TRASH)

    # ---------------------------------------------------------------- M (SM)
    @s.case("sm_push")
    def _(t):
        G["chain"] << 1
        SM.push(37, SH3, center=(800, 800), rtype="Chain", lm=1)

    @s.case("sm_tick")
    def _(t):
        SM.tick()
        t.out("live", SM.live)

    # ---------------------------------------------------------------- rtype·명령·중심 (SR)
    @s.case("sr_probe")
    def _(t):
        for k, v in G.items():
            t.watch(k, v.getValueAddr())
        t.watch("anchor_x", SR.anchor.x.getValueAddr())

    @s.case("sr_push")
    def _(t):
        # rtype 번호(변수) × 명령 종류(ok: 0 없음 1 어택 로케이션 2 순찰 좌표 3 이동 변수 좌표) × 중심 (1100, 1300)
        rt = t.var("rt")
        ok = t.var("ok")
        ox, oy = t.var("ox"), t.var("oy")
        n = t.var("n", 3)
        for kind, order in ((0, None), (1, Order.attack("Location 13")), (2, Order.patrol(700, 800)),
                            (3, Order.move(ox, oy))):
            if EUDIf()(ok.Exactly(kind)):
                SR.push(t.var("unit", 37), SH3, owner=P2, center=(1100, 1300), rtype=rt,
                        order=order, lm=n)
            EUDEndIf()

    @s.case("sr_push_const")
    def _(t):
        # 상수 rtype 이름 (핸들러 없는 이름 → 후처리 없음, 명령 속성 있으면 후처리)
        k = t.var("k")
        if EUDIf()(k.Exactly(1)):
            SR.push(37, SH3, owner=P2, center=(1100, 1300), rtype="Nothing")
        EUDEndIf()
        if EUDIf()(k.Exactly(2)):
            SR.push(37, SH3, owner=P2, center=(1100, 1300), rtype="Nothing", order=Order.attack(900, 950))
        EUDEndIf()
        if EUDIf()(k.Exactly(3)):
            SR.push(37, SH3, owner=P2, center=(1100, 1300), rtype="Home", order=Order.patrol(HOME))
        EUDEndIf()
        if EUDIf()(k.Exactly(4)):
            SR.push(37, SH3, owner=P2, center=(1100, 1300))  # rtype 생략 = default_rtype(없음)
        EUDEndIf()

    @s.case("sr_center")
    def _(t):
        mode = t.var("mode")
        vx, vy, vloc, vepd = t.var("vx"), t.var("vy"), t.var("vloc"), t.var("vepd")
        cases = [
            (1, None),
            (2, (1234, 2345)),
            (3, (vx, vy)),
            (4, "Location 13"),
            (5, 25),
            (6, vloc),
            (7, at_unit(vepd)),
        ]
        for k, c in cases:
            if EUDIf()(mode.Exactly(k)):
                SR.push(1, SH3, owner=P8, center=c, rtype=0)
            EUDEndIf()
        if EUDIf()(mode.Exactly(8)):
            # 명령 목표 = 로케이션 25(넣는 순간 중심), 중심 = 좌표
            SR.push(1, SH1, owner=P8, center=(600, 700), order=Order.attack(25))
        EUDEndIf()
        if EUDIf()(mode.Exactly(9)):
            SR.push(1, SH1, owner=P8, center=(600, 700), order=Order.move(at_unit(vepd)))
        EUDEndIf()
        if EUDIf()(mode.Exactly(10)):
            SR.push(1, SH1, owner=P8, center=(600, 700), order=Order.patrol(vloc))
        EUDEndIf()

    @s.case("sr_anchor")
    def _(t):
        SR.anchor.x = t.var("ax")
        SR.anchor.y << t.var("ay")

    @s.case("sr_move_loc")
    def _(t):
        # 로케이션 25 를 다른 자리로 (넣은 뒤에 옮겨도 작업 중심·명령 목표는 그대로여야 한다)
        DoActions([SetMemory(0x58DC60 + 20 * 24 + 4 * k, SetTo, v) for k, v in enumerate((100, 100, 300, 300))])

    @s.case("sr_tick")
    def _(t):
        f_setcurpl(t.var("cp0", 3))
        SR.tick()
        _cp_raw(t, "cpraw")
        t.out("cpc", f_getcurpl())
        t.out("live", SR.live)

    @s.case("sr_now")
    def _(t):
        mode = t.var("mode")
        f_setcurpl(t.var("cp0", 5))
        if EUDIf()(mode.Exactly(1)):
            SR.spawn_now(40, count=3, owner=P2, at=(900, 910), rtype="Home")
        EUDEndIf()
        if EUDIf()(mode.Exactly(2)):
            SR.spawn_now(t.var("u", 41), count=t.var("cnt"), owner=t.var("own"), at="Location 13", rtype=t.var("rt"))
        EUDEndIf()
        if EUDIf()(mode.Exactly(3)):
            SR.spawn_now(42, count=2, owner=P2, at=t.var("loc"), order=Order.attack(333, 444), rtype="Nothing")
        EUDEndIf()
        if EUDIf()(mode.Exactly(4)):
            SR.spawn_now(43, owner=P2, at=(9000, 9000))  # 경계 검사 없음
        EUDEndIf()
        if EUDIf()(mode.Exactly(5)):
            SR.spawn_now(44, owner=P2)  # at 생략 = anchor
        EUDEndIf()
        _cp_raw(t, "cpraw")
        t.out("cpc", f_getcurpl())

    # ---------------------------------------------------------------- 이펙트 (SE)
    @s.case("se_push")
    def _(t):
        k = t.var("k")
        if EUDIf()(k.Exactly(1)):
            SE.scan_effect(SH3, 429, color=16, owner=P8, center=(1500, 1400))
        EUDEndIf()
        if EUDIf()(k.Exactly(2)):
            SE.push(33, SH1, effect=Effect.scan(t.var("img"), color=t.var("col")), owner=P2, center=(1600, 1400))
        EUDEndIf()
        if EUDIf()(k.Exactly(3)):
            SE.scan_effect([SH1, SH3], 214, owner=P2, center=(1700, 1400))  # 색 없음, 두 층
        EUDEndIf()
        if EUDIf()(k.Exactly(4)):
            SE.spawn_now(33, count=2, owner=P2, at=(1800, 1400), effect=Effect.scan(391, color=10))
        EUDEndIf()

    @s.case("se_tick")
    def _(t):
        SE.tick()
        t.out("live", SE.live)

    # ---------------------------------------------------------------- on_create (SO·SO3) / props None (SO2)
    @s.case("so_setup")
    def _(t):
        i = t.var("i")
        DATA.hp2[i] = 1234
        DATA.tag[i] = 55

    @s.case("so_push")
    def _(t):
        SO.push(37, SH1, center=(500, 500), owner=P8)
        SO3.push(38, SH1, center=(510, 500), owner=P8)
        SO2.push(39, SH3, center=(520, 500), owner=P8, rtype="Home2")

    @s.case("so_tick")
    def _(t):
        SO.tick()
        SO3.tick()
        SO2.tick()
        i = t.var("i")
        t.out("hp2", DATA.hp2[i])
        t.out("tag", DATA.tag[i])

    @s.case("sg_run")
    def _(t):
        SG.rotation = 0
        SG.push(1, SH4, center=(1000, 1000), rotate=SG.GLOBAL, rtype="Turn", owner=P8)
        SG.tick()
        t.out("rot", SG.rotation)

    # ---------------------------------------------------------------- 변수 인자·varray (SV)
    @s.case("sv_push")
    def _(t):
        SV.push(t.var("unit"), t.var("sid"), owner=t.var("own"), center=(t.var("cx"), t.var("cy")), lm=t.var("lm"),
                delay=t.var("d"), size=t.var("size", 100), rotate=t.var("rot"), offset=(t.var("dx"), t.var("dy")))

    @s.case("sv_tick")
    def _(t):
        SV.tick()
        t.out("live", SV.live)

    # ---------------------------------------------------------------- 빌드 오류
    def err(name, fn, msg=None):
        s.case("err_" + name, expect_build_error=EudextError, expect_message=msg)(lambda t: fn())

    err("empty_const", lambda: SA.push(1, EMPTY), "점이 없습니다")
    err("unit_range", lambda: SA.push(227, SH1), "unit")
    err("unit_name", lambda: SA.push("No Such Unit", SH1), "유닛 이름")
    err("lm_range", lambda: SA.push(1, SH1, lm=256), "lm")
    err("lm_word", lambda: SA.push(1, SH1, lm="fast"), "lm")
    err("rtype_name", lambda: SR.push(1, SH1, rtype="KiilUnit"), "등록되지 않은 rtype 이름")
    err("rtype_id", lambda: SR.push(1, SH1, rtype=250), "등록되지 않은 rtype 번호")
    err("rot3d", lambda: SA.push(1, SH1, rot3d=True), "2단계")
    err("variant", lambda: SA.push(1, SH1, variant="sweep"), "2단계")
    err("mirror", lambda: SA.push(1, SH1, mirror=True), "2단계")
    err("frag", lambda: SA.push(116, SH1, effect=Effect.frag([(37, 1)])), "2단계")
    err("rot3d_attr", lambda: SA.rot3d, "2단계")
    err("effect_unit", lambda: SE.push(37, SH1, effect=Effect.scan(429)), "33")
    err("center_3", lambda: SA.push(1, SH1, center=(1, 2, 3)), "두 값")
    err("center_loc0", lambda: SA.push(1, SH1, center=0), "0부터")
    err("center_loc300", lambda: SA.push(1, SH1, center=300), "1 ~ 255")
    err("center_float", lambda: SA.push(1, SH1, center=(1.5, 2)), "실수")
    err("owner_cp", lambda: SA.push(1, SH1, owner=CurrentPlayer), "CurrentPlayer")
    err("owner_str", lambda: SA.push(1, SH1, owner="Player 8"), "owner")
    err("owner_range", lambda: SA.push(1, SH1, owner=12), "owner")
    err("shape_list", lambda: SA.push(1, [SH1, SH3]), "목록")
    err("job_kw", lambda: SA.job(colour=1), "모르는 인자")
    err("layer_kw", lambda: SA.job().layer(1, SH1, center=(1, 2)), "모르는 인자")
    err("no_layers", lambda: SA.job().push(), "층이 없습니다")
    err("too_many_layers", lambda: SJ.push_layers([(1, SH1)] * 5), "capacity")
    err("multi_mismatch", lambda: SA.push_multi([37, 38, 39], [SH1, SH3]), "수가 다릅니다")
    err("order_bad", lambda: SA.push(1, SH1, order=(Attack, 1, 2)), "order")
    err("effect_bad", lambda: SA.push(33, SH1, effect=429), "effect")
    err("offset_bad", lambda: SA.push(1, SH1, offset=5), "offset")
    err("sid_range", lambda: SA.push(1, 999), "범위")
    err("reentry_tick", lambda: SX1.tick(), "재진입")
    err("reentry_now", lambda: SX2.tick(), "재진입")
    err("reentry_clear", lambda: SX3.tick(), "재진입")
    err("no_default_target", lambda: SX4.tick(), "default_target")
    err("late_feature", _late_feature, "주 함수를 다 만든 뒤")
    err("f_f_name", lambda: spawn.f_f_attack, "spawn.attack")


def _late_feature():
    SX5._xdefined = True
    try:
        SX5.push(1, SH1, size=50)
    finally:
        SX5._xdefined = False


# =============================================================================================
# 실행·비교
# =============================================================================================


class Env:
    def __init__(self, s):
        self.s = s
        self.m = s.machine
        self.um = scmodel.unit_model(self.m)
        self.lm = locmodel.loc_model(self.m)
        self.tm = scmodel.text_model(self.m)
        self.seen = 0
        self.oseen = 0
        self.eff_log = []

    def fresh(self):
        self.s.reset()
        self.um.clear_log()
        self.um.clear_failures()
        self.lm.clear()
        self.tm.clear()
        self.seen = 0
        self.oseen = 0
        del self.eff_log[:]

    def new_plots(self):
        out = self.lm.plots[self.seen:]
        self.seen = len(self.lm.plots)
        return out

    def new_orders(self):
        out = self.lm.orders[self.oseen:]
        self.oseen = len(self.lm.orders)
        return out

    def probe(self, name):
        return self.m.var("sr_probe." + name)


def got_key(p):
    return (p.x & M32, p.y & M32, p.unit, p.player)


def want_key(w):
    return (w.X, w.Y, w.unit, w.owner)


def cmp_frame(s, env, case, ref, label, live_key="live", on_spawn=None):
    r = s.run(case)
    got = [got_key(p) for p in env.new_plots()]
    want = [want_key(w) for w in ref.tick(on_spawn=on_spawn)]
    s.expect_true(case, r.error is None and got == want, label,
                  "기록 %d %r\n기대 %d %r (오류 %r)" % (len(got), got[:4], len(want), want[:4], r.error))
    if live_key:
        s.expect_true(case, r.values.get(live_key) == ref.live, label + " live",
                      "%r (기대 %d)" % (r.values.get(live_key), ref.live))
    return r


def ref_layers(name, owner=7):
    out = []
    for unit, sh, lm, d in table_layers(name):
        out.append(RS.Layer(unit, sh.points, owner=owner, lm=lm, delay=d, schedule=sh.schedule))
    return out


def run_table(s, env):
    """S1 9.1 A~I (+C'): 참조 모델(= 명세 표)과 프레임마다 좌표·유닛·주인·live 비교."""
    for idx, name in enumerate(TABLE):
        env.fresh()
        ref = RS.RefSpawner(8)
        s.run("sa_push", {"sc": idx + 1})
        ref.push(ref_layers(name), center=(1000 + 10 * idx, 1000))
        _layers, want, end = RS.TABLE_91[name]
        for f in range(len(want) + 2):
            r = cmp_frame(s, env, "sa_tick", ref, "9.1 %s f%d" % (name, f))
            if f == end:
                s.expect_true("sa_tick", r.values["live"] == 0, "9.1 %s 반납 프레임 f%d" % (name, f), repr(r.values))
            elif f < end:
                s.expect_true("sa_tick", r.values["live"] >= 1, "9.1 %s 진행 중 f%d" % (name, f), repr(r.values))
    # 표 그대로(점 수 목록) — 좌표 비교와 별개로 한 번 더
    for idx, name in enumerate(TABLE):
        env.fresh()
        s.run("sa_push", {"sc": idx + 1})
        _layers, want, _end = RS.TABLE_91[name]
        got = []
        for _ in range(len(want)):
            s.run("sa_tick")
            got.append(len(env.new_plots()))
        s.expect_true("sa_tick", got == want, "9.1 %s 표 %r" % (name, want), repr(got))


def run_n_o_p(s, env):
    # N: 같은 프레임에 두 작업 (C 와 E) — 서로 다른 레코드, 서로 영향 없음
    env.fresh()
    ref = RS.RefSpawner(8)
    for name in ("C", "E"):
        idx = TABLE.index(name)
        s.run("sa_push", {"sc": idx + 1})
        ref.push(ref_layers(name), center=(1000 + 10 * idx, 1000))
    for f in range(8):
        cmp_frame(s, env, "sa_tick", ref, "9.1 N f%d" % f)
    # N': E 두 개 + C 섞기 (층 사이 빈 프레임이 다른 작업과 섞여도 1개)
    env.fresh()
    ref = RS.RefSpawner(8)
    for name in ("E", "C", "E", "I"):
        idx = TABLE.index(name)
        s.run("sa_push", {"sc": idx + 1})
        ref.push(ref_layers(name), center=(1000 + 10 * idx, 1000))
    for f in range(8):
        cmp_frame(s, env, "sa_tick", ref, "9.1 N' f%d" % f)
    # O: clear — 사슬 뒤 층도
    env.fresh()
    ref = RS.RefSpawner(8)
    for name in ("E", "D"):
        idx = TABLE.index(name)
        s.run("sa_push", {"sc": idx + 1})
        ref.push(ref_layers(name), center=(1000 + 10 * idx, 1000))
    cmp_frame(s, env, "sa_tick", ref, "9.1 O f0")
    r = s.run("sa_clear")
    ref.clear()
    s.expect_true("sa_clear", r.values["live"] == 0, "9.1 O clear 뒤 live 0", repr(r.values))
    for f in range(1, 5):
        cmp_frame(s, env, "sa_tick", ref, "9.1 O f%d" % f)
    # clear 뒤 다시 넣기 (빈 칸이 모두 돌아왔나)
    for _ in range(8):
        s.run("sa_push", {"sc": TABLE.index("A") + 1})
        ref.push(ref_layers("A"), center=(1000 + 10 * TABLE.index("A"), 1000))
    r = cmp_frame(s, env, "sa_tick", ref, "9.1 O clear 뒤 8개")
    s.expect_true("sa_tick", r.values["ovf"] == 0 and ref.overflow == 0, "9.1 O 넘침 없음", repr(r.values))
    # P: 변수 sid → 점 0개 도형 / 범위 밖 sid → 바로 끝 + debug 문구, lm 변수 0 = 자동
    for sid, lmv in ((SA_EMPTY_SID, 0), (999, 5), (SA.shapes.sid_of(SH41), 0), (SA.shapes.sid_of(SH300), 7)):
        env.fresh()
        s.run("sa_push_var", {"sid": sid, "lm": lmv})
        ref = RS.RefSpawner(8)
        n = len(SA.shapes[sid]) if sid < len(SA.shapes) else 0
        pts = SA.shapes[sid].points if n else []
        if n:
            ref.push([RS.Layer(1, pts, owner=7, lm=lmv)], center=(500, 500))
        for f in range(3):
            cmp_frame(s, env, "sa_tick", ref, "9.1 P sid=%d lm=%d f%d" % (sid, lmv, f))
        texts = [x for x in env.tm.texts() if x and "점이 없는 도형" in x]
        s.expect_true("sa_push_var", (len(texts) >= 1 and len(set(texts)) == 1) == (n == 0),
                      "9.1 P debug 문구 sid=%d" % sid, repr(texts))
        s.expect_true("sa_push_var", len(texts) in (0, N_EVERYONE), "9.1 P 문구는 사람·관전자마다 한 번", repr(len(texts)))


def run_jkl(s, env):
    # J: capacity 4 에 1층 작업 5개 → 5번째 버림, overflow 1, 나머지 영향 없음
    env.fresh()
    ref = RS.RefSpawner(4)
    for k in range(5):
        r = s.run("sj_push", {"n": 1, "cx": 1000 + 50 * k})
        ref.push([RS.Layer(37, SH41.points, owner=7, lm=10)], center=(1000 + 50 * k, 1200))
    s.expect_true("sj_push", (r.values["live"], r.values["ovf"]) == (4, 1) == (ref.live, ref.overflow), "9.1 J",
                  repr(r.values))
    texts = [x for x in env.tm.texts() if x and "가득 차" in x]
    wavs = env.tm.wavs()
    s.expect_true("sj_push", len(texts) == N_EVERYONE and len(wavs) == 2 * N_EVERYONE and len(set(texts)) == 1,
                  "9.1 J 넘침 문구 한 번·Buzz ×2 (on_full=report, 대상마다)", "%r %r" % (texts, wavs))
    for f in range(6):
        cmp_frame(s, env, "sj_tick", ref, "9.1 J f%d" % f)
    # K: 3층 + 2층 → 두 번째는 통째로 버림
    env.fresh()
    ref = RS.RefSpawner(4)
    s.run("sj_push", {"n": 3})
    r = s.run("sj_push", {"n": 2})
    ref.push([RS.Layer(37, SH41.points, lm=10), RS.Layer(38, SH41B.points, lm=10), RS.Layer(39, SH3.points)],
             center=(1500, 1500))
    ref.push([RS.Layer(40, SH3.points), RS.Layer(41, SH3.points)], center=(1700, 1700))
    s.expect_true("sj_push", (r.values["live"], r.values["ovf"]) == (3, 1) == (ref.live, ref.overflow), "9.1 K",
                  repr(r.values))
    for f in range(14):
        cmp_frame(s, env, "sj_tick", ref, "9.1 K f%d" % f)
    # L: 마지막 칸이 찬 상태에서 넣기 → 레코드 표·그 뒤를 쓰지 않는다 (메모리 비교)
    env.fresh()
    for k in range(4):
        s.run("sj_push", {"n": 1, "cx": 900 + k})
    m = env.m
    before = dict(m.mem)
    r = s.run("sj_push", {"n": 1, "cx": 1999})
    after = m.mem
    S = m.addrs["sj_tick.S"]
    E = SJ.pool._E
    lo, hi = S, S + 72 * E * SJ.capacity + 72 * 2 * SJ.capacity + 2400
    trash = m.addrs["sj_tick.TRASH"]
    changed = {a for a in set(before) | set(after) if before.get(a, 0) != after.get(a, 0)}
    bad = sorted(a for a in changed if lo <= a < hi)
    s.expect_true("sj_push", r.values["ovf"] == 1 and not bad, "9.1 L 레코드 표·표 뒤 무변경",
                  "넘침 %r, 바뀐 곳 %s" % (r.values["ovf"], [hex(a) for a in bad[:8]]))
    in_trash = [a for a in changed if trash <= a < trash + 4 * (18 * E + 100)]
    s.expect_true("sj_push", not in_trash and len(changed) <= 40, "9.1 L 넘친 넣기는 필드를 쓰지 않는다(alloc_n 분기)",
                  "쓰레기 %d, 바뀐 곳 %d" % (len(in_trash), len(changed)))
    ref = RS.RefSpawner(4)
    for k in range(4):
        ref.push([RS.Layer(37, SH41.points, lm=10)], center=(900 + k, 1200))
    for f in range(6):
        cmp_frame(s, env, "sj_tick", ref, "9.1 L f%d" % f)


def run_m(s, env):
    """M: tick 중 핸들러가 push → 새 작업은 다음 tick 부터."""
    env.fresh()
    ref = RS.RefSpawner(8)
    chained = {"done": False}

    def on_spawn(rsp, sp_):
        if sp_.job == 0 and not chained["done"]:
            chained["done"] = True
            rsp.push([RS.Layer(40, SH1.points)], center=(sp_.X, sp_.Y))

    s.run("sm_push")
    ref.push([RS.Layer(37, SH3.points, lm=1)], center=(800, 800))
    frames = []
    for f in range(6):
        cmp_frame(s, env, "sm_tick", ref, "9.1 M f%d" % f, on_spawn=on_spawn)
        frames.append([p.unit for p in env.lm.plots if p.cycle == env.lm.plots[-1].cycle] if env.lm.plots else [])
    first40 = [p.cycle for p in env.lm.plots if p.unit == 40]
    first37 = [p.cycle for p in env.lm.plots if p.unit == 37]
    s.expect_true("sm_tick", len(first40) == 1 and first40[0] == first37[0] + 1, "9.1 M 새 작업은 다음 tick",
                  "%r %r" % (first37, first40))


# --- rtype·명령 ---


def spawned(env, unit=None):
    return [p for p in env.lm.plots if p.ok and (unit is None or p.unit == unit)]


def run_rtypes(s, env):
    um = env.um
    base_pts = [(1100 + x, 1300 + y) for x, y in SH3.points]
    # (rtype id, 기대 검사 함수)
    for rt in (0, 1, 3, 5, 6, 7, 8, 50, 51, 106, 147, 148, 180, 187, 201, 222):
        for ok in (0, 1, 2, 3):
            env.fresh()
            s.run("sr_push", {"rt": rt, "ok": ok, "ox": 1600, "oy": 1700, "unit": 37})
            r = s.run("sr_tick")
            plots = env.new_plots()
            orders = env.new_orders()
            label = "rtype %d order %d" % (rt, ok)
            s.expect_true("sr_tick", [(p.x, p.y) for p in plots] == base_pts and all(p.ok for p in plots)
                          and r.values["live"] == 0, label + " 소환", repr([(p.x, p.y, p.ok) for p in plots]))
            s.expect_true("sr_tick", all(p.player == 1 and p.unit == 37 for p in plots)
                          and all(p.action == "CreateUnitWithProperties" for p in plots), label + " 주인·유닛·props",
                          repr(plots[:1]))
            idx = [p.indices[0] for p in plots]
            # 명령 기대 (순서대로)
            want = []
            has_order = ok != 0
            for k, (x, y) in enumerate(base_pts):
                box = (x - 1, y - 1, x + 1, y + 1)
                if rt in (1, 8, 7) and not has_order:
                    if rt == 1:
                        want.append((box, 2, HOME, None))
                    elif rt == 8:
                        want.append((box, 1, HOME, None))
                    else:
                        want.append((box, 2, LOC2, (1099, 1299, 1101, 1301)))
                if rt == 106:
                    want.append((box, 2, LOC2, (1099, 1299, 1101, 1301)))
                if rt == 147:
                    tx, ty = ((1100, 1300) if not has_order else
                              {1: (2048, 2048), 2: (700, 800), 3: (1600, 1700)}[ok])
                    want.append((box, 2, LOC2, (tx - 1, ty - 1, tx + 1, ty + 1)))
                if rt == 50:
                    want.append((box, 0, LOC2, (499, 599, 501, 601)))
                if has_order:
                    tx, ty = {1: (2048, 2048), 2: (700, 800), 3: (1600, 1700)}[ok]
                    want.append((box, {1: 2, 2: 1, 3: 0}[ok], LOC2, (tx - 1, ty - 1, tx + 1, ty + 1)))
            got = [(o.rect, o.order, o.dest, o.dest_rect if o.dest == LOC2 else None) for o in orders]
            s.expect_true("sr_tick", got == want, label + " 명령", "기록 %r\n기대 %r" % (got, want))
            s.expect_true("sr_tick", all(o.unit == 37 and o.player == 1 for o in orders), label + " 명령 유닛·주인",
                          repr(orders[:1]))
            # 명령받은 유닛: 상자 안의 같은 종류·주인 유닛 전부 (방금 만든 유닛 포함). KillUnit(3) 은 먼저 죽었다
            s.expect_true("sr_tick", rt == 3 or all(set(o.targets) >= {i for i in idx if um.pos(i) == ((o.rect[0] + o.rect[2]) // 2,
                                                                                         (o.rect[1] + o.rect[3]) // 2)}
                                         for o in orders), label + " 명령 대상", repr([o.targets for o in orders]))
            # CUnit 칸
            for i in idx:
                tr = um.get(i, spawn.CU_TURN_RADIUS, 1)
                spd = um.get(i, spawn.CU_TOP_SPEED, 4)
                acc = um.get(i, spawn.CU_ACCEL, 2)
                rtm = um.get(i, spawn.CU_REMOVE_TIMER, 2)
                par = um.get(i, spawn.CU_PARASITE, 1)
                oid = um.get(i, spawn.CU_ORDER_ID, 1)
                inv = um.get(i, spawn.CU_STATUS, 4) & spawn.STATUS_INVINCIBLE
                exp = {
                    "tr": 127 if (rt in (1, 7, 8, 106, 201, 147, 148)) else 0,
                    "spd": {106: 128, 201: 1}.get(rt, 0),
                    "acc": {106: 128, 201: 1}.get(rt, 0),
                    "rtm": {5: 77, 8: 15}.get(rt, 0),
                    "par": 0xFF if rt in (180, 147, 148) else 0,
                    "oid": 187 if rt == 187 else (0 if rt == 3 else scmodel.ORDER_ON_CREATE),
                    "inv": spawn.STATUS_INVINCIBLE if rt == 50 else 0,
                }
                if rt in (147, 148):
                    tx, ty = ((1100, 1300) if not has_order else
                              {1: (2048, 2048), 2: (700, 800), 3: (1600, 1700)}[ok])
                    ux, uy = um.pos(i)
                    d2 = u32((ux - tx) * (ux - tx) + (uy - ty) * (uy - ty)) >> 2
                    sp_ = RM.isqrt(d2)
                    exp["spd"], exp["acc"] = sp_, sp_ & 0xFFFF
                gotc = {"tr": tr, "spd": spd, "acc": acc, "rtm": rtm, "par": par, "oid": oid, "inv": inv}
                s.expect_true("sr_tick", gotc == exp, label + " CUnit 칸", "%r (기대 %r)" % (gotc, exp))
            # KillUnit
            kills = [(k.action, k.unit, k.player) for k in um.killed]
            s.expect_true("sr_tick", kills == ([("KillUnit", 37, 1)] * 3 if rt == 3 else []), label + " KillUnit",
                          repr(kills))
            # 사용자 핸들러 값
            if rt == 50:
                last = idx[-1]
                vals = {k: env.probe(k) for k in ("hx", "hy", "hpx", "hpy", "hcx", "hcy", "hepd", "hunit", "howner",
                                                  "hcount")}
                x, y = base_pts[-1]
                s.expect_true("sr_probe", vals == {"hx": x, "hy": y, "hpx": x, "hpy": y, "hcx": 1100, "hcy": 1300,
                                                   "hepd": um.epd(last), "hunit": 37, "howner": 1, "hcount": 3},
                              label + " 파이썬 핸들러 값", repr(vals))
            if rt == 51:
                last = idx[-1]
                vals = {k: env.probe(k) for k in ("ef_epd", "ef_unit", "ef_owner", "ef_x", "ef_y", "ef_n")}
                x, y = base_pts[-1]
                s.expect_true("sr_probe", vals == {"ef_epd": um.epd(last), "ef_unit": 37, "ef_owner": 1, "ef_x": x,
                                                   "ef_y": y, "ef_n": 303}, label + " EUDFunc 핸들러 값", repr(vals))
            # 등록 안 한 rtype (222) → 아무것도 안 함 + debug 문구
            texts = [x for x in env.tm.texts() if x and "등록되지 않은 rtype" in x]
            s.expect_true("sr_tick", len(texts) == (3 * N_EVERYONE if rt == 222 else 0), label + " 등록 안 한 rtype 문구",
                          repr(texts))
    # 상수 rtype: 핸들러 없는 이름은 후처리 없음(캡처 없음), 명령 속성이 있으면 명령
    for k, (n_orders, kinds) in {1: (0, []), 2: (3, [2]), 3: (3, [1]), 4: (0, [])}.items():
        env.fresh()
        s.run("sr_push_const", {"k": k})
        s.run("sr_tick")
        orders = env.new_orders()
        s.expect_true("sr_tick", len(orders) == n_orders and {o.order for o in orders} == set(kinds),
                      "상수 rtype k=%d 명령" % k, repr(orders[:2]))
        if k == 3:
            s.expect_true("sr_tick", all(o.dest_rect == (2047, 2047, 2049, 2049) for o in orders),
                          "Home + 명령 속성 → default_order 없음, 명령만 (로케이션 13 중심)", repr(orders[:1]))
    # 생성 실패 → 핸들러·명령 없음
    env.fresh()
    env.um.fail_next(2)
    s.run("sr_push", {"rt": 50, "ok": 1, "unit": 37})
    s.run("sr_tick")
    plots = env.new_plots()
    orders = env.new_orders()
    s.expect_true("sr_tick", [p.ok for p in plots] == [False, False, True] and len(orders) == 2
                  and env.probe("hcount") == 1, "생성 실패 → 핸들러·명령 없음",
                  "%r %d %d" % ([p.ok for p in plots], len(orders), env.probe("hcount")))
    # 빈 칸 없음 → 핸들러·명령 없음
    env.fresh()
    env.um.fill()
    s.run("sr_push", {"rt": 1, "ok": 2, "unit": 37})
    s.run("sr_tick")
    s.expect_true("sr_tick", len(env.new_orders()) == 0 and all(not p.ok for p in env.new_plots()),
                  "빈 칸 없음 → 명령 없음")
    # CP 보존
    for cp0 in (0, 3, 7, 11):
        env.fresh()
        s.run("sr_push", {"rt": 147, "ok": 3, "ox": 5, "oy": 6, "unit": 37})
        r = s.run("sr_tick", {"cp0": cp0})
        s.expect_true("sr_tick", (r.values["cpraw"], r.values["cpc"]) == (cp0, cp0), "tick CP 보존 %d" % cp0,
                      repr(r.values))


def run_centers(s, env):
    um = env.um
    lmod = env.lm
    for mode in range(1, 8):
        env.fresh()
        lmod.set_location(25, 3000, 3100, 3010, 3120)
        i = um.spawn(1, 0, 777, 888)
        s.run("sr_anchor", {"ax": 1500, "ay": 1600})
        s.run("sr_center", {"mode": mode, "vx": 2100, "vy": 2200, "vloc": 25, "vepd": um.epd(i)})
        s.expect_true("sr_probe", env.probe("anchor_x") == 1500, "중심 모드 %d: anchor 를 덮어쓰지 않음" % mode,
                      repr(env.probe("anchor_x")))
        s.run("sr_anchor", {"ax": 1, "ay": 2})  # 넣은 뒤 anchor 를 바꿔도 작업 중심은 그대로
        s.run("sr_move_loc")  # 로케이션 25 를 옮겨도 그대로
        s.run("sr_tick")
        c = {1: (1500, 1600), 2: (1234, 2345), 3: (2100, 2200), 4: (2048, 2048), 5: (3005, 3110), 6: (3005, 3110),
             7: (777, 888)}[mode]
        got = [(p.x, p.y) for p in env.new_plots()]
        want = [(c[0] + x, c[1] + y) for x, y in SH3.points]
        s.expect_true("sr_tick", got == want, "중심 모드 %d" % mode, "%r (기대 %r)" % (got, want))
    for mode, dest in ((8, (3005, 3110)), (9, (777, 888)), (10, (3005, 3110))):
        env.fresh()
        lmod.set_location(25, 3000, 3100, 3010, 3120)
        i = um.spawn(2, 0, 777, 888)
        s.run("sr_center", {"mode": mode, "vloc": 25, "vepd": um.epd(i)})
        s.run("sr_move_loc")
        s.run("sr_tick")
        orders = env.new_orders()
        kind = {8: 2, 9: 0, 10: 1}[mode]
        s.expect_true("sr_tick", [(o.order, o.dest_xy) for o in orders] == [(kind, dest)],
                      "명령 목표 모드 %d (넣는 순간 해석)" % mode, repr(orders))


def run_now(s, env):
    um = env.um
    # 1: 상수, 3기 한 자리, Home(기본 어택) — 명령 상자에 앞서 만든 같은 종류도 들어간다(TOrder 의미)
    for cp0 in (0, 6):
        env.fresh()
        r = s.run("sr_now", {"mode": 1, "cp0": cp0})
        plots = env.new_plots()
        orders = env.new_orders()
        s.expect_true("sr_now", [(p.x, p.y, p.unit, p.player) for p in plots] == [(900, 910, 40, 1)] * 3,
                      "spawn_now 상수 3기", repr(plots))
        s.expect_true("sr_now", [len(o.targets) for o in orders] == [1, 2, 3] and all(o.dest == HOME for o in orders),
                      "spawn_now 명령 대상(겹친 같은 종류 포함)", repr([o.targets for o in orders]))
        s.expect_true("sr_now", (r.values["cpraw"], r.values["cpc"]) == (cp0, cp0), "spawn_now CP 보존", repr(r.values))
        s.expect_true("sr_now", all(um.get(p.indices[0], spawn.CU_TURN_RADIUS, 1) == 127 for p in plots),
                      "spawn_now 회전반경")
    # 2: 변수 유닛·수·주인·rtype, 로케이션 이름 중심 (한 칸 앞 로케이션이 아님 — S1 10-18)
    for cnt, own, rt in ((0, 3, 6), (1, 4, 180), (4, 0, 1), (2, 2, 222)):
        env.fresh()
        s.run("sr_now", {"mode": 2, "u": 41, "cnt": cnt, "own": own, "rt": rt})
        plots = env.new_plots()
        s.expect_true("sr_now", [(p.x, p.y, p.unit, p.player) for p in plots] == [(2048, 2048, 41, own)] * cnt,
                      "spawn_now 변수 cnt=%d" % cnt, repr(plots))
        if rt == 180:
            s.expect_true("sr_now", all(um.get(p.indices[0], spawn.CU_PARASITE, 1) == 0xFF for p in plots),
                          "spawn_now 변수 rtype(Vision)")
        texts = [x for x in env.tm.texts() if x and "등록되지 않은 rtype" in x]
        s.expect_true("sr_now", len(texts) == (cnt * N_EVERYONE if rt == 222 else 0), "spawn_now 등록 안 한 rtype 문구",
                      repr(texts))
    # 3: 로케이션 번호 변수 중심 + 명령 속성(좌표)
    env.fresh()
    env.lm.set_location(20, 3400, 2700, 3420, 2760)
    s.run("sr_now", {"mode": 3, "loc": 20})
    plots = env.new_plots()
    orders = env.new_orders()
    s.expect_true("sr_now", [(p.x, p.y) for p in plots] == [(3410, 2730)] * 2
                  and [(o.order, o.dest_xy, o.rect) for o in orders] == [(2, (333, 444), (3409, 2729, 3411, 2731))] * 2,
                  "spawn_now 로케이션 변수·명령", "%r %r" % (plots, orders))
    # 4: 경계 검사 없음 / 5: anchor
    env.fresh()
    s.run("sr_now", {"mode": 4})
    s.run("sr_anchor", {"ax": 1111, "ay": 2222})
    s.run("sr_now", {"mode": 5})
    got = [(p.x, p.y, p.unit) for p in env.new_plots()]
    s.expect_true("sr_now", got == [(9000, 9000, 43), (1111, 2222, 44)], "spawn_now 경계 검사 없음·anchor", repr(got))


def _cp_raw(t, name):
    """지금 CP 원시 값(0~11)을 칸에 — CP 로 읽는 함수(f_dwread_epd)는 CP 를 옮기므로 조건으로 잰다."""
    v = t.var(name)
    DoActions(v.SetNumber(M32))
    for p in range(12):
        RawTrigger(conditions=Memory(0x6509B0, Exactly, p), actions=v.SetNumber(p))


def _eff_prep(m):
    lm = locmodel.install(m)
    # 에뮬레이터 메모리에는 맵 MRGN 이 없다 → 시험이 쓰는 이름 있는 로케이션을 기준 맵 값으로 채운다
    lm.set_location(HOME, 2048, 2048, 2048, 2048)
    lm.set_location(14, 2731, 2048, 2731, 2048)
    m.setdw(SCAN_IMG, (m.dw(SCAN_IMG) & ~0xFFFF) | spawn.SCAN_SPRITE_IMAGE_DEFAULT)
    for img, v in ((429, 0x05), (214, 0x07), (391, 0x0B), (77, 0x03)):
        m.setdb(DRAW + img, v)
    orig = m.act_handlers.get(scmodel.ACT_CREATE_UNIT_PROPS)
    if getattr(orig, "_efflog", False):
        return
    log = []

    def h(mm, f, _orig=orig):
        if f[6] == 33:
            img = mm.dw(SCAN_IMG) & 0xFFFF
            log.append((img, mm.db(DRAW + img) if img < 999 else None))
        _orig(mm, f)

    h._efflog = True
    h.log = log
    m.act_handlers[scmodel.ACT_CREATE_UNIT_PROPS] = h


def run_effects(s, env):
    um = env.um
    m = env.m
    log = m.act_handlers[scmodel.ACT_CREATE_UNIT_PROPS].log
    cases = [
        (1, {}, [(429, 16)] * 3, 3, 7),
        (2, {"img": 77, "col": 200}, [(77, 200)], 1, 1),
        (3, {}, [(214, 0x07)] + [(214, 0x07)] * 3, 4, 1),
        (4, {}, [(391, 10)] * 2, 2, 1),
    ]
    for k, inp, want_log, n, owner in cases:
        env.fresh()
        del log[:]
        d = dict(inp, k=k)
        s.run("se_push", d)
        for _ in range(4):
            s.run("se_tick")
        plots = env.new_plots()
        s.expect_true("se_tick", len(plots) == n and all(p.unit == 33 and p.player == owner for p in plots),
                      "scan k=%d 생성" % k, repr(plots))
        s.expect_true("se_tick", log == want_log, "scan k=%d 생성 순간 이미지·색" % k, "%r (기대 %r)" % (log, want_log))
        kills = [(x.action, x.unit, x.player) for x in um.killed]
        s.expect_true("se_tick", kills == [("KillUnit", 33, owner)] * n, "scan k=%d KillUnit(33, 주인)" % k, repr(kills))
        restored = (m.dw(SCAN_IMG) & 0xFFFF, m.db(DRAW + 429), m.db(DRAW + 214), m.db(DRAW + 391), m.db(DRAW + 77))
        s.expect_true("se_tick", restored == (546, 5, 7, 11, 3), "scan k=%d 이미지·색 되돌림" % k, repr(restored))
        s.expect_true("se_tick", not env.new_orders() and not any(um.get(p.indices[0], spawn.CU_TURN_RADIUS, 1)
                                                                  for p in plots if p.indices),
                      "scan k=%d 후처리 없음" % k)
    # 레이어 두 개(k=3) 사이 빈 프레임
    env.fresh()
    s.run("se_push", {"k": 3})
    cyc = []
    for _ in range(4):
        s.run("se_tick")
        cyc.append(len(env.new_plots()))
    s.expect_true("se_tick", cyc == [1, 0, 3, 0], "scan 두 층 빈 프레임", repr(cyc))


def run_on_create(s, env):
    um = env.um
    for _ in range(2):
        env.fresh()
        nxt = um.next_free()
        s.run("so_setup", {"i": nxt})
        r = s.run("so_tick", {"i": nxt})
        s.expect_true("so_tick", (r.values["hp2"], r.values["tag"]) == (1234, 55), "on_create 전 값", repr(r.values))
        s.run("so_push")
        r = s.run("so_tick", {"i": nxt})
        plots = env.new_plots()
        s.expect_true("so_tick", (r.values["hp2"], r.values["tag"]) == (0, 9), "on_create UnitData 초기화(기본값)",
                      repr(r.values))
        s.expect_true("so_tick", plots[0].indices == (nxt,), "on_create 칸 = 만든 칸", repr(plots[:1]))
        s.expect_true("sr_probe", (env.probe("oc_n"), env.probe("oc_idx")) == (1, plots[1].indices[0]),
                      "on_create 함수 훅 = 만든 칸", repr((env.probe("oc_n"), env.probe("oc_idx"))))
        s.expect_true("so_tick", [p.action for p in plots[2:]] == ["CreateUnit"] * 3, "props=None → CreateUnit",
                      repr([p.action for p in plots]))
        orders = env.new_orders()
        s.expect_true("so_tick", [o.dest_xy for o in orders] == [(321, 654)] * 3, "default_order 좌표 목표",
                      repr(orders))


def run_global_per_point(s, env):
    env.fresh()
    r = s.run("sg_run")
    got = [(p.x - 1000, p.y - 1000) for p in env.new_plots()]
    s.expect_true("sg_run", got == [(0, -32), (32, 0), (0, 32), (-32, 0)] and r.values["rot"] == 360,
                  "전역 회전은 점마다 읽는다(핸들러가 바꾼 값이 다음 점에)", "%r %r" % (got, r.values))


def run_sv(s, env, rng):
    """변수 인자 전부 + varray 저장 + 변수 sid(스케줄 도형 포함) — 참조와 차등."""
    shapes = list(SV.shapes.shapes)
    for trial in range(24):
        env.fresh()
        ref = RS.RefSpawner(6)
        jobs = []
        for _ in range(rng.randint(1, 3)):
            sid = rng.randrange(len(shapes))
            sh = shapes[sid]
            job = dict(unit=rng.randrange(227), sid=sid, own=rng.randrange(12), cx=rng.randrange(0, 4000),
                       cy=rng.randrange(0, 4000), lm=rng.choice((0, 1, 3, 255, 1000)), d=rng.choice((0, 1, 2, 5)),
                       size=rng.choice((100, 100, 50, 150, 0, 255)), rot=u32(rng.choice((0, 0, 30, -45, 720, 91))),
                       dx=u32(rng.randint(-50, 50)), dy=u32(rng.randint(-50, 50)))
            s.run("sv_push", job)
            lm = job["lm"]
            ref.push([RS.Layer(job["unit"], sh.points, owner=job["own"], lm=lm, delay=job["d"], size=job["size"],
                               rot=job["rot"], schedule=sh.schedule)],
                     center=(job["cx"], job["cy"]), offset=(job["dx"], job["dy"]))
            jobs.append(job)
        for f in range(40):
            cmp_frame(s, env, "sv_tick", ref, "변수 인자·varray t%d f%d %r" % (trial, f, jobs if f == 0 else ""))
            if ref.live == 0:
                break


def python_checks(ck):
    """에뮬레이터 밖: 참조 모델 = 명세, 생성자·등록 검사, 표 복사, 파이썬 계산."""
    for name, ok, got in RS.table_91_check():
        ck.true("참조 모델 = S1 9.1 %s" % name, ok, repr(got))
    LoadMap(BASE_MAP)
    E = EudextError
    ck.raises("loc 없음", E, Spawner, loc=None, loc2=2)
    ck.raises("loc == loc2", E, Spawner, loc=3, loc2=3)
    ck.raises("loc 0", E, Spawner, loc=0, loc2=2)
    ck.raises("loc 64", E, Spawner, loc=64, loc2=2)
    ck.raises("loc Anywhere", E, Spawner, loc="Anywhere", loc2=2)
    ck.raises("loc2 실수", E, Spawner, loc=1, loc2=2.0)
    ck.raises("map_size", E, Spawner, loc=1, loc2=2, map_size=(0, 5))
    ck.raises("turn_radius", E, Spawner, loc=1, loc2=2, turn_radius=300)
    ck.raises("props", E, Spawner, loc=1, loc2=2, props="full")
    ck.raises("unclickable 2단계", E, Spawner, loc=1, loc2=2, unclickable={1: 2})
    ck.raises("on_full", E, Spawner, loc=1, loc2=2, on_full="loud")
    ck.raises("on_create", E, Spawner, loc=1, loc2=2, on_create=5)
    ck.raises("cycle", E, Spawner, loc=1, loc2=2, cycle=361)
    ck.raises("default_owner 변수", E, Spawner, loc=1, loc2=2, default_owner=EUDVariable())
    ck.raises("default_target (1,2,3)", E, Spawner, loc=1, loc2=2, default_target=(1, 2, 3))
    ck.raises("debug", E, Spawner, loc=1, loc2=2, debug=1)
    t = Spawner(capacity=2, loc=1, loc2=2, name="t")
    ck.eq("rtype 자동 번호", [t.rtype("A").id, t.rtype("B", id=5).id, t.rtype("C").id], [1, 5, 2])
    ck.raises("rtype 이름 중복", E, t.rtype, "A")
    ck.raises("rtype 번호 중복", E, t.rtype, "D", id=5)
    ck.raises("rtype 번호 0", E, t.rtype, "D", id=0)
    ck.raises("rtype 번호 256", E, t.rtype, "D", id=256)
    ck.raises("rtype 핸들러 아님", E, t.rtype, "D", handler=5)
    ck.raises("rtype 빈 이름", E, t.rtype, "")
    ck.raises("rtype_func 함수 없음", E, t.rtype_func, "E")
    ck.eq("rtype_id", (t.rtype_id("B"), t.rtype_id(5), t.rtype_id(0), t.rtype_id(t._rtypes["C"])), (5, 5, 0, 2))
    ck.raises("rtype_id 모름", E, t.rtype_id, "Z")
    ck.raises("rtype_id 번호 모름", E, t.rtype_id, 9)
    t.default_rtype = "B"
    ck.eq("default_rtype", t.default_rtype, 5)
    t.default_rtype = None
    ck.eq("default_rtype None", t.default_rtype, 0)
    ck.raises("default_rtype 모름", E, setattr, t, "default_rtype", "Q")
    u = Spawner(capacity=2, loc=1, loc2=2, name="u")
    ck.raises("다른 Spawner 의 rtype", E, u.rtype_id, t._rtypes["A"])
    t._point_sub = object()
    ck.raises("tick 뒤 rtype 등록", E, t.rtype, "Late")
    ck.raises("tick 뒤 핸들러 더하기", E, t._rtypes["A"], lambda s_: None)
    t._point_sub = None
    ck.raises("Order 종류", E, Order, "charge", 1, 2)
    ck.raises("Order 목표 3개", E, Order.attack, 1, 2, 3)
    ck.raises("Order 목표 없음", E, Order.attack)
    ck.raises("Order 로케이션 0", E, Order.attack, 0)
    ck.eq("Order 종류 번호", [Order.move(1, 2).kind, Order.patrol("A").kind, Order.attack(3).kind,
                          spawn.order(Attack, 1, 2).kind, spawn.attack([1, 2]).target], [0, 1, 2, 2, (1, 2)])
    ck.raises("Effect 이미지 0", E, Effect.scan, 0)
    ck.raises("Effect 색 256", E, Effect.scan, 5, color=256)
    ck.raises("Effect frag", E, Effect.frag)
    ck.raises("Effect 종류", E, Effect, "frag", 5)
    ck.raises("at_unit 상수", E, at_unit, 19025)
    ck.raises("at_unit 문자열", E, at_unit, "x")
    ck.true("GLOBAL repr", repr(spawn.GLOBAL) == "spawn.GLOBAL" and Spawner.GLOBAL is spawn.GLOBAL)
    ck.true("repr", "spawn.Spawner" in repr(t) and "SpawnCtx" in repr(t.ctx) and "Job" in repr(t.job()))
    ck.eq("loc 이름 → 번호", Spawner(loc="Location 0", loc2="Location 13", name="n").loc, 26)
    ck.eq("map_size (chk)", t.map_size, (4096, 4096))
    ck.eq("map_size 인자", Spawner(loc=1, loc2=2, map_size=(6144, 3072), name="ms").map_size, (6144, 3072))
    ck.raises("anchor 다른 이름", AttributeError, setattr, t.anchor, "z", 1)
    ck.raises("모듈 f_f_ 이름", E, getattr, spawn, "f_f_scan")
    ck.raises("모듈 없는 이름", AttributeError, getattr, spawn, "no_such")
    # preview (컴파일 시점 계산) = 참조 변환
    for kw in (dict(center=(100, 100)), dict(center=(4050, 1200)), dict(center=(-5, 30), size=150, rotate=30),
               dict(center=(2000, 2000), rotate=spawn.GLOBAL, rotation=77, offset=(5, -9))):
        pv = t.preview(RING, **kw)
        glob = kw.get("rotate") is spawn.GLOBAL
        want = []
        for x, y in RING.points:
            X, Y, ok = RS.transform(x, y, size=kw.get("size", 100), rot=0 if glob else kw.get("rotate", 0), glob=glob,
                                    rotation=kw.get("rotation", 0), dx=kw.get("offset", (0, 0))[0],
                                    dy=kw.get("offset", (0, 0))[1], cx=kw["center"][0], cy=kw["center"][1])
            if ok:
                want.append((X, Y))
        ck.eq("preview %r" % kw, pv, want)
        ck.eq("preview_count %r" % kw, t.preview_count(RING, **kw), len(want))
    ck.raises("preview 변수", E, t.preview, RING, center=(EUDVariable(), 1))
    # 파이썬 계산 = 참조
    rng = random.Random(9)
    bad = 0
    for _ in range(3000):
        x, y, a = rng.randint(-5000, 5000), rng.randint(-5000, 5000), rng.randint(-1000, 1000)
        if spawn.rotate_py(x, y, a) != RS.rotate_py(x, y, a):
            bad += 1
        sz = rng.randint(0, 300)
        sx, sy = RS.size_py(x, y, sz)
        want = RS.rotate_py(sx, sy, a) if u32(a) else (sx, sy)
        if spawn.transform_py(x, y, sz, a) != want:
            bad += 1
    ck.eq("rotate_py·transform_py = 참조 (3000)", bad, 0)
    # 표 복사 (S1 10-10): 받은 목록·도형을 고치지 않는다
    units_list = [37, 38]
    shapes_list = [SH1, SH3]
    pts_before = (SH1.points, SH3.points)
    job = t.job(center=(1, 2))
    job.layer(37, SH1)
    layers_before = list(job._layers)
    ck.eq("Job.layer 는 사슬", job.layer(38, SH3) is job, True)
    ck.eq("push_multi 목록 그대로", (units_list, shapes_list, (SH1.points, SH3.points)),
          ([37, 38], [SH1, SH3], pts_before))
    ck.eq("Job 층 목록 복사", len(layers_before), 1)


def emit_isolated(fn):
    with _compat.isolated_scope():
        c0 = GetTriggerCounter()
        fn()
        return GetTriggerCounter() - c0


def trigger_independence(ck):
    """3.8: tick·소환 코드의 트리거 수가 도형 수·점 수와 무관한가."""
    LoadMap(BASE_MAP)
    CompressPayload(True)
    rng = random.Random(5)
    small = ShapeSet([Shape([(1, 2)])], name="ind_small")
    big = ShapeSet([Shape([(rng.randint(-900, 900), rng.randint(-900, 900))
                           for _ in range(rng.choice((1, 37, 1700)))]) for _ in range(60)], name="ind_big")
    counts = {}
    for tag, ss in (("warm", small), ("small", small), ("big", big)):
        sp = Spawner(capacity=8, loc=LOC, loc2=LOC2, default_target=HOME, shapes=ss, name="ind_" + tag)
        sp.rtype("Home", sp.builtin.attack_default)

        def body(sp=sp, ss=ss):
            sp.push(1, 0, center=(5, 5), size=50, rotate=30, rtype="Home")
            sp.tick()
            sp._define_xsubs()

        counts[tag] = emit_isolated(body)
    print("  트리거 수 (도형 1개·1점 / 60개·%d점): %r" % (big.stored_points, counts))
    ck.eq("tick·소환·변환 트리거 수 무관", counts["small"], counts["big"])
    _compat.reset_build_state()


# =============================================================================================
# epScript 예제 · 인게임 맵
# =============================================================================================


def _load_eps(name):
    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_spawn_eps_" + name)
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name + ".eps"), os.path.join(work, name + ".eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, name + ".eps"), {})


def eps_checks(ck):
    for name, needles in (
        ("spawn_example", ("spawn.Spawner(capacity=", ".layer(", ".push()", "sp.tick()", "spawn.f_attack(",
                           "sp.rtype_func(", "sp.spawn_now(", "_ATTW(sp.anchor, 'x')", "rotate=sp.GLOBAL",
                           "sp.scan_effect(")),
        ("spawn_ingame", ("spawn.Spawner(", "sp.job(", "sp.tick()", "sp.spawn_now(", "spawn.f_attack(")),
    ):
        src = open(os.path.join(EX, name + ".eps"), encoding="utf-8").read()
        out, nerr = _compat.eps_compile(name + ".eps", src)
        ck.eq(name + " 번역 오류", nerr, 0)
        for needle in needles:
            ck.true("eps %s: %s" % (name, needle), out is not None and needle in out, "")


def _run_map(mod, frames, names, prep_extra=None):
    prog = emu.Program(mod.afterTriggerExec, setup=getattr(mod, "onPluginStart", None))
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m, units={}, text=True)
    lm = locmodel.install(m)
    if prep_extra:
        prep_extra(m)
    err = None
    rows = []
    try:
        for _ in range(frames):
            m.cycle()
            rows.append({n: m.var(n) for n in names})
    except emu.EmuError as e:
        err = str(e)
    return prog, m, lm, rows, err


def eps_emulate(ck):
    mod = _load_eps("spawn_example")
    names = ("frame", "homes", "boss", "live", "ovf")
    prog, m, lm, rows, err = _run_map(mod, 30, names, prep_extra=lambda mm: mm.loc_model.set_location(13, 2048, 2048,
                                                                                                     2048, 2048))
    got = rows[-1] if rows else {}
    nring, nstar = len(mod.ring), len(mod.star)
    print("  spawn epScript 에뮬레이션: 페이로드 %d B, %r, 생성 %d, 명령 %d" % (prog.payload_size, got, len(lm.plots),
                                                                            len(lm.orders)))
    ck.eq("eps 오류", err, None)
    ck.eq("eps 값", got, {"frame": 30, "homes": nring + nstar, "boss": 1, "live": 0, "ovf": 0})
    ck.eq("eps 명령 수 (기본 어택 원·별 + 명령 속성 페이드 원)", len(lm.orders), nring + nstar + nring)
    units_ = [p.unit for p in lm.plots if p.loc == LOC]  # eudplib 로케일 판별용 CreateUnit(실패) 1건 제외
    ck.eq("eps 유닛별 수", {u: units_.count(u) for u in set(units_)},
          {37: nring, 38: nstar, 39: nring, 40: nring, 68: 1, 33: nring})
    frames = {u: sorted({p.cycle for p in lm.plots if p.unit == u}) for u in (37, 38)}
    ck.eq("eps 2층 사이 빈 프레임", frames[38][0] - frames[37][-1], 2)
    boss = [p for p in lm.plots if p.unit == 68]
    ck.eq("eps 보스 removeTimer", m.unit_model.get(boss[0].indices[0], spawn.CU_REMOVE_TIMER, 2), 240)
    glob = [(p.x - 2048, p.y - 2048) for p in lm.plots if p.unit == 40]
    rot0 = 15 * 5  # 5 프레임째 tick 앞에서 sp.rotation = 75, 그 뒤 프레임마다 +15
    want = []
    k = 0
    for f in range(5):
        ang = rot0 + 15 * 2 * f
        for _ in range(4):
            if k < nring:
                want.append(spawn.rotate_py(*mod.ring.points[k], ang))
                k += 1
    ck.eq("eps 전역 회전 원 (사이클마다 그때의 각)", glob, want)
    texts = [x for x in m.text_model.texts() if x]
    ck.true("eps 문구 없음(넘침·오류)", not any("ERROR" in x for x in texts), repr(texts[:3]))


def _map_locations(m):
    """기준 맵 chk 의 MRGN 사각형을 에뮬레이터 메모리에 쓴다(에뮬레이터에는 MRGN 이 없다)."""
    import struct

    from eudplib import GetChkTokenized

    mrgn = GetChkTokenized().getsection("MRGN")
    for i in range(len(mrgn) // 20):
        rect = struct.unpack_from("<4I", mrgn, 20 * i)
        if any(rect):
            m.loc_model.set_location(i + 1, *rect)


def ingame_emulate(ck):
    """인게임 확인 맵을 끝까지 돌린다: 맵 자체 점검 모두 통과 + 패턴별 좌표·순서·명령 = 참조."""
    mod = _load_eps("spawn_ingame")
    names = ("frame", "phase", "checks", "good", "homes", "parked", "vis", "boss", "marks")
    prog, m, lm, rows, err = _run_map(mod, mod.TOTAL_FRAMES, names, prep_extra=_map_locations)
    got = rows[-1] if rows else {}
    print("  spawn 인게임 맵 에뮬레이션: %r, 페이로드 %d B, 생성 %d, 명령 %d" % (got, prog.payload_size, len(lm.plots),
                                                                          len(lm.orders)))
    ck.eq("ingame emu 오류", err, None)
    ck.eq("ingame 값", {k: got.get(k) for k in ("frame", "phase", "checks", "good")},
          {"frame": mod.TOTAL_FRAMES, "phase": mod.LAST_PHASE, "checks": mod.CHECKS, "good": mod.CHECKS})
    ck.eq("ingame 수", {k: got.get(k) for k in ("homes", "parked", "vis", "boss", "marks")},
          {"homes": mod.N1 + mod.N2, "parked": mod.NBH, "vis": 3 * mod.NBH, "boss": 1, "marks": 5})
    texts = [x for x in m.text_model.texts() if x]
    ck.true("ingame 다름 줄 없음", not any("다름 (프레임" in x for x in texts),
            repr([x for x in texts if "다름 (프레임" in x][:3]))
    ck.true("ingame 넘침·오류 문구 없음", not any("ERROR" in x for x in texts), "")
    plots = [p for p in lm.plots if p.loc == LOC]
    # 시야 격자: 12×12 중 맵 안 121점, P1 맵 리빌러
    rev = [p for p in plots if p.unit == 101]
    ck.eq("ingame 리빌러 격자 (맵 밖 건너뜀)", ([(p.x, p.y) for p in rev], {p.player for p in rev}, rev[0].cycle + 1),
          (mod.sp.preview(mod.grid), {0}, 1))
    # 패턴 1: 오른쪽 끝·아래쪽 끝 해처리 — 소환 좌표 = preview, 넣은 프레임에 모두, 본진(23) 어택
    for k, (cx_, cy_) in enumerate((mod.P1A, mod.P1B)):
        want = mod.sp.preview(mod.hatch, center=(cx_, cy_))
        got_pts = [(p.x, p.y) for p in plots if p.unit == mod.U_LING and p.cycle + 1 == mod.P1_FRAME + k]
        ck.eq("ingame 패턴1 %d 좌표 (%d점)" % (k, len(want)), got_pts, want)
    ling_orders = [o for o in lm.orders if o.unit == mod.U_LING]
    ck.eq("ingame 패턴1 명령 = 로케이션 23 어택", ({o.dest for o in ling_orders}, {o.order for o in ling_orders},
                                                len(ling_orders)), ({23}, {2}, mod.N1 + mod.N2))
    # 패턴 2: 페이드 — 18 프레임에 걸쳐 스케줄대로, 히드라·옵저버 같은 박자, 명령 없음(해제 뒤 트리거 명령만)
    sched = mod.bhFade.schedule
    for unit, start in ((mod.U_HYDRA, mod.PH2), (mod.U_OBS, mod.PH2)):
        per = [len([p for p in plots if p.unit == unit and p.cycle + 1 == start + f]) for f in range(len(sched))]
        ck.eq("ingame 패턴2 유닛 %d 프레임별 수 = 스케줄" % unit, per, list(sched))
    hyd = [p for p in plots if p.unit == mod.U_HYDRA]
    ck.eq("ingame 패턴2 히드라 무적", {m.unit_model.get(p.indices[0], spawn.CU_STATUS, 4) & spawn.STATUS_INVINCIBLE
                                   for p in hyd}, {spawn.STATUS_INVINCIBLE})
    ck.eq("ingame 패턴2 옵저버 기생 0xFF", {m.unit_model.get(p.indices[0], spawn.CU_PARASITE, 1)
                                      for p in plots if p.unit == mod.U_OBS}, {0xFF})
    ck.eq("ingame 패턴2 히드라 명령은 해제 트리거 한 번", [(o.loc, o.dest, o.order) for o in lm.orders
                                                if o.unit == mod.U_HYDRA], [(64, 23, 2)])
    # 패턴 3: 보스 워프 — 층 네 개가 2프레임 간격, 명령 목표 = 로케이션 14 중심, 보스 자리 = 로케이션 14
    warp_frames = sorted({p.cycle for p in plots if p.unit in mod.WARP_UNITS})
    ck.eq("ingame 패턴3 층 프레임 (빈 프레임 1개씩)", [f - warp_frames[0] for f in warp_frames], [0, 2, 4, 6])
    ck.eq("ingame 패턴3 층 순서", [p.unit for p in plots if p.unit in mod.WARP_UNITS][::36], list(mod.WARP_UNITS))
    wp = [(p.x, p.y) for p in plots if p.unit == 8]
    ck.eq("ingame 패턴3 도형 = 로케이션 13 중심", wp, mod.sp.preview(mod.warp, center=(2048, 2048)))
    dests = {o.dest_xy for o in lm.orders if o.unit in mod.WARP_UNITS}
    ck.eq("ingame 패턴3 명령 목표 = Location 14 중심 (A-3 17)", dests, {(2731, 2048)})
    boss = [(p.x, p.y, p.cycle + 1) for p in plots if p.unit == mod.U_BOSS]
    ck.eq("ingame 패턴3 보스 자리 = Location 14 (A-3 18)", boss, [(2731, 2048, mod.PH3 + 10)])
    marks = [(p.x, p.y) for p in plots if p.unit == mod.U_MARK]
    ck.eq("ingame A-3 19 번호 15 = 오른쪽 끝", marks, mod.sp.preview(mod.marker, center=(3413, 2048)))
    # 보조: 전역 회전 나선 — 소환 순간의 각 (PH4 부터 프레임마다 +12, 3프레임마다 한 점)
    from eudplib import EncodeUnit

    sc = [(p.x - 2048, p.y - 2048) for p in plots if p.unit == EncodeUnit("Zerg Scourge")]
    want = [spawn.rotate_py(*mod.ray.points[k], 12 * (1 + 3 * k)) for k in range(len(mod.ray))]
    ck.eq("ingame 보조 나선 (시계 방향)", sc, want)
    # 보조: 스킬 유닛 — 순찰(명령 속성)만, removeTimer 15
    br = [p for p in plots if p.unit == EncodeUnit("Zerg Broodling")]
    ck.eq("ingame 보조 스킬 유닛 수·removeTimer", (len(br), {m.unit_model.get(p.indices[0], spawn.CU_REMOVE_TIMER, 2)
                                                         for p in br}), (len(mod.ring), {15}))
    ck.eq("ingame 보조 스킬 유닛 명령 = 로케이션 18 순찰", {(o.order, o.dest_xy) for o in lm.orders
                                                           if o.unit == EncodeUnit("Zerg Broodling")},
          {(1, (2048, 2731))})
    # 보조: 스캔 이펙트
    scans = [p for p in plots if p.unit == 33]
    ck.eq("ingame 보조 스캔 수·주인", (len(scans), {p.player for p in scans}), (len(mod.ring), {1}))
    ck.eq("ingame 보조 스캔 이미지 되돌림", m.dw(SCAN_IMG) & 0xFFFF, 546)


def euddraft_builds(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("spawn_example", "spawn_ingame"):
        work = os.path.join(_common.WORK, "t_spawn_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")
        ck.true("freeze off " + name, not r.freeze)


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

COST_MEMORY = {"units": {}}
C_LINE = Shape([(k, 0) for k in range(40)], name="cost_line")
C_RING = RING
_C = {}


def _csp(name, **kw):
    sp = _C.get(name)
    if sp is None:
        sp = Spawner(capacity=8, loc=LOC, loc2=LOC2, default_target=HOME, name="c_" + name, **kw)
        sp.rtype("Home", sp.builtin.attack_default)
        sp.rtype("Nothing")
        _C[name] = sp
    return sp


def _cost_tick(name, lm, **pkw):
    sp = _csp(name)

    def setup(t):
        sp.push(1, C_LINE, center=(1000, 1000), lm=lm, **pkw)

    return dict(build=lambda t: sp.tick(), setup=setup)


def _cost_wait(name):
    sp = _csp(name)

    def setup(t):
        if EUDIf()(t.var("go").Exactly(1)):
            sp.push(1, C_LINE, center=(1000, 1000), lm=1, delay=50)
        EUDEndIf()
        sp.tick()  # 첫 사이클을 돌려 둔다 (다음 tick 은 기다리기만)

    return dict(build=lambda t: sp.tick(), setup=setup, setup_inputs={"go": 1}, setup_cycles=1)


_c_idle = _csp("idle")
_c_push = _csp("push")
_c_now = _csp("now")
_c_clear = _csp("clear")

COST_CASES = [
    CostCase("tick — 빈 대기열", lambda t: _c_idle.tick(), note="호출 자리 칸은 첫 호출이 만든 본문(서브루틴) 포함, 뒤 호출은 1"),
    CostCase("tick — 기다리는 레코드 1개(delay)", **_cost_wait("wait"), note="레코드 방문(pool 적재 20 + 되쓰기 4) + w 검사"),
    CostCase("tick db lm=1 (한 점, 후처리 없음)", **_cost_tick("p1", 1)),
    CostCase("tick db lm=10 (열 점, 후처리 없음)", **_cost_tick("p10", 10), note="(10점 − 1점)/9 = 점당 실행 (S1 8.6 ≤ 60)"),
    CostCase("tick db lm=10, rtype Home(기본 어택)", **_cost_tick("home10", 10, rtype="Home"),
             note="점당 캡처 21 + 위치 읽기 + 로케이션 + Order + 회전반경 (목표 기본 명령 +40)"),
    CostCase("tick db lm=10, 명령 속성(좌표)", **_cost_tick("ord10", 10, order=Order.attack(3000, 3000))),
    CostCase("tick db lm=10, size=150", **_cost_tick("sz10", 10, size=150), note="목표 크기 +40"),
    CostCase("tick db lm=10, rotate=30", **_cost_tick("rot10", 10, rotate=30), note="목표 회전 +120"),
    CostCase("tick db lm=10, rotate=GLOBAL", **_cost_tick("glob10", 10, rotate=spawn.GLOBAL)),
    CostCase("tick db lm=10, scan_effect(색)", build=lambda t: _csp("eff10").tick(),
             setup=lambda t: _csp("eff10").scan_effect(C_LINE, 429, color=16, center=(1000, 1000), lm=10),
             note="사이클마다 이미지·색 준비 약 60 + 점마다 트리거 1"),
    CostCase("push 상수 1층 (anchor 중심)", lambda t: _c_push.push(1, C_RING, lm=10)),
    CostCase("push 상수 1층 ((x, y) 상수)", lambda t: _c_push.push(1, C_RING, center=(100, 200))),
    CostCase("push 1층 변수 5개", lambda t: _c_push.push(t.var("u"), C_RING, center=(t.var("x"), t.var("y")),
                                                     size=t.var("s"), rotate=t.var("r")),
             {"u": 1, "x": 10, "y": 20, "s": 100, "r": 0}),
    CostCase("push 1층 로케이션 중심", lambda t: _c_push.push(1, C_RING, center=HOME)),
    CostCase("push 1층 변수 sid", lambda t: _c_push.push(1, t.var("sid"), center=(1, 2)), {"sid": 0}),
    CostCase("push 3층 (job)", lambda t: _c_push.job(center=(1, 2)).layer(1, C_RING).layer(2, C_RING).layer(3, C_RING).push()),
    CostCase("spawn_now 상수 1기 (후처리 없음)", lambda t: _c_now.spawn_now(1, at=(500, 500), rtype="Nothing")),
    CostCase("spawn_now 상수 1기 (Home)", lambda t: _c_now.spawn_now(1, at=(500, 500), rtype="Home")),
    CostCase("clear (레코드 3개)", lambda t: _c_clear.clear(),
             setup=lambda t: [_c_clear.push(1, C_RING, center=(1, 1), lm=1) for _ in range(3)]),
]


def main():
    rng = random.Random(12)
    ck = Checker("t_spawn (python)")
    python_checks(ck)
    trigger_independence(ck)

    s = Suite("t_spawn", memory={"units": {}, "text": True}, prep=_eff_prep)
    SV.shapes.add(SH41)
    SV.shapes.add(SH12S)
    SV.shapes.add(RING)
    SV.shapes.add(Shape(rpts(300, 11), name="sv300"))
    SV.shapes.add(SH3)
    build_cases(s)
    s.build()
    env = Env(s)
    run_table(s, env)
    run_n_o_p(s, env)
    run_jkl(s, env)
    run_m(s, env)
    run_rtypes(s, env)
    run_centers(s, env)
    run_now(s, env)
    run_effects(s, env)
    run_on_create(s, env)
    run_global_per_point(s, env)
    run_sv(s, env, rng)
    ok1 = s.report()

    cke = Checker("t_spawn (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    ingame_emulate(cke)
    euddraft_builds(cke)
    finish(ok1, ck.report(), cke.report())


if __name__ == "__main__":
    main()
