"""`bullet` 시험 (에뮬레이터 + scmodel 유닛 모델) — 정본 명세 S4 6절 기대값.

- 6.1 방향: 360→256 표, `bullet_to` 방향표, 참조 구현(`ref_bullet` + `ref_mathx`)과 무작위 차등(reverse 둘 다)
- 6.2 dat 액션: speed/time/height 표 + flingy·무기·유닛 번호 전수, 변수 set_speed/set_time/set_height,
  BulletDat 이 UE_RE `EUDEditorDat.lua` 의 (A -> B) 결과와 같은지, 금지 칸(0x656990 + 유닛 번호) 쓰기 없음
- 6.3 포인터 처리: 정상·음수 방향·슬롯 없음·생성 실패(실패 주입)·shell·y_offset·m2·CP, 생성 뒤 CUnit 칸 전부(보초값으로
  마스크 밖 비트 보존까지), 엉뚱한 메모리 쓰기 없음, 실패 뒤 분기 복구, 여러 발, recipe·reverse·remove_timer·shell·높이 조합
- 인자 검사(빌드 오류 기대), epScript 예제·인게임 확인 맵의 번역·에뮬레이션·euddraft 빌드

python tests/t_bullet.py
비용 표: python tools/cost.py tests/t_bullet.py [--append --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402

from eudplib import (  # noqa: E402
    P3,
    P8,
    CompressPayload,
    CurrentPlayer,
    DoActions,
    EUDVariable,
    LoadMap,
    SetMemory,
    SetMemoryX,
    SetTo,
    f_getcurpl,
    f_setcurpl,
)

import ref_bullet as RB  # noqa: E402
import ref_mathx as R  # noqa: E402

from eudext import _compat, bullet, mathx  # noqa: E402
from eudext import datpatch as dat  # noqa: E402
from eudext.bullet import BulletDat, BulletKind  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import BASE_MAP, emu, scmodel  # noqa: E402
from eudext.testing.harness import EDGES32, Suite, rand32  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
LOC = 26  # 기준 맵 "Location 0" (사각형 0 — 비어 있는 로케이션)
LOC27 = 27  # 기준 맵 "CLoc"
MRGN = 0x58DC60
NEXT = 0x628438
FIRST_UNIT = 0x628430
CP_ADDR = 0x6509B0
EX = os.path.join(_common.PKG, "examples")
UERE_DAT = os.path.join(_common.ROOT, "reference", "MapSource", "MSF_UE_RE", "EUDEditorDat.lua")

bullet.setup(loc=LOC)


def loc_addr(n):
    return MRGN + 20 * (n - 1)


# 시험 종류 (본문 조합이 겹치지 않게 recipe·수명·shell·y_offset·reverse·높이 칸 시프트를 섞는다)
KINDS = {
    "ue": BulletKind(),  # 208/127/106, ue_re, 수명 12, 높이 칸 시프트 0
    "ue0": BulletKind(remove_timer=0),  # 수명 칸 안 씀
    "m2": BulletKind(unit=205, weapon=126, flingy=173, recipe="m2"),  # 수명 30, 높이 시프트 8
    "mn": BulletKind(unit=206, weapon=30, flingy=174, recipe="minimal"),  # 수명 없음, 시프트 16
    "mn5": BulletKind(unit=207, recipe="minimal", remove_timer=5),  # 시프트 24
    "sh": BulletKind(unit=210, weapon=128, flingy=158, shell=204),  # 204 로 만들고 210 으로
    "shm": BulletKind(unit=210, shell=205, recipe="m2", y_offset=10, remove_timer=300),  # shell 시프트 8
    "y10": BulletKind(y_offset=10),
    "yn2": BulletKind(unit=209, recipe="minimal", y_offset=-2, remove_timer=7),
    "fw": BulletKind(reverse=False),
}
# install() 시험용 (모듈을 불러올 때 선언 = 빌드마다 시작 1회 목록에 들어간다)
KDAT = BulletKind(unit=211, weapon=129, flingy=150, shell=203,
                  dat=BulletDat(sprite=300, remove_after=77, idle_order=23, top_speed=1234))
KDAT.install()

TO_KINDS = ("ue", "fw", "shm", "mn", "sh")
AT_KINDS = ("ue", "m2", "sh", "yn2")
HV_KINDS = ("ue", "m2", "mn", "mn5", "sh", "shm")
HC_KINDS = ("ue", "m2", "mn5")


def made_unit(k):
    return k.unit if k.shell is None else k.shell


# =============================================================================================
# 파이썬 쪽 (6.1 표, 6.2 액션, 인자 검사, BulletDat 대 UE_RE)
# =============================================================================================


def decode(act):
    """SetMemory/SetMemoryX 액션 → (주소, 수정자 이름, 값, 마스크)."""
    f = act.fields
    mods = {7: "SetTo", 8: "Add", 9: "Subtract"}
    addr = (0x58A364 + 4 * (f[6] * 12 + f[4])) & M32
    mask = (f[0] & M32) if f[11] == 0x4353 else M32
    return (addr, mods.get(f[8], f[8]), f[5] & M32, mask)


def decode_all(acts):
    return [decode(a) for a in acts]


SPEC_62 = [
    ("flingy=158 speed_actions(500)", lambda: BulletKind(flingy=158).speed_actions(500),
     [SetMemory(0x6CA170, SetTo, 0xFFFFFE0B), SetMemoryX(0x6C9DB4, SetTo, 500, 0xFFFF)]),
    ("flingy=158 speed_actions(500, halt=1)", lambda: BulletKind(flingy=158).speed_actions(500, halt=1),
     [SetMemory(0x6CA170, SetTo, 0xFFFFFE0B), SetMemoryX(0x6C9DB4, SetTo, 500, 0xFFFF), SetMemory(0x6C9BA8, SetTo, 1)]),
    ("flingy=174 speed_actions(8000)", lambda: BulletKind(flingy=174).speed_actions(8000),
     [SetMemory(0x6CA1B0, SetTo, 0xFFFFE0BF), SetMemoryX(0x6C9DD4, SetTo, 8000, 0xFFFF)]),
    ("flingy=173 speed_actions(700) 가속도 윗 워드", lambda: BulletKind(flingy=173).speed_actions(700)[1:],
     [SetMemoryX(0x6C9DD0, SetTo, 700 << 16, 0xFFFF0000)]),
    ("reverse=False flingy=106 speed_actions(8000)", lambda: BulletKind(flingy=106, reverse=False).speed_actions(8000),
     [SetMemory(0x6CA0A0, SetTo, 8000), SetMemoryX(0x6C9D4C, SetTo, 8000, 0xFFFF)]),
    ("weapon=127 time_actions(32)", lambda: BulletKind(weapon=127).time_actions(32),
     [SetMemoryX(0x6570BC, SetTo, 32 << 24, 0xFF000000)]),
    ("weapon=30 time_actions(32)", lambda: BulletKind(weapon=30).time_actions(32),
     [SetMemoryX(0x65705C, SetTo, 32 << 16, 0xFF0000)]),
    ("weapon=128 time_actions(64)", lambda: BulletKind(weapon=128).time_actions(64),
     [SetMemoryX(0x6570C0, SetTo, 64, 0xFF)]),
    ("unit=208 height_actions(20)", lambda: BulletKind(unit=208).height_actions(20),
     [SetMemoryX(0x663220, SetTo, 20, 0xFF)]),
    ("unit=206 height_actions(20)", lambda: BulletKind(unit=206).height_actions(20),
     [SetMemoryX(0x66321C, SetTo, 20 << 16, 0xFF0000)]),
    ("shell=204 unit=210 height_actions(20)", lambda: BulletKind(unit=210, shell=204).height_actions(20),
     [SetMemoryX(0x66321C, SetTo, 20, 0xFF)]),
]

DIR_TABLE = [(0, 64), (1, 64), (44, 95), (45, 96), (89, 127), (90, 128), (135, 160), (180, 192), (225, 224),
             (270, 0), (315, 32), (359, 63), (360, 64)]
TO_TABLE = [  # 출발, 목표, atan2(출발 − 목표), facing, 진행
    ((100, 100), (200, 100), 180, 192, 64),
    ((100, 100), (100, 200), 270, 0, 128),
    ((100, 100), (0, 100), 0, 64, 192),
    ((100, 100), (100, 0), 90, 128, 0),
    ((100, 100), (200, 200), 226, 224, 96),
    ((100, 100), (0, 0), 46, 96, 224),
    ((100, 100), (101, 102), 244, 237, 109),
    ((2048, 1548), (2048, 2048), 270, 0, 128),
    ((0, 0), (32767, 1), 181, 192, 64),
    ((100, 100), (100, 100), 90, 128, 0),
]


def spec_checks(ck):
    # 6.1: 360 → 256 표
    for a, want in DIR_TABLE:
        ck.eq("6.1 to_dir256(%d)" % a, mathx.to_dir256(a), want)
        ck.eq("6.1 ref to_dir256(%d)" % a, R.to_dir256_tep(a), want)
    for a in range(360):
        ck.true("6.1 표 = a·32//45 + 64 (%d)" % a, R.to_dir256_tep(a) == (a * 32 // 45 + 64) % 256, "")
    for (s, t, ang, face, head) in TO_TABLE:
        ck.eq("6.1 atan2 %r→%r" % (s, t), R.atan2(R.u32(s[1] - t[1]), R.u32(s[0] - t[0])), ang)
        ck.eq("6.1 facing %r→%r" % (s, t), RB.facing_to(s[0], s[1], t[0], t[1]), face)
        ck.eq("6.1 진행 %r→%r" % (s, t), (face + 128) & 0xFF, head)
        ck.eq("6.1 heading_to_facing %r→%r" % (s, t), bullet.heading_to_facing(KINDS["ue"], head), face)
        if s != t:
            ck.eq("6.1 reverse=False %r→%r" % (s, t), RB.facing_to(s[0], s[1], t[0], t[1], reverse=False),
                  (face - 128) & 0xFF)
    rng = random.Random(61)
    for _ in range(20000):
        sx, sy, tx, ty = (rng.randrange(-16384, 16384) for _ in range(4))
        if (sx, sy) == (tx, ty):
            continue
        f1 = RB.facing_to(sx, sy, tx, ty)
        f2 = RB.facing_to(sx, sy, tx, ty, reverse=False)
        if (f1 - f2) & 0xFF != 128:
            ck.true("6.1 reverse 두 식 차이 128", False, repr((sx, sy, tx, ty, f1, f2)))
            break
    else:
        ck.true("6.1 reverse 두 식 차이 128 (2만 쌍)", True)
    # 상수 좌표 bullet_to 는 컴파일 시점에 방향을 구한다 — 참조 구현과 같은가
    bad = []
    for j in range(20000):
        sx, sy = rng.randrange(0, 32768), rng.randrange(0, 32768)
        tx, ty = sx + rng.randrange(-32767, 32768), sy + rng.randrange(-32767, 32768)
        if j % 50 == 0:
            tx, ty = sx, sy
        for rev in (True, False):
            got = bullet._const_facing(rev, sx & M32, sy & M32, tx & M32, ty & M32)
            if got != RB.facing_to(sx, sy, tx, ty, rev):
                bad.append((sx, sy, tx, ty, rev, got))
    ck.eq("6.1 상수 좌표 방향 = 참조 (2만 쌍 × 2)", bad[:5], [])
    for (sx, sy), (tx, ty), _a, face, _h in TO_TABLE:
        ck.eq("6.1 상수 좌표 표 %r→%r" % ((sx, sy), (tx, ty)), bullet._const_facing(True, sx, sy, tx, ty), face)

    # 6.2: 액션 표
    for label, fn, want in SPEC_62:
        ck.eq("6.2 " + label, decode_all(fn()), decode_all(want))
    # 전수: flingy·무기·유닛 번호마다 참조 식과 같은가
    for f in range(209):
        for v in (0, 1, 500, 8000, 0xFFFF):
            for rev in (True, False):
                got = decode_all(BulletKind(flingy=f, reverse=rev).speed_actions(v, halt=v * 3))
                if got != RB.speed_writes(f, v, rev, v * 3):
                    ck.true("6.2 speed_actions flingy %d v %d rev %r" % (f, v, rev), False, repr(got))
    ck.true("6.2 speed_actions 전수 (209 × 5 × 2)", True)
    for w in range(130):
        for t in (0, 1, 32, 255):
            if decode_all(BulletKind(weapon=w).time_actions(t)) != RB.time_writes(w, t):
                ck.true("6.2 time_actions weapon %d t %d" % (w, t), False)
    ck.true("6.2 time_actions 전수 (130 × 4)", True)
    for u in range(228):
        for h in (0, 20, 255):
            got = decode_all(BulletKind(unit=u).height_actions(h))
            got2 = decode_all(BulletKind(unit=0, shell=u).height_actions(h))
            if got != RB.height_writes(u, h) or got2 != got:
                ck.true("6.2 height_actions unit %d h %d" % (u, h), False, repr(got))
    ck.true("6.2 height_actions 전수 (228 × 3, shell 칸 포함)", True)
    # 금지 확인: 어떤 dat 액션도 0x656990 + 유닛 번호(≥ 130) 칸에 쓰지 않는다
    acts = []
    for u in (204, 205, 206, 207, 208, 209, 210, 211):
        k = BulletKind(unit=u, weapon=128, flingy=158, dat=BulletDat(attack_angle=0, remove_after=9))
        acts += k.speed_actions(9, halt=1) + k.time_actions(9) + k.height_actions(9) + k.init_actions()
    bad = [d for d in decode_all(acts) if RB.forbidden(d[0], d[3])]
    ck.eq("6.2 금지 칸 쓰기 없음 (액션 %d)" % len(acts), bad, [])
    ck.true("6.2 금지 칸 판정 자체 (UE_RE 버그 칸 0x656A5C)", RB.forbidden(0x656A5C, 0xFF), "")
    ck.true("6.2 금지 칸 판정 자체 (무기 128 attackAngle 은 정상)", not RB.forbidden(0x656A10, 0xFF), "")


UERE_NAMES = {
    ("units", "Graphics"): "flingy",
    ("units", "Elevation Level"): "elevation",
    ("units", "Ground Weapon"): "groundWeapon",
    ("units", "Special Ability Flags"): "baseProperty",
    ("units", "Comp AI Idle"): "computerIdleOrder",
    ("units", "Human AI Idle"): "humanIdleOrder",
    ("units", "Return to Idle"): "returnToIdleOrder",
    ("units", "Attack Unit"): "attackUnitOrder",
    ("units", "Attack Move"): "attackMoveOrder",
    ("weapons", "Graphics"): "flingy",
    ("weapons", "Weapon Behavior"): "behavior",
    ("weapons", "Explosion Type"): "explosionType",
    ("weapons", "Inner Splash Range"): "splashInnerRadius",
    ("weapons", "Medium Splash Range"): "splashMiddleRadius",
    ("weapons", "Outer Splash Range"): "splashOuterRadius",
    ("weapons", "Damage Amount"): "damage",
    ("weapons", "Damage Bonus"): "damageBonus",
    ("weapons", "Weapon Cooldown"): "cooldown",
    ("weapons", "Attack Angle"): "attackAngle",
    ("flingy", "Sprite"): "sprite",
    ("flingy", "Speed"): "topSpeed",
    ("flingy", "Acceleration"): "acceleration",
    ("flingy", "Halt Distance"): "haltDistance",
    ("flingy", "Turn Radius"): "turnRadius",
    ("flingy", "Movement Control"): "movementControl",
}
_UERE_LINE = re.compile(r"\{(0x[0-9A-Fa-f]+),\s*(-?\d+)\},\s*--\s*(\w+):(.+?) #(\d+) \((\d+) -> (\d+)\)")


def uere_rows():
    rows = []
    with open(UERE_DAT, encoding="utf-8") as fp:
        for line in fp:
            m = _UERE_LINE.search(line)
            if m:
                addr, _add, table, name, idx, a, b = m.groups()
                rows.append((int(addr, 16), table, name.strip(), int(idx), int(a), int(b)))
    return rows


def uere_check(ck, label, kind, wanted):
    """kind.init_actions() 를 UE_RE (A -> B) 줄의 A 값 위에 적용해 B 가 되는가. wanted = {(표, 번호)}."""
    rows = [r for r in uere_rows() if (r[1], r[3]) in wanted]
    mem = {}
    checked = []
    for addr, table, name, idx, a, b in rows:
        fname = UERE_NAMES.get((table, name))
        if fname is None:
            continue
        f = dat.field(table, fname)
        base, shift, mask = f.location(idx)
        ck.eq("%s 주소 %s:%s #%d" % (label, table, name, idx), base, addr)
        mem[base] = (mem.get(base, 0) & ~mask) | ((a << shift) & mask)
        checked.append((table, fname, idx, base, shift, mask, b))
    dat.simulate(kind.init_actions(), mem)
    for table, fname, idx, base, shift, mask, b in checked:
        ck.eq("%s %s.%s #%d = UE_RE 값" % (label, table, fname, idx), (mem[base] & mask) >> shift, b & (mask >> shift))
    ck.true("%s 비교한 칸 수 %d" % (label, len(checked)), len(checked) >= 10, "")


def dat_checks(ck):
    # UE_RE 208 / 무기 127 / flingy 106 (탄막 유닛 설정 기본값)
    uere_check(ck, "UE_RE 208", BulletKind(dat=BulletDat(sprite=344)),
               {("units", 208), ("weapons", 127), ("flingy", 106)})
    # UE_RE 210 / 무기 128 (정적 설정 — flingy 164 는 UE_RE 가 속도 등을 고치지 않았다)
    k210 = BulletKind(unit=210, weapon=128, flingy=164, dat=BulletDat(
        damage=50, splash=(256, 255, 256), idle_order=23, attack_order=23, attack_move_order=23, right_click=0,
        base_property=0x20000004,
        attack_angle=0, cooldown=None, top_speed=None, halt=None, turn=None, move_control=None))
    # 2026-09-18: 기본값이 CtrigAsm 레시피(공격이동 135·우클릭 1)로 바뀌었다 — UE_RE 210 은 23·0 이라 그대로 적어 준다
    uere_check(ck, "UE_RE 210", k210, {("units", 210), ("weapons", 128)})
    # 그 밖: shell 칸에는 지상 무기를 쓰지 않는다, flingy 없으면 오류, reverse 에 따른 최고속도
    acts = decode_all(BulletKind(unit=210, shell=204, weapon=128, flingy=158, dat=BulletDat()).init_actions())
    gw204 = dat.field("units", "groundWeapon").location(204)
    ck.true("BulletDat shell 에 groundWeapon 안 씀", not any(a[0] == gw204[0] and a[3] & gw204[2] for a in acts), "")
    el204 = dat.field("units", "elevation").location(204)
    ck.true("BulletDat shell 에 elevation 씀", any(a[0] == el204[0] and a[3] & el204[2] for a in acts), "")
    mem = dat.simulate(BulletKind(flingy=150, reverse=False, dat=BulletDat(top_speed=900)).init_actions())
    ck.eq("BulletDat reverse=False 최고속도", mem.get(dat.field("flingy", "topSpeed").location(150)[0]), 900)
    mem = dat.simulate(BulletKind(flingy=150, dat=BulletDat(top_speed=900)).init_actions())
    ck.eq("BulletDat reverse 최고속도", mem.get(dat.field("flingy", "topSpeed").location(150)[0]), M32 - 900)
    ck.raises("BulletDat flingy 없음", EudextError, lambda: BulletKind(flingy=None, dat=BulletDat()).init_actions())
    ck.raises("BulletDat 가속도 범위", EudextError, lambda: BulletKind(dat=BulletDat(top_speed=70000)).init_actions())
    ck.eq("BulletDat 가속도 따로", len(BulletKind(dat=BulletDat(top_speed=70000, accel=10)).init_actions()) > 0, True)
    ck.raises("BulletDat splash 개수", EudextError, lambda: BulletDat(splash=(1, 2)))
    ck.raises("BulletDat flyer bool", EudextError, lambda: BulletDat(flyer=1))
    ck.raises("BulletDat damage 범위", EudextError, lambda: BulletDat(damage=70000))
    ck.raises("init_actions dat 없음", EudextError, lambda: BulletKind().init_actions())
    ck.raises("install dat 없음", EudextError, lambda: BulletKind().install())
    ck.true("BulletDat repr", "sprite=300" in repr(KDAT.dat), repr(KDAT.dat))


def arg_checks(ck):
    LoadMap(BASE_MAP)  # 유닛·로케이션 이름은 맵 문자열 표로 찾는다
    k = KINDS["ue"]
    ck.eq("timer ue_re", KINDS["ue"].timer, 12)
    ck.eq("timer m2", KINDS["m2"].timer, 30)
    ck.eq("timer minimal", KINDS["mn"].timer, None)
    ck.eq("timer 0", KINDS["ue0"].timer, None)
    ck.eq("timer minimal 5", KINDS["mn5"].timer, 5)
    ck.eq("made_unit", (k.made_unit, KINDS["sh"].made_unit), (208, 204))
    ck.eq("unit 이름", BulletKind(unit="Right Pit Door").unit, 208)
    ck.true("repr 안내", "const" in repr(k), repr(k))
    for label, fn in [
        ("recipe", lambda: BulletKind(recipe="x")),
        ("unit 범위", lambda: BulletKind(unit=228)),
        ("unit 이름 없음", lambda: BulletKind(unit="없는 유닛")),
        ("weapon 범위", lambda: BulletKind(weapon=130)),
        ("flingy 범위", lambda: BulletKind(flingy=209)),
        ("reverse bool", lambda: BulletKind(reverse=1)),
        ("shell 범위", lambda: BulletKind(shell=-1)),
        ("remove_timer 범위", lambda: BulletKind(remove_timer=0x10000)),
        ("y_offset 실수", lambda: BulletKind(y_offset=1.5)),
        ("dat 형식", lambda: BulletKind(dat={})),
        ("speed 범위", lambda: k.speed_actions(0x10000)),
        ("speed 음수", lambda: k.speed_actions(-1)),
        ("time 범위", lambda: k.time_actions(256)),
        ("height 범위", lambda: k.height_actions(-1)),
        ("flingy 없음", lambda: BulletKind(flingy=None).speed_actions(1)),
        ("weapon 없음", lambda: BulletKind(weapon=None).time_actions(1)),
        ("setup Anywhere", lambda: bullet.setup(loc=64)),
        ("setup 0", lambda: bullet.setup(loc=0)),
        ("setup 256", lambda: bullet.setup(loc=256)),
        ("setup 실수", lambda: bullet.setup(loc=1.5)),
        ("setup 변수", lambda: bullet.setup(loc=EUDVariable())),
        ("heading bool", lambda: bullet.heading_to_facing(k, True)),
        ("heading 종류 아님", lambda: bullet.heading_to_facing(5, 1)),
        ("epScript f_f_ 이름", lambda: bullet.f_f_bullet),
    ]:
        ck.raises(label, EudextError, fn)
    ck.eq("setup 뒤 값 그대로", bullet._state["loc"], LOC)
    ck.true("없는 이름 hasattr", not hasattr(bullet, "no_such_name"), "")
    for h in (0, 1, 127, 128, 255, 256, 0xFFFFFFC0, -64):
        ck.eq("heading_to_facing %d" % h, bullet.heading_to_facing(k, h), RB.heading_to_facing(h & M32))
        ck.eq("heading_to_facing fw %d" % h, bullet.heading_to_facing(KINDS["fw"], h), RB.heading_to_facing(h & M32, False))
    ck.eq("setup 이름 저장", (bullet.setup(loc="Location 0"), bullet._state["loc"])[1], "Location 0")
    bullet.setup(loc=LOC)


# =============================================================================================
# 에뮬레이터 케이스
# =============================================================================================


def build_cases(s):
    for name, k in KINDS.items():
        @s.case("v_" + name)
        def _(t, k=k):
            t.out("r", bullet.bullet(k, t.var("o"), t.var("x"), t.var("y"), t.var("f")))

        @s.case("c_" + name)
        def _(t, k=k):
            t.out("r", bullet.bullet(k, P8, t.var("x"), t.var("y"), 300))

    for name in TO_KINDS:
        @s.case("t_" + name)
        def _(t, k=KINDS[name]):
            t.out("r", bullet.bullet_to(k, t.var("o"), t.var("x"), t.var("y"), t.var("tx"), t.var("ty")))

    for name in AT_KINDS:
        @s.case("a_" + name)
        def _(t, k=KINDS[name]):
            t.out("r", bullet.bullet_at(k, t.var("o"), t.var("l"), t.var("f")))

    for name in HV_KINDS:
        @s.case("hv_" + name)
        def _(t, k=KINDS[name]):
            t.out("r", bullet.bullet(k, P8, t.var("x"), t.var("y"), t.var("f"), height=t.var("h")))

    for name in HC_KINDS:
        @s.case("hc_" + name)
        def _(t, k=KINDS[name]):
            t.out("r", bullet.bullet(k, P8, t.var("x"), t.var("y"), t.var("f"), height=77))

    @s.case("allconst")
    def _(t):
        t.out("r", bullet.bullet(KINDS["ue"], P8, 1000, 2000, 300))

    @s.case("to_const")
    def _(t):
        t.out("r", bullet.bullet_to(KINDS["ue"], P8, 100, 100, 101, 102, height=20))

    @s.case("cpv")
    def _(t):
        f_setcurpl(t.var("c"))
        t.out("r", bullet.bullet(KINDS["ue"], P8, t.var("x"), t.var("y"), t.var("f")))
        t.out("gc", f_getcurpl())
        t.watch("cpm", CP_ADDR)

    @s.case("to_consts")
    def _(t):
        for j, ((sx, sy), (tx, ty), _a, _f, _h) in enumerate(TO_TABLE[:6]):
            t.out("r%d" % j, bullet.bullet_to(KINDS["fw" if j % 2 else "ue"], P8, sx, sy, tx, ty))

    @s.case("at_name")
    def _(t):
        t.out("r", bullet.bullet_at(KINDS["ue"], P8, "CLoc", -64))

    @s.case("cp")
    def _(t):
        f_setcurpl(P3)
        t.out("r", bullet.bullet(KINDS["ue"], P8, t.var("x"), t.var("y"), t.var("f")))
        t.out("gc", f_getcurpl())
        t.watch("cpm", CP_ADDR)

    @s.case("ocp")
    def _(t):
        f_setcurpl(P3)
        t.out("r", bullet.bullet(KINDS["ue"], CurrentPlayer, t.var("x"), t.var("y"), t.var("f")))
        t.watch("cpm", CP_ADDR)

    @s.case("multi")
    def _(t):
        x, y = t.var("x"), t.var("y")
        t.out("r1", bullet.bullet(KINDS["ue"], P8, x, y, 0))
        t.out("r2", bullet.bullet_to(KINDS["sh"], P8, x, y, 0, 0))
        t.out("r3", bullet.bullet(KINDS["m2"], P8, x, y, t.var("f")))

    @s.case("hf")
    def _(t):
        h = t.var("h")
        t.out("rev", bullet.heading_to_facing(KINDS["ue"], h))
        t.out("fwd", bullet.heading_to_facing(KINDS["fw"], h))

    @s.case("spd")
    def _(t):
        KINDS["sh"].set_speed(t.var("v"))  # flingy 158

    @s.case("spd_odd")
    def _(t):
        KINDS["m2"].set_speed(t.var("v"), halt=t.var("hd"))  # flingy 173 (가속도 윗 워드)

    @s.case("spd_fwd")
    def _(t):
        KINDS["fw"].set_speed(t.var("v"))  # flingy 106 reverse=False

    @s.case("spd_mix")
    def _(t):
        KINDS["mn"].set_speed(100, halt=t.var("hd"))  # flingy 174: 상수 속도 + 변수 halt
        KINDS["ue"].set_speed(t.var("v"), halt=5)  # flingy 106: 변수 속도 + 상수 halt

    @s.case("spd_c")
    def _(t):
        KINDS["mn"].set_speed(4321, halt=9)  # flingy 174

    @s.case("tm")
    def _(t):
        KINDS["ue"].set_time(t.var("v"))  # 무기 127 (시프트 24)
        KINDS["mn"].set_time(33)  # 무기 30

    @s.case("ht")
    def _(t):
        KINDS["mn"].set_height(t.var("v"))  # 206 (시프트 16)
        KINDS["m2"].set_height(44)  # 205

    # 빌드 때 오류가 나야 하는 것
    def bad(name, fn, msg=None):
        s.case("err_" + name, expect_build_error=EudextError, expect_message=msg)(lambda t: fn(t))

    ku = KINDS["ue"]
    bad("owner14", lambda t: bullet.bullet(ku, 14, 0, 0, 0), "owner")
    bad("owner_all", lambda t: bullet.bullet(ku, "AllPlayers", 0, 0, 0), "owner")
    bad("owner_bool", lambda t: bullet.bullet(ku, True, 0, 0, 0), "owner")
    bad("height256", lambda t: bullet.bullet(ku, P8, 0, 0, 0, height=256), "height")
    bad("facing_float", lambda t: bullet.bullet(ku, P8, 0, 0, 1.5), "facing")
    bad("x_bool", lambda t: bullet.bullet(ku, P8, True, 0, 0), "x")
    bad("x_big", lambda t: bullet.bullet(ku, P8, 1 << 32, 0, 0), "x")
    bad("kind", lambda t: bullet.bullet(5, P8, 0, 0, 0), "BulletKind")
    bad("kind_to", lambda t: bullet.bullet_to(None, P8, 0, 0, 0, 0), "BulletKind")
    bad("at0", lambda t: bullet.bullet_at(ku, P8, 0, 0), "loc")
    bad("at256", lambda t: bullet.bullet_at(ku, P8, 256, 0), "loc")
    bad("at_name", lambda t: bullet.bullet_at(ku, P8, "없는 로케이션", 0), "로케이션")
    bad("speed_var", lambda t: ku.speed_actions(t.var("v")), "set_speed")
    bad("time_var", lambda t: ku.time_actions(t.var("v")), "set_time")
    bad("height_var", lambda t: ku.height_actions(t.var("v")), "set_height")
    bad("noflingy", lambda t: BulletKind(flingy=None).set_speed(t.var("v")), "flingy")
    bad("noweapon", lambda t: BulletKind(weapon=None).set_time(3), "weapon")

    def bad_setup(t):
        bullet.setup(loc="없는 로케이션")
        try:
            bullet.bullet(ku, P8, 0, 0, 0)
        finally:
            bullet.setup(loc=LOC)

    s.case("err_setup_name", expect_build_error=EudextError, expect_message="맵에 없습니다")(bad_setup)


class Env:
    def __init__(self, s, rng):
        self.s = s
        self.m = s.machine
        self.model = scmodel.unit_model(self.m)
        self.rng = rng
        self.lo, self.hi = self.m.base, self.m.limit_addr
        self.head = 0
        self.sent = {}
        self.before = {}

    def ext(self):
        return {k: v for k, v in self.m.mem.items() if not self.lo <= k < self.hi}

    def fresh(self, head=5, fill=False, fail=0, loc27=None, cp=None):
        self.s.reset()
        self.model.clear_log()
        self.model.clear_failures()
        self.model.set_free(list(range(head, 1700)) + list(range(head)))
        self.head = head
        base = RB.ptr_of(head)
        self.sent = {}
        for k in range(2, 84):
            v = self.rng.getrandbits(32)
            self.m.setdw(base + 4 * k, v)
            self.sent[k] = v
        if loc27 is not None:
            self.model.set_location(LOC27, *loc27)
        if cp is not None:
            self.m.setdw(CP_ADDR, cp)
        if fill:
            self.model.fill()
        if fail:
            self.model.fail_next(fail)
        self.before = self.ext()

    def changed(self):
        after = self.ext()
        return {k for k in set(self.before) | set(after) if self.before.get(k, 0) != after.get(k, 0)}


def expect_slot(env, kind, owner, pos, facing):
    exp = dict(env.sent)
    exp[10] = pos
    exp[19] = (exp[19] & ~0xFFFF & M32) | owner | (scmodel.ORDER_ON_CREATE << 8)
    exp[25] = (exp[25] & ~0xFFFF & M32) | made_unit(kind)
    exp[41] = (exp[41] & ~0xFF00 & M32) | ((((exp[41] >> 8) + 1) & 0xFF) << 8)
    exp[55] |= 1
    patch = RB.patch(kind.recipe, facing, pos, kind.remove_timer, kind.unit if kind.shell is not None else None)
    for k, (v, mk) in patch.items():
        exp[k] = (exp[k] & ~mk & M32) | (v & mk)
    return exp


def scenario(s, env, case, inputs, label, kind, mode, *, owner=7, x=0, y=0, facing=0, tx=0, ty=0, loc=None,
             loc27=None, height=None, head=5, fill=False, fail=0, cp=None, extra_allowed=(), memo=None):
    """케이스 한 번 실행 + S4 6.3 판정. 반환: (통과 여부, RunResult)."""
    env.fresh(head, fill, fail, loc27, cp)
    r = s.run(case, inputs)
    results = []

    def rec(lbl, cond, msg=""):
        results.append(s.expect_true(case, cond, label + " / " + lbl, msg))

    if r.error:
        rec("실행", False, r.error)
        return False, r
    m, model = env.m, env.model
    created = model.created
    failed = fill or fail
    want = 0 if failed else RB.epd_of(head)
    rec("반환", r["r"] == want, "r=%d 기대 %d" % (r["r"], want))
    if mode == "at":
        want_loc = loc
    else:
        want_loc = LOC
    yoff = kind.y_offset if mode != "at" else 0
    y2 = (y + yoff) & M32
    if fill:
        rec("CreateUnit 기록 없음", created == [], repr(created))
    else:
        ok = (len(created) == 1 and created[0].unit == made_unit(kind) and created[0].player == owner
              and created[0].loc == want_loc and created[0].count == 1 and created[0].ok == (not fail))
        rec("CreateUnit 기록", ok, repr(created))
    allowed = set(extra_allowed)
    if not fill and mode != "at":
        la = loc_addr(LOC)
        rect = [m.dw(la + 4 * i) for i in range(4)]
        rec("로케이션", rect == [x & M32, y2, x & M32, y2], "%r 기대 %r" % (rect, [x, y2, x, y2]))
        allowed |= {la + 4 * i for i in range(4)}
    if height is not None and not fill:
        ea, esh = RB.elevation_addr(made_unit(kind))
        got = (m.dw(ea) >> esh) & 0xFF
        rec("높이", got == height & 0xFF, "elevation=%d 기대 %d" % (got, height & 0xFF))
        allowed.add(ea)
        before = env.before.get(ea, 0)
        rec("높이 칸 밖 비트", (m.dw(ea) & ~(0xFF << esh) & M32) == (before & ~(0xFF << esh) & M32), "")
    if not failed:
        base = RB.ptr_of(head)
        allowed |= {base + 4 * k for k in range(84)} | {NEXT, FIRST_UNIT}
        nxt = model.next_free()
        if nxt is not None:
            allowed.add(RB.ptr_of(nxt))
        if mode == "at":
            l, t_, rr, b = loc27
            pos = RB.pos_word((l + rr) // 2, (t_ + b) // 2)
        else:
            pos = RB.pos_word(x, y2)
        exp = expect_slot(env, kind, owner, pos, facing)
        bad = []
        for k in range(2, 84):
            if k in (2, 3, 28):  # 모델만 쓰는 칸 (HP·스프라이트·서브유닛)
                continue
            got = m.dw(base + 4 * k)
            if got != exp[k]:
                bad.append("+%d(0x%X): 0x%08X 기대 0x%08X" % (k, 4 * k, got, exp[k]))
        rec("CUnit 칸", not bad, "; ".join(bad))
        if memo is not None:
            memo["facing"] = (m.dw(base + 32) >> 8) & 0xFF
    changed = env.changed()
    rec("엉뚱한 쓰기 없음", changed <= allowed, ", ".join("0x%X" % a for a in sorted(changed - allowed)))
    rec("금지 칸", not any(RB.forbidden(a) for a in changed), "")
    return all(results), r


def to_inputs(o, x, y, tx, ty):
    return {"o": o, "x": x & M32, "y": y & M32, "tx": tx & M32, "ty": ty & M32}


def run_spec63(s, env, rng):
    ku = KINDS["ue"]
    head = 5
    # 정상 (S4 6.3 첫 줄): 반환 19445, 칸 값
    scenario(s, env, "c_ue", {"x": 1000, "y": 2000}, "6.3 정상", ku, "own", x=1000, y=2000, facing=300, head=head)
    m = env.m
    e = 19445
    ck = [(22, M32, RB.pos_word(1000, 2000)), (8, 0xFF00, 0x2C00), (19, 0xFF00, 0x8700), (40, 0xFF000000, 0),
          (55, 0x300104, 0x200104), (57, M32, 0), (68, 0xFFFF, 12)]
    for off, mk, want in ck:
        got = m.dw(0x58A364 + 4 * (e + off)) & mk
        s.expect_true("c_ue", got == want, "6.3 표 [%d+%d]" % (e, off), "0x%X 기대 0x%X" % (got, want))
    scenario(s, env, "allconst", {}, "6.3 정상 (모두 상수)", ku, "own", x=1000, y=2000, facing=300)
    # 음수 방향
    memo = {}
    scenario(s, env, "v_ue", {"o": 7, "x": 1000, "y": 2000, "f": 0xFFFFFFC0}, "6.3 음수 방향", ku, "own",
             x=1000, y=2000, facing=0xFFFFFFC0, memo=memo)
    s.expect_true("v_ue", memo.get("facing") == 192, "6.3 음수 방향 = 192", repr(memo))
    # 슬롯 없음 / 생성 실패
    for case, inp in (("v_ue", {"o": 7, "x": 1, "y": 2, "f": 3}), ("c_ue", {"x": 1, "y": 2}),
                      ("t_ue", to_inputs(7, 1, 2, 3, 4))):
        mode = "to" if case.startswith("t_") else "own"
        scenario(s, env, case, inp, "6.3 슬롯 없음", ku, mode, x=1, y=2, fill=True)
        scenario(s, env, case, inp, "6.3 생성 실패", ku, mode, x=1, y=2, fail=1)
    scenario(s, env, "a_ue", {"o": 7, "l": LOC27, "f": 3}, "6.3 슬롯 없음 (at)", ku, "at", loc=LOC27,
             loc27=(10, 20, 30, 40), fill=True)
    scenario(s, env, "a_ue", {"o": 7, "l": LOC27, "f": 3}, "6.3 생성 실패 (at)", ku, "at", loc=LOC27,
             loc27=(10, 20, 30, 40), fail=1)
    for name in ("sh", "shm", "m2", "mn5"):
        scenario(s, env, "hv_" + name, {"x": 5, "y": 6, "f": 7, "h": 9}, "6.3 생성 실패 + 높이", KINDS[name], "own",
                 owner=7, x=5, y=6, facing=7, height=9, fail=1)
    # shell / y_offset / m2
    scenario(s, env, "v_sh", {"o": 7, "x": 1000, "y": 2000, "f": 300}, "6.3 shell", KINDS["sh"], "own",
             x=1000, y=2000, facing=300)
    base = RB.ptr_of(env.head)
    s.expect_true("v_sh", (m.dw(base + 100) & 0xFFFF) == 210, "6.3 shell [+25] = 210", "")
    s.expect_true("v_sh", env.model.created[0].unit == 204, "6.3 shell CreateUnit 204", "")
    scenario(s, env, "v_y10", {"o": 7, "x": 1000, "y": 2000, "f": 300}, "6.3 y_offset", KINDS["y10"], "own",
             x=1000, y=2000, facing=300)
    s.expect_true("v_y10", [m.dw(loc_addr(LOC) + 4 * i) for i in (1, 3)] == [2010, 2010], "6.3 y_offset T=B=2010", "")
    scenario(s, env, "v_m2", {"o": 7, "x": 1000, "y": 2000, "f": 300}, "6.3 recipe m2", KINDS["m2"], "own",
             x=1000, y=2000, facing=300)
    pos = RB.pos_word(1000, 2000)
    got = [m.dw(base + 4 * k) for k in (4, 6, 7, 22)]
    s.expect_true("v_m2", got == [pos] * 4, "6.3 m2 [+4]=[+6]=[+7]=[+22]=pos", repr(got))
    s.expect_true("v_m2", (m.dw(base + 32) & 0xFF0000) == 127 << 16, "6.3 m2 [+8] turnSpeed 127", "")
    s.expect_true("v_m2", (m.dw(base + 272) & 0xFFFF) == 30, "6.3 m2 [+68] = 30", "")
    for k in (40, 55, 57):
        want = env.sent[k] | (1 if k == 55 else 0)
        s.expect_true("v_m2", m.dw(base + 4 * k) == want, "6.3 m2 +%d 안 씀" % k, "")
    # CP
    ok, r = scenario(s, env, "cp", {"x": 1000, "y": 2000, "f": 1}, "6.3 CP", ku, "own", x=1000, y=2000, facing=1,
                     cp=0, extra_allowed={CP_ADDR})
    s.expect_true("cp", r.values.get("cpm") == 2 and r.values.get("gc") == 2, "6.3 호출 뒤 CP = P3", repr(r.values))
    ok, r = scenario(s, env, "ocp", {"x": 3, "y": 4, "f": 5}, "owner = CurrentPlayer", ku, "own", owner=2, x=3, y=4,
                     facing=5, cp=0, extra_allowed={CP_ADDR})
    s.expect_true("ocp", r.values.get("cpm") == 2, "CurrentPlayer 뒤 CP", repr(r.values))
    for cpv in (0, 1, 7, 11, 0x12345, M32):
        ok, r = scenario(s, env, "cpv", {"c": cpv, "x": 3, "y": 4, "f": 5}, "CP 0x%X 그대로" % cpv, ku, "own",
                         x=3, y=4, facing=5, cp=0, extra_allowed={CP_ADDR})
        s.expect_true("cpv", r.values.get("cpm") == cpv and r.values.get("gc") == cpv, "CP 0x%X 보존" % cpv,
                      repr(r.values))
        for fill, fail in ((True, 0), (False, 1)):
            ok, r = scenario(s, env, "cpv", {"c": cpv, "x": 3, "y": 4, "f": 5}, "CP 0x%X 실패 경로" % cpv, ku, "own",
                             x=3, y=4, facing=5, cp=0, fill=fill, fail=fail, extra_allowed={CP_ADDR})
            s.expect_true("cpv", r.values.get("cpm") == cpv and r.values.get("gc") == cpv,
                          "CP 0x%X 보존 (실패 경로)" % cpv, repr(r.values))
    # 6.1 방향표를 본문으로
    for (sx, sy), (tx, ty), _a, face, _h in TO_TABLE:
        memo = {}
        scenario(s, env, "t_ue", to_inputs(7, sx, sy, tx, ty), "6.1 표 %r→%r" % ((sx, sy), (tx, ty)), ku, "to",
                 x=sx, y=sy, facing=face, memo=memo)
        s.expect_true("t_ue", memo.get("facing") == face, "6.1 표 facing %r→%r" % ((sx, sy), (tx, ty)), repr(memo))
    scenario(s, env, "to_const", {}, "to 상수 (100,100)→(101,102)", ku, "to", x=100, y=100, facing=237, height=20)


def run_matrix(s, env, rng):
    """조합: 종류 × 방식(변수 방향·상수 방향·to·at·높이) × 무작위 입력."""
    edges_xy = [0, 1, 0x7FFF, 0x8000, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, M32]
    for name, k in KINDS.items():
        for j in range(24):
            o = rng.randrange(12)
            x = edges_xy[j % 9] if j < 9 else rng.getrandbits(32)
            y = edges_xy[(j * 5) % 9] if j < 9 else rng.randrange(0, 8192)
            f = EDGES32[j % len(EDGES32)] if j < 9 else rand32(rng)
            scenario(s, env, "v_" + name, {"o": o, "x": x, "y": y, "f": f}, "v %s #%d" % (name, j), k, "own",
                     owner=o, x=x, y=y, facing=f, head=rng.randrange(1700))
        for j in range(6):
            x, y = rng.randrange(4096), rng.randrange(4096)
            scenario(s, env, "c_" + name, {"x": x, "y": y}, "c %s #%d" % (name, j), k, "own", x=x, y=y, facing=300,
                     head=rng.randrange(1700))
    for name in TO_KINDS:
        k = KINDS[name]
        for j in range(60):
            sx, sy = rng.randrange(8192), rng.randrange(8192)
            if j < 20:
                tx, ty = sx + rng.randrange(-3, 4), sy + rng.randrange(-3, 4)
            else:
                tx, ty = rng.randrange(8192), rng.randrange(8192)
            o = rng.randrange(12)
            face = RB.facing_to(sx, sy, tx, ty, k.reverse)
            scenario(s, env, "t_" + name, to_inputs(o, sx, sy, tx, ty), "to %s #%d" % (name, j), k, "to",
                     owner=o, x=sx, y=sy, facing=face, head=rng.randrange(1700))
    for name in AT_KINDS:
        k = KINDS[name]
        for j in range(12):
            l, t_ = rng.randrange(4000), rng.randrange(4000)
            rect = (l, t_, l + rng.randrange(0, 96), t_ + rng.randrange(0, 96))
            f = rand32(rng)
            o = rng.randrange(12)
            loc = LOC27 if j % 2 else LOC27
            scenario(s, env, "a_" + name, {"o": o, "l": loc, "f": f}, "at %s #%d" % (name, j), k, "at", owner=o,
                     facing=f, loc=loc, loc27=rect, head=rng.randrange(1700))
    rect = (1312, 1216, 1440, 1312)
    scenario(s, env, "at_name", {}, "at 이름 CLoc (−64)", KINDS["ue"], "at", loc=LOC27, loc27=rect, facing=0xFFFFFFC0)
    for name in HV_KINDS:
        k = KINDS[name]
        for j in range(12):
            h = EDGES32[j] if j < len(EDGES32) else rand32(rng)
            x, y = rng.randrange(4096), rng.randrange(4096)
            f = rng.randrange(256)
            scenario(s, env, "hv_" + name, {"x": x, "y": y, "f": f, "h": h}, "hv %s h=0x%X" % (name, h), k, "own",
                     x=x, y=y, facing=f, height=h, head=rng.randrange(1700))
    for name in HC_KINDS:
        k = KINDS[name]
        scenario(s, env, "hc_" + name, {"x": 9, "y": 8, "f": 7}, "hc %s" % name, k, "own", x=9, y=8, facing=7,
                 height=77)


def run_sequences(s, env, rng):
    """실패 뒤 분기가 되돌아오는가 (fresh 없이 이어서), 여러 발, 방향 무작위 차등."""
    m, model = env.m, env.model
    ku = KINDS["ue"]
    env.fresh(head=100)
    inp = {"o": 7, "x": 10, "y": 20, "f": 30}
    saved = m.dw(NEXT)
    m.setdw(NEXT, 0)
    r1 = s.run("v_ue", inp)
    m.setdw(NEXT, saved)
    r2 = s.run("v_ue", inp)
    model.fail_next(1)
    r3 = s.run("v_ue", inp)
    r4 = s.run("v_ue", inp)
    m.setdw(NEXT, 0)
    r5 = s.run("t_ue", to_inputs(7, 1, 2, 3, 4))
    m.setdw(NEXT, RB.ptr_of(300))
    model.set_free(list(range(300, 1700)))
    r6 = s.run("t_ue", to_inputs(7, 1, 2, 3, 4))
    got = [r.values.get("r") for r in (r1, r2, r3, r4, r5, r6)]
    want = [0, RB.epd_of(100), 0, RB.epd_of(101), 0, RB.epd_of(300)]
    s.expect_true("v_ue", got == want, "실패 → 성공 분기 복구", "%r 기대 %r" % (got, want))
    s.expect_true("v_ue", [c.ok for c in model.created] == [True, False, True, True], "분기 복구 기록",
                  repr(model.created))
    # 상수 좌표 bullet_to 여러 발 (reverse 번갈아)
    env.fresh(head=60)
    r = s.run("to_consts", {})
    got = [(m.dw(RB.ptr_of(60 + j) + 32) >> 8) & 0xFF for j in range(6)]
    want = [RB.facing_to(sx, sy, tx, ty, j % 2 == 0) for j, ((sx, sy), (tx, ty), _a, _f, _h) in enumerate(TO_TABLE[:6])]
    rv = [r.values.get("r%d" % j) for j in range(6)]
    s.expect_true("to_consts", got == want and rv == [RB.epd_of(60 + j) for j in range(6)] and not r.error,
                  "상수 좌표 bullet_to 6발", "%r 기대 %r (%r %s)" % (got, want, rv, r.error))
    # 여러 발 (한 사이클)
    env.fresh(head=40)
    r = s.run("multi", {"x": 500, "y": 600, "f": 9})
    want = [RB.epd_of(40), RB.epd_of(41), RB.epd_of(42)]
    got = [r.values.get(n) for n in ("r1", "r2", "r3")]
    s.expect_true("multi", got == want and not r.error, "세 발 칸", "%r 기대 %r %s" % (got, want, r.error))
    s.expect_true("multi", [c.unit for c in model.created] == [208, 204, 205], "세 발 종류", repr(model.created))
    face2 = RB.facing_to(500, 600, 0, 0)
    got = [(m.dw(RB.ptr_of(i) + 32) >> 8) & 0xFF for i in (40, 41, 42)]
    s.expect_true("multi", got == [0, face2, 9], "세 발 방향", "%r" % got)
    s.expect_true("multi", (m.dw(RB.ptr_of(41) + 100) & 0xFFFF) == 210, "두 번째 shell 종류", "")
    # 변수 방향 무작위 차등 (칸 바이트만 빠르게)
    bad = 0
    env.fresh(head=0)
    snap = m.snapshot()
    for j in range(300):
        m.restore(snap)
        model.clear_log()
        f = EDGES32[j] if j < len(EDGES32) else rand32(rng)
        r = s.run("v_ue", {"o": 7, "x": 1, "y": 2, "f": f})
        got = (m.dw(RB.ptr_of(0) + 32) >> 8) & 0xFF
        if r.error or r.values.get("r") != RB.epd_of(0) or got != f & 0xFF:
            bad += 1
    s.expect_true("v_ue", bad == 0, "변수 방향 차등 300", "불일치 %d" % bad)
    # bullet_to 무작위 차등 (좌표 차 ±32767, reverse 둘 다)
    for name in ("ue", "fw"):
        k = KINDS[name]
        bad = []
        for j in range(400):
            m.restore(snap)
            sx, sy = rng.randrange(0, 32768), rng.randrange(0, 32768)
            tx, ty = rng.randrange(max(0, sx - 32767), min(65536, sx + 32768)), \
                rng.randrange(max(0, sy - 32767), min(65536, sy + 32768))
            if j % 7 == 0:
                tx, ty = sx, sy
            r = s.run("t_" + name, to_inputs(7, sx, sy, tx, ty))
            got = (m.dw(RB.ptr_of(0) + 32) >> 8) & 0xFF
            want = RB.facing_to(sx, sy, tx, ty, k.reverse)
            if r.error or got != want:
                bad.append((sx, sy, tx, ty, got, want, r.error))
        s.expect_true("t_" + name, not bad, "bullet_to 차등 400", repr(bad[:5]))
    # heading_to_facing (변수)
    bad = 0
    for j in range(200):
        h = EDGES32[j] if j < len(EDGES32) else rand32(rng)
        r = s.run("hf", {"h": h}, fresh=True)
        if r.error or r.values.get("rev") != RB.heading_to_facing(h) or r.values.get("fwd") != RB.heading_to_facing(h, False):
            bad += 1
    s.expect_true("hf", bad == 0, "heading_to_facing 변수 200", "불일치 %d" % bad)


def run_dat(s, env, rng):
    m = env.m
    # install() 한 BulletDat 이 시작 1회 목록으로 들어갔는가
    mem = dat.simulate(KDAT.init_actions())
    # 시작 목록은 다른 칸과 dword 를 나눠 쓰므로(마스크 쓰기) 마스크 부분만 비교
    bad = []
    for d in decode_all(KDAT.init_actions()):
        a, mod, v, mk = d
        if (m.dw(a) & mk) != (v & mk):
            bad.append((hex(a), hex(v), hex(mk), hex(m.dw(a))))
    s.expect_true("spd", not bad and len(mem) > 10, "install() → 게임 시작 때 dat 적용", repr(bad))
    fl158_top, fl158_acc = 0x6CA170, 0x6C9DB4
    for v in (0, 1, 500, 0xFFFF, 0x10000, 0x12345678, M32):
        r = s.run("spd", {"v": v}, fresh=True)
        got = (m.dw(fl158_top), m.dw(fl158_acc) & 0xFFFF)
        want = (M32 - v, v & 0xFFFF)
        s.expect_true("spd", got == want and not r.error, "set_speed(%d) flingy 158" % v, "%r 기대 %r" % (got, want))
    top173 = 0x6C9EF8 + 4 * 173
    acc173 = 0x6C9DD0
    halt173 = 0x6C9930 + 4 * 173
    for v, hd in ((0, 0), (700, 5), (0xFFFF, M32), (0x12345, 77)):
        r = s.run("spd_odd", {"v": v, "hd": hd}, fresh=True)
        got = (m.dw(top173), (m.dw(acc173) >> 16) & 0xFFFF, m.dw(halt173))
        want = (M32 - v, v & 0xFFFF, hd)
        s.expect_true("spd_odd", got == want and not r.error, "set_speed(%d, halt) flingy 173" % v,
                      "%r 기대 %r %s" % (got, want, r.error))
    for v in (0, 8000, M32):
        r = s.run("spd_fwd", {"v": v}, fresh=True)
        got = (m.dw(0x6CA0A0), m.dw(0x6C9D4C) & 0xFFFF)
        s.expect_true("spd_fwd", got == (v, v & 0xFFFF), "set_speed reverse=False %d" % v, repr(got))
    for v, hd in ((0, 0), (9000, M32), (M32, 12)):
        r = s.run("spd_mix", {"v": v, "hd": hd}, fresh=True)
        got = (m.dw(0x6CA1B0), m.dw(0x6C9DD4) & 0xFFFF, m.dw(0x6C9930 + 4 * 174),
               m.dw(0x6CA0A0), m.dw(0x6C9D4C) & 0xFFFF, m.dw(0x6C9930 + 4 * 106))
        want = (M32 - 100, 100, hd, M32 - v, v & 0xFFFF, 5)
        s.expect_true("spd_mix", got == want and not r.error, "set_speed 상수·변수 섞기 %d %d" % (v, hd),
                      "%r 기대 %r" % (got, want))
    r = s.run("spd_c", {}, fresh=True)
    got = (m.dw(0x6CA1B0), m.dw(0x6C9DD4) & 0xFFFF, m.dw(0x6C9930 + 4 * 174))
    s.expect_true("spd_c", got == (M32 - 4321, 4321, 9), "set_speed 상수", repr(got))
    for v in (0, 1, 255, 256, M32):
        r = s.run("tm", {"v": v}, fresh=True)
        got = ((m.dw(0x6570BC) >> 24) & 0xFF, (m.dw(0x65705C) >> 16) & 0xFF)
        s.expect_true("tm", got == (v & 0xFF, 33), "set_time(%d)" % v, repr(got))
        r = s.run("ht", {"v": v}, fresh=True)
        got = ((m.dw(0x66321C) >> 16) & 0xFF, (m.dw(0x663150 + 204) >> 8) & 0xFF)
        s.expect_true("ht", got == (v & 0xFF, 44), "set_height(%d)" % v, repr(got))


# =============================================================================================
# epScript 예제·인게임 확인 맵
# =============================================================================================


def eps_checks(ck):
    src = open(os.path.join(EX, "bullet_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("bullet_example.eps", src)
    ck.eq("eps errors", nerr, 0)
    for needle in ("bullet.BulletKind(unit=208, weapon=127, flingy=106, dat=bullet.BulletDat(sprite=344))",
                   "bullet.f_setup(loc=\"Location 0\")", "kind.install()", "DoActions(kind.speed_actions(500))",
                   "bullet.f_bullet(kind, P8, 2048, 2048, angle)", "bullet.f_heading_to_facing(kind,",
                   "bullet.f_bullet_at(kind, P8, \"CLoc\", f)",
                   "bullet.f_bullet_to(shell, P7, 1000 + frame * 100, 1000, 2048, 2048, height=12)",
                   "kind.set_speed(speedNow)",
                   "splash=FlattenList([8, 8, 8])"):
        ck.true("eps: " + needle, out is not None and needle in out, "")
    src = open(os.path.join(EX, "bullet_ingame.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("bullet_ingame.eps", src)
    ck.eq("ingame eps errors", nerr, 0)
    ck.true("ingame eps: f_ 번역", out is not None and "bullet.f_bullet_to(kA," in out, "")
    bad = _compat.eps_compile("bad.eps", "import eudext.bullet as bullet;\nfunction g() { bullet.f_bullet(0, 0, 0, 0, 0); }")[0]
    ck.true("eps: bullet.f_bullet → f_f_bullet", bad is not None and "bullet.f_f_bullet(" in bad, "")


def _load_eps(name, work_name):
    from eudext.tools import build

    work = os.path.join(_common.WORK, work_name)
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name), os.path.join(work, name))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, name), {})


def eps_emulate(ck):
    """예제를 싣고 에뮬레이터에서 4 사이클 돌린다."""
    mod = _load_eps("bullet_example.eps", "t_bullet_eps")
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "made", "failed", "lastFacing", "lastTo", "speedNow")
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m, units={})
    model = scmodel.unit_model(m)
    model.set_location(LOC27, 1312, 1216, 1440, 1312)
    rows = []
    for _ in range(4):
        m.cycle()
        rows.append({n: m.var(n) for n in names})
    print("  epScript 예제 에뮬레이션: %r" % rows[-1])
    # 사이클마다 8방향 8발 + at 1발 + to 1발. at 의 facing = heading_to_facing(frame·8) = frame·8 + 128
    for cyc, row in enumerate(rows):
        fr = cyc + 1
        to_face = RB.facing_to(1000 + fr * 100, 1000, 2048, 2048)
        ck.eq("eps 사이클 %d" % fr, row, {"frame": fr, "made": 8 * fr, "failed": 0,
                                          "lastFacing": (fr * 8 + 128) & 0xFF, "lastTo": to_face,
                                          "speedNow": 400 + fr})
    ck.eq("eps 기록 수", len(model.created), 4 * 10 + 1)  # + eudplib 로케일 판별 CreateUnit 1
    shots = [c for c in model.created if c.ok]
    ck.eq("eps 기록 종류", sorted({(c.unit, c.loc, c.player) for c in shots}),
          [(204, LOC, 6), (208, LOC, 7), (208, LOC27, 7)])
    ck.eq("eps dat: flingy 106 최고속도(set_speed 404)", m.dw(0x6CA0A0), M32 - 404)
    ck.eq("eps dat: flingy 158 최고속도(install)", m.dw(0x6CA170), M32 - 2560)
    ck.eq("eps dat: 무기 127 수명", (m.dw(0x6570BC) >> 24) & 0xFF, 32)
    ck.eq("eps dat: elevation 208·210", (m.dw(0x663220) & 0xFF, (m.dw(0x663220) >> 16) & 0xFF), (20, 20))
    ck.eq("eps dat: elevation 204 (height=12)", m.dw(0x66321C) & 0xFF, 12)
    sp_a, sp_sh, sp_m = dat.field("flingy", "sprite").location(106)
    ck.eq("eps dat: flingy 106 그림", (m.dw(sp_a) & sp_m) >> sp_sh, 344)
    ck.eq("eps 흉내 못 낸 것", [k for k in m.unknown if k != ("act", 9)], [])


def ingame_emulate(ck):
    """인게임 확인 맵을 에뮬레이터에서 700 사이클 돌린다(실행 오류·흐름·방향 확인)."""
    mod = _load_eps("bullet_ingame.eps", "t_bullet_ingame")
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "shots", "zeroShots", "facingBad", "hits", "fillMade", "shellType", "e6count")
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m, units={})
    model = scmodel.unit_model(m)
    for i in range(66):  # 기준 맵처럼 P1 맵 리빌러 64 + 시작 위치 2
        model.spawn(101 if i < 64 else 214, 0)
    err = None
    try:
        for cyc in range(700):
            if cyc % 10 == 5:
                model.process_deaths()
            m.cycle()
    except emu.EmuError as e:
        err = str(e)
    got = {n: m.var(n) for n in names}
    print("  인게임 맵 에뮬레이션: %r, 기록 %d" % (got, len(model.created)))
    ck.eq("ingame emu 오류", err, None)
    # 모델에는 탄·피해가 없으므로 hits = 0. 채움 = 1700 − 66(미리 놓임) = 1634
    ck.eq("ingame emu 값", got, {"frame": 700, "shots": 19, "zeroShots": 1, "facingBad": 0, "hits": 0,
                                  "fillMade": 1634, "shellType": 210, "e6count": 5})
    kinds = [(c.unit, c.player) for c in model.created if c.ok and c.unit in (204, 208, 210)]
    ck.eq("ingame emu 탄 수", len(kinds), 19 + 2 + 5 + 2 + 3)
    ck.eq("ingame emu 표적", len([c for c in model.created if c.ok and c.unit == 0 and c.player == 1]), 18)
    ck.eq("ingame emu dat: flingy 106 최고속도", m.dw(0x6CA0A0), 0xFFFFE0BF)
    ck.eq("ingame emu dat: 204 지상 무기", (m.dw(0x6636B8 + 204) & 0xFF), 127)
    ck.eq("ingame emu dat: 210 지상 무기·특수 능력", ((m.dw(0x6636B8 + 208) >> 16) & 0xFF, m.dw(0x664080 + 4 * 210)),
          (128, 0x20000004))
    ck.eq("ingame emu 흉내 못 낸 것", [k for k in m.unknown if k != ("act", 9)], [])


def eps_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    for name in ("bullet_example", "bullet_ingame"):
        work = os.path.join(_common.WORK, "t_bullet_build_" + name)
        eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
        print("  " + r.summary())
        ck.true("euddraft " + name, r.ok, r.log[-2000:])
        ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

COST_MEMORY = {"units": {}}
_CK = BulletKind()
_CKM = BulletKind(recipe="minimal")
_CK2 = BulletKind(recipe="m2")
_CKS = BulletKind(unit=210, shell=204)
_CKH = BulletKind(unit=206)
_CKO = BulletKind(flingy=173)


def _body_of(kind, mode, fkind, height=False, reverse=None):
    loc = None if mode == "at" else LOC
    key = bullet._Key(mode, fkind, kind.recipe, kind.y_offset if mode != "at" else 0, kind.timer,
                      kind.shell is not None, height, loc, reverse)
    return bullet._body(key)


def _no_slot(t):
    DoActions(SetMemory(NEXT, SetTo, 0))


COST_CASES = [
    CostCase("bullet (ue_re, 상수 방향, 변수 x·y)", lambda t: bullet.bullet(_CK, P8, t.var("x"), t.var("y"), 64),
             {"x": 100, "y": 200}, funcs=[_body_of(_CK, "own", "const")], target={"body": 40, "call": 3},
             note="S4 5.3 목표 본문 ≤ 40, 호출 ≤ 3"),
    CostCase("bullet (ue_re, 변수 방향·x·y)", lambda t: bullet.bullet(_CK, P8, t.var("x"), t.var("y"), t.var("f")),
             {"x": 100, "y": 200, "f": 0xFF}, funcs=[_body_of(_CK, "own", "var")], target={"body": 40, "call": 3},
             note="변수 인자 3개도 호출 자리 1 (변수 트리거를 VProc 으로 이음)"),
    CostCase("bullet (ue_re, 모두 상수)", lambda t: bullet.bullet(_CK, P8, 100, 200, 64),
             funcs=[_body_of(_CK, "own", "const")], target={"body": 40, "call": 3}),
    CostCase("bullet (minimal, 상수 방향)", lambda t: bullet.bullet(_CKM, P8, t.var("x"), t.var("y"), 64),
             {"x": 100, "y": 200}, funcs=[_body_of(_CKM, "own", "const")], target={"body": 40, "call": 3}),
    CostCase("bullet (m2, 변수 방향)", lambda t: bullet.bullet(_CK2, P8, t.var("x"), t.var("y"), t.var("f")),
             {"x": 100, "y": 200, "f": 3}, funcs=[_body_of(_CK2, "own", "var")], target={"body": 40, "call": 3},
             note="위치 4칸 복사"),
    CostCase("bullet (shell + 상수 높이)", lambda t: bullet.bullet(_CKS, P8, t.var("x"), t.var("y"), 64, height=20),
             {"x": 100, "y": 200}, funcs=[_body_of(_CKS, "own", "const", height=True)],
             target={"body": 40, "call": 3}),
    CostCase("bullet (변수 높이, 시프트 16)", lambda t: bullet.bullet(_CKH, P8, 1, 2, 64, height=t.var("h")), {"h": 20},
             funcs=[_body_of(_CKH, "own", "const", height=True), bullet._shift_fn(16, 8)],
             target={"body": 49, "call": 3}, note="본문 = bullet 본문 + 시프트 도우미(9). 호출 = 도우미 호출 + bullet 호출"),
    CostCase("bullet 빈 칸 없음 (실행)", lambda t: bullet.bullet(_CK, P8, t.var("x"), t.var("y"), 64),
             {"x": 100, "y": 200}, setup=_no_slot, note="첫 검사에서 실패 경로"),
    CostCase("bullet_to (변수 좌표 4)",
             lambda t: bullet.bullet_to(_CK, P8, t.var("x"), t.var("y"), t.var("tx"), t.var("ty")),
             {"x": 100, "y": 200, "tx": 900, "ty": 50}, funcs=[_body_of(_CK, "to", "var", reverse=True)],
             note="atan2(약 120)·to_dir256(20) 실행 포함, 두 본문은 따로(mathx)"),
    CostCase("bullet_to (좌표 모두 상수)", lambda t: bullet.bullet_to(_CK, P8, 100, 100, 101, 102),
             funcs=[_body_of(_CK, "own", "const")], note="방향을 컴파일 시점에 — bullet 상수 방향 본문과 같음"),
    CostCase("bullet_to 빈 칸 없음 (실행)",
             lambda t: bullet.bullet_to(_CK, P8, t.var("x"), t.var("y"), t.var("tx"), t.var("ty")),
             {"x": 100, "y": 200, "tx": 900, "ty": 50}, setup=_no_slot, note="atan2 를 돌기 전에 실패"),
    CostCase("bullet_at (변수 로케이션, 상수 방향)", lambda t: bullet.bullet_at(_CK, P8, t.var("l"), 64), {"l": 27},
             funcs=[_body_of(_CK, "at", "const")], target={"body": 40, "call": 3}),
    CostCase("heading_to_facing (변수)", lambda t: bullet.heading_to_facing(_CK, t.var("h")), {"h": 300}),
    CostCase("set_speed (변수, flingy 짝수)", lambda t: _CK.set_speed(t.var("v")), {"v": 500}),
    CostCase("set_speed (변수, flingy 홀수 + 변수 halt)", lambda t: _CKO.set_speed(t.var("v"), halt=t.var("h")),
             {"v": 500, "h": 3}, funcs=[bullet._shift_fn(16, 16)], note="가속도 윗 워드 시프트 도우미(17)"),
    CostCase("set_speed (상수)", lambda t: _CK.set_speed(500)),
    CostCase("set_time (변수, 시프트 24)", lambda t: _CK.set_time(t.var("v")), {"v": 32},
             funcs=[bullet._shift_fn(24, 8)]),
    CostCase("set_height (변수, 시프트 0)", lambda t: _CK.set_height(t.var("v")), {"v": 20}),
]


# =============================================================================================


def main():
    rng = random.Random(14)
    ck = Checker("t_bullet (python)")
    spec_checks(ck)
    dat_checks(ck)
    arg_checks(ck)

    s = Suite("t_bullet", memory={"units": {}})
    build_cases(s)
    s.build()
    env = Env(s, rng)
    run_spec63(s, env, rng)
    run_matrix(s, env, rng)
    run_sequences(s, env, rng)
    run_dat(s, env, rng)
    ok1 = s.report()

    cke = Checker("t_bullet (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    ingame_emulate(cke)
    eps_build(cke)
    finish(ok1, ck.report(), cke.report())


if __name__ == "__main__":
    main()
