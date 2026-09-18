# S7 — StrDesign 명세 (`eudext.strdesign`)

작성 2026-09-17. 조사·명세만 했고 코드는 만들지 않았다. 근거는 `파일:줄`, 확인 못 한 것은 "(추측)".
원본 Lua 함수는 **lupa(lua54)로 직접 돌려** 기대 출력을 뽑았고, 파이썬 참조 구현과 156건 모두 일치했다(5절).

## 약어

| 약어 | 파일 |
|---|---|
| L322 | `ScmDraft 2\MapSource\Library\LibraryFor322.lua` |
| Tpl | `C:\Users\whatd\Documents\MSF-Template\func.lua` |
| Seed | `ScmDraft 2\theSeed\Engine\func.lua` |
| Stel | `ScmDraft 2\Stella_II\Engine\func.lua` |
| ResV | `ScmDraft 2\MSF_Respect_V\func.lua` |
| Mem2 | `ScmDraft 2\MapSource\MSF_Memory_2\func.lua` |
| SCAN7 | `…\scratchpad\spec_s3\s7_scan.py` → `s7_report.txt` (사용 맥락·로드 순서) |
| SCAN | `…\scratchpad\spec_s3\s3_scan.py` → `s3_report.txt` (호출 수) |
| LUPA | `…\scratchpad\spec_s3\s7_lupa.py` → `s7_lupa_out.json` (원본 실행 결과 + 파이썬 비교) |

맵 약칭은 R1 0절과 같다(DPS·Seed·Stel·ResV·Mem2·Mem1·G2R·UERE·Brz·Tpl).

---

## 0. 한눈에

- StrDesign 은 **컴파일 시점 문자열 꾸미기**다. 트리거를 만들지 않고, 입력 문자열 앞뒤에 정해진 장식 바이트를 붙일 뿐이다: `StrDesign(s) = 앞 .. s .. 뒤`, `StrDesignX(s) = "\x13" .. 앞 .. s .. 뒤`(0x13 = 가운데 정렬).
- **판이 4가지**(장식이 다름): 『 』(L322 — DPS·UERE·Brz·G2R·Mem1 이 씀), 。˙+˚ 빨강(Tpl·Seed·Stel), 。˙+˚ 초록(ResV), ·【 】·(Mem2). Mem2 만 `StrDesign`/`StrDesignX` 앞에 `\r\r` 을 더 붙이고, 그것이 없는 `StrDesignX2` 를 따로 둔다.
- 맵 판이 있는 맵은 **맵 판이 항상 이긴다**(Library 를 먼저 불러오고, 맵 정의보다 먼저 실행되는 최상위 호출이 0건 — SCAN7).
- 사용: 9맵 **899회**(DPS 473) — `DisplayText` 309 · `DisplayTextX` 296 · 변수 대입 207 · `print_utf8` 46 · `DisplayPrintEr` 16 · 리더보드 16 · `DisplayPrint` 6. 판별 부분 표 `StrD = {앞, 뒤}` 를 Seed·Stel·ResV 가 96회 쓴다.
  (R1 의 735 는 `..StrDesign(` 처럼 연결 연산자 뒤 호출을 빼고 센 값이다.)
- eudext: `eudext.strdesign.design(s, style=, center=)` 파이썬 함수 하나 + `Style` 표. 맵마다 `set_style()` 한 번. **바이트까지 원본과 같다**(5절 표로 시험).

---

## 1. 원본 정의와 판

| 판 이름(제안) | 정의 | 앞(`StrD[1]`) | 뒤(`StrD[2]`) | X 판 | 그 밖 |
|---|---|---|---|---|---|
| `mcf` | L322:66 `StrDesign`, L322:71 `StrDesignX` | `"\x07『 "` | `" \x07』"` | `"\x13"` + 앞 | `StrD` 없음 |
| `seed` | Tpl:16/21 (`StrD` Tpl:11~13), Seed:22/27 (`StrD` Seed:17~19), Stel:16/21 (`StrD` Stel:11~13) | `"\x08。\x18˙\x0F+\x1C˚ "` | `" \x1C。\x0F+\x18.\x08˚"` | `"\x13"` + 앞 | 세 파일의 두 함수·`StrD` 는 **글자까지 같다**(LUPA 에서 Tpl=Seed=Stel 출력 동일) |
| `respect` | ResV:12/17 (`StrD` ResV:7~9) | `"\x07。\x18˙\x0F+\x1C˚ "` | `" \x1C。\x0F+\x18.\x07˚"` | `"\x13"` + 앞 | `seed` 와 첫 색(0x07)·끝 색(0x07)만 다름 |
| `memory` | Mem2:4 `StrDesign`, Mem2:10 `StrDesignX`, Mem2:13 `StrDesignX2` | `"\x07·\x11·\x08·\x07【 "` | `" \x07】\x08·\x11·\x07·"` | `StrDesignX` = `"\r\r\x13"` + 앞, `StrDesignX2` = `"\x13"` + 앞 | `StrDesign` 도 `"\r\r"` + 앞. `StrD` 없음. 주석 처리된 옛 판 `Operator.lua:256` |

바이트(16진, LUPA 로 확인):

| 판 | 앞 | 뒤 | 늘어나는 길이 |
|---|---|---|---|
| `mcf` | `07 E3 80 8E 20` | `20 07 E3 80 8F` | +10 (X +11) |
| `seed` | `08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20` | `20 1C E3 80 82 0F 2B 18 2E 08 CB 9A` | +25 (X +26) |
| `respect` | `07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20` | `20 1C E3 80 82 0F 2B 18 2E 07 CB 9A` | +25 (X +26) |
| `memory` | `07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20` | `20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7` | StrDesign +32 (`0D 0D` 포함), X +33, X2 +29 |

글자: 『 U+300E, 』 U+300F, 。 U+3002, ˙ U+02D9, ˚ U+02DA, · U+00B7, 【 U+3010, 】 U+3011. 0x07·0x08·0x0F·0x11·0x18·0x1C 는 SC 색 코드, 0x13 은 가운데 정렬, 0x0D 는 보이지 않는 글자.

- 파일 인코딩은 모두 UTF-8 이고 TEP30Flag=1 경로라 Lua 문자열이 곧 UTF-8 바이트다(G8 1.1).
- 같은 이름의 정의는 이 다섯 파일뿐이다(`function StrDesign`·`StrDesign =` 검색, `DPS_eud\eud\` 제외). DPS 는 정의가 없다(G8 0절: L322 판).
- `---@param Str? string` 주석은 nil 을 허용하는 것처럼 적었지만 실제로는 nil 이면 오류다(3절).

---

## 2. 어느 정의가 이기나

TEP 는 `main.lua` 의 로더 순서대로 파일을 실행한다. 모든 맵이 `MapSource\Library`(L322 포함)를 **먼저** 불러오고 맵 파일을 **나중에** 불러오므로, 맵 판이 있으면 그것이 전역 `StrDesign` 을 덮는다.

| 맵 | 로더 | 맵 판 로드 위치 | 쓰는 판 |
|---|---|---|---|
| DPS | `DPS_eud\main.lua:12~24` (Library → `DPS_Enhance\`) | 없음 | `mcf` |
| Seed | `theSeed\main.lua:125` Library → 128~131 Engine·MapConfig·MapLogic | `Engine\func.lua` (맵 파일 74개 중 4번째) | `seed` |
| Stel | `Stella_II\main.lua:23~47` Library → Engine·MapConfig·MapLogic → 루트 | `Engine\func.lua` (16개 중 3번째) | `seed` |
| ResV | `MSF_Respect_V\main.lua:10~24` Library → 루트 | `func.lua` (9개 중 2번째, 앞은 `CallTriggers.lua`) | `respect` |
| Mem2 | `MSF_Memory_2\main.lua:54~67` Library → 루트 | `func.lua` (20개 중 8번째) | `memory` |
| Mem1 | `MSF_Memory\Main.lua:48~56` | 없음 | `mcf` (호출 0) |
| G2R | `MSF_GaLaXy.2_R\main.lua:42~55` | 없음 | `mcf` |
| UERE | `MSF_UE_RE\main.lua:44~57` | 없음 | `mcf` |
| Brz | `MSF_Breeze\main.lua:45~58` | 없음 | `mcf` |
| Tpl | (Stella_II 가 같은 `Engine\func.lua` 를 씀, R1 4절) | `func.lua` | `seed` |

- 로드 순서는 Windows `dir /b` 정렬(대소문자 무시, `_` 는 글자 뒤)을 따른다(`theSeed\main.lua:85~98` 주석). SCAN7 이 이 규칙으로 파일 순서를 만들고,
  **맵 판 정의 파일보다 먼저 실행되는 파일의 최상위(함수 밖) 호출**을 찾았다 → **0건**. 즉 모든 호출이 맵 판을 받는다.
- 최상위 대입도 맵 판 뒤에 있다: 예) Seed `MapConfig\Buildings.lua:2971` `GunAnnouncePrefix = "\x13"..StrD[1]..…`(MapConfig 는 Engine 뒤).
- 주의: 맵 판을 **나중에** 추가하거나 파일 이름을 바꿔 정렬이 바뀌면, 그보다 앞 파일의 최상위 호출이 `mcf` 판을 받는다(조용히 다른 장식).

---

## 3. 규칙 (입력 → 출력)

판 `P = (lead, pre, post)` 에 대해(`mcf`/`seed`/`respect` 는 `lead = ""`, `memory` 는 `lead = "\r\r"`):

```
StrDesign(s)   = lead            .. pre .. tostring(s) .. post
StrDesignX(s)  = lead .. "\x13"  .. pre .. tostring(s) .. post
StrDesignX2(s) =         "\x13"  .. pre .. tostring(s) .. post        -- memory 판만
StrD           = { pre, post }                                        -- seed/respect 판만 (mcf·memory 에는 없음)
```

세부 규칙(모두 Lua 5.4 `..` 연산의 성질 — TEP 의 Lua 는 5.4.4, `TEP3.0_Headless_Compiler\TrigEditPlus\Editor\Encoder\Lua\lua.h:20~24`):

1. **바이트 그대로 이어 붙인다.** 이스케이프·정규화·길이 검사가 없다. 입력 안의 `\x00`·`\n`·색 코드·이미 있는 `\x13` 도 그대로 남는다(`\x13` 이 두 번 들어가도 지우지 않음).
2. **정수**는 10진 표기(`5` → `"5"`), **실수**는 `%.14g` 표기이고 정수값 실수는 `.0` 이 붙는다(`1.5` → `"1.5"`, `3.0` → `"3.0"`, `100000/1000` → `"100.0"`). Lua 5.4 에서 `/` 는 늘 실수를 낸다.
   실사용: DPS `CallTriggers\gameplay\gacha.lua:332` 의 `(k[3]/1000).." %"`, DPS `TBL.lua:1212` `StrDesignX(k[1].." "..Convert_Number(k[2]).." \x04개 - \x07"..(k[3]/1000).." %")` — 이런 곳은 `"12.5 %"`, `"100.0 %"` 처럼 찍힌다.
3. **nil·불리언·표**는 오류(`attempt to concatenate a nil value`)로 컴파일이 멈춘다.
4. 앞의 공백 1개·뒤의 공백 1개는 장식의 일부다(빈 문자열을 넣으면 공백 두 개가 붙어 있다).
5. `StrD[1]`/`StrD[2]` 는 `StrDesign` 의 `pre`/`post` 와 **같은 바이트**다(LUPA 로 확인). 그래서 `"\x13"..StrD[1]..X..StrD[2]` 는 `StrDesignX(X)` 와 같고, 가운데에 동적 원소를 끼울 때 쓴다(DisplayPrint 원소, S3 5.1 Stel 예).
6. 결과는 한 줄로 간주되지 않는다 — 입력에 `\n` 이 있으면 장식은 첫 줄 앞과 마지막 줄 뒤에만 붙는다.
7. `memory` 판의 `\r\r` 은 줄 머리에 붙는 보이지 않는 글자다. 채팅 효과 블록의 표식 `"\x0D\x0D!H"`(S6)와 **겹치지 않는다**(`0D 0D 07 C2` ≠ `0D 0D 21 48`). Mem2 는 표식이 필요한 줄에는 `"\x0D\x0D!H"..StrDesignX2(…)` 를 쓴다(9회 전부, 예: Mem2 `Operator.lua:459`, `Interface.lua:523~526`, `System.lua:1462`, `func.lua:441,2016`, `GunData.lua:1327`).

---

## 4. 사용

### 4.1 호출 수 (SCAN, 주석 제외, `..` 뒤 호출 포함)

| 함수 | DPS | Seed | Stel | ResV | Mem2 | Mem1 | G2R | UERE | Brz | Tpl | 9맵 합 | 그 밖 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `StrDesign` | 194 | 44 | 36 | 60 | 51 | · | 1 | · | 18 | · | 404 | 23 |
| `StrDesignX` | 279 | 17 | 43 | 66 | 15 | · | 2 | 9 | 55 | · | 486 | 40 |
| `StrDesignX2` | · | · | · | · | 9 | · | · | · | · | · | 9 | 0 |
| 합 | 473 | 61 | 79 | 126 | 75 | 0 | 3 | 9 | 73 | 0 | **899** | 63 |
| `StrD[1]`/`StrD[2]` 참조 | · | 36 | 32 | 28 | · | · | · | · | · | · | 96 | — |

### 4.2 감싸는 호출 (가장 안쪽, SCAN7)

| 맥락 | 9맵 합 | 맵별 | 예 |
|---|---:|---|---|
| `DisplayText(StrDesign…(…), 4)` | 309 | DPS 186, Stel 24, ResV 47, Mem2 32, UERE 8, Brz 12 | DPS `CallTriggers.lua:900` `DisplayText(StrDesign("\x08ERR…"),4)` |
| `DisplayTextX(…)` (RotatePlayer 안) | 296 | DPS 116, Seed 4, Stel 39, ResV 61, Mem2 20, G2R 1, UERE 1, Brz 54 | DPS `GlobalBoss.lua:39` `RotatePlayer({DisplayTextX(StrDesignX("\x1DExtra Boss…"),4)}, Force1, FP)` |
| 변수 대입·표·연결식 | 207 | DPS 102, Seed 52, Stel 7, ResV 16, Mem2 21, G2R 2, Brz 7 | G2R `main.lua:5414` `MacroWarn = "…"..StrDesignX("…").."\n"..StrDesignX("…")..…` |
| `print_utf8(12,0,…)` | 46 | DPS 46 | DPS `CallTriggers\economy\stat_shop.lua:56` |
| `DisplayPrintEr({…})` 원소 | 16 | DPS 16 | DPS `SCR_DB.lua:270` |
| `LeaderBoardScore/Kills(…)` 이름 | 16 | DPS 2, Seed 2, Stel 9, ResV 2, Mem2 1 | Seed `MapLogic\LeaderBoard.lua:220` `LeaderBoardKills("Any unit", StrDesign(LeaderBoardKillsLabel))` |
| `DisplayPrint({…})` 원소 | 6 | DPS 3, Seed 3 | DPS `CallTriggers\gameplay\gacha.lua:326` |
| `table.insert(…)` | 3 | DPS 2, Mem2 1 | DPS `Interface.lua:272` |

### 4.3 인자 종류 (SCAN7)

| 맵 | 문자열 리터럴 | 연결식(`..`) | 변수 | 그 밖 |
|---|---:|---:|---:|---:|
| DPS | 374 | 95 | 4 | · |
| Seed | 50 | 6 | 3 | 2 (여러 줄 연결식, `Combination.lua:160`) |
| Stel | 54 | 25 | · | · |
| ResV | 101 | 25 | · | · |
| Mem2 | 47 | 26 | 2 | · |
| G2R | 2 | 1 | · | · |
| UERE | 9 | · | · | · |
| Brz | 66 | 7 | · | · |

- 숫자를 **직접** 넘긴 호출은 0 이다. 숫자는 연결식 안에서만 섞인다(3-2 규칙이 거기서 적용).
- 변수 인자는 컴파일 시점 Lua 문자열(예: DPS `Interface.lua:272` `StrDesign(MText)`, Seed `LeaderBoard.lua:220` `StrDesign(LeaderBoardKillsLabel)`)이다. 런타임 값은 넣을 수 없다(넣으면 3-3 오류 또는 표 연결 오류).

---

## 5. 시험 기대값 (LUPA — 원본 Lua 실행 결과)

방법: 각 파일에서 `function StrDesign…end` 원문을 뽑아 lupa `LuaRuntime(encoding=None)`(바이트 문자열)에서 실행하고, 3절 규칙을 옮긴 파이썬 참조 구현과 비교했다. **6개 파일 × 13개 함수판 × 12개 입력 = 156건 모두 일치**(`s7_lupa_out.json`).
실행: `C:\Users\whatd\.venvs\eud076\Scripts\python.exe s7_lupa.py` (lupa.lua54 = Lua 5.4, TEP 와 같은 판).

입력 12개: 빈 문자열 / `abc` / `보스 등장` / `\x04[\x1f보스\x04]` / `\x13가운데` / `a\nb` / `a\x00b` / 정수 5 / 실수 1.5 / 실수 3.0 / nil / true.

### 5.1 `mcf` (L322)

| 함수 | 입력 | 출력 (16진) |
|---|---|---|
| StrDesign | `""` | `07 E3 80 8E 20 20 07 E3 80 8F` |
| StrDesign | `abc` | `07 E3 80 8E 20 61 62 63 20 07 E3 80 8F` |
| StrDesign | `보스 등장` | `07 E3 80 8E 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 07 E3 80 8F` |
| StrDesign | `\x04[\x1f보스\x04]` | `07 E3 80 8E 20 04 5B 1F EB B3 B4 EC 8A A4 04 5D 20 07 E3 80 8F` |
| StrDesign | `a\x00b` | `07 E3 80 8E 20 61 00 62 20 07 E3 80 8F` |
| StrDesign | 5 | `07 E3 80 8E 20 35 20 07 E3 80 8F` |
| StrDesign | 3.0 | `07 E3 80 8E 20 33 2E 30 20 07 E3 80 8F` |
| StrDesign | nil / true | 오류 (`attempt to concatenate`) |
| StrDesignX | `""` | `13 07 E3 80 8E 20 20 07 E3 80 8F` |
| StrDesignX | `\x13가운데` | `13 07 E3 80 8E 20 13 EA B0 80 EC 9A B4 EB 8D B0 20 07 E3 80 8F` |
| StrDesignX | 1.5 | `13 07 E3 80 8E 20 31 2E 35 20 07 E3 80 8F` |

### 5.2 `seed` (Tpl = Seed = Stel, 세 파일 출력 동일)

| 함수 | 입력 | 출력 (16진) |
|---|---|---|
| StrDesign | `""` | `08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A` |
| StrDesign | `abc` | `08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A` |
| StrDesign | `a\nb` | `08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 0A 62 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A` |
| StrDesign | 5 | `08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 35 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A` |
| StrDesignX | `보스 등장` | `13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 EB B3 B4 EC 8A A4 20 EB 93 B1 EC 9E A5 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A` |
| StrDesignX | 3.0 | `13 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 33 2E 30 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A` |
| `StrD` | — | `{ 08 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 , 20 1C E3 80 82 0F 2B 18 2E 08 CB 9A }` |

### 5.3 `respect` (ResV)

| 함수 | 입력 | 출력 (16진) |
|---|---|---|
| StrDesign | `abc` | `07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 61 62 63 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A` |
| StrDesignX | `""` | `13 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A` |
| `StrD` | — | `{ 07 E3 80 82 18 CB 99 0F 2B 1C CB 9A 20 , 20 1C E3 80 82 0F 2B 18 2E 07 CB 9A }` |

### 5.4 `memory` (Mem2)

| 함수 | 입력 | 출력 (16진) |
|---|---|---|
| StrDesign | `""` | `0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7` |
| StrDesign | `abc` | `0D 0D 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 62 63 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7` |
| StrDesignX | `abc` | `0D 0D 13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 62 63 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7` |
| StrDesignX2 | `abc` | `13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 61 62 63 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7` |
| StrDesignX2 | 1.5 | `13 07 C2 B7 11 C2 B7 08 C2 B7 07 E3 80 90 20 31 2E 35 20 07 E3 80 91 08 C2 B7 11 C2 B7 07 C2 B7` |

나머지 조합(모든 판 × 12 입력)은 `s7_lupa_out.json` 에 있다. 구현 시험은 이 JSON 을 `tests/data/strdesign_expected.json` 으로 옮겨 쓴다.

### 5.5 구현 시험 항목 (`tests/t_strdesign.py`)

1. 5절 JSON 의 156건: `design(...)` 의 UTF-8 바이트가 기대값과 같다(오류 기대 건은 `EPError`).
2. lupa 가 있으면(개발 venv `eud081`, DESIGN 2.1) 원본 Lua 파일을 직접 돌리는 차등 시험을 무작위 문자열 1,000개로 한 번 더(색 코드·한글·전각·`\n`·`\x00` 섞기).
3. `STYLE.parts == (pre, post)` 가 `StrD` 와 같다.
4. epScript 번역: `import eudext.strdesign as sd; … sd.design("…")` 가 `sd.f_design(...)` 로 번역되고 빌드된다(DESIGN 3.1·3.11).
5. 트리거 0개: `design()` 호출 전후 트리거 수가 같다.

인게임 확인은 필요 없다(바이트가 원본과 같으면 화면도 같다). 다만 새 판(스타일)을 추가할 때 글꼴에서 기호가 보이는지는 눈으로 확인한다.

---

## 6. eudext API 확정안 (`eudext.strdesign`)

```python
from eudext import strdesign as sd

sd.Style(pre: str, post: str, lead: str = "")          # 판 정의 (불변 값 객체)
sd.STYLES = {"mcf": …, "seed": …, "respect": …, "memory": …}   # 1절 표 그대로
sd.set_style(name_or_style)                             # 맵마다 한 번 (기본값 없음 → 부르기 전 design() 은 EPError)
sd.design(text, *, style=None, center=False, lead=True) -> str
    # = lead(선택) + ("\x13" if center) + pre + text + post
    # style=None 이면 set_style 로 정한 판. lead=False 는 memory 판의 StrDesignX2.
sd.design_x(text, **kw)  = sd.design(text, center=True, **kw)     # StrDesignX 별칭
sd.parts(style=None) -> (pre, post)                                # StrD 대체
sd.lua_tostring(x) -> str                                          # 3-2 규칙(옮기기용)
# 별칭 (DESIGN 3.1): f_design = design, f_design_x = design_x, StrDesign = design, StrDesignX = design_x
```

- **text 는 `str`(또는 `bytes`)만** 받는다. `int`·`float` 는 `EPError("숫자는 f-문자열로 바꾸거나 sd.lua_tostring 을 쓰세요")` — 파이썬 `str(100.0)` 은 `"100.0"` 으로 같지만 `str(1/3)` 은 `0.3333333333333333`(17자리)로 Lua `%.14g`(`0.33333333333333`)와 달라 조용히 어긋나기 때문이다. 옮길 때 `sd.lua_tostring(k3/1000)` 을 쓰면 원본과 같다.
  (`lua_tostring`: `int` → `str(x)`, `float` → 정수값이고 |x|<1e16 이면 `"%d.0"`, 아니면 `"%.14g"` — LUPA 참조 구현 `s7_lupa.py:lua_tostring`. inf/nan 은 `EPError`.)
- `None`·`bool`·그 밖은 `EPError`(원본도 오류).
- 반환은 `str`. `bytes` 를 넣으면 `bytes` 를 돌려준다(UTF-8 로 이어 붙임). eudplib 은 `DisplayText(str)` 을 UTF-8 로 인코딩하므로 바이트 결과가 원본과 같다.
- **트리거를 만들지 않는다**(순수 파이썬). 비용 0. CP·로컬 무관.
- epScript: 전역 문자열 상수 선언은 안 되지만 함수 인자는 된다(DESIGN 3.11) → `DisplayText(sd.design("…"))` 형태로 쓴다.
- `display` 와의 관계: `dp.show(t, sd.parts()[0], v, sd.parts()[1])` 가 옛 `{StrD[1], v, StrD[2]}` 와 같다. 편의로 `sd.wrap(*parts, center=False)` → `[lead, "\x13"?, pre, *parts, post]` 목록을 돌려주는 도우미를 둔다(display part 목록에 펼쳐 넣기용).

옮기기 예:

```python
sd.set_style("seed")                                         # theSeed / Stella_II / 새 템플릿
DoActions(DisplayText(sd.design_x("\x1DExtra Boss\x04 …"), 4))        # DPS GlobalBoss.lua:39 모양 (DPS 는 style="mcf")
dp.show(players.Humans, *sd.wrap("\x13", hero_name, "\x04을(를) 처치! ", pts, center=False))  # Stel System.lua:1691 모양
LeaderBoardKills("Any unit", sd.design(LEADERBOARD_KILLS_LABEL))       # Seed LeaderBoard.lua:220
DisplayText("\r\r!H" + sd.design_x("…", style="memory", lead=False))   # Mem2 StrDesignX2 + 채팅 효과 표식
```

---

## 7. 함정

1. **판이 맵마다 다르다.** 같은 이름이 4가지 결과를 낸다. 공용 코드(라이브러리)는 판을 가정하지 말고 `sd.design()` 에 맡긴다. `set_style` 을 안 부르면 오류로 멈추게 한 것도 이 때문이다(조용히 `mcf` 가 되는 원본 사고 방지 — 2절 주의).
2. **Mem2 의 `\r\r`**: `StrDesign`/`StrDesignX` 결과가 `0D 0D` 로 시작한다. 이 결과 뒤에 문자열 비교(예: 채팅 효과 표식 `\x0D\x0D!H` 검사, S6)를 하면 앞 두 바이트가 같아 **부분 일치**로 오해하기 쉽다. 4바이트 전체를 비교하면 겹치지 않는다(3-7).
3. **실수 표기**: Lua `/` 결과를 이어 붙이면 `"100.0"` 이 된다(3-2). 원본 화면에 `100.0 %` 가 찍히던 곳을 새 코드에서 `f"{x/1000} %"` 로 옮기면 같지만, `f"{x/1000:g}"` 로 바꾸면 `100` 이 되어 달라진다. 의도적으로 고칠 곳인지 옮길 때 판단.
4. **길이**: 장식이 +10~+33 바이트를 더한다. `print_utf8(12,0,…)`(13번째 줄, 218B)이나 TBL 자리, `DisplayPrintEr`(210B)에 넣을 때 넘치기 쉽다 — `display` 쪽 길이 검사(S3 7.2)가 장식 길이까지 포함해 센다.
5. **`\x13` 중복**: `StrDesignX("\x13…")` 는 `\x13` 이 두 번 들어간다(원본 그대로, 무해 — 추측: SC 는 줄마다 정렬 코드를 한 번만 본다).
6. **`\x00`**: 입력에 NUL 이 있으면 결과 문자열이 거기서 끊겨 보인다(원본도 같음). eudext 는 경고만 한다(`EPWarning`).
7. **`StrD` 는 `seed`/`respect` 판에만 있다.** `mcf`·`memory` 판에서 `sd.parts()` 를 부르면 1절 표의 pre/post 를 돌려준다(원본에는 없던 기능 — 옮긴 코드에는 영향 없음).
8. R1 의 735 와 이 문서의 899 는 셈 방식 차이다(연결 연산자 뒤 호출 포함 여부). 우선순위 판단(DESIGN 0.2)에는 영향 없음.

---

## 8. DESIGN.md 수정 제안

1. **4.7 `strdesign` 줄** 교체:
   `from eudext.strdesign import design` / `design("\x04[\x1f보스\x04] 등장")` →
   `sd.set_style("seed")` + `sd.design(text, style=None, center=False, lead=True)`, `sd.design_x`, `sd.parts()`, `sd.wrap()`, `sd.lua_tostring()`, `sd.STYLES`(mcf/seed/respect/memory).
   "StrDesign 규칙을 파이썬 함수로 (S7 에서 규칙 추출)" → "규칙: lead + [\x13] + pre + text + post (S7 3절), 판 4개, 트리거 0".
2. **4.7 근거 줄**: "`StrDesign` 735회" → "`StrDesign` 계열 9맵 899회(`..` 뒤 호출 포함, S7 4.1) + `StrD` 96회".
3. **0.1 표 또는 3.1 이름 규칙**: 컴파일 시점 전용 순수 함수도 `f_` 별칭을 둔다는 것을 한 줄(`sd.f_design`). epScript 호출 가능하게.
4. **6.1 표 WP6 추가 완료 조건**: "`tests/t_strdesign.py` 가 S7 5절 기대값 156건과 일치, lupa 차등 1,000건".
5. **2.2 폴더 구조**: `strdesign.py` 설명을 "컴파일 시점 색 문자열 꾸미기 (StrDesign 4판 + StrD)" 로.
6. **새 맵 템플릿 안내**(1.3 또는 별도 절): 새 맵은 `sd.set_style()` 을 맵 설정 파일 맨 앞에서 부른다. 원본의 "Library 먼저, 맵 판이 덮음" 구조를 없앤다.
7. **8절 표**에 "StrDesign 규칙·기대값 → `docs/spec/S7_strdesign.md`" 행 추가.

---

## 9. 미확인

1. `memory` 판의 앞 `\r\r` 이 **왜** 붙었는지(채팅 효과 표식과의 관계, 줄 정렬 목적 등) — 코드에 설명이 없다. 동작(바이트)은 확인했다.
2. `\x13` 이 한 줄에 두 번 있을 때 SC:R 화면이 어떻게 되는지(7-5, 추측).
3. 입력의 `\x00` 이후를 SC:R 이 정말 안 그리는지(7-6, 일반 지식 기반 추측).
4. 원본 맵의 **실제 빌드 산출물**(STRx 문자열)과 대조하지는 않았다 — 함수 원문을 lupa 로 돌린 결과만 확인했다. TEP 의 문자열 처리(`TEP30Flag=1`, UTF-8 그대로)는 G8 1.1 을 따랐다.
5. 구판 맵(그 밖 63회)은 판을 조사하지 않았다(대부분 `mcf` 로 보인다 — 추측).
6. `Stella_II\Engine\func.lua` 와 Tpl 이 "빈 줄 하나 차이"(R1 4절)인데, 함수 부분은 LUPA 로 같다는 것만 확인했다.
