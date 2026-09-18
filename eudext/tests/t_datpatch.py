"""`datpatch` 시험: 주소표 전수 대조, S5 A.8 액션 기대값, TEP 변환·경고(D19), 64개 묶음 경계,
에뮬레이터(시작 1회·매 프레임·조건 목록·now·temporary 되돌리기), EUD Editor 목록, epScript 예제 번역·빌드.

python tests/t_datpatch.py
비용 표: python tools/cost.py tests/t_datpatch.py [--append --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import math  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import warnings  # noqa: E402

import eudplib as ep  # noqa: E402
from eudplib import (  # noqa: E402
    EPD,
    CompressPayload,
    DoActions,
    EUDArray,
    EUDEndIf,
    EUDIf,
    EUDOnStart,
    EUDVariable,
    GetTriggerCounter,
    LoadMap,
    SetMemory,
    SetMemoryX,
    SetTo,
    f_bread_epd,
    f_dwread_epd,
    f_wread_epd,
)

from eudext import _compat  # noqa: E402
from eudext import datpatch as dat  # noqa: E402
from eudext import datpatch_tables as tb  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import emu  # noqa: E402
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
REF = os.path.join(_common.ROOT, "reference")
M2_DAT = os.path.join(REF, "MapSource", "MSF_Memory_2", "EUDEditorDat.lua")
UERE_DAT = os.path.join(REF, "MapSource", "MSF_UE_RE", "EUDEditorDat.lua")
SEED_PY = os.path.join(REF, "theSeed", "DataEditor.py")
DPS_PY = os.path.join(REF, "DPS_Enhance-eudplib-port", "build", "eudplibData", "DataEditor.py")
TPL_FUNC = os.path.join(REF, "MSF-Template", "func.lua")
SEED_FUNC = os.path.join(REF, "theSeed", "Engine", "func.lua")
EX = os.path.join(_common.PKG, "examples")

warnings.simplefilter("ignore", ep.EPWarning)  # 경고는 dat.tep.warnings 로 센다


# ---------------------------------------------------------------------------------------------
# 도우미
# ---------------------------------------------------------------------------------------------


def dec(act):
    """eudplib 액션 → ("SetMemory"|"SetMemoryX", 주소, 수정자, 값, 마스크). datpatch 와 따로 짠 해독기."""
    f = act.fields
    locid, p1, p2, unit, atype, amount, eudx = f[0], f[4], f[5], f[6], f[7], f[8], f[11]
    assert atype == 45, atype
    kind = "SetMemoryX" if eudx == 0x4353 else "SetMemory"
    mod = {7: "SetTo", 8: "Add", 9: "Subtract"}[amount]
    a = (0x58A364 + 4 * (p1 + 12 * unit)) & M32
    return (kind, a, mod, p2 & M32, (locid & M32) if kind == "SetMemoryX" else M32)


def X(a, v, m):
    return ("SetMemoryX", a, "SetTo", v, m)


def S(a, v, mod="SetTo"):
    return ("SetMemory", a, mod, v & M32, M32)


def loc(base, stride, idx, width, first=0):
    """독립 계산: (정렬 주소, 시프트, 마스크)."""
    off = base + (idx - first) * stride
    sub = off & 3
    return off - sub, 8 * sub, (((1 << (8 * width)) - 1) << (8 * sub)) & M32


def W(base, stride, idx, width, value):
    a, sh, m = loc(base, stride, idx, width)
    if m == M32:
        return S(a, value)
    return X(a, (value << sh) & m, m)


def acts_of(fn, merge=False):
    lst = dat.PatchList("t")
    fn(lst)
    return [dec(a) for a in lst.actions(merge=merge)]


def tep_acts(method, *args, **kw):
    lst = dat.PatchList("t")
    getattr(dat.tep, method)(*args, target=lst, **kw)
    return [dec(a) for a in lst.actions(merge=False)]


# ---------------------------------------------------------------------------------------------
# (1) 주소표 전수 대조
# ---------------------------------------------------------------------------------------------


def table_checks(ck):
    classes = {"units": ep.TrgUnit, "weapons": ep.Weapon, "flingy": ep.Flingy, "upgrades": ep.Upgrade,
               "techdata": ep.Tech, "sprites": ep.Sprite, "images": ep.Image}
    n_members = 0
    for d, cls in classes.items():
        first, last, _s = cls.range
        ck.eq("count %s" % d, last - first + 1, tb.SPEC_COUNTS[d])
        for name, desc in _compat.scdata_members(cls):
            info = _compat.scdata_member_info(desc)
            if not info["implemented"]:
                ck.true("not implemented %s.%s is eudext" % (d, name), dat.field(d, name).member is None)
                continue
            f = dat.field(d, name)
            n_members += 1
            ck.true("member %s.%s" % (d, name), f.member is desc)
            # 디스크립터 공개 속성과 직접 대조 (_compat 결과가 아닌 원본 값)
            ck.eq("offset %s.%s" % (d, name), f.base, desc.offset)
            ck.eq("stride %s.%s" % (d, name), f.stride, desc.stride)
            ck.eq("size %s.%s" % (d, name), f.size, desc.kind.size())
            want_bit = {"Bit0Kind": 1, "Bit1Kind": 2}.get(desc.kind.__name__)
            ck.eq("bit %s.%s" % (d, name), f.bit, want_bit)
            want_count = tb.COUNT_OVERRIDE.get((d, name), tb.SPEC_COUNTS[d])
            ck.eq("count %s.%s" % (d, name), f.count, want_count)
            # 상수 번호 주소 = scdata 가 쓰는 divmod(offset + i·stride, 4)
            for i in (0, 1, 2, 3, f.last):
                q, r = divmod(desc.offset + i * desc.stride, 4)
                a, sh, m = f.location(i)
                ck.eq("loc %s.%s[%d]" % (d, name, i), (a, sh), (q * 4, 8 * r))
    ck.true("scdata member count", n_members >= 120, str(n_members))
    # eudext 전용 필드: scdata 에서 읽은 주소
    ck.eq("buildingDimX", dat.field("units", "buildingDimX").base, ep.TrgUnit.buildingDimensions.offset)
    ck.eq("buildingDimY", dat.field("units", "buildingDimY").base, ep.TrgUnit.buildingDimensions.offset + 2)
    ck.eq("addonPlacement", dat.field("units", "addonPlacement").base, ep.TrgUnit.addonPlacement.offset)
    ck.eq("computerAI", dat.field("units", "computerAI").base, ep.TrgUnit.ignoreStrategicSuicideMissions.offset)
    ck.eq("addon first/count", (dat.field("units", "addonPlacementY").first, dat.field("units", "addonPlacementY").last), (106, 201))
    ck.eq("infestation", (dat.field("units", "infestationUnit").base, dat.field("units", "infestationUnit").last), (0x664980, 201))
    # 표끼리 겹치지 않는다 (원소 수 검증: 106칸 소리 필드 등)
    for d in list(classes) + ["players", "damage"]:
        spans = {}
        for name in dat.field_names(d):
            f = dat.field(d, name)
            start = f.base - (f.base % f.stride)
            span = (start, start + f.count * f.stride, f.stride)
            spans.setdefault(start, set()).add((span, name))
        items = sorted(spans.items())
        for (s0, group0), (s1, _g1) in zip(items, items[1:]):
            ends = {sp[1] for sp, _n in group0}
            ck.true("span %s 0x%X" % (d, s0), len({sp for sp, _n in group0}) == 1, str(group0))
            ck.true("overlap %s 0x%X..0x%X / 0x%X" % (d, s0, max(ends), s1), max(ends) <= s1, str(group0))
    # A.2 스냅숏: TEP 키 → (기준, 폭) 이 datpatch 가 쓰는 칸과 같다
    tables = {"units": tb.TEP_UNITS, "weapons": tb.TEP_WEAPONS, "upgrades": tb.TEP_UPGRADES,
              "flingy": tb.TEP_FLINGY, "sprites": tb.TEP_SPRITES, "images": tb.TEP_IMAGES}
    special = {("units", "AdvFlag"): ("baseProperty", None), ("units", "Reqptr"): ("requirementOffset", None),
               ("sprites", "IsVisible"): ("isVisible", 1)}
    for d, keys in tb.SPEC_TEP_ADDR.items():
        for key, (base, width) in keys.items():
            if (d, key) in special:
                name, w = special[(d, key)]
            else:
                name, _mul, w = tables[d][key]
            f = dat.field(d, name)
            ck.eq("A.2 %s.%s" % (d, key), (f.base, w or f.size), (base, width))
    # TEP 원본 파일에서 키 → 주소를 직접 읽어 대조 (TPL·theSeed)
    lua_checks(ck)


_LUA_FUNCS = {"SetUnitsDatX": "units", "SetWeaponsDatX": "weapons", "SetUpgradesDatX": "upgrades",
              "SetFlingyDatX": "flingy", "SetSpritesDatX": "sprites", "SetImageDatX": "images"}
_LUA_WIDTH = {"SetMemoryB": 1, "SetMemoryW": 2, "SetMemory": 4, "SetMemoryX": None}


def lua_checks(ck):
    for path in (TPL_FUNC, SEED_FUNC):
        if not os.path.isfile(path):
            print("  TEP 원본 없음: %s — 건너뜀" % path)
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        tag = "tpl" if path == TPL_FUNC else "seed"
        nkeys = 0
        for fm in re.finditer(r"^function (\w+)\(", text, re.M):
            d = _LUA_FUNCS.get(fm.group(1))
            if d is None:
                continue
            end = text.find("\nend", fm.end())
            body = text[fm.end():end]
            parts = re.split(r'(?:if|elseif) j\s*==\s*"(\w+)"\s*then', body)
            for key, block in zip(parts[1::2], parts[2::2]):
                block = re.split(r"\n\s*(?:elseif|else)\b", block)[0]
                nkeys += 1
                known = (key in {"units": tb.TEP_UNITS, "weapons": tb.TEP_WEAPONS, "upgrades": tb.TEP_UPGRADES,
                                 "flingy": tb.TEP_FLINGY, "sprites": tb.TEP_SPRITES, "images": tb.TEP_IMAGES}[d]
                         or key in tb.TEP_UNIT_SPECIAL + tb.TEP_WEAPON_SPECIAL + tb.TEP_SPRITE_SPECIAL)
                ck.true("%s %s.%s supported" % (tag, d, key), known)
                m = re.search(r"(SetMemory[BWX]?)\((0x[0-9A-Fa-f]+)\s*\+", block)
                if m is None:
                    continue  # Reqptr (주석 처리됨) 등
                fn, base = m.group(1), int(m.group(2), 16)
                want = tb.SPEC_TEP_ADDR.get(d, {}).get(key)
                if want is None:
                    continue
                width = _LUA_WIDTH[fn]
                if fn == "SetMemoryX":
                    mask = re.search(r",\s*(0x[0-9A-Fa-f]+|k\[2\])\)\)", block).group(1)
                    if mask == "0xFFFF0000":
                        base, width = base + 2, 2
                    elif mask == "0xFFFF":
                        width = 2
                    else:
                        width = 4
                ck.eq("%s lua %s.%s" % (tag, d, key), (base, width), want)
        ck.true("%s lua keys" % tag, nkeys >= 60, str(nkeys))


# ---------------------------------------------------------------------------------------------
# (2) S5 A.8 액션 기대값 + TEP 변환·경고
# ---------------------------------------------------------------------------------------------


def a8_checks(ck):
    nwarn = len(dat.tep.warnings)
    ck.eq("A.8 AdvFlag/BdDim", tep_acts("SetUnitsDatX", 162, {"AdvFlag": (0x400200, 0x480200), "BdDimX": 1, "BdDimY": 1}),
          [X(0x664308, 0x400200, 0x480200), X(0x662AE8, 0x1, 0xFFFF), X(0x662AE8, 0x10000, 0xFFFF0000)])
    ck.eq("A.8 HP", tep_acts("SetUnitsDatX", 208, {"HP": 5000}), [S(0x662690, 0x138800)])
    ck.eq("A.8 SuppCost 0", tep_acts("SetUnitsDatX", 0, {"SuppCost": 2}), [X(0x663CE8, 0x4, 0xFF)])
    ck.eq("A.8 SuppCost 1", tep_acts("SetUnitsDatX", 1, {"SuppCost": 2}), [X(0x663CE8, 0x400, 0xFF00)])
    ck.eq("A.8 MinCost tep", tep_acts("SetUnitsDatX", 3, {"MinCost": 75}), [X(0x66388C, 0x4B0000, 0xFFFF0000)])
    ck.eq("A.8 MinCost scdata", acts_of(lambda d: d.unit(3).set(mineralCost=75)), [X(0x66388C, 0x4B0000, 0xFFFF0000)])
    size_want = [X(0x6617E0, 0xA, 0xFFFF), X(0x6617E0, 0xC0000, 0xFFFF0000), X(0x6617E4, 0xB, 0xFFFF)]
    ck.eq("A.8 Size tep", tep_acts("SetUnitsDatX", 3, {"SizeL": 10, "SizeU": 12, "SizeR": 11}), size_want)
    ck.eq("A.8 Size scdata", acts_of(lambda d: d.unit(3).set(unitBoundsL=10, unitBoundsT=12, unitBoundsR=11)), size_want)
    ck.eq("A.8 Size merged", acts_of(lambda d: d.unit(3).set(unitBoundsL=10, unitBoundsT=12, unitBoundsR=11), merge=True),
          [S(0x6617E0, 0xC000A), X(0x6617E4, 0xB, 0xFFFF)])
    ck.eq("A.8 Shield false", tep_acts("SetUnitsDatX", 3, {"Shield": False}),
          [X(0x6647B0, 0x0, 0xFF000000), X(0x660E04, 0x0, 0xFFFF0000)])
    ck.eq("Shield number", tep_acts("SetUnitsDatX", 3, {"Shield": 300}),
          [X(0x6647B0, 0x1000000, 0xFF000000), X(0x660E04, 300 << 16, 0xFFFF0000)])
    ck.eq("Shield true", tep_acts("SetUnitsDatX", 3, {"Shield": True}), [X(0x6647B0, 0x1000000, 0xFF000000)])
    ck.eq("hasShield scdata = bit", acts_of(lambda d: d.unit(3).set(hasShield=True)), [X(0x6647B0, 0x1000000, 0x1000000)])
    ck.eq("A.8 WhatSndInit", tep_acts("SetUnitsDatX", 3, {"WhatSndInit": 5}), [X(0x662BF4, 0x50000, 0xFFFF0000)])
    ck.eq("A.8 WhatSndInit warning", len(dat.tep.warnings) - nwarn, 1)
    ck.true("warning text", "반대" in dat.tep.warnings[-1][1], dat.tep.warnings[-1][1])
    ck.eq("WhatSndEnd", tep_acts("SetUnitsDatX", 3, {"WhatSndEnd": 5}), [X(0x65FFB4, 0x50000, 0xFFFF0000)])
    ck.eq("WhatSndEnd warning", len(dat.tep.warnings) - nwarn, 2)
    ck.eq("A.8 whatSoundStart", acts_of(lambda d: d.unit(3).set(whatSoundStart=5)), [X(0x65FFB4, 0x50000, 0xFFFF0000)])
    ck.eq("A.8 DmgBase", tep_acts("SetWeaponsDatX", 1, {"DmgBase": 75}), [X(0x656EB0, 0x4B0000, 0xFFFF0000)])
    splash_want = [X(0x6566F8, 0x300, 0xFF00), X(0x656888, 0x70000, 0xFFFF0000),
                   X(0x6570C8, 0xE0000, 0xFFFF0000), X(0x657780, 0x150000, 0xFFFF0000)]
    ck.eq("A.8 Splash tep", tep_acts("SetWeaponsDatX", 1, {"Splash": (7, 14, 21)}), splash_want)
    ck.eq("A.8 splash()", acts_of(lambda d: d.weapon(1).splash(7, 14, 21)), splash_want)
    ck.eq("Splash true/false", tep_acts("SetWeaponsDatX", 1, Splash=True) + tep_acts("SetWeaponsDatX", 1, Splash=False),
          [X(0x6566F8, 0x300, 0xFF00), X(0x6566F8, 0x100, 0xFF00)])
    ck.eq("A.8 RemoveAfter", tep_acts("SetWeaponsDatX", 128, {"RemoveAfter": 64}), [X(0x6570C0, 0x40, 0xFF)])
    ck.eq("A.8 FlingyID", tep_acts("SetWeaponsDatX", 128, {"FlingyID": 158}), [S(0x656EA8, 0x9E)])
    ck.eq("flingy scdata = byte", acts_of(lambda d: d.weapon(128).set(flingy=158)), [X(0x656EA8, 0x9E, 0xFF)])
    ck.eq("A.8 topSpeed", acts_of(lambda d: d.flingy(106).set(topSpeed=8000)), [S(0x6CA0A0, 0x1F40)])
    ck.eq("topSpeed negative", acts_of(lambda d: d.flingy(106).set(topSpeed=-7999)), [S(0x6CA0A0, -7999)])
    ck.eq("A.8 enable P1", acts_of(lambda d: d.player_unit_enable(5, players=[0], value=1)), [X(0x57F280, 0x100, 0xFF00)])
    ck.eq("A.8 disable P8", acts_of(lambda d: d.player_unit_enable(5, players=[7], value=0)), [X(0x57F8BC, 0x0, 0xFF00)])
    ck.eq("enable P1 object", acts_of(lambda d: d.player_unit_enable(5, players=ep.P1)), [X(0x57F280, 0x100, 0xFF00)])
    n0 = len(dat.tep.warnings)
    ck.eq("A.8 Reqptr ignore", tep_acts("SetUnitsDatX", 3, {"Reqptr": 5}), [])
    ck.eq("Reqptr warning", len(dat.tep.warnings) - n0, 1)
    ck.eq("Reqptr once", tep_acts("SetUnitsDatX", 3, {"Reqptr": 5}, reqptr="once"), [X(0x660A74, 0x50000, 0xFFFF0000)])
    ck.eq("Upgrade Reqptr", tep_acts("SetUpgradesDatX", 1, {"Reqptr": 5}), [W(0x6558C0, 2, 1, 2, 5)])
    dat.clear()
    ck.eq("Reqptr every_frame (target 비움)", tep_acts("SetUnitsDatX", 3, {"Reqptr": 5}, reqptr="every_frame"), [])
    dat.tep.PatchInsertPrsv(SetMemory(0x58A368, SetTo, 2))
    ck.eq("Reqptr every_frame list", [dec(a) for a in dat.EVERY_FRAME.actions(merge=False)],
          [X(0x660A74, 0x50000, 0xFFFF0000), S(0x58A368, 2)])
    ck.eq("START untouched", dat.START.entries(), [])
    dat.clear()
    # Playerable
    enable = [W(0x57F27C, 1, p * 228 + 7, 1, v) for p, v in enumerate((1, 1, 1, 1, 1, 0, 0, 0))]
    ck.eq("Playerable 2 (TPL)", tep_acts("SetUnitsDatX", 7, {"Playerable": 2}), enable)
    seed_enable = [W(0x57F27C, 1, p * 228 + 7, 1, 1 if p < 7 else 0) for p in range(8)]
    ck.eq("Playerable 2 humans", tep_acts("SetUnitsDatX", 7, {"Playerable": 2}, humans=range(7)), seed_enable)
    ck.eq("Playerable true", tep_acts("SetUnitsDatX", 7, {"Playerable": True}), [W(0x57F27C, 1, p * 228 + 7, 1, 1) for p in range(8)])
    # theSeed 비트 이름 · 키워드 인자 · None(=nil) 건너뛰기
    ck.eq("seed bit", tep_acts("SetUnitsDatX", 3, Flyer=True, RoboticUnit=False, Hero=None),
          [X(0x66408C, 0x4, 0x4), X(0x66408C, 0x0, 0x4000)])
    ck.eq("scdata flags merged", acts_of(lambda d: d.unit(3).flags(Flyer=True, Robotic=False, Hero=True)),
          [X(0x66408C, 0x44, 0x4044)])
    ck.eq("flags weapons", acts_of(lambda d: d.weapon(0).flags(Air=True, Ground=False)), [X(0x657998, 0x1, 0x3)])
    ck.eq("flags groupFlags", acts_of(lambda d: d.unit(1).flags("groupFlags", Zerg=True)), [X(0x6637A0, 0x100, 0x100)])
    ck.eq("mask()", acts_of(lambda d: d.unit(162).mask("baseProperty", 0x400200, 0x480200)), [X(0x664308, 0x400200, 0x480200)])
    ck.eq("mask() bit field whole byte", acts_of(lambda d: d.unit(3).mask("hasShield", 0x81, 0xFF)), [X(0x6647B0, 0x81000000, 0xFF000000)])
    ck.eq("position tuple", acts_of(lambda d: d.unit(3).set(buildingDimensions=(3, 4))), [S(0x66286C, 0x40003)])
    ck.eq("addon", tep_acts("SetUnitsDatX", 107, {"AddonPlacement": (5, 6)}),
          [X(0x6626E4, 5, 0xFFFF), X(0x6626E4, 6 << 16, 0xFFFF0000)])
    ck.eq("infestation", tep_acts("SetUnitsDatX", 106, {"InfestationUnit": 30}), [X(0x664980, 30, 0xFFFF)])
    ck.eq("ConstructionAnimation dword", tep_acts("SetUnitsDatX", 2, {"ConstructionAnimation": 9}), [S(0x6610B8, 9)])
    ck.eq("constructionGraphic word", acts_of(lambda d: d.unit(2).set(constructionGraphic=9)), [X(0x6610B8, 9, 0xFFFF)])
    ck.eq("ComputerAI byte", tep_acts("SetUnitsDatX", 1, {"ComputerAI": 3}), [X(0x660178, 0x300, 0xFF00)])
    ck.eq("scdata names", acts_of(lambda d: d.weapon(2).set(damageType="Normal", behavior="Bounce", explosionType="SplashEnemy")),
          [X(0x657258, 0x30000, 0xFF0000), X(0x656670, 0x70000, 0xFF0000), X(0x6566F8, 0x30000, 0xFF0000)])
    ck.eq("unit name index", acts_of(lambda d: d.unit("Terran Marine").set(armor=1)), [X(0x65FEC8, 1, 0xFF)])
    ck.eq("unit name value", acts_of(lambda d: d.unit(1).set(subUnit="Terran Marine")), [X(0x6607C0, 0, 0xFFFF0000)])
    ck.eq("sprites IsVisible", tep_acts("SetSpritesDatX", 5, {"IsVisible": True, "ImageFile": 10}),
          [W(0x666160, 2, 5, 2, 10), W(0x665C48, 1, 5, 1, 1)])
    ck.eq("images GraphicsTurns", tep_acts("SetImageDatX", 944, {"GraphicsTurns": 3, "IscriptID": 70}),
          [W(0x66E860, 1, 944, 1, 3), S(0x66EC48 + 944 * 4, 70)])
    ck.eq("flingy tep", tep_acts("SetFlingyDatX", 1, {"Speed": 100, "TurnRadius": 27, "Acceleration": 5}),
          [S(0x6C9EFC, 100), W(0x6C9E20, 1, 1, 1, 27), W(0x6C9C78, 2, 1, 2, 5)])
    ck.eq("upgrades tep", tep_acts("SetUpgradesDatX", 7, {"MaxLevel": 250, "MinCost": 0}),
          [W(0x655700, 1, 7, 1, 250), W(0x655740, 2, 7, 2, 0)])
    ck.eq("DamageRatio", tep_acts("SetDamageRatio", 3, 2, 768), [S(0x515B88 + 0x14 * 3 + 8, 768)])
    ck.eq("damage_ratio names", acts_of(lambda d: d.damage_ratio("Explosive", "Large", 256)), [S(0x515B88 + 0x14 + 12, 256)])
    ck.eq("DmgType (DPS)", tep_acts("SetWeaponsDatX", 1, DmgType=2), [X(0x657258, 0x200, 0xFF00)])
    # TEP 처럼 잘라 쓰기 + 경고
    n0 = len(dat.tep.warnings)
    ck.eq("SuppCost overflow", tep_acts("SetUnitsDatX", 0, {"SuppCost": 200}), [X(0x663CE8, 400 & 0xFF, 0xFF)])
    ck.eq("overflow warning", len(dat.tep.warnings) - n0, 1)
    # PatchInsert
    lst = dat.PatchList()
    dat.tep.PatchInsert(SetMemory(0x58A364, SetTo, 5), target=lst)
    ck.eq("PatchInsert", [dec(a) for a in lst.actions()], [S(0x58A364, 5)])
    # SetUnitAbility (TPL 18인자)
    ability_checks(ck)
    # 오류
    errors = [
        ("unknown tep key", lambda: tep_acts("SetUnitsDatX", 3, {"Foo": 1})),
        ("unknown weapon key", lambda: tep_acts("SetWeaponsDatX", 3, {"HP": 1})),
        ("unknown field", lambda: acts_of(lambda d: d.unit(3).set(maxHP=1))),
        ("unit 228", lambda: acts_of(lambda d: d.unit(228))),
        ("unit 228 tep", lambda: tep_acts("SetUnitsDatX", 228, {"HP": 1})),
        ("unit -1", lambda: acts_of(lambda d: d.unit(-1))),
        ("weapon 130", lambda: acts_of(lambda d: d.weapon(130))),
        ("YesInit 106", lambda: tep_acts("SetUnitsDatX", 106, {"YesInit": 1})),
        ("yesSoundStart 106", lambda: acts_of(lambda d: d.unit(106).set(yesSoundStart=1))),
        ("readySound 106", lambda: acts_of(lambda d: d.unit(106).set(readySound=1))),
        ("addon 105", lambda: tep_acts("SetUnitsDatX", 105, {"AddonPlacement": (1, 2)})),
        ("infestation 202", lambda: acts_of(lambda d: d.unit(202).set(infestationUnit=1))),
        ("bit value 2", lambda: acts_of(lambda d: d.unit(3).set(hasShield=2))),
        ("word overflow", lambda: acts_of(lambda d: d.unit(3).set(maxShield=70000))),
        ("byte negative", lambda: acts_of(lambda d: d.unit(3).set(armor=-129))),
        ("var value in list", lambda: acts_of(lambda d: d.unit(3).set(maxHp=EUDVariable()))),
        ("var index in list", lambda: acts_of(lambda d: d.unit(EUDVariable()))),
        ("Splash bad", lambda: tep_acts("SetWeaponsDatX", 1, {"Splash": (1, 2)})),
        ("AdvFlag bad", lambda: tep_acts("SetUnitsDatX", 1, {"AdvFlag": 5})),
        ("EUDArray value", lambda: tep_acts("SetUnitsDatX", 1, AdvFlag=EUDArray([1, 2]))),
        ("Property not dict", lambda: tep_acts("SetUnitsDatX", 1, [1, 2])),
        ("reqptr mode", lambda: tep_acts("SetUnitsDatX", 1, {"Reqptr": 1}, reqptr="always")),
        ("flag name", lambda: acts_of(lambda d: d.unit(3).flags(Flier=True))),
        ("flag value", lambda: acts_of(lambda d: d.unit(3).flags(Flyer=3))),
        ("flags no default", lambda: acts_of(lambda d: d.flingy(3).flags(Foo=True))),
        ("mask too wide", lambda: acts_of(lambda d: d.unit(3).mask("armor", 1, 0x1FF))),
        ("splash on unit", lambda: acts_of(lambda d: d.unit(3).splash(1, 2, 3))),
        ("enable value 2", lambda: acts_of(lambda d: d.player_unit_enable(1, players=0, value=2))),
        ("enable player 12", lambda: acts_of(lambda d: d.player_unit_enable(1, players=12))),
        ("damage type 5", lambda: acts_of(lambda d: d.damage_ratio(5, 0, 256))),
        ("DamageRatio value", lambda: tep_acts("SetDamageRatio", 0, 0, -1)),
        ("raw CP", lambda: acts_of(lambda d: d.raw(SetMemory(0x6509B0, SetTo, 1)))),
        ("table name", lambda: dat.field("unitz", "maxHp")),
        ("end_actions empty", lambda: dat.end_actions()),
        ("end_temporary empty", lambda: dat.end_temporary()),
        ("emit chunk", lambda: dat.emit([], chunk=65)),
        ("Ability ArmorDefType tpl", lambda: dat.tep.SetUnitAbility(40, None, 1, ArmorDefType=1, target=dat.PatchList())),
        ("Ability DmgType", lambda: dat.tep.SetUnitAbility(40, None, 9, target=dat.PatchList())),
    ]
    for label, fn in errors:
        ck.raises(label, EudextError, fn)
    ck.true("EUDArray hint", _err_text(lambda: tep_acts("SetUnitsDatX", 1, AdvFlag=EUDArray([1, 2]))).find("dat.values") >= 0)
    ck.true("suggest", "maxHp" in _err_text(lambda: acts_of(lambda d: d.unit(3).set(maxHP=1))))
    # 기타 공개 API
    ck.eq("values", dat.values(1, 2, 3), (1, 2, 3))
    ck.eq("field repr", repr(dat.field("units", "maxHp")), "Field(base=0x662350, size=4, stride=4, count=228, member=TrgUnit.maxHp)")
    ck.eq("addr const", dat.addr("weapons", "damage", 127), (0x656FAC, 16, 0xFFFF0000))
    ck.eq("addr alias table", dat.addr("Weapon", "damage", 0), (0x656EB0, 0, 0xFFFF))
    ck.eq("addr players", dat.addr("players", "unitAvailability", 7 * 228 + 5), (0x57F8BC, 8, 0xFF00))
    for name in ("unit", "weapon", "flingy", "upgrade", "tech", "sprite", "image", "player_unit_enable", "damage_ratio",
                 "raw", "from_eud_editor", "start", "every_frame", "actions", "begin_actions", "end_actions", "emit",
                 "values", "clear", "set_debug", "addr", "field", "begin_temporary", "end_temporary", "unpatch_all",
                 "parse_eud_editor"):
        ck.true("alias %s" % name, getattr(dat, name) is getattr(dat, "f_" + name))
    # 합치기 = 순서대로 적용한 결과와 같다 (무작위)
    merge_diff(ck)
    # 디버그 경고
    dat.set_debug(True)
    try:
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always")
            acts_of(lambda d: d.unit(3).set(armor=1).set(armor=2))
        ck.true("debug warning", any("다시 씁니다" in str(w.message) for w in rec), str([str(w.message) for w in rec]))
    finally:
        dat.set_debug(False)
    # 64개 묶음 수 (계산)
    for n, want in ((1182, 19), (773, 13), (64, 1), (65, 2), (0, 0)):
        ck.eq("chunks %d" % n, math.ceil(n / dat.CHUNK), want)


def _err_text(fn):
    try:
        fn()
    except EudextError as e:
        return str(e)
    return ""


def ability_checks(ck):
    nw = dat.tep.warnings[:]
    lst = dat.PatchList()
    info = dat.tep.SetUnitAbility(21, 18, 3, 1, 17000, 500, (8, 9, 10, 11), 30, 450, 20, (5, 10, 15), None, 160, 5,
                                  None, "Kazansky Prime", 2000, 7, target=lst)
    want = [
        W(0x663DD0, 1, 21, 1, 94), W(0x6637A0, 1, 21, 1, 0xA), X(0x6640D4, 0, 0x80C0), W(0x661518, 2, 21, 2, 0x1C7),
        W(0x660178, 1, 21, 1, 1), S(0x6623A4, 17000 * 256), W(0x6647B0, 1, 21, 1, 1), W(0x660E00, 2, 21, 2, 500),
        W(0x6636B8, 1, 21, 1, 18), W(0x6616E0, 1, 21, 1, 130), W(0x662DB8, 1, 21, 1, 5), W(0x663EB8, 2, 21, 2, 2000),
        X(0x661870, 8, 0xFFFF), X(0x661870, 9 << 16, 0xFFFF0000), X(0x661874, 10, 0xFFFF), X(0x661874, 11 << 16, 0xFFFF0000),
        W(0x657998, 2, 18, 2, 11), W(0x657258, 1, 18, 1, 3), W(0x656FB8, 1, 18, 1, 30), W(0x656EB0, 2, 18, 2, 450),
        S(0x6574B8, 160), W(0x6564E0, 1, 18, 1, 1),
        W(0x6566F8, 1, 18, 1, 3), W(0x656888, 2, 18, 2, 5), W(0x6570C8, 2, 18, 2, 10), W(0x657780, 2, 18, 2, 15),
        W(0x657678, 2, 18, 2, 20), W(0x6571D0, 1, 18, 1, 7),
    ]
    ck.eq("SetUnitAbility actions", [dec(a) for a in lst.actions(merge=False)], want)
    ck.eq("SetUnitAbility info", (info["color"], info["name"], info["name_hex"], info["big_kill_point"]),
          (0x1B, "<08>K<04>azansky <08>P<04>rime ", "<1b>K<04>azansky <1b>P<04>rime ", None))
    # 서브유닛(시즈 탱크 5 → 6), 킬 점수 65536 이상, 무기 없음 AI 3 (영웅 비트)
    lst = dat.PatchList()
    info = dat.tep.SetUnitAbility(5, 27, 1, 3, 100, None, None, 10, 5, None, None, 2, 30, None, None, "T", 70000, None,
                                  target=lst)
    got = [dec(a) for a in lst.actions(merge=False)]
    ck.eq("Ability subunit first", got[:2], [W(0x6636B8, 1, 6, 1, 27), W(0x6616E0, 1, 6, 1, 130)])
    ck.true("Ability subunit ground 130", W(0x6636B8, 1, 5, 1, 130) in got)
    ck.true("Ability hero flag", X(0x664094, 0x40, 0x80C0) in got)
    ck.true("Ability shield false", W(0x660E00, 2, 5, 2, 0) in got)
    ck.true("Ability big kill -> 0", W(0x663EB8, 2, 5, 2, 0) in got and info["big_kill_point"] == 70000)
    ck.eq("Ability color", info["color"], 0x11)
    # DmgType true / nil, 83번 예외(TPL), DmgType 5
    lst = dat.PatchList()
    dat.tep.SetUnitAbility(83, 60, 5, 1, 10, target=lst)
    got = [dec(a) for a in lst.actions(merge=False)]
    ck.true("83 ground 130 (tpl)", W(0x6636B8, 1, 83, 1, 130) in got)
    ck.true("DmgType 5 class 95", W(0x663DD0, 1, 83, 1, 95) in got)
    ck.true("DmgType 5 -> 3", W(0x657258, 1, 60, 1, 3) in got)
    lst = dat.PatchList()
    dat.tep.SetUnitAbility(83, 61, 5, 1, 10, ArmorDefType=0, variant="seed", target=lst)
    got = [dec(a) for a in lst.actions(merge=False)]
    ck.true("83 ground wep (seed)", W(0x6636B8, 1, 83, 1, 61) in got)
    ck.true("seed DmgType 5 -> 0", W(0x657258, 1, 61, 1, 0) in got)
    ck.true("seed DefType", W(0x662180, 1, 83, 1, 0) in got)
    lst = dat.PatchList()
    dat.tep.SetUnitAbility(84, None, None, 1, 10, target=lst)
    got = [dec(a) for a in lst.actions(merge=False)]
    ck.true("DmgType nil: no class", all(g[1] != loc(0x663DD0, 1, 84, 1)[0] or g[4] != loc(0x663DD0, 1, 84, 1)[2] for g in got))
    ck.raises("WepID duplicated", EudextError, dat.tep.SetUnitAbility, 85, 18, 3, target=dat.PatchList())
    lst = dat.PatchList()
    dat.tep.SetUnitAbility(86, 71, 3, target=lst)
    dat.tep.SetUnitAbility(87, 71, 3, target=lst)
    ck.true("WepID 71 free (tpl)", True)
    ck.eq("Ability no new warnings", dat.tep.warnings, nw)


def merge_diff(ck):
    rng = random.Random(15)
    fields = [("units", "maxHp"), ("units", "armor"), ("units", "hasShield"), ("units", "unitBoundsT"),
              ("units", "unitBoundsL"), ("units", "buildingDimX"), ("units", "buildingDimY"), ("weapons", "damage"),
              ("units", "dontBecomeGuard"), ("units", "computerAI")]
    bad = 0
    for trial in range(300):
        lst = dat.PatchList()
        addrs = set()
        for _ in range(rng.randrange(1, 30)):
            r = rng.random()
            if r < 0.15:
                a = 0x662350 + 4 * rng.randrange(4)
                lst.raw(SetMemory(a, ep.Add, rng.getrandbits(32)))
            elif r < 0.2:
                lst.raw(SetMemoryX(0x6617C8 + 8 * rng.randrange(2), SetTo, rng.getrandbits(32), rng.getrandbits(32)))
            elif r < 0.3:
                lst.unit(rng.randrange(4)).mask("baseProperty", rng.getrandbits(32), rng.getrandbits(32))
            else:
                d, name = rng.choice(fields)
                f = dat.field(d, name)
                lo, hi = (0, 1) if f.bit else (0, f.full_mask)
                lst.row(d, rng.randrange(6)).set(**{name: rng.randint(lo, hi)})
        for e in lst.entries():
            addrs.add(e[0])
        init = {a: rng.getrandbits(32) for a in addrs}
        m1 = dat.simulate(lst.writes(merge=False), dict(init))
        m2 = dat.simulate([dec_to_write(a) for a in lst.actions(merge=True)], dict(init))
        if m1 != m2:
            bad += 1
        if len(lst.actions(merge=True)) > len(lst.entries()):
            bad += 1
    ck.eq("merge diff 300", bad, 0)


def dec_to_write(act):
    kind, a, mod, v, m = dec(act)
    return (a, mod, v, m)


# ---------------------------------------------------------------------------------------------
# EUD Editor 목록
# ---------------------------------------------------------------------------------------------


def _lua_pairs(path, table="EUDEditorDatActs"):
    """독립 파서: 표 시작 줄부터 첫 '}' 줄까지 `{0x…, 수}` 를 줄 단위로."""
    out = []
    inside = False
    for line in open(path, encoding="utf-8-sig", errors="replace"):
        if line.startswith(table + " = {"):
            inside = True
            continue
        if inside:
            if line.startswith("}"):
                break
            m = re.match(r"\s*\{(0x[0-9A-Fa-f]+),\s*(-?\d+)\}", line)
            if m:
                out.append((int(m.group(1), 16), int(m.group(2))))
    return out


def eud_editor_checks(ck):
    for tag, path, n in (("M2", M2_DAT, 1182), ("UERE", UERE_DAT, 773)):
        if not os.path.isfile(path):
            print("  %s 없음 — 건너뜀" % path)
            continue
        pairs = _lua_pairs(path)
        ck.eq("%s count (independent)" % tag, len(pairs), n)
        lst = dat.PatchList()
        ck.eq("%s from_eud_editor" % tag, lst.from_eud_editor(path), n)
        got = [dec(a) for a in lst.actions()]
        ck.eq("%s same order Add" % tag, got, [("SetMemory", a, "Add", v & M32, M32) for a, v in pairs])
        ck.eq("%s no merge" % tag, len(lst.actions()), n)
    for tag, path, n in (("seed py", SEED_PY, 292), ("dps py", DPS_PY, 416)):
        if not os.path.isfile(path):
            continue
        items = dat.parse_eud_editor(path)
        want = [(int(a, 16), mod, int(v)) for a, mod, v in re.findall(r"SetMemory\((0x[0-9A-Fa-f]+), (\w+), (-?\d+)\)",
                                                                       open(path, encoding="utf-8-sig").read())]
        ck.eq("%s parse" % tag, items, want)
        ck.eq("%s count" % tag, len(items), n)
    ck.eq("pairs list", acts_of(lambda d: d.from_eud_editor([(0x58A364, -1), (0x58A368, "SetTo", 5)])),
          [S(0x58A364, -1, "Add"), S(0x58A368, 5)])
    ck.raises("bad addr", EudextError, dat.parse_eud_editor, [(0x58A365, 1)])
    ck.raises("no file", EudextError, dat.parse_eud_editor, "/nonexistent/EUDEditorDat.lua")
    if os.path.isfile(M2_DAT):
        ck.raises("no table", EudextError, dat.parse_eud_editor, M2_DAT, "NoSuchTable")
        ck.eq("status table", len(dat.parse_eud_editor(M2_DAT, "EUDEditorStatusFnActs")), 12)


# ---------------------------------------------------------------------------------------------
# (3) 에뮬레이터: 한 빌드(Suite)
# ---------------------------------------------------------------------------------------------

EMIT_NS = (1, 63, 64, 65, 128, 129)
MINRANGE = 0x656A18


def build_cases(s, info):
    info["emit"] = {}

    @s.case("start_list")
    def _(t):
        # 빌드 중(단계 1) 선언 → 이번 빌드의 시작 목록
        dat.unit(208).set(maxHp=5000 * 256, elevation=20)
        dat.unit(208).flags(Flyer=True, Invincible=True)
        dat.unit(162).mask("baseProperty", 0x400200, 0x480200)
        dat.tep.SetUnitsDatX(162, {"BdDimX": 1, "BdDimY": 2, "SuppCost": 3})
        dat.weapon(1).splash(7, 14, 21)
        dat.flingy(106).set(topSpeed=8000)
        dat.player_unit_enable(5, players=[0, 7], value=1)
        info["phase_in_build"] = _compat.onstart_phase()

    @s.case("every_frame")
    def _(t):
        dat.every_frame().unit(0).set(requirementOffset=0x1234)
        dat.every_frame().player_unit_enable(3, players=2, value=1)

    @s.case("actions_cond")
    def _(t):
        c = t.var("c")
        acts = dat.actions(lambda d: d.weapon(128).set(damage=65535, flingy=158))
        info["captured"] = dat.actions(lambda d: dat.unit(5).set(armor=9))  # 모듈 함수도 캡처 목록으로
        dat.begin_actions()
        dat.weapon(129).set(cooldown=33)
        acts2 = dat.end_actions()
        if EUDIf()(c.Exactly(1)):
            DoActions(acts)
            dat.emit(acts2)
        EUDEndIf()

    @s.case("now_const")
    def _(t):
        dat.now.weapon(5).set(damage=1234, cooldown=7)
        dat.now.unit(3).flags(Flyer=True)
        dat.now.unit(3).mask("baseProperty", 0x10, 0x30)
        dat.now.player_unit_enable(9, players=[1, 2], value=1)
        dat.now.damage_ratio(1, 2, 300)

    @s.case("now_var")
    def _(t):
        i, v, b = t.var("i"), t.var("v"), t.var("b")
        dat.now.unit(i).set(maxHp=v)
        dat.now.weapon(i).set(damage=v)
        dat.now.unit(i).set(elevation=v)
        dat.now.unit(i).set(hasShield=b)
        dat.now.unit(i).set(buildingDimY=v)
        dat.now.unit(i).set(computerAI=v)
        dat.now.unit(i).mask("baseProperty", v, 0x00FF00F0)
        dat.now.unit(i).flags(Hero=True)
        dat.now.player_unit_enable(i, players=b, value=b)

    @s.case("temp_const")
    def _(t):
        v, b = t.var("v"), t.var("b")
        with dat.temporary():
            dat.now.weapon(5).set(damage=v)
            dat.now.unit(3).set(elevation=0x5A, hasShield=b)
            dat.now.unit(9).set(maxHp=v)
            dat.now.unit(4).flags(Flyer=True)
            dat.now.unit(6).set(hasShield=True)
            for k, a in TEMP_ADDRS.items():
                t.out("mid_" + k, f_dwread_epd(EPD(a)))
        for k, a in TEMP_ADDRS.items():
            t.out("out_" + k, f_dwread_epd(EPD(a)))

    @s.case("temp_var")
    def _(t):
        i, v = t.var("i"), t.var("v")
        with dat.temporary() as nw:
            nw.weapon(i).set(damage=v)
            nw.unit(i).set(elevation=v)
            nw.unit(i).set(buildingDimY=v)
            nw.unit(i).set(maxHp=v)
            nw.unit(i).mask("baseProperty", v, 0xF0)
            _reads(t, "mid_", i)
        _reads(t, "out_", i)

    @s.case("temp_later")
    def _(t):
        v = t.var("v")
        with dat.temporary(restore=False):
            dat.now.unit(20).set(maxHp=v)
        t.out("mid", f_dwread_epd(EPD(0x662350 + 80)))
        dat.unpatch_all()
        t.out("out", f_dwread_epd(EPD(0x662350 + 80)))

    for n in EMIT_NS:

        @s.case("emit_%d" % n)
        def _(t, n=n):
            lst = dat.PatchList("emit")
            for k in range(n):
                lst.weapon(k).set(minRange=0x1000 + k)
            c0 = GetTriggerCounter()
            cnt = dat.emit(lst)
            info["emit"][n] = (cnt, GetTriggerCounter() - c0, len(lst.actions()))


TEMP_ADDRS = {"w": 0x656EB8, "e": 0x663150, "s": 0x6647B0, "h": 0x662350 + 36, "f": 0x664080 + 16, "s6": 0x6647B4}


def _reads(t, prefix, i):
    e, s_ = dat.addr("weapons", "damage", i)
    t.out(prefix + "w", f_wread_epd(e, s_))
    e, s_ = dat.addr("units", "elevation", i)
    t.out(prefix + "e", f_bread_epd(e, s_))
    e, s_ = dat.addr("units", "buildingDimY", i)
    t.out(prefix + "y", f_wread_epd(e, s_))
    e, s_ = dat.addr("units", "maxHp", i)
    t.out(prefix + "h", f_dwread_epd(e))
    e, s_ = dat.addr("units", "baseProperty", i)
    t.out(prefix + "p", f_dwread_epd(e))


def _fill(m, rng, addrs):
    """주소들을 난수로 채우고, 매 프레임 목록(every_frame 케이스)이 사이클마다 다시 쓰는 칸을 반영한 값을 돌려준다."""
    init = {}
    for a in addrs:
        init[a] = rng.getrandbits(32)
        m.setdw(a, init[a])
    return dat.simulate(dat.EVERY_FRAME.writes(False), init)


def _region(base, stride, count):
    lo = base & ~3
    hi = base + stride * count + 4
    return list(range(lo, hi & ~3, 4))


NOW_REGIONS = (
    _region(0x662350, 4, 228) + _region(0x656EB0, 2, 130) + _region(0x663150, 1, 228) + _region(0x6647B0, 1, 228)
    + _region(0x662860, 4, 228) + _region(0x660178, 1, 228) + _region(0x664080, 4, 228) + _region(0x57F27C, 1, 228 * 12)
)


def run_checks(s, info, ck):
    m = s.machine
    # --- 시작 목록: 첫 사이클에 1회 적용 ---
    ck.eq("phase in build", info.get("phase_in_build"), 1)
    want = dat.simulate(dat.START.writes(merge=False))
    got = {a: m.dw(a) for a in want}
    s.expect_true("start_list", got == want, "memory", "%r != %r" % (got, want))
    spot = {0x662690: 0x138800, 0x663150 + 208: 20, 0x6643C0: 0x20000004, 0x662AE8: 0x20001,
            0x663D88: 6 << 16, 0x6CA0A0: 8000, 0x57F280: 0x100, 0x57F8BC: 0x100}
    for a, v in spot.items():
        s.expect_true("start_list", m.dw(a) == v, "spot 0x%X" % a, "0x%X != 0x%X" % (m.dw(a), v))
    s.expect_true("start_list", dat.START.last_emit is not None and dat.START.last_emit[1] == math.ceil(dat.START.last_emit[0] / 64),
                  "last_emit", str(dat.START.last_emit))
    ck.true("captured not in START", all(e[0] != 0x65FEC8 + 4 for e in dat.START.entries()))
    ck.eq("captured acts", [dec(a) for a in info["captured"]], [X(0x65FECC, 9 << 8, 0xFF00)])
    m.setdw(0x662690, 7)
    r = s.run("start_list")
    s.expect_true("start_list", r.error is None and m.dw(0x662690) == 7, "once only", "%r 0x%X" % (r.error, m.dw(0x662690)))
    s.reset()
    # --- 매 프레임 목록 ---
    a_req = 0x660A70  # requirementOffset[0] (워드, subp 0)
    a_en = 0x57F27C + 2 * 228 + 3
    s.expect_true("every_frame", m.dw(a_req) & 0xFFFF == 0x1234, "applied", "0x%X" % m.dw(a_req))
    m.setdw(a_req, 0xAAAA0000)
    m.setdb(a_en, 0)
    r = s.run("start_list")  # 아무 케이스나 — 매 프레임 목록은 게임 루프 시작점에서 돈다
    s.expect_true("every_frame", r.error is None and m.dw(a_req) == 0xAAAA1234, "restored", "0x%X" % m.dw(a_req))
    s.expect_true("every_frame", m.db(a_en) == 1, "restored enable", "%d" % m.db(a_en))
    s.reset()
    # --- 조건 목록 ---
    s.check("actions_cond", {"c": 0}, {}, label="c=0", fresh=True)
    s.expect_true("actions_cond", m.dw(0x656FAC + 4) == 0 and m.dw(0x656EA8) == 0 and m.db(0x656FB8 + 129) == 0, "c=0 no write")
    s.check("actions_cond", {"c": 1}, {}, label="c=1", fresh=True)
    s.expect_true("actions_cond", (m.dw(0x656FB0) & 0xFFFF) == 65535, "damage", "0x%X" % m.dw(0x656FB0))
    s.expect_true("actions_cond", m.dw(0x656EA8) == 158, "flingy", "0x%X" % m.dw(0x656EA8))
    s.expect_true("actions_cond", m.db(0x656FB8 + 129) == 33, "emit list", "%d" % m.db(0x656FB8 + 129))
    s.reset()
    # --- now 상수 ---
    rng = random.Random(7)
    addrs = [0x656EB8, 0x656FB8 + 4, 0x66408C, 0x57F27C + 228 + 8, 0x57F27C + 456 + 8, 0x515B88 + 0x14 + 8]
    init = _fill(m, rng, addrs)
    r = s.run("now_const")
    lst = dat.PatchList()
    lst.weapon(5).set(damage=1234, cooldown=7)
    lst.unit(3).flags(Flyer=True).mask("baseProperty", 0x10, 0x30)
    lst.player_unit_enable(9, players=[1, 2], value=1)
    lst.damage_ratio(1, 2, 300)
    want = dat.simulate(lst.writes(False), dict(init))
    s.expect_true("now_const", r.error is None and {a: m.dw(a) for a in want} == want, "memory", str(r.error))
    s.reset()
    # --- now 변수 (무작위 + 경계) ---
    cases = [(0, 0, 0), (129, M32, 1), (1, 0x12345678, 1), (2, 0xDEADBEEF, 0), (3, 0x80000001, 1), (106, 0xFFFF, 0)]
    cases += [(rng.randrange(130), rng.getrandbits(32), rng.randrange(2)) for _ in range(20)]
    for i, v, b in cases:
        s.reset()
        init = _fill(m, rng, NOW_REGIONS)
        r = s.run("now_var", {"i": i, "v": v, "b": b})
        lst = dat.PatchList()
        lst.unit(i).set(maxHp=v, elevation=v & 0xFF, hasShield=b, buildingDimY=v & 0xFFFF, computerAI=v & 0xFF)
        lst.weapon(i).set(damage=v & 0xFFFF)
        lst.unit(i).mask("baseProperty", v & 0x00FF00F0, 0x00FF00F0).flags(Hero=True)
        lst.player_unit_enable(i, players=b, value=b)
        want = dat.simulate(lst.writes(False), dict(init))
        full = dict(init)
        full.update(want)
        got = {a: m.dw(a) for a in full}
        diff = {hex(a): (hex(got[a]), hex(full[a])) for a in full if got[a] != full[a]}
        s.expect_true("now_var", r.error is None and not diff, "i=%d v=0x%X b=%d" % (i, v, b), "%s %s" % (r.error, list(diff.items())[:4]))
    s.reset()
    # --- temporary 상수 번호 ---
    for v, b in ((0x11223344, 1), (0, 0), (M32, 1), (0xABCD, 0)):
        s.reset()
        init = _fill(m, rng, list(TEMP_ADDRS.values()))
        r = s.run("temp_const", {"v": v, "b": b})
        lst = dat.PatchList()
        lst.weapon(5).set(damage=v & 0xFFFF)
        lst.unit(3).set(elevation=0x5A, hasShield=b)
        lst.unit(9).set(maxHp=v)
        lst.unit(4).flags(Flyer=True)
        lst.unit(6).set(hasShield=True)
        mid = dat.simulate(lst.writes(False), dict(init))
        exp = {}
        for k, a in TEMP_ADDRS.items():
            exp["mid_" + k] = mid[a]
            exp["out_" + k] = init[a]
        bad = {k: (hex(r.values.get(k, -1)), hex(w)) for k, w in exp.items() if r.values.get(k) != w}
        s.expect_true("temp_const", r.error is None and not bad, "v=0x%X b=%d" % (v, b), "%s %s" % (r.error, bad))
        after = {a: m.dw(a) for a in init}
        s.expect_true("temp_const", after == init, "restored v=0x%X" % v)
    # --- temporary 변수 번호 ---
    tcases = [(0, 0x1234ABCD), (1, M32), (2, 0), (3, 0x80000000), (129, 0x55AA55AA)]
    tcases += [(rng.randrange(130), rng.getrandbits(32)) for _ in range(12)]
    for i, v in tcases:
        s.reset()
        init = _fill(m, rng, NOW_REGIONS)
        r = s.run("temp_var", {"i": i, "v": v})
        exp = {"mid_w": v & 0xFFFF, "mid_e": v & 0xFF, "mid_y": v & 0xFFFF, "mid_h": v}
        a_p = 0x664080 + 4 * i
        exp["mid_p"] = (init[a_p] & ~0xF0 | v & 0xF0) & M32
        exp["out_w"] = (init[loc(0x656EB0, 2, i, 2)[0]] >> loc(0x656EB0, 2, i, 2)[1]) & 0xFFFF
        exp["out_e"] = (init[loc(0x663150, 1, i, 1)[0]] >> loc(0x663150, 1, i, 1)[1]) & 0xFF
        exp["out_y"] = (init[0x662860 + 4 * i] >> 16) & 0xFFFF
        exp["out_h"] = init[0x662350 + 4 * i]
        exp["out_p"] = init[a_p]
        bad = {k: (hex(r.values.get(k, -1)), hex(w)) for k, w in exp.items() if r.values.get(k) != w}
        s.expect_true("temp_var", r.error is None and not bad, "i=%d v=0x%X" % (i, v), "%s %s" % (r.error, bad))
        after = {a: m.dw(a) for a in init}
        s.expect_true("temp_var", after == init, "restored i=%d" % i,
                      str([(hex(a), hex(after[a]), hex(init[a])) for a in init if after[a] != init[a]][:3]))
    s.reset()
    for v in (5, 0xFFFFFFFF):
        m.setdw(0x662350 + 80, 0x77)
        r = s.run("temp_later", {"v": v})
        s.expect_true("temp_later", r.error is None and r.values["mid"] == v and r.values["out"] == 0x77 and m.dw(0x662350 + 80) == 0x77,
                      "v=0x%X" % v, str(r))
    s.reset()
    # --- 64개 묶음 경계 ---
    for n in EMIT_NS:
        cnt, trig, nacts = info["emit"][n]
        want_t = math.ceil(n / 64)
        s.expect_true("emit_%d" % n, (cnt, trig, nacts) == (want_t, want_t, n), "count", str((cnt, trig, nacts)))
        for k in range(130):
            m.setdw(MINRANGE + 4 * k, 0)
        r = s.run("emit_%d" % n)
        ok = all(m.dw(MINRANGE + 4 * k) == (0x1000 + k if k < n else 0) for k in range(130))
        s.expect_true("emit_%d" % n, r.error is None and ok, "applied")
        s.expect_true("emit_%d" % n, r.steps and r.steps[0] == want_t, "exec", str(r.steps))
    s.reset()


# ---------------------------------------------------------------------------------------------
# (3') 에뮬레이터: 따로 빌드 (빌드 밖 선언, EUD Editor 목록, 빈 빌드)
# ---------------------------------------------------------------------------------------------


def _program(body=lambda: None):
    LoadMap(BASE_MAP)
    CompressPayload(True)
    prog = emu.Program(body)
    return prog.build()


def separate_builds(ck):
    rng = random.Random(99)
    # --- 빌드 밖(단계 0) 선언 → 빌드마다 적용, 합치기 결과 = 순서대로 적용 ---
    dat.clear()
    ck.eq("phase outside", _compat.onstart_phase(), 0)
    for _ in range(150):
        r = rng.random()
        if r < 0.1:
            dat.raw(SetMemory(0x662350 + 4 * rng.randrange(8), ep.Add, rng.getrandbits(32)))
        elif r < 0.2:
            dat.unit(rng.randrange(8)).mask("baseProperty", rng.getrandbits(32), rng.getrandbits(32))
        else:
            name = rng.choice(["maxHp", "armor", "elevation", "hasShield", "unitBoundsL", "unitBoundsB", "buildingDimY"])
            f = dat.field("units", name)
            dat.unit(rng.randrange(8)).set(**{name: rng.randint(0, 1 if f.bit else f.full_mask)})
    dat.from_eud_editor([(0x6C9EF8, 5), (0x6C9EF8, -2)])
    entries = dat.START.entries()
    merged = dat.START.writes(True)
    ck.true("merged smaller", len(merged) < len(entries), "%d/%d" % (len(merged), len(entries)))
    addrs = {e[0] for e in entries}
    for build_no in range(2):
        m = _program()
        init = {a: rng.getrandbits(32) for a in addrs}
        m.init_mem(init)
        m.cycle()
        want = dat.simulate(entries, dict(init))
        got = {a: m.dw(a) for a in want}
        ck.eq("phase0 build %d memory" % build_no, got, want)
        ck.eq("phase0 build %d last_emit" % build_no, dat.START.last_emit, (len(merged), math.ceil(len(merged) / 64)))
        for a in addrs:
            m.setdw(a, 0x5A5A5A5A)
        m.cycle(2)
        ck.true("phase0 build %d once" % build_no, all(m.dw(a) == 0x5A5A5A5A for a in addrs))
    dat.clear()
    # --- EUD Editor 목록 (빌드 중 선언) ---
    for tag, path, n, trig in (("M2", M2_DAT, 1182, 19), ("UERE", UERE_DAT, 773, 13)):
        if not os.path.isfile(path):
            continue
        pairs = _lua_pairs(path)
        m = _program(lambda path=path: dat.from_eud_editor(path))
        init = {a: rng.getrandbits(32) for a, _v in pairs}
        m.init_mem(init)
        m.cycle()
        want = dat.simulate([(a, "Add", v & M32, M32) for a, v in pairs], dict(init))
        ck.eq("%s emu memory" % tag, {a: m.dw(a) for a in want}, want)
        ck.eq("%s triggers" % tag, dat.START.last_emit, (n, trig))
        ck.eq("%s exec" % tag, m.ends[-1][0] - _empty_steps(), trig)
    # --- 빈 빌드: 앞 빌드의 선언이 남지 않는다 ---
    dat.START.last_emit = None
    m = _program()
    m.cycle()
    ck.true("empty build no emit", dat.START.last_emit in (None, (0, 0)), str(dat.START.last_emit))  # 빌드 밖 훅은 남아 빈 목록을 낸다
    ck.eq("empty build memory", m.dw(0x664504), 0)
    ck.eq("persist empty", (len(dat.START.entries()), len(dat.EVERY_FRAME.entries())), (0, 0))


_EMPTY = []


def _empty_steps():
    if not _EMPTY:
        dat.START.last_emit = None
        m = _program()
        m.cycle()
        _EMPTY.append(m.ends[-1][0])
    return _EMPTY[0]


def late_declare_check(ck):
    """주 함수 뒤 시작 함수에서 선언 → 오류(이미 내보냄). 빌드가 중간에 끊기므로 맨 마지막에 한다."""
    def body():
        dat.unit(1).set(armor=1)

        def late():
            dat.unit(2).set(armor=2)

        EUDOnStart(late)

    ck.raises("declare after emit", EudextError, _program, body)


# ---------------------------------------------------------------------------------------------
# (5) epScript 예제
# ---------------------------------------------------------------------------------------------


def _repo_artifacts():
    found = []
    for dirpath, dirnames, filenames in os.walk(_common.PKG):
        rel = os.path.relpath(dirpath, _common.PKG)
        if rel.startswith("docs"):
            continue
        for d in dirnames:
            if d in ("__pycache__", "__epspy__"):
                found.append(os.path.join(rel, d))
        for f in filenames:
            if f.endswith((".scx", ".pyc")) and not (rel == "testing" and f == "base.scx"):
                found.append(os.path.join(rel, f))
    return found


def example_checks(ck):
    from eudext.tools import build

    src = open(os.path.join(EX, "datpatch_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("datpatch_example.eps", src)
    ck.eq("eps errors", nerr, 0)
    out = out or ""
    for frag in ("from eudext import datpatch as dat", "dat.f_unit(\"Terran Marine\").set(maxHp=80 * 256, armor=2)",
                 "flags(Flyer=True, Invincible=True)", "dat.f_values(0x400200, 0x480200)",
                 "dat.tep.SetUnitsDatX(162,", "dat.f_every_frame().unit(1)", "dat.f_begin_actions()",
                 "acts = dat.f_end_actions()", "dat.f_begin_temporary()", "dat.now.weapon(", "dat.f_end_temporary()",
                 "dat.f_player_unit_enable(5, players=FlattenList([0, 1, 2]), value=1)"):
        ck.true("eps has %s" % frag, frag in out, "")
    # 단독 빌드 (작업 폴더 사본)
    sa = os.path.join(_common.WORK, "t_datpatch", "standalone")
    os.makedirs(sa, exist_ok=True)
    for n in ("datpatch_example.py", "datpatch_example.eps"):
        shutil.copy2(os.path.join(EX, n), os.path.join(sa, n))
    dat.clear()
    path = build.standalone([os.path.join(sa, "datpatch_example.py"), os.path.join(sa, "datpatch_example.eps")],
                            out=os.path.join(sa, "datpatch_sa.scx"))
    ck.true("standalone output", os.path.getsize(path) > 10000, path)
    ck.true("standalone start list", dat.START.last_emit is not None and dat.START.last_emit[0] > 20, str(dat.START.last_emit))
    # py 의 unit(0)·eps 의 unit(1) requirementOffset 은 같은 dword(0x660A70) → 1액션으로 합쳐진다
    ck.eq("standalone every_frame", dat.EVERY_FRAME.last_emit, (1, 1))
    dat.clear()
    # euddraft 빌드 (별도 프로세스)
    if os.path.isfile(build.EUDDRAFT):
        work = os.path.join(_common.WORK, "t_datpatch", "euddraft")
        eds, out_map = build.prepare_eds(os.path.join(EX, "datpatch_example.eds"), work)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, "datpatch.log"))
        print("  " + r.summary())
        ck.true("euddraft ok", r.ok, r.log[-2000:])
        ck.true("euddraft eps compiled", '[epScript] Compiling "datpatch_example.eps"' in r.log)
        ck.true("euddraft boot", "[eudext] 0.0.1 (eudplib 0.81.0)" in r.log)
    else:
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py)
# ---------------------------------------------------------------------------------------------


def _cost_list(n, field_name="maxHp"):
    def build(t):
        lst = dat.PatchList("cost")
        mask = dat.field("units", field_name).full_mask
        for k in range(n):
            lst.unit(k).set(**{field_name: (0x100 + k) & mask})
        dat.emit(lst)

    return build


def _cost_scdata(n):
    def build(t):
        for k in range(n):
            ep.TrgUnit(k).maxHp = 0x100 + k

    return build


def _cost_eud_editor(path):
    def build(t):
        lst = dat.PatchList("cost")
        lst.from_eud_editor(path)
        dat.emit(lst)

    return build


def _cost_ability(t):
    lst = dat.PatchList("cost")
    tep = dat.Tep()
    tep.warn = False
    tep.SetUnitAbility(21, 18, 3, 1, 17000, 500, (8, 9, 10, 11), 30, 450, 20, (5, 10, 15), None, 160, 5, None, "K", 2000, 7,
                       target=lst)
    dat.emit(lst)


def _cost_bounds(t):
    lst = dat.PatchList("cost")
    lst.unit(3).set(unitBoundsL=10, unitBoundsT=12, unitBoundsR=11, unitBoundsB=13)
    dat.emit(lst)


def _cost_enable(t):
    lst = dat.PatchList("cost")
    for u in (0, 1, 2, 3):
        lst.player_unit_enable(u, players=range(5), value=1)
    dat.emit(lst)


def _cost_temp_var(t):
    i, v = t.var("i"), t.var("v")
    with dat.temporary():
        dat.now.weapon(i).set(damage=v)


def _cost_temp_const(t):
    v = t.var("v")
    with dat.temporary():
        dat.now.weapon(5).set(damage=v)


COST_CASES = [
    CostCase("시작 목록 64필드(maxHp, dword 64개) → emit", _cost_list(64), note="scdata 대입 64줄 대비"),
    CostCase("시작 목록 228필드(maxHp 전 유닛) → emit", _cost_list(228)),
    CostCase("시작 목록 228필드(armor, 바이트 → 57 dword 로 합쳐짐)", _cost_list(228, "armor"), note="합치기"),
    CostCase("참고: scdata 대입문 64줄 (TrgUnit(k).maxHp = …)", _cost_scdata(64), note="한 줄 = 트리거 1"),
    CostCase("참고: scdata 대입문 228줄", _cost_scdata(228)),
    CostCase("EUD Editor M2 1,182줄 → emit", _cost_eud_editor(M2_DAT), note="S5 A.8: 19 트리거"),
    CostCase("EUD Editor UERE 773줄 → emit", _cost_eud_editor(UERE_DAT), note="S5 A.8: 13 트리거"),
    CostCase("tep.SetUnitAbility 1회 (28 액션)", _cost_ability, note="합친 뒤 액션 수로 1 트리거"),
    CostCase("유닛 크기 L/T/R/B (4필드 → 2액션)", _cost_bounds),
    CostCase("player_unit_enable 4유닛×5명 (20필드)", _cost_enable),
    CostCase("now 상수 번호·상수 값 (damage)", lambda t: dat.now.weapon(5).set(damage=100)),
    CostCase("now 상수 번호·변수 값 (maxHp)", lambda t: dat.now.unit(5).set(maxHp=t.var("v")), {"v": 7}),
    CostCase("now 변수 번호·변수 값 (maxHp, 간격 4)", lambda t: dat.now.unit(t.var("i")).set(maxHp=t.var("v")), {"i": 5, "v": 7}),
    CostCase("now 변수 번호·변수 값 (damage, 간격 2)", lambda t: dat.now.weapon(t.var("i")).set(damage=t.var("v")),
             {"i": 5, "v": 7}, note="scdata 곱셈 캐시"),
    CostCase("now 변수 번호·변수 값 (elevation, 간격 1)", lambda t: dat.now.unit(t.var("i")).set(elevation=t.var("v")),
             {"i": 5, "v": 7}),
    CostCase("now 변수 번호·변수 값 (buildingDimY, eudext 전용)", lambda t: dat.now.unit(t.var("i")).set(buildingDimY=t.var("v")),
             {"i": 5, "v": 7}),
    CostCase("temporary 상수 번호 워드 필드 + 되돌리기", _cost_temp_const, {"v": 7}, note="읽기·합치기·f_dwpatch_epd·f_unpatchall"),
    CostCase("temporary 변수 번호 워드 필드 + 되돌리기", _cost_temp_var, [{"i": 4, "v": 7}, {"i": 5, "v": 7}],
             note="subp 분기 2개"),
]


def main():
    LoadMap(BASE_MAP)  # 이름 문자열 번호 변환에 맵이 필요하다 (euddraft 는 플러그인보다 맵을 먼저 읽는다)
    ck = Checker("t_datpatch (python)")
    table_checks(ck)
    a8_checks(ck)
    eud_editor_checks(ck)
    ok1 = ck.report()

    dat.clear()
    info = {}
    s = Suite("t_datpatch")
    build_cases(s, info)
    ck2 = Checker("t_datpatch (emu)")
    s.build()
    run_checks(s, info, ck2)
    ok2 = s.report()

    before = set(_repo_artifacts())
    separate_builds(ck2)
    example_checks(ck2)
    late_declare_check(ck2)
    ck2.eq("repo clean", sorted(set(_repo_artifacts()) - before), [])
    ok3 = ck2.report()
    finish(ok1, ok2, ok3)


if __name__ == "__main__":
    main()
