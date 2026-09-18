"""총알 — 탄막 유닛을 만들어 그 자리에서 무기를 쏘게 한다 (DESIGN 4.15, 정본 명세 `docs/spec/S4_bullet.md`).

사용자 맵의 `CreateBullet`/`CreateBulletXY`/`CreateBulletLoc`(정본 = UE_RE `Install_CBullet`)를 eudplib 방식으로 옮겼다.
원리(S4 0·3절): 빈 유닛 칸(0x628438)을 읽고 → 한 점 로케이션에 탄막 유닛을 만들고 → 그 유닛의 위치(+0x28)를
주문 목표(+0x58)에 복사하고 방향(+0x21)과 주문(+0x4D ← 135 "Attack Ground")을 쓴다. 트리거가 끝난 뒤 게임 로직이
주문 135 를 실행하며 그 유닛의 지상 무기를 쏜다(같은 프레임).

    from eudext import bullet
    from eudext.bullet import BulletKind, BulletDat

    bullet.setup(loc="eudext.bullet")                       # 총알 전용 로케이션 하나 (이름 또는 1-based 번호)
    k = BulletKind(unit=208, weapon=127, flingy=106)        # UE_RE 208번 탄막 유닛
    epd = bullet.bullet(k, P8, x, y, facing)                # 실패하면 0
    epd = bullet.bullet_to(k, P8, x, y, tx, ty)             # 목표 좌표 쪽으로 (1프레임)
    epd = bullet.bullet_at(k, P8, "Boss", facing)           # 그 로케이션에 바로
    DoActions(k.speed_actions(500) + k.time_actions(32))    # 속도·수명은 전역 dat — 패턴 시작 때 따로
    k.install()                                             # (선택) BulletDat 묶음을 시작 1회 목록에

epScript (모듈 함수는 번역에서 `f_` 가 붙는다 → `bullet.bullet(…)` 로 쓴다. `bullet.f_bullet(…)` 은 `f_f_bullet` 이 된다):

    import eudext.bullet as bullet;
    const k = bullet.BulletKind(unit=208, weapon=127, flingy=106);
    bullet.setup(loc="eudext.bullet");
    function afterTriggerExec() {
        const e = bullet.bullet(k, P8, 2048, 2048, 64);
        const e2 = bullet.bullet_to(k, P8, x, y, 2048, 2048, height=20);
        DoActions(k.speed_actions(500));
    }

## 방향 (가장 헷갈리는 곳)

- `facing` 은 **유닛이 바라보는 방향**(SC 256 방향, 0 = 위, 시계 방향)이다. 사용자 맵의 총알 flingy 는 **최고속도가 음수**라
  탄이 **facing + 128** 쪽으로 날아간다(S4 2.3). `BulletKind(reverse=True)`(기본)가 이 관례이고, `bullet_to` 는 이것을
  고려해 `atan2(출발 − 목표)` 로 방향을 구한다. 진행 방향으로 주고 싶으면 `bullet.heading_to_facing(k, 진행)`.
- `facing` 은 0~255 밖 값도 받아 하위 8비트만 쓴다(음수 −64 → 192, UE_RE 보정과 같은 값).
- `bullet_to` 의 방향 = `mathx.to_dir256(mathx.atan2(…))` — CtrigAsm `f_Atan2` + 사용자 표와 같은 값(D5, S4 6.1).
  출발 = 목표이면 atan2 가 90° → facing 128.

## 속도·수명·높이 (전역 dat)

- 속도(`flingy` 최고속도·가속도)와 수명(`weapon` removeAfter)은 전역 dat 이다. **같은 프레임에 같은 flingy/무기를 쓰는
  총알은 마지막으로 쓴 값을 함께 쓴다**(R4a A.4). 그래서 인자로 받지 않고 `k.speed_actions(v)`/`k.time_actions(t)` 로
  액션 목록을 돌려준다(패턴 시작 조건 블록에 넣는다). 변수 값은 `k.set_speed(v)`/`k.set_time(t)`.
- `reverse=True` 면 최고속도 칸에 `0xFFFFFFFF − v`(= −v−1, 사용자판 `SetFlingySpeed` 와 같은 값), 가속도 칸에 v.
- `height` 인자와 `k.height_actions(h)` 는 **units.dat elevation[만드는 유닛]**(0x663150 + 번호)에 쓴다. 사용자판은 모두
  틀린 주소(UE_RE 는 weapons attackAngle[유닛 번호] = 무기 17·18 최소 사거리)에 썼다 — 그 동작은 옮기지 않았다(S4 4.1).

## 생성 뒤 칸 패치 (recipe, S4 2.2·5.2)

| recipe | 쓰는 칸 |
|---|---|
| `"ue_re"`(기본, 정본) | +0x58 ← 위치, +0x21 ← facing, +0x4D ← 135, +0xA3 ← 0, +0xDC ← 0x200104(마스크 0x300104), +0xE4 ← 0, +0x110 ← 12 |
| `"m2"` | +0x10·+0x18·+0x1C·+0x58 ← 위치, +0x21 ← facing, +0x22 ← 127, +0x4D ← 135, +0x110 ← 30 |
| `"minimal"` (Galaxy.py) | +0x58 ← 위치, +0x21 ← facing, +0x4D ← 135 (수명은 `remove_timer` 를 줄 때만) |

`remove_timer=None` 이면 recipe 기본값, `0` 이면 쓰지 않는다. `shell=204` 면 204 로 만든 뒤 +0x64(종류)만 `unit` 으로
바꾼다(G2R·Galaxy.py 방식). `y_offset` 은 로케이션 Y 보정(UE_RE 0, M2·G2R +10, CtrigAsm −2).

## 실패와 판정

- 빈 유닛 칸이 없으면(0x628438 = 0) 아무것도 쓰지 않고 0 을 돌려준다.
- 생성이 실패하면(0x628438 이 그대로 — `units.capture` 와 같은 판정) CUnit 칸을 쓰지 않고 0 을 돌려준다.
  사용자판은 이 검사가 없어 빈 칸을 고쳤다(R4a A.8).
- 반환값은 만든 유닛의 EPD. **0 인지 먼저 확인하고** 칸 쓰기에 쓴다(EPD 0 = P1 마린 데스 칸).

## 비용 (docs/COSTS.md "bullet (WP14)")

본문은 (방식, 방향 상수/변수, recipe, y_offset, 수명, shell 여부, 높이 여부, 로케이션[, reverse]) 조합마다 1벌.
`unit`·`shell`·높이 주소는 상수 인자로 넘겨 본문을 나눠 쓴다. 호출 자리 = 인자 복사(변수 인자마다 1) + 호출.

## 주의

- CP: 바꾸지 않음(본문이 CP 를 잠깐 옮겨 칸을 쓰고 `f_setcurpl2cpcache` 로 되돌린다). 로컬: 공유 안전(공유 상태만 읽고 쓴다).
- 공유 본문은 재진입하지 않는다(EUDFunc). 스포너 콜백 안에서 부르는 것은 괜찮지만, 이 함수가 스포너를 부르지는 않는다.
- 총알 전용 로케이션(`setup`)은 부를 때마다 옮겨진다 — 다른 용도로 쓰지 않는다. Anywhere(64)는 받지 않는다.
- 스프라이트를 읽지 않는다(언리미터에서 eudplib `CSprite.from_read` 가 틀린 포인터, R4a A.6).

## 3단계: CtrigAsm 28장 스프라이트 함수 (WP21, DESIGN 4.15·4.20, R4a A)

CtrigAsm v5.5 28장(`CreateStorm`, `CreateSprite`, `ScanSprite`, `UnitSprite`, `RecallSprite`, `BulletInitSetting`,
`ScanInitSetting`, `SetScanImage`, `SetRecallImage`)을 옮겼다. 원리(R4a A.3)는 1단계와 같다 — 유닛을 만들고 칸을 고쳐
게임 로직이 스프라이트를 만들게 한다. **CtrigAsm 가이드북은 언리미터를 권장**한다(eds 에 `[unlimiter]`).

    k = bullet.CtrigKind(unit=203, unit_flingy=74, unit_sprite=229, half_air=True,       # BulletInitSetting
                         weapon=2, flingy=147, sprite=231, image=233, iscript=233, color=0)
    k.install()                                              # A.2 표를 시작 1회 목록에 (CtrigAsm 과 같은 값)
    bullet.perma_sprite(k, P8, x, y, 0, speed=0, height=h)   # CreateSprite: 투사 방식 7, 영구 스프라이트
    bullet.storm(k, P8, x, y, 0, 380, 30)                    # CreateStorm: 투사 방식 3, 이미지 iscript 236
    bullet.scan_init(); DoActions(bullet.scan_image_actions(391))
    bullet.scan_sprite(P1, x, y, count=1)                    # ScanSprite: 스캐너 스윕(33), 높이 4 고정, 0틱
    e = bullet.unit_sprite(P1, 8, x, y, height=3, time=48)   # UnitSprite: 표시용 유닛 (+0xDC·+0xE4 드래그 방지)
    bullet.unit_sprite(P1, 8, x, y, track=False)             # UnitSprite(Time="X"): 칸 연산 없음
    e = bullet.recall_sprite(P1, 86, x, y)                   # RecallSprite: 아비터가 (x, y) 에 리콜 (0틱 불가)

- `storm`/`perma_sprite` 는 부를 때마다 전역 dat(투사 방식·속도·수명·이미지 iscript)를 쓴 뒤 `bullet` 과 같은 본문을
  부른다 → 같은 프레임 같은 무기의 마지막 값이 모두에 적용된다(R4a A.4). 빈 칸이 없을 때도 dat 는 쓴다.
- CGRP 그림은 `eudext.cgrp`(`CGRPPainter` 가 `perma_sprite` 와 같은 본문을 점마다 부른다).
- 흰색(화면 출력 17) 이미지를 영구 스프라이트로 두면 42틱 뒤 튕긴다(GB 8466) — 쓰지 않는다.

출처: UE_RE `func.lua:2~117` `Install_CBullet`(정본), M2 `func.lua:2083~2342`(`Call_CBullet`, `SetBulletSpeed`,
`SetFlingySpeed`, `WeaponTimeLeft`), euddraft 0.9.10.11 플러그인 `Galaxy.py:6~61`, CtrigAsm v5.5 28장(CA:81453~81529).
DPS eudplib 이식판(a7aad90)에는 총알 코드가 없다(새로 작성). 위치 복사는 eudplib 0.81 `f_maskread_cp`(표 읽기 사슬)의
`ret=[EPD 식]` 경로로 목적지 액션 칸에 바로 쓴다(`memio/readtable.py:_cp_caller`).
3단계: CtrigAsm v5.5 `reference/MapSource/Library/CtrigAsm v5.5.lua:81159~81828`(28장), 가이드북 7868~8157·18028~18053.
"""

import functools
from collections import namedtuple

from eudplib import (
    EPD,
    Add,
    CreateUnit,
    CurrentPlayer,
    DoActions,
    EncodeLocation,
    EncodePlayer,
    EncodeUnit,
    EUDFunc,
    EUDVariable,
    Exactly,
    Forward,
    Memory,
    NextTrigger,
    RawTrigger,
    SeqCompute,
    SetDeaths,
    SetDeathsX,
    SetMemory,
    SetMemoryX,
    SetNextPtr,
    SetNextTrigger,
    SetTo,
    Subtract,
    VProc,
    f_dwread_epd,
    f_maskread_cp,
    f_setcurpl2cpcache,
    unProxy,
)

from eudext import _compat, _parts, mathx, units
from eudext import datpatch as dat
from eudext.errors import fail

__all__ = [
    "BulletDat",
    "BulletKind",
    "CtrigKind",
    "DEFAULT_LOC",
    "ORDER_CAST_RECALL",
    "ORDER_FIRE",
    "RECALL_SPRITE",
    "RECIPES",
    "SCAN_SPRITE",
    "SCAN_UNIT",
    "bullet",
    "bullet_at",
    "bullet_to",
    "f_bullet",
    "f_bullet_at",
    "f_bullet_to",
    "f_heading_to_facing",
    "f_perma_sprite",
    "f_recall_image_actions",
    "f_recall_sprite",
    "f_scan_image_actions",
    "f_scan_init",
    "f_scan_init_actions",
    "f_scan_sprite",
    "f_set_recall_image",
    "f_set_scan_image",
    "f_setup",
    "f_storm",
    "f_unit_sprite",
    "heading_to_facing",
    "perma_sprite",
    "recall_image_actions",
    "recall_sprite",
    "scan_image_actions",
    "scan_init",
    "scan_init_actions",
    "scan_sprite",
    "set_recall_image",
    "set_scan_image",
    "setup",
    "storm",
    "unit_sprite",
]

M32 = 0xFFFFFFFF
DEFAULT_LOC = "eudext.bullet"
ORDER_FIRE = 135  # CUnit orderID: Attack Ground (Infested Terran) — GB "자폭명령"
RECIPES = ("ue_re", "m2", "minimal", "ctrig")
_DEFAULT_TIMER = {"ue_re": 12, "m2": 30, "minimal": None, "ctrig": 6}
# 3단계(WP21) 상수 — CtrigAsm 28장 (CA = reference/MapSource/Library/CtrigAsm v5.5.lua)
ORDER_CAST_RECALL = 137  # RecallSprite 가 쓰는 주문 (CA:81196, R4a A.1 추측: BWAPI CastRecall)
SCAN_UNIT = 33  # Scanner Sweep (ScanSprite, CA:81342)
SCAN_SPRITE = 380  # SetScanImage 가 고치는 스프라이트 (CA:81822 0x666458 = sprites.image[380])
RECALL_SPRITE = 379  # SetRecallImage (CA:81814 0x666456 = sprites.image[379])
_CARRIER_IMAGE = 256  # BulletInitSetting 이 만드는 유닛 스프라이트의 이미지(벌처, CA:81425)
_ISCRIPT_CARRIER = 86  # CreateBullet/Storm/Sprite 가 이미지 256 에 쓰는 iscript (CA:81464)
_ISCRIPT_STORM = 236  # CreateStorm 이 지정 이미지에 쓰는 iscript (CA:81689)
_BEHAVIOR_STORM = 3  # 투사 방식 3 (CA:81686)
_BEHAVIOR_SPRITE = 7  # 투사 방식 7 (CA:81759)
_SCAN_IDLE_ORDER = 140  # ScanSprite 가 되돌리는 스캐너 대기 주문 (CA:81350)
_RECALL_TIMER = 3  # RecallSprite 수명 (CA:81197)
_POS_RECIPES = ("ue_re", "m2", "minimal", "ctrig")  # 위치(+0x28)를 읽어 +0x58 에 복사하는 recipe
# 내부 전용 recipe (BulletKind(recipe=…) 로는 고를 수 없다): "unit_sprite"(UnitSprite), "recall"(RecallSprite)

_NEXT_UNIT = units.NEXT_UNIT_ADDR  # 0x628438
_CP_ADDR = 0x6509B0
_EPD_CP = EPD(_CP_ADDR)
_MRGN = 0x58DC60  # 로케이션 표 (eudplib locf 와 같은 주소), 1-based n → +20·(n−1)
_LOC_ANYWHERE = 64
_ACT_CREATE_UNIT = 44
# 위치(+0x28) = x(word) | y(word)<<16 을 32비트 그대로 복사한다. eudplib 표 읽기 사슬의 0xFFFFFFFF 줄(게임 시작 때
# 이미 있는 트리거)을 탄다 → 실행 32 + 2, 새 트리거 0. (맵 안 좌표만 보면 0x1FFFFFFF 로 3 줄일 수 있지만 가정을 두지 않는다)
_POS_MASK = M32
_CP_POS = 10  # 위치 칸 EPD 오프셋 (0x28 // 4). 패치 트리거는 CP = epd + 10 에서 시작한다

_ELEVATION = dat.field("units", "elevation")
_TOP_SPEED = dat.field("flingy", "topSpeed")
_ACCEL = dat.field("flingy", "acceleration")
_HALT = dat.field("flingy", "haltDistance")
_REMOVE_AFTER = dat.field("weapons", "removeAfter")

_state = {"loc": DEFAULT_LOC}


def __getattr__(name):
    # epScript `bullet.f_bullet(…)` 은 `bullet.f_f_bullet(…)` 로 번역된다 → 알아볼 수 있는 안내를 낸다
    if name.startswith("f_f_"):
        fail("bullet.%s: epScript 에서는 `bullet.%s(…)` 로 부르세요 (번역이 이름 앞에 f_ 를 붙입니다)", name, name[4:])
    raise AttributeError("module 'eudext.bullet' has no attribute %r" % name)


# =============================================================================================
# 인자 검사
# =============================================================================================


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _const_int(x, fname, what, lo, hi):
    v = unProxy(x)
    if not _is_int(v):
        fail("%s: %s 는 정수 상수여야 합니다 (%r)", fname, what, x)
    if not lo <= v <= hi:
        fail("%s: %s %d 가 %d ~ %d 밖입니다", fname, what, v, lo, hi)
    return v


def _num(x, fname, what):
    """정수 상수 → 32비트 int, EUDVariable → 그대로, 읽기 전용 값 칸 → 읽은 새 변수, 상수식 → 그대로."""
    v = unProxy(x)
    if isinstance(v, bool):
        fail("%s: %s 에 bool 은 받지 않습니다", fname, what)
    if _is_int(v):
        if not -(1 << 31) <= v < (1 << 32):
            fail("%s: %s 상수 %d 가 32비트 범위 밖입니다", fname, what, v)
        return v & M32
    if isinstance(v, float):
        fail("%s: %s 에 실수 %r 는 쓸 수 없습니다", fname, what, x)
    if _compat.is_var(v):
        return v
    if _compat.is_varbase(v) or hasattr(v, "getValueAddr"):
        return f_dwread_epd(EPD(v.getValueAddr()))
    if _compat.is_const(v):
        return v
    fail("%s: %s 로 쓸 수 없는 값입니다 (%r)", fname, what, x)


def _to_var(v):
    if _compat.is_var(v):
        return v
    t = EUDVariable()
    t << v
    return t


def _owner(x, fname):
    v = unProxy(x)
    if isinstance(v, bool):
        fail("%s: owner 에 bool 은 받지 않습니다", fname)
    if _compat.is_var(v):
        return v
    try:
        p = unProxy(EncodePlayer(v))
    except Exception as e:  # noqa: BLE001 — eudplib 인코딩 오류를 한국어 안내로
        fail("%s: owner %r 를 플레이어로 바꿀 수 없습니다 (%s)", fname, x, e)
    if not _is_int(p) or not (0 <= p <= 11 or p == 13):
        fail("%s: owner 는 P1~P12 또는 CurrentPlayer 여야 합니다 (%r)", fname, x)
    return p


def _unit_id(x, fname, what):
    v = unProxy(x)
    if isinstance(v, str):
        try:
            v = unProxy(EncodeUnit(v))
        except Exception as e:  # noqa: BLE001
            fail("%s: %s 유닛 이름 %r 을(를) 찾지 못했습니다 (%s)", fname, what, x, e)
    return _const_int(v, fname, what, 0, _ELEVATION.last)


def _loc_const(x, fname, what):
    v = unProxy(x)
    if isinstance(v, (str, bytes)):
        try:
            v = unProxy(EncodeLocation(v))
        except Exception as e:  # noqa: BLE001
            fail("%s: %s 로케이션 %r 이(가) 맵에 없습니다 — 맵에 만들거나 번호(1-based)로 주세요 (%s)", fname, what, x, e)
    v = _const_int(v, fname, what + " 번호(1-based)", 1, 255)
    return v


def _loc_arg(x, fname):
    v = unProxy(x)
    if _compat.is_var(v):
        return v
    return _loc_const(v, fname, "loc")


def _resolve_setup_loc():
    loc = _loc_const(_state["loc"], "bullet", "총알 로케이션(bullet.setup)")
    if loc == _LOC_ANYWHERE:
        fail("bullet.setup: Anywhere(64) 는 총알 로케이션으로 쓸 수 없습니다 (부를 때마다 옮겨집니다)")
    return loc


def f_setup(loc=DEFAULT_LOC):
    """총알을 만들 로케이션 하나를 정한다(부를 때마다 옮겨지므로 다른 용도로 쓰지 않는다).

    인자: loc(맵의 로케이션 이름 또는 1-based 번호. 기본 "eudext.bullet" — 맵에 그 이름의 로케이션이 있어야 한다)
    반환: None
    의미: 보통 맵 코드 맨 위에서 한 번 부른다. 다시 부르면 **그 뒤에 만드는** 호출부터 새 로케이션을 쓴다(본문은 로케이션마다
          따로 만들어진다 — 앞의 호출은 앞 로케이션 그대로). 이름은 본문을 만들 때 번호로 바꾼다. Anywhere(64)는 오류.
    비용: 없음(컴파일 시점)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `bullet.setup(loc="eudext.bullet");` (→ `bullet.f_setup`, 전역 문장으로 둔다)
    출처: S4 4.6·5.1 (사용자판 `Install_CBullet` 은 로케이션 0 = 1번을 고정으로 썼다)
    """
    v = unProxy(loc)
    if _compat.is_var(v) or not (isinstance(v, (str, bytes)) or _is_int(v)):
        fail("bullet.setup: loc 는 로케이션 이름 또는 1-based 번호(상수)여야 합니다 (%r)", loc)
    if _is_int(v):
        _const_int(v, "bullet.setup", "loc", 1, 255)
        if v == _LOC_ANYWHERE:
            fail("bullet.setup: Anywhere(64) 는 총알 로케이션으로 쓸 수 없습니다 (부를 때마다 옮겨집니다)")
    _state["loc"] = v


setup = f_setup


# =============================================================================================
# 종류와 dat 묶음
# =============================================================================================


def _pos_word(v, what):
    """Position dword (아래 word = x, 위 word = y). 숫자 하나면 가로·세로가 같다, 짝이면 (가로, 세로)."""
    if isinstance(v, (tuple, list)):
        if len(v) != 2:
            fail("bullet.BulletDat: %s 는 숫자 하나이거나 (가로, 세로) 두 개여야 합니다 (%r)", what, v)
        return (int(v[0]) & 0xFFFF) | ((int(v[1]) & 0xFFFF) << 16)
    w = v & 0xFFFF
    return w | (w << 16)


class BulletDat:
    """EUD Editor 없이 탄막 유닛·무기·flingy 를 설정하는 dat 묶음(선택). 기본값은 UE_RE 208/127/106 (S4 2.6·5.4).

    ## 주의 — 기본값이 그냥 적용된다 (2026-09-18 인게임 뒤)

    `BulletKind(...)` 에 `dat=` 를 주지 않아도 recipe 의 기본 `BulletDat()` 이 붙고, `install()`(또는 `init_actions()`)
    이 **아래 칸들을 그 유닛·무기·flingy 의 dat 에 덮어쓴다**. 게임 전체가 쓰는 표라, 그 번호(유닛 208·무기 127·
    flingy 106 …)를 맵에서 **다른 용도로 쓰고 있으면 그쪽이 바뀐다**. 번호를 바꾸려면 `BulletKind(unit=…, weapon=…,
    flingy=…)`, 칸을 끄려면 그 인자에 `None` 을 준다.

      유닛(kind.unit, shell 도): flingy 88 · 고도 20 · Flyer·Invincible 켜고 Building 끔 · 충돌 상자 1,1,1,1 ·
        배치 상자 가로1 세로0 · **에디터 어빌리티 0x1CF** · 소속그룹 2 · 부가사거리 3 · 우클릭 1 ·
        대기 주문 2(컴퓨터·사람·복귀) · 공격 주문 134 · 공격이동 135 · 지상 무기 = kind.weapon
      무기(kind.weapon): flingy 106 · 방식 9 · 폭발 3 · 스플 96/96/96 · 피해 60000 · 추가피해 0 · 쿨다운 1
      flingy(weapon_flingy): 최고속도 8000(reverse 면 음수로) · 가속도 = 최고속도 · 멈춤거리 1 · 회전 127 · 이동제어 0

    **에디터 어빌리티(0x1CF)를 빼면 유닛이 하나도 만들어지지 않는다** — 문·함정 유닛(208·210·204)은 이 비트가 없어
    CreateUnit 이 거절한다(2026-09-18 인게임에서 배치 상자·충돌 상자·고도·Flyer·소속그룹·생산 가능을 다 바꿔 봐도
    이 칸 하나만 답이었다). CtrigAsm v5.5 의 탄막 설치 코드도 같은 칸을 쓴다.

    **탄이 날아가지 않으면 그림(image)의 iscript 를 본다** — `image=`·`image_iscript=`(UE_RE 는 360 → 395)·
    `image_draw=`(10). 기본값은 None 이라 건드리지 않는다. 사슬은 무기 flingy → 그 flingy 의 sprite → 그 sprite 의
    image 다. 원판에서 106→344→360 은 아무도 안 쓰는 고아 사슬이지만, **맵이 그 sprite·image 를 두들레드로 깔아
    놨거나 다른 유닛을 그 flingy 로 돌려놨으면 그림이 같이 바뀐다** — 번호를 바꾸기 전에 확인한다.

    `shell=` 로 만든 탄은 **유닛 수 표**(Command 조건이 읽는 표)에 만든 종류로 남는다 — 지워도 그 종류의 수가 줄지
    않는다(2026-09-18 인게임). 탄 개수를 `Command` 로 세지 않는다.

    인자 (None = 그 필드를 쓰지 않음):
      유닛(`kind.unit`, shell 이 있으면 shell 도): unit_flingy(88 벌처), elevation(20), flyer(True), invincible(True),
        base_property(None — 주면 특수 능력 dword 전체를 이 값으로, flyer/invincible/Building 대신. UE_RE 210 은 0x20000004),
        bounds(1 — 유닛 충돌 크기 L·U·R·D 를 모두 이 값으로. None = 쓰지 않음),
        placement((1, 0) — **배치 상자**(buildingDimensions). 숫자 하나면 가로·세로가 같고, 짝이면 (가로, 세로).
          CtrigAsm·UE_RE 가 쓰는 값이 가로1 세로0 이다. None = 쓰지 않음),
        star_edit(0x1CF — **에디터 어빌리티 플래그**. 이 칸이 없으면 CreateUnit 이 거절한다. 위 "주의" 참고),
        group_flag(2 — 소속그룹), seek_range(3 — 부가사거리), right_click(1 — 우클릭 행동),
        idle_order(2 — 컴퓨터·사람 대기·복귀 주문, UE_RE 210 은 23), attack_order(134 — 유닛 공격 주문),
        attack_move_order(135 — 공격 이동 주문. None 이면 attack_order 를 쓴다),
        image(None — 탄 그림 번호), image_iscript(None — 그 그림의 iscript, UE_RE 360 은 395),
        image_draw(None — 그 그림의 그리기 함수, UE_RE 360 은 10),
        ground_weapon(True = `kind.weapon` 을 지상 무기로. shell 에는 쓰지 않는다)
      무기(`kind.weapon`): weapon_flingy(None = `kind.flingy`), behavior(9 GoToMaxRange), explosion(3 SplashEnemy),
        splash((96, 96, 96)), damage(60000), bonus(0), cooldown(1), remove_after(None),
        attack_angle(None — UE_RE 128 은 0. **무기 번호** 칸이다 — 사용자판 높이 버그의 `0x656990 + 유닛` 과 다르다)
      flingy(weapon_flingy): sprite(None — UE_RE 106 은 344), top_speed(8000 — reverse 면 `0xFFFFFFFF − v` 로 기록),
        accel(None = top_speed), halt(1), turn(127), move_control(0)
    반환: -
    의미: `BulletKind(dat=…)` 에 주면 `k.init_actions()`(액션 목록)·`k.install()`(datpatch 시작 1회 목록)이 쓴다.
          이미지 iscript 는 `image_iscript=` 를 줄 때만 바꾼다(기본값은 건드리지 않는다).
    비용: 액션 약 30개(시작 1회 — 2026-09-18 에 에디터 어빌리티·소속그룹·부가사거리·우클릭·주문으로 7개 늘었다,
          image 칸까지 주면 +2)
    CP: 해당 없음
    로컬: 공유
    epScript: `const k = bullet.BulletKind(unit=208, weapon=127, flingy=106, dat=bullet.BulletDat(sprite=344));`
    출처: UE_RE `EUDEditorDat.lua`(208·127·106 줄), S4 5.4
    """

    _FIELDS = ("unit_flingy", "elevation", "flyer", "invincible", "base_property", "bounds", "placement",
               "star_edit", "group_flag", "seek_range", "right_click",
               "idle_order", "attack_order", "attack_move_order",
               "image", "image_iscript", "image_draw",
               "ground_weapon", "weapon_flingy", "behavior", "explosion", "splash", "damage", "bonus", "cooldown",
               "remove_after", "attack_angle", "sprite", "top_speed", "accel", "halt", "turn", "move_control")

    def __init__(self, unit_flingy=88, elevation=20, flyer=True, invincible=True, base_property=None, bounds=1,
                 placement=(1, 0), star_edit=0x1CF, group_flag=2, seek_range=3, right_click=1, idle_order=2,
                 attack_order=134, attack_move_order=135,
                 image=None, image_iscript=None, image_draw=None,
                 ground_weapon=True, weapon_flingy=None, behavior=9, explosion=3,
                 splash=(96, 96, 96), damage=60000, bonus=0, cooldown=1, remove_after=None, attack_angle=None,
                 sprite=None, top_speed=8000, accel=None, halt=1, turn=127, move_control=0):
        vals = dict(locals())
        fname = "bullet.BulletDat"
        for key in ("flyer", "invincible", "ground_weapon"):
            if not isinstance(vals[key], bool):
                fail("%s: %s 는 True/False 여야 합니다 (%r)", fname, key, vals[key])
        limits = {"unit_flingy": 208, "elevation": 255, "idle_order": 188, "attack_order": 188,
                  "attack_move_order": 188, "star_edit": 0xFFFF, "group_flag": 255, "seek_range": 255,
                  "right_click": 255, "image": 998, "image_iscript": 0xFFFFFFFF, "image_draw": 255,
                  "weapon_flingy": 208,
                  "behavior": 255, "explosion": 255, "damage": 0xFFFF, "bonus": 0xFFFF, "cooldown": 255,
                  "remove_after": 255, "attack_angle": 255, "base_property": M32, "sprite": 516,
                  "top_speed": 0x7FFFFFFF, "accel": 0xFFFF, "halt": M32, "turn": 255, "move_control": 255,
                  "bounds": 0xFFFF, "placement": 0xFFFF}
        for key, hi in limits.items():
            if vals[key] is not None and not (key == "placement" and isinstance(vals[key], (tuple, list))):
                vals[key] = _const_int(vals[key], fname, key, 0, hi)
        if isinstance(vals["placement"], (tuple, list)):
            if len(vals["placement"]) != 2:
                fail("%s: placement 는 숫자 하나이거나 (가로, 세로) 두 개여야 합니다 (%r)", fname, placement)
            vals["placement"] = tuple(_const_int(x, fname, "placement", 0, 0xFFFF) for x in vals["placement"])
        sp = vals["splash"]
        if sp is not None:
            sp = list(unProxy(sp)) if isinstance(unProxy(sp), (list, tuple)) else None
            if sp is None or len(sp) != 3:
                fail("%s: splash 는 (안, 중, 밖) 반경 세 개여야 합니다 (%r)", fname, splash)
            vals["splash"] = tuple(_const_int(r, fname, "splash", 0, 0xFFFF) for r in sp)
        for key in self._FIELDS:
            setattr(self, key, vals[key])

    def __repr__(self):
        return "BulletDat(%s)" % ", ".join("%s=%r" % (k, getattr(self, k)) for k in self._FIELDS)

    def _unit_row(self, lst, u, kind, weapon):
        row = {}
        if self.unit_flingy is not None:
            row["flingy"] = self.unit_flingy
        if self.elevation is not None:
            row["elevation"] = self.elevation
        # 2026-09-18 인게임: 이 두 칸을 안 쓰면 탄막 유닛(208·210·204 = 문·함정 = Building 플래그)이 **하나도 안 만들어진다**
        # — CreateUnit 이 배치 상자(buildingDimensions)로 자리를 검사해 거절한다(EP81 scdata/unit.py:319 주석:
        # "Building 플래그가 있는 유닛이 공간에 들어갈 수 있는지 … 31x31 이하면 물·절벽에도 지을 수 있다").
        # UE_RE EUD Editor 도 같은 칸을 쓴다(S4 2.6 "유닛 크기(unitBounds) 1, 배치 상자 0~1").
        if self.bounds is not None:
            b = _pos_word(self.bounds, "bounds")
            row["unitBoundsLT"] = b
            row["unitBoundsRB"] = b
        if self.placement is not None:
            row["buildingDimensions"] = _pos_word(self.placement, "placement")
        if weapon and self.ground_weapon and kind.weapon is not None:
            row["groundWeapon"] = kind.weapon
        # 2026-09-18 인게임에서 밝혀진 것: **에디터 어빌리티 플래그**(availabilityFlags)에 트리거 비트가 없으면
        # CreateUnit 이 그 유닛을 **하나도 만들지 못한다**(문·함정 208·210·204 가 그렇다 — 배치 상자·충돌 상자·고도·
        # Flyer 를 어떻게 바꿔도 안 되고, 이 칸만 채우면 된다). CtrigAsm v5.5 의 탄막 설치 코드(81404~81410 줄)가
        # 쓰는 값 그대로다: 에디터 어빌리티 0x1CF · 소속그룹 2 · 생산크기 가로1 세로0 · 부가사거리 3 · 우클릭 1 ·
        # 대기 주문 2 · 공격 주문 134 · 공격이동 135. (0x1C7 로도 만들어지는 것을 인게임에서 확인했다 — 두 값은
        # "플레이어 세팅" 비트 하나만 다르다.)
        for key, name in (("star_edit", "availabilityFlags"), ("group_flag", "groupFlags"),
                          ("seek_range", "seekRange"), ("right_click", "rightClickAction")):
            if getattr(self, key) is not None:
                row[name] = getattr(self, key)
        if self.idle_order is not None:
            row.update(computerIdleOrder=self.idle_order, humanIdleOrder=self.idle_order,
                       returnToIdleOrder=self.idle_order)
        if self.attack_order is not None:
            row["attackUnitOrder"] = self.attack_order
        am = self.attack_move_order if self.attack_move_order is not None else self.attack_order
        if am is not None:
            row["attackMoveOrder"] = am
        if self.base_property is not None:
            row["baseProperty"] = self.base_property
        if row:
            lst.unit(u).set(**row)
        if self.base_property is None:
            # Building 을 **끈다** — 켜져 있으면 CreateUnit 이 건물 배치 검사를 해서 만들지 못한다(2026-09-18 인게임).
            # base_property 를 직접 주면(UE_RE 0x20000004) 그 값이 Building 을 이미 0 으로 둔다.
            lst.unit(u).flags(Flyer=self.flyer, Invincible=self.invincible, Building=False)

    def _declare(self, lst, kind):
        self._unit_row(lst, kind.unit, kind, True)
        if kind.shell is not None:
            self._unit_row(lst, kind.shell, kind, False)
        wf = self.weapon_flingy if self.weapon_flingy is not None else kind.flingy
        if kind.weapon is not None:
            row = {}
            if wf is not None:
                row["flingy"] = wf
            for key, name in (("behavior", "behavior"), ("damage", "damage"), ("bonus", "damageBonus"),
                              ("cooldown", "cooldown"), ("remove_after", "removeAfter"),
                              ("attack_angle", "attackAngle")):
                if getattr(self, key) is not None:
                    row[name] = getattr(self, key)
            if row:
                lst.weapon(kind.weapon).set(**row)
            if self.splash is not None:
                lst.weapon(kind.weapon).splash(*self.splash, explosion=3 if self.explosion is None else self.explosion)
            elif self.explosion is not None:
                lst.weapon(kind.weapon).set(explosionType=self.explosion)
        if wf is None:
            if any(getattr(self, k) is not None for k in ("sprite", "top_speed", "accel", "halt", "turn", "move_control")):
                fail("bullet.BulletDat: flingy 설정이 있는데 BulletKind.flingy·weapon_flingy 가 없습니다")
            return
        row = {}
        if self.sprite is not None:
            row["sprite"] = self.sprite
        if self.top_speed is not None:
            row["topSpeed"] = (M32 - self.top_speed) if kind.reverse else self.top_speed
        accel = self.accel if self.accel is not None else self.top_speed
        if accel is not None:
            if accel > 0xFFFF:
                fail("bullet.BulletDat: 가속도 %d 가 word 범위(0~65535) 밖입니다 — accel= 을 따로 주세요", accel)
            row["acceleration"] = accel
        for key, name in (("halt", "haltDistance"), ("turn", "turnRadius"), ("move_control", "movementControl")):
            if getattr(self, key) is not None:
                row[name] = getattr(self, key)
        if row:
            lst.flingy(wf).set(**row)
        # 탄 그림(image)의 iscript — 2026-09-18 인게임: 유닛은 만들어졌는데 **탄이 날아가지 않았다**. 탄으로 쓰는
        # 이미지의 iscript 가 문 유닛 것(244)이어서다. UE_RE 는 image 360 을 iscript 395·그리기 10 으로 바꾼다.
        # 번호는 사슬을 따라간다: 무기 flingy -> 그 flingy 의 sprite -> 그 sprite 의 image. 원판에서 106→344→360 은
        # 아무도 쓰지 않는 고아 사슬이라 안전하지만, **맵이 그 image·sprite 를 이미 쓰는지 직접 확인해야 한다**.
        irow = {}
        if self.image_iscript is not None:
            irow["iscript"] = self.image_iscript
        if self.image_draw is not None:
            irow["drawingFunction"] = self.image_draw
        if irow:
            if self.image is None:
                fail("bullet.BulletDat: image_iscript·image_draw 를 주려면 image 번호도 주세요")
            lst.image(self.image).set(**irow)


class BulletKind:
    """탄막 유닛 종류(컴파일 시점 객체). 만들 유닛, 그 무기·flingy, 방향 관례, 생성 뒤 칸 패치 묶음을 정한다.

    인자: unit(만들 유닛 번호 또는 이름, 기본 208), weapon(그 유닛의 지상 무기 — 수명 액션·dat 묶음용, None 이면 그 기능 금지),
          flingy(무기 flingy — 속도 액션·dat 묶음용, None 이면 그 기능 금지), reverse(flingy 최고속도가 음수인 사용자 관례 —
          `bullet_to`·`speed_actions`·dat 묶음이 따른다, 기본 True), shell(정수면 이 유닛으로 만든 뒤 종류만 unit 으로 바꿈),
          recipe("ue_re" | "m2" | "minimal"), remove_timer(None = recipe 기본 12/30/없음, 0 = 쓰지 않음, 1~65535),
          y_offset(로케이션 Y 보정, 부호 있음), dat(BulletDat 또는 None)
    반환: -
    메서드: `speed_actions(v, halt=None)`, `time_actions(t)`, `height_actions(h)`(액션 목록),
            `set_speed(v, halt=None)`, `set_time(t)`, `set_height(h)`(그 자리 실행, 변수 가능),
            `init_actions()`(dat 묶음 액션 목록), `install()`(dat 묶음을 datpatch 시작 1회 목록에)
    비용: 없음(컴파일 시점 객체). 메서드 비용은 각 docstring
    CP: 해당 없음
    로컬: 해당 없음
    epScript: `const k = bullet.BulletKind(unit=208, weapon=127, flingy=106);` (var 가 아니라 const)
    출처: S4 5.1 (CtrigAsm 28장 `BulletInitSetting` 표 대신 사용자판처럼 번호만 든다)
    """

    __slots__ = ("unit", "weapon", "flingy", "reverse", "shell", "recipe", "remove_timer", "timer", "y_offset", "dat")

    def __init__(self, unit=208, weapon=127, flingy=106, reverse=True, shell=None, recipe="ue_re", remove_timer=None,
                 y_offset=0, dat=None):
        fname = "bullet.BulletKind"
        self.unit = _unit_id(unit, fname, "unit")
        self.weapon = None if weapon is None else _const_int(weapon, fname, "weapon", 0, _REMOVE_AFTER.last)
        self.flingy = None if flingy is None else _const_int(flingy, fname, "flingy", 0, _TOP_SPEED.last)
        if not isinstance(reverse, bool):
            fail("%s: reverse 는 True/False 여야 합니다 (%r)", fname, reverse)
        self.reverse = reverse
        self.shell = None if shell is None else _unit_id(shell, fname, "shell")
        recipe = unProxy(recipe)
        if recipe not in RECIPES:
            fail("%s: recipe 는 %s 중 하나여야 합니다 (%r)", fname, "/".join(RECIPES), recipe)
        self.recipe = recipe
        self.remove_timer = None if remove_timer is None else _const_int(remove_timer, fname, "remove_timer", 0, 0xFFFF)
        t = _DEFAULT_TIMER[recipe] if self.remove_timer is None else self.remove_timer
        self.timer = t or None  # 실제로 쓸 값 (None = 쓰지 않음)
        self.y_offset = _const_int(y_offset, fname, "y_offset", -(1 << 31), (1 << 31) - 1)
        if dat is not None and not isinstance(dat, BulletDat):
            fail("%s: dat 는 BulletDat 여야 합니다 (%r)", fname, dat)
        self.dat = dat

    def __repr__(self):
        return ("<bullet.BulletKind unit=%d weapon=%r flingy=%r reverse=%r shell=%r recipe=%s timer=%r y_offset=%d"
                " — epScript 에서는 var 가 아니라 const 로 묶으세요>"
                % (self.unit, self.weapon, self.flingy, self.reverse, self.shell, self.recipe, self.timer, self.y_offset))

    # --- 컴파일 시점 값 ---
    @property
    def made_unit(self):
        """CreateUnit 으로 만드는 유닛(shell 이 있으면 shell)."""
        return self.unit if self.shell is None else self.shell

    def _create_word(self):
        # CreateUnit 액션 +24 dword = 유닛(word) | 액션 번호(byte) << 16 | 수량(byte) << 24
        return self.made_unit | (_ACT_CREATE_UNIT << 16) | (1 << 24)

    def _need(self, what, fname):
        v = getattr(self, what)
        if v is None:
            fail("%s: 이 BulletKind 는 %s 가 None 입니다", fname, what)
        return v

    # --- 속도 ---
    def speed_actions(self, v, halt=None):
        """flingy 최고속도·가속도(·정지 거리) 액션 목록 (사용자판 `SetBulletSpeed`/`SetFlingySpeed`).

        인자: v(속도 상수 0~65535 — 가속도 칸이 word), halt(정지 거리 상수, 선택)
        반환: list[Action] — reverse 면 최고속도 ← 0xFFFFFFFF − v, 가속도 ← v (+ 정지 거리 ← halt)
        의미: 전역 dat → 같은 프레임 같은 flingy 의 총알은 마지막 값을 함께 쓴다.
        비용: 액션 2~3 (트리거 0 — 넣는 자리에서)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `DoActions(k.speed_actions(500));`
        출처: M2 func.lua:2320~2339, UE_RE func.lua:1964~1969 (S4 2.4)
        """
        fname = "BulletKind.speed_actions"
        fl = self._need("flingy", fname)
        if _compat.is_var(unProxy(v)):
            fail("%s: 변수 속도는 k.set_speed(v) 를 쓰세요", fname)
        v = _const_int(v, fname, "v", 0, 0xFFFF)
        row = {"topSpeed": (M32 - v) if self.reverse else v, "acceleration": v}
        if halt is not None:
            if _compat.is_var(unProxy(halt)):
                fail("%s: 변수 halt 는 k.set_speed(v, halt) 를 쓰세요", fname)
            row["haltDistance"] = _const_int(halt, fname, "halt", 0, M32)
        return dat.actions(lambda d: d.flingy(fl).set(**row), merge=False)

    def set_speed(self, v, halt=None):
        """그 자리에서 속도를 쓴다(값이 변수여도 된다).

        인자: v(상수 또는 변수), halt(선택, 상수 또는 변수)
        반환: None
        의미: 변수 v 는 최고속도 ← 0xFFFFFFFF, 최고속도 −= v(포화 뺄셈이지만 v ≤ 0xFFFFFFFF 라 결과가 같다 — DESIGN 3.5-7),
              가속도 ← v 의 하위 16비트. reverse=False 면 최고속도 ← v.
        비용: 상수 = 트리거 1 / 변수 = 호출 자리 3 / 실행 5. flingy 번호가 홀수면 가속도 시프트 도우미(본문 17 1벌)를 거쳐
              변수 halt 와 함께 호출 5 / 실행 28 (docs/COSTS.md)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `k.set_speed(v);`
        출처: S4 4.4·6.2
        """
        fname = "BulletKind.set_speed"
        fl = self._need("flingy", fname)
        vv = _num(v, fname, "v")
        hv = None if halt is None else _num(halt, fname, "halt")
        if _is_int(vv):
            acts = self.speed_actions(vv, hv if hv is None or _is_int(hv) else None)
        else:
            top = _TOP_SPEED.location(fl)[0]
            if self.reverse:
                acts = [SetMemory(top, SetTo, M32), SetMemory(top, Subtract, vv)]
            else:
                acts = [SetMemory(top, SetTo, vv)]
            acts.append(_var_write_action(_ACCEL, fl, vv))
            if hv is not None and _is_int(hv):
                acts += dat.actions(lambda d: d.flingy(fl).set(haltDistance=hv))
        if hv is not None and not _is_int(hv):
            acts.append(_var_write_action(_HALT, fl, hv))
        DoActions(acts)

    # --- 수명 ---
    def time_actions(self, t):
        """무기 removeAfter(탄 수명) 액션 목록 (사용자판 `WeaponTimeLeft`).

        인자: t(상수 0~255)
        반환: list[Action] (SetMemoryX 1개)
        의미: 전역 dat → 같은 프레임 같은 무기의 총알은 마지막 값을 함께 쓴다.
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `DoActions(k.time_actions(32));`
        출처: M2 func.lua:2340~2342
        """
        fname = "BulletKind.time_actions"
        w = self._need("weapon", fname)
        if _compat.is_var(unProxy(t)):
            fail("%s: 변수 수명은 k.set_time(t) 를 쓰세요", fname)
        t = _const_int(t, fname, "t", 0, 255)
        return dat.actions(lambda d: d.weapon(w).set(removeAfter=t))

    def set_time(self, t):
        """그 자리에서 무기 removeAfter 를 쓴다(값이 변수여도 된다).

        인자: t(상수 0~255 또는 변수 — 변수는 하위 8비트)
        반환: None
        비용: 상수 = 트리거 1 / 변수 = 호출 자리 3 / 실행 16 (무기 127 — 시프트 도우미 본문 9 1벌), 시프트 0 이면 호출 2 / 실행 3
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `k.set_time(t);`
        출처: S4 4.4
        """
        fname = "BulletKind.set_time"
        w = self._need("weapon", fname)
        tv = _num(t, fname, "t")
        if _is_int(tv):
            DoActions(self.time_actions(tv))
        else:
            DoActions(_var_write_action(_REMOVE_AFTER, w, tv))

    # --- 높이 ---
    def height_actions(self, h):
        """units.dat elevation[만드는 유닛](shell 이 있으면 shell) 액션 목록 — 사용자판과 달리 **올바른 주소**.

        인자: h(상수 0~255)
        반환: list[Action] (SetMemoryX 1개)
        비용: 액션 1
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `DoActions(k.height_actions(20));`
        출처: CtrigAsm 28장 CA:81467 (0x663150 + 유닛). 사용자판은 틀린 칸(S4 4.1)
        """
        fname = "BulletKind.height_actions"
        if _compat.is_var(unProxy(h)):
            fail("%s: 변수 높이는 k.set_height(h) 또는 bullet.bullet(…, height=h) 를 쓰세요", fname)
        h = _const_int(h, fname, "h", 0, 255)
        u = self.made_unit
        return dat.actions(lambda d: d.unit(u).set(elevation=h))

    def set_height(self, h):
        """그 자리에서 elevation[만드는 유닛] 을 쓴다(값이 변수여도 된다).

        인자: h(상수 0~255 또는 변수 — 변수는 하위 8비트)
        반환: None
        비용: 상수 = 트리거 1 / 변수 = 호출 자리 2 / 실행 3 (유닛 번호가 4의 배수), 아니면 시프트 도우미(본문 9 1벌) 호출 3 / 실행 16
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `k.set_height(h);`
        출처: S4 5.1 (대칭으로 더함)
        """
        fname = "BulletKind.set_height"
        hv = _num(h, fname, "h")
        if _is_int(hv):
            DoActions(self.height_actions(hv))
        else:
            DoActions(_var_write_action(_ELEVATION, self.made_unit, hv))

    # --- dat 묶음 ---
    def init_actions(self):
        """`dat=BulletDat(…)` 묶음의 액션 목록(시작 1회 구역·조건 블록용).

        인자: 없음
        반환: list[Action] (datpatch 가 같은 dword 의 SetTo 를 합친 목록)
        비용: 액션 약 20 (64개마다 트리거 1)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `DoActions(k.init_actions());`
        출처: S4 5.4
        """
        d = self._need("dat", "BulletKind.init_actions")
        return dat.actions(lambda lst: d._declare(lst, self))

    def install(self):
        """`dat=BulletDat(…)` 묶음을 datpatch 시작 1회 목록(`dat.start()`)에 선언한다.

        인자: 없음
        반환: self
        의미: 모듈을 불러올 때(빌드 밖) 부르면 빌드마다, 빌드 중에 부르면 그 빌드에만 들어간다(datpatch 규칙).
        비용: 시작 1회 트리거(64액션마다 1), 호출 자리 0
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `k.install();` (전역 문장)
        출처: S4 5.4
        """
        d = self._need("dat", "BulletKind.install")
        d._declare(dat.f_start(), self)
        return self


def _kind(k, fname):
    k = unProxy(k)
    if not isinstance(k, BulletKind):
        fail("%s: 첫 인자는 BulletKind 여야 합니다 (%r)", fname, k)
    return k


def f_heading_to_facing(k, heading):
    """진행 방향 → 유닛 방향(`bullet` 의 facing). reverse 종류면 +128, 아니면 그대로(하위 8비트).

    인자: k(BulletKind), heading(0~255 SC 방향 — 상수 또는 변수)
    반환: 0~255 — 상수면 int, 변수면 새 EUDVariable
    비용: 상수 0 / 변수 = 호출 자리 3 / 실행 5 (덧셈 + and_const)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const f = bullet.heading_to_facing(k, 64);`
    출처: S4 0절·2.3 (음수 최고속도 관례)
    """
    fname = "bullet.heading_to_facing"
    k = _kind(k, fname)
    h = _num(heading, fname, "heading")
    if _is_int(h):
        return ((h + 128) if k.reverse else h) & 0xFF
    h = _to_var(h)
    if k.reverse:
        h = h + 128
    return _parts.and_const(h, 0xFF)


heading_to_facing = f_heading_to_facing


# =============================================================================================
# 본문 (EUDFunc 조합마다 1벌)
# =============================================================================================

_Key = namedtuple("_Key", "mode facing recipe y_offset timer shell height loc reverse")

_PARAMS = {
    "own": ("owner", "x", "y", "fw", "cu"),
    "at": ("owner", "loc", "fw", "cu"),
    "to": ("owner", "x", "y", "tx", "ty", "cu"),
}


def _param_names(key):
    names = list(_PARAMS[key.mode])
    if key.facing == "none":  # 3단계: 방향을 쓰지 않는 recipe (unit_sprite·recall)
        names.remove("fw")
    if key.shell:
        names.append("fu")
    if key.height:
        names += ["ee", "ev", "em"]
    if key.recipe == "recall":  # 리콜 목표 좌표: x(own 은 x 인자를 같이 씀), y·65536
        names += ["ry"] if key.mode == "own" else ["rx", "ry"]
    if key.timer == "var":
        names.append("tm")
    return names


def _make_func(names, emit):
    # EUDFunc 는 인자 수를 함수 서명에서 읽는다 → 조합마다 서명이 다른 얇은 함수를 만든다(이름은 고정 목록에서만 온다)
    src = "def bullet_body(%s):\n    _emit(dict(zip(_names, (%s,))))\n" % (", ".join(names), ", ".join(names))
    ns = {"_emit": emit, "_names": tuple(names)}
    exec(src, ns)  # noqa: S102 — 입력은 _PARAMS 의 고정 이름뿐
    return ns["bullet_body"]


def _patch_actions(key, pos_acts, fw_act, fu_act, extra=None):
    """CP = epd + 10 에서 시작하는 칸 쓰기 액션 목록. 위치·방향·종류 칸의 값은 앞 단계가 채운다.

    extra: 3단계 recipe 의 값 칸 자리 {"rx", "ry", "tm"} (앞 단계가 채운다)
    """
    acts = []
    cp = _CP_POS

    def move(to):
        nonlocal cp
        if to != cp:
            acts.append(SetMemory(_CP_ADDR, Add, (to - cp) & M32))
            cp = to

    def at(off, value, mask=None, holder=None):
        # off = 목적지 EPD 오프셋. 지금 CP 에서 12 의 배수만큼 떨어져 있으면 unit 칸으로 닿는다
        d = off - cp
        if d < 0 or d % 12:
            move(off)
            d = 0
        act = SetDeaths(CurrentPlayer, SetTo, value, d // 12) if mask is None else \
            SetDeathsX(CurrentPlayer, SetTo, value, d // 12, mask)
        acts.append(act if holder is None else (holder << act))

    fire = ORDER_FIRE << 8
    if key.recipe == "m2":
        at(22, 0, holder=pos_acts[0])
        at(4, 0, holder=pos_acts[1])
        at(6, 0, holder=pos_acts[2])
        at(7, 0, holder=pos_acts[3])
        at(8, 0, 0xFF00, holder=fw_act)
        at(8, 127 << 16, 0xFF0000)
        if key.timer:
            at(68, key.timer, 0xFFFF)
        at(19, fire, 0xFF00)
    elif key.recipe == "ue_re":
        at(22, 0, holder=pos_acts[0])
        move(8)
        at(8, 0, 0xFF00, holder=fw_act)
        if key.timer:
            at(68, key.timer, 0xFFFF)
        move(19)
        at(19, fire, 0xFF00)
        at(55, 0x200104, 0x300104)
        move(40)
        at(40, 0, 0xFF000000)
        move(57)
        at(57, 0)
    elif key.recipe == "minimal":
        at(22, 0, holder=pos_acts[0])
        move(8)
        at(8, 0, 0xFF00, holder=fw_act)
        if key.timer:
            at(68, key.timer, 0xFFFF)
        move(19)
        at(19, fire, 0xFF00)
    elif key.recipe == "ctrig":
        # CtrigAsm CreateBullet/CreateStorm/CreateSprite (CA:81522~81527): +0x58 ← 위치, +0x21 ← 방향,
        # +0x4D ← 135 와 +0x4E·+0x4F ← 0 (마스크 0xFFFF00), +0x110 ← 6
        at(22, 0, holder=pos_acts[0])
        move(8)
        at(8, 0, 0xFF00, holder=fw_act)
        if key.timer:
            at(68, key.timer, 0xFFFF)
        move(19)
        at(19, fire, 0xFFFF00)
    elif key.recipe == "unit_sprite":
        # CtrigAsm UnitSprite (CA:81302~81309): [+0x110 ← Time], +0xDC |= 0x100, +0xE4 ← 0
        at(55, 0x100, 0x100)
        at(57, 0)
        if key.timer == "var":
            at(68, 0, 0xFFFF, holder=extra["tm"])
        elif key.timer:
            at(68, key.timer, 0xFFFF)
    elif key.recipe == "recall":
        # CtrigAsm RecallSprite (CA:81193~81197): +0x58 ← X(마스크 0xFFFF)·Y·65536(마스크 0xFFFF0000),
        # +0x4D ← 137, +0x110 ← 3
        at(22, 0, 0xFFFF, holder=extra["rx"])
        at(22, 0, 0xFFFF0000, holder=extra["ry"])
        move(19)
        at(19, ORDER_CAST_RECALL << 8, 0xFF00)
        at(68, key.timer, 0xFFFF)
    else:
        fail("bullet: 알 수 없는 recipe %r", key.recipe)
    if key.shell:
        at(25, 0, 0xFFFF, holder=fu_act)
    return acts


def _emit_body(key, p, ret):
    fail_t, end = Forward(), Forward()
    checks = []

    def check_fail(cond):
        # 조건이 참이면 자기 next 를 실패 트리거로 바꿔 그리로 간다. 실패 트리거가 next 를 되돌린다(EUDBranch 의 절반)
        t, nxt = Forward(), Forward()
        t << RawTrigger(nextptr=nxt, conditions=cond, actions=SetNextPtr(t, fail_t))
        nxt << NextTrigger()
        checks.append((t, nxt))

    # 1) 빈 칸이 없으면 바로 실패 (다음 칸 읽기 실행 18 을 아낀다)
    check_fail(Memory(_NEXT_UNIT, Exactly, 0))
    ptr, epd, _index = units.f_next_slot()

    # 2) 방향
    if key.mode == "to":
        if key.reverse:
            dy, dx = p["y"] - p["ty"], p["x"] - p["tx"]
        else:
            dy, dx = p["ty"] - p["y"], p["tx"] - p["x"]
        facing = mathx.f_to_dir256(mathx.f_atan2(dy, dx))
    else:
        facing = p.get("fw")  # 3단계 recipe(unit_sprite·recall)는 방향 인자가 없다
    var_facing = key.facing == "var"

    # 3) 인자를 액션 칸으로 (로케이션, 소유자, 유닛, 비교값, 종류, 높이, 상수 방향)
    create_act, elev_act = Forward(), Forward()
    fw_act, fu_act = Forward(), Forward()
    pos_acts = [Forward() for _ in range(4 if key.recipe == "m2" else 1)]
    same = Memory(_NEXT_UNIT, Exactly, 0)  # 비교값 = 생성 전 포인터 (units.Capture.end 와 같은 판정)
    first, second = [], []
    if var_facing:
        first.append((EPD(fw_act) + 5, SetTo, 0))
    if key.mode == "at":
        first.append((EPD(create_act), SetTo, p["loc"]))
    else:
        d = EPD(_MRGN + 20 * (key.loc - 1))
        first += [(d, SetTo, p["x"]), (d + 1, SetTo, p["y"])]
        second += [(d + 2, SetTo, p["x"]), (d + 3, SetTo, p["y"])]
    first += [(EPD(create_act) + 4, SetTo, p["owner"]), (EPD(create_act) + 6, SetTo, p["cu"]),
              (EPD(same) + 2, SetTo, ptr)]
    if key.facing == "const":
        first.append((EPD(fw_act) + 5, SetTo, p["fw"]))
    if key.shell:
        first.append((EPD(fu_act) + 5, SetTo, p["fu"]))
    if key.height:
        first += [(EPD(elev_act), SetTo, p["em"]), (EPD(elev_act) + 4, SetTo, p["ee"]),
                  (EPD(elev_act) + 5, SetTo, p["ev"])]
    extra = {}
    if key.recipe == "recall":  # 3단계: 리콜 목표 좌표 두 칸
        extra = {"rx": Forward(), "ry": Forward()}
        first += [(EPD(extra["rx"]) + 5, SetTo, p["x"] if key.mode == "own" else p["rx"]),
                  (EPD(extra["ry"]) + 5, SetTo, p["ry"])]
    if key.timer == "var":  # 3단계: 변수 수명 (unit_sprite)
        extra["tm"] = Forward()
        first.append((EPD(extra["tm"]) + 5, SetTo, p["tm"]))
    SeqCompute(first + second)

    # 4) 생성 (높이 → 로케이션 Y 보정 → CreateUnit)
    acts = []
    if key.height:
        acts.append(elev_act << SetDeathsX(0, SetTo, 0, 0, 0xFF))
    if key.mode != "at" and key.y_offset:
        base = _MRGN + 20 * (key.loc - 1)
        acts += [SetMemory(base + 4, Add, key.y_offset & M32), SetMemory(base + 12, Add, key.y_offset & M32)]
    acts.append(create_act << CreateUnit(1, 0, 1 if key.mode == "at" else key.loc, 0))
    RawTrigger(actions=acts)
    check_fail(same)  # 0x628438 이 그대로면 생성 실패

    # 5) 변수 방향: 하위 8비트를 액션 값 칸에 << 8 로 옮겨 쌓는다
    if var_facing:
        for i in range(8):
            RawTrigger(conditions=facing.AtLeastX(1, 1 << i), actions=SetMemory(fw_act + 20, Add, 1 << (i + 8)))

    # 6) CP ← epd + 10, 위치(+0x28) 읽기 → 액션 값 칸(들)
    VProc(epd, [SetMemory(_CP_ADDR, SetTo, _CP_POS), *epd.QueueAddTo(_EPD_CP)])
    if key.recipe == "m2":
        pos = f_maskread_cp(0, _POS_MASK)
        SeqCompute([(EPD(a) + 5, SetTo, pos) for a in pos_acts])
    elif key.recipe in _POS_RECIPES:
        f_maskread_cp(0, _POS_MASK, ret=[EPD(pos_acts[0]) + 5])

    # 7) 칸 쓰기 한 트리거, 8) CP 복구 + 반환값
    RawTrigger(actions=_patch_actions(key, pos_acts, fw_act, fu_act, extra))
    f_setcurpl2cpcache(v=[epd], actions=epd.QueueAssignTo(ret))
    SetNextTrigger(end)
    fail_t << RawTrigger(actions=[ret.SetNumber(0)] + [SetNextPtr(t, nxt) for t, nxt in checks])
    end << NextTrigger()


@functools.cache
def _body(key):
    ret = EUDVariable()
    names = _param_names(key)
    fn = EUDFunc(_make_func(names, lambda p: _emit_body(key, p, ret)))
    return _compat.predefine_returns(fn, [ret])


@functools.cache
def _shift_fn(shift, width):
    """변수의 아래 width 비트를 shift 만큼 올린 새 값 (비트마다 조건 트리거 1 — eudplib filler 의 바이트 채우기와 같은 방식)."""
    out = EUDVariable()

    @EUDFunc
    def _bullet_shift(v):
        RawTrigger(actions=out.SetNumber(0))
        for i in range(width):
            RawTrigger(conditions=v.AtLeastX(1, 1 << i), actions=out.AddNumber((1 << (i + shift)) & M32))

    return _compat.predefine_returns(_bullet_shift, [out])


def _var_write_action(field_, index, value):
    """상수 번호 dat 칸에 변수 값을 쓰는 액션 1개(값 칸은 eudplib 가 패치). 칸이 dword 경계가 아니면 먼저 시프트한다."""
    a, shift, mask = field_.location(index)
    v = _to_var(value)
    if shift:
        v = _shift_fn(shift, 8 * field_.size)(v)
    return SetMemory(a, SetTo, v) if mask == M32 else SetMemoryX(a, SetTo, v, mask)


def _height_args(k, height, fname):
    """(ee, ev, em) — elevation 칸 EPD, 시프트한 값, 마스크."""
    a, shift, mask = _ELEVATION.location(k.made_unit)
    h = _num(height, fname, "height")
    if _is_int(h):
        if h > 255:
            fail("%s: height %d 가 0 ~ 255 밖입니다", fname, h)
        ev = h << shift
    elif shift == 0:
        ev = h
    else:
        ev = _shift_fn(shift, 8)(_to_var(h))
    return [EPD(a), ev, mask]


def _facing_arg(facing, fname):
    f = _num(facing, fname, "facing")
    if _is_int(f):
        return "const", (f & 0xFF) << 8
    return "var", _to_var(f)


def _call(k, mode, fkind, args, height, fname, loc=None, reverse=None):
    if k.shell is not None:
        args.append(k.unit)
    if height is not None:
        args += _height_args(k, height, fname)
    key = _Key(mode, fkind, k.recipe, k.y_offset if mode != "at" else 0, k.timer, k.shell is not None,
               height is not None, loc, reverse)
    return _body(key)(*args)


def f_bullet(k, owner, x, y, facing, height=None):
    """(x, y) 에 탄막 유닛을 만들어 facing 방향 유닛이 무기를 쏘게 한다 (CreateBullet). **진행 방향 = facing + 128**(reverse 종류).

    인자: k(BulletKind), owner(P1~P12·CurrentPlayer 상수 또는 변수 0~11), x, y(맵 좌표 — 상수·변수),
          facing(유닛 방향 0~255, 하위 8비트만 씀 — 상수·변수), height(선택: elevation[만드는 유닛] 에 먼저 쓸 값 0~255)
    반환: 만든 유닛 EPD (EUDVariable). 빈 칸 없음·생성 실패면 0 — 0 인지 확인한 뒤 칸 쓰기에 쓴다
    비용: 본문 12(상수 방향)·20(변수 방향)·24(m2 변수 방향) 조합마다 1벌 / 호출 자리 1(변수 인자는 그 변수 트리거를 잇는다) /
          실행 74~92(인자 복사 포함), 빈 칸 없음 7. 변수 높이는 시프트 도우미(본문 9) 호출 +1
          (docs/COSTS.md "bullet (WP14)", 2026-09-17)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const e = bullet.bullet(k, P8, x, y, 64);` (→ `bullet.f_bullet`)
    출처: UE_RE func.lua:21~60 CreateBullet/CallCBullet, Galaxy.py:6~34, M2 func.lua:2085~2116
    """
    fname = "bullet.bullet"
    k = _kind(k, fname)
    ow = _owner(owner, fname)
    xv, yv = _num(x, fname, "x"), _num(y, fname, "y")
    fkind, fw = _facing_arg(facing, fname)
    loc = _resolve_setup_loc()
    return _call(k, "own", fkind, [ow, xv, yv, fw, k._create_word()], height, fname, loc=loc)


bullet = f_bullet


def _const_facing(reverse, sx, sy, ex, ey):
    """bullet_to 의 방향(상수 좌표): reverse 면 to_dir256(atan2(출발 − 목표)), 아니면 목표 − 출발."""
    if reverse:
        a = mathx.f_atan2((sy - ey) & M32, (sx - ex) & M32)
    else:
        a = mathx.f_atan2((ey - sy) & M32, (ex - sx) & M32)
    return mathx.f_to_dir256(a)


def f_bullet_to(k, owner, x, y, tx, ty, height=None):
    """(x, y) 에서 (tx, ty) 쪽으로 쏜다 (CreateBulletXY, 1프레임). 방향은 CtrigAsm `f_Atan2` 와 같은 값으로 구한다.

    인자: k(BulletKind), owner, x, y(출발), tx, ty(목표) — 상수·변수, height(선택)
    반환: 만든 유닛 EPD, 실패면 0
    의미: reverse 종류는 facing = to_dir256(atan2(y − ty, x − tx)) (목표 반대쪽을 보고 음수 속도로 목표 쪽에 날아감),
          reverse=False 는 atan2(ty − y, tx − x). 좌표 차는 −32768 ~ 32767(원본 f_Atan2 범위). 출발 = 목표면 facing 128(reverse)
    비용: 본문 26 1벌(+ mathx atan2 182·to_dir256 43 1벌, 페이로드 약 111KB 한 번) / 호출 자리 1 / 실행 약 235, 빈 칸 없음 9.
          좌표가 모두 상수면 방향을 컴파일 시점에 구해 `bullet` 상수 방향 본문을 쓴다(실행 약 74, atan2 본문 안 씀)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const e = bullet.bullet_to(k, P8, x, y, 2048, 2048);` (→ `bullet.f_bullet_to`)
    출처: UE_RE func.lua:62~114 CreateBulletXY/Call_CreateBulletXY, M2 func.lua:2263~2316, S4 2.3·6.1
    """
    fname = "bullet.bullet_to"
    k = _kind(k, fname)
    ow = _owner(owner, fname)
    vals = [_num(v, fname, n) for v, n in ((x, "x"), (y, "y"), (tx, "tx"), (ty, "ty"))]
    vals = [_to_var(v) if not _compat.is_var(v) and not _is_int(v) else v for v in vals]
    loc = _resolve_setup_loc()
    if all(_is_int(v) for v in vals):
        # 좌표가 모두 상수면 방향도 컴파일 시점에 (mathx 상수 계산 = 실행 중 계산과 같은 값) → 방향 상수 본문
        fw = _const_facing(k.reverse, *vals) << 8
        return _call(k, "own", "const", [ow, vals[0], vals[1], fw, k._create_word()], height, fname, loc=loc)
    return _call(k, "to", "var", [ow, *vals, k._create_word()], height, fname, loc=loc, reverse=k.reverse)


bullet_to = f_bullet_to


def f_bullet_at(k, owner, loc, facing, height=None):
    """주어진 로케이션에 바로 탄막 유닛을 만들어 쏜다 (CreateBulletLoc). 총알 로케이션을 옮기지 않는다.

    인자: k(BulletKind), owner, loc(로케이션 이름 또는 1-based 번호 — 상수·변수), facing(유닛 방향), height(선택)
    반환: 만든 유닛 EPD, 실패면 0
    의미: 유닛은 그 로케이션 중심에 생긴다(CreateUnit 규칙). `k.y_offset` 은 적용하지 않는다(M2·Galaxy.py CreateBulletLoc 와 같음).
    비용: 본문 11(상수 방향)·19(변수 방향) 1벌 / 호출 자리 1 / 실행 약 71
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const e = bullet.bullet_at(k, P8, "Boss", 128);` (→ `bullet.f_bullet_at`)
    출처: M2 func.lua:2059~2069, Galaxy.py:37~61
    """
    fname = "bullet.bullet_at"
    k = _kind(k, fname)
    ow = _owner(owner, fname)
    lv = _loc_arg(loc, fname)
    fkind, fw = _facing_arg(facing, fname)
    return _call(k, "at", fkind, [ow, lv, fw, k._create_word()], height, fname)


bullet_at = f_bullet_at


# =============================================================================================
# 3단계 (WP21): CtrigAsm 28장 스프라이트 함수 (R4a A, CA = reference/MapSource/Library/CtrigAsm v5.5.lua)
# =============================================================================================

_SPRITE_IMAGE = dat.field("sprites", "image")
_IMAGE_ISCRIPT = dat.field("images", "iscript")
_IMAGE_FULL = dat.field("images", "useFullIscript")
_COMP_IDLE = dat.field("units", "computerIdleOrder")
_HUMAN_IDLE = dat.field("units", "humanIdleOrder")


def _declare_ctrig_table(lst, k):
    """CtrigAsm `BulletInitSetting` 표(CA:81402~81450, R4a A.2)를 목록 lst 에 같은 순서로 선언한다(같은 칸은 뒤가 이긴다)."""
    lst.unit(k.unit).set(
        groundWeapon=k.weapon, seekRange=3,
        baseProperty=0x20000004 if k.half_air else 0x38000004,
        movementFlags=0 if k.half_air else 197,
        unitBoundsLT=0x10001, unitBoundsRB=0, flingy=k.unit_flingy, groupFlags=2, availabilityFlags=0x1CF,
        buildingDimensions=1, computerIdleOrder=2, humanIdleOrder=2, returnToIdleOrder=2,
        attackUnitOrder=134, attackMoveOrder=135, rightClickAction=1)
    lst.flingy(k.unit_flingy).set(topSpeed=0, acceleration=1, haltDistance=0, turnRadius=128, movementControl=0,
                                  sprite=k.unit_sprite)
    lst.sprite(k.unit_sprite).set(image=_CARRIER_IMAGE)
    sp = k.splash
    lst.weapon(k.weapon).set(
        damage=k.damage, damageBonus=k.damage_bonus, damageFactor=k.count, upgrade=k.upgrade,
        damageType=k.damage_type, explosionType=k.explosion, splashInnerRadius=sp[0], splashMiddleRadius=sp[1],
        splashOuterRadius=sp[2], launchSpin=0, minRange=0, maxRange=3, flingy=k.flingy, forwardOffset=0,
        verticalOffset=2, attackAngle=255)
    lst.flingy(k.flingy).set(sprite=k.sprite, acceleration=50000, haltDistance=0, turnRadius=127, movementControl=0)
    lst.sprite(k.sprite).set(image=k.image)
    lst.image(k.image).set(drawingFunction=k.color, iscript=k.iscript)
    if k.carrier_iscript is not None:
        # CtrigAsm 은 CreateBullet/Storm/Sprite 를 부를 때마다 쓴다(CA:81464·81651·81730). 값이 상수라 시작 때 한 번
        lst.image(_CARRIER_IMAGE).set(iscript=k.carrier_iscript)


class CtrigKind(BulletKind):
    """CtrigAsm 28장 방식 종류 (`BulletInitSetting` 대체). `storm`·`perma_sprite`·`cgrp.CGRPPainter` 가 쓴다.

    인자: unit(탄막 유닛 번호·이름), weapon(그 유닛의 지상 무기), flingy(무기 flingy), sprite(flingy 의 스프라이트),
          image(sprite 의 이미지), iscript(image 의 iscript — 395 럴커 = 지속 피해, 235·242 등 = 단발), color(image 의
          화면 출력 0~255), unit_flingy·unit_sprite(탄막 유닛의 flingy·그 스프라이트, 기본 74·229 = 가이드북 예제 값),
          half_air(True = 반공중 — 가이드북: 203~213 트랩류, 생성 자리의 유닛·높이와 무관하게 정확히 생성),
          damage, damage_bonus(0~65535), upgrade, count(총알 수 — 2 면 두 발), damage_type, explosion(0~255),
          splash((안, 중, 밖) 0~65535), carrier_iscript(이미지 256 의 iscript, 기본 86 — None 이면 쓰지 않음),
          remove_timer(None = 6), y_offset(로케이션 Y 보정, 기본 −2 = CtrigAsm)
    반환: -
    의미: `BulletKind(recipe="ctrig", reverse=True)` 에 A.2 표를 더한 것. 생성 뒤 칸 = +0x58 ← 위치, +0x21 ← 방향,
          +0x4D ← 135(+0x4E·+0x4F ← 0), +0x110 ← 6. `bullet.bullet(k, …)` 으로도 쏠 수 있지만 CtrigAsm `CreateBullet` 이
          부를 때마다 쓰는 투사 방식 9·속도·수명은 쓰지 않는다(`k.speed_actions` 등으로 따로).
          `init_actions()` / `install()` 은 CtrigAsm 과 같은 칸에 같은 값을 쓴다(시험이 Lua 원문을 읽어 대조) + 이미지 256
          iscript ← 86(CtrigAsm 은 부를 때마다). **영구 부작용**: 벌처 이미지(256) iscript, 고른 유닛의 units.dat 여러 칸(R4a A.8).
    비용: 없음(컴파일 시점 객체). `install()` = 시작 1회 액션 약 45개(트리거 1)
    CP: 해당 없음
    로컬: 공유
    epScript: `const k = bullet.CtrigKind(unit=203, weapon=2, flingy=147, sprite=231, image=233, iscript=233, half_air=True); k.install();`
    출처: CtrigAsm `BulletInitSetting`(CA:81379~81451), 가이드북 7927~7949·18031~18035(예제 28-1)
    """

    __slots__ = ("unit_flingy", "unit_sprite", "sprite", "image", "iscript", "color", "damage", "damage_bonus",
                 "upgrade", "count", "damage_type", "explosion", "splash", "half_air", "carrier_iscript")

    def __init__(self, unit, weapon, flingy, sprite, image, iscript, color=0, unit_flingy=74, unit_sprite=229,
                 half_air=False, damage=0, damage_bonus=0, upgrade=0, count=1, damage_type=0, explosion=0,
                 splash=(0, 0, 0), carrier_iscript=_ISCRIPT_CARRIER, remove_timer=None, y_offset=-2):
        fname = "bullet.CtrigKind"
        if unProxy(weapon) is None or unProxy(flingy) is None:
            fail("%s: weapon·flingy 는 None 일 수 없습니다", fname)
        BulletKind.__init__(self, unit=unit, weapon=weapon, flingy=flingy, reverse=True, shell=None, recipe="ctrig",
                            remove_timer=remove_timer, y_offset=y_offset, dat=None)
        if not isinstance(half_air, bool):
            fail("%s: half_air 는 True/False 여야 합니다 (%r)", fname, half_air)
        self.half_air = half_air
        self.unit_flingy = _const_int(unit_flingy, fname, "unit_flingy", 0, _TOP_SPEED.last)
        self.unit_sprite = _const_int(unit_sprite, fname, "unit_sprite", 0, _SPRITE_IMAGE.last)
        self.sprite = _const_int(sprite, fname, "sprite", 0, _SPRITE_IMAGE.last)
        self.image = _const_int(image, fname, "image", 0, _IMAGE_ISCRIPT.last)
        self.iscript = _const_int(iscript, fname, "iscript", 0, M32)
        self.color = _const_int(color, fname, "color", 0, 255)
        self.damage = _const_int(damage, fname, "damage", 0, 0xFFFF)
        self.damage_bonus = _const_int(damage_bonus, fname, "damage_bonus", 0, 0xFFFF)
        self.upgrade = _const_int(upgrade, fname, "upgrade", 0, 255)
        self.count = _const_int(count, fname, "count", 0, 255)
        self.damage_type = _const_int(damage_type, fname, "damage_type", 0, 255)
        self.explosion = _const_int(explosion, fname, "explosion", 0, 255)
        sp = unProxy(splash)
        if not isinstance(sp, (list, tuple)) or len(sp) != 3:
            fail("%s: splash 는 (안, 중, 밖) 반경 세 개여야 합니다 (%r)", fname, splash)
        self.splash = tuple(_const_int(r, fname, "splash", 0, 0xFFFF) for r in sp)
        self.carrier_iscript = None if carrier_iscript is None else \
            _const_int(carrier_iscript, fname, "carrier_iscript", 0, M32)

    def __repr__(self):
        return ("<bullet.CtrigKind unit=%d weapon=%d flingy=%d sprite=%d image=%d iscript=%d color=%d half_air=%r"
                " timer=%r y_offset=%d — epScript 에서는 var 가 아니라 const 로 묶으세요>"
                % (self.unit, self.weapon, self.flingy, self.sprite, self.image, self.iscript, self.color,
                   self.half_air, self.timer, self.y_offset))

    def init_actions(self):
        """A.2 표(CtrigAsm `BulletInitSetting`) + 이미지 256 iscript 의 액션 목록(조건 블록·시작 1회 구역용).

        인자: 없음
        반환: list[Action] (datpatch 가 같은 dword 의 SetTo 를 합친 목록)
        비용: 액션 약 45 (64개마다 트리거 1)
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `DoActions(k.init_actions());`
        출처: CA:81379~81451
        """
        return dat.actions(lambda lst: _declare_ctrig_table(lst, self))

    def install(self):
        """A.2 표를 datpatch 시작 1회 목록(`dat.start()`)에 선언한다(CtrigAsm `BulletInitSetting(…, Preserve=0)`).

        인자: 없음
        반환: self
        의미: 모듈을 불러올 때(빌드 밖) 부르면 빌드마다, 빌드 중에 부르면 그 빌드에만 들어간다(datpatch 규칙).
        비용: 시작 1회 트리거(64액션마다 1), 호출 자리 0
        CP: 바꾸지 않음
        로컬: 공유
        epScript: `k.install();` (전역 문장)
        출처: CA:81379~81451
        """
        _declare_ctrig_table(dat.f_start(), self)
        return self


def _height_args_for(unit, height, fname):
    return _height_args(_UnitOnly(unit), height, fname)


class _UnitOnly:
    __slots__ = ("made_unit",)

    def __init__(self, unit):
        self.made_unit = unit


def _const_height(height, fname):
    """높이 인자를 먼저 검사한다(트리거를 내기 전에). 반환: 변환한 값 또는 None."""
    if height is None:
        return None
    h = _num(height, fname, "height")
    if _is_int(h) and h > 255:
        fail("%s: height %d 가 0 ~ 255 밖입니다", fname, h)
    return h


def _storm_dat_actions(k, image, time, fname="bullet.storm"):
    """CreateStorm 이 부를 때마다 쓰는 dat (CA:81686~81701): 투사 방식 3, removeAfter ← time, 상수 image 면 iscript 236·전체 iscript.

    반환: (액션 목록, 변수 image 면 그 값 아니면 None)
    """
    w = k._need("weapon", fname)
    acts = dat.actions(lambda d: d.weapon(w).set(behavior=_BEHAVIOR_STORM))
    if _is_int(time):
        acts += k.time_actions(time)
    else:
        acts.append(_var_write_action(_REMOVE_AFTER, w, time))
    if _is_int(image):
        acts += dat.actions(lambda d: d.image(image).set(iscript=_ISCRIPT_STORM, useFullIscript=True))
        return acts, None
    return acts, image


@functools.cache
def _storm_image_fn():
    """변수 이미지 번호 img(0~1023)에 iscript[img] ← 236, useFullIscript[img] ← 1 을 쓰는 공유 본문.

    iscript 는 dword 칸(EPD = 기준 + img)이라 더하기 한 번, useFullIscript 는 바이트 칸이라 img 의 비트 2~9 를 EPD 에,
    비트 0~1 을 바이트 위치(값·마스크)에 나눠 쌓는다(비트당 조건 트리거 1 — datpatch now 의 scdata 쓰기보다 호출 자리가 작다).
    """
    epd_i, epd_f = EPD(_IMAGE_ISCRIPT.location(0)[0]), EPD(_IMAGE_FULL.location(0)[0])
    act_i, act_f = Forward(), Forward()

    @EUDFunc
    def _bullet_storm_image(img):
        VProc(img, [SetMemory(act_i + 16, SetTo, epd_i), *img.QueueAddTo(EPD(act_i) + 4)])
        RawTrigger(actions=SetMemory(act_f + 16, SetTo, epd_f))
        for i in range(2, 10):
            RawTrigger(conditions=img.AtLeastX(1, 1 << i), actions=SetMemory(act_f + 16, Add, 1 << (i - 2)))
        for sub in range(4):
            bit = 1 << (8 * sub)
            RawTrigger(conditions=img.ExactlyX(sub, 3), actions=[SetMemory(act_f, SetTo, bit),
                                                                 SetMemory(act_f + 20, SetTo, bit)])
        RawTrigger(actions=[act_i << SetDeaths(0, SetTo, _ISCRIPT_STORM, 0), act_f << SetDeathsX(0, SetTo, 0, 0, 0)])

    return _bullet_storm_image


def _perma_dat_actions(k, speed, fname="bullet.perma_sprite"):
    """CreateSprite 가 부를 때마다 쓰는 dat (CA:81759~81765): 투사 방식 7, flingy 최고속도 ← −speed(reverse)."""
    w = k._need("weapon", fname)
    f = k._need("flingy", fname)
    acts = dat.actions(lambda d: d.weapon(w).set(behavior=_BEHAVIOR_SPRITE))
    top = _TOP_SPEED.location(f)[0]
    if _is_int(speed):
        acts.append(SetMemory(top, SetTo, ((-speed) if k.reverse else speed) & M32))
    elif k.reverse:
        # −v = (0xFFFFFFFF ⊖ v) + 1 — SC Subtract 는 포화지만 v ≤ 0xFFFFFFFF 라 결과가 같고(3.5-7), Add 는 한 바퀴 돈다
        acts += [SetMemory(top, SetTo, M32), SetMemory(top, Subtract, speed), SetMemory(top, Add, 1)]
    else:
        acts.append(SetMemory(top, SetTo, speed))
    return acts


def _sprite_call(k, ow, x, y, fname, height=None):
    """점 하나: `perma_sprite` 에서 dat 쓰기를 뺀 것(상수 방향 0 본문). cgrp.CGRPPainter 가 점마다 부른다."""
    loc = _resolve_setup_loc()
    return _call(k, "own", "const", [ow, x, y, 0, k._create_word()], height, fname, loc=loc)


def f_storm(k, owner, x, y, facing, image, time, height=None):
    """(x, y) 에 스톰형 스프라이트를 만든다 (CtrigAsm `CreateStorm`, 투사 방식 3 — 지점 지속).

    인자: k(BulletKind — 보통 CtrigKind), owner(P1~P12·CurrentPlayer 또는 변수), x, y(좌표 — 상수·변수),
          facing(유닛 방향 0~255), image(총알 이미지 번호 — 상수·변수. **그 이미지의 iscript 가 236, 전체 iscript 가 1 로 바뀐다**),
          time(무기 removeAfter 0~255 — 상수·변수), height(선택: elevation[탄막 유닛])
    반환: 만든 유닛 EPD (EUDVariable), 빈 칸 없음·생성 실패면 0
    의미: 먼저 전역 dat(무기 투사 방식 ← 3, removeAfter ← time, 이미지 iscript ← 236·전체 iscript ← 1)를 쓰고
          `bullet(k, …)` 과 같은 본문을 부른다. 같은 프레임 같은 무기의 마지막 값이 모두에 적용된다. 0틱 연산 불가(GB 8039).
    비용: dat 호출 자리 1 + `bullet` 호출 1 = 2 / 실행 약 77 (상수 이미지·수명). 변수 수명·높이는 시프트 도우미 호출 +1씩,
          변수 이미지는 공유 본문(20) 호출 +1 / 실행 +16 (docs/COSTS.md "bullet 3단계 — 28장 스프라이트 (WP21)")
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const e = bullet.storm(k, P8, x, y, 0, 380, 30);` (→ `bullet.f_storm`)
    출처: CtrigAsm `CreateStorm`(CA:81638~81715), 가이드북 8002~8018
    """
    fname = "bullet.storm"
    k = _kind(k, fname)
    k._need("weapon", fname)
    ow = _owner(owner, fname)
    xv, yv, fv = _num(x, fname, "x"), _num(y, fname, "y"), _num(facing, fname, "facing")
    img = _num(image, fname, "image")
    if _is_int(img):
        _const_int(img, fname, "image", 0, _IMAGE_ISCRIPT.last)
    tv = _num(time, fname, "time")
    if _is_int(tv):
        _const_int(tv, fname, "time", 0, 255)
    hv = _const_height(height, fname)
    _resolve_setup_loc()
    acts, var_img = _storm_dat_actions(k, img, tv, fname)
    DoActions(acts)
    if var_img is not None:
        _storm_image_fn()(_to_var(var_img))
    return f_bullet(k, ow, xv, yv, fv, height=hv)


storm = f_storm


def f_perma_sprite(k, owner, x, y, facing=0, speed=0, height=None):
    """(x, y) 에 영구 스프라이트를 만든다 (CtrigAsm `CreateSprite`, 투사 방식 7 — 튕김, 수명 없음).

    인자: k(BulletKind — 보통 CtrigKind), owner, x, y(상수·변수), facing(유닛 방향 0~255),
          speed(총알 최고속도 — 상수·변수. reverse 종류는 **−speed** 를 쓴다(CtrigAsm 과 같음, `speed_actions` 의
          0xFFFFFFFF − v 와 1 차이 — 0 이면 정확히 0 이라 점이 움직이지 않는다)), height(선택)
    반환: 만든 유닛 EPD, 실패면 0
    의미: 전역 dat(투사 방식 ← 7, 최고속도 ← −speed)를 쓰고 `bullet` 본문을 부른다. 만든 총알은 영구 스프라이트로
          남고 395(럴커) iscript 외에는 피해가 없다(GB 8037). 흰색(화면 출력 17) 이미지는 42틱 뒤 튕기므로 쓰지 않는다.
    비용: dat 호출 자리 1(변수 speed 는 액션 3) + `bullet` 호출 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const e = bullet.perma_sprite(k, P8, x, y, 0, speed=0, height=h);` (→ `bullet.f_perma_sprite`)
    출처: CtrigAsm `CreateSprite`(CA:81717~81786), 가이드북 8021~8040, 예제 29-4~29-10
    """
    fname = "bullet.perma_sprite"
    k = _kind(k, fname)
    k._need("weapon", fname)
    k._need("flingy", fname)
    ow = _owner(owner, fname)
    xv, yv, fv = _num(x, fname, "x"), _num(y, fname, "y"), _num(facing, fname, "facing")
    sp = _num(speed, fname, "speed")
    hv = _const_height(height, fname)
    _resolve_setup_loc()
    DoActions(_perma_dat_actions(k, sp, fname))
    return f_bullet(k, ow, xv, yv, fv, height=hv)


perma_sprite = f_perma_sprite


# --- 칸 연산 없이 만들기 (ScanSprite, UnitSprite Time="X") ---

_PKey = namedtuple("_PKey", "loc height scan_remove")


def _emit_plain(key, p):
    create_act, elev_act = Forward(), Forward()
    d = EPD(_MRGN + 20 * (key.loc - 1))
    items = [(d, SetTo, p["x"]), (d + 1, SetTo, p["y"]), (EPD(create_act) + 4, SetTo, p["owner"]),
             (EPD(create_act) + 6, SetTo, p["cu"])]
    if key.height:
        items += [(EPD(elev_act), SetTo, p["em"]), (EPD(elev_act) + 4, SetTo, p["ee"]),
                  (EPD(elev_act) + 5, SetTo, p["ev"])]
    SeqCompute(items + [(d + 2, SetTo, p["x"]), (d + 3, SetTo, p["y"])])
    idle = [_COMP_IDLE.location(SCAN_UNIT), _HUMAN_IDLE.location(SCAN_UNIT)]
    acts = []
    if key.height:
        acts.append(elev_act << SetDeathsX(0, SetTo, 0, 0, 0xFF))
    if key.scan_remove:  # CA:81337~81340 — 생성 동안만 스캐너 대기 주문 ← 0(Die)
        acts += [SetMemoryX(a, SetTo, 0, m) for a, _sh, m in idle]
    acts.append(create_act << CreateUnit(1, 0, key.loc, 0))
    if key.scan_remove:  # CA:81355~81358 — 140 으로 되돌림
        acts += [SetMemoryX(a, SetTo, _SCAN_IDLE_ORDER << sh, m) for a, sh, m in idle]
    RawTrigger(actions=acts)


@functools.cache
def _plain_body(key):
    names = ["owner", "x", "y", "cu"] + (["ee", "ev", "em"] if key.height else [])
    return EUDFunc(_make_func(names, lambda p: _emit_plain(key, p)))


def _create_word_for(unit, count, fname):
    """CreateUnit 액션 +24 dword (유닛 | 44<<16 | 수량<<24). count 가 변수면 하위 8비트를 올린 새 변수."""
    base = unit | (_ACT_CREATE_UNIT << 16)
    if _is_int(count):
        return base | ((count & 0xFF) << 24)
    c = _shift_fn(24, 8)(_to_var(count))
    DoActions(c.AddNumber(base))
    return c


def f_scan_sprite(owner, x, y, count=1, remove=True):
    """(x, y) 에 스캐너 스윕(유닛 33)을 만들어 그 스프라이트(스프라이트 380 의 이미지)를 띄운다 (CtrigAsm `ScanSprite`).

    인자: owner(P1~P12·CurrentPlayer 또는 변수), x, y(상수·변수), count(만들 수 1~255 상수 또는 변수 — 하위 8비트),
          remove(True = 생성 동안 스캐너의 컴퓨터·사람 대기 주문을 0(Die)으로 두었다가 140 으로 되돌린다 — 유닛은 바로
          없어지고 스프라이트만 남는다(가이드북 "스캔 제거"))
    반환: None
    의미: 칸 연산이 없어 **0틱 연산이 된다**. 높이는 4 고정, 한도 약 500~600(언리미터로 안 늘어남, GB 8562).
          선행: `scan_init()`(스캐너 크기 0·에디터 어빌리티), 이미지는 `scan_image_actions(i)`/`set_scan_image(i)`.
          빈 칸 검사·생성 확인은 하지 않는다(CtrigAsm 과 같음 — 실패하면 아무 일도 없다).
    비용: 본문 3 1벌(로케이션마다) / 호출 자리 1(변수 count 는 시프트 도우미 +2) / 실행 약 10
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `bullet.scan_sprite(P1, x, y, count=1);` (→ `bullet.f_scan_sprite`)
    출처: CtrigAsm `ScanSprite`(CA:81315~81365), 가이드북 7877~7890, 예제 29-9
    """
    fname = "bullet.scan_sprite"
    ow = _owner(owner, fname)
    xv, yv = _num(x, fname, "x"), _num(y, fname, "y")
    cnt = _num(count, fname, "count")
    if _is_int(cnt):
        _const_int(cnt, fname, "count", 1, 255)
    if not isinstance(remove, bool):
        fail("%s: remove 는 True/False 여야 합니다 (%r)", fname, remove)
    loc = _resolve_setup_loc()
    cu = _create_word_for(SCAN_UNIT, cnt, fname)
    _plain_body(_PKey(loc, False, remove))(ow, xv, yv, cu)


scan_sprite = f_scan_sprite


def f_unit_sprite(owner, unit, x, y, height=None, time=None, track=True):
    """(x, y) 에 표시용 유닛을 만든다 (CtrigAsm `UnitSprite`).

    인자: owner, unit(유닛 번호·이름 — 상수), x, y(상수·변수), height(선택: elevation[unit] ← 값, 상수·변수),
          time(선택: +0x110 removeTimer ← 값 0~65535, 상수·변수. None = 쓰지 않음(지속 시간 제한 없음)),
          track(False = CtrigAsm `Time="X"` — 칸 연산 없이 만들기만 한다. time 을 줄 수 없고 None 을 돌려준다)
    반환: track=True 면 만든 유닛 EPD(빈 칸 없음·생성 실패면 0), False 면 None
    의미: track=True 는 생성 뒤 +0xDC |= 0x100, +0xE4 ← 0(드래그 방지 — 가이드북 "+0xE4 를 0 으로 고정") 과 수명을 쓴다.
          0틱 연산이 된다. 유닛 850 개를 넘으면 갱신이 3틱으로 늘고, 드래그 방지는 클로킹 소리가 난다(GB 8566).
          사용자판과 달리 생성 실패면 칸을 쓰지 않는다(1단계와 같은 판정).
    비용: track = 본문 약 12 1벌 / 호출 자리 1 / 실행 약 45(위치 읽기 없음) · track=False = 본문 3 / 호출 1 / 실행 약 9
          (변수 높이·수명은 시프트 도우미를 거칠 수 있다, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const e = bullet.unit_sprite(P1, 8, x, y, height=3, time=48);` (→ `bullet.f_unit_sprite`)
    출처: CtrigAsm `UnitSprite`(CA:81209~81313), 가이드북 7891~7905, 예제 29-7
    """
    fname = "bullet.unit_sprite"
    ow = _owner(owner, fname)
    if _compat.is_var(unProxy(unit)):
        fail("%s: unit 은 상수여야 합니다 (높이 칸 주소를 컴파일 시점에 정한다)", fname)
    u = _unit_id(unit, fname, "unit")
    xv, yv = _num(x, fname, "x"), _num(y, fname, "y")
    if not isinstance(track, bool):
        fail("%s: track 은 True/False 여야 합니다 (%r)", fname, track)
    hv = _const_height(height, fname)
    timer, tv = None, None
    if time is not None:
        if not track:
            fail("%s: track=False(CtrigAsm Time=\"X\")에는 time 을 줄 수 없습니다", fname)
        tv = _num(time, fname, "time")
        if _is_int(tv):
            timer = _const_int(tv, fname, "time", 0, 0xFFFF) or None
        else:
            timer, tv = "var", _to_var(tv)
    loc = _resolve_setup_loc()
    cu = _create_word_for(u, 1, fname)
    hargs = [] if hv is None else _height_args_for(u, hv, fname)
    if not track:
        _plain_body(_PKey(loc, hv is not None, False))(ow, xv, yv, cu, *hargs)
        return None
    key = _Key("own", "none", "unit_sprite", 0, timer, False, hv is not None, loc, None)
    return _body(key)(ow, xv, yv, cu, *hargs, *([tv] if timer == "var" else []))


unit_sprite = f_unit_sprite


def f_recall_sprite(owner, unit, x, y, loc=None):
    """아비터류 유닛을 만들어 (x, y) 에 리콜을 시전하게 한다 (CtrigAsm `RecallSprite`) — 리콜 스프라이트(379)가 뜬다.

    인자: owner, unit(리콜을 쓰는 유닛 번호·이름 — 상수), x, y(리콜 목표 좌표 — 상수·변수, 각 하위 16비트),
          loc(None = 총알 로케이션을 (x, y) 로 옮겨 그 자리에 만든다. 이름·1-based 번호(상수·변수)면 그 로케이션에 만든다 —
          가이드북 예제 28-1 은 따로 둔 "CLoc2")
    반환: 만든 유닛 EPD, 빈 칸 없음·생성 실패면 0
    의미: 생성 뒤 +0x58 ← (x, y), +0x4D ← 137(리콜 시전), +0x110 ← 3. 게임 로직이 주문을 실행해야 하므로 **0틱 불가**.
          리콜 마나를 0 으로 두는 것을 권장(GB 7925). 실제 리콜이므로 목표 근처 소유자 유닛이 끌려올 수 있다(R4a A.8 추측).
          이미지는 `recall_image_actions(i)`/`set_recall_image(i)`.
    비용: 본문 약 11 1벌 / 호출 자리 1(변수 y 는 시프트 도우미 +1) / 실행 약 40 (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const e = bullet.recall_sprite(P1, 86, x, y, loc="CLoc2");` (→ `bullet.f_recall_sprite`)
    출처: CtrigAsm `RecallSprite`(CA:81159~81207), 가이드북 7911~7926
    """
    fname = "bullet.recall_sprite"
    ow = _owner(owner, fname)
    if _compat.is_var(unProxy(unit)):
        fail("%s: unit 은 상수여야 합니다", fname)
    u = _unit_id(unit, fname, "unit")
    xv, yv = _num(x, fname, "x"), _num(y, fname, "y")
    lv = None if loc is None else _loc_arg(loc, fname)
    lc = _resolve_setup_loc() if loc is None else None
    cu = _create_word_for(u, 1, fname)
    if _is_int(yv):
        ry = (yv & 0xFFFF) << 16
    else:
        ry = _shift_fn(16, 16)(_to_var(yv))
    if loc is None:
        key = _Key("own", "none", "recall", 0, _RECALL_TIMER, False, False, lc, None)
        return _body(key)(ow, xv, yv, cu, ry)
    key = _Key("at", "none", "recall", 0, _RECALL_TIMER, False, False, None, None)
    return _body(key)(ow, lv, cu, xv, ry)


recall_sprite = f_recall_sprite


# --- 초기화·이미지 (ScanInitSetting, SetScanImage, SetRecallImage) ---


def _declare_scan_init(lst):
    # CA:81373~81375: 스캐너 스윕(33) 크기 0x6618D0/D4 ← 0, 에디터 어빌리티 0x66155A ← 0x1CF
    lst.unit(SCAN_UNIT).set(unitBoundsLT=0, unitBoundsRB=0, availabilityFlags=0x1CF)


def f_scan_init_actions():
    """`scan_sprite` 전에 필요한 스캐너 초기화 액션 목록 (CtrigAsm `ScanInitSetting`).

    인자: 없음
    반환: list[Action] (스캐너 스윕 크기 ← 0, 에디터 어빌리티 ← 0x1CF)
    의미: **진짜 스캐너 스윕의 크기도 0 이 된다**(영구 부작용, R4a A.8).
    비용: 액션 3
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `DoActions(bullet.scan_init_actions());`
    출처: CA:81367~81377, 가이드북 7872~7876
    """
    return dat.actions(_declare_scan_init)


scan_init_actions = f_scan_init_actions


def f_scan_init():
    """스캐너 초기화(`scan_init_actions`)를 datpatch 시작 1회 목록에 선언한다 (`ScanInitSetting(…, Preserve=0)`).

    인자: 없음
    반환: None
    비용: 시작 1회 액션 3, 호출 자리 0
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `bullet.scan_init();` (전역 문장)
    출처: CA:81367~81377
    """
    _declare_scan_init(dat.f_start())


scan_init = f_scan_init


_SET_IMAGE_NAME = {SCAN_SPRITE: "bullet.set_scan_image", RECALL_SPRITE: "bullet.set_recall_image"}


def _image_actions(sprite, image, fname):
    if _compat.is_var(unProxy(image)):
        fail("%s: 변수 이미지는 %s(…) 를 쓰세요", fname, _SET_IMAGE_NAME[sprite])
    i = _const_int(image, fname, "image", 0, _IMAGE_ISCRIPT.last)
    return dat.actions(lambda d: d.sprite(sprite).set(image=i))


def _set_image(sprite, image, fname):
    v = _num(image, fname, "image")
    if _is_int(v):
        DoActions(_image_actions(sprite, v, fname))
    else:
        DoActions(_var_write_action(_SPRITE_IMAGE, sprite, v))


def f_scan_image_actions(image):
    """스캔 스프라이트(380)의 이미지 액션 목록 (CtrigAsm `SetScanImage`).

    인자: image(이미지 번호 0~998 상수)
    반환: list[Action] (SetMemoryX 1개 — 0x666458 워드)
    비용: 액션 1
    CP: 바꾸지 않음
    로컬: 공유 (전역 dat)
    epScript: `DoActions(bullet.scan_image_actions(391));`
    출처: CA:81822~81824
    """
    return _image_actions(SCAN_SPRITE, image, "bullet.scan_image_actions")


scan_image_actions = f_scan_image_actions


def f_set_scan_image(image):
    """그 자리에서 스캔 스프라이트(380)의 이미지를 쓴다(값이 변수여도 된다, CtrigAsm `TSetScanImage`).

    인자: image(상수 또는 변수 — 하위 16비트)
    반환: None
    비용: 호출 자리 1(변수는 +1) / 실행 1~3
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `bullet.set_scan_image(i);`
    출처: CA:81826~81828
    """
    _set_image(SCAN_SPRITE, image, "bullet.set_scan_image")


set_scan_image = f_set_scan_image


def f_recall_image_actions(image):
    """리콜 스프라이트(379)의 이미지 액션 목록 (CtrigAsm `SetRecallImage`).

    인자: image(이미지 번호 0~998 상수)
    반환: list[Action] (SetMemoryX 1개 — 0x666456 워드)
    비용: 액션 1
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `DoActions(bullet.recall_image_actions(379));`
    출처: CA:81814~81816
    """
    return _image_actions(RECALL_SPRITE, image, "bullet.recall_image_actions")


recall_image_actions = f_recall_image_actions


def f_set_recall_image(image):
    """그 자리에서 리콜 스프라이트(379)의 이미지를 쓴다(값이 변수여도 된다, CtrigAsm `TSetRecallImage`).

    인자: image(상수 또는 변수 — 하위 16비트, 변수는 시프트 도우미를 거친다)
    반환: None
    비용: 상수 = 호출 자리 1 / 변수 = 호출 자리 3, 실행 약 20 (시프트 도우미 본문 17 1벌)
    CP: 바꾸지 않음
    로컬: 공유
    epScript: `bullet.set_recall_image(i);`
    출처: CA:81818~81820
    """
    _set_image(RECALL_SPRITE, image, "bullet.set_recall_image")


set_recall_image = f_set_recall_image
