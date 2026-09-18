"""eudext 예제 빌드 스크립트: SCR_DB 선언 → eds(sync 훅 + scrdb 훅) → euddraft (DESIGN 4.18, 5.3).

    python eudext/examples/scrdb_build.py --work <작업 폴더> [--map <입력 맵>] [--venv <euddraft 용 lupa 폴더>]
                                          [--build-id N] [--manifest <경로>] [--stash <폴더>] [--no-run]

sync 예제(`sync_build.py`)와 같은 세 단계다.
1. 선언 수집: 맵 소스를 이 파이썬에서 번역·실행한다. 모듈 최상위의 `sync.Bus(…)`, `scrdb.setup(…)` 만 실행된다.
   `scrdb.setup` 은 SCR_DB 채널 8줄을 버스에 넣는다.
2. eds 생성: 부트(VenvSite, Preload: scrdb) → `[MSQC]` → sync 훅 → scrdb 훅(BuildId·Manifest 설정) → 맵.
   빌드 ID 를 여기서 정해 훅 설정으로 넘기므로 매니페스트와 맵의 빌드 ID 가 같다.
3. euddraft: `tools/build.py` 가 eds 를 작업 폴더로 옮겨 실행한다. scrdb 훅이 매니페스트를 쓰고 `frame()` 을 낸다.
   `--stash` 를 주면 매니페스트를 `<이름표>_<지문>.json` 으로 복사한다(런처 배포본 manifests 폴더용).

Lua 코어 위치는 `EUDEXT_SCRDB_CORE` 환경 변수 또는 기본 자리(tools/lua_consts 모듈 docstring).
맵 파일·eds·훅은 모두 작업 폴더(`<work>/src`)에 만든다. 이 폴더(examples)에는 아무것도 쓰지 않는다.
"""

import argparse
import os
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_MAP = os.path.join(PKG, "testing", "base.scx")
MAP_SOURCE = os.path.join(HERE, "scrdb_ingame.eps")


def default_venv():
    if os.name == "nt":
        return os.path.join(os.path.expanduser("~"), ".venvs", "euddraft011_site")
    return os.path.join(ROOT, ".tools", "euddraft_site")


def generate(work, source=MAP_SOURCE, base_map=BASE_MAP, venv_site=None, build_id=None, manifest=None, core=None,
             frame_hook=True, out_name=None):
    """① 선언 수집 + ② eds 생성. 반환: (eds 경로, ScrDb)"""
    from eudext import scrdb, sync
    from eudext.tools import edsgen

    src_dir = os.path.join(work, "src")
    os.makedirs(src_dir, exist_ok=True)
    name = os.path.basename(source)
    shutil.copy2(source, os.path.join(src_dir, name))
    if build_id is None:
        build_id = int(time.time()) % 0x7FFFFFFF
    os.environ[scrdb.BUILD_ID_ENV] = str(build_id)  # 수집 단계의 setup 도 같은 빌드 ID 로
    buses = sync.collect(os.path.join(src_dir, name), map_path=base_map)  # ① (트리거 없음)
    db = scrdb.current()
    print(db)
    for b in buses:
        print(b.describe())
    eds = os.path.join(src_dir, os.path.splitext(name)[0] + ".eds")
    doc = edsgen.EdsDoc(os.path.relpath(base_map, src_dir), out_name or (os.path.splitext(name)[0] + "_out.scx"))
    doc.header_comment = "eudext scrdb 예제 — examples/scrdb_build.py 가 만든 파일 (빌드 ID %d)" % build_id
    doc.boot(eudext_root=ROOT, eds_dir=src_dir, venv_site=venv_site or default_venv())
    doc.add_sync(hook=True)  # [MSQC] (scrdb 채널 포함) + sync 훅
    doc.add_scrdb(db, build_id=build_id, manifest=manifest or scrdb.default_manifest_path(db.save_key), core=core,
                  frame=frame_hook)
    doc.add_plugin(name)
    doc.freeze = False
    doc.write(eds)
    return eds, db


def build(eds, work):
    """③ euddraft (작업 폴더로 옮겨 실행). 반환: tools.build.BuildResult"""
    from eudext.tools import build as tb

    out_dir = os.path.join(work, "build")
    new_eds, out_map = tb.prepare_eds(eds, out_dir)
    return tb.run_euddraft(new_eds, out_map=out_map, log_path=os.path.join(out_dir, "build.log"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="eudext scrdb 예제 빌드")
    work0 = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
    ap.add_argument("--work", default=os.path.join(work0, "scrdb_example"))
    ap.add_argument("--map", default=BASE_MAP, help="입력 맵 (기본 testing/base.scx — 사람 1명, 2인 확인은 base_multi.scx)")
    ap.add_argument("--venv", default=None, help="euddraft 용 lupa 폴더 (기본: Windows ~/.venvs/euddraft011_site, 그 밖 .tools/euddraft_site)")
    ap.add_argument("--build-id", type=int, default=None)
    ap.add_argument("--manifest", default=None, help="매니페스트 경로 (기본: Windows C:\\Temp\\SCR_DB_manifest_<이름표>.json)")
    ap.add_argument("--core", default=None, help="SCR_DB_Core.lua 경로 (기본: EUDEXT_SCRDB_CORE 또는 기본 자리)")
    ap.add_argument("--stash", default=None, help="매니페스트를 <이름표>_<지문>.json 으로 복사할 폴더")
    ap.add_argument("--no-run", action="store_true", help="eds 만 만들고 euddraft 는 돌리지 않는다")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    work = os.path.abspath(args.work)
    eds, db = generate(work, base_map=os.path.abspath(args.map), venv_site=args.venv, build_id=args.build_id,
                       manifest=args.manifest, core=args.core)
    print("eds:", eds)
    with open(eds, encoding="utf-8") as f:
        print(f.read())
    if args.no_run:
        return 0
    r = build(eds, work)
    if not r.ok:
        print(r.log)
    print(r.summary())
    if r.ok and args.stash:
        from eudext import scrdb

        man = args.manifest or scrdb.default_manifest_path(db.save_key)
        print("매니페스트 보관:", scrdb.stash_manifest(man, args.stash))
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
