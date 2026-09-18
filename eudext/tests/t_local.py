"""`local` 시험: 키 표(CtrigAsm·MSQC·NSQC 대조), 로컬 조건(키·마우스·채팅 중·관전자), 엣지 캐시와 update(),
구역(only/begin/end/allow), 좌표 읽기, 로컬 플레이어, 토글·추적기, 표식 경고·strict, 늦은 등록 오류.

python tests/t_local.py
비용 표: python tools/cost.py tests/t_local.py [--append --bytes]

에뮬레이터에서 로컬 메모리(0x596A18 키 표, 0x6CDDC0 버튼, 0x68C144 채팅, 0x512684 로컬 플레이어, 화면·마우스 좌표)를
사이클 사이에 바꿔 가며 확인한다.
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import ast  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import warnings  # noqa: E402

from eudplib import (  # noqa: E402
    CurrentPlayer,
    DoActions,
    EUDEndIf,
    EUDIf,
    EUDVariable,
    Exactly,
    MemoryX,
    RawTrigger,
    SetMemory,
    SetTo,
    f_setcurpl,
)

from eudext import _compat, local  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing.harness import Suite  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
REPO = _common.ROOT
CA_LUA = os.path.join(REPO, "reference", "MapSource", "Library", "CtrigAsm v5.5.lua")
MSQC_PY = os.path.join(REPO, ".tools", "euddraft0.11.0.1", "plugins", "MSQC.py")
NSQC_PY = os.path.join(REPO, "reference", "euddraft-0.9.10.11-plugins", "NSQC.py")
KEY = local.KEY_STATE_ADDR

ck = Checker("t_local (python)")


# =============================================================================================
# 1. 키 표 대조
# =============================================================================================


def ctrig_table():
    text = open(CA_LUA, encoding="utf-8", errors="replace").read()
    i = text.index("function ParseKeyName(KeyName)")
    body = text[i : text.index("}", i)]
    out = []
    for m in re.finditer(r"\[(?:'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\")\]\s*=\s*(0x[0-9A-Fa-f]+)", body):
        name = m.group(1) if m.group(1) is not None else m.group(2)
        out.append((name.encode().decode("unicode_escape"), int(m.group(3), 16)))
    return out


def plugin_table(path):
    text = open(path, encoding="utf-8").read()
    i = text.index("KeyCodeDict = {")
    j = text.index("}", i)
    return list(ast.literal_eval(text[i + len("KeyCodeDict = ") : j + 1]).items())


def section_tables():
    ca = ctrig_table()
    ck.eq("CtrigAsm 표 크기", len(ca), 196)
    ck.eq("CtrigAsm = local 표", ca, list(local._KEY_TABLE))
    for path, label in ((MSQC_PY, "MSQC 0.11"), (NSQC_PY, "NSQC 0.9.10.11")):
        ck.eq("%s = local 표" % label, plugin_table(path), list(local._KEY_TABLE))
    ck.eq("NSQC 표기 역슬래시", local.key_code("\\"), 0xDC)
    ck.eq("파이프", local.key_code("|"), 0xDC)
    ck.eq("MSQC 이름 0xDC", local.msqc_key_name("\\"), "|")
    ck.eq("MSQC 이름 =", local.msqc_key_name(0xBB), "=")
    ck.eq("소문자", local.key_code("numpad*"), 0x6A)
    ck.eq("정수", local.key_code(0x41), 0x41)
    ck.eq("공백 제거", local.key_code(" f12 "), 0x7B)
    for bad in ("", "NOPE", 256, -1, True, None, 1.5):
        ck.raises("key_code %r" % (bad,), EudextError, local.key_code, bad)
    ck.raises("msqc 이름 없음", EudextError, local.msqc_key_name, 0x07)
    ck.eq("buttons", [local.button_bit(b) for b in ("l", "LEFT", "r", "Right", "m", "MIDDLE")], [2, 2, 8, 8, 32, 32])
    ck.eq("button names", [local.button_name(b) for b in ("left", "RIGHT", "m")], ["L", "R", "M"])
    ck.raises("button bad", EudextError, local.button_bit, "X")
    # 조건 모양·eds 표기
    c = local.key_held("X")
    ck.eq("key_held fields", c.fields, MemoryX(KEY + 0x58, Exactly, 1, 1).fields)
    ck.eq("key_held eds", (c.eds, local.key_held("X", held=False).eds, local.key_held(0x07).eds), ("KeyPress(X)", None, None))
    ck.eq("key_held r=3", local.key_held("W").fields, MemoryX(KEY + 0x57 - 3, Exactly, 1 << 24, 1 << 24).fields)
    ck.eq("edge eds", (local.key_pressed("A").eds, local.key_released("\\").eds), ("KeyDown(A)", "KeyUp(|)"))
    ck.eq("mouse eds", (local.mouse_held("r").eds, local.mouse_pressed("L").eds, local.mouse_released("M").eds),
          ("MousePress(R)", "MouseDown(L)", "MouseUp(M)"))
    ck.eq("typing eds", (local.typing().eds, local.not_typing().eds), ("0x68C144, AtLeast, 1", "NotTyping"))
    ck.eq("observer eds", local.is_observer().eds, "0x512684, AtLeast, 128; 0x512684, AtMost, 131")
    ck.true("markers", local.is_local(c) and local.is_local(local.is_observer()) and local.is_local(local.LocalValue())
            and not local.is_local(EUDVariable()))
    ck.true("LocalValue cond", isinstance(local.LocalValue().Exactly(3), local.LocalCondition))
    ck.raises("only bad player", EudextError, local.begin, 12)
    ck.raises("only bad player 132", EudextError, local.begin, 132)
    ck.raises("end without begin", EudextError, local.end)
    ck.raises("toggle guard type", EudextError, local.key_toggle, "Q", guard=5)
    ck.eq("strict toggle", (local.strict(True), local.strict(False)), (False, True))


# =============================================================================================
# 2. 에뮬레이터
# =============================================================================================

ALL_CODES = sorted(set(local.KEYS.values()))


def build_cases(s, order):
    @s.case("held_all")
    def _(t):
        with local.allow():
            for code in ALL_CODES:
                t.flag("k%02X" % code, local.key_held(code))
            t.flag("x_up", local.key_held("X", held=False))

    @s.case("edges")
    def _(t):
        with local.allow():
            for k in ("X", "SPACE", "\\", "F24"):
                c = local.key_code(k)
                t.flag("p%02X" % c, local.key_pressed(k))
                t.flag("r%02X" % c, local.key_released(k))
            for b in ("L", "R", "M"):
                t.flag("mp" + b, local.mouse_pressed(b))
                t.flag("mr" + b, local.mouse_released(b))
                t.flag("mh" + b, local.mouse_held(b))
            local.update()

    @s.case("update_first")
    def _(t):
        # watch_keys 로 미리 등록한 키(Z, section_emu)는 update() 뒤에 처음 써도 된다 (이번 사이클 엣지는 못 본다)
        with local.allow():
            local.update()
            t.flag("pz", local.key_pressed("Z"))

    @s.case("typing")
    def _(t):
        with local.allow():
            t.flag("ty", local.typing())
            t.flag("nt", local.not_typing())
            t.flag("ob", local.is_observer())

    @s.case("only")
    def _(t):
        pv = t.var("pv")
        for p in (0, 3, 7, 11, 128, 131):
            v = t.var("c%d" % p)
            DoActions(v.SetNumber(0))
            with local.only(p):
                DoActions(v.SetNumber(1))
        vv = t.var("vv")
        DoActions(vv.SetNumber(0))
        with local.only(pv):
            DoActions(vv.SetNumber(1))
        vc = t.var("vc")
        DoActions(vc.SetNumber(0))
        f_setcurpl(t.var("cp"))
        local.begin(CurrentPlayer)
        DoActions(vc.SetNumber(1))
        local.end()
        nested = t.var("nest")
        DoActions(nested.SetNumber(0))
        local.begin()
        local.begin(pv)
        DoActions(nested.AddNumber(1))
        local.end()
        DoActions(nested.AddNumber(2))
        local.end()
        f_setcurpl(0)

    @s.case("coords")
    def _(t):
        with local.allow():
            x, y = local.mouse_map_xy()
            t.out("mx", x)
            t.out("my", y)
            sx, sy = local.screen_xy()
            t.out("sx", sx)
            t.out("sy", sy)
            a, b = t.var("ix"), t.var("iy")
            r = local.mouse_screen_xy(into=(a, b))
            t.out("same", 1 if (r[0] is a and r[1] is b) else 0)

    @s.case("player")
    def _(t):
        with local.allow():
            t.out("pl", local.player())
            t.out("pl2", local.player())

    @s.case("toggle")
    def _(t):
        with local.allow():
            t.out("tg", tg_holder["tg"])
            t.out("tx", tr_holder["mouse"].x)
            t.out("ty", tr_holder["mouse"].y)
            t.out("ux", tr_holder["screen"].x)
            local.update()

    # 표식 경고 (구역 밖) — 빌드 때 경고, 실행에는 영향 없음
    @s.case("warn_cond")
    def _(t):
        t.flag("w", local.key_held("Q"))

    @s.case("warn_value")
    def _(t):
        lv = local.LocalValue()
        shared = t.var("shared")
        shared << lv

    @s.case("no_warn")
    def _(t):
        lv = local.LocalValue()
        shared = t.var("shared")
        with local.only(0):
            shared << lv
            t.flag("f", local.key_held("Q"))
        with local.allow():
            t.out("sum", lv + 1)

    @s.case("strict")
    def _(t):
        old = local.strict(True)
        try:
            RawTrigger(conditions=local.key_held("E"))
        except EudextError as e:
            expected_errors["strict"] = str(e)
        finally:
            local.strict(old)

    @s.case("late_key")
    def _(t):
        # 같은 빌드에서 update() 를 낸 뒤(앞 케이스들) 처음 쓰는 키 → 오류
        try:
            local.key_pressed("K")
        except EudextError as e:
            expected_errors["late"] = str(e)
        try:
            local.track_screen()  # 이미 있는 추적기는 괜찮다
            expected_errors["tracker_ok"] = True
        except EudextError:
            expected_errors["tracker_ok"] = False

    order.extend(["held_all", "edges", "update_first", "typing", "only", "coords", "player", "toggle"])


tg_holder = {}
tr_holder = {}
expected_errors = {}


def set_keys(m, state):
    for code in ALL_CODES:
        m.setdb(KEY + code, state.get(code, 0))


def section_emu():
    tg_holder["tg"] = local.key_toggle("TAB", guard=local.not_typing())
    tr_holder["mouse"] = local.track_mouse()
    tr_holder["screen"] = local.track_screen()
    ck.true("tracker shared", local.track_mouse() is tr_holder["mouse"])
    local.watch_keys("Z")
    local.watch_buttons("L")
    s = Suite("t_local", memory={"local_player": 3})
    order = []
    build_cases(s, order)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s.build()
    msgs = [str(x.message) for x in w]
    s.expect_true("warn_cond", any("로컬 조건(LocalCondition)" in x and "t_local.py" in x for x in msgs), "warning", "; ".join(msgs))
    s.expect_true("warn_value", any("로컬 값(LocalValue)" in x for x in msgs), "warning", "; ".join(msgs))
    s.expect_true("no_warn", s.cases["no_warn"].build_error is None, "built")
    s.expect_true("no_warn", sum("로컬" in x for x in msgs) == 2, "only two warnings", "; ".join(msgs))
    s.expect_true("strict", "로컬 조건" in expected_errors.get("strict", ""), "strict error", str(expected_errors))
    s.expect_true("late_key", "update() 를 낸 뒤" in expected_errors.get("late", ""), "late error", str(expected_errors))
    s.expect_true("late_key", expected_errors.get("tracker_ok") is True, "existing tracker ok")
    m = s.machine
    rng = random.Random(5)

    # --- held_all: 모든 키 한 개씩 + 무작위 모양 ---
    for code in ALL_CODES:
        set_keys(m, {code: 1})
        r = s.run("held_all")
        want = {("k%02X" % c): int(c == code) for c in ALL_CODES}
        bad = [k for k, v in want.items() if r.values[k] != v]
        s.expect_true("held_all", not bad and r.values["x_up"] == int(code != 0x58), "one 0x%02X" % code, str(bad[:4]))
    for i in range(30):
        state = {c: rng.choice((0, 0, 1)) for c in ALL_CODES}
        set_keys(m, state)
        r = s.run("held_all")
        bad = [c for c in ALL_CODES if r.values["k%02X" % c] != state[c]]
        s.expect_true("held_all", not bad, "random %d" % i, str(bad[:4]))
    set_keys(m, {})

    # --- edges: 키·버튼 무작위 순서, 참조 = 이번 상태 ∧ ¬지난 update 때 상태 ---
    keys = [0x58, 0x20, 0xDC, 0x87]
    prev = {c: 0 for c in keys}
    prevb = {b: 0 for b in (2, 8, 32)}
    for i in range(200):
        state = {c: rng.choice((0, 1)) if rng.random() < 0.5 else prev[c] for c in keys}
        set_keys(m, state)
        bits = rng.getrandbits(8) & 0xFF
        m.setdw(local.MOUSE_BUTTON_ADDR, bits | (rng.getrandbits(8) << 8))
        r = s.run("edges")
        bad = []
        for c in keys:
            wp, wr = int(state[c] and not prev[c]), int(not state[c] and prev[c])
            if (r.values["p%02X" % c], r.values["r%02X" % c]) != (wp, wr):
                bad.append("0x%02X %s" % (c, (r.values["p%02X" % c], r.values["r%02X" % c], wp, wr)))
            prev[c] = state[c]
        for name, bit in (("L", 2), ("R", 8), ("M", 32)):
            now = int(bool(bits & bit))
            wp, wr = int(now and not prevb[bit]), int(not now and prevb[bit])
            got = (r.values["mp" + name], r.values["mr" + name], r.values["mh" + name])
            if got != (wp, wr, now):
                bad.append("%s %s" % (name, (got, (wp, wr, now))))
            prevb[bit] = now
        if not s.expect_true("edges", not bad, "step %d" % i, "; ".join(bad)):
            break
    set_keys(m, {})
    m.setdw(local.MOUSE_BUTTON_ADDR, 0)

    # --- update_first: update 가 앞이면 엣지는 보이지 않는다 ---
    m.setdb(KEY + 0x5A, 1)
    r1 = s.run("update_first")
    m.setdb(KEY + 0x5A, 0)
    s.run("update_first")
    s.expect_true("update_first", r1.values["pz"] == 0, "no edge after update")

    # --- typing / observer ---
    for chat in (0, 1, 5, 0x80000000, M32):
        m.setdw(local.CHAT_TARGET_ADDR, chat)
        s.check("typing", {}, {"ty": int(chat != 0), "nt": int(chat == 0)}, label="chat %X" % chat)
    m.setdw(local.CHAT_TARGET_ADDR, 0)
    for lp in (0, 3, 7, 11, 12, 127, 128, 129, 131, 132, 0x80, 0xFFFFFFFF):
        m.setdw(local.LOCAL_PLAYER_ADDR, lp)
        s.check("typing", {}, {"ob": int(128 <= lp <= 131)}, label="observer %d" % lp)

    # --- only ---
    for lp in (0, 3, 7, 11, 128, 131, 5):
        m.setdw(local.LOCAL_PLAYER_ADDR, lp)
        for pv in (0, 3, 131, 5):
            want = {"c%d" % p: int(p == lp) for p in (0, 3, 7, 11, 128, 131)}
            want.update({"vv": int(pv == lp), "nest": 2 + int(pv == lp)})
            s.check("only", {"pv": pv, "cp": 3}, want, label="lp %d pv %d" % (lp, pv))
    # CurrentPlayer(IsUserCP)는 시작 때 읽은 로컬 번호(3)와 CP 를 비교한다
    for cp in (0, 3, 7):
        s.check("only", {"pv": 0, "cp": cp}, {"vc": int(cp == 3)}, label="IsUserCP cp %d" % cp)
    m.setdw(local.LOCAL_PLAYER_ADDR, 3)

    # --- coords ---
    def ref(sx, sy, mx, my):
        sx, sy, mx, my = sx & 0x1FFF, sy & 0x1FFF, mx & 0x7FF, my & 0x3FF
        return {"mx": sx + mx, "my": sy + my, "sx": sx, "sy": sy, "ix": mx, "iy": my, "same": 1}

    vals = [(0, 0, 0, 0), (8191, 8191, 2047, 1023), (1, 2, 3, 4), (M32, M32, M32, M32), (0x12345, 0x6789A, 0xBCDE, 0xF012)]
    vals += [tuple(rng.getrandbits(r) for r in (13, 13, 11, 10)) for _ in range(40)]
    for sx, sy, mx, my in vals:
        m.setdw(local.SCREEN_X_ADDR, sx)
        m.setdw(local.SCREEN_Y_ADDR, sy)
        m.setdw(local.MOUSE_X_ADDR, mx)
        m.setdw(local.MOUSE_Y_ADDR, my)
        s.check("coords", {}, ref(sx, sy, mx, my), label="coords %X %X %X %X" % (sx, sy, mx, my))

    # --- player ---
    s.check("player", {}, {"pl": 3, "pl2": 3}, label="local player")

    # --- toggle + trackers ---
    tg = 0
    last_tab = 0
    for i in range(60):
        tab = rng.choice((0, 1))
        chat = 1 if rng.random() < 0.2 else 0
        m.setdb(KEY + 0x09, tab)
        m.setdw(local.CHAT_TARGET_ADDR, chat)
        sx, sy, mx, my = rng.getrandbits(13), rng.getrandbits(13), rng.getrandbits(11), rng.getrandbits(10)
        m.setdw(local.SCREEN_X_ADDR, sx)
        m.setdw(local.SCREEN_Y_ADDR, sy)
        m.setdw(local.MOUSE_X_ADDR, mx)
        m.setdw(local.MOUSE_Y_ADDR, my)
        r = s.run("toggle")
        # 출력은 update 앞에서 읽으므로 이전 사이클의 update 결과다
        want = {"tg": tg}
        got_tg = r.values["tg"]
        if tab and not last_tab and not chat:
            tg ^= 1
        last_tab = tab
        ok = got_tg == want["tg"]
        if i > 0:
            ok = ok and (r.values["tx"], r.values["ty"], r.values["ux"]) == prev_xy
        prev_xy = (sx + mx, sy + my, sx)
        if not s.expect_true("toggle", ok, "step %d" % i, "%r %r" % (r.values, want)):
            break
    m.setdw(local.CHAT_TARGET_ADDR, 0)
    return s


# =============================================================================================
# 3. 자동 update(훅) 모드
# =============================================================================================


def section_auto():
    local.set_auto_update(True)
    try:
        s = Suite("t_local_auto", verbose=False)

        @s.case("auto")
        def _(t):
            with local.allow():
                local.update()  # 훅 모드: 아무것도 내지 않는다
                t.flag("p", local.key_pressed("Y"))
                local._emit_update_from_hook()

        s.build()
        m = s.machine
        m.setdb(KEY + 0x59, 1)
        r1 = s.run("auto")
        r2 = s.run("auto")
        ck.eq("auto edge once", (r1.values["p"], r2.values["p"]), (1, 0))
        ck.true("auto built", s.cases["auto"].build_error is None, str(s.cases["auto"].build_error))
    finally:
        local.set_auto_update(False)


# =============================================================================================
# 비용
# =============================================================================================


def _if(cond):
    EUDIf()(cond)
    EUDEndIf()


def _cost_update_one(t):
    local.watch_keys("V")
    with local.allow():
        local._emit_update()


def _cost_only_const(t):
    with local.only(1):
        DoActions(SetMemory(0x58A364 + 4 * 300, SetTo, 1))


def _cost_only_var(t):
    with local.only(t.var("p")):
        DoActions(SetMemory(0x58A364 + 4 * 300, SetTo, 1))


def _allow(fn):
    def build(t):
        with local.allow():
            fn(t)

    return build


COST_CASES = [
    CostCase("key_held + if", _allow(lambda t: _if(local.key_held("X")))),
    CostCase("key_pressed + if (조건 2)", _allow(lambda t: _if(local.key_pressed("X")))),
    CostCase("mouse_held + if", _allow(lambda t: _if(local.mouse_held("L")))),
    CostCase("not_typing + if", _allow(lambda t: _if(local.not_typing()))),
    CostCase("is_observer + if", _allow(lambda t: _if(local.is_observer()))),
    CostCase("only(상수 p) + 액션 1", _cost_only_const, note="이 PC 가 아닐 때~맞을 때"),
    CostCase("only(변수 p) + 액션 1", _cost_only_var, [{"p": 0}, {"p": 5}]),
    CostCase("update() — 등록 키 2개(X, V)", _cost_update_one, note="키·버튼마다 2, 토글마다 2, 추적기마다 mouse_map_xy 1회"),
    CostCase("mouse_map_xy()", _allow(lambda t: local.mouse_map_xy())),
    CostCase("screen_xy()", _allow(lambda t: local.screen_xy())),
    CostCase("player() 읽기", _allow(lambda t: t.out("p", local.player())), note="시작 코드 별도"),
]


def section_example():
    """examples/local_example.py 단독 빌드 (경고 없이)."""
    import shutil

    from eudext.tools import build

    work = os.path.join(_common.WORK, "t_local", "example")
    os.makedirs(work, exist_ok=True)
    src = os.path.join(_common.PKG, "examples", "local_example.py")
    dst = os.path.join(work, "local_example.py")
    shutil.copy2(src, dst)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        out = build.standalone([dst], out=os.path.join(work, "local_example.scx"))
    msgs = [str(x.message) for x in w if "로컬" in str(x.message)]
    ck.true("example standalone", os.path.getsize(out) > 10000, out)
    ck.eq("example no local warning", msgs, [])


def main():
    section_tables()
    s = section_emu()
    ok1 = s.report()
    section_auto()
    section_example()
    ok2 = ck.report()
    finish(ok1, ok2)


if __name__ == "__main__":
    main()
