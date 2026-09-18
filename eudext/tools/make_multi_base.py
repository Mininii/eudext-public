"""여러 명이 함께 여는 인게임 확인용 기준 맵을 만든다 (docs/INGAME_CHECKLIST.md 의 2인 이상 항목).

    python eudext/tools/make_multi_base.py [--humans 4] [--src eudext/testing/base.scx] [--out eudext/testing/base_multi.scx]

- `testing/base.scx`(P1 사람, P2 컴퓨터)의 scenario.chk 만 고친 사본을 만든다. eudplib `SaveMap` 을 쓰지 않으므로
  페이로드가 들어가지 않고, SCMDraft 로도 다시 열 수 있다(eudplib 이 저장한 맵과 달리 가짜 ISOM 이 없다).
- 바꾸는 것: OWNR(P1~Pn = 사람 6, 나머지 P1~P8 = 비활성 0), FORC(P1~Pn 을 세력 1 로), UNIT(없는 시작 위치(214)를
  P1 시작 위치 오른쪽에 32픽셀 간격으로 더함). SIDE·IOWN·지형·로케이션·맵 리빌러(P1 소유)는 그대로다.
- 관전자 슬롯은 CHK 가 아니라 방 설정이다(SC:R 사용자 지정 게임 방에서 관전자로 들어간다).
"""

import argparse
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SRC = os.path.join(PKG, "testing", "base.scx")
OUT = os.path.join(PKG, "testing", "base_multi.scx")

OWNR_HUMAN, OWNR_INACTIVE = 6, 0
START_LOCATION = 214
UNIT_SIZE = 36


def split_chk(raw):
    """CHK 바이트를 [(이름, 데이터)] 로 나눈다(같은 이름이 여러 번이면 순서대로 모두)."""
    out, i = [], 0
    while i + 8 <= len(raw):
        name = raw[i : i + 4]
        (size,) = struct.unpack_from("<i", raw, i + 4)
        if size < 0 or i + 8 + size > len(raw):
            break
        out.append((name, bytearray(raw[i + 8 : i + 8 + size])))
        i += 8 + size
    return out


def join_chk(sections):
    return b"".join(name + struct.pack("<I", len(data)) + bytes(data) for name, data in sections)


def _section(sections, name):
    found = [d for n, d in sections if n == name]
    if not found:
        raise SystemExit("scenario.chk 에 %r 구역이 없습니다" % name)
    return found[-1]  # SC 는 같은 이름이면 마지막 것을 쓴다


def patch(raw, humans):
    if not 1 <= humans <= 8:
        raise SystemExit("--humans 는 1~8 이어야 합니다")
    sections = split_chk(raw)
    ownr = _section(sections, b"OWNR")
    for p in range(8):
        ownr[p] = OWNR_HUMAN if p < humans else OWNR_INACTIVE
    forc = _section(sections, b"FORC")
    for p in range(humans):
        forc[p] = 0
    unit = _section(sections, b"UNIT")
    starts = {}
    serial_max = 0
    for i in range(len(unit) // UNIT_SIZE):
        serial, x, y, uid = struct.unpack_from("<IHHH", unit, i * UNIT_SIZE)
        serial_max = max(serial_max, serial)
        owner = unit[i * UNIT_SIZE + 16]
        if uid == START_LOCATION:
            starts[owner] = (i, x, y)
    if 0 not in starts:
        raise SystemExit("P1 시작 위치가 없습니다")
    tmpl_i, x0, y0 = starts[0]
    tmpl = unit[tmpl_i * UNIT_SIZE : (tmpl_i + 1) * UNIT_SIZE]
    added = 0
    for p in range(humans):
        if p in starts:
            continue
        e = bytearray(tmpl)
        serial_max += 1
        struct.pack_into("<IHH", e, 0, serial_max, x0 + 32 * p, y0)
        e[16] = p
        unit += e
        added += 1
    return join_chk(sections), added


def main(argv=None):
    ap = argparse.ArgumentParser(description="여러 명 인게임 확인용 기준 맵 만들기")
    ap.add_argument("--humans", type=int, default=4)
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)

    sys.dont_write_bytecode = True
    from eudplib.bindings._rust import mpqapi  # eudplib 0.81 MPQ (비공개 경로 — 개발 도구 전용, 라이브러리 본체는 쓰지 않는다)

    src = mpqapi.MPQ.open(os.path.abspath(args.src))
    raw = bytes(src.extract_file("staredit\\scenario.chk"))
    del src
    new, added = patch(raw, args.humans)

    out = os.path.abspath(args.out)
    tmpdir = tempfile.mkdtemp(prefix="eudext_multi_")
    try:
        work = os.path.join(tmpdir, "map.scx")
        shutil.copyfile(os.path.abspath(args.src), work)
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
        shutil.copyfile(work, out)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    print("만듦: %s (사람 P1~P%d, 시작 위치 %d개 추가)" % (out, args.humans, added))
    return 0


if __name__ == "__main__":
    sys.exit(main())
