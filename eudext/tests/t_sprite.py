"""`bullet` 3단계(CtrigAsm 28장 스프라이트) 시험 — 에뮬레이터 + scmodel 유닛 모델 (DESIGN 4.15·4.20, R4a A).

- 원문 대조: CtrigAsm v5.5 Lua 원문(`reference/MapSource/Library/CtrigAsm v5.5.lua`)에서 `BulletInitSetting`·`CreateStorm`·
  `CreateSprite`·`ScanInitSetting`·`ScanSprite`·`UnitSprite`·`RecallSprite`·`SetScanImage`·`SetRecallImage` 의 쓰기 줄을
  정규식으로 읽어 파이썬으로 계산한 **바이트**와 eudext 가 내는 액션·칸 값을 비교한다(가이드북 예제의 인자 + 무작위).
- 에뮬레이터: storm·perma_sprite·unit_sprite·recall_sprite 는 만든 CUnit 84칸 전부(보초값으로 마스크 밖 보존까지),
  scan_sprite·unit_sprite(track=False) 는 CreateUnit 기록·생성 순간의 dat(대기 주문·높이)·로케이션, 모든 함수의
  빈 칸 없음·생성 실패(실패 주입), CP 보존(여섯 값 × 성공·실패), 게임 메모리 쓰기 집합 ⊆ 허용 집합, 여러 발.
- 인자 검사(빌드 오류 기대), 인게임 확인 맵 `examples/sprite_ingame` 의 번역·에뮬레이션(710 사이클)·euddraft 빌드.

python tests/t_sprite.py
비용 표: python tools/cost.py tests/t_sprite.py [--append --bytes]
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
    P1,
    P8,
    CompressPayload,
    CurrentPlayer,
    DoActions,
    EUDVariable,
    LoadMap,
    SetMemory,
    SetTo,
    f_getcurpl,
    f_setcurpl,
)

import ref_bullet as RB  # noqa: E402

from eudext import _compat, bullet  # noqa: E402
from eudext import datpatch as dat  # noqa: E402
from eudext.bullet import BulletKind, CtrigKind  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import BASE_MAP, emu, scmodel  # noqa: E402
from eudext.testing.harness import EDGES32, Suite, rand32  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
LOC = 26  # 기준 맵 "Location 0" (총알 로케이션)
LOC27 = 27  # "CLoc"
MRGN = 0x58DC60
NEXT = 0x628438
FIRST_UNIT = 0x628430
CP_ADDR = 0x6509B0
UNIT_TABLE = 0x59CCA8
EX = os.path.join(_common.PKG, "examples")
CA = os.path.join(_common.ROOT, "reference", "MapSource", "Library", "CtrigAsm v5.5.lua")
ELEV = 0x663150
IDLE_ADDRS = (0x662EC0, 0x662288)  # 스캐너(33) 컴퓨터·사람 대기 주문 바이트가 든 dword (바이트 +1)

bullet.setup(loc=LOC)

# 시험 종류 (가이드북 예제 값). KDOT 은 모듈을 불러올 때 install → 시작 1회 목록 확인
KDOT = CtrigKind(unit=203, weapon=2, flingy=147, sprite=231, image=233, iscript=233, half_air=True)  # 29-4·29-5
KSTORM = CtrigKind(unit=19, weapon=0, flingy=162, sprite=356, image=380, iscript=236, splash=(10, 25, 50), upgrade=7)
KB = CtrigKind(unit=20, weapon=1, flingy=164, sprite=344, image=360, iscript=233, upgrade=7)  # 28-1 (flingy 만 바꿈)
KT0 = CtrigKind(unit=205, weapon=3, flingy=170, sprite=300, image=400, iscript=1, remove_timer=0, y_offset=0)
KU = BulletKind()  # UE_RE 종류로도 storm/perma 가 되는가
KF = BulletKind(unit=206, weapon=30, flingy=174, reverse=False, recipe="minimal")  # reverse=False 속도
KDOT.install()


def loc_addr(n):
    return MRGN + 20 * (n - 1)


def dw4(a):
    return a & ~3


# =============================================================================================
# CtrigAsm Lua 원문 읽기
# =============================================================================================

_TEXT = []
_WRITE = re.compile(
    r"\{?T?SetMemory(B|W|X|Dw)?[\(,]\s*(Vi\(NRet\[\d+\],\s*[^)]*\)|[^,]+?)\s*,\s*SetTo\s*,\s*([^,{}]+?|\{[^}]*\})"
    r"\s*(?:,\s*(0x[0-9A-Fa-f]+|\d+))?\s*[\)\}]")
_VI = re.compile(r"Vi\(NRet\[\d+\],\s*(.+)\)$")
_SIZE = {None: 4, "B": 1, "W": 2, "X": 4, "Dw": 4}


def lua_function(name):
    if not _TEXT:
        with open(CA, encoding="utf-8") as f:
            _TEXT.append(f.read())
    m = re.search(r"^function %s\(.*?^end[ \t]*$" % re.escape(name), _TEXT[0], re.M | re.S)
    if m is None:
        raise RuntimeError("CtrigAsm 원문에 %s 가 없습니다" % name)
    return m.group(0)


def lua_writes(name):
    """[(크기 종류, 주소 식, 값 식, 마스크 문자열)] — 변수 판(`{…}` 값)은 뺀다."""
    return [m.groups() for m in _WRITE.finditer(lua_function(name)) if not m.group(3).startswith("{")]


def ev(expr, ns):
    return int(eval(expr, {"__builtins__": {}}, ns))  # noqa: S307 — 원문 Lua 의 산술식(상수·이름·색인)


def put_bytes(mem, addr, size, value, mask):
    for b in range(size):
        mb = (mask >> (8 * b)) & 0xFF
        if mb:
            ov, om = mem.get(addr + b, (0, 0))
            mem[addr + b] = ((ov & ~mb) | ((value >> (8 * b)) & mb), om | mb)


def lua_dat_bytes(writes, ns):
    mem = {}
    for kind, a, v, mk in writes:
        size = _SIZE[kind]
        mask = int(mk, 0) if mk else (1 << (8 * size)) - 1
        put_bytes(mem, ev(a, ns), size, ev(v, ns) & M32, mask)
    return mem


def decode(act):
    """SetMemory/SetMemoryX 액션 → (주소, 수정자 이름, 값, 마스크). (t_bullet 과 같은 식)"""
    f = act.fields
    mods = {7: "SetTo", 8: "Add", 9: "Subtract"}
    addr = (0x58A364 + 4 * (f[6] * 12 + f[4])) & M32
    mask = (f[0] & M32) if f[11] == 0x4353 else M32
    return (addr, mods.get(f[8], f[8]), f[5] & M32, mask)


def act_bytes(acts):
    mem = {}
    for a in acts:
        addr, mod, val, mask = decode(a)
        if mod != "SetTo":
            raise RuntimeError("SetTo 가 아닌 액션 %r" % (mod,))
        put_bytes(mem, addr, 4, val, mask)
    return mem


def compare_bytes(ck, label, lua, eud, partial_ok=(), extra_ok=()):
    """lua 가 쓰는 바이트를 eud 가 같은 값으로 쓰는가. partial_ok: eud 가 일부 비트만 쓰고 나머지를 lua 가 0 으로 쓰는 바이트."""
    bad, partial = [], []
    for a, (lv, lm) in sorted(lua.items()):
        e = eud.get(a)
        if e is None:
            if lv == 0 and a in partial_ok:
                partial.append(a)
                continue
            bad.append("0x%X 안 씀 (원문 0x%02X)" % (a, lv))
            continue
        evv, em = e
        if (lv & em) != (evv & em) or (lv & lm & ~em) != 0:
            bad.append("0x%X: 0x%02X/%02X (원문 0x%02X/%02X)" % (a, evv, em, lv, lm))
        elif lm & ~em:
            if a not in partial_ok:
                bad.append("0x%X: 일부 비트만 (0x%02X/%02X, 원문 0x%02X/%02X)" % (a, evv, em, lv, lm))
            partial.append(a)
    more = sorted(set(eud) - set(lua) - set(extra_ok))
    ck.eq(label, bad + ["원문에 없는 0x%X" % a for a in more], [])
    return partial


def lua_patch(name, ns, skip_values=()):
    """생성 뒤 칸 쓰기 {EPD 오프셋: (값, 마스크)} — 원문의 `Vi(NRet[…], 오프셋)` 줄."""
    out = {}
    for kind, a, v, mk in lua_writes(name):
        m = _VI.match(a)
        if not m or v in skip_values:
            continue
        off = int(eval(m.group(1), {"__builtins__": {}}, {}))  # noqa: S307 — "0x58/4" 같은 식
        val = ns["POS"] if v.startswith("V(NRet") else ev(v, ns) & M32
        mask = int(mk, 0) if mk else M32
        ov, om = out.get(off, (0, 0))
        out[off] = ((ov & ~mask) | (val & mask), om | mask)
    return out


# 가이드북 예제의 BulletInitSetting 인자: (이름, UnitId 표, Weapon, Flingy, Sprite, Image, Script, Color, Damage, DamageUp,
#   UpgradeID, BulletNumber, DamageType, Special, Splash)  — 가이드북 줄 18031~18034, 18220, 18237~18238, 18403~18404, 18476
GB_INITS = [
    ("28-1a", (1, 74, 229), 2, 164, 354, 541, 395, 0, 0, 0, 7, 1, 0, 0, (10, 25, 50)),
    ("28-1b", (1, 74, 229), 2, 164, 354, 505, 235, 0, 0, 0, 7, 1, 0, 0, (10, 25, 50)),
    ("28-1c", (20, 74, 229), 1, 147, 344, 360, 233, 0, 0, 0, 7, 1, 0, 0, (0, 0, 0)),
    ("28-1d", (19, 74, 229), 0, 162, 356, 380, 236, 0, 0, 0, 7, 1, 0, 0, (10, 25, 50)),
    ("29-4", (1, 74, 229), 2, 147, 231, 233, 233, 0, 0, 0, 0, 1, 0, 0, (0, 0, 0)),
    ("29-5a", (203, 74, 229, 1), 2, 147, 231, 233, 233, 0, 0, 0, 0, 1, 0, 0, (0, 0, 0)),
    ("29-5b", (203, 74, 229, 1), 2, 147, 231, 210, 233, 10, 0, 0, 0, 1, 0, 0, (0, 0, 0)),
    ("29-7b", (204, 177, 385, 1), 1, 164, 386, 210, 233, 10, 0, 0, 0, 1, 0, 0, (0, 0, 0)),
    ("29-8", (203, 74, 229, 1), 2, 147, 231, 233, 233, 15, 0, 0, 0, 1, 0, 0, (0, 0, 0)),
]


def init_ns(args):
    _n, ut, w, f, s, i, sc, col, dmg, dup, up, bn, dt, sp, spl = args
    return {"UnitId": ut[0], "Weapon": w, "Flingy": f, "Sprite": s, "Image": i, "Script": sc, "Color": col,
            "Damage": dmg, "DamageUp": dup, "UpgradeID": up, "BulletNumber": bn, "DamageType": dt, "Special": sp,
            "Splash": {1: spl[0], 2: spl[1], 3: spl[2]}, "BulletUnitFlingy": ut[1], "BulletUnitSprite": ut[2]}


def init_kind(args, **kw):
    _n, ut, w, f, s, i, sc, col, dmg, dup, up, bn, dt, sp, spl = args
    return CtrigKind(unit=ut[0], unit_flingy=ut[1], unit_sprite=ut[2], half_air=len(ut) == 4 and ut[3] == 1,
                     weapon=w, flingy=f, sprite=s, image=i, iscript=sc, color=col, damage=dmg, damage_bonus=dup,
                     upgrade=up, count=bn, damage_type=dt, explosion=sp, splash=spl, **kw)


def lua_init_bytes(args):
    """BulletInitSetting 의 쓰기 바이트. TrapAct(if 반공중) 두 줄 / 아니면 두 줄을 골라 쓴다."""
    ws = lua_writes("BulletInitSetting")
    trap, rest = ws[:4], ws[4:]
    half = len(args[1]) == 4 and args[1][3] == 1
    ns = init_ns(args)
    mem = lua_dat_bytes(rest, ns)
    tns = dict(ns, UnitId={1: args[1][0]})
    for kind, a, v, mk in (trap[:2] if half else trap[2:]):
        size = _SIZE[kind]
        put_bytes(mem, ev(a, tns), size, ev(v, tns) & M32, (1 << (8 * size)) - 1)
    return mem


def weapon_flingy_upper(w):
    a = 0x656CA8 + 4 * w
    return {a + 1, a + 2, a + 3}


def full_iscript_byte(i):
    return {0x66D4D8 + i}


# =============================================================================================
# 파이썬 쪽
# =============================================================================================


def lua_checks(ck):
    rng = random.Random(2101)
    sets = list(GB_INITS)
    for j in range(40):
        ut = (rng.randrange(228), rng.randrange(209), rng.randrange(517)) + ((1,) if j % 2 else ())
        sets.append(("무작위%d" % j, ut, rng.randrange(130), rng.randrange(209), rng.randrange(517),
                     rng.randrange(999), rng.getrandbits(16), rng.randrange(256), rng.randrange(65536),
                     rng.randrange(65536), rng.randrange(256), rng.randrange(256), rng.randrange(256),
                     rng.randrange(256), (rng.randrange(65536), rng.randrange(65536), rng.randrange(65536))))
    n_partial = 0
    for args in sets:
        name = args[0]
        lua = lua_init_bytes(args)
        k0 = init_kind(args, carrier_iscript=None)
        got = act_bytes(k0.init_actions())
        partial = compare_bytes(ck, "BulletInitSetting %s = 원문" % name, lua, got,
                                partial_ok=weapon_flingy_upper(args[2]))
        n_partial += len(partial)
        # 기본(carrier_iscript=86): 원문 표 + 이미지 256 iscript ← 86 (CreateBullet 류가 부를 때마다 쓰는 줄)
        k1 = init_kind(args)
        got1 = act_bytes(k1.init_actions())
        lua1 = dict(lua)
        put_bytes(lua1, 0x66F048, 4, 86, M32)
        compare_bytes(ck, "BulletInitSetting %s + iscript86" % name, lua1, got1, partial_ok=weapon_flingy_upper(args[2]))
        ck.eq("CtrigKind %s 성질" % name, (k1.recipe, k1.timer, k1.y_offset, k1.reverse, k1.made_unit),
              ("ctrig", 6, -2, True, args[1][0]))
    ck.true("weapons.flingy 윗 3바이트만 원문과 다르게 안 씀 (원문 0)", n_partial == 3 * len(sets), str(n_partial))
    # install() 은 시작 1회 목록에 같은 액션을 넣는다
    ck.eq("install = 시작 목록", act_bytes(dat.actions(lambda d: bullet._declare_ctrig_table(d, KDOT))),
          act_bytes(KDOT.init_actions()))

    # CreateStorm / CreateSprite 가 부를 때마다 쓰는 dat (높이·이미지 256 줄 제외)
    for k in (KDOT, KSTORM, KB, KT0):
        bt = {k.unit: {1: k.weapon, 2: k.flingy, 3: k.sprite}}
        for img in (0, 1, 233, 380, 503, 998):
            for t in (0, 1, 30, 255):
                ns = {"UnitId": k.unit, "BulletTable": bt, "ImageID": img, "Time": t}
                ws = [w for w in lua_writes("CreateStorm") if not w[1].startswith(("Vi(", "0x66F048", "0x663150"))]
                acts, var_img = bullet._storm_dat_actions(k, img, t)
                ck.true("storm dat 상수 이미지 %d" % img, var_img is None, "")
                compare_bytes(ck, "CreateStorm dat unit %d img %d t %d" % (k.unit, img, t), lua_dat_bytes(ws, ns),
                              act_bytes(acts), partial_ok=full_iscript_byte(img))
        for sp in (0, 1, 1280, 8000, 0x7FFFFFFF, 0x80000000, M32):
            ns = {"UnitId": k.unit, "BulletTable": bt, "Speed": sp}
            ws = [w for w in lua_writes("CreateSprite") if not w[1].startswith(("Vi(", "0x66F048", "0x663150"))]
            compare_bytes(ck, "CreateSprite dat unit %d speed %d" % (k.unit, sp), lua_dat_bytes(ws, ns),
                          act_bytes(bullet._perma_dat_actions(k, sp)))
    ck.eq("perma dat reverse=False", [decode(a) for a in bullet._perma_dat_actions(KF, 700)][-1],
          (0x6C9EF8 + 4 * 174, "SetTo", 700, M32))
    # ScanInitSetting / SetScanImage / SetRecallImage
    compare_bytes(ck, "ScanInitSetting = 원문", lua_dat_bytes(lua_writes("ScanInitSetting"), {}),
                  act_bytes(bullet.scan_init_actions()))
    bad = []
    for i in range(999):
        for fn, lua_name in ((bullet.scan_image_actions, "SetScanImage"), (bullet.recall_image_actions, "SetRecallImage")):
            if act_bytes(fn(i)) != lua_dat_bytes(lua_writes(lua_name), {"ImageID": i}):
                bad.append((lua_name, i))
    ck.eq("SetScanImage·SetRecallImage 이미지 0~998 = 원문", bad, [])
    # ScanSprite 의 대기 주문 줄 (생성 전 0, 생성 뒤 140)
    ws = lua_writes("ScanSprite")
    ck.eq("ScanSprite 원문 줄", [(ev(a, {}), ev(v, {}), int(mk, 0)) for _k, a, v, mk in ws],
          [(IDLE_ADDRS[0], 0, 0xFF00), (IDLE_ADDRS[1], 0, 0xFF00), (IDLE_ADDRS[0], 140 << 8, 0xFF00),
           (IDLE_ADDRS[1], 140 << 8, 0xFF00)])
    # 칸 쓰기 표 (원문 식) — 에뮬레이터 판정이 이 값을 쓴다
    ck.eq("CreateStorm 칸 표", lua_patch("CreateStorm", {"Angle": 64 << 8, "POS": 0x1234}),
          {22: (0x1234, M32), 8: (64 << 8, 0xFF00), 19: (135 << 8, 0xFFFF00), 68: (6, 0xFFFF)})
    ck.eq("CreateSprite 칸 표 = CreateStorm", lua_patch("CreateSprite", {"Angle": 3 << 8, "POS": 7}),
          lua_patch("CreateStorm", {"Angle": 3 << 8, "POS": 7}))
    ck.eq("UnitSprite 칸 표", lua_patch("UnitSprite", {"Time": 48}),
          {68: (48, 0xFFFF), 55: (0x100, 0x100), 57: (0, M32)})
    ck.eq("RecallSprite 칸 표", lua_patch("RecallSprite", {"X": 0x12345, "Y": 0x6789A}),
          {22: (0x789A2345, M32), 19: (137 << 8, 0xFF00), 68: (3, 0xFFFF)})


def arg_checks(ck):
    LoadMap(BASE_MAP)
    ck.true("repr 안내", "const" in repr(KDOT) and "CtrigKind" in repr(KDOT), repr(KDOT))
    ck.eq("CtrigKind 기본값", (KDOT.unit_flingy, KDOT.unit_sprite, KDOT.color, KDOT.count, KDOT.splash,
                                KDOT.carrier_iscript), (74, 229, 0, 1, (0, 0, 0), 86))
    ck.eq("CtrigKind remove_timer=0", (KT0.timer, KT0.y_offset), (None, 0))
    ck.true("CtrigKind 는 BulletKind", isinstance(KDOT, BulletKind), "")
    ck.eq("CtrigKind 이름 유닛", CtrigKind(unit="Right Pit Door", weapon=1, flingy=1, sprite=1, image=1, iscript=1).unit, 208)
    ck.eq("RECIPES", bullet.RECIPES, ("ue_re", "m2", "minimal", "ctrig"))
    ck.eq("BulletKind(recipe='ctrig') 수명", BulletKind(recipe="ctrig").timer, 6)
    base = dict(unit=203, weapon=2, flingy=147, sprite=231, image=233, iscript=233)
    for label, kw in [
        ("weapon None", dict(base, weapon=None)),
        ("flingy None", dict(base, flingy=None)),
        ("sprite 범위", dict(base, sprite=517)),
        ("image 범위", dict(base, image=999)),
        ("unit_flingy 범위", dict(base, unit_flingy=209)),
        ("unit_sprite 범위", dict(base, unit_sprite=-1)),
        ("color 범위", dict(base, color=256)),
        ("damage 범위", dict(base, damage=65536)),
        ("upgrade 범위", dict(base, upgrade=256)),
        ("count 범위", dict(base, count=256)),
        ("splash 개수", dict(base, splash=(1, 2))),
        ("splash 범위", dict(base, splash=(1, 2, 65536))),
        ("half_air bool", dict(base, half_air=1)),
        ("iscript 실수", dict(base, iscript=1.5)),
        ("carrier_iscript 음수", dict(base, carrier_iscript=-1)),
        ("unit 범위", dict(base, unit=228)),
        ("remove_timer 범위", dict(base, remove_timer=65536)),
    ]:
        ck.raises("CtrigKind " + label, EudextError, lambda kw=kw: CtrigKind(**kw))
    for label, fn in [
        ("scan_image 범위", lambda: bullet.scan_image_actions(999)),
        ("scan_image 변수", lambda: bullet.scan_image_actions(EUDVariable())),
        ("recall_image 음수", lambda: bullet.recall_image_actions(-1)),
        ("recall_image 변수", lambda: bullet.recall_image_actions(EUDVariable())),
        ("epScript f_f_storm", lambda: bullet.f_f_storm),
        ("storm dat weapon 없음", lambda: bullet._storm_dat_actions(BulletKind(weapon=None), 1, 1)),
        ("perma dat flingy 없음", lambda: bullet._perma_dat_actions(BulletKind(flingy=None), 1)),
    ]:
        ck.raises(label, EudextError, fn)
    names = ("storm", "perma_sprite", "scan_sprite", "unit_sprite", "recall_sprite", "scan_init", "scan_init_actions",
             "scan_image_actions", "set_scan_image", "recall_image_actions", "set_recall_image")
    ck.true("f_ 별칭", all(getattr(bullet, n) is getattr(bullet, "f_" + n) for n in names), "")
    ck.true("__all__", all(n in bullet.__all__ and "f_" + n in bullet.__all__ for n in names), "")
    for n in bullet.__all__:
        ck.true("__all__ 이름 있음 " + n, hasattr(bullet, n), "")


# =============================================================================================
# 에뮬레이터 케이스
# =============================================================================================

STORM_KINDS = {"dot": KDOT, "st": KSTORM, "t0": KT0, "ku": KU}
PERMA_KINDS = {"dot": KDOT, "b": KB, "ku": KU, "kf": KF}
US_UNITS = {"u8": 8, "u205": 205, "u206": 206}  # 높이 칸 시프트 0 / 8 / 16


def build_cases(s):
    for name, k in STORM_KINDS.items():
        @s.case("st_v_" + name)
        def _(t, k=k):
            t.out("r", bullet.storm(k, t.var("o"), t.var("x"), t.var("y"), t.var("f"), t.var("img"), t.var("tm"),
                                    height=t.var("h")))

        @s.case("st_c_" + name)
        def _(t, k=k):
            t.out("r", bullet.storm(k, P8, t.var("x"), t.var("y"), 64, 380, 30))

    for name, k in PERMA_KINDS.items():
        @s.case("pm_v_" + name)
        def _(t, k=k):
            t.out("r", bullet.perma_sprite(k, t.var("o"), t.var("x"), t.var("y"), t.var("f"), speed=t.var("sp"),
                                           height=t.var("h")))

        @s.case("pm_c_" + name)
        def _(t, k=k):
            t.out("r", bullet.perma_sprite(k, P8, t.var("x"), t.var("y")))

    @s.case("pm_h")
    def _(t):
        t.out("r", bullet.perma_sprite(KDOT, P8, 100, 200, 3, speed=1280, height=77))

    @s.case("sc_v")
    def _(t):
        bullet.scan_sprite(t.var("o"), t.var("x"), t.var("y"), count=t.var("n"))

    @s.case("sc_c")
    def _(t):
        bullet.scan_sprite(P1, t.var("x"), t.var("y"))

    @s.case("sc_nr")
    def _(t):
        bullet.scan_sprite(P1, t.var("x"), t.var("y"), count=3, remove=False)

    for name, u in US_UNITS.items():
        @s.case("us_v_" + name)
        def _(t, u=u):
            t.out("r", bullet.unit_sprite(t.var("o"), u, t.var("x"), t.var("y"), height=t.var("h"), time=t.var("tm")))

        @s.case("us_x_" + name)
        def _(t, u=u):
            bullet.unit_sprite(t.var("o"), u, t.var("x"), t.var("y"), height=t.var("h"), track=False)

    @s.case("us_c")
    def _(t):
        t.out("r", bullet.unit_sprite(P1, 8, t.var("x"), t.var("y"), time=48))

    @s.case("us_n")
    def _(t):
        t.out("r", bullet.unit_sprite(P1, "Floor Missile Trap", t.var("x"), t.var("y"), height=3))

    @s.case("us_x0")
    def _(t):
        bullet.unit_sprite(P1, 206, t.var("x"), t.var("y"), track=False)

    @s.case("us_t0")
    def _(t):
        t.out("r", bullet.unit_sprite(P1, 8, t.var("x"), t.var("y"), time=0))

    @s.case("rc_v")
    def _(t):
        t.out("r", bullet.recall_sprite(t.var("o"), 86, t.var("x"), t.var("y")))

    @s.case("rc_at")
    def _(t):
        t.out("r", bullet.recall_sprite(t.var("o"), 86, t.var("x"), t.var("y"), loc=t.var("l")))

    @s.case("rc_c")
    def _(t):
        t.out("r", bullet.recall_sprite(P1, "Danimoth (Arbiter)", 0x12345, 0x6789A, loc="CLoc"))

    @s.case("rc_cxy")
    def _(t):
        t.out("r", bullet.recall_sprite(P1, 71, 1000, 2000))

    @s.case("img")
    def _(t):
        bullet.set_scan_image(t.var("a"))
        bullet.set_recall_image(t.var("b"))

    @s.case("img_c")
    def _(t):
        bullet.set_scan_image(391)
        bullet.set_recall_image(379)

    @s.case("init")
    def _(t):
        DoActions(bullet.scan_init_actions())
        DoActions(KSTORM.init_actions())

    for fn_name in ("storm", "perma", "us", "rc", "sc"):
        @s.case("cp_" + fn_name)
        def _(t, fn_name=fn_name):
            f_setcurpl(t.var("c"))
            x, y = t.var("x"), t.var("y")
            if fn_name == "storm":
                t.out("r", bullet.storm(KDOT, CurrentPlayer, x, y, 5, 380, 30))
            elif fn_name == "perma":
                t.out("r", bullet.perma_sprite(KDOT, P8, x, y, 5))
            elif fn_name == "us":
                t.out("r", bullet.unit_sprite(P1, 8, x, y, time=9))
            elif fn_name == "rc":
                t.out("r", bullet.recall_sprite(P1, 86, x, y, loc=LOC27))
            else:
                bullet.scan_sprite(CurrentPlayer, x, y)
            t.out("gc", f_getcurpl())
            t.watch("cpm", CP_ADDR)

    @s.case("multi")
    def _(t):
        x, y = t.var("x"), t.var("y")
        t.out("r1", bullet.perma_sprite(KDOT, P8, x, y, 0, height=1))
        t.out("r2", bullet.storm(KSTORM, P8, x, y, 64, 380, 30))
        bullet.scan_sprite(P1, x, y, count=2)
        t.out("r3", bullet.unit_sprite(P1, 8, x, y, time=5))
        t.out("r4", bullet.recall_sprite(P1, 86, x, y))
        bullet.unit_sprite(P1, 8, x, y, track=False)

    # 빌드 때 오류가 나야 하는 것
    def bad(name, fn, msg=None):
        s.case("err_" + name, expect_build_error=EudextError, expect_message=msg)(lambda t: fn(t))

    bad("storm_img", lambda t: bullet.storm(KDOT, P8, 0, 0, 0, 999, 1), "image")
    bad("storm_time", lambda t: bullet.storm(KDOT, P8, 0, 0, 0, 1, 256), "time")
    bad("storm_height", lambda t: bullet.storm(KDOT, P8, 0, 0, 0, 1, 1, height=256), "height")
    bad("storm_kind", lambda t: bullet.storm(5, P8, 0, 0, 0, 1, 1), "BulletKind")
    bad("storm_noweapon", lambda t: bullet.storm(BulletKind(weapon=None), P8, 0, 0, 0, 1, 1), "weapon")
    bad("storm_owner", lambda t: bullet.storm(KDOT, 14, 0, 0, 0, 1, 1), "owner")
    bad("storm_facing", lambda t: bullet.storm(KDOT, P8, 0, 0, 1.5, 1, 1), "facing")
    bad("perma_noflingy", lambda t: bullet.perma_sprite(BulletKind(flingy=None), P8, 0, 0), "flingy")
    bad("perma_speed", lambda t: bullet.perma_sprite(KDOT, P8, 0, 0, speed=1 << 32), "speed")
    bad("perma_height", lambda t: bullet.perma_sprite(KDOT, P8, 0, 0, height=-1), "height")
    bad("perma_x", lambda t: bullet.perma_sprite(KDOT, P8, True, 0), "x")
    bad("scan_count0", lambda t: bullet.scan_sprite(P1, 0, 0, count=0), "count")
    bad("scan_count256", lambda t: bullet.scan_sprite(P1, 0, 0, count=256), "count")
    bad("scan_remove", lambda t: bullet.scan_sprite(P1, 0, 0, remove=1), "remove")
    bad("scan_owner", lambda t: bullet.scan_sprite("AllPlayers", 0, 0), "owner")
    bad("us_varunit", lambda t: bullet.unit_sprite(P1, t.var("u"), 0, 0), "unit")
    bad("us_unit", lambda t: bullet.unit_sprite(P1, 228, 0, 0), "unit")
    bad("us_name", lambda t: bullet.unit_sprite(P1, "없는 유닛", 0, 0), "unit")
    bad("us_track", lambda t: bullet.unit_sprite(P1, 8, 0, 0, track=0), "track")
    bad("us_x_time", lambda t: bullet.unit_sprite(P1, 8, 0, 0, time=3, track=False), "time")
    bad("us_time", lambda t: bullet.unit_sprite(P1, 8, 0, 0, time=65536), "time")
    bad("us_height", lambda t: bullet.unit_sprite(P1, 8, 0, 0, height=300), "height")
    bad("rc_varunit", lambda t: bullet.recall_sprite(P1, t.var("u"), 0, 0), "unit")
    bad("rc_loc0", lambda t: bullet.recall_sprite(P1, 86, 0, 0, loc=0), "loc")
    bad("rc_locname", lambda t: bullet.recall_sprite(P1, 86, 0, 0, loc="없는 로케이션"), "로케이션")
    bad("rc_owner", lambda t: bullet.recall_sprite(12, 86, 0, 0), "owner")
    bad("set_scan_image", lambda t: bullet.set_scan_image(999), "image")
    bad("set_recall_image", lambda t: bullet.set_recall_image(True), "image")

    def bad_setup(t):
        bullet.setup(loc="없는 로케이션")
        try:
            bullet.scan_sprite(P1, 0, 0)
        finally:
            bullet.setup(loc=LOC)

    s.case("err_setup_name", expect_build_error=EudextError, expect_message="맵에 없습니다")(bad_setup)


# =============================================================================================
# 판정 도구
# =============================================================================================


WATCH_ADDRS = [ELEV + 8 & ~3, ELEV + 203 & ~3, ELEV + 205 & ~3, ELEV + 206 & ~3, ELEV + 19 & ~3, ELEV + 20 & ~3,
               ELEV + 86 & ~3, ELEV + 71 & ~3, ELEV + 208 & ~3] + list(IDLE_ADDRS)


class Env:
    def __init__(self, s, rng):
        self.s = s
        self.m = s.machine
        self.model = scmodel.unit_model(self.m)
        self.rng = rng
        self.lo, self.hi = self.m.base, self.m.limit_addr
        self.sent = {}
        self.before = {}
        self.at_create = []
        orig = self.m.act_handlers[scmodel.ACT_CREATE_UNIT]

        def rec(m, fields):
            # 생성 순간의 전역 dat (대기 주문·높이)와 로케이션
            self.at_create.append({a: m.dw(a) for a in WATCH_ADDRS})
            orig(m, fields)

        self.m.act_handlers[scmodel.ACT_CREATE_UNIT] = rec

    def ext(self):
        return {k: v for k, v in self.m.mem.items() if not self.lo <= k < self.hi}

    def fresh(self, head=5, fill=False, fail=0, loc27=None, cp=None, sentinel=True):
        self.s.reset()
        self.model.clear_log()
        self.model.clear_failures()
        self.model.set_free(list(range(head, 1700)) + list(range(head)))
        self.at_create = []
        self.sent = {}
        if sentinel:
            base = RB.ptr_of(head)
            for k in range(2, 84):
                v = self.rng.getrandbits(32)
                self.m.setdw(base + 4 * k, v)
                self.sent[k] = v
        for a in WATCH_ADDRS:  # 생성 순간 값을 알아볼 수 있게 보초값
            self.m.setdw(a, self.rng.getrandbits(32))
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


def expect_slot(env, unit, owner, pos, patch):
    exp = dict(env.sent)
    exp[10] = pos
    exp[19] = (exp[19] & ~0xFFFF & M32) | owner | (scmodel.ORDER_ON_CREATE << 8)
    exp[25] = (exp[25] & ~0xFFFF & M32) | unit
    exp[41] = (exp[41] & ~0xFF00 & M32) | ((((exp[41] >> 8) + 1) & 0xFF) << 8)
    exp[55] |= 1
    for k, (v, mk) in patch.items():
        exp[k] = (exp[k] & ~mk & M32) | (v & mk)
    return exp


def byte_in(dw, addr):
    return (dw >> (8 * (addr & 3))) & 0xFF


def body_scenario(s, env, case, inputs, label, *, unit, lua_name, ns, owner=7, x=0, y=0, yoff=0, loc=None,
                  loc27=None, height=None, head=5, fill=False, fail=0, cp=None, dat_addrs=(), extra_allowed=(),
                  skip_values=(), patch=None):
    """본문(칸 연산이 있는) 함수 한 번 실행 + 판정. loc=None 이면 총알 로케이션을 (x, y + yoff) 로 옮겨 만든다.

    칸 쓰기 기대값 = 원문 `lua_name` 의 Vi 줄(ns 로 계산). patch 를 주면 그것 + 위치 칸(22 ← 위치).
    """
    env.fresh(head, fill, fail, loc27, cp)
    r = s.run(case, inputs)
    ok = []

    def rec(lbl, cond, msg=""):
        ok.append(s.expect_true(case, cond, label + " / " + lbl, msg))

    if r.error:
        rec("실행", False, r.error)
        return False, r
    m, model = env.m, env.model
    created = model.created
    failed = fill or fail
    rec("반환", r["r"] == (0 if failed else RB.epd_of(head)), "r=%d" % r["r"])
    want_loc = LOC if loc is None else loc
    y2 = (y + yoff) & M32
    if fill:
        rec("CreateUnit 없음", created == [], repr(created))
    else:
        c = created[0] if len(created) == 1 else None
        rec("CreateUnit 기록", c is not None and (c.unit, c.player, c.loc, c.count, c.ok) ==
            (unit, owner, want_loc, 1, not fail), repr(created))
    allowed = set(extra_allowed) | set(dat_addrs)
    if loc is None and not fill:
        la = loc_addr(LOC)
        rect = [m.dw(la + 4 * i) for i in range(4)]
        rec("로케이션", rect == [x & M32, y2, x & M32, y2], repr(rect))
        allowed |= {la + 4 * i for i in range(4)}
    if height is not None and not fill:
        ea = ELEV + unit
        rec("생성 순간 높이", env.at_create and byte_in(env.at_create[0][ea & ~3], ea) == height & 0xFF,
            repr(env.at_create[:1]))
        allowed.add(ea & ~3)
    if not failed:
        base = RB.ptr_of(head)
        allowed |= {base + 4 * k for k in range(84)} | {NEXT, FIRST_UNIT}
        nxt = model.next_free()
        if nxt is not None:
            allowed.add(RB.ptr_of(nxt))
        if loc is None:
            pos = RB.pos_word(x, y2)
        else:
            lx, ly = model.loc_center(loc)
            pos = RB.pos_word(lx, ly)
        if patch is None:
            want = lua_patch(lua_name, dict(ns, POS=pos), skip_values)
        else:
            want = dict(patch)
            want[22] = (pos, M32)
        exp = expect_slot(env, unit, owner, pos, want)
        bad = []
        for k in range(2, 84):
            if k in (2, 3, 28):
                continue
            got = m.dw(base + 4 * k)
            if got != exp[k]:
                bad.append("+%d: 0x%08X 기대 0x%08X" % (k, got, exp[k]))
        rec("CUnit 칸", not bad, "; ".join(bad))
    changed = env.changed()
    rec("엉뚱한 쓰기 없음", changed <= allowed, ", ".join("0x%X" % a for a in sorted(changed - allowed)))
    return all(ok), r


def plain_scenario(s, env, case, inputs, label, *, unit, count=1, owner=0, x=0, y=0, height=None, remove=False,
                   head=5, fill=False, fail=0, cp=None, extra_allowed=()):
    """칸 연산 없는 생성(scan_sprite, unit_sprite track=False) 한 번 + 판정."""
    env.fresh(head, fill, fail, None, cp, sentinel=False)
    r = s.run(case, inputs)
    ok = []

    def rec(lbl, cond, msg=""):
        ok.append(s.expect_true(case, cond, label + " / " + lbl, msg))

    if r.error:
        rec("실행", False, r.error)
        return False, r
    m, model = env.m, env.model
    created = model.created
    c = created[0] if len(created) == 1 else None
    want_ok = not fill and not fail
    rec("CreateUnit 기록", c is not None and (c.unit, c.player, c.loc, c.count, c.ok) ==
        (unit, owner, LOC, count or 1, want_ok), repr(created))
    if want_ok:
        rec("만든 수", len(c.indices) == (count or 1), repr(c))
    la = loc_addr(LOC)
    rect = [m.dw(la + 4 * i) for i in range(4)]
    rec("로케이션", rect == [x & M32, y & M32, x & M32, y & M32], repr(rect))
    allowed = set(extra_allowed) | {la + 4 * i for i in range(4)} | {NEXT, FIRST_UNIT}
    allowed |= {UNIT_TABLE + a for a in range(0, 336 * 1700, 4)}  # 모델이 만든 유닛·목록 (라이브러리는 CUnit 을 안 씀)
    snap = env.at_create[0] if env.at_create else None
    if height is not None:
        ea = ELEV + unit
        rec("생성 순간 높이", snap is not None and byte_in(snap[ea & ~3], ea) == height & 0xFF, repr(snap))
        allowed.add(ea & ~3)
    for a in IDLE_ADDRS:
        b = (m.dw(a) >> 8) & 0xFF  # 스캐너(33) 대기 주문 = dword 의 둘째 바이트
        if remove:
            rec("생성 순간 대기 주문 0x%X" % a, snap is not None and (snap[a] >> 8) & 0xFF == 0, repr(snap))
            rec("뒤 대기 주문 140 (0x%X)" % a, b == 140, str(b))
            rec("대기 주문 밖 비트 (0x%X)" % a, m.dw(a) & ~0xFF00 & M32 == env.before.get(a, 0) & ~0xFF00 & M32, "")
            allowed.add(a)
        else:
            rec("대기 주문 그대로 (0x%X)" % a, m.dw(a) == env.before.get(a, 0), "")
    changed = env.changed()
    rec("엉뚱한 쓰기 없음", changed <= allowed, ", ".join("0x%X" % a for a in sorted(changed - allowed)))
    return all(ok), r


def storm_dat_addrs(k, img):
    return {dw4(0x656670 + k.weapon), dw4(0x657040 + k.weapon), 0x66EC48 + 4 * img, dw4(0x66D4D8 + img)}


def perma_dat_addrs(k):
    return {dw4(0x656670 + k.weapon), 0x6C9EF8 + 4 * k.flingy}


def check_storm_dat(s, env, case, label, k, img, t):
    m = env.m
    w = k.weapon
    got = (byte_in(m.dw(dw4(0x656670 + w)), 0x656670 + w), byte_in(m.dw(dw4(0x657040 + w)), 0x657040 + w),
           m.dw(0x66EC48 + 4 * img), byte_in(m.dw(dw4(0x66D4D8 + img)), 0x66D4D8 + img) & 1)
    s.expect_true(case, got == (3, t & 0xFF, 236, 1), label + " / dat", "%r" % (got,))
    # 한 비트·한 바이트 칸 밖은 그대로 (전체 iscript 칸은 이미지마다 1바이트)
    a = dw4(0x66D4D8 + img)
    keep = ~(1 << (8 * ((0x66D4D8 + img) & 3))) & M32
    a2 = dw4(0x657040 + w)
    keep2 = ~(0xFF << (8 * ((0x657040 + w) & 3))) & M32
    s.expect_true(case, m.dw(a) & keep == env.before.get(a, 0) & keep and
                  m.dw(a2) & keep2 == env.before.get(a2, 0) & keep2, label + " / 옆 칸 보존", "")


def check_perma_dat(s, env, case, label, k, sp):
    m = env.m
    got = (byte_in(m.dw(dw4(0x656670 + k.weapon)), 0x656670 + k.weapon), m.dw(0x6C9EF8 + 4 * k.flingy))
    want = (7, ((-sp) if k.reverse else sp) & M32)
    s.expect_true(case, got == want, label + " / dat", "%r 기대 %r" % (got, want))


def run_storm(s, env, rng):
    xs = [0, 1, 0x7FFF, 0x8000, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, M32]
    for name, k in STORM_KINDS.items():
        for j in range(14):
            o = rng.randrange(12)
            x = xs[j % 9] if j < 9 else rng.randrange(4096)
            y = xs[(j * 5) % 9] if j < 9 else rng.randrange(4096)
            f = EDGES32[j % 9] if j < 9 else rand32(rng)
            img = [0, 1, 2, 3, 380, 998, 997, 233, 4, 5, 6, 7, 511, 512][j]
            t = EDGES32[j % 9] if j < 9 else rng.randrange(256)
            h = EDGES32[(j + 3) % 9] if j < 9 else rng.randrange(256)
            label = "storm %s #%d" % (name, j)
            if k.recipe == "ctrig":
                ns = {"Angle": (f & 0xFF) << 8}
                body_scenario(s, env, "st_v_" + name, {"o": o, "x": x, "y": y, "f": f, "img": img, "tm": t, "h": h},
                              label, unit=k.made_unit, lua_name="CreateStorm", ns=ns, owner=o, x=x, y=y,
                              yoff=k.y_offset, height=h, head=rng.randrange(1700), dat_addrs=storm_dat_addrs(k, img),
                              skip_values=() if k.timer else ("6",))
            else:
                ue_scenario(s, env, "st_v_" + name, {"o": o, "x": x, "y": y, "f": f, "img": img, "tm": t, "h": h},
                            label, k, owner=o, x=x, y=y, facing=f, height=h, dat_addrs=storm_dat_addrs(k, img))
            check_storm_dat(s, env, "st_v_" + name, label, k, img, t)
        for j in range(3):
            x, y = rng.randrange(4096), rng.randrange(4096)
            label = "storm 상수 %s #%d" % (name, j)
            if k.recipe == "ctrig":
                body_scenario(s, env, "st_c_" + name, {"x": x, "y": y}, label, unit=k.made_unit,
                              lua_name="CreateStorm", ns={"Angle": 64 << 8}, owner=7, x=x, y=y, yoff=k.y_offset,
                              dat_addrs=storm_dat_addrs(k, 380), skip_values=() if k.timer else ("6",))
            else:
                ue_scenario(s, env, "st_c_" + name, {"x": x, "y": y}, label, k, owner=7, x=x, y=y, facing=64,
                            dat_addrs=storm_dat_addrs(k, 380))
            check_storm_dat(s, env, "st_c_" + name, label, k, 380, 30)
        # 실패 경로 (dat 는 쓴다 — CtrigAsm 과 다름, design.md)
        for fill, fail in ((True, 0), (False, 1)):
            label = "storm %s %s" % (name, "칸 없음" if fill else "생성 실패")
            inp = {"o": 3, "x": 5, "y": 6, "f": 7, "img": 380, "tm": 9, "h": 10}
            if k.recipe == "ctrig":
                body_scenario(s, env, "st_v_" + name, inp, label, unit=k.made_unit, lua_name="CreateStorm",
                              ns={"Angle": 7 << 8}, owner=3, x=5, y=6, yoff=k.y_offset, height=10, fill=fill,
                              fail=fail, dat_addrs=storm_dat_addrs(k, 380), extra_allowed={dw4(ELEV + k.made_unit)})
            else:
                ue_scenario(s, env, "st_v_" + name, inp, label, k, owner=3, x=5, y=6, facing=7, height=10, fill=fill,
                            fail=fail, dat_addrs=storm_dat_addrs(k, 380))
            check_storm_dat(s, env, "st_v_" + name, label, k, 380, 9)


def ue_scenario(s, env, case, inputs, label, k, *, owner, x, y, facing, height=None, fill=False, fail=0,
                dat_addrs=()):
    """1단계 종류(ue_re·minimal recipe)로 storm/perma 를 불렀을 때: 칸 쓰기는 1단계 bullet 과 같다(ref_bullet.patch)."""
    patch = RB.patch(k.recipe, facing, 0, k.remove_timer)
    patch.pop(22)
    return body_scenario(s, env, case, inputs, label, unit=k.made_unit, lua_name=None, ns={}, owner=owner, x=x, y=y,
                         yoff=k.y_offset, height=height, fill=fill, fail=fail, dat_addrs=dat_addrs, patch=patch,
                         extra_allowed={dw4(ELEV + k.made_unit)} if height is not None else ())


def run_perma(s, env, rng):
    sps = [0, 1, 1280, 8000, 0x7FFFFFFF, 0x80000000, M32]
    for name, k in PERMA_KINDS.items():
        for j in range(12):
            o = rng.randrange(12)
            x, y = rng.randrange(8192), rng.randrange(8192)
            f = rand32(rng)
            sp = sps[j % 7] if j < 7 else rand32(rng)
            h = rng.randrange(256) if j % 3 else EDGES32[j % 9]
            label = "perma %s #%d speed 0x%X" % (name, j, sp)
            inp = {"o": o, "x": x, "y": y, "f": f, "sp": sp, "h": h}
            if k.recipe == "ctrig":
                body_scenario(s, env, "pm_v_" + name, inp, label, unit=k.made_unit, lua_name="CreateSprite",
                              ns={"Angle": (f & 0xFF) << 8}, owner=o, x=x, y=y, yoff=k.y_offset, height=h,
                              head=rng.randrange(1700), dat_addrs=perma_dat_addrs(k))
            else:
                ue_scenario(s, env, "pm_v_" + name, inp, label, k, owner=o, x=x, y=y, facing=f, height=h,
                            dat_addrs=perma_dat_addrs(k))
            check_perma_dat(s, env, "pm_v_" + name, label, k, sp)
        x, y = rng.randrange(4096), rng.randrange(4096)
        label = "perma 기본값 %s" % name
        if k.recipe == "ctrig":
            body_scenario(s, env, "pm_c_" + name, {"x": x, "y": y}, label, unit=k.made_unit, lua_name="CreateSprite",
                          ns={"Angle": 0}, owner=7, x=x, y=y, yoff=k.y_offset, dat_addrs=perma_dat_addrs(k))
        else:
            ue_scenario(s, env, "pm_c_" + name, {"x": x, "y": y}, label, k, owner=7, x=x, y=y, facing=0,
                        dat_addrs=perma_dat_addrs(k))
        check_perma_dat(s, env, "pm_c_" + name, label, k, 0)
        for fill, fail in ((True, 0), (False, 1)):
            label = "perma %s %s" % (name, "칸 없음" if fill else "생성 실패")
            inp = {"o": 3, "x": 5, "y": 6, "f": 7, "sp": 9, "h": 10}
            if k.recipe == "ctrig":
                body_scenario(s, env, "pm_v_" + name, inp, label, unit=k.made_unit, lua_name="CreateSprite",
                              ns={"Angle": 7 << 8}, owner=3, x=5, y=6, yoff=k.y_offset, height=10, fill=fill,
                              fail=fail, dat_addrs=perma_dat_addrs(k), extra_allowed={dw4(ELEV + k.made_unit)})
            else:
                ue_scenario(s, env, "pm_v_" + name, inp, label, k, owner=3, x=5, y=6, facing=7, height=10, fill=fill,
                            fail=fail, dat_addrs=perma_dat_addrs(k))
            check_perma_dat(s, env, "pm_v_" + name, label, k, 9)
    body_scenario(s, env, "pm_h", {}, "perma 상수 높이·속도", unit=203, lua_name="CreateSprite", ns={"Angle": 3 << 8},
                  owner=7, x=100, y=200, yoff=-2, height=77, dat_addrs=perma_dat_addrs(KDOT))
    check_perma_dat(s, env, "pm_h", "perma 상수 높이·속도", KDOT, 1280)


def run_scan(s, env, rng):
    for j in range(16):
        o = rng.randrange(12)
        x, y = rand32(rng), rand32(rng)
        n = [1, 2, 3, 255, 256 + 7, 0x12345603][j % 6] if j < 12 else rng.randrange(1, 12)
        cnt = n & 0xFF
        plain_scenario(s, env, "sc_v", {"o": o, "x": x, "y": y, "n": n}, "scan 변수 #%d n=%d" % (j, n), unit=33,
                       count=cnt, owner=o, x=x, y=y, remove=True, head=rng.randrange(1400))
    for j in range(3):
        x, y = rng.randrange(4096), rng.randrange(4096)
        plain_scenario(s, env, "sc_c", {"x": x, "y": y}, "scan 기본 #%d" % j, unit=33, owner=0, x=x, y=y, remove=True)
        plain_scenario(s, env, "sc_nr", {"x": x, "y": y}, "scan remove=False #%d" % j, unit=33, count=3, owner=0,
                       x=x, y=y, remove=False)
    for fill, fail in ((True, 0), (False, 1)):
        plain_scenario(s, env, "sc_v", {"o": 2, "x": 1, "y": 2, "n": 2}, "scan %s" % ("칸 없음" if fill else "실패"),
                       unit=33, count=2, owner=2, x=1, y=2, remove=True, fill=fill, fail=fail)


def run_unit_sprite(s, env, rng):
    for name, u in US_UNITS.items():
        for j in range(10):
            o = rng.randrange(12)
            x, y = rand32(rng), rng.randrange(8192)
            h = rand32(rng)
            tm = [0, 1, 48, 0xFFFF, 0x10000, 0x12345678][j % 6] if j < 6 else rand32(rng)
            ns = {"Time": tm & M32}
            body_scenario(s, env, "us_v_" + name, {"o": o, "x": x, "y": y, "h": h, "tm": tm},
                          "unit_sprite %s #%d time 0x%X" % (name, j, tm), unit=u, lua_name="UnitSprite", ns=ns,
                          owner=o, x=x, y=y, height=h, head=rng.randrange(1700))
            plain_scenario(s, env, "us_x_" + name, {"o": o, "x": x, "y": y, "h": h},
                           "unit_sprite X %s #%d" % (name, j), unit=u, owner=o, x=x, y=y, height=h)
        for fill, fail in ((True, 0), (False, 1)):
            body_scenario(s, env, "us_v_" + name, {"o": 1, "x": 3, "y": 4, "h": 5, "tm": 6},
                          "unit_sprite %s %s" % (name, "칸 없음" if fill else "실패"), unit=u, lua_name="UnitSprite",
                          ns={"Time": 6}, owner=1, x=3, y=4, height=5, fill=fill, fail=fail,
                          extra_allowed={dw4(ELEV + u)})
            plain_scenario(s, env, "us_x_" + name, {"o": 1, "x": 3, "y": 4, "h": 5},
                           "unit_sprite X %s %s" % (name, "칸 없음" if fill else "실패"), unit=u, owner=1, x=3, y=4,
                           height=5, fill=fill, fail=fail)
    for j in range(3):
        x, y = rng.randrange(4096), rng.randrange(4096)
        body_scenario(s, env, "us_c", {"x": x, "y": y}, "unit_sprite 상수 수명 #%d" % j, unit=8,
                      lua_name="UnitSprite", ns={"Time": 48}, owner=0, x=x, y=y)
        body_scenario(s, env, "us_n", {"x": x, "y": y}, "unit_sprite 수명 없음 #%d" % j, unit=203,
                      lua_name="UnitSprite", ns={}, owner=0, x=x, y=y, height=3, skip_values=("Time",))
        body_scenario(s, env, "us_t0", {"x": x, "y": y}, "unit_sprite time=0 #%d" % j, unit=8,
                      lua_name="UnitSprite", ns={}, owner=0, x=x, y=y, skip_values=("Time",))
        plain_scenario(s, env, "us_x0", {"x": x, "y": y}, "unit_sprite X 높이 없음 #%d" % j, unit=206, owner=0, x=x, y=y)


def run_recall(s, env, rng):
    for j in range(14):
        o = rng.randrange(12)
        x, y = rand32(rng), rand32(rng)
        ns = {"X": x, "Y": y}
        body_scenario(s, env, "rc_v", {"o": o, "x": x, "y": y}, "recall 제자리 #%d" % j, unit=86,
                      lua_name="RecallSprite", ns=ns, owner=o, x=x, y=y, head=rng.randrange(1700))
        rect = (rng.randrange(4000), rng.randrange(4000))
        rect = rect + (rect[0] + rng.randrange(64), rect[1] + rng.randrange(64))
        body_scenario(s, env, "rc_at", {"o": o, "x": x, "y": y, "l": LOC27}, "recall 로케이션 #%d" % j, unit=86,
                      lua_name="RecallSprite", ns=ns, owner=o, x=x, y=y, loc=LOC27, loc27=rect,
                      head=rng.randrange(1700))
    for fill, fail in ((True, 0), (False, 1)):
        body_scenario(s, env, "rc_v", {"o": 1, "x": 2, "y": 3}, "recall %s" % ("칸 없음" if fill else "실패"),
                      unit=86, lua_name="RecallSprite", ns={"X": 2, "Y": 3}, owner=1, x=2, y=3, fill=fill, fail=fail)
        body_scenario(s, env, "rc_at", {"o": 1, "x": 2, "y": 3, "l": LOC27},
                      "recall 로케이션 %s" % ("칸 없음" if fill else "실패"), unit=86, lua_name="RecallSprite",
                      ns={"X": 2, "Y": 3}, owner=1, x=2, y=3, loc=LOC27, loc27=(10, 20, 30, 40), fill=fill, fail=fail)
    body_scenario(s, env, "rc_c", {}, "recall 상수·이름", unit=86, lua_name="RecallSprite",
                  ns={"X": 0x12345, "Y": 0x6789A}, owner=0, x=0x12345, y=0x6789A, loc=LOC27, loc27=(1312, 1216, 1440, 1312))
    body_scenario(s, env, "rc_cxy", {}, "recall 상수 제자리 (71)", unit=71, lua_name="RecallSprite",
                  ns={"X": 1000, "Y": 2000}, owner=0, x=1000, y=2000)


def run_misc(s, env, rng):
    m = env.m
    for a, b in ((0, 0), (391, 379), (998, 1), (0x12345, 0xABCDE), (M32, M32)):
        env.fresh(sentinel=False)
        before = (m.dw(0x666458), m.dw(0x666454))
        r = s.run("img", {"a": a, "b": b})
        got = (m.dw(0x666458), m.dw(0x666454))
        want = ((before[0] & ~0xFFFF & M32) | (a & 0xFFFF), (before[1] & 0xFFFF) | ((b & 0xFFFF) << 16))
        s.expect_true("img", got == want and not r.error, "set_scan/recall_image %d %d" % (a, b),
                      "%r 기대 %r %s" % (got, want, r.error))
        s.expect_true("img", env.changed() <= {0x666458, 0x666454}, "set_*_image 쓰기 칸", "")
    env.fresh(sentinel=False)
    r = s.run("img_c", {})
    s.expect_true("img_c", ((m.dw(0x666458) & 0xFFFF), m.dw(0x666454) >> 16) == (391, 379) and not r.error,
                  "set_*_image 상수", "")
    env.fresh(sentinel=False)
    r = s.run("init", {})
    mem = act_bytes(bullet.scan_init_actions() + KSTORM.init_actions())
    bad = [hex(a) for a, (v, mk) in mem.items() if (m.dw(a & ~3) >> (8 * (a & 3))) & mk != v & mk]
    s.expect_true("init", not bad and not r.error, "scan_init + init_actions 실행", repr(bad))
    # 시작 1회 목록 (KDOT.install): 초기화 사이클 뒤 메모리에 들어 있다
    s.reset()
    mem = act_bytes(KDOT.init_actions())
    bad = [hex(a) for a, (v, mk) in mem.items() if (m.dw(a & ~3) >> (8 * (a & 3))) & mk != v & mk]
    s.expect_true("init", not bad and len(mem) > 60, "install() → 게임 시작 때 적용", repr(bad))
    # CP 보존 (성공·실패 경로)
    for fn_name in ("storm", "perma", "us", "rc", "sc"):
        case = "cp_" + fn_name
        for cpv in (0, 1, 7, 11, 0x12345, M32):
            for fill, fail in ((False, 0), (True, 0), (False, 1)):
                env.fresh(fill=fill, fail=fail, cp=0, loc27=(10, 20, 30, 40))
                r = s.run(case, {"c": cpv, "x": 3, "y": 4})
                s.expect_true(case, r.values.get("cpm") == cpv and r.values.get("gc") == cpv and not r.error,
                              "CP 0x%X (%s)" % (cpv, "칸 없음" if fill else "실패" if fail else "성공"),
                              "%r %s" % (r.values, r.error))
                if fn_name in ("storm", "sc") and not fill and not fail and cpv < 12:
                    s.expect_true(case, bool(env.model.created) and env.model.created[0].player == cpv,
                                  "CurrentPlayer = CP 0x%X" % cpv, repr(env.model.created))
    # 여러 발 한 사이클
    env.fresh(head=40, sentinel=False)
    r = s.run("multi", {"x": 500, "y": 600})
    got = [r.values.get(n) for n in ("r1", "r2", "r3", "r4")]
    # 순서: perma(40) storm(41) scan×2(42·43) unit_sprite(44) recall(45) unit_sprite X(46)
    want = [RB.epd_of(40), RB.epd_of(41), RB.epd_of(44), RB.epd_of(45)]
    s.expect_true("multi", got == want and not r.error, "여러 발 반환", "%r 기대 %r %s" % (got, want, r.error))
    s.expect_true("multi", [(c.unit, c.count) for c in env.model.created] ==
                  [(203, 1), (19, 1), (33, 2), (8, 1), (86, 1), (8, 1)], "여러 발 종류", repr(env.model.created))
    model = env.model
    s.expect_true("multi", [(model.get(i, 0x4D, 1), model.get(i, 0x110, 2)) for i in (40, 41, 44, 45)] ==
                  [(135, 6), (135, 6), (scmodel.ORDER_ON_CREATE, 5), (137, 3)], "여러 발 주문·수명",
                  repr([(model.get(i, 0x4D, 1), model.get(i, 0x110, 2)) for i in (40, 41, 44, 45)]))
    s.expect_true("multi", [(model.pos(i)) for i in (40, 41, 45)] == [(500, 598), (500, 598), (500, 600)],
                  "여러 발 위치(ctrig 는 y − 2)", repr([(model.pos(i)) for i in (40, 41, 45)]))


# =============================================================================================
# 인게임 확인 맵
# =============================================================================================


def _load_eps(name, work_name):
    from eudext.tools import build

    work = os.path.join(_common.WORK, work_name)
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name), os.path.join(work, name))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, name), {})


def eps_checks(ck):
    src = open(os.path.join(EX, "sprite_ingame.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("sprite_ingame.eps", src)
    ck.eq("ingame eps errors", nerr, 0)
    for needle in ("bullet.CtrigKind(unit=203, weapon=2, flingy=147", "kDot.install()", "bullet.f_scan_init()",
                   "bullet.f_perma_sprite(kDot, P1,", "bullet.f_storm(kStorm, P1, 1200, 1000, 0, 380, 30)",
                   "bullet.f_unit_sprite(P1, 8, 2100, 1000, track=False)", "bullet.f_scan_sprite(P1, 2800, 1000, count=3)",
                   "bullet.f_recall_sprite(P1, 86, 3200, 1600, loc=25)", "bullet.f_set_scan_image(391)",
                   "bullet.f_recall_image_actions(379)", "cgrp.CGRP.load(\"sprite_user.cgrp\", missing_ok=True)",
                   "cgrp.CGRPPainter(", "painter.tick()"):
        ck.true("eps: " + needle, out is not None and needle in out, "")
    bad = _compat.eps_compile("bad.eps", "import eudext.bullet as bullet;\nfunction g() { bullet.f_storm(0); }")[0]
    ck.true("eps: bullet.f_storm → f_f_storm", bad is not None and "bullet.f_f_storm(" in bad, "")


def ingame_emulate(ck):
    """인게임 확인 맵을 에뮬레이터에서 710 사이클 돌린다(실행 오류·흐름·반환값)."""
    mod = _load_eps("sprite_ingame.eps", "t_sprite_ingame")
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "dotMade", "dotZero", "bounceE", "stormE", "stormE2", "usE", "usMoving", "recE", "recE2",
             "marine", "fillMade", "fullZero", "paintDone", "userDone")
    for n in names:
        prog.watch(n, getattr(mod, n))
    pd = mod.painter
    prog.watch("drawn", pd.drawn)
    prog.watch("dropped", pd.dropped)
    m = prog.build()
    scmodel.install(m, units={})
    model = scmodel.unit_model(m)
    for i in range(66):  # 기준 맵처럼 P1 맵 리빌러 64 + 시작 위치 2
        model.spawn(101 if i < 64 else 214, 0)
    err = None
    try:
        for cyc in range(710):
            if cyc % 10 == 5:
                model.process_deaths()
            m.cycle()
    except emu.EmuError as e:
        err = str(e)
    got = {n: m.var(n) for n in names}
    print("  인게임 맵 에뮬레이션: %r, 기록 %d" % (got, len(model.created)))
    ck.eq("ingame emu 오류", err, None)
    nonzero = ("bounceE", "stormE", "stormE2", "usE", "recE", "recE2", "marine")
    ck.eq("ingame emu 0 아닌 값", [n for n in nonzero if not got[n]], [])
    ck.eq("ingame emu 값", {n: got[n] for n in names if n not in nonzero},
          {"frame": 710, "dotMade": 16, "dotZero": 0, "usMoving": 61, "fillMade": 1700 - 66 - 16 - 1 - 2 - 2 - 61 - 5
           - 1 - 2 - pd.total, "fullZero": 1, "paintDone": 1, "userDone": 1})
    # 합성 그림 24×6: 1·6행 24, 2·5행 6, 3·4행 각 30(R 2 + r 4×2 + G 2 + # 4 + B 2 + k 4×3) → 120
    ck.eq("ingame emu 그림 점", (m.var("drawn"), m.var("dropped"), pd.total), (120, 0, 120))
    ck.eq("ingame 사용자 그림 (파일 없음)", (mod.userCg.found, mod.userPainter.total), (0, 0))
    kinds = sorted({(c.unit, c.count) for c in model.created if c.ok})
    ck.eq("ingame emu 만든 종류", kinds, [(0, 1), (8, 1), (19, 1), (20, 1), (33, 1), (33, 3), (86, 1), (101, 1),
                                         (203, 1)])
    ck.eq("ingame emu dat: 이미지 256 iscript 86", m.dw(0x66F048), 86)
    ck.eq("ingame emu dat: 기술 21 마나 0", m.dw(0x6563A8) >> 16, 0)
    ck.eq("ingame emu 흉내 못 낸 것", [k for k in m.unknown if k != ("act", 9)], [])


def eps_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    name = "sprite_ingame"
    work = os.path.join(_common.WORK, "t_sprite_build_" + name)
    eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
    r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
    print("  " + r.summary())
    ck.true("euddraft " + name, r.ok, r.log[-2000:])
    ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")
    ck.true("unlimiter 실음 " + name, "unlimiter" in r.log.lower(), "")


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

COST_MEMORY = {"units": {}}


def _body_of(kind, height=False):
    return bullet._body(bullet._Key("own", "const", kind.recipe, kind.y_offset, kind.timer, False, height, LOC, None))


def _sprite_body(recipe, mode, timer, height=False):
    return bullet._body(bullet._Key(mode, "none", recipe, 0, timer, False, height, LOC if mode == "own" else None,
                                    None))


def _no_slot(t):
    DoActions(SetMemory(NEXT, SetTo, 0))


COST_CASES = [
    CostCase("storm (상수 이미지·수명, 변수 x·y)", lambda t: bullet.storm(KDOT, P8, t.var("x"), t.var("y"), 0, 380, 30),
             {"x": 100, "y": 200}, funcs=[_body_of(KDOT)], target={"body": 40, "call": 3},
             note="dat 1 트리거 + bullet(ctrig) 본문"),
    CostCase("storm (변수 이미지·수명·높이)",
             lambda t: bullet.storm(KDOT, P8, t.var("x"), t.var("y"), 0, t.var("i"), t.var("t"), height=t.var("h")),
             {"x": 100, "y": 200, "i": 380, "t": 30, "h": 4},
             funcs=[_body_of(KDOT, True), bullet._shift_fn(24, 8), bullet._shift_fn(16, 8), bullet._storm_image_fn()],
             target={"call": 6}, note="변수 dat 인자 3개: 이미지 공유 본문(20) 1 + 수명 도우미 1 + 변수 값 액션 2 + 높이 도우미 1 + 본문 1"),
    CostCase("perma_sprite (상수 속도 0, 변수 x·y)", lambda t: bullet.perma_sprite(KDOT, P8, t.var("x"), t.var("y")),
             {"x": 100, "y": 200}, funcs=[_body_of(KDOT)], target={"body": 40, "call": 3},
             note="CGRP 점 하나와 같은 본문"),
    CostCase("perma_sprite (변수 속도)", lambda t: bullet.perma_sprite(KDOT, P8, t.var("x"), t.var("y"), 0,
                                                                   speed=t.var("s")),
             {"x": 100, "y": 200, "s": 1280}, funcs=[_body_of(KDOT)], target={"call": 3}, note="−speed 액션 3"),
    CostCase("perma_sprite 빈 칸 없음 (실행)", lambda t: bullet.perma_sprite(KDOT, P8, t.var("x"), t.var("y")),
             {"x": 100, "y": 200}, setup=_no_slot, note="dat 는 쓰고 본문 첫 검사에서 실패"),
    CostCase("scan_sprite (상수 수)", lambda t: bullet.scan_sprite(P1, t.var("x"), t.var("y")), {"x": 100, "y": 200},
             funcs=[bullet._plain_body(bullet._PKey(LOC, False, True))], target={"body": 40, "call": 3},
             note="칸 연산 없음 (0틱)"),
    CostCase("scan_sprite (변수 수)", lambda t: bullet.scan_sprite(P1, t.var("x"), t.var("y"), count=t.var("n")),
             {"x": 100, "y": 200, "n": 3},
             funcs=[bullet._plain_body(bullet._PKey(LOC, False, True)), bullet._shift_fn(24, 8)],
             note="수 << 24 시프트 도우미"),
    CostCase("unit_sprite (상수 수명)", lambda t: bullet.unit_sprite(P1, 8, t.var("x"), t.var("y"), time=48),
             {"x": 100, "y": 200}, funcs=[_sprite_body("unit_sprite", "own", 48)], target={"body": 40, "call": 3},
             note="위치 읽기 없음"),
    CostCase("unit_sprite (변수 높이·수명)",
             lambda t: bullet.unit_sprite(P1, 8, t.var("x"), t.var("y"), height=t.var("h"), time=t.var("t")),
             {"x": 100, "y": 200, "h": 3, "t": 48}, funcs=[_sprite_body("unit_sprite", "own", "var", True)],
             target={"body": 40, "call": 3}),
    CostCase("unit_sprite (track=False)", lambda t: bullet.unit_sprite(P1, 8, t.var("x"), t.var("y"), track=False),
             {"x": 100, "y": 200}, funcs=[bullet._plain_body(bullet._PKey(LOC, False, False))],
             target={"body": 40, "call": 3}, note="CtrigAsm Time=\"X\""),
    CostCase("recall_sprite (제자리, 변수 x·y)", lambda t: bullet.recall_sprite(P1, 86, t.var("x"), t.var("y")),
             {"x": 100, "y": 200}, funcs=[_sprite_body("recall", "own", 3), bullet._shift_fn(16, 16)],
             target={"call": 3}, note="y·65536 시프트 도우미(17) 포함"),
    CostCase("recall_sprite (로케이션, 상수)", lambda t: bullet.recall_sprite(P1, 86, 1000, 2000, loc=LOC27),
             funcs=[_sprite_body("recall", "at", 3)], target={"body": 40, "call": 3}),
    CostCase("set_scan_image (변수)", lambda t: bullet.set_scan_image(t.var("i")), {"i": 391}),
    CostCase("set_recall_image (변수)", lambda t: bullet.set_recall_image(t.var("i")), {"i": 379},
             funcs=[bullet._shift_fn(16, 16)]),
]


# =============================================================================================


def main():
    rng = random.Random(21)
    ck = Checker("t_sprite (python)")
    lua_checks(ck)
    arg_checks(ck)

    s = Suite("t_sprite", memory={"units": {}})
    build_cases(s)
    s.build()
    env = Env(s, rng)
    run_storm(s, env, rng)
    run_perma(s, env, rng)
    run_scan(s, env, rng)
    run_unit_sprite(s, env, rng)
    run_recall(s, env, rng)
    run_misc(s, env, rng)
    ok1 = s.report()

    cke = Checker("t_sprite (epScript)")
    eps_checks(cke)
    ingame_emulate(cke)
    eps_build(cke)
    finish(ok1, ck.report(), cke.report())


if __name__ == "__main__":
    main()
