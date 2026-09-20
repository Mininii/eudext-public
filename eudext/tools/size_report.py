"""페이로드 용량이 어디서 나오는지 센다 (빌드 시점, 게임 실행과 무관 — DESIGN 5.2 의 짝).

`tools/cost.py` 는 **항목 하나**의 값을 잰다(본문·호출 자리·실행·40벌 평균 바이트). 이 도구는 반대로
**맵 하나를 통째로 빌드해 놓고** 페이로드에 실제로 들어간 객체를 만든 자리로 되짚어 합친다.
어느 모듈·어느 줄이 용량을 먹는지 한 장에서 보려고 쓴다.

    python tools/size_report.py examples/hello.py                    파일별 요약
    python tools/size_report.py examples/auto_all.py --sites 40      줄별 상위 40개까지
    python tools/size_report.py a.py b.eps --attribute caller        eudext 안이 아니라 부른 쪽으로 몰아 센다
    python tools/size_report.py a.py --off i64.CONST_DIVISOR         용량 스위치를 끄고 견준다

페이로드는 eudplib 객체들의 바이트 합이다. 트리거 하나가 **2408바이트**라 트리거 수가 용량을 지배한다
(표의 "트리거환산" = 바이트 ÷ 2408).

되짚는 방법: 빌드하는 동안 `EUDObject` 갈래들의 `__init__` 을 감싸 **파이썬 호출 자리**를 적어 둔다
(eudplib 0.81 의 `EUDObject.__new__` 는 Rust 쪽이라 감싸면 안전성 검사에 걸린다 — `__init__` 을 쓴다).
자리는 스택에서 건너뛸 꾸러미(기본 eudplib) 밖의 첫 프레임이다. `--attribute caller` 면 eudext 도 건너뛰어
맵 코드 쪽으로 몰아 센다. 맵·eudext 코드가 스택에 아예 없으면(eudplib 이 스스로 굽는 도우미 본문) `[eudplib] <파일>` 로 따로 센다.

eudplib 은 **SaveMap 때** 본문을 굽는다(EUDFunc 는 부를 때까지 트리거를 내지 않는다) — 그래서 감싸기는
SaveMap 을 감싼 동안에만 걸어 둔다.
"""

import argparse
import collections
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

__all__ = ["Report", "measure", "render"]

TRIGGER_BYTES = 2408


# ---------------------------------------------------------------------------------------------
# 자리 되짚기
# ---------------------------------------------------------------------------------------------


def _norm(p):
    return os.path.abspath(p).replace("\\", "/")


def _skip_dirs(attribute):
    """(건너뛸 꾸러미 폴더 목록, eudplib 뿌리, eudplib 속살 폴더). 건너뛴 폴더 안에서 만든 객체는 부른 쪽으로 넘긴다."""
    import eudplib

    ep = _norm(os.path.dirname(eudplib.__file__))
    out = [ep + "/", _norm(HERE) + "/"]
    if attribute == "caller":
        out.append(_norm(PKG) + "/")
    return out, ep + "/", ep + "/core/"


def _install(record, skips, eplib, core, stop):
    """EUDObject 갈래들의 __init__ 을 감싼다. 되돌리기 목록을 반환.

    stop: `measure()` 의 프레임. 빌드를 시작한 `save()` 프레임과 그 아래는 보지 않는다 — 안 그러면
    eudplib 이 스스로 굽는 본문이 `measure()` 를 부른 줄에 몽땅 붙는다.
    """
    from eudplib.core.eudobj import EUDObject

    def site():
        f = sys._getframe(2)
        inner = sub = None
        while f is not None and f.f_back is not stop:
            fn = _norm(f.f_code.co_filename)
            if not any(fn.startswith(s) for s in skips):
                return (fn, f.f_lineno, False)
            if inner is None and fn.startswith(eplib):
                inner = (fn, f.f_lineno, True)
            if sub is None and fn.startswith(eplib) and not fn.startswith(core):
                sub = (fn, f.f_lineno, True)  # core 밖의 eudplib 갈래 (memio·string·trigger…) — 더 알아보기 쉽다
            f = f.f_back
        return sub or inner  # 맵·eudext 프레임이 하나도 없다 = eudplib 이 스스로 굽는 본문

    def wrap(orig):
        def tagged(self, *a, **k):
            orig(self, *a, **k)
            if id(self) not in record:
                record[id(self)] = site()

        return tagged

    targets = []

    def walk(c):
        for s in c.__subclasses__():
            if "__init__" in s.__dict__:
                targets.append(s)
            walk(s)

    walk(EUDObject)
    targets.append(EUDObject)  # 제 __init__ 이 없는 갈래는 여기서 걸린다

    undo = []
    for cls in targets:
        had_own = "__init__" in cls.__dict__  # 덮어쓰기 전에 본다 (EUDObject 는 제 __init__ 이 없다)
        orig = cls.__dict__.get("__init__", cls.__init__)
        try:
            cls.__init__ = wrap(orig)
        except TypeError:  # noqa: PERF203  (Rust 쪽 타입 등 못 고치는 것은 건너뛴다)
            continue
        undo.append((cls, had_own, orig))
    return undo


def _restore(undo):
    for cls, had_own, orig in undo:
        if had_own:
            cls.__init__ = orig
        else:
            try:
                del cls.__init__
            except AttributeError:
                cls.__init__ = orig


# ---------------------------------------------------------------------------------------------
# 재기
# ---------------------------------------------------------------------------------------------


class Report:
    """by_class·by_file·by_site 는 {이름: [객체 수, 바이트]}. total 은 [객체 수, 바이트]."""

    __slots__ = ("by_class", "by_file", "by_site", "elapsed", "out", "total")

    def __init__(self):
        self.by_class = collections.defaultdict(lambda: [0, 0])
        self.by_file = collections.defaultdict(lambda: [0, 0])
        self.by_site = collections.defaultdict(lambda: [0, 0])
        self.total = [0, 0]
        self.out = None
        self.elapsed = 0.0


def measure(save, attribute="eudext", root=None):
    """save() 를 감싸 재고 Report 를 돌려준다.

    save: SaveMap 까지 하는 함수 (반환값은 Report.out 에 담는다). LoadMap·코드 싣기는 부르는 쪽에서 끝내 둔다.
    attribute: "eudext" = eudext 줄까지 보인다, "caller" = eudext 도 건너뛰어 맵 코드 쪽으로 몰아 센다.
    root: 파일 이름을 이 폴더 기준 상대경로로 (기본 저장소 뿌리).
    """
    from eudplib.core.allocator import payload as pl

    record = {}
    skips, eplib, core = _skip_dirs(attribute)
    t = time.time()
    undo = _install(record, skips, eplib, core, sys._getframe())
    try:
        out = save()
    finally:
        _restore(undo)

    rep = Report()
    rep.out = out
    rep.elapsed = time.time() - t
    base = _norm(root or ROOT)
    for obj in pl._found_objects_dict:
        try:
            size = obj.GetDataSize()
        except Exception:  # noqa: BLE001  (크기를 못 내는 객체는 빼고 센다)
            continue
        rep.total[0] += 1
        rep.total[1] += size
        cls = type(obj).__name__
        rep.by_class[cls][0] += 1
        rep.by_class[cls][1] += size
        where = record.get(id(obj))
        if where is None:
            fkey = key = "(모름)"
        else:
            path, line, inner = where
            try:
                fkey = os.path.relpath(path, base).replace("\\", "/")
            except ValueError:
                fkey = path
            if inner:  # 맵·eudext 코드가 스택에 없다 = eudplib 이 스스로 만든 것
                fkey = "[eudplib] " + os.path.basename(path)
            key = "%s:%d" % (fkey, line)
        rep.by_file[fkey][0] += 1
        rep.by_file[fkey][1] += size
        rep.by_site[key][0] += 1
        rep.by_site[key][1] += size
    return rep


# ---------------------------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------------------------


def render(rep, sites=0, classes=12, files=0):
    tot = max(1, rep.total[1])
    L = []
    L.append("")
    L.append("페이로드 객체 %d개 / %.2f MB   (빌드 %.0fs)" % (rep.total[0], rep.total[1] / 1048576.0, rep.elapsed))
    L.append("트리거 1개 = %d 바이트. '트리거환산' 은 바이트 ÷ %d 이다." % (TRIGGER_BYTES, TRIGGER_BYTES))
    L.append("")
    L.append("── 종류별 " + "─" * 46)
    L.append("%-28s %8s %12s %7s" % ("클래스", "객체", "바이트", "비중"))
    for cls, (n, b) in sorted(rep.by_class.items(), key=lambda x: -x[1][1])[:classes]:
        L.append("%-28s %8d %12d %6.1f%%" % (cls, n, b, 100.0 * b / tot))
    L.append("")
    L.append("── 파일별 " + "─" * 46)
    L.append("%-46s %8s %12s %9s %7s" % ("파일", "객체", "바이트", "트리거환산", "비중"))
    rows = sorted(rep.by_file.items(), key=lambda x: -x[1][1])
    for f, (n, b) in rows[:files] if files else rows:
        L.append("%-46s %8d %12d %9.0f %6.1f%%" % (f[:46], n, b, b / TRIGGER_BYTES, 100.0 * b / tot))
    if sites:
        L.append("")
        L.append("── 줄별 상위 %d " % sites + "─" * 40)
        L.append("%-56s %8s %12s %9s" % ("파일:줄", "객체", "바이트", "트리거환산"))
        for s, (n, b) in sorted(rep.by_site.items(), key=lambda x: -x[1][1])[:sites]:
            L.append("%-56s %8d %12d %9.0f" % (s[:56], n, b, b / TRIGGER_BYTES))
    return "\n".join(L)


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------


def main(argv=None):
    a = argparse.ArgumentParser(description="페이로드 용량을 만든 자리별로 센다")
    a.add_argument("plugins", nargs="+", help="단독 빌드로 실을 .py / .eps")
    a.add_argument("--base", default=None, help="바탕 맵 (기본 testing/base.scx)")
    a.add_argument("--out", default=None, help="빌드 산출 scx 자리 (기본 작업 폴더)")
    a.add_argument("--sites", type=int, default=0, help="줄별 상위 N개도 출력")
    a.add_argument("--classes", type=int, default=12, help="종류별 상위 N개 (기본 12)")
    a.add_argument("--files", type=int, default=0, help="파일별 상위 N개 (0 = 전부)")
    a.add_argument("--attribute", choices=("eudext", "caller"), default="eudext",
                   help="eudext = eudext 줄까지 보인다(기본), caller = eudext 를 건너뛰고 부른 쪽으로")  # fmt: skip
    a.add_argument("--root", default=None, help="파일 이름의 기준 폴더 (기본 저장소 뿌리)")
    a.add_argument("--off", default="", help="용량 스위치를 끄고 견준다: 쉼표로 `모듈.이름` "
                                            "(예: i64.CONST_DIVISOR,i128.CONST_DIVISOR)")  # fmt: skip
    ns = a.parse_args(argv)

    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

    from eudext.tools import build

    for name in (x.strip() for x in ns.off.split(",")):
        if not name:
            continue
        mod, _, attr = name.rpartition(".")
        if not mod:
            sys.exit("스위치 이름은 `모듈.이름` 이어야 합니다: %s" % name)
        m = __import__("eudext." + mod, fromlist=[attr])
        if not hasattr(m, attr):
            sys.exit("eudext.%s 에 %s 가 없습니다" % (mod, attr))
        setattr(m, attr, False)
        print("스위치 끔: eudext.%s.%s" % (mod, attr))

    out = ns.out or os.path.join(build._default_work(), "size_report.scx")
    rep = measure(lambda: build.standalone(ns.plugins, base=ns.base or build.BASE_MAP, out=out),
                  attribute=ns.attribute, root=ns.root)  # fmt: skip
    print(render(rep, sites=ns.sites, classes=ns.classes, files=ns.files))
    print("\n빌드 산출: %s" % rep.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
