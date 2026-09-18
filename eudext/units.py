"""방금 만든 유닛, 유닛별 저장 (DESIGN 4.10).

CtrigAsm 맵마다 반복되던 세 가지 틀을 eudplib 방식으로 준다.
- "방금 만든 유닛 잡기": `CreateUnit` 직전에 0x628438(다음에 쓸 빈 유닛 칸)을 읽어 두고 뒤에 바뀌었는지 본다
  (R1: 10맵 311회, 그중 `f_Read(FP, 0x628438, …)` 136회). → `capture()` / `Capture` / `create()`
- EXCC(유닛 칸마다 N 줄 저장, R1: 8맵 361회) → `UnitData` (필드마다 1700칸 + 여분 1칸, 칸당 4B)
- EXCC 의 죽은 유닛 인식·ResetFlag(행 전체 0) → `clear_on_death()`, `dying()`
- `EUDLoopNewUnit` 감싸기 + 칸 번호 → `new_units()`
- `CUnit` (eudplib scdata) 다시 내보내기 — `MoveCp` 관용구(R1: 345회) 대신 멤버 이름으로 쓴다.

파이썬:

    from eudext import units
    data = units.UnitData(hp2="dword", stack="word", flags="byte")
    with units.capture() as u:                 # 0x628438 → u.ptr / u.epd / u.index (= u.index_before)
        data.clear(u.index_before)             # 생성 전에 그 칸을 초기화 (EXCC 초기화·on_create 훅 대체)
        DoActions(CreateUnit(1, "Zerg Zergling", "Anywhere", P8))
    if EUDIf()(u.ok):                          # 0x628438 이 바뀌었으면 생성 성공
        data.hp2[u] += 5                       # 칸 번호 자리에 Capture·UnitRef 를 그대로 넣어도 된다
        units.CUnit(u.epd).set_color(P1)
    EUDEndIf()
    data.of(epd).stack = 3                     # EPD(또는 포인터·CUnit) → 칸 번호 변환 후 쓰기
    for nu in units.new_units(clear=data): …   # 새 유닛마다 (nu.ptr, nu.epd, nu.index), 그 칸의 data 를 먼저 0 으로
    for d in units.dying(data, key="flags"): … # 죽는 중(주문 0)이고 flags ≠ 0 인 칸마다 한 번, 끝나면 행 초기화
    units.clear_on_death(data)                 # 죽는 중인 칸의 행을 기본값으로 (본문 없는 빠른 판)

epScript (컨텍스트 관리자 대신 `begin()`/`end()`, 3.11):

    import eudext.units as units;
    const data = units.UnitData(hp2="dword", stack="word");
    const u = units.Capture();
    function f() {
        u.begin(); CreateUnit(1, "Zerg Zergling", "Anywhere", P8); u.end();
        if (u.ok) { data.hp2[u.index] += 5; }
        const c = units.create(1, "Terran Marine", "Anywhere", P8, on_create=data);   // 한 줄 판
        foreach (nu : units.new_units()) { data.stack[nu.index] = 1; }
    }

칸 번호: 유닛 칸 i(0~1699)의 포인터·EPD 는 `slot(i)`, 반대는 `index(epd 또는 ptr)`. 번호 간격은 API 에 드러내지 않는다(3.9).
빈 칸이 없거나 잘못된 값이면 칸 번호는 `NO_INDEX`(=1700)다. `UnitData` 는 1701칸이라 이 칸에 써도 안전하다(버리는 칸).
"""

import functools
import struct

from eudplib import (
    EPD,
    Add,
    AtLeast,
    AtMost,
    CreateUnit,
    CreateUnitWithProperties,
    CUnit,
    CurrentPlayer,
    Db,
    DoActions,
    EUDEndWhile,
    EUDFunc,
    EUDLightBool,
    EUDLightVariable,
    EUDLoopNewUnit,
    EUDNot,
    EUDSetContinuePoint,
    EUDVariable,
    EUDWhileNot,
    Exactly,
    ExprProxy,
    Forward,
    Memory,
    MemoryEPD,
    MemoryXEPD,
    NextTrigger,
    RawTrigger,
    SeqCompute,
    SetDeaths,
    SetDeathsX,
    SetMemory,
    SetMemoryEPD,
    SetMemoryXEPD,
    SetNextPtr,
    SetNextTrigger,
    SetTo,
    Subtract,
    VProc,
    f_bread_epd,
    f_dwread_epd,
    f_setcurpl2cpcache,
    f_wread_epd,
    unProxy,
)

from eudext import _compat, _parts
from eudext.errors import fail

__all__ = [
    "CUnit",
    "Capture",
    "NEXT_UNIT_ADDR",
    "NO_INDEX",
    "UNIT_COUNT",
    "UNIT_TABLE",
    "UnitData",
    "UnitField",
    "UnitRef",
    "UnitRow",
    "capture",
    "clear_on_death",
    "create",
    "dying",
    "f_capture",
    "f_clear_on_death",
    "f_create",
    "f_dying",
    "f_index",
    "f_new_units",
    "f_next_slot",
    "f_slot",
    "index",
    "new_units",
    "next_slot",
    "slot",
]

M32 = 0xFFFFFFFF
UNIT_TABLE = 0x59CCA8  # CUnit 표 시작 (eudplib CUnit.range 와 같음)
UNIT_COUNT = 1700
NO_INDEX = UNIT_COUNT  # 빈 칸 없음·잘못된 값 → 이 칸 번호. UnitData 의 버리는 칸
NEXT_UNIT_ADDR = 0x628438  # 다음에 쓸 빈 유닛 칸의 포인터 (없으면 0)

# 내부 전용 (3.9: 번호 간격 리터럴을 API 밖으로 드러내지 않는다)
_STRIDE = 336
_EPD_STRIDE = 84
_EPD0 = EPD(UNIT_TABLE)  # 19025
_PTR_MAX = UNIT_TABLE + _STRIDE * (UNIT_COUNT - 1)
_EPD_MAX = _EPD0 + _EPD_STRIDE * (UNIT_COUNT - 1)
_BITS = 11  # 1699 < 2**11
_SLOTS = UNIT_COUNT + 1  # UnitData 한 필드의 칸 수 (마지막 = 버리는 칸)
_ORDER_EPD = 0x4C // 4  # CUnit +0x4C dword 의 둘째 바이트 = orderID
_ORDER_MASK = 0xFF00
_CP = 0x6509B0
_KINDS = {"dword": M32, "word": 0xFFFF, "byte": 0xFF}
_SCAN_CHUNKS = (1, 2, 4, 5, 10, 17, 20, 25, 34, 50)  # 1700 의 약수 (한 번에 볼 칸 수)

# 한 프로세스 여러 빌드(시험·비용 도구): EUDLoopNewUnit 그림자 표가 빌드마다 쌓이지 않게 한다 (WP0 보고서 (d))
_compat.register_build_reset(_compat.reset_new_unit_loops)


# =============================================================================================
# 칸 번호 ↔ 포인터·EPD
# =============================================================================================


def _const_index(v):
    v &= M32
    if UNIT_TABLE <= v <= _PTR_MAX:
        q, r = divmod(v - UNIT_TABLE, _STRIDE)
    elif _EPD0 <= v <= _EPD_MAX:
        q, r = divmod(v - _EPD0, _EPD_STRIDE)
    else:
        q = r = None
    if q is None or r:
        fail("units.index: 유닛 포인터·EPD 가 아닌 상수 0x%X", v)
    return q


def _emit_sub_chain(t, idx, base, stride):
    # t ∈ [base, base + stride·1699] → idx = (t − base) / stride. t 는 함수 인자(복사본)라 고쳐도 된다.
    RawTrigger(actions=[t.AddNumber((-base) & M32), idx.SetNumber(0)])
    for k in reversed(range(_BITS)):
        w = stride << k
        # t ≥ w 인 것을 조건이 보장하므로 Add(−w) 는 한 바퀴 돌지 않는다 (3.5-7)
        RawTrigger(conditions=t.AtLeast(w), actions=[t.AddNumber((-w) & M32), idx.AddNumber(1 << k)])


@functools.cache
def _index_func():
    """포인터 또는 EPD(변수) → 칸 번호. 범위 밖이면 NO_INDEX. 반환 변수에 바로 쓴다."""
    ret = EUDVariable()

    @EUDFunc
    def _unit_index(t):
        ptr_path, invalid, end = Forward(), Forward(), Forward()
        _parts.jump_if([t.AtLeast(UNIT_TABLE), t.AtMost(_PTR_MAX)], ptr_path)
        _parts.jump_if_not([t.AtLeast(_EPD0), t.AtMost(_EPD_MAX)], invalid)
        _emit_sub_chain(t, ret, _EPD0, _EPD_STRIDE)
        SetNextTrigger(end)
        ptr_path << NextTrigger()
        _emit_sub_chain(t, ret, UNIT_TABLE, _STRIDE)
        SetNextTrigger(end)
        invalid << RawTrigger(actions=ret.SetNumber(NO_INDEX))
        end << NextTrigger()

    return _compat.predefine_returns(_unit_index, [ret])


@functools.cache
def _slot_func():
    """칸 번호(변수, 0~1699) → (포인터, EPD). 반환 변수에 바로 쓴다."""
    ptr, epd = EUDVariable(), EUDVariable()

    @EUDFunc
    def _unit_slot(t):
        RawTrigger(actions=[ptr.SetNumber(UNIT_TABLE), epd.SetNumber(_EPD0)])
        for k in reversed(range(_BITS)):
            RawTrigger(
                conditions=t.AtLeast(1 << k),
                actions=[t.AddNumber((-(1 << k)) & M32), ptr.AddNumber(_STRIDE << k), epd.AddNumber(_EPD_STRIDE << k)],
            )

    return _compat.predefine_returns(_unit_slot, [ptr, epd])


def f_index(x):
    """유닛 포인터·EPD·CUnit → 칸 번호 (0~1699, 아니면 NO_INDEX).

    `Capture`·`UnitRef` 를 넘기면 이미 아는 `.index` 를 그대로 돌려준다(트리거 0).
    인자: x(상수·EUDVariable·CUnit·Capture·UnitRef). 포인터(≥ 0x59CCA8)와 EPD 는 값 범위로 가린다.
    반환: 상수면 int(틀린 상수는 빌드 오류), 변수면 새 EUDVariable
    비용: 상수 0 / 변수 = 본문 30 (1벌) / 호출 자리 1 / 실행 19 (범위 밖 7) (docs/COSTS.md, 2026-09-16)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const i = units.index(epd);` (→ `units.f_index`)
    출처: DESIGN 4.10 `(ptr − 0x59CCA8) // 336`. 나눗셈 대신 11비트 뺄셈 사슬(새로 작성)
    """
    if isinstance(x, (Capture, UnitRef)):
        return x.index
    v = unProxy(x)
    if isinstance(v, bool):
        fail("units.index: bool 은 받지 않습니다")
    if isinstance(v, int):
        return _const_index(v)
    if _compat.is_var(v):
        return _index_func()(v)
    fail("units.index: 유닛 포인터·EPD(상수·변수)·CUnit·Capture·UnitRef 가 아닙니다 (%r)", x)


index = f_index


def f_slot(i):
    """칸 번호 → (포인터, EPD). `index()` 의 반대.

    인자: i(상수 0~1699 또는 EUDVariable — 변수가 1700 이상이면 결과는 표 밖 주소)
    반환: (ptr, epd) — 상수면 int 둘, 변수면 새 EUDVariable 둘
    비용: 상수 0 / 변수 = 본문 13 (1벌) / 호출 자리 1 / 실행 17 (docs/COSTS.md, 2026-09-16)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const ptr, epd = units.slot(i);` (→ `units.f_slot`)
    출처: 새로 작성
    """
    v = unProxy(i)
    if isinstance(v, int) and not isinstance(v, bool):
        if not 0 <= v < UNIT_COUNT:
            fail("units.slot: 칸 번호 %d 가 0~1699 밖입니다", v)
        return UNIT_TABLE + _STRIDE * v, _EPD0 + _EPD_STRIDE * v
    if _compat.is_var(v):
        return _slot_func()(v)
    fail("units.slot: 칸 번호는 상수 또는 EUDVariable 이어야 합니다 (%r)", i)


slot = f_slot


def _as_index(x):
    """칸 번호 자리에 온 값: int·변수는 그대로, Capture·UnitRef 는 .index, CUnit 은 변환."""
    if isinstance(x, (Capture, UnitRef)):
        return x.index
    if isinstance(x, CUnit):
        return f_index(x)
    v = unProxy(x)
    if isinstance(v, bool):
        fail("units: 칸 번호에 bool 은 받지 않습니다")
    if isinstance(v, int):
        if not 0 <= v <= NO_INDEX:
            fail("units: 칸 번호 %d 가 0~1700 밖입니다", v)
        return v
    if _compat.is_var(v):
        return v
    fail("units: 칸 번호는 상수·EUDVariable·Capture·UnitRef·CUnit 이어야 합니다 (%r)", x)


# =============================================================================================
# 다음 빈 칸 읽기와 생성 판정
# =============================================================================================


def _emit_next_slot(ptr, epd, idx):
    # 0x628438 을 변수로 복사하지 않고, 조건의 문턱값을 고쳐 가며 11비트 이진 탐색을 한다.
    # 비트 k 조건: [0x628438] ≥ 0x59CCA8 + 336·(앞서 찾은 칸 + 2^k). 참이면 아래 비트의 문턱값에 336·2^k 를 더한다.
    thr0 = [UNIT_TABLE + (_STRIDE << k) for k in range(_BITS)]
    conds = [Memory(NEXT_UNIT_ADDR, AtLeast, thr0[k]) for k in range(_BITS)]
    RawTrigger(
        actions=[ptr.SetNumber(UNIT_TABLE), epd.SetNumber(_EPD0), idx.SetNumber(0)]
        + [SetMemory(conds[k] + 8, SetTo, thr0[k]) for k in range(_BITS)]
    )
    for k in reversed(range(_BITS)):
        RawTrigger(
            conditions=conds[k],
            actions=[ptr.AddNumber(_STRIDE << k), epd.AddNumber(_EPD_STRIDE << k), idx.AddNumber(1 << k)]
            + [SetMemory(conds[j] + 8, Add, _STRIDE << k) for j in range(k)],
        )
    RawTrigger(
        conditions=Memory(NEXT_UNIT_ADDR, Exactly, 0),
        actions=[ptr.SetNumber(0), epd.SetNumber(0), idx.SetNumber(NO_INDEX)],
    )


@functools.cache
def _next_slot_func():
    rets = [EUDVariable(), EUDVariable(), EUDVariable()]

    @EUDFunc
    def _next_unit_slot():
        _emit_next_slot(*rets)

    return _compat.predefine_returns(_next_unit_slot, rets)


def f_next_slot():
    """다음에 만들어질 유닛 칸(0x628438)을 (포인터, EPD, 칸 번호)로 읽는다. 빈 칸이 없으면 (0, 0, NO_INDEX).

    `Capture` 가 쓰는 부품이다. bullet·spawn 처럼 생성 흐름을 직접 짜는 모듈도 쓸 수 있다.
    인자: 없음
    반환: (ptr, epd, index) 새 EUDVariable 셋
    비용: 본문 14 (1벌) / 호출 자리 1 / 실행 18 (docs/COSTS.md, 2026-09-16). eudplib `f_cunitepdread_epd` 는 칸 번호를 주지 않는다
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const ptr, epd, i = units.next_slot();` (→ `units.f_next_slot`)
    출처: CtrigAsm 관용구 `f_Read(FP, 0x628438, ptr, epd, 0xFFFFFF)` (R1), 칸 번호는 새로 작성
    """
    return _next_slot_func()()


next_slot = f_next_slot


class Capture:
    """방금 만든 유닛 잡기: 생성 코드 앞뒤에서 0x628438 을 비교한다.

    `begin()` 이 0x628438 을 읽어 `ptr`·`epd`·`index` 에 두고, `end()` 가 그 값이 바뀌었는지(= 생성 성공)를
    `ok` 에 기록한다. 파이썬은 `with units.capture() as u:` 로, epScript 는 `u.begin(); …; u.end();` 로 쓴다.
    여러 번 써도 된다(같은 변수에 덮어쓴다).

    속성: `ptr`, `epd`, `index`(= `index_before`, 생성 **전에** 알 수 있는 칸 번호 — on_create 훅에 넘긴다,
          S1 11-6), `ok`(조건: 생성 성공 — 읽을 때마다 새 조건), `failed`(조건: 실패), `cunit`(eudplib CUnit)
    의미:
    - 한 블록에서 여러 마리를 만들면 ptr/epd/index 는 **첫** 유닛이고, ok 는 "하나라도 만들었다" 이다.
    - 터렛이 있는 유닛(골리앗·탱크)은 본체가 먼저 칸을 가져간다고 본다(인게임 확인 항목).
    - 빈 칸이 없으면 ptr = epd = 0, index = NO_INDEX, ok = 거짓. **ok 를 확인하기 전에는 epd 로 쓰지 않는다**
      (EPD 0 은 P1 마린 데스 칸이다, 3.9).
    - 블록 안에서 다른 트리거가 유닛을 만들고 지워 0x628438 이 제자리로 돌아오는 경우는 가리지 못한다.
    인자: ptr/epd/index(선택: 결과를 받을 EUDVariable. 없으면 새로 만든다)
    반환: -
    비용: begin = 호출 자리 1 / 실행 18, end = 호출 자리 2 / 실행 3, 본문(읽기 함수) 14 1벌 (docs/COSTS.md, 2026-09-16).
          변수 3개(216B) + 1비트
    CP: 바꾸지 않음
    로컬: 공유 안전 (생성은 모든 클라이언트에서 같은 조건으로 — 3.7)
    epScript: `const u = units.Capture(); … u.begin(); CreateUnit(…); u.end(); if (u.ok) { … }`
    출처: CtrigAsm 관용구 `f_Read(FP,0x628438,"X",Nextptrs,0xFFFFFF)` + 생성 뒤 비교(R1 2절, S4 0절 1~2)
    """

    __slots__ = ("_ok", "_open", "epd", "index", "ptr")

    def __init__(self, ptr=None, epd=None, index=None):
        for name, v in (("ptr", ptr), ("epd", epd), ("index", index)):
            if v is not None and not isinstance(unProxy(v), EUDVariable):
                fail("units.Capture: %s 는 EUDVariable 이어야 합니다 (%r)", name, v)
        self.ptr = unProxy(ptr) if ptr is not None else EUDVariable()
        self.epd = unProxy(epd) if epd is not None else EUDVariable()
        self.index = unProxy(index) if index is not None else EUDVariable()
        if len({id(self.ptr), id(self.epd), id(self.index)}) != 3:
            fail("units.Capture: ptr/epd/index 는 서로 다른 변수여야 합니다")
        self._ok = EUDLightBool()
        self._open = False

    def __repr__(self):
        return "<units.Capture %s>" % ("열림" if self._open else "닫힘")

    def begin(self):
        """생성 코드 앞: 0x628438 을 읽는다."""
        if self._open:
            fail("units.Capture: begin() 을 두 번 불렀습니다 (end() 먼저)")
        self._open = True
        _next_slot_func()(ret=[self.ptr, self.epd, self.index])
        return self

    def end(self):
        """생성 코드 뒤: 0x628438 이 begin 때 값과 다르면 ok."""
        if not self._open:
            fail("units.Capture: begin() 없이 end() 를 불렀습니다")
        self._open = False
        same = Memory(NEXT_UNIT_ADDR, Exactly, 0)
        VProc(self.ptr, [self._ok.Set(), *self.ptr.QueueAssignTo(EPD(same) + 2)])
        RawTrigger(conditions=same, actions=self._ok.Clear())
        return self

    def __enter__(self):
        return self.begin()

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.end()
        else:
            self._open = False
        return False

    @property
    def index_before(self):
        return self.index

    @property
    def ok(self):
        return self._ok.IsSet()

    @property
    def failed(self):
        return self._ok.IsCleared()

    @property
    def cunit(self):
        return CUnit.cast(self.epd, ptr=self.ptr)


def f_capture(ptr=None, epd=None, index=None):
    """`Capture` 를 만든다: `with units.capture() as u:` (DESIGN 4.10 이름).

    인자·반환·비용: `Capture` 와 같음
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const u = units.capture();` (→ `units.f_capture`). 컨텍스트 관리자가 없으므로 `u.begin()`/`u.end()`
    출처: DESIGN 4.10
    """
    return Capture(ptr, epd, index)


capture = f_capture


def _data_list(x):
    if x is None:
        return []
    if isinstance(x, UnitData):
        return [x]
    if isinstance(x, (list, tuple)):
        out = []
        for y in x:
            out.extend(_data_list(y))
        return out
    fail("units: UnitData(또는 그 목록)가 아닙니다 (%r)", x)


def f_create(count, unit, where, owner, props=None, on_create=None, into=None):
    """`Capture` + `CreateUnit`(또는 `CreateUnitWithProperties`) 한 줄 판.

    인자: count, unit, where(로케이션 이름 또는 1-based 번호), owner — eudplib CreateUnit 과 같음(변수도 됨),
          props(UnitProperty — 주면 CreateUnitWithProperties),
          on_create(생성 직전에 부를 것: UnitData 또는 그 목록이면 그 칸을 초기화, 함수면 `on_create(u.index_before)`),
          into(결과를 받을 Capture, 없으면 새로 만든다)
    반환: Capture (`ok`, `epd`, `index` …)
    비용: Capture 비용 + 생성 액션 1 트리거 (+ on_create)
    CP: 바꾸지 않음 (on_create 가 바꾸면 그대로)
    로컬: 공유 안전
    epScript: `const u = units.create(1, "Terran Marine", "Anywhere", P8, on_create=data);` (→ `units.f_create`)
    출처: S1 8.5 spawn_one 4번(`on_create(u.index_before)` → CreateUnitWithProperties)
    """
    u = into if into is not None else Capture()
    if not isinstance(u, Capture):
        fail("units.create: into 는 Capture 여야 합니다 (%r)", into)
    with u:
        if on_create is not None:
            if callable(on_create) and not isinstance(on_create, UnitData):
                on_create(u.index_before)
            else:
                for d in _data_list(on_create):
                    d.clear(u.index_before)
        if props is None:
            DoActions(CreateUnit(count, unit, where, owner))
        else:
            DoActions(CreateUnitWithProperties(count, unit, where, owner, props))
    return u


create = f_create


# =============================================================================================
# UnitData — 유닛 칸마다 저장 (EXCC 대체)
# =============================================================================================


def _distinct(v, *others):
    """v 가 others 중 하나와 같은 변수 객체면 복사본을 돌려준다(한 변수 트리거를 두 곳에 쓰지 않게)."""
    if any(v is o for o in others):
        t = EUDVariable()
        t << v
        return t
    return v


def _neg_var(v):
    t = EUDVariable()
    # t = 0xFFFFFFFF ⊖ v + 1 = −v (32비트). 0xFFFFFFFF ≥ v 이므로 Subtract 가 포화하지 않는다 (3.5-7)
    SeqCompute([(t, SetTo, M32), (t, Subtract, v), (t, Add, 1)])
    return t


class UnitField(ExprProxy):
    """`UnitData` 의 한 필드(1700칸 + 버리는 칸). `data.이름` 으로 얻는다. EUDArray 처럼 쓴다.

    칸 번호 자리에는 int(0~1700)·EUDVariable·Capture·UnitRef·CUnit 을 넣을 수 있다.
    인자: (메서드) i = 칸 번호, v = 상수 또는 EUDVariable
    반환: 읽기는 새 EUDVariable, 조건 메서드는 Condition(또는 1비트 조건), 쓰기는 None
    - 읽기 `f[i]` / `f.get(i)`, 쓰기 `f[i] = v` / `f.set(i, v)` — word/byte 필드는 값의 아래 16/8비트만 남는다.
    - `f.iadd(i, v)` = wrap 덧셈, `f.isub(i, v)` = **wrap** 뺄셈, `f.isub_sat(i, v)` = **포화** 뺄셈(0 에서 멈춤, 3.5).
      epScript `f[i] += v;` `f[i] -= v;` 는 각각 `iadditem`·`isubitem`(wrap)으로 번역된다.
      파이썬 `f[i] += v` 는 읽고 다시 쓰므로 맞지만 비싸다 → `f.iadd(i, v)` 를 쓴다.
    - `f.iand(i, 상수)`, `f.ior(i, 상수)` (비트), 그 밖의 연산은 epScript 에서 읽고-쓰기로 처리된다.
    - 조건 `f.eq(i, v)`, `ne`, `le`, `ge`, `lt`, `gt` (epScript `f[i] == v` → `eqitem`). 칸 번호가 변수면
      조건을 만드는 순간 패치 트리거를 낸다(3.4) — 조건은 바로 그 자리에서 쓴다. 값이 변수인 `ne`/`lt`/`gt` 는
      그 자리에서 1비트에 결과를 받는다(eudplib `EUDNot` 이 패치되는 비교값을 뒤집지 못한다).
    - `f.clear(i)` = 기본값으로.
    주의: 변수 칸 번호는 0~1700 이어야 한다(실행 중 검사 없음 — EUDArray 와 같다). 유닛에서 얻은 번호(`index()`,
          Capture, UnitRef)는 늘 이 범위다.
    비용 (실행 트리거, docs/COSTS.md, 2026-09-16): 상수 칸 쓰기 1, 변수 칸 dword 쓰기·덧셈·포화 뺄셈 3, 변수 값 wrap 뺄셈 6,
          word/byte 덧셈 4(값도 변수면 5), 변수 칸 읽기 dword 38 / word 22 / byte 14, 변수 칸 조건 준비 2(값도 변수면 3),
          값이 변수인 ne/lt/gt +2. 호출 자리는 1~3
    CP: 바꾸지 않음 (word/byte 연산은 CP 를 잠깐 옮기고 `f_setcurpl2cpcache` 로 되돌린다, 3.6)
    로컬: 공유 안전
    epScript: `data.hp2[i] += 5;`, `if (data.flags[i] == 1) { … }`, `data.stack.isub_sat(i, 3);`
    출처: EXCC `Set_EXCC2`/`Cond_EXCC2`/`Set_EXCC2X` 대체(R1), eudplib 0.81 `collections/eudarray.py` 연산 모양
    """

    __slots__ = ("_base", "data", "default", "kind", "mask", "name")

    def __init__(self, data, name, kind, default, base):
        super().__init__(base)
        self.data = data
        self.name = name
        self.kind = kind
        self.mask = _KINDS[kind]
        self.default = default
        self._base = base

    def __repr__(self):
        return "<units.UnitField %s:%s>" % (self.name, self.kind)

    def __len__(self):
        return UNIT_COUNT

    @property
    def length(self):
        return UNIT_COUNT

    @property
    def epd(self):
        """칸 0 의 EPD (ConstExpr). 칸 i = epd + i."""
        return self._base

    # --- 쓰기 부품 ---
    def _masked(self):
        return self.mask != M32

    def _apply(self, i, mod, v, post_mask):
        """[칸 i] ← mod v. post_mask 면 그 뒤 필드 폭 밖 비트를 지운다."""
        i = _as_index(i)
        v = unProxy(v)
        vvar = _compat.is_var(v)
        if not vvar:
            if not _compat.is_const(v):
                fail("units.%s: 값은 상수 또는 EUDVariable 이어야 합니다 (%r)", self.name, v)
            if isinstance(v, int):
                v &= M32
        clear_hi = SetDeathsX(CurrentPlayer, SetTo, 0, 0, ~self.mask & M32)
        if isinstance(i, int):
            addr = self._base + i
            post = [SetMemoryXEPD(addr, SetTo, 0, ~self.mask & M32)] if post_mask else []
            if not vvar:
                RawTrigger(actions=[SetMemoryEPD(addr, mod, v), *post])
                return
            SeqCompute([(addr, mod, v)])
            if post:
                RawTrigger(actions=post)
            return
        if vvar:
            v = _distinct(v, i)
            if not post_mask:
                VProc([i, v], [v.SetDest(self._base), *i.QueueAddTo(EPD(v.getDestAddr())), v.SetModifier(mod)])
                return
            VProc(
                [i, v],
                [SetMemory(_CP, SetTo, self._base), *i.QueueAddTo(EPD(_CP)), v.SetDest(CurrentPlayer), v.SetModifier(mod)],
            )
            f_setcurpl2cpcache(actions=[clear_hi])
            return
        if not post_mask:
            act = SetDeaths(0, mod, v, 0)
            VProc(i, [SetMemory(act + 16, SetTo, self._base), *i.QueueAddTo(EPD(act) + 4)])
            RawTrigger(actions=act)
            return
        VProc(i, [SetMemory(_CP, SetTo, self._base), *i.QueueAddTo(EPD(_CP))])
        f_setcurpl2cpcache(actions=[SetDeaths(CurrentPlayer, mod, v, 0), clear_hi])

    def _single(self, i, act_fn):
        """칸 i 에 액션 하나(act_fn(epd))를 실행한다."""
        i = _as_index(i)
        if isinstance(i, int):
            RawTrigger(actions=act_fn(self._base + i))
            return
        act = act_fn(0)
        VProc(i, [SetMemory(act + 16, SetTo, self._base), *i.QueueAddTo(EPD(act) + 4)])
        RawTrigger(actions=act)

    # --- 읽기·쓰기 ---
    def get(self, i):
        i = _as_index(i)
        addr = self._base + i
        if self.kind == "dword":
            return f_dwread_epd(addr)
        if self.kind == "word":
            return f_wread_epd(addr, 0)
        return f_bread_epd(addr, 0)

    def set(self, i, v):
        v = unProxy(v)
        if isinstance(v, int) and not isinstance(v, bool):
            self._apply(i, SetTo, v & self.mask, False)
        else:
            self._apply(i, SetTo, v, self._masked() and _compat.is_var(v))

    def __getitem__(self, i):
        return self.get(i)

    def __setitem__(self, i, v):
        self.set(i, v)

    def __iter__(self):
        fail("units.UnitField 는 순회할 수 없습니다")

    def iadd(self, i, v):
        """wrap 덧셈 (필드 폭 기준)."""
        v = unProxy(v)
        if isinstance(v, int) and not isinstance(v, bool):
            v &= self.mask
            if v == 0:
                return
        self._apply(i, Add, v, self._masked())

    def isub(self, i, v):
        """wrap 뺄셈 (0 아래로 가면 한 바퀴 돈다, 필드 폭 기준)."""
        v = unProxy(v)
        if isinstance(v, int) and not isinstance(v, bool):
            if v & M32 == 0:
                return
            self._apply(i, Add, (-v) & M32, self._masked())
            return
        if not _compat.is_var(v):
            fail("units.%s.isub: 값은 상수 또는 EUDVariable 이어야 합니다 (%r)", self.name, v)
        self._apply(i, Add, _neg_var(v), self._masked())

    def isub_sat(self, i, v):
        """포화 뺄셈 (0 에서 멈춘다). SC Subtract 액션."""
        v = unProxy(v)
        if isinstance(v, int) and not isinstance(v, bool) and v & M32 == 0:
            return
        self._apply(i, Subtract, v, False)

    def iand(self, i, v):
        v = unProxy(v)
        if not isinstance(v, int) or isinstance(v, bool):
            raise AttributeError("units.UnitField.iand: 상수 마스크만 됩니다")
        self._single(i, lambda a: SetMemoryXEPD(a, SetTo, 0, ~v & M32))

    def ior(self, i, v):
        v = unProxy(v)
        if not isinstance(v, int) or isinstance(v, bool):
            raise AttributeError("units.UnitField.ior: 상수 마스크만 됩니다")
        bits = v & self.mask
        if bits:
            self._single(i, lambda a: SetMemoryXEPD(a, SetTo, M32, bits))

    def clear(self, i):
        self._apply(i, SetTo, self.default, False)

    # epScript 훅 (eudplib epscript/helper.py _ARRW, _ARRC)
    iadditem = iadd
    isubitem = isub
    isubtractitem = isub_sat
    ianditem = iand
    ioritem = ior

    # --- 조건 ---
    def _cond(self, i, cmp, v):
        i = _as_index(i)
        v = unProxy(v)
        if isinstance(i, int):
            return MemoryEPD(self._base + i, cmp, v)
        if _compat.is_var(v):
            v = _distinct(v, i)
            c = MemoryEPD(0, cmp, 0)
            VProc([i, v], [SetMemory(c + 4, SetTo, self._base), *i.QueueAddTo(EPD(c) + 1), *v.QueueAssignTo(EPD(c) + 2)])
            return c
        c = MemoryEPD(0, cmp, v)
        VProc(i, [SetMemory(c + 4, SetTo, self._base), *i.QueueAddTo(EPD(c) + 1)])
        return c

    def _not(self, i, cmp, v):
        i = _as_index(i)
        c = self._cond(i, cmp, v)
        if isinstance(i, int) or not _compat.is_var(unProxy(v)):
            return EUDNot(c)  # 비교값이 상수거나 칸이 상수(eudplib 이 변수 비교값을 패치하고 1비트로 뒤집는다)
        # eudplib EUDNot 은 조건의 비교값을 컴파일 시점에 고쳐 뒤집는다(AtLeast v → AtMost v−1).
        # 비교값을 실행 중에 패치하는 조건에는 쓸 수 없으므로 1비트에 결과를 받아 뒤집는다.
        flag = EUDLightBool()
        RawTrigger(actions=flag.Set())
        RawTrigger(conditions=c, actions=flag.Clear())
        return flag.IsSet()

    def eq(self, i, v):
        return self._cond(i, Exactly, v)

    def ne(self, i, v):
        return self._not(i, Exactly, v)

    def le(self, i, v):
        return self._cond(i, AtMost, v)

    def ge(self, i, v):
        return self._cond(i, AtLeast, v)

    def lt(self, i, v):
        return self._not(i, AtLeast, v)

    def gt(self, i, v):
        return self._not(i, AtMost, v)

    eqitem = eq
    neitem = ne
    leitem = le
    geitem = ge
    ltitem = lt
    gtitem = gt


_ROW_METHODS = {"iaddattr": "iadd", "isubattr": "isub", "iandattr": "iand", "iorattr": "ior",
                "eqattr": "eq", "neattr": "ne", "leattr": "le", "geattr": "ge", "ltattr": "lt", "gtattr": "gt"}


class UnitRow:
    """`UnitData` 의 한 칸(유닛 하나)을 필드 이름으로 읽고 쓰는 뷰. `data.of(epd)` / `data.at(i)` 로 얻는다.

    `row.이름` 읽기(트리거가 나온다 — 여러 번 읽으면 변수에 받아 둔다), `row.이름 = v` 쓰기,
    epScript `row.이름 += v;`(wrap) `row.이름 -= v;`(wrap) `if (row.이름 == v)`, 파이썬 `row.isub_sat("이름", v)`.
    인자: data(UnitData), i(칸 번호 — `of`/`at` 가 정한다)
    반환: -
    비용: `UnitField` 와 같음 (칸 번호는 뷰를 만들 때 한 번 구한다)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const r = data.of(epd); r.stack += 1;`
    출처: EXCC `Set_EXCC`/`Cond_EXCC`(단락 안 쓰기·검사) 대체
    """

    __slots__ = ("_data", "index")

    def __init__(self, data, i):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "index", i)

    def __repr__(self):
        return "<units.UnitRow %r>" % (self.index,)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        m = _ROW_METHODS.get(name)
        if m is not None:
            return lambda attr, v: getattr(self._data.field(attr), m)(self.index, v)
        return self._data.field(name).get(self.index)

    def __setattr__(self, name, v):
        if name in UnitRow.__slots__:
            fail("units.UnitRow: %s 는 바꿀 수 없습니다", name)
        self._data.field(name).set(self.index, v)

    def isub_sat(self, name, v):
        self._data.field(name).isub_sat(self.index, v)

    def clear(self):
        self._data.clear(self.index)


class UnitData:
    """유닛 칸마다 값을 두는 표 (EXCC 대체, DESIGN 4.10).

    인자: 필드=형 키워드. 형은 "dword" | "word" | "byte", 또는 (형, 기본값) 튜플(기본값은 초기값이자 `clear` 값).
    반환: -
    저장: 필드마다 1701칸(1700 + 버리는 칸 NO_INDEX) × 4B, 한 `Db` 에 이어 둔다(칸 i 의 EPD = 필드 시작 + i).
          필드 형은 값 폭이다(word/byte 는 쓸 때 아래 비트만 남긴다). 읽기는 폭만큼만 읽어 싸다.
    사용: `data.이름[i]`(UnitField), `data.of(epd·ptr·CUnit·Capture·UnitRef)` / `data.at(i)`(UnitRow),
          `data.clear(i)`, `data.fields`(이름 튜플), `data.field(이름)`
    비용: 메모리 필드당 6,804B. scx 증가(압축 뒤, 기본값 0)는 1700×1 약 150B, ×6 약 440B, ×20 약 1.2KB
          (2026-09-16 실측, docs/COSTS.md — 3.8 목표 "1700×N 은 EUDArray, scx < 1KB" 충족).
          `clear(i)` = 상수 칸 실행 1, 변수 칸 실행 4 (필드 수와 무관, 필드 60개까지)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const data = units.UnitData(hp2="dword", stack="word");` (const 로 묶는다)
    출처: EXCC(`Install_EXCC`, DPS function.lua:1439, R2 1.8) — VarBlock 대신 EUDArray 방식(R2 4.4 권고)
    """

    __slots__ = ("_db", "_fields", "_order")
    _RESERVED = frozenset(("of", "at", "clear", "field", "fields", "nbytes"))

    def __init__(self, **fields):
        if not fields:
            fail("units.UnitData: 필드를 하나 이상 주세요 (예: UnitData(hp=\"dword\"))")
        specs = []
        for name, spec in fields.items():
            if name.startswith("_") or name in UnitData._RESERVED:
                fail("units.UnitData: 필드 이름 %r 는 쓸 수 없습니다", name)
            if isinstance(spec, str):
                kind, default = spec, 0
            elif isinstance(spec, (tuple, list)) and len(spec) == 2:
                kind, default = spec
            else:
                fail("units.UnitData: %s 의 형은 \"dword\"/\"word\"/\"byte\" 또는 (형, 기본값) 입니다 (%r)", name, spec)
            if kind not in _KINDS:
                fail("units.UnitData: %s 의 형 %r 은 dword/word/byte 가 아닙니다", name, kind)
            if isinstance(default, bool) or not isinstance(default, int) or not 0 <= default <= _KINDS[kind]:
                fail("units.UnitData: %s 의 기본값 %r 이 %s 범위 밖입니다", name, default, kind)
            specs.append((name, kind, default))
        if len(specs) > 60:
            fail("units.UnitData: 필드는 60개까지입니다 (%d)", len(specs))
        blob = b"".join(struct.pack("<I", d) * _SLOTS if d else bytes(4 * _SLOTS) for _n, _k, d in specs)
        db = Db(blob)
        object.__setattr__(self, "_db", db)
        base = EPD(db)
        flist = []
        for k, (name, kind, default) in enumerate(specs):
            flist.append(UnitField(self, name, kind, default, base + k * _SLOTS))
        object.__setattr__(self, "_order", tuple(flist))
        object.__setattr__(self, "_fields", {f.name: f for f in flist})

    def __repr__(self):
        return "<units.UnitData %s>" % ", ".join("%s:%s" % (f.name, f.kind) for f in self._order)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        try:
            return self._fields[name]
        except KeyError:
            raise AttributeError("units.UnitData 에 필드 %r 가 없습니다" % name) from None

    def __setattr__(self, name, v):
        fail("units.UnitData: 필드를 통째로 바꿀 수 없습니다 (data.%s[i] = 값 으로 쓰세요)", name)

    def field(self, name):
        try:
            return self._fields[name]
        except KeyError:
            fail("units.UnitData 에 필드 %r 가 없습니다 (있는 것: %s)", name, ", ".join(self._fields))

    @property
    def fields(self):
        return tuple(f.name for f in self._order)

    @property
    def nbytes(self):
        return 4 * _SLOTS * len(self._order)

    def at(self, i):
        """칸 번호 i 의 행 뷰 (변환 없음)."""
        return UnitRow(self, _as_index(i))

    def of(self, x):
        """유닛(EPD·포인터·CUnit, 또는 Capture·UnitRef)의 행 뷰. EPD·포인터 변수는 여기서 칸 번호로 바꾼다."""
        if isinstance(x, (Capture, UnitRef)):
            return UnitRow(self, x.index)
        return UnitRow(self, f_index(x))

    def clear(self, i):
        """칸 i 의 모든 필드를 기본값으로. i 는 칸 번호 자리 값(int·변수·Capture·UnitRef·CUnit)."""
        i = _as_index(i)
        if isinstance(i, int):
            RawTrigger(actions=[SetMemoryEPD(f._base + i, SetTo, f.default) for f in self._order])
            return
        acts = []
        for k, f in enumerate(self._order):
            if k:
                acts.append(SetMemory(_CP, Add, _SLOTS))
            acts.append(SetDeaths(CurrentPlayer, SetTo, f.default, 0))
        VProc(i, [SetMemory(_CP, SetTo, self._order[0]._base), *i.QueueAddTo(EPD(_CP))])
        f_setcurpl2cpcache(actions=acts)


# =============================================================================================
# 유닛 순회
# =============================================================================================


class UnitRef:
    """순회가 주는 유닛 하나: `ptr`, `epd`, `index`, `cunit`. `for ptr, epd, i in …` 로 풀어도 된다.

    변수는 순회가 가진 것이다. 다음 반복에서 바뀌므로 오래 두려면 복사한다.
    인자: ptr, epd, i(EUDVariable — 순회가 만든다)
    반환: -
    비용: 없음(묶음일 뿐). `cunit` 은 복사 없이 CUnit 으로 감싼다
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `foreach (nu : units.new_units()) { data.hp[nu.index] = 1; }`
    출처: 새로 작성 (eudplib EUDLoopNewUnit 의 (ptr, epd) + 칸 번호)
    """

    __slots__ = ("epd", "index", "ptr")

    def __init__(self, ptr, epd, i):
        self.ptr = ptr
        self.epd = epd
        self.index = i

    def __repr__(self):
        return "<units.UnitRef>"

    def __iter__(self):
        return iter((self.ptr, self.epd, self.index))

    @property
    def cunit(self):
        return CUnit.cast(self.epd, ptr=self.ptr)


def f_new_units(allowance=2, clear=None):
    """새로 생긴 유닛마다 한 번 도는 순회 (eudplib `EUDLoopNewUnit` + 칸 번호).

    인자: allowance(eudplib 과 같음: 이미 본 유닛을 이만큼 만나면 멈춘다. 새 유닛은 활성 목록 앞쪽 두 자리에 들어온다),
          clear(UnitData 또는 목록: 새 유닛을 내주기 전에 그 칸을 기본값으로 — 칸 재사용 대비)
    반환: 생성기 — 반복마다 UnitRef(ptr, epd, index)
    의미: eudplib 규칙 그대로 — 활성 유닛 목록(0x628430)을 앞에서부터 보며 고유 바이트(+0xA5)가 그림자 표와 다른 유닛을
          새 유닛으로 본다. 실행 시점은 이 순회를 둔 자리(트리거 실행 중)라서, 앞 사이클의 트리거 뒤·이번 사이클 이 자리
          앞에 생긴 유닛(생산·트리거 생성 모두)이 나온다. 같은 사이클에 이 자리보다 **뒤**에서 만든 유닛은 다음 사이클에 나온다.
          미리 놓인 유닛은 첫 사이클에 나올 수 있다(고유 바이트가 0 이 아니면).
    주의: `clear=` 는 새 유닛을 처음 볼 때 그 칸을 지우므로, `capture` 의 on_create 나 같은 사이클 이 순회 앞에서 그 유닛에
          써 둔 값도 지운다 — 생성 직후 값을 쓰는 표에는 `clear=` 를 쓰지 않거나, 값을 순회 뒤(다음 사이클)에 쓴다.
    비용: 순회 1곳마다 eudplib 그림자 표 571KB(메모리). scx 증가는 첫 순회 약 6.9KB(eudplib `EUDLoopNewUnit` 자체 6.2KB —
          그중 0 으로 찬 표가 약 4.4KB), 둘째 순회부터 약 0.7KB씩 (docs/COSTS.md, 2026-09-16). 호출 자리 38.
          실행: 새 유닛당 약 66(eudplib 순회 약 46 + 칸 번호 20, clear 표마다 +4), 이미 본 유닛 확인은 allowance 개까지 약 40씩.
    CP: 바꾸지 않음 (eudplib 순회가 되돌린다)
    로컬: 공유 안전
    epScript: `foreach (nu : units.new_units()) { data.hp[nu.index] = 1; }` (→ `units.f_new_units`)
    출처: eudplib 0.81 `eudlib/utilf/listloop.py:153` EUDLoopNewUnit, CtrigAsm `CunitCtrig_Part*`(R1) 대체
    """
    datas = _data_list(clear)
    for ptr, epd in EUDLoopNewUnit(allowance):
        i = _index_func()(epd)
        for d in datas:
            d.clear(i)
        yield UnitRef(ptr, epd, i)


new_units = f_new_units


def _chunks(items, n):
    for k in range(0, len(items), n):
        yield items[k:k + n]


def _emit_scan(chunk, make_slot, extra_init=()):
    """1700칸을 chunk 칸씩 도는 순회를 낸다. make_slot(j) → (조건들, 액션들, 패치들[(주소, 칸 0 값, 칸당 증가)]).

    반복마다: 칸 j 트리거 chunk 개 → 패치 증가 트리거(들) → 끝 검사 1. 끝 검사 트리거의 next 는 시작 때 되돌린다.
    """
    if chunk not in _SCAN_CHUNKS:
        fail("units: chunk 는 1700 의 약수 %s 중 하나여야 합니다 (%r)", _SCAN_CHUNKS, chunk)
    slots = [make_slot(j) for j in range(chunk)]
    patches = [p for s in slots for p in s[2]]
    counter = EUDLightVariable()
    top, test, done = Forward(), Forward(), Forward()
    init = [SetMemory(a, SetTo, v0) for a, v0, _d in patches]
    init += [counter.SetNumber(0), SetNextPtr(test, top), *extra_init]
    for part in _chunks(init, 64):
        RawTrigger(actions=part)
    top << NextTrigger()
    for conds, acts, _p in slots:
        if len(conds) > 16 or len(acts) > 64:
            fail("units: 칸 트리거의 조건 %d / 액션 %d 가 한도를 넘습니다", len(conds), len(acts))
        RawTrigger(conditions=conds, actions=acts)
    inc = [SetMemory(a, Add, d * chunk) for a, _v0, d in patches] + [counter.AddNumber(chunk)]
    for part in _chunks(inc, 64):
        RawTrigger(actions=part)
    test << RawTrigger(nextptr=top, conditions=counter.AtLeast(UNIT_COUNT), actions=SetNextPtr(test, done))
    done << NextTrigger()


def _order_cond(j):
    epd0 = _EPD0 + _ORDER_EPD + _EPD_STRIDE * j
    c = MemoryXEPD(epd0, Exactly, 0, _ORDER_MASK)
    return c, (c + 4, epd0, _EPD_STRIDE)


def _key_field(datas, key):
    if key is None:
        return None
    if isinstance(key, UnitField):
        kf = key
    elif isinstance(key, str):
        kf = None
        for d in datas:
            if key in d._fields:
                kf = d._fields[key]
                break
        if kf is None:
            fail("units: key 필드 %r 가 주어진 UnitData 에 없습니다", key)
    else:
        fail("units: key 는 필드 이름 또는 UnitField 입니다 (%r)", key)
    if kf.default != 0:
        fail("units: key 필드 %s 의 기본값은 0 이어야 합니다 (%d)", kf.name, kf.default)
    return kf


def _key_cond(kf, j):
    c = MemoryEPD(kf._base + j, AtLeast, 1)
    return c, (c + 4, kf._base + j, 1)


def f_clear_on_death(*datas, key=None, chunk=20):
    """죽는 중인 유닛 칸(주문 +0x4D == 0)의 UnitData 행을 기본값으로 되돌리는 1700칸 순회를 낸다 (EXCC ResetFlag 대체).

    인자: datas(UnitData 하나 이상), key(선택: 필드 이름 또는 UnitField — 주면 그 필드가 0 이 아닌 칸만 지운다.
          기본값 0 인 필드여야 한다), chunk(한 트리거 묶음에 볼 칸 수, 1700 의 약수 — 클수록 실행이 적고 본문이 크다)
    반환: None
    의미: 주문 0 은 죽는 중인 유닛과 빈 칸(한 번도 안 쓴 칸 포함)이다. key 가 없으면 이런 칸을 매번 모두 지운다(같은 값을
          다시 쓰는 것이라 결과는 같다). 죽은 유닛의 칸이 이 순회보다 먼저 다시 쓰이면 지우지 못한다 → 생성 쪽에서
          `capture` + `data.clear(u.index_before)` 또는 `new_units(clear=data)` 로 막는다.
    비용: 호출 자리 = chunk + 증가 트리거 + 초기화 + 1 (chunk 20·필드 3 → 25, chunk 50 → 59).
          실행 = 1700 × (1 + (증가 트리거 + 1)/chunk) + 초기화 (chunk 20 → 1,957, chunk 50 → 1,874 /사이클.
          원본 EXCC 는 유닛 트리거 1700 + α). scx 약 1.9KB(UnitData 1700×3 포함). docs/COSTS.md, 2026-09-16
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `units.clear_on_death(data);` (→ `units.f_clear_on_death`)
    출처: EXCC `Install_EXCC(…, ResetFlag)` + 죽은 유닛 단락(theSeed MapLogic/CunitSystem.lua:329, orderID == 0 판정)
    """
    datas = _data_list(list(datas))
    if not datas:
        fail("units.clear_on_death: UnitData 를 하나 이상 주세요")
    kf = _key_field(datas, key)
    flist = [f for d in datas for f in d._order]

    def make_slot(j):
        oc, op = _order_cond(j)
        conds, patches = [oc], [op]
        if kf is not None:
            kc, kp = _key_cond(kf, j)
            conds.append(kc)
            patches.append(kp)
        acts = []
        for f in flist:
            a = SetMemoryEPD(f._base + j, SetTo, f.default)
            acts.append(a)
            patches.append((a + 16, f._base + j, 1))
        return conds, acts, patches

    _emit_scan(chunk, make_slot)


clear_on_death = f_clear_on_death


def f_dying(*datas, key, chunk=20, limit=None):
    """죽는 중(주문 0)이고 key 필드가 0 이 아닌 유닛 칸마다 한 번 도는 순회. 본문 뒤 그 칸의 datas 를 기본값으로 되돌린다.

    EXCC 의 "죽은 유닛 인식" 단락(DUnitCalc) 대체. 본문이 끝나면(EUDContinue 포함) key 가 0 이 되므로 다음 사이클에는
    다시 나오지 않는다. **EUDBreak 는 쓰지 않는다** — 그 칸도 지우지 않으므로 다음 사이클에 같은 칸이 다시 나온다.
    한 사이클에 처리할 수를 줄이려면 `limit` 을 준다(남은 칸은 다음 사이클에 나온다).
    인자: datas(UnitData 하나 이상 — 행을 되돌릴 표), key(필드 이름 또는 UnitField, 기본값 0), chunk(`clear_on_death` 와 같음),
          limit(선택: 한 사이클에 내줄 최대 칸 수, 1 이상 상수)
    반환: 생성기 — 반복마다 UnitRef(ptr, epd, index). 칸 번호 오름차순.
    의미: 1단계에서 1700칸을 chunk 칸씩 보고 걸린 칸 번호를 대기열(1700칸)에 모은 뒤, 2단계에서 하나씩 내준다.
          key 는 살아 있을 때 찍어 두는 표식이다(예: `new_units()` 에서 `data.alive[nu.index] = 1`).
          같은 표에 `clear_on_death()` 를 함께 쓰지 않는다 — 죽는 칸의 key 를 먼저 지워 알림이 사라진다(limit 로 남긴 칸 포함).
    비용: 호출 자리 31 (chunk 20). 실행 = 1단계 1700 × (1 + 2/chunk) + 초기화(chunk 20 → 1,874/사이클),
          걸린 칸마다 + 약 60 + 본문. 메모리: 대기열 6,800B + 변수 3. docs/COSTS.md, 2026-09-16
    CP: 바꾸지 않음 (본문이 바꾸면 그대로)
    로컬: 공유 안전
    epScript: `foreach (d : units.dying(data, key="alive")) { … d.epd … }` (→ `units.f_dying`)
    출처: theSeed MapLogic/CunitSystem.lua:329 (orderID == 0 + 생존 도장 + 행 리셋), MSF_Respect_V System.lua:1119
    """
    datas = _data_list(list(datas))
    if not datas:
        fail("units.dying: UnitData 를 하나 이상 주세요")
    kf = _key_field(datas, key)
    if kf is None:
        fail("units.dying: key 필드를 주세요 (죽음을 한 번만 알리는 표식)")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        fail("units.dying: limit 은 1 이상 정수 상수입니다 (%r)", limit)
    queue = Db(4 * UNIT_COUNT)
    qepd = EPD(queue)
    qn, qr = EUDVariable(), EUDVariable()
    # 칸 j 트리거의 대기열 쓰기: player = 대기열 위치(걸릴 때마다 모든 칸 트리거가 +1), 값 = 칸 번호(반복마다 +chunk)
    writes = [SetMemoryEPD(qepd, SetTo, j) for j in range(chunk)]

    def make_slot(j):
        oc, op = _order_cond(j)
        kc, kp = _key_cond(kf, j)
        acts = [writes[j], qn.AddNumber(1), *[SetMemory(w + 16, Add, 1) for w in writes]]
        return [oc, kc], acts, [op, kp, (writes[j] + 20, j, 1)]

    extra = [qn.SetNumber(0), qr.SetNumber(qepd)] + [SetMemory(w + 16, SetTo, qepd) for w in writes]
    _emit_scan(chunk, make_slot, extra)
    if limit is not None and limit < UNIT_COUNT:
        RawTrigger(conditions=qn.AtLeast(limit + 1), actions=qn.SetNumber(limit))
    if EUDWhileNot()(qn.Exactly(0)):
        i = f_dwread_epd(qr)
        ptr, epd = _slot_func()(i)
        yield UnitRef(ptr, epd, i)
        EUDSetContinuePoint()
        for d in datas:
            d.clear(i)
        # qn ≥ 1 을 루프 조건이 보장한다 (3.5-7)
        DoActions([qn.SubtractNumber(1), qr.AddNumber(1)])
    EUDEndWhile()


dying = f_dying
