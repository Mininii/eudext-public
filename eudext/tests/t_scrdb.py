"""`scrdb`·`tools/lua_consts`(SCR_DB 부분) 시험 (WP18, DESIGN 4.18).

python tests/t_scrdb.py
비용 표: python tools/cost.py tests/t_scrdb.py [--append --bytes]

1. 약속 값이 Lua 코어에서 온다 — ScrdbCore 값·계획, DPS 런처 원문 상수와 대조, scrdb.py 에 레이아웃 숫자가 없음, sync 줄 형식 공유
2. FieldHash·id·JSON·매니페스트 — Lua `SCRDB_FieldHash/AssignIds/Json/WriteManifest` 와 바이트 차등(무작위 + 경계)
3. 설정 검사 — Lua `SCRDB_Setup` 이 거부하는 것과 eudext 추가 검사
4. 수신기·표지 블록·알림음 — 에뮬레이터 대 Lua 트리 실행 모델(`ref_scrdb.LuaFrame`) 차등, 기본 쓰기 함수, 세 설정
5. 1회 블록 순서·시그니처 비연속·로컬 칸(LocalPlayer·Notify 가 공유 칸을 건드리지 않음)
6. 바꾼 Lua 코어(칸 번호·시그니처·토글·꼬리표·예약 워드·알림 코드)로 빌드해도 Lua 모델과 같다 — (a) 단일 출처
7. MSQC.py 실제 수신 코드 + 런처 전송 모델(락스텝·에코·되읽기·준비·저장 완료) + 턴 모델 + 워드 깨짐
8. edsgen.add_scrdb·훅·예제 eds 의 [MSQC] 줄
9. 금지 조합(IsPName 라이트 변수, NSQC 데스 유닛, 플러그인 순서) — 빌드 오류 기대
10. epScript 예제 번역·euddraft 빌드(정적 eds, 훅 eds, 순서 틀림, lupa 없음), 산출 chk 에 시그니처가 연속으로 없음
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import ast  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import struct  # noqa: E402
import subprocess  # noqa: E402
import tokenize  # noqa: E402
import warnings  # noqa: E402

from eudplib import (  # noqa: E402
    CompressPayload,
    CurrentPlayer,
    DoActions,
    EUDArray,
    EUDEndIf,
    EUDFunc,
    EUDIf,
    EUDVariable,
    GetChkTokenized,
    GetEUDNamespace,
    IsPName,
    LoadMap,
    Memory,
    Exactly,
    P1,
    RawTrigger,
    SetMemoryEPD,
    SetTo,
    f_getcurpl,
    f_setcurpl,
)

import ref_scrdb  # noqa: E402
from eudext import _compat, scrdb, sync  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import emu, scmodel  # noqa: E402
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.testing.syncmodel import (  # noqa: E402
    QCUnits,
    TurnSim,
    load_plugin,
    set_humans,
    settings_of,
    unload_plugin,
)
from eudext.tools import build as tbuild  # noqa: E402
from eudext.tools import edsgen  # noqa: E402
from eudext.tools import lua_consts as lc  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
REPO = _common.ROOT
PKG = _common.PKG
EXAMPLES = os.path.join(PKG, "examples")
BASE_MULTI = os.path.join(PKG, "testing", "base_multi.scx")
MSQC_PY = os.path.join(REPO, ".tools", "euddraft0.11.0.1", "plugins", "MSQC.py")
PORT = "/home/developer/DPS_Enhance-eudplib-port"
LAUNCHER_PY = os.path.join(PORT, "tools", "scr_db_launcher.py")
WORK = os.path.join(_common.WORK, "t_scrdb")
os.makedirs(WORK, exist_ok=True)
VENV_SITE = os.path.join(REPO, ".tools", "euddraft_site")

ck = Checker("t_scrdb (python)")
CORE = lc.scrdb_core(quiet=True)
A, B = CORE.toggle_a, CORE.toggle_b


def fresh(base=BASE_MAP, humans=None):
    """선언·버스·훅 상태를 지우고 맵을 다시 읽는다(사람 슬롯을 바꿀 수 있다). 같은 선언을 다시 모을 수 있게
    sync 가 eudplib 네임스페이스에 등록한 `eudext_` 이름도 지운다."""
    scrdb.clear()
    scrdb.hook_reset()
    sync._buses[:] = []
    ns = GetEUDNamespace()
    for k in [k for k in ns if k.startswith("eudext_")]:
        del ns[k]
    LoadMap(base)
    CompressPayload(True)
    if humans is not None:
        set_humans(humans)


def dword_bytes(m):
    """에뮬레이터에 올린 페이로드 바이트(재배치 뒤)."""
    out = bytearray()
    for a in range(m.base, m.limit_addr, 4):
        out += struct.pack("<I", m.dw(a))
    return bytes(out)


# =============================================================================================
# 1. 약속 값·계획
# =============================================================================================


def _launcher_consts():
    """DPS 런처 원문(읽기만)의 모듈 수준 상수를 ast 로 읽는다."""
    with open(LAUNCHER_PY, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        t = node.targets[0]
        try:
            if isinstance(t, ast.Name):
                if isinstance(node.value, ast.Name) and node.value.id in out:
                    out[t.id] = out[node.value.id]
                else:
                    out[t.id] = ast.literal_eval(node.value)
            elif isinstance(t, ast.Tuple):
                names = [e.id for e in t.elts]
                v = node.value
                if isinstance(v, ast.Call) and getattr(v.func, "id", "") == "range":
                    vals = list(range(*[ast.literal_eval(a) for a in v.args]))
                else:
                    vals = list(ast.literal_eval(v))
                out.update(zip(names, vals))
        except (ValueError, SyntaxError, AttributeError, TypeError):
            continue
    return out


def _launcher_field_hash():
    with open(LAUNCHER_PY, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "field_hash":
            ns = {}
            exec(compile(ast.Module([node], []), LAUNCHER_PY, "exec"), ns)
            return ns["field_hash"]
    return None


def _camel(name):
    return "".join(w.capitalize() for w in name.split("_"))


def section_consts():
    c = CORE
    ck.eq("layout from lua", c.layout, 7)
    ck.eq("total", c.total, 168)
    ck.true("core path", os.path.isfile(c.path) and c.path.endswith("SCR_DB_Core.lua"), c.path)
    ref = os.path.join(lc.REFERENCE_LIBRARY, lc.SCRDB_CORE_NAME)
    if os.path.isfile(ref):
        same = lc.file_info(ref)[1] == c.sha256
        print("  저장소 사본(reference) %s 최신본과 %s" % (ref, "같음" if same else "다름 — 최신본 기준"))
    # 런처 원문과 대조 (Lua 가 단일 출처이고 런처는 같은 값을 따로 적었다)
    if os.path.isfile(LAUNCHER_PY):
        L = _launcher_consts()
        ck.eq("launcher magic", tuple(L["SCR_MAGIC"]), c.magic)
        ck.eq("launcher total", L["SCR_TOTAL"], c.total)
        ck.true("launcher supports layout", c.layout in L["SUPPORTED_LAYOUTS"], L["SUPPORTED_LAYOUTS"])
        ck.eq("launcher layout", L["SCR_LAYOUT_VERSION"], c.layout)
        ck.eq("launcher toggles", tuple(L["MSQC_TOGGLES"][c.layout]), (c.toggle_a, c.toggle_b))
        ck.eq("launcher tags", (L["MSQC_TAG_KEY"], L["MSQC_TAG_LO"], L["MSQC_TAG_HI"]), (c.tag_key, c.tag_lo, c.tag_hi))
        ck.eq("launcher echo", L["MSQC_ECHO_MASK"], c.echo_mask)
        ck.eq("launcher words", (L["MSQC_WORD_READY"], L["MSQC_WORD_SAVED"]), (c.word_ready, c.word_saved))
        ck.eq("launcher table players", L["MSQC_TABLE_PLAYERS"], c.table_players)
        idx = {_camel(k[2:]): v for k, v in L.items() if k.startswith("I_")}
        ck.eq("launcher index", {k: idx.get(k) for k in c.index}, c.index)
        ck.eq("launcher notify codes", sorted(v for k, v in L.items() if k.startswith("NOTIFY_")),
              sorted(code for code, _w in c.notify))
    else:
        print("  DPS 런처 원문이 없어 대조를 건너뜀: %s" % LAUNCHER_PY)
    # 계획 모양: 0 초기화 → 헤더 → 시그니처(마지막, 한 트리거 8액션)
    flat = [a for trig in c.anchor_once for a in trig]
    ck.eq("plan zero first", flat[: c.total], [(i, "SetTo", ("const", 0)) for i in range(c.total)])
    ck.eq("plan sig last", c.anchor_once[-1], [(i, "SetTo", ("const", c.magic[i])) for i in range(8)])
    header = {a[0]: a[2] for a in flat[c.total: -8]}
    ck.eq("plan header sources", {k: v for k, v in header.items() if v[0] == "cfg"}, {
        c.index["Build"]: ("cfg", "BuildId"), c.index["Self"]: ("cfg", "AnchorBase"),
        c.index["XferBase"]: ("cfg", "XferBase"), c.index["XferStride"]: ("cfg", "XferStride"),
        c.index["SlotBase"]: ("cfg", "SlotBase"), c.index["SlotStride"]: ("cfg", "SlotStride"),
        c.index["MaxPlayers"]: ("cfg", "MaxPlayers"), c.index["SlotCount"]: ("cfg", "SlotCount"),
        c.index["FieldCount"]: ("cfg", "#Fields"), c.index["FieldHash"]: ("cfg", "FieldHash"),
        c.index["Humans"]: ("cfg", "Humans"), c.index["MsqcAddr"]: ("cfg", "MsqcAddr"),
        c.index["MsqcChannels"]: ("cfg", "Channels")})
    ck.eq("plan header consts", header[c.index["Version"]], ("const", c.layout))
    ck.eq("plan every", c.anchor_every, [([("local_player", "Exactly", i)], [(c.index["LocalPlayer"], "SetTo", ("const", i + 1))])
                                          for i in range(8)] + [([], [(c.index["Seq"], "Add", ("const", 1))])])
    ck.eq("plan notify", (c.notify_index, [x[0] for x in c.notify]), (c.index["Notify"], [1, 2, 3, 4]))
    ck.eq("receiver digest", c.receiver_digest, scrdb.RECEIVER_DIGEST)
    ck.eq("slot formula", [c.slot(24, k, i) for k, i in ((0, 0), (1, 3), (7, 7))], [24 + 0, 24 + 8 + 3, 24 + 56 + 7])
    # scrdb.py 코드(주석·문서 제외)에 레이아웃 숫자가 없다
    with open(scrdb.__file__, "rb") as f:
        toks = list(tokenize.tokenize(io.BytesIO(f.read()).readline))
    nums = set()
    for t in toks:
        if t.type == tokenize.NUMBER:
            try:
                nums.add(int(t.string, 0))
            except ValueError:
                pass
    forbidden = set(c.magic) | {c.toggle_a, c.toggle_b, c.tag_mask, c.tag_lo, c.tag_hi, c.echo_mask, c.word_ready,
                                c.word_saved, c.total} | {v for k, v in c.index.items() if v >= 88}
    ck.eq("no layout literals in scrdb.py", sorted(nums & forbidden), [])
    # sync 와 같은 줄 형식 (4.18 (d))
    ck.eq("msqc lines = sync", scrdb.msqc_lines(), sync.scrdb_msqc_lines())
    ck.eq("msqc lines custom", scrdb.msqc_lines(0x593F00, 182, 2),
          ["Memory(0x593F00,AtLeast,1); val, 0x593F00 : 182", "Memory(0x593F04,AtLeast,1); val, 0x593F04 : 183"])
    # 명령줄
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, os.path.join(PKG, "tools", "lua_consts.py"), "scrdb", "--json"], capture_output=True,
                       env=env, timeout=120)
    try:
        d = json.loads(p.stdout.decode("utf-8"))
    except ValueError:
        d = {}
    ck.eq("cli scrdb json", (p.returncode, d.get("layout"), d.get("receiver_digest")), (0, c.layout, c.receiver_digest))
    # 코어 찾기 규칙
    old = os.environ.get(lc.SCRDB_CORE_ENV)
    try:
        os.environ[lc.SCRDB_CORE_ENV] = os.path.dirname(c.path)
        ck.eq("env dir", lc.find_scrdb_core(), (c.path, "환경 변수 %s" % lc.SCRDB_CORE_ENV))
        os.environ[lc.SCRDB_CORE_ENV] = os.path.join(WORK, "nope")
        ck.raises("env missing", lc.LuaConstsError, lc.find_scrdb_core)
    finally:
        if old is None:
            os.environ.pop(lc.SCRDB_CORE_ENV, None)
        else:
            os.environ[lc.SCRDB_CORE_ENV] = old
    cands = lc.scrdb_core_candidates()
    ck.true("candidates order", cands[0] == os.path.join(os.path.dirname(REPO), "MapSource", "Library")
            and cands[-1] == lc.REFERENCE_LIBRARY, cands)
    ck.eq("explicit path", lc.find_scrdb_core(c.path)[0], c.path)
    ck.raises("explicit missing", lc.LuaConstsError, lc.find_scrdb_core, os.path.join(WORK, "x.lua"))


# =============================================================================================
# 2. FieldHash·id·JSON·매니페스트 차등
# =============================================================================================

ALPHA = list("abcXYZ_09#|한글값 é") + ['"', "\\", "\x01", "\x1f", "\x7f", "\n", "\t", ":"]


def _rname(rng, pool=None):
    if pool and rng.random() < 0.4:
        return rng.choice(pool)
    return "".join(rng.choice(ALPHA) for _ in range(rng.randrange(1, 9)))


def _rfields(rng, n):
    pool = [_rname(rng) for _ in range(3)]
    out = []
    for _ in range(n):
        mode = rng.choice(["arr", "var"])
        pos = rng.choice([0, 1, rng.randrange(100), rng.randrange(70000)])
        d = {"name": _rname(rng, pool), "mode": mode, ("index" if mode == "arr" else "slot"): pos}
        out.append(d)
    return out


def _rvalue(rng, depth=0):
    r = rng.random()
    if depth > 2 or r < 0.35:
        return rng.choice([0, 1, -5, 2**40, M32, True, False, 3.0, _rname(rng), "", "\x00x"])
    if r < 0.65:
        return [_rvalue(rng, depth + 1) for _ in range(rng.randrange(0, 4))]
    return {_rname(rng): _rvalue(rng, depth + 1) for _ in range(rng.randrange(0, 4))}


def section_json():
    rng = random.Random(1804)
    launcher_hash = _launcher_field_hash() if os.path.isfile(LAUNCHER_PY) else None
    bad = 0
    for n in range(300):
        fields = _rfields(rng, rng.randrange(1, 25))
        lf, ldups = CORE.assign_ids(fields)
        ids, dups = scrdb.assign_ids(fields)
        ok = ids == [f["id"] for f in lf] and dups == list(ldups)
        h_lua = CORE.field_hash(lf)
        ok = ok and scrdb.field_hash(fields) == h_lua and scrdb.field_hash(lf) == h_lua
        if launcher_hash is not None:
            ok = ok and launcher_hash(lf) == h_lua
        ck.true("fieldhash/ids %d" % n, ok, "ids %r / %r hash %r / %r" % (
            ids[:3], [f["id"] for f in lf][:3], scrdb.field_hash(fields), h_lua))
    for n in range(400):
        v = _rvalue(rng)
        lua, py = CORE.json(v), scrdb.json_bytes(v)
        ck.true("json %d" % n, lua == py, "%r\n   Lua %r\n   py  %r" % (v, lua, py))
    edges = [{}, [], {"a": None}, [1, None, 2], {1: "x", 2: "y"}, {1: "x", "k": 2}, {2: "x"}, True, False, -5, 2**40,
             3.0, "제어\x00\x01\x7f", {"b": {}, "a": []}, {"z": [{"y": 1}]}, "\"\\/", 0xFFFFFFFF]
    for i, v in enumerate(edges):
        ck.eq("json edge %d" % i, scrdb.json_bytes(v), CORE.json(v))
    ck.raises("json float py", EudextError, scrdb.json_bytes, 1.5)
    ck.raises("json float lua", lc.LuaConstsError, CORE.json, 1.5)
    ck.eq("fieldhash known", scrdb.field_hash([{"name": "a", "mode": "arr", "index": 0}]),
          CORE.field_hash([{"id": "a", "name": "a", "mode": "arr", "index": 0}]))
    # 매니페스트 전체 (무작위 설정 60개) — ScrDb 가 Lua 바이트와 파이썬 바이트를 대조하고, 여기서 한 번 더
    fresh()
    for n in range(60):
        fields = []
        for d in _rfields(rng, rng.randrange(1, 12)):
            extra = {"desc": _rname(rng)} if rng.random() < 0.2 else {}
            if d["mode"] == "arr":
                fields.append(scrdb.arr(d["name"], d["index"] % 50, **extra))
            else:
                fields.append(scrdb.var(d["name"], d["slot"] % 50, **extra))
        kw = dict(humans=rng.randrange(1, 9), channels=rng.randrange(1, 9), xfer_base=0x58F678, xfer_stride=64,
                  slot_base=0x590000, slot_stride=60, build_id=rng.randrange(0x7FFFFFFF), key_mode="ordinal",
                  generated="2026-09-%02d 12:34:56" % rng.randrange(1, 29), name="mj%d" % n,
                  extra=_rvalue(rng, 2) if rng.random() < 0.5 else {"require_launcher": 1, "map_title": "한글 맵"})
        if not isinstance(kw["extra"], dict) or not kw["extra"]:
            kw["extra"] = {"n": n}
        try:
            db = scrdb.ScrDb(fields, "key_%d" % n, **kw)
            data = db.manifest_bytes()
            lua = CORE.manifest_bytes(db._lua_in, os_time=db.build_id, os_date=db.generated)
            doc = json.loads(data.decode("utf-8"))
            ok = data == lua and doc["field_hash"] == db.field_hash and doc["build_id"] == kw["build_id"]
            ok = ok and [f["id"] for f in doc["fields"]] == db.ids and doc["layout_version"] == CORE.layout
        except Exception as e:  # noqa: BLE001
            ok = False
            print("  [오류] manifest %d: %r" % (n, e))
        ck.true("manifest %d" % n, ok)
        sync._buses[:] = []
    # 파일로 쓰기·보관 이름
    db = scrdb.ScrDb([scrdb.arr("Gold", 0)], "My Map!", humans=2, xfer_base=0x58F678, xfer_stride=4, build_id=77,
                     generated="2026-09-17 00:00:00", name="mjw")
    path = db.write_manifest(os.path.join(WORK, "m", "man.json"))
    with open(path, "rb") as f:
        ck.eq("write_manifest bytes", f.read(), db.manifest_bytes())
    dst = scrdb.stash_manifest(path, os.path.join(WORK, "m", "store"))
    ck.eq("stash name", os.path.basename(dst), "My_Map__%08X.json" % db.field_hash)
    ck.eq("default manifest path", os.path.basename(scrdb.default_manifest_path("a b")), "SCR_DB_manifest_a_b.json")
    sync._buses[:] = []


# =============================================================================================
# 3. 설정 검사
# =============================================================================================

GOOD = dict(humans=4, xfer_base=0x58F678, xfer_stride=500, slot_base=0x5934F8, slot_stride=101, build_id=5)


def _mk(fields=None, key="k", **kw):
    keep = kw.get("bus")
    sync._buses[:] = [keep] if keep is not None else []  # 설정마다 같은 채널 줄을 새 버스에 넣는다
    args = dict(GOOD)
    args.update(kw)
    args.setdefault("name", "e%d" % len(sync._buses))
    return scrdb.ScrDb(fields if fields is not None else [scrdb.arr("a", 0), scrdb.var("b", 0)], key, **args)


def section_setup_errors():
    fresh()
    db = _mk()
    ck.eq("defaults", (db.channels, db.msqc_addr, db.msqc_death, db.max_players, db.slot_count, db.anchor_base,
                       db.key_mode, db.dup_names), (8, 0x58F508, 21, 8, 1, 0x594198, "ordinal", []))
    ck.eq("bus lines", db.bus.eds_lines(), sync.scrdb_msqc_lines())
    ck.eq("regions", db._regions["anchor"], (0x594198, 0x594198 + 168 * 4))
    ck.eq("field addr", (db.field_addr("a", 2), db.field_addr("b", 3), db.field_epd("a", 0)),
          (0x58F678 + (2 * 500 + 0) * 4, 0x5934F8 + (3 * 101 + 0) * 4, (0x58F678 - 0x58A364) // 4))
    ck.eq("key_of", (db.key_of("a"), db.key_of("b")), (0, 1))
    lua_rejects = [
        ("humans 0", dict(humans=0)),
        ("humans 9", dict(humans=9)),
        ("channels 0", dict(channels=0)),
        ("channels 9", dict(channels=9)),
        ("key mode", dict(key_mode="name")),
        ("anchor over msqc", dict(anchor=0x58F400)),
    ]
    for label, kw in lua_rejects:
        ck.raises("lua rejects " + label, EudextError, _mk, **kw)
    ck.raises("index key with var field (eudext)", EudextError, _mk, key_mode="index")
    lua_idx = CORE.setup(dict(db._lua_in, KeyMode="index"))  # Lua 는 받는다 (and/or 로 순번이 된다) — 런처가 멈추는 조합
    ck.eq("lua accepts index+var", lua_idx["KeyMode"], "index")
    ck.raises("lua rejects big key", EudextError, _mk, [scrdb.arr("a", 0xFFFD)], key_mode="index",
              xfer_stride=1, allow_outside_mirror=True)
    ok_idx = _mk([scrdb.arr("a", 0xFFFC)], key_mode="index", xfer_stride=1, allow_outside_mirror=True)
    ck.eq("index key max ok", ok_idx.key_of("a"), 0xFFFC)
    try:
        _mk(humans=9)
    except EudextError as e:
        ck.true("lua message kept", "Humans=9 (1..8)" in str(e), str(e))
    # eudext 추가 검사
    ck.raises("layout mismatch", EudextError, _mk, layout=6)
    ck.eq("layout ok", _mk(layout=7).core.layout, 7)
    ck.raises("no fields", EudextError, _mk, [])
    ck.raises("too many fields", EudextError, _mk, [scrdb.arr("f%d" % i, i) for i in range(4097)])
    ck.raises("stride 0", EudextError, _mk, xfer_stride=0)
    ck.raises("anchor outside mirror", EudextError, _mk, anchor=0x5A0000)
    ck.raises("values outside mirror", EudextError, _mk, xfer_base=0x59F000)
    ck.raises("anchor over values", EudextError, _mk, anchor=0x58F700)
    ck.raises("arr needs xfer", EudextError, _mk, xfer_base=None)
    ck.raises("var needs slot", EudextError, _mk, slot_base=None)
    ck.raises("deaths custom xfer", EudextError, _mk, [scrdb.deaths("d", 4), scrdb.arr("a", 0)])
    dd = _mk([scrdb.deaths("d", 4), scrdb.deaths("e", 6)], key_mode="index", xfer_base=None, xfer_stride=None,
             slot_base=None, slot_stride=None)
    ck.eq("deaths defaults", (dd.xfer_base, dd.xfer_stride, dd.slot_base, dd.slot_stride, dd.key_of("e")),
          (0x58A364, 1, 0x58A364, 1, 72))
    ck.raises("save key", EudextError, _mk, key="")
    ck.raises("build id range", EudextError, _mk, build_id=0x7FFFFFFF)
    ck.raises("bad field mode", EudextError, scrdb.Field, "x", "obj", index=0)
    ck.raises("bad field index", EudextError, scrdb.arr, "x", -1)
    ck.raises("field extra id", EudextError, scrdb.arr, "x", 0, id="y")
    ck.raises("fields eudarray", EudextError, _mk, EUDArray(2))
    ck.raises("bus nsqc", EudextError, _mk, bus=sync.Bus("nsqc", name="nb", deaths=[300]))
    ck.raises("bus + qc_unit", EudextError, _mk, bus=sync.Bus("msqc", name="mb"), qc_unit=49)
    ck.eq("field from dict/tuple", [f.pos for f in _mk([{"name": "a", "mode": "arr", "index": 3, "id": "z"},
                                                        ("b", "var", 4)]).fields], [3, 4])
    # 맵이 작으면 20비트 워드가 안 실린다 (MSQC val 범위)
    chk = GetChkTokenized()
    dim = chk.getsection("DIM")
    try:
        chk.setsection("DIM", struct.pack("<HH", 20, 20) + bytes(dim[4:]))
        ck.raises("map too small", EudextError, _mk)
        chk.setsection("DIM", struct.pack("<HH", 64, 64) + bytes(dim[4:]))
        ck.eq("64x64 ok", _mk().core.layout, 7)
    finally:
        chk.setsection("DIM", dim)
    # humans 기본값 = 가장 큰 사람 번호 + 1
    fresh(humans=[0, 2, 5])
    ck.eq("humans from map", _mk(humans=None).humans, 6)
    # setup 두 번
    fresh()
    scrdb.setup([scrdb.arr("a", 0)], "k", **GOOD)
    ck.raises("setup twice", EudextError, scrdb.setup, [scrdb.arr("a", 0)], "k", **GOOD)
    ck.true("current/declared", scrdb.current() is scrdb.declared())
    fresh()
    ck.raises("current none", EudextError, scrdb.current)
    ck.true("declared none", scrdb.declared() is None)
    # NSQC 버스의 출력 데스 유닛이 채널과 겹치면
    sync._buses[:] = []
    nb = sync.Bus("nsqc", name="nq", deaths=[23])
    nb.key_press("A")
    args = dict(GOOD, name="nqx")
    ck.raises("nsqc death overlap", EudextError, scrdb.ScrDb, [scrdb.arr("a", 0)], "k", **args)
    fresh()


# =============================================================================================
# 4~6. 수신기·표지 블록·알림음 차등 (에뮬레이터 대 Lua 트리)
# =============================================================================================

LOGSIZE = 400


class Rig:
    """db + 기록 쓰기 함수 + 에뮬레이터 프로그램."""

    def __init__(self, db, write_kind="default", guard_var=None, close_addr=None):
        self.db = db
        self.close_addr = close_addr
        self.logn = EUDVariable()
        self.log = EUDArray(LOGSIZE)
        self.guard_var = guard_var
        log_epd = _compat.eudarray_epd(self.log)
        guard = (lambda: [guard_var.Exactly(0)]) if guard_var is not None else None
        writer = db.default_writer(guard)

        def logger(p, key, val):
            DoActions(SetMemoryEPD(log_epd + self.logn, SetTo, p), self.logn.AddNumber(1))
            DoActions(SetMemoryEPD(log_epd + self.logn, SetTo, key), self.logn.AddNumber(1))
            DoActions(SetMemoryEPD(log_epd + self.logn, SetTo, val), self.logn.AddNumber(1))
            writer(p, key, val)

        if write_kind == "eudfunc":
            @EUDFunc
            def efw(p, key, val):
                logger(p, key, val)

            self.write = efw
        else:
            self.write = logger

    def body(self):
        self.db.frame(self.write)
        if self.close_addr is not None:
            self.db.close_load(Memory(self.close_addr, Exactly, 1))

    def build(self):
        prog = emu.Program(self.body)
        prog.watch("logn", self.logn)
        prog.watch("log", _compat.eudarray_addr(self.log))
        for name in ("ready", "saved", "activity"):
            prog.watch(name, _compat.eudarray_addr(getattr(self.db, name)))
        if self.guard_var is not None:
            prog.watch("guard", self.guard_var)
        self.prog = prog
        self.m = prog.build()
        self.pristine = self.m.snapshot()
        return self.m

    def start(self, local_player, humans, prefill=None):
        m = self.m
        m.restore(self.pristine)
        m.ends.clear()
        scmodel.install(m, local_player=local_player, players=["human" if p in humans else "computer" for p in range(8)],
                        text=True)
        if prefill:
            for a, v in prefill.items():
                m.setdw(a, v)
        return m

    def writes(self):
        n = self.m.var("logn")
        base = self.m.addr("log")
        vals = [self.m.dw(base + 4 * j) for j in range(n)]
        self.m.set_var("logn", 0)
        return [tuple(vals[j:j + 3]) for j in range(0, n, 3)]

    def flags(self, name):
        base = self.m.addr(name)
        return [self.m.dw(base + 4 * i) for i in range(8)]


class WordGen:
    """채널 칸마다 프로토콜 워드(키 → 하위 → 상위, 토글 번갈아)와 섞인 무작위 워드."""

    def __init__(self, rng, core, keys, channels, humans):
        self.rng = rng
        self.c = core
        self.keys = list(keys)
        self.state = {(k, i): [0, core.toggle_a, 0] for k in range(channels) for i in range(humans)}

    def word(self, k, i):
        rng, c = self.rng, self.c
        st = self.state[(k, i)]
        r = rng.random()
        if r < 0.45:
            return 0
        if r < 0.80:
            phase, tog, _last = st
            if phase == 0:
                pay = rng.choice(self.keys + [c.word_ready, c.word_saved]) if rng.random() < 0.9 else rng.randrange(65536)
                tag = c.tag_key
            elif phase == 1:
                pay, tag = rng.randrange(65536), c.tag_lo
            else:
                pay, tag = rng.randrange(65536), c.tag_hi
            w = tog | tag | pay
            st[0] = (phase + 1) % 3 if rng.random() < 0.9 else rng.randrange(3)
            st[1] = c.toggle_b if tog == c.toggle_a else c.toggle_a
            st[2] = w
            return w
        if r < 0.88:
            return st[2]  # 같은 워드 다시 (토글이 같아 무시돼야 한다)
        w = rng.choice([c.toggle_a, c.toggle_b, c.toggle_a | c.toggle_b, 0])
        w |= rng.choice([c.tag_key, c.tag_lo, c.tag_hi, c.tag_mask]) | rng.randrange(65536)
        if rng.random() < 0.3:
            w |= rng.randrange(1, 0x1000) << 20
        return w


def run_diff(label, rig, humans, local_player, cycles, seed, notify_codes, guard_flip=False, check_fields=True):
    """에뮬레이터(rig)와 Lua 트리(LuaFrame)를 같은 입력으로 cycles 사이클 돌려 비교한다. 반환: 실패 수."""
    db, c = rig.db, rig.db.core
    rng = random.Random(seed)
    close = None
    if rig.close_addr is not None:
        close = [lc.Term("Memory", rig.close_addr, lc.TEP_CONSTS["Exactly"], 1)]
    lf = ref_scrdb.LuaFrame(c, db._lua_in, db.build_id, close_load=close)
    prefill = {db.anchor_base + 4 * i: rng.getrandbits(32) for i in range(c.total)}
    m = rig.start(local_player, humans, prefill)
    lmem = dict(prefill)
    lmem[0x512684] = local_player
    keys = [db.key_of(f) for f in db.fields]
    gen = WordGen(rng, c, keys, db.channels, db.humans)
    expect_fields = {}
    fails = 0
    notify_addr = db.addr(c.notify_index)
    sounds_seen = 0
    stats = {"writes": 0}
    for cyc in range(cycles):
        for k in range(db.channels):
            for i in range(8):
                w = gen.word(k, i) if i < db.humans else 0
                a = scrdb.DEATHS_BASE + 4 * db.death_epd(k, i)
                m.setdw(a, w)
                lmem[a] = w
        if rng.random() < 0.15:
            code = rng.choice(notify_codes)
            m.setdw(notify_addr, code)
            lmem[notify_addr] = code
        if rig.close_addr is not None and rng.random() < 0.1:
            v = rng.choice([0, 1, 2])
            m.setdw(rig.close_addr, v)
            lmem[rig.close_addr] = v
        gate = 0
        if guard_flip:
            gate = 1 if rng.random() < 0.3 else 0
            m.set_var("guard", gate)
        nrec = len(m.text_model.records)
        try:
            m.cycle()
        except Exception as e:  # noqa: BLE001
            ck.true("%s cycle %d" % (label, cyc), False, repr(e))
            return fails + 1
        lf.cycle(lmem)
        problems = []
        got_anchor = [m.dw(db.anchor_base + 4 * i) for i in range(c.total)]
        want_anchor = [lmem.get(db.anchor_base + 4 * i, 0) for i in range(c.total)]
        if got_anchor != want_anchor:
            diff = [(i, hex(g), hex(w)) for i, (g, w) in enumerate(zip(got_anchor, want_anchor)) if g != w]
            problems.append("anchor %r" % diff[:6])
        for name, lname in (("ready", "LauncherReady"), ("saved", "SaveDone"), ("activity", "Activity")):
            got = rig.flags(name)
            want = [lf.flag(lname, i) for i in range(8)]
            if got != want:
                problems.append("%s %r != %r" % (name, got, want))
        gw = rig.writes()
        stats["writes"] += len(lf.writes)
        if gw != lf.writes:
            problems.append("writes %r != %r" % (gw[:4], lf.writes[:4]))
        heard = [r.text for r in m.text_model.records[nrec:] if r.kind == "wav" and r.cp == local_player]
        want_heard = [s for cp, s in lf.sounds if cp == local_player]
        sounds_seen += len(want_heard)
        if heard != want_heard:
            problems.append("sounds %r != %r" % (heard, want_heard))
        if check_fields and gate == 0:
            for p, key, val in lf.writes:
                if db.key_mode == "ordinal":
                    if key < len(db.fields):
                        expect_fields[db.field_addr(key, p)] = val
                else:
                    hit = [f for f in db.fields if f.index == key]
                    if hit:
                        expect_fields[db.field_addr(hit[0], p)] = val
        if check_fields:
            bad = {hex(a): (hex(m.dw(a)), hex(v)) for a, v in expect_fields.items() if m.dw(a) != v}
            if bad:
                problems.append("fields %r" % list(bad.items())[:4])
        if problems:
            fails += 1
        if fails <= 3 or not problems:
            ck.true("%s P%d 사이클 %d" % (label, local_player, cyc), not problems, "; ".join(problems))
    print("  %s 로컬 P%d: 쓰기 %d, 들린 소리 %d, 받은 워드 %d, 준비 %s, 저장 완료 %s" % (
        label, local_player, stats["writes"], sounds_seen,
        sum(m.dw(db.msqc_count_addr(k, i)) for k in range(db.channels) for i in range(db.humans)),
        rig.flags("ready")[: db.humans], rig.flags("saved")[: db.humans]))
    ck.true("%s exercised (P%d)" % (label, local_player), stats["writes"] > 0)
    return sounds_seen


def section_receiver():
    # C1: DPS 모양 — 사람 4, 채널 8, ordinal, arr+var 섞임, 기본 쓰기 함수
    fresh(humans=[0, 1, 2, 3])
    fields = [scrdb.arr("Gold", 0), scrdb.arr("Gold", 7), scrdb.var("Lv", 0), scrdb.arr("Big", 3), scrdb.var("St", 5)]
    db = scrdb.setup(fields, "C1", xfer_base=0x58F678, xfer_stride=500, slot_base=0x5934F8, slot_stride=101,
                     build_id=123456, qc_unit=49)
    ck.eq("C1 dup ids", db.ids, ["Gold#arr0", "Gold#arr7", "Lv", "Big", "St"])
    rig = Rig(db)
    rig.build()
    heard = 0
    for lp, seed in ((0, 1), (3, 2), (128, 3)):
        heard += run_diff("C1 수신기", rig, [0, 1, 2, 3], lp, 150, seed, [0, 1, 2, 3, 4, 5, 9])
    ck.true("C1 sounds exercised", heard > 0, heard)
    steps = [n for n, _t in rig.m.ends[-20:]]
    print("  C1 사이클 실행 트리거 수(마지막 20):", steps)
    # 1회 블록·로컬 칸·시그니처 (C1 빌드 재사용)
    section_anchor_local(rig)
    # C2: MSF 모양 — 사람 7, 채널 3, 다른 채널 자리, index 키, 데스 항목, EUDFunc 쓰기, 조건(guard)
    fresh(humans=list(range(7)))
    units = [4, 6, 24, 11, 18, 35, 36, 37]
    fields = [scrdb.deaths("F%d" % u, u) for u in units]
    gv = EUDVariable()
    db = scrdb.setup(fields, "C2", key_mode="index", anchor=0x593800, channels=3, msqc_addr=0x593F00, msqc_death=182,
                     build_id=99, qc_unit=49)
    ck.eq("C2 bus lines", db.bus.eds_lines(), ["QCUnit : 49"] + scrdb.msqc_lines(0x593F00, 182, 3))
    rig = Rig(db, write_kind="eudfunc", guard_var=gv)
    rig.build()
    for lp, seed in ((6, 11), (0, 12)):
        run_diff("C2 수신기", rig, list(range(7)), lp, 120, seed, [0, 1, 4, 6], guard_flip=True)
    # C3: 사람 1, 채널 1
    fresh(humans=[0])
    db = scrdb.setup([scrdb.arr("x", 0)], "C3", xfer_base=0x58F678, xfer_stride=1, channels=1, build_id=1, qc_unit=49)
    rig = Rig(db, close_addr=0x58F800)
    rig.build()
    run_diff("C3 수신기", rig, [0], 0, 200, 21, [0, 3])
    m = rig.start(0, [0])
    m.cycle()
    lo = m.dw(db.addr("LoadOpen"))
    m.setdw(0x58F800, 1)
    m.cycle()
    ck.eq("close_load", (lo, m.dw(db.addr("LoadOpen"))), (1, 0))
    ck.eq("C3 sites", db.channels * db.humans, 1)
    section_modified_core()


def section_anchor_local(rig):
    db, c, m = rig.db, rig.db.core, rig.m
    humans = [0, 1, 2, 3]
    # 1회 블록 순서: 0 초기화 → 헤더 → 시그니처 마지막, 수신기는 그 뒤 (첫 사이클에 온 워드도 센다)
    m = rig.start(0, humans, {db.anchor_base + 4 * i: 0xDEADBEEF for i in range(c.total)})
    writes = []
    orig = m.setdw

    def rec(addr, v, orig=orig):
        if db.anchor_base <= addr < db.anchor_base + 4 * c.total:
            writes.append(((addr - db.anchor_base) // 4, v & M32))
        orig(addr, v)

    m.setdw = rec
    m.setdw(scrdb.DEATHS_BASE + 4 * db.death_epd(0, 1), A | c.tag_key | 3)
    writes.clear()
    m.cycle()
    once = [x for trig in c.anchor_once for x in trig]
    got_once = writes[: len(once)]
    ck.eq("1-shot order", [i for i, _v in got_once], [i for i, _m, _s in once])
    ck.eq("1-shot zero first", [v for _i, v in got_once[: c.total]], [0] * c.total)
    ck.eq("1-shot sig last", got_once[-8:], [(i, c.magic[i]) for i in range(8)])
    after = writes[len(once):]
    ck.eq("every-cycle then receiver", [i for i, _v in after],
          [c.index["LocalPlayer"], c.index["Seq"], c.index["MsqcCount"] + db.slot(0, 1)] + [c.index["MsqcEcho"] + db.slot(0, 1)] * 2)
    ck.eq("echo masked", m.dw(db.msqc_echo_addr(0, 1)), c.tag_key | 3)
    ck.eq("first-cycle word counted", m.dw(db.msqc_count_addr(0, 1)), 1)
    writes.clear()
    m.setdw(scrdb.DEATHS_BASE + 4 * db.death_epd(0, 1), 0)
    m.cycle()
    ck.eq("second cycle no zeroing", [i for i, _v in writes], [c.index["LocalPlayer"], c.index["Seq"]])
    ck.eq("seq counts", m.dw(db.addr("Seq")), 2)
    m.setdw = orig
    del m.setdw
    # 헤더 값
    want = {"Version": c.layout, "Build": db.build_id, "Self": db.anchor_base, "XferBase": db.xfer_base,
            "XferStride": db.xfer_stride, "SlotBase": db.slot_base, "SlotStride": db.slot_stride, "MaxPlayers": 8,
            "SlotCount": db.slot_count, "FieldCount": len(db.fields), "FieldHash": db.field_hash, "Humans": 4,
            "MsqcAddr": db.msqc_addr, "MsqcChannels": db.channels, "LoadOpen": 1, "Ready": 0, "Notify": 0}
    ck.eq("header values", {k: m.dw(db.addr(k)) for k in want}, want)
    # 시그니처 8 dword 가 페이로드에 연속으로 없다 (c)
    sig = struct.pack("<8I", *c.magic)
    ck.true("signature not contiguous in payload", sig not in dword_bytes(m))
    ck.true("signature parts present", all(struct.pack("<I", x) in dword_bytes(m) for x in c.magic))
    # LocalPlayer: 이 PC 번호 + 1, 관전자는 0
    for lp in (0, 1, 2, 3, 5, 7, 128, 131):
        m = rig.start(lp, humans)
        m.cycle(2)
        ck.eq("local player slot P%d" % lp, m.dw(db.addr("LocalPlayer")), lp + 1 if lp < 8 else 0)
    # (f) 로컬 칸이 공유 칸을 건드리지 않는다: 두 클라이언트(P0, P1)에 같은 워드를 주고 P0 에만 알림 코드를 쓴다
    rng = random.Random(77)
    script = []
    for cyc in range(40):
        ws = {(k, i): (rng.choice([0, 0, A | c.tag_key | 1, B | c.tag_lo | 2, A | c.tag_hi | 3])) for k in range(8)
              for i in range(4)}
        note = rng.choice([0, 0, 1, 2, 3, 4, 7]) if cyc % 3 == 0 else None
        script.append((ws, note))
    snaps = {}
    for lp, with_note in ((0, False), (1, False), (0, True)):
        m = rig.start(lp, humans)
        for ws, note in script:
            for (k, i), w in ws.items():
                m.setdw(scrdb.DEATHS_BASE + 4 * db.death_epd(k, i), w)
            if with_note and note is not None:
                m.setdw(db.addr("Notify"), note)
            m.cycle()
        rig.writes()
        snaps[(lp, with_note)] = dict(m.mem)
    anchor = range(db.anchor_base, db.anchor_base + 4 * c.total)

    def diff(x, y):
        keys = set(x) | set(y)
        return {a for a in keys if x.get(a, 0) != y.get(a, 0)}

    base_local = diff(snaps[(0, False)], snaps[(1, False)])  # eudplib 이 원래 로컬 값으로 두는 칸 + LocalPlayer
    with_note = diff(snaps[(0, True)], snaps[(1, False)])
    extra = sorted(hex(a) for a in with_note - base_local if a not in anchor and a != 0x6509B0)
    ck.eq("notify touches only anchor/local", extra, [])
    ck.eq("notify vs no-notify same shared state",
          sorted(hex(a) for a in diff(snaps[(0, True)], snaps[(0, False)]) if a not in anchor), [])
    ck.true("local diff exists (sanity)", db.addr("LocalPlayer") in base_local)


def section_modified_core():
    """레이아웃 값을 바꾼 Lua 코어 사본으로 빌드해도 Lua 모델과 같다 → 파이썬에 적힌 값이 없다 (a)."""
    with open(CORE.path, encoding="utf-8") as f:
        text = f.read()
    reps = [
        ("Seq = 18,", "Seq = 167,"),
        ("0x53435244, 0x425F3031", "0x11111111, 0x22222222"),
        ("SCRDB_TOGGLE_A = 0x40000", "SCRDB_TOGGLE_A = 0x80000"),
        ("SCRDB_TOGGLE_B = 0x80000", "SCRDB_TOGGLE_B = 0x40000"),
        ("SCRDB_TAG_KEY = 0x00000", "SCRDB_TAG_KEY = 0x20000"),
        ("SCRDB_TAG_HI = 0x20000", "SCRDB_TAG_HI = 0x00000"),
        ("SCRDB_WORD_READY = 0xFFFE", "SCRDB_WORD_READY = 0xFFF0"),
        ("SCRDB_WORD_SAVED = 0xFFFD", "SCRDB_WORD_SAVED = 0xFFF1"),
        ('{1, "sound\\\\Misc\\\\ZRescue.wav"}', '{7, "sound\\\\Misc\\\\ZRescue.wav"}'),
        ("SetMemory(SCRDB_Addr(SCRDB_I.LoadOpen),     SetTo, 1)", "SetMemory(SCRDB_Addr(SCRDB_I.LoadOpen),     SetTo, 2)"),
        ("Notify = 152,", "Notify = 167 - 1,"),
    ]
    missing = [a for a, _b in reps if a not in text]
    ck.eq("modified core patterns", missing, [])
    for a, b in reps:
        text = text.replace(a, b, 1)
    text = text.replace("LoadOpen = 166,", "LoadOpen = 152,")  # Notify 를 166 으로 옮긴 자리
    d = os.path.join(WORK, "core_mod")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "SCR_DB_Core.lua")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    mc = lc.scrdb_core(path, quiet=True)
    ck.eq("modified values", (mc.index["Seq"], mc.index["Notify"], mc.index["LoadOpen"], mc.magic[0], mc.toggle_a,
                              mc.tag_key, mc.word_ready, [x[0] for x in mc.notify]),
          (167, 166, 152, 0x11111111, 0x80000, 0x20000, 0xFFF0, [7, 2, 3, 4]))
    ck.true("modified digest differs", mc.receiver_digest != scrdb.RECEIVER_DIGEST)
    fresh(humans=[0, 1])
    db = scrdb.setup([scrdb.arr("a", 0), scrdb.var("b", 1)], "MOD", xfer_base=0x58F678, xfer_stride=8,
                     slot_base=0x58F778, slot_stride=4, channels=2, build_id=31337, core=path, qc_unit=49)
    ck.true("db uses modified core", db.core is mc)
    rig = Rig(db)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        rig.build()
    ck.true("digest warning", any("SCRDB_Receiver" in str(x.message) for x in w), [str(x.message)[:80] for x in w])
    run_diff("바꾼 코어 수신기", rig, [0, 1], 1, 150, 41, [0, 2, 7, 1, 4, 3])
    m = rig.start(0, [0, 1])
    m.cycle(3)
    ck.eq("modified anchor", (m.dw(db.addr(167)), m.dw(db.addr(152)), m.dw(db.anchor_base), m.dw(db.addr("LoadOpen"))),
          (3, 2, 0x11111111, 2))


# =============================================================================================
# 7. MSQC.py 실제 수신 코드 + 런처 모델 + 턴 모델
# =============================================================================================


def section_msqc_e2e():
    humans = [0, 1, 2]
    fresh(humans=humans)
    bus = sync.Bus("msqc", qc_unit=49, debug=False, name="e2e")
    fields = [scrdb.arr("f%d" % n, n) for n in range(10)] + [scrdb.var("v%d" % n, n) for n in range(5)]
    db = scrdb.setup(fields, "E2E", xfer_base=0x58F678, xfer_stride=16, slot_base=0x58F800, slot_stride=8, bus=bus,
                     build_id=2024)
    req = EUDVariable()
    settings = settings_of(sync.eds_sections()["MSQC"])
    m_mod = load_plugin(MSQC_PY, "MSQC", settings)
    ck.eq("e2e humans", m_mod.humans, humans)
    ck.eq("e2e qc count", m_mod.QCCount, 8)

    def body():
        m_mod.beforeTriggerExec()
        db.frame()
        for p in humans:
            RawTrigger(conditions=req.Exactly(p + 1), actions=[db.save_signal(p), req.SetNumber(0)])
        m_mod.afterTriggerExec()

    prog = emu.Program(body, setup=m_mod.onPluginStart)
    prog.watch("req", req)
    for name in ("ready", "saved"):
        prog.watch(name, _compat.eudarray_addr(getattr(db, name)))
    try:
        mach = prog.build()
    finally:
        unload_plugin("MSQC")
    scmodel.install_game_memory(mach, local_player=0, players=["human" if p in humans else "computer" for p in range(8)])
    qc = QCUnits(mach, m_mod, humans)
    mach.cycle()
    ck.true("e2e qc units", mach.dw(0x628438) == qc.expected_head() and qc.all_reset())
    rng = random.Random(9)
    c = db.core
    for latency, turn, corrupt in ((2, 1, 0.0), (3, 2, 0.04)):
        launchers = {}
        want = {}
        for p in (0, 2):  # P2(1번)는 런처 없음
            L = ref_scrdb.LauncherModel(c, db.anchor_base, p, db.channels)
            items = []
            for n, f in enumerate(db.fields):
                v = rng.choice([0, 1, 0xFFFF, 0x10000, M32, rng.getrandbits(32)])
                items.append((db.key_of(f), db.field_addr(f, p), v))
                want[db.field_addr(f, p)] = v
            L.load(items)
            launchers[p] = L
        for f in db.fields:
            want.setdefault(db.field_addr(f, 1), mach.dw(db.field_addr(f, 1)))
        sim = TurnSim({k: k for k in range(db.channels)}, latency, turn)
        frame, corrupted = 0, 0
        while any(L.busy for L in launchers.values()) and frame < 4000:
            for p, L in launchers.items():
                sent = {k: v for k, v in L.frame(mach.dw).items() if v}
                if sent:
                    sim.send(frame, p, sent)
            for p, d in sim.execute(frame).items():
                for k, v in d.items():
                    if corrupt and rng.random() < corrupt:
                        v ^= 1 << rng.randrange(16)
                        corrupted += 1
                    qc.inject_value(humans.index(p), db.msqc_death + k, v)
            mach.cycle()
            frame += 1
        label = "e2e L%d T%d" % (latency, turn)
        ck.true(label + " finished", not any(L.busy for L in launchers.values()), frame)
        bad = {hex(a): (hex(mach.dw(a)), hex(v)) for a, v in want.items() if mach.dw(a) != v}
        ck.eq(label + " values", bad, {})
        ck.eq(label + " ready", [mach.dw(mach.addr("ready") + 4 * p) for p in range(3)], [1, 0, 1])
        ck.true(label + " waypoints", qc.all_reset())
        for p in (0, 2):
            cnt = [mach.dw(db.msqc_count_addr(k, p)) for k in range(db.channels)]
            ck.true(label + " toggle parity P%d" % p, all(launchers[p].toggle[k] == (A if n % 2 == 0 else B)
                                                           for k, n in enumerate(cnt)), cnt)
        if corrupt:
            ck.true(label + " corruption resent", corrupted > 0 and sum(L.resent for L in launchers.values()) > 0,
                    (corrupted, [L.resent for L in launchers.values()]))
        print("  %s: %d 프레임, 다시 보냄 %s, 깨짐 %d, 로그 %s" % (label, frame, [L.resent for L in launchers.values()],
                                                        corrupted, [L.log for L in launchers.values()]))
        for p in range(3):  # 다음 판을 위해 준비 표시를 내린다
            mach.setdw(mach.addr("ready") + 4 * p, 0)
    # 저장: 맵이 P0 의 저장 신호를 올린다 → 런처가 알아채고 저장 완료 워드 → 맵의 save_done
    L = ref_scrdb.LauncherModel(c, db.anchor_base, 0, db.channels)
    seq0 = mach.dw(db.addr(c.index["SaveSeqP"] + 0))
    mach.set_var("req", 1)
    mach.cycle()
    ck.eq("save signal", (mach.dw(db.addr(c.index["SaveSeqP"] + 0)) - seq0, mach.dw(db.addr(c.index["SaveSeqP"] + 2))),
          (1, 0))
    L.saved()
    sim = TurnSim({k: k for k in range(db.channels)}, 2, 1)
    frame = 0
    while L.busy and frame < 200:
        sent = {k: v for k, v in L.frame(mach.dw).items() if v}
        if sent:
            sim.send(frame, 0, sent)
        for p, d in sim.execute(frame).items():
            for k, v in d.items():
                qc.inject_value(humans.index(p), db.msqc_death + k, v)
        mach.cycle()
        frame += 1
    ck.eq("save done flag", [mach.dw(mach.addr("saved") + 4 * p) for p in range(3)], [1, 0, 0])


# =============================================================================================
# 8. edsgen·훅
# =============================================================================================


def section_edsgen():
    fresh()
    db = scrdb.setup([scrdb.arr("a", 0)], "EG", xfer_base=0x58F678, xfer_stride=4, build_id=9, qc_unit=49)
    doc = edsgen.EdsDoc("base.scx", "out.scx")
    ck.raises("add_scrdb no boot", edsgen.EdsError, doc.add_scrdb)
    doc.boot(eudext_root=REPO, preload=["i64"])
    ck.raises("add_scrdb no venv", edsgen.EdsError, doc.add_scrdb)
    doc = edsgen.EdsDoc("base.scx", "out.scx")
    doc.boot(eudext_root=REPO, preload=["i64"], venv_site=VENV_SITE)
    doc.add_sync(hook=True)
    sec = doc.add_scrdb(core=CORE.path, build_id=9, manifest="m.json", frame=False)
    doc.add_plugin("main.eps")
    names = [s.name for s in doc.sections()]
    ck.eq("eds order", names[2:], ["MSQC", "eudext_sync_hook.py", "eudext_scrdb_hook.py", "main.eps"])
    ck.eq("boot preload", dict(doc.boot_sec.items)["Preload"], "i64, scrdb")
    ck.eq("hook settings", sec.items, [("Core", CORE.path), ("BuildId", "9"), ("Manifest", os.path.abspath("m.json")),
                                       ("Frame", "0")])
    msqc = [s for s in doc.sections() if s.name == "MSQC"][0]
    ck.eq("msqc lines once", [k for k, _v in msqc.items], ["QCUnit : 49"] + sync.scrdb_msqc_lines())
    ck.eq("hook file", doc.extra_files["eudext_scrdb_hook.py"], scrdb.hook_source())
    ck.raises("hook twice", edsgen.EdsError, doc.add_scrdb)
    out = os.path.join(WORK, "eds_gen", "x.eds")
    doc.write(out)
    ck.true("hook written", os.path.isfile(os.path.join(os.path.dirname(out), "eudext_scrdb_hook.py")))
    doc2 = edsgen.EdsDoc("base.scx", "out.scx")
    doc2.boot(eudext_root=REPO, venv_site=VENV_SITE)
    doc2.add_scrdb(db)
    doc2.add_plugin("main.eps")
    ck.eq("scrdb without sync hook", [s.name for s in doc2.sections()][2:], ["MSQC", "eudext_scrdb_hook.py", "main.eps"])
    # 훅 동작: frame 은 훅만, 맵 호출은 아무것도 내지 않음, 직접 내면 오류
    scrdb.hook_loaded({"core": CORE.path, "BuildId": "0x10", "manifest": "", "FRAME": "1"})
    ck.eq("hook parsed", (scrdb._hook["active"], scrdb._hook["build_id"], scrdb._hook["manifest"], scrdb._hook["frame"]),
          (True, 16, None, True))
    s = Suite("t_scrdb_hook", verbose=False)
    emitted = []

    @s.case("map_frame_noop")
    def _(t):
        n0 = _trig_count()
        db.frame()
        emitted.append(_trig_count() - n0)

    @s.case("map_anchor", expect_build_error=EudextError, expect_message="훅")
    def _(t):
        db.anchor()

    s.build()
    ck.eq("map frame no-op under hook", (emitted, s.cases["map_frame_noop"].build_error), ([0], None))
    ok = s.report()
    ck.true("hook suite", ok)
    scrdb.hook_reset()
    # 훅 플러그인 파일을 euddraft 처럼 불러와 에뮬레이터로: 훅이 frame 을 내고 매니페스트를 쓴다
    fresh(humans=[0, 1])
    hook_path = os.path.join(WORK, "eds_gen", "eudext_scrdb_hook.py")
    man = os.path.join(WORK, "eds_gen", "hook_manifest.json")
    if os.path.exists(man):
        os.remove(man)
    hook_mod = load_plugin(hook_path, "eudext_scrdb_hook", {"BuildId": "5", "Manifest": man})
    try:
        db = scrdb.setup([scrdb.arr("a", 0)], "HK", xfer_base=0x58F678, xfer_stride=4, qc_unit=49)
        ck.eq("hook build id", db.build_id, 5)
        counts = []

        def body():
            hook_mod.beforeTriggerExec()
            n0 = _trig_count()
            db.frame()  # 맵 쪽 호출 — 훅이 있으니 아무것도 내지 않는다
            counts.append(_trig_count() - n0)

        prog = emu.Program(body, setup=hook_mod.onPluginStart)
        m = prog.build()
    finally:
        unload_plugin("eudext_scrdb_hook")
    ck.true("hook wrote manifest", os.path.isfile(man) and open(man, "rb").read() == db.manifest_bytes())
    scmodel.install(m, local_player=1, players=["human", "human"])
    m.setdw(scrdb.DEATHS_BASE + 4 * db.death_epd(3, 1), A | 7)
    m.cycle(2)
    ck.true("module-level api", all(callable(getattr(scrdb, n)) for n in (
        "anchor", "receiver", "notify", "save_signal", "close_load", "write_manifest", "frame", "setup")))
    ck.eq("module save_signal", repr(scrdb.save_signal(1).fields[:6]), repr(db.save_signal(1).fields[:6]))
    ck.eq("hook frame emitted", (m.dw(db.anchor_base), m.dw(db.addr("LocalPlayer")), m.dw(db.addr("Seq")),
                                 m.dw(db.msqc_count_addr(3, 1)), counts), (CORE.magic[0], 2, 2, 1, [0]))
    scrdb.hook_reset()
    # 예제 eds 의 [MSQC] = 선언에서 만든 줄
    fresh()
    sync.collect(os.path.join(EXAMPLES, "scrdb_ingame.eps"), map_path=BASE_MAP)
    gen = sync.eds_sections()["MSQC"]
    static = [x for x in tbuild.read_eds(os.path.join(EXAMPLES, "scrdb_ingame.eds")) if x[0] == "MSQC"][0][1]
    ck.eq("example eds msqc = declarations", [edsgen.line_key(r) + " : " + (v or "") for _k, v, r in static],
          [edsgen.line_key(x) + " : " + x.split(" : ", 1)[1] for x in gen])
    order = [x[0] for x in tbuild.read_eds(os.path.join(EXAMPLES, "scrdb_ingame.eds"))]
    ck.eq("example eds order", order, ["main", "../boot.py", "MSQC", "dbg_setup.py", "scrdb_ingame.eps", "eudTurbo", "freeze"])
    ex = scrdb.current()
    ck.eq("example db", (ex.save_key, ex.humans, len(ex.fields), ex.key_mode, ex.manifest),
          ("eudext_scrdb_check", 1, 5, "ordinal", scrdb.default_manifest_path("eudext_scrdb_check")))
    # 플러그인 순서 검사 (4.18 (e))
    secs = ["main", "boot.py", "MSQC", "eudext_scrdb_hook.py", "map.eps"]
    scrdb._check_plugin_order(secs, caller="map")
    scrdb._check_plugin_order(secs, caller="eudext_scrdb_hook")
    ck.raises("order map before msqc", EudextError, scrdb._check_plugin_order,
              ["main", "boot.py", "..\\src\\map.eps", "MSQC"], caller="map")
    scrdb._check_plugin_order(["main", "other.py", "MSQC", "map.eps"], caller="map")
    scrdb._check_plugin_order(["main", "map.eps"], caller="map")  # [MSQC] 없음은 sync.verify 몫
    ck.true("order ok cases", True)
    fresh()


def _trig_count():
    from eudplib import GetTriggerCounter

    return GetTriggerCounter()


def section_flags():
    """표시 조건·액션·값 칸 주소를 상수·변수·CurrentPlayer 플레이어로 (에뮬레이터)."""
    fresh(humans=[0, 1, 2, 3])
    db = scrdb.setup([scrdb.arr("a", 3), scrdb.var("b", 1)], "FL", xfer_base=0x58F678, xfer_stride=16,
                     slot_base=0x58F800, slot_stride=8, build_id=3, qc_unit=49)
    s = Suite("t_scrdb_flags", verbose=False, memory={"players": ["human"] * 4})

    @s.case("flags")
    def _(t):
        p = t.var("p")
        for name in ("ready", "saved", "activity"):
            t.watch(name, _compat.eudarray_addr(getattr(db, name)))
        t.flag("r", db.launcher_ready(p))
        t.flag("s", db.save_done(p))
        t.flag("g", db.got_word(p))
        t.flag("r2", db.launcher_ready(2))
        DoActions(db.clear_ready(p), db.clear_word(p), db.save_signal(p))
        t.out("fe", db.field_epd("a", p))
        t.out("fa", db.field_addr("b", p))
        cp0 = f_getcurpl()
        f_setcurpl(p)
        t.flag("sc", db.save_done(CurrentPlayer))
        DoActions(db.clear_save_done(CurrentPlayer))
        f_setcurpl(cp0)

    s.build()
    m = s.machine
    for p in range(4):
        for on in (1, 0):
            s.reset()
            for name in ("ready", "saved", "activity"):
                m.setdw(m.addr("flags." + name) + 4 * p, on)
            m.setdw(m.addr("flags.ready") + 8, on)
            seq0 = m.dw(db.addr(CORE.index["SaveSeqP"] + p))
            r = s.run("flags", {"p": p})
            v = r.values
            got = (v.get("r"), v.get("s"), v.get("g"), v.get("r2"), v.get("fe"), v.get("fa"), v.get("sc"),
                   [m.dw(m.addr("flags." + n) + 4 * p) for n in ("ready", "saved", "activity")],
                   m.dw(db.addr(CORE.index["SaveSeqP"] + p)) - seq0, r.error)
            want = (on, on, on, on, db.field_epd("a", p), db.field_addr("b", p), on, [0, 0, 0], 1, None)
            ck.eq("flags P%d on=%d" % (p, on), got, want)
    ck.eq("field addr formula", (db.field_addr("a", 3), db.field_addr("b", 3)),
          (0x58F678 + (3 * 16 + 3) * 4, 0x58F800 + (3 * 8 + 1) * 4))
    ck.raises("flag bad player", EudextError, db.launcher_ready, 8)
    ck.raises("save_signal CurrentPlayer const", EudextError, db.save_signal, CurrentPlayer)
    fresh()


# =============================================================================================
# 9. 금지 조합 (IsPName 라이트 변수)
# =============================================================================================


def section_forbidden():
    fresh(humans=[0, 1])
    db = scrdb.setup([scrdb.arr("a", 0)], "FB", xfer_base=0x58F678, xfer_stride=4, build_id=1, qc_unit=49)
    ck.eq("no lightvar yet", _compat.pname_lightvar_units(), [])

    # A: 상수 플레이어·문자열 IsPName 은 라이트 변수를 쓰지 않는다 → 빌드 됨
    def body_a():
        if EUDIf()(IsPName(P1, "abc")):
            DoActions(SetMemoryEPD(0, SetTo, 0) if False else [])
        EUDEndIf()
        db.frame()

    try:
        emu.Program(body_a).build()
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = False
        print("  A:", repr(e))
    ck.true("const IsPName ok", ok and _compat.pname_lightvar_units() == [])

    # C: 수신기 뒤에 라이트 변수 IsPName → 빌드 끝 검사(주 함수 뒤)에서 오류
    def body_c():
        db.frame()
        if EUDIf()(IsPName(CurrentPlayer, "late")):
            pass
        EUDEndIf()

    try:
        emu.Program(body_c).build()
        err = None
    except EudextError as e:
        err = str(e)
    except Exception as e:  # noqa: BLE001
        err = "다른 오류 %r" % e
    ck.true("late IsPName build error", err is not None and "IsPName" in err and "msqc" in err, err)
    ck.eq("lightvar used", _compat.pname_lightvar_units(), [436])

    # B: 수신기 앞의 라이트 변수 IsPName → 수신기를 낼 때 오류 (빌드 오류 기대 케이스)
    s = Suite("t_scrdb_forbidden", verbose=False, memory={"players": ["human", "human"]})

    @s.case("ispname_then_frame", expect_build_error=EudextError, expect_message="IsPName")
    def _(t):
        t.flag("x", IsPName(CurrentPlayer, "early"))
        db.frame()

    @s.case("check_forbidden_direct", expect_build_error=EudextError, expect_message="겹칩니다")
    def _(t):
        scrdb.check_forbidden(db)

    s.build()
    ck.true("forbidden suite", s.report())

    # D: 채널을 옮기면(MSF 자리) 라이트 변수 칸과 겹치지 않아 빌드 됨
    fresh(humans=[0, 1])
    db2 = scrdb.setup([scrdb.deaths("a", 4)], "FB2", key_mode="index", anchor=0x593800, msqc_addr=0x593F00,
                      msqc_death=182, build_id=2, qc_unit=49)

    def body_d():
        if EUDIf()(IsPName(CurrentPlayer, "moved")):
            pass
        EUDEndIf()
        db2.frame()

    try:
        emu.Program(body_d).build()
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = False
        print("  D:", repr(e))
    ck.true("moved channels + IsPName ok", ok)
    fresh()


# =============================================================================================
# 10. epScript 예제·euddraft 빌드
# =============================================================================================


def repo_artifacts():
    found = []
    for dirpath, dirnames, filenames in os.walk(PKG):
        rel = os.path.relpath(dirpath, PKG)
        if rel.startswith("docs"):
            continue
        for d in dirnames:
            if d in ("__pycache__", "__epspy__"):
                found.append(os.path.join(rel, d))
        for f in filenames:
            if f.endswith((".scx", ".pyc", ".json")) and not (rel == "testing" and f.endswith(".scx")):
                found.append(os.path.join(rel, f))
    return found


def _chk_bytes(scx):
    LoadMap(scx)
    return GetChkTokenized().savechk()


def section_build():
    before = set(repo_artifacts())
    with open(os.path.join(EXAMPLES, "scrdb_ingame.eps"), encoding="utf-8") as f:
        py, nerr = _compat.eps_compile("scrdb_ingame.eps", f.read())
    ck.true("example eps translate", py is not None and nerr == 0, "errors %d" % nerr)
    ck.true("example eps names", "scrdb.f_setup(" in (py or "") and "scrdb.f_slot(" in (py or "")
            and "db.frame()" in (py or ""), (py or "")[:200])
    if not os.path.isfile(tbuild.EUDDRAFT):
        print("  euddraft 없음 — 빌드 시험 건너뜀")
        return
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", EUDEXT_WORK=WORK)
    sig = struct.pack("<8I", *CORE.magic)
    # 10-1 정적 eds (맵이 db.frame() 을 부른다)
    work = os.path.join(WORK, "static")
    shutil.rmtree(work, ignore_errors=True)
    # 예제는 manifest="auto" → scrdb.default_manifest_path: Windows 는 늘 C:\Temp, 그 밖은 빌드 환경의 EUDEXT_WORK(= WORK)
    if os.name == "nt":
        man = scrdb.default_manifest_path("eudext_scrdb_check")
    else:
        man = os.path.join(WORK, "SCR_DB_manifest_eudext_scrdb_check.json")
    if os.path.exists(man):
        os.remove(man)
    new_eds, out_map = tbuild.prepare_eds(os.path.join(EXAMPLES, "scrdb_ingame.eds"), work)
    r = tbuild.run_euddraft(new_eds, out_map=out_map, log_path=os.path.join(work, "build.log"), env=env)
    ck.true("static build ok", r.ok, r.log[-2500:])
    ck.true("static preload lupa", "preload=dbg,scrdb venv=yes" in r.log and "[eudext.scrdb] Lua 코어" in r.log, r.log[-1500:])
    ck.true("static no warning", "Warning" not in r.log and "[Error]" not in r.log, r.log[-1500:])
    ck.true("static manifest written", "[eudext.scrdb] 매니페스트" in r.log and os.path.isfile(man), r.log[-800:])
    if os.path.isfile(man):
        with open(man, encoding="utf-8") as f:
            doc = json.load(f)
        fresh()
        sync.collect(os.path.join(EXAMPLES, "scrdb_ingame.eps"), map_path=BASE_MAP)
        ex = scrdb.current()
        ck.eq("static manifest content", (doc["field_hash"], doc["save_key"], [x["id"] for x in doc["fields"]],
                                          doc["humans"], doc["layout_version"]),
              (ex.field_hash, "eudext_scrdb_check", ex.ids, 1, CORE.layout))
    if r.ok:
        ck.true("static chk has no contiguous signature", sig not in _chk_bytes(out_map))
    # 10-2 훅 eds (선언 수집 → eds → euddraft), 빌드 ID 고정, 2인 기준 맵
    work = os.path.join(WORK, "hook")
    shutil.rmtree(work, ignore_errors=True)
    man2 = os.path.join(work, "manifest.json")
    code = (
        "import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
        "import scrdb_build\n"
        "eds, db = scrdb_build.generate(%r, base_map=%r, build_id=77777, manifest=%r)\n"
        "r = scrdb_build.build(eds, %r)\n"
        "print(r.summary())\n"
        "sys.exit(0 if r.ok else 1)\n"
    ) % (REPO, EXAMPLES, work, BASE_MULTI, man2, work)
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env, stdin=subprocess.DEVNULL, timeout=900)
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    log_path = os.path.join(work, "build", "build.log")
    log = open(log_path, encoding="utf-8").read() if os.path.isfile(log_path) else ""
    ck.true("hook build ok", p.returncode == 0, out[-2500:] + log[-1500:])
    ck.true("hook plugins loaded", "Loading plugin eudext_scrdb_hook.py" in log and "Loading plugin eudext_sync_hook.py" in log)
    ck.true("hook manifest", "(빌드 77777," in log and os.path.isfile(man2), log[-800:])
    if os.path.isfile(man2):
        with open(man2, "rb") as f:
            data = f.read()
        fresh(base=BASE_MULTI)
        os.environ[scrdb.BUILD_ID_ENV] = "77777"
        try:
            sync.collect(os.path.join(EXAMPLES, "scrdb_ingame.eps"), map_path=BASE_MULTI)
        finally:
            os.environ.pop(scrdb.BUILD_ID_ENV, None)
        ex = scrdb.current()
        d1, d2 = json.loads(data.decode("utf-8")), json.loads(ex.manifest_bytes().decode("utf-8"))
        d1.pop("generated")
        d2.pop("generated")
        ck.eq("hook manifest = in-process", d1, d2)
        ck.eq("hook humans (multi map)", d1["humans"], 4)
    # 10-3 [MSQC] 가 맵 플러그인 뒤 → 빌드 오류
    bad_dir = os.path.join(WORK, "order")
    shutil.rmtree(bad_dir, ignore_errors=True)
    os.makedirs(bad_dir)
    text = open(os.path.join(EXAMPLES, "scrdb_ingame.eds"), encoding="utf-8").read()
    msqc_block = re.search(r"(?m)^\[MSQC\]\n[^\[]*", text).group(0)
    text2 = text.replace(msqc_block, "").replace("[freeze]", msqc_block + "\n[freeze]")
    for name in ("scrdb_ingame.eps", "dbg_setup.py"):   # eds 가 디버그 브리지를 켠다 (WP-D)
        shutil.copy2(os.path.join(EXAMPLES, name), os.path.join(bad_dir, name))
    bad_eds = os.path.join(bad_dir, "scrdb_ingame.eds")
    with open(bad_eds, "w", encoding="utf-8") as f:
        f.write(text2.replace("../testing/base.scx", os.path.join(PKG, "testing", "base.scx"))
                .replace("[../boot.py]", "[%s]" % os.path.join(PKG, "boot.py"))
                .replace("EudextRoot : ../..", "EudextRoot : " + REPO)
                .replace("VenvSite : ../../.tools/euddraft_site", "VenvSite : " + VENV_SITE))
    new_eds, out_map = tbuild.prepare_eds(bad_eds, os.path.join(bad_dir, "build"))
    r = tbuild.run_euddraft(new_eds, out_map=out_map, env=env)
    ck.true("order error", not r.ok and "[MSQC] 앞에 있습니다" in r.log, r.log[-1500:])
    # 10-4 VenvSite 없음 → lupa 를 못 불러와 안내 오류
    nov = os.path.join(WORK, "novenv")
    shutil.rmtree(nov, ignore_errors=True)
    os.makedirs(nov)
    for name in ("scrdb_ingame.eps", "dbg_setup.py"):
        shutil.copy2(os.path.join(EXAMPLES, name), os.path.join(nov, name))
    with open(os.path.join(nov, "scrdb_ingame.eds"), "w", encoding="utf-8") as f:
        f.write(text.replace("../testing/base.scx", os.path.join(PKG, "testing", "base.scx"))
                .replace("[../boot.py]", "[%s]" % os.path.join(PKG, "boot.py"))
                .replace("EudextRoot : ../..", "EudextRoot : " + REPO)
                .replace("VenvSite : ../../.tools/euddraft_site\n", ""))
    new_eds, out_map = tbuild.prepare_eds(os.path.join(nov, "scrdb_ingame.eds"), os.path.join(nov, "build"))
    r = tbuild.run_euddraft(new_eds, out_map=out_map, env=env)
    ck.true("no venv error", not r.ok and "lupa 를 불러오지 못했습니다" in r.log, r.log[-1500:])
    after = set(repo_artifacts())
    ck.eq("repo clean", sorted(after - before), [])


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

_cost = {}


def _cdb(humans):
    """비용용 설정(사람 수별). 같은 빌드에서 여러 번 내므로 빌드 상태를 지운다."""
    key = "db%d" % humans
    if key not in _cost:
        scrdb.clear()
        extra = {} if humans == 4 else dict(msqc_addr=0x593F00, msqc_death=182, anchor=0x593800)  # 채널 줄이 겹치지 않게
        _cost[key] = scrdb.ScrDb([scrdb.arr("a%d" % n, n) for n in range(20)] + [scrdb.var("v%d" % n, n) for n in range(4)],
                                 "COST%d" % humans, humans=humans, xfer_base=0x58F678, xfer_stride=40,
                                 slot_base=0x5934F8, slot_stride=8, build_id=1, name="cost%d" % humans, **extra)
    scrdb._reset_build()
    return _cost[key]


def _cost_anchor(t):
    _cdb(4).anchor()


def _cost_notify(t):
    _cdb(4).notify()


def _cost_receiver(humans, channels_word=None):
    def build(t):
        db = _cdb(humans)
        scrdb._bst.anchor = True  # 표지 블록은 따로 잰다
        if channels_word is not None:
            DoActions(SetMemoryEPD(db.death_epd(0, 0), SetTo, t.var("w")))
        db.receiver()

    return build


def _cost_three_words(t):
    """같은 수신기에 사이클마다 키 → 하위 → 상위 워드(토글 번갈아)를 넣는다. 셋째 사이클이 기본 쓰기 함수까지 간다."""
    db = _cdb(4)
    c = db.core
    phase = t.var("phase")
    scrdb._bst.anchor = True
    for n, w in enumerate((A | c.tag_key | 5, B | c.tag_lo | 0x1234, A | c.tag_hi | 0x0001)):
        RawTrigger(conditions=phase.Exactly(n), actions=SetMemoryEPD(db.death_epd(0, 0), SetTo, w))
    DoActions(phase.AddNumber(1))
    db.receiver()


def _cost_frame(t):
    _cdb(4).frame()


COST_CASES = [
    CostCase("anchor: 1회 블록(첫 사이클) + LocalPlayer 8 + Seq", _cost_anchor, note="둘째 사이클부터 실행 9"),
    CostCase("notify: 알림 코드 4개 (알림 없음)", _cost_notify),
    CostCase("receiver: 채널 8 × 사람 4, 받은 워드 없음", _cost_receiver(4),
             note="호출 자리 = 자리 32 + 본문 한 벌(기본 쓰기 함수 포함). 자리당 약 310B"),
    CostCase("receiver: 채널 8 × 사람 1, 받은 워드 없음", _cost_receiver(1)),
    CostCase("receiver: 워드 1개 (키·토글 A)", _cost_receiver(4, 0), inputs={"w": A | 0x5}),
    CostCase("receiver: 워드 1개 (같은 토글 — 무시)", _cost_receiver(4, 0), inputs={"w": B | 0x5}),
    CostCase("receiver: 키 → 하위 → 상위 워드 → 기본 쓰기(ordinal)", _cost_three_words, cycles=3,
             note="실행 = 세 사이클 중 최대(셋째 = 상위 워드 + 쓰기)"),
    CostCase("frame: anchor + receiver(8×4) + notify", _cost_frame, cycles=2, note="실행 = 두 사이클 중 최대(첫 사이클 1회 블록)"),
]


def main():
    section_consts()
    section_json()
    section_setup_errors()
    section_receiver()
    section_msqc_e2e()
    section_edsgen()
    section_flags()
    section_forbidden()
    section_build()
    finish(ck.report())


if __name__ == "__main__":
    main()
