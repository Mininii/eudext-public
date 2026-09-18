"""인게임 확인 맵을 순서대로 한꺼번에 빌드한다 (docs/INGAME_CHECKLIST.md 의 "확인 순서").

    python eudext/tools/ingame_maps.py --out <폴더> [이름 일부 ...] [--list]

- 각 맵은 `tools/build.py` 처럼 작업 폴더(`EUDEXT_WORK`/ingame_maps/<이름>)로 옮겨 euddraft 로 빌드하고,
  결과를 `<폴더>/<번호>_<이름>.scx` 로 복사한다. 저장소 안에는 산출물을 남기지 않는다.
- `base` 가 "multi" 인 맵은 `testing/base_multi.scx`(P1~P4 사람, `tools/make_multi_base.py`)를 입력으로 쓴다.
- 동기화 입력(`sync`)을 쓰는 맵은 선언 수집 → eds 생성 단계가 먼저 필요하므로 `examples/sync_build.py` 의
  `generate()` 를 거친다(`kind="sync"`).
- 소리 합성처럼 맵 소스 옆에 파일을 만들어야 하는 맵은 `kind="gen"` — 도우미 모듈(`examples/*_build.py`)의
  `generate(work, base_map=…)` 가 (eds, 출력 맵 경로) 를 돌려준다.
- 끝에 `<폴더>/MAPS.md`(번호·파일·확인 항목·여는 방법 표)를 쓴다.

euddraft 위치는 `tools/build.py` 규칙(`EUDEXT_EUDDRAFT` > Windows `C:\\euddraft0.11.0.1` > 저장소 `.tools`)을 따른다.

2026-09-18 보탬 (WP-D 자동 판정)
- **00 auto_all** 이 맨 앞이다: 안전한 자동 점검을 한 맵에서 다 돌린다(`examples/auto_all_build.py`).
- 출력 맵 이름을 `<번호>_<이름>.scx` 로 바꿔 쓴다 → `eudext.dbg` 의 기본 맵 이름(= eds `[main] output`)이
  판정 명세의 `map` 과 같아진다. 계측판 eds 에는 `[dbg_setup.py]`(브리지 켜기)와 `[eudTurbo]`(매 프레임 실행 —
  인게임 G-1: 터보가 없으면 한 사이클이 약 30프레임)가 있다.
- 심볼 JSON 은 `<폴더>/dbg/`, 판정 명세 사본은 `<폴더>/specs/` 에 같이 둔다(`tools/make_ingame_specs.py`).
- `base` 가 "aa" 인 맵은 `testing/auto_all_base.scx`(base + P1 파이어뱃 — B15-3)를 입력으로 쓴다.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile

NL = chr(10)
Q = chr(34)   # 따옴표
B = chr(92)   # 역슬래시
CRLF = chr(13) + chr(10)

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EX = os.path.join(PKG, "examples")
BASE = os.path.join(PKG, "testing", "base.scx")
BASE_MULTI = os.path.join(PKG, "testing", "base_multi.scx")
BASE_AA = os.path.join(PKG, "testing", "auto_all_base.scx")
# 사용자 확인 문서 (README 안내용 — 도구는 사용자가 인자를 줄 때만 쓴다)
CHECKLIST_DOC = os.path.join("C:", os.sep, "Users", "whatd", "Desktop", "Stormcoast Fortress",
                             "ScmDraft 2", "MapSource", "EUDPLIB_PORT_CHECKLIST.md")

# (번호, 이름, eds 또는 맵 소스, 입력 맵 "single"|"multi", 종류 "eds"|"sync", 확인 항목, 여는 방법)
# 번호는 확인 순서다(필수·기반이 되는 것 먼저). docs/INGAME_CHECKLIST.md 의 "확인 순서" 표와 맞춘다.
MAPS = [
    ("00", "auto_all", os.path.join(EX, "auto_all_build.py"), "aa", "gen",
     "안전한 자동 점검 전부 (eudext 91항목 — 단계 19개)",
     "혼자. 그냥 기다린다(약 3분 30초) → 채팅 한 줄(선택, 60초) → 화면 확인 쪽(선택). 판정은 RUN.bat 이 한다"),
    ("01", "S8_SubtractTest", os.path.join(EX, "s8_check.eds"), "single", "eds",
     "A-1 (마스크 Subtract·Add 식)", "혼자. 19줄이 돈다 — SUBX·ADDX 두 줄 (브리지가 자동 판정)"),
    ("02", "i64_check", os.path.join(EX, "i64_ingame.eds"), "single", "eds",
     "C3-1~3 (SC Subtract 부호 없는 포화, 64비트 포화 뺄셈)", "혼자. 약 10초마다 한 줄, '[C3-7] 점검 23 / 23'"),
    ("03", "units_ingame", os.path.join(EX, "units_ingame.eds"), "single", "eds",
     "B10-1~10 (유닛 생성·칸 번호·새 유닛 순회·죽음)", "혼자. [T1]~[T11] 줄"),
    ("04", "datpatch_check", os.path.join(EX, "datpatch_ingame.eds"), "aa", "eds",
     "B15-1·3·4·10 (dat 패치·피해 배율 주소 — 계측판: 화면 줄·덤프 추가)",
     "혼자. 1초 뒤 [B15-1] 두 줄, 2분 뒤 [B15-4] 줄"),
    ("05", "cmp_check", os.path.join(EX, "cmp_example.eds"), "single", "eds",
     "B1-1 (조건 칸 채우기)", "혼자. '점검 15 / 15'"),
    ("06", "cell_check", os.path.join(EX, "cell_example.eds"), "single", "eds",
     "C2-1 (Cell 연산·변수 색인 비교)", "혼자. '점검 18 / 18'"),
    ("07", "mathx_check", os.path.join(EX, "mathx_ingame.eds"), "single", "eds",
     "C9-2 (mathx 값 = CtrigAsm)", "혼자. [C9-2] 줄 — 전체 일치 110 / 110"),
    ("08", "pool_check", os.path.join(EX, "pool_ingame.eds"), "single", "eds",
     "C11-1~7 (pool 사슬 적재·넘침·순회 중 반납)", "혼자. 12프레임부터 2초마다 [T1]~[T7] 줄, 각 줄 '판정 1'"),
    ("09", "strdesign_check", os.path.join(EX, "strdesign_ingame.eds"), "single", "eds",
     "D6-1~5 (StrDesign 색·정렬 — 권장)", "혼자. 6초마다 한 쪽씩 5쪽"),
    ("10", "bullet_check", os.path.join(EX, "bullet_ingame.eds"), "single", "eds",
     "D14-1~8 (총알 방향·실패 0·의도 모르는 칸·종류 교체)", "혼자(P2 컴퓨터). 약 1분 — [D14-번호] 줄과 탄이 간 쪽"),
    ("11", "bgm_check", os.path.join(EX, "bgm_ingame_build.py"), "multi", "gen",
     "D16-1~9 (배경음악: 문자열 칸 채우기·조각 틈·관전자·동기)", "혼자(D16-4 는 관전자, D16-7 은 2인 이상). 약 40초 동안 ①~⑩"),
    ("12", "plot_check", os.path.join(EX, "plot_ingame.eds"), "single", "eds",
     "D7-1~5 (도형 모양·방향·속도·스케줄·반복)", "혼자. [D7-1]~[D7-5] 줄, 마지막 '[D7-5] 점검 15 / 15'"),
    ("13", "chat_check", os.path.join(EX, "chat_ingame.eds"), "single", "eds",
     "D17-1~9 (타자기·채팅 줄)", "혼자, 가장 빠름. 18초 뒤 채팅으로 !H안녕 éè 가나다"),
    ("14", "scrdb_check", os.path.join(EX, "scrdb_ingame.eds"), "single", "eds",
     "D18-1~9 (SCR_DB 런처 연동)", "혼자 + SCR_DB 런처. 2인 확인(D18-6)은 examples/scrdb_build.py --map testing/base_multi.scx"),
    ("15", "i64_ops_check", os.path.join(EX, "i64_ops_ingame.eds"), "single", "eds",
     "D4-1 (i64 곱셈·나눗셈·부호 나눗셈·비트·시프트 — 권장)", "혼자. 약 10초마다 한 줄, '[D4-9] 점검 56 / 56'"),
    ("16", "numfmt_check", os.path.join(EX, "numfmt_ingame.eds"), "single", "eds",
     "D5-1~10 (numfmt 서식·색·전각·이름 표)", "혼자. 약 10초마다 [D5-1]~[D5-9] 줄, '[D5-1] 자체 점검 23 / 23'"),
    ("17", "exit_trap_check", os.path.join(EX, "misc_exit_trap.eds"), "multi", "eds",
     "F19-4 (나가면 멈춤 — 실험 기능, 위험)", "2인 이상. P1 이 나가면 P1 의 스타가 멈추는지 — 맵 안 경고 문구를 먼저 읽는다"),
    ("18", "sprite_check", os.path.join(EX, "sprite_ingame.eds"), "single", "eds",
     "F21-1~7 (28장 스프라이트·CGRP)", "혼자. 약 1분 — [F21-번호] 줄과 모양. F21-7 은 CS_Photo 가 만든 .cgrp 를 EUDEXT_CGRP_DIR 의 sprite_user.cgrp 로 두고 다시 빌드"),
    ("19", "spawn_check", os.path.join(EX, "spawn_ingame.eds"), "single", "eds",
     "E12-1~9 (G_CB 소환 패턴 3종·로케이션 오프바이원 A-3)", "혼자(적 P2). [E12-번호] 줄과 소환 모양, 마지막 자체 점검 11 / 11"),
    ("25", "display_check", os.path.join(EX, "display_ingame.eds"), "multi", "eds",
     "E6-1~10 (DisplayPrint 대체: 관전자·13번째 줄·TBL NUL·이름 주소·0x0D 폭) — **튕길 위험**",
     "P1 혼자(E6-1 은 관전자 PC 하나 더). 6초마다 한 쪽씩 9쪽. 2026-09-18 인게임에서 통합 맵이 이 쪽들(13번째 줄·TBL)에서 EUD ERROR 로 멈췄다 — 멈추면 RUN.bat --once 로 m25.stage 를 읽는다"),
    ("25b", "display_bisect", os.path.join(EX, "display_bisect.eds"), "single", "eds",
     "13번째 줄·TBL 쓰기 좁히기 18단계 (E6-3·4·4b 의 EUD ERROR 범인 찾기) — **튕길 위험**",
     "혼자. 약 20초. 멈추면 그 상태로 RUN.bat --once 를 돌려 bx.stage(마지막 시작)·bx.ok(마지막 성공)를 읽는다"),
    ("24", "i128_check", os.path.join(EX, "i128_ingame.eds"), "single", "eds",
     "F20-1 (i128 덧셈·뺄셈·비교·곱셈·나눗셈·10진 — 권장)", "혼자. 약 1초마다 한 줄, '[F20-9] 점검 46 / 46'"),
    ("26", "switch_check", os.path.join(EX, "switch_ingame.eds"), "single", "eds",
     "A-2 (스위치 표 주소 0x58DC40)", "혼자. 약 2초마다 [A-2] 줄 — 기대 2147483653·129, 조건 줄 둘"),
    ("20", "players_check", os.path.join(EX, "players_example.eds"), "multi", "eds",
     "B8-1~8 (관전자·CP·사람 판정·동맹)", "2인 이상 + 관전자 1명"),
    ("21", "sync_check", os.path.join(EX, "sync_example.eps"), "multi", "sync",
     "B13-1~12 (2인 동기화 입력)", "2~3인 LAN(가능하면 배틀넷)"),
    ("23", "misc_obs_check", os.path.join(EX, "misc_ingame.eds"), "multi", "eds",
     "F19-1~3·5·6 (관전자 채팅 B1 수정·방장·부대 지정·와이드)", "사람 2명 + 관전자 2명 이상"),
    ("22", "pool_multi", os.path.join(EX, "pool_ingame.eds"), "multi", "eds",
     "C11-8 (pool 멀티 — 권장)", "2인 이상. 08 과 같은 맵을 여러 명이 연다"),
    ("27", "X_limit", os.path.join(EX, "xlimit_ingame.eds"), "single", "eds",
     "B10-1(b)·B10-8(한도)·B10-9·D14-3·D14-2(출발=목표) — 튕길 위험",
     "혼자, 버려도 되는 방. 유닛 칸을 가득 채운다(멈출 수 있다). 약 10초"),
]


def _rewrite_input(eds_path, new_input):
    with open(eds_path, encoding="utf-8") as f:
        text = f.read()
    text, n = re.subn(r"(?mi)^(\s*input\s*:).*$", lambda m: "%s %s" % (m.group(1), new_input), text, count=1)
    if n != 1:
        raise RuntimeError("%s 에 input 줄이 없습니다" % eds_path)
    with open(eds_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)


def _rewrite_output(eds_path, work, new_name):
    """eds 의 output 을 `<번호>_<이름>.scx` 로 바꾼다 (dbg 기본 맵 이름 = 이 파일 이름 = 명세의 map)."""
    with open(eds_path, encoding="utf-8") as f:
        text = f.read()
    out_map = os.path.join(work, new_name)
    text, n = re.subn(r"(?mi)^(\s*output\s*:).*$",
                      lambda m: "%s %s" % (m.group(1), out_map), text, count=1)
    if n != 1:
        raise RuntimeError("%s 에 output 줄이 없습니다" % eds_path)
    with open(eds_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    return out_map


def build_one(entry, out_dir, work_root):
    from eudext.tools import build

    num, name, src, base_kind, kind, _items, _how = entry
    base = {"multi": BASE_MULTI, "aa": BASE_AA}.get(base_kind, BASE)
    if not os.path.isfile(base):
        raise RuntimeError("입력 맵이 없습니다: %s (tools/make_multi_base.py 로 만든다)" % base)
    work = os.path.join(work_root, name)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    if kind == "sync":
        sys.path.insert(0, EX)
        try:
            import sync_build  # examples/sync_build.py
        finally:
            sys.path.remove(EX)
        eds, _buses = sync_build.generate(work, source=src, base_map=base)
        new_eds, out_map = build.prepare_eds(eds, os.path.join(work, "build"))
        # sync 판도 output 을 <번호>_<이름>.scx 로 — dbg 기본 맵 이름(= 명세의 map)이 여기서 나온다
        out_map = _rewrite_output(new_eds, os.path.dirname(out_map) or work, "%s_%s.scx" % (num, name))
    elif kind == "gen":  # 맵 소스 옆에 파일(합성 소리 등)을 만들어야 하는 맵 — 도우미의 generate() 가 eds 준비까지 한다
        mod_name = os.path.splitext(os.path.basename(src))[0]
        sys.path.insert(0, EX)
        try:
            mod = __import__(mod_name)
        finally:
            sys.path.remove(EX)
        new_eds, out_map = mod.generate(work, base_map=base)
        out_map = _rewrite_output(new_eds, os.path.dirname(out_map) or work, "%s_%s.scx" % (num, name))
    else:
        new_eds, out_map = build.prepare_eds(src, work)
        _rewrite_input(new_eds, base)
        out_map = _rewrite_output(new_eds, work, "%s_%s.scx" % (num, name))
    env = dict(os.environ, EUDEXT_DBG_DIR=os.path.join(out_dir, "dbg"))
    res = build.run_euddraft(new_eds, out_map=out_map, log_path=os.path.join(work, "euddraft.log"),
                             env=env)
    if not res.ok:
        tail = "\n".join(res.log.splitlines()[-30:])
        raise RuntimeError("%s 빌드 실패 (rc=%s)\n%s" % (name, res.rc, tail))
    dst = os.path.join(out_dir, "%s_%s.scx" % (num, name))
    shutil.copyfile(res.out_map, dst)
    return dst, res


def _spec_maps(specs):
    """목록의 명새 파일에서 판정하는 맵 이름들을 모은다(파일 이름 + 명새 속 map 값)."""
    have = set()
    for x in specs:
        have.add(os.path.splitext(os.path.basename(x))[0])
        try:
            with open(x, encoding="utf-8") as f:
                have.add(json.load(f).get("map"))
        except (OSError, ValueError):
            pass
    return have


def write_index(out_dir, built, specs=()):
    """<폴더>/MAPS.md — 번호·파일·항목·여는 방법·판정 명세 표 (auto_all 이 맨 앞)."""
    have = _spec_maps(specs)
    lines = [
        "# eudext 인게임 확인 맵",
        "",
        "`eudext/tools/ingame_maps.py` 가 만든 파일이다. **00 auto_all 을 먼저** 열면 안전한 자동 점검(91항목)이 한 번에",
        "끝난다. 나머지는 사람이 따로 보는 맵이다(위험·소리·런처·키 조작·멀티·화면). 판정은 `RUN.bat` 을 켜 두면",
        "자동으로 되고(`판정` 칸이 있는 맵), 결과는 `results.json`·`results.log` 에 쌓인다. 자세한 방법은 `README.md`.",
        "",
        "| 번호 | 파일 | 확인 항목 | 여는 방법 | 판정 |",
        "|---|---|---|---|---|",
    ]
    for entry, path in built:
        num, name, _src, _base, _kind, items, how = entry
        base = os.path.splitext(os.path.basename(path))[0]
        judge = "자동" if base in have else "사람"
        lines.append("| %s | `%s` | %s | %s | %s |" % (num, os.path.basename(path), items, how, judge))
    lines += [
        "",
        "모든 맵은 `[eudTurbo]`(트리거를 매 프레임 실행)로 빌드했다 — 인게임 G-1(2026-09-18)에서 터보가 없으면 한 사이클이",
        "약 28~30프레임(1.2초)이라 맵의 시간 안내가 30배 늦게 갔다.",
    ]
    with open(os.path.join(out_dir, "MAPS.md"), "w", encoding="utf-8") as f:
        f.write(NL.join(lines) + NL)


def copy_specs(out_dir):
    """판정 명세를 <폴더>/specs/ 로 만든다(생성기를 돌린다). 반환: 파일 목록."""
    sys.path.insert(0, HERE)
    import make_ingame_specs  # noqa: PLC0415

    spec_dir = os.path.join(out_dir, "specs")
    written = make_ingame_specs.write_all(out_dir=spec_dir, spec_dir=spec_dir, check=True)
    return [p for p, _m in written]


def write_run_bat(out_dir):
    """<폴더>/RUN.bat — 자동 판정 도구를 켜 두는 배치 파일 (ASCII·CRLF)."""
    py = sys.executable
    lines = [
        "@echo off",
        "setlocal",
        "rem eudext in-game auto judge launcher (generated by eudext/tools/ingame_maps.py)",
        "rem 1) open StarCraft: Remastered   2) run this file   3) open 00_auto_all.scx (single player)",
        "set " + Q + "NoDefaultCurrentDirectoryInExePath=" + Q,
        "set " + Q + "PYTHONIOENCODING=utf-8" + Q,
        "set " + Q + "PYTHONUTF8=1" + Q,
        "set " + Q + "PYTHONDONTWRITEBYTECODE=1" + Q,
        "set " + Q + "REPO=" + ROOT + Q,
        "set " + Q + "PY=" + py + Q,
        "set " + Q + "MAPS=%~dp0" + Q,
        "cd /d " + Q + "%REPO%" + Q,
        "echo [eudext] auto judge is running - now open a map in StarCraft: Remastered.",
        "echo [eudext] map folder : %MAPS%",
        "echo [eudext] open 00_auto_all.scx first (alone). Wait about 3 min 30 sec.",
        "echo [eudext] results     : %MAPS%results.json  (log: %MAPS%results.log)",
        "echo [eudext] press Ctrl+C to stop.",
        Q + "%PY%" + Q + " " + Q + "%REPO%" + B + "eudext" + B + "tools" + B + "ingame_auto.py" + Q
        + " --specs " + Q + "%MAPS%specs" + Q + " --symbols " + Q + "%MAPS%dbg" + Q
        + " --out " + Q + "%MAPS%results.json" + Q + " --log " + Q + "%MAPS%results.log" + Q + " %*",
        "echo.",
        "echo [eudext] done. see results.json / results.log",
        "pause",
    ]
    path = os.path.join(out_dir, "RUN.bat")
    with open(path, "w", encoding="ascii", newline=CRLF) as f:
        f.write(NL.join(lines) + NL)
    return path


def write_readme(out_dir, built, specs=()):
    """<폴더>/README.md — 사용자용 사용법 (한국어)."""
    have = _spec_maps(specs)
    auto = [(e, p) for e, p in built if os.path.splitext(os.path.basename(p))[0] in have]
    manual = [(e, p) for e, p in built if os.path.splitext(os.path.basename(p))[0] not in have]
    lines = [
        "# eudext 인게임 확인 — 이렇게 하면 됩니다",
        "",
        "## 0. 2026-09-18 1차 결과 뒤 — 이번에 해 주실 것 (약 8분)",
        "",
        "1차(2026-09-18 05:12)에서 단계 12개가 통과하고 units·plot·bullet 이 값으로 걸렸고, **display 단계에서 게임이",
        "EUD ERROR(0xFF9BE98B)로 멈췄습니다**. 고친 것: 통합 맵에서 13번째 줄·TBL 쓰기(E6-3·4·4b)를 뺐고, 탄막 유닛의",
        "배치 상자 dat 를 쓰게 했고(탄이 하나도 안 만들어진 원인), units·plot 의 기대값을 실제 게임 동작에 맞췄습니다.",
        "",
        "| 순서 | 맵 | 시간 | 보는 것 |",
        "|---|---|---|---|",
        "| 1 | `00_auto_all.scx` | 약 4분 30초 | **끝까지 가는지**. bullet 단계에서 탄이 보이는지(`[D14-0]` 줄의 `첫 탄 epd` 가 0 이 아니어야) |",
        "| 2 | `25b_display_bisect.scx` | 약 20초 | 18단계 중 **어디서 멈추는지**. 멈추면 그대로 두고(또는 강제 종료) `RUN.bat --once` |",
        "| 3 | `25_display_check.scx` | 약 1분 | 13번째 줄·TBL 을 눈으로. 멈추면 `RUN.bat --once` 로 `m25.stage` |",
        "",
        "2·3 은 **멈출 수 있는 맵**입니다 — 버려도 되는 방에서 혼자 여세요. 멈추는 것이 곧 결과입니다.",
        "",
        "## 1. 준비 (한 번)",
        "",
        "1. 이 폴더의 `.scx` 파일을 StarCraft: Remastered 의 `Maps` 폴더(또는 하위 폴더)에 복사합니다.",
        "2. `RUN.bat` 을 두 번 눌러 켜 둡니다. 창에 `프로세스 …에 붙었습니다` 또는 `StarCraft.exe 를 기다립니다` 가 보이면 됩니다.",
        "   (이 창이 자동 판정 도구입니다. 게임 메모리를 **읽기만** 합니다. 끄려면 Ctrl+C.)",
        "3. 스타크래프트를 켜고 아래 순서로 맵을 엽니다. 창에 단계마다 `단계 … 시작/끝`, 맵이 끝나면 `>>> 다음 맵을 여세요` 가 나옵니다.",
        "",
        "## 2. 순서",
        "",
        "### ① 자동 (기다리기만) — `00_auto_all.scx`",
        "",
        "혼자(싱글) 열고 **약 3분 30초 기다립니다**. 그 뒤 화면에 안내가 나오면",
        "",
        "- (선택) 채팅으로 `!H안녕 éè 가나다` 한 줄을 보냅니다 — D17-6·E6-2. 안 해도 60초 뒤 자동으로 끝납니다.",
        "- (선택) 그 뒤로 6초마다 도는 화면 확인 쪽(D5-2~8, D6-1~5, E6-7, E6-6)을 눈으로 봅니다. 사진이 있으면 가장 좋습니다.",
        "- 판정 중에 화면 줄도 그대로 나옵니다 — 옆에서 봐도 어디를 보는지 알 수 있게 phase 마다 안내 줄과 CenterView 가 있습니다.",
        "",
        "이 맵 하나가 **eudext 확인 항목 88개**를 덮습니다(자동 판정 57여 개 + 화면으로 보는 28개).",
        "2026-09-18 인게임 뒤 13번째 줄·TBL 쓰기(E6-3·4·4b)는 이 맵에서 빼고 25·25b 맵으로 옮겼습니다 — 그 세 항목에서",
        "게임이 EUD ERROR 로 멈춰 뒤 단계(chat·final·assist)가 아예 돌지 못했기 때문입니다.",
        "",
        "### ② 브리지가 도와주는 맵 (사람이 조작하거나 위험한 맵)",
        "",
        "| 맵 | 무엇을 하나 |",
        "|---|---|",
    ]
    for e, path in auto:
        if e[0] == "00":
            continue
        lines.append("| `%s` | %s |" % (os.path.basename(path), e[6]))
    lines += [
        "",
        "`RUN.bat` 이 켜져 있으면 이 맵들도 자동으로 판정됩니다(사람 조작 부분은 조작한 값이 기록됩니다).",
        "**27_X_limit 은 유닛 칸을 가득 채워 멈출 수 있습니다** — 버려도 되는 방에서 혼자 열고, 멈추면 강제 종료하세요.",
        "그 자체가 결과입니다(브리지가 어디까지 갔는지 남깁니다).",
        "**25b_display_bisect·25_display_check 도 멈출 수 있습니다** (2026-09-18 EUD ERROR 0xFF9BE98B).",
        "멈추면 게임을 그대로 두거나 끄고 `RUN.bat --once` 를 한 번 돌리세요 — 블록에 남은 단계 표식(`bx.stage`·`bx.ok`,",
        "`m25.stage`)이 어느 쓰기에서 멈췄는지 알려 줍니다. 단계 표는 `eudext/examples/display_bisect.py` 머리말입니다.",
        "",
        "### ③ 사람이 눈·귀로 보는 맵 (판정 없음)",
        "",
        "①(통합 맵)이 같은 값을 이미 판정합니다 — 값이 어긋났을 때 좁히거나, 모양을 크게 보려고 여는 맵입니다.",
        "",
        "| 맵 | 무엇을 보나 |",
        "|---|---|",
    ]
    for e, path in manual:
        lines.append("| `%s` | %s |" % (os.path.basename(path), e[5]))
    lines += [
        "",
        "## 3. 결과",
        "",
        "- `results.json` — 판정 결과(맵마다 항목·단계·값). 사람이 읽는 줄은 `results.log`.",
        "- `results.json.progress.json` — 도는 중의 진행(마지막 단계·프레임). 게임이 멈추면 여기서 어디까지 갔는지 봅니다.",
        "- `dbg/` — 맵마다의 심볼 JSON(빌드 ID 짝). 지우지 마세요(판정에 필요합니다).",
        "- `specs/` — 판정 명세(항목 번호 = 확인 문서 번호).",
        "- 결과를 확인 문서에 자동으로 적고 싶으면 `RUN.bat` 에 인자를 더해 켭니다:",
        "  `RUN.bat --write-checklist " + CHECKLIST_DOC + "`",
        "  (빈 `결과` 칸에만 `자동: 통과 (날짜)` 를 씁니다. 이미 적힌 칸은 건드리지 않습니다.)",
        "",
        "## 4. 사람이 따로 봐야 하는 항목",
        "",
        "- 통합 맵 안에서 화면으로 보는 항목: `eudext/docs/INGAME_CHECKLIST.md` 의 **화면 확인** 표(D5-2~8, D6-1~5, E6-7, E6-6,",
        "  그리고 값은 자동이지만 모양은 눈으로 보는 D7-1~3·E12-1~7·D14-1·2·8·9·13·E6-9·D17-1·3·7·8).",
        "- E6-3·E6-4·E6-4b(13번째 줄·TBL)는 25·25b 맵에서만 봅니다.",
        "- 멀티·관전자·소리·런처 항목: 위 ②·③ 표의 맵들.",
        "- 게임이 필요 없는 항목(C9-1·D7-6·D18-9·B15-2·9)은 문서에 방법이 적혀 있습니다.",
        "",
        "## 5. 문제가 생기면",
        "",
        "- `RUN.bat` 창에 `eudext 심볼을 찾지 못했습니다` → `dbg/` 폴더가 비었는지 보세요(맵을 다시 빌드하면 채워집니다).",
        "- `판정 명세가 없어 건너뜁니다` → 그 맵은 사람이 보는 맵입니다(③ 표).",
        "- `멈춤`/`튕김` 으로 끝나면 `results.log` 의 마지막 `단계 …` 줄이 어디서 멈췄는지 알려 줍니다.",
        "- `시간 초과 … [eudTurbo] 가 빠진 것 같습니다` → 그 맵은 옛 판입니다. 이 폴더의 맵으로 다시 복사하세요",
        "  (이 폴더의 맵은 모두 트리거를 매 프레임 돌립니다 — 그래서 시간 안내가 초 단위로 맞습니다).",
        "- 통합 맵의 첫 판정 `G-5`(터보)가 실패하면 나머지 시간 안내도 다 어긋납니다 — 먼저 알려 주세요.",
    ]
    path = os.path.join(out_dir, "README.md")
    with open(path, "w", encoding="utf-8", newline=NL) as f:
        f.write(NL.join(lines) + NL)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="인게임 확인 맵 일괄 빌드")
    ap.add_argument("names", nargs="*", help="이름 일부 (없으면 전부)")
    ap.add_argument("--out", required=False, help="결과 폴더")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--docs-only", action="store_true",
                    help="맵을 다시 빌드하지 않고 명세·MAPS.md·RUN.bat·README.md 만 다시 쓴다")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    entries = sorted((e for e in MAPS if not args.names or any(n in e[1] for n in args.names)), key=lambda e: e[0])
    if args.list or not args.out:
        for e in entries:
            print("%s  %-22s %-6s %s" % (e[0], e[1], e[3], e[5]))
        return 0
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    work_root = os.path.join(
        os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work"), "ingame_maps"
    )
    built, failed = [], []
    if args.docs_only:
        for e in sorted(MAPS, key=lambda e: e[0]):
            dst = os.path.join(out_dir, "%s_%s.scx" % (e[0], e[1]))
            if os.path.exists(dst):
                built.append((e, dst))
        specs = copy_specs(out_dir)
        write_index(out_dir, built, specs)
        write_run_bat(out_dir)
        write_readme(out_dir, built, specs)
        print("맵 %d개 기준으로 명세 %d개·MAPS.md·RUN.bat·README.md 를 다시 썼습니다" % (len(built), len(specs)))
        return 0
    for e in entries:
        try:
            dst, res = build_one(e, out_dir, work_root)
            built.append((e, dst))
            print("OK   %s  %.1fs  %s" % (e[0], res.seconds, dst))
        except Exception as ex:  # noqa: BLE001 — 한 맵의 실패가 나머지를 막지 않게
            failed.append(e)
            print("FAIL %s %s: %s" % (e[0], e[1], ex))
    specs = []
    if not args.names:
        try:
            specs = copy_specs(out_dir)
        except Exception as ex:  # noqa: BLE001
            print("명세 생성 실패: %s" % ex)
        write_index(out_dir, built, specs)
        write_run_bat(out_dir)
        write_readme(out_dir, built, specs)
        print("판정 명세 %d개, RUN.bat·README.md 를 %s 에 썼습니다" % (len(specs), out_dir))
    print("완료 %d, 실패 %d" % (len(built), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
