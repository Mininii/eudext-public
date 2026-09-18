"""CGRP — CS_Photo.exe 가 만드는 점 그림 표를 읽어 영구 스프라이트로 찍는다 (DESIGN 4.20, R4a B, CtrigAsm 29장).

CGRP 는 이미지 파일이 아니라 **래스터 점 표**다(가이드북 8321~8345, R4a B.1):

| 위치 | 크기 | 내용 |
|---|---|---|
| +0 | 4 | 전체 점 수 (뜻 미확인 — `count_meaning()`) |
| +4 | 4 | 가로 칸 수 W |
| +8 | 4 | 세로 칸 수 H |
| +12 | 2 | 점 가로 크기(px, 기본 3) — 예제 29-8 이 아래 워드를 X 로 읽는다 |
| +14 | 2 | 점 세로 크기(px) |
| +16 | 4·W·H | 칸마다 dword, 행 우선(빈 칸 포함) |

칸 dword: 비트 0 Red(화면 출력 0) · 1 Green(13) · 2 Blue(16) · 3 White(17, 42틱 안에 다시 찍어야 함) · 4 EMP(8) ·
5 Indigo(12) · 6 Box(15) · 7 Fill(점을 찍는 칸) · 8~10 흑색 명암 0~7(10) · 11~13 적색 명암 0~7(6) · 14~23 이미지 번호 ·
24~31 높이.

원본(CtrigAsm 예제 29-4~29-10)은 파일을 통째로 싣고 **모든 칸**을 런타임에 읽었다. 여기서는 컴파일 시점에 파일을 풀어
**그릴 점만** 층(같은 색·이미지·높이)별 `Db` 로 굽고, `CGRPPainter.tick()` 이 프레임마다 N 점씩 `bullet.perma_sprite` 와
같은 본문을 부른다(R4a B.4). 전역 dat(이미지 화면 출력·스프라이트 이미지)가 바뀌는 층 사이에는 프레임을 쉰다(예제 29-6 Delay).

    from eudext import bullet, cgrp
    k = bullet.CtrigKind(unit=203, unit_flingy=74, unit_sprite=229, half_air=True,
                         weapon=2, flingy=147, sprite=231, image=233, iscript=233)
    k.install()
    cg = cgrp.CGRP.load("29-6_out.cgrp")               # 컴파일 시점 (euddraft 작업 폴더 기준 상대 경로)
    painter = cgrp.CGRPPainter(cg.layers(mode="stack", height=5), k, P8, per_frame=64, delay=4)
    painter.start(384, 1120)                           # 원점 (왼쪽 위 점의 좌표)
    painter.tick()                                     # 매 프레임 (한 곳에서)
    if EUDIf()(painter.done()): …

epScript:

    import eudext.bullet as bullet;
    import eudext.cgrp as cgrp;
    const k = bullet.CtrigKind(unit=203, weapon=2, flingy=147, sprite=231, image=233, iscript=233, half_air=True);
    const cg = cgrp.CGRP.load("my.cgrp");              // 클래스 메서드는 이름이 바뀌지 않는다 (cgrp.load(…) 도 됨)
    const painter = cgrp.CGRPPainter(cg.layers(), k, P8, per_frame=32);
    function afterTriggerExec() { painter.tick(); if (painter.done()) { … } }

주의
- 형식은 가이드북 설명과 예제 코드만 근거다 — **실제 CS_Photo 출력으로 확인하기 전**이다(인게임 목록 F21-7).
  헤더 +0 의 "전체 점 수" 가 무엇을 세는지 모른다(`count_meaning()` 이 후보와 맞춰 본다).
- 흰색(비트 3) 점은 층에 넣지 않는다(영구 스프라이트로 두면 42틱 뒤 튕김, GB 8466). `white_points()` 로 따로 받아
  `bullet.unit_sprite(…, track=False)`·`scan_sprite` 로 매 프레임 갱신하거나 흰 배경을 깐다(예제 29-6·29-7).
- 가이드북: CGRP 는 **UnlimiterX 필수**(총알 스프라이트 한도, GB 8314). 점 1개 = 탄막 유닛 1개가 6프레임 동안 유닛 칸을
  차지한다 → `per_frame` 이 크면 칸이 모자라 점이 빠진다(`dropped`). 시야 안 총알 약 4096 을 넘으면 튕긴다 → 소유자는
  컴퓨터, 시야를 끄고 그린다(GB 8605~8640).
- 로컬: 공유 안전(모든 클라이언트에서 같은 상태를 쓴다). CP: 바꾸지 않음.

출처: CtrigAsm 가이드북 29장(`reference/MapSource/Library/Ctrig Assembler v5.4 Guide Book.txt:8315~8642`, 예제
18217~18620), R4a B. CS_Photo.exe 와 실제 .cgrp 파일은 이 저장소·Ubuntu 환경에 없다(합성 파일로 시험). DPS 이식판(a7aad90)에는
CGRP 코드가 없다(새로 작성).
"""

import os
import struct

from eudplib import (
    EPD,
    Db,
    DoActions,
    EUDBreak,
    EUDElse,
    EUDEndIf,
    EUDEndSwitch,
    EUDEndWhile,
    EUDFunc,
    EUDIf,
    EUDSwitch,
    EUDSwitchCase,
    EUDVariable,
    EUDWhile,
    RawTrigger,
    SeqCompute,
    SetTo,
    f_wread_epd,
    unProxy,
)

from eudext import bullet
from eudext import datpatch as dat
from eudext.errors import fail

__all__ = [
    "BLUE",
    "BOX",
    "CGRP",
    "CGRPLayer",
    "CGRPPainter",
    "COLOR_CODES",
    "EMP",
    "FILL",
    "GREEN",
    "HEADER_SIZE",
    "INDIGO",
    "LAYER_ORDER",
    "RED",
    "WHITE",
    "black_level",
    "cell_height",
    "cell_image",
    "f_black_level",
    "f_cell_height",
    "f_cell_image",
    "f_load",
    "f_red_level",
    "load",
    "red_level",
]

M32 = 0xFFFFFFFF
HEADER_SIZE = 16
RED, GREEN, BLUE, WHITE, EMP, INDIGO, BOX, FILL = 1, 2, 4, 8, 16, 32, 64, 128
COLOR_BITS = RED | GREEN | BLUE | WHITE | EMP | INDIGO | BOX
# 비트 → 이미지 화면 출력(drawing function) 번호 (GB 8328~8337)
COLOR_CODES = {RED: 0, GREEN: 13, BLUE: 16, WHITE: 17, EMP: 8, INDIGO: 12, BOX: 15}
RED_STACK_CODE = 6
BLACK_STACK_CODE = 10
# 층 순서 (가이드북: 흑색 > 적색 > 기본색 순으로 높이. 예제 29-6 은 R, G, B, T(적색), K(흑색) 순으로 찍는다)
_BASE = (("red", RED), ("green", GREEN), ("blue", BLUE), ("emp", EMP), ("indigo", INDIGO), ("box", BOX))
LAYER_ORDER = tuple(n for n, _b in _BASE) + ("fill", "red_stack", "black_stack")
MAX_CELLS = 1 << 22  # 파일 16MB
_MODES = ("stack", "height", "fill")
_IMAGE_LAST = dat.field("images", "iscript").last
_SPRITE_LAST = dat.field("sprites", "image").last


def __getattr__(name):
    if name.startswith("f_f_"):
        fail("cgrp.%s: epScript 에서는 `cgrp.%s(…)` 로 부르세요 (번역이 이름 앞에 f_ 를 붙입니다)", name, name[4:])
    raise AttributeError("module 'eudext.cgrp' has no attribute %r" % name)


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _const(x, fname, what, lo, hi):
    v = unProxy(x)
    if not _int(v):
        fail("%s: %s 는 정수 상수여야 합니다 (%r)", fname, what, x)
    if not lo <= v <= hi:
        fail("%s: %s %d 가 %d ~ %d 밖입니다", fname, what, v, lo, hi)
    return v


# =============================================================================================
# 칸 값 풀기
# =============================================================================================


def f_black_level(v):
    """칸 값의 흑색 명암 단계(비트 8~10, 0~7).

    인자: v(칸 dword, 파이썬 정수)
    반환: int
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const b = cgrp.black_level(v);` (컴파일 시점 값)
    출처: 가이드북 8338 (Black Stack (0~7)*256)
    """
    return (v >> 8) & 7


def f_red_level(v):
    """칸 값의 적색 명암 단계(비트 11~13, 0~7 — 가이드북: 실제로는 3단계까지).

    인자: v(칸 dword)
    반환: int
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const r = cgrp.red_level(v);`
    출처: 가이드북 8339
    """
    return (v >> 11) & 7


def f_cell_image(v):
    """칸 값의 이미지 번호(비트 14~23, 10비트).

    인자: v(칸 dword)
    반환: int
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const i = cgrp.cell_image(v);`
    출처: 가이드북 8340
    """
    return (v >> 14) & 0x3FF


def f_cell_height(v):
    """칸 값의 높이(비트 24~31).

    인자: v(칸 dword)
    반환: int
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const h = cgrp.cell_height(v);`
    출처: 가이드북 8342, 예제 29-5 `CReadX(…, {0xFF000000, 0xFF}, 1/16777216)`
    """
    return (v >> 24) & 0xFF


black_level = f_black_level
red_level = f_red_level
cell_image = f_cell_image
cell_height = f_cell_height


# =============================================================================================
# 파일
# =============================================================================================


class CGRP:
    """CGRP 파일 한 개(컴파일 시점). `load`·`from_bytes`·`from_cells`·`from_rows` 로 만든다.

    속성: path, found(1 = 파일을 읽음, 0 = `missing_ok` 로 만든 빈 그림), count(헤더 +0), width, height(칸 수),
          dot_w, dot_h(점 크기 px), cells(행 우선 dword 목록), fill_count, painted_count(Fill 또는 색 비트가 있는 칸),
          pixel_width, pixel_height
    메서드: `cell(x, y)`, `points(select, mask)`, `layers(mode, height, image, color)`, `white_points()`,
            `to_bytes()`, `count_meaning()`
    비용: 없음(컴파일 시점 객체). 층의 `Db` 가 점 1개당 4B
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const cg = cgrp.CGRP.load("a.cgrp");` (var 가 아니라 const)
    출처: 가이드북 8321~8345, 예제 29-8(헤더 읽기), R4a B.1·B.4
    """

    __slots__ = ("path", "found", "count", "width", "height", "dot_w", "dot_h", "cells")

    def __init__(self, width, height, cells, dot_w=3, dot_h=3, count=None, path=None, found=1):
        fname = "cgrp.CGRP"
        self.width = _const(width, fname, "width", 0, M32)
        self.height = _const(height, fname, "height", 0, M32)
        if self.width * self.height > MAX_CELLS:
            fail("%s: 칸 수 %d × %d 가 너무 큽니다 (최대 %d)", fname, self.width, self.height, MAX_CELLS)
        self.dot_w = _const(dot_w, fname, "dot_w", 0, 0xFFFF)
        self.dot_h = _const(dot_h, fname, "dot_h", 0, 0xFFFF)
        cells = list(unProxy(cells))
        if len(cells) != self.width * self.height:
            fail("%s: 칸 값이 %d 개입니다 (W×H = %d)", fname, len(cells), self.width * self.height)
        self.cells = [_const(v, fname, "칸 값", 0, M32) for v in cells]
        self.count = self.fill_count if count is None else _const(count, fname, "count", 0, M32)
        self.path = path
        self.found = found

    # --- 만들기 ---
    @classmethod
    def from_bytes(cls, data, path=None):
        """바이트열(파일 내용)을 푼다.

        인자: data(bytes), path(표시용 이름)
        반환: CGRP
        의미: 길이 < 16, 길이 ≠ 16 + 4·W·H, 칸 수 > 2²² 이면 오류(EudextError, 한국어 메시지).
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다(파일은 `load`)
        출처: 가이드북 8321~8345
        """
        name = path or "<bytes>"
        data = bytes(data)
        if len(data) < HEADER_SIZE:
            fail("cgrp: %s 는 CGRP 가 아닙니다 — 길이 %d B (헤더 16B 보다 짧음)", name, len(data))
        count, w, h, dw, dh = struct.unpack_from("<IIIHH", data, 0)
        if w * h > MAX_CELLS:
            fail("cgrp: %s 헤더의 칸 수 %d × %d 가 너무 큽니다 (CGRP 가 아니거나 깨진 파일)", name, w, h)
        need = HEADER_SIZE + 4 * w * h
        if len(data) != need:
            fail("cgrp: %s 크기가 헤더와 맞지 않습니다 — 헤더 %d × %d 칸이면 %d B, 실제 %d B", name, w, h, need, len(data))
        cells = struct.unpack_from("<%dI" % (w * h), data, HEADER_SIZE)
        return cls(w, h, cells, dw, dh, count, path=path)

    @classmethod
    def load(cls, path, missing_ok=False, base=None):
        """CGRP 파일을 읽는다(컴파일 시점).

        인자: path(파일 경로. 상대 경로는 base(없으면 현재 작업 폴더 — euddraft 는 eds 폴더) → 환경 변수 `EUDEXT_CGRP_DIR`
              순서로 찾는다), missing_ok(True 면 없을 때 빈 그림(found=0)을 돌려준다), base(상대 경로의 기준 폴더)
        반환: CGRP
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const cg = cgrp.CGRP.load("a.cgrp", missing_ok=True);` 또는 `cgrp.load(…)`
        출처: CtrigAsm `f_GetFileptr`(가이드북 8290~8306)의 컴파일 시점 대체
        """
        p = unProxy(path)
        if not isinstance(p, str) or not p:
            fail("cgrp.load: path 는 파일 경로 문자열이어야 합니다 (%r)", path)
        tried = []
        if os.path.isabs(p):
            tried.append(p)
        else:
            tried.append(os.path.join(base if base is not None else os.getcwd(), p))
            env = os.environ.get("EUDEXT_CGRP_DIR")
            if env:
                tried.append(os.path.join(env, p))
        for cand in tried:
            if os.path.isfile(cand):
                with open(cand, "rb") as f:
                    return cls.from_bytes(f.read(), path=cand)
        if missing_ok:
            return cls(0, 0, [], 0, 0, 0, path=p, found=0)
        fail("cgrp.load: CGRP 파일 %r 을(를) 찾지 못했습니다 (찾아본 곳: %s)", p, ", ".join(tried))

    @classmethod
    def from_cells(cls, width, height, cells, dot_w=3, dot_h=3, count=None):
        """칸 값 목록으로 만든다(합성 그림·시험용).

        인자: width, height, cells(행 우선 W·H 개), dot_w, dot_h, count(헤더 +0, None = Fill 칸 수)
        반환: CGRP
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const cg = cgrp.CGRP.from_cells(2, 1, list(0x80, 0x81));`
        출처: 새로 작성
        """
        return cls(width, height, cells, dot_w, dot_h, count)

    @classmethod
    def from_rows(cls, rows, dot=3, legend=None, image=233, height=0):
        """글자 그림으로 만든다(예제·시험용). 한 글자 = 한 칸.

        인자: rows(같은 길이 문자열 목록), dot(점 크기 px, 가로·세로 같음), legend({글자: 칸 값} — 기본 아래 표),
              image·height(0 이 아닌 칸에 이미지·높이 비트가 없으면 채울 값)
        기본 legend: `.`·공백 = 빈 칸, `#` = Fill, `R`/`G`/`B`/`W`/`E`/`I`/`X` = Fill + Red/Green/Blue/White/EMP/Indigo/Box,
              `r`/`g`/`b` = Fill + 그 색 + 적색 명암 1, `k` = Fill + Red + 흑색 명암 2
        반환: CGRP
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const cg = cgrp.CGRP.from_rows(list("R.G", ".B."), dot=4);`
        출처: 새로 작성
        """
        fname = "cgrp.CGRP.from_rows"
        rows = [unProxy(r) for r in unProxy(rows)]
        if not rows or not all(isinstance(r, str) for r in rows) or len({len(r) for r in rows}) != 1:
            fail("%s: rows 는 길이가 같은 문자열 목록이어야 합니다 (%r)", fname, rows)
        table = dict(_DEFAULT_LEGEND if legend is None else unProxy(legend))
        img = _const(image, fname, "image", 0, 0x3FF)
        h = _const(height, fname, "height", 0, 255)
        cells = []
        for r in rows:
            for ch in r:
                if ch not in table:
                    fail("%s: legend 에 없는 글자 %r", fname, ch)
                v = _const(table[ch], fname, "legend 값", 0, M32)
                if v:
                    if not v & (0x3FF << 14):
                        v |= img << 14
                    if not v & (0xFF << 24):
                        v |= h << 24
                cells.append(v)
        d = _const(dot, fname, "dot", 0, 0xFFFF)
        return cls(len(rows[0]), len(rows), cells, d, d)

    def to_bytes(self):
        """파일 내용(헤더 16B + 칸).

        인자: 없음
        반환: bytes
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다
        출처: 가이드북 8321~8345
        """
        head = struct.pack("<IIIHH", self.count, self.width, self.height, self.dot_w, self.dot_h)
        return head + struct.pack("<%dI" % len(self.cells), *self.cells)

    def __repr__(self):
        return ("<cgrp.CGRP %s %d×%d 칸 점 %d×%dpx count=%d fill=%d%s — epScript 에서는 const 로 묶으세요>"
                % (self.path or "-", self.width, self.height, self.dot_w, self.dot_h, self.count, self.fill_count,
                   "" if self.found else " (파일 없음)"))

    # --- 읽기 ---
    @property
    def fill_count(self):
        return sum(1 for v in self.cells if v & FILL)

    @property
    def painted_count(self):
        return sum(1 for v in self.cells if v & (FILL | COLOR_BITS))

    @property
    def pixel_width(self):
        return self.width * self.dot_w

    @property
    def pixel_height(self):
        return self.height * self.dot_h

    def summary(self):
        """한 줄 요약 문자열(인게임 확인·로그용).

        인자: 없음
        반환: str — 파일 이름, 칸·점 크기, 헤더 점 수와 그 뜻(`count_meaning`), Fill·색 칸 수, 흰색 칸 수, 쓰인 비트,
              이미지·높이 목록. `{`·`}` 가 없어 printAll 서식 문자열로 그대로 쓸 수 있다
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `printAll(cg.summary());`
        출처: 새로 작성 (인게임 F21-7 확인용)
        """
        if not self.found:
            return "CGRP %s: 파일 없음" % os.path.basename(str(self.path))
        imgs = sorted({f_cell_image(v) for v in self.cells if v & (FILL | COLOR_BITS)})
        hts = sorted({f_cell_height(v) for v in self.cells if v & (FILL | COLOR_BITS)})
        bits = 0
        for v in self.cells:
            bits |= v & 0xFF
        return ("CGRP %s: %d x %d 칸, 점 %d x %d px, 헤더 점 수 %d (%s), Fill %d, 색·Fill 칸 %d, 흰색 %d,"
                " 쓰인 비트 0x%02X, 이미지 %s, 높이 %s"
                % (os.path.basename(str(self.path)), self.width, self.height, self.dot_w, self.dot_h, self.count,
                   self.count_meaning() or "뜻 모름", self.fill_count, self.painted_count, len(self.points(WHITE)), bits,
                   _short(imgs), _short(hts)))

    def count_meaning(self):
        """헤더 +0(가이드북: 전체 점의 개수)이 어느 값과 같은지 — 실제 파일로 뜻을 확인하기 위한 도구.

        인자: 없음
        반환: "fill"(Fill 칸 수) | "painted"(Fill 또는 색 비트가 있는 칸 수) | "cells"(W·H) | None(어느 것도 아님)
        비용: 없음
        CP: 해당 없음
        로컬: 해당 없음
        epScript: 쓰지 않는다(`summary()` 에 들어 있다)
        출처: 가이드북 8323
        """
        for name, v in (("fill", self.fill_count), ("painted", self.painted_count),
                        ("cells", self.width * self.height)):
            if self.count == v:
                return name
        return None

    def cell(self, x, y):
        """칸 (x, y) 의 값.

        인자: x(가로 0~W−1), y(세로 0~H−1) — 파이썬 정수
        반환: int (dword)
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const v = cg.cell(3, 4);`
        출처: 가이드북 8325 (행 우선 칸 배열)
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            fail("cgrp.CGRP.cell: (%r, %r) 가 %d × %d 밖입니다", x, y, self.width, self.height)
        return self.cells[y * self.width + x]

    def points(self, select=FILL, mask=None):
        """조건에 맞는 칸 목록(행 우선).

        인자: select(비교 값), mask(None 이면 select) — (값 & mask) == select 인 칸
        반환: [(x, y, 값)]
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const reds = cg.points(1);`
        출처: 예제 29-4 `NVar(CGRP, Exactly, 128, 128)` 의 컴파일 시점 판
        """
        m = select if mask is None else mask
        w = self.width
        return [(i % w, i // w, v) for i, v in enumerate(self.cells) if v & m == select] if w else []

    def white_points(self):
        """흰색(비트 3) 칸 목록 — 층에 넣지 않으므로 따로 매 프레임 갱신할 때 쓴다.

        인자: 없음
        반환: [(dx, dy, 높이)] (px, 원점 기준)
        비용: 없음(컴파일 시점)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const whites = cg.white_points();`
        출처: 가이드북 8466~8470 (흰색은 42틱 안에 다시 찍기), 예제 29-7 White UnitSprite
        """
        return [(x * self.dot_w, y * self.dot_h, f_cell_height(v)) for x, y, v in self.points(WHITE)]

    def _offsets(self, fname):
        if self.width and (self.width - 1) * self.dot_w > 0xFFFF or self.height and (self.height - 1) * self.dot_h > 0xFFFF:
            fail("%s: 그림이 65535px 을 넘습니다 (%d×%d 칸, 점 %d×%d)", fname, self.width, self.height, self.dot_w, self.dot_h)

    def layers(self, mode="stack", height=None, image="cell", color=None):
        """그릴 점만 추려 층 목록으로 만든다(컴파일 시점).

        인자: mode —
              "stack"(예제 29-6·29-10): 기본색 층(Red 0·Green 13·Blue 16·EMP 8·Indigo 12·Box 15)과 색 비트 없는 Fill 층을
                높이 height(기본 5)에, 적색 명암 N 인 점을 화면 출력 6·높이 height+1 에 N 번, 흑색 명암 N 인 점을 화면 출력 10·
                높이 height+2 에 N 번.
              "height"(예제 29-5·29-7): 같은 층을 **칸의 높이 + height(기본 0)** 에, 적색 명암은 그 +1 에 N 번. 흑색 명암은
                찍지 않는다(뒤에 명암 배경을 깔고 높이차로 나타낸다).
              "fill"(예제 29-4): Fill 칸만 한 층(화면 출력 color, None = 바꾸지 않음), 높이 height(None = 칸의 높이).
              height(위 뜻, 0~255), image("cell" = 칸의 이미지 비트 | None = 스프라이트 이미지를 바꾸지 않음 | 번호),
              color(mode "fill" 만)
        반환: list[CGRPLayer] — 순서 = `LAYER_ORDER` 분류 → (이미지, 높이). 빈 층은 없다. 흰색 점은 넣지 않는다
        의미: 칸 (x, y) 의 점은 원점에서 (x·dot_w, y·dot_h) px. 명암·높이 + 1·+2 가 255 를 넘으면 255.
              image="cell" 인데 찍을 칸의 이미지 비트가 998 을 넘으면 오류(images.dat 밖).
        비용: 없음(컴파일 시점). 층의 Db 는 점 1개(반복 포함)당 4B
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `const layers = cg.layers(mode="height");`
        출처: 예제 29-4~29-10 (가이드북 18217~18620), R4a B.3·B.4
        """
        fname = "cgrp.CGRP.layers"
        mode = unProxy(mode)
        if mode not in _MODES:
            fail("%s: mode 는 %s 중 하나여야 합니다 (%r)", fname, "/".join(_MODES), mode)
        if color is not None and mode != "fill":
            fail("%s: color 는 mode=\"fill\" 에서만 씁니다", fname)
        col = None if color is None else _const(color, fname, "color", 0, 255)
        if mode == "stack":
            base = 5 if height is None else _const(height, fname, "height", 0, 255)
        elif mode == "height":
            base = 0 if height is None else _const(height, fname, "height", 0, 255)
        else:
            base = None if height is None else _const(height, fname, "height", 0, 255)
        image = unProxy(image)
        if image != "cell" and image is not None:
            image = _const(image, fname, "image", 0, _IMAGE_LAST)
        self._offsets(fname)
        groups = {}

        def add(cat, code, img, h, dx, dy, n=1):
            key = (LAYER_ORDER.index(cat), -1 if img is None else img, min(h, 255))
            g = groups.get(key)
            if g is None:
                g = groups[key] = (cat, code, img, min(h, 255), [])
            g[4].extend([(dx, dy)] * n)

        w = self.width
        for i, v in enumerate(self.cells):
            if not v:
                continue
            dx, dy = (i % w) * self.dot_w, (i // w) * self.dot_h
            img = f_cell_image(v) if image == "cell" else image
            if img is not None and img > _IMAGE_LAST and v & (FILL | COLOR_BITS | 0x3F00):
                fail("%s: 칸 (%d, %d) 의 이미지 번호 %d 가 images.dat 범위(0~%d) 밖입니다 — layers(image=번호 또는 None)",
                     fname, i % w, i // w, img, _IMAGE_LAST)
            if mode == "fill":
                if v & FILL:
                    add("fill", col, img, f_cell_height(v) if base is None else base, dx, dy)
                continue
            h = base if mode == "stack" else f_cell_height(v) + base
            for name, bit in _BASE:
                if v & bit:
                    add(name, COLOR_CODES[bit], img, h, dx, dy)
            if v & FILL and not v & COLOR_BITS:
                add("fill", None, img, h, dx, dy)
            r = f_red_level(v)
            if r:
                add("red_stack", RED_STACK_CODE, img, h + 1, dx, dy, r)
            b = f_black_level(v)
            if b and mode == "stack":
                add("black_stack", BLACK_STACK_CODE, img, base + 2, dx, dy, b)
        return [CGRPLayer(cat, code, img, h, pts) for _k, (cat, code, img, h, pts) in sorted(groups.items())]


def _short(vals):
    if len(vals) <= 6:
        return "/".join(str(v) for v in vals) or "-"
    return "%s…%s (%d종)" % ("/".join(str(v) for v in vals[:3]), vals[-1], len(vals))


_DEFAULT_LEGEND = {
    ".": 0, " ": 0, "#": FILL,
    "R": FILL | RED, "G": FILL | GREEN, "B": FILL | BLUE, "W": FILL | WHITE, "E": FILL | EMP, "I": FILL | INDIGO,
    "X": FILL | BOX,
    "r": FILL | RED | (1 << 11), "g": FILL | GREEN | (1 << 11), "b": FILL | BLUE | (1 << 11),
    "k": FILL | RED | (2 << 8),
}


def f_load(path, missing_ok=False, base=None):
    """`CGRP.load` 와 같다(모듈 함수판).

    인자·반환: `CGRP.load`
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const cg = cgrp.load("a.cgrp");` (→ `cgrp.f_load`)
    출처: 새로 작성
    """
    return CGRP.load(path, missing_ok=missing_ok, base=base)


load = f_load


class CGRPLayer:
    """같은 화면 출력·이미지·높이로 찍는 점 묶음(컴파일 시점). `CGRP.layers()` 가 만든다(직접 만들어도 된다).

    인자: name(분류 이름), color(이미지 화면 출력 번호 0~255 또는 None = 바꾸지 않음), image(스프라이트에 넣을 이미지
          번호 또는 None = 바꾸지 않음), height(0~255), points([(dx, dy)] px, 0~65535 — 같은 점이 여러 번 있어도 된다. 펼친 정수 목록도 받는다)
    속성: count, db(점마다 dword `dx | dy << 16` 을 구운 `Db`, 처음 읽을 때 만든다), data()(그 바이트)
    비용: 점 1개당 4B
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const lay = cgrp.CGRPLayer("mine", 0, 233, 5, list(0, 0, 3, 0));` (펼친 목록 = (0, 0), (3, 0))
    출처: R4a B.4
    """

    __slots__ = ("name", "color", "image", "height", "points", "_db")

    def __init__(self, name, color, image, height, points):
        fname = "cgrp.CGRPLayer"
        self.name = str(unProxy(name))
        self.color = None if color is None else _const(color, fname, "color", 0, 255)
        self.image = None if image is None else _const(image, fname, "image", 0, _IMAGE_LAST)
        self.height = _const(height, fname, "height", 0, 255)
        raw = [unProxy(p) for p in unProxy(points)]
        if raw and all(_int(p) for p in raw):  # epScript list(dx0, dy0, dx1, dy1, …) — 중첩 list 는 펼쳐진다
            if len(raw) % 2:
                fail("%s: 펼친 점 목록의 길이가 홀수입니다 (%d)", fname, len(raw))
            raw = [(raw[i], raw[i + 1]) for i in range(0, len(raw), 2)]
        pts = []
        for p in raw:
            p = unProxy(p)
            if not isinstance(p, (list, tuple)) or len(p) != 2:
                fail("%s: 점은 (dx, dy) 여야 합니다 (%r)", fname, p)
            pts.append((_const(p[0], fname, "dx", 0, 0xFFFF), _const(p[1], fname, "dy", 0, 0xFFFF)))
        self.points = pts
        self._db = None

    def __repr__(self):
        return "<cgrp.CGRPLayer %s color=%r image=%r height=%d 점 %d>" % (
            self.name, self.color, self.image, self.height, len(self.points))

    @property
    def count(self):
        return len(self.points)

    def data(self):
        """구울 바이트: 점마다 dword `dx | dy << 16` (리틀 엔디언).

        인자: 없음 / 반환: bytes / 비용: 없음(컴파일 시점) / CP: 해당 없음 / 로컬: 해당 없음
        epScript: 쓰지 않는다(`lay.db` 가 이 바이트의 Db) / 출처: R4a B.4
        """
        return b"".join(struct.pack("<HH", dx, dy) for dx, dy in self.points)

    @property
    def db(self):
        if self._db is None:
            self._db = Db(self.data())
        return self._db


# =============================================================================================
# 그리기 (런타임)
# =============================================================================================


class CGRPPainter:
    """층 목록을 프레임마다 N 점씩 영구 스프라이트로 찍는다(런타임).

    인자: source(CGRP — `layers()` 기본값을 쓴다 — 또는 CGRPLayer 목록), kind(BulletKind — 보통 `bullet.CtrigKind`,
          weapon·flingy 필요), owner(P1~P12·CurrentPlayer 또는 변수 — 가이드북: 대량이면 컴퓨터),
          per_frame(한 프레임에 찍는 점 수 1~4096, 기본 64), delay(전역 설정이 바뀌는 층 사이에 더 쉴 프레임 0~65535,
          기본 4 — 예제 29-6), sprite(층의 이미지를 넣을 스프라이트 번호. None = kind.sprite(CtrigKind)),
          on_fail("skip" = 빈 칸이 없거나 생성이 실패한 점은 버림(CtrigAsm 과 같음) | "retry" = 이번 프레임을 끝내고 다음
          프레임에 그 점부터 다시)
    메서드: `start(ox, oy)`(원점 = 칸 (0, 0) 점의 좌표, 상수·변수. 처음부터 다시), `tick()`(매 프레임 한 번),
            `stop()`, `done()`(조건: 다 찍음), `running()`(조건)
    속성: dropped(실패한 점 수 EUDVariable — 3.10 넘침 카운터, start 때 0), drawn(만든 점 수), layers,
          total(찍을 점 수, 반복 포함 — 파이썬 정수)
    의미: 층마다 먼저 전역 dat 를 쓴다 — 무기 투사 방식 ← 7, flingy 최고속도 ← 0, elevation[탄막 유닛] ← 층 높이,
          [sprites[sprite].image ← 층 이미지], [images[이미지].화면 출력 ← 층 색]. 층의 이미지·색이 None 이면 CtrigKind 의
          image·color(BulletInitSetting 값)를 쓰고, 그 밖의 종류면 그 칸을 건드리지 않는다. 그다음 점마다 `bullet.perma_sprite(kind,
          owner, ox + dx, oy + dy, 0, 0)` 와 같은 본문을 부른다(방향 0, CtrigKind 면 로케이션 Y − 2). (이미지, 색)이 바뀌는
          층으로 넘어가면 그 프레임을 끝내고 delay 프레임 더 쉰다(총알은 트리거 뒤 게임 로직에서 만들어지므로 한 프레임에
          두 설정을 섞으면 마지막 값으로 그려진다). 높이만 바뀌는 층은 쉬지 않는다(높이는 유닛을 만들 때 정해진다 — 예제 29-7).
          같은 프레임에 같은 무기·스프라이트를 쓰는 다른 코드가 있으면 그 값이 섞인다.
    비용: tick 본문 painter 마다 1벌(층 1개 29, 2개 34, 6개 52, 12개 72 — 층당 약 5) + perma 본문 12(공유) / 호출 자리 1 /
          실행 = 점 1개당 약 126 + 층 전환마다 약 10, 쉬는 프레임 7 (docs/COSTS.md "cgrp (WP21)"). 점 데이터 4B/점,
          한 번 페이로드 painter 한 개 약 15~22KB
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const p = cgrp.CGRPPainter(cg.layers(), k, P8, per_frame=32); … p.start(384, 1120); p.tick();`
    출처: 예제 29-4~29-10 (가이드북 18217~18620)의 이중 루프 대체, R4a B.4
    """

    __slots__ = ("layers", "kind", "per_frame", "delay", "sprite", "on_fail", "dropped", "drawn", "total", "_owner",
                 "_state", "_step", "_left", "_ptr", "_wait", "_budget", "_brk", "_ox", "_oy", "_fn", "_acts",
                 "_groups")

    def __init__(self, source, kind, owner, per_frame=64, delay=4, sprite=None, on_fail="skip"):
        fname = "cgrp.CGRPPainter"
        src = unProxy(source)
        if isinstance(src, CGRP):
            layers = src.layers()
        elif isinstance(src, (list, tuple)) and all(isinstance(unProxy(x), CGRPLayer) for x in src):
            layers = [unProxy(x) for x in src]
        else:
            fail("%s: source 는 CGRP 또는 CGRPLayer 목록이어야 합니다 (%r)", fname, source)
        self.layers = [lay for lay in layers if lay.count]
        self.total = sum(lay.count for lay in self.layers)
        k = unProxy(kind)
        if not isinstance(k, bullet.BulletKind):
            fail("%s: kind 는 bullet.BulletKind(보통 CtrigKind)여야 합니다 (%r)", fname, kind)
        k._need("weapon", fname)
        k._need("flingy", fname)
        self.kind = k
        self._owner = bullet._owner(owner, fname)
        self.per_frame = _const(per_frame, fname, "per_frame", 1, 4096)
        self.delay = _const(delay, fname, "delay", 0, 0xFFFF)
        on_fail = unProxy(on_fail)
        if on_fail not in ("skip", "retry"):
            fail("%s: on_fail 은 \"skip\" 또는 \"retry\" 여야 합니다 (%r)", fname, on_fail)
        self.on_fail = on_fail
        if sprite is None:
            sprite = getattr(k, "sprite", None) if isinstance(k, bullet.CtrigKind) else None
        self.sprite = None if sprite is None else _const(sprite, fname, "sprite", 0, _SPRITE_LAST)
        ctrig = isinstance(k, bullet.CtrigKind)
        # 층의 None = CtrigKind 의 이미지·색(BulletInitSetting 값). 그 밖의 종류면 바꾸지 않음
        keys = [(lay.image if lay.image is not None or not ctrig else k.image,
                 lay.color if lay.color is not None or not ctrig else k.color) for lay in self.layers]
        if self.sprite is None and any(img is not None for img, _c in keys):
            fail("%s: 이미지가 있는 층이 있는데 sprite 를 모릅니다 — sprite= 를 주거나 CtrigKind 를 쓰세요"
                 " (또는 layers(image=None))", fname)
        if any(c is not None and img is None for img, c in keys):
            fail("%s: 색이 있는 층의 이미지 번호를 모릅니다 — CtrigKind 를 쓰거나 layers(image=번호)", fname)
        self._acts = [self._step_actions(lay, img, c) for lay, (img, c) in zip(self.layers, keys)]
        self._groups = [j for j in range(1, len(keys)) if keys[j] != keys[j - 1]]
        self.dropped = EUDVariable()
        self.drawn = EUDVariable()
        (self._state, self._step, self._left, self._ptr, self._wait, self._budget, self._brk, self._ox,
         self._oy) = (EUDVariable() for _ in range(9))
        self._fn = None

    def __repr__(self):
        return "<cgrp.CGRPPainter 층 %d 점 %d per_frame=%d delay=%d — epScript 에서는 const 로 묶으세요>" % (
            len(self.layers), sum(lay.count for lay in self.layers), self.per_frame, self.delay)

    def _step_actions(self, lay, img, color):
        k = self.kind

        def decl(d):
            d.weapon(k.weapon).set(behavior=bullet._BEHAVIOR_SPRITE)
            d.flingy(k.flingy).set(topSpeed=0)
            d.unit(k.made_unit).set(elevation=lay.height)
            if img is not None:
                d.sprite(self.sprite).set(image=img)
            if color is not None:
                d.image(img).set(drawingFunction=color)

        return dat.actions(decl)

    # --- 런타임 ---
    def start(self, ox, oy):
        """원점을 정하고 처음 층부터 다시 찍는다(dropped·drawn 도 0).

        인자: ox, oy(칸 (0, 0) 점의 맵 좌표 — 상수·변수)
        반환: None
        비용: 호출 자리 2 / 실행 약 4
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `p.start(384, 1120);`
        출처: 예제 29-4 `Y = 1120`, `X = 384`
        """
        fname = "cgrp.CGRPPainter.start"
        vals = [bullet._num(v, fname, n) for v, n in ((ox, "ox"), (oy, "oy"))]
        SeqCompute([(self._ox, SetTo, vals[0]), (self._oy, SetTo, vals[1])])
        DoActions(self._state.SetNumber(1 if self.layers else 2), self._step.SetNumber(0), self._left.SetNumber(0),
                  self._wait.SetNumber(0), self.dropped.SetNumber(0), self.drawn.SetNumber(0))

    def stop(self):
        """그리기를 멈춘다(done 은 거짓). 다시 하려면 start.

        인자: 없음 / 반환: None / 비용: 호출 자리 1 / CP: 바꾸지 않음 / 로컬: 공유 / epScript: `p.stop();` / 출처: 새로 작성
        """
        DoActions(self._state.SetNumber(0))

    def done(self):
        """조건: 모든 층을 다 찍었다(새 Condition).

        인자: 없음 / 반환: Condition / 비용: 조건 1 / CP: 바꾸지 않음 / 로컬: 공유
        epScript: `if (p.done()) { … }` / 출처: R4a B.4
        """
        return self._state.Exactly(2)

    def running(self):
        """조건: 찍는 중이다(start 뒤 done 전, stop 전).

        인자: 없음 / 반환: Condition / 비용: 조건 1 / CP: 바꾸지 않음 / 로컬: 공유
        epScript: `if (p.running()) { … }` / 출처: 새로 작성
        """
        return self._state.Exactly(1)

    def tick(self):
        """한 프레임 분량을 찍는다(매 프레임 한 번. 본문은 처음 부를 때 한 벌 만든다).

        인자: 없음
        반환: None
        비용: 호출 자리 1 / 실행 = 쉬는 프레임 약 5, 찍는 프레임 약 20 + 점당 약 125 (docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `p.tick();`
        출처: 예제 29-6 의 단계(Step)·Delay 흐름
        """
        self._tick_func()()

    def _tick_func(self):
        # 이 painter 의 tick 본문 EUDFunc (처음 부를 때 만든다 — 비용 측정도 이것을 본다)
        if self._fn is None:
            self._fn = EUDFunc(_make_tick(self))
        return self._fn

    def _emit_tick(self):
        k = self.kind
        n = len(self.layers)
        retry = self.on_fail == "retry"
        if not n:  # 빈 그림: start 가 곧바로 done 으로 둔다
            return
        if EUDIf()(self._state.Exactly(1)):
            if EUDIf()(self._wait.AtLeast(1)):
                DoActions(self._wait.SubtractNumber(1))
            if EUDElse()():
                DoActions(self._budget.SetNumber(self.per_frame), self._brk.SetNumber(0))
                if EUDWhile()(self._brk.Exactly(0)):
                    # 1) 지금 층의 전역 dat (처음 들어가면 점 위치·개수도)
                    EUDSwitch(self._step)
                    for i, lay in enumerate(self.layers):
                        if EUDSwitchCase()(i):
                            if self._acts[i]:
                                DoActions(self._acts[i])
                            RawTrigger(conditions=self._left.Exactly(0),
                                       actions=[self._ptr.SetNumber(EPD(lay.db)), self._left.SetNumber(lay.count)])
                            EUDBreak()
                    EUDEndSwitch()
                    # 2) 점 찍기
                    if EUDWhile()([self._left.AtLeast(1), self._budget.AtLeast(1)]):
                        dx = f_wread_epd(self._ptr, 0)
                        dy = f_wread_epd(self._ptr, 2)
                        r = bullet._sprite_call(k, self._owner, self._ox + dx, self._oy + dy, "cgrp.CGRPPainter")
                        if retry:
                            if EUDIf()(r.Exactly(0)):
                                DoActions(self.dropped.AddNumber(1))
                                EUDBreak()
                            EUDEndIf()
                        DoActions(self._ptr.AddNumber(1), self._left.SubtractNumber(1),
                                  self._budget.SubtractNumber(1), self.drawn.AddNumber(1))
                        if not retry:
                            # 실패한 점: drawn 을 되돌린다(방금 1 더했으므로 포화 뺄셈이 0 에 걸리지 않는다)
                            RawTrigger(conditions=r.Exactly(0),
                                       actions=[self.dropped.AddNumber(1), self.drawn.SubtractNumber(1)])
                    EUDEndWhile()
                    # 3) 층 끝: 다음 층으로 (설정이 바뀌면 이번 프레임을 끝내고 쉰다, 마지막이면 끝)
                    if EUDIf()(self._left.Exactly(0)):
                        DoActions(self._step.AddNumber(1))
                        EUDSwitch(self._step)
                        for j in self._groups:
                            if EUDSwitchCase()(j):
                                DoActions(self._wait.SetNumber(self.delay), self._brk.SetNumber(1))
                                EUDBreak()
                        if EUDSwitchCase()(n):
                            DoActions(self._state.SetNumber(2), self._brk.SetNumber(1))
                            EUDBreak()
                        EUDEndSwitch()
                    if EUDElse()():
                        DoActions(self._brk.SetNumber(1))
                    EUDEndIf()
                EUDEndWhile()
            EUDEndIf()
        EUDEndIf()


def _make_tick(painter):
    def cgrp_tick():
        painter._emit_tick()

    return cgrp_tick

