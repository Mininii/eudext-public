"""`bullet` 파이썬 참조 구현 — 사용자판 CreateBullet 이 내는 칸 값·dat 액션을 명세(S4)대로 옮긴 것 (DESIGN 4.15 시험).

`eudext.bullet` 과 **따로** 짠다: 주소는 datpatch 표가 아니라 S4 2.4·6.2 의 기준 주소 + 번호 식으로, 방향은
`ref_mathx`(CtrigAsm Lua 원문을 줄 단위로 옮긴 참조)로 구한다.

원문 (약칭은 S4 머리 표)
- UE_RE `func.lua:34~60` CallCBullet, `:86~114` Call_CreateBulletXY (정본 칸 패치, 수명 12)
- M2 `func.lua:2085~2116` Call_CBullet (이동 목표 3칸·turnSpeed 127·수명 30), `:2320~2342` 속도·수명 헬퍼
- Galaxy.py `:6~34` (위치·방향·주문만)
"""

import ref_mathx as R

M32 = 0xFFFFFFFF
FIRE = 135
TIMERS = {"ue_re": 12, "m2": 30, "minimal": None}
UNIT_EPD0 = 19025
UNIT_PTR0 = 0x59CCA8

# S4 2.4 / 2.1 의 기준 주소
FLINGY_TOP = 0x6C9EF8  # dword × 209
FLINGY_ACCEL = 0x6C9C78  # word × 209
FLINGY_HALT = 0x6C9930  # dword × 209
WEAPON_REMOVE = 0x657040  # byte × 130
UNIT_ELEVATION = 0x663150  # byte × 228
WEAPON_ATTACK_ANGLE = 0x656990  # byte × 130 (사용자판 높이 버그 칸)
WEAPON_MIN_RANGE = 0x656A18  # dword × 130 (UE_RE 버그가 덮는 곳)


def epd_of(i):
    return UNIT_EPD0 + 84 * i


def ptr_of(i):
    return UNIT_PTR0 + 336 * i


def timer_of(recipe, remove_timer=None):
    t = TIMERS[recipe] if remove_timer is None else remove_timer
    return t or None


def facing_to(sx, sy, tx, ty, reverse=True):
    """CreateBulletXY 의 방향: 표[f_Atan2(출발 − 목표)] + 64 (reverse). reverse=False 면 목표 − 출발."""
    if reverse:
        a = R.atan2(R.u32(sy - ty), R.u32(sx - tx))
    else:
        a = R.atan2(R.u32(ty - sy), R.u32(tx - sx))
    return R.to_dir256_tep(a)


def heading_to_facing(heading, reverse=True):
    return ((heading + 128) if reverse else heading) & 0xFF


def patch(recipe, facing, pos, remove_timer=None, shell_unit=None):
    """생성 뒤 칸 쓰기 {EPD 오프셋: (값, 마스크)} (S4 2.2 표, 5.2 의사코드)."""
    f = (facing & 0xFF) << 8
    out = {22: (pos & M32, M32), 19: (FIRE << 8, 0xFF00)}
    if recipe == "m2":
        out.update({4: (pos, M32), 6: (pos, M32), 7: (pos, M32), 8: (f | (127 << 16), 0xFFFF00)})
    else:
        out[8] = (f, 0xFF00)
    if recipe == "ue_re":
        out.update({40: (0, 0xFF000000), 55: (0x200104, 0x300104), 57: (0, M32)})
    t = timer_of(recipe, remove_timer)
    if t:
        out[68] = (t, 0xFFFF)
    if shell_unit is not None:
        out[25] = (shell_unit, 0xFFFF)
    return out


def pos_word(x, y):
    """모델이 만든 유닛의 +0x28 dword (x, y 는 word)."""
    return (x & 0xFFFF) | ((y & 0xFFFF) << 16)


def _byte_write(base, index, value):
    a = base + index
    sh = 8 * (a & 3)
    return (a & ~3, "SetTo", (value & 0xFF) << sh, 0xFF << sh)


def _word_write(base, index, value):
    a = base + 2 * index
    sh = 8 * (a & 3)
    return (a & ~3, "SetTo", ((value & 0xFFFF) << sh) & M32, (0xFFFF << sh) & M32)


def speed_writes(flingy, v, reverse=True, halt=None):
    """SetBulletSpeed / SetFlingySpeed (S4 2.4): 최고속도 ← 0xFFFFFFFF − v (reverse), 가속도 ← v, [정지 거리]."""
    out = [(FLINGY_TOP + 4 * flingy, "SetTo", (M32 - v) if reverse else v, M32),
           _word_write(FLINGY_ACCEL, flingy, v)]
    if halt is not None:
        out.append((FLINGY_HALT + 4 * flingy, "SetTo", halt & M32, M32))
    return out


def time_writes(weapon, t):
    """WeaponTimeLeft: removeAfter[weapon] ← t."""
    return [_byte_write(WEAPON_REMOVE, weapon, t)]


def height_writes(unit, h):
    """올바른 높이 칸: elevation[unit] ← h (사용자판의 0x656990 + 유닛 이 아니다)."""
    return [_byte_write(UNIT_ELEVATION, unit, h)]


def elevation_addr(unit):
    a = UNIT_ELEVATION + unit
    return a & ~3, 8 * (a & 3)


def forbidden(addr, mask=M32):
    """사용자판 높이 버그가 쓰던 칸인가: attackAngle 표 **밖**(0x656990 + 130 이상, 번호 ≥ 130 = 유닛 번호)부터 minRange 표 끝까지.

    addr 은 4의 배수 주소, mask 가 덮는 바이트만 본다(무기 128·129 의 attackAngle 바이트 쓰기는 정상).
    """
    lo, hi = WEAPON_ATTACK_ANGLE + 130, WEAPON_MIN_RANGE + 4 * 130
    return any((mask >> (8 * b)) & 0xFF and lo <= addr + b < hi for b in range(4))
