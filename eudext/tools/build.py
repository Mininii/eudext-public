"""빌드 실행 도구 (DESIGN 2.3, 5.3).

단독 빌드 (개발 venv 의 eudplib 으로 LoadMap/SaveMap, euddraft 없이):
    python tools/build.py standalone examples/hello.py --base testing/base.scx --out <작업폴더>/hello_sa.scx

euddraft 빌드 (eds 를 작업 폴더로 옮겨 실행 — 산출물·__epspy__ 가 저장소에 남지 않는다):
    python tools/build.py euddraft examples/hello.eds --work <작업폴더> [--freeze on|off|keep]

- 단독 빌드는 euddraft payloadMain 과 같은 순서로 싣는다: onPluginStart → 루프(게임 루프 시작점 →
  beforeTriggerExec → RunTrigTrigger → afterTriggerExec(역순) → EUDDoEvents). freeze 는 없다.
- euddraft 빌드는 표준 입력을 비워 실행한다(플러그인 오류 때 euddraft 가 입력을 기다리므로).
- euddraft 위치: `EUDEXT_EUDDRAFT` 환경 변수 > Windows `C:\\euddraft0.11.0.1\\euddraft.exe` >
  Linux `<저장소>/.tools/euddraft0.11.0.1/euddraft`(setup_ubuntu.sh 가 푼다) > PATH 의 `euddraft`.
- eds 의 경로 값은 `\\` 와 `/` 둘 다 받는다(Linux 에서는 `\\` 를 `/` 로 바꿔 읽는다).
- freeze 끄기: eds 에 `[freeze]` + `freeze : 0` (키가 있으면 꺼짐). `--freeze off` 가 이것을 넣는다(기본).
  `keep` 은 eds 그대로(euddraft 0.11 은 [freeze] 섹션이 없으면 freeze 가 켜진다).
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
BASE_MAP = os.path.join(PKG, "testing", "base.scx")


def _default_euddraft():
    """euddraft 실행 파일 위치: 환경 변수 EUDEXT_EUDDRAFT > (Windows) C:\\euddraft0.11.0.1 > (그 밖) 저장소 .tools > PATH."""
    env = os.environ.get("EUDEXT_EUDDRAFT")
    if env:
        return env
    if os.name == "nt":
        return r"C:\euddraft0.11.0.1\euddraft.exe"
    local = os.path.join(ROOT, ".tools", "euddraft0.11.0.1", "euddraft")
    if os.path.isfile(local):
        return local
    return shutil.which("euddraft") or local


EUDDRAFT = _default_euddraft()


def _native(p):
    """eds 경로 값의 구분자를 이 OS 에 맞춘다(Windows 에서 쓴 `..\\x` 를 Linux 에서도 읽게)."""
    return p.replace("\\", "/") if os.sep == "/" else p

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

__all__ = ["BuildResult", "EUDDRAFT", "prepare_eds", "read_eds", "run_euddraft", "standalone"]


def _default_work():
    return os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")


# ---------------------------------------------------------------------------------------------
# 단독 빌드
# ---------------------------------------------------------------------------------------------


def _load_plugin(path, settings):
    """euddraft pluginLoader 처럼 플러그인을 불러온다(settings 를 넣은 새 모듈, sys.modules 등록)."""
    from importlib.machinery import SourceFileLoader

    from eudplib import EPSLoader

    path = os.path.abspath(path)
    name = os.path.splitext(os.path.basename(path))[0]
    mod = types.ModuleType(name)
    mod.__dict__["settings"] = dict(settings or {})
    loader = EPSLoader(name, path) if path.endswith(".eps") else SourceFileLoader(name, path)
    mod.__loader__ = loader
    sys.modules[name] = mod
    old = os.getcwd()
    d = os.path.dirname(path)
    added = d not in sys.path
    if added:
        sys.path.insert(1, d)
    try:
        loader.exec_module(mod)
    finally:
        os.chdir(old)
    return mod


def standalone(plugins, base=BASE_MAP, out=None, settings=None):
    """개발 venv 에서 플러그인(.py/.eps)들을 euddraft 와 같은 틀로 싣고 SaveMap 한다.

    plugins: 경로 목록. settings: {경로: dict}. eudext 부트는 필요 없다(이 프로세스의 sys.path 에 ROOT 가 있다).
    반환: 출력 경로
    """
    from eudplib import CompressPayload, EUDDoEvents, EUDEndInfLoop, EUDFunc, EUDInfLoop, LoadMap, RunTrigTrigger, SaveMap

    from eudext import _compat

    if isinstance(plugins, str):
        plugins = [plugins]
    out = out or os.path.join(_default_work(), "standalone_out.scx")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    _compat.check()
    _compat.reset_build_state()
    LoadMap(base)
    mods = [_load_plugin(p, (settings or {}).get(p)) for p in plugins]
    starts = [getattr(m, "onPluginStart", None) for m in mods]
    befores = [getattr(m, "beforeTriggerExec", None) for m in mods]
    afters = [getattr(m, "afterTriggerExec", None) for m in mods]

    @EUDFunc
    def payload_main():
        for f in starts:
            if f:
                f()
        if EUDInfLoop()():
            _compat.set_game_loop_start()
            for f in befores:
                if f:
                    f()
            RunTrigTrigger()
            for f in reversed(afters):
                if f:
                    f()
            EUDDoEvents()
        EUDEndInfLoop()

    CompressPayload(True)
    SaveMap(out, payload_main)
    return out


# ---------------------------------------------------------------------------------------------
# euddraft 빌드
# ---------------------------------------------------------------------------------------------

_HEADER = re.compile(r"\[(.+)\]$")
_KV = re.compile(r"(([^\\:=]|\\.)+)\s*[:=]\s*(.+)$")


def read_eds(path):
    """eds 를 [(섹션, [(키, 값 또는 None, 원문 줄)])] 로 읽는다 (euddraft readconfig 와 같은 규칙, 주석 `::`)."""
    out = []
    cur = None
    with open(path, encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            m = _HEADER.fullmatch(line)
            if m:
                cur = (m.group(1), [])
                out.append(cur)
                continue
            if line.startswith("::"):
                continue
            if cur is None:
                raise ValueError("%s: 섹션 밖의 줄 %r" % (path, line))
            m = _KV.fullmatch(line)
            if m:
                cur[1].append((m.group(1).strip(), m.group(3), line))
            else:
                cur[1].append((line, None, line))
    return out


_PATH_KEYS = {"eudextroot", "venvsite", "pycacheprefix", "dbgdir"}


def prepare_eds(eds, work, freeze="off", pycache=True):
    """eds 를 작업 폴더로 옮긴다: eds 폴더의 플러그인 파일은 복사, 나머지 경로는 절대 경로로, 출력은 작업 폴더로.

    반환: (새 eds 경로, 출력 맵 경로)
    """
    eds = os.path.abspath(eds)
    src_dir = os.path.dirname(eds)
    os.makedirs(work, exist_ok=True)
    secs = read_eds(eds)
    lines = [":: %s 에서 옮김 (eudext tools/build.py, %s)" % (eds, datetime.datetime.now().isoformat(timespec="seconds"))]
    out_map = None
    has_freeze = False
    for name, items in secs:
        new_name = name
        is_boot = os.path.basename(name).lower() == "boot.py"
        if name.lower().endswith((".py", ".eps")):
            nn = _native(name)
            p = nn if os.path.isabs(nn) else os.path.normpath(os.path.join(src_dir, nn))
            if is_boot and pycache:
                # 동결된 euddraft 는 PYTHONPYCACHEPREFIX·PYTHONDONTWRITEBYTECODE 를 무시한다(WP0 실측).
                # boot.py 자신은 PycachePrefix 를 정하기 전에 컴파일되므로 사본을 작업 폴더에 둔다.
                shutil.copy2(p, os.path.join(work, "eudext_boot.py"))
                new_name = "eudext_boot.py"
            elif os.path.normcase(os.path.dirname(p)) == os.path.normcase(src_dir):
                shutil.copy2(p, os.path.join(work, os.path.basename(p)))
                new_name = os.path.basename(p)
            else:
                new_name = p
        if name == "freeze":
            has_freeze = True
            if freeze == "off":
                items = [("freeze", "0", "freeze : 0")]
            elif freeze == "on":
                items = []
        lines.append("")
        lines.append("[%s]" % new_name)
        for key, val, raw in items:
            if name == "main" and key in ("input", "output"):
                if key == "input":
                    val = os.path.normpath(os.path.join(src_dir, _native(val)))
                else:
                    val = os.path.join(work, os.path.basename(_native(val)))
                    out_map = val
                lines.append("%s : %s" % (key, val))
            elif is_boot and val is not None and key.lower() in _PATH_KEYS:
                val = re.sub(r"\s+;.*$", "", val).strip()  # boot.py 와 같게 끝 주석을 뗀다
                lines.append("%s : %s" % (key, os.path.normpath(os.path.join(src_dir, _native(val)))))
            else:
                lines.append(raw)
        if is_boot and pycache and not any(k.lower() == "pycacheprefix" for k, _v, _r in items):
            lines.append("PycachePrefix : %s" % os.path.join(work, "pycache"))
    if not has_freeze and freeze in ("off", "on"):
        lines.append("")
        lines.append("[freeze]")
        if freeze == "off":
            lines.append("freeze : 0")
    new_eds = os.path.join(work, os.path.basename(eds))
    with open(new_eds, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    return new_eds, out_map


class BuildResult:
    def __init__(self, rc, log, out_map, seconds, eds):
        self.rc = rc
        self.log = log
        self.out_map = out_map
        self.seconds = seconds
        self.eds = eds

    @property
    def freeze(self):
        return "[[ freeze activated ]]" in self.log

    @property
    def ok(self):
        return (
            self.rc == 0
            and self.out_map is not None
            and os.path.isfile(self.out_map)
            and "Output scenario.chk" in self.log
            and "[Error]" not in self.log
        )

    def summary(self):
        size = os.path.getsize(self.out_map) if self.out_map and os.path.isfile(self.out_map) else None
        m = re.search(r"Output scenario\.chk : ([\d.]+MB)", self.log)
        return "%s rc=%s %.1fs chk=%s scx=%s freeze=%s -> %s" % (
            "OK" if self.ok else "FAIL", self.rc, self.seconds, m.group(1) if m else "-", size, self.freeze, self.out_map)


def _decode(b):
    for enc in ("utf-8", "cp949"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def run_euddraft(eds, exe=EUDDRAFT, timeout=600, log_path=None, out_map=None, env=None):
    """euddraft 를 표준 입력을 비워 실행한다. eds 경로는 절대 경로로 넘긴다(eds 폴더가 sys.path[0] 이 된다)."""
    eds = os.path.abspath(eds)
    if out_map and os.path.isfile(out_map):
        os.remove(out_map)
    t0 = time.time()
    p = subprocess.run(
        [exe, eds],
        cwd=os.path.dirname(eds),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        env=env,
    )
    log = _decode(p.stdout)
    if log_path:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log)
    return BuildResult(p.returncode, log, out_map, time.time() - t0, eds)


def main(argv=None):
    ap = argparse.ArgumentParser(description="eudext 빌드 도구")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("standalone", help="개발 venv 에서 LoadMap/SaveMap")
    a.add_argument("plugins", nargs="+")
    a.add_argument("--base", default=BASE_MAP)
    a.add_argument("--out", default=None)
    b = sub.add_parser("euddraft", help="euddraft 로 eds 빌드 (작업 폴더에서). 실행 파일은 --exe 또는 EUDEXT_EUDDRAFT")
    b.add_argument("eds")
    b.add_argument("--work", default=None)
    b.add_argument("--exe", default=EUDDRAFT)
    b.add_argument("--freeze", choices=("off", "on", "keep"), default="off")
    b.add_argument("--in-place", action="store_true", help="작업 폴더로 옮기지 않고 eds 그대로 실행")
    b.add_argument("--show-log", action="store_true")
    args = ap.parse_args(argv)

    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if args.cmd == "standalone":
        sys.dont_write_bytecode = True
        out = standalone(args.plugins, args.base, args.out)
        print("단독 빌드:", out, os.path.getsize(out), "B")
        return 0

    work = os.path.abspath(args.work or os.path.join(_default_work(), "build", os.path.splitext(os.path.basename(args.eds))[0]))
    if args.in_place:
        eds, out_map = os.path.abspath(args.eds), None
        for name, items in read_eds(eds):
            if name == "main":
                for k, v, _r in items:
                    if k == "output":
                        out_map = os.path.join(os.path.dirname(eds), _native(v))
    else:
        eds, out_map = prepare_eds(args.eds, work, freeze=args.freeze)
    log_path = os.path.join(os.path.dirname(eds), os.path.splitext(os.path.basename(eds))[0] + ".log")
    r = run_euddraft(eds, args.exe, log_path=log_path, out_map=out_map)
    if args.show_log or not r.ok:
        print(r.log)
    print(r.summary())
    print("로그:", log_path)
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
