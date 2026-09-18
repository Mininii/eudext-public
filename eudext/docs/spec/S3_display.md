# S3 — DisplayPrint 대체 명세 (`eudext.display` + `eudext.numfmt`)

작성 2026-09-17. 조사·명세만 했고 코드는 만들지 않았다. 근거는 `파일:줄`, 확인하지 못한 것은 "(추측)".
DPS 이식용 명세 G8 이 이미 DisplayPrint 계열의 동작을 자세히 적었다. 이 문서는 G8 을 **바탕으로 삼고**,
(1) 9맵 전체의 실제 사용 모양, (2) 원소·대상 종류 전수 표, (3) 13번째 줄·TBL 고정 길이 규칙,
(4) DPS 서식 원소(`{SetNumX,…}` 등)의 바이트 배치, (5) `eudext.display`/`eudext.numfmt` API 확정안을 보탠다.
G8 과 같은 설명은 "G8 1.x" 로만 가리킨다.

## 약어

| 약어 | 파일 |
|---|---|
| DPL | `ScmDraft 2\MapSource\Library\DisplayPrint.lua` (1,423줄, **정본**) |
| G8 | `ScmDraft 2\DPS_eud\eud\spec\G8_text_scrdb.md` |
| CA | `ScmDraft 2\MapSource\Library\CtrigAsm v5.5.lua` |
| L322 | `ScmDraft 2\MapSource\Library\LibraryFor322.lua` |
| PU | `ScmDraft 2\MapSource\Library\Print_utf8X.lua` |
| CONV | `ScmDraft 2\DPS_eud\CallTriggers\utils\converter.lua` (DPS 서식 원소) |
| DF | `ScmDraft 2\DPS_eud\function.lua` |
| TXT | `ScmDraft 2\DPS_eud\eud\ctrig\text.py` (DPS 이식 계층의 같은 루틴) |
| EP81 | eudplib 0.81.0 소스 `…\scratchpad\upstream\eudplib\src\eudplib\` |
| R1 / R4a | `docs\research\R1_usage.md` / `R4a_bullet_text.md` |
| SCAN | 이번 집계 스크립트 `…\scratchpad\spec_s3\s3_scan.py` → `s3_report.txt`, `s3_out.json` |
| REF | 참조 모델 `…\scratchpad\spec_s3\s3_ref.py` → `s3_ref_out.txt` (8절 기대값) |

맵 약칭은 R1 0절과 같다: DPS(`DPS_eud` 루트·`CallTriggers\`), Seed(`theSeed`), Stel(`Stella_II`), ResV(`MSF_Respect_V`),
Mem2·Mem1·G2R·UERE·Brz(`MapSource\MSF_*`), Tpl(`Documents\MSF-Template`). "9맵" = Tpl 을 뺀 9곳(Tpl 은 DisplayPrint 호출 0).
집계는 주석을 뺀 정규식 셈이다(SCAN). R1 의 수와 주요 맵 합이 같다(470 / 97 / 96).

---

## 0. 한눈에

- **정의는 한 벌**(DPL)이고 9맵 모두 `MapSource\Library` 를 먼저 불러온다(예: `Stella_II\main.lua:23~28`, `MSF_Respect_V\main.lua:10~15`, `theSeed\main.lua:125`). 덮어쓰기는 `Print_13X`(DPS `function.lua:310`) 하나뿐이고 동작은 같다(G8 1.1).
- **원소 종류는 13가지**(DPL 판별 순서, 2.1 표) + 그 위에 사용자가 얹은 **함수 원소**(DPS 12종 + 맵별 맨 함수 원소 4종, 2.2 표).
  9맵 DisplayPrint 원소는 문자열 1,386(리터럴 1,299 포함) · V 418 · "숫자(변수 번호) = 1바이트 글자" 389 · 함수 원소 147(DPS) · PName 50 · W 20 · `PVWArrX`(VA/WA) 22 순이다(6.3). Er·Tbl 까지 합친 함수 원소는 213(R1 은 다른 셈으로 220).
- **대상 종류는 8가지**(3절): 상수 번호(P9~P12 관전자 포함), 루프 상수·지역 매개변수(`i`, `CP`), V(공유 번호), V(로컬 번호 `LCP`), `CurrentPlayer`, Force1~5·AllPlayers·EveryPlayers, 목록(`HumanPlayers` — **9맵 모두 관전자 P9~P12 포함**), 그 밖(오류).
  관전자는 CtrigAsm 이 CP 128~131 로 바꿔 넣는다(CA:322~399 `PlayerConvertX`, 128 로 바꾸는 줄 392~396).
- **고정 길이 규칙**: DisplayPrint 는 "틀 문자열 + 동적 원소 폭만큼 0x0D", DisplayPrintEr 는 13번째 줄(0x641598)에 "문자열은 4의 배수로 앞 채움, V 16/48, W 20, 이름 20, 글자 1", DisplayPrintTbl 은 "바이트 그대로 이어 쓰고 끝에 E2 80 89, NUL 없음"(4절).
- **eudext 결정**(7절): 서식은 **로컬 분기 안에서 대상 목록에 이 PC 가 있을 때 한 번만** 한다. 호출 자리마다 StringBuffer 한 개(DPL 의 틀과 같은 수).
  맨 `EUDVariable` 은 DPL 처럼 **부호 있는 10진**. 13번째 줄은 `f_raise_CCMU` + 로컬 가변 길이 쓰기(고정 배치 불필요), TBL 은 바이트 정확 쓰기.
  옛 화면과 바이트까지 같아야 할 때를 위해 `numfmt.dp.*` 호환 프리셋 9개를 둔다(REF 로 기대값 확정).

---

## 1. 원본 정의와 판

### 1.1 정본과 사본

| 함수 | 정본 | 다른 판 | 비고 |
|---|---|---|---|
| `DisplayPrint` | DPL:146 | 없음 | |
| `DisplayPrintEr` | DPL:413 | 없음 | 내부에서 `Print_13X` 를 서브루틴으로 부른다 |
| `DisplayPrintTbl` | DPL:32 | 없음 | |
| `DisplaySTRX` | DPL:1305 | 없음 | |
| `DP_Start_init` | DPL:1153 | 없음 | 안에서 `_0DPatchforVArr`(1243), `PName`(1253) 을 전역으로 정의한다 |
| `init_Setting` | DPL:608 | 없음 | 안에서 `dp.ItoDec`(627)·서브루틴 8개(997~1131)를 정의한다 |
| `_0DPatchforVArr` | DPL:1243 | L322:1062(같은 코드, DP_Start_init 실행 때 DPL 판으로 덮임), `ScmDraft 2\LibraryFor322.lua:537`·`Map2Source\LibraryFor322.lua:223`(Library 밖, 로드 안 됨), `MSF_GaLaXy\Gal.lua:103`(구판, 2인자 `(VArrName,VArrLength)`) | |
| `print_utf8_A` | DPL:1274 | 없음 | |
| `Print_13X` | DPL:569 | **DPS `function.lua:310`**(3인자, String=nil 이면 같음), `MSF_GaLaXy.R\func.lua:1295`, `NewTestMap3\function.lua:309` | G8 1.1 |
| `PName` | DPL:1253 | 없음. theSeed `ChatSeedInput.lua:130` 주석이 "덮어쓰면 안 된다"고 경고 | |
| (CtrigAsm 쪽 친척) | `Print_13`(CA:57574), `C13Print`(CA:79775), `CreateSV54`(CA:79718), `CAPrint`(CA:56873), `FixText`(CA:57175) | — | 9맵 호출: C13Print 0, CAPrint 3(Mem2 1·UERE 2), FixText 18 |

### 1.2 초기화 순서(맵별 줄)

`DP_Start_init` 는 맵 코드 **맨 앞**, `init_Setting` 은 모든 DisplayPrint 호출 **뒤**에 한 번 부른다(G8 `init_StrX` 함정).

| 맵 | DP_Start_init | init_Setting |
|---|---|---|
| DPS | `main.lua:73` `DP_Start_init()` | `main.lua:125` |
| Seed | `main.lua:164` `DP_Start_init(FP)` | `main.lua:353` |
| Stel | `main.lua:85` | `main.lua:131` |
| ResV | `main.lua:50` | `main.lua:94` |
| Mem2 | `main.lua:115` `DP_Start_init(FP,nil,0x4000, 0x6000)` | `main.lua:170` |
| Mem1 | `Main.lua:136` | `Main.lua:18963` |
| G2R | `main.lua:72` | `main.lua:7711` |
| UERE | `main.lua:79` `DP_Start_init(FP,{15,5000},0x4000, 0x6000)` | `main.lua:163` |
| Brz | `main.lua:83` | `main.lua:276` |

### 1.3 전역 계약

G8 1.2 그대로다: 함수 원소가 호출되는 동안 `RetV`(틀 주소 V), `Dev`(쓰기 오프셋), `BSize`(틀 길이), `dp.StrT`, `TBLPtr`, `DPGeneralFuncKey` 가 살아 있다.
DPS 밖에서도 이 계약을 쓰는 사용자 함수가 있다 — 맨 함수 원소 `HeroTextFunc`(Stel `MapLogic\System.lua:1671`, ResV `System.lua:1146`, G2R `main.lua:773`,
Seed `MapLogic\CunitSystem.lua:634` 지역 함수), `MarineTextFunc`(Seed `MapLogic\Marines.lua` 659 근처). 모두 `f_Memcpy(FP,_Add(RetV,Dev),Arr(…),0x40)` 후 `Dev`·`BSize` 를 0x40 늘린다.
eudext 는 이 계약을 흉내 내지 않고 **Part 객체**(7.3)로 대신한다.

---

## 2. 원소 종류 전부

### 2.1 DPL 이 직접 아는 원소 (판별 순서 = DPL:199~289, 첫 일치만)

폭은 바이트. "DP" = DisplayPrint·DisplaySTRX, "Tbl" = DisplayPrintTbl, "Er" = DisplayPrintEr.
사용 수는 9맵 DisplayPrint+Er+Tbl 원소 합(SCAN, 6.3). 런타임 서브루틴 배치는 4.4.

| # | 원소 | Lua 모양 | 판별 | 폭 DP / Tbl / Er | 런타임 동작 | 9맵 사용 | eudext part (7.5) |
|---|---|---|---|---|---|---|---|
| 1 | 맨 함수 | `HeroTextFunc` | `type(k)=="function"` (DPL:200) | 함수가 늘린 BSize 만큼 D / 함수 몫 / **오류**(Er 는 else 로 감, DPL:471) | `k()` | 6 (Seed 2·Stel 2·ResV 1·G2R 1) | `Pick(...)` 또는 사용자 `Part` |
| 2 | 함수 원소 | `{SetNumX, v, 1}` | `type(k[1])=="function"` (DPL:206) | 호출 전후 BSize 차 / 함수 몫 / 호출 **뒤** Dev 에 자리표시자(DPL:469) | `table.remove(k,1)` 후 `f(table.unpack(k))` — 표를 고친다 | 213 (DPS 전부: DP 147 · Er 20 · Tbl 46, 2.2) | `numfmt.Man/Per/...` |
| 3 | 문자열 | `"…"`, `"…"..x`, `StrDesign(…)` | `type(k)=="string"` | `#k` / `#k` / `#k` 를 4의 배수로 **앞에 D** 채움(DPL:429) | 없음(틀에 굽는다). Tbl 은 `CreateCText`+`f_Memcpy` 로 **런타임 복사**(DPL:72~74) | 1,299+82+5 (DP) · 147+16 (Er) · 153+3 (Tbl) | `str` / `bytes` |
| 4 | 플레이어 이름 | `PName(p)` = `{"PVA",p}` (DPL:1253) | `k[1]=="PVA"` | 20 / 20 / 20 | p=`"LocalPlayerID"` → 로컬 이름 캐시 복사, 숫자 → 그 이름, V → `CMov(VtoNameV,V)` 후 복사. **그 밖(nil)·7 이상은 아무것도 안 씀**(DPL:1013~1017) | 상수 42 · V 13(손으로 쓴 `{"PVA",v}` 1 포함) · 로컬 2 | `PName(p)` / `LocalName()` |
| 5 | V + `fwc` | `v` (단, `v.fwc=true` 를 전에 붙임) | `k[4]=="V"` 이고 `k.fwc==true` | 48 / 48 / 48(자리표시자는 16만 찍음, DPL:436) | `Call_IToDecX` (전각, 부호 없음) | 9 (DPS 4·Seed 1·UERE 4, 식별자 판정 포함) | `numfmt.Dec(v, fullwidth=True)` |
| 6 | V + `hex` | `v.hex=true` | `k[4]=="V"` 이고 `k.hex==true` | 12 / 12 / **16 으로 처리**(Er 는 hex 무시, DPL:438~444) | `Call_ItoHex` (8자리 대문자) | **0** | `numfmt.Hex(v)` |
| 7 | V | `v`, `_Add(a,b)` 같은 임시식 | `k[4]=="V"` | 16 / 16 / 16 | `Call_IToDec` (부호 있는 10진) | 474 (DP 405+임시식 13 · Er 46 · Tbl 10, 추적 못 한 식별자 뺌) | `EUDVariable` 그대로 |
| 8 | VA | `VArr(a,i)`, `PVWArrX(x)`(V 쪽) | `k[4]=="VA"` | 16 / **무시**(Tbl 에 분기 없음) / 16 | 7 과 같음. fwc/hex 무시. CP ← RecoverCp (G8 2 표 #8) | 3 (Seed) + `PVWArrX`/`PVdata` 22 중 일부 | `EUDVariable`(배열 원소 읽기) |
| 9 | W | `w`, `_LSub(…)` | `k[4]=="W"` | 20 / 20 / 20 | `f_LMov` 복사 후 `Call_lIToDec` (부호 있는 64비트 10진) | 18 + 임시식 2 (DP 만) | `Int64` |
| 10 | WA | `WArr(a,i)`, `PVWArrX(x)`(W 쪽) | `k[4]=="WA"` | 20 / **무시** / 20 | 9 와 같음 | PVWArrX 19 중 일부 | `Int64`(배열 원소) |
| 11 | V 목록 | `{v1,v2,v3,v4}` (예: `CreateVarArr(4,FP)` 표 통째) | `k[1][4]=="V"` | `#k` / **무시** / **오류** | 원소마다 하위 1바이트를 1바이트씩(`Call_TBwrite`) | 5 (G2R 2 `hondondisplay`·`AtkSpeedDisplay` — `ON`/`OFF` 글자, Mem1 1 `ExScoreP` — 의도 불명, Seed 2 `{ChatSeedValue[1],…}` `ChatSeedInput.lua:273`) | `Bytes(v1, v2, …)` |
| 12 | 숫자 | `x[2]`, `7` | `type(k)=="number"` | 1 / 1 / 1 | **변수 번호 n 의 값** `V(n)` 의 하위 1바이트를 씀(DPL:280~285). 색 코드·숫자 글자를 변수로 바꿀 때 쓴다 | 399 (DPS 372 — `CTimeDDArr[1][2]` 같은 글자 변수, `TxtColor[2]` 같은 색 변수) | `Byte(v)` |
| 13 | 그 밖 | — | — | — | `PushErrorMsg("Print_Inputdata_Error")` (Tbl 은 **조용히 무시**, DPL:63~112 에 else 없음) | 0 (SCAN 이 Seed `TrapBuilding.lua:541` `Announce` 를 Ccode 로 오판 — 실제는 문자열 매개변수) | 컴파일 시점 `EPError` |

추가로 원소 자리에 오지만 DPL 이 따로 보지 않는 모양:
- `table.unpack(Str)` (Mem1 `Main.lua:18503` 등 12) — Lua 가 표를 펼쳐 여러 원소가 된다. eudext 는 `*parts` 로 같은 효과.
- `arg` 자체가 변수(`DisplayPrint(t, TxtArr)` DPS `GameDisplay.lua:193`, `DisplaySTRX(Parts)` Seed `MissionObjective.lua:93`, Seed `CcodeWatch.lua:167`·`EasterEgg.lua:196`·`SetupMenu.lua:451`) — 컴파일 시점에 만든 원소 표. eudext 는 `dp.show(t, *parts)`.
- 원소 표 리터럴 `{"PVA", SetupAuthorityPlayer}` (Seed `SetupMenu.lua:283`) — PName 을 손으로 쓴 것.
- 정의를 추적하지 못한 식별자·식 DP 111 · Er 9 · Tbl 12개(주로 함수 매개변수: 문자열 또는 V) — SCAN 한계(11절).

### 2.2 함수 원소 (사용자 정의)

DPS 12종은 CONV 에 있고 `CallTriggers\init.lua:158~168` 에서 전역 별칭을 만든다. 배치는 4.5.

| 함수 | 정의 | 판 | 폭 | 인자 | 9맵 사용(주석 제외) | 3번째 인자 사용률(주석 포함 grep) |
|---|---|---|---|---|---|---|
| `SetNumX` | CONV:474 | STR | 18 | `(V/VA/W/WA, ColorCodeOp)` | 62 | 색 켬 56/87 |
| `SetNumX128` | CONV:495 | STR | 18 | `({W lo, W hi}, ColorCodeOp)` | 32 | 18/39 |
| `SetNumX256` | CONV:505 | STR | 18 | `({W,W,W,W}, ColorCodeOp)` | 3 | 3/3 |
| `SetEPerSTRX` | CONV:445 | STR | 8 | `(V, PermilFlag)` | 46 | 퍼밀 5/77 |
| `SetNumTBLX` | CONV:460 | TBL | 18 | `(V/W, ColorCodeOp)` | 17 | 12/17 |
| `SetNumTBLX128` | CONV:517 | TBL | 18 | 128비트 | 7 | 2/7 |
| `SetNumTBLX256` | CONV:526 | TBL | 18 | 256비트 | 1 | 1/1 |
| `SetEPerTBLX` | CONV:431 | TBL | 8 | `(V, PermilFlag)` | 18 | 0/18 |
| `SetNumErX` | CONV:537 | Er(지연) | 18 | `(V/W, ColorCodeOp)` | 20 | 20/20 |
| `dpletter2` | DPS `GameDisplay.lua:90`(지역 정의) | STR | 2 | `(V)` | 2 | — |
| `GaugeBar` | DF:2378 | STR | 40 (+틀에 막대 문자열을 **한 번 더** 넣음) | `(V, ResetFlag)` | 2 | — |
| `GaugeBarTbl` | DF:2400 | TBL | 40 | `(V)` | 3 | — |

맵별 맨 함수 원소(1.3): `HeroTextFunc` 4맵, `MarineTextFunc`(Seed) — 모두 "런타임에 고른 컴파일 시점 문자열(0x40바이트, `print_utf8_A` 로 구움)을 복사".

### 2.3 원소 판별의 함정

- **판별 순서가 의미다.** V 표는 `k[1]`(주인 플레이어 번호)이 숫자라서 2번(함수) 검사는 통과하지 않고, `k[4]` 로 7번에 간다. VA 는 Tbl 에 분기가 없어 **조용히 사라진다**(Dev 도 안 늘어 뒤 원소가 당겨진다).
- `{함수,…}` 는 `table.remove` 로 **표를 고친다** — 같은 표를 두 번 넘기면 두 번째는 함수가 아니다(G8 1.2).
- `v.fwc=true` / `v.hex=true` 는 V 표에 **영구히** 붙는다(DPS `GameDisplay.lua:109` `LevelLoc["fwc"] = true`, Mem1 `Main.lua:18954` `ExScoreP[i]["fwc"] = true`). 그 뒤 어디서 찍든 전각이다.
- 숫자 원소는 **글자 코드가 아니라 변수 번호**다. `DisplayPrint(t,{…,0x1F,…})` 는 0x1F 번 변수의 값을 쓴다(주석 "상수index V 입력", DPL:280). 9맵의 숫자 원소는 모두 `x[2]` 모양이라 실수는 없었다.
- V 목록(11)과 V 배열 통째(`CreateVarArr` 결과)는 같은 모양이다. Mem1 `Main.lua:18956` `ExScoreP`(5칸)는 fwc 를 원소마다 붙인 뒤 표 통째를 넘겨 **1바이트 5개**가 찍힌다(의도는 `ExScoreP[i]` 로 보임 — 추측).
- 이름 원소는 플레이어 0~6 캐시만 있다(DPL:976, 1013). `PName(7)` 이상·관전자 번호는 **이전 내용이 남는다**(G8 2 표 #4). LocalPlayerID 캐시는 관전자에서 초기값(0 추정)이라 **NUL 20개**가 복사돼 줄이 그 자리에서 끊긴다(G8 1.4(f)).

### 2.4 숫자 서식 옵션 (ItoDec 계열)

DisplayPrint 안에서는 옵션이 **고정**이다(`init_Setting`, DPL:998·1003·1008). 사용자가 옵션을 고를 수 있는 곳은 `ItoDec`/`ItoDecX`/`CA__ItoCustom` 직접 호출(R1 1-a: ItoDec 20, ItoCustom 55)이고, 그 의미는 R4a C.1 표에 있다.

| 옵션 | 뜻 (CA:58336, 58911 머리 주석) | DisplayPrint 안의 값 | numfmt 대응 (DESIGN 4.6) |
|---|---|---|---|
| ZeroMode | 앞자리 채움: 0 `'0'` / 1 공백(전각은 U+3000) / 2 0x0D | IToDec 2, IToDecX 2, ItoHex **0** | `fill="0"` / `" "` / `"\r"` |
| Color | 색 바이트(0x01~0x1F, 기본 0x0D). DecX 는 자리마다 표(맨 뒤부터) | 없음(0x0D) | `color=` / `colors=(…)` |
| Sign | 0 부호 없음 / 1 `-`(CA 는 양수 `+`, DPL `dp.ItoDec` 은 양수 **D**) / 2 부호+공백 | IToDec **1(DPL 판)**, IToDecX 0 | `sign=None` / `"-"` / `"+-"` / `sign_space=True` |
| DigitMax | 그보다 윗자리를 0x0D 로 지움(1~10) | 10 | `max_digits=` |
| DigitMin | **아래 k−1 자리를 지움**(최소 폭 아님, DPL:943~967) | 1 | `cut_low=k-1` |
| Case (Hex) | 0 대문자 / 1 소문자 | 0 | `Hex(lower=)` |

---

## 3. 대상 종류 전부

DisplayPrint 의 출력은 `DisplayText(틀, 4)` 한 번이고, SC 는 **CP 가 이 PC 의 플레이어일 때만** 글자를 띄운다(G8 1.5). 대상 처리는 DPL:300~330.

| # | 대상 모양 | 판별 | 원본 동작 | 끝난 뒤 CP | 관전자 | 9맵 사용 (DP / Er) | eudext (7.6) |
|---|---|---|---|---|---|---|---|
| T1 | 상수 번호 `0`, `P1` | 숫자 | `RotatePlayer({DisplayTextX},{p},FP)` = `SetMemory(0x6509B0,SetTo,p)`+DisplayText (L322:74 → CA:42981) | **FP(7)** | P9~P12 → 128~131 | 3 / 0 | `P1`, `0` |
| T2 | 루프 상수 `i`, `i-1`, 지역 매개변수 `CP` | Lua 숫자(컴파일 시점) | T1 과 같음(루프마다 호출 자리 한 벌) | FP | — | 26 / 20 | `for p in …: dp.show(p, …)` 또는 `players.each` |
| T3 | V (공유 번호) `GCP`, `UpgradeCP`, `GiveNextP`, `OCU_CP` | `k[4]=="V"` | `CDoActions(FP,{TSetMemory(0x6509B0,SetTo,V),DisplayText})` (DPL:310~319) | **V 값** | V 가 128~131 이면 관전자 | 110 / 70 | `EUDVariable` |
| T4 | V (**로컬** 번호) DPS `LCP` | 같음 | 같음. `iv.LCP` 는 `CIf(LocalPlayerID(i))` 안에서 i(0~3)로 한 번 채운다(DPS `OnInit.lua:302~303`) → **모든 PC 가 각자 자기 화면에** 찍는다 | 로컬 값(PC 마다 다름) | 관전자는 LCP=초기값 0 → 안 보임(추측) | 197 / 0 | `dp.LOCAL` |
| T5 | `CurrentPlayer`, `"CP"` | 상수 비교 | `f_SaveCp()` 후 끝에 `TSetMemory(0x6509B0,SetTo,BackupCp)`+DisplayText (DPL:168, 300~309) | BackupCp | — | 0 (DPS `function.lua:636` 의 `CP` 는 지역 매개변수 = T2) | `CurrentPlayer` |
| T6 | `Force1~4`, `AllPlayers` | 숫자 상수 | RotatePlayer → `PlayerConvertX`: TEP `SetForces(...)` 로 정한 `CForce1..4`/`CAllPlayers` 표(CA:322~399) | FP | Force5 = P9~P12 → 128~131, `EveryPlayers` = AllPlayers+관전자 | Force1 18, AllPlayers 7 / 0 | `Force1…`, `players.Observers` |
| T7 | 목록 `HumanPlayers`, `{P1,…,P5}`, `MapPlayers` | 표 | RotatePlayer 가 원소마다 CP 를 바꿔 DisplayText (원소 수만큼 액션 2개) | FP | **HumanPlayers 는 9맵 모두 P9~P12 포함**(DPS `Variables.lua:17`, Seed `MapConfig\Setup.lua:539`, Stel `Vars.lua:8`, ResV `Variables.lua:7`, Mem2 `Var_init.lua:249`, Mem1 `Main.lua:113`, G2R `main.lua:62`, UERE `Var_Include.lua:36`, Brz `Variables.lua:6`). Mem2·G2R 는 P8 도 포함 | 109 / 7 (Er 는 `MapPlayers`) | `list`/`tuple`, `players.Humans` |
| T8 | 그 밖 | — | RotatePlayer 에 넘어가 `Input[P+1]` 로 처리 — 문자열 등은 Lua 오류 | — | — | 0 | `EPError` |

- **Er 의 대상**(DPL:477~519): 숫자(0~7, 8 이상은 `PushErrorMsg`), V, 숫자·V 목록. 공유 부분은 대상마다 `Call_Print13X`(CCMU), 로컬 부분은 `0x512684 == 대상`(목록이면 `TTOR`). 관전자 대상은 **받지 않는다**(8 이상 오류).
  UERE `Player_interface.lua:1003` 의 `CP` 는 지역 매개변수(숫자) = T2.
- **Tbl 은 대상이 없다**(TBL 메모리는 모든 PC 에 쓴다, 로컬 표시용).
- `FixTextPreset`(4.1, 5.1) 은 **숫자 대상일 때만** 로컬 조건이 선다. Brz `Interface.lua:699` `DisplayPrint(i, {...}, 3)` 이 유일한 사용.
- CtrigAsm 의 `CForce1..4` 는 TEP `SetForces` 인자(예: Seed `main.lua:150` `SetForces({P1..P7},{P8},{},{},{P1..P8})`)로 정해진다. eudplib 의 Force 는 맵 FORC 절에서 읽는다 → **두 표가 다를 수 있다**(9절).

---

## 4. 고정 길이 규칙

### 4.1 DisplayPrint·DisplaySTRX 틀

- 틀 = 원소 순서대로 [문자열은 그대로] + [동적 원소는 폭만큼 0x0D] + 끝 `\r\r\r\r` (DPL:298, 1412). 폭은 2.1 표.
- 이 틀을 `DisplayText` 로 STRx 표에 올리고, `init_StrX` 가 `RetV = 0x191943C8 + dword[0x191943C8 + 4·id]` 로 주소를 채운다(G8 1.3). 동적 원소는 `RetV + Dev` 에 **모든 PC 에서** 쓴다.
- 같은 글자의 틀은 문자열 번호가 같아 **버퍼를 공유**한다(G8 1.3). ResetTimer 호출끼리 겹치면 섞인다.
- 함수 원소는 BSize 증가분만큼 D 를 넣는다. `GaugeBar`(ResetFlag=nil)는 막대 문자열 40B 를 `dp.StrT` 에 **직접** 넣고 BSize 도 40 늘려, 틀에는 막대 40B + D 40B = **80B** 가 들어가지만 Dev 는 40 만 는다 → 뒤 동적 원소가 틀의 D 구간에 찍혀 **앞으로 당겨진다**(DF:2378~2398, DPS `GameDisplay.lua:143,153`). 원본 동작.
- `FixTextPreset`: 1·3 → 출력 전 `FixText(FP,1)`(0x640B58 저장), 2·3 → 출력 후 `FixText(FP,2)`(복원). 숫자 대상일 때만 `CIf(0x512684==n)` 안(DPL:147~167, 335~356).
- `ResetTimer`: V 면 `CIf(CV(V,0))`, 숫자 N 이면 전역 Ccode 로 N 사이클마다(DPL:178~191). **버퍼 갱신만** 감싸고 DisplayText 는 매 사이클(G8 1.5).
- `SoundRepeat`: WAV 이름 표. 대상 처리 액션 뒤에 `PlayWAV`/`PlayWAVX` 를 붙인다(DPL:303~328). 같은 이름을 여러 번 넣는 것은 볼륨용 관용구(Seed `CunitSystem.lua` 주석).

### 4.2 13번째 줄 (DisplayPrintEr)

주소 `0x641598` = `0x640B60 + 12·218`(4의 배수). 컴파일 시점에 오프셋을 정하고, 런타임에는 로컬에서 덮어쓴다(DPL:413~563, `print_utf8_2` DPL:371).

1. `Dev=0`. 원소마다(DPL:426~474):
   - 문자열: `L = #k`(TEP30Flag=1, G8 1.1). `L%4≠0` 이면 **앞에** D 를 `4−L%4` 개 붙여 L 을 4의 배수로. `print_utf8_2(12, Dev, k)`. Dev += L.
   - V/VA: `print_utf8_2(12, Dev, D×16)`, 나중 목록에 `(v, Dev, fwc)`. Dev += 16 (fwc 면 48).
   - W/WA: D×20, Dev += 20. PName: 자리표시자 없음, Dev += 20. 숫자: D×1, Dev += 1.
   - `{함수,…}`: 호출 전 Dev 를 기억하고 호출한 뒤 **호출 뒤 Dev** 에 D×증가분을 찍는다(원본 버그, 대개 무해). `SetNumErX` 는 여기서 트리거를 만들지 않고 `DPGeneralFuncKey` 에 `(클로저, 호출 전 Dev)` 를 넣는다(CONV:537~550).
2. `print_utf8_2(line, off, s)`: `dst = 0x640B60 + line·218 + off`. `dst%4≠0` 이면 앞에 D 를 `dst%4` 개 붙이고 `dst − dst%4` 부터 dword 로 쓴다. 문자열이 4의 배수가 아니면 마지막 dword 의 남는 바이트는 **0(NUL)**. **끝 NUL 은 따로 붙이지 않는다**(G8 2 `DisplayPrintEr`).
   - 그래서 1바이트 숫자 원소 뒤의 문자열은 한 칸 앞(숫자 자리)부터 D 를 쓰고, 숫자 바이트는 **나중에** 로컬 블록이 다시 쓴다(DPL:550~553) → 결과는 맞다.
3. 공유 부분: 대상마다 `Print_13X`(CCMU 트릭, G8 1.7). `OP_Hold ~= "X"` 면 숫자 대상마다 `SetDeaths(k, SetTo, OP_Hold[2], OP_Hold[1])`, V 대상이면 `TSetDeaths` (DPL:488~496).
   UERE `DP_Start_init(FP,{15,5000},…)` 은 Er 을 띄울 때마다 대상의 **유닛 15 데스 = 5000** 을 넣고, UERE `Operator.lua:8,12,383` 의 상시 13번째 줄 안내는 `Deaths(i,AtMost,0,15)` 일 때만 쓴다 → **Er 문구가 상시 안내에 덮이지 않게 잠그는 장치**(데스를 줄이는 쪽은 확인 못 함, 11절).
4. 로컬 부분 `CIf(0x512684 == 대상)`(목록이면 TTOR, DPL:506~519):
   1. `print_utf8_2(12, 0, D×210)` — 0x641598 부터 **210B 를 D, 210·211 은 NUL**(마지막 dword `D D 00 00`).
   2. 문자열·자리표시자 액션(1단계 결과) 실행.
   3. `publicItoCusPtr ← 0x641598`. 32비트 → 64비트 → 이름 → 글자 → 지연 함수 순서로 서브루틴 실행(DPL:523~556). 서로 겹치지 않으므로 순서는 결과에 영향이 없다.
   4. 이름 원소가 V 면 `VtoNamePtr` **만** 채우고 `VtoNameV` 를 안 채운다(DPL:545~546, 원본 버그 → 이전 번호의 이름이 찍힘). UERE `Player_interface.lua:482,485` 가 이 모양(`PName(TempGivePV2)`)이다 → **그 줄의 이름은 틀릴 수 있다**(추측, 인게임 확인 11절).
5. 한 줄 = 218B 이므로 Dev 가 210 을 넘으면 NUL 을 덮고 넘친다(검사 없음). 한 틱에 Er 을 두 번 부르면 뒤 호출이 앞을 지운다(Seed `ChatSeedInput.lua:271~272` 주석).

REF `er_layout` 예: `{"\x07HP ", v=123, " / ", 글자 0x1F, "MAX"}` → 앞 32B `07 48 50 20 | 0D×13 31 32 33 | 0D 20 2F 20 | 1F 0D 4D 41 58 00 00 00`, Dev=29, 보이는 글 `<07>HP 123 / <1F>MAX`.

### 4.3 TBL (DisplayPrintTbl)

1. `TBLPtr` = TBL id 마다 V 하나(`dp.TBLKeyArr`, DPL:39~47). `init_StrX` 가 `f_GetTblptr` 로 채운다: `ptr = 0x19184660 + word[0x19184660 + 2·id]`(G8 1.8, id 는 1부터).
2. `Dev=0`. 원소를 **바이트 그대로** 이어 쓴다. 문자열은 `CreateCText`(L322:381) 배열에서 `f_Memcpy` 로 `#k` 바이트(정렬 없음). V 16/48/12, W 20, 이름 20, 숫자 1(2.1 표). **VA·WA·V 목록은 무시**.
3. 끝에 `Call_TBwrite` 세 번으로 **E2 80 89**(U+2009) — 4번째 인자 `UTF8OptionOff` 가 nil 일 때만(DPL:115~119). **NUL 은 쓰지 않는다.**
4. 그래서 이번에 쓴 길이보다 원래 TBL 문자열이 길면 뒤가 남아 보인다 → DPS 는 문자열 끝에 D 를 잔뜩 붙이고(DPS `TBL.lua:968`), ResV 는 `\t…\x0D×20`(ResV `Interface.lua:892~895`)으로 덮는다.
5. 쓴 길이가 원래 자리보다 길면 **다음 TBL 문자열을 덮는다**(검사 없음). 자리 크기는 eds `[dataDumper] custom_txt.tbl` 이 정한다(G8 1.8).
6. `UTF8OptionOff=1` 사용: Seed `KickVote.lua:103`(1), ResV `Interface.lua:892~895`(4) — 끝 3바이트도 안 쓴다.

REF `tbl_layout` 예(원래 자리 32B 를 `?` 로 가정): `{"\x04Lv ", v=42}` → `04 4C 76 20 | 0D×14 34 32 | E2 80 89 | 3F×9` (NUL 없음, 뒤 `?` 가 남는다).

### 4.4 서브루틴 배치 (G8 1.4 요약)

| 서브루틴 | 폭 | 배치 (D = 0x0D) | 근거 |
|---|---|---|---|
| `Call_IToDec` | 16 | `D D D D` · `색(D)` · `부호(D 또는 '-')` · 10^9 · 10^8 · 10^7..10^0. 앞자리 0 은 D, 1의 자리는 늘 숫자. 음수는 절댓값 | DPL:627~969, 997~1000 |
| `Call_IToDecX` | 48 | `D×8` + 10칸 × `[D, EF, BC, 90+d]`. 앞자리 칸은 `D D D D`. 부호 없음 | CA:58911~59080, DPL:1002~1005 |
| `Call_ItoHex` | 12 | `D×4` + 8자리 대문자(앞 0 유지) | CA:58673, DPL:1007~1010 |
| `Call_lIToDec` | 20 | 바이트 (19−i) = 10^i. 양수: 바이트0 은 늘 D, 앞 0 은 D. **음수: 바이트0 '-', 나머지 19자리 0 채움**(`-0000000000000000005`) | DPL:1029~1080 |
| `Call_VtoName` / `VtoLPName` | 20 | `[D D D 색]` + 이름 16B(0 바이트는 D). 색 = `ColorCode[p+1]` = {08,0E,0F,10,11,15,16,17}(DPL:1155). 이름 표 `0x6D0FDC + 0x24·p` | DPL:976~984, 1012~1022, CA:58307 |
| `Call_TBwrite` | 1 | `TBwInputChar & 0xFF` | DPL:1024~1026 |
| `Call_Print13X` | — | CCMU 트릭 | DPL:1129, G8 1.7 |

기대값은 8.1(REF 가 DPL 줄을 그대로 옮긴 모델, TXT 의 이식 루틴과 배치가 같다: TXT:163~330).

### 4.5 DPS 서식 원소 배치

**`SetNumX` 계열 — 만·억·조 단위 18B** (`Call_WarLetter`, CONV:223~428). 값 V(32/64/128/256비트, 부호 없음):

1. 단위 t: V < 10^4 이면 t=0, 아니면 10^(4t) ≤ V < 10^(4t+4) 인 t(1=만 … 17=무, 17 은 위 한계 없음). CONV:237~300.
2. 윗덩이 `A = ⌊V / 10^(4t)⌋`(32비트로 자름), 아랫덩이 `B = ⌊V / 10^(4t−4)⌋ mod 10^4`(t=1 이면 `V mod 10^4`). t=0 이면 A=0, B=V. CONV:317~352.
3. 색: t 마다 (색1, 색2) 표(CONV:282~300: 만 1C/03, 억 1D/1C, 조 19/1D, 경 1B/19, 해 15/1B, 자 11/15, 양 18/11, 구 1E/18, 간 1F/1E, 정 10/1F, 재 11/10, 극 08/11, 항 06/08, 아 07/06, 나 04/07, 불 02/04, 무 01/02), t=0 은 03/03. `ColorCodeOp` 가 nil 이면 둘 다 D(CONV:359).
4. 4자리 글자 `L(n)`: 1000·100·10·1 자리 ASCII, 앞 0 은 D, 1의 자리는 늘 숫자(CONV:43~55).
5. 바이트(CONV:361~418):
   - t=0: [0..5]=D, A=B=0 이면 [0]=색1, [4]='0'. [9..11]=D.
   - t≥1: [0]=색1, [1..4]=L(A), 색 켬이면 [5]=0x04.
   - B≠0: [9]=색2, [10..13]=L(B), 색 켬이면 [14]=0x04. B=0: [9..14]=D, [15..17]=D.
   - 단위(CONV:420~428, 387~396): [6..8]=단위(t) UTF-8 3B(t=0 은 D×3). B≠0 이고 t≥2 면 [15..17]=단위(t−1), t=1 이면 D×3.
   - 색을 끈 호출에서 [5]·[14] 는 쓰이지 않고 틀의 D 가 남는다.
6. 보이는 모양: `1234만5678`, `1억 5만`(가운데 0 덩어리는 사라짐 → `1억 0005만`은 `1억5만`), `0`. **위 두 덩이만** 보이고 나머지 자리는 버린다.
7. 128/256비트: V ≥ 2^128 이면 `Math128` 나눗셈이 **위 64비트끼리만** 나눈다(CONV:326~340) → 10^40 이상에서 아랫덩이가 어긋날 수 있다(계산상 추측). t=17(무)에서 A ≥ 10^4 이면 `L(A)` 가 한 자리에 10 이상을 넣어 글자가 깨진다(10^72 이상).

**`SetEPer*` — 1/1000 단위 소수 8B** (CONV:59~95, 431~458): x = min(V, 최대). 최대 = 100000, 퍼밀이면 STR 5000000 / TBL 1000000.
바이트 = `[10^6][10^5][10^4][10^3] '.' [10^2][10^1][10^0]`(x 의 자리). 앞: 10^6 자리 ≤'0' 이면 D, 10^5·10^4 는 윗자리가 모두 D 이고 자신이 ≤'0' 일 때 D, **10^3 자리는 늘 보인다**.
뒤: 10^0 자리 ≤'0' 이면 D, 10^0·10^1 모두 ≤'0' 이면 10^1 도 D, 셋 다면 10^2 와 '.' 도 D. 예: 12500 → `12.5`, 12050 → `12.05`, 100000 → `100`, 1 → `0.001`.

**`dpletter2` — 2B** (DPS `GameDisplay.lua:90~99`): `L(v)` 의 10·1 자리. 0~9 → `D d`, 10~99 → 두 자리, 100 이상은 **아래 두 자리만**(`105` → `05`).

**`GaugeBar(Tbl)` — 40B**: `"\x04l"×20`. `i+1 ≤ v` 인 칸 i(0~19)의 색 바이트(짝수 오프셋)를 0x07 로(DF:2378~2410). v ≥ 20 이면 전부 0x07. STR 판의 틀 이중 삽입은 4.1.

---

## 5. 함수별 명세

### 5.1 DisplayPrint

- **원본 정의**: DPL:146 (정본 하나).
- **인자·기본값**: `DisplayPrint(TargetPlayers, arg, FixTextPreset=nil, SoundRepeat=nil, ResetTimer=nil)` — 대상 3절, 원소 2절, 추가 인자 4.1.
- **런타임 동작**: G8 2 `DisplayPrint` 의 방출 순서 1~11 그대로. 요약:
  - 버퍼 쓰기는 **모든 PC**(조건이 공유 조건이면). 값이 로컬 값(`LCP` 대상, 선택 유닛)이면 PC 마다 다른 내용 — 게임 상태가 아니라 디싱크 없음(G8 1.6).
  - 출력은 대상 CP 로 DisplayText → 그 PC 에서만 보인다.
  - **CP 를 되돌리지 않는다**: V 대상 → V 값, 목록·Force·숫자 → FP(7), `CurrentPlayer` → BackupCp(3절).
  - 작업 변수(`dp.publicItoDecV` 등)는 공유 변수지만 쓰기 전에 읽는 공유 로직이 없어 안전(G8 1.6).
- **실제 사용 모양**(9맵 470, 그 밖 28):
  - `DisplayPrint(Force1,{"\x07보유금액 \x04: ",{SetNumX256,{…},1}," \x04원\x12\x07사냥터 \x1B",{dpletter2,IncomeLoc}," / \x19",{dpletter2,IncomeMaxLoc}},nil,nil,iv.Time5)` DPS `GameDisplay.lua:107` — 함수 원소 + ResetTimer
  - `DisplayPrint(GiveNextP, {"\x12\x07『 ",PName(GivePrevP),"\x04에게 \x1F",GiveMin," Ore\x04를 기부받았습니다.\x02 \x07』"})` ResV `CallTriggers.lua:10` — 대상 V + 이름 V
  - `DisplayPrint(HumanPlayers,{"\x13"..StrD[1],HeroTextFunc,"\x04을(를) \x07처치하였습니다! \x1F＋ ",HPTInput," \x1FＰｔｓ"..StrD[2]})` Stel `MapLogic\System.lua:1691` — 관전자 포함 목록 + 맨 함수
  - `DisplayPrint(HumanPlayers, {"\x13",PName(i),"\x04가 매크로를 …"}, nil, {"staredit\\wav\\zzirizziri.ogg",…})` Stel `System.lua:2868` — SoundRepeat
  - `DisplayPrint(HumanPlayers,{…,GlobalLoveSys,…,DCount,"\x04/\x06",DCountMAX,…},nil,nil,5)` Stel `System.lua:2917` — 숫자 ResetTimer, `FixText(FP,1)`(2914)·`FixText(FP,2)`(2937) 사이
  - `DisplayPrint({P1,P2,P3,P4,P5}, {"\x10【 \x11T\x04enebris\x10 】\x08 : ",TestW})` Mem1 `Main.lua:1892` — W
- **eudext 대응**: `dp.show(target, *parts, sound=, every=, update_if=, pin=)` (7.2). 원소 대응 7.5, 대상 대응 7.6.
- **시험 기대값**: 8.1 서브루틴 표, 8.2 캡처 시험(대상별 DisplayText 발생 PC, 버퍼 바이트).
- **인게임 확인**: 관전자 대상 표시, `pin=True` 줄 고정, `every=` 갱신 주기(8.3).
- **함정**: 틀 공유(4.1), GaugeBar 이중 삽입, fwc 영구 플래그, CP 미복구, Force 표 출처(3절), 숫자 원소=변수 번호.

### 5.2 DisplayPrintEr

- **원본 정의**: DPL:413 (내부 `Print_13X` 는 DPS 에서 `function.lua:310` 판).
- **인자·기본값**: `DisplayPrintEr(TargetPlayer, arg)` — 대상은 숫자(0~7)·V·목록, 원소는 2.1 의 Er 열(맨 함수 오류, hex 무시, V 목록 오류). 전역 `OP_Hold` 는 `DP_Start_init` 2번째 인자.
- **런타임 동작**: 4.2. 공유(CCMU·OP_Hold) → 로컬(줄 초기화·쓰기). **공유 조건으로만 도달해야 한다**(G8 1.6 — 로컬 조건으로 열면 CCMU 가 한 PC 에서만 돈다).
  CP: `CallTrigger`·`CMov` 가 RecoverCp 를 쓰는 만큼 바뀐다(G8 2). 대상 CP 설정은 없다(CreateUnit 의 플레이어 칸으로 대상 지정).
- **실제 사용 모양**(9맵 97, 그 밖 3):
  - `DisplayPrintEr(GCP, {"\x07『 \x1F은\x1C하\x1D의 \x1E조\x02각\x04을 ", {SetNumErX, TempCostV, 1}, "\x04개 소모하여 \x07강화하였습니다. \x07』"})` DPS `CallTriggers\items\crystal.lua:307`
  - `DisplayPrintEr(GCP, {"\x07『 ", TxtColor[2], G_PushBtnm, "강 \x04유닛 \x1B자동강화 \x07ON …"})` DPS `CallTriggers\ui\button_auto.lua:55` — 색 변수 번호 + V
  - `DisplayPrintEr(MapPlayers, {"TotalM : ",TotalM})` ResV `GunData.lua:1382` — 목록
  - `DisplayPrintEr(i, {"\x07『 ",PName(TempGivePV2),"\x04에게 \x1F",TempGiveVX," Ore\x04를 기부하였습니다. \x07』"})` UERE `Player_interface.lua:482` — 이름 V(원본 버그 경로, 4.2-4-4)
- **eudext 대응**: `dp.show_line13(target, *parts, hold=)` (7.2). 고정 배치는 따르지 않는다(가변 길이 + NUL, 최대 217B 컴파일 검사).
- **시험 기대값**: 8.1 `er_layout`, 8.2 CCMU 액션 순서.
- **인게임 확인**: CCMU 뒤 글자가 보이는지, 유닛 한도 가득(0x628438=0)일 때, `hold=` 잠금.
- **함정**: 한 틱에 두 번 부르면 앞이 지워짐, 210B 초과 넘침, 이름 V 버그, 대상 8 이상 오류(관전자 불가), 로컬 조건 안에서 부르면 디싱크(CCMU 가 공유 동작).

### 5.3 DisplayPrintTbl

- **원본 정의**: DPL:32.
- **인자·기본값**: `DisplayPrintTbl(TBLID, arg, ResetTimer=nil, UTF8OptionOff=nil)`. TBLID 는 Lua 숫자(식 가능: `PersonalUIDArr[j]+1`, `MarID[1]+1`, `KickVoteTblIDs[k]`).
- **런타임 동작**: 4.3. 대상 없음, 모든 PC 에서 쓴다. `TBLPtr`·`Dev` 는 호출 뒤에도 남는다(G8 2). CP 는 `f_Memcpy`·`CMov` 가 바꾸는 만큼.
- **실제 사용 모양**(9맵 96: DPS 83, ResV 12, Seed 1):
  - `DisplayPrintTbl(92,{"\x08\x081강~25강 \x1C자동사냥 \x18설정"})` DPS `TBL.lua:144` — 상수 문자열만(48회가 이 모양)
  - `DisplayPrintTbl(113,{"\x08강화 \x07진행도 \x04: \x1B",iv.E56_ProgressLoc," \x04/ \x06",iv.E56_ProgressMAXLoc},iv.Time5)` DPS `TBL.lua:822` — V + ResetTimer(21회)
  - `DisplayPrintTbl(PersonalUIDArr[j]+1, {"\x08\x07『 \x19진 \x07각성 \x07",{SetNumTBLX,iv.CSL_AwakLoc,1},"\x07단. ",PName(j-1)," \x07』\x0D…"})` DPS `TBL.lua:968` — 플레이어별 유닛 툴팁
  - `DisplayPrintTbl(1391,{"z\x02\x07。…(\x1F",HealCost[i+1]," Ore\x04) …"})` ResV `Interface.lua:1715` — 단축키 2바이트(`z`, 0x02) 머리
  - `DisplayPrintTbl(KickVoteTblIDs[k], {KickVoteHotkeyPrefix .. StrD[1], PName(…), …}, nil, 1)` Seed `MapLogic\KickVote.lua:103` — UTF8OptionOff
- **eudext 대응**: `dp.set_tbl(tbl_id, *parts, tail=" ", eos=True, every=, update_if=)` (7.2).
- **시험 기대값**: 8.1 `tbl_layout`.
- **인게임 확인**: NUL 을 쓰는 eudext 방식에서 툴팁이 정상인지, U+2009 없이 쓸 때(`tail=None`) 모양.
- **함정**: 자리 넘침(다음 문자열 덮음), NUL 없음(뒤 잔재), VA/WA 무시, 같은 TBLID 를 여러 호출이 나눠 쓰면 호출 순서가 결과를 정함(G8 2).

### 5.4 DP_Start_init

- **원본 정의**: DPL:1153.
- **인자·기본값**: `DP_Start_init(FixedPlayer=FP, DP_OP_Hold=nil→"X", AllocStart=0xC000, AllocEnd=0xF000, SettingOp=nil)`.
  - `FixedPlayer` 가 nil 이고 전역 FP 도 없으면 오류. `STRCTRIGASM==0` 이면 오류(DPL:1170).
  - `DP_OP_Hold = {DeathUnit, Value}` → Er 공유 부분의 SetDeaths(4.2-3). UERE 만 `{15,5000}`.
  - `AllocStart/End` 는 `dp.Alloc`/`dp.AllocLimit` 에만 들어가고 **쓰이지 않는다**(Mem2·UERE 가 `0x4000,0x6000` 을 넘김).
  - `SettingOp` 가 있으면 초기화 사슬 연결 액션을 트리거로 만들지 않고 표로 돌려준다(DPL:1259~1263). 9맵 사용 0(NTM3 `main.lua:160` 만 1).
- **런타임 동작**: 전역 `ColorCode`·`dp` 표·작업 변수·서브루틴 번호를 만들고(DPL:1155~1222), `_0DPatchforVArr`·`PName` 을 전역으로 정의, 1회 초기화 사슬(`dp.CustominitJump`)을 첫 사이클 맨 앞에 끼운다(DPL:1260, G8 1.3·G5).
- **실제 사용 모양**: 1.2 표(9맵 각 1회). `DP_Start_init()`(DPS, 인자 없음 — 전역 FP 사용), `DP_Start_init(FP)`(5맵), `DP_Start_init(FP,{15,5000},0x4000, 0x6000)`(UERE).
- **eudext 대응**: **필요 없음**. `import eudext.display` 가 끝이다. 이름 캐시가 필요하면 7.3 `PName(cache=True)`. OP_Hold 는 `show_line13(hold=)` 로.
- **시험**: 없음(설치 코드).
- **함정**: 이 호출 전에 `PName` 을 부르면 nil 호출 오류(G8 1.1). `ColorCode` 전역을 다른 코드(DPS `OnInit.lua:309`)가 같이 쓴다.

### 5.5 init_Setting

- **원본 정의**: DPL:608.
- **인자**: 없음.
- **런타임 동작**:
  1. 1회 구역(DPL:975~988): 플레이어 0~6 이름 캐시(`ItoName` + `_0DPatchforVArr`), 로컬 플레이어 이름 캐시(`CIf(LocalPlayerID(i))`), `init_StrX()`(모든 틀·TBL 주소 채우기), 초기화 사슬 복구.
  2. 서브루틴 정의(DPL:995~1136): `Call_IToDec`, `Call_IToDecX`, `Call_ItoHex`, `Call_VtoName`, `Call_VtoLPName`, `Call_TBwrite`, `Call_lIToDec`(`CheckInclude_64BitLibrary==1` 일 때만), `Call_Print13X`.
- **실제 사용 모양**: 1.2 표. 항상 맵 코드 끝(모든 DisplayPrint 뒤).
- **eudext 대응**: 없음. 서브루틴은 numfmt 의 공용 `EUDFunc`(처음 부를 때 한 벌), 주소는 eudplib `GetMapStringAddr`(상수 Forward)·`GetTBLAddr`(런타임 캐시, EP81 `string/tblprint.py:30`)가 맡는다.
- **함정**: `init_StrX` 뒤에 추가된 DisplayPrint 는 주소가 비어 **0 번지에 쓴다**(DPL 에 검사 없음, G8 `init_StrX`). 64비트 라이브러리를 안 켠 맵(Seed 등)에서 W 원소를 쓰면 `Call_lIToDec` 가 없다 — 9맵에서 W 원소는 DPS·Mem1 만(둘 다 64비트 켬).

### 5.6 _0DPatchforVArr

- **원본 정의**: DPL:1243 (L322:1062 동일).
- **인자**: `_0DPatchforVArr(Player, VArrName, VArrLength)` — 원소 0..VArrLength(**VArrLength+1 개**).
- **런타임 동작**: 원소·바이트마다 "값이 0 이면 0x0D 로" 트리거 1개(플래그 없음 = **1회**). 5원소 = 20트리거.
- **실제 사용 모양**(9맵 9: Mem2 1, Mem1 5, G2R 3 / 그 밖 11):
  - `_0DPatchforVArr(FP,Names[i+1],4)` Mem2 `OnPluginStart.lua:330` — 이름 캐시(사용자판 ItoName)
  - `_0DPatchforVArr(FP,UpCompRet,4)` G2R `main.lua:721` — ItoDec 출력의 NUL 제거
  - `_0DPatchforVArr(FP,PerCostVA,6)` Mem1 `Main.lua:18190` — 조건 블록 안(1회 트리거라 **처음 한 번만** 패치됨, 추측상 의도와 다를 수 있음)
- **eudext 대응**: 없음(이름·숫자 part 가 NUL 을 만들지 않는다). 필요하면 `textfx.patch_nul(epd, n, fill=0x0D)`(설계만).
- **함정**: 1회 트리거라 반복 블록 안에서 한 번만 돈다.

### 5.7 print_utf8_A

- **원본 정의**: DPL:1274.
- **인자**: `print_utf8_A(DB, string)` → 액션 목록. `DB` = `CreateArr` 핸들, 문자열은 4의 배수가 되게 **앞에** D 채움.
- **런타임 동작**: `SetCtrig1X(FP, DB[2], 칸오프셋, 0, SetTo, dword)` 로 CtrigAsm 배열 칸(602칸마다 2칸 건너뜀)에 문자열을 굽는 **액션**을 돌려준다(DPL:1285). 보통 `Trigger2X(…, {CVX(DeadUnitID, id), …, print_utf8_A(Arr, name..pad)})` 로 "조건에 맞는 문자열을 버퍼에 복사" 한다.
- **실제 사용 모양**(9맵 4: Seed 2, Stel 1, ResV 1):
  - `print_utf8_A(HeroNameArr, ColoredName .. string.rep("\x0D", 0x40 - (#ColoredName)))` Seed `MapLogic\CunitSystem.lua:667` (+ 0x40 초과 시 컴파일 중단 검사 661~664)
  - `print_utf8_A(NameArr, Label .. string.rep("\x0D", 0x40 - #Label))` Seed `MapLogic\Marines.lua:631`
  - `print_utf8_A(HTArr, k[3]..string.rep("\x0D",0x40-(#k[3])))` Stel `MapLogic\System.lua:1663` (ResV `System.lua:1138` 같은 줄)
- **eudext 대응**: `display.Pick(index, table, width=0x40)` — 컴파일 시점 문자열 표를 `Db` 로 굽고 런타임 번호로 고른다(복사 없음, 7.3). 번호가 표에 없으면 `default`.
- **함정**: 0x40 초과 시 `string.rep` 음수 → 패딩이 사라져 뒤가 밀림(Seed 가 검사를 붙인 이유). 604 번호 산술(DESIGN 3.9 금지 대상).

### 5.8 DisplaySTRX

- **원본 정의**: DPL:1305.
- **인자**: `DisplaySTRX(arg, ResetTimer=nil)` → 틀 문자열(Lua 문자열).
- **런타임 동작**: DisplayPrint 의 원소 처리와 같고(fwc/hex/V 목록 포함, **VA·WA 분기 없음** → 오류), 대상·출력 대신 `DoActions(FP,{Disabled(DisplayText(StrT))},1)` 로 문자열을 STRx 에 등록한 뒤 틀을 돌려준다(DPL:1412~1419). 호출자는 이 문자열을 다른 액션에 넣는다(같은 글자 = 같은 번호 = 같은 버퍼).
- **실제 사용 모양**(9맵 2):
  - `return DisplaySTRX(Parts)` Seed `MapLogic\MissionObjective.lua:93` → `RotatePlayer({SetMissionObjectivesX(BuildStr(false))}, HumanPlayers, FP)`(같은 파일 103·106·109) — **임무 목표 창의 동적 문자열**
  - `DCountStr = DisplaySTRX({"\x08。\x18˙…",DCount,"\x04/\x06",DCountMAX," \x1C。…"},10)` Stel `MapLogic\System.lua:2123` — 숫자 ResetTimer
- **eudext 대응**: `t = dp.Template(*parts, every=, update_if=)`; `t.string`(액션에 넣을 TrgString), `t.update()`(그 자리에서 다시 쓰기) (7.2).
- **인게임 확인**: 임무 창을 연 채로 값이 바뀔 때 반영되는지(Seed 주석은 "창을 열 때 읽는다"고 봄).
- **함정**: 같은 글자의 다른 틀과 버퍼 공유. 반환 문자열을 수정하면 번호가 달라져 연결이 끊긴다.

### 5.9 딸림 함수

| 함수 | 정의 | 요지 | eudext |
|---|---|---|---|
| `PName(p)` | DPL:1253 | `{"PVA",p}` 표식 | `display.PName(p)` |
| `FixText(PlayerID, Preset)` | CA:57175 | 1 = `0x640B58` 저장(비트 0~3 모으기), 2 = 복원. 9맵 18회, 대부분 UI 블록 앞뒤(DPS `GameDisplay.lua:88`/`2413`, Seed `SeedInfoDisplay.lua:103/125`) | `with dp.pinned():` |
| `Print_13X` | DPL:569 / DF:310 | CCMU 트릭(G8 1.7) | eudplib `f_raise_CCMU(p)` (EP81 `string/cpprint.py:257`) |
| `Print_13_2` | DF:289 | 목록 대상 CCMU(DPS 2, UERE 1) | `f_raise_CCMU` 반복 |
| `print_utf8_2` | DPL:371 | 13번째 줄 상수 굽기(앞 D 채움, 끝 NUL 없음) | 내부 구현 없음(가변 쓰기로 대체) |
| `print_utf8` | PU:98 | 채팅 줄 상수 + NUL (DPS 66, UERE 12) | `dp.show_line13(…)` 또는 `chat` 모듈(S6) |

---

## 6. 사용 빈도 (SCAN, 주석 제외)

### 6.1 호출 수

| 함수 | DPS | Seed | Stel | ResV | Mem2 | Mem1 | G2R | UERE | Brz | 9맵 합 | 그 밖 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DisplayPrint | 316 | 33 | 18 | 38 | 14 | 15 | 6 | 15 | 15 | **470** | 28 |
| DisplayPrintEr | 69 | 1 | 1 | 4 | 3 | · | · | 15 | 4 | **97** | 3 |
| DisplayPrintTbl | 83 | 1 | · | 12 | · | · | · | · | · | **96** | 0 |
| DisplaySTRX | · | 1 | 1 | · | · | · | · | · | · | 2 | 0 |
| DP_Start_init / init_Setting | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 9 / 9 | 4 / 4 |
| _0DPatchforVArr | · | · | · | · | 1 | 5 | 3 | · | · | 9 | 11 |
| print_utf8_A | · | 2 | 1 | 1 | · | · | · | · | · | 4 | 0 |
| PName | 9 | 4 | 4 | 11 | 3 | 14 | · | 7 | 4 | 56 | 5 |
| FixText | 2 | 4 | 2 | 2 | · | 2 | · | 4 | 2 | 18 | 8 |
| print_utf8 | 66 | · | · | · | · | · | · | 12 | · | 78 | 54 |

(Tpl 은 전부 0. "그 밖" 은 R1 0절의 구판·시험 맵.)

### 6.2 DisplayPrint 대상 × 맵

| 대상 | DPS | Seed | Stel | ResV | Mem2 | Mem1 | G2R | UERE | Brz | 합 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V 로컬 `LCP` (T4) | 197 | | | | | | | | | 197 |
| 목록 `HumanPlayers` (T7, 관전자 포함) | | 24 | 17 | 21 | 14 | 14 | 5 | 10 | 3 | 108 |
| V 공유 (T3: `GCP` 89, `UpgradeCP` 12, `OCU_CP` 3, `GivePrevP/GiveNextP` 4, 그 밖 2) | 89 | 4 | | 7 | | | 1 | 2 | 7 | 110 |
| 루프 상수 `i`, `i-1` (T2) | 9 | | | 9 | | | | 3 | 4 | 25 |
| `Force1` (T6) | 13 | 4 | | | | | | | 1 | 18 |
| `AllPlayers` (T6) | 7 | | | | | | | | | 7 |
| 상수 `0` (T1) | | 1 | 1 | 1 | | | | | | 3 |
| 지역 매개변수 `CP` (T2) | 1 | | | | | | | | | 1 |
| 목록 리터럴 `{P1..P5}` (T7) | | | | | | 1 | | | | 1 |

DisplayPrintEr 대상: `GCP` 68, 루프 `i` 16(DPS 1·ResV 2·UERE 9·Brz 4), `MapPlayers` 7(ResV 2·Mem2 3·UERE 2), 지역 `CP` 4(UERE), V 2(Seed `SetupAuthorityPlayer`, Stel `CurrentOP`).

### 6.3 원소 × 맵 (DisplayPrint)

| 원소 | DPS | Seed | Stel | ResV | Mem2 | Mem1 | G2R | UERE | Brz | 합 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 문자열 리터럴 | 1003 | 58 | 31 | 59 | 41 | 17 | 18 | 38 | 34 | 1299 |
| 문자열 연결식(`..`) | 35 | 18 | 10 | 17 | 1 | 1 | | | | 82 |
| `StrDesign(…)` | 2 | 3 | | | | | | | | 5 |
| V (배열 원소 `x[i]` 포함) | 262 | 32 | 19 | 25 | 24 | | 8 | 16 | 19 | 405 |
| V 임시식(`_Add`, `_Mul` …) | 13 | | | | | | | | | 13 |
| V + fwc | 4 | 1 | | | | | | 3 | | 8 |
| 숫자 = 변수 번호 `x[2]` | 362 | | 7 | 12 | 1 | | 4 | 3 | | 389 |
| PName 상수 | | 1 | 4 | 9 | 3 | 14 | | 5 | 2 | 38 |
| PName V (`{"PVA",v}` 직접 1 포함) | 3 | 3 | | 2 | | | | | 2 | 10 |
| PName 로컬 | 2 | | | | | | | | | 2 |
| W | 17 | | | | | 1 | | | | 18 |
| W 임시식 | 2 | | | | | | | | | 2 |
| `PVWArrX(…)`(VA/WA) + `PVdata[..]` | 22 | | | | | | | | | 22 |
| VA | | 3 | | | | | | | | 3 |
| V 목록 / 배열 통째 | | 2 | | | | 1 | 2 | | | 5 |
| 함수 원소 `{SetNumX…}` 등 | 147 | | | | | | | | | 147 |
| 맨 함수 원소 | | 2 | 2 | 1 | | | 1 | | | 6 |
| `table.unpack(…)` | | | | | | 12 | | | | 12 |
| 추적 못 한 식별자·식 | 83 | 15 | 2 | 3 | 4 | | | 2 | 2 | 111 |
| 원소 표 자체가 변수(`arg` = `TxtArr`/`Parts` 등) | 1 | 3 | | | | | | | | 4 |

함수 원소 세부(DisplayPrint): `SetNumX` 62, `SetEPerSTRX` 46, `SetNumX128` 32, `SetNumX256` 3, `dpletter2` 2, `GaugeBar` 2.

### 6.4 원소 종류 조합 상위 (DisplayPrint)

`V + 문자열` 155 (DPS 109) · `문자열만` 41 · `SetNumX + 문자열` 22 · `PName + 문자열` 18 · `V + SetEPerSTRX + 문자열` 16 · `SetEPerSTRX + 문자열` 14 · `SetNumX128 + 문자열` 12 · `PVWArrX + 문자열` 10 · `V + W + 문자열` 9 · `V + 문자열 + 숫자` 9 · `PName + V + 문자열` 9.
→ **한 호출 안의 동적 원소는 대부분 1~3개**이고, 32비트 V 가 압도적이다.

### 6.5 추가 인자

| 인자 | 사용 |
|---|---|
| DisplayPrint `ResetTimer` = V | DPS 120 (전부 `iv.Time5`) |
| DisplayPrint `ResetTimer` = 숫자 | Stel 1 (`5`, `System.lua:2917`) |
| DisplayPrint `SoundRepeat` | Seed 1(`WavArr`, `OneClickUpgrade.lua:181`), Stel 1, Mem1 9 |
| DisplayPrint `FixTextPreset` | Brz 1 (`3`, `Interface.lua:699`) |
| DisplayPrintTbl `ResetTimer` | DPS 21 (`iv.Time5`) |
| DisplayPrintTbl `UTF8OptionOff` | Seed 1, ResV 4 |
| DisplaySTRX `ResetTimer` | Stel 1 (`10`) |

---

## 7. eudext API 확정안

### 7.1 원칙

1. **로컬 한 번 서식**: `dp.show` 는 "이 PC 의 플레이어(`f_getuserplayerid()`)가 대상에 있으면" 로컬 분기에서 한 번만 서식을 만들고 DisplayText 한다. 대상마다 버퍼를 다시 쓰지 않는다(DESIGN 4.7 위험 항목 해결).
   원본과 보이는 결과는 같다: 원본도 버퍼 내용은 대상과 무관하고 DisplayText 가 CP 로 걸러질 뿐이다.
2. **호출 자리마다 버퍼 한 개**(StringBuffer). 용량 = part 들의 최대 길이 합(각 part 는 dword 경계까지 0x0D 로 채워지므로 4의 배수로 올림, EP81 `memio/cpbyterw.py:50~72`). DPL 의 "호출마다 틀 하나" 와 같은 수다. `every=`/`update_if=` 가 버퍼를 유지하려면 호출 자리 버퍼가 필요하다.
3. **CP 복구**(DESIGN 3.6-4). 원본은 CP 를 대상·FP 로 남기지만 eudext 는 되돌린다 — 옮긴 코드가 그 CP 에 기대면 명시적으로 `f_setcurpl` 해야 한다(9절).
4. **로컬 오염 허용 구역**: 서식 scratch 버퍼·StringBuffer·TBL 메모리·13번째 줄은 PC 마다 내용이 달라도 된다(게임 상태 아님). 이 구역을 공유 로직이 읽지 않게 문서화한다(G8 1.6 과 같은 논리).
5. **공유 동작은 공유 조건으로**: `show_line13` 의 CCMU, `hold=` 액션은 모든 PC 에서 같은 조건으로 돈다. 로컬 조건 블록 안에서 `show_line13` 을 부르면 빌드 때 경고(가능한 범위, DESIGN 3.7).
6. 맨 `EUDVariable` 은 **부호 있는 10진**으로 찍는다(DPL V 원소와 같음, 405회 사용). 부호 없는 값은 `Dec(v)` 로 명시. (eudplib `{}` 는 부호 없음 — 9절)

### 7.2 `eudext.display`

```python
from eudext import display as dp
from eudext.display import PName, LocalName, Byte, Bytes, Pick, Part
from eudext.numfmt import Dec, Hex, Man, Per, Gauge

dp.show(target, *parts, sound=None, every=None, update_if=None, pin=False)
    # DisplayPrint. target: 7.6. sound: WAV 이름 또는 목록(대상 PC 에서 PlayWAV).
    # every=N: N 프레임마다 버퍼 갱신(표시는 매 프레임). update_if=Condition: 조건이 참일 때만 갱신.
    # pin=True: 이 출력 앞뒤로 0x640B58 저장·복원 (FixTextPreset=3).
dp.LOCAL                                   # 대상: 모든 PC 가 각자 자기 화면에 (DPS LCP 관용구)
with dp.pinned():                          # FixText(1) ... FixText(2) 블록판. 안의 dp.show 가 매 프레임 같은 줄에 찍힌다
    ...

dp.show_line13(target, *parts, hold=None)
    # DisplayPrintEr. target: 상수 0~7 | 변수 | 목록 (관전자 불가 — 원본과 같음).
    # 공유: 대상마다 f_raise_CCMU(p) [+ hold(p) 가 돌려준 액션]. 로컬: 이 PC 가 대상이면 0x641598 에 parts + NUL.
    # hold: None | (unit, value) → SetDeaths(p, SetTo, value, unit)  | callable(p) -> actions
    # 최대 길이(7.1-2 규칙) > 217B 이면 EPError.

dp.set_tbl(tbl_id, *parts, tail=" ", eos=True, every=None, update_if=None, capacity=None)
    # DisplayPrintTbl. 바이트 정확 쓰기(EP81 f_dbstr_print 경로, string/eudprint.py:218). 모든 PC 에서.
    # tail: 끝에 붙일 문자열(None 이면 안 붙임 = UTF8OptionOff). eos=False 면 NUL 을 안 씀(원본 호환).
    # capacity: 자리 크기(바이트). 주면 최대 길이 초과를 컴파일 때 막는다. tbl 파일에서 읽는 도우미는 tools 쪽(설계만).

t = dp.Template(*parts, every=None, update_if=None)
    # DisplaySTRX. t.string → TrgString(DisplayText·SetMissionObjectives·LeaderBoard 이름 등에 넣음)
    # t.update() → 이 자리에서 버퍼 다시 쓰기(모든 PC). every/update_if 를 주면 호출 자리에서 알아서.
```

- `dp.show` 비용 목표: 호출 자리 = 대상 판정 1~3 + 로컬 분기 2 + part 마다 1~3 + 표시 1. 서식 본문(numfmt)은 공용 1벌.
- `players.display`(DESIGN 4.9) = `dp.show` 별칭.

### 7.3 part 종류

| part | 뜻 | 최대 길이 | 원본 |
|---|---|---|---|
| `str` / `bytes` | 컴파일 시점 상수(UTF-8) | 그 길이 | 문자열 원소 |
| `EUDVariable`, `int` 상수 | 부호 있는 10진(가변 길이) | 11 | V 원소 |
| `Int64` | 부호 있는 64비트 10진 | 20 | W 원소 |
| `numfmt.Dec/Hex/Man/Per/Gauge(...)` | 7.4 | 옵션에 따라 | fwc·hex·함수 원소 |
| `PName(p, color="player"|None|int)` | 플레이어 p 의 이름. p = 상수 0~7 / 변수. 이름 주소는 eudplib 과 같은 **0x57EEEB+36p**(EP81 `string/cpprint.py:67`). `color="player"` 면 DPL 색표 {08,0E,0F,10,11,15,16,17}(P8 은 0x17) | 1+26 | PName 원소 |
| `LocalName(color=…)` | `PName(f_getuserplayerid())`. 관전자면 빈 문자열 | 27 | `PName("LocalPlayerID")` |
| `Byte(v)` | v 의 하위 1바이트 한 개(색 코드·글자) | 1 | 숫자 원소(`x[2]`) |
| `Bytes(v1, v2, …)` | 여러 개 | n | V 목록 원소 |
| `Pick(index, table, default="")` | `table`(dict 또는 list: 번호 → 문자열)에서 런타임에 고른 상수 문자열. 표는 `Db` 로 굽고 `EUDArray` 주소표로 찾는다 | 표의 최대 | 맨 함수 원소 + `print_utf8_A` |
| `Part` (기반 클래스) | `fmt()` 가 eudplib 인쇄 가능 객체를 돌려주고 `max_len` 을 가진다. 사용자 확장용 | 사용자 | 함수 원소 일반 |

- `PName` 에 상수 8 이상을 주면 `EPError`, 변수가 런타임에 8 이상이면 **아무것도 안 쓴다**(DPL 은 이전 내용이 남았다).
- part 는 `fmt()` 로 eudplib 에 넘어간다(DESIGN 3.2-7). `f_cpchar_print`(TextFX) 경로에는 `.fmt()` 결과를 넘긴다(DESIGN 4.6 주의).

### 7.4 `eudext.numfmt` 추가분 (DESIGN 4.6 보강)

```python
Dec(v, width=0, fill="\r", sign=None, sign_space=False, max_digits=None, cut_low=0,
    fullwidth=False, colors=None, group=None, glyphs=None)      # DESIGN 4.6 그대로 + sign_space
Hex(v, width=8, lower=False, fill="0")
Man(v, top=2, colors=None, after=None, units="만억조경해자양구간정재극항아나불무", fixed=False)
    # 만 단위(SetNumX 일반화). v: EUDVariable | Int64 (| Int128, WP20)
    # top: 보일 덩어리 수(원본 2). colors=None 이면 색 없음, "dps" 면 4.5-3 표, 또는 (단위별 (색1,색2)) 표
    # after: 덩어리 뒤 색(원본 색 켬 = 0x04). fixed=True 면 4.5 의 18B 배치를 그대로 (numfmt.dp.man18 과 같음)
Per(v, scale=1000, frac=3, max=None, trim=True, int_min=1)
    # SetEPer 일반화: v/scale 을 소수 frac 자리까지, 뒤 0·점 지움(trim), 정수부 최소 1자리
Gauge(n, cells=20, glyph="l", on=0x07, off=0x04)          # GaugeBar (글자당 [색][glyph])

# DisplayPrint 호환 프리셋 — 옛 화면과 바이트까지 같아야 할 때만. 모두 고정 폭, 0x0D 채움 (4.4·4.5)
numfmt.dp.dec16(v)                 # V 원소
numfmt.dp.decfw48(v)               # V.fwc
numfmt.dp.hex12(v)                 # V.hex
numfmt.dp.dec20(x64)               # W 원소 (음수는 0 채움 19자리)
numfmt.dp.name20(p)                # PName 원소 (0x6D0FDC 표, 0→D)  ※ 주소 결정 D13
numfmt.dp.man18(v, color=False)    # SetNumX/TBLX/ErX
numfmt.dp.per8(v, permil=False, tbl=False)   # SetEPerSTRX/TBLX
numfmt.dp.dig2(v)                  # dpletter2
numfmt.dp.gauge40(n)               # GaugeBar(Tbl)
```

- `Man` 알고리즘 권고: 32비트는 10^4·10^8 비교-뺄셈으로 덩어리를 뽑고(나눗셈 없음), 64비트는 단위 판정 4개(만·억·조·경, 2^64 < 10^20) + `i64` 나눗셈 2회. 128비트 이상은 WP20 뒤.
- 원본 근사(4.5-7)는 따라 하지 않는다 — `man18` 도 정확한 값을 쓴다(기대값이 다를 수 있는 구간은 10^40 이상뿐).

### 7.5 원소 → API 대응표

| DPL 원소 (2.1 #) | 옛 코드 | eudext |
|---|---|---|
| 3 문자열 | `"\x07HP "` | `"\x07HP "` |
| 3 StrDesign | `StrDesign("…")` | `strdesign.design("…", style=…)` (S7) |
| 7 V | `v`, `_Add(a,b)` | `v`, `a + b` |
| 8 VA | `VArr(arr,i)`, `PVWArrX(x)` | `arr[i]` (EUDArray/EUDVArray 읽기) |
| 5 V.fwc | `v.fwc=true; …v…` | `Dec(v, fullwidth=True)` |
| 6 V.hex | `v.hex=true` | `Hex(v)` |
| 9·10 W/WA | `w`, `WArr(…)` | `Int64` / `Int64Array[i]` |
| 4 PName | `PName(3)`, `PName(v)` | `PName(3)`, `PName(v)` |
| 4 PName 로컬 | `PName("LocalPlayerID")` | `LocalName()` |
| 12 숫자 | `TxtColor[2]`, `CTimeDDArr[1][2]` | `Byte(TxtColor)`, `Byte(ctime_dd[0])` |
| 11 V 목록 | `hondondisplay`(4칸) | `Bytes(*hondondisplay)` — 새 코드는 `"ON"`/`"OFF"` 를 `Pick(mode, {0:"\x04OFF", 1:"\x08ON"})` |
| 1 맨 함수 | `HeroTextFunc` + `print_utf8_A` | `Pick(unit_id, {id: colored_name, …})` |
| 2 `{SetNumX, v, 1}` | 만 단위 + 색 | `Man(v, colors="dps", after=0x04)` (바이트 호환: `numfmt.dp.man18(v, color=True)`) |
| 2 `{SetNumX128, {lo,hi}}` | 128비트 | `Man(Int128(...))` (WP20 뒤) |
| 2 `{SetEPerSTRX, v}` | 확률 | `Per(v, max=100000)` |
| 2 `{SetEPerSTRX, v, 1}` | 퍼밀 | `Per(v, max=5000000)` |
| 2 `{dpletter2, v}` | 두 자리 | `numfmt.dp.dig2(v)` (원본은 100 이상에서 아래 두 자리를 `0` 채움으로 찍는다). 새 코드는 `Dec(v, width=2, fill="\r")` |
| 2 `{GaugeBar, v}` | 막대 | `Gauge(v)` |
| 2 `{SetNumErX, v, 1}` | 13번째 줄 만 단위 | `dp.show_line13(p, …, Man(v, colors="dps", after=0x04), …)` |
| `table.unpack(t)` | 펼침 | `*t` |

### 7.6 대상 → API 대응표

| 3절 | 옛 코드 | eudext | 로컬 판정 |
|---|---|---|---|
| T1 | `0`, `P1` | `0`, `P1` | `userp == 0` |
| T1 관전자 | `P9`…`P12` | `P9`…`P12` 또는 `players.Observers` | `userp == 128+k` |
| T2 | `i` (Lua 루프) | 파이썬 루프 변수(상수) | 상수 비교 |
| T3 | `GCP` (V) | `EUDVariable` | `userp == v` |
| T4 | `LCP` (로컬 V) | `dp.LOCAL` | 항상 참 |
| T5 | `CurrentPlayer`, `"CP"` | `CurrentPlayer` | `IsUserCP()` (EP81 `eudlib/utilf/userpl.py:27`) |
| T6 | `Force1`…`Force4`, `AllPlayers` | 같은 이름(eudplib `TrgPlayer`) | 컴파일 시점 표: `GetPlayerInfo(p).force`(EP81 `core/mapdata/playerinfo.py:61`) — **TEP SetForces 표와 다를 수 있음** |
| T6 | `Force5`, `EveryPlayers` | `players.Observers`, `players.Everyone` | 상수 집합 |
| T7 | `HumanPlayers` 표 | `list`/`tuple`, `players.Humans` | 상수 집합(4개 이하는 OR 조건, 그 이상은 256B 표 조회 — 구현 선택) |

- 대상이 상수 집합이면 호출 자리 비용은 "집합 판정 1~2트리거". 변수가 섞인 목록은 원소마다 비교.
- `show_line13` 은 T1·T2·T3·T7(0~7 만)만 받는다. `dp.LOCAL` 은 `players.Humans` 로 바꿔 쓰라고 오류 메시지로 안내.

### 7.7 옛 코드 옮기기 예

```python
# ResV CallTriggers.lua:10
# DisplayPrint(GiveNextP, {"\x12\x07『 ",PName(GivePrevP),"\x04에게 \x1F",GiveMin," Ore\x04를 기부받았습니다.\x02 \x07』"})
dp.show(give_next_p, "\x12\x07『 ", PName(give_prev_p), "\x04에게 \x1F", give_min, " Ore\x04를 기부받았습니다.\x02 \x07』")

# DPS GameDisplay.lua:107 (ResetTimer = iv.Time5 → update_if)
dp.show(Force1, "\x07보유금액 \x04: ", Man(money, colors="dps", after=0x04), " \x04원\x12\x07사냥터 \x1B",
        numfmt.dp.dig2(income), " / \x19", numfmt.dp.dig2(income_max), update_if=time5.Exactly(0))

# DPS crystal.lua:307
dp.show_line13(gcp, "\x07『 \x1F은\x1C하\x1D의 \x1E조\x02각\x04을 ", Man(cost, colors="dps", after=0x04),
               "\x04개 소모하여 \x07강화하였습니다. \x07』")

# DPS TBL.lua:968 (플레이어별 툴팁)
for j in range(7):
    dp.set_tbl(personal_uid[j] + 1, "\x08\x07『 \x19진 \x07각성 \x07", numfmt.dp.man18(awak[j], color=True),
               "\x07단. ", PName(j), " \x07』", every=None)

# Seed MissionObjective.lua:93
t = dp.Template("\x13", MAP_TEXT, "\n", diff_label, …, map_seed, "\n", …)
DoActions([SetMissionObjectives(t.string)])   # 대상 CP 는 players.run_as 로
```

### 7.8 epScript

```js
import eudext.display as dp;
import eudext.numfmt as nf;

function afterTriggerExec() {
    dp.show(dp.LOCAL, "\x07HP ", hp, " / ", nf.Man(gold, colors="dps", after=0x04));   // 키워드 인자 번역됨 (DESIGN 3.11)
    dp.show_line13(P1, "\x08ERROR \x04: 골드 부족");
}
```
(`dp.show` 는 파이썬 함수라 `f_` 접두사 규칙(DESIGN 3.1)에 따라 실제 정의는 `f_show`, 별칭 `show`. epScript 에서 `dp.show(...)` 는 `dp.f_show(...)` 로 번역된다.)

---

## 8. 시험

### 8.1 기대값 (REF — DPL·CA·CONV 줄을 그대로 옮긴 파이썬 모델, `s3_ref_out.txt`)

`numfmt.dp.*` 는 아래와 **바이트 단위로 같아야** 한다. 에뮬레이터에서 대상 주소를 읽어 비교한다.

**dec16** (`Call_IToDec`, 4.4)

| 입력 | 16B | 보이는 글 |
|---|---|---|
| 0 | `0D×15 30` | `0` |
| 5 | `0D×15 35` | `5` |
| 10 | `0D×14 31 30` | `10` |
| 12345 | `0D×11 31 32 33 34 35` | `12345` |
| 999999999 | `0D×7 39×9` | `999999999` |
| 1000000000 | `0D×6 31 30×9` | `1000000000` |
| 2147483647 | `0D×6 32 31 34 37 34 38 33 36 34 37` | `2147483647` |
| 0x80000000 | `0D×5 2D 32 31 34 37 34 38 33 36 34 38` | `-2147483648` |
| 0xFFFFFFFF | `0D×5 2D 0D×9 31` | `-1` |
| 0xFFFFFFF6 | `0D×5 2D 0D×8 31 30` | `-10` |

**decfw48** (`Call_IToDecX`): 0 → `0D×45 EF BC 90`(`０`), 1234 → `0D×33 EF BC 91 0D EF BC 92 0D EF BC 93 0D EF BC 94`(`１２３４`), 4294967295 → `0D×9 EF BC 94 0D EF BC 92 … 0D EF BC 95`(`４２９４９６７２９５`, 음수 처리 없음).

**hex12**: 0 → `0D×4 30×8`, 0xABCDEF → `0D×4 30 30 41 42 43 44 45 46`, 0xFFFFFFFF → `0D×4 46×8`.

**dec20** (`Call_lIToDec`)

| 입력(부호 있는 64비트) | 20B | 보이는 글 |
|---|---|---|
| 0 | `0D×19 30` | `0` |
| 12800000000 | `0D×9 31 32 38 30×8` | `12800000000` |
| 10^18 | `0D 31 30×18` | `1000000000000000000` |
| 2^63−1 | `0D 39 32 32 33 33 37 32 30 33 36 38 35 34 37 37 35 38 30 37` | `9223372036854775807` |
| −5 | `2D 30×18 35` | `-0000000000000000005` |
| −2^63 | `2D 39 32 32 33 33 37 32 30 33 36 38 35 34 37 37 35 38 30 38` | `-9223372036854775808` |

**man18** (`SetNumX`, `<xx>` = 색 코드)

| 입력 | 색 | 18B | 보이는 글 |
|---|---|---|---|
| 0 | 켬 | `03 0D 0D 0D 30 0D×13` | `<03>0` |
| 0 | 끔 | `0D 0D 0D 0D 30 0D×13` | `0` |
| 7 | 켬 | `0D×9 03 0D 0D 0D 37 04 0D 0D 0D` | `<03>7<04>` |
| 10000 | 켬 | `1C 0D 0D 0D 31 04 EB A7 8C 0D×9` | `<1C>1<04>만` |
| 12345678 | 켬 | `1C 31 32 33 34 04 EB A7 8C 03 35 36 37 38 04 0D 0D 0D` | `<1C>1234<04>만<03>5678<04>` |
| 12345678 | 끔 | `0D 31 32 33 34 0D EB A7 8C 0D 35 36 37 38 0D 0D 0D 0D` | `1234만5678` |
| 100050000 | 켬 | `1D 0D 0D 0D 31 04 EC 96 B5 1C 0D 0D 0D 35 04 EB A7 8C` | `<1D>1<04>억<1C>5<04>만` |
| 123456789012 | 켬 | `1D 31 32 33 34 04 EC 96 B5 1C 35 36 37 38 04 EB A7 8C` | `<1D>1234<04>억<1C>5678<04>만` |
| 123456789×10^12 | 켬 | `15 0D 0D 0D 31 04 ED 95 B4 1B 32 33 34 35 04 EA B2 BD` | `<15>1<04>해<1B>2345<04>경` |
| 2^64−1 | 켬 | `1B 31 38 34 34 04 EA B2 BD 19 36 37 34 34 04 EC A1 B0` | `<1B>1844<04>경<19>6744<04>조` |

**per8** (`SetEPer`, 1/1000 단위)

| 입력 | 퍼밀 | 8B | 보이는 글 |
|---|---|---|---|
| 0 | 아님 | `0D 0D 0D 30 0D 0D 0D 0D` | `0` |
| 1 | 아님 | `0D 0D 0D 30 2E 30 30 31` | `0.001` |
| 500 | 아님 | `0D 0D 0D 30 2E 35 0D 0D` | `0.5` |
| 12500 | 아님 | `0D 0D 31 32 2E 35 0D 0D` | `12.5` |
| 12050 | 아님 | `0D 0D 31 32 2E 30 35 0D` | `12.05` |
| 150000 | 아님 | `0D 31 30 30 0D 0D 0D 0D` | `100` (최대로 자름) |
| 5000000 | STR | `35 30 30 30 0D 0D 0D 0D` | `5000` |
| 1234567 | STR | `31 32 33 34 2E 35 36 37` | `1234.567` |

**dig2**: 0 → `0D 30`, 5 → `0D 35`, 42 → `34 32`, 100 → `30 30`, 105 → `30 35`.
**gauge40**: 0 → `(04 6C)×20`, 3 → `(07 6C)×3 (04 6C)×17`, 25 → `(07 6C)×20`.
**name20**: P1 이름 `GALAXY_BURST`, 색 0x08 → `0D 0D 0D 08 47 41 4C 41 58 59 5F 42 55 52 53 54 0D 0D 0D 0D`.
**er_layout**, **tbl_layout**: 4.2, 4.3 끝.

REF 자체의 확인: dec16/decfw48/hex12/dec20 배치는 TXT(DPS 이식 계층, TXT:163~330)의 배치 주석·초기값과 같다. man18/per8 은 CONV 를 줄 단위로 옮겼다(REF docstring 에 줄 번호). 원본 트리거를 직접 돌린 비교는 하지 못했다(11절).

### 8.2 에뮬레이터 시험 항목 (`tests/t_display.py`, `tests/t_numfmt.py`)

1. `numfmt.dp.*` × 경계값(0, 9, 10, 10^k±1, 2^31±1, 2^32−1, Int64 경계) × 무작위 2만 개 — REF 와 바이트 비교.
2. `Man/Per/Dec/Hex` 가변 판 — 파이썬 참조(`format`, REF 의 보이는 글)와 문자열 비교(0x0D 제거 후).
3. `dp.show` — DisplayText 캡처 모델(DESIGN 5.1)에 "이 PC 의 플레이어 번호"를 0~7·128 로 바꿔 가며: 대상별로 DisplayText 가 **정확히 한 번** 생기는지, 버퍼 내용, 호출 뒤 CP 가 호출 전과 같은지.
4. `every=N` — N 프레임 동안 버퍼가 그대로이고 표시는 매 프레임인지. `update_if` 도 같음.
5. `show_line13` — 공유 액션(CCMU: 0x628438 ← 0, CreateUnit, 복원)이 **이 PC 번호와 무관하게** 같은 순서로 도는지, 로컬 쓰기는 대상 PC 에서만, 0x641598 부터 parts + NUL, 217B 초과 컴파일 오류.
6. `set_tbl` — `GetTBLAddr` 모의(0x6D5A30 값) 위치에 바이트 정확 쓰기, tail/eos 조합 4가지, `capacity` 초과 오류.
7. `Pick` — 표에 있는 번호/없는 번호/경계.
8. `PName` — 변수 값 8 이상에서 아무것도 안 쓰는지.

### 8.3 인게임 확인 항목 (`docs/INGAME_CHECKLIST.md` 에 옮길 것)

1. `dp.show(players.Humans, …)` 가 관전자(128~131) 화면에도 뜨는지. `dp.LOCAL` 이 관전자에게 뜨는지.
2. `with dp.pinned():` 안의 여러 줄 UI 가 매 프레임 같은 줄에 고정되는지, 사용자 채팅이 끼면 어떻게 되는지.
3. `show_line13`: CCMU 뒤 글자가 보이는지, 유닛이 1700 가득일 때(0x628438=0)도 보이는지, `hold=` 가 UERE 식 잠금으로 동작하는지.
4. `set_tbl`: NUL 을 쓰는 방식(eos=True)에서 버튼 툴팁이 정상인지, 원래보다 짧게 쓸 때 뒤 잔재가 없는지, U+2009 를 빼면 어떻게 보이는지.
5. `PName` 이 0x57EEEB 에서 읽은 이름과 DPL(0x6D0FDC) 캐시가 같은지(클랜 태그·긴 한글 이름 포함).
6. `Template` 을 `SetMissionObjectives` 에 물렸을 때, 창을 연 채로 값이 바뀌면 반영되는지.
7. 0x0D 채움 고정 폭(`numfmt.dp.*`)이 옛 맵과 같은 위치에 보이는지(SC:R 글꼴).
8. 옛 UERE `PName(V)` Er 경로(4.2-4-4)가 실제로 틀린 이름을 찍는지(옮길 때 고칠지 판단용).

---

## 9. 함정

1. **CP**: 원본은 CP 를 대상(V)·FP 로 남긴다. eudext 는 복구한다 → 옮긴 코드가 "DisplayPrint 뒤 CP = 대상" 에 기대면(원본 코드 중 `DisplayPrint(GCP,…)` 뒤 `TSetMemory(0x6509B0,…)` 없이 CP 액션을 쓰는 곳) 깨진다. 옮길 때 CP 를 명시.
2. **부호**: DPL V 는 부호 있음, eudplib `{}`/`f_dbstr_adddw` 는 부호 없음. `dp.show` 의 맨 변수는 부호 있음(7.1-6), `f_sprintf` 에 같은 변수를 넣으면 부호 없음 — 문서에 나란히 적는다.
3. **Force 표 출처**: CtrigAsm `CForce1..4` 는 TEP `SetForces` 인자, eudplib 는 맵 FORC. 둘을 다르게 둔 맵이면 대상이 달라진다.
4. **관전자**: eudplib `EUDPlayerLoop` 는 0~7 만 돈다(EP81 `eudlib/utilf/pexist.py:124~140`). 관전자 대상은 `f_getuserplayerid()` 비교로만 처리한다(0x512684 는 1바이트로 읽음, EP81 `userpl.py:19`).
5. **로컬 값**: `dp.LOCAL` 과 로컬 변수 part 는 표시 전용. part 안의 계산(예: `Man(Int64)` 의 나눗셈)은 로컬 분기에서만 돈다 → 그 계산이 쓰는 공용 작업 변수를 공유 로직이 **먼저 쓰지 않고 읽으면** 디싱크(DESIGN 3.7). numfmt 는 전용 scratch 만 쓴다.
6. **StringBuffer 는 로컬에서만 쓴다**(EP81 `string/strbuffer.py:258~271` `_cpblock`). `Template.update()` 와 `set_tbl` 은 모든 PC 에서 써야 하므로 StringBuffer 의 쓰기 메서드를 쓰지 말고 `f_dbstr_print`/바이트 쓰기로 직접 쓴다.
7. **dword 채움**: `f_cpstr_print` 는 항목마다 dword 경계까지 0x0D 를 채운다 → 표시에는 무해하지만 **바이트 위치가 필요한 곳(TBL·Template 의 고정 폭)** 에는 쓰지 않는다.
8. **13번째 줄 길이**: 한 줄 218B. eudplib `f_eprintln` 은 길이 검사가 없다 → `show_line13` 이 컴파일 시점에 막는다(7.2).
9. **TBL 자리 크기**: 원본도 검사하지 않았다. `capacity` 를 모르면 넘침을 막을 수 없다.
10. **틀 공유**: DPL 은 같은 글자의 틀끼리 버퍼를 공유했다. eudext 의 StringBuffer 는 `ForceAddString` 으로 **공유하지 않는다**(EP81 `strbuffer.py:114`) → 원본에서 우연히 공유되던 동작(두 호출이 같은 버퍼를 보는 것)을 기대한 코드는 없다고 본다(추측).
11. **fwc 영구 플래그·숫자 원소=변수 번호·VA 무시(Tbl)·맨 함수 오류(Er)**: 옮길 때 원소를 하나씩 7.5 표로 바꾼다. 자동 번역기는 이 넷을 경고해야 한다.
12. **`Man` 128비트 이상**: 원본은 10^40 이상에서 근사다(4.5-7). 옛 화면과 다른 숫자가 나와도 eudext 가 맞다.
13. **ResetTimer 숫자형**: 원본은 호출마다 전역 `ResetTimerCode` 를 새로 만들어 덮는다(DPL:186) — 호출 자리별 카운터라 동작엔 문제없지만 Ccode 를 하나씩 쓴다. eudext `every=` 는 호출 자리별 `EUDLightVariable` 하나.

---

## 10. DESIGN.md 수정 제안

1. **4.7 API 교체**: 7.2 의 서명으로 바꾼다 — `dp.show(target, *parts, sound=, every=, update_if=, pin=)`, `dp.LOCAL`, `dp.pinned()`, `dp.show_line13(target, *parts, hold=)`, `dp.set_tbl(tbl_id, *parts, tail=" ", eos=True, every=, update_if=, capacity=)`, `dp.Template(...).string/.update()`.
   parts 목록을 7.3 으로 교체(`Byte`, `Bytes`, `Pick`, `LocalName`, `Part` 추가, `PColor` 는 `PName(color=)` 로 흡수).
2. **4.7 의미 절**: "내부는 StringBuffer + f_sprintf + EUDPlayerLoop" 를 "로컬 판정 1회 + 호출 자리 StringBuffer(`f_cpstr_print`) + DisplayText" 로 고친다. `EUDPlayerLoop` 는 관전자를 돌지 않아 쓰지 않는다(9-4).
3. **4.6 numfmt**: `Man`, `Per`, `Gauge`, `sign_space` 를 추가하고, `numfmt.dp` 호환 프리셋 9개(7.4)를 넣는다. `group=(4, ("만","억","조"))` 초안은 `Man` 으로 대체(원본은 "위 두 덩이만" 규칙이라 group 과 뜻이 다르다).
4. **3.2-7 / 4.7**: "표시 함수의 맨 EUDVariable 은 부호 있는 10진" 을 명시(7.1-6). → 7절 결정 **D15** 로 올린다.
5. **3.6 CP**: display 계열이 원본과 달리 CP 를 복구한다는 것을 "옮길 때 주의" 로 한 줄.
6. **4.9 players**: `players.Observers`(128~131), `players.Everyone`, 목록 대상의 로컬 판정 도우미(`players.contains_user(targets)` — 7.6)를 display 가 쓴다. WP6 선행에 WP8 이 이미 있으니 이 도우미를 WP8 완료 조건에 넣는다.
7. **6.1 WP6 추가 완료 조건**: "`numfmt.dp.*` 가 `docs/spec/S3` 8.1 기대값과 바이트 일치, `s3_ref.py` 를 `tests/ref_dp.py` 로 옮겨 무작위 차등" 을 넣는다. WP5 에도 `Man/Per` 차등.
8. **7절 결정 추가**:
   - **D13** 이름 주소: `PName` 을 0x57EEEB(eudplib·IsPName 과 같음)로 할지 0x6D0FDC(DPL·CA `ItoName`)로 할지 — 권장 0x57EEEB, `numfmt.dp.name20` 만 0x6D0FDC. 인게임 8.3-5 로 확인.
   - **D14** TBL 끝 NUL: 권장 `eos=True`(eudplib 과 같음), 원본 호환은 `eos=False`. 인게임 8.3-4.
   - **D15** 표시용 맨 변수 부호: 권장 "부호 있음"(DPL 호환).
9. **0.2 표**: "서식 있는 출력(DisplayPrint) 9맵 696" 옆에 "원소는 문자열·V·1바이트 변수가 95%" 를 덧붙여 WP6 1차 범위(문자열·V·Int64·PName·Byte·Man·Per)를 좁힌다. `Hex` 는 사용 0 이라 2차.
10. **8절 표**: "DisplayPrint 원소·대상 전수, 고정 길이 규칙, 기대값" → `docs/spec/S3_display.md` 행 추가.

---

## 11. 미확인

1. **0x6D0FDC 와 0x57EEEB 의 이름이 늘 같은지**(G8 6-1, R4b D1). 싱글·리플레이·관전자 슬롯 포함.
2. **TBL 에 NUL 을 써도 툴팁이 정상인지**, U+2009 가 왜 필요한지(eudplib `f_settbl` 도 붙인다 — EP81 `string/tblprint.py:48~63`). 원본은 NUL 을 안 썼다.
3. **CP 128~131 로 DisplayText 할 때 관전자에게 보이는지** — CtrigAsm 이 그렇게 만든다는 것(CA:392~396)만 확인했다.
4. **DPS `LCP` 가 관전자 PC 에서 0 인지**(`iv.LCP` 초기값·관전자 경로) — 그렇다면 DPS 의 197회 출력은 관전자에게 안 보였다.
5. **UERE 유닛 15 데스(OP_Hold)를 줄이는 코드** — `LevelUp.lua:268`, `Operator.lua:367,372` 에서 5000 을 넣는 것만 찾았다. 줄이는 곳(타이머)은 못 찾았다.
6. **UERE `PName(V)` Er 경로가 실제로 틀린 이름을 찍는지**(4.2-4-4) — 코드상 `VtoNameV` 를 안 채우므로 직전 값이 쓰인다고 판단.
7. **REF 와 원본 트리거의 직접 대조** — DPL 서브루틴은 CtrigAsm 내부(SetCtrig1X·CallLabelAlways)라 이번에 돌리지 못했다. REF 는 Lua 줄을 옮겼고 TXT 와 배치가 같다는 것까지만 확인. man18 의 128비트 이상 근사는 계산상 추측.
8. **정의를 추적하지 못한 원소 식별자·식 132개**(DP 111 · Er 9 · Tbl 12)의 실제 종류 — 대부분 함수 매개변수로 보인다(예: DPS `TitleStr`, `StatVar`). 문자열/V 비율은 조금 달라질 수 있다.
9. **Mem1 `ExScoreP` 통째 전달**(2.3)이 버그인지 의도인지.
10. **GaugeBar 틀 이중 삽입**(4.1)이 화면에서 어떻게 보이는지 — 코드로는 뒤 원소가 앞으로 당겨진다.
11. **eudplib 0.81 에서 `GetPlayerInfo(p).force` 가 Force 번호를 0부터 세는지 1부터 세는지**(구현 때 확인).
12. **SC:R 에서 DisplayText 문자열 길이 한계**(틀이 218B 를 넘는 DPS 호출이 있는지 — DPS `Interface.lua:395` 는 `\n` 으로 여러 줄) — 줄 단위로 나뉘는지 확인 못 함.
