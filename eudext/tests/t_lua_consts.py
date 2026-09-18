"""`tools/lua_consts` 일반 부품 시험 (WP18, DESIGN 5.4): 실행기·변환·파일 찾기·CtrigAsm 기록 스텁·모양 지문,
lupa 가 없을 때의 안내, 다음 배치(shape.CX)가 쓸 CB Paint 적재.

python tests/t_lua_consts.py
(SCR_DB 약속 값·계획은 t_scrdb 가 본다.)
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402

from eudext.tools import lua_consts as lc  # noqa: E402

ck = Checker("t_lua_consts")
WORK = os.path.join(_common.WORK, "t_lua_consts")
os.makedirs(WORK, exist_ok=True)


def write(name, text):
    path = os.path.join(WORK, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def section_runtime():
    ck.true("lupa available", lc.lupa_available() and lc.lupa_error() is None)
    L = lc.Lua()
    val = {"a": 1, "b": [1, 2, {"c": "한글"}], "d": True, "e": None, "f": [], "g": 2.5, 3: "x"}
    L.set("T", val)
    back = L.get("T")
    ck.eq("roundtrip", back, {"a": 1, "b": [1, 2, {"c": "한글"}], "d": True, "f": [], "g": 2.5, 3: "x"})
    ck.eq("raw bytes", L.get("T", raw=True)[b"b"][2][b"c"], "한글".encode())
    ck.eq("sequence -> list", L.to_py(L.rt.eval(b"{10, 20, 30}")), [10, 20, 30])
    ck.eq("holes -> dict", L.to_py(L.rt.eval(b"{[1]=1, [3]=3}")), {1: 1, 3: 3})
    ck.eq("empty -> list", L.to_py(L.rt.eval(b"{}")), [])
    L.run("function add(a, b) return a + b, a .. '|' .. b end")
    ck.eq("call tuple", L.call("add", 2, 3), (5, "2|3"))
    ck.true("has", L.has("add") and not L.has("nope"))
    ck.raises("call missing", lc.LuaConstsError, L.call, "nope")
    ck.raises("lua error", lc.LuaConstsError, L.run, "error('boom 한글')")
    try:
        L.run("error('boom 한글')")
    except lc.LuaConstsError as e:
        ck.true("error message decoded", "boom 한글" in str(e), str(e))

    def py_raise():
        raise KeyError("stub")

    L.install({"PyRaise": py_raise, "Name": "값", "Tbl": [1, 2]})
    ck.raises("python exception passes", KeyError, L.run, "PyRaise()")
    ck.eq("installed values", (L.get("Name"), L.get("Tbl")), ("값", [1, 2]))
    L.set_os(time=12345, date="2026-09-17 00:00:00")
    ck.eq("os stubs", (L.rt.eval(b"os.time()"), L.get("__nothing") if False else L.to_py(L.rt.eval(b"os.date('%Y')"))),
          (12345, "2026-09-17 00:00:00"))
    ck.eq("utf8 bom file", lc.load(write("bom.lua", "\ufeffX = 7")).get("X"), 7)
    ck.raises("missing file", lc.LuaConstsError, lc.load, os.path.join(WORK, "nope.lua"))
    p = write("g.lua", "A = 1\nB = {x = 'y'}\nfunction F() end\nlocal hidden = 3\n")
    ck.eq("read_globals new", lc.read_globals(p), {"A": 1, "B": {"x": "y"}})
    ck.eq("read_globals names", lc.read_globals(p, ["B"]), {"B": {"x": "y"}})
    ck.eq("read_globals stubs", lc.read_globals(write("s.lua", "Y = Base + 1"), ["Y"], stubs={"Base": 41}), {"Y": 42})
    info = lc.file_info(p)
    ck.true("file_info", info[0] == os.path.abspath(p) and len(info[1]) == 64 and info[2] > 0)


def section_find():
    d1 = os.path.join(WORK, "c1")
    d2 = os.path.join(WORK, "c2")
    os.makedirs(d1, exist_ok=True)
    os.makedirs(d2, exist_ok=True)
    with open(os.path.join(d2, "X.lua"), "w") as f:
        f.write("X = 1")
    ck.eq("find second", lc.find_lua_file("X.lua", [d1, d2]), (os.path.join(d2, "X.lua"), d2))
    ck.eq("find direct file", lc.find_lua_file("X.lua", [os.path.join(d2, "X.lua")])[0], os.path.join(d2, "X.lua"))
    ck.raises("find none", lc.LuaConstsError, lc.find_lua_file, "X.lua", [d1])
    try:
        lc.find_lua_file("X.lua", [d1])
    except lc.LuaConstsError as e:
        ck.true("find message lists tried", d1 in str(e), str(e))
    os.environ["EUDEXT_T_LC"] = d1
    try:
        ck.raises("env only (missing)", lc.LuaConstsError, lc.find_lua_file, "X.lua", [d2], env="EUDEXT_T_LC")
        os.environ["EUDEXT_T_LC"] = d2
        ck.eq("env dir", lc.find_lua_file("X.lua", [d1], env="EUDEXT_T_LC")[1], "환경 변수 EUDEXT_T_LC")
    finally:
        os.environ.pop("EUDEXT_T_LC", None)


TRACE_SRC = r"""
Code = CreateCcode()
Arr = CreateCcodeArr(3)
V1, V2 = CreateVars(2, FP)
function Emit()
    CIf(FP, {Memory(0x58F500, AtLeast, 1), CD(Code, 0)}, {SetCD(Code, 1)})
        TriggerX(FP, {LocalPlayerID("Ob1")}, {SetMemory(0x58F504, Add, 1)})
        TriggerX(FP, {CV(V1, 5, AtMost)}, {SetCD(Arr[2], 7)}, {preserved})
        f_Read(FP, DtoA(3, 21), V1, nil, 0xFFFF)
        CMov(FP, V2, V1)
        CMov(FP, 0x58F508, V2, nil, 0xFF)
        CAdd(FP, V2, V1, _Mul(V1, 65536))
    CIfEnd()
    CIfOnce(FP)
        local acts = {}
        for i = 1, 130 do table.insert(acts, SetMemory(0x58F600 + 4 * i, SetTo, i)) end
        DoActions2(FP, acts)
        DoActions(FP, {SetDeaths(1, SetTo, 2, 3)}, {})
        DoActionsX(FP, {SetDeathsX(1, SetTo, 2, 3, 0xFF)})
    CIfEnd()
    Callback(1, V1, V2)
end
"""


def section_trace():
    L = lc.Lua()
    tr = lc.CtrigTrace(L)
    L.run(TRACE_SRC)
    L.set("Callback", tr.callback("W"))
    L.call("Emit")
    root = tr.take()
    ck.eq("trace top", [n.kind for n in root], ["if", "once", "call"])
    blk = root[0]
    ck.eq("if conds", [c.op for c in blk.conds], ["Memory", "CD"])
    ck.eq("if acts", [a.op for a in blk.acts], ["SetCD"])
    ck.eq("if preserved", (blk.preserved, root[1].preserved), (True, False))
    ck.eq("if body kinds", [n.kind for n in blk.body], ["trig", "trig", "read", "mov", "mov", "add"])
    t1, t2 = blk.body[0], blk.body[1]
    ck.eq("TriggerX no flags = once", (t1.preserved, t2.preserved), (False, True))
    ck.eq("LocalPlayerID Ob1", t1.conds[0], lc.Term("Memory", 0x512684, 10, 128))
    ck.eq("CV default cmp", (t2.conds[0].args[1], t2.conds[0].args[2]), (5, lc.TEP_CONSTS["AtMost"]))
    ck.eq("Ccode arr ref", t2.acts[0].args[0].kind, "ccode")
    rd = blk.body[2]
    ck.eq("f_Read", (rd.args[0], rd.args[2]), (0x58A364 + 0x30 * 21 + 4 * 3, 0xFFFF))
    ck.eq("CMov mask", (blk.body[3].args[2], blk.body[4].args[0], blk.body[4].args[2]), (0xFFFFFFFF, 0x58F508, 0xFF))
    ck.eq("CAdd mul", blk.body[5].args[2].op, "Mul")
    once = root[1].body
    ck.eq("DoActions2 chunks", [len(n.acts) for n in once], [64, 64, 2, 1, 1])
    ck.eq("DoActions flags {} = not preserved", (once[3].preserved, once[4].preserved), (False, True))
    ck.eq("SetDeaths mask", (once[3].acts[0].args[4], once[4].acts[0].args[4]), (0xFFFFFFFF, 0xFF))
    ck.eq("callback node", root[2].args[:2], ("W", 1))
    ck.eq("refs", (tr.counts["ccode"], tr.counts["var"]), (4, 2))
    # 모양 지문: 번호가 달라도 모양이 같으면 같다
    L2 = lc.Lua()
    tr2 = lc.CtrigTrace(L2)
    L2.run("Extra = CreateCcode()\n" + TRACE_SRC)
    L2.set("Callback", tr2.callback("W"))
    L2.call("Emit")
    ck.eq("digest same shape", lc.trace_digest(tr2.take()), lc.trace_digest(root))
    L3 = lc.Lua()
    tr3 = lc.CtrigTrace(L3)
    L3.run(TRACE_SRC.replace("AtLeast, 1)", "AtLeast, 2)"))
    L3.set("Callback", tr3.callback("W"))
    L3.call("Emit")
    ck.true("digest differs", lc.trace_digest(tr3.take()) != lc.trace_digest(root))
    # 오류
    L4 = lc.Lua()
    tr4 = lc.CtrigTrace(L4)
    ck.raises("PushErrorMsg", lc.LuaStubError, L4.run, "PushErrorMsg('설정 오류')")
    ck.raises("unknown function", lc.LuaConstsError, L4.run, "Unknown(FP)")
    ck.raises("CIfEnd unmatched", lc.LuaConstsError, L4.run, "CIfEnd()")
    ck.raises("f_Read var input", lc.LuaConstsError, L4.run, "f_Read(FP, CreateVar(FP), CreateVar(FP))")
    ck.raises("CMov deviation", lc.LuaConstsError, L4.run, "CMov(FP, CreateVar(FP), 1, 2)")
    ck.true("trace kept", isinstance(tr4.take(), list))


def section_nolupa():
    code = (
        "import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r)\n"
        "sys.modules['lupa'] = None\n"
        "from eudext.tools import lua_consts as lc\n"
        "print('AVAIL', lc.lupa_available(), bool(lc.lupa_error()))\n"
        "try:\n"
        "    lc.Lua()\n"
        "except lc.LuaConstsError as e:\n"
        "    print('ERR', 'VenvSite' in str(e) and 'Preload : scrdb' in str(e))\n"
    ) % _common.ROOT
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=120,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    out = p.stdout.decode("utf-8", "replace")
    ck.true("no lupa -> guidance", "AVAIL False True" in out and "ERR True" in out, out + p.stderr.decode("utf-8", "replace"))


def section_reuse():
    """다음 배치 shape.CX 가 CB Paint 를 이 부품으로 읽는다 (DESIGN 5.4)."""
    path, _src = lc.find_lua_file("CB Paint v2.5.lua", [os.path.join(os.path.dirname(_common.ROOT), "MapSource", "Library"),
                                                        lc.REFERENCE_LIBRARY])
    L = lc.load(path)
    ck.true("cb paint functions", L.has("CSMakePolygon") and L.has("CSMakeCircle"))
    poly = L.call("CSMakePolygon", 4, 64, 0, 5, 0)
    ck.eq("cb paint polygon", (poly[0], len(poly), [round(x) for x in poly[2]]), (5, 6, [0, -64]))
    p = subprocess.run([sys.executable, os.path.join(_common.PKG, "tools", "lua_consts.py"), "get",
                        write("cli.lua", "K = {a = 1}\nN = 5\n"), "K", "N"], capture_output=True, timeout=120,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    ck.eq("cli get", json.loads(p.stdout.decode("utf-8")), {"K": {"a": 1}, "N": 5})


def main():
    section_runtime()
    section_find()
    section_trace()
    section_nolupa()
    section_reuse()
    finish(ck.report())


if __name__ == "__main__":
    main()
