# eudext 설계도 (v0.1, 2026-09-17)

새 맵 코드를 eudplib(파이썬·epScript)으로 짤 때 쓰는 공용 라이브러리의 설계다.
CtrigAsm 에는 있었지만 eudplib 에는 없는 기능, 그리고 사용자 맵마다 반복되던 틀(G_CB 스포너, 건물 스택,
DisplayPrint, EXCC 등)을 eudplib 방식으로 제공한다. 이 문서를 보고 모듈별로 나눠 병렬로 구현하는 것이 목표다.

이름은 `eudext` 로 정했다(2026-09-17, 7절 D1). 기준 판은 euddraft 0.11.0.1 / eudplib 0.81.0 이다(D2).

> **작업 저장소 (2026-09-17)** — 이 설계도와 eudext 는 GitHub `Mininii/eudext` 저장소의 `eudext/` 가 정본이다(Ubuntu VS Code Server 에서 이어 작업).
> 문서의 Windows 경로(`MapSource\Py\…`, `ScmDraft 2\…`, `C:\euddraft0.11.0.1`, `.venvs\eud081` 등)는 저장소 최상위 `README.md` 의 **경로 대응표**로 바꿔 읽는다.
> 참고 소스는 `reference/`, 동봉한 eudplib·euddraft 는 `vendor/` 에 있다.

> **판 기준 변경 (2026-09-17)** — 조사 문서(R1~R4b)는 eudplib 0.76.14 에서 했다. 기준을 0.81.0 으로 올렸으므로
> R3 의 실측(euddraft 경로 규칙, epScript 번역, 번들 표준 모듈, 에뮬레이터 가로채기)은 **WP0 에서 0.81 로 다시 확인**한다.
> 0.81 에서 달라진 것은 R3 4절 표에 있다(변수끼리 `<`·`>` 버그 수정, `EUDArray` EPD 기본, scdata, epScript 타입 변수 등).

근거 자료:

| 자료 | 위치 |
|---|---|
| CtrigAsm ↔ eudplib 기능 비교 | `MapSource\Py\CtrigAsm_vs_eudplib\` (README = 결론) |
| 이 설계의 조사 문서 5개 | `docs\research\` — R1 맵별 사용량, R2 DPS 이식 계층 재고, R3 eudplib 규약·epScript·최신판, R4a 총알·서식·글자 효과·채팅, R4b 입력·CX Paint·수학·기타 |
| 시제품·실험 | `docs\proto\` (Int64 시제품, 에뮬레이터 시험, lupa 로 CB Paint 돌리기, 비용 측정) |
| DPS 이식 계층·명세 | `ScmDraft 2\DPS_eud\eud\` (`ctrig\*.py`, `spec\G1~G9`, `tests\emu.py`) — DPS_Enhance 저장소 `eudplib-port` 브랜치 |
| 용량 원리 | `MapSource\Library\EPSCRIPT_TRIGGER_BUDGET.md` 2·4절 |

---

## 0. 한눈에

### 0.1 핵심 결정

| 주제 | 결정 | 근거 |
|---|---|---|
| 기준 판 | euddraft **0.11.0.1** / eudplib **0.81.0** (번들 파이썬 3.14.7). `C:\euddraft0.11.0.1` 에 **나란히 설치**하고, 기존 CtrigAsm 맵·DPS 이식 계층이 쓰는 `C:\euddraft0.9.2.0`(0.9.10.11 / 0.76.14)은 그대로 둔다. 0.76.14 호환은 목표가 아니다 | 사용자 결정 D2, R3 4절 |
| 위치·형태 | `MapSource\Py\eudext\` **평평한 패키지**(`import eudext.i64 as i64;`) | R3 3.2 |
| 불러오기 | eds 맨 앞 **부트 플러그인**이 `sys.path` 추가와 `import eudext` 까지 끝낸다 | R3 3.1 (euddraft 가 플러그인마다 sys.path 를 되돌림) |
| 64비트 | 파이썬 클래스 `Int64` 안에 `EUDVariable` 두 개(lo, hi). EUDStruct·EUDVariable 상속은 쓰지 않는다 | R3 1.2, 시제품 400건 통과 |
| Ccode | `Cell` = `EUDLightVariable`(4B Db) 감싸기. 정수 코드(Line/Index)는 없앤다 | 2026-09-17 실험 |
| 숫자 서식 | `Dec(v, width=…)` 같은 **래퍼 객체 + `fmt()` 훅**. `{:05d}` 는 선택(몽키패치) | R4a C.3 |
| 입력 동기화 | 전송은 MSQC/NSQC 플러그인에 맡기고, 라이브러리는 선언을 받아 **eds 조각을 생성**한다 | R4b A7 |
| CX Paint | 도형 계산은 **lupa 로 `CB Paint v2.5.lua` 를 그대로** 돌리고, 찍기는 좌표표 + 루프 하나 | R4b B, 실험 통과 |
| 비교 연산 | 부호 있는 비교·경계값 처리는 `cmp` 모듈로 통일한다(0.76.14 의 변수끼리 `<`·`>` 버그는 0.81 에서 고쳐졌다) | R3 1.6, 4.1 |
| 뺄셈 의미 | **0 에서 멈추는 뺄셈(포화)과 한 바퀴 도는 뺄셈(wrap)을 이름으로 확실히 구분한다.** 연산자·`sub` = wrap, `_sat` 접미사·`Subtract` 단어 = 포화(eudplib 관례와 같음), CtrigAsm 별칭은 원래 의미. eudplib `v -= v` 버그(결과 0xFFFFFFFF)는 내부에서 피한다 | 사용자 지시, S8, 3.5 |
| 각도·반올림 | **CtrigAsm 과 같게 고정**한다. 런타임 각도는 CtrigAsm `f_Lengthdir` 기준(0 = +x, 화면에서 시계 방향), 도형 좌표는 TEP 처럼 0 방향 자르기. 회전도 CtrigAsm 처럼 항별 자르기(실수 회전과 최대 ±2 차이). 다른 기준을 고르는 옵션은 두지 않는다 표는 정확 반올림 sin/tan 으로 만들어 빌드 플랫폼과 무관하다(원본 Windows TEP 값과 같은지는 인게임 C9-1) | 사용자 결정 D5·D6, S1 |
| 위험 기능 | 일부러 멈추게 하거나 디싱크를 내는 기능은 `unsafe_` 접두사, 기본 비활성 | R4b D8 |

### 0.2 우선순위 (맵 10개 사용량 기준, R1 3절)

| 순위 | 기능 | 사용량 | 모듈 |
|---|---|---|---|
| 상 | 64비트 정수·출력 | 4맵 2,658회 (+DPS 128비트 163) | `i64`, `numfmt` |
| 상 | CX Paint 도형·찍기, G_CB 스포너 | 8맵 1,798 / 7맵 121 / 7맵 2,048 | `shape`, `plot`, `spawn` |
| 상 | 건물 스택(Gun_Line)·오브젝트 풀 | 4맵 2,298 (+TStruct 58, +NBag DPS 8 — `pool.Bag` 은 2단계) | `pool` |
| 상 | 서식 있는 출력(DisplayPrint) | 9맵 696 (+DPS 원소 220) | `display`, `numfmt` |
| 상 | 방금 만든 유닛·유닛별 저장(EXCC) | 10맵 311 / 8맵 361 | `units` |
| 상 | 키 입력·MSQC | 4맵 77 + 헬퍼 78 | `local`, `sync` |
| 상 | 플레이어별 액션·CP 관용구 | RotatePlayer 783, DisplayTextX 1,994 | `players` |
| 중 | lengthdir(음수·360 초과 보정) | 8맵 100 | `mathx` |
| 중 | 총알(사용자판) | 4맵 95 (라이브러리 28장은 0) | `bullet` |
| 중 | dat 패치 표 | 8맵 950 | `datpatch` |
| 중 | BGM, 채팅 효과·관전자 채팅, SCR_DB | 7맵 57 / 5맵·4맵 복붙 블록(관전자 채팅 보관소 1.37MiB → eudext Db 약 2.3KB) / 2맵 21 | `bgm`, `chat`, `misc`, `scrdb` |
| 하 | 128비트, CGRP, 28장 스프라이트, 방장·부대 지정, ExitDrop, Timer/Stage | 0~3회 (CGRP·28장 스프라이트는 WP21, 128비트는 WP20 으로 구현됨) | `i128`, `cgrp`, `bullet`, `misc` |

호출이 0회인 CtrigAsm 기능(`CA__MoveXY`, `CD__ScanW`, `f_Log2`, `f_Diff`, `NSQCSend`, `MousePress` 등)은
**설계만 남기고 구현은 요청이 있을 때** 한다.

### 0.3 쓰는 모습

파이썬 플러그인:

```python
from eudplib import *
from eudext import i64, numfmt, players, units, sync
from eudext.i64 import Int64
from eudext.numfmt import Dec
from eudext import strdesign as sd
sd.set_style("seed")                     # 맵 설정 맨 앞 (4.7.1)

gold = [Int64(0) for _ in range(8)]
bus = sync.Bus(transport="msqc")      # [MSQC] eds 조각은 빌드 스크립트가 euddraft 전에 만든다 (4.12, 5.3)
buy = bus.key_down("B", guard=sync.not_typing())

def beforeTriggerExec():
    for p in players.humans():                           # 컴파일 시점 목록 (루프가 펼쳐짐)
        if EUDIf()(buy.pulse(p)):
            gold[p] += 12_800_000_000                    # 64비트 상수
            players.display(p, "골드: ", Dec(gold[p], group=(3, ",")))
        EUDEndIf()
    with units.capture() as u:
        DoActions(CreateUnit(1, "Zerg Zergling", "Anywhere", P8))
    if EUDIf()(u.ok):
        units.CUnit(u.epd).set_invincible()
    EUDEndIf()
```

epScript:

```js
import eudext.i64 as i64;
import eudext.numfmt as nf;

const hp = i64.Int64(0x100000000);      // const 로 묶는다 (var 에 담으면 32비트가 된다)
var mp;

function afterTriggerExec() {
    hp.v += 5;                          // const 객체는 .v 통로로 고친다
    if (hp >= 0x100000005) {
        printAll("HP {}", hp.fmt());                      // 값 타입은 fmt() 로 넘긴다 (3.2-7)
        printAll("MP {}", nf.Dec(mp, width=5, fill="0")); // 파이썬 함수 호출의 키워드 인자는 된다
    }
}
```

(위 epScript 는 `epsCompile` 번역까지 확인한 모양이다. `nf.Dec(mp, width=5, fill="0")` 줄은 WP5 가 번역·빌드·에뮬레이터 실행(`MP 00042`)까지 확인했다. `nf.Dec(…)` 는 대문자라 그대로, `nf.dec(…)` 였다면 `nf.f_dec(…)` 로 번역된다.)

---

## 1. 목표와 범위

### 1.1 목표

1. **새 맵 코드가 CtrigAsm 없이** 사용자 맵의 모든 기능을 짤 수 있게 한다.
2. **용량**: eudplib 의 적층·72B 변수·함수 1벌 방출을 해치지 않는다. 모듈마다 비용 목표를 둔다(3.8).
3. **안전**: eudplib 함정(뺄셈 포화/wrap 혼동, 비교 경계, CP 캐시, P1 마린 데스 칸, 로컬 값 섞기)을 라이브러리 안에서 막는다.
4. **파이썬과 epScript 양쪽**에서 쓸 수 있다(3.11).
5. **게임 없이 시험**할 수 있다(5.1, 트리거 에뮬레이터).

### 1.2 비목표

- CtrigAsm 함수 이름·인자 모양의 복제. 새 API 는 eudplib 관례를 따른다(단, 사용자가 원한 `Cell`/`CD` 계열처럼 익숙한 이름은 별칭으로 둔다).
- CtrigAsm 원본 동작의 바이트 단위 재현. 그것은 호환 계층(`DPS_eud\eud\ctrig`)의 몫이다.
- "주소 + 번호×604" 같은 번호 산술을 API 로 노출하는 것.
- 사용 0회인 기능의 선구현.

### 1.3 호환 계층과의 관계

| | 호환 계층 `ctrig` | `eudext` |
|---|---|---|
| 대상 | 기존 CtrigAsm Lua 맵(DPS 등) | 새로 짜는 코드 |
| 입력 | Lua 표(`{P,Index,Next,"V"}`, T 팩, Flags) | eudplib 객체 |
| 원칙 | 원본과 같은 결과 | eudplib 관례, 용량 우선 |

- `eudext` 는 `ctrig` 에 의존하지 않는다. 알고리즘은 **복사해서** 가져오고 출처를 주석에 적는다(R2 7.1 목록).
- **이식판의 최신 코드를 우선 가져온다**(사용자 지시): DPS 이식판에는 인게임 계측 뒤의 최적화(원소 읽기 CP 방식, 상수 제수 나눗셈, 128비트 곱셈, TTLMemory 수정 등)가 계속 들어가고 있다. R2 의 줄 번호는 그 이전 기준이다. 최신판 위치와 확인 절차(GitHub `Mininii/DPS_Enhance` 의 `eudplib-port` 브랜치 — 없으면 사용자에게 노트북에서 커밋·푸시를 요청)는 저장소 최상위 `CLAUDE.md` 에 있다.
- `eudext.i64` 가 안정되고 DPS 가 인게임을 통과한 뒤, `ctrig/war.py` 가 `eudext.i64` 본체를 쓰도록 합칠 수 있다(선택, 6.1 WP-X).
- 같은 eudplib 판이면 한 맵에서 둘을 섞어 쓸 수 있다. 지금 DPS 이식 계층은 0.76.14 이므로, DPS 에 eudext 를 섞는 것은 DPS 를 0.81 로 옮긴 뒤다.

---

## 2. 환경과 배포

### 2.1 기준 판

| 용도 | 위치 | 판 |
|---|---|---|
| eudext 빌드 | `C:\euddraft0.11.0.1` | euddraft 0.11.0.1, eudplib 0.81.0, 번들 파이썬 **3.14.7 (GIL 켜진 일반 빌드** — 변경 기록의 "3.14t" 와 달리 `Py_GIL_DISABLED=0`, `python314.dll`) |
| eudext 개발·시험 | `C:\Users\whatd\.venvs\eud081` | 파이썬 3.13.15 + eudplib 0.81.0 + lupa 2.8 |
| euddraft 안에서 쓸 lupa | `C:\Users\whatd\.venvs\euddraft011_site` | lupa 2.8 **cp314** 휠을 `pip install --target` 으로 받은 폴더 |
| 기존 맵(theSeed·MSF·DPS 이식) | `C:\euddraft0.9.2.0`, `C:\Users\whatd\.venvs\eud076` | 0.9.10.11 / 0.76.14 — **건드리지 않는다** |
| **Ubuntu** eudext 개발·시험 | `<저장소>/.venv` | `setup_ubuntu.sh` 가 `vendor/wheels` 에서 eudplib 0.81.0·lupa 2.8 설치 (glibc 2.39+, 아니면 소스 빌드) |
| **Ubuntu** eudext 빌드 | `<저장소>/.tools/euddraft0.11.0.1/euddraft` | euddraft 0.11.0.1 Linux 판(`vendor/euddraft`). `EUDEXT_EUDDRAFT` 로 바꿀 수 있다. Linux 실행 확인(2026-09-16, Debian 13 glibc 2.41 — 예제·시험 빌드 통과) |
| **Ubuntu** euddraft 용 lupa | `<저장소>/.tools/euddraft_site` | lupa 2.8 cp314 (Linux) |

euddraft 0.11.0.1 실측(ENV 탐침 + WP0 보고서 3·6·8절):
- 플러그인의 `sys.path` 앞머리는 eds 를 **절대 경로**로 넘기면 `[eds 폴더, lib\library.zip, lib, …]`(eds 폴더가 빌드 내내 남음), 작업 폴더 기준 **상대 경로**면 `[lib\library.zip, eds 폴더(읽는 동안만), lib, …]` 다. 자동 빌드는 절대 경로로 넘긴다.
- `__file__` 은 없고 `__loader__` 는 있다. 동결된 euddraft 는 `PYTHON*` 환경 변수를 무시한다(`sys.flags.ignore_environment = 1`).
- **freeze**: `[freeze]` 섹션에 `freeze` 키가 있으면(값과 무관: `0`, `1`, 키만) 꺼진다. 섹션이 없거나 비어 있으면 켜진다(빈 맵 chk 0.37MB → 1.17MB). freeze 는 블록 테이블 4MiB 한도가 있다(메모리 `theseed-freeze-limit`). 시험 빌드는 `[freeze]` / `freeze : 0`.
- 플러그인 오류 때 euddraft 는 입력을 기다린다. 표준 입력을 비워 두면 종료 코드 127 로 끝난다(자동 빌드는 `< nul`).
- 부트 플러그인이 `VenvSite` 를 `sys.path` 끝에 붙이고 `import lupa.lua54` → Lua 5.4 동작(`math.atan2` 는 없음). 부트 **읽는 동안** import 한 lupa 는 뒤 플러그인에서 그대로 쓸 수 있고, 뒤 플러그인에서 처음 import 하면 실패한다.
- 플러그인 모듈 이름 = 섹션 파일 이름에서 확장자를 뺀 것(.py·.eps 모두), 전역에 `settings` 가 있다. `sys.argv[1]` = eds 절대 경로(Linux 판 확인).
  eudext 는 이것으로 "지금 트리거를 내는 플러그인" 과 eds 섹션 순서를 확인한다(scrdb (e)).
- 부트 뒤 플러그인에서도 `os.environ` 은 읽힌다(`EUDEXT_WORK`, `EUDEXT_SCRDB_CORE` — 동결 파이썬이 무시하는 것은 `PYTHON*` 해석뿐).
  (WP7 실측) lupa 를 뒤 플러그인에서 처음 import 하면 실패하는 것은 VenvSite 가 sys.path 에서 빠지기 때문이다. `eudext.shape` 는 스스로 후보 폴더(`EUDEXT_LUPA_SITE` → 저장소 `.tools/euddraft_site` → `~/.venvs/euddraft011_site`)를 sys.path 끝에 붙이므로 **Preload 없이도 적재된다**. 그래도 eds 에는 `Preload : shape` 를 권장하고, `VenvSite` 는 선택이다(없는 폴더면 부트가 경고만 한다).

규칙:
- 상대 import 를 쓰지 않는다. 패키지 안에서도 `import eudext.x` 절대 경로만(0.81 은 sys.path 밖으로 나가는 상대 import 가 ImportError).
- 비공개 API 는 `_compat.py` 한 곳에서만 쓰고, import 때 판(0.81.x)을 검사한다.
- 0.81 에서 생긴 기능(scdata `TrgUnit.armor`, epScript 타입 변수, `EUDArray` EPD 기본, 문자열 식)은 **써도 된다**. 쓸 때는 docstring 에 적는다.
- 개발 venv 의 파이썬(3.13)과 번들(3.14.7)이 다르므로, 파이썬 판에 기대는 코드(표준 모듈, 바이트코드)는 쓰지 않는다. 최종 확인은 euddraft 빌드로 한다.

### 2.2 폴더 구조

```
MapSource\Py\eudext\
  __init__.py        판 번호, 판 검사. 무거운 import 금지 (lupa 는 shape 만)
  _compat.py         eudplib 판 검사, 비공개 API 접근 한 곳 (EUDVarBuffer._initvals, curpl 캐시, _create_func_body …)
  _parts.py          내부 부품: 분기·1회 분기·마스크 쓰기·임시 변수 (DPS core.py 에서 복사)
  boot.py            euddraft 부트 플러그인 (eds 에서 경로로 지정)
  errors.py          EPError 도우미, 한국어 메시지
  ── 값·수학 ──
  cmp.py             부호 없는 안전 비교, 부호 있는 비교
  cell.py            Cell(Ccode), Flag, PCell
  i64.py             Int64, Int64Array, Int64Ref(나중)
  i128.py            128비트 (WP20)
  mathx.py           lengthdir/atan2/isqrt/ilog2/부호 나눗셈/Delta/Table
  ── 글자 ──
  numfmt.py          Dec/Hex 래퍼, 고정 폭 변환, Int64 10진, 직접 쓰기, 파싱
  display.py         DisplayPrint 대체 (대상·원소·13번째 줄·TBL)
  strdesign.py       컴파일 시점 색 문자열 꾸미기 (StrDesign 4판 + StrD)
  textfx.py          셀(글자당 4B) 편집 효과
  chat.py            채팅 줄 직접 쓰기 (CDPrint 대체), 13번째 줄
  ── 게임 ──
  players.py         대상 목록, 플레이어별 액션, 사람 판정
  units.py           방금 만든 유닛, 유닛별 저장(UnitData), 새 유닛 루프
  pool.py            오브젝트 풀 + 살아 있는 것만 돌기 (Gun_Line/TStruct 대체)
  local.py           로컬 입력(키·마우스·채팅 중·화면) — 표시 전용
  sync.py            동기화 입력 선언 → MSQC/NSQC eds 조각, 수신값 걸쇠
  bullet.py          총알·스프라이트
  datpatch.py        dat 필드 표, 시작 시 적용, 되돌릴 수 있는 패치
  datpatch_tables.py datpatch 보조 표 (eudext 전용 필드·TEP 키 대응)
  bgm.py             곡 표(길이 자동 측정·MPQ 등록), local/synced 재생기(조각·돌려 쓰기·busy 정책), 관전자 끄기, 시계(NormalTurboSet 대체)
  misc.py            방장, 부대 지정, 관전자 채팅, 와이드 판정, unsafe_exit_trap
  ── 도형 ──
  shape.py           lupa 다리(CX), Shape, ShapeSet(좌표표 저장)
  _crmath.py         정확 반올림 sin/cos/tan/asin/acos/atan2/exp/log (decimal) — shape 의 Lua math 표에 넣는다
  plot.py            Plotter(찍기 루프), 점 변환(CA_ 대체)
  spawn.py           G_CB 식 소환 대기열
  cgrp.py            CGRP 파서·층 굽기·CGRPPainter (WP21)
  ── 앱 ──
  scrdb.py           SCR_DB 네이티브 코어 (런처 레이아웃 7 호환)
  dbg.py             디버그 브리지 블록(DebugBridge.lua 배치 v1) — 감시·판정·단계 → 외부 리더·자동 판정 (4.21)
  ── 개발 ──
  testing\           emu.py(에뮬레이터), scmodel.py(SC 조건·액션 확장·유닛·글 기록), harness.py(차등 시험 틀), base.scx(빈 기준 맵),
                     base_multi.scx(P1~P4 사람), locmodel.py(로케이션·Order), chatmodel.py(채팅 버퍼), syncmodel.py(MSQC 수신·턴), dispmodel.py(표시 순간 버퍼·13번째 줄·TBL)
  tools\             cost.py(비용 보고), edsgen.py(eds 생성), build.py(단독·euddraft 빌드), lua_consts.py(Lua 상수 읽기),
                     make_multi_base.py(여러 명 기준 맵), make_auto_all_base.py(통합 맵 기준 맵 — P1 파이어뱃),
                     ingame_maps.py(인게임 확인 맵 일괄 빌드 → `work\ingame_auto_maps\` 에 맵·명세·RUN.bat·README),
                     make_ingame_specs.py(자동 판정 명세 만들기, 5.6),
                     ingame_auto.py(디버그 브리지 자동 판정), debugbridge\(dbg_reader.py 리더·fake_game.py 가짜 게임 — DPS 이식판 사본, 5.5)
  tests\             모듈별 시험 (t_<모듈>.py), _common.py, run_all.py, t_tools.py, t_build_example.py
  examples\          작은 예제 맵 소스 (hello.py, hello.eps, hello.eds)
  docs\              research\, proto\, COSTS.md(측정값 기록), spec\(명세 S1~S8, WP0 보고서)
```

`.gitignore` 에 `__epspy__/`, `__pycache__/`, `docs/spec/S8_ingame/build/` 를 넣었다(epScript 번역본이 패키지 폴더에 생긴다, R3 2.1). 시험·예제 빌드 산출물은 작업 폴더(`%TEMP%\eudext_work`)로 간다.

### 2.3 불러오기

**euddraft 빌드** — eds:

```ini
[main]
input: base.scx
output: out.scx

:: 부트 플러그인은 반드시 eudext 를 쓰는 모든 플러그인보다 앞에 둔다
[..\..\MapSource\Py\eudext\boot.py]
EudextRoot : C:\Users\whatd\Desktop\Stormcoast Fortress\ScmDraft 2\MapSource\Py
:: VenvSite 는 shape(lupa, cp314) 를 쓸 때만. Preload 는 부트 중에 미리 import 할 모듈
VenvSite : C:\Users\whatd\.venvs\euddraft011_site
Preload : shape, i64

[MSQC]
...
[main.eps]

[freeze]
freeze : 0
```

**eds 문법 주의**(WP0 보고서 3절): 값은 줄 끝까지다. **줄 끝 주석이 없다**(`Key : value ; 설명` 은 값이 `value ; 설명` 이 된다). 주석 줄은 **`::` 로 시작하는 줄만**이다(`;` 로 시작하는 줄은 값 없는 키가 된다). `[머리] ; 주석` 은 머리로 읽히지 않는다. `boot.py` 는 방어로 값 끝의 `<공백>; …` 을 떼지만 eds 에 쓰지 않는다.

`boot.py` 가 하는 일:
1. `settings` 키를 소문자로 접고 `EudextRoot` 를 `sys.path` 앞에, `VenvSite` 를 **뒤에** 넣는다(번들 eudplib 이 먼저 잡혀야 한다).
2. `import eudext` 후 `_compat.check()` 로 eudplib 판을 검사한다.
3. `Preload` 의 모듈을 import 한다. **lupa 는 부트 중에만** import 할 수 있다(그 뒤 venv 경로가 빠진다).
4. `PycachePrefix`(선택)가 있으면 `sys.pycache_prefix` 로 둔다. 부트 플러그인 자신의 `.pyc` 는 막지 못하므로 `tools\build.py` 는 boot.py 사본을 작업 폴더에서 실행한다.
5. 판 번호와 불러온 모듈을 한 줄 출력한다.

규칙:
- 공용 코드는 모두 `eudext` 패키지 **안**에 둔다. `MapSource\Py` 바로 밑의 비패키지 모듈은 부트 뒤에 불러올 수 없다.
- eudext 안의 `.eps` 도 `import eudext.x` 로 불러올 수 있다. 같은 이름의 `.py` 가 있으면 `.py` 가 먼저 잡힌다.
- 위 규칙은 0.11.0.1 에서 다시 쟀다(WP0 보고서 3절). 0.9.10.11 과 달라진 것: sys.path 밖으로 나가는 상대 import(`import ..shared.x`)는 ImportError. 같은 폴더·sys.path 안의 상대 import 는 된다.

**단독 빌드(시험·개발)** — venv 파이썬에서 `sys.path.insert(0, MapSource\Py)` 후 `LoadMap`/`SaveMap`. 도구: `tools\build.py standalone …`, `tools\build.py euddraft <eds> --work <폴더>`(5.3).

### 2.4 번들 파이썬 제약

번들에 **없는** 표준 모듈은 쓰지 않는다. 0.11.0.1 전수(`sys.stdlib_module_names` 297개, WP0 보고서 6절):
- **없는 공개 모듈 56개**: `bdb, cProfile, cmd, compileall, curses, dbm, doctest, ensurepip, fcntl, filecmp, fileinput, graphlib, grp, imaplib, mailbox, modulefinder, nturl2path, optparse, pdb, pickletools, plistlib, poplib, posix, profile, pstats, pty, pwd, pyclbr, pydoc, readline, resource, sched, shelve, shlex, smtplib, socketserver, sqlite3, sre_compile, sre_constants, sre_parse, symtable, syslog, tabnanny, termios, timeit, tomllib, trace, tty, unittest, uuid, venv, wave, webbrowser, wsgiref, zipapp, zoneinfo` (+ `tkinter, turtle, idlelib` 등).
- 0.9.10.11 에는 있던 `shlex, pdb, doctest, pydoc, webbrowser, plistlib, socketserver` 도 없다. 반대로 `colorsys, configparser` 는 생겼다.
- 제3자: `openpyxl`, `rich`, `typing_extensions` 있음. `lupa`, `numpy`, `colorama` 없음.
- 시험(`tests/`)은 개발 venv 에서만 돌므로 `unittest` 를 써도 되지만, **패키지 본체는 쓰지 않는다**.
- 소리 파일 길이 측정은 `wave` 모듈에 기대지 않고 `struct` 로 직접 읽는다(S5 B.9).

---

## 3. 공통 규약

모든 모듈이 지킨다. 리뷰할 때 이 절을 체크리스트로 쓴다.

### 3.1 이름

- **epScript 에서 부를 모듈 함수는 `f_이름`** 으로 정의한다. epScript 가 `m.foo()` 를 `m.f_foo()` 로 번역하기 때문이다(R3 2.2). 파이썬 편의로 `foo = f_foo` 별칭을 둔다. 트리거를 만들지 않는 컴파일 시점 순수 함수(`strdesign.design` 등)도 같은 규칙으로 `f_` 별칭을 둔다.
- 클래스·상수는 대문자로 시작한다(번역에서 접두사가 붙지 않는다).
- 로컬 전용 함수는 `local` 모듈에 두거나 이름에 `local_` 을 붙인다. 위험 기능은 `unsafe_` 로 시작한다.
- 모듈 전역 이름에 CtrigAsm 이름을 그대로 쓰는 것은 **별칭**일 때만(`cell.CD = cell.f_cd`).
- 내부 모듈(`_parts`)도 epScript 에서 `import eudext._parts as parts;` 로 불러올 수 있다(밑줄 이름 허용, WP0 확인).

### 3.2 값 타입 규약 (`Int64` 가 기준 구현)

R3 5절을 그대로 따른다.

1. 파이썬 클래스 + 내부 `EUDVariable`. `__slots__`, `dont_flatten = True`, `__hash__ = id`.
2. 실수 막기: `__bool__`·`__format__`·`__iter__`·`cast` 는 안내 오류, `__repr__` 에 "epScript 에서는 var 대신 const" 안내문.
3. 생성: `T(상수)` = 초기값만(트리거 0개). `T(변수)`·`T(a, b)` = 실행 시 대입. `T.wrap(…)` = 복사 없이 감싸기.
4. 이항 연산은 **새 임시 객체**를 만든다. 제자리 연산은 self 를 고치고 self 를 돌려준다(epScript 는 반환값을 버린다).
5. `<<` 는 **대입**이다. epScript 식 `x << 3` 은 시프트로 번역되므로 값 타입에서는 막는다. 시프트는 메서드(`shl`, `shr`)와
   `>>`(새 값), `<<=`·`>>=`(제자리 — eudplib `EUDVariable` 과 같게 `<<=` 는 시프트)로 준다(WP4, D60).
6. epScript 통로: `x.v = y`(property), `x.v += y`(`iaddattr`/`isubattr`), `x.assign(y)`, `x.iadd(y)`.
7. 인쇄: `fmt()` 를 구현한다(`f_dbstr_print`, `StringBuffer`, `f_eprintln` 이 부른다). `f_sprintf("{}", x)` 는 `__format__` 에서 막고 `x.fmt()` 를 쓰라고 안내한다.
8. 함수 인자로는 한 칸에 못 넘긴다. `(lo, hi)` 두 인자로 받고 본문에서 `Int64.wrap(lo, hi)`.
- 숫자 서식 객체(`numfmt.Dec` 등)는 값 타입이 아니라 eudplib `ptr2s` 를 상속한 **표식**이다 — 서식 문자열을 그대로 통과하고 `fmt()` 가 인쇄 순간 변환한다. `f_cpchar_print`(TextFX) 경로는 `fmt()` 를 부르지 않으므로 `_value` 에서 안내 오류를 낸다(4.6).
- `<<` 대입이 epScript `_LSH`(식 `x << 3`)로 불리면 빌드 오류(`_compat.eps_lshift_caller`). 문장 `x << y;` 는 epScript 문법 오류이고,
  `x.v <<= n`·`x.v >>= n` 은 `ilshiftattr`/`irshiftattr` 로 와서 시프트(WP4).
- (보탬) 32비트 `EUDVariable` 이 왼쪽인 곱셈·나눗셈·나머지·오른쪽 시프트(`v * x`, `v // x`, `v % x`, `v >> x`)는 eudplib 이 값 타입을
  상수처럼 다뤄 **조용히 틀린다**(`_const_mul` 의 `number &= 0xFFFFFFFF` 가 Int64 를 제자리에서 바꿈) → 값 타입은 그 호출 경로
  (`_compat.eudplib_calc_caller`)를 보고 안내 오류를 낸다. 모듈 함수(`i64.mul(v, x)`)를 쓴다.
- (보탬) 파이썬 `/` 는 값 타입에서 오류로 두고 `//` 만 준다(epScript `/` 는 `//` 로 번역된다).
- 파이썬 `x.v += y` 는 `x.v = (x.v += y)` 로 되쓰기가 따라오므로 `v` setter 는 같은 객체면 아무것도 하지 않는다.
- `fmt()` 는 **호출 자리마다 버퍼**를 둔다 — epScript 는 `printAll("{} {}", a.fmt(), b.fmt())` 의 인자를 먼저 모두 계산하므로
  공유 버퍼면 앞 값이 덮인다. 인쇄 함수에 값 타입을 그대로 넘기면(`f_dbstr_print(buf, x)`) 인쇄 순간 `fmt()` 가 불린다.
  상수 `fmt()` 는 문자열(트리거 0).
- `__eq__`/`__ne__` 는 `None` 과 비교하면 `NotImplemented`(파이썬 컨테이너 검사가 깨지지 않게).
- 32비트 `EUDVariable` 이 **왼쪽**인 비교·산술(`v >= x`, `v + x`)은 eudplib 연산자가 먼저 불려 오류 → 모듈 함수(`i64.ge(v, x)`)를 쓴다.

### 3.3 연산 분기와 함수 캐시

| 피연산자 | 처리 |
|---|---|
| 모두 상수 | 파이썬에서 계산 (트리거 0) |
| 한쪽 상수 | 본문이 트리거 3개 이하면 **인라인**, 아니면 `functools.cache` 로 **상수별 EUDFunc** |
| 모두 변수 | **처음 부를 때 한 벌** 만드는 공유 `EUDFunc`, 결과는 `ret=[…]` 로 받는다 |

- 옵션 조합이 많은 함수(예: `Dec` 서식)는 "공용 본문 1벌 + 옵션별 작은 꼬리" 로 캐시한다(키 = 옵션 튜플).
- EUDFunc 는 재귀·재진입이 안 된다. 라이브러리 함수 안에서 사용자 콜백을 부를 때(예: `Plotter.on_point`) 그 콜백이 같은 함수를 다시 부르지 않게 문서화하고, 가능하면 빌드 때 검사한다.
- WP20 실측: 128비트 변수 덧셈을 펼치면 호출 자리 9 트리거 4.5KB(실행 16), 공유 함수 호출은 1 트리거 2.8KB(실행 35) → 공유 함수 기본.
  32비트 이하 값을 더할 때는 펼침(7 / 9, 2.4KB)이 작아 `inline=None` 이 자동으로 고른다. 한 번 페이로드는 공유 함수가 약 5KB 더 들어
  호출 자리가 둘 이상이면 공유 함수가 싸다.
- 공유 본문 안에서 다른 공유 본문을 부르는 조율 본문(i128 곱셈·나눗셈)은 반환 변수를 미리 정하지 않는다(eudplib `_EUDPredefineReturn`
  규칙: 본문 안 EUDFunc 호출 금지·반환 변수를 원천으로 쓰지 않기). 미리 정한 반환 변수는 목적지와 조건으로만 쓴다.
- 상수마다 본문을 만드는 연산은 **한 번 페이로드**를 같이 본다: 128비트 상수 제수는 칸 넷 본문(약 84KB) 대신 i64 상수 본문(약 36KB,
  i64 와 공유)을 칸마다 부른다(실행 +30%).
- 주 함수를 다 만든 뒤(`_compat.on_start_after_main`) 떨어진 서브루틴을 정의하면서 EUDFunc(mathx 엔진 등)을 처음 불러도 된다(WP12 실측) — "쓰인 기능만 코드에 넣기" 에 쓸 수 있다. 단 그 안에서 `EUDOnStart` 를 부르는 함수(players.contains_user 등)는 부르지 않는다(5.1 기존 기록).
- 비용 표기: 조건 칸이 아니라 **액션의 player(EPD)·amount·mask 칸**을 VProc/SeqCompute 로 채우는 방식은 1단계 bullet 과 같다(`SetDeathsX` 의 +0 = 마스크, +16 = EPD, +20 = 값). (WP21)
- WP5 방식: 본문은 배치별 1벌(반환 없음, 모듈 작업 변수에 씀), 옵션 꼬리는 `_compat.predefine_returns` 로 반환 변수를 미리 정한 EUDFunc(작업 변수를 반환 변수로 공유 — 호출마다 반드시 초기화, 반환 변수를 원천으로 복사하지 않음). 호출 자리는 `ret=[EPD(buf)+j…]` 로 결과를 버퍼에 바로 받는다. 입력마다 달라지는 보정은 파이썬 계획으로 미리 구해 같은 보정끼리 묶고 범위를 반으로 나눠 분기한다.
- WP4 실측: 비트 연산 변수끼리 `^` 는 호출 자리 7 트리거지만 바이트(3.2KB)가 공유 함수 호출(곱셈 호출 3.4KB)과 비슷해 인라인으로 두었다.
  한쪽 상수인 곱셈·나눗셈·시프트는 상수마다 공유 본문(`functools.cache`, 본문 7~130), 상수 0·1·−1·2^s 와 1비트·32비트 시프트만 인라인.
- 콜백 안에서 같은 객체의 루프를 또 만드는 재진입은 **바깥 루프를 다 만든 뒤** 오류를 낸다(안에서 바로 올리면 열린 블록·서브루틴 정의가 반쯤 남는다 — plot 방식, WP7).
- eudplib `EUDFuncN.__call__` 은 상수 인자를 한 트리거의 액션으로, 변수 인자는 그 변수 트리거를 VProc 으로 이어 붙인다 → 변수 인자가 여러 개여도 **호출 자리 트리거는 1**(실행만 인자 수만큼 는다, WP14 실측). 옵션 조합이 많은 본문은 컴파일 시점 상수(유닛 번호·dat 칸 주소)를 인자로 넘겨 본문을 나눠 쓴다(bullet).
- 변수 인자 공유 본문이 상태를 가지면(예: mathx 변수 각 엔진의 '마지막으로 준비한 각') 같은 입력이 이어질 때 준비를 건너뛰게 할 수 있다. 공유 본문은 기본 하나, 번갈아 쓰기가 잦은 곳은 `own=True` 식 전용 본문을 선택으로 둔다(WP9).
- "모두 변수 = 공유 EUDFunc" 는 **인라인의 호출 자리 바이트가 함수 호출보다 크게 많을 때** 적용한다. 인라인이 호출
자리 3 이하이고 바이트가 비슷하면 인라인이 기본(`i64` 덧셈·wrap 뺄셈), 크면 공유 함수가 기본(`i64` 포화 뺄셈). 둘 다 가능한 연산은
`inline=` 인자를 둔다.

### 3.4 조건을 돌려주는 함수

R3 1.3 규칙:

- 돌려주는 것: **새** `Condition`(또는 목록) > `EUDLightBool` > 0/1 `EUDVariable` 순으로 싼 것을 고른다.
- 앞 계산 트리거가 필요하면 **함수를 부르는 순간** 낸다(`EUDIf()(f())` 에서 분기보다 앞에 놓인다. 루프 조건도 매번 다시 계산된다 — 실험 확인).
- 같은 `Condition` 객체를 캐시해 두 번 쓰지 않는다(오류).
- epScript 는 `__lt__`·`__gt__`·`__ne__` 를 부르지 않고 `__ge__`·`__le__`·`__eq__` 의 부정을 쓴다 → 이 세 개를 먼저 완성한다.
- epScript `return a < b;` 는 컴파일 오류다 → 문서에 `return a < b ? 1 : 0;` 로 안내한다.
- **값 칸을 실행 중에 채우는 조건은 amount 자리에 정수가 아닌 자리 표시(`Forward`)를 둔다.** 정수를 두면 eudplib `EUDNot`·`EUDSCAnd(neg=True)` 의 `negate_cond` 가 제자리에서 비교를 뒤집어 **틀린 답**이 된다(WP1 실측, 예: `AtLeast 0` → Never). `Forward` 면 eudplib 이 분기로 부정한다. 비트마스크 칸(+0)을 채우고 상수와 비교하는 "자기 칸 조건"(eudplib 0.81 `__lt__` 방식)은 amount 가 상수라 제자리 부정이 맞다. WP2(Cell)·WP3(i64 비교)도 같은 규칙(4.2). 자리 표시를 둘 수 없는 조건(조건 칸이 공유 본체에 있는 경우 등)은 그 자리에서 결과를 1비트에 받아 뒤집는다(`units.UnitField.ne/lt/gt`, WP10 실측 — `EUDNot` 이 `AtLeast v` → `AtMost v−1` 처럼 비교값을 컴파일 시점에 고쳐 변수 값에서 틀린 답을 냈다).
- eudplib `EUDNot` 은 상수 `AtMost 0xFFFFFFFF` 조건을 제자리에서 `AtLeast 2³²` 로 바꿔 **늘 참**으로 만든다(WP2 실측 — `EUDIf(…, neg=True)` 경로는 맞음). 상수 경계는 `cmp` 처럼 Always/Never 로 접어서 돌려준다. eudplib `RawTrigger(conditions=…)` 는 `EUDLightVariable` 자체(참거짓 뜻)를 받지 않는다(`EUDIf`·`EUDNot` 은 받는다).
- 작업 변수 값 칸에 쓰는 보정은 마스크 SetTo(SetMemoryX)로 — 자리 글자가 이미 들어간 칸도 맞다(WP5). 마스크 Add 는 여전히 쓰지 않는다(3.5-8).
- 조건 트리거가 참일 때 자기 next 를 고쳐 가는 방식(eudplib `EUDBranch` 의 앞 트리거)은, 되돌리는 트리거를 따로 두지 않고 **공통 지점(프레임 첫 트리거 등)에서 한꺼번에 되돌리면** 트리거 1개로 갈라진다(`chat.Typewriter` 칸 판정). do-while 끝도 같은 방법(머리가 되돌림, 반복당 판정 1 — `textfx` 스캐너). (WP17)
- 조건 **+12 칸(유닛 워드·비교·종류 바이트)을 실행 중에 바꾸는 막이 조건**(i64 포화 뺄셈: 조건 트리거가 Always 로 바꾸고
준비 트리거가 매번 Memory·AtLeast 로 되살림)은 라이브러리 내부 트리거에만 둔다(사용자에게 돌려주는 조건에는 쓰지 않는다 —
eudplib 제자리 부정이 비교 바이트를 바꾸면 되살림 값과 어긋난다). 인게임 C3-2.

### 3.5 뺄셈과 비교의 의미

**이 절은 64비트 구현의 가장 중요한 대목이다(사용자 지시).** 게임 기능에는 0 에서 멈춰야 하는 뺄셈(체력·자원·쿨타임)이
분명히 필요하고, eudplib 은 곳에 따라 `Add(-k)` 로 한 바퀴 돌게 빼기도 하고 `Subtract` 액션으로 0 에서 멈추게 빼기도 한다.
두 의미가 이름만 보고 구분되어야 한다.

조사 결과: `docs/spec/S8_subtract.md` (eudplib 0.76.14·0.81.0 은 뺄셈 의미가 **같다**, 실측).

**eudplib 의 규칙은 이름에 있다.**

| 방법 | 의미 | 근거 |
|---|---|---|
| SC `Subtract` 액션 (`SetDeaths`/`SetMemory`/`SetResources` …) | **포화**(0 에서 멈춤) | SC 동작 |
| 이름에 `Subtract` 가 든 것: `SubtractNumber(X)`, `SeqCompute`/`SetVariables`/`NonSeqCompute(…, Subtract, …)`, `f_dwsubtract_epd`/`_cp`, `f_wsubtract_epd`·`f_bsubtract_epd`(마스크 포화), `isubtractitem`/`isubtractattr`, `QueueSubtractTo` | **포화** | S8 2절 |
| 연산자: `EUDVariable -= 상수`(`Add(-k)`), `-= 변수`, `a - b`, epScript `--`, 단항 `-` | **wrap** | S8 2.1 |
| 이름에 `sub` 만 든 것: `isubitem`/`isubattr`(epScript `arr[i] -=`, `s.f -=`) | **wrap** | S8 2.5, 5절 |
| 0.81 scdata 멤버 `-=`, `TrgUnit`·`TrgPlayer` 값 `-=`, `EUDVArray[i] -=` | **wrap** | S8 2.5 |
| **예외** `EUDLightVariable -= x` (`VariableBase.__isub__`) | 연산자인데 **포화** | S8 1-2 |
| **eudplib 버그** 같은 변수끼리 `v -= v` | 0 이 아니라 **0xFFFFFFFF** (`self += 1` 을 먼저 하고 `~self` 를 더함) | `eudv.py` `__isub__`, S8 1-3 |

**eudext 규칙** (S8 7.1 을 적용, 7절 D3 — 사용자 확인 대기):
1. **연산자와 `sub`/`isub`/`neg` 는 모든 eudext 타입에서 wrap**(`Int64`, `Cell`, 배열 원소, 필드 뷰). eudplib `EUDVariable` 과 같다.
2. **포화는 `_sat` 접미사**: 32비트 `sub_sat(a, b)`/`isub_sat(v, b)`(모듈 함수는 `f_sub_sat`/`f_isub_sat`), `Int64` 는 `x.isub_sat(y)`/`i64.sub_sat(x, y)`, `Cell` 은 `c.isub_sat(v)`, 배열은 `arr.isub_sat(i, v)`.
3. **이름에 `Subtract` 가 든 것은 포화만** 뜻한다(eudplib 관례 그대로). `Cell.SubtractNumber(k)` 는 eudplib 그대로 포화 액션. `Int64.SubtractNumber`/`AddNumber` 는 **두지 않는다**(64비트 포화는 조건 트리거가 필요해 액션 하나가 될 수 없다).
4. `Cell` 은 `VariableBase.__isub__` 를 **wrap 으로 덮어쓴다**. 문서에 "`EUDLightVariable -= x` 는 포화, `Cell -= x` 는 wrap" 경고를 둔다.
5. CtrigAsm 이름 별칭은 원래 의미: 포화 = `SubCD`, `SubV`, `CSub`, `_Sub`, `f_LSub`(**64비트 전체 기준 포화**), wrap = `CiSub`, `_iSub`, `f_LiSub`, `f_LNeg`. `SetNWar(Subtract)` 식 **반쪽별 포화는 만들지 않는다**(2³²−1 에서 틀림). pool 옛 줄 번호 별칭 `SetLine(…, Subtract, …)` 도 포화(S2 6.9).
6. eudext 내부의 32비트 뺄셈은 `_parts.isub32(a, b)` 하나를 거친다. `a is b` 면 `a << 0` 으로 바꿔 eudplib 버그를 피한다. `Int64` 도 `x -= x`, `sub_sat(x, x)` 를 컴파일 시점에 0 으로 접는다.
7. SC `Subtract` 액션을 **써도 되는 곳**: `~y`(= `0xFFFFFFFF ⊖ y`), 판정용 임시값(`t = b ⊖ a`, t>0 ⇔ a<b), 앞 단계가 `값 ≥ 빼는 값` 을 보장한 곳, 64비트 포화의 hi 반쪽(lo 보정 트리거와 함께), 32비트 포화 헬퍼. **쓰면 안 되는 곳**: wrap 뺄셈의 반쪽, 반쪽별 포화로 64비트 포화 흉내, 부호 있는 값.
8. **마스크(필드) 뺄셈**: SC 마스크 `Subtract` 의 세부 식은 인게임 확인 전이다(`docs/spec/S8_ingame/`). 그 전까지 `field.isub(v)`(= 마스크 Add −v, wrap)만 열고, `field.isub_sat` 는 결과가 나온 뒤에 연다.
9. epScript 에서: wrap = `a -= b;`, `a--;`, `x.v -= b;`, `x.isub(b);` / 포화 = `x.isub_sat(b);`, `m.isub_sat(a, b);`, `const r = m.sub_sat(a, b);`, 32비트 상수는 `DoActions(a.SubtractNumber(k));` 도 된다.

비교:
- 0.76.14 변수끼리 `a < b`(b=0), `a > b`(b=0xFFFFFFFF) 는 틀린 답이었다(0.81 에서 고침). eudext 는 판과 상관없이 `cmp` 를 쓴다.
  0.81.0 변수끼리 여섯 연산자는 32비트 경계값 81쌍 + 무작위에서 모두 맞았다(WP1 실측, `t_cmp.py` `eudplib081_*`). 그래도 `cmp` 가 더 싸거나 `RawTrigger` 에 넣을 수 있어 감싸지 않고 직접 짰다(4.2).
- eudplib 0.81 의 **음수 상수는 연산자마다 뜻이 다르다**(WP1 실측): `x < -1` → Never, `x > -1` → 늘 참(파이썬 정수 뜻), `x <= -1` → 늘 참, `x >= -1`·`x == -1`·`x != -1` → 0xFFFFFFFF 로 읽음. `cmp` 는 모든 함수에서 2³² 나머지로 읽는다.
- 0 나눗셈: 기본은 eudplib 과 같게(몫 전부 1, 나머지 = 피제수). CtrigAsm 값이 필요하면 `div0=` 인자(4.5).

### 3.6 CP 규약

R3 1.5:

1. CP 를 잠깐 옮겨 쓰는 함수는 끝에서 **반드시 `f_setcurpl2cpcache()`**.
2. CP 를 바꾼 채 두려면 `f_setcurpl` / `SetCurrentPlayer`.
3. `SetMemory(0x6509B0, SetTo, …)` 로 CP 를 바꾸는 원시 액션은 **금지**. 사용자가 넘긴 원시 액션 목록을 받는 헬퍼는 `_parts.cp_fix`(DPS core.py 761 방식)로 캐시를 같이 고친다. 같은 호출 안에서 `f_setcurpl2cpcache()` 로 되돌리는 **잠깐 옮기기**(R3 1.5-1, eudplib `DisplayTextAll`·`f_dwread_epd` 와 같은 방식)는 여기에 해당하지 않는다 — 예: `players.run_as`(4.9).
4. 기본 계약: 라이브러리 함수는 **호출자의 CP 를 바꾸지 않는다**. 바꾸는 함수는 이름이나 문서에 적는다.
5. 옮길 때 주의: 원본 DisplayPrint 는 CP 를 바꾼 채 두었지만 `display` 는 되돌린다(S3). eudplib `PlayWAVAll`/`DisplayTextAll` 은 CP 를 되돌리지 않는다(S5).
6. `f_getcurpl()` 은 CP 캐시 변수 자체가 아니라 사본 변수를 돌려준다 — 값 원천(`SeqCompute(…, Add, f_getcurpl())`)으로 그대로 써도 캐시가 틀어지지 않는다(WP2 확인).
7. CP 를 원시로 잠깐 옮겨(`SetMemory(0x6509B0, SetTo/Add, …)`) CP 상대 `SetDeaths(X)` 여러 개(unit 칸 = 12 의 배수 거리)를 한 트리거에 쓰고 끝에 `f_setcurpl2cpcache` 하는 방식은 허용되는 잠깐 옮기기다(bullet). 이런 함수 뒤 CP 는 **eudplib CP 캐시 값**으로 돌아간다 — 캐시를 거치지 않고 원시로 바꾼 CP 는 되돌아오지 않는다(`f_dwread_epd` 와 같은 계약). 시험에서 CP 를 바꿀 때는 `f_setcurpl`.
8. `EUDSwitch(변수)` 는 CP 트릭을 쓰고 case 로 가기 전에 CP 를 **캐시 값**으로 되돌린다 → case 본문에서 CP 를 다른 값(예: 이 PC 번호)으로 쓰려면 원시 쓰기가 아니라 `f_setcurpl(값)`(캐시 포함)으로 바꾼 뒤 switch 에 들어간다(bgm 재생 함수).
9. CP 를 기록 칸 포인터로 쓰는 루프: `SetCurrentPlayer(EPD(Db) + k)`·`AddCurrentPlayer(1)` 로 캐시까지 맞추면 루프 안에서 부른 eudplib 읽기 함수(`f_dwread_epd`, `EUDArray` 읽기)가 CP 를 그 포인터로 되돌려 주고, `f_dwread_cp(오프셋)` 은 CP 를 바꾸지 않는다. 루프 뒤에 들어올 때의 CP 로 되돌린다(bgm).
10. 한 트리거 안에서 `SetMemory(0x6509B0, Add, 1)` 뒤의 `SetDeaths(CurrentPlayer, …)` 는 바뀐 CP 로 쓴다(액션마다 CP 를 다시 읽음 — 에뮬레이터도 같음). 잠깐 옮기기(끝에서 `f_setcurpl2cpcache()`)로 연속 칸 쓰기에 쓴다. `Deaths/SetDeaths(CurrentPlayer, …, unit=u)` 는 CP + 12u (데스 표 = [유닛][플레이어])라 연속 칸이 아니다 — 쓰지 않았다(SC:R 확인 전). (WP17)
11. `numfmt.f_scan_dec_cells`·`f_fmt_dec_cells`(변수 EPD)는 CP 를 원시 쓰기로 잠깐 옮기고(`SeqCompute([(EPD_CP, SetTo, epd)])`, `SetMemory(0x6509B0, Add, 1)`) 끝에서 `f_setcurpl2cpcache()` 로 되돌린다 — 3.6-3 의 잠깐 옮기기. `AddCurrentPlayer` 는 캐시도 바꾸므로 이 방식에 쓰지 않는다.

### 3.7 로컬과 공유

- 로컬 값(키·마우스·채팅 중·화면 좌표·`0x512684`·와이드 판정)은 **공유 상태에 쓰면 디싱크**다.
- `local` 모듈의 함수는 결과에 표식을 붙인다(`LocalValue`/`LocalCondition` 래퍼). `sync` 의 전송 함수만 받아들이고, 공유 변수 대입(`<<`)에 넣으면 빌드 때 경고한다(가능한 범위에서).
- 표시 전용 블록은 `with local.only(player):` 또는 `IsUserCP()` 분기로 감싼다. `StringBuffer` 쓰기도 이 안에서만.
- `misc.ObserverChat`·`misc.is_widescreen` 은 자체 완결 로컬 기능이라 바깥 판정(관전자 슬롯·contains_user)은 평범한 조건으로 두고 본문만 `local.f_allow()` 로 감싼다(Typewriter 와 같은 방식). is_widescreen 결과는 로컬 값(LocalValue)이라 공유 로직에 쓰면 디싱크 — sync 로 보낸다. (WP19)
- 로컬 메모리를 읽는 함수는 `textfx.warn_outside_local(이름)`(공개 `local.f_in_region()` 으로 판정, 호출 자리마다 한 번)으로 구역 밖 경고를 낸다. 조건을 돌려주는 함수는 `local.LocalCondition.wrap(cond)` 로 표식을 붙이면 local 의 경고를 그대로 쓴다. (WP17)
- CreateUnit 실패 트릭(13번째 줄)처럼 **공유 동작**은 모든 클라이언트에서 같은 조건으로 실행한다.

### 3.8 용량 규약

`EPSCRIPT_TRIGGER_BUDGET.md` 2·4절:

- **작은 트리거**를 선호한다. 액션 64개를 억지로 채우지 않는다(적층 이득이 사라진다).
- 저장소 고르기: 자주 읽는 값 = `EUDVariable`(72B), 비교·설정만 하는 값 = `Cell`(4B), 참/거짓 = `Flag`(1비트), 많은 값 = `EUDArray`(칸당 4B). 원소마다 변수 트리거가 필요할 때만 `EUDVArray`(72B). 매 프레임 모든 필드를 읽는 레코드 = 사슬 저장 + 레지스터(`pool`, 4.11).
- eudplib 의 바이트 복사(`f_dbstr_print`·`f_cpstr_print` 의 상수 글자·`f_memcpy`)는 **바이트당 실행 약 35**, `f_repmovsd_epd` 는 **단어당 약 35**(WP6b 실측). 매 프레임 도는 글은 상수를 버퍼에 굽고 숫자는 제자리에 쓴다(display 틀 방식). (WP6b)
- 서브루틴 호출 대상을 사이클마다 한 번 고치는 방식(호출 트리거의 next 와 각 서브루틴 끝의 next 를 미리 써 둠)으로 점마다의 분기를 없앨 수 있다(spawn 점당 −4).
- eudplib 0.81 페이로드 참고값(WP18 실측, 40벌 평균): 조건 1·액션 1~2 트리거 ≈ 250B, 액션 7 ≈ 555B, `f_dwread_cp` 1회 ≈ 1.0KB,
  변수 대상 액션(`SetMemoryEPD(상수 + 변수, …, 변수)`) 1개 ≈ 1.1KB, `EUDIf` 1개 ≈ 0.76KB.
- eudplib 0.81 적층 페이로드에서 트리거 크기는 조건·액션 수에 거의 비례한다(실측: 조건 1·액션 1 = 257B, 액션 8 = 682B, 액션 64 = 2,408B, 조건 0·액션 1 = 157B). 드물게 도는 경로(변환·초기화)는 64액션 트리거 여러 개보다 작은 트리거의 루프가 싸다. 칸마다 펼친 코드는 액션 수를 줄이는 것이 페이로드를 줄인다. (WP17)
- pool 은 풀마다 공유 코드가 약 20~26KB(페이로드) 든다 — 레코드가 몇 개뿐인 곳은 전역 변수가 싸다.
  - 변수 색인 읽기 실행 수(0.81 측정, S2 5.2): `EUDArray` 38, `EUDVArray` 12, `f_dwread_epd` 36.
- 공개 함수 docstring 에 **비용**을 적는다: "본문 N 트리거(1벌) / 호출 자리 M / 실행 K".
- 비용 표의 페이로드는 호출 자리 몫(40벌 평균)이라 공유 본문의 **한 번 페이로드**가 안 보인다. 본문이 큰 모듈은 빈 빌드 대비 한 번 페이로드도 적는다(WP9: lengthdir 98KB, atan2 111KB, 참고 eudplib f_lengthdir 57KB·f_atan2 125KB). 호출 자리마다 트리거를 수십 개 내는 인라인 펼치기(DPS `_mul_small` 등)는 실행이 조금 줄어도 피한다.
- 모듈마다 `docs\COSTS.md` 에 측정값을 남긴다(5.2 도구).
- 비용 목표(초안, 구현 뒤 실측으로 고친다):

| 항목 | 목표 |
|---|---|
| Int64 덧셈·wrap 뺄셈 호출 자리 | ≤ 3 트리거 |
| Int64 포화 뺄셈 | 상수 ≤ 4 인라인(분기 없음), 변수 호출 자리 ≤ 3, 실행 ≤ 30 (S8: 상수 2~4, 공유 함수 실행 25) |
| Int64 곱셈 실행 | ≤ 1,000 트리거 (war.py 2,268~4,626 → **WP4 최악 358**, 상수 최악 약 90) |
| Int64 나눗셈 실행 | ≤ 711 (war.py 수준 유지 → **WP4 최악 391**, 상수 제수 12~83) |
| Int128 덧셈·wrap 뺄셈 | 변수 = 공유 함수 호출 1 / 실행 ≤ 40 (실측 35·39), 32비트 값·상수 펼침 ≤ 9 / 9 |
| Int128 포화 뺄셈 | 변수 호출 1 / 실행 ≤ 50 (실측 43), 상수 ≤ 11 인라인 |
| Int128 곱셈 실행 | 64×64 ≤ 1,000 (**WP20 최악 585**), 128×128 ≤ 1,400 (최악 1,326), 상수 ≤ 200 (최악 196) |
| Int128 나눗셈 실행 | 32비트 제수 ≤ 711 (최악 703), 64비트 제수 ≤ 1,300 (실측 최악 1,047), 128비트 제수 ≤ 1,600 (실측 최악 1,272), 상수 제수 ≤ 250 (최악 231) — DPS 원본 호출당 약 23,000 |
| 128비트 10진 | 본문 ≤ 620 (윗 자리 372 + i64 본문 137 공유) / 실행 ≤ 600 (최악 536) |
| 32비트 10진 고정 폭 | 본문 ≤ 60, 실행 ≤ 80 |
| 64비트 10진 | 본문 ≤ 620, 실행 ≤ 450 |
| 도형 찍기 | 트리거 수가 도형 수·점 수와 무관, 좌표 1점 4B |
| 유닛별 저장 1700×N | `EUDArray` (scx 증가 < 1KB, R2 4.4) |
| BGM `tick` 호출 자리 / 재생 함수 | ≤ 10(실측 1) / ≤ 40 + 칸 수(실측 switch 19 + 칸, patch 12) |

### 3.9 금지 목록

- P1 마린 데스 칸(`0x58A364`, EPD 0)을 저장소로 쓰기. eudplib 변수의 기본 dest 이기도 하다 → 사용자 문서에 경고.
- `EUDVariable` 연속 배치 가정. 포인터 산술이 필요하면 `EUDArray` 나 전용 버퍼.
- 번호 간격 리터럴(604/2416/72/18)을 API 밖으로 노출.
- 로케이션을 0-based 정수로 받는 API. 로케이션은 **eudplib 규칙(이름 문자열 또는 1-based 번호)만** 받는다(원본 G_CB 는 곳마다 0/1 기준이 달라 오프바이원이 났다, S1 10절).
- `EUDStruct.alloc()` / epScript `P.alloc()` — 전역 풀이 페이로드를 약 19MB 늘린다(S2 5.2). 동적 레코드는 `pool` 을 쓴다.
- MSQC 채널 7(`0x58F524`)과 겹치는 eudplib `IsPName`(**이름이 변수이거나 플레이어가 CurrentPlayer 인 경로** — 데스 유닛 436 부터 라이트 변수)을
  SCR_DB 와 함께 쓰기. `scrdb` 가 `receiver()` 때와 빌드 끝(주 함수 뒤)에 검사해 SCR_DB 칸과 겹치면 빌드 오류(`_compat.pname_lightvar_units`).
  0.81 의 `f_check_id`·`SetPName`·`IsPName(상수 플레이어, 문자열)` 은 그 칸을 쓰지 않는다(WP18 실측). 상수는 `sync.PNAME_LIGHTVAR_ADDR`.
- NSQC(0.9.10.11 판)를 eudplib 0.81 에서 배열 출력·이름 원본·키 엣지와 함께 쓰기 — 수신 코드가 TypeError 로 멈추거나 배열 밖에 쓴다(WP13 실측, `sync` 가 막는다).
- 상수식 오프셋에 **2³¹ 이상 정수** 넣기: `Forward() << 0x80000000` 은 빌드 때 `'int' object has no attribute 'Evaluate'`, `RlocInt(0x80000000, 0)` 은 `offset out of range for i32`(eudplib 0.81.0 버그, WP1 실측). 음수(`f << -0x80000000`)로 넣으면 맞게 써진다.
- 페이로드 주소에 **음수 계수**가 붙은 식(`-EPD(arr)`, `k - EPD(arr)`)을 값으로 쓰기 — eudplib 0.81 은 재배치하지 못해 조용히 틀린 값이 된다
  (`f_dwread_cp(cpo)` 는 `Add, -cpo` 를 내므로 cpo 에 페이로드 주소를 섞으면 CP 가 어긋난다, WP18 실측). 두 페이로드 주소의 차이나
  양수 계수만 쓴다.
- `ExprProxy` 하위 클래스에 `_value` 라는 메서드·속성 두기(슬롯과 겹쳐 `'_value' is read-only`). eudplib `TrgComparison`/`TrgModifier`/`TrgPlayer`(`AtLeast`, `SetTo`, `P1` …)는 `ExprProxy` 라 `unProxy` 하면 정수가 된다 → 형식 검사는 `unProxy` 전에 한다(WP2).
- (WP12) `VProc(v, actions)` 의 `actions` 는 **변수 트리거보다 먼저** 실행된다 → `VProc(e, [*e.QueueAssignTo(t), t.AddNumber(k)])` 는 더하기가 대입에 덮여 사라진다(WP12 에서 위치 읽기가 틀렸던 원인). `t = k` 를 먼저 두고 `e.QueueAddTo(t)` 로 더하거나, 대입 뒤 따로 더한다.
- (eudplib 0.81 사실, WP21) 변수 번호로 dat 한 칸을 쓸 때 datpatch `now`(scdata 쓰기)는 바이트 칸에서 호출 자리가 수십 트리거다(images.useFullIscript 56). 자주 부르는 곳은 번호의 비트를 액션의 EPD·값·마스크 칸에 나눠 쌓는 공유 본문이 싸다(`bullet._storm_image_fn`, 본문 20·호출 1).
- (eudplib 0.81 사실) eudplib 변수 트리거의 기본 수정자는 SetTo(core/variable/vbuf.py:81 `2D 07`). 라이브러리 전용 변수를 로더로 읽을 때 수정자를 매번 싣지 않아도 된다(그 변수를 eudplib 연산의 원천으로 쓰지 않는다는 조건). (WP17)
- (eudplib 0.81 사실, WP14) 유닛·로케이션 이름 문자열(`EncodeUnit`/`EncodeLocation`)은 맵을 불러온 뒤에만 번호로 바뀐다 — 파이썬 시험의 모듈 전역 객체에 이름을 쓰면 `LoadMap` 먼저(euddraft 는 플러그인보다 맵을 먼저 읽는다).
- (eudplib 0.81 사실, WP14) `f_maskread_cp(cpo, 연속 마스크, ret=[EPD 식])` 은 읽은 값을 임의 EPD 칸(액션 값 칸 등)에 바로 쓴다 — 변수 복사 1회 절약. 0xFFFFFFFF(내림차순) 사슬은 eudplib 이 import 때 만들어 두므로 새 트리거가 없다.
- `VProc` 목록에 같은 변수를 두 번 넣기(변수 트리거 next 가 자기를 가리켜 무한 루프). 라이브러리 함수가 사용자 변수 둘을 한 VProc 에 넣을 때는 같은 객체인지 먼저 본다(`pool.free(g.handle)` 가 그 경우).
- 라이브러리 함수 안에서 받은 변수에 `+`·`-`·배열 색인 식을 바로 쓰기 — eudplib 은 **rvalue(함수 결과·식 결과)를 제자리에서 고친다**(`EUDVariable.__add__/__radd__`, `EUDArray[i]` 의 `EPD + i`). 받은 값을 두 번 이상 쓰면 새 변수에 복사하거나 `VProc(x, x.QueueAssignTo(t))` 로 옮긴 뒤 계산한다. 사용자 문서에도 "`i = f(); arr[i]; arr2[i]` 는 틀릴 수 있다 → `var i = f();`(복사)" 를 적는다.
- `_compat.py` 밖에서 eudplib 비공개 속성 접근.
- (Windows, 2026-09-17 실측) lupa 로 Lua 를 부르면서 `tools/lua_consts.lua_c_locale()` 로 감싸지 않기 — Windows 표준 파이썬(개발 venv)은
  시작할 때 `LC_CTYPE` 을 사용자 로캘(`Korean_Korea.949`)로 잡고 lupa 의 Lua 도 같은 ucrt 를 써서 Lua 문자 분류가 바뀐다(949: 바이트 0x80 이 `%c`·`%q` 에서
  제어문자, 1252: `string.upper`·`%a` 까지). 원본 TEP 는 정적 CRT(/MT)라 "C" 로캘이고 `setlocale` 을 부르지 않는다 → `SCRDB_Json` 은 `"글"`(EA B8 80)을
  그대로 둔다. 감싸지 않으면 `\u0080` 으로 바뀌어 venv 안의 scrdb 빌드·시험이 Lua·파이썬 매니페스트 대조 오류로 멈춘다(`가`·`글` 등 0x80 이 든 한글 이름·설명).
  euddraft 0.11 번들 파이썬은 플러그인 단계에서 `LC_ALL=C` 라 원래 해당이 없다(같은 한글 설명으로 고치기 전 코드 빌드 확인).
  `lua_consts.Lua`·`shape.CX`·`shape.lua_load` 는 이미 감싼다. 로캘이 C/POSIX/UTF-8 이면 가드는 아무것도 바꾸지 않는다(Linux·euddraft 동작 그대로).
- (2026-09-17 Windows 실측) 좌표·표 값을 만드는 Lua·파이썬 계산을 **플랫폼 C 수학 라이브러리**(`sin`·`tan`·`exp`·`pow` …)에 맡기기 —
  결과가 1ulp 달라지고 `int()` 자르기(D6)를 거치면 점이 바뀐다. CB Paint `CSMakeStar(5,144,96,0,CS_Level('Star',5,3),0)` 의
  6번째 점 y(참값 48)는 정확 반올림·Windows ucrt·**원본 플러그인** = 47, glibc·mingw(tepc) = 48. `shape` 은 Lua `math` 를 `_crmath`
  (정확 반올림)로 바꿔 원본 플러그인과 같은 값을 모든 OS 에서 낸다(4.13). `^`(C `pow`)는 바꿀 수 없다 — `x^2` 는 Lua 5.4 가 곱셈으로
  하므로 괜찮고, 새 도형 코드에서 다른 지수가 필요하면 곱셈이나 `math.exp(b * math.log(a))` 로 쓴다. `tools.lua_consts` 런타임은
  아직 플랫폼 수학이다 — 도형 계산에 쓰지 않는다. 헤드리스 tepc 대조에서는 star 4점이 이 차이로 다르다(`t_shape.py` `TEP_KNOWN`).
- (eudplib 0.81 사실, dbg 2026-09-18) `_compat.on_game_loop_start(fn)` 등록은 **프로세스에 계속 남는다**(빌드마다 불림) → 등록하는 모듈은
  한 번만 등록하고, fn 안에서 이번 빌드 상태를 보고 아무것도 안 낼 수 있어야 한다(`dbg` 방식). 게임 루프 시작 코드는 루프 몸체보다 먼저
  돌므로 거기서 복사한 값은 **앞 프레임 끝** 값이다. `EUDOnStart` 를 모듈 전역에서 부르면 `_start_functions1` 에 계속 남는다(같은 규칙).
- (dbg 시험) `f_dwread_epd(EPD(0x6509B0))` 는 CP 값이 아니라 **EPD(0x6509B0) 자신**을 돌려준다(읽는 동안 CP 를 그 EPD 로 옮기므로).
  실제 CP 는 `Memory(0x6509B0, Exactly, k)` 조건으로 본다. 페이로드 크기를 견주는 시험은 `ShufflePayload(False)`(적층 배치 고정).
- (dbg) 게임 메모리의 미러 구역 블록은 같은 SC 프로세스의 **앞 게임 값이 남는다** — 새 게임 시작 때 쓰는 칸을 지운다. 서명은 맨 마지막에 쓴다.
  디버그 블록·자동 판정은 싱글·LAN 전용(외부 프로세스 메모리 읽기). 배포 빌드는 `Dbg : 0`(트리거 0).

### 3.10 오류 처리

- 입력 검사는 **컴파일 시점**에 `EPError`(한국어 메시지)로 한다: 범위 밖 상수, 잘못된 옵션, 로컬 값 섞기, 재진입 가능성.
- `EUDIf()(f(x))` 에서 f 가 예외를 내면 `EUDIf()` 가 이미 블록을 열어 둔 채 남아 뒤 빌드가 'Block starting/ending mismatch' 로 깨진다 → 입력 검사가 있는 함수 결과는 먼저 변수에 받고 `EUDIf()(cond)`. (WP6b 실측)
- (WP7) eudplib `EncodeUnit`·`EncodeLocation` 의 **문자열**은 `LoadMap` 뒤에만 바뀐다. 모듈 전역(시험)에서 만드는 객체는 이름을 그대로 두었다가 빌드 때 바꾼다(plot.Plotter). `EncodePlayer('Player 8')` 는 문자열을 그대로 돌려줘 액션 검사에서 실패한다 → owner 문자열은 받지 않는다.
- 런타임 검사는 비용이 들므로 `debug=True` 옵션일 때만 넣는다(예: 스포너 대기열 넘침 알림).
- 단, **넘침·실패 카운터(`dropped`, `overflow`)는 항상 둔다.** 원본은 넘침 때마다 문구를 띄워 제작자가 문제를 알아챘다. 문구는 `debug`/`on_full` 로 켜고 끈다(S1 11-9).

### 3.11 epScript 연동

R3 2절 요약 + 0.81 재측정(WP0 보고서 5절):

- `import eudext.i64 as i64;` 형태로 쓴다(`from … import` 없음, 마지막 이름만 묶임). 세 단계(`import a.b.c as d;`)와 밑줄 이름(`import eudext._parts as parts;`)도 된다.
- 값 타입 객체는 `const` 로 묶는다. `var` 에 담으면 32비트 변수로 바뀐다(0.81 에서도 `Invalid initval`/`invalid amount` 오류 — `__repr__` 안내문이 보인다).
- 파이썬 함수를 부를 때 **키워드 인자는 된다**(`nf.Dec(v, width=5)`). 라이브러리 API 는 키워드 인자를 자유롭게 써도 된다. 인자에 리스트 리터럴 `[a]` 를 쓰면 `_ARR(...)`(EUDArray)로 번역된다 — 파이썬 리스트를 넘기려면 epScript `list(a, b)`(→ `FlattenList([a, b])`) 또는 사슬 API(예: `sp.job().layer()`). **`py_list(a, b)` 는 파이썬 `list(a, b)` 로 번역돼 실행 오류다**(0.81.0 실측, WP15).
- 0.81 에서 된다: 문자열 식(`const s = "abc";`, 연결, 메서드), 타입 변수(`var x: T = v;`, `static var x: T`), `import py_x;`(→ `import x`).
- 여전히 안 된다: `from … import`, 전역 `static var`, `const x: T`, epScript 함수 정의의 기본 인자, f-문자열, 실수, `**`.
- `return a < b;` 는 빌드 오류(`Invalid fields for action`), `return a == b;` 는 `Orphan condition` → `return a < b ? 1 : 0;`. 조건을 `var` 에 담는 `var r = cmp.lt(a, b);` 도 `Orphan condition`(WP1 실측).
- epScript `arr[i] = v;` 는 `_ARRW(arr, i) << v` 로 번역되고, arr 가 `ExprProxy`·`EUDVariable`·`ConstExpr` 가 아니면 `arr[i]` 를 **읽어** 그 값에 대입한다(**쓰기가 사라진다**, WP10 실측). 배열처럼 쓰는 eudext 객체는 `ExprProxy` 를 상속한다. `a.b += v` 는 `a.iaddattr("b", v)`, `a.b == v` 는 `a.eqattr("b", v)` 를 찾는다(없으면 읽고-쓰기).
- const 로 묶은 값 칸 객체(`Cell` 등 VariableBase)는 epScript `c -= 1;`·`c = 1;` 이 번역 오류(`Undefined variable c_1`), `var y = c;` 가 빌드 오류다 → `.v` 통로(`iaddattr`/`isubattr`/`isubtractattr`/`eqattr`…와 property)와 `assign/iadd/isub/isub_sat` 메서드를 둔다(WP2). `__repr__` 에 안내문을 넣으면 빌드 오류 메시지(`invalid amount: <…>`)에 보인다.
- `default` 는 epScript 예약어라 키워드 인자 이름으로 쓸 수 없다(`f(x, default="?")` 는 General syntax error) — 라이브러리는 다른 이름(`missing=`)을 같이 둔다. `None` 대신 `false` 를 받게 한다(display `tail=false`). (WP6b 실측)
- 값 타입 둘을 섞을 때 **왼쪽 피연산자의 연산자가 먼저 불린다**: `i64값 + x128` 은 `Int64.__add__` 가 Int128 을 모르는 값으로 보고 오류를
  낸다(파이썬 반사 연산자 `__radd__` 까지 가지 않음). 넓은 쪽 모듈 함수를 쓴다: `i128.add(a64, x)`, `i128.ge(a64, x)`. (WP20)
- epScript 함수는 인자 12~20개도 번역·빌드된다(`i128_ingame.eps` — 칸 넷 값 셋을 넘기는 함수). 반환 8개(`return q.w0, …, r.w3;`)도 된다. (WP20)
- epScript 함수 이름은 **그 함수 정의보다 뒤에서는** 값으로 넘길 수 있다(`sp.rtype_func("H", H)` → 번역 `sp.rtype_func("H", H)`, 전역 const 에서도). WP7 의 "Undefined rvalue" 는 정의보다 앞에서 쓴 경우다. `obj.hook(fn)` 식 등록 API 는 "정의 뒤에서 부르라" 고 문서화하면 된다. (WP12)
- `spawn.Order.attack(…)`(모듈.클래스.메서드 호출)은 번역 오류 `Undefined function f_attack`, `const O = spawn.Order;`(호출 없는 모듈 속성)는 문법 오류 → epScript 에 줄 값 객체 생성은 모듈 함수(`f_…`)로 둔다. (WP12)
- (WP21 실측) epScript `list(list(a, b), list(c, d))` 는 `FlattenList` 가 **펼쳐** `[a, b, c, d]` 가 된다 → 쌍 목록을 받는 API 는 펼친 정수 목록도 받는다(`cgrp.CGRPLayer(…, list(dx0, dy0, dx1, dy1))`).
- (WP21 실측) epScript 는 **클래스 메서드 이름은 바꾸지 않는다** — `cgrp.CGRP.load(…)` 는 그대로 번역된다(모듈 함수 `m.foo()` 만 `m.f_foo()`). 전역 `const x = m.Cls.make(…)` 식 생성자는 `f_` 걱정 없이 쓸 수 있다.
- 전역 `var x = -5;` 는 문법 오류(음수 초기값), `var a = 1, b = 2;`·`const a = Db(1), b = Db(2);` 처럼 쉼표로 이은 선언도 오류 → 한 줄에 하나, 음수는 16진(`0xFFFFFFFB`)으로(WP5 실측). `nf.dp.dec16(v)` 처럼 세 단계 호출은 `f_` 가 붙지 않는다.
- epScript 함수 이름이 **eudplib 전역 이름과 같으면 `f_` 가 붙지 않는다**(WP4 실측: `function bits()` → `bits`, `bitsplit` → `f_bitsplit`).
  또 `function mul()` 은 `f_mul` 로 번역되어 그 모듈 안의 eudplib `f_mul` 을 가린다 — 예제·시험 함수 이름은 eudplib 이름을 피한다.
- `const q, r = i64.divmod(x, y);` 는 `List2Assignable([…])` 로 번역되어 튜플 반환을 그대로 푼다(WP4 확인).
- `x.v *= y; x.v /= y; x.v %= y; x.v &= y; x.v |= y; x.v ^= y; x.v <<= n; x.v >>= n;` 은 `imulattr`·`ifloordivattr`·`imodattr`·
  `iandattr`·`iorattr`·`ixorattr`·`ilshiftattr`·`irshiftattr` 를 찾는다. `arr[i] *= v;` 등은 `imulitem`·`ifloordivitem`·`imoditem`·
  `ianditem`·`ioritem`·`ixoritem`·`ilshiftitem`·`irshiftitem`. 값 타입은 이것들을 둔다(WP4).
- epScript 예약어 `var` 는 모듈 함수 이름으로 부를 수 없다(`scrdb.var(…)` 는 번역 오류 "Chunk-level error") → `scrdb.slot(…)` 별칭(WP18).
- epScript 전역 `var a = 1, b = 0;` 은 번역 오류(`General syntax error`) → 한 줄에 하나. const 초기화의 문자열 곱·연결 (`"\x04" * 151 + "…"`)은 된다. epScript 문자열 안의 `\x13`·`\n` 은 파이썬 문자열 탈출로 그대로 넘어간다. (WP17)
- epScript 는 함수 이름을 값으로 넘길 수 없다(`obj.hook(fn)` → `Undefined rvalue fn`). 본문을 받는 API 는 `foreach (x : obj.each())` 생성기(eudplib `EUDLoop*` 방식 — `EUDSetContinuePoint` 로 `continue` 지원)를 둔다(WP7).
- 전역 `const` 이름 `P1`~`P12`(그리고 eudplib 전역 이름)는 `Name collision with eudplib global` 번역 오류(WP7).
- `list(a, b)` 는 FlattenList 라 중첩 목록·반복 가능한 객체를 푼다 — 풀리면 안 되는 객체는 `dont_flatten = True`(shape.Shape·ShapeSet), 좌표 목록은 평평하게(`Shape.from_flat`) (WP7).
- epScript 함수는 EUDFunc 라 **문자열 인자를 받을 수 없다**(예: `function show(text) { … DisplayText(text) … }` 는 빌드 오류) — 문자열을 받는 도우미는 파이썬 함수로 두거나 호출 자리에 풀어 쓴다(WP16·WP9).
- `f_` 로 시작하는 **모듈 함수를 부를 때**도 `m.f_foo()` 는 `m.f_f_foo()` 로 번역된다(WP14 실측, 함수 정의만의 문제가 아님) → epScript 문서·예제는 `m.foo()`. 모듈 `__getattr__` 로 `f_f_` 이름에 안내 오류를 낼 수 있다(bullet).
- **액션 문장의 문자열 리터럴 인자에 짝 없는 `)` 가 있으면 번역문의 닫는 괄호가 사라져 파이썬 문법 오류**가 난다: `DisplayText("1) 보스");` → `DoActions(DisplayText("1) 보스")`(`)` 하나 모자람).
  `epsCompile` 오류 수는 0 이고 빌드(모듈 import) 때 `SyntaxError: unterminated string literal` 로 멈춘다. 짝 없는 `(` 나 `]`·`}`, 짝이 맞는 `(2)` 는 괜찮고,
  `printAll("1) 보스");`(함수 호출), `DisplayText(sd.design("1) 보스"));`(안쪽 함수로 감쌈), `const s = "1) 보스"; DisplayText(s);` 도 괜찮다. → 액션에 넣는 글에는 `1.`·`①` 등을 쓰거나 const 에 담는다.
- 전역 `const x = m.f(…);` 는 `_CGFW` 가 **import 때 바로** 계산한다(파이썬 값 그대로 — 문자열이면 str). 뒤에 정의된 이름을 참조해 `NameError` 가 나면 `ExprProxy` 로 두고 게임 시작 때 계산한다.
  전역에서 부르는 설정 함수(`sd.set_style` 등)는 `const` 로 받는다.
- 전역 `const a = [1, 2];`(배열 리터럴)는 시작 트리거를 만든다(`_CGFW`). 한 프로세스에서 두 번째 빌드부터 `Reforwarding without reset` 오류 — 시험·도구가 여러 번 빌드하는 예제는 초기값 배열 `EUDArray(list(1, 2))` 를 쓴다(맵 빌드 한 번에는 문제없음).
- 전역 `const A = [1, 2, 3];` 배열 리터럴은 게임 시작 때 칸을 채우는 트리거(`_ARR`)를 만들고, 한 프로세스에서 두 번째 빌드 때 `Reforwarding without reset` 오류를 낸다 → 상수 표는 `const A = EUDArray(list(1, 2, 3));`(초기값이 박힌 배열, 트리거 없음).
- epScript 함수에 문자열 인자를 넘길 수 없다(`invalid amount: '…'`) → 이름 줄은 부르는 자리에서 찍는다.
- 전역 `var a = 1, b = 2;` 는 문법 오류 → 한 줄에 하나. 여러 값 반환은 `const a, b = f();`(함수 안)·`a, b = f();`(전역 var 대입).
- 배열처럼 쓰는 값 타입 배열(`Int64Array`)은 `ExprProxy` 를 상속하고 `iadditem/isubitem/isubtractitem/eqitem…` 을 둔다.
  원소 읽기가 사본인 타입은 사본에 메서드·`.v` 제자리 연산을 막는다(epScript `arr[i].v += 1;` 은 번역상 쓰기가 사라진다).
- epScript 변수 이름으로 파이썬 예약어(`pass` 등)를 쓰면 번역 오류(`Name collision with Python keyword`).
- `f_` 로 시작하는 epScript 함수 이름은 번역 결과가 일정하지 않다(`function f_shift()` → `f_f_shift`, `function f_mul()` → `f_mul` —
  eudplib 에 같은 이름이 있으면 접두사를 안 붙이는 것으로 보임) → 예제·시험에서는 `f_` 로 시작하는 이름을 쓰지 않는다.
- 여러 값 반환 `return a.lo, a.hi;` 와 파이썬 함수 키워드 인자 `x.isub_sat(y, inline=True)`, `i64.fmt(x, signed=True)` 는 번역·빌드된다.
- epScript 에는 `with`·람다가 없다 → 컨텍스트 매니저·콜백 API 는 `begin_…()`/`end_…()` 짝을 같이 둔다(`local.begin/end`, `units.Capture().begin/end`, `dat.begin_actions/end_actions`, `dat.begin_temporary/end_temporary`). `printAll`·`Db(8)`·`dwwrite_epd`·`EPD(buf)` 는 번역·빌드된다(WP1 예제).
- epScript `a -= a;` 는 eudplib 버그로 0xFFFFFFFF 가 된다 → `a = 0;` 으로 쓴다(3.5).
- 모듈마다 `examples\` 에 epScript 사용 예 하나와 번역 시험(`epsCompile`)을 둔다.

### 3.12 문서화

공개 함수·클래스 docstring 형식:

```
한 줄 요약.

인자: …
반환: …(조건이면 어떤 형태인지)
비용: 본문 N / 호출 M / 실행 K (측정일)
CP: 바꾸지 않음 | 바꿈(어떻게)
로컬: 공유 안전 | 로컬 전용
epScript: 사용 예 한 줄
출처: CtrigAsm 함수 이름, 재사용한 코드(파일:줄)
```

---

## 4. 모듈 설계

### 4.0 계층과 의존

| 계층 | 모듈 | 의존 |
|---|---|---|
| 0 기반 | `_compat`, `_parts`, `errors`, `boot` | eudplib |
| 1 값 | `cmp`, `cell`, `i64`, `mathx`, `i128` | 0 |
| 2 글자 | `numfmt`, `strdesign`, `display`, `textfx`, `chat` | 0, 1 |
| 3 게임 | `players`, `units`, `pool`, `local`, `sync`, `datpatch`, `bullet`, `bgm`, `misc` | 0~2 |
| 4 도형 | `shape`(+`_crmath`), `plot`, `spawn`, `cgrp` | 0~3 (`shape` 만 lupa, `_crmath` 는 표준 `decimal` 만, `cgrp` 는 `bullet`·`datpatch` — bullet 의 모듈 내부 도우미 `_owner`·`_num`·`_sprite_call` 을 쓴다) |
| 5 앱 | `scrdb` | 0~3, `tools.lua_consts` |
| 디버그 | `dbg` | 0 (`Int64`·`Int128`·`Cell` 은 넘겨받을 때만 — import 하지 않음) |
| 개발 | `testing`, `tools` | eudplib |

아래 각 절의 형식: **목적 / 근거 / API / 의미·알고리즘 / 비용 목표 / 시험 / 위험·미정**.

---

### 4.1 `_compat`, `_parts`, `boot`, `errors` — **WP0 완료**

**목적**: 판 검사와 비공개 API 격리, 여러 모듈이 쓰는 내부 부품. 구현과 이식 메모는 WP0 보고서 9절.

**`_compat`**
- `check(strict=False)`: eudplib 판이 **0.81.x** 가 아니면 경고, 필요한 비공개 이름(`_REQUIRED`, 지금 18개)이 없으면 오류.
- 접근자: `cpcache_var`, `cpcache_cond`, `isolated_scope`, `capture_payload`, `reset_build_state`, `register_build_reset`, `set_game_loop_start`, `chk_string_section`, `eps_compile`.
- 판별 도우미: `is_const`, `is_var`, `is_varbase`, `is_eudfunc`, `split64_const`.
- 배치 B 가 더한 것(파일 끝 WP 블록): WP10 `predefine_returns(func, rets)`(EUDFunc 본문이 반환 변수에 바로 쓰게), `reset_new_unit_loops()` / WP13 `eudarray_ptr_view` 등 3개 / WP3 `eps_lshift_caller(depth=2)`(epScript 식 `a << b` 의 번역 `_LSH` 가 부른 것인지 — `Int64.__lshift__` 가 대입이라 시프트 식을 막는다) / WP15 `check_datpatch`, `scdata_members`, `scdata_member_info`, `scdata_flag_masks`, `scdata_cast`, `scdata_epd_subp`, `onstart_phase`, `on_start_after_main`, `on_game_loop_start`, `dwpatch_epd`, `unpatch_all`. 판 검사 이름은 `_REQUIRED` 에 합쳤다.
- 배치 D 가 더한 것: WP5 `hook_format_field(hook)`(eudplib 서식 필드 처리 가로채기 — `enable_format_spec`), WP16 `mpq_read_file(path, name)`(출력 맵 MPQ 안 파일 읽기), WP4 `eudplib_calc_caller(depth=2)`(32비트 변수가 왼쪽인 산술이 값 타입을 조용히 바꾸는 경로 감지).
- 배치 C 가 더한 것: WP11 `check_pool()`(`_EUDVArrayData` 모양 검사), `custom_varray(triples)`(원소별 dest/value/next 72B 배열 — pool 사슬 저장), `chk_string_section_name()`(scmodel 글 기록). 판 검사 이름(`_LSH`, `_EUDVArrayData`)은 `_REQUIRED` 에 합쳤다.
- 필요한 WP 가 더할 것: `varbuffer_initvals`, `funcbody_hook`.
- 판이 올라가면 `reset_build_state` 가 부르는 비공개 이름 4개를 다시 확인한다(`check()` 가 알려 준다).

**`_parts`** (DPS `ctrig/core.py` 등에서 옮겨 0.81 에 맞춤)
- `branch(cond, ontrue, onfalse)`, `jump_if`, `jump_if_not`, `once_branch()` — `EUDBranch` 가 변수 필드 액션을 패치하지 않는 문제를 피한다. 0.81 `SetNextTrigger` 로 꼬리 점프 트리거를 없앴다(DPS 판보다 1씩 적음).
- `set_masked(addr, value, mask)`, `write_addr` — 값·마스크가 변수여도 패치된 `SetMemoryX` 1액션.
- `and_const(v, m)` — 0.81 `v & 상수` 감싸기(호출 2 / 실행 3).
- `cp_fix(actions)` — 원시 CP 쓰기에 캐시 갱신 액션을 붙인다(0.81 CP 캐시 = `EUDXVariable(EPD(0x6509B0), SetTo, 0)`, 값 칸 주소 같음).
- `SubLabel` + `call_sub(label, conds=None, acts=None, preserved=True)` — 인자 없는 서브루틴 트램펄린(호출 1트리거, 재진입 금지). 본문은 `with sub.define():`.
- `isub32(a, b)`(wrap, `a is b` → `a << 0`) / `isub_sat32(a, b)`(포화) — 3.5-6. `EUDLightVariable -= 변수` 는 0.81 에서 빌드 오류라 임시 변수를 거친다.
- `all_const`, `has_var_fields`.
- WP4 가 더한 것: **자기 수정 갈림 트리거 틀** `SelfFrame`(`node`/`test`/`tree`/`finish` — 참이면 자기 next 를 바꾸는 조건 트리거와 매 호출
  첫머리 되돌림 묶음), **변수 트리거 사슬** `var_chain(pairs, end)`·`add_modifiers(*vs)`, **결정 나무** `DNode`·`DLeaf`·`dtree`·
  `emit_dtree`·`dspine`·`dpresets`·`dlabel`·`dgoto`(DPS 이식판 a7aad90 `war.py:493~555` 를 옮김). i64 곱셈·나눗셈·시프트 본문이 쓴다.
  `t_parts.py` 에는 아직 직접 시험이 없고 `t_i64_ops.py`(195,805 판정)가 간접으로 덮는다 — 다음 배치에서 `t_parts` 에 단위 시험을 더하면 좋다.
- **조건 칸 채우기 묶음**을 `cmp` 에서 옮겼다(WP1 제안): `Plan`(상수 쓰기 → 변수 채우기 SeqCompute 한 줄 → 조건 트리거,
  `uses(src)` 로 같은 변수를 두 번 원천으로 쓰는지 확인), `selfcond(cmp, amount)`(자기 비트마스크 칸을 읽는 조건),
  `placeholder(value=0)`(amount 자리 `Forward`, 3.4), `flag_cond(plan, init)`(자기 칸 깃발). `cmp` 는 여기서 가져온다
  (`t_cmp.py` 36,825 판정 그대로 통과). `i64` 가 64비트 비교에 쓴다. WP2 `cell.py` 안의 사본(`_selfcond`, 줄인 `_Plan`)도 다음에
  이것으로 바꿀 수 있다.

**`boot`**: 2.3 절.

**시험**: `tests\t_parts.py`(2,591 판정), 비용은 `docs\COSTS.md`(20항목).

---

### 4.2 `cmp` — 안전 비교와 부호 있는 비교 — **WP1 완료**

**근거**: 부호 있는 비교 CtrigAsm TT(R1: `iAtLeast` 4회, 그러나 `f_SHRead` 70·부호 뺄셈 다수), 경계값 처리(`gt(x, 0xFFFFFFFF)` 등),
0.76.14 비교 버그(R3 1.6). DPS 이식판(a7aad90) `core.c_*`, `tlib.flip/cmp32`, "TT 비교 계획·조건 칸 채우기"(`tlib.py:204~`, `core.py:365~` pre_fill) 재사용.

**API** (모듈 함수는 `f_이름`, 파이썬 별칭은 `f_` 없는 이름 — 3.1)

```python
from eudext import cmp
cmp.ge(a, b) cmp.le(a, b) cmp.gt(a, b) cmp.lt(a, b) cmp.eq(a, b) cmp.ne(a, b)   # 부호 없음, 모든 경계 정확
cmp.sge(a, b) cmp.sle(a, b) cmp.sgt(a, b) cmp.slt(a, b)                        # 부호 있는 32비트
cmp.between(x, lo, hi, signed=False)                                            # lo ≤ x ≤ hi (양 끝 포함)
cmp.f_wread_signed(epd, subp=0, *, ret=None)  # = cmp.wread_signed, 16비트 부호 확장 읽기
cmp.f_bread_signed(epd, subp=0, *, ret=None)  # = cmp.bread_signed, 8비트 부호 확장 읽기
```

- 피연산자: 정수 상수(−2³¹ ~ 2³²−1, **모든 함수에서 2³² 나머지** — 부호 없는 함수의 `-1` = `0xFFFFFFFF`), 주소식 상수(`Forward`·`EPD(…)`),
  `EUDVariable`, 읽기 전용 값 칸(`EUDLightVariable`, `getValueAddr()` 를 가진 객체 — WP2 `Cell` 이 그대로 들어온다).
  `EUDLightBool`·`Condition`·범위 밖 정수는 `EPError`.
- 반환: 조건 하나면 **새 `Condition`**, 여럿이면 **조건 목록(AND)**. 상수끼리·같은 객체끼리는 `Always()`/`Never()` 로 접는다.
  EUDLightBool·0/1 변수는 돌려주지 않는다(OR 도 아래의 자기 칸 조건으로 Condition 이 된다).
- 앞 계산은 **부르는 순간** 낸다 → 돌려받은 조건은 **꼭 한 번** 트리거에 놓는다(안 놓으면 빌드 때 `Orphan condition`).
  루프 조건은 조건 자리에서 부른다(`EUDWhile()(cmp.lt(i, n))`). `RawTrigger(conditions=…)` 에도 넣을 수 있다(필드가 모두 상수식).

**의미·알고리즘**
- 상수 비교 → 구간 [lo, hi]: `[x ≥ lo]`·`[x ≤ hi]` 조건 목록(트리거 0). 경계: `gt(x, 0xFFFFFFFF)`·`lt(x, 0)`·`sgt(x, 0x7FFFFFFF)`·`slt(x, −2³¹)` = Never.
- 부호 있는 상수 구간이 0 을 걸치면(`sge(x, −5)`, `sle(x, 5)`, `between(x, −16, 16, signed=True)`) "틈 [hi+1, lo−1] 밖" = OR.
  `ne(x, k)`(k ≠ 0, 0xFFFFFFFF)도 같은 모양. **초안의 EUDLightBool(트리거 2) 대신**:
  - `EUDVariable` x: 조건 자신의 비트마스크 칸(+0)에 `x − 틈 시작` 을 채우고 `[그 칸 ≥ 틈 길이]` (호출 1 / 실행 2, 제자리 부정 됨).
  - 읽기 전용 칸 x: 자기 칸 깃발 — `칸 ← 1`, `[x ∈ 틈] → 칸 ← 0`, 조건 `[칸 ≥ 1]` (호출 2 / 실행 2).
- 변수끼리(부호 없음): 한쪽 값을 조건 amount 칸(+8)에 채운다. `ge`/`le`/`eq` = `[a op 채운 b]`, `gt`/`lt` = `[a ≥ b+1] ∧ [b ≤ 0xFFFFFFFE]`
  (DPS a7aad90 "gt" 원자). 한쪽이 칸이면 칸을 읽는 쪽에 둔다. `ne` = 자기 칸 ← `~b + a`, `[칸 ≤ 0xFFFFFFFE]`. 칸끼리는 한쪽을 `f_dwread_epd` 로 읽는다.
- 변수끼리(부호 있음): **임시 변수 없이** 조건 하나의 두 칸에 `a+2³¹`(+0), `b+2³¹`(+8)을 채우고 `[+0 ≥ +8]`.
  `sgt` 는 +8 에 `b+2³¹+1` 을 넣고 `[+8 칸 ≥ 1]` 을 덧붙인다(b = 2³¹−1 이면 0 으로 돈다). 초안의 "사본 + 포화 뺄셈" 보다 싸다(실행 3).
  한쪽이 칸이면: 부호 없는 비교 + 부호 보정 트리거 2(x 음수·y 양수 → 거짓, x 양수·y 음수 → 참) + 깃발.
- `between` 변수 끝: `ge` + `le` 를 한 묶음(SeqCompute 한 번)으로. 부호 있는 변수 x 는 `x+2³¹` 을 한 칸에만 채우고 두 조건이 같이 읽는다.
- **채운 조건과 eudplib 부정**: amount 칸을 실행 중에 채우는 조건은 amount 자리에 정수가 아닌 `Forward`(값 0)를 둔다.
  정수 자리 표시를 두면 `EUDNot`·`EUDSCAnd(neg=True)` 의 `negate_cond` 가 제자리에서 비교를 뒤집어 **틀린 답**이 된다(예: `AtLeast 0` → Never).
  `Forward` 면 eudplib 이 분기로 부정한다(결과 정확, 트리거 조금 더). 자기 칸·깃발 조건은 amount 가 정수 상수라 제자리 부정이 맞다.
- `f_wread_signed(epd, subp)` = `f_wread_epd` + `[값 ≥ 0x8000] → += 0xFFFF0000` 트리거 1. `f_bread_signed` 도 같다(0x80 / 0xFFFFFF00).
  **CtrigAsm `f_SHRead` 와 의미가 다르다**: 원본은 dword 의 하위 16비트 + 비트 31 로 부호를 정했다(32비트로 저장한 좌표 표).
  그런 표를 eudplib 으로 옮기면 `f_dwread_epd` 로 읽으면 되고, 이 함수는 진짜 16비트 필드(i16)용이다.
  둘째 인자 이름은 초안의 `off` 대신 eudplib `f_wread_epd(epd, subp)` 와 같은 `subp`, 결과 변수는 `ret=[v]`.

**비용** (cmp 자체, 2026-09-16, `docs/COSTS.md` "cmp (WP1)" — 표 값에는 소비 트리거 1 이 들어 있다):
상수 0 / 0 · OR 상수 변수 1 / 2, 칸 2 / 2 · 변수끼리 `ge/le/gt/lt/eq` 1 / 2, `ne/sge/sle/sgt/slt` 1 / 3 · 칸·변수 `ge` 류 1 / 2, `ne` 2 / 3, `sge` 류 4 / 5(목표 초과, 드문 조합) ·
칸끼리 3 / 39 · `between` 변수 끝 1 / 3(부호 있음 1 / 4) · 읽기 = eudplib 읽기 + 1 / 1.
eudplib 0.81 연산자 대비: `a < b` 실행 3 → 2, `a != b` 호출 2·실행 4 → 1·3, `a >= b`·`a == b` 같음.

**시험**: `tests/t_cmp.py` 36,825 판정 — 10 함수 × (변수·칸 쌍 4종 × 경계값 81쌍 + 무작위 100, 상수 12개 × 좌·우 × 변수·칸, 주소식 5개,
상수끼리 접기, 같은 객체) × 문맥(EUDIf, neg, EUDNot 값, RawTrigger, EUDSCAnd/EUDSCOr ± neg, 중첩 목록, EUDTernary ± neg, EUDElseIf,
EUDWhile 3회 재계산), `between` 상수 구간 100 + 변수 끝 24, 읽기(subp 0~3 상수·변수, ret), epScript 예제 8 함수 + 인게임 점검 함수(`selftest` = 15),
`return cmp.lt(a, b);`·`var r = cmp.lt(a, b);` 빌드 오류 확인, euddraft 0.11 빌드.
**위험**: 조건 칸을 실행 중에 채우는 방식이 SC:R 에서 에뮬레이터 가정대로인지(비트마스크 칸은 EUDX 표식이 없으면 무시) — eudplib 0.81 `<` 가 같은 방식을 쓴다. 인게임 점검은 `examples/cmp_example.eds`("점검 15 / 15").

---

### 4.3 `cell` — Ccode — **WP2 완료**

**근거**: 사용자 요청(Ccode 를 그대로 쓰고 싶다). DPS `CD` 490, `SetCD` 503(대부분 비교·설정). 2026-09-17 실험(`docs/proto/cell_exp.py`).
CtrigAsm 원본 `CreateCcode`/`CreateCcodes`/`CreateCcodeArr`(CtrigAsm v5.5.lua:75959~75979), `CD`/`CDX`/`SetCD`/`SetCDX`/`AddCD`/`SubCD`(LibraryFor322.lua:586~625, 740~759).
DPS 이식판(a7aad90)은 Ccode 를 `EUDVariable` 로 바꿨고(`eud/ctrig/core.py:257`) 칸 조건·액션 모양(`eud/ctrig/cells.py` `epd_cond`/`epd_act`)을 참고했다.
변수 색인 조건 패치는 `units.UnitField`(WP10), 조건 칸 채우기는 `cmp`(WP1) 방식.

| 동작 | `EUDLightVariable` 그대로 | `Cell` 에서 (구현) |
|---|---|---|
| 상수 대입·비교 | 됨 | 그대로 (대입 1 / 1, 비교 0 — 경계는 `cmp` 가 Always/Never 로 접는다) |
| 변수 대입 `c << v`, `c += v` | **오류** | `SeqCompute` 로 자동 전환 (호출 1 / 실행 2). 칸 값(`Cell`·`EUDLightVariable`)은 `f_dwread_epd` 로 읽어서 |
| 변수로 읽기 | **오류** (`v << lv` 도) | `c.read(ret=None)`·`c.v` → `f_dwread_epd` (공유 본문 + 호출 1~2 / 실행 약 36) |
| `-=` | 포화 | **wrap** 으로 고정(`VariableBase.__isub__` 덮어쓰기 → `_parts.isub32`, 변수 3 / 5, 같은 칸 = 0). epScript 통로 `c.v -= v`(`isubattr`), `c.isub(v)` 도 wrap |
| 포화 뺄셈 | `SubtractNumber(k)` 액션 | `c.isub_sat(v)`(값이 변수·칸이어도, `_parts.isub_sat32`, 변수 1 / 2), `c.SubtractNumber(k)`(eudplib 그대로 포화 액션), `SubCD`(= `subtract_cd`), epScript `isubtractattr` |
| 변수와 비교, `AtMost(0xFFFFFFFF)` | `EUDNot` 에서 틀림 | 비교 연산자·`AtLeast/AtMost/Exactly`·`…attr` 모두 `cmp` 로 (`Forward` 자리 표시·경계 접기 — 부정도 맞음) |

**경고(문서·docstring 에 적음)**: `EUDLightVariable -= x` 는 포화, `Cell -= x` 는 wrap. 자주 읽는 값을 `Cell` 에 두면 읽을 때마다 실행 약 36 → `EUDVariable` 에 둔다.

**API**

```python
from eudext.cell import Cell, Flag, CellArray, PCell, CreateCcode, CreateCcodes, CreateCcodeArr
from eudext.cell import CD, CDX, SetCD, SetCDX, AddCD, SubCD   # CtrigAsm 이름 (원래 의미, SubCD = 포화)
# 모듈 함수(epScript `cell.cd(…)` → `cell.f_cd(…)`): f_cd, f_cdx, f_set_cd, f_set_cdx, f_add_cd, f_subtract_cd
# 파이썬 별칭: cd, cdx, set_cd, set_cdx, add_cd, subtract_cd  (f_sub_cd 는 두지 않는다 — 3.5 이름 규칙)

c = Cell(0)                   # = CreateCcode(). 초기값: 정수·주소식(트리거 0) / 변수·칸(그 자리에서 대입)
c = Cell.at(addr)             # 있는 칸 감싸기 (4의 배수 상수, 0x58A364 는 오류)
a, b = CreateCcodes(2)        # n = 1 이면 Cell 하나 (CtrigAsm table.unpack 과 같음). CreateCcodes(n, init)
arr = CreateCcodeArr(15)      # = CellArray(15) 또는 CellArray([상수 초기값…])
f = Flag()                    # EUDLightBool 하위 클래스 (Set/Clear/Toggle/IsSet/IsCleared, EUDIf()(f))
pc = PCell(init=0, count=8)   # CellArray 하위 클래스, 색인 = P1~·0~count−1·CurrentPlayer·변수

c << v; c += v; c -= v; c.isub_sat(v); c.read(ret=None); c.v; c.addr; c.epd
c.assign(v); c.iadd(v); c.isub(v)                          # epScript 통로 (+ c.v = / += / -= / == …)
c == v; c != v; c <= v; c < v; c >= v; c > v; c.AtLeast(v); c.AtMost(v); c.Exactly(v)   # cmp 규칙
CD(c, 값=1, 비교=Exactly)            # CtrigAsm 순서. CD(c, AtLeast, 3)·CD(c, AtLeast)(값 1) 도 받는다 → 조건
CDX(c, 값, 마스크, 비교=Exactly)     # 마스크는 정수 상수 → 조건
SetCD(c, 값=1); SetCD(c, SetTo|Add|Subtract, 값); AddCD(c, 값=1); SubCD(c, 값=1); SetCDX(c, 값, 마스크)   # → 액션
arr[3]                        # Cell 뷰 (arr.cell(3), 같은 k 는 같은 객체)
arr[i]; arr.get(i, ret=None)  # 변수 색인 = 읽은 값 (EUDArray 와 같음)
arr[i] = v; arr.set(i, v); arr.iadditem(i, v); arr.isubitem(i, v)(wrap); arr.isub_sat(i, v)(포화, = isubtractitem)
arr.eqitem/neitem/leitem/ltitem/geitem/gtitem(i, v)   # = eq/ne/le/lt/ge/gt
arr.array; arr.epd; arr.addr; len(arr); for c in arr: …
```

**의미·알고리즘**
- `Cell` = `EUDLightVariable` 하위 클래스. 값 칸 주소를 자기 슬롯 `_addr` 에 두고 `getValueAddr()` 를 덮어쓴다(eudplib 은 칸 주소를 늘 이 메서드로 읽는다 — `_memaddr` 는 `eudlv.py` 안에서만 쓰인다) → 비공개 이름 없이 뷰(`Cell.at`, 배열 원소)를 만든다. 주소식 초기값은 `EUDArray([식])` 한 칸에 굽는다(`_compat.eudarray_addr`).
- 값 분류(정수·주소식·변수·칸): 칸 값은 `f_dwread_epd` 로 읽어 변수로 바꾼 뒤 쓴다. 같은 칸끼리 `c -= c`·`c.isub_sat(c)` = 0(`_parts` 가 접음), `c << c` = 트리거 0, `c += c` = 읽어서 두 배.
  `Flag`/`EUDLightBool`·조건·목록·범위 밖 정수(−2³¹ ~ 2³²−1 밖)·비교/수정자 상수(`AtLeast`, `SetTo` — 인자 순서 실수)는 `EudextError`.
- 파이썬 `if c:` 는 `EudextError`(늘 참이 되는 실수 방지). `EUDIf()(c)` 는 eudplib 이 `[c ≥ 1]` 로 바꾼다.
- 비교: 모든 비교가 `cmp` 를 부른다(칸 피연산자). eudplib `VariableBase.AtLeast/AtMost/Exactly` 도 덮어쓴다 — 비교값이 변수면 `EUDNot` 이 틀리고(3.4),
  **상수라도 `EUDNot(AtMost 0xFFFFFFFF)` 가 넘쳐 늘 참**이다(WP2 실측, 3.4 보탬).
- `CellArray(ExprProxy)`: `EUDArray` 를 감싼다(epScript `arr[i] = v;` 가 사라지지 않게 — 3.11). 상수 색인 → 캐시된 `Cell` 뷰(같은 객체라 파이썬 `arr[k] += v` 의 되쓰기를 건너뜀).
  변수 색인 쓰기는 `EUDArray.set/iadditem/isubtractitem`(eudplib `iset`, VProc). **wrap 뺄셈은 `neg = 0; _parts.isub32(neg, v)` 뒤 `iadditem`** — eudplib `isubitem` 의 마스크 Add 반전 기법(인게임 확인 전, A-1)을 쓰지 않는다(3.5-6·8).
  변수 색인 읽기 `arr[i]` = `f_dwread_epd(epd + i)`. 변수 색인 비교는 `MemoryEPD(0, 비교, 값)` 의 플레이어 칸(+4)에 `epd + i`, 값이 변수면 amount 칸(+8, `Forward` 자리 표시)에 값을 한 `SeqCompute` 로 채운다.
  경계(`ge 0`·`le 0xFFFFFFFF` = Always, `gt 0xFFFFFFFF`·`lt 0` = Never)는 접고, `gt`/`lt` 변수는 `[칸 ≥ v+1] ∧ [v ≤ 0xFFFFFFFE]`·`[칸 ≤ v−1] ∧ [v ≥ 1]`, `ne` 는 자기 칸 깃발(`cmp` 와 같은 방식).
- `PCell(CellArray)`: 색인을 `EncodePlayer` 로 풀고(P1~P12·0~count−1), `CurrentPlayer`(13)는 `f_getcurpl()`(캐시 확인 + **사본** 변수 — 캐시 변수 자체가 아니다, WP2 확인), 변수는 그대로.
  `AllPlayers`·Force 같은 묶음은 오류(`players.each`/`run_as` 로 돈다). `players.PerPlayer(Cell)` 도 동작한다(시험함) — 변수 색인이 EUDSwitch(호출 15)라 `PCell`(1~2)이 싸다.
- CtrigAsm 이름은 원래 의미: `SubCD` = SC Subtract(포화). `SetCD`/`AddCD`/`SubCD`/`SetCDX` 는 **액션**을 돌려준다(값이 변수면 `DoActions`/`Trigger` 가 채운다. `RawTrigger` 는 상수만). 칸 값은 부르는 자리에서 읽는다.
  `CD`/`CDX` 는 조건. `CDX` 상수 비교는 `(x & m) ∈ [0, m]` 으로 늘 참·거짓을 접고(eudplib 부정이 넘치지 않게), 값이 변수면 amount 칸을 채운다. 마스크는 정수 상수만(마스크 조건·마스크 SetTo 는 확실한 동작, S8 3절).
- epScript(번역 실측): const `Cell` 에 `c -= 1;`·`c = 1;` 은 번역 오류(`Undefined variable c_1`), `var y = c;` 는 빌드 오류(메시지에 `Cell` repr 안내 "c.read() / epScript c.v … const" 가 보인다)
  → `c.v -= 1;`·`c.v = 1;`·`var y = c.v;`. `c < x` 는 `EUDIf()(c >= x, neg=True)` 로 번역된다(부정은 분기라 맞다). `if (c)` = `c ≠ 0`.
  `arr[i] = v; arr[i] += v; arr[i] -= v; if (arr[i] == v)` → `_ARRW`/`_ARRC` → 위 메서드, `var y = arr[i];` → 읽기. `cell.cd(…)` → `cell.f_cd(…)`, `cell.CD(…)`·`cell.Cell(…)` 은 그대로.

**비용** (2026-09-17, `docs/COSTS.md` "cell (WP2)", 호출 자리 / 실행): 만들기 0 / 0(4바이트) · 상수 대입·덧셈·wrap·포화 1 / 1 · 변수 대입·덧셈·포화 1 / 2 · 변수 wrap 3 / 5 ·
읽기 호출 1~2 / 실행 약 36 · 비교는 cmp 와 같음(상수 0, `!= k` 2 / 2, 변수 1 / 2, `!=` 변수 2 / 3) · `DoActions(SetCD(c, 변수))` 채우기 1 ·
배열 변수 색인: 쓰기 값 상수 2 / 3·값 변수 1 / 3, wrap 값 변수 3 / 7(eudplib 마스크 반전 3 / 6), 읽기 약 37, 비교 준비 1 / 2(값 변수 1 / 3, `!=` 2 / 3~4) · `PCell` `CurrentPlayer` +1 / +7. 3.8 목표 초과 없음.

**시험**: `tests/t_cell.py` 50,916 판정 — 쓰기 21 형태(연산자·메서드·epScript 통로·CtrigAsm 액션) × 값 종류(정수 8·주소식 3·변수·EUDLightVariable·Cell·같은 칸) 경계값·무작위 차등,
읽기·생성(정수·주소식·변수·칸 초기값, `Cell.at`, `CreateCcodes`, 만들기 트리거 0), 조건 20 형태 × 값 종류 × 문맥(EUDIf, neg, EUDNot, RawTrigger, EUDSCAnd/EUDSCOr ± neg, 목록, EUDTernary ± neg, EUDElseIf),
뒤집힌 피연산자(`5 < c`), CDX(마스크 3 × 비교 3 × 값 7~8 + 변수)·SetCDX(값·마스크 상수/변수), CellArray 쓰기 10 형태 × (변수·상수 색인) × 값 종류(색인 변수 자신 포함)·읽기 4·비교 6 × 값 종류 × 문맥,
파이썬 `arr[i] += v`, PCell 8 연산 × 색인 4 종(+12칸, CP 복구·캐시 일치), `players.PerPlayer(Cell)`, Flag, `EUDLightVariable -=` 포화 대 `Cell -=` wrap 대 `SubtractNumber` 포화,
빌드 오류 50건(harness `expect_build_error`), epScript 예제 9 함수 차등 + `selftest` 18/18 + 인게임 맵 흐름 30 사이클(24 사이클째 한 번), 번역 문자열 19개, 안 되는 모양 3개,
euddraft 0.11 빌드, docstring 3.12 항목·비공개 eudplib 이름 없음 검사.

**위험**: 변수 색인 조건(플레이어 칸 채우기)·자기 칸 깃발·amount 채우기가 SC:R 에서 에뮬레이터 가정대로인지 — 인게임 권장 항목 C2-1(`examples/cell_example.eds` "점검 18 / 18").
파이썬 `arr[i] << v`(변수 i)는 읽은 사본에 쓴다(eudplib `EUDArray` 와 같음) — 문서화. 파이썬 `arr[i] += v`(변수 i)는 읽고-쓰기라 맞지만 비싸고, 값이 칸(Cell)이면 eudplib `EUDVariable += Cell` 이 되어 빌드 오류.

**초안과 달라진 점**
1. `CD` 인자 순서를 CtrigAsm 원본 `CD(Code, Value=1, Type=Exactly)` 로 했다(초안 예 `CD(c, AtLeast, 3)` 는 원본과 순서가 다르다). 초안 모양도 받는다(비교·수정자 상수는 형식으로 구분된다).
   `SetCD` 도 원본 `SetCD(Code, Value=1)` + 초안 `SetCD(c, SetTo, v)`. → 7절 D22 확인 요청.
2. 모듈 함수 이름 `f_cd`, `f_cdx`, `f_set_cd`, `f_set_cdx`, `f_add_cd`, `f_subtract_cd` 를 더했다(3.1). `SubCD` 의 모듈 함수를 `f_sub_cd` 로 하면 3.5 이름 규칙(`sub` = wrap)과 충돌해 `f_subtract_cd` 로 했다.
   LibraryFor322 의 `CDX`/`SetCDX` 도 옮겼다(마스크 조건·마스크 SetTo 만 — 마스크 Add/Subtract 는 A-1 전이라 두지 않음).
3. `Flag` 는 `EUDLightBool` 하위 클래스(초기값 검사·repr). 동작은 같다.
4. `PCell` 은 `players.PerPlayer(Cell)` 대신 `CellArray`(EUDArray) 기반 — 변수 색인 비용 EUDSwitch 15 → 1~2, `CurrentPlayer` 색인 지원.
5. `CellArray[변수]` 는 **읽은 값**(새 EUDVariable)을 돌려준다(eudplib `EUDArray` 와 같게 — epScript `var y = arr[i];` 가 되도록). `PerPlayer[변수]` 는 오류인 것과 다르다 → 7절 D23.
   초안의 "변수 색인 → 읽기·쓰기 함수" 는 `get/set/iadditem/isubitem/isub_sat/…item` 으로 준다.
6. `AtLeast/AtMost/Exactly` 를 덮어써 상수까지 `cmp` 로 보낸다(eudplib `EUDNot(AtMost 0xFFFFFFFF)` 버그).
7. 더한 것: `Cell.at(주소)`, `c.assign/iadd/isub`, `c.v` 와 `…attr` 통로, `CreateCcode(init)`/`CreateCcodes(n, init)`, `CellArray(초기값 목록)`, 파이썬 `if c:` 오류.

---

### 4.4 `i64` — 64비트 정수 — **WP3 완료(1차)·WP4 완료(2차)**

**근거**: 4맵 2,658회(R1). 시제품(`docs/proto/i64_proto.py`, 400건). 알고리즘 S8 6절(뺄셈), DPS 이식판(a7aad90)
`war.py` `_add64_inline`·`_inplace64`·`_subsat64_inline`, `tlib.py:204~` 비교 계획, `text.py:381` `_lidec_ops`.
2차: R1 사용량 `f_LMul` 59(+`_LMul` 93), `f_LDiv` 33(+`_LDiv` 37), `f_LMod` 9(+5), `f_LXor` 7(+2), `f_LRand` 5(+1), `f_LOr` 2(+1)
(부호 있는 곱·나눗셈, `f_LAnd/LNot/LlShift/LAbs` 는 0회). 이식판 a7aad90 `war.py:305~420`(`_mul3232`·`_mul64`·`_div6432`·
`_div64big`·`_divmod64` — 0 / 32비트 제수 / 64비트 제수 3경로), `war.py:483~642`(`_cdiv` — a41d2ed 에서 다시 짠 상수 제수
나눗셈, 결정 나무), `divide.py`(변수 제수 표 재사용), `arith.py:275`(`_mul_small`), `eud/DESIGN.md` 5.1 4차 기록(opt-wasub),
`eud/tests/t_war.py` 기대값. CtrigAsm v5.5 `f_LiDiv`/`f_LiMod` 본문(v5.5.lua:91309~91743·92306~92447 — 0 방향 자르기와
0 나눗셈 규칙), eudplib 0.81 `core/calcf/muldiv.py`(`_eud_mul`·`_eud_div` 자기 수정 기법)·`eudlib/mathf/div.py`(부호 나눗셈).
(받아 둔 이식판 사본은 HEAD e7efff2 — 옮긴 부분·`divide.py`·`t_war.py` 는 a7aad90 과 같다.)

**실제로 쓰인 모양**(R1 2-a): 10진 문자열 상수, 32비트 값을 올리기(`{V,0}`), 결과를 `{V,V}` 로 받기, 식 중첩, 부호 있는 64비트 비교.
2차: `f_LMul(W,W,"10000000000000000")` 17(상수 곱이 가장 흔함), `(W,W,{WA,0})` 9(32비트 곱하는 수), `(W,{V,0},"500")`,
`f_LDiv(W,WA,"10")`(상수 제수), `f_LDiv(WA,"0xFFFF…",WA)`(넘침 검사 — 변수 제수), 128비트 흐름의 64×64 조각.

**API** (모듈 함수는 `f_이름` + 파이썬 별칭)

```python
from eudext import i64
from eudext.i64 import Int64, Int64Array, parse

x = Int64(12_800_000_000)          # 초기값만 (트리거 0). Int64("12,800,000,000") 도 된다
y = Int64(v32)                     # 실행 시 대입: lo ← v32, hi ← 0 (EUDLightVariable 은 읽어서)
z = Int64(lo, hi)                  # 실행 시 대입 (각 반쪽 32비트 상수·변수)
w = Int64.wrap(lo_var, hi_var)     # 복사 없이 감싸기 (= i64.wrap)
k = parse("12800000000")           # 문자열 상수 → int (쉼표·밑줄·0x·음수 = 2의 보수)

x << y; x.assign(y); x.v = y       # 대입 (epScript 식 `x << 3` 은 빌드 오류로 막음)
x += y; x.iadd(y); x.v += y        # 덧셈 (wrap). x += x 도 된다
x -= y; x.isub(y); x.v -= y        # **wrap** 뺄셈 (x -= x 는 0 으로 접음). isub(y, inline=False) = 공유 함수
x.isub_sat(y)                      # **포화** 뺄셈, 64비트 전체 기준 (= CtrigAsm f_LSub). 변수끼리 기본 = 공유 함수, inline=True 선택
x.isubtractattr("v", y)            # 포화 별칭 (eudplib 이름 관례)
x.ineg(); x.neg(); -x              # 부호 반전 (wrap)
x + y; x - y; 5 - x                # 새 Int64 (상수끼리는 파이썬 int)
i64.add(a, b); i64.sub(a, b, inline=True); i64.sub_sat(a, b, inline=False); i64.neg(a)   # 새 값
i64.iadd(x, b); i64.isub(x, b); i64.isub_sat(x, b)                                      # 제자리 (x 는 Int64)
i64.LAdd(d, a, b); i64.LiSub(d, a, b); i64.LSub(d, a, b); i64.LNeg(d, a)  # CtrigAsm 별칭 (PlayerID 없음, d 가 a·b 와 같아도 됨)
x >= y; x <= y; x == y; x > y; x < y; x != y # 부호 없는 사전식 비교 → 조건 (i64.ge(a, b) … 도 같음)
x.sge(y); i64.sge(a, b) …                    # 부호 있는 비교 (sge/sle/sgt/slt)
x.lo, x.hi                                   # 반쪽 EUDVariable
x.fmt(); x.fmt(signed=True); i64.fmt(x)      # 10진 출력 (ptr2s — 호출 자리 버퍼 24B, 상수는 문자열)
i64.lidec_to(dst_epd, lo, hi, signed=False)  # 20자리 10진을 dst 5칸에 쓰고 앞자리 수를 돌려줌 (numfmt 가 쓰는 경계)

# --- 2차 (WP4) ---
x * y; 3 * x; x *= y; x.imul(y); x.v *= y     # 곱셈 (64비트 wrap — 부호 없음·있음 결과 같음)
i64.mul(a, b); i64.mul32(v, w); i64.imul(x, b)  # mul32 = 32비트 × 32비트 → 64비트
x // y; x % y; divmod(x, y); x //= y; x %= y  # 부호 없는 나눗셈 (0 나눗셈 = 몫 2^64−1, 나머지 = 피제수)
x.idiv(y); x.imod(y); x.v /= y; x.v %= y      # epScript `/` 는 `//` 로 번역된다. 파이썬 `x / y` 는 오류
i64.div(a, b); i64.mod(a, b); i64.divmod(a, b); i64.idiv(x, b); i64.imod(x, b)
i64.sdiv(a, b, div0="eudplib"); i64.smod(a, b, div0=…); i64.sdivmod(a, b, div0=…)   # 부호 있음, 0 방향 자르기
x.sdiv(y); x.smod(y)                          # div0 = "eudplib"(기본) | "ctrig"
x & y; x | y; x ^ y; ~x; x.invert()           # 비트 연산 (새 값). 32비트 변수는 0 확장
x &= y; x |= y; x ^= y; x.iand(y); x.ior(y); x.ixor(y); x.iinvert(); x.v &= y …
i64.bitand(a, b); i64.bitor(a, b); i64.bitxor(a, b); i64.bitnot(a); i64.iand(x, b) …
x.shl(n); x.shr(n); x >> n                    # 논리 시프트 (새 값), n = 0 이상 정수 또는 32비트 변수, n ≥ 64 → 0
x <<= n; x >>= n; x.ishl(n); x.ishr(n); x.v <<= n; x.v >>= n   # 제자리 (`<<` 는 여전히 대입)
i64.shl(a, n); i64.shr(a, n); i64.ishl(x, n); i64.ishr(x, n)
x.to32(saturate=True, signed=False); i64.to32(a, …)   # → EUDVariable (포화: 부호 없음 min, 부호 있음 [−2^31, 2^31−1])
x.abs(); x.iabs(); i64.abs(a); i64.iabs(x)            # |x| (부호 있는 64비트로 읽음, |−2^63| = 2^63)
i64.rand()                                             # 64비트 난수 (eudplib f_dwrand 두 번)
i64.LMul/LiMul/LDiv/LMod/LiDiv/LiMod/LAnd/LOr/LXor(d, a, b); i64.LNot(d, a); i64.LAbs(d, a); i64.LRand(d)  # CtrigAsm 별칭
# (파이썬 별칭 i64.divmod·i64.abs 는 내장 이름과 겹쳐 __all__ 에서 뺐다 — f_divmod·f_abs 는 있다)

arr = Int64Array(1700)             # lo EUDArray + hi EUDArray (원소 8B). Int64Array([1, "12800000000", -1]) 도 된다
arr[i] = v; arr[i] += v; arr[i] -= v          # epScript 는 iadditem/isubitem(wrap)
arr.isub_sat(i, v); arr.isubtractitem(i, v)   # 포화
arr[i] >= v …                                 # epScript _ARRC → geitem …; 부호 있는 비교는 i64.sge(arr[i], v)
e = arr[i]                                    # 새 Int64 **사본** (메서드·.v 로 제자리 연산하면 오류)
arr.lo, arr.hi, arr.epd_lo, arr.epd_hi, len(arr)
arr[i] *= v; arr[i] /= v; arr[i] %= v; arr[i] &= v; arr[i] |= v; arr[i] ^= v; arr[i] <<= n; arr[i] >>= n  # 2차
arr.imul/idiv/imod/iand/ior/ixor/ishl/ishr(i, v)   # (= imulitem/ifloordivitem/imoditem/ianditem/ioritem/ixoritem/ilshiftitem/irshiftitem)

# 3단계: i64.ssub_sat (부호 있는 포화), x ** n (지금은 안내 오류)
```

**의미**
- `+ - 단항-` wrap, 비교 연산자는 **사전식**(hi 먼저) 부호 없음. CtrigAsm 의 "반쪽별 AND"(NWar) 비교는 제공하지 않는다.
- **뺄셈 두 의미**(3.5): 연산자·`isub`·`sub`·`neg`·`isubitem`·`f_LiSub`·`f_LNeg` = wrap, `isub_sat`·`sub_sat`·`isubtractitem`·
  `isubtractattr`·`f_LSub` = 포화(64비트 전체 기준). 반쪽별 포화(`SetNWar(Subtract)`)와 `Int64.SubtractNumber`/`AddNumber` 는 없다.
  같은 객체끼리 `x -= x`·`sub_sat(x, x)`·`LSub(x, x, x)` 는 0 으로 접는다. 반쪽이 엇갈려 겹치는 경우(`x -= Int64.wrap(x.hi, x.lo)`,
  `LSub(d, a, d)`)는 임시 변수를 거친다.
- 32비트 변수 피연산자는 **0 확장**(hi = 0) — 부호 있는 비교·나눗셈에서도 음수 32비트로 읽지 않는다(음수는 Int64 로 올려 넣는다).
- 32비트 변수가 **왼쪽**인 비교(`v >= x`)·산술(`v + x`, `v * x`, `v // x`, `v % x`, `v >> x`)은 eudplib `EUDVariable` 연산자가 먼저
  불린다 → `i64.ge(v, x)`, `i64.mul(v, x)` … 로 쓴다. 곱셈·나눗셈·시프트는 eudplib 이 Int64 를 상수처럼 다뤄(`_const_mul` 의
  `number &= 0xFFFFFFFF` 가 Int64 를 **제자리에서 바꾼다**) 조용히 틀리므로, Int64 가 그 호출 경로(`_compat.eudplib_calc_caller`)를
  보고 안내 오류를 낸다. (`5 < x`, `3 * x` 처럼 정수가 왼쪽이면 파이썬이 Int64 쪽 연산자를 불러 맞게 된다.)
- 비교는 **새 Condition 또는 조건 목록(AND)**. 앞 계산은 부르는 순간 낸다(cmp 와 같은 규칙 — 꼭 한 번 트리거에 놓고, 루프 조건은
  조건 자리에서 부른다). 상수끼리·같은 객체끼리는 `Always()`/`Never()`.
- 편차 덧셈(`f_LMov` Deviation)은 제공하지 않는다(호환 전용).
- 배열 원소 사본: `arr[i]` 는 읽은 사본이다. 사본에 `iadd()`·`isub()`·`isub_sat()`·`imul()`·`idiv()`·`iand()`·`ishl()`…·`<<`·
  `.v = / += / -= / *= / <<= …`·`ineg()`·`iinvert()`·`iabs()` 를 하면 배열에 쓰이지 않으므로 **EudextError**(epScript `arr[i].v += 1;` 함정).
  파이썬 연산자 `arr[i] += v`·`arr[i] *= v` 는 파이썬이 되쓰므로 허용(읽고-쓰기라 비쌈 → `arr.iadd(i, v)`). 사본이 필요하면 `Int64(arr[i])`.
- **곱셈**: `(a × b) mod 2^64`. 부호 없음·있음 결과가 같다(`LiMul` = `LMul`).
- **부호 없는 나눗셈**: 0 나눗셈은 몫 2^64 − 1, 나머지 = 피제수(war.py·CtrigAsm `f_LDiv`/`f_LMod`·eudplib `f_div` 와 같음 — 7절 D4).
- **부호 있는 나눗셈** `sdiv/smod/sdivmod`: 0 방향으로 자른다(C·JavaScript·CtrigAsm `f_LiDiv`), 나머지 부호 = 피제수 부호(`a = q·b + r`).
  −2^63 ÷ −1 = 2^63(wrap — 곧 −2^63, CtrigAsm 과 같음). 0 나눗셈: 나머지는 늘 피제수, 몫은 `div0=` 로 고른다 —
  `"eudplib"`(기본): 부호 없는 결과(2^64 − 1)에 같은 부호 규칙을 붙인 값 = 피제수 < 0 이면 1, 아니면 −1(eudplib 0.81
  `f_div_towards_zero` 의 32비트 동작과 같음). `"ctrig"`: CtrigAsm `f_LiDiv` — 피제수 < 0 이면 −2^63, 아니면 2^63 − 1.
  CtrigAsm 별칭 `LiDiv`/`LiMod` 는 `"ctrig"`. (7절 D59)
- **비트**: `& | ^ ~` 반쪽마다. 32비트 변수는 0 확장이라 `~v32` 의 상위는 0xFFFFFFFF.
- **시프트**: 논리 시프트, n 은 부호 없는 32비트로 읽고 **n ≥ 64 → 0**. 음수 정수·Int64·실수는 오류. `<<` 는 대입 그대로이고
  `<<=`·`>>=`·`>>` 는 시프트다(eudplib `EUDVariable` 과 같음 — 7절 D60). CtrigAsm `f_LlShift` 는 시프트 양의 하위 6비트가 0 이면
  시프트하지 않는 것으로 읽혀(v5.5.lua:72666 `CtrigX(CRet, Exactly, 0, 0x3F)` — n = 64 → 그대로) 별칭을 두지 않았다(D61).
- **to32**: `saturate=True`(기본) 부호 없음 = min(x, 2^32 − 1), `signed=True` = [−2^31, 2^31 − 1] 로 자른 32비트 2의 보수,
  `saturate=False` = 하위 반쪽. 새 EUDVariable(상수면 int).
- **abs**: 부호 있는 64비트로 읽은 절댓값, |−2^63| = 2^63.
- **rand**: eudplib `f_dwrand()` 두 번(하위·상위, 공유 시드 — 모든 클라이언트가 같은 값). CtrigAsm `f_LRand`(시드 스위치 64번)와
  값은 다르다(G3 1.10 이 허용).
- 파이썬 `x / y` 는 오류(정수 나눗셈만), `x ** n` 은 오류. `x.shl(n)` 의 n 이 Int64 면 오류(`x.lo` 를 넘긴다).

**알고리즘**
- 대입: SeqCompute 한 줄(반쪽이 엇갈리면 순서를 맞추거나 임시 변수).
- 덧셈(인라인): `x.lo += y.lo`, `x.hi += y.hi`, 올림 조건 amount ← 새 lo + 1 을 한 줄에, 올림 = `[y.lo ≥ 채움] ∧ [채움 ≥ 1]` 트리거 1.
  상수 = 더하기 트리거 + `[새 lo ≤ kl−1] → hi += 1`. `x += x` = hi 두 배 → 옛 lo 최상위 비트 올림 → lo 두 배.
- wrap 뺄셈(인라인 기본): `x.lo += ~y.lo + 1`, `x.hi += ~y.hi + 1`(~ = 0xFFFFFFFF ⊖, 포화하지 않음)을 한 줄에 하고
  **빌림 ⇔ 새 lo > ~y.lo** 를 `[~y.lo ≤ 새 lo − 1] ∧ [새 lo ≥ 1]` 로 판정 → hi −= 1. S8 WVb(6 / 12)보다 적다(2 / 7).
  상수 = `x += (−K mod 2^64)`(S8 WK 와 같은 2 / 2). `inline=False` = 같은 본문의 공유 EUDFunc(본문 4, 호출 1 / 실행 18).
  인라인과 공유 함수의 호출 자리 바이트가 거의 같아(1,384B / 1,358B) 인라인을 기본으로 했다.
- 포화 뺄셈: 상수 = S8 **SK**(분기 없음, 2~4). 변수 = 한 줄[amt2 ← 옛 hi + 1, hi ⊖= y.hi(포화), n ← ~y.lo, lo += n + 1,
  amt1 ← 새 lo − 1] + T_a[빌림: n ≤ amt1 ∧ 새 lo ≥ 1 → hi −= 1(wrap), amt2 −= 1(wrap), 막이 조건 G 를 Always 로] +
  T_c[y.hi ≥ amt2 ∧ G → x ← 0]. G = `[amt2 ≥ 1]`(옛 hi = 0xFFFFFFFF 일 때 amt2 가 0 으로 도는 것을 막음)이고 준비 트리거가 매번
  조건 +12 칸을 Memory·AtLeast 로 되살린다. 빌림이면 "hi 가 작거나 같음"이 곧 0 이 되는 조건이 되고, 그때 hi(포화 0)는 wrap −1 로
  0xFFFFFFFF 가 되지만 T_c 가 0 으로 만든다. 변수끼리 **기본은 이 본문의 공유 EUDFunc**(본문 5, 호출 1 / 실행 19),
  `inline=True` 는 호출 3 / 실행 8(호출 자리 약 +1KB). S8 SVa(7 / 14)·SVf(9 / 25)·war.py `_subsat64`(27 / 51)보다 적다.
  2,076쌍 모형 검사와 에뮬레이터 차등으로 확인.
- 부호 반전: 제자리 = `x ← ~x`(한 줄) → `[lo = 0xFFFFFFFF] → hi += 1` → `lo += 1`(3 / 7). 새 값 = `0 − x`(wrap 뺄셈 3인자, 2 / 7).
- 비교(DPS a7aad90 비교 계획): `x ≥ y = [xh ≥ yh] ∧ ¬([xh ≤ yh] ∧ [xl < yl])`, `x > y` 는 끝을 `[xl ≤ yl]` 로.
  원자(상수 비교·변수 비교·`gt`)를 구간으로 합치고, 부정 부분이 원자 하나면 base 에 넣는다. 아니면 자기 칸 깃발
  (`_parts.flag_cond`)을 끄는 조건 트리거 하나(DPS 는 결과 조건 종류를 Never 로 바꿨다 — 같은 비용). 변수 값은 조건 amount 칸에
  채우고(`_parts.Plan`, amount 자리는 `Forward` — 3.4), 같은 변수를 두 번 원천으로 쓰지 않게 채울 방향을 고른다.
  부호 있는 비교는 hi 에 2^31 을 더한 자기 칸(`selfcond`)을 쓰고, base 아래에서 `[xh' ≤ yh'] ⇔ xh = yh` 로 부정 부분을 줄인다.
  비용: 변수끼리 2 / 5, 부호 있음 3 / 7, `==` 1 / 3, 상수 0~2 / 0~2(`x >= 2^32` 처럼 lo 가 0 이면 조건 하나·트리거 0).
- 10진 출력: 공유 본문 `_lidec_body`(반환 변수 미리 정함 — `_compat.predefine_returns`): 단마다 `c = b·10^i`(b = 8,4,2,1) 복원 뺄셈을
  서로 배타인 트리거 둘([hi ≥ ch ∧ lo ≥ cl] / 빌림 [hi ≥ ch+1 ∧ lo < cl])로, 값 < 2^32 가 보장된 단부터는 하나로(77단, 116 트리거).
  단 시작 때 값 < 2c 라 한쪽이 빼면 다른 쪽은 거짓이다. 이어서 앞자리 '0' 수 세기 19. 호출 자리는 결과 변수가 버퍼 칸에 바로 쓰게
  `ret=[EPD(buf)+k…, p]` 로 부르고 `p += buf`. 부호 있는 판 `_slidec_body` 는 음수면 절댓값으로 바꾸고 첫 숫자 앞 '0' 에 −3(→ '-').
  한 print 에 `fmt()` 가 여러 개일 수 있으므로(epScript 는 인자를 먼저 계산) 버퍼는 호출 자리마다 둔다. 상수 `fmt()` 는 문자열.
  numfmt(WP5)는 `i64.lidec_to(dst_epd, lo, hi, signed=, lead=)`(20자리 0 채움 + 앞자리 수)와 코드 생성기 `i64._lidec_code` 를 쓰면 된다.
- 배열: 칸 번호·값이 모두 상수면 원소 칸(`_Cell`)에 위 상수 알고리즘을 바로 쓴다(읽기 없음). 그 밖은 `f_dwread_epd` 두 번으로 읽고
  셈하고 다시 쓴다(변수 칸 `arr[i] += y` 8 / 87). 칸 번호를 조건·액션의 EPD 칸에 채우는 방식은 다음 과제(D26).
  2차 원소 연산도 같다: 상수 칸 & | 상수 값만 칸에 마스크 SetTo(1 / 1), 나머지는 읽고-셈-쓰기(`arr[i] *= y` 7 / 365).
- **2차 공통 틀** (`_parts.SelfFrame`·`var_chain`·결정 나무 `DNode`/`dtree`/`emit_dtree` — 이식판 a7aad90 `war.py:493` `_Node` 를 일반화):
  단계마다 조건 트리거 하나(방문 1)가, 참이면 액션으로 자기 next 를 **변수 트리거 사슬**(원천마다 목적지·next 를 준비 액션으로 정해
  두고 잇는 것 — eudplib VProc·SeqCompute 와 같은 방식)의 첫 트리거로 바꾼다. 바뀐 next 는 본문 끝의 되돌림 묶음이 매 호출
  첫머리에 거짓 쪽으로 되돌린다(첫 트리거가 되돌림 묶음으로 뛰었다가 돌아온다). 공유 트리거의 돌아갈 곳·몫 액션의 칸과 값은
  단계 준비 트리거가 액션으로 고친다. 쓰는 기법은 eudplib 이 스스로 쓰는 것(`_eud_mul`·`_eud_div` 의 SetNextPtr 자기 수정,
  조건 amount·액션 값 칸 채우기)뿐이라 인게임 새 가정이 없다.
- **곱셈(변수)** — 16비트 쪼개기(G3 1.10 제안): a = (al, ah), al = a0 + a1·2^16, b = (bl, bh), bh = c0 + c1·2^16.
  `al·bl = a0·b0 + (a1·b0 + a0·b1)·2^16 + a1·b1·2^32`, `(ah·bl + al·bh)·2^32` 은 하위 32비트만 필요하다.
  al 을 조각내고(상위 16비트를 비트마다 옮김, al < 2^16 이면 건너뜀) 16단을 돈다. 단 i 에서 t0 = a0·2^i, t1 = a1·2^i 는
  2^32 를 넘지 않고 h0 = ah·2^i 는 wrap 이다:
  `[bl 비트 i] → rl += t0, m0 += t1, rh += h0` · `[bl 비트 16+i] → m1 += t0, rh += t1, z += h0` ·
  `[bh 비트 i] → rh += t0, z += t1` · `[bh 비트 16+i] → z += t0` · `[남은 비트 있음] → t0, t1, h0 두 배`(없으면 끝으로).
  누적기 rl = a0·b0, m0 = a1·b0, m1 = a0·b1 은 2^32 미만이라 넘치지 않고, rh(가중치 2^32)·z(2^48, 하위 16비트만 쓰임)는 wrap 이
  맞다. 끝에서 m0 += m1(올림 → rh += 2^16), m0 의 상위 16비트 → rh(비트마다), 하위 16비트 << 16 → L(비트마다, 올림 판정 칸도
  같이 더함), rl += L(올림 → rh += 1), z 의 하위 16비트 << 16 → rh. hi 가 상수 0 인 쪽(32비트 변수)은 곱하는 수로 돌려
  bh 단을 빼고(64×32 본문), 둘 다면 h0·z 도 뺀다(32×32 본문). 본문 171 / 123 / 106, 실행 최악 355 / 273 / 209.
  war.py `_mul64`(32단 비트 루프 + f_mul 두 번, 단마다 올림 처리)는 실행 2,268~4,626(초기 계측) — 여기서는 누적기가 넘치지 않게
  나눠 단마다 조건 트리거 + 사슬만 돈다.
- **곱셈(상수 K)** — K 마다 공유 본문. 두 방법의 최악 실행을 컴파일 시점에 어림해 싼 쪽을 고른다.
  ① 비트 누적(이식판 128비트 곱셈 "파이썬화"처럼 부분곱을 컴파일 시점에 계산): 곱해지는 수 x 의 비트 i 마다 조건 트리거 하나가
  상수 T_i = K·2^i mod 2^64 의 조각을 더한다 — rl += (T_i 하위 32비트의 하위 27비트), F += (하위 32비트 >> 27), rh += (상위 32비트).
  하위 조각은 x 의 하위 32비트에서만 생기므로 rl < 32·2^27 = 2^32, F < 2^10 로 넘치지 않는다. 끝에서 F·2^27 을 rl(올림)·rh 로 옮긴다
  (비트 10개). 16비트 조각이 0 이면 그 조각의 비트 트리거 16개를 건너뛴다. K 와 거의 무관하게 실행 최악 약 90(64비트 x)·55(32비트 x).
  ② 배가·덧셈(이식판 `arith.py:275` `_mul_small` 을 64비트로): K = K'·2^s, K' 의 이진·NAF 자릿수 중 싼 쪽으로 `r = 2r ± x`,
  끝에 `<< s`. 64비트 두 배는 실행 4(준비 → xh 변수 → [옛 xl 최상위 비트] xh += 1 → xl 변수). ×10 은 실행 29.
  K = 0·1·−1 은 인라인(대입·부호 반전), 2^s 는 시프트.
- **나눗셈(변수 제수)** — 이식판 `_divmod64` 3경로(제수 0 / 32비트 제수 / 64비트 제수)를 한 공유 본문(반환 변수 미리 정함)에 두고,
  한 단을 **공유 비교 트리거**로 줄였다(제수는 비교 조건 amount 칸에 호출마다 한 번만 채운다).
  · 32비트 제수 d: 나머지 r(< d)에 피제수 비트를 하나씩 밀어 넣는다(64단 — nh 의 32비트, nl 의 32비트).
    한 단 = 준비(공유 R·CMP·ND 의 next 와 CMP 몫 액션의 칸·값을 이 단으로) → R(r += r) → S0([비트] r += 1) → CMP([r ≥ d] 몫 += 비트,
    next → ND) → ND(r += −d) → 다음 단. 실행 4~5(war.py `_div6432` 단당 약 11). d ≤ 2^31 이면 2r + 1 < 2^32 라 넘치지 않는다(경로 A).
    d > 2^31 이면(경로 B) 상위 몫은 nh ≥ d 면 1(nh < 2^32 < 2d)이고, 하위 32단 앞에 [옛 r ≥ 2^31](넘침 = 반드시 뺌) 트리거를 둔다.
    nh < d 면 32단째부터 r = nh 로, 아니면 r = 0 에서 시작하고, r = 0 인 단어는 결정 나무(깊이 5)로 최상위 비트 단계에 들어간다.
  · 64비트 제수 D(dh ≥ 1): n < D 면 몫 0(64비트 비교 계획 조건 하나로 판정). dh ≥ 2^31 이면 몫 1, 나머지 n − D(n < 2^64 ≤ 2D).
    그 밖(D < 2^63)은 몫 < 2^32 라 R = (0, nh) 에서 nl 의 32비트를 밀어 넣는 32단: 준비 → RH(rh += rh) → TC([옛 rl ≥ 2^31] rh += 1)
    → RL(rl += rl) → S0 → K0([rh ≤ dh − 1] → 다음 단) → K1([rh ≥ dh + 1][rl ≥ dl] → VA(rl += −dl)·VB(rh += −dh))
    → K2([rh ≥ dh + 1][rl ≤ dl − 1] → VA·VC(rh += −dh − 1, 빌림)) → K3([rl ≥ dl] → VA·VB) → 다음 단. 실행 6~11
    (war.py `_div64big` 단당 약 16). 조건 칸 6개와 −dl·−dh·−dh−1 은 호출마다 한 번 채운다.
  본문 389 트리거, 실행 최악 391(목표 ≤ 711). 32비트끼리도 이 본문(최악 191 — eudplib `f_div` 는 제수 두 배수 표를 매번 만들어
  최악 266이라 쓰지 않았다. 이식판 `divide.py` 의 "같은 제수면 표 재사용"은 32비트 전용이라 옮기지 않았다).
- **나눗셈(상수 제수 K < 2^32)** — 이식판 `_cdiv`(a41d2ed)를 옮겼다: 두 칸 수를 위 칸부터, 칸마다 값 (r·2^32 + x) ÷ K 를 복원 나눗셈
  단 j = 31…0 으로(한 단 = 서로 배타인 트리거 둘 — 빌림 T2 / 빌림 없음 T1, K·2^j < 2^32 인 단 아래는 T1 만). 들어갈 단은
  결정 나무로 고른다(r = 0 이면 x 로 — 참 쪽으로 닿은 잎은 그 단의 뺄셈을 갈림 트리거가 바로 한다, r ≥ 1 이면 r 로).
  몫만 / 나머지만 / 둘 다 본문을 따로 두고(몫 변수·나머지 칸이 곧 반환 변수), 나머지만이면 몫을 셈하지 않는다.
  이식판의 `fn._frets`·`_fend` 직접 접근은 `_compat.predefine_returns` 와 본문 끝 라벨로 바꿨다. 실행 12~81(`x % 10000` 은 이식판에서
  171 → 74 로 줄인 항목), 본문 약 120.
  **K ≥ 2^32**: 같은 배타 트리거 단(64비트 값 ≥ K·2^j)을 K·2^j < 2^64 인 단부터 돌고, 들어갈 단은 hi 반쪽으로 결정 나무. 몫 < 2^32. 실행 18~83.
  K = 0·1 은 인라인, 2^s 는 몫 = 시프트·나머지 = 마스크 SetTo.
- **부호 있는 나눗셈**: 공유 본문(div0 마다) — 피제수·제수가 음수면 부호 반전(깃발), 부호 없는 나눗셈 본문을 부르고, 몫은 두 부호가
  다르면, 나머지는 피제수가 음수면 부호 반전. div0="ctrig" 는 제수 0 일 때 몫을 덮어쓴다. 상수 제수는 |K| 로 상수 나눗셈 본문을 부르는
  제수별 본문. 실행 37~368.
- **비트**: `a & b` = d ← a, 마스크 칸 ← ~b(0xFFFFFFFF ⊖ b), `d.SetNumberX(0, 마스크)` / `a | b` = 마스크 칸 ← b,
  `d.SetNumberX(0xFFFFFFFF, 마스크)` (eudplib 0.81 `EUDVariable.__and__`/`__or__` 와 같은 마스크 칸 채우기, 두 반쪽을 한 줄에) /
  `a ^ b` = (a | b) ⊖ (a & b) — 뒤가 앞의 부분집합이라 SC Subtract 가 정확하다(eudplib `__xor__` 의 마스크 Add 식은 인게임 확인 전 —
  S8 A-1 — 이라 쓰지 않음) / `~a` = 0xFFFFFFFF ⊖ a. 상수는 마스크 SetTo 1액션. 모두 인라인(xor 변수끼리 호출 7 트리거 — 호출 자리 바이트
  3.2KB 가 공유 함수 호출 3.4KB 와 비슷해 3.3 에 따라 인라인).
- **시프트(상수 n)**: 왼쪽은 64비트 두 배 n 번(실행 4n)과 제자리 비트 옮기기(실행 65 − n — 조건 트리거가 비트를 마스크 SetTo 로 지우고
  새 자리(이미 빔)에 Add) 중 싼 쪽, n ≥ 32 는 칸 옮기기 + 32비트. 오른쪽은 비트 옮기기(오름차순)와 96비트 창 (w2, xh, xl) 을
  (32 − n)번 두 배 하고 (w2, xh) 를 읽는 방법(실행 6(32 − n) + 4 — n ≥ 27 에서 쌈) 중 싼 쪽. n = 1(왼쪽)·n = 32 는 인라인,
  그 밖은 n 마다 공유 본문.
- **시프트(변수 n)**: 공유 본문 — n ≥ 64 → 0, n ≥ 32 → 칸 옮기고 n −= 32, 남은 m(1~31)은 결정 나무(깊이 5)로 두 배 단계에 들어가
  m 번(왼쪽, 실행 4씩) 또는 (32 − m)번(오른쪽 96비트 창, 실행 6씩) 돈다. 단계 트리거는 xl 변수 트리거의 next 만 고치고, xh·TM 의
  next 는 호출 첫머리에 정한다. 실행 최악 147 / 208.
- to32 는 인라인(부호 없음 트리거 2, 부호 있음 5 — 서로 배타인 넘침 규칙 4개, 상수 반쪽은 컴파일 시점에 접음), abs 는 공유 본문
  (`[hi ≥ 2^31] → 부호 반전`), rand 는 `f_dwrand` 두 번(반환 변수를 `makeL()` 로 좌값으로).
- 32비트 변수 곱·나눗셈에 eudplib `f_mul`/`f_div` 를 쓰지 않았다: `f_mul` 은 하위 32비트뿐이고(실행 57~196), `f_div` 는 최악 266 으로
  새 본문(191)보다 비싸다(`docs/COSTS.md` 참고 행).

**비용** (2026-09-17, `docs/COSTS.md` "i64 (WP3)"·"i64 2차 (WP4)". 호출 / 실행, 비교는 소비 트리거 제외)
덧셈 상수 2 / 2(hi 만 1 / 1), 변수 2 / 5, 새 값 2 / 7 · wrap 뺄셈 상수 2 / 2, 변수 2 / 7(공유 함수 1 / 18, 본문 4), 새 값 2 / 9 ·
포화 상수 2~4 / 2~4, 변수 1 / 19(공유 함수 기본, 본문 5)·인라인 3 / 8, 새 값 1 / 19 · 부호 반전 3 / 7 · 대입 1 / 1~3 ·
비교 변수 2 / 5(부호 있음 3 / 7, `==` 1 / 3), 상수 0~2 / 0~2 · 10진 본문 137(부호 있음 163) / 호출 2 / 실행 146~177 ·
배열 상수 칸·상수 값 2~4, 변수 칸 읽기 4 / 76, 쓰기 2 / 6.
2차: 곱셈 변수 1 / 35~355(64×64, 본문 171)·140~273(64×32, 123)·72~209(32×32, 106), 상수 1 / 26~90(비트 누적 본문 50~85, ×10 배가·덧셈
본문 11 / 실행 29), 2^s = 시프트 · 나눗셈 변수 1 / 17~391(본문 389), 32비트 제수 160~191, 상수 1 / 12~83(본문 100~130), 2^s 1 / 64 ·
부호 나눗셈 1 / 37~368(본문 26 + 부호 없는 본문), 상수 ÷ −7 1 / 42~76 · & | 2 / 6, ^ 7 / 17(제자리 5 / 13), 상수 & | 2 / 2, 상수 ^ 3 / 7,
~ 1 / 3 · 시프트 상수 1 / 24~69(n 마다 본문 7~62), n = 1·32 인라인 2~3 / 3~7, 변수 1 / 40~147(왼쪽, 본문 72)·205~208(오른쪽, 본문 74) ·
to32 2 / 3(부호 있음 5 / 6) · abs 1 / 10~18(본문 7) · rand 2 / 194 · 배열 원소 `arr[i] *= y` 7 / 365, 상수 칸 `&= 상수` 1 / 1.
**3.8 목표를 넘은 항목 없음** — 곱셈 실행 ≤ 1,000(최악 358), 나눗셈 실행 ≤ 711(최악 391).
시제품 대비: 덧셈 실행 19 → 5, wrap 뺄셈 21 → 7, 변수 비교 22 → 5. war.py 대비: 곱셈 2,268~4,626 → ≤ 358, 나눗셈 한 단 약 11·16 → 4~5·6~11.

**시험**: `tests/t_i64.py` 307,079 판정(1차 — WP4 에서 "2차 자리" 안내 오류 판정을 "여전히 안 되는 것"(`**`, `/`, `1 << x`)으로
바꿨고 `__all__` 확인이 늘었다) — 경계값 24개(S8 방식, 2^32−1 빌림·2^63 부호·10^19 자리 경계 포함) 전 쌍 + 무작위 1,500쌍 ×
변수끼리 연산 전부(연산자·메서드·모듈 함수·CtrigAsm 별칭·`.v` 통로·인라인/공유 함수), 32비트 변수 올리기(왼쪽·오른쪽), 같은 객체끼리,
반쪽이 엇갈려 겹치는 경우, 비교 문맥 12종(EUDIf·neg·EUDNot·RawTrigger·EUDSCAnd/Or ± neg·목록·EUDTernary ± neg·EUDElseIf),
상수 24개 × (경계 24 + 근처 6 + 무작위 30) × 상수 연산(오른쪽·왼쪽, 정수·음수·10진 문자열 표기) + 문맥, EUDWhile 조건 재계산
(부호 없음·있음·상수), Int64Array(변수 칸·상수 칸 × 변수·상수 값, 초기값 목록), 생성 규칙(초기값만 / 실행 시 대입, 주소식,
EUDLightVariable), 10진 출력 바이트(부호 없음·있음·32비트·상수·두 fmt 한 줄·`lidec_to` 상수/변수 dst·부호 있음), 시제품 시험 400건
(`docs/proto/t_i64_emu.py` 를 새 API 로, 32비트 부호 비교는 `cmp.sge`), epScript 예제 함수 15종, 인게임 맵 에뮬레이션(23 / 23),
euddraft 0.11 빌드 2개, 빌드 오류여야 하는 epScript 5종(`x << 3`, `var x = Int64`, `return x >= 1`, 원소 사본 `.v +=`,
왼쪽 32비트 변수 비교) + `EUDTypedFunc([Int64])`, 파이썬 쪽 판정 327.
`tests/t_i64_ops.py` 195,805 판정(2차) — 변수끼리 1,276쌍(경계값 전 쌍 + 비트 폭을 섞은 무작위 700 — 나눗셈 경로 A/B·64비트 제수·
몫 0/1·n < d·0 나눗셈이 고루 나오게) × 곱셈 9형태·나눗셈 17형태·부호 나눗셈 12형태(div0 두 규칙)·비트 27형태, 638쌍 × abs·to32 10형태·
32비트 변수 올리기 21형태(왼쪽 `i64.mul(v, x)`·`i64.div(v, x)`, `mul32`, 32비트끼리)·같은 객체 24형태(`x * x`, `x // x`, `LDiv(x, x, x)` …)·
반쪽이 엇갈려 겹치는 경우 16형태, 상수 30개(0·1·2의 거듭제곱·−1·2^32 이상·10^16·10^19·음수·10진 문자열 표기) × 약 55값 × 24형태
(오른쪽·왼쪽 곱, 몫·나머지·divmod·상수가 피제수, 부호 나눗셈 두 규칙, & | ^ 제자리), 시프트 상수 n 28개(0~100) × 35값 × 13형태·
변수 n 74개(0~66, 100, 127, 128, 255, 2^31, 2^32−1, 2^32−64) × 17값 × 9형태(시프트 양이 자기 반쪽 포함), Int64Array 원소 연산
(변수 칸 60 × 8단계 15연산, 상수 칸 24 × 4단계), 난수(eudplib LCG 모형과 20회), 이식판 `t_war.py` 기대값(곱셈 12·변수 나눗셈 34·
B4~B9·C1~C3·C8~C9·상수 제수 7×6×3 — t_war 의 덧셈·뺄셈·대입 항목은 1차 몫), epScript 예제 21함수 차등, 번역 문자열 29개,
인게임 맵 에뮬레이션(56 / 56), euddraft 0.11 빌드 2개, 빌드 오류여야 하는 epScript 9종(`v * hp`, `v / hp`, `v % hp`, `v >> hp`, `hp << 3`,
원소 사본 `.v *=`, `div0="c"`, `shl(-1)`, `shr(hp)`), 실행 트리거 수 목표 대조(최악 입력), 파이썬 쪽 판정 340(상수 접기·모양·오류 26종·
사본 쓰기 금지 12종·별칭·`__all__`·docstring·비공개 API·마스크 Add 안 씀).
**위험**: ① 포화 뺄셈(변수)이 조건 +12 칸(비교·종류 바이트)을 실행 중에 바꾸는 방법에 기댄다(DPS a7aad90 비교 계획과 같은 종류) —
인게임 C3-2. ② SC `Subtract` 의 부호 없는 0 멈춤 — 인게임 C3-1(S8 A-1 과 같은 사실. 2차 상수 제수 나눗셈도 "값 ≥ 빼는 값" 이 보장된
곳에서 쓴다). ③ 변수 칸 배열 연산이 비싸다(읽기 76, 원소 곱 365). ④ `_compat.eps_lshift_caller` 가 eudplib epScript 도우미 `_LSH` 이름에,
`_compat.eudplib_calc_caller` 가 eudplib `core/calcf/muldiv`·`bitwise` 모듈 이름에 기댄다(`_WP3_REQUIRED`·`_WP4_REQUIRED`).
⑤ 2차 본문은 트리거 next 자기 수정·조건 amount·액션 칸/값 채우기에 기댄다 — eudplib `_eud_mul`/`_eud_div` 와 같은 기법이라 새 가정은 아니지만
인게임 권장 D4-1(`examples/i64_ops_ingame.eds` "점검 56 / 56"). ⑥ 본문 크기: 나눗셈 공유 본문 389 트리거(한 벌), 상수 곱·상수 제수는
상수마다 본문 50~130 트리거 — 서로 다른 상수를 많이 쓰면 페이로드가 는다. ⑦ 2차 본문 안에서는 사용자 코드를 부르지 않는다(재진입 없음).
`EUDTypedFunc([Int64])` 는 안 된다(한 칸) → `cast` 에서 안내 오류, `(lo, hi)` 두 인자 + `Int64.wrap`. 128비트는 4.4b.
- "128비트는 4.4b" 문장 뒤: i128 이 i64 내부 부품(비교 계획 원자·`_halves`·`_assign`·`_iadd`·곱셈·나눗셈·상수 제수·10진 본문·`_split16`)을
  같은 패키지 안에서 쓴다(4.4b 위험 ③). 이 이름을 바꾸면 `tests/t_i128.py` 도 돌린다.

**초안과 달라진 점**
- wrap 뺄셈 변수끼리 기본을 공유 EUDFunc(WVf) 대신 **인라인**으로: 새 알고리즘이 호출 2 / 실행 7 이고 호출 자리 바이트가 함수 호출과
  같다(3.3 "모두 변수 = 공유 함수" 규칙의 예외, 7절 D25). `inline=False` 로 공유 함수를 고를 수 있다.
- 포화 뺄셈 인라인을 S8 SVa(7 / 14)에서 **3 / 8** 로(자기 수정 막이 조건). 기본은 3.3 대로 공유 함수(D24).
- 비교를 시제품의 EUDLightBool·0/1 변수 대신 **조건(목록)** 으로(3.4, cmp 와 같은 규칙).
- `x.neg()`(새 값)·`x.ineg()`(제자리)를 1차에 넣었다(wrap). `x.abs()`·`x.iabs()` 는 2차에 넣었다.
- `fmt(signed=)`, `i64.fmt`, `i64.lidec_to` 를 더했다(numfmt 경계). 시제품의 16진 fmt 는 버렸다.
- 모듈 함수 `add/sub/sub_sat/neg/iadd/isub/isub_sat/wrap/parse` 와 CtrigAsm 별칭 `LAdd/LiSub/LSub/LNeg`(3인자, PlayerID 없음)를 더했다.
- `Int64Array`: 초기값 목록, 비교 `*item`, `isubtractitem`(포화 별칭), `lo/hi/epd_lo/epd_hi`, 원소 사본 쓰기 금지 규칙을 더했다.
- 2차(WP4):
  1. **`<<=`·`>>=`·`>>` 를 시프트로** 열었다. 3.2-5 는 "시프트는 메서드로만" 이었지만, eudplib `EUDVariable` 도 `<<` 는 대입·`<<=` 는
     시프트이고, epScript `x.v <<= n;` 이 자연스럽다. `x << y`(대입)와 epScript 식 `x << 3` 막기는 그대로. → 7절 D60.
  2. 나눗셈은 이식판 3경로 구조를 유지하되 **한 단을 공유 비교 트리거로** 다시 짰다(war.py `_div6432`/`_div64big` 는 단마다 임시 변수
     비교·EUDJumpIf — 단당 약 11·16). 32비트 제수는 d ≤ 2^31(넘침 없음)과 d > 2^31(옛 r 최상위 비트 검사) 두 경로로 나눴고,
     64비트 제수 D ≥ 2^63 은 몫 0/1 로 따로 처리한다. r = 0 인 단어는 결정 나무로 앞 0 비트를 건너뛴다.
  3. 32비트 곱셈·나눗셈에 eudplib `f_mul`/`f_div` 를 쓰지 않았다(64비트 곱이 필요하고, 나눗셈은 새 본문이 싸다). 이식판 `divide.py` 의
     "마지막 제수의 표 재사용"은 32비트 전용이라 옮기지 않았다(필요하면 32비트 나눗셈 모듈 몫).
  4. 상수 곱에 **비트 누적**을 더했다(war.py 는 상수 곱도 변수 곱 본문, 이식판 `arith.py` `_mul_small` 은 32비트 작은 상수만).
     작은 상수는 `_mul_small` 을 64비트·NAF 로 넓힌 배가·덧셈. K 마다 싼 쪽.
  5. 부호 있는 나눗셈의 0 나눗셈 기본값: D4 "몫 전부 1" 을 eudplib `f_div_towards_zero` 의 실제 동작(피제수 < 0 이면 몫 1)으로 적용하고
     CtrigAsm 값은 `div0="ctrig"` 로(CtrigAsm 별칭 `LiDiv`/`LiMod` 는 이쪽). → 7절 D59.
  6. 모듈 함수 이름: 비트는 eudplib 관례 `bitand/bitor/bitxor/bitnot`(`and`/`or` 는 파이썬 예약어). 초안의 `i64.abs`·`i64.divmod` 는 파이썬
     별칭으로 두되 내장 이름을 가리지 않게 `__all__` 에서 뺐다(`f_abs`·`f_divmod` 는 있음). 더한 것: `mul32`, `sdivmod`, `to32(signed=)`,
     `invert()`/`iinvert()`, `iabs()`, 제자리 모듈 함수 `imul/idiv/imod/iand/ior/ixor/ishl/ishr/iabs/iinvert`, epScript 통로
     `imulattr/ifloordivattr/imodattr/iandattr/iorattr/ixorattr/ilshiftattr/irshiftattr`, 배열 원소 연산 8종(+ `*item` 별칭),
     CtrigAsm 별칭 `LMul/LiMul/LDiv/LMod/LiDiv/LiMod/LAnd/LOr/LXor/LNot/LAbs/LRand`. `f_LlShift` 별칭은 시프트 양 해석이 달라 두지 않았다(D61).
  7. 32비트 변수가 왼쪽인 `v * x`·`v // x`·`v % x`·`v >> x` 를 안내 오류로 막았다(eudplib 이 Int64 를 제자리에서 바꾸던 경로).
  8. 공용 부품(자기 수정 갈림 트리거 틀·변수 트리거 사슬·결정 나무)을 `_parts` 에 공개 부품으로 두었다(4.1).
  9. D26(배열 원소 칸 EPD 채우기)은 하지 않았다 — 2차 원소 연산도 읽고-셈-쓰기(`arr[i] *= y` 7 / 365). 곱셈·나눗셈 비용이 읽기(76)보다
     커서 이득이 작다.

### 4.4b `i128` — 128비트 정수 — **WP20 완료**

**근거**: DPS 128비트 호출 163회(R1 1-b — `SetNumX128` 36, `f_LMov128` 24, `f_LAdd128` 24, `f_LMul128_2` 17, `f_LDiv128` 17,
`Compare_128` 9, `f_LMul128X` 8, `SetNumTBLX128` 7, `f_LMul128` 6, `f_LSub128` 5, 192·256비트 10). 7절 D12(새 맵이 필요로 할 때 —
사용자가 "할 수 있는 모든 작업" 을 요청해 WP20 으로 만들었다). 원본 DPS_Enhance `CallTriggers/utils/math128.lua`(`Call_div128`·
`Call_Add`·`Call_Sub`·`Call_mul64`·`Compare_128`)·`converter.lua`(`SetNumX128`), DPS 이식판(a7aad90, 받아 둔 사본 HEAD e7efff2)
`eud/ctrig/war.py:1075~1260`(`_div128`·`_div128_2`·`_div128_4`·`Div128`·`_mul6464`·`Mul128`)·`:1443~1560`(`AddWords`·`SubWords`)·
`eud/tests/t_war.py:89~138`(D128·K128·M128 기대값), eudext.i64(WP3·WP4 — 비교 계획·16비트 쪼개기 곱셈·64÷64 나눗셈·상수 제수·
10진 본문).

**실제로 쓰인 모양**(DPS 호출 자리): `f_LMul128_2(PVWArrX(a), PVWArrX(b))`(64×64 → 128, 17), `f_LDiv128(FFRet, {"100","0"})`
(128 ÷ 32비트 상수 — 100·1000·5000·5·10·20·32·1000000), `f_LDiv128({Credit, Credit3}, {GaCostXCWlo, GaCostXCWhi})`(128 ÷ 128 변수,
sell_refactored.lua:279), `f_LMov128(FP, XRet, {DRetT[1], DRetT[2]})`, `f_LMul128X({_LAdd(W,"1000"),"0"}, XRet)`(64 × 128),
`f_LAdd128({PVWArrX(x), PVWArrX(xhi)}, {DmgW, DmgWhi})`(플레이어별 128비트 누적 — 타격마다), `f_LSub128(총량, 사용량)`,
`Compare_128(A, AtLeast/Exactly/">", B)`, `{SetNumX128, {lo, hi}, 1}`(한글 단위 표기 — numfmt 몫).

**API** (모듈 함수는 `f_이름` + 파이썬 별칭, DPS 이름 별칭은 대문자 — epScript 번역에서 접두사가 붙지 않는다)

```python
from eudext import i128
from eudext.i128 import Int128, Int128Array, parse

x = Int128(10**30)                 # 초기값만 (트리거 0). Int128("340,282,…") · Int128(-1) (= 2^128 − 1) 도 된다
y = Int128(v32); y = Int128(i64v)  # 실행 시 대입 (0 확장)
z = Int128(lo64, hi64)             # 실행 시 대입 — 각 반쪽 = Int64·64비트 상수·32비트 변수·10진 문자열 (Int128 은 오류)
w = Int128.wrap(lo64, hi64)        # Int64 둘을 복사 없이 감싸기 (= i128.wrap)
w = Int128.wrap(w0, w1, w2, w3)    # EUDVariable 넷 (w0 이 최하위 — EUDFunc 인자·반환 받기)
x.w0 … x.w3, x.words               # 칸 (32비트 EUDVariable)
x.lo, x.hi                         # 반쪽 (복사 없이 같은 변수를 감싼 Int64)
k = parse("100000000000000000000000")  # 문자열 상수 → int (쉼표·밑줄·0x·음수 = 2의 보수, −2^127 ~ 2^128 − 1)

x << y; x.assign(y); x.v = y       # 대입 (epScript 식 `x << 3` 은 빌드 오류 — 시프트는 없다)
x += y; x.iadd(y, inline=None); x.v += y        # 덧셈 (wrap). inline=None: 32비트 이하 값이면 펼치고 그 밖은 공유 함수
x -= y; x.isub(y, inline=None); x.v -= y        # **wrap** 뺄셈 (x -= x 는 0 으로 접음)
x.isub_sat(y, inline=False)        # **포화** 뺄셈, 128비트 전체 기준. 변수끼리 기본 = 공유 함수
x.isubtractattr("v", y)            # 포화 별칭 (eudplib 이름 관례)
x.ineg(); x.neg(); -x              # 부호 반전 (wrap)
x + y; x - y; 5 - x                # 새 Int128 (상수끼리는 파이썬 int)
i128.add(a, b, inline=None); i128.sub(a, b, inline=None); i128.sub_sat(a, b, inline=False); i128.neg(a)
i128.iadd(x, b); i128.isub(x, b); i128.isub_sat(x, b)                 # 제자리 (x 는 Int128)
x >= y; x <= y; x == y; x > y; x < y; x != y   # 부호 없는 사전식 비교 → 조건 (i128.ge(a, b) … 도 같음)
x * y; 3 * x; x *= y; x.imul(y); x.v *= y      # 곱셈 (128비트 wrap). 64비트 이하끼리는 전체 곱
i128.mul(a, b); i128.mul64(a64, b64); i128.imul(x, b)   # mul64 = 64×64 → 128 (Int128 을 넣으면 오류)
x // y; x % y; divmod(x, y); x //= y; x %= y   # 부호 없는 나눗셈 (제수 128비트까지) — 나머지도 Int128
x.idiv(y); x.imod(y); x.v /= y; x.v %= y       # epScript `/` 는 `//` 로 번역된다. 파이썬 `x / y` 는 오류
i128.div(a, b); i128.mod(a, b); i128.divmod(a, b); i128.idiv(x, b); i128.imod(x, b)
x.fmt(); i128.fmt(x)               # 10진 (최대 39자리 — 호출 자리 버퍼 44B, 상수는 문자열)
i128.lidec_to(dst_epd, x, lead=None)   # 40자리 고정 폭(첫 바이트는 늘 '0')을 dst 10칸에 쓰고 앞자리 수(1~39) 반환 — numfmt 경계
x.to64(saturate=True); i128.to64(a, saturate=…)  # → 새 Int64 (포화 = min(x, 2^64 − 1), 아니면 하위 64비트)
x.to32(saturate=True); i128.to32(a, saturate=…)  # → 새 EUDVariable

# DPS math128 이름 (호출 모양만, PlayerID 없음)
i128.LMov128(d, x)                 # d ← x (d 는 Int128)
i128.LAdd128(a, b)                 # 새 값 a + b
i128.LSub128(a, b)                 # 새 값 max(a − b, 0) — 128비트 전체 기준 (원본과 다른 점은 아래)
i128.LMul128(a64, b64); i128.LMul128_2(a64, b64)   # = mul64 (.lo, .hi 가 원본의 Retlo, Rethi)
q, r = i128.LDiv128(a, d)          # = divmod (0 나눗셈은 eudext 규칙)
i128.LCmp128(a, ">=", b); i128.Compare_128(a, AtLeast, b)   # 조건 (">" "<" "==" ">=" "<=" "!=" · AtLeast/AtMost/Exactly)

arr = Int128Array(8)               # EUDArray 넷 (원소 16B). Int128Array([1, "10**30 의 10진", -1]) 도 된다
arr[i] = v; arr[i] += v; arr[i] -= v; arr[i] *= v; arr[i] /= v; arr[i] %= v   # epScript *item (−= 는 wrap)
arr.isub_sat(i, v); arr.isubtractitem(i, v)    # 포화
arr[i] >= v …                      # epScript _ARRC → geitem …
e = arr[i]                         # 새 Int128 **사본** (메서드·.v 로 제자리 연산하면 오류)
arr.w0 … arr.w3, arr.epd(k), len(arr)
# (파이썬 별칭 i128.divmod 는 내장 이름과 겹쳐 __all__ 에서 뺐다 — f_divmod 는 있다)
```

**만들지 않은 것**(DPS math128 이 쓰지 않거나 다른 모듈 몫): 부호 있는 128비트, 비트 연산·시프트(`&`·`>>` 등은 안내 오류),
192·256비트(`f_LAdd192` 3, `Compare_192/256`·`f_LSub256`·`SetNumX256`/`TBLX256` 각 1 — 모두 10회), 한글 단위 표기
`SetNumX128`/`SetNumTBLX128`(43 — numfmt 몫, 경계는 `i128.lidec_to`), `f_LMul128X` 의 "두 상위가 모두 0 이 아니면 최댓값" 규칙
(`a * b` 는 wrap).

**의미**
- `+ − 단항−` wrap, 비교 연산자는 **사전식**(위 칸 먼저) 부호 없음. 32비트 변수·Int64 피연산자는 **0 확장**.
- **뺄셈 두 의미**(3.5): 연산자·`isub`·`sub`·`neg`·`isubitem` = wrap, `isub_sat`·`sub_sat`·`isubtractitem`·`isubtractattr`·`LSub128` =
  포화(128비트 전체 기준). 같은 객체끼리 `x -= x`·`sub_sat(x, x)` 는 0. 칸이 엇갈려 겹치는 경우(`x += Int128.wrap(x.w1, x.w0, …)`)는
  임시 변수(또는 공유 함수의 인자 복사)를 거친다.
  DPS `f_LSub128` 은 `Call_Sub`(Size 2)가 상위 64비트를 먼저 포화로 빼고(`f_LSub(A2, A2, B2)`) 하위를 보정해, `A2 < B2` 이고
  `A1 > B1` 이면 0 이 아니라 `A1 − B1` 을 낸다(반쪽별 포화의 한 형태) — 옮기지 않았다(D81).
- **곱셈**: `(a × b) mod 2^128`. 피연산자가 둘 다 64비트 이하(Int64·32비트 변수·64비트 상수)면 전체 곱이라 넘치지 않는다.
- **나눗셈**: 부호 없음. 0 나눗셈 = 몫 2^128 − 1, 나머지 = 피제수(i64·eudplib `f_div` 와 같은 규칙 — 7절 D4).
  DPS `Call_div128` 의 0 나눗셈은 나머지 반쪽이 뒤바뀐다(R1 ← A2, R2 ← A1) — 옮기지 않았다(D82).
  **나머지는 Int128**(`%`·`imod`·`divmod`·`LDiv128`): 제수가 64비트 이하면 위 64비트는 늘 0(`r.lo` 가 Int64), 0 나눗셈이면 피제수라
  128비트다(D80).
- **10진**: 앞 0 없이 최대 39자리(`2^128 − 1 = 340282366920938463463374607431768211455`). `lidec_to` 는 40자리 고정 폭(첫 바이트 = 10^39
  자리는 늘 '0')과 앞자리 수 1~39(값 0 이면 39)를 준다.
- **to64/to32**: `saturate=True`(기본) = 최댓값에서 멈춤, `False` = 하위 비트.
- 32비트 변수가 **왼쪽**인 `v * x`·`v // x`·`v % x` 는 eudplib 연산자가 먼저 불려 안내 오류(`_compat.eudplib_calc_caller`, i64 와 같음).
  **Int64 가 왼쪽**인 `i64값 + x`·`i64값 >= x` 는 i64 연산자가 먼저 불려 i64 의 "쓸 수 없는 값" 오류다 → `i128.add(i64값, x)`·
  `i128.ge(i64값, x)`(5절 요청 1).
- 배열 원소 사본: `arr[i]` 는 읽은 사본이다. 사본(과 그 `.lo`/`.hi`)에 제자리 연산을 하면 EudextError(i64 와 같은 규칙).
- 파이썬 `x / y`·`x ** n`·비트·시프트는 오류. `EUDTypedFunc([Int128])` 는 안 된다 → `cast` 에서 안내 오류(칸 넷 인자 + `Int128.wrap`).

**알고리즘**
- 대입: SeqCompute 한 줄(칸이 엇갈려 겹치면 겹치는 원천만 임시 변수로).
- **덧셈(변수)**: 네 칸 `x_k += y_k` 를 한 줄에 하고, 같은 줄에서 올림 판정 amount ← 새 x_k + 1 을 채운다. 그 뒤 칸마다
  생성 G_k `[y_k ≥ amt][amt ≥ 1] → c_(k+1) ← 1`, 넘김 W_k `[c_k ≥ 1][x_k = M32] → x_k ← 0, c_(k+1) ← 2`,
  더함 I_k `[c_k ≥ 1][c_(k+1) ≤ 1] → x_k += 1`(깃발 c = EUDLightVariable). G_k 가 참이면 x_k < y_k ≤ M32 라 W_k 는 거짓이고 I_k 는
  넘치지 않는다. W_k 가 참이면 c_(k+1) = 2 라 I_k 는 거짓이다(DPS 이식판 `AddWords` 와 같은 생각). 칸 0 에는 들어오는 올림 대신
  cin(뺄셈의 +1)을 한 줄에 더하고 판정을 `[y_0 ≥ 새 x_0]` 로 바꾼다. 트리거 8(한 줄 제외), 실행 16.
- **wrap 뺄셈** = `x + ~y + 1`(~y = 0xFFFFFFFF ⊖ y — 포화하지 않는다, 3.5-7). **포화 뺄셈** = 같은 덧셈에 마지막 올림 깃발을 더 내고
  `[c_4 = 0](= 빌림) → x ← 0`. i64 의 SK·WK 처럼 반쪽 조합을 쓰지 않고 칸 넷 전체 기준이다.
- **상수 덧셈**: 한 트리거로 칸마다 더한 뒤, 칸 j 로 올림이 들어오는 경우 `[s_(j−1) ≤ k_(j−1) − 1]` 또는
  `[s_(j−1) = M32] ∧ (칸 j−1 로 올림)` 를 서로 배타인 조건 묶음으로 펼쳐 **위 칸부터**(아래 칸을 아직 고치지 않았을 때) `x_j += 1`.
  깃발 없음, 트리거 1 + 0~6. 상수 뺄셈 = `x + (−K mod 2^128)`. **상수 포화** = `x < K` 묶음(0~4, 서로 배타)이면 `x ← K` 로 두고 K 를 뺀다.
- **펼침/공유 함수**(3.3): 변수끼리 펼치면 호출 자리 9 트리거 4.5KB, 공유 함수(`_addsub_fn` — 인자 8, 반환 4) 호출은 1 트리거 2.8KB 라
  **공유 함수가 기본**이다(`inline=None` — 32비트 이하 값은 펼침이 더 작아 펼친다). 포화는 i64 와 같게 공유 함수 기본(`inline=False`).
- **비교**: i64 비교 계획(DPS a7aad90 `tlib.py:204`)을 재귀로 넓혔다 —
  `lex(x, y, 엄격) = [x_t ≥ y_t] ∧ ¬([x_t ≤ y_t] ∧ lex(y 나머지, x 나머지, ¬엄격))`, 칸이 둘 남으면 i64 와 같은 원자 식.
  부정 부분마다 자기 칸 깃발(`_parts.flag_cond`)을 끄는 조건 트리거 하나(안쪽 먼저 — Plan 순서). 변수 값은 조건 amount 칸에 채우고
  (`Plan`, amount 자리는 `Forward` — 3.4), 같은 변수를 두 번 원천으로 쓰지 않게 방향을 고른다(i64 `_pick`). `==` 는 원자 넷의 AND.
- **곱셈(변수 64×64 → 128)** — i64 16비트 쪼개기의 전체 곱 판: 곱해지는 수의 칸 둘을 16비트 조각 t0~t3 으로 나누고(`_split16`),
  곱하는 수의 16비트 조각 m 의 비트 i 마다 조건 트리거 하나가 사슬로 `A[k][m] += t_k`(k = 0~3), 단마다 t_k 두 배(남은 비트가 없으면 끝).
  `A[k][m] = a_k·b_m < 2^32` 라 16개 누적기 모두 넘치지 않는다. 가중치 2^(16(k+m)): 짝수 무리의 첫 누적기는 곧 반환 칸 R_(s/2)이고,
  홀수 무리(s = 1·3·5)는 한 누적기에 합쳐(올림 → H += 2^16) 16비트로 갈라 H(윗 칸)·L(아랫 칸)에 옮긴다. 마지막으로 칸마다
  `R_w += 나머지 짝수 누적기, H_w, L_w`(올림 → R_(w+1) += 1 — R_(w+1) ≤ 2^32 − 2^17 + 1 이라 작은 올림 몇 개는 넘치지 않는다).
  올림 판정 `[R_w ≤ V − 1] ∧ [V ≥ 1]` 의 amount 는 누적기면 한 줄로 미리 채우고, H·L 이면 비트를 옮길 때 같이 더한다(i64 `_mul_tail`)
  — 반환 칸 R 은 원천으로 쓰지 않는다(eudplib 반환 변수 규칙). 곱하는 수가 32비트면 64×32 본문(조각 m = 0·1). 둘 다 32비트면 i64
  32×32 본문. 본문 251 / 162, 실행 최악 585 / 368.
- **곱셈(128비트가 낌)**: `P = 하위 64 × 하위 64 (전체)`, `P += (a 상위 × b 하위 mod 2^64) << 64`, `P += (a 하위 × b 상위 mod 2^64) << 64`
  (i64 64×64 곱셈 본문과 i64 인라인 덧셈 — 상위가 0 이면 건너뜀). 조율 본문(`_mulbig_fn`, 13)은 다른 EUDFunc 를 부르므로 반환 변수를
  미리 정하지 않는다.
- **상수 곱**(K마다 본문, 곱해지는 수 칸 수 1·2·4 마다): 비트 누적 — x 의 비트 i 마다 조건 트리거 하나가 `T_i = K·2^i mod 2^128` 의
  칸을 누적기에 더한다. 칸 w 누적기에 더해지는 횟수 N_w 로 나눔 비트 `S_w = 32 − ⌈log2 N_w⌉` 를 정해 하위 S_w 비트는 R_w 에, 나머지는
  F_w 에 더한다(N_w·(2^S − 1) < 2^32). 끝에서 F_w·2^(S_w) 를 비트마다 Lx_w(칸 안쪽)·Lx_(w+1)(바깥)로 옮기고 `R_w += Lx_w`
  (올림 → Lx_(w+1) += 1, 판정 amount 는 Lx 에 더할 때 같이). 맨 위 칸은 wrap 으로 바로 더한다. 16비트 조각이 0 이면 건너뛴다.
  i64 의 배가·덧셈(작은 상수)은 128비트에서 한 단이 비싸(두 배 8·덧셈 16) 옮기지 않았다.
- **나눗셈(32비트 제수 d)**: i64 64÷64 공유 본문을 위 칸부터 — `(x3:x2) ÷ d → 몫 위 두 칸, r`, `(r:x1) ÷ d → 몫 칸 1`(r < d 라
  < 2^32), `(r:x0) ÷ d → 몫 칸 0, 나머지`. 위 두 칸이 0 이면 한 번.
- **나눗셈(64비트 제수 D, D ≥ 2^32)**: "나머지 R < D 인 (R·2^32 + x) ÷ D" 한 칸 본문(`_d9664`, 32단)을 위 칸부터(맨 위 0 아닌 칸 t 에서
  R = x_t 로 시작 — t = 0 이면 몫 0). 한 단 = OVT([옛 R 위 칸 ≥ 2^31] → 이 단의 S0 다음을 OV 로) → 준비(공유 트리거 next·몫 비트) →
  R 두 배(i64 의 TC 사슬) → S0([x 비트] R += 1) → K0([rh ≤ dh − 1] → 다음 단) → K1([rh ≥ dh + 1][dh + 1 ≠ 0][rl ≥ dl] → 뺌) →
  K2([rh ≥ dh + 1][dh + 1 ≠ 0][rl ≤ dl − 1] → 빌려 뺌) → K3([rl ≥ dl] → 뺌) → 다음 단. i64 `_udiv_emit` 64비트 제수 단은
  dh < 2^31 이라 넘침이 없었지만 여기서는 R < D 가 2^63 이상일 수 있다: 넘침(OV)이면 참값 2^64 + R ≥ D 라 반드시 한 번 빼고
  (wrap 뺄셈 — OV1 `[rl ≥ dl]` / OV2 빌림), dh = M32 이면 dh + 1 이 0 으로 도는 것을 `[amount ≥ 1]` 막이 조건으로 막는다. 단당 실행 7~12.
- **나눗셈(128비트 제수 D ≥ 2^64)**: N < D → 몫 0 (i128 비교 계획), D ≥ 2^127 → 몫 1·나머지 N − D, 그 밖은 몫 < 2^64 인 64단
  복원 나눗셈(`_d128`): R = N >> 64 에서 N 의 아래 64비트를 밀어 넣는다(2R + 1 < 2D < 2^128 — 넘치지 않음). 한 단 = 준비 → R 두 배
  (칸 넷 변수 트리거 + 올림 셋) → S0 → K0a `[r3 ≤ d3 − 1][d3 ≥ 1]`·K0b `[d3 = 0][r3 = 0][r2 ≤ d2 − 1]`(R 이 확실히 작으면 다음 단) →
  P(b1,b2,b3) 8개 — `R − D` 의 빌림 조합마다 칸 조건 넷(채운 amount, 넘침 막이 포함)이 참이면 몫 비트를 더하고 칸마다
  `−d_k` 또는 `−d_k − 1` 을 더하는 뺄셈 사슬로(참인 조합은 R ≥ D 일 때 하나뿐) → 다음 단. 단당 실행 11~23.
- **상수 제수 K < 2^32**: i64 상수 제수 본문(`i64._cdiv_fn(K, "qr")` — 이식판 a41d2ed `_cdiv`, 64비트 값 ÷ K)을 32비트 제수와 같은 순서로
  세 번(위 두 칸이 0 이면 한 번) 부르는 작은 본문(K마다 9). 칸 넷을 한 번에 나누는 `_cdiv_emit(K, 칸 넷)` 본문(K마다 약 265 트리거,
  한 번 페이로드 약 84KB)보다 한 번 페이로드가 절반 이하(약 45KB, 그중 약 36KB 는 같은 상수로 64비트를 나누는 i64 코드와 공유)이고
  실행은 40~231(칸 넷 본문 27~181). K = 0·1 은 인라인, K ≥ 2^32 는 변수 제수 본문에 상수를 인자로.
- **10진**: 윗 20자리(10^39 ~ 10^20 자리)와 10^19 자리는 `c = b·10^i`(b = 8·4·2·1) 복원 뺄셈 — 단마다 "값 ≥ c 면 c 를 빼고 자릿값을
  더함" 을 **빌림 조합마다 트리거 하나**(`_ksub_emit`: 칸 k 가 빌리지 않으면 `[v_k ≥ c_k + b_in]`·SC Subtract, 빌리면
  `[v_k ≤ c_k + b_in − 1]`·wrap 더하기)로 펼친다. 단 시작 때 값 < 2c(불변식)라 한 조합이 빼면 값 < c 가 되어 다른 조합은 거짓이다.
  칸 수는 `2c − 1` 이 들어가는 만큼(4 → 3). 들어가는 곳: 위 칸 ≥ 1 → 첫 단, 칸 2 ≥ 1 → c < 2^96 인 첫 단, 그 밖(값 < 2^64)은
  윗 단을 모두 건너뛴다. 남은 값(< 10^19)은 i64 10진 본문(`_lidec_body`, 20자리)을 그대로 부르고, 그 본문이 쓰는 첫 칸(10^19 자리 = '0')에
  윗 본문이 돌려준 10^19 자리 숫자를 더한다. 앞자리 '0' 수 = 윗 20자리 수(1~20), 윗 본문을 건너뛰었으면 20 + 아래 자리 수.
  윗 본문 372 트리거(빌림 조합 344 + 앞자리 수 20), 호출 자리 7(64비트 이하 4).
- **배열**: 칸 번호·값이 모두 상수면 원소 칸(`_Cell`)에 상수 덧셈·포화·비교를 바로 쓴다(읽기 없음). 그 밖은 `EUDArray` 읽기 네 번
  (변수 칸 번호는 새 변수에 복사 — rvalue 제자리 고침 방지, 3.9)·셈·쓰기 네 번.

**비용** (2026-09-17, `docs/COSTS.md` "i128 (WP20)". 호출 자리 / 실행, 비교는 소비 트리거 제외)
덧셈 변수 1 / 35(공유 함수 기본, 본문 11), 펼침 9 / 16, Int64 1 / 33·펼침 8 / 12, 32비트 변수 펼침 7 / 9, 상수 4~7 / 4~7, 새 값 1 / 35 ·
wrap 뺄셈 1 / 39(본문 11), 펼침 9 / 20, 32비트 변수 9 / 12, 상수 7 / 7 · 포화 1 / 43(본문 14), 펼침 12 / 24, 상수 8~11 · 부호 반전 1 / 37 ·
대입 1 / 1~5 · 비교 변수 5 / 12, `==` 2 / 6, `!=` 3 / 7, Int64 5 / 8, 상수 1~5 / 1~5 ·
곱셈 64×64 1 / 165~585(본문 251), 64×32 1 / 119~368(162), 32×32 2 / 68~209(i64 본문 106), 128×64 1 / 104~963, 128×128 1 / 108~1,326,
상수 1 / 20~196(상수마다 본문 117~184) · 나눗셈 32비트 제수 1 / 124~703(본문 13 + i64 389), 64비트 제수 1 / 127~1,047(본문 143 —
최악 추정 약 1,270), 128비트 제수 1 / 48~1,272(본문 209 — 최악 추정 약 1,520), 상수 제수 1 / 40~231(상수마다 본문 9 + i64 상수 본문),
64비트 상수(10^19) 1 / 286~910 · 10진 7 / 176~536(본문 372 + i64 137), 64비트 이하 4 / 150 · to64 3 / 5, to32 4 / 5 ·
배열 변수 칸 읽기 9 / 154, 쓰기 5 / 14, `arr[i] += y` 15 / 203, 상수 칸·상수 값 덧셈 4 / 4, 비교 5 / 5.
**한 번 페이로드**(빈 빌드 대비, 호출 하나 포함): 덧셈 공유 함수 약 8KB, 포화 약 9.5KB, 64×64 곱 약 123KB, 128×128 곱 약 198KB,
상수 곱 상수마다 약 36~48KB, 상수 나눗셈 상수마다 약 45KB(i64 상수 본문 약 36KB 포함), 32비트 제수 나눗셈 약 153KB(i64 나눗셈 본문 포함),
64비트 제수 약 222KB, 128비트 제수 약 374KB, 10진 약 213KB(i64 10진 본문 48KB 포함).
**3.8 목표**(2절에 새 줄): 곱셈 64×64 ≤ 1,000 — 최악 585, 128×128 ≤ 1,400 — 최악 1,326. 나눗셈 32비트 제수 ≤ 711 — 최악 703,
64비트 제수 ≤ 1,300, 128비트 제수 ≤ 1,600. 10진 본문 ≤ 620(윗 본문 372) / 실행 ≤ 600 — 최악 536. **넘은 항목 없음.**
DPS 원본 대비: 128비트 나눗셈 호출당 약 23,000 실행(Lua 128단 루프 — 이식판 DESIGN 5차 기록) → 최악 약 1,300, 상수 5000 ÷ 이식판 174 → 236.

**시험**: `tests/t_i128.py` 기본 234,778 판정(약 2분 15초), `EUDEXT_I128_FULL=1` 전체 872,888 판정(약 9분) — 경계값 24개(칸 경계 2^32·2^64·2^96 의
올림·빌림, 2^127, 10^19·10^38, 칸마다 다른 무늬) 전 쌍 + 무작위 600쌍(전체 4,000 — 비트 폭과 제수 모양을 섞음: 0, 32비트 제수 > 2^31,
64비트 제수 ≥ 2^63(넘침 비트), 128비트 제수, D ≥ 2^127, 위 칸이 같음, 같은 값) × 덧셈 9형태·wrap 뺄셈 7·부호 반전 3·포화 8·대입(DPS 별칭 포함),
비교 6연산 × 연산자·모듈 함수·뒤집기·LCmp128(문자열·AtLeast/AtMost/Exactly) + 3연산 × 문맥 12종(EUDIf·neg·EUDNot·RawTrigger·
EUDSCAnd/Or ± neg·목록·EUDTernary ± neg·EUDElseIf), 곱셈 7형태, 나눗셈 18형태, to64/to32·반쪽·생성, Int64·32비트 변수 섞기 30형태
(64×64·64×32·32×64·32×32 전체 곱 포함), 같은 객체 18형태, 칸이 엇갈려 겹치는 경우 9형태 / 상수 26개(0·1·2·3·7·10·100·1000·5000·10^8·
2^31 근처·2^32 근처·6.5·10^12·10^16·2^63·2^64 근처·10^20·10^30·2^127·2^127 + 12345·2^128 − 1·2^100 — 정수·음수·쉼표 10진·10진 표기를
돌려 씀) × (경계 24 + 근처 7 + 무작위 10(전체 30)) × 30형태(오른쪽·왼쪽 덧셈·뺄셈·포화·곱셈·나눗셈·나머지, 제자리, 비교 12, mul64,
32비트 × 상수) / EUDWhile 조건 재계산 3종, 상수 조건 문맥 5종 × 12, Int128Array(변수 칸 × 변수·상수 값 15연산, 상수 칸 7개 × 상수·변수 값,
초기값 목록), 생성 규칙 16형태(초기값만 / 실행 시 대입, 반쪽 조합, EUDLightVariable·주소식·문자열), 10진 출력 바이트(fmt 여섯 모양 한 줄,
두 fmt 한 줄, `lidec_to` 상수·변수 dst — 10^k·10^k − 1 경계, 2^k, 무작위), DPS math128 호출 모양 재현 17출력 × 44입력(CallTriggers·mine·
money·damage_check·GlobalBoss·token·sell_refactored(128 ÷ 128)·TBL), 이식판 `t_war.py` 128비트 기대값(D128 11쌍·K128 6·M128 9)과 0 제수
(eudext 규칙), epScript 예제 16함수 차등, 번역 문자열 24개, 인게임 맵 에뮬레이션(46 / 46), euddraft 0.11 빌드 2개, 빌드 오류여야 하는 모양
10종(`x << 3`, `var x = Int128`, `return x >= 1`, 원소 사본 `.v +=`, `v * x`·`v / x`·`v % x`, `x & 5`, `x.v >>= 1`,
`EUDTypedFunc([Int128])`), 파이썬 쪽 판정 352(상수 접기·오류 30여 종·사본 쓰기 금지 11종·별칭·`__all__`·docstring·비공개 API·마스크 Add 안 씀).
`EUDEXT_I128_ONLY=vars,const,misc,eps,py,ingame,build,bad` 로 묶음을 골라 돌릴 수 있다.

**위험**
① 64비트 제수 넘침 비트(OV) 경로와 128비트 제수 빌림 조합 조건은 트리거 next 자기 수정·조건 amount·액션 칸 채우기에 기댄다 — i64
  2차와 같은 기법이라 새 가정은 없지만 인게임 권장 F20-1(`examples/i128_ingame.eds` "점검 46 / 46").
② 한 번 페이로드가 크다(128비트 제수 나눗셈 약 374KB, 128×128 곱 약 198KB, 10진 약 213KB) — 128비트 나눗셈·출력을 쓰는 맵만 낸다.
③ eudext.i64 의 내부 이름 21개에 기댄다(`_Cell`·`_isvar`·`_isconst`·`_epd`·`_rd`·`_act`·`_read_tmp`·`GE/LE/EQ`·`_cmp`·`_gt`·`_and`·
  `_negate`·`_simplify`·`_conds`·`_halves`·`_assign`·`_const_pair`·`_iadd`·`_mul_into`·`_mul_fn`·`_udiv_fn`·`_cdiv_fn`·`_lidec_body`·
  `_split16`) — i64 를 고치면 `t_i128.py` 도 돌린다(5절 요청 2).
④ 조율 본문(곱셈·나눗셈 `_mulbig_fn`·`_udiv_fn`·`_cdiv_fn`)은 다른 EUDFunc 를 부르므로 반환 변수를 미리 정하지 않았다(EUDReturn).
  본문 안에서 사용자 코드를 부르지 않는다(재진입 없음). `_d128` 은 나머지 변수를 두 배 원천으로 쓰므로 역시 EUDReturn.
⑤ Int64 가 왼쪽인 산술·비교는 i64 오류 메시지("쓸 수 없는 값")가 나온다 — 안내가 부족하다(5절 요청 1).
⑥ 인라인 덧셈의 올림 깃발·임시 변수는 빌드마다 새로 만든 공용 칸을 쓴다(한 연산 안에서만 — i64 `_scratch` 와 같은 규칙).

**초안과 달라진 점**
1. 표현을 "`Int64` 두 개" 대신 **32비트 칸 넷**(`EUDVariable` 넷)으로: 칸 단위 올림 전파·빌림 조합·비교 계획이 칸 넷에서 짜인다.
   `x.lo`/`x.hi` 는 같은 변수를 감싼 Int64 라 64비트 코드와 바로 섞인다. `Int128.wrap` 은 Int64 둘 또는 변수 넷을 받는다.
2. 나눗셈 제수를 64비트에서 **128비트까지** 넓혔다(DPS `f_LDiv128` 이 128비트 제수를 한 번 쓴다 — sell_refactored.lua:279).
3. **나머지를 Int128** 로(설계 초안 "나머지 64") — 0 나눗셈 규칙(나머지 = 피제수)을 지키고 연산자 결과 타입을 고르게 하려고.
   제수가 64비트 이하면 위 칸은 0 이라 `r.lo` 로 64비트를 얻는다(D80).
4. 변수끼리 덧셈·wrap 뺄셈 기본을 **공유 함수**로(i64 는 펼침 기본): 128비트 펼침은 호출 자리 바이트가 공유 함수 호출의 1.6배라
   3.3 규칙대로. 32비트 이하 값은 펼침(`inline=None` 자동, D79).
5. 상수 제수 < 2^32 를 칸 넷 한 번(`_cdiv_emit` n = 4 — 이식판 `_cdiv(c, 4)` 와 같음) 대신 i64 상수 본문 세 번으로(한 번 페이로드 절반,
   i64 와 공유 — D84).
6. 10진은 numfmt 에 기대지 않고 i128 안에서(윗 자리 복원 뺄셈 + i64 10진 본문). numfmt 의 128비트 서식(`SetNumX128` 한글 단위 등)은
   `i128.lidec_to`(40자리 고정 폭 + 앞자리 수)를 경계로 쓰면 된다(5절 요청 3).
7. 더한 것: `mul64`(64×64 전체 곱), `to32`, `ineg`/`neg`, `Int128Array`(DPS 플레이어별 128비트 값), DPS 이름 별칭
   `LMov128/LAdd128/LSub128/LMul128/LMul128_2/LDiv128/LCmp128/Compare_128`.
8. 만들지 않은 것: 부호 있는 128비트·비트·시프트(DPS 0회), 192·256비트(DPS 10회), `f_LMul128X` 포화 규칙, 한글 단위 표기(numfmt 몫).

---

### 4.5 `mathx` — 삼각·정수 수학 — **WP9 완료**

**근거**: `f_Lengthdir` 8맵 100회. 전부 Cycle 360, **음수 반지름과 360 초과·음수 각도가 실제로 들어온다**(R1). eudplib `f_lengthdir` 는 음수에서 틀림(예: (100, −90) → (−97, 24), R4b C5).
고정밀 모드(LengthdirX)는 Memory_2 한 곳 — 그 맵은 `Include_CtrigPlib(360, …, 1)` 이라 `CA_Rotate`·`CA_Rotate3D`(G_CB 점 변환)까지 고정밀 표를 쓴다.
원본: CtrigAsm v5.5 `f_Lengthdir`(CA:84377~84638), `f_Atan2`(CA:84640~84841), `f_Atan2X`(CA:84843~85048), `CiDiv`/`CiMod`(CA:25314, 26882), `CNeg`(CA:22466),
`f_Div`/`f_iDiv`/`f_iMod`(CA:30465~31105), `f_Sqrt`(CA:84231), `f_Log2`(CA:85121), CB Paint v2.5 `CA_RatioXY`/`CA_Rotate`/`CA_Rotate3D`(CBP:9718, 9865, 9883).
TEP 정수화: TrigEditPlus v3.0 `Encoder/TriggerEncode.cpp:85` `luaL_checkint_Fix` = C `(int)` 캐스트(0 방향), `bit32.band` 도 `(lua_Integer)` 캐스트(`src/linit.c:37`).

**파일**: `eudext/mathx.py`(API), `eudext/mathx_tables.py`(표 — eudplib 없이 컴파일 시점 계산, shape·plot·bullet 도 쓸 수 있음),
`tests/ref_mathx.py`(참조 구현 — 원본을 줄 단위로 옮김), `tests/t_mathx.py`, `examples/mathx_example.{eps,eds}`, `examples/mathx_ingame.{eps,eds}`(C9-2),
`examples/mathx_tep_check.py`(C9-1 도구: TEP 에 넣을 Lua 를 쓰고, TEP 로 컴파일한 맵의 표 값을 대조한다).

**API**

```python
from eudext import mathx as mx
c, s = mx.lengthdir(r, a, cycle=360, precise=False, ret=None)   # (r·cos a, r·sin a) = CtrigAsm f_Lengthdir (precise = LengthdirX)
rot = mx.Rotator(angle=None, cycle=360, precise=False, own=False) # 상수 각 = 고정 / 변수 각 = 만들 때 복사 / None = 변수 각(처음 0, 트리거 0)
x2, y2 = rot(x, y)            # = rot.rotate(x, y, ret=None) — CA_Rotate (항별 자르기)
c, s = rot.lengthdir(r)       # 이 각의 lengthdir
rot.set(a); rot.angle += 1    # 변수 각만 (상수 각 Rotator 에 부르면 EudextError)
X, Y, Z = mx.rotate3d(x, y, xy=None, yz=None, zx=None, cycle=360, precise=False, own=False, ret=None)  # CA_Rotate3D
t = mx.atan2(dy, dx, cycle=360, ret=None)        # CtrigAsm f_Atan2 (0 = +x, 시계, 0 ~ cycle−1, 올림 성격)
d = mx.atan2_sc(dy, dx, ret=None)                # CtrigAsm f_Atan2X (SC 256 방향, 0 = 위쪽)
d = mx.to_dir256(a, cycle=360, ret=None)         # (floor((a mod cycle)·256/cycle) + 64) mod 256
q, m = mx.sdivmod(a, b, div0="eudplib"|"ctrig", ret=None)   # 0 방향 몫, 피제수 부호 나머지
q = mx.sdiv(a, b, div0=…, ret=None); m = mx.smod(a, b, div0=…, ret=None)
v = mx.ratio(x, mul, div, div0="eudplib", ret=None)          # x·mul(32비트) ÷ div (CA_RatioXY 한 축)
k = mx.isqrt(n, ret=None); e = mx.ilog2(n, zero=0x80000000, ret=None)
mx.DIV0                                            # ("eudplib", "ctrig")
from eudext import mathx_tables as mt              # sin_table(cycle), atan_thresholds(cycle), coarse_thresholds(),
                                                   # packed_sin_table(cycle), precise_table_bytes(cycle), precise_table_size(cycle),
                                                   # cr_sin/cr_tan, check_cycle, MAX_CYCLE (= 65536), SIN_SCALE
```

- 모듈 함수는 `f_이름` 이 정본이고 `이름` 이 별칭(3.1). epScript: `import eudext.mathx as mx;` → `const c, s = mx.lengthdir(r, a);`,
  전역 `var cx, cy;` 에는 `cx, cy = mx.lengthdir(r, a);`, `mx.lengthdir(r, a, 360, ret=list(cx, cy));`, `const rot = mx.Rotator();`(전역에서는 None 또는 상수 각),
  `rot.set(a);`, `const x2, y2 = rot(x, y);`, `rot.angle += 5;`, `mx.sdiv(a, 0, "ctrig")`, `mx.smod(a, 7, div0="ctrig")`.
- 인자: 정수 상수(−2³¹ ~ 2³²−1, 32비트로 읽음), `EUDVariable`, 읽기 전용 값 칸(`EUDLightVariable`·`cell.Cell` — `f_dwread_epd` 로 읽음, 실행 +36), 주소식(복사).
  실수·범위 밖 정수·그 밖은 `EudextError`. cycle 은 4 ~ 65536 의 4의 배수(`mathx_tables.check_cycle`), precise·own 은 bool, div0 는 `DIV0` 중 하나.
- 반환(3.3): **모두 상수면 파이썬 정수**(트리거 0) — 부호 있는 결과(lengthdir·회전·sdiv·smod·ratio)는 음수 정수, atan2·to_dir256·isqrt·ilog2 는 0 이상.
  `ret=` 를 주면 그 변수에 넣는다(트리거 1). 변수가 있으면 EUDFunc 호출 → eudplib 관례대로 새 변수 튜플(`ret=` 가능).
- `Delta`(f_Diff)·`Table`(CMathFunc)은 **만들지 않았다**(사용 0, 0.2). 필요해지면 `mathx_tables` 의 정확 반올림 표 도구 위에 만든다.

**각도 기준·결과 (사용자 결정 D5 — 옵션 없음)**
- 런타임 0 = +x, y 가 아래로 커지므로 각이 늘면 화면에서 시계 방향. SC 256 방향은 `atan2_sc`/`to_dir256`.
- lengthdir: 표 `T[i] = trunc(0x10000·sin(i·90/Q °))`(Q = cycle/4, T[30] = 32767, T[45] = 46340, T[90] = 65536). 결과 = `R·T` 를 32비트로 곱해
  `CiDiv(·, 0x10000)`(0 방향), 사분면 부호면 뒤집기. 각은 `a mod cycle`(부호 있게 읽음 — 원본 "θ ≥ Cycle 이면 CiMod, 음수면 +Cycle" 과 같다).
  **R 은 원본 범위(−32768 ~ 32767) 밖이어도 원본처럼 곱이 한 바퀴 돈 값**을 낸다(느린 길).
- 고정밀(precise): 표 칸 (l, k) = trunc(k·sin(l·90/Q °)) (double 곱 뒤 자르기), |R| 의 하위 15비트로 읽고 사분면 부호 → R 부호 순으로 뒤집는다
  (R = −32768 → 0). **표 크기 (Q+1)×32768×4 — 360 이면 11,927,552 바이트**, 처음 쓸 때 `EPWarning`.
- 회전 `x' = lx.cos − ly.sin`, `y' = lx.sin + ly.cos`(항마다 자름, wrap 뺄셈). rotate3d = 원본 단계 그대로(Z 는 0 에서 시작, ZX 단계는 X 만 고친다).
- atan2: 부호로 사분면을 정하고 |dy|<<16 (32비트, 원본처럼 돔) ÷ |dx| (0 이면 0xFFFFFFFF) 비율 → `A[i] = trunc(0x10000·tan(i·90/Q °))` 에서
  `비율 ≤ A[i]` 인 첫 i(없으면 Q). A[45] = 65535 라 (1, 1) → 46, (0, 0) → 90. 사분면 보정 2Q−θ / θ+2Q / 4Q−θ. 원본 범위 안 출력 0 ~ cycle−1.
  원본의 거친 8갈래 점프는 결과를 바꾸지 않는다(참조 구현으로 주기 9개 × 무작위 확인).
- atan2_sc = atan2(·, ·, 256) + 64, 256 이상이면 −256. to_dir256 = 위 식(cycle 360 은 사용자 표 `(i/360)*256` 자르기 + 64 와 같음, S4 2.3).

**표 (플랫폼 무관)**: 원본 값은 C 라이브러리 `sin`/`tan` 에 달려 있고 sin 30°(32767.999…)·tan 45°(65535.999…)가 자르기 경계에 붙어 있다.
`mathx_tables` 는 sin·tan 을 `decimal` 50자리로 구해 **정확 반올림** double 로 만든 뒤 자른다 → Windows(euddraft 번들 파이썬)에서 빌드해도 같은 표.
Linux glibc `math` 과 4 ~ 1024 의 모든 주기·큰 주기에서 같다(시험). 헤드리스 TEP(`tepc`, Linux)로 CtrigAsm 표 식을 그대로 컴파일한 트리거 값과도 같다(시험, C9-1 도구).
원본을 실제로 빌드하는 **Windows TEP(MSVC UCRT)** 에서도 같은지는 인게임 항목 **C9-1(필수)** 로 확인한다.

**0 나눗셈 (D4 권장안 — 구현)**
- `div0="eudplib"`(기본): eudplib `f_div_towards_zero` 와 같다 — 몫 = a ≥ 0 이면 0xFFFFFFFF(−1), a < 0 이면 **1**(부호 없는 "몫 전부 1" 에 부호 보정), 나머지 = a.
- `div0="ctrig"`: CtrigAsm `f_iDiv`/`f_iMod` — 몫 = a ≥ 0 이면 0x7FFFFFFF, a < 0 이면 0x80000000, 나머지 = a.
  상수 0 으로 나누는 원본 `CiDiv(X, 0)` 은 ±1 이 되지만 따르지 않는다(상수·변수 제수 모두 f_iDiv 규칙).
- b ≠ 0: 두 정책 모두 0 방향 몫·피제수 부호 나머지(C 방식), −2³¹ ÷ −1 = −2³¹. ratio 도 같은 정책.

**알고리즘**
- lengthdir 빠른 길(|R| ≤ 32767): |R| 의 비트 15개마다 조건 트리거 하나가 `cos칸 += Tc·2^i`, `sin칸 += Ts·2^i`(두 액션), 이어서 `>> 16`(eudplib 시프트 트리거 1),
  부호 = R 부호 XOR 사분면 부호(조건 하나, 비교값이 1 − 사분면 부호). 느린 길(|R| > 32767): 절댓값 곱(eudplib `f_mul`, 작은 쪽 비트만) + `CiDiv(·, 0x10000)`.
- 상수 각: 각(정규화 값)마다 본문 1벌 — 곱이 상수 액션, T = 0 이면 트리거 없음, T = 0x10000 이면 복사.
- 변수 각: **주기·정밀도마다 공유 엔진 하나**(lengthdir·Rotator·rotate3d 기본). 엔진은 "마지막으로 준비한 각" 과 그 상태(액션 값 칸 30개, 부호 조건 비교값 2개)를 들고 있고,
  각이 다르면 준비한다: 정규화(흔한 [cycle, 2cycle)·[−cycle, 0) 은 트리거 2개) → 사분면(트리거 4) → sin·cos 를 한 칸에 담은 표(`EUDVArray`, Q+1 칸) 읽기 →
  두 값을 2배씩 늘리며 30칸에 쓰기(`SeqCompute` 60 연산). 처음 상태는 각 0.
  `Rotator(…, own=True)`·`rotate3d(…, own=True)` 는 전용 엔진(번갈아 불러도 준비하지 않음, 대신 페이로드 약 +55KB·+150KB).
- 고정밀: 엔진이 cos·sin 표 행의 EPD 를 준비하고 점마다 `f_dwread_epd` 2번.
- atan2: |dx| ≤ 65535 면 제수 배수 사슬(x·2^k, k < L — L 은 2^(16+L) 이 마지막 문턱보다 크게 하는 가장 작은 값, 최소 8. 360 은 8칸) 하나를
  서브루틴으로 세 번(정수 부분 L 비트 → 소수 1바이트 → 1바이트). y ≥ x·2^L 이면 바로 Q. |dy| > 65535 는 원본 `<<16` 이 하위 16비트만 남기므로 같은 길.
  |dx| > 65535(원본 범위 밖)만 32비트 나눗셈(DPS 이식판 `div3232`, sdiv 와 공유).
  비율 → 각은 "A[i] < 비율 인 i 의 개수"(표가 단조라 '처음 참인 i' 와 같다 — 표를 만들 때 단조를 검사)를 이진 결정 나무(버킷 폭 6) + 버킷 안 세기로.
- isqrt: 두 비트씩 내리는 자릿수 방식(곱셈 없음, D = rem·4 + 쌍 − (4r+1) 을 조건 트리거가 자기 액션 값 칸에서 읽음), 앞쪽 0 쌍은 점프로 건너뛴다.
- ilog2: 2¹⁶ 으로 갈라 문턱 15개 세기. to_dir256: 정규화 → `a <<= 11` → 8단 긴 나눗셈(제수 cycle·8) → +64 → 256 이상이면 −256.
- sdiv: 부호 떼기 → 부호 없는 나눗셈(변수 제수 = DPS 이식판 `div3232`(마지막 제수 표 재사용), 상수 제수 = 긴 나눗셈 사슬 또는 시프트·마스크) → 부호 붙이기.
- ratio: 곱은 절댓값 곱(변수×변수) 또는 eudplib 상수 곱(상수마다 본문 1벌) → sdiv.

**비용** (2026-09-17, `docs/COSTS.md` "mathx (WP9)" — 본문 / 호출 자리 / 실행): 3.8 에 목표 없음. S1 8.6 "회전 점당 +120" 만 걸었고 통과.
- lengthdir 변수 각: 공유 본문 108(+ 준비 본문) / 1 / **같은 각 36, 각 준비 160~186**, |r| > 32767 +약 210. 상수 각: 30(각마다) / 1 / 31 (느린 길 240).
- 고정밀(주기 8): 62 / 1 / 116. Rotator 같은 각의 점 **89**(목표 120), 상수 각 76, 각이 바뀐 첫 점 213~240. rotate3d 상수 각 셋 174.
- atan2(360): 182 / 1 / **16~123**(dx = 0 → 16), |dx| > 65535 약 170. atan2_sc 122~125. to_dir256 43 / 1 / 20~47. isqrt 129 / 1 / 33~185. ilog2 37 / 1 / 24.
- sdivmod 변수 211 / 1 / 27(같은 제수)~271, 상수 7 → 36 / 1 / 43, 상수 65536 → 10 / 1 / 18. ratio(변수, 150, 100) 75, 변수 셋 189~283.
- 한 번 드는 페이로드(빈 빌드 대비, 쓰는 eudplib 공유 함수 포함): lengthdir 변수 각 98KB(그중 느린 길의 eudplib `f_mul` 38KB), 상수 각 54KB, Rotator(공유) 103KB,
  rotate3d 104KB, atan2 111KB(1024 주기 159KB, 그중 `div3232` 52KB), isqrt 41KB, sdiv 57KB. eudplib 참고: `f_lengthdir` 57KB, `f_atan2` 125KB, `f_sqrt` 66KB.
- eudplib 대비 실행: `f_lengthdir` 267(값 틀림), `f_atan2` 517(값 다름), `f_sqrt` 758~1478.

**시험**: `tests/t_mathx.py` — 기본 66,368 판정(약 85초), `EUDEXT_MATHX_FULL=1` 전체 843,896 판정(약 12분(718초) — 무작위 793,400 + 경계 조합 17,566).
- 참조 구현 `tests/ref_mathx.py` 와 차등: lengthdir(주기 360·4·8·12·64·256·1024 변수 각, 상수 각 38개, 상수 반지름 13개, 고정밀 8·16, `ret`, 읽기 전용 칸 입력,
  같은 각/다른 각 번갈아), 한 사이클 16호출 묶음 **무작위 기본 8,000 / 전체 200,000**; atan2(주기 7개, 상수 한쪽 12개, atan2_sc, S4 6.1 표) 묶음 **8,000 / 200,000**;
  Rotator(변수·None+set·`angle +=`·상수 각 12개·고정밀 16, 변수 각 Rotator 둘을 공유/own 으로 번갈아 + lengthdir 섞기, 사이클마다 각 하나로 8점 **1,600 / 50,000점**),
  rotate3d(변수 셋·상수 5조합·섞음·own·고정밀 16, 묶음 400 / 20,000), isqrt·ilog2(제곱·2의 거듭제곱 ±1 경계), sdivmod 두 정책(변수·상수 제수 16개·상수 피제수 6개),
  ratio(변수 셋·상수 9조합·섞음), to_dir256(주기 6개). 경계 조합: R 17 × 각 32, dy·dx 20 × 20, EDGES32 + 작은 수 등 기본 16,018개.
- 전체 실행에서만: 고정밀 360(11.9MB 표) 20,000개 + 경계, 고정밀 Rotator 45°, 주기 4096·65536 의 atan2·lengthdir 각 5,000개.
- S1 9.2 좌표·회전·크기 벡터 전부, S4 6.1 방향 표·f_bullet_to 표 — 에뮬레이터와 상수 접기 모두.
- 표: Decimal 표 = libm 표(주기 4~1024 전부 + 1440·2048·3600·4096·16384·65536), 고정밀 표본, 원본 거친 점프 = 첫 i(무작위), 상수 접기 = 참조(기본 2만·전체 20만 벌).
- 입력 검사 23가지, 별칭·`__all__`, eudplib 비공개 import·남의 비공개 속성 접근 없음.
- epScript: 예제 번역(15곳)·에뮬레이터(기본 60·전체 400 사이클을 참조와 비교)·euddraft 빌드, 인게임 맵 번역·표 110칸 = 참조·에뮬레이터(일치 110 / 110, 출력 14줄)·euddraft 빌드.
- 헤드리스 TEP(`/home/developer/TEP3.0_Headless_Compiler/build/tepc`, `EUDEXT_TEPC` 로 바꿈)로 C9-1 도구의 Lua 를 컴파일 → 표 261칸 일치.

**위험·미확인**
- Windows TEP 의 `sin(30°)`·`tan(45°)` 가 정확 반올림과 다르면 원본 값 자체가 다르다(C9-1).
- 에뮬레이터 가정: eudplib 시프트(`>>=`·`<<=` 11 이상)·`ineg`·atan2 의 `<< 8` 액션(eudplib 식 복사)이 쓰는 마스크 SetTo/Add/Subtract 식(A-1), 조건 amount 칸을 실행 중에 채우는 비교(B1-1),
  조건이 같은 트리거의 액션 값 칸을 읽는 자기 칸(isqrt), 액션 값 칸 패치(엔진·나눗셈 사슬) — C9-2 인게임 맵이 한꺼번에 본다.
- eudplib `f_lengthdir`/`f_atan2` 를 대신 쓰면 음수·반올림이 조용히 달라진다(R4b C5) → eudext 안에서는 쓰지 않는다.
- 공유 엔진은 EUDFunc 이라 재진입하지 않는다(콜백 없음 — 문제 없음). 각이 다른 lengthdir·Rotator 를 점마다 번갈아 부르면 매번 준비(+약 125) — `own=True` 로 피한다.

**초안과 달라진 점**
- `Rotator` 에 `set`/`angle`/`lengthdir`/`own`, 각 None(변수 각, 트리거 0) 추가. 변수 각 본문은 주기마다 공유가 기본(용량) — 인스턴스마다 본문을 두면 한 개에 약 55KB.
- `rotate3d` 는 2단계 예정이었지만 S1 이 쓰므로 1차에 넣었다(`own` 선택 포함). 반환에 Z 를 준다(원본은 임시 칸).
- `sdivmod` 추가(몫·나머지 한 번에 — `sdiv`/`smod` 는 그 한쪽). `smod` 의 div0 는 두 정책 모두 나머지 = a 라 결과가 같다.
- 0 나눗셈 eudplib 정책의 음수 피제수 몫은 1(eudplib `f_div_towards_zero` 와 같게) — 3.5 의 "몫 전부 1" 문구를 이렇게 풀었다(7절 D27).
- 원본 범위 밖 입력도 원본의 넘친 값을 재현(7절 D28). 표는 파이썬 `math` 대신 정확 반올림(플랫폼 무관).
- `Delta`·`Table` 은 만들지 않음. `ratio` 의 상수 곱은 DPS `_mul_small`(호출 자리마다 약 40 트리거) 대신 eudplib 상수 곱.
- 경계 시험 목록에 R = −32768·32768, 각 0x80000000, dy/dx = ±65535·±65536 을 더했다.

---

### 4.6 `numfmt` — 숫자 서식 — **WP5 완료**

**근거**: DisplayPrint 원소·ItoCustom 에서 실제로 쓰는 것(R1 3절 2번): 자릿수 제한, 0 채움, 전각, 자리마다 색, 세 자리 묶음, 부호, 64비트.
eudplib 은 부호 없는 가변 10진과 8자리 대문자 16진뿐(R4a C.2). 명세(정본): `docs/spec/S3_display.md` 4.4·4.5·7.4·8.1, R4a C, S6 1.7.
구현 재료: DPS 이식판 `eud/ctrig/text.py` `_itodec16_ops`·`_itodec48_ops`·`_itohex12_ops`·`_lidec_ops`·`_dec_digits`(a7aad90 — 작업 때
`../DPS_Enhance-eudplib-port` 는 e7efff2 로 더 새것이었고 text.py 도 바뀌었지만 쓴 것은 알고리즘(자리값 비교·뺄셈)뿐이다),
CtrigAsm v5.5.lua:58336 `ItoDec`·58911 `ItoDecX`·54357 `CD__ScanV`, DPS `CallTriggers/utils/converter.lua`(SetNumX·SetEPer), i64 10진 본문(WP3).

**API**

```python
from eudext import numfmt
from eudext.numfmt import Dec, Hex, Man, Per, Gauge

Dec(v, width=0, fill="\r", sign=None, sign_space=False, max_digits=None, cut_low=0,
    fullwidth=False, colors=None, group=None, glyphs=None, align=None, bits=None)
    # v: EUDVariable·식 | EUDLightVariable·Cell(인쇄 때 읽음) | 정수·10진 문자열 | Int64 | 주소식
    # sign: None(부호 없음) | "-" | "+-" | " -"(파이썬 " ")      sign_space: 부호 뒤 공백(CtrigAsm Sign=2)
    # align: None(fill "0" 이면 "=", 그 밖 ">") | ">" | "="       group: None | True | "," | (n, sep)
    # colors: None | 정수 | 1의 자리부터 목록(모자라면 0x0D)      glyphs: 10글자 문자열·목록   bits: None | 32 | 64
Hex(v, width=8, lower=False, fill="0", align=None)          # 32비트만 (Int64 는 2차)
Man(v, top=2, colors=None, after=None, units="만억조경해자양구간정재극항아나불무", fixed=False)   # top 1 | 2
Per(v, scale=1000, frac=3, max=None, trim=True, int_min=1, width=0, fill="\r")
Gauge(n, cells=20, glyph="l", on=0x07, off=0x04)
numfmt.dp.dec16 / decfw48 / hex12 / dec20 / name20 / man18(v, color=False) / per8(v, permil=False, tbl=False) / dig2 / gauge40

f_sprintf(buf, "HP {}", Dec(hp, width=5, fill="0"))   # fmt() 훅 (패치 없음)
sb.printf("{} 골드", Dec(gold, group=True)); printAll("MP {}", nf.Dec(mp, width=5, fill="0"));
obj.fmt()            # 이 자리 버퍼에 쓰고 ptr2s (상수면 bytes) — TextFX 에는 이것을
obj.max_len / obj.fixed_len / obj.const_bytes()          # display(WP6) 용

numfmt.f_fmt_dec_to(dst_ptr, value, **opts) -> 쓴 길이             # NUL 없음 (별칭 fmt_dec_to)
numfmt.f_fmt_dec_cells(dst_epd, value, color=None, layout="eudplib", **opts) -> 쓴 칸 수   # 오른쪽 정렬 전체 칸
numfmt.f_scan_dec_cells(src_epd, n, signed=False, layout="eudplib") -> 값                 # CD__ScanV 대체
numfmt.enable_format_spec() / disable_format_spec() / format_spec_enabled()             # 선택 몽키패치
```

**의미**
- 서식 객체는 **만들 때 트리거 0**, `fmt()` 를 부르는 자리에 변환 호출과 그 자리 전용 버퍼(Db, 출력 최대 길이 + NUL)가 생긴다.
  eudplib 인쇄 함수(`f_dbstr_print`·`f_sprintf`·`f_cpstr_print`·`StringBuffer.print/printf/append`·`f_eprintln`·`printAll`)는
  인자마다 `fmt()` 를 먼저 부르므로 객체를 그대로 넘기면 된다(3.2-7). 값은 인쇄 순간에 읽는다. 한 인쇄에 여러 개·`fmt()` 를 미리 여러 번 불러도
  버퍼가 따로다. 상수 값이면 `fmt()` 가 bytes(트리거 0).
- 객체는 eudplib `ptr2s` 를 상속한 **표식**이다 → 서식 문자열(`_EUDFormatter`)을 그대로 통과한다. `f_cpchar_print`(TextFX·`StringBuffer.fadeIn`
  경로 — `fmt()` 를 부르지 않는다)는 `_value` 를 읽는 순간 **안내 오류**(`EudextError`)가 난다 → `obj.fmt()` 결과를 넘긴다(R4a C.3).
  `format(obj)`·f-문자열·`bool(obj)` 도 안내 오류. epScript `var d = nf.Dec(x);` 는 빌드 오류(값 타입이 아니라 const 에 담는다).
- `Dec` 기본은 **부호 없음**(eudplib `{}` 와 같음). 표시용 맨 변수를 부호 있게 찍는 것(D17)은 display 몫(`Dec(v, sign="-")`).
- 파이썬 `format` 과 같은 조합은 **바이트까지 같다**: width·fill·align·sign(`-`/`+`/` `)·group(`,`/`_`)·`0` 채움(부호 뒤 0,
  구분자도 0 사이에 들어가고 구분자로 시작하지 않게 0 하나 더 — 파이썬 규칙). fill 기본 `"\r"` 은 `{:\r>Nd}` 와 같다.
- 확장: `sign_space`(부호 글자 뒤 공백 — CtrigAsm Sign=2), `max_digits=m`(아래 m 자리만, 값이 더 길면 남긴 자리의 0 도 보임 — DigitMax),
  `cut_low=c`(아래 c 자리 **글자만** 0x0D, 부호·채움은 그대로, 길이 유지 — DigitMin = c+1), `fullwidth`(글자마다 4B 셀 `[0D][EF BC 90+d]`,
  `\r`→`0D×4`, `" "`→U+3000, 그 밖 ASCII→전각 — ItoDecX), `colors`(반각이면 모든 글자가 2B `[색|0D][글자]`, 전각·셀이면 셀 앞 바이트),
  `glyphs`(숫자 글자표, 폭이 섞이면 0x0D 로 채움, 4B 글자는 접두 없이), 셀 배치 `layout="eudplib"`(`[C][c][0D][0D]`)·`"ctrig"`(`[C][0D][0D][c]`).
- `Hex`: `{:08X}` 모양(fill `"0"` = 0 채움), `width=0` 이면 앞 0 없음, `lower`.
- `Man`: 원본 SetNumX 규칙 — 단위 t(0 = 만 미만), 윗덩이 A = V // 10^(4t), 다음 덩이 B(0 이면 숨김, top=1 이면 늘 숨김).
  배치 = 덩이마다 `[색][4자리 — 앞 0 은 0x0D][after][단위]`. `fixed=True` 는 18B 전체와 원본 버릇(값 0 이면 after 없음, t=0 은 B 칸에 값)까지
  `numfmt.dp.man18` 과 같고, `fixed=False` 는 앞의 0x0D(색이 없으면 첫 숫자 앞까지)를 건너뛰고 값 0 도 after 를 붙인다.
  colors: `"dps"`(S3 4.5-3 표) | 단위별 색 목록 | 단위별 (색1, 색2) 목록. 원본의 10^40 이상 근사는 따라 하지 않는다(128비트는 WP20).
- `Per`: v/scale 을 frac 자리까지 버림, `trim` 이면 뒤 0 과(모두 0 이면) 점을 0x0D 로, 정수부 최소 `int_min` 자리, `max` 로 자름.
  scale 은 10^s(s ≥ 1), frac ≤ s. `width/fill` 은 앞 채움(dp.per8 = width 8).
- `numfmt.dp.*`(S3 8.1 과 바이트 일치): `dec16` = 앞 D×5 + `=` 정렬 폭 11(부호는 고정 자리), `decfw48` = 전각 폭 12칸, `hex12` = D×4 + `%08X`,
  `dec20` = 양수 `\r>20`, 음수 `-` + 19자리 0 채움, `name20` = `[D D D 색]` + 0x6D0FDC 이름 16B(0 바이트 → D, p ≥ 7 이면 쓰지 않음 — DPL 캐시 0~6,
  상수 p ≥ 7 은 오류), `man18`, `per8`(최대 100000 / 퍼밀 STR 5000000·TBL 1000000), `dig2` = `max_digits=2, width=2`, `gauge40`.
- `f_fmt_dec_to`: 출력 길이가 고정이고 dst 가 정수 상수이며 `(dst − 시작 위치) % 4 == 0` 이면 반환 변수를 목적지 단어에 바로 쓴다(앞 부분 단어는
  마스크 쓰기, 앞뒤 바이트 보존). 그 밖은 `f_dbstr_print(dst, obj, EOS=False)`(바이트 복사). 반환 = int(고정·상수) 또는 EUDVariable.
- `f_fmt_dec_cells`: 이미지 전체(최대 글자 수 또는 width 칸)를 오른쪽 정렬로 쓰고 앞 칸은 빈 셀 `0D×4`. 숫자 셀의 C = color(또는 colors),
  다른 셀의 C = 0x0D. 반환 = 칸 수(상수). 변수 EPD 는 CP 를 잠깐 옮겨 쓴다(3.6-3).
- `f_scan_dec_cells`: 앞에서부터 숫자 셀 = ×10 + 자리, `,` 셀 건너뜀, `-` 셀(signed) = 0·음수 표시, 그 밖 셀 = 0·표시 끔 → 끝에서 거꾸로 읽다
  숫자·쉼표 아닌 글자에서 멈추는 CD__ScanV 와 같은 값. 셀의 나머지 두 바이트가 0x0D 가 아니면 숫자가 아니다. 32비트 넘침은 wrap.
  CP 를 잠깐 옮겨 `DeathsX(CurrentPlayer, …)` 조건으로 읽는다(읽기 비용 없음).
- `enable_format_spec()`: `_compat.hook_format_field` 로 `_EUDFormatter.eudformat_field` 를 감싼다. 숫자 값(정수·변수·칸·Int64)에
  `d`·`x`·`X`·`w`(전각)·빈 형식 + 너비/채움/정렬/부호/묶음 지정자가 오면 Dec/Hex 로 바꾼다. `{}`·`{:x}`·`{:X}`(eudplib 8자리 대문자)·`s t c n` 은
  eudplib 그대로. 부호 글자가 있으면 부호 있는 값. Int64 의 `{}` 도 Dec. 안 되는 것(`<`·`^` 정렬, `#`, 정밀도, `z`, 16진 부호·묶음)은 빌드 오류.
  `disable_format_spec()` 으로 되돌린다(컴파일 시점 전역 상태).

**알고리즘**
- **배치(layout)**: 글자 슬롯(폭 U = 1 | 2 | 3 | 4)을 본문 영역(작업 단어 W 개, 오른쪽 정렬)에 늘어놓는다 — 자리 k 의 위치 D[k], 구분자·점 슬롯,
  Per 는 NUL 뒤에 숨은 아래 자리. 이미지 = 덧붙인 단어 E 개(너비·부호용, 꼬리마다) + 본문 단어 W 개.
- **공용 본문(배치별 1벌, EUDFunc, 반환 없음 — 공용 작업 단어 `_POOL`·시작 위치 `_S` 에 쓴다)**: 32비트 = 자릿수 판정 `[a ≥ base^(n−1)] → S = D[n−1]`
  9(16진 7) + 자리값 비교·뺄셈 `[a ≥ b·base^k] → a ⊖ b·base^k, 단어 += b·증가분` 39(16진은 니블마다 `[a ≥ 10·16^k] → 글자 보정` 을 먼저 두어
  마스크 조건 없이 40) = 본문 49. 글자 증가분은 슬롯 바이트를 정수로 본 등차(ASCII·전각·셀 모두), 등차가 아닌 glyphs 는 자리마다
  `[a ≥ j·10^k]`(j = 9..1, 먼저 맞는 것만) 마스크 SetTo 9개. 색·채움·구분자·부호는 본문을 가르지 않는다(꼬리가 초기화).
  64비트 = i64 `_lidec_code` 와 같은 단 표(빌림 없음/빌림 배타 트리거) + 뒤에서 `[S == D[k]] ∧ [자리 k 가 0 글자] → S = D[k−1]` 19.
  **64비트 반각 연속 배치는 i64 의 10진 본문(`i64._lidec_body` — `i64.lidec_to` 와 같은 본문)을 반환 변수만 바꿔 부른다**(Int64.fmt 와 공유).
- **옵션 꼬리(옵션 튜플마다 1벌, EUDFunc, 반환 변수 = 덧붙인 단어 + 본문 단어 + S 를 `_compat.predefine_returns` 로 미리 정함 → 호출 자리의
  `ret=[EPD(buf)+j…, p]` 로 버퍼에 바로 쓴다)**: 단어·S 초기화 1 → (Per) 최댓값 자르기 → (부호) `x ≥ 2^31` 이면 `t = ~x + 1`(3.5-7) 로 본문을 부르고
  음수 보정, 아니면 그대로(가지 안에 본문 호출이 둘) → S += 4E → (max_digits) `[S < D[m−1]] → S = D[m−1]`, (Per) 정수부 최소 →
  **시작 위치별 보정**: 계획(파이썬)이 첫 유효 자리 위치 F 마다 [새 시작, F) 에 쓸 바이트(채움·부호·0 채움 무늬·cut_low·셀 앞 빈 칸)와 새 시작 위치를
  구하고, 이미 그 값인 바이트는 빼고, 같은 보정이 이어지는 F 끼리 묶고, 묶음이 4개를 넘으면 F 범위를 반으로 나눠 분기(실행 = 깊이 + 잎 2~3).
  보정 쓰기는 작업 변수 값 칸에 **마스크 SetTo**(SetMemoryX) — 자리 글자가 이미 들어간 칸에도 맞다. S 는 늘 왼쪽으로만 옮겨 뒤 트리거에 다시 걸리지 않는다.
  출력 길이가 고정이면 S 보정을 빼고 끝에서 상수로. → (Per) 뒤 0 가림(자리 조건 frac + 점 1).
- 상수 값·`max_len`·`fixed_len` 은 같은 계획을 파이썬으로 흉내 내 구한다(트리거와 같은 결과가 보장된다).
- **Man**: 앞 계산(1벌) → (Q, T): 32비트 = `[x ≥ 10^4]`·`[x ≥ 10^8]` 판정 + T=2 면 Q = x // 10^4 비교·뺄셈 19단(나눗셈 없음),
  64비트 = 단위 판정 8 + T ≥ 2 가지마다 Q = x // 10^(4T−4) 를 64비트 비교·뺄셈 27단(값 < 2^64 인 단만)으로 — **i64 나눗셈(WP4)을 쓰지 않는다**
  (상수 제수라 비교·뺄셈이 더 싸고 WP4 를 기다리지 않는다). 꼬리(옵션마다) = A = Q // 10^4(14단), 단위별 색·after·단위 쓰기(T 마다 1),
  숨김(값 0·B = 0·top=1), 시작 위치(fixed=False), 덩이 안 앞 0 → D(6), 자리 글자 32.
- **Gauge**: 꼬리(옵션마다) = 초기화 + `[n ≥ i+1] → i 칸 색 = on` 칸마다 1.
- **name20**: 꼬리 1벌 = e = 9p + EPD(0x6D0FDC), `f_dwread_epd` 4번, 색 7, 0 바이트 → D 16. 호출 자리가 `[p ≤ 6]` 일 때만 부른다.

**비용** (2026-09-17, `docs/COSTS.md` "numfmt (WP5)" — 본문 / 호출 / 실행, 3.8 목표 안)
32비트 `Dec` 본문 49 / 호출 2 / 실행 60~78(옵션 꼬리 3~42 — dp.dec16 42, 부호 24, 부호+0 채움+묶음 40), 등차 아닌 glyphs 본문 95 / 실행 111 ·
`Hex` 48 / 2 / 58~61 · `Per` 49 / 2 / 65~70 · 64비트 `Dec` 본문 136~137(반각은 i64 본문 공유) / 2 / 153~175 ·
`Man` 32비트 앞 계산 27 + 꼬리 60~67 / 3 / 83~109, 64비트 앞 계산 147 + 꼬리 67 / 3 / 102~144 · `Gauge(20칸)` 22 / 2 / 36 ·
`dp.name20` 36 / 3 / 약 190 · `f_fmt_dec_to` 단어째 호출 3 / Dec + 0~2, 바이트 복사 바이트당 약 30 · `f_fmt_dec_cells` 상수 EPD 호출 1,
변수 EPD 칸당 약 3(호출 자리 22 — 8.8KB, 드묾) · `f_scan_dec_cells` 본문 27 / 칸당 약 8 + 숫자 칸 약 12.
호출 자리 페이로드 약 1.2~1.5KB(버퍼 + 결과 포인터 변수 + 호출 트리거, i64.fmt 와 비슷).

**시험**: `tests/t_numfmt.py` **266,085 판정** — 옵션 조합(32비트 179 · 64비트 20 · 16진 9 · Per 14 · Man 13 · Gauge 6) × 경계값·무작위 바이트 비교
(참조 `tests/ref_numfmt.py` — 파이썬 `format` 과 같음을 스스로 확인하고, 확장 없는 조합은 시험에서도 `format` 과 직접 비교),
`numfmt.dp.*` S3 8.1 표 + 무작위 2만 개(REF 모델 차등, 이름 표 7명 + p ≥ 7), fmt() 훅(`f_sprintf`·`f_dbstr_print`·`StringBuffer.print/printf`·
`printAll`, fmt() 두 번, 입력 종류 7가지), `enable_format_spec` 켠 뒤 13개 지정자·상수 지정자·끈 뒤 원래대로·빌드 오류 2, `f_cpchar_print`/
`TextFX_FadeIn`/`StringBuffer.fadeIn` 안내 오류, `f_fmt_dec_to`(단어째·바이트 복사·변수 주소·상수·가변, 앞뒤 보존, CP 보존),
`f_fmt_dec_cells`(상수·변수 EPD × eudplib/ctrig) → `f_scan_dec_cells` 왕복, 손으로 만든 셀 154개, 계획 흉내 = 참조(조합 수만 개),
옵션·지정자 오류 73, 문서·별칭·비공개 API, epScript 예제 9 함수(500) + DESIGN 0.3 모양 번역·실행, 인게임 맵 에뮬레이션 23 / 23, euddraft 0.11 빌드 2,
빌드 오류여야 하는 epScript 6.
**위험**: ① `enable_format_spec` 은 eudplib 비공개 `_EUDFormatter` 에 기댄다(`_WP5_REQUIRED`). ② 서식 객체가 `ptr2s` 표식인 것과 `f_cpchar_print`
가 `arg._value` 를 읽는 것에 기댄다(판이 바뀌면 안내 오류 대신 다른 오류가 날 수 있다 — 시험이 잡는다). ③ 64비트 반각은 i64 비공개 `_lidec_body`
(반환 변수 5 + 앞자리 수)에 기댄다 — 없으면 자체 본문으로 넘어가지만 모양이 바뀌면 틀린다(시험이 잡는다). ④ 보정이 작업 변수 값 칸 마스크 SetTo·
마스크 Exactly, 셀 읽기가 CP 기준 `DeathsX` 에 기댄다 — 인게임 D5-1. ⑤ StringBuffer·printAll 은 항목마다 dword 경계까지 0x0D 를 채운다(보이는 글은 같음).
⑥ 인게임 맵 첫 프레임이 약 31,000 트리거를 실행한다(비교 22개 — 맵 자체의 부담, 라이브러리 아님).

**초안과 달라진 점**
- `Dec` 에 `align`(`">"`/`"="`)·`bits` 인자를 더했다(파이썬 `{:*=8d}`·`{:0>5d}` 를 표현하고 32비트 값을 64비트 배치로). `sign` 에 `" -"`(파이썬 `" "`)를 더했다.
  `sign_space` 는 파이썬 `" "` 가 아니라 CtrigAsm Sign=2 "부호 뒤 공백" 으로 정했다(7절 D62).
- `fill="0"` 은 파이썬 `0` 플래그처럼 부호 뒤를 0 으로 채우고 구분자도 넣는다(D63). 다른 채움은 부호 앞.
- `cut_low` 는 자리 글자만 가리고 부호·채움 글자는 두며 길이를 유지한다(원본은 고정 16B 안의 자리를 0x0D 로 덮음).
- "공용 본문 1벌" 은 **배치(글자 폭·구분자 위치)별 1벌**이다. 옵션 꼬리는 반환 변수를 미리 정한 EUDFunc 이고, 시작 위치별 보정을 계획으로 미리 구해
  분기 트리로 낸다(초안의 "옵션별 작은 꼬리").
- 64비트: 반각은 i64 본문 재사용, 묶음·전각·셀·색 배치는 같은 단 표로 만든 자체 본문(초안의 "10^9 덩어리로 나눈 뒤 32비트 재사용" 대신 — 나눗셈이 없어 더 싸다).
  `Man` 64비트 몫도 i64 나눗셈 대신 비교·뺄셈.
- `Hex` 는 32비트만(Int64·부호·묶음·전각은 2차). `align` 인자를 더했다.
- `Per` 에 `width`·`fill` 을 더했다(dp.per8). scale 은 10 의 거듭제곱만.
- `Man` 의 top 은 1·2 만(3 이상은 2차). colors 에 단위별 색 목록·(색1, 색2) 목록. `units` 는 글자마다 폭이 달라도 된다(가장 넓은 폭에 0x0D 채움).
- `f_fmt_dec_cells` 는 이미지 전체를 오른쪽 정렬로 쓰고 칸 수(상수)를 돌려준다. `layout` 인자(eudplib/ctrig).
- `f_scan_dec_cells` 에 `layout` 인자, 규칙을 앞에서부터 읽는 모양으로 정했다(CD__ScanV 와 같은 값). `n` 은 변수여도 된다.
- `disable_format_spec`·`format_spec_enabled`, 서식 객체의 `max_len`·`fixed_len`·`const_bytes()` 를 더했다(WP6 가 버퍼 크기를 정할 때).
- `numfmt.dp` 는 하위 모듈이 아니라 모듈 안 객체다(epScript `nf.dp.dec16(v)` 는 그대로 번역된다 — `f_` 접두사 없음).
- `f_cpchar_print` 경로는 문서화 + **빌드 오류로 막는다**(R4a C.3 의 "시험으로 막는다").

---

### 4.7 `display`, `strdesign` — DisplayPrint 대체 — **WP6b 완료(display)·WP6a 완료(4.7.1 strdesign)**

> **2026-09-18 인게임: 13번째 줄 쪽에서 게임이 EUD ERROR(0xFF9BE98B — "이 EUD 지도는 지원되지 않습니다")로 멈췄다.**
> 사실만 적으면:
> - 같은 프레임 앞의 자체 점검(E6-8)은 **7 / 7 통과** — 거기에는 `show_line13(P1, "…", v42)`(32바이트)과
>   `set_tbl(1, "…", v42)` 가 들어 있고, **13번째 줄 버퍼와 TBL 바이트가 에뮬레이터와 같았다**. 즉 두 쓰기 자체는 된다.
> - 다음 프레임 E6-3 의 `show_line13(P1, 23바이트, 변수, 57바이트)`(틀 93바이트)에서 줄 버퍼에 글은 **써졌고**
>   (스냅숏에 남았다) 바로 뒤 `dbg.mark` 부터 기록이 없다.
> - **경계 검산**: `show_line13` 은 틀 ≤ `LINE13_MAX`(217)을 빌드 때 막고, 0x641598 부터 `(틀 + 1)`을 4로 올린 만큼
>   dword 로 쓴다. 93바이트면 +0..95 — 줄 버퍼(218) 안이다. 줄 밖(0x641672~3)을 dword 창에 넣는 경우는 틀 ≥ 213 일
>   때의 마지막 **마스크** dword(+216)뿐이고, 값은 마스크로 보존된다. 이 호출에는 해당 없고 이름 주소(0x57EEEB)·TBL
>   주소도 없다. **그래서 길이·경계는 원인이 아니다.**
> - 남은 후보: ① 상수 주소 `SetMemory` 로 줄 버퍼를 쓰는 방식(eudplib 은 CP + `SetDeaths(CurrentPlayer)` 로 쓴다 —
>   `string/cpprint.py` `_eprint_init`), ② `f_raise_CCMU` 의 CreateUnit 실패 트릭을 한 프레임에 두 번(자체 점검 + E6-3)
>   부르는 것, ③ 줄 번호 12 자체, ④ TBL 쓰기. → `25b_display_bisect`(18단계, `examples/display_bisect.py` 머리말의 표)가
>   한 단계에 한 가지만 해서 `bx.stage`·`bx.ok` 로 범인을 남긴다.
> 그 사이 **통합 맵에서는 E6-3·E6-4·E6-4b 를 뺐다**(자체 점검도 5 항목) — 그 뒤 단계(chat·final·assist)가 돌 수 있게.

**명세(정본)**: `docs/spec/S3_display.md`(DisplayPrint), `docs/spec/S7_strdesign.md`(StrDesign). API 는 S3 7절·S7 이 정본이고, 이 절은 구현 결과다.
구현 `eudext/display.py`, 시험 `tests/t_display.py`(18,000여 판정) + 참조 모델 `tests/ref_dp.py`, 표시 모델 `testing/dispmodel.py`,
예제 `examples/display_example.{eps,eds}`, 인게임 확인 맵 `examples/display_ingame.{eps,eds}`(기준 맵 `testing/base_multi.scx`),
`_compat.py` 끝 WP6b 블록(`force_add_string`, `forget_mapstring_addrs`, `string_map_token`, `refresh_mapstring_queries`),
비용 `docs/COSTS.md` "display (WP6b)".

**근거**: `DisplayPrint` 9맵 470, `DisplayPrintEr` 97(13번째 줄), `DisplayPrintTbl` 96(TBL = 버튼 설명), DPS 서식 원소 220(R1).
원소는 문자열·V·1바이트 변수가 95% 다(S3 6절). 재료: S3 4.1~4.5·8.1, DPS 이식판 e7efff2 `eud/spec/G8_text_scrdb.md` 1.5~1.9·
`eud/ctrig/text.py`(직접 쓰기 `_direct`·FixText), eudplib 0.81 `string/cpprint.py`(f_raise_CCMU·PName 주소)·`tblprint.py`·`userpl.py`·`strbuffer.py`.

**API**

```python
from eudext import display as dp
from eudext.display import PName, LocalName, Byte, Bytes, Pick, Part
from eudext.numfmt import Dec, Hex, Man, Per, Gauge

dp.show(target, *parts, sound=None, every=None, update_if=None, pin=False) -> dp.Shown   # DisplayPrint
dp.LOCAL                                   # 대상: 모든 PC 가 각자 자기 화면에 (DPS LCP, 관전자 포함). 목록 안에 있어도 된다
with dp.pinned(): ...                      # FixText(1)…(2) — epScript: dp.begin_pinned(); … dp.end_pinned();
dp.show_line13(target, *parts, hold=None) -> dp.Shown   # DisplayPrintEr (틀 ≤ 217B, 관전자·LOCAL 불가)
dp.set_tbl(tbl_id, *parts, tail="\u2009", eos=True, every=None, update_if=None, capacity=None) -> 최대 길이(NUL 포함)
t = dp.Template(*parts, every=None, update_if=None); t.string / t.string_id / t.addr / t.content / t.size; t.update()
dp.max_len(*parts, layout=False)           # 컴파일 시점 최대 바이트 (TBL capacity 계획용; layout=True = 틀 길이)
# parts: str | bytes | int 상수(부호 있는 10진) | EUDVariable·EUDLightVariable·Cell·상수식(부호 있는 10진, D17) | Int64(부호 있는 64비트)
#        | Dec/Hex/Man/Per/Gauge/numfmt.dp.* | PName(p, color="player"|None|색, cache=False) | LocalName(color=, cache=)
#        | Byte(v) | Bytes(v1, …) | Pick(i, table, default="", missing=None) | Part 하위 클래스(fmt()+max_len) | Part.of(값, max_len)
#        | 목록·튜플(펼친다 — sd.wrap(…) 그대로, epScript list(…))
# target: 상수 0~7·P1~P8 | 관전자 128~131·P9~P12 | EUDVariable | CurrentPlayer | Force1~4·AllPlayers·players.Force(n)
#         | players.Humans/Observers/Everyone/Allies/Targets | 목록 | dp.LOCAL  (판정은 players.contains_user)
# epScript: dp.show(…) → dp.f_show(…), show_line13 → f_show_line13, set_tbl → f_set_tbl, begin_pinned → f_begin_pinned,
#           max_len → f_max_len. 대문자(dp.LOCAL, dp.PName, dp.Template …)는 그대로. `default` 는 epScript 예약어 → Pick(…, missing=…),
#           None 대신 set_tbl(…, tail=false). 파이썬 별칭: show, show_line13, set_tbl, begin_pinned, end_pinned, max_len, pinned(with 전용)
```

**의미**
- **틀(template) 버퍼** — S3·초안의 "호출 자리 StringBuffer + `f_cpstr_print`" 대신 DPL 틀 방식(아래 "달라진 점" 1): 호출 자리마다 맵 문자열 하나
  (`_compat.force_add_string` — 같은 글자라도 합치지 않는다)를 만들고 **상수 원소는 그 문자열에 굽는다**. 실행 원소는 4바이트 경계에 맞춘
  **자리(slot)**(크기 = max_len 을 4 배수로 올림, 이름 캐시 28, name20 20)를 받고, 맞춤·남는 바이트는 0x0D(보이지 않는 글자)다.
  보이는 글은 원소를 이어 붙인 것과 같다. 상수 글자는 실행 0, 갱신은 자리만 쓴다.
- 자리 쓰기(종류는 `Shown.slots` 로 보인다):
  - `direct`(오른쪽 맞춤, 복사 없음): 맨 변수(`Dec(v, sign="-", width=12)`), Int64(폭 20), 고정 길이 `Dec`/`Hex`/`Per`(앞 부분 단어는 마스크 쓰기),
    **채움이 0x0D 인 가변 길이 `Dec`/`Hex`/`Per` 는 최대 폭으로 넓힌 같은 서식**(보이는 글이 같다), `Man`·`Gauge`(배치 전체 — 앞은 0x0D),
    `numfmt.dp.name20`(p ≥ 7 이면 이전 내용 — DPL 과 같음). numfmt 꼬리의 반환 칸을 자리 단어로 준다(`_Fmt._emit_buf` 훅).
  - `copy`(왼쪽 맞춤): 그 밖의 서식 객체(0 채움·공백 채움 가변 길이 등)·사용자 `Part` — 자리를 0x0D 로 지운 뒤 `f_dbstr_print`(바이트당 실행 약 35).
  - `name`: `[색]` + 이름 복사(0x57EEEB + 36p, NUL 까지 — 뒤 잔재를 쓰지 않는다). `namecache`(`cache=True`): 게임 시작 때 8명 × 28B 를
    72B 원소 사슬(`_compat.custom_varray`)에 담아 두고 dest 7개를 고쳐 뛰어든다(실행 8, 변수 p 는 EUDSwitch 공유 본문 약 25).
  - `pick`: 항목마다 같은 크기(4 배수, 0x0D 채움)로 구운 Db + EPD 표 → `f_repmovsd_epd`(단어당 약 35). 번호가 표 밖이면 default.
  - `bytes`: 상수 바이트는 갱신 첫 트리거에, 변수는 마스크 쓰기(첫 칸) / `f_bwrite_epd`. 값 0 은 0x0D.
- `show`: [every 시계 1] → `EUDIf(players.contains_user(target))` → 갱신(지우기·상수 1 + 자리마다 1~3, every/update_if 가 있으면 조건 분기) →
  표시 1(`DisplayTextAll` + 소리 `PlayWAVAll` + [pin 되돌리기] + `f_setcurpl2cpcache` 를 한 VProc 트리거에). 서식은 이 PC 가 대상일 때만 만든다(S3 7.1-1).
  대상에 이 PC 가 두 번 들어 있어도 한 번만 보인다. 안쪽은 `local.allow()` 구역.
  - 상수만: 대상이 상수 번호·`players.Targets`(Humans·Everyone …)만이면 `players.run_as(target, DisplayText(글), PlayWAV…)`(호출 1 / 실행 2 — 같은 번호가
    두 번 들어 있으면 두 번, 원본 RotatePlayer 와 같음), 변수가 든 목록·값이나 LOCAL 이면 판정 1회 + `DisplayTextAll`.
  - `every=N`(상수 N ≥ 1): 호출 자리 시계(`EUDLightVariable`)가 **모든 PC 에서** 호출마다 1 씩 줄고(포화) 0 인 호출에서 갱신하며 N 으로 되돌린다
    (대상이 아니던 PC 는 대상이 되는 순간 바로 갱신). `update_if`: 조건·조건 목록·변수(0 이 아니면 참)·`fn() -> 조건`. 둘 다면 둘 다 참일 때.
    표시는 매 호출. 상수만인 호출에서는 갱신할 것이 없어 쓰지 않는다(형식 검사만).
  - `pin=True`: 표시 직전 `f_gettextptr()`(0x640B58)를 공유 칸 `EUDXVariable(EPD(0x640B58))` 에 담고 표시 트리거의 VProc 로 되돌린다.
    `begin_pinned()/end_pinned()`(= `with pinned()`) 는 블록마다 칸 하나(중첩 가능, 짝이 안 맞으면 빌드 오류).
- `show_line13`: 공유 — 상수 대상마다 `f_raise_CCMU(p)`(+ `hold` 액션을 한 트리거에), 변수는 `p ≤ 7` 일 때만, CurrentPlayer 는 그대로,
  `players.Targets`(Humans 등)는 `players.each`. 로컬 — `contains_user(target) ∧ 이 PC 번호 ≤ 7` 이면 0x641598 에 틀 전체 + NUL
  (줄 버퍼 218B 밖 바이트는 마스크로 보존, 직접 쓰기 자리 단어는 건너뜀)을 한 트리거로 쓰고 자리를 채운다(CCMU **뒤에**).
  틀 > 217B 이면 빌드 오류, `\n` 이 있으면 경고, 로컬 구역(`local.only` 등) 안에서 부르면 경고. `hold`: None | (유닛, 값) → `SetDeaths(p, SetTo, 값, 유닛)` | fn(p).
- `set_tbl`: 원소를 **바이트 그대로**(0x0D 채움 없음, 맨 변수 = 가변 길이) `f_dbstr_print(GetTBLAddr(id), …, EOS=eos)` + tail. 모든 PC.
  서식은 먼저 모두 계산한다. `PName(cache=True)` 도 여기서는 실시간. capacity 를 주면 최대 길이(+NUL) 초과가 빌드 오류.
  상수만 쓰는 TBL 은 한 번만(시작 때·`EUDExecuteOnce`) 부른다(바이트당 실행 약 35).
- `Template`: 틀을 **처음 쓸 때**(`t.string`/`t.addr`/`t.update()`) 문자열 표에 넣는다(epScript 전역 const 로 만들어도 된다. 한 프로세스에서
  맵을 다시 불러오면 새 번호로 다시 넣는다). `update()` 는 모든 PC 에서(로컬 분기 없음), every/update_if 는 update() 자리에서(한 곳에서 매 프레임 부르는 것을 가정).
- **CP**: 모든 함수가 호출자의 CP 를 바꾸지 않는다(원본과 다름 — 3.6-5). 이 PC 번호·0x640B58·13번째 줄·TBL·버퍼는
  PC 마다 달라도 되는 표시 구역이고 공유 로직이 읽지 않는다(S3 7.1-4). numfmt 작업 칸·eudplib 바이트 읽기/쓰기 틀은 쓰기 전에 읽히지 않는다.
- 원소 정리: 목록·튜플만 펼친다(서식 객체·Targets 는 `dont_flatten`). 상수(문자열·int·상수 서식·상수 번호 Pick/Byte)는 이어 붙여 굽는다.
  NUL 이 든 상수는 경고. None·bool·실수·조건·배열(epScript 리스트 리터럴 = EUDArray)·최대 길이를 모르는 인쇄 값(`ptr2s`·`StringBuffer` —
  `Part.of(값, max_len)` 로)·`dp.LOCAL` 은 빌드 오류. 한 줄(`\n` 사이) 틀이 217B 를 넘으면 경고(E6-9).
- 이름: `PName` = 0x57EEEB(eudplib·IsPName 과 같음, **D15**), 옛 바이트 그대로는 `numfmt.dp.name20`(0x6D0FDC). TBL 끝 NUL = `eos=True`(**D16**).
  맨 변수 = 부호 있는 10진(**D17**). 이름 캐시는 `EUDOnStart` 로 채우므로 시작 코드 안에서 `PName(cache=True)` 를 처음 만들지 않는다(4.9 contains_user 와 같은 제약).

**비용**(2026-09-17, `docs/COSTS.md` "display (WP6b)", 호출 자리 = 공용 본문을 먼저 만든 뒤 그 자리 몫)
목표(4.7): 호출 자리 = 대상 판정 ≤ 3 + 분기 ≤ 2 + 원소마다 ≤ 3 + 표시 1 — **모두 안**.
`show(P1, "HP ", v)` 호출 4 / 실행 70~76 / 약 2.0KB(서식 본문 89 공유) · 상수만 run_as 1 / 2 / 371B(`players.Humans` 도 같음) ·
원소 3개(v, Man, v) 5 / 223~254 / 5.0KB · 변수 대상 5 · 섞인 대상 8 · every +3 · update_if +2 · pin +1(실행 +11) ·
넓힌 `Dec(v)` 6 / 71~74 · 복사 `Dec(v, width=5, fill="0")` 10 / 292~459 · `Per(max)` 6 / 75 · `man18` 5 / 86~105 · Int64 5 / 169~180 ·
`PName` 실시간 7~9 / 23~86 + 이름 바이트당 약 35 · `PName(cache=True)` 상수 4 / 12, 변수 4 / 24~38(시작 때 한 번 약 3,000) · `Byte` 6 / 8 ·
`Pick`(3개) 8 / 86 · `show_line13(P1, v)` 5 / 98~104 · 변수 대상 8 · Humans(each) 11 · `set_tbl`(20B + v) 11 / 1,182~1,350 ·
`set_tbl`(상수 40B) 6 / 1,734 · `Template.update()`(v) 1 / 66~72 · begin+end 2 / 12.

**시험**: `tests/t_display.py` **18,300여 판정**(스위트 9 + 파이썬 쪽)
- 원소 59종 × 경계값·무작위(7,531): 이 PC 화면 글(표시 모델이 **DisplayText 순간의 버퍼 메모리**를 읽음)의 보이는 글 = 원소 출력(`ref_numfmt`) 이음,
  버퍼 바이트 = 틀 모델(상수·4 배수 자리·자리 맞춤, `Shown.slots` 로 종류 확인), 상수·맞춤 바이트 불변, 25바이트 이름·NUL 뒤 잔재.
- S3 8.1(53): dp 프리셋 9개 × 8.1 표 행을 `show` 자리에서 바이트 비교, name20 `GALAXY_BURST`, `tbl_layout`(eos=False 바이트 일치), `er_layout`(보이는 글 = DPL).
- 대상 18종(+ 상수만 8종, players.display) × 이 PC 번호 12가지(0~7, 128~131 — `suite.restart(local_player=…)`, 빌드 한 번) × 변수 조합(8,112):
  보인 횟수 정확히 1/0, 소리, 로컬 분기 1회, CP(원시·캐시) 복구.
- 옵션(20): every(주기·대상 바뀜·LOCAL), update_if(변수·조건·목록 + every), pin·pinned·중첩·begin/end(채팅 줄 모델 `chatmodel` + `live_strings`), 소리 목록, 빌드 오류 3.
- 13번째 줄(1,625): 대상 8종 × 이 PC 7가지 × 변수 — CCMU 대상·순서(이 PC 와 무관), 로컬 쓰기는 대상 PC(관전자 제외)에서만, 틀 + NUL, 보초 보존,
  CP, 0x628438 복원, hold·hold fn, 원소 10개 모델 비교, **217B 경계**(218·219 바이트 보존), 218B·관전자·LOCAL·Everyone 빌드 오류, 로컬 구역 경고.
- TBL(104): tail·eos 4조합 × 이 PC 3가지(LocalName 포함) × 4 배수가 아닌 주소 — 바이트·잔재, 변수 번호, 상수만, 빈 원소, every+update_if, capacity·번호 오류.
- Template(31): 모든 PC 갱신(관전자 포함), every+update_if, `update_if=fn`(update() 두 번), 상수 틀, SetMissionObjectives 액션.
- **DPL 참조 모델 무작위 차등(576)**: 무작위 구조 24개 × 값 8벌 × {show 보이는 글 = DPL 틀(4.1), 13번째 줄 보이는 글 = DPL Er(4.2),
  TBL(dp 프리셋, eos=False) 바이트 = DPL Tbl(4.3)}. 변형(맨 변수 부호 없음·TBL tail·Er 모델)을 넣으면 각각 실패한다(저장소 밖 확인).
- epScript(64 + 번역 23): 예제 번역 문자열 11, 에뮬레이터(이 PC 4가지 — LOCAL 줄·Humans 줄·Template·13번째 줄·CCMU·TBL), 인게임 맵 에뮬레이션
  (자체 점검 7 / 7, 1,500 사이클, [E6-1]~[E6-10] 줄), euddraft 0.11 빌드 2, 빌드 오류여야 하는 epScript 4(리스트 리터럴·pinned()·LOCAL 13번째 줄·var 에 Part).
- 파이썬 쪽(222): 입력 오류 40여 종, 경고(NUL·줄 길이), max_len, Shown, 문서(3.12), 별칭, `__all__`, eudplib 하위 모듈 import 없음,
  `_WP6b_REQUIRED`, **players.display → display.f_show**(players 쪽 lazy import 경로 — 반환값 Shown, 옵션 전달).
- 참조 모델 `tests/ref_dp.py`(자체 점검 18): DPL 틀(GaugeBar 이중 삽입으로 뒤 원소가 당겨지는 원본 버릇 포함)·Er(print_utf8_2 앞 D 채움·NUL)·
  Tbl(VA/V 목록 무시·U+2009·잔재), eudext 원소 출력·자리 맞춤·이름 캐시 배치, S3 4.2·4.3 예.

**위험**: ① 0x0D 가 폭을 차지하지 않는다는 가정(E6-7 — DPL·eudplib 도 같은 가정). ② 틀이 실제 글보다 길다 → 긴 줄이 218B 줄 버퍼를 넘을 수 있다(E6-9, 빌드 경고).
③ CCMU 트릭·관전자 표시·TBL NUL·이름 두 주소는 인게임 확인 전(E6-1·3·4·5). ④ numfmt 비공개 계약(`_Fmt._emit_buf(nwords, call)`·`_NumFmt._plan()/_spec/_kind`·
`numfmt._plan`·`_name_tail`·`_args`)에 기댄다 — numfmt 판이 바뀌면 시험이 잡는다(7절 D93 요청). ⑤ `every` 시계는 호출 자리마다 4B, pin 칸 72B.
⑥ 이름 캐시는 게임 시작 때 한 번 — 뒤에 SetPName 으로 바꾼 이름은 `cache=True` 에서 안 보인다.

**초안(S3 7절·DESIGN 4.7)과 달라진 점과 이유**
1. **버퍼 = 틀(상수를 굽고 0x0D 자리)** — 초안의 "StringBuffer + `f_cpstr_print`" 는 상수 글자도 실행 중에 복사하는데 eudplib 의 복사가
   **바이트당 약 35 실행**(실측: 8바이트 306, 40바이트 1,498)이라 매 프레임 UI 에 너무 비쌌다. 틀 방식은 상수가 0, 숫자는 numfmt 꼬리가 자리에
   바로 쓴다(맨 변수 1개 실행 70). 대가: 버퍼 바이트 길이가 (자리 − 실제 길이)만큼 길다(DPL 은 V 16B, eudext 12B). CP 를 옮기지 않아 CP 복구도 공짜다.
   StringBuffer(EUDStruct 288B)도 쓰지 않는다. → 7절 D87.
2. 반환값 `dp.Shown`(버퍼 번호·주소·틀·자리 목록)을 더했다(시험·고급용). `dp.max_len(…)` 을 더했다(TBL capacity 계획).
3. `PName(…, cache=True)`·`LocalName(cache=…)`(S3 5.4 의 선택안), `Part.of(값, max_len)`, `Pick(…, missing=)`(epScript `default` 예약어), `Bytes` 는 1~64개.
4. `show` 상수만 경로: 상수·`players.Targets` 대상은 run_as(`players.display` 의 옛 임시 경로와 같은 모양 — t_players 그대로 통과), 변수가 든 목록·값·LOCAL 이면 판정 1회(같은 PC 가 두 번 들어 있어도 한 번) → 7절 D94.
5. `show_line13` 로컬 쓰기에 "이 PC 번호 ≤ 7" 조건을 더했다(변수 대상 값이 128~131 일 때 CCMU 없이 줄만 바뀌는 것을 막음). CCMU 는 변수 대상 ≤ 7 일 때만.
   `players.Humans` 같은 Targets 는 `players.each` 로 돈다(관전자가 들면 빌드 오류 — 원본과 같음).
6. `Byte` 값 0 → 0x0D(원본은 NUL 이라 뒤 글이 사라졌다), `PName` 변수 p ≥ 8 → 빈 글(원본은 이전 내용) → D88·D89.
7. `set_tbl` 기본 tail 은 S3 의 U+2009(DESIGN 초안 표기 `" "` 는 U+2009 가 공백으로 옮겨진 것) → D95. `tail=false` 를 None 과 같게(epScript).
   반환값 = 최대 쓰기 길이.
8. `Template` 은 문자열을 처음 쓸 때 넣는다(전역 const·맵 다시 불러오기 대응). 속성 `string_id`·`addr`·`content`·`size`·`slots`.
9. `pinned` 는 파이썬 with 전용, epScript 는 `begin_pinned()/end_pinned()`(3.11 규칙). `dp.pinned()` 를 epScript 에서 부르면(→ `f_pinned`) 빌드 오류로 안내.
10. `update_if` 에 조건 목록·변수·`fn()` 을 받는다. Template 은 update() 마다 조건을 복사해 쓴다(같은 조건 객체를 두 트리거에 두지 않게).

**S3 정정**(명세 문서는 이 WP 의 수정 범위 밖 — 합칠 때 반영)
1. 7.3 `PName` 최대 길이 "1+26" → 색 1 + 이름 칸 25(0x57EEE0 구조체 +11, 36B 끝까지). 자리는 28.
2. 10-8 의 결정 번호 D13/D14/D15 는 DESIGN 7절의 D15(이름 주소)/D16(TBL NUL)/D17(부호)이다.
3. 7.2 `tail=" "` 의 글자는 U+2009 다(DESIGN 4.7 초안에는 보통 공백으로 옮겨져 있다).
4. 7.1-2 "호출 자리마다 버퍼 한 개(StringBuffer)… f_cpstr_print" → 틀 방식(위 1). 9-6·9-7 의 StringBuffer 주의는 display 에는 해당 없음.
5. 5.7·7.3 `Pick(index, table, default="")` — epScript 에서는 `missing=`.
6. 8.2-5 "0x628438 ← 0, CreateUnit, 복원" 은 eudplib `f_raise_CCMU` 가 0x628438 이 이미 0 이면 저장·복원 액션을 끄는 모양까지 포함한다(에뮬레이터 확인).

#### 4.7.1 `strdesign` — 컴파일 시점 색 문자열 꾸미기 — **WP6a 완료**

**명세(정본)**: `docs/spec/S7_strdesign.md`(규칙 3절, 기대값 5절, API 6절). 이 소절은 구현 결과다. S7 에서 틀린 곳은 아래 "S7 정정"에 적었다.

**근거**: `StrDesign`/`StrDesignX`/`StrDesignX2` 9맵 899회(`..` 뒤 호출 포함, S7 4.1) + `StrD[1]`/`StrD[2]` 96회. 원본 정의 6개 파일
(`MapSource/Library/LibraryFor322.lua:66~74`, `theSeed/Engine/func.lua:17~30`, `Stella_II/Engine/func.lua:11~24`, `MSF-Template/func.lua:11~24`,
`MSF_Respect_V/func.lua:7~20`, `MSF_Memory_2/func.lua:4~15`) — 사용자 작업 폴더의 최신 파일도 스냅숏과 정의가 같다(2026-09-17 확인).
DPS 이식판(e7efff2)에는 같은 코드가 없어 새로 짰다.

**API**

```python
from eudext import strdesign as sd

sd.set_style("seed")        # 맵 설정 맨 앞에서 한 번. "mcf" | "seed" | "respect" | "memory" | sd.Style(...). 반환: Style
                            # (None = 지우기, 시험용). 기본 판이 없다 — 판 없이 design() 을 부르면 EudextError
sd.get_style()              # 지금 판 또는 None
sd.design(text, style=None, center=False, lead=True, right=False)   # = [lead] + ["\x13" | "\x12"] + pre + text + post
sd.design_x(text, style=None, lead=True)                            # center=True (StrDesignX). lead=False = memory 판 StrDesignX2
sd.parts(style=None)        # (pre, post) — StrD[1], StrD[2]. 모든 판에서 돌려준다(원본은 seed/respect 에만)
sd.wrap(*items, style=None, center=False, lead=True, right=False)   # [머리, *items, 꼬리] — display 원소 목록용.
                            # 머리 = lead + 정렬 + pre 를 한 문자열로 합친다. items 는 그대로(실행 중 값 가능)
sd.lua_tostring(x)          # Lua 5.4 `..` 의 숫자 표기 (옮기기용)
sd.Style(pre, post, lead="", name=None)   # 불변 값 객체: .pre .post .lead .name .parts() .design(…). 같음 = (pre, post, lead)
sd.STYLES                   # {"mcf", "seed", "respect", "memory"} → Style (읽기 전용)
sd.MAP_STYLES               # 맵 이름 → 판 이름 (참고 표: DPS_Enhance·MSF_UE_RE·MSF_Breeze·MSF_GaLaXy.2_R·MSF_Memory → mcf,
                            #   theSeed·Stella_II·MSF-Template → seed, MSF_Respect_V → respect, MSF_Memory_2 → memory)
sd.CENTER, sd.RIGHT         # "\x13", "\x12"
# 모듈 함수(epScript sd.design(…) → sd.f_design(…)): f_set_style, f_get_style, f_design, f_design_x, f_parts, f_wrap, f_lua_tostring
# 파이썬 별칭: set_style, get_style, design, design_x, parts, wrap, lua_tostring (= f_ 함수)
# CtrigAsm 이름(원래 의미 — 숫자는 lua_tostring 으로 받는다): StrDesign(s, style=None), StrDesignX(…), StrDesignX2(…)
```

epScript (번역·빌드 실측):

```js
import eudext.strdesign as sd;
const style = sd.set_style("seed");          // 전역에서는 선언만 되므로 const 에 받는다 (import 때 바로 실행된다)
const title = sd.design("보스 등장");          // 전역 const = 파이썬 str (0.81 `_CGFW` 가 즉시 계산)
const pp = sd.parts();                       // pp[0], pp[1] 로 쓴다
function show(n) {
    printAll(title);
    DisplayText(sd.design_x("가운데", style="memory", lead=false));   // 키워드 인자·true/false 번역됨
    printAll("{}남은 적 {}{}", pp[0], n, pp[1]);                      // 실행 중 값을 장식 사이에
}
```

**판** (S7 1절, 바이트는 시험으로 확인)

| 이름 | 쓰는 맵 | pre | post | lead | 늘어나는 길이(StrDesign / X / X2) |
|---|---|---|---|---|---|
| `mcf` | DPS, UE_RE, Breeze, G2R, Mem1 | `07 E3 80 8E 20` | `20 07 E3 80 8F` | — | +10 / +11 |
| `seed` | theSeed, Stella_II, Template | `08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20` | `20 1C E3 80 82 0F 2B 18 2E 08 CB 9A` | — | +25 / +26 |
| `respect` | Respect_V | `07 …`(seed 와 첫 색만 다름) | `… 07 CB 9A`(끝 색만 다름) | — | +25 / +26 |
| `memory` | Memory_2 | `07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20` | `20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7` | `0D 0D` | **+30 / +31 / +29** |

**의미·알고리즘**
- 순수 파이썬 문자열 연결. 트리거·eudplib 객체를 만들지 않는다(CP·로컬 무관). `str` 을 넣으면 `str`, `bytes`(`bytearray`)를 넣으면 `bytes`(판 장식은 UTF-8).
  eudplib `DisplayText(str)` 은 UTF-8 로 인코딩하므로 맵 문자열 표의 바이트가 원본 Lua 결과와 같다(에뮬레이터로 확인).
- 입력: `str`/`bytes` 만. `int`·`float` 는 `EudextError`("f-문자열이나 `sd.lua_tostring`") — 파이썬 `str(1/3)` 이 Lua 와 조용히 달라서.
  `None`·`bool`·eudplib 객체·목록도 오류(원본도 오류, 실행 중 값은 `wrap`/`parts` 로). 플래그(`center`/`lead`/`right`)는 True/False/0/1 만, `center`·`right` 함께는 오류.
- 입력에 `\x00` 이 있으면 `EPWarning`(원본과 같게 결과는 그대로. 맵 문자열 표는 NUL 에서 끝나 뒤 장식까지 안 보인다 — 에뮬레이터 실측).
  `\n` 이 있으면 장식은 첫 줄 앞·끝 줄 뒤에만, `\x13` 이 이미 있어도 그대로(원본과 같음).
- 판 상태: 모듈 전역 하나. **판을 지정하지 않은 호출이 나온 뒤 `set_style()` 로 다른 판으로 바꾸면 `EPWarning`**(원본의 "맵 판이 나중에 덮어써 앞 호출만 Library 판을 받는" 사고를 알림, S7 2절).
  같은 판을 다시 정하거나 `style=` 로만 쓴 호출 뒤에는 경고하지 않는다. 한 프로세스에서 여러 맵을 빌드하면 판이 남으므로 맵마다 `set_style()` 을 부른다(빌드 리셋에 등록하지 않았다 — epScript 전역 `const` 는 import 때 한 번만 실행되므로 리셋하면 다음 빌드에서 판이 사라진다).
- `lua_tostring`: Lua 5.4 `lobject.c` `tostringbuff` 그대로 — 정수(−2⁶³~2⁶³−1) `%d`, 실수 `"%.14g"` 뒤 `-0123456789` 만으로 된 모양이면 `.0`
  (`100.0`, `-0.0`, `1e+15`, `1.2345678901234e+14`). inf·nan·범위 밖 정수·bool·None 은 오류(원본은 `inf` 를 찍지만 옮길 코드의 버그일 가능성이 커서 막았다).
- 새 맵 템플릿: `sd.set_style()` 을 **맵 설정 파일 맨 앞**에서 부른다. 원본의 "Library 먼저 불러오고 맵 판이 전역 함수를 덮어씀" 구조를 없앤다. 공용 코드(라이브러리)는 판을 가정하지 않고 `design()` 에 맡긴다.
- display 와의 관계(WP6b 에 넘김): 원본 `{"\x13"..StrD[1], PName(i), "…"..StrD[2]}` → `dp.show(t, *sd.wrap(PName(i), "…", center=True))`.
  epScript 에는 펼치기가 없으니 display 는 **원소 자리에 파이썬 목록이 오면 펼치는 것**을 권장한다(`dp.show(t, sd.wrap(…))`). 원본의 `"\x12"..StrD[1]`(Stella_II 6회)은 `right=True`.

**비용** (2026-09-17, `docs/COSTS.md` "strdesign (WP6a)"): `design`/`design_x`/`wrap`/`parts`/별칭 모두 호출 자리 0 · 실행 0 · 페이로드 0.
참고: `DoActions(DisplayText(sd.design(…)))` 는 DisplayText 액션 트리거 1개(1 / 1, 약 167B/벌) — strdesign 몫은 0, 장식 문자열은 맵 STR 에 들어간다. 3.8 목표 초과 없음.

**시험**: `tests/t_strdesign.py` 1,779 판정 (+ 참조 `tests/ref_strdesign.py`)
- S7 5절 기대값 **156건**(6개 파일 × 함수판 13 × 입력 12): 문자열은 `design`·`design(bytes)`·`design_x`·별칭·`set_style` 뒤 별칭·`Style.design` 이 모두 같은 바이트,
  숫자는 `design` 오류 + `design(lua_tostring(x))`·별칭이 같은 바이트, nil·true 는 `design`·별칭 모두 오류. 고정 기대값이 S7 문서 표(5.1~5.4 의 25행)·1절 바이트 표·길이·파이썬 참조와 같은지.
- **lupa 차등 1,000건**: 원본 파일 6개에서 `StrD`·`function StrDesign…end` 원문을 뽑아 lupa `lua54`(`encoding=None`)로 실행, 무작위 입력 1,000개(str 70%·bytes 15%·실수·정수 — 색 코드 전부·한글·전각·이모지·`\n`·`\r\r!H`·`\x00`·잘못된 UTF-8)
  × 함수판 13 = 13,000 비교, 고정 기대값 = 원본 재실행, `StrD` = `parts()`(seed/respect), mcf·memory 에는 `StrD` 없음, `"\x13"..StrD[1]..X..StrD[2]` = `StrDesignX(X)`.
  `lua_tostring` 무작위 3,000개(64비트 정수, 무작위 비트 실수, 1e13~1e17 정수값, ±0, 아주 작은 수 …)를 Lua `"" .. x` 와 비교.
- API 119 판정(docstring 3.12 항목·순수 파이썬 검사 포함, 판 없음 오류·안내문, 판 바꿈 경고 조건 4가지, `\x00` 경고, 입력·플래그 오류, `right`, lead 는 memory 판에만 영향, `wrap`, `Style` 불변·같음·해시·복사·pickle, `STYLES` 읽기 전용, `f_` 별칭, 트리거 0).
- 에뮬레이터 333 판정: 고정 기대값 중 문자열 결과 130개 + 무작위 200개를 `DisplayText` 로 찍어 맵 문자열 표 바이트가 원본 Lua 결과와 같은지(NUL 에서 끊김 포함, 실행 트리거 = 액션 묶음 수).
- epScript 72 판정: 예제(`examples/strdesign_example.eps`)·인게임 맵 번역 문자열 17개, 짧은 모양(`const s = sd.design("x");` + `printAll`), 짝 없는 `)` 함정 4모양,
  예제 에뮬레이터(찍힌 6줄 = 원본 Lua, `\r\r!H` 표식과 4바이트가 다름), 인게임 맵 1,441 사이클(쪽 시작 사이클, 22줄 × 2바퀴 = 원본 Lua, 줄 ≤ 218B), euddraft 0.11 빌드 2개(판 바꿈 경고 없음).
- 변형 시험(저장소 밖 사본): `lua_tostring` 음수 규칙, respect 끝 색, StrDesignX 의 lead 누락을 넣으면 각각 실패한다.

**위험**: 없음(바이트가 원본과 같다). 인게임 확인은 권장만(D6-1~5 — 판별 모양·색, `\r\r` 뒤 `\x13` 가운데 정렬, `\x13` 두 번, `\x12` 오른쪽 정렬, 줄바꿈). 원본 맵의 실제 STRx 산출물과는 대조하지 않았다(S7 9-4, TEP 경로).

**초안(S7 6절)과 달라진 점**
1. `design` 인자를 키워드 전용(`*`)이 아니라 DESIGN 4.7 초안대로 위치 인자도 받게 했다(`design(text, style, center, lead, right)`).
2. `right=False`(`\x12` 오른쪽 정렬)를 더했다 — Stella_II 가 `"\x12"..StrD[1]` 로 6회 직접 쓴다. `wrap` 도 같다.
3. `wrap` 은 `[lead, "\x13"?, pre, *items, post]` 대신 **머리를 한 문자열로 합친** `[lead+정렬+pre, *items, post]` 를 돌려준다(원소 수를 줄임, 이어 붙인 결과는 같다). `style`·`lead`·`right` 키워드도 받는다.
4. CtrigAsm 이름 별칭(`StrDesign`/`StrDesignX`/`StrDesignX2`)은 `design` 과 같은 함수가 아니라 **숫자를 `lua_tostring` 으로 바꿔 받는** 얇은 함수다(원래 의미, 3.1). `design` 은 S7 대로 숫자를 거부한다. `StrDesignX2` 별칭을 더했다. → 7절 D34.
5. `get_style()`, `set_style(None)`(지우기), `MAP_STYLES`, `CENTER`/`RIGHT`, `Style.design()` 을 더했다. `set_style` 은 Style 을 돌려준다(epScript 전역 `const` 로 받기 위해).
6. `\x00` 경고는 호출마다 낸다(원본과 결과는 같게 둠).
7. 기대값 JSON(`tests/data/strdesign_expected.json`) 대신 `tests/ref_strdesign.py` 의 `EXPECTED` 표(원본 Lua 재실행으로 만든 고정값, 시험이 재실행 결과와 같은지도 본다) — Windows 쪽 `s7_lupa_out.json` 은 이 저장소에 없다.

**S7 정정** (명세 문서는 이 WP 의 수정 범위 밖이라 여기 적는다 — 합칠 때 S7 에도 반영)
1. 1절 바이트 표 "늘어나는 길이" `memory` 의 StrDesign **+32 → +30**, X **+33 → +31**(X2 +29 는 맞다). 5.4 기대값 16진을 세면 30·31 바이트다. 이 값은 DESIGN 에 없고 `strdesign` docstring·위 표는 고친 값으로 적었다.
2. 6절 `lua_tostring` 설명 "정수값이고 |x|<1e16 이면 `%d.0`" 은 틀린 곳이 있다: Lua 는 `1e15` → `1e+15`, `123456789012345.0` → `1.2345678901234e+14`, `-0.0` → `-0.0`(설명대로면 `1000000000000000.0`·`123456789012345.0`·`0.0`).
   맞는 규칙은 "`%.14g` 로 쓰고 `-0123456789` 만으로 된 모양이면 `.0`"(Lua 5.4 `tostringbuff`). 3,000개 차등으로 확인.
3. 6절 옮기기 예 `dp.show(players.Humans, *sd.wrap("\x13", hero_name, "\x04을(를) 처치! ", pts, center=False))` 는 `\x13` 이 pre 뒤로 가서 원본과 다르다 →
   `dp.show(players.Humans, *sd.wrap(hero_name, "\x04을(를) \x07처치하였습니다! \x1F＋ ", pts, " \x1FＰｔｓ", center=True))`(Stella_II `MapLogic/System.lua:1691`).
4. 5절 "구현 시험은 이 JSON 을 `tests/data/strdesign_expected.json` 으로 옮겨 쓴다" → `tests/ref_strdesign.py` `EXPECTED`(위 7).
5. 9-3(`\x00` 이후를 안 그리는지): eudplib 맵 문자열 표에 NUL 이 든 문자열을 넣으면 표에서 NUL 에서 끝난다(에뮬레이터 문자열 표 해독) — SC 가 C 문자열로 읽으므로 인게임 확인이 필요 없다.

---

### 4.8 `textfx`, `chat` — 글자 효과와 채팅 줄 — **WP17 완료**

**명세(정본)**: `docs/spec/S6_chat.md` 1절·4.1·4.2. API 는 S6 4절이 정본이고, 아래 "S6 와 달라진 점" 만 다르다.
구현 `eudext/textfx.py`, `eudext/chat.py`, 채팅 버퍼 모델 `eudext/testing/chatmodel.py`(scmodel 대신 — 배치 E 에서 scmodel 은 WP11 몫),
시험 `tests/t_textfx.py`(1,613 판정)·`tests/t_chat.py`(557 판정), 예제 `examples/textfx_example.{eps,eds}`·`chat_example.{eps,eds}`,
인게임 확인 맵 `examples/chat_ingame.{eps,eds}`, `_compat.py` 끝 WP17 블록(`cpchar_addstr_epd`, `cpchar_color_var` — 시험 전용),
비용 `docs/COSTS.md` "textfx (WP17)"·"chat (WP17)".

**근거**: 채팅 효과 블록(`CD__ScanChat` + `CDPrint(…, "HTextEff")`)이 5맵에 복붙(원본 보관소 HStr2·HStr4 트리거 648개 ≈ 1.49MiB),
표식 문자열 `"\x0D\x0D!H"` 가 문구 표에 수백 번. 관전자 채팅 블록(4맵)은 WP19 `misc.ObserverChat` 이 이 타자기를 쓴다.
`CA__MoveXY`·`ConvertColor`·`ConvertLetter` 는 0회(설계만).

**셀 배치**(S6 1.7): 셀 = dword, `[C][b0][b1][b2]`(C = 색, 빈 바이트 0x0D).
1바이트 글자 CtrigAsm `[C][D][D][c]` 대 eudplib `[C][c][D][D]`, 2바이트 `[C][D][b0][b1]` 대 `[C][b0][b1][D]`, 3바이트 같음.
표식 셀 `MARK_U200B = 0x8B80E20D`, 빈칸 `BLANK = 0x0D0D0D0D` 는 두 배치 공통. eudext 는 eudplib 배치만 쓴다.

**API**

```python
from eudext import textfx as tfx, chat, players

tfx.cell_const(ch, color=None); tfx.cell_const_ctrig(ch, color=None)     # 셀 dword (eudplib / 옛 CtrigAsm 배치)
tfx.BLANK, tfx.MARK_U200B, tfx.CELL_NEWLINE, tfx.CELL_UNKNOWN, tfx.COLOR_CODES, tfx.RULES, tfx.is_marker_cell(v)
tfx.scan_const(data, max_cells=52, rule="ctrig", skip_odd_head=False) -> ScanResult(cells, extra)   # 컴파일 시점 참조판
n = tfx.f_scan_cells(src_ptr, dst_epd, max_cells, rule="ctrig", skip_odd_head=False)              # 런타임 (로컬 분기 안)
n = tfx.f_scan_cells_epd(src_epd, dst_epd, max_cells, src_sub=0, rule="ctrig", skip_odd_head=False) # EPD 판 (주소 나누기 없음)
tfx.warn_outside_local(what)          # 로컬 메모리를 읽는 함수가 구역 밖이면 빌드 경고 (chat 도 씀)

chat.f_line_ptr(slot); chat.f_line_epd(slot)       # 상수 slot → int, 변수 → EUDVariable. 상수판 line_ptr/line_epd/line_cell_addr(slot, i)
chat.line_active(slot)                             # local.LocalCondition (첫 바이트 ≠ 0, 홀수 slot 은 −2 주소 마스크 0xFF0000)
chat.f_slot_of_row(row)                            # (row + [0x640B58]) % 11 — 로컬 값
chat.CHAT_BUF, CHAT_EPD, NEXT_LINE_ADDR, LINE_BYTES(218), LINES(11), CELLS_PER_LINE(54), ARCHIVE_CELLS(52), DEFAULT_MARKER
tw = chat.Typewriter(marker=b"\r\r!H", targets=players.Everyone, speed=1, erase=None, sound=None,
                     nul_cell=True, rule="ctrig", enable=None, every=None)
tw.tick()                    # 매 프레임 한 번 — 안에서 contains_user(targets) ∧ enable 로 갈라 11줄 처리
tw.mark(text)                # marker + text, 줄바꿈 뒤마다 marker (끝 줄바꿈 뒤는 뺌). str/bytes 그대로
tw.archive, tw.rem_vars, tw.lag_vars, tw.timer     # 보관소 Db(11·52·4), 칸별 남은 일·아직 안 옮긴 셀 수, every 시계
```

epScript(번역·에뮬레이터·euddraft 빌드 확인): `const tw = chat.Typewriter(speed=1);` … `tw.tick();`,
`DoActions(DisplayTextAll(tw.mark("\x13\x04…")));`, `local.begin(); const n = tfx.scan_cells(0x640B60, EPD(buf), 52); local.end();`,
`if (chat.line_active(3))`(→ `f_line_active`), `chat.slot_of_row(0)`.

**스캐너 규칙**(`rule`, textfx 모듈 docstring 이 정본)
- `"ctrig"`: CtrigAsm `CD__ScanChat` 공용 본문(v5.5.lua:87607~88980)을 읽어 정리한 규칙 + 2바이트 수정. 색 코드(0x01~08, 0x0E~11, 0x14~1F)는
  "그 색을 만났을 때의 출력 칸" 의 C 로(그 뒤 첫 글자·줄바꿈을 쓴 다음 덮음 — 보통은 다음 글자 셀, 색과 글자 사이에 0x0D×4 빈칸이 끼면 그 빈칸),
  연속 색은 마지막 것. 색 + 0x0D×3 = 색 있는 빈칸 셀. 0x0D 는 4개 연속일 때만 BLANK, 아니면 1바이트 건너뜀. 0x0A 는 셀(뒤가 NUL 이거나
  한도 마지막 칸이면 쓰지 않고 한도만 줄임 — 대기 색은 반환 수 뒤 칸 C 에). 그 밖 ≤0x7F 는 1바이트, 0xC0~DF 는 **2바이트(원본 버그 수정)**,
  0xF0↑ 는 4바이트를 먹고 `'?'`, 0x80~BF·0xE0~EF 는 3바이트(원본과 같음). 글자 머리 NUL 에서 멈춤. 뒤 바이트가 NUL 이면 멈춤(원본은 넘어 읽음).
- `"eudplib"`: `_cpchar_addstr` 묶음(≤0x7F 모두 1바이트 — 색·0x0D·0x0A 도 셀, 0x80~DF 2바이트, 0xE0↑ 3바이트). C 는 0x0D(eudplib 은 `color_v`, 기본 2).
- 한도(`max_cells`)는 셀(글자·빈칸·줄바꿈)마다 1. `skip_odd_head` = 첫 0x0D 0x0D 건너뛰기(원본 SkipInit 의 홀수 줄 동작).

**스캐너 알고리즘**(EUDFunc 1벌/규칙·옵션): 앞보기 창 q0..q3(값 = 바이트 × 0x01010101 — 마스크 SetTo 한 번으로 셀 어느 칸에든 넣는다, 원본 FCHAT[4] 방법).
새 바이트는 CP = 원문 dword, 칸(`sub`)에 맞춰 비트 조건 8개의 마스크를 고친 뒤 `DeathsX(CurrentPlayer, AtLeast, 1, 0, bit)` 로 읽는다
(eudplib readtable 방식, 칸 분기 4). 셀은 쓰기 트리거 하나(마스크 SetTo 액션 5개)가 쓰고, 목적지 칸은 Add 1 로 따라간다.
바이트 소비는 do-while(끝 트리거가 참이면 자기 next 를 머리로 고치고 머리가 되돌림). CP 는 끝에서 `f_setcurpl2cpcache()`(3.6 잠깐 옮기기).
마스크 Add/Subtract 는 쓰지 않는다(A-1 인게임 전).

**타자기 동작**(S6 1.2, 모두 로컬): 이 PC 가 대상이고 enable 이 참인 프레임마다 slot 0..10:
① 진행 중(남은 일 ≥ 1)이고 셀 0 이 표식이면 → 줄이 떠 있을 때 드러내기: 아직 안 옮긴 셀을 보관소에서 줄로(셀 i+1 ← 보관 i), 차례(`every`)면
   `sound` 확인(셀 k 가 빈칸·공백이 아닐 때 `PlayWAVAll` + CP 복구) 뒤 k += min(speed, 52 − k). **쓰고 나서 늘린다**(원본 순서).
② 아니면 진행 상태를 0 으로, 원문 앞 바이트가 marker 와 같으면(상수 MemoryX 조건 — 홀수 slot 도 바이트 단위) 변환:
   보관 줄 = 빈칸 52 → 스캔(최대 52) → 앞 `erase` 칸 빈칸 → 줄 = 표식 + 빈칸 52 + 셀 53 NUL, k = 0. 변환 프레임에는 드러내지 않는다.
③ `nul_cell` 이면 11줄 셀 53 = 0(원본 부수효과). 상태: 칸마다 `rem`(= 52 − k + lag) · `lag`(= k − 옮긴 셀 수) EUDVariable 두 개.

**구현 구조**(본문 77): 칸마다 트리거 4개를 펼친다 — A(조건 rem ≥ 1 ∧ 셀 0 표식 → 자기 next = R), B(rem = 0), C(원문 표식 →
칸 상수·rem/lag 초기값을 싣고 자기 next = 변환 루틴, 루틴 끝의 next = 다음 칸), R(흐름 밖, 조건 줄 떠 있음 → 칸 상수·로더 준비 → 드러내기 루틴).
조건 트리거가 자기 next 를 고쳐 갈라지는 것은 eudplib `EUDBranch` 원리이고, 프레임 첫 트리거가 A·C·R 의 next 와 칸 변수 사슬을 되돌린다.
드러내기 루틴은 칸 변수를 **로더**(칸 변수 트리거의 dest 를 루틴 변수로, next 사슬로 이어 실행 — eudplib `VProc` 과 같은 필드)로 읽고
끝에서 되돌려 쓴다. 칸마다의 준비는 상수 액션뿐이다. 보관 셀 하나 옮기기 = `f_dwread_epd` + `f_dwwrite_epd`(약 40).
빈칸 채우기는 모든 타자기가 공유하는 루프(`_blank_run`, CP 를 바꿔 가며 SetDeaths(CurrentPlayer)) — 64액션 트리거 대신(페이로드 −8KB/개).

**원본과 다른 점**
- 스테이징 셀·마스크(CDPrint)가 없다 — 이 PC 에서만 돌므로 채팅 버퍼에 직접 쓴다.
- 원본은 드러내는 줄의 셀 1..52 를 매 프레임 다시 썼다. eudext 는 **새로 드러낼 셀만** 쓴다(보관소가 트리거가 아니라 Db 라 셀 하나 옮기는 데 약 40).
  다른 코드가 그 줄의 셀을 고치면 원본은 되살리고 eudext 는 두지 않는다(7절 D49). 다 드러낸 줄은 더 보지 않는다(화면 같음).
- U+2008 표식 경로·이름 줄(HCheck 4~6)은 넣지 않았다(도달 0 / 실험 코드).
- UERE 소리는 `RotatePlayer(PlayWAVX, HumanPlayers)` 대신 로컬 분기 안 `PlayWAVAll`(이 PC 만). `every` 시계는 원본 `TC`(SubCD → TalkTimer)와 같은 순서.
- 한 맵에 Typewriter 는 하나만 동시에 돈다(둘이면 서로의 표식 줄을 자기 줄로 볼 수 있다 — 원본도 블록 하나). `enable` 로 배타면 된다(인게임 맵).

**S6 와 달라진 점**
- `erase` 기본값 `None` = "표식만 스캔한 셀 수": 기본 표식·`"ctrig"` 이면 2(원본과 같음), `"eudplib"` 이면 4 — S6 1.7 함정(eudplib 묶음에서는
  `\r\r` 도 셀이 되어 `!H` 가 셀 2·3 으로 밀림)을 기본값에서 막는다(7절 D50). 정수를 주면 그대로.
- `enable` 은 조건 외에 EUDVariable·EUDLightVariable·EUDLightBool·"조건을 돌려주는 함수"도 받는다. 조건 객체는 한 번만 쓸 수 있어
  `tick()` 을 두 번 부르면 EudextError(함수로 넘기면 된다).
- `speed` 는 상수 1~52 또는 EUDVariable, `every` 는 상수 ≥ 1 또는 EUDVariable(S6 "또는 every=N" 을 둘 다 받게).
- marker 검사: 3~16바이트, NUL 없음, 변환한 줄의 표식 셀(0D E2 80 8x)과 겹치면(짝수 +0, 홀수 +2) 오류 — 같은 줄을 매 프레임 다시 변환하는 것을 막는다
  (원본의 "셀 0 이 U+200x 가 아니면 변환" 조건을 컴파일 시점 검사로 옮김). 타자기는 `skip_odd_head` 를 쓰지 않는다(기본 표식에서 결과 같음).
- 추가: `f_scan_cells_epd`(EPD 판), `scan_const`/`ScanResult`(컴파일 시점 참조판 — 시험 기대값·상수 문구 미리 계산), `is_marker_cell`,
  `CELL_NEWLINE`·`CELL_UNKNOWN`·`COLOR_CODES`·`RULES`, `warn_outside_local`, `line_ptr`/`line_epd`/`line_cell_addr`(상수판), `f_line_active`(epScript 별칭),
  Typewriter 속성 `archive`·`rem_vars`·`lag_vars`·`timer`, `tw.f_mark`·`tw.f_tick` 별칭, `chat.DEFAULT_MARKER`(WP19 가 참조).
- `line_active` 는 `local.LocalCondition` 을 돌려준다(구역 밖 경고). `f_scan_cells`·`f_slot_of_row` 도 구역 밖이면 경고(3.7). `f_line_ptr/epd` 는 계산만이라 경고 없음.
- 채팅 버퍼 모델은 `testing/scmodel.py` 대신 `testing/chatmodel.py`(4.8 초안 "scmodel 에 추가" 대신 — 배치 E 소유 규칙).
- 셀 53 NUL: `nul_cell=False` 여도 **변환한 줄**의 셀 53 은 한 번 쓴다(원문 꼬리가 빈칸 뒤로 비치지 않게).

**비용**(2026-09-17 실측, docs/COSTS.md): 스캐너 본문 94(ctrig)·45(eudplib)·주소 나누기 38, 실행 = 빈 원문 101 + 원문 바이트당 약 16 + 글자당 약 10
(ASCII 글자당 26, 한글 64 — 목표 "글자당 약 6" 초과: 바이트마다 비트 8개 읽기 + 칸 분기 4 + 창 밀기 4. 표식 줄이 새로 뜰 때 한 번뿐).
타자기 본문 77(sound·every 변수판 93) + 공유 빈칸 루프 7 — 목표 "약 60" 초과: 칸 판정을 11번 펼쳐 실행을 줄였다(실행 루프로 돌리면 프레임당 약 200).
실행: 빈 프레임 39(= 11 × 3 + 6, 목표 안), 드러내는 줄마다 +65, 변환 프레임 약 980(16글자). 페이로드: 첫 타자기 +67KB(스캐너 포함, scx +6.5KB),
둘째부터 +38KB(scx +3.6KB). eudplib 0.81 페이로드의 트리거 크기는 액션 수에 거의 비례한다(3.8 보충).

**시험**: `t_textfx.py` — 셀 상수 두 배치(S6 5.1-1 + 조합 표), 참조 스캐너 기대값(S6 4.1 예·5.1-2 목록·색/빈칸/줄바꿈 경계),
런타임 스캐너 차등(두 규칙 × 고정 24줄 × 칸 0~3 × 한도 2종 + 무작위 750 + skip 100 + 주소 변수판 80 + 상수 주소 4칸 + 주소식),
eudplib `_cpchar_addstr` 대조 124, CP 보존, 구역 밖 경고, 빌드 오류 4, 예제 번역·에뮬레이터·euddraft.
`t_chat.py` — 주소·EPD(slot 0~15), line_active(상수·변수, 홀수 첫 바이트), slot_of_row(0x640B58 0~10 × row 0~21),
타자기 6설정 × 무작위 160프레임 × 3 + enable·함수 enable·관전자 PC 를 **원본 참조 모델(`chatmodel.TypewriterRef`, 매 프레임 셀 1..52 다시 쓰기)과
프레임마다 11줄 바이트 비교**, S6 5.1-3 개별(변환 프레임, 드러내기 순서, 홀수 +2 정렬, 바이트 표식 비교, 꺼짐·재개·새 줄, 사용자 채팅 덮기,
nul_cell 짝 212/홀 214, 소리 빈칸·공백, DisplayText 여러 줄, CP 보존, 대상 밖), 경고·빌드 오류, 채팅 모델 자체 21,
예제·인게임 맵 번역·에뮬레이터(1,250프레임)·euddraft 빌드.

**인게임**: `docs/INGAME_CHECKLIST.md` D17-1~9(필수 D17-1·2·4·6), 확인 맵 `examples/chat_ingame.eds`.

**위험·미정**: 0x0D 폭·가운데 정렬 모양(D17-1), 셀 53 NUL 이 모든 줄을 212/214 에서 자름(원본과 같음, `nul_cell=False` 검토), 줄 표시 시간 저장 위치 미확인(D17-8),
사용자 채팅 줄 바이트 배치 미확인(D17-6), 한 맵 여러 타자기, 다른 코드가 드러내는 줄의 셀을 고치는 경우(D49), SC:R 줄 넘김(폭)으로 한 문구가
여러 줄이 되면 둘째 줄은 표식이 없어 원문 그대로(원본과 같음).
`convert_color`·`reveal`·`blit`·`convert_letter`(D.5 스케치)는 사용 0 이라 만들지 않았다 — 요청 시.

---

### 4.9 `players` — 대상 목록과 플레이어별 액션 — **WP8 완료**

**근거**: `RotatePlayer` 783, `DisplayTextX`/`PlayWAVX` 1,994, 원시 CP `0x6509B0` 1,670, 플레이어 수만큼 배열 494, `HumanCheck`/`LocalPlayerID` 371(R1 1-c).
구현 `eudext/players.py`, 시험 `tests/t_players.py`(726 판정), 예제 `examples/players_example.{eps,eds}`·`players_plugin.py`, 비용 `docs/COSTS.md` "players (WP8)".

**API**

```python
from eudext import players as pl

pl.humans()                      # 컴파일 시점 사람 슬롯 목록 (맵 OWNR) → for p in pl.humans(): 펼침
pl.force_members(n)              # 컴파일 시점 Force n 목록 (맵 FORC, Unused 슬롯 제외)
pl.set_table(humans=, forces=)   # 위 두 표를 맵 대신 직접 (TEP SetForces 표 옮기기). 인자 없이 = 맵으로
pl.Humans                        # 런타임 대상: humans() 중 지금 형 바이트 == 2 인 슬롯
pl.Observers                     # CP 128~131 (P9~P12 도 관전자로 읽는다)
pl.Everyone                      # Humans + Observers
pl.Force(n), pl.All              # 컴파일 시점 표 (eudplib Force1~4·AllPlayers 도 받는다)
pl.Allies(p)                     # p 가 동맹으로 둔 플레이어(자신 제외) — 런타임 동맹 표 0x58D634, p 는 상수
pl.Targets(*원소), 대상 | 대상    # 대상 섞기. 목록(list/tuple)도 대상이다. 원소: 0~7, 128~131, P1~P12,
                                 #   CurrentPlayer, AllPlayers, Force1~4, EUDVariable, 위 상수들
pl.contains_user(targets)        # 로컬 조건: 이 PC(관전자 포함)가 대상에 드는가 (display 가 씀)
with pl.each(targets) as p:      # 런타임 반복(본문 1벌). CP = p(캐시 포함), 끝에서 CP 복구, break/continue 됨
for p in pl.each(targets): ...   # 같은 것 (epScript `foreach(p : pl.each(T))`). 관전자는 observers=True 일 때만
pl.run_as(targets, *actions)     # 대상마다 CP 를 옮겨 같은 액션 (RotatePlayer 대체). 상수 대상은 한 트리거
pl.display(targets, *parts, **kw) # = display.show (WP6). WP6 전에는 문자열만 → run_as(DisplayText)
pl.play_wav(targets, wav)        # = run_as(targets, PlayWAV(wav))
pl.is_human(p) / pl.human_mask() # 형 바이트 == 2 (Enable_HumanCheck 재사용). p 는 상수·변수
pl.PerPlayer(T, *args, count=8, by_player=False)   # 8칸 객체 모음 (CreateVarArr 대체)
```

**의미·알고리즘**
- **대상 해석**: 원소를 상수 집합 / 조건부(Humans = 형 바이트, Allies = 동맹 바이트) / 변수 / CurrentPlayer 로 나눈다. 같은 상수는 한 번. 변수 원소는 런타임 중복 제거를 하지 않는다(RotatePlayer 와 같음). 상수 표(humans·Force)는 **쓰는 순간** 읽는다(LoadMap·set_table 뒤).
- **`run_as`**: 순서 CurrentPlayer → 조건부 → 변수 → 상수. 상수 원소는 `[CP←p, 액션…]×n` 을 한 트리거에 모아 `f_setcurpl2cpcache(actions=…)`(VProc) 와 합친다 → 호출 1 / 실행 2. 액션이 모두 표시 전용(PlayWAV·DisplayText·CenterView·SetMissionObjectives·MinimapPing·TalkingPortrait·(Un)MuteUnitSpeech)이면 Humans 의 존재 판정을 뺀다. 액션은 원소마다 복사하고, `fn(p)` 를 주면 원소마다 부른다.
- **CP**: `run_as` 는 CP 를 원시 `SetMemory(0x6509B0, SetTo, p)` 로 **잠깐** 옮기고 같은 호출 끝에서 `f_setcurpl2cpcache()` 로 되돌린다(R3 1.5-1 의 "잠깐 옮겨 쓰기", eudplib `DisplayTextAll`·`f_dwread_epd` 와 같은 방식). 3.6-3 이 막는 "원시 액션으로 CP 를 바꾼 채 두기"와 다르다. 사용자 액션 안의 CP 쓰기는 오류(run_as 가 CP 를 관리). `each` 는 본문 동안 `SetCurrentPlayer`(캐시 포함)로 p 를 두고, 들어올 때의 **eudplib CP 캐시 값**으로 되돌린다(f_getcurpl 보다 실행 5 적음, run_as 와 같은 규약 — 캐시가 낡은 상태에서도 두 함수 모두 캐시 값 기준, 시험 `ra_nocache`/`each_nocache`).
- **관전자**: 관전자 CP(128~131)에는 표시 전용 액션과 CurrentPlayer 가 아닌 SetDeaths/SetMemory 만 허용(그 밖은 EPError). `each` 는 기본으로 관전자를 막는다(p 로 배열 색인·CP 액션을 하면 위험).
- **`contains_user`**: 이 PC 번호 u 는 eudplib `f_getuserplayerid()`(0x512684 바이트). 값은 0~7·128~131 만 나온다고 본다.
  - 상수 집합: 한 원소 → `u == p`. `lo ≤ (u & m) ≤ hi` 로 가려지면(컴파일 시점에 마스크 255개 탐색) 조건 1~2개 — 예: 사람 0~6 + 관전자 = `(u & 7) ≤ 6`. 그 밖(예: 사람 0·2·3·4·6·7 + 관전자)은 게임 시작 때 `EUDOnStart` 로 한 번 만든 "이 PC 비트"(EUDLightVariable, 1 << 자리)에 마스크 조건 1개. 12개 번호의 부분집합 4,095개 중 마스크 구간으로 되는 것 147개.
  - Humans 의 존재 판정은 뺀다(이 PC 는 늘 게임에 있다). 변수·CurrentPlayer(`IsUserCP`)·Allies 가 섞이면 부분마다 트리거 1개로 1비트 깃발(`EUDLightBool`)을 채워 그 조건을 돌려준다.
  - 결과는 로컬 조건이다(3.7). WP13 `local` 의 `LocalCondition` 표식이 생기면 감싸는 것을 검토.
- **`each`**: 디스패처 사슬 + 본문 1벌. 원소마다 디스패처 트리거 하나가 `pv ← p`, `SetCurrentPlayer(p)`, "본문 끝 트리거의 next ← 다음 디스패처" 를 하고 본문으로 뛴다. 조건부 원소는 eudplib `EUDBranch` 와 같은 **자기 next 고치기**로 트리거 1개(들어올 때 한꺼번에 되돌림 — 비정상 탈출 뒤에도 안전). 루프 블록(`contpoint`/`loopend`)을 등록해 `EUDContinue`/`EUDBreak` 가 된다. 본문 밖으로 점프(EUDReturn)하면 CP 를 되돌리지 않는다.
- **`PerPlayer`**: 상수 번호는 원소 그대로(트리거 0). 변수 번호는 `get/set/iadditem/isubitem/switch`(EUDSwitch). `pp[변수]` 는 오류 — epScript `pp[p] = x` 가 `_ARRW` 경로에서 임시 값에 쓰이는 것을 막는다(`pp[p] += x` 는 `iadditem` 으로 된다). 뺄셈은 wrap(`_parts.isub32`).

**설계와 달라진 점 (이유)**
1. `pl.Humans` = "humans() 중 **형 바이트 == 2**"(Enable_HumanCheck). 초안의 `EUDPlayerLoop + f_playerexist` 는 컴퓨터도 참이고 관전자를 못 돈다.
2. `each` 는 `EUDPlayerLoop` 감싸기가 아니라 자체 디스패처(관전자·Force·변수·CurrentPlayer·Allies 를 받고, 원소당 실행 2). p 는 `TrgPlayer.cast(변수)`(0.81 scdata, `p.ore` 등).
3. `run_as(targets, *actions)` — 액션을 여러 인자로도 받는다(epScript 에서 목록 리터럴이 EUDArray 가 되는 문제 회피). epScript 목록은 `list(P1, P2)`(→ FlattenList), `Targets` 는 `dont_flatten`.
4. 추가: `set_table`(TEP `SetForces` 표 옮기기, S3 9-3 위험 대응), `force_members`, `Targets`, `ALL_IDS`/`OBSERVER_IDS`/`LOCAL_ONLY_ACTS`.
5. `P9`~`P12`(8~11)는 관전자 128~131 로 읽는다(S3 7.6, CtrigAsm `PlayerConvertX`). 중립 플레이어(P12) 뜻으로는 쓸 수 없다.
6. `Everyone` = Humans + Observers(4.9 초안). S3 T6 의 `EveryPlayers`(AllPlayers + 관전자)와는 컴퓨터 슬롯이 다르다 — 표시 액션에서는 같다.
7. `Force(n)` 은 컴파일 시점 표만(런타임 판정 없음, SC Force 와 같게 컴퓨터 포함, Unused 슬롯 제외).
8. `Allies(p)` 는 자신 제외, 한 방향(p 의 동맹 표), p 는 상수만.
9. `display` 임시 경로: `eudext.display` 가 없으면 문자열 원소만 `run_as(DisplayText)` 로 띄운다(옵션·다른 원소는 "WP6 이후" 오류). WP6 이 들어오면 늘 `display.f_show` 로 넘긴다.
   (WP6b 뒤) 늘 `display.f_show` 로 넘어간다(시험 확인).
10. `PerPlayer(T)` 는 형식·팩토리 일반 도우미(Int64 전). 변수 번호 읽기는 EUDVariable 원소만.

**비용**(docs/COSTS.md "players (WP8)", 2026-09-16): run_as 상수 = 호출 1 / 실행 2, Humans 조건부 6명 = 7 / 8, 변수 1명 = 3 / 5. contains_user 상수 = 호출 0 / 실행 0(비트 마스크형은 시작 때 한 번 12트리거·3.1KB), 섞임(변수+관전자+CP) = 5 / 6~7. each = 고정 실행 7 + 원소당 2(+본문). is_human 변수 = 본문 11 / 호출 1 / 실행 15. human_mask = 11 / 1 / 14. PerPlayer 변수 번호 get = 15 / 10.
**시험**: CP 복구(모든 run_as·each 변형, 낡은 캐시 포함), 대상 조합(상수·변수·Force·목록·관전자·Allies·CurrentPlayer), `contains_user` × 이 PC 번호 12가지(0~7, 관전자 128~131) × 대상 60종(무작위 부분집합 30 포함), 마스크 구간 계획 4,095 부분집합 전수, 사람 판정(형 바이트 8종), run_as 대상별 액션·순서·64 초과 나눔·변수 필드 패치, each 안 CP·break/continue·중첩·존재 변화 연속 사이클, PerPlayer, 컴파일 오류 22종, epScript 번역·단독·euddraft 빌드.
**위험**: 관전자 번호(0x512684 = 128~131)와 CP 128~131 표시, 원시 CP 여러 번 바꾸기(한 트리거), 형 바이트의 나감 표시, 동맹 표 주소는 인게임 확인 대기(`docs/INGAME_CHECKLIST.md`). u 가 0~7·128~131 밖이면 마스크 구간 조건은 뜻이 정해지지 않는다(비트 마스크형은 거짓).

---

### 4.10 `units` — 방금 만든 유닛, 유닛별 저장 — **WP10 완료**

> **2026-09-18 인게임 사실 두 가지** (에뮬레이터 모델 `testing/scmodel.py` 와 다르다 — 모델은 그대로 두고 확인 맵의
> 판정을 방향에 안 기대게 바꿨다):
> 1. **빈 유닛 칸 목록은 칸 번호가 줄어드는 쪽으로 간다.** 미리 놓인 65기(맵 리빌러 64 + 파이어뱃)가 1699부터 내려가며
>    차지해 첫 머리(0x628438)가 **1635** 였고, 마린 한 기를 만들면 1634 가 됐다. 골리앗(본체 + 터렛)은 −2, 마린 3기는
>    −3. `capture`·`bullet` 의 성공 판정은 "머리가 바뀌었나" 뿐이라 영향이 없지만, **칸 번호 산술을 "+1" 로 가정하면
>    안 된다**(터렛은 idx − 1). 모델은 늘어나는 쪽이라 확인 맵은 절대값(`stepAbs`)으로 본다.
> 2. **미리 놓인 맵 리빌러는 `new_units()` 순회에 나오지 않는다.** 칸은 차지하는데(머리 1635) 첫 프레임 순회가 낸 것은
>    파이어뱃 + 그 프레임에 만든 마린 = 2 뿐이었다. 리빌러·스캐너 스윕류가 활성 목록(0x628430) 밖 목록에 있거나
>    고유 바이트가 0 이기 때문으로 보인다(둘 중 무엇인지는 아직 못 가렸다). 모델은 66 을 내므로 기대를 2~68 로 뒀다.

**근거**: `0x628438` 10맵 311(그중 `f_Read` 136), EXCC 8맵 361, `MoveCp` 345(R1). EXCC 대체는 `EUDArray` 방식이 용량·실행 모두 유리(R2 1.8: VarBlock +11.5KB vs EUDArray +0.66KB). 이식판(DPS `eudplib-port` a7aad90) `eud/ctrig/excc.py` 는 VarBlock·Lua 전역 구조라 가져오지 않고 구조만 참고했다(칸 번호 산술·CP 가정은 호환 쪽 문제).

**API**

```python
from eudext import units

with units.capture() as u:            # = units.Capture(); u.begin() … u.end()  (epScript 는 begin/end)
    data.clear(u.index_before)        # 생성 전에 알 수 있는 칸 번호 → on_create 훅 (S1 11-6)
    DoActions(CreateUnit(1, unit, loc, owner))
u.ptr, u.epd, u.index                 # 0x628438 에서 읽은 첫 유닛 (index == index_before)
u.ok, u.failed                        # 조건: 0x628438 이 바뀌었나 (읽을 때마다 새 조건)
u.cunit                               # CUnit.cast(u.epd, ptr=u.ptr)
u = units.create(1, unit, loc, owner, props=None, on_create=data | [data…] | fn(index), into=None)
ptr, epd, i = units.next_slot()       # 다음 빈 칸 (없으면 0, 0, NO_INDEX) — bullet·spawn 부품

data = units.UnitData(hp2="dword", stack="word", flags=("byte", 3))   # (형, 기본값) 도 된다. 필드 60개까지
data.hp2[i]  data.hp2[i] = v          # word/byte 는 값 폭(쓸 때 아래 비트만 남김, 읽기도 폭만큼)
data.hp2.iadd(i, v)  .isub(i, v)      # wrap   (epScript `+=`, `-=` → iadditem / isubitem)
data.hp2.isub_sat(i, v)               # 포화   (isubtractitem 별칭)
data.flags.iand(i, 상수)  .ior(i, 상수)
data.hp2.eq/ne/le/ge/lt/gt(i, v)      # 조건 (epScript `data.hp2[i] == v` → eqitem …)
data.of(epd | ptr | CUnit | Capture | UnitRef).stack   # 행 뷰(UnitRow): 읽기·쓰기·iaddattr·eqattr·isub_sat
data.at(i)                            # 칸 번호로 행 뷰
data.clear(i)                         # 한 행을 기본값으로
data.fields, data.field(name), data.nbytes
# 칸 번호 자리에는 int(0~1700)·EUDVariable·Capture·UnitRef·CUnit 을 넣을 수 있다.

units.index(epd_or_ptr)               # 칸 번호 (변수: 11비트 뺄셈 사슬, 범위 밖은 NO_INDEX. 상수: 틀리면 빌드 오류)
units.slot(i)                         # (ptr, epd)
units.NO_INDEX                        # 1700 — 빈 칸 없음·잘못된 값. UnitData 는 1701칸이라 이 칸에 써도 안전(버리는 칸)

for nu in units.new_units(allowance=2, clear=data):   # EUDLoopNewUnit + 칸 번호. UnitRef(ptr, epd, index, cunit)
    ...                                               # `for ptr, epd, i in …` 로 풀어도 된다
units.clear_on_death(*datas, key=None, chunk=20)      # 주문(+0x4D) 0 인 칸의 행을 기본값으로 (EXCC ResetFlag 대체)
for d in units.dying(*datas, key="alive", chunk=20, limit=None):   # 죽는 중 + key ≠ 0 인 칸마다 한 번, 끝에 행 초기화
    ...                                               # (EXCC 죽은 유닛 인식 단락 DUnitCalc 대체)
units.CUnit                           # eudplib CUnit 다시 내보냄 (MoveCp 관용 → 멤버 이름 접근)
```

epScript 는 모듈 함수에 `f_` 가 붙는다(`units.create` → `units.f_create`, `units.new_units` → `units.f_new_units`). `Capture`·`UnitData`·`CUnit` 은 대문자라 그대로. 객체는 `const` 로 묶는다. 번역·에뮬레이터·euddraft 빌드 확인: `examples/units_example.eps`.

**의미·알고리즘**
- 0x628438 읽기: 변수로 복사하지 않고 조건 11개의 문턱값을 고쳐 가며 이진 탐색(`[0x628438] ≥ 0x59CCA8 + 336·(찾은 칸 + 2^k)`, 참이면 아래 문턱값에 336·2^k 더함). 포인터·EPD·칸 번호가 한 번에 나온다. 공유 EUDFunc 1벌(반환 변수에 바로 씀 — `_compat.predefine_returns`).
- 생성 판정: `end()` 가 `Memory(0x628438, Exactly, ptr)` 조건의 비교값을 ptr 로 패치하고 1비트에 기록. 한 블록에서 여러 마리면 ptr 은 첫 유닛, ok 는 "하나라도". 빈 칸이 없으면 ptr = epd = 0, index = NO_INDEX — **ok 전에는 epd 를 쓰지 않는다**(EPD 0 = P1 마린 데스 칸).
- 칸 번호(변수): 포인터·EPD 를 값 범위로 가리고 11비트 뺄셈 사슬(나눗셈 없음).
- UnitData: 필드마다 1701칸 dword 를 한 `Db` 에 이어 둔다(필드 k 칸 i 의 EPD = 시작 + k·1701 + i). 필드 객체는 `ExprProxy` 를 상속한다 — epScript `arr[i] = v` 번역(`_ARRW.__lshift__`)은 대상이 ExprProxy 가 아니면 **읽은 값에 대입해 쓰기가 사라진다**.
  word/byte 연산은 CP 를 칸으로 잠깐 옮겨 `Add` 뒤 `SetDeathsX(CP, SetTo, 0, 0, ~폭)`(마스크 SetTo 만 사용 — 마스크 Add/Subtract 식은 쓰지 않는다, 3.5-8), 끝에 `f_setcurpl2cpcache`. dword 는 eudplib `iset` 과 같은 dest 패치.
- clear_on_death / dying: 1700칸을 chunk(1700 의 약수) 칸씩 도는 날(raw) 순회. 칸 트리거 chunk 개(조건: `+0x4C` 마스크 0xFF00 == 0 [+ key ≥ 1]) → 패치 증가 트리거 → 끝 검사 1(next 는 시작 때 되돌림). dying 은 1단계에서 걸린 칸 번호를 대기열(1700칸)에 모으고 2단계에서 하나씩 내주며, 반복 끝(continue 지점)에서 행을 지운다(본문에서 모든 필드를 읽을 수 있다). EUDBreak 는 쓰지 않는다(그 칸도 남아 다음 사이클에 다시 나온다) — 처리량 제한은 `limit`.
- 주문 0 은 죽는 중인 유닛과 빈 칸(한 번도 안 쓴 칸 포함)이다. 죽은 칸이 순회보다 먼저 재사용되면 지우지 못하므로 생성 쪽(`capture` + `data.clear(u.index_before)` 또는 `new_units(clear=data)`)에서도 막는다. 단 `new_units(clear=)` 는 새 유닛을 처음 볼 때 칸을 지우므로 capture 의 on_create·같은 사이클 앞쪽에서 쓴 값도 지운다(값은 순회 뒤에 쓴다).
- `dying()` 과 `clear_on_death()` 를 **같은 표**에 쓰지 않는다 — clear_on_death 가 죽는 칸의 key 를 먼저 지워 알림이 사라진다(limit 로 남긴 칸 포함). 확인용 맵은 표를 둘로 나눴다.
- new_units: eudplib 규칙 그대로(활성 목록 0x628430 을 앞에서부터, 고유 바이트 +0xA5 를 그림자 표와 비교, 이미 본 유닛 allowance 개에서 멈춤 — 새 유닛은 목록 두 번째 자리에 들어간다는 전제). 실행 시점: 순회를 둔 자리. 앞 사이클 트리거 뒤 ~ 이번 사이클 이 자리 앞에 생긴 유닛이 나오고, 이 자리 뒤에서 만든 유닛은 다음 사이클에 나온다.

**비용** (docs/COSTS.md `units (WP10)`): capture 전체 실행 24(본문 14 1벌), index 19(본문 30), 변수 칸 쓰기 3~5, 읽기 dword 38 / word 22 / byte 14, clear 4(필드 수 무관), new_units 새 유닛당 약 66, clear_on_death 1,957/사이클(chunk 20), dying 1,874 + 걸린 칸당 약 60. scx: UnitData 1700×6 +약 480B(목표 < 1KB 충족), new_units 첫 순회 +약 6.9KB(eudplib `EUDLoopNewUnit` 자체 6.2KB — 571KB 0 표의 섹터 압축분이 대부분).

**시험**: `tests/t_units.py` (3,261 판정, 약 7초) — capture(성공·실패 주입·빈 칸 없음·터렛·여러 마리·CP 보존·로케이션 중심·props), index/slot 차등, 필드 set/iadd/isub/isub_sat/비트/조건 × dword·word·byte 차등(표 전체 영역 검사 포함), 행 뷰, clear, new_units(모델 참조 구현과 차등, 칸 재사용, 12마리), clear_on_death·dying(chunk 1/17/20/50, key, limit, break/continue), 유닛 액션 모델, epScript 예제·인게임 확인 맵의 번역·에뮬레이션(모델 위 55 사이클)·euddraft 빌드, scx 증가분(`--scx`).
**인게임**: `docs/INGAME_CHECKLIST.md` 배치 B 의 B10-* (생성 실패 시 ok, index_before 가 실제 칸인지, 터렛, new_units 실행 시점·두 번째 자리 삽입, 죽은 칸 반환 위치, 고유 바이트 증가, 순회 실행량 체감).
**위험**: 모델 가정(삽입 위치·죽은 칸 반환·터렛 순서)이 인게임과 다르면 new_units·dying 시험 기대값을 고친다. `dying`/`clear_on_death` 는 매 사이클 약 2,000 실행 — 부담되면 몇 프레임에 한 번 부르고, 재사용 대비는 생성 쪽 초기화로 한다.

**초안과 달라진 점과 이유**
- `capture()` 와 함께 `Capture` 클래스의 `begin()`/`end()`: epScript 에 `with` 가 없다. `create()`(한 줄 판, S1 spawn_one 모양)와 `next_slot()`(bullet·spawn 이 쓰는 부품, S4 5.2)을 더했다.
- `u.index` 와 `u.index_before` 는 같은 변수다(생성 전에 읽으므로 둘 다 "만들어질 칸").
- `NO_INDEX`(1700)와 필드당 버리는 칸 1개: 빈 칸이 없을 때 on_create 훅(`data.clear(u.index_before)`)이 표 밖을 쓰지 않게. 변수 `index()` 도 범위 밖 값을 NO_INDEX 로 돌려 `data.of(잘못된 epd)` 가 안전하다.
- UnitData 저장: 초안 "필드마다 EUDArray(1700)" 대신 필드를 한 `Db` 에 이어 둠(칸당 4B·압축 크기 같음). 행 초기화가 CP 한 번 + 필드당 액션 2개로 필드 수와 무관하게 실행 4. `(형, 기본값)` 은 EXCC ResetFlag 표(값 지정) 대체. EUDArray 를 그대로 감싸지 않은 이유: eudplib 포인터 배열 모드(`_use_ptr_array`)에서 `EUDArray(_from=EPD)` 의 뜻이 바뀐다.
- `data.of()` 는 EPD 뿐 아니라 포인터·CUnit·Capture·UnitRef 도 받고, 칸 번호로 바로 여는 `data.at(i)` 를 더했다.
- `new_units()` 는 `UnitRef` 를 내준다(`nu.ptr/epd/index/cunit`, 풀어 쓰기 가능). `clear=` 로 새 유닛 칸 초기화(재사용 대비).
- `clear_on_death(*datas, key=None, chunk=20)`: 초안은 "죽은 유닛 칸 초기화 루프" 한 줄이었다. 원본 EXCC 는 죽은 유닛 인식(주문 0) 때 행 전체를 리셋했으므로(theSeed CunitSystem.lua:329, ResetFlag) 같은 판정을 1700칸 묶음 순회로 한다.
- **`dying(*datas, key, chunk, limit)` 추가**: EXCC 죽은 유닛 인식 단락(DUnitCalc — 처치 보상·사망 알림)이 맵마다 있다. key(살아 있을 때 찍는 표식, 예: `new_units` 에서 `data.alive[nu.index] = 1`)로 한 번만 알리고 끝에 행을 지운다. 1700칸을 칸마다 도는 eudplib 식 순회(칸당 4~5 실행, 사이클 약 8,000)보다 묶음 순회 + 대기열이 싸다(1,874 + 걸린 칸당 60).
- `new_units()` 는 초안대로 `EUDLoopNewUnit` 을 감쌌다(인게임 검증된 판정). 대신 첫 순회에 scx 약 7KB(eudplib 571KB 그림자 표의 섹터 압축분이 약 4.4KB)가 든다. 칸당 1바이트 그림자 표(메모리 6.8KB)로 직접 짜면 약 5KB 줄일 수 있다 — **결정 요청(7절 D21)**: 사용자가 원하면 WP 후속으로 `new_units(shadow="compact")` 를 만든다(판정 규칙은 eudplib 과 같게, 인게임 B10-5 확인 뒤).

---

### 4.11 `pool` — 오브젝트 풀 (건물 스택·TStruct 대체) — **WP11 완료**

**근거**: `Gun_Line`/`Gun_SetLine` 4맵 2,298회, TStruct 2맵 58(R1). 건물 하나의 기록 칸을 줄 번호로 조건·대입하고(`Gun_Line(5, Exactly, 0)`), 매 프레임 살아 있는 슬롯마다 공통 처리를 한다(`Install_GunStack`: 슬롯 수만큼 트리거 → 용량 큼).
구현 `eudext/pool.py`, 시험 `tests/t_pool.py`(1,590 판정)·`tests/ref_pool.py`(참조 모델), 예제 `examples/pool_example.{eps,eds}`, 인게임 확인 맵 `examples/pool_ingame.{eps,eds}`, `_compat.py` 끝 WP11 블록(`check_pool`, `custom_varray`, `chk_string_section_name`), `testing/scmodel.py` 글·소리 기록 모델, 비용 `docs/COSTS.md` "pool (WP11)".

**명세(정본)**: `docs/spec/S2_pool.md` — API 는 S2 6절이 정본이고, 아래 "S2 와 달라진 점" 만 다르다.

**원본 구조**(S2 0·2·3절): 건물 스택과 TStruct 는 같은 기계다. 슬롯 하나 = CtrigAsm 트리거 하나, 필드 k = 액션 k 의 값 칸. 매 프레임 슬롯마다 조건 트리거가 돌고, 참이면 필드를 레지스터에 한꺼번에 싣고 공유 본체를 부른 뒤 되쓴다. 모든 맵에 공통인 줄은 0·1·2(유닛·X·Y)와 54(반납 표시)뿐이다. `Gun_Line` 은 0부터, `TSLine` 은 1부터 센다. **`Suspend`/`Gun_DoSuspend` 는 일시 정지가 아니라 반납**이다.

**API** (S2 6.2~6.10)

```python
from eudext.pool import Pool, Field

guns = Pool("Gun",
    fields=[Field("unit", readonly=True), Field("x", readonly=True), Field("y", readonly=True),
            "owner", "timer", "phase", Field("dir", signed=True), "done", "gunid"],   # 또는 "unit! x! y! owner timer …"
    capacity=36,
    aliases={0: "unit", 1: "x", 2: "y", 4: "owner", 7: "timer"}, alias_base=0,   # 옛 줄 번호 (없으면 필드 순서)
    on_full="report", on_unknown="report", writeback="accessed", debug=False,
    index=False)                                  # True: 번호를 사슬에 실어 g.index 가 공짜 (레코드당 72B·방문당 1 더)

h = guns.alloc(unit=epd, x=x, y=y, gunid=3)      # 핸들 EUDVariable, 0 = 넘침 (dropped += 1, on_full)
hs = guns.alloc_n(3, unit=u)                     # 원자적으로 3개 (모자라면 모두 0, dropped += 1 한 번) — spawn 층
for g in guns.each():                            # 살아 있는 것만, 할당 순서. 루프 중 free·alloc 안전
    g.timer += 16                                # g.x = 레지스터 EUDVariable. -= 는 wrap, 포화는 g.isub_sat("timer", v)
    guns.dispatch("gunid", {3: boss_a, 4: boss_b})   # EUDSwitch + 기본 가지 = on_unknown (문구 + 반납)
    if EUDIf()(g.done >= 1):
        guns.free_current()                      # 원본 Gun_DoSuspend (= 반납). 두 번 불러도 한 번
    EUDEndIf()
for g, h in guns.each(handle=True): ...          # (보기, 핸들 레지스터)
@guns.case(131, 132)                             # dispatch 가 쓸 등록 (중복이면 컴파일 오류 = GCase_Duplicated)
def hatchery(g): ...
guns.Line(5, Exactly, 0); guns.LineRange(8, 100, 200)      # 옛 줄 번호 조건 (signed 필드는 부호 있는 비교)
guns.SetLine(7, Add, 1); guns.SetLine(11, Subtract, 1)     # 바로 실행. Subtract 는 원본처럼 포화
guns.SetLineAct(7, Add, 1); guns.line(8)                   # 액션판 / 레지스터
guns.count; guns.dropped; guns.full()            # 논리 개수(Actived_Gun), 넘침 누적, 빈 칸 없음 조건
guns.free(h); guns.is_alive(h); guns.index_of(h) # 방문 밖 (h 가 방문 중 레코드면 free = free_current)
guns.get(h, "timer"); guns.set(h, "timer", 0)    # 느린 경로 (방문 중 레코드면 레지스터)
guns.cur                                         # 레지스터 보기 (each 가 주는 것과 같은 객체)
g.handle; g.index; g.alive; g.touch("name")      # 핸들 레지스터, 번호, 방문 중 생존 1비트, 되쓰기 목록에 넣기
```

epScript (`examples/pool_example.eps`, 번역·에뮬레이터·euddraft 빌드 확인):

```js
import eudext.pool as pool;
const guns = pool.Pool("Gun", "unit! x! y! owner timer started phase work done", capacity=8);
const g = guns.cur;                       // const 로 (var 에 담지 않는다)
function gunSend(u, x, y) { const h = guns.alloc(unit=u, x=x, y=y); if (h == 0) { … } }
function afterTriggerExec() {
    foreach (_ : guns.each()) {
        if (guns.Line(5, Exactly, 0)) { guns.SetLine(5, SetTo, 1); }
        switch (g.unit) { case 131: …; break; default: guns.free_current(); continue; }
        g.timer += 16;                    // → g.iaddattr. g.x -= v → isubattr(wrap). g.x == v → eqattr(signed 반영)
        if (g.done >= 1) { guns.free_current(); continue; }
    }
    foreach (g2, h : guns.each(handle=true)) { … }
}
```
- 필드는 공백으로 나눈 문자열 하나(`[...]` 는 EUDArray 가 된다). `Field` 를 섞을 때는 `list(pool.Field("dir", signed=true), "w")`.
- epScript `g.x /= v` 는 eudplib `_ATTW.__ifloordiv__` 버그로 안 된다 → `g.x = g.x / v`.

**의미·알고리즘** (S2 6.12 을 구현하며 정한 것)
- **저장**: 레코드 = 72B 변수 원소 E 개의 사슬(E = F+2, `index=True` 면 F+3; `_compat.custom_varray`, eudplib 0.81 `EUDQueue` 기법). 원소 k 는 "레지스터 k ← 값" 한 액션 뒤 원소 k+1 로 간다. 숨은 원소는 `_addr`(레코드 주소, 목록 압축용), (`_index`), `_h`(핸들). **마지막 원소의 next 칸이 생존 표시**다(`T_alive` = 살아 있음, `T_dead` = 반납) → 방문 때 생존 판정 트리거가 없다. 숨은 원소 값은 상수라 alloc 이 쓰지 않는다.
- **핸들 = 마지막 원소 next 칸의 EPD**(0 = 없음, 사용자에게는 불투명한 수). CP 를 핸들에 두면 필드 k 값 칸이 `CP + 18(k−E+1) + 86`, 생존 칸이 `CP` 라 곱셈 없이 CP 연속 쓰기(액션 사이 `CP += 18`)로 필드를 쓰고 되쓴다.
- **살아 있는 목록**: 72B 원소 **2×cap** 개. 원소 i 는 자기 next 칸에 레코드 주소를 쓰는 원소라 뛰어들면 곧바로 그 레코드 사슬로 간다. 순회 포인터는 트리거 C 의 next 칸 하나(적재 뒤 `T_alive`/`T_dead` 가 +72). 목록 끝 판정은 C 의 조건(`[C.next ≥ 끝]`, 끝은 머리에서 채움). 2×cap 인 까닭: 한 프레임 안에서 "앞에서 빠졌지만 자리를 차지한 레코드(≤ cap)" 뒤에 "루프 중 새 레코드(≤ cap)" 가 붙는다. 정리 뒤 길이는 cap 이하.
- **빈 칸 스택**: dword cap 개(번호, 처음 pop 순서 0,1,2…). 꺼낼 때 CP 로 번호의 비트 b 개만 `DeathsX` 로 읽으면서 핸들·주소를 한꺼번에 더한다(곱셈 없음). 넣을 때는 번호가 필요하므로 핸들에서 비트 사슬(b+2)로 구한다(`index=True` 면 레지스터).
- **한 프레임** (호출 자리마다 머리·끝 코드 1벌, 나머지는 풀마다 1벌): 머리(빈 풀이면 끝, 실행 2) → C → L[i] → 사슬 E → `T_alive`(포인터 +72, flag=1, 쓰기 포인터 +1) → 본문 → `T_tail`(flag==0 이면 반납 경로) → 되쓰기(W+4) → (앞에서 빠진 레코드가 있었으면 MOVE: 목록 앞으로 당김 3) → C. 반납·표시된 레코드는 `T_dead`/`FREEP` → `DEAD`(빈 칸 스택에 넣기) → C. "빠진 레코드가 있었나" 는 비교 트리거 없이 **다음 트리거 주소를 바꿔 두는 칸(K 칸)** 으로 기억한다.
- **끝**: 루프 중 alloc 이 있었으면(1비트) 그 레코드들을 본문 없이 한 번 더 훑어 압축(2단계, 반납 표시된 것은 스택으로). C 가 끝으로 갈 때 자기 next(포인터)를 덮으므로 머리에서 목록 끝을 `snap` 변수에도 남겨 두고 2단계가 거기서 다시 시작한다. 빠진 것이 있었으면 목록 끝 = 쓰기 포인터.
- **EUDContinue** = 방문 꼬리(되쓰기). **EUDBreak** = 이번 방문을 마치고 남은 레코드는 본문 없이 정리만(`T_alive` 의 다음을 본문 없는 경로로). S2 는 1단계에서 컴파일 오류로 두었지만, 같은 부품으로 싸게 되어 지원했다(7절 D31).
- **free(h)**: CP ← h, `Memory(0x6509B0, Exactly, 방문 중 핸들)` 이면 방문 중 레코드 → flag 기반(= free_current), 아니면 `[생존 칸 == T_alive]` → `T_dead` 쓰기 + count−1. 빈 칸 스택에는 다음 each 정리 때 들어간다(T2·T5·T9). 이미 반납이면 무시(debug 면 문구). 루프 밖에서는 방문 중 핸들이 0 이라 h = 0 은 아무 일도 하지 않는다. `is_alive` 도 같은 모양.
- **free_current**: `[flag==1] → flag=0, count−1` 한 트리거. 방문 끝에서 되쓰기를 생략하고 생존 칸에 `T_dead` 를 쓴 뒤 스택에 넣는다(같은 프레임 뒤쪽 alloc 이 재사용).
- **alloc**: 공유 핵심(빈 칸 없으면 dropped+1·문구 → 핸들 = 쓰레기 레코드; 있으면 pop·목록 끝에 붙이기·count+1) → 호출 자리의 VProc(`out_h → h → CP`, 변수 값들 → 액션 amount) → CP 상대로 모든 필드 + 생존 칸 쓰기 → CP 되돌림 → `[out_h == 쓰레기] → h = 0`. 넘쳐도 호출 자리 코드가 분기 없이 같게 돌도록 **쓰레기 레코드(TRASH)** 에 쓴다.
- **되쓰기 목록**: 본문을 만드는 동안(each 호출 자리가 열려 있는 동안) 보기 객체로 접근한 쓰기 가능 필드를 **풀 전체에서 합쳐**, 주 함수 생성이 끝난 뒤(`_compat.on_start_after_main`) 되쓰기 코드 1벌을 만든다(모든 호출 자리가 공유). 본문을 epScript 함수로 나눠도 그 함수가 루프 안에서 처음 불리면 잡힌다. 조건만 보는 접근(`Line`, `g.x == v` 의 eqattr)은 목록에 넣지 않는다. 목록이 정해진 뒤 새 필드를 접근하면 컴파일 오류(→ `writeback="all"` 또는 `g.touch`).
- **dispatch**: `EUDSwitch(레지스터)` + 등록 본문 인라인(인자 0개 또는 보기 1개) + 기본 가지. `on_unknown="report"` = 원본 문구 + Buzz ×2 + `free_current()`, `"silent"` = 반납만, 함수 = 그 함수만.
- **옛 줄 번호**: `aliases` 없으면 `alias_base + 필드 순서`. `SetLine(…, Subtract, …)` 은 SC 액션 포화(`_parts.isub_sat32`), `Add` 는 wrap. mask 는 SetTo 만(마스크 Add/Subtract 는 A-1 확인 전). 이름 없는 번호는 컴파일 오류.
- (WP12 확인) (4.11): `alloc_n` 은 넘칠 때 필드를 전혀 쓰지 않는다(분기에서 dropped 만 올림 — 쓰레기 레코드는 `alloc` 한 개 넣기 때만).
- **순회 순서 보장**(WP12 요청): `alloc`/`alloc_n` 은 레코드를 차례로 잡아 살아 있는 목록 끝에 이어 붙이고, `each()` 는 **넣은 순서**로 돈다(압축해도 순서 유지). spawn 이 "다음 층 = 바로 뒤 레코드" 로 이 보장에 기댄다 — 순서를 바꾸는 최적화를 하면 `t_spawn` 이 알려 준다.
- **넘침·미등록 문구**: 원본(MSF_Respect_V `GunData.lua:26, 312`) 문구에서 "f_Gun" → 풀 이름, "G_Send" → "alloc". `players.run_as(players.Everyone, DisplayText, PlayWAV("sound\\Misc\\Buzz.wav") ×3/×2)`.
- **한 프로세스 여러 빌드**: 공유 코드는 빌드마다 새로 만든다(`register_build_reset`). 레지스터·원소 객체는 재사용. EUDFunc 본문(epScript 함수 포함) 안의 each·alloc 은 첫 빌드 공유 코드를 가리키므로 첫 빌드에서만 맞다(문자열 번호 제약과 같다).
- CP 규약(3.6): 안에서 잠깐 옮기고 eudplib CP 캐시 변수 트리거로 되돌린다(`f_setcurpl2cpcache` 와 같은 방식). 호출자 CP 는 바뀌지 않는다.

**비용** (docs/COSTS.md "pool (WP11)", 2026-09-17)

| 항목 | S2 6.13 목표 | 실측 |
|---|---|---|
| 빈 풀 한 프레임 | ≤ 6 | 2 |
| 방문당 고정 | ≤ F+12+2W | F+10+W (W=0 이면 F+6), 레코드가 있는 프레임 고정 8 |
| 압축 이동 1회 | ≤ 6 | 3 |
| alloc | 실행 ≤ 3F+30, 호출 자리 ≤ 4 | b+15+(변수 값 수), 호출 자리 4 |
| free / free_current | ≤ 6 / 1 | 6 (방문 중 레코드 7) / 1 |
| each 호출 자리 | ≤ 40 | 8~12 |
| 저장 | cap×((F+3)×72+76)+(F+3)×72 | 같음 + 쓰레기 레코드 약 72F B |
| Seed (F=13, W=3, 5개) | 약 161 | 153 |
| 유형 분기 26경우 | ≤ log2+3 | 9 (경우 끝 점프 포함) |

풀마다 공유 코드 약 2b+30 트리거(페이로드 약 20~26KB). cap 128·F 16 풀 전체 페이로드 +214KB(원본 432KB), scx +19.6KB.
느린 경로: get 42, set 9, is_alive 9, index_of 13(cap 8).

**시험** (`tests/t_pool.py`, 1,590 판정, 약 5초): S2 7.2 시나리오 T1~T14(참조 모델 `ref_pool.RefPool` 이 먼저 S2 기대값과 맞는지 확인 → 구현이 같은 기대값), 참조 모델과 **무작위 차등 1,450 걸음**(용량 2·4·5·6·7·9, `index=True`, `writeback="all"`, 호출 자리 2개; 조작 = alloc·alloc_n(2/3)·free·get·set·is_alive·index_of·tick; 본문 동작 11가지 — timer+=16, 본문 alloc, 남 free, free_current, 필드 쓰기, EUDContinue, 자기 free(g.handle), is_alive, EUDBreak — 걸음마다 방문 순서·목록·빈 칸 스택·생존·필드·count·dropped 전부 비교), 필드 경계값(상수·변수·음수 상수·같은 변수 세 필드), 뺄셈 의미(-= wrap 0xFFFFFFFE / isub_sat 0 / SetLine Subtract 0 / isubattr wrap, 변수판, 마스크 SetTo), SetLine Add 뒤 Line 참, dispatch(등록·표·기본 가지·default=None·silent·중복 오류·문구와 Buzz 수), each(handle=True)·index_of·g.index·g.alive, 되쓰기 목록(DoActions 로만 쓴 필드 저장·밖에서 꺼낸 레지스터 미저장·touch·writeback="all"·readonly 대입/iaddattr/SetLine 오류·없는 줄 번호 오류), 다른 풀 중첩·같은 풀 중첩 오류, 부호 필드(상수·변수 비교, 별칭, LineRange, epScript 비교 통로), 넘침(report/silent/함수, 누적, **쓰레기 레코드 밖을 안 씀**), 방문 중 레코드의 get·set·is_alive·free·free_current 두 번, Seed 규모 4프레임, 빈 풀 실행 ≤ 6, 방문당 실행 일정, 선언 검사(파이썬), epScript 예제·인게임 맵의 번역·에뮬레이션·euddraft 빌드, 저장 크기(`--storage`).
배치 무작위성(eudplib 페이로드 셔플) 때문에 시험을 6번 반복해 모두 통과했다(아래 "구현 중 찾은 것").

**인게임**: `docs/INGAME_CHECKLIST.md` 배치 C 의 C11-* — **C11-1 [필수] 사슬 적재·되쓰기**, C11-2 넘침 문구, C11-3 방문 중 반납·할당, C11-4 느린 경로, C11-5 128칸 체감, C11-6 부호·포화, C11-7 미등록 문구, C11-8(권장) 멀티 디싱크, C11-9(WP12) spawn 중심. 확인용 맵 `examples/pool_ingame.eds`.

**위험·미정**
- 사슬 저장이 비공개 `_EUDVArrayData` 에 기댄다 → `_compat.check_pool()` 이 모양까지 검사(Pool 생성 때).
- 새로 쓰는 SC 동작 조합: 변수 원소가 **자기 next 칸에** 써서 그 값으로 가는 것, 레코드 마지막 원소 next 칸을 생존 표시로 쓰는 것 — C11-1 로 확인.
- 본문 안의 "게임당 한 번" 구조(EUDExecuteOnce, 보존 안 한 트리거, G_CB PreserveFlag=1)는 풀 전체에서 한 번이 된다(원본과 같은 함정, 검사 못 함 — docstring).
- 풀마다 공유 코드가 약 20~26KB(페이로드) → 풀이 아주 많은 맵이면 공유판 검토(7절 D32).
- 루프 밖 `free` 는 다음 each 정리 전까지 칸을 돌려주지 않는다(T9) → each 를 오래 안 부르면 풀이 마른다.
- 본문에서 같은 풀을 순회하는 EUDFunc 를 부르면 재진입(검사는 each 가 직접 중첩될 때만).
- 넘침 문구의 표시 대상은 `players.Everyone`(사람 + 관전자) — 원본 HumanPlayers(관전자 포함)와 같다.

**S2(초안)와 달라진 점과 이유**
1. **핸들 = 레코드 주소 → 마지막 원소 next 칸의 EPD**: 필드 쓰기·반납·느린 경로가 모두 EPD 가 필요한데 주소 → EPD 는 나눗셈이다. EPD 핸들이면 CP 에 바로 넣는다. 점프에 필요한 주소는 숨은 원소 `_addr` 와 목록 원소가 가진다. 사용자에게는 여전히 불투명한 수(0 = 실패)라 API 는 같다.
2. **숨은 원소 `_self, _index, _alive` → `_addr, _h`(+ `index=True` 면 `_index`)**: 생존은 레지스터가 아니라 마지막 원소의 next 칸(적재가 곧 분기)이라 생존 판정 트리거가 없다. 번호는 방문마다 쓰지 않으므로 기본은 싣지 않고 `g.index` 가 계산한다(실행 약 b+10). 저장 식은 목록이 2×cap 이 되어 S2 식과 같아졌다.
3. **살아 있는 목록 cap → 2×cap**: S2 의사코드대로 끝에 붙이면 한 프레임에 cap 을 넘을 수 있다(무작위 차등에서 발견).
4. **빈 칸 스택 읽기**: EUDArray 변수 색인 읽기(36~38) 대신 번호 비트 b 개만 CP 로 읽으며 핸들·주소를 더한다(b+3).
5. **되쓰기 목록을 호출 자리별 → 풀 전체 합**: epScript 함수로 나눈 본문도 잡고, 되쓰기 코드를 한 벌만 둔다(호출 자리 코드 8~12). 호출 자리마다 접근 필드가 크게 다르면 W 가 조금 커진다.
6. **EUDBreak 지원**(S2: 1단계 컴파일 오류) — 남은 레코드는 본문 없이 정리만(7절 D31).
7. **`is_alive` 반환**: 앞 계산 + 1비트 조건(`[r ≥ 1]`, EUDNot 가능).
8. **`free(h)` 가 방문 중 레코드면 `free_current()` 와 같다**(S2 6.3 "레지스터 `_alive` 도 0" 과 같은 뜻). 방문 중 여부는 CP 에 넣은 h 와 방문 중 핸들 비교로 가른다(비교 앞 계산 없이 실행 6).
9. **`index=True` 선택지 추가**, `pool.cur` 보기에 `g.alive`(EUDLightVariable) — S2 6.3 의 "Condition 용 변수".
10. **넘침 문구 "G_Send" → "alloc"**(7절 D33).
11. `dispatch(…, default=None)` = 기본 가지 없음, 문자열 `"unknown"` = on_unknown(기본).
12. 2단계(찬 필드 `hot=False`, `Field.i64`, `pool.Bag`)는 만들지 않았다(지시대로).

**구현 중 찾은 것** (3절 보탬 후보, 아래 B)
- 넘침용 쓰레기 Db 가 2워드 작았을 때, 페이로드 셔플에 따라 옆 트리거(EUDIf 분기)의 next 를 0 으로 덮어 가끔만 틀렸다 → 쓰레기 크기 18E+100 칸으로 고치고, 시험에 "쓰레기 레코드 밖을 안 씀" 판정과 6회 반복 확인을 넣었다.
- 시험 드라이버에서 `idx = g.index`(함수 결과 = rvalue)를 `self.BEH[idx]` 가 제자리에서 바꿔 뒤의 `ARG[idx]` 가 엉뚱한 칸을 읽었다(eudplib `EPD + rvalue` 는 rvalue 를 고친다). pool 의 `set()` 도 같은 이유로 `h + 오프셋` 을 새 변수에 계산하도록 고쳤다.
- epScript 전역 `const a = [1, 2];` 는 시작 트리거(`_CGFW` 의 EUDOnStart)를 만들어, 한 프로세스의 두 번째 빌드에서 `Reforwarding without reset` 오류가 난다 → 예제는 `EUDArray(list(1, 2))`(초기값 배열, 트리거 없음).
- eudplib `_EUDVArrayData` 두 개가 서로의 주소를 초기값으로 가리키면 수집 단계에서 `deque mutated during iteration` → 사슬과 목록을 한 데이터 객체로 만들었다.

---

### 4.12 `local`, `sync` — 입력 — **WP13 완료**

**근거**: `KeyPress` 4맵 77, 사용자 MSQC 헬퍼 78, 원시 채팅 중 조건 27(R1). 입력값은 전부 로컬 메모리(R4b A1). MSQC/NSQC 플러그인이 동기화한다.
구현 `eudext/local.py`, `eudext/sync.py`, `eudext/tools/edsgen.py`(add_sync·훅), `_compat.py` 끝 WP13 블록(접근자 3개).
시험 `tests/t_local.py`(629)·`tests/t_sync.py`(781)·`tests/t_tools.py`(추가 23), 예제 `examples/sync_example.eps`·`sync_build.py`·`local_example.py`.

**`local`** (표시 전용)

```python
from eudext import local
local.key_held("X", held=True)      # LocalCondition  MemoryX(0x596A18+코드, Exactly, 1, 1)   eds: KeyPress(X)
local.key_pressed("X"); local.key_released("X")   # LocalConditions (조건 2), 캐시는 update() 가 갱신   eds: KeyDown/KeyUp
local.mouse_held("L", held=True); local.mouse_pressed("L"); local.mouse_released("L")   # eds: MousePress/MouseDown/MouseUp
local.typing(); local.not_typing()  # 0x68C144   eds: "0x68C144, AtLeast, 1" / NotTyping
local.is_observer()                 # 0x512684 in 128..131 (조건 2)
local.player()                      # LocalValue, 게임 시작 때 1회 채움 (빌드마다 1개)
local.screen_xy(into=None); local.mouse_screen_xy(into=None); local.mouse_map_xy(into=None)   # (x, y) LocalValue
local.track_mouse(); local.track_screen()        # update() 가 매 사이클 채우는 .x/.y (sync.value 원본으로 쓴다)
local.key_toggle("TAB", guard=local.not_typing())  # 누를 때마다 0/1 (DPS KeyToggleFunc 대체)
with local.only(p): ...             # 파이썬. p = None | 0~11 | 128~131 | 변수 | CurrentPlayer(IsUserCP)
local.begin(p); ...; local.end()    # epScript (with 가 없다)
with local.allow(): ...             # 분기 없이 경고만 끔 (IsUserCP 로 이미 감싼 코드)
local.update()                      # 모든 소비자 뒤 1회. 훅 플러그인이 있으면 아무것도 내지 않음
local.watch_keys(...); local.watch_buttons(...)  # update() 를 먼저 내야 할 때 미리 등록
local.strict(True)                  # 구역 밖 사용을 경고 대신 오류
local.KEYS; local.BUTTONS; local.key_code(k); local.msqc_key_name(k); local.button_bit(b)
local.LocalValue; local.LocalCondition; local.LocalConditions; local.is_local(x); local.in_region()
```

- **키 표**: CtrigAsm v5.5 `ParseKeyName`(196개) = MSQC 0.11 = NSQC 0.9.10.11 `KeyCodeDict`(시험이 세 표를 대조) + NSQC 가이드북 표기 `\`(0xDC). eds 에는 플러그인 표 이름을 쓴다(0xDC → `|`).
- **표식(3.7)**: `LocalCondition` 은 eudplib `Condition` 하위 클래스로, 구역(`only`/`begin`/`allow`) 밖에서 **트리거에 놓이는 순간**(`SetParentTrigger`) 경고한다. `LocalValue` 는 `EUDVariable` 하위 클래스로, 값이 **다른 곳으로 흘러갈 때**(`SetDest` — `shared << lv`, 함수 인자, `lv + 1`, 변수 필드 액션) 경고한다. 경고는 사용자 코드 위치(파일:줄)를 적고 한 곳에 한 번. 한계: `lv + 1` 의 결과에는 표식이 없다. `sync.Bus.value(lv)` 는 플러그인이 메모리를 직접 읽어 경고가 없다.
- **update() 는 즉시 낸다**(지연 본문 없음 — eudplib 0.81 create-payload 콜백이 첫 빌드에서만 불려 쓸 수 없다). 그래서 같은 빌드에서 update() 를 낸 뒤 **처음 쓰는** 키·버튼·토글·추적기는 오류로 막는다(캐시가 갱신되지 않으므로).
- 토글은 마스크 Add 를 쓰지 않는다(3.5-8, 인게임 식 확인 전): 엣지면 +1, 2 면 0 (트리거 2).
- 좌표 마스크: 화면 0x1FFF(256타일), 마우스 X 0x7FF·Y 0x3FF (NSQC 는 0x3FF/0x1FF — SC:R 와이드 여유).

**`sync`** (공유 로직용)

```python
from eudext import sync
bus = sync.Bus("msqc", qc_unit=49, qc_loc=1, qc_player=10, qc_xy=(128, 128), debug=False,
               name="b0", players=None)                       # NSQC: + qc_dummy=227, deaths=200 또는 [..]
jump = bus.key_down("SPACE", guard=sync.not_typing(), level=True)   # Pulse (level=True 면 KeyUp 짝도 선언)
bus.key_up(k); bus.key_press(k); bus.mouse_down("L", level=…); bus.mouse_up(b); bus.mouse_press(b)
bus.when(guard)                                               # guard 조건만으로 펄스
mx = bus.value(local.track_mouse().x, latch=True, guard=None) # Value — 원본 = 주소(int) 또는 선언 때 만든 변수
wide = bus.dword(0x6CDDC4, error=0xFFFFFFFF)                  # NSQC 전용
cur = bus.mouse_location("MouseP1")                           # 이름 또는 1부터 번호. cur.location(p)
bus.raw(key, value); bus.scrdb_channels()                     # 원문 줄 / SCR_DB 8채널
jump.pulse(p); jump.count(p); jump.level(p); jump.level_value(p)   # p = 0~7 | 변수 | CurrentPlayer
mx.received(p)  # = mx.pulse(p);   mx.get(p) (걸쇠);   mx.raw(p)
# guard: sync.not_typing(), key_held(k), mouse_held(b), memory_guard(addr, "Exactly", v), bit_guard(addr, bits),
#        raw_guard('Switch("Switch 210", Cleared)'), flag_guard(var), mouse_moved()/screen_moved()/wide_screen() (NSQC),
#        local.* 조건(.eds 가 있는 것), 문자열, 목록. epScript 는 sync.guards(a, b) (리스트 리터럴은 EUDArray 로 번역된다)
sync.update()                    # 걸쇠·레벨 갱신: 플러그인 수신 뒤, 소비자 앞 (훅이 있으면 아무것도 내지 않음)
sync.verify()                    # euddraft 안: [MSQC]/[NSQC] 설정 = 선언인지 (update·훅이 부른다)
sync.collect("main.eps", map_path=…)   # 빌드 스크립트 1단계: 선언만 실행 → [Bus]
bus.eds_lines(); bus.eds_fragment(); bus.write_eds_fragment(path); bus.describe(map_size, humans)
sync.eds_sections(buses); sync.eds_fragment(buses); sync.write_eds_fragment(path)
sync.hook_source(); sync.write_hook(path); sync.buses(); sync.scrdb_msqc_lines()
# 상수(단일 출처, 4.18 (d)): SCRDB_MSQC_ADDR=0x58F508, SCRDB_MSQC_DEATH=21, SCRDB_MSQC_CHANNELS=8,
#   PNAME_LIGHTVAR_ADDR=0x58F524, IDLE_VALUE, DEFAULT_QC_UNIT=58, NSQC_DUMMY_DEATH=227, TRANSPORTS
```

**핵심 제약**(R4b A7)
- euddraft 는 eds 를 플러그인보다 먼저 읽는다 → **eds 조각은 같은 빌드 안에서 반영되지 않는다.** 빌드 순서 = "선언 수집(`sync.collect`, 트리거 없음) → eds 생성 → euddraft"(5.3).
- 받은 값은 네트워크 턴이 실행된 사이클에만 들어오고 한 턴 안에서는 마지막 값만 남는다 → `latch`, `level` 도우미.
- 자체 전송(`transport="native"`)은 **3단계 선택**(지금은 오류). 같은 줄 문법의 대체 플러그인은 `TRANSPORTS` 에 한 줄(섹션·모듈 이름·기능)을 더해 붙인다 — MapSource `SNQC`(랠리 포인트 채널)는 줄 문법이 MSQC 와 같아 붙일 수 있지만, NSQC 와 같은 0.81 함정(`EUDVArray(8)` 판별, `EUDArray(8)` 키 캐시)을 먼저 고쳐야 한다(WP13 평가).

**초안과 달라진 점과 이유**
1. **`level(p)` 는 선언 때 `level=True`** 가 있어야 한다 — 레벨에는 Up 짝 줄이 eds 에 있어야 하는데, eds 는 빌드 전에 만들므로 `beforeTriggerExec` 안의 `.level()` 호출로는 줄을 더할 수 없다. 짝 없이 부르면 오류. Up 짝 줄에는 guard 를 붙이지 않는다(채팅 중에 떼도 레벨이 풀리게).
2. **레벨 규칙은 "토글" 이 아니라 설정/해제**: Down 만 → 1, Up 만 → 0, 둘 다 → 그대로(짝이 맞으면 원래 상태와 같다). 같은 턴에 엣지를 잃어도(INT 5.1) 다음 엣지에서 회복한다(순수 토글은 한 번 잃으면 계속 뒤집힌다).
3. **`guard=` 는 조건 객체가 아니라 eds 표기**다(플러그인이 보내는 PC 에서 평가). `local.*` 조건은 `.eds` 가 있으면 그대로 받는다.
4. **훅 플러그인** `eudext_sync_hook.py` 를 더했다(`tools/edsgen` 이 eds 옆에 만든다). eds 순서 `[MSQC]` → 훅 → 맵 플러그인이면 onPluginStart 에서 `sync.verify()`, beforeTriggerExec(수신 뒤, 맵 코드 앞)에서 `sync.update()`, afterTriggerExec(역순이라 맵 코드 뒤)에서 `local.update()`(설정 `LocalUpdate : 0` 으로 끔). 맵 코드는 update 를 부르지 않아도 된다(불러도 아무것도 내지 않는다). 훅 없이 쓰면 직접 부르고, level/걸쇠를 쓰는데 update 가 빌드에 없으면 경고(`_compat.on_start_after_main` — WP15 접근자를 `getattr` 로 씀).
5. **`verify()`**(빌드 안): 선언한 줄이 설정에 없거나 값이 다르면, `eudext_` 이름을 쓰는 옛 줄이 남았으면, euddraft 안인데 섹션이 없으면, 선언한 QCUnit 이 맵 UNIT 구역에 놓여 있으면 오류(theSeed QCUnit 58 크래시 사례). "선언을 고치고 eds 를 다시 만들지 않은" 실수를 막는다.
6. **eds 키 이스케이프**: `=`, `:`, `\` 는 `\` 를 붙인다(euddraft readconfig 가 푼다 — 실측 `KeyDown(\=)` → `KeyDown(=)`). `;` 키는 `SEMICOLON` 으로 쓴다(`;` 는 조건 구분자).
7. **출력 칸**
   - MSQC: 이름 붙은 `EUDArray(8)`. 네임스페이스에는 **값이 포인터인 사본**(`_compat.eudarray_ptr_view`)을 등록한다(MSQC 0.11 `array if array._is_epd() else EPD(array)` 가 경고 없이 맞게 읽음). 값 칸 초기값 0xFFFFFFFF(사람 아닌 칸도 "못 받음"). MSQC 의 VArray 출력은 플러그인 내부 클래스(`type(QC_EPDs[0])`)만 맞아 쓸 수 없다.
   - **NSQC(0.9.10.11 판)는 eudplib 0.81 에서 데스값 출력만 된다**(실측): ReceiveQC `parseArray` 가 이름 문자열을 만나면 `isUnproxyInstance(v, EUDVArray(8))` 에서 TypeError(0.81 의 `EUDVArray(8)` 은 타입이 아니고 부를 때마다 다른 것). → `Bus("nsqc", deaths=200)`(그 번호부터) 또는 `deaths=[…]`, 값 원본은 **주소(int)만**, `val` 은 못 받으면 0 이라 `latch`·`received` 없음(→ `dword` 권장). 키 엣지 캐시도 `EUDArray(8)+오프셋//8` 이 0.81 에서 배열 밖에 써서 `key_down`/`key_up` 을 막았다(`allow_nsqc_key_edges=True` 로 풀 수 있음 — 플러그인을 고친 경우). 마우스 엣지는 정상. NSQC 는 번들에 없다(옛 판을 eds 폴더에 둔다).
   - NSQC `QCDummy` 버그: 설정에 QCDummy 가 있으면 **dict 의 마지막 키**를 지운다(onInit 436~437) → QCDummy 줄을 맨 끝에 쓴다.
8. **`qc_loc` 는 1부터 번호만** 받고 eds 에는 0부터로 쓴다. 이름은 받지 않는다(MSQC 는 이름을 `GetLocationIndex`(1부터)로 읽고 숫자는 0부터로 써서 이름이면 한 칸 어긋난다 — 3.9 로케이션 규칙). `qc_unit` 을 주지 않으면 기본 58 과 함께 경고한다.
9. `mouse_location` 의 로케이션 = 첫 로케이션 + p − (가장 작은 사람 번호) (MSQC 326·1119~1120).
10. 여러 Bus 는 전송별로 합친다. 설정이 다르거나 같은 키가 두 번이면 오류.

**비용**(`docs/COSTS.md` "t_local"·"t_sync (WP13 local/sync)"): 펄스·레벨·수신 조건 = 조건 1(if 포함 호출 2 / 실행 1), 변수 p = 호출 4 / 실행 5, CurrentPlayer = 호출 5 / 실행 12, 값 읽기 = 실행 37, update: 레벨 채널당 사람마다 트리거 2(실행 2), 걸쇠 채널당 사람마다 호출 3(받지 않은 사이클 실행 1, 받은 사이클 + 읽기). local: 키 조건 1, 엣지 2 + update 키당 2, `mouse_map_xy` 호출 8 / 실행 69.
**시험**: 에뮬레이터 수신 주입(`t_sync` RecvModel = MSQC ReceiveQC 출력 규칙, TurnSim = 지연·턴 경계·QC 유닛별 마지막 명령), 여러 플레이어·한 턴 여러 값·Down/Up 같은 사이클·엣지 소실, **MSQC.py ReceiveQC 실제 코드 + 훅 + 소비자**(가짜 QC CUnit 에 moveTarget 비트 주입, 사람 3명, 불리언 유닛 2개 + val 유닛, 40사이클), 플러그인 파서 수용(MSQC 0.11·0.9.10.11·NSQC 원문을 이 프로세스에서 실행), euddraft 빌드(MSQC 예제, NSQC 맵), 불일치·섹션 없음·QCUnit 배치 검출.
- t_sync 의 수신·턴·가짜 QC 유닛·OWNR 모델은 `testing/syncmodel.py` 로 옮겼다(WP18). e2e 의 가짜 QC 유닛은 scmodel 유닛 모델을 쓴다(판정 같음).

---
**인게임**: `docs/INGAME_CHECKLIST.md` B13(2인 디싱크, 엣지·레벨·걸쇠, 채팅 중, 관전자, 선택 복원, 150프레임 재시작).
**위험**: 로컬 값 섞기(3.7), 한 턴 안 엣지 소실(INT 5.1), MSQC Move 명령이 150프레임마다 다시 시작돼 그 사이클 값이 빈다(MapSource SNQC 조사) → 펄스·걸쇠 공백, 턴이 여러 프레임인 방(배틀넷)의 지연·소실은 인게임 확인 전, NSQC 화면 로케이션의 로컬 좌표.

---

### 4.13 `shape`, `plot` — CX Paint 도형과 찍기 — **WP7 완료**

> **2026-09-18 인게임 사실**: `Plotter` 가 **요청한 점**(`pt.x`·`pt.y`)은 도형 표와 정확히 같았지만(D7-5 15/15),
> **만들어진 유닛의 실제 위치**는 211개 중 102개가 어긋났다. 몸집이 큰 공중 유닛(뮤탈 44px·레이스·스카웃·커세어)은
> 점 간격(막대 6px, 원 32px)이 충돌 상자보다 작아 **게임이 새 유닛을 옆으로 밀어낸다**(사용자 맵은
> `NoAirCollisionX` 로 공중 충돌을 끄지만 확인 맵은 쓰지 않는다). 스커지(12px)로 찍은 108점 + 별의 첫 점만 정확했다.
> → 라이브러리 문제가 아니다. 확인 맵의 자리 판정은 스커지 플로터만 하고(`posbad`), 나머지는 밀린 수(`nudged`)와
> 생성 실패(`madebad`)를 나눠 적는다. 정확한 자리가 필요한 맵은 공중 충돌을 끄거나 점 간격을 충돌 상자보다 크게 둔다.

**근거**: `CSMake*`/`CS_*` 8맵 1,798, `CSPlot` 7맵 121, `CAPlot` 류 소수, `CA_Rotate3D` 10·`CA_RatioXY` 9·`CA_Rotate` 5(R1).
lupa 실험(R4b B3) 그대로 되었고, 이번에 **헤드리스 TEP(`tepc`, TrigEditPlus v3.0 인코더)** 로 같은 식을 계산한 좌표와
lupa 결과(자르기 규칙 적용)가 도형 17개(Hollow·NaN·난수 `CS_Shuffle`·`CSMakeGraphT`·`CS_Addon` 포함, 최대 1,700점)에서 모두 같음을
확인했다(`t_shape.py tep_compare`). Lua 5.4 난수(`math.randomseed`)도 TEP 와 lupa 가 같은 수열이다.
**2026-09-17(Windows)**: 수학 함수를 정확 반올림(`_crmath`)으로 바꿨다 — 아래 "수학 함수". 그 뒤로 tepc 대조는 star 4점만 알려진 예외다
(tepc 는 C 수학 라이브러리 그대로라 원본 플러그인과 다르다).
원본: CB Paint v2.5(CBP), theSeed `Engine/CAPlotIndexed.lua`(CAPI — 루프 의미·주소표), theSeed `MapConfig/Shape.lua:938` GunFadeShape(sweep),
DPS 이식판 a7aad90 `eud/ctrig/luart.py`(bit32 흉내·latin-1 런타임·BOM), `ctrig/classic.py _i32`(정수화 규칙).

**`shape`** — 컴파일 시점 도형 + 좌표표

```python
from eudext.shape import CX, Shape, ShapeSet

cx = CX(lib_dir=None, extra=["CSMakeSpiral.lua", "CS_Addon.lua"], seed=0, file_dir=None)
#   lib_dir 기본 = 환경 변수 EUDEXT_CBPAINT_DIR > 저장소 reference/MapSource/Library
#   seed: 모든 Lua 파일을 읽은 뒤 math.randomseed(seed) (기본 0 — 빌드마다 같은 결과, None = 원본의 시각 시드)
ring = cx.call("CSMakeCircle", 6, 32, 0, 37, 0)      # Shape — 인자: list/tuple → 표, dict → 표, Shape → {n,{x,y}…}(raw), None → nil
star = cx.eval("CS_Rotate(CSMakeStar(5,72,60,0,CS_Level('Star',5,4),0), 15)")
cx.run_file("MapShapes/Boss.lua"); boss = cx.get("SH_Boss")   # 맵별 Lua 도형
cx.run("function F(t) … end"); cx.invoke("CSSaveWithName", …); cx.value("CS_Level('Star',5,3)")   # 도형이 아닌 값
cx.reseed(1234); cx.lua; cx.globals; cx.files

s = Shape([(x, y), …], schedule=None, name=None)       # = Shape.from_points(...), Shape.from_flat([x0, y0, x1, …])
s.points; s.raw; s.schedule; s.nan_count; len(s); s[i]; s.bounds()
fade = ring.sweep("right", px_per_cycle=32)           # "right"|"left"|"in"(theSeed 그대로) + "out"|"down"|"up"
ring.with_schedule([1, 6, 12, 18])                    # LoopMax 스케줄 (사이클별 점 수)

shapes = ShapeSet([ring, star, fade], storage="db", dedupe=True)   # "db" 4B/점 | "varray" 144B/점(읽기 실행 9)
sid = shapes.add(shape)                               # 0부터. SaveMap 이 페이로드를 모으기 전까지 더할 수 있다
shapes.count(sid); shapes.start(sid); shapes.schedule(sid); shapes.lookup(sid)   # 상수 sid → 파이썬 값/상수식
x, y = shapes.point_at(sid, i)                        # 상태 없는 점 읽기 (변수 sid 가 범위 밖이면 (0, 0))
x, y = shapes.point_from(start, i); x, y = shapes.read_at(cursor)   # spawn 이 lookup 으로 받아 둔 start 로 점마다
shape.tep_int(v); shape.encode_point(x, y); shape.decode_point(w)
# lupa 적재 함수(tools/lua_consts 와 합칠 것): import_lupa, lupa_site_candidates, new_lua_runtime, install_tep_shims,
#   lua_load, lua_load_file, lua_to_py, BIT32_LUA, TEP_SHIMS_LUA, LUPA_SOURCE
```

- **좌표 정수화(D6)**: TEP 파일 배열(`SaveFileArr` → `bit32.band`)의 규칙 = `(lua_Integer)` 캐스트(0 방향) 뒤 아래 32비트
  (`linit.c:37`). DPS `_i32` 와 같고, `_i32` 가 오류를 내는 **NaN·무한대는 0**(MSVC x64·x86 `__dtol3`·glibc x86-64 모두
  0x8000000000000000 → 아래 32비트 0, tepc 실측). NaN 은 원점에 극좌표 함수(`CS_MoveRA` 등)를 쓸 때 생기고 원본 관용구
  `CS_FixShape` 도 0 으로 되돌린다. 무한대는 경고한다. 참고로 **정적 `CSPlot` 경로(`luaL_checkint_Fix` = 직접 `(int)` 캐스트)는
  NaN 을 0x80000000 으로 만든다**(tepc 실측) — eudext 는 루프형(CAPlot)의 규칙을 따른다(결정 요청 D45).
  반올림과는 1,700점 원에서 1,184점이 다르다. 부동소수 잡음도 그대로다(원의 (27.71, −15.999…) → (27, −15)).
- **수학 함수(정확 반올림, 옵션 없음 — D5·D6)**: `new_lua_runtime()` 이 Lua `math.sin/cos/tan/asin/acos/atan(y[, x])/exp/log(x[, b])` 를
  `eudext/_crmath.py` 로 바꾼다. 파이썬 `decimal` 로 고정밀 근삿값을 구하고 오차 구간의 두 끝이 같은 double 로 반올림될 때까지 자릿수를
  올린다(Ziv, 36→72→…→576자리). 뜻은 TEP Lua 5.4.4 `lmathlib.c` 그대로(`atan` = `atan2(y, x or 1)`, `log` 밑 2 → `log2`, 10 → `log10`,
  그 밖 `log(x)/log(b)`, 인자 검사·오류 문구 `luaL_checknumber` 와 같음), 특수값은 C99 부록 F(±0 부호, 극점 ±inf, 정의역 밖 NaN = x86 기본
  NaN 비트). **왜**: C 라이브러리의 1ulp 차이가 자르기(D6)로 점을 바꾼다 — star 6번째 점 y 의 참값 48 을 double 연쇄 계산이
  47.99999999999999(정확 반올림·Windows x64/x86 ucrt·**원본 플러그인 TrigEditPlus3.0.sdp**) 또는 48.000…(glibc·mingw)로 낸다.
  조사(2026-09-17, 원본 플러그인 CRT 기계어를 32비트 파이썬에서 직접 불러 잼): 맵 소스 리터럴 도형식 426개·매개변수 격자 1,166개에서
  정확 반올림 = 원본 플러그인 좌표 차이 **0점**(x64 ucrt 는 별 10개 34점, mingw 는 7개 20점 다름). 함수 호출 단위로는 원본도 0.13% 가
  정확 반올림이 아니지만 표본 좌표에는 영향이 없었다. `math.sqrt`(IEEE 정확)·`floor`·`fmod` 등과 `math.rad`/`deg`(상수 곱 한 번 — 원본
  기계어 상수 0x3F91DF46A2529D39·0x404CA5DC1A63C1F8 과 같다)는 그대로 둔다. `^` 는 Lua 5.4 `luai_numpow`(`b == 2` 면 곱셈, 아니면 C `pow`)라
  바꿀 수 없다 — CB Paint·CSMakeSpiral·CS_Addon 의 `^` 는 `^2` 와 `CS_Round`/`CXRound` 의 `10^Digit` 뿐이다(정수 Digit 0~22 는 결과가
  정확히 표현되어 플랫폼과 무관). 캐시: 파이썬 쪽 함수별 dict(프로세스 공유) + Lua 쪽 런타임별 표(±0·NaN 은 표 열쇠가 될 수 없어 건너뜀).
  처음 보는 인자는 호출당 0.1~0.3ms, t_shape 전체 시간은 거의 그대로(11.9 → 10.4~12.1초, COSTS.md "shape" 메모). euddraft 번들 3.14 와 venv 3.13 의 결과가
  같음을 확인했다(2,400값 해시·star). 인게임 맵은 2026-09-18 에 Windows 에서 다시 빌드해(`work\ingame_auto_maps\12_plot_check.scx`)
  지금 값이다 — 그 전 Ubuntu(glibc) 빌드는 별 4점이 1px 달랐다(INGAME_CHECKLIST D7).
- **Hollow**: `CSMake*(…, Hollow)` 는 선언 개수 `Shape[1]` 보다 Hollow 개 많은 점을 표에 남긴다 → `[1]` 개만 읽는다(CSPlot·CAPlot 과 같음).
- **각도(D5)**: 도형은 CB Paint 가 계산하므로 0° = 12시·시계 방향(`CS_Rotate(ray, 90)` 이 12시 → 3시).
- **Shape → Lua 는 `raw`**(자르기 전 좌표)를 넘긴다 — Lua 안에서 이어 계산한 결과와 같다(시험함).
- **shim**: `bit32`(이식판 복사), 정확 반올림 `math`(위), `math.atan2 = math.atan`, `PushErrorMsg`, `exists`/`isdir`(CSSave), `FileDirectory`
  (기본 `EUDEXT_WORK/cx_files/`). Lua 소스·청크 이름·식은 UTF-8 바이트로 넘긴다(latin-1 런타임, 한글 주석 가능).
- **저장("db")**: 점 = dword `(x+0x8000) | (y+0x8000)<<16`(−32768 ~ 32767, 밖이면 빌드 오류). 도형별 시작 EPD·점 수·스케줄 EPD 는
  주소표 3개(도형당 4B씩)와 도형 수 칸 1개. 점 읽기는 eudplib `f_readgen_epd` 한 벌(비트 32개를 x·y 로 나눠 더하고 초기값으로
  편향을 뺀다 — 모든 ShapeSet 이 공유). 변수 sid 는 [도형 수 ≤ sid] 조건(amount 자리 표시, 3.4)으로 거른다.
- **저장("varray")**: 점 = 72B 변수 원소 둘(`_compat.custom_varray` — x 원소 → y 원소 → 되돌이 트리거). 좌표 32비트.
  읽기 = 커서를 점프 트리거의 next 에 받아 원소 사슬 실행(실행 9). 커서 간격 144, 임의 접근은 16비트 곱 사슬.
- **게으른 표**: 표·좌표는 `EUDObject` 하위 클래스로, SaveMap 이 모으기(CollectDependency)를 시작하면 굳고 두 번째
  WritePayload(eudplib 0.81 은 할당·쓰기 단계에서 한 번씩 부른다) 뒤에 풀린다. 그래서 spawn 이 `push` 때 도형을 등록해도 되고,
  시험 프로세스의 다음 빌드에서도 더할 수 있다(`register_build_reset` 로 끊긴 빌드도 푼다).
- **중복 제거**: 좌표가 같으면 시작 주소를 같이 쓰고(점 한 번), 좌표·스케줄이 같으면 같은 sid. 같은 객체는 늘 같은 sid.
- **sweep**: theSeed `GunFadeShape` 를 파이썬으로 옮겼다(자 = raw 좌표, 안정 정렬, 밴드 = floor((자 − 최솟값)/폭) + 1, 빈 밴드 0 유지).
  원문 Lua 를 lupa 로 돌린 결과와 순서·스케줄이 같음을 도형 5개 × 모드 3 × 폭 3 으로 시험했다.
- **lupa 적재(2.3·2.4)**: `import eudext.shape` 가 곧바로 `lupa.lua54` 를 불러 둔다(부트 `Preload : shape`). 기본 경로에 없으면
  `EUDEXT_LUPA_SITE`(os.pathsep 구분) → 저장소 `.tools/euddraft_site` → `~/.venvs/euddraft011_site` 를 sys.path 끝에 붙여 찾고
  한 줄 알린다(`[eudext.shape] lupa 2.8 를 불러왔습니다: …`). 판이 맞지 않는 폴더(cp314 를 3.13 에서)는 건너뛴다.
  lupa 가 없어도 `Shape`/`ShapeSet` 은 되고 `CX()` 만 오류(한국어 안내).
  **실측(euddraft 0.11.0.1 Linux, 번들 3.14)**: ① `Preload : shape` + VenvSite 없음 → 폴더 찾기로 적재 ② `VenvSite : …/.tools/euddraft_site`
  → 기본 경로로 적재 ③ **Preload 없이도** eps 플러그인이 import 할 때 폴더 찾기로 적재된다(모두 빌드 통과). 예제 eds 는 VenvSite 를
  적지 않아 Linux(저장소 .tools)·Windows(`%USERPROFILE%\.venvs\euddraft011_site`) 에서 그대로 빌드된다.

**`plot`** — 런타임

```python
from eudext import plot
from eudext.plot import Plotter

pl = Plotter(shapes, unit="Zerg Scourge", owner=P8, loc="CAPlot", per_tick=12, delay=1, size=0, repeat=False,
             count=1, props=None, capture=False, on_point=None, name=None)
pl.start(shape=idx, center="loc")        # center: "loc"(pl 의 로케이션 지금 중심) | 다른 로케이션(이름·1부터 번호·번호 변수) | (x, y)
pl.set_center((x, y)); pl.stop()
@pl.on_point                              # CAfunc 대체 (파이썬 — 인자 없는 EUDFunc 도 됨. epScript 는 each())
def fx(pt):
    pt.rotate(angle, cycle=360)           # CA_Rotate (mathx.Rotator)
    pt.rotate3d(xy, yz, zx)               # CA_Rotate3D → pt.z
    pt.move(dx, dy); pt.ratio(mx, dx, my, dy)   # CA_MoveXY, CA_RatioXY (변수 제수 0 은 CtrigAsm f_iDiv 규칙)
    pt.crop(x1, x2, y1, y2)               # CA_CropXY (x ≤ x1 · x ≥ x2 · … 면 건너뜀, 부호 있음)
    if EUDIf()(pt.x > 200): pt.skip()     # CB[10]
    EUDEndIf()
@pl.on_created                            # 생성 직후 (capture=True 면 pt.unit.ok / pt.unit.epd)
def after(pt): ...
pl.tick()                                 # 매 프레임 1회 — 본문은 서브루틴 한 벌, 호출 자리 1
for pt in pl.each(): ...                  # tick() 대신 본문을 그 자리에 (epScript: foreach (pt : pl.each()) { … })
                                          #   continue = 이 점 건너뛰기, break = 이번 사이클 멈춤(그 점은 다음 사이클에)
pl.busy; pl.done                          # 조건 (읽을 때마다 새 조건)
pl.index; pl.count_var; pl.shape; pl.interrupted; pl.pt; pl.loc
pt.x; pt.y; pt.index; pt.shape; pt.center; pt.unit

# 상태 없는 부품 (spawn 이 여러 작업에 씀, S1 11-4 — 모두 상수면 파이썬 값)
x, y = plot.read_point(shapes, sid, i); x, y = plot.read_from(shapes, start, i)
x, y = plot.ratio(x, y, mx, dx, my, dy); x, y = plot.move(x, y, dx, dy)
x, y = plot.rotate(x, y, angle, cycle=360); X, Y, Z = plot.rotate3d(x, y, xy, yz, zx)
conds = plot.inside(x, y, x1, x2, y1, y2)             # CA_CropXY 의 반대 (남기는 점)
cx, cy = plot.loc_center(loc); plot.setloc_box(loc, x, y, size)
plot.create_shape(shapes, shape, unit, loc, owner, center="loc", size=0, count=1, props=None)   # 정적 CSPlot 의 루프판
# (units 에 CreateUnitShape 가 없어서 plot 쪽 도우미로 두었다 — DESIGN 초안의 units.CreateUnitShape 자리)
```

- **한 프레임**(CAPlotIndexed 의미, S1 6.2):
  `if 찍는 중 and w == 0: L = 스케줄[ptr](밴드 수 > ptr 면 ptr += 1) 또는 per_tick; k = min(L, n − p);
  k 번 {점 p 읽기(편향 빼기) → 본문/on_point → 건너뛰지 않으면 중심 더하기 → 로케이션 (X±size, Y±size) → CreateUnit → on_created → p += 1};
  w = delay; p ≥ n 이면 repeat ? (p = 0, ptr = 1) : 끝}; w = max(w − 1, 0)`.
  delay 0·1 = 매 프레임, k = k 프레임마다. 첫 사이클은 start 한 프레임. 밴드 0 사이클은 쉰다(찍는 중). 마지막 밴드는 되풀이.
  per_tick 변수 0 이면 아무것도 찍지 않고 찍는 중(원본과 같음). 점이 없는 도형은 바로 끝(repeat 면 계속 찍는 중).
- **스케줄 포인터는 start() 마다 1**(CAPlotIndexed 2026-09-09 기록의 의도. 원본 코드는 매 호출 1 로 되돌렸다 — S1 12-1).
- **각도(D5)**: 정적 도형은 0° = 12시, 런타임 `pt.rotate` 등은 CtrigAsm CA_ 와 같은 0° = +x·Cycle 단위. 양의 각은 둘 다 시계 방향
  (시험: `plot.rotate(0, −32, 90)` = (32, 0) = `CS_Rotate(ray, 90)`). 90° 어긋남은 "각 0 이 가리키는 곳" 뿐이며 원본 그대로다.
  docstring(모듈·`Point.rotate`)에 적었다. 값은 `tests/ref_mathx.py`(CA_Rotate·CA_Rotate3D·CA_RatioXY 원문 이식)와 같다.
- **중심**은 start() 순간에 한 번 읽는다(로케이션이면 (L+R)/2 를 0 방향 부호 나눗셈 — CAPI:307~315). 로케이션은 점마다
  (X−size, Y−size, X+size, Y+size) 로 옮기고 되돌리지 않는다(찍기 전용 로케이션). 맵 밖 좌표도 그대로 만든다(원본과 같음).
- **재진입(3.3)**: 본문 안에서 같은 Plotter 의 tick()/each() 를 부르면 빌드 오류. 트리거 범위·블록을 깨지 않게 **바깥 루프를 다 만든 뒤**
  오류를 낸다(안쪽 호출은 표시만 — on_created 콜백 안의 재진입도 같다). tick() 을 처음 부른 뒤에 콜백을 더하면 오류.
  `pt.*` 변환·skip 은 on_point/each() 본문에서만(on_created 에서는 오류 — 유닛을 이미 만들었다).
- **이름**: 유닛·로케이션 이름은 맵을 불러오기 전(모듈 전역·epScript const)에도 받는다 — 유닛 이름은 CreateUnit 이, 로케이션 이름은
  빌드 때 번호로 바꾼다. 로케이션은 이름 또는 1부터 번호 상수만(3.9), owner 는 eudplib 플레이어 상수·번호·변수만(문자열 거절).
- 변수 size 는 사이클마다 한 번 −size 를 만든다. count·unit·owner 변수는 eudplib DoActions 변수 칸 패치를 점마다 한다.

**비용**(docs/COSTS.md "shape (WP7)"·"plot (WP7)"): 점당 실행 **"db" 53, "varray" 22**(S1 8.6 목표 60 안), 빈 프레임 4, 사이클 머리 약 21
(+스케줄 45), tick 서브루틴 본문 약 29 + 공유 점 읽기 35(한 벌), 호출 1. 찍기 루프 트리거 수는 도형 수·점 수와 무관(시험: 1개·1점 ↔
60개·21,492점 모두 34·48). 좌표: 1,700점 원 scx +5.9KB(압축 뒤, 날 6.8KB), "varray" +22KB, 도형 50개×37점 +7.2KB. 주소표 도형당 12B.
start: 상수 3 / 변수 sid 134 / 로케이션 중심 +약 195. point_at: 상수 sid 42, 변수 sid 172(db)·163(varray). create_shape 점당 약 80 + 127.
`pt.rotate(변수 각)` +약 100/점, capture +21/점, count 변수 +14/점.

**시험**: `tests/t_shape.py`(1,877 — tepc 없으면 1,857) — 고정 시드 스냅숏 17도형(점 수·NaN 수·자르기≠반올림 수·sha·앞 6점·자르기 규칙 —
star 는 2026-09-17 정확 반올림 값으로 고침), **원본 TEP(tepc) 대조 17도형 + NaN/직접 캐스트 차이**(star 4점은 알려진 예외 `TEP_KNOWN`),
**정확 반올림 수학**(`tests/ref_crmath.py` — 다른 알고리즘의 90자리 기준값과 무작위·경계 인자 761호출 비트 일치, C99 특수값 94, 원본 플러그인
측정값 16(star 인자 4 포함), decimal 전역 문맥과 무관, Lua 연결 480호출·rad/deg 상수·정수/문자열 인자·결과 float·±0/NaN·Lua 캐시 호출 수·
인자 오류 문구·`10^k`·`x^2`, star `S[7]`·`S[21]` = 47·95), `tep_int` 경계 21, Hollow(표 길이·선언 개수·앞 Hollow 점 건너뜀), NaN = CS_FixShape, 무한대 경고,
CX API(call/invoke/eval/value/run/run_file/get/reseed/to_lua/한글 주석/BOM/CSSave/atan2 흉내/bit32)와 오류 13종, Shape API·sweep(원문 Lua 와
45조합 대조 + 새 모드 15)·스케줄 검사, 인코딩 왕복 2,049쌍·범위 오류, ShapeSet 컴파일 시점(중복 제거·dedupe=False·varray·오류),
lupa 폴더 찾기(하위 프로세스: 기본 경로에 없을 때 EUDEXT_LUPA_SITE 로 적재, 못 찾으면 CX 만 오류, cp314 폴더 거절),
에뮬레이터 1,451(db·varray·dedupe=False × point_at/point_from/커서 진행/lookup·count·start·schedule/좌표표·스케줄 표 메모리/
범위 밖 sid 4종/상수 접기/게으른 표 — 쓰는 중 add 오류·다 쓴 뒤 add → 다음 빌드에 실림, 빌드 오류 5), epScript 예제 번역·에뮬레이션·
euddraft 빌드 3종(Preload / VenvSite / Preload 없음), scx 크기.
`tests/t_plot.py`(9,192) — 참조 모델(`Ref`, CAPlotIndexed 의미)과 프레임마다 찍은 상자·유닛·주인·수량·props·busy/done/index/interrupted 비교:
상수 인자(도형 8종 × 중심 2), 재시작·범위 밖 sid·stop, 변수 인자 6조합 × 도형 4(per_tick 0·0xFFFFFFFF 포함), varray + "all" + size + repeat
+ stop, props + count + delay 0 + repeat, on_point(pt.rotate 변수 각 7종·move·ratio 변수 제수 0 포함·crop·skip) = ref_mathx,
each() continue/break, EUDFunc 콜백(pl.pt 사용), capture + on_created(생성 실패 주입), each() rotate3d·ratio·`pt.x -=`, 중심 모드 4종(자기 로케이션 음수 사각형 포함·번호 변수·
이름·set_center), create_shape(변수·상수·varray·props·loc 중심), 상태 없는 부품 차등(ratio 1,200·move·rotate·rotate3d·inside·loc_center·
setloc_box·read_point/read_from), 빌드 오류 25종(재진입 3종·콜백 늦게 더하기·on_created 에서 skip 포함), 트리거 수 무관(3.8), epScript 예제·인게임 확인 맵의
번역·에뮬레이션(맵 자체 점검 15/15 + 545프레임 동안 찍은 좌표 전체 = 참조)·euddraft 빌드.

**인게임**: `docs/INGAME_CHECKLIST.md` D7-1~D7-5 (필수 D7-1: 모양·방향이 CB Paint 원본과 같은가). 확인 맵 `examples/plot_ingame.eds`.

**위험·미정**: 인게임에서 공중 유닛이 겹칠 때 조금 밀리는 것(모양 확인에는 지장 없음 예상), 로케이션 중심 계산(0 방향)이 SC 의 생성 위치와
같다는 가정(유닛 모델과 같음), 콜백 안 임시 변수 — 공유 함수(점 읽기·mathx)는 차례로 불려 겹치지 않는다(재진입만 막음).

**초안과 달라진 점과 이유**
1. **epScript 는 콜백 대신 `foreach (pt : pl.each())`**: epScript 는 함수 이름을 값으로 넘길 수 없다(`pl.on_point(fx)` → 번역 오류
   "Undefined rvalue fx", 0.81 실측). 3.11 의 begin/end 짝 대신 eudplib 관용구(생성기 + `EUDSetContinuePoint`)를 썼고, `continue`/`break` 가
   건너뛰기·사이클 멈춤이 된다. 파이썬은 초안대로 `@pl.on_point` + `tick()`.
2. **`storage="varray"` 는 144B/점**(초안 72B): 72B 원소 하나에는 액션이 하나라 x·y 두 원소가 필요하다. 한 원소에 x·y 를 묶으면 비트 나누기(실행 32)가
   다시 필요해 "읽기가 빠르다" 는 뜻이 없어진다(결정 요청 D43).
3. **sid 는 0부터**(CAPlot CA[1] 은 1부터). 파이썬·epScript 목록 번호와 같게(결정 요청 D44).
4. **`ShapeSet` 조회 함수 더함**: `lookup`(start·count·schedule 한 번에), `start`, `schedule`, `point_from`, `read_at`, `step` — spawn 이 작업마다
   캐시하고 점마다 `point_from` 을 쓰게(S1 8.5 "sid, n 넣을 때 캐시"). 변수 sid 범위 검사(읽지 않고 0).
5. **게으른 표**: 초안은 ShapeSet 을 만들 때 좌표를 굳히는 그림이었다. spawn 의 push 등록을 위해 SaveMap 직전까지 더할 수 있게 했다.
6. **`Plotter` 인자 더함**: `count`(CAPlot PerUnit), `props`(CreateUnitWithProperties), `capture`/`on_created`(CAPlot PerAction 자리 — 생성 뒤 유닛 손보기),
   `on_point=` 키워드. 제어 `stop()`·`set_center()`, 값 `index`·`count_var`·`shape`·`interrupted`(찍는 중에 start 가 끊은 횟수 — 3.10 "넘침 카운터 항상").
7. **`Point` 메서드 더함**: `rotate3d`(CA_Rotate3D 10회 사용), `crop`(CA_CropXY). RA 계열(CA_MoveRA·CA_RatioRA·CA_ConvertRA/XY·CA_InvertXY/RA·CA_CropRA)은
   사용 0 이라 만들지 않았다(0.2 원칙) — 필요하면 mathx.atan2·isqrt·lengthdir 로 한 줄.
8. **`units.CreateUnitShape` → `plot.create_shape`**: units 에 없어 plot 쪽 도우미로 두었다(지시대로).
9. **상태 없는 부품 더함**: `inside`, `loc_center`, `setloc_box`, `read_from`, `rotate3d`.
10. **`CX.invoke`/`value`/`run`/`get`/`reseed` 더함**: 도형이 아닌 반환(CSSave, CS_Level)과 맵 Lua 의 전역 도형.
11. **sweep 모드 더함**: theSeed 의 right/left/in 에 out/down/up(같은 규칙).
12. **Shape → Lua 는 raw**: 정수 점을 넘기면 `CS_Rotate(cx.call(...), 15)` 처럼 이어 계산한 결과가 Lua 안 연쇄와 달라진다(시험에서 발견).
13. **2단계 `variants`** 는 만들지 않았다(지시대로 — 7절 D14 뒤).
14. B8 의 `convention=` 인자는 두지 않았다(D5: 옵션 없음 — 문서로만).

---

### 4.14 `spawn` — G_CB 식 소환 대기열 — **WP12 완료(1단계)**

**근거**: `G_CB_TSetSpawn` 962, `G_CB_SetSpawn` 393, `f_TempRepeat` 297, `G_CB_TScanEff` 183 등 7맵 2,048회(R1, S1 7.1). 구조: 도형을 컴파일 시점에
번호로 등록(최대 4층) → 런타임에 소환 작업을 대기열에 넣음 → `G_CBPlot` 이 매 프레임 작업을 진행(theSeed `Engine/G_CB_Lib.lua` 2,769줄 —
2026-09-17 theSeed 판과 reference 사본이 같음을 확인). 비용 문제: 대기열 307KB + 빈 도형 좌표 약 1.78MB + 도형당 약 6트리거(theSeed 도형 726개에 12.7MB),
점당 실행 약 400~500(추정).

**명세(정본)**: `docs/spec/S1_gcb.md` — 정본 판은 **theSeed 판**. API·내부 구성·비용 목표는 S1 8절, 시험은 9절, 함정 대책은 10절. 아래 "S1 8절과 달라진 점" 만 다르다.
`G_CA`(옛판)·UE_RE 판은 대상 밖(S1 1.4 — 옮길 때 단계 번호를 도형 객체로 풀어 `push`). RepeatType 은 맵마다 번호·뜻이 달라 **등록형 핸들러**다.

**파일**: `eudext/spawn.py`, `tests/t_spawn.py`·`tests/t_spawn_xform.py`·`tests/ref_spawn.py`, `examples/spawn_example.{eps,eds}`,
`examples/spawn_ingame.{eps,eds}`(인게임 E12).

**API**

```python
from eudext.spawn import Spawner, Order, Effect, at_unit, GLOBAL

sp = Spawner(capacity=128, loc="GCB Src", loc2="GCB Dst", default_target="Home",   # loc·loc2 필수 (이름 또는 1부터 번호, 64 금지)
             default_owner=P8, map_size=None, cycle=360, turn_radius=127,
             storage="db", shapes=None,          # 좌표표 ShapeSet (없으면 새로, 있으면 함께 씀)
             props="energy",                     # 원본처럼 CreateUnitWithProperties(energy=100) | None = CreateUnit | UnitProperty
             on_create=None,                     # UnitData(목록) = 생성 직전 그 칸 초기화 | fn(칸 번호)
             on_full=None, debug=False,          # 넘침 문구: None = debug 면 "report" | "silent" | 함수. 넘침 카운터는 항상
             unclickable=None, name="spawn")     # unclickable 은 2단계(자리만)

sp.rtype("Nothing")                                   # 핸들러 없음. 번호 생략 = 1~255 중 빈 가장 작은 번호, 0 = "없음" 예약
sp.rtype("Home", sp.builtin.attack_default)           # 내장 핸들러 (아래), 핸들러 목록도 된다
@sp.rtype("Skill", id=8)
def _skill(s):                                        # s: SpawnCtx
    s.default_order(Patrol)                           # 명령 속성이 있으면 아무것도 안 함
    s.set_remove_timer(15)
sp.rtype_func("Hold", HoldFn, sp.builtin.vision)      # EUDFunc(epd, unit, owner, x, y) 또는 인자 0개 (epScript)
sp.default_rtype = "Home"                             # rtype 생략 시 (None = 0 = 없음)

sp.push(37, ring, owner=P8,
        center=None,        # None = 넣는 순간의 sp.anchor | (x, y) | "Loc" | 1부터 번호 | 번호 변수 | at_unit(epd)
        lm="max",           # "max" = 255 | 1~255 | 0 = 자동 n//50+1 (넣을 때 계산) | 변수(0 이면 자동)
        delay=0, size=100,  # 상수·변수. delay 0·1 = 매 프레임
        rotate=0,           # 정수(−1 도 각도) | 변수 | sp.GLOBAL
        offset=(0, 0),      # DistanceXY — 회전 뒤 평행이동
        rtype=None,         # 등록된 이름·번호 | 변수(등록 안 된 값이면 아무것도 안 함 + debug 문구)
        order=None,         # Order.attack(x, y) | Order.patrol("Loc") | Order.move(at_unit(epd)) …
        effect=None)        # Effect.scan(image, color=None) — 유닛 33 고정
        # 2단계 자리(쓰면 컴파일 오류): rot3d=True, variant=…, mirror=True, Effect.frag(…), sp.rot3d
h = sp.job(owner=P8, center=(x, y), order=Order.attack("Boss")).layer(37, ring).layer(38, star, size=150, delay=5).push()
sp.push_layers([(37, ring), (38, star)], owner=P8)    # 파이썬 편의
sp.push_multi([8, 12, 2, 3], warp, center="Boss")     # 원본 CUTable·ShapeTable 모양 (도형 하나 = 모든 층, 수가 다르면 컴파일 오류)
sp.scan_effect(ring, 429, color=16, center="Boss")    # G_CB_TScanEff (도형 목록이면 층마다)
sp.tick()                                             # 매 프레임 1회 (push 뒤에 두면 같은 프레임에 첫 사이클)
sp.spawn_now(37, count=5, owner=P8, at="Boss", rtype="Skill", order=None, effect=None)   # f_TempRepeat(X)
sp.clear()                                            # 모든 작업(뒤 층 포함) 반납
sp.anchor.x, sp.anchor.y      # G_CB_X/Y (대입하면 값이 들어간다 — epScript `sp.anchor.x = 3072;`)
sp.rotation                   # G_CB_RotateV (`sp.rotation += 5`)
sp.live, sp.overflow          # 살아 있는 레코드(층) 수, 넘친 넣기 수 (EUDVariable)
sp.preview(shape, center=(x, y), size=…, rotate=…, offset=…, rotation=…)   # 컴파일 시점 소환 좌표 목록 (문구·점검용)
sp.preview_count(…); sp.rtype_id("Home"); sp.shapes; sp.pool; sp.ctx; sp.loc; sp.loc2; sp.map_size
spawn.rotate_py(x, y, a, cycle), spawn.transform_py(x, y, size, rotate, cycle)   # 파이썬 계산 (CtrigAsm CA_Rotate 값)
```

`SpawnCtx`(핸들러 `s`, epScript 는 `sp.ctx`): 값 `epd`, `ptr`, `index`, `cunit`, `unit`, `owner`, `rtype`, `px`/`py`(소환한 점),
`cx`/`cy`(작업 중심), `ox`/`oy`(명령 목표), `x`/`y`(유닛이 실제로 선 자리 — 읽을 때마다 새로 읽음, `pos()` 는 둘 한 번에),
조건 `has_order`. 동작 `here()`(loc ← 유닛 자리 ±1), `default_order(kind, target=None)`(명령 속성이 없을 때만 — target None = default_target
(로케이션이면 **명령 순간**의 그 로케이션), "center", 로케이션, (x, y)), `order(kind, x, y)`, `kill_all()`, `set_turn_radius`, `set_speed(top, accel)`,
`set_remove_timer`, `set_parasite(0xFF)`, `set_order_id`, `set_invincible()`.
내장 `sp.builtin`: `attack_default`(원본 0), `kill_all_of_type`(3), `remove_timer(n=250)`(5), `attack_center`(7 — 원본 이름 `patrol_center` 도 별칭,
이름과 달리 어택), `skill_unit`(8), `vision`(180), `nxct`(106), `no_speed`(201), `nspeed(attack=True)`(147/148), `force_order(187)`(JYD).
맵 전용(130~137, 175~179, 181, 188)은 없다 — 맵이 `rtype` 으로 등록한다.

epScript (`examples/spawn_example.eps`, 번역·에뮬레이터·euddraft 빌드 확인):

```js
import eudext.spawn as spawn;
const sp = spawn.Spawner(capacity=16, loc=26, loc2=27, default_target=13);
function CountHome(epd, unit, owner, x, y) { homes += 1; }          // rtype_func 보다 앞에 정의
function onPluginStart() { sp.rtype_func("Home", sp.builtin.attack_default, CountHome); sp.rtype("Nothing"); }
function afterTriggerExec() {
    if (frame == 1) {
        sp.anchor.x = 1024; sp.anchor.y = 1024;
        sp.job(owner=P8, rtype="Home").layer(37, ring).layer(38, star, size=150).push();
        sp.push(39, fade, center=list(2048, 1024), rtype="Nothing", order=spawn.attack(13));
    }
    sp.rotation += 15;
    sp.tick();
}
```
- 명령·이펙트·유닛 자리 표식은 **모듈 함수** `spawn.attack/patrol/move/order(…)`, `spawn.scan(…)`, `spawn.at_unit(epd)`(번역 `spawn.f_attack` …).
  `spawn.Order.attack(…)` 사슬은 번역 오류(`Undefined function f_attack`), `const O = spawn.Order;` 는 문법 오류(실측).
- epScript 함수 이름은 **정의보다 뒤에서** 값으로 넘길 수 있다(`sp.rtype_func("H", H)` — 번역 `sp.rtype_func("H", H)`). 앞에서 쓰면 "Undefined rvalue".
- `sp.rotation += 15;`·`sp.anchor.x = 3072;` 는 `_ATTW` 로 번역되고 속성 setter 가 값 대입으로 바꾼다.

**의미·알고리즘** (S1 6절 = theSeed G_CB + CAPlotIndexed, 8.1 원칙)
- **레코드 = 층 하나 = pool 레코드**(필드 20개: unit·owner·rtype·pc(점 커서)·left(남은 점)·sp/se(스케줄 포인터·끝)·w(남은 대기)·lm·delay·size·rot·
  flags·cx·cy·dx·dy·ox·oy·eff — 되쓰는 필드는 pc·left·sp·w 넷). `push` 는 호출 자리에서 `pool.alloc_n(층 수)` 한 번(원자적: 모자라면 통째로 버리고
  `overflow += 1`, 문구는 on_full). 첫 층 w = 0, 뒤 층 w = 0xFFFFFFFF(기다림).
- **tick** (서브루틴 한 벌, 호출 자리 1 — 살아 있는 레코드가 없으면 들어가지 않음):
  ```
  carry = 0
  for 레코드 (pool 순회 = 넣은 순서, 루프 중 넣은 작업은 다음 tick):
      carry 면 carry = 0, w = 2                     ← 층 사이 빈 프레임 1개 (D13 재현)
      if w == 0:
          L = 스케줄[sp](se > sp 면 sp += 1) 또는 lm;  k = min(L, left)
          k ≥ 1 이면 사이클 머리(작업 레지스터 적재·소환 루틴 고르기·생성 액션 패치·회전각·이펙트 준비) 뒤 k 번:
              점 읽기 → [크기 → 회전(전역이면 점마다 sp.rotation)] → + (dx + cx, dy + cy) → X ≤ W−1 이고 Y ≤ H−1 이면 소환 → pc += 1, left −= 1
          w = delay;  left == 0 이면 (뒤 층 있음 → carry = 1) 반납(free_current)
      w = max(w − 1, 0)
  ```
  "바로 뒤 레코드 = 다음 층" 은 pool 규칙(할당 순서로 순회, 루프 중 할당은 다음 루프)과 `alloc_n` 이 층을 차례로 잡는 것에 기댄다(다음 층 핸들 필드를 두지
  않아 방문당 실행 1·층 넘김 9 절약). 여러 작업 섞기·압축·핸들러 안의 push 에서 참조 모델과 같음을 시험했다.
- **변환**(S1 6.3): 크기 `CiDiv(x·S mod 2³², 100)`(mathx.ratio, S ≠ 100 일 때만) → 회전 CtrigAsm `CA_Rotate` 항별 자르기(mathx.Rotator(None) —
  Spawner 마다 각 변수, 변수 각 엔진은 공유) → 평행이동 → 중심 → 경계(부호 없는 비교라 음수도 걸러짐). 경계 밖 점은 건너뛰고 진행으로 친다.
  크기·회전 코드는 **주 함수를 다 만든 뒤 쓰인 기능만** 서브루틴에 채운다(`_compat.on_start_after_main`) — 안 쓰면 mathx 엔진(약 110KB)이 페이로드에 안 들어간다.
  주 함수 뒤에 그 기능을 쓰는 push 가 나오면 컴파일 오류.
- **소환 루틴 세 벌**(후처리 없음 · 후처리 · 이펙트): 사이클 머리에서 flags 로 하나를 골라 점마다의 호출 트리거 대상과 돌아올 곳을 고친다(점마다 분기 없음).
  - 후처리 없음: `loc ← (X, Y, X, Y)` → 생성 액션 1 (유닛·주인 칸은 사이클 머리에서 패치).
  - 후처리(rtype 에 핸들러가 있거나 rtype 이 변수거나 명령 속성·on_create 가 있을 때 — 넣을 때 정함): `units.Capture` 시작 → on_create(칸 번호) → 생성 →
    성공이면 `EUDSwitch(rtype)` → 등록 핸들러(인라인) → 명령 속성이 있으면 loc ← 유닛 자리 ±1, loc2 ← 목표 ±1, `Order(유닛, 주인, loc, 종류, loc2)`.
    생성 성공 판정은 원본의 에너지 상위 바이트 검사 대신 capture(0x628438 이 바뀌었나).
  - 이펙트: `[0x666458 ← 이미지(word), CreateUnit(33), KillUnit(33, 주인), 0x666458 ← 546]` 한 트리거. 색은 사이클 동안 images.dat Draw Function
    (0x669E28 + 이미지)을 바꿨다가 되돌린다(원본은 점마다 — 같은 프레임 안이라 결과 같음).
- **넣는 순간 해석**: 중심·명령 목표 로케이션은 넣을 때 `(L+R)/2, (T+B)/2`(0 방향 — plot.loc_center)로 좌표가 된다. anchor 는 그때 값을 복사한다.
  원본과 달리 로케이션 중심 모드가 anchor 를 **덮어쓰지 않는다**(S1 10-28). 기본 명령의 로케이션 목표는 명령 순간의 로케이션(원본 DefaultAttackLoc 과 같음).
- **spawn_now**: 작업 레지스터에 값을 싣고 같은 소환 루틴을 count 번(모두 한 점 — 원본 직접 경로와 같음, 경계 검사 없음).
- **clear**: 그 자리에 pool 순회 하나를 두고 모두 `free_current`.
- **로케이션**: eudplib 규칙 하나(이름 또는 1부터 번호, 3.9) — S1 10-17·18·19 의 오프바이원은 원본 의도대로(이름 = 그 로케이션, 번호 = 1부터) 고쳤다(A-3 → E12-3·4).
- **CP**(3.6): 유닛 칸 쓰기는 CP 를 원시로 옮기고 캐시로 되돌리는 방식(3.6-7), 나머지는 CP 를 쓰지 않는다. tick·push·spawn_now 앞뒤 CP 동일(시험).
- **재진입**(3.3): 핸들러 안에서 같은 Spawner 의 `tick`·`spawn_now`·`clear` 는 소환 루틴을 다 만든 뒤 빌드 오류. 핸들러 안의 `push`(다음 tick 부터)·
  다른 Spawner·`bullet`·`units` 는 된다. 다른 Spawner 의 핸들러를 거쳐 되돌아오는 호출(A → B → A.spawn_now)은 검사하지 못한다(문서).
- **한 프로세스 여러 빌드**: 코드 조각(서브루틴·템플릿 액션)은 빌드마다 새로(`register_build_reset`), 변수·rtype 등록은 그대로.
- **mathx(WP9 안내)**: 회전은 `mathx.Rotator(None)` 에 사이클마다(전역 회전은 점마다) `set` — 변수 각 엔진은 같은 주기의 모든 Rotator 가 공유하고,
  각 변수만 Spawner 마다 따로 둔다(한 Spawner 의 핸들러가 다른 Spawner 를 돌려도 각이 섞이지 않게). 3D(`rotate3d(…, own=True)`)는 2단계.
- **총알(WP14 안내)**: S1 11-1 대로 `on_point`(점마다 사용자 코드)는 2단계 후보라 1단계에는 없다. 옛 G_CA `RepeatType 101`(탄막)을 옮길 때는
  rtype 핸들러에서 `bullet.bullet(k, s.owner, s.px, s.py, 방향)`·`bullet_to(…)` 를 부를 수 있다(bullet 은 스포너를 부르지 않아 재진입 없음 — 에뮬레이터
  시험은 하지 않았다). 이때도 층 유닛은 만들어지므로 곧 사라지는 유닛(핸들러에서 `s.set_remove_timer(1)`)을 쓰거나 `s.kill_all()` 로 지운다(`Effect.scan` 작업은 핸들러를 부르지 않는다).

**S1 10절 함정 대책** (시험 = t_spawn 케이스 이름)

| # | 함정 | eudext |
|---|---|---|
| 1 | 조건 없는 넣기가 매 사이클 쏟아짐 | `push` 에 조건 인자 없음(호출 자리 EUDIf), 넘침 카운터 + debug 문구 (J) |
| 2 | PreserveFlag·CallTriggerX 플래그 뜻 반대 | 보존 플래그 없음 — `EUDExecuteOnce` 안내(docstring). 공유 본체 안 "게임당 한 번" 주의는 pool 과 같음 |
| 3 | 인자 위치 혼동(TOrder·TCreateUnitWithProperties) | 키워드 인자, 템플릿 액션 + 칸 패치 — 명령 상자·목표·수량 시험(`sr_tick`) |
| 4 | 원시 주소 되읽기 | 로케이션은 번호로 받고 주소 계산은 `_box` 한 곳, 유닛 자리는 CUnit 에서 |
| 5 | 128×128 상수 | `map_size`(없으면 chk DIM) 한 곳 — 6144×3072 경계 벡터(t_spawn_xform) |
| 6 | 타이머 Exactly | 호출 쪽 문제(문서) |
| 7 | 대기열 경계 넘어 쓰기 | pool alloc_n — L: 가득 찬 뒤 넣기에서 레코드 표·표 뒤 무변경(메모리 비교) |
| 8 | CB 표 크기 | 해당 없음(ShapeSet) |
| 9 | 도형 등록이 표 동일성 → 트리거 폭증 | ShapeSet 내용 중복 제거 + 도형당 트리거 0 (트리거 수 무관 시험) |
| 10 | 받은 도형·속성 표를 고쳐 씀 | 받은 목록을 복사해서 씀(Job 층 목록·push_multi 시험), Shape 는 바뀌지 않는 값 |
| 11 | 유닛 수 ≠ 도형 수 | 층마다 유닛·도형 한 쌍, `push_multi` 수가 다르면 컴파일 오류(`err_multi_mismatch`) |
| 12 | 4층 같은 도형 겹침 | 문서(인게임 E12-3 은 같은 도형 네 층) |
| 13 | 빈 밴드 사이클을 버림 | 스케줄 사이클은 늘 살아 있음(I, 인게임 E12-2 빈 6열) |
| 14 | 40번 시한부 | 맵 쪽 핸들러(문서) |
| 15 | 0틱 클릭 토글 조건 | 2단계(unclickable — 자리만) |
| 16 | LoopMax 포인터 매 호출 1 | **작업별 포인터**(I: 5, 0, 7) — 인게임 E12-2 에서 체감 비교 |
| 17 | Order 로케이션 문자열 한 칸 앞 | 이름 = 그 로케이션(`sr_center` 8, E12-3) |
| 18 | f_TempRepeat 문자열 중심 한 칸 앞 | 이름 = 그 로케이션(`sr_now` 2, E12-3) |
| 19 | 숫자 중심 0/1 혼동 | 1부터 번호만, 0 은 컴파일 오류(`err_center_loc0`, `sr_center` 5·6, E12-4) |
| 20 | 명령 로케이션 모드가 중심 표식을 봄 | 명령 목표는 넣을 때 좌표로(`sr_center` 8·10, `sr_now` 3) |
| 21 | 리버 스캐럽 로케이션 1 고정 | 만들지 않음(맵 핸들러로) |
| 22 | LM 자동을 도형 번호 하위 바이트로 비교 | 넣을 때 `n//50+1`(F, 변수 sid 는 실행 중 계산 — `sa_push_var`) |
| 23 | LM 0 + 딜레이 ≥ 2 → 영원히 | lm 0 = 자동(≥ 1)이라 생기지 않음 |
| 24 | RepeatType 이름 오타 → 조용히 0 | 등록 안 한 이름·번호는 컴파일 오류(`err_rtype_name/id`), 변수는 아무것도 안 함 + debug 문구 |
| 25 | 바이트 묶음 넘침(크기 300% 등) | 필드가 dword (size 0~2³¹−1) |
| 26 | T 경로 스테이징 대입 경합 | 넣기는 호출 자리에서 한 번에(스테이징 변수 없음) |
| 27 | VMode CAdd 누적 | 해당 없음 |
| 28 | 로케이션 중심이 G_CB_X/Y 덮어씀 | 덮어쓰지 않음(`sr_center` anchor 확인) |
| 29 | KillUnit·스캔이 그 주인의 유닛 전부 | 같게, 문서(`kill_all_of_type`, `Effect.scan`, 주인 기본 P8) |
| 30 | TOrder 2×2 상자 | 같게, 문서 — 명령받은 유닛 기록으로 시험(`sr_now` 1: 겹친 같은 종류도 받음) |
| 31 | 생성 실패여도 뒤처리 | capture 로 성공일 때만 핸들러·명령(생성 실패·빈 칸 없음 시험) |
| 32 | 구판 래퍼 컴파일 불가 | 해당 없음(push_multi 가 CUTable 모양) |
| 33 | 층별 회전 표 | 층마다 `rotate=` |
| 34 | Patrol_Center 는 어택 | `attack_center`(별칭 `patrol_center`), 문서 |
| 35 | f_TempEffRepeatX 전역 PP | 해당 없음(`spawn_now(effect=…)`) |
| 36 | 프리펑션 작업 칸 1,699점 | 2단계 |
| 37 | CB_MarNumFill 변수 7개 | 해당 없음 |

**비용** (docs/COSTS.md "spawn (WP12)", 2026-09-17 — S1 8.6 목표)

| 항목 | 목표 | 실측 |
|---|---|---|
| 도형 등록 | 트리거 0 | 0 (좌표 4B/점, 트리거 수 무관 시험: 도형 1개·1점 = 60개·21,492점 = 152) |
| 엔진 본체 | ≤ 400 (핸들러 제외) | tick·소환 루틴 세 벌·변환 서브루틴 약 150 (+ 공유 함수: capture 14, 위치 읽기, pool 공유 코드 2b+30) |
| 빈 프레임 | ≤ 3 | **1** (살아 있는 레코드가 없으면 서브루틴에 안 들어감) |
| 점당 실행(크기·회전·명령 없음, "db") | ≤ 60 | **58** |
| 기본 명령(좌표 읽기 + 로케이션 2개 + Order) | +40 | +79 (캡처 21·rtype 분기 약 6·회전반경 쓰기 약 5 포함 — 이것을 빼면 약 +47) |
| 크기 | +40 | **+133** (변수 크기 곱 + 상수 100 부호 나눗셈 × 두 축 — mathx.ratio. 결정 요청 D76) |
| 회전 | +120 | +107 (같은 각), 전역 회전 +97 |
| 스캔 이펙트 | - | 점당 +15, 사이클 머리 약 +60(색 있음) |
| 레코드 방문(기다리는 층) | - | 약 45/프레임 (pool 적재 20 + 되쓰기 4 포함) |
| 호출 자리(상수만) | ≤ 3 + 호출 | push 7 (pool alloc_n 인라인 — 분기 + alloc 4), 로케이션 중심 +1 |
| push 실행 | - | 상수 20~22, 변수 5개 25, 로케이션 중심 216, 변수 sid 156, 3층 56 |
| spawn_now | - | 상수 1기 31(후처리 없음)·110(기본 어택) |
| clear | - | 3개 132 |
| 대기열 저장 | 128칸 약 12KB | **chk +309KB, scx +30KB**(capacity 128, 기능 없음) — pool 레코드가 72B 원소 22개(1.7KB/층)라서. capacity 8 은 chk +92KB·scx +9.6KB. 크기·회전을 쓰면 mathx 엔진 +113KB(chk)·+13KB(scx), 모든 기능 chk +474KB·scx +50KB. 원본은 대기열 307KB + 빈 도형 1.78MB + 도형 726개 12.7MB (결정 요청 D75) |

**시험**
- `tests/t_spawn.py` (2,514 판정, 약 20초): 참조 모델 = S1 9.1 표 A~I 확인 → **9.1 A~I(+C') 프레임마다 좌표·유닛·주인·live·반납 프레임**, N(여러 작업 동시·
  층 사이 빈 프레임이 섞여도 1개), O(clear — 뒤 층 포함, 빈 칸 되돌림), P(점 0개 상수 도형 = 컴파일 오류, 변수 sid 빈 도형·범위 밖 = 바로 끝 + debug 문구,
  lm 변수 0 = 자동), J·K(넘침 — 넘침 문구 한 번·Buzz ×2), L(가득 찬 뒤 넣기 — 레코드 표·표 뒤 무변경), M(핸들러 안의 push 는 다음 tick),
  rtype 16종 × 명령 속성 4종(내장 핸들러 10종·파이썬 핸들러·EUDFunc 5인자 핸들러·등록 안 한 변수 rtype — 명령 상자·목표·명령받은 유닛·CUnit 칸
  (회전반경·속도·가속도·removeTimer·기생·주문·무적)·KillUnit), 상수 rtype(핸들러 없는 이름은 후처리 없음, Home + 명령 속성 = 명령만), 생성 실패·빈 칸 없음,
  CP 보존(tick·spawn_now × CP 여러 값), 중심 모드 7종(넣은 뒤 anchor·로케이션을 바꿔도 그대로, anchor 를 덮어쓰지 않음), 명령 목표 모드 3종,
  spawn_now 5모드(변수 유닛·수·주인·rtype, 로케이션 이름·번호 변수, 경계 검사 없음, anchor), scan_effect 4모드(생성 순간 이미지·색, KillUnit, 되돌림,
  두 층 빈 프레임), on_create(UnitData 기본값·함수 훅 = 만든 칸), props=None, 전역 회전을 점마다 읽음(핸들러가 바꾼 값), 변수 인자 전부 + varray +
  변수 sid(스케줄 도형) 무작위 차등 24회, 빌드 오류 36종(2단계 자리·재진입 3종·default_target 없음·주 함수 뒤 기능·`spawn.f_f_…` 안내 포함),
  파이썬 검사 76(생성자·등록·Order/Effect·preview = 참조·표 복사), 트리거 수 무관, epScript 예제·인게임 맵 번역·에뮬레이션·euddraft 빌드.
- `tests/t_spawn_xform.py` (기본 191 판정, 약 25초): 참조 = S1 9.2 29줄 확인 → **lengthdir 9·rotate 8·size 5·전체 변환 7(6144×3072 경계) 에뮬레이터**,
  상수 인자 판, 전역 회전은 넣은 뒤 값, 무작위 차등(작업마다 255점: db 20,400점 + varray 2,040 + 경계 맵 2,040, 전역 회전·크기·음수 좌표 섞음),
  파이썬 계산 2만 건. **`EUDEXT_SPAWN_FULL=1`: 무작위 204,000점 + varray 20,400 + 경계 20,400(합 244,800점), 파이썬 20만 건 — 1,055 판정 통과(약 3분 10초)**.
- 시험 모델: `testing/scmodel.py`(KillUnit/RemoveUnit 의 Force1~4, 대량 생성 때 빈 칸 목록을 끝까지 따라가지 않음),
  `testing/locmodel.py`(Order 기록 `orders` — 시작·목표 사각형, 목표 중심, 명령받은 유닛, `order_move`).

**인게임**: `docs/INGAME_CHECKLIST.md` E12-* — **필수 E12-1(해처리: 맵 오른쪽·아래 끝, 연속 두 건물), E12-2(블랙홀: 페이드·빈 열·사용자 핸들러),
E12-3(보스 워프: 층 간격·명령 목표 = 그 로케이션·보스 자리 — A-3 17·18)**, E12-4(A-3 19), 보조 E12-5~7(전역 회전 방향, 스킬 유닛, 스캔 이펙트),
E12-8(자체 점검 11/11), E12-9(체감 부하). 확인용 맵 `examples/spawn_ingame.eds`(혼자, 적 = 기준 맵 컴퓨터 P2, P1 맵 리빌러 격자로 시야).

**위험·미정**
- "바로 뒤 레코드 = 다음 층" 은 pool 의 순회 규칙에 기댄다(pool 이 순서를 바꾸면 층 간격이 한 프레임 밀린다 — 시험이 알려 준다).
- 명령·기본 명령은 원본처럼 2×2 상자 안의 같은 종류·주인 유닛 전부가 받는다. SC 가 유닛을 밀어내 상자 밖에 세우면 명령을 못 받는다(원본과 같음 — E12-1).
- `0x666458`(스캐너 스윕 스프라이트 이미지 칸)·Draw Function 은 원본 코드·DPS 관용구로만 확인(S1 12-5, E12-7).
- 에뮬레이터에는 맵 MRGN 이 없어 시험이 이름 있는 로케이션 사각형을 채운다. 로케이션 중심 계산(0 방향)이 SC 생성 위치와 같다는 가정은 plot 과 같음.
- 크기 변환 점당 실행이 목표의 세 배(D76). 128칸 대기열 페이로드가 목표 12KB 의 약 25배(D75).

**S1 8절(확정안)과 달라진 점과 이유**
1. **다음 층 필드(`next`)·시작 프레임(`start_frame`) 대신 `w`(대기)와 "앞 레코드가 끝나면 w = 2" 한 비트** — pool 이 넣은 순서로 순회하므로 다음 층은 늘 바로 뒤
   레코드다. 방문당 필드 적재 1·비교 1, 층 넘김 느린 쓰기 9 를 아꼈다. 뒤 층은 w = 0xFFFFFFFF 로 기다린다. 결과(층 사이 빈 프레임 1개)는 같다(D13).
2. **레코드 필드**: 8.5 표의 `sid, n, p` 대신 점 커서 `pc`·남은 점 `left`, 스케줄은 포인터 `sp`·끝 `se`(밴드 수를 읽지 않음), 명령 종류·전역 회전·
   다음 층·후처리·이펙트는 `flags` 비트, 이펙트는 `eff` 한 칸(이미지 | 색 << 16 | 색 있음 << 24). 20필드.
3. **소환 루틴 세 벌 + 사이클마다 고르기**(8.5 "spawn_one 한 벌"): 점마다 분기를 없애 점당 실행 62 → 58. 캡처·핸들러 분기는 필요한 작업만(넣을 때 flags).
4. **크기·회전·이펙트 코드는 주 함수 뒤 쓰인 것만** 채운다(페이로드 약 110KB 절약). 주 함수 뒤에 그 기능을 처음 쓰면 컴파일 오류.
5. **epScript 핸들러 `rtype_func(name, *fns)`**: 여러 개를 차례로(내장 + 사용자). 인자 5개 함수는 유닛 자리를 읽어 넘긴다. `sp.ctx` 로 SpawnCtx 동작.
   epScript 함수 이름은 정의 뒤에서 값으로 넘길 수 있음을 확인했다(WP7 의 "Undefined rvalue" 는 정의 앞에서 쓴 경우).
6. **명령·이펙트 모듈 함수** `spawn.attack/patrol/move/order/scan/at_unit` — epScript 에서 `spawn.Order.attack` 이 번역되지 않는다.
7. **API 더함**: `push_multi`(원본 CUTable 모양 + 수 불일치 검사), `preview`/`preview_count`(컴파일 시점 좌표 — 문구·자체 점검), `rtype_id`,
   `ctx`, `rotate_py`/`transform_py`, `Spawner(props=…, on_full=…, name=…)`, `SpawnCtx.pos/order/kill_all/set_invincible/set_order_id/set_parasite/
   set_remove_timer`, 내장 `force_order(order_id)`·`remove_timer(n)`·`nspeed(attack)`, `patrol_center` 별칭.
8. **`sp.rot3d`·`unclickable`·`variant`·`mirror`·`Effect.frag`** 는 2단계 자리(쓰면 컴파일 오류 — 지시대로).
9. **유닛 번호 범위 0~226**(원본 Call_Repeat 조건), 주인 P1~P12(CurrentPlayer 는 tick 안에서 뜻이 없어 컴파일 오류).
10. **spawn_now 의 명령 목표 로케이션은 넣는 순간 좌표**(원본 직접 경로는 명령 로케이션 모드가 동작하지 않았다 — S1 10-20).
11. **스캔 이펙트 색은 사이클마다 한 번** 바꾸고 되돌린다(원본은 점마다 — 같은 프레임 안이라 결과 같음, 점당 실행이 준다).
12. **rtype 0 은 "없음"**(원본 0 = 기본 어택): 기본 어택은 `sp.rtype("Home", sp.builtin.attack_default)` + `sp.default_rtype = "Home"` 로 둔다
    (맵마다 번호가 달라 고정 번호를 주지 않음).

---

### 4.15 `bullet` — 총알 — **WP14 완료(1단계)** · **WP21 완료(3단계, 4.15.1)**

> **2026-09-18 인게임 수정**: `BulletDat` 이 **배치 상자**(`buildingDimensions`)와 **유닛 충돌 크기**(`unitBounds`)를
> 쓰지 않아 탄이 **하나도 만들어지지 않았다**(통합 맵 bullet 단계 19발 전부 `epd = 0`, 표적 8기 생존). 탄막 유닛
> 208·210·204 는 문·함정이라 `Building` 플래그가 켜져 있고, `CreateUnit` 은 Building 유닛의 자리를 `buildingDimensions`
> 로 검사한다(EP81 `scdata/unit.py:319` 주석 — "31x31 이하면 물·절벽에도 지을 수 있다"). UE_RE EUD Editor 도 같은 칸을
> 쓴다(S4 2.6 "유닛 크기(unitBounds) 1, 배치 상자 0~1"). 그래서 `BulletDat(bounds=1, placement=1)` 을 기본으로 넣고,
> `base_property=None` 경로의 `flags(...)` 에 `Building=False` 를 더했다(직접 준 `base_property=0x20000004` 는 이미 0).
> 값 0 은 유닛을 보이지 않게 하므로 1 을 쓴다. 통합 맵에는 계측 `D14-0`(dat 값 5개 · 같은 자리 대조 마린 · 머리 전후 ·
> 첫 탄 epd)을 더해, 다시 실패하면 "빈 칸 없음 / 자리 문제 / 종류 문제 / dat 안 써짐" 을 한 번에 가른다.

**명세(정본)**: `docs/spec/S4_bullet.md`. API 는 S4 5절 + 아래 "초안과 달라진 점".

**근거**: 라이브러리 28장 함수는 0회. 사용자판은 **6계통**(M2 = Breeze 사본, UE_RE = UE, G2R = G2, M1, `Galaxy.py`, NewTestMap1 은 속도 헬퍼만), 주요 4맵 97회. theSeed·Stella_II·Respect_V·MEME·DPS·템플릿에는 정의도 호출도 없다. 정본 = UE_RE `Install_CBullet` 판(`reference/MapSource/MSF_UE_RE/func.lua:2~117`). DPS eudplib 이식판(a7aad90)에는 총알 코드가 없어 새로 작성했다.

**파일**: `eudext/bullet.py`, `tests/t_bullet.py`, `tests/ref_bullet.py`(참조 구현 — S4 기준 주소 + `ref_mathx` 방향), `examples/bullet_example.{eps,eds}`, `examples/bullet_ingame.{eps,eds}`(인게임 D14).

**공통 핵심**(S4 3절): 새 유닛 칸 읽기(`0x628438`) → 로케이션을 한 점으로 옮겨 생성 → 위치(+0x28)를 주문 목표(+0x58)로 복사 → 방향(+0x21), 주문(+0x4D) ← 135. 판별 차이(만드는 유닛, 소유자, Y 보정, 수명 칸, 상태 플래그 칸, 방향 인자 대 `f_Atan2`)는 `BulletKind` 옵션으로.

**API**

```python
from eudext import bullet
from eudext.bullet import BulletKind, BulletDat

bullet.setup(loc="eudext.bullet")      # 총알 로케이션 (맵의 이름 또는 1-based 번호. Anywhere(64) 금지)
k = BulletKind(unit=208, weapon=127, flingy=106, reverse=True, shell=None, recipe="ue_re",
               remove_timer=None, y_offset=0, dat=None)          # recipe: "ue_re" | "m2" | "minimal"
epd = bullet.bullet(k, owner, x, y, facing, height=None)          # = f_bullet     (CreateBullet)    실패 0
epd = bullet.bullet_to(k, owner, x, y, tx, ty, height=None)       # = f_bullet_to  (CreateBulletXY, 1프레임)
epd = bullet.bullet_at(k, owner, loc, facing, height=None)        # = f_bullet_at  (CreateBulletLoc)
f = bullet.heading_to_facing(k, heading)                          # 진행 방향 → 유닛 방향 (reverse 면 +128)
acts = k.speed_actions(v, halt=None); k.time_actions(t); k.height_actions(h)   # 상수 → 액션 목록 (전역 dat)
k.set_speed(v, halt=None); k.set_time(t); k.set_height(h)         # 그 자리 실행 (변수 가능)
acts = k.init_actions(); k.install()                              # BulletDat 묶음: 액션 목록 / datpatch 시작 1회 목록
k.timer, k.made_unit                                              # 실제 수명 값(None = 안 씀), CreateUnit 에 쓰는 유닛
BulletDat(unit_flingy=88, elevation=20, flyer=True, invincible=True, base_property=None, idle_order=None,
          attack_order=None, ground_weapon=True, weapon_flingy=None, behavior=9, explosion=3, splash=(96, 96, 96),
          damage=60000, bonus=0, cooldown=1, remove_after=None, attack_angle=None, sprite=None, top_speed=8000,
          accel=None, halt=1, turn=127, move_control=0)           # None = 그 필드를 쓰지 않음. 기본 = UE_RE 208/127/106
bullet.DEFAULT_LOC, bullet.ORDER_FIRE, bullet.RECIPES
# 3단계(WP21, 4.15.1): CtrigKind, f_storm, f_perma_sprite, f_scan_sprite, f_unit_sprite, f_recall_sprite,
#   f_scan_init(_actions), f_scan_image_actions/f_set_scan_image, f_recall_image_actions/f_set_recall_image
```

epScript: `import eudext.bullet as bullet;` → **`bullet.bullet(k, P8, x, y, 64)`**(번역 `bullet.f_bullet`). `bullet.f_bullet(…)` 이라고 쓰면 `bullet.f_f_bullet(…)` 로 번역되므로(실측) 모듈이 "`bullet.bullet(…)` 로 부르세요" 안내 오류를 낸다. `BulletKind`·`BulletDat` 은 `const` 로 묶고, `k.install();`·`bullet.setup(…);` 은 전역 문장으로 둔다. 묶음 값은 `splash=list(8, 8, 8)`. 번역·에뮬레이터·euddraft 빌드 확인: `examples/bullet_example.eps`.

**의미·제약**
- `facing` 은 **유닛 방향**(SC 256, 0 = 위, 시계)이고 하위 8비트만 쓴다(−64 → 192 = UE_RE 보정과 같은 값). 사용자 맵의 총알 flingy 는 최고속도가 음수라 **실제 진행 = facing + 128**(S4 2.3). `reverse=True`(기본)가 이 관례이고 `bullet_to`·`speed_actions`·`BulletDat.top_speed` 가 따른다.
- 방향 계산은 `mathx.atan2` + `mathx.to_dir256`(D5 — CtrigAsm 과 같은 값): reverse 면 `to_dir256(atan2(y − ty, x − tx))`, 아니면 `atan2(ty − y, tx − x)`. 출발 = 목표 → facing 128. 좌표가 모두 상수면 컴파일 시점에 구한다.
- 속도·수명은 전역 dat → **같은 프레임 같은 flingy/무기의 총알은 마지막 값을 함께 쓴다**(R4a A.4). 그래서 인자가 아니라 `k.speed_actions`/`time_actions`(상수 액션 목록)와 `k.set_speed`/`set_time`(변수)으로 준다. `speed_actions` 의 v 는 0~65535(가속도 칸이 word), reverse 면 최고속도 ← `0xFFFFFFFF − v`(사용자판 값). 변수 `set_speed(v)` 는 최고속도 ← 0xFFFFFFFF 뒤 `Subtract v`(포화지만 결과가 같음 — 3.5-7).
- **높이 인자는 사용자판 모두 틀린 주소**에 썼다(UE_RE 는 weapons attackAngle[유닛 번호] → 무기 17·18 최소 사거리). eudext 는 units.dat elevation[만드는 유닛](shell 이면 shell)에 쓴다. 옛 동작은 옮기지 않았다(시험이 0x656990 + 130 ~ minRange 표 끝에 쓰지 않음을 확인).
- 소유자: P1~P12(0~11)·CurrentPlayer(13 — CreateUnit 때의 CP) 상수, 또는 변수.
- 생성 성공 확인은 `units.capture` 와 같은 판정(`Memory(0x628438, Exactly, 생성 전 ptr)`). 빈 칸이 없거나 생성이 실패하면 **CUnit 칸을 쓰지 않고 0** 을 돌려준다(사용자판은 빈 칸을 고쳤다, R4a A.8). 반환 EPD 는 0 확인 뒤 쓴다.
- `bullet_at` 은 그 로케이션에 바로 만든다(총알 로케이션을 옮기지 않음). `y_offset` 은 적용하지 않는다(M2·Galaxy.py 와 같음).
- CP 바꾸지 않음(본문이 CP 를 잠깐 옮겨 칸을 쓰고 `f_setcurpl2cpcache`). 공유 안전(공유 상태만 읽고 쓴다). 스프라이트는 읽지 않는다.

**알고리즘** (S4 5.2 를 이렇게 구현)
1. `Memory(0x628438, Exactly, 0)` 이면 실패 트리거로 — 자기 next 를 바꾸는 트리거 1개(실패 트리거가 되돌린다. EUDBranch 의 절반).
2. `units.next_slot()` → ptr, epd.
3. (to) `dy`·`dx` 뺄셈 → `mathx.atan2` → `mathx.to_dir256`.
4. SeqCompute 한 번: 로케이션 L·T·R·B ← x·y, CreateUnit 액션의 소유자 칸·유닛 칸(dword `유닛 | 44<<16 | 1<<24` 를 상수 인자로) ← 인자, 생성 판정 조건의 비교값 ← ptr, [shell 종류 칸, 높이 액션의 주소·값·마스크 칸, 상수 방향 칸].
5. 한 트리거: [elevation ← height] → [T·B += y_offset] → `CreateUnit`.
6. `Memory(0x628438, Exactly, ptr)` 이면 실패 트리거로(1과 같은 방식).
7. (변수 방향) 방향의 비트 8개를 칸 쓰기 액션의 값 칸에 `<<8` 로 쌓는다(비트당 조건 트리거 1, 곱셈 없음).
8. CP ← epd + 10 (VProc 한 번: `SetMemory(CP, SetTo, 10)` + `epd.QueueAddTo(CP)`).
9. 위치 32비트 복사: eudplib `f_maskread_cp(0, 0xFFFFFFFF, ret=[EPD(칸 쓰기 액션) + 5])` — 게임 시작 때 이미 있는 표 읽기 사슬이 CP 칸을 읽어 **액션 값 칸에 바로** 쓴다(변수 복사 없음). m2 는 변수로 읽어 4칸에.
10. 칸 쓰기 한 트리거: CP 상대 `SetDeaths(X)`(unit 칸 = 12 의 배수 거리) + `SetMemory(0x6509B0, Add, 차)`.
11. `f_setcurpl2cpcache(v=[epd], actions=epd.QueueAssignTo(반환값))` 한 VProc. 실패 트리거 = 반환값 0 + 1·6 의 next 복구.
- 본문 키: (방식 own/at/to, 방향 상수/변수, recipe, y_offset, 수명, shell 여부, 높이 여부, 로케이션 번호, reverse(to 만)). `unit`·`shell`·높이 칸은 상수 인자라 본문을 나눠 쓴다. 반환값은 `_compat.predefine_returns`.
- 변수 높이가 바이트 경계가 아닌 유닛(번호 % 4 ≠ 0)은 호출 자리에서 시프트 도우미(비트당 조건 1, 본문 9 1벌 — eudplib filler 의 바이트 채우기와 같은 방식)를 거친다. `set_speed`(홀수 flingy 가속도, 도우미 17)·`set_time`·`set_height` 의 변수 값도 같은 도우미 + `SetMemoryX` 1액션.

**비용** (docs/COSTS.md "bullet (WP14)"): 본문 12(상수 방향)·20(변수 방향)·24(m2 변수)·11(at)·26(to, + mathx atan2 182·to_dir256 43 1벌) — **목표 ≤ 40 통과**. 호출 자리 1(변수 인자는 그 변수 트리거를 VProc 으로 이어 붙인다), 변수 높이 2 — **목표 ≤ 3 통과**. 실행 74~92, to 약 235, 빈 칸 없음 7(to 9). 한 번 페이로드: 상수 방향 본문 +4.7KB(`units.next_slot` 9.8KB 는 units 와 공유), 변수 방향 +7.2KB, `bullet_to`(변수 좌표) 약 139KB(atan2 공유 본문 111KB 포함), 상수 좌표 `bullet_to` 14.7KB.

**시험**: `tests/t_bullet.py` (5,462 판정, 약 9초) — S4 6.1 표(360→256, `bullet_to` 10줄, reverse 두 식 128 차이 2만 쌍, 상수 좌표 방향 = 참조 4만), 6.2 표 11줄 + speed(209 flingy × 5 값 × reverse)·time(130)·height(228, shell 칸) 전수, BulletDat = UE_RE `EUDEditorDat.lua` 의 (A → B) 결과(208/127/106 과 210/128), 금지 칸, 6.3(정상 19445 표, 음수 방향, 슬롯 없음·생성 실패 — own/to/at·높이, shell, y_offset, m2, CP 여섯 값 × 성공·실패 경로, owner=CurrentPlayer), **생성 뒤 CUnit 84칸 전부**(보초값으로 채워 마스크 밖 비트·안 쓰는 칸 보존), **게임 메모리 쓰기 집합 ⊆ 허용 집합**(칸·0x628438·활성 목록·로케이션·elevation), 종류 10가지 × 방식 조합(무작위·경계 좌표), 실패 뒤 분기 복구, 한 사이클 여러 발, 변수 방향 300·`bullet_to` 800 차등, heading_to_facing, set_speed/time/height(상수·변수·섞기), install() 이 시작 목록에 들어감, 빌드 오류 18종, epScript 예제(4 사이클)·인게임 맵(700 사이클) 번역·에뮬레이션·euddraft 빌드.
**인게임**: `docs/INGAME_CHECKLIST.md` D14-* — 필수 D14-1(진행 = facing + 128·명중)·D14-2(`bullet_to` 8방향·가까운/먼 목표·같은 점)·D14-3(칸 가득 → 0)·D14-6(+0xA3·+0xDC·+0xE4)·D14-8(종류 교체 뒤 무기). 확인용 맵 `examples/bullet_ingame.eds`(혼자, P2 컴퓨터 표적, dat 는 맵 안 BulletDat).
**위험**: 음수 최고속도 관례와 ue_re 추가 칸의 뜻은 인게임 전 가정. 영구 dat 부작용(R4a A.8) — BulletDat 는 iscript 를 바꾸지 않는다. 언리미터에서 eudplib `CSprite.from_read` 가 틀린 포인터(R4a A.6) — bullet 은 스프라이트를 읽지 않는다. 위치 복사는 eudplib 0.81 `f_maskread_cp` 의 `ret=[EPD 식]` 경로(`memio/readtable.py:_cp_caller`)에 기댄다 — 판이 오르면 시험(칸 값 비교)이 알려 준다. 옛 G_CA 의 `RepeatType 101`(탄막)은 spawn 의 `on_point` 콜백으로 대체(S4 5.5).

**초안과 달라진 점과 이유**
1. **epScript 이름**: S4 5.1 의 `bullet.f_bullet(…)` 은 `f_f_bullet` 로 번역된다(실측) → 문서·예제는 `bullet.bullet(…)`, 모듈 `__getattr__` 이 `f_f_` 이름에 안내 오류.
2. **`bullet_at`**: "로케이션 중심 → 좌표를 읽어 `f_bullet`" 대신 그 로케이션에 바로 만든다(M2·Galaxy.py 원본과 같고, dword 4개 읽기·나눗셈이 없다 — 실행 71). 그래서 `y_offset` 은 적용하지 않는다(결정 요청 D35).
3. **`setup`**: 다시 불러도 된다(본문이 로케이션마다 따로 — "한 번만" 을 강제하면 epScript 모듈을 빌드 사이에 불러올 때 거짓 오류가 났다). 이름은 본문을 만들 때 번호로 바꾸고, 맵에 없으면 안내 오류. Anywhere(64) 금지.
4. **다음 칸 읽기**: S4 의사코드의 `f_cunitepdread_epd` 대신 `units.next_slot()`(units 와 같은 판정 계열 — 지시 사항) + 앞에 빈 칸 검사 1트리거(가득 찼을 때 실행 7).
5. **위치·방향 쓰기**: 위치는 변수를 거치지 않고 표 읽기 사슬이 액션 값 칸에 바로(32비트 전부 — 맵 안 좌표를 가정하면 실행 3 을 더 줄일 수 있지만 가정을 두지 않음). `facing·256` 은 곱셈·`f_bwrite_epd` 대신 상수면 인자에서, 변수면 비트 8개를 액션 값 칸에 쌓는다(S4 5.2 "싼 방법을 구현 때 측정해 고른다").
6. **본문 키**에 방식·방향 상수/변수·로케이션을 더했다. **상수 좌표 `bullet_to`** 는 컴파일 시점에 방향을 구해 atan2 본문(111KB)을 끌어오지 않는다.
7. **더한 API**: `k.set_height(h)`(set_speed/set_time 과 대칭), `k.install()`(BulletDat → datpatch 시작 1회 목록 — S5 "시작 시 1회 목록에 쌓는다"), `k.timer`·`k.made_unit`, 상수 `DEFAULT_LOC`·`ORDER_FIRE`·`RECIPES`.
8. **BulletDat**: `base_property`(UE_RE 210 은 특수 능력 dword 전체를 씀)·`attack_order`·`ground_weapon`·`attack_angle`(**무기 번호** 칸 — UE_RE 128 은 0)·`accel`·`bonus`·`sprite`(UE_RE 106 은 344)를 더했다. 기본값은 UE_RE 208/127/106 그대로(시험이 `EUDEditorDat.lua` 결과와 대조) — `idle_order` 는 UE_RE 208 이 바꾸지 않았으므로 None(S4 5.4 초안의 2 는 M2 값). 유닛 행(그림·높이·특수 능력·주문)은 shell 에도 쓰고 지상 무기는 unit 에만.
9. **`set_*` 변수 값**: datpatch `now`(scdata 쓰기 — 호출 자리 34) 대신 시프트 도우미 + `SetMemoryX`(호출 2~5).
10. owner 검사(P1~P12·CurrentPlayer), `heading_to_facing` 변수 결과도 `& 0xFF`.

#### 4.15.1 3단계 — CtrigAsm 28장 스프라이트 함수 — **WP21 완료**

**근거**: R4a A.1~A.8, CtrigAsm v5.5 원문(`reference/MapSource/Library/CtrigAsm v5.5.lua:81159~81828` — `RecallSprite`·`UnitSprite`·`ScanSprite`·`ScanInitSetting`·`BulletInitSetting`·`CreateStorm`·`CreateSprite`·`SetRecallImage`·`SetScanImage`), 가이드북 28장(7868~8157)·예제 28-1(18028~18053)·29-4~29-10. 사용 0회(DESIGN 0.2 "하") → 원리가 A.3 에 있는 다섯 함수와 그 준비 함수만 옮겼다. DPS 이식판(a7aad90)에는 해당 코드가 없다(새로 작성).

**파일**: `eudext/bullet.py`(1단계 뒤에 덧붙임 — 1단계 API·동작은 그대로, `t_bullet` 5,462 판정 통과), `tests/t_sprite.py`, `examples/sprite_ingame.{eps,eds}`(인게임 F21, CGRP 포함).

**API**

```python
from eudext import bullet
from eudext.bullet import CtrigKind

k = CtrigKind(unit, weapon, flingy, sprite, image, iscript, color=0, unit_flingy=74, unit_sprite=229,
              half_air=False, damage=0, damage_bonus=0, upgrade=0, count=1, damage_type=0, explosion=0,
              splash=(0, 0, 0), carrier_iscript=86, remove_timer=None, y_offset=-2)   # BulletInitSetting
acts = k.init_actions(); k.install()          # A.2 표(원문과 같은 칸·값) + 이미지 256 iscript ← 86
e = bullet.storm(k, owner, x, y, facing, image, time, height=None)         # = f_storm        (CreateStorm)
e = bullet.perma_sprite(k, owner, x, y, facing=0, speed=0, height=None)    # = f_perma_sprite (CreateSprite)
bullet.scan_sprite(owner, x, y, count=1, remove=True)                      # = f_scan_sprite  (ScanSprite, 반환 없음)
e = bullet.unit_sprite(owner, unit, x, y, height=None, time=None, track=True)   # = f_unit_sprite (UnitSprite)
bullet.unit_sprite(owner, unit, x, y, height=None, track=False)            #   (UnitSprite Time="X", 반환 None)
e = bullet.recall_sprite(owner, unit, x, y, loc=None)                      # = f_recall_sprite (RecallSprite)
bullet.scan_init(); acts = bullet.scan_init_actions()                      # ScanInitSetting (시작 1회 / 액션)
acts = bullet.scan_image_actions(i); bullet.set_scan_image(i)              # SetScanImage / TSetScanImage
acts = bullet.recall_image_actions(i); bullet.set_recall_image(i)          # SetRecallImage / TSetRecallImage
bullet.RECIPES == ("ue_re", "m2", "minimal", "ctrig"); bullet.ORDER_CAST_RECALL (137), SCAN_UNIT (33),
bullet.SCAN_SPRITE (380), bullet.RECALL_SPRITE (379)
```

epScript: `bullet.storm(…)`·`bullet.perma_sprite(…)` 등(번역 `bullet.f_storm` …). `bullet.f_storm(…)` 은 `f_f_storm` 이 되어 모듈이 안내 오류를 낸다(1단계와 같은 `__getattr__`). `CtrigKind` 는 `const`, `k.install();`·`bullet.scan_init();` 은 전역 문장.

**의미·제약**
- `CtrigKind` 는 `BulletKind(recipe="ctrig", reverse=True, y_offset=-2)` 에 A.2 표를 더한 하위 클래스다. `ctrig` 칸 쓰기(CA:81522~81527): +0x58 ← 위치(+0x28 복사), +0x21 ← facing, +0x4D ← 135 **와 +0x4E·+0x4F ← 0**(마스크 0xFFFF00), +0x110 ← 6. `BulletKind(recipe="ctrig")` 로도 고를 수 있다(수명 기본 6).
- `init_actions()`/`install()` 은 원문 `BulletInitSetting` 의 모든 쓰기와 같은 바이트를 쓴다(시험이 원문 줄을 정규식으로 읽어 가이드북 예제 9벌 + 무작위 40벌 대조). 다른 점: `weapons.flingy` 는 datpatch 표가 바이트 칸이라 윗 3바이트(원문은 0)를 쓰지 않는다 — 원래 값도 0. 이미지 256 iscript ← 86 은 원문이 CreateBullet 류를 **부를 때마다** 쓰는 줄인데 값이 상수라 시작 1회 목록에 넣었다(`carrier_iscript=None` 이면 안 씀).
- `storm`/`perma_sprite` 는 부를 때마다 전역 dat 를 먼저 쓰고(1 트리거) `bullet(k, …)` 과 같은 본문을 부른다. storm: 무기 투사 방식 ← 3, removeAfter ← time, 이미지 iscript ← 236·전체 iscript ← 1(원문 CA:81686~81701). perma: 투사 방식 ← 7, flingy 최고속도 ← **−speed**(원문과 같음 — 1단계 `speed_actions` 의 0xFFFFFFFF − v 와 1 차이, speed 0 이면 정확히 0 이라 CGRP 점이 움직이지 않는다). 변수 speed 는 `0xFFFFFFFF ⊖ v` 뒤 `Add 1`(3.5-7). 같은 프레임 같은 무기·flingy 의 마지막 값이 모두에 적용된다(A.4). **빈 칸이 없어도 dat 는 쓴다**(원문은 CIf 안 — 결정 요청 D69).
- `scan_sprite`: 로케이션 ← (x, y), [remove 면 스캐너 컴퓨터·사람 대기 주문 ← 0], `CreateUnit(count, 33)`, [대기 주문 ← 140] 을 **한 트리거**에(원문 CA:81315~81365). 칸 연산이 없어 0틱 연산이 되고 빈 칸 검사·생성 확인도 없다(원문과 같음). count 는 상수 1~255 또는 변수(하위 8비트). 높이 4 고정, 한도 500~600(GB 8562).
- `unit_sprite`: track=True 는 본문(`recipe="unit_sprite"`, 방향·위치 읽기 없음)으로 생성 뒤 [+0x110 ← time(마스크 0xFFFF)], +0xDC |= 0x100, +0xE4 ← 0(원문 CA:81302~81309). time 은 상수·변수(변수는 값 칸 자리 표시), None·0 이면 안 씀. track=False 는 원문 `Time="X"` — 높이·로케이션·CreateUnit 만(반환 None, time 금지). unit 은 상수만(높이 칸 주소를 컴파일 시점에 정함 — 원문은 변수도 받았다).
- `recall_sprite`: 본문(`recipe="recall"`, 방향 없음)으로 생성 뒤 +0x58 ← x(마스크 0xFFFF)·y·65536(마스크 0xFFFF0000), +0x4D ← 137, +0x110 ← 3(원문 CA:81193~81197). loc=None 이면 총알 로케이션을 (x, y) 로 옮겨 그 자리에, loc 을 주면(이름·1-based 번호, 상수·변수) 그 로케이션에 아비터를 만든다(예제 28-1 은 "CLoc2"). 변수 y 는 시프트 도우미(16비트, 본문 17 1벌). 0틱 불가, 리콜 마나 0 권장(예제: `techdata.energyCost[21] = 0`).
- `unit_sprite`·`recall_sprite`·`storm`·`perma_sprite` 는 1단계와 같은 판정으로 **빈 칸 없음·생성 실패면 0 을 돌려주고 칸을 쓰지 않는다**(원문은 확인 없음).
- 로케이션 Y 보정: CtrigKind 는 −2(원문 CreateBullet 류), scan·unit·recall 은 보정 없음(원문과 같음).
- CP 바꾸지 않음, 공유 안전(공유 상태만 쓴다 — 가이드북의 "비공유 렌더링"은 쓰지 않는다).

**알고리즘 추가(1단계 본문에 덧붙인 것)**: `_Key.facing = "none"`(방향 인자·칸 없음), recipe `ctrig`·`unit_sprite`·`recall` 의 `_patch_actions` 분기, 위치 읽기는 `ue_re/m2/minimal/ctrig` 만(`_POS_RECIPES`), 값 칸 자리 표시 `extra = {rx, ry, tm}`(SeqCompute 로 채움). 칸 연산 없는 생성은 따로 `_plain_body(_PKey(loc, height, scan_remove))`(SeqCompute + 한 트리거, 본문 3~4). 변수 이미지 storm 은 공유 본문 `_storm_image_fn`(iscript 칸 EPD = 기준 + img 더하기, 전체 iscript 바이트는 img 비트 2~9 → EPD·비트 0~1 → 값·마스크, 본문 20 — datpatch `now`(scdata) 는 호출 자리 56 이었다).

**비용** (조각 costs.md "bullet 3단계 — 28장 스프라이트 (WP21)"): storm·perma(상수 dat) 본문 12(ctrig 본문, CGRP 와 공유)/호출 2/실행 77, perma 변수 속도 호출 3/실행 79, scan 본문 4/호출 1/실행 13(변수 수 호출 3·실행 28), unit_sprite 본문 11/호출 1/실행 41~47, track=False 본문 4/호출 1/실행 13, recall 본문 10/호출 1~2/실행 37~66, set_scan_image 변수 호출 2/실행 3, set_recall_image 변수 호출 3/실행 24 — **목표(본문 ≤ 40·호출 ≤ 3) 통과**. 예외: storm 을 변수 이미지·수명·높이로 부르면 호출 6(변수 dat 인자 3개가 각각 도우미·패치를 거침 — 이미지 공유 본문 1 + 수명 도우미 1 + 변수 값 액션 2 + 높이 도우미 1 + 본문 1), 실행 128. 한 번 페이로드: perma_sprite(본문 + `units.next_slot` 포함) 약 17KB, 변수 인자 storm 약 30KB, 변수 recall 약 20KB.

**시험**: `tests/t_sprite.py` (2,500 판정, 약 23초) — 원문 대조 452(BulletInitSetting 49벌 바이트, CreateStorm·CreateSprite dat 줄(4종류 × 이미지 6 × 수명 4, 속도 7), ScanInitSetting, SetScanImage·SetRecallImage 이미지 0~998 전부, ScanSprite 대기 주문 줄, 칸 쓰기 표 4종), CtrigKind·이미지 함수 인자 검사 17+7종. 에뮬레이터 2,021: storm(종류 4 × 무작위·경계 14 + 상수 3 + 칸 없음·실패)·perma(종류 4 × 12, 속도 경계 0·1·0x7FFFFFFF·0x80000000·0xFFFFFFFF)·scan(변수 수 0x100·0x12345603 포함 16, remove 둘 다, 생성 순간 대기 주문 0 → 뒤 140·옆 비트 보존)·unit_sprite(유닛 3종 × 시프트 × 수명 경계 10, track=False, time=0, 이름)·recall(제자리·로케이션 14씩, x·y > 0xFFFF)·이미지 쓰기(변수·상수)·시작 1회 목록·CP 여섯 값 × 세 경로 × 다섯 함수·한 사이클 여섯 발. 판정은 **CUnit 84칸 전부**(보초값), **원문 식으로 계산한 칸 쓰기 표**, 생성 순간의 높이·대기 주문(CreateUnit 처리기로 기록), dat 값과 옆 비트, **게임 메모리 쓰기 집합 ⊆ 허용 집합**. 빌드 오류 28종. 인게임 맵 번역·에뮬레이션(710 사이클 — 점 16·스톰 2·레이스·스캔·리콜·합성 CGRP 120점·칸 가득 0)·euddraft 빌드([unlimiter] 포함). 변이 시험(시험 파일 밖): 상수 8가지를 틀리게 바꾸면 모두 실패로 잡힌다(iscript 236→235, 대기 주문 140→139, 리콜 주문·수명, 발사 주문, A.2 표 한 칸, −speed, 엉뚱한 칸 한 바이트).

**인게임**: `INGAME_CHECKLIST` F21-* — 필수 F21-1(영구 점·튕김)·F21-2(스톰)·F21-3(표시용 유닛·드래그 방지)·F21-4(스캔)·F21-5(리콜)·F21-6(합성 CGRP)·F21-7(**실제 CGRP 파일** — 사용자 파일 필요). 확인용 맵 `examples/sprite_ingame.eds`(혼자, `[unlimiter]`).

**위험**: iscript 86·236 과 대기 주문 140 의 뜻, 음수 최고속도·투사 방식 7 의 "영구" 동작, +0xDC 0x100·+0xE4 의 드래그 방지는 원문·가이드북 근거뿐(인게임 F21). 영구 부작용(R4a A.8): 벌처 이미지(256) iscript, storm 이미지 iscript 236, 스캐너 크기 0, 고른 유닛의 units.dat — 맵의 진짜 벌처·스캐너가 깨진다. 흰색(화면 출력 17) 영구 스프라이트는 42틱 뒤 튕김(GB 8466) — 막지는 않고 문서화. 리콜은 실제 시전이라 목표 근처 소유자 유닛이 끌려올 수 있다(F21-5 에서 확인). 스프라이트를 읽지 않는다(A.6).

**초안(R4a A.7 스케치)과 달라진 점과 이유**
1. **종류 객체**: 스케치의 `BulletKind(… image, iscript …)` 대신 `CtrigKind(BulletKind)` 하위 클래스 — 1단계 `BulletKind` 를 바꾸지 않기 위해. 이름·인자 순서는 원문 `BulletInitSetting` 을 따른다(unit_flingy·unit_sprite 기본 74·229 = 가이드북 예제 값). 스케치의 `bullet_setup(*kinds)`·종류 번호 표(런타임 색인)는 두지 않았다(본문은 상수 인자로 나눠 씀 — 1단계와 같음).
2. **`f_storm`** 에 facing 을 더했다(원문 CreateStorm 의 Angle). height 는 선택.
3. **`f_perma_sprite`**: facing·speed 기본 0. 최고속도는 원문대로 −speed.
4. **`f_scan_sprite`**: 스케치의 image 인자·die 대신 원문처럼 이미지는 `scan_image_actions`/`set_scan_image` 로 따로(전역 dat), `remove`(원문 RemoveScan), `count`(원문 Number).
5. **`f_unit_sprite`**: 스케치의 `nodrag` 는 두지 않았다 — 원문은 칸 연산 판에서 +0xDC·+0xE4 를 늘 쓰고, 따로 켜고 끄는 원리는 확인하지 못했다(결정 요청 D73). 원문 `Time="X"` 는 `track=False`.
6. **`f_recall_sprite`**: 스케치의 image 인자 대신 `recall_image_actions`, 아비터 자리 `loc`(원문의 로케이션 인자) 추가.
7. 스케치의 `BulletFrame`(같은 프레임 값 충돌 감지, 선택)은 만들지 않았다.
8. 이미지 256 iscript ← 86 을 부를 때마다 → 시작 1회(D70). storm/perma 의 dat 는 빈 칸이 없어도 쓴다(D69).
9. 원문 `CreateBullet`·`CreateBulletTarget`(부를 때마다 투사 방식 9·−속도·수명)은 옮기지 않았다 — 1단계 `bullet`/`bullet_to` + `k.speed_actions`/`time_actions` 로 대신한다(D71).
10. 생성 확인(0 반환·칸 안 씀)을 더했다(1단계와 같은 판정, 원문 없음).

---

### 4.16 `datpatch` — dat 필드 표 — **WP15 완료**

**명세(정본)**: `docs/spec/S5_dat_bgm.md` A절. **API 는 S5 A.7 이 정본**이고, 구현하며 더하거나 바꾼 것은 아래 API·"명세·초안과 달라진 점" 에 있다.

**근거**: `PatchInsert*` 614, `SetUnitsDatX`/`SetWeaponsDatX`/`SetUnitAbility` 336, 8맵(R1). 정본 = 템플릿 `func.lua`, theSeed 판이 필드가 가장 많다. 적용은 게임 시작 1회(`InitCtrig`) + 매 프레임·조건부 큐, **되돌리기는 어느 판에도 없다.**
**scdata 대비**(S5 A.4): 실제 쓰기 6,875건 중 **89.9% 가 scdata 멤버 하나로 그대로**, 97.3% 가 부분 대응(호출 지점 기준 52.1% / 74.1%). eudext 표에 넣을 것은 플레이어별 표(생산 가능 `0x57F27C` 등)·Addon/Subunit2/Infestation·SpecialAttack·피해 배율(주소 확인 후)뿐이다.
구현: `eudext/datpatch.py`, `eudext/datpatch_tables.py`, `_compat.py` 끝 WP15 블록. DPS 이식판(a7aad90)에는 dat 패치용 파이썬 코드가 없다(Lua 헬퍼를 lupa 로 돌림). 바이트·워드 규칙은 CtrigAsm `SetMemoryB/W`(CA:43497~43541)를 따랐다.

**API** (구현된 것)

```python
from eudext import datpatch as dat
# 시작 1회 목록 (상수만). 필드 이름 = scdata 멤버 이름 + eudext 전용(buildingDimX/Y, computerAI, subunit2,
#   addonPlacement(X/Y), infestationUnit, specialAttack, images 의 grpFile·overlay 6종, players.unitAvailability, damage.ratio)
dat.unit(208).set(maxHp=5000 * 256, elevation=20); dat.unit("Terran Marine").set(armor=1)
dat.unit(208).flags(Flyer=True); dat.unit(1).flags("groupFlags", Zerg=True)
dat.unit(162).mask("baseProperty", 0x400200, 0x480200); dat.unit(3).set(buildingDimensions=(3, 4))
dat.weapon(1).splash(7, 14, 21)                  # explosionType 3(SplashEnemy, TEP "일방형") + 반경
dat.flingy(i) / dat.upgrade(i) / dat.tech(i) / dat.sprite(i) / dat.image(i)
dat.player_unit_enable(unit, players, value=1)   # 0x57F27C + P·228 + U
dat.damage_ratio(피해형, 크기, 값)                  # 0x515B88 + 0x14·피해형 + 4·크기 — 인게임 확인 전(경고)
dat.raw(액션…); dat.from_eud_editor(경로 또는 목록, table="EUDEditorDatActs"); dat.parse_eud_editor(…)
# TEP 이식 층 (키·변환 그대로)
dat.tep.SetUnitsDatX / SetWeaponsDatX / SetUpgradesDatX / SetFlingyDatX / SetSpritesDatX / SetImageDatX
dat.tep.SetDamageRatio / PatchInsert / PatchInsertPrsv / SetUnitAbility(TPL 18인자, variant="seed")
# 목록·내보내기
dat.start(); dat.every_frame()                   # PatchList
acts = dat.actions(lambda d: …)                  # 파이썬
dat.begin_actions(); …; acts = dat.end_actions() # epScript
dat.emit(acts, preserved=True, chunk=64)          # 그 자리에 64개씩 조건 없는 트리거
dat.PatchList(name)                               # 따로 모으는 목록 (.unit … .actions(merge) .emit() .entries())
# 즉시 쓰기·되돌리기
dat.now.unit(u).set(maxHp=v)                      # 번호·값 변수 가능
with dat.temporary(restore=True): dat.now…       # 파이썬
dat.begin_temporary(); …; dat.end_temporary()    # epScript
dat.unpatch_all()
# 정보
dat.field("units", "maxHp"); dat.field_names("units"); dat.addr("weapons", "damage", 127)
dat.values(a, b)                                  # epScript 묶음 값 (list(a, b) 도 됨)
dat.simulate(목록, 메모리)                          # 시험·확인용 파이썬 적용기
dat.clear(); dat.set_debug(True)
```

**의미**
- **scdata 대입문은 한 줄 = 트리거 1개**다. 시작 패치 수백 줄을 그대로 쓰지 않고, **scdata 디스크립터의 주소 정보(offset/stride/size)만 빌려 원시 액션을 모아 64개씩** 낸다.
- 템플릿 결함: `WhatSndInit/End` 이름이 eudplib·EUD Editor 와 **반대**, `Reqptr` 는 아무 일도 안 함, Breeze `PatchInsert` 3줄 미적용(추측). `dat.tep` 은 TEP 동작을 보존하고 경고한다(7절 D19).
- 선택 기준(S5 A.6): CHK 로 되는 값은 맵 편집기, 한 필드의 출처는 하나, EUD Editor Add 차분 주의, dataDumper 는 dat 배열에 해당 없음.
- 시작 목록: 선언은 상수만. scdata 디스크립터의 offset·stride·크기로 원시 액션(`SetMemory`/`SetMemoryX`)을 만들고,
  **같은 dword 에 연달아 쓰는 SetTo 를 한 액션으로 합친 뒤**(사이에 그 주소 Add/Subtract 나 모르는 액션이 있으면 끊음)
  **64개씩** 조건 없는 트리거로 낸다. 실행은 게임 시작 1회, 주 함수(onPluginStart·beforeTriggerExec)보다 먼저.
- 등록 시점: import 때(빌드 밖) 선언 = 빌드마다 적용되는 "계속" 목록, 빌드 중(onPluginStart 등) 선언 = 그 빌드에만.
  빌드 밖 선언은 `EUDOnStart` 로 훅을 걸고, 훅이 `eud_onstart2`(주 함수 뒤 생성 목록)에 내보내기를 건다
  → 주 함수 안의 선언까지 한 번에 낸다. 주 함수를 다 만든 뒤(다른 시작 함수 안 등)에 선언하면 `EudextError`.
- 매 프레임 목록: 게임 루프 시작점 훅(eudplib `_on_game_loop_start`) — beforeTriggerExec 앞에서 매 프레임 64개씩.
- `now`: 상수 번호·값 = `SetMemoryX` 1액션(한 `set` 호출의 상수 쓰기는 한 트리거). 변수 번호·값 = scdata 멤버 쓰기
  (`setattr(TrgUnit.cast(i), 이름, v)`), eudext 전용 필드는 epd·subp 직접 계산 + `f_bwrite/wwrite/dwwrite_epd`.
- `temporary`: 폭 4 는 `f_dwpatch_epd` 바로, 폭 1·2·비트는 "dword 읽기 → 바꿀 부분만 합치기 → f_dwpatch_epd".
  변수 번호로 subp 가 변하면 가능한 subp 값마다 분기. 끝에서 `f_unpatchall`(스택 전체). 겹쳐 열기 금지.
- 값 검사: 필드 폭 밖 값·비트 필드 0/1 밖·번호 범위 밖(유닛 228, 무기 130, 소리 106, Addon/Infestation 106~201,
  플레이어 12, 피해 배율 5×5)은 `EudextError`. 목록에 변수 값·번호를 주면 "dat.now 를 쓰라" 는 오류.
- 선택 기준(S5 A.6)은 모듈 docstring 에 옮겼다.

**명세·초안과 달라진 점**

| # | 무엇 | 이유 |
|---|---|---|
| 1 | **같은 dword 의 연속 SetTo 합치기** 추가 (`actions(merge=True)` 기본) | 같은 dword 에 여러 필드를 쓰는 일이 많다(SetUnitAbility 28액션 중 크기 4필드 → 2액션, 바이트 필드 228개 → 57액션). 결과는 순서대로 적용한 것과 같다(무작위 300건 + 에뮬레이터 확인). A.8 기대값은 합치기 전 기록(`merge=False`)으로 대조. **EUD Editor Add 목록은 합치지 않는다**(순서·중복에 민감, A.8 "19 트리거" 유지) |
| 2 | **64개씩 채움** (3.8 "작은 트리거 선호"와의 균형) | 1회 목록은 액션 자체가 바이트의 대부분이라 64개를 채우는 편이 바이트·실행 모두 적다(예산 문서 2.1: 1액션 트리거 146B, 8액션 719B = 액션당 90B, 64액션 2408B = 액션당 38B). 3.8 의 "억지로 채우지 않는다" 는 빈 액션으로 채우지 말라는 뜻으로 읽고, 마지막 묶음은 남은 수만큼 낸다. 매 프레임 목록도 실행 수를 줄이려 64개씩. `emit(chunk=…)` 로 바꿀 수 있다 |
| 3 | `now` 변수 번호는 **명세대로 scdata 쓰기** | 직접 계산(epd·subp)과 비교 실측: 간격 2 필드 1회 = 실행 37 대 37, 바이트 3.5KB 대 7.0KB, 같은 번호 2회 = 실행 58 대 72, 4.9KB 대 13.2KB → scdata 쪽이 싸다(곱셈 캐시 공유). eudext 전용 필드만 직접 계산 |
| 4 | 시작 목록 **등록 방식**(빌드 밖 = 계속, 빌드 중 = 그 빌드) | 빌드 밖에서 `EUDOnStart` 로 바로 내면 주 함수 안의 선언을 못 보고, 빌드 중 선언을 모듈 목록에 남기면 한 프로세스 여러 빌드(시험·cost.py)에서 다음 빌드로 샌다. 빌드별 상태는 `_compat.register_build_reset` 로 지운다 |
| 5 | epScript 용 짝 함수 `begin_actions/end_actions`, `begin_temporary/end_temporary`, `values()`, `start()`, `emit()` 추가 | epScript 에 람다·`with` 가 없다. 리스트 리터럴은 EUDArray 로 번역된다 |
| 6 | `tep.SetUnitsDatX` 의 사람 플레이어 인자 이름을 `players=` 대신 **`humans=`** (기본 `tep.humans = P1~P5`, TPL) | `player_unit_enable(players=…)` 와 뜻(값을 쓸 대상)이 달라 헷갈린다. theSeed 판(P1~P7)은 `dat.tep.humans = range(7)` |
| 7 | TEP 값이 필드 폭을 넘으면 **TEP 처럼 잘라 쓰고 경고** (scdata 이름 API 는 오류) | TEP(SetMemoryB/W)는 마스크로 잘려 들어갔다(예: SuppCost 200 → 400 → 144). 이식 동작 보존 |
| 8 | `readySound` 원소 수를 **106** 으로, TEP `RdySnd` 에도 번호 검사(EudextError) | units.dat 배치상 106칸(0x661FC0 + 228·2 는 rightClickAction·sizeType 과 겹침). TEP 에는 검사가 없어 106 이상이면 다른 표를 덮어썼다 — "TEP 동작 보존" 의 예외로 오류 처리 |
| 9 | theSeed 비트 이름(`Flyer=`, `RoboticUnit=` …): **`true` 일 때만 켜고 그 밖은 끔**(그대로) + bool 이 아니면 경고 | theSeed `k == true` 비교 동작 보존 |
| 10 | `tep.SetUnitAbility` 는 **dat 부분만**. 이름 문자열·점수 표(InputStrArr, UnitPointArr, KillPointArr, SizeChangeFlag)는 만들지 않고 dict(`color`, `name`, `name_hex`, `point`, `big_kill_point`)로 돌려준다. `variant="seed"`(무기 중복 예외 70, DmgType 5 = `inscribed_damage_type`, 83번 예외 없음, `ArmorDefType`) | 문자열·점수 표는 dat 가 아니고 맵마다 쓰임이 다르다(display/strdesign 몫) |
| 11 | `damage_ratio` / `tep.SetDamageRatio` 를 **0x515B88(CtrigAsm·theSeed 값)로 구현하고 첫 사용 때 경고** | 명세는 "주소 확인 후" 였지만 theSeed 가 이미 쓰는 헬퍼라 이식 층에 필요. eudplib 주석은 0x515B84 → 인게임 확인(A.9-4) 전까지 경고 유지 |
| 12 | images `grpFile`·overlay 6종(eudext 전용)을 넣고 **첫 사용 때 "SC:R 읽기 전용일 수 있음" 경고** | theSeed `SetImageDatX` 이식용(A.4 "요청 시"). 주소는 scdata image.py 주석·theSeed 와 같음 |
| 13 | `from_eud_editor` 값 범위를 **±2³²** 로 | M2 `EUDEditorDat.lua` 에 −2³¹ 보다 작은 차분이 있다(최상위 바이트 감소 = (새−옛)·2²⁴). 덧셈은 2³² 로 돌아 결과가 같다. Lua 표 이름 선택(`EUDEditorStatusFnActs` 등), DataEditor.py·목록도 받는다 |
| 14 | `player_upgrade_max` 등 플레이어별 업그레이드·테크 표는 **구현하지 않음** | A.10: 주소 이름 확정 전. 필요하면 `dat.raw(…)` |
| 15 | 시험이 scdata 디스크립터의 공개 속성(`offset`·`stride`·`kind.size()`)을 직접 읽는다 | "_compat 경유" 결과가 아니라 원본 값과 대조하려는 목적. 라이브러리 코드는 `_compat` 만 쓴다 |

**비용**: `docs/COSTS.md` "datpatch (WP15)" — dword 64필드 = 1 트리거·2.4KB(scdata 대입 64줄 = 64 트리거·9.4KB),
M2 EUD Editor 1,182줄 = 19 트리거, UERE 773줄 = 13 트리거.
**시험**: `tests/t_datpatch.py` — scdata 멤버 전수(주소·크기·간격·비트·원소 수·상수 주소), eudext 전용 필드 주소,
표끼리 겹침 없음(원소 수 검증), S5 A.2 스냅숏, TPL·theSeed `func.lua` 를 직접 읽어 키→주소 대조, A.8 기대값 전부,
TEP 변환·경고, 오류 38종, 합치기 무작위 300건, EUD Editor 4파일, 에뮬레이터(시작 1회·매 프레임·조건 목록·now 상수/변수
26건·temporary 상수/변수/나중 되돌리기·64개 경계 1/63/64/65/128/129), 빌드 밖 선언 두 번 빌드, 주 함수 뒤 선언 오류,
epScript 번역·단독 빌드·euddraft 빌드.
**인게임**: S5 A.9 (`docs/INGAME_CHECKLIST.md` B15).

---

### 4.17 `bgm` — 배경음악 — **WP16 완료**

**명세(정본)**: `docs/spec/S5_dat_bgm.md` B절. API 는 S5 B.9 + 아래 "초안과 달라진 점".
구현 `eudext/bgm.py`, 시험 `tests/t_bgm.py`, 예제 `examples/bgm_example.eps`, 인게임 확인 맵 `examples/bgm_ingame.eps`(빌드 도우미
`examples/bgm_ingame_build.py` — 소리 합성·`[MSQC]` 확인·euddraft).

**근거**: `AddBGM` 44 등 7맵 57(R1). 엔진은 두 계통 — **로컬형**(`IBGM_EPD`, TPL: 곡 × 대상마다 트리거 1, RESV 52×12 = 624)과
**공유형**(`AddBGM` + `Install_BGMSystem` + `IBGM_EPDX`, MSQC 로 방장 경과 시간 동기화). 시간은 `0x51CE8C`(실제 ms 의 보수),
곡 길이는 전부 손으로 적은 값, `NormalTurboSet` 은 곡 길이와 무관(두 사이클 합). 조각 이어 재생은 맵이 손으로 짰다(M2 364조각 × 4 = 1,456 트리거).
euddraft `bgmplayer.py` 는 한 곡 반복만, `soundlooper.py` 는 `EUDSwitch` 로 조각마다 `PlayWAV`. DPS 이식판(e7efff2)에는 BGM 코드가 없어 새로 작성했다.

**API**

```python
from eudext import bgm, sync, players as pl
# 컴파일 시점: 곡 표 (선언하는 순간 MPQAddWave(이름, 절대 경로) — 같은 이름 두 번은 eudplib 중복 오류 EPError)
bgm.set_dir("MSF_UE_RE_BGM")                        # 상대 경로 기준(선택). 없으면 부른 파일 폴더 → 작업 폴더
OP   = bgm.track("GRAVITY_OP.ogg")                  # 길이 자동(내림 ms), 이름 "staredit\\wav\\GRAVITY_OP.ogg"
BOSS = bgm.track("SBoss.ogg", length_ms=368000)     # 수동 길이 / trim_ms=n (자동 − n) / mpq_name= / add=False(맵에 이미 든 소리)
LV10 = bgm.chunks("LV10_{:03d}.ogg", range(1, 273)) # 조각 이어 재생 (= chunks(pattern, 1, 273)), 조각마다 실측 길이
ROT  = bgm.rotation(["BGM1_1.ogg", "BGM1_2.ogg"], length_ms=45000)   # 요청마다 다음 파일 (칸마다 카운터)
bgm.measure_ms(path); bgm.sound_info(path); bgm.songs(); bgm.table()
# Track = ExprProxy(곡 번호): .id .kind .start .count .names .lengths .files — epScript `player.current(0) == BOSS`

# 런타임
bus = sync.Bus("msqc", qc_unit=49)
player = bgm.Player(
    mode="synced",                   # "local"(기본) | "synced"
    targets=pl.humans(),             # None/"humans"/Humans, "all", Everyone, All, Observers, 번호(0~7, 128~131, P9~P12) 목록
    elapsed=bus.value(bgm.clock.local_dt(), latch=True),   # synced 필수. EUDVariable·정수도 됨. local 은 None(이 PC 시계)
    max_elapsed=2500,                # 넘으면 그 사이클 0 (None = 검사 없음) — local 모드에도 적용
    busy="drop",                     # "drop" | "replace" | "queue"
    busy_sound=None,                 # drop 때 그 칸에 낼 소리(MPQ 이름 또는 Track)
    observers=True,                  # 관전자 칸(8)
    observer_toggle_key="DELETE",    # 관전자 로컬 끄기(채팅 중 제외). None = 없음
    lead_ms=0,                       # 남은 시간 보정(음수는 1ms 남김)
    method="switch",                 # "switch"(EUDSwitch, 기본) | "patch"(PlayWAV 문자열 칸 채우기 — D16-1 확인 전)
    repeat=2,                        # PlayWAV 반복(기존 관례, D16-2)
)
player.request(BOSS); player.request(BOSS, p); player.request(OP, loop=True, force=True)
player.loop(BOSS, p=None, force=False); player.stop(p=None); player.mute(p=None, on=True)
player.is_playing(p); player.current(p); player.chunk(p); player.remaining(p); player.last_dt()
player.tick()                        # 사이클마다 한 번 (빌드에 한 번 — 두 번이면 오류). 시계 update 도 여기서
player.cells(); player.body_sizes(); player.state_region(); player.shared_region(); player.control_vars()   # 시험·디버그
bgm.clock.local_dt(); bgm.clock.half(); bgm.clock.half_value(); bgm.clock.dt2(elapsed); bgm.clock.update()   # = bgm.clock_update()
```

epScript: 모듈 함수는 `bgm.track/chunks/rotation/set_dir/measure_ms/clock_update`(→ `f_…`), `bgm.clock.local_dt()` 등 객체 메서드와
`bgm.Player(…)`·`player.…` 는 그대로 번역된다. 조각 번호 범위는 `bgm.chunks(p, 1, 273)` 또는 `py_range(1, 273)`, 파일 목록은 `list(…)`.
재생기·곡은 전역 `const` 로 선언한다(`var` 에 담지 않는다).

**의미·알고리즘**
- **곡 표**(빌드마다, 처음 코드를 낼 때 굳힘): 칸(파일)마다 길이 `EUDArray`, 곡마다 (시작 칸, 개수, 돌려 쓰기 카운터 필드) `EUDArray` 3개.
  문자열 번호 `EUDArray` 는 `method="patch"` 재생기가 있을 때만. `busy_sound` 이름은 곡 표 뒤 "덤 칸"(재생 함수에만).
  같은 프로세스에서 `LoadMap` 을 다시 하면 eudplib 이 MPQ 목록을 비우므로 표를 굳힐 때 빠진 파일을 다시 넣는다.
  표가 굳은 뒤 선언한 곡·`busy_sound` 는 **그 빌드에서 쓰면 오류**(선언 자체는 된다 — 다음 빌드 표에 들어간다).
- **기록 칸**: 필드(유닛 자리) × 칸 12 — REM(남은 ms), SONG, SLOT(표 칸), CHUNK, LEFT(남은 조각 수), LOOP, MUTE, REQ, EN(대상), 돌려 쓰기 카운터(곡마다).
  칸 k 의 필드 f = `EPD(기록) + 12·f + k`. 루프는 **CP = EPD(기록) + k**(캐시까지 `SetCurrentPlayer`/`AddCurrentPlayer`)로 돌아
  `Deaths(CurrentPlayer, …, f)`·`SetDeaths(CurrentPlayer, …, f)` 로 상수 조건·액션만 쓴다. eudplib 읽기 함수는 CP 를 캐시(= 칸 포인터)로 되돌린다.
  synced = 공유 기록(칸 0~7 = 플레이어, 8 = 관전자), local = 이 PC 의 로컬 기록(칸 0 하나) + 공유 요청·끔 칸(칸 0~8).
- **tick** (본문 EUDFunc 1벌, 곡 수·대상 수와 무관 — 대상 1명과 11명의 본문 트리거 수가 같다, 시험):
  1. dt ← 경과 시간(synced: `sync.Value` 면 지금 있는 가장 작은 번호 사람의 값), `dt > max_elapsed` 면 0.
  2. 관전자 로컬 끄기 키(이 PC 가 관전자일 때만, 자체 이전 상태 비트 — `local.update()` 순서와 무관).
  3. local: 공유 요청이 있으면 내 칸 요청(없으면 전원 요청)을 로컬 REQ 로 옮기고 **공유 칸은 모든 PC 가 같게 지운다**.
  4. 할 일이 없으면(곡 수 0 이고 요청 없음 / local 은 대상 아님·곡·요청 없음) 끝 — 유휴 실행 8~11.
  5. 빼기 패스(곡 수 ≥ 1, dt ≥ 1): 칸마다 `REM −= dt`(SC Subtract 포화, 액션 칸을 dt 로 한 번 채움) → 0 이고 곡이 있으면
     남은 조각 → 다음 칸(길이 캐시: 앞 칸과 같은 표 칸이면 다시 읽지 않음) / 반복 → 같은 곡 시작 / 아니면 곡 0·"끝남" 표시.
  6. 요청 패스(새 요청, 또는 기다리는 요청이 있고 이번에 끝난 곡이 있을 때): 칸마다 REQ(없으면 전원 요청) → 강제면 바로,
     재생 중이면 drop(버리고 busy_sound) / replace / queue(칸 요청은 그 칸이 빌 때, 전원 요청은 **모든 대상 칸이 빈 사이클**에). 정지 = 강제 정지 요청.
  7. CP 를 들어올 때 값으로 되돌린다.
- **start**(공유 함수): 정지·반복 비트 처리, 모르는 번호 무시, 표 읽기(시작 캐시: 앞 칸과 같은 곡이면 다시 읽지 않음 — 돌려 쓰기 제외),
  돌려 쓰기는 칸의 카운터 번째 파일 + 카운터 증가, 남은 시간 = 길이 + lead, **play_mine**.
- **소리**: play_mine = "이 칸이 이 PC 몫(시작 때 채운 비교값)·끔 비트 0·관전자 끄기 아님" 이면 재생 함수. 재생 함수는 CP 를
  `f_setcurpl(f_getuserplayerid())` 로 바꾸고(캐시 포함 — `EUDSwitch(변수)` 가 끝에서 CP 를 캐시로 되돌리므로) `PlayWAV × repeat`, 끝에서 원래 CP.
  끈 플레이어·관전자 끄기는 **소리만** 막고 곡 상태는 흐른다(다시 켜면 다음 조각·곡부터).
- **로컬/공유**: local 모드 값(`current/chunk/remaining/is_playing/last_dt`)은 `LocalValue`/`LocalCondition`. synced 는 `elapsed` 가
  동기화 값이면 기록 전체가 공유 안전 — 이 PC 번호 0·1·2·128 에서 같은 입력을 돌려 기록·요청 변수가 매 사이클 같고 소리는 그 PC 에만 나는 것을 시험했다.
- **시계**: `local_dt` = `0x51CE8C` 아래 16비트의 사이클 차이(시작 때 1회 읽기, 한 사이클 65초 한계), `half` = 0/1 공유 토글,
  `dt2(e)` = 0 인 사이클 A ← e, 1 인 사이클 B ← A + e (UERE Option_NT).
- **길이 측정**: 앞 4바이트로 판별 — `RIFF`: fmt(확장 형식 포함)·fact·data 청크(홀수 크기 채움, 잘린·크기 미상 data 는 있는 만큼),
  PCM/float = 프레임 ÷ 표본율, 그 밖 = fact 표본 수 또는 data ÷ byte rate. `OggS`: 첫 페이지 식별 헤더(Vorbis 표본율, Opus 48k·pre-skip, FLAC STREAMINFO),
  끝에서부터 창을 넓혀 **같은 serial·granule ≥ 0·CRC 가 맞는** 마지막 페이지. 내림 정수 ms. `struct` 만 쓴다(번들에 `wave` 없음).

**비용** (2026-09-17, `docs/COSTS.md` "bgm (WP16)", 곡 표 289칸·돌려 쓰기 2곡)
- `tick()` 호출 자리 **1**(목표 ≤ 10) + 빌드 첫 시계 8(실행 30). 실행: local 유휴 11 · 재생 중 37, synced 8칸 유휴 8 · 빼기만 62 ·
  조각 경계(8칸 같은 칸, 캐시) 273 · 전원 요청 → 8칸 시작 580(첫 칸만 표 읽기).
- 본문(재생기마다 1벌): synced 루프+start+play_mine **131**, local 141(관전자 끄기 키가 있으면 +6). 재생기 1개 페이로드 약 38KB(에뮬레이터 빌드 차이).
- 재생 함수(같은 method·repeat 인 재생기끼리 1벌): `switch` = **19 + 칸 수**(289칸 308), `patch` = **12**(칸 수와 무관) — S5 목표 "재생 본문 ≤ 40(+ 방식 1 이면 칸 수)" 안.
- `request` 상수 1 / 1, 변수 곡·변수 p 5 / 8, `mute` 상수 1 / 1. 곡 표 = 칸마다 4B(+ patch 4B) + 곡마다 12B.
- 상태 기계(131~141)는 S5 의 "재생 본문 40" 보다 크다: 곡 수·대상 수와 무관한 1벌에 busy 정책 3종·반복·정지·돌려 쓰기·조각/시작 캐시·
  이 PC 판정을 모두 넣었다. 비교: RESV 624 / M2 상시 BGM 1,456 트리거(곡·조각 × 대상마다 1).

**시험** (`tests/t_bgm.py`, 22,724 판정)
- 길이: S5 B.6 실측 표 7개(GBGM1 33095 … BGM_167 60031 — 같은 granule 의 합성 Ogg, 실측 파일은 이 PC 에 없음), `.wav` 확장자의 OggS,
  PCM 8/16/24비트 × 1/2채널 × 5표본율 × 확장 형식·덧청크(개발 venv 의 `wave` 와 대조), float, IMA ADPCM(fact/byte rate), 홀수 청크, 잘린·크기 미상 data,
  Opus pre-skip, FLAC, 본문 속 가짜 OggS·다른 serial·64KB 넘는 꼬리·granule −1 페이지, 모르는 형식(EudextError / length_ms 로 통과).
- 표: track 3개 다음 chunks 272 → 칸 275, 조각 곡 (3, 272). MPQ: 같은 이름 두 번 → EPError, 한 선언 안 중복이면 아무것도 넣지 않음, LoadMap 뒤 다시 넣기, 굳은 뒤 선언.
- 옵션·대상 검사 오류 22종, 빌드 오류 기대 7종(tick 두 번, 모르는 곡, 다른 프로세스 Track, CurrentPlayer, 범위 밖 p, mute 값, synced p 없음).
- **무작위 차등**: 재생기 8종(local drop/replace/queue/patch+lead, synced drop/queue/replace+patch/all) × 이 PC 0·1·2·128 × 700 사이클,
  사이클마다 파이썬 참조 모델과 공유 상태·로컬 칸·소리(CP·파일)·CP 복구·쓴 dt 비교. 요청 op 14종(전원·칸·변수 p·관전자 칸·강제·반복·정지·끄기·모르는 번호),
  dt 0~0xFFFFFFFF, 관전자 키·채팅 중. 시작(3종)·조각 넘김·곡 끝·반복·정지·버림·기다림(칸·전원)·소리 막힘·관전자 키가 모두 나오는지 센다.
  synced 는 네 PC 의 공유 상태가 같고 소리가 그 PC 에만 나는지 따로 본다.
- B.10 시나리오: local 요청 BOSS → 368000·요청 칸 0, drop(busy_sound), 1000 × 368 → 끝 → 다음 요청, LV10 272조각 순서·조각 번호·끝,
  반복(조각 곡 처음부터), 정지, 돌려 쓰기 순서, 끄기·켜기, 대상 아닌 PC. synced: 3000 → 그대로, 2500 → 뺌, 끈 PC 소리 없음, queue 가 전원 0 인 사이클(8번째)에 적용.
- 동기화 값: 걸쇠 값의 방장 몫, 2600 → 0, 방장이 나가면 다음 사람 몫, 걸쇠 없는 값(0xFFFFFFFF → 0). 시계: half 0,1,…, dt2, local_dt(16비트 넘김 포함), 시계 재생기.
- 본문 크기 대상 1명 = 11명({'body': 73, 'start': 58, 'play_mine': 6, …}). 읽기(상수·변수 p·관전자 칸, local 값 형식).
- epScript 예제·인게임 맵 번역, 예제 에뮬레이션(소리 순서: op → 조각 3 → 돌려 쓰기 2 → 반복), 인게임 맵 에뮬레이션(1,000 사이클 소리 요약),
  빌드 도우미로 euddraft 빌드 2개 + MPQ 에 소리(RIFF)가 들었는지·없는 이름은 안 들었는지, `[MSQC]` 줄 불일치 검출.

**인게임**: `docs/INGAME_CHECKLIST.md` D16-1~9 (필수 D16-1 문자열 칸 채우기, D16-3 조각 사이 틈·일시정지). 확인 맵 `examples/bgm_ingame.eps`.

**의존**: WP8(players — 사람 판정·표시), WP13(sync — synced 모드, `Value.get`), local(키·로컬 표식).

**초안과 달라진 점과 이유**
1. **요청은 tick 에서 적용**한다(`request/stop/loop` 은 칸에 쓰기만). 여러 PC·여러 재생기에서 상태가 바뀌는 곳을 한 곳으로 모았다. `stop` = 강제 정지 요청.
2. `request(…, loop=, force=)` 를 더했다(`loop()` 는 별칭). `remaining(p)`, `last_dt()`, 시험용 `cells/body_sizes/state_region/shared_region/control_vars`.
3. **queue**: 칸 요청은 그 칸이 빌 때, 전원 요청은 모든 대상 칸이 빈 사이클에(UERE ReserveBGM). local 모드는 전원 요청을 자기 칸 요청으로 합친다.
   기다리는 동안은 곡이 끝난 사이클에만 요청 패스를 돈다(실행 절약).
4. **끈 플레이어**(mute·관전자 끄기)도 곡 상태는 흐른다(LIB 는 타이머를 세우지 않았다). `chunk(p)` 로 패턴을 맞추는 맵에서 PC·플레이어마다 같게 두려고. 7절 D41.
5. **synced elapsed**: `sync.Value` 를 받으면 지금 있는 가장 작은 번호의 사람 값을 쓴다(방장이 나가면 다음 사람). `latch=True`(명세 예)는 받지 못한 사이클에
   마지막 값을 다시 빼므로 턴이 여러 프레임인 방에서 평균이 맞는다(받은 사이클만 빼면 한 턴에 한 프레임 몫만 줄어 곡이 늦게 끝난다). `latch=False` 는 UERE 방식
   (못 받은 사이클 0xFFFFFFFF → max_elapsed 로 0). 7절 D40.
6. `max_elapsed` 를 local 모드에도 적용한다(일시정지 뒤 큰 dt 로 조각을 건너뛰지 않게 — D16-3 에서 확인).
7. **선언 시점 MPQAddWave**(euddraft 는 맵을 먼저 읽고 플러그인을 불러온다 — 실측) + 빌드마다 빠진 것 다시 넣기. "표가 굳은 뒤 선언" 은 선언을 막지 않고
   그 빌드에서 쓸 때 막는다 — eudplib 시작 단계 표식(`_has_already_started`)이 빌드가 끝난 뒤에도 2 로 남아 "빌드 사이" 를 가려낼 수 없다.
8. 관전자 끄기 키는 `local.key_pressed` 대신 자체 이전 상태 비트(트리거 4) — `local.update()` 가 어디서 도는지와 무관하게 한 번 누름 = 한 번 바꿈.
9. `local_dt` 는 아래 16비트만 읽는다(읽기 실행 약 16 절약). 한 사이클이 65.5초를 넘으면 틀리지만 그런 dt 는 max_elapsed 로 버린다.
10. `Track` 을 `ExprProxy`(곡 번호)로 했다 — epScript `player.current(0) == BOSS`, `var s = BOSS;` 가 된다.
11. `targets` 는 컴파일 시점 칸 목록이다(`players.Allies`·변수·일반 `Targets` 는 받지 않음 — 칸 EN 을 초기값으로 굽는다). local 모드의 "이 PC 가 대상인가" 는 시작 때 칸마다 트리거 1.
12. `PlayWAV` 반복 기본 2(TPL·LIB 관례). D16-2 결과로 1 로 줄일 수 있다(7절 D39).
13. 두 재생 방식을 모두 구현했고 기본은 `switch`(7절 D18). `patch` 는 D16-1 확인 전.
14. 길이 캐시 두 가지(조각 넘김: 칸 → 길이, 시작: 곡 → 시작 칸·남은 조각·길이)를 넣어 전원 요청·조각 경계의 실행을 줄였다(8칸 시작 1,141 → 580).

**위험·미정**: D16-1~9 전부(문자열 칸 채우기, 반복 이유, 조각 틈·일시정지, 관전자 CP, 없는 파일, Ogg 이름, 동기 방장 이탈·디싱크, 동시 소리 수, 로딩 시간).
턴이 여러 프레임인 방의 `latch` 근사 오차. CP 를 칸 포인터로 쓰는 루프는 eudplib CP 캐시 규약(3.6)에 기댄다 — 루프 안에서 부르는 eudplib 함수가
CP 를 캐시로 되돌린다는 가정(0.81 읽기 함수·EUDSwitch·f_setcurpl 확인).

---

### 4.18 `scrdb` — SCR_DB 네이티브 코어 — **WP18 완료**

**근거**: DPS·UE_RE 사용(2맵 21). 가치와 제약은 R2 3.1, 규약 표는 DPS 이식판 `eud/spec/G8_text_scrdb.md` 1.10·1.11(e7efff2),
`docs/SCR_DB_PORTING.md`. 정본 Lua 코어 `MapSource/Library/SCR_DB_Core.lua`(레이아웃 7, MapSource `b57b6fe` "MSQC 워드를 20비트로") —
저장소 사본 `reference/MapSource/Library/SCR_DB_Core.lua` 와 2026-09-17 현재 **같다**(sha256 `4ff6745b0add…`).
구현 `eudext/scrdb.py`, `eudext/tools/lua_consts.py`, `eudext/tools/edsgen.py`(`add_scrdb`), `eudext/testing/syncmodel.py`(시험 모델),
`_compat.py` 끝 WP18 블록(`pname_lightvar_units`). 시험 `tests/t_scrdb.py`(2,016)·`tests/t_lua_consts.py`(55)·`tests/ref_scrdb.py`(참조).
예제 `examples/scrdb_ingame.{eps,eds}`, `examples/scrdb_build.py`.

**API**

```python
from eudext import scrdb
db = scrdb.setup(fields, save_key, layout=None, *, anchor=0x594198, humans=None, channels=8,
                 msqc_addr=0x58F508, msqc_death=21, xfer_base=None, xfer_stride=None, slot_base=None, slot_stride=None,
                 max_players=8, slot_count=None, key_mode="ordinal", extra=None, manifest=None,   # manifest: 경로 | "auto"
                 bus=None, qc_unit=None, write=None, guard=None, build_id=None, core=None, generated=None,
                 name="scrdb", allow_outside_mirror=False)          # 맵에 하나, 모듈 최상위
scrdb.arr(name, index); scrdb.var(name, slot) / scrdb.slot(name, slot)   # epScript 는 var 가 예약어 → slot
scrdb.deaths(name, unit)                         # MSF 방식 (arr, index = unit×12, xfer 0x58A364/1)
db.frame(write=None)                             # anchor → receiver → notify (훅이 있으면 아무것도 내지 않음)
db.anchor(); db.receiver(write=None); db.notify()
db.save_signal(p) -> Action; db.close_load(conds); db.close_load_action()
db.launcher_ready(p) / db.save_done(p) / db.got_word(p) -> Condition   # p = 0~7 | 변수 | CurrentPlayer
db.clear_ready(p) / db.clear_save_done(p) / db.clear_word(p) -> Action
db.ready / db.saved / db.activity                # EUDArray(8) (epScript `db.ready[p]`)
db.default_writer(guard=None) -> fn(p, key, val)
db.addr(칸 이름|번호); db.slot(k, i); db.death_epd(k, i); db.field_addr(항목, p); db.field_epd(항목, p)  # p 변수 가능
db.msqc_count_addr(k, i); db.msqc_echo_addr(k, i); db.key_of(항목)
db.manifest_doc(); db.manifest_bytes(); db.write_manifest(path=None)
db.core (ScrdbCore); db.ids; db.dup_names; db.field_hash; db.build_id; db.bus; db.lua_cfg
# 모듈 수준 (DESIGN 초안 이름): scrdb.frame/anchor/receiver/notify/save_signal/close_load/write_manifest = current() 의 것
scrdb.current(); scrdb.declared(); scrdb.clear()
scrdb.field_hash(fields); scrdb.assign_ids(fields); scrdb.json_bytes(value)            # Lua 판의 파이썬 구현
scrdb.msqc_lines(addr=0x58F508, death=21, channels=8)                                   # sync.scrdb_msqc_lines 의 자리 인자판
scrdb.manifest_name(save_key, hash); scrdb.default_manifest_path(save_key); scrdb.stash_manifest(src, store)
scrdb.check_forbidden(db=None); scrdb.hook_source(); scrdb.write_hook(path)
# tools
from eudext.tools import lua_consts as lc          # 5.4
lc.scrdb_core(path=None) -> ScrdbCore; lc.find_scrdb_core(path=None)
doc.add_scrdb(db=None, hook=True, core=None, build_id=None, manifest=None, frame=True, preload=True)   # EdsDoc
```

**핵심 제약 — 구현**
- **(a) 단일 출처**: 파이썬에 레이아웃 숫자가 없다(시험이 `scrdb.py` 의 숫자 토큰을 검사). 빌드 때 `lua_consts.scrdb_core()` 가 lupa 로 Lua
  코어를 실행해 전역 상수(SCRDB_I·MAGIC·TOTAL·TABLE_PLAYERS·토글·꼬리표·페이로드·에코·예약 워드)를 읽고, **CtrigAsm 트리거 함수 스텁**
  (`CtrigTrace`)으로 `SCRDB_Anchor`/`SCRDB_Notify`/`SCRDB_Receiver` 를 기록해 계획을 뽑는다: 1회 블록의 트리거별 액션 목록
  (칸·수정자·값 출처 — 설정 두 벌로 돌려 `BuildId`·`FieldHash`·`#Fields` 등 출처를 가린다), 매 사이클 트리거(LocalPlayer 8·Seq),
  알림 코드·소리. `db.anchor()`/`db.notify()` 는 이 계획을 그대로 낸다. 설정 검사·BuildId·FieldHash·id 도 **Lua `SCRDB_Setup` 을 실행한
  결과**를 쓰고(거부 메시지 그대로 `EudextError`), 매니페스트도 **Lua `SCRDB_WriteManifest` 가 쓴 바이트**를 쓴다. 수신기 논리는 파이썬으로
  짰으므로 Lua 수신기 기록의 모양 지문(`RECEIVER_DIGEST`)이 다르면 빌드 경고. 시험이 칸 번호·시그니처·토글·꼬리표·예약 워드·알림 코드·
  LoadOpen 값을 바꾼 Lua 사본으로 빌드해 Lua 모델과 같게 도는 것을 확인한다.
- **(b)** 파이썬 판 `field_hash`/`assign_ids`/`json_bytes`/`manifest_doc` 를 두고 **빌드마다 Lua 결과와 바이트 대조**(다르면 오류).
  시험: 무작위 300(지문·id)·400(JSON)·매니페스트 60 + 경계값, DPS 런처 `field_hash` 와도 대조.
- **(c)** 시그니처는 Lua 계획대로 SetMemory 8액션 트리거 하나(마지막). 시험: 에뮬레이터 페이로드와 euddraft 산출 chk 에 8 dword 연속 없음.
- **(d)** 채널 줄은 `setup` 이 MSQC `sync.Bus`(기본 새 버스 `name="scrdb"`, `bus=` 로 기존 버스)에 넣는다 — 기본 자리면
  `bus.scrdb_channels()`, 아니면 같은 형식(`scrdb.msqc_lines`, 시험이 `sync.scrdb_msqc_lines()` 와 대조)으로 `bus.raw`. 그래서
  eds 생성(`add_sync`)·빌드 안 확인(`sync.verify`)을 sync 와 같이 쓴다. NSQC 버스의 출력 데스 유닛이 채널 데스 유닛과 겹치면 오류.
- **(e)** `receiver()` 는 같은 빌드에서 `anchor()` 가 없으면 먼저 낸다. euddraft 안에서는 명령줄 eds 를 읽어 **수신기를 내는 플러그인**
  (호출 스택에서 `settings` 전역을 가진 모듈 = 파일 이름)이 `[MSQC]` 앞이면 빌드 오류. 훅(`eudext_scrdb_hook.py`)을 쓰면 edsgen 이
  `[MSQC]` → sync 훅 → scrdb 훅 → 맵 순서로 놓는다. `frame()` 은 beforeTriggerExec **최상위**에서 부른다.
- **(f)** LocalPlayer = `Memory(0x512684, Exactly, i)` 조건 트리거 8개(표지 블록 칸만 SetTo), Notify = 코드마다
  `[알림 칸 == 코드, 이 PC 번호 ≤ 7] → PlayWAVAll(소리), 알림 칸 0` + 코드 범위 지우기(관전자는 소리 없이 0) + CP 복구.
  시험: 두 "클라이언트"(이 PC 0/1)에 같은 워드를 주고 한쪽에만 알림 코드를 써도 표지 블록 밖 메모리 차이가 eudplib 이 원래 로컬로
  두는 칸을 넘지 않는다.

**의미·알고리즘**
- 표지 블록: `EUDExecuteOnce` 안에 Lua 계획의 트리거 5개(0 초기화 64/64/40 → 헤더 15 → 시그니처 8), 그 뒤 매 사이클 LocalPlayer 8·Seq+1.
- 수신기(채널 k × 사람 i): 자리마다 **트리거 1개**(`Deaths(i, AtLeast, 1, D+k)` → `n ← 자리 번호`, 자기 next ← 본문 입구).
  본문 한 벌(`_parts.SubLabel`): CP = EPD(표) + n(잠깐 옮기기)에서 **표 하나**(필드 7 × 자리 수: 호출 트리거 next 칸·돌아갈 곳·
  데스 칸 EPD·Count/Echo 칸 번호·상태·키·하위 값)를 정수 오프셋으로 읽고 쓴다 — 호출 트리거의 next 되돌리기와 복귀 주소는
  읽기 결과를 액션 칸·next 칸에 바로 넣는다(`f_dwread_cp(…, ret=[EPD 칸])`). 워드는 `f_maskread_epd(데스 칸, 토글|에코)` 1회,
  토글·꼬리표·예약 워드는 워드 변수의 마스크 조건, 키·하위 값·에코는 "워드 SetTo → 마스크 SetTo 0"(마스크 Add/Subtract 는 쓰지 않음, 3.5-8).
  상위 워드면 키·하위 값을 읽고 `페이로드 × 65536`(eudplib 읽기 표, 자리 옮김)을 더해(CP 는 캐시로 돌아감) `write(p, key, val)`.
  Lua 와 같은 점: 토글 두 if 는 else 가 아님(둘 다 서면 Count +2), 꼬리표 3 은 에코·카운트만, 상위 워드 뒤에도 HaveLo 유지,
  예약 워드는 꼬리표 0 일 때만, 20비트 위 비트는 무시.
- 기본 쓰기 함수: ordinal = 키 < 항목 수이고 guard 가 참이면 `EPD(P1 칸)[키] + (플레이어 × 보폭)`(모드가 섞이면 모드 표) 에 SetTo.
  index = 항목마다 `key == index` 트리거 → 데스/전송 칸 + 플레이어. 없는 키는 무시(DPS·MSF 어댑터와 같은 뜻).
- 매니페스트: `manifest="auto"` 면 Windows `C:\Temp\SCR_DB_manifest_<이름표>.json`(런처가 찾는 자리), 그 밖은 `EUDEXT_WORK`.
  `receiver()` 를 낼 때(빌드 안) 쓴다. 훅 설정 `Manifest` 가 있으면 훅의 onPluginStart 가 쓴다. BuildId 는 인자 > 훅 `BuildId` >
  환경 변수 `EUDEXT_SCRDB_BUILD_ID` > 지금 시각(`os.time() % 0x7FFFFFFF` 과 같은 뜻). 빌드 스크립트(`examples/scrdb_build.py`)는
  수집·빌드에 같은 BuildId 를 준다. `stash_manifest` = DPS `build_headless.stash_manifest` 규칙(`<이름표>_<지문>.json`).
- **빌드 때 lupa**(2.3): `scrdb` 가 `tools.lua_consts` 를 불러오고 그것이 import 때 lupa 를 불러온다 → eds 부트에
  `VenvSite` + `Preload : scrdb` 가 필요(`add_scrdb` 가 넣고 VenvSite 가 없으면 오류). 없으면 setup 이 안내 오류.
  Lua 코어 찾기: `setup(core=)`·훅 `Core` > `EUDEXT_SCRDB_CORE` > `<저장소>/../MapSource/Library` > `~/MapSource/Library` >
  (Windows) `%USERPROFILE%\Desktop\Stormcoast Fortress\ScmDraft 2\MapSource\Library` > 저장소 `reference`(경고). 빌드 로그에 경로·sha256.
- **eudext 추가 검사**(Lua 에 없음): 레이아웃 인자 불일치, 항목 0개·4096 초과(런처 한도), 보폭 0, 표지 블록·값 칸·채널 칸이 미러 구역
  (0x57F0E0~0x59F0E0) 밖(`allow_outside_mirror`), 표지 블록이 값 칸·채널 데스 칸과 겹침, deaths 항목인데 xfer 가 0x58A364/1 이 아님,
  **`key_mode="index"` 에 var 항목**(Lua 는 `and F.index or (n-1)` 로 순번이 되어 받지만 런처 `plan()` 이 `f["index"]` 에서 멈춘다),
  맵 MSQC val 범위 < 워드 비트(64×64 미만), SCRDB_TABLE_PLAYERS 가 2의 거듭제곱이 아님, 설정 두 번, 금지 조합(3.9).

**비용**(`docs/COSTS.md` "scrdb (WP18)"): 대기 사이클 실행 ≈ 48(8채널×4명, Lua 판 추정 140), receiver 페이로드 ≈ 36KB
(자리당 ≈ 310B + 본문 ≈ 21KB + 기본 쓰기 ≈ 4KB), 워드 한 개 실행 250~550, anchor ≈ 11KB(첫 사이클 실행 15, 그 뒤 9), notify 실행 7.
4.18 목표("32벌 펼침 → 한 벌 + 읽기 1회") 만족.

**시험**: `t_scrdb`(2,016 — 표시 조건·액션의 상수·변수·CurrentPlayer 플레이어 포함) — 약속 값·계획(DPS 런처 원문 상수와 대조), 지문·id·JSON·매니페스트 바이트 차등, 설정 검사(Lua 거부 6종 +
eudext 20여 종), **수신기·표지 블록·알림음·close_load 를 Lua 트리 실행 모델(`ref_scrdb.LuaFrame`, CtrigAsm 의미)과 사이클 단위 차등**
(설정 3개 × 이 PC 번호 2~3개, 무작위·프로토콜·중복·토글 둘·꼬리표 3·20비트 위 비트 섞음, 기본 쓰기 함수 값 칸까지), 바꾼 Lua 코어,
1회 블록 순서(메모리 쓰기 기록)·시그니처 비연속·LocalPlayer(0~7, 관전자)·로컬 칸 메모리 차이, **MSQC.py 실제 수신 코드 + 런처 전송 모델
(`ref_scrdb.LauncherModel` — 락스텝·에코·되읽기·준비·저장 완료) + 턴 모델 + 워드 깨짐**, edsgen·훅(에뮬레이터에서 훅이 frame·매니페스트를
냄), 금지 조합(빌드 오류 기대), euddraft 빌드 4종(정적 eds·훅 eds·순서 틀림·VenvSite 없음). `t_lua_consts`(55) — 실행기·변환·파일 찾기·
기록 스텁·지문·lupa 없을 때 안내·CB Paint 적재. **인게임**: INGAME_CHECKLIST D18(필수 D18-1·2·3·4·6 — 런처 연동).

**초안과 달라진 점과 이유**
1. `setup` 인자가 늘었다(Lua Cfg 를 키워드로). `layout=` 은 확인용. 채널 자리·데스 유닛을 바꿀 수 있다(MSF 는 0x593F00/182).
2. **설정 검사·FieldHash·매니페스트를 Lua 로 실행**하고 파이썬 판은 대조용 — 초안의 "파이썬 구현 + 차등 시험" 에 더해 빌드마다 대조.
3. 헤더·알림음은 Lua 트리거 함수를 **기록해 계획으로** 가져온다(값만이 아니라 헤더 구성도 단일 출처).
4. 수신기는 `EUDFunc(k, i)` 대신 **자리마다 트리거 1개 + 인자 없는 서브루틴 한 벌 + 자리 표**(호출 자리 페이로드 610B → 310B).
   `f_maskread_epd` 1회는 그대로.
5. `write(p, key, val)` 의 p 는 변수(본문이 한 벌이라). EUDFunc(epScript 함수)도 받는다. 기본 쓰기 함수(`default_writer`, `guard=`)를 더했다.
6. 훅 플러그인(`eudext_scrdb_hook.py`, 설정 Core·BuildId·Manifest·Frame)과 `EdsDoc.add_scrdb` 를 더했다(빌드 설정을 eds 로 넘기고 순서를 보장).
7. epScript 에서 `var` 가 예약어라 `scrdb.slot(…)` 별칭.
8. Notify 는 Lua 의 "플레이어마다 8트리거" 대신 `PlayWAVAll`(eudplib 이 이 PC 번호로 CP 를 채움) — 관전자에게는 Lua 처럼 소리 없음.
9. 금지 조합 검사는 `IsPName` 의 **라이트 변수 경로만**(0.81 의 `f_check_id`·`SetPName` 은 그 칸을 쓰지 않음 — 실측). 겹치는 SCR_DB 칸
   (채널·표지 블록·데스 칸·값 칸)이 있을 때만 오류라 채널을 옮긴 맵(MSF)은 IsPName 을 써도 된다.

**위험·미정**: 런처 연동 전체(인게임 D18), 2인 LocalPlayer·디싱크(D18-6), PlayWAVAll 로 낸 알림음(D18-5), 기본 표지 블록 자리
0x594198 이 맵의 다른 쓰임과 겹치는지는 맵 몫(검사는 SCR_DB 칸끼리만), 맵이 스스로 지우는 구역(MSF onInit_EUD)과의 순서는 맵 몫.

---

### 4.19 `misc` — 기타 소기능 — **WP19 완료(ObserverChat 먼저)**

**근거**: 관전자 채팅(4맵 복붙 블록)을 빼면 모두 사용 0~2회다. ObserverChat 을 정본 명세대로 완성하고(정본 `docs/spec/S6_chat.md` 2절·4.3),
나머지는 원리가 문서로 확실한 것만 작게 구현했다(R4b D절). 구현 `eudext/misc.py`, 시험 `tests/t_misc_obs.py`(ObserverChat, 60 판정)·`tests/t_misc.py`(나머지, 33 판정),
예제 `examples/misc_example.{eps,eds}`·`misc_ingame.{eps,eds}`·`misc_exit_trap.{eps,eds}`. `_compat` 에 새 비공개 이름은 **더하지 않았다**(공개 eudplib API 만 씀).
DPS_Enhance eudplib-port(a7aad90)에는 대응 코드가 없다.

| 기능 | API | 로컬/공유 | 위험 |
|---|---|---|---|
| 관전자 채팅 | `misc.ObserverChat(keys, delay, edge, notice, decorate, typewriter, sound, always, slots)` + `obs.tick()` — 4맵 블록 대체(S6 4.3). **원본 딜레이 버그 B1(관전자 2~4번 키가 첫 입력 뒤 영구히 막힘)을 고친다.** ToPlayer·음소거는 공유성 미확인이라 설계만, ObserverDrop 은 넣지 않음(D10) | 로컬 | 하 |
| 방장 번호·이름 | `misc.host_player()`(게임 시작 1회, 0~7 또는 0xFFFFFFFF), `misc.HostNameIs(name)` | 공유(표 공유성 미확인 — F19-1) | 중 |
| 부대 지정 | `misc.hotkey_addr(p,g,i)`, `misc.alpha_id(uid,idx)`, `misc.HotkeyUnit(p,g,i,cmp,alpha)`, `misc.SetHotkeyUnit(...)` | 미확인(F19-2) | 하 |
| 카운트다운 | `misc.Countdown(start)` + `tick()`·`done()`·`at_least(n)`·`set(n)`·`add(n)` (스테이지는 `EUDSwitch(cd.v)`) | 공유 | — |
| 와이드 판정 | `misc.is_widescreen(loc, into=None)` → 로컬 값. 필요하면 `sync.Bus.value()` 로 동기화 | 로컬 | 상(섞으면 디싱크), **실험 F19-3** |
| 나가면 멈춤 | `misc.unsafe_exit_trap(target, list_owner=P8, enable=False)` | 로컬 next 포인터 | **최상**, 기본 비활성·인게임 검증 전 실험(F19-4) |
| 채팅 이름 | eudplib `SetPName` 그대로 안내(문서만) | 표시 전용 | — |

**ObserverChat 의미**(모두 로컬, 관전자 PC 에서만):
- `u = f_getuserplayerid()`, `u ∈ slots`(기본 128~131)일 때만. 상태 `mode`·`wait` 는 라이브러리 전용 `EUDVariable`(공유 로직이 읽지 않는다) — 원본의 Timer EUD 주소(0x58DBDC)를 받지 않는다.
- 채팅창이 닫혀 있고(`0x68C144 == 0`) `wait == 0` 이면 `keys` 를 차례로 보고 눌린(엣지/레벨) 첫 키의 모드로 `mode` 를 정하고 `wait = delay`, 문구(CP=u 로 DisplayTextAll, 뒤 `f_setcurpl2cpcache`)·소리.
- `wait > 0` 이면 매 프레임 1 줄인다 — **관전자 구역 안에서(모든 슬롯)** → B1 수정.
- 채팅창이 열려 있고 `mode ≠ 0` 이면 `0x68C144 = mode 값`(모드마다 트리거 1). `always="all"` 이면 mode 를 2 로 두고 키·문구를 만들지 않는다(OBA, 트리거 1).
- 키 판정은 `local.key_held`(레벨, 기본)·`local.key_pressed`(엣지). `delay=0` 이면 엣지 강제. `always` 와 `keys` 는 배타(B2 방지).

**exit_trap 원리**(R4b D4, eudplib 사상): 게임 시작 때 `pts + 12·owner + 8`(= list_owner 목록의 `tstart` 주소)의 EPD 를 한 번 읽어 두고, 매 프레임(메인 루프 끝) 대상 PC 에서만 그 `tstart+4`(next)를 자기 순환 트리거로 덮는다. `tstart` 는 매 프레임 자기 next 를 되돌리므로 정상 실행은 순환에 들어가지 않고, 게임을 떠날 때 SC 가 목록을 따라가다 멈춘다(추측). **기본으로 막혀 있다**(`enable=True` 이중 확인 + `EPWarning`). SC 정리 루틴 동작이 추측이라 목록 주인이 틀리면 다른 PC 가 멈출 수 있어 인게임(F19-4) 전까지 실험 기능.

**비용**(docs/COSTS.md "misc ObserverChat (WP19)"·"misc 나머지 (WP19)", 2026-09-17): ObserverChat.tick 본문 22(키 3개, 문구·소리·모드 쓰기 포함) / 호출 자리 3, 관전자가 아닌 PC 는 판정 1. always='all' 본문 2. host_player 시작 1회(f_memcmp 1벌 + 플레이어마다 호출 2). Countdown.tick 액션 1. is_widescreen 호출 자리 약 20(로컬, 비용표 제외).

**시험**: `t_misc_obs.py` — **128·131 두 슬롯에서 두 번째 입력**(B1), 채팅 닫힘/열림, 관전자 아닌 PC 무변화, 문구 CP=이 PC·소리, CP 복구, always·edge·여러 모드, 빌드 오류(always+keys, mode='player'), epScript 예제·인게임 맵 3종 번역·euddraft 빌드. `t_misc.py` — host_player(슬롯별·미발견·중복), HostNameIs, hotkey Set/Get, Countdown(포화·done·at_least·add), is_widescreen 빌드·실행, **unsafe_exit_trap 이 enable 없이 막히는지**(expect_build_error).

**위험·미정**: ObserverChat 은 로컬만 쓴다(안전). host 표·부대 지정 표의 공유성, `0x68C144` 값 정의, is_widescreen/exit_trap 은 인게임 확인 전(F19-1~4). exit_trap 은 인게임 통과 전까지 unsafe.

**S6/R4b(초안)와 달라진 점과 이유**
1. 상태를 원본 Timer EUD 주소 대신 라이브러리 전용 변수(mode, wait)로 — 로컬 전용 표시가 명확하고 정의되지 않은 틈(0x58DBDC)을 안 쓴다(S6 6-7).
2. 딜레이 감소를 관전자 구역 안에 두어 모든 슬롯에서 동작(B1 수정) — 원본은 Ob1 조건뿐이었다.
3. 문구는 `DisplayTextAll`(CP=이 PC) + `f_setcurpl2cpcache`(원본은 FP 로 되돌림, S6 6-10).
4. `decorate` 는 판(`strdesign.set_style`)이 정해졌을 때만 적용(정하지 않았으면 문구의 색 코드를 그대로) — 시험 안정성.
5. ObserverChat.tick 본문 22 는 S6 4.3 초안(≈12)보다 큼 — 초안이 문구·소리를 세지 않았다(costs 메모).
6. is_widescreen 은 `local.is_widescreen()`(초안) 대신 `misc.is_widescreen(loc)` — local.py 는 WP13 소유라 고치지 않았다(아래 3절 보탬·7절 참고). 로케이션을 받는다(FindSDLocal, R4b D5).
7. `unsafe_exit_trap` 은 `enable=True` 이중 확인 + 경고로 기본 비활성(R4b D8, D10).

---

### 4.20 `cgrp` 와 28장 스프라이트 (3단계) — **WP21 완료**

**목적**: CtrigAsm 29장 CGRP(CS_Photo.exe 가 8비트 BMP 로 만드는 점 그림 표)를 eudplib 맵에서 그린다. 28장 스프라이트 함수는 4.15.1.

**근거**: R4a B.1~B.5, 가이드북 29장(8315~8642 — 형식 8321~8345, CS_Photo 사용법 8347~8499, 헤더 활용 8527~8538, 가변 그림 8543~8567, UnlimiterX 8573~8642), 예제 29-4~29-10(18217~18620). 사용 0회. **CS_Photo.exe 와 실제 .cgrp 파일은 이 저장소·Ubuntu 환경에 없다**(찾아봄) → 형식은 문서·예제 코드뿐이고, 합성 파일로 시험했다. 실제 파일 확인은 인게임 F21-7(사용자에게 CS_Photo 가 만든 .cgrp 한 개를 받는다). DPS 이식판(a7aad90)에는 CGRP 코드가 없다(새로 작성).

**파일**: `eudext/cgrp.py`, `tests/t_cgrp.py`, `examples/cgrp_example.{eps,eds}`, 인게임은 `examples/sprite_ingame`(F21-6·F21-7).

**형식**(B.1, 리틀 엔디언): +0 dword 전체 점 수(뜻 미확인), +4 가로 칸 수 W, +8 세로 칸 수 H, +12 word 점 가로 크기, +14 word 점 세로 크기(예제 29-8 이 아래 워드를 X 로 읽음 — B.1 표의 "가로/세로" 순서와 같다), +16 칸 W·H 개(행 우선, 빈 칸 포함). 칸: 비트 0 Red(화면 출력 0)·1 Green(13)·2 Blue(16)·3 White(17)·4 EMP(8)·5 Indigo(12)·6 Box(15)·7 Fill·8~10 흑색 명암(10)·11~13 적색 명암(6)·14~23 이미지·24~31 높이.

**API**

```python
from eudext import cgrp
from eudext.cgrp import CGRP, CGRPLayer, CGRPPainter

cg = CGRP.load(path, missing_ok=False, base=None)    # = cgrp.load / f_load. 상대 경로: base(없으면 작업 폴더 — euddraft 는
                                                      #   eds 폴더) → 환경 변수 EUDEXT_CGRP_DIR. missing_ok 면 빈 그림(found=0)
cg = CGRP.from_bytes(data, path=None)                 # 길이 < 16·≠ 16+4WH·W·H > 2²² 는 한국어 오류
cg = CGRP.from_cells(w, h, cells, dot_w=3, dot_h=3, count=None)   # 합성 (count 기본 = Fill 칸 수)
cg = CGRP.from_rows(rows, dot=3, legend=None, image=233, height=0)  # 글자 그림 (R/G/B/W/E/I/X/#/r/g/b/k)
cg.count, cg.width, cg.height, cg.dot_w, cg.dot_h, cg.cells, cg.found, cg.path
cg.fill_count, cg.painted_count, cg.pixel_width, cg.pixel_height
cg.cell(x, y); cg.points(select=FILL, mask=None); cg.white_points(); cg.to_bytes()
cg.count_meaning()                                    # "fill" | "painted" | "cells" | None (헤더 +0 의 뜻 확인용)
cg.summary()                                          # 한 줄 요약 (printAll 에 그대로)
layers = cg.layers(mode="stack", height=None, image="cell", color=None)   # → [CGRPLayer]
lay = CGRPLayer(name, color, image, height, points)   # color·image None = 바꾸지 않음(CtrigKind 면 그 종류 값)
lay.count, lay.points, lay.data(), lay.db             # 점마다 dword dx | dy << 16 을 구운 Db
p = CGRPPainter(source, kind, owner, per_frame=64, delay=4, sprite=None, on_fail="skip")   # source = CGRP 또는 층 목록
p.start(ox, oy); p.tick(); p.stop(); p.done(); p.running()                # done/running = 새 Condition
p.dropped, p.drawn (EUDVariable), p.total, p.layers
cgrp.black_level(v), red_level(v), cell_image(v), cell_height(v)          # 칸 값 풀기 (f_ 판 있음)
cgrp.RED … FILL, COLOR_CODES, LAYER_ORDER, HEADER_SIZE
```

epScript: `const cg = cgrp.CGRP.load("a.cgrp");`(클래스 메서드 이름은 번역이 바꾸지 않는다), `const p = cgrp.CGRPPainter(cg.layers(), k, P8, per_frame=32);`, `p.start(384, 1120); p.tick(); if (p.done()) {…}`. 중첩 `list(list(…))` 는 펼쳐지므로 `CGRPLayer` 의 점은 펼친 목록 `list(dx0, dy0, dx1, dy1)` 도 받는다.

**층 만들기**(`layers`, 컴파일 시점 — 그릴 점만 추림)
- `mode="stack"`(예제 29-6·29-10): 기본색 층 Red·Green·Blue·EMP·Indigo·Box(색 비트마다 한 층 — 한 칸에 여러 비트면 여러 층)와 색 비트 없는 Fill 칸(`fill`, 색 None)을 높이 `height`(기본 5)에, 적색 명암 N 인 칸을 화면 출력 6·높이 +1 에 N 번, 흑색 명암 N 인 칸을 화면 출력 10·높이 +2 에 N 번(가이드북: 흑색 > 적색 > 기본색 순으로 높이).
- `mode="height"`(예제 29-5·29-7): 같은 층을 **칸 높이 + height(기본 0)** 에, 적색 명암은 +1 에. 흑색 명암은 찍지 않는다(명암 배경을 깔고 높이차로 — 예제 방식).
- `mode="fill"`(예제 29-4): Fill 칸만 한 층, 색 `color`(None = 바꾸지 않음), 높이 `height`(None = 칸 높이).
- `image="cell"` 이면 칸의 이미지 비트(찍을 칸에서 998 을 넘으면 오류), None 이면 스프라이트 이미지를 건드리지 않음, 번호면 그 값.
- 흰색(비트 3)은 넣지 않는다 — 영구 스프라이트로 두면 42틱 뒤 튕긴다(GB 8466). `white_points()` 로 받아 따로 갱신한다.
- 순서: `LAYER_ORDER`(분류) → (이미지, 높이). 점 순서는 행 우선. 점 위치 = (열·dot_w, 행·dot_h) px — 65535 를 넘으면 오류. 높이 +1·+2 는 255 에서 멈춤.

**그리기**(`CGRPPainter`, 런타임)
- `tick()` 은 painter 마다 본문 한 벌(EUDFunc, 호출 자리 1). 상태: 단계 번호·남은 점·점 포인터(EPD)·대기·원점.
- 층마다 먼저 전역 dat: 무기 투사 방식 ← 7, flingy 최고속도 ← 0, elevation[탄막 유닛] ← 층 높이, [sprites[sprite].image ← 층 이미지], [images[이미지].화면 출력 ← 층 색] — 한 트리거(EUDSwitch 로 층 고르기). 층의 이미지·색이 None 이면 CtrigKind 의 image·color, 그 밖의 종류면 그 칸을 건드리지 않는다. sprite 기본 = CtrigKind.sprite.
- 점마다: `f_wread_epd` 두 번(dx, dy) → `bullet.perma_sprite` 와 같은 본문(방향 0, 원점 + 점, CtrigKind 면 Y − 2). 원문처럼 점마다 dat 를 쓰지 않고 층마다 쓴다(점당 트리거 1 절약).
- (이미지, 색)이 바뀌는 층으로 넘어가면 그 프레임을 끝내고 `delay` 프레임 더 쉰다(총알은 트리거 뒤 게임 로직에서 만들어지고 이미지 설정은 전역 — 예제 29-6 의 Delay). 높이만 바뀌는 층은 쉬지 않는다(높이는 유닛을 만들 때 정해진다 — 예제 29-7 이 한 프레임에 점마다 높이를 바꾼다).
- 빈 칸이 없거나 생성이 실패한 점: `on_fail="skip"`(기본, 원문처럼 버림)은 `dropped += 1` 하고 진행, `"retry"` 는 `dropped += 1` 하고 그 프레임을 끝내 다음 프레임에 같은 점부터. `drawn` = 만든 점 수. `start` 는 둘 다 0 으로.
- 빈 그림(층 없음)은 `start` 가 곧바로 done. `stop` 은 멈춤(done 거짓).
- 같은 프레임에 같은 무기·flingy·스프라이트·이미지를 쓰는 다른 코드가 있으면 설정이 섞인다(문서화).

**비용** (조각 costs.md "cgrp (WP21)"): tick 호출 자리 1, 실행 = 점 1개 142(층 1개)·점 8개 1,028(점당 약 126), 쉬는 프레임 7, 멈춤 3. tick 본문은 painter 마다 한 벌 — 층 1개 29, 2개 34, 6개 52, 12개 72(층당 약 5: switch 칸·설정 액션·대기 칸) + perma 본문 12(공유). start 호출 2/실행 4. 한 번 페이로드: painter 한 개 약 15~22KB(tick 본문) + 점 1개(반복 포함)당 4B + perma 본문 약 17KB(bullet 과 공유). 원본 방식(모든 칸을 런타임에 읽음)과 달리 빈 칸 비용이 없다. 3.8 에 cgrp 목표는 없다(도형 찍기 목표 "트리거 수가 점 수와 무관, 1점 4B" 는 만족).

**시험**: `tests/t_cgrp.py` (978 판정, 약 4초) — 파일 773: 시험이 `int.to_bytes` 로 만든 합성 파일 60벌(헤더·칸·되쓰기·cell·크기), 점 크기 워드 순서, 오류 9종(빈 파일·15B·헤더만·±1B·±4B·너무 큼), load 경로 5종(절대·base·작업 폴더·환경 변수·없음/missing_ok)·깨진 파일, count_meaning 4, summary, white_points, from_rows·from_cells, 칸 값 풀기 302, **층 = 따로 짠 참조 구현(`ref_layers` — 분류마다 칸을 다시 훑음) 무작위 400벌 × 방식 10가지**, 흰색 제외·여러 색·높이 상한·65535px 경계·칸 이미지 999/1023, CGRPLayer 바이트·Db·펼친 목록·오류, painter 7개의 대기 자리·층 설정 액션(필드 표로 계산)·인자 오류 13종. 에뮬레이터 189(판정 하나가 한 번의 그리기 전체): **틱마다 만든 점 = 참조 타임라인(`ref_ticks`)**(생성 순간의 로케이션·높이·스프라이트 이미지·화면 출력·투사 방식·최고속도·소유자를 CreateUnit 처리기로 기록), painter 5종 × 원점 4(0xFFFFFFFD·0x7FFFFFFF 넘김 포함), 변수 소유자 3, 빈 그림, 칸 없음 skip(모두 버림·틱 수 같음)·retry(제자리 5틱 뒤 이어서 전부), start 다시, stop, CP 5값 × 4틱, 끝난 뒤 tick, 쓰기 칸 ⊆ 허용. epScript 예제 번역·에뮬레이션(40 사이클, 점 8개 위치)·euddraft 빌드. 변이 시험(시험 파일 밖): per_frame +1·delay +1·대기 자리 하나 빼기·색 안 쓰기·점 순서 뒤집기 — 모두 실패로 잡힌다.

**인게임**: F21-6(합성 그림 모양·색, 필수), **F21-7(실제 CGRP 파일, 필수 — 사용자가 CS_Photo 로 만든 .cgrp 를 `sprite_user.cgrp` 로 두고 빌드)**.

**위험**: 형식은 문서뿐 — 헤더 +0 의 뜻, 점 크기 워드 순서, 명암 비트 폭(가이드북 표는 0~7, 예제는 2비트 마스크 0x300·0x1800 으로 0~3 만 읽음 → D68), 이미지·높이 비트를 CS_Photo 가 실제로 채우는지는 F21-7 로 확인. 가이드북: CGRP 는 UnlimiterX 필수, 점 1개 = 탄막 유닛 1개가 6프레임 칸을 차지(per_frame × 6 < 빈 칸), 시야 안 총알 약 4096 을 넘으면 튕김 → 대량이면 컴퓨터 소유·시야를 끄고 그린다(GB 8605~8640).

**초안(R4a B.4)과 달라진 점과 이유**
1. `layers(mode=…)` 에 `"fill"` 과 `image`·`color` 인자를 더했다(예제 29-4 단색 방식, 이미지 비트를 쓰지 않는 파일). `CGRPLayer` 의 `draw_func` → `color`, `script` 는 없앴다(CGRP 에 iscript 정보가 없다 — 종류의 iscript 를 쓴다).
2. `CGRPPainter(source, …)` 는 CGRP 또는 층 목록을 받고, `sprite=`·`on_fail=`·`stop()`·`running()`·`dropped`·`drawn`·`total` 을 더했다. delay 기본 4(예제 값). tick 은 painter 마다 EUDFunc(호출 자리 1).
3. 층 설정(dat)을 점마다가 아니라 층마다 쓴다. 층의 None 이미지·색은 CtrigKind 값으로 채운다(앞 층 설정이 새어 들어가지 않게).
4. 원본 파일을 `Db` 로 싣고 런타임에 모든 칸을 읽는 방식(B.4 "원본 그대로")과 가변 그림(예제 29-9: 여러 CGRP 를 스캔·유닛 스프라이트로 매 프레임), 흰색 갱신은 만들지 않았다 — 사용 0회, 필요하면 `points()`/`white_points()` + `scan_sprite`/`unit_sprite(track=False)` 로 짤 수 있다(D72).
5. 헤더 점 수는 검사하지 않고 `count_meaning()` 으로 뜻만 맞춰 본다. 칸 이미지 > 998 은 `layers` 오류.

---

### 4.21 `dbg` — 디버그 브리지 (게임 중 값 → 외부 리더·자동 판정) — **완료(2026-09-18, feat/debugbridge)**

**목적**: 인게임 확인 항목(eudext 확인 맵 26개 + 이식판 5개)을 사람이 화면으로 하나씩 보는 대신, 맵이 값을 블록에 남기고
외부 도구가 읽어 **한 번에 판정**한다. 튕길 위험이 있는 것만 사람이 따로 본다(분류 `docs/ingame_auto/classification.md`).
안전한 자동 점검은 **통합 맵 하나**(`auto_all`, 20 phase)에서 차례로 돌린다 — 그래서 점검 **단계(suite)** 표식을 둔다.

**근거**: CtrigAsm 맵용 `theSeed\MapLogic\DebugBridge.lua`(블록 배치 v1, 사용자 작성, c5d0776)와 리더 `dbg_reader.py`·`dbg_gui.py`·
`fake_game.py`(DPS_Enhance eudplib-port `tools/debugbridge`, 021b77b). eudext 판은 **같은 배치**라 기존 리더가 그대로 읽는다(시험:
사본 리더의 `find_blocks`·`Block`·`Symbols`·`Viewer` 로 해석). 페이로드 블록 방식은 이식판 `eud/ctrig/profile.py`(CounterBlock).

**파일**: `eudext/dbg.py`, 리더 사본 `eudext/tools/debugbridge/{dbg_reader,fake_game}.py`(5.5), 자동 판정 `eudext/tools/ingame_auto.py`(5.5),
시험 `tests/t_dbg.py`, 예제 `examples/dbg_example.{eps,eds}` + 판정 명세 `examples/dbg_example_spec.json`, 분류 자료 `docs/ingame_auto/`.

**블록 배치 v1** (dword 인덱스 — 모듈 설명에 표): 0~7 서명(게임 시작 때 SetMemory 로 조립 — 맵 파일에는 연속 사본이 없다), 8 판, 9 빌드 ID,
10 자기 EUD 주소, 11 용량(W | P<<16), 12 seq 시작, 13 게임 프레임(0x57F23C), 14 로컬 플레이어, 15 사용 개수, 16~19 0x57EEE8 사본,
20~23 0x57FD3C 사본, 24.. 감시 W칸(**첫 칸 = eudext 표지 = 맵 이름 CRC32**), 24+W seq 끝, 25+W.. 프로브 P칸.

**API** (모듈 함수는 `f_이름`, 파이썬 별칭은 `f_` 없는 이름 — epScript 는 `dbg.watch(…)`)

```python
dbg.setup(map_name=None, addr="top", watch_slots=64, probes=256, enable=None, build_id=None, tag=None,
          symbols=None, allow_outside_mirror=False)          # → Bridge. 맨 먼저(모듈 전역 const)
dbg.watch(name, src, signed=False, suite=None)             # EUDVariable 1칸 / 상수 주소·Cell·EUDLightVariable·페이로드 주소 1칸 /
                                                           #   Int64 2칸 / Int128 4칸 — 매 프레임 (seq 안)
dbg.snapshot(name, src, n, every=1, text=False, is_epd=False, suite=None)   # n dword (StringBuffer·EUDArray·Db·주소·주소 변수)
dbg.snapshot_text(name, src, n, every=1, …)                # 리더가 UTF-8 글로 풀어 본다
dbg.capture(name)                                          # every=0 스냅숏을 이 자리에서만 복사 (채팅 버퍼 같은 큰 칸)
dbg.probe(name, suite=None) → Action                       # 실행될 때마다 +1 (꺼지면 비활성 액션)
dbg.hit(name, cond=None, suite=None)                       # 지날 때마다(조건이 참일 때) +1
dbg.check(name, cond, suite=None)                          # 판정 카운터: 전체 +1, 참이면 통과 +1
dbg.result(name, passed, total, suite=None)                # 맵이 센 결과 보고 (통과·전체·보고 횟수)
dbg.mark(name, value=1, suite=None) / dbg.mark_action(name, value=1)   # 완료 표식 ("done" 을 자동 판정이 기다림)
dbg.suite_begin(name, phase=None) / dbg.suite_end(name, ok=None)       # 점검 단계 (with dbg.suite(name): 는 파이썬 전용)
dbg.enabled (모듈 속성, setup 기본값) / dbg.f_enabled() → 1/0
dbg.layout() / dbg.symbols_doc() / dbg.reset()             # 시험·도구용
```

**위치**: 기본 `"top"` = CtrigAsm void 맨 위(0x5967F0) 아래 16 정렬 — 기본 용량이면 **0x596280~0x5967E4**(DebugBridge.lua 와 같은 자리).
근거: theSeed·DPS 인게임에서 DebugBridge 로 SC:R 이 읽고 쓰는 것을 확인한 자리이고, void 는 아래(0x58F500)부터 채워지며 SCR_DB
(0x58F500~0x594438)·MSQC 채널도 아래쪽이다. 1.16.1 미러 구역이라 리더 `--peek`(블록과 같은 오프셋으로 미러 주소 직접 읽기)가 된다.
정수 주소(미러 구역 밖이면 오류 — `allow_outside_mirror`), `"payload"`(Db — void 를 안 쓰지만 `--peek`·`--diag` 선형 진단 불가, 게임이 끝나도
옛 블록이 남을 수 있음 — 리더·도구는 seq 가 움직이는 블록만 고른다). SCR_DB 가 설정돼 있으면 그 칸과 겹치는지 검사한다.
하이브리드 맵(DebugBridge.lua 와 함께)은 자리가 겹치므로 addr 를 옮긴다.

**의미**
- 매 프레임 코드 = **게임 루프 시작점**(`_compat.on_game_loop_start`): seq 시작 +1(+ 프레임 변수 +1) → 게임 프레임 읽기 → 변수 감시
  (SeqCompute 한 줄) → 주소·스냅숏 복사(`f_dwread_epd`/`f_repmovsd_epd`, every 는 카운트다운 변수) → seq 끝 +1. 보이는 값은
  **앞 프레임 끝**. 심볼 JSON 도 여기서 쓴다(칸 번호를 이때 정한다 — 항목 주소는 `Forward`).
- 시작 1회: 미러 블록의 **쓰는 칸만** 지운다(서명·seq·게임 프레임·사용 감시 칸·사용 프로브 칸 — 같은 SC 프로세스의 앞 게임 값.
  본문은 게임 루프 훅에서 칸을 정한 뒤 만들고 시작 코드는 `_parts.call_sub` 로 부른다) → 머리 → 정적 사본 → **서명은 맨 마지막**.
  모듈 전역 setup 은 `EUDOnStart`(start1), 빌드 중 setup 은 주 함수 뒤 시작 목록(start2) — 둘 다 주 함수보다 먼저 실행.
  쓰지 않는 칸은 옛 값이 남는다(리더는 사용 개수까지만 본다).
- 빌드 밖 설정·등록은 계속 남고, 빌드 중 것은 그 빌드에만(datpatch 규칙). 훅은 프로세스에 한 번 등록하고 꺼져 있으면 아무것도 안 낸다.
- 블록은 **맵만 쓰고 게임 로직은 읽지 않는다** → 로컬 분기 안의 hit·로컬 값 감시도 디싱크 없음(값은 PC 마다 다를 수 있다).
- 단계: 전체 칸 3(지금 단계 번호·마지막으로 시작한 단계 번호·마지막 사건 프레임) + 단계마다 4칸(상태 0/1/2·시작·끝 프레임·맵 판정 0/1/2).
  번호 = `phase`(통합 맵 phase 번호) 또는 등록 순서의 빈 번호(겹치면 빌드 오류). **코드 순서로 begin~end 사이에 등록한 항목은 그 단계**
  (심볼 `suite`) — 이름 앞머리 `c3.` 도 같은 단계로 본다(도구). 한 번에 하나씩 도는 것을 전제로 한다(끝나면 지금 단계 = 0).
- 꺼짐(`enable=False`, `dbg.enabled=False`, 빌드 환경 `EUDEXT_DBG=0` = 부트 `Dbg : 0`, setup 없음): **트리거·페이로드 0**(시험:
  dbg 호출 없는 빌드와 트리거 수·페이로드 크기가 같다). epScript 인자 식이 내는 트리거는 남는다.
- 심볼 JSON = 리더 `--symbols` 형식(format·layout_version·build_id·signature·block_eud·total_dwords·header·watch_start·watch_cap·
  seq_end·probe_start·probe_cap·static_copies·dynamic_copies·watches[slot,name,kind,src,site]·probes[index,name,sites]·vars·mems)
  + `eudext` 확장(map_name·build_tag·where·marker·used·watches·texts·hits·checks·results·marks·suites·suite_slots·result_names, 항목마다
  suite). 감시 kind: var·mem(상수 주소 — 리더 `--diag` 대조)·pmem(페이로드·변수 칸)·text·dwords·const(표지). 64/128비트는 `이름.lo/hi`·`w0~w3`.
  파일: `setup(symbols=)` > `EUDEXT_DBG_DIR`(부트 `DbgDir`) > `EUDEXT_WORK/dbg` > `<임시>/eudext_work/dbg`,
  `DebugBridge_<맵>_<빌드 ID>.json` + 최신 사본 `DebugBridge_symbols.json`. **C:\Temp 에는 쓰지 않는다.**
- map_name 기본 = euddraft eds 의 `[main] output` 파일 이름(확장자 뺌), build_id 기본 = 시각 × 상수 ^ 이름 CRC (31비트, 0 아님).

**비용**(docs/COSTS.md "dbg"): 매 프레임 설정만 37(seq 2 + 게임 프레임 읽기) / 변수 감시 +1씩(8개 46) / Int64 +3 / 주소 감시 +35 /
스냅숏 단어당 약 35(16단어 602, every=4 평균 180, every=0 은 0) / 단계는 매 프레임 0. 호출 자리: hit 1, check(조건) 2, check(변수) 4,
result 2, mark 1, suite_begin 2, suite_end(조건) 4, capture(16단어) 5/실행 565. 시작 1회 실행 약 370. 한 번 페이로드: 기본 +5.2KB
(쓰는 칸만 지우기 — 처음 구현의 345칸 전부 지우기는 +18.0KB), 페이로드 판 +6.2KB.

**시험**: `tests/t_dbg.py` 292 판정(약 40초, Windows — run_all 기준, harness 5 포함) — 파이썬 106(setup 검사·기본 자리, 명세 검사 + **분류 286항목을 명세에 그대로 담기**,
항목 판정 32, 확인 문서 쓰기(가짜 문서 LF/CRLF+BOM·실제 문서 사본 시험 실행 — 원본 불변 확인)), 에뮬레이터 72(모든 종류를 싣는 빌드 10사이클:
머리·정적 사본·서명·seq·감시·64/128비트·Cell·페이로드 주소·글·every·주소 변수·capture·hit·check·result·mark·단계 번호/상태 —
**사본 리더 파서로 해석**, 옛 게임 값(0xDEADBEEF·옛 서명) 지우기, seq 시작 → 감시 → seq 끝 쓰기 순서, CP 보존, 페이로드 판,
꺼짐 3가지 트리거·페이로드 같음, 등록 오류 5종(harness), 빌드 끝 오류 5종(하위 프로세스), 매 프레임 비용), 서명·epScript 27
(서명이 scx·scenario.chk·페이로드에 연속으로 없음, 예제 번역·에뮬레이션·**예제 명세로 판정 = 통과**·euddraft 빌드·`Dbg : 0`), 판정 흐름 23(에뮬레이터 스냅숏 →
MapRun: 통과·실패·단계 순서·멈춤·튕김·단계 시간 초과·ever·맵 시간 초과·심볼 없는 단계), **Win32 통합 59**(원래 가짜 게임 자체 시험 모드를 고친 리더로 읽기(회귀) 12 + 에뮬레이터 스냅숏을
`fake_game.py --replay` 프로세스에 올려 리더 `--once`·`--peek`·`--diag`·`--record` 와 `ingame_auto.py` 를 실제 Win32 읽기로:
맵 네 개 연속(미러·페이로드·미러 자리 재사용), 단계 멈춤 "멈춤: c2", 프로세스 종료 "튕김: e2", 결과 누적·진행 파일, 확인 문서 사본의
빈 칸 두 줄만 씀·사용자가 적은 칸 그대로).

**인게임**: G-1(블록이 SC:R 에서 찾히고 값이 흐르는가 — **필수**, 맵 `work\dbg_example.scx`), G-2(자동 판정 도구로 예제 판정). 결과가 나오면
통합 맵(`auto_all`) 계측으로 넘어간다.

**위험·미정**
- SC:R 이 void 맨 위(0x596280 부근)를 eudplib 맵에서도 같게 받는지는 G-1 로 확인(CtrigAsm 맵에서는 확인됨). 페이로드 판의 SC:R 메모리
  배치(옛 블록이 남는지)도 G-1 에서 본다.
- 정적 사본 주소(0x57EEE8·0x57FD3C·0x512684)와 게임 프레임(0x57F23C)은 DebugBridge.lua 가 인게임에서 읽던 주소라 안전하다고 본다.
- 프로브 칸(hit·check·result·mark·단계·capture)은 seq 밖이라 찢어진 읽기를 막지 못한다 → 도구가 두 번 읽어 같을 때 판정한다.
- 리더의 전체 메모리 스캔은 SC:R 에서 몇 초 걸린다 → 도구는 판정 중에는 15초마다만 다시 훑는다(블록 머리는 매번 읽는다).
- 멈춤 판정은 싱글 일시 정지(메뉴)와 구분하지 못한다(`stall_s` 를 넉넉히 — 기본 15초).
- SCR_DB·SNQC 시그니처로 오프셋을 잡는 찾기(eudext 가 없는 판용)는 설계만(5.5).

---

## 5. 개발 도구

### 5.1 `testing` — 트리거 에뮬레이터 (WP0 완료)

- `testing/emu.py`: DPS `eud/tests/emu.py` 를 옮겼다(0.81 에서 고치지 않아도 돌았다). 비공개 가로채기는 `_compat` 경유. 흉내 내는 것: Deaths/Memory 조건(마스크 포함), SetDeaths(SetTo/Add/포화 Subtract, 마스크), next 사슬·자기수정, 보존 플래그, CP(player 13). WP0 이 더한 것: 게임 루프 시작점 설정, 조건·액션 처리기 표(`cond_handlers`/`act_handlers`), 메모리 초기값 표, 바이트 읽기·쓰기, 스냅숏.
- **주의**: 마스크 Add/Subtract 식은 가정이다(S8 8절 인게임 결과로 고친다).
- `testing/scmodel.py`: 모듈 시험에 필요한 SC 모델을 **필요한 만큼만** 더한다(R2 4.3).

| 확장 | 필요한 모듈 |
|---|---|
| Switch 조건 / SetSwitch **(WP0 완료, 스위치 표 주소 0x58DC40 은 인게임 확인)** | misc, 일반 |
| 게임 메모리 초기값(0x512684, 0x57EEE8, 0x6509B0) **(WP0 완료)** | local, players |
| DisplayText 캡처(STR/STRx 해독) **(WP11 기록판: DisplayText(9)·PlayWAV(8) 을 CP·문자열과 함께 기록, `install_text`/`Suite(memory={"text": True})`, `machine.text_model.texts()/wavs()`. 표시 대상 판정·줄 위치는 WP6/WP17)** **(WP6b: `testing/dispmodel.py` — 문자열 표를 0x191943C8 에 올리고 DisplayText 순간의 메모리를 읽음, 보임 = CP == 이 PC, CCMU·13번째 줄, 가짜 stat_txt(0x6D5A30), 이름 두 표, `live_strings()` 로 chatmodel 연결)** | display, chat |
| CreateUnit 기록 + `0x628438` 모델 (실패 주입 옵션 포함) **(WP10 완료: CreateUnit·CreateUnitWithProperties 기록, 빈 칸 목록 머리 이동, `fail_next(n)`·`fail_when(pred)`, 빈 칸 없음, 터렛 두 칸, 생성 위치 = MRGN 사각형 중심)** | units, plot, spawn, bullet |
| MoveLocation / MRGN 모델 **(WP7 완료: `testing/locmodel.py` — scmodel 을 고치지 않고 따로 끼운다. `install(machine, record=True, move=True)`, CreateUnit(WithProperties) 순간의 로케이션 사각형·중심·수량·props 기록(`PlotRecord`), MoveLocation(38): 찾는 곳 안 첫 유닛(활성 목록 순서) 위치로 크기 그대로 옮김, 없으면 찾는 곳 중심 — 인게임 미확인 가정. harness 는 `Suite(prep=lambda m: locmodel.install(m))`. 에뮬레이터 메모리에는 맵 MRGN 이 없으므로 시험이 `set_location` 으로 채운다)** | plot, spawn, mathx |
| CUnit 표 스텁 (+0x28 좌표 포함) **(WP10 완료: 1700칸, prev/next 링크, HP·스프라이트·좌표·주인·주문·종류·서브유닛·고유 바이트·상태, 활성 목록 0x628430, 죽는 중/죽음 처리 `process_deaths`)** | units, pool, spawn |
| KillUnit(유닛·주인 전체), Order 기록(상자·목표) **(WP10 완료: KillUnit·KillUnitAt·RemoveUnit·RemoveUnitAt(주문 0 표시, AnyUnit·AllPlayers, 로케이션 범위는 유닛 중심점) + Order 기록. 유닛 이동·분류 230~232·Force 대상은 WP12)** **(WP12 완료: `testing/locmodel.py` 의 `orders`(OrderPlot — 시작·목표 사각형, 목표 중심, 명령받은 유닛 = 시작 사각형 안의 주인·종류가 맞는 살아 있는 유닛 전부, `order_move=True` 면 목표 중심으로 바로 옮김), `scmodel` KillUnit/RemoveUnit 의 Force1~4(18~21 — 플레이어 구조체 +10 세력 바이트). 특수 유닛 분류 230~232·MoveUnit·GiveUnits 는 spawn 시험에 필요 없어 미룸)** | spawn |
| 플레이어 목록 여러 개, before/afterTriggerExec 순서, 수신 펄스 주입 **(WP18 완료: `testing/syncmodel.py` — `RecvModel`·`RefState`·`TurnSim`·`QCUnits`(MSQC 실제 코드용 가짜 QC 유닛, scmodel 유닛 모델 사용)·`load_plugin`·`set_humans`·`settings_of`. t_sync 781 그대로)** | sync, scrdb |
| 채팅 버퍼(0x640B60) 바이트 — 11줄·홀짝 정렬·0x640B58 **(WP17 완료: `testing/chatmodel.py` — 줄 원문·셀(홀수 +2)·포인터·꺼짐, `push_line/push_text`(SC 가 한 줄 쓰기 흉내, NUL 뒤는 그대로 = strcpy 가정), DisplayText 처리기(CP == 이 PC 일 때 `\n` 으로 나눠 쓰기, 글 기록 모델과 이어짐), 표시 시간은 파이썬 쪽 `advance()/expire` **가정**(위치 미확인), 원본 참조 타자기 `TypewriterRef`)** | chat, textfx, misc(ObserverChat) |

- `scmodel` 유닛 모델(WP10): `install_units(machine, free=None, insert="second"|"head", free_to="back"|"front", subunits=None, hp=None)` 또는 `install(machine, units={...})`(harness 는 `Suite(memory={"units": {...}})`). 모델 객체 `machine.unit_model`(`scmodel.unit_model(m)`). 상태는 전부 에뮬레이터 메모리라 `snapshot`/`restore`·`Suite.run(fresh=True)` 로 함께 되돌아간다(기록 `created`/`killed`/`orders` 와 실패 주입 설정은 파이썬 쪽이라 안 돌아간다 → `clear_log()`, `clear_failures()`). API 는 `UnitModel` docstring. 모델 가정(새 유닛은 활성 목록 두 번째 자리, 죽은 칸은 빈 칸 목록 끝, 터렛은 본체 다음 칸, 고유 바이트 +1)은 인게임 B10 결과로 고친다.
- `scmodel` 글 기록 모델(WP11): `install_text(machine, strings=None)` 또는 `install(machine, text=True)`. 문자열 표는 설치 때(빌드 직후) `string_table()` 로 한 번 읽는다. 기록 `records`(TextRecord: kind·cp·strid·text·cycle)는 파이썬 쪽이라 `Suite.run(fresh=True)` 로 안 비워진다 → `clear()`.
- WP16 시험은 자체 PlayWAV 기록기(`t_bgm.py` Recorder — CP·문자열 번호 → 이름, 문자열 표는 `scmodel.string_table()`)를 쓴다. 출력 맵의 MPQ 확인: `_compat.mpq_read_file(맵, 이름)`(출력 맵에는 `(listfile)` 이 없어 `get_file_names_from_listfile` 이 실패한다).
- `testing/locmodel.py`(WP7) — 로케이션 사각형 기록·MoveLocation(`install(machine, record=True, move=True)`, harness 는 `Suite(prep=lambda m: locmodel.install(m))`). 맵 chk 의 MRGN 은 에뮬레이터 메모리에 실리지 않는다(시험이 `set_location` 으로 채운다).
- `testing/chatmodel.py`(WP17): `install(machine, display=True, next_line=None, lines=None, clear_rest=False, expire=None)` → `machine.chat_model`. harness 에서는 `Suite(memory={"text": True}, prep=lambda m: chatmodel.install(m))`(scmodel.install 인자에 넣지 않고 prep 로 끼운다). WP19 ObserverChat 시험도 이것을 쓴다.
- `scmodel` 유닛 모델: `_make` 가 빈 칸 수를 앞에서 필요한 만큼만 센다(수천 기를 만드는 시험의 속도 — 동작 같음).
- 에뮬레이터 메모리에는 맵 MRGN 이 없다 — 이름 있는 로케이션을 쓰는 코드(spawn 의 `center="Location 13"`)를 돌리려면 시험이 사각형을 채운다 (`t_spawn._map_locations`: 기준 맵 chk 의 MRGN 을 그대로 복사).
- `players.run_as(players.Everyone, DisplayText(…))` 는 글 기록 모델에 **대상마다 한 줄**(기준 맵: 사람 1 + 관전자 4 = 5줄)이 남는다.
- `StringBuffer` 는 `LoadMap` 뒤(케이스 본문 안)에서 만든다. 문자열 버퍼 주소는 `t.watch(이름, GetMapStringAddr(sb.StringIndex))` 로 읽는다(WP5).
- 칸을 쓰는 모듈의 페이로드 순서(WP7): eudplib 은 CollectDependency(모으기) → WritePayload(ObjAllocator, 할당) → GetDataSize → WritePayload(PayloadBuffer, 쓰기) → GetDataSize 순으로 부른다. `DynamicConstructed` 가 아닌 객체의 크기는 모으기 뒤 바뀌면 안 된다(shape 의 게으른 표가 이 순서로 굳힘을 판단).
- eudplib 은 맵 시작마다 로케일 판별용으로 `0x628438 = 0` 을 두고 `CreateUnit(…, AllPlayers)` 를 일부러 실패시킨다(`string/locale.py` `_detect_locale` → `f_raise_CCMU`). 유닛 모델은 빈 칸이 없으면 플레이어를 해석하지 않고 실패로 기록한다(첫 사이클 기록에 이것이 하나 있다).
- `testing/harness.py`: 한 빌드에 여러 케이스를 모으고(빌드 시간 절약), 케이스 하나의 예외가 전체를 멈추지 않게 한다. 파이썬 참조 구현과 **무작위 + 경계값 차등 시험**, 실행 트리거 수 기록.
- 칸을 쓰는 모듈의 시험 방식(WP14): 대상 칸을 난수 보초값으로 채운 뒤 **마스크 밖 비트와 안 쓰는 칸이 그대로인지**, 페이로드 밖 게임 메모리의 **바뀐 주소 집합이 허용 집합 안인지**(`Machine.mem` 비교) 본다 — spawn·plot 시험에도 쓸 수 있다.
- MRGN(로케이션 사각형)은 맵 chk 에 있어 에뮬레이터 메모리에는 0 이다 — 로케이션을 옮기지 않고 쓰는 시험(bullet_at)은 `UnitModel.set_location` 먼저.
- **빌드 때 오류가 나야 하는 케이스**: `@suite.case(이름, expect_build_error=예외 클래스 또는 튜플, expect_message=정규식)`. 본문을 만들다 그 예외가 나면 통과 1, 안 나거나 다른 예외이거나
  메시지가 맞지 않으면 실패 1(판정 이름 "빌드 오류 기대", `build()` 때 기록). 이런 케이스는 실행하지 않고(`run`/`check`/`diff` 는 실패로 기록) 잡은 예외는 `suite.cases[이름].caught` 에 남는다.
  본문은 `_compat.isolated_scope` 안이라 예외 전에 만든 트리거·열린 블록은 바깥 흐름에 붙지 않는다(시험함). SaveMap 단계 오류(`Orphan condition` 등)는 이 표시로 시험할 수 없다.
  `expect_build_error` 가 없는 케이스는 예전과 같다. `summary()` 행에 `expect_build_error`(bool)가 더해졌다. 사용 예: `t_cell.py` 빌드 오류 50건.
- **`suite.restart(memory=None, *, init_mem=None, prep=None, **바꿀 키)`**: 빌드한 프로그램을 그대로 두고 메모리를 빌드 직후(게임 시작 전) 스냅숏으로 되돌린 뒤
  `scmodel.install(machine, **memory)` → `init_mem`(`{주소: 값}`) → `prep(machine)` → 초기화 사이클 2번(빈 사이클 기준값·케이스 호출 오버헤드를 다시 잰다)을 돌고 그 상태를 `reset()` 기준으로 기억한다.
  "게임 시작 1회" 코드(`EUDOnStart`, `f_getuserplayerid` 초기화, 비보존 트리거)가 새 메모리로 다시 돈다 → **이 PC 번호(0x512684)마다 새로 빌드하지 않아도 된다**(WP8 `t_players.py` 의 번호별 빌드를 이것으로 바꿀 수 있다 — 고치지는 않았다).
  키워드는 `suite.memory` 에 덮어쓰고(`restart(local_player=3)`), `memory=` 는 통째로 바꾼다. `init_mem`/`prep` 은 주면 바꾸고 안 주면 그대로(`{}`/`False` = 지움). `Suite(…, init_mem=, prep=)` 도 받는다.
  파이썬 쪽 상태(시험이 끼운 처리기)는 그대로 남고, `memory["units"]` 가 있으면 유닛 모델은 새로 만든다(기록·실패 주입도 새것). `suite.restarts` = 횟수. 사용법은 harness 모듈 docstring.
  시험: `t_emu.py` 4절(빌드 오류 기대 6종·이 PC 번호·`init_mem`·`prep`·유닛 모델·기준값 유지 — 60 → 97 판정).
- 작은 기준 맵: `testing/base.scx`(빈 맵, CBTest.scx 사본).
- **여러 번 빌드**(WP0 보고서 7절): eudplib 0.81.0 은 create-payload 콜백을 **첫 빌드에서만** 부른다. 한 프로세스에서 여러 번 빌드하려면 빌드마다 `LoadMap` + `_compat.reset_build_state()`(emu·harness·tools 는 자동). eudext 모듈의 빌드별 상태는 `_compat.register_build_reset(fn)` 에 등록한다(모듈별 `_reset()` 을 따로 두지 않는다). 첫 빌드에서 만든 EUDFunc 본문은 재사용되며, 본문에 구운 **문자열 번호는 다음 빌드에서 틀린다** → 문자열 결과를 보는 시험은 한 빌드에 모은다.
  eudplib `EUDLoopNewUnit` 은 순회마다 571KB 그림자 표를 만들고 목록을 빌드 사이에 비우지 않아, 뒤 빌드에 앞 빌드의 표가 계속 실린다(값은 맞고 페이로드만 는다). `_compat.reset_build_state()` 가 `reset_new_unit_loops()` 로 비운다(WP10 발견). 이 등록은 `_game_loop_start_functions` 에 남으므로 그 뒤 빌드는 모두 `set_game_loop_start()` 를 불러야 한다(emu·harness·tools 는 이미 부른다).
  eudplib 0.81.0 은 `GetMapStringAddr(상수 번호)` 주소를 푸는 수집 뒤 콜백(`string/cpstr.py` `_initialize_queries`)도 **첫 빌드에서만** 부른다 → 한 프로세스의 두 번째 빌드부터 그 주소는 첫 빌드 값으로 남는다(StringBuffer 를 쓰는 시험은 번호·오프셋이 우연히 같으면 통과한다). `_compat.refresh_mapstring_queries()` 가 빌드마다 다시 걸고(지금 문자열 표에 없는 번호는 먼저 지움), display 는 `register_build_reset` 으로 부른다 (display 를 import 한 프로세스에서만). `reset_build_state()` 가 늘 부르게 하면 numfmt 의 DESIGN 0.3 예 시험이 빈 출력을 내서(2026-09-17 실측) 옮기지 않았다(7절 D97 보류). (WP6b 발견)
  eudplib `LoadMap` 은 `MPQAddFile`/`MPQAddWave` 목록을 비운다(listfile 로 다시 채움). euddraft 는 맵을 먼저 읽고 플러그인을 불러오므로 모듈 최상위의 `MPQAddWave` 가 된다(2026-09-17 실측). 같은 프로세스에서 선언 뒤 `LoadMap` 을 다시 하면 넣은 파일이 사라진다 → 빌드 때 `MPQCheckFile` 로 확인해 다시 넣는다(bgm).
  eudplib 시작 단계 표식(`_has_already_started`, `_compat.onstart_phase()`)은 빌드가 끝나도 2 로 남는다(다음 `reset_build_state` 까지) → 빌드 사이 판별에 쓸 수 없다. 이 값이 2 이면 `EUDOnStart` 도 안 된다 — 시작 코드 안에서 `players.contains_user` 처럼 `EUDOnStart` 를 부르는 함수를 부르지 않는다(WP16).

### 5.2 `tools/cost.py` — 비용 보고 (WP0 완료)

- 함수별 `EUDFuncN.size()`, 호출 자리 비용(`GetTriggerCounter()` 차이), 실행 트리거 수(에뮬레이터), SaveMap 결과 크기 증가분을 표로 출력.
- 결과를 `docs/COSTS.md` 에 날짜와 함께 덧붙인다. 3.8 목표와 비교해 넘으면 표시.
- 호출 자리 수는 `CostCase.funcs` 에 넣은 EUDFunc 만 먼저 만든다. 케이스 안에서 처음 불리는 도우미(예: `bullet._shift_fn(16, 8)`)는 그 **본문 트리거가 호출 자리에 섞여** 크게 나온다(WP21: storm 변수 인자 16 → 도우미를 funcs 에 넣으니 6). 케이스가 부르는 도우미 본문은 모두 funcs 에 적는다.
- 공유 본문의 한 번 페이로드는 표에 드러나지 않는다 → 모듈 메모에 따로 적는다(WP21: painter 한 개 약 15~22KB, perma 본문 약 17KB).
- 시험 파일의 `COST_MEMORY`(dict)를 harness `Suite(memory=…)` 로 넘긴다(`--memory-attr`, WP10 요청 — `t_units` 는 `{"units": {}}` 를 두면 capture 항목이 유닛 모델 위에서 잰다). `CostCase(setup=fn, setup_inputs=…, setup_cycles=1)`: 상태를 만드는 준비 케이스를 먼저 돌리고(세지 않음) 이어서 잰다(pool 방문 비용). 둘 다 없으면 예전과 같다.
- 페이로드 증가분은 적층 배치 잡음(±1KB) 때문에 같은 코드를 40벌 넣고 나눈 값을 적는다(참고값).

### 5.3 `tools/edsgen.py`, `tools/build.py` — eds 생성과 빌드 (WP0 틀, WP13 동기화 조각 완료)

- `tools\edsgen.EdsDoc`: `boot()`, `add_plugin()`, `freeze`. 맵별 `build.py` 가 부트 줄, `sync.Bus` 선언의 `[MSQC]`/`[NSQC]` 조각, SCR_DB 채널 줄, 언리미터·기타 플러그인 줄을 모아 eds 를 쓴다.
  - `add_msqc(*lines)` / `add_nsqc(*lines)`: 문자열(원문 줄) 또는 `sync.Bus`(그 버스의 줄). 다른 전송의 버스는 오류.
  - **`add_sync(buses=None, hook=True, local_update=True, sections=None, hook_name="eudext_sync_hook.py")`**: 선언된 버스(기본 전부)의 `[MSQC]`/`[NSQC]` 줄 + 훅 플러그인 섹션(`plugins` 맨 앞 = `[MSQC]`/`[NSQC]` 바로 뒤)을 넣고, 훅 파일 내용을 `extra_files` 에 둔다. `sections={"NSQC": "NSQC.py"}` 로 섹션 이름(= eds 폴더의 플러그인 파일)을 바꾼다.
  - `write(path)`: eds 와 `extra_files`(훅)를 같은 폴더에 쓴다. `render()` 는 `[MSQC]`/`[NSQC]` 안에서 **같은 키가 두 번이면 오류**(euddraft 오류를 미리), 똑같은 줄은 한 번만 쓴다. 키 비교는 `line_key()`(이스케이프를 푼 형태).
  - `write_eds(…, sync=True | {add_sync 인자})`.
  - SCR_DB 채널 줄: `doc.add_msqc(*sync.scrdb_msqc_lines())` (단일 출처는 `sync`).
  - `add_scrdb(db=None, hook=True, core=None, build_id=None, manifest=None, frame=True, preload=True, require_venv=True)` (WP18): scrdb 채널 줄([MSQC], 같은 줄은 한 번), 부트 Preload 에 `scrdb`(VenvSite 없으면 오류), 훅 `eudext_scrdb_hook.py`(sync 훅 바로 뒤, 설정 Core·BuildId·Manifest·Frame). 빌드 순서 예: `examples/scrdb_build.py`.
- `tools\build.py standalone …`: venv 에서 LoadMap/SaveMap.
- `tools\build.py euddraft <eds> --work <폴더>`: eds 폴더의 플러그인(동기화 훅 포함)과 boot.py 사본을 작업 폴더로 옮기고 경로를 절대 경로로 바꿔 실행한다(표준 입력 비움). 출력·`__epspy__`·바이트코드가 저장소에 남지 않는다. `--freeze off`(기본)는 `freeze : 0` 을 넣고, `keep` 은 eds 그대로 둔다. euddraft 0.11.0.1 Linux 판도 이 방식으로 빌드된다(2026-09-16 Debian 13 확인).
- **빌드 순서** (예: `examples/sync_build.py`)
  1. `sync.collect(맵 소스(.eps/.py), map_path=입력 맵)` — 모듈 최상위 선언만 실행(트리거 없음). .eps 는 `_compat.eps_compile` 번역을 실행하므로 `__epspy__` 를 쓰지 않는다. 선언은 **모듈 최상위**(epScript 전역 `const`)에 둔다 — 두 번의 실행(수집·euddraft)에서 같은 순서로 실행돼야 이름(`eudext_<버스>_<종류><번호>`)이 같다.
  2. `EdsDoc(…)`, `boot(…)`, `add_sync(buses, hook=True)`, `add_plugin(맵)`, `write(eds)` — 맵 소스·eds·훅은 작업 폴더에.
  3. `tools/build.py` `prepare_eds` + `run_euddraft`. 빌드 안에서 훅이 `sync.verify()` 로 eds 가 선언과 같은지 확인한다.
  4. (선택) CPLP.
- theSeed `EUDEditorEdsGen.lua` 를 참고했다. DPS 이식판(a7aad90) `build_eud.py write_eds` 는 EUD Editor eds 를 고쳐 쓰는 DPS 전용 변환이라 옮기지 않았고, SCR_DB `[MSQC]` 8줄 형식만 `sync.scrdb_msqc_lines()` 로 가져왔다(출처 주석).

### 5.4 `tools/lua_consts.py` — **WP18 완료**

- lupa(Lua 5.4, `encoding=None` — 문자열은 바이트 그대로)로 Lua 파일을 실행해 전역 상수·함수 결과를 파이썬 값으로 가져온다.
  `Lua`(실행기: `run_file`/`run`/`get`/`set`/`call`/`install`/`set_os` — `os.time`·`os.date` 고정, 표 ↔ dict/list 변환, Lua 오류 →
  `LuaConstsError` UTF-8 메시지), `load(path, stubs=…)`, `read_globals(path, names)`, `find_lua_file(name, 후보, env=)`, `file_info`.
- `CtrigTrace`: CtrigAsm 트리거 함수(CIf/CIfOnce/TriggerX/DoActions*/SetMemory/DeathsX/CD/CV/f_Read/CMov/CAdd/…) 스텁 —
  컴파일 시점 호출을 `Node`/`Term`/`Ref` 트리로 기록(모르는 함수는 오류), `trace_digest`(칸 번호를 다시 매긴 모양 지문).
  보존 여부는 CtrigAsm v5.5 정의대로(DoActions* 기본 보존, TriggerX 는 플래그에 preserved 가 있을 때만, CIfOnce 1회).
- `ScrdbCore`/`scrdb_core()`/`find_scrdb_core()`(4.18). `python eudext/tools/lua_consts.py scrdb [--json]`, `… get <파일> <이름…>`.
- **euddraft 안**: 모듈 import 때 lupa 를 불러오므로 부트 `VenvSite` + `Preload`(scrdb 또는 tools.lua_consts) 가 필요. 부트 뒤 처음
  불러오면 `lupa_available()` 이 거짓이고 `Lua()` 가 안내 오류(`VenvSite`·`Preload : scrdb`).
- **shape.CX 재사용**(다음 배치): `lc.load("CB Paint v2.5.lua")` 후 `lua.call("CSMakePolygon", 4, 64, 0, 5, 0)` 이 좌표 list 를 준다
  (t_lua_consts 확인). 파일 찾기는 `find_lua_file("CB Paint v2.5.lua", [<저장소>/../MapSource/Library, lc.REFERENCE_LIBRARY])`.
- **`lua_c_locale()`**: Lua 를 부르는 구간 동안 `LC_CTYPE` 을 "C" 로 두고 되돌리는 컨텍스트 관리자(재진입·스레드는 구간 수를 세고, 예외에도 되돌림).
  lupa 로 Lua 를 부르는 곳(`Lua`, `shape`, 시험 참조 `ref_strdesign.LuaDefs`)은 모두 이것을 쓴다(3.9 Windows 로캘 함정).

### 5.5 디버그 브리지 도구 — `tools/debugbridge/`, `tools/ingame_auto.py` (2026-09-18)

Windows 전용(외부 프로세스 메모리 **읽기만**, 싱글·LAN 시험). 64비트 SC:R 은 64비트 파이썬(개발 venv)으로 실행한다. 블록은 4.21.

**`tools/debugbridge/dbg_reader.py`** — DPS_Enhance eudplib-port `tools/debugbridge/dbg_reader.py`(021b77b, blob 8237e4e)의 사본.
원본 그대로 들여온 커밋 뒤에 eudext 변경만 따로 커밋했다(차이를 보이게). 원본 파일은 고치지 않았다.
- 원본 기능: 서명 스캔으로 블록 찾기, seqlock 스냅숏, 실시간 화면(`--once`), `--diag`(선형 매핑·변수 메모리 진단), `--peek 주소[:n]`
  (블록과 같은 오프셋으로 미러 주소 직접 읽기 — 블록이 미러 구역에 있을 때만), `--vars`(VarStack 빌드).
- eudext 변경: (1) `--symbols` 에 폴더를 받고 찾은 블록의 **빌드 ID 로 심볼을 고른다**. 기본 후보 `EUDEXT_DBG_SYMBOLS` →
  `EUDEXT_DBG_DIR` → `EUDEXT_WORK/dbg` → **저장소 `work/dbg`** → `<임시>/eudext_work/dbg` → `C:\Temp\DebugBridge_symbols.json`(CtrigAsm 판).
  (2) 심볼의 `eudext` 확장을 화면 끝에 풀어 보인다(`ext_values`·`ext_lines` — 맵 이름·태그·단계(지금 단계·상태·프레임)·판정·결과·표식·
  64/128비트·글 스냅숏. 글·표지 칸은 숫자 줄로 따로 안 보인다). (3) Windows 가 아니어도 import 된다(파서 시험용). (4) `--judge 명세…`
  = `ingame_auto` 로 넘김. (5) `--record 파일`(+`--record-keys`, `--record-watch 이름…`, `--record-seconds`, `--stall-seconds`):
  시간순 기록(탭 구분, 줄마다 바로 씀) — 시작·박동(seq·게임 프레임·초당 프레임·일관 여부)·멈춤·다시 움직임·단계 시작/끝·값 변화·로컬 키 표
  (0x596A18, 미러 — `--diag` 로 직접 읽히는지 먼저 확인) 변화·블록 잃음·끝. CRASH_RISK 세션의 증거, AUTO_ASSIST 의 조작 기록용.
  선택 표(0x6284B8)·채팅 상태(0x68C144)처럼 미러 밖 값은 맵이 `dbg.watch` 한 이름을 `--record-watch` 로 준다.
- 사용: 맵을 혼자 열고 `python eudext\tools\debugbridge\dbg_reader.py --once`(저장소 폴더에서 — 기본 심볼 후보가 `work\dbg`).

**`tools/debugbridge/fake_game.py`** — 같은 곳의 사본(b1724f9) + **재생 모드** `--replay 시나리오.json`: 에뮬레이터가 돌린 맵의
블록 스냅숏(서명 칸은 0 — 이 프로세스에 연속 서명 사본이 생기지 않게)을 프레임마다 다시 쓴다. 미러 맵은 EUD 0x57F0E0~0x59F0E0 를
흉내 내는 버퍼 하나(맵이 바뀌어도 같은 자리 — SC 처럼 덮어쓰고, 게임 프레임 칸도 같이 씀 → `--peek`·`--diag` 가 된다), 페이로드 맵은
맵마다 새 버퍼(끝나도 남음). 프레임마다 seq 시작 → 나머지 칸 → 틈(`gap`) → seq 끝, 서명은 첫 프레임 뒤. `hold`(멈춘 채 두기),
`tail` 0 이면 바로 끝(튕김 흉내). 출력 `READY <pid>`·`MAP i 이름 0x주소`·`END i`·`DONE`. `t_dbg.py` 통합 시험이 쓴다.

**`tools/ingame_auto.py`** — 자동 판정. 명세 형식은 모듈 설명이 정본이다(요약):
- `python eudext\tools\ingame_auto.py --specs <명세 폴더·파일…> [--symbols 폴더] [--out 결과.json] [--log 파일] [--pid N | --name StarCraft.exe]
  [--maps N] [--quit-when-all] [--stall 초] [--progress 초] [--write-checklist 문서.md [--dry-run-checklist] [--date …]]`
- 흐름: 프로세스를 기다려 붙음 → 전체 스캔(판정 중이 아니면 2초, 판정 중이면 15초마다) → 블록 머리는 폴링마다 읽어 빌드가 바뀌면(같은
  미러 자리에 다른 맵) 새 블록으로 → seq 가 움직이는 블록의 빌드 ID 로 심볼 → 심볼 맵 이름으로 명세 → `MapRun` 에 일관 스냅숏을 먹인다 →
  완료 표식(+`settle_cycles`, 판정 칸이 두 번 연속 같을 때)·모든 단계 끝·모든 항목 통과·시간 초과·**멈춤**(seq 가 `stall_s` 동안 정지 —
  단계 설정이 우선)·**튕김**(프로세스 종료 — `GetExitCodeProcess`)·블록 사라짐/바뀜/다시 시작에서 판정 → 결과 JSON 누적·사람이 읽는 줄·
  `<결과>.progress.json`(진행 중에도 계속 — 마지막으로 본 단계·프레임) → "다음 맵을 여세요".
- 명세(JSON, `format: eudext-ingame-spec`, `version: 1`): `map`(= `dbg.setup(map_name)`), `title`, `done`(표식 목록), `timeout_s`·`timeout_cycles`·
  `stall_s`·`settle_cycles`, `checklist`(맵 전체 행), `items`, `suites[name·phase·title·timeout_s·timeout_cycles·stall_s·checklist·items·all_checks]`.
  항목 kind: `check`(total·"sites")·`result`(total)·`watch`(equals·min·max·in·mask, 64/128비트·signed)·`hit`·`mark`·`text`(equals·contains·regex·
  offset·length)·`dwords`·`all_checks`(suite)·`group`(items 모두)·`manual`(사람 확인 — 판정·문서 쓰기 제외)·`peek`(addr·count — 미러 블록만)·
  `hdr`(seq·game_frame·local_player·build·player_info·map_path)·`wall`(fps·max_gap_s·seconds — 단계 항목이면 그 단계 구간), `when`(final|ever),
  `checklist`(`"행"`·`true`(= id)·`{row, section}`·목록), 항목의 `suite`(이름)·`phase`(번호)는 그 단계로 옮긴다. **분류 파일의 설명 필드**
  (`read`·`expect`·`done_marker`·`phase`·`category`·`doc_section`·`required`·`map`·`bundle`·`notes`·`risk`·`extra`·`instrument`)를 그대로 두면
  결과의 `info` 로 옮겨진다(판정에는 안 쓴다 — 시험: 286항목 전부 `manual` 로 담기).
- 단계 판정: 심볼 단계(번호순)와 명세 단계(이름 또는 phase 로 짝) — 시작·끝을 실시간으로 알리고, 끝나면 그 단계 항목(명세 항목 + phase/suite
  로 옮긴 맵 항목 + 기본 `all_checks`(그 단계의 check·result, `all_checks: false` 로 뺌))을 판정. 상태 = 통과·실패(항목 실패·맵이 실패로 적음·
  단계 시간 초과)·**미실행**·**멈춤**·**튕김**. 맵 판정 = 원인이 done 이고 모든 단계 통과·맵 항목 통과(사람 확인 제외).
- 결과 JSON: `{"format": "eudext-ingame-results", "runs": [...]}` — 판정마다 map·title·spec·build_id·build_tag·where·block·pid·started·finished·
  seq·fps·reason·cause(done/timeout/stall/crash/other)·verdict·last_seen{seq,frame,suite,last_suite,time}·checklist·items[id,kind,name,verdict
  (통과/실패/사람 확인),detail,value,checklist,info]·suites[name,no,phase,title,status,begin,end,seconds,reason,verdict_slot,items,checklist].
- `--write-checklist`: 사용자 확인 문서(`MapSource\EUDPLIB_PORT_CHECKLIST.md`)의 행 첫 칸(굵게 표시 무시, 첫 낱말도 됨)이 행 번호와 같고
  `section` 글자가 위 제목에 든 **한 줄**의, 표 머리 마지막 칸에 "결과" 가 있는 표의 **빈 마지막 칸에만** `자동: 통과 (날짜)` /
  `자동: 실패 — 이유 (날짜)` 를 쓴다(같은 행에 여러 결과가 모이면 모두 통과여야 통과, 이유에서 `|` 는 `/`). 무언가 적힌 칸·"답" 표·여러 줄에
  걸리는 행 번호는 건드리지 않고 알린다. 줄 끝·BOM 유지, 읽은 뒤 파일이 바뀌었으면 다시 읽는다. **실제 문서에는 사용자가 원할 때만** —
  이 작업의 시험은 사본으로만 했다.

**설계만 (다음 작업)** — eudext 가 없는 판(UE_RE ①②, 14 scrdb, Memory 1·2 의 eudext 없는 판)의 오프셋 잡기:
SCR_DB 표지 블록(SCR_DB_Core 의 magic = 매니페스트 `signature`, 기본 자리 0x594198, 런처 레이아웃 7)이나 SNQC 디버그 칸(0x592100,
`MapSource\MSF_UE_RE\tools\snqc_probe.py` 의 `DBG_MAGIC`)을 서명처럼 찾아 "실제 주소 − EUD 주소" 를 얻으면, 계측 없이도 `peek`(미러 구역) 판정이 된다. 리더에 `--anchor scrdb|snqc`
찾기를 더하고, `ingame_auto` 는 심볼 대신 "맵 이름 → 기준 블록 종류" 명세(`anchor`)로 판정한다. Memory 1·2 의 eudext 없는 판은 최소 블록
플러그인(순수 eudplib, eudext 없이 `dbg` 배치만 쓰는 작은 .py)을 eds 에 넣는 방법이 있다.

### 5.6 자동 점검 통합 맵 `auto_all` 과 계측판 맵 (2026-09-18, 브랜치 `feat/auto-all`)

> **최종 인게임 결과(2026-09-18 14:51, 빌드 `301F7781`): `00_auto_all` 완전 통과 — 맵 항목 17/17 · 단계 19/19 · 실패 0.**
> 1차에서 걸린 셋의 원인이 모두 확정됐다(자세한 표는 `docs/INGAME_CHECKLIST.md` 맨 앞):
> ① display 멈춤은 그 뒤 판에서 재현되지 않았고 통합 맵은 display·chat·final 까지 끝까지 간다(E6-3·4·4b 는 25·25b 로 옮긴 상태 그대로).
> ② 탄막이 안 만들어진 진짜 원인은 배치 상자가 아니라 **units.dat 에디터 어빌리티 플래그**(0x661518)였다 — 좁히기 10단계로 확정.
> ③ 탄이 안 날아간 원인은 **탄 그림의 iscript**(image 360 = 244 → 395). 도형 밀림은 `[noAirCollision]` + 충돌 상자 1,1,1,1.
> `BulletDat` 기본값을 CtrigAsm v5.5 의 탄막 설치 레시피에 맞췄다(4.15).
>
> **1차 인게임 결과(2026-09-18 05:12, 제작자 혼자)와 그 뒤 고친 것** — 자세한 표는 `docs/INGAME_CHECKLIST.md` 맨 앞.
> 단계 12개(pool·switch·s8·datpatch·i64·i64_ops·i128·numfmt·cmp_cell·mathx·players·spawn)와 G-5(터보)·정리 판정 통과.
> 1. **display 에서 게임이 EUD ERROR(0xFF9BE98B)로 멈췄다.** 자체 점검(E6-8, 13번째 줄·TBL 바이트 포함)은 통과한
>    다음 프레임에 E6-3(13번째 줄 93바이트)에서 멈췄다. 주소 검산 결과 그 호출은 0x641598 +0..95 만 건드려 줄 버퍼
>    218 안이다(줄 밖 dword 창은 틀 길이 ≥ 213 일 때만). 원인을 못 정했으므로 **E6-3·E6-4·E6-4b 를 통합 맵에서 빼고**
>    `25_display_check`(쪽마다 `m25.stage`)와 새 **`25b_display_bisect`(18단계 좁히기, `examples/display_bisect.py`)** 로
>    옮겼다. 통합 맵의 자체 점검은 7 → 5 항목.
> 2. **bullet: 탄이 하나도 안 만들어졌다**(19발 전부). 탄막 유닛 208·210·204 는 문·함정 = **Building 플래그**라
>    `CreateUnit` 이 배치 상자(`buildingDimensions`)로 자리를 검사해 거절한다. `BulletDat` 에 `bounds`(유닛 충돌 크기)·
>    `placement`(배치 상자) 를 더하고 `base_property=None` 경로에서 **Building 을 끄게** 했다(UE_RE EUD Editor 와 같은
>    칸 — S4 2.6). 계측 `D14-0`(dat 값·대조 마린·머리 전후)을 더했다.
> 3. **units: 빈 칸 목록이 번호가 줄어드는 쪽**(머리 1635 → 1634)이다. 칸 걸음 판정을 절대값으로 바꿨다.
>    미리 놓인 **맵 리빌러 64기는 `new_units` 순회에 나오지 않는다**(B10-5 F1 = 2). 에뮬레이터 모델은 66 이라 기대를 2~68 로.
> 4. **plot: 자리 102/211 이 밀렸다.** 몸집이 큰 공중 유닛(뮤탈·레이스·스카웃·커세어)은 점 간격(6~32px)이 충돌 상자보다
>    작아 게임이 만든 유닛을 밀어낸다(사용자 맵의 `NoAirCollisionX` 를 쓰지 않는다). 자리 판정은 스커지 플로터만 하고
>    (`posbad`), 나머지는 밀린 수(`nudged`)와 생성 실패(`madebad`)로 나눠 적는다.

`docs/ingame_auto/classification.md` 5절의 묶음 설계를 그대로 구현한 것이다. 확인 항목 286개를 분류해
**안전하게 자동 판정할 수 있는 eudext 항목 91개**(AUTO 60 · AUTO_ASSIST 3 · VISUAL 28)를 **맵 하나**(`00_auto_all.scx`)에
모으고, 나머지(튕길 위험·소리·런처·키 조작·멀티)는 원래 확인 맵에 브리지만 더한 **계측판**으로 남겼다. 사람이 하는 일은
"맵을 열고 기다린다" 뿐이고, 판정은 `tools/ingame_auto.py`(5.5)가 맵 밖에서 한다.

**구성** — `examples/auto_all.eps`(진행기) + `examples/auto_all/`(단계별 파일 13개 — 공용 `aa_common.py`,
단계 11개, 기대 글 파서 `aa_fmt.py`) + `examples/auto_all_build.py`(빌드기).
기준 맵은 `testing/auto_all_base.scx`(= `base.scx` + P1 파이어뱃 한 기, `tools/make_auto_all_base.py` 로 만든다 —
B15-3 "미리 놓인 유닛의 dat 패치" 에 필요). 단계마다 `dbg.suite_begin(이름, phase=N)` → 점검 → 정리 → `dbg.suite_end` 이고,
값은 `dbg.check/result/mark/watch/snapshot/capture` 로만 내보낸다(4.21). 진행기는 프레임 창으로 단계를 나눈다
(1 units · 2 pool · 3 switch · 4 s8 · 5 datpatch · 6~11 값 모듈 · 12 players · 13 plot · 14 spawn · 15 bullet · 16 display ·
17 chat · 18 final · 19 assist(선택) · 20 visual(선택) — 표는 `auto_all.eps` 머리와 `docs/INGAME_CHECKLIST.md` "확인 순서").
자동 부분은 프레임 4952(약 3분 26초)에 끝나고, 사람 조작(assist)·화면 확인(visual)은 그 뒤 선택이다.

- **점검 코드는 원래 확인 맵을 그대로 부른다**: 값 모듈 단계(6~11)는 `i64_ingame`·`i64_ops_ingame`·`i128_ingame`·
  `numfmt_ingame`·`cmp_ingame`·`cell_ingame`·`mathx_ingame` 의 `selftest`·`report` 를 import 해 결과 수만 판정으로 내보낸다
  (빌드기가 그 맵 파일들을 작업 폴더로 복사한다). 화면 줄도 그대로 나오므로 옆에서 보는 사람이 어디를 보는지 알 수 있다.
- **단계 사이 간섭을 막는 규칙**: 단계마다 만든 유닛·도형·총알·화면을 되돌리고 `aa.clean.<단계>` 판정으로 "되돌렸는지" 를
  함께 내보낸다(정리 뒤 한 프레임 쉬고 확인 — 그 프레임에 SC 가 유닛을 지운다). CP 는 단계 끝마다 제자리인지 본다(`final.cp`).
- **발견 ② 격리**: `datpatch` 는 선언이 남아 다른 단계의 유닛 값을 바꿀 수 있어, 통합 맵에서는 **파이어뱃 maxHp·발키리
  timeCost/supplyUsed·매 프레임 requirementOffset** 만 선언한다(원래 04 맵의 넓은 선언은 계측판 `04_datpatch_check` 에 남겼다).
- **화면(VISUAL) 항목은 판정하지 않는다**: 단계 20 이 6초마다 한 쪽씩 돌고, 명세에는 `manual` 항목으로 두어 결과에
  "사람 확인" 으로 남는다(확인 문서에 자동으로 쓰지 않는다).

**설계에서 벗어난 것(분류 5절 대비)** — 셋뿐이다.
1. **단계 19(assist)를 선택으로**: 분류는 채팅 한 줄(D17-6·E6-2)을 통합 맵 안에 넣으라고만 했다. 사람이 안 쳐도 맵이
   끝나야 하므로 `optional` 단계로 만들고, 안 하면 `건너뜀`(실패 아님)이 되게 `ingame_auto` 에 상태를 하나 더했다.
2. **X_limit 를 뺐다**: B10-1(b)·B10-8·B10-9·D14-3·D14-2(출발=목표)는 유닛 칸을 가득 채워 멈출 수 있어 통합 맵 안에 두면
   나머지 90개를 잃는다 → 별도 맵 `27_X_limit`(`examples/xlimit_ingame.{eps,eds}`). 위험한 동작 자체는 손대지 않았다.
3. **C11-1 을 두 번 본다**: "여러 프레임 뒤에도 값이 남는가" 는 단계 2 안에서 볼 수 없어 단계 18(final)에서 다시 본다
   (같은 확인 문서 행 — 둘 다 통과해야 통과).

**`[eudTurbo]` (2026-09-18 인게임 G-1 뒤)** — 확인 맵의 eds 에 euddraft 번들 플러그인 `[eudTurbo]` 를 넣는다.
인게임 결과에서 트리거 한 사이클이 **게임 프레임 28~30(약 1.2초)** 마다 돌아(맵 실행 속도 기본값) 프레임으로 짠 시간
설계가 30배 늦게 갔다. eudext 안에 같은 것을 구현하는 대신(`SetMemory(0x6509A0, SetTo, 0)` 한 줄이면 되지만) 번들
플러그인을 쓴 이유: ① eudext 는 라이브러리이므로 **맵의 실행 속도를 말없이 바꾸면 안 된다**(3.9 금지 목록의 "전역 상태를
몰래 바꾸기"), ② 확인 맵은 eds 가 있으니 한 줄로 켤 수 있고 어떤 맵이 터보인지 eds 만 보면 안다, ③ euddraft 판이 바뀌어도
같은 이름으로 유지된다. 대신 **터보를 전제로 한 것을 판정 가능하게** 만들었다: 통합 맵 첫 단계가 24사이클 동안 지난
게임 프레임 수를 재서 `aa.turbo`(≤40)·`aa.turbo.frames` 로 내보내고(확인 문서 **G-5**), `ingame_auto` 의 제한은
`timeout_cycles`(프레임 창 + 여유) + `timeout_s`(그것 ÷ 24 + 여유)로 두 겹이며, 시간 초과 설명에 관측한 초당 사이클과
"`[eudTurbo]` 가 빠진 것 같습니다" 를 붙인다(`TURBO_CPS`·`TURBO_CPS_MIN`).

**계측판 맵(통합 맵 밖)** — 원래 맵의 동작은 바꾸지 않고 `[dbg_setup.py]`(eds 에서 `dbg.setup` 을 부르는 플러그인)과
단계·판정만 더했다: `01_S8_SubtractTest`(A-1 마스크 식 비트마스크 — boot 없는 순수 eudplib 맵이라 `s8_check.eds` 로
boot+dbg 를 붙인 판을 따로 빌드한다, 발견 ④), `04_datpatch_check`(화면 줄이 없던 맵 — 0x515B80 32칸 덤프와 `[B15-*]`
줄을 더했다, 발견 ①), `08/22_pool`, `11_bgm`, `14_scrdb`, `17_exit_trap`, `18_sprite`, `20_players`, `21_sync`,
`23_misc_obs`, `25_display`, `27_X_limit`. 명세는 `examples/ingame_specs/*.json`, 항목 **id 는 확인 문서 번호와 같다**.

**게임 없이 한 검증**(`tests/t_auto_all.py`, 105항목) — 세 겹이다: ① 에뮬레이터로 통합 맵을 6,500사이클 끝까지 돌려
단계·판정·표식·정리 값을 본다(모든 단계 통과, 실패 판정 0), ② 그 스냅숏을 `MapRun` 에 먹여 **명세로 판정**한다(통과, 그리고
일부러 망친 단계가 잡히는지), ③ 같은 스냅숏을 `fake_game.py --replay` 로 실제 프로세스 메모리에 재생해
`ingame_auto.py --specs` 가 Win32 읽기 경로로 판정하는지 본다. 계측판 맵도 에뮬레이터로 가능한 만큼 돌린다.

**dbg 공개 API 변화 없음** — 이 작업에서 `eudext/dbg.py` 는 내부 고침 하나뿐이다: 조건 칸에 **변수**가 든 조건
(`a == b` 같은 것)을 `dbg.check` 에 넘기면 `Deaths: invalid amount` 로 죽던 것을 `_raw_ok()` 로 걸러 `EUDIf` 경로로 보낸다.

---

## 6. 작업 계획

### 6.1 작업 묶음

크기: 하 = 반나절 이하, 중 = 1~2일, 상 = 3일 이상(에이전트 기준 추정).
"재사용" 은 복사해 올 코드. 완료 조건은 6.4 공통 + 표의 추가 조건.

| WP | 내용 | 선행 | 우선 | 크기 | 재사용 | 추가 완료 조건 |
|---|---|---|---|---|---|---|
| ENV | **완료(2026-09-17)**. euddraft 0.11.0.1 을 `C:\euddraft0.11.0.1` 에 나란히 설치, 개발 venv `eud081`(파이썬 3.13 + eudplib 0.81.0 + lupa), euddraft 용 lupa cp314 폴더 | — | 필수 | 하 | — | 빈 맵 빌드·lupa 적재 성공, 기존 `C:\euddraft0.9.2.0` 무변경 |
| **WP0** | **완료(2026-09-17, 시험 2,700 통과)** 뼈대: 패키지, `_compat`, `_parts`, `errors`, `boot`, `testing`(emu 이식 + harness), `tools/cost`, `examples` 틀, 단독 빌드·euddraft 빌드 스크립트. **R3 실측(경로 규칙·epScript 번역·번들 표준 모듈)을 0.81 로 다시 재고 2.3·2.4·3.11 을 고친다** | ENV | 필수 | 중 | DPS emu.py, core.py 부품, R3 boot 시제품 | euddraft 0.11 로 빈 예제 맵 빌드 성공, 부트 뒤 `import eudext.x` 성공, 한 프로세스 여러 빌드 확인 |
| S8 | **완료** 조사: **뺄셈 의미 전수 조사**(eudplib 0.76.14·0.81.0, CtrigAsm, SC 마스크 뺄셈) + 에뮬레이터 실험 → 3.5 규칙과 Int64 이름 확정안 | — | **최상** | 중 | — | `docs/spec/S8_subtract.md` |
| S1 | **완료** 명세: G_CB 속성·대기열·f_TempRepeat | — | 상 | 중 | — | `docs/spec/S1_gcb.md` |
| S2 | **완료** 명세: 건물 스택(GunData 등)·TStruct | — | 상 | 하~중 | — | `docs/spec/S2_pool.md` |
| S3 | **완료** 명세: DisplayPrint 원소·대상·Er·Tbl | — | 상 | 하 | G8 | `docs/spec/S3_display.md` |
| S4 | **완료** 명세: 사용자판 CreateBullet 비교 | — | 중 | 하 | — | `docs/spec/S4_bullet.md` |
| S5 | **완료** 명세: SetUnitsDatX·PatchInsert 필드표·scdata 대비, BGM 엔진 | — | 중 | 하 | — | `docs/spec/S5_dat_bgm.md` |
| S6 | **완료** 명세: 채팅 효과 블록·관전자 채팅 블록 | — | 중 | 하 | — | `docs/spec/S6_chat.md` |
| S7 | **완료** 명세: StrDesign 규칙 | — | 중 | 하 | — | `docs/spec/S7_strdesign.md` |
| **WP1** | **완료(2026-09-16, 시험 36,825 통과 — 경계값 차등 전부, epScript 예제 euddraft 빌드)** `cmp` | WP0 | 상 | 하 | core.c_*, tlib.flip/cmp32, 비교 계획(DPS a7aad90) | 경계값 차등 전부 통과 |
| **WP2** | **완료(2026-09-17, 시험 50,916 통과 — 4.3 표의 모든 동작 경계값·무작위 차등, epScript 예제 euddraft 빌드)** `cell` (+ `testing/harness.py`: 빌드 오류 기대 케이스·`restart`, `t_emu.py` 97 판정) | WP1, S8 | 상 | 하 | DPS cells.py(a7aad90) | 4.3 표의 모든 동작 |
| **WP3** | **완료(2026-09-17, 시험 307,019 통과 — 경계값 24개 전 쌍 + 무작위 1,500쌍 × 모든 연산, 뺄셈 두 의미 경계값, 시제품 400건, epScript 예제·euddraft 빌드, 인게임 확인 맵 `examples/i64_ingame`)** `i64` 1차: 생성·대입·덧셈·wrap/포화 뺄셈·부호 반전·비교(부호 없음·있음)·배열·fmt 훅·epScript 통로 | WP1, S8 | 상 | 중 | S8 WK/WVb/SK/SVf, war.py·text.py `_lidec_body`(a7aad90) | 시제품 시험 400건 + epScript 빌드, 뺄셈 두 의미 경계값 시험 |
| **WP4** | **완료(2026-09-17, 시험 t_i64_ops 195,805 + t_i64 307,079 통과 — 경계값 전 쌍 + 무작위 × 곱셈·나눗셈·부호 나눗셈·비트·시프트·to32·abs, 상수 30개, 시프트 0~100·변수 n, 이식판 t_war 기대값, epScript 예제·euddraft 빌드, 인게임 확인 맵 `examples/i64_ops_ingame`)** `i64` 2차: 곱셈(16비트 쪼개기·상수 비트 누적)·나눗셈(이식판 3경로 + 공유 비교 트리거, 상수 `_cdiv`)·부호 나눗셈·비트·시프트·난수·to32·abs·배열 원소 연산 (+ `_parts` 자기 수정 갈림 트리거 틀·결정 나무) | WP3 | 상 | 중 | war.py `_mul64`, `_divmod64`, `_cdiv`(a7aad90), arith.py `_mul_small` | 곱셈 실행 ≤ 1,000 — **최악 358** (나눗셈 ≤ 711 — 최악 391) |
| **WP5** | **완료(2026-09-17, 시험 266,085 통과 — 파이썬 format·참조와 바이트 일치, S3 8.1 기대값·무작위 2만 개, epScript 예제·euddraft 빌드, 인게임 확인 맵 `examples/numfmt_ingame`)** `numfmt` (Dec·Hex·Man·Per·Gauge·`numfmt.dp` 프리셋·직접 쓰기·셀·지정자) | WP3 | 상 | 중 | text.py 고정 폭 루틴(a7aad90), i64 `_lidec_body` | 파이썬 format 과 바이트 일치, `Man`/`Per`/`numfmt.dp.*` 가 S3 8.1 기대값과 일치 |
| **WP6a** | **완료(2026-09-17, 시험 1,779 통과 — S7 기대값 156건, lupa 차등 1,000건(× 함수판 13 = 13,000 비교)·lua_tostring 3,000, 에뮬레이터 문자열 표 333, epScript 예제·인게임 맵 번역·에뮬레이터·euddraft 빌드)** `strdesign` | S7 | 상 | 하 | S7 참조 구현(lupa 로 원본 Lua 실행) | `tests/t_strdesign.py` 가 S7 기대값 156건 + lupa 차등 1,000건 |
| **WP6b** | **완료(2026-09-17, 시험 18,300여 통과 — DisplayText 캡처(실행 순간 버퍼) 비교, S3 8.1 기대값, 대상 18종 × 이 PC 12가지, 13번째 줄 217B 경계, TBL 바이트, DPL 참조 모델(`tests/ref_dp.py`) 무작위 차등, epScript 예제·인게임 맵 에뮬레이션·euddraft 빌드)** `display` (+ `testing/dispmodel.py`) | WP5, WP6a, WP8, S3 | 상 | 중 | G8, text.py(e7efff2), eudplib f_raise_CCMU·GetTBLAddr | DisplayText 캡처 비교 ✔, S3 참조 모델 → `tests/ref_dp.py` 무작위 차등 ✔. 인게임 E6-1·3·4·5·7·8(필수) 대기 |
| **WP7** | **완료(2026-09-17, 시험 t_shape 1,854 + t_plot 9,192 통과 — 고정 시드 스냅숏·원본 TEP(tepc) 대조, 찍은 좌표 = 참조 모델(프레임마다), 번들 파이썬 3.14 에서 lupa 적재 euddraft 빌드 3종, 인게임 확인 맵 `examples/plot_ingame`)** `shape`, `plot` (+`testing/locmodel.py`) | WP0, WP9(점 변환) | 상 | 중 | luart.py bit32(a7aad90), lupa 실험, CAPlotIndexed 구조, GunFadeShape | 고정 시드 스냅숏, 찍힌 좌표 비교, 번들 파이썬에서 lupa 적재 확인 — 모두 통과. 인게임 D7-1(필수) 대기 |
| **WP8** | **완료(2026-09-16, 시험 726 통과)** `players` (+`Observers`·`Everyone`·`contains_user`·`set_table`) | WP0 | 상 | 하 | framework.py HumanCheck | CP 복구 확인, 관전자 슬롯 판정 (이 PC 번호 0~7·128~131 열두 경우 모두) |
| **WP9** | **완료(2026-09-17, `tests/t_mathx.py` 기본 66,368 판정 통과 — 무작위 46,340 + 경계 조합 16,018. `EUDEXT_MATHX_FULL=1` 전체 실행: lengthdir 200,000·atan2 200,000 무작위 차등 포함 843,896 판정 통과(약 12분(718초) — 무작위 793,400 + 경계 조합 17,566), 헤드리스 TEP 표 대조, epScript 예제·인게임 맵 euddraft 빌드)** `mathx` | WP1 | 중(lengthdir 상) | 중 | CtrigAsm Lua 원문(참조 구현), DPS divide.py·div3232(a7aad90) | 20만 개 무작위 차등 |
| **WP10** | **완료(2026-09-16, 시험 3,261 통과)** `units` + scmodel 유닛 모델(CreateUnit·0x628438·실패 주입·CUnit 스텁·Kill/Remove·Order 기록) | WP0 | 상 | 하 | — | CUnit 스텁 시험 |
| **WP11** | **완료(2026-09-17, 시험 1,590 통과 — S2 7.2 T1~T14, 참조 모델 무작위 차등 1,450 걸음, epScript 예제·인게임 맵 euddraft 빌드)** `pool` (+`alloc_n`, `index=True`, EUDBreak) | WP0, S2 | 상 | 중~상 | EP81 `eudqueue.py` 사슬 순회 기법, S2 6.12 의사코드 → `tests/ref_pool.py` | S2 7.2 T1~T14 통과 ✔, S2 6.13 비용 기록 ✔(모두 충족, 유형 분기만 점프 1 초과), 사슬 적재 인게임 1회(C11-1 — 대기) |
| **WP12** | **완료(2026-09-17, 시험 t_spawn 2,514 + t_spawn_xform 191 통과 — S1 9.1 표 A~P·9.2 벡터 전부(에뮬레이터)·무작위 20만 점(`EUDEXT_SPAWN_FULL=1`), 함정 대책·빌드 오류 36종, epScript 예제·인게임 확인 맵 `examples/spawn_ingame` 에뮬레이션·euddraft 빌드. 인게임 E12-1~3(필수) 대기)** `spawn` 1단계 (+`testing/locmodel.py` Order 기록, `scmodel` Force 대상) | WP7, WP9(`Rotator`), WP10, WP11, S1 | 상 | 상 | G_CB 구조(S1) | S1 9.1 표 A~P ✔, 9.2 벡터 전부 ✔, 인게임 S1 9.4 의 1~3(E12-1~3 — 대기) |
| **WP13** | **완료(2026-09-16)** `local`, `sync`, `tools/edsgen`(add_sync·훅) — 시험 t_local 629 + t_sync 781 + t_tools 추가 23 통과, MSQC 수신 코드 e2e(에뮬레이터)·euddraft 빌드(MSQC·NSQC) 통과 | WP0 | 상 | 중 | CA 키 표, NSQC 표, DPS build_eud.py(a7aad90) SCR_DB 줄 | eds 조각 생성, 펄스 주입 시험, 2인 인게임(`INGAME_CHECKLIST` B13 — 대기) |
| **WP14** | **완료(2026-09-17, 시험 5,462 통과 — S4 6.1 방향표·참조 구현 무작위 차등(에뮬레이터 800 + 상수 계산 4만), 6.2 액션 표 11줄 + flingy·무기·유닛 번호 전수, BulletDat = UE_RE `EUDEditorDat.lua` 결과값 대조, 6.3 포인터 처리 전부(실패 주입 포함) + 조합 행렬, epScript 예제·인게임 확인 맵 `examples/bullet_ingame` 에뮬레이션·euddraft 빌드. 인게임 D14-1·2·3 대기)** `bullet` 1단계 | WP9, WP10, S4 | 중 | 중 | Galaxy.py, UE_RE `Install_CBullet`, `EUDEditorDat.lua` | S4 6.2·6.3 기대값, 인게임 S4 7절 1~3 |
| **WP15** | **완료(2026-09-16, 시험 2,346 통과)** `datpatch` | WP0, S5 | 중 | 하~중 | scdata 디스크립터 | 주소표를 scdata 디스크립터와 대조(멤버 전수 + TEP 원본 func.lua 대조), S5 A.8 액션 기대값 — 모두 통과. 인게임 S5 A.9 대기 |
| **WP16** | **완료(2026-09-17, 시험 22,724 통과 — local/synced 재생기 × 이 PC 4종 무작위 차등, B.10 기대값, epScript 예제·인게임 맵 euddraft 빌드(MPQ 소리 확인))** `bgm` | WP8, WP13, S5 | 중 | 중 | euddraft bgmplayer·soundlooper 방식 | S5 B.10 — 모두 통과(실측 파일 대신 같은 길이의 합성 Ogg). 인게임 S5 B.11 = D16-1~9 대기(필수 D16-1·3) |
| **WP17** | **완료(2026-09-17, 시험 t_textfx 1,613 + t_chat 557 통과 — 원본 참조 모델과 프레임마다 버퍼 바이트 비교, epScript 예제·euddraft 빌드, 인게임 확인 맵 `examples/chat_ingame`)** `textfx`, `chat` (Typewriter) + `testing/chatmodel.py` | S6 (WP5 는 쓰지 않음) | 중 | 중 | — (DPS 이식판에 없음) | S6 5.1 셀·스캐너·타자기 시험, 채팅 버퍼 모델 추가 |
| **WP18** | **완료(2026-09-17, 시험 t_scrdb 2,016 + t_lua_consts 55 통과 — FieldHash·id·JSON·매니페스트 Lua 바이트 차등, 수신기·표지 블록·알림음 Lua 트리 차등, MSQC 실제 코드 + 런처 모델 e2e, epScript 예제·euddraft 빌드, 인게임 확인 맵 `examples/scrdb_ingame`)** `scrdb`, `tools/lua_consts`, `testing/syncmodel`(t_sync 모델 옮김, 781 그대로), `edsgen.add_scrdb` | WP13 | 중 | 상 | SCR_DB_Core.lua, DPS G8 1.10·1.11, 런처(e7efff2) | FieldHash 차등(완료), 런처 인게임(D18 대기) |
| **WP19** | **완료(2026-09-17, 시험 t_misc_obs 60 + t_misc 33 통과 — ObserverChat 128·131 두 슬롯 두 번째 입력(B1), 채팅 닫힘/열림·문구 CP·CP 복구·always·edge·빌드 오류; host_player·HostNameIs·hotkey·Countdown·is_widescreen; unsafe_exit_trap enable 없이 막힘. epScript 예제 3종·euddraft 빌드)** `misc` (ObserverChat 먼저) | WP13, WP17 | 하(ObserverChat 은 중) | 하~중 | — | ObserverChat 시험(128·131 두 슬롯 두 번째 입력) ✔, exit_trap 은 인게임 전까지 unsafe ✔ |
| **WP20** | **완료(2026-09-17, 시험 t_i128 기본 234,778 / 전체 872,888 통과 — 경계값 24개 전 쌍 + 무작위(비트 폭·제수 모양 섞음) × 모든 연산, 상수 26개, DPS math128 호출 모양 재현, 이식판 t_war 128비트 기대값, epScript 예제·euddraft 빌드, 인게임 확인 맵 `examples/i128_ingame`)** `i128`: 칸 넷 값 타입 — 덧셈·wrap/포화 뺄셈(올림 깃발 전파, 공유 함수 기본)·사전식 비교·곱셈(64×64 전체 곱 16비트 쪼개기, 128비트 wrap, 상수 비트 누적)·나눗셈(32·64·128비트 제수, 상수 제수는 i64 본문 재사용)·10진 39자리·to64/to32·배열·DPS 이름 별칭 | WP4 | 하 | 중 | math128.lua, 이식판 war.py `_div128`·`_mul6464`·`AddWords`(a7aad90), i64 본문 | 곱셈 64×64 ≤ 1,000 — **최악 585** (128×128 최악 1,326, 나눗셈 최악 약 1,270) |
| **WP21** | **완료(2026-09-17, 시험 t_sprite 2,500 + t_cgrp 978 통과 — CtrigAsm Lua 원문(28장 9개 함수)의 쓰기 줄을 읽어 계산한 바이트·칸 표와 대조, CUnit 84칸·생성 순간 dat·쓰기 칸 집합, 합성 CGRP 파일 파싱·참조 구현 층 차등 400벌 × 10·painter 틱별 참조 타임라인, 변이 시험 13가지 검출, epScript 예제·인게임 맵 번역·에뮬레이션·euddraft 빌드. 실제 .cgrp 파일 검증은 인게임 F21-7 — 사용자 파일 필요)** `cgrp`, 28장 스프라이트 (`bullet` 3단계: CtrigKind·storm·perma_sprite·scan_sprite·unit_sprite·recall_sprite) | WP14 | 하 | 중 | R4a A·B, CtrigAsm 28장 원문 | 합성 파일 시험 통과 ✔, 실제 .cgrp 파일 확인(F21-7 — 대기) |
| **WP-D** | **완료(2026-09-18, Windows, feat/debugbridge — 시험 t_dbg 전부 통과: 파이썬·에뮬레이터·서명·epScript·판정 흐름·Win32 통합)** `dbg`(디버그 브리지 블록·단계) + 리더 사본(`tools/debugbridge`, `--judge`·`--record`) + `tools/ingame_auto.py`(자동 판정·확인 문서 빈 칸 쓰기) + 분류 자료 `docs/ingame_auto/` | WP0 | 상 | 중 | DebugBridge.lua 배치, DPS dbg_reader·fake_game·profile.py | 기존 리더 파서로 블록 해석, 가짜 게임 프로세스 통합(여러 맵·멈춤·튕김), 꺼짐 트리거 0. 인게임 G-1(필수)·G-2 대기 → 통합 맵 `auto_all` 계측 |
| WP-X | DPS `ctrig/war.py` 가 `eudext.i64` 본체를 쓰게 합치기 | WP4, DPS 인게임 통과 | 선택 | 하 | — | t_war 61건 통과 |

### 6.2 병렬 배치

| 배치 | 동시에 하는 일 | 전제 |
|---|---|---|
| A | **완료(2026-09-17)** ENV → WP0, 그리고 동시에 명세·조사 S1~S8 (모두 서로 독립) | — |
| B | **완료(2026-09-16, Ubuntu)** WP1, WP8, WP10, WP13, WP15 | WP0 |
| C | **완료(2026-09-17, Ubuntu)** WP2, WP3, WP9, WP11 | WP1 (WP2·WP3 은 S8, WP11 은 S2) |
| D | **완료(2026-09-17, Ubuntu)** WP4, WP5, WP7, WP14, WP16 (+WP6a, 배치 E 의 WP17·WP18 을 앞당김) | WP3 / WP9 |
| E | **완료(2026-09-17, Ubuntu)** WP6b, WP12, WP17, WP18 | WP5, WP7, WP11, WP13 |
| F | **완료(2026-09-17, Ubuntu)** WP19, WP20, WP21 — WP-X 는 DPS 인게임 통과 뒤(대기) | 필요할 때 |

- 한 배치 안의 WP 는 서로 다른 파일만 고친다. 공용 파일(`_parts`, `testing/scmodel.py`)을 고쳐야 하면 **그 배치에서 한 WP 만** 맡고 나머지는 요청을 남긴다.
- 인게임 확인은 사용자 몫이다. 배치 끝마다 `docs/INGAME_CHECKLIST.md` 에 확인 항목을 모은다.

### 6.3 에이전트 지시문 틀

```
너는 eudext 의 WP<n>(<모듈>) 을 구현한다.
- 설계: MapSource\Py\eudext\DESIGN.md 3절(공통 규약)과 4.<k>절. 규약과 다르게 하려면 먼저 멈추고 이유를 보고한다.
- 재료: <R 문서 절>, <재사용 코드 파일:줄> (복사해 오고 출처를 주석에)
- 환경: C:\Users\whatd\.venvs\eud081\Scripts\python.exe (eudplib 0.81.0). euddraft 빌드는 C:\euddraft0.11.0.1. 기존 C:\euddraft0.9.2.0 과 eud076 venv 는 건드리지 않는다.
- 고칠 수 있는 파일: eudext\<모듈>.py, eudext\tests\t_<모듈>.py, eudext\examples\<모듈>_*.{py,eps}, eudext\docs\COSTS.md(덧붙이기만)
- 다른 모듈에 필요한 변경은 고치지 말고 보고에 적는다.
- 완료 조건: DESIGN.md 6.4 + 6.1 표의 추가 조건.
- 보고(300단어 이내): 만든 API, 시험 결과(건수), 비용 측정값, 설계와 달라진 점, 인게임 확인 항목.
```

### 6.4 완료 조건 (모든 WP 공통)

1. 공개 API 가 4절 초안과 맞거나, 달라진 점을 DESIGN.md 에 반영했다.
2. docstring 이 3.12 형식을 따른다(비용·CP·로컬 표기 포함).
3. `tests/t_<모듈>.py` 가 에뮬레이터에서 통과한다: 파이썬 참조와 무작위 + 경계값 차등(해당되는 모듈).
4. `tools/cost.py` 측정값을 `docs/COSTS.md` 에 기록했고 3.8 목표를 넘으면 이유를 적었다.
5. epScript 예제가 `epsCompile` 번역과 euddraft 빌드를 통과했다(epScript 대상 모듈).
6. `_compat` 밖에서 비공개 API 를 쓰지 않았다. 금지 목록(3.9)을 어기지 않았다.
7. 에뮬레이터로 확인할 수 없는 동작은 `docs/INGAME_CHECKLIST.md` 에 항목으로 남겼다.

---

## 7. 결정이 필요한 것

| # | 질문 | 권장 | 영향 |
|---|---|---|---|
| D1 | 라이브러리 이름 | **결정: `eudext`** (2026-09-17) | — |
| D2 | euddraft 를 최신판으로 올릴지 | **결정: 올린다** (2026-09-17). 0.11.0.1 을 나란히 설치하고 eudext 기준 판으로. 기존 맵용 0.9.10.11 은 유지 | 2.1, WP0 재측정 |
| D3 | 뺄셈 두 의미의 이름 | **사용자 지시: 포화와 wrap 을 확실히 구분**(64비트 구현의 핵심). S8 조사 결과를 3.5 에 적용: 연산자·`sub` = wrap, `_sat` 접미사·`Subtract` 단어 = 포화(eudplib 관례), CtrigAsm 별칭 = 원래 의미. **사용자 확인 대기** | i64, cell, 모든 값 타입. 마스크 필드 포화는 인게임 확인 뒤(`docs/spec/S8_ingame/`) |
| D4 | 0 나눗셈 기본값 | eudplib 과 같게(몫 전부 1, 나머지 = 피제수). `div0="ctrig"` 선택 | 부호 나눗셈 |
| D5 | 각도 기준 | **결정: CtrigAsm 과 같게 고정**(옵션 없음). 결과 값까지 CtrigAsm `f_Lengthdir`/`f_Atan2`/CA_ 와 같게 | mathx, plot, spawn |
| D6 | 도형 좌표 정수화 | **결정: CtrigAsm(TEP) 과 같게 0 방향 자르기로 고정**(옵션 없음) | shape |
| D7 | 입력 전송 | 1단계 MSQC/NSQC + eds 생성, 자체 전송은 3단계 선택 | 빌드 순서가 2단계가 됨 |
| D8 | (해결됨) epScript 에서 키워드 인자 | 파이썬 함수 호출의 키워드 인자는 번역된다. 따로 할 일 없음 | — |
| D9 | SCR_DB 네이티브를 언제 | 2단계(WP18). 새 맵이 저장을 쓸 때 | 런처 호환 시험 |
| D10 | 위험 기능 포함 여부 | `unsafe_exit_trap` 은 실험 기능으로만, `ObserverDrop` 은 넣지 않음 | 맵 신뢰성 |
| D11 | Ccode 정수 코드 | 없앰(객체 핸들만) | 옛 코드 직역 불가(호환 계층 몫) |
| D12 | 128비트 | **결정: WP20 으로 구현**(2026-09-17 — 사용자 "할 수 있는 모든 작업" 요청). DPS math128 이 쓰는 연산만(4.4b) | i128 |
| D13 | G_CB 층 사이 빈 프레임 1개를 재현할지 | 명세는 **재현**(박자 연출 호환). 단순화하려면 알려 달라 | spawn (S1 12-13) (WP12 는 재현으로 구현 — 확정 여부 D74) |
| D14 | G_CB 프리펑션(런타임 무작위 정렬)을 컴파일 시점 변형 K개 + 런타임 선택으로 근사해도 되는지 | 근사(2단계). 체감 확인 필요 | spawn, shape (S1 12-12) |
| D15 | 플레이어 이름 주소 | `PName` = 0x57EEEB(eudplib·IsPName 과 같음), `numfmt.dp.name20` 만 0x6D0FDC(원본 DPL). 인게임 S3 8.3-5 로 두 칸이 같은 이름인지 확인 | display (S3) |
| D16 | TBL 끝 NUL | `eos=True`(eudplib 과 같음), 원본 호환은 `eos=False`. 인게임 S3 8.3-4 | display (S3) |
| D17 | 표시용 맨 변수의 부호 | **부호 있는 10진**(DPL 호환) | display, numfmt (S3) |
| D18 | BGM 재생 방식 | **구현: 두 방식 모두**(`method="switch"` 기본 — 칸마다 트리거 1, `method="patch"` — 12 트리거 고정). D16-1 에서 patch 가 되면 기본을 patch 로 바꿀지 결정 | bgm (재생 함수 크기: 289칸 308 → 12) |
| D19 | `dat.tep` 의 `WhatSndInit/End` 반대 이름, `Reqptr` 무시 | **권장안으로 구현(2026-09-16 WP15), 사용자 확인 대기**: `WhatSndInit` → 0x662BF0(eudplib `whatSoundEnd`), `WhatSndEnd` → 0x65FFB0(`whatSoundStart`) 로 TEP 주소를 그대로 쓰고, 유닛 `Reqptr` 는 TPL 처럼 무시(`reqptr="once"`/`"every_frame"` 로 적용 가능). 둘 다 컴파일 시점 `EPWarning`(키마다 한 번, `dat.tep.warnings` 에 기록, `dat.tep.warn = False` 로 끔) — euddraft 0.11 로그 표시 확인. 새 코드는 scdata 이름(`whatSoundStart`, `requirementOffset`) | datpatch (S5) |
| D20 | `NormalTurboSet` 대체 시계를 bgm 밖 공용으로 둘지 | **구현: `bgm.clock`**(local_dt·half·dt2·update). 다른 모듈이 쓰면 `players` 또는 `clock` 모듈로 옮김 | bgm |
| D21 | `units.new_units` 를 칸당 1바이트 그림자 표로 직접 짤지 | 지금은 eudplib `EUDLoopNewUnit` 감싸기(인게임 검증된 판정, 첫 순회 scx +약 6.9KB). 직접 짜면 약 5KB 줄지만 판정 규칙을 새로 검증해야 한다 → 인게임 B10-5 확인 뒤, 원하면 `new_units(shadow="compact")` 로 | units (WP10) |
| D22 | `CD`·`SetCD` 인자 순서 | **구현: CtrigAsm 원본 순서**(`CD(c, 값=1, 비교=Exactly)`, `SetCD(c, 값=1)`)를 기본으로 하고 설계 초안 순서(`CD(c, AtLeast, 3)`, `SetCD(c, SetTo, v)`)도 받는다(비교·수정자 상수는 형식으로 가려진다). 한쪽만 남기려면 알려 달라 | cell (WP2) |
| D23 | `CellArray[변수 색인]` 읽기의 의미 | **구현: eudplib `EUDArray` 처럼 읽은 값**(epScript `var y = arr[i];` 가 됨). 파이썬 `arr[i] << v` 는 사본에 쓰므로 문서에 경고. `PerPlayer[변수]` 처럼 오류로 바꿀 수도 있다(그러면 epScript 읽기는 `arr.get(i)`) | cell (WP2), 배열형 API 일관성 |
| D24 | `Int64` 포화 뺄셈(변수끼리) 기본을 공유 함수(호출 1 / 실행 19, 호출 자리 약 1.4KB)로 둘지 인라인(3 / 8, 약 2.4KB)으로 둘지 | **공유 함수 기본**(DESIGN 3.3·용량 우선). 매 프레임 여러 번 도는 루프는 `inline=True` | i64 |
| D25 | `Int64` wrap 뺄셈(변수끼리)을 3.3 규칙의 예외로 인라인 기본으로 둘지 | **인라인 기본**(호출 2 / 실행 7, 호출 자리 바이트가 함수 호출과 같음). `inline=False` 선택 | i64 |
| D26 | `Int64Array` 변수 칸 연산(읽기 76, `+=` 87)을 칸 EPD 채우기 방식으로 줄일지 | 쓰임이 확인되면(DPS `WArrX` 같은 원소 연산이 많은 맵) WP4 와 같이. 지금은 읽고-쓰기 | i64 |
| D27 | `div0="eudplib"`(기본)에서 음수 ÷ 0 의 몫 | **구현: 1** (eudplib `f_div_towards_zero` 와 같음 — 부호 없는 몫 0xFFFFFFFF 에 부호 보정). 3.5 의 "몫 전부 1" 을 모든 부호에서 0xFFFFFFFF 로 읽어야 한다면 알려 달라 | mathx sdiv·smod·ratio |
| D28 | 원본 범위 밖 입력(|R| > 32767 — −32768 포함, |dx| > 65535)도 원본의 넘친 값을 재현할지 | **구현: 재현**(D5 "결과 값까지 같게"). 그 대가로 느린 길이 eudplib `f_mul`(38KB, 변수 곱을 쓰는 맵이면 이미 있음)·`div3232`(52KB)를 끌어온다. "범위 밖은 값 보장 없음" 으로 바꾸면 한 번 페이로드 약 40~50KB 절약 | mathx lengthdir·Rotator·atan2 |
| D29 | 변수 각 엔진 공유 | **구현: 주기마다 하나를 lengthdir·Rotator·rotate3d 가 공유**(용량 우선), `own=True` 로 전용 본문. 번갈아 쓰는 곳에서 실행 +125/회 | mathx, plot·spawn(WP7·WP12) |
| D30 | 변수 제수 부호 나눗셈의 부호 없는 나눗셈 본문 | **구현: DPS 이식판 `div3232`**(같은 제수면 표 재사용 — 실행 271 → 27). 맵이 eudplib `a / b`(`f_div`)도 쓰면 비슷한 본문이 둘(+52KB). eudplib `f_div` 로 바꾸면 그 본문을 같이 쓴다 | mathx sdiv·smod·ratio·atan2(범위 밖) |
| D31 | `pool.each()` 안 `EUDBreak()` 를 허용할지 (S2 는 1단계 컴파일 오류) | **허용(구현함)**: 이번 방문 꼬리(되쓰기)까지 하고, 남은 레코드는 본문 없이 정리만 한다. 막으려면 한 줄로 되돌릴 수 있다 | pool (WP11) |
| D32 | 풀마다 공유 코드(약 2b+30 트리거, 페이로드 20~26KB)를 여러 풀이 나눠 쓰게 할지 | 지금은 풀마다 1벌(상수가 풀마다 달라 단순). 한 맵에 풀이 5개를 넘거나 용량이 빠듯하면 WP 후속으로 "E·b 가 같은 풀끼리 공유" 검토 | pool, spawn(WP12 작업 풀) |
| D33 | 넘침 문구의 "G_Send" 를 "alloc" 으로 바꾼 것 | **바꿈(구현함)** — 새 API 에 G_Send 가 없다. 원본 그대로가 필요하면 `on_full=함수` 로 직접 띄운다 | pool 문구 |
| D34 | `sd.design()` 은 숫자를 거부(S7 6절)하고, CtrigAsm 이름 별칭 `sd.StrDesign`/`StrDesignX`/`StrDesignX2` 만 숫자를 Lua 표기(`lua_tostring`)로 받게 했다. 별칭도 거부할지 | **구현: 별칭은 받는다**(원래 의미 — Lua 와 같은 표기라 조용한 차이가 없다). 새 코드는 `design` + f-문자열 | strdesign (WP6a) |
| D35 | `bullet_at` 에 `y_offset` 을 적용할지 | **구현: 적용 안 함**(로케이션에 바로 생성 — M2·Galaxy.py CreateBulletLoc 와 같음). 적용하려면 로케이션 중심을 읽어(실행 약 +150) `bullet` 으로 보낸다 | bullet_at |
| D36 | `BulletDat` 기본값 | **구현: UE_RE 208/127/106 그대로**(idle_order 없음, 피해 60000, 스플래시 96, 최고속도 −8001). S4 5.4 초안의 idle_order=2(M2) 가 필요하면 알려 달라. 필드 목록 확정은 인게임 D14-9·D14-13 뒤 | BulletDat |
| D37 | 인게임 결과에 따라 본문을 줄일지: ① D14-5 에서 위치 = (x, y + 보정) 이면 위치 읽기(실행 34)를 빼고 좌표를 바로 쓰기 ② D14-6 에서 효과가 없는 ue_re 칸(+0xA3·+0xDC·+0xE4)을 빼기 | **결과가 나오기 전에는 원본 그대로**(ue_re = UE_RE 판). 결과를 보고 recipe 를 고친다 | bullet 본문(실행 −34, 액션 −3) |
| D38 | `setup` 을 여러 번 부르는 것 | **구현: 허용**(그 뒤 만드는 호출부터 새 로케이션, 본문이 로케이션마다 따로). S4 는 "한 번만" | bullet |
| D39 | `PlayWAV` 반복 기본값 | 2(기존 관례). D16-2 에서 1번으로 충분하면 1 로 | bgm 재생 함수 액션 수 |
| D40 | synced `elapsed` 기본 모양 | `bus.value(clock.local_dt(), latch=True)`(받지 못한 사이클에 마지막 값 — 턴이 여러 프레임이면 평균이 맞음). UERE 처럼 받은 사이클만 빼려면 `latch=False`. D16-7 결과로 확정 | bgm synced 곡 길이 정확도 |
| D41 | 끈 플레이어(mute·관전자 끄기)의 곡 상태 | **흐름**(소리만 막음 — PC·플레이어마다 조각 번호가 같게). LIB 처럼 멈추려면 알려 달라 | bgm |
| D42 | `max_elapsed`(기본 2500)를 local 모드에도 적용 | 적용(일시정지 뒤 큰 dt 로 조각을 건너뛰지 않게). D16-3 일시정지 결과로 확정 | bgm local |
| D43 | `ShapeSet(storage="varray")` 를 점당 144B(원소 둘)로 둔다(초안 72B). 1,700점 245KB·scx +22KB 대신 점 읽기 실행 40 → 9 | **그대로**(큰 도형·많은 도형은 기본 "db", 작은 도형을 자주 찍는 곳만 varray) | shape, spawn |
| D44 | 도형 번호(sid)를 0부터 센다(CAPlot 의 CA[1] 은 1부터) | **0부터**(파이썬·epScript 목록과 같게) | shape, plot, spawn |
| D45 | 좌표 NaN·무한대를 0 으로 싣는다(루프형 CAPlot 의 bit32 규칙·CS_FixShape 와 같음). 정적 CSPlot 은 NaN 을 0x80000000 으로 넣는다(tepc 실측) | **0**(찍히는 자리가 원점 — 원본 CAPlot·G_CB 와 같음) | shape |
| D46 | `center="loc"`(로케이션 중심)를 start() 순간에 한 번만 읽는다. CAPI 의 nil 중심은 점마다 다시 읽고 로케이션을 되돌린다(찍는 중 로케이션을 옮기면 따라감) | **한 번**(점마다 약 150 실행을 아낀다). 따라가야 하면 `pl.set_center(...)` 를 프레임마다 | plot |
| D47 | 콜백·본문이 없는 `tick()` 에서 점 읽기 비트 트리거가 로케이션 칸에 바로 더하는 전용 읽기를 둘지(점당 53 → 약 44, Plotter 마다 트리거 약 32 더) | 지금은 두지 않음. G_CB(spawn)처럼 점이 아주 많은 곳에서 체감되면 | plot, spawn |
| D48 | `CX()` 의 기본 CB Paint 폴더를 저장소 `reference/MapSource/Library`(2026-09-16 사본)로 둔다. MapSource 최신본을 쓰려면 `EUDEXT_CBPAINT_DIR` 또는 `lib_dir=` | **그대로**(빌드 재현성). 새 CB Paint 판이 나오면 사본을 갱신 | shape |
| D49 | 타자기 드러내기: 원본처럼 매 프레임 셀 1..52 를 다시 쓸지(보관소를 72B 원소 배열 `_compat.custom_varray` 로 두면 셀당 실행 약 3 — 인스턴스당 페이로드 약 +41KB) / 새 셀만 쓸지(구현, Db 2.3KB, 셀당 약 40) | **새 셀만**(구현). 다른 코드가 드러내는 줄을 고치는 맵이면 알려 달라 | chat (WP17) |
| D50 | `Typewriter(erase=)` 기본값을 S6 의 2 대신 "표식만 스캔한 셀 수"(기본 표식·ctrig = 2, eudplib = 4)로 둘지 | **구현대로**(기본 설정은 원본과 같고 `rule="eudplib"` 에서 `!H` 가 보이는 함정을 막음) | chat (WP17) |
| D51 | 한 맵에 Typewriter 여럿 — 빌드 때 막을지 / 문서만(구현, `enable` 로 배타) | **문서만**(인게임 확인 맵이 두 개를 번갈아 쓴다) | chat, WP19 |
| D52 | `rule="eudplib"` 스캐너의 C 바이트 — 0x0D(구현: 원문 색 코드가 살아 있음) / eudplib `color_v`(기본 2: 셀마다 기본색으로 되돌림) | **0x0D** | textfx |
| D53 | 4바이트 UTF-8(이모지) — `'?'` 셀(구현, S6 권장) / 건너뛰기 | **'?'** | textfx |
| D54 | 표지 블록 기본 자리를 DPS 원본 0x594198 로 둘지, 필수 인자로 할지 | **기본값 유지**(구현). SCR_DB 칸끼리 겹침·미러 구역만 검사한다. 맵이 그 칸을 다른 데 쓰면 맵 몫 | scrdb |
| D55 | 1회 블록의 0 초기화를 Lua 계획 그대로(SetMemory 168개, 페이로드 ≈ 11KB) 둘지 루프(≈ 3KB)로 줄일지 | **그대로**(구현 — Lua 계획을 그대로 내고 순서 시험이 쉽다). 용량이 문제면 알려 달라 | scrdb anchor |
| D56 | 수신기 본문을 CP 기준 상수 액션으로 더 줄일지(≈ 3KB) | 필요할 때 | scrdb receiver |
| D57 | Lua 수신기 모양 지문이 다를 때 경고(구현) 대신 빌드 오류로 할지 | **경고**(Lua 코어를 고친 뒤 t_scrdb 로 확인하는 흐름) | scrdb |
| D58 | MapSource `SCR_DB_Core.lua` 의 `SCRDB_Setup` 에 "KeyMode index 인데 index 없는 항목" 검사를 넣을지 (지금은 순번으로 넘어가 런처 `plan()` 이 KeyError) | 넣기 권장(MapSource 쪽 수정 — 이 WP 는 읽기만) | MapSource Lua, 런처 |
| D59 | 부호 있는 64비트 나눗셈의 0 나눗셈 기본값 | **구현: eudplib `f_div_towards_zero` 와 같게**(몫 = 피제수 < 0 이면 1, 아니면 −1 / 나머지 = 피제수). CtrigAsm 값(±(2^63 − 1) 쪽)은 `div0="ctrig"`, CtrigAsm 별칭 `LiDiv`/`LiMod` 는 이쪽. 기본을 CtrigAsm 쪽으로 바꾸려면 알려 달라 | i64 (WP4) |
| D60 | `Int64` 의 `<<=`·`>>=`·`>>` 를 시프트로 열지 (3.2-5 는 "시프트는 메서드로만") | **구현: 연다**(eudplib `EUDVariable` 과 같음, epScript `x.v <<= n;`). `<<` 는 대입 그대로, epScript 식 `x << 3` 은 빌드 오류 그대로. 헷갈리면 `<<=` 도 안내 오류로 되돌릴 수 있다 | i64 (WP4), 다른 값 타입 |
| D61 | CtrigAsm `f_LlShift` 별칭을 둘지 | **두지 않음**: 원본은 시프트 양의 하위 6비트가 0 이면 시프트하지 않는 것으로 읽힌다(v5.5.lua:72666, n = 64 → 그대로, 65 → 0). eudext `shl` 은 n ≥ 64 → 0. 원본 의미가 필요하면 그 규칙의 별칭을 더할 수 있다(DPS 등 사용 0회) | i64 (WP4) |
| D62 | `sign_space` 의 뜻 | **구현: 부호 글자 뒤 공백**(CtrigAsm Sign=2, `"- 5"`). 파이썬 `{: d}`(양수 자리 공백)는 `sign=" -"` 로 따로 둠. 파이썬 뜻으로 바꾸려면 알려 달라 | numfmt |
| D63 | `fill="0"` 의 정렬 | **구현: 파이썬 `0` 플래그처럼 부호 뒤 0 채움**(`-0005`, 구분자 포함 `0,001,234`). 부호 앞 0(`000-5`)은 `align=">"` | numfmt, display |
| D64 | `Man(fixed=False)` 의 배치 | **구현: 18B 배치에서 앞 0x0D 만 건너뜀**(덩이 안 앞 0·숨긴 덩이·단위 자리 0x0D 는 남음 — 보이는 글은 같음). 0x0D 없는 촘촘한 배치가 필요하면 2차 | numfmt, display(TBL 길이) |
| D65 | `f_cpchar_print`/TextFX 에 서식 객체를 넘기면 | **구현: 빌드 오류로 안내**(`obj.fmt()` 를 넘기라고). eudplib 을 몽키패치해 자동으로 `fmt()` 를 부르게 할 수도 있다 | numfmt, textfx(WP17) |
| D66 | 서식 객체 호출 자리 비용(페이로드 약 1.2~1.5KB — 버퍼 + 포인터 변수 + 호출) | 지금 그대로(i64.fmt 와 같은 모양). 인쇄가 수백 곳인 맵에서 줄여야 하면 포인터를 꼬리 안에서 더해 트리거 1개를 줄이는 안(실행 +1~2)이 있다 | numfmt, display |
| D67 | `numfmt.dp.name20(p)` 상수 p ≥ 7 | **구현: 빌드 오류**(DPL 이름 캐시가 0~6 뿐이라 원본도 아무것도 쓰지 않음). 변수 p ≥ 7 은 원본처럼 버퍼를 그대로 둔다 | numfmt(dp), display |
| D68 | CGRP 흑·적 명암 단계를 몇 비트로 읽을지. 가이드북 형식 표는 0~7(3비트), 예제 29-6·29-10 은 마스크 `3*0x100`·`3*0x800`(2비트, 0~3) 으로만 반복했다 | **구현: 3비트(형식 표)**. 실제 CS_Photo 파일(F21-7)에서 4 이상이 나오는지 보고 확정. 예제처럼 자르려면 `layers(…)` 에 옵션을 더한다 | cgrp.layers |
| D69 | `storm`/`perma_sprite` 의 전역 dat 쓰기(투사 방식·속도·수명·이미지 iscript)를 빈 유닛 칸이 없을 때도 할지. 원문은 `CIf(0x628438 ≥ 1)` 안이라 안 쓴다 | **구현: 항상 쓴다**(호출 자리 1 트리거 적음. 다음 성공 호출이 같은 값을 다시 쓰므로 보이는 차이 없음) | bullet 3단계 |
| D70 | 이미지 256(벌처) iscript ← 86 을 원문처럼 부를 때마다 쓸지 | **구현: `CtrigKind.install()`/`init_actions()` 에서 한 번**(값이 상수). `carrier_iscript=None` 이면 안 씀 | CtrigKind |
| D71 | 원문 `CreateBullet`·`CreateBulletTarget`(부를 때마다 투사 방식 9·−속도·수명을 쓰는 판)을 3단계 함수로 옮길지 | **요청 시**(사용 0회. 1단계 `bullet`/`bullet_to` + `k.speed_actions`/`time_actions` 로 대신) | bullet |
| D72 | 가변 그림(예제 29-9: CGRP 여러 장을 스캔·유닛 스프라이트로 매 프레임)·흰색 점 갱신·원본 파일 런타임 읽기를 API 로 둘지 | **요청 시**(사용 0회. `points()`·`white_points()` + `scan_sprite`/`unit_sprite(track=False)` 로 짤 수 있다) | cgrp |
| D73 | `unit_sprite` 의 +0xDC(0x100)·+0xE4 쓰기(드래그 방지)를 끌 수 있게(`nodrag=False`) 할지 — 원문은 칸 연산 판에서 늘 쓴다 | **F21-3 결과 뒤**(클로킹 소리·선택 여부를 보고) | unit_sprite |
| D74 | D13(층 사이 빈 프레임 1개 재현)을 확정해도 되는지 | **재현으로 구현**(권장안). 인게임 E12-3 에서 층 간격이 체감되는지 보고 결정 | spawn |
| D75 | 대기열 저장: pool 레코드(층당 약 1.7KB, capacity 128 = chk +309KB·scx +30KB)로 둘지, S1 목표(dword 레코드 128칸 12KB)처럼 줄일지 | **pool 유지** — 적재가 필드당 실행 1 이라 빠르고, 원본(대기열 307KB + 빈 도형 1.78MB + 도형당 트리거)보다 이미 작다. 필요하면 `capacity` 를 줄인다(8 = chk +92KB). dword 레코드로 바꾸면 사이클마다 필드 읽기가 약 36 × 20 실행 늘어난다 | spawn 페이로드 |
| D76 | 크기 변환 점당 +133(목표 +40): 지금(변수 곱 + 부호 나눗셈, mathx.ratio)으로 둘지 | **유지**(값이 CtrigAsm 과 같고 크기를 쓰는 작업만 느려짐). 요청이 있으면 사이클마다 크기 곱을 준비하는 비트 곱(추정 +80)을 WP 후속으로 | spawn 실행량 |
| D77 | 생성 속성 기본값 `props="energy"`(원본처럼 에너지 100%로 생성) 유지 | **유지**(원본 G_CB 가 모든 소환을 energy 100 으로 만들었다 — 마법 유닛 에너지가 원본과 같다). 끄려면 `props=None` | spawn |
| D78 | rtype 0 = "없음"(원본 0 = 기본 어택) | **"없음"**(맵마다 번호가 달라 고정하지 않음). 원본처럼 쓰려면 `sp.rtype("Home", sp.builtin.attack_default, id=…)` + `sp.default_rtype = "Home"` | spawn 옮기기 |
| D79 | `Int128` 변수끼리 덧셈·wrap 뺄셈 기본을 공유 함수(호출 1 / 실행 35·39, 호출 자리 2.8KB)로 둘지 펼침(9 / 16·20, 4.5·5.6KB)으로 둘지 (i64 는 펼침 기본 — 바이트가 같아서) | **구현: 공유 함수 기본**(3.3, `inline=None` 은 32비트 이하 값만 펼침). 타격마다 도는 루프처럼 실행 수가 중요하면 `inline=True` | i128 |
| D80 | 나머지(`%`·`imod`·`divmod`·`LDiv128`)의 타입 — Int128(구현) / 제수 폭(64비트 이하면 Int64) | **Int128**: 0 나눗셈 규칙(나머지 = 피제수, 128비트)을 지키고 연산자 결과 타입이 고르다. 64비트가 필요하면 `r.lo`(복사 없음). 설계 초안 "나머지 64" 는 크기 뜻으로 읽었다 | i128 |
| D81 | `LSub128` 을 128비트 전체 기준 포화로 둔 것(DPS `f_LSub128` 은 상위가 작고 하위가 클 때 0 이 아닌 값 — 예: a = 10, b = 2^64 + 5 → 5) | **전체 기준**(3.5: 반쪽별 포화 금지). DPS 코드가 그 값에 기대는 곳(GlobalBoss.lua:614·fragment.lua:54·GameDisplay.lua:103·function.lua:688)은 원래 a ≥ b 를 뜻한 것으로 보인다 — 원본 값이 필요하면 알려 달라 | i128, DPS 옮기기 |
| D82 | `LDiv128`·`divmod` 의 0 나눗셈 = eudext 규칙(몫 2^128 − 1, 나머지 = 피제수) — DPS `Call_div128` 은 나머지 반쪽이 뒤바뀜(R1 ← A2, R2 ← A1) | **eudext 규칙**(7절 D4). 이식판 `Div128(…, ZeroRule=1)` 처럼 원본 값을 재현할 곳이 있으면 알려 달라 | i128, DPS 옮기기 |
| D83 | `f_LMul128X`(128 × 128) 별칭을 둘지 — 원본은 "두 상위가 모두 0 이 아니면 최댓값, 한쪽만이면 wrap" | **두지 않음**(`a * b` 는 wrap, DPS 호출 8곳은 모두 한쪽 상위가 "0"). 포화 곱이 필요하면 `mul_sat` 을 따로 만든다 | i128 |
| D84 | 128비트 상수 제수 < 2^32 를 i64 상수 본문 세 번(구현: 실행 40~231, 상수마다 한 번 페이로드 약 45KB 중 36KB 는 i64 와 공유) / 칸 넷 한 번 본문(27~181, 약 84KB) 중 무엇으로 | **i64 본문 재사용**(DPS 는 상수 제수 8종 이상 — 약 300KB 차이). 실행이 더 중요하면 알려 달라 | i128 |
| D85 | 128비트 10진 본문(한 번 페이로드 약 165KB + i64 10진 48KB)을 더 줄일지 — 대안: 128 ÷ 10^9 네 번(i64 상수 본문 재사용, 실행 약 800) | **지금 판**(실행 최악 536). numfmt 128비트 서식이 같은 본문(`lidec_to`)을 쓰면 한 벌로 끝난다 | i128, numfmt |
| D86 | 192·256비트(`f_LAdd192` 3, `Compare_192/256`·`f_LSub256`·`SetNumX256`/`TBLX256` 각 1 — DPS 10회)를 만들지 | **만들지 않음**(D12 범위 밖). DPS 를 새 코드로 옮길 때 필요하면 `Int128` 방식으로 칸 여섯·여덟을 더한다 | — |
| D87 | display 버퍼를 DPL 식 **틀**(상수 굽기 + 0x0D 자리)로 둘지, S3 초안의 StringBuffer + `f_cpstr_print`(글이 실제 길이만큼)로 둘지 | **틀**(구현): 실행이 크게 적다(상수 0, 맨 변수 70 — 복사 방식은 글자당 35). 대가는 버퍼가 길어지는 것(E6-9 결과를 보고 긴 줄만 복사 방식으로 바꾸는 선택지를 둘 수 있다) | display 전체 |
| D88 | `Byte(v)`·`Bytes` 값 0 을 0x0D 로 바꿀지(원본은 NUL 이라 그 뒤 글이 사라짐) | **바꿈**(구현, 조건 트리거 1) | display |
| D89 | `PName(변수)` 가 8 이상일 때 빈 글(구현) / 원본처럼 이전 내용 | **빈 글**(S3 7.3). `numfmt.dp.name20` 은 원본처럼 이전 내용 | display |
| D90 | `show_line13` 의 로컬 쓰기를 관전자 PC 에서 막을지 | **막음**(구현 — 관전자에게는 CCMU 가 뜨지 않는다) | display |
| D91 | `set_tbl` 의 상수 글자 복사(바이트당 약 35)를 줄일지 — 실행 중 주소 정렬(4가지)별 단어 쓰기를 미리 구우면 실행은 몇 트리거지만 호출 자리 페이로드가 글 길이 × 약 4배 늘어난다 | **그대로**(구현). 상수만 쓰는 TBL 은 한 번만 부르도록 문서에 적었다. DPS 처럼 매 5프레임 수십 곳을 갱신하는 맵이면 알려 달라 | display set_tbl |
| D92 | `PName` 기본을 실시간(0x57EEEB 복사 — 이름 바이트당 35, SetPName 반영)으로 둘지 캐시(`cache=True` — 실행 8~38, 시작 때 한 번 약 3,000·원소 사슬 4KB)로 둘지 | **실시간**(eudplib PName 과 같음). UI 에서 매 프레임 찍는 이름은 `cache=True` 권장(문서) | display |
| D93 | display 가 numfmt 비공개 계약(`_Fmt._emit_buf(nwords, call)` 훅, `_NumFmt._plan()/_spec/_kind`, `numfmt._plan`, `_name_tail`, `_args`)에 기대는 것 | **numfmt 에 공개 API 를 두기를 요청**: 예) `obj.emit_words(dests)`(이미지 단어를 dests 에 쓰고 시작 위치를 돌려줌), `obj.layout()`(단어 수·시작 위치·고정 여부), `obj.widened()`(0x0D 채움 최대 폭 판). 생기면 display 를 그쪽으로 바꾼다. 지금은 시험(원소 59종·S3 8.1)이 계약 변화를 잡는다 | numfmt(WP5 소유), display |
| D94 | `show` 상수만 + 상수 대상의 run_as 경로에서 같은 번호가 목록에 두 번이면 두 번 뜨는 것(원본 RotatePlayer 와 같음) | **그대로**(호출 1 / 실행 2 로 가장 싸다). 변수가 든 목록·값은 판정 1회라 한 번. `players.Targets` 안에 변수를 섞으면 두 번 볼 수 있다(안을 볼 수 없어서 — players 에 공개 조회가 생기면 가를 수 있다) | display |
| D95 | `set_tbl` 기본 tail = U+2009(S3) | **U+2009**(구현). DESIGN 4.7 초안 표기(공백)를 고친다 | display, DESIGN 표기 |
| D96 | 한 줄 틀이 217B 를 넘을 때 빌드 경고(구현) / 오류 / 무시 | **경고**. E6-9 에서 SC:R 이 긴 줄을 자르면 오류로, 줄바꿈해 보여 주면 경고를 없앤다 | display show |
| D98 | dbg 블록 기본 자리 | **void 맨 위(0x5967F0 아래, 기본 0x596280 — DebugBridge.lua 와 같은 자리)**(구현). 하이브리드 맵은 `addr=` 로 옮긴다. 페이로드 판은 선택(`--peek` 불가) | dbg, 리더 |
| D99 | dbg 심볼 JSON 기본 폴더 | **`EUDEXT_DBG_DIR`(부트 `DbgDir`) > `EUDEXT_WORK/dbg` > `<임시>/eudext_work/dbg`**(구현, C:\Temp 안 씀). 리더는 저장소 `work/dbg` 도 찾는다. 예제 eds 는 `DbgDir : ../../work/dbg` | dbg, 리더, 예제 |
| D100 | 항목의 단계(suite) 정하기 | **코드 순서로 열린 단계**(구현) + `suite=` 인자 + 이름 앞머리(`c3.`). 실행 순서로 정하려면 매 사건마다 단계 번호를 칸에 적어야 해 비싸다 | dbg, ingame_auto |
| D101 | 자동 판정의 멈춤 기준 | **seq 가 15초 멈추면 멈춤**(도구 `--stall`, 명세·단계 `stall_s` 가 우선). 싱글 일시 정지와 구분 못 함 | ingame_auto |
| D102 | 확인 문서 자동 기록 | **선택 옵션**(`--write-checklist`, 빈 칸에만 `자동: 통과 (날짜)` / `자동: 실패 — 이유 (날짜)`). 사용자가 원할 때만 실제 문서에 — 이번 작업은 사본으로만 시험 | ingame_auto, MapSource 확인 문서 |
| D97 | `_compat.refresh_mapstring_queries()` 를 `reset_build_state()` 가 늘 부르게 할지(지금은 display 를 import 한 프로세스에서만) | **늘 부르게 옮기기 권장** — 여러 번 빌드하는 시험·도구의 StringBuffer·GetMapStringAddr 주소가 첫 빌드 값으로 남는 문제(`_compat` 는 공용 파일이라 WP6b 는 덧붙이기만 했다) | _compat, 모든 시험 — **보류(2026-09-17)**: 늘 부르게 해 보니 `t_numfmt` 의 DESIGN 0.3 예 실행이 빈 출력(`b''`)이 됐다. 원인 조사 전까지 display 가 부르는 방식 유지 |

---

## 8. 참고 — 조사 문서 요약 위치

| 알고 싶은 것 | 문서·절 |
|---|---|
| 맵별 호출 수·실제 인자 모양 | `docs/research/R1_usage.md` 1·2절 |
| 이식 계층에서 떼어 올 코드(파일:줄) | `docs/research/R2_existing.md` 7.1 |
| 에뮬레이터가 흉내 내는 범위 | R2 4.1 |
| SCR_DB 네이티브 제약 | R2 3.1 |
| 값 타입·조건·함수·CP 규약 근거 | `docs/research/R3_eudplib_conv.md` 1절 |
| epScript 번역 규칙(실험) | R3 2절, `docs/proto/eps_probe_out.txt` |
| euddraft 경로 규칙·부트 | R3 3절 |
| 최신 eudplib 대비 | R3 4절 |
| 총알 원리·dat 필드 | `docs/research/R4a_bullet_text.md` A |
| 숫자 서식 확장 지점 | R4a C |
| 글자 셀 배치 차이 | R4a D.1 |
| 채팅 버퍼 사실 | R4a E.1 |
| 입력 주소·MSQC 동작 | `docs/research/R4b_input_shape_misc.md` A |
| CB Paint 도형 형식·lupa 적재 | R4b B1~B4 |
| CAPlotIndexed 구조 | R4b B5 |
| CB Paint 도형·lupa·TEP 대조 / 찍기 루프 의미 | `tests/t_shape.py`(tep_compare) / `plot.py` 모듈 설명 |
| lengthdir/atan2 원본 동작 | R4b C, 참조 구현 `tests/ref_mathx.py`, 표 `mathx_tables` |
| ExitDrop 원리 | R4b D4 |
| G_CB 속성·대기열·spawn API | `docs/spec/S1_gcb.md` |
| 건물 스택·TStruct·pool API | `docs/spec/S2_pool.md` |
| DisplayPrint 원소·대상·고정 길이·기대값 | `docs/spec/S3_display.md` |
| 사용자판 총알·bullet API | `docs/spec/S4_bullet.md`, 참조 구현 `tests/ref_bullet.py` |
| dat 패치 표·scdata 대비·BGM 엔진 | `docs/spec/S5_dat_bgm.md` |
| 채팅 효과 블록·관전자 채팅 | `docs/spec/S6_chat.md` |
| StrDesign 규칙·기대값 | `docs/spec/S7_strdesign.md` |
| 뺄셈 의미 전수·64비트 뺄셈 알고리즘·인게임 시험 | `docs/spec/S8_subtract.md`, `docs/spec/S8_ingame/` |
| 인게임 확인 항목 분류(AUTO·VISUAL·MULTI·CRASH_RISK…)·통합 맵 `auto_all` 설계·맵별 계측 명세 | `docs/ingame_auto/classification.md`·`.json` (4.21, 5.5) |
| euddraft 0.11 재측정 | `docs/spec/WP0_report_0.81.md` (WP0 이 작성) |
