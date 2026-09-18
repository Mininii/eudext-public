"""`dbg`(디버그 브리지)·리더 사본·자동 판정 도구 시험 (DESIGN 4.21, 5.5).

1. 파이썬: setup 검사·기본 자리, 판정 명세 검사(분류 파일 286항목을 그대로 담기), 항목 판정, 확인 문서 쓰기(가짜 문서·
   실제 문서 사본 — 빈 칸만 쓰는지), 명세 결과 합치기.
2. 에뮬레이터: 블록 배치 v1(머리·정적 사본·서명·seq·감시·64/128비트·Cell·주소·글·배열 every·주소 변수·capture·프로브·
   판정·결과·표식·단계)을 기존 리더 파서(`dbg_reader` 사본의 find_blocks·Block·Symbols·Viewer)로 해석, seq 앞뒤 쓰기 순서,
   CP 보존, 페이로드 판, 꺼짐(트리거 0·페이로드 같음, EUDEXT_DBG=0), 빌드 오류(하위 프로세스), 매 프레임 비용.
3. 서명이 맵 파일(scenario.chk)·페이로드에 연속으로 없는지, epScript 예제 번역·에뮬레이션·euddraft 빌드.
4. 판정 흐름(Win32 없이): 에뮬레이터 스냅숏으로 MapRun — 통과·실패·단계 순서·멈춤·튕김·단계 시간 초과·ever.
5. 통합(Windows): 에뮬레이터 스냅숏을 가짜 게임 프로세스(`fake_game.py --replay`)에 올려 리더(--once·--peek·--record)와
   `ingame_auto.py`(여러 맵 연속, 단계 멈춤, 튕김, 확인 문서 사본 쓰기)를 실제 Win32 읽기 경로로 돌린다.
   원래의 가짜 게임 자체 시험 모드(CtrigAsm 식 심볼·`--vars`)도 고친 리더로 그대로 읽히는지 본다.

python tests/t_dbg.py            (하위 프로세스 모드: t_dbg.py --finalize-error <종류>)
"""

import sys

sys.dont_write_bytecode = True
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import struct  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import zlib  # noqa: E402

from eudplib import (  # noqa: E402
    CompressPayload,
    Db,
    DoActions,
    EUDArray,
    EUDElse,
    EUDEndIf,
    EUDIf,
    EUDLightVariable,
    EUDVariable,
    Exactly,
    GetTriggerCounter,
    LoadMap,
    Memory,
    SetMemory,
    SetTo,
    ShufflePayload,
    f_setcurpl,
)

from eudext import _compat, dbg  # noqa: E402
from eudext.cell import Cell  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.i64 import Int64  # noqa: E402
from eudext.i128 import Int128  # noqa: E402
from eudext.testing import emu, scmodel  # noqa: E402
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.tools import build, ingame_auto as A  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402
from eudext.tools.debugbridge import dbg_reader as R  # noqa: E402

EX = os.path.join(_common.PKG, "examples")
TOOLS = os.path.join(_common.PKG, "tools")
READER = os.path.join(TOOLS, "debugbridge", "dbg_reader.py")
FAKE = os.path.join(TOOLS, "debugbridge", "fake_game.py")
AUTO = os.path.join(TOOLS, "ingame_auto.py")
CLASSIFICATION = os.path.join(_common.PKG, "docs", "ingame_auto", "classification.json")
_CHECKLIST_CANDIDATES = (
    os.environ.get("EUDEXT_CHECKLIST"),
    r"C:\Users\whatd\Desktop\Stormcoast Fortress\ScmDraft 2\MapSource\EUDPLIB_PORT_CHECKLIST.md",
    os.path.join(os.path.expanduser("~"), "Documents", "MapSource", "EUDPLIB_PORT_CHECKLIST.md"),
)
# 사용자 확인 문서(있을 때만 쓰는 시험). PC 마다 자리가 다르다 — 환경 변수 EUDEXT_CHECKLIST 가 가장 앞선다.
REAL_CHECKLIST = next((p for p in _CHECKLIST_CANDIDATES if p and os.path.isfile(p)), _CHECKLIST_CANDIDATES[1])
T = os.path.join(_common.WORK, "t_dbg")
SYMDIR = os.path.join(T, "sym")
SIG = struct.pack("<8I", *dbg.SIGNATURE)
M32 = 0xFFFFFFFF
os.makedirs(T, exist_ok=True)


def _fresh_dir(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path)
    return path


# =============================================================================================
# 1. 파이썬
# =============================================================================================


def python_checks(ck):
    dbg.reset()
    ck.eq("레이아웃 상수 = 리더", (dbg.HDR, dbg.H_SEQ_BEGIN, dbg.H_USED, dbg.LAYOUT_VERSION, dbg.SIGNATURE,
                             dbg.STATIC_COPIES, dbg.GAME_FRAME_EUD),
          (R.HDR, R.H_SEQ_BEGIN, R.H_USED, R.LAYOUT_VERSION, R.DEFAULT_SIGNATURE, R.STATIC_COPIES, R.GAME_FRAME_EUD))
    dbg.setup(map_name="p", build_id=1, enable=True)
    lay = dbg.layout()
    ck.eq("기본 자리 = DebugBridge.lua (0x596280)", (lay["addr"], lay["total"], lay["seq_end"], lay["probe_start"]),
          (0x596280, 345, 88, 89))
    dbg.setup(map_name="p", build_id=1, watch_slots=200, probes=1000)
    lay = dbg.layout()
    ck.eq("용량이 크면 더 아래 (16 정렬)", lay["addr"], (0x5967F0 - 4 * (24 + 200 + 1 + 1000)) & ~15)
    dbg.setup(map_name="p", build_id=1, addr=0x594800)
    ck.eq("정수 주소", dbg.layout()["addr"], 0x594800)
    dbg.setup(map_name="p", build_id=1, addr="payload")
    ck.true("페이로드 판 Db", dbg.layout()["where"] == "payload" and dbg.layout()["db"] is not None)
    for label, kw in (("watch_slots 0", dict(watch_slots=0)), ("probes 음수", dict(probes=-1)),
                      ("너무 큼", dict(watch_slots=0xFFFF, probes=0xFFFF)), ("정렬 안 됨", dict(addr=0x594801)),
                      ("미러 밖", dict(addr=0x6509A0)), ("모르는 자리", dict(addr="heap")),
                      ("void 에 안 들어감", dict(watch_slots=0x3000, probes=0x800)), ("build_id 0", dict(build_id=0)),
                      ("이름 줄바꿈", dict(map_name="a\nb")), ("이름 빈", dict(map_name=""))):
        kw.setdefault("map_name", "p")
        kw.setdefault("build_id", 1)
        ck.raises("setup 오류: " + label, EudextError, dbg.setup, **kw)
    dbg.setup(map_name="p", build_id=1, addr=0x6509A0, allow_outside_mirror=True)
    ck.eq("미러 밖 허용", dbg.layout()["addr"], 0x6509A0)
    dbg.setup(map_name="p", build_id=1, enable=False)
    ck.eq("꺼짐 → enabled 0", dbg.f_enabled(), 0)
    ck.eq("꺼진 probe = 비활성 액션", dbg.probe("x").fields[9] & 2, 2)
    os.environ["EUDEXT_DBG"] = "0"
    try:
        dbg.setup(map_name="p", build_id=1, enable=True)
        ck.eq("EUDEXT_DBG=0 이면 꺼짐", dbg.f_enabled(), 0)
    finally:
        del os.environ["EUDEXT_DBG"]
    dbg.setup(map_name="p", build_id=1)
    ck.eq("켜짐 → enabled 1", dbg.f_enabled(), 1)
    ck.raises("이름 검사", EudextError, dbg.hit, "")
    ck.raises("snapshot n 0", EudextError, dbg.snapshot, "s", 0x58A364, 0)
    ck.raises("snapshot every 음수", EudextError, dbg.snapshot, "s", 0x58A364, 1, every=-1)
    ck.raises("mark_action 변수", EudextError, dbg.mark_action, "m", EUDVariable())
    ck.raises("주소 아님", EudextError, dbg.watch, "w", "text")
    dbg.reset()
    ck.eq("reset 뒤 설정 없음", dbg.layout(), None)
    ck.eq("setup 없이 hit → 아무것도", dbg.hit("x"), None)
    ck.true("setup 없이 부른 수 기록", dbg._bridge.unset_calls >= 1)
    ck.eq("_default_map_name (euddraft 밖)", dbg._default_map_name(), "map")
    spec_checks(ck)
    judge_unit_checks(ck)
    checklist_checks(ck)


def _spec(**kw):
    d = {"format": "eudext-ingame-spec", "version": 1, "map": "m"}
    d.update(kw)
    return d


def spec_checks(ck):
    s = A.check_spec(_spec(items=[{"kind": "check", "name": "a", "checklist": True},
                                  {"kind": "watch", "name": "w", "equals": "0x10", "phase": 3, "read": ["r"],
                                   "expect": "e", "done_marker": "dm", "category": "AUTO"},
                                  {"kind": "group", "id": "g", "items": [{"kind": "mark", "name": "done"}]},
                                  {"kind": "peek", "addr": "0x58DC40", "count": 2, "equals": [5, 129]},
                                  {"kind": "wall", "metric": "fps", "min": 1.5},
                                  {"kind": "manual", "id": "V-1", "expect": "보기"}],
                           suites=[{"name": "s", "phase": 3, "items": [{"kind": "hit", "name": "h"}]}]))
    ck.eq("명세 기본값", (s["timeout_s"], s["settle_cycles"], s["stall_s"], s["items"][0]["checklist"]),
          (300.0, 2, None, [("a", None)]))
    ck.eq("명세 정수 문자열", (s["items"][1]["equals"], s["items"][3]["addr"], s["items"][3]["equals"]),
          (16, 0x58DC40, [5, 129]))
    ck.eq("분류 설명 필드는 info 로", s["items"][1]["info"],
          {"read": ["r"], "expect": "e", "done_marker": "dm", "phase": 3, "category": "AUTO"})
    ck.eq("wall 실수 기준", s["items"][4]["min"], 1.5)
    bad = [
        ("format", {"format": "x", "map": "m"}),
        ("map 없음", {"format": "eudext-ingame-spec"}),
        ("kind", _spec(items=[{"kind": "nope"}])),
        ("name 없음", _spec(items=[{"kind": "check"}])),
        ("id 겹침", _spec(items=[{"kind": "hit", "name": "a"}, {"kind": "mark", "name": "a"}])),
        ("when", _spec(items=[{"kind": "hit", "name": "a", "when": "sometimes"}])),
        ("equals 글", _spec(items=[{"kind": "watch", "name": "a", "equals": "열"}])),
        ("regex", _spec(items=[{"kind": "text", "name": "a", "regex": "("}])),
        ("peek 정렬", _spec(items=[{"kind": "peek", "addr": 3}])),
        ("hdr field", _spec(items=[{"kind": "hdr", "field": "cp"}])),
        ("wall metric", _spec(items=[{"kind": "wall", "metric": "tps"}])),
        ("group 빈", _spec(items=[{"kind": "group", "id": "g", "items": []}])),
        ("checklist 형", _spec(items=[{"kind": "hit", "name": "a", "checklist": 3}])),
        ("done 형", _spec(done="done")),
        ("timeout 0", _spec(timeout_s=0)),
        ("단계 이름", _spec(suites=[{"phase": 1}])),
        ("단계 겹침", _spec(suites=[{"name": "a"}, {"name": "a"}])),
        ("phase 겹침", _spec(suites=[{"name": "a", "phase": 1}, {"name": "b", "phase": 1}])),
    ]
    for label, doc in bad:
        ck.raises("명세 오류: " + label, A.SpecError, A.check_spec, doc)
    # 분류 파일 286항목을 그대로(수동 항목으로) 담을 수 있다
    with open(CLASSIFICATION, encoding="utf-8") as f:
        items = json.load(f)
    conv = [dict(it, kind="manual") for it in items]
    s = A.check_spec(_spec(items=conv))
    ck.eq("분류 항목 전부 담김", len(s["items"]), len(items))
    ck.true("분류 필드 보존", all(x["info"].get("expect") == y.get("expect") and x["info"].get("read") == y.get("read")
                                  and x["info"].get("done_marker") == y.get("done_marker")
                                  and x["info"].get("phase") == y.get("phase") for x, y in zip(s["items"], items)))
    ck.eq("분류 phase 수", sum(1 for x in s["items"] if x.get("phase") is not None),
          sum(1 for y in items if y.get("phase") is not None))
    # 폴더 불러오기 (다른 JSON 건너뜀, 같은 맵 둘이면 오류)
    d = _fresh_dir(os.path.join(T, "specload"))
    for n, doc in (("a.json", _spec(map="x")), ("b.json", {"other": 1}), ("c.json", _spec(map="y"))):
        with open(os.path.join(d, n), "w", encoding="utf-8") as f:
            json.dump(doc, f)
    ck.eq("폴더 명세", sorted(A.load_specs([d])), ["x", "y"])
    with open(os.path.join(d, "d.json"), "w", encoding="utf-8") as f:
        json.dump(_spec(map="x"), f)
    ck.raises("같은 맵 두 명세", A.SpecError, A.load_specs, [d])


class _Sym:
    """판정 단위 시험용 가짜 심볼."""

    def __init__(self, ext):
        self.ext = ext


def judge_unit_checks(ck):
    ext = {"checks": [{"name": "a", "sites": ["x:1", "x:2"], "suite": None}, {"name": "s.b", "sites": ["x:3"], "suite": None}],
           "results": [{"name": "r", "sites": []}], "marks": [{"name": "done"}], "hits": [], "watches": [], "texts": []}
    sym = _Sym(ext)
    vals = {"checks": {"a": (2, 2), "s.b": (0, 1)}, "results": {"r": (3, 4, 1)}, "marks": {"done": 5}, "hits": {"h": 7},
            "watches": {"w": -5, "big": 1 << 40},
            "texts": {"t": ("HP 5 / 10", struct.unpack("<3I", "HP 5 / 10".encode() + bytes(3))),
                      "raw": (None, (1, 2, 3))},
            "suites": {}, "suite_now": None}
    cases = [
        ({"kind": "check", "name": "a"}, True),
        ({"kind": "check", "name": "a", "total": "sites"}, True),
        ({"kind": "check", "name": "a", "total": 3}, False),
        ({"kind": "check", "name": "s.b"}, False),
        ({"kind": "check", "name": "zz"}, False),
        ({"kind": "result", "name": "r"}, False),
        ({"kind": "all_checks"}, False),
        ({"kind": "all_checks", "suite": "s"}, False),
        ({"kind": "all_checks", "suite": "none"}, None),
        ({"kind": "mark", "name": "done"}, True),
        ({"kind": "mark", "name": "done", "equals": 4}, False),
        ({"kind": "hit", "name": "h", "min": 7, "max": 7}, True),
        ({"kind": "watch", "name": "w", "equals": -5}, True),
        ({"kind": "watch", "name": "big", "equals": str(1 << 40)}, True),
        ({"kind": "watch", "name": "w", "in": [1, 2]}, False),
        ({"kind": "text", "name": "t", "contains": "HP 5"}, True),
        ({"kind": "text", "name": "t", "regex": r"^HP \d+ / 10$"}, True),
        ({"kind": "text", "name": "t", "equals": "HP 5"}, False),
        ({"kind": "text", "name": "t", "offset": 3, "length": 1, "equals": "5"}, True),
        ({"kind": "dwords", "name": "raw", "equals": [1, 2]}, True),
        ({"kind": "manual", "id": "v", "expect": "눈으로"}, None),
        ({"kind": "group", "id": "g", "items": [{"kind": "mark", "name": "done"}, {"kind": "manual", "id": "v"}]}, True),
        ({"kind": "group", "id": "g", "items": [{"kind": "mark", "name": "done"}, {"kind": "check", "name": "s.b"}]}, False),
        ({"kind": "peek", "addr": 0x58DC40, "count": 2, "equals": [0x80000005, 129]}, True),
        ({"kind": "peek", "addr": 0x58DC40, "count": 2, "equals": [5, 129]}, False),
        ({"kind": "peek", "addr": 0x58DC40, "mask": 0xF, "equals": 5}, True),
        ({"kind": "peek", "addr": 0x58DC44, "min": 130}, False),
        ({"kind": "hdr", "field": "local_player", "in": [128, 129]}, True),
        ({"kind": "hdr", "field": "player_info", "equals": [1, 2, 3, 4]}, True),
        ({"kind": "wall", "metric": "fps", "min": 23, "max": 25}, True),
        ({"kind": "wall", "metric": "max_gap_s", "max": 0.05}, True),
        ({"kind": "wall", "metric": "seconds", "min": 5}, False),
    ]
    header = [0] * 24
    header[R.H_LOCAL_PLAYER] = 129
    header[16:20] = [1, 2, 3, 4]
    ctx = {"d": header, "peek": lambda a, n: tuple([0x80000005, 129][:n]) if a == 0x58DC40 else (0,) * n,
           "timeline": [(100 + k / 24, k) for k in range(49)], "window": None}
    for k, (it, want) in enumerate(cases):
        it = A._check_item(it, "unit[%d]" % k)
        ok, detail, _v = A.evaluate_item(it, sym, vals, ctx)
        ck.eq("항목 판정 %d %s %s" % (k, it["kind"], it.get("name") or it["id"]), ok, want)
    ok, detail, _v = A.evaluate_item(A._check_item({"kind": "peek", "addr": 0}, "p"), sym, vals, {})
    ck.true("peek 없는 맥락 = 실패", ok is False and "peek 불가" in detail, detail)


CHECKLIST_FIXTURE = """# 확인 목록

## 1. 맵

### 1.1 맵별 요약

| 맵 | 여는 방법 | 결과 (한 줄) |
|---|---|---|
| 01 `01_a.scx` | 혼자 | |
| 02 `02_b.scx` | 혼자 | 통과 (사용자) |

### 1.3 권장

| 맵 | 권장 항목 | 결과 |
|---|---|---|
| 01 | A-9 | |
| 02 | B-9 | |

#### 01 `01_a.scx`

| # | 확인할 것 | 방법 | 결과 |
|---|---|---|---|
| **A-1** | 식 `a | b` 확인 | 연다 |  |
| A-2 | 두 번째 | 연다 | 다름: 3 |
| A-3 | 세 번째 | 연다 | |

## 6. 정해 주실 것

| # | 질문 | 권장 | 답 |
|---|---|---|---|
| Q-1 | 할까요? | 예 | |
"""


def checklist_checks(ck):
    path = os.path.join(T, "checklist_fixture.md")
    for newline, bom in (("\n", False), ("\r\n", True)):
        data = CHECKLIST_FIXTURE.replace("\n", newline).encode("utf-8")
        if bom:
            data = b"\xef\xbb\xbf" + data
        with open(path, "wb") as f:
            f.write(data)
        entries = [("A-1", None, "자동: 통과 (2026-09-18)"), ("A-2", None, "자동: 실패 — x (2026-09-18)"),
                   ("01", None, "자동: 통과 (2026-09-18)"), ("01", "1.1", "자동: 통과 (2026-09-18)"),
                   ("02", "1.1", "자동: 통과 (2026-09-18)"), ("Q-1", None, "자동: 통과 (2026-09-18)"),
                   ("Z-9", None, "자동: 통과 (2026-09-18)"), ("A-3", "#### 99", "자동: 통과 (2026-09-18)")]
        dry = A.write_checklist(path, entries, dry_run=True)
        with open(path, "rb") as f:
            ck.eq("시험 실행은 안 씀 (%r)" % newline, f.read(), data)
        got = A.write_checklist(path, entries)
        states = [st for _r, _s, st, _t in got]
        ck.eq("확인 문서 상태 (%r)" % newline, states,
              ["씀", "이미 적힘 — 그대로", "행이 여러 개 — section 을 주세요 (2곳)", "씀", "이미 적힘 — 그대로",
               "결과 칸이 아님", "행 없음", "행 없음"])
        ck.eq("시험 실행 상태", [st for _r, _s, st, _t in dry][0], "쓸 것(시험 실행)")
        with open(path, "rb") as f:
            out = f.read()
        ck.eq("BOM 유지 (%r)" % newline, out.startswith(b"\xef\xbb\xbf"), bom)
        text = out.decode("utf-8-sig")
        ck.true("줄 끝 유지 (%r)" % newline, (text.count("\r\n") == text.count("\n")) == (newline == "\r\n"))
        lines = text.split(newline)
        base = CHECKLIST_FIXTURE.split("\n")
        changed = [(a, b) for a, b in zip(base, lines) if a != b]
        ck.eq("바뀐 줄 둘뿐 (%r)" % newline, changed, [
            ("| 01 `01_a.scx` | 혼자 | |", "| 01 `01_a.scx` | 혼자 | 자동: 통과 (2026-09-18) |"),
            ("| **A-1** | 식 `a | b` 확인 | 연다 |  |", "| **A-1** | 식 `a | b` 확인 | 연다 | 자동: 통과 (2026-09-18) |"),
        ])
        again = A.write_checklist(path, entries[:1])
        ck.eq("두 번째엔 그대로", again[0][2], "이미 적힘 — 그대로")
    # 결과 합치기
    run = {"map": "m", "verdict": A.FAIL, "reason": "완료 표식", "checklist": [{"row": "01", "section": "1.1"}],
           "items": [{"id": "A-1", "verdict": A.PASS, "detail": "1/1", "checklist": [{"row": "A-1", "section": None}]},
                     {"id": "A-2", "verdict": A.FAIL, "detail": "0 | 1", "checklist": [{"row": "A-2", "section": None}]},
                     {"id": "V", "verdict": A.MANUAL, "detail": "", "checklist": [{"row": "A-3", "section": None}]}],
           "suites": [{"name": "s", "status": A.STALLED, "reason": "멈춤", "items": [],
                       "checklist": [{"row": "B-1", "section": None}]}]}
    ents = A.checklist_entries([run], "2026-09-18")
    ck.eq("결과 합치기", ents, [
        ("01", "1.1", "자동: 실패 — 실패 A-2, s(멈춤) (2026-09-18)"),
        ("A-1", None, "자동: 통과 (2026-09-18)"),
        ("A-2", None, "자동: 실패 — A-2 0 / 1 (2026-09-18)"),
        ("B-1", None, "자동: 실패 — s 멈춤: 멈춤 (2026-09-18)"),
    ])
    # 실제 확인 문서의 사본 (원본은 건드리지 않는다)
    if os.path.isfile(REAL_CHECKLIST):
        before = open(REAL_CHECKLIST, "rb").read()
        copy = os.path.join(T, "EUDPLIB_PORT_CHECKLIST.copy.md")
        shutil.copy2(REAL_CHECKLIST, copy)
        res = A.write_checklist(copy, [("02", None, "자동: 통과 (x)"), ("02", "1.1", "자동: 통과 (x)"),
                                       ("C3-1", None, "자동: 실패 — 시험 (x)"), ("Q-1", None, "자동: 통과 (x)")],
                                dry_run=True)
        states = [st for _r, _s, st, _t in res]
        ok_states = ("쓸 것(시험 실행)", "이미 적힘 — 그대로")
        # REAL_CHECKLIST 는 **사용자 문서**다 — 이미 결과가 적혀 있거나(이미 적힘) 인게임 결과 표가 더해져 행이 여러
        # 개일 수 있다(2026-09-18: C3-1 이 두 곳). 도구가 그 상태를 알려 주는 것까지가 이 시험의 범위다.
        many = "행이 여러 개"
        ck.true("실제 문서 사본 시험 실행", states[0].startswith(many) and
                (states[1] in ok_states or states[1].startswith(many)) and
                (states[2] in ok_states or states[2].startswith(many)) and
                states[3] == "결과 칸이 아님", states)
        ck.eq("원본 확인 문서 그대로", open(REAL_CHECKLIST, "rb").read(), before)


# =============================================================================================
# 2. 에뮬레이터
# =============================================================================================


class EmuProc:
    """에뮬레이터 메모리를 dbg_reader 의 Process 처럼 보이게 (scan·dwords·read)."""

    pid = 0
    bits = 32

    def __init__(self, m):
        self.m = m

    def dwords(self, addr, count):
        return tuple(self.m.dw(addr + 4 * i) for i in range(count))

    def read(self, addr, size):
        return self.m.read_bytes(addr, size)

    def scan(self, pattern, mask):
        hits = []
        for lo, hi in ((0x57F0E0, 0x59F0E0), (self.m.base, self.m.limit_addr)):
            data = b"".join(struct.pack("<I", self.m.dw(a)) for a in range(lo, hi, 4))
            i = data.find(pattern)
            while i >= 0:
                if i % 4 == 0:
                    hits.append(lo + i)
                i = data.find(pattern, i + 1)
        return hits


def _block_words(m, addr, total):
    return [m.dw(addr + 4 * i) for i in range(total)]


class _Refs:
    pass


def build_layout_program():
    """모든 종류를 싣는 빌드 (미러 기본 자리 아님: probes=128)."""
    dbg.reset()
    LoadMap(BASE_MAP)
    CompressPayload(True)
    dbg.setup(map_name="t_layout", build_id=0x0BADC0DE, symbols=SYMDIR, watch_slots=64, probes=128, tag="시험")
    r = _Refs()
    r.v = EUDVariable()
    r.lv = EUDLightVariable()
    r.cell = Cell(0)
    r.x64 = Int64(0)
    r.x128 = Int128(0)
    r.flag = EUDVariable()
    r.cpv = EUDVariable()
    r.txt = Db(b"hello world!")
    r.db2 = Db(b"WXYZabcd")
    r.arr = EUDArray(4)
    r.arr2 = EUDArray(2)
    r.ptr = EUDVariable()

    def setup():
        r.ptr << r.db2
        dbg.watch("v", r.v)
        dbg.watch("lv", r.lv)
        dbg.watch("cell", r.cell)
        dbg.watch("x64", r.x64, signed=True)
        dbg.watch("x128", r.x128)
        dbg.watch("frame", 0x57F23C)
        dbg.watch("db2", r.db2)
        dbg.snapshot_text("txt", r.txt, 3)
        dbg.snapshot("arr", r.arr, 4, every=3)
        dbg.snapshot("ptr", r.ptr, 2)
        dbg.snapshot("cap", r.arr2, 2, every=0)

    def body():
        # 루프 시작 코드(dbg) 바로 뒤의 실제 CP — 앞 사이클 끝에서 3 으로 두었다
        if EUDIf()(Memory(0x6509B0, Exactly, 3)):
            r.cpv << 3
        if EUDElse()():
            r.cpv << 99
        EUDEndIf()
        r.v.__iadd__(1)
        r.lv.__iadd__(1)
        r.cell.__iadd__(2)
        r.x64.__iadd__(0x100000001)
        r.x128.__iadd__((1 << 96) + 3)
        r.flag << 0
        if EUDIf()(r.v.AtLeastX(1, 2)):
            r.flag << 1
        EUDEndIf()
        r.arr[0] = r.v
        r.arr2[0] = r.v
        dbg.hit("all")
        dbg.hit("odd", r.v.AtLeastX(1, 1))
        dbg.hit("never", False)
        dbg.hit("flag", r.flag)
        DoActions(dbg.probe("act"), SetMemory(0x58F500, SetTo, 0))
        dbg.check("c.ge", r.v >= 1)
        dbg.check("c.eq3", r.v == 3)
        dbg.check("c.const", True)
        dbg.check("c.var", r.flag)
        if EUDIf()(r.v == 5):
            dbg.result("r", r.v, 7)
            dbg.mark("m5", r.v)
            dbg.capture("cap")
            DoActions(dbg.mark_action("ma", 9))
        EUDEndIf()
        if EUDIf()(r.v == 2):
            dbg.suite_begin("s1", phase=5)
            dbg.check("s1.a", r.v == 2)
        EUDEndIf()
        if EUDIf()(r.v == 4):
            dbg.suite_end("s1", r.v == 4)
        EUDEndIf()
        if EUDIf()(r.v == 6):
            dbg.suite_begin("s2")
            dbg.hit("s2.hit")
        EUDEndIf()
        f_setcurpl(3)

    prog = emu.Program(body, setup=setup)
    prog.watch("cpv", r.cpv)
    m = prog.build()
    scmodel.install(m, local_player=2)
    m.write_bytes(0x57FD3C, b"maps\\t_layout.scx\0")
    # 같은 SC 프로세스의 앞 게임이 남긴 값 흉내 (옛 서명 포함) — 시작 코드가 쓰는 칸을 지워야 한다
    lay = dbg.layout()
    m.init_mem({lay["addr"] + 4 * i: 0xDEADBEEF for i in range(lay["total"])})
    m.init_mem({lay["addr"] + 4 * i: w for i, w in enumerate(dbg.SIGNATURE)})
    return m, r, prog


def emu_layout(ck):
    m, r, prog = build_layout_program()
    lay = dbg.layout()
    addr, total = lay["addr"], lay["total"]
    ck.eq("자리 (probes=128)", addr, (0x5967F0 - 4 * (24 + 64 + 1 + 128)) & ~15)
    doc = dbg.symbols_doc()
    ck.true("심볼 파일", os.path.isfile(os.path.join(SYMDIR, "DebugBridge_t_layout_0BADC0DE.json")) and
            os.path.isfile(os.path.join(SYMDIR, "DebugBridge_symbols.json")))
    ck.eq("심볼 머리", (doc["format"], doc["layout_version"], doc["build_id"], doc["block_eud"], doc["total_dwords"],
                     doc["seq_end"], doc["probe_start"], doc["eudext"]["map_name"], doc["eudext"]["build_tag"]),
          ("eud-debug-bridge", 1, 0x0BADC0DE, addr, total, 88, 89, "t_layout", "시험"))
    ck.eq("옛 게임 흉내: 처음 칸", (_block_words(m, addr, total)[:8], m.dw(addr + 4 * 88)),
          (list(dbg.SIGNATURE), 0xDEADBEEF))
    frames = {}
    for k in range(1, 11):
        m.setdw(0x57F23C, 1000 + k)
        m.cycle()
        frames[k] = _block_words(m, addr, total)
    ck.eq("흉내 못 낸 것", sorted(m.unknown), [("act", 44)])  # eudplib 로케일 판별 CreateUnit
    d = frames[10]
    K = 10
    ck.eq("서명", tuple(d[:8]), dbg.SIGNATURE)
    ck.eq("머리", (d[8], d[9], d[10], d[11], d[15]), (1, 0x0BADC0DE, addr, 64 | 128 << 16, doc["eudext"]["used"][0]
                                                     | doc["eudext"]["used"][1] << 16))
    ck.eq("seq = 사이클", (d[12], d[88]), (K, K))
    ck.true("seq 는 매 사이클 앞뒤가 같다", all(frames[k][12] == frames[k][88] == k for k in frames))
    ck.eq("게임 프레임 사본 (사이클 시작 값)", d[13], 1000 + K)
    ck.eq("정적 사본: 이 PC·플레이어 정보·맵 경로", (d[14], tuple(d[16:20]), R.decode_text(d[20:24])),
          (2, tuple(m.dw(0x57EEE8 + 4 * i) for i in range(4)), "maps\\t_layout.sc"))
    ck.eq("표지 = 맵 이름 CRC", d[24], zlib.crc32(b"t_layout"))
    used_w, used_p = doc["eudext"]["used"]
    ck.eq("옛 값: 쓰지 않는 칸은 그대로 (리더는 사용 개수까지만 본다)",
          (d[24 + used_w], d[89 + used_p], d[20 + 0] != 0xDEADBEEF), (0xDEADBEEF, 0xDEADBEEF, True))
    ck.true("옛 값: 쓰는 칸은 지워졌다", 0xDEADBEEF not in d[:24 + used_w] + d[88:89 + used_p], d[:100])
    # 리더 사본으로 찾고 읽기
    proc = EmuProc(m)
    hits, blocks = R.find_blocks(proc, R.DEFAULT_SIGNATURE)
    ck.eq("리더 find_blocks", ([b.addr for b in blocks], len(hits)), ([addr], 1))
    block = blocks[0]
    snap, ok = block.snapshot()
    ck.true("리더 스냅숏 일관", ok and list(snap) == d)
    ck.eq("리더 Layout", (block.layout.watch_cap, block.layout.probe_cap, block.layout.seq_end, block.layout.total,
                         block.layout.watch_used, block.layout.probe_used), (64, 128, 88, total) + tuple(doc["eudext"]["used"]))
    sym = R.load_symbols(SYMDIR, block.build)
    ck.true("심볼 폴더에서 빌드로 고름", sym.loaded and sym.ext and sym.build_id == 0x0BADC0DE)
    v = R.ext_values(sym, d)
    ck.eq("감시 값 (앞 사이클 끝)", {k: v["watches"][k] for k in ("v", "lv", "cell", "frame")},
          {"v": K - 1, "lv": K - 1, "cell": 2 * (K - 1), "frame": 1000 + K})
    ck.eq("64비트 (부호 있음)", v["watches"]["x64"], (K - 1) * 0x100000001)
    ck.eq("128비트", v["watches"]["x128"], (K - 1) * ((1 << 96) + 3))
    ck.eq("페이로드 주소 감시", v["watches"]["db2"], struct.unpack("<I", b"WXYZ")[0])
    ck.eq("글 스냅숏", v["texts"]["txt"][0], "hello world!")
    last_copy = max(c for c in range(1, K + 1) if c % 3 == 1)
    ck.eq("every=3 배열", v["texts"]["arr"][1], (last_copy - 1, 0, 0, 0))
    ck.eq("주소 변수 스냅숏", v["texts"]["ptr"][1], struct.unpack("<2I", b"WXYZabcd"))
    ck.eq("capture (사이클 5 에서 한 번)", v["texts"]["cap"][1], (5, 0))
    ck.eq("capture 전에는 0", R.ext_values(sym, frames[4])["texts"]["cap"][1], (0, 0))
    ck.eq("hit", v["hits"], {"all": K, "odd": (K + 1) // 2, "never": 0, "flag": sum(1 for k in range(1, K + 1) if k & 2),
                            "act": K, "s2.hit": 1})
    ck.eq("check", v["checks"], {"c.ge": (K, K), "c.eq3": (1, K), "c.const": (K, K),
                                 "c.var": (sum(1 for k in range(1, K + 1) if k & 2), K), "s1.a": (1, 1)})
    ck.eq("result·mark", (v["results"], v["marks"]), ({"r": (5, 7, 1)}, {"m5": 5, "ma": 9}))
    ck.eq("단계", v["suites"], {"s1": (2, 2, 4, 1), "s2": (1, 6, 0, 0)})
    ck.eq("지금 단계", v["suite_now"], {"current": "s2", "last": "s2", "frame": 6})
    nos = {s["name"]: s["no"] for s in sym.ext["suites"]}
    ck.eq("단계 번호 (phase 고정 + 빈 번호)", nos, {"s1": 5, "s2": 1})
    ck.eq("항목의 단계", {c["name"]: c["suite"] for c in sym.ext["checks"]},
          {"c.ge": None, "c.eq3": None, "c.const": None, "c.var": None, "s1.a": "s1"})
    ck.eq("결과 이름 목록", sym.ext["result_names"], ["c.ge", "c.eq3", "c.const", "c.var", "s1.a", "r"])
    ck.eq("CP 보존 (루프 시작 코드 뒤 CP = 캐시)", m.var("cpv"), 3)
    screen = R.Viewer(sym).render(block, snap, ok)
    for needle in ("빌드 %d [심볼 일치]" % 0x0BADC0DE, "-- eudext: 맵 t_layout", "판정 c.eq3", "1 / 10  실패 있음",
                   "결과 r", "글   txt", "'hello world!'", "단계 s1", "끝 프레임 2~4  맵 판정 통과", "단계 지금 s2",
                   "값   x128", "  v  "):
        ck.true("리더 화면: " + needle, needle in screen, screen)
    ck.true("리더 화면: 글 칸은 숫자 줄로 안 보임", "txt[0]" not in screen)
    # seq 앞뒤 쓰기 순서 (사이클 11 — capture 없음)
    log = []
    orig = m.setdw
    lo, hi = addr, addr + 4 * total

    def spy(a, value):
        if lo <= (a & M32) < hi:
            log.append(((a & M32) - lo) // 4)
        orig(a, value)

    m.setdw = spy
    try:
        m.cycle()
    finally:
        del m.setdw
    i_begin, i_end = log.index(12), log.index(88)
    watch_idx = [n for n, x in enumerate(log) if 25 <= x < 88]
    ck.true("seq 시작 → 감시 → seq 끝", i_begin < min(watch_idx) and max(watch_idx) < i_end, log)
    ck.true("seq 끝 뒤에는 감시 칸을 쓰지 않음", all(not 24 <= x < 88 for x in log[i_end + 1:]), log)
    ck.true("프로브 칸은 seq 밖(본문)", all(n > i_end for n, x in enumerate(log) if x > 88), log)
    return m, frames


def emu_payload(ck):
    dbg.reset()
    LoadMap(BASE_MAP)
    CompressPayload(True)
    dbg.setup(map_name="t_payload", build_id=0x77, addr="payload", symbols=SYMDIR, watch_slots=8, probes=8)
    db = dbg.layout()["db"]
    v = EUDVariable()

    def body():
        v.__iadd__(1)
        dbg.hit("tick")

    def setup():
        dbg.watch("v", v)

    prog = emu.Program(body, setup=setup)
    prog.watch("blk", db)
    m = prog.build()
    scmodel.install(m)
    addr = m.addr("blk")
    total = dbg.layout()["total"]
    ck.eq("페이로드 블록 크기", total, 24 + 8 + 1 + 8)
    ck.true("페이로드 블록은 처음에 0", not any(_block_words(m, addr, total)))
    m.cycle(4)
    d = _block_words(m, addr, total)
    ck.eq("페이로드 머리 (자기 주소 = 재배치된 주소)", (tuple(d[:8]), d[8], d[9], d[10], d[12], d[32]),
          (dbg.SIGNATURE, 1, 0x77, addr, 4, 4))
    proc = EmuProc(m)
    _hits, blocks = R.find_blocks(proc, R.DEFAULT_SIGNATURE)
    ck.eq("리더가 페이로드 블록을 찾음", [b.addr for b in blocks], [addr])
    ck.eq("delta = 0 (에뮬레이터)", blocks[0].delta, 0)
    sym = R.load_symbols(SYMDIR, 0x77)
    vals = R.ext_values(sym, d)
    ck.eq("페이로드 값", (vals["watches"]["v"], vals["hits"]["tick"]), (3, 4))
    ck.eq("심볼 where·block_eud", (sym.doc["block_eud"], sym.ext["where"]), (None, "payload"))


def _count_build(body):
    LoadMap(BASE_MAP)
    CompressPayload(True)
    ShufflePayload(False)  # 적층 배치를 고정해야 크기를 견줄 수 있다 (tools/cost.py 와 같음)
    try:
        prog = emu.Program(body)
        c0 = GetTriggerCounter()
        prog.build()
    finally:
        ShufflePayload(True)
    return GetTriggerCounter() - c0, prog.payload_size


def emu_disabled(ck):
    v = EUDVariable()
    arr = EUDArray(2)

    def calls():
        dbg.watch("v", v)
        dbg.snapshot("a", arr, 2)
        dbg.hit("h")
        dbg.hit("h2", v == 1)
        dbg.check("c", v == 1)
        dbg.result("r", v, 3)
        dbg.mark("m")
        dbg.suite_begin("s")
        dbg.suite_end("s", v == 1)
        DoActions(dbg.probe("p"), dbg.mark_action("ma"))

    def plain():
        DoActions(dbg._off_action(), dbg._off_action())

    dbg.reset()
    _count_build(plain)
    base = _count_build(plain)
    dbg.setup(map_name="off", build_id=1, enable=False)
    off = _count_build(calls)
    ck.eq("꺼짐: 트리거 수·페이로드 같음", off, base)
    os.environ["EUDEXT_DBG"] = "0"
    try:
        dbg.setup(map_name="off", build_id=1, enable=True)
        ck.eq("EUDEXT_DBG=0: 같음", _count_build(calls), base)
    finally:
        del os.environ["EUDEXT_DBG"]
    dbg.reset()
    ck.eq("setup 없음: 같음", _count_build(calls), base)
    dbg.setup(map_name="on", build_id=2, symbols=SYMDIR)
    on = _count_build(calls)
    ck.true("켜면 늘어난다", on[0] > base[0] and on[1] > base[1], (on, base))
    dbg.reset()


def emu_build_errors(ck):
    """등록 자리에서 나는 오류 (harness expect_build_error)."""
    dbg.reset()
    dbg.setup(map_name="err", build_id=3, symbols=SYMDIR)
    s = Suite("t_dbg errors", verbose=False)
    v = EUDVariable()

    @s.case("dup_watch", expect_build_error=EudextError, expect_message="이미")
    def _(t):
        dbg.watch("dup", v)
        dbg.watch("dup", v)

    @s.case("capture_unknown", expect_build_error=EudextError, expect_message="snapshot")
    def _(t):
        dbg.capture("nope")

    @s.case("phase_diff", expect_build_error=EudextError, expect_message="번호")
    def _(t):
        dbg.suite_begin("px", phase=2)
        dbg.suite_end("px")
        dbg.suite_begin("px", phase=3)

    @s.case("phase_range", expect_build_error=EudextError, expect_message="phase")
    def _(t):
        dbg.suite_begin("py", phase=0)

    @s.case("setup_after_init", expect_build_error=EudextError, expect_message="setup")
    def _(t):
        dbg.setup(map_name="again", build_id=4)

    s.build()
    ok = s.report()
    ck.true("등록 오류 5종", ok)
    dbg.reset()


FINALIZE_ERRORS = {
    "caps": "감시 칸이 모자랍니다",
    "probes": "프로브 칸이 모자랍니다",
    "phase_dup": "단계 번호 7",
    "scrdb": "SCR_DB",
    "late": "게임 루프 훅에서 칸을 이미 정했습니다",
}


def finalize_error_child(kind):
    """하위 프로세스: 빌드 끝(게임 루프 훅)에서 나야 하는 오류."""
    dbg.reset()
    LoadMap(BASE_MAP)
    CompressPayload(True)
    if kind == "caps":
        dbg.setup(map_name="e", build_id=1, watch_slots=2, symbols=SYMDIR)

        def body():
            dbg.watch("a", EUDVariable())
            dbg.watch("b", EUDVariable())
    elif kind == "probes":
        dbg.setup(map_name="e", build_id=1, probes=3, symbols=SYMDIR)

        def body():
            dbg.check("a", True)
            dbg.check("b", True)
    elif kind == "phase_dup":
        dbg.setup(map_name="e", build_id=1, symbols=SYMDIR)

        def body():
            dbg.suite_begin("a", phase=7)
            dbg.suite_begin("b", phase=7)
    elif kind == "scrdb":
        import types

        fake = types.ModuleType("eudext.scrdb")
        fake._current = types.SimpleNamespace(_regions={"anchor": (0x596000, 0x596400)})
        sys.modules["eudext.scrdb"] = fake
        dbg.setup(map_name="e", build_id=1, symbols=SYMDIR)

        def body():
            dbg.hit("a")
    else:
        dbg.setup(map_name="e", build_id=1, symbols=SYMDIR)
        _compat.on_game_loop_start(lambda: dbg.hit("late"))

        def body():
            dbg.hit("a")
    try:
        emu.Program(body).build()
    except EudextError as e:
        print("CAUGHT %s" % e)
        return 0
    except Exception as e:  # noqa: BLE001
        print("OTHER %s: %s" % (type(e).__name__, e))
        return 1
    print("NOERROR")
    return 1


def emu_finalize_errors(ck):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    for kind, needle in FINALIZE_ERRORS.items():
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--finalize-error", kind], env=env,
                           capture_output=True, timeout=300)
        out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
        caught = [line for line in out.splitlines() if line.startswith(("CAUGHT", "OTHER", "NOERROR"))]
        ck.true("빌드 끝 오류 %s" % kind, caught and caught[-1].startswith("CAUGHT") and needle in caught[-1],
                "\n".join(out.splitlines()[-8:]))


PER_FRAME = []


def emu_frame_costs(ck):
    """매 프레임 루프 시작 코드의 실행 트리거 수 (빈 프로그램 대비)."""
    def run(setup_fn, cycles=6, enable=True):
        dbg.reset()
        LoadMap(BASE_MAP)
        CompressPayload(True)
        if enable:
            dbg.setup(map_name="cost", build_id=9, symbols=SYMDIR)
        prog = emu.Program(lambda: None, setup=setup_fn)
        m = prog.build()
        scmodel.install(m)
        m.cycle()
        first = m.last_steps()
        steps = []
        for _ in range(cycles):
            m.cycle()
            steps.append(m.last_steps())
        return first, steps

    vs = [EUDVariable() for _ in range(8)]
    b_first, b_steps = run(None, enable=False)
    base = b_steps[-1]
    cases = [
        ("설정만 (seq·게임 프레임)", None),
        ("+ 변수 감시 1", lambda: dbg.watch("v0", vs[0])),
        ("+ 변수 감시 8", lambda: [dbg.watch("v%d" % i, vs[i]) for i in range(8)]),
        ("+ Int64 감시", lambda: dbg.watch("x", Int64(0))),
        ("+ 주소 감시 1", lambda: dbg.watch("m", 0x57F23C)),
        ("+ 스냅숏 16단어", lambda: dbg.snapshot("s", 0x58A364, 16)),
        ("+ 스냅숏 16단어 every=4 (평균)", lambda: dbg.snapshot("s", 0x58A364, 16, every=4)),
        ("+ 스냅숏 16단어 every=0 (capture 만)", lambda: dbg.snapshot("s", 0x58A364, 16, every=0)),
        ("+ 단계 1 (감시 없음)", lambda: [dbg.suite_begin("a"), dbg.suite_end("a")]),
    ]
    PER_FRAME.clear()
    first0, _s = run(None)
    PER_FRAME.append(("시작 1회 (쓰는 칸 지우기 + 머리 + 정적 사본 3회 + 서명)", first0 - b_first))
    for label, fn in cases:
        _f, steps = run(fn)
        per = round(sum(steps[-4:]) / 4 - base, 1) if "every=4" in label else steps[-1] - base
        PER_FRAME.append((label, per))
    for label, n in PER_FRAME:
        print("  매 프레임 비용 %-40s %s" % (label, n))
    d = dict(PER_FRAME)
    ck.true("설정만 ≤ 45 (seq 2 + dwread 약 36)", d["설정만 (seq·게임 프레임)"] <= 45, d)
    ck.true("변수 감시 1 추가 ≤ 설정 + 3", d["+ 변수 감시 1"] - d["설정만 (seq·게임 프레임)"] <= 3, d)
    ck.true("capture 만은 매 프레임 비용 0", d["+ 스냅숏 16단어 every=0 (capture 만)"] == d["설정만 (seq·게임 프레임)"], d)
    dbg.reset()


# =============================================================================================
# 3. 서명·epScript 예제
# =============================================================================================


def _eps_module(work_name):
    work = _fresh_dir(os.path.join(T, work_name))
    shutil.copy2(os.path.join(EX, "dbg_example.eps"), os.path.join(work, "dbg_example.eps"))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, "dbg_example.eps"), {})


def eps_checks(ck):
    src = open(os.path.join(EX, "dbg_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("dbg_example.eps", src)
    ck.eq("eps 오류 수", nerr, 0)
    for needle in ('dbg.f_setup(map_name="dbg_example")', 'dbg.f_watch("big", big)', 'dbg.f_snapshot_text("line", sb, 16)',
                   'DoActions(dbg.f_probe("second"))', 'dbg.f_suite_begin("g1", phase=1)', 'dbg.f_check("g1.big", big >= ',
                   'dbg.f_suite_end("g2", sec == 3)', 'dbg.f_result("g.total", 3, 3)', 'dbg.f_mark("done")'):
        ck.true("eps: " + needle, out is not None and needle in out, "")
    dbg.reset()
    os.environ["EUDEXT_DBG_DIR"] = SYMDIR
    try:
        mod = _eps_module("eps_emu")
        prog = emu.Program(mod.afterTriggerExec)
        m = prog.build()
    finally:
        del os.environ["EUDEXT_DBG_DIR"]
    scmodel.install(m)
    lay = dbg.layout()
    frames = []
    for i in range(130):
        m.setdw(0x57F23C, 2 * i)
        m.cycle()
        words = _block_words(m, lay["addr"], lay["total"])
        frames.append([0] * 8 + words[8:])
        if i == 99:
            at100 = words
    ck.eq("예제 자리·이름", (lay["addr"], lay["map_name"]), (0x596280, "dbg_example"))
    sym = R.load_symbols(SYMDIR, lay["build_id"])
    ck.true("예제 심볼 (EUDEXT_DBG_DIR)", sym.loaded and sym.ext["map_name"] == "dbg_example")
    v = R.ext_values(sym, at100)
    ck.eq("예제 값", (v["checks"], v["results"], v["marks"], v["hits"], v["watches"], v["texts"]["line"][0],
                    v["suites"], v["suite_now"]),
          ({"g1.frame": (1, 1), "g1.big": (1, 1), "g2.sec": (1, 1)}, {"g.total": (3, 3, 1)}, {"done": 1},
           {"tick": 100, "second": 4}, {"frame": 99, "sec": 4, "big": 99 * 10 ** 9, "elapsed": 198}, "eudext dbg 4 sec",
           {"g1": (2, 24, 24, 0), "g2": (2, 48, 72, 1)}, {"current": None, "last": "g2", "frame": 72}))
    # 예제 명세도 검사를 통과한다
    spec = A.load_specs([os.path.join(EX, "dbg_example_spec.json")])["dbg_example"]
    ck.eq("예제 명세", (spec["map"], [x["name"] for x in spec["suites"]], len(spec["items"])),
          ("dbg_example", ["g1", "g2"], 8))
    mp = {"sym": sym, "block_eud": lay["addr"], "build": lay["build_id"], "where": "mirror", "frames": frames,
          "mirrors": [{} for _ in frames]}
    run = simulate(spec, mp)
    ck.eq("예제 명세로 판정 (G-2 기대)", (run["verdict"], run["reason"], _suites(run), _items(run)),
          (A.PASS, "완료 표식", {"g1": A.PASS, "g2": A.PASS},
           {"G-2a": A.PASS, "G-2b": A.PASS, "G-2c": A.PASS, "G-2d": A.PASS, "G-2e": A.PASS, "G-2f": A.PASS,
            "G-2g": A.PASS, "G-2h": A.MANUAL}))
    dbg.reset()


def signature_checks(ck):
    dbg.reset()
    work = _fresh_dir(os.path.join(T, "sig"))
    shutil.copy2(os.path.join(EX, "dbg_example.eps"), os.path.join(work, "dbg_example.eps"))
    os.environ["EUDEXT_DBG_DIR"] = SYMDIR
    try:
        out = build.standalone([os.path.join(work, "dbg_example.eps")], out=os.path.join(work, "sig.scx"))
    finally:
        del os.environ["EUDEXT_DBG_DIR"]
    raw = open(out, "rb").read()
    chk = _compat.mpq_read_file(out, "staredit\\scenario.chk")
    ck.true("단독 빌드 chk 읽음", chk is not None and len(chk) > 10000, len(chk or b""))
    ck.true("서명이 scx 파일에 연속으로 없다", SIG not in raw)
    ck.true("서명이 scenario.chk 에 연속으로 없다", SIG not in (chk or b""))
    parts = sum(1 for w in dbg.SIGNATURE if struct.pack("<I", w) in (chk or b""))
    print("  서명 dword 가 chk 에 따로 보이는 수: %d / 8 (액션 값 칸에 흩어짐 — 0 이면 페이로드가 부호화돼 있다)" % parts)
    # 에뮬레이터 페이로드: 처음에는 없고, 돌린 뒤에는 블록 한 곳에만
    dbg.reset()
    LoadMap(BASE_MAP)
    CompressPayload(True)
    dbg.setup(map_name="sigp", build_id=5, addr="payload", symbols=SYMDIR)
    prog = emu.Program(lambda: dbg.hit("x"))
    prog.watch("blk", dbg.layout()["db"])
    m = prog.build()

    def payload_bytes():
        return b"".join(struct.pack("<I", m.dw(a)) for a in range(m.base, m.limit_addr, 4))

    ck.eq("에뮬레이터 페이로드: 처음 서명 수", payload_bytes().count(SIG), 0)
    m.cycle(2)
    data = payload_bytes()
    ck.eq("에뮬레이터 페이로드: 돌린 뒤 서명 = 블록 하나", (data.count(SIG), data.find(SIG) + m.base), (1, m.addr("blk")))
    dbg.reset()


def eps_build(ck):
    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return None
    work = _fresh_dir(os.path.join(T, "euddraft"))
    eds, out_map = build.prepare_eds(os.path.join(EX, "dbg_example.eds"), work)
    sym_dir = os.path.join(work, "dbg")
    text = open(eds, encoding="utf-8").read()
    text = re.sub(r"(?m)^DbgDir : .*$", lambda _m: "DbgDir : " + sym_dir, text)
    ck.true("eds DbgDir 절대 경로로 옮김", "DbgDir : " + sym_dir in text)
    with open(eds, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, "dbg_example.log"))
    print("  " + r.summary())
    ck.true("euddraft dbg_example", r.ok, r.log[-3000:])
    ck.true("eps 번역됨", '[epScript] Compiling "dbg_example.eps"' in r.log)
    ck.true("블록 줄", "[eudext.dbg] 블록 mirror 0x596280" in r.log, r.log[-2000:])
    files = sorted(os.listdir(sym_dir)) if os.path.isdir(sym_dir) else []
    ck.true("euddraft 심볼 (DbgDir)", any(re.match(r"DebugBridge_dbg_example_[0-9A-F]{8}\.json$", n) for n in files), files)
    if r.ok:
        chk = _compat.mpq_read_file(out_map, "staredit\\scenario.chk")
        ck.true("euddraft 맵: 서명이 연속으로 없다", SIG not in open(out_map, "rb").read() and SIG not in (chk or b""))
    # Dbg : 0 이면 꺼진다
    eds2 = eds.replace("dbg_example.eds", "dbg_example_off.eds")
    text2 = text.replace("DbgDir : ", "Dbg : 0\nDbgDir : ").replace("dbg_example_out.scx", "dbg_example_off.scx")
    with open(eds2, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text2)
    out2 = out_map.replace("dbg_example_out.scx", "dbg_example_off.scx")
    r2 = build.run_euddraft(eds2, out_map=out2, log_path=os.path.join(work, "dbg_example_off.log"))
    ck.true("euddraft Dbg : 0 빌드", r2.ok and "[eudext.dbg] 블록" not in r2.log, r2.log[-2000:])
    return r


# =============================================================================================
# 4. 판정 흐름 (에뮬레이터 스냅숏 → MapRun)
# =============================================================================================


def _suite_block(f, name, begin, end, phase=None, checks=(), ok=None, result=None):
    """f == begin 에 단계 시작, f == end 에 끝. checks = [(이름, 조건 만드는 함수)] (끝 프레임에)."""
    if EUDIf()(f == begin):
        dbg.suite_begin(name, phase=phase)
    EUDEndIf()
    if EUDIf()(f == end):
        for cname, cond in checks:
            dbg.check(cname, cond())
        if result is not None:
            dbg.result(*result)
        dbg.suite_end(name, None if ok is None else ok())
    EUDEndIf()


def build_scenario_map(name, build_id, where, cycles, body_fn, setup_fn=None):
    """맵 하나를 에뮬레이터로 돌려 프레임별 블록 스냅숏(서명 칸은 0)을 만든다."""
    dbg.reset()
    LoadMap(BASE_MAP)
    CompressPayload(True)
    dbg.setup(map_name=name, build_id=build_id, addr="payload" if where == "payload" else "top", symbols=SYMDIR)
    f = EUDVariable()

    def body():
        f.__iadd__(1)
        body_fn(f)

    prog = emu.Program(body, setup=(lambda: setup_fn(f)) if setup_fn else None)
    if where == "payload":
        prog.watch("blk", dbg.layout()["db"])
    m = prog.build()
    scmodel.install(m)
    lay = dbg.layout()
    addr = m.addr("blk") if where == "payload" else lay["addr"]
    frames, mirrors = [], []
    for k in range(1, cycles + 1):
        m.setdw(0x57F23C, 3 * k)
        m.cycle()
        words = _block_words(m, addr, lay["total"])
        frames.append([0] * 8 + words[8:])
        mirrors.append({0x57F23C: m.dw(0x57F23C), 0x58DC40: m.dw(0x58DC40)})
    sym = R.load_symbols(SYMDIR, build_id)
    dbg.reset()
    return {"name": name, "build": build_id, "where": where, "block_eud": addr if where == "mirror" else None,
            "frames": frames, "mirrors": mirrors, "sym": sym}


def make_maps():
    maps = {}

    def body_a(f):
        dbg.hit("tick")
        dbg.check("A.pos", f >= 1)
        if EUDIf()(f == 60):
            dbg.result("A.res", 7, 7)
            dbg.mark("done")
        EUDEndIf()

    big = Int64(12345678901234)
    msg = Db(b"hello A\0")

    def setup_a(f):
        dbg.watch("f", f)
        dbg.watch("big", big)
        dbg.snapshot_text("msg", msg, 2)

    maps["A"] = build_scenario_map("t_A", 0xA1, "mirror", 150, body_a, setup_a)

    def body_b(f):
        dbg.check("B.ok", f >= 1)
        dbg.check("B.bad", f == 0)
        if EUDIf()(f == 20):
            dbg.mark("done")
        EUDEndIf()

    maps["B"] = build_scenario_map("t_B", 0xB2, "payload", 150, body_b)

    def body_d(f):
        dbg.hit("tick")
        _suite_block(f, "d1", 60, 75, phase=1, checks=[("d1.x", lambda: f == 75)])
        _suite_block(f, "d2", 80, 95, phase=2, checks=[("d2.y", lambda: f >= 80)], ok=lambda: f == 95)
        _suite_block(f, "d3", 100, 115, phase=3, result=("d3.r", 3, 3))

    maps["D"] = build_scenario_map("t_D", 0xD4, "mirror", 150, body_d)

    def stall_body(prefix):
        def body(f):
            _suite_block(f, prefix + "1", 3, 6, checks=[(prefix + "1.a", lambda: f == 6)])
            _suite_block(f, prefix + "2", 8, 200, checks=[(prefix + "2.a", lambda: f == 200)])
            _suite_block(f, prefix + "3", 210, 220)
        return body

    maps["C"] = build_scenario_map("t_C", 0xC3, "mirror", 90, stall_body("c"))
    maps["E"] = build_scenario_map("t_E", 0xE5, "payload", 90, stall_body("e"))
    return maps


def write_specs(specdir):
    _fresh_dir(specdir)
    specs = {
        "A": _spec(map="t_A", title="통과 맵", checklist={"row": "02", "section": "1.1"}, items=[
            {"kind": "check", "name": "A.pos", "checklist": {"row": "C3-1"}},
            {"kind": "result", "name": "A.res", "total": 7},
            {"kind": "watch", "name": "f", "min": 20},
            {"kind": "watch", "name": "big", "equals": "12345678901234"},
            {"kind": "text", "name": "msg", "equals": "hello A"},
            {"kind": "hit", "name": "tick", "min": 20},
            {"kind": "hdr", "field": "local_player", "equals": 0},
            {"kind": "peek", "addr": "0x57F23C", "min": 1},
            {"kind": "wall", "metric": "fps", "min": 1},
            {"kind": "watch", "name": "f", "id": "f.ever", "min": 40, "max": 55, "when": "ever"},
            {"kind": "manual", "id": "V-A", "expect": "화면 확인", "checklist": True},
        ]),
        "B": _spec(map="t_B", title="실패 맵", items=[
            {"kind": "check", "name": "B.ok"},
            {"kind": "all_checks"},
            {"kind": "peek", "addr": "0x57F23C", "id": "B.peek"},
        ]),
        "D": _spec(map="t_D", title="단계 맵", suites=[
            {"name": "d2", "timeout_s": 60, "checklist": "C3-2"},
        ], items=[
            {"kind": "hit", "name": "tick", "phase": 3, "min": 100, "id": "d3.tick"},
            {"kind": "wall", "metric": "seconds", "suite": "d1", "min": 0.01, "id": "d1.secs"},
        ]),
        "C": _spec(map="t_C", title="멈춤 맵", stall_s=1.0, suites=[{"name": "c2", "stall_s": 1.0}]),
        "E": _spec(map="t_E", title="튕김 맵", stall_s=5.0),
    }
    for key, doc in specs.items():
        with open(os.path.join(specdir, "spec_%s.json" % key), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
    return A.load_specs([specdir])


def simulate(spec, mp, fps=24.0, end="stall", say=None):
    """스냅숏을 차례로 넣어 판정. end: 프레임이 끝난 뒤 "stall"(마지막 프레임을 계속) 또는 "crash"."""
    t = 1000.0
    mirror = {}

    def peek(addr, n):
        return tuple(mirror.get(addr + 4 * i, 0) for i in range(n))

    run = A.MapRun(spec, mp["sym"], mp["block_eud"] or 0x10000000, mp["build"], now=t, where=mp["where"],
                   say=say, peek=peek)
    last_change = t
    for d, mir in zip(mp["frames"], mp["mirrors"]):
        t += 1.0 / fps
        mirror.clear()
        mirror.update(mir)
        last_change = t
        got = run.feed(d, t)
        if got:
            return run.judge(got[0], got[1], d)
    if end == "crash":
        return run.judge("튕김 — 게임 프로세스 끝남 (시험)", "crash")
    while True:
        t += 0.1
        got = run.feed(mp["frames"][-1], t)
        if got:
            return run.judge(got[0], got[1], mp["frames"][-1])
        if t - last_change >= run.stall_limit():
            return run.judge("멈춤 — 프레임이 %g초 동안 늘지 않음" % run.stall_limit(), "stall")


def _items(run):
    return {x["id"]: x["verdict"] for x in run["items"]}


def _suites(run):
    return {s["name"]: s["status"] for s in run["suites"]}


def check_runs(ck, runs, label):
    a, b, dd, c, e = (runs[k] for k in "ABDCE")
    ck.eq(label + " A 판정", (a["verdict"], a["cause"], a["reason"]), (A.PASS, "done", "완료 표식"))
    ck.eq(label + " A 항목", _items(a), {"A.pos": A.PASS, "A.res": A.PASS, "f": A.PASS, "big": A.PASS, "msg": A.PASS,
                                        "tick": A.PASS, "local_player": A.PASS, "peek": A.PASS, "fps": A.PASS,
                                        "f.ever": A.PASS, "V-A": A.MANUAL})
    ck.eq(label + " B 판정", (b["verdict"], _items(b)), (A.FAIL, {"B.ok": A.PASS, "all_checks": A.FAIL, "B.peek": A.FAIL}))
    ck.true(label + " B 사유", "B.bad 0/" in next(x["detail"] for x in b["items"] if x["id"] == "all_checks") and
            "peek 불가" in next(x["detail"] for x in b["items"] if x["id"] == "B.peek"), b["items"])
    ck.eq(label + " D 판정", (dd["verdict"], dd["reason"], _suites(dd)),
          (A.PASS, "모든 단계 끝", {"d1": A.PASS, "d2": A.PASS, "d3": A.PASS}))
    ck.eq(label + " D 단계 번호·프레임", [(s["no"], s["begin"], s["end"], s["verdict_slot"]) for s in dd["suites"]],
          [(1, 60, 75, 0), (2, 80, 95, 1), (3, 100, 115, 0)])
    ck.eq(label + " D 단계 항목", {s["name"]: [x["id"] for x in s["items"]] for s in dd["suites"]},
          {"d1": ["d1.secs", "all_checks:d1"], "d2": ["all_checks:d2"], "d3": ["d3.tick", "all_checks:d3"]})
    ck.eq(label + " C 판정", (c["verdict"], c["cause"], _suites(c)),
          (A.FAIL, "stall", {"c1": A.PASS, "c2": A.STALLED, "c3": A.NOT_RUN}))
    ck.true(label + " C 사유에 단계", "c2" in c["reason"] and "멈춤" in c["reason"], c["reason"])
    ck.eq(label + " C 마지막으로 본 단계", (c["last_seen"]["suite"], c["last_seen"]["frame"]), ("c2", 8))
    ck.eq(label + " E 판정", (e["verdict"], e["cause"], _suites(e)),
          (A.FAIL, "crash", {"e1": A.PASS, "e2": A.CRASHED, "e3": A.NOT_RUN}))
    ck.true(label + " E 사유", "튕김" in e["reason"] and "e2" in e["reason"], e["reason"])


def offline_judge(ck, maps, specs):
    notes = []
    runs = {}
    for key in "ABDC":
        runs[key] = simulate(specs[maps[key]["name"]], maps[key], say=notes.append)
    runs["E"] = simulate(specs["t_E"], maps["E"], end="crash", say=notes.append)
    check_runs(ck, runs, "오프라인")
    for needle in ("단계 d1 (1) 시작 (프레임 60)", "단계 d1 끝 (프레임 75)", "단계 d2: 통과", "단계 c2 (2) 시작 (프레임 8)"):
        ck.true("진행 알림: " + needle, any(needle in n for n in notes), notes)
    lines = A.run_lines(runs["C"])
    ck.true("사람이 읽는 줄", lines[0].startswith("맵 t_C (빌드 000000C3): 실패") and any("단계 c2" in x and "멈춤" in x
                                                                                       for x in lines), lines)
    # 단계 시간 초과·ever·맵 제한 시간
    spec = A.check_spec(_spec(map="t_D", suites=[{"name": "d2", "timeout_cycles": 3}]), "timeout")
    r = simulate(spec, maps["D"])
    ck.eq("단계 시간 초과", (_suites(r)["d2"], r["verdict"]), (A.FAIL, A.FAIL))
    ck.true("단계 시간 초과 사유", "단계 시간 초과 (사이클 3)" in r["suites"][1]["reason"], r["suites"][1])
    spec = A.check_spec(_spec(map="t_A", done=["never"], timeout_s=2.0, items=[{"kind": "mark", "name": "done"}]), "to")
    r = simulate(spec, maps["A"])
    # 시간 초과 설명에는 관측한 초당 사이클이 붙는다(터보 기준 — 8 밑이면 [eudTurbo] 안내까지, DESIGN 5.6)
    ck.eq("맵 시간 초과", (r["verdict"], r["cause"], r["reason"].split(" — ")[0]),
          (A.FAIL, "timeout", "시간 초과 (2초)"))
    ck.true("맵 시간 초과 — 초당 사이클", "초당 사이클" in r["reason"], r["reason"])
    spec = A.check_spec(_spec(map="t_A", done=[], items=[{"kind": "mark", "name": "done"},
                                                         {"kind": "watch", "name": "f", "min": 30}]), "all")
    r = simulate(spec, maps["A"])
    ck.eq("done 없이 모든 항목 통과", (r["verdict"], r["reason"]), (A.PASS, "모든 항목 통과"))
    ck.true("심볼 없는 단계", A.check_spec(_spec(map="t_A", suites=[{"name": "zz"}]), "zz") is not None)
    r = simulate(A.check_spec(_spec(map="t_A", suites=[{"name": "zz"}]), "zz"), maps["A"])
    ck.eq("심볼 없는 단계 = 실패", (_suites(r), r["verdict"]), ({"zz": A.FAIL}, A.FAIL))
    return runs


# =============================================================================================
# 5. 통합 (Windows): 가짜 게임 프로세스 + 리더 + 자동 판정
# =============================================================================================


def _scenario(maps, keys, fps, hold, tail, start_delay):
    out = []
    for k in keys:
        mp = maps[k]
        mir = []
        if mp["where"] == "mirror":
            mir = [[0x58DC40, 0x80000005], [0x58DC44, 129]]
        out.append({"name": mp["name"], "where": mp["where"], "block_eud": mp["block_eud"], "frames": mp["frames"],
                    "mirror": mir, "fps": fps, "hold": hold.get(k, 1.0), "gap": 0.003})
    return {"maps": out, "tail": tail, "start_delay": start_delay}


class _Lines:
    """하위 프로세스 표준 출력을 줄 단위로 모은다."""

    def __init__(self, proc):
        self.lines = []
        self.proc = proc
        self.t = threading.Thread(target=self._read, daemon=True)
        self.t.start()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.append(line.rstrip("\n"))

    def wait_for(self, prefix, timeout):
        end = time.time() + timeout
        while time.time() < end:
            for line in self.lines:
                if line.startswith(prefix):
                    return line
            if self.proc.poll() is not None and not self.t.is_alive():
                break
            time.sleep(0.02)
        return None


def _env():
    return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")


def _run_py(args, timeout=60):
    p = subprocess.run([sys.executable, *args], env=_env(), capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")


def win32_legacy(ck):
    """원래의 가짜 게임 자체 시험 모드(CtrigAsm DebugBridge 식 심볼)를 고친 리더가 그대로 읽는가."""
    if not R.WIN32:
        return
    work = _fresh_dir(os.path.join(T, "legacy"))
    sym, vs = os.path.join(work, "sym.json"), os.path.join(work, "VARSTACK.txt")
    fake = subprocess.Popen([sys.executable, FAKE, "--symbols", sym, "--varstack", vs, "--seconds", "20"], env=_env(),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    fl = _Lines(fake)
    try:
        line = fl.wait_for("PID ", 30)
        ck.true("원래 가짜 게임 시작", line is not None, fl.lines)
        if line is None:
            return
        time.sleep(1.0)
        pid = line.split()[1]
        rc, out = _run_py([READER, "--pid", pid, "--symbols", sym, "--once"])
        for needle in ("[심볼 일치]", "minus_frame", "frame@", "직접 ", "(Ccode 위치 계산용, 자동)", "every_3rd_frame"):
            ck.true("원래 모드 --once: " + needle, rc == 0 and needle in out, out[-1500:])
        ck.true("원래 모드: eudext 칸 없음", "-- eudext" not in out)
        rc, out = _run_py([READER, "--pid", pid, "--symbols", sym, "--varstack", vs, "--vars", "Fake", "--once"],
                          timeout=90)
        for needle in ("FakeConst", "1234", "FakeSec", "다른 스택(P1"):
            ck.true("원래 모드 --vars: " + needle, rc == 0 and needle in out, out[-1500:])
    finally:
        fake.kill()
        fake.wait(timeout=30)


def win32_integration(ck, maps, specdir):
    if not R.WIN32:
        print("  Windows 가 아님 — 통합 시험 건너뜀")
        return
    work = _fresh_dir(os.path.join(T, "win32"))
    scen1 = os.path.join(work, "scen1.json")
    with open(scen1, "w", encoding="utf-8") as f:
        json.dump(_scenario(maps, "ABDC", fps=60, hold={"A": 1.0, "B": 1.0, "D": 1.0, "C": 3.0}, tail=3.0,
                            start_delay=1.5), f)
    copy = os.path.join(work, "checklist_copy.md")
    if os.path.isfile(REAL_CHECKLIST):
        shutil.copy2(REAL_CHECKLIST, copy)
        text = open(copy, encoding="utf-8").read()
        # 사용자가 이미 적은 칸 흉내 (C3-2 행)
        text = re.sub(r"(?m)^(\| C3-2 \|.*\|)[ \t]*\|[ \t]*$", lambda m: m.group(1) + " 통과 (사용자) |", text)
        with open(copy, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    else:
        with open(copy, "w", encoding="utf-8") as f:
            f.write(CHECKLIST_FIXTURE)
    before_copy = open(copy, encoding="utf-8").read()
    fake = subprocess.Popen([sys.executable, FAKE, "--replay", scen1], env=_env(), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    fl = _Lines(fake)
    auto = None
    try:
        ready = fl.wait_for("READY", 30)
        ck.true("가짜 게임 READY", ready is not None, fl.lines)
        if ready is None:
            return
        pid = ready.split()[1]
        out1 = os.path.join(work, "results.json")
        log1 = os.path.join(work, "auto.log")
        auto = subprocess.Popen([sys.executable, AUTO, "--specs", specdir, "--symbols", SYMDIR, "--pid", pid,
                                 "--out", out1, "--log", log1, "--maps", "4", "--poll", "0.02", "--scan-interval", "0.2",
                                 "--busy-scan-interval", "0.5", "--progress", "0.5", "--stall", "5",
                                 "--max-seconds", "90", "--write-checklist", copy, "--date", "2026-09-18"],
                                env=_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8")
        al = _Lines(auto)
        ck.true("맵 A 재생", fl.wait_for("MAP 0", 30) is not None)
        time.sleep(0.4)
        rc, out = _run_py([READER, "--pid", pid, "--once", "--symbols", SYMDIR])
        for needle in ("빌드 161 [심볼 일치]", "-- eudext: 맵 t_A", "판정 A.pos", "글   msg", "'hello A'", "  f  "):
            ck.true("리더 --once: " + needle, rc == 0 and needle in out, out[-1500:])
        rc, out = _run_py([READER, "--pid", pid, "--peek", "0x57F23C", "0x58DC40:2", "--symbols", SYMDIR])
        vals = re.findall(r"EUD 0x(\w+)\s+(\d+)", out)
        got = {int(a, 16): int(b) for a, b in vals}
        ck.true("리더 --peek 게임 프레임(미러 버퍼)", rc == 0 and got.get(0x57F23C, 0) > 0 and got.get(0x57F23C) % 3 == 0,
                out[-800:])
        ck.eq("리더 --peek 스위치 표", (got.get(0x58DC40), got.get(0x58DC44)), (0x80000005, 129))
        rc, out = _run_py([READER, "--pid", pid, "--diag", "--symbols", SYMDIR])
        ck.true("리더 --diag", rc == 0 and "game_frame" in out and "일치" in out, out[-1500:])
        ck.true("맵 D 재생", fl.wait_for("MAP 2", 40) is not None)
        rec = os.path.join(work, "record.tsv")
        rc, out = _run_py([READER, "--pid", pid, "--symbols", SYMDIR, "--record", rec, "--record-seconds", "2.5",
                           "--record-watch", "d1.x", "tick", "--record-keys", "--interval", "0.02"], timeout=60)
        rtext = open(rec, encoding="utf-8").read() if os.path.isfile(rec) else ""
        for needle in ("\t시작\t", "\t박동\t", "\t단계\td1\t시작", "\t단계\td1\t끝", "\t값\td1.x", "\t끝\t"):
            ck.true("리더 --record: " + needle.strip(), needle in rtext, rtext[-1500:])
        rc = auto.wait(timeout=120)
        auto_out = "\n".join(al.lines)
        ck.eq("ingame_auto 종료 코드 (실패 맵 포함 → 1)", rc, 1)
        doc = json.load(open(out1, encoding="utf-8"))
        runs = {r["map"][-1]: r for r in doc["runs"]}
        ck.eq("판정한 맵 순서", [r["map"] for r in doc["runs"]], ["t_A", "t_B", "t_D", "t_C"])
        for needle in ("판정 시작", "단계 d1 (1) 시작", "진행: 맵 t_D", ">>> 다음 맵을 여세요", "멈춤", "확인 문서 C3-1"):
            ck.true("ingame_auto 출력: " + needle, needle in auto_out, auto_out[-3000:])
        ck.true("로그 파일", os.path.isfile(log1) and "다음 맵을 여세요" in open(log1, encoding="utf-8").read())
        prog = json.load(open(out1 + ".progress.json", encoding="utf-8"))
        ck.eq("진행 파일 (마지막 맵)", (prog["map"], prog.get("finished"), prog["last_seen"]["suite"]),
              ("t_C", True, "c2"))
        # 튕김: 두 번째 가짜 게임은 맵 E 가 단계 도중에 프로세스를 끝낸다
        scen2 = os.path.join(work, "scen2.json")
        with open(scen2, "w", encoding="utf-8") as f:
            json.dump(_scenario(maps, "E", fps=60, hold={"E": 0.5}, tail=0.0, start_delay=1.0), f)
        fake2 = subprocess.Popen([sys.executable, FAKE, "--replay", scen2], env=_env(), stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8")
        fl2 = _Lines(fake2)
        ready2 = fl2.wait_for("READY", 30)
        out2 = os.path.join(work, "results.json")  # 같은 파일에 덧붙인다
        rc2, text2 = _run_py([AUTO, "--specs", specdir, "--symbols", SYMDIR, "--pid", ready2.split()[1], "--out", out2,
                              "--maps", "1", "--poll", "0.02", "--scan-interval", "0.2", "--busy-scan-interval", "0.5",
                              "--progress", "0.5", "--max-seconds", "60"], timeout=120)
        fake2.wait(timeout=30)
        doc = json.load(open(out2, encoding="utf-8"))
        ck.eq("결과 누적", [r["map"] for r in doc["runs"]], ["t_A", "t_B", "t_D", "t_C", "t_E"])
        runs["E"] = doc["runs"][-1]
        ck.true("튕김 출력", "튕김" in text2 and "e2" in text2, text2[-2000:])
        check_runs(ck, runs, "Win32")
        # 확인 문서 사본: 빈 칸만
        # 확인 문서 사본은 **사용자 문서**(REAL_CHECKLIST)의 사본이다 — 그 행이 이미 채워져 있거나 행이 여러 개면
        # 도구가 건드리지 않는 것이 옳다. 그래서 "빈 칸만 쓴다 + 채워진 칸은 그대로" 만 본다(고정 개수 대신).
        after = open(copy, encoding="utf-8").read()
        changed = [(x, y) for x, y in zip(before_copy.split("\n"), after.split("\n")) if x != y]
        ck.true("확인 문서 사본: 바뀐 줄 수", len(changed) <= 2, changed)
        ck.true("확인 문서 사본: 빈 칸에만 씀", all(_x.rstrip().endswith("| |") and
                                              y.endswith("| 자동: 통과 (2026-09-18) |") for _x, y in changed), changed)
        empty_c31 = re.search(r"(?m)^\| C3-1 \|.*\|[ \t]*\|[ \t]*$", before_copy) is not None
        if empty_c31 and before_copy.count("\n| C3-1 |") == 1:
            ck.true("확인 문서 사본: C3-1 행", any(y.startswith("| C3-1 |") and
                                              y.endswith("| 자동: 통과 (2026-09-18) |") for _x, y in changed), changed)
        else:
            ck.true("확인 문서 사본: 채워진 C3-1 행은 그대로",
                    not any(y.startswith("| C3-1 |") for _x, y in changed), changed)
        ck.true("확인 문서 사본: 사용자가 적은 칸은 그대로",
                all("| C3-2 |" not in y for _x, y in changed), changed)
        ck.true("확인 문서: 손대지 않음 보고", ("확인 문서 C3-2: 이미 적힘 — 그대로" in auto_out or
                                        "확인 문서 C3-2: 행이 여러 개" in auto_out), auto_out[-2000:])
    finally:
        for p in (auto, fake):
            if p is not None and p.poll() is None:
                p.kill()
        fake.wait(timeout=30)


# =============================================================================================
# 비용 (tools/cost.py)
# =============================================================================================


def _cost_ready():
    if not dbg.f_enabled():
        dbg.setup(map_name="cost", build_id=11, symbols=os.path.join(T, "cost_sym"))


def _cost(fn):
    def build_fn(t):
        _cost_ready()
        fn(t)
    return build_fn


def _capture_case():
    # 빌드마다 한 번 등록하고 capture 만 여러 번 (페이로드 측정은 한 빌드에 40벌)
    if not any(it.name == "cap" for it in dbg._bridge.items()):
        dbg.snapshot("cap", 0x58A364, 16, every=0)
    dbg.capture("cap")


COST_CASES = [
    CostCase("hit(이름)", _cost(lambda t: dbg.hit("h"))),
    CostCase("hit(이름, 조건)", _cost(lambda t: dbg.hit("h2", t.var("v") >= 3)), {"v": 5}),
    CostCase("hit(이름, 변수)", _cost(lambda t: dbg.hit("h3", t.var("v"))), {"v": 1}),
    CostCase("DoActions(probe)", _cost(lambda t: DoActions(dbg.probe("p")))),
    CostCase("check(이름, 조건)", _cost(lambda t: dbg.check("c", t.var("v") == 5)), {"v": 5}),
    CostCase("check(이름, 변수)", _cost(lambda t: dbg.check("c2", t.var("v"))), {"v": 1}),
    CostCase("check(이름, 상수)", _cost(lambda t: dbg.check("c3", True))),
    CostCase("result(이름, 변수, 상수)", _cost(lambda t: dbg.result("r", t.var("v"), 7)), {"v": 5}),
    CostCase("mark(이름)", _cost(lambda t: dbg.mark("m"))),
    CostCase("mark(이름, 변수)", _cost(lambda t: dbg.mark("m2", t.var("v"))), {"v": 5}),
    CostCase("suite_begin", _cost(lambda t: dbg.suite_begin("s"))),
    CostCase("suite_end(이름, 조건)", _cost(lambda t: dbg.suite_end("s2", t.var("v") == 5)), {"v": 5}),
    CostCase("capture (16단어)", _cost(lambda t: _capture_case())),
]


# =============================================================================================


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--finalize-error":
        sys.exit(finalize_error_child(sys.argv[2]))
    _fresh_dir(SYMDIR)
    ck = Checker("t_dbg (python)")
    python_checks(ck)

    cke = Checker("t_dbg (에뮬레이터)")
    emu_layout(cke)
    emu_payload(cke)
    emu_disabled(cke)
    emu_frame_costs(cke)
    emu_build_errors(cke)
    emu_finalize_errors(cke)

    cks = Checker("t_dbg (서명·epScript)")
    signature_checks(cks)
    eps_checks(cks)
    eps_build(cks)

    ckj = Checker("t_dbg (판정 흐름)")
    maps = make_maps()
    specdir = os.path.join(T, "specs")
    specs = write_specs(specdir)
    offline_judge(ckj, maps, specs)

    ckw = Checker("t_dbg (Win32 통합)")
    win32_legacy(ckw)
    win32_integration(ckw, maps, specdir)
    finish(ck.report(), cke.report(), cks.report(), ckj.report(), ckw.report())


if __name__ == "__main__":
    main()
