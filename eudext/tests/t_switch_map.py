"""A-2 스위치 표 확인 맵(`examples/switch_ingame.py`) 시험: 에뮬레이터에서 스위치 칸 값과 출력 경로, euddraft 빌드.

python tests/t_switch_map.py
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import os  # noqa: E402

import _common  # noqa: F401,E402
from _common import Checker, finish  # noqa: E402

from eudplib import CompressPayload, LoadMap  # noqa: E402

from eudext.testing import emu, scmodel  # noqa: E402
from eudext.testing.harness import BASE_MAP  # noqa: E402

EX = os.path.join(_common.PKG, "examples")


def emulate(ck):
    from eudext.tools import build

    LoadMap(BASE_MAP)
    CompressPayload(True)
    mod = build._load_plugin(os.path.join(EX, "switch_ingame.py"), {})
    prog = emu.Program(mod.beforeTriggerExec)
    prog.watch("tick", mod._tick)
    m = prog.build()
    scmodel.install(m, text=True)
    err = None
    try:
        for _ in range(60):
            m.cycle()
    except emu.EmuError as e:
        err = str(e)
    ck.eq("에뮬레이터 오류", err, None)
    ck.eq("스위치 칸 0 (Switch 1·3·32)", m.dw(scmodel.SWITCH_TABLE), mod.EXPECT_W0)
    ck.eq("스위치 칸 1 (Switch 33·40)", m.dw(scmodel.SWITCH_TABLE + 4), mod.EXPECT_W1)
    for sw, on in ((0, True), (1, False), (2, True), (31, True), (32, True), (39, True), (40, False)):
        ck.eq("스위치 %d" % sw, scmodel.read_switch(m, sw), on)
    ck.eq("기대값 상수", (mod.EXPECT_W0, mod.EXPECT_W1), (2147483653, 129))
    ck.eq("출력 주기(48 사이클마다 0 으로)", m.var("tick"), 60 - 48)
    texts = m.text_model.texts() if hasattr(m, "text_model") else []
    ck.true("출력이 한 번 이상", len(texts) >= 1, "기록 %r" % (texts,))


def eds_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    work = os.path.join(_common.WORK, "t_switch_map_build")
    eds, out_map = build.prepare_eds(os.path.join(EX, "switch_ingame.eds"), work)
    r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, "switch_ingame.log"))
    print("  " + r.summary())
    ck.true("euddraft switch_ingame", r.ok, r.log[-2000:])


def main():
    ck = Checker("t_switch_map")
    emulate(ck)
    eds_build(ck)
    finish(ck.report())


if __name__ == "__main__":
    main()
