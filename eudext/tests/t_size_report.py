"""용량 되짚기 도구 시험 (tools/size_report.py).

빌드 하나를 재서 (1) 합계가 실제 페이로드와 맞는지, (2) 맵 코드·eudext 줄이 제대로 붙는지,
(3) 감쌌던 `__init__` 이 원래대로 돌아오는지 본다.

python tests/t_size_report.py
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import shutil  # noqa: E402

from eudext.tools import build, size_report  # noqa: E402

ck = Checker("t_size_report")

WORK = os.path.join(_common.WORK, "t_size_report")
os.makedirs(WORK, exist_ok=True)

# i128 을 쓰는 작은 플러그인 — eudext 줄이 표에 잡혀야 한다
PLUG = os.path.join(WORK, "szplug.py")
with open(PLUG, "w", encoding="utf-8") as f:
    f.write(
        "from eudplib import DoActions, SetMemory, SetTo\n"
        "from eudext import i128\n"
        "from eudext.i128 import Int128\n"
        "\n"
        "\n"
        "def afterTriggerExec():\n"
        "    DoActions(SetMemory(0x58A364, SetTo, 1))\n"
        "    a = Int128(0)\n"
        "    b = Int128(0)\n"
        "    a += b\n"
        "    a //= 16\n"
        "    i128.f_fmt(a)\n"
    )

from eudplib.core.eudobj import EUDObject  # noqa: E402

before = {c: c.__dict__.get("__init__") for c in (EUDObject, *EUDObject.__subclasses__())}

out = os.path.join(WORK, "sz.scx")
rep = size_report.measure(lambda: build.standalone([PLUG], out=out))

# (3) 되돌리기 — 감싼 함수가 클래스에 남아 있으면 다음 빌드까지 느려지고 기록이 샌다
after = {c: c.__dict__.get("__init__") for c in (EUDObject, *EUDObject.__subclasses__())}
ck.eq("__init__ 되돌림", [c.__name__ for c in before if before[c] is not after.get(c)], [])

# (1) 합계
ck.true("객체 수", rep.total[0] > 100, rep.total[0])
ck.eq("합계 = 종류별 합", rep.total[1], sum(b for _n, b in rep.by_class.values()))
ck.eq("합계 = 파일별 합", rep.total[1], sum(b for _n, b in rep.by_file.values()))
ck.eq("합계 = 줄별 합", rep.total[1], sum(b for _n, b in rep.by_site.values()))
ck.eq("객체 수 = 파일별 객체 합", rep.total[0], sum(n for n, _b in rep.by_file.values()))
ck.true("RawTrigger 가 대부분", rep.by_class["RawTrigger"][1] > rep.total[1] * 0.5, dict(rep.by_class))
ck.true("빌드 산출", os.path.isfile(rep.out), rep.out)

# (2) 자리 붙이기
files = dict(rep.by_file)
ck.true("i128 이 잡힌다", files.get("eudext/i128.py", [0, 0])[1] > 100000, sorted(files))
ck.true("맵 플러그인이 잡힌다", any(k.endswith("szplug.py") for k in files), sorted(files))
unknown = files.get("(모름)", [0, 0])[1]
ck.true("모르는 몫이 작다", unknown < rep.total[1] * 0.25, "%d / %d" % (unknown, rep.total[1]))
ck.true("eudplib 속살은 갈래별로", any(k.startswith("[eudplib] ") for k in files), sorted(files))
ck.true("줄 번호가 붙는다", any(k.startswith("eudext/i128.py:") for k in rep.by_site), "")

# --- caller 모드: eudext 를 건너뛰고 맵 코드로 몰아 센다 ---
rep2 = size_report.measure(lambda: build.standalone([PLUG], out=out), attribute="caller")
files2 = dict(rep2.by_file)
ck.true("caller 모드에 eudext 줄이 없다", not any(k.startswith("eudext/") for k in files2), sorted(files2))
ck.true("caller 모드가 같은 총량", abs(rep2.total[1] - rep.total[1]) < rep.total[1] * 0.02,
        "%d vs %d" % (rep2.total[1], rep.total[1]))  # fmt: skip

# --- 출력 ---
text = size_report.render(rep, sites=5)
ck.true("표에 파일별", "── 파일별" in text and "eudext/i128.py" in text, text[:400])
ck.true("표에 줄별", "── 줄별 상위 5" in text, text[-600:])

shutil.rmtree(WORK, ignore_errors=True)
finish(ck.report())
