"""Ccode(`Cell`) — 비교·설정만 하는 4바이트 값 칸, 1비트 깃발, 배열·플레이어별 칸 (DESIGN 4.3, 3.5).

CtrigAsm 의 Ccode(`CreateCcode`, `CD`, `SetCD` …)를 eudplib 방식으로 준다. 정수 코드(Line·Index)는 없고 핸들은 객체다.

    from eudext.cell import Cell, Flag, PCell, CreateCcode, CreateCcodes, CreateCcodeArr, CD, SetCD, AddCD, SubCD
    c = Cell(0)                      # = CreateCcode()
    c << 3; c += v; c -= 1           # 대입·덧셈·뺄셈(wrap) — 값이 변수여도 된다
    c.isub_sat(v)                    # 포화 뺄셈 (0 에서 멈춤)
    if EUDIf()(c >= v): …            # 비교는 cmp 와 같다 (모든 경계 정확)
    DoActions(SetCD(c, 5), SubCD(c)) # CtrigAsm 이름 = 원래 의미 (SubCD 는 포화)

    import eudext.cell as cell;      // epScript
    const c = cell.Cell(0);          // const 로 묶는다 (var 에 담으면 32비트 변수로 바뀐다)
    c.v -= x;  c.isub_sat(x);  if (c == 3) { … }  if (c.v >= x) { … }  var y = c.v;

## 어떤 저장소를 고를까 (DESIGN 3.8)

`Cell` 은 `EUDLightVariable`(4바이트)이다. **비교·설정·덧셈만** 하는 값에 쓴다. 값을 변수로 **읽을** 때마다
`f_dwread_epd`(실행 약 36 트리거)가 든다 → 자주 읽는 값은 `EUDVariable`(72바이트, 읽기 0)에 둔다.
참/거짓은 `Flag`(1비트), 많은 값은 `CellArray`(칸당 4바이트).

## 동작 (4.3 표)

| 동작 | `EUDLightVariable` 그대로 | `Cell` |
|---|---|---|
| 상수 대입·비교 | 됨 | 같음 (대입 1 트리거, 비교 0 — 경계값은 `cmp` 규칙대로 접는다) |
| 변수 대입 `c << v`, `c += v` | 오류 | `SeqCompute` 로 자동 전환 (호출 1) |
| 변수로 읽기 | 오류 (`v << c` 도 오류) | `c.read()` / `c.v` → `f_dwread_epd` |
| `-=` | **포화**(`VariableBase.__isub__`) | **wrap** 으로 고정 (`_parts.isub32`). epScript `c.v -= x;`, `c.isub(x);` 도 wrap |
| 포화 뺄셈 | `SubtractNumber(k)` | `c.isub_sat(v)`(값이 변수여도), `c.SubtractNumber(k)`(eudplib 그대로 포화 액션), `SubCD` |
| 변수와 비교, `AtMost(0xFFFFFFFF)` | `EUDNot` 에서 틀림 | `cmp` 로 전환 (`Forward` 자리 표시·경계 접기 — 부정도 맞음) |

**경고: `EUDLightVariable -= x` 는 포화(0 에서 멈춤), `Cell -= x` 는 wrap(한 바퀴 돎)이다.** 0 에서 멈춰야 하면
`c.isub_sat(x)` 나 `SubCD(c, x)` 를 쓴다(DESIGN 3.5). 같은 칸끼리 `c -= c` 는 0 이다(eudplib `v -= v` 버그를 피함).

- `<<` 는 대입, `<<=`·`>>=` 는 eudplib 그대로 **시프트**(상수), `|=`·`&=`·`^=` 는 상수 마스크만(eudplib 그대로).
- 값: 정수 상수(−2³¹ ~ 2³²−1, 2³² 나머지), 주소식(`EPD(…)`, `Forward`), `EUDVariable`, 다른 칸(`Cell`,
  `EUDLightVariable` — 읽어서 쓴다). `Flag`/`EUDLightBool`·조건은 값이 아니다(`EudextError`).
- 파이썬 `if c:` 는 오류(늘 참이 되는 실수를 막는다). 실행 중 판정은 `EUDIf()(c)`(= `c ≠ 0`) 또는 비교를 쓴다.
- epScript 에서 const `Cell` 에 `c -= 1;`·`c = 1;` 은 번역 오류("Undefined variable c_1") → `c.v -= 1;`, `c.v = 1;`.
  `var y = c;` 도 오류 → `var y = c.v;`. 파이썬 `c.v += 1` 은 읽고-쓰기라 비싸다 → `c += 1`.

## 배열·플레이어별 칸

`CellArray(n)`(= `CreateCcodeArr(n)`)은 `EUDArray` 위에 있다. **상수 색인 `arr[3]` 은 `Cell` 뷰**(모든 Cell 연산),
**변수 색인은 읽기·쓰기 함수**다: `arr[i]`(= `arr.get(i)`, 새 EUDVariable), `arr[i] = v`(= `arr.set(i, v)`),
`arr.iadditem(i, v)`, `arr.isubitem(i, v)`(wrap), `arr.isub_sat(i, v)`(포화), `arr.eqitem(i, v)` 등 비교.
epScript `arr[i] = v; arr[i] += v; arr[i] -= v; if (arr[i] == v)` 는 이 메서드로 번역된다(`CellArray` 는 `ExprProxy`).
**파이썬 `arr[i] << v`(변수 i)는 읽은 사본에 쓴다** → `arr[i] = v` 를 쓴다(eudplib `EUDArray` 와 같음).
`PCell()` 은 플레이어 8칸(CtrigAsm 의 플레이어 사본 대체): 색인에 `P1`~, `0`~`7`, `CurrentPlayer`, 변수를 넣는다.

## CtrigAsm 이름 (LibraryFor322.lua, 원래 의미)

`CD(c, 값=1, 비교=Exactly)`, `CDX(c, 값, 마스크, 비교=Exactly)` → 조건.
`SetCD(c, 값=1)`, `AddCD(c, 값=1)`, `SubCD(c, 값=1)`(**포화**), `SetCDX(c, 값, 마스크)` → 액션(`DoActions`/`Trigger` 에 넣는다).
설계 초안 모양 `CD(c, AtLeast, 3)`·`SetCD(c, SetTo, v)`(비교·수정자를 앞에)도 받는다.
모듈 함수 이름(epScript `cell.cd(…)` → `cell.f_cd(…)`): `f_cd`, `f_cdx`, `f_set_cd`, `f_set_cdx`, `f_add_cd`,
`f_subtract_cd`(포화 — 이름에 `subtract`, 3.5-3). `CreateCcode`·`CreateCcodes`·`CreateCcodeArr` 는 대문자라 그대로 불린다.

출처: CtrigAsm `CreateCcode`/`CreateCcodes`/`CreateCcodeArr`(CtrigAsm v5.5.lua:75959~75979),
`CD`/`CDX`/`SetCD`/`SetCDX`/`AddCD`/`SubCD`(LibraryFor322.lua:586~625, 740~759), `CDeaths`/`SetCDeaths`(CtrigAsm v5.5.lua:9047~9089);
DPS_Enhance eudplib-port a7aad90 `eud/ctrig/cells.py`(`epd_cond`/`epd_act` 칸 조건·액션 모양), `eud/ctrig/core.py:257`(Ccode = 변수);
eudext `cmp`(WP1) 칸 비교, `_parts.isub32`/`isub_sat32`, `units.UnitField`(WP10) 변수 색인 패치 모양; 2026-09-17 실험 `docs/proto/cell_exp.py`.
"""

from eudplib import (
    EPD,
    Add,
    Always,
    AtLeast,
    AtMost,
    Condition,
    EncodeComparison,
    EncodeModifier,
    EncodePlayer,
    EUDArray,
    EUDLightBool,
    EUDLightVariable,
    EUDVariable,
    Exactly,
    ExprProxy,
    Forward,
    List2Assignable,
    MemoryEPD,
    MemoryX,
    Never,
    RawTrigger,
    SeqCompute,
    SetMemory,
    SetMemoryEPD,
    SetMemoryX,
    SetTo,
    Subtract,
    TrgComparison,
    TrgModifier,
    f_dwread_epd,
    f_getcurpl,
    unProxy,
)

from eudext import _compat, _parts, cmp
from eudext.errors import fail

M32 = 0xFFFFFFFF
P1_MARINE_ADDR = 0x58A364  # EPD 0 — 저장소로 쓰지 않는다 (DESIGN 3.9)
MAX_PLAYERS = 12

__all__ = [
    "AddCD",
    "CD",
    "CDX",
    "Cell",
    "CellArray",
    "CreateCcode",
    "CreateCcodeArr",
    "CreateCcodes",
    "Flag",
    "PCell",
    "SetCD",
    "SetCDX",
    "SubCD",
    "add_cd",
    "cd",
    "cdx",
    "f_add_cd",
    "f_cd",
    "f_cdx",
    "f_set_cd",
    "f_set_cdx",
    "f_subtract_cd",
    "set_cd",
    "set_cdx",
    "subtract_cd",
]

# 값 종류
_K = "상수"  # 정수 상수 (32비트로 줄인 값)
_E = "주소식"  # 정수가 아닌 상수식
_V = "변수"  # EUDVariable
_M = "칸"  # 읽기 전용 값 칸 (Cell, EUDLightVariable …) — 값으로 쓰려면 읽어야 한다

_CMP_OP = {0: "ge", 1: "le", 10: "eq"}  # EncodeComparison 값 → cmp 함수 이름
_UNSET = object()


def _classify(x, fname, what="값"):
    """값 인자를 (종류, 값) 으로. 정수는 32비트로 줄인다(−2^31 ~ 2^32−1)."""
    if isinstance(x, (TrgComparison, TrgModifier)):
        fail("%s: %s 자리에 비교·수정자(%r)가 왔습니다 — 인자 순서를 확인하세요", fname, what, x)
    x = unProxy(x)
    if isinstance(x, bool):
        return _K, int(x)
    if isinstance(x, int):
        if not -(1 << 31) <= x < (1 << 32):
            fail("%s: %s %d 는 32비트 범위(−2^31 ~ 2^32−1) 밖입니다", fname, what, x)
        return _K, x & M32
    if isinstance(x, EUDLightBool):
        fail("%s: %s 에 Flag/EUDLightBool 은 넣을 수 없습니다 (조건은 IsSet() — 값이 아닙니다)", fname, what)
    if isinstance(x, (Condition, list, tuple)):
        fail("%s: %s 에 조건·목록은 넣을 수 없습니다 (%r)", fname, what, x)
    if _compat.is_var(x):
        return _V, x
    if _compat.is_varbase(x):
        return _M, x
    if x is not None and _compat.is_const(x):
        return _E, x
    fail("%s: %s 는 정수·주소식·EUDVariable·Cell 이어야 합니다 (%r)", fname, what, x)
    return None  # fail 은 돌아오지 않는다


def _read(x):
    """읽기 전용 칸의 값을 새 EUDVariable 로 읽는다 (f_dwread_epd)."""
    return f_dwread_epd(EPD(x.getValueAddr()))


def _as_var(kind, val):
    """칸이면 읽어서 변수로 바꾼다. (종류, 값)"""
    if kind == _M:
        return _V, _read(val)
    return kind, val


def _check_ret(fname, ret):
    if ret is None:
        return None
    if not isinstance(ret, (list, tuple)) or len(ret) != 1 or not _compat.is_var(ret[0]):
        fail("%s: ret 는 [EUDVariable] 이어야 합니다 (%r)", fname, ret)
    return [unProxy(ret[0])]


def _ph(value=0):
    """실행 중에 채울 amount 칸의 자리 표시. 정수가 아니므로 eudplib 이 제자리 부정을 하지 않는다 (DESIGN 3.4)."""
    f = Forward()
    f << value
    return f


def _selfcond(cmp_, amount):
    """자기 비트마스크 칸(조건 +0)을 읽는 조건 (출처: eudext/cmp.py `_selfcond`, eudplib 0.81 `__lt__` 방식)."""
    slot = Forward()
    c = MemoryEPD(slot, cmp_, amount)
    slot << EPD(c)
    return c


class _Fill:
    """한 번의 호출이 내는 앞 계산: 칸 채우기(SeqCompute 한 번) → 조건 트리거들.

    출처: eudext/cmp.py `_Plan`(WP1, DPS_Enhance eudplib-port a7aad90 core.py:365 pre_fill) 을 줄여 옮김.
    """

    __slots__ = ("consts", "trigs", "vars")

    def __init__(self):
        self.consts = []
        self.vars = []
        self.trigs = []

    def put(self, dst, value):
        self.consts.append((dst, SetTo, value))

    def set_sum(self, dst, const, var):
        """칸(EPD) ← const + var (32비트 wrap). const 는 정수·주소식, var 는 EUDVariable."""
        if isinstance(const, int):
            const &= M32
            if const == 0:
                self.vars.append((dst, SetTo, var))
                return
        self.consts.append((dst, SetTo, const))
        self.vars.append((dst, Add, var))

    def trig(self, conds, acts):
        self.trigs.append((conds, acts))

    def emit(self):
        pairs = self.consts + self.vars
        if pairs:
            SeqCompute(pairs)
        for conds, acts in self.trigs:
            RawTrigger(conditions=conds, actions=acts)


def _flag_not(fill, cond):
    """[cond 가 거짓] 을 자기 칸 깃발 조건 하나로 (깃발 ← 1, [cond] → 깃발 ← 0)."""
    k = _selfcond(AtLeast, 1)
    fill.put(EPD(k), 1)
    fill.trig([cond], [SetMemoryEPD(EPD(k), SetTo, 0)])
    return k


def _ret(conds):
    return conds[0] if len(conds) == 1 else conds


# ---------------------------------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------------------------------


class Cell(EUDLightVariable):
    """비교·설정만 하는 32비트 값 칸(4바이트). CtrigAsm Ccode 대체. `EUDLightVariable` 을 상속한다.

    인자: init — 정수 상수(초기값만, 트리거 0), 주소식(초기값만), EUDVariable·다른 칸(부른 자리에서 실행 중 대입)
    반환: -
    연산 (모듈 docstring 표):
      `c << v` 대입, `c += v` 덧셈(wrap), `c -= v` **뺄셈(wrap)**, `c.isub_sat(v)` **포화 뺄셈**,
      `c.read(ret=None)`/`c.v` 읽기, 비교 `== != < <= > >=`·`c.AtLeast(v)` 등(값이 변수면 `cmp` 로),
      `c.addr`/`c.epd`(주소 핸들 — CtrigAsm `_Ccode` 대체), `Cell.at(주소)`(있는 칸 감싸기),
      epScript 통로 `c.v = x;` `c.v += x;` `c.v -= x;`(wrap) `c.assign(x)` `c.iadd(x)` `c.isub(x)` `c.isub_sat(x)`
      `if (c.v == x)`.
    비용: 호출 자리 / 실행 (2026-09-17, docs/COSTS.md "cell (WP2)") — 만들기 0 / 0(4바이트),
          상수 대입·덧셈·wrap 뺄셈·포화 뺄셈 1 / 1, 변수 대입·덧셈·포화 뺄셈 1 / 2, 변수 wrap 뺄셈 3 / 5(`_parts.isub32`),
          읽기 `read()` = eudplib f_dwread_epd(공유 본문 + 호출 1~2 / 실행 약 36), 칸 값(다른 Cell)은 읽기 비용이 더해진다.
          비교 = `cmp` 와 같음(상수 0 / 0, `!= k` 2 / 2, 변수 1 / 2, `!=` 변수 2 / 3). **자주 읽는 값은 EUDVariable 에 둔다.**
    CP: 바꾸지 않음 (읽기는 f_dwread_epd 가 잠깐 옮기고 되돌림)
    로컬: 공유 안전 (넣는 값이 로컬 값이면 칸도 로컬 — DESIGN 3.7)
    epScript: `const c = cell.Cell(0); c.v -= x; c.isub_sat(x); if (c >= x) { … } var y = c.v;`
    출처: CtrigAsm `CreateCcode`, `CDeaths`/`SetCDeaths`, DESIGN 4.3 (2026-09-17 실험 docs/proto/cell_exp.py)
    """

    # 값 칸 주소는 자기 슬롯에 둔다(뷰는 새 메모리를 잡지 않는다). eudplib 은 칸 주소를 늘 getValueAddr() 로 읽는다.
    __slots__ = ("_addr",)

    def __init__(self, init=0):
        kind, val = _classify(init, "Cell", "초기값")
        if kind == _E:
            self._addr = _compat.eudarray_addr(EUDArray([val]))  # 주소식 초기값은 EUDArray 한 칸에 굽는다
            return
        super().__init__(val if kind == _K else 0)
        self._addr = EUDLightVariable.getValueAddr(self)
        if kind != _K:
            self.Assign(val)

    def getValueAddr(self):  # noqa: N802 — eudplib 이름
        return self._addr

    @classmethod
    def at(cls, addr):
        """있는 주소(4의 배수 상수·주소식)를 Cell 로 감싼다. P1 마린 데스 칸(0x58A364)은 오류(DESIGN 3.9).

        인자: addr(정수 또는 주소식 상수)
        반환: Cell (새 메모리를 잡지 않는다)
        비용: 없음(컴파일 시점)
        CP: 바꾸지 않음
        로컬: 공유 안전
        epScript: `const hp = cell.Cell.at(0x58A364 + 4 * 12);` (대문자 클래스 메서드라 이름 번역 없음)
        출처: 새로 작성 (CtrigAsm `_Ccode` 주소 핸들 대체)
        """
        a = unProxy(addr)
        if isinstance(a, bool) or _compat.is_var(a) or not (isinstance(a, int) or _compat.is_const(a)):
            fail("Cell.at: 주소는 상수(정수·주소식)여야 합니다 (%r)", addr)
        if isinstance(a, int):
            if not 0 <= a <= M32:
                fail("Cell.at: 주소 0x%X 가 32비트 밖입니다", a)
            if a & 3:
                fail("Cell.at: 주소 0x%X 는 4의 배수가 아닙니다", a)
            if a == P1_MARINE_ADDR:
                fail("Cell.at: 0x58A364(P1 마린 데스 칸, EPD 0)는 저장소로 쓰지 않습니다 (DESIGN 3.9)")
        return cls._view(a)

    @classmethod
    def _view(cls, addr):
        obj = cls.__new__(cls)
        obj._addr = addr
        return obj

    # --- 기본 ---
    def __repr__(self):
        return (
            "<eudext.cell.Cell @ %r — 값으로 쓰려면 c.read() / epScript c.v (epScript 에서는 var 대신 const 로 묶는다)>"
            % (self._addr,)
        )

    def __hash__(self):
        return id(self)

    def __bool__(self):
        fail("Cell 은 파이썬 if 에 쓸 수 없습니다 — 실행 중 판정은 EUDIf()(c) / EUDIf()(c == 값)")

    @property
    def addr(self):
        """값 칸의 주소 (ConstExpr 또는 정수)."""
        return self._addr

    @property
    def epd(self):
        """값 칸의 EPD (ConstExpr 또는 정수)."""
        return EPD(self._addr)

    # --- 대입·덧셈·뺄셈 ---
    def Assign(self, value):  # noqa: N802 — eudplib VariableBase 이름
        """c ← value. 상수 1 트리거, 변수 SeqCompute(호출 1 / 실행 2), 칸은 읽어서."""
        kind, val = _classify(value, "Cell <<")
        if val is self:
            return self
        if kind in (_K, _E):
            RawTrigger(actions=SetMemory(self._addr, SetTo, val))
            return self
        kind, val = _as_var(kind, val)
        SeqCompute([(self.epd, SetTo, val)])
        return self

    def __lshift__(self, value):
        return self.Assign(value)

    def assign(self, value):
        """c ← value (epScript 통로 — `c.assign(x);`). 반환: self"""
        return self.Assign(value)

    def __iadd__(self, value):
        kind, val = _classify(value, "Cell +=")
        if kind == _K:
            if val:
                RawTrigger(actions=SetMemory(self._addr, Add, val))
            return self
        if kind == _E:
            RawTrigger(actions=SetMemory(self._addr, Add, val))
            return self
        kind, val = _as_var(kind, val)  # c += c 도 읽은 값으로
        SeqCompute([(self.epd, Add, val)])
        return self

    def iadd(self, value):
        """c += value (wrap 덧셈, epScript 통로 `c.iadd(x);`). 반환: self"""
        return self.__iadd__(value)

    def __isub__(self, value):
        # VariableBase.__isub__(포화) 를 덮어쓴다 — Cell 의 연산자 뺄셈은 wrap (DESIGN 3.5-4)
        kind, val = _classify(value, "Cell -=")
        if val is not self:
            kind, val = _as_var(kind, val)
        _parts.isub32(self, val)
        return self

    def isub(self, value):
        """c −= value, **wrap**(한 바퀴 돎). epScript 통로 `c.isub(x);`. 같은 칸끼리는 0. 반환: self"""
        return self.__isub__(value)

    def isub_sat(self, value):
        """c ← max(c − value, 0), **포화**(0 에서 멈춤, SC Subtract). 값이 변수·칸이어도 된다. 반환: self

        인자: value(상수·주소식·EUDVariable·칸)
        비용: 상수 1 / 1, 변수 1 / 2 (칸은 읽기 비용 +)
        epScript: `c.isub_sat(x);`
        출처: DESIGN 3.5-2, `_parts.isub_sat32`
        """
        kind, val = _classify(value, "Cell.isub_sat")
        if val is not self:
            kind, val = _as_var(kind, val)
        _parts.isub_sat32(self, val)
        return self

    # --- 읽기 ---
    def read(self, ret=None):
        """값을 새 EUDVariable 로 읽는다(`f_dwread_epd`). 자주 읽는 값이면 EUDVariable 에 두는 편이 싸다.

        인자: ret([EUDVariable], 선택 — 그 변수에 받는다)
        반환: EUDVariable
        비용: eudplib f_dwread_epd (공유 본문 + 호출 2 / 실행 36~38, 2026-09-17)
        CP: 바꾸지 않음 (잠깐 옮기고 캐시로 되돌림)
        epScript: `var y = c.read();` · `var y = c.v;`
        """
        ret = _check_ret("Cell.read", ret)
        return f_dwread_epd(self.epd, ret=ret)

    @property
    def v(self):
        """epScript 통로: 읽으면 `read()`(트리거가 나온다), 쓰면 대입."""
        return self.read()

    @v.setter
    def v(self, value):
        self.Assign(value)

    # epScript `c.v op= x` (eudplib epscript/helper.py _ATTW)
    @staticmethod
    def _attr(name):
        if name != "v":
            raise AttributeError(name)

    def iaddattr(self, name, value):
        self._attr(name)
        self.__iadd__(value)

    def isubattr(self, name, value):
        self._attr(name)
        self.__isub__(value)  # wrap

    def isubtractattr(self, name, value):
        self._attr(name)
        self.isub_sat(value)  # 이름에 Subtract → 포화

    # --- 비교 ---
    def __eq__(self, other):
        return cmp.f_eq(self, other)

    def __ne__(self, other):
        return cmp.f_ne(self, other)

    def __le__(self, other):
        return cmp.f_le(self, other)

    def __lt__(self, other):
        return cmp.f_lt(self, other)

    def __ge__(self, other):
        return cmp.f_ge(self, other)

    def __gt__(self, other):
        return cmp.f_gt(self, other)

    # eudplib VariableBase.AtLeast 류는 비교값이 변수면 EUDNot 에서 틀리고(DESIGN 3.4), 상수라도
    # EUDNot(AtMost 0xFFFFFFFF) 가 AtLeast 2^32 로 넘쳐 늘 참이 된다(WP2 실측) → 모두 cmp 로 보낸다.
    def AtLeast(self, value):  # noqa: N802
        """[c ≥ value] (= `cmp.ge(c, value)`). 상수는 조건 하나(경계는 Always/Never 로 접음), 변수·칸은 부르는 자리에서 채운다."""
        return cmp.f_ge(self, value)

    def AtMost(self, value):  # noqa: N802
        """[c ≤ value] (= `cmp.le(c, value)`)."""
        return cmp.f_le(self, value)

    def Exactly(self, value):  # noqa: N802
        """[c = value] (= `cmp.eq(c, value)`)."""
        return cmp.f_eq(self, value)

    def eqattr(self, name, value):
        self._attr(name)
        return self == value

    def neattr(self, name, value):
        self._attr(name)
        return self != value

    def leattr(self, name, value):
        self._attr(name)
        return self <= value

    def ltattr(self, name, value):
        self._attr(name)
        return self < value

    def geattr(self, name, value):
        self._attr(name)
        return self >= value

    def gtattr(self, name, value):
        self._attr(name)
        return self > value


class Flag(EUDLightBool):
    """참/거짓 1비트 (`EUDLightBool` 그대로 — 32개가 4바이트 한 칸을 나눠 쓴다).

    인자: init(bool, 초기값)
    반환: -
    쓰기: 액션 `f.Set()`, `f.Clear()`, `f.Toggle()` (`DoActions(f.Set())`) / 조건 `f.IsSet()`, `f.IsCleared()`,
          `EUDIf()(f)`(= IsSet). 값이 아니므로 `Cell`·`cmp` 에 넣으면 오류.
    비용: 액션·조건 하나 (트리거 0 — 넣은 트리거 안에서)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const f = cell.Flag(); DoActions(f.Set()); if (f.IsSet()) { … }`
    출처: DESIGN 4.3 (CtrigAsm 참거짓 Ccode 대체), eudplib 0.81 `core/variable/eudlv.py` EUDLightBool
    """

    __slots__ = ()

    def __init__(self, init=False):
        if not isinstance(init, bool) and init not in (0, 1):
            fail("Flag: 초기값은 True/False 여야 합니다 (%r)", init)
        super().__init__(bool(init))

    def __repr__(self):
        return "<eudext.cell.Flag — 조건은 f.IsSet(), 액션은 f.Set()/f.Clear()>"


# ---------------------------------------------------------------------------------------------
# CellArray / PCell
# ---------------------------------------------------------------------------------------------


class CellArray(ExprProxy):
    """Cell 여러 개(칸당 4바이트, `EUDArray` 기반). CtrigAsm `CreateCcodeArr` 대체.

    인자: init — 개수(1 이상 정수, 모두 0) 또는 초기값 목록(정수·주소식 상수)
    반환: -
    - 상수 색인 `arr[k]` / `arr.cell(k)` = **Cell 뷰**(같은 k 는 같은 객체). Cell 의 모든 연산을 쓴다.
    - 변수 색인: `arr[i]`·`arr.get(i, ret=None)` 읽기(새 EUDVariable), `arr[i] = v`·`arr.set(i, v)`,
      `arr.iadditem(i, v)`(= `iadd`), `arr.isubitem(i, v)`(= `isub`, **wrap**), `arr.isub_sat(i, v)`(= `isubtractitem`, **포화**),
      비교 `arr.eqitem/neitem/leitem/ltitem/geitem/gtitem(i, v)`(= `eq/ne/le/lt/ge/gt`) — 상수 색인도 같은 메서드가 된다.
      **파이썬 `arr[i] << v`(변수 i)는 읽은 사본에 쓴다** → `arr[i] = v`. 파이썬 `arr[i] += v` 는 읽고-쓰기라 비싸다 → `iadditem`.
    - 변수 색인은 0 ~ n−1 이어야 한다(실행 중 검사 없음 — EUDArray 와 같다).
    - `arr.array`(EUDArray), `arr.epd`(칸 0 의 EPD), `arr.addr`(칸 0 의 주소), `len(arr)`, `for c in arr`(Cell 뷰).
    비용: 호출 자리 / 실행 (2026-09-17, docs/COSTS.md "cell (WP2)") — 상수 색인 = Cell 과 같음.
          변수 색인: 대입·덧셈·포화 뺄셈 값 상수 2 / 3·값 변수 1 / 3, wrap 뺄셈 값 상수 2 / 3·값 변수 3 / 7,
          읽기 = EUDArray 와 같음(호출 1~2 / 실행 약 37), 비교 준비 1 / 2(값 변수 1 / 3), `!=` 2 / 3(값 변수 2 / 4)
    CP: 바꾸지 않음 (읽기는 잠깐 옮기고 되돌림)
    로컬: 공유 안전
    epScript: `const arr = cell.CreateCcodeArr(15); arr[i] = 3; arr[i] -= 1; if (arr[i] == 0) { … } arr.isub_sat(i, x);`
    출처: CtrigAsm `CreateCcodeArr`(CtrigAsm v5.5.lua:75973), eudplib 0.81 `collections/eudarray.py`,
          eudext `units.UnitField`(WP10) 변수 색인 조건 패치 모양
    """

    __slots__ = ("_addr0", "_arr", "_epd0", "_n", "_views")
    dont_flatten = True

    def __init__(self, init):
        if isinstance(init, bool):
            fail("CellArray: 개수는 정수여야 합니다 (%r)", init)
        if isinstance(init, int):
            if init < 1:
                fail("CellArray: 개수는 1 이상이어야 합니다 (%d)", init)
            n = init
            arr = EUDArray(n)
        elif isinstance(init, (list, tuple)):
            vals = []
            for k, x in enumerate(init):
                kind, val = _classify(x, "CellArray", "초기값 %d" % k)
                if kind not in (_K, _E):
                    fail("CellArray: 초기값 %d 는 상수여야 합니다 (%r) — 변수는 만든 뒤 arr[%d] = v", k, x, k)
                vals.append(val)
            if not vals:
                fail("CellArray: 초기값 목록이 비었습니다")
            n = len(vals)
            arr = EUDArray(vals)
        else:
            fail("CellArray: 개수(정수) 또는 초기값 목록을 넣습니다 (%r)", init)
        super().__init__(arr)
        self._arr = arr
        self._n = n
        self._epd0 = _compat.eudarray_epd(arr)
        self._addr0 = _compat.eudarray_addr(arr)
        self._views = {}

    def __repr__(self):
        return "<eudext.cell.%s × %d>" % (type(self).__name__, self._n)

    __str__ = __repr__

    def __len__(self):
        return self._n

    def __iter__(self):
        return iter([self.cell(k) for k in range(self._n)])

    def __bool__(self):
        return True

    @property
    def length(self):
        return self._n

    @property
    def array(self):
        """밑에 있는 EUDArray (eudplib 함수에 넘길 때)."""
        return self._arr

    @property
    def epd(self):
        """칸 0 의 EPD (칸 k = epd + k)."""
        return self._epd0

    @property
    def addr(self):
        """칸 0 의 주소 (칸 k = addr + 4k)."""
        return self._addr0

    # --- 색인 ---
    def _index(self, i, fname):
        """정수(0 ~ n−1) 또는 EUDVariable."""
        i = unProxy(i)
        if isinstance(i, bool):
            i = int(i)
        if isinstance(i, int):
            if not 0 <= i < self._n:
                fail("%s: 색인 %d 가 범위(0~%d) 밖입니다", fname, i, self._n - 1)
            return i
        if _compat.is_var(i):
            return i
        fail("%s: 색인은 정수 상수 또는 EUDVariable 이어야 합니다 (%r)", fname, i)
        return None

    def cell(self, k):
        """상수 색인 k 의 Cell 뷰 (같은 k 는 같은 객체)."""
        k = self._index(k, "%s.cell" % type(self).__name__)
        if not isinstance(k, int):
            fail("%s.cell: 상수 색인만 됩니다 — 변수 색인은 get/set/iadditem/…item 을 씁니다", type(self).__name__)
        v = self._views.get(k)
        if v is None:
            v = Cell._view(self._addr0 + 4 * k)
            self._views[k] = v
        return v

    def __getitem__(self, i):
        i = self._index(i, "%s[]" % type(self).__name__)
        if isinstance(i, int):
            return self.cell(i)
        return self.get(i)

    def __setitem__(self, i, value):
        self.set(i, value)

    # --- 읽기·쓰기 ---
    def get(self, i, ret=None):
        """칸 i 의 값 → 새 EUDVariable (ret 를 주면 그 변수)."""
        fname = "%s.get" % type(self).__name__
        i = self._index(i, fname)
        ret = _check_ret(fname, ret)
        if isinstance(i, int):
            return self.cell(i).read(ret=ret)
        return f_dwread_epd(self._epd0 + i, ret=ret)

    def _val(self, fname, value):
        kind, val = _classify(value, fname)
        return _as_var(kind, val)

    def set(self, i, value):
        """칸 i ← value."""
        fname = "%s.set" % type(self).__name__
        i = self._index(i, fname)
        if isinstance(i, int):
            c = self.cell(i)
            if unProxy(value) is not c:  # 파이썬 `arr[k] += v` 가 뷰를 다시 넣는 경우
                c.Assign(value)
            return
        _kind, val = self._val(fname, value)
        self._arr.set(i, val)

    def iadditem(self, i, value):
        """칸 i += value (wrap 덧셈, epScript `arr[i] += v;`)."""
        fname = "%s.iadditem" % type(self).__name__
        i = self._index(i, fname)
        if isinstance(i, int):
            self.cell(i).__iadd__(value)
            return
        kind, val = self._val(fname, value)
        if kind == _K and val == 0:
            return
        self._arr.iadditem(i, val)

    def isubitem(self, i, value):
        """칸 i −= value, **wrap** (epScript `arr[i] -= v;`, DESIGN 3.5-1)."""
        fname = "%s.isubitem" % type(self).__name__
        i = self._index(i, fname)
        if isinstance(i, int):
            self.cell(i).__isub__(value)
            return
        kind, val = self._val(fname, value)
        if kind == _K:
            if val:
                self._arr.iadditem(i, (-val) & M32)
            return
        neg = EUDVariable()
        neg << 0
        _parts.isub32(neg, val)  # neg = −val (wrap). 마스크 Add 반전 기법(eudplib isubitem)은 쓰지 않는다
        self._arr.iadditem(i, neg)

    def isub_sat(self, i, value):
        """칸 i ← max(칸 i − value, 0), **포화** (SC Subtract, eudplib `isubtractitem` 과 같은 뜻)."""
        fname = "%s.isub_sat" % type(self).__name__
        i = self._index(i, fname)
        if isinstance(i, int):
            self.cell(i).isub_sat(value)
            return
        kind, val = self._val(fname, value)
        if kind == _K and val == 0:
            return
        self._arr.isubtractitem(i, val)

    iadd = iadditem
    isub = isubitem
    isubtractitem = isub_sat

    # --- 비교 ---
    def _cmp(self, op, i, value):
        fname = "%s.%s" % (type(self).__name__, op)
        i = self._index(i, fname)
        if isinstance(i, int):
            return getattr(cmp, "f_" + op)(self.cell(i), value)
        kind, val = self._val(fname, value)
        fill = _Fill()
        conds = _item_conds(fill, self._epd0, i, op, kind, val)
        fill.emit()
        return _ret(conds)

    def eq(self, i, value):
        """[칸 i = value]. 반환: Condition (변수 색인이면 부르는 자리에서 칸 번호를 채운다 — 꼭 한 번 쓴다)."""
        return self._cmp("eq", i, value)

    def ne(self, i, value):
        """[칸 i ≠ value]."""
        return self._cmp("ne", i, value)

    def le(self, i, value):
        """[칸 i ≤ value]."""
        return self._cmp("le", i, value)

    def lt(self, i, value):
        """[칸 i < value]."""
        return self._cmp("lt", i, value)

    def ge(self, i, value):
        """[칸 i ≥ value]."""
        return self._cmp("ge", i, value)

    def gt(self, i, value):
        """[칸 i > value]."""
        return self._cmp("gt", i, value)

    eqitem = eq
    neitem = ne
    leitem = le
    ltitem = lt
    geitem = ge
    gtitem = gt


def _item_conds(fill, epd0, i, op, kind, val):
    """[칸(epd0 + i) op val] 조건 목록 (i 는 변수). 칸 번호·비교값은 fill 이 채운다(amount 는 Forward 자리 표시)."""

    def rd(cmp_, amount):
        c = MemoryEPD(0, cmp_, amount)
        fill.set_sum(EPD(c) + 1, epd0, i)
        return c

    base = {"eq": Exactly, "ge": AtLeast, "le": AtMost}
    if kind == _K:
        k = val
        if op == "eq":
            return [rd(Exactly, k)]
        if op == "ge":
            return [Always()] if k == 0 else [rd(AtLeast, k)]
        if op == "le":
            return [Always()] if k == M32 else [rd(AtMost, k)]
        if op == "gt":
            return [Never()] if k == M32 else [rd(AtLeast, k + 1)]
        if op == "lt":
            return [Never()] if k == 0 else [rd(AtMost, k - 1)]
        if k == 0:
            return [rd(AtLeast, 1)]
        if k == M32:
            return [rd(AtMost, M32 - 1)]
        return [_flag_not(fill, rd(Exactly, k))]
    if kind == _E:
        if op in base:
            return [rd(base[op], val)]
        t = EUDVariable()
        t << val
        val = t
    if op in base:
        c = rd(base[op], _ph())
        fill.set_sum(EPD(c) + 2, 0, val)
        return [c]
    if op == "gt":
        c = rd(AtLeast, _ph())  # [칸 ≥ v+1] ∧ [v ≠ 0xFFFFFFFF]
        fill.set_sum(EPD(c) + 2, 1, val)
        return [c, val.AtMost(M32 - 1)]
    if op == "lt":
        c = rd(AtMost, _ph())  # [칸 ≤ v−1] ∧ [v ≠ 0]
        fill.set_sum(EPD(c) + 2, M32, val)
        return [c, val.AtLeast(1)]
    c = rd(Exactly, _ph())
    fill.set_sum(EPD(c) + 2, 0, val)
    return [_flag_not(fill, c)]


class PCell(CellArray):
    """플레이어별 Cell (기본 8칸). CtrigAsm 에서 플레이어마다 따로 두던 Ccode(플레이어 사본) 대체.

    인자: init(정수·주소식 상수 하나 = 모든 칸, 또는 count 개 목록), count(1~12, 기본 8)
    반환: -
    색인: `P1`~`P12`·`0`~`count−1`(상수 → Cell 뷰), `CurrentPlayer`(실행 중 CP — `f_getcurpl()`), EUDVariable.
          `pc[P1] << 3`, `pc[CurrentPlayer] = 3`, `pc.iadditem(CurrentPlayer, 1)`, `pc.isub_sat(p, v)`, `pc.eqitem(p, 0)`.
          나머지는 `CellArray` 와 같다. `AllPlayers`·`Force1` 같은 묶음은 받지 않는다(`players.run_as`/`each` 로 돈다).
    비용: CellArray 와 같음. `CurrentPlayer` 색인은 `f_getcurpl()`(캐시 확인 + 사본, 호출 +1 / 실행 +7)이 더해진다 (2026-09-17)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const kills = cell.PCell(); kills[CurrentPlayer] += 1; if (kills[P1] >= 10) { … }`
    출처: CtrigAsm Ccode 플레이어 사본(`CDeaths(Player, …)` 의 Player 자리), DESIGN 4.3
    """

    __slots__ = ()

    def __init__(self, init=0, count=8):
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_PLAYERS:
            fail("PCell: count 는 1~%d 정수여야 합니다 (%r)", MAX_PLAYERS, count)
        if isinstance(init, (list, tuple)):
            if len(init) != count:
                fail("PCell: 초기값 목록 길이 %d 가 count %d 와 다릅니다", len(init), count)
            vals = list(init)
        else:
            vals = [init] * count
        super().__init__(vals)

    def _index(self, p, fname):
        pu = unProxy(p)
        if isinstance(pu, bool):
            fail("%s: 플레이어 번호에 bool 은 넣을 수 없습니다", fname)
        if _compat.is_var(pu):
            return pu
        try:
            e = unProxy(EncodePlayer(p))
        except Exception:  # noqa: BLE001 — eudplib 의 여러 오류를 한국어 안내로
            e = None
        if isinstance(e, int) and not isinstance(e, bool):
            if e == 13:  # CurrentPlayer — f_getcurpl() 은 캐시를 확인하고 사본 변수를 돌려준다
                return f_getcurpl()
            if 0 <= e < self._n:
                return e
            fail("%s: 플레이어 %r(번호 %d)는 이 PCell(%d칸)에 없습니다 (묶음 대상은 players.each 로 돈다)",
                 fname, p, e, self._n)
        if _compat.is_var(e):
            return e
        fail("%s: 플레이어는 P1~·0~%d·CurrentPlayer·EUDVariable 이어야 합니다 (%r)", fname, self._n - 1, p)
        return None


# ---------------------------------------------------------------------------------------------
# 만들기 (CtrigAsm 이름)
# ---------------------------------------------------------------------------------------------


def CreateCcode(init=0):  # noqa: N802 — CtrigAsm 이름
    """Cell 하나 (= `Cell(init)`). CtrigAsm `CreateCcode()` 대체.

    인자: init(초기값, 기본 0)
    반환: Cell
    비용: 4바이트, 트리거 0 (상수 초기값)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const c = cell.CreateCcode();`
    출처: CtrigAsm v5.5.lua:75959 CreateCcode
    """
    return Cell(init)


def CreateCcodes(n, init=0):  # noqa: N802
    """Cell n 개. n = 1 이면 Cell 하나, 아니면 목록(`a, b = CreateCcodes(2)`).

    인자: n(1 이상), init(모두의 초기값)
    반환: Cell 또는 Cell 목록
    비용: 4바이트 × n, 트리거 0
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const a, b = cell.CreateCcodes(2);`
    출처: CtrigAsm v5.5.lua:75964 CreateCcodes (Lua `table.unpack` 과 같게 여러 값)
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        fail("CreateCcodes: 개수는 1 이상 정수여야 합니다 (%r)", n)
    return List2Assignable([Cell(init) for _ in range(n)])


def CreateCcodeArr(n):  # noqa: N802
    """CellArray (= `CellArray(n)`). 상수 색인은 Cell 뷰, 변수 색인은 읽기·쓰기 함수.

    인자: n(개수) 또는 초기값 목록
    반환: CellArray
    비용: 4바이트 × n, 트리거 0
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const arr = cell.CreateCcodeArr(15);`
    출처: CtrigAsm v5.5.lua:75973 CreateCcodeArr
    """
    return CellArray(n)


# ---------------------------------------------------------------------------------------------
# CD / SetCD 계열 (LibraryFor322.lua, 원래 의미)
# ---------------------------------------------------------------------------------------------


def _code(x, fname):
    if isinstance(x, CellArray):  # ExprProxy 라 unProxy 하기 전에 본다
        fail("%s: CellArray 가 아니라 칸(arr[k])을 넣습니다", fname)
    x = unProxy(x)
    if not _compat.is_varbase(x):
        fail("%s: Ccode 자리에는 Cell·EUDLightVariable·EUDVariable 을 넣습니다 (%r)", fname, x)
    return x


def _cmp_name(t, fname):
    # TrgComparison 은 ExprProxy 라 unProxy 하면 정수가 된다 → 형식을 먼저 본다
    if isinstance(t, (TrgComparison, str)):
        try:
            code = EncodeComparison(t)
        except Exception:  # noqa: BLE001
            code = None
        if code in _CMP_OP:
            return _CMP_OP[code]
    fail("%s: 비교는 AtLeast·AtMost·Exactly 여야 합니다 (%r)", fname, t)
    return None


def f_cd(code, value=1, type=_UNSET):  # noqa: A002 — CtrigAsm 인자 이름
    """[code 비교 value] 조건. CtrigAsm `CD(Code, Value, Type)` 와 같은 인자 순서(기본 value=1, Exactly).

    `CD(c, AtLeast, 3)` 처럼 비교를 둘째 자리에 둬도 된다. 값이 변수·칸이면 `cmp` 로 조건 칸을 채운다(부르는 자리).
    인자: code(Cell·EUDLightVariable·EUDVariable·CellArray 원소), value(상수·주소식·변수·칸), type(AtLeast/AtMost/Exactly)
    반환: Condition 또는 조건 목록 (`cmp.ge/le/eq` 와 같음 — 꼭 한 번 트리거에 넣는다)
    비용: 상수 0 / 0, 변수 1 / 2 (cmp 와 같음)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cell.CD(c, 3, AtLeast)) { … }` · `if (cell.cd(c, 0)) { … }`
    출처: LibraryFor322.lua:740 CD (CDeaths / TCDeaths)
    """
    if isinstance(value, TrgComparison):
        value, type = (1 if type is _UNSET else type), value
    if type is _UNSET:
        type = Exactly
    code = _code(code, "CD")
    op = _cmp_name(type, "CD")
    return getattr(cmp, "f_" + op)(code, value)


def f_cdx(code, value, mask, type=_UNSET):  # noqa: A002
    """[(code & mask) 비교 value] 조건. CtrigAsm `CDX(Code, Value, Mask, Type)`.

    마스크 비교(EUDX 조건)는 SC 에서 확실한 동작이다(S8 3절). mask 는 정수 상수만.
    값이 변수면 amount 칸을 부르는 자리에서 채운다(`Forward` 자리 표시 — `EUDNot` 도 맞음).
    인자: code, value(상수·변수·칸), mask(정수 상수), type(AtLeast/AtMost/Exactly, 기본 Exactly)
    반환: Condition (늘 참·거짓인 상수 조합은 Always/Never 로 접는다)
    비용: 상수 0 / 0, 변수 1 / 2
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (cell.CDX(c, 0x10, 0xF0)) { … }`
    출처: LibraryFor322.lua:750 CDX (CDeathsX / TCDeathsX)
    """
    if isinstance(value, TrgComparison):
        fail("CDX: 인자 순서는 CDX(c, 값, 마스크, 비교) 입니다")
    if type is _UNSET:
        type = Exactly
    code = _code(code, "CDX")
    op = _cmp_name(type, "CDX")
    m = unProxy(mask)
    if isinstance(m, bool) or not isinstance(m, int):
        fail("CDX: 마스크는 정수 상수여야 합니다 (%r)", mask)
    m &= M32
    kind, val = _classify(value, "CDX")
    cmp_ = {"ge": AtLeast, "le": AtMost, "eq": Exactly}[op]
    if kind == _K:
        # (x & m) ∈ [0, m] — 늘 참/거짓을 접는다 (eudplib 부정이 AtMost 0xFFFFFFFF 를 넘기지 않게)
        if op == "ge" and val == 0 or op == "le" and val >= m:
            return Always()
        if op == "ge" and val > m or op == "eq" and val & ~m & M32:
            return Never()
        return MemoryX(code.getValueAddr(), cmp_, val, m)
    if kind == _E:
        return MemoryX(code.getValueAddr(), cmp_, val, m)
    kind, val = _as_var(kind, val)
    c = MemoryX(code.getValueAddr(), cmp_, _ph(), m)
    SeqCompute([(EPD(c) + 2, SetTo, val)])
    return c


def _mod_args(fname, a, b, default_mod):
    """(수정자, 값) — `f(c, 값)` 또는 `f(c, 수정자, 값)`."""
    if isinstance(a, TrgModifier):  # ExprProxy 라 unProxy 하기 전에 본다
        if EncodeModifier(a) not in (7, 8, 9):
            fail("%s: 수정자는 SetTo·Add·Subtract 여야 합니다 (%r)", fname, a)
        return a, (1 if b is _UNSET else b)
    if b is not _UNSET:
        fail("%s: 인자는 (c, 값) 또는 (c, SetTo/Add/Subtract, 값) 입니다 (%r, %r)", fname, a, b)
    return default_mod, a


def _cd_act(fname, code, mod, value, mask=None):
    code = _code(code, fname)
    kind, val = _classify(value, fname)
    kind, val = _as_var(kind, val)  # 칸 값은 부르는 자리에서 읽는다 (액션은 변수 필드면 DoActions/Trigger 가 채운다)
    if mask is None:
        return SetMemory(code.getValueAddr(), mod, val)
    mu = unProxy(mask)
    if isinstance(mu, bool) or not (isinstance(mu, int) or _compat.is_var(mu)):
        fail("%s: 마스크는 정수 상수 또는 EUDVariable 이어야 합니다 (%r)", fname, mask)
    if isinstance(mu, int):
        mu &= M32
    return SetMemoryX(code.getValueAddr(), mod, val, mu)


def f_set_cd(code, value=1, value2=_UNSET):
    """code ← value 액션. CtrigAsm `SetCD(Code, Value)`(기본 1). `SetCD(c, SetTo/Add/Subtract, v)` 도 받는다.

    값이 변수면 액션에 변수 필드가 생긴다 → `DoActions`/`Trigger` 안에서만(RawTrigger 는 상수만). 칸 값은 부르는 자리에서 읽는다.
    수정자 `Subtract` 는 SC 포화 뺄셈이다(이름 규칙, 3.5-3).
    인자: code, value(또는 수정자), value2(수정자를 줬을 때 값)
    반환: Action
    비용: 액션 하나 (넣은 트리거 안, 변수 값이면 DoActions 가 채우기 트리거 1 을 더한다)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `DoActions(cell.SetCD(c, 5));` · `DoActions(cell.SetCD(c, Add, x));`
    출처: LibraryFor322.lua:606 SetCD (SetCDeaths / TSetCDeaths)
    """
    mod, val = _mod_args("SetCD", value, value2, SetTo)
    return _cd_act("SetCD", code, mod, val)


def f_add_cd(code, value=1):
    """code += value 액션 (wrap 덧셈 — 음수 상수는 wrap 뺄셈). CtrigAsm `AddCD(Code, Value)`.

    인자: code, value(상수·변수·칸, 기본 1)
    반환: Action
    비용: 액션 하나
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `DoActions(cell.AddCD(c, 1));`
    출처: LibraryFor322.lua:586 AddCD
    """
    return _cd_act("AddCD", code, Add, value)


def f_subtract_cd(code, value=1):
    """code ← max(code − value, 0) 액션, **포화**(SC Subtract). CtrigAsm `SubCD(Code, Value)` — 원래 의미.

    wrap 뺄셈은 `c -= v` / `c.isub(v)` / `AddCD(c, -k)`.
    인자: code, value(상수·변수·칸, 기본 1)
    반환: Action
    비용: 액션 하나
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `DoActions(cell.SubCD(c, 1));` · `DoActions(cell.subtract_cd(c, x));`
    출처: LibraryFor322.lua:596 SubCD (DESIGN 3.5-5)
    """
    return _cd_act("SubCD", code, Subtract, value)


def f_set_cdx(code, value, mask):
    """code ← (code & ~mask) | (value & mask) 액션. CtrigAsm `SetCDX(Code, Value, Mask)`.

    마스크 SetTo 는 SC 에서 확실한 동작이다(S8 3절). 마스크 Add·Subtract 는 인게임 확인 전이라 두지 않는다(3.5-8).
    인자: code, value(상수·변수·칸), mask(정수 상수 또는 EUDVariable)
    반환: Action
    비용: 액션 하나
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `DoActions(cell.SetCDX(c, 0x30, 0xF0));`
    출처: LibraryFor322.lua:616 SetCDX
    """
    return _cd_act("SetCDX", code, SetTo, value, mask)


# 파이썬 별칭 (DESIGN 3.1)
cd = f_cd
cdx = f_cdx
set_cd = f_set_cd
set_cdx = f_set_cdx
add_cd = f_add_cd
subtract_cd = f_subtract_cd

# CtrigAsm 별칭 (원래 의미 — SubCD 는 포화)
CD = f_cd
CDX = f_cdx
SetCD = f_set_cd
SetCDX = f_set_cdx
AddCD = f_add_cd
SubCD = f_subtract_cd

