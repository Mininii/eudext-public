# WP0 보고서 — 뼈대 구현과 eudplib 0.81 재측정 (2026-09-17)

기준 판: euddraft **0.11.0.1** (번들 파이썬 3.14.7, `sys.flags.ignore_environment = 1`) / eudplib **0.81.0**.
개발 venv: `C:\Users\whatd\.venvs\eud081` (파이썬 3.13.15). epScript 번역기는 venv 와 euddraft 가 **같은 파일**이다
(`libepScriptLib.dll` md5 `2366f206b2920759c1f493d88ccc403d`, 세 곳 동일).

실험 파일은 세션 스크래치패드 `…\scratchpad\wp0\` 에 있다(세션이 끝나면 사라질 수 있어 핵심 결과는 이 문서에 옮겼다).
- `probe081\map\` — (a) 경로 탐침 `pboot.py`/`plate.py`/`pmain.eps`/`probe_*.eds`, 로그 `run_*.log`, (c) `stdprobe.py` → `stdlib_081.json`
- `probe081\eps081.py` → `eps081_out.txt` — (b) 번역 조각 57개
- `probe081\retp\`, `probe081\objp\` — (b) 실제 컴파일 확인, `probe081\frz\` — (e) freeze, `probe081\venv\` — VenvSite
- `try1\multi*.py`, `leak*.py` — (d) 여러 번 빌드

---

## 1. 한눈에

| 항목 | 결과 |
|---|---|
| 시험 | `tests\run_all.py` **4파일 PASS, 판정 2,700개 통과 / 실패 0** (t_parts 2,591, t_emu 60, t_tools 40, t_build_example 9), 약 7초 |
| 예제 빌드 | `examples\hello.eds` → euddraft 0.11 **성공**(약 1초, chk 약 0.37MB, scx 약 46KB, freeze 꺼짐). 부트 뒤 `import eudext.errors`(.py), `import eudext._parts`(.eps), `onPluginStart` 안 지연 import 모두 성공. 산출물·`__epspy__`·바이트코드는 작업 폴더로만 간다 |
| 에뮬레이터 | DPS `emu.py` 는 **0.81 에서 고치지 않아도 돈다**(가로채기 두 이름이 그대로). 이식하면서 `_compat` 경유·게임 루프 시작점·처리기 표·메모리 표·스냅숏을 더했다 |
| 0.81 에서 달라진 것 (중요) | ① create-payload 콜백이 **프로세스에서 한 번만** 불린다 → 여러 번 빌드하면 변수 버퍼가 쌓인다(고침: `_compat.reset_build_state`) ② 위로 나가는 상대 import(`import ..shared.x`) **ImportError** ③ epScript 문자열 식·타입 변수·`import py_x` 허용 ④ 동결 euddraft 는 `PYTHON*` 환경 변수를 무시 ⑤ 번들 표준 모듈 목록 변경(`shlex`, `pdb`, `doctest`, `pydoc`, `webbrowser` 등 없음, `colorsys`·`configparser` 있음) ⑥ 필드에 패치 안 된 변수가 있으면 **빌드 때 EPError**(`Invalid fields for action`) |
| 그대로인 것 | 플러그인마다 `sys.path`·cwd 복원, `__file__` 없음, 부트 뒤 패키지 하위 모듈 import 가능, 비패키지 모듈 불가, `m.foo()`→`m.f_foo()` 규칙, 키워드 인자 번역, `return a < b;` 빌드 오류, `EUDBranch(_actions)` 변수 필드 미패치 |
| freeze 끄기 | `[freeze]` 섹션에 **`freeze` 키가 있으면**(값 무관: `0`, `1`, 키만) 꺼진다. 섹션이 없거나 비어 있으면 켜진다 |
| 추가 요청 | `_parts.isub32`(wrap, `a is b`→`a << 0`)·`isub_sat32`(포화) 추가, eudplib `v -= v` = 0xFFFFFFFF 버그를 0.81.0 에서 재확인(시험 고정) |

---

## 2. 만든 파일

| 파일 | 내용 |
|---|---|
| `__init__.py` | `__version__ = "0.0.1"`, `VERSION`. import 없음 |
| `_compat.py` | 판 검사 `check()`(0.81.x 아니면 경고, 비공개 이름 18개 존재 확인), 판별 `is_const/is_var/is_varbase/is_eudfunc/split64_const`, CP 캐시 `cpcache_var/cpcache_cond`, `isolated_scope()`(새 블록 관리자 + 트리거 범위), `reset_build_state()`/`register_build_reset()`, `set_game_loop_start()`, `capture_payload()`(SaveMap 가로채기), `chk_string_section()`, `eps_compile()` |
| `_parts.py` | `branch`, `jump_if`, `jump_if_not`, `once_branch`, `write_addr`, `set_masked`(+`f_set_masked`), `and_const`(+`f_and_const`), `isub32`, `isub_sat32`, `cp_fix`, `SubLabel` + `call_sub`, `all_const`, `has_var_fields` |
| `errors.py` | `EudextError(EPError)`("[eudext] " 접두), `fail`, `require`, `warn`, `check_range`, `check_choice` |
| `boot.py` | 부트 플러그인. 키 소문자화, **값 끝 `<공백>; …` 제거**, `;`/`#`/`::` 로 시작하는 키 무시, `EudextRoot`(앞)·`VenvSite`(끝)·`Preload`·`PycachePrefix`, 다른 위치의 eudext 가 이미 있으면 오류, 한 줄 출력 |
| `testing\__init__.py`, `emu.py`, `scmodel.py`, `harness.py`, `base.scx` | 에뮬레이터(4절), SC 모델(게임 메모리 초기값, Switch/SetSwitch), 차등 시험 틀, CBTest.scx 사본(md5 동일) |
| `tools\__init__.py`, `cost.py`, `edsgen.py`, `build.py` | 비용 보고(COSTS.md 덧붙이기), eds 생성(`[MSQC]`/`[NSQC]` 자리), 단독 빌드·euddraft 빌드(작업 폴더로 옮겨 실행, 표준 입력 비움) |
| `examples\hello.py`, `hello.eps`, `hello.eds` | 부트 뒤 import 예제 |
| `tests\_common.py`, `t_emu.py`, `t_parts.py`, `t_tools.py`, `t_build_example.py`, `run_all.py` | 시험(모두 저장소에 `__pycache__` 를 남기지 않는다) |
| `docs\COSTS.md` | `_parts` 측정 표 |

---

## 3. (a) euddraft 0.11 경로 규칙

근거: upstream `euddraft\pluginLoader.py`·`euddraft.py`(0.11.0.1 태그 근처) + 실측 로그 `probe081\map\run_a_abs.log`, `run_a_rel.log`, `run_rel_*.log`.

| 항목 | 0.9.10.11 (R3 3.1) | **0.11.0.1 실측** |
|---|---|---|
| eds 를 **절대 경로**로 넘길 때 `sys.path[:2]` | `[eds폴더, lib\library.zip]` | 같음. eds 폴더가 끝까지 0번에 남는다 |
| eds 를 **상대 경로**(작업 폴더 = eds 폴더)로 넘길 때 | (시험 안 함) | `[lib\library.zip, eds폴더, lib…]` — eds 폴더는 **플러그인을 읽는 동안만** 1번 자리(`pluginDir` 삽입). `onPluginStart` 때는 없다 → `tools\build.py` 는 절대 경로로 넘긴다 |
| 플러그인마다 `sys.path`·cwd 복원 | 됨 | **됨** (`finally: os.chdir, sys.path[:] = initialPath`) |
| `__file__` | 없음 | **없음** (`types.ModuleType` + `SourceFileLoader.exec_module`, `__loader__` 는 있음) |
| 부트 뒤 `import eudprobe.lazy2`(패키지 하위, 처음) | 성공 | **성공** (.py 플러그인·`onPluginStart`·.eps 모두) |
| 부트 뒤 비패키지 `import rootmod2` | 실패 | **실패** (ModuleNotFoundError) |
| eds 폴더 모듈 `import localpy` | 성공 | 성공 (절대 경로 실행 기준) |
| .eps: `import pkg.epsmod`(패키지 안 .eps) | 성공 | **성공** (`EPSFinder` 는 여전히 `sys.meta_path` 끝) |
| .eps: `import .helper`(같은 폴더) | 성공 | **성공** (번역: `try: _RELIMP(".", "helper") except ImportError: from . import helper`) |
| .eps: `import ..helper`(하위 폴더에서 eds 폴더로) | — | **성공** (목표가 sys.path 안) |
| .eps: `import ..shared.pkg.relmod`(sys.path 밖으로) | 성공(최상위 `relmod` 로 따로 올라감) | **실패**: `ImportError: attempted relative import beyond top-level package` (`_RELIMP`, 빌드 중단) |
| 부트에서 `VenvSite` 를 끝에 붙인 뒤 다음 플러그인 | — | VenvSite **없음**, `import lupa` 실패. 부트(또는 그 플러그인) **읽는 동안** import 한 `lupa.lua54` 는 뒤 플러그인에서 그대로 쓸 수 있다(Lua 5.4) |
| 환경 변수 `PYTHONPYCACHEPREFIX`, `PYTHONDONTWRITEBYTECODE` | — | **무시**(`sys.flags.ignore_environment = 1`). 부트 플러그인 자신의 `.pyc` 는 `boot.py` 옆 `__pycache__` 에 생긴다 → `PycachePrefix` 키 + `build.py` 가 boot.py 사본을 작업 폴더에서 실행 |
| 플러그인 오류 + 표준 입력 비움 | — | `input()` 이 EOFError → 종료 코드 **127**, 멈추지 않음 |

eds 문법(upstream `readconfig.py`, 실측 `run_a_abs.log` 의 `settings raw`):
- 값은 줄 끝까지다: `Trail : value ; inline comment` → `'value ; inline comment'`. **끝 주석 불가.**
- `; semicolon line` → 키 `'; semicolon line'`, 값 `''`(주석이 아니다). **주석은 `::` 로 시작하는 줄만.**
- `[머리] ; 주석` 은 머리로 읽히지 않는다.

## 4. 에뮬레이터 이식에서 바뀐 점 (`testing\emu.py`)

| 항목 | DPS (0.76.14) | eudext (0.81.0) |
|---|---|---|
| SaveMap 가로채기 | 파일 안에서 직접 `savemap.apply_injector`, `apply_injector.initialize_payload` 교체 | `_compat.capture_payload()` 로 옮김. **0.81 에서도 두 이름이 같은 자리에 있어 그대로 동작**(DPS 파일 복사본이 수정 없이 통과) |
| 재배치 | prttable/orttable, `RlocInt.offset/rlocmode` | 같음(Rust `RlocInt_C` 도 두 속성 있음). 0.81 은 `CompressPayload(False)` 미지원 → 적층 필수 |
| 빌드 전 초기화 | 없음 | `Program.build()` 가 `_compat.reset_build_state()` 를 먼저 부른다(7절) |
| 루프 | `EUDInfLoop` + `EUDDoEvents` | 같음 + euddraft 처럼 루프 머리에서 **게임 루프 시작점** 설정(`EUDLoopNewUnit` 의 `_UniqueIdentifier` 초기화가 이 지점을 요구, 없으면 SaveMap 오류) |
| 출력 파일 | `%TEMP%\eud_emu_out.scx` | `tempfile.gettempdir()` 또는 `out=` (시험은 `EUDEXT_WORK` 로 보냄) |
| 조건·액션 확장 | 없음(모두 거짓·기록) | `Machine.cond_handlers`/`act_handlers` 표 → `scmodel` 이 Switch(11)/SetSwitch(13) 를 끼움. 모르는 것은 `Machine.unknown` 에 집계 |
| 메모리 | dword 만 | `db/setdb`, `read_bytes/write_bytes`, `init_mem(표)`, `snapshot/restore`, `set_var/addr` |
| 범위 검사 | `base ≤ t < base+0x10000000` | `base-8 ≤ t < base+페이로드 길이`(더 엄격), 실행 한도는 사이클마다 |
| 기록 | 무제한 | `log_limit` 20,000 |
| 오류 | `RuntimeError` | `EmuError(RuntimeError)` |

`scmodel`: `game_memory(local_player, players, cp, races, forces)` → 0x512684, 0x6509B0, 플레이어 표(0x57EEE0 + 36i: id, storm id, 형·종족·세력 바이트, 사람 = 2). 스위치 표 `SWITCH_TABLE = 0x58DC40`(256비트; MRGN 0x58DC60 바로 앞 32바이트 — **인게임 미확인**), SetSwitch 4/5/6/11, Switch 상태 2/3.

`harness.Suite`: 케이스 본문을 `SubLabel` 서브루틴(격리 범위)으로 만들고 `mode` 변수로 한 사이클에 하나만 부른다. 본문 생성 예외는 그 케이스만 "빌드 실패", 실행 예외는 기록 뒤 스냅숏 복원. `check`/`diff`(경계값 조합 + 치우친 난수)/`trace`(여러 사이클)/`expect_true`, 실행 수는 빈 사이클과 호출 오버헤드(빈 케이스로 잼, 3)를 뺀 값. 실측: 변이 시험(변수 액션을 `EUDBranch(_actions)` 에 그대로 넣는 판)은 0.81 이 빌드 때 EPError 를 내고, 틀이 그 케이스만 실패로 기록했다.

## 5. (b) epScript 번역 (0.81.0) — 0.76.14(R3 2절)와 비교

57조각, 결과 `eps081_out.txt`. "실컴파일" 은 번역문을 실제로 실행해 SaveMap 까지 간 결과.

| epScript | 0.81.0 번역 / 결과 | 0.76.14 와 |
|---|---|---|
| `m.foo(a)` / `m.f_foo(a)` / `m.foo_bar(a)` | `m.f_foo(a)` / `m.f_f_foo(a)` / `m.f_foo_bar(a)` | 같음 |
| `m.Foo(a)`, `m.EUDFoo(a)`, `m.CONST_X(a)` | 그대로 | 같음 |
| `m.sub.foo(a)`, `m.Int64.from_var(a)` | 그대로(두 단계는 접두사 없음) | 같음 |
| `m.CONST`, `m.foo`(호출 아님) | 그대로 | 같음 |
| `const add = m.add; add(a, a);` | `add = _CGFW(lambda: [m.add], 1)[0]`, `add(a, a)` | 같음 |
| 정의 없는 전역 `foo(a)` | 오류 | 같음 |
| `setcurpl(a)`, `dwread_epd(a)`, `printAll(…)` | `f_setcurpl`, `f_dwread_epd`, `f_printAll` | 같음 |
| `if (cmp.lt(a, 1))` | `EUDIf()(cmp.f_lt(a, 1))` | 같음 |
| `import eudext.i64 as i64;` | `from eudext import i64 as i64` | 같음 |
| `import eudext.fmt;` 뒤 `eudext.fmt.foo()` | 오류(마지막 이름만 묶임) | 같음 |
| `import eudext.sub.mod as sm;` (세 단계) | `from eudext.sub import mod as sm` | (0.76 미시험) |
| `import eudext._parts as parts;` (밑줄 이름) | `from eudext import _parts as parts`, `parts.f_and_const(…)` | (미시험) — 된다 |
| `import .sibling as sb;` | `try: sb = _RELIMP(".", "sibling")` / `except ImportError: from . import sibling as sb` | **바뀜**(대체 경로 추가) |
| `import ..shared.x.relmod as rm;` | 번역은 됨, **실행 시 ImportError**(3절) | **바뀜** |
| `import py_mylib;` | `import mylib` | **바뀜**(0.76 오류) |
| `from a import b;` | 문법 오류 | 같음 |
| 전역 `const I = m.Int64(1, 2);` | `_CGFW(lambda: [...], 1)[0]` | 같음 |
| 전역 `var q = m.Obj();` | `_TYGV([None], lambda: [...])` → **실컴파일 EPError `Invalid initval: <repr>`** | 번역 함수 바뀜(`_IGVA`→`_TYGV`), 결과(오류) 같음 |
| 지역 `var q = m.Obj(a);` | `_TYLV([None], [...])` → **실컴파일 EPError `invalid amount: <repr>`** | `_LVAR`→`_TYLV`, 결과 같음. 두 경우 모두 `__repr__` 안내문이 보인다(`dont_flatten` 객체) |
| 지역 `const q = m.Obj(a); q = a;` | 오류 | 같음 |
| 전역 `static var sv = 3;` | 오류 | 같음 |
| `var x: TrgUnit = a;` (지역) / `static var x: T = 0;` / 전역 `var gx: T = 0;` | `_TYLV([TrgUnit], [a])` / `_TYSV([T], [0])` / `_TYGV([T], …)` | **새로 됨** |
| `var x: i64.Int64 = a;` | `_TYLV([i64.Int64], [a])` (실행 시 `T.cast`) | 새로 됨 — 64비트 값 타입은 여전히 불가(R3 4.1) |
| `const gx: T = 0;` | 오류 | — |
| `const s = "abc";`(전역) / `'abc'`(지역) | `_CGFW(lambda: ["abc"], 1)[0]` / `s = 'abc'` | **새로 됨** |
| `"ab" + "cd"`, `"a,b".split(",")` | 그대로 | **새로 됨** |
| f-문자열 `f"x{a}"` | 오류 | — |
| `a < b` (조건 / 값 / 삼항) | `a >= b, neg=True` / `EUDNot(a >= b)` / `EUDTernary(a >= b, neg=True)` | 같음 |
| `a > b`, `a != b` | `a <= b, neg=True`, `a == b, neg=True` | 같음 |
| `!(a < b)` | `(a >= b)` | 같음 |
| `a << b`, `a << 3`, `a <<= 2` | `_LSH(a,b)`, `_LSH(a,3)`, `a.__ilshift__(2)` | 같음 (`_LSH`: 변수면 `f_bitlshift`, 아니면 파이썬 `<<` → const 값 타입에서는 `__lshift__` 가 불린다) |
| `a -= b; a--; a -= a;` | `a.__isub__(b)`, `a.__isub__(1)`, **`a.__isub__(a)` → 0xFFFFFFFF**(eudplib 버그, S8) | 같음 |
| `X.v = b; X.v += b; X.v -= b;` | `_ATTW(X,'v') << b`, `.__iadd__(b)`, `.__isub__(b)` | 같음 |
| `return a < b;` | `EUDReturn(EUDNot(a >= b))` → **실컴파일 EPError**(`Invalid fields for action`) | 같음 |
| `return a == b;` | → **실컴파일 EPError `Orphan condition`** | R3 추측 확인 |
| `return a < b ? 1 : 0;` | `EUDReturn(EUDTernary(…)(1)(0))` → 실컴파일 성공 | 같음 |
| `nf.Dec(v, width=5, fill="0")` / `nf.dec(v, width=5)` | 그대로 / `nf.f_dec(v, width=5)` | 같음(키워드 인자 된다) |
| `f_dwread_epd(a, ret=[a])` | `ret=_ARR(FlattenList([a]))` | — (리스트 리터럴은 `_ARR` 로 바뀐다: 파이썬 리스트를 넘기려면 `py_list(…)`) |
| `s.printf("{}", a, end=1)` | 그대로 | 같음 |
| `function f(a, b = 3)`, `1.5`, `a ** 2` | 오류 | 같음 |
| `0x100000000` | 파이썬 int | 같음 |
| `object P {…}`, `foreach (i : py_range(3))` | EUDStruct 클래스 / 파이썬 for | 같음 |

## 6. (c) 번들 표준 모듈 (파이썬 3.14.7, `sys.stdlib_module_names` 297개 전수)

방법: 탐침 플러그인이 모든 이름을 `importlib.import_module`(부작용 모듈 7개는 `find_spec` 만). 결과 `stdlib_081.json`.

- **없는 공개 모듈 56개**: `bdb, cProfile, cmd, compileall, curses, dbm, doctest, ensurepip, fcntl, filecmp, fileinput, graphlib, grp, imaplib, mailbox, modulefinder, nturl2path, optparse, pdb, pickletools, plistlib, poplib, posix, profile, pstats, pty, pwd, pyclbr, pydoc, readline, resource, sched, shelve, shlex, smtplib, socketserver, sqlite3, sre_compile, sre_constants, sre_parse, symtable, syslog, tabnanny, termios, timeit, tomllib, trace, tty, unittest, uuid, venv, wave, webbrowser, wsgiref, zipapp, zoneinfo`
- **find_spec 도 없음(시험 안 한 7개)**: `antigravity, idlelib, pydoc_data, this, tkinter, turtle, turtledemo`
- 없는 내부 모듈: `_curses, _curses_panel, _dbm, _gdbm, _sqlite3, _tkinter, _uuid, _zoneinfo, _pydecimal, _pyio, _pylong, _pydatetime, _py_abc, _markupbase, _posixshmem, _posixsubprocess, _osx_support, _aix_support, _android_support, _apple_support, _ios_support, _scproxy`
- **있는 공개 모듈 131개**: `abc annotationlib argparse array ast asyncio atexit base64 binascii bisect builtins bz2 calendar cmath code codecs codeop collections colorsys compression concurrent configparser contextlib contextvars copy copyreg csv ctypes dataclasses datetime decimal difflib dis email encodings enum errno faulthandler fnmatch fractions ftplib functools gc genericpath getopt getpass gettext glob gzip hashlib heapq hmac html http importlib inspect io ipaddress itertools json keyword linecache locale logging lzma marshal math mimetypes mmap msvcrt multiprocessing netrc nt ntpath numbers opcode operator os pathlib pickle pkgutil platform posixpath pprint py_compile pyexpat queue quopri random re reprlib rlcompleter runpy secrets select selectors shutil signal site socket ssl stat statistics string stringprep struct subprocess sys sysconfig tarfile tempfile textwrap threading time token tokenize traceback tracemalloc types typing unicodedata urllib warnings weakref winreg winsound xml xmlrpc zipfile zipimport zlib`
- 0.9.10.11(R3 3.3) 대비: `colorsys`, `configparser` **생김**. `bdb, cmd, doctest, pdb, pydoc, shlex, plistlib, socketserver, webbrowser, nturl2path` **없어짐**(R3 목록에 없던 것).
- 제3자: `openpyxl 3.1.5`, `rich`, `typing_extensions`, `freezeMpq`, `draw` 있음. `colorama`, `Cython`, `lupa`, `numpy` 없음.
- eudext 본체가 쓰는 표준 모듈(`contextlib, importlib, warnings, os, re, sys, random, struct, tempfile, collections, traceback`)은 모두 있다. 도구(`argparse, datetime, glob, shutil, subprocess, time, types`)도 있다.

## 7. (d) 한 프로세스에서 여러 번 SaveMap

실험: `try1\multi.py`, `multi_str.py`, `leak*.py`, 고정 시험 `tests\t_emu.py` 2절.

| 현상 (eudplib 0.81.0) | 원인 | 영향 | 처리 |
|---|---|---|---|
| 빈 빌드를 되풀이하면 페이로드가 **+2,448B 씩** 는다 (105,708 → 108,156 → 110,604) | `RegisterCreatePayloadCallback` 콜백이 Rust `PayloadBuilder` 에서 **첫 호출 뒤 비워진다**(등록 A → 호출 → 등록 B → 호출 두 번 = `['A','B']`). 그래서 `EUDVarBuffer`·`EUDCustomVarBuffer`·점프 버퍼가 새로 안 만들어지고 앞 빌드의 변수(빌드당 34개)가 계속 실린다. `_userp_fws`(IsUserCP 등록)도 안 비워져 옛 `UserPBuffer` 가 딸려 온다 | 값은 맞다(에뮬레이터 확인). 용량만 는다. `get_trace_map`(추적표)도 첫 빌드 뒤에는 안 불린다 | `_compat.reset_build_state()` 가 `vbuf._register_new_varbuffer/_register_new_custom_varbuffer`, `jumptable.register_new_jumpbuffer`, `userpl._rcpc_reset_userp` 를 직접 부른다 → 크기 고정(시험 고정) |
| 주 함수 안 `EUDOnStart` 가 k 번째 빌드에서 **k 번** 실행 | `mainloop._start_functions2` 를 비우지 않음 | 초기화 중복 | `reset_build_state` 가 비운다(시험 고정) |
| 둘째 빌드에서 `_set_game_loop_start()` 가 "already set" | `_game_loop_start` Forward 가 설정된 채 남음 | euddraft 식 틀을 venv 에서 두 번 빌드하면 오류 | `reset_build_state` 가 `Reset()` |
| 첫 빌드에서 만든 **EUDFunc 본문은 재사용**된다 | 본문 트리거가 파이썬 객체로 남음(`_fstart`) | 결과는 맞다(`f_inc(7)+22 = 30` 세 번 동일). 다시 만들 수 없다("already compiled") | 그대로 둔다 |
| 그 본문에 **구운 문자열 번호**가 다음 빌드에서 틀린다 | `DisplayText("…")` 는 만들 때 `GetStringIndex` 로 번호를 정한다. LoadMap 하면 문자열 표가 새로 시작 | 둘째 빌드 STR 에 그 문자열이 없다(다른 문자열이 같은 번호를 가짐) | **해결 안 함**. 문자열을 보는 시험은 한 빌드에 모은다(harness 가 한 빌드에 여러 케이스를 모으는 이유). 시험으로 고정(`[True, False]`) |
| LoadMap 없이 SaveMap 두 번 | SaveMap 이 불러온 chk 의 STR(페이로드 포함)·TRIG·MRGN 을 제자리에서 고침 | 둘째 출력 STR 이 첫 페이로드까지 품고 커진다(110,928 → 244,872B) | **빌드마다 LoadMap**(emu·harness·cost·build 모두 그렇게 함) |

eudext 모듈 규칙(제안): 빌드마다 되돌릴 모듈 상태는 `RegisterCreatePayloadCallback` 이 아니라 `_compat.register_build_reset(fn)` 에 등록한다. 모듈별 `_reset()` 대신 이 훅 하나로 모은다. `functools.cache` 로 만든 상수별 EUDFunc 는 재사용해도 되지만, 문자열을 굽는 본문이면 여러 빌드 시험에서 주의.

## 8. (e) freeze 끄는 법 (`probe081\frz\`, 빈 맵 + 작은 플러그인)

| eds | `[[ freeze activated ]]` | `Stage 4/3`(freezeMpq) | chk | scx |
|---|---|---|---|---|
| `[freeze]` 없음 | **켜짐** | 있음 | 1.167MB | 133,584 |
| `[freeze]` (빈 섹션) | 켜짐 ("Freeze plugin loaded") | 있음 | 1.123MB | 130,816 |
| `[freeze]` + `freeze : 0` | **꺼짐** | 없음 | 0.367MB | 46,092 |
| `[freeze]` + `freeze : 1` | 꺼짐 | 없음 | 0.369MB | 45,680 |
| `[freeze]` + `freeze` (키만) | 꺼짐 | 없음 | 0.367MB | 45,687 |

근거: `pluginLoader.py` — `if "freeze" in config["freeze"]: freeze_enabled = False`(값을 보지 않음), 기본값 `freeze_enabled = True`. `[main] sectorSize` 기본 15. 파이썬 단독 빌드(`tools\build.py standalone`)에는 freeze 가 없다. `tools\build.py euddraft --freeze off`(기본)가 `freeze : 0` 을 넣고, `keep` 은 eds 그대로 둔다.

## 9. `_parts` 이식 메모 (0.81)

- `EUDBranch(_actions=…)` 는 0.81 에서도 액션 변수 필드를 패치하지 않는다(`trigger/branch.py:_branch_sub`). 대신 0.81 은 **RawTrigger 를 만들 때 필드를 검사**해서 조용히 틀리는 대신 `EPError: Invalid fields for action` 을 낸다.
- 0.81 `SetNextTrigger(target)`(EUDJump 방식)으로 분기 꼬리 점프 트리거를 없앴다(변수 액션 분기 호출 4 / 실행 1~5, DPS 판보다 1씩 적음). 1회 분기의 **머리**는 실제 트리거여야 하므로 그대로 `RawTrigger(nextptr=…)`.
- `and_const`: 0.81 은 마스크 칸 접근이 공개(`getMaskAddr`, `SetMask`)가 됐고, `v & 상수` 가 DPS 판과 같은 호출 2 / 실행 3 이라 감싸기만 했다(원본 변수 트리거를 건드리지 않음).
- `cp_fix`: 0.81 CP 캐시는 `EUDXVariable(EPD(0x6509B0), SetTo, 0)` 이다(값 칸 주소는 같음). 액션 필드 순서도 같아 그대로 옮겼다.
- `call_sub(label)` → `SubLabel` 객체 + `call_sub(label, conds=None, acts=None, preserved=True)`. 본문은 `with sub.define():` 로 격리 범위에 만든다(정의가 호출보다 뒤여도 됨, 두 번 정의하면 오류).
- **추가(코디네이터 요청)**: `isub32(a, b)` — `a is b` → `a << 0`, 정수 → `Add(-b)`(0 이면 트리거 없음), EUDVariable → eudplib `a -= b`, EUDLightVariable 등 → 임시 변수에 `~b+1` 을 만들어 더함. `isub_sat32(a, b)` — `a is b` → `a << 0`, 정수 → `SubtractNumber`, 변수 → `SeqCompute(Subtract)`. 시험: 경계값 9×9 + 난수 150(변수), 상수 0/1/0x80000000/0xFFFFFFFF × 39, `x -= x`(EUDVariable·EUDLightVariable), 0−1, 0−0xFFFFFFFF, 0xFFFFFFFF−0xFFFFFFFF, 5−0xFFFFFFFF, 0x80000000−0x80000001, EUDLightVariable 대상 wrap/포화. **eudplib `v -= v` = 0xFFFFFFFF 를 0.81.0 에서 다시 확인**(판이 바뀌면 시험이 알린다). 참고: `EUDLightVariable -= 변수` 는 0.81 에서 빌드 오류(상수만 됨).
- 비용: `docs\COSTS.md` (20항목).

## 10. DESIGN.md 수정 제안 (문장)

- **2.1 ENV 실측** 첫 항목을: "빌드 성공. 플러그인 `sys.path` 앞머리는 eds 를 **절대 경로**로 넘기면 `[eds 폴더, lib\library.zip, lib, …]`(eds 폴더가 빌드 내내 남음), 작업 폴더 기준 상대 경로면 `[lib\library.zip, eds 폴더(읽는 동안만), lib, …]` 이다. 자동 빌드는 절대 경로로 넘긴다. `__file__` 은 없고 `__loader__` 는 있다. 동결 euddraft 는 `PYTHON*` 환경 변수를 무시한다(`sys.flags.ignore_environment=1`)."
- **2.1** freeze 항목을: "`[freeze]` 섹션에 `freeze` 키가 있으면(값과 무관) freeze 가 꺼진다. 섹션이 없거나 비면 켜진다(chk 0.37MB → 1.17MB). 시험 빌드는 `[freeze]` / `freeze : 0`."
- **2.1** 추가: "플러그인 오류 때 표준 입력을 비워 두면 euddraft 가 종료 코드 127 로 끝난다."
- **2.2** 폴더 구조에 `testing\base.scx`, `tools\build.py`, `tests\_common.py`, `tests\run_all.py`, `tests\t_tools.py`, `tests\t_build_example.py`, `examples\hello.{py,eps,eds}` 를 더한다.
- **2.3** eds 예의 끝 주석(`; 반드시 …`, `; shape(lupa…)`, `; 부트 중에…`)을 지우고 다음 문장을 넣는다: "eds 는 값이 줄 끝까지이고 끝 주석이 없다. 주석 줄은 `::` 로 시작한다(`;` 로 시작하는 줄은 값 없는 키가 된다). `boot.py` 는 방어로 값 끝의 `<공백>; …` 을 떼지만 eds 에 쓰지 않는다."
- **2.3** 부트 키에 "`PycachePrefix`(선택): `sys.pycache_prefix`. 부트 플러그인 자신의 `.pyc` 는 막지 못하므로 `tools\build.py` 는 boot.py 사본을 작업 폴더에서 실행한다." 를 더한다.
- **2.3** 마지막 문단을: "위 경로 규칙은 0.11.0.1 에서 다시 쟀다(WP0 보고서 3절). 달라진 것: sys.path 밖으로 나가는 상대 import(`import ..shared.x`)는 ImportError. 같은 폴더·sys.path 안의 상대 import 는 된다." 로 바꾼다.
- **2.4** "없음" 목록을 WP0 보고서 6절의 56개로 바꾸고, 특히 "`shlex`, `pdb`, `doctest`, `pydoc`, `webbrowser`, `plistlib`, `socketserver` 도 없다(0.9.10.11 에는 있었다)" 를 적는다. "탐침에 넣지 않은 모듈은 WP0 이 채운다" 문장은 지운다.
- **3.1** 끝에: "내부 모듈(`_parts`)도 epScript 에서 `import eudext._parts as parts;` 로 불러올 수 있다(밑줄 이름 허용)."
- **3.11** 에 추가: "0.81 에서 된다: 문자열 식(`const s = "abc";`, 연결, 메서드), 타입 변수(`var x: T = v;`, `static var x: T`), `import py_x;`(→ `import x`), 세 단계 import(`import a.b.c as d;`). 여전히 안 된다: `from … import`, 전역 `static var`, `const x: T`, 기본 인자, f-문자열, 실수, `**`. `return a == b;` 는 `Orphan condition` 오류. epScript `a -= a;` 는 eudplib 버그로 0xFFFFFFFF 가 되므로 `a = 0;` 으로 쓴다. 인자에 리스트 리터럴 `[a]` 는 `_ARR(...)`(EUDArray)로 번역된다."
- **4.1 `_compat`** 을: "`check(strict=False)`: eudplib 판이 **0.81.x** 가 아니면 경고, 비공개 이름이 없으면 오류. 접근자: `cpcache_var`, `cpcache_cond`, `isolated_scope`, `capture_payload`, `reset_build_state`, `register_build_reset`, `set_game_loop_start`, `chk_string_section`, `eps_compile`, 판별 `is_const/is_var/is_varbase/is_eudfunc/split64_const`. (`varbuffer_initvals`, `funcbody_hook` 은 필요한 WP 가 더한다.)"
- **4.1 `_parts`** 목록에 `write_addr`, `isub32`/`isub_sat32`(3.5-6), `all_const`/`has_var_fields` 를 더하고, `call_sub(label)` 을 "`SubLabel`(`with sub.define():`) + `call_sub(label, conds=None, acts=None, preserved=True)`" 로, `and_const` 를 "0.81 `v & 상수` 감싸기(호출 2 / 실행 3)" 로 바꾼다.
- **5.1** 끝 항목(모듈 상태 초기화)을: "eudplib 0.81.0 은 create-payload 콜백을 첫 빌드에서만 부른다. 한 프로세스에서 여러 번 빌드하려면 빌드마다 `LoadMap` + `_compat.reset_build_state()`(emu·harness·tools 는 자동). eudext 모듈의 빌드별 상태는 `_compat.register_build_reset(fn)` 에 등록한다. 첫 빌드에서 만든 EUDFunc 본문은 재사용되며, 본문에 구운 문자열 번호는 다음 빌드에서 틀리므로 문자열 결과를 보는 시험은 한 빌드에 모은다." 로 바꾼다.
- **5.1** 에뮬레이터 설명에 "게임 루프 시작점 설정, 조건·액션 처리기 표(`cond_handlers`/`act_handlers`), 메모리 초기값 표, 스냅숏" 을 더하고 확장 표의 "Switch 조건 / SetSwitch", "게임 메모리 초기값" 행에 "(WP0 완료)" 를 단다. 스위치 표 주소 0x58DC40 은 인게임 확인 항목.
- **5.2** 에 "페이로드 증가분은 적층 배치 노이즈(±1KB) 때문에 같은 코드를 40벌 넣고 나눈 값을 적는다(참고값)." 를 더한다.
- **5.3** 에 "`tools\edsgen.EdsDoc`(`boot()`, `add_plugin()`, `add_msqc()`/`add_nsqc()` = WP13 자리, `freeze`), `tools\build.py euddraft <eds> --work <폴더>`(eds 폴더의 플러그인과 boot.py 사본을 작업 폴더로 옮기고 경로를 절대 경로로, 출력·`__epspy__`·바이트코드가 저장소에 남지 않음)" 를 적는다.
- **6.1 WP0 행**: "완료(2026-09-17)" 표시.

## 11. 막힌 점·미확인

- 막힌 것은 없다.
- 미확인(인게임): 스위치 표 주소(0x58DC40), 에뮬레이터의 마스크 Add/Subtract 식(S8 8절 결과 대기), `IsUserCP`·로컬 번호 모델.
- eudplib 쪽: create-payload 콜백이 한 번만 불리는 것은 upstream 버그일 가능성이 크다(`maprw/savemap.py` 의 `get_trace_map` 도 영향). 판이 올라가면 `reset_build_state` 가 부르는 비공개 이름 4개를 다시 확인한다(`check()` 가 없으면 오류를 낸다).
- `_compat` 이 쓰는 비공개 이름은 18개다(`_REQUIRED`). eudext 의 다른 파일은 비공개 이름을 쓰지 않는다(시험·도구 포함, 에뮬레이터 가로채기도 `_compat` 경유).
- 여러 빌드에서 문자열 번호가 틀리는 문제는 해결하지 않았다(7절).
