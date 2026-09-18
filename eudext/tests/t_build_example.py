"""예제 빌드 시험: 단독 빌드(venv)와 euddraft 0.11 빌드. 부트 뒤 import 와 저장소 청결을 확인한다.

python tests/t_build_example.py      (euddraft 가 없으면 euddraft 부분은 건너뛴다)
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import shutil  # noqa: E402

from eudext.tools import build  # noqa: E402

ck = Checker("t_build_example")
EX = os.path.join(_common.PKG, "examples")
ARTIFACTS = ("__pycache__", "__epspy__")


def repo_artifacts():
    found = []
    for dirpath, dirnames, filenames in os.walk(_common.PKG):
        rel = os.path.relpath(dirpath, _common.PKG)
        if rel.startswith("docs"):
            continue
        for d in dirnames:
            if d in ARTIFACTS:
                found.append(os.path.join(rel, d))
        for f in filenames:
            if f.endswith((".scx", ".pyc")) and not (rel == "testing" and f == "base.scx"):
                found.append(os.path.join(rel, f))
    return found


before = set(repo_artifacts())

# --- 단독 빌드 (예제 파일을 작업 폴더에 복사해서) ---
sa = os.path.join(_common.WORK, "t_build", "standalone")
os.makedirs(sa, exist_ok=True)
for n in ("hello.py", "hello.eps"):
    shutil.copy2(os.path.join(EX, n), os.path.join(sa, n))
out = build.standalone([os.path.join(sa, "hello.py"), os.path.join(sa, "hello.eps")], out=os.path.join(sa, "hello_sa.scx"))
ck.true("standalone output", os.path.getsize(out) > 10000, out)

# --- euddraft 빌드 ---
if os.path.isfile(build.EUDDRAFT):
    work = os.path.join(_common.WORK, "t_build", "euddraft")
    eds, out_map = build.prepare_eds(os.path.join(EX, "hello.eds"), work)
    r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, "hello.log"))
    print("  " + r.summary())
    ck.true("euddraft ok", r.ok, r.log[-2000:])
    ck.true("freeze off", not r.freeze)
    ck.true("boot line", "[eudext] 0.0.1 (eudplib 0.81.0)" in r.log, "")
    ck.true("py import after boot", "eudext.errors 불러옴" in r.log, "")
    ck.true("onPluginStart lazy import", "onPluginStart: eudext._parts 불러옴" in r.log, "")
    ck.true("eps compiled", '[epScript] Compiling "hello.eps"' in r.log, "")
    ck.true("epspy in work", os.path.isfile(os.path.join(work, "__epspy__", "hello.py")))
else:
    print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)

after = set(repo_artifacts())
ck.eq("repo clean", sorted(after - before), [])
finish(ck.report())
