"""인게임 자동 판정 — 디버그 브리지 블록을 읽어 맵별 판정 명세와 맞춰 본다 (DESIGN 5.5).

    python eudext/tools/ingame_auto.py --specs <명세 폴더 또는 파일 …> [--out 결과.json] [--log 결과.log]
           [--symbols <심볼 폴더>] [--pid N] [--maps N] [--write-checklist <확인 문서.md>]

StarCraft(또는 `--pid` 로 준 프로세스)에 **읽기 전용**으로 붙어 `eudext.dbg` 블록을 기다린다. 맵을 열면 블록의 빌드 ID 로
심볼 JSON 을 찾고(`--symbols`, 기본은 리더와 같은 후보), 심볼의 맵 이름(`dbg.setup(map_name=…)`)으로 명세를 고른다.
완료 표식이 서거나 모든 단계가 끝나거나 제한 시간이 지나면 판정해 결과를 남기고 "다음 맵을 여세요" 를 알린다. 여러 맵을
차례로 열어도 된다(Ctrl+C 로 끝, `--maps N` 이면 N 개 판정 뒤 끝). 싱글·LAN 시험 전용(외부 프로세스 메모리 읽기).

**단계(suite) — 자동 점검 통합 맵**: 맵이 `dbg.suite_begin/suite_end` 로 점검 단계를 남기면 단계마다 시작·끝을 실시간으로
알리고, 단계가 끝날 때 그 단계의 항목을 판정한다. 블록의 프레임(seq)이 `stall_s` 초 동안 늘지 않으면 "멈춤: <단계>",
게임 프로세스가 사라지면 "튕김: <단계>" 로 끝내고 나머지 단계는 "미실행" 으로 남긴다(마지막으로 본 단계·프레임을 기록).
진행 상태는 `<결과>.progress.json` 에도 계속 쓴다(도구가 먼저 죽어도 어디까지 봤는지 남는다).

**시간 판정은 터보 기준**이다: 확인 맵은 모두 `[eudTurbo]`(트리거를 매 프레임 실행)로 빌드하므로 트리거 한 사이클 =
게임 한 프레임, 초당 약 24 사이클(`TURBO_CPS`)이다. 명세의 `timeout_s` 는 "프레임 창 ÷ 24 + 여유", `timeout_cycles` 는
프레임 창 그대로 잡는다. 터보가 빠진 맵은 한 사이클이 28~30프레임(약 1.2초) 간격이라(인게임 G-1, 2026-09-18) 시간
초과로 끝나고, 그 설명에 관측한 초당 사이클과 `[eudTurbo] 가 빠진 것 같습니다` 안내가 붙는다. 통합 맵은 첫 단계에서
터보 자체를 점검한다(G-5 `aa.turbo` — 24 사이클이 게임 프레임 40 안에 지나는지).

## 판정 명세 (JSON, 맵 하나에 파일 하나 — 폴더를 주면 `*.json` 가운데 format 이 맞는 것만)

    {
      "format": "eudext-ingame-spec", "version": 1,
      "map": "90_auto_all",                // dbg.setup(map_name=…) 과 같은 이름 (필수)
      "title": "자동 점검 통합 맵",          // 표시용 (선택)
      "done": ["done"],                     // 모두 0 이 아니면 맵 판정. 없으면: 심볼에 "done" 표식이 있으면 ["done"], 없으면 []
                                            //   ([] 이면 단계가 있는 맵은 모든 단계가 끝날 때, 없는 맵은 모든 항목이 통과할 때)
      "timeout_s": 600,                     // 맵 전체 벽시계 제한 (기본 300)
      "timeout_cycles": 20000,              // 맵 전체 트리거 사이클(seq) 제한 (선택)
      "stall_s": 10,                        // 프레임이 이만큼 안 늘면 멈춤 (기본: 도구의 --stall, 15초)
      "settle_cycles": 2,                   // 완료·단계 끝 뒤 기다릴 사이클 (기본 2)
      "checklist": {"row": "02", "section": "1.1"},   // 맵 전체 결과를 적을 확인 문서 행 (선택, 목록도 됨)
      "items": [ … 맵 항목 … ],
      "suites": [                           // 단계별 설정 (선택). 심볼에만 있는 단계도 기본 규칙으로 판정한다
        {"name": "c3", "timeout_s": 30, "timeout_cycles": 720, "stall_s": 5, "checklist": "C3-1",
         "items": [ … 단계 항목 … ]},     // 없으면 {"kind": "all_checks", "suite": 이름} 하나 (그 단계의 check·result 전부)
        {"name": "assist", "optional": true}   // 선택 단계: 맵이 시작하지 않았으면 "건너뜀"(실패 아님, 확인 문서에 안 씀)
      ]
    }

항목:

    {"id": "C3-1", "kind": "check", "name": "C3-1", "total": 3, "checklist": "C3-1"}
    {"id": "C3-7", "kind": "result", "name": "C3-7", "total": 23}
    {"id": "hp",   "kind": "watch", "name": "hp", "equals": 5}          // 또는 "min"/"max"/"in": [..]
    {"id": "big",  "kind": "watch", "name": "gold", "equals": "12345678901234", "when": "ever"}
    {"id": "tick", "kind": "hit", "name": "tick", "min": 24}
    {"id": "st",   "kind": "mark", "name": "stage", "equals": 3}        // 기본: 0 이 아님
    {"id": "line", "kind": "text", "name": "line", "contains": "HP 5"}  // "equals"/"regex"/"contains", 기본: 빈 글 아님
    {"id": "raw",  "kind": "dwords", "name": "arr", "equals": [1, 2, 3]}
    {"id": "all",  "kind": "all_checks", "suite": "c3"}                   // check·result 전부 (suite 를 주면 그 단계만:
                                                                          //   심볼 suite 가 같거나 이름이 "c3." 으로 시작)
    {"id": "sw",   "kind": "peek", "addr": "0x58DC40", "count": 2, "equals": [2147483653, 129]}  // 미러 주소 직접 읽기
                                                                          //   (미러 블록만. 1칸이면 min/max/mask 도)
    {"id": "lp",   "kind": "hdr", "field": "local_player", "in": [128, 129, 130, 131]}  // 머리: seq·game_frame·
                                                                          //   local_player·build·player_info·map_path
    {"id": "fps",  "kind": "wall", "metric": "max_gap_s", "max": 0.5}     // 벽시계: fps·max_gap_s·seconds
                                                                          //   (단계 안 항목이면 그 단계 구간만)
    {"id": "A-3",  "kind": "group", "items": [ {…}, {…} ], "checklist": true}   // 모두 통과해야 통과
    {"id": "D6-1", "kind": "manual", "expect": "색·정렬이 원본과 같다"}    // 사람 확인 (판정·확인 문서 쓰기에서 뺀다)
    {"id": "line", "kind": "text", "name": "chat", "offset": 218, "length": 218, "contains": "…"}  // 글의 바이트 구간

- 분류 파일(`docs/ingame_auto/classification.json`) 항목의 설명 필드 `read`·`expect`·`done_marker`·`phase`·`category`·
  `doc_section`·`required`·`map`·`bundle`·`notes`·`risk`·`extra`·`instrument` 를 **그대로** 항목에 둘 수 있다
  (판정에는 쓰지 않고 결과의 `info` 로 옮긴다). `phase`(정수)나 `suite`(이름)가 있는 맵 항목은 그 단계의 항목이 된다
  (단계는 이름, 또는 `dbg.suite_begin(…, phase=N)` 의 번호로 짝짓는다). `"checklist": true` 는 id 가 행 번호라는 뜻.
- 단계 설정의 `"all_checks": false` 는 그 단계의 기본 항목(단계의 check·result 전부)을 뺀다.
- 단계 설정의 `"optional": true` 는 선택 단계다(사람 조작 구간 등). 맵 판정 때까지 시작하지 않았으면 상태 "건너뜀" —
  맵 판정을 실패로 만들지 않고, 그 단계의 항목·행은 확인 문서에 쓰지 않는다. 시작했으면 보통 단계와 같다(2026-09-18 추가).

- `check`: 통과 == 전체 ≥ 1, `total` 을 주면 전체 == total. `"total": "sites"` 면 심볼에 적힌 호출 자리 수.
- `result`: 보고 ≥ 1, 통과 == 전체, `total` 을 주면 전체 == total.
- `watch`: 64·128비트는 합친 값, 심볼의 signed 이면 부호 있게. `equals` 에 문자열(10진·0x)을 줄 수 있다.
- `when`: `"final"`(기본 — 판정 순간의 값) 또는 `"ever"`(한 번이라도 맞으면 통과 — 지나가는 값).
- `checklist`: `"행 번호"`, `{"row": …, "section": …}` 또는 그 목록. `section` 은 행 위 제목(####·### …)에 든 글자.
- 이름이 심볼에 없으면 그 항목은 실패("심볼에 없음")다. 단계 판정: 항목이 모두 통과하고 맵이 `suite_end(…, ok)` 로
  실패를 적지 않았으면 통과. 단계에 check·result 가 하나도 없으면 끝난 것만으로 통과(맵 판정이 있으면 그것).

## 결과

- `--out`(기본 `EUDEXT_WORK/ingame_auto/results.json`): `{"format": "eudext-ingame-results", "runs": [판정 한 번 …]}` 에 덧붙인다.
  판정 한 번: map·title·build_id·build_tag·where·block·started·finished·seq·reason·cause("done"/"timeout"/"stall"/"crash"/"other")·
  verdict("통과"/"실패")·last_seen{seq, frame, suite, time}·items[…]·suites[name·no·status("통과"/"실패"/"미실행"/"멈춤"/"튕김")·
  begin·end·seconds·reason·verdict_slot·items[…]]. 항목: id·kind·name·verdict·detail·value·checklist.
- `--log`: 화면에 찍은 사람이 읽는 줄을 같은 파일에 덧붙인다. 판정 중에는 `--progress` 초마다 진행 줄을 찍는다.
- `--write-checklist 문서.md`(선택): 명세의 `checklist` 행 "결과" 칸이 **비어 있을 때만** `자동: 통과 (날짜)` /
  `자동: 실패 — 이유 (날짜)` 를 쓴다. 이미 무언가 적힌 칸은 절대 바꾸지 않는다. 표의 마지막 머리 칸에 "결과" 가 없으면 쓰지 않는다.
  같은 행이 여러 개면(구역을 안 줬을 때) 쓰지 않고 알린다. `--dry-run-checklist` 는 쓰지 않고 할 일만 보인다.

출처: 새로 작성. 블록 찾기·읽기는 `tools/debugbridge/dbg_reader.py`(DPS_Enhance eudplib-port 사본)를 그대로 쓴다.
"""

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from eudext.tools.debugbridge import dbg_reader as R  # noqa: E402

SPEC_FORMAT = "eudext-ingame-spec"
RESULTS_FORMAT = "eudext-ingame-results"
PASS, FAIL = "통과", "실패"
NOT_RUN, STALLED, CRASHED = "미실행", "멈춤", "튕김"
SKIPPED = "건너뜀"  # 선택 단계(optional)를 시작하지 않음
RUNNING, ENDED = "도는 중", "끝남"
KINDS = ("check", "result", "watch", "hit", "mark", "text", "dwords", "all_checks", "group", "manual", "peek", "hdr",
         "wall")
MANUAL = "사람 확인"
# classification.json 항목의 설명 필드 — 판정에는 쓰지 않고 결과에 그대로 옮긴다
INFO_KEYS = ("read", "expect", "done_marker", "phase", "category", "doc_section", "required", "map", "bundle", "notes",
             "risk", "extra", "instrument", "title")
HDR_FIELDS = {"seq": (R.H_SEQ_BEGIN, 1), "game_frame": (R.H_GAME_FRAME, 1), "local_player": (R.H_LOCAL_PLAYER, 1),
              "build": (R.H_BUILD, 1), "player_info": (16, 4), "map_path": (20, 4)}
WALL_METRICS = ("fps", "max_gap_s", "seconds")
# 터보([eudTurbo]) 기준: 트리거 한 사이클 = 게임 한 프레임 → 초당 약 24 사이클.
# 터보가 없으면 한 사이클이 28~30프레임(1.2초) 간격이라 초당 1 사이클도 안 된다(인게임 G-1, 2026-09-18).
TURBO_CPS = 24.0
TURBO_CPS_MIN = 8.0  # 이보다 낮으면 터보가 빠진 맵으로 보고 안내한다

__all__ = ["CRASHED", "FAIL", "MANUAL", "NOT_RUN", "PASS", "SKIPPED", "STALLED", "MapRun", "ResultStore", "SpecError",
           "checklist_entries", "evaluate_item", "load_specs", "main", "run_lines", "write_checklist"]


class SpecError(ValueError):
    pass


# ---------------------------------------------------------------------------------------------
# 명세
# ---------------------------------------------------------------------------------------------


def _as_int(v, what):
    if isinstance(v, bool):
        raise SpecError("%s: 참거짓은 숫자가 아닙니다" % what)
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            return int(v.replace("_", ""), 0)
        except ValueError:
            pass
    raise SpecError("%s: 정수(또는 10진·0x 문자열)가 아닙니다: %r" % (what, v))


def _as_num(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise SpecError("%s: 숫자가 아닙니다: %r" % (what, v))
    return v


def _as_float(v, what):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        raise SpecError("%s: 양수여야 합니다: %r" % (what, v))
    return float(v)


def parse_checklist_targets(value, where, item_id=None):
    """명세의 checklist 값 → [(row, section 또는 None)]. true 면 항목 id 가 행 번호."""
    if value is None or value is False:
        return []
    if value is True:
        if not item_id:
            raise SpecError("%s: checklist: true 는 id 가 있는 항목에만 씁니다" % where)
        return [(str(item_id).strip(), None)]
    out = []
    for x in value if isinstance(value, list) else [value]:
        if isinstance(x, str):
            out.append((x.strip(), None))
        elif isinstance(x, dict) and isinstance(x.get("row"), str):
            sec = x.get("section")
            out.append((x["row"].strip(), sec if isinstance(sec, str) and sec else None))
        else:
            raise SpecError("%s: checklist 는 \"행\"·true·{\"row\", \"section\"} 입니다: %r" % (where, x))
    return out


_NEEDS_NAME = ("check", "result", "watch", "hit", "mark", "text", "dwords")


def _check_item(it, where, sub=False):
    if not isinstance(it, dict) or it.get("kind") not in KINDS:
        raise SpecError("%s: kind 는 %s 중 하나입니다" % (where, ", ".join(KINDS)))
    it = dict(it)
    kind = it["kind"]
    if kind in _NEEDS_NAME and not isinstance(it.get("name"), str):
        raise SpecError("%s: name 이 없습니다" % where)
    it.setdefault("id", it.get("name") or it.get("field") or it.get("metric") or
                  (kind + (":" + it["suite"] if it.get("suite") else "")))
    it["id"] = str(it["id"])
    if it.get("when", "final") not in ("final", "ever"):
        raise SpecError("%s: when 은 final 또는 ever 입니다" % where)
    if kind == "wall":
        if it.get("metric") not in WALL_METRICS:
            raise SpecError("%s: wall 의 metric 은 %s 중 하나입니다" % (where, ", ".join(WALL_METRICS)))
        for key in ("equals", "min", "max"):
            if key in it:
                it[key] = _as_num(it[key], "%s %s" % (where, key))
    else:
        for key in ("equals", "min", "max", "mask"):
            if key in it and kind in ("watch", "hit", "mark", "hdr", "peek") and not isinstance(it[key], list):
                it[key] = _as_int(it[key], "%s %s" % (where, key))
    if "in" in it:
        it["in"] = [_as_int(x, where + " in") for x in it["in"]]
    if "total" in it and it["total"] != "sites":
        it["total"] = _as_int(it["total"], where + " total")
    if kind in ("dwords", "peek", "hdr") and isinstance(it.get("equals"), list):
        it["equals"] = [_as_int(x, where + " equals") & 0xFFFFFFFF for x in it["equals"]]
    if kind == "peek":
        it["addr"] = _as_int(it.get("addr"), where + " addr")
        it["count"] = _as_int(it.get("count", 1), where + " count")
        if it["addr"] % 4 or not 1 <= it["count"] <= 1024:
            raise SpecError("%s: peek 주소는 4의 배수, count 는 1~1024 입니다" % where)
    if kind == "hdr" and it.get("field") not in HDR_FIELDS:
        raise SpecError("%s: hdr 의 field 는 %s 중 하나입니다" % (where, ", ".join(HDR_FIELDS)))
    if kind == "text":
        for key in ("offset", "length"):
            if key in it:
                it[key] = _as_int(it[key], "%s %s" % (where, key))
                if it[key] < 0:
                    raise SpecError("%s: %s 는 0 이상입니다" % (where, key))
    if "regex" in it:
        try:
            re.compile(it["regex"])
        except re.error as e:
            raise SpecError("%s: regex 오류 %s" % (where, e)) from None
    if kind == "group":
        subs = it.get("items")
        if not isinstance(subs, list) or not subs:
            raise SpecError("%s: group 에는 items 목록이 필요합니다" % where)
        it["items"] = [_check_item(x, "%s.items[%d]" % (where, k), sub=True) for k, x in enumerate(subs)]
    if "phase" in it and it["phase"] is not None:
        it["phase"] = _as_int(it["phase"], where + " phase")
    if "suite" in it and it["suite"] is not None and not isinstance(it["suite"], str):
        raise SpecError("%s: suite 는 단계 이름입니다" % where)
    it["checklist"] = [] if sub else parse_checklist_targets(it.get("checklist"), where, it["id"])
    if isinstance(it.get("checklist_section"), str) and it["checklist"]:
        it["checklist"] = [(r, s or it["checklist_section"]) for r, s in it["checklist"]]
    it["info"] = {k: it[k] for k in INFO_KEYS if k in it}
    return it


def _check_items(items, where0):
    out = []
    ids = set()
    for k, it in enumerate(items or []):
        it = _check_item(it, "%s items[%d]" % (where0, k))
        if it["id"] in ids:
            raise SpecError("%s items[%d]: id %r 가 겹칩니다" % (where0, k, it["id"]))
        ids.add(it["id"])
        out.append(it)
    return out


def check_spec(spec, path="?"):
    """명세 dict 를 검사하고 기본값을 채운 사본을 돌려준다."""
    if not isinstance(spec, dict) or spec.get("format") != SPEC_FORMAT:
        raise SpecError("%s: format 이 %s 가 아닙니다" % (path, SPEC_FORMAT))
    if spec.get("version", 1) != 1:
        raise SpecError("%s: 모르는 version %r" % (path, spec.get("version")))
    name = spec.get("map")
    if not isinstance(name, str) or not name:
        raise SpecError("%s: map(맵 이름)이 없습니다" % path)
    out = dict(spec)
    out["path"] = path
    out["timeout_s"] = _as_float(spec.get("timeout_s", 300), path + " timeout_s")
    out["timeout_cycles"] = _as_int(spec["timeout_cycles"], path + " timeout_cycles") if "timeout_cycles" in spec else None
    out["stall_s"] = _as_float(spec["stall_s"], path + " stall_s") if "stall_s" in spec else None
    out["settle_cycles"] = _as_int(spec.get("settle_cycles", 2), path + " settle_cycles")
    done = spec.get("done")
    if done is not None and not (isinstance(done, list) and all(isinstance(x, str) for x in done)):
        raise SpecError("%s: done 은 표식 이름 목록입니다" % path)
    out["checklist"] = parse_checklist_targets(spec.get("checklist"), path)
    out["items"] = _check_items(spec.get("items"), path)
    suites = []
    seen, phases = set(), set()
    for k, s in enumerate(spec.get("suites") or []):
        where = "%s suites[%d]" % (path, k)
        if not isinstance(s, dict) or not isinstance(s.get("name"), str) or not s["name"]:
            raise SpecError("%s: name 이 없습니다" % where)
        if s["name"] in seen:
            raise SpecError("%s: 단계 %r 가 겹칩니다" % (where, s["name"]))
        seen.add(s["name"])
        phase = _as_int(s["phase"], where + " phase") if s.get("phase") is not None else None
        if phase is not None:
            if phase in phases:
                raise SpecError("%s: phase %d 가 겹칩니다" % (where, phase))
            phases.add(phase)
        suites.append({
            "name": s["name"],
            "phase": phase,
            "title": s.get("title"),
            "timeout_s": _as_float(s["timeout_s"], where + " timeout_s") if "timeout_s" in s else None,
            "timeout_cycles": _as_int(s["timeout_cycles"], where + " timeout_cycles") if "timeout_cycles" in s else None,
            "stall_s": _as_float(s["stall_s"], where + " stall_s") if "stall_s" in s else None,
            "checklist": parse_checklist_targets(s.get("checklist"), where),
            "items": _check_items(s.get("items"), where) if s.get("items") else [],
            "all_checks": bool(s.get("all_checks", True)),
            "optional": bool(s.get("optional", False)),
        })
    out["suites"] = suites
    return out


def load_specs(paths):
    """파일·폴더 목록 → {맵 이름: 명세}. 같은 맵 이름이 둘이면 오류. 폴더 안의 다른 형식 JSON 은 건너뛴다."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend((os.path.join(p, n), True) for n in sorted(os.listdir(p)) if n.lower().endswith(".json"))
        else:
            files.append((p, False))
    specs = {}
    for f, from_dir in files:
        with open(f, encoding="utf-8-sig") as fh:
            try:
                doc = json.load(fh)
            except ValueError as e:
                raise SpecError("%s: JSON 오류 %s" % (f, e)) from None
        if from_dir and not (isinstance(doc, dict) and doc.get("format") == SPEC_FORMAT):
            continue
        spec = check_spec(doc, f)
        if spec["map"] in specs:
            raise SpecError("맵 %r 의 명세가 둘입니다: %s, %s" % (spec["map"], specs[spec["map"]]["path"], f))
        specs[spec["map"]] = spec
    return specs


# ---------------------------------------------------------------------------------------------
# 판정
# ---------------------------------------------------------------------------------------------


def _ext_entry(sym, group, name):
    for e in (sym.ext or {}).get(group, []):
        if e.get("name") == name:
            return e
    return None


def _in_suite(entry, suite):
    return entry.get("suite") == suite or entry["name"].startswith(suite + ".")


def _cmp(value, it):
    """(맞는가, 기대 설명). mask 가 있으면 값에 먼저 씌운다."""
    if value is not None and "mask" in it and isinstance(value, int):
        value &= it["mask"]
    want = []
    ok = value is not None
    if "equals" in it:
        want.append("= %s" % (it["equals"],))
        ok = ok and value == it["equals"]
    if "min" in it:
        want.append("≥ %s" % it["min"])
        ok = ok and not isinstance(value, list) and value >= it["min"]
    if "max" in it:
        want.append("≤ %s" % it["max"])
        ok = ok and not isinstance(value, list) and value <= it["max"]
    if "in" in it:
        want.append("∈ %s" % it["in"])
        ok = ok and value in it["in"]
    return ok, " ".join(want)


def _wall(metric, timeline, window):
    """timeline = [(시각, seq)] (seq 가 바뀐 순간들). window = (t0, t1) 또는 None."""
    pts = [(t, s) for t, s in timeline if window is None or window[0] <= t <= window[1]]
    if len(pts) < 2:
        return None
    if metric == "seconds":
        return round(pts[-1][0] - pts[0][0], 3)
    if metric == "fps":
        dt = pts[-1][0] - pts[0][0]
        return round((pts[-1][1] - pts[0][1]) / dt, 2) if dt > 0 else None
    return round(max(b[0] - a[0] for a, b in zip(pts, pts[1:])), 3)


def evaluate_item(it, sym, vals, ctx=None):
    """항목 하나 → (통과 True/False/판정 없음 None, 설명, 관측값). vals = dbg_reader.ext_values(sym, d).

    ctx(선택): {"d": 블록 dword, "peek": fn(주소, 수) 또는 None, "timeline": [(시각, seq)], "window": (t0, t1) 또는 None}
    """
    ctx = ctx or {}
    kind, name = it["kind"], it.get("name")
    if kind == "manual":
        return None, "사람 확인" + (" — " + it["info"]["expect"] if isinstance(it.get("info", {}).get("expect"), str)
                                 else ""), None
    if kind == "group":
        parts, ok_all, values = [], True, {}
        for sub in it["items"]:
            ok, detail, value = evaluate_item(sub, sym, vals, ctx)
            values[sub["id"]] = value
            if ok is None:
                continue
            ok_all = ok_all and ok
            parts.append("%s%s: %s" % ("" if ok else "✗ ", sub["id"], detail))
        return ok_all, "; ".join(parts), values
    if kind == "check":
        entry = _ext_entry(sym, "checks", name)
        if entry is None or name not in vals["checks"]:
            return False, "심볼에 없는 판정 %r" % name, None
        p, t = vals["checks"][name]
        want = it.get("total")
        if want == "sites":
            want = len(entry.get("sites", []))
        ok = t is not None and t >= 1 and p == t and (want is None or t == want)
        return ok, "%s / %s" % (p, t) + ("" if want is None else " (기대 전체 %d)" % want), [p, t]
    if kind == "result":
        if name not in vals["results"]:
            return False, "심볼에 없는 결과 %r" % name, None
        p, t, n = vals["results"][name]
        want = it.get("total")
        ok = bool(n) and p == t and (want is None or t == want)
        detail = ("보고 없음" if not n else "%s / %s" % (p, t)) + ("" if want is None else " (기대 전체 %d)" % want)
        return ok, detail, [p, t, n]
    if kind == "all_checks":
        suite = it.get("suite")
        bad, count = [], 0
        for e in (sym.ext or {}).get("checks", []):
            if suite is not None and not _in_suite(e, suite):
                continue
            count += 1
            p, t = vals["checks"].get(e["name"], (None, None))
            if not t or p != t:
                bad.append("%s %s/%s" % (e["name"], p, t))
        for e in (sym.ext or {}).get("results", []):
            if suite is not None and not _in_suite(e, suite):
                continue
            count += 1
            p, t, n = vals["results"].get(e["name"], (None, None, None))
            if not n or p != t:
                bad.append("%s %s/%s" % (e["name"], p, t) if n else "%s 보고 없음" % e["name"])
        if count == 0:
            return None, "check·result 없음", 0
        return not bad, ("모두 통과 (%d개)" % count) if not bad else "실패: " + ", ".join(bad[:6]), count - len(bad)
    if kind == "watch":
        if name not in vals["watches"]:
            return False, "심볼에 없는 감시 %r" % name, None
        v = vals["watches"][name]
        ok, want = _cmp(v, it)
        return ok, "%s %s" % (v, want), v
    if kind in ("hit", "mark"):
        group = "hits" if kind == "hit" else "marks"
        if name not in vals[group]:
            return False, "심볼에 없는 %s %r" % ("hit" if kind == "hit" else "표식", name), None
        v = vals[group][name]
        spec = dict(it)
        if not any(k in spec for k in ("equals", "min", "max", "in")):
            spec["min"] = 1
        ok, want = _cmp(v, spec)
        return ok, "%s %s" % (v, want), v
    if kind == "peek":
        peek = ctx.get("peek")
        if peek is None:
            return False, "peek 불가 (미러 블록이 아님)", None
        got = peek(it["addr"], it["count"])
        if got is None:
            return False, "0x%X 읽기 불가" % it["addr"], None
        v = got[0] if it["count"] == 1 and not isinstance(it.get("equals"), list) else list(got)
        ok, want = _cmp(v, it)
        return ok, "0x%X = %s %s" % (it["addr"], v, want), v
    if kind == "hdr":
        d = ctx.get("d")
        if d is None:
            return False, "블록을 읽지 못함", None
        index, count = HDR_FIELDS[it["field"]]
        v = d[index] if count == 1 else list(d[index:index + count])
        if it["field"] == "map_path" and "contains" in it:
            text = R.decode_text(v)
            return it["contains"] in text, "%r ⊃ %r" % (text, it["contains"]), text
        ok, want = _cmp(v, it)
        return ok, "%s = %s %s" % (it["field"], v, want), v
    if kind == "wall":
        v = _wall(it["metric"], ctx.get("timeline") or [], ctx.get("window"))
        if v is None:
            return False, "시간 기록이 모자람", None
        ok, want = _cmp(v, it)
        return ok, "%s = %s %s" % (it["metric"], v, want), v
    if kind in ("text", "dwords"):
        if name not in vals["texts"]:
            return False, "심볼에 없는 스냅숏 %r" % name, None
        text, words = vals["texts"][name]
        if kind == "dwords":
            if "equals" not in it:
                return True, "칸 %d개" % len(words), list(words)
            got = list(words[:len(it["equals"])])
            return got == it["equals"], "%s (기대 %s)" % (got, it["equals"]), list(words)
        if "offset" in it or "length" in it or text is None:
            raw = R.words_bytes(words)
            off = it.get("offset", 0)
            raw = raw[off:off + it["length"]] if "length" in it else raw[off:]
            raw = raw.split(b"\0", 1)[0]
            text = bytes(b for b in raw if b >= 0x20 or b == 0x0A).decode("utf-8", errors="replace")
        if "equals" in it:
            ok, want = text == it["equals"], "= %r" % it["equals"]
        elif "regex" in it:
            ok, want = re.search(it["regex"], text) is not None, "~ /%s/" % it["regex"]
        elif "contains" in it:
            ok, want = it["contains"] in text, "⊃ %r" % it["contains"]
        else:
            ok, want = text != "", "빈 글 아님"
        return ok, "%r %s" % (text, want), text
    return False, "모르는 kind %r" % kind, None


def _verdict(ok):
    return MANUAL if ok is None else (PASS if ok else FAIL)


def _item_record(it, ok, detail, value):
    rec = {"id": it["id"], "kind": it["kind"], "name": it.get("name") or it.get("suite") or it.get("field")
           or it.get("metric"), "verdict": _verdict(ok), "detail": detail, "value": value,
           "checklist": [{"row": r, "section": s} for r, s in it["checklist"]]}
    if it.get("info"):
        rec["info"] = it["info"]
    return rec


class _Ever:
    """when="ever" 항목의 걸쇠."""

    def __init__(self):
        self.hit = {}

    def feed(self, items, sym, vals, seq, ctx):
        for it in items:
            if it.get("when") == "ever" and it["id"] not in self.hit:
                ok, detail, value = evaluate_item(it, sym, vals, ctx)
                if ok:
                    self.hit[it["id"]] = (detail, value, seq)

    def judge(self, items, sym, vals, ctx):
        out = []
        for it in items:
            if vals is None:
                ok, detail, value = (None, "사람 확인", None) if it["kind"] == "manual" else (False, "블록을 읽지 못함", None)
            else:
                ok, detail, value = evaluate_item(it, sym, vals, ctx)
            if ok is False and it["id"] in self.hit:
                d0, v0, s0 = self.hit[it["id"]]
                ok, detail, value = True, "%s (사이클 %d 에 맞음)" % (d0, s0), v0
            out.append((it, ok, detail, value))
        return out


class SuiteRun:
    """단계 하나의 판정 상태."""

    def __init__(self, name, no, spec, in_symbols):
        self.name = name
        self.no = no
        self.spec = spec or {"name": name, "phase": no, "title": None, "timeout_s": None, "timeout_cycles": None,
                             "stall_s": None, "checklist": [], "items": [], "all_checks": True, "optional": False}
        self.in_symbols = in_symbols
        self.items = list(self.spec.get("items") or [])
        if self.spec.get("all_checks", True):
            self.items.append(_check_item({"kind": "all_checks", "suite": name, "id": "all_checks:" + name}, name))
            self.items[-1]["auto"] = True
        self.status = NOT_RUN
        self.begin = self.end = None  # 프레임 (맵이 적은 값)
        self.begin_time = self.end_time = None
        self.end_seen_seq = None
        self.prev_key = None
        self.waits = 0
        self.ever = _Ever()
        self.record = None

    def attach(self, it):
        auto = [x for x in self.items if x.get("auto")]
        self.items = [x for x in self.items if not x.get("auto")] + [it] + auto

    @property
    def judged(self):
        return self.record is not None

    def window(self):
        if self.begin_time is None:
            return None
        return (self.begin_time, self.end_time or time.time())

    def judge(self, sym, vals, ctx, status_override=None, reason=None):
        items = []
        all_ok = True
        judged_any = False
        ctx = dict(ctx or {}, window=self.window())
        for it, ok, detail, value in self.ever.judge(self.items, sym, vals, ctx):
            if ok is None and it.get("auto"):
                continue  # 단계에 check·result 가 없다 — 기본 항목은 빼고
            items.append(_item_record(it, ok, detail, value))
            if ok is None:
                continue
            judged_any = True
            all_ok = all_ok and ok
        slot = vals["suites"].get(self.name, (None, None, None, None))[3] if vals is not None else None
        if slot == 2:
            all_ok = False
        why = reason or ""
        if status_override is not None:
            status = status_override
        elif not self.in_symbols:
            status, why = FAIL, "심볼에 없는 단계 (맵이 이 단계를 만들지 않음)"
        else:
            status = PASS if all_ok else FAIL
            if not why:
                why = ("항목 %d개" % sum(1 for x in items if x["verdict"] != MANUAL)) if judged_any else \
                    ("맵 판정 %s" % {1: "통과", 2: "실패"}.get(slot, "없음"))
                if slot == 2:
                    why += " — 맵이 실패로 적음"
        secs = None
        if self.begin_time is not None:
            secs = round((self.end_time or time.time()) - self.begin_time, 3)
        self.record = {"name": self.name, "no": self.no, "phase": self.spec.get("phase") or self.no,
                       "title": self.spec.get("title"), "status": status, "begin": self.begin, "end": self.end,
                       "seconds": secs, "reason": why, "verdict_slot": slot, "items": items,
                       "checklist": [{"row": r, "section": s} for r, s in self.spec.get("checklist", [])]}
        return self.record


class MapRun:
    """맵 한 판의 판정 상태. `feed()` 가 판정할 때를 알려 주고 `judge()` 가 결과 dict 를 만든다.

    say(글) = 진행 알림 (단계 시작·끝·판정). peek(주소, 수) = 미러 주소 직접 읽기 (미러 블록일 때만 판정에 쓴다).
    """

    def __init__(self, spec, sym, block_addr, build, now=None, pid=None, where=None, say=None, default_stall=15.0,
                 peek=None, force_stall=0.0):
        self.force_stall = force_stall
        self.spec = spec
        self.sym = sym
        self.block_addr = block_addr
        self.build = build
        self.pid = pid
        self.say = say or (lambda text: None)
        self.default_stall = default_stall
        self.where = where or (sym.ext or {}).get("where")
        self.peek = peek if self.where == "mirror" else None
        self.started = now if now is not None else time.time()
        self.started_iso = datetime.datetime.now().isoformat(timespec="seconds")
        self.first_seq = None
        self.last_seq = None
        self.done_seq = None
        self.prev_key = None
        self.waits = 0
        self.ever = _Ever()
        self.last_d = None
        self.last_vals = None
        self.timeline = []
        self.last_seen = {"seq": None, "frame": None, "suite": None, "last_suite": None, "time": None}
        done = spec.get("done")
        if done is None:
            done = ["done"] if _ext_entry(sym, "marks", "done") is not None else []
        self.done = done
        # 단계: 심볼의 단계(번호순) + 명세에만 있는 단계. 명세 단계는 이름 또는 phase 번호로 짝짓는다
        sym_suites = sorted((sym.ext or {}).get("suites", []), key=lambda s: s.get("no") or 0)
        by_name = {s["name"]: s for s in spec.get("suites", [])}
        by_phase = {s["phase"]: s for s in spec.get("suites", []) if s.get("phase") is not None}
        self.suites = []
        used = set()
        for s in sym_suites:
            sp = by_name.get(s["name"]) or by_phase.get(s.get("no"))
            if sp is not None:
                used.add(sp["name"])
            self.suites.append(SuiteRun(s["name"], s.get("no"), sp, True))
        for s in spec.get("suites", []):
            if s["name"] not in used:
                self.suites.append(SuiteRun(s["name"], s.get("phase"), s, False))
        # 맵 항목 가운데 suite·phase 가 있는 것은 그 단계로
        self.items = []
        for it in spec["items"]:
            target = None
            if it.get("suite"):
                target = self._suite(it["suite"]) or self._new_suite(it["suite"], None)
            elif it.get("phase") is not None and (self.suites or spec.get("suites")):
                target = self._suite_no(it["phase"]) or self._new_suite("phase%d" % it["phase"], it["phase"])
            if target is None:
                self.items.append(it)
            else:
                target.attach(it)
        self.finished = None

    def _suite(self, name):
        return next((s for s in self.suites if s.name == name), None)

    def _suite_no(self, no):
        return next((s for s in self.suites if s.no == no), None)

    def _new_suite(self, name, no):
        s = SuiteRun(name, no, None, False)
        self.suites.append(s)
        return s

    # --- 상태 ---
    def ctx(self):
        return {"d": self.last_d, "peek": self.peek, "timeline": self.timeline, "window": None}

    def current_suite(self):
        for s in self.suites:
            if s.status in (RUNNING, ENDED) and not s.judged:
                return s
        return None

    def stall_limit(self):
        if self.force_stall:  # --once: 이미 멈춘 게임을 한 번 읽는다 — 명세의 stall_s 를 무시한다
            return self.force_stall
        s = self.current_suite()
        if s is not None and s.spec.get("stall_s"):
            return s.spec["stall_s"]
        return self.spec.get("stall_s") or self.default_stall

    def progress(self):
        vals = self.last_vals
        cur = self.current_suite()
        parts = ["맵 %s" % self.spec["map"], "사이클 %s" % self.last_seq]
        if self.suites:
            done = sum(1 for s in self.suites if s.judged)
            parts.append("단계 %d/%d" % (done, len(self.suites)))
            if cur is not None:
                p = t = 0
                if vals is not None:
                    for e in (self.sym.ext or {}).get("checks", []):
                        if _in_suite(e, cur.name):
                            pp, tt = vals["checks"].get(e["name"], (0, 0))
                            p, t = p + (pp or 0), t + (tt or 0)
                parts.append("지금 %s (%s, 판정 %d/%d)" % (cur.name, cur.status, p, t))
        return ", ".join(parts)

    def snapshot_state(self):
        return {"map": self.spec["map"], "build_id": self.build, "block": self.block_addr, "started": self.started_iso,
                "last_seen": dict(self.last_seen),
                "suites": [{"name": s.name, "no": s.no, "status": s.record["status"] if s.judged else s.status}
                           for s in self.suites]}

    @staticmethod
    def _key(vals, names=None):
        if names is None:
            return json.dumps([vals["checks"], vals["results"], vals["marks"],
                               sorted((k, v[1]) for k, v in vals["texts"].items())], sort_keys=True, default=str)
        return json.dumps([{k: v for k, v in vals["checks"].items() if k in names},
                           {k: v for k, v in vals["results"].items() if k in names}], sort_keys=True, default=str)

    def _suite_names(self, suite):
        ext = self.sym.ext or {}
        return {e["name"] for g in ("checks", "results") for e in ext.get(g, []) if _in_suite(e, suite.name)}

    # --- 먹이기 ---
    def feed(self, d, now=None):
        """일관된 스냅숏 하나를 넣는다. 맵을 판정할 때가 되면 (이유, 원인) 을, 아니면 None 을 돌려준다."""
        now = time.time() if now is None else now
        seq = d[R.H_SEQ_BEGIN]
        if self.first_seq is None:
            self.first_seq = seq
        if seq != self.last_seq:
            self.timeline.append((now, seq))
            if len(self.timeline) > 200000:
                del self.timeline[:100000]
        self.last_seq = seq
        vals = R.ext_values(self.sym, d)
        self.last_d, self.last_vals = d, vals
        ctx = self.ctx()
        now_info = vals.get("suite_now") or {}
        self.last_seen = {"seq": seq, "frame": now_info.get("frame"), "suite": now_info.get("current"),
                          "last_suite": now_info.get("last"), "time": datetime.datetime.now().isoformat(timespec="seconds")}
        self.ever.feed(self.items, self.sym, vals, seq, ctx)
        settle = self.spec["settle_cycles"]
        for s in self.suites:
            if s.judged or not s.in_symbols:
                continue
            state, begin, end, _verdict_slot = vals["suites"].get(s.name, (0, None, None, 0))
            if s.status == NOT_RUN and state in (1, 2):
                s.status, s.begin, s.begin_time = RUNNING, begin, now
                self.say("단계 %s%s 시작 (프레임 %s)" % (s.name, " (%d)" % s.no if s.no else "", begin))
            if s.status == RUNNING:
                s.ever.feed(s.items, self.sym, vals, seq, dict(ctx, window=s.window()))
                if state == 2:
                    s.status, s.end, s.end_time, s.end_seen_seq = ENDED, end, now, seq
                    self.say("단계 %s 끝 (프레임 %s)" % (s.name, end))
                else:
                    lim_s, lim_c = s.spec.get("timeout_s"), s.spec.get("timeout_cycles")
                    over = None
                    if lim_s and now - s.begin_time >= lim_s:
                        over = "단계 시간 초과 (%g초)" % lim_s
                    elif lim_c and begin is not None and seq - begin >= lim_c:
                        over = "단계 시간 초과 (사이클 %d)" % lim_c
                    if over:
                        s.end_time = now
                        rec = s.judge(self.sym, vals, ctx, status_override=FAIL, reason=over)
                        self.say("단계 %s: %s — %s" % (s.name, rec["status"], over))
            if s.status == ENDED and not s.judged and seq >= s.end_seen_seq + settle:
                key = self._key(vals, self._suite_names(s))
                if key != s.prev_key and s.waits < 20:
                    s.prev_key, s.waits = key, s.waits + 1
                    continue
                rec = s.judge(self.sym, vals, ctx)
                self.say("단계 %s: %s (%s)" % (s.name, rec["status"], rec["reason"]))
        return self._map_ready(seq, vals, now, ctx)

    def _map_ready(self, seq, vals, now, ctx):
        settle = self.spec["settle_cycles"]
        reason = None
        if self.done:
            if self.done_seq is None and all(vals["marks"].get(m) for m in self.done):
                self.done_seq = seq
            if self.done_seq is not None and seq >= self.done_seq + settle and all(
                    s.judged or s.status == NOT_RUN or not s.in_symbols for s in self.suites):
                reason = ("완료 표식", "done")
        elif any(s.in_symbols for s in self.suites):
            if all(s.judged or (s.spec.get("optional") and s.status == NOT_RUN) for s in self.suites if s.in_symbols):
                reason = ("모든 단계 끝", "done")
        elif self.items:
            if all(ok is not False for _it, ok, _d, _v in self.ever.judge(self.items, self.sym, vals, ctx)):
                if self.done_seq is None:
                    self.done_seq = seq
                if seq >= self.done_seq + settle:
                    reason = ("모든 항목 통과", "done")
            else:
                self.done_seq = None
        key = self._key(vals)
        stable = key == self.prev_key
        self.prev_key = key
        if reason is not None:
            if not stable and self.waits < 20:
                self.waits += 1
                return None
            return reason
        if self.spec["timeout_cycles"] is not None and seq - self.first_seq >= self.spec["timeout_cycles"]:
            return ("시간 초과 (사이클 %d)%s" % (self.spec["timeout_cycles"], self.turbo_hint()), "timeout")
        if now - self.started >= self.spec["timeout_s"]:
            return ("시간 초과 (%g초)%s" % (self.spec["timeout_s"], self.turbo_hint()), "timeout")
        return None

    def turbo_hint(self):
        """시간 초과 설명에 붙이는 초당 사이클 안내 — 터보가 빠진 맵은 초당 1 사이클도 못 돈다(G-1)."""
        cps = _wall("fps", self.timeline, None)
        if cps is None:
            return ""
        if cps < TURBO_CPS_MIN:
            return " — 초당 사이클 %.2f (터보 기준 %g). 맵 eds 에 [eudTurbo] 가 빠진 것 같습니다" % (cps, TURBO_CPS)
        return " — 초당 사이클 %.1f" % cps

    # --- 판정 ---
    def judge(self, reason, cause="other", d=None):
        """최종 판정 → 결과 dict. d 가 없으면 마지막으로 본 스냅숏을 쓴다(튕김·멈춤)."""
        if d is not None:
            self.last_d = d
            vals = R.ext_values(self.sym, d)
        else:
            vals = self.last_vals
        ctx = self.ctx()
        cur = self.current_suite()
        for s in self.suites:
            if s.judged:
                continue
            if not s.in_symbols:
                s.judge(self.sym, vals, ctx)
            elif s.status == NOT_RUN and s.spec.get("optional"):
                s.judge(self.sym, vals, ctx, status_override=SKIPPED, reason="선택 단계 — 시작하지 않음")
            elif s.status == NOT_RUN:
                s.judge(self.sym, vals, ctx, status_override=NOT_RUN, reason="시작하지 않음")
            elif s.status == ENDED and cause != "crash":
                s.judge(self.sym, vals, ctx)
            else:  # 도는 중(또는 끝났지만 판정 전에 튕김)
                status = {"stall": STALLED, "crash": CRASHED}.get(cause, FAIL)
                s.end_time = s.end_time or time.time()
                s.judge(self.sym, vals, ctx, status_override=status, reason="%s — %s 도중 (마지막 프레임 %s)"
                        % (reason, s.name, self.last_seen.get("frame")))
        items = [_item_record(it, ok, detail, value)
                 for it, ok, detail, value in self.ever.judge(self.items, self.sym, vals, ctx)]
        if self.done and self.done_seq is None:
            for x in items:
                if x["verdict"] == FAIL:
                    x["detail"] += " — 완료 표식 없음(%s)" % ", ".join(self.done)
        suites = [s.record for s in self.suites]
        judged = [x for x in items if x["verdict"] != MANUAL]
        all_ok = (bool(judged) or bool(suites)) and all(x["verdict"] == PASS for x in judged) \
            and all(r["status"] in (PASS, SKIPPED) for r in suites) and cause == "done"
        if cur is not None and cause in ("stall", "crash"):
            reason = "%s: %s (프레임 %s)" % (reason, cur.name, self.last_seen.get("frame"))
        ext = self.sym.ext or {}
        self.finished = {
            "map": self.spec["map"],
            "title": self.spec.get("title"),
            "spec": self.spec.get("path"),
            "build_id": self.build,
            "build_tag": ext.get("build_tag"),
            "where": self.where,
            "block": "0x%X" % self.block_addr if self.block_addr is not None else None,
            "pid": self.pid,
            "started": self.started_iso,
            "finished": datetime.datetime.now().isoformat(timespec="seconds"),
            "seq": [self.first_seq, self.last_seq],
            "fps": _wall("fps", self.timeline, None),
            "reason": reason,
            "cause": cause,
            "verdict": PASS if all_ok else FAIL,
            "last_seen": dict(self.last_seen),
            "checklist": [{"row": r, "section": s} for r, s in self.spec["checklist"]],
            "items": items,
            "suites": suites,
        }
        return self.finished


# ---------------------------------------------------------------------------------------------
# 결과 저장·표시
# ---------------------------------------------------------------------------------------------


class ResultStore:
    """결과 JSON(누적)·진행 파일·사람이 읽는 로그."""

    def __init__(self, path, log_path=None, echo=True):
        self.path = path
        self.log_path = log_path
        self.echo = echo

    def load(self):
        if self.path and os.path.isfile(self.path):
            with open(self.path, encoding="utf-8") as f:
                doc = json.load(f)
            if doc.get("format") == RESULTS_FORMAT:
                return doc
        return {"format": RESULTS_FORMAT, "version": 1, "runs": []}

    @staticmethod
    def _write_json(path, doc):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    def append(self, run):
        if not self.path:
            return
        doc = self.load()
        doc["runs"].append(run)
        self._write_json(self.path, doc)

    def progress(self, state):
        if self.path:
            self._write_json(self.path + ".progress.json", dict(state, updated=datetime.datetime.now().isoformat(
                timespec="seconds")))

    def say(self, text):
        line = "[%s] %s" % (time.strftime("%H:%M:%S"), text)
        if self.echo:
            print(line, flush=True)
        if self.log_path:
            os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


def run_lines(run):
    ok = sum(1 for x in run["items"] if x["verdict"] == PASS)
    bad = sum(1 for x in run["items"] if x["verdict"] == FAIL)
    head = "맵 %s (빌드 %08X): %s — %s" % (run["map"], run["build_id"] or 0, run["verdict"], run["reason"])
    if run["items"]:
        head += " / 맵 항목 통과 %d·실패 %d" % (ok, bad)
    if run["suites"]:
        counts = {}
        for s in run["suites"]:
            counts[s["status"]] = counts.get(s["status"], 0) + 1
        head += " / 단계 " + ", ".join("%s %d" % kv for kv in counts.items())
    lines = [head]
    for x in run["items"]:
        lines.append("    %s  %-12s %-10s %-20s %s" % (x["verdict"], x["id"], x["kind"], x["name"] or "", x["detail"]))
    manual = [x["id"] for x in run["items"] if x["verdict"] == MANUAL]
    manual += [x["id"] for s in run["suites"] for x in s["items"] if x["verdict"] == MANUAL]
    if manual:
        lines.append("    사람 확인: " + ", ".join(manual))
    for s in run["suites"]:
        lines.append("    단계 %-14s %-4s %s" % (s["name"], s["status"], s["reason"]))
        for x in s["items"]:
            if s["status"] == SKIPPED:
                break
            if x["verdict"] == FAIL or (s["status"] != PASS and x["verdict"] != MANUAL):
                lines.append("        %s  %-12s %s" % (x["verdict"], x["id"], x["detail"]))
    return lines


# ---------------------------------------------------------------------------------------------
# 확인 문서 쓰기
# ---------------------------------------------------------------------------------------------

_ROW_EMPTY_LAST = re.compile(r"^(?P<head>\s*\|.*\|)(?P<cell>[ \t]*)\|[ \t]*$")
_FIRST_CELL = re.compile(r"^\s*\|\s*(?P<first>[^|]*?)\s*\|")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_SEPARATOR = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")


def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def checklist_entries(runs, date):
    """판정 결과들 → [(row, section, 쓸 글)] (같은 행은 합친다: 모두 통과면 통과)."""
    groups = {}
    order = []

    def add(key, ok, why):
        if key not in groups:
            groups[key] = [True, []]
            order.append(key)
        groups[key][0] = groups[key][0] and ok
        if not ok and why:
            groups[key][1].append(why)

    for run in runs:
        failed = [x["id"] for x in run["items"] if x["verdict"] == FAIL]
        failed += ["%s(%s)" % (s["name"], s["status"]) for s in run.get("suites", []) if s["status"] not in (PASS, SKIPPED)]
        for c in run.get("checklist", []):  # 맵 전체 행: 실패한 항목·단계 이름(없으면 사유)
            add((c["row"], c.get("section")), run["verdict"] == PASS,
                ("실패 " + ", ".join(failed[:8])) if failed else run["reason"])
        for x in run["items"]:
            if x["verdict"] == MANUAL:
                continue  # 사람이 적는다
            for c in x.get("checklist", []):
                add((c["row"], c.get("section")), x["verdict"] == PASS, "%s %s" % (x["id"], x["detail"]))
        for s in run.get("suites", []):
            if s["status"] == SKIPPED:
                continue  # 선택 단계를 하지 않았다 — 결과 칸은 비워 둔다
            for c in s.get("checklist", []):
                add((c["row"], c.get("section")), s["status"] == PASS, "%s %s: %s" % (s["name"], s["status"], s["reason"]))
            for x in s["items"]:
                if x["verdict"] == MANUAL:
                    continue
                for c in x.get("checklist", []):
                    ok = x["verdict"] == PASS and s["status"] == PASS
                    add((c["row"], c.get("section")), ok,
                        "%s %s" % (x["id"], x["detail"]) if x["verdict"] != PASS else "%s %s" % (s["name"], s["status"]))
    out = []
    for key in order:
        ok, whys = groups[key]
        if ok:
            text = "자동: 통과 (%s)" % date
        else:
            reason = "; ".join(dict.fromkeys(whys)) or "실패"
            reason = reason.replace("|", "/").replace("\n", " ")
            if len(reason) > 160:
                reason = reason[:157] + "…"
            text = "자동: 실패 — %s (%s)" % (reason, date)
        out.append((key[0], key[1], text))
    return out


def write_checklist(path, entries, dry_run=False, _depth=0):
    """확인 문서의 "결과" 칸이 빈 행에만 글을 쓴다. 반환: [(row, section, 상태, 글)].

    상태: "씀" / "쓸 것(시험 실행)" / "이미 적힘 — 그대로" / "행 없음" / "행이 여러 개 — section 을 주세요" / "결과 칸이 아님".
    """
    with open(path, "rb") as f:
        raw = f.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(newline)

    heads, table_head, is_head_row = [], [], []
    stack = []
    cur_head = None
    prev_table = False
    for line in lines:
        is_table = line.lstrip().startswith("|")
        m = _HEADING.match(line)
        if m and not is_table:
            level = len(m.group(1))
            stack = [h for h in stack if h[0] < level] + [(level, m.group(2))]
        first = is_table and not prev_table
        if first:
            cur_head = _cells(line)
        heads.append([h[1] for h in stack])
        table_head.append(cur_head if is_table else None)
        is_head_row.append(first)
        prev_table = is_table

    results = []
    changed = False
    for row, section, new in entries:
        matches = []
        for i, line in enumerate(lines):
            if table_head[i] is None or is_head_row[i] or _SEPARATOR.match(line):
                continue
            fm = _FIRST_CELL.match(line)
            if not fm:
                continue
            cell = fm.group("first").replace("**", "").strip()
            if row not in (cell, cell.split()[0] if cell.split() else ""):
                continue
            if section is not None and not any(section in h for h in heads[i]):
                continue
            matches.append(i)
        if not matches:
            results.append((row, section, "행 없음", new))
            continue
        if len(matches) > 1:
            results.append((row, section, "행이 여러 개 — section 을 주세요 (%d곳)" % len(matches), new))
            continue
        i = matches[0]
        if "결과" not in (table_head[i][-1] if table_head[i] else ""):
            results.append((row, section, "결과 칸이 아님", new))
            continue
        m = _ROW_EMPTY_LAST.match(lines[i])
        if not m:
            results.append((row, section, "이미 적힘 — 그대로", new))
            continue
        if dry_run:
            results.append((row, section, "쓸 것(시험 실행)", new))
            continue
        lines[i] = "%s %s |" % (m.group("head"), new)
        changed = True
        results.append((row, section, "씀", new))

    if changed:
        # 읽은 뒤 누가 고쳤으면 다시 한다 (사용자가 편집 중일 수 있다)
        with open(path, "rb") as f:
            if f.read() != raw and _depth < 3:
                return write_checklist(path, entries, dry_run, _depth + 1)
        data = newline.join(lines).encode("utf-8")
        if bom:
            data = b"\xef\xbb\xbf" + data
        tmp = path + ".eudext_tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    return results


# ---------------------------------------------------------------------------------------------
# 게임 프로세스 감시 (Windows)
# ---------------------------------------------------------------------------------------------


if R.WIN32:
    import ctypes

    R.k32.GetExitCodeProcess.argtypes = (R.wt.HANDLE, ctypes.POINTER(R.wt.DWORD))
    R.k32.GetExitCodeProcess.restype = R.wt.BOOL
STILL_ACTIVE = 259


def _alive(proc):
    """열린 핸들의 프로세스가 아직 살아 있는가 (종료 코드, 못 얻으면 메모리 영역이 보이는지)."""
    if R.WIN32:
        code = R.wt.DWORD(0)
        if R.k32.GetExitCodeProcess(proc.handle, ctypes.byref(code)):
            return code.value == STILL_ACTIVE
    try:
        for _region in proc.regions(R.WRITABLE):
            return True
    except OSError:
        return False
    return False


class Watcher:
    """게임 프로세스를 지켜보며 블록마다 MapRun 을 돌린다 (Windows)."""

    def __init__(self, args, specs, store):
        self.args = args
        self.specs = specs
        self.store = store
        self.proc = None
        self.blocks = {}  # 주소 -> dbg_reader.Block
        self.seq = {}  # 주소 -> (seq, 바뀐 시각)
        self.runs = {}  # 주소 -> MapRun
        self.closed = {}  # (주소, 빌드) -> 끝낼 때의 seq (이보다 작아지면 같은 자리의 새 게임)
        self.noted = set()
        self.judged = []
        self.passed_maps = set()
        self.last_scan = None
        self.last_progress = 0.0

    def note_once(self, key, text):
        if key not in self.noted:
            self.noted.add(key)
            self.store.say(text)

    def attach(self):
        pids = [self.args.pid] if self.args.pid else R.find_pids(self.args.name)
        for pid in pids:
            try:
                proc = R.Process(pid)
            except OSError as e:
                self.note_once(("open", pid), str(e))
                continue
            if not _alive(proc):
                proc.close()
                continue
            self.proc = proc
            self.store.say("프로세스 %d 에 붙었습니다 (%d비트, 읽기 전용)" % (pid, proc.bits))
            self.noted.discard("wait-proc")
            return True
        self.note_once("wait-proc", "%s 를 기다립니다 …" % (self.args.pid or self.args.name))
        return False

    def detach(self, why):
        for addr in list(self.runs):
            self.finish(addr, "튕김 — 게임 프로세스 끝남 (%s)" % why, "crash")
        if self.proc is not None:
            self.proc.close()
            self.store.say("프로세스에서 떨어졌습니다: %s" % why)
        self.proc = None
        self.blocks.clear()
        self.seq.clear()
        self.last_scan = None

    def scan(self):
        _hits, blocks = R.find_blocks(self.proc, R.DEFAULT_SIGNATURE)
        found = {}
        for b in blocks:
            old = self.blocks.get(b.addr)
            found[b.addr] = old if old is not None and old.build == b.build else b
        self.blocks = found
        for addr in list(self.runs):
            if addr not in found:
                self.finish(addr, "블록이 사라짐", "other")

    def step(self, now):
        a = self.args
        if self.proc is None and not self.attach():
            return
        interval = a.busy_scan_interval if self.runs else a.scan_interval
        if self.last_scan is None or now - self.last_scan >= interval:
            if not _alive(self.proc):
                self.detach("프로세스 없음")
                return
            self.scan()
            self.last_scan = now
        for addr, block in list(self.blocks.items()):
            header = self.proc.dwords(addr, R.HDR)
            if header is None and addr in self.runs and not _alive(self.proc):
                self.detach("프로세스 없음")
                return
            if header is None or tuple(header[:8]) != R.DEFAULT_SIGNATURE or header[R.H_VERSION] != R.LAYOUT_VERSION:
                if addr in self.runs:
                    self.finish(addr, "블록이 사라짐", "other")
                self.blocks.pop(addr, None)
                self.seq.pop(addr, None)
                continue
            if header[R.H_BUILD] != block.build:  # 같은 자리(미러 구역)에 다른 맵이 올라왔다
                if addr in self.runs:
                    self.finish(addr, "블록이 바뀜 (다른 맵)", "other")
                block = self.blocks[addr] = R.Block(self.proc, addr, header)
                self.seq.pop(addr, None)
            s = header[R.H_SEQ_BEGIN]
            prev = self.seq.get(addr)
            if prev is None or prev[0] != s:
                self.seq[addr] = (s, now)
            live = prev is not None and prev[0] != s
            key = (addr, block.build)
            if key in self.closed and s < self.closed[key]:
                del self.closed[key]  # 같은 자리에서 새 게임이 시작됐다 (seq 가 줄었다)
            if addr not in self.runs and live and key not in self.closed:
                self.start(addr, block, now)
        for addr, run in list(self.runs.items()):
            block = self.blocks.get(addr)
            d, ok = block.snapshot() if block is not None else (None, False)
            if d is None:
                if not _alive(self.proc):
                    self.detach("프로세스 없음")
                    return
                self.finish(addr, "블록을 읽지 못함", "other")
                continue
            if d[R.H_SEQ_BEGIN] < (run.last_seq or 0):
                self.finish(addr, "게임이 다시 시작됨", "other")
                continue
            if not ok:
                continue
            got = run.feed(d, now)
            if got is None:
                last = self.seq.get(addr, (None, now))[1]
                if now - last >= run.stall_limit():
                    got = ("멈춤 — 프레임이 %g초 동안 늘지 않음" % run.stall_limit(), "stall")
            if got is not None:
                self.finish(addr, got[0], got[1], d if got[1] != "stall" else None)
        if self.runs and now - self.last_progress >= a.progress:
            self.last_progress = now
            for run in self.runs.values():
                self.store.say("진행: " + run.progress())
                self.store.progress(run.snapshot_state())

    def start(self, addr, block, now):
        sym = R.load_symbols(self.args.symbols, block.build)
        if not sym.loaded or not sym.ext:
            self.note_once(("nosym", block.build), "블록 0x%X 빌드 %08X: eudext 심볼을 찾지 못했습니다 (--symbols 확인)"
                           % (addr, block.build))
            return
        name = sym.ext.get("map_name")
        spec = self.specs.get(name)
        if spec is None:
            self.note_once(("nospec", block.build), "맵 %s (빌드 %08X): 판정 명세가 없어 건너뜁니다" % (name, block.build))
            self.closed[(addr, block.build)] = self.seq[addr][0]
            return
        run = MapRun(spec, sym, addr, block.build, now=now, pid=self.proc.pid, default_stall=self.args.stall,
                     force_stall=(3.0 if getattr(self.args, "once", False) else 0.0),
                     say=lambda text, m=name: self.store.say("  [%s] %s" % (m, text)),
                     peek=lambda eud, n, b=block: b.direct(eud, n))
        self.runs[addr] = run
        self.store.say("맵 %s%s (빌드 %08X, 블록 0x%X %s) — 판정 시작: 맵 항목 %d, 단계 %d, 완료 표식 %s, 제한 %g초"
                       % (name, " — " + spec["title"] if spec.get("title") else "", block.build, addr, run.where,
                          len(run.items), len(run.suites), ",".join(run.done) or "(없음)", spec["timeout_s"]))
        self.store.progress(run.snapshot_state())

    def finish(self, addr, reason, cause, d=None):
        run = self.runs.pop(addr, None)
        if run is None:
            return
        res = run.judge(reason, cause, d)
        self.closed[(addr, run.build)] = run.last_seq or 0
        self.store.append(res)
        self.store.progress(dict(run.snapshot_state(), finished=True, verdict=res["verdict"], reason=res["reason"]))
        for line in run_lines(res):
            self.store.say(line)
        self.judged.append(res)
        if res["verdict"] == PASS:
            self.passed_maps.add(res["map"])
        if self.args.write_checklist:
            date = self.args.date or datetime.date.today().isoformat()
            for row, sec, st, text in write_checklist(self.args.write_checklist, checklist_entries([res], date),
                                                      dry_run=self.args.dry_run_checklist):
                self.store.say("    확인 문서 %s%s: %s — %s" % (row, " (" + sec + ")" if sec else "", st, text))
        left = [m for m in self.specs if m not in self.passed_maps]
        self.store.say(">>> 다음 맵을 여세요." + (" 남은 맵: " + ", ".join(left) if left else " 명세의 모든 맵이 통과했습니다."))


def main(argv=None):
    ap = argparse.ArgumentParser(description="eudext 인게임 자동 판정 (디버그 브리지)")
    ap.add_argument("--specs", nargs="+", required=True, help="판정 명세 JSON 파일 또는 폴더")
    ap.add_argument("--symbols", default=None, help="심볼 JSON 폴더 또는 파일 (기본: 리더와 같은 후보)")
    ap.add_argument("--out", default=None, help="결과 JSON (누적). 기본 EUDEXT_WORK/ingame_auto/results.json")
    ap.add_argument("--log", default=None, help="사람이 읽는 줄을 덧붙일 파일")
    ap.add_argument("--name", default="StarCraft.exe")
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--maps", type=int, default=0, help="이 수만큼 판정하면 끝 (0 = Ctrl+C 까지)")
    ap.add_argument("--once", action="store_true",
                    help="이미 멈춘(또는 끝난) 게임의 블록을 한 번 읽고 판정해 끝낸다 — 맵 1개, 멈춤 판정 3초"
                         " (명세의 stall_s 무시). 튕길 위험 맵에서 '멈춘 자리' 를 읽을 때 쓴다")
    ap.add_argument("--quit-when-all", action="store_true", help="명세의 모든 맵이 통과하면 끝")
    ap.add_argument("--poll", type=float, default=0.1, help="블록 읽기 간격 초")
    ap.add_argument("--scan-interval", type=float, default=2.0, help="판정 중인 맵이 없을 때 메모리 전체를 훑는 간격 초")
    ap.add_argument("--busy-scan-interval", type=float, default=15.0,
                    help="판정 중일 때의 전체 스캔 간격 초 (SC:R 메모리 전체를 훑는 데 몇 초 걸린다)")
    ap.add_argument("--stall", type=float, default=15.0, help="프레임(seq)이 이만큼 안 늘면 멈춤 (초, 명세 stall_s 가 우선)")
    ap.add_argument("--progress", type=float, default=5.0, help="판정 중 진행 줄 간격 초")
    ap.add_argument("--max-seconds", type=float, default=0, help="전체 실행 제한 (0 = 없음)")
    ap.add_argument("--write-checklist", default=None, help="확인 문서 경로 — 빈 결과 칸에만 자동 결과를 쓴다")
    ap.add_argument("--dry-run-checklist", action="store_true", help="확인 문서에 쓰지 않고 할 일만 보인다")
    ap.add_argument("--date", default=None, help="확인 문서에 적을 날짜 (기본 오늘)")
    args = ap.parse_args(argv)
    if args.once:
        args.maps = args.maps or 1
        args.stall = min(args.stall, 3.0)

    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        specs = load_specs(args.specs)
    except SpecError as e:
        print("명세 오류:", e)
        return 2
    if not specs:
        print("판정 명세가 없습니다:", " ".join(args.specs))
        return 2
    if not R.WIN32:
        print("게임 읽기는 Windows 전용입니다 (명세 검사는 통과: %d개)" % len(specs))
        return 1
    if args.out is None:
        work = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
        args.out = os.path.join(work, "ingame_auto", "results.json")
    store = ResultStore(args.out, args.log)
    store.say("명세 %d개: %s. 결과 → %s" % (len(specs), ", ".join(specs), args.out))
    w = Watcher(args, specs, store)
    t0 = time.time()
    try:
        while True:
            now = time.time()
            w.step(now)
            if args.maps and len(w.judged) >= args.maps:
                break
            if args.quit_when_all and all(m in w.passed_maps for m in specs):
                break
            if args.max_seconds and now - t0 >= args.max_seconds:
                store.say("실행 제한 %g초 — 끝냅니다" % args.max_seconds)
                for addr in list(w.runs):
                    w.finish(addr, "시간 초과 (도구 실행 제한)", "timeout")
                break
            time.sleep(args.poll)
    except KeyboardInterrupt:
        store.say("Ctrl+C — 끝냅니다")
        for addr in list(w.runs):
            w.finish(addr, "도구를 멈춤 (Ctrl+C)", "other")
    finally:
        if w.proc is not None:
            w.proc.close()
    passed = sum(1 for r in w.judged if r["verdict"] == PASS)
    store.say("판정한 맵 %d개 (통과 %d, 실패 %d)" % (len(w.judged), passed, len(w.judged) - passed))
    return 0 if w.judged and passed == len(w.judged) else 1


if __name__ == "__main__":
    sys.exit(main())
