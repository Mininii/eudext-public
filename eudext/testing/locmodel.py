"""에뮬레이터용 로케이션 모델 (DESIGN 5.1 표의 "MoveLocation / MRGN 모델" — WP7).

scmodel(공용 파일)을 고치지 않고 따로 끼운다. `scmodel.install(machine, units={…})` 로 유닛 모델을 먼저 끼운 뒤 부른다.

    from eudext.testing import locmodel
    lm = locmodel.install(machine)            # machine.loc_model
    lm.set_location(26, 0, 0, 0, 0)
    …  machine.cycle()
    lm.plots                                  # 생성 기록: PlotRecord(cycle, loc, rect, x, y, unit, player, count, ok, …)
    lm.points()                               # [(x, y)] — 만들 때 로케이션 중심

하는 일
- **생성 기록**: CreateUnit(44)·CreateUnitWithProperties(11) 처리기를 감싸 그 순간의 로케이션 사각형(MRGN 메모리)과
  중심을 기록한다(유닛 모델의 CreateRecord 는 로케이션 번호만 남긴다). 유닛 모델이 없으면 생성은 흉내 내지 않고
  사각형만 기록한다(ok = None).
- **MoveLocation(38)**: 찾는 곳(locid1) 안에서 주인·종류가 맞는 첫 유닛(유닛 모델의 활성 목록 순서, 유닛 중심이 사각형 안)의
  위치로 옮길 로케이션(p2)의 중심을 옮긴다. 크기는 그대로(왼쪽 = x − 폭//2, 위 = y − 높이//2). 맞는 유닛이 없으면
  찾는 곳의 중심으로 옮긴다(eudplib `MoveLocation` 설명). **인게임 미확인 가정**: 홀수 폭의 반올림, 유닛이 여럿일 때 고르는 순서.
- **명령 기록**(WP12 — spawn 시험): Order(46) 처리기를 감싸 그 순간의 시작 로케이션 사각형·목표 로케이션 사각형·목표 중심과
  **명령받은 유닛**(시작 사각형 안에 중심이 있는, 주인·종류가 맞는 살아 있는 유닛 전부 — SC `Order` 가 상자 안의 유닛 전부에
  명령하는 것)을 `orders` 에 남긴다(OrderPlot). 유닛 모델의 OrderRecord 도 그대로 남는다.
  `order_move=True` 면 명령받은 유닛을 목표 중심으로 바로 옮긴다(유닛 이동의 가장 단순한 모델 — 걷는 시간·길 찾기 없음).
- 로케이션은 MRGN 메모리(0x58DC60, 20B, 1-based 번호)에 있으므로 스냅숏·restore 로 함께 되돌아간다. 기록(`plots`, `moves`,
  `orders`)은 파이썬 쪽이라 `clear()` 로 지운다.

설치: `install(machine, record=True, move=True, orders=True, order_move=False)` → LocModel. harness 에서는
`Suite(prep=lambda m: locmodel.install(m))` (유닛 모델이 `memory={"units": {}}` 로 먼저 끼워진 뒤 prep 이 불린다).
"""

from collections import namedtuple

from eudext.testing import scmodel

__all__ = ["ACT_MOVE_LOCATION", "ACT_ORDER", "LocModel", "MoveRecord", "OrderPlot", "PlotRecord", "install", "loc_model"]

ACT_MOVE_LOCATION = 38
ACT_ORDER = scmodel.ACT_ORDER
MRGN_TABLE = scmodel.MRGN_TABLE
MRGN_SIZE = scmodel.MRGN_SIZE
LOC_ANYWHERE = scmodel.LOC_ANYWHERE
M32 = 0xFFFFFFFF

PlotRecord = namedtuple("PlotRecord", "cycle loc rect x y unit player count ok indices action props")
PlotRecord.__doc__ = """CreateUnit 한 번의 기록 (로케이션 사각형 포함).

cycle: 몇 번째 사이클(0부터), loc: 로케이션 번호(1-based), rect: (왼, 위, 오른, 아래) 부호 있는 값,
x, y: 사각형 중심((왼+오른)//2, (위+아래)//2 — 유닛 모델의 생성 위치와 같다), unit, player, count(수량, 0 → 1),
ok(유닛 모델이 없으면 None), indices: 만든 칸 번호, action: "CreateUnit" | "CreateUnitWithProperties",
props: UPRP 번호(WithProperties 만, 아니면 None)
"""
MoveRecord = namedtuple("MoveRecord", "cycle loc src unit player found rect")
MoveRecord.__doc__ = """MoveLocation 한 번의 기록 (loc = 옮긴 로케이션, src = 찾는 곳, found = 찾은 유닛 칸 또는 None, rect = 옮긴 뒤)."""
OrderPlot = namedtuple("OrderPlot", "cycle unit player loc rect order dest dest_rect dest_xy targets")
OrderPlot.__doc__ = """Order 한 번의 기록 (WP12).

cycle, unit(종류 — 229 = 아무 유닛), player(해석한 플레이어, 17 = 모두), loc(시작 로케이션 1-based), rect(시작 사각형),
order(SC 명령 번호 0 Move · 1 Patrol · 2 Attack), dest(목표 로케이션), dest_rect(목표 사각형), dest_xy(목표 중심),
targets(명령받은 유닛 칸 번호 — 유닛 모델이 없으면 ())
"""


def _s32(v):
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v


class LocModel:
    """로케이션 표 읽기·쓰기 + 생성 기록 + MoveLocation. `install` 이 만든다.

    메서드: `rect(n)`, `center(n)`, `set_location(n, l, t, r, b)`, `points(ok_only=False)`, `clear()`
    기록: `plots`(PlotRecord 목록), `moves`(MoveRecord 목록), `orders`(OrderPlot 목록 — WP12)
    설정: `order_move`(True 면 명령받은 유닛을 목표 중심으로 바로 옮김 — WP12)
    """

    def __init__(self, machine):
        self.m = machine
        self.plots = []
        self.moves = []
        self.orders = []
        self.order_move = False

    def _addr(self, n):
        return MRGN_TABLE + MRGN_SIZE * (n - 1)

    def rect(self, n):
        a = self._addr(n)
        return tuple(_s32(self.m.dw(a + 4 * k)) for k in range(4))

    def center(self, n):
        left, top, right, bottom = self.rect(n)
        return (left + right) // 2, (top + bottom) // 2

    def set_location(self, n, left, top, right, bottom):
        a = self._addr(n)
        for k, v in enumerate((left, top, right, bottom)):
            self.m.setdw(a + 4 * k, v & M32)

    def points(self, ok_only=False):
        return [(r.x, r.y) for r in self.plots if not ok_only or r.ok]

    def clear(self):
        del self.plots[:]
        del self.moves[:]
        del self.orders[:]

    def _cycle(self):
        return len(self.m.ends)

    # --- 처리기 ---
    def on_create(self, orig, fields):
        locid, _strid, _wav, _time, p1, p2, unit, atype, amount, _flags, _eudx = fields
        rect = self.rect(locid)
        x, y = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        um = scmodel.unit_model(self.m)
        ok, indices, player = None, (), p1
        if orig is not None and um is not None:
            before = len(um.created)
            orig(self.m, fields)
            if len(um.created) > before:
                rec = um.created[-1]
                ok, indices, player = rec.ok, rec.indices, rec.player
        elif p1 == 13:
            player = self.m.dw(scmodel.CP_ADDR)
        if atype == scmodel.ACT_CREATE_UNIT:
            action, props = "CreateUnit", None
        else:
            action, props = "CreateUnitWithProperties", p2
        self.plots.append(PlotRecord(self._cycle(), locid, rect, x, y, unit, player, amount or 1, ok, indices, action, props))

    def on_move(self, fields):
        src, _strid, _wav, _time, p1, dst, unit, _atype, _amount, _flags, _eudx = fields
        um = scmodel.unit_model(self.m)
        found = None
        if um is not None:
            player = self.m.dw(scmodel.CP_ADDR) if p1 == 13 else p1
            sl, st, sr, sb = self.rect(src)
            for i in um.active_list():
                if not um.alive(i):
                    continue
                if p1 != 17 and um.owner(i) != player:
                    continue
                if unit != scmodel.UNIT_ANY and um.unit_type(i) != unit:
                    continue
                px, py = um.pos(i)
                if src != LOC_ANYWHERE and not (sl <= px <= sr and st <= py <= sb):
                    continue
                found = i
                break
        if found is not None:
            cx, cy = um.pos(found)
        else:
            cx, cy = self.center(src)
        left, top, right, bottom = self.rect(dst)
        w, h = right - left, bottom - top
        nl, nt = cx - w // 2, cy - h // 2
        self.set_location(dst, nl, nt, nl + w, nt + h)
        self.moves.append(MoveRecord(self._cycle(), dst, src, unit, p1, found, self.rect(dst)))

    def on_order(self, orig, fields):
        locid, _strid, _wav, _time, p1, p2, unit, _atype, amount, _flags, _eudx = fields
        rect = self.rect(locid)
        dest_rect = self.rect(p2)
        dest_xy = ((dest_rect[0] + dest_rect[2]) // 2, (dest_rect[1] + dest_rect[3]) // 2)
        um = scmodel.unit_model(self.m)
        player = self.m.dw(scmodel.CP_ADDR) if p1 == 13 else p1
        targets = []
        if um is not None:
            left, top, right, bottom = rect
            for i in um.active_list():
                if not um.alive(i):
                    continue
                if player != 17 and um.owner(i) != player:
                    continue
                if unit != scmodel.UNIT_ANY and um.unit_type(i) != unit:
                    continue
                px, py = um.pos(i)
                if locid != LOC_ANYWHERE and not (left <= px <= right and top <= py <= bottom):
                    continue
                targets.append(i)
        if orig is not None:
            orig(self.m, fields)
        if self.order_move and um is not None:
            for i in targets:
                um.set_pos(i, dest_xy[0] & 0xFFFF, dest_xy[1] & 0xFFFF)
        self.orders.append(OrderPlot(self._cycle(), unit, player, locid, rect, amount, p2, dest_rect, dest_xy,
                                     tuple(targets)))


def loc_model(machine):
    """machine 에 끼운 LocModel (없으면 None)."""
    return getattr(machine, "loc_model", None)


def install(machine, record=True, move=True, orders=True, order_move=False):
    """로케이션 모델을 끼운다. 유닛 모델(scmodel.install_units)을 먼저 끼워야 생성·MoveLocation·Order 가 유닛을 본다.

    인자: record(생성 기록 — CreateUnit 처리기를 감싼다), move(MoveLocation 처리기),
          orders(명령 기록 — Order 처리기를 감싼다, WP12), order_move(명령받은 유닛을 목표 중심으로 바로 옮기기)
    반환: LocModel (`machine.loc_model` 에도 둔다). 두 번 불러도 처리기를 겹쳐 감싸지 않는다.
    """
    lm = loc_model(machine)
    if lm is None:
        lm = LocModel(machine)
        machine.loc_model = lm
    if record:
        for atype in (scmodel.ACT_CREATE_UNIT, scmodel.ACT_CREATE_UNIT_PROPS):
            cur = machine.act_handlers.get(atype)
            if getattr(cur, "_locmodel", False):
                continue
            orig = cur

            def handler(m, f, _orig=orig):
                m.loc_model.on_create(_orig, f)

            handler._locmodel = True
            machine.act_handlers[atype] = handler
    if move:
        machine.act_handlers[ACT_MOVE_LOCATION] = lambda m, f: m.loc_model.on_move(f)
    if orders:
        cur = machine.act_handlers.get(ACT_ORDER)
        if not getattr(cur, "_locmodel", False):

            def order_handler(m, f, _orig=cur):
                m.loc_model.on_order(_orig, f)

            order_handler._locmodel = True
            machine.act_handlers[ACT_ORDER] = order_handler
    lm.order_move = bool(order_move)
    return lm
