"""`players` 시험 (에뮬레이터): 대상 해석·run_as·contains_user(관전자 슬롯 포함)·each·사람 판정·PerPlayer·CP 복구·예제 빌드.

python tests/t_players.py
비용 표: python tools/cost.py tests/t_players.py [--append --out <파일> --bytes]

SC 모델(이 시험 전용 도우미):
- DisplayText(9)/PlayWAV(8) 캡처 — 실행 순간의 CP 를 기록한다. SC 는 CP == 이 PC 번호(0x512684)일 때만 띄운다.
- 이 PC 번호 = `scmodel.game_memory(local_player=…)` (관전자는 128~131).
- 플레이어 형 바이트(0x57EEE8 + 36p), 동맹 표(0x58D634 + 12p + q)는 기계 메모리에 직접 쓴다.
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import shutil  # noqa: E402

from eudplib import (  # noqa: E402
    EPD,
    Add,
    AllPlayers,
    CurrentPlayer,
    DisplayText,
    DoActions,
    EncodeString,
    EUDBreak,
    EUDContinue,
    EUDEndIf,
    EUDIf,
    EUDLightVariable,
    EUDVariable,
    Exactly,
    Force2,
    Force3,
    GetTriggerCounter,
    Memory,
    P1,
    P2,
    P3,
    P4,
    P5,
    P8,
    P9,
    P12,
    PlayWAV,
    SetDeaths,
    SetMemory,
    SetResources,
    SetTo,
    f_dwread_epd,
    f_getuserplayerid,
    f_setcurpl,
    TrgPlayer,
)

from eudext import _compat  # noqa: E402
from eudext import players as pl  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import scmodel  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
CP = 0x6509B0
DEATH0 = 0x58A364
LOCALS = pl.ALL_IDS  # 0~7, 관전자 128~131
OBS = pl.OBSERVER_IDS
U = 20  # 시험이 쓰는 데스 칸 유닛 번호의 시작 (P1 마린 칸 EPD 0 과 떨어뜨림)

# 시험 맵 설정: 컴파일 시점 표(set_table)와 런타임 형 바이트
HUMAN_TABLE = [0, 2, 3, 4, 6, 7]
FORCES = [[0, 2], [1], [3, 4], []]
TYPES = ["human", "computer", "human", "human", "human", "inactive", "human", "human"]
ALLY = {0: {2, 5}, 1: {0, 1, 3}, 2: {7}}  # p → p 가 동맹으로 둔 q (자기 자신 칸 포함은 무시돼야 한다)

pl.set_table(humans=HUMAN_TABLE, forces=FORCES)


# ---------------------------------------------------------------------------------------------
# SC 모델 도우미
# ---------------------------------------------------------------------------------------------


def install_capture(m):
    m.captured = []

    def disp(mm, f):
        mm.captured.append(("text", mm.dw(CP), f[1]))

    def wav(mm, f):
        mm.captured.append(("wav", mm.dw(CP), f[2]))

    m.act_handlers[9] = disp
    m.act_handlers[8] = wav


def local_memory(local):
    """이 PC 번호가 local(0~7, 관전자 128~131)인 클라이언트의 시작 메모리."""
    return {"local_player": local, "players": list(TYPES), "cp": 0}


def set_type(m, p, kind):
    m.setdb(scmodel.PLAYER_TABLE + scmodel.PLAYER_STRUCT * p + 8, scmodel.PLAYER_TYPE[kind])


def set_allies(m, table):
    for p in range(12):
        for q in range(12):
            m.setdb(0x58D634 + 12 * p + q, 0)
    for p, qs in table.items():
        for q in qs:
            m.setdb(0x58D634 + 12 * p + q, 1)


def deaths(m, p, unit):
    return m.dw(DEATH0 + 4 * (unit * 12 + p))


def run_with(s, name, inputs=None, prep=None, cycles=1):
    """메모리를 초기 상태로 돌리고 prep(machine) 뒤 실행. (결과, 캡처) 를 돌려준다."""
    s.reset()
    m = s.machine
    if prep is not None:
        prep(m)
    m.captured.clear()
    r = s.run(name, inputs, cycles)
    return r, list(m.captured)


def cps(cap, kind="text"):
    return [c[1] for c in cap if c[0] == kind]


def present_humans(types):
    return [p for p in HUMAN_TABLE if types[p] == "human"]


# ---------------------------------------------------------------------------------------------
# 파이썬 참조: 이 PC 가 대상에 드는가
# ---------------------------------------------------------------------------------------------


def _random_subsets(n=30, seed=8):
    import random

    rng = random.Random(seed)
    out = []
    while len(out) < n:
        k = rng.randrange(2, 12)
        sub = sorted(rng.sample(pl.ALL_IDS, k))
        if sub not in out:
            out.append(sub)
    return out


RANDOM_SETS = _random_subsets()


def ref_set(key, v, w, cp, allies):
    """대상 키 → (이 PC 번호 집합). Humans 는 컴파일 시점 표(이 PC 는 늘 게임에 있다)."""

    def al(p):
        return {q for q in allies.get(p, ()) if q != p and q < 8}

    hum = set(HUMAN_TABLE)
    table = {
        "p1": {0},
        "p8": {7},
        "ob1": {128},
        "p9": {128},
        "p12": {131},
        "obs": set(OBS),
        "hum": hum,
        "every": hum | set(OBS),
        "all": set(range(8)),
        "allp": set(range(8)),
        "f1": {0, 2},
        "f2": {1},
        "f4": set(),
        "range": {1, 2, 3},
        "range_obs": {7} | set(OBS),
        "obs_head": {128, 129},
        "mask": {0, 2, 130},
        "pair": {3, 5},
        "list_all": set(pl.ALL_IDS),
        "empty": set(),
        "var": {v},
        "var_list": {v, 0},
        "var2": {v, w},
        "cur": {cp},
        "cur_mix": {cp, 1},
        "ally": al(0),
        "team": {0} | al(0),
        "ally_hum": al(1) | hum,
        "ally_two": al(0) | al(2),
        "mix_all": {v, cp} | set(OBS) | al(0) | {4},
    }
    for i, sub in enumerate(RANDOM_SETS):
        table["rnd%d" % i] = set(sub)
    return table[key]


def contains_targets(v, w):
    out = {
        "p1": P1,
        "p8": P8,
        "ob1": 128,
        "p9": P9,
        "p12": P12,
        "obs": pl.Observers,
        "hum": pl.Humans,
        "every": pl.Everyone,
        "all": pl.All,
        "allp": AllPlayers,
        "f1": pl.Force(1),
        "f2": Force2,
        "f4": pl.Force(4),
        "range": [P2, P3, P4],
        "range_obs": [P8, pl.Observers],
        "obs_head": [128, 129],
        "mask": [P1, P3, 130],
        "pair": (3, 5),
        "list_all": list(pl.ALL_IDS),
        "empty": [],
        "var": v,
        "var_list": [v, P1],
        "var2": pl.Targets(v, w),
        "cur": CurrentPlayer,
        "cur_mix": [CurrentPlayer, P2],
        "ally": pl.Allies(P1),
        "team": pl.Targets(P1, pl.Allies(P1)),
        "ally_hum": [pl.Allies(P2), pl.Humans],
        "ally_two": pl.Allies(P1) | pl.Allies(P3),
        "mix_all": [v, CurrentPlayer, pl.Observers, pl.Allies(P1), P5],
    }
    for i, sub in enumerate(RANDOM_SETS):
        out["rnd%d" % i] = list(sub)
    return out


CONTAINS_KEYS = list(contains_targets(0, 1))


# ---------------------------------------------------------------------------------------------
# 이 PC 번호별 시험 (관전자 슬롯 포함)
# ---------------------------------------------------------------------------------------------


def build_local_cases(s, local, py):
    @s.case("contains")
    def _(t):
        v, w, cpv = t.var("v"), t.var("w"), t.var("cp")
        f_setcurpl(cpv)
        n0 = GetTriggerCounter()
        for key, tg in contains_targets(v, w).items():
            t.flag(key, pl.contains_user(tg))
        py.setdefault("contains_triggers", GetTriggerCounter() - n0)
        t.watch("rawcp", CP)
        t.watch("cache", _compat.cpcache_var().getValueAddr())

    @s.case("const_calls")
    def _(t):
        # 상수 대상의 로컬 판정은 호출 자리 트리거 0
        n0 = GetTriggerCounter()
        conds = [pl.contains_user(x) for x in (P1, pl.Everyone, pl.Observers, [P2, P3], pl.Humans, [P1, 130])]
        py["const_call_triggers"] = GetTriggerCounter() - n0
        for i, c in enumerate(conds):
            t.flag("c%d" % i, c)

    @s.case("userbit")
    def _(t):
        cell = pl._user_bit_cell()
        t.watch("bit", cell.getValueAddr())
        t.out("userp", f_getuserplayerid())

    @s.case("show")
    def _(t):
        pl.display(pl.Everyone, "\x04every")
        pl.run_as([P2, pl.Observers], DisplayText("p2obs"))
        pl.play_wav(pl.Humans, "sound\\glue\\bnet.wav")


def run_local_checks(s, local, py):
    ok_const = py.get("const_call_triggers") == 0
    s.expect_true("const_calls", ok_const, "호출 자리 0", "트리거 %r" % py.get("const_call_triggers"))
    r = s.run("const_calls", fresh=True)
    want = [local == 0, local in HUMAN_TABLE or local in OBS, local in OBS, local in (1, 2), local in HUMAN_TABLE, local in (0, 130)]
    for i, wv in enumerate(want):
        s.expect_true("const_calls", r.values.get("c%d" % i) == int(wv), "c%d" % i, "값 %r 기대 %r" % (r.values.get("c%d" % i), wv))

    s.check("userbit", {}, {"bit": 1 << pl._slot(local), "userp": local}, label="이 PC 비트 (local=%d)" % local, fresh=True)

    vals = [0, 1, 2, 5, 7, 128, 131, 9, M32]
    combos = []
    for v in vals:
        combos.append((v, (v + 3) % 8, local if v % 2 else 6))
    combos += [(local, 128, 0), (130, local, 129), (0, 0, local)]
    for v, w, cpv in combos:
        exp = {key: int(local in ref_set(key, v, w, cpv, ALLY)) for key in CONTAINS_KEYS}
        exp.update({"rawcp": cpv, "cache": cpv})
        s.reset()
        set_allies(s.machine, ALLY)
        s.check("contains", {"v": v, "w": w, "cp": cpv}, exp, label="local=%d v=%d w=%d cp=%d" % (local, v, w, cpv))
    # 동맹 표를 비우면 Allies 원소는 모두 거짓
    s.reset()
    set_allies(s.machine, {})
    exp = {key: int(local in ref_set(key, 3, 4, 0, {})) for key in CONTAINS_KEYS}
    s.check("contains", {"v": 3, "w": 4, "cp": 0}, exp, label="local=%d 동맹 없음" % local)

    # 표시: 이 PC 에서 정확히 한 번 보이는가
    r, cap = run_with(s, "show")
    s.expect_true("show", r.error is None, "error", str(r.error))
    every = cps(cap)[: len(HUMAN_TABLE) + 4]
    want_every = HUMAN_TABLE + list(OBS)
    s.expect_true("show", every == want_every, "display 순서", "%r" % every)
    shown = [c for c in cps(cap)[: len(want_every)] if c == local]
    s.expect_true("show", len(shown) == (1 if local in want_every else 0), "display 한 번", "local=%d %r" % (local, shown))
    second = cps(cap)[len(want_every):]
    s.expect_true("show", second == [1] + list(OBS), "run_as 순서", "%r" % second)
    wavs = cps(cap, "wav")
    s.expect_true("show", wavs == HUMAN_TABLE, "play_wav 대상", "%r" % wavs)
    s.expect_true("show", wavs.count(local) == (1 if local in HUMAN_TABLE else 0), "play_wav 한 번", "%r" % wavs)


# ---------------------------------------------------------------------------------------------
# 주 시험 (run_as, each, is_human, PerPlayer)
# ---------------------------------------------------------------------------------------------


def _cp_watch(t):
    t.watch("rawcp", CP)
    t.watch("cache", _compat.cpcache_var().getValueAddr())


def build_main_cases(s, py):
    # --- run_as ---
    @s.case("ra_const")
    def _(t):
        f_setcurpl(t.var("c0"))
        n0 = GetTriggerCounter()
        pl.run_as([P1, P3, 2, pl.Observers, P9], DisplayText("A"))
        py["ra_const_triggers"] = GetTriggerCounter() - n0
        py["strid_A"] = EncodeString("A")
        _cp_watch(t)

    @s.case("ra_humans_state")
    def _(t):
        f_setcurpl(t.var("c0"))
        pl.run_as(pl.Humans, SetDeaths(CurrentPlayer, Add, 1, U + 0), DisplayText("B"))
        _cp_watch(t)

    @s.case("ra_humans_local")
    def _(t):
        f_setcurpl(t.var("c0"))
        n0 = GetTriggerCounter()
        pl.run_as(pl.Humans, DisplayText("C"))
        py["ra_humans_local_triggers"] = GetTriggerCounter() - n0
        _cp_watch(t)

    @s.case("ra_everyone")
    def _(t):
        f_setcurpl(t.var("c0"))
        pl.run_as(pl.Everyone, [DisplayText("D"), PlayWAV("sound\\glue\\bnet.wav")])
        _cp_watch(t)

    @s.case("ra_var")
    def _(t):
        v = t.var("v")
        f_setcurpl(t.var("c0"))
        pl.run_as([v, P2], DisplayText("E"))
        _cp_watch(t)

    @s.case("ra_var_state")
    def _(t):
        v = t.var("v")
        f_setcurpl(t.var("c0"))
        pl.run_as(v, SetDeaths(CurrentPlayer, Add, 1, U + 2))
        _cp_watch(t)

    @s.case("ra_current")
    def _(t):
        f_setcurpl(t.var("c0"))
        pl.run_as([CurrentPlayer, P8], DisplayText("F"))
        pl.run_as(CurrentPlayer, SetDeaths(CurrentPlayer, Add, 1, U + 3))
        _cp_watch(t)

    @s.case("ra_mixed")
    def _(t):
        v = t.var("v")
        f_setcurpl(t.var("c0"))
        pl.run_as([P2, v, pl.Humans, CurrentPlayer], SetDeaths(CurrentPlayer, Add, 1, U + 4), DisplayText("G"))
        _cp_watch(t)

    @s.case("ra_callable")
    def _(t):
        v = t.var("v")
        f_setcurpl(t.var("c0"))
        pl.run_as([P1, P2, v], lambda p: SetDeaths(CurrentPlayer, SetTo, p + 100, U + 5))
        _cp_watch(t)

    @s.case("ra_varfield")
    def _(t):
        x = t.var("x")
        f_setcurpl(t.var("c0"))
        pl.run_as([P1, P2, P3], SetDeaths(CurrentPlayer, SetTo, x, U + 6))
        _cp_watch(t)

    @s.case("ra_many")
    def _(t):
        f_setcurpl(t.var("c0"))
        n0 = GetTriggerCounter()
        pl.run_as(pl.All, [SetDeaths(CurrentPlayer, Add, 1, U + 7)] * 7)  # 8 × 8 + 2 > 64 → 나눔
        py["ra_many_triggers"] = GetTriggerCounter() - n0
        _cp_watch(t)

    @s.case("ra_allies")
    def _(t):
        f_setcurpl(t.var("c0"))
        pl.run_as(pl.Allies(P1), SetDeaths(CurrentPlayer, Add, 1, U + 8))
        pl.run_as(pl.Targets(P1, pl.Allies(P1)), DisplayText("H"))
        pl.run_as([pl.Humans, pl.Allies(P1)], SetDeaths(CurrentPlayer, Add, 1, U + 9))
        _cp_watch(t)

    @s.case("ra_force")
    def _(t):
        f_setcurpl(t.var("c0"))
        pl.run_as([pl.Force(1), Force3], DisplayText("I"))
        pl.run_as(AllPlayers, PlayWAV("sound\\glue\\bnet.wav"))
        _cp_watch(t)

    @s.case("ra_empty")
    def _(t):
        f_setcurpl(t.var("c0"))
        n0 = GetTriggerCounter()
        pl.run_as([], DisplayText("J"))
        pl.run_as(pl.Force(4), DisplayText("J"))
        pl.run_as(pl.Everyone)  # 액션 없음
        pl.run_as([P1, pl.Humans], lambda p: [])
        py["ra_empty_triggers"] = GetTriggerCounter() - n0
        _cp_watch(t)

    @s.case("ra_display")
    def _(t):
        f_setcurpl(t.var("c0"))
        pl.display([P3, 131], "\x04a", "b")
        py["strid_ab"] = EncodeString("\x04ab")
        pl.play_wav(P8, "sound\\glue\\bnet.wav")
        _cp_watch(t)

    @s.case("ra_nocache")
    def _(t):
        # 원시 CP 쓰기로 캐시가 낡은 상태: run_as 는 캐시 값으로 되돌린다 (eudplib 규약)
        f_setcurpl(3)
        DoActions(SetMemory(CP, SetTo, 5))
        pl.run_as(P1, DisplayText("K"))
        _cp_watch(t)

    # --- each ---
    def each_record(t, p, key="n"):
        n = t.var(key)
        ok = t.var(key + "_cpok")
        n += 1
        if EUDIf()([Memory(CP, Exactly, p), _compat.cpcache_var().Exactly(p)]):
            ok += 1
        EUDEndIf()
        DoActions(DisplayText("each"))

    @s.case("each_humans")
    def _(t):
        f_setcurpl(t.var("c0"))
        with pl.each(pl.Humans) as p:
            each_record(t, p)
        _cp_watch(t)

    @s.case("each_const_for")
    def _(t):
        f_setcurpl(t.var("c0"))
        for p in pl.each([P3, P1, 1, P2]):
            each_record(t, p)
        _cp_watch(t)

    @s.case("each_obs")
    def _(t):
        f_setcurpl(t.var("c0"))
        with pl.each(pl.Everyone, observers=True) as p:
            each_record(t, p)
        _cp_watch(t)

    @s.case("each_var")
    def _(t):
        v, w = t.var("v"), t.var("w")
        f_setcurpl(t.var("c0"))
        with pl.each([v, w, v]) as p:
            each_record(t, p)
        _cp_watch(t)

    @s.case("each_current")
    def _(t):
        f_setcurpl(t.var("c0"))
        with pl.each([P8, CurrentPlayer]) as p:
            each_record(t, p)
        _cp_watch(t)

    @s.case("each_break")
    def _(t):
        f_setcurpl(t.var("c0"))
        with pl.each(pl.All) as p:
            if EUDIf()(p == 2):
                EUDContinue()
            EUDEndIf()
            if EUDIf()(p == 5):
                EUDBreak()
            EUDEndIf()
            each_record(t, p)
        _cp_watch(t)

    @s.case("each_nested")
    def _(t):
        f_setcurpl(t.var("c0"))
        back = t.var("back")
        with pl.each([P1, P2]) as p:
            with pl.each([P3, P4]) as q:
                each_record(t, q)
            if EUDIf()([Memory(CP, Exactly, p), _compat.cpcache_var().Exactly(p)]):
                back += 1
            EUDEndIf()
        _cp_watch(t)

    @s.case("each_empty")
    def _(t):
        f_setcurpl(t.var("c0"))
        with pl.each(pl.Force(4)) as p:
            each_record(t, p)
        with pl.each([]) as p:
            each_record(t, p, "m")
        _cp_watch(t)

    @s.case("each_allies")
    def _(t):
        f_setcurpl(t.var("c0"))
        with pl.each([pl.Allies(P1), pl.Allies(P3), P2]) as p:
            each_record(t, p)
        _cp_watch(t)

    @s.case("each_readfn")
    def _(t):
        f_setcurpl(t.var("c0"))
        with pl.each([P2, P5]) as p:
            f_dwread_epd(EPD(DEATH0))  # 끝에서 CP 를 캐시 값으로 되돌리는 eudplib 함수
            each_record(t, p)
        _cp_watch(t)

    @s.case("each_nocache")
    def _(t):
        # 원시 CP 쓰기로 캐시가 낡은 상태: each 는 캐시 값으로 되돌리고, CurrentPlayer 원소도 캐시 값
        f_setcurpl(3)
        DoActions(SetMemory(CP, SetTo, 5))
        with pl.each([CurrentPlayer, P1]) as p:
            each_record(t, p)
        _cp_watch(t)

    @s.case("each_sum")
    def _(t):
        gold = pl.PerPlayer(EUDVariable)
        for k, g in enumerate(gold):
            t.watch("g%d" % k, g.getValueAddr())
        f_setcurpl(t.var("c0"))
        with pl.each(pl.All) as p:
            gold.iadditem(p, p)
            gold.iadditem(p, 10)
        _cp_watch(t)

    # --- 사람 판정 ---
    @s.case("human")
    def _(t):
        v = t.var("v")
        for i in range(8):
            t.flag("h%d" % i, pl.is_human(i))
        t.flag("hp3", pl.is_human(P3))
        t.flag("hv", pl.is_human(v))
        t.flag("htp", pl.is_human(TrgPlayer.cast(v)))
        t.out("mask", pl.human_mask())

    # --- PerPlayer ---
    @s.case("pp_const")
    def _(t):
        a = t.var("a")
        pp = pl.PerPlayer(EUDVariable, count=10)
        for k, g in enumerate(pp):
            t.watch("e%d" % k, g.getValueAddr())
        pp[0] += a
        pp[P2] << a
        pp.set(3, 99)
        pp.isubitem(4, a)
        pp.iadditem(P8, 5)
        pp[5] = a
        t.out("r", pp.get(3))

    @s.case("pp_var")
    def _(t):
        a, v, w, u = t.var("a"), t.var("v"), t.var("w"), t.var("u")
        pp = pl.PerPlayer(EUDVariable, count=10)
        for k, g in enumerate(pp):
            t.watch("e%d" % k, g.getValueAddr())
        pp.iadditem(v, a)
        pp.isubitem(w, a)
        pp.set(u, a)
        t.out("r", pp.get(v))

    @s.case("pp_light")
    def _(t):
        a, v = t.var("a"), t.var("v")
        pp = pl.PerPlayer(EUDLightVariable, count=3)
        for k, g in enumerate(pp):
            t.watch("e%d" % k, g.getValueAddr())
        pp.isubitem(v, a)  # wrap (EUDLightVariable 의 eudplib -= 는 포화)
        pp.iadditem(P1, 1)

    @s.case("pp_byplayer")
    def _(t):
        pp = pl.PerPlayer(lambda p, k: EUDVariable(p * k), 3, count=12, by_player=True)
        for k, g in enumerate(pp):
            t.watch("e%d" % k, g.getValueAddr())
        py["pp_len"] = len(pp)

    # --- 컴파일 시점 오류 (빌드 안에서 검사) ---
    @s.case("py_errors")
    def _(t):
        v = t.var("v")

        def expect(label, fn):
            try:
                fn()
            except EudextError as e:
                py.setdefault("errors", {})[label] = str(e)
            else:
                py.setdefault("errors", {})[label] = None

        expect("obs_state", lambda: pl.run_as(pl.Observers, SetResources(CurrentPlayer, Add, 1, "Ore")))
        expect("every_state", lambda: pl.run_as(pl.Everyone, SetDeaths(CurrentPlayer, Add, 1, U + 0)))
        expect("cp_write", lambda: pl.run_as(P1, SetMemory(CP, SetTo, 3)))
        expect("not_action", lambda: pl.run_as(P1, 5))
        expect("each_obs", lambda: pl.each(pl.Everyone).__enter__())
        expect("each_p9", lambda: pl.each([P9]).__enter__())
        expect("bad_str", lambda: pl.contains_user("P1"))
        expect("bad_12", lambda: pl.contains_user(12))
        expect("bad_light", lambda: pl.contains_user(EUDLightVariable()))
        expect("bad_none", lambda: pl.run_as(None, DisplayText("x")))
        expect("allies_var", lambda: pl.Allies(v))
        expect("allies_8", lambda: pl.Allies(8))
        expect("force_0", lambda: pl.Force(0))
        expect("force_5", lambda: pl.Force(5))
        expect("is_human_8", lambda: pl.is_human(P9))
        expect("pp_var_getitem", lambda: pl.PerPlayer(EUDVariable)[v])
        expect("pp_range", lambda: pl.PerPlayer(EUDVariable)[8])
        expect("pp_light_get", lambda: pl.PerPlayer(EUDLightVariable).get(v))
        expect("pp_count", lambda: pl.PerPlayer(EUDVariable, count=0))
        expect("obs_ok_setdeaths_p1", lambda: pl.run_as(pl.Observers, SetDeaths(P1, Add, 1, U)))
        each_obj = pl.each([P1])
        with each_obj as _p:
            pass
        expect("each_twice", lambda: each_obj.__enter__())
        try:
            import eudext.display  # noqa: F401
            py["has_display"] = True
        except ModuleNotFoundError:
            py["has_display"] = False
            expect("display_var", lambda: pl.display(P1, "x", v))
            expect("display_kw", lambda: pl.display(P1, "x", sound="a.wav"))


def run_main_checks(s, py):
    c0s = (0, 6, 128)
    base_types = list(TYPES)

    def cp_ok(name, r, c0, label):
        s.expect_true(name, r.error is None, label + " err", str(r.error))
        s.expect_true(name, r.values.get("rawcp") == c0 and r.values.get("cache") == c0, label + " CP 복구",
                      "rawcp=%r cache=%r 기대 %d" % (r.values.get("rawcp"), r.values.get("cache"), c0))

    # ra_const: 한 트리거, 중복 제거, 오름차순, P9 → 128
    s.expect_true("ra_const", py.get("ra_const_triggers") == 1, "호출 자리 1", "%r" % py.get("ra_const_triggers"))
    for c0 in c0s:
        r, cap = run_with(s, "ra_const", {"c0": c0})
        cp_ok("ra_const", r, c0, "c0=%d" % c0)
        s.expect_true("ra_const", cps(cap) == [0, 2] + list(OBS), "대상 c0=%d" % c0, "%r" % cps(cap))
        s.expect_true("ra_const", all(c[2] == py["strid_A"] for c in cap), "문자열", "%r" % cap)

    # ra_humans_state: 지금 사람인 슬롯만 (형 바이트)
    for absent in ((), (3,), (0, 6, 7), tuple(HUMAN_TABLE)):
        types = list(base_types)
        for p in absent:
            types[p] = "closed"

        def prep(m, types=types):
            for p, k in enumerate(types):
                set_type(m, p, k)

        for c0 in (1, 128):
            r, cap = run_with(s, "ra_humans_state", {"c0": c0}, prep)
            cp_ok("ra_humans_state", r, c0, "absent=%r" % (absent,))
            want = present_humans(types)
            got = [p for p in range(8) if deaths(s.machine, p, U + 0) == 1]
            s.expect_true("ra_humans_state", got == want, "SetDeaths absent=%r" % (absent,), "%r 기대 %r" % (got, want))
            s.expect_true("ra_humans_state", cps(cap) == want, "DisplayText absent=%r" % (absent,), "%r" % cps(cap))

    # ra_humans_local: 표시 전용이면 존재 판정 없이 한 트리거
    s.expect_true("ra_humans_local", py.get("ra_humans_local_triggers") == 1, "호출 자리 1", "%r" % py.get("ra_humans_local_triggers"))

    def absent3(m):
        set_type(m, 3, "closed")

    for c0 in c0s:
        r, cap = run_with(s, "ra_humans_local", {"c0": c0}, absent3)
        cp_ok("ra_humans_local", r, c0, "c0=%d" % c0)
        s.expect_true("ra_humans_local", cps(cap) == HUMAN_TABLE, "대상", "%r" % cps(cap))

    # ra_everyone
    r, cap = run_with(s, "ra_everyone", {"c0": 4})
    cp_ok("ra_everyone", r, 4, "c0=4")
    want = HUMAN_TABLE + list(OBS)
    s.expect_true("ra_everyone", cps(cap) == want and cps(cap, "wav") == want, "대상", "%r" % cap)
    s.expect_true("ra_everyone", [c[0] for c in cap] == ["text", "wav"] * len(want), "액션 순서", "%r" % cap)

    # ra_var / ra_var_state
    for v in (0, 1, 5, 7, 128, 131):
        for c0 in (2, 129):
            r, cap = run_with(s, "ra_var", {"v": v, "c0": c0})
            cp_ok("ra_var", r, c0, "v=%d c0=%d" % (v, c0))
            s.expect_true("ra_var", cps(cap) == [v, 1], "v=%d" % v, "%r" % cps(cap))
    for v in range(8):
        r, cap = run_with(s, "ra_var_state", {"v": v, "c0": 6})
        cp_ok("ra_var_state", r, 6, "v=%d" % v)
        got = [p for p in range(8) if deaths(s.machine, p, U + 2)]
        s.expect_true("ra_var_state", got == [v], "v=%d" % v, "%r" % got)

    # ra_current
    for c0 in (0, 3, 7):
        r, cap = run_with(s, "ra_current", {"c0": c0})
        cp_ok("ra_current", r, c0, "c0=%d" % c0)
        s.expect_true("ra_current", cps(cap) == [c0, 7], "대상 c0=%d" % c0, "%r" % cps(cap))
        got = [p for p in range(8) if deaths(s.machine, p, U + 3)]
        s.expect_true("ra_current", got == [c0], "현재 플레이어 c0=%d" % c0, "%r" % got)

    # ra_mixed: 순서 = CurrentPlayer → 조건부(Humans, 번호순) → 변수 → 상수
    for v, c0 in ((1, 5), (4, 0), (2, 2)):
        types = list(base_types)
        types[4] = "closed"

        def prep(m, types=types):
            for p, k in enumerate(types):
                set_type(m, p, k)

        r, cap = run_with(s, "ra_mixed", {"v": v, "c0": c0}, prep)
        cp_ok("ra_mixed", r, c0, "v=%d c0=%d" % (v, c0))
        hum = [p for p in present_humans(types) if p != 1]  # P2(1) 은 상수 원소
        want = [c0] + hum + [v, 1]
        s.expect_true("ra_mixed", cps(cap) == want, "순서 v=%d c0=%d" % (v, c0), "%r 기대 %r" % (cps(cap), want))
        cnt = {p: deaths(s.machine, p, U + 4) for p in range(8)}
        wantc = {p: want.count(p) for p in range(8)}
        s.expect_true("ra_mixed", cnt == wantc, "SetDeaths 횟수 v=%d" % v, "%r 기대 %r" % (cnt, wantc))

    # ra_callable: 원소마다 새 액션 (변수 원소는 변수 값)
    for v in (3, 6):
        r, _cap = run_with(s, "ra_callable", {"v": v, "c0": 7})
        cp_ok("ra_callable", r, 7, "v=%d" % v)
        got = {p: deaths(s.machine, p, U + 5) for p in (0, 1, v)}
        s.expect_true("ra_callable", got == {0: 100, 1: 101, v: v + 100}, "v=%d" % v, "%r" % got)

    # ra_varfield: 액션의 변수 필드는 복사본마다 패치
    for x in (0, 7, 0x12345678, M32):
        r, _cap = run_with(s, "ra_varfield", {"x": x, "c0": 128})
        cp_ok("ra_varfield", r, 128, "x=0x%X" % x)
        got = [deaths(s.machine, p, U + 6) for p in range(4)]
        s.expect_true("ra_varfield", got == [x, x, x, 0], "x=0x%X" % x, "%r" % got)

    # ra_many: 액션 64개 초과 → 트리거 둘
    s.expect_true("ra_many", py.get("ra_many_triggers") == 2, "호출 자리 2", "%r" % py.get("ra_many_triggers"))
    r, _cap = run_with(s, "ra_many", {"c0": 5})
    cp_ok("ra_many", r, 5, "c0=5")
    got = [deaths(s.machine, p, U + 7) for p in range(8)]
    s.expect_true("ra_many", got == [7] * 8, "SetDeaths", "%r" % got)

    # ra_allies: 런타임 동맹 표 (자기 칸 제외)
    for table in (ALLY, {0: {0, 1, 7}}, {}):

        def prep(m, table=table):
            set_allies(m, table)
            set_type(m, 3, "closed")

        r, cap = run_with(s, "ra_allies", {"c0": 2}, prep)
        cp_ok("ra_allies", r, 2, "table=%r" % (table,))
        al = sorted(q for q in table.get(0, ()) if q != 0)
        got8 = [p for p in range(8) if deaths(s.machine, p, U + 8)]
        s.expect_true("ra_allies", got8 == al, "Allies state %r" % (table,), "%r" % got8)
        s.expect_true("ra_allies", cps(cap) == al + [0], "Allies text %r" % (table,), "%r" % cps(cap))
        hum = [p for p in HUMAN_TABLE if p != 3]
        want9 = sorted(set(hum) | set(al))
        got9 = [p for p in range(8) if deaths(s.machine, p, U + 9)]
        s.expect_true("ra_allies", got9 == want9, "Humans|Allies %r" % (table,), "%r 기대 %r" % (got9, want9))

    # ra_force (set_table 표)
    r, cap = run_with(s, "ra_force", {"c0": 0})
    cp_ok("ra_force", r, 0, "c0=0")
    s.expect_true("ra_force", cps(cap) == [0, 2, 3, 4], "Force1|Force3", "%r" % cps(cap))
    s.expect_true("ra_force", cps(cap, "wav") == list(range(8)), "AllPlayers", "%r" % cps(cap, "wav"))

    # ra_empty
    s.expect_true("ra_empty", py.get("ra_empty_triggers") == 0, "빈 대상 트리거 0", "%r" % py.get("ra_empty_triggers"))
    r, cap = run_with(s, "ra_empty", {"c0": 3})
    cp_ok("ra_empty", r, 3, "c0=3")
    s.expect_true("ra_empty", cap == [], "캡처 없음", "%r" % cap)

    # ra_display (display 임시 경로 또는 WP6)
    r, cap = run_with(s, "ra_display", {"c0": 1})
    cp_ok("ra_display", r, 1, "c0=1")
    s.expect_true("ra_display", cps(cap) == [2, 131], "display 대상", "%r" % cps(cap))
    if not py.get("has_display"):
        s.expect_true("ra_display", all(c[2] == py["strid_ab"] for c in cap if c[0] == "text"), "display 문자열", "%r" % cap)
    s.expect_true("ra_display", cps(cap, "wav") == [7], "play_wav", "%r" % cps(cap, "wav"))

    # ra_nocache: 들어올 때 CP(5) 가 캐시(3)와 달라도 캐시 값으로 되돌린다
    r, cap = run_with(s, "ra_nocache")
    s.expect_true("ra_nocache", r.values.get("rawcp") == 3 and r.values.get("cache") == 3, "캐시 값으로", "%r" % r.values)
    s.expect_true("ra_nocache", cps(cap) == [0], "대상", "%r" % cps(cap))

    # --- each ---
    def each_ok(name, r, cap, want, c0, label, key="n"):
        cp_ok(name, r, c0, label)
        s.expect_true(name, cps(cap) == want, label + " 순서", "%r 기대 %r" % (cps(cap), want))
        s.expect_true(name, r.values.get(key) == len(want) and r.values.get(key + "_cpok") == len(want),
                      label + " 본문 CP", "n=%r cpok=%r 기대 %d" % (r.values.get(key), r.values.get(key + "_cpok"), len(want)))

    # each_humans: 사이클마다 존재가 바뀌어도 자기 next 되돌리기가 맞는지 (메모리를 되돌리지 않고 이어서)
    s.reset()
    m = s.machine
    seq = [(), (3,), (0, 7), tuple(HUMAN_TABLE), (), (2, 4, 6)]
    total = 0
    for i, absent in enumerate(seq):
        types = list(base_types)
        for p in absent:
            types[p] = "closed"
        for p, k in enumerate(types):
            set_type(m, p, k)
        m.captured.clear()
        c0 = (5, 128, 0)[i % 3]
        r = s.run("each_humans", {"c0": c0, "n": 0, "n_cpok": 0})
        want = present_humans(types)
        total += 1
        each_ok("each_humans", r, list(m.captured), want, c0, "cycle %d absent=%r" % (i, absent))
    s.reset()

    for c0 in (0, 7, 131):
        r, cap = run_with(s, "each_const_for", {"c0": c0})
        each_ok("each_const_for", r, cap, [0, 1, 2], c0, "c0=%d" % c0)

    def closed2(m):
        set_type(m, 2, "closed")

    r, cap = run_with(s, "each_obs", {"c0": 1}, closed2)
    each_ok("each_obs", r, cap, [p for p in HUMAN_TABLE if p != 2] + list(OBS), 1, "observers=True")

    for v, w in ((1, 4), (6, 6), (128, 0)):
        r, cap = run_with(s, "each_var", {"v": v, "w": w, "c0": 3})
        each_ok("each_var", r, cap, [v, w], 3, "v=%d w=%d" % (v, w))

    for c0 in (0, 4, 129):
        r, cap = run_with(s, "each_current", {"c0": c0})
        each_ok("each_current", r, cap, [c0, 7], c0, "c0=%d" % c0)

    for c0 in (6, 130):
        r, cap = run_with(s, "each_break", {"c0": c0})
        each_ok("each_break", r, cap, [0, 1, 3, 4], c0, "break/continue c0=%d" % c0)

    r, cap = run_with(s, "each_nested", {"c0": 5})
    each_ok("each_nested", r, cap, [2, 3, 2, 3], 5, "nested")
    s.expect_true("each_nested", r.values.get("back") == 2, "안쪽 뒤 바깥 CP", "%r" % r.values.get("back"))

    r, cap = run_with(s, "each_empty", {"c0": 2})
    each_ok("each_empty", r, cap, [], 2, "empty")
    s.expect_true("each_empty", r.values.get("m") == 0, "빈 목록", "%r" % r.values.get("m"))

    for table in (ALLY, {0: {6}, 2: {1, 3}}, {}):
        r, cap = run_with(s, "each_allies", {"c0": 0}, lambda m, table=table: set_allies(m, table))
        want = sorted({q for q in table.get(0, ()) if q != 0} | {q for q in table.get(2, ()) if q != 2} | {1})
        each_ok("each_allies", r, cap, want, 0, "allies %r" % (table,))

    r, cap = run_with(s, "each_readfn", {"c0": 128})
    each_ok("each_readfn", r, cap, [1, 4], 128, "f_dwread_epd 안")

    r, cap = run_with(s, "each_nocache")
    each_ok("each_nocache", r, cap, [3, 0], 3, "낡은 캐시")

    r, _cap = run_with(s, "each_sum", {"c0": 7})
    cp_ok("each_sum", r, 7, "c0=7")
    got = [r.values.get("g%d" % k) for k in range(8)]
    s.expect_true("each_sum", got == [k + 10 for k in range(8)], "PerPlayer 변수 번호", "%r" % got)

    # --- 사람 판정 ---
    for types in (base_types, ["closed"] * 8, ["human"] * 8, ["computer", "human", "open", "rescue", "neutral", "human", "unused", "inactive"]):

        def prep(m, types=types):
            for p, k in enumerate(types):
                set_type(m, p, k)

        mask = sum(1 << p for p, k in enumerate(types) if k == "human")
        for v in (0, 1, 3, 5, 7, 8, 128, M32):
            r, _cap = run_with(s, "human", {"v": v}, prep)
            exp = {"h%d" % i: int(types[i] == "human") for i in range(8)}
            exp.update({"hp3": int(types[2] == "human"), "mask": mask})
            hv = int(v < 8 and types[v] == "human")
            exp.update({"hv": hv, "htp": hv})
            bad = {k: (r.values.get(k), x) for k, x in exp.items() if r.values.get(k) != x}
            s.expect_true("human", r.error is None and not bad, "types=%r v=%d" % (types, v), "%r %r" % (r.error, bad))

    # --- PerPlayer ---
    for a in (0, 5, M32):
        exp = {"e%d" % k: 0 for k in range(10)}
        exp.update({"e0": a, "e1": a, "e3": 99, "e4": (-a) & M32, "e7": 5, "e5": a, "r": 99})
        s.check("pp_const", {"a": a}, exp, fresh=True, label="a=0x%X" % a)
    for a, v, w, u in ((3, 1, 2, 3), (7, 4, 4, 4), (1, 9, 9, 9), (2, 0, M32, 8), (M32, 5, 5, 0)):
        e = [0] * 10
        if v < 10:
            e[v] = (e[v] + a) & M32
        if w < 10:
            e[w] = (e[w] - a) & M32
        if u < 10:
            e[u] = a
        rv = e[v] if v < 10 else 0
        exp = {"e%d" % k: e[k] for k in range(10)}
        exp["r"] = rv
        s.check("pp_var", {"a": a, "v": v, "w": w, "u": u}, exp, fresh=True, label="a=%d v=%d w=%d u=%d" % (a, v, w, u))
    for a, v in ((1, 0), (5, 2), (3, 3)):
        e = [0, 0, 0]
        if v < 3:
            e[v] = (-a) & M32
        e[0] = (e[0] + 1) & M32
        s.check("pp_light", {"a": a, "v": v}, {"e0": e[0], "e1": e[1], "e2": e[2]}, fresh=True, label="a=%d v=%d" % (a, v))
    s.check("pp_byplayer", {}, {"e%d" % k: 3 * k for k in range(12)}, fresh=True)
    s.expect_true("pp_byplayer", py.get("pp_len") == 12, "len", "%r" % py.get("pp_len"))

    # --- 컴파일 시점 오류 ---
    errs = py.get("errors", {})
    must_fail = [
        "obs_state", "every_state", "cp_write", "not_action", "each_obs", "each_p9", "bad_str", "bad_12", "bad_light",
        "bad_none", "allies_var", "allies_8", "force_0", "force_5", "is_human_8", "pp_var_getitem", "pp_range",
        "pp_light_get", "pp_count", "each_twice",
    ]
    if not py.get("has_display"):
        must_fail += ["display_var", "display_kw"]
    for k in must_fail:
        s.expect_true("py_errors", errs.get(k) is not None, k, "오류가 나지 않음")
    s.expect_true("py_errors", errs.get("obs_ok_setdeaths_p1", "x") is None, "관전자 + SetDeaths(P1)", str(errs.get("obs_ok_setdeaths_p1")))
    s.expect_true("py_errors", "관전자" in (errs.get("obs_state") or ""), "한국어 안내", str(errs.get("obs_state")))


# ---------------------------------------------------------------------------------------------
# 맵 정보(set_table 없음) 시험
# ---------------------------------------------------------------------------------------------


def build_map_cases(s, py):
    @s.case("mapinfo")
    def _(t):
        py["humans"] = pl.humans()
        py["f1"] = pl.force_members(1)
        py["f2"] = pl.force_members(2)
        py["f3"] = pl.force_members(3)
        pl.run_as(pl.Humans, DisplayText("M"))
        pl.run_as(Force2, PlayWAV("sound\\glue\\bnet.wav"))
        t.flag("cu", pl.contains_user(pl.Everyone))


def run_map_checks(s, py):
    s.expect_true("mapinfo", py.get("humans") == [0], "humans()", "%r" % py.get("humans"))
    s.expect_true("mapinfo", (py.get("f1"), py.get("f2"), py.get("f3")) == ([0], [1], []), "force_members", "%r" % py)
    r, cap = run_with(s, "mapinfo")
    s.expect_true("mapinfo", cps(cap) == [0] and cps(cap, "wav") == [1], "대상", "%r" % cap)
    s.expect_true("mapinfo", r.values.get("cu") == 1, "Everyone 에 이 PC(P1)", "%r" % r.values)


# ---------------------------------------------------------------------------------------------
# 파이썬 쪽 판정 (빌드 없이)
# ---------------------------------------------------------------------------------------------


def python_checks(ck):
    ck.eq("aliases", (pl.run_as, pl.contains_user, pl.each, pl.display, pl.play_wav, pl.is_human, pl.human_mask, pl.humans,
                      pl.set_table, pl.force_members),
          (pl.f_run_as, pl.f_contains_user, pl.f_each, pl.f_display, pl.f_play_wav, pl.f_is_human, pl.f_human_mask,
           pl.f_humans, pl.f_set_table, pl.f_force_members))
    ck.eq("humans table", pl.humans(), HUMAN_TABLE)
    ck.eq("force table", [pl.force_members(n) for n in (1, 2, 3, 4)], FORCES)
    ck.raises("set_table humans 8", EudextError, pl.set_table, humans=[8])
    ck.raises("set_table forces dup", EudextError, pl.set_table, forces=[[0], [0]])
    ck.raises("set_table forces 5", EudextError, pl.set_table, forces=[[], [], [], [], []])
    ck.eq("table kept after errors", (pl.humans(), pl.force_members(1)), (HUMAN_TABLE, [0, 2]))
    pl.set_table(humans=[P3, 1, 1], forces=([P1], (2, 3)))
    ck.eq("set_table normalize", (pl.humans(), pl.force_members(1), pl.force_members(2), pl.force_members(4)), ([1, 2], [0], [2, 3], []))
    pl.set_table(humans=HUMAN_TABLE, forces=FORCES)
    ck.raises("Targets iter", EudextError, list, pl.Humans)
    ck.eq("Targets repr", repr(pl.Targets(P1, 129, pl.Force(2), CurrentPlayer)), "Targets(P1, Ob2, Force(2), Current)")
    ck.eq("Everyone repr", repr(pl.Everyone), "Targets(Humans, Ob1, Ob2, Ob3, Ob4)")
    ck.eq("or", repr(pl.Humans | [P2]), "Targets(Humans, P2)")
    ck.eq("ror", repr([P2] | pl.Observers), "Targets(P2, Ob1, Ob2, Ob3, Ob4)")
    r = pl._resolve([P9, P12, 10, 128, P1, pl.Force(2), pl.Humans])
    ck.eq("resolve const", sorted(r.const), [0, 1, 128, 130, 131])
    ck.eq("resolve cond", sorted(r.cond), [2, 3, 4, 6, 7])
    r.drop_presence()
    ck.eq("drop_presence", (sorted(r.const), r.cond), ([0, 1, 2, 3, 4, 6, 7, 128, 130, 131], {}))
    from eudplib import FlattenList

    fl = FlattenList([pl.Humans, [P1, pl.Observers]])
    ck.true("FlattenList keeps Targets", fl[0] is pl.Humans and fl[2] is pl.Observers and len(fl) == 3, repr(fl))
    ck.eq("slot", [pl._slot(p) for p in pl.ALL_IDS], list(range(12)))
    # 마스크 구간 계획: 12개 번호의 모든 부분집합에서 참조와 같은가
    from eudplib import AtLeast, AtMost

    bad, counts = 0, {}
    ids = pl.ALL_IDS
    for bits in range(1, 1 << 12):
        sub = {ids[i] for i in range(12) if bits >> i & 1}
        plan = pl._masked_plan(sub)
        counts[None if plan is None else len(plan)] = counts.get(None if plan is None else len(plan), 0) + 1
        if plan is None:
            continue
        for u in ids:
            ok = True
            for m, cmp, val in plan:
                x = u & m
                ok &= (x == val) if cmp is Exactly else (x >= val) if cmp is AtLeast else (x <= val) if cmp is AtMost else False
            bad += ok != (u in sub)
    ck.eq("masked plan all subsets", bad, 0)
    ck.true("masked plan coverage", counts.get(1, 0) > 70 and counts.get(None, 0) > 0, repr(counts))
    ck.eq("masked plan everyone(0~6)", pl._masked_plan(list(range(7)) + list(OBS)), [(7, AtMost, 6)])
    ck.eq("masked plan obs head", pl._masked_plan([128, 129]), [(130, Exactly, 128)])
    ck.eq("masked plan none", pl._masked_plan(HUMAN_TABLE + list(OBS)), None)


# ---------------------------------------------------------------------------------------------
# epScript 예제: 번역·단독 빌드·euddraft 빌드
# ---------------------------------------------------------------------------------------------

EX = os.path.join(_common.PKG, "examples")


def example_checks(ck):
    from eudext.tools import build

    with open(os.path.join(EX, "players_example.eps"), encoding="utf-8") as f:
        src = f.read()
    out, nerr = _compat.eps_compile("players_example.eps", src)
    ck.eq("eps errors", nerr, 0)
    ck.true("eps translated", out is not None and "pl.f_each(" in out and "pl.f_run_as(" in out and "pl.f_contains_user(" in out,
            (out or "")[:400])
    work = os.path.join(_common.WORK, "t_players")
    sa = os.path.join(work, "standalone")
    os.makedirs(sa, exist_ok=True)
    for n in ("players_plugin.py", "players_example.eps"):
        shutil.copy2(os.path.join(EX, n), os.path.join(sa, n))
    pl.set_table()  # 예제는 맵 정보로
    try:
        o = build.standalone([os.path.join(sa, "players_plugin.py"), os.path.join(sa, "players_example.eps")],
                             out=os.path.join(sa, "players_sa.scx"))
        ck.true("standalone build", os.path.getsize(o) > 10000, o)
    finally:
        pl.set_table(humans=HUMAN_TABLE, forces=FORCES)
    if os.path.isfile(build.EUDDRAFT):
        ed = os.path.join(work, "euddraft")
        eds, out_map = build.prepare_eds(os.path.join(EX, "players_example.eds"), ed)
        r = build.run_euddraft(eds, out_map=out_map, log_path=os.path.join(ed, "players_example.log"))
        print("  " + r.summary())
        ck.true("euddraft ok", r.ok, r.log[-2000:])
        ck.true("euddraft eps", '[epScript] Compiling "players_example.eps"' in r.log, "")
        ck.true("euddraft py plugin", "[players_plugin.py] humans=" in r.log, r.log[-1500:])
    else:
        print("  euddraft 없음: %s — 건너뜀" % build.EUDDRAFT)


# ---------------------------------------------------------------------------------------------
# 비용 측정 항목 (tools/cost.py)
# ---------------------------------------------------------------------------------------------


def _cost_each(targets, observers=False):
    def build(t):
        with pl.each(targets, observers=observers) as _p:
            pass

    return build


def _cost_user_bit(t):
    pl._user_bit_cell()
    pl._init_user_bit()


def _cost_pp_get(t):
    pp = pl.PerPlayer(EUDVariable)
    pp.get(t.var("v"))


def _cost_pp_add(t):
    pp = pl.PerPlayer(EUDVariable)
    pp.iadditem(t.var("v"), 1)


def _cost_is_human_var(t):
    t.flag("f", pl.is_human(t.var("v")))


COST_CASES = [
    CostCase("run_as 상수 3명 DisplayText", lambda t: pl.run_as([P1, P2, P3], DisplayText("c")), target={"call": 1}),
    CostCase("run_as Everyone DisplayText (사람 6 + 관전자 4)", lambda t: pl.run_as(pl.Everyone, DisplayText("c")),
             target={"call": 1}, note="표시 전용 → 존재 판정 생략"),
    CostCase("run_as Humans SetDeaths (조건부 6명)", lambda t: pl.run_as(pl.Humans, SetDeaths(CurrentPlayer, Add, 1, 0)),
             note="시험 메모리: P1 만 사람"),
    CostCase("run_as 변수 1명 DisplayText", lambda t: pl.run_as(t.var("v"), DisplayText("c")), {"v": 1}),
    CostCase("run_as CurrentPlayer 만", lambda t: pl.run_as(CurrentPlayer, SetDeaths(CurrentPlayer, Add, 1, 0))),
    CostCase("run_as All × 액션 7 (트리거 나눔)", lambda t: pl.run_as(pl.All, [SetDeaths(CurrentPlayer, Add, 1, 0)] * 7)),
    CostCase("play_wav Everyone", lambda t: pl.play_wav(pl.Everyone, "sound\\glue\\bnet.wav"), target={"call": 1}),
    CostCase("contains_user 한 명", lambda t: t.flag("f", pl.contains_user(P1)),
             note="EUDIf 분기 포함"),
    CostCase("contains_user 구간(관전자)", lambda t: t.flag("f", pl.contains_user(pl.Observers)), note="EUDIf 분기 포함"),
    CostCase("contains_user 마스크 구간(사람 0~6 + 관전자)", lambda t: t.flag("f", pl.contains_user(list(range(7)) + [pl.Observers])),
             note="EUDIf 분기 포함, `(번호 & 7) ≤ 6` 한 조건"),
    CostCase("contains_user 비트 마스크(Everyone, 사람 0·2·3·4·6·7)", lambda t: t.flag("f", pl.contains_user(pl.Everyone)),
             note="EUDIf 분기 포함, 시작 초기화 별도"),
    CostCase("contains_user 섞임(변수+관전자+CurrentPlayer)",
             lambda t: t.flag("f", pl.contains_user([t.var("v"), pl.Observers, CurrentPlayer])), note="EUDIf 분기 포함"),
    CostCase("참고: EUDIf 분기만 (t.flag)", lambda t: t.flag("f", t.var("a").Exactly(1)), note="위 네 줄에서 뺄 값"),
    CostCase("시작 초기화: 이 PC 비트 (1회)", _cost_user_bit, note="게임 시작 때 한 번, contains_user 마스크형이 쓸 때만"),
    CostCase("each 상수 1명 (빈 본문)", _cost_each([P1]), note="고정분 + 원소 1"),
    CostCase("each 상수 4명 (빈 본문)", _cost_each([P1, P2, P3, P4])),
    CostCase("each Humans 6명 (빈 본문, 조건부)", _cost_each(pl.Humans), note="시험 메모리: P1 만 사람"),
    CostCase("each 변수 1명 (빈 본문)", lambda t: _cost_each([t.var("v")])(t), {"v": 2}),
    CostCase("is_human 상수", lambda t: t.flag("f", pl.is_human(3)), note="EUDIf 분기 포함"),
    CostCase("is_human 변수", _cost_is_human_var, {"v": 0}, funcs=[pl._is_human_var], note="EUDIf 분기 포함"),
    CostCase("human_mask", lambda t: pl.human_mask(), funcs=[pl._human_mask]),
    CostCase("PerPlayer.get 변수 번호", _cost_pp_get, [{"v": 0}, {"v": 7}]),
    CostCase("PerPlayer.iadditem 변수 번호", _cost_pp_add, [{"v": 0}, {"v": 7}]),
]


def main():
    ck = Checker("t_players (python)")
    oks = []

    # 주 시험
    py = {}
    s = Suite("t_players main", memory=local_memory(0))
    build_main_cases(s, py)
    s.build()
    install_capture(s.machine)
    run_main_checks(s, py)
    oks.append(s.report())

    # 이 PC 번호별 (관전자 128~131 포함)
    for local in LOCALS:
        pyl = {}
        sl = Suite("t_players local=%d" % local, memory=local_memory(local), verbose=False)
        build_local_cases(sl, local, pyl)
        sl.build()
        install_capture(sl.machine)
        run_local_checks(sl, local, pyl)
        oks.append(sl.report())

    # 맵 정보
    pl.set_table()
    pym = {}
    sm = Suite("t_players mapinfo", memory={"local_player": 0, "players": ["human", "computer"]})
    build_map_cases(sm, pym)
    sm.build()
    install_capture(sm.machine)
    run_map_checks(sm, pym)
    oks.append(sm.report())
    pl.set_table(humans=HUMAN_TABLE, forces=FORCES)

    python_checks(ck)
    example_checks(ck)
    oks.append(ck.report())
    finish(*oks)


if __name__ == "__main__":
    main()
