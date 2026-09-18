"""에뮬레이터용 SC 모델 확장 (DESIGN 5.1 표). 모듈 시험에 필요한 만큼만 더한다.

지금 있는 것 (WP0):
- 게임 메모리 초기값 표 `game_memory()` / `install_game_memory()` — 로컬 플레이어 번호, 플레이어 형, 시작 CP.
- Switch 조건(condtype 11) / SetSwitch 액션(acttype 13). 상태는 스위치 표 메모리(`SWITCH_TABLE`)에 비트로 둔다.

더한 것 (WP10, 아래 "유닛 모델" 절 — bullet·plot·spawn·pool 이 재사용한다):
- CUnit 표 스텁(0x59CCA8, 336B × 1700) + 빈 칸 목록(머리 0x628438) + 활성 목록(머리 0x628430).
  상태는 전부 에뮬레이터 메모리에 있어 `Machine.snapshot()`/`restore()`·`Suite.run(fresh=True)` 로 함께 되돌아간다.
- CreateUnit(44)·CreateUnitWithProperties(11) 기록과 생성(빈 칸 목록 머리를 가져가 0x628438 을 다음 칸으로),
  **실패 주입**(`fail_next(n)`, `fail_when(pred)` — 실패하면 0x628438 그대로, CUnit 쓰기 없음).
- KillUnit(22)·KillUnitAt(23)·RemoveUnit(24)·RemoveUnitAt(25): 대상 유닛을 "죽는 중"(주문 0, HP 0)으로 표시,
  `process_deaths()` 가 게임 프레임 처리처럼 활성 목록에서 빼고 빈 칸 목록에 돌려준다.
- Order(46) 기록(유닛·주인·상자·명령·목표). 유닛은 움직이지 않는다.
- 로케이션은 MRGN 메모리(0x58DC60, 20B)의 사각형을 **읽기만** 한다(생성 위치 = 중심, KillUnitAt 범위).
- 설치: `install_units(machine, **opts)` 또는 `install(machine, units={...})` (harness: `Suite(memory={"units": {...}})`).
  모델 객체는 `machine.unit_model` / `unit_model(machine)`. API 는 `UnitModel` docstring.

더한 것 (WP11, 아래 "글·소리 기록" 절 — pool 의 넘침·미등록 문구 시험):
- DisplayText(9)·PlayWAV(8) 기록(그때의 CP 포함)과 맵 문자열 표 해독(STR/STRx). `install_text(machine)` 또는
  `install(machine, text=True)` (harness: `Suite(memory={"text": True})`). 모델 객체는 `machine.text_model` /
  `text_model(machine)`. 표시 대상 판정·줄 위치·표시 시간은 흉내 내지 않는다(기록만).

나중에 더할 자리 (담당 WP):
- DisplayText 캡처의 화면 모델(대상 판정·13줄·색) — WP6/WP17 (지금은 WP11 의 기록판)
- MoveLocation / MRGN 쓰기 모델 — WP7/WP9/WP12 (지금은 `UnitModel.set_location` 으로 메모리에 직접 쓴다)
- MoveUnit·GiveUnits, 특수 유닛 분류(230 Men·231 Buildings·232 Factories) — spawn(WP12) 시험에는 필요 없어 미룸
  (WP12 가 더한 것: KillUnit/RemoveUnit 의 Force1~4(18~21) 대상, 대량 생성 속도(`_free_at_least`).
  Order 의 상자·목표 사각형 기록과 명령받은 유닛 목록·이동은 `testing/locmodel.py` 의 `orders`)
- 플레이어 목록 여러 개, before/afterTriggerExec 순서, 수신 펄스 주입 — WP13/WP18
- 채팅 버퍼(0x640B60) 바이트 — WP17

확장 방법: `Machine.cond_handlers[condtype] = fn(machine, fields) -> bool`,
`Machine.act_handlers[acttype] = fn(machine, fields)`. fields 는 emu.py `_cond`/`_act` 주석의 튜플 순서.
공용 파일이므로 한 배치에서 한 WP 만 고친다(DESIGN 6.2).
"""

from collections import namedtuple

__all__ = [
    "COND_SWITCH",
    "ACT_SET_SWITCH",
    "LOCAL_PLAYER_ADDR",
    "PLAYER_TABLE",
    "PLAYER_TYPE",
    "SWITCH_TABLE",
    "game_memory",
    "install",
    "install_game_memory",
    "install_switches",
    "read_switch",
    "write_switch",
    # WP10 유닛 모델
    "ACT_CREATE_UNIT",
    "ACT_CREATE_UNIT_PROPS",
    "ACT_KILL_UNIT",
    "ACT_KILL_UNIT_AT",
    "ACT_ORDER",
    "ACT_REMOVE_UNIT",
    "ACT_REMOVE_UNIT_AT",
    "CU",
    "CreateRecord",
    "DEFAULT_SUBUNITS",
    "FIRST_UNIT",
    "FIRST_UNUSED",
    "KillRecord",
    "LOC_ANYWHERE",
    "MRGN_SIZE",
    "MRGN_TABLE",
    "OrderRecord",
    "UNIT_COUNT",
    "UNIT_EPD0",
    "UNIT_SIZE",
    "UNIT_TABLE",
    "UnitModel",
    "install_units",
    "unit_model",
    # WP11 글·소리 기록
    "ACT_DISPLAY_TEXT",
    "ACT_PLAY_WAV",
    "TextModel",
    "TextRecord",
    "install_text",
    "string_table",
    "text_model",
]

# --- 주소 (SC 1.16.1 / SC:R 호환 EUD 주소) ---
LOCAL_PLAYER_ADDR = 0x512684  # 로컬 플레이어 번호 (dword). 클라이언트마다 다르다 → 로컬 값
PLAYER_TABLE = 0x57EEE0  # 플레이어 구조체 36B × 12: +0 id, +4 storm id, +8 형(byte), +9 종족, +10 세력, +11 이름(25)
PLAYER_STRUCT = 36
CP_ADDR = 0x6509B0
# 스위치 상태 256비트(32바이트). MRGN 표(0x58DC60, eudplib locf.py 가 쓰는 주소) 바로 앞 — EUD 주소표 기준, 인게임 미확인
SWITCH_TABLE = 0x58DC40

# 플레이어 형(구조체 +8 바이트). 사람 = 2 (DPS framework.Enable_HumanCheck 가 이 값으로 판정)
PLAYER_TYPE = {
    "inactive": 0,
    "computer": 1,
    "human": 2,
    "rescue": 3,
    "unused": 4,
    "computer_open": 5,
    "open": 6,
    "neutral": 7,
    "closed": 8,
}

COND_SWITCH = 11
ACT_SET_SWITCH = 13

# SetSwitch amount 값 (eudplib constenc.SwitchActionDict), Switch 조건 비교 값 (SwitchStateDict)
_SW_SET, _SW_CLEAR, _SW_TOGGLE, _SW_RANDOM = 4, 5, 6, 11
_ST_SET, _ST_CLEARED = 2, 3


def game_memory(local_player=0, players=("human",), cp=0, races=None, forces=None):
    """게임 시작 직후 메모리 초기값 표를 만든다.

    인자: local_player(이 클라이언트의 플레이어 번호), players(P1 부터의 형 이름 목록, 나머지 8명까지는 inactive),
          cp(주 루프 시작 때 CP), races/forces(선택: 플레이어별 종족·세력 바이트)
    반환: {주소: 값 또는 bytes} — `Machine.init_mem` 에 넣는다
    """
    table = {LOCAL_PLAYER_ADDR: local_player & 0xFFFFFFFF, CP_ADDR: cp & 0xFFFFFFFF}
    kinds = list(players) + ["inactive"] * (8 - len(players))
    for i in range(12):
        base = PLAYER_TABLE + PLAYER_STRUCT * i
        kind = kinds[i] if i < 8 else "inactive"
        ptype = PLAYER_TYPE[kind] if isinstance(kind, str) else int(kind)
        race = races[i] if races and i < len(races) else 0
        force = forces[i] if forces and i < len(forces) else 0
        table[base] = i
        table[base + 4] = i if ptype == PLAYER_TYPE["human"] else 0xFFFFFFFF
        table[base + 8] = bytes([ptype & 0xFF, race & 0xFF, force & 0xFF])
    return table


def install_game_memory(machine, **kw):
    """`game_memory(**kw)` 를 machine 에 쓴다."""
    machine.init_mem(game_memory(**kw))


# --- 스위치 ---


def read_switch(machine, sw):
    """스위치 sw(0~255)가 켜져 있으면 True."""
    a = SWITCH_TABLE + 4 * (sw >> 5)
    return bool(machine.dw(a) >> (sw & 31) & 1)


def write_switch(machine, sw, on):
    a = SWITCH_TABLE + 4 * (sw >> 5)
    bit = 1 << (sw & 31)
    v = machine.dw(a)
    machine.setdw(a, (v | bit) if on else (v & ~bit))


def _cond_switch(machine, fields):
    # fields = (locid, player, amount, unit, comparison, condtype, restype, flags, eudx)
    state, sw = fields[4], fields[6]
    on = read_switch(machine, sw)
    if state == _ST_SET:
        return on
    if state == _ST_CLEARED:
        return not on
    raise RuntimeError("Switch 조건의 상태 값 %d" % state)


def _act_set_switch(machine, fields):
    # fields = (locid, strid, wavid, time, player1, player2, unit, acttype, amount, flags, eudx)
    sw, mode = fields[5] & 0xFF, fields[8]
    if mode == _SW_SET:
        write_switch(machine, sw, True)
    elif mode == _SW_CLEAR:
        write_switch(machine, sw, False)
    elif mode == _SW_TOGGLE:
        write_switch(machine, sw, not read_switch(machine, sw))
    elif mode == _SW_RANDOM:
        write_switch(machine, sw, machine.rng.random() < 0.5)  # 결정적 난수 (Machine.rng)
    else:
        raise RuntimeError("SetSwitch 의 상태 값 %d" % mode)


def install_switches(machine):
    """Switch 조건·SetSwitch 액션 처리기를 machine 에 끼운다."""
    machine.cond_handlers[COND_SWITCH] = _cond_switch
    machine.act_handlers[ACT_SET_SWITCH] = _act_set_switch


def install(machine, units=None, text=None, **memory_kw):
    """WP0 모델 전부: 게임 메모리 초기값 + 스위치. `units` 를 주면 유닛 모델도 끼운다(WP10).

    인자: units(None = 유닛 모델 없음(WP0 동작 그대로), True 또는 dict = `install_units(machine, **dict)`),
          text(None = 글 기록 없음, True 또는 dict = `install_text(machine, **dict)` — WP11),
          memory_kw(`game_memory` 인자)
    """
    install_game_memory(machine, **memory_kw)
    install_switches(machine)
    if units is not None and units is not False:
        install_units(machine, **(units if isinstance(units, dict) else {}))
    if text is not None and text is not False:
        install_text(machine, **(text if isinstance(text, dict) else {}))


# =============================================================================================
# 유닛 모델 (WP10): CUnit 표 스텁, 빈 칸 목록(0x628438), CreateUnit/KillUnit/RemoveUnit/Order
# =============================================================================================
#
# 모델 가정 (인게임 미확인 항목은 docs/INGAME_CHECKLIST.md 로 — WP10 조각 ingame.md):
# - 빈 칸 목록·활성 목록은 CUnit +0x00(prev)·+0x04(next) 로 이어진 목록이다(eudplib EUDLoopUnit·
#   EUDLoopNewUnit·_UniqueIdentifier._init 이 +0x04 로 따라간다). 처음 빈 칸 목록은 0,1,…,1699 순서.
# - 생성: 빈 칸 목록 머리(0x628438)를 가져가고 머리를 그 칸의 next 로 바꾼다. 새 유닛은 활성 목록의
#   **두 번째 자리**에 들어간다(목록이 비었으면 머리) — EUDLoopNewUnit 의 allowance=2 가 전제하는 동작.
#   `insert="head"` 로 바꿀 수 있다.
# - 고유 바이트 +0xA5 는 그 칸에 유닛이 생길 때마다 1 늘어난다(8비트 wrap).
# - 서브유닛(터렛)이 있는 유닛은 본체 칸을 먼저, 터렛 칸을 다음에 가져간다(`DEFAULT_SUBUNITS`).
#   두 칸이 없으면 그 유닛은 만들지 않는다.
# - 죽음: KillUnit 류는 주문(+0x4D)·HP(+0x08)를 0 으로만 만든다("죽는 중"). 트리거 뒤 게임 프레임 처리에
#   해당하는 `process_deaths()` 가 활성 목록에서 빼고 스프라이트(+0x0C)를 0 으로 하고 빈 칸 목록 **끝**에 돌려준다
#   (`free_to="front"` 로 바꿀 수 있다). CUnit 의 다른 칸(주인·종류·고유 바이트 …)은 그대로 남는다.
# - 생성 위치 = 로케이션 사각형 중심((L+R)//2, (T+B)//2). 자리 찾기(겹침 회피)는 없다.
# - CreateUnit 수량 0 은 1 로 본다.

UNIT_TABLE = 0x59CCA8  # CUnit 표 시작 (유닛 i = UNIT_TABLE + UNIT_SIZE·i)
UNIT_SIZE = 336
UNIT_COUNT = 1700
UNIT_EPD0 = 19025  # EPD(UNIT_TABLE) — 유닛 i 의 EPD = 19025 + 84·i
FIRST_UNIT = 0x628430  # 활성(보이는) 유닛 목록 머리
FIRST_UNUSED = 0x628438  # 다음에 쓸 빈 유닛 칸 = 빈 칸 목록 머리 (없으면 0)
MRGN_TABLE = 0x58DC60  # 로케이션 표 (eudplib locf.py 와 같은 주소), 로케이션 번호 n(1-based) → +20·(n−1)
MRGN_SIZE = 20
LOC_ANYWHERE = 64
FAKE_SPRITE = 0x629D98  # 살아 있는 유닛의 +0x0C 에 넣는 가짜 스프라이트 주소(0 이 아니기만 하면 된다)

ACT_CREATE_UNIT_PROPS = 11
ACT_KILL_UNIT = 22
ACT_KILL_UNIT_AT = 23
ACT_REMOVE_UNIT = 24
ACT_REMOVE_UNIT_AT = 25
ACT_CREATE_UNIT = 44
ACT_ORDER = 46

# CUnit 오프셋 (이름은 eudplib scdata.CUnit 과 같게)
CU = {
    "prev": (0x00, 4),
    "next": (0x04, 4),
    "hitPoints": (0x08, 4),  # 8.8 고정소수점 (HP × 256)
    "sprite": (0x0C, 4),
    "posX": (0x28, 2),
    "posY": (0x2A, 2),
    "playerID": (0x4C, 1),
    "orderID": (0x4D, 1),
    "unitType": (0x64, 2),
    "subUnit": (0x70, 4),
    "uniquenessIdentifier": (0xA5, 1),
    "status": (0xDC, 4),
}
ORDER_DIE = 0
ORDER_ON_CREATE = 3  # 모델 값(PlayerGuard). 0 이 아니기만 하면 된다
STATUS_COMPLETED = 1
UNIT_ANY = 229

# 본체 → 터렛 (units.dat subunit1, 바닐라)
DEFAULT_SUBUNITS = {
    3: 4,  # Terran Goliath → Goliath Turret
    5: 6,  # Siege Tank (Tank Mode) → Tank Turret
    17: 18,  # Alan Schezar → Alan Schezar Turret
    23: 24,  # Edmund Duke (Tank Mode) → Turret
    25: 26,  # Edmund Duke (Siege Mode) → Turret
    30: 31,  # Siege Tank (Siege Mode) → Turret
}

CreateRecord = namedtuple(
    "CreateRecord", "action count unit loc player props ok indices subs cycle"
)
CreateRecord.__doc__ = """CreateUnit(WithProperties) 한 번의 기록.

action: "CreateUnit" | "CreateUnitWithProperties", count: 수량(0 → 1), unit: 유닛 종류, loc: 로케이션 번호(1-based),
player: 해석한 플레이어(CurrentPlayer → CP 값), props: UPRP 번호(WithProperties 만, 아니면 None),
ok: 한 마리라도 만들었나, indices: 만든 본체 칸 번호 목록, subs: 터렛 칸 번호 목록, cycle: 몇 번째 사이클(0부터)
"""
KillRecord = namedtuple("KillRecord", "action unit player loc count indices cycle")
KillRecord.__doc__ = """KillUnit/KillUnitAt/RemoveUnit/RemoveUnitAt 한 번의 기록 (loc·count 는 *At 만, 아니면 None)."""
OrderRecord = namedtuple("OrderRecord", "unit player loc order dest cycle")
OrderRecord.__doc__ = """Order 한 번의 기록 (loc = 시작 로케이션, dest = 목표 로케이션, 1-based)."""


def _s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


class UnitModel:
    """CUnit 표 스텁 + 빈 칸 목록 + 유닛 액션 모델. `install_units` 가 만들어 `machine.unit_model` 에 둔다.

    인자: machine, free(처음 빈 칸 순서 목록, 기본 0..1699), insert("second" | "head": 새 유닛의 활성 목록 자리),
          free_to("back" | "front": 죽은 칸을 빈 칸 목록 어디에 돌려줄지), subunits({본체: 터렛}, 기본 DEFAULT_SUBUNITS,
          `{}` 면 터렛 없음), hp({유닛 종류: HP}, 기본 모든 유닛 100), order_on_create(생성 때 주문 값)

    칸·주소 도우미 (정적): `ptr(i)`, `epd(i)`, `index_of(ptr 또는 epd)`
    필드: `get(i, 이름 또는 오프셋, size=4)`, `set(i, 이름 또는 오프셋, 값, size=4)`,
          `unit_type(i)`, `owner(i)`, `order(i)`, `hp(i)`(HP×256 원값), `pos(i)` → (x, y), `set_pos(i, x, y)`,
          `uniq(i)`, `sub_unit(i)`, `alive(i)`(스프라이트 ≠ 0 이고 주문 ≠ 0), `dying(i)`
    목록: `next_free()`(0x628438 의 칸 번호, 없으면 None), `free_list()`, `active_list()`, `set_free(목록)`,
          `fill(n=None)`(빈 칸 n 개를 가짜 유닛으로 채움, None = 전부 → 0x628438 = 0)
    유닛: `spawn(unit, player, x=0, y=0, index=None, hp=None, order=None)` → 칸 번호 (기록 없이 바로 놓기),
          `kill(i)`, `remove(i)`(죽는 중 표시), `process_deaths()` → 처리한 칸 목록,
          `units(player=None, unit=None, alive=True)` → 활성 목록 순서의 칸 번호
    로케이션: `set_location(n, l, t, r, b)`(MRGN 메모리에 쓰기), `loc_rect(n)`, `loc_center(n)`
    실패 주입: `fail_next(n=1)`(다음 n 번의 CreateUnit 액션 실패), `fail_when(pred)`(pred(record) 가 참이면 실패,
          record 는 ok=False 인 CreateRecord), `clear_failures()`
    기록: `created`(CreateRecord 목록), `killed`(KillRecord), `orders`(OrderRecord), `clear_log()`
    주의: 기록·실패 주입 설정은 파이썬 쪽에 있어 `Machine.restore()` 로 되돌아가지 않는다(메모리 상태만 되돌아간다).
    """

    def __init__(self, machine, free=None, insert="second", free_to="back", subunits=None, hp=None,
                 order_on_create=ORDER_ON_CREATE):
        if insert not in ("second", "head"):
            raise ValueError("insert 는 'second' 또는 'head'")
        if free_to not in ("back", "front"):
            raise ValueError("free_to 는 'back' 또는 'front'")
        self.m = machine
        self.insert = insert
        self.free_to = free_to
        self.subunits = dict(DEFAULT_SUBUNITS if subunits is None else subunits)
        self.hp_table = dict(hp or {})
        self.order_on_create = order_on_create
        self.created = []
        self.killed = []
        self.orders = []
        self._fail_count = 0
        self._fail_pred = None
        self.set_free(range(UNIT_COUNT) if free is None else free)
        machine.setdw(FIRST_UNIT, 0)

    # --- 주소 ---
    @staticmethod
    def ptr(i):
        return UNIT_TABLE + UNIT_SIZE * i

    @staticmethod
    def epd(i):
        return UNIT_EPD0 + 84 * i

    @staticmethod
    def index_of(v):
        """포인터 또는 EPD → 칸 번호 (틀린 값이면 ValueError)."""
        if v >= UNIT_TABLE:
            q, r = divmod(v - UNIT_TABLE, UNIT_SIZE)
        else:
            q, r = divmod(v - UNIT_EPD0, 84)
        if r or not 0 <= q < UNIT_COUNT:
            raise ValueError("유닛 포인터/EPD 가 아닙니다: 0x%X" % v)
        return q

    # --- 필드 ---
    def _field(self, name, size):
        if isinstance(name, str):
            return CU[name]
        return name, size

    def get(self, i, name, size=4):
        off, size = self._field(name, size)
        a = self.ptr(i) + off
        if size == 4:
            return self.m.dw(a)
        v = 0
        for k in range(size):
            v |= self.m.db(a + k) << (8 * k)
        return v

    def set(self, i, name, value, size=4):
        off, size = self._field(name, size)
        a = self.ptr(i) + off
        if size == 4:
            self.m.setdw(a, value)
            return
        for k in range(size):
            self.m.setdb(a + k, (value >> (8 * k)) & 0xFF)

    def unit_type(self, i):
        return self.get(i, "unitType")

    def owner(self, i):
        return self.get(i, "playerID")

    def order(self, i):
        return self.get(i, "orderID")

    def hp(self, i):
        return self.get(i, "hitPoints")

    def pos(self, i):
        return self.get(i, "posX"), self.get(i, "posY")

    def set_pos(self, i, x, y):
        self.set(i, "posX", x)
        self.set(i, "posY", y)

    def uniq(self, i):
        return self.get(i, "uniquenessIdentifier")

    def sub_unit(self, i):
        return self.get(i, "subUnit")

    def alive(self, i):
        return self.get(i, "sprite") != 0 and self.order(i) != ORDER_DIE

    def dying(self, i):
        return self.get(i, "sprite") != 0 and self.order(i) == ORDER_DIE

    # --- 연결 목록 (메모리) ---
    def _walk(self, head_addr):
        out = []
        p = self.m.dw(head_addr)
        while p:
            out.append(self.index_of(p))
            if len(out) > UNIT_COUNT:
                raise RuntimeError("유닛 목록이 순환합니다 (머리 0x%X)" % head_addr)
            p = self.m.dw(p + 4)
        return out

    def free_list(self):
        return self._walk(FIRST_UNUSED)

    def active_list(self):
        return self._walk(FIRST_UNIT)

    def next_free(self):
        p = self.m.dw(FIRST_UNUSED)
        return self.index_of(p) if p else None

    def set_free(self, indices):
        """빈 칸 목록을 이 순서로 다시 만든다(목록에 없는 칸의 링크는 건드리지 않는다)."""
        idx = list(indices)
        prev = 0
        for k, i in enumerate(idx):
            p = self.ptr(i)
            self.m.setdw(p, prev)
            self.m.setdw(p + 4, self.ptr(idx[k + 1]) if k + 1 < len(idx) else 0)
            prev = p
        self.m.setdw(FIRST_UNUSED, self.ptr(idx[0]) if idx else 0)

    def _unlink(self, head_addr, p):
        prev, nxt = self.m.dw(p), self.m.dw(p + 4)
        if prev:
            self.m.setdw(prev + 4, nxt)
        else:
            if self.m.dw(head_addr) != p:
                raise RuntimeError("칸 0x%X 이 목록(머리 0x%X)에 없습니다" % (p, head_addr))
            self.m.setdw(head_addr, nxt)
        if nxt:
            self.m.setdw(nxt, prev)
        self.m.setdw(p, 0)
        self.m.setdw(p + 4, 0)

    def _take_free(self, index=None):
        if index is None:
            p = self.m.dw(FIRST_UNUSED)
            if not p:
                return None
        else:
            p = self.ptr(index)
            if index not in self.free_list():
                raise RuntimeError("칸 %d 는 빈 칸이 아닙니다" % index)
        self._unlink(FIRST_UNUSED, p)
        return self.index_of(p)

    def _insert_active(self, i):
        p = self.ptr(i)
        head = self.m.dw(FIRST_UNIT)
        if head == 0 or self.insert == "head":
            self.m.setdw(p, 0)
            self.m.setdw(p + 4, head)
            if head:
                self.m.setdw(head, p)
            self.m.setdw(FIRST_UNIT, p)
            return
        nxt = self.m.dw(head + 4)
        self.m.setdw(p, head)
        self.m.setdw(p + 4, nxt)
        self.m.setdw(head + 4, p)
        if nxt:
            self.m.setdw(nxt, p)

    def _give_back(self, i):
        p = self.ptr(i)
        head = self.m.dw(FIRST_UNUSED)
        if self.free_to == "front" or head == 0:
            self.m.setdw(p, 0)
            self.m.setdw(p + 4, head)
            if head:
                self.m.setdw(head, p)
            self.m.setdw(FIRST_UNUSED, p)
            return
        tail = head
        while self.m.dw(tail + 4):
            tail = self.m.dw(tail + 4)
        self.m.setdw(tail + 4, p)
        self.m.setdw(p, tail)
        self.m.setdw(p + 4, 0)

    # --- 유닛 ---
    def _init_unit(self, i, unit, player, x, y, hp, order):
        self.set(i, "hitPoints", ((self.hp_table.get(unit, 100) if hp is None else hp) << 8) & 0xFFFFFFFF)
        self.set(i, "sprite", FAKE_SPRITE + 36 * i)
        self.set_pos(i, x & 0xFFFF, y & 0xFFFF)
        self.set(i, "playerID", player)
        self.set(i, "orderID", self.order_on_create if order is None else order)
        self.set(i, "unitType", unit)
        self.set(i, "uniquenessIdentifier", (self.uniq(i) + 1) & 0xFF)
        self.set(i, "status", self.get(i, "status") | STATUS_COMPLETED)
        self.set(i, "subUnit", 0)

    def _free_at_least(self, n):
        """빈 칸 목록이 n 칸 이상인가 (앞에서 n 칸만 따라간다 — WP12: 대량 생성 시험의 속도)."""
        p = self.m.dw(FIRST_UNUSED)
        k = 0
        while p and k < n:
            k += 1
            p = self.m.dw(p + 4)
        return k >= n

    def _make(self, unit, player, x, y, index=None, hp=None, order=None):
        """칸을 가져와 유닛을 놓는다. 터렛 칸이 모자라면 None (아무것도 바꾸지 않음)."""
        sub = self.subunits.get(unit)
        if index is not None and index not in self.free_list():
            raise RuntimeError("칸 %d 는 빈 칸이 아닙니다" % index)
        if not self._free_at_least(2 if sub is not None else 1):
            return None
        i = self._take_free(index)
        self._init_unit(i, unit, player, x, y, hp, order)
        self._insert_active(i)
        s = None
        if sub is not None:
            s = self._take_free()
            self._init_unit(s, sub, player, x, y, hp, order)
            self.set(i, "subUnit", self.ptr(s))
            self.set(s, "subUnit", self.ptr(i))
            self._insert_active(s)
        return i, s

    def spawn(self, unit, player, x=0, y=0, index=None, hp=None, order=None):
        """기록 없이 유닛 하나를 놓는다(미리 놓인 유닛·시험 준비용). 반환: 본체 칸 번호. 칸이 없으면 RuntimeError."""
        r = self._make(unit, player, x, y, index, hp, order)
        if r is None:
            raise RuntimeError("빈 칸이 없습니다")
        return r[0]

    def fill(self, n=None):
        """빈 칸 n 개(None = 전부)를 가짜 유닛(종류 0, P12, 활성 목록 밖)으로 채운다. 반환: 채운 칸 목록."""
        out = []
        while n is None or len(out) < n:
            i = self._take_free()
            if i is None:
                break
            self._init_unit(i, 0, 11, 0, 0, 0, None)
            out.append(i)
        return out

    def kill(self, i):
        """칸 i 의 유닛을 죽는 중으로 만든다(주문 0, HP 0). 목록 처리는 `process_deaths()`."""
        self.set(i, "orderID", ORDER_DIE)
        self.set(i, "hitPoints", 0)

    remove = kill

    def process_deaths(self):
        """죽는 중인 유닛을 활성 목록에서 빼고 스프라이트를 0 으로 하고 빈 칸 목록에 돌려준다. 반환: 칸 목록."""
        done = []
        for i in self.active_list():
            if self.order(i) == ORDER_DIE:
                self._unlink(FIRST_UNIT, self.ptr(i))
                self.set(i, "sprite", 0)
                self._give_back(i)
                done.append(i)
        return done

    def units(self, player=None, unit=None, alive=True):
        out = []
        for i in self.active_list():
            if alive and not self.alive(i):
                continue
            if player is not None and self.owner(i) != player:
                continue
            if unit is not None and unit != UNIT_ANY and self.unit_type(i) != unit:
                continue
            out.append(i)
        return out

    # --- 로케이션 (MRGN 읽기) ---
    def set_location(self, n, left, top, right, bottom):
        a = MRGN_TABLE + MRGN_SIZE * (n - 1)
        for k, v in enumerate((left, top, right, bottom)):
            self.m.setdw(a + 4 * k, v)

    def loc_rect(self, n):
        a = MRGN_TABLE + MRGN_SIZE * (n - 1)
        return tuple(_s32(self.m.dw(a + 4 * k)) for k in range(4))

    def loc_center(self, n):
        left, top, right, bottom = self.loc_rect(n)
        return (left + right) // 2, (top + bottom) // 2

    def _in_loc(self, i, n):
        if n == LOC_ANYWHERE:
            return True
        left, top, right, bottom = self.loc_rect(n)
        x, y = self.pos(i)
        return left <= x <= right and top <= y <= bottom

    # --- 실패 주입·기록 ---
    def fail_next(self, n=1):
        self._fail_count = n

    def fail_when(self, pred):
        self._fail_pred = pred

    def clear_failures(self):
        self._fail_count = 0
        self._fail_pred = None

    def clear_log(self):
        del self.created[:]
        del self.killed[:]
        del self.orders[:]

    def _cycle(self):
        return len(self.m.ends)

    # --- 액션 처리 ---
    def _player(self, p, allow_all=False):
        if p == 13:
            return [self.m.dw(CP_ADDR)]
        if 0 <= p <= 11:
            return [p]
        if allow_all and p == 17:
            return list(range(12))
        if allow_all and 18 <= p <= 21:
            # Force1~4 (WP12): 플레이어 구조체 +10 세력 바이트(0부터)가 p − 18 인 P1~P8
            return [i for i in range(8) if self.m.db(PLAYER_TABLE + PLAYER_STRUCT * i + 10) == p - 18]
        from eudext.testing.emu import EmuError

        raise EmuError("유닛 모델: 플레이어 값 %d 는 흉내 내지 않습니다" % p)

    def on_create(self, fields):
        locid, _strid, _wav, _time, p1, p2, unit, atype, amount, _flags, _eudx = fields
        # eudplib 은 맵 시작마다 0x628438 = 0 으로 두고 CreateUnit(…, AllPlayers) 를 일부러 실패시킨다
        # (string/locale.py _detect_locale → f_raise_CCMU). 빈 칸이 없으면 플레이어를 해석하지 않고 실패로 기록한다.
        player = self.m.dw(CP_ADDR) if p1 == 13 else p1
        count = amount or 1
        action = "CreateUnit" if atype == ACT_CREATE_UNIT else "CreateUnitWithProperties"
        rec = CreateRecord(action, count, unit, locid, player, p2 if atype == ACT_CREATE_UNIT_PROPS else None,
                           False, (), (), self._cycle())
        fail = False
        if self.m.dw(FIRST_UNUSED) == 0:
            fail = True
        elif self._fail_count > 0:
            self._fail_count -= 1
            fail = True
        elif self._fail_pred is not None and self._fail_pred(rec):
            fail = True
        made, subs = [], []
        if not fail:
            (player,) = self._player(p1)
            x, y = self.loc_center(locid)
            for _ in range(count):
                r = self._make(unit, player, x, y)
                if r is None:
                    break
                made.append(r[0])
                if r[1] is not None:
                    subs.append(r[1])
        self.created.append(rec._replace(ok=bool(made), indices=tuple(made), subs=tuple(subs)))

    def on_kill(self, fields):
        locid, _strid, _wav, _time, p1, _p2, unit, atype, amount, _flags, _eudx = fields
        at = atype in (ACT_KILL_UNIT_AT, ACT_REMOVE_UNIT_AT)
        if unit > UNIT_ANY:
            from eudext.testing.emu import EmuError

            raise EmuError("유닛 모델: 유닛 분류 %d 는 흉내 내지 않습니다" % unit)
        players = self._player(p1, allow_all=True)
        limit = (amount or None) if at else None
        hit = []
        for i in self.active_list():
            if limit is not None and len(hit) >= limit:
                break
            if not self.alive(i) or self.owner(i) not in players:
                continue
            if unit != UNIT_ANY and self.unit_type(i) != unit:
                continue
            if at and not self._in_loc(i, locid):
                continue
            hit.append(i)
        for i in hit:
            self.kill(i)
        name = {ACT_KILL_UNIT: "KillUnit", ACT_KILL_UNIT_AT: "KillUnitAt", ACT_REMOVE_UNIT: "RemoveUnit",
                ACT_REMOVE_UNIT_AT: "RemoveUnitAt"}[atype]
        self.killed.append(KillRecord(name, unit, players[0] if len(players) == 1 else p1,
                                      locid if at else None, amount if at else None, tuple(hit), self._cycle()))

    def on_order(self, fields):
        locid, _strid, _wav, _time, p1, p2, unit, _atype, amount, _flags, _eudx = fields
        (player,) = self._player(p1, allow_all=False) if p1 != 17 else (17,)
        self.orders.append(OrderRecord(unit, player, locid, amount, p2, self._cycle()))


def unit_model(machine):
    """machine 에 끼운 UnitModel (없으면 None)."""
    return getattr(machine, "unit_model", None)


def install_units(machine, **opts):
    """유닛 모델을 machine 에 끼운다. 인자는 `UnitModel` 과 같다. 반환: UnitModel (`machine.unit_model` 에도 둔다).

    처리기: CreateUnit(44)·CreateUnitWithProperties(11)·KillUnit(22)·KillUnitAt(23)·RemoveUnit(24)·
    RemoveUnitAt(25)·Order(46). 메모리: 빈 칸 목록·활성 목록 머리(0x628438·0x628430)와 CUnit 링크.
    """
    model = UnitModel(machine, **opts)
    machine.unit_model = model
    machine.act_handlers[ACT_CREATE_UNIT] = lambda m, f: m.unit_model.on_create(f)
    machine.act_handlers[ACT_CREATE_UNIT_PROPS] = lambda m, f: m.unit_model.on_create(f)
    for a in (ACT_KILL_UNIT, ACT_KILL_UNIT_AT, ACT_REMOVE_UNIT, ACT_REMOVE_UNIT_AT):
        machine.act_handlers[a] = lambda m, f: m.unit_model.on_kill(f)
    machine.act_handlers[ACT_ORDER] = lambda m, f: m.unit_model.on_order(f)
    return model


# =============================================================================================
# 글·소리 기록 (WP11): DisplayText(9)·PlayWAV(8) — 기록만, 화면 모델은 WP6/WP17
# =============================================================================================

ACT_PLAY_WAV = 8
ACT_DISPLAY_TEXT = 9

TextRecord = namedtuple("TextRecord", "kind cp strid text cycle")
TextRecord.__doc__ = """DisplayText/PlayWAV 한 번의 기록.

kind: "text" | "wav", cp: 실행 때 CP 값(대상 플레이어), strid: 문자열 번호(DisplayText 는 strid, PlayWAV 는 wavid),
text: 해독한 문자열(맵 문자열 표에 없으면 None), cycle: 몇 번째 사이클(0부터)
"""


def string_table():
    """지금 불러온 맵 chk 의 문자열 표를 {번호(1부터): 바이트} 로 읽는다 (STR·STRx 둘 다).

    에뮬레이터 빌드 뒤(`Program.build`) 에 부르면 그 빌드가 더한 문자열까지 들어 있다.
    """
    import struct

    from eudext import _compat

    sec = _compat.chk_string_section()
    wide = _compat.chk_string_section_name() == "STRx"
    fmt, size = ("<I", 4) if wide else ("<H", 2)
    if len(sec) < size:
        return {}
    n = struct.unpack_from(fmt, sec, 0)[0]
    out = {}
    for i in range(1, n + 1):
        if size * (i + 1) > len(sec):
            break
        off = struct.unpack_from(fmt, sec, size * i)[0]
        if off >= len(sec):
            continue
        end = sec.find(b"\0", off)
        out[i] = sec[off:end if end >= 0 else len(sec)]
    return out


class TextModel:
    """DisplayText·PlayWAV 기록 (`install_text` 가 만든다).

    - `records`: TextRecord 목록 (사이클을 넘어 쌓인다 — `clear()` 로 비움. `Suite.run(fresh=True)` 로 안 비워진다)
    - `texts(cp=None)`: 표시한 문자열 목록(해독한 str), `wavs(cp=None)`: 소리 파일 이름 목록
    - 문자열 표는 설치할 때(빌드 직후) 한 번 읽는다. 다른 빌드의 문자열 번호는 해독하지 않는다.
    """

    def __init__(self, machine, strings=None):
        self.m = machine
        self.records = []
        self.strings = string_table() if strings is None else dict(strings)

    def _decode(self, sid):
        b = self.strings.get(sid)
        return None if b is None else b.decode("utf-8", "replace")

    def _cycle(self):
        return len(self.m.ends)

    def on_display(self, fields):
        _loc, strid = fields[0], fields[1]
        self.records.append(TextRecord("text", self.m.dw(CP_ADDR), strid, self._decode(strid), self._cycle()))

    def on_wav(self, fields):
        wavid = fields[2]
        self.records.append(TextRecord("wav", self.m.dw(CP_ADDR), wavid, self._decode(wavid), self._cycle()))

    def texts(self, cp=None):
        return [r.text for r in self.records if r.kind == "text" and (cp is None or r.cp == cp)]

    def wavs(self, cp=None):
        return [r.text for r in self.records if r.kind == "wav" and (cp is None or r.cp == cp)]

    def clear(self):
        del self.records[:]


def text_model(machine):
    """machine 에 끼운 TextModel (없으면 None)."""
    return getattr(machine, "text_model", None)


def install_text(machine, strings=None):
    """글·소리 기록 모델을 machine 에 끼운다. 반환: TextModel (`machine.text_model` 에도 둔다).

    인자: strings(선택: {번호: 바이트} — 없으면 지금 불러온 맵에서 읽는다)
    처리기: DisplayText(9), PlayWAV(8). 둘 다 기록만 한다(에뮬레이터 로그에도 그대로 남는다).
    """
    model = TextModel(machine, strings)
    machine.text_model = model
    machine.act_handlers[ACT_DISPLAY_TEXT] = lambda m, f: m.text_model.on_display(f)
    machine.act_handlers[ACT_PLAY_WAV] = lambda m, f: m.text_model.on_wav(f)
    return model
