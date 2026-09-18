"""eudext.datpatch — dat 필드 표와 dat 패치 목록 (DESIGN 4.16, 정본 명세 `docs/spec/S5_dat_bgm.md` A절).

템플릿 `SetUnitsDatX`/`SetWeaponsDatX`/`PatchInsert`(8맵, 호출 지점 722곳) 를 eudplib 방식으로 옮긴다.

    from eudext import datpatch as dat
    dat.unit(208).set(maxHp=5000 * 256, elevation=20)      # 필드 이름 = scdata 멤버 이름. 시작 시 1회 목록
    dat.unit(208).flags(Flyer=True, Invincible=True)        # baseProperty 비트 (이름은 scdata)
    dat.unit(162).mask("baseProperty", 0x400200, 0x480200) # {값, 마스크}
    dat.unit(162).set(buildingDimX=1, buildingDimY=1)       # scdata 로 안 되는 칸은 eudext 표(A.4)
    dat.weapon(1).splash(7, 14, 21)
    dat.player_unit_enable("Terran Marine", players=range(5), value=1)
    dat.tep.SetUnitsDatX(162, {"AdvFlag": (0x400200, 0x480200), "BdDimX": 1})   # TEP 키·변환 그대로
    dat.from_eud_editor("EUDEditorDat.lua")                 # EUD Editor Add 목록, 순서 유지
    dat.every_frame().unit(0).set(requirementOffset=0)      # 매 프레임 목록
    acts = dat.actions(lambda d: d.weapon(128).set(damage=65535))   # 액션 목록만 (조건 블록용)
    with dat.temporary():                                   # f_dwpatch_epd … f_unpatchall
        dat.now.weapon(w).set(damage=v)                     # 변수 번호·값 허용, 그 자리에서 실행
    dat.field("units", "maxHp"); dat.addr("weapons", "damage", 127)

동작 요약
- **시작 목록**: 선언은 컴파일 시점 상수만 받는다. scdata 대입문(`TrgUnit(208).maxHp = …`)은 한 줄이 그 자리
  트리거 1개라 수백 줄이면 트리거 수백 개다. 여기서는 scdata 디스크립터의 주소 정보(offset·stride·크기)만 빌려
  원시 액션(`SetMemory`/`SetMemoryX`)을 모으고, 같은 dword 에 연달아 쓰는 SetTo 는 한 액션으로 합친 뒤
  **64개씩** 트리거로 낸다(N 액션 → ceil(N/64) 트리거, 게임 시작 1회, 주 함수보다 먼저).
  - 모듈 import 때(빌드 밖) 선언한 것은 빌드마다, 빌드 중(onPluginStart·beforeTriggerExec 안) 선언한 것은
    그 빌드에만 들어간다. 주 함수 코드를 다 만든 뒤에 선언하면 오류(이미 내보냄).
  - 같은 칸을 두 번 선언하면 뒤의 값이 이긴다(`set_debug(True)` 면 경고).
- **매 프레임 목록**(`every_frame()`): 게임 루프 시작점(beforeTriggerExec 앞)에서 매 프레임 적용.
- **액션 목록**(`actions()`, `begin_actions()`/`end_actions()`): 조건 블록 안에서 `DoActions`/`emit` 로 쓴다.
- **즉시 쓰기**(`now`): 번호·값이 변수여도 된다. 상수면 `SetMemoryX` 1액션, 변수면 scdata 멤버 쓰기를 그대로 부른다.
  `temporary()` 안에서는 `f_dwpatch_epd` 로 dword 를 통째 바꾸고(폭 1·2 필드는 지금 dword 를 읽어 합친다)
  블록 끝에서 `f_unpatchall` 로 되돌린다.
- **TEP 이식 층**(`tep`): 키 이름과 변환(HP×256, SuppCost×2, Shield/Splash bool, Playerable 2 …)을 TEP 그대로.
  `WhatSndInit`/`WhatSndEnd` 는 TEP 주소(eudplib·EUD Editor 와 이름이 반대)를 그대로 쓰고, `Reqptr` 는 TPL 처럼
  무시한다 — 둘 다 컴파일 시점 경고를 낸다(DESIGN 7절 D19, 권장안).

어느 수단을 쓸까 (S5 A.6)
- 게임 내내 고정이고 **맵 CHK 로 표현되는 값**(체력·실드·아머·비용·빌드 시간·이름·무기 피해, 업그레이드·테크 비용,
  플레이어별 생산 가능·업그레이드·테크): 맵 편집기(SCMDraft 유닛/업그레이드 설정). 트리거 0개.
- 고정이지만 CHK 로 안 되는 값(투사 방식, flingy, iscript, AI 주문, 크기, 특수 능력 …): `datpatch` 시작 목록 **또는**
  EUD Editor — **한 필드의 출처는 하나만**(EUD Editor 는 Add 차분이라 SetTo 와 섞이면 순서에 따라 값이 달라진다).
- EUD Editor 를 이미 쓰는 맵을 옮길 때: `from_eud_editor` 로 같은 Add 목록을 같은 순서로 낸 뒤, 새 값은 SetTo 로 그 뒤에.
- 게임이 되돌리는 칸(요구사항 오프셋 등): `every_frame()`.
- 페이즈·모드에 따라 바뀌는 값: `actions()` 를 조건 블록에 / 되돌려야 하면 `temporary()`.
- 파일 통째(tbl 등 포인터로 가리키는 자료): euddraft `[dataDumper]`. dat 배열에는 해당 없음.

epScript: `import eudext.datpatch as dat;` — 모듈 함수는 `dat.unit(…)` → `dat.f_unit(…)` 로 번역된다(`f_` 이름이 정본).
리스트 리터럴 `[a, b]` 는 EUDArray 로 번역되므로 묶음 값은 `dat.values(a, b)` 또는 epScript `list(a, b)`
(→ 파이썬 리스트)로 넘긴다(`py_list(a, b)` 는 파이썬 `list(a, b)` 로 번역돼 실행 오류). `with` 가 없으니
`dat.begin_temporary(); … dat.end_temporary();`, `dat.begin_actions(); … const acts = dat.end_actions();` 를 쓴다.

출처: 템플릿 `reference/MSF-Template/func.lua:27~456`(정본), theSeed `Engine/func.lua:10~535`(필드가 가장 많음),
CtrigAsm `SetMemoryB/W`(`reference/MapSource/Library/CtrigAsm v5.5.lua:43497~43541`, 4바이트 경계로 내린 주소 + 시프트
값 + 마스크), eudplib 0.81 `scdata`·`eudlib/utilf/mempatch.py`. DPS eudplib 이식판(`eudplib-port` a7aad90)에는
dat 패치용 파이썬 코드가 없다(Lua 헬퍼를 lupa 로 돌림, 바이트·워드 규칙은 `eud/spec/G6_arr_mem.md:234` 와 같음).
"""

import contextlib
import difflib
import os
import re

import eudplib as ep
from eudplib import (
    Add,
    EUDEndIf,
    EUDIf,
    EUDIfNot,
    EUDOnStart,
    EUDVariable,
    FlattenList,
    RawTrigger,
    SetMemory,
    SetMemoryX,
    SetTo,
    Subtract,
    Trigger,
    f_bitlshift,
    f_bwrite_epd,
    f_dwread_epd,
    f_dwwrite_epd,
    f_maskwrite_epd,
    f_wwrite_epd,
    unProxy,
)

from eudext import _compat, _parts
from eudext import datpatch_tables as _tb
from eudext.errors import fail, warn

M32 = 0xFFFFFFFF
CHUNK = 64
DEBUG = False
EPD0 = 0x58A364

__all__ = [
    "CHUNK",
    "EVERY_FRAME",
    "START",
    "DatRow",
    "Field",
    "PatchList",
    "Tep",
    "actions",
    "all_unit_size",
    "addr",
    "begin_actions",
    "begin_temporary",
    "clear",
    "damage_ratio",
    "emit",
    "end_actions",
    "end_temporary",
    "every_frame",
    "f_actions",
    "f_all_unit_size",
    "f_addr",
    "f_begin_actions",
    "f_begin_temporary",
    "f_clear",
    "f_damage_ratio",
    "f_emit",
    "f_end_actions",
    "f_end_temporary",
    "f_every_frame",
    "f_field",
    "f_flingy",
    "f_from_eud_editor",
    "f_image",
    "f_parse_eud_editor",
    "f_player_unit_enable",
    "f_raw",
    "f_set_debug",
    "f_sprite",
    "f_start",
    "f_tech",
    "f_unit",
    "f_unpatch_all",
    "f_upgrade",
    "f_values",
    "f_weapon",
    "field",
    "flingy",
    "from_eud_editor",
    "image",
    "now",
    "parse_eud_editor",
    "player_unit_enable",
    "raw",
    "set_debug",
    "sprite",
    "start",
    "tech",
    "temporary",
    "tep",
    "unit",
    "unpatch_all",
    "upgrade",
    "values",
    "weapon",
]


# =============================================================================================
# 필드 표
# =============================================================================================


class Field:
    """dat 필드 하나의 배치: 주소 = base + (번호 − first) × stride, 크기 size 바이트.

    인자: dat(표 이름), name(필드 이름), base, size(1·2·4), stride, count(원소 수), first(첫 번호),
          member(scdata 디스크립터 또는 None), bit(비트 멤버면 비트 마스크), kind(scdata 종류 이름), note
    반환: -
    비용: 없음(컴파일 시점 자료)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const f = dat.field("units", "maxHp");` 뒤 `f.base`, `f.size` …
    출처: S5 A.7 `Field(base=0x662350, size=4, stride=4, count=228, member=TrgUnit.maxHp)`
    """

    __slots__ = ("dat", "name", "base", "size", "stride", "count", "first", "member", "bit", "kind", "note")

    def __init__(self, dat, name, base, size, stride, count, first=0, member=None, bit=None, kind=None, note=""):
        self.dat = dat
        self.name = name
        self.base = base
        self.size = size
        self.stride = stride
        self.count = count
        self.first = first
        self.member = member
        self.bit = bit
        self.kind = kind
        self.note = note

    @property
    def last(self):
        """마지막 번호."""
        return self.first + self.count - 1

    @property
    def full_mask(self):
        """필드 폭 전체 마스크(시프트 전). 비트 멤버도 바이트 전체."""
        return (1 << (8 * self.size)) - 1

    def contains(self, index):
        """번호가 이 필드의 범위 안인가."""
        return self.first <= index <= self.last

    def location(self, index, full=False):
        """상수 번호 → (4바이트 경계로 내린 주소, 시프트 비트 수, 시프트한 마스크).

        full=True 면 비트 멤버도 바이트 전체 마스크를 쓴다.
        """
        off = self.base + (index - self.first) * self.stride
        sub = off & 3
        shift = 8 * sub
        width = self.full_mask if (full or self.bit is None) else self.bit
        return off - sub, shift, (width << shift) & M32

    def widened(self, size):
        """TEP 처럼 더 넓게(바이트·dword 통째) 쓰는 사본. scdata 쓰기 경로는 쓰지 않는다."""
        return Field(self.dat, self.name, self.base, size, self.stride, self.count, self.first,
                     None, None, None, "%s (폭 %d 로 씀)" % (self.note, size))

    def __repr__(self):
        if self.member is not None:
            owner = _DAT_CLASS[self.dat].__name__ if self.dat in _DAT_CLASS else "?"
            mem = "%s.%s" % (owner, self.name)
        else:
            mem = None
        extra = "" if self.first == 0 else ", first=%d" % self.first
        bit = "" if self.bit is None else ", bit=0x%X" % self.bit
        return "Field(base=0x%X, size=%d, stride=%d, count=%d%s%s, member=%s)" % (
            self.base, self.size, self.stride, self.count, extra, bit, mem)


_DAT_CLASS = {}
_DAT_ENCODE = {}
_DAT_COUNT = {}
_ALIASES = {}
_FIELDS = {}


def _build_tables():
    _compat.check_datpatch()
    for dat, (clsname, encname, aliases) in _tb.DATS.items():
        cls = getattr(ep, clsname)
        first, last, _step = cls.range
        count = last - first + 1
        _DAT_CLASS[dat] = cls
        _DAT_ENCODE[dat] = getattr(ep, encname)
        _DAT_COUNT[dat] = count
        for a in (dat,) + tuple(aliases):
            _ALIASES[a.lower()] = dat
        fields = {}
        for name, desc in _compat.scdata_members(cls):
            info = _compat.scdata_member_info(desc)
            if not info["implemented"] or info["layout"] != "array":
                continue
            cnt = _tb.COUNT_OVERRIDE.get((dat, name), count)
            fields[name] = Field(dat, name, info["offset"], info["size"], info["stride"], cnt, 0,
                                 desc, info["bit"], info["kind"], "scdata")
        _FIELDS[dat] = fields
    for dat, aliases in _tb.PSEUDO_DATS.items():
        _FIELDS[dat] = {}
        _DAT_ENCODE[dat] = None
        for a in (dat,) + tuple(aliases):
            _ALIASES[a.lower()] = dat
    _DAT_COUNT["players"] = _tb.PLAYER_COUNT * _tb.UNIT_COUNT
    _DAT_COUNT["damage"] = _tb.DAMAGE_TYPES * _tb.DAMAGE_SIZES
    for dat, name, base, size, stride, first, count, note in _tb.EXTRA_FIELDS:
        if isinstance(base, tuple):
            _tag, mname, delta = base
            desc = dict(_compat.scdata_members(_DAT_CLASS[dat]))[mname]
            base = _compat.scdata_member_info(desc)["offset"] + delta
        if count is None:
            count = _DAT_COUNT[dat]
        _FIELDS[dat][name] = Field(dat, name, base, size, stride, count, first, None, None, None, note)


_build_tables()


def _dat_key(table):
    if isinstance(table, type):
        table = table.__name__
    key = _ALIASES.get(str(table).lower())
    if key is None:
        fail("dat 표 이름 %r 을(를) 모릅니다 (가능: %s)", table, ", ".join(_FIELDS))
    return key


def _lookup(dat, name):
    f = _FIELDS[dat].get(name)
    if f is None:
        near = difflib.get_close_matches(str(name), list(_FIELDS[dat]), n=3)
        hint = (" — 비슷한 이름: " + ", ".join(near)) if near else ""
        fail("%s 표에 %r 필드가 없습니다 (이름은 eudplib scdata 멤버 이름)%s", dat, name, hint)
    return f


def field_names(table):
    """표의 필드 이름 목록 (scdata 멤버 + eudext 전용).

    인자: table(표 이름)
    반환: list[str]
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    return list(_FIELDS[_dat_key(table)])


def f_field(table, name):
    """필드 배치 정보(`Field`)를 돌려준다.

    인자: table("units"·"weapons"·"flingy"·"upgrades"·"techdata"·"sprites"·"images"·"players"·"damage" 또는 별칭),
          name(scdata 멤버 이름 또는 eudext 전용 이름)
    반환: Field (base, size, stride, count, first, member …)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const f = dat.field("units", "maxHp");`
    출처: S5 A.7
    """
    return _lookup(_dat_key(table), name)


field = f_field


# =============================================================================================
# 번호·값 변환
# =============================================================================================


def _encode_index(dat, index, allow_var=False):
    x = unProxy(index)
    if isinstance(x, bool):
        fail("%s 번호에 bool 을 줄 수 없습니다", dat)
    if not isinstance(x, int):
        if isinstance(x, str) and _DAT_ENCODE.get(dat) is not None:
            x = unProxy(_DAT_ENCODE[dat](x))
        elif allow_var and _compat.is_var(x):
            return x
        else:
            fail("%s 번호는 정수 상수여야 합니다 (받은 값 %r). 변수 번호는 dat.now 를 쓰세요", dat, index)
    if not isinstance(x, int) or not 0 <= x < _DAT_COUNT[dat]:
        fail("%s 번호 %r 이(가) 범위 밖입니다 (0 ~ %d)", dat, x, _DAT_COUNT[dat] - 1)
    return x


def _check_index(field_, index):
    if isinstance(index, int) and not field_.contains(index):
        fail("%s.%s 는 번호 %d ~ %d 만 있습니다 (받은 값 %d)", field_.dat, field_.name, field_.first, field_.last, index)


def _const_value(field_, value):
    """상수 값을 정수로 바꾼다. 변수·식이면 None."""
    v = unProxy(value)
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, (tuple, list)):
        if len(v) == 2 and field_.size == 4 and (field_.kind == "PositionKind" or field_.name == "addonPlacement"):
            x, y = (_const_value(_WORD, a) for a in v)
            if x is None or y is None or not (0 <= x <= 0xFFFF and 0 <= y <= 0xFFFF):
                fail("%s.%s: (x, y) 는 0 ~ 65535 정수 두 개여야 합니다 (받은 값 %r)", field_.dat, field_.name, value)
            return x | (y << 16)
        fail("%s.%s: 값으로 %r 을(를) 줄 수 없습니다", field_.dat, field_.name, value)
    if _compat.is_var(v):
        return None
    if field_.member is not None and isinstance(v, str):
        v = _compat.scdata_cast(field_.member, v)
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int):
            return v
    if isinstance(v, str):
        fail("%s.%s: 문자열 값 %r 을(를) 번호로 바꿀 수 없습니다", field_.dat, field_.name, value)
    return None


_WORD = Field("-", "-", 0, 2, 2, 1)


def _range_of(field_):
    if field_.bit is not None:
        return 0, 1
    bits = 8 * field_.size
    return -(1 << (bits - 1)), (1 << bits) - 1


def _check_value(field_, v, label=None):
    lo, hi = _range_of(field_)
    if not lo <= v <= hi:
        if field_.bit is not None:
            fail("%s: 비트 필드는 0/1(True/False)만 받습니다 (받은 값 %r)", label or field_.name, v)
        fail("%s: %d바이트 필드의 범위 밖 값 %d (허용 %d ~ %d)", label or field_.name, field_.size, v, lo, hi)
    if field_.bit is not None:
        return v
    return v & field_.full_mask


_warned_fields = set()


def _warn_field(field_):
    key = (field_.dat, field_.name)
    msg = _tb.WARN_FIELDS.get(key)
    if msg and key not in _warned_fields:
        _warned_fields.add(key)
        warn("datpatch %s.%s: %s", field_.dat, field_.name, msg)


def _players_of(players):
    p = unProxy(players)
    if isinstance(p, (int, str)) or not hasattr(p, "__iter__"):
        items = [p]
    else:
        items = list(p)
    out = []
    for x in items:
        x = unProxy(x)
        if not isinstance(x, int):
            x = unProxy(ep.EncodePlayer(x))
        if isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < _tb.PLAYER_COUNT:
            fail("플레이어는 0 ~ %d (P1 ~ P12) 정수 상수여야 합니다 (받은 값 %r)", _tb.PLAYER_COUNT - 1, x)
        out.append(x)
    return out


def _enable_value(value):
    v = unProxy(value)
    if isinstance(v, bool):
        v = int(v)
    if v not in (0, 1):
        fail("player_unit_enable: value 는 0/1(True/False)만 받습니다 (받은 값 %r)", value)
    return v


def _damage_index(damage_type, size):
    dt = unProxy(damage_type)
    sz = unProxy(size)
    if isinstance(dt, str):
        dt = _compat.scdata_cast(_FIELDS["weapons"]["damageType"].member, dt)
    if isinstance(sz, str):
        sz = _compat.scdata_cast(_FIELDS["units"]["sizeType"].member, sz)
    for name, x, n in (("피해형", dt, _tb.DAMAGE_TYPES), ("크기", sz, _tb.DAMAGE_SIZES)):
        if isinstance(x, bool) or not isinstance(x, int) or not 0 <= x < n:
            fail("damage_ratio: %s 은(는) 0 ~ %d 정수여야 합니다 (받은 값 %r). 5 이상은 다른 칸을 덮어쓴다", name, n - 1, x)
    return dt * _tb.DAMAGE_SIZES + sz


# =============================================================================================
# 원시 쓰기 기록 (addr, mod, value, mask) · 합치기 · 액션 만들기
# =============================================================================================

_MOD_OF = {7: "SetTo", 8: "Add", 9: "Subtract"}
_MOD_OBJ = {"SetTo": SetTo, "Add": Add, "Subtract": Subtract}


def _decode_action(act):
    """SetMemory/SetMemoryX 모양(상수 필드) 액션이면 (addr, mod, value, mask), 아니면 None."""
    f = getattr(act, "fields", None)
    if not isinstance(f, (list, tuple)) or len(f) < 12:
        return None
    locid, _s, _w, _t, p1, p2, unit_, atype, amount, flags, _i, eudx = f[:12]
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in (locid, p1, p2, unit_, atype, amount, flags, eudx)):
        return None
    if atype != 45 or flags != 20 or 12 <= p1 <= 26:
        return None
    mod = _MOD_OF.get(amount)
    if mod is None:
        return None
    addr_ = (EPD0 + 4 * (unit_ * 12 + p1)) & M32
    mask = (locid & M32) if eudx == 0x4353 else M32
    return (addr_, mod, p2 & M32, mask)


def _to_action(w):
    addr_, mod, value, mask = w
    if mask == M32:
        return SetMemory(addr_, _MOD_OBJ[mod], value)
    return SetMemoryX(addr_, _MOD_OBJ[mod], value, mask)


def _merge(entries):
    """같은 주소에 연달아 쓰는 SetTo 를 하나로 합친다. 사이에 그 주소를 Add/Subtract 하거나 모르는 액션이 있으면 끊는다."""
    out = []
    last = {}
    for e in entries:
        if e[0] == "raw":
            out.append(e)
            last.clear()
            continue
        addr_, mod, value, mask = e
        if mod == "SetTo":
            j = last.get(addr_)
            if j is not None:
                a0, m0, v0, k0 = out[j]
                out[j] = (a0, m0, ((v0 & ~mask) | (value & mask)) & M32, (k0 | mask) & M32)
                continue
            last[addr_] = len(out)
            out.append((addr_, mod, value & mask, mask))
        else:
            last.pop(addr_, None)
            out.append(e)
    return out


def simulate(writes, memory=None):
    """쓰기 기록(또는 액션) 목록을 파이썬 dict 메모리에 적용한다(시험·확인용, 에뮬레이터와 같은 식).

    인자: writes(PatchList·액션·(addr, mod, value, mask) 목록), memory({주소: dword}, 없으면 새로)
    반환: memory
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: testing/emu.py `_act` 의 SetDeaths 식 (마스크 Add/Subtract 식은 S8 인게임 확인 전 가정)
    """
    mem = {} if memory is None else memory
    if isinstance(writes, PatchList):
        writes = writes.actions()
    for w in writes:
        if not isinstance(w, tuple):
            d = _decode_action(w)
            if d is None:
                fail("simulate: 흉내 낼 수 없는 액션 %r", w)
            w = d
        if w[0] == "raw":
            d = _decode_action(w[1])
            if d is None:
                fail("simulate: 흉내 낼 수 없는 액션 %r", w[1])
            w = d
        a, mod, v, m = w
        old = mem.get(a, 0)
        if mod == "SetTo":
            new = (old & ~m) | (v & m)
        elif mod == "Add":
            new = (old & ~m) | (((old & m) + (v & m)) & m)
        else:
            new = (old & ~m) | (max((old & m) - (v & m), 0) & m)
        mem[a] = new & M32
    return mem


# =============================================================================================
# 목록
# =============================================================================================


class DatRow:
    """dat 한 행(번호 하나)에 쓰기. `PatchList.unit(…)`, `dat.unit(…)`, `dat.now.unit(…)` 이 돌려준다.

    인자: sink(목록 또는 now), dat(표 이름), index(번호 — 목록은 상수, now 는 변수 가능)
    반환: -
    비용: 목록이면 트리거 0(내보낼 때 64액션당 1), now 면 `now` 설명
    CP: 바꾸지 않음
    로컬: 공유(게임 상태)
    epScript: `dat.unit(208).set(maxHp=5000 * 256);`
    출처: S5 A.7
    """

    __slots__ = ("_sink", "_dat", "_index")

    def __init__(self, sink, dat, index):
        self._sink = sink
        self._dat = dat
        self._index = sink._index(dat, index)

    def set(self, **values):
        """필드 여러 개를 값으로 쓴다(이름 = scdata 멤버 이름). 값은 원시 값(TEP 변환 없음).

        인자: 이름=값 … (값: 정수, bool, 이름 문자열(scdata 변환), 위치 필드는 (x, y))
        반환: self (이어 쓰기)
        비용: 목록 = 필드당 액션 1(같은 dword 는 합쳐짐) / now = 상수 1액션, 변수는 scdata 쓰기
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.unit(208).set(maxHp=5000 * 256, elevation=20);`
        출처: S5 A.7
        """
        self._sink._begin()
        try:
            for name, value in values.items():
                self._sink._set(_lookup(self._dat, name), self._index, value)
        finally:
            self._sink._end()
        return self

    def flags(self, *field_name, **bits):
        """비트 이름으로 켜고 끈다. 한 번에 준 비트는 마스크 쓰기 1개로 합친다.

        인자: field_name(생략하면 유닛 = baseProperty, 무기 = targetFlags), 비트이름=True/False …
        반환: self
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.unit(208).flags(Flyer=true, Invincible=true);`
        출처: eudplib scdata EnumMember 비트 이름 (theSeed AdvFlagBitArr 의 다른 이름은 dat.tep 에서)
        """
        if len(field_name) > 1:
            fail("flags: 필드 이름은 하나만 줄 수 있습니다 (%r)", field_name)
        fname = field_name[0] if field_name else _tb.DEFAULT_FLAG_FIELD.get(self._dat)
        if fname is None:
            fail("flags: %s 표는 기본 비트 필드가 없습니다 — flags(\"필드\", 비트=…) 로 주세요", self._dat)
        f = _lookup(self._dat, fname)
        masks = _compat.scdata_flag_masks(f.member) if f.member is not None else {}
        if not masks:
            fail("flags: %s.%s 는 비트 이름 표가 없습니다 — mask() 를 쓰세요", self._dat, fname)
        value = mask = 0
        for name, on in bits.items():
            m = masks.get(name)
            if m is None:
                near = difflib.get_close_matches(name, list(masks), n=3)
                fail("flags: %s.%s 에 %r 비트가 없습니다%s", self._dat, fname, name,
                     (" — 비슷한 이름: " + ", ".join(near)) if near else "")
            on = unProxy(on)
            if isinstance(on, bool):
                on = int(on)
            if on not in (0, 1):
                fail("flags: 비트 값은 True/False 상수여야 합니다 (%s=%r). 변수 값은 set()/mask() 를 쓰세요", name, on)
            mask |= m
            if on:
                value |= m
        if mask:
            self._sink._begin()
            try:
                self._sink._set_masked(f, self._index, value, mask)
            finally:
                self._sink._end()
        return self

    def mask(self, name, value, mask):
        """필드 안의 마스크 부분만 쓴다(값·마스크는 필드 기준, 시프트 전). TEP `AdvFlag={값, 마스크}`.

        인자: name(필드), value(상수, now 에서는 변수도 됨), mask(상수, 필드 폭 안 — 비트 필드도 바이트 전체까지)
        반환: self
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.unit(162).mask("baseProperty", 0x400200, 0x480200);`
        출처: TPL func.lua:185 `SetMemoryX(0x664080 + id*4, SetTo, k[1], k[2])`
        """
        f = _lookup(self._dat, name)
        m = unProxy(mask)
        if isinstance(m, bool) or not isinstance(m, int) or not 0 <= m <= f.full_mask:
            fail("mask: %s.%s 의 마스크는 0 ~ 0x%X 상수여야 합니다 (받은 값 %r)", self._dat, name, f.full_mask, mask)
        v = unProxy(value)
        if isinstance(v, bool):
            v = int(v)
        if isinstance(v, int):
            if not -(1 << (8 * f.size - 1)) <= v <= f.full_mask:
                fail("mask: %s.%s 의 값 %d 이(가) 필드 폭 밖입니다", self._dat, name, v)
            v &= m
        elif not _compat.is_var(v):
            fail("mask: 값은 정수 상수(now 에서는 변수도)여야 합니다 (받은 값 %r)", value)
        self._sink._begin()
        try:
            self._sink._set_masked(f, self._index, v, m)
        finally:
            self._sink._end()
        return self

    def splash(self, inner, middle, outer, explosion=3):
        """무기 스플래시: explosionType(기본 3 = SplashEnemy, TEP "일방형") + 반경 3개. TEP `Splash={안, 중, 밖}`.

        인자: inner, middle, outer(반경), explosion(폭발 형식 번호 또는 scdata 이름, 3 = SplashEnemy)
        반환: self
        비용: 액션 4
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.weapon(1).splash(7, 14, 21);`
        출처: TPL func.lua:49~53
        """
        if self._dat != "weapons":
            fail("splash 는 무기(dat.weapon)에만 쓸 수 있습니다")
        return self.set(explosionType=explosion, splashInnerRadius=inner,
                        splashMiddleRadius=middle, splashOuterRadius=outer)

    def __repr__(self):
        return "DatRow(%s, %r)" % (self._dat, self._index)


class PatchList:
    """상수 dat 쓰기를 모으는 목록. 내보낼 때 같은 dword 의 SetTo 를 합치고 64개씩 트리거로 낸다.

    인자: name(표시용)
    반환: -
    비용: 선언 트리거 0 / 내보내기 = ceil(액션 수 / 64) 트리거
    CP: 바꾸지 않음(목록에 사용자가 넣은 원시 액션 제외)
    로컬: 공유
    epScript: `dat.every_frame().unit(0).set(requirementOffset=0);`
    출처: TPL `PatchInsert`/`CtrigInitArr`, CtrigAsm `InitCtrig`(64개씩)
    """

    def __init__(self, name="list"):
        self.name = name
        self._items = []

    # --- 행 ---
    def unit(self, index):
        """이 목록의 유닛 행.

        인자: index(0~227 또는 이름 문자열 — 상수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 선언 트리거 0 (목록을 낼 때 64액션당 1)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.every_frame().unit(0).set(armor=1);`
        출처: TPL SetUnitsDatX
        """
        return DatRow(self, "units", index)

    def weapon(self, index):
        """이 목록의 무기 행.

        인자: index(0~129 또는 이름 — 상수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 선언 트리거 0 (목록을 낼 때 64액션당 1)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.every_frame().weapon(1).set(damage=10);`
        출처: TPL SetWeaponsDatX
        """
        return DatRow(self, "weapons", index)

    def flingy(self, index):
        """이 목록의 flingy 행.

        인자: index(0~208 — 상수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 선언 트리거 0 (목록을 낼 때 64액션당 1)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.every_frame().flingy(106).set(topSpeed=8000);`
        출처: theSeed SetFlingyDatX
        """
        return DatRow(self, "flingy", index)

    def upgrade(self, index):
        """이 목록의 업그레이드 행.

        인자: index(0~60 — 상수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 선언 트리거 0 (목록을 낼 때 64액션당 1)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.every_frame().upgrade(0).set(maxLevel=250);`
        출처: theSeed SetUpgradesDatX
        """
        return DatRow(self, "upgrades", index)

    def tech(self, index):
        """이 목록의 테크 행.

        인자: index(0~43 — 상수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 선언 트리거 0 (목록을 낼 때 64액션당 1)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.every_frame().tech(14).set(energyCost=0);`
        출처: eudplib scdata Tech
        """
        return DatRow(self, "techdata", index)

    def sprite(self, index):
        """이 목록의 스프라이트 행.

        인자: index(0~516 — 상수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 선언 트리거 0 (목록을 낼 때 64액션당 1)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.every_frame().sprite(5).set(image=10);`
        출처: theSeed SetSpritesDatX
        """
        return DatRow(self, "sprites", index)

    def image(self, index):
        """이 목록의 이미지 행.

        인자: index(0~998 — 상수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 선언 트리거 0 (목록을 낼 때 64액션당 1)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.every_frame().image(944).set(iscript=70);`
        출처: theSeed SetImageDatX
        """
        return DatRow(self, "images", index)

    def row(self, table, index):
        """아무 표의 행 (표 이름으로 고른다).

        인자: table(표 이름·별칭), index(상수)
        반환: DatRow
        비용: 선언 트리거 0
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.every_frame().row("units", 0).set(armor=1);`
        출처: 새로 작성
        """
        return DatRow(self, _dat_key(table), index)

    def player_unit_enable(self, unit_, players, value=1):
        """플레이어별 생산 가능 표(0x57F27C + P·228 + U)에 쓴다. TEP `Playerable`, CtrigAsm `SetUnitAvailable`.

        인자: unit_(번호·이름), players(플레이어 번호 0~11 하나 또는 목록), value(0/1)
        반환: self
        비용: 플레이어당 액션 1
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.player_unit_enable(5, players=dat.values(0, 1), value=1);`
        출처: TPL func.lua:127~145, CtrigAsm v5.5.lua:101365 SetUnitAvailable
        """
        u = _encode_index("units", unit_)
        f = _FIELDS["players"]["unitAvailability"]
        v = _enable_value(value)
        self._begin()
        try:
            for p in _players_of(players):
                self._put(f, p * _tb.UNIT_COUNT + u, v)
        finally:
            self._end()
        return self

    def damage_ratio(self, damage_type, size, value):
        """피해 배율 표(0x515B88 + 0x14·피해형 + 4·크기, 256 = 1배)에 쓴다. **주소 인게임 확인 전**(경고).

        인자: damage_type(0~4 또는 scdata 이름), size(0~4 또는 이름), value(dword)
        반환: self
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유(모든 플레이어·유닛 전역)
        epScript: `dat.damage_ratio(0, 1, 256);`
        출처: CtrigAsm v5.5.lua:101377 SetDamageMultiplier, theSeed func.lua:145 SetDamageRatio
        """
        f = _FIELDS["damage"]["ratio"]
        self._begin()
        try:
            self._set(f, _damage_index(damage_type, size), value)
        finally:
            self._end()
        return self

    def raw(self, *actions_):
        """원시 액션을 그대로 넣는다(TEP `PatchInsert`). SetMemory 모양이면 합치기에 참여한다.

        인자: 액션 …(목록 가능)
        반환: self
        비용: 액션 수만큼
        CP: 넣은 액션에 따름(CP 를 바꾸는 원시 액션은 넣지 않는다, DESIGN 3.6)
        로컬: 넣은 액션에 따름
        epScript: `dat.raw(SetMemory(0x58A364, SetTo, 1));`
        출처: TPL func.lua:32 PatchInsert
        """
        for act in FlattenList(list(actions_)):
            d = _decode_action(act)
            if d is not None and d[0] & ~3 == _parts.CP_ADDR:
                fail("raw: CP(0x6509B0) 를 바꾸는 원시 액션은 목록에 넣을 수 없습니다 (DESIGN 3.6)")
            self._append(d if d is not None else ("raw", act))
        return self

    def from_eud_editor(self, source, table="EUDEditorDatActs"):
        """EUD Editor 3 의 dat 편집분(Add 차분)을 **같은 순서**로 넣는다. 합치지 않는다.

        인자: source(EUDEditorDat.lua 처럼 `{주소, 차분}` 표가 있는 Lua 파일, EUD Editor 가 만든 DataEditor.py,
              또는 (주소, 차분) / (주소, "Add"|"SetTo", 값) 목록), table(Lua 표 이름)
        반환: 넣은 액션 수
        비용: 액션 수만큼 (1,182개 → 19 트리거)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.from_eud_editor("EUDEditorDat.lua");`
        출처: MSF_Memory_2 EUDEditorDat.lua·EUDEditorPort.lua:129~159, theSeed E3sDatReader.lua (S5 A.6)
        """
        items = parse_eud_editor(source, table)
        for a, mod, v in items:
            self._append((a, mod, v & M32, M32))
        return len(items)

    # --- 목록 프로토콜 (DatRow 가 부른다) ---
    def _index(self, dat, index):
        return _encode_index(dat, index)

    def _begin(self):
        pass

    def _end(self):
        pass

    def _set(self, field_, index, value):
        _check_index(field_, index)
        v = _const_value(field_, value)
        if v is None:
            fail("%s.%s: 목록에는 상수 값만 넣을 수 있습니다 (받은 값 %r). 실행 중 값은 dat.now 를 쓰세요",
                 field_.dat, field_.name, value)
        self._put(field_, index, _check_value(field_, v, "%s.%s" % (field_.dat, field_.name)))

    def _put(self, field_, index, v):
        """v 는 범위 검사를 마친 필드 값."""
        _check_index(field_, index)
        _warn_field(field_)
        a, shift, mask = field_.location(index)
        if field_.bit is not None:
            v = field_.bit if v else 0
        self._write(a, "SetTo", (v << shift) & mask, mask)

    def _set_masked(self, field_, index, value, mask):
        if not isinstance(value, int):
            fail("%s.%s: 목록에는 상수 값만 넣을 수 있습니다. 실행 중 값은 dat.now 를 쓰세요", field_.dat, field_.name)
        _check_index(field_, index)
        _warn_field(field_)
        a, shift, _m = field_.location(index, full=True)
        self._write(a, "SetTo", ((value & mask) << shift) & M32, (mask << shift) & M32)

    def _write(self, a, mod, value, mask):
        if DEBUG and mod == "SetTo":
            for e in self._all_items():
                if e[0] != "raw" and e[0] == a and e[1] == "SetTo" and e[3] & mask:
                    warn("datpatch %s: 0x%X (마스크 0x%X) 를 다시 씁니다 — 뒤의 값이 이깁니다", self.name, a, e[3] & mask)
                    break
        self._append((a, mod, value & M32, mask & M32))

    def _append(self, entry):
        self._target_items().append(entry)

    def _target_items(self):
        return self._items

    def _all_items(self):
        return list(self._items)

    # --- 결과 ---
    def entries(self):
        """넣은 순서 그대로의 기록 목록.

        인자: 없음
        반환: [(주소, "SetTo"|"Add"|"Subtract", 값, 마스크) 또는 ("raw", 액션)]
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const e = lst.entries();`
        출처: 새 작성
        """
        return self._all_items()

    def writes(self, merge=True):
        """기록 목록(merge=True 면 같은 dword 의 SetTo 를 합친 뒤).

        인자: merge(bool)
        반환: `entries()` 와 같은 모양
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const w = lst.writes();`
        출처: 새 작성
        """
        items = self._all_items()
        return _merge(items) if merge else items

    def actions(self, merge=True):
        """eudplib 액션 목록(merge=True 면 같은 dword SetTo 를 합친 뒤).

        인자: merge(bool)
        반환: list[Action]
        비용: 없음(액션 객체만)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `const acts = dat.every_frame().actions();`
        출처: 새로 작성
        """
        return [w[1] if w[0] == "raw" else _to_action(w) for w in self.writes(merge)]

    def emit(self, preserved=True, merge=True):
        """이 목록을 그 자리에 64개씩 조건 없는 트리거로 낸다(`f_emit`).

        인자: preserved(bool), merge(bool)
        반환: 낸 트리거 수
        비용: 호출 자리·실행 ceil(액션 수/64)
        CP: 넣은 원시 액션에 따름
        로컬: 공유
        epScript: `lst.emit();`
        출처: CtrigAsm InitCtrig
        """
        return f_emit(self.actions(merge), preserved=preserved)

    def clear(self):
        """목록을 비운다.

        인자: 없음
        반환: None
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `lst.clear();`
        출처: 새 작성
        """
        self._items = []

    def __len__(self):
        return len(self.writes(True))

    def __repr__(self):
        return "PatchList(%r, 기록 %d)" % (self.name, len(self._all_items()))


class _Scheduled(PatchList):
    """시작 1회(`START`) / 매 프레임(`EVERY_FRAME`) 목록. 빌드 밖 선언은 계속, 빌드 중 선언은 그 빌드에만."""

    def __init__(self, name, mode):
        super().__init__(name)
        self._mode = mode
        self._persist = []
        self._build = []
        self._hook = False
        self._registered = False
        self._emitted = False
        self.last_emit = None  # (액션 수, 트리거 수) — 마지막으로 내보낸 결과

    def _target_items(self):
        phase = _compat.onstart_phase()
        self._prepare(phase)
        return self._persist if phase == 0 else self._build

    def _all_items(self):
        return self._persist + self._build

    def _prepare(self, phase):
        # 빌드가 끝난 뒤(단계 0)의 선언은 다음 빌드부터 적용되는 "계속" 목록이라 막지 않는다.
        if self._emitted and phase != 0:
            fail("dat %s 목록은 이번 빌드에서 이미 내보냈습니다 — 지금 선언한 값은 적용되지 않습니다. "
                 "dat.actions()/dat.emit() 로 그 자리에 내세요", self.name)
        if self._mode == "frame":
            if not self._hook:
                _compat.on_game_loop_start(self._emit_now)
                self._hook = True
            return
        if phase == 0:
            if not self._hook:
                EUDOnStart(self._list1_hook)
                self._hook = True
        elif not self._registered:
            if phase >= 2:
                fail("주 함수 코드를 다 만든 뒤에는 dat 시작 목록에 넣을 수 없습니다 — dat.emit(...) 로 그 자리에 내세요")
            EUDOnStart(self._emit_now)  # 빌드 중 → 주 함수 뒤에 생성되는 시작 목록
            self._registered = True

    def _list1_hook(self):
        # 빌드 밖에서 등록한 시작 함수(주 함수보다 먼저 생성). 내보내기는 주 함수 뒤로 미룬다(그 뒤의 선언까지 보려고).
        if not self._registered:
            _compat.on_start_after_main(self._emit_now)
            self._registered = True

    def _emit_now(self):
        self._emitted = True
        acts = self.actions()
        n = f_emit(acts, preserved=(self._mode == "frame")) if acts else 0
        self.last_emit = (len(acts), n)

    def _reset_build(self):
        self._build = []
        self._registered = False
        self._emitted = False

    def clear(self):
        """빌드 밖·빌드 중 선언을 모두 지운다(시험용). 등록한 훅은 남는다(비어 있으면 아무것도 내지 않음)."""
        self._persist = []
        self._build = []

    def __repr__(self):
        return "PatchList(%r, 계속 %d, 이번 빌드 %d)" % (self.name, len(self._persist), len(self._build))


START = _Scheduled("start", "start")
EVERY_FRAME = _Scheduled("every_frame", "frame")
_stack = []


def _sink():
    return _stack[-1] if _stack else START


# =============================================================================================
# 모듈 함수 (현재 목록 = 시작 목록, begin_actions/actions 안에서는 그 목록)
# =============================================================================================


def f_unit(index):
    """현재 목록(기본: 시작 1회 목록)의 유닛 행.

    인자: index(유닛 번호 0~227 또는 이름 문자열 — 상수)
    반환: DatRow (`.set(…)`, `.flags(…)`, `.mask(…)`)
    비용: 선언 트리거 0 / 시작 목록 전체가 64액션당 트리거 1(1회 실행)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.unit("Terran Marine").set(armor=2);` (→ `dat.f_unit`)
    출처: TPL SetUnitsDatX
    """
    return _sink().unit(index)


def f_weapon(index):
    """현재 목록(기본: 시작 1회 목록)의 무기 행.

    인자: index(0~129 또는 이름 — 상수)
    반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
    비용: 선언 트리거 0 / 시작 목록 전체가 64액션당 트리거 1(1회 실행)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.weapon(1).splash(7, 14, 21);`
    출처: TPL SetWeaponsDatX
    """
    return _sink().weapon(index)


def f_flingy(index):
    """현재 목록의 flingy 행.

    인자: index(0~208 — 상수)
    반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
    비용: 선언 트리거 0 / 시작 목록 전체가 64액션당 트리거 1(1회 실행)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.flingy(106).set(topSpeed=8000);`
    출처: theSeed SetFlingyDatX
    """
    return _sink().flingy(index)


def f_upgrade(index):
    """현재 목록의 업그레이드 행.

    인자: index(0~60 — 상수)
    반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
    비용: 선언 트리거 0 / 시작 목록 전체가 64액션당 트리거 1(1회 실행)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.upgrade(0).set(maxLevel=250);`
    출처: theSeed SetUpgradesDatX
    """
    return _sink().upgrade(index)


def f_tech(index):
    """현재 목록의 테크 행.

    인자: index(0~43 — 상수)
    반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
    비용: 선언 트리거 0 / 시작 목록 전체가 64액션당 트리거 1(1회 실행)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.tech(14).set(energyCost=0);`
    출처: eudplib scdata Tech
    """
    return _sink().tech(index)


def f_sprite(index):
    """현재 목록의 스프라이트 행.

    인자: index(0~516 — 상수)
    반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
    비용: 선언 트리거 0 / 시작 목록 전체가 64액션당 트리거 1(1회 실행)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.sprite(5).set(image=10);`
    출처: theSeed SetSpritesDatX
    """
    return _sink().sprite(index)


def f_image(index):
    """현재 목록의 이미지 행.

    인자: index(0~998 — 상수)
    반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
    비용: 선언 트리거 0 / 시작 목록 전체가 64액션당 트리거 1(1회 실행)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.image(944).set(iscript=70);`
    출처: theSeed SetImageDatX
    """
    return _sink().image(index)


def f_player_unit_enable(unit_, players, value=1):
    """현재 목록에 플레이어별 생산 가능 값을 넣는다(`PatchList.player_unit_enable`).

    인자: unit_(번호·이름), players(0~11 하나 또는 목록), value(0/1)
    반환: 현재 목록
    비용: 플레이어당 액션 1
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.player_unit_enable(5, players=dat.values(0, 1, 2), value=1);`
    출처: TPL func.lua:127 Playerable, S5 A.8
    """
    return _sink().player_unit_enable(unit_, players, value)


def f_all_unit_size(value=1, first=0, last=None, target=None):
    """유닛 전체(또는 번호 범위)의 **충돌 상자**를 네 방향 모두 같은 값으로 만든다 (units.dat SizeL/U/R/D).

    인자: value(0~65535 — 네 방향 모두 이 값, 기본 1), first·last(유닛 번호 범위, 기본 0~227), target(선택: 넣을 PatchList)
    반환: 넣은 목록
    비용: 유닛당 액션 2개(dword 두 칸: SizeL|SizeU, SizeR|SizeD) — 228개면 액션 456 = 트리거 8개, 게임 시작 1회
    CP: 바꾸지 않음
    로컬: 공유 안전 (dat 는 모든 플레이어가 같다)
    epScript: `dat.all_unit_size(1);` (→ `dat.f_all_unit_size`)
    주의: 유닛이 서로 밀지 않게 되지만 **건물 배치·길찾기·선택 상자**도 같이 작아진다. 특히 **로케이션 판정**이
          유닛의 충돌 상자로 이뤄지므로, 점(또는 작은) 로케이션으로 큰 유닛을 잡던 트리거(Bring·RemoveUnitAt·
          KillUnitAt·MoveUnit)가 더는 잡지 못할 수 있다 (2026-09-18 인게임: 점 로케이션이 커맨드 센터를 놓쳤다).
          공중 유닛끼리 미는 것은
          충돌 상자와 별개다 — euddraft `[noAirCollision]`(또는 CtrigAsm `NoAirCollisionX`)를 같이 쓴다.
    출처: 새로 작성 (CtrigAsm `SetUnitsDatX(번호, {SizeL=1, SizeU=1, SizeR=1, SizeD=1})` 를 번호마다 부르는 것과 같다)
    """
    v = int(value)
    if not 0 <= v <= 0xFFFF:
        fail("datpatch.all_unit_size: 값은 0~65535 여야 합니다 (%r)", value)
    lo = int(first)
    hi = _tb.UNIT_COUNT - 1 if last is None else int(last)
    if not 0 <= lo <= hi <= _tb.UNIT_COUNT - 1:
        fail("datpatch.all_unit_size: 번호 범위가 0~%d 를 벗어납니다 (%r~%r)", _tb.UNIT_COUNT - 1, first, last)
    lst = _sink() if target is None else target
    row = {"SizeL": v, "SizeU": v, "SizeR": v, "SizeD": v}
    for u in range(lo, hi + 1):
        tep.SetUnitsDatX(u, row, target=lst)
    return lst


def f_damage_ratio(damage_type, size, value):
    """현재 목록에 피해 배율 칸을 넣는다(`PatchList.damage_ratio`, 주소 인게임 확인 전 — 경고).

    인자: damage_type(0~4 또는 이름), size(0~4 또는 이름), value(상수)
    반환: 현재 목록
    비용: 액션 1
    CP: 바꾸지 않음
    로컬: 공유(전역 표)
    epScript: `dat.damage_ratio(0, 1, 256);`
    출처: theSeed SetDamageRatio
    """
    return _sink().damage_ratio(damage_type, size, value)


def f_raw(*actions_):
    """현재 목록에 원시 액션을 넣는다(TEP `PatchInsert`).

    인자: 액션 …
    반환: 현재 목록
    비용: 액션 수만큼
    CP: 바꾸지 않음
    로컬: 넣은 액션에 따름
    epScript: `dat.raw(SetMemory(0x58A364, SetTo, 1));`
    출처: TPL PatchInsert
    """
    return _sink().raw(*actions_)


def f_from_eud_editor(source, table="EUDEditorDatActs"):
    """현재 목록에 EUD Editor dat 편집분(Add 차분)을 같은 순서로 넣는다(`PatchList.from_eud_editor`).

    인자: source(파일 또는 목록), table(Lua 표 이름)
    반환: 넣은 액션 수
    비용: 액션 수만큼 (1,182개 → 19 트리거)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.from_eud_editor("EUDEditorDat.lua");`
    출처: MSF_Memory_2 EUDEditorDat.lua
    """
    return _sink().from_eud_editor(source, table)


def f_start():
    """시작 1회 목록(`START`)을 돌려준다(`begin_actions` 안에서도 시작 목록에 넣을 때).

    인자: 없음
    반환: PatchList
    비용: 없음
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.start().unit(0).set(armor=1);`
    출처: TPL CtrigInitArr
    """
    return START


def f_every_frame():
    """매 프레임 목록(`EVERY_FRAME`)을 돌려준다. 게임 루프 시작점(beforeTriggerExec 앞)에서 매 프레임 적용.

    인자: 없음
    반환: PatchList
    비용: 매 프레임 ceil(액션 수 / 64) 트리거 실행
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.every_frame().unit(0).set(requirementOffset=0);`
    출처: theSeed func.lua:10 PatchInsertPrsv / PatchInput (TEP `PatchArrPrsv`)
    """
    return EVERY_FRAME


def f_actions(fn=None, merge=True):
    """새 목록에 fn(목록) 이 선언한 것을 모아 액션 목록으로 돌려준다(조건 블록용). fn 안의 `dat.unit(…)` 도 이 목록에 들어간다.

    인자: fn(목록을 받는 함수), merge(같은 dword SetTo 합치기)
    반환: list[Action] — `DoActions(acts)`, `Trigger(cond, acts)`, `dat.emit(acts)` 로 낸다
    비용: 선언 트리거 0 (낼 때 64액션당 1)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.begin_actions(); dat.weapon(128).set(damage=65535); const acts = dat.end_actions();`
    출처: UERE SetWeaponsDat(Condition, …), M2 SetUnitsDat2X(tesPatchT, …) (S5 A.3)
    """
    lst = f_begin_actions()
    try:
        if fn is not None:
            fn(lst)
    except BaseException:
        if _stack and _stack[-1] is lst:
            _stack.pop()
        raise
    return f_end_actions(merge)


def f_begin_actions():
    """이후의 `dat.unit(…)` 등을 새 목록에 모은다(`end_actions` 가 돌려줌). epScript 용.

    인자: 없음
    반환: 그 목록(PatchList)
    비용: 없음
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.begin_actions();`
    출처: 새 작성
    """
    lst = PatchList("actions")
    _stack.append(lst)
    return lst


def f_end_actions(merge=True):
    """`begin_actions` 로 연 목록을 닫고 액션 목록을 돌려준다.

    인자: merge(같은 dword SetTo 합치기)
    반환: list[Action]
    비용: 없음(낼 때 64액션당 1)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `const acts = dat.end_actions();`
    출처: 새 작성
    """
    if not _stack:
        fail("end_actions: begin_actions 가 없습니다")
    return _stack.pop().actions(merge)


def f_emit(actions_, preserved=True, chunk=CHUNK):
    """액션 목록을 그 자리에 chunk(기본 64)개씩 조건 없는 트리거로 낸다.

    인자: actions_(액션 목록 또는 PatchList), preserved(False 면 한 번만 실행), chunk(1~64)
    반환: 낸 트리거 수
    비용: 호출 자리 ceil(N/chunk) 트리거, 실행 같은 수 (변수 필드가 있는 묶음은 eudplib Trigger 가 패치를 더함)
    CP: 넣은 액션에 따름
    로컬: 넣은 액션에 따름
    epScript: `dat.emit(acts);`
    출처: CtrigAsm InitCtrig(64개씩), eudplib Trigger
    """
    if isinstance(actions_, PatchList):
        actions_ = actions_.actions()
    if isinstance(chunk, bool) or not isinstance(chunk, int) or not 1 <= chunk <= 64:
        fail("emit: chunk 는 1 ~ 64 정수여야 합니다 (%r)", chunk)
    acts = FlattenList(list(actions_))
    n = 0
    for i in range(0, len(acts), chunk):
        part = acts[i:i + chunk]
        if _parts.all_const(part):
            RawTrigger(actions=part, preserved=preserved)
        else:
            Trigger(actions=part, preserved=preserved)
        n += 1
    return n


def f_values(*args):
    """epScript 에서 묶음 값(튜플)을 넘길 때 쓴다(리스트 리터럴은 EUDArray 로 번역되므로).

    인자: 값 …
    반환: tuple
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `dat.tep.SetUnitsDatX(162, AdvFlag=dat.values(0x400200, 0x480200));`
    출처: 새로 작성 (DESIGN 3.11)
    """
    return tuple(args)


def f_clear():
    """시작·매 프레임 목록을 모두 비운다(시험·재빌드용).

    인자: 없음
    반환: None
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `dat.clear();`
    출처: 새 작성
    """
    START.clear()
    EVERY_FRAME.clear()


def f_set_debug(on=True):
    """같은 칸을 두 번 선언할 때 컴파일 경고를 낼지 정한다(기본 끔, S5 A.7).

    인자: on(bool)
    반환: None
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `dat.set_debug(true);`
    출처: S5 A.7
    """
    global DEBUG
    DEBUG = bool(on)


def f_addr(table, name, index):
    """필드 칸의 주소를 돌려준다.

    인자: table, name, index(상수 또는 변수)
    반환: 상수 번호 → (4바이트 경계 주소, 시프트 비트 수, 시프트한 마스크) / 변수 번호 → (epd, subp)
    비용: 상수 0 / 변수 = 곱셈·나눗셈 트리거(scdata 멤버는 scdata 캐시)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const a = dat.addr("weapons", "damage", 127);`
    출처: S5 A.7, eudplib scdata member.py:143
    """
    dat = _dat_key(table)
    f = _lookup(dat, name)
    idx = _encode_index(dat, index, allow_var=True)
    if isinstance(idx, int):
        _check_index(f, idx)
        return f.location(idx)
    return _field_epd_subp(f, idx)


# =============================================================================================
# 즉시 쓰기 (now) · 되돌리는 패치 (temporary)
# =============================================================================================


def _field_epd_subp(field_, index):
    if isinstance(index, int):
        a, shift, _m = field_.location(index)
        return ep.EPD(a), shift // 8
    if field_.member is not None:
        return _compat.scdata_epd_subp(field_.member, _DAT_CLASS[field_.dat].cast(index))
    base0 = field_.base - field_.first * field_.stride
    epd0 = ep.EPD(base0 & ~3)
    if field_.stride % 4 == 0:
        k = field_.stride // 4
        return (index if k == 1 else index * k) + epd0, base0 & 3
    tmp = (index if field_.stride == 1 else index * field_.stride) + (base0 & 3)
    return (tmp >> 2) + epd0, tmp & 3


def _possible_subps(field_):
    return sorted({(field_.base + k * field_.stride) & 3 for k in range(min(field_.count, 4))})


def _for_each_subp(field_, subp, body):
    if isinstance(subp, int):
        body(subp)
        return
    for s in _possible_subps(field_):
        if EUDIf()(subp.Exactly(s)):
            body(s)
        EUDEndIf()


def _patch_dword(epd, s, value, mask_rel, bit):
    """epd 칸의 (mask_rel << 8s) 부분을 value 로 바꾼 dword 를 f_dwpatch_epd 로 쓴다."""
    sh = 8 * s
    m = (mask_rel << sh) & M32
    value = unProxy(value)
    if isinstance(value, int):
        put = (((mask_rel if value else 0) if bit else value) << sh) & m
    elif bit:
        put = EUDVariable()
        put << 0
        if EUDIfNot()(value.Exactly(0)):
            put << m
        EUDEndIf()
    else:
        sv = f_bitlshift(value, sh) if sh else value
        put = sv if m == M32 else _parts.and_const(sv, m)
    if m == M32:
        _compat.dwpatch_epd(epd, put)
        return
    cur = f_dwread_epd(epd)
    new = _parts.and_const(cur, ~m & M32)
    if not (isinstance(put, int) and put == 0):
        new = new | put
    _compat.dwpatch_epd(epd, new)


class _Now:
    """그 자리에서 실행하는 쓰기(모듈 객체 `dat.now`). 번호·값이 변수여도 된다. `temporary()` 안에서는 되돌릴 수 있게 쓴다.

    인자: 없음 (`dat.now.unit(u)` 처럼 행을 고른다)
    반환: -
    비용: 상수 = SetMemoryX 1액션(한 set 호출은 한 트리거) / 변수 번호 = scdata 쓰기(간격 4 가 아니면 scdata 곱셈 캐시) / temporary = 필드당 dword 읽기 + f_dwpatch_epd (docs 비용 표)
    CP: 바꾸지 않음
    로컬: 공유(게임 상태)
    epScript: `dat.now.weapon(w).set(damage=v);`
    출처: S5 A.7 (변수 번호·값 → scdata 멤버 쓰기)
    """

    def __init__(self):
        self._buf = []
        self._depth = 0

    # --- 행 ---
    def unit(self, index):
        """그 자리에서 쓰는 유닛 행 (temporary 안이면 되돌릴 수 있게).

        인자: index(0~227 또는 이름 문자열 — 상수 또는 변수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 상수 번호·값 = SetMemoryX 1액션(한 set 호출의 상수 쓰기는 한 트리거에 모음) / 변수 = scdata 쓰기(docs 비용 표) / temporary = 필드당 읽기·f_dwpatch_epd
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.now.unit(u).set(armor=1);`
        출처: TPL SetUnitsDatX, eudplib scdata 쓰기
        """
        return DatRow(self, "units", index)

    def weapon(self, index):
        """그 자리에서 쓰는 무기 행 (temporary 안이면 되돌릴 수 있게).

        인자: index(0~129 또는 이름 — 상수 또는 변수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 상수 번호·값 = SetMemoryX 1액션(한 set 호출의 상수 쓰기는 한 트리거에 모음) / 변수 = scdata 쓰기(docs 비용 표) / temporary = 필드당 읽기·f_dwpatch_epd
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.now.weapon(w).set(damage=10);`
        출처: TPL SetWeaponsDatX, eudplib scdata 쓰기
        """
        return DatRow(self, "weapons", index)

    def flingy(self, index):
        """그 자리에서 쓰는 flingy 행 (temporary 안이면 되돌릴 수 있게).

        인자: index(0~208 — 상수 또는 변수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 상수 번호·값 = SetMemoryX 1액션(한 set 호출의 상수 쓰기는 한 트리거에 모음) / 변수 = scdata 쓰기(docs 비용 표) / temporary = 필드당 읽기·f_dwpatch_epd
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.now.flingy(106).set(topSpeed=8000);`
        출처: theSeed SetFlingyDatX, eudplib scdata 쓰기
        """
        return DatRow(self, "flingy", index)

    def upgrade(self, index):
        """그 자리에서 쓰는 업그레이드 행 (temporary 안이면 되돌릴 수 있게).

        인자: index(0~60 — 상수 또는 변수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 상수 번호·값 = SetMemoryX 1액션(한 set 호출의 상수 쓰기는 한 트리거에 모음) / 변수 = scdata 쓰기(docs 비용 표) / temporary = 필드당 읽기·f_dwpatch_epd
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.now.upgrade(u).set(maxLevel=250);`
        출처: theSeed SetUpgradesDatX, eudplib scdata 쓰기
        """
        return DatRow(self, "upgrades", index)

    def tech(self, index):
        """그 자리에서 쓰는 테크 행 (temporary 안이면 되돌릴 수 있게).

        인자: index(0~43 — 상수 또는 변수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 상수 번호·값 = SetMemoryX 1액션(한 set 호출의 상수 쓰기는 한 트리거에 모음) / 변수 = scdata 쓰기(docs 비용 표) / temporary = 필드당 읽기·f_dwpatch_epd
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.now.tech(14).set(energyCost=0);`
        출처: eudplib scdata Tech, eudplib scdata 쓰기
        """
        return DatRow(self, "techdata", index)

    def sprite(self, index):
        """그 자리에서 쓰는 스프라이트 행 (temporary 안이면 되돌릴 수 있게).

        인자: index(0~516 — 상수 또는 변수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 상수 번호·값 = SetMemoryX 1액션(한 set 호출의 상수 쓰기는 한 트리거에 모음) / 변수 = scdata 쓰기(docs 비용 표) / temporary = 필드당 읽기·f_dwpatch_epd
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.now.sprite(5).set(image=10);`
        출처: theSeed SetSpritesDatX, eudplib scdata 쓰기
        """
        return DatRow(self, "sprites", index)

    def image(self, index):
        """그 자리에서 쓰는 이미지 행 (temporary 안이면 되돌릴 수 있게).

        인자: index(0~998 — 상수 또는 변수)
        반환: DatRow (`.set`, `.flags`, `.mask`, 무기는 `.splash`)
        비용: 상수 번호·값 = SetMemoryX 1액션(한 set 호출의 상수 쓰기는 한 트리거에 모음) / 변수 = scdata 쓰기(docs 비용 표) / temporary = 필드당 읽기·f_dwpatch_epd
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.now.image(944).set(iscript=70);`
        출처: theSeed SetImageDatX, eudplib scdata 쓰기
        """
        return DatRow(self, "images", index)

    def row(self, table, index):
        """아무 표의 즉시 쓰기 행.

        인자: table(표 이름·별칭), index(상수·변수)
        반환: DatRow
        비용: `now` 와 같음
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.now.row("units", u).set(armor=v);`
        출처: 새로 작성
        """
        return DatRow(self, _dat_key(table), index)

    def player_unit_enable(self, unit_, players, value=1):
        """플레이어별 생산 가능 값을 지금 쓴다. unit_·players(하나)·value 가 변수여도 된다.

        인자: unit_(번호·이름·변수), players(0~11 상수·목록 또는 변수 하나), value(0/1 또는 변수)
        반환: now
        비용: 상수 = 액션 1 / 변수 = 곱셈·덧셈 + f_bwrite_epd
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.now.player_unit_enable(u, players=p, value=1);`
        출처: CtrigAsm SetUnitAvailable
        """
        f = _FIELDS["players"]["unitAvailability"]
        u = _encode_index("units", unit_, allow_var=True)
        v = unProxy(value)
        if not _compat.is_var(v):
            v = _enable_value(v)
        p = unProxy(players)
        ps = [p] if _compat.is_var(p) else _players_of(p)
        self._begin()
        try:
            for pl in ps:
                self._set(f, pl * _tb.UNIT_COUNT + u, v)  # 변수면 곱셈·덧셈 트리거
        finally:
            self._end()
        return self

    def damage_ratio(self, damage_type, size, value):
        """피해 배율 칸을 지금 쓴다(번호는 상수, 값은 변수 가능). 주소 인게임 확인 전 — 경고.

        인자: damage_type(0~4), size(0~4), value(상수·변수)
        반환: now
        비용: 상수 = 액션 1 / 변수 = f_dwwrite_epd
        CP: 바꾸지 않음
        로컬: 공유(전역 표)
        epScript: `dat.now.damage_ratio(0, 1, v);`
        출처: CtrigAsm SetDamageMultiplier
        """
        f = _FIELDS["damage"]["ratio"]
        self._begin()
        try:
            self._set(f, _damage_index(damage_type, size), value)
        finally:
            self._end()
        return self

    # --- 목록 프로토콜 ---
    def _index(self, dat, index):
        return _encode_index(dat, index, allow_var=True)

    def _begin(self):
        self._depth += 1

    def _end(self):
        self._depth -= 1
        if self._depth == 0:
            self._flush()

    def _flush(self):
        if self._buf:
            acts, self._buf = self._buf, []
            f_emit([_to_action(w) for w in _merge(acts)], preserved=True)

    def _set(self, field_, index, value):
        _check_index(field_, index)
        _warn_field(field_)
        v = _const_value(field_, value)
        if v is not None:
            v = _check_value(field_, v, "%s.%s" % (field_.dat, field_.name))
        elif not _compat.is_var(unProxy(value)):
            fail("%s.%s: 값 %r 을(를) 쓸 수 없습니다", field_.dat, field_.name, value)
        if _temp.depth:
            self._flush()
            self._patch(field_, index, value if v is None else v, None)
            return
        if isinstance(index, int) and v is not None:
            a, shift, mask = field_.location(index)
            put = (field_.bit if v else 0) if field_.bit is not None else v
            self._buf.append((a, "SetTo", (put << shift) & mask, mask))
            return
        self._flush()
        val = value if v is None else v
        if field_.member is not None:
            setattr(_DAT_CLASS[field_.dat].cast(index), field_.name, val)
            return
        epd, subp = _field_epd_subp(field_, index)
        if field_.size == 1:
            f_bwrite_epd(epd, subp, val)
        elif field_.size == 2:
            f_wwrite_epd(epd, subp, val)
        else:
            f_dwwrite_epd(epd, val)

    def _set_masked(self, field_, index, value, mask):
        _check_index(field_, index)
        _warn_field(field_)
        if _temp.depth:
            self._flush()
            self._patch(field_, index, value, mask)
            return
        if isinstance(index, int) and isinstance(value, int):
            a, shift, _m = field_.location(index, full=True)
            self._buf.append((a, "SetTo", ((value & mask) << shift) & M32, (mask << shift) & M32))
            return
        self._flush()
        epd, subp = _field_epd_subp(field_, index)

        def body(s):
            sh = 8 * s
            m = (mask << sh) & M32
            if isinstance(value, int):
                f_maskwrite_epd(epd, ((value & mask) << sh) & M32, m)
            else:
                f_maskwrite_epd(epd, f_bitlshift(value, sh) if sh else value, m)

        _for_each_subp(field_, subp, body)

    def _patch(self, field_, index, value, mask):
        bit = mask is None and field_.bit is not None
        if mask is None:
            mask = field_.bit if bit else field_.full_mask
        epd, subp = _field_epd_subp(field_, index)
        _for_each_subp(field_, subp, lambda s: _patch_dword(epd, s, value, mask, bit))

    def __repr__(self):
        return "dat.now"


now = _Now()


class _Temp:
    depth = 0


_temp = _Temp()


def f_begin_temporary():
    """이후의 `dat.now` 쓰기를 되돌릴 수 있게(f_dwpatch_epd) 한다. `end_temporary` 로 닫는다. 겹쳐 열 수 없다.

    인자: 없음
    반환: `now`
    비용: 없음(표시만)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.begin_temporary(); dat.now.weapon(w).set(damage=v); dat.end_temporary();`
    출처: eudplib f_dwpatch_epd / f_unpatchall (S5 A.7)
    """
    if _temp.depth:
        fail("dat.temporary 는 겹쳐 열 수 없습니다")
    now._flush()
    _temp.depth = 1
    return now


def f_end_temporary(restore=True):
    """`begin_temporary` 를 닫는다. restore=True 면 그 자리에서 `f_unpatchall` 로 **모든** 패치를 되돌린다.

    인자: restore(False 면 되돌리지 않음 — 나중에 `dat.unpatch_all()`)
    반환: None
    비용: restore 면 f_unpatchall 호출(패치 수에 비례해 실행)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.end_temporary();`
    출처: eudplib f_unpatchall
    """
    if not _temp.depth:
        fail("end_temporary: begin_temporary 가 없습니다")
    _temp.depth = 0
    if restore:
        _compat.unpatch_all()


@contextlib.contextmanager
def temporary(restore=True):
    """블록 안의 `dat.now` 쓰기를 블록 끝에서 되돌린다(dword 단위 f_dwpatch_epd … f_unpatchall).

    - 폭 1·2 필드는 "지금 dword 읽기 → 바꿀 부분만 합치기 → f_dwpatch_epd" 로 쓴다. 되돌릴 때 dword 통째로 돌아가므로
      블록 사이에 같은 dword 의 다른 칸을 바꾼 것도 되돌려진다.
    - `f_unpatchall` 은 eudplib 패치 스택 전체(8192칸, 다른 코드가 넣은 것 포함)를 되돌린다.
    - 같은 프레임 안에서 쓰는 용도(eudplib 관례). 프레임을 넘기려면 restore=False 로 열고 시점을 정해 `dat.unpatch_all()`.
    인자: restore(bool)
    반환: 컨텍스트 관리자 (as 로 `now` 를 받음)
    비용: 필드당 dword 읽기 1 + f_dwpatch_epd 1 (폭 4 는 읽기 없음), 끝에 f_unpatchall
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `with` 가 없다 → `dat.begin_temporary(); … dat.end_temporary();`
    출처: S5 A.7
    """
    f_begin_temporary()
    ok = False
    try:
        yield now
        ok = True
    finally:
        if ok:
            f_end_temporary(restore)
        else:
            _temp.depth = 0


def f_unpatch_all():
    """eudplib 패치 스택(f_dwpatch_epd 등)을 모두 되돌린다(`f_unpatchall`).

    인자: 없음
    반환: None
    비용: f_unpatchall 호출(패치 수에 비례해 실행)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.unpatch_all();`
    출처: eudplib mempatch.py:113
    """
    _compat.unpatch_all()


# =============================================================================================
# EUD Editor 목록 읽기
# =============================================================================================

_NUM = r"-?\s*(?:0[xX][0-9A-Fa-f]+|\d+)"
_LUA_ENTRY = re.compile(r"\{\s*(" + _NUM + r")\s*,\s*(" + _NUM + r")\s*\}")
_PY_ENTRY = re.compile(r"SetMemory\(\s*(" + _NUM + r")\s*,\s*(SetTo|Add|Subtract)\s*,\s*(" + _NUM + r")\s*\)")
_LUA_BLOCK_COMMENT = re.compile(r"--\[(=*)\[.*?\]\1\]", re.S)
_LUA_LINE_COMMENT = re.compile(r"--[^\n]*")


def _num(s):
    return int(s.replace(" ", ""), 0)


def _lua_table_body(text, table):
    m = re.search(r"(?<![\w.])" + re.escape(table) + r"\s*=\s*\{", text)
    if m is None:
        return None
    depth = 0
    for i in range(m.end() - 1, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[m.end():i]
    fail("from_eud_editor: 표 %s 의 닫는 괄호가 없습니다", table)
    return None


def f_parse_eud_editor(source, table="EUDEditorDatActs"):
    """EUD Editor dat 편집분을 [(주소, "Add"|"SetTo"|"Subtract", 값)] 로 읽는다(트리거 없음).

    인자: source(Lua 파일·DataEditor.py·목록), table(Lua 표 이름)
    반환: list
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: MSF_Memory_2 EUDEditorDat.lua 형식, EUD Editor 3 DataEditor.py 형식 (S5 A.6)
    """
    out = []
    if not isinstance(source, (str, bytes, os.PathLike)):
        for item in source:
            item = tuple(item)
            if len(item) == 2:
                a, mod, v = item[0], "Add", item[1]
            elif len(item) == 3:
                a, mod, v = item
            else:
                fail("from_eud_editor: 항목은 (주소, 값) 또는 (주소, 수정자, 값) 이어야 합니다 (%r)", item)
            out.append((a, mod, v))
    else:
        path = os.fspath(source)
        if isinstance(path, bytes):
            path = path.decode()
        if not os.path.isfile(path):
            fail("from_eud_editor: 파일이 없습니다: %s", path)
        with open(path, encoding="utf-8-sig", errors="replace") as fp:
            text = fp.read()
        if path.lower().endswith(".py"):
            text = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
            for a, mod, v in _PY_ENTRY.findall(text):
                out.append((_num(a), mod, _num(v)))
        else:
            text = _LUA_LINE_COMMENT.sub("", _LUA_BLOCK_COMMENT.sub("", text))
            body = _lua_table_body(text, table)
            if body is None:
                fail("from_eud_editor: %s 에 표 %s 가 없습니다", path, table)
            for a, v in _LUA_ENTRY.findall(body):
                out.append((_num(a), "Add", _num(v)))
    for a, mod, v in out:
        if isinstance(a, bool) or not isinstance(a, int) or a & 3 or not 0 <= a <= M32:
            fail("from_eud_editor: 주소 %r 은(는) 4의 배수 정수여야 합니다", a)
        if mod not in _MOD_OBJ:
            fail("from_eud_editor: 수정자 %r (SetTo/Add/Subtract 만)", mod)
        # EUD Editor 차분은 (새 값 − 원래 값)·256^바이트위치 라 최상위 바이트가 줄면 −2³¹ 보다 작다(M2 실측). 덧셈은 2³² 로 돈다.
        if isinstance(v, bool) or not isinstance(v, int) or not -(1 << 32) < v <= M32:
            fail("from_eud_editor: 값 %r 이(가) ±2³² 밖입니다", v)
    return out


parse_eud_editor = f_parse_eud_editor


# =============================================================================================
# TEP 이식 층
# =============================================================================================


class Tep:
    """TEP(CtrigAsm 템플릿) 헬퍼를 키 이름·변환 그대로 옮긴 층 (이식용). 새 코드는 scdata 이름 API 를 쓴다.

    - 대상 목록: 기본은 현재 목록(시작 1회, `actions()` 안이면 그 목록). `target=` 으로 바꿀 수 있다.
    - 변환: HP×256, SuppCost×2, Shield/Splash bool·표, Playerable bool/2(사람만 = `humans`, 기본 TPL 판 P1~P5),
      AdvFlag (값, 마스크), theSeed 비트 이름(True 일 때만 켬 — theSeed 와 같음), 값이 필드 폭을 넘으면 TEP 처럼 잘라 쓰고 경고.
    - **D19(권장안, 사용자 확인 대기)**: `WhatSndInit`/`WhatSndEnd` 는 TEP 주소(0x662BF0/0x65FFB0, eudplib·EUD Editor 와
      이름이 반대)를 그대로 쓰고 경고. `Reqptr`(유닛) 는 TPL 처럼 무시하고 경고(`reqptr="once"|"every_frame"` 로 적용).
    - 경고는 키마다 한 번 표시하고 전부 `warnings` 에 모은다. `warn=False` 면 표시하지 않는다.
    인자: 없음 (모듈 객체 `dat.tep` 를 쓴다)
    반환: -
    비용: 키당 액션 1(Shield·Splash·Playerable 은 2~8)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `dat.tep.SetUnitsDatX(162, AdvFlag=dat.values(0x400200, 0x480200), BdDimX=1);`
    출처: TPL reference/MSF-Template/func.lua:27~456, theSeed Engine/func.lua:33~535, DPS DmgType 키
    """

    def __init__(self):
        self.warn = True
        self.humans = (0, 1, 2, 3, 4)
        self.reqptr = "ignore"
        self.warnings = []
        self._warned = set()
        self._wep_persist = set()
        self._wep_build = set()

    # --- 내부 ---
    def _note(self, key, msg):
        self.warnings.append((key, msg))
        if self.warn and key not in self._warned:
            self._warned.add(key)
            warn("dat.tep: %s (같은 경고는 한 번만 표시)", msg)

    def _reset_build(self):
        self._wep_build = set()

    @staticmethod
    def _props(fname, prop, kw):
        if prop is None:
            prop = {}
        if not isinstance(prop, dict):
            fail("%s: Property 는 dict 여야 합니다 (TEP 'Property Inputdata Error', 받은 값 %r)", fname, prop)
        out = dict(prop)
        out.update(kw)
        return out

    @staticmethod
    def _seq(fname, key, k, n):
        v = unProxy(k)
        if isinstance(v, (tuple, list)) and len(v) == n:
            return tuple(v)
        hint = " (epScript 에서는 dat.values(…) 또는 list(…) 로)" if not isinstance(v, (tuple, list, dict)) else ""
        fail("%s: %s 는 값 %d개 묶음이어야 합니다 (TEP '%s Inputdata Error', 받은 값 %r)%s", fname, key, n, key, k, hint)
        return None

    def _put(self, sink, dat, index, name, k, mul=1, width=None, key=None):
        f = _lookup(dat, name)
        if width is not None and (width != f.size or f.bit is not None):
            f = f.widened(width)
        v = unProxy(k)
        if isinstance(v, bool):
            v = int(v)
        if not isinstance(v, int):
            if isinstance(v, str) and f.member is not None:
                v = _const_value(f, v)
            if not isinstance(v, int):
                fail("dat.tep %s: 값은 정수 상수여야 합니다 (받은 값 %r)", key or name, k)
        v *= mul
        lo, hi = _range_of(f)
        if not lo <= v <= hi:
            self._note(("range", key or name), "%s=%d 이(가) %s.%s(%d바이트) 폭을 넘어 TEP 처럼 잘라 씁니다"
                       % (key or name, v, dat, f.name, f.size))
            v &= f.full_mask if f.bit is None else 1
        else:
            v = _check_value(f, v, key or name)
        _check_index(f, index)
        sink._put(f, index, v)

    def _sink(self, target):
        if target is None:
            return _sink()
        if isinstance(target, PatchList):
            return target
        fail("dat.tep: target 은 PatchList(dat.start()·dat.every_frame()·begin_actions() 의 목록)여야 합니다 (%r)", target)
        return None

    # --- units ---
    def SetUnitsDatX(self, UnitID, Property=None, *, reqptr=None, humans=None, target=None, **kw):  # noqa: N802,N803
        """TEP `SetUnitsDatX(UnitID, {키=값})`. 키는 TPL + theSeed 판 전부(`datpatch_tables.TEP_UNITS` 등).

        인자: UnitID(번호·이름), Property(dict), reqptr("ignore"|"once"|"every_frame", 기본 self.reqptr),
              humans(Playerable=2 일 때 1 을 쓸 플레이어, 기본 self.humans = P1~P5), target(목록), **kw(키=값, epScript 용)
        반환: None
        비용: 키당 액션 1 (Shield 1~2, Playerable 8)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.tep.SetUnitsDatX(162, AdvFlag=dat.values(0x400200, 0x480200), BdDimX=1, BdDimY=1);`
        출처: TPL func.lua:98~264, theSeed func.lua:191~390
        """
        props = self._props("SetUnitsDatX", Property, kw)
        sink = self._sink(target)
        u = _encode_index("units", UnitID)
        for key, k in props.items():
            if unProxy(k) is None:
                continue  # Lua nil = 키 없음
            if key == "Shield":
                kk = unProxy(k)
                if isinstance(kk, bool):
                    self._put(sink, "units", u, "hasShield", 1 if kk else 0, width=1, key=key)
                    if not kk:
                        self._put(sink, "units", u, "maxShield", 0, key=key)
                else:
                    self._put(sink, "units", u, "hasShield", 1, width=1, key=key)
                    self._put(sink, "units", u, "maxShield", kk, key=key)
            elif key == "AdvFlag":
                val, msk = self._seq("SetUnitsDatX", key, k, 2)
                val, msk = unProxy(val), unProxy(msk)
                if not all(isinstance(x, int) and not isinstance(x, bool) for x in (val, msk)):
                    fail("SetUnitsDatX: AdvFlag 값·마스크는 정수 상수여야 합니다 (%r)", k)
                sink._set_masked(_FIELDS["units"]["baseProperty"], u, val & M32 & msk, msk & M32)
            elif key in _tb.TEP_ADV_FLAG_BITS:
                m = _tb.TEP_ADV_FLAG_BITS[key]
                kk = unProxy(k)
                if not isinstance(kk, bool):
                    self._note(("advbit", key), "SetUnitsDatX: %s=%r — theSeed 판은 true 일 때만 켜고 그 밖의 값은 끕니다(그대로 따름)"
                               % (key, kk))
                sink._set_masked(_FIELDS["units"]["baseProperty"], u, m if kk is True else 0, m)
            elif key == "Playerable":
                kk = unProxy(k)
                st = (1 if kk else 0) if isinstance(kk, bool) else kk
                if not isinstance(st, int):
                    fail("SetUnitsDatX: Playerable 은 bool 또는 정수여야 합니다 (%r)", k)
                hs = set(_players_of(humans if humans is not None else self.humans))
                for p in range(8):
                    v = (1 if p in hs else 0) if st == 2 else st
                    self._put(sink, "players", p * _tb.UNIT_COUNT + u, "unitAvailability", v, key=key)
            elif key == "Reqptr":
                mode = reqptr if reqptr is not None else self.reqptr
                if mode == "ignore":
                    self._note(("Reqptr",), "SetUnitsDatX: Reqptr 는 TPL 판에서 아무 일도 하지 않아 그대로 무시합니다 "
                                            "(적용하려면 reqptr=\"once\" 또는 \"every_frame\", 새 코드는 requirementOffset)")
                elif mode == "once":
                    self._put(sink, "units", u, "requirementOffset", k, key=key)
                elif mode == "every_frame":
                    self._put(EVERY_FRAME, "units", u, "requirementOffset", k, key=key)
                else:
                    fail("SetUnitsDatX: reqptr 는 \"ignore\"·\"once\"·\"every_frame\" 중 하나 (%r)", mode)
            elif key == "AddonPlacement":
                x, y = self._seq("SetUnitsDatX", key, k, 2)
                self._put(sink, "units", u, "addonPlacementX", x, key=key)
                self._put(sink, "units", u, "addonPlacementY", y, key=key)
            elif key in _tb.TEP_UNITS:
                name, mul, width = _tb.TEP_UNITS[key]
                if key in _tb.TEP_WHATSOUND:
                    self._note(("WhatSnd", key), "SetUnitsDatX: TEP 의 %s 는 %s 칸(0x%X)에 씁니다 — eudplib·EUD Editor 와 "
                                                 "이름이 반대입니다. TEP 동작을 그대로 따릅니다(뜻대로 쓰려면 %s)"
                               % (key, name, _FIELDS["units"][name].base, _tb.TEP_WHATSOUND[key]))
                self._put(sink, "units", u, name, k, mul, width, key)
            else:
                fail("SetUnitsDatX: 모르는 키 %r (TEP 'Wrong Property Name Detected')", key)

    # --- weapons ---
    def SetWeaponsDatX(self, WepID, Property=None, *, target=None, **kw):  # noqa: N802,N803
        """TEP `SetWeaponsDatX(WepID, {키=값})` (TPL + theSeed + DPS `DmgType`).

        인자: WepID(0~129), Property(dict), target, **kw
        반환: None
        비용: 키당 액션 1 (Splash 표는 4)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.tep.SetWeaponsDatX(1, DmgBase=75, Splash=dat.values(7, 14, 21));`
        출처: TPL func.lua:27~96, theSeed func.lua:33~101
        """
        props = self._props("SetWeaponsDatX", Property, kw)
        sink = self._sink(target)
        w = _encode_index("weapons", WepID)
        for key, k in props.items():
            kk = unProxy(k)
            if kk is None:
                continue
            if key == "Splash":
                if isinstance(kk, bool):
                    self._put(sink, "weapons", w, "explosionType", 3 if kk else 1, key=key)
                else:
                    a, b, c = self._seq("SetWeaponsDatX", "Splash", k, 3)
                    self._put(sink, "weapons", w, "explosionType", 3, key=key)
                    self._put(sink, "weapons", w, "splashInnerRadius", a, key=key)
                    self._put(sink, "weapons", w, "splashMiddleRadius", b, key=key)
                    self._put(sink, "weapons", w, "splashOuterRadius", c, key=key)
            elif key in _tb.TEP_WEAPONS:
                name, mul, width = _tb.TEP_WEAPONS[key]
                self._put(sink, "weapons", w, name, k, mul, width, key)
            else:
                fail("SetWeaponsDatX: 모르는 키 %r (TEP 'Wrong Property Name Detected')", key)

    def _simple(self, fname, dat, table, index, Property, kw, target):  # noqa: N803
        props = self._props(fname, Property, kw)
        sink = self._sink(target)
        i = _encode_index(dat, index)
        for key, k in props.items():
            if unProxy(k) is None:
                continue
            if key not in table:
                fail("%s: 모르는 키 %r (TEP 'Wrong Property Name Detected')", fname, key)
            name, mul, width = table[key]
            self._put(sink, dat, i, name, k, mul, width, key)
        return sink, i, props

    def SetUpgradesDatX(self, UpgradeID, Property=None, *, target=None, **kw):  # noqa: N802,N803
        """theSeed `SetUpgradesDatX` (Reqptr·MaxLevel·비용 6종 — 업그레이드 Reqptr 는 theSeed 처럼 실제로 쓴다).

        인자: UpgradeID(0~60), Property(dict), target, **kw
        반환: None
        비용: 키당 액션 1
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.tep.SetUpgradesDatX(7, MaxLevel=250);`
        출처: theSeed func.lua:392~432
        """
        self._simple("SetUpgradesDatX", "upgrades", _tb.TEP_UPGRADES, UpgradeID, Property, kw, target)

    def SetFlingyDatX(self, FlingyID, Property=None, *, target=None, **kw):  # noqa: N802,N803
        """theSeed `SetFlingyDatX` (Speed·Acceleration·HaltDistance·TurnRadius·MovementControl).

        인자: FlingyID(0~208), Property(dict), target, **kw
        반환: None
        비용: 키당 액션 1
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.tep.SetFlingyDatX(1, Speed=100);`
        출처: theSeed func.lua:434~464
        """
        self._simple("SetFlingyDatX", "flingy", _tb.TEP_FLINGY, FlingyID, Property, kw, target)

    def SetSpritesDatX(self, SpriteID, Property=None, *, target=None, **kw):  # noqa: N802,N803
        """theSeed `SetSpritesDatX` (ImageFile, IsVisible — true 일 때만 1, 바이트 통째).

        인자: SpriteID(0~516), Property(dict), target, **kw
        반환: None
        비용: 키당 액션 1
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.tep.SetSpritesDatX(5, IsVisible=true);`
        출처: theSeed func.lua:466~492
        """
        props = self._props("SetSpritesDatX", Property, kw)
        rest = {k: v for k, v in props.items() if k not in _tb.TEP_SPRITE_SPECIAL}
        sink, i, _p = self._simple("SetSpritesDatX", "sprites", _tb.TEP_SPRITES, SpriteID, rest, {}, target)
        if "IsVisible" in props and unProxy(props["IsVisible"]) is not None:
            self._put(sink, "sprites", i, "isVisible", 1 if unProxy(props["IsVisible"]) is True else 0,
                      width=1, key="IsVisible")

    def SetImageDatX(self, ImageID, Property=None, *, target=None, **kw):  # noqa: N802,N803
        """theSeed `SetImageDatX` (GRPFile·IscriptID·비트 4종(바이트 통째)·오버레이 5종 — SC:R 읽기 전용일 수 있음, 경고).

        인자: ImageID(0~998), Property(dict), target, **kw
        반환: None
        비용: 키당 액션 1
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.tep.SetImageDatX(944, IscriptID=70);`
        출처: theSeed func.lua:494~535
        """
        self._simple("SetImageDatX", "images", _tb.TEP_IMAGES, ImageID, Property, kw, target)

    def SetDamageRatio(self, DamageType, ArmorType, Value, *, target=None):  # noqa: N802,N803
        """theSeed `SetDamageRatio(피해형, 아머형, 값)` — 0x515B88 + 0x14·피해형 + 4·아머형 (주소 인게임 확인 전, 경고).

        인자: DamageType(0~4), ArmorType(0~4), Value(0 ~ 0x7FFFFFFF, 256 = 1배)
        반환: None
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유(전역 표)
        epScript: `dat.tep.SetDamageRatio(0, 0, 768);`
        출처: theSeed func.lua:145~176
        """
        v = unProxy(Value)
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 0x7FFFFFFF:
            fail("SetDamageRatio: Value 는 0 ~ 0x7FFFFFFF 정수여야 합니다 (256 = 1.0배, 받은 값 %r)", Value)
        self._sink(target).damage_ratio(DamageType, ArmorType, v)

    def PatchInsert(self, *actions_, target=None):  # noqa: N802
        """TEP `PatchInsert(액션)` — 현재 목록(시작 1회)에 원시 액션.

        인자: 액션 …, target
        반환: None
        비용: 액션 수만큼
        CP: 넣은 액션에 따름
        로컬: 넣은 액션에 따름
        epScript: `dat.tep.PatchInsert(SetMemory(0x58A364, SetTo, 1));`
        출처: TPL func.lua:32
        """
        self._sink(target).raw(*actions_)

    def PatchInsertPrsv(self, *actions_):  # noqa: N802
        """theSeed `PatchInsertPrsv(액션)` — 매 프레임 목록에 원시 액션.

        인자: 액션 …
        반환: None
        비용: 매 프레임 액션 수만큼
        CP: 넣은 액션에 따름
        로컬: 넣은 액션에 따름
        epScript: `dat.tep.PatchInsertPrsv(SetMemory(0x58A364, SetTo, 1));`
        출처: theSeed func.lua:10
        """
        EVERY_FRAME.raw(*actions_)

    def SetUnitAbility(self, UnitID, WepID=None, DmgType=None, AIFlag=None, HP=None, Shield=None, Size=None,  # noqa: N802,N803
                       Cooldown=None, Damage=None, DFactor=None, Splash=None, ObjNum=None, RangeMax=None,
                       SeekRange=None, Point=None, Text=None, KillPoint=None, UpgradeType=None, *,
                       ArmorDefType=None, variant="tpl", inscribed_damage_type=0, target=None):
        """TEP `SetUnitAbility`(TPL 18인자 판)의 **dat 부분**. 이름 문자열·점수 표(InputStrArr, UnitPointArr,
        KillPointArr, SizeChangeFlag)는 만들지 않고 결과 dict 로 돌려준다.

        인자: TPL 순서 18개(UnitID, WepID, DmgType, AIFlag, HP, Shield, Size(L,U,R,D), Cooldown, Damage, DFactor, Splash,
              ObjNum, RangeMax, SeekRange, Point, Text, KillPoint, UpgradeType),
              variant("tpl" | "seed" — theSeed 판: 무기 중복 예외 70, DmgType 5 = inscribed_damage_type, 83번 예외 없음,
              ArmorDefType 사용), target
        반환: dict(unit, weapon, color, name, name_hex, point, big_kill_point)
        비용: 유닛 키 최대 16 + 무기 키 최대 12 액션 (서브유닛 있는 유닛은 +2)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `dat.tep.SetUnitAbility(21, 18, 3, 17000, false, 30, 450, false, 1, 160, 5, 45000, "Kazansky", 2000);`
        출처: TPL func.lua:316~456, theSeed func.lua:795~950
        """
        if variant not in ("tpl", "seed"):
            fail("SetUnitAbility: variant 는 \"tpl\" 또는 \"seed\" (%r)", variant)
        seed = variant == "seed"
        uid = _encode_index("units", UnitID)
        wid = None if unProxy(WepID) is None else _encode_index("weapons", WepID)
        temp_wid, temp_wid2 = wid, 130
        lclass, group_flag = 94, 0xA
        if Shield is None:
            Shield = False
        free_wep = 70 if seed else 71
        if wid is not None and wid != free_wep:
            used = self._wep_persist | self._wep_build
            if wid in used:
                fail("SetUnitAbility: WepID Duplicated : %d", wid)
            (self._wep_persist if _compat.onstart_phase() == 0 else self._wep_build).add(wid)
        dt = unProxy(DmgType)
        if dt is True:
            color, lclass, group_flag, dt = 0x04, 94, 0xA, None
        elif dt is None:
            color, lclass, group_flag = 0x04, None, None
        elif dt in _tb.ABILITY_COLOR and not isinstance(dt, bool):
            color = _tb.ABILITY_COLOR[dt]
        elif dt == 5 and not isinstance(dt, bool):
            color, lclass = (0x10, 94) if seed else (0x08, 95)
        else:
            fail("SetUnitAbility: Unit DamageType Error (%r)", DmgType)
        text = "" if Text is None else str(Text)
        words = text.split()
        name = "".join("<08>%s<04>%s " % (w[:1], w[1:]) for w in words)
        name_hex = "".join("<%x>%s<04>%s " % (color, w[:1], w[1:]) for w in words)
        if uid in _tb.ABILITY_AIR_SAME:
            temp_wid2 = wid
        if uid in _tb.ABILITY_SUBUNIT_OWNERS:
            temp_wid = 130
            self.SetUnitsDatX(uid + 1, {"GroundWeapon": wid, "AirWeapon": temp_wid2}, target=target)
        size = (None, None, None, None) if Size is None else tuple(self._seq("SetUnitAbility", "Size", Size, 4))
        big_kill = None
        kp = unProxy(KillPoint)
        if kp is not None and kp >= 65536:
            big_kill, kp = kp, 0
        adv_hero = 0x40 if unProxy(AIFlag) == 3 else 0
        if uid == 83 and not seed:
            temp_wid, temp_wid2 = 130, 130
        props = {
            "Class": lclass, "GroupFlag": group_flag, "AdvFlag": (adv_hero, 0x40 + 0x8000 + 0x80),
            "StarEditFlag": 0x1C7, "ComputerAI": AIFlag, "HP": HP, "Shield": Shield,
            "GroundWeapon": temp_wid, "AirWeapon": temp_wid2, "SeekRange": SeekRange, "KillScore": kp,
            "SizeL": size[0], "SizeU": size[1], "SizeR": size[2], "SizeD": size[3],
        }
        if seed:
            props["DefType"] = ArmorDefType
        elif ArmorDefType is not None:
            fail("SetUnitAbility: ArmorDefType 은 variant=\"seed\" 에서만 받습니다")
        self.SetUnitsDatX(uid, props, target=target)
        obj = 1 if ObjNum is None else ObjNum
        if dt == 5:
            dt = inscribed_damage_type if seed else 3
        if wid is not None:
            self.SetWeaponsDatX(wid, {
                "TargetFlag": 11, "DamageType": dt, "Cooldown": Cooldown, "DmgBase": Damage, "RangeMax": RangeMax,
                "ObjectNum": obj, "Splash": Splash, "DmgFactor": DFactor, "UpgradeType": UpgradeType,
            }, target=target)
        return {"unit": uid, "weapon": wid, "color": color, "name": name, "name_hex": name_hex,
                "point": Point, "big_kill_point": big_kill}


tep = Tep()


# =============================================================================================
# 파이썬 별칭 (DESIGN 3.1) · 빌드 상태
# =============================================================================================

unit = f_unit
weapon = f_weapon
flingy = f_flingy
upgrade = f_upgrade
tech = f_tech
sprite = f_sprite
image = f_image
player_unit_enable = f_player_unit_enable
all_unit_size = f_all_unit_size
damage_ratio = f_damage_ratio
raw = f_raw
from_eud_editor = f_from_eud_editor
start = f_start
every_frame = f_every_frame
actions = f_actions
begin_actions = f_begin_actions
end_actions = f_end_actions
emit = f_emit
values = f_values
clear = f_clear
set_debug = f_set_debug
addr = f_addr
begin_temporary = f_begin_temporary
end_temporary = f_end_temporary
unpatch_all = f_unpatch_all


@_compat.register_build_reset
def _reset_build():
    START._reset_build()
    EVERY_FRAME._reset_build()
    tep._reset_build()
    del _stack[:]
    now._buf = []
    now._depth = 0
    _temp.depth = 0
