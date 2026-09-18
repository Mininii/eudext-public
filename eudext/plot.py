"""도형 찍기 — 좌표표를 루프 하나로 찍는 `Plotter`, 점 변환(CA_ 대체), 상태 없는 부품 (DESIGN 4.13).

    from eudext.shape import CX, ShapeSet
    from eudext.plot import Plotter
    shapes = ShapeSet([ring, star, fade])
    pl = Plotter(shapes, unit="Zerg Scourge", owner=P8, loc="CAPlot", per_tick=12, delay=1, size=0, repeat=False)
    pl.start(shape=1, center=(x, y))          # 또는 center="loc"(pl 의 로케이션 지금 중심) / 다른 로케이션 이름·번호

    @pl.on_point                              # CAfunc 대체 (파이썬). 점마다 생성 직전에 불린다
    def fx(pt):
        pt.rotate(angle)                      # CA_Rotate (mathx.Rotator — CtrigAsm 과 같은 값)
        pt.move(dx, dy); pt.ratio(3, 2, 1, 1) # CA_MoveXY, CA_RatioXY
        pt.crop(x2=200)                       # CA_CropXY (범위 밖이면 건너뜀)
        if EUDIf()(pt.x > 200): pt.skip()
        EUDEndIf()
    pl.tick()                                 # 매 프레임 1회 (본문은 서브루틴 한 벌, 호출 자리 1)
    pl.busy / pl.done                         # 조건

    for pt in pl.each():                      # tick() 대신: 본문을 그 자리에 쓰는 판 (epScript 는 이것)
        pt.rotate(angle)
        if EUDIf()(pt.index == 3): EUDContinue()   # continue = 이 점 건너뛰기, break = 이번 사이클 멈춤(그 점은 다음에)
        EUDEndIf()

epScript:

    import eudext.plot as plot;
    const pl = plot.Plotter(shapes, unit="Zerg Scourge", owner=P1, loc=26, per_tick=4);
    function afterTriggerExec() {
        if (pl.done) { pl.start(0, center=list(2048, 2048)); }
        foreach (pt : pl.each()) { pt.rotate(ang); if (pt.x > 200) continue; }
    }

## 한 프레임 (theSeed CAPlotIndexed.lua 루프와 같은 의미, S1 6.2)

    if 찍는 중 and w == 0:
        L = 스케줄이 있으면 sched[ptr] (그리고 밴드 수 > ptr 이면 ptr += 1), 없으면 per_tick
        k = min(L, n − p)
        k 번: 점 p 읽기 → 편향 빼기 → on_point → (건너뛰지 않으면) 중심 더하기 → 로케이션 ±size → CreateUnit → p += 1
        w = delay
        p ≥ n 이면: repeat 면 p = 0, ptr = 1 / 아니면 끝(done)
    w = max(w − 1, 0)

- delay 0 과 1 은 둘 다 매 프레임, delay k(≥2) 는 k 프레임에 한 번. 첫 사이클은 start() 한 프레임에 돈다(start 가 tick 앞이면).
- 스케줄(LoopMax, `Shape.sweep`/`with_schedule`)은 도형에 붙는다. 포인터는 **start() 마다 1** 에서 시작한다
  (CAPlotIndexed 의 2026-09-09 버그 기록 — 원본은 매 호출 1 로 되돌리는 코드였다, S1 12-1). 밴드 값 0 인 사이클은 쉰다.
  마지막 밴드를 지나면 그 값이 되풀이된다.
- 루프 본문은 도형 수·점 수와 무관한 트리거 몇십 개다(DESIGN 3.8). 점 하나 = 좌표 4B("db").
- 점 좌표를 읽은 뒤 `pt.x`/`pt.y`(부호 있는 32비트)를 고칠 수 있다. 중심은 그 뒤에 더한다(CAPI 와 같은 순서).
- 로케이션은 점마다 (X−size, Y−size, X+size, Y+size) 로 옮기고 **되돌리지 않는다**(찍기 전용 로케이션을 쓴다).
  X·Y 가 맵 밖이어도 원본처럼 그대로 만든다(생성이 실패할 뿐). 걸러야 하면 `pt.crop`.

## 각도 기준 (사용자 결정 D5 — CtrigAsm 과 같게, 옵션 없음)

- 정적 도형(CB Paint, `shape.CX`)은 **0° = 12시**, 각이 늘면 시계 방향.
- 런타임 점 변환 `pt.rotate`·`rotate`·`rotate3d` 는 CtrigAsm CA_ 함수와 같은 **0° = +x(3시)** 기준에 `Include_MatheMatics`
  Cycle 단위(기본 360)다. 양의 각은 화면에서 시계 방향 — 회전 방향은 정적 도형과 같고, "각 0 이 가리키는 곳" 만 90° 다르다.
  이 어긋남은 원본 그대로다(R4b B6·B8). 결과 값은 CtrigAsm `CA_Rotate` 와 같다(항별 자르기, mathx).

## 재진입 (DESIGN 3.3)

`on_point`/`each()` 본문 안에서 **같은 Plotter** 의 `tick()`/`each()` 를 부르면 빌드 오류다. 다른 Plotter·`create_shape`·
점 읽기(`shapes.point_at`)는 불러도 된다(차례로 실행될 뿐 되돌아올 곳이 겹치지 않는다). 본문 안에서 `start()` 를
부르면 다음 점부터 새 도형이 섞인다 — 이번 사이클이 끝난 뒤(루프 밖)에서 부른다.

출처: theSeed `Engine/CAPlotIndexed.lua`(CAPI:216~411), CB Paint v2.5 `CBPlot`(CBP:15068~15420)·`CSPlot`(CBP:7023)·
CA_ 함수(CBP:9658~10060), S1 6.2~6.3·8.5·11-4, R4b B5~B8.
"""

import functools

from eudplib import (
    EPD,
    CreateUnit,
    CreateUnitWithProperties,
    DoActions,
    EncodeLocation,
    EncodePlayer,
    EncodeUnit,
    EUDElse,
    EUDEndIf,
    EUDEndWhile,
    EUDFunc,
    EUDIf,
    EUDLightVariable,
    EUDSetContinuePoint,
    EUDVariable,
    EUDWhile,
    RawTrigger,
    SeqCompute,
    SetMemoryEPD,
    SetTo,
    Add,
    Subtract,
    f_dwread_epd,
    unProxy,
)

from eudext import _compat, _parts, cmp, mathx, units
from eudext.errors import check_choice, fail, warn
from eudext.shape import ShapeSet

M32 = 0xFFFFFFFF
MRGN_EPD = EPD(0x58DC60)  # 로케이션 표 (1-based n → +5·(n−1))
PER_TICK_ALL = "all"

__all__ = [
    "PER_TICK_ALL",
    "Plotter",
    "Point",
    "create_shape",
    "f_create_shape",
    "f_inside",
    "f_loc_center",
    "f_move",
    "f_ratio",
    "f_read_from",
    "f_read_point",
    "f_rotate",
    "f_rotate3d",
    "f_setloc_box",
    "inside",
    "loc_center",
    "move",
    "ratio",
    "read_from",
    "read_point",
    "rotate",
    "rotate3d",
    "setloc_box",
]


# =============================================================================================
# 인자 도우미
# =============================================================================================


def _num(x, fname, what, lo=-(1 << 31), hi=M32, allow_var=True):
    """정수 상수(범위 검사) 또는 EUDVariable(주소식·읽기 전용 칸은 새 변수로)."""
    x = unProxy(x)
    if isinstance(x, bool):
        x = int(x)
    if isinstance(x, int):
        if not lo <= x <= hi:
            fail("%s: %s 상수 %d 가 범위(%d ~ %d) 밖입니다", fname, what, x, lo, hi)
        return x
    if isinstance(x, float):
        fail("%s: %s 에 실수 %r 는 쓸 수 없습니다", fname, what, x)
    if allow_var:
        if _compat.is_var(x):
            return x
        if _compat.is_varbase(x) or hasattr(x, "getValueAddr"):
            return f_dwread_epd(EPD(x.getValueAddr()))
        if _compat.is_const(x):
            v = EUDVariable()
            v << x
            return v
    fail("%s: %s 로 쓸 수 없는 값입니다 (%r)", fname, what, x)


def _loc_check(loc, fname):
    """로케이션 인자 검사: 이름(문자열 — 맵을 불러온 뒤 번호로 바꾼다) 또는 1-based 번호 상수 (DESIGN 3.9)."""
    loc = unProxy(loc)
    if isinstance(loc, bool) or not isinstance(loc, (int, str)):
        fail("%s: 로케이션은 이름 또는 1부터 번호(상수)여야 합니다 (%r)", fname, loc)
    if isinstance(loc, int) and not 1 <= loc <= 255:
        fail("%s: 로케이션 번호 %r 는 1 ~ 255 여야 합니다 (0부터 번호는 받지 않는다 — DESIGN 3.9)", fname, loc)
    return loc


def _loc_const(loc, fname):
    """로케이션 이름 또는 1-based 번호(상수) → 1-based 정수. 이름은 맵을 불러온 뒤에만 바꿀 수 있다."""
    loc = _loc_check(loc, fname)
    n = EncodeLocation(loc)
    if not isinstance(n, int) or not 1 <= n <= 255:
        fail("%s: 로케이션 %r 의 번호 %r 가 1 ~ 255 밖입니다", fname, loc, n)
    return n


def _unit_arg(unit, fname):
    u = unProxy(unit)
    if isinstance(u, str):
        return u  # 이름은 CreateUnit 이 맵을 불러온 뒤 번호로 바꾼다
    return _num(u, fname, "unit", 0, 65535)


def _owner_arg(owner, fname):
    o = unProxy(owner)
    if isinstance(o, str):
        fail("%s: owner 는 P1~P12·CurrentPlayer 같은 eudplib 상수, 번호(0~26) 또는 변수여야 합니다 (%r)", fname, owner)
    if isinstance(o, (int, bool)) or _compat.is_var(o) or _compat.is_varbase(o):
        return _num(o, fname, "owner", 0, 26)
    o = EncodePlayer(o)
    return _num(o, fname, "owner", 0, 26)


def _s32(v):
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v


def _call_hook(fn, pt):
    if _compat.is_eudfunc(fn):
        fn()  # 인자 없는 EUDFunc — 본문에서 Plotter.pt 를 쓴다
    else:
        fn(pt)


# =============================================================================================
# 상태 없는 부품 (spawn 이 여러 작업에 쓴다 — S1 11-4)
# =============================================================================================


def _out(values, ret):
    """두 값 결과: ret 가 있으면 그 변수에 넣고, 없으면 그대로(상수는 파이썬 정수)."""
    if ret is None:
        return tuple(values)
    ret = [unProxy(r) for r in ret]
    if len(ret) != len(values):
        fail("plot: ret 은 변수 %d개의 목록이어야 합니다 (%r)", len(values), ret)
    pairs = []
    for r, v in zip(ret, values):
        if r is v:
            continue
        pairs.append((r, SetTo, (v & M32) if isinstance(v, int) else v))
    if pairs:
        SeqCompute(pairs)
    return tuple(ret)


def f_read_point(shapes, sid, i, *, ret=None):
    """도형 sid 의 i 번째 점 (x, y) — `ShapeSet.point_at` 과 같다(plot 쪽 이름, DESIGN 4.13).

    인자: shapes(ShapeSet), sid, i(0부터, 상수·변수), ret([x, y] 변수)
    반환: (x, y) — 모두 상수면 파이썬 정수
    비용: `ShapeSet.point_at` ("db" 실행 약 40, 변수 sid 는 주소표 읽기 +44)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const x, y = plot.read_point(shapes, sid, i);`
    출처: S1 11-4, CAPI:327~328
    """
    if not isinstance(shapes, ShapeSet):
        fail("plot.read_point: shapes 는 ShapeSet 이어야 합니다 (%r)", shapes)
    return shapes.point_at(sid, i, ret=ret)


def f_read_from(shapes, start, i, *, ret=None):
    """`shapes.lookup(sid)` 로 받아 둔 start 에서 i 번째 점 — 점마다 부르는 곳의 빠른 판.

    인자: shapes(ShapeSet), start(첫 점 커서 — 상수식·변수), i(0부터, 점 수보다 작아야 한다), ret([x, y])
    반환: (x, y) EUDVariable
    비용: `ShapeSet.point_from` ("db" 실행 약 42, "varray" 약 29 — 변수 i 곱 포함)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const x, y = plot.read_from(shapes, st, i);`
    출처: S1 11-4 (스케줄 포인터·시작 주소는 호출자가 가진다)
    """
    if not isinstance(shapes, ShapeSet):
        fail("plot.read_from: shapes 는 ShapeSet 이어야 합니다 (%r)", shapes)
    return shapes.point_from(start, i, ret=ret)


def _ratio_axis(v, mul, div, fname):
    if mul is None and div is None:
        return v
    if div is not None:
        d = unProxy(div)
        if isinstance(d, int) and not isinstance(d, bool) and d == 0:
            fail("%s: 상수 0 으로 나눌 수 없습니다 (CtrigAsm CiDiv(X, 0) 의 ±1 은 따르지 않는다)", fname)
    if div is None:
        m = _num(mul, fname, "mul")
        if isinstance(v, int) and isinstance(m, int):
            return _s32(v * m)
        if isinstance(v, int):
            v, m = m, v
        r = v * m  # 32비트 wrap (부호 있는 곱과 아래 32비트가 같다)
        return r
    if mul is None:
        return mathx.sdiv(v, div, div0="ctrig")
    return mathx.ratio(v, mul, div, div0="ctrig")


def f_ratio(x, y, mx=None, dx=None, my=None, dy=None, *, ret=None):
    """CtrigAsm `CA_RatioXY(mX, dX, mY, dY)`: x' = x·mX ÷ dX, y' = y·mY ÷ dY (곱은 32비트 wrap, 나눗셈은 0 방향 부호 나눗셈).

    인자: x, y(부호 있는 32비트, 상수·변수), mx/dx/my/dy(None = 그 단계 생략, 상수·변수. 변수 제수 0 은 CtrigAsm f_iDiv 처럼
          몫 0x7FFFFFFF/0x80000000 — mathx div0="ctrig". 상수 0 은 빌드 오류), ret([x', y'] 변수)
    반환: (x', y') — 모두 상수면 파이썬 정수
    비용: 축마다 mathx.ratio(상수 곱·상수 몫 실행 약 75) 또는 곱만(eudplib)/몫만(mathx.sdiv)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const x2, y2 = plot.ratio(x, y, 3, 2, 1, 1);`
    출처: CB Paint CA_RatioXY(CBP:9718~9751), S1 6.3-1
    """
    fname = "plot.ratio"
    xv = _num(x, fname, "x")
    yv = _num(y, fname, "y")
    return _out((_ratio_axis(xv, mx, dx, fname), _ratio_axis(yv, my, dy, fname)), ret)


def f_move(x, y, dx=0, dy=0, *, ret=None):
    """CtrigAsm `CA_MoveXY(X, Y)`: (x + dx, y + dy) (32비트 wrap).

    인자: x, y, dx, dy(상수·변수), ret([x', y'] — x·y 자신을 주면 제자리 더하기)
    반환: (x', y') — 모두 상수면 파이썬 정수
    비용: 호출 2 / 실행 5 (변수 넷)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const x2, y2 = plot.move(x, y, 5, -3);`
    출처: CB Paint CA_MoveXY(CBP:9687)
    """
    fname = "plot.move"
    xv, yv = _num(x, fname, "x"), _num(y, fname, "y")
    dxv, dyv = _num(dx, fname, "dx"), _num(dy, fname, "dy")
    if ret is not None:
        rx, ry = (unProxy(r) for r in ret)
        pairs = []
        for r, v, d in ((rx, xv, dxv), (ry, yv, dyv)):
            if isinstance(v, int) and isinstance(d, int):
                pairs.append((r, SetTo, (v + d) & M32))
                continue
            if r is not v:
                pairs.append((r, SetTo, v))
            if not (isinstance(d, int) and d == 0):
                pairs.append((r, Add, d & M32 if isinstance(d, int) else d))
        if pairs:
            SeqCompute(pairs)
        return rx, ry
    out = []
    for v, d in ((xv, dxv), (yv, dyv)):
        if isinstance(v, int) and isinstance(d, int):
            out.append(_s32(v + d))
        else:
            out.append(v + d)
    return tuple(out)


def f_rotate(x, y, angle, cycle=360, precise=False, *, ret=None):
    """CtrigAsm `CA_Rotate(θ)`: x' = lx.cos − ly.sin, y' = lx.sin + ly.cos (항별 자르기, 0° = +x, 양의 각 = 화면 시계 방향).

    인자: x, y, angle(상수·변수, Cycle 단위), cycle(기본 360), precise(LengthdirX 고정밀 표), ret
    반환: (x', y') — 모두 상수면 파이썬 정수
    비용: `mathx.Rotator` (상수 각 실행 76, 변수 각 89 + 각이 바뀐 첫 점 213~240)
    CP: 바꾸지 않음 / 로컬: 공유 안전
    epScript: `const x2, y2 = plot.rotate(x, y, ang);`
    출처: CB Paint CA_Rotate(CBP:9865~9881), mathx.Rotator(WP9), 각도 기준은 모듈 설명(D5)
    """
    rot = mathx.Rotator(angle, cycle, precise)
    return rot(x, y, ret=None if ret is None else [unProxy(r) for r in ret])


def f_rotate3d(x, y, xy=None, yz=None, zx=None, cycle=360, precise=False, *, ret=None):
    """CtrigAsm `CA_Rotate3D(XY, YZ, ZX)` — `mathx.rotate3d` 와 같다(평면별 회전, 각이 None 인 단계는 건너뜀).

    인자: x, y, xy/yz/zx(각, 상수·변수·None), cycle, precise, ret([X, Y, Z])
    반환: (X, Y, Z) — 모두 상수면 파이썬 정수
    비용: mathx.rotate3d (실행 약 174~1,440 — 각 준비 포함)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const X, Y, Z = plot.rotate3d(x, y, 30);`
    출처: CB Paint CA_Rotate3D(CBP:9883~9932), mathx(WP9)
    """
    return mathx.rotate3d(x, y, xy, yz, zx, cycle=cycle, precise=precise,
                          ret=None if ret is None else [unProxy(r) for r in ret])


def f_inside(x, y, x1=None, x2=None, y1=None, y2=None):
    """`CA_CropXY` 의 반대: x1 < x < x2 이고 y1 < y < y2 (부호 있음, None 인 쪽은 검사하지 않음) — 남기는 점의 조건.

    반환: 조건 목록(AND). 모두 None 이면 빈 목록. 앞 계산은 부르는 순간 낸다(cmp 규칙).
    비용: 경계 하나마다 cmp 부호 있는 비교(상수 0~1 트리거, 변수 실행 3)
    CP: 바꾸지 않음 / 로컬: 공유 안전
    epScript: `if (plot.inside(x, y, -100, 100, -100, 100)) { … }`
    출처: CB Paint CA_CropXY(CBP:9934~10016)
    """
    conds = []
    for v, lo, hi in ((x, x1, x2), (y, y1, y2)):
        if lo is not None:
            c = cmp.sgt(v, lo)
            conds.extend(c if isinstance(c, list) else [c])
        if hi is not None:
            c = cmp.slt(v, hi)
            conds.extend(c if isinstance(c, list) else [c])
    return conds


@functools.lru_cache(maxsize=None)
def _loc_center_fn():
    @EUDFunc
    def lc(epd):
        left = f_dwread_epd(epd)
        epd += 1
        top = f_dwread_epd(epd)
        epd += 1
        left += f_dwread_epd(epd)
        epd += 1
        top += f_dwread_epd(epd)
        x = mathx.sdiv(left, 2)
        y = mathx.sdiv(top, 2)
        return x, y

    return lc


def f_loc_center(loc, *, ret=None):
    """로케이션 중심 ((L+R)/2, (T+B)/2) — 0 방향 부호 나눗셈(CAPI:307~315 `_iDiv(_Add(L,R),2)`).

    인자: loc(이름 또는 1부터 번호 — 상수 또는 번호 변수), ret([x, y])
    반환: (x, y) EUDVariable
    비용: 본문 13(1벌, 읽기·나눗셈 함수 제외) / 호출 1 / 실행 194
    CP: 바꾸지 않음 / 로컬: 공유 안전
    epScript: `const cx, cy = plot.loc_center("Location 13");`
    출처: CAPI:307~315, S1 8.5-③
    """
    fname = "plot.loc_center"
    lv = unProxy(loc)
    if isinstance(lv, (int, str)) and not isinstance(lv, bool):
        epd = MRGN_EPD + 5 * (_loc_const(lv, fname) - 1)
    else:
        n = _num(lv, fname, "loc", 1, 255)
        epd = n * 5
        epd += MRGN_EPD - 5
    if ret is None:
        return _loc_center_fn()(epd)
    return _loc_center_fn()(epd, ret=[unProxy(r) for r in ret])


def f_setloc_box(loc, x, y, size=0):
    """로케이션을 (x−size, y−size, x+size, y+size) 로 둔다(찍기 한 점).

    인자: loc(이름 또는 1부터 번호 — 상수), x, y(상수·변수), size(0 이상, 상수·변수)
    반환: None
    비용: x·y 변수·size 상수 = 호출 3 / 실행 7, size 변수 +약 5
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `plot.setloc_box(26, x, y, 16);`
    출처: CAPI:343~346, CSPlot(CBP:7061~7067)
    """
    fname = "plot.setloc_box"
    n = _loc_const(loc, fname)
    base = MRGN_EPD + 5 * (n - 1)
    xv, yv = _num(x, fname, "x"), _num(y, fname, "y")
    sv = _num(size, fname, "size", 0, 0x7FFFFFFF)
    if isinstance(xv, int) and isinstance(yv, int) and isinstance(sv, int):
        DoActions([SetMemoryEPD(base + k, SetTo, v & M32)
                   for k, v in enumerate((xv - sv, yv - sv, xv + sv, yv + sv))])
        return
    SeqCompute([(base, SetTo, xv), (base + 1, SetTo, yv), (base + 2, SetTo, xv), (base + 3, SetTo, yv)])
    if isinstance(sv, int):
        if sv:
            DoActions([SetMemoryEPD(base, Add, -sv & M32), SetMemoryEPD(base + 1, Add, -sv & M32),
                       SetMemoryEPD(base + 2, Add, sv), SetMemoryEPD(base + 3, Add, sv)])
        return
    neg = EUDVariable()
    neg << 0
    _parts.isub32(neg, sv)
    SeqCompute([(base, Add, neg), (base + 1, Add, neg), (base + 2, Add, sv), (base + 3, Add, sv)])


_create_building = [False]
_create_fns = {}


def _create_shape_fn(shapes, loc, props):
    key = (id(shapes), loc, id(props))
    hit = _create_fns.get(key)
    if hit is not None:
        return hit[0]
    base = MRGN_EPD + 5 * (loc - 1)

    @EUDFunc
    def cs(sid, unit, owner, cx, cy, count, size):
        cur, n = shapes.lookup(sid)[:2]
        neg = EUDVariable()
        neg << 0
        _parts.isub32(neg, size)
        px, py = EUDVariable(), EUDVariable()
        if EUDWhile()(n.AtLeast(1)):
            shapes.read_at(cur, ret=[px, py])
            SeqCompute([(px, Add, cx), (py, Add, cy)])
            SeqCompute([(base, SetTo, px), (base + 1, SetTo, py), (base + 2, SetTo, px), (base + 3, SetTo, py)])
            SeqCompute([(base, Add, neg), (base + 1, Add, neg), (base + 2, Add, size), (base + 3, Add, size)])
            if props is None:
                DoActions(CreateUnit(count, unit, loc, owner))
            else:
                DoActions(CreateUnitWithProperties(count, unit, loc, owner, props))
            DoActions([cur.AddNumber(shapes.step), n.SubtractNumber(1)])
        EUDEndWhile()

    _create_fns[key] = (cs, shapes, props)  # 객체를 붙잡아 id 가 재사용되지 않게
    return cs


def f_create_shape(shapes, shape, unit, loc, owner, center="loc", size=0, count=1, props=None):
    """도형 하나를 **지금** 모두 찍는다 — 정적 `CSPlot` 류의 루프판(units.CreateUnitShape 자리, DESIGN 4.13).

    인자: shapes(ShapeSet), shape(sid 또는 Shape), unit(이름·번호·변수), loc(찍기 로케이션 — 이름 또는 1부터 번호, 상수),
          owner(플레이어·변수), center("loc" = loc 의 지금 중심 | 다른 로케이션 | (x, y)), size(로케이션 반폭),
          count(점마다 마릿수), props(UnitProperty — 주면 CreateUnitWithProperties)
    반환: None
    비용: 본문 18((shapes, loc, props) 마다 1벌) / 호출 약 19 (+ 중심 읽기) / 실행 점마다 약 80 + 주소표 127
          (37점 3,021. CSPlot 은 1,700점에 243 트리거·583KB — 여기는 도형 수·점 수와 무관)
    CP: 바꾸지 않음 / 로컬: 공유 안전
    epScript: `plot.create_shape(shapes, 0, "Zerg Scourge", 26, P1, center=list(2048, 2048));`
    출처: CB Paint CSPlot(CBP:7023~7120), R4b B5
    """
    fname = "plot.create_shape"
    if not isinstance(shapes, ShapeSet):
        fail("%s: shapes 는 ShapeSet 이어야 합니다 (%r)", fname, shapes)
    if _create_building[0]:
        fail("%s: create_shape 본문을 만드는 중에 다시 불렀습니다 (재진입 금지)", fname)
    n = _loc_const(loc, fname)
    sid = shapes._sid(shape, fname)
    cx, cy = _resolve_center(center, n, fname)
    u = _unit_arg(unit, fname)
    if isinstance(u, str):
        u = EncodeUnit(u)
    args = (sid, u, _owner_arg(owner, fname), cx, cy,
            _num(count, fname, "count", 0, 255), _num(size, fname, "size", 0, 0x7FFFFFFF))
    fn = _create_shape_fn(shapes, n, props)
    _create_building[0] = True
    try:
        fn(*args)
    finally:
        _create_building[0] = False


def _resolve_center(center, own_loc, fname):
    """center → (cx, cy): 상수·변수. "loc"/None = own_loc 의 지금 중심."""
    c = unProxy(center)
    if c is None or (isinstance(c, str) and c == "loc"):
        return f_loc_center(own_loc)
    if isinstance(c, (list, tuple)):
        if len(c) != 2:
            fail("%s: center 는 (x, y) 두 값이어야 합니다 (%r)", fname, center)
        return _num(c[0], fname, "center x"), _num(c[1], fname, "center y")
    if isinstance(c, (str, int)) and not isinstance(c, bool):
        return f_loc_center(c)
    if _compat.is_var(c) or _compat.is_varbase(c):
        return f_loc_center(c)
    fail("%s: center 는 \"loc\", 로케이션(이름·1부터 번호) 또는 (x, y) 여야 합니다 (%r)", fname, center)


read_point = f_read_point
read_from = f_read_from
ratio = f_ratio
move = f_move
rotate = f_rotate
rotate3d = f_rotate3d
inside = f_inside
loc_center = f_loc_center
setloc_box = f_setloc_box
create_shape = f_create_shape


# =============================================================================================
# Point — on_point / each() 의 현재 점
# =============================================================================================


class Point:
    """찍는 중인 점. `on_point` 콜백과 `each()` 가 준다(같은 객체를 되풀이해 준다 — 빌드 시점 객체).

    속성: `x`, `y`(부호 있는 32비트 EUDVariable — 읽기·대입·`+=` 가능, 중심을 더하기 전 도형 좌표),
          `z`(rotate3d 뒤의 z), `index`(점 번호 p, 읽기 전용), `shape`(sid), `center`((cx, cy)),
          `unit`(Plotter(capture=True) 일 때 units.Capture — on_created 에서 씀)
    메서드: `rotate(angle, cycle=360, precise=False)`(CA_Rotate), `rotate3d(xy, yz, zx, …)`(CA_Rotate3D),
            `move(dx, dy)`(CA_MoveXY), `ratio(mx, dx, my, dy)`(CA_RatioXY), `crop(x1, x2, y1, y2)`(CA_CropXY),
            `skip()`(이 점은 만들지 않고 번호만 넘김 — CB[10])
    비용: 메서드마다 해당 부품(`plot.rotate` 등)의 비용. skip/crop 을 한 번이라도 쓰면 점마다 +1 (건너뛰기 검사)
    CP: 바꾸지 않음 / 로컬: 공유 안전
    epScript: `foreach (pt : pl.each()) { pt.rotate(ang); pt.x += 5; if (pt.x > 200) pt.skip(); }`
    출처: CB Paint CA_ 실시간 편집 함수(CBP:9658~10060), CAPI CA[8]·CA[9]·CB[10]
    """

    __slots__ = ("_plot", "_x", "_y", "_z", "unit")

    def __init__(self, plot):
        self._plot = plot
        self._x = EUDVariable()
        self._y = EUDVariable()
        self._z = None
        self.unit = None

    def __repr__(self):
        return "<plot.Point of %r>" % (self._plot,)

    def _check(self, what):
        phase = self._plot._phase
        if phase == "created":
            fail("plot.Point.%s: on_created 콜백에서는 쓸 수 없습니다 (유닛을 이미 만들었다 — on_point/each() 본문에서 부른다)", what)
        if phase != "body":
            fail("plot.Point.%s: on_point/each() 본문 밖에서 불렀습니다", what)

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        if unProxy(value) is self._x:  # epScript `pt.x += v` 의 되쓰기
            return
        self._x << value

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        if unProxy(value) is self._y:
            return
        self._y << value

    @property
    def z(self):
        if self._z is None:
            self._z = EUDVariable()
        return self._z

    @property
    def index(self):
        return self._plot._p

    @property
    def shape(self):
        return self._plot._sid

    @property
    def center(self):
        return self._plot._cx, self._plot._cy

    def rotate(self, angle, cycle=360, precise=False):
        """CA_Rotate — 점을 angle 만큼 돌린다(0° = +x 기준 각 단위, 양의 각 = 시계 방향). 비용: `plot.rotate`."""
        self._check("rotate")
        f_rotate(self._x, self._y, angle, cycle, precise, ret=[self._x, self._y])
        return self

    def rotate3d(self, xy=None, yz=None, zx=None, cycle=360, precise=False):
        """CA_Rotate3D — (x, y) 를 돌리고 z 는 `pt.z` 에 둔다. 비용: `plot.rotate3d`."""
        self._check("rotate3d")
        f_rotate3d(self._x, self._y, xy, yz, zx, cycle, precise, ret=[self._x, self._y, self.z])
        return self

    def move(self, dx=0, dy=0):
        """CA_MoveXY — x += dx, y += dy. 비용: 트리거 1."""
        self._check("move")
        f_move(self._x, self._y, dx, dy, ret=[self._x, self._y])
        return self

    def ratio(self, mx=None, dx=None, my=None, dy=None):
        """CA_RatioXY — x = x·mx ÷ dx, y = y·my ÷ dy (None 인 단계는 생략). 비용: `plot.ratio`."""
        self._check("ratio")
        fname = "plot.Point.ratio"
        xr = _ratio_axis(self._x, mx, dx, fname)
        yr = _ratio_axis(self._y, my, dy, fname)
        _out((xr, yr), [self._x, self._y])
        return self

    def skip(self):
        """이 점은 만들지 않는다(번호는 넘어간다). 조건 블록 안에서 부른다. 비용: 액션 1(+ 점마다 검사 1)."""
        self._check("skip")
        self._plot._skip_used = True
        DoActions(self._plot._skip.SetNumber(1))

    def crop(self, x1=None, x2=None, y1=None, y2=None):
        """CA_CropXY — x ≤ x1, x ≥ x2, y ≤ y1, y ≥ y2 (부호 있음) 이면 건너뛴다. None 인 경계는 보지 않는다.

        비용: 경계마다 조건 트리거 1(+ cmp 앞 계산). 출처: CBP:9934~10016
        """
        self._check("crop")
        pl = self._plot
        pl._skip_used = True
        for v, lo, hi in ((self._x, x1, x2), (self._y, y1, y2)):
            if lo is not None:
                RawTrigger(conditions=cmp.sle(v, lo), actions=pl._skip.SetNumber(1))
            if hi is not None:
                RawTrigger(conditions=cmp.sge(v, hi), actions=pl._skip.SetNumber(1))
        return self


# =============================================================================================
# Plotter
# =============================================================================================


class Plotter:
    """도형 찍기 작업 하나(CAPlot/CBPlot 대체). 한 번에 한 도형을 찍는다.

    인자: shapes(ShapeSet 또는 Shape 목록), unit(이름·번호·변수), owner(플레이어·변수),
          loc(찍기 로케이션 — 이름 또는 1부터 번호, 상수. 점마다 옮겨지고 되돌리지 않는다),
          per_tick(사이클당 점 수 — 1 이상 상수·변수 또는 "all". 도형에 스케줄이 있으면 그것을 쓴다. 변수가 0 이면
                   아무것도 찍지 않고 찍는 중으로 남는다 — CAPlot 과 같음),
          delay(사이클 간격 프레임 — 0·1 = 매 프레임, k = k 프레임마다. 상수·변수), size(로케이션 반폭, 상수·변수),
          repeat(True = 끝나면 처음부터 다시 — stop() 까지. 점이 없는 도형이면 아무것도 찍지 않고 계속 찍는 중),
          count(점마다 마릿수, CreateUnit 수량),
          props(UnitProperty → CreateUnitWithProperties), capture(True = 점마다 units.Capture 로 잡아 `pt.unit` 에 둔다,
          점마다 실행 +24), on_point(콜백 — 데코레이터 대신 줄 때), name(표시용)
    메서드: `start(shape=0, center="loc")`, `set_center(center)`, `stop()`, `tick()`, `each()`, `on_point(fn)`,
            `on_created(fn)`
    속성(조건): `busy`, `done` / (변수) `index`(다음 점 번호), `count_var`(점 수), `shape`(sid), `pt`(Point),
            `interrupted`(찍는 중에 start() 가 불린 횟수)
    비용: 본문(tick 서브루틴) 약 29 + 점 읽기 공유 본문 35 / tick 호출 1 / 빈 프레임 실행 4.
          찍는 사이클 = 머리 약 21(스케줄 있으면 +약 45) + **점마다 53("db"), 22("varray")**. size 변수 +1/점·+4/사이클,
          count 변수 +14/점, unit·owner 변수 +2~3/점, capture +21/점, pt.rotate(변수 각) +약 100/점
          (docs/COSTS.md "plot (WP7)"). 트리거 수는 도형 수·점 수와 무관(시험 확인).
          변수 15개(Point 포함, 1,080B) + 1바이트 칸 3개. start(): 상수 sid·상수 중심 호출 3 / 실행 3,
          변수 sid 실행 134, 중심이 로케이션이면 +약 195
    CP: 바꾸지 않음
    로컬: 공유 안전 (찍기는 모든 클라이언트에서 같은 조건으로)
    epScript: `const pl = plot.Plotter(shapes, unit="Zerg Scourge", owner=P1, loc=26, per_tick=4);` →
              `pl.start(0, center=list(2048, 2048));` → `foreach (pt : pl.each()) { … }` → `if (pl.done) …`
    출처: theSeed CAPlotIndexed.lua(CAPI:216~411), CB Paint CBPlot(CBP:15068~15420), S1 6.2
    """

    def __init__(self, shapes, unit, owner, loc, per_tick=1, delay=1, size=0, repeat=False, count=1,
                 props=None, capture=False, on_point=None, name=None):
        fname = "plot.Plotter"
        if isinstance(shapes, (list, tuple)):
            shapes = ShapeSet(shapes)
        if not isinstance(shapes, ShapeSet):
            fail("%s: shapes 는 ShapeSet(또는 Shape 목록)이어야 합니다 (%r)", fname, shapes)
        self.shapes = shapes
        self.name = name or "plot%d" % id(self)
        self._loc = _loc_check(loc, fname)
        self._unit = _unit_arg(unit, fname)
        self._owner = _owner_arg(owner, fname)
        pt_ = unProxy(per_tick)
        if isinstance(pt_, str):
            check_choice(fname + " per_tick", pt_, (PER_TICK_ALL,))
            self._per_tick = M32
        else:
            self._per_tick = _num(pt_, fname, "per_tick", 1, M32)
        self._delay = _num(delay, fname, "delay", 0, M32)
        self._size = _num(size, fname, "size", 0, 0x7FFFFFFF)
        self._count = _num(count, fname, "count", 0, 255)
        if not isinstance(repeat, bool):
            fail("%s: repeat 는 True/False 여야 합니다 (%r)", fname, repeat)
        if not isinstance(capture, bool):
            fail("%s: capture 는 True/False 여야 합니다 (%r)", fname, capture)
        self.repeat = repeat
        self.capture = capture
        self.props = props
        # 상태
        self._sid = EUDVariable()
        self._start = EUDVariable()
        self._cur = EUDVariable()
        self._n = EUDVariable()
        self._p = EUDVariable()
        self._w = EUDVariable()
        self._left = EUDVariable()
        self._lim = EUDVariable()
        self._sched = EUDVariable()
        self._sptr = EUDVariable()
        self._nb = EUDVariable()
        self._cx = EUDVariable()
        self._cy = EUDVariable()
        self._active = EUDLightVariable()
        self._skip = EUDLightVariable()
        self._interrupted = EUDLightVariable()
        self._neg_size = None
        self.pt = Point(self)
        self._point_hooks = []
        self._created_hooks = []
        self._sub = None
        self._frames = 0
        self._in_body = False
        self._phase = None
        self._reentry = False
        self._skip_used = False
        self._sealed = False
        if on_point is not None:
            self.on_point(on_point)

    def __repr__(self):
        return "<plot.Plotter %s loc=%s>" % (self.name, self._loc)

    @property
    def loc(self):
        """찍기 로케이션 번호(1부터). 이름으로 만들었으면 맵을 불러온 뒤에 읽는다."""
        return _loc_const(self._loc, "plot.Plotter")

    # --- 등록 ---
    def on_point(self, fn):
        """점마다 생성 직전에 부를 콜백 `fn(pt)` 을 등록한다(데코레이터로 써도 된다). 인자 없는 EUDFunc 도 된다
        (본문에서 `pl.pt` 를 쓴다). epScript 는 함수 이름을 값으로 넘길 수 없으므로 `each()` 를 쓴다.

        tick() 을 처음 부르기 전에 등록해야 한다. 반환: fn
        """
        if self._sealed:
            fail("plot.Plotter.on_point: tick()/each() 로 본문을 만든 뒤에는 콜백을 더할 수 없습니다")
        if not callable(fn):
            fail("plot.Plotter.on_point: 부를 수 있는 것이어야 합니다 (%r)", fn)
        self._point_hooks.append(fn)
        return fn

    def on_created(self, fn):
        """점마다 생성 직후(건너뛴 점 제외)에 부를 콜백 `fn(pt)`. capture=True 면 `pt.unit.ok`/`pt.unit.epd` 를 쓸 수 있다."""
        if self._sealed:
            fail("plot.Plotter.on_created: tick()/each() 로 본문을 만든 뒤에는 콜백을 더할 수 없습니다")
        if not callable(fn):
            fail("plot.Plotter.on_created: 부를 수 있는 것이어야 합니다 (%r)", fn)
        self._created_hooks.append(fn)
        return fn

    # --- 조건·값 ---
    @property
    def busy(self):
        """조건: 찍는 중(repeat 면 stop() 전까지 계속 참). 읽을 때마다 새 조건."""
        return self._active.Exactly(1)

    @property
    def done(self):
        """조건: 찍지 않는 중(처음·끝·stop 뒤)."""
        return self._active.Exactly(0)

    @property
    def index(self):
        return self._p

    @property
    def count_var(self):
        return self._n

    @property
    def shape(self):
        return self._sid

    @property
    def interrupted(self):
        return self._interrupted

    # --- 제어 ---
    def start(self, shape=0, center="loc"):
        """도형 shape 를 center 에 찍기 시작한다(찍는 중이면 끊고 새로 — `interrupted` += 1).

        인자: shape(sid 상수·변수 또는 Shape — Shape 면 shapes 에 넣는다),
              center("loc" = 이 Plotter 의 로케이션 **지금** 중심 | 다른 로케이션 이름·1부터 번호(상수·번호 변수) | (x, y))
        반환: None
        비용: 상수 sid·(x, y) 중심 = 호출 3 / 실행 3. 변수 sid = 실행 134(주소표 읽기, 스케줄이 있으면 밴드 수 읽기 +40).
              로케이션 중심 = +약 195
        CP: 바꾸지 않음 / 로컬: 공유 안전
        epScript: `pl.start(1, center=list(x, y));`
        출처: CAPI Preset·ptr 되돌리기(CAPI:219~260)
        """
        fname = "plot.Plotter.start"
        if self._in_body:
            warn("%s: on_point/each() 본문 안에서 start() 를 불렀습니다 — 다음 점부터 새 도형이 섞입니다", fname)
        sid = self.shapes._sid(shape, fname)
        cx, cy = _resolve_center(center, self.loc, fname)
        RawTrigger(conditions=self._active.Exactly(1), actions=self._interrupted.AddNumber(1))
        pairs = []
        if isinstance(sid, int):
            st, n, sc = self.shapes.lookup(sid)
            nb = 0 if isinstance(sc, int) else len(self.shapes[sid].schedule)
            pairs += [(self._sid, SetTo, sid), (self._start, SetTo, st), (self._cur, SetTo, st),
                      (self._n, SetTo, n), (self._sched, SetTo, sc), (self._nb, SetTo, nb)]
        else:
            self.shapes.lookup(sid, ret=[self._start, self._n, self._sched])
            if EUDIf()(self._sched.AtLeast(1)):
                f_dwread_epd(self._sched, ret=[self._nb])
            EUDEndIf()
            pairs += [(self._sid, SetTo, sid), (self._cur, SetTo, self._start)]
        pairs += [(self._p, SetTo, 0), (self._w, SetTo, 0), (self._sptr, SetTo, 1)]
        for dst, v in ((self._cx, cx), (self._cy, cy)):
            pairs.append((dst, SetTo, (v & M32) if isinstance(v, int) else v))
        SeqCompute(pairs)
        DoActions([self._active.SetNumber(1), self._skip.SetNumber(0)])

    def set_center(self, center):
        """찍는 중에 중심만 바꾼다(다음 점부터). 인자는 start 의 center 와 같다. epScript: `pl.set_center(list(x, y));`"""
        cx, cy = _resolve_center(center, self.loc, "plot.Plotter.set_center")
        SeqCompute([(self._cx, SetTo, (cx & M32) if isinstance(cx, int) else cx),
                    (self._cy, SetTo, (cy & M32) if isinstance(cy, int) else cy)])

    def stop(self):
        """찍기를 멈춘다(done 이 참). 비용: 트리거 1. epScript: `pl.stop();`"""
        DoActions(self._active.SetNumber(0))

    # --- 본문 ---
    def _emit_create(self):
        loc = self.loc
        base = MRGN_EPD + 5 * (loc - 1)
        px, py = self.pt._x, self.pt._y
        SeqCompute([(px, Add, self._cx), (py, Add, self._cy)])
        SeqCompute([(base, SetTo, px), (base + 1, SetTo, py), (base + 2, SetTo, px), (base + 3, SetTo, py)])
        s = self._size
        if isinstance(s, int):
            if s:
                DoActions([SetMemoryEPD(base, Add, -s & M32), SetMemoryEPD(base + 1, Add, -s & M32),
                           SetMemoryEPD(base + 2, Add, s), SetMemoryEPD(base + 3, Add, s)])
        else:
            neg = self._neg_size  # 사이클 머리에서 −size 로 채워 둔다
            SeqCompute([(base, Add, neg), (base + 1, Add, neg), (base + 2, Add, s), (base + 3, Add, s)])
        if self.capture:
            self.pt.unit = units.f_create(self._count, self._unit, loc, self._owner, props=self.props, into=self.pt.unit)
        elif self.props is None:
            DoActions(CreateUnit(self._count, self._unit, loc, self._owner))
        else:
            DoActions(CreateUnitWithProperties(self._count, self._unit, loc, self._owner, self.props))
        if self._created_hooks:
            self._in_body = True  # 재진입 검사는 생성 뒤 콜백에도 걸린다
            self._phase = "created"
            try:
                for fn in self._created_hooks:
                    _call_hook(fn, self.pt)
            finally:
                self._in_body = False
                self._phase = None

    def _frame(self):
        """한 프레임 코드(모듈 설명의 의사코드). 점마다 self.pt 를 한 번 내준다.

        재진입(본문 안에서 같은 Plotter 의 루프를 또 만들기)은 여기서 오류를 내지 않고 표시만 한다 — 열린 블록·트리거 범위를
        깨지 않게, 바깥 루프를 다 만든 뒤 `tick()`/`each()` 가 오류를 낸다.
        """
        if self._in_body:
            self._reentry = True
            return
        self._frames += 1
        if self._frames > 1:
            warn("plot.Plotter %s: 찍기 루프를 %d 곳에 만들었습니다 — 모두 실행되면 프레임마다 여러 사이클이 돈다",
                 self.name, self._frames)
        self._sealed = True
        if self.capture and self.pt.unit is None:
            self.pt.unit = units.Capture()
        shapes = self.shapes
        pt = self.pt
        if EUDIf()([self._active.Exactly(1), self._w.Exactly(0)]):
            # 이번 사이클 점 수
            if EUDIf()(self._sched.AtLeast(1)):
                band = self._sched + self._sptr
                f_dwread_epd(band, ret=[self._lim])
                RawTrigger(conditions=cmp.gt(self._nb, self._sptr), actions=self._sptr.AddNumber(1))
            if EUDElse()():
                SeqCompute([(self._lim, SetTo, self._per_tick)])
            EUDEndIf()
            # k = min(L, n − p)  (p ≤ n 이므로 포화 뺄셈이 wrap 과 같다 — DESIGN 3.5-7)
            SeqCompute([(self._left, SetTo, self._n), (self._left, Subtract, self._p)])
            if EUDIf()(cmp.gt(self._left, self._lim)):
                self._left << self._lim
            EUDEndIf()
            if not isinstance(self._size, int):
                if self._neg_size is None:
                    self._neg_size = EUDVariable()
                self._neg_size << 0
                _parts.isub32(self._neg_size, self._size)
            if EUDWhile()(self._left.AtLeast(1)):
                shapes.read_at(self._cur, ret=[pt._x, pt._y])
                self._skip_used = False
                self._in_body = True
                self._phase = "body"
                try:
                    yield pt
                finally:
                    self._in_body = False
                    self._phase = None
                skip_used = self._skip_used
                if skip_used:
                    if EUDIf()(self._skip.Exactly(0)):
                        self._emit_create()
                    EUDEndIf()
                else:
                    self._emit_create()
                EUDSetContinuePoint()
                acts = [self._p.AddNumber(1), self._cur.AddNumber(shapes.step), self._left.SubtractNumber(1)]
                if skip_used:
                    acts.append(self._skip.SetNumber(0))
                DoActions(acts)
            EUDEndWhile()
            SeqCompute([(self._w, SetTo, self._delay)])
            if EUDIf()(cmp.ge(self._p, self._n)):
                if self.repeat:
                    SeqCompute([(self._p, SetTo, 0), (self._sptr, SetTo, 1), (self._cur, SetTo, self._start)])
                else:
                    DoActions(self._active.SetNumber(0))
            EUDEndIf()
            if skip_used:
                DoActions(self._skip.SetNumber(0))  # break 로 빠져나온 경우
        EUDEndIf()
        DoActions(self._w.SubtractNumber(1))  # 포화 (0 에서 멈춤)

    def each(self):
        """이번 프레임의 찍기 루프를 이 자리에 만들고, 점마다 `pt` 를 내준다(본문 = 생성 직전 코드).

        본문 안: `pt.*` 변환, `continue`(EUDContinue — 이 점 건너뛰기), `break`(EUDBreak — 이번 사이클을 멈춘다. 그 점은
        다음 사이클에 다시 나온다). 등록한 on_point 콜백은 부르지 않는다(on_created 는 부른다).
        반환: 생성기 (파이썬 `for pt in pl.each():`, epScript `foreach (pt : pl.each()) { … }`)
        비용: 클래스 설명(찍기 루프 코드 약 45 트리거가 이 자리에 놓인다)
        """
        outer = not self._in_body  # 안쪽(재진입) each() 는 표시만 하고, 바깥 루프가 끝난 뒤 오류를 낸다
        for pt in self._frame():
            yield pt
        if outer:
            self._check_reentry()

    def _check_reentry(self):
        if self._reentry:
            self._reentry = False
            fail("plot.Plotter %s: on_point/each() 본문 안에서 같은 Plotter 의 tick()/each() 를 불렀습니다 (재진입 금지 — DESIGN 3.3)",
                 self.name)

    def tick(self):
        """이번 프레임을 진행한다(on_point 콜백 사용). 본문은 서브루틴 한 벌, 호출 자리 트리거 1.

        반환: None / 비용: 호출 1 + 클래스 설명 / epScript: `pl.tick();` (epScript 는 콜백 대신 each() 를 쓴다)
        """
        if self._in_body:
            self._reentry = True
            return
        if self._sub is None:
            self._sub = _parts.SubLabel(self.name)
            with self._sub.define():
                for pt in self._frame():
                    for fn in self._point_hooks:
                        _call_hook(fn, pt)
            self._check_reentry()
        _parts.call_sub(self._sub)
