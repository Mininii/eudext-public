"""eudext 내부 부품: 분기·1회 분기·마스크 쓰기·상수 AND·32비트 뺄셈·CP 캐시 보정·서브루틴·조건 칸 채우기 묶음·
자기 수정 갈림 트리거 틀·변수 트리거 사슬·결정 나무 (DESIGN 4.1, 3.4, 3.5).

DPS 이식 계층(`ScmDraft 2\\DPS_eud\\eud\\ctrig`, eudplib 0.76.14 용)에서 복사해 eudplib 0.81 에 맞췄다.
라이브러리 모듈이 쓰는 부품이다. 맵 코드는 eudplib 제어문(EUDIf 등)을 쓰면 된다.

0.81 에서 달라진 점과 이 파일의 처리:
- `EUDBranch(_actions=…)` 는 여전히 액션의 변수 필드를 패치하지 않는다(`trigger/branch.py:_branch_sub`).
  → 변수 필드가 있는 액션은 분기 뒤 따로 싣는다(DPS 방식 유지).
- 0.81 은 `SetNextTrigger(target)` 로 앞 트리거의 next 를 바로 고쳐 점프 트리거를 아낀다(EUDJump 와 같음).
  → 분기 꼬리의 `RawTrigger(nextptr=…)` 를 `SetNextTrigger` 로 바꿨다(트리거 1개, 실행 1회 절약).
- 변수 마스크 칸이 공개 API(`getMaskAddr`, `SetMask`)가 됐다. `a & 상수` 도 실행 3회로 같다
  → `and_const` 는 eudplib 연산을 감싸기만 한다(측정: docs/COSTS.md).
- CP 캐시(`core/curpl.py`)는 `_compat` 경유.

모든 함수는 호출한 자리에 트리거를 낸다(EUDFunc 아님). 파이썬에서 쓰는 이름이 기본이고,
epScript 에서 부를 수 있는 값 함수 두 개(`and_const`, `set_masked`)만 `f_` 별칭을 둔다.

조건 칸 채우기 묶음(`Plan`, `selfcond`, `placeholder`, `flag_cond`)은 WP3(2026-09-17)에서 `cmp` 로부터 옮겼다.
`cmp`(32비트 비교)와 `i64`(64비트 비교)가 같이 쓴다. 조건 칸을 실행 중에 채우는 규칙은 DESIGN 3.4.

자기 수정 갈림 트리거 틀(`SelfFrame`)·변수 트리거 사슬(`var_chain`, `add_modifiers`)·결정 나무(`DNode`, `DLeaf`, `dtree`,
`emit_dtree`, `dspine`, `dpresets`, `dlabel`, `dgoto`)는 WP4(2026-09-17)에서 더했다 — `i64` 곱셈·나눗셈·시프트 본문이 쓴다
(DPS 이식판 a7aad90 `war.py` 결정 나무를 옮김).
"""

import contextlib

from eudplib import (
    Action,
    Add,
    AtLeast,
    EUDBranch,
    EUDVariable,
    Forward,
    MemoryEPD,
    NextTrigger,
    RawTrigger,
    SeqCompute,
    SetMemory,
    SetMemoryX,
    SetNextPtr,
    SetNextTrigger,
    SetTo,
    Subtract,
    Trigger,
    f_setcurpl,
    unProxy,
)
from eudplib import EPD as _EPD

from eudext import _compat
from eudext.errors import fail

M32 = 0xFFFFFFFF
CP_ADDR = 0x6509B0
EPD_CP = 203155  # EPD(0x6509B0)
FLAGS_OFFSET = 2376  # 트리거 주소 + 8 + 320 + 2048 = 플래그 dword
FLAG_DISABLED = 8

__all__ = [
    "DLeaf",
    "DNode",
    "M32",
    "Plan",
    "SelfFrame",
    "SubLabel",
    "add_modifiers",
    "all_const",
    "and_const",
    "branch",
    "call_sub",
    "cp_fix",
    "dgoto",
    "dlabel",
    "dpresets",
    "dspine",
    "dtree",
    "emit_dtree",
    "f_and_const",
    "f_set_masked",
    "flag_cond",
    "has_var_fields",
    "isub32",
    "isub_sat32",
    "jump_if",
    "jump_if_not",
    "once_branch",
    "placeholder",
    "selfcond",
    "set_masked",
    "var_chain",
    "write_addr",
]


def _flat(items):
    if items is None:
        return []
    if isinstance(items, (list, tuple)):
        out = []
        for x in items:
            out.extend(_flat(x))
        return out
    return [items]


def has_var_fields(obj):
    """조건·액션 객체의 필드에 EUDVariable 이 있는가.

    인자: obj(Condition 또는 Action)
    반환: bool
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS_eud ctrig/core.py:849 has_var_fields
    """
    return any(_compat.is_var(f) for f in obj.fields)


def all_const(items):
    """목록의 모든 조건·액션이 상수 필드만 가지는가(패치 없이 RawTrigger 에 넣을 수 있는가).

    인자: items(Condition/Action 목록, 중첩 가능)
    반환: bool
    비용: 없음
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: DPS_eud ctrig/core.py:853 all_const
    """
    return not any(has_var_fields(x) for x in _flat(items))


def _jump(target):
    # 0.81: 앞 트리거의 next 를 바로 고친다(EUDJump 와 같은 방식). 이어지는 트리거가 없으면 할 일도 없다.
    SetNextTrigger(target)


# ---------------------------------------------------------------------------------------------
# 분기
# ---------------------------------------------------------------------------------------------


def branch(conds, ontrue, onfalse, acts=None):
    """조건이 모두 참이면 acts 를 실행하고 ontrue 로, 하나라도 거짓이면 onfalse 로 간다.

    `EUDBranch(_actions=…)` 는 액션의 변수 필드를 패치하지 않으므로, 변수 필드가 있으면 참 경로에 따로 싣는다.
    인자: conds(조건·조건 목록·EUDVariable, 비면 무조건 참), ontrue/onfalse(트리거 주소식·Forward),
          acts(액션 목록, 선택)
    반환: None
    비용: 조건 16개 이하·상수 액션 = 호출 자리 2 / 실행 1(거짓)~2(참). 변수 액션 = 호출 4 / 실행 1~5 (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음(acts 가 바꾸면 그대로)
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_eud ctrig/core.py:872 branch (꼬리 점프를 SetNextTrigger 로)
    """
    acts = _flat(acts)
    if all_const(acts):
        EUDBranch(conds, ontrue, onfalse, _actions=acts or None)
        return
    tpath = Forward()
    EUDBranch(conds, tpath, onfalse)
    tpath << NextTrigger()
    Trigger(actions=acts)
    _jump(ontrue)


def jump_if(conds, target, acts=None):
    """조건이 참이면 acts 를 실행하고 target 으로 간다. 거짓이면 다음 트리거로.

    인자: conds, target, acts — `branch` 와 같음
    반환: None
    비용: `branch` 와 같음 (상수 액션 = 호출 2 / 실행 1~2)
    CP: 바꾸지 않음(acts 가 바꾸면 그대로)
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_eud ctrig/core.py:885 jump_if
    """
    onfalse = Forward()
    branch(conds, target, onfalse, acts)
    onfalse << NextTrigger()


def jump_if_not(conds, target, acts=None):
    """조건이 거짓이면 target 으로 간다. 참이면 acts 를 실행하고 다음 트리거로.

    인자: conds, target, acts — `branch` 와 같음
    반환: None
    비용: 상수 액션 = 호출 2 / 실행 1~2. 변수 액션 = 호출 4 / 실행 1~5 (docs/COSTS.md)
    CP: 바꾸지 않음(acts 가 바꾸면 그대로)
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_eud ctrig/core.py:891 jump_if_not
    """
    acts = _flat(acts)
    ontrue = Forward()
    if all_const(acts):
        EUDBranch(conds, ontrue, target, _actions=acts or None)
        ontrue << NextTrigger()
        return
    EUDBranch(conds, ontrue, target)
    ontrue << NextTrigger()
    Trigger(actions=acts)


def once_branch(conds, ontrue, onfalse, acts=None):
    """게임당 한 번: 조건이 처음 참인 사이클에 acts 를 실행하고 ontrue 로. 그 뒤로는 늘 onfalse 로.

    머리 트리거를 끄고(플래그 8) next 를 onfalse 로 고친다. 조건이 비면 첫 사이클에 바로 실행한다.
    조건 없는 머리가 자기 next 를 고치면 엔진이 곧바로 그 값을 따라가므로, 이 경우 다음 트리거에서 고친다.
    인자: conds(비어도 됨), ontrue, onfalse, acts(선택)
    반환: None
    비용: 조건 있음·상수 액션 = 호출 2 / 실행 2(첫 참) 1(그 밖). 조건 없음 = 호출 2 / 실행 2(첫 사이클) → 1
    CP: 바꾸지 않음(acts 가 바꾸면 그대로)
    로컬: 공유 안전. 머리 트리거 상태가 곧 기억이므로 로컬 조건과 섞으면 디싱크 (DESIGN 3.7)
    epScript: 쓰지 않는다 (epScript 는 `once (cond) { }`)
    출처: DPS_eud ctrig/core.py:913 once_branch
    """
    head = Forward()
    head << NextTrigger()
    once = [SetNextPtr(head, onfalse), SetMemory(head + FLAGS_OFFSET, SetTo, FLAG_DISABLED)]
    acts = _flat(acts)
    conds = _flat(conds)
    if not conds:
        tpath = Forward()
        RawTrigger(nextptr=tpath)  # 머리는 실제 트리거여야 한다 (SetNextTrigger 로 줄이면 안 됨)
        tpath << NextTrigger()
        if all_const(acts):
            RawTrigger(nextptr=ontrue, actions=[*acts, *once])
            return
        Trigger(actions=acts)
        RawTrigger(nextptr=ontrue, actions=once)
        return
    if all_const(acts):
        EUDBranch(conds, ontrue, onfalse, _actions=acts + once)
        return
    tpath = Forward()
    EUDBranch(conds, tpath, onfalse, _actions=once)
    tpath << NextTrigger()
    Trigger(actions=acts)
    _jump(ontrue)


# ---------------------------------------------------------------------------------------------
# 마스크 쓰기
# ---------------------------------------------------------------------------------------------


def write_addr(addr, val, mask=M32):
    """주소 칸 ← (칸 & ~mask) | (val & mask). 값·마스크가 변수여도 SetMemoryX 1액션(패치 포함).

    0x6509B0(CP) 은 전체 쓰기만 되고 `f_setcurpl` 로 캐시까지 고친다. CP 마스크 쓰기는 오류.
    인자: addr(주소 상수·주소식, 4의 배수), val(상수·변수), mask(상수·변수)
    반환: None
    비용: docs/COSTS.md `_parts` 표 (상수 = 트리거 1 / 실행 1, 변수가 끼면 패치 트리거가 붙는다)
    CP: addr 가 CP 일 때만 바꿈(f_setcurpl)
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_eud ctrig/core.py:521 write_addr
    """
    mvar = _compat.is_var(mask)
    vvar = _compat.is_var(val)
    if not mvar:
        mask &= M32
    if not vvar and isinstance(val, int):
        val &= M32
    if isinstance(addr, int) and addr & ~3 == CP_ADDR:
        if mvar or mask != M32:
            fail("CP(0x6509B0) 마스크 쓰기는 지원하지 않습니다")
        f_setcurpl(val)
        return
    if not mvar and mask == M32:
        if vvar:
            SeqCompute([(_EPD(addr), SetTo, val)])
            return
        RawTrigger(actions=SetMemory(addr, SetTo, val))
        return
    act = SetMemoryX(addr, SetTo, val, mask)
    if vvar or mvar:
        Trigger(actions=act)
    else:
        RawTrigger(actions=act)


def set_masked(dst, val, mask=M32):
    """변수 dst ← (dst & ~mask) | (val & mask). 값·마스크가 변수여도 된다.

    마스크가 전체(0xFFFFFFFF 상수)면 `dst << val` 과 같다.
    인자: dst(EUDVariable), val(상수·변수), mask(상수·변수)
    반환: None
    비용: `write_addr` 와 같음 (docs/COSTS.md `_parts` 표)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `parts.set_masked(v, x, 0xFF00);` (→ `f_set_masked`)
    출처: DPS_eud ctrig/core.py:509 set_masked
    """
    if not isinstance(dst, EUDVariable):
        fail("set_masked: dst 는 EUDVariable 이어야 합니다 (%r)", dst)
    if not _compat.is_var(mask):
        mask &= M32
        if mask == M32:
            if val is dst:
                return
            dst << val
            return
    write_addr(dst.getValueAddr(), val, mask)


f_set_masked = set_masked


def and_const(v, m):
    """v & m (m 은 상수)을 새 임시 변수로 돌려준다. v 는 바꾸지 않는다.

    eudplib 0.81 의 `v & 상수`(복사 1회 + SetMemoryX 1액션)를 감싼다. DPS 판(변수 트리거 마스크 칸을
    잠시 m 으로 두는 방법)과 실행 수가 같고(3회) v 의 트리거를 건드리지 않는다(docs/COSTS.md).
    인자: v(EUDVariable 또는 상수), m(정수 상수)
    반환: 새 EUDVariable (v 가 상수면 파이썬 int)
    비용: 호출 자리 트리거 2 / 실행 3 (2026-09-17)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const low = parts.and_const(x, 0xFF);` (→ `f_and_const`)
    출처: DPS_eud ctrig/arith.py:51 and_const (0.81 판은 eudplib `EUDVariable.__and__` 감싸기)
    """
    if _compat.is_var(m) or not isinstance(m, int):
        fail("and_const: 마스크는 정수 상수여야 합니다 (%r)", m)
    m &= M32
    if not _compat.is_var(v):
        if isinstance(v, int):
            return v & m
        fail("and_const: 값은 EUDVariable 또는 정수여야 합니다 (%r)", v)
    if m == M32:
        t = EUDVariable()
        t << v
        return t
    return v & m


f_and_const = and_const


# ---------------------------------------------------------------------------------------------
# 32비트 뺄셈 (DESIGN 3.5 규칙 6, docs/spec/S8_subtract.md 1절·6.4·7.1)
# ---------------------------------------------------------------------------------------------


def _check_dest(fname, a):
    if not _compat.is_varbase(a):
        fail("%s: 대상은 EUDVariable/EUDLightVariable 이어야 합니다 (%r)", fname, a)


def isub32(a, b):
    """a ← a − b (32비트 **wrap**, 한 바퀴 돎). a 를 제자리에서 고치고 a 를 돌려준다.

    eudext 내부의 32비트 뺄셈은 모두 이 함수를 거친다(DESIGN 3.5-6).
    - `b is a`: eudplib `v -= v` 는 0 이 아니라 0xFFFFFFFF 가 된다(`__isub__` 가 `self += 1` 을 먼저 하고
      `~other` 를 더함, 0.76.14·0.81.0 공통, S8 1-3) → `a << 0` 으로 바꾼다.
    - b 가 정수 상수: `Add(-b)` 액션 1개(b == 0 이면 트리거 없음).
    - a 가 EUDVariable: 그 밖은 eudplib `a -= b`.
    - a 가 EUDLightVariable 등(eudplib `-=` 가 **포화**인 타입): 임시 변수에 `~b + 1` 을 만들어 더한다.
    인자: a(EUDVariable 또는 VariableBase), b(상수·ConstExpr·변수)
    반환: a
    비용: 상수 = 호출 1 / 실행 1. 변수(EUDVariable a) = 호출 1 / 실행 3 (eudplib `-=`). 같은 객체 = 1 / 1.
          EUDLightVariable a + 변수 b = 호출 3 / 실행 5. (2026-09-17, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다 (epScript 는 `a -= b;` — 같은 변수끼리는 `a = 0;`)
    출처: S8_subtract.md 7.1-6, eudplib 0.81 `core/variable/eudv.py:__isub__`
    """
    _check_dest("isub32", a)
    bu = unProxy(b)
    if bu is a:
        _assign0(a)
        return a
    if isinstance(bu, bool):
        bu = int(bu)
    if isinstance(bu, int):
        k = bu & M32
        if k:
            RawTrigger(actions=a.AddNumber((-k) & M32))
        return a
    if isinstance(a, EUDVariable):
        a -= bu
        return a
    t = EUDVariable()
    SeqCompute([(t, SetTo, M32), (t, Subtract, bu), (t, Add, 1)])
    SeqCompute([(_EPD(a.getValueAddr()), Add, t)])
    return a


def isub_sat32(a, b):
    """a ← max(a − b, 0) (32비트 **포화**, 0 에서 멈춤). a 를 제자리에서 고치고 a 를 돌려준다.

    SC `Subtract` 액션을 쓴다(eudplib 이름 규칙: `Subtract` = 포화). `b is a` 면 `a << 0`.
    인자: a(EUDVariable 또는 VariableBase), b(상수·ConstExpr·변수)
    반환: a
    비용: 상수 = 호출 1 / 실행 1. 변수 = 호출 1 / 실행 2 (SeqCompute). (docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다 (공개 판은 WP1/WP2 의 `isub_sat`)
    출처: S8_subtract.md 6.4-5, 7.1-2
    """
    _check_dest("isub_sat32", a)
    bu = unProxy(b)
    if bu is a:
        _assign0(a)
        return a
    if isinstance(bu, bool):
        bu = int(bu)
    if isinstance(bu, int):
        k = bu & M32
        if k:
            RawTrigger(actions=a.SubtractNumber(k))
        return a
    SeqCompute([(_EPD(a.getValueAddr()), Subtract, bu)])
    return a


def _assign0(a):
    RawTrigger(actions=a.SetNumber(0))


# ---------------------------------------------------------------------------------------------
# CP 캐시 보정
# ---------------------------------------------------------------------------------------------


def cp_fix(acts):
    """CP(0x6509B0)에 쓰는 원시 액션 앞에 eudplib CP 캐시 두 칸을 같은 연산으로 고치는 액션을 붙인다.

    eudplib 의 읽기 함수(`f_dwread_epd` 등)는 끝에서 검사 없이 CP 를 캐시 값으로 되돌린다
    (`f_setcurpl2cpcache`). 사용자가 넘긴 원시 액션 목록을 받는 헬퍼는 이 함수를 거쳐 캐시를 맞춘다(DESIGN 3.6).
    CP 쓰기 1개당 액션이 2개 는다. 마스크 CP 쓰기는 오류.
    인자: acts(Action 목록, 중첩 가능)
    반환: 새 목록(바꿀 것이 없으면 평평하게 편 원래 목록)
    비용: CP 쓰기 1개당 액션 +2
    CP: 액션이 바꾸는 대로(캐시가 따라감)
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_eud ctrig/core.py:761 cp_fix
    """
    acts = _flat(acts)
    out = None
    for i, a in enumerate(acts):
        if not isinstance(a, Action):
            fail("cp_fix: 액션이 아닌 항목 %r", a)
        f = a.fields
        if f[7] == 45 and isinstance(f[4], int) and f[4] == EPD_CP and f[6] == 0:
            if out is None:
                out = list(acts[:i])
            if f[11] == 0x4353 and not (isinstance(f[0], int) and f[0] & M32 == M32):
                fail("CP(0x6509B0) 마스크 쓰기는 지원하지 않습니다")
            cache = _compat.cpcache_var()
            cond = _compat.cpcache_cond()
            mod, val = f[8], f[5]
            out.append(Action(0, 0, 0, 0, _EPD(cache.getValueAddr()), val, 0, 45, mod, 20))
            out.append(Action(0, 0, 0, 0, _EPD(cond + 8), val, 0, 45, mod, 20))
        if out is not None:
            out.append(a)
    return acts if out is None else out


# ---------------------------------------------------------------------------------------------
# 서브루틴 (인자 없는 트램펄린)
# ---------------------------------------------------------------------------------------------


class SubLabel:
    """인자 없는 서브루틴. 본문은 따로 떨어진 트리거 영역에 두고 `call_sub` 로 부른다.

    돌아올 곳은 끝 트리거의 next 칸 하나뿐이다 → **재진입·재귀 금지**(본문 안에서 자기를 다시 부르면 무한 루프).
    본문 정의(`with sub.define():`)는 호출보다 앞이든 뒤든 된다. 정의하지 않고 부르면 빌드 때 Forward 오류.

    인자: name(표시용, 선택)
    반환: -
    비용: 본문 = 본문 트리거 + 끝 1 / 호출 자리 1 (조건 없을 때) / 실행 = 본문 + 2
    CP: 본문이 바꾸는 대로
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_eud ctrig/trig.py:256 _emit_call, 26 _call (SetCall/SetCallEnd)
    """

    __slots__ = ("_defined", "entry", "name", "ret")

    def __init__(self, name=None):
        self.name = name
        self.entry = Forward()
        self.ret = Forward()
        self._defined = False

    def __repr__(self):
        return "<SubLabel %s>" % (self.name or hex(id(self)))

    @contextlib.contextmanager
    def define(self):
        """본문을 정의한다: `with sub.define(): …` (바깥 흐름과 떨어진 영역에 놓인다)."""
        if self._defined:
            fail("SubLabel %s: 본문을 두 번 정의했습니다", self.name)
        self._defined = True
        with _compat.isolated_scope():
            self.entry << NextTrigger()
            yield self
            self.ret << RawTrigger()  # next 는 호출하는 쪽이 고친다

    @property
    def defined(self):
        return self._defined


def call_sub(label, conds=None, acts=None, preserved=True):
    """서브루틴을 부른다. conds 가 있으면 참일 때만, preserved=False 면 게임당 한 번만.

    acts 는 부르기 직전에 실행한다(조건이 참일 때).
    인자: label(SubLabel), conds(선택), acts(선택), preserved(bool)
    반환: None
    비용: 조건·액션 없음 = 호출 자리 트리거 1 / 실행 1 + 본문 + 1(끝). 조건 있음 = +2
    CP: 본문이 바꾸는 대로
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_eud ctrig/trig.py:256 _emit_call
    """
    if not isinstance(label, SubLabel):
        fail("call_sub: SubLabel 이 아닙니다 (%r)", label)
    conds = _flat(conds)
    acts = _flat(acts)
    after = Forward()
    link = [SetNextPtr(label.ret, after)]
    if preserved:
        if conds:
            jump_if_not(conds, after, acts)
            RawTrigger(nextptr=label.entry, actions=link)
        elif all_const(acts):
            RawTrigger(nextptr=label.entry, actions=[*acts, *link])
        else:
            Trigger(actions=acts)
            RawTrigger(nextptr=label.entry, actions=link)
    else:
        callp = Forward()
        once_branch(conds, callp, after, acts)
        callp << RawTrigger(nextptr=label.entry, actions=link)
    after << NextTrigger()


# ---------------------------------------------------------------------------------------------
# 조건 칸 채우기 묶음 (DESIGN 3.4) — WP1 `cmp` 에서 옮김(WP3, 2026-09-17). cmp·i64 가 같이 쓴다.
# ---------------------------------------------------------------------------------------------


def placeholder(value=0):
    """실행 중에 채울 조건 amount 칸의 자리 표시(`Forward`, 값 value).

    정수가 아니므로 eudplib `EUDNot`·`EUDSCAnd(neg=True)` 가 제자리 부정을 하지 않고 분기로 처리한다(DESIGN 3.4).
    인자: value(정수, 기본 0)
    반환: Forward
    비용: 없음
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudext/cmp.py `_ph`(WP1)
    """
    f = Forward()
    f << value
    return f


def selfcond(cmp_, amount):
    """자기 비트마스크 칸(조건 +0)을 읽는 Memory 조건. 그 칸은 부르는 쪽이 실행 중에 채운다.

    eudplib 0.81 `EUDVariable.__lt__` 와 같은 방식. amount 가 정수면 제자리 부정이 맞다(칸 값이 부정과 무관).
    인자: cmp_(AtLeast/AtMost/Exactly), amount(정수 또는 `placeholder()`)
    반환: 새 Condition (칸 EPD 는 `EPD(조건)`)
    비용: 없음(채우기는 부르는 쪽)
    CP: 해당 없음
    로컬: 해당 없음
    epScript: 쓰지 않는다
    출처: eudext/cmp.py `_selfcond`(WP1), eudplib 0.81 `core/variable/eudv.py:589` `__lt__`
    """
    slot = Forward()
    c = MemoryEPD(slot, cmp_, amount)
    slot << _EPD(c)
    return c


class Plan:
    """한 번의 호출이 내는 앞 계산 묶음: 상수 쓰기 → 변수 채우기(SeqCompute 한 번) → 조건 트리거들.

    - `fill(dst, src, add=0)`: 칸(EPD) ← src + add (32비트 wrap). src 는 정수 또는 EUDVariable.
    - `put(dst, value)`: 칸 ← 상수. `op(dst, mod, src)`: 변수 연산 한 줄을 그대로.
    - `trig(conds, acts)`: 채우기 뒤에 낼 조건 트리거.
    - `uses(src)`: 이 묶음이 src 를 이미 원천으로 썼는가(같은 변수를 두 번 원천으로 쓰면 SeqCompute 가
      준비 트리거를 하나 더 낸다 — 채울 방향을 고를 때 본다).
    - `emit()`: 상수(준비 트리거) → 변수(차례대로) → 조건 트리거.
    인자: 없음
    반환: -
    비용: 준비 트리거 1 + 원천 변수마다 실행 1 (+ 원천이 겹치면 준비 1) + 조건 트리거 수
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/core.py:365~430` _PreBatch/pre_fill/_pre_flush
          (묶음 공유·되살림은 뺐다 — 한 호출의 조건만 다룬다). eudext/cmp.py `_Plan`(WP1)에서 옮김.
    """

    __slots__ = ("consts", "trigs", "used", "vars")

    def __init__(self):
        self.consts = []
        self.vars = []
        self.trigs = []
        self.used = set()

    def _src(self, src):
        self.used.add(id(src))

    def uses(self, src):
        return id(src) in self.used

    def fill(self, dst, src, add=0):
        """칸(EPD) ← src + add (32비트 wrap). src 는 정수 또는 EUDVariable."""
        add &= M32
        if isinstance(src, int):
            self.consts.append((dst, SetTo, (src + add) & M32))
        elif add:
            self.consts.append((dst, SetTo, add))
            self.vars.append((dst, Add, src))
            self._src(src)
        else:
            self.vars.append((dst, SetTo, src))
            self._src(src)

    def put(self, dst, value):
        self.consts.append((dst, SetTo, value))

    def op(self, dst, mod, src):
        if isinstance(src, int):
            self.consts.append((dst, mod, src & M32))
            return
        self.vars.append((dst, mod, src))
        self._src(src)

    def trig(self, conds, acts):
        self.trigs.append((conds, acts))

    def emit(self):
        # 상수를 먼저 두어야 SeqCompute 가 준비 트리거 하나에 모은다 (같은 변수가 두 번 나오면 스스로 나눈다)
        pairs = self.consts + self.vars
        if pairs:
            SeqCompute(pairs)
        for conds, acts in self.trigs:
            RawTrigger(conditions=conds, actions=acts)


def flag_cond(plan, init):
    """자기 칸 깃발 조건 `[칸 ≥ 1]` 과 그 칸 EPD. 칸은 plan 이 init 으로 먼저 채운다(plan 의 상수 쓰기).

    인자: plan(Plan), init(0 또는 1)
    반환: (Condition, 칸 EPD)
    비용: 준비 트리거의 액션 1 (트리거는 늘지 않는다)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: eudext/cmp.py `_flag`(WP1)
    """
    k = selfcond(AtLeast, 1)
    plan.put(_EPD(k), init)
    return k, _EPD(k)


# ---------------------------------------------------------------------------------------------
# 자기 수정 갈림 트리거 · 변수 트리거 사슬 · 결정 나무 (WP4, 2026-09-17) — i64 곱셈·나눗셈·시프트가 쓴다.
#
# 단계마다 조건 트리거 하나(방문 1)가, 조건이 참이면 액션으로 자기 next 를 바꿔 변수 트리거 사슬로 들어가게 한다.
# 바뀐 next 는 본문 첫머리의 되돌림 묶음이 매 호출 거짓 쪽으로 되돌린다. 쓰는 기법은 eudplib 이 스스로 쓰는 것뿐이다
# (`core/calcf/muldiv.py` `_eud_mul`·`_eud_div` 의 SetNextPtr 자기 수정, `core/variable/eudv.py` VProc 사슬).
# ---------------------------------------------------------------------------------------------


def add_modifiers(*vs):
    """변수 트리거들의 modifier 를 Add 로 바꾸는 액션 목록 (None 은 건너뜀). `var_chain` 원천 준비에 쓴다.

    인자: vs(EUDVariable 또는 None)
    반환: Action 목록
    비용: 액션만 (트리거 없음)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `EUDVariable.SetModifier`
    """
    return [v.SetModifier(Add) for v in vs if v is not None]


def var_chain(pairs, end):
    """[(원천 변수, 목적지)] 를 변수 트리거 사슬로 잇는다 → (첫 변수 트리거 주소, 준비 액션 목록).

    준비 액션을 실행한 트리거가 첫 변수 트리거로 가면 원천마다 `목적지 (원천 modifier) 원천 값` 이 차례로 실행되고
    마지막 변수 트리거가 end 로 간다. 원천은 한 사슬에 한 번만 나올 수 있다. 원천의 modifier 는 부르는 쪽이 정해 둔다
    (`add_modifiers`). 목적지는 EUDVariable 또는 EPD(상수식). `x += x` 는 (x, x).
    인자: pairs([(EUDVariable, 목적지)], 1개 이상), end(다음 트리거 주소식)
    반환: (ConstExpr, [Action]) — 준비 액션은 원천마다 2개(목적지·next)
    비용: 준비 트리거 1(부르는 쪽) + 원천마다 실행 1
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: eudplib 0.81 `core/variable/eudv.py:665` VProc·`:702` `_seqcompute_sub`, DPS_Enhance eudplib-port a7aad90
          `eud/ctrig/arrays.py` 원소 읽기 사슬(준비 액션으로 직접 잇기)
    """
    acts = []
    for k, (src, dst) in enumerate(pairs):
        nxt = pairs[k + 1][0].GetVTable() if k + 1 < len(pairs) else end
        acts.append(src.SetDest(dst))
        acts.append(SetNextPtr(src.GetVTable(), nxt))
    return pairs[0][0].GetVTable(), acts


class SelfFrame:
    """자기 수정 갈림 트리거를 쓰는 본문(보통 EUDFunc 본문)의 틀.

    만들 때 첫 트리거(init 액션)를 내고, 그 트리거는 본문 끝의 되돌림 묶음으로 뛰었다가 본문 첫 줄로 돌아온다.
    `node()` 가 만든 갈림 트리거의 next 는 되돌림 묶음이 매 호출 거짓 쪽으로 되돌린다. 본문을 다 낸 뒤 `finish()` 를
    부른다(그 앞에 흐름 밖 트리거를 둘 때는 먼저 `SetNextTrigger` 로 흐름을 끊는다). `end` = 본문 끝 라벨.
    - `node(conds, true_next, acts=(), false_next=None)`: 참이면 acts 를 하고 true_next 로, 거짓이면 false_next(없으면 다음 트리거).
    - `test(conds, pairs)`: 참이면 `var_chain(pairs)` 를 돌고, 어느 쪽이든 다음 트리거로.
    - `tree(root)`: `DNode` 나무 뿌리 줄의 되돌림을 등록한다(나무 트리거는 `emit_dtree` 가 낸다).
    - `resets`: 되돌림 액션 목록(직접 더해도 된다 — 다른 트리거가 바꾸는 next 등).
    인자: init(첫 트리거 액션 목록, 64개 이하)
    반환: -
    비용: 첫 트리거 1 + 되돌림 트리거 ⌈되돌림 수 / 64⌉ (매 호출), 갈림 트리거 방문 1씩
    CP: 바꾸지 않음
    로컬: 공유 안전 (갈림 트리거 상태는 한 호출 안에서만 쓰인다)
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/war.py:493` `_Node`(갈림 트리거 — 정적 next = 거짓 쪽)를 일반화
    """

    def __init__(self, init=()):
        self.resets = []
        self._reset = Forward()
        self._main = Forward()
        self.end = Forward()
        RawTrigger(nextptr=self._reset, actions=list(init))
        self._main << NextTrigger()

    def node(self, conds, true_next, acts=(), false_next=None):
        fn = Forward() if false_next is None else false_next
        lab = Forward()
        lab << RawTrigger(nextptr=fn, conditions=conds, actions=[SetNextPtr(lab, true_next), *acts])
        self.resets.append(SetNextPtr(lab, fn))
        if false_next is None:
            fn << NextTrigger()
        return lab

    def test(self, conds, pairs):
        if not pairs:
            return
        nxt = Forward()
        first, acts = var_chain(pairs, nxt)
        self.node(conds, first, acts, false_next=nxt)
        nxt << NextTrigger()

    def tree(self, root):
        self.resets += dpresets(dspine(root))

    def finish(self):
        SetNextTrigger(self.end)
        self._reset << NextTrigger()
        acts = self.resets
        for i in range(0, len(acts), 64):
            RawTrigger(actions=acts[i : i + 64])
        SetNextTrigger(self._main)
        self.end << NextTrigger()


class DNode:
    """결정 나무의 갈림 트리거(방문 1). 정적 next = 거짓 쪽 f, 참이면 액션이 자기 next 를 참 쪽 t 로 고친다.

    방문 전에 next 를 거짓 쪽으로 되돌려 둔다 — 들어가는 곳에서 거짓으로만 이어지는 줄(`dspine`)은 부르는 쪽이
    (`SelfFrame.tree` 또는 `dpresets`), 참 쪽 자식의 줄은 그 참 액션이 되돌린다(`emit_dtree`).
    인자: cond(Condition), t·f(DNode·DLeaf·트리거 주소식)
    반환: - (`label` = 이 트리거 주소)
    비용: 방문 1
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/war.py:493` `_Node`
    """

    __slots__ = ("cond", "f", "label", "t")

    def __init__(self, cond, t, f):
        self.label, self.cond, self.t, self.f = Forward(), cond, t, f


class DLeaf:
    """결정 나무의 잎 = label 로 들어감. 참 쪽으로 닿으면(acts 가 있으면) 그 일을 갈림 트리거가 하고 after 로 간다.

    인자: label(트리거 주소식), acts(참 쪽으로 닿았을 때 갈림 트리거가 할 액션 목록, 선택), after(그때 갈 곳)
    반환: -
    비용: 없음 (갈림 트리거가 대신 한다)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/war.py:502` `_Leaf`
    """

    __slots__ = ("acts", "after", "label")

    def __init__(self, label, acts=None, after=None):
        self.label, self.acts, self.after = label, acts, after


def dlabel(x):
    """DNode 면 그 트리거 주소, 그 밖(주소식)은 그대로. 출처: war.py a7aad90 `_lab`"""
    return x.label if isinstance(x, DNode) else x


def dgoto(x, true_side):
    """x 로 갈 때 (다음 트리거, 갈림 트리거가 함께 할 액션). 출처: war.py a7aad90 `_goto`"""
    if isinstance(x, DLeaf):
        if true_side and x.acts is not None:
            return dlabel(x.after), list(x.acts)
        return x.label, []
    return dlabel(x), []


def dspine(x):
    """x 에서 거짓 쪽으로만 이어지는 DNode 줄. 출처: war.py a7aad90 `_spine`"""
    out = []
    while isinstance(x, DNode):
        out.append(x)
        x = x.f
    return out


def dpresets(nodes):
    """DNode 들의 next 를 거짓 쪽으로 되돌리는 액션 목록. 출처: war.py a7aad90 `_presets`"""
    return [SetNextPtr(x.label, dgoto(x.f, False)[0]) for x in nodes]


def dtree(v, items):
    """items = [(문턱, 잎)] (문턱 오름차순, v ≥ 첫 문턱은 안다) → v ≥ 문턱인 마지막 잎으로 가는 균형 결정 나무.

    인자: v(EUDVariable — `AtLeast` 조건을 만든다), items([(int, DNode·DLeaf·주소식)], 1개 이상)
    반환: DNode (잎이 하나면 그 잎)
    비용: 나무 깊이 ⌈log2 len(items)⌉ 방문
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/war.py:535` `_tree`
    """
    if len(items) == 1:
        return items[0][1]
    m = len(items) // 2
    return DNode(v.AtLeast(items[m][0]), dtree(v, items[m:]), dtree(v, items[:m]))


def emit_dtree(root, done=None):
    """root 아래 DNode 트리거를 모두 낸다(모두 next 가 정해진 트리거 — 흐름 밖에 둔다). done: 이미 낸 노드 id 집합.

    인자: root(DNode), done(set, 선택 — 나무 여러 개가 노드를 나눠 가질 때)
    반환: None
    비용: 노드마다 트리거 1
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: 쓰지 않는다
    출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/war.py:543` `_emit_nodes`
    """
    done = set() if done is None else done
    stack = [root]
    while stack:
        x = stack.pop()
        if not isinstance(x, DNode) or id(x) in done:
            continue
        done.add(id(x))
        tl, acts = dgoto(x.t, True)
        x.label << RawTrigger(
            nextptr=dgoto(x.f, False)[0],
            conditions=x.cond,
            actions=[SetNextPtr(x.label, tl), *acts, *dpresets(dspine(x.t))],
        )
        stack += [x.t, x.f]
