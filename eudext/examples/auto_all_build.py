"""자동 점검 통합 맵 `auto_all` 빌드 도우미 (kind="gen" — tools/ingame_maps.py 가 `generate()` 를 부른다).

    python eudext/examples/auto_all_build.py --work <작업 폴더> [--base <기준 맵>] [--no-build]

하는 일
1. 기준 맵(`testing/auto_all_base.scx`)이 없으면 `tools/make_auto_all_base.py` 로 만든다.
2. 단계 모듈(`examples/auto_all/*.eps|*.py`)과 진행기가 import 하는 **원래 확인 맵 소스**(i64_ingame 등)를 작업 폴더로
   복사한다 — euddraft 는 eds 폴더를 `sys.path` 에 두므로 `import aa_units;` 가 그 사본을 찾는다. 저장소에는
   `__epspy__`·산출물을 남기지 않는다.
3. `tools/build.py prepare_eds` 로 eds 를 옮기고(경로 절대화, freeze 끄기) euddraft 를 돌린다.

심볼 JSON 은 환경 변수 `EUDEXT_DBG_DIR`(없으면 `EUDEXT_WORK/dbg`)에 나온다 — 자동 판정 도구의 `--symbols` 에 같은 폴더를 준다.
"""

import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EDS = os.path.join(HERE, "auto_all.eds")
PHASE_DIR = os.path.join(HERE, "auto_all")
BASE = os.path.join(PKG, "testing", "auto_all_base.scx")
# 진행기가 import 하는 원래 확인 맵 소스 (그 맵의 시험 함수를 그대로 쓴다 — 분류 문서 5.3)
IMPORTED = (
    os.path.join(HERE, "i64_ingame.eps"),
    os.path.join(HERE, "i64_ops_ingame.eps"),
    os.path.join(HERE, "i128_ingame.eps"),
    os.path.join(HERE, "numfmt_ingame.eps"),
    os.path.join(HERE, "cmp_example.eps"),
    os.path.join(HERE, "cell_example.eps"),
    os.path.join(HERE, "mathx_ingame.eps"),
    os.path.join(HERE, "strdesign_ingame.eps"),
    os.path.join(PKG, "docs", "spec", "S8_ingame", "s8_ingame.py"),
)


def ensure_base(base=BASE):
    """기준 맵이 없으면 만든다."""
    if not os.path.isfile(base):
        sys.path.insert(0, os.path.join(PKG, "tools"))
        import make_auto_all_base  # noqa: PLC0415

        make_auto_all_base.build(out=base)
    return base


def copy_sources(work):
    """단계 모듈·원래 맵 소스를 작업 폴더로 복사한다. 반환: 복사한 파일 목록."""
    os.makedirs(work, exist_ok=True)
    out = []
    for name in sorted(os.listdir(PHASE_DIR)):
        if name.endswith((".eps", ".py")):
            dst = os.path.join(work, name)
            shutil.copy2(os.path.join(PHASE_DIR, name), dst)
            out.append(dst)
    for src in IMPORTED:
        dst = os.path.join(work, os.path.basename(src))
        shutil.copy2(src, dst)
        out.append(dst)
    return out


def generate(work, base_map=None, eds=EDS):
    """작업 폴더를 준비하고 (새 eds 경로, 출력 맵 경로) 를 돌려준다 (ingame_maps.py kind="gen" 규약)."""
    from eudext.tools import build

    base = ensure_base(base_map or BASE)
    os.makedirs(work, exist_ok=True)
    new_eds, out_map = build.prepare_eds(eds, work)
    copy_sources(work)
    with open(new_eds, encoding="utf-8") as f:
        text = f.read()
    import re

    text = re.sub(r"(?mi)^(\s*input\s*:).*$", lambda m: "%s %s" % (m.group(1), base), text, count=1)
    with open(new_eds, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(text)
    return new_eds, out_map


def main(argv=None):
    ap = argparse.ArgumentParser(description="auto_all 통합 맵 빌드")
    ap.add_argument("--work", default=None, help="작업 폴더 (기본 EUDEXT_WORK/auto_all)")
    ap.add_argument("--base", default=None, help="기준 맵 (기본 testing/auto_all_base.scx)")
    ap.add_argument("--no-build", action="store_true", help="작업 폴더만 준비하고 euddraft 는 돌리지 않는다")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    work = args.work or os.path.join(os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(),
                                                                                   "eudext_work"), "auto_all")
    eds, out_map = generate(work, args.base)
    print("작업 폴더: %s" % work)
    print("eds: %s → %s" % (eds, out_map))
    if args.no_build:
        return 0
    from eudext.tools import build

    r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, "auto_all.log"))
    print(r.summary())
    if not r.ok:
        print("\n".join(r.log.splitlines()[-40:]))
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
