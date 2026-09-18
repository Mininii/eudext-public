"""모든 시험을 따로따로 (새 프로세스에서) 돌린다. 개발 venv 에서:

    (Linux)   .venv/bin/python eudext/tests/run_all.py [이름 일부 ...]
    (Windows) C:\\Users\\whatd\\.venvs\\eud081\\Scripts\\python.exe eudext\\tests\\run_all.py

산출물은 EUDEXT_WORK(없으면 <임시 폴더>/eudext_work)로 간다. 종료 코드 0 = 모두 통과.
"""

import glob
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
COUNT = re.compile(r"^\[(?P<name>[^\]]+)\] (?:결과: )?통과 (?P<ok>\d+), 실패 (?P<fail>\d+)", re.M)


def main(argv):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    work = os.environ.get("EUDEXT_WORK") or os.path.join(tempfile.gettempdir(), "eudext_work")
    os.makedirs(work, exist_ok=True)
    env = dict(os.environ)
    env["EUDEXT_WORK"] = work
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    files = sorted(glob.glob(os.path.join(HERE, "t_*.py")))
    if argv:
        files = [f for f in files if any(a in os.path.basename(f) for a in argv)]
    rows = []
    total_ok = total_fail = 0
    for f in files:
        name = os.path.basename(f)
        t0 = time.time()
        p = subprocess.run([sys.executable, f], cwd=HERE, env=env, capture_output=True)
        out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
        dt = time.time() - t0
        passed = p.returncode == 0 and "RESULT PASS" in out
        ok = sum(int(m.group("ok")) for m in COUNT.finditer(out))
        fail = sum(int(m.group("fail")) for m in COUNT.finditer(out))
        total_ok += ok
        total_fail += fail
        rows.append((name, passed, ok, fail, dt))
        with open(os.path.join(work, name + ".log"), "w", encoding="utf-8") as lf:
            lf.write(out)
        if not passed:
            print("---- %s 출력 (마지막 60줄) ----" % name)
            print("\n".join(out.splitlines()[-60:]))
    print("==== eudext 시험 (작업 폴더 %s) ====" % work)
    for name, passed, ok, fail, dt in rows:
        print("  %-24s %s  통과 %5d  실패 %3d  %5.1fs" % (name, "PASS" if passed else "FAIL", ok, fail, dt))
    allok = all(r[1] for r in rows) and rows
    print("합계: 파일 %d, 판정 통과 %d, 실패 %d → %s" % (len(rows), total_ok, total_fail, "PASS" if allok else "FAIL"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
