"""eudext.spawn — G_CB 식 소환 대기열 (DESIGN 4.14, 정본 명세 docs/spec/S1_gcb.md 8절 — 1단계).

도형(`shape.Shape`)과 유닛을 **작업**으로 넣으면(`push`/`job().layer().push()`), 매 프레임 `tick()` 이 살아 있는 작업마다
이번 프레임 몫의 점을 찍는다. theSeed `Engine/G_CB_Lib.lua`(GCB) + `CAPlotIndexed.lua`(CAPI) 의 의미를 따른다.

    from eudext.spawn import Spawner, Order, Effect, at_unit
    from eudext.shape import CX

    ring = CX(seed=1234).call("CSMakeCircle", 6, 32, 0, 37, 0)
    sp = Spawner(capacity=128, loc="GCB Src", loc2="GCB Dst", default_target="Home")
    sp.rtype("Home", sp.builtin.attack_default)          # RepeatType 은 등록형 (맵마다 번호·뜻이 다르다)
    @sp.rtype("Skill", id=8)
    def _skill(s):                                       # s: SpawnCtx
        s.default_order(Patrol)                          # 명령 속성이 있으면 아무것도 안 함
        s.set_remove_timer(15)
    sp.default_rtype = "Home"

    if EUDIf()(cond):                                    # 조건은 호출 자리의 EUDIf (원본 Condition 인자)
        sp.push(37, ring, owner=P8, lm="max", size=150, rotate=30, order=Order.attack("Boss"))
        sp.job(owner=P8, center=(x, y)).layer(37, ring).layer(38, ring, size=150).push()   # 여러 층
    EUDEndIf()
    sp.tick()                                            # 매 프레임 1회 (push 뒤에 두면 같은 프레임에 첫 사이클)
    sp.spawn_now(37, count=5, at="Boss", rtype="Skill")  # f_TempRepeat 대체 (대기열을 거치지 않음)
    sp.scan_effect(ring, image=429, color=16, center="Boss")   # G_CB_TScanEff 대체
    sp.anchor.x << 3072; sp.rotation += 1; sp.live; sp.overflow; sp.clear()

epScript (`import eudext.spawn as spawn;` — 사슬 API 가 기본형, 모듈 함수는 `spawn.attack(…)` → `spawn.f_attack`):

    const sp = spawn.Spawner(capacity=64, loc="GCB Src", loc2="GCB Dst", default_target="Home");
    function Count(epd, unit, owner, x, y) { made += 1; }          // rtype_func 보다 **앞에** 정의한다
    function onPluginStart() { sp.rtype_func("Home", sp.builtin.attack_default, Count); }
    function afterTriggerExec() {
        if (…) { sp.job(owner=P8, order=spawn.attack("Boss")).layer(37, ring).layer(38, ring, size=150).push(); }
        sp.tick();
    }

## 한 프레임 (tick — S1 6.2 · CAPI:216~411 과 같은 의미)

    for 살아 있는 층 레코드 (할당 순서 = 넣은 순서, 한 작업의 층들은 목록에서 이어져 있다):
        바로 앞 레코드가 "다음 층 있음" 으로 끝났으면 이 레코드(= 그 다음 층)의 w = 2   ← 층 사이 빈 프레임 1개 (D13)
        if w == 0:
            L = 스케줄[포인터] (포인터 < 밴드 수면 +1) 또는 lm;  k = min(L, 남은 점)
            k 번: 점 읽기 → 크기(CiDiv(x·S, 100)) → 회전(CtrigAsm CA_Rotate, 전역 회전은 점마다 sp.rotation)
                  → 평행이동 → 중심 → 경계(X ≤ W−1, Y ≤ H−1 부호 없음) → 안이면 한 기 소환
            w = delay;  남은 점 == 0 이면 완료(반납)
        w = max(w − 1, 0)

- delay 0 과 1 은 둘 다 매 프레임, k(≥2) 는 k 프레임마다 한 사이클. 첫 사이클은 넣은 뒤 첫 tick.
- 층 k 가 프레임 N 에 끝나면 N+1 은 빈 프레임, N+2 에 층 k+1 의 첫 사이클(GCB 3.5, D13 재현). 뒤 층은 그때까지
  w = 0xFFFFFFFF 로 기다린다. "바로 뒤 레코드 = 다음 층" 은 pool 의 순회 규칙(할당 순서, 루프 중 할당은 다음 루프)과
  `alloc_n` 이 층을 차례로 잡는 것에 기댄다(시험: 여러 작업 섞기·압축·핸들러 안의 push).
- lm: "max" = 255, 0 = 자동 `n // 50 + 1`(넣을 때 계산). 도형에 LoopMax 스케줄이 있으면 스케줄이 lm 을 덮는다.
  **스케줄 포인터는 작업마다**(원본은 매 호출 1 로 되돌림 — S1 10-16, 의도된 의미로 구현). 빈 밴드(0) 사이클은 쉰다.
- 경계 밖 점은 건너뛰고 진행으로 친다(원본과 같음). 맵 크기는 chk DIM × 32 또는 `map_size`.
- 넣는 순간 해석: 중심(`None` = 그때의 `sp.anchor`, 로케이션 = 그때의 중심 (L+R)/2·(T+B)/2 0 방향), 명령 목표(같음).
  원본과 달리 로케이션 중심 모드가 anchor 를 **덮어쓰지 않는다**(S1 10-28).
- tick 중에 넣은 작업(핸들러 안의 push)은 다음 tick 부터 돈다(pool 규칙).

## 소환 한 기 (공유 서브루틴 한 벌 — tick 과 spawn_now 가 같이 쓴다)

    loc ← (X, Y, X, Y)
    effect 면: [0x666458 ← 이미지, CreateUnit(33), KillUnit(33, 주인), 0x666458 ← 546] 한 트리거 (색은 사이클마다)
    아니면:  (후처리가 필요한 작업만) units.Capture 시작 → on_create(칸 번호) → CreateUnitWithProperties(energy 100)
             → 생성 성공이면 EUDSwitch(rtype) → 핸들러 → 명령 속성이 있으면 loc ← 유닛 자리 ±1, loc2 ← 목표 ±1,
               Order(유닛, 주인, loc, 종류, loc2)

- 후처리(캡처·핸들러·명령)는 rtype 에 핸들러가 있거나 명령 속성·on_create 가 있을 때만 한다(없으면 점당 실행이 줄어든다).
  생성 성공 판정은 원본의 에너지 검사 대신 `units.Capture`(0x628438 이 바뀌었나).
- 명령은 원본 `TOrder` 처럼 **2×2 상자 안의 같은 종류·같은 주인 유닛 전부**가 받는다(겹친 유닛도 — S1 10-30).
- 기본 명령(`default_order`)의 로케이션 목표는 **명령 순간의** 로케이션이다(원본 DefaultAttackLoc 과 같음).

## 원본과 일부러 다른 것 (S1 8.1 표)

작은 pool 레코드 사슬(층 하나 = 레코드 하나), 넣기는 호출 자리에서 한 번에(원자적 — 층이 모자라면 통째로 버림, 넘침 카운터
`overflow` 는 항상, 문구는 `debug`/`on_full`), 로케이션은 eudplib 규칙 하나(이름 또는 1부터 번호 — S1 10-17·18·19 의
0/1 오프바이원 없음), 전역 회전은 `sp.GLOBAL`(−1 도 각도), 유닛 0 허용, 유닛·도형 수 불일치·점 0개 상수 도형·
등록 안 한 rtype 은 컴파일 오류, 스케줄 포인터 작업별, RepeatType 등록형(`EUDSwitch`), nilunit 가짜 생성 없음,
리버 스캐럽 충전(로케이션 1 고정 — S1 10-21)·EXCC 초기화·theSeed 전용 동작 없음(on_create 훅으로).
받은 도형·목록·속성은 고치지 않는다(S1 10-10).

## 2단계 (자리만 — 쓰면 컴파일 오류)

`rot3d=True`/`sp.rot3d`, `unclickable`, `variant`(프리펑션 변형, D14), `Effect.frag`(기억의 조각), `mirror`(점대칭).

## 재진입 (DESIGN 3.3)

핸들러(소환 서브루틴 본문) 안에서 같은 Spawner 의 `tick()`·`spawn_now()`·`clear()` 를 부르면 빌드 오류다(서브루틴을 다 만든 뒤).
핸들러 안의 `push()`(다음 tick 부터), 다른 Spawner, `bullet`·`units` 함수는 된다. 다만 다른 Spawner 의 핸들러를 거쳐
되돌아오는 호출(A 의 핸들러 → B.tick → B 의 핸들러 → A.spawn_now)은 검사하지 못하므로 쓰지 않는다(작업 레지스터가 덮인다).

출처: theSeed `Engine/G_CB_Lib.lua`(GCB, 2,769줄 — 2026-09-17 판과 같음), `Engine/CAPlotIndexed.lua`(CAPI),
Stella_II `MapLogic/GunFunc.lua`, MSF_MEME_EUD `function.lua`, CB Paint v2.5 `CA_RatioXY`·`CA_Rotate`, S1 1~12절.
"""

import inspect
import weakref

from eudplib import (
    EPD,
    P8,
    Add,
    Attack,
    CreateUnit,
    CreateUnitWithProperties,
    CurrentPlayer,
    DisplayText,
    DoActions,
    EncodeLocation,
    EncodeOrder,
    EncodePlayer,
    EncodeUnit,
    EUDBreak,
    EUDElse,
    EUDEndIf,
    EUDEndSwitch,
    EUDEndWhile,
    EUDIf,
    EUDIfNot,
    EUDLightVariable,
    EUDSwitch,
    EUDSwitchCase,
    EUDSwitchDefault,
    EUDVariable,
    EUDWhile,
    Forward,
    GetChkTokenized,
    KillUnit,
    Move,
    NextTrigger,
    Patrol,
    PlayWAV,
    RawTrigger,
    SeqCompute,
    SetDeathsX,
    SetMemory,
    SetMemoryX,
    SetNextPtr,
    SetTo,
    UnitProperty,
    VProc,
    f_bread_epd,
    f_bwrite_epd,
    f_dwread_epd,
    f_readgen_epd,
    f_setcurpl2cpcache,
    unProxy,
)
from eudplib import Order as _SCOrder

from eudext import _compat, _parts, cmp, mathx, mathx_tables, plot, units
from eudext.errors import check_choice, fail, require, warn
from eudext.pool import Pool
from eudext.shape import Shape, ShapeSet

__all__ = [
    "BUZZ_WAV",
    "GLOBAL",
    "AtUnit",
    "Effect",
    "Job",
    "Order",
    "RType",
    "SpawnCtx",
    "Spawner",
    "at_unit",
    "attack",
    "f_at_unit",
    "f_attack",
    "f_move",
    "f_order",
    "f_patrol",
    "f_scan",
    "move",
    "order",
    "patrol",
    "scan",
]

M32 = 0xFFFFFFFF
CP_ADDR = 0x6509B0
CP_EPD = EPD(CP_ADDR)
MRGN_ADDR = 0x58DC60  # 로케이션 표 (1부터 번호 n → +20·(n−1))
MRGN_EPD = EPD(MRGN_ADDR)
BUZZ_WAV = "sound\\Misc\\Buzz.wav"
INF_WAIT = M32  # 아직 차례가 아닌 층 (40억 프레임 뒤에나 0 이 된다)
LM_MAX = 255
UNIT_MAX = 226  # G_CB Call_Repeat 이 받는 유닛 범위 0 ~ 226 (GCB 699)
UNIT_SCAN = 33  # Scanner Sweep
SCAN_SPRITE_IMAGE = 0x666458  # sprites.dat 이미지(word) 표의 380번(스캐너 스윕) 칸 — GCB 720
SCAN_SPRITE_IMAGE_DEFAULT = 546
DRAW_FUNC = 0x669E28  # images.dat Draw Function(byte) 표 — S1 4.4
DRAW_FUNC_EPD = EPD(DRAW_FUNC)  # 0x669E28 은 4 의 배수라 이미지 i 의 칸 = EPD + i//4, 바이트 i%4

# 레코드 flags 비트
F_GLOBAL = 0x01  # 회전 = sp.rotation (점마다 읽음)
F_NEXT = 0x02  # 뒤에 층이 있다
F_ORDER = 0x0C  # 명령 속성: (SC 명령 번호 + 1) << 2 — 0 = 없음, 1 = Move, 2 = Patrol, 3 = Attack
F_POST = 0x10  # 생성 뒤 처리(캡처·핸들러·명령)가 필요하다
F_EFFECT = 0x20  # 스캔 이펙트 (eff 필드)

# CUnit 오프셋 (바이트, eudplib scdata 이름)
CU_POS = 0x28
CU_TURN_RADIUS = 0x22
CU_TOP_SPEED = 0x34
CU_ACCEL = 0x48
CU_ORDER_ID = 0x4D
CU_STATUS = 0xDC
CU_REMOVE_TIMER = 0x110
CU_PARASITE = 0x121
STATUS_INVINCIBLE = 0x04000000

ACT_CREATE = 44
ACT_CREATE_PROPS = 11
ACT_KILL = 22
ACT_ORDER = 46

FIELDS = "unit! owner! rtype! pc left sp se! w lm! delay! size! rot! flags! cx! cy! dx! dy! ox! oy! eff!"

_KINDS = {"move": 0, "patrol": 1, "attack": 2}


# =============================================================================================
# 인자 도우미
# =============================================================================================


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _num(x, fname, what, lo=-(1 << 31), hi=M32):
    """정수 상수(범위 검사) 또는 EUDVariable. 읽기 전용 값 칸·상수식은 새 변수로."""
    x = unProxy(x)
    if isinstance(x, bool):
        x = int(x)
    if _is_int(x):
        if not lo <= x <= hi:
            fail("%s: %s 상수 %d 가 범위(%d ~ %d) 밖입니다", fname, what, x, lo, hi)
        return x
    if isinstance(x, float):
        fail("%s: %s 에 실수 %r 는 쓸 수 없습니다", fname, what, x)
    if _compat.is_var(x):
        return x
    if _compat.is_varbase(x) or hasattr(x, "getValueAddr"):
        return f_dwread_epd(EPD(x.getValueAddr()))
    if _compat.is_const(x):
        v = EUDVariable()
        v << x
        return v
    fail("%s: %s 로 쓸 수 없는 값입니다 (%r)", fname, what, x)


def _u32(v):
    return v & M32 if _is_int(v) else v


def _s32(v):
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v


def _tdiv(a, b):
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _loc_check(loc, fname, what="로케이션"):
    """이름(문자열 — 맵을 불러온 뒤 번호로) 또는 1부터 번호 상수 (DESIGN 3.9)."""
    loc = unProxy(loc)
    if isinstance(loc, bytes):
        loc = loc.decode("utf-8")
    if isinstance(loc, bool) or not isinstance(loc, (int, str)):
        fail("%s: %s 는 이름 또는 1부터 번호(상수)여야 합니다 (%r)", fname, what, loc)
    if isinstance(loc, int) and not 1 <= loc <= 255:
        fail("%s: %s 번호 %r 는 1 ~ 255 여야 합니다 (0부터 번호는 받지 않는다 — DESIGN 3.9)", fname, what, loc)
    return loc


def _loc_num(loc, fname, what="로케이션"):
    loc = _loc_check(loc, fname, what)
    try:
        n = EncodeLocation(loc)
    except Exception as e:  # noqa: BLE001 — eudplib 이 여러 종류를 낸다
        fail("%s: %s %r 를 맵에서 찾지 못했습니다 (%s)", fname, what, loc, e)
    if not _is_int(n) or not 1 <= n <= 255:
        fail("%s: %s %r 의 번호 %r 가 1 ~ 255 밖입니다", fname, what, loc, n)
    return n


def _unit_arg(unit, fname):
    u = unProxy(unit)
    if isinstance(u, bytes):
        u = u.decode("utf-8")
    if isinstance(u, str):
        try:
            u = EncodeUnit(u)
        except Exception as e:  # noqa: BLE001
            fail("%s: 유닛 이름 %r 를 모릅니다 (%s)", fname, unit, e)
    return _num(u, fname, "unit", 0, UNIT_MAX)


def _owner_arg(owner, fname):
    o = unProxy(owner)
    if isinstance(o, (str, bytes)):
        fail("%s: owner 는 P1~P12 같은 eudplib 상수, 번호(0~11) 또는 변수여야 합니다 (%r)", fname, owner)
    if not (isinstance(o, (int, bool)) or _compat.is_var(o) or _compat.is_varbase(o)):
        o = EncodePlayer(o)
    if _is_int(o) and o == 13:
        fail("%s: owner 에 CurrentPlayer 는 쓸 수 없습니다 — 소환은 tick 안에서 일어나 그때의 CP 가 뜻이 없습니다", fname)
    return _num(o, fname, "owner", 0, 11)


def _order_kind(kind, fname):
    k = unProxy(kind)
    if isinstance(k, bytes):
        k = k.decode("utf-8")
    if isinstance(k, str):
        check_choice(fname + " kind", k.lower(), tuple(_KINDS))
        return _KINDS[k.lower()]
    try:
        v = EncodeOrder(k)
    except Exception:  # noqa: BLE001
        v = None
    if not _is_int(v) or not 0 <= v <= 2:
        fail("%s: 명령 종류는 Attack/Patrol/Move 또는 \"attack\"/\"patrol\"/\"move\" 여야 합니다 (%r)", fname, kind)
    return v


def _call_n_args(fn):
    """파이썬 함수의 필수 위치 인자 수 (EUDFunc 는 _argn)."""
    if _compat.is_eudfunc(fn):
        return getattr(fn, "_argn", 0)
    try:
        return len([p for p in inspect.signature(fn).parameters.values()
                    if p.default is inspect.Parameter.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)])
    except (TypeError, ValueError):
        return 0


def _any_bit(var, mask):
    """var & mask ≠ 0 → 새 조건."""
    return var.AtLeastX(1, mask)


def _bit(var, mask):
    """var 의 mask 비트가 모두 켜짐 → 새 조건."""
    return var.ExactlyX(mask, mask)


def _no_bit(var, mask):
    return var.ExactlyX(0, mask)


# --- 파이썬 계산 (preview·참조와 같은 식 — CtrigAsm CA_Rotate 항별 자르기) ---


def _ld_py(r, a, cycle):
    q = cycle // 4
    t = _s32(a) % cycle
    if t < q:
        cs, ss, si, ci = 0, 0, t, q - t
    elif t < 2 * q:
        cs, ss, si, ci = 1, 0, 2 * q - t, t - q
    elif t < 3 * q:
        cs, ss, si, ci = 1, 1, t - 2 * q, 3 * q - t
    else:
        cs, ss, si, ci = 0, 1, 4 * q - t, t - 3 * q
    tbl = mathx_tables.sin_table(cycle)

    def term(v, tv, flip):
        p = _s32(v * tv)
        d = _tdiv(p, 0x10000)
        return -d if flip else d

    return term(r, tbl[ci], cs), term(r, tbl[si], ss)


def rotate_py(x, y, a, cycle=360):
    """(x, y) 를 CtrigAsm CA_Rotate 로 돌린 부호 있는 (x', y') — preview·시험용 파이썬 계산."""
    xc, xs = _ld_py(x, a, cycle)
    yc, ys = _ld_py(y, a, cycle)
    return _s32(xc - ys), _s32(xs + yc)


def transform_py(x, y, size=100, rotate=0, cycle=360):
    """크기 → 회전 한 점의 부호 있는 좌표 (평행이동·중심 전). rotate 0 = 안 돎."""
    if size != 100:
        x = _tdiv(_s32(x * size), 100)
        y = _tdiv(_s32(y * size), 100)
    if rotate & M32:
        x, y = rotate_py(x, y, rotate, cycle)
    return x, y


# =============================================================================================
# 표식·명세 객체 (컴파일 시점 값)
# =============================================================================================


class _Global:
    """`rotate=sp.GLOBAL` — 회전각을 점마다 `sp.rotation` 에서 읽는다 (원본 `RotateTable="Main"`)."""

    __slots__ = ()
    dont_flatten = True

    def __repr__(self):
        return "spawn.GLOBAL"


GLOBAL = _Global()


class AtUnit:
    """`center=at_unit(epd)` — 넣는 순간 그 유닛이 선 자리(CUnit +0x28)를 중심으로 쓴다."""

    __slots__ = ("epd",)
    dont_flatten = True

    def __init__(self, epd):
        e = unProxy(epd)
        if _is_int(e):
            fail("spawn.at_unit: epd 는 변수여야 합니다 (상수 %d)", e)
        if not (_compat.is_var(e) or _compat.is_varbase(e)):
            fail("spawn.at_unit: epd 는 EUDVariable 이어야 합니다 (%r)", epd)
        self.epd = e

    def __repr__(self):
        return "spawn.at_unit(%r)" % (self.epd,)


def f_at_unit(epd):
    """유닛 자리 중심 표식.

    인자: epd(유닛 EPD 변수 — `units.Capture.epd` 등)
    반환: AtUnit (center=·at=·명령 목표 자리에 넣는다)
    비용: 없음(표식). 해석할 때 위치 읽기 약 30 실행
    CP: 해당 없음
    로컬: 공유 안전
    epScript: `sp.push(37, ring, center=spawn.at_unit(u.epd));`
    출처: S1 8.2 `at_unit(epd)`
    """
    return AtUnit(epd)


at_unit = f_at_unit


class Order:
    """명령 속성 (원본 `Order={Attack|Patrol|Move, X, Y}` / `{…, 로케이션}`).

    만들기: `Order.attack(x, y)` / `Order.attack("Loc")` / `Order.attack(3)`(1부터 번호) / `Order.attack(at_unit(epd))`,
            `Order.patrol(…)`, `Order.move(…)`, `Order("attack", target)`.
    의미: 목표는 **넣는 순간** 좌표로 바뀐다(로케이션이면 그때의 중심). 명령 속성이 있으면 핸들러의 `default_order` 는 아무것도
          안 하고, 핸들러 뒤에 이 명령을 준다(2×2 상자 안의 같은 종류·주인 유닛 전부).
    비용: 없음(값). 넣을 때 로케이션 목표 +약 195, 소환마다 약 42
    CP: 해당 없음
    로컬: 공유 안전
    epScript: 모듈 함수 `spawn.attack(…)`/`spawn.patrol(…)`/`spawn.move(…)` (클래스 메서드 사슬 `spawn.Order.attack` 은 번역되지 않는다)
    출처: GCB 2395~2426, 617~624. 로케이션 이름을 한 칸 앞 번호로 해석하던 원본 오프바이원(S1 10-17)은 없다
    """

    __slots__ = ("kind", "target")
    dont_flatten = True

    def __init__(self, kind, *target):
        self.kind = _order_kind(kind, "spawn.Order")
        if len(target) == 1 and isinstance(unProxy(target[0]), (list, tuple)):
            target = tuple(target[0])
        if len(target) not in (1, 2):
            fail("spawn.Order: 목표는 (x, y), 로케이션, at_unit 중 하나입니다 (%r)", target)
        if len(target) == 1:
            t = unProxy(target[0])
            if isinstance(t, bytes):
                t = t.decode("utf-8")
            if not isinstance(t, AtUnit) and not (_compat.is_var(t) or _compat.is_varbase(t)):
                _loc_check(t, "spawn.Order", "명령 목표 로케이션")
            self.target = t
        else:
            self.target = tuple(target)

    def __repr__(self):
        return "spawn.Order(%s, %r)" % ({0: "move", 1: "patrol", 2: "attack"}[self.kind], self.target)

    @classmethod
    def attack(cls, *target):
        return cls("attack", *target)

    @classmethod
    def patrol(cls, *target):
        return cls("patrol", *target)

    @classmethod
    def move(cls, *target):
        return cls("move", *target)


def f_order(kind, *target):
    """명령 속성을 만든다(`Order(kind, *target)` 와 같음).

    인자: kind("attack"|"patrol"|"move" 또는 Attack/Patrol/Move), target((x, y) 두 값 | 로케이션 | at_unit)
    반환: Order / 비용: 없음 / CP: 해당 없음 / 로컬: 공유 안전
    epScript: `order=spawn.order("attack", "Boss")`
    출처: S1 8.2
    """
    return Order(kind, *target)


def f_attack(*target):
    """어택 명령 속성(`Order.attack`).

    인자: target((x, y) 두 값 | 로케이션 이름·1부터 번호 | 번호 변수 | at_unit)
    반환: Order / 비용: 없음(값) / CP: 해당 없음 / 로컬: 공유 안전
    epScript: `order=spawn.attack("Boss")` / `order=spawn.attack(x, y)` (→ spawn.f_attack)
    출처: GCB Order={Attack, …}
    """
    return Order("attack", *target)


def f_patrol(*target):
    """순찰 명령 속성(`Order.patrol`).

    인자·반환·비용: `f_attack` 과 같음 / CP: 해당 없음 / 로컬: 공유 안전
    epScript: `order=spawn.patrol(3)`
    출처: GCB Order={Patrol, …}
    """
    return Order("patrol", *target)


def f_move(*target):
    """이동 명령 속성(`Order.move`).

    인자·반환·비용: `f_attack` 과 같음 / CP: 해당 없음 / 로컬: 공유 안전
    epScript: `order=spawn.move(x, y)`
    출처: GCB Order={Move, …}
    """
    return Order("move", *target)


order = f_order
attack = f_attack
patrol = f_patrol
move = f_move


class Effect:
    """이펙트 속성. 1단계는 `Effect.scan(image, color=None)`(원본 EffID·EffColor, 유닛 33) 만.

    scan: 점마다 스캐너 스윕(33)의 스프라이트 이미지(sprites.dat 380번 칸 0x666458)를 image 로 바꿔 만들고 곧바로 죽인 뒤
          546 으로 되돌린다(한 트리거, GCB 700~727). color(0~255, images.dat Draw Function 값)를 주면 사이클 동안 image 의
          Draw Function 을 바꿨다가 되돌린다. `KillUnit(33, 주인)` 이라 **그 주인의 스캐너 스윕 전부**가 죽는다(원본과 같음 —
          주인 기본 P8, S1 10-29). rtype·명령은 쓰지 않는다. 유닛은 33 으로 고정.
    frag: 기억의 조각 — 2단계(쓰면 컴파일 오류).
    인자: image(1~65535 상수·변수), color(None | 0~255 상수·변수)
    비용: 사이클마다 약 30(+ 색 약 60), 점마다 트리거 1
    CP: 해당 없음 / 로컬: 공유 안전
    epScript: `effect=spawn.scan(429, color=16)`
    출처: GCB 2115~2150(G_CB_TScanEff), 700~727
    """

    __slots__ = ("color", "image", "kind")
    dont_flatten = True

    def __init__(self, kind, image=0, color=None):
        check_choice("spawn.Effect kind", kind, ("scan",))
        self.kind = kind
        self.image = _num(image, "spawn.Effect", "image", 0, 0xFFFF)
        self.color = None if color is None else _num(color, "spawn.Effect", "color", 0, 255)
        if _is_int(self.image) and self.image == 0:
            fail("spawn.Effect.scan: image 는 1 이상이어야 합니다 (0 은 '이펙트 없음' 표시)")

    def __repr__(self):
        return "spawn.Effect.scan(%r, color=%r)" % (self.image, self.color)

    @classmethod
    def scan(cls, image, color=None):
        return cls("scan", image, color)

    @classmethod
    def frag(cls, *args, **kw):
        fail("spawn.Effect.frag: 기억의 조각(FfragMode)은 2단계 기능입니다 (S1 8.7)")


def f_scan(image, color=None):
    """스캔 이펙트 속성(`Effect.scan`).

    인자: image(1~65535), color(None | 0~255 Draw Function 값) — 상수·변수
    반환: Effect / 비용: `Effect` 설명 / CP: 해당 없음 / 로컬: 공유 안전
    epScript: `effect=spawn.scan(429, color=16)`
    출처: GCB EffID·EffColor
    """
    return Effect.scan(image, color)


scan = f_scan


class RType:
    """등록된 RepeatType 하나 (`Spawner.rtype` 가 돌려준다). `rt.id`, `rt.name`, `rt.handlers`.

    데코레이터로 쓰면 핸들러를 더한다: `@sp.rtype("Skill", id=8)`.
    """

    __slots__ = ("_sp", "handlers", "id", "name")
    dont_flatten = True

    def __init__(self, sp, name, rid):
        self._sp = sp
        self.name = name
        self.id = rid
        self.handlers = []

    def __repr__(self):
        return "<spawn.RType %s=%d 핸들러 %d>" % (self.name, self.id, len(self.handlers))

    def __call__(self, fn):
        self._sp._check_open("rtype 핸들러 등록")
        if not callable(fn):
            fail("spawn.rtype %s: 핸들러는 부를 수 있는 것이어야 합니다 (%r)", self.name, fn)
        self.handlers.append(fn)
        return fn


class _Anchor:
    """`sp.anchor` — 중심 생략 시 기준 좌표(원본 G_CB_X/G_CB_Y). `.x`/`.y` 는 EUDVariable, 대입하면 값이 들어간다."""

    __slots__ = ("_x", "_y")

    def __init__(self):
        object.__setattr__(self, "_x", EUDVariable())
        object.__setattr__(self, "_y", EUDVariable())

    def __repr__(self):
        return "<spawn anchor>"

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    def __setattr__(self, name, value):
        if name not in ("x", "y"):
            raise AttributeError("spawn anchor 에는 x, y 만 있습니다 (%s)" % name)
        var = self._x if name == "x" else self._y
        if unProxy(value) is var:  # `anchor.x += 1` 이 제자리에서 고친 뒤 다시 넣는 경우
            return
        var << value


# =============================================================================================
# 핸들러 문맥
# =============================================================================================


class SpawnCtx:
    """핸들러 인자 `s` — 방금 만든 유닛과 작업 값. 모든 메서드는 부른 자리에 코드를 낸다.

    값(EUDVariable): `epd`, `ptr`, `index`(units 칸 번호), `unit`, `owner`, `rtype`, `px`, `py`(소환한 점 = 최종 좌표),
          `cx`, `cy`(작업 중심 — 평행이동 전), `ox`, `oy`(명령 목표), `cunit`(eudplib CUnit)
    `x`, `y`: 유닛이 **실제로 선 자리**(CUnit +0x28) — 읽을 때마다 새로 읽는다(실행 약 30). 둘 다 쓰면 `s.pos()` 한 번.
    조건: `has_order`(명령 속성이 있나 — 읽을 때마다 새 조건)
    동작: `here()`(loc ← 유닛 자리 ±1, 번호 반환), `default_order(kind, target=None)`(명령 속성이 없을 때만:
          here + Order(유닛, 주인, loc, kind, 목표) — target None = 기본 목표, "center" = 작업 중심, 로케이션, (x, y)),
          `order(kind, x, y)`(항상), `kill_all()`(KillUnit(유닛, 주인) — 같은 종류 전부),
          `set_turn_radius(v)`, `set_speed(top, accel=None)`, `set_remove_timer(n)`, `set_parasite(v=0xFF)`,
          `set_order_id(n)`, `set_invincible()`
    비용: 메서드 설명 / CP: 메서드는 CP 를 바꾸지 않는다(안에서 잠깐 옮기고 캐시로 되돌림)
    로컬: 공유 안전
    epScript: rtype_func 핸들러 안에서 `sp.ctx.default_order(Attack);`
    출처: GCB 164~199(LocHere·LocCenter·DefaultOrder), 441~590(RepeatType 표)
    """

    def __init__(self, sp):
        self._sp = sp

    def __repr__(self):
        return "<spawn.SpawnCtx %s>" % self._sp.name

    # --- 값 ---
    @property
    def epd(self):
        return self._sp._cap.epd

    @property
    def ptr(self):
        return self._sp._cap.ptr

    @property
    def index(self):
        return self._sp._cap.index

    @property
    def cunit(self):
        return self._sp._cap.cunit

    @property
    def unit(self):
        return self._sp._J["unit"]

    @property
    def owner(self):
        return self._sp._J["owner"]

    @property
    def rtype(self):
        return self._sp._J["rtype"]

    @property
    def px(self):
        return self._sp._px

    @property
    def py(self):
        return self._sp._py

    @property
    def cx(self):
        return self._sp._J["cx"]

    @property
    def cy(self):
        return self._sp._J["cy"]

    @property
    def ox(self):
        return self._sp._J["ox"]

    @property
    def oy(self):
        return self._sp._J["oy"]

    @property
    def has_order(self):
        return _any_bit(self._sp._J["flags"], F_ORDER)

    def pos(self):
        """유닛 자리 (x, y) 를 지금 읽는다(새 변수 둘). 비용: 실행 약 30."""
        return self._sp._posread(self.epd)

    @property
    def x(self):
        return self.pos()[0]

    @property
    def y(self):
        return self.pos()[1]

    # --- 로케이션 ---
    def here(self):
        """loc ← 유닛 자리 2×2 상자(원본 G_CB_LocHere). 반환: loc 번호. 비용: 실행 약 35."""
        sp = self._sp
        ux, uy = sp._posread(self.epd)
        sp._box(sp.loc, ux, uy, 1)
        return sp.loc

    def _dest(self, target):
        sp = self._sp
        t = unProxy(target)
        if t is None:
            t = sp._default_target
            if t is None:
                fail("spawn %s: default_target 이 없어 기본 명령 목표를 모릅니다 (Spawner(default_target=…))", sp.name)
        if isinstance(t, bytes):
            t = t.decode("utf-8")
        if isinstance(t, str) and t == "center":
            sp._box(sp.loc2, sp._J["cx"], sp._J["cy"], 1)
            return sp.loc2
        if isinstance(t, (tuple, list)):
            if len(t) != 2:
                fail("SpawnCtx: 목표 (x, y) 는 두 값이어야 합니다 (%r)", t)
            sp._box(sp.loc2, _num(t[0], "SpawnCtx", "목표 x"), _num(t[1], "SpawnCtx", "목표 y"), 1)
            return sp.loc2
        return _loc_num(t, "SpawnCtx", "명령 목표 로케이션")

    def default_order(self, kind=Attack, target=None):
        """명령 속성이 없을 때만 유닛 자리에서 목표로 명령한다(원본 G_CB_DefaultOrder).

        인자: kind(Attack/Patrol/Move), target(None = Spawner default_target(로케이션이면 **명령 순간**의 그 로케이션),
              "center" = 작업 중심, 로케이션 이름·번호, (x, y))
        비용: 명령 속성이 있으면 실행 1, 없으면 약 40 (위치 읽기 + 로케이션 + Order)
        """
        k = _order_kind(kind, "SpawnCtx.default_order")
        sp = self._sp
        if EUDIf()(_no_bit(sp._J["flags"], F_ORDER)):
            self.here()
            dest = self._dest(target)
            sp._uo_action(_SCOrder(0, 0, sp.loc, k, dest), ACT_ORDER, k)
        EUDEndIf()

    def order(self, kind, x, y):
        """명령 속성과 상관없이 유닛 자리에서 (x, y) 로 명령한다. 비용: 실행 약 42."""
        k = _order_kind(kind, "SpawnCtx.order")
        sp = self._sp
        xv, yv = _num(x, "SpawnCtx.order", "x"), _num(y, "SpawnCtx.order", "y")
        self.here()
        sp._box(sp.loc2, xv, yv, 1)
        sp._uo_action(_SCOrder(0, 0, sp.loc, k, sp.loc2), ACT_ORDER, k)

    def kill_all(self):
        """KillUnit(유닛, 주인) — **그 주인의 그 종류 유닛 전부**(원본 RepeatType 3, S1 10-29). 비용: 실행 2."""
        self._sp._uo_action(KillUnit(0, 0), ACT_KILL, 0)

    # --- CUnit 칸 ---
    def _write(self, items):
        self._sp._cunit_write(self.epd, items)

    def set_turn_radius(self, v):
        """회전반경(+0x22 바이트). 비용: 실행 약 4."""
        self._write([(CU_TURN_RADIUS, _num(v, "SpawnCtx.set_turn_radius", "v", 0, 255), 1)])

    def set_speed(self, top, accel=None):
        """최고속도(+0x34 dword)·가속도(+0x48 word, None 이면 top 과 같게). 비용: 실행 약 4~6."""
        t = _num(top, "SpawnCtx.set_speed", "top")
        a = t if accel is None else _num(accel, "SpawnCtx.set_speed", "accel", 0, 0xFFFF)
        self._write([(CU_TOP_SPEED, _u32(t), 4), (CU_ACCEL, a, 2)])

    def set_remove_timer(self, n):
        """removeTimer(+0x110 word). 비용: 실행 약 4."""
        self._write([(CU_REMOVE_TIMER, _num(n, "SpawnCtx.set_remove_timer", "n", 0, 0xFFFF), 2)])

    def set_parasite(self, v=0xFF):
        """기생 플래그(+0x121 바이트, 0xFF = 모든 플레이어에게 시야 — 원본 Vision). 비용: 실행 약 4."""
        self._write([(CU_PARASITE, _num(v, "SpawnCtx.set_parasite", "v", 0, 255), 1)])

    def set_order_id(self, n):
        """주문 번호(+0x4D 바이트, 원본 JYD 187). 비용: 실행 약 4."""
        self._write([(CU_ORDER_ID, _num(n, "SpawnCtx.set_order_id", "n", 0, 255), 1)])

    def set_invincible(self):
        """무적 상태 비트(+0xDC 0x04000000). 비용: 실행 약 4."""
        self._write([(CU_STATUS, STATUS_INVINCIBLE, 4, STATUS_INVINCIBLE)])


# =============================================================================================
# 내장 핸들러
# =============================================================================================


class _Builtins:
    """`sp.builtin` — 일반 RepeatType 핸들러(S1 5.4 의 "일반" 줄). 맵 전용(130~137, 175~179, 181, 188)은 없다.

    - `attack_default`(원본 0): 유닛 자리에서 기본 목표로 어택(명령 속성이 없을 때) + 회전반경
    - `kill_all_of_type`(3): KillUnit(유닛, 주인)
    - `remove_timer(n=250)`(5): removeTimer = n
    - `attack_center`(7, 원본 이름 `patrol_center` — 이름과 달리 **어택**): 작업 중심으로 어택 + 회전반경
    - `skill_unit`(8): 기본 목표로 순찰 + 회전반경 + removeTimer 15
    - `vision`(180): 기생 플래그 0xFF
    - `nxct`(106): 회전반경, 속도·가속도 128, 작업 중심으로 어택(명령 속성 무시)
    - `no_speed`(201): 회전반경, 속도·가속도 1
    - `nspeed(attack=True)`(147/148): 목표(명령 속성 목표, 없으면 작업 중심)까지 거리로 속도 = isqrt((dx²+dy²)/4),
      기생 0xFF, 회전반경 127. attack 이면 그 목표로 어택(명령 속성과 무관 — 원본 147), 아니면 속도만(148)
    - `force_order(order_id=187)`(JYD): 주문 번호 직접 쓰기
    회전반경은 `Spawner(turn_radius=…)`(None 이면 쓰지 않음, nspeed 는 원본처럼 127 고정).
    """

    def __init__(self, sp):
        self._sp = sp

    def __repr__(self):
        return "<spawn builtin handlers>"

    def _radius(self, s):
        if self._sp.turn_radius is not None:
            s.set_turn_radius(self._sp.turn_radius)

    def attack_default(self, s):
        s.default_order(Attack)
        self._radius(s)

    def kill_all_of_type(self, s):
        s.kill_all()

    def remove_timer(self, n=250):
        n = _num(n, "spawn.builtin.remove_timer", "n", 0, 0xFFFF)

        def remove_timer_handler(s):
            s.set_remove_timer(n)

        return remove_timer_handler

    def attack_center(self, s):
        s.default_order(Attack, "center")
        self._radius(s)

    patrol_center = attack_center  # 원본 이름 (S1 10-34: 이름과 달리 어택)

    def skill_unit(self, s):
        s.default_order(Patrol)
        self._radius(s)
        s.set_remove_timer(15)

    def vision(self, s):
        s.set_parasite(0xFF)

    def nxct(self, s):
        sp = self._sp
        self._radius(s)
        s.set_speed(128, 128)
        s.here()
        sp._box(sp.loc2, sp._J["cx"], sp._J["cy"], 1)
        sp._uo_action(_SCOrder(0, 0, sp.loc, Attack, sp.loc2), ACT_ORDER, 2)

    def no_speed(self, s):
        self._radius(s)
        s.set_speed(1, 1)

    def nspeed(self, attack=True):
        attack = bool(attack)
        sp = self._sp

        def nspeed_handler(s):
            J = sp._J
            tx, ty = EUDVariable(), EUDVariable()
            if EUDIf()(_no_bit(J["flags"], F_ORDER)):
                SeqCompute([(tx, SetTo, J["cx"]), (ty, SetTo, J["cy"])])
            if EUDElse()():
                SeqCompute([(tx, SetTo, J["ox"]), (ty, SetTo, J["oy"])])
            EUDEndIf()
            ux, uy = sp._posread(s.epd)
            dx, dy = EUDVariable(), EUDVariable()
            SeqCompute([(dx, SetTo, ux), (dy, SetTo, uy)])
            _parts.isub32(dx, tx)
            _parts.isub32(dy, ty)
            sq = dx * dx
            sq += dy * dy
            sq = sq >> 2  # 원본 _Div(합, 4) — 부호 없는 나눗셈
            speed = mathx.isqrt(sq)
            s._write([(CU_PARASITE, 0xFF, 1), (CU_TURN_RADIUS, 127, 1), (CU_TOP_SPEED, speed, 4),
                      (CU_ACCEL, speed, 2)])
            sp._box(sp.loc2, tx, ty, 1)
            if attack:
                sp._box(sp.loc, ux, uy, 1)
                sp._uo_action(_SCOrder(0, 0, sp.loc, Attack, sp.loc2), ACT_ORDER, 2)

        return nspeed_handler

    def force_order(self, order_id=187):
        n = _num(order_id, "spawn.builtin.force_order", "order_id", 0, 255)

        def force_order_handler(s):
            s.set_order_id(n)

        return force_order_handler


# =============================================================================================
# 작업 (여러 층)
# =============================================================================================

_LAYER_KEYS = ("owner", "lm", "delay", "size", "rotate", "rtype", "variant", "mirror")
_JOB_KEYS = _LAYER_KEYS + ("center", "offset", "order", "effect", "rot3d")


class Job:
    """여러 층 작업 만들기 (`sp.job(**작업 값).layer(유닛, 도형, **층 값)….push()`).

    작업 값(모든 층 공통): center, offset, order, effect, rot3d(2단계) + 층 값의 기본(owner, lm, delay, size, rotate, rtype).
    층 값: owner, lm, delay, size, rotate, rtype (variant·mirror 는 2단계).
    층은 넣은 순서대로 진행한다(층 사이 빈 프레임 1개). 원본은 4층까지였지만 제한이 없다(capacity 안).
    `push()` 는 부른 자리에 넣기 코드를 낸다 — 같은 Job 을 두 번 push 하면 두 곳에 코드가 생긴다.
    인자·반환·비용: `Spawner.push` 와 같다(층마다 pool alloc 한 벌)
    CP: 바꾸지 않음 / 로컬: 공유 안전
    epScript: `sp.job(owner=P8, order=spawn.attack("Boss")).layer(37, ring).layer(38, ring, size=150).push();`
    출처: S1 8.2·8.3 (epScript 의 `[a, b]` 는 EUDArray 가 되므로 사슬 API 가 기본형)
    """

    dont_flatten = True

    def __init__(self, sp, **kw):
        for k in kw:
            if k not in _JOB_KEYS:
                fail("spawn.job: 모르는 인자 %r (쓸 수 있는 것: %s)", k, ", ".join(_JOB_KEYS))
        self._sp = sp
        self._kw = dict(kw)
        self._layers = []

    def __repr__(self):
        return "<spawn.Job 층 %d>" % len(self._layers)

    def layer(self, unit, shape, **kw):
        """층 하나를 더한다. 반환: 같은 Job (사슬)."""
        for k in kw:
            if k not in _LAYER_KEYS:
                fail("spawn.Job.layer: 모르는 인자 %r (쓸 수 있는 것: %s)", k, ", ".join(_LAYER_KEYS))
        self._layers.append((unit, shape, dict(kw)))
        return self

    def push(self):
        """작업을 대기열에 넣는다(원자적). 반환: 첫 층 핸들 EUDVariable (0 = 넘침)."""
        return self._sp._emit_push(dict(self._kw), list(self._layers))


# =============================================================================================
# Spawner
# =============================================================================================


def _rotator(cycle):
    # WP9 안내: Rotator(None) 에 작업마다 set. 변수 각 엔진(본문)은 같은 주기의 모든 Rotator 가 같이 쓰고,
    # 각 변수만 Spawner 마다 따로 둔다 — 한 Spawner 의 핸들러가 다른 Spawner 를 돌려도 각이 섞이지 않게.
    return mathx.Rotator(None, cycle=cycle)


_SPAWNERS = weakref.WeakSet()


@_compat.register_build_reset
def _reset_all():
    # 한 프로세스 여러 빌드: 코드 조각(서브루틴·템플릿 액션)은 빌드마다 새로 만든다. 변수·등록은 그대로.
    for sp in list(_SPAWNERS):
        sp._reset_build()


def _eff_value(effect):
    img, col = effect.image, effect.color
    if _is_int(img) and (col is None or _is_int(col)):
        return img | (0 if col is None else (col << 16) | (1 << 24))
    ev = EUDVariable()
    ev << img
    if col is not None:
        if _is_int(col):
            ev += col << 16
        else:
            c16 = EUDVariable()
            c16 << col
            c16 <<= 16
            ev += c16
        ev += 1 << 24
    return ev


class Spawner:
    """G_CB 식 소환 대기열 (원본 `Include_G_CB_Library` + `G_CBPlot` + `G_CB_TSetSpawn` …).

    인자: capacity(레코드 = 층 수, 1 이상. 넣기 한 번에 층 수만큼 쓴다 — 원본은 128칸 × 최대 4층),
          loc(소환 자리·명령 주체 상자 — 이름 또는 1부터 번호. 필수, 점마다 옮겨지고 되돌리지 않는다),
          loc2(명령 목표 상자 — 필수, loc 과 달라야 한다),
          default_target(기본 명령 목표: 로케이션(명령 순간의 그 로케이션) 또는 (x, y). 없으면 기본 목표를 쓰는 핸들러가 빌드 오류),
          default_owner(주인 생략 시, 기본 P8), map_size(None = chk DIM × 32, 또는 (W, H) 픽셀),
          cycle(회전 각 단위, 기본 360), turn_radius(내장 핸들러가 쓰는 회전반경, None = 안 씀),
          storage(좌표 저장 "db" | "varray" — shapes 를 안 줄 때), shapes(함께 쓸 ShapeSet, 없으면 새로),
          props("energy" = UnitProperty(energy=100) — 원본과 같음 | None = CreateUnit | UnitProperty),
          on_create(생성 직전 훅: UnitData(목록) = 그 칸 초기화, 함수 = f(칸 번호) — 모든 소환이 캡처를 쓴다),
          on_full(넘침 문구: None = debug 면 "report" 아니면 "silent" | "report" | "silent" | 함수),
          debug(넘침·빈 작업·등록 안 한 rtype 문구), name(표시용), unclickable(2단계 — None 만)
    속성: `anchor`(.x/.y), `rotation`, `live`(살아 있는 레코드 수), `overflow`(넘침 누적), `shapes`, `pool`,
          `builtin`, `ctx`(핸들러 문맥), `GLOBAL`, `default_rtype`(rtype 생략 시 — 이름·번호·None=0 없음), `loc`, `loc2`,
          `map_size`, `rot3d`(2단계)
    메서드: `push`, `job`, `push_layers`, `push_multi`, `tick`, `spawn_now`, `scan_effect`, `clear`, `rtype`, `rtype_func`,
          `rtype_id`, `preview`, `preview_count`
    비용: 저장 = pool(필드 20) — capacity × (22×72 + 148) B + 공유 코드. capacity 128 = chk +309KB·scx +30KB,
          8 = chk +92KB·scx +9.6KB, 크기·회전을 쓰면 mathx 엔진 chk +113KB(쓴 기능만 넣는다).
          tick·소환 루틴 세 벌·변환 서브루틴 약 150 트리거(한 벌), tick 호출 자리 1. 실행은 tick·push 설명.
          트리거 수는 도형 수·점 수와 무관(DESIGN 3.8) (2026-09-17, docs/COSTS.md "spawn (WP12)")
    CP: 바꾸지 않음 (소환·핸들러 안에서 잠깐 옮기고 캐시로 되돌림. 사용자 핸들러가 바꾼 CP 는 그 핸들러 책임)
    로컬: 공유 안전 (넣기·tick 은 모든 클라이언트에서 같은 조건으로)
    epScript: `const sp = spawn.Spawner(capacity=64, loc="GCB Src", loc2="GCB Dst", default_target="Home");`
    출처: GCB 61~2768, CAPI 216~411, S1 8절
    """

    GLOBAL = GLOBAL
    dont_flatten = True

    def __init__(self, capacity=128, loc=None, loc2=None, default_target=None, default_owner=P8, map_size=None,
                 cycle=360, turn_radius=127, storage="db", shapes=None, props="energy", unclickable=None,
                 on_create=None, on_full=None, debug=False, name="spawn"):
        fname = "spawn.Spawner"
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        require(isinstance(name, str) and name, "%s: name 은 문자열이어야 합니다 (%r)", fname, name)
        self.name = name
        if loc is None or loc2 is None:
            fail("%s: loc(소환 자리)·loc2(명령 목표) 로케이션은 필수입니다 (이름 또는 1부터 번호)", fname)
        self._loc = _loc_check(loc, fname, "loc")
        self._loc2 = _loc_check(loc2, fname, "loc2")
        if self._loc == self._loc2:
            fail("%s: loc 과 loc2 는 서로 다른 로케이션이어야 합니다 (%r)", fname, loc)
        for lv in (self._loc, self._loc2):
            if lv == 64 or (isinstance(lv, str) and lv.lower() == "anywhere"):
                fail("%s: Anywhere(64) 는 점마다 옮기는 로케이션으로 쓸 수 없습니다", fname)
        dt = unProxy(default_target)
        if isinstance(dt, bytes):
            dt = dt.decode("utf-8")
        if isinstance(dt, (list, tuple)):
            require(len(dt) == 2, "%s: default_target (x, y) 는 두 값이어야 합니다 (%r)", fname, dt)
            dt = (_num(dt[0], fname, "default_target x"), _num(dt[1], fname, "default_target y"))
        elif dt is not None:
            dt = _loc_check(dt, fname, "default_target")
        self._default_target = dt
        self._default_owner = _owner_arg(default_owner, fname)
        if not _is_int(self._default_owner):
            fail("%s: default_owner 는 상수 플레이어여야 합니다", fname)
        if map_size is not None:
            ms = [unProxy(v) for v in map_size]
            require(len(ms) == 2 and all(_is_int(v) and 1 <= v <= 0x10000 for v in ms),
                    "%s: map_size 는 (W, H) 픽셀 정수여야 합니다 (%r)", fname, map_size)
            map_size = tuple(ms)
        self._map_size = map_size
        self.cycle = mathx_tables.check_cycle(cycle, fname)
        tr = unProxy(turn_radius)
        if tr is not None:
            if not _is_int(tr) or not 0 <= tr <= 255:
                fail("%s: turn_radius 는 0~255 상수 또는 None 이어야 합니다 (%r)", fname, turn_radius)
        self.turn_radius = tr
        if shapes is None:
            shapes = ShapeSet(storage=storage, name=name + ".shapes")
        elif not isinstance(shapes, ShapeSet):
            fail("%s: shapes 는 ShapeSet 이어야 합니다 (%r)", fname, shapes)
        self.shapes = shapes
        if isinstance(props, str):
            check_choice(fname + " props", props, ("energy",))
            props = UnitProperty(energy=100)
        elif props is not None and not isinstance(props, (UnitProperty, bytes)):
            fail("%s: props 는 \"energy\", None, UnitProperty 중 하나입니다 (%r)", fname, props)
        self.props = props
        if unclickable is not None:
            fail("%s: unclickable(0틱 클릭 불가)은 2단계 기능입니다 (S1 8.7)", fname)
        if on_create is not None and not (callable(on_create) or isinstance(on_create, (units.UnitData, list, tuple))):
            fail("%s: on_create 는 UnitData(또는 목록)·함수여야 합니다 (%r)", fname, on_create)
        self.on_create = on_create
        if not isinstance(debug, bool):
            fail("%s: debug 는 True/False (%r)", fname, debug)
        self.debug = debug
        if on_full is None:
            on_full = "report" if debug else "silent"
        if not (on_full in ("report", "silent") or callable(on_full)):
            fail("%s: on_full 은 \"report\"·\"silent\"·함수 중 하나 (%r)", fname, on_full)
        self.on_full = on_full
        # 되쓰는 필드는 pc·left·sp·w 넷뿐(나머지는 readonly) → "all" 이어도 같고, 주 함수 뒤 순서에 기대지 않는다
        self.pool = Pool(name, FIELDS, capacity, on_full=self._pool_full, on_unknown="silent", writeback="all")
        self.capacity = self.pool.capacity
        # 상태 변수
        self._anchor = _Anchor()
        self._rotation = EUDVariable()
        self._J = {k: EUDVariable() for k in ("unit", "owner", "rtype", "flags", "cx", "cy", "ox", "oy", "ouword", "eff")}
        self._px, self._py = EUDVariable(), EUDVariable()
        self._tx, self._ty, self._S = EUDVariable(), EUDVariable(), EUDVariable()
        self._L, self._k = EUDVariable(), EUDVariable()
        self._fsize, self._frot, self._carry = EUDLightVariable(), EUDLightVariable(), EUDLightVariable()
        self._fxf = EUDLightVariable()
        self._eimg, self._ecol, self._eepd, self._esub, self._eold = (EUDVariable() for _ in range(5))
        self._ehas = EUDLightVariable()
        self._cap = units.Capture()
        self._rot = _rotator(self.cycle)
        # rtype
        self._rtypes = {}
        self._rtype_by_id = {}
        self._default_rtype = 0
        self.builtin = _Builtins(self)
        self.ctx = SpawnCtx(self)
        # 코드 조각
        self._tick_sub = None
        self._point_sub = None
        self._create_acts = None
        self._psubs = None
        self._scan_acts = None
        self._posread_fn = None
        self._in_point = False
        self._reentry = []
        self._ticks = 0
        self._building_tick = False
        # 쓰인 기능 (주 함수를 다 만든 뒤 변환 서브루틴을 채울 때 본다 — 안 쓴 기능은 페이로드에 넣지 않는다)
        self._need = {"size": False, "rot": False, "effect": False}
        self._xsubs = None
        self._xdefined = False
        _SPAWNERS.add(self)

    def _reset_build(self):
        self._tick_sub = None
        self._point_sub = None
        self._create_acts = None
        self._psubs = None
        self._scan_acts = None
        self._posread_fn = None
        self._in_point = False
        self._reentry = []
        self._ticks = 0
        self._building_tick = False
        self._need = {"size": False, "rot": False, "effect": False}
        self._xsubs = None
        self._xdefined = False

    def __repr__(self):
        return "<spawn.Spawner %s capacity=%d>" % (self.name, self.capacity)

    # ------------------------------------------------------------------ 속성
    @property
    def anchor(self):
        """중심 생략(center=None) 때 쓰는 좌표 — `.x`, `.y` (EUDVariable). **넣는 순간** 값이 작업에 복사된다.

        epScript: `sp.anchor.x = 3072; sp.anchor.y = 1536;`
        """
        return self._anchor

    @property
    def rotation(self):
        """전역 회전각 EUDVariable(원본 G_CB_RotateV) — `rotate=sp.GLOBAL` 작업이 **점마다** 읽는다.

        epScript: `sp.rotation += 5;`
        """
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        if unProxy(value) is self._rotation:
            return
        self._rotation << value

    @property
    def rot3d(self):
        """(2단계) 3D 회전 각 (xy, yz, zx) — 1단계에서는 읽으면 컴파일 오류."""
        fail("spawn %s: rot3d(3D 회전)는 2단계 기능입니다 (S1 8.7)", self.name)

    @property
    def live(self):
        """살아 있는 레코드(층) 수 EUDVariable — 아직 차례가 아닌 뒤 층 포함."""
        return self.pool.count

    @property
    def overflow(self):
        """넘침 누적 EUDVariable — 빈 칸이 모자라 버린 넣기 횟수(층 수가 아니라 넣기 한 번에 1)."""
        return self.pool.dropped

    @property
    def loc(self):
        """소환 자리 로케이션 번호(1부터). 이름으로 만들었으면 맵을 불러온 뒤에 읽는다."""
        return _loc_num(self._loc, "spawn.Spawner", "loc")

    @property
    def loc2(self):
        """명령 목표 로케이션 번호(1부터)."""
        return _loc_num(self._loc2, "spawn.Spawner", "loc2")

    @property
    def map_size(self):
        """(W, H) 픽셀 — map_size 인자, 없으면 지금 맵의 chk DIM × 32."""
        if self._map_size is not None:
            return self._map_size
        dim = GetChkTokenized().getsection("DIM")
        return (dim[0] | dim[1] << 8) * 32, (dim[2] | dim[3] << 8) * 32

    @property
    def default_rtype(self):
        """rtype 생략 시 쓰는 번호(0 = 없음). 이름·번호로 넣는다(등록된 것만). epScript: `sp.default_rtype = "Home";`"""
        return self._default_rtype

    @default_rtype.setter
    def default_rtype(self, value):
        v = self.rtype_id(value) if value is not None else 0
        if not _is_int(v):
            fail("spawn %s: default_rtype 은 상수(이름·번호)여야 합니다", self.name)
        self._default_rtype = v

    # ------------------------------------------------------------------ rtype 등록
    def _check_open(self, what):
        if self._point_sub is not None:
            fail("spawn %s: %s 는 tick()/spawn_now() 로 소환 코드를 만들기 전에 해야 합니다 (모든 push/tick 보다 앞)",
                 self.name, what)

    def rtype(self, name, handler=None, id=None):  # noqa: A002
        """RepeatType(소환 뒤 행동)을 등록한다. 컴파일 시점, 첫 tick()/spawn_now() 보다 앞.

        인자: name(문자열 — push 의 rtype= 로 부른다), handler(fn(s) 또는 인자 없는 함수, EUDFunc, 그 목록, 또는 None = 아무것도
              안 함), id(1~255, 생략 = 비어 있는 가장 작은 번호). 0 은 "없음" 으로 예약.
        반환: RType (데코레이터로 쓰면 핸들러를 더한다: `@sp.rtype("Skill", id=8) def f(s): …`)
        비용: 없음(등록). 소환 서브루틴의 EUDSwitch 에 가지가 하나 생긴다(실행 약 log2(수) + 4)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `sp.rtype("Home", sp.builtin.attack_default);` (epScript 함수는 `rtype_func`)
        출처: GCB 441~610 RepeatTypeDefs, G_CB_RepeatTypeExtraDefs, S1 8.2
        """
        self._check_open("rtype 등록")
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        if not isinstance(name, str) or not name:
            fail("spawn.rtype: 이름은 빈 문자열이 아닌 문자열이어야 합니다 (%r)", name)
        if name in self._rtypes:
            fail("spawn %s: rtype 이름 %r 를 두 번 등록했습니다 (RepeatTypeNum_Duplicated)", self.name, name)
        if id is None:
            rid = next((i for i in range(1, 256) if i not in self._rtype_by_id), None)
            if rid is None:
                fail("spawn %s: rtype 번호 1~255 가 모두 찼습니다", self.name)
        else:
            rid = unProxy(id)
            if not _is_int(rid) or not 1 <= rid <= 255:
                fail("spawn.rtype %s: id 는 1~255 상수여야 합니다 (%r) — 0 은 '없음'", name, id)
            if rid in self._rtype_by_id:
                fail("spawn %s: rtype 번호 %d 를 두 번 등록했습니다 (%s, %s) (RepeatTypeNum_Duplicated)", self.name, rid,
                     self._rtype_by_id[rid].name, name)
        rt = RType(self, name, rid)
        handlers = [] if handler is None else (list(handler) if isinstance(handler, (list, tuple)) else [handler])
        for h in handlers:
            if not callable(h):
                fail("spawn.rtype %s: 핸들러는 부를 수 있는 것이어야 합니다 (%r)", name, h)
        self._rtypes[name] = rt
        self._rtype_by_id[rid] = rt
        for h in handlers:
            rt(h)
        return rt

    def rtype_func(self, name, *fns, id=None):  # noqa: A002
        """epScript 함수(EUDFunc)로 RepeatType 을 등록한다. 함수는 인자 5개 `(epd, unit, owner, x, y)` 또는 0개.

        여러 개를 주면 차례로 부른다(내장 핸들러를 섞어도 된다: `sp.rtype_func("Home", sp.builtin.attack_default, Count)`).
        x, y 는 유닛이 실제로 선 자리(읽기 약 30 실행). 함수 안에서 `sp.ctx` 로 SpawnCtx 동작을 쓸 수 있다.
        epScript 함수는 **이 호출보다 앞에** 정의해야 이름을 값으로 넘길 수 있다(뒤에 있으면 번역 오류 "Undefined rvalue").
        인자: name, fns(EUDFunc·파이썬 핸들러), id
        반환: RType
        비용: `rtype` 과 같음 + 함수 호출(인자 5개면 위치 읽기 포함 약 40)
        CP: 해당 없음
        로컬: 해당 없음
        epScript: `function onPluginStart() { sp.rtype_func("Hold", HoldHandler); }`
        출처: S1 8.3
        """
        if not fns:
            fail("spawn.rtype_func %s: 함수가 없습니다", name)
        return self.rtype(name, list(fns), id=id)

    def rtype_id(self, value):
        """rtype 인자 → 번호. 이름·번호 상수는 등록된 것만(0 = 없음), 변수는 그대로.

        반환: int 또는 EUDVariable / 비용: 없음(상수) / epScript: `const n = sp.rtype_id("Home");`
        """
        v = unProxy(value)
        if isinstance(v, bytes):
            v = v.decode("utf-8")
        if isinstance(v, str):
            rt = self._rtypes.get(v)
            if rt is None:
                fail("spawn %s: 등록되지 않은 rtype 이름 %r (등록: %s) — 원본은 조용히 0 이 되던 오타(S1 10-24)",
                     self.name, v, ", ".join(sorted(self._rtypes)) or "없음")
            return rt.id
        if isinstance(v, RType):
            if v._sp is not self:
                fail("spawn %s: 다른 Spawner 의 rtype 입니다 (%r)", self.name, v)
            return v.id
        if _is_int(v):
            if v == 0:
                return 0
            if v not in self._rtype_by_id:
                fail("spawn %s: 등록되지 않은 rtype 번호 %d", self.name, v)
            return v
        return _num(v, "spawn.rtype", "rtype", 0, 255)

    # ------------------------------------------------------------------ 컴파일 시점 도우미
    def preview(self, shape, center=(0, 0), size=100, rotate=0, offset=(0, 0), rotation=0):
        """넣었을 때 소환될 좌표 목록을 컴파일 시점에 계산한다(상수 인자만 — 확인·문구용).

        인자: shape(Shape 또는 sid 상수), center((x, y) 상수), size, rotate(각 또는 GLOBAL — GLOBAL 이면 rotation 값),
              offset((dx, dy)), rotation(GLOBAL 일 때의 전역 각)
        반환: [(X, Y)] 경계 안의 점(소환 순서). 스케줄·lm 과 무관
        비용: 없음(파이썬)
        CP: 해당 없음 / 로컬: 해당 없음
        epScript: `const n = sp.preview_count(ring, center=list(4050, 1200));`
        출처: 새로 작성 (S1 6.3 의 변환 순서)
        """
        if not isinstance(shape, Shape):
            shape = self.shapes[unProxy(shape)]
        W, H = self.map_size
        cx, cy = (unProxy(v) for v in center)
        dx, dy = (unProxy(v) for v in offset)
        size = unProxy(size)
        glob = unProxy(rotate) is GLOBAL
        ang = unProxy(rotation) if glob else unProxy(rotate)
        for v in (cx, cy, dx, dy, size, ang):
            if not _is_int(v):
                fail("spawn.preview: 상수만 받습니다 (%r)", v)
        out = []
        for x, y in shape.points:
            if size != 100:
                x = _tdiv(_s32(x * size), 100)
                y = _tdiv(_s32(y * size), 100)
            if glob or (ang & M32) != 0:
                x, y = rotate_py(x, y, ang, self.cycle)
            X = (x + dx + cx) & M32
            Y = (y + dy + cy) & M32
            if X <= W - 1 and Y <= H - 1:
                out.append((X, Y))
        return out

    def preview_count(self, shape, center=(0, 0), size=100, rotate=0, offset=(0, 0), rotation=0):
        """`len(preview(…))` — epScript 용 컴파일 시점 정수(인게임 문구·자체 점검에 쓴다).

        인자·비용: `preview` 와 같음 / 반환: int / CP: 해당 없음 / 로컬: 해당 없음
        epScript: `const n = sp.preview_count(ring, center=list(4050, 1200));`
        출처: 새로 작성
        """
        return len(self.preview(shape, center=center, size=size, rotate=rotate, offset=offset, rotation=rotation))

    # ------------------------------------------------------------------ 넘침 문구
    def _pool_full(self):
        how = self.on_full
        if how == "silent":
            return
        if callable(how):
            if _call_n_args(how) == 0:
                how()
            else:
                how(self)
            return
        self._say("\x07『 \x08ERROR \x04: %s 소환 대기열이 가득 차 데이터를 입력하지 못했습니다! "
                  "스크린샷으로 제작자에게 제보해주세요!\x07 』" % self.name, 2)

    def _say(self, text, buzz=0):
        from eudext import players

        players.run_as(players.Everyone, DisplayText(text), *[PlayWAV(BUZZ_WAV)] * buzz)

    # ------------------------------------------------------------------ 넣기
    def job(self, **kw):
        """여러 층 작업을 만든다(원본 G_CB_TSetSpawn 의 CUTable·ShapeTable 여러 개).

        인자: kw(작업 값 — center, offset, order, effect + 층 기본 owner, lm, delay, size, rotate, rtype)
        반환: Job (`.layer(유닛, 도형, **층 값)` 사슬 뒤 `.push()`)
        비용: 없음(push 가 코드를 낸다)
        CP: 해당 없음 / 로컬: 공유 안전
        epScript: `sp.job(owner=P8).layer(37, ring).layer(38, ring, size=150).push();`
        출처: S1 8.2·8.3
        """
        return Job(self, **kw)

    def push(self, unit, shape, owner=None, center=None, lm="max", delay=0, size=100, rotate=0, rot3d=False,
             offset=(0, 0), rtype=None, order=None, effect=None, variant=None, mirror=False):
        """층 하나짜리 작업을 넣는다(원본 G_CB_TSetSpawn 한 유닛·한 도형). 조건은 호출 자리의 EUDIf, 게임당 한 번은 EUDExecuteOnce.

        인자: unit(유닛 이름·번호 0~226·변수), shape(Shape — 이 Spawner 의 ShapeSet 에 넣는다 | sid 상수·변수),
              owner(None = default_owner | P1~P12 | 번호 변수),
              center(None = 그때의 sp.anchor | (x, y) | 로케이션 이름·1부터 번호(그때의 중심) | 로케이션 번호 변수 | at_unit(epd)),
              lm("max" = 255 | 1~255 | 0 = 자동 n//50+1 | 변수 — 0 이면 자동), delay(0·1 = 매 프레임, k = k 프레임마다),
              size(퍼센트, 100 = 그대로), rotate(각 | 변수 | sp.GLOBAL), offset((dx, dy) — 회전 뒤 평행이동),
              rtype(None = default_rtype | 등록된 이름·번호 | 변수), order(Order | None), effect(Effect.scan | None),
              rot3d·variant·mirror(2단계 — 쓰면 컴파일 오류)
        반환: 첫 층 핸들 EUDVariable (0 = 넘침 — overflow += 1, 층을 하나도 넣지 않는다)
        비용: 호출 자리 약 7 (pool alloc_n, 층마다 +4) / 실행 약 20~25 (3층 56). 로케이션 중심 +약 195, at_unit +약 30,
              변수 sid +약 135 (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유 안전(값이 로컬이면 디싱크)
        epScript: `sp.push(37, ring, owner=P8, center=list(x, y), size=150, rotate=sp.GLOBAL);`
        출처: GCB 2260~2571, S1 8.2
        """
        return self._emit_push(dict(owner=owner, center=center, offset=offset, order=order, effect=effect, rot3d=rot3d),
                               [(unit, shape, dict(lm=lm, delay=delay, size=size, rotate=rotate, rtype=rtype,
                                                   variant=variant, mirror=mirror))])

    def push_layers(self, pairs, **kw):
        """파이썬 편의: `[(unit, shape), …]` 를 한 작업의 층으로 넣는다.

        인자: pairs((유닛, 도형) 쌍 목록 — 받은 목록은 고치지 않는다), kw(job 인자)
        반환: 첫 층 핸들 / 비용: push 와 같음(층마다 pool alloc) / CP: 바꾸지 않음 / 로컬: 공유 안전
        epScript: 쓰지 않는다(파이썬 목록 — epScript 는 job().layer() 사슬)
        출처: S1 8.2 push_layers
        """
        job = Job(self, **kw)
        for p in pairs:
            if not isinstance(p, (list, tuple)) or len(p) != 2:
                fail("spawn.push_layers: (유닛, 도형) 쌍 목록이어야 합니다 (%r)", p)
            job.layer(p[0], p[1])
        return job.push()

    def push_multi(self, unit_list, shapes, **kw):
        """파이썬 편의(원본 CUTable·ShapeTable 모양): 유닛 목록과 도형 목록(또는 도형 하나 — 모든 층에 같은 도형)을 층으로 넣는다.

        인자: unit_list(유닛 목록), shapes(도형 목록 — 유닛 수와 같아야 한다 — 또는 도형 하나(Stella SH_Warp 처럼 네 유닛에 한 도형)),
              kw(job 인자)
        반환: 첫 층 핸들
        오류: 유닛 수 ≠ 도형 수면 컴파일 오류(원본은 뒤 층이 유닛 0 또는 도형 0 이 되던 곳 — S1 10-11).
              받은 목록은 고치지 않는다(S1 10-10)
        비용: push 와 같음 / CP: 바꾸지 않음 / 로컬: 공유 안전
        epScript: 쓰지 않는다(job().layer() 사슬)
        출처: GCB 2266~2293 G_CB_Shapes
        """
        us = list(unit_list) if isinstance(unit_list, (list, tuple)) else [unit_list]
        if not us:
            fail("spawn.push_multi: 유닛이 없습니다")
        ss = list(shapes) if isinstance(shapes, (list, tuple)) and not isinstance(shapes, Shape) else [shapes] * len(us)
        if len(us) != len(ss):
            fail("spawn.push_multi: 유닛 %d개와 도형 %d개의 수가 다릅니다 (도형 하나만 주면 모든 층에 쓴다)", len(us), len(ss))
        return self.push_layers(list(zip(us, ss)), **kw)

    def scan_effect(self, shape, image, color=None, owner=None, center=None, lm="max", **kw):
        """스캔 이펙트 작업을 넣는다(원본 G_CB_TScanEff) = `push(33, shape, effect=Effect.scan(image, color), …)`.

        인자: shape(Shape·sid 또는 그 목록 — 도형마다 층 하나), image, color, owner(None = default_owner, 기본 P8), center, lm,
              kw(job 인자: delay·size·rotate·offset …)
        반환: 첫 층 핸들
        비용: push 와 같음 + Effect 설명
        CP: 바꾸지 않음 / 로컬: 공유 안전
        epScript: `sp.scan_effect(ring, 429, color=16, center="Boss");`
        출처: GCB 2115~2150
        """
        job = Job(self, owner=owner, center=center, effect=Effect.scan(image, color), lm=lm, **kw)
        for s in (shape if isinstance(shape, (list, tuple)) and not isinstance(shape, Shape) else [shape]):
            job.layer(UNIT_SCAN, s)
        return job.push()

    def _resolve_xy(self, c, fname, what):
        """center·명령 목표 → (x, y) 상수/변수. 로케이션은 지금 중심."""
        c = unProxy(c)
        if isinstance(c, bytes):
            c = c.decode("utf-8")
        if isinstance(c, AtUnit):
            return self._posread(c.epd)
        if isinstance(c, (list, tuple)):
            if len(c) != 2:
                fail("%s: %s (x, y) 는 두 값이어야 합니다 (%r)", fname, what, c)
            return _num(c[0], fname, what + " x"), _num(c[1], fname, what + " y")
        if isinstance(c, str) or _is_int(c):
            n = _loc_num(c, fname, what + " 로케이션")
            return plot.f_loc_center(n)
        if _compat.is_var(c) or _compat.is_varbase(c):
            return plot.f_loc_center(c)
        fail("%s: %s 는 (x, y), 로케이션(이름·1부터 번호), 번호 변수, at_unit 중 하나입니다 (%r)", fname, what, c)

    def _emit_push(self, jkw, layers):
        fname = "spawn.push"
        if not layers:
            fail("%s: 층이 없습니다 (job().layer(…) 를 먼저)", fname)
        if len(layers) > self.capacity:
            fail("%s: 층 %d개가 capacity %d 보다 많습니다", fname, len(layers), self.capacity)
        if jkw.get("rot3d"):
            fail("%s: rot3d(3D 회전)는 2단계 기능입니다 (S1 8.7)", fname)
        effect = unProxy(jkw.get("effect"))
        if effect is not None and not isinstance(effect, Effect):
            fail("%s: effect 는 Effect.scan(…) 이어야 합니다 (%r)", fname, effect)
        order_ = unProxy(jkw.get("order"))
        if order_ is not None and not isinstance(order_, Order):
            fail("%s: order 는 Order.attack/patrol/move(…) 이어야 합니다 (%r)", fname, order_)
        off = unProxy(jkw.get("offset"))
        if off is None:
            off = (0, 0)
        if not isinstance(off, (list, tuple)) or len(off) != 2:
            fail("%s: offset 은 (dx, dy) 여야 합니다 (%r)", fname, off)
        # 층 인자 먼저 검사 (코드를 내기 전에)
        plans = []
        for li, (unit, shape, lkw) in enumerate(layers):
            kw = {k: v for k, v in jkw.items() if k in _LAYER_KEYS and v is not None}
            kw.update({k: v for k, v in lkw.items() if v is not None})
            if kw.get("variant") is not None:
                fail("%s: variant(프리펑션 변형)는 2단계 기능입니다 (DESIGN 7절 D14)", fname)
            if kw.get("mirror"):
                fail("%s: mirror(점대칭 소환)는 2단계 기능입니다 (S1 8.7)", fname)
            if effect is not None:
                u = unProxy(unit)
                if not (u is None or (_is_int(u) and u == UNIT_SCAN) or u == "Scanner Sweep"):
                    fail("%s: effect=scan 작업의 유닛은 33(Scanner Sweep)이어야 합니다 (%r)", fname, unit)
                unit = UNIT_SCAN
            plans.append(self._plan_layer(li, unit, shape, kw, effect is not None, fname))
        if effect is not None:
            self._mark("effect", "effect=scan")
        # 작업 공통 값 (넣는 순간 해석)
        cen = unProxy(jkw.get("center"))
        if cen is None:
            cx, cy = self._anchor.x, self._anchor.y
        else:
            cx, cy = self._resolve_xy(cen, fname, "center")
        dx, dy = _num(off[0], fname, "offset dx"), _num(off[1], fname, "offset dy")
        okind, ox, oy = 0, 0, 0
        if order_ is not None:
            okind = order_.kind + 1
            ox, oy = self._resolve_xy(order_.target, fname, "명령 목표")
        eff = 0 if effect is None else _eff_value(effect)
        inits = []
        for li, p in enumerate(plans):
            flags = p["flags"] | (okind << 2)
            if li + 1 < len(plans):
                flags |= F_NEXT
            if effect is not None:
                flags = (flags & ~F_POST) | F_EFFECT
            elif okind or self.on_create is not None:
                flags |= F_POST
            if p["sid_var"] is not None:
                self._runtime_layer(p)
            inits.append(dict(unit=_u32(p["unit"]), owner=p["owner"], rtype=p["rtype"], pc=p["pc"], left=p["n"],
                              sp=p["sp"], se=p["se"], w=0 if li == 0 else INF_WAIT, lm=p["lm"], delay=_u32(p["delay"]),
                              size=_u32(p["size"]), rot=p["rot"], flags=flags, cx=_u32(cx), cy=_u32(cy),
                              dx=_u32(dx), dy=_u32(dy), ox=_u32(ox), oy=_u32(oy), eff=eff))
        hs = self.pool.alloc_n(len(plans), inits=inits)
        return hs[0]

    def _plan_layer(self, li, unit, shape, kw, is_effect, fname):
        what = "%s 층 %d" % (fname, li + 1)
        p = {}
        p["unit"] = _unit_arg(unit, what)
        owner = kw.get("owner")
        p["owner"] = self._default_owner if owner is None else _owner_arg(owner, what)
        # 도형
        s = unProxy(shape)
        if isinstance(s, (list, tuple)) and not isinstance(s, Shape):
            fail("%s: 도형 자리에 목록이 왔습니다 — 여러 층은 job().layer() 또는 push_multi 를 쓴다 (%r)", what, s)
        if s is None:
            fail("%s: 도형이 없습니다", what)
        sid = self.shapes.resolve(s, what)
        p["sid_var"] = None
        if _is_int(sid):
            st, n, sc = self.shapes.lookup(sid)
            if n == 0:
                fail("%s: 도형 %d 에 점이 없습니다 (원본은 'G_CBPlot Not Found' 문구 뒤 버리던 작업 — S1 9.1 P)", what, sid)
            p["pc"], p["n"] = st, n
            sched = self.shapes[sid].schedule
            if sched is not None:
                p["sp"], p["se"] = sc + 1, sc + len(sched)
            else:
                p["sp"], p["se"] = 0, 0
        else:
            p["sid_var"] = sid
            p["pc"], p["n"], p["sp"], p["se"] = (EUDVariable() for _ in range(4))
        # lm
        lm = unProxy(kw.get("lm", "max"))
        if isinstance(lm, bytes):
            lm = lm.decode("utf-8")
        p["lm_mode"] = None
        if isinstance(lm, str):
            check_choice(what + " lm", lm.lower(), ("max",))
            p["lm"] = LM_MAX
        elif _is_int(lm) or isinstance(lm, bool):
            lmv = _num(lm, what, "lm", 0, LM_MAX)
            if lmv == 0:
                if p["sid_var"] is None:
                    p["lm"] = p["n"] // 50 + 1
                else:
                    p["lm"] = EUDVariable()
                    p["lm_mode"] = "auto"
            else:
                p["lm"] = lmv
        else:
            src = _num(lm, what, "lm")
            v = EUDVariable()
            v << src
            p["lm"] = v
            p["lm_mode"] = "var"
        p["delay"] = _num(kw.get("delay", 0), what, "delay", 0, M32)
        p["size"] = _num(kw.get("size", 100), what, "size", 0, 0x7FFFFFFF)
        if not (_is_int(p["size"]) and p["size"] == 100):
            self._mark("size", "size")
        rot = unProxy(kw.get("rotate", 0))
        p["flags"] = 0
        if rot is GLOBAL:
            p["rot"] = 0
            p["flags"] |= F_GLOBAL
            self._mark("rot", "rotate=GLOBAL")
        else:
            p["rot"] = _u32(_num(rot, what, "rotate"))
            if not (_is_int(p["rot"]) and p["rot"] == 0):
                self._mark("rot", "rotate")
        rt = kw.get("rtype")
        if is_effect:
            p["rtype"] = 0
        else:
            rid = self._default_rtype if rt is None else self.rtype_id(rt)
            p["rtype"] = rid
            if not _is_int(rid) or (rid and self._rtype_by_id[rid].handlers) or (rid and self.debug):
                p["flags"] |= F_POST
        if p["lm_mode"] == "var":
            # 변수 lm 이 0 이면 자동 (상수 도형은 여기서, 변수 도형은 _runtime_layer 에서)
            if p["sid_var"] is None:
                if EUDIf()(p["lm"].Exactly(0)):
                    p["lm"] << p["n"] // 50 + 1
                EUDEndIf()
        return p

    def _runtime_layer(self, p):
        """변수 sid: 표를 읽어 커서·점 수·스케줄을 채우고, lm 자동이면 n//50+1."""
        sid = p["sid_var"]
        st, n, sc = self.shapes.lookup(sid)
        nb = EUDVariable()
        SeqCompute([(p["pc"], SetTo, st), (p["n"], SetTo, n), (p["sp"], SetTo, 0), (p["se"], SetTo, 0)])
        if EUDIf()(sc.AtLeast(1)):
            f_dwread_epd(sc, ret=[nb])
            SeqCompute([(p["sp"], SetTo, sc), (p["sp"], Add, 1), (p["se"], SetTo, sc), (p["se"], Add, nb)])
        EUDEndIf()
        mode = p["lm_mode"]
        if mode is not None:
            cond = p["lm"].Exactly(0)
            if mode == "auto" or EUDIf()(cond):
                q = mathx.sdiv(p["n"], 50)
                SeqCompute([(p["lm"], SetTo, q), (p["lm"], Add, 1)])
            if mode == "var":
                EUDEndIf()
        if self.debug:
            if EUDIf()(p["n"].Exactly(0)):
                self._say("\x07『 \x03TESTMODE OP \x04: %s: 점이 없는 도형이라 작업을 바로 끝냅니다 \x07』" % self.name)
            EUDEndIf()

    # ------------------------------------------------------------------ 소환 부품
    def _box(self, loc, x, y, half):
        """로케이션 loc 을 (x−half, y−half, x+half, y+half) 로."""
        if _is_int(x) and _is_int(y):
            DoActions([SetMemory(MRGN_ADDR + 20 * (loc - 1) + 4 * k, SetTo, v & M32)
                       for k, v in enumerate((x - half, y - half, x + half, y + half))])
            return
        base = MRGN_EPD + 5 * (loc - 1)
        pairs = [(base, SetTo, x), (base + 1, SetTo, y), (base + 2, SetTo, x), (base + 3, SetTo, y)]
        if half:
            pairs += [(base, Add, -half & M32), (base + 1, Add, -half & M32), (base + 2, Add, half), (base + 3, Add, half)]
        SeqCompute([(d, m, _u32(v)) for d, m, v in pairs])

    def _posread(self, epd):
        """유닛 EPD → (x, y) 새 변수 (맵 크기 마스크로 +0x28 을 읽는다)."""
        if self._posread_fn is None:
            W, H = self.map_size
            mx = (1 << max(1, (W - 1).bit_length())) - 1
            my = (1 << max(1, (H - 1).bit_length())) - 1
            self._posread_fn = f_readgen_epd(
                (mx & 0xFFFF) | ((my & 0xFFFF) << 16),
                (0, lambda b: b if b <= 0xFFFF else 0),
                (0, lambda b: b >> 16),
            )
        e = unProxy(epd)
        t = EUDVariable()
        # VProc 의 앞 액션은 변수 트리거보다 먼저 돈다 → t = 10 을 먼저, 변수 트리거가 e 를 더한다
        VProc(e, [t.SetNumber(CU_POS // 4), *e.QueueAddTo(t)])
        x, y = EUDVariable(), EUDVariable()
        self._posread_fn(t, ret=[x, y])
        return x, y

    def _uo_action(self, act, acttype, amount):
        """유닛·주인 칸을 작업 값(J.unit, J.owner)으로 채워 액션 하나를 실행한다(실행 2)."""
        J = self._J
        VProc([J["unit"], J["owner"]], [*J["unit"].QueueAssignTo(EPD(act) + 6), *J["owner"].QueueAssignTo(EPD(act) + 4)])
        RawTrigger(actions=[SetMemory(act + 24, Add, (acttype << 16) | (amount << 24)), act])

    def _cunit_write(self, epd, items):
        """CUnit 칸 쓰기: CP ← epd, CP 상대 SetDeathsX 들, 끝에 CP 캐시로 되돌림 (DESIGN 3.6-7). 실행 약 4(+ 변수 값)."""
        e = unProxy(epd)
        acts = []
        cur = 0
        for item in sorted(items, key=lambda it: it[0]):
            off, val, nbytes = item[:3]
            k, sub = divmod(off, 4)
            if k != cur:
                acts.append(SetMemory(CP_ADDR, Add, (k - cur) & M32))
                cur = k
            mask = item[3] if len(item) > 3 else (((1 << (8 * nbytes)) - 1) << (8 * sub)) & M32
            if _is_int(val):
                acts.append(SetDeathsX(CurrentPlayer, SetTo, (val << (8 * sub)) & M32, 0, mask))
            else:
                if sub:
                    v2 = EUDVariable()
                    v2 << val
                    v2 <<= 8 * sub
                    val = v2
                acts.append(SetDeathsX(CurrentPlayer, SetTo, val, 0, mask))
        VProc(e, e.QueueAssignTo(CP_EPD))
        DoActions(acts)
        f_setcurpl2cpcache()

    def _load_job_common(self, call_trig, after):
        """사이클 머리 공통(tick·spawn_now): 소환 루틴 고르기, 명령 워드, 생성 액션 패치, 이펙트 준비.

        call_trig 는 점마다 소환 루틴으로 뛰는 트리거, after 는 돌아올 곳. 사이클마다 한 번 고르므로 점마다 분기가 없다.
        """
        J = self._J
        ps = self._psubs
        plain = ps["post"] if self.on_create is not None else ps["plain"]
        RawTrigger(actions=[*(SetNextPtr(sub.ret, after) for sub in ps.values()), SetNextPtr(call_trig, plain.entry)])
        RawTrigger(conditions=_bit(J["flags"], F_POST), actions=SetNextPtr(call_trig, ps["post"].entry))
        RawTrigger(conditions=_bit(J["flags"], F_EFFECT), actions=SetNextPtr(call_trig, ps["eff"].entry))
        ow = J["ouword"]
        SeqCompute([(ow, SetTo, J["unit"])])
        for code, sc_kind in ((1, 0), (2, 1), (3, 2)):
            RawTrigger(conditions=J["flags"].ExactlyX(code << 2, F_ORDER),
                       actions=ow.AddNumber((ACT_ORDER << 16) | (sc_kind << 24)))
        adds = []
        for act, ctype in self._create_acts:
            VProc([J["unit"], J["owner"]],
                  [*J["unit"].QueueAssignTo(EPD(act) + 6), *J["owner"].QueueAssignTo(EPD(act) + 4)])
            adds.append(SetMemory(act + 24, Add, (ctype << 16) | (1 << 24)))
        RawTrigger(actions=adds)
        if EUDIf()(_bit(J["flags"], F_EFFECT)):
            _parts.call_sub(self._xsubs[2])
        EUDEndIf()

    def _end_job_common(self):
        """사이클 끝 공통: 이펙트 색 되돌리기."""
        _parts.call_sub(self._xsubs[3], conds=[_bit(self._J["flags"], F_EFFECT), self._ehas.Exactly(1)])

    def _mark(self, feature, what):
        """기능을 쓴다고 기록한다. 변환 서브루틴을 이미 채운 뒤(주 함수 생성 뒤)면 컴파일 오류."""
        if self._need[feature]:
            return
        if self._xdefined:
            fail("spawn %s: %s(%s)을 쓰는 코드가 주 함수를 다 만든 뒤에 나왔습니다 — 이 기능의 코드를 넣지 않았습니다",
                 self.name, what, feature)
        self._need[feature] = True

    def _ensure_xsubs(self):
        """크기·회전·이펙트 서브루틴: 자리(SubLabel)는 지금, 본문은 주 함수를 다 만든 뒤 쓰인 기능만 채운다."""
        if self._xsubs is not None:
            return self._xsubs
        self._xsubs = tuple(_parts.SubLabel("%s.%s" % (self.name, n)) for n in ("size", "rot", "eff_begin", "eff_end"))
        if _compat.onstart_phase() < 2:
            _compat.on_start_after_main(self._define_xsubs)
        else:
            for k in self._need:
                self._need[k] = True
            self._define_xsubs()
        return self._xsubs

    def _define_xsubs(self):
        if self._xdefined:
            return
        self._xdefined = True
        size_sub, rot_sub, eb_sub, ee_sub = self._xsubs
        px, py, J = self._px, self._py, self._J
        with size_sub.define():
            if self._need["size"]:
                mathx.ratio(px, self._S, 100, div0="ctrig", ret=[px])
                mathx.ratio(py, self._S, 100, div0="ctrig", ret=[py])
        with rot_sub.define():
            if self._need["rot"]:
                if EUDIf()(_bit(J["flags"], F_GLOBAL)):
                    self._rot.set(self._rotation)
                EUDEndIf()
                self._rot(px, py, ret=[px, py])
        with eb_sub.define():
            if self._need["effect"]:
                self._emit_effect_begin()
        with ee_sub.define():
            if self._need["effect"]:
                f_bwrite_epd(self._eepd, self._esub, self._eold)

    def _emit_effect_begin(self):
        """eff = 이미지 | 색 << 16 | 색 있음 << 24 → 이미지, 색, Draw Function 칸(EPD, 바이트) + 액션 패치 + 색 바꾸기."""
        J = self._J
        t = EUDVariable()
        t << J["eff"]
        img, col, epd, sub = self._eimg, self._ecol, self._eepd, self._esub
        RawTrigger(actions=[img.SetNumber(0), col.SetNumber(0), epd.SetNumber(DRAW_FUNC_EPD), sub.SetNumber(0),
                            self._ehas.SetNumber(0)])
        RawTrigger(conditions=t.AtLeast(1 << 24), actions=[t.SubtractNumber(1 << 24), self._ehas.SetNumber(1)])
        for b in range(23, -1, -1):
            # 조건 t ≥ 2^b 가 보장하므로 Subtract(포화)가 wrap 과 같다 (DESIGN 3.5-7)
            acts = [t.SubtractNumber(1 << b)]
            if b >= 16:
                acts.append(col.AddNumber(1 << (b - 16)))
            else:
                acts.append(img.AddNumber(1 << b))
                acts.append(epd.AddNumber(1 << (b - 2)) if b >= 2 else sub.AddNumber(1 << b))
            RawTrigger(conditions=t.AtLeast(1 << b), actions=acts)
        set_img, create, kill, _restore = self._scan_acts
        VProc([img, J["owner"]], [*img.QueueAssignTo(EPD(set_img) + 5), *J["owner"].QueueAssignTo(EPD(create) + 4)])
        VProc(J["owner"], J["owner"].QueueAssignTo(EPD(kill) + 4))
        if EUDIf()(self._ehas.Exactly(1)):
            f_bread_epd(epd, sub, ret=[self._eold])
            f_bwrite_epd(epd, sub, col)
        EUDEndIf()

    def _ensure_point(self):
        """소환 루틴 세 벌(후처리 없음 · 후처리 · 이펙트)을 만든다. 템플릿 액션의 유닛·주인은 사이클 머리에서 채운다."""
        if self._psubs is not None:
            return
        J = self._J
        loc = self.loc
        props = self.props
        ps = {n: _parts.SubLabel("%s.point_%s" % (self.name, n)) for n in ("plain", "post", "eff")}
        self._psubs = ps
        self._point_sub = ps["post"]  # 등록 마감 표시 (_check_open)
        self._create_acts = []

        def create(unit):
            if props is None:
                return CreateUnit(1, unit, loc, 0), ACT_CREATE
            return CreateUnitWithProperties(1, unit, loc, 0, props), ACT_CREATE_PROPS

        with ps["plain"].define():
            if self.on_create is None:
                self._box(loc, self._px, self._py, 0)
                act, ctype = create(0)
                self._create_acts.append((act, ctype))
                RawTrigger(actions=act)
        with ps["post"].define():
            self._box(loc, self._px, self._py, 0)
            act, ctype = create(0)
            self._create_acts.append((act, ctype))
            self._cap.begin()
            if self.on_create is not None:
                self._call_on_create()
            RawTrigger(actions=act)
            self._cap.end()
            if EUDIf()(self._cap.ok):
                self._emit_post()
            EUDEndIf()
        with ps["eff"].define():
            self._box(loc, self._px, self._py, 0)
            scan_create, _ctype = create(UNIT_SCAN)
            set_img = SetMemoryX(SCAN_SPRITE_IMAGE, SetTo, 0, 0xFFFF)
            kill = KillUnit(UNIT_SCAN, 0)
            restore = SetMemoryX(SCAN_SPRITE_IMAGE, SetTo, SCAN_SPRITE_IMAGE_DEFAULT, 0xFFFF)
            self._scan_acts = (set_img, scan_create, kill, restore)
            RawTrigger(actions=[set_img, scan_create, kill, restore])
        if self._reentry:
            what = ", ".join(sorted(set(self._reentry)))
            self._reentry = []
            fail("spawn %s: 핸들러(소환 서브루틴) 안에서 같은 Spawner 의 %s 를 불렀습니다 (재진입 금지 — DESIGN 3.3)",
                 self.name, what)

    def _point_call(self):
        """점마다 소환 루틴으로 뛰는 트리거(대상은 사이클 머리가 고른다). 반환: (call 트리거, 돌아올 곳)."""
        after = Forward()
        trig = RawTrigger(nextptr=self._psubs["plain"].entry)
        after << NextTrigger()
        return trig, after

    def _call_on_create(self):
        oc = self.on_create
        if isinstance(oc, (units.UnitData, list, tuple)):
            for d in (oc if isinstance(oc, (list, tuple)) else [oc]):
                if not isinstance(d, units.UnitData):
                    fail("spawn %s: on_create 목록에는 UnitData 만 (%r)", self.name, d)
                d.clear(self._cap.index)
        else:
            oc(self._cap.index)

    def _emit_post(self):
        J = self._J
        ctx = self.ctx
        cases = [rid for rid in sorted(self._rtype_by_id) if self._rtype_by_id[rid].handlers or self.debug]
        if cases or self.debug:
            EUDSwitch(J["rtype"])
            for rid in cases:
                rt = self._rtype_by_id[rid]
                if EUDSwitchCase()(rid):
                    self._in_point = True
                    try:
                        for h in rt.handlers:
                            self._call_handler(h, ctx)
                    finally:
                        self._in_point = False
                    EUDBreak()
            if self.debug:
                if EUDSwitchCase()(0):
                    EUDBreak()
                if EUDSwitchDefault()():
                    self._say("\x07『 \x08ERROR : \x04%s: 등록되지 않은 rtype 값이 들어와 아무것도 하지 않았습니다.\x07 』"
                              % self.name, 1)
                    EUDBreak()
            EUDEndSwitch()
        # 명령 속성 (핸들러 뒤 — 원본 Call_RepeatOption 끝)
        if EUDIfNot()(_no_bit(J["flags"], F_ORDER)):
            ctx.here()
            self._box(self.loc2, J["ox"], J["oy"], 1)
            order_act = _SCOrder(0, 0, self.loc, Move, self.loc2)
            VProc([J["ouword"], J["owner"]],
                  [*J["ouword"].QueueAssignTo(EPD(order_act) + 6), *J["owner"].QueueAssignTo(EPD(order_act) + 4)])
            RawTrigger(actions=order_act)
        EUDEndIf()

    def _call_handler(self, h, ctx):
        n = _call_n_args(h)
        if _compat.is_eudfunc(h):
            if n == 0:
                h()
            elif n == 5:
                x, y = ctx.pos()
                h(ctx.epd, self._J["unit"], self._J["owner"], x, y)
            else:
                fail("spawn %s: rtype_func 함수는 인자 5개(epd, unit, owner, x, y) 또는 0개여야 합니다 (%d개)", self.name, n)
        elif n == 0:
            h()
        else:
            h(ctx)

    # ------------------------------------------------------------------ tick
    def tick(self):
        """이번 프레임을 진행한다(매 프레임 1회). 본문은 서브루틴 한 벌, 호출 자리 트리거 1.

        인자: 없음
        반환: None
        비용: 호출 자리 1 / 실행: 빈 대기열 1, 레코드 방문마다 약 45(pool 적재 20 포함), 사이클이 도는 레코드 머리 약 55,
              점마다 "db"·후처리 없음 58 / 기본 어택 137 / 크기 +133 / 회전 +107 / 전역 회전 +97 (2026-09-17, docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `sp.tick();`
        출처: GCB 2607~2747(Call_G_CB), 1742~1991(G_CBPlot), CAPI 216~411
        """
        if self._in_point:
            self._reentry.append("tick()")
            return
        if self._tick_sub is None:
            self._ensure_point()
            self._ensure_xsubs()
            self._tick_sub = _parts.SubLabel(self.name + ".tick")
            self._building_tick = True
            try:
                with self._tick_sub.define():
                    self._emit_tick()
            finally:
                self._building_tick = False
        self._ticks += 1
        if self._ticks > 1:
            warn("spawn %s: tick() 을 %d 곳에서 부릅니다 — 한 프레임에 여러 번 실행되면 여러 프레임이 흐릅니다",
                 self.name, self._ticks)
        # 살아 있는 레코드가 없으면 서브루틴에 들어가지 않는다 (빈 대기열 실행 1~2).
        # free_current 한 레코드는 같은 순회에서 목록에서 빠지므로 count == 0 이면 목록도 비었다(pool 규칙).
        _parts.call_sub(self._tick_sub, conds=self.pool.count.AtLeast(1))

    def _emit_tick(self):
        J = self._J
        W, H = self.map_size
        shapes = self.shapes
        rot = self._rot
        px, py = self._px, self._py
        L, k = self._L, self._k
        carry = self._carry
        size_sub, rot_sub = self._xsubs[:2]
        RawTrigger(actions=carry.SetNumber(0))
        for g in self.pool.each():
            w = g.w
            RawTrigger(conditions=carry.Exactly(1), actions=[carry.SetNumber(0), w.SetNumber(2)])
            if EUDIf()(w.Exactly(0)):
                # 이번 사이클 점 수 L
                if EUDIf()(g.sp.AtLeast(1)):
                    f_dwread_epd(g.sp, ret=[L])
                    RawTrigger(conditions=cmp.gt(g.se, g.sp), actions=g.sp.AddNumber(1))
                if EUDElse()():
                    SeqCompute([(L, SetTo, g.lm)])
                EUDEndIf()
                SeqCompute([(k, SetTo, g.left)])
                if EUDIf()(cmp.gt(k, L)):
                    SeqCompute([(k, SetTo, L)])
                EUDEndIf()
                if EUDIf()(k.AtLeast(1)):
                    SeqCompute([
                        (J["unit"], SetTo, g.unit), (J["owner"], SetTo, g.owner), (J["rtype"], SetTo, g.rtype),
                        (J["flags"], SetTo, g.flags), (J["cx"], SetTo, g.cx), (J["cy"], SetTo, g.cy),
                        (J["ox"], SetTo, g.ox), (J["oy"], SetTo, g.oy), (J["eff"], SetTo, g.eff),
                        (self._tx, SetTo, g.cx), (self._tx, Add, g.dx), (self._ty, SetTo, g.cy), (self._ty, Add, g.dy),
                        (self._S, SetTo, g.size),
                    ])
                    fx = self._fxf
                    RawTrigger(actions=[self._fsize.SetNumber(1), self._frot.SetNumber(1), fx.SetNumber(1)])
                    RawTrigger(conditions=g.size.Exactly(100), actions=self._fsize.SetNumber(0))
                    RawTrigger(conditions=[g.rot.Exactly(0), _no_bit(g.flags, F_GLOBAL)],
                               actions=self._frot.SetNumber(0))
                    RawTrigger(conditions=[self._fsize.Exactly(0), self._frot.Exactly(0)], actions=fx.SetNumber(0))
                    if EUDIf()([self._frot.Exactly(1), _no_bit(g.flags, F_GLOBAL)]):
                        rot.set(g.rot)
                    EUDEndIf()
                    call_trig, after = Forward(), Forward()
                    self._load_job_common(call_trig, after)
                    if EUDWhile()(k.AtLeast(1)):
                        shapes.read_at(g.pc, ret=[px, py])
                        if EUDIf()(fx.Exactly(1)):
                            _parts.call_sub(size_sub, conds=self._fsize.Exactly(1))
                            _parts.call_sub(rot_sub, conds=self._frot.Exactly(1))
                        EUDEndIf()
                        SeqCompute([(px, Add, self._tx), (py, Add, self._ty)])
                        if EUDIf()([px.AtMost(W - 1), py.AtMost(H - 1)]):
                            t_, a_ = self._point_call()
                            call_trig << t_
                            after << a_
                        EUDEndIf()
                        # left ≥ k ≥ 1 이므로 Subtract(포화)가 wrap 과 같다 (DESIGN 3.5-7)
                        DoActions([g.pc.AddNumber(shapes.step), k.SubtractNumber(1), g.left.SubtractNumber(1)])
                    EUDEndWhile()
                    self._end_job_common()
                EUDEndIf()
                SeqCompute([(w, SetTo, g.delay)])
                if EUDIf()(g.left.Exactly(0)):
                    RawTrigger(conditions=_bit(g.flags, F_NEXT), actions=carry.SetNumber(1))
                    self.pool.free_current()
                EUDEndIf()
            EUDEndIf()
            DoActions(w.SubtractNumber(1))  # 포화 (0 에서 멈춤)

    # ------------------------------------------------------------------ 바로 소환
    def spawn_now(self, unit, count=1, owner=None, at=None, rtype=None, order=None, effect=None):
        """대기열을 거치지 않고 지금 count 기를 한 자리에 만든다(원본 f_TempRepeat / f_TempRepeatX).

        인자: unit(이름·번호·변수), count(0~ 상수·변수), owner(None = default_owner), at(center 와 같은 모양 — None = 그때의 anchor,
              로케이션 이름은 **그 로케이션**(원본의 한 칸 앞 오프바이원 S1 10-18 없음)), rtype, order, effect — push 와 같은 뜻.
              경계 검사는 하지 않는다(원본과 같음).
        반환: None
        비용: 호출 자리 약 20 / 실행 한 기 31(후처리 없음)·110(기본 어택), 기마다 소환 루틴(2026-09-17)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `sp.spawn_now(37, count=5, owner=P8, at="Boss", rtype="Skill");`
        출처: GCB 954~1163, 1165~1175, 636~950 (직접 소환 경로)
        """
        fname = "spawn.spawn_now"
        if self._in_point:
            self._reentry.append("spawn_now()")
            return
        self._ensure_point()
        self._ensure_xsubs()
        effect = unProxy(effect)
        if effect is not None and not isinstance(effect, Effect):
            fail("%s: effect 는 Effect.scan(…) 이어야 합니다 (%r)", fname, effect)
        order_ = unProxy(order)
        if order_ is not None and not isinstance(order_, Order):
            fail("%s: order 는 Order.attack/patrol/move(…) 이어야 합니다 (%r)", fname, order_)
        u = _unit_arg(UNIT_SCAN if effect is not None else unit, fname)
        o = self._default_owner if owner is None else _owner_arg(owner, fname)
        cnt = _num(count, fname, "count", 0, M32)
        flags = 0
        rid = 0
        if effect is None:
            rid = self._default_rtype if rtype is None else self.rtype_id(rtype)
            if (not _is_int(rid) or (rid and (self._rtype_by_id[rid].handlers or self.debug))
                    or order_ is not None or self.on_create is not None):
                flags |= F_POST
        else:
            flags |= F_EFFECT
            self._mark("effect", "effect=scan")
        if at is None:
            X, Y = self._anchor.x, self._anchor.y
        else:
            X, Y = self._resolve_xy(at, fname, "at")
        ox = oy = 0
        if order_ is not None:
            flags |= (order_.kind + 1) << 2
            ox, oy = self._resolve_xy(order_.target, fname, "명령 목표")
        eff = 0 if effect is None else _eff_value(effect)
        J = self._J
        n = EUDVariable()
        SeqCompute([(J["unit"], SetTo, _u32(u)), (J["owner"], SetTo, _u32(o)), (J["rtype"], SetTo, _u32(rid)),
                    (J["flags"], SetTo, flags), (J["cx"], SetTo, _u32(X)), (J["cy"], SetTo, _u32(Y)),
                    (J["ox"], SetTo, _u32(ox)), (J["oy"], SetTo, _u32(oy)), (J["eff"], SetTo, _u32(eff)),
                    (self._px, SetTo, _u32(X)), (self._py, SetTo, _u32(Y)), (n, SetTo, _u32(cnt))])
        call_trig, after = Forward(), Forward()
        self._load_job_common(call_trig, after)
        if EUDWhile()(n.AtLeast(1)):
            t_, a_ = self._point_call()
            call_trig << t_
            after << a_
            DoActions(n.SubtractNumber(1))
        EUDEndWhile()
        self._end_job_common()

    # ------------------------------------------------------------------ 모두 취소
    def clear(self):
        """모든 작업(뒤 층 포함)을 반납한다. 핸들러·tick 본문 안에서는 부를 수 없다(빌드 오류).

        인자: 없음
        반환: None
        비용: 호출 자리 약 10 / 실행 고정 약 10 + 레코드마다 약 40 (3개 132, 2026-09-17)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `sp.clear();`
        출처: S1 8.2 `sp.clear()` (원본에는 없음 — 대기열 55줄 0 쓰기 관용구)
        """
        if self._in_point:
            self._reentry.append("clear()")
            return
        if self._building_tick:
            fail("spawn %s: tick 본문 안에서 clear() 를 부를 수 없습니다", self.name)
        RawTrigger(actions=self._carry.SetNumber(0))
        for _g in self.pool.each():
            self.pool.free_current()


def __getattr__(name):
    if name.startswith("f_f_"):
        fail("eudext.spawn: epScript 에서는 `spawn.%s(…)` 로 부르세요 (번역이 f_ 를 한 번 더 붙입니다)", name[4:])
    raise AttributeError("module 'eudext.spawn' has no attribute %r" % name)
