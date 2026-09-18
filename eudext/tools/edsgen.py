"""eds 생성 (DESIGN 5.3): 부트 플러그인 줄 + [MSQC]/[NSQC] 조각(eudext.sync) + 플러그인 줄 → euddraft 설정 파일.

euddraft 0.11 eds 문법 (upstream `readconfig.py`, WP0 실측):
- `[머리]` 줄은 그 줄 전체가 `[...]` 여야 한다. 뒤에 주석을 달면 머리로 읽히지 않는다.
- `키 : 값` 의 값은 줄 끝까지 전부다. **끝 주석(`; …`)을 달 수 없다** — 값에 들어간다.
- 주석 줄은 `::` 로 시작한다. `;` 나 `#` 로 시작하는 줄은 "값 없는 키" 로 읽힌다(플러그인이 무시하면 무해).
- 같은 머리·같은 키가 두 번 나오면 오류.
- 플러그인 머리가 `.py`/`.eps` 로 끝나면 eds 폴더 기준 경로, 아니면 euddraft `plugins` 폴더의 이름.
- `[freeze]` 에 `freeze` 키가 **있으면**(값과 무관) freeze 가 꺼진다. 섹션이 없으면 켜진다.

예:
    from eudext.tools import edsgen
    doc = edsgen.EdsDoc("base.scx", "out.scx")
    doc.boot(eudext_root=r"...\\MapSource\\Py", preload=["i64"])
    doc.add_plugin("main.eps")
    doc.freeze = False
    doc.write("map.eds")

동기화 입력 (WP13, DESIGN 4.12·5.3) — 빌드 순서 = 선언 수집 → eds → euddraft:
    from eudext import sync
    sync.collect("main.eps", map_path="base.scx")      # ① 선언만 실행 (트리거 없음)
    doc = edsgen.EdsDoc("base.scx", "out.scx")
    doc.boot(eudext_root=ROOT)
    doc.add_sync(hook=True)                             # ② [MSQC] 줄 + 훅 플러그인(eudext_sync_hook.py)
    doc.add_plugin("main.eps")
    doc.write("map.eds")                                # 훅 파일도 eds 옆에 쓴다
    # ③ tools/build.py euddraft map.eds --work …
- `[MSQC]`/`[NSQC]` 줄은 키가 겹치면 euddraft 가 오류를 내므로 render() 가 먼저 막는다(키는 역슬래시 이스케이프를 푼 형태로 비교).
- 훅 플러그인은 `[MSQC]`/`[NSQC]` 바로 뒤, 다른 맵 플러그인보다 앞에 놓인다(`plugins` 맨 앞).
- NSQC.py 를 eds 폴더에 두고 쓰려면 `add_sync(sections={"NSQC": "NSQC.py"})` (섹션 이름 = 플러그인 경로).

SCR_DB (WP18, DESIGN 4.18·5.3) — `scrdb.setup(…)` 이 모듈 최상위에서 MSQC 버스(채널 줄)를 만든다:
    sync.collect("main.eps", map_path="base.scx")      # ① scrdb 버스도 모인다
    doc.boot(eudext_root=ROOT, venv_site=SITE)          # lupa 폴더 (빌드 때 Lua 코어를 읽는다)
    doc.add_sync(hook=True)                             # ② [MSQC] 줄(scrdb 채널 포함) + sync 훅
    doc.add_scrdb(build_id=…, manifest=…)               #    부트 Preload 에 scrdb + scrdb 훅(sync 훅 바로 뒤)
    doc.add_plugin("main.eps")
- scrdb 훅(`eudext_scrdb_hook.py`)은 `[MSQC]` 뒤·맵 플러그인 앞에서 `scrdb.frame()` 을 낸다(`frame=False` 면 맵이 직접).
  훅 설정: `Core`(Lua 코어 경로), `BuildId`, `Manifest`(빌드 때 쓸 매니페스트 경로), `Frame`(0/1).
- `add_scrdb()` 는 부트 섹션에 `VenvSite` 가 없으면 오류(lupa 가 부트 중에만 import 된다, DESIGN 2.3).
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
ROOT = os.path.dirname(PKG)
BOOT_PY = os.path.join(PKG, "boot.py")

MAIN_OPTIONS = (
    "input",
    "output",
    "shufflePayload",
    "debug",
    "decodeUnitName",
    "objFieldN",
    "sectorSize",
    "ptrEUDArray",
    "errorReapplyEPD",
    "suppressWarnings",
)

__all__ = ["BOOT_PY", "EdsDoc", "EdsError", "HOOK_NAME", "SCRDB_HOOK_NAME", "Section", "boot_section", "line_key",
           "write_eds"]

HOOK_NAME = "eudext_sync_hook.py"
SCRDB_HOOK_NAME = "eudext_scrdb_hook.py"


class EdsError(ValueError):
    """eds 로 쓸 수 없는 값."""


def _check_value(key, value):
    value = str(value)
    if "\n" in value or "\r" in value:
        raise EdsError("eds 값에 줄바꿈을 넣을 수 없습니다: %s" % key)
    if value != value.strip():
        value = value.strip()
    return value


def _check_key(key):
    key = str(key).strip()
    if not key or any(ch in key for ch in ":=\n\r"):
        raise EdsError("eds 키로 쓸 수 없는 이름: %r" % key)
    if key.startswith("::"):
        raise EdsError("'::' 로 시작하는 키는 주석으로 읽힙니다: %r" % key)
    return key


class Section:
    """eds 섹션 하나. items 는 (키, 값) 순서 목록. 값이 None 이면 `키` 만 쓴다."""

    def __init__(self, name, items=None, comment=None):
        name = str(name)
        if "\n" in name or not name.strip():
            raise EdsError("잘못된 섹션 이름: %r" % name)
        self.name = name
        self.items = []
        self.comment = comment
        for k, v in items or []:
            self.set(k, v)

    def set(self, key, value=None):
        key = _check_key(key)
        for i, (k, _v) in enumerate(self.items):
            if k == key:
                self.items[i] = (key, None if value is None else _check_value(key, value))
                return self
        self.items.append((key, None if value is None else _check_value(key, value)))
        return self

    def add_line(self, line):
        """원문 줄(예: MSQC 의 `KeyDown(...) : 0x58D740, 1`)을 그대로 넣는다."""
        line = str(line).strip()
        if not line or "\n" in line:
            raise EdsError("잘못된 줄: %r" % line)
        self.items.append((line, "\0raw"))
        return self

    def render(self):
        out = []
        if self.comment:
            for c in str(self.comment).splitlines():
                out.append(":: " + c)
        out.append("[%s]" % self.name)
        for k, v in self.items:
            if v == "\0raw":
                out.append(k)
            elif v is None:
                out.append(k)
            else:
                out.append("%s : %s" % (k, v))
        return "\n".join(out)


def line_key(line):
    """`키 : 값` 줄의 키를 euddraft readconfig 처럼 읽어 이스케이프(`\\x`)를 푼 형태로 돌려준다. 값이 없으면 줄 전체."""
    line = str(line).strip()
    out = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            out.append(line[i + 1])
            i += 2
            continue
        if ch in ":=":
            return "".join(out).strip()
        out.append(ch)
        i += 1
    return "".join(out).strip()


def _rel(path, base_dir):
    path = os.path.abspath(path)
    try:
        rel = os.path.relpath(path, base_dir)
    except ValueError:  # 다른 드라이브
        return path
    return rel


def boot_section(eudext_root=ROOT, venv_site=None, preload=(), pycache_prefix=None, boot_path=BOOT_PY, eds_dir=None):
    """부트 플러그인 섹션을 만든다. eds_dir 를 주면 boot 경로를 eds 기준 상대 경로로 쓴다."""
    head = _rel(boot_path, eds_dir) if eds_dir else os.path.abspath(boot_path)
    sec = Section(head, comment="eudext 부트 (다른 eudext 사용 플러그인보다 앞)")
    sec.set("EudextRoot", os.path.abspath(eudext_root))
    if venv_site:
        sec.set("VenvSite", os.path.abspath(venv_site))
    if preload:
        sec.set("Preload", ", ".join(preload))
    if pycache_prefix:
        sec.set("PycachePrefix", os.path.abspath(pycache_prefix))
    return sec


class EdsDoc:
    """eds 문서. 쓰는 순서: [main] → 부트 → (SCBank) → [MSQC] → [NSQC] → 나머지 플러그인 → [freeze].

    msqc_lines / nsqc_lines: `[MSQC]`/`[NSQC]` 줄(원문). `add_msqc`/`add_nsqc`/`add_sync` 가 채운다. 비어 있으면 섹션을 쓰지 않는다.
    section_names: {"MSQC": 섹션 이름, "NSQC": …} — 플러그인 파일을 eds 폴더에 둘 때 바꾼다(예: "NSQC.py").
    extra_files: {파일 이름: 내용} — `write()` 가 eds 옆에 같이 쓴다(sync 훅 플러그인).
    freeze: None = 섹션 없음(euddraft 0.11 기본: freeze 켜짐), False = `[freeze] freeze : 0`(끔), True = `[freeze]`(켬).
    """

    def __init__(self, input_map, output_map, **main_options):
        self.main = Section("main")
        self.main.set("input", input_map)
        self.main.set("output", output_map)
        for k, v in main_options.items():
            if k not in MAIN_OPTIONS:
                raise EdsError("[main] 에 없는 옵션: %s" % k)
            self.main.set(k, v)
        self.boot_sec = None
        self.pre_plugins = []  # 부트와 MSQC 사이 (SCBank 등)
        self.msqc_lines = []
        self.nsqc_lines = []
        self.plugins = []
        self.freeze = None
        self.header_comment = None
        self.section_names = {"MSQC": "MSQC", "NSQC": "NSQC"}
        self.extra_files = {}

    def boot(self, **kw):
        self.boot_sec = boot_section(**kw)
        return self.boot_sec

    def add_plugin(self, name, settings=None, before_msqc=False, comment=None):
        sec = Section(name, list((settings or {}).items()), comment=comment)
        (self.pre_plugins if before_msqc else self.plugins).append(sec)
        return sec

    @staticmethod
    def _lines_of(items, section):
        out = []
        for x in items:
            if hasattr(x, "eds_lines") and hasattr(x, "transport"):  # eudext.sync.Bus
                if x.transport.section != section:
                    raise EdsError("%s 버스를 [%s] 에 넣을 수 없습니다" % (x.transport.section, section))
                out.extend(x.eds_lines())
            elif isinstance(x, (list, tuple)):
                out.extend(EdsDoc._lines_of(x, section))
            else:
                line = str(x).strip()
                if not line or "\n" in line:
                    raise EdsError("잘못된 [%s] 줄: %r" % (section, x))
                out.append(line)
        return out

    def add_msqc(self, *lines):
        """[MSQC] 줄을 더한다. 문자열(원문 줄) 또는 `eudext.sync.Bus`(그 버스의 줄)."""
        self.msqc_lines.extend(self._lines_of(lines, "MSQC"))

    def add_nsqc(self, *lines):
        """[NSQC] 줄을 더한다. 문자열 또는 NSQC `eudext.sync.Bus`."""
        self.nsqc_lines.extend(self._lines_of(lines, "NSQC"))

    def add_sync(self, buses=None, hook=True, local_update=True, sections=None, hook_name=HOOK_NAME):
        """선언된 `eudext.sync` 버스(기본: 모두)의 [MSQC]/[NSQC] 줄과 훅 플러그인을 넣는다 (WP13).

        인자: buses(Bus 목록, 기본 sync.buses()), hook(훅 플러그인 섹션 + 파일), local_update(False 면 훅이
              local.update() 를 내지 않음 — 설정 `LocalUpdate : 0`), sections({"NSQC": "NSQC.py"} 처럼 섹션 이름 바꾸기),
              hook_name(훅 파일 이름, eds 폴더 기준)
        반환: 훅 섹션(Section) 또는 None
        """
        from eudext import sync

        for sec, lines in sync.eds_sections(buses).items():
            if sec == "MSQC":
                self.msqc_lines.extend(lines)
            elif sec == "NSQC":
                self.nsqc_lines.extend(lines)
            else:  # 새 전송이 생기면 여기에 섹션을 더한다
                raise EdsError("edsgen 이 모르는 sync 섹션: %s" % sec)
        for k, v in (sections or {}).items():
            if k not in self.section_names:
                raise EdsError("바꿀 수 없는 섹션 이름: %s" % k)
            self.section_names[k] = str(v)
        if not hook:
            return None
        if any(p.name == hook_name for p in self.plugins):
            raise EdsError("훅 플러그인이 이미 있습니다: %s" % hook_name)
        items = [] if local_update else [("LocalUpdate", "0")]
        sec = Section(hook_name, items, comment="eudext.sync 훅: [MSQC]/[NSQC] 뒤, 맵 플러그인 앞 (수신 뒤 sync.update, 맵 뒤 local.update)")
        self.plugins.insert(0, sec)
        self.extra_files[hook_name] = sync.hook_source()
        return sec

    def add_scrdb(self, db=None, hook=True, core=None, build_id=None, manifest=None, frame=True, preload=True,
                  require_venv=True, hook_name=SCRDB_HOOK_NAME):
        """SCR_DB(WP18): scrdb 채널 줄([MSQC]) + 부트 Preload `scrdb` + scrdb 훅 플러그인을 넣는다.

        인자: db(scrdb.ScrDb, 기본 scrdb 에 선언된 것 — 없으면 채널 줄은 add_sync 몫), hook(훅 섹션·파일),
              core(Lua 코어 경로 → 훅 설정 Core, 절대 경로로), build_id(→ BuildId), manifest(→ Manifest, 절대 경로로),
              frame(False 면 훅 설정 Frame : 0 — 맵이 db.frame() 을 직접 부른다), preload(부트 Preload 에 scrdb),
              require_venv(부트에 VenvSite 가 없으면 오류), hook_name
        반환: 훅 섹션(Section) 또는 None
        순서: 훅은 sync 훅 바로 뒤(없으면 plugins 맨 앞) — `[MSQC]` 섹션은 plugins 보다 앞에 쓰이므로 수신 뒤, 맵 앞이다.
        """
        from eudext import scrdb

        if db is None:
            db = scrdb.declared()
        if db is not None:
            self.add_msqc(db.bus)  # 같은 줄은 render 가 한 번만 쓴다
        if preload:
            if self.boot_sec is None:
                raise EdsError("add_scrdb: boot() 를 먼저 부르세요 (Preload·VenvSite 가 필요)")
            items = dict(self.boot_sec.items)
            if require_venv and not items.get("VenvSite"):
                raise EdsError("add_scrdb: 부트 섹션에 VenvSite(euddraft 용 lupa 폴더)가 없습니다 — "
                               "boot(venv_site=…) 로 넣으세요 (lupa 는 부트 중에만 불러올 수 있다)")
            names = [x.strip() for x in (items.get("Preload") or "").split(",") if x.strip()]
            if "scrdb" not in names:
                names.append("scrdb")
                self.boot_sec.set("Preload", ", ".join(names))
        if not hook:
            return None
        if any(p.name == hook_name for p in self.plugins):
            raise EdsError("scrdb 훅 플러그인이 이미 있습니다: %s" % hook_name)
        settings = []
        if core:
            settings.append(("Core", os.path.abspath(core)))
        if build_id is not None:
            settings.append(("BuildId", str(int(build_id))))
        if manifest:
            settings.append(("Manifest", os.path.abspath(manifest)))
        if not frame:
            settings.append(("Frame", "0"))
        sec = Section(hook_name, settings,
                      comment="eudext.scrdb 훅: [MSQC] 뒤, 맵 플러그인 앞 (표지 블록·수신기·알림음, 매니페스트)")
        at = 0
        for i, p in enumerate(self.plugins):
            if p.name == HOOK_NAME:
                at = i + 1
        self.plugins.insert(at, sec)
        self.extra_files[hook_name] = scrdb.hook_source()
        return sec

    def _qc_section(self, key, lines):
        name = self.section_names.get(key, key)
        seen = {}
        sec = Section(name)
        for line in lines:
            k = line_key(line)
            if k in seen:
                if seen[k] == line.strip():
                    continue  # 똑같은 줄은 한 번만
                raise EdsError("[%s] 에 같은 키가 두 번 있습니다(euddraft 오류): %s" % (name, k))
            seen[k] = line.strip()
            sec.add_line(line)
        return sec

    def sections(self):
        out = [self.main]
        if self.boot_sec is not None:
            out.append(self.boot_sec)
        out.extend(self.pre_plugins)
        if self.msqc_lines:
            out.append(self._qc_section("MSQC", self.msqc_lines))
        if self.nsqc_lines:
            out.append(self._qc_section("NSQC", self.nsqc_lines))
        out.extend(self.plugins)
        if self.freeze is False:
            out.append(Section("freeze", [("freeze", "0")], comment="freeze 끔 (키가 있으면 값과 무관하게 꺼진다)"))
        elif self.freeze is True:
            out.append(Section("freeze"))
        names = [s.name for s in out]
        dup = {n for n in names if names.count(n) > 1}
        if dup:
            raise EdsError("같은 섹션이 두 번: %s" % ", ".join(sorted(dup)))
        return out

    def render(self):
        parts = []
        if self.header_comment:
            parts.append("\n".join(":: " + c for c in str(self.header_comment).splitlines()))
        parts.extend(s.render() for s in self.sections())
        return "\n\n".join(parts) + "\n"

    def write(self, path):
        """eds 를 쓰고, `extra_files`(sync 훅 등)를 eds 옆에 쓴다."""
        text = self.render()
        d = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
        for name, content in self.extra_files.items():
            with open(os.path.join(d, name), "w", encoding="utf-8", newline="\r\n") as f:
                f.write(content)
        return path


def write_eds(path, input_map, output_map, plugins, eudext_root=ROOT, venv_site=None, preload=(),
              pycache_prefix=None, msqc=(), freeze=False, relative=True, sync=None, **main_options):
    """한 번에 eds 를 쓴다. plugins: 이름 또는 (이름, 설정 dict) 목록. relative=True 면 경로를 eds 기준 상대로.

    sync: None(안 씀) / True(선언된 버스 전부 + 훅) / dict(`EdsDoc.add_sync` 인자)
    """
    eds_dir = os.path.dirname(os.path.abspath(path))

    def fix(p):
        if relative and (p.endswith(".py") or p.endswith(".eps") or p.endswith(".scx") or p.endswith(".scm")):
            return _rel(p, eds_dir) if os.path.isabs(p) else p
        return p

    doc = EdsDoc(fix(input_map), fix(output_map), **main_options)
    doc.boot(eudext_root=eudext_root, venv_site=venv_site, preload=preload, pycache_prefix=pycache_prefix,
             eds_dir=eds_dir if relative else None)
    for p in plugins:
        name, settings = (p, None) if isinstance(p, str) else p
        doc.add_plugin(fix(name), settings)
    doc.add_msqc(*msqc)
    if sync:
        doc.add_sync(**(sync if isinstance(sync, dict) else {}))
    doc.freeze = freeze
    return doc.write(path)
