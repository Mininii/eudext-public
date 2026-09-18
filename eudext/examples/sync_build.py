"""eudext 예제 빌드 스크립트: 동기화 입력 선언 → eds 생성 → euddraft (DESIGN 4.12, 5.3).

    python eudext/examples/sync_build.py --work <작업 폴더> [--map <입력 맵>] [--no-run]

euddraft 는 eds 를 플러그인보다 먼저 읽으므로 `[MSQC]` 조각은 같은 빌드 안에서 만들 수 없다.
그래서 맵마다 이런 스크립트를 두고 세 단계로 빌드한다.

1. 선언 수집: 맵 소스(.eps/.py)를 이 파이썬에서 번역·실행한다. 모듈 최상위의 `sync.Bus(…)`,
   `bus.key_down(…)` 만 실행되고 트리거 함수는 부르지 않는다(`sync.collect`).
2. eds 생성: `EdsDoc` 에 부트 → `[MSQC]`(선언 줄) → 훅 플러그인 → 맵 플러그인 순으로 넣고 쓴다.
   훅 파일(`eudext_sync_hook.py`)도 eds 옆에 생긴다.
3. euddraft: `tools/build.py` 가 eds 를 작업 폴더로 옮겨 실행한다(저장소에 산출물이 남지 않는다).

맵 파일·eds·훅은 모두 작업 폴더(`<work>/src`)에 만든다. 이 폴더(examples)에는 아무것도 쓰지 않는다.
"""

import argparse
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

BASE_MAP = os.path.join(PKG, "testing", "base.scx")
MAP_SOURCE = os.path.join(HERE, "sync_example.eps")


def generate(work, source=MAP_SOURCE, base_map=BASE_MAP, sections=None, extra_plugins=()):
    """① 선언 수집 + ② eds 생성. 반환: (eds 경로, 모은 Bus 목록)"""
    from eudext import sync
    from eudext.tools import edsgen

    src_dir = os.path.join(work, "src")
    os.makedirs(src_dir, exist_ok=True)
    name = os.path.basename(source)
    shutil.copy2(source, os.path.join(src_dir, name))
    shutil.copy2(os.path.join(HERE, "dbg_setup.py"), os.path.join(src_dir, "dbg_setup.py"))  # 디버그 브리지 켜기
    for p in extra_plugins:  # 예: NSQC.py 를 eds 폴더에 둘 때
        shutil.copy2(p, os.path.join(src_dir, os.path.basename(p)))

    buses = sync.collect(os.path.join(src_dir, name), map_path=base_map)  # ① (트리거 없음)
    from eudplib import GetChkTokenized

    chk = GetChkTokenized()
    dim, ownr = chk.getsection("DIM"), chk.getsection("OWNR")
    size = (dim[0] | dim[1] << 8, dim[2] | dim[3] << 8)
    humans = sum(1 for p in range(8) if ownr[p] == 6)
    for b in buses:
        print(b.describe(map_size=size, humans=humans))

    eds = os.path.join(src_dir, os.path.splitext(name)[0] + ".eds")
    doc = edsgen.EdsDoc(os.path.relpath(base_map, src_dir), "sync_example_out.scx")
    doc.header_comment = "eudext sync 예제 — examples/sync_build.py 가 만든 파일"
    doc.boot(eudext_root=ROOT, eds_dir=src_dir, preload=["dbg", "sync", "local"])
    doc.add_sync(buses, hook=True, sections=sections)  # ② [MSQC] + 훅
    doc.add_plugin("dbg_setup.py", {"WatchSlots": 128, "Probes": 256},
                   comment="디버그 브리지 (자동 판정 — eudext/tools/ingame_auto.py)")
    doc.add_plugin(name)
    # euddraft 번들 플러그인 — 트리거를 매 프레임 돌린다(인게임 G-1: 없으면 한 사이클이 28~30프레임 = 1.2초)
    doc.add_plugin("eudTurbo", comment="트리거를 매 프레임 실행 (한 사이클 = 한 프레임)")
    doc.freeze = False
    doc.write(eds)
    return eds, buses


def build(eds, work):
    """③ euddraft (작업 폴더로 옮겨 실행). 반환: tools.build.BuildResult"""
    from eudext.tools import build as tb

    out_dir = os.path.join(work, "build")
    new_eds, out_map = tb.prepare_eds(eds, out_dir)
    return tb.run_euddraft(new_eds, out_map=out_map, log_path=os.path.join(out_dir, "build.log"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="eudext sync 예제 빌드")
    work0 = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
    ap.add_argument("--work", default=os.path.join(work0, "sync_example"))
    ap.add_argument("--map", default=BASE_MAP, help="입력 맵 (기본 testing/base.scx — 사람 1명). 2인 시험은 사람 슬롯이 둘 이상인 맵")
    ap.add_argument("--no-run", action="store_true", help="eds 만 만들고 euddraft 는 돌리지 않는다")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    eds, _buses = generate(os.path.abspath(args.work), base_map=os.path.abspath(args.map))
    print("eds:", eds)
    with open(eds, encoding="utf-8") as f:
        print(f.read())
    if args.no_run:
        return 0
    r = build(eds, os.path.abspath(args.work))
    if not r.ok:
        print(r.log)
    print(r.summary())
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
