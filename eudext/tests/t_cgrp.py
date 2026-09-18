"""`cgrp` 시험 — 합성 CGRP 파일 파싱, 점 추리기·층 굽기(참조 구현 차등), CGRPPainter 진행(에뮬레이터) (DESIGN 4.20, R4a B).

- 파일: 시험이 `struct` 로 직접 만든 바이트(가이드북 B.1 형식: 헤더 16B + 칸당 dword)를 `CGRP.from_bytes`/`load` 로 읽는다.
  길이·크기 오류, 없는 파일, 경로 찾기(절대·base·작업 폴더·EUDEXT_CGRP_DIR), 되쓰기(to_bytes).
  **실제 CS_Photo 출력은 이 환경에 없다** — 인게임 목록 F21-7(사용자에게 파일을 받아 확인).
- 층: 따로 짠 참조 구현(`ref_layers` — 가이드북 예제 29-4~29-10 처럼 분류마다 칸을 다시 훑는다)과 무작위 칸 400벌 × 방식 대조.
  CGRPLayer 바이트(Db), 입력 검사.
- CGRPPainter: 참조 타임라인(`ref_ticks`)과 틱마다 만든 점(생성 순간 로케이션·높이·스프라이트 이미지·화면 출력·투사 방식·
  속도)을 비교. 층 전환 대기(delay)·per_frame·빈 칸 없음(skip·retry)·start 다시·stop·빈 그림·변수 원점/소유자·CP 보존·
  게임 메모리 쓰기 집합 ⊆ 허용 집합.
- epScript 예제 `examples/cgrp_example` 번역·에뮬레이션·euddraft 빌드.

python tests/t_cgrp.py
비용 표: python tools/cost.py tests/t_cgrp.py [--append --bytes]
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import random  # noqa: E402
import shutil  # noqa: E402
import struct  # noqa: E402

from eudplib import (  # noqa: E402
    P3,
    P8,
    CompressPayload,
    Db,
    EUDVariable,
    LoadMap,
    f_getcurpl,
    f_setcurpl,
)

from eudext import _compat, bullet, cgrp  # noqa: E402
from eudext import datpatch as dat  # noqa: E402
from eudext.bullet import BulletKind, CtrigKind  # noqa: E402
from eudext.cgrp import CGRP, CGRPLayer, CGRPPainter  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import BASE_MAP, emu, scmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
LOC = 26
MRGN = 0x58DC60
NEXT = 0x628438
FIRST_UNIT = 0x628430
CP_ADDR = 0x6509B0
UNIT_TABLE = 0x59CCA8
EX = os.path.join(_common.PKG, "examples")
TMP = os.path.join(_common.WORK, "t_cgrp_files")

bullet.setup(loc=LOC)

CAT = ("red", "green", "blue", "emp", "indigo", "box", "fill", "red_stack", "black_stack")
CODE = {"red": 0, "green": 13, "blue": 16, "emp": 8, "indigo": 12, "box": 15, "red_stack": 6, "black_stack": 10}
BIT = {"red": 1, "green": 2, "blue": 4, "emp": 16, "indigo": 32, "box": 64}


def pack_file(count, w, h, dw, dh, cells):
    """가이드북 B.1 형식 그대로 바이트를 만든다 (구현과 따로)."""
    out = bytearray()
    out += count.to_bytes(4, "little") + w.to_bytes(4, "little") + h.to_bytes(4, "little")
    out += dw.to_bytes(2, "little") + dh.to_bytes(2, "little")
    for v in cells:
        out += v.to_bytes(4, "little")
    return bytes(out)


def rand_cells(rng, w, h, density=0.6, images=(233, 210, 0, 998), heights=(0, 3, 9, 254, 255)):
    cells = []
    for _ in range(w * h):
        if rng.random() > density:
            cells.append(0 if rng.random() < 0.8 else rng.getrandbits(32) & ~(0x3FF << 14) | (rng.choice(images) << 14))
            continue
        low = rng.getrandbits(14)
        if rng.random() < 0.5:
            low &= ~0x3F00  # 명암 없는 칸을 섞는다
        if rng.random() < 0.3:
            low &= ~0x7F  # 색 비트 없는 칸 (Fill 만)
        cells.append(low | (rng.choice(images) << 14) | (rng.choice(heights) << 24))
    return cells


def ref_layers(w, h, dw, dh, cells, mode="stack", height=None, image="cell", color=None):
    """층 참조 구현: 분류마다 칸 전체를 행 우선으로 다시 훑는다(가이드북 예제의 이중 루프 방식)."""
    out = []
    for cat in CAT:
        groups = {}
        for row in range(h):
            for col in range(w):
                v = cells[row * w + col]
                img = ((v >> 14) & 1023) if image == "cell" else image
                ch = (v >> 24) & 0xFF
                hits = []
                if mode == "fill":
                    if cat == "fill" and v & 128:
                        hits.append((ch if height is None else height, 1))
                else:
                    if mode == "stack":
                        base = 5 if height is None else height
                    else:
                        base = ch + (0 if height is None else height)
                    if cat in BIT and v & BIT[cat]:
                        hits.append((base, 1))
                    elif cat == "fill" and v & 128 and not v & 127:
                        hits.append((base, 1))
                    elif cat == "red_stack" and (v >> 11) & 7:
                        hits.append((base + 1, (v >> 11) & 7))
                    elif cat == "black_stack" and mode == "stack" and (v >> 8) & 7:
                        hits.append(((5 if height is None else height) + 2, (v >> 8) & 7))
                for hh, n in hits:
                    key = (-1 if img is None else img, min(hh, 255))
                    groups.setdefault(key, []).extend([(col * dw, row * dh)] * n)
        for key in sorted(groups):
            img, hh = key
            code = color if mode == "fill" else CODE.get(cat)
            out.append((cat, code, None if img == -1 else img, hh, groups[key]))
    return out


def lay_tuple(lay):
    return (lay.name, lay.color, lay.image, lay.height, lay.points)


def effective(kind, lay):
    ctrig = isinstance(kind, CtrigKind)
    img = lay.image if lay.image is not None or not ctrig else kind.image
    col = lay.color if lay.color is not None or not ctrig else kind.color
    return img, col


def ref_ticks(kind, layers, per_frame, delay):
    """틱마다 만들 점 [(dx, dy, 높이, 이미지, 색)] 목록 (구현과 따로 짠 흐름)."""
    lays = [lay for lay in layers if lay.points]
    ticks = []
    i = p = wait = 0
    while i < len(lays):
        if wait:
            ticks.append([])
            wait -= 1
            continue
        budget = per_frame
        cur = []
        while True:
            lay = lays[i]
            img, col = effective(kind, lay)
            while p < len(lay.points) and budget:
                dx, dy = lay.points[p]
                cur.append((dx, dy, lay.height, img, col))
                p += 1
                budget -= 1
            if p < len(lay.points):
                break
            i += 1
            p = 0
            if i == len(lays):
                break
            if effective(kind, lays[i]) != (img, col):
                wait = delay
                break
            if not budget:
                break
        ticks.append(cur)
    return ticks


# =============================================================================================
# 파이썬 쪽: 파일·층
# =============================================================================================


def file_checks(ck):
    rng = random.Random(4201)
    os.makedirs(TMP, exist_ok=True)
    # 헤더·칸
    for j in range(60):
        w, h = rng.randrange(0, 9), rng.randrange(0, 9)
        dw, dh = rng.choice((0, 1, 3, 5, 0xFFFF)), rng.choice((0, 2, 3, 7))
        cells = [rng.getrandbits(32) for _ in range(w * h)]
        count = rng.getrandbits(32)
        data = pack_file(count, w, h, dw, dh, cells)
        cg = CGRP.from_bytes(data, path="x%d" % j)
        ck.eq("헤더 #%d" % j, (cg.count, cg.width, cg.height, cg.dot_w, cg.dot_h, cg.cells, cg.found),
              (count, w, h, dw, dh, cells, 1))
        ck.eq("되쓰기 #%d" % j, cg.to_bytes(), data)
        for y in range(h):
            for x in range(w):
                if cg.cell(x, y) != cells[y * w + x]:
                    ck.true("cell #%d (%d,%d)" % (j, x, y), False)
        ck.eq("크기 #%d" % j, (cg.pixel_width, cg.pixel_height), (w * dw, h * dh))
        ck.eq("fill·painted #%d" % j, (cg.fill_count, cg.painted_count),
              (sum(1 for v in cells if v & 128), sum(1 for v in cells if v & 0xFF)))
    # 예제 29-8 이 읽는 식: X 크기 = +12 워드, Y 크기 = +14 워드
    cg = CGRP.from_bytes(pack_file(5, 2, 1, 3, 7, [128, 0]))
    ck.eq("점 크기 워드 순서", (cg.dot_w, cg.dot_h), (3, 7))
    # 오류
    good = pack_file(1, 3, 2, 3, 3, [128] * 6)
    for label, data, msg in [
        ("빈 파일", b"", "헤더"),
        ("15B", good[:15], "헤더"),
        ("헤더만", good[:16], "크기"),
        ("한 칸 모자람", good[:-4], "크기"),
        ("1B 모자람", good[:-1], "크기"),
        ("1B 남음", good + b"\0", "크기"),
        ("한 칸 남음", good + b"\0" * 4, "크기"),
        ("너무 큼", pack_file(0, 0x10000, 0x10000, 3, 3, []), "너무 큽니다"),
        ("큰 W·H 곱", pack_file(0, 5000, 1000, 3, 3, []), "너무 큽니다"),
    ]:
        try:
            CGRP.from_bytes(data, path="bad")
        except EudextError as e:
            ck.true("오류 " + label, msg in str(e), str(e))
        else:
            ck.true("오류 " + label, False, "오류가 나지 않음")
    # load: 절대·base·작업 폴더·환경 변수·없음
    path = os.path.join(TMP, "a.cgrp")
    with open(path, "wb") as f:
        f.write(good)
    ck.eq("load 절대", CGRP.load(path).to_bytes(), good)
    ck.eq("load base", CGRP.load("a.cgrp", base=TMP).path, path)
    old = os.getcwd()
    os.chdir(TMP)
    try:
        ck.eq("load 작업 폴더", CGRP.load("a.cgrp").cells, [128] * 6)
        ck.eq("cgrp.load 함수판", cgrp.load("a.cgrp").width, 3)
    finally:
        os.chdir(old)
    env_old = os.environ.get("EUDEXT_CGRP_DIR")
    os.environ["EUDEXT_CGRP_DIR"] = TMP
    try:
        ck.eq("load 환경 변수", CGRP.load("a.cgrp", base=os.path.join(TMP, "없는 폴더")).path, path)
    finally:
        if env_old is None:
            del os.environ["EUDEXT_CGRP_DIR"]
        else:
            os.environ["EUDEXT_CGRP_DIR"] = env_old
    try:
        CGRP.load("없음.cgrp", base=TMP)
    except EudextError as e:
        ck.true("load 없음 오류", "찾지 못했습니다" in str(e) and TMP in str(e), str(e))
    else:
        ck.true("load 없음 오류", False)
    miss = CGRP.load("없음.cgrp", missing_ok=True, base=TMP)
    ck.eq("load missing_ok", (miss.found, miss.width, miss.height, miss.count, miss.cells, miss.layers()),
          (0, 0, 0, 0, [], []))
    ck.true("missing summary", "파일 없음" in miss.summary(), miss.summary())
    ck.raises("load 경로 형식", EudextError, lambda: CGRP.load(3))
    ck.raises("load 빈 경로", EudextError, lambda: CGRP.load(""))
    bad = os.path.join(TMP, "bad.cgrp")
    with open(bad, "wb") as f:
        f.write(good[:-2])
    ck.raises("load 깨진 파일", EudextError, lambda: CGRP.load(bad))
    # 요약·count 뜻
    cells = [128 | 1, 128, 2, 0, 8 | 128, 0]
    for count, meaning in ((3, "fill"), (4, "painted"), (6, "cells"), (7, None)):
        cg = CGRP.from_cells(3, 2, cells, count=count)
        ck.eq("count_meaning %d" % count, cg.count_meaning(), meaning)
    ck.eq("from_cells count 기본 = Fill 칸", CGRP.from_cells(3, 2, cells).count, 3)
    s = CGRP.from_bytes(pack_file(3, 3, 2, 3, 4, [128 | (233 << 14) | (5 << 24)] * 6), path="/x/y/p.cgrp").summary()
    ck.true("summary", all(t in s for t in ("p.cgrp", "3 x 2 칸", "점 3 x 4 px", "헤더 점 수 3 (뜻 모름)", "Fill 6",
                                            "이미지 233", "높이 5")) and "{" not in s and "}" not in s, s)
    ck.eq("white_points", CGRP.from_cells(2, 2, [8 | (7 << 24), 0, 1, 8], dot_w=3, dot_h=5).white_points(),
          [(0, 0, 7), (3, 5, 0)])
    ck.true("repr 안내", "const" in repr(cg), repr(cg))
    # from_cells·from_rows 검사
    for label, fn in [
        ("칸 수", lambda: CGRP.from_cells(2, 2, [0, 0, 0])),
        ("칸 값 음수", lambda: CGRP.from_cells(1, 1, [-1])),
        ("칸 값 범위", lambda: CGRP.from_cells(1, 1, [1 << 32])),
        ("dot 범위", lambda: CGRP.from_cells(1, 1, [0], dot_w=0x10000)),
        ("width 실수", lambda: CGRP.from_cells(1.0, 1, [0])),
        ("rows 길이 다름", lambda: CGRP.from_rows(["R.", "R"])),
        ("rows 빈 목록", lambda: CGRP.from_rows([])),
        ("rows 모르는 글자", lambda: CGRP.from_rows(["Z"])),
        ("rows image 범위", lambda: CGRP.from_rows(["R"], image=1024)),
        ("cell 범위", lambda: CGRP.from_cells(1, 1, [0]).cell(1, 0)),
        ("epScript f_f_load", lambda: cgrp.f_f_load),
    ]:
        ck.raises(label, EudextError, fn)
    cg = CGRP.from_rows(["R.#", "rkW", "gbX"], dot=4, image=210, height=3)
    base = (210 << 14) | (3 << 24)
    ck.eq("from_rows 칸", cg.cells, [128 | 1 | base, 0, 128 | base, 128 | 1 | (1 << 11) | base,
                                    128 | 1 | (2 << 8) | base, 128 | 8 | base, 128 | 2 | (1 << 11) | base,
                                    128 | 4 | (1 << 11) | base, 128 | 64 | base])
    ck.eq("from_rows 비트가 있으면 그대로", CGRP.from_rows(["A"], legend={"A": 128 | (5 << 14) | (1 << 24)}).cells,
          [128 | (5 << 14) | (1 << 24)])
    for v in [rng.getrandbits(32) for _ in range(300)] + [0, M32]:
        ck.true("풀기 %08X" % v, (cgrp.black_level(v), cgrp.red_level(v), cgrp.cell_image(v), cgrp.cell_height(v)) ==
                ((v & 0x700) // 0x100, (v & 0x3800) // 0x800, (v & 0xFFC000) // 0x4000, v // 0x1000000), "")
    ck.true("f_ 별칭", all(getattr(cgrp, n) is getattr(cgrp, "f_" + n)
                          for n in ("black_level", "red_level", "cell_image", "cell_height", "load")), "")
    for n in cgrp.__all__:
        ck.true("__all__ " + n, hasattr(cgrp, n), "")


def layer_checks(ck):
    rng = random.Random(4202)
    n = 0
    for j in range(400):
        w, h = rng.randrange(1, 12), rng.randrange(1, 9)
        dw, dh = rng.choice((1, 3, 4)), rng.choice((1, 3, 6))
        cells = rand_cells(rng, w, h)
        cg = CGRP.from_cells(w, h, cells, dw, dh)
        opts = [dict(mode="stack"), dict(mode="stack", height=rng.randrange(256)), dict(mode="height"),
                dict(mode="height", height=rng.randrange(256)), dict(mode="fill"), dict(mode="fill", height=7),
                dict(mode="fill", color=13), dict(mode="stack", image=None), dict(mode="height", image=990),
                dict(mode="fill", image=None, color=0)]
        for o in opts:
            got = [lay_tuple(lay) for lay in cg.layers(**o)]
            want = ref_layers(w, h, dw, dh, cells, **o)
            if got != want:
                k = next((i for i, (g, w_) in enumerate(zip(got, want)) if g != w_), min(len(got), len(want)))
                ck.eq("층 #%d %r (층 %d 개 / 기대 %d 개, 처음 다른 층 %d)" % (j, o, len(got), len(want), k),
                      got[k:k + 1], want[k:k + 1])
            n += 1
    ck.true("층 = 참조 (%d 벌)" % n, True)
    # 흰색은 넣지 않는다, 색 비트가 여럿이면 층마다
    cg = CGRP.from_cells(3, 1, [8 | 128, 1 | 2 | 128, 128], dot_w=3)
    ck.eq("흰색 제외·여러 색", [(lay.name, lay.points) for lay in cg.layers()],
          [("red", [(3, 0)]), ("green", [(3, 0)]), ("fill", [(6, 0)])])
    # 높이 255 넘침 → 255
    cg = CGRP.from_cells(1, 1, [1 | (7 << 11) | (7 << 8) | (255 << 24)])
    ck.eq("높이 상한", [(lay.name, lay.height, lay.count) for lay in cg.layers(mode="stack", height=254)],
          [("red", 254, 1), ("red_stack", 255, 7), ("black_stack", 255, 7)])
    ck.eq("height 방식 상한", [(lay.name, lay.height) for lay in cg.layers(mode="height", height=10)],
          [("red", 255), ("red_stack", 255)])
    # 오류
    big = CGRP.from_cells(2, 1, [128, 128], dot_w=0x10000 - 1)
    ck.eq("65535px 경계 통과", big.layers()[0].points, [(0, 0), (65535, 0)])
    ok_img = CGRP.from_cells(2, 1, [128 | (999 << 14), 1023 << 14])
    ck.eq("칸 이미지 밖이어도 image 지정·빈 칸이면 통과", ([lay.image for lay in ok_img.layers(image=5)],
                                                 CGRP.from_cells(1, 1, [1023 << 14]).layers()), ([5], []))
    for label, fn in [
        ("mode", lambda: cg.layers(mode="x")),
        ("color stack", lambda: cg.layers(color=3)),
        ("height 범위", lambda: cg.layers(height=256)),
        ("image 범위", lambda: cg.layers(image=999)),
        ("칸 이미지 999", lambda: CGRP.from_cells(1, 1, [128 | (999 << 14)]).layers()),
        ("칸 이미지 1023 (명암만)", lambda: CGRP.from_cells(1, 1, [1 << 8 | (1023 << 14)]).layers()),
        ("65535px 넘음", lambda: CGRP.from_cells(3, 1, [128] * 3, dot_w=0x8000).layers()),
        ("세로 65535px 넘음", lambda: CGRP.from_cells(1, 3, [128] * 3, dot_h=0x8000).layers()),
        ("layer color", lambda: CGRPLayer("a", 256, None, 0, [])),
        ("layer image", lambda: CGRPLayer("a", None, 999, 0, [])),
        ("layer height", lambda: CGRPLayer("a", None, None, -1, [])),
        ("layer 점 형식", lambda: CGRPLayer("a", None, None, 0, [(1, 2, 3)])),
        ("layer 점 범위", lambda: CGRPLayer("a", None, None, 0, [(0x10000, 0)])),
        ("layer 펼친 목록 홀수", lambda: CGRPLayer("a", None, None, 0, [1, 2, 3])),
    ]:
        ck.raises(label, EudextError, fn)
    # 바이트·Db
    lay = CGRPLayer("x", 0, 233, 5, [(1, 2), (0xFFFF, 0x1234)])
    ck.eq("layer data", lay.data(), struct.pack("<HHHH", 1, 2, 0xFFFF, 0x1234))
    ck.true("layer db", isinstance(lay.db, Db) and lay.db.content == lay.data() and lay.db is lay.db, "")
    ck.eq("layer 펼친 목록", CGRPLayer("x", None, None, 0, [1, 2, 3, 4]).points, [(1, 2), (3, 4)])
    ck.eq("layer 목록 섞기", CGRPLayer("x", None, None, 0, [(1, 2), [3, 4]]).points, [(1, 2), (3, 4)])
    ck.true("layer repr", "점 2" in repr(lay), repr(lay))


KDOT = CtrigKind(unit=203, weapon=2, flingy=147, sprite=231, image=233, iscript=233, half_air=True)
KALT = CtrigKind(unit=205, weapon=5, flingy=150, sprite=250, image=240, iscript=1, color=9, y_offset=0)
KPLAIN = BulletKind(unit=206, weapon=30, flingy=174, recipe="minimal")
OWNER = EUDVariable()

_R = random.Random(4203)
CG_A = CGRP.from_cells(9, 7, rand_cells(_R, 9, 7, density=0.7, images=(233, 210), heights=(3, 9)), 3, 3)
CG_G = CGRP.from_cells(6, 5, rand_cells(_R, 6, 5, density=0.8, images=(233,), heights=(0, 1, 2, 250)), 4, 5)
LAY_F = [CGRPLayer("f1", None, None, 3, [(0, 0), (3, 0), (3, 0)]), CGRPLayer("f2", None, None, 4, [(6, 0)]),
         CGRPLayer("f3", 16, None, 4, [(9, 9), (0, 9)]), CGRPLayer("empty", 1, 233, 0, []),
         CGRPLayer("f4", 16, 233, 7, [(1, 1)]), CGRPLayer("f5", 16, 233, 8, [(2, 2)] * 5)]

PAINTERS = {
    "A": CGRPPainter(CG_A, KDOT, P8, per_frame=5, delay=2),
    "B": CGRPPainter(CG_A.layers(mode="height"), KDOT, OWNER, per_frame=1, delay=0, on_fail="retry"),
    "C": CGRPPainter(CG_G.layers(mode="fill", image=None), KPLAIN, P3, per_frame=4, delay=3),
    "D": CGRPPainter(CGRP.load("없음.cgrp", missing_ok=True), KDOT, P8),
    "E": CGRPPainter(CG_G.layers(mode="height", image=None), KALT, P8, per_frame=7, delay=1, sprite=300),
    "F": CGRPPainter(LAY_F, KDOT, P8, per_frame=3, delay=1),
    "G": CGRPPainter(CG_G, KALT, P8, per_frame=64, delay=5, on_fail="skip"),
}


def painter_checks(ck):
    ck.eq("painter 빈 층 버림", [lay.name for lay in PAINTERS["F"].layers], ["f1", "f2", "f3", "f4", "f5"])
    ck.eq("painter total", {k: p.total for k, p in PAINTERS.items()},
          {k: sum(len(lay.points) for lay in p.layers) for k, p in PAINTERS.items()})
    ck.eq("painter D 빈 그림", (PAINTERS["D"].total, PAINTERS["D"].layers), (0, []))
    # 층 전환 대기 자리 = (이미지, 색)이 바뀌는 곳 (None 은 CtrigKind 값)
    for k, p in PAINTERS.items():
        keys = [effective(p.kind, lay) for lay in p.layers]
        ck.eq("painter %s 대기 자리" % k, p._groups, [j for j in range(1, len(keys)) if keys[j] != keys[j - 1]])
    ck.eq("painter F 대기 자리 (f1·f2 같은 설정, f3 색 16)", PAINTERS["F"]._groups, [2])
    # 층 설정 액션
    for k, p in PAINTERS.items():
        for lay, acts in zip(p.layers, p._acts):
            img, col = effective(p.kind, lay)
            want = {}

            def put(field, idx, v):
                a, sh, mk = dat.field(*field).location(idx)
                want[a] = ((want.get(a, (0, 0))[0] & ~mk) | ((v << sh) & mk), want.get(a, (0, 0))[1] | mk)

            put(("weapons", "behavior"), p.kind.weapon, 7)
            put(("flingy", "topSpeed"), p.kind.flingy, 0)
            put(("units", "elevation"), p.kind.made_unit, lay.height)
            if img is not None:
                put(("sprites", "image"), p.sprite, img)
            if col is not None:
                put(("images", "drawingFunction"), img, col)
            got = {}
            for a in acts:
                f = a.fields
                addr = (0x58A364 + 4 * (f[6] * 12 + f[4])) & M32
                mk = (f[0] & M32) if f[11] == 0x4353 else M32
                ov, om = got.get(addr, (0, 0))
                got[addr] = ((ov & ~mk) | (f[5] & mk), om | mk)
            ck.eq("painter %s 층 %s 설정" % (k, lay.name), got, want)
    ck.eq("painter sprite 기본", (PAINTERS["A"].sprite, PAINTERS["C"].sprite, PAINTERS["E"].sprite), (231, None, 300))
    ck.true("painter repr", "const" in repr(PAINTERS["A"]), repr(PAINTERS["A"]))
    for label, fn in [
        ("source", lambda: CGRPPainter(5, KDOT, P8)),
        ("source 목록", lambda: CGRPPainter([1], KDOT, P8)),
        ("kind", lambda: CGRPPainter(CG_A, 5, P8)),
        ("weapon 없음", lambda: CGRPPainter(CG_A, BulletKind(weapon=None), P8)),
        ("flingy 없음", lambda: CGRPPainter(CG_A, BulletKind(flingy=None), P8)),
        ("owner", lambda: CGRPPainter(CG_A, KDOT, 14)),
        ("per_frame 0", lambda: CGRPPainter(CG_A, KDOT, P8, per_frame=0)),
        ("per_frame 4097", lambda: CGRPPainter(CG_A, KDOT, P8, per_frame=4097)),
        ("delay 음수", lambda: CGRPPainter(CG_A, KDOT, P8, delay=-1)),
        ("on_fail", lambda: CGRPPainter(CG_A, KDOT, P8, on_fail="stop")),
        ("sprite 범위", lambda: CGRPPainter(CG_A, KDOT, P8, sprite=517)),
        ("일반 종류 + 이미지 층", lambda: CGRPPainter(CG_A.layers(mode="fill"), KPLAIN, P8)),
        ("일반 종류 + 색 층", lambda: CGRPPainter(CG_A.layers(mode="fill", image=None, color=3), KPLAIN, P8)),
    ]:
        ck.raises("painter " + label, EudextError, fn)
    ck.eq("일반 종류 + sprite + 색 층", CGRPPainter(CG_A.layers(mode="fill", color=3), KPLAIN, P8, sprite=5).sprite, 5)


# =============================================================================================
# 에뮬레이터: painter 진행
# =============================================================================================


def build_cases(s):
    for k, p in PAINTERS.items():
        @s.case("start_" + k)
        def _(t, p=p):
            p.start(t.var("ox"), t.var("oy"))

        @s.case("tick_" + k)
        def _(t, p=p):
            p.tick()
            t.flag("done", p.done())
            t.flag("run", p.running())
            t.watch("drawn", p.drawn.getValueAddr())
            t.watch("dropped", p.dropped.getValueAddr())

    @s.case("start_A_const")
    def _(t):
        PAINTERS["A"].start(384, 1120)

    @s.case("stop_A")
    def _(t):
        PAINTERS["A"].stop()

    @s.case("owner")
    def _(t):
        OWNER << t.var("o")

    @s.case("cp_A")
    def _(t):
        f_setcurpl(t.var("c"))
        PAINTERS["A"].tick()
        t.out("gc", f_getcurpl())
        t.watch("cpm", CP_ADDR)

    def bad(name, fn, msg=None):
        s.case("err_" + name, expect_build_error=EudextError, expect_message=msg)(lambda t: fn(t))

    bad("start_x", lambda t: PAINTERS["A"].start(1.5, 0), "ox")
    bad("start_y", lambda t: PAINTERS["A"].start(0, True), "oy")


class Rec:
    """생성 순간의 전역 dat·로케이션을 기록하는 CreateUnit 처리기."""

    def __init__(self, m, addrs):
        self.m = m
        self.addrs = sorted(addrs)
        self.log = []
        orig = m.act_handlers[scmodel.ACT_CREATE_UNIT]

        def rec(mm, fields):
            la = MRGN + 20 * (fields[0] - 1)
            self.log.append((tuple(mm.dw(la + 4 * i) for i in range(4)), {a: mm.dw(a) for a in self.addrs}, fields[4]))
            orig(mm, fields)

        m.act_handlers[scmodel.ACT_CREATE_UNIT] = rec


def byte_at(snap, a):
    return (snap[a & ~3] >> (8 * (a & 3))) & 0xFF


def watch_addrs(p):
    k = p.kind
    out = {0x656670 + k.weapon & ~3, 0x6C9EF8 + 4 * k.flingy, 0x663150 + k.made_unit & ~3}
    if p.sprite is not None:
        out.add(dat.field("sprites", "image").location(p.sprite)[0])
    for lay in p.layers:
        img, _c = effective(k, lay)
        if img is not None:
            out.add(0x669E28 + img & ~3)
    return out


def dot_of(p, snap):
    """생성 순간 값 → (높이, 스프라이트 이미지 또는 None, 화면 출력 또는 None, 투사 방식, 최고속도)."""
    k = p.kind
    h = byte_at(snap, 0x663150 + k.made_unit)
    img = None
    if p.sprite is not None:
        a, sh, mk = dat.field("sprites", "image").location(p.sprite)
        img = (snap[a] & mk) >> sh
    col = None
    if img is not None and ((0x669E28 + img) & ~3) in snap:
        col = byte_at(snap, 0x669E28 + img)
    return h, img, col, byte_at(snap, 0x656670 + k.weapon), snap[0x6C9EF8 + 4 * k.flingy]


def run_painter(s, rec, key, ox, oy, owner=7, label=None, expire=True, max_ticks=400):
    """start → 끝날 때까지 tick. 반환: (틱별 [(x, y, h, img, color)], 틱별 결과)."""
    p = PAINTERS[key]
    m = s.machine
    model = scmodel.unit_model(m)
    label = label or key
    s.run("start_" + key, {"ox": ox, "oy": oy})
    ticks, results = [], []
    for _ in range(max_ticks):
        n0 = len(rec.log)
        r = s.run("tick_" + key, {})
        results.append(r)
        cur = []
        for rect, snap, player in rec.log[n0:]:
            h, img, col, beh, top = dot_of(p, snap)
            cur.append(((rect[0] - ox) & M32, (rect[1] - oy - p.kind.y_offset) & M32, h, img, col, beh, top, player,
                        rect[0] == rect[2] and rect[1] == rect[3]))
        ticks.append(cur)
        if expire:  # 탄막 유닛은 6프레임 뒤 사라진다 — 모델에서는 매 틱 지운다
            for c in model.created:
                for i in c.indices:
                    model.kill(i)
            model.process_deaths()
            model.clear_log()
        if r.error or r.values.get("done"):
            break
    return ticks, results


def compare_run(s, key, ticks, results, owner, label):
    p = PAINTERS[key]
    case = "tick_" + key
    want = ref_ticks(p.kind, p.layers, p.per_frame, p.delay)
    errs = [r.error for r in results if r.error]
    s.expect_true(case, not errs, label + " / 실행", repr(errs[:2]))
    got_plain = [[(dx, dy, h, img, col) for dx, dy, h, img, col, _b, _t, _o, _pt in tick] for tick in ticks]
    want_cmp = [[(dx, dy, h, img if p.sprite is not None else None, col if img is not None else None)
                 for dx, dy, h, img, col in tick] for tick in want]
    s.expect_true(case, got_plain == want_cmp, label + " / 틱별 점 = 참조",
                  "틱 %d / %d, 처음 다른 틱 %s" % (len(got_plain), len(want_cmp),
                                              next((i for i, (a, b) in enumerate(zip(got_plain, want_cmp)) if a != b),
                                                   None)))
    others = [(b, t_, o, pt) for tick in ticks for _dx, _dy, _h, _i, _c, b, t_, o, pt in tick]
    s.expect_true(case, all(x == (7, 0, owner, True) for x in others), label + " / 투사 방식 7·속도 0·소유자·한 점",
                  repr(set(others)))
    last = results[-1].values if results else {}
    s.expect_true(case, (last.get("done"), last.get("run"), last.get("drawn"), last.get("dropped")) ==
                  (1, 0, p.total, 0), label + " / 끝 상태", repr(last))
    s.expect_true(case, all(r.values.get("done") == 0 and r.values.get("run") == 1 for r in results[:-1]),
                  label + " / 중간 상태", "")


def emu_checks(s, rng):
    m = s.machine
    model = scmodel.unit_model(m)
    addrs = set()
    for p in PAINTERS.values():
        addrs |= watch_addrs(p)
    rec = Rec(m, addrs)
    lo, hi = m.base, m.limit_addr

    def ext():
        return {k: v for k, v in m.mem.items() if not lo <= k < hi}

    for key, owner in (("A", 7), ("C", 2), ("E", 7), ("F", 7), ("G", 7)):
        for ox, oy in ((384, 1120), (0, 0), (4000, 3000), (M32 - 2, 0x7FFFFFFF)):
            s.reset()
            model.clear_log()
            rec.log.clear()
            before = ext()
            ticks, results = run_painter(s, rec, key, ox, oy)
            compare_run(s, key, ticks, results, owner, "%s 원점 (%d,%d)" % (key, ox, oy))
            after = ext()
            changed = {a for a in set(before) | set(after) if before.get(a, 0) != after.get(a, 0)}
            allowed = watch_addrs(PAINTERS[key]) | {MRGN + 20 * (LOC - 1) + 4 * i for i in range(4)} | \
                {NEXT, FIRST_UNIT} | {UNIT_TABLE + a for a in range(0, 336 * 1700, 4)}
            s.expect_true("tick_" + key, changed <= allowed, "%s 쓰기 칸" % key,
                          ", ".join("0x%X" % a for a in sorted(changed - allowed)))
            # 끝난 뒤 tick 은 아무것도 안 만든다
            n0 = len(rec.log)
            r = s.run("tick_" + key, {})
            s.expect_true("tick_" + key, len(rec.log) == n0 and r.values.get("done") == 1, "%s 끝난 뒤 tick" % key, "")
    # B: 변수 소유자, per_frame 1, delay 0, retry
    for o in (0, 5, 11):
        s.reset()
        model.clear_log()
        rec.log.clear()
        s.run("owner", {"o": o})
        ticks, results = run_painter(s, rec, "B", 100, 200, max_ticks=2000)
        compare_run(s, "B", ticks, results, o, "B 소유자 %d" % o)
    # D: 빈 그림 — start 뒤 곧 done, tick 은 아무것도 안 함
    s.reset()
    rec.log.clear()
    r0 = s.run("tick_D", {})
    s.run("start_D", {"ox": 1, "oy": 2})
    r1 = s.run("tick_D", {})
    s.expect_true("tick_D", (r0.values.get("done"), r0.values.get("run"), r1.values.get("done"), len(rec.log)) ==
                  (0, 0, 1, 0), "빈 그림", "%r %r" % (r0.values, r1.values))
    # 빈 칸 없음: skip = 버리고 진행, retry = 그 점에서 기다림
    s.reset()
    model.clear_log()
    model.fill()
    rec.log.clear()
    ticks, results = run_painter(s, rec, "A", 10, 20, expire=False)
    pa = PAINTERS["A"]
    last = results[-1].values
    # 본문이 빈 칸 검사에서 먼저 실패하므로 CreateUnit 기록도 없다
    s.expect_true("tick_A", (last.get("done"), last.get("drawn"), last.get("dropped")) == (1, 0, pa.total) and
                  model.created == [] and rec.log == [], "skip: 칸 없음 → 모두 버림",
                  "%r 기록 %d" % (last, len(model.created)))
    s.expect_true("tick_A", len(ticks) == len(ref_ticks(pa.kind, pa.layers, pa.per_frame, pa.delay)),
                  "skip: 칸 없음 → 틱 수(대기 포함)는 같음", "%d" % len(ticks))
    s.reset()
    model.clear_log()
    model.fill()
    s.run("owner", {"o": 4})
    s.run("start_B", {"ox": 0, "oy": 0})
    stuck = [s.run("tick_B", {}).values for _ in range(5)]
    s.expect_true("tick_B", [(v["drawn"], v["dropped"], v["done"], v["run"]) for v in stuck] ==
                  [(0, i + 1, 0, 1) for i in range(5)], "retry: 칸 없음 → 제자리", repr(stuck))
    model.set_free(list(range(1700)))
    rec.log.clear()
    model.clear_log()
    pb = PAINTERS["B"]
    n = 0
    for _ in range(pb.total * 2 + 50):
        v = s.run("tick_B", {}).values
        for c in model.created:
            for i in c.indices:
                model.kill(i)
        model.process_deaths()
        model.clear_log()
        n += 1
        if v["done"]:
            break
    got = [((rect[0]) & M32, (rect[1] + 2) & M32) for rect, _snap, _o in rec.log]
    want = [(dx, dy) for tick in ref_ticks(pb.kind, pb.layers, pb.per_frame, pb.delay) for dx, dy, *_ in tick]
    s.expect_true("tick_B", v["done"] == 1 and v["drawn"] == pb.total and v["dropped"] == 5 and got == want,
                  "retry: 칸이 생기면 첫 점부터 이어서", "%r 점 %d/%d" % (v, len(got), len(want)))
    # start 다시 / stop
    s.reset()
    model.clear_log()
    rec.log.clear()
    s.run("start_A", {"ox": 0, "oy": 0})
    for _ in range(3):
        s.run("tick_A", {})
    first = len(rec.log)
    s.run("start_A_const", {})
    rec.log.clear()
    ticks, results = run_painter(s, rec, "A", 384, 1120)
    s.expect_true("tick_A", first > 0, "start 다시 전 점", str(first))
    compare_run(s, "A", ticks, results, 7, "A start 다시")
    s.reset()
    rec.log.clear()
    s.run("start_A", {"ox": 0, "oy": 0})
    s.run("tick_A", {})
    s.run("stop_A", {})
    n0 = len(rec.log)
    vals = [s.run("tick_A", {}).values for _ in range(4)]
    s.expect_true("tick_A", len(rec.log) == n0 and all(v["done"] == 0 and v["run"] == 0 for v in vals),
                  "stop 뒤 멈춤", repr(vals[-1]))
    # CP 보존
    for cpv in (0, 1, 7, 0x12345, M32):
        s.reset()
        s.run("start_A", {"ox": 0, "oy": 0})
        for j in range(4):
            r = s.run("cp_A", {"c": cpv})
            s.expect_true("cp_A", r.values.get("cpm") == cpv and r.values.get("gc") == cpv and not r.error,
                          "CP 0x%X 틱 %d" % (cpv, j), "%r %s" % (r.values, r.error))


# =============================================================================================
# epScript 예제
# =============================================================================================


def eps_checks(ck):
    src = open(os.path.join(EX, "cgrp_example.eps"), encoding="utf-8").read()
    out, nerr = _compat.eps_compile("cgrp_example.eps", src)
    ck.eq("eps errors", nerr, 0)
    for needle in ("cgrp.CGRP.from_cells(3, 2, FlattenList([", "cg.layers(mode=\"height\")",
                   "cgrp.CGRPPainter(layers, kind, P8, per_frame=2, delay=1, on_fail=\"retry\")",
                   "cgrp.CGRPLayer(\"mine\", 16, 233, 12, FlattenList([0, 0, 8, 0, 8, 0]))",
                   "painter.start(1000, 1000)", "painter.tick()", "painter.done()"):
        ck.true("eps: " + needle, out is not None and needle in out, "")
    bad = _compat.eps_compile("bad.eps", "import eudext.cgrp as cgrp;\nconst a = cgrp.f_load(\"x\");")[0]
    ck.true("eps: cgrp.f_load → f_f_load", bad is not None and "cgrp.f_f_load(" in bad, "")


def _load_eps(name, work_name):
    from eudext.tools import build

    work = os.path.join(_common.WORK, work_name)
    os.makedirs(work, exist_ok=True)
    shutil.copy2(os.path.join(EX, name), os.path.join(work, name))
    LoadMap(BASE_MAP)
    CompressPayload(True)
    return build._load_plugin(os.path.join(work, name), {})


def eps_emulate(ck):
    mod = _load_eps("cgrp_example.eps", "t_cgrp_eps")
    prog = emu.Program(mod.afterTriggerExec)
    names = ("frame", "finished", "finished2", "drawn", "dropped", "drawn2")
    for n in names:
        prog.watch(n, getattr(mod, n))
    m = prog.build()
    scmodel.install(m, units={})
    model = scmodel.unit_model(m)
    for _ in range(40):
        m.cycle()
    got = {n: m.var(n) for n in names}
    print("  epScript 예제 에뮬레이션: %r" % got)
    ck.eq("eps 예제 값", got, {"frame": 40, "finished": 1, "finished2": 1, "drawn": 5, "dropped": 0, "drawn2": 3})
    ck.eq("eps 예제 total", (mod.painter.total, mod.painter2.total), (5, 3))
    dots = [c for c in model.created if c.ok]
    ck.eq("eps 예제 만든 점", [(c.unit, c.player) for c in dots], [(203, 7)] * 8)
    # (0,0) 빨강 h3 · (0,5) Fill h3 · (8,0) 초록 h9 · (4,5) 빨강 h9 · (4,5) 적색 명암 h10 — 원점 (1000,1000), y − 2
    pos = sorted(model.pos(i) for c in dots for i in c.indices)
    ck.eq("eps 예제 위치", pos, sorted([(1000, 998), (1000, 1003), (1008, 998), (1004, 1003), (1004, 1003),
                                     (1200, 998), (1208, 998), (1208, 998)]))
    ck.eq("eps 예제 흉내 못 낸 것", [k for k in m.unknown if k != ("act", 9)], [])


def eps_build(ck):
    from eudext.tools import build

    if not os.path.isfile(build.EUDDRAFT):
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)
        return
    name = "cgrp_example"
    work = os.path.join(_common.WORK, "t_cgrp_build_" + name)
    eds, out_map = build.prepare_eds(os.path.join(EX, name + ".eds"), work)
    r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(work, name + ".log"))
    print("  " + r.summary())
    ck.true("euddraft " + name, r.ok, r.log[-2000:])
    ck.true("eps compiled " + name, '[epScript] Compiling "%s.eps"' % name in r.log, "")


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

COST_MEMORY = {"units": {}}
_CG1 = CGRP.from_cells(4, 1, [129, 129, 129, 129 | 2 << 14])
_P1 = CGRPPainter(_CG1.layers(image=None), KDOT, P8, per_frame=1, delay=2)
_P8 = CGRPPainter(CGRP.from_cells(8, 1, [129] * 8).layers(image=None), KDOT, P8, per_frame=8, delay=2)
_PW = CGRPPainter(_CG1, KDOT, P8, per_frame=4, delay=100)
_PX = CGRPPainter(_CG1, KDOT, P8, per_frame=4)


def _start(p):
    return lambda t: p.start(384, 1120)


def _start_wait(t):
    _PW.start(384, 1120)
    _PW.tick()  # 첫 층 다음 층으로 넘어가며 대기


COST_CASES = [
    CostCase("CGRPPainter.tick (점 1개)", lambda t: _P1.tick(), funcs=[_P1._tick_func(), bullet._body(
        bullet._Key("own", "const", "ctrig", -2, 6, False, False, LOC, None))], setup=_start(_P1),
        target={"call": 3}, note="per_frame 1, 층 1개. 본문 = tick 본문 + perma 본문(공유)"),
    CostCase("CGRPPainter.tick (점 8개)", lambda t: _P8.tick(), funcs=[_P8._tick_func()], setup=_start(_P8),
             target={"call": 3}, note="per_frame 8 — 실행 ÷ 8 = 점당"),
    CostCase("CGRPPainter.tick (쉬는 프레임)", lambda t: _PW.tick(), funcs=[_PW._tick_func()], setup=_start_wait,
             note="층 전환 대기 중"),
    CostCase("CGRPPainter.tick (멈춤)", lambda t: _PX.tick(), funcs=[_PX._tick_func()], note="start 전"),
    CostCase("CGRPPainter.start (변수 원점)", lambda t: _PX.start(t.var("x"), t.var("y")), {"x": 1, "y": 2}),
]


# =============================================================================================


def main():
    ck = Checker("t_cgrp (python)")
    file_checks(ck)
    layer_checks(ck)
    painter_checks(ck)

    s = Suite("t_cgrp", memory={"units": {}})
    build_cases(s)
    s.build()
    emu_checks(s, random.Random(4204))
    ok1 = s.report()

    cke = Checker("t_cgrp (epScript)")
    eps_checks(cke)
    eps_emulate(cke)
    eps_build(cke)
    finish(ok1, ck.report(), cke.report())


if __name__ == "__main__":
    main()
