"""`sync` 시험: 선언 → eds 조각, 플러그인 파서 수용, 수신 펄스 주입(에뮬레이터), MSQC 수신 코드 실행,
epScript 예제 번역·선언 수집·euddraft 빌드(MSQC/NSQC), 선언과 eds 불일치 검출.

python tests/t_sync.py
비용 표: python tools/cost.py tests/t_sync.py [--append --bytes]

수신 주입 모델(`RecvModel`)·참조 모델(`RefState`)·턴 모델(`TurnSim`)·가짜 QC 유닛(`QCUnits`)·OWNR 바꾸기는
`eudext/testing/syncmodel.py` 에 있다(WP18 에서 이 파일로부터 옮김 — 설명은 그 모듈 docstring).
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import ast  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import types  # noqa: E402
import warnings  # noqa: E402

from eudplib import (  # noqa: E402
    AtLeast,
    CurrentPlayer,
    EUDArray,
    EUDVariable,
    Exactly,
    GetEUDNamespace,
    LoadMap,
    f_setcurpl,
)

from eudext import _compat, local, sync  # noqa: E402
from eudext.errors import EudextError  # noqa: E402
from eudext.testing import emu, scmodel, syncmodel  # noqa: E402
from eudext.testing.syncmodel import (  # noqa: E402
    QCUnits,
    RecvModel,
    RefState,
    TurnSim,
    load_plugin,
    set_humans,
    settings_of,
)
from eudext.testing.harness import BASE_MAP, Suite  # noqa: E402
from eudext.tools import build as tbuild  # noqa: E402
from eudext.tools import edsgen  # noqa: E402
from eudext.tools.cost import CostCase  # noqa: E402

M32 = 0xFFFFFFFF
REPO = _common.ROOT
MSQC_PY = os.path.join(REPO, ".tools", "euddraft0.11.0.1", "plugins", "MSQC.py")
MSQC_OLD_PY = os.path.join(REPO, "reference", "euddraft-0.9.10.11-plugins", "MSQC.py")
NSQC_PY = os.path.join(REPO, "reference", "euddraft-0.9.10.11-plugins", "NSQC.py")
WORK = os.path.join(_common.WORK, "t_sync")
os.makedirs(WORK, exist_ok=True)

ck = Checker("t_sync (python)")


# =============================================================================================
# 1. 선언 → eds 줄
# =============================================================================================


def section_declare():
    b = sync.Bus("msqc", qc_unit=49, qc_loc=3, qc_player=10, qc_xy=(64, 96), debug=False, name="decl")
    guard_flag = EUDVariable()
    lv = local.LocalValue()
    ch = [
        b.key_down("SPACE", guard=sync.not_typing(), level=True),
        b.key_down("=", guard=[local.not_typing(), local.key_held("LCTRL")]),
        b.key_up("\\", inc=4),
        b.key_press(",", guard=sync.guards(sync.memory_guard(0x58F450, "Exactly", 0), sync.raw_guard('Switch("Switch 210", Cleared)'))),
        b.key_down("semicolon", guard=local.is_observer()),
        b.key_down("numpad*", guard=sync.bit_guard(0x58F454, 0x10)),
        b.mouse_down("r", guard=sync.flag_guard(guard_flag, name="eudext_decl_flag"), level=True),
        b.mouse_up("M"),
        b.mouse_press("LEFT", guard=sync.key_held("LSHIFT")),
        b.when(sync.guards(local.not_typing(), local.mouse_held("L"))),
        b.value(lv),
        b.value(0x6CDDC4, latch=False, guard=sync.not_typing()),
        b.mouse_location(1),
    ]
    want = [
        "QCUnit : 49",
        "QCLoc : 2",
        "QCPlayer : 10",
        "QC_XY : 64, 96",
        "QCDebug : false",
        "NotTyping; KeyDown(SPACE) : eudext_decl_p1, 1",
        "KeyUp(SPACE) : eudext_decl_p2, 1",
        "NotTyping; KeyPress(LCTRL); KeyDown(\\=) : eudext_decl_p3, 1",
        "KeyUp(|) : eudext_decl_p4, 4",
        '0x58F450, Exactly, 0; Switch("Switch 210", Cleared); KeyPress(,) : eudext_decl_p5, 1',
        "0x512684, AtLeast, 128; 0x512684, AtMost, 131; KeyDown(SEMICOLON) : eudext_decl_p6, 1",
        "0x58F454, 0x10; KeyDown(NUMPAD*) : eudext_decl_p7, 1",
        "eudext_decl_flag.AtLeast(1); MouseDown(R) : eudext_decl_p8, 1",
        "MouseUp(R) : eudext_decl_p9, 1",
        "MouseUp(M) : eudext_decl_p10, 1",
        "KeyPress(LSHIFT); MousePress(L) : eudext_decl_p11, 1",
        "NotTyping; MousePress(L) : eudext_decl_p12, 1",
        "Always(); val, eudext_decl_s13 : eudext_decl_v14",
        "NotTyping; val, 0x6CDDC4 : eudext_decl_v15",
        "mouse : 1",
    ]
    ck.eq("decl lines", b.eds_lines(), want)
    frag = b.eds_fragment()
    ck.true("decl fragment head", frag.splitlines()[1] == "[MSQC]" and frag.splitlines()[0].startswith("::"), frag[:80])
    ck.eq("decl sections", sync.eds_sections([b]), {"MSQC": want})
    ns = GetEUDNamespace()
    ck.true("decl ns view", isinstance(ns["eudext_decl_p1"], EUDArray) and ns["eudext_decl_s13"] is lv)
    ck.true("decl ns flag", ns["eudext_decl_flag"] is guard_flag)
    ck.true("decl level pair", ch[0].up.key == "KeyUp(SPACE)" and ch[6].up.key == "MouseUp(R)" and ch[0].lvl is not None)
    ck.true("decl dedupe", b.key_down("SPACE", guard=sync.not_typing()) is ch[0])
    ck.true("decl dedupe level", b.key_down("SPACE", guard=sync.not_typing(), level=True) is ch[0])
    ck.true("decl up reuse", b.mouse_up("R") is ch[6].up)
    ck.raises("dup other inc", EudextError, b.key_down, "SPACE", guard=sync.not_typing(), inc=2)
    ck.raises("dup mouse", EudextError, b.mouse_location, 1)
    ck.raises("dup value addr", EudextError, b.value, 0x6CDDC4, guard=sync.not_typing())
    ck.eq("describe", b.describe((128, 128), 3).splitlines()[:3], [
        "[MSQC] 버스 decl: 펄스 12, 값 3, dword 0",
        "  QC 유닛 4×사람 (불리언 22비트/유닛), 프레임당 최대 60바이트 + 선택 복원 26",
        "  사람 3명 → QC 유닛 12마리",
    ])
    ck.true("describe qc warn", "qc_unit" in sync.Bus("msqc", name="warnq").describe())

    # 오류
    ck.raises("unknown transport", EudextError, sync.Bus, "tcp", name="e1")
    ck.raises("native not yet", EudextError, sync.Bus, "native", name="e2")
    ck.raises("same bus name", EudextError, sync.Bus, "msqc", name="decl")
    ck.raises("bad bus name", EudextError, sync.Bus, "msqc", name="a-b")
    ck.raises("qc_loc 0", EudextError, sync.Bus, "msqc", qc_loc=0, name="e3")
    ck.raises("qc_loc str", EudextError, sync.Bus, "msqc", qc_loc="Loc", name="e4")
    ck.raises("qc_dummy msqc", EudextError, sync.Bus, "msqc", qc_dummy=227, name="e5")
    e = sync.Bus("msqc", qc_unit=49, name="err")
    ck.raises("dword msqc", EudextError, e.dword, 0x6CDDC4)
    ck.raises("nsqc guard on msqc", EudextError, e.key_press, "A", guard=sync.mouse_moved())
    ck.raises("unknown key", EudextError, e.key_down, "NOPE")
    ck.raises("no msqc name", EudextError, e.key_down, 0x07)
    ck.raises("bad button", EudextError, e.mouse_down, "X")
    ck.raises("guard eudarray", EudextError, e.key_down, "A", guard=EUDArray(2))
    ck.raises("guard no eds", EudextError, e.key_down, "A", guard=local.key_held("A", held=False))
    ck.raises("guard bad type", EudextError, e.key_down, "A", guard=5)
    ck.raises("guard semicolon", EudextError, sync.Guard, "A; B")
    ck.raises("when empty", EudextError, e.when, None)
    ck.raises("value bad src", EudextError, e.value, "name")
    ck.raises("level() w/o level", EudextError, e.key_down("A").level, 0)
    ck.raises("memory_guard cmp", EudextError, sync.memory_guard, 0x58F450, "Bigger", 0)
    ck.raises("inc 0", EudextError, e.key_down, "B", inc=0)
    ck.raises("raw dup", EudextError, e.raw, "KeyDown(A)", "x, 1")
    ck.raises("pidx 8", EudextError, e.key_down("A").pulse, 8)
    ck.raises("ns clash", EudextError, sync.flag_guard, EUDVariable(), name="eudext_decl_flag")
    n = sync.Bus("nsqc", qc_unit=49, qc_dummy=230, name="nsdecl", deaths=[200, 201, 202, 203])
    ck.raises("nsqc key_down blocked", EudextError, n.key_down, "A")
    ck.raises("nsqc key_up blocked", EudextError, n.key_up, "A")
    n.key_press("A", guard=sync.guards(sync.not_typing(), sync.wide_screen()))
    n.when(sync.screen_moved())
    nd = n.dword(0x6CDDC4, error=0x12345678)
    ck.raises("nsqc val latch", EudextError, n.value, 0x6CDDC8)
    ck.raises("nsqc var source", EudextError, n.value, local.LocalValue(), latch=False)
    nv = n.value(0x6CDDC8, latch=False)
    ck.raises("nsqc deaths exhausted", EudextError, n.key_press, "B")
    ck.raises("nsqc val received", EudextError, nv.received, 0)
    ck.eq("nsqc dword out", (nd.out.unit, nd.out.addr(), nv.out.unit), (202, 0x58A364 + 4 * 202 * 12, 203))
    ck.eq("nsqc lines (QCDummy last)", n.eds_lines(), [
        "QCUnit : 49",
        "NotTyping; WideScreen; KeyPress(A) : 200, 1",
        "ScreenMoved : 201, 1",
        "Always(); dword, 0x6CDDC4 : 202, 0x12345678",
        "Always(); val, 0x6CDDC8 : 203",
        "QCDummy : 230",
    ])
    ck.raises("nsqc no deaths", EudextError, sync.Bus("nsqc", name="nsnone").key_press, "A")
    ck.raises("deaths on msqc", EudextError, sync.Bus, "msqc", name="e6", deaths=[5])
    ck.raises("deaths dummy", EudextError, sync.Bus, "nsqc", name="e7", deaths=[227])
    ck.raises("deaths zero", EudextError, sync.Bus, "nsqc", name="e8", deaths=[0])
    ck.raises("deaths dup", EudextError, sync.Bus, "nsqc", name="e9", deaths=[5, 5])
    ok_edges = sync.Bus("nsqc", name="nsfixed", allow_nsqc_key_edges=True, deaths=226)
    ck.eq("nsqc edges allowed + base", [(c.key, c.out.unit) for c in (ok_edges.key_down("A"), ok_edges.key_up("A"))],
          [("KeyDown(A)", 226), ("KeyUp(A)", 228)])

    # 설정 합치기 (같은 전송의 여러 버스)
    s1 = sync.Bus("msqc", qc_unit=49, name="m1")
    s1.key_down("F1")
    s2 = sync.Bus("msqc", qc_unit=49, debug=True, name="m2")
    s2.key_down("F2")
    merged = sync.eds_sections([s1, s2])["MSQC"]
    ck.eq("merge", merged, ["QCUnit : 49", "QCDebug : true", "KeyDown(F1) : eudext_m1_p1, 1", "KeyDown(F2) : eudext_m2_p1, 1"])
    s3 = sync.Bus("msqc", qc_unit=50, name="m3")
    ck.raises("merge conflict", EudextError, sync.eds_sections, [s1, s3])
    ck.raises("cross-bus dup", EudextError, s2.key_down, "F1")
    both = sync.eds_fragment([s1, n])
    ck.eq("fragment both", (both.count("[MSQC]"), both.count("[NSQC]")), (1, 1))
    ck.true("buses filter", s1 in sync.buses("msqc") and n in sync.buses("nsqc") and n not in sync.buses("msqc"))

    # 이스케이프 왕복
    rng = random.Random(3)
    alphabet = "ab=:\\;, ()|"
    for i in range(300):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randrange(1, 12))).strip() or "a"
        esc = sync.escape_key(text)
        if not ck.eq("escape roundtrip %d" % i, edsgen.line_key(esc + " : v"), text.strip()):
            break

    # SCR_DB 채널 (DPS build_eud.py 식과 같은 뜻)
    dps = ["Memory(0x%X,AtLeast,1);val, 0x%X: %d" % (0x58F508 + 4 * k, 0x58F508 + 4 * k, 21 + k) for k in range(8)]
    mine = sync.scrdb_msqc_lines()

    def norm(line):
        k = edsgen.line_key(line)
        return ([c.strip() for c in k.split(";")], line.rsplit(":", 1)[1].strip())

    ck.eq("scrdb lines", [norm(x) for x in mine], [norm(x) for x in dps])
    ck.eq("scrdb ch7 = IsPName slot", 0x58F508 + 4 * 7, sync.PNAME_LIGHTVAR_ADDR)
    sb = sync.Bus("msqc", qc_unit=49, name="scr")
    sb.scrdb_channels()
    ck.eq("scrdb bus", sb.eds_lines()[1:], mine)
    ck.raises("scrdb nsqc", EudextError, n.scrdb_channels)
    # 설정이 서로 다른 시험용 버스는 뒤 절(update·verify 가 모든 버스를 합친다)에 남기지 않는다
    sync._buses[:] = []
    return b, n, [s1, s2, sb]


# =============================================================================================
# 2. 플러그인 파서가 조각을 받아들이는가 (MSQC.py/NSQC.py 원문을 이 프로세스에서 실행)
# =============================================================================================


load_plugin_module = load_plugin  # testing/syncmodel (옛 플러그인의 '\g' 이스케이프 경고는 거기서 숨긴다)


def section_parser(decl, nbus, others):
    LoadMap(BASE_MAP)
    lines = sync.eds_sections([decl])["MSQC"]
    settings = settings_of(lines)
    for path, label in ((MSQC_PY, "msqc 0.11"), (MSQC_OLD_PY, "msqc 0.9.10.11")):
        try:
            m = load_plugin_module(path, "MSQC", settings)
        except Exception as e:  # noqa: BLE001
            ck.true("parse %s" % label, False, repr(e))
            continue
        finally:
            pass
        ck.eq("%s QCUnit" % label, (m.QCUnit, m.QCLoc, m.QCPlayer, m.QCX, m.QCY, m.QCDebug), (49, 2, 10, 64, 96, False))
        pulses = [c for c in decl.channels if isinstance(c, sync.Pulse)]
        ck.eq("%s qc_rets" % label, m.qc_rets, [["array", c.out.name, c.inc] for c in pulses])
        want_xy = [["val", "eudext_decl_s13", "eudext_decl_v14"], ["val", (0x6CDDC4 - 0x58A364) // 4, "eudext_decl_v15"]]
        got_xy = [r for r in m.xy_rets if r[0] == "val"]
        ck.eq("%s val rets" % label, got_xy, want_xy)
        ck.true("%s mouse" % label, m.useMouseLocation and ["mouse"] == [r[0] for r in m.xy_rets if r[0] == "mouse"])
        ck.eq("%s cons count" % label, [len(c) for c in m.qc_cons], [2, 1, 3, 1, 3, 3, 2, 2, 1, 1, 2, 2])
        ck.eq("%s key offsets" % label, sorted(m.KeyOffset), sorted([0x20, 0xBB, 0xDC, 0xBA, 0x6A]))
        ck.eq("%s mouse offsets" % label, sorted(m.MouseOffset), [8, 32])
        # verify: 설정이 선언과 같으면 통과, 다르면 오류 (플러그인 모듈을 sys.modules 에서 찾는다)
        saved = list(sync._buses)
        try:
            sync._buses[:] = [decl]
            ck.eq("%s verify ok" % label, sync.verify(force=True), ["MSQC"])
            m.settings["NotTyping; KeyDown(SPACE)"] = "eudext_decl_p1, 2"
            ck.raises("%s verify diff" % label, EudextError, sync.verify, force=True)
            m.settings["NotTyping; KeyDown(SPACE)"] = "eudext_decl_p1, 1"
            m.settings["KeyDown(X)"] = "eudext_old_p9, 1"
            ck.raises("%s verify stale" % label, EudextError, sync.verify, force=True)
            del m.settings["KeyDown(X)"]
            del m.settings["QCUnit"]
            ck.raises("%s verify missing" % label, EudextError, sync.verify, force=True)
        finally:
            sync._buses[:] = saved
            del sys.modules["MSQC"]

    # NSQC 0.9.10.11: QCDummy 를 맨 끝에 둬야 설정이 온전하다
    nl = sync.eds_sections([nbus])["NSQC"]
    nset = settings_of(nl)
    try:
        nm = load_plugin_module(NSQC_PY, "NSQC", nset)
        ck.eq("nsqc QCDummy", (nm.QCUnit, nm.QCDummy), (49, "230"))
        ck.eq("nsqc qc_rets", nm.qc_rets, [["deaths", 200, 1], ["deaths", 201, 1]])
        ck.eq("nsqc death units", sorted(nm.deathsUnits), [200, 201, 202, 203, 230])
        ck.eq("nsqc xy kinds", [r[0] for r in nm.xy_rets], ["low", "high", "val", "val"])
        ck.eq("nsqc dword err", nm.xy_rets[0][3], 0x12345678)
        ck.true("nsqc settings intact", "QCDummy" not in nm.settings and "Always(); val, 0x6CDDC8" in nm.settings, str(nm.settings))
        saved = list(sync._buses)
        try:
            sync._buses[:] = [nbus]
            ck.eq("nsqc verify ok", sync.verify(force=True), ["NSQC"])
        finally:
            sync._buses[:] = saved
        del sys.modules["NSQC"]
    except Exception as e:  # noqa: BLE001
        ck.true("nsqc parse", False, repr(e))
    finally:
        sys.modules.pop("NSQC", None)
    # QCDummy 가 끝이 아니면 NSQC 는 마지막 줄을 지우고 QCDummy 를 조건으로 읽는다 (이 모듈이 순서를 지키는 이유)
    bad = dict(nset)
    bad.pop("QCDummy")
    bad = {"QCDummy": "230", **bad}
    try:
        nm2 = load_plugin_module(NSQC_PY, "NSQC", bad)
        broken = "Always(); val, 0x6CDDC8" not in nm2.settings
    except Exception:  # noqa: BLE001
        broken = True
    finally:
        sys.modules.pop("NSQC", None)
    ck.true("nsqc QCDummy-first bug reproduced", broken)
    ck.true("plugin modules removed", "MSQC" not in sys.modules and "NSQC" not in sys.modules)


# =============================================================================================
# 3. 수신 펄스 주입 (에뮬레이터)
# =============================================================================================


def section_inject():
    players = list(range(8))
    b = sync.Bus("msqc", qc_unit=49, name="inj", players=players)
    lvx = local.LocalValue()
    jump = b.key_down("SPACE", guard=sync.not_typing(), level=True)
    fire = b.mouse_down("L", inc=3)
    mx = b.value(lvx)
    rawv = b.value(0x6CDDC4, latch=False)
    nb = sync.Bus("nsqc", name="injn", players=players, deaths=[210])
    dw = nb.dword(0x6CDDC8, error=0xDEADBEEF)
    part = sync.Bus("msqc", qc_unit=49, name="part", players=[1, 5])
    pj = part.key_down("F1", level=True)

    s = Suite("t_sync")
    arrays = {"jump": jump, "jumpup": jump.up, "fire": fire, "mx": mx, "raw": rawv, "dw": dw, "pj": pj, "pjup": pj.up}

    @s.case("consume")
    def _(t):
        for name, ch in arrays.items():
            t.watch("a_" + name, ch.out.addr())
        t.watch("l_jump", _compat.eudarray_addr(jump.lvl.arr))
        t.watch("l_mx", _compat.eudarray_addr(mx.latch.arr))
        sync.update()
        for p in players:
            t.flag("jp%d" % p, jump.pulse(p))
            t.flag("jl%d" % p, jump.level(p))
            t.flag("up%d" % p, jump.up.pulse(p))
            t.out("fc%d" % p, fire.count(p))
            t.flag("fp%d" % p, fire.pulse(p))
            t.out("mx%d" % p, mx.get(p))
            t.flag("mr%d" % p, mx.received(p))
            t.out("rv%d" % p, rawv.get(p))
            t.flag("rr%d" % p, rawv.pulse(p))
            t.out("dw%d" % p, dw.get(p))
            t.flag("dr%d" % p, dw.received(p))
            t.out("dl%d" % p, jump.level_value(p))
            t.flag("pl%d" % p, pj.level(p))
        pv = t.var("pv")
        t.flag("jpv", jump.pulse(pv))
        t.flag("jlv", jump.level(pv))
        t.out("mxv", mx.get(pv))
        t.out("fcv", fire.count(pv))
        cpv = t.var("cpv")
        f_setcurpl(cpv)
        t.flag("jpc", jump.pulse(CurrentPlayer))
        t.flag("jlc", jump.level(CurrentPlayer))
        t.out("mxc", mx.get(CurrentPlayer))

    @s.case("no_update")
    def _(t):
        t.flag("x", jump.level(0))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s.build()
    msgs = [str(x.message) for x in w]
    s.expect_true("consume", any("sync.update() 가 없습니다" in x for x in msgs) is False, "no false warning", "; ".join(msgs[:3]))
    m = s.machine
    addr = {name: m.addr("consume.a_" + name) for name in arrays}
    model = RecvModel(m, players)
    for name, ch in arrays.items():
        if name not in ("pj", "pjup"):
            model.add(ch, addr[name])
    part_model = RecvModel(m, players)
    part_model.add(pj, addr["pj"])
    part_model.add(pj.up, addr["pjup"])
    ck.eq("value idle init", [m.dw(addr["mx"] + 4 * p) for p in players], [M32] * 8)
    ck.eq("dword out = death 210", addr["dw"], 0x58A364 + 4 * 210 * 12)

    ref = RefState()
    pref = RefState()
    level_pairs = [(jump, jump.up)]
    latches = [mx, dw]

    def run_cycle(received, pv=0, cpv=0, label=""):
        model.apply(received)
        precv = {p: {c: v for c, v in r.items() if c in (pj, pj.up)} for p, r in received.items()}
        part_model.apply(precv)
        ref.step(received, level_pairs, latches, players)
        pref.step(precv, [(pj, pj.up)], [], [1, 5])
        r = s.run("consume", {"pv": pv, "cpv": cpv})
        if r.error:
            s.expect_true("consume", False, label, r.error)
            return False
        v = r.values
        bad = []
        for p in players:
            rp = received.get(p, {})
            exp = {
                "jp%d" % p: int(jump in rp),
                "up%d" % p: int(jump.up in rp),
                "jl%d" % p: ref.level.get((id(jump), p), 0),
                "dl%d" % p: ref.level.get((id(jump), p), 0),
                "fc%d" % p: 3 if fire in rp else 0,
                "fp%d" % p: int(fire in rp),
                "mx%d" % p: ref.latch.get((id(mx), p), 0),
                "mr%d" % p: int(mx in rp),
                "rv%d" % p: rp.get(rawv, M32),
                "rr%d" % p: int(rawv in rp),
                "dw%d" % p: ref.latch.get((id(dw), p), 0),
                "dr%d" % p: int(dw in rp),
                "pl%d" % p: pref.level.get((id(pj), p), 0),
            }
            for k, want in exp.items():
                if v[k] != want & M32:
                    bad.append("%s=%X(기대 %X)" % (k, v[k], want & M32))
        rpv = received.get(pv, {})
        rcp = received.get(cpv, {})
        extra = {
            "jpv": int(jump in rpv), "jlv": ref.level.get((id(jump), pv), 0), "mxv": ref.latch.get((id(mx), pv), 0),
            "fcv": 3 if fire in rpv else 0,
            "jpc": int(jump in rcp), "jlc": ref.level.get((id(jump), cpv), 0), "mxc": ref.latch.get((id(mx), cpv), 0),
        }
        for k, want in extra.items():
            if v[k] != want:
                bad.append("%s=%X(기대 %X)" % (k, v[k], want))
        return s.expect_true("consume", not bad, label, ", ".join(bad[:6]))

    # 3-1 손으로 짠 순서: Down → (유지) → Up, 같은 사이클 Down+Up, 엣지 잃음, 여러 플레이어
    seq = [
        {0: {jump: True}},
        {},
        {0: {jump.up: True}, 1: {jump: True}},
        {1: {jump: True, jump.up: True}},  # 둘 다 → 그대로(1)
        {1: {jump.up: True}},
        {2: {jump.up: True}},  # Down 을 잃고 Up 만 → 0 유지
        {2: {jump: True}, 3: {mx: 1234, fire: True}},
        {3: {mx: 0}, 7: {mx: 0x3FFFFF, dw: 0}},
        {7: {dw: 0xFFFFFFFF, rawv: 55}},
        {5: {pj: True}, 1: {pj: True}, 0: {pj: True}},  # part 버스는 1, 5 만 갱신
        {5: {pj.up: True}},
    ]
    for i, rcv in enumerate(seq):
        run_cycle(rcv, pv=i % 8, cpv=(i * 3) % 8, label="seq %d" % i)

    # 3-2 무작위 수신 (플레이어별 독립)
    rng = random.Random(7)
    chans = [jump, jump.up, fire, mx, rawv, dw, pj, pj.up]
    for i in range(160):
        rcv = {}
        for p in players:
            d = {}
            for ch in chans:
                if rng.random() < 0.3:
                    if isinstance(ch, sync.Pulse):
                        d[ch] = True
                    elif ch is dw:
                        d[ch] = rng.choice([0, 1, 0xDEADBEEE, M32, rng.getrandbits(32)])
                    else:
                        d[ch] = rng.choice([0, 1, 0x3FFFFF, rng.randrange(0x400000)])
            if d:
                rcv[p] = d
        run_cycle(rcv, pv=rng.randrange(8), cpv=rng.randrange(8), label="rand %d" % i)

    # 3-3 턴 모델: 한 턴 여러 프레임 → 마지막 값만, 같은 QC 유닛의 다른 엣지는 사라짐
    for latency, turn in ((2, 1), (2, 2), (3, 4)):
        sim = TurnSim({jump: 0, jump.up: 0, fire: 0, mx: 1, rawv: 2, dw: 3, pj: 4, pj.up: 4}, latency, turn)
        last_sent_mx = {}
        exec_last = {}
        for frame in range(60):
            for p in (0, 4, 6):
                sent = {}
                if rng.random() < 0.4:
                    sent[rng.choice([jump, jump.up, fire])] = True
                if rng.random() < 0.8:
                    sent[mx] = rng.randrange(0x400000)
                if sent:
                    sim.send(frame, p, sent)
                if mx in sent:
                    last_sent_mx[(p, frame)] = sent[mx]
            rcv = sim.execute(frame)
            for p, d in rcv.items():
                if mx in d:
                    exec_last[p] = d[mx]
            run_cycle(rcv, pv=frame % 8, cpv=0, label="turn L%d T%d f%d" % (latency, turn, frame))
        for p, v in exec_last.items():
            s.expect_true("consume", ref.latch.get((id(mx), p)) == v, "turn latch %d/%d p%d" % (latency, turn, p))

    # 3-4 update 가 없으면 경고 (level 을 쓴 케이스가 있는 빌드에서 update 를 빼 본다)
    s2 = Suite("t_sync_noupdate", verbose=False)

    @s2.case("lvl_only")
    def _(t):
        t.flag("x", jump.level(0))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        s2.build()
    ck.true("no-update warning", any("sync.update() 가 없습니다" in str(x.message) for x in w), [str(x.message) for x in w])
    return s


# =============================================================================================
# 4. MSQC.py ReceiveQC 실제 코드 + 훅 + 소비자 (에뮬레이터, 가짜 QC 유닛)
# =============================================================================================

CUNIT0 = syncmodel.CUNIT0  # 0x59CCA8
CUNIT_SIZE = syncmodel.CUNIT_SIZE  # 336


def section_msqc_e2e():
    humans = [0, 1, 3]
    LoadMap(BASE_MAP)
    set_humans(humans)
    sync._buses[:] = []  # 앞 절의 버스는 빼고 (verify·update 가 모든 버스를 본다)
    bus = sync.Bus("msqc", qc_unit=49, debug=False, name="e2e", players=humans)
    k_a = bus.key_down("A", level=True)
    k_b = bus.key_down("B", inc=5)
    val = bus.value(0x6CDDC4)
    many = [bus.key_press("F%d" % i) for i in range(1, 22)]  # 첫 유닛을 넘겨 두 번째 불리언 유닛까지
    settings = settings_of(sync.eds_sections()["MSQC"])
    m_mod = load_plugin_module(MSQC_PY, "MSQC", settings)
    ck.eq("e2e humans", m_mod.humans, humans)
    hook = types.ModuleType("eudext_sync_hook")
    hook.__dict__["settings"] = {}
    exec(compile(sync.hook_source(), "eudext_sync_hook.py", "exec"), hook.__dict__)
    outs = {}
    for p in humans:
        for name in ("ap", "al", "bc", "v"):
            outs["%s%d" % (name, p)] = EUDVariable()
        for i in range(len(many)):
            outs["f%d_%d" % (i, p)] = EUDVariable()

    def body():
        m_mod.beforeTriggerExec()
        hook.beforeTriggerExec()
        for p in humans:
            _flag(outs["ap%d" % p], k_a.pulse(p))
            _flag(outs["al%d" % p], k_a.level(p))
            outs["bc%d" % p] << k_b.count(p)
            outs["v%d" % p] << val.get(p)
            for i, ch in enumerate(many):
                _flag(outs["f%d_%d" % (i, p)], ch.pulse(p))
        hook.afterTriggerExec()
        m_mod.afterTriggerExec()

    def setup():
        m_mod.onPluginStart()
        hook.onPluginStart()

    prog = emu.Program(body, setup=setup)
    for name, var in outs.items():
        prog.watch(name, var)
    try:
        mach = prog.build()
    except Exception as e:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        ck.true("e2e build", False, repr(e))
        return
    finally:
        sys.modules.pop("MSQC", None)
        sync._hook_active = False
        local.set_auto_update(False)
    ck.true("e2e build", True)
    scmodel.install_game_memory(mach, local_player=0, players=["human" if p in humans else "computer" for p in range(8)])
    qc = QCUnits(mach, m_mod, humans)  # scmodel 유닛 모델로 QC 유닛 칸을 만든다
    mach.cycle()  # 시작 코드 + Respawn + 첫 사이클
    qccount = m_mod.QCCount
    ck.eq("e2e qccount", qccount, len(m_mod.xy_rets) + -(-len(m_mod.qc_rets) // len(m_mod.bit_xy)))
    ck.eq("e2e units created", mach.dw(0x628438), CUNIT0 + CUNIT_SIZE * qccount * len(humans))
    ck.true("e2e waypoints reset", qc.all_reset())

    def inject(hi, chans, value=None):
        qc.inject_bits(hi, [["array", ch.out.name, ch.inc] for ch in chans])
        if value is not None:
            qc.inject_value(hi, val.out.name, value)

    rng = random.Random(11)
    ref_level = {p: 0 for p in humans}
    ref_val = {p: 0 for p in humans}
    ok = True
    for cyc in range(40):
        rcv = {}
        for hi, p in enumerate(humans):
            chans = [c for c in [k_a, k_a.up, k_b] + many if rng.random() < 0.25]
            value = rng.randrange(1 << 22) if rng.random() < 0.5 else None
            if chans or value is not None:
                inject(hi, chans, value)
            rcv[p] = (set(chans), value)
            d, u = k_a in chans, k_a.up in chans
            if d and not u:
                ref_level[p] = 1
            elif u and not d:
                ref_level[p] = 0
            if value is not None:
                ref_val[p] = value
        mach.cycle()
        for p in humans:
            chans, value = rcv[p]
            got = {
                "ap": mach.var("ap%d" % p),
                "al": mach.var("al%d" % p),
                "bc": mach.var("bc%d" % p),
                "v": mach.var("v%d" % p),
                "f": [mach.var("f%d_%d" % (i, p)) for i in range(len(many))],
            }
            want = {
                "ap": int(k_a in chans), "al": ref_level[p], "bc": 5 if k_b in chans else 0, "v": ref_val[p],
                "f": [int(ch in chans) for ch in many],
            }
            if got != want:
                ok = ck.true("e2e cycle %d p%d" % (cyc, p), False, "%r != %r" % (got, want)) and ok
                break
        if not ok:
            break
        if not qc.all_reset():
            ck.true("e2e waypoint restored %d" % cyc, False)
            break
    ck.true("e2e 40 cycles", ok)
    ck.true("e2e verify ran in hook", sync._st.verified)
    unknown = dict(mach.unknown)
    print("  e2e 흉내 못 낸 조건·액션:", unknown)


def _flag(v, cond):
    from eudplib import EUDElse, EUDEndIf, EUDIf

    if EUDIf()(cond):
        v << 1
    if EUDElse()():
        v << 0
    EUDEndIf()


# =============================================================================================
# 5. epScript 예제 → 선언 수집 → eds → euddraft (MSQC / NSQC / 불일치 / QCUnit 검사)
# =============================================================================================

EXAMPLES = os.path.join(_common.PKG, "examples")


def repo_artifacts():
    found = []
    for dirpath, dirnames, filenames in os.walk(_common.PKG):
        rel = os.path.relpath(dirpath, _common.PKG)
        if rel.startswith("docs"):
            continue
        for d in dirnames:
            if d in ("__pycache__", "__epspy__"):
                found.append(os.path.join(rel, d))
        for f in filenames:
            if f.endswith((".scx", ".pyc")) and not (rel == "testing" and f == "base.scx"):
                found.append(os.path.join(rel, f))
    return found


NSQC_EPS = """// NSQC 시험 맵 (t_sync 가 만든다)
import eudext.sync as sync;
import eudext.local as local;
const bus = sync.Bus("nsqc", qc_unit=49, debug=0, name="nx", deaths=200);
const k = bus.key_press("X", guard=sync.not_typing());
const moved = bus.when(sync.mouse_moved());
const md = bus.mouse_down("L");
const dw = bus.dword(0x6CDDC4, error=0xFFFFFFFE);
const vv = bus.value(0x6CDDC8, latch=0);
const cnt = PVariable();
function beforeTriggerExec() {
    foreach(p : EUDLoopPlayer()) {
        if (k.pulse(p)) { cnt[p] += 1; }
        if (md.pulse(p) && moved.pulse(p)) { cnt[p] += 2; }
        if (dw.received(p)) { cnt[p] = dw.get(p) + vv.get(p); }
    }
}
"""

PY_DECL = """# 파이썬 선언 모듈 (t_sync 가 만든다)
from eudplib import *
from eudext import sync, local
bus = sync.Bus("msqc", qc_unit=49, name="pyx")
fire = bus.key_down("Z", guard=local.not_typing())
"""


def section_build():
    before = set(repo_artifacts())
    # 5-0 번역
    with open(os.path.join(EXAMPLES, "sync_example.eps"), encoding="utf-8") as f:
        py, nerr = _compat.eps_compile("sync_example.eps", f.read())
    ck.true("example eps translate", py is not None and nerr == 0, "errors %d" % nerr)
    ck.true("example eps f_ names", "sync.f_not_typing()" in (py or "") and "local.f_begin(CurrentPlayer)" in (py or ""))
    # 5-1 파이썬 선언 수집
    pyfile = os.path.join(WORK, "decl_mod.py")
    with open(pyfile, "w", encoding="utf-8") as f:
        f.write(PY_DECL)
    got = sync.collect(pyfile)
    ck.eq("collect py", [b.name for b in got], ["pyx"])
    ck.eq("collect py lines", got[0].eds_lines(), ["QCUnit : 49", "NotTyping; KeyDown(Z) : eudext_pyx_p1, 1"])
    ck.true("collect no module left", "decl_mod" not in sys.modules)

    if not os.path.isfile(tbuild.EUDDRAFT):
        print("  euddraft 없음 — 빌드 시험 건너뜀")
        return
    # 5-2 예제 (MSQC) — 빌드는 새 프로세스에서 (선언 수집 + eds + euddraft)
    work = os.path.join(WORK, "example")
    shutil.rmtree(work, ignore_errors=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", EUDEXT_WORK=_common.WORK)
    p = subprocess.run([sys.executable, os.path.join(EXAMPLES, "sync_build.py"), "--work", work],
                       capture_output=True, env=env, stdin=subprocess.DEVNULL, timeout=900)
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    ck.true("example build rc", p.returncode == 0, out[-3000:])
    log_path = os.path.join(work, "build", "build.log")
    log = open(log_path, encoding="utf-8").read() if os.path.isfile(log_path) else ""
    ck.true("example msqc loaded", "[MSQC] map size: 128x128, 1 men x 3 QCUnits (ID: 49)" in log, log[-1500:])
    ck.true("example hook loaded", "Loading plugin eudext_sync_hook.py" in log)
    ck.true("example no warning", "Warning" not in log and "[Error]" not in log, log[-1500:])
    eds = os.path.join(work, "src", "sync_example.eds")
    eds_text = open(eds, encoding="utf-8").read() if os.path.isfile(eds) else ""
    order = [s[0] for s in tbuild.read_eds(eds)] if eds_text else []
    ck.eq("example eds order", [os.path.basename(x) for x in order],
          ["main", "boot.py", "MSQC", "eudext_sync_hook.py", "dbg_setup.py", "sync_example.eps", "eudTurbo",
           "freeze"])
    ck.true("example hook file", os.path.isfile(os.path.join(work, "src", "eudext_sync_hook.py")))

    # 5-3 불일치: eds 의 증가량을 바꾸면 빌드 안 verify 가 멈춘다
    bad_dir = os.path.join(work, "bad")
    shutil.rmtree(bad_dir, ignore_errors=True)
    bad_src = os.path.join(work, "src_bad")
    shutil.rmtree(bad_src, ignore_errors=True)
    shutil.copytree(os.path.join(work, "src"), bad_src)
    bad_eds = os.path.join(bad_src, "sync_example.eds")
    text = open(bad_eds, encoding="utf-8").read().replace("eudext_ex_p1, 1", "eudext_ex_p1, 2")
    with open(bad_eds, "w", encoding="utf-8") as f:
        f.write(text)
    new_eds, out_map = tbuild.prepare_eds(bad_eds, bad_dir)
    r = tbuild.run_euddraft(new_eds, out_map=out_map, log_path=os.path.join(bad_dir, "build.log"))
    ck.true("mismatch fails", not r.ok and "eds 조각이 선언과 다릅니다" in r.log, r.log[-1500:])

    # 5-4 옛 조각 없음: [MSQC] 를 지우면 훅이 멈춘다
    nomsqc = re.sub(r"\[MSQC\][^\[]*", "", open(eds, encoding="utf-8").read())
    no_src = os.path.join(work, "src_nomsqc")
    shutil.rmtree(no_src, ignore_errors=True)
    shutil.copytree(os.path.join(work, "src"), no_src)
    with open(os.path.join(no_src, "sync_example.eds"), "w", encoding="utf-8") as f:
        f.write(nomsqc)
    new_eds, out_map = tbuild.prepare_eds(os.path.join(no_src, "sync_example.eds"), os.path.join(work, "nomsqc"))
    r = tbuild.run_euddraft(new_eds, out_map=out_map)
    ck.true("missing section fails", not r.ok and "[MSQC] 섹션이 없습니다" in r.log, r.log[-1500:])

    # 5-5 QCUnit 이 맵에 놓인 번호(101)면 멈춘다
    qc_src = os.path.join(work, "src_qc")
    shutil.rmtree(qc_src, ignore_errors=True)
    shutil.copytree(os.path.join(work, "src"), qc_src)
    for name in ("sync_example.eds", "sync_example.eps"):
        path = os.path.join(qc_src, name)
        t = open(path, encoding="utf-8").read()
        t = t.replace("QCUnit : 49", "QCUnit : 101").replace("qc_unit=49", "qc_unit=101")
        with open(path, "w", encoding="utf-8") as f:
            f.write(t)
    new_eds, out_map = tbuild.prepare_eds(os.path.join(qc_src, "sync_example.eds"), os.path.join(work, "qc"))
    r = tbuild.run_euddraft(new_eds, out_map=out_map)
    ck.true("qcunit placed fails", not r.ok and "QCUnit 101" in r.log, r.log[-1500:])

    # 5-6 NSQC (0.9.10.11 판을 eds 폴더에 두고 [NSQC.py] 로)
    nwork = os.path.join(WORK, "nsqc")
    shutil.rmtree(nwork, ignore_errors=True)
    os.makedirs(nwork)
    neps = os.path.join(nwork, "nsqc_map.eps")
    with open(neps, "w", encoding="utf-8") as f:
        f.write(NSQC_EPS)
    code = (
        "import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
        "import sync_build\n"
        "eds, buses = sync_build.generate(%r, source=%r, sections={'NSQC': 'NSQC.py'}, extra_plugins=[%r])\n"
        "r = sync_build.build(eds, %r)\n"
        "print(r.summary())\n"
        "sys.exit(0 if r.ok else 1)\n"
    ) % (REPO, EXAMPLES, nwork, neps, NSQC_PY, nwork)
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env, stdin=subprocess.DEVNULL, timeout=900)
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    nlog_path = os.path.join(nwork, "build", "build.log")
    nlog = open(nlog_path, encoding="utf-8").read() if os.path.isfile(nlog_path) else ""
    ck.true("nsqc build", p.returncode == 0, out[-2000:] + nlog[-2000:])
    ck.true("nsqc loaded", "[NSQC] map size: 128x128, 1 men x 5 QCUnits (ID: 49), QCDummy (UnitID: 227)" in nlog, nlog[-800:])
    # 1651/1652 = KeyUpdate/MouseUpdate (플러그인 자신의 캐시, MouseArray 는 EPD 그대로라 맞다). 출력 칸 쪽 경고는 없어야 한다
    arr_warn = [n for n in re.findall(r'NSQC\.py", line (\d+), in ReceiveQC', nlog) if n not in ("1651", "1652")]
    ck.eq("nsqc no output EPD warning", arr_warn, [])
    after = set(repo_artifacts())
    ck.eq("repo clean", sorted(after - before), [])


# =============================================================================================
# 비용 측정 항목 (tools/cost.py)
# =============================================================================================

_cost_bus = None


def _cbus():
    global _cost_bus
    if _cost_bus is None:
        _cost_bus = sync.Bus("msqc", qc_unit=49, name="cost", players=range(8))
        _cost_bus.k = _cost_bus.key_down("SPACE", level=True)
        _cost_bus.v = _cost_bus.value(0x6CDDC4)
        _cost_bus.solo = sync.Bus("msqc", qc_unit=49, name="costh", players=[0])
        _cost_bus.solo.k = _cost_bus.solo.key_down("F9", level=True)
        _cost_bus.solo.v = _cost_bus.solo.value(0x6CDDC8)
    return _cost_bus


def _if(cond):
    from eudplib import EUDEndIf, EUDIf

    EUDIf()(cond)
    EUDEndIf()


def _cost_level_update(players):
    def build(t):
        b = _cbus() if players == 8 else _cbus().solo
        b.k._emit_update(b._players())

    return build


def _cost_latch_update(players):
    def build(t):
        b = _cbus() if players == 8 else _cbus().solo
        b.v._emit_update(b._players())

    return build


COST_CASES = [
    CostCase("pulse(상수 p) 조건 + if", lambda t: _if(_cbus().k.pulse(3))),
    CostCase("pulse(변수 p) 조건 + if", lambda t: _if(_cbus().k.pulse(t.var("p"))), {"p": 2}),
    CostCase("pulse(CurrentPlayer) + if", lambda t: _if(_cbus().k.pulse(CurrentPlayer))),
    CostCase("level(상수 p) + if", lambda t: _if(_cbus().k.level(3))),
    CostCase("count(상수 p) 읽기", lambda t: t.out("c", _cbus().k.count(3))),
    CostCase("Value.get(상수 p) 읽기 (걸쇠)", lambda t: t.out("c", _cbus().v.get(3))),
    CostCase("Value.received(상수 p) + if", lambda t: _if(_cbus().v.received(3))),
    CostCase("update: level 채널 1개 × 8명", _cost_level_update(8), note="Down/Up 둘 다 0 인 사이클"),
    CostCase("update: level 채널 1개 × 1명", _cost_level_update(1)),
    CostCase("update: 걸쇠 채널 1개 × 8명 (받지 않은 사이클)", _cost_latch_update(8), note="받은 사이클은 사람마다 +읽기"),
    CostCase("update: 걸쇠 채널 1개 × 1명 (받지 않은 사이클)", _cost_latch_update(1)),
]


def main():
    decl, nbus, others = section_declare()
    section_parser(decl, nbus, others)
    s = section_inject()
    ok1 = s.report()
    section_msqc_e2e()
    section_build()
    ok2 = ck.report()
    finish(ok1, ok2)


if __name__ == "__main__":
    main()
