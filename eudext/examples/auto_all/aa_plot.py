"""auto_all phase 13 `plot` (프레임 300~845, 정리 850) — examples/plot_ingame.eps 를 파이썬으로 옮기고 계측했다.

원래 맵과 같은 도형·플로터·프레임 순서다(pf = 이 단계 안 프레임 1부터). 더한 것:
- `Plotter(capture=True)` + `on_created` 콜백에서 **만든 유닛의 위치(+0x28)** 를 `shapes.point_at(sid, index) + 중심`
  과 맞대 본다 → `plot.D7-1.posbad` / `orderbad`(점 번호가 0 또는 앞 번호 + 1 이 아닌 수). D7-1 의 "그 자리에 그 순서로".
- 프레임별 생성 수를 플로터별로 이어 적는다(빈 프레임은 건너뛰고 첫·끝 프레임과 간격을 따로) → D7-2·D7-3.
- 원(①) 두 번째 점의 중심 상대 좌표 → D7-1 의 "12시(0, −32)".
- 화면 줄은 원래 맵과 같다. epScript 에서 부르는 함수는 `f_` 이름이다.
"""

from eudplib import (
    DoActions,
    EUDArray,
    EUDElse,
    EUDEndIf,
    EUDIf,
    EUDVariable,
    P1,
    RemoveUnit,
    f_setcurpl,
    f_setloc,
    f_wread_epd,
)
from eudplib import CenterView

import aa_common as aa
from eudext import dbg, plot, shape

# 2026-09-18 인게임: 도형 유닛끼리 밀려 좌표가 어긋났다 (posbad 18, nudged 82).
# ① eds 의 [noAirCollision](euddraft 0.11 번들)이 공중 반발 표를 매 프레임 지우고,
# ② 여기서 도형에 쓰는 다섯 유닛의 충돌 상자를 1,1,1,1 로 만든다 (units.dat SizeL/U/R/D, 0x6617C8+8n).
#    점 간격이 6px 인 막대 도형(스카웃·커세어)도 제자리에 남아야 한다.
#    충돌 상자는 aa_early.py 가 **유닛 228개 전부**에 1,1,1,1 로 건다(dat.all_unit_size) — 여기서는 따로 걸지 않는다.

cx = shape.CX(seed=1234)
_dia = cx.run("function EudextDiamond(W, H, S) local P = {} for x = -W, W, S do local L = math.floor(H * (1 - "
              "math.abs(x) / W)) for y = -math.floor(L / S) * S, L, S do P[#P + 1] = {x, y} end end local R = {#P} "
              "for i, v in ipairs(P) do R[i + 1] = v end return R end")
circle = cx.call("CSMakeCircle", 6, 32, 0, 19, 0)
star = cx.eval("CSMakeStar(5, 144, 48, 0, CS_Level('Star', 5, 3), 0)")
ray = cx.call("CSMakeLine", 1, 32, 0, 6, 1)
rayR = cx.call("CS_Rotate", ray, 90)
dia = cx.call("EudextDiamond", 256, 96, 32)
fade = dia.sweep("right", px_per_cycle=32)
shapes = shape.ShapeSet([circle, star, ray, rayR, fade])

PH2, PH3, PH4, PH5 = 201, 301, 421, 540
TOTAL_FRAMES = 545
CHECKS = 15
MADE_TOTAL = 211  # 19 + 31 + 5 + 5 + 5 + 19 + 19 + 51 + 19×3
UNITS = ("Zerg Scourge", "Zerg Mutalisk", "Terran Wraith", "Protoss Scout", "Protoss Corsair")

frame = EUDVariable()
phase = EUDVariable()
made = EUDVariable()
checks = EUDVariable()
good = EUDVariable()
rounds = EUDVariable()
posbad = EUDVariable()
nudged = EUDVariable()
madebad = EUDVariable()
orderbad = EUDVariable()
p2dx = EUDVariable()
p2dy = EUDVariable()


class _Seq:
    """플로터별 "프레임마다 만든 수" 를 빈 프레임을 건너뛰고 이어 적는다 (D7-2·D7-3)."""

    def __init__(self, name, n):
        self.arr = EUDArray(n)
        self.cnt = EUDVariable()
        self.n = EUDVariable()
        self.first = EUDVariable()
        self.last = EUDVariable()
        self.name = name
        dbg.snapshot("plot.%s.seq" % name, self.arr, n, every=0, suite="plot")

    def flush(self, pf):
        if EUDIf()(self.cnt >= 1):
            self.arr[self.n] = self.cnt
            self.n += 1
            if EUDIf()(self.first == 0):
                self.first << pf
            EUDEndIf()
            self.last << pf
            self.cnt << 0
        EUDEndIf()

    def report(self):
        dbg.capture("plot.%s.seq" % self.name)
        dbg.mark("plot.%s.n" % self.name, self.n, suite="plot")
        dbg.mark("plot.%s.first" % self.name, self.first, suite="plot")
        dbg.mark("plot.%s.span" % self.name, self.last - self.first, suite="plot")


def _mk(unit, per_tick=1, delay=4, repeat=False):
    return plot.Plotter(shapes, unit=unit, owner=P1, loc=26, per_tick=per_tick, delay=delay, repeat=repeat,
                        capture=True)


pA = _mk("Zerg Scourge")
pB = _mk("Zerg Mutalisk")
pC = _mk("Terran Wraith")
pD = _mk("Protoss Scout")
pE = _mk("Protoss Corsair")
pF = _mk("Zerg Scourge", per_tick=6, delay=1)
pG = _mk("Zerg Mutalisk", per_tick=6, delay=8)
pS = _mk("Zerg Scourge")
pR = _mk("Terran Wraith", per_tick=2, delay=2, repeat=True)

seqF = _Seq("D7-2.pF", 8)
seqG = _Seq("D7-2.pG", 8)
seqS = _Seq("D7-3.pS", 24)


def _watch(pl, sid, seq=None, second=False, strict=True):
    """점마다 생성 직후: 위치·순서 판정 (sid = 기대 도형 번호 — ⑤는 정적 회전 도형 3).

    `strict=False` 는 **몸집이 큰 공중 유닛**(뮤탈·레이스·스카웃·커세어)용이다 — 2026-09-18 인게임에서 점 간격(6~32px)이
    유닛 충돌 상자보다 작아 게임이 만든 유닛을 밀어냈다(`posbad` 102/211). 그 플로터는 밀린 수를 `nudged` 에 기록만 하고,
    자리 판정(`posbad`)은 스커지(충돌 상자 12px < 점 간격 32px) 플로터에서만 한다. 순서·생성 성공은 모두 판정한다.
    """
    nexti = EUDVariable()
    bad = posbad if strict else nudged

    def created(pt):
        px, py = pt.center
        ex, ey = shapes.point_at(sid, pt.index)
        ex += px
        ey += py
        if EUDIf()(pt.unit.ok):
            gx = f_wread_epd(pt.unit.epd + 10, 0)
            gy = f_wread_epd(pt.unit.epd + 10, 2)
            if EUDIf()([gx == ex, gy == ey]):
                pass
            if EUDElse()():
                bad.__iadd__(1)
            EUDEndIf()
            if second:
                if EUDIf()(pt.index == 1):
                    p2dx << gx - px
                    p2dy << gy - py
                EUDEndIf()
        if EUDElse()():
            madebad.__iadd__(1)
        EUDEndIf()
        if EUDIf()(pt.index == nexti):
            nexti << pt.index + 1
        if EUDElse()():
            if EUDIf()(pt.index == 0):  # repeat 로 다시 시작
                nexti << 1
            if EUDElse()():
                orderbad.__iadd__(1)
            EUDEndIf()
        EUDEndIf()
        if seq is not None:
            seq.cnt.__iadd__(1)

    pl.on_created(created)
    return pl


# 2026-09-18 뒤: 충돌 상자 1,1,1,1 + [noAirCollision] 이라 **모든 플로터**가 자리 판정(strict)이다.
# (그 전에는 몸집 큰 공중 유닛이 밀려 뮤탈·레이스·스카웃·커세어·반복 원은 nudged 기록만 했다.)
for _pl, _sid, _st in ((pA, 0, True), (pB, 1, True), (pC, 2, True), (pD, 3, True), (pE, 3, True), (pR, 0, True)):
    _watch(_pl, _sid, second=_pl is pA, strict=_st)
_watch(pF, 0, seq=seqF)
_watch(pG, 0, seq=seqG)
_watch(pS, 4, seq=seqS)


def _clear_units():
    DoActions([RemoveUnit(u, P1) for u in UNITS])   # 파이썬에서는 액션을 DoActions 로 내야 한다


def _check(ok):
    checks.__iadd__(1)
    if EUDIf()(ok):
        good.__iadd__(1)
    if EUDElse()():
        aa.f_say("\x08[D7] 점검 {} 다름 (프레임 {})", checks, frame)
    EUDEndIf()


def f_step(f):
    """진행기가 300~845 프레임에 부른다 (pf = f − 299)."""
    pf = EUDVariable()
    pf << f
    pf -= 299
    frame << pf
    if EUDIf()(pf == 1):
        phase << 1
        f_setcurpl(0)
        DoActions(CenterView("Location 13"))
        aa.f_say("\x07[D7-1] 모양·방향: 네 도형이 4프레임마다 한 점씩 찍힌다. 원(스커지)·별(뮤탈)은 위, 막대 셋은 아래")
        aa.f_say("\x07[D7-1] 원: 가운데 → 바로 위(12시) → 시계 방향 6점 → 다시 12시(반지름 64) → 시계 방향 12점 (기대)")
        pA.start(0, center=(1850, 1880))
        pB.start(1, center=(2230, 1880))
        pC.start(2, center=(1800, 2260))
        pD.start(3, center=(1950, 2230))
        pE.start(2, center=(2150, 2230))
    EUDEndIf()
    if EUDIf()(pf == PH2):
        phase << 2
        _clear_units()
        aa.f_say("\x07[D7-2] 속도: 왼쪽 원은 한 프레임에 6점씩(4프레임에 끝), 오른쪽 원은 8프레임마다 6점씩 (기대)")
        pF.start(0, center=(1850, 2048))
        pG.start(0, center=(2230, 2048))
    EUDEndIf()
    if EUDIf()(pf == PH3):
        phase << 3
        _clear_units()
        aa.f_say("\x07[D7-3] 스케줄: 가로 다이아몬드가 왼쪽 끝부터 한 열(32px)씩 4프레임마다 오른쪽으로, 17열 (기대)")
        pS.start(4, center=(2048, 2048))
    EUDEndIf()
    if EUDIf()(pf == PH4):
        phase << 4
        _clear_units()
        aa.f_say("\x07[D7-4] 반복: 가운데 원이 2프레임마다 2점씩, 다 그리면 지우고 다시. 세 번 뒤 멈춤 (기대)")
        pR.start(0, center=(2048, 2048))
    EUDEndIf()
    if EUDIf()([pR.index == 0, rounds == 3]):
        pR.stop()
    EUDEndIf()

    for pl in (pA, pB, pC, pD, pF, pG, pS):
        for _pt in pl.each():
            made.__iadd__(1)
    for pt in pE.each():
        pt.rotate(90)                                    # 런타임 회전(CA_Rotate): 12시 막대 → 3시
        sx, sy = shapes.point_at(3, pt.index)            # 정적 회전(CS_Rotate) 결과와 같아야 한다 (D7-1 ⑤ = ④)
        _check([pt.x == sx, pt.y == sy])
        made.__iadd__(1)
    for pt in pR.each():
        if EUDIf()(pt.index == 0):
            DoActions(RemoveUnit("Terran Wraith", P1))
            rounds.__iadd__(1)
        EUDEndIf()
        made.__iadd__(1)
    seqF.flush(pf)
    seqG.flush(pf)
    seqS.flush(pf)

    if EUDIf()(pf == 120):
        _check(pB.busy)
    EUDEndIf()
    if EUDIf()(pf == 121):
        _check(pB.done)
        _check([pA.done, pC.done, pD.done, pE.done])
        aa.f_say("\x07[D7-1] 찍기 끝 — 원·별·막대 모양과 순서를 알려 주세요")
    EUDEndIf()
    if EUDIf()(pf == PH2 + 3):
        _check(pF.done)
    EUDEndIf()
    if EUDIf()(pf == PH2 + 23):
        _check(pG.busy)
    EUDEndIf()
    if EUDIf()(pf == PH2 + 24):
        _check(pG.done)
        aa.f_say("\x07[D7-2] 두 원 끝 (오른쪽이 약 1초 늦게 끝나면 정상)")
    EUDEndIf()
    if EUDIf()(pf == PH3 + 63):
        _check(pS.busy)
    EUDEndIf()
    if EUDIf()(pf == PH3 + 64):
        _check(pS.done)
        aa.f_say("\x07[D7-3] 다이아몬드 끝 (약 2.7초 동안 왼→오로 고르게 채워지면 정상)")
    EUDEndIf()
    if EUDIf()(pf == PH5):
        phase << 5
        _check([rounds == 3, pR.done])
        _check(made == MADE_TOTAL)
        aa.f_say("\x07[D7-4] 원 {} 번 그림 (3), 만든 점 {} ({})", rounds, made, MADE_TOTAL)
        aa.f_say("\x07[D7-5] 점검 {} / {} (같으면 정상, 기대 {})", good, checks, CHECKS)
        _report()
    EUDEndIf()


def _report():
    dbg.mark("plot.D7-1.posbad", posbad, suite="plot")
    dbg.mark("plot.D7-1.nudged", nudged, suite="plot")
    dbg.mark("plot.D7-1.madebad", madebad, suite="plot")
    dbg.mark("plot.D7-1.orderbad", orderbad, suite="plot")
    dbg.mark("plot.D7-1.p2dx", p2dx, suite="plot")
    dbg.mark("plot.D7-1.p2dy", p2dy, suite="plot")
    dbg.check("plot.D7-1.pos", [posbad.Exactly(0), orderbad.Exactly(0), madebad.Exactly(0)], suite="plot")
    dbg.mark("plot.D7-4.rounds", rounds, suite="plot")
    dbg.mark("plot.D7-4.made", made, suite="plot")
    dbg.check("plot.D7-4.made", [rounds.Exactly(3), made.Exactly(MADE_TOTAL)], suite="plot")
    dbg.result("plot.D7-5.all", good, checks, suite="plot")
    seqF.report()
    seqG.report()
    seqS.report()


def f_cleanup():
    """phase 끝(850): 만든 유닛을 지우고 로케이션 26 을 되돌린다."""
    _clear_units()
    f_setloc(26, 0, 0)


def f_clean_check():
    """정리 확인(853): 이 단계가 만든 종류가 하나도 남지 않았다."""
    dbg.check("aa.clean.plot", [aa.f_count_is(P1, u, 0) for u in UNITS])
