"""auto_all phase 3 `switch`(A-2) · 4 `s8`(A-1·B15-5) · 5 `datpatch`(B15-1·3·4·10) — 파이썬 단계 모듈.

- 3 `switch`: examples/switch_ingame.py 와 같은 시험(스위치 1·3·32·33·40 → 0x58DC40 두 칸과 조건 두 개).
  판정 뒤(110 프레임) 스위치를 지운다 — 뒤 단계가 스위치를 쓰지 않게.
- 4 `s8`: docs/spec/S8_ingame/s8_ingame.py 를 **모듈로 import** 해 `run_tests()` + `dbg_report()`(그 파일에 더한 함수).
- 5 `datpatch`: 시작 1회 dat 목록은 이 모듈을 불러올 때 선언된다. **04 예제의 선언 가운데 탄(bullet) 단계와 겹치는 것
  (flingy 106 최고속도 +8000, 유닛 208 플래그, 무기 1·3·128)은 넣지 않는다**(분류 문서 4절 발견 ②) — 대신 아무 단계도
  쓰지 않는 칸만 쓴다: 파이어뱃 최대 체력(B15-3), 발키리 timeCost·supplyUsed(B15-4), 유닛 0·1 requirementOffset
  매 프레임(B15-10). B15-1 은 피해 배율 표 근처 0x515B80:32 덤프(04 맵에는 표시 코드가 없었다 — 발견 ①).

epScript 에서 부르는 함수는 `f_` 이름이다(`ph.switch_step(f)` → `f_switch_step`).
"""

import s8_ingame as s8
from eudplib import (
    Clear,
    Cleared,
    DoActions,
    EUDEndIf,
    EUDIf,
    EUDVariable,
    Exactly,
    Memory,
    RawTrigger,
    Set,
    SetSwitch,
    Switch,
    f_dwread,
    f_simpleprint,
    hptr,
)

import aa_common as aa
from eudext import datpatch as dat
from eudext import dbg

# --- 맵 전체: 유닛 충돌 상자 1,1,1,1 (2026-09-18 인게임 뒤) ----------------------------------------
# 도형 유닛이 서로 밀려 좌표가 어긋났고(D7-1 posbad 18), 탄막 유닛은 한 발도 만들어지지 않았다(D14-0).
# 밀림을 없애려고 **탄막 유닛(208·210·204)을 포함한 유닛 228개 전부**의 충돌 상자를 1,1,1,1 로 만든다.
# 공중 유닛끼리 미는 것은 충돌 상자와 별개다 — eds 의 [noAirCollision] 이 그쪽을 맡는다.
# 액션 456개 = 트리거 8개(게임 시작 1회). 탄막 recipe 도 같은 칸에 1 을 쓰므로 값이 겹쳐도 같은 값이다.
dat.all_unit_size(1)

# (탄막 유닛의 에디터 어빌리티 0x1CF·소속그룹·주문과 탄 그림 iscript 는 2026-09-18 부터 eudext.bullet 의
#  기본값이 건다 — aa_bullet.eps 의 BulletKind/BulletDat 참고. 여기서 따로 걸지 않는다.)

# --- phase 3 switch (A-2) -----------------------------------------------------------------------
SWITCHES = (0, 2, 31, 32, 39)  # Switch 1, 3, 32, 33, 40
EXPECT_W0 = (1 << 0) | (1 << 2) | (1 << 31)
EXPECT_W1 = (1 << 0) | (1 << 7)
SWITCH_TABLE = 0x58DC40

# --- phase 5 datpatch ---------------------------------------------------------------------------
FIREBAT = 32
VALKYRIE = 58
VALK_TIME = 777  # B15-4: 아무 단계도 쓰지 않는 칸에 눈에 띄는 값을 넣고 몇 분 뒤 그대로인지 본다
VALK_SUPPLY = 7
RATIO_DUMP = 0x515B80
RATIO_A = 0x515BA0  # 0x515B88 표기가 맞을 때 128·192·256 이 시작하는 자리
RATIO_B = 0x515B9C  # 0x515B84(eudplib 주석)가 맞을 때

dat.unit(FIREBAT).set(maxHp=100 * 256)
dat.unit(VALKYRIE).set(timeCost=VALK_TIME, supplyUsed=VALK_SUPPLY)
dat.every_frame().unit(0).set(requirementOffset=0)
dat.every_frame().unit(1).set(requirementOffset=0)

dbg.snapshot("datpatch.B15-1.dump", RATIO_DUMP, 32, every=0, suite="datpatch")


def _read_field(table, name, index):
    """dat 필드 한 칸 값(상수 번호) — 4바이트 경계에서 읽고 마스크·시프트."""
    addr, shift, mask = dat.addr(table, name, index)
    v = f_dwread(addr)
    if mask != 0xFFFFFFFF:
        v = v & mask
    if shift:
        v = v >> shift
    return v


def f_switch_step(f):
    """phase 3: 1 프레임에 스위치를 켜고 48 프레임에 판정, 110 프레임에 지운다."""
    if EUDIf()(f == 1):
        DoActions([SetSwitch(i, Set) for i in SWITCHES])
    EUDEndIf()
    if EUDIf()(f == 48):
        w0 = f_dwread(SWITCH_TABLE)
        w1 = f_dwread(SWITCH_TABLE + 4)
        c1 = EUDVariable()
        c2 = EUDVariable()
        c1 << 0
        c2 << 0
        RawTrigger(conditions=Switch(0, Set), actions=c1.SetNumber(1))
        RawTrigger(conditions=Switch(1, Cleared), actions=c2.SetNumber(1))
        dbg.mark("switch.A-2.w0", w0, suite="switch")
        dbg.mark("switch.A-2.w1", w1, suite="switch")
        dbg.mark("switch.A-2.cond1", c1, suite="switch")
        dbg.mark("switch.A-2.cond2", c2, suite="switch")
        dbg.check("switch.A-2.w0", w0 == EXPECT_W0, suite="switch")
        dbg.check("switch.A-2.w1", w1 == EXPECT_W1, suite="switch")
        dbg.check("switch.A-2.cond1", c1 == 1, suite="switch")
        dbg.check("switch.A-2.cond2", c2 == 1, suite="switch")
        f_simpleprint("\x07[A-2]\x04 0x58DC40 =", w0, hptr(w0), "(기대 %d = 0x%08X)" % (EXPECT_W0, EXPECT_W0),
                      " 0x58DC44 =", w1, hptr(w1), "(기대 %d = 0x%08X)" % (EXPECT_W1, EXPECT_W1))
        aa.f_say("\x07[A-2]\x04 조건 확인: Switch 1 켜짐 = {} (1), Switch 2 꺼짐 = {} (1)", c1, c2)
    EUDEndIf()
    if EUDIf()(f == 110):  # 정리: 다음 단계가 스위치를 쓰지 않게 지운다
        DoActions([SetSwitch(i, Clear) for i in SWITCHES])
    EUDEndIf()


def f_switch_clean():
    """정리 확인: 스위치 표 두 칸이 0 (진행기가 112 프레임에 부른다)."""
    dbg.check("aa.clean.switch", [Memory(SWITCH_TABLE, Exactly, 0), Memory(SWITCH_TABLE + 4, Exactly, 0)])


# --- phase 4 s8 (A-1, B15-5) --------------------------------------------------------------------


def f_s8_step(f):
    """phase 4: 2 프레임에 S8 시험을 돌리고 결과를 블록에 남긴다. 3 프레임에 SUBX·ADDX 줄을 띄운다."""
    if EUDIf()(f == 2):
        s8.run_tests()
        s8.dbg_report(prefix="s8", suite="s8")
        n = s8._line_count()
        s8._print_line(n - 2)  # SUBX 줄
        s8._print_line(n - 1)  # ADDX 줄
    EUDEndIf()


# --- phase 5 datpatch (B15-1·3·4·10) ------------------------------------------------------------


def _ratio_start():
    """128·192·256(폭발형 소형·중형·대형)이 시작하는 주소 (못 찾으면 0)."""
    start = EUDVariable()
    start << 0
    for addr in (RATIO_A, RATIO_B):
        RawTrigger(conditions=[Memory(addr, Exactly, 128), Memory(addr + 4, Exactly, 192),
                               Memory(addr + 8, Exactly, 256)],
                   actions=start.SetNumber(addr))
    return start


def f_datpatch_step(f):
    """phase 5: 24 프레임에 피해 배율 표를 덤프하고 dat 칸을 읽는다(시작 1회 목록이 적용된 뒤)."""
    if EUDIf()(f == 24):
        dbg.capture("datpatch.B15-1.dump")
        start = _ratio_start()
        dbg.mark("datpatch.B15-1.start", start, suite="datpatch")
        dbg.check("datpatch.B15-1.found", start >= 1, suite="datpatch")
        d0 = f_dwread(RATIO_B)
        d1 = f_dwread(RATIO_A)
        f_simpleprint("\x07[B15-1]\x04 0x515B9C =", d0, " 0x515BA0 =", d1,
                      " (128·192·256 이 시작하는 자리 =", start, hptr(start), ") 128 은 폭발형×소형")
        tc = _read_field("units", "timeCost", VALKYRIE)
        su = _read_field("units", "supplyUsed", VALKYRIE)
        mx = _read_field("units", "maxHp", FIREBAT)
        r0 = _read_field("units", "requirementOffset", 0)
        r1 = _read_field("units", "requirementOffset", 1)
        dbg.mark("datpatch.B15-4.time", tc, suite="datpatch")
        dbg.mark("datpatch.B15-4.supply", su, suite="datpatch")
        dbg.mark("datpatch.B15-3.max", mx, suite="datpatch")
        dbg.mark("datpatch.B15-10.req0", r0, suite="datpatch")
        dbg.mark("datpatch.B15-10.req1", r1, suite="datpatch")
        dbg.check("datpatch.B15-4.set", [tc.Exactly(VALK_TIME), su.Exactly(VALK_SUPPLY)], suite="datpatch")
        dbg.check("datpatch.B15-3.max", mx == 100 * 256, suite="datpatch")
        dbg.check("datpatch.B15-10.req", [r0.Exactly(0), r1.Exactly(0)], suite="datpatch")
        f_simpleprint("\x07[B15-4]\x04 발키리 timeCost =", tc, "(%d)" % VALK_TIME, " supplyUsed =", su,
                      "(%d)" % VALK_SUPPLY, " / [B15-3] 파이어뱃 최대 체력 =", mx, "(25600)",
                      " / [B15-10] 요구 오프셋 =", r0, r1, "(0 0)")
    EUDEndIf()


def f_datpatch_final():
    """phase 18: 시작 1회 목록으로 바꾼 값이 몇 분 뒤에도 그대로인가 (B15-4)."""
    tc = _read_field("units", "timeCost", VALKYRIE)
    su = _read_field("units", "supplyUsed", VALKYRIE)
    mx = _read_field("units", "maxHp", FIREBAT)
    r0 = _read_field("units", "requirementOffset", 0)
    dbg.mark("final.B15-4.time", tc, suite="final")
    dbg.mark("final.B15-4.supply", su, suite="final")
    dbg.mark("final.B15-3.max", mx, suite="final")
    dbg.mark("final.B15-10.req0", r0, suite="final")
    dbg.check("final.B15-4.keep", [tc.Exactly(VALK_TIME), su.Exactly(VALK_SUPPLY), mx.Exactly(100 * 256)],
              suite="final")
    dbg.check("final.B15-10.req", r0.Exactly(0), suite="final")
    aa.f_say("\x07[B15-4]\x04 몇 분 뒤 dat 칸: timeCost {} ({}) supplyUsed {} ({}) 최대 체력 {} (25600)",
             tc, VALK_TIME, su, VALK_SUPPLY, mx)
