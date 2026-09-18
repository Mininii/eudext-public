"""자동 점검 통합 맵 `auto_all` 과 계측판 맵·판정 명세 시험 (DESIGN 4.21·5.5, docs/ingame_auto/classification.md 5절).

1. 파이썬: 판정 명세(auto_all + 맵별 13개)가 검사를 통과하고, 분류 파일의 auto_all 항목 91개가 모두 명세에 있는지.
   fmt 기대 글 뽑기(aa_fmt), 단계 표(PHASES)와 명세 단계가 같은지.
2. 에뮬레이터: 통합 맵을 처음부터 끝까지(약 6,500 사이클) 돌려 모든 phase 가 끝나고 판정이 모두 통과하는지
   (`testing/aamodel.py` 모델 위에서). 블록 스냅숏을 프레임마다 모아 둔다.
3. 판정: 그 스냅숏을 `tools/ingame_auto.MapRun` 에 먹여 명세로 판정 → 통과. 사람 조작 구간(assist)을 한 판 더
   (채팅 줄을 넣어) 돌려 통과. **일부러 한 phase 를 틀리게 한 변이**는 그 단계만 실패로 잡히는지.
4. 계측판 맵: 01 S8·04 datpatch·27 X_limit·08 pool 을 에뮬레이터로 돌려 각 맵 명세로 판정.
5. 통합(Windows): 스냅숏을 가짜 게임(`fake_game.py --replay`)에 올려 `ingame_auto.py` 를 실제 Win32 읽기로 돌린다.
6. 빌드: euddraft 로 통합 맵과 계측판 맵을 빌드한다(느려서 `EUDEXT_SKIP_BUILD=1` 이면 건너뜀).

python tests/t_auto_all.py
"""

import sys

sys.dont_write_bytecode = True
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import importlib.util  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

from eudplib import CompressPayload, LoadMap  # noqa: E402

from eudext import dbg  # noqa: E402
from eudext.testing import aamodel, emu, scmodel  # noqa: E402
from eudext.tools import build, ingame_auto as A  # noqa: E402
from eudext.tools.debugbridge import dbg_reader as R  # noqa: E402

EX = os.path.join(_common.PKG, "examples")
PHASE_DIR = os.path.join(EX, "auto_all")
TOOLS = os.path.join(_common.PKG, "tools")
AUTO = os.path.join(TOOLS, "ingame_auto.py")
FAKE = os.path.join(TOOLS, "debugbridge", "fake_game.py")
SPEC_DIR = os.path.join(EX, "ingame_specs")
AUTO_ALL_SPEC = os.path.join(EX, "auto_all_spec.json")
CLASSIFICATION = os.path.join(_common.PKG, "docs", "ingame_auto", "classification.json")
T = os.path.join(_common.WORK, "t_auto_all")
SYMDIR = os.path.join(T, "dbg")
FRAMES_STEP = 8  # 블록 스냅숏 간격(사이클) — 리더도 0.1초마다 읽으므로 모든 프레임이 필요하지 않다
os.makedirs(T, exist_ok=True)


def _fresh(path):
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    return path


def _load_py(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# =============================================================================================
# 1. 파이썬 (명세·분류·fmt 기대 글)
# =============================================================================================


def python_checks(ck):
    sys.path.insert(0, PHASE_DIR)
    try:
        import aa_fmt
    finally:
        sys.path.remove(PHASE_DIR)
    sys.path.insert(0, TOOLS)
    try:
        import make_ingame_specs as gen
    finally:
        sys.path.remove(TOOLS)

    specs = A.load_specs([AUTO_ALL_SPEC, SPEC_DIR])
    ck.true("명세 묶음", len(specs) >= 14, sorted(specs))
    aa = specs.get("00_auto_all")
    ck.true("통합 맵 명세", aa is not None and aa["done"] == ["aa.done"], aa and aa.get("done"))
    names = [s["name"] for s in aa["suites"]]
    ck.eq("단계 이름·순서", names, [n for _no, n, _t, _s, _o, _c in gen.SUITES])
    ck.eq("선택 단계", [s["name"] for s in aa["suites"] if s["optional"]], ["assist"])
    # 터보 기준 제한: 단계마다 사이클 제한이 있고, 벽시계 제한은 사이클 ÷ 24 보다 넉넉하다
    ck.true("단계 제한 사이클", all(s["timeout_cycles"] for s in aa["suites"]),
            [(s["name"], s["timeout_cycles"]) for s in aa["suites"] if not s["timeout_cycles"]])
    ck.true("단계 제한 시간 ≥ 사이클/24",
            all(s["timeout_s"] >= s["timeout_cycles"] / A.TURBO_CPS for s in aa["suites"]),
            [(s["name"], s["timeout_s"], s["timeout_cycles"]) for s in aa["suites"]
             if s["timeout_s"] < s["timeout_cycles"] / A.TURBO_CPS])
    ck.true("맵 제한도 터보 기준", aa["timeout_cycles"] == 8000 and aa["timeout_s"] >= 8000 / A.TURBO_CPS,
            (aa["timeout_cycles"], aa["timeout_s"]))
    # 분류 파일의 auto_all 항목이 모두 명세에 있는가
    with open(CLASSIFICATION, encoding="utf-8") as f:
        cls = json.load(f)
    want = {e["id"] for e in cls if (e.get("bundle") or "").startswith("auto_all")}
    have = {x["id"] for x in aa["items"]} | {x["id"] for s in aa["suites"] for x in s["items"]}
    # 91 → 88: 2026-09-18 인게임에서 E6-3·E6-4·E6-4b(13번째 줄·TBL 쓰기)가 EUD ERROR 로 게임을 멈춰 통합 맵에서 뺐다
    # (25_display_check·25b_display_bisect 전용 — classification `bundle` 도 그렇게 바뀌었다).
    ck.eq("분류 auto_all 항목 수", len(want), 88)
    ck.eq("명세에 빠진 항목", sorted(want - have), [])
    ck.true("명세 항목이 확인 문서 행을 가리킨다",
            all(x["checklist"] for x in aa["items"] + [y for s in aa["suites"] for y in s["items"]]
                if x["id"] in want), "")
    # 맵별 명세: 맵 이름이 빌드 이름(<번호>_<이름>)과 같은가
    sys.path.insert(0, TOOLS)
    try:
        import ingame_maps as im
    finally:
        sys.path.remove(TOOLS)
    map_names = {"%s_%s" % (e[0], e[1]) for e in im.MAPS}
    ck.eq("명세 맵 이름이 빌드 이름과 같다", sorted(set(specs) - map_names), [])
    ck.true("00 auto_all 이 맨 앞", im.MAPS[0][0] == "00" and im.MAPS[0][1] == "auto_all", im.MAPS[0][:2])
    ck.true("27 X_limit 이 있다", any(e[1] == "X_limit" for e in im.MAPS), "")
    # fmt 기대 글: 원래 맵 show() 에서 뽑은 값이 명세와 같은가
    for name, spec_name, n in (("i64_ingame.eps", "i64.C3-3.fmt", 22), ("i64_ops_ingame.eps", "i64_ops.D4-1.fmt", 56),
                               ("i128_ingame.eps", "i128.F20-1.fmt", 46)):
        want_text = aa_fmt.expect_text_of(os.path.join(EX, name))
        items = [x for s in aa["suites"] for x in s["items"]]
        found = None
        for x in items:
            for sub in x.get("items", []):
                if sub.get("name") == spec_name:
                    found = sub.get("equals")
        ck.eq("fmt 기대 글 %s (%d개)" % (spec_name, n), (found == want_text, len(want_text.split())),
              (True, n))


# =============================================================================================
# 2. 에뮬레이터 (통합 맵 전체 실행)
# =============================================================================================


def _prepare(work):
    """작업 폴더를 만들고 통합 맵 플러그인을 에뮬레이터로 올린다. 반환: (mod, machine, prog, 모델들)"""
    os.environ["EUDEXT_DBG_DIR"] = SYMDIR
    os.makedirs(SYMDIR, exist_ok=True)
    ab = _load_py(os.path.join(EX, "auto_all_build.py"), "auto_all_build")
    ab.generate(work)
    LoadMap(ab.ensure_base())
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(work, "auto_all.eps"), {})
    prog = emu.Program(mod.afterTriggerExec, setup=getattr(mod, "onPluginStart", None))
    m = prog.build(out=os.path.join(T, "emu_auto_all.scx"))
    scmodel.install(m, units={}, text=True)
    um, _fb = aamodel.prespawn(m)
    lm, dm, cm, sim = aamodel.install_all(m, chk_locations=aamodel.map_locations())
    um.fail_when(lambda rec: rec.unit == 106 and any(um.unit_type(i) == 106 for i in um.units()))
    return mod, m, prog, (um, lm, dm, cm, sim)


def run_map(m, sim, cycles, addr, total, step=FRAMES_STEP, chat_at=None, cm=None):
    """사이클마다 돌리고 블록 스냅숏을 모은다. chat_at 프레임에 사용자 채팅 줄을 넣는다(assist 구간).

    반환: (스냅숏, 오류, 사이클마다 실행한 트리거 수) — 마지막 것은 비용 문서(docs/COSTS.md)의 근거다.
    """
    frames, err, steps = [], None, []
    try:
        for cyc in range(1, cycles + 1):
            if chat_at and cyc == chat_at:
                cm.push_line("\x03Mininii:\x04 !H안녕 éè 가나다".encode())
            m.setdw(0x57F23C, cyc)
            m.cycle()
            steps.append(m.last_steps())
            sim.after_cycle(cyc)
            if cyc % step == 0 or cyc <= 4:
                words = [m.dw(addr + 4 * i) for i in range(total)]
                frames.append([0] * 8 + words[8:])
    except Exception as e:  # noqa: BLE001 — 에뮬레이터 오류도 결과다
        err = "%s: %s" % (type(e).__name__, e)
    return frames, err, steps


def emulate_child(path, cycles, assist=False):
    """자식 프로세스: 통합 맵을 만들어 돌리고 블록 스냅숏을 JSON 으로 남긴다.

    한 프로세스에서 두 번 빌드하면 eudplib 이 EUDFunc 본문을 재사용해(DESIGN 5.1) 함수 안의 dbg 등록이 다시 돌지
    않는다 → 판마다 새 프로세스로 돌린다.
    """
    work = _fresh(os.path.join(T, "map_assist" if assist else "map"))
    _mod, m, prog, (_um, _lm, _dm, cm, sim) = _prepare(work)
    lay = dbg.layout()
    addr, total = lay["addr"], lay["total"]
    t0 = time.time()
    frames, err, steps = run_map(m, sim, cycles, addr, total, chat_at=4980 if assist else None, cm=cm)
    d = [m.dw(addr + 4 * i) for i in range(total)]
    top = sorted(range(len(steps)), key=lambda i: steps[i], reverse=True)[:5]
    doc = {"addr": addr, "total": total, "build": lay["build_id"], "map_name": lay["map_name"],
           "where": lay["where"], "items": len(lay["items"]), "payload": prog.payload_size,
           "frames": frames, "last": d, "err": err, "seconds": round(time.time() - t0, 1),
           "cycles": cycles,
           # 비용: 사이클마다 실행한 트리거 수 (첫 프레임·가장 무거운 프레임·평균)
           "steps_first": steps[0] if steps else None,
           "steps_top": [[i + 1, steps[i]] for i in top],
           "steps_avg": round(sum(steps) / len(steps), 1) if steps else None}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return 0


def _run_child(name, cycles, assist=False):
    """자식 프로세스를 돌려 스냅숏 JSON 을 읽는다."""
    path = os.path.join(T, name)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
               EUDEXT_DBG_DIR=SYMDIR)
    args = [sys.executable, os.path.abspath(__file__), "--emulate", path, "--cycles", str(cycles)]
    if assist:
        args.append("--assist")
    p = subprocess.run(args, env=env, capture_output=True, timeout=1800)
    log = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    if p.returncode != 0 or not os.path.isfile(path):
        print(log[-2000:])
        raise RuntimeError("에뮬레이터 자식 프로세스 실패 (rc=%s)" % p.returncode)
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    doc["sym"] = R.load_symbols(SYMDIR, doc["build"])
    doc["vals"] = R.ext_values(doc["sym"], doc["last"])
    print("  %s: %d 사이클 %.1f초, 블록 0x%X %d dword, 등록 %d, 페이로드 %d B"
          % (name, doc["cycles"], doc["seconds"], doc["addr"], doc["total"], doc["items"], doc["payload"]))
    print("    실행 트리거: 첫 프레임 %s, 평균 %s, 가장 무거운 프레임 %s"
          % (doc.get("steps_first"), doc.get("steps_avg"),
             ", ".join("%d:%d" % (c, s) for c, s in doc.get("steps_top") or [])))
    return doc


def emulate(ck, cycles=6500):
    data = _run_child("frames.json", cycles)
    ck.eq("에뮬레이터 오류", data["err"], None)
    ck.eq("블록 자리·이름", (data["map_name"], data["where"]), ("00_auto_all", "mirror"))
    sym = data["sym"]
    ck.true("심볼 JSON", sym.loaded and sym.ext["map_name"] == "00_auto_all", "")
    vals = data["vals"]
    ended = {k: v[0] for k, v in vals["suites"].items()}
    ck.eq("끝난 단계", sorted(k for k, v in ended.items() if v == 2),
          sorted(k for k in ended if k != "assist"))
    ck.eq("assist 단계는 미실행(사람 조작 없음)", ended["assist"], 0)
    ck.eq("실패한 판정", {k: v for k, v in vals["checks"].items() if v[1] and v[0] != v[1]}, {})
    ran = {k: v for k, v in vals["checks"].items() if v[1]}
    ck.true("판정이 도는 수", len(ran) >= 69, len(ran))
    ck.eq("보고된 결과", {k: v for k, v in vals["results"].items() if v[2] and v[0] != v[1]}, {})
    marks = vals["marks"]
    ck.eq("터보 확인(24 사이클에 게임 프레임 24)", marks["aa.turbo.frames"], 24)
    ck.eq("완료 표식", (marks["aa.done"], marks["aa.assist.skipped"]), (6400, 1))
    ck.eq("CP 어긋남", marks["final.cpbad"], 0)
    # 비용(docs/COSTS.md "자동 점검 통합 맵") — 값이 크게 바뀌면 문서를 고치라는 뜻이다
    ck.true("첫 프레임 실행 트리거 (기록 31,405)", 10000 <= data["steps_first"] <= 60000, data["steps_first"])
    ck.true("가장 무거운 프레임 (기록 60,175 = i128 자체 점검)",
            data["steps_top"][0][1] <= 120000, data["steps_top"][:3])
    ck.eq("units B10-5 F1~F7", [marks["units.B10-5.F%d" % k] for k in range(1, 8)], [68, 2, 3, 1, 0, 1, 1])
    ck.eq("s8 모형 비트 (A2·M)", (marks["s8.SUBX.match"], marks["s8.ADDX.match"]), (2, 1))
    ck.eq("datpatch 피해 배율 시작", marks["datpatch.B15-1.start"], 0x515BA0)
    ck.eq("plot 위치·순서", (marks["plot.D7-1.posbad"], marks["plot.D7-1.orderbad"], marks["plot.D7-4.made"]),
          (0, 0, 211))
    ck.eq("spawn 명령 목표 (A-3)", (marks["spawn.A-3.warp_x"], marks["spawn.A-3.warp_y"],
                                 marks["spawn.E12-1.order_x"], marks["spawn.E12-1.order_y"]),
          (2731, 2048, 2048, 3413))
    ck.eq("bullet 명중·방향", (marks["bullet.D14-1.hits"], marks["bullet.D14-1.facingbad"],
                            marks["bullet.D14-8.shell"]), (8, 0, 210))
    ck.eq("display 자체 점검·이름", (marks["display.E6-8.lastbad"], marks["display.E6-5.same"]), (0, 1))
    ck.eq("chat 드러내기 속도·NUL", (marks["chat.D17-9.delta"], marks["chat.D17-4.nul"],
                                marks["chat.D17-5.front"]), (20, 1, 52))
    texts = {k: v[0] for k, v in vals["texts"].items()}
    ck.true("chat D17-1 줄에 !H 없음", "!H" not in texts["chat.D17-1.line"], texts["chat.D17-1.line"])
    ck.true("chat D17-3 2바이트 UTF-8", "é ñ ü ß ç ø Ω" in texts["chat.D17-3.line"], texts["chat.D17-3.line"])
    ck.true("display 이름 네 개", re.search(r"같아야: (.+?) / \1 / \1 / \1", texts["display.E6-5.line"]) is not None,
            texts["display.E6-5.line"])
    return data


def emulate_assist(ck, cycles=5200):
    """사람 조작 구간: 채팅 줄을 넣어 assist 단계가 돌고 끝나는지."""
    data = _run_child("frames_assist.json", cycles, assist=True)
    ck.eq("assist 판 에뮬레이터 오류", data["err"], None)
    vals = data["vals"]
    ck.eq("assist 단계 끝남", vals["suites"]["assist"][0], 2)
    ck.eq("assist 판정", {k: v for k, v in vals["checks"].items() if k.startswith("assist") and v[0] != v[1]}, {})
    ck.true("assist 사용자 줄", "안녕" in vals["texts"]["assist.D17-6.line"][0],
            vals["texts"]["assist.D17-6.line"][0])
    ck.true("완료 표식이 assist 뒤", 0 < vals["marks"]["aa.done"] <= cycles, vals["marks"]["aa.done"])
    return data


# =============================================================================================
# 3. 판정 (오프라인 MapRun)
# =============================================================================================


def _judge(data, spec, fps=24.0, end_reason="스냅숏 끝", say=None):
    t = 1000.0
    mirror = {0x58DC40: 0x80000005, 0x58DC44: 129}
    run = A.MapRun(spec, data["sym"], data["addr"], data["build"], now=t, where="mirror", say=say or (lambda s: None),
                   peek=lambda a, n: tuple(mirror.get(a + 4 * i, 0) for i in range(n)))
    for d in data["frames"]:
        t += 1.0 / fps
        got = run.feed(d, t)
        if got:
            return run.judge(got[0], got[1], d)
    return run.judge(end_reason, "other", data["frames"][-1])


def judge_checks(ck, data, assist):
    spec = A.load_specs([AUTO_ALL_SPEC])["00_auto_all"]
    notes = []
    res = _judge(data, spec, say=notes.append)
    ck.eq("통합 맵 판정", (res["verdict"], res["cause"], res["reason"]), (A.PASS, "done", "완료 표식"))
    st = {s["name"]: s["status"] for s in res["suites"]}
    ck.eq("단계 판정", {k: v for k, v in st.items() if v != A.PASS}, {"assist": A.SKIPPED})
    bad = [x["id"] for x in res["items"] if x["verdict"] == A.FAIL]
    bad += [x["id"] for s in res["suites"] if s["status"] != A.SKIPPED for x in s["items"]
            if x["verdict"] == A.FAIL]
    ck.eq("실패 항목", bad, [])
    manual = {x["id"] for x in res["items"] if x["verdict"] == A.MANUAL}
    manual |= {x["id"] for s in res["suites"] for x in s["items"] if x["verdict"] == A.MANUAL}
    ck.true("사람 확인 항목 15개(D5-2~8·D6-1~5·E6-7·E6-6·D14-13·D5-10)", len(manual) >= 15, sorted(manual))
    ck.true("진행 알림", any("단계 units (1) 시작" in n for n in notes)
            and any("단계 chat: 통과" in n for n in notes), notes[:5])
    lines = A.run_lines(res)
    ck.true("사람이 읽는 줄", lines[0].startswith("맵 00_auto_all") and "통과" in lines[0], lines[0])
    # 확인 문서 행: 항목 id 가 행 번호다
    rows = {c["row"] for x in res["items"] for c in x["checklist"]}
    rows |= {c["row"] for s in res["suites"] for x in s["items"] for c in x["checklist"]}
    for row in ("B10-1", "C3-2", "D7-1", "E12-3", "D14-1", "E6-8", "D17-4", "A-1", "A-2", "B15-1"):
        ck.true("확인 문서 행 " + row, row in rows, sorted(rows)[:10])
    # assist 판
    res2 = _judge(assist, spec)
    st2 = {s["name"]: s["status"] for s in res2["suites"]}
    ck.eq("assist 판 단계 판정", {k: v for k, v in st2.items() if v != A.PASS}, {})
    ck.eq("assist 판 맵 판정", res2["verdict"], A.PASS)
    return res


def mutation_checks(ck, data):
    """일부러 한 phase 를 틀리게 한 변이: 그 단계만 실패로 잡히는가."""
    spec = A.load_specs([AUTO_ALL_SPEC])["00_auto_all"]
    sym = data["sym"]
    ext = sym.ext
    slot = next(c["pass"] for c in ext["checks"] if c["name"] == "spawn.E12-1.count")
    frames = [list(d) for d in data["frames"]]
    for d in frames:
        if d[slot]:
            d[slot] = 0  # 통과 수만 0 으로 (전체 수는 그대로) → spawn 단계 실패
    bad = dict(data, frames=frames)
    res = _judge(bad, spec)
    st = {s["name"]: s["status"] for s in res["suites"]}
    ck.eq("변이: spawn 단계만 실패", sorted(k for k, v in st.items() if v == A.FAIL), ["spawn"])
    ck.eq("변이: 맵 판정 실패", res["verdict"], A.FAIL)
    ids = [x["id"] for s in res["suites"] if s["name"] == "spawn" for x in s["items"] if x["verdict"] == A.FAIL]
    ck.true("변이: E12-1 이 실패", "E12-1" in ids, ids)
    # 완료 표식이 없으면(맵이 끝나기 전에 멈춤) 멈춤으로 잡히는가
    short = dict(data, frames=[list(d) for d in data["frames"][:200]])
    res2 = _judge(short, spec, end_reason="멈춤 — 프레임이 20초 동안 늘지 않음")
    ck.eq("도중 멈춤 판정", res2["verdict"], A.FAIL)
    ck.true("멈춤 뒤 남은 단계는 미실행", any(s["status"] == A.NOT_RUN for s in res2["suites"]), "")


# =============================================================================================
# 4. 계측판 맵 (에뮬레이터 + 맵별 명세)
# =============================================================================================


def _emulate_eds_map(name, eps, cycles, base=None, models=True, chk_locs=True):
    """계측판 맵 하나를 에뮬레이터로 돌린다 (dbg.setup 은 시험이 직접 부른다 — eds 의 dbg_setup 대신)."""
    work = _fresh(os.path.join(T, name))
    for src in (eps,):
        shutil.copy2(src, os.path.join(work, os.path.basename(src)))
    dbg.reset()
    os.environ["EUDEXT_DBG_DIR"] = SYMDIR
    LoadMap(base or os.path.join(_common.PKG, "testing", "auto_all_base.scx"))
    CompressPayload(True)
    dbg.setup(map_name=name, watch_slots=128, probes=256, symbols=SYMDIR)
    mod = build._load_plugin(os.path.join(work, os.path.basename(eps)), {})
    body = getattr(mod, "afterTriggerExec", None) or getattr(mod, "beforeTriggerExec")
    prog = emu.Program(body, setup=getattr(mod, "onPluginStart", None))
    m = prog.build(out=os.path.join(T, "emu_%s.scx" % name))
    scmodel.install(m, units={}, text=True)
    um, _fb = aamodel.prespawn(m)
    sim = None
    if models:
        _lm, _dm, _cm, sim = aamodel.install_all(m, chk_locations=aamodel.map_locations() if chk_locs else None)
    lay = dbg.layout()
    addr, total = lay["addr"], lay["total"]
    frames, err = [], None
    try:
        for cyc in range(1, cycles + 1):
            m.setdw(0x57F23C, cyc)
            m.cycle()
            if sim is not None:
                sim.after_cycle(cyc)
            if cyc % 4 == 0 or cyc <= 4:
                words = [m.dw(addr + 4 * i) for i in range(total)]
                frames.append([0] * 8 + words[8:])
    except Exception as e:  # noqa: BLE001
        err = "%s: %s" % (type(e).__name__, e)
    sym = R.load_symbols(SYMDIR, lay["build_id"])
    d = [m.dw(addr + 4 * i) for i in range(total)]
    return {"frames": frames, "addr": addr, "total": total, "build": lay["build_id"], "sym": sym,
            "vals": R.ext_values(sym, d), "err": err, "machine": m, "mod": mod, "um": um}


def other_maps(ck):
    specs = A.load_specs([SPEC_DIR])
    # 01 S8 (부트 있는 빌드: dbg_report 가 결과를 남긴다)
    got = _emulate_eds_map("01_S8_SubtractTest", os.path.join(_common.PKG, "docs", "spec", "S8_ingame",
                                                              "s8_ingame.py"), 6, models=False)
    ck.eq("01 S8 오류", got["err"], None)
    ck.eq("01 S8 모형 비트", (got["vals"]["marks"]["m01.SUBX.match"], got["vals"]["marks"]["m01.ADDX.match"]), (2, 1))
    res = _judge(got, specs["01_S8_SubtractTest"])
    ck.eq("01 S8 판정", (res["verdict"], [x["id"] for x in res["items"] if x["verdict"] == A.FAIL]), (A.PASS, []))
    # 04 datpatch (발견 ① — 덤프·화면 줄을 더한 계측판)
    got = _emulate_eds_map("04_datpatch_check", os.path.join(EX, "datpatch_ingame.eps"), 2900)
    ck.eq("04 datpatch 오류", got["err"], None)
    ck.eq("04 피해 배율 시작", got["vals"]["marks"]["m04.B15-1.start"], 0x515BA0)
    res = _judge(got, specs["04_datpatch_check"])
    ck.eq("04 datpatch 판정", (res["verdict"], [x["id"] for x in res["items"] if x["verdict"] == A.FAIL]),
          (A.PASS, []))
    # 27 X_limit (유닛 한도 — 위험 세션)
    got = _emulate_eds_map("27_X_limit", os.path.join(EX, "xlimit_ingame.eps"), 160)
    ck.eq("27 X_limit 오류", got["err"], None)
    marks = got["vals"]["marks"]
    ck.true("27 채운 유닛 수", marks["xl.t9.fill"] > 1000, marks["xl.t9.fill"])
    ck.eq("27 한도 뒤 ok·ptr", (marks["xl.t9.ok"], marks["xl.t9.ptr"]), (0, 0))
    ck.eq("27 칸 가득 총알 0 반환", (marks["xl.D14-3.e1"], marks["xl.D14-3.e2"], marks["xl.D14-3.e3"]), (0, 0, 0))
    ck.eq("27 출발=목표 facing", marks["xl.D14-2.same"], 128)
    res = _judge(got, specs["27_X_limit"])
    ck.eq("27 X_limit 판정", (res["verdict"], [x["id"] for x in res["items"] if x["verdict"] == A.FAIL]),
          (A.PASS, []))
    # 08 pool (같은 eds 를 22 멀티로도 쓴다)
    got = _emulate_eds_map("08_pool_check", os.path.join(EX, "pool_ingame.eps"), 70)
    ck.eq("08 pool 오류", got["err"], None)
    res = _judge(got, specs["08_pool_check"])
    ck.eq("08 pool 판정", (res["verdict"], [x["id"] for x in res["items"] if x["verdict"] == A.FAIL]), (A.PASS, []))


# =============================================================================================
# 5. 통합 (Windows): 가짜 게임 + ingame_auto.py
# =============================================================================================


class _Lines:
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


def win32_integration(ck, data):
    if not R.WIN32:
        print("  Windows 가 아님 — 통합 시험 건너뜀")
        return
    work = _fresh(os.path.join(T, "win32"))
    scen = os.path.join(work, "scen.json")
    with open(scen, "w", encoding="utf-8") as f:
        json.dump({"maps": [{"name": "00_auto_all", "where": "mirror", "block_eud": data["addr"],
                             "frames": data["frames"], "mirror": [[0x58DC40, 0x80000005], [0x58DC44, 129]],
                             "fps": 400, "hold": 2.0, "gap": 0.001}], "tail": 2.0, "start_delay": 1.0}, f)
    fake = subprocess.Popen([sys.executable, FAKE, "--replay", scen], env=_env(), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    fl = _Lines(fake)
    try:
        ready = fl.wait_for("READY", 60)
        ck.true("가짜 게임 READY", ready is not None, fl.lines[-3:])
        if ready is None:
            return
        pid = ready.split()[1]
        out = os.path.join(work, "results.json")
        log = os.path.join(work, "results.log")
        rc = subprocess.run([sys.executable, AUTO, "--specs", AUTO_ALL_SPEC, SPEC_DIR, "--symbols", SYMDIR,
                             "--pid", pid, "--out", out, "--log", log, "--maps", "1", "--poll", "0.02",
                             "--scan-interval", "0.2", "--busy-scan-interval", "0.5", "--progress", "1",
                             "--stall", "10", "--max-seconds", "180"], env=_env(), capture_output=True,
                            timeout=300)
        text = rc.stdout.decode("utf-8", "replace") + rc.stderr.decode("utf-8", "replace")
        ck.eq("ingame_auto 종료 코드(모두 통과 → 0)", rc.returncode, 0)
        doc = json.load(open(out, encoding="utf-8"))
        run = doc["runs"][-1]
        ck.eq("Win32 판정", (run["map"], run["verdict"], run["cause"]), ("00_auto_all", A.PASS, "done"))
        st = {s["name"]: s["status"] for s in run["suites"]}
        ck.eq("Win32 단계 판정", {k: v for k, v in st.items() if v != A.PASS}, {"assist": A.SKIPPED})
        for needle in ("판정 시작", "단계 units (1) 시작", "단계 chat", ">>> 다음 맵을 여세요"):
            ck.true("출력: " + needle, needle in text, text[-1500:])
        ck.true("로그 파일", os.path.isfile(log) and "00_auto_all" in open(log, encoding="utf-8").read(), "")
    finally:
        if fake.poll() is None:
            fake.kill()
        fake.wait(timeout=30)


# =============================================================================================
# 6. 빌드 (euddraft)
# =============================================================================================


def builds(ck):
    if os.environ.get("EUDEXT_SKIP_BUILD") or not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음 또는 EUDEXT_SKIP_BUILD — 빌드 시험 건너뜀")
        return
    sys.path.insert(0, TOOLS)
    try:
        import ingame_maps as im
    finally:
        sys.path.remove(TOOLS)
    out = _fresh(os.path.join(T, "maps"))
    work_root = os.path.join(T, "build")
    made = []
    for num in ("00", "01", "04", "27"):
        entry = next(e for e in im.MAPS if e[0] == num)
        try:
            path, res = im.build_one(entry, out, work_root)
        except Exception as e:  # noqa: BLE001
            ck.true("빌드 %s" % num, False, str(e)[:300])
            continue
        made.append(entry)
        ck.true("빌드 %s %s" % (num, entry[1]), res.ok and os.path.isfile(path), res.log[-800:])
        ck.true("빌드 %s 블록 줄" % num, "[eudext.dbg] 블록 mirror" in res.log, res.log[-500:])
        ck.true("빌드 %s 터보" % num, "eudTurbo" in res.log, res.log[-500:])
    # 21 sync 는 선언 수집(eudplib)을 이 프로세스에서 하므로 새 프로세스에서 빌드한다
    # (에뮬레이터가 이미 dbg 를 켜 둔 프로세스에서는 `dbg.watch` 가 게임 루프 훅 뒤라 거절된다)
    e21 = next(e for e in im.MAPS if e[0] == "21")
    if _build_child("21", out, work_root):
        made.append(e21)
        ck.true("빌드 21 %s" % e21[1], os.path.isfile(os.path.join(out, "21_%s.scx" % e21[1])), out)
    else:
        ck.true("빌드 21 %s" % e21[1], False, "자식 프로세스 빌드 실패")
    syms = [n for n in os.listdir(os.path.join(out, "dbg"))] if os.path.isdir(os.path.join(out, "dbg")) else []
    ck.true("심볼 JSON 이 맵 폴더에", any(n.startswith("DebugBridge_00_auto_all") for n in syms), syms)
    # 맵 안의 이름(dbg.setup map_name)이 명세의 map 과 같아야 판정이 붙는다 — 21 sync 처럼 eds 를 만들어 쓰는 맵 포함
    bad = [e[0] for e in made
           if not any(n.startswith("DebugBridge_%s_%s_" % (e[0], e[1])) for n in syms)]
    ck.eq("심볼 맵 이름 = <번호>_<이름>", bad, [])
    specs = im.copy_specs(out)
    ck.true("판정 명세 사본", len(specs) >= 14, len(specs))
    ck.true("RUN.bat (ASCII·CRLF)", _run_bat_ok(im.write_run_bat(out)), "")
    im.write_index(out, [], specs)
    im.write_readme(out, [], specs)
    ck.true("MAPS.md·README.md", os.path.isfile(os.path.join(out, "MAPS.md"))
            and os.path.isfile(os.path.join(out, "README.md")), "")


def _build_child(num, out, work_root):
    """맵 하나를 새 프로세스에서 빌드한다 (선언 수집이 eudplib 을 쓰는 맵 — 21 sync). 반환: 성공 여부."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    p = subprocess.run([sys.executable, os.path.abspath(__file__), "--build", num, out, work_root],
                       env=env, capture_output=True, timeout=1800)
    if p.returncode != 0:
        print((p.stdout + p.stderr).decode("utf-8", "replace")[-1500:])
    return p.returncode == 0


def build_child(num, out, work_root):
    """자식 프로세스: ingame_maps.build_one 하나만 돌린다."""
    sys.path.insert(0, TOOLS)
    try:
        import ingame_maps as im  # noqa: PLC0415
    finally:
        sys.path.remove(TOOLS)
    entry = next(e for e in im.MAPS if e[0] == num)
    path, res = im.build_one(entry, out, work_root)
    ok = res.ok and os.path.isfile(path) and "eudTurbo" in res.log and "[eudext.dbg] 블록 mirror" in res.log
    print("build %s: %s %s" % (num, "OK" if ok else "FAIL", path))
    if not ok:
        print(res.log[-1500:])
    return 0 if ok else 1


def _run_bat_ok(path):
    raw = open(path, "rb").read()
    return (raw.decode("ascii", "strict") is not None and b"\r\n" in raw
            and b"NoDefaultCurrentDirectoryInExePath=" in raw and b"ingame_auto.py" in raw
            and b"PYTHONIOENCODING=utf-8" in raw)


# =============================================================================================


def main():
    if "--emulate" in sys.argv:
        i = sys.argv.index("--emulate")
        path = sys.argv[i + 1]
        cycles = int(sys.argv[sys.argv.index("--cycles") + 1]) if "--cycles" in sys.argv else 6500
        sys.exit(emulate_child(path, cycles, assist="--assist" in sys.argv))
    if "--build" in sys.argv:
        i = sys.argv.index("--build")
        sys.exit(build_child(sys.argv[i + 1], sys.argv[i + 2], sys.argv[i + 3]))
    ck = Checker("t_auto_all (python)")
    python_checks(ck)

    cke = Checker("t_auto_all (에뮬레이터)")
    _fresh(SYMDIR)
    data = emulate(cke)
    assist = emulate_assist(cke)

    ckj = Checker("t_auto_all (판정)")
    judge_checks(ckj, data, assist)
    mutation_checks(ckj, data)

    cko = Checker("t_auto_all (계측판 맵)")
    other_maps(cko)

    ckw = Checker("t_auto_all (Win32 통합)")
    win32_integration(ckw, data)

    ckb = Checker("t_auto_all (빌드)")
    builds(ckb)
    finish(ck.report(), cke.report(), ckj.report(), cko.report(), ckw.report(), ckb.report())


if __name__ == "__main__":
    main()
