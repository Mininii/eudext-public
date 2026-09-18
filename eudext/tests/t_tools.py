"""도구·부트·판 검사 단위 시험 (에뮬레이터 없음): _compat.check, boot 설정 읽기, edsgen ↔ build.read_eds, cost 표.

python tests/t_tools.py
"""

import sys

sys.dont_write_bytecode = True  # 저장소에 __pycache__ 를 남기지 않는다
import _common  # noqa: E402
from _common import Checker, finish  # noqa: E402

import os  # noqa: E402
import warnings  # noqa: E402

import eudext  # noqa: E402
from eudext import _compat, boot, errors  # noqa: E402
from eudext.tools import build, cost, edsgen  # noqa: E402

ck = Checker("t_tools")

# --- 판 검사 ---
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    ver = _compat.check()
ck.eq("eudplib version", ver, "0.81.0")
ck.eq("no version warning", [str(x.message) for x in w], [])
ck.eq("version tuple", _compat.eudplib_version()[:2], (0, 81))
ck.eq("eudext version", eudext.__version__, "0.0.1")
ck.true("strict check ok", _compat.check(strict=True) == "0.81.0")

# --- errors ---
ck.raises("fail", errors.EudextError, errors.fail, "값 %d", 3)
ck.raises("check_range", errors.EudextError, errors.check_range, "x", 10, 0, 5)
ck.eq("check_range ok", errors.check_range("x", 5, 0, 5), 5)
ck.raises("check_range bool", errors.EudextError, errors.check_range, "x", True, 0, 5)
ck.raises("check_choice", errors.EudextError, errors.check_choice, "m", "z", ("a", "b"))
try:
    errors.fail("메시지")
except errors.EudextError as e:
    ck.true("prefix", str(e).startswith("[eudext] 메시지"), str(e))
ck.true("EPError subclass", issubclass(errors.EudextError, __import__("eudplib").EPError))

# --- boot 설정 읽기 (euddraft 가 넣는 settings 흉내) ---
boot.settings = {
    "EudextRoot": " C:\\x\\Py ",
    "VenvSite": "C:\\site ; 끝 주석",
    "; semicolon line": "",
    "Preload": "i64, shape;cell",
}
opts = boot._read_settings()
del boot.settings
ck.eq("boot keys lower", sorted(opts), ["eudextroot", "preload", "venvsite"])
ck.eq("boot trailing comment", opts["venvsite"], "C:\\site")
ck.eq("boot root strip", opts["eudextroot"], "C:\\x\\Py")
ck.eq("boot preload split", boot._split_names(opts["preload"]), ["i64", "shape", "cell"])
ck.raises("boot no root", RuntimeError, boot._boot, {})
ck.raises("boot bad root", RuntimeError, boot._boot, {"eudextroot": os.path.join(_common.WORK, "nowhere")})
ck.eq("boot real root", boot._boot({"eudextroot": _common.ROOT, "preload": "errors"}), eudext)

# --- edsgen → build.read_eds 왕복 ---
eds_path = os.path.join(_common.WORK, "t_tools", "gen.eds")
doc = edsgen.EdsDoc("base.scx", "out.scx", shufflePayload="False")
doc.header_comment = "시험용\n두 줄"
doc.boot(eudext_root=_common.ROOT, venv_site="C:\\site", preload=["i64"], eds_dir=os.path.dirname(eds_path))
doc.add_msqc("KeyDown(A) : 0x58D740, 1", "MouseDown(L) : 0x58D744, 1")
doc.add_plugin("main.eps")
doc.add_plugin("other.py", {"Opt": "1"})
doc.freeze = False
doc.write(eds_path)
secs = build.read_eds(eds_path)
names = [s[0] for s in secs]
ck.eq("eds sections", names[0], "main")
ck.true("eds boot rel", names[1].endswith("boot.py") and not os.path.isabs(names[1]), names[1])
ck.eq("eds order", names[2:], ["MSQC", "main.eps", "other.py", "freeze"])
main_items = {k: v for k, v, _r in secs[0][1]}
ck.eq("eds main", main_items, {"input": "base.scx", "output": "out.scx", "shufflePayload": "False"})
boot_items = {k: v for k, v, _r in secs[1][1]}
ck.eq("eds boot keys", sorted(boot_items), ["EudextRoot", "Preload", "VenvSite"])
ck.eq("eds msqc raw", [r for _k, _v, r in secs[2][1]], ["KeyDown(A) : 0x58D740, 1", "MouseDown(L) : 0x58D744, 1"])
ck.eq("eds freeze", secs[-1][1][0][:2], ("freeze", "0"))
with open(eds_path, encoding="utf-8") as f:
    text = f.read()
ck.true("eds comments", text.startswith(":: 시험용\n:: 두 줄"), text[:30])
ck.raises("eds bad key", edsgen.EdsError, edsgen.Section("x").set, "a:b", "1")
ck.raises("eds newline", edsgen.EdsError, edsgen.Section("x").set, "a", "1\n2")
ck.raises("eds dup section", edsgen.EdsError, lambda: (lambda d: (d.add_plugin("a.py"), d.add_plugin("a.py"), d.render()))(edsgen.EdsDoc("i", "o")))
ck.raises("eds bad main opt", edsgen.EdsError, edsgen.EdsDoc, "i", "o", nothing="1")
d2 = edsgen.EdsDoc("i", "o")
d2.freeze = None
ck.true("eds no freeze section", "[freeze]" not in d2.render())

# --- prepare_eds (작업 폴더로 옮기기) ---
work = os.path.join(_common.WORK, "t_tools", "prep")
new_eds, out_map = build.prepare_eds(os.path.join(_common.PKG, "examples", "hello.eds"), work)
secs = build.read_eds(new_eds)
ck.eq("prep out", out_map, os.path.join(work, "hello_out.scx"))
ck.eq("prep sections", [s[0] for s in secs], ["main", "eudext_boot.py", "hello.py", "hello.eps", "freeze"])
ck.true("prep copies", all(os.path.isfile(os.path.join(work, n)) for n in ("eudext_boot.py", "hello.py", "hello.eps")))
bi = {k: v for k, v, _r in secs[1][1]}
ck.eq("prep root abs", os.path.normcase(bi["EudextRoot"]), os.path.normcase(_common.ROOT))
ck.eq("prep pycache", bi["PycachePrefix"], os.path.join(work, "pycache"))
mi = {k: v for k, v, _r in secs[0][1]}
ck.eq("prep input abs", os.path.normcase(mi["input"]), os.path.normcase(os.path.join(_common.PKG, "testing", "base.scx")))

# --- 경로 구분자 (Linux 에서 Windows 식 eds 경로 읽기) ---
_sep = os.sep
try:
    os.sep = "/"
    ck.eq("native posix backslash", build._native(r"..\testing\base.scx"), "../testing/base.scx")
    ck.eq("native posix slash", build._native("../boot.py"), "../boot.py")
    ck.eq("boot native posix", boot._native(r"..\.."), "../..")
    os.sep = "\\"
    ck.eq("native windows keeps", build._native(r"..\x"), r"..\x")
finally:
    os.sep = _sep
ck.true("euddraft default path", isinstance(build.EUDDRAFT, str) and build.EUDDRAFT.endswith(("euddraft", "euddraft.exe")), build.EUDDRAFT)

# --- cost 표 ---
row = cost.CostRow("x", "비고")
row.call, row.exec_min, row.exec_max, row.target = 5, 2, 9, {"call": 3, "exec": 10}
ck.eq("cost over", row.over(), ["call 5 > 3"])
md = cost.render([row], "제목", date="2026-09-17")
ck.true("cost render", "| x | - | 5 | 2~9 | - | call≤3, exec≤10 **초과: call 5 > 3** | 비고 |" in md, md)

# --- edsgen: [MSQC]/[NSQC] 줄과 sync 훅 (WP13) ---
from eudext import sync  # noqa: E402

ck.eq("line_key plain", edsgen.line_key("KeyDown(A) : x, 1"), "KeyDown(A)")
ck.eq("line_key escaped", edsgen.line_key(r"NotTyping; KeyDown(\=) : x, 1"), "NotTyping; KeyDown(=)")
ck.eq("line_key equals sep", edsgen.line_key("QCUnit = 49"), "QCUnit")
ck.eq("line_key backslash", edsgen.line_key("KeyDown(\\\\) : x"), "KeyDown(\\)")
ck.eq("line_key no value", edsgen.line_key("KeyPress(A)"), "KeyPress(A)")
tb = sync.Bus("msqc", qc_unit=49, name="tt")
tb.key_down("=", guard=sync.not_typing())
tn = sync.Bus("nsqc", qc_unit=49, name="ttn", deaths=250)
tn.key_press("B")
d3 = edsgen.EdsDoc("i.scx", "o.scx")
d3.add_msqc(tb, "KeyDown(Q) : 0x58D740, 1")
d3.add_nsqc(tn)
ck.raises("add_msqc nsqc bus", edsgen.EdsError, d3.add_msqc, tn)
ck.raises("add_msqc newline", edsgen.EdsError, d3.add_msqc, "a : 1\nb : 2")
r3 = d3.render()
ck.true("add_msqc bus lines", "[MSQC]\nQCUnit : 49\nNotTyping; KeyDown(\\=) : eudext_tt_p1, 1\nKeyDown(Q) : 0x58D740, 1" in r3, r3)
ck.true("add_nsqc bus lines", "[NSQC]\nQCUnit : 49\nKeyPress(B) : 250, 1" in r3, r3)
d3.add_msqc("NotTyping; KeyDown(\\=) : eudext_tt_p1, 1")  # 똑같은 줄은 한 번만
ck.eq("same line once", d3.render().count("KeyDown(\\=)"), 1)
d3.add_msqc("NotTyping; KeyDown(\\=) = other, 2")
ck.raises("dup key", edsgen.EdsError, d3.render)

sync_dir = os.path.join(_common.WORK, "t_tools", "sync")
d4 = edsgen.EdsDoc("base.scx", "out.scx")
d4.boot(eudext_root=_common.ROOT, eds_dir=sync_dir)
d4.add_plugin("main.eps")
hook_sec = d4.add_sync([tb, tn], hook=True, local_update=False, sections={"NSQC": "NSQC.py"})
ck.raises("add_sync twice hook", edsgen.EdsError, d4.add_sync, [], hook=True)
ck.raises("add_sync bad section", edsgen.EdsError, edsgen.EdsDoc("i", "o").add_sync, [], hook=False, sections={"X": "y"})
d4.freeze = False
sync_eds = d4.write(os.path.join(sync_dir, "sync.eds"))
secs4 = build.read_eds(sync_eds)
ck.eq("add_sync order", [os.path.basename(s[0]) for s in secs4],
      ["main", "boot.py", "MSQC", "NSQC.py", edsgen.HOOK_NAME, "main.eps", "freeze"])
ck.eq("add_sync hook settings", [(k, v) for k, v, _r in secs4[4][1]], [("LocalUpdate", "0")])
ck.true("add_sync hook section", hook_sec is not None and hook_sec.name == edsgen.HOOK_NAME)
hook_file = os.path.join(sync_dir, edsgen.HOOK_NAME)
ck.true("hook file written", os.path.isfile(hook_file))
with open(hook_file, encoding="utf-8") as f:
    hook_text = f.read()
ck.eq("hook file content", hook_text, sync.hook_source())
ck.true("hook compiles", compile(hook_text, hook_file, "exec") is not None)
ck.eq("msqc raw keys", [k for k, _v, _r in secs4[2][1]], ["QCUnit", r"NotTyping; KeyDown(\=)"])
prep_dir = os.path.join(_common.WORK, "t_tools", "sync_prep")
for _n in ("main.eps", "NSQC.py"):  # prepare_eds 가 eds 폴더의 플러그인 파일을 복사한다 — 빈 파일로 둔다
    open(os.path.join(sync_dir, _n), "w").close()
new_eds4, _o = build.prepare_eds(sync_eds, prep_dir)
ck.true("prepare copies hook", os.path.isfile(os.path.join(prep_dir, edsgen.HOOK_NAME)))
ck.eq("prepare keeps sections", [os.path.basename(s[0]) for s in build.read_eds(new_eds4)][2:5],
      ["MSQC", "NSQC.py", edsgen.HOOK_NAME])
w5 = edsgen.write_eds(os.path.join(sync_dir, "w5.eds"), "base.scx", "out.scx", ["main.eps"],
                      sync={"buses": [tb], "hook": False})
ck.eq("write_eds sync", [s[0] for s in build.read_eds(w5)][2:], ["MSQC", "main.eps", "freeze"])

finish(ck.report())
