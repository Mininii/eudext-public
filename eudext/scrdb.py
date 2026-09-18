"""SCR_DB 네이티브 코어 — 오프라인 세이브 런처(레이아웃 7)와 맞물리는 맵 쪽 부품 (DESIGN 4.18).

CtrigAsm 판(`MapSource/Library/SCR_DB_Core.lua`)과 **같은 런처 규약**을 eudplib 코드로 낸다. 런처와의 약속 값
(표지 블록 칸 번호·시그니처·MSQC 워드 비트·헤더 구성·알림음)은 파이썬에 다시 적지 않고 빌드 때
`tools/lua_consts` 가 lupa 로 Lua 코어를 읽어 가져온다(단일 출처, 4.18 (a)).

    from eudext import scrdb
    db = scrdb.setup([scrdb.arr("Gold", 0), scrdb.arr("Level", 1), scrdb.var("Stat", 0)], "MyMap",
                     anchor=0x594198, xfer_base=0x58F678, xfer_stride=16, slot_base=0x58F778, slot_stride=4,
                     qc_unit=49, manifest="auto")
    def beforeTriggerExec():            # [MSQC] 플러그인 뒤 (수신과 같은 사이클)
        db.frame()                      # 표지 블록(1회 블록 → 로컬 플레이어 → Seq) → 수신기 → 알림음
        for p in range(db.humans):
            if EUDIf()(db.launcher_ready(p)): ...; DoActions(db.clear_ready(p))
            if EUDIf()(저장 조건): DoActions(db.save_signal(p))
            if EUDIf()(db.save_done(p)): ...; DoActions(db.clear_save_done(p))

epScript:

    import eudext.scrdb as scrdb;
    const db = scrdb.setup(list(scrdb.arr("Gold", 0), scrdb.slot("Stat", 0)), "MyMap", anchor=0x594198, …);
    function beforeTriggerExec() { db.frame(); if (db.launcher_ready(0)) { … } }

**빌드**(sync 와 같은 3단계, DESIGN 5.3): ① `sync.collect(맵 소스)` — `setup` 이 만든 MSQC 버스(채널 8줄)가 모인다
② `tools/edsgen.EdsDoc`: `boot(venv_site=…)` → `add_sync()` → `add_scrdb()`(부트 Preload 에 scrdb, 훅 플러그인
`eudext_scrdb_hook.py` — 설정 Core·BuildId·Manifest·Frame) → 맵 플러그인 ③ euddraft. 훅이 있으면 훅이
`[MSQC]` 바로 뒤에서 `frame()` 을 내므로 맵은 `db.frame()` 을 부르지 않아도 된다(불러도 아무것도 내지 않는다).
훅 없이 eds 를 손으로 쓸 때는 부트에 `VenvSite`·`Preload : scrdb` 를 넣고 `[MSQC]` 줄은 `sync` 선언과 같게 쓴다
(빌드 안에서 `sync.verify()` 가 확인한다). 예: `examples/scrdb_ingame.{eps,eds}`.

**핵심 제약**(4.18)
- (a) 약속 값은 Lua 에서: `db.core`(ScrdbCore). `layout=` 은 확인용(다르면 오류).
- (b) FieldHash·id·매니페스트는 Lua `SCRDB_Setup`/`SCRDB_WriteManifest` 결과를 쓰고, 이 모듈의 파이썬 구현
  (`field_hash`, `assign_ids`, `json_bytes`, `manifest_doc`)과 **빌드마다 바이트 단위로 대조**한다(다르면 오류).
- (c) 시그니처 8 dword 는 SetMemory 액션 8개로만 쓴다(Lua 계획 그대로 — 페이로드에 연속으로 나타나지 않는다).
- (d) MSQC 채널 줄은 `sync` 형식(`sync.scrdb_msqc_lines()` 와 같은 식)으로 버스에 넣는다. eudplib `IsPName`
  (라이트 변수 경로)이 채널·표지 블록·데스 칸과 겹치면 빌드 오류(3.9) — `receiver()` 때와 빌드 끝에 검사.
- (e) `receiver()` 는 같은 빌드에서 `anchor()` 가 먼저 나오게 한다(없으면 먼저 낸다). 맵 플러그인은 `[MSQC]` 뒤.
  `frame()` 은 beforeTriggerExec **최상위**(매 사이클 무조건 도는 자리)에서 부른다.
- (f) 로컬 칸: LocalPlayer 는 `Memory(0x512684) == i` 조건 트리거 8개, Notify 는 알림 칸 조건 트리거 —
  둘 다 표지 블록 칸·CP·PlayWAV 만 건드리고 공유 변수를 쓰지 않는다.

**수신기 구조**(비용 목표: 32벌 펼침 → 공유 본문 한 벌 + 읽기 1회)
- 채널 k × 플레이어 i 마다 **트리거 1개**(조건 1·액션 2): `Deaths(i, AtLeast, 1, 데스 유닛)` 이면 자리 번호 n 을 넣고
  자기 next 를 본문 입구로 바꿔 뛰어든다. 받은 워드가 없으면 실행 1.
- 본문(한 벌): 필드 7개 × 자리 수의 표 하나를 CP = EPD(표) + n 에서 정수 오프셋으로 읽고 쓴다 — 호출 트리거 next 되돌리기·
  돌아갈 곳(표 → 액션 칸·next 칸에 바로 읽기), 데스 칸 EPD, Count/Echo 칸 번호, 칸 상태(토글·하위 받음 비트), 키·하위 값
  (마스크 SetTo 로 페이로드만 남김). 워드는 `f_maskread_epd` 1회. 토글 두 if 는 else 가 아니고, 상위 워드 뒤에도 하위 받음
  비트를 내리지 않는다(Lua 와 같음). 끝에서 CP 를 캐시로 되돌린다.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import time

from eudplib import (
    EPD,
    Add,
    AtLeast,
    AtMost,
    CurrentPlayer,
    Deaths,
    DoActions,
    EncodePlayer,
    EUDArray,
    EUDEndExecuteOnce,
    EUDEndIf,
    EUDExecuteOnce,
    EUDIf,
    EUDVariable,
    Exactly,
    Forward,
    GetChkTokenized,
    IsEUDVariable,
    Memory,
    MemoryEPD,
    NextTrigger,
    PlayWAVAll,
    RawTrigger,
    SetMemory,
    SetMemoryEPD,
    SetMemoryXEPD,
    SetNextPtr,
    SetTo,
    Subtract,
    SetDeaths,
    SetDeathsX,
    SeqCompute,
    f_dwread_cp,
    f_getcurpl,
    f_maskread_epd,
    f_readgen_epd,
    f_setcurpl2cpcache,
)

from eudext import _compat, _parts, sync
from eudext.errors import EudextError, fail, warn
from eudext.tools import lua_consts as _lc

__all__ = [
    "anchor",
    "close_load",
    "notify",
    "receiver",
    "save_signal",
    "write_manifest",
    "DEATHS_BASE",
    "DEFAULT_ANCHOR",
    "Field",
    "HOOK_NAME",
    "MIRROR_REGION",
    "RECEIVER_DIGEST",
    "ScrDb",
    "arr",
    "assign_ids",
    "check_forbidden",
    "current",
    "declared",
    "deaths",
    "default_manifest_path",
    "field_hash",
    "frame",
    "hook_source",
    "json_bytes",
    "manifest_name",
    "msqc_lines",
    "setup",
    "slot",
    "stash_manifest",
    "var",
    "write_hook",
]

# --- eudext 쪽 사실 (런처 규약 값이 아니다) ------------------------------------------------------
DEATHS_BASE = 0x58A364  # 데스 표 시작 = EPD 0
# 런처가 EUD 주소 + 보정치로 닿는 구역 (DPS tools/scr_db_launcher.py local_player 주석, G8 1.11 A-1)
MIRROR_REGION = (0x57F0E0, 0x59F0E0)
DEFAULT_ANCHOR = 0x594198  # DPS 원본 자리(G8 1.10). 맵이 이 칸들을 쓰지 않을 때만
LOCAL_PLAYER_ADDR = 0x512684
_CP_ADDR = 0x6509B0  # CurrentPlayer (본문이 잠깐 옮기고 캐시로 되돌린다, DESIGN 3.6-3)
HOOK_NAME = "eudext_scrdb_hook.py"
BUILD_ID_ENV = "EUDEXT_SCRDB_BUILD_ID"
MAX_FIELDS = 4096  # 런처 find_anchors 가 받는 FieldCount 상한 (scr_db_launcher.py:645)
# eudext 수신기가 따라간 Lua `SCRDB_Receiver` 기록의 모양 지문 (tools/lua_consts.ScrdbCore.receiver_digest).
# 다르면 Lua 수신기가 바뀐 것이다 → 경고(차등 시험 t_scrdb 의 수신기 절을 다시 돌려 확인한다).
RECEIVER_DIGEST = "d422fc6f558d16050ee4c307aad9d0a26c18ca19d52af01cbd9493b692580d05"
# 트리거 안 액션 0 의 player·value 칸 오프셋 (헤더 8 + 조건 16×20 + 16 / +20)
_ACT0_PLAYER = 8 + 16 * 20 + 16
_ACT0_VALUE = 8 + 16 * 20 + 20

_MODS = {"SetTo": SetTo, "Add": Add, "Subtract": Subtract}
_CMPS = {"Exactly": Exactly, "AtLeast": AtLeast, "AtMost": AtMost}
M32 = 0xFFFFFFFF


def _epd(addr):
    return ((addr - DEATHS_BASE) // 4) & M32


def _lowbit(x):
    return x & -x


# ---------------------------------------------------------------------------------------------
# 저장 항목
# ---------------------------------------------------------------------------------------------


class Field:
    """저장 항목 하나(매니페스트 `fields` 의 원소).

    인자: name(런처가 id 로 쓰는 이름), mode("arr" | "var"), index(arr: XferBase 기준 칸), slot(var: SlotBase 기준 칸),
          extra(매니페스트에 같이 적을 키, 선택)
    값 자리(플레이어 P): arr = XferBase + (P·XferStride + index)·4, var = SlotBase + (P·SlotStride + slot)·4
    반환: -
    비용: 없음(선언)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `scrdb.arr("Gold", 0)`, `scrdb.slot("Stat", 3)`(epScript 는 `var` 가 예약어), `scrdb.deaths("Level", 18)`
    출처: SCR_DB_Core.lua SCRDB_Setup 의 Cfg.Fields 설명
    """

    __slots__ = ("deaths_unit", "extra", "index", "mode", "name", "slot")

    def __init__(self, name, mode, index=None, slot=None, deaths_unit=None, **extra):
        if mode not in ("arr", "var"):
            fail("scrdb 항목 %r: mode 는 'arr' 또는 'var' (%r)", name, mode)
        for label, v in (("index", index), ("slot", slot)):
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
                fail("scrdb 항목 %r: %s 는 0 이상 정수 (%r)", name, label, v)
        if mode == "arr" and index is None:
            fail("scrdb 항목 %r: arr 항목은 index 가 필요합니다", name)
        if mode == "var" and slot is None:
            fail("scrdb 항목 %r: var 항목은 slot 이 필요합니다", name)
        if not isinstance(name, str) or not name:
            fail("scrdb 항목 이름은 빈 문자열이 아닌 문자열 (%r)", name)
        for k in extra:
            if k in ("id", "name", "mode", "index", "slot"):
                fail("scrdb 항목 %r: extra 에 %r 를 쓸 수 없습니다", name, k)
        self.name = name
        self.mode = mode
        self.index = index
        self.slot = slot
        self.deaths_unit = deaths_unit
        self.extra = dict(extra)

    @property
    def pos(self):
        """Lua `F.index or F.slot`."""
        return self.index if self.index is not None else self.slot

    def as_dict(self):
        """매니페스트에 적는 dict(name·mode·index/slot·extra)."""
        d = {"name": self.name, "mode": self.mode}
        if self.index is not None:
            d["index"] = self.index
        if self.slot is not None:
            d["slot"] = self.slot
        d.update(self.extra)
        return d

    def __repr__(self):
        return "<scrdb.Field %s %s %s>" % (self.name, self.mode, self.pos)


def f_arr(name, index, **extra):
    """arr 항목(전송 버퍼 칸)을 만든다.

    인자: name, index(0 이상), extra(매니페스트 추가 키)
    반환: Field
    비용: 없음(선언)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `scrdb.arr("Gold", 0)`
    출처: SCR_DB_Core.lua Cfg.Fields
    """
    return Field(name, "arr", index=index, **extra)


def f_var(name, slot, **extra):
    """var 항목(슬롯 블록 칸)을 만든다. epScript 에서는 `var` 가 예약어라 같은 함수 `scrdb.slot(…)` 을 쓴다.

    인자: name, slot(0 이상), extra(매니페스트 추가 키)
    반환: Field
    비용: 없음(선언)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `scrdb.slot("Stat", 0)`
    출처: SCR_DB_Core.lua Cfg.Fields
    """
    return Field(name, "var", slot=slot, **extra)


f_slot = f_var


def f_deaths(name, unit, **extra):
    """데스값 항목(MSF 방식): arr, index = 유닛×12. setup 의 xfer_base 는 0x58A364, xfer_stride 는 1 이어야 한다(기본값).

    인자: name, unit(데스 유닛 번호), extra
    반환: Field
    비용: 없음(선언)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `scrdb.deaths("NewLevel", 18)`
    출처: MapSource/MSF_UE_RE/SCR_DB_MSF.lua SCRMSF_Init (index = F[2] * 12)
    """
    if isinstance(unit, bool) or not isinstance(unit, int) or not 0 <= unit <= 0xFFFF:
        fail("scrdb.deaths %r: 유닛 번호 0~65535 (%r)", name, unit)
    return Field(name, "arr", index=unit * 12, deaths_unit=unit, **extra)


def _to_field(x):
    if isinstance(x, Field):
        return x
    if isinstance(x, dict):
        d = dict(x)
        d.pop("id", None)  # id 는 setup 이 다시 매긴다
        return Field(d.pop("name", None), d.pop("mode", None), index=d.pop("index", None), slot=d.pop("slot", None), **d)
    if isinstance(x, (list, tuple)) and len(x) == 3:
        name, mode, pos = x
        return Field(name, mode, index=pos if mode == "arr" else None, slot=pos if mode == "var" else None)
    fail("scrdb 항목으로 쓸 수 없는 값: %r (scrdb.arr/var/deaths, dict 또는 (이름, 모드, 칸))", x)


def _fields_of(fields):
    if isinstance(fields, (Field, dict)):
        fields = [fields]
    if isinstance(fields, EUDArray) or not isinstance(fields, (list, tuple)):
        fail("scrdb.setup: 항목은 파이썬 목록으로 줍니다 (epScript 는 list(a, b), 리스트 리터럴은 EUDArray 로 번역된다) — %r", fields)
    return [_to_field(x) for x in fields]


# ---------------------------------------------------------------------------------------------
# 지문·id·JSON (Lua 판 파이썬 구현 — 빌드마다 Lua 결과와 대조)
# ---------------------------------------------------------------------------------------------


def _lua_str(v):
    """Lua `string.format("%s", v)` / `tostring(v)` 의 바이트."""
    if isinstance(v, bytes):
        return v
    if isinstance(v, bool):
        return b"true" if v else b"false"
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e16:
            return ("%.1f" % v).encode()
        return repr(v).encode()
    return str(v).encode("utf-8", "surrogateescape")


def _lua_d(v):
    """Lua 5.4 `string.format("%d", v)`: 정수 값만(정수 float 도 된다)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EudextError("scrdb: %%d 에 숫자가 아닌 값 %r" % (v,))
    if isinstance(v, float):
        if v != int(v):
            raise EudextError("scrdb: %%d 에 정수가 아닌 수 %r (Lua 도 오류)" % (v,))
        v = int(v)
    return b"%d" % v


def _field_dict(f):
    return f.as_dict() if isinstance(f, Field) else dict(f)


def _pos(d):
    v = d.get("index")
    return d.get("slot") if v is None else v


def f_assign_ids(fields):
    """이름이 겹치는 항목에만 저장 위치를 붙인 id 를 매긴다(Lua `SCRDB_AssignIds` 의 파이썬 판).

    인자: fields(Field·dict 목록)
    반환: (id 목록, 겹친 이름 정렬 목록)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: SCR_DB_Core.lua:103 SCRDB_AssignIds
    """
    ds = [_field_dict(f) for f in fields]
    count = {}
    for d in ds:
        count[d["name"]] = count.get(d["name"], 0) + 1
    ids, dups = [], set()
    for d in ds:
        if count[d["name"]] > 1:
            ids.append((_lua_str(d["name"]) + b"#" + _lua_str(d["mode"]) + _lua_d(_pos(d))).decode("utf-8", "surrogateescape"))
            dups.add(d["name"])
        else:
            ids.append(d["name"])
    return ids, sorted(dups, key=lambda n: _lua_str(n))


def f_field_hash(fields, ids=None):
    """항목 목록의 지문(djb2 32비트, Lua `SCRDB_FieldHash` 의 파이썬 판). ids 가 없으면 `assign_ids` 로 매긴다.

    인자: fields(Field·dict 목록 — dict 에 "id" 가 있으면 그것을 쓴다), ids(선택)
    반환: int (부호 없는 32비트)
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: SCR_DB_Core.lua:127 SCRDB_FieldHash, DPS tools/scr_db_launcher.py:457 field_hash
    """
    ds = [_field_dict(f) for f in fields]
    if ids is None:
        if all("id" in d for d in ds):
            ids = [d["id"] for d in ds]
        else:
            ids = f_assign_ids(ds)[0]
    h = 5381
    for d, fid in zip(ds, ids):
        line = _lua_str(fid) + b"|" + _lua_str(d["mode"]) + b"|" + _lua_d(_pos(d)) + b"\n"
        for b in line:
            h = (h * 33 + b) % 4294967296
    return h


def _json_str(b):
    b = b.replace(b"\\", b"\\\\").replace(b'"', b'\\"')
    out = bytearray(b'"')
    for c in b:
        if c < 32 or c == 127:  # Lua %c (iscntrl, C 로캘)
            out += b"\\u%04x" % c
        else:
            out.append(c)
    out += b'"'
    return bytes(out)


def f_json_bytes(value):
    """Lua `SCRDB_Json` 과 같은 바이트 JSON(키 이름순, `%d` 숫자, `\\\\`·`\\"`·제어문자만 이스케이프, 비ASCII 그대로).

    파이썬 dict 는 Lua 표처럼 다룬다: 값이 None 인 칸은 없는 칸, 비었으면 `[]`, 키 1..n 이 있으면 배열(그 밖의 키는 버림).
    list 는 첫 None 앞까지 배열. 문자열이 아닌 키는 `tostring` 한 이름으로 정렬하고 값은 null(Lua 와 같음).
    인자: value
    반환: bytes
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: SCR_DB_Core.lua:323 SCRDB_Json
    """
    if isinstance(value, bool):
        return b"true" if value else b"false"
    if isinstance(value, (int, float)):
        return _lua_d(value)
    if isinstance(value, (str, bytes)):
        return _json_str(value.encode("utf-8", "surrogateescape") if isinstance(value, str) else value)
    if isinstance(value, (list, tuple)):
        items = []
        for x in value:
            if x is None:
                break
            items.append(f_json_bytes(x))
        return b"[" + b",".join(items) + b"]"
    if isinstance(value, dict):
        d = {k: v for k, v in value.items() if v is not None}
        n = 0
        while (n + 1) in d and not isinstance(n + 1, bool):
            n += 1
        if n > 0 or not d:
            return f_json_bytes([d[i] for i in range(1, n + 1)])
        keys = sorted(((_lua_str(k), k) for k in d), key=lambda kv: kv[0])
        parts = []
        for kb, k in keys:
            v = d[k] if isinstance(k, (str, bytes)) else None
            parts.append(_json_str(kb) + b":" + (b"null" if v is None else f_json_bytes(v)))
        return b"{" + b",".join(parts) + b"}"
    return b"null"


def f_manifest_name(save_key, field_hash_value):
    """배포용 매니페스트 파일 이름 `<이름표>_<지문 8자리>.json`.

    인자: save_key, field_hash_value
    반환: str
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS_Enhance-eudplib-port tools/build_headless.py:116 stash_manifest (e7efff2)
    """
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", str(save_key or "map"))
    return "%s_%08X.json" % (key, field_hash_value & M32)


def f_default_manifest_path(save_key):
    """매니페스트 기본 경로: Windows `C:\\Temp\\SCR_DB_manifest_<이름표>.json`(개발 PC 에서 런처가 찾는 자리), 그 밖은 `EUDEXT_WORK`.

    인자: save_key
    반환: str
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `scrdb.setup(…, manifest="auto")` 가 쓴다
    출처: DPS scr_db_launcher.py:117 DEFAULT_MANIFEST, SCR_DB_PORTING.md 1
    """
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", str(save_key or "map"))
    name = "SCR_DB_manifest_%s.json" % key
    if os.name == "nt":
        return os.path.join("C:\\Temp", name)
    work = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
    return os.path.join(work, name)


def f_stash_manifest(src, store):
    """매니페스트를 배포 폴더에 `<이름표>_<지문>.json` 으로 복사한다(런처 배포본 manifests 폴더용).

    인자: src(매니페스트 파일), store(폴더)
    반환: 복사한 경로
    비용: 없음(빌드 스크립트)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS_Enhance-eudplib-port tools/build_headless.py:103 stash_manifest (e7efff2)
    """
    with open(src, "r", encoding="utf-8") as f:
        doc = json.load(f)
    fh = doc.get("field_hash")
    if not isinstance(fh, int):
        fail("stash_manifest: %s 에 field_hash 가 없습니다", src)
    os.makedirs(store, exist_ok=True)
    dst = os.path.join(store, f_manifest_name(doc.get("save_key"), fh))
    shutil.copy2(src, dst)
    return dst


def _channel_pairs(addr, death, channels):
    # sync._scrdb_pairs 와 같은 식 (sync.scrdb_msqc_lines 는 기본 자리만 준다 — 시험이 두 결과를 대조한다)
    return [("Memory(0x%X,AtLeast,1); val, 0x%X" % (addr + 4 * k, addr + 4 * k), str(death + k)) for k in range(channels)]


def f_msqc_lines(addr=sync.SCRDB_MSQC_ADDR, death=sync.SCRDB_MSQC_DEATH, channels=sync.SCRDB_MSQC_CHANNELS):
    """SCR_DB 채널 `[MSQC]` 줄(자리를 바꿀 수 있는 `sync.scrdb_msqc_lines()`).

    인자: addr(채널 0 로컬 주소), death(채널 0 데스 유닛), channels
    반환: [str]
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS eudplib-port build_eud.py:37~42, SCR_DB_PORTING.md 3 (eds 채널 줄)
    """
    return ["%s : %s" % (sync.escape_key(k), v) for k, v in _channel_pairs(addr, death, channels)]


# ---------------------------------------------------------------------------------------------
# 상태
# ---------------------------------------------------------------------------------------------


class _BuildState:
    def __init__(self):
        self.anchor = False
        self.receiver = False
        self.notify = False
        self.checked = False
        self.manifest = None


_current = None
_bst = _BuildState()
_hook = {"active": False, "core": None, "build_id": None, "manifest": None, "frame": True}


def _reset_build():
    global _bst
    _bst = _BuildState()


_compat.register_build_reset(_reset_build)


def f_current():
    """지금 선언된 ScrDb 를 돌려준다(없으면 EudextError).

    인자: 없음
    반환: ScrDb
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const db = scrdb.current();`
    출처: 새로 작성
    """
    if _current is None:
        fail("scrdb.setup(…) 을 먼저 부르세요")
    return _current


def _map_info():
    try:
        chk = GetChkTokenized()
        ownr = chk.getsection("OWNR")
        dim = chk.getsection("DIM")
    except Exception:  # noqa: BLE001 — 맵을 읽지 않은 경우
        return None, None
    humans = [p for p in range(8) if ownr[p] == 6]
    size = (dim[0] | dim[1] << 8, dim[2] | dim[3] << 8)
    return humans, size


def _msqc_val_mask(size):
    # MSQC 0.11 onInit: map_x = (dim_x - 1).bit_length() + 4, valMask = 2^map_x - 1 + ((2^map_y - 1) << map_x)
    # (euddraft 0.11.0.1 plugins/MSQC.py:263, 503 — "Sendable value range for 'val' syntax")
    mx = (size[0] - 1).bit_length() + 4
    my = (size[1] - 1).bit_length() + 4
    return (2**mx - 1) + ((2**my - 1) << mx)


def _in_mirror(lo, hi):
    return MIRROR_REGION[0] <= lo and hi <= MIRROR_REGION[1]


def _overlap(a, b):
    return a[0] < b[1] and b[0] < a[1]


class ScrDb:
    """SCR_DB 설정 하나(맵에 하나). `setup(...)` 이 만든다 — 인자 설명은 `setup`.

    인자: `setup` 과 같다
    속성: `core`(ScrdbCore), `fields`, `ids`, `dup_names`, `field_hash`, `build_id`, `generated`, `save_key`, `anchor_base`,
          `humans`, `channels`, `msqc_addr`, `msqc_death`, `xfer_base`/`xfer_stride`, `slot_base`/`slot_stride`,
          `max_players`, `slot_count`, `key_mode`, `extra`, `manifest`, `bus`(sync.Bus), `lua_cfg`(Lua 가 보완한 설정),
          `ready`/`saved`/`activity`(EUDArray(8) — 수신기가 1 로 세우고 맵이 내린다)
    반환: -
    비용: 선언 때 EUDArray 3개(8칸). 트리거는 anchor/receiver/notify 가 낸다(각 메서드)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const db = scrdb.setup(…);` 뒤 `db.frame();`
    출처: SCR_DB_Core.lua (Cfg·SCRDB_* 전역)
    """

    def __init__(self, fields, save_key, layout=None, *, anchor=DEFAULT_ANCHOR, humans=None, channels=None,
                 msqc_addr=None, msqc_death=None, xfer_base=None, xfer_stride=None, slot_base=None, slot_stride=None,
                 max_players=None, slot_count=None, key_mode="ordinal", extra=None, manifest=None, bus=None,
                 qc_unit=None, write=None, guard=None, build_id=None, core=None, generated=None, name="scrdb",
                 allow_outside_mirror=False):
        self.core = _lc.scrdb_core(core or _hook["core"])
        c = self.core
        if c.table_players & (c.table_players - 1):
            fail("scrdb: Lua 코어의 SCRDB_TABLE_PLAYERS=%s 가 2의 거듭제곱이 아니면 수신기를 만들 수 없습니다", c.table_players)
        if layout is not None and layout != c.layout:
            fail("scrdb.setup: layout=%r 이지만 Lua 코어(%s)는 레이아웃 %s 입니다", layout, c.path, c.layout)
        self.fields = _fields_of(fields)
        if not 1 <= len(self.fields) <= MAX_FIELDS:
            fail("scrdb.setup: 항목 수 %d (1 ~ %d — 런처가 받는 범위)", len(self.fields), MAX_FIELDS)
        if not isinstance(save_key, str) or not save_key:
            fail("scrdb.setup: save_key 는 빈 문자열이 아닌 문자열 (%r)", save_key)
        self.save_key = save_key
        map_humans, self.map_size = _map_info()
        if humans is None:
            if not map_humans:
                fail("scrdb.setup: humans 를 주세요 (맵을 읽지 않았거나 사람 슬롯이 없습니다)")
            humans = max(map_humans) + 1
        self.humans = humans
        self.channels = sync.SCRDB_MSQC_CHANNELS if channels is None else channels
        self.msqc_addr = sync.SCRDB_MSQC_ADDR if msqc_addr is None else msqc_addr
        self.msqc_death = sync.SCRDB_MSQC_DEATH if msqc_death is None else msqc_death
        self.anchor_base = anchor
        self.key_mode = key_mode
        self.max_players = c.table_players if max_players is None else max_players
        for label, v in (("anchor", anchor), ("humans", humans), ("channels", self.channels),
                         ("msqc_addr", self.msqc_addr), ("msqc_death", self.msqc_death), ("max_players", self.max_players)):
            if isinstance(v, bool) or not isinstance(v, int):
                fail("scrdb.setup: %s 는 정수 상수 (%r)", label, v)
        modes = {f.mode for f in self.fields}
        if key_mode == "index" and "var" in modes:
            # Lua 는 `and F.index or (n - 1)` 라 순번으로 넘어가지만 런처 plan() 은 f["index"] 에서 멈춘다
            fail("scrdb.setup: key_mode='index' 에는 arr 항목만 쓸 수 있습니다 (var 항목 %s)",
                 [f.name for f in self.fields if f.mode == "var"][:5])
        all_deaths = all(f.deaths_unit is not None for f in self.fields)
        if all_deaths:
            xfer_base = DEATHS_BASE if xfer_base is None else xfer_base
            xfer_stride = 1 if xfer_stride is None else xfer_stride
        if any(f.deaths_unit is not None for f in self.fields) and (xfer_base, xfer_stride) != (DEATHS_BASE, 1):
            fail("scrdb.setup: deaths 항목은 xfer_base=0x58A364, xfer_stride=1 일 때만 됩니다 (지금 %r, %r)", xfer_base, xfer_stride)
        if "arr" in modes and (xfer_base is None or xfer_stride is None):
            fail("scrdb.setup: arr 항목이 있으면 xfer_base·xfer_stride 가 필요합니다")
        if "var" in modes and (slot_base is None or slot_stride is None):
            fail("scrdb.setup: var 항목이 있으면 slot_base·slot_stride 가 필요합니다")
        # 없는 쪽은 있는 쪽 값을 적는다 (런처는 두 보폭이 모두 0 보다 커야 블록을 받는다)
        if xfer_base is None:
            xfer_base, xfer_stride = slot_base, slot_stride
        if slot_base is None:
            slot_base, slot_stride = xfer_base, xfer_stride
        self.xfer_base, self.xfer_stride = xfer_base, xfer_stride
        self.slot_base, self.slot_stride = slot_base, slot_stride
        for label, v in (("xfer_base", xfer_base), ("xfer_stride", xfer_stride), ("slot_base", slot_base),
                         ("slot_stride", slot_stride)):
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                fail("scrdb.setup: %s 는 0 보다 큰 정수 상수 (%r)", label, v)
        if slot_count is None:
            slots = [f.slot for f in self.fields if f.mode == "var"]
            slot_count = max(slots) + 1 if slots else 0
        self.slot_count = slot_count
        self.extra = dict(extra or {})
        if build_id is None:
            build_id = _hook["build_id"]
        if build_id is None and os.environ.get(BUILD_ID_ENV):
            build_id = int(os.environ[BUILD_ID_ENV], 0)
        if build_id is None:
            build_id = int(time.time()) % 0x7FFFFFFF
        if isinstance(build_id, bool) or not isinstance(build_id, int) or not 0 <= build_id < 0x7FFFFFFF:
            fail("scrdb.setup: build_id 는 0 ~ 0x7FFFFFFE (%r)", build_id)
        self.build_id = build_id
        self.generated = generated or time.strftime("%Y-%m-%d %H:%M:%S")
        if manifest == "auto":
            manifest = f_default_manifest_path(save_key)
        self.manifest = manifest
        self.write = write
        self.guard = guard
        self.name = name

        # --- Lua 로 검사·보완 (단일 출처) ---
        lua_cfg = {
            "SaveKey": save_key, "Fields": [f.as_dict() for f in self.fields], "AnchorBase": anchor, "Humans": humans,
            "MsqcAddr": self.msqc_addr, "MsqcDeath": self.msqc_death, "XferBase": xfer_base, "XferStride": xfer_stride,
            "SlotBase": slot_base, "SlotStride": slot_stride, "ManifestPath": manifest or "unused.json",
            "Channels": self.channels, "KeyMode": key_mode, "MaxPlayers": self.max_players, "SlotCount": slot_count,
        }
        if self.extra:
            lua_cfg["Extra"] = self.extra
        self._lua_in = lua_cfg
        try:
            res = c.setup(lua_cfg, os_time=build_id)
        except _lc.LuaStubError as e:
            raise EudextError("scrdb.setup: Lua 코어가 설정을 거부했습니다 — %s" % str(e).replace("[eudext] ", "")) from e
        self.lua_cfg = res
        self.ids = [f["id"] for f in res["Fields"]]
        self.dup_names = list(res["DupNames"])
        self.field_hash = res["FieldHash"]
        # 파이썬 판과 대조 (b)
        py_ids, py_dups = f_assign_ids(self.fields)
        if py_ids != self.ids or py_dups != self.dup_names or f_field_hash(self.fields, py_ids) != self.field_hash:
            fail("scrdb 내부 오류: 파이썬 id/FieldHash 가 Lua 와 다릅니다 (%r / %r, %r / %r)",
                 py_ids[:5], self.ids[:5], f_field_hash(self.fields, py_ids), self.field_hash)
        if res["BuildId"] != build_id:
            fail("scrdb 내부 오류: Lua BuildId %r != %r", res["BuildId"], build_id)

        # --- eudext 추가 검사 ---
        self._regions = self._make_regions()
        if not allow_outside_mirror:
            for label, (lo, hi) in self._regions.items():
                if label.startswith("death") or label == "values_none":
                    continue
                if not _in_mirror(lo, hi):
                    fail("scrdb.setup: %s 자리 0x%X~0x%X 가 런처가 닿는 구역 0x%X~0x%X 밖입니다 (allow_outside_mirror=True 로 끔)",
                         label, lo, hi, MIRROR_REGION[0], MIRROR_REGION[1])
        a = self._regions["anchor"]
        for label in ("values_arr", "values_var", "deaths"):
            r = self._regions.get(label)
            if r and _overlap(a, r):
                fail("scrdb.setup: 표지 블록 0x%X~0x%X 가 %s 0x%X~0x%X 와 겹칩니다", a[0], a[1], label, r[0], r[1])
        if self.map_size is not None and _msqc_val_mask(self.map_size) < c.word_mask():
            fail("scrdb.setup: 맵 %dx%d 의 MSQC val 범위 0~%d 로는 워드(최대 0x%X)를 보낼 수 없습니다",
                 self.map_size[0], self.map_size[1], _msqc_val_mask(self.map_size), c.word_mask())
        self._check_other_buses()

        # --- MSQC 채널 (d) ---
        if bus is None:
            bus = sync.Bus("msqc", qc_unit=qc_unit, name=name)
        elif qc_unit is not None:
            fail("scrdb.setup: bus 를 주면 qc_unit 은 그 버스에서 정합니다")
        if getattr(bus, "transport", None) is None or bus.transport.name != "msqc":
            fail("scrdb.setup: bus 는 MSQC sync.Bus 여야 합니다 (%r)", bus)
        self.bus = bus
        if (self.msqc_addr, self.msqc_death, self.channels) == (
                sync.SCRDB_MSQC_ADDR, sync.SCRDB_MSQC_DEATH, sync.SCRDB_MSQC_CHANNELS):
            bus.scrdb_channels()
        else:
            for k, v in _channel_pairs(self.msqc_addr, self.msqc_death, self.channels):
                bus.raw(k, v)

        # --- 실행 칸 ---
        self.ready = EUDArray(8)
        self.saved = EUDArray(8)
        self.activity = EUDArray(8)
        self._writer_tables = None

    def __repr__(self):
        return "<scrdb.ScrDb %s 항목 %d, 사람 %d, 채널 %d, 지문 %08X>" % (
            self.save_key, len(self.fields), self.humans, self.channels, self.field_hash)

    # --- 주소 ---
    def addr(self, name_or_index):
        """표지 블록 칸의 EUD 주소.

        인자: name_or_index(`SCRDB_I` 키 또는 칸 번호)
        반환: int
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `dwread(db.addr("Seq"))`
        출처: SCR_DB_Core.lua:96 SCRDB_Addr
        """
        i = self.core.index[name_or_index] if isinstance(name_or_index, str) else name_or_index
        if not 0 <= i < self.core.total:
            fail("scrdb: 표지 블록 칸 번호 %r 는 0..%d 밖", i, self.core.total - 1)
        return self.anchor_base + 4 * i

    def slot(self, k, i):
        """MsqcCount/Echo 표의 (채널 k, 플레이어 i) 칸 오프셋 = `SCRDB_Slot(0, k, i)`(k·표 플레이어 수 + i).

        인자: k, i
        반환: int
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: SCR_DB_Core.lua:91 SCRDB_Slot
        """
        return k * self.core.table_players + i

    def death_epd(self, k, i):
        """채널 k 로 플레이어 i 가 받은 워드가 들어오는 데스 칸의 EPD.

        인자: k, i
        반환: int
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: SCR_DB_Core.lua:258 (MsqcDeath + k)
        """
        return (self.msqc_death + k) * 12 + i

    def _field_place(self, field):
        f = self._field(field)
        if f.mode == "arr":
            return self.xfer_base + f.index * 4, self.xfer_stride
        return self.slot_base + f.slot * 4, self.slot_stride

    def field_addr(self, field, p):
        """항목의 플레이어 p 값 주소(런처가 읽고 기본 쓰기 함수가 쓰는 칸).

        인자: field(id·번호·Field), p(0~7 상수 또는 변수)
        반환: int, 또는 p 가 변수면 EUDVariable 식
        비용: 변수 p 면 곱셈·덧셈 계산
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `dwread(db.field_addr("Gold", p))`
        출처: DPS scr_db_launcher.py:418 Manifest.offsets
        """
        base, stride = self._field_place(field)
        if IsEUDVariable(p):
            return base + p * (4 * stride)
        return base + self._pconst(p) * stride * 4

    def field_epd(self, field, p):
        """`field_addr` 의 EPD.

        인자: field, p(상수 또는 변수)
        반환: int 또는 EUDVariable 식
        비용: 변수 p 면 계산
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `dwwrite_epd(db.field_epd("Gold", p), 0);`
        출처: 새로 작성
        """
        base, stride = self._field_place(field)
        if IsEUDVariable(p):
            return _epd(base) + (p if stride == 1 else p * stride)
        return (_epd(base) + self._pconst(p) * stride) & M32

    def msqc_count_addr(self, k, i):
        """MsqcCount[채널 k, 플레이어 i] 칸 주소(받아들인 워드 수).

        인자: k, i
        반환: int
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `dwread(db.msqc_count_addr(0, 0))`
        출처: 새로 작성
        """
        return self.addr(self.core.index["MsqcCount"] + self.slot(k, i))

    def msqc_echo_addr(self, k, i):
        """MsqcEcho[채널 k, 플레이어 i] 칸 주소(받은 워드의 꼬리표+페이로드).

        인자: k, i
        반환: int
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `dwread(db.msqc_echo_addr(0, 0))`
        출처: 새로 작성
        """
        return self.addr(self.core.index["MsqcEcho"] + self.slot(k, i))

    def key_of(self, field):
        """항목이 MSQC 로 받는 키(ordinal = 순번, index = index 값).

        인자: field
        반환: int
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: DPS scr_db_launcher.py:450 Manifest.plan
        """
        f = self._field(field)
        return self.fields.index(f) if self.key_mode == "ordinal" else f.index

    def _field(self, field):
        if isinstance(field, Field):
            if field not in self.fields:
                fail("scrdb: 이 설정의 항목이 아닙니다 (%r)", field)
            return field
        if isinstance(field, int) and not isinstance(field, bool):
            return self.fields[field]
        hits = [f for f, fid in zip(self.fields, self.ids) if fid == field]
        if len(hits) != 1:
            fail("scrdb: 항목 id %r 를 찾지 못했습니다(이름이 겹치면 id = 이름#모드칸)", field)
        return hits[0]

    def _make_regions(self):
        c = self.core
        out = {"anchor": (self.anchor_base, self.anchor_base + 4 * c.total),
               "msqc": (self.msqc_addr, self.msqc_addr + 4 * self.channels)}
        d0 = DEATHS_BASE + 4 * self.death_epd(0, 0)
        out["deaths"] = (d0, DEATHS_BASE + 4 * (self.death_epd(self.channels - 1, 7) + 1))
        for mode, base, stride in (("arr", self.xfer_base, self.xfer_stride), ("var", self.slot_base, self.slot_stride)):
            pos = [f.pos for f in self.fields if f.mode == mode]
            if pos:
                out["values_" + mode] = (base + min(pos) * 4, base + ((self.max_players - 1) * stride + max(pos) + 1) * 4)
        return out

    def _check_other_buses(self):
        mine = set(range(self.msqc_death, self.msqc_death + self.channels))
        for b in sync.buses("nsqc"):
            for ch in b.channels:
                unit = getattr(getattr(ch, "out", None), "unit", None)
                if unit in mine:
                    fail("scrdb: NSQC 버스 %s 의 출력 데스 유닛 %d 이 SCR_DB 채널 데스 유닛과 겹칩니다", b.name, unit)

    def _value(self, src):
        kind, v = src
        if kind == "const":
            return v
        if v == "#Fields":
            return len(self.fields)
        if v not in self.lua_cfg:
            fail("scrdb: Lua 헤더 계획의 값 %r 를 설정에서 찾지 못했습니다", v)
        return self.lua_cfg[v]

    # --- 매니페스트 (b) ---
    def manifest_doc(self):
        """매니페스트 dict (Lua `SCRDB_WriteManifest` 의 파이썬 판 — 키 이름은 그 함수에서 옮겼다).

        인자: 없음
        반환: dict
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: SCR_DB_Core.lua:356 SCRDB_WriteManifest
        """
        c = self.core
        fields = []
        for f, fid in zip(self.fields, self.ids):
            d = f.as_dict()
            d["id"] = fid
            fields.append(d)
        doc = {
            "format": "scr-db-manifest",
            "layout_version": c.layout,
            "build_id": self.build_id,
            "generated": self.generated,
            "signature": list(c.magic),
            "header": dict(c.index),
            "total_dwords": c.total,
            "anchor_eud": self.anchor_base,
            "xfer_base": self.xfer_base,
            "xfer_stride": self.xfer_stride,
            "slot_base": self.slot_base,
            "slot_stride": self.slot_stride,
            "slot_count": self.slot_count,
            "max_players": self.max_players,
            "humans": self.humans,
            "msqc_addr": self.msqc_addr,
            "msqc_death": self.msqc_death,
            "msqc_channels": self.channels,
            "msqc_key": self.key_mode,
            "field_hash": self.field_hash,
            "save_key": self.save_key,
            "duplicate_names": list(self.dup_names),
            "fields": fields,
        }
        doc.update(self.extra)
        return doc

    def manifest_bytes(self, check=True):
        """매니페스트 파일 내용 — Lua 가 쓴 바이트. check=True 면 파이썬 판(`json_bytes(manifest_doc())`)과 같은지 확인한다.

        인자: check(bool)
        반환: bytes
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: SCR_DB_Core.lua:323 SCRDB_Json, 356 SCRDB_WriteManifest
        """
        lua_bytes = self.core.manifest_bytes(self._lua_in, os_time=self.build_id, os_date=self.generated)
        if check:
            py = f_json_bytes(self.manifest_doc())
            if py != lua_bytes:
                fail("scrdb 내부 오류: 파이썬 매니페스트가 Lua 와 다릅니다\n  Lua %r\n  py  %r", lua_bytes[:200], py[:200])
        return lua_bytes

    def write_manifest(self, path=None):
        """매니페스트를 파일로 쓴다(폴더를 만든다).

        인자: path(없으면 setup 의 manifest, 그것도 없으면 `default_manifest_path(save_key)`)
        반환: 경로
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `db.write_manifest();`
        출처: SCR_DB_Core.lua:356 SCRDB_WriteManifest
        """
        path = path or self.manifest or f_default_manifest_path(self.save_key)
        data = self.manifest_bytes()
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    # --- 규약 행동 (액션·조건) ---
    def save_signal(self, p):
        """저장 신호 액션: 플레이어 p 의 SaveSeqP 칸 +1 (런처는 자기 칸만 본다). 값이 다 준비된 순간에만 올린다.

        인자: p(0~7 상수, 변수 — 변수면 DoActions/Trigger 안에서만)
        반환: Action
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유 안전(공유 조건으로 부를 것)
        epScript: `DoActions(db.save_signal(p));`
        출처: SCR_DB_Core.lua:245 SCRDB_SaveSignal
        """
        base = self.core.index["SaveSeqP"]
        if IsEUDVariable(p):
            return SetMemoryEPD(_epd(self.addr(base)) + p, Add, 1)
        p = self._pconst(p)
        return SetMemory(self.addr(base + p), Add, 1)

    def close_load(self, conds=None):
        """조건이 참인 사이클부터 LoadOpen 칸을 0 으로(불러오기를 더 받지 않음). conds 는 **공유 조건만**.

        인자: conds(조건 또는 목록, 없으면 무조건)
        반환: None (보존 트리거 1개를 낸다)
        비용: 호출 1 / 실행 1
        CP: 바꾸지 않음
        로컬: 공유 조건이어야 한다
        epScript: `db.close_load(list(Switch("Switch 240", Set)));`
        출처: SCR_DB_Core.lua:240 SCRDB_CloseLoad
        """
        RawTrigger(conditions=_flat(conds), actions=SetMemory(self.addr("LoadOpen"), SetTo, 0))

    def close_load_action(self):
        """LoadOpen = 0 액션(맵의 다른 트리거에 끼울 때).

        인자: 없음
        반환: Action
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유 조건으로 부를 것
        epScript: `DoActions(db.close_load_action());`
        출처: SCR_DB_Core.lua:240
        """
        return SetMemory(self.addr("LoadOpen"), SetTo, 0)

    @staticmethod
    def _pconst(p):
        if p is CurrentPlayer:
            fail("scrdb: CurrentPlayer 대신 f_getcurpl() 을 넘기세요")
        code = EncodePlayer(p)
        if not isinstance(code, int) or not 0 <= code <= 7:
            fail("scrdb: 플레이어는 0~7 (%r)", p)
        return code

    def _flag(self, arr, p, value):
        if p is CurrentPlayer:
            p = f_getcurpl()
        if IsEUDVariable(p):
            return MemoryEPD(_compat.eudarray_epd(arr) + p, Exactly, value)
        return MemoryEPD(_compat.eudarray_epd(arr) + self._pconst(p), Exactly, value)

    def _set_flag(self, arr, p, value):
        if p is CurrentPlayer:
            p = f_getcurpl()
        if IsEUDVariable(p):
            return SetMemoryEPD(_compat.eudarray_epd(arr) + p, SetTo, value)
        return SetMemoryEPD(_compat.eudarray_epd(arr) + self._pconst(p), SetTo, value)

    def launcher_ready(self, p):
        """조건: 플레이어 p 의 런처가 불러오기를 끝냈다(예약 워드 0xFFFE 를 MSQC 로 받음, 맵이 내릴 때까지 1).

        인자: p(0~7, 변수, CurrentPlayer)
        반환: Condition (변수 p 면 앞 계산 트리거가 부르는 자리에 생긴다)
        비용: 상수 p = 조건 1 / 변수 p = 계산 2~3 + 조건 1
        CP: 바꾸지 않음
        로컬: 공유 안전(MSQC 로 받은 값)
        epScript: `if (db.launcher_ready(p)) { … DoActions(db.clear_ready(p)); }`
        출처: SCR_DB_Core.lua:186 SCRDB_LauncherReady
        """
        return self._flag(self.ready, p, 1)

    def save_done(self, p):
        """조건: 플레이어 p 의 세이브 파일까지 쓰였다(예약 워드 저장 완료를 MSQC 로 받음, 맵이 내릴 때까지 1).

        인자: p(0~7, 변수, CurrentPlayer)
        반환: Condition
        비용: `launcher_ready` 와 같음
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (db.save_done(p)) { … }`
        출처: SCR_DB_Core.lua:187 SCRDB_SaveDone
        """
        return self._flag(self.saved, p, 1)

    def got_word(self, p):
        """조건: 플레이어 p 의 워드가 하나라도 왔다(맵이 내리기 전까지 1 — 불러오는 중 표시용).

        인자: p(0~7, 변수, CurrentPlayer)
        반환: Condition
        비용: `launcher_ready` 와 같음
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `if (db.got_word(p)) { … }`
        출처: SCR_DB_Core.lua:188 SCRDB_Activity
        """
        return self._flag(self.activity, p, 1)

    def clear_ready(self, p):
        """액션: launcher_ready 표시를 내린다.

        인자: p(상수 — 어디든, 변수 — DoActions/Trigger 안에서)
        반환: Action
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유 조건으로 부를 것
        epScript: `DoActions(db.clear_ready(p));`
        출처: 새로 작성
        """
        return self._set_flag(self.ready, p, 0)

    def clear_save_done(self, p):
        """액션: save_done 표시를 내린다.

        인자: p(상수 또는 변수)
        반환: Action
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유 조건으로 부를 것
        epScript: `DoActions(db.clear_save_done(p));`
        출처: 새로 작성
        """
        return self._set_flag(self.saved, p, 0)

    def clear_word(self, p):
        """액션: got_word 표시를 내린다.

        인자: p(상수 또는 변수)
        반환: Action
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유 조건으로 부를 것
        epScript: `DoActions(db.clear_word(p));`
        출처: 새로 작성
        """
        return self._set_flag(self.activity, p, 0)

    # --- 트리거 내기 ---
    def _emit_check(self, what):
        if _hook["active"] and _hook["frame"] and not _bst_from_hook[0]:
            fail("scrdb.%s(): scrdb 훅 플러그인이 이미 frame() 을 냅니다 — 맵에서 부르지 마세요(훅 설정 Frame : 0 으로 끔)", what)
        if getattr(_bst, what):
            fail("scrdb.%s() 를 이 빌드에서 두 번 냈습니다", what)
        setattr(_bst, what, True)

    def anchor(self):
        """표지 블록: 게임 시작 1회 블록(0 초기화 → 헤더 → 시그니처 마지막) + 매 사이클 LocalPlayer·Seq.

        Lua 코어의 계획(`core.anchor_once`/`anchor_every`)을 그대로 낸다. 매 사이클 무조건 도는 자리에서 부른다.
        인자: 없음
        반환: None
        비용: 1회 블록 트리거 5(+분기) / 매 사이클 트리거 9 (실행 9 — LocalPlayer 조건 8 + Seq 1)
        CP: 바꾸지 않음
        로컬: LocalPlayer 트리거는 로컬 조건(표지 블록 칸만 쓴다, 보존)
        epScript: `db.anchor();` (보통 `db.frame();`)
        출처: SCR_DB_Core.lua:195 SCRDB_Anchor
        """
        self._emit_check("anchor")
        if EUDExecuteOnce()():
            for trig in self.core.anchor_once:
                DoActions([SetMemory(self.addr(i), _MODS[m], self._value(src)) for i, m, src in trig])
        EUDEndExecuteOnce()
        for conds, acts in self.core.anchor_every:
            RawTrigger(
                conditions=[Memory(LOCAL_PLAYER_ADDR, _CMPS[c], v) for _kind, c, v in conds],
                actions=[SetMemory(self.addr(i), _MODS[m], self._value(src)) for i, m, src in acts],
            )

    def notify(self):
        """런처 알림음: 알림 칸이 코드면 이 PC(P1~P8)에게 소리를 내고 칸을 0 으로(관전자는 소리 없이 0).

        인자: 없음
        반환: None
        비용: 트리거 = 코드 수 + 지우기(코드가 이어진 수면 1, 아니면 코드 수) + CP 복구 1 (Lua 코어 4코드 → 6, 실행 6)
        CP: 소리 트리거가 이 PC 번호로 바꾸고 바로 뒤에서 캐시로 되돌린다
        로컬: 로컬 전용(알림 칸은 런처가 이 PC 에만 쓴다) — 표지 블록 칸·CP·PlayWAV 만 건드린다
        epScript: `db.notify();` (보통 `db.frame();`)
        출처: SCR_DB_Core.lua:306 SCRDB_Notify, eudplib PlayWAVAll(이 PC 번호로 CP)
        """
        self._emit_check("notify")
        n = self.addr(self.core.notify_index)
        codes = [code for code, _w in self.core.notify]
        for code, wav in self.core.notify:
            RawTrigger(
                conditions=[Memory(n, Exactly, code), Memory(LOCAL_PLAYER_ADDR, AtMost, 7)],
                actions=[*PlayWAVAll(wav), SetMemory(n, SetTo, 0)],
            )
        if codes and sorted(codes) == list(range(min(codes), max(codes) + 1)):
            RawTrigger(conditions=[Memory(n, AtLeast, min(codes)), Memory(n, AtMost, max(codes))],
                       actions=SetMemory(n, SetTo, 0))
        else:
            for code in codes:
                RawTrigger(conditions=Memory(n, Exactly, code), actions=SetMemory(n, SetTo, 0))
        f_setcurpl2cpcache()

    def receiver(self, write=None):
        """MSQC 수신기: 채널 × 플레이어마다 트리거 1개 + 공유 본문 한 벌. 값 하나가 모이면 `write(p, key, val)` 을 부른다.

        같은 빌드에서 `anchor()` 가 아직 없으면 먼저 낸다(4.18 (e)). `[MSQC]` 플러그인 뒤, 매 사이클 도는 자리에서 부른다.
        인자: write(선택: 파이썬 함수 fn(p, key, val) — 세 인자 모두 EUDVariable(읽기 전용). EUDFunc(epScript 함수)도 된다.
              없으면 setup 의 write, 그것도 없으면 `default_writer(guard=setup 의 guard)`).
              write 는 CP 가 캐시와 같은 상태에서 불린다. write 안에서 이 모듈의 함수(receiver 등)를 부르지 않는다(재진입 금지).
        반환: None
        비용: 호출 자리 = 채널×사람 트리거(각 조건 1·액션 2, 받은 워드가 없으면 실행 1) + 본문 한 벌 +
              칸 표 6개(채널×12 dword 씩). 수치는 docs/COSTS.md "scrdb (WP18)"
        CP: 바꾸지 않음(본문이 잠깐 데스 칸으로 옮기고 끝에서 캐시로 되돌린다)
        로컬: 공유 안전(MSQC 로 받은 데스값만 읽는다)
        epScript: `db.receiver();` (보통 `db.frame();`)
        출처: SCR_DB_Core.lua:252 SCRDB_Receiver, R2 3.1 가치 2
        """
        if not _bst.anchor:
            self.anchor()
        self._emit_check("receiver")
        self._build_checks()
        write = write or self.write or self.default_writer(self.guard)
        # 호출 자리 n = k·사람 수 + i (조밀 번호). 표 한 개에 필드 7개를 n 칸씩 잇는다 → 본문은 CP = EPD(표) + n 으로 두고
        # 필드 f 를 CP + f·N (정수 오프셋)으로 읽고 쓴다. (eudplib 0.81 은 페이로드 주소가 음수로 들어간 식을 재배치하지 못해
        # CP 읽기 오프셋에 표 주소를 섞을 수 없다 — 실측)
        order = [(k, i) for k in range(self.channels) for i in range(self.humans)]
        nsite = len(order)
        sites = [(k, i, Forward(), Forward()) for k, i in order]
        fields = [
            [EPD(site) + 1 for _k, _i, site, _a in sites],  # 0 호출 트리거 next 칸 EPD
            [after for _k, _i, _s, after in sites],  # 1 호출 트리거 다음 트리거 (돌아갈 곳)
            [self.death_epd(k, i) for k, i, _s, _a in sites],  # 2 데스 칸 EPD
            [self.slot(k, i) for k, i, _s, _a in sites],  # 3 Count/Echo 칸 번호
            [0] * nsite,  # 4 상태: 비트 0 = 토글(Tog), 비트 1 = 하위 16비트 받음(HaveLo)
            [0] * nsite,  # 5 키 (하위 16비트)
            [0] * nsite,  # 6 하위 값 (하위 16비트)
        ]
        tab = EUDArray([v for col in fields for v in col])
        vn = EUDVariable()
        sub = _parts.SubLabel("scrdb.receiver")
        with sub.define():
            self._emit_body(write, sub, tab, vn, nsite)
        for n, (k, i, site, after) in enumerate(sites):
            site << RawTrigger(
                conditions=Deaths(i, AtLeast, 1, self.msqc_death + k),
                actions=[vn.SetNumber(n), SetNextPtr(site, sub.entry)],
            )
            after << NextTrigger()

    def _emit_body(self, write, sub, tab, vn, N):
        c = self.core
        cp = _CP_ADDR
        tab_epd = _compat.eudarray_epd(tab)
        F_SITE, F_AFTER, F_DEATH, F_SLOT, F_STATE, F_KEY, F_LO = (f * N for f in range(7))

        def to_base():  # CP = EPD(표) + n (잠깐 옮기기 — 끝에서 f_setcurpl2cpcache)
            SeqCompute([(EPD(cp), SetTo, vn), (EPD(cp), Add, tab_epd)])

        # 1) 호출한 트리거의 next 를 되돌리고 돌아갈 곳을 정한다 (표를 액션 칸·next 칸에 바로 읽어 넣는다)
        to_base()
        restore = Forward()
        f_dwread_cp(F_SITE, ret=[EPD(restore) + _ACT0_PLAYER // 4])
        f_dwread_cp(F_AFTER, ret=[EPD(restore) + _ACT0_VALUE // 4])
        f_dwread_cp(F_AFTER, ret=[EPD(sub.ret) + 1])
        restore << RawTrigger(actions=SetMemoryEPD(0, SetTo, 0))  # 칸은 바로 위 읽기가 채운다
        # 2) 워드와 칸 상태
        w, st, cnt, dth, s8, key, lo, val = (EUDVariable() for _ in range(8))
        dth << f_dwread_cp(F_DEATH)
        st << f_dwread_cp(F_STATE)
        w << f_maskread_epd(dth, c.word_mask())  # CP 가 캐시로 돌아간다
        to_base()
        DoActions(cnt.SetNumber(0))
        # 토글 두 if 는 else 가 아니다 (Lua: CIf A → CIfEnd, CIf B → CIfEnd)
        RawTrigger(conditions=[w.ExactlyX(c.toggle_a, c.toggle_a), st.ExactlyX(0, 1)],
                   actions=[st.SetNumberX(1, 1), cnt.AddNumber(1)])
        RawTrigger(conditions=[w.ExactlyX(c.toggle_b, c.toggle_b), st.ExactlyX(1, 1)],
                   actions=[st.SetNumberX(0, 1), cnt.AddNumber(1)])
        if EUDIf()(cnt.AtLeast(1)):
            anchor_epd = _epd(self.anchor_base)
            s8 << f_dwread_cp(F_SLOT)
            p = _parts.and_const(s8, c.table_players - 1)
            DoActions(
                SetMemoryEPD(anchor_epd + c.index["MsqcCount"] + s8, Add, cnt),
                SetMemoryEPD(anchor_epd + c.index["MsqcEcho"] + s8, SetTo, w),
                SetMemoryXEPD(anchor_epd + c.index["MsqcEcho"] + s8, SetTo, 0, M32 & ~c.echo_mask),
                SetMemoryEPD(_compat.eudarray_epd(self.activity) + p, SetTo, 1),
            )
            if EUDIf()(w.ExactlyX(c.tag_key, c.tag_mask)):
                DoActions(
                    st.SetNumberX(0, 2),
                    SetMemory(cp, Add, F_KEY),
                    SetDeaths(CurrentPlayer, SetTo, w, 0),
                    SetDeathsX(CurrentPlayer, SetTo, 0, 0, M32 & ~c.payload),
                    SetMemory(cp, Add, -F_KEY),
                )
                if EUDIf()(w.ExactlyX(c.word_ready, c.payload)):
                    DoActions(SetMemoryEPD(_compat.eudarray_epd(self.ready) + p, SetTo, 1))
                EUDEndIf()
                if EUDIf()(w.ExactlyX(c.word_saved, c.payload)):
                    DoActions(SetMemoryEPD(_compat.eudarray_epd(self.saved) + p, SetTo, 1))
                EUDEndIf()
            EUDEndIf()
            if EUDIf()(w.ExactlyX(c.tag_lo, c.tag_mask)):
                DoActions(
                    st.SetNumberX(2, 2),
                    SetMemory(cp, Add, F_LO),
                    SetDeaths(CurrentPlayer, SetTo, w, 0),
                    SetDeathsX(CurrentPlayer, SetTo, 0, 0, M32 & ~c.payload),
                    SetMemory(cp, Add, -F_LO),
                )
            EUDEndIf()
            # 칸 상태를 되돌려 쓴다 (쓰기 함수보다 먼저 — 그 앞에서 CP 가 캐시로 돌아간다)
            DoActions(SetMemory(cp, Add, F_STATE), SetDeaths(CurrentPlayer, SetTo, st, 0), SetMemory(cp, Add, -F_STATE))
            # 상위 워드 뒤에도 HaveLo 를 내리지 않는다 (재전송 멱등)
            if EUDIf()([w.ExactlyX(c.tag_hi, c.tag_mask), st.ExactlyX(2, 2)]):
                key << f_dwread_cp(F_KEY)
                lo << f_dwread_cp(F_LO)
                val << lo + self._hi_reader()(dth)  # CP 가 캐시로 돌아간다
                write(p, key, val)
            EUDEndIf()
        EUDEndIf()
        f_setcurpl2cpcache()

    def _hi_reader(self):
        # 페이로드 × 65536 (Lua: CAdd(Val, Lo, _Mul(Pay, 65536))) — 연속 마스크 + 자리 옮김이라 eudplib 읽기 표를 쓴다
        width = self.core.payload + 1
        return f_readgen_epd(self.core.payload, (0, lambda x: x * width))

    def default_writer(self, guard=None):
        """기본 쓰기 함수: 받은 값을 그 항목의 값 칸(`field_addr(항목, p)`)에 쓴다. 없는 키는 무시한다.

        ordinal: 순번 → P1 칸 EPD 표(EUDArray, 항목 수) + 플레이어 보폭 표. index: 항목마다 키 비교 트리거 1개.
        인자: guard(선택: 쓰기 전에 더 볼 **공유** 조건 — 조건·목록, 또는 조건을 돌려주는 함수(빌드마다 새로))
        반환: fn(p, key, val)
        비용: ordinal = 쓰기 1회 실행 약 80~120 / index = 항목 수 트리거
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `scrdb.setup(…, guard=list(Switch("Switch 240", Cleared)))` (기본 쓰기 함수에 넘어간다)
        출처: DPS SCR_DB.lua:299 SCR_DB_Receiver(범위 검사 + 표), MSF SCR_DB_MSF.lua SCRMSF_Exec(데스 칸)
        """

        def write(p, key, val):
            conds = guard() if callable(guard) else guard
            conds = _flat(conds)
            if self.key_mode == "ordinal":
                self._write_ordinal(p, key, val, conds)
            else:
                self._write_index(p, key, val, conds)

        return write

    def _tables(self):
        if self._writer_tables is None:
            mp = self.max_players
            xs = [(q * self.xfer_stride) & M32 for q in range(mp)]
            ss = [(q * self.slot_stride) & M32 for q in range(mp)]
            modes = {f.mode for f in self.fields}
            mixed = len(modes) > 1
            p1 = EUDArray([self.field_epd(f, 0) for f in self.fields])
            kinds = EUDArray([(mp if f.mode == "var" else 0) for f in self.fields]) if mixed else None
            off = EUDArray((xs + ss) if mixed else (ss if modes == {"var"} else xs))
            self._writer_tables = (p1, kinds, off)
        return self._writer_tables

    def _write_ordinal(self, p, key, val, conds):
        p1, kinds, off = self._tables()
        if EUDIf()([key.AtMost(len(self.fields) - 1)] + conds):
            e = EUDVariable()
            e << p1[key]
            if kinds is not None:
                o = kinds[key] + p
                e += off[o]
            else:
                e += off[p]
            DoActions(SetMemoryEPD(e, SetTo, val))
        EUDEndIf()

    def _write_index(self, p, key, val, conds):
        e, ok = EUDVariable(), EUDVariable()
        DoActions(ok.SetNumber(0))
        for f in self.fields:
            RawTrigger(conditions=key.Exactly(f.index), actions=[e.SetNumber(_epd(self.xfer_base) + f.index), ok.SetNumber(1)])
        if EUDIf()([ok.Exactly(1)] + conds):
            if self.xfer_stride == 1:
                e += p
            else:
                _, _, off = self._tables()
                e += off[p]
            DoActions(SetMemoryEPD(e, SetTo, val))
        EUDEndIf()

    def frame(self, write=None):
        """한 사이클 분량: `anchor()` → `receiver(write)` → `notify()`. 훅 플러그인이 있으면 아무것도 내지 않는다.

        인자: write(선택 — receiver 와 같음)
        반환: None
        비용: anchor + receiver + notify (t_scrdb 비용 표 "frame")
        CP: 바꾸지 않음
        로컬: anchor·notify 의 로컬 칸 규칙(모듈 docstring (f))
        epScript: `function beforeTriggerExec() { db.frame(); … }`
        출처: SCR_DB_Core.lua 머리 주석의 부르는 순서, DPS SCR_DB.lua:204 SCR_DB_Exec
        """
        if _hook["active"] and _hook["frame"] and not _bst_from_hook[0]:
            return
        self.anchor()
        self.receiver(write)
        self.notify()

    # --- 빌드 검사 ---
    def _build_checks(self):
        if _bst.checked:
            return
        _bst.checked = True
        sync.verify()
        if self.core.receiver_digest != RECEIVER_DIGEST:
            warn("scrdb: Lua 코어(%s)의 SCRDB_Receiver 가 eudext 가 따라간 판과 다릅니다(지문 %s) — "
                 "t_scrdb 수신기 차등 시험으로 다시 확인하세요", self.core.path, self.core.receiver_digest[:12])
        f_check_forbidden(self)
        _check_plugin_order()
        if _compat.onstart_phase() == 1:
            _compat.on_start_after_main(lambda: f_check_forbidden(self))
        if self.manifest and _bst.manifest is None and not _hook["manifest"]:
            _bst.manifest = self.write_manifest()
            print("[eudext.scrdb] 매니페스트 %s (빌드 %d, 지문 %08X, 항목 %d)" % (
                _bst.manifest, self.build_id, self.field_hash, len(self.fields)))


def _flat(x):
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        out = []
        for y in x:
            out.extend(_flat(y))
        return out
    return [x]


_bst_from_hook = [False]


def _in_euddraft():
    return "pluginLoader" in sys.modules and "applyeuddraft" in sys.modules


def _eds_sections():
    """euddraft 안이면 명령줄의 eds 섹션 이름 목록(없으면 None)."""
    if not _in_euddraft():
        return None
    for a in sys.argv[1:]:
        if a.lower().endswith((".eds", ".edd")) and os.path.isfile(a):
            out = []
            with open(a, encoding="utf-8-sig", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("[") and line.endswith("]"):
                        out.append(line[1:-1].strip())
            return out
    return None


def _plugin_base(name):
    return os.path.basename(name.replace("\\", "/")).lower()


def _caller_plugin():
    """지금 트리거를 내는 euddraft 플러그인 모듈 이름(전역에 settings 가 있는 가장 가까운 프레임, 없으면 None)."""
    f = sys._getframe(1)
    while f is not None:
        g = f.f_globals
        name = g.get("__name__") or ""
        if isinstance(g.get("settings"), dict) and not name.startswith("eudext."):
            return name
        f = f.f_back
    return None


def _check_plugin_order(sections=None, caller=None):
    """(e) 수신기를 내는 플러그인은 eds 에서 [MSQC] 뒤여야 한다. euddraft 안에서 eds 를 읽어 확인한다.

    인자: sections(섹션 이름 목록 — 없으면 명령줄의 eds), caller(플러그인 모듈 이름 — 없으면 호출 스택에서 찾는다)
    플러그인 모듈 이름 = 섹션 파일 이름에서 확장자를 뺀 것(euddraft 0.11 실측).
    """
    secs = _eds_sections() if sections is None else sections
    if not secs:
        return
    caller = caller or _caller_plugin()
    if not caller:
        return
    low = [x.lower() for x in secs]
    if "msqc" not in low:
        return  # sync.verify 가 알린다
    at = low.index("msqc")
    for i, sec in enumerate(secs):
        b = _plugin_base(sec)
        if b.endswith((".py", ".eps")) and os.path.splitext(b)[0] == caller.lower() and i < at:
            fail("SCR_DB 수신기를 내는 플러그인 [%s] 이 [MSQC] 앞에 있습니다 — eds 에서 [MSQC] 를 먼저 두세요"
                 "(MSQC 가 같은 사이클에 받은 데스값을 수신기가 읽어야 한다, DESIGN 4.18 (e))", sec)


def f_check_forbidden(db=None):
    """금지 조합 검사(DESIGN 3.9): eudplib `IsPName` 라이트 변수 칸이 SCR_DB 자리와 겹치면 오류.

    `receiver()` 가 부르고, 빌드 끝(주 함수 뒤)에 한 번 더 부른다.
    인자: db(선택, 기본 current())
    반환: None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: R2 3.1 (d), G8 1.11-6, eudplib 0.81 string/pname.py `_get_player_lightvar`
    """
    db = db or f_current()
    units = _compat.pname_lightvar_units()
    if not units:
        return
    lo = DEATHS_BASE + 4 * (units[0] * 12)
    hi = DEATHS_BASE + 4 * (units[-1] * 12 + 8)
    for label, r in db._regions.items():
        if _overlap((lo, hi), r):
            fail("SCR_DB 와 eudplib IsPName(이름 변수·CurrentPlayer)을 같이 쓸 수 없습니다: IsPName 칸 0x%X~0x%X 가 "
                 "SCR_DB %s 0x%X~0x%X 와 겹칩니다 (DESIGN 3.9). IsPName 을 상수 플레이어·문자열로 쓰거나 "
                 "scrdb.setup(msqc_addr=…, msqc_death=…) 로 채널을 옮기세요", lo, hi, label, r[0], r[1])


def f_setup(fields, save_key, layout=None, **kw):
    """SCR_DB 설정(맵에 하나, **모듈 최상위**에서 — 선언 수집과 빌드에서 같은 순서로 실행).

    인자: fields(항목 목록 — `arr`/`var`/`deaths`, dict, (이름, 모드, 칸)), save_key(세이브 이름표 — 맵마다 다르게, 바꾸지 않는다),
          layout(확인용 — Lua 코어와 다르면 오류),
          anchor(표지 블록 자리, 기본 0x594198 — 맵이 쓰지 않는 미러 구역), humans(수신 플레이어 수 P1..Pn, 기본 맵의 가장 큰 사람 번호+1),
          channels(기본 8), msqc_addr(기본 0x58F508), msqc_death(기본 21),
          xfer_base/xfer_stride(arr 항목 자리 — deaths 항목만이면 0x58A364/1), slot_base/slot_stride(var 항목 자리),
          max_players(기본 Lua 표 플레이어 수 8), slot_count(기본 var 칸 최대+1), key_mode("ordinal" | "index"),
          extra(매니페스트에 덧붙일 dict), manifest(경로 또는 "auto" — 빌드 때 receiver() 가 쓴다),
          bus(MSQC sync.Bus — 없으면 이름 name 으로 새로), qc_unit(새 버스의 QCUnit), write(쓰기 함수), guard(기본 쓰기 함수 조건),
          build_id(기본: 훅 BuildId > 환경 변수 EUDEXT_SCRDB_BUILD_ID > 지금 시각 % 0x7FFFFFFF), core(Lua 코어 경로),
          generated(매니페스트 생성 시각 문자열), name(버스 이름), allow_outside_mirror
    반환: ScrDb
    비용: 없음(선언 — EUDArray 5개: 표시 3×8칸, 상태 2×(채널×8)칸)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const db = scrdb.setup(list(scrdb.arr("Gold", 0)), "MyMap", xfer_base=0x58F678, xfer_stride=16);`
    출처: SCR_DB_Core.lua:150 SCRDB_Setup
    """
    global _current
    if _current is not None:
        fail("scrdb.setup 이 두 번 불렸습니다 (맵에 설정은 하나)")
    _current = ScrDb(fields, save_key, layout, **kw)
    return _current


def f_declared():
    """선언된 ScrDb 또는 None (빌드 스크립트·tools/edsgen 용).

    인자: 없음
    반환: ScrDb | None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    return _current


def f_frame(write=None):
    """`current().frame(write)` — 표지 블록 → 수신기 → 알림음.

    인자: write(선택)
    반환: None
    비용: ScrDb.frame 과 같음
    CP: 바꾸지 않음
    로컬: ScrDb.frame 과 같음
    epScript: `scrdb.frame();`
    출처: SCR_DB_Core.lua 머리 주석의 부르는 순서
    """
    return f_current().frame(write)


def f_anchor():
    """`current().anchor()` — 표지 블록.

    인자: 없음
    반환: None
    비용: ScrDb.anchor 와 같음
    CP: 바꾸지 않음
    로컬: LocalPlayer 칸은 로컬 조건
    epScript: `scrdb.anchor();`
    출처: SCR_DB_Core.lua:195 SCRDB_Anchor
    """
    return f_current().anchor()


def f_receiver(write=None):
    """`current().receiver(write)` — MSQC 수신기.

    인자: write(선택)
    반환: None
    비용: ScrDb.receiver 와 같음
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `scrdb.receiver();`
    출처: SCR_DB_Core.lua:252 SCRDB_Receiver
    """
    return f_current().receiver(write)


def f_notify():
    """`current().notify()` — 런처 알림음.

    인자: 없음
    반환: None
    비용: ScrDb.notify 와 같음
    CP: 바꾸지 않음(잠깐 옮기고 되돌림)
    로컬: 로컬 전용
    epScript: `scrdb.notify();`
    출처: SCR_DB_Core.lua:306 SCRDB_Notify
    """
    return f_current().notify()


def f_save_signal(p):
    """`current().save_signal(p)` — 저장 신호 액션.

    인자: p(0~7 상수 또는 변수)
    반환: Action
    비용: 액션 1
    CP: 바꾸지 않음
    로컬: 공유 조건으로 부를 것
    epScript: `DoActions(scrdb.save_signal(p));`
    출처: SCR_DB_Core.lua:245 SCRDB_SaveSignal
    """
    return f_current().save_signal(p)


def f_close_load(conds=None):
    """`current().close_load(conds)` — 조건이 참인 사이클부터 LoadOpen = 0.

    인자: conds(공유 조건)
    반환: None
    비용: 호출 1 / 실행 1
    CP: 바꾸지 않음
    로컬: 공유 조건이어야 한다
    epScript: `scrdb.close_load(list(Switch("Switch 240", Set)));`
    출처: SCR_DB_Core.lua:240 SCRDB_CloseLoad
    """
    return f_current().close_load(conds)


def f_write_manifest(path=None):
    """`current().write_manifest(path)` — 매니페스트 파일을 쓴다.

    인자: path(선택)
    반환: 경로
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `scrdb.write_manifest();`
    출처: SCR_DB_Core.lua:356 SCRDB_WriteManifest
    """
    return f_current().write_manifest(path)


def f_clear():
    """선언을 지운다(한 프로세스에서 설정을 여러 번 만드는 시험·빌드 스크립트용). sync 버스는 지우지 않는다.

    인자: 없음
    반환: None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    global _current
    _current = None
    _reset_build()


# ---------------------------------------------------------------------------------------------
# 훅 플러그인
# ---------------------------------------------------------------------------------------------

HOOK_SOURCE = '''"""eudext.scrdb 훅 플러그인 — tools/edsgen 이 만든 파일(고치지 않는다).

eds 순서: [eudext boot (VenvSite, Preload: scrdb)] → [MSQC] → [eudext_sync_hook.py] → [이 파일] → 맵 플러그인.
- 불러올 때: 설정(Core·BuildId·Manifest·Frame)을 scrdb 에 넘긴다(맵 플러그인의 scrdb.setup 보다 먼저 읽힌다).
- onPluginStart: scrdb.setup 이 있었는지 확인하고 Manifest 가 있으면 매니페스트를 쓴다.
- beforeTriggerExec: [MSQC] 수신 뒤, 맵 코드 앞에서 표지 블록·수신기·알림음을 낸다(scrdb frame).
"""
import eudext.scrdb as _scrdb

_scrdb.hook_loaded(settings)


def onPluginStart():
    _scrdb.hook_plugin_start()


def beforeTriggerExec():
    _scrdb.hook_before()
'''


def f_hook_source():
    """훅 플러그인 파일 내용. `tools/edsgen.EdsDoc.add_scrdb()` 가 eds 옆에 쓴다.

    인자: 없음
    반환: str
    비용: 훅이 내는 트리거 = frame()
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    return HOOK_SOURCE


def f_write_hook(path):
    """훅 플러그인 파일을 쓴다(CRLF).

    인자: path
    반환: path
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: 새로 작성
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(HOOK_SOURCE)
    return path


def hook_loaded(settings):
    """훅 플러그인을 불러올 때 부른다(설정 키 대소문자 무시: Core, BuildId, Manifest, Frame). 훅 파일 전용.

    인자: settings(eds 훅 섹션)
    반환: None
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: sync.hook_loaded 와 같은 방식
    """
    opts = {str(k).strip().lower(): str(v).strip() for k, v in (settings or {}).items()}
    _hook["active"] = True
    _hook["core"] = opts.get("core") or None
    bid = opts.get("buildid")
    _hook["build_id"] = int(bid, 0) if bid else None
    _hook["manifest"] = opts.get("manifest") or None
    _hook["frame"] = opts.get("frame", "1") not in ("0", "false", "off")


def hook_plugin_start():
    """훅 onPluginStart: setup 확인·매니페스트 쓰기(설정 Manifest). 훅 파일 전용."""
    db = f_current()
    if _hook["manifest"] and _bst.manifest is None:
        _bst.manifest = db.write_manifest(_hook["manifest"])
        print("[eudext.scrdb] 매니페스트 %s (빌드 %d, 지문 %08X, 항목 %d)" % (
            _bst.manifest, db.build_id, db.field_hash, len(db.fields)))


def hook_before():
    """훅 beforeTriggerExec: frame() 을 낸다(설정 Frame : 0 이면 아무것도). 훅 파일 전용."""
    if not _hook["frame"]:
        return
    db = f_current()
    _bst_from_hook[0] = True
    try:
        db.frame()
    finally:
        _bst_from_hook[0] = False


def hook_reset():
    """훅 상태를 지운다(시험용)."""
    _hook.update({"active": False, "core": None, "build_id": None, "manifest": None, "frame": True})


# --- epScript·파이썬 공용 이름 ------------------------------------------------------------------
arr = f_arr
var = f_var
slot = f_slot
deaths = f_deaths
setup = f_setup
current = f_current
declared = f_declared
frame = f_frame
anchor = f_anchor
receiver = f_receiver
notify = f_notify
save_signal = f_save_signal
close_load = f_close_load
write_manifest = f_write_manifest
clear = f_clear
field_hash = f_field_hash
assign_ids = f_assign_ids
json_bytes = f_json_bytes
manifest_name = f_manifest_name
default_manifest_path = f_default_manifest_path
stash_manifest = f_stash_manifest
msqc_lines = f_msqc_lines
check_forbidden = f_check_forbidden
hook_source = f_hook_source
write_hook = f_write_hook
