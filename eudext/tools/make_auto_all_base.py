"""자동 점검 통합 맵(`auto_all`)의 기준 맵을 만든다 (docs/ingame_auto/classification.md 5.1).

    python eudext/tools/make_auto_all_base.py [--src eudext/testing/base.scx] [--out eudext/testing/auto_all_base.scx]

- `testing/base.scx`(128×128, P1 사람·P2 컴퓨터, P1 맵 리빌러 64, 시작 위치 2, 로케이션 그대로)의 scenario.chk 만 고친
  사본이다. 바꾸는 것은 UNIT 구역 하나: **P1 파이어뱃(유닛 32) 한 기를 (160, 160)** 에 더한다(체력 100%).
  B15-3(시작 1회 dat 목록의 최대 체력 패치가 미리 놓인 유닛에 어떻게 먹는가)을 보는 유닛이다. 통합 맵의 어느 단계도
  파이어뱃을 만들거나 죽이지 않는다(units 단계의 KillUnit 은 마린만).
- eudplib `SaveMap` 을 쓰지 않으므로 페이로드가 없고 SCMDraft 로도 다시 열 수 있다(`make_multi_base.py` 와 같은 방식).
- 이미 파이어뱃이 있는 맵이면 더하지 않는다(여러 번 돌려도 같다).
"""

import argparse
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from make_multi_base import UNIT_SIZE, _section, join_chk, split_chk  # noqa: E402

SRC = os.path.join(PKG, "testing", "base.scx")
OUT = os.path.join(PKG, "testing", "auto_all_base.scx")

FIREBAT = 32
MAP_REVEALER = 101
FIREBAT_XY = (160, 160)
# UNIT 한 칸(36B): serial u32, x u16, y u16, unit u16, relation u16, special u16, valid u16, owner u8, hp% u8,
# shield% u8, energy% u8, resources u32, hangar u16, state u16, unused u32, related serial u32
VALID_OWNER, VALID_HP, VALID_SHIELD, VALID_ENERGY = 0x1, 0x2, 0x4, 0x8


def patch(raw, unit=FIREBAT, owner=0, xy=FIREBAT_XY):
    """chk 바이트 → (새 chk, 더한 수). 같은 (유닛, 주인) 이 이미 있으면 그대로."""
    sections = split_chk(raw)
    units = _section(sections, b"UNIT")
    serial_max = 0
    tmpl = None
    for i in range(len(units) // UNIT_SIZE):
        serial, _x, _y, uid = struct.unpack_from("<IHHH", units, i * UNIT_SIZE)
        serial_max = max(serial_max, serial)
        own = units[i * UNIT_SIZE + 16]
        if uid == unit and own == owner:
            return join_chk(sections), 0
        if uid == MAP_REVEALER and own == owner and tmpl is None:
            tmpl = bytes(units[i * UNIT_SIZE:(i + 1) * UNIT_SIZE])
    if tmpl is None:
        raise SystemExit("P%d 맵 리빌러가 없어 UNIT 칸 틀을 만들 수 없습니다" % (owner + 1))
    e = bytearray(tmpl)
    struct.pack_into("<IHHHHHH", e, 0, serial_max + 1, xy[0], xy[1], unit, 0, 0,
                     VALID_OWNER | VALID_HP | VALID_SHIELD | VALID_ENERGY)
    e[16] = owner
    e[17] = e[18] = e[19] = 100
    struct.pack_into("<IHHII", e, 20, 0, 0, 0, 0, 0)
    units += e
    return join_chk(sections), 1


def build(src=SRC, out=OUT):
    sys.dont_write_bytecode = True
    from eudplib.bindings._rust import mpqapi  # eudplib 0.81 MPQ (개발 도구 전용 — make_multi_base 와 같은 경로)

    m = mpqapi.MPQ.open(os.path.abspath(src))
    raw = bytes(m.extract_file("staredit\\scenario.chk"))
    del m
    new, added = patch(raw)
    out = os.path.abspath(out)
    tmpdir = tempfile.mkdtemp(prefix="eudext_aabase_")
    try:
        work = os.path.join(tmpdir, "map.scx")
        shutil.copyfile(os.path.abspath(src), work)
        chk = os.path.join(tmpdir, "scenario.chk")
        with open(chk, "wb") as f:
            f.write(new)
        mw = mpqapi.MPQ.open(work)
        mw.add_file("staredit\\scenario.chk", chk)
        mw.compact()
        del mw
        check = mpqapi.MPQ.open(work)
        got = bytes(check.extract_file("staredit\\scenario.chk"))
        del check
        if got != new:
            raise SystemExit("저장한 scenario.chk 가 다릅니다")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copyfile(work, out)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return out, added


def main(argv=None):
    ap = argparse.ArgumentParser(description="auto_all 기준 맵 만들기 (base.scx + P1 파이어뱃)")
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    out, added = build(args.src, args.out)
    print("만듦: %s (P1 파이어뱃 %d기 더함, 자리 %d,%d)" % (out, added, *FIREBAT_XY))
    return 0


if __name__ == "__main__":
    sys.exit(main())
