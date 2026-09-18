"""자동 점검 통합 맵(`auto_all`)·계측판 맵을 에뮬레이터로 돌릴 때 필요한 SC 모델 보탬 (DESIGN 5.1 표, WP-D).

`scmodel`(유닛·글)·`locmodel`(로케이션·명령)·`dispmodel`(표시·TBL·이름)·`chatmodel`(채팅 버퍼) 위에 다음을 더한다.

| 더한 것 | 무엇 | 근거·가정 |
|---|---|---|
| `Command` 조건(2) | 살아 있는 유닛 수(229 = 아무 유닛) | SC 동작. 정리 확인(`aa.clean.*`)이 쓴다 |
| `SetInvincibility` 액션(43) | 대상 유닛의 +0xDC 무적 비트(0x04000000) 켜기·끄기 | **가정**(로케이션은 무시) — spawn E12-2 |
| `SetResources` 액션(26) | 광물 0x57F0F0·가스 0x57F120 표 (SetTo·Add·Subtract) | SC 동작 — players B8-4 |
| 피해 배율 표 | 0x515B88 에 바닐라 값(폭발형 소형·중형·대형 128·192·256) | S5 A.9-4 — datpatch B15-1 |
| `Sim.after_cycle` | removeTimer 카운트다운 → 제거, Order 뒤 orderTarget(+0x58) 쓰기, 탄막 유닛(204·208·210) 진행 방향의 표적 마린 제거 | **가정**(SC 물리·명령 처리를 아주 단순하게 흉내) — spawn E12-6, bullet D14-1·2 |

"진행 방향의 표적 제거" 는 SC 의 총알을 흉내 내는 것이 아니라 **맵의 계측 흐름**(명중 판정을 어디서 읽는지)을 끝까지
돌려 보기 위한 최소 모형이다. 실제 탄이 어디로 나는지는 인게임에서만 알 수 있다(D14-1·2).
"""
import math
import struct

from eudext.testing import chatmodel, dispmodel, locmodel, scmodel

COND_COMMAND = 2
ACT_SET_INVINCIBILITY = 43
ACT_SET_RESOURCES = 26
ORE_TABLE = 0x57F0F0
GAS_TABLE = 0x57F120
STATUS_INVINCIBLE = 0x04000000
CU_STATUS = 0xDC
CU_REMOVE_TIMER = 0x110
CU_FACING = 0x21
RATIO_BASE = 0x515B88
RATIOS = ((0, 256, 256, 256, 0), (0, 128, 192, 256, 0), (0, 256, 128, 64, 0), (0, 256, 256, 256, 0),
          (0, 256, 256, 256, 0))
BULLET_UNITS = (204, 208, 210)
MARINE = 0
ANY_UNIT = 229


def _cp(m):
    return m.dw(0x6509B0)


def install_command(m):
    """Command 조건: 살아 있는 유닛 수 (229 = 아무 유닛). 유닛 모델이 있어야 한다."""

    def handler(mm, fields):
        _locid, player, amount, unit, cmp_, _ct, _rt, _fl, _ex = fields
        if player == 13:
            player = _cp(mm)
        if player > 11:
            return False
        um = mm.unit_model
        if unit == ANY_UNIT:
            n = len(list(um.units(player=player)))
        else:
            n = len(list(um.units(player=player, unit=unit)))
        if cmp_ == 0:
            return n >= amount
        if cmp_ == 1:
            return n <= amount
        return n == amount

    m.cond_handlers[COND_COMMAND] = handler


def install_invincibility(m):
    """SetInvincibility(Enable=4 / Disable=5): 대상 유닛의 +0xDC 무적 비트를 켜고 끈다(로케이션은 무시)."""

    def handler(mm, fields):
        _locid, _strid, _wavid, _time, p1, _p2, unit, _at, amount, _fl, _ex = fields
        if p1 == 13:
            p1 = _cp(mm)
        um = mm.unit_model
        players = range(12) if p1 == 17 else [p1]
        for p in players:
            if p > 11:
                continue
            for i in um.units(player=p, unit=None if unit == ANY_UNIT else unit):
                v = um.get(i, CU_STATUS, 4)
                um.set(i, CU_STATUS, (v | STATUS_INVINCIBLE) if amount == 4 else (v & ~STATUS_INVINCIBLE), 4)

    m.act_handlers[ACT_SET_INVINCIBILITY] = handler


def install_resources(m):
    """SetResources(수정자 7 SetTo · 8 Add · 9 Subtract, 자원 0 광물 · 1 가스 · 2 둘)."""

    def handler(mm, fields):
        _locid, _strid, _wavid, _time, p1, p2, restype, _at, mod, _fl, _ex = fields
        if p1 == 13:
            p1 = _cp(mm)
        players = range(12) if p1 == 17 else [p1]
        tables = {0: (ORE_TABLE,), 1: (GAS_TABLE,), 2: (ORE_TABLE, GAS_TABLE)}.get(restype, ())
        for p in players:
            if p > 11:
                continue
            for base in tables:
                a = base + 4 * p
                old = mm.dw(a)
                if mod == 7:
                    new = p2
                elif mod == 8:
                    new = old + p2
                else:
                    new = max(0, old - p2)
                mm.setdw(a, new & 0xFFFFFFFF)

    m.act_handlers[ACT_SET_RESOURCES] = handler


def install_ratio_table(m):
    for t, row in enumerate(RATIOS):
        for s, v in enumerate(row):
            m.setdw(RATIO_BASE + 4 * (t * 5 + s), v)


class Sim:
    """사이클마다 흉내 내는 SC 동작: removeTimer 카운트다운, 총알 명중, Order 뒤 +0x58 쓰기."""

    def __init__(self, m, lm):
        self.m = m
        self.lm = lm
        self.um = m.unit_model
        self.seen_orders = 0
        self.seen_created = 0
        self.hits = 0
        self.timers = True

    def _orders(self):
        for o in self.lm.orders[self.seen_orders:]:
            x, y = o.dest_xy
            for i in o.targets:
                self.um.set(i, 0x58, x & 0xFFFF, 2)
                self.um.set(i, 0x5A, y & 0xFFFF, 2)
        self.seen_orders = len(self.lm.orders)

    def _bullets(self):
        """새로 만든 탄막 유닛(204·208·210)의 진행 방향(facing + 128)에 있는 P2 마린을 없앤다."""
        news = [r for r in self.um.created[self.seen_created:] if r.ok and r.unit in BULLET_UNITS]
        self.seen_created = len(self.um.created)
        for r in news:
            i = r.indices[0]
            face = self.um.get(i, CU_FACING, 1)
            bx, by = self.um.pos(i)
            ang = (face + 128) % 256 * 2 * math.pi / 256
            dx, dy = math.sin(ang), -math.cos(ang)
            for j in list(self.um.units(player=1, unit=MARINE)):
                mx, my = self.um.pos(j)
                px, py = mx - bx, my - by
                proj = px * dx + py * dy
                perp = abs(px * dy - py * dx)
                if 0 <= proj <= 400 and perp <= 40:
                    self.um.kill(j)
                    self.hits += 1

    def _timers(self):
        for i in list(self.um.units()):
            t = self.um.get(i, CU_REMOVE_TIMER, 2)
            if t:
                t -= 1
                self.um.set(i, CU_REMOVE_TIMER, t, 2)
                if t == 0:
                    self.um.kill(i)

    def after_cycle(self, cyc):
        self._orders()
        self._bullets()
        if self.timers:
            self._timers()
        if cyc % 5 == 0:
            self.um.process_deaths()


def install_all(m, chk_locations=None, names=None):
    """모든 모델을 끼운다. 반환: (lm, dm, cm, sim)"""
    lm = locmodel.install(m)
    dm = dispmodel.install(m, tbl={1: (b"Terran Marine", 64)}, names=names or {0: b"Tester"})
    cm = chatmodel.install(m, strings=dispmodel.live_strings(m))
    install_command(m)
    install_invincibility(m)
    install_resources(m)
    install_ratio_table(m)
    if chk_locations:
        for n, rect in chk_locations.items():
            lm.set_location(n, *rect)
    return lm, dm, cm, Sim(m, lm)


def map_locations():
    """지금 불러온 맵 chk 의 MRGN → {번호: (l, t, r, b)}"""
    from eudplib import GetChkTokenized

    mrgn = GetChkTokenized().getsection("MRGN")
    out = {}
    for i in range(len(mrgn) // 20):
        rect = struct.unpack_from("<4I", mrgn, 20 * i)
        if any(rect):
            out[i + 1] = rect
    return out


def prespawn(m, firebat_hp=50):
    """기준 맵(auto_all_base.scx)처럼 미리 놓인 유닛: P1 맵 리빌러 64 + 시작 위치 2 + P1 파이어뱃 1."""
    um = scmodel.unit_model(m)
    for _ in range(64):
        um.spawn(101, 0)
    um.spawn(214, 0)
    um.spawn(214, 1)
    fb = um.spawn(32, 0, x=160, y=160, hp=firebat_hp)
    return um, fb
