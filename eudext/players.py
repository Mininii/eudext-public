"""players — 대상 목록과 플레이어별 액션, 사람·관전자 판정 (DESIGN 4.9, 3.6, 3.7).

CtrigAsm 맵의 플레이어 관용구를 eudplib 방식으로 준다.

| CtrigAsm | eudext |
|---|---|
| `for i=0,6 do … end` (컴파일 시점 펼침) | `for p in players.humans():` |
| `RotatePlayer({…}, 대상, FP)` / `CopyCpAction` | `players.run_as(대상, 액션…)` |
| `DisplayTextX`/`PlayWAVX` + RotatePlayer | `players.display(대상, …)` / `players.play_wav(대상, wav)` |
| `LocalPlayerID(i)`, 대상 목록의 로컬 판정 | `players.contains_user(대상)` |
| `HumanCheck(i, 1)` / `Enable_HumanCheck` | `players.is_human(i)` / `players.human_mask()` |
| `CreateVarArr(8, FP)` | `players.PerPlayer(EUDVariable)` |
| `HumanPlayers`(P1~P7 + P9~P12) | `players.Everyone` (= `Humans` + `Observers`) |
| `Force1`~`Force4`, `AllPlayers` | `players.Force(n)`, `players.All` (eudplib `Force1`, `AllPlayers` 도 받는다) |
| `SetForces({…},{…},…)` | `players.set_table(forces=…)` (맵 FORC 대신 쓸 표) |

대상(targets)으로 받는 것 — 목록(list/tuple/set)·`Targets` 로 섞어도 된다:
- 상수 번호 0~7, `P1`~`P8`
- 관전자 128~131. `P9`~`P12`(8~11)도 CtrigAsm `PlayerConvertX` 처럼 관전자 128~131 로 읽는다.
- `CurrentPlayer` — 부른 순간의 CP
- `AllPlayers` = `All`(0~7), `Force1`~`Force4` = `Force(1)`~`Force(4)`
- `Humans`(런타임에 사람인 슬롯), `Observers`(128~131), `Everyone`, `Allies(p)`(런타임 동맹)
- `EUDVariable`(런타임 번호, 0~7 또는 128~131)

CP 규약(DESIGN 3.6): 이 모듈의 함수는 **호출자의 CP 를 바꾸지 않는다**. `run_as` 는 CP 를 잠깐 옮겨 쓰고
(R3 1.5-1: 원시 CP 쓰기 + 끝에서 `f_setcurpl2cpcache()`) 캐시 값으로 되돌린다. `each` 는 본문 동안
CP·캐시를 p 로 두고(`SetCurrentPlayer`) 끝에서 들어올 때의 CP 로 되돌린다.

로컬(DESIGN 3.7): `contains_user` 의 결과는 **로컬 조건**이다(클라이언트마다 다르다). 그 결과로 공유 상태를
바꾸면 디싱크다. 표시(DisplayText·PlayWAV 등)만 그 안에서 한다. 이 PC 번호 비트(`_user_bit`)는 eudplib 의
`f_getuserplayerid()` 와 같은 로컬 값이고, 로컬 판정에만 읽는다.

출처: DPS_Enhance eudplib-port a7aad90 `eud/ctrig/framework.py:37` Enable_HumanCheck(사람 판정),
`eud/ctrig/cp.py`·`eud/ctrig/core.py:646,874`(CP 쓰기와 캐시), `eud/spec/G7_cp_classic.md` 1.5·RotatePlayer 절,
`docs/spec/S3_display.md` 3절·7.6(대상 표, 관전자 128~131).
"""

import copy

from eudplib import (
    Always,
    AtLeast,
    AtMost,
    CurrentPlayer,
    DisplayText,
    EncodePlayer,
    EUDBreak,
    EUDCreateBlock,
    EUDEndSwitch,
    EUDFunc,
    EUDJump,
    EUDLightBool,
    EUDLightVariable,
    EUDOnStart,
    EUDPopBlock,
    EUDReturn,
    EUDSwitch,
    EUDSwitchCase,
    EUDVariable,
    Exactly,
    Forward,
    GetPlayerInfo,
    IsUserCP,
    MemoryX,
    Never,
    NextTrigger,
    PlayWAV,
    RawTrigger,
    SetCurrentPlayer,
    SetMemory,
    SetNextPtr,
    SetTo,
    Trigger,
    TrgPlayer,
    f_getuserplayerid,
    f_setcurpl,
    f_setcurpl2cpcache,
    unProxy,
)

from eudext import _compat, _parts
from eudext.errors import fail

__all__ = [
    "ALL_IDS",
    "All",
    "Allies",
    "Everyone",
    "Force",
    "Humans",
    "OBSERVER_IDS",
    "Observers",
    "PerPlayer",
    "Targets",
    "contains_user",
    "display",
    "each",
    "f_contains_user",
    "f_display",
    "f_each",
    "f_force_members",
    "f_human_mask",
    "f_humans",
    "f_is_human",
    "f_play_wav",
    "f_run_as",
    "f_set_table",
    "force_members",
    "human_mask",
    "humans",
    "is_human",
    "play_wav",
    "run_as",
    "set_table",
]

# --- 주소 (SC 1.16.1 / SC:R EUD 주소) ---
CP_ADDR = 0x6509B0
LOCAL_PLAYER_ADDR = 0x512684  # 이 클라이언트의 플레이어 번호 (관전자 128~131) — 로컬 값
PLAYER_TYPE_ADDR = 0x57EEE8  # 플레이어 구조체(0x57EEE0, 36B) +8 = 형 바이트. 사람 = 2
PLAYER_STRUCT = 36
ALLIANCE_ADDR = 0x58D634  # 동맹 표 12×12 바이트, [p][q] ≥ 1 = p 가 q 를 동맹으로 둠
HUMAN_TYPE = 2

PLAYER_IDS = tuple(range(8))
OBSERVER_IDS = (128, 129, 130, 131)
ALL_IDS = PLAYER_IDS + OBSERVER_IDS

# 한 PC 에만 효과가 있는 액션(CP 가 이 PC 일 때만 보이거나 들린다). 관전자 CP 에도 안전하고,
# 부재 중인 플레이어에게 내도 아무 일이 없다(run_as 가 존재 판정을 생략하는 근거).
LOCAL_ONLY_ACTS = {
    8: "PlayWAV",
    9: "DisplayText",
    10: "CenterView",
    12: "SetMissionObjectives",
    28: "MinimapPing",
    29: "TalkingPortrait",
    30: "MuteUnitSpeech",
    31: "UnMuteUnitSpeech",
}
_ACT_SETDEATHS = 45
_P_CURRENT = 13


def _slot(p):
    """ALL_IDS 안의 번호 → 비트 자리 0~11."""
    return p if p < 8 else p - 120


# =============================================================================================
# 컴파일 시점 플레이어 표
# =============================================================================================

_table = {"humans": None, "forces": None}


def _player_list(name, items):
    out = []
    for x in _flat_py(items):
        e = EncodePlayer(x)
        if isinstance(e, bool) or not isinstance(e, int) or not 0 <= e <= 7:
            fail("%s: 플레이어 번호는 0~7(P1~P8) 상수여야 합니다 (%r)", name, x)
        if e not in out:
            out.append(e)
    return sorted(out)


def _flat_py(items):
    if isinstance(items, (list, tuple, set, frozenset, range)):
        out = []
        for x in items:
            out.extend(_flat_py(x))
        return out
    return [items]


def f_set_table(humans=None, forces=None):
    """컴파일 시점 플레이어 표를 맵 정보(OWNR·FORC) 대신 직접 정한다. 인자 없이 부르면 맵 정보로 돌아간다.

    CtrigAsm 맵은 TEP `SetForces(...)` 인자로 Force 표를 정했고, 이 표가 맵 FORC 와 다를 수 있다
    (S3 7.6·9-3). 옛 맵을 옮길 때 같은 표를 여기에 넣는다. 빌드마다 되돌리지 않는다(맵 설정이므로).
    인자: humans(사람 슬롯 번호 목록, None 이면 맵 OWNR), forces(최대 4개의 번호 목록, None 이면 맵 FORC)
    반환: None
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 해당 없음
    epScript: `pl.set_table(list(0, 1, 2), list(list(0, 1, 2), list(7)));` (→ `f_set_table`)
    출처: CtrigAsm `SetForces`(TEP), S3 7.6
    """
    # 모두 검사한 뒤 한꺼번에 바꾼다 (오류가 나면 표는 그대로)
    hs = None if humans is None else _player_list("set_table(humans)", humans)
    fs = None
    if forces is not None:
        if not isinstance(forces, (list, tuple)) or len(forces) > 4:
            fail("set_table(forces): 최대 4개의 번호 목록이어야 합니다 (%r)", forces)
        fs = [_player_list("set_table(forces[%d])" % i, f) for i, f in enumerate(forces)]
        seen = {}
        for i, f in enumerate(fs):
            for p in f:
                if p in seen:
                    fail("set_table(forces): 플레이어 %d 가 Force%d 와 Force%d 에 함께 있습니다", p, seen[p] + 1, i + 1)
                seen[p] = i
        fs += [[] for _ in range(4 - len(fs))]
    _table["humans"] = hs
    _table["forces"] = fs


set_table = f_set_table


def _pinfo(p):
    try:
        return GetPlayerInfo(p)
    except (IndexError, KeyError):
        fail("players: 맵을 불러오기(LoadMap) 전에는 플레이어 표를 읽을 수 없습니다")


def f_humans():
    """사람 슬롯 번호 목록(컴파일 시점, 오름차순). `for p in players.humans():` 로 코드를 펼친다.

    맵 OWNR 에서 형이 Human 인 슬롯(0~7). `set_table(humans=…)` 가 있으면 그 표. 관전자는 들지 않는다.
    인자: 없음
    반환: list[int]
    비용: 없음(컴파일 시점, 트리거 0)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `foreach(p : pl.humans()) { gold[p] += 1; }` (→ `f_humans`)
    출처: eudplib `EUDLoopPlayer("Human")` 의 목록 부분, CtrigAsm `for i=0,6`
    """
    if _table["humans"] is not None:
        return list(_table["humans"])
    return [p for p in PLAYER_IDS if _pinfo(p).typestr == "Human"]


humans = f_humans


def f_force_members(n):
    """Force n(1~4)의 슬롯 번호 목록(컴파일 시점). 맵 FORC 에서 그 세력이고 형이 Unused 가 아닌 슬롯.

    `set_table(forces=…)` 가 있으면 그 표.
    인자: n(1~4)
    반환: list[int]
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `foreach(p : pl.force_members(1)) { … }` (→ `f_force_members`)
    출처: eudplib `GetPlayerInfo(p).force` (S3 7.6)
    """
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 4:
        fail("Force: 세력 번호는 1~4 여야 합니다 (%r)", n)
    if _table["forces"] is not None:
        return list(_table["forces"][n - 1])
    out = []
    for p in PLAYER_IDS:
        pi = _pinfo(p)
        if pi.force == n - 1 and pi.typestr in ("Human", "Computer", "Rescuable", "Neutral"):
            out.append(p)
    return out


force_members = f_force_members


# =============================================================================================
# 대상
# =============================================================================================


class _M:
    """정규화된 대상 원소 (kind, arg)."""

    __slots__ = ("arg", "kind")

    def __init__(self, kind, arg=None):
        self.kind = kind
        self.arg = arg

    def __repr__(self):
        if self.kind == "p":
            return "P%d" % (self.arg + 1) if self.arg < 8 else "Ob%d" % (self.arg - 127)
        if self.kind in ("force", "allies"):
            return "%s(%r)" % (self.kind.capitalize(), self.arg)
        if self.kind == "var":
            return "var"
        return self.kind.capitalize()


def _norm(x, out):
    if isinstance(x, Targets):
        out.extend(x._members)
        return
    if isinstance(x, _M):
        out.append(x)
        return
    if isinstance(x, (list, tuple, set, frozenset, range)):
        for y in x:
            _norm(y, out)
        return
    if x is None or isinstance(x, (bool, str, bytes)):
        fail("대상: 플레이어 번호·변수·목록이어야 합니다 (%r)", x)
    e = EncodePlayer(x)
    if _compat.is_var(e):
        out.append(_M("var", unProxy(e)))
        return
    if isinstance(e, bool) or not isinstance(e, int):
        fail("대상: 플레이어 번호·EUDVariable·목록이어야 합니다 (%r). EUDLightVariable 은 EUDVariable 에 복사해 넘기세요", x)
    if 0 <= e <= 7:
        out.append(_M("p", e))
    elif 8 <= e <= 11:
        out.append(_M("p", 128 + e - 8))  # P9~P12 → 관전자 (CtrigAsm PlayerConvertX)
    elif e in OBSERVER_IDS:
        out.append(_M("p", e))
    elif e == _P_CURRENT:
        out.append(_M("current"))
    elif e == 17:
        out.append(_M("all"))
    elif 18 <= e <= 21:
        out.append(_M("force", e - 17))
    else:
        fail("대상: 지원하지 않는 플레이어 값 %r (0~7, P9~P12/128~131, CurrentPlayer, AllPlayers, Force1~4)", x)


class Targets:
    """대상 모음. 원소를 섞어 한 대상으로 쓴다: `Targets(P1, gcp, Force(2))`, `Humans | Observers`.

    원소 종류는 모듈 설명 참고. 상수 원소의 실제 번호(맵 표)는 **쓰는 순간** 정해진다(LoadMap·set_table 뒤).
    인자: members(여러 개, 목록·Targets 중첩 가능)
    반환: -
    비용: 없음(컴파일 시점)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const team = pl.Targets(P1, P2, pl.Observers);` (대문자라 이름 번역 없음)
    출처: S3 3절 대상 8종, 7.6
    """

    __slots__ = ("_members",)
    dont_flatten = True  # eudplib FlattenList(epScript `list(…)`)가 펼치지 않게

    def __init__(self, *members):
        out = []
        for m in members:
            _norm(m, out)
        self._members = tuple(out)

    def __or__(self, other):
        return Targets(self, other)

    def __ror__(self, other):
        return Targets(other, self)

    def __iter__(self):
        fail("Targets 는 런타임 대상입니다. 컴파일 시점 목록은 players.humans()/force_members(n), 런타임 반복은 players.each(대상)")

    def __repr__(self):
        return "Targets(%s)" % ", ".join(repr(m) for m in self._members)


def Force(n):  # noqa: N802 — 대상 상수처럼 쓰는 이름 (epScript 에서 번역되지 않게 대문자)
    """Force n(1~4) 대상(컴파일 시점 표, 런타임 판정 없음). eudplib `Force1`~`Force4` 와 같다.

    인자: n(1~4)
    반환: Targets
    비용: 없음
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `pl.run_as(pl.Force(1), DisplayText("…"));`
    출처: S3 7.6 (맵 FORC — TEP SetForces 표와 다르면 set_table 로 맞춘다)
    """
    f_force_members(n)  # 번호 검사
    return Targets(_M("force", n))


def Allies(p):  # noqa: N802
    """p 가 동맹으로 둔 플레이어(p 자신 제외, 0~7) 대상. 판정은 **런타임** 동맹 표(0x58D634).

    p 는 상수(0~7)만. 팀 전체는 `Targets(p, Allies(p))`.
    인자: p(0~7, P1~P8)
    반환: Targets
    비용: 원소마다 조건 1 (run_as/each 는 플레이어마다 조건 트리거)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `pl.run_as(pl.Targets(P1, pl.Allies(P1)), DisplayText("팀"));`
    출처: eudplib scdata `TrgPlayer.allyStatus`(0x58D634, 주석) — SC 동맹 표
    """
    e = EncodePlayer(p)
    if isinstance(e, bool) or not isinstance(e, int) or not 0 <= e <= 7:
        fail("Allies: 기준 플레이어는 0~7 상수여야 합니다 (%r)", p)
    return Targets(_M("allies", e))


Humans = Targets(_M("humans"))
Observers = Targets(*[_M("p", k) for k in OBSERVER_IDS])
Everyone = Targets(_M("humans"), *[_M("p", k) for k in OBSERVER_IDS])
All = Targets(_M("all"))


# --- 조건 조각 ---


def _is_human_cond(p):
    return MemoryX(PLAYER_TYPE_ADDR + PLAYER_STRUCT * p, Exactly, HUMAN_TYPE, 0xFF)


def _ally_cond(p, q):
    off = 12 * p + q
    addr = ALLIANCE_ADDR + (off & ~3)
    sh = 8 * (off & 3)
    return MemoryX(addr, AtLeast, 1 << sh, 0xFF << sh)


class _Res:
    """대상 해석 결과.

    const: 무조건 원소(번호 집합), cond: {번호: [(조건 공장, 존재 판정뿐인가)]},
    vars: 변수 원소(중복 제거), current: CurrentPlayer 포함 여부.
    """

    def __init__(self):
        self.const = set()
        self.cond = {}
        self.vars = []
        self.current = False

    def add_cond(self, p, factory, presence):
        self.cond.setdefault(p, []).append((factory, presence))

    def finish(self):
        for p in list(self.cond):
            if p in self.const:
                del self.cond[p]

    def drop_presence(self):
        """존재 판정뿐인 조건을 뗀다(이 PC 판정·표시 전용 액션): 그런 대안이 있는 번호는 무조건 원소로."""
        for p in list(self.cond):
            if any(presence for _f, presence in self.cond[p]):
                self.const.add(p)
                del self.cond[p]

    def has_observer(self):
        return any(p >= 128 for p in self.const) or any(p >= 128 for p in self.cond)

    def ordered(self):
        """each 순서: CurrentPlayer → 번호 오름차순(무조건·조건 섞어) → 변수."""
        out = []
        if self.current:
            out.append(("current", None, None))
        for p in sorted(self.const | set(self.cond)):
            out.append(("p", p, self.cond.get(p)))
        for v in self.vars:
            out.append(("var", v, None))
        return out


def _resolve(targets):
    ms = []
    _norm(targets, ms)
    r = _Res()
    for m in ms:
        k = m.kind
        if k == "p":
            r.const.add(m.arg)
        elif k == "all":
            r.const.update(PLAYER_IDS)
        elif k == "force":
            r.const.update(f_force_members(m.arg))
        elif k == "humans":
            for p in f_humans():
                r.add_cond(p, (lambda p=p: [_is_human_cond(p)]), True)
        elif k == "allies":
            q = m.arg
            for p in PLAYER_IDS:
                if p != q:
                    r.add_cond(p, (lambda p=p, q=q: [_ally_cond(q, p)]), False)
        elif k == "current":
            r.current = True
        elif k == "var":
            if not any(v is m.arg for v in r.vars):
                r.vars.append(m.arg)
        else:  # pragma: no cover
            fail("대상 원소 종류 %r", k)
    r.finish()
    return r


def _alt_conds(alts):
    """대안 목록(OR) → 조건 목록(AND). 대안이 둘 이상이면 1비트 깃발을 계산하는 트리거를 지금 낸다."""
    if len(alts) == 1:
        return alts[0][0]()
    flag = EUDLightBool()
    RawTrigger(actions=flag.Clear())
    for factory, _presence in alts:
        RawTrigger(conditions=factory(), actions=flag.Set())
    return [flag.IsSet()]


# =============================================================================================
# 이 PC 판정
# =============================================================================================

_ub = {"cell": None, "registered": False}


@_compat.register_build_reset
def _reset_user_bit():
    _ub["registered"] = False


def _init_user_bit():
    # 게임 시작 때 한 번: 이 PC 번호(eudplib 이 0x512684 바이트로 채운 값) → 비트 1개
    cell = _ub["cell"]
    u = f_getuserplayerid()
    for p in ALL_IDS:
        RawTrigger(conditions=u.Exactly(p), actions=cell.SetNumber(1 << _slot(p)))


def _user_bit_cell():
    if _ub["cell"] is None:
        _ub["cell"] = EUDLightVariable()
    if not _ub["registered"]:
        _ub["registered"] = True
        EUDOnStart(_init_user_bit)
    return _ub["cell"]


_plan_cache = {}


def _masked_plan(ids):
    """이 PC 번호(바이트) u 에 대해 `lo ≤ (u & m) ≤ hi` 하나로 ids 를 가려낼 수 있으면 [(m, 비교, 값)…] (0~2개).

    u 는 ALL_IDS 값만 나온다고 본다(0~7, 관전자 128~131). 마스크 0xFF 는 보통 구간 비교다.
    예: 사람이 0~6 이면 Everyone = {0~6, 128~131} = `(u & 7) ≤ 6` 한 조건. 없으면 None.
    """
    key = frozenset(ids)
    if key in _plan_cache:
        return _plan_cache[key]
    comp = [x for x in ALL_IDS if x not in key]
    best = None
    if not comp:
        best = []
    else:
        for m in (0xFF, *range(1, 0xFF)):
            sp = [x & m for x in key]
            lo, hi = min(sp), max(sp)
            if any(lo <= (x & m) <= hi for x in comp):
                continue
            allp = [x & m for x in ALL_IDS]
            if lo == hi:
                specs = [(m, Exactly, lo)]
            else:
                specs = []
                if lo > min(allp):
                    specs.append((m, AtLeast, lo))
                if hi < max(allp):
                    specs.append((m, AtMost, hi))
            if best is None or len(specs) < len(best):
                best = specs
            if len(best) <= 1:
                break
    _plan_cache[key] = best
    return best


def _const_user_conds(ids):
    """이 PC 번호 ∈ ids (상수 집합) → 조건 목록 (AND)."""
    u = f_getuserplayerid()
    ids = set(ids)
    if not ids:
        return [Never()]
    if len(ids) == 1:
        return [u.Exactly(next(iter(ids)))]
    plan = _masked_plan(ids)
    if plan is not None:
        # 마스크 구간 비교 0~2개 (시작 초기화가 필요 없다)
        if not plan:
            return [Always()]
        return [MemoryX(u.getValueAddr(), cmp, value, m) for m, cmp, value in plan]
    mask = 0
    for p in ids:
        mask |= 1 << _slot(p)
    cell = _user_bit_cell()
    return [cell.AtLeastX(1, mask)]


def f_contains_user(targets):
    """이 PC 의 플레이어(관전자 128~131 포함)가 대상에 드는가 — **로컬 조건**.

    - 상수 집합: 한 원소면 `이 PC 번호 == p`. `lo ≤ (번호 & m) ≤ hi` 로 가려지면 마스크 비교 1~2개
      (예: 사람 0~6 + 관전자 = `(번호 & 7) ≤ 6`). 그 밖은 게임 시작 때 한 번 만든 "이 PC 비트"에
      마스크 조건 1개(시작 트리거 12개·약 3.1KB, 맵에 한 번).
    - `Humans` 의 존재 판정은 뺀다(이 PC 는 늘 게임에 있다). `Allies(q)`·변수·`CurrentPlayer` 가 섞이면
      부르는 자리에 판정 트리거(원소마다 1)를 내고 1비트 깃발 조건을 돌려준다.
    인자: targets(대상)
    반환: Condition 또는 조건 목록(AND) — `EUDIf()(…)` 에 넣는다. 매 호출 새 객체
    비용: 상수 집합 = 호출 자리 0 / 실행 0 (비트 마스크형은 게임 시작 때 한 번 12트리거·3.1KB).
          섞인 대상 = 호출 (부분 수 + 1 + 변수 패치) / 실행 비슷 — 변수+관전자+CurrentPlayer 호출 5 / 실행 6~7 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: **로컬 전용** — 결과로 공유 상태를 바꾸면 디싱크. 표시만 한다
    epScript: `if (pl.contains_user(pl.Everyone)) { … }` (→ `f_contains_user`)
    출처: S3 7.6 대상별 로컬 판정, eudplib `f_getuserplayerid`/`IsUserCP`(eudlib/utilf/userpl.py)
    """
    r = _resolve(targets)
    r.drop_presence()
    u = f_getuserplayerid()
    parts = []
    if r.const:
        parts.append(("const", r.const))
    for p in sorted(r.cond):
        parts.append(("cond", p, r.cond[p]))
    for v in r.vars:
        parts.append(("var", v))
    if r.current:
        parts.append(("current",))
    if not parts:
        return Never()

    def conds_of(part):
        k = part[0]
        if k == "const":
            return _const_user_conds(part[1])
        if k == "cond":
            p, alts = part[1], part[2]
            if len(alts) == 1:
                return [u.Exactly(p)] + alts[0][0]()
            return [u.Exactly(p)] + _alt_conds(alts)
        if k == "var":
            return [u.Exactly(part[1])]
        return [IsUserCP()]

    if len(parts) == 1:
        cs = conds_of(parts[0])
        return cs[0] if len(cs) == 1 else cs
    flag = EUDLightBool()
    RawTrigger(actions=flag.Clear())
    for part in parts:
        Trigger(conditions=conds_of(part), actions=flag.Set())
    return flag.IsSet()


contains_user = f_contains_user


# =============================================================================================
# 사람 판정
# =============================================================================================


@EUDFunc
def _is_human_var(p):
    # 출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/framework.py:37 Enable_HumanCheck 의 조건(형 바이트 == 2)
    ret = EUDVariable()
    ret << 0
    for i in PLAYER_IDS:
        RawTrigger(conditions=[p.Exactly(i), _is_human_cond(i)], actions=ret.SetNumber(1))
    EUDReturn(ret)


def f_is_human(p):
    """플레이어 p(0~7)가 지금 사람인가(플레이어 구조체 +8 형 바이트 == 2, 나가면 거짓).

    인자: p(0~7 상수 또는 EUDVariable — 0~7 밖이면 거짓)
    반환: Condition (상수 = MemoryX 1개, 변수 = 공유 함수 결과 비교)
    비용: 상수 = 호출 0 / 실행 0. 변수 = 본문 11(1벌) / 호출 1 / 실행 15 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `if (pl.is_human(i)) { … }` (→ `f_is_human`)
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/framework.py:37 Enable_HumanCheck, CtrigAsm HumanCheck
    """
    e = EncodePlayer(p)
    if _compat.is_var(e):
        r = _is_human_var(unProxy(e))
        return r.Exactly(1)
    if isinstance(e, bool) or not isinstance(e, int) or not 0 <= e <= 7:
        fail("is_human: 플레이어 번호는 0~7 이어야 합니다 (%r)", p)
    return _is_human_cond(e)


is_human = f_is_human


@EUDFunc
def _human_mask():
    # 출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/framework.py:37 Enable_HumanCheck (0 으로 비우고 8개 조건 트리거)
    ret = EUDVariable()
    ret << 0
    for i in PLAYER_IDS:
        RawTrigger(conditions=_is_human_cond(i), actions=ret.AddNumber(1 << i))
    EUDReturn(ret)


def f_human_mask():
    """지금 사람인 플레이어의 비트 모음(비트 i = 플레이어 i)을 새 변수로 돌려준다.

    인자: 없음
    반환: EUDVariable (0~255)
    비용: 본문 11(1벌) / 호출 1 / 실행 14 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const hm = pl.human_mask();` (→ `f_human_mask`)
    출처: DPS_Enhance eudplib-port a7aad90 eud/ctrig/framework.py:37 Enable_HumanCheck (결과를 고정 주소 대신 변수로)
    """
    return _human_mask()


human_mask = f_human_mask


# =============================================================================================
# 플레이어별 액션
# =============================================================================================


def _is_cp_write(a):
    f = a.fields
    return f[7] == _ACT_SETDEATHS and isinstance(f[4], int) and f[4] == _parts.EPD_CP and f[6] == 0


def _observer_safe(a):
    t = a.fields[7]
    if t in LOCAL_ONLY_ACTS:
        return True
    return t == _ACT_SETDEATHS and not (isinstance(a.fields[4], int) and a.fields[4] == _P_CURRENT)


def _act_name(a):
    t = a.fields[7]
    return LOCAL_ONLY_ACTS.get(t, "acttype %r" % (t,))


def _make_actions(actions, p):
    """액션 인자 → 이 원소용 새 Action 목록 (호출 가능한 것은 p 로 부른다, 나머지는 복사)."""
    out = []
    for a in actions:
        if callable(a) and not hasattr(a, "fields"):
            out.extend(_make_actions(_flat_py(a(p)), p))
            continue
        if isinstance(a, (list, tuple)):
            out.extend(_make_actions(a, p))
            continue
        au = unProxy(a)
        if isinstance(au, Forward) and au.IsSet():
            au = au.expr
        if not hasattr(au, "fields") or not hasattr(au, "SetParentTrigger"):
            fail("run_as: 액션이 아닙니다 (%r)", a)
        if _is_cp_write(au):
            fail("run_as: 액션 안에서 CP(0x6509B0)를 바꾸지 마세요 — run_as 가 CP 를 관리합니다")
        out.append(copy.copy(au))
    return out


def _cpw(p):
    # 잠깐 옮기는 CP 쓰기(캐시는 그대로 두고 끝에서 f_setcurpl2cpcache 로 되돌린다, R3 1.5-1)
    return SetMemory(CP_ADDR, SetTo, p)


def f_run_as(targets, *actions):
    """대상마다 CP 를 그 플레이어로 옮겨 같은 액션을 낸다 (RotatePlayer/CopyCpAction 대체). 끝에서 CP 를 되돌린다.

    - 액션: Action, 목록, 또는 `fn(p)`(원소마다 새 액션을 돌려주는 함수; p 는 번호·변수·CurrentPlayer).
      Action 은 원소마다 복사한다. 액션 안의 CP 쓰기는 오류.
    - 실행 순서: CurrentPlayer → 조건부 원소(Humans·Allies) → 변수 원소 → 상수 원소. 상수 원소는 모아서
      **한 트리거**(액션 64개 넘으면 나눔)에 넣고 CP 되돌리기와 합친다.
    - 액션이 모두 표시 전용(`LOCAL_ONLY_ACTS`)이면 `Humans` 의 존재 판정을 생략한다(부재 PC 는 화면이 없다).
    - 관전자(128~131) 원소에는 표시 전용 액션과 CurrentPlayer 가 아닌 SetDeaths/SetMemory 만 준다(그 밖은 오류).
    - 같은 상수는 한 번만. 변수 원소는 런타임에 중복을 빼지 않는다(CtrigAsm RotatePlayer 와 같음).
    인자: targets(대상), actions(여러 개)
    반환: None
    비용: 상수 대상(n명·액션 k개) = 호출 1 / 실행 2 (n·(k+1)+2 ≤ 64, 넘으면 64개마다 +1). 조건부 원소마다 호출·실행 +1
          (Humans 6명 SetDeaths = 호출 7 / 실행 8), 변수 원소 1명 = 호출 3 / 실행 5, CurrentPlayer 만 = 1 / 1 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음(잠깐 옮기고 eudplib CP 캐시 값으로 되돌림 — 들어올 때 CP == 캐시가 eudplib 규약)
    로컬: 공유 안전(액션이 공유 동작이면 모든 PC 에서 같게 돈다)
    epScript: `pl.run_as(pl.Everyone, DisplayText("시작"), PlayWAV("x.wav"));` (→ `f_run_as`; 목록은 `list(P1, P2)`)
    출처: CtrigAsm CopyCpAction(CA:42981)/RotatePlayer(L322:74) — DPS_Enhance eudplib-port a7aad90 eud/spec/G7_cp_classic.md RotatePlayer 절,
          eudplib `DisplayTextAll`(eudlib/utilf/userpl.py) 의 CP 옮기기
    """
    r = _resolve(targets)
    segs_cur = _make_actions(actions, CurrentPlayer) if r.current else None
    segs_cond = {p: _make_actions(actions, p) for p in sorted(r.cond)}
    segs_var = [(v, _make_actions(actions, v)) for v in r.vars]
    samples = [a for seg in segs_cond.values() for a in seg] + [a for _v, seg in segs_var for a in seg]
    if segs_cur:
        samples += segs_cur
    const_ids = sorted(r.const)
    segs_const = {p: _make_actions(actions, p) for p in const_ids}
    for seg in segs_const.values():
        samples += seg
    if not samples:
        return  # 대상이나 액션이 없다
    local_only = all(a.fields[7] in LOCAL_ONLY_ACTS for a in samples)
    if local_only and r.cond:
        # 존재 판정만 있던 원소를 상수 원소로 옮긴다
        before = set(r.cond)
        r.drop_presence()
        for p in before - set(r.cond):
            segs_const[p] = segs_cond.pop(p)
        const_ids = sorted(segs_const)
    for p in list(segs_const) + list(segs_cond):
        if p >= 128:
            seg = segs_const.get(p) or segs_cond.get(p) or []
            bad = [a for a in seg if not _observer_safe(a)]
            if bad:
                fail("run_as: 관전자(CP %d)에게는 표시 전용 액션만 줄 수 있습니다 (%s)", p, _act_name(bad[0]))
    moved = False
    # 1) CurrentPlayer — CP 를 옮기기 전
    if segs_cur:
        if segs_const and not segs_cond and not segs_var:
            pass  # 아래 상수 트리거 맨 앞에 합친다
        else:
            Trigger(actions=segs_cur)
    # 2) 조건부 원소
    for p, seg in segs_cond.items():
        conds = _alt_conds(r.cond[p])
        Trigger(conditions=conds, actions=[_cpw(p), *seg])
        moved = True
    # 3) 변수 원소
    for v, seg in segs_var:
        Trigger(actions=[_cpw(v), *seg])
        moved = True
    # 4) 상수 원소 + CP 되돌리기
    acts = []
    if segs_cur and segs_const and not segs_cond and not segs_var:
        acts.extend(segs_cur)
    for p in const_ids:
        acts.append(_cpw(p))
        acts.extend(segs_const[p])
    if const_ids:
        moved = True
    if not moved:
        if acts:
            Trigger(actions=acts)
        return
    if _parts.all_const(acts):
        f_setcurpl2cpcache(actions=acts)
    else:
        Trigger(actions=acts)
        f_setcurpl2cpcache()


run_as = f_run_as


def f_play_wav(targets, wav):
    """대상 PC 에서 소리를 낸다 (PlayWAVX 대체) = `run_as(targets, PlayWAV(wav))`.

    인자: targets(대상), wav(맵 안의 소리 파일 이름)
    반환: None
    비용: `run_as` 와 같음 (상수 대상 = 호출 1 / 실행 2)
    CP: 바꾸지 않음
    로컬: 공유 안전(소리는 대상 PC 에서만 난다)
    epScript: `pl.play_wav(pl.Everyone, "staredit\\wav\\button3.wav");` (→ `f_play_wav`)
    출처: CtrigAsm PlayWAVX + RotatePlayer, eudplib `PlayWAVAll`
    """
    f_run_as(targets, PlayWAV(wav))


play_wav = f_play_wav


def f_display(targets, *parts, **kw):
    """대상 PC 에 서식 있는 글을 띄운다 = `display.show(targets, *parts, **kw)` (DESIGN 4.7, WP6).

    `eudext.display`(WP6)가 없으면: parts 가 모두 문자열이고 옵션이 없을 때만 `run_as(targets, DisplayText(글))`
    로 띄운다(임시 경로). 그 밖은 오류.
    인자: targets(대상), parts(원소들), kw(display.show 옵션)
    반환: display.show 의 반환값 (임시 경로는 None)
    비용: display.show 참고. 임시 경로 = `run_as` (상수 대상 = 호출 1 / 실행 2)
    CP: 바꾸지 않음
    로컬: 공유 안전(글은 대상 PC 에서만 보인다)
    epScript: `pl.display(pl.Everyone, "\\x04게임 시작");` (→ `f_display`)
    출처: S3 7.2 (`players.display` = `dp.show` 별칭)
    """
    try:
        import eudext.display as dp
    except ModuleNotFoundError as e:
        if e.name != "eudext.display":
            raise
        dp = None
    if dp is not None:
        return dp.f_show(targets, *parts, **kw)
    if parts and not kw and all(isinstance(x, (str, bytes)) for x in parts):
        if all(isinstance(x, str) for x in parts):
            text = "".join(parts)
        else:
            text = b"".join(x.encode("utf-8") if isinstance(x, str) else x for x in parts)
        f_run_as(targets, DisplayText(text))
        return None
    fail("display: 문자열이 아닌 원소나 옵션(%s)은 display 모듈(WP6) 이후에 쓸 수 있습니다",
         ", ".join(sorted(kw)) or ", ".join(type(x).__name__ for x in parts if not isinstance(x, (str, bytes))))


display = f_display


# =============================================================================================
# 런타임 반복
# =============================================================================================

_EACH_BLOCK = "eudext_players_each"


class _Each:
    """`each(targets)` 결과: `with … as p:` 또는 `for p in …:` (epScript `foreach`) 로 한 번 연다."""

    __slots__ = ("_observers", "_st", "_targets")

    def __init__(self, targets, observers):
        self._targets = targets
        self._observers = observers
        self._st = None

    def __repr__(self):
        return "<players.each %r>" % (self._targets,)

    def _open(self):
        if self._st is not None:
            fail("each: 같은 each 객체는 한 번만 열 수 있습니다")
        r = _resolve(self._targets)
        if r.has_observer() and not self._observers:
            fail("each: 관전자(128~131)는 돌지 않습니다. 관전자 표시는 run_as/display/contains_user 를 쓰거나 observers=True")
        members = r.ordered()
        pv = EUDVariable()
        body_start, body_end, after, cont = Forward(), Forward(), Forward(), Forward()
        n = len(members)
        disp = [Forward() for _ in range(n)] + [after]
        orig = None
        if n == 0:
            EUDJump(after, must_use=False)
        else:
            # 들어올 때의 CP = eudplib CP 캐시 값 (run_as·eudplib 읽기 함수와 같은 규약, f_getcurpl 보다 실행 5 적음)
            orig = EUDVariable()
            orig << _compat.cpcache_var()
            selfmod = {k: Forward() for k, m in enumerate(members) if m[0] == "p" and m[2]}
            restore = [SetNextPtr(selfmod[k], disp[k + 1]) for k in sorted(selfmod)]
            first = members[0]
            if restore and not (first[0] == "p" and not first[2]):
                RawTrigger(actions=restore)
                restore = []
            for k, (kind, arg, alts) in enumerate(members):
                nxt = disp[k + 1]
                link = SetNextPtr(body_end, nxt)
                if kind == "p" and not alts:
                    acts = [*restore, pv.SetNumber(arg), *SetCurrentPlayer(arg), link]
                    restore = []
                    disp[k] << RawTrigger(nextptr=body_start, actions=acts)
                elif kind == "p":
                    disp[k] << NextTrigger()
                    conds = _alt_conds(alts)
                    xk = selfmod[k]
                    xk << RawTrigger(
                        nextptr=nxt,
                        conditions=conds,
                        actions=[pv.SetNumber(arg), *SetCurrentPlayer(arg), link, SetNextPtr(xk, body_start)],
                    )
                elif kind == "current":
                    # 맨 앞 원소라 캐시 = orig. CP 도 캐시 값으로 맞춰 "본문에서 CP = p" 를 지킨다
                    disp[k] << NextTrigger()
                    pv << orig
                    f_setcurpl2cpcache(actions=[link])
                    EUDJump(body_start)
                else:
                    disp[k] << NextTrigger()
                    pv << arg
                    f_setcurpl(pv, actions=[link])
                    EUDJump(body_start)
        body_start << NextTrigger()
        EUDCreateBlock(_EACH_BLOCK, {"contpoint": cont, "loopend": after})
        self._st = (body_end, after, cont, orig, n)
        return TrgPlayer.cast(pv)

    def _close(self):
        body_end, after, cont, orig, n = self._st
        EUDPopBlock(_EACH_BLOCK)
        if not cont.IsSet():
            cont << NextTrigger()
        body_end << RawTrigger()  # next 는 디스패처가 실행 중에 고친다
        after << NextTrigger()
        if n:
            f_setcurpl(orig)

    def __enter__(self):
        return self._open()

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._close()
        return False

    def __iter__(self):
        p = self._open()
        yield p
        self._close()


def f_each(targets, observers=False):
    """대상마다 한 번씩 본문을 돈다(런타임). 본문 안에서 CP = p(캐시 포함), 끝나면 들어올 때의 CP 로 되돌린다.

    본문 트리거는 한 벌이다. 컴파일 시점 펼침은 `for p in players.humans():`.
    - 순서: CurrentPlayer → 번호 오름차순 → 변수. `Humans`·`Allies` 는 런타임 판정이 참인 플레이어만.
    - `EUDBreak()`/`EUDContinue()`(epScript `break`/`continue`) 를 쓸 수 있다.
    - 관전자는 기본으로 막는다(p 가 128~131 이면 배열 색인·CP 액션이 위험). `observers=True` 면 돈다.
    - EUDFunc 본문과 같이 재진입하지 않는다(같은 each 안에서 자기 자신을 다시 부르지 않는다).
    인자: targets(대상), observers(bool)
    반환: 컨텍스트/반복 객체 — `with pl.each(T) as p:` / `for p in pl.each(T):`. p 는 TrgPlayer(변수)
    비용: 호출 자리 = 캐시 복사 1 + 원소마다 1(변수·CurrentPlayer 원소는 3~4, 맨 앞이 조건부면 +1) + 꼬리 3.
          실행 = 고정 7 + 원소마다 디스패처 1 + 도는 원소마다 (본문 + 1) — 상수 1명 빈 본문 9, 4명 15 (2026-09-16, docs/COSTS.md)
    CP: 본문 동안 p(캐시 포함), 끝나면 들어올 때의 eudplib CP 캐시 값으로 되돌림(break 포함).
        본문 밖으로 점프(EUDReturn 등)하면 되돌리지 않는다. CurrentPlayer 원소의 p 도 캐시 값
    로컬: 공유 안전
    epScript: `foreach(p : pl.each(pl.Humans)) { … }` (→ `f_each`)
    출처: eudplib `EUDPlayerLoop`(eudlib/utilf/pexist.py — 관전자를 돌지 않음), `EUDBranch` 의 자기 next 고치기(trigger/branch.py)
    """
    return _Each(targets, bool(observers))


each = f_each


# =============================================================================================
# 플레이어별 저장
# =============================================================================================


class PerPlayer:
    """플레이어 수만큼 같은 형식의 객체를 만든다 (CreateVarArr 대체). `PerPlayer(EUDVariable)`.

    - 상수 번호(0~count-1, P1~): `pp[0]`, `pp[P2] += 1`, `for x in pp:` — 그 객체를 그대로 쓴다(트리거 0).
    - 변수 번호: `pp.get(p)`(EUDVariable 원소만), `pp.set(p, v)`, `pp.iadditem(p, v)`, `pp.isubitem(p, v)`,
      `pp.switch(p, fn)` — `EUDSwitch` 로 고른다. 범위 밖 번호는 아무것도 하지 않는다(get 은 0).
      `pp[변수]` 는 오류(epScript `pp[p] = x` 가 임시 값에 쓰이는 것을 막는다) — epScript `pp[p] += x;` 는 된다.
    - 뺄셈은 wrap(DESIGN 3.5): 변수 원소는 `_parts.isub32`, 그 밖은 원소의 `isub`/`-=`.
    인자: factory(형식 또는 함수), *args/**kwargs(factory 인자), count(개수, 기본 8),
          by_player(True 면 factory(p, *args, **kwargs))
    반환: -
    비용: 원소 비용 × count. 상수 번호 = 원소 연산 그대로. 변수 번호(EUDSwitch, 8칸) = get 호출 15 / 실행 10,
          iadditem 호출 14 / 실행 8 (2026-09-16, docs/COSTS.md)
    CP: 바꾸지 않음
    로컬: 공유 안전
    epScript: `const gold = pl.PerPlayer(EUDVariable);` → `gold[0] += 5; gold.set(p, 3);` (대문자라 이름 번역 없음)
    출처: CtrigAsm CreateVarArr/CreateWarArr (R1 1-c)
    """

    __slots__ = ("_items",)

    def __init__(self, factory, *args, count=8, by_player=False, **kwargs):
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            fail("PerPlayer: count 는 1 이상의 정수여야 합니다 (%r)", count)
        if by_player:
            self._items = [factory(p, *args, **kwargs) for p in range(count)]
        else:
            self._items = [factory(*args, **kwargs) for _ in range(count)]

    def __repr__(self):
        return "PerPlayer(%d × %s)" % (len(self._items), type(self._items[0]).__name__)

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    @property
    def items(self):
        return list(self._items)

    def _index(self, p):
        e = EncodePlayer(p)
        if _compat.is_var(e):
            return unProxy(e)
        if isinstance(e, bool) or not isinstance(e, int) or not 0 <= e < len(self._items):
            fail("PerPlayer: 번호 %r 가 범위(0~%d) 밖입니다", p, len(self._items) - 1)
        return e

    def __getitem__(self, p):
        i = self._index(p)
        if isinstance(i, int):
            return self._items[i]
        fail("PerPlayer[변수 번호]: 읽기는 .get(p), 쓰기는 .set(p, 값) 을 쓰세요 (대입이 임시 값에 쓰이는 것을 막습니다)")

    def __setitem__(self, p, value):
        self.set(p, value)

    def switch(self, p, fn):
        """번호 p 의 원소로 fn(원소) 을 부른다. p 가 변수면 EUDSwitch 로 원소마다 fn 을 한 번씩 낸다."""
        i = self._index(p)
        if isinstance(i, int):
            fn(self._items[i])
            return
        EUDSwitch(i)
        for k, item in enumerate(self._items):
            if EUDSwitchCase()(k):
                fn(item)
                EUDBreak()
        EUDEndSwitch()

    def get(self, p):
        """원소 p 의 값. 상수 번호면 원소 자체, 변수 번호면 새 EUDVariable(원소가 EUDVariable 일 때만)."""
        i = self._index(p)
        if isinstance(i, int):
            return self._items[i]
        if not all(isinstance(x, EUDVariable) for x in self._items):
            fail("PerPlayer.get(변수 번호): 원소가 EUDVariable 일 때만 됩니다. 그 밖은 .switch(p, fn)")
        ret = EUDVariable()
        ret << 0

        def rd(item):
            ret << item

        self.switch(i, rd)
        return ret

    def set(self, p, value):
        """원소 p ← value."""

        def wr(item):
            if item is value:
                return
            if _compat.is_varbase(item):
                item << value
            elif hasattr(item, "assign"):
                item.assign(value)
            else:
                item << value

        self.switch(p, wr)

    def iadditem(self, p, value):
        """원소 p += value (epScript `pp[p] += v`)."""

        def add(item):
            if hasattr(item, "iadd") and not _compat.is_varbase(item):
                item.iadd(value)
            else:
                item += value  # noqa: PLW2901 — 변수 계열은 제자리 연산

        self.switch(p, add)

    def isubitem(self, p, value):
        """원소 p −= value, **wrap** (epScript `pp[p] -= v`, DESIGN 3.5)."""

        def sub(item):
            if _compat.is_varbase(item):
                _parts.isub32(item, value)
            elif hasattr(item, "isub"):
                item.isub(value)
            else:
                item -= value  # noqa: PLW2901

        self.switch(p, sub)
