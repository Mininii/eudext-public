# S1 — G_CB 스포너 명세 (`eudext.spawn` 구현 전)

작성 2026-09-17. 조사만 했고 맵·라이브러리 파일은 고치지 않았다. 확인하지 못한 것은 "(추측)", 코드만 읽고 인게임으로 보지 못한 것은 "(코드 읽기)"라고 적었다.
실험 파일은 스크래치패드 `spec_s1\` 에 있다: `gcb_usage.py`(사용 빈도, 결과 `gcb_usage_out.txt`), `gcb_ref.py`(좌표 변환·대기열 참조 모델).

## 줄임말

| 줄임 | 경로 (`SD` = `C:\Users\whatd\Desktop\Stormcoast Fortress\ScmDraft 2`) |
|---|---|
| **GCB** | `SD\theSeed\Engine\G_CB_Lib.lua` (정본, 2,769줄) |
| CAPI | `SD\theSeed\Engine\CAPlotIndexed.lua` |
| STL | `SD\Stella_II\Engine\G_CB_Lib.lua` (원본, 2,230줄) |
| TPL | `C:\Users\whatd\Documents\MSF-Template\G_CB_Lib.lua` (2,225줄) |
| RSV | `SD\MSF_Respect_V\G_CBPlot.lua` (구판, 1,837줄) |
| UER | `SD\MapSource\MSF_UE_RE\func.lua` 632~1537줄 (별계열) |
| MEME | `SD\MSF_MEME_EUD\function.lua` 296~2054줄 (신판 초기 사본) |
| CA | `SD\MapSource\Library\CtrigAsm v5.5.lua` |
| L322 | `SD\MapSource\Library\LibraryFor322.lua` |
| CBP | `SD\MapSource\Library\CB Paint v2.5.lua` |
| PLAN | `SD\theSeed\G_CB_REFACTOR_PLAN.md` |
| PROG | `SD\theSeed\PROGRESS.md` |
| Seed/Stel/ResV/Mem2/G2R/UERE/Brz | R1 약칭과 같은 맵 폴더 |

---

## 0. 한눈에

| 항목 | 결론 |
|---|---|
| 정본 | **theSeed 판(GCB)**. 맵 크기 일반화, 로케이션 계약, 대기열 경계 수정, CB 표 크기 수정, RepeatType 표, CAPlotIndexed, LoopMax 배선이 모두 들어 있고 인게임을 통과했다(PLAN 369~378, PROG 34절). 단 theSeed 전용 RepeatType(40·83·130·176~181 등)은 일반 기능이 아니다 |
| 구조 | 소환 요청 1건 = 트리거 레코드 1개(액션 55개의 값 칸이 데이터). 최대 4층을 바이트로 묶어 넣고, 매 프레임 레코드마다 맨 앞 층 하나를 CBPlot 으로 진행한다. 점마다 콜 3단(`CA_Func1 → Call_CA_Repeat → Set_Repeat → Call_Repeat`)으로 1기씩 만들고 `Call_RepeatOption` 이 RepeatType 별 후처리를 한다 |
| 속성 | 신판 `G_CB_TSetSpawn` 속성 **15종** + 위치 인자 3개(주인·중심·보존). 구판·UE_RE 전용 키까지 합치면 **22종**(5절) |
| RepeatType | **맵마다 이름·번호·의미가 다르다**(5.4). eudext 는 고정 표가 아니라 **등록형 핸들러**로 준다 |
| 가장 까다로운 것 | ① 대기열 레코드·임시 변수 공유(T 경로 경합), ② 로케이션 번호의 0/1 기준이 함수·판마다 다름(오프바이원 2건 발견, 10절), ③ CtrigAsm 회전의 항별 자르기 재현, ④ LoopMax 포인터가 작업별로 저장되지 않음(코드 읽기, 10절) |
| API 확정안 | `Spawner(capacity, loc, loc2, default_target, …)` + `push(unit, shape, …)` / `job().layer().push()` + `tick()` + `spawn_now()` + `rtype()` 등록 + `scan_effect()`. 내부 = pool 레코드(층 1개 = 레코드 1개, 사슬) + plot 점 읽기 + mathx 회전 + units.capture (8절) |
| 비용 | 지금: 대기열 307KB + 빈 도형 좌표 약 1.78MB + 도형당 약 6트리거 + 점당 실행 약 400~500(추정). 목표: 대기열 12KB, 도형당 0트리거, 점당 실행 60 이하(기본 경로, 추정 목표) |

---

## 1. 판 비교와 정본

### 1.1 판 목록

| 계열 | 판 | 쓰는 맵 | 특징 |
|---|---|---|---|
| **신판 G_CB** | STL (원본) | Stel | `G_CB_TSetSpawn(Cond, CUT, Shape, Owner, Center, Preserve, Prop)` 7인자, 속성 15종, RepeatType `CElseIfX_AddRepeatType` 나열 |
| | TPL | (템플릿) | STL 과 같고 `CB_initTCopy` 표 크기 수정과 CA2Arr 제거만 있다(대기열 경계 수정은 없음) |
| | **GCB (theSeed)** | Seed | STL 통째 복사 뒤 재정비(아래 1.2) |
| | MEME | MEME | STL 보다 이른 사본. 속성에 `FfragMode`·`FfragAfterTimer` 가 없고 3D 옵션 키가 `NQOpTable` 이다. Order 로케이션 인코딩이 `Temp+2`(MEME 1723) |
| **구판 G_CB** | RSV | ResV | `G_CB_TSetSpawn(Cond, CUT, Shape, Preserve, Prop)` 5인자(RSV 1438). 주인·중심이 속성(`OwnerTable`, `CenterXY`). 모르는 키는 **무시**. `RotateTable` 층별 표·`"Main2"` 지원(RSV 1562~1588). 맵 경계 `32*64`×`32*256`(RSV 931) |
| **UE 계열** | UER | UERE | 전혀 다른 구현. `Include_G_CB_Library(StartIndex, ArrSize, Lines, DefCenterXYV, TRepeatXYV, ShapeTable, LoopMaxTable)`(UER 632), 도형을 **이름 문자열 목록**으로 미리 등록(UER 950~966), 소환은 `CreateUnitQueue*` 배열에 적재(UER 720~731), `f_TempRepeat(UnitID, Number, Cond, Type, Owner, CenterXY)` 인자 순서가 다름(UER 742) |
| **옛판 G_CA** | Mem2 `func.lua:536`, G2R `func.lua:79`, Brz `func.lua:352` | Mem2, G2R, Brz | `G_CA_SetSpawn(Cond, CUT, SNTable, SLTable, LM, RepeatType, [Size/CenterType], Center, Owner, …)`(Brz 1231). 도형 고르는 법이 맵마다 다르다 — **G2R·Brz** 는 계열 배열 + 단계 번호(`{S_4,P_6}`, `{1,4}` → `SL*12` 또는 `256+j`), **Mem2 는 `SNTable` 에 `"ACAS"`(= `Another_CAPlot_Shape`) 를 주고 `SLTable` 에 도형 이름(문자열)을 주어 이름 → 인덱스로 찾는다**(실측: `SNTable` 103/103 이 `"ACAS"`, 도형 이름 136개 — Mem2 `eud/DESIGN.md` 10.13). 찍기는 `CAPlot2`(맵 안 재정의)다. 신판 `G_CB_SetSpawn` 이 이 서명을 흉내 낸 호환 래퍼다(4.2). DESIGN 4.14 대로 **eudext 대상에서 뺀다**(2026-09-20: 이 계열이 걸리던 eudext 쪽 공백 — `rot3d`·`size_div`·`bounds` — 은 메웠다) |

`f_TempRepeat2X` 는 G_CB_Lib 에 없고 Mem2 `func.lua:1086` 에만 있다(유닛 최대 20종 + 이펙트 번호 = 신판 `G_CB_SetSpawn2X`/`FfragMode` 의 전신).

### 1.2 STL → GCB 차이 (재정비 내용)

| 항목 | STL/TPL | GCB | 근거 |
|---|---|---|---|
| 맵 경계 | `32*128` 고정, LPos 클램프 4096/4095 | `GMapSize` 에서 `W-1`/`H-1` | GCB 79~99, 781~783, 1453; PLAN B-5 |
| 점대칭 중심(RepeatType 130~133) | 2048 고정 | `G_CB_CenterX/Y` = 맵/2 | GCB 860~889 |
| 폴백 좌표 | `3712,288`(Stella 맵 좌표) | 맵 중앙 | GCB 96~99, 933~934 |
| 스크래치 로케이션 | 0 과 130 | `TempLoc`/`TempLoc2`(theSeed 250/251) | GCB 164~199; `theSeed\main.lua:219-221` |
| 점 되읽기 | `0x58DC60` 고정(로케이션 0) | `0x58DC60 + 20*TempLoc` | GCB 681~690; PLAN 2-A |
| `TCreateUnitWithProperties` 인자 | (정상) | Phase 2 에서 개수 자리에 로케이션을 넣었다가 고침 | GCB 891~897; PLAN 312~326 |
| 대기열 경계 | STL 은 수정됨, **TPL 은 옛 조건**(`604*Size-2`) | `604*(Size-1)-1` | GCB 1358~1365; TPL 1020 |
| `CB_initTCopy` 표 크기 | STL 은 항목 수(버그), TPL 은 수정 | 바이트 수 `(#FX+1)*4` | GCB 1509~1521; PROG 34절 정정 |
| CA2ArrX/Y/Z(1700칸 VArr 3개) | 있음(12.3MB) | 없앰 | GCB 69~74 |
| RepeatType 정의 | `CElseIfX_AddRepeatType` 나열 | 순서 있는 배열 `RepeatTypeDefs` + 맵 확장 `G_CB_RepeatTypeExtraDefs` | GCB 319~345, 441~610 |
| 플롯 | `CBPlot`(도형당 약 17트리거) | `CAPlotIndexed`(도형당 약 4.0) | CAPI 1~39; PROG 34절 |
| LoopMax | 만들고 버림(`nil` 전달) | `G_CB_LoopSchedule`(도형 표가 키) 배선 | GCB 1755~1780 |
| 빈 밴드 사이클 | "Not Found" 오류로 작업 버림 | 살아 있는 것으로 침 | GCB 1931~1941 |
| 0틱 클릭 불가 | 없음 | `G_CB_SpawnUnclickableUnits` | GCB 42~59, 1885~1942 |
| 계측 | 주석 처리된 DisplayPrint | `GCBDebugText`(`theSeed\MapConfig\Interface.lua:577`, 과제 설명의 `Debug.lua` 는 없음) | GCB 1437~1445, 1862~1874, 1943~1956 |
| theSeed 전용 | — | 40번 removeTimer 0, 난이도 체력, Wait_130, Vision, Gun_Home, Home_Vision | GCB 235~253, 347~439, 491~588 |

### 1.3 정본으로 GCB 를 고른 이유

1. 맵 크기·로케이션 번호를 한곳(`GMapSize`, `TempLoc`)에서 받는다. eudext 로 옮길 때 "숫자가 무엇인지"가 코드에 남아 있다.
2. 알려진 버그 5건(대기열 경계, CB 표 크기, 로케이션 0 되읽기, 개수/로케이션 자리, 128×128 상수)이 모두 고쳐졌다. STL 은 CB 표 크기, TPL 은 대기열 경계가 남아 있다.
3. 인게임 검증: 해처리 41점(PLAN 369~378), CAPlotIndexed(CAPI 34~38), CB 표 크기(PROG 34절 정정).
4. 동작을 설명하는 주석이 가장 많다(`G_CB_TSetSpawn` 인자·속성 조사 주석 GCB 2188~2259).

**주의**: GCB 의 RepeatType 표 가운데 일반 기능은 0·2·3·5·6·7·8·106·147·148·180·187·201 뿐이다. 나머지는 theSeed 맵 로직(EXCC 칸 번호, P9/P10, 난이도 변수)에 묶여 있어 eudext 에 넣지 않는다(5.4).

### 1.4 G_CA·UE_RE 와 eudext

- G_CA: 도형 계열+단계 선택, `CAPlot2`, 맵마다 다른 서명(3개 맵에서 인자 수가 다름). eudext 대상 밖. 옛 맵을 옮길 때는 "단계 번호 → 도형 객체"를 컴파일 시점에 풀어 `push` 로 부르면 된다.
- UE_RE: 도형을 이름으로 미리 등록하고 PF(`PlotSizeCalc` 단계, UER 1118~1152) 같은 맵 전용 전처리가 있다. 소환 자체는 `CreateUnitQueue` 에 맡긴다. 속성 의미(LM, Delay, RepeatType, FN, Center, Owner)는 신판과 같은 축이므로 8.4 대응표로 옮길 수 있다.

---

## 2. 초기화 `Include_G_CB_Library(DefaultAttackLoc, StartIndex, Size_of_G_CB_Arr)` (GCB 61~2768)

파일 전체가 이 함수 한 몸이다. 파일을 읽을 때는 아무것도 안 만들고, 호출 시점에 전부 만든다(PLAN 35~37).

### 2.1 인자

| 인자 | 뜻 | theSeed 값 | 근거 |
|---|---|---|---|
| `DefaultAttackLoc` | RepeatType 기본 명령의 목표 로케이션. **1-based(에디터 번호)** 그대로 `TOrder` 의 목표 인자로 간다 | `GunDefaultAttackLoc+1` = 101 | GCB 638~640, 907, 197~199; `theSeed\main.lua:226,236-238` |
| `StartIndex` | 대기열 레코드의 트리거 라벨 시작 번호 | `0x600` | GCB 1196, 2762 |
| `Size_of_G_CB_Arr` | 대기열 칸 수 | 128 (모든 맵 128, UERE 256) | GCB 2752; `gcb_usage_out.txt` |

### 2.2 선행 조건

| 필요한 것 | 검사 | 누가 만드나 | 쓰는 곳 |
|---|---|---|---|
| `CPos`/`CPosX`/`CPosY`/`Convert_CPosXY`, `GMapSize` | GCB 65, 89 | `Include_Conv_CPosXY(FP,{W,H})` L322 1526~1560 | 유닛 좌표 읽기, 맵 경계 |
| `FP` | GCB 66 | 맵 | 모든 트리거 주인 |
| `GLocC`, `TGetLocCenter` | GCB 67 | `Install_GetCLoc(FP, Loc, nilunit)` L322 1217~1250 | 로케이션 중심 구하기 |
| `TempRandRet`, `f_CRandNum` | GCB 68 | `Include_CRandNum(FP)` L322 1286 | 프리펑션 난수 |
| `TempLoc`, `TempLoc2` (0-based 번호) | 없음 | 맵 전역(theSeed main.lua:220-221) | 소환 자리 / 명령 목표 |
| `nilunit` | 없음 | 맵(theSeed 181, main.lua:140) | `CAPlotIndexed` 의 가짜 생성, `Install_GetCLoc` |
| `RandSwitch1` | 없음 | 맵("Switch 100", main.lua:147) | `CB_RandSort` |
| `Include_CtrigPlib(360, …)` | 없음 | main.lua:170 | `f_Lengthdir`/`f_Sqrt`/`f_Atan2`, 회전 **Cycle = 360** |
| `Include_CBPaint()` | `CB_TCopy` 가 `CBPlotTempArr` 검사 | main.lua:198 | `CB_Sort`, `CB_GetNumber`, `CA_*` |
| `STRCTRIGASM == 1` | CAPI 42~44 | 빌드 설정 | 파일 배열 |
| `DUnitCalc`, `UnivCunit` (EXCC), `Set_EXCC3` | 없음 | `Install_EXCC`(main.lua:167,169), 템플릿 함수 | 유닛별 저장 |
| `Call_EXCC_AllReset`, `ResetUnitI` | 없음 | `Install_CallTriggers()`(main.lua:235, `theSeed\Engine\CallTriggers.lua`) | 새 유닛 슬롯의 EXCC 초기화 |
| `ImagesDatClickableAddr` | 없음 | `theSeed\Engine\func.lua` | 0틱 클릭 불가 |
| `ParseUnitNameT` | 없음 | 맵(`SetUnitAbility`, PLAN 270) | 유닛 이름 문자열 |
| `InitCFunc`/`CFunc` | 없음 | CtrigAsm | 정렬 함수 |
| `TestStart`, `Limit`, `DebugOn`, `DisplayPrintEr` | 없음 | 맵 | 시험 문구·계측 |
| `RegisterDifficultyVars`, `GunDifficultyMin/Max`, `GunSpawnHPPct`, `GunBlackHoleMobSpeed`, `GunBlackHoleMarkLine` | 없음 | theSeed MapConfig/MapLogic | theSeed 전용 RepeatType |

호출 위치(theSeed main.lua): `init_func` CJump(선언 전용) 블록 안에서 위 선행 함수들 → `Include_G_CB_Library`(238). 최상위 코드에서 모든 로직 뒤에 `Create_G_CB_Arr()`(332). 다시 CJump 블록(`init_func2`) 안에서 `G_CBPlot()`(342). Stella 도 같은 배치다(`SD\Stella_II\main.lua:86-127`).

### 2.3 만드는 것

| 종류 | 이름 (GCB 줄) | 용도 |
|---|---|---|
| 전역 변수 | `CA_Eff_Rat`(=25000, 62), `CA_Eff_XY/YZ/ZX`, `CA_Create`(63; `CA_Create2` 는 `CreateVars(4)` 라 nil) | 3D 회전 각(맵이 씀) |
| 오류 문구 | `f_RepeatTypeErr` 등 9개(101~109) | 부저 + 문구 |
| 로컬 변수 | `Gun_TempSpawnSet1`(유닛), `Spawn_TempW`(남은 수), `RepeatType`, `Repeat_EffID`, `Repeat_OrderX/Y/Type`, `Repeat_TempV`, `CreatePlayer`, `TRepeatX/Y`, `NQOption`, `CA_Repeat_Check`(Ccode) (110~126) | `Call_Repeat` 입력 |
| 전역 변수 | `SpeedRet`, `G_CB_Nextptrs`(EPD), `G_CB_NextptrsP`(ptr), `CA_Repeat_X/Y`, `G_CB_BackupX/Y`(작업 중심), **`G_CB_X/Y`**(중심 생략 시 기준), `G_CB_CPlayer`, `G_CB_XDis/YDis`, `G_CB_Eff`, `G_CB_ColorMem/Color/ColorMask`, `G_CB_SpUnitType[5]`, `G_CB_SpUnitNum[5]`, `G_CB_SpAfterTimer`, **`G_CB_RotateV`**, `G_CB_RotateV2` (119~150) | 작업→소환 전달, 맵 손잡이 |
| 로컬 | `G_CB_SUTV[5]`, `G_CB_SUNV[5]`, `G_CB_SATV` (143~145) | Ffrag 임시 |
| 전역 | `RBX, RBY, RUID, RPID, RType, RPtr, RPtrP, RLocV, QueueOX, QueueOY, RUI2` (152~162) | RepeatType 처리 입력 |
| 표 | `G_CB_Shapes = {}`, `G_CB_ShapeIndexAlloc = 1` (147~148) | 도형 등록 |
| 콜 | `Call_Calc_NSpeed`(201~221), `Call_RepeatOption`(223~632), `Call_Repeat`(636~950), `Set_Repeat`(1165~1175), `Write_SpawnSet`(1212~1371), `Call_CA_Repeat`(1385~1397), `Call_G_CB`(2607~2747), `Call_G_CBPlot`(인덱스만 1738, 몸은 `G_CBPlot()`) | 4.9 |
| 임시 표(스테이징) | `G_CB_LineV`, `G_CB_CUTV`, `G_CB_SNTV[4]`, `G_CB_DLTV[4]`, `G_CB_FNTV`, `G_CB_LMTV`, `G_CB_RPTV`, `G_CB_CPTV`, `G_CB_SZTV`, `G_CB_RTTV[4]`, `G_CB_XPos/YPos`, `G_CB_OrderXPos/YPos/Act`, `G_CB_NQOption` (1177~1192) | 넣기 인자. **모든 호출 자리가 공유** |
| 대기열 작업 표 | `G_CB_TempTable[55]`(1200), `G_CB_TempH`, `G_CB_Num`, `G_CB_InputH`(init 때 0x600 레코드 +0x15C 의 EPD, 1210), `G_CB_LineTemp` | 레코드 ↔ 작업 변수 |
| CFunc | `CFunc1`(정렬 키, 1470~1490), `CFunc2`(반지름, 1492~1496) | 프리펑션 |
| 함수 | `f_TempRepeat`, `f_TempRepeatX`, `f_TempEffRepeatX`, `CA_Func1`, `G_CB_Prefunc`(안에 `CB_initTCopy`, `CB_TCopy`, `CB_RandSort`, `CB_MarNumFill`), `G_CBPlot`, `T_to_ByteBuffer`, `G_CB_SetSpawn`, `G_CB_SetSpawnX`, `G_CB_TScanEff`, `G_CB_SetSpawn2X`, `G_CB_TSetSpawn`, `AutoSetV`, `TAutoSetV`, `Create_G_CB_Arr` | 4절 |
| RepeatType 이름 | `RTypeDupeCheck`, `RTypeKey`(이름→번호, 279~280) | 문자열 RepeatType |
| theSeed 전역 | `GunBlackHoleWaveNoV/ReleasedV`(Wait_130 이 만듦, 396~399) | 맵 전용 |

### 2.4 대기열 크기와 배치 — `Create_G_CB_Arr()` (GCB 2749~2766)

- `Size_of_G_CB_Arr` 개의 **트리거**를 라벨 `StartIndex+i` 로 만든다(`G_CB_Arr_IndexAlloc`). 두 번 부르면 `Already_G_CB_Arr_Created` 오류.
- 레코드 i 의 조건: `CVar("X","X",AtLeast,1)` = 자기 0번 줄(첫 액션 값 칸)이 1 이상.
- 액션(모두 63개): `G_CB_InputCVar`(55개, `SetCVar(FP, TempTable[k], SetTo, <값>)` — **이 값 칸이 곧 데이터**), `G_CB_TempH ← 자기 +0x15C 의 EPD`, `G_CB_Num ← i+1`, `Actived_G_CB += 1`, `Call_G_CB` 호출·복귀 액션 5개.
- 플래그 `1` → `CTrigger` 에서는 **보존**(CA 7238~7240).
- 즉 매 프레임 128개 레코드가 모두 조건 검사를 받고, 살아 있는 레코드만 자기 55줄을 `G_CB_TempTable` 로 복사한 뒤 `Call_G_CB` 를 부른다. 레코드 순서 = 처리 순서.
- 배치: `Create_G_CB_Arr()` 를 부른 자리(theSeed 는 모든 Setup 뒤). **그보다 앞에서 넣은 작업은 같은 프레임에 첫 사이클이 돈다**(코드 읽기).

### 2.5 `G_CBPlot()` 컴파일 절차 (GCB 1742~1991)

1. `Z[k[2]] = k[1]` — 등록된 도형을 번호 자리에 놓는다(1743~1749). `STSize = #Y`.
2. LoopMax: `rawget(_G, "g_cb_loopschedule")` 에서 도형 **테이블을 키로** 스케줄을 찾아 `X[j]` 에 둔다. 하나도 없으면 `false`(1769~1780). (호스트가 `_G` 키를 소문자로 저장한다: `theSeed\TriggerBudget.md` 끝 주석.)
3. **빈 도형** `CS_InputVoid(1699)`(1,699점짜리 0 좌표, CBP 14517)를 3개 + 대기열 칸 수만큼 덧붙인다(1782~1787). 번호: `STSize+1`(미사용), `STSize+2`(복사 원본), `STSize+3 = EndRetShape`(정렬 결과), `STSize+3+레코드번호`(레코드별 작업 도형).
4. `SetCall2(FP, Call_G_CBPlot)` 안에 작업 변수 적재 → 0틱 클릭 끄기 → `CAPlotIndexed(Z, LoopMax, FP, nilunit, TempLoc, {TT[8],TT[9]}, 1, 32, {0,0,0,0,0,1}, "CA_Func1", "G_CB_Prefunc", FP, nil, nil, {SetCDeaths(FP,Add,1,CA_Suspend)})`(1928~1930) → 빈 밴드 처리 → 클릭 복구 → 진행 저장(1987).
5. `GunUseIndexedPlot = false` 면 라이브러리 `CBPlot` 을 같은 인자로 부른다(1928~1929; `theSeed\MapConfig\Buildings.lua:1411`).

---

## 3. 대기열 데이터 구조

### 3.1 레코드 = 트리거

- 한 레코드 = 트리거 한 개(2,400바이트, CtrigAsm 칸 간격 0x970 = 604 dword).
- **줄 k** = 그 트리거의 액션 k 의 값 칸(+0x15C + k·32바이트, EPD 로 `k*8`). `Write_SpawnSet` 은 `_Add(LineTemp, k*(0x20/4))`(GCB 1260~1301), `Call_G_CB` 는 `Vi(G_CB_TempH[2], k*(0x20/4))`(2614~2743)로 같은 칸을 가리킨다.
- 레코드가 실행되면 줄 k 가 `G_CB_TempTable[k+1]` 로 복사된다(이하 **TT[k+1]**).
- 빈 칸 판정 = 0번 줄 dword 전체가 0.

### 3.2 줄 배치 (GCB 1237~1256 주석 + 1259~1356 쓰기 + 1797~1860 읽기)

"4B 묶음" 은 `T_to_ByteBuffer` 로 층 1~4 를 바이트 0~3 에 넣은 값이다. 진행 중에는 **바이트 0 = 지금 층**.

| 줄 | TT | 내용 | 형태 | 넣을 때 | 진행 중 되쓰기 |
|---|---|---|---|---|---|
| 0 | 1 | 유닛 ID (층별) | 4B 묶음 | `G_CB_CUTV`(221~224 자리표 치환 뒤) | 바이트 0 |
| 1 | 2 | 프리펑션 번호 | 4B 묶음 | `FNTV` | 바이트 0 (실행 후 0) |
| 2 | 3 | 진행 번호(CA[6]) | dword | 0 | 전체 |
| 3 | 4 | 남은 대기(CA[2]) | dword | 0 | 전체 |
| 4 | 5 | 루프 한도 LM | 4B 묶음 | `LMTV` | 바이트 0 (자동 계산 결과) |
| 5 | 6 | RepeatType | 4B 묶음 | `RPTV` | 바이트 0 |
| 6 | 7 | (미사용) | — | 0 | 바이트 0 |
| 7, 8 | 8, 9 | 작업 중심 X, Y | dword | 3.4 중심 규칙 | — |
| 9 | 10 | 주인 | 4B 묶음 | `CPTV` | 바이트 0 |
| 10 | 11 | 크기 % | 4B 묶음 | `SZTV` | 바이트 0 |
| 11 | 12 | 3D 옵션(NQ) | 4B 묶음 | `NQOption` | 바이트 0 |
| 12~15 | 13~16 | 층별 도형 번호 | dword ×4 | `SNTV[1..4]` | 12 = TT[13](프리펑션이 바꿈) |
| 16~19 | 17~20 | 층별 딜레이(CA[3]) | dword ×4 | `DLTV[1..4]` | — |
| 20~23 | 21~24 | 층별 회전 | dword ×4 | `RTTV[1..4]` | — |
| 24, 25 | 25, 26 | 평행이동 dx, dy | dword | `XDis/YDis` | — |
| 26 | 27 | 이펙트 이미지 | dword | `G_CB_Eff` | — |
| 27~29 | 28~30 | 색 칸 EPD / 값 / 마스크 | dword | `ColorMem/Color/ColorMask` | — |
| 30, 31, 32 | 31~33 | 명령 X, Y, 종류(1 어택, 2 순찰, 3 이동) | dword | `OrderAct ≥ 1` 일 때만 씀 | — |
| 33~37 | 34~38 | Ffrag 유닛 5줄(각 4B 묶음) | dword | `SUTV[1..5]` | — |
| 38~42 | 39~43 | Ffrag 마릿수 5줄 | dword | `SUNV[1..5]` | — |
| 43 | 44 | Ffrag removeTimer | dword | `SATV` | — |
| 44~54 | 45~55 | (미사용, `G_CB_Lines = 55`) | — | — | 완료 시 0 |

### 3.3 바이트 묶음 `T_to_ByteBuffer(Table)` (GCB 1993~2052)

- 상수 표: `Σ v_i · 256^(i-1)`. 문자열은 `ParseUnitNameT[이름]`. 5개 이상이면 `BiteStack_is_Over_5` 컴파일 오류.
- **검사 없음**: 값이 255 를 넘으면 다음 층 바이트로 넘친다(크기 300% → 다음 층 크기가 1 늘어난다).
- 순회가 `pairs` 이고 자리 카운터가 "방문한 원소 수"라서, 표에 `nil` 구멍이 있으면 뒤 원소가 앞 바이트로 당겨진다(RepeatType 이름 오타가 이것을 만든다, 10절).
- V(변수) 원소가 있으면 `G_CBPlotTOption = 1` 로 T 경로를 켜고 `TempV` 에 `CAdd` 로 쌓는다. 1번 원소가 V 면 `ByteValue + j*1` 에서 표 산술이 되어 컴파일이 멈춘다(추측). 2번 이후 V 는 `CAdd` 가 **보존 트리거**라 실행될 때마다 누적된다(코드 읽기). 실사용 맵은 변수 유닛을 V 대신 **자리표 221~224 + `UnitIDV1~4`** 로 넘긴다(GCB 1214~1227).

### 3.4 넣기 — `Write_SpawnSet` (GCB 1212~1371)

1. **자리표 치환**(1216~1227): 유닛 바이트가 221~224 이면 `UnitIDV1~4` 의 값으로 바꾼다(바이트 위치와 무관하게 221→V1, 222→V2 …).
2. `LineV = 0`, 반복 라벨(1231~1232).
3. `LineTemp = LineV + InputH`. 그 칸 0번 줄이 0 이면(빈 칸) 아래 4~6 을 하고 끝.
4. 줄 0~6, 9~29, 33~43 쓰기(1259~1304). 2·3·6 은 0.
5. 명령(1306~1336): `OrderAct ≥ 1` 일 때만 32번 줄에 종류를 쓰고
   - X·Y 둘 다 `< 0x80000000` → 30·31 에 좌표,
   - 둘 다 `≥ 0x80000000` → 각각 `-0x80000000` → `TGetLocCenter(X값)` 로 중심을 구해 30·31 에 씀 (**넣는 순간의 로케이션 중심**),
   - 그 밖 → 30~32 모두 0(명령 취소).
   `OrderAct == 0` 이면 30~32 를 **쓰지 않는다**(빈 칸은 완료 시 0 으로 지워지므로 실제로는 0).
6. 중심(1338~1356):
   - X = Y = `0xFFFFFFFF` → **넣는 순간의 `G_CB_X/Y`**,
   - 둘 다 `≥ 0x80000000` → 각각 `-0x80000001` → `TGetLocCenter` → **결과를 `G_CB_X/Y` 에 덮어쓴 뒤** 7·8 에 씀(부작용),
   - 그 밖 → 좌표 그대로. 따라서 좌표 모드의 좌표는 `0x7FFFFFFF` 이하여야 한다.
7. 칸이 차 있으면: `LineV ≤ 604*(Size-1)-1` 이면 `LineV += 604` 후 3 으로. 아니면 **넘침**: 요청을 버리고 사람 플레이어에게 `f_GunSendErrT` + Buzz 2회(1366~1370, 항상 켜짐).
8. 경계 수정 이력: 옛 조건 `604*Size-2` 는 마지막 칸에서도 한 칸 더 가서 **표 바로 뒤 레코드**를 빈 칸으로 보고 44줄을 썼다(GCB 1358~1362; TPL 1020 은 아직 옛 조건).
9. 비용: 빈 칸을 앞에서부터 선형 탐색한다. 칸 하나당 반복 몇 트리거(추정).

### 3.5 매 프레임 — `Call_G_CB` (GCB 2607~2747)

레코드가 살아 있으면(0번 줄 ≠ 0) 복사 후 이 콜이 돈다.

```
if TT[1] & 0xFF ≥ 1:                      # 지금 층에 유닛이 있다
    call Call_G_CBPlot                     # 6절, 이번 프레임 몫을 찍는다
    if Launch ≥ 1 and Suspend == 0:        # 진행 중
        되쓰기: 줄0·1·4·5·6·9·10·11 의 바이트0 ← TT, 줄2 ← TT[3], 줄3 ← TT[4], 줄12 ← TT[13]
    elif Launch ≥ 1 and Suspend ≥ 1:       # 이 층 완료
        지우기: 줄0·1·4·5·6·9·10·11 바이트0 ← 0, 줄2·3·12·16·20 ← 0
        if 줄0 dword == 0: 55줄 전부 0 (줄 2 만 1)   # 모든 층 완료 → 칸 반납
    else:                                  # Launch == 0: 이번 프레임에 아무 일도 없었다
        f_GunErrT("G_CBPlot Not Found") + Buzz 2회, 위와 같은 지우기
elif TT[1] ≥ 1:                            # 바이트0 은 비었고 뒤 층이 남음 → 층 이동
    줄0·1·4·5·6·9·10·11 ← (TT >> 8), 줄2·3 ← 0
    줄12..14 ← TT[14..16], 줄15 ← 0; 줄16..18 ← TT[18..20], 줄19 ← 0; 줄20..22 ← TT[22..24], 줄23 ← 0
Suspend ← 0, Launch ← 0
```

- **층 사이에 빈 프레임이 하나** 생긴다: N 프레임에 층 k 완료 → N+1 에 이동만 → N+2 에 층 k+1 첫 사이클(코드 읽기, 9.1 E).
- 층 이동 뒤 남은 대기(줄3)는 0 이므로 새 층은 딜레이 없이 시작한다. 층별 딜레이는 **사이클 사이 간격**이지 시작 지연이 아니다.
- 유닛 바이트가 0 인 층은 건너뛴다. 유닛 ID 0(테란 마린)은 G_CB 로 만들 수 없다.
- 도형 번호가 0 인 층(유닛 수 > 도형 수)은 막는 코드가 없다. CAPI 는 `CA[1] == 0` 일 때 점 개수 트리거가 없어 이전 값을 쓰고, 포인터 표 0번 칸을 읽는다(코드 읽기, 결과는 추측). theSeed 는 `GunWavePattern` 이 컴파일 때 막는다(`theSeed\MapLogic\GunSystem.lua:710-716`).
- Launch 를 세우는 곳: `CA_Func1`(점 하나라도 처리, 범위 밖 포함, 1455~1460), 빈 밴드(1939~1941), 남은 대기 값이 바뀜(1957).

### 3.6 도형 등록 — `G_CB_Shapes` (GCB 2266~2293)

- `ShapeTable[1]` 이 숫자면(= 도형 한 개를 맨몸으로 줌) `{S,S,S,S}` 로 네 층에 복사한다(2266~2267). Stella 는 이것을 일부러 쓴다: `CUT[1] = {8,12,2,3}` 네 유닛을 `SH_Warp` 한 도형에 차례로(`SD\Stella_II\MapLogic\GunFunc.lua:23`).
- 표로 주면 5개 이상은 오류. i = 1..4: 처음 보는 도형 **테이블(동일성 기준)** 이면 `G_CB_Shapes[S] = {S, 번호}` 로 새 번호를 준다. **받은 표의 원소를 번호로 덮어쓴다**. 없는 층은 0.
- 번호는 1부터, 전 맵 공통. `CS_Thin` 처럼 호출마다 새 표를 만드는 함수를 그대로 넘기면 같은 모양이 번호를 여러 개 받는다(PROG 34절 원인 ①: 131 → 1,802).
- 도형 개수 = 트리거 수·용량에 직접 영향(2.5, 8.6).

---

## 4. 공개 함수

### 4.1 `G_CB_TSetSpawn(Condition, CUTable, ShapeTable, OwnerTable, CenterXY, PreserveFlag, Property)` (GCB 2260~2571)

| 인자 | 받는 것 | 기본 |
|---|---|---|
| `Condition` | 조건 목록. `{}` = 무조건 | — |
| `CUTable` | 유닛 ID/이름 최대 4개 (표 필수) | — |
| `ShapeTable` | 도형 표 최대 4개, 또는 도형 하나(4층 복사) | — |
| `OwnerTable` | 숫자 = 네 층 같은 주인, 표 = 층별. **상수만**(3.3) | FP ×4 |
| `CenterXY` | 숫자 = 로케이션 번호(1-based로 해석, 10절), 문자열 = 로케이션 이름, `{X,Y}` = 좌표, nil = 넣는 순간 `G_CB_X/Y` | nil |
| `PreserveFlag` | nil = 조건이 참인 동안 매번, 1 = 게임당 한 번 | nil |
| `Property` | 5.1 표의 키만. 모르는 키는 컴파일 오류 | nil |

**두 경로** (2514~2570):
- **평범 경로**(`G_CBPlotTOption == 0`): 스테이징 변수 대입 약 41개 + 콜 액션 5개를 **한 트리거**에 담아 `CallTriggerX(FP, Write_SpawnSet, Condition, Act, PreserveFlag)`. 조건이 거짓이면 대입도 안 한다. 값은 상수만(변수를 주면 `SetCVar` 에 표가 들어가 컴파일 오류, 추측).
- **T 경로**(속성 표에 비-V 표가 있거나 `RotateTable = V`, 또는 `T_to_ByteBuffer` 가 V 를 만남): `CDoActions(FP, T액션들, PreserveFlag)` 를 **조건 없이** 내고, `CallTriggerX(..., Condition, nil, PreserveFlag)` 를 따로 낸다. 이 경로는 `FfragMode`·`FfragAfterTimer` 를 쓰지 않는다(2552~2566 목록에 없음).
  - `PreserveFlag = 1` 이면 `CDoActions` 가 게임당 한 번(L322 1500~1504)만 돌아, 조건이 나중에 참이 될 때 **다른 호출이 덮어쓴 스테이징 값**으로 넣는다(10절 함정).
- `CallTriggerX` 플래그: nil → 보존, 1 → 비보존(L322 287~294). `CTrigger(..., 1)` 은 반대로 보존이다(CA 7238~7240). PLAN B-3 의 혼동 지점.

### 4.2 `G_CB_SetSpawn`, `G_CB_SetSpawnX` (구판 래퍼)

- `G_CB_SetSpawn(Cond, CUT, SNTable, SLTable, LMTable, RepeatType, SizeTable, CenterXY, OwnerTable, PreserveFlag, NQOpTable)`(GCB 2057~2092): G_CA 서명 흉내. `SNTable == "ACAS"` 면 `_G[SLTable[j]]`(이름으로 전역 도형), 아니면 `SNTable[j][SLTable[j]+1]`(계열 배열 + 단계) 이고 이때 **FN = 1(무작위 정렬)을 자동으로 켠다**.
- `G_CB_SetSpawnX(Cond, CUT, ShapeTable, LM, RepeatType, Delay, Size, FN, CenterXY, Owner, Preserve, NQOp)`(2098~2112): 속성 표로 바꿔 `G_CB_TSetSpawn` 을 **5인자(구판 서명)** 로 부른다.
- **신판(STL/TPL/GCB/MEME)에서는 둘 다 컴파일이 멈춘다**(코드 읽기): 7인자 `G_CB_TSetSpawn` 에 넘어가면서 속성 표가 `CenterXY` 자리에 들어가 `#CenterXY ~= 2` → `CenterXY_TableError`(2334). 게다가 `OwnerTable`·`NQOpTable`·`CenterXY` 키는 신판에서 "Wrong Property Name" 이다. 실제 호출은 구판 ResV(160+128)와 UERE(자기 판, 233)뿐이다.

### 4.3 `G_CB_SetSpawn2X(Cond, CUT, ShapeTable, AfterTimer, EffType, Color, CenterXY, Owner, PreserveFlag, Property)` (GCB 2151~2187)

"기억의 조각(Ffrag)": 도형 점마다 유닛 116(알)을 만들고, 알이 죽을 때 맵 쪽이 `CUT` 의 유닛을 뽑는다.
- `CUT` = `{{유닛, 수}, …}` 최대 20개 → `FfragMode`. `AfterTimer` → `FfragAfterTimer`(알 수명). `EffType` → `EffID`(알 이미지). `Color` → 색 3종(4.4 계산).
- `G_CB_TSetSpawn(Cond, {116}, {ShapeTable}, Owner, CenterXY, PreserveFlag, PP)`.
- 받은 `Property` 표를 **그대로 고쳐 쓴다**(PP = Property).
- 알이 죽을 때의 처리는 맵에 있다: Stella `MapLogic\System.lua:1700-1723`(EXCC 10~14 줄 유닛 묶음 × 15~19 줄 수 → `f_TempRepeatX` 로 알 자리에 소환, RepeatType = 20줄, 명령 = 21~23줄), 알 이동은 같은 파일 1160~1177(UnivCunit 10줄 LPos 로 목적지).

### 4.4 `G_CB_TScanEff(Cond, ShapeTable, CenterXY, ScanEffID, PreserveFlag, Property, Color, Player)` (GCB 2115~2150)

- 도형 수만큼 유닛 33(스캐너 스윕)을 층으로 만든다. `Player` 기본 P8.
- `Color` 가 있으면: `a = 0x669E28 + ScanEffID`(images.dat Draw Function 칸, `SetImageColor` 와 같은 주소 CA 81788), `r = a % 4`, 마스크 `0xFF << 8r`, 값 `Color << 8r`, `EffColorMem = EPDF(a - r)`.
- 받은 `Property` 표를 고쳐 쓴다.
- 사용: MEME 183회뿐(`MSF_MEME_EUD\GunTrig.lua:329` 등).

### 4.5 직접 소환 — `f_TempRepeat` 계열

대기열을 거치지 않고 **그 자리에서** `Number` 기를 만든다(`Set_Repeat` → `Call_Repeat`).

| 함수 | 서명 | 차이 |
|---|---|---|
| `f_TempRepeat` (GCB 954~1016) | `(Condition, UnitID, Number, Type, Owner, CenterXY, Flags, NQOp, ROrder)` | 상수만. 대입 액션을 `CallTriggerX` 한 트리거에 담는다(조건이 참일 때만 대입). `Flags` = 보존 플래그 |
| `f_TempRepeatX` (1020~1090) | 같은 서명 | 유닛·수·중심·주인에 V 허용(T 액션, **조건 없이** 대입). `ROrder[1]` 도 V 허용. 유닛 이름 변환이 `Type == nil` 일 때만 되는 위치 버그(1023~1027) |
| `f_TempEffRepeatX` (1092~1163) | `(Condition, ScanEffID, Color, Type, Owner, CenterXY, Flags, NQOp)` | 유닛 33 스캔 이펙트 1개. **전역 `PP` 를 공유**해 호출 사이에 값이 샌다. 사용 0회 |
| `f_TempRepeat2X` | Mem2 `func.lua:1086` | G_CB_Lib 에 없음(1.1) |

인자 해석:
- `UnitID`: 번호 또는 이름. 256 이면 아무것도 안 만든다(1168).
- `Type`: RepeatType 번호/이름. nil = 0.
- `Owner`: nil → `0xFFFFFFFF` → 소환 때 `G_CB_CPlayer`(850).
- `CenterXY`: `{X,Y}` 좌표(V 가능은 X판만) / nil·`"CG"` → **둘 다 `G_CB_X/Y`**(`0x7FFFFFFB` 이상이면 같은 가지, 669~673) / 숫자·문자열 → `TRepeatX = ConvertLocation 의 0-based 값`, `TRepeatY = 0x32223222`(로케이션 표식) → `TGetLocCenter(TRepeatX)` 가 그 값을 1-based 로 쓴다(오프바이원, 10절). 로케이션 모드는 결과를 `G_CB_X/Y` 에 덮어쓴다(661).
- `ROrder`: `{Attack|Patrol|Move, X, Y}` 또는 `{…, 로케이션}`(→ `OrderY = 0x32223222`). 그런데 `Call_Repeat` 은 **중심 표식(`TRepeatY`)** 을 보고 `TGetLocCenter(Repeat_OrderY, …)` 를 부른다(646~648) — 명령 로케이션 모드는 동작하지 않는다(코드 읽기).
- `NQOp`: `NQOption` 에 넣지만 직접 소환 경로에서는 읽지 않는다.

### 4.6 프리펑션 — `G_CB_Prefunc()` (GCB 1498~1713)

`CAPlotIndexed` 가 매 호출 시작 때 `_G[Prefunc]()` 로 부른다(CAPI 216~218).
- `CB_initTCopy()`(1500~1533): 선언 블록(`CB_PrfcInit` CJump, 1610~1613) 안에서 도형별 X/Y 파일 배열 주소표 `CBPlotFXArr/FYArr` 와 점 개수표 `CBPlotFNum` 을 `f_GetVoidptr(…, 바이트 수)` 로 만든다. `CBPlotNumHeader` = 점 개수 헤더.
- `CB_TCopy(Shape, RetShape)`(1535~1602): 런타임에 도형 Shape 의 좌표·개수를 RetShape 로 복사(CB Paint 내부 콜 `FCBCOPYCall1/2`).
- `CB_RandSort()`(1619~1645): `CalcX, CalcY ∈ [-100, 99]`, `CalcA ∈ [0, 359]`, `NG` = 스위치 난수, `DirRand = f_CRandNum(2)`(정렬 방향), `FncRand = f_CRandNum(3)` → `CB_Sort(CFunc1, DirRand, STSize+2, EndRetShape)`. CFunc1(1470~1490): FncRand 0 = `x·CalcX + y·CalcY − 100`(NG 면 절댓값), 1 = `√(x²+y²)`, 2 = `(|atan2(y,x)| + CalcA) mod 360`. 즉 "무작위 방향에서 쓸어 오기 / 안팎 / 회전 시작각".
- `CB_MarNumFill()`(1646~1666): 이름과 달리 반지름 정렬(`CFunc2`)만 한다(방향 무작위). `local MarNum = CreateVars(FP)` 는 AllPlayers 변수 7개를 만든다(PROG 2496).
- 실행(1676~1709):
  1. `TT[2] & 0xFF ≥ 1` 이면 `CB_TCopy(CA[1] → STSize+2)` → 번호에 맞는 함수 → `CB_TCopy(EndRetShape → EndRetShape + G_CB_Num)` → `CA[1] = TT[13] = EndRetShape + G_CB_Num`(레코드 전용 도형). LM 바이트가 0 이면 `LM = 정렬된 점 수 // 50 + 1`.
  2. `TT[5] & 0xFF == 0`(LM 자동)이면 등록 도형마다 트리거 하나: `TT[13] & 0xFF == j` → `LM = k[1]/50 + 1`(Lua 실수 → TEP 자르기 = `n//50 + 1`). **도형 번호를 0xFF 로 가려 비교**한다(10절).
  3. `CA[5] = TT[5] & 0xFF`, `TT[2]` 바이트0 ← 0 (프리펑션은 층마다 한 번).
- 제약: 작업 도형 칸은 1,699점짜리라 그보다 큰 도형은 프리펑션을 못 탄다(추측). LoopMax 스케줄과 함께 못 쓴다(`theSeed\MapConfig\Shape.lua:891-892`).

### 4.7 `AutoSetV(ActT, T)` / `TAutoSetV(ActT, T)` (GCB 2572~2585)

`T = {{변수, 값}, …}` 를 `SetCVar`/`TSetCVar` 로 바꿔 `ActT` 뒤에 붙인다. 속성 → 스테이징 변수 대입용.

### 4.8 `CA_Func1()` (GCB 1401~1464)

`CAPlotIndexed` 가 점마다 부르는 CAfunc. 6.3 참고. 끝에서 범위 안이면 `TempLoc` 을 그 점(크기 0 상자)으로 옮기고 `Call_CA_Repeat` 를 부른다.

### 4.9 내부 콜

| 콜 | 줄 | 하는 일 |
|---|---|---|
| `Call_CA_Repeat` | 1385~1397 | `CA_TempUID ≥ 221` 이면 0, `CA_Repeat_Check = 1`, 유닛·수(1)·RepeatType(TT[6]&0xFF)·주인(TT[10]&0xFF) 설정 → `Set_Repeat`. (94·4 제한 줄은 수가 항상 1 이라 죽은 코드) |
| `Set_Repeat` | 1165~1175 | 유닛 256 이면 수 0. 수 ≥ 1 이면 `Spawn_TempW = 수` → `Call_Repeat` |
| `Call_Repeat` | 636~950 | 6.5 |
| `Call_RepeatOption` | 223~632 | 6.6 |
| `Call_Calc_NSpeed` | 201~221 | 유닛 좌표 − (명령 목표 또는 작업 중심) = d, `speed = √((dx²+dy²)/4)`. 회전반경 127, 최고속도·가속도 = speed. `TempLoc2` 를 목표점으로 |

### 4.10 맵이 만지는 손잡이

| 이름 | 뜻 |
|---|---|
| `G_CB_X`, `G_CB_Y` | 중심 생략·`"CG"` 의 기준. theSeed 건작 본체가 슬롯마다 건물 좌표를 넣는다(`theSeed\MapLogic\GunSystem.lua:1049-1051`, `CorpseFlower.lua:155-156`) |
| `G_CB_RotateV` (`G_CB_RotateV2` 구판) | `RotateTable = "Main"`(`"Main2"`)의 회전각. 점마다 읽는다(ResV `System.lua:1358-1359`, MEME `GunTrig.lua:102,658`) |
| `G_CB_CPlayer` | 직접 소환에서 주인 생략 시 |
| `CA_Eff_XY/YZ/ZX` | 3D 옵션 각 |
| `UnitIDV1~4` | 유닛 자리표 221~224 의 실제 값 |
| `G_CB_RepeatTypeExtraDefs` | RepeatType 표 확장(GCB 10~15, 597~599) |
| `G_CB_SpawnUnclickableUnits` | `{{UnitID, ImageID}, …}` 0틱 클릭 불가(GCB 42~59) |
| `G_CB_LoopSchedule` | 도형 표 → `{밴드 수, c1, c2, …}`(`theSeed\MapConfig\Shape.lua:905-906`) |
| `GunUseIndexedPlot` | CAPlotIndexed ↔ CBPlot |
| `GCBDebugText` | 계측 3곳(플롯 호출·CBPlot 직후 레지스터·CA 호출 수와 좌표) |

---

## 5. 속성 표

### 5.1 신판 `G_CB_TSetSpawn` 속성 15종 (GCB 2346~2512)

"T" = 이 모양을 주면 T 경로(4.1). "층별" = 층마다 다른 값을 저장할 수 있나.

| # | 키 | 받는 값 | 기본 | 줄 | 층별 | 런타임 의미 |
|---|---|---|---|---|---|---|
| 1 | `LMTable` | `"MAX"` → −1(모든 층 255) / 숫자 k → k×4 / 숫자 표(T) / V → 컴파일 오류(추측) | 0 | 4 | 예(1B) | 한 사이클에 찍을 최대 점 수. **0 = 자동 `n//50+1`**(4.6). 스케줄이 있는 도형은 스케줄이 덮어씀 |
| 2 | `Delay` | 숫자·V → 네 층 같게 / 표 → 층별(T) | 0 | 16~19 | 예 | 한도만큼 찍은 뒤 쉴 프레임 수(CA[3]). 0 과 1 은 같다(6.2) |
| 3 | `SizeTable` | 숫자 → ×4 / 숫자 표(T) / V → 오류(추측) | 100 | 10 | 예(1B, 0~255) | 퍼센트. 100 이 아니면 `x·s/100`(0 방향) |
| 4 | `RotateTable` | 숫자 → 네 층 같게 / `"Main"` → 0xFFFFFFFF / V → 네 층 같게(T) / 표 → 오류(추측) | 0 | 20~23 | 저장은 층별, 입력은 같은 값 | 0 = 안 돎, 0xFFFFFFFF = `G_CB_RotateV`, 그 밖 = 각도(Cycle 360). −1 은 "Main" 과 구별 불가 |
| 5 | `RepeatType` | 숫자·이름 → ×4 / 표(이름·숫자, T) | 0 | 5 | 예(1B) | 소환 직후 행동(6.6). 모르는 이름은 조용히 0 |
| 6 | `Order` | `{Attack\|Patrol\|Move, X, Y}` / `{…, 로케이션}` | 없음 | 30~32 | 아니오 | 모든 층 유닛에 명령. RepeatType 의 기본 명령을 끈다(6.6). 로케이션은 넣는 순간 중심 |
| 7 | `DistanceXY` | `{dx, dy}` | `{0,0}` | 24, 25 | 아니오 | 회전 뒤 더하는 평행이동 |
| 8 | `FNTable` | 숫자 → ×4 / 표(T) | 0 | 1 | 예(1B) | 프리펑션 1 = 무작위 쓸기, 2 = 반지름 정렬 |
| 9 | `Rotate3D_Option` (MEME·구판: `NQOpTable`) | 숫자 → ×4 / 표(T) | 0 | 11 | 예(1B) | 1 이면 `CA_Rotate3D(CA_Eff_XY, CA_Eff_YZ, CA_Eff_ZX)`. 원래 이름 "Use Queue Option"(생성 대기열 사용) |
| 10 | `EffID` | 숫자·V | 0 | 26 | 아니오 | 33: 스캐너 스프라이트 이미지. 116: 알 이미지 |
| 11 | `EffColorMem` | EPD | 0 | 27 | 아니오 | Draw Function 칸 EPD(4.4) |
| 12 | `EffColor` | 값 | 0xFFFFFFFF | 28 | 아니오 | `≤ 0x7FFFFFFF` 일 때만 색을 바꾼다 |
| 13 | `EffColorMask` | 마스크 | 0 | 29 | 아니오 | |
| 14 | `FfragMode` | `{{유닛, 수}, …}` 최대 20 (빈 자리 `{0,0}` 로 채움) | 0 | 33~42 | 4개씩 5줄 | 알이 죽을 때 뽑을 목록(맵 처리). **CUT 에 116 필요** |
| 15 | `FfragAfterTimer` | 숫자 | 500 | 43 | 아니오 | 알 removeTimer(하위 16비트) |
| — | 그 밖의 키 | | | | | `"Wrong Property Name : 키"` 컴파일 오류(2510) |

### 5.2 위치 인자

| 인자 | 기본 | 줄 | 의미 |
|---|---|---|---|
| `OwnerTable` | FP×4 | 9 (1B) | 층별 주인. 0~255 |
| `CenterXY` | nil | 7, 8 | 3.4-6 |
| `PreserveFlag` | nil | — | 4.1 |

### 5.3 다른 판의 속성

| 판 | 키 | 신판과 다른 점 |
|---|---|---|
| 구판 RSV (1494~1599) | `LMTable`, `Delay`, `SizeTable`, `FNTable`, `NQOpTable`, `RepeatType`, `RotateTable`, `CenterXY`, `OwnerTable` | `RotateTable` 층별 표(`{0,90,…}`) 허용, `"Main2"` → 0xFFFFFFFE → `G_CB_RotateV2`(RSV 919~920). `CenterXY` 는 좌표만. **모르는 키 무시**. T 경로는 V 원소로만 켜진다 |
| UER `G_CB_SetSpawnX` (1372~1416) | `FNTable`, `PFTable`, `RPTable`, `LMTable`(기본 255), `CenterXY`, `Owner`, `Delay`, `PreserveFlag` | PF = 크기 단계(`PlotSizeCalc`) 전처리, 층별 각도 줄(14) |

신판 15 + 신판에 없는 키 7(`NQOpTable`, `OwnerTable`, `CenterXY`, `PFTable`, `RPTable`, `Owner`, `PreserveFlag`) = **22종**.

### 5.4 RepeatType 표 (GCB 441~590, 체인 순서 그대로)

소환 성공(에너지 상위 바이트 ≥ 150, 6.6) 뒤 `RType` 으로 if/elseif 를 위에서부터 훑는다. 공통 헬퍼: `LocHere` = 유닛 좌표 2×2 상자를 `TempLoc` 에, `LocCenter` = 작업 중심을 `TempLoc2` 에, `DefaultOrder(종류, 목표)` = **명령 속성이 없을 때만**(`Repeat_OrderType == 0`) `TOrder(RUID, RPID, TempLoc+1, 종류, 목표)`(GCB 179~199).

| 번호 | 이름 | 하는 일 | 분류 |
|---|---|---|---|
| 0 | (기본) | `LocHere`, `DefaultOrder(Attack, DefaultAttackLoc)`, 회전반경(+0x22) 127 | **일반** |
| 2 | (이름 없음) | 없음 | 일반(예약) |
| 3 | `KillUnit` | `TKillUnit(RUID, RPID)` — **로케이션 없이 그 주인의 그 유닛 전부** | 일반(이펙트 정리용) |
| 5 | `RemoveTimer` | removeTimer(+0x110) = 250 | 일반 |
| 6 | `Nothing` | 없음 | 일반 |
| 130~137 | `IC1~4`, `GB1~4` | P9 로 `f_CGive`, 무적(+0xDC 0x04000000), +0x26 = 0, 기생 0xFF, UnivCunit 칸 설정 | theSeed/Stella 전용 |
| 175 | `XelNaga` | 없음(116 경로에서 특별 취급) | 맵 전용 |
| 180 | `Vision` | 기생 플래그(+0x121) = 0xFF | 일반 |
| 178, 179 | `Wait_130_P9/P10` | 무적, 기생, 속도·가속도, 회전반경, 난이도 체력, `f_CGive` 로 P9/P10, EXCC 회차 표식 | theSeed 전용 |
| 176 | `XelNaga_Show` | 난이도 체력 | theSeed 전용 |
| 177 | `Gun_Home` | 0 번 + 난이도 체력 | theSeed 전용 |
| 106 | `NXCT` | 회전반경 127, 속도·가속도 128, 작업 중심으로 어택(명령 속성 무시) | 일반 |
| 201 | `Cocoon_NoSpeed` | 회전반경 127, 속도·가속도 1 | 일반 |
| 147 | `Attack_Target_NSpeed` | `Call_Calc_NSpeed` 후 목표로 어택(명령 속성과 무관하게) | 일반 |
| 148 | `Wait_Target_NSpeed` | `Call_Calc_NSpeed` 만 | 일반 |
| 7 | `Patrol_Center` | `DefaultOrder(Attack, 작업 중심)` — **이름과 달리 어택** | 일반 |
| 187 | `JYD` | orderID(+0x4D) = 187 직접 씀 | 일반 |
| 188 | `JYD_After_Timer_Attack` | 187 + UnivCunit 타이머 칸 | 맵 전용 |
| 8 | `SkillUnit` | `DefaultOrder(Patrol, DefaultAttackLoc)`, 회전반경 127, removeTimer 15 | 일반 |
| 181 | `Home_Vision` | 0 번 + 기생 0xFF | theSeed 전용 |
| 그 밖 | | 오류 문구 + Buzz 3회 | |

체인 앞뒤(GCB 227~312, 617~624): 유닛 54 특수(생성 전 EXCC), 40 번 removeTimer 0(theSeed), RType 54~56 → EXCC 표식 후 RType 0, 유닛 83(리버) 스캐럽 1개(`TModifyUnitHangarCount(1,1,83,RPID,1)` — 로케이션 인자가 **1 고정**, 10절), 끝에 명령 속성 처리.

**맵마다 다른 표**(`gcb_usage.py` 로 뽑은 이름): ResV = `Guard(2)`, `Attack_HP10(5)`, `BanUnit(6)`, `Attack_HP50(1)`, `Attack_HP25(7)`, `Attack_Cell(168)`, `JYD(187)`, `JYD_HP10(188)`, `Gene1~3/EnemyStorm(200~203)`, `gMAX1/2`, `Explosion_Guard(84)`, `Era_*(129~134)`, `Timer_Attack(3)`, `Timer_Attack_Gun(4)`, `Attack_Gun(14)`, `Patrol_Gun(140)`, `Walls(217)`, `MAXHP(218)`. MEME = `Attack_Parasite(127)`, `KillUnit(3)`, `RemoveTimer(5)`, `Nothing(6)`, `Patrol_Center(7)`, `SkillUnit(8)`. **같은 번호(5, 6, 7)가 맵마다 뜻이 다르다.**

---

## 6. 매 프레임 알고리즘 (`Call_G_CBPlot` + `CAPlotIndexed` + 소환 콜)

### 6.1 작업 선택

레코드 0 → 127 순서로, 살아 있는 레코드마다 지금 층(바이트 0) 하나를 진행한다(3.5). 한 레코드 안의 층은 차례로만 진행된다.

### 6.2 층 진행 (GCB 1797~1987, CAPI 216~411)

작업 변수 적재(1797~1879): `TT[17]`(지금 층 딜레이) == 0 이면 `TT[4] = 0`. `CA[1]` = 도형(TT[13]), `CA[3]` = 딜레이, `CA[2]` = 남은 대기(TT[4]), `CA[6]` = 진행(TT[3]), `CA[5]` = LM(TT[5]&0xFF), 이펙트·명령·Ffrag 전달 변수, `G_CB_BackupX/Y` = 중심.

한 프레임(참조 모델 `gcb_ref.py timeline()`):

```
L = LM (0 이면 프리펑션 단계에서 n//50+1 로 바뀜)
if 도형에 스케줄: L = sched[ptr];  if sched[0] > ptr and w == 0: ptr += 1     # CAPI 301~304
while w == 0:
    if c < L and p < n and n ≥ 1 and L ≥ 1:
        점 p 읽기 → CA_Func1 (6.3~6.5) → c += 1, p += 1
    else:
        w = D (딜레이), c = 0, 반복 끝                                      # CAPI 384~385
if p ≥ n: p = 0, ptr = 1, Suspend += 1                                      # 완료 (CAPI 399~407)
w = max(w − 1, 0)                                                           # 포화 뺄셈 (CAPI 411)
```

- D = 0 과 D = 1 은 **둘 다 매 프레임 한 사이클**, D = k(≥2) 는 k 프레임에 한 사이클.
- 첫 사이클은 층이 시작한 프레임에 바로 돈다.
- 스케줄 포인터 `ptr` 은 **작업별로 저장되지 않는다**: `CMov(ptr, 1)` 이 플롯 몸 안(CAPI 235~237)에 있어 매 호출마다 1 로 돌아간다(코드 읽기). 그래서 실제로는 매 사이클 `sched[1]` 개씩 찍힌다고 읽힌다. 의도(주석 CAPI 232~234)는 "소환 시작 때만 1". 인게임에서 페이드는 정상으로 보고됐다(`theSeed\MapConfig\Shape.lua:896-900`, PROG 35절) — 밴드 크기가 비슷하면 겉으로 차이가 작다(추측).
- 빈 밴드(L = 0) 사이클은 Launch 를 세워 작업을 살린다(GCB 1939~1941).
- 끝에 진행·남은 대기를 TT[3]·TT[4] 로 저장(1987) → `Call_G_CB` 가 레코드에 되씀.

### 6.3 점 변환 (`CA_Func1`, GCB 1401~1464)

점 (x, y) = 도형 좌표(컴파일 시점 실수를 TEP 가 0 방향으로 자른 32비트 정수, `f_SHRead` 로 부호 있게 읽음, CAPI 327~328). 순서:

1. **크기**: `S = TT[11] & 0xFF`. `S ≠ 100` 이면 `x = CiDiv(x·S, 100)`, `y = CiDiv(y·S, 100)`(곱은 32비트, 나눗셈은 0 방향; CBP 9718~9750).
2. **회전**: `R = TT[21]`(지금 층, dword). `R ≥ 1`(부호 없음)이면 `R == 0xFFFFFFFF` → `G_CB_RotateV`, 아니면 R 으로 `CA_Rotate(θ)`:
   `(xc, xs) = lengthdir(x, θ)`, `(yc, ys) = lengthdir(y, θ)`, `x' = xc − ys`, `y' = xs + yc`(CBP 9865~9881).
3. **3D**: `NQOption == 1` 이면 `CA_Rotate3D(XY, YZ, ZX)`(CBP 9883~9932): XY 로 2 와 같은 회전 → YZ: `(y, z) = lengthdir(y, YZ)` → ZX: `x = lengthdir(x, ZX).cos − lengthdir(z, ZX).sin`. CA[11~14] 를 덮어쓴다.
4. **평행이동**: `x += dx`, `y += dy`(TT[25], TT[26]).
5. **중심**: `X = x + TT[8]`, `Y = y + TT[9]`(32비트).
6. **경계**: `X ≤ W−1` 이고 `Y ≤ H−1`(부호 없는 비교라 음수도 걸러짐)일 때만 `TempLoc = (X, Y, X, Y)` 로 옮기고 소환 콜. 밖이면 **그 점은 건너뛰고 진행으로 친다**(Launch 도 세움).
7. 그 뒤 CAPI 는 `CA[8],CA[9]` 에 중심을 더하고 `TempLoc` 을 ±32 로 옮겨 `TCreateUnit(1, nilunit, TempLoc, FP)` 를 한 번 더 실행한다(CAPI 347~368). theSeed `nilunit = 181` 이라 실패하는 생성으로 추측한다. eudext 는 넣지 않는다.

`f_Lengthdir(r, θ)` (Cycle C = 360, Q = C/4, CA 84377~84479):
- `T[i] = trunc(0x10000 · sin(i·90/Q °))`, i = 0..Q (TEP 가 실수 액션 값을 0 방향으로 자름. T[30] = 32767, T[45] = 46340, T[90] = 65536).
- θ ≥ C(부호 없음)이면 `θ = CiMod(θ, C)`(피제수 부호), 그 뒤 θ ≥ 0x80000000 이면 `θ += C`.
- 사분면: θ < Q → (cs, ss, si, ci) = (0, 0, θ, Q−θ); < 2Q → (1, 0, 2Q−θ, θ−Q); < 3Q → (1, 1, θ−2Q, 3Q−θ); 그 밖 → (0, 1, 4Q−θ, θ−3Q).
- `sin = CiDiv(r·T[si], 0x10000)`, `cos = CiDiv(r·T[ci], 0x10000)`(곱은 32비트 부호 있는 값), cs/ss 면 부호 반전. |r| ≤ 32767.

**각도 기준(D5)**: 런타임 회전은 CtrigAsm CA_ 기준 — 0 = +x, 양의 각은 화면에서 **시계 방향**. 정적 도형(CB Paint, 0° = 12시)과 기준점은 90° 다르지만 **회전 방향은 같다**(R4b B3: `CS_Rotate` 45 가 시계 방향). 결과 값은 항마다 따로 잘라서 실수 회전과 다르다(9.2).

### 6.4 중심 모드 (넣는 순간 해석, 3.4)

| 입력 | 저장 값 | 해석 시점 | 결과 |
|---|---|---|---|
| nil | X=Y=0xFFFFFFFF | 넣을 때 | `G_CB_X/Y` 값 복사 |
| 숫자 N | `(N+1)+0x80000000` → `−0x80000001` = N | 넣을 때 | `TGetLocCenter(N)` — N 을 1-based 로 씀 |
| 문자열 | `(0-based+2)+0x80000000` → 1-based | 넣을 때 | 그 이름 로케이션 중심 |
| `{X, Y}` | 그대로 | — | 좌표(0~0x7FFFFFFF) |

`TGetLocCenter(L, X, Y)`(L322 1237~1245): 작업 로케이션을 (0,0,0,0) 으로 만들고 `TMoveLocation(작업, nilunit, FP, L)` 한 뒤 작업 로케이션의 왼쪽·위를 읽는다. 대상 유닛(nilunit)이 없을 때 SC 가 목적 로케이션 중심으로 옮긴다는 동작에 기댄다(추측 — 이 조사에서 확인 못 함). CAPI 의 숫자 중심 모드는 `(L+R)/2, (U+D)/2`(0 방향)로 직접 계산한다(CAPI 307~315).

### 6.5 소환 — `Call_Repeat` (GCB 636~950)

`Spawn_TempW` 번 반복한다(대기열 경로는 1).

1. `DefaultAttackLocV = DefaultAttackLoc`.
2. 직접 소환 경로(`CA_Repeat_Check == 0`)면 명령·중심을 풀어 `TempLoc` 을 정한다(645~674, 4.5).
3. 대기열 경로(`== 1`)면 `TempLoc` 의 왼쪽·위를 읽어 `QueueX/Y`, `CA_Repeat_X/Y` 에 둔다(680~693).
4. 유닛이 0~226 일 때:
   - **33 (스캔 이펙트)** 6.7
   - **116 (알)** 6.8
   - **그 밖**(838~910):
     1. `0x628438 ≥ 1`(빈 유닛 슬롯이 있음)일 때만 진행.
     2. `G_CB_Nextptrs` = 다음 유닛 EPD(`f_Read(FP, 0x628438, ptr, epd, 0xFFFFFF)`, CA 36149). 그 유닛의 +0x26 바이트 = 0(EXCC 잠금 해제, `theSeed\MapLogic\CunitSystem.lua:135,190`). 색인 `(epd−19025)/84` → ×604 → `Call_EXCC_AllReset`(그 슬롯의 EXCC 전부 0).
     3. 주인이 0xFFFFFFFF 면 `G_CB_CPlayer`.
     4. RepeatType 130~133 이면 점을 맵 중앙 기준 점대칭 자리로 옮겨 소환하고, 원래 점으로 **이동 명령**(명령 종류 3)을 건다(868~889).
     5. `TCreateUnitWithProperties(1, 유닛, TempLoc+1, 주인, {energy = 100})`(897; 인자 순서 CA 14521).
     6. `RUID/RPID/RType/RPtr/RPtrP/RLocV/RUI2` 를 채우고 `Call_RepeatOption`(6.6).
     - 생성 실패(자리 없음 등)여도 `RPtr` 은 그 빈 슬롯을 가리킨 채 6.6 으로 간다. 6.6 의 에너지 검사가 사실상 "생성 성공" 판정이다(코드 읽기).
5. 직접 경로면 `TempLoc` 을 다시 중심으로(919~936). 대기열 경로에서 수 ≥ 2 면 `TempLoc = CA_Repeat_X/Y`(943~945).
6. `Spawn_TempW -= 1`. 반복이 끝나면 `RepeatType = 0`(949).

### 6.6 소환 뒤 처리 — `Call_RepeatOption` (GCB 223~632)

1. 유닛 54 이고 에너지 상위 바이트(+0xA3) ≤ 149 → EXCC 표식, RType 0(맵 전용).
2. **에너지 상위 바이트 ≥ 150**(= 에너지 100% 로 방금 생성됨)일 때만:
   1. 40 번 removeTimer 0(theSeed 전용), RType 54~56 EXCC 표식(맵 전용).
   2. 유닛 좌표를 `CPos` 로(`f_Read(RPtr+10)` → `Convert_CPosXY`).
   3. 유닛 83 이면 스캐럽 1개.
   4. RepeatType 체인(5.4). 표에 없으면 오류 문구 + Buzz 3회.
   5. **명령 속성**(`Repeat_OrderType ≥ 1`): `TempLoc` = 유닛이 선 자리 2×2, `TempLoc2` = 명령 좌표 2×2 → `TOrder(RUID, RPID, TempLoc+1, Attack|Patrol|Move, TempLoc2+1)`(617~624; 인자 순서 CA 15525).
   - `TOrder` 는 **그 상자 안의 같은 종류·같은 주인 유닛 전부**에 명령한다(겹쳐 선 다른 유닛도 받는다).
   - 명령 목표는 **넣는 순간** 구한 좌표다(로케이션 모드도 넣을 때 중심). 기본 명령의 `DefaultAttackLoc` 은 **명령 순간의** 로케이션이다.

### 6.7 스캔 이펙트 (유닛 33, GCB 700~727)

빈 슬롯이 있을 때: +0x26 = 0, EXCC 초기화 → 색(`SendEff[2] ≤ 0x7FFFFFFF`)이면 `SendEff[1]` 칸을 읽어 두고 새 값 씀 → 한 트리거에 `SetMemoryX(0x666458, EffID, 0xFFFF)`(스캐너 스윕 스프라이트의 이미지 칸, 원래 값 546 — DPS `CallTriggers\level\level_up.lua:205` 에 같은 관용구) + `CreateUnitWithProperties(1, 33, TempLoc, 주인)` + `KillUnit(33, 주인)` + 이미지 546 복구 → 색 복구. RepeatOption 은 안 탄다.
- `KillUnit(33, 주인)` 은 그 주인의 스캐너 스윕을 **전부** 죽인다(주인이 사람이면 진짜 스캔도 사라진다).

### 6.8 기억의 조각 (유닛 116, GCB 729~835)

빈 슬롯이 있을 때: +0x26 = 0, EXCC 초기화 → 이미지 `EffID` 의 iscript(`0x66EC48 + EffID*4`)를 읽어 두고 → 색 → `TempLoc` = **작업 중심**(RepeatType 175 면 점) → 한 번에 `SetMemoryX(0x6663C4, EffID, 0xFFFF)`(116 의 스프라이트 이미지 칸, 추측) + iscript = 165 + 생성 + iscript 복구 + 상태 플래그 `|= 0xA00000`(+0xDC; BWAPI 이름으로 NoCollide|IsGathering, 추측) + removeTimer = `FfragAfterTimer` → 색 복구 → `LPos = QueueX | QueueY<<16`(175 면 0), 16비트 칸마다 `≥ 32768 → 0`, `W ≤ v ≤ 32768 → W−1`(Y 는 H) → DUnitCalc 10~14 = 유닛 묶음, 15~19 = 수, 20 = RepeatType, 21~23 = 명령, 5·6 = 점 좌표, UnivCunit 10 = LPos. 알이 점으로 날아가고, 죽을 때 맵이 소환한다(4.3).

### 6.9 완료·보존·오류

- 층 완료 = `CA[6] ≥ CA[10]` → Preserve 액션(`Suspend += 1`, 진행 0, ptr 1). 레코드는 3.5 대로 층을 지우고 모든 층이 끝나면 55줄을 지운다.
- CBPlot 의 Preserve 는 "도형을 다시 처음부터" 라는 뜻이지만, G_CB 는 Suspend 를 완료 신호로 쓰므로 **반복 재생은 없다**. 반복은 호출 자리(보존 플래그 nil + 조건)로 만든다.
- "G_CBPlot Not Found": 한 프레임에 점도 대기 변화도 없으면(예: 점 0개 도형 + 딜레이 ≤ 1, LM 0 + 스케줄 없음) 문구 + Buzz 후 층을 버린다.
- LM 0 이고 스케줄이 없는데 딜레이 ≥ 2 면 남은 대기가 매 프레임 바뀌어 Launch 가 서므로 **영원히 끝나지 않는다**(코드 읽기).

### 6.10 0틱 클릭 불가 (GCB 1885~1942)

지금 층 유닛 바이트가 목록의 UnitID 이면 플롯 직전에 `SetMemoryB(ImagesDatClickableAddr + ImageID, 0)`, 직후에 1. SC 가 생성 순간의 값을 유닛 이미지에 복사하므로 그 창에서 만든 유닛만 클릭이 안 된다. 조건을 RepeatType 이 아니라 유닛 바이트로 하는 이유는 `Call_Repeat` 이 끝에서 RepeatType 을 0 으로 만들기 때문이다.

### 6.11 실행 비용 (추정)

기본 경로(RepeatType 0, 크기·회전 없음) 점 하나에: 좌표 `f_SHRead` 2회, `Call_CA_Repeat`/`Set_Repeat`/`Call_Repeat` 트램펄린, 로케이션 되읽기 `f_SHRead` 2회, `0x628438` `f_Read`, 색인 계산 `_Div`·`f_Mul`, EXCC 초기화, 생성, 좌표 `f_Read`+`Convert_CPosXY`(`f_Div`) 2회, RepeatType 선형 비교 약 20, 로케이션 T 액션 여러 번. CtrigAsm 32비트 읽기 한 번이 수십 트리거이므로 **점당 약 400~500 트리거 실행**으로 추정한다(측정 안 함). LM "MAX" 면 한 프레임 최대 255점.

---

## 7. 실제 사용

### 7.1 호출 수 (`gcb_usage.py`, 주석 제외, 라이브러리 사본 몸체 제외)

| 함수 | Seed | Stel | ResV | Mem2 | G2R | UERE | Brz | MEME | 합 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `G_CB_TSetSpawn` | 14 | 51 | 477 | | | | | 420 | 962 |
| `G_CB_SetSpawn` | | | 160 | | | 233 | | | 393 |
| `G_CB_SetSpawnX` | | | 128 | | | | | | 128 |
| `G_CB_SetSpawn2X` | | 52 | | | | | | | 52 |
| `G_CB_TScanEff` | | | | | | | | 183 | 183 |
| `f_TempRepeat` | | 56 | 50 | 4 | 1 | 118 | 68 | | 297 |
| `f_TempRepeatX` | | 10 | 43 | 10 | 7 | 2 | | | 72 |
| `f_TempRepeat2X` | | | | 15 | | | | | 15 |
| `f_TempEffRepeatX` | | | | | | | | | 0 |
| `G_CA_SetSpawn` | | | | 103 | 162 | | 44 | | 309 |

- R1 의 "`G_CB_TSetSpawn` 542/420" 과 일치한다(542 = Seed+Stel+ResV).
- Seed 의 14 는 **글자 그대로의 호출 수**다. theSeed 는 `Spawn()`, `GunWavePattern` 같은 도우미 안에서 부르고, 그 도우미가 CIf 가지마다 호출을 펼치므로 실제 트리거 호출 자리는 훨씬 많다.
- Mem2·G2R·Brz 의 `f_TempRepeat` 는 G_CA 계열 정의, UERE 는 자기 판(인자 순서 다름)이다.
- 보존 플래그: Stel 51/51, MEME 420/420 이 `1`, Seed 14/14 가 nil, ResV 411/477 이 `1`.

### 7.2 속성별 빈도 (신판 = Seed+Stel+MEME, 래퍼 포함)

| 속성 | TSetSpawn (Seed/Stel/MEME) | SetSpawn2X (Stel) | TScanEff (MEME) | 값 모양 |
|---|---|---|---|---|
| `LMTable` | 7 / 50 / 387 | 52 | 178 | 문자열(`"MAX"`) 561, 숫자 1~12 |
| `Order` | 1 / 7 / 135 | 4 | — | `{Patrol, "CD224"}` 처럼 **로케이션 이름**이 거의 전부 |
| `RepeatType` | 6 / 10 / 86 | 9 | 2 | 이름 문자열 대부분, 숫자 187·175·44 |
| `SizeTable` | 0 / 9 / 46 | 8 | 20 | 50·75·100·150·200, 변수(Lua 숫자) |
| `RotateTable` | 0 / 5 / 8 | 2 | 17 | 식(`(i*360)/8`, `45+90`), `"Main"`, V |
| `DistanceXY` | — / — / 25 | — | 19 | `{±72,0}`, `{0,(-32*2)+(32*i)}` |
| `FNTable` | — / — / 6 | — | — | 2 |
| `Rotate3D_Option` / `NQOpTable` | — / 5 / 4 | — | 3 | 1 |
| `Delay` | (Seed 도우미 안) / 2 / — | — | — | 5 |
| `EffID`·색 | 래퍼 경유만 | 52 | 183 | 이미지 번호 214·318·333·391·429·978 등, 색 0·10·13·15·16·17 |
| `FfragMode`·`FfragAfterTimer` | 래퍼 경유만 | 52 | — | 목록 글자 그대로인 것은 7쌍, 나머지는 도우미 결과. 타이머 대부분 60 |
| 속성 없음 | — / — / 19 | | | |

구판 ResV `G_CB_TSetSpawn`(477): `OwnerTable` 477, `LMTable` 381, `RotateTable` 111(0~315 의 45·60 배수, `"Main"`, V), `SizeTable` 96(100~250), `RepeatType` 91(층별 표 53), `CenterXY` 82.
위치 인자: 중심은 Stel 이 변수(`GunTrigGLoc` 등) 34 + 숫자 12 + 좌표 5, MEME 가 로케이션 이름 135 + 변수 251(`GunTrigGLoc`) + 좌표 34, Seed 가 nil 11 + 변수 3(좌표 표 2, 로케이션 번호 1). 주인은 대부분 상수 플레이어, MEME 층별 표 62.

### 7.3 대표 예

| 모양 | 파일:줄 |
|---|---|
| 건작 기본: 무조건, 1유닛·1도형, 중심 생략, MAX | `theSeed\MapConfig\Buildings.lua:1239` (주석 예), `theSeed\MapLogic\GunSystem.lua:772-773` (젠별 표, 최대 4층, `Delay`·`SizeTable` 은 설정에 따라) |
| 박자 연출: 도우미가 속성 병합, P7 이펙트 | `theSeed\MapConfig\Buildings.lua:2484-2499` |
| 좌표 중심 + 스케줄 페이드 + 사용자 RepeatType | `theSeed\MapConfig\Buildings.lua:2713-2714, 2744-2745` |
| 4층, 같은 도형 두 번(지상+공중) | `theSeed\MapConfig\Buildings.lua:2870-2872` |
| 로케이션 중심 + 명령 + SkillUnit | `theSeed\MapLogic\SpecialMarines.lua:341` |
| 보스 워프: 도형 하나를 네 유닛에, Ffrag, 명령 | `Stella_II\MapLogic\GunFunc.lua:22-24, 31` |
| 지상 2 + 공중 2 층, 프리셋 도형 | `Stella_II\MapLogic\GunFunc.lua:64-69` |
| 구판: 주인·회전 "Main"·층별 RepeatType | `MSF_Respect_V\GunData.lua:418` |
| 구판 래퍼: 이름 도형 `"ACAS"` | `MSF_Respect_V\GunData.lua:58, 416` |
| 프리펑션 2 + 여러 유닛 | `MSF_MEME_EUD\GunTrig.lua:69` |
| RepeatType 이름 오타(`"KiilUnit"` → 조용히 0) | `MSF_MEME_EUD\GunTrig.lua:70` |
| 스캔 이펙트 | `MSF_MEME_EUD\GunTrig.lua:329` |
| 직접 소환: 좌표, 187 | `MSF_Breeze\System.lua:192`, `Stella_II\MapLogic\GunTrig.lua:467` |
| 직접 소환 X: 변수 좌표 | `Stella_II\MapLogic\GunTrig.lua:514`, `MSF_Memory_2\BossTrig.lua:211` |
| Ffrag 알이 죽을 때 소환(맵 쪽) | `Stella_II\MapLogic\System.lua:1700-1723` |
| UE_RE 판 | `MSF_UE_RE\Gun_SpawnSet.lua:14` |

---

## 8. `eudext.spawn` API 확정안 (DESIGN 4.14 개정)

### 8.1 원칙

1. **의미는 GCB 를 따른다**: 층 순서, 층 사이 빈 프레임 1개, LM·딜레이 의미, 변환 순서(크기 → 회전 → 3D → 이동 → 중심 → 경계), CtrigAsm 회전 값, 넣는 순간의 중심·명령 해석, RepeatType 기본 명령이 명령 속성에 밀리는 규칙.
2. **일부러 다르게 하는 것**(원본 결함·우연):

| 원본 | eudext |
|---|---|
| 레코드 = 트리거 2,400B, 128칸 매 프레임 검사 | 작은 레코드 + 살아 있는 작업만 도는 루프(pool) |
| 층 4개를 바이트로 묶음(255 넘침 검사 없음) | 층 하나 = 레코드 하나, 층끼리 사슬. 값은 dword |
| 모든 호출이 스테이징 변수 공유, T 경로는 조건 없이 대입 | 넣기는 호출 자리에서 한 번에(원자적). 변수 인자 자유 |
| 로케이션 번호 0/1 기준이 곳마다 다름 | **eudplib 규칙 하나**: 이름 문자열 또는 1-based 번호 |
| 회전 −1 = "Main" | 전역 회전은 `sp.GLOBAL` 표식, 각도는 아무 정수 |
| 유닛 0 불가, 도형 0 층 방치 | 유닛 0 허용, 유닛·도형 수 불일치는 컴파일 오류 |
| 빈 도형·LM 0 → 오류 문구 또는 영원히 안 끝남 | 컴파일 오류(상수) / 즉시 완료 + `debug` 알림(변수) |
| LoopMax 포인터 전역·매 프레임 1 | **작업별 포인터**(의도된 의미) |
| LM 자동을 도형 번호 하위 바이트로 비교 | 넣을 때 `n//50+1` 계산 |
| 넘침 시 항상 문구 + Buzz | 넘침 횟수 변수 + `debug=True` 일 때만 문구 |
| RepeatType 고정 체인(맵마다 복사·수정) | **등록형 핸들러**, `EUDSwitch` 로 O(1) 분기 |
| 명령 목표 로케이션 = 원본 `TOrder` 2×2 상자 | 같게(유닛 한 기를 고르는 SC 액션이 없음). 문서에 "겹친 같은 종류도 받는다" 명시 |
| 스캔 이펙트의 `KillUnit(33, 주인)` 전체 처치 | 같게, 문서화(주인 기본 P8) |
| 프리펑션 = 런타임 정렬(CB_Sort) | 2단계: 컴파일 시점 변형 K개 + 런타임 무작위 선택 |
| `CAPlotIndexed` 의 nilunit 가짜 생성 | 없음 |

### 8.2 파이썬 API

```python
from eudext.spawn import Spawner, Order, Effect, at_unit
from eudext.shape import CX

cx = CX(lib_dir=LIB, seed=1234)
ring = cx.call("CSMakeCircle", 6, 32, 0, 37, 0)          # Shape
fade = ring.sweep("right", px_per_cycle=32)               # (shape 제안) 정렬 + LoopMax 스케줄이 붙은 새 Shape

sp = Spawner(
    capacity=128,              # 레코드(층) 수. 넣기 한 번 = 층 수만큼 사용
    loc="GCB Src",             # 소환 자리·명령 주체 상자 (이름 또는 1-based 번호). 필수
    loc2="GCB Dst",            # 명령 목표 상자. 필수
    default_target="Home",     # 기본 명령 목표: 로케이션(명령 순간 중심) 또는 (x, y)
    default_owner=P8,
    map_size=None,             # None = chk DIM × 32. (W, H) 픽셀로 덮어쓰기
    cycle=360,                 # 회전 각 단위 (mathx)
    turn_radius=127,           # 기본 RepeatType 들이 쓰는 회전반경. None = 안 씀
    storage="db",              # 좌표 저장 (shape.ShapeSet 로 전달)
    unclickable=None,          # {unit_id: image_id}  0틱 클릭 불가 (2단계)
    on_create=None,            # f(unit_index): 생성 직전 훅 (units.UnitData 초기화 등)
    debug=False,               # 넘침·빈 작업·알 수 없는 rtype 알림
)

# RepeatType 등록 (컴파일 시점, 모든 push/tick 보다 앞). 번호 생략 시 자동(1..255)
sp.rtype("Nothing")                                  # 핸들러 없음
sp.rtype("Home", sp.builtin.attack_default)          # 원본 0: 기본 목표 어택 + 회전반경
sp.rtype("Kill", sp.builtin.kill_all_of_type)        # 원본 3
@sp.rtype("Skill", id=8)
def _skill(s):                                       # s: SpawnCtx
    s.default_order(Patrol)                          # 명령 속성이 있으면 아무것도 안 함
    s.cunit.removeTimer = 15                         # CUnit 멤버 (eudplib 0.81)
sp.default_rtype = "Home"                            # rtype 생략 시

# 넣기 — 조건은 호출 자리의 EUDIf, "게임당 한 번"은 EUDExecuteOnce
sp.push(37, ring, owner=P8,
        center=None,            # None = sp.anchor | (x, y) | "Loc" | 1-based int | at_unit(epd)
        lm="max",               # "max"(=255) | 1..255 | 0(자동 n//50+1) | 변수
        delay=0, size=100,      # 상수 또는 변수
        rotate=0,               # 정수 | 변수 | sp.GLOBAL
        rot3d=False,            # True = sp.rot3d 묶음 | Rot3D | 묶음 이름
        bounds=None,            # None = Spawner 기본 | "skip" | "clamp"
        offset=(0, 0),          # DistanceXY
        rtype="Home",           # 이름 | 번호 | 변수(등록된 번호)
        order=None,             # Order.attack(x, y) | Order.patrol("Loc") | Order.move(...)
        effect=None)            # Effect.scan(image, color=None) (2단계: Effect.frag(...))
job = sp.job(owner=P8, center=(x, y), order=Order.attack("Home"))   # 여러 층 (최대 제한 없음, 원본 4)
job.layer(37, ring).layer(38, star, size=150, delay=5, rtype="Nothing").push()
sp.push_layers([(37, ring), (38, star)], owner=P8)   # 파이썬 편의

sp.tick()                                            # 매 프레임 1회 (push 뒤에 두면 같은 프레임에 첫 사이클)

sp.spawn_now(37, count=5, owner=P8, at=(x, y), rtype="Home", order=None)   # f_TempRepeat(X)
sp.scan_effect(ring, image=429, color=16, owner=P8, center="Boss", lm="max")  # G_CB_TScanEff

sp.anchor.x, sp.anchor.y          # G_CB_X / G_CB_Y (EUDVariable)
sp.rotation                       # G_CB_RotateV
sp.rot3d                          # 기본 Rot3D 묶음 (.xy/.yz/.zx EUDVariable) — tick() 보다 앞에서 만든다
sp.rot3d_set("eff2")              # 묶음 더 만들기 (최대 3)
sp.live                           # 살아 있는 레코드 수
sp.overflow                       # 넘침 누적
sp.clear()                        # 모든 작업 취소
```

`SpawnCtx`(핸들러 인자): `epd`, `ptr`, `index`, `cunit`(eudplib `CUnit`), `unit`, `owner`, `x`, `y`(유닛이 실제로 선 자리), `px`, `py`(도형 점), `cx`, `cy`(작업 중심), `has_order`, `default_order(종류, target=None)`, `order(종류, x, y)`, `set_turn_radius(v)`, `set_speed(top, accel)`.
내장 핸들러 `sp.builtin`: `attack_default`(0), `kill_all_of_type`(3), `remove_timer(n)`(5), `patrol_center`(7, 원본처럼 어택 — 이름은 `attack_center` 로 바꿀 것을 제안), `skill_unit`(8), `vision`(180), `nxct`(106), `no_speed`(201), `nspeed(attack=True)`(147/148), `force_order(order_id)`(187). 맵 전용(130~137, 175~179, 181, 188)은 넣지 않는다.

### 8.3 epScript

```js
import eudext.spawn as spawn;
import eudext.shape as shape;

const cx = shape.CX(lib_dir="…\\MapSource\\Library", seed=1234);
const ring = cx.call("CSMakeCircle", 6, 32, 0, 37, 0);
const sp = spawn.Spawner(capacity=128, loc="GCB Src", loc2="GCB Dst", default_target="Home");

function onPluginStart() {
    sp.rtype("Home", sp.builtin.attack_default);
    sp.rtype_func("Hold", HoldHandler);          // epScript 함수 = EUDFunc(epd, unit, owner, x, y)
}
function HoldHandler(epd, unit, owner, x, y) { /* … */ }

function afterTriggerExec() {
    if (Bring(P1, AtLeast, 1, "Terran Marine", "Gate")) {
        sp.anchor.x = 3072; sp.anchor.y = 1536;
        sp.job(owner=P8, rtype="Home").layer(37, ring).layer(38, ring, size=150).push();
    }
    sp.tick();
}
```

- epScript 의 `[a, b]` 는 `EUDArray` 로 번역된다(`docs\proto\eps_probe_out.txt:166-169`). 그래서 여러 층은 **`job().layer()` 사슬**을 기본 모양으로 둔다. 파이썬 목록 인자(`push_layers`)는 파이썬 전용이다.
- 핸들러: 파이썬은 콜러블(소환 본체 안에 한 번 펼침), epScript 는 `rtype_func(name, f)`(인자 5개 `EUDFunc` 를 호출). 파이썬 데코레이터는 epScript 에서 쓸 수 없다.
- 문자열 인자(로케이션 이름, rtype 이름)는 함수 인자로는 된다(DESIGN 3.11).

### 8.4 G_CB → eudext 대응

| G_CB | eudext |
|---|---|
| `Include_G_CB_Library(Loc, Idx, N)` | `Spawner(capacity=N, default_target=Loc, loc=…, loc2=…)` |
| `Create_G_CB_Arr()` / `G_CBPlot()` | 없음(자동) / `sp.tick()` |
| `G_CB_TSetSpawn(C, CUT, SH, Own, Ctr, Pf, P)` | `if EUDIf()(C): [if EUDExecuteOnce()():] sp.job(owner=Own, center=Ctr, …)` + 층마다 `.layer(u, s, …)` + `.push()` |
| `LMTable="MAX"`/k/0 | `lm="max"`/k/0 |
| `Delay`, `SizeTable` | `delay=`, `size=` (층별은 `layer(..., delay=, size=)`) |
| `RotateTable=k/"Main"/V` | `rotate=k/sp.GLOBAL/v` |
| `RepeatType` | `rtype=` + `sp.rtype(...)` 등록 |
| `Order={A, X, Y}` / `{A, Loc}` | `order=Order.attack(X, Y)` / `Order.attack("Loc")` |
| `DistanceXY` | `offset=` |
| `FNTable=1/2` | (2단계) `layer(..., variant="sweep"/"radial")` |
| `Rotate3D_Option=1`, `CA_Eff_*` | `rot3d=True`, `sp.rot3d` (`CA_Eff_*2` 는 `sp.rot3d_set("…")` + `rot3d=그 묶음`) |
| 옛판 `CA_RatioXY(v, 256, v, 256)` | `Spawner(size_div=256)` + `size=v` |
| 옛판 `CA_Func` 의 4095 클램프 / `G_CA_MapLimit()` | `bounds="clamp"`(맵 크기는 chk DIM 에서) / `bounds="skip"` |
| `G_CB_TScanEff` / `EffID`·색 | `sp.scan_effect(...)` / `effect=Effect.scan(img, color)` |
| `G_CB_SetSpawn2X` / `FfragMode` | (2단계) `effect=Effect.frag(units=[(u, n), …], life=…)` + `sp.on_frag_death` 도우미 |
| `f_TempRepeat(C, U, N, T, O, Ctr, F, _, RO)` | `sp.spawn_now(U, N, owner=O, at=Ctr, rtype=T, order=RO)` |
| `G_CB_X/Y`, `G_CB_RotateV`, `G_CB_CPlayer` | `sp.anchor`, `sp.rotation`, `default_owner` |
| `G_CB_LoopSchedule[shape] = {…}` | `Shape.with_schedule([...])` 또는 `shape.sweep(...)` |
| `G_CB_SpawnUnclickableUnits` | `Spawner(unclickable={…})` |
| `G_CB_RepeatTypeExtraDefs` | `sp.rtype(...)` |
| `UnitIDV1~4` 자리표 | `layer(unit_var, …)` 변수 직접 |
| UER `G_CB_SetSpawnX(C, CUT, SN, {FNTable, RPTable, LMTable, CenterXY, Owner, Delay, PreserveFlag})` | 같은 방식(`PFTable` 은 대응 없음 — 크기 단계는 컴파일 시점에 도형을 골라 넘김) |

### 8.5 내부 구성

**레코드(층 하나, dword 24개 이하)** — `pool.Pool` 레코드(DESIGN 4.11):

| 필드 | 뜻 |
|---|---|
| `start_frame` | 이 프레임 이상이면 진행(층 사이 빈 프레임 재현) |
| `next` | 다음 층 레코드(0 = 없음) |
| `unit`, `owner`, `rtype` | |
| `sid`, `n` | 도형 번호·점 수(넣을 때 캐시) |
| `p`, `w`, `c` 는 레코드 밖 | 진행 번호, 남은 대기 (c 는 tick 지역) |
| `lm`, `delay`, `sched` | 한도(0 이면 넣을 때 계산), 딜레이, 스케줄 포인터(0 = 없음) |
| `size`, `rot`, `flags` | 크기, 각, 비트(전역 회전·3D·이펙트 종류) |
| `cx`, `cy`, `dx`, `dy` | 중심(넣을 때 해석), 평행이동 |
| `oact`, `ox`, `oy` | 명령 |
| `eimg`, `ecol` | 이펙트 이미지·색(2단계 frag 는 별도 표 포인터 1칸) |

**넣기** (`push`): 호출 자리에서 ① 층 수만큼 `pool.alloc` (모자라면 이미 잡은 것 반납 + `overflow += 1`) ② 필드 쓰기(상수는 한 트리거에 모음, 변수는 `SeqCompute`/CP 연속 쓰기) ③ 중심·명령 로케이션 해석(MRGN 에서 `(L+R)//2, (T+B)//2` 를 0 방향으로; `TGetLocCenter` 흉내를 쓰지 않음) ④ 첫 층 `start_frame = sp.frame`, 뒤 층 `start_frame = 무한대`. 공용 부분은 `EUDFunc` 한 벌(3.3).

**tick**:
```
for rec in pool.live():                     # 시작 시 수를 고정, tick 중 새로 넣은 작업은 다음 tick
    if sp.frame < rec.start_frame: continue
    한 사이클 (6.2 의 의사코드. 스케줄은 rec.sched 를 쓰고 올림)
      회전·크기 준비는 사이클마다 1번: mathx 고정각 회전 부품(11절 제안)
      점마다: shapes.point(sid, p) → 변환 → 경계 → spawn_one(...)
    if p ≥ n: 완료 → next 가 있으면 next.start_frame = sp.frame + 2; pool.free(rec)
sp.frame += 1
```

**spawn_one** (공용 `EUDFunc` 한 벌, 작업 공통 값은 루프 앞에서 전용 변수에 둠):
1. 이펙트 분기(scan: 이미지·색 바꿔 생성·처치·복구 한 트리거 묶음).
2. `f_setloc(loc, X, Y)` (크기 0 상자).
3. `unclickable` 이면 Clickable 0.
4. `with units.capture() as u:` 안에서 `on_create(u.index_before)` → `CreateUnitWithProperties(1, unit, loc, owner, energy=100)`.
5. Clickable 복구.
6. `u.ok` 이면 `EUDSwitch(rtype)` → 핸들러 → 명령 속성이 있으면 `f_posread_epd` 로 실제 자리 → `loc` ±1, `loc2` = 목표 ±1 → `Order(unit, owner, loc, act, loc2)`.
7. CP 는 바꾸지 않는다(3.6).

**spawn_now**: 같은 `spawn_one` 을 count 번 부르는 작은 루프. 중심 해석은 호출 순간.

**의존**: `shape`(ShapeSet: `point_at`, `count`, `schedule`, 변형), `plot`(점 변환 부품), `mathx`(CtrigAsm 호환 회전·부호 나눗셈), `units`(`capture`, `CUnit`, `UnitData`), `pool`(레코드·살아 있는 목록), `players`(debug 문구).

### 8.6 비용

**지금 G_CB (theSeed)**

| 항목 | 값 | 근거 |
|---|---|---|
| 대기열 | 128 트리거 × 2,400B = **307KB**, 매 프레임 128 트리거 조건 검사 | 2.4 |
| 빈 도형 좌표 | (3 + 128) × 1,699점 × X·Y 4B = **약 1.78MB** 파일 배열 | GCB 1782~1787, CAPI 97~98 (계산) |
| 도형당 | 점 수 트리거 1 + LM 자동 1 + (스케줄 1) + 좌표 FArr 2개 + 주소표 칸. 도형 726 에서 `g_cbplot` **5,299 트리거 ≈ 12.7MB**(그중 `g_cb_prefunc` 1,435) | `theSeed\TriggerBudget.md:4,23-29` |
| 엔진 본체(`Include_G_CB_Library`) | 측정 없음. 수백 트리거(추정) | — |
| 호출 자리 | 평범 경로 1 트리거(액션 약 46), T 경로 2~수 트리거 | 4.1 |
| 실행 | 점당 약 400~500 트리거(추정), 한 프레임 최대 255점 × 층 수 × 작업 수 | 6.11 |

**eudext 목표** (구현 뒤 `tools/cost.py` 로 실측해 `COSTS.md` 에 적는다)

| 항목 | 목표 |
|---|---|
| 레코드 | dword 24개 이하 → 128칸 약 12KB |
| 도형 등록 | 트리거 0 (좌표 4B/점 + 주소표). 빈 도형 없음 |
| 엔진 본체 | 핸들러 제외 400 트리거 이하 |
| 호출 자리 | 상수만: 3 트리거 이하 + 호출. 변수 인자 하나당 +1 이하 |
| 빈 프레임 | 살아 있는 작업이 없을 때 3 트리거 이하 |
| 점당 실행 | 크기·회전·명령 없음 60 이하 / 기본 명령(좌표 읽기 + 로케이션 2개 + Order) +40 이하 / 크기 +40 / 회전 +120 (모두 추정 목표, "db" 저장 기준. "varray" 저장이면 읽기 몫이 줄어든다) |

### 8.7 단계

| 단계 | 범위 | 근거(7.2) |
|---|---|---|
| 1 | Spawner, push/job/layer, tick, lm·delay·size·rotate(GLOBAL 포함)·offset·order·center 5종, rtype 등록 + 내장 핸들러, spawn_now, 스케줄(작업별 포인터), debug, clear | 사용량 대부분, theSeed 전부 |
| 1(선택) | `Effect.scan` / `scan_effect` | MEME 183 |
| 2 | `unclickable`, 프리펑션 변형(`variant`), `Effect.frag` + 죽음 처리 도우미, 점대칭 스폰(`mirror=True`) | Stel 5·52, MEME 13, ResV 약 130 |
| 1(2026-09-20 보탬) | **`rot3d`**(`push(rot3d=True)` + `sp.rot3d`/`sp.rot3d_set()` — 2D 회전 뒤·평행이동 앞에 `mathx.rotate3d`), **`size_div`**(크기의 분모 — 기본 100 = 퍼센트, 256 = 옛판 `CA_RatioXY(v,256,…)`), **`bounds`**(`"skip"` 기본 = 밖은 버린다 / `"clamp"` = 0~W−1·0~H−1 로 잘라 반드시 소환 — 옛판 `CA_Func` 기본), **`precise`**(회전에 고정밀 lengthdir 표 — 원본이 `Include_CtrigPlib(…, LengthdirX=1)` 인 맵. 기본 False), **`rtype(…, id=0)`**(0 을 정상 번호로 — "없음" 표지는 `RTYPE_NONE`=256 으로 옮겨 간다) | Mem2 P6-c: 3D 59곳·비율 26곳·MapLimit 2곳·rtype 0 34곳 |
| 하지 않음 | 유닛 자리표 221~224(변수로 대체), `f_TempEffRepeatX`(0회), `CB_MarNumFill` 이름, theSeed 전용 RepeatType | |

---

## 9. 시험

### 9.1 대기열 동작 (에뮬레이터, `testing/scmodel.py` 의 CreateUnit 기록 + MRGN 모델)

프레임 f 에 찍힌 점 수. push 는 f=0 의 tick 앞. (`gcb_ref.py timeline()`)

| # | 경우 | 기대 |
|---|---|---|
| A | 1층, n=41, lm=max, delay 0 | f0: 41, f0 에 레코드 반납 |
| B | n=300, lm=max | f0: 255, f1: 45, f1 반납 |
| C | n=41, lm=10, delay 0 | f0~f3: 10씩, f4: 1 |
| C' | 같고 delay 1 | C 와 같음 |
| D | n=41, lm=10, delay 3 | f0, f3, f6, f9: 10씩, f12: 1 |
| E | 2층(41점, 41점), lm=max | f0: 층1 41, f1: 없음, f2: 층2 41, f2 반납 |
| F | n=41, lm=0 | 매 프레임 1점, f40 완료 (L = 41//50+1 = 1) |
| G | n=255, lm=max | f0 에 255, 같은 프레임 완료 |
| H | n=256, lm=max, delay 2 | f0: 255, f2: 1 |
| I | 스케줄 `{3, 5, 0, 7}`, n=12 | f0: 5, f1: 0(작업 유지), f2: 7 완료 (**의도된 의미**. 원본 코드 읽기로는 5, 5, 2 — 10절) |
| J | capacity 4 에 1층 작업 5개 | 5번째 버림, `overflow == 1`, 다른 작업 영향 없음 |
| K | capacity 4, 3층 작업 + 2층 작업 | 두 번째는 통째로 버림(부분 할당 없음) |
| L | 경계: 마지막 칸이 찬 상태에서 넣기 | 표 밖 쓰기 없음(에뮬레이터 메모리 비교) |
| M | tick 중 핸들러가 push | 새 작업은 다음 tick 부터 |
| N | 층 1 이 끝나기 전에 같은 프레임 다른 작업 넣기 | 서로 다른 레코드, 순서 무관 |
| O | clear() | 모든 레코드 반납, 사슬 뒤 층도 |
| P | n=0 상수 도형 | 컴파일 오류. 변수 경로로 n=0 이면 즉시 완료 + debug 알림 |

### 9.2 좌표 계산 기대값 (Cycle 360, `gcb_ref.py`)

`lengthdir(r, θ)` (CtrigAsm 호환):

| r, θ | 기대 (cos, sin) | 실수 참고 |
|---|---|---|
| 32, 0 | (32, 0) | |
| 32, 45 | (22, 22) | 22.627 |
| −32, 90 | (0, −32) | |
| 100, −90 | (0, −100) | eudplib `f_lengthdir` 는 (−97, 24) |
| 100, 450 | (0, 100) | |
| 100, 359 | (99, −1) | (99.985, −1.745) |
| 100, 360 | (100, 0) | |
| −100, 30 | (−86, −49) | T[30] = 32767 이라 −50 이 아님 |
| 32767, 45 | (23169, 23169) | |

`rotate(x, y, θ)`:

| x, y, θ | 기대 | 실수 참고 |
|---|---|---|
| 0, −32, 90 | (32, 0) | 12시 → 3시 = 시계 방향 |
| 32, 0, 45 | (22, 22) | |
| 27, −16, 30 | (30, 0) | (31.383, −0.356) — 항별 자르기 |
| 27, −16, −30 | (16, −26) | 330 과 같음 |
| 0, −32, 180 | (0, 32) | |
| 64, 64, 45 | (0, 90) | (0, 90.51) |
| −48, 20, 135 | (19, −47) | (19.799, −48.083) |
| 100, 0, 1 | (99, 1) | |

`size`: (27, −16)·150 → (40, −24); (−33, 33)·50 → (−16, 16); (7, −7)·0 → (0, 0); (100, −100)·255 → (255, −255); (1, −1)·99 → (0, 0).

전체 변환(W=6144, H=3072):

| 점, 설정 | 기대 (X, Y, 소환) |
|---|---|
| (27, −16), size 150, rot 30, offset (10, 0), center (3072, 1536) | (3127, 1535, 예) |
| (64, 0), center (6100, 100) | (6164, 100, 아니오) |
| (−32, 0), center (10, 10) | X = 0xFFFFFFEA, 아니오 |
| (0, 0), center (6143, 3071) | (6143, 3071, 예) |
| (1, 0), center (6143, 3071) | (6144, 3071, 아니오) |
| (0, −32), rotate=GLOBAL, rotation=90, center (100, 100) | (132, 100, 예) |
| (0, −32), rotate=−90, center (100, 100) | (68, 100, 예) — 원본은 −90 을 각도로 받지만 −1 은 "Main" 이다 |

알 목적지 클램프(2단계, 16비트 칸): (6200, 100) → (6143, 100); (−5, 50) → (0, 50); (32768, 3072) → (0, 3071); (6143, 3100) → (6143, 3071).

차등 시험: 무작위 x, y ∈ [−2000, 2000], θ ∈ [−720, 720], size ∈ [0, 255] 20만 건을 `gcb_ref.py` 참조와 비교(mathx 참조 구현과 공유).

### 9.3 기타 단위 시험

- 중심: 로케이션 이름·1-based 번호 → MRGN 중심. anchor 는 **넣는 순간 값**(넣은 뒤 anchor 를 바꿔도 작업 중심 불변).
- 명령: 명령 속성이 있으면 `default_order` 가 아무것도 안 함. 핸들러의 다른 동작은 실행됨.
- 생성 실패(`u.ok == 0`)면 핸들러·명령 없음.
- rtype 변수 값이 등록되지 않은 번호면 아무것도 안 함(debug 알림).
- CP 보존: tick·push·spawn_now 앞뒤 CP 동일.
- epScript 예제 번역·빌드(`job().layer().push()`, kwargs, `rtype_func`).

### 9.4 인게임 확인 (패턴 3개 + 보조)

| # | 패턴 | 원본 위치 | 보는 것 |
|---|---|---|---|
| 1 | **해처리 건작**: 부순 건물 자리(anchor)에 SHBcI 41점 저글링, lm max, 기본 어택 | `theSeed\MapConfig\Buildings.lua:1234-1242`, `MapLogic\GunSystem.lua:772` | 마릿수 41, 위치, 본진 어택, **맵 오른쪽 끝(X > 4096)과 아래쪽 끝** 소환, 연속 2개 부수기, 넘침 문구 없음 |
| 2 | **블랙홀 건작(130)**: 맵 중앙 좌표 중심, 페이드 스케줄, P7 이펙트 "Vision", 몹은 사용자 핸들러(주인 넘기기·무적·속도) | `theSeed\MapConfig\Buildings.lua:2706-2750` | 페이드 속도(원본과 나란히 영상 비교 — 스케줄 포인터 차이가 보이는지), 빈 밴드에서 작업 유지, 사용자 핸들러 |
| 3 | **보스 워프**: 로케이션 중심, 한 도형에 네 유닛 층, 명령 `{Attack, 보스 로케이션}`, 보스 1기 직접 소환 | `Stella_II\MapLogic\GunFunc.lua:22-31` (Ffrag 줄은 2단계라 빼고) | 층 사이 빈 프레임, 명령 목표가 **정확히 그 로케이션**인지(원본은 한 칸 앞 로케이션일 수 있음, 10절), spawn_now |
| 보조 | 회전 패턴: 전역 회전 변수를 매 프레임 바꾸며 도형 소환 | `MSF_Respect_V\GunData.lua:418` + `System.lua:1358` | 회전 방향(시계), 점마다 전역 값 반영 |
| 보조 | 스킬유닛: 로케이션 중심 + 명령 + removeTimer + 0틱 클릭 불가(2단계) | `theSeed\MapLogic\SpecialMarines.lua:341` | 중심 로케이션 번호 기준 |

---

## 10. 함정

### 10.1 알려진 것 (theSeed 재정비에서 잡음)

| # | 함정 | 근거 | eudext 대책 |
|---|---|---|---|
| 1 | **조건 없는 `G_CB_TSetSpawn`** 이 매 사이클 큐(128칸)에 쏟아짐 → 넘침 문구 도배 | PLAN B-2 | 문서 + debug 넘침 알림. `push` 에 조건 인자를 두지 않아 호출 자리의 `EUDIf` 가 눈에 보이게 |
| 2 | **`PreserveFlag = 1`** 은 공유 본체에서 "게임당 한 번" → 두 번째 건물부터 안 나옴. 게다가 `CallTriggerX(…,1)` = 비보존, `CTrigger(…,1)` = 보존으로 뜻이 반대 | PLAN B-3; L322 287~294; CA 7238~7240 | 보존 플래그 없음. `EUDExecuteOnce` 안내 + "공유 본체 안에서는 쓰지 말 것" 경고 |
| 3 | **인자 위치가 함수마다 다름**: `TOrder(Unit, Player, StartLoc, Order, DestLoc)` 3번이 로케이션, `TCreateUnitWithProperties(Amount, Unit, Loc, Player, Prop)` 1번이 개수 → 255마리 × 점 | PLAN 312~326; CA 15525, 14521 | 키워드 인자, 시험 |
| 4 | 로케이션을 원시 주소(`0x58DC60`)로 되읽는 곳은 번호가 안 보임 | PLAN 330~334 | 스크래치 로케이션을 객체로 받고 주소 계산은 한 함수 |
| 5 | 128×128 상수(4096/4095/2048/3712) | PLAN B-5 | `map_size` 한 곳 |
| 6 | 타이머 `Exactly` 는 안 맞음(사이클당 29ms) | PLAN B-4 | 호출 쪽 문제. 문서 |
| 7 | 대기열 경계 `604*Size-2` → 표 뒤 레코드 덮어쓰기 | GCB 1358~1362 | 풀 할당, 시험 L |
| 8 | `f_GetVoidptr` 크기는 바이트 → CB 표 넘침(09-08 사건의 진짜 원인) | GCB 1509~1518 | 해당 없음(ShapeSet) |
| 9 | 도형 등록이 테이블 동일성 → `CS_Thin` 등 새 표마다 새 번호 → 트리거 폭증 | PROG 34절 | ShapeSet 은 좌표 내용으로 중복 제거(선택) + 도형당 트리거 0 |
| 10 | 받은 도형 표·속성 표를 **고쳐 씀** → 같은 표를 두 번 넘기면 두 번째가 엉뚱 | `theSeed\MapConfig\Buildings.lua:2482-2483`; GCB 2285, 2121, 2153 | 인자를 복사해서 씀 |
| 11 | 유닛 수 ≠ 도형 수(유닛이 적으면 뒤 층 유닛 0, 도형이 적으면 도형 0 층) | `theSeed\MapLogic\GunSystem.lua:710-716` | 컴파일 오류 |
| 12 | 4층 줄에서 같은 도형을 지상끼리·공중끼리 두면 겹쳐서 안 나옴(관찰 기록) | `theSeed\MapLogic\GunSystem.lua:701-709` | 문서(원인은 추측: 공중 겹침·밀어내기) |
| 13 | 빈 밴드 사이클을 "Not Found" 로 버림 | GCB 1931~1938 | 스케줄 사이클은 항상 살아 있음 |
| 14 | 40번(브루들링 슬롯)은 체력·에너지 조작 순간 시한부가 됨 | GCB 235~253 | 문서(맵 쪽 핸들러) |
| 15 | 0틱 클릭 토글은 켜기·끄기 조건이 글자 그대로 같아야 함 | GCB 1908~1912 | 한 트리거 안에서 끄기·생성·켜기 |

### 10.2 이번에 새로 찾은 것 (코드 읽기, 인게임 미확인)

| # | 함정 | 근거 | 영향 |
|---|---|---|---|
| 16 | **LoopMax 포인터가 매 호출 1 로 돌아감** → 매 사이클 `sched[1]` 개 | CAPI 235~237, 301~304 | 페이드 속도가 밴드별로 안 바뀜(의도와 다름) |
| 17 | **`Order` 로케이션 문자열이 한 칸 앞 로케이션**(STL/GCB). `Temp+0x80000000` → `−0x80000000` → 0-based 값을 `TGetLocCenter` 가 1-based 로 씀. MEME 는 `Temp+2` 라 맞음 | GCB 2424, 1318~1322; MEME 1723, 904~905; L322 1086~1095, 1237~1245 | Stella `Set_Warp` 의 `Order={Attack,"Location 24"}` 가 Location 23 중심을 목표로 삼는다고 읽힘 |
| 18 | `f_TempRepeat` 로케이션 중심: 숫자 N → 1-based N, **문자열 → 한 칸 앞**(`SetX = Temp`). MEME 는 `Temp+1` 로 맞음 | GCB 994~997, 1068~1071; MEME 632~635 | 이름으로 준 직접 소환 위치가 틀림 |
| 19 | `G_CB_TSetSpawn` 중심 숫자 N 은 1-based 로 해석되는데 theSeed 스킬유닛은 **0-based** `PlotLoc = 102` 를 넘긴다 → 로케이션 101(= `DetectLoc`) 중심을 씀. 두 로케이션이 같은 마린 위라 **우연히 가려짐** | `theSeed\MapConfig\Marines.lua:1208-1215`, `MapLogic\SpecialMarines.lua:299-300,341` | 로케이션 배치가 바뀌면 드러남 |
| 20 | `f_TempRepeat` 의 명령 로케이션 모드가 **중심 표식(`TRepeatY`)** 을 보고 `TGetLocCenter(Repeat_OrderY)` 를 부름 | GCB 645~648 | `ROrder={A, Loc}` 가 동작하지 않음 |
| 21 | 리버(83) 스캐럽 충전이 **로케이션 1 고정**(`TModifyUnitHangarCount(1,1,83,RPID,1)`, 마지막 인자가 로케이션, CA 15822). theSeed 로케이션 1 = 마린 생산 지점 | GCB 309~312 | theSeed 에서 G_CB 리버가 스캐럽을 못 받음(추측) |
| 22 | LM 자동(0)을 `TT[13] & 0xFF == j` 로 비교 → 도형 번호 256 이상은 **다른 도형의 점 수**를 쓰거나(256의 배수면) 한도 0 | GCB 1702~1705 | theSeed 도형 726개 — LM 을 안 주는 호출(스케줄 없는 것)이 있으면 드러남 |
| 23 | LM 0 + 스케줄 없음 + 딜레이 ≥ 2 → 작업이 **영원히 안 끝남** | 6.9 | 레코드 고갈 |
| 24 | RepeatType 이름 오타 → `RTypeKey[이름] = nil` → 조용히 0(표 형태면 뒤 원소가 앞 바이트로 당겨짐) | GCB 2450~2464, 3.3; MEME `GunTrig.lua:70` `"KiilUnit"` | 이펙트 유닛이 본진으로 어택 |
| 25 | `T_to_ByteBuffer` 값 > 255 → 다음 층으로 넘침(크기 300% 등) | GCB 2012~2019 | 다음 층 설정 오염 |
| 26 | T 경로 + 보존 플래그 1 → 스테이징 대입은 첫 통과 때 한 번, 넣기는 조건이 참일 때 → 다른 호출이 덮어쓴 값으로 넣음 | GCB 2544~2568; L322 1500~1504 | Stella 의 변수 회전 호출(5회)이 영향권(추측) |
| 27 | `T_to_ByteBuffer` VMode 의 `CAdd` 누적 | GCB 2031~2050 | 변수 원소가 실행마다 커짐(사용처는 없음, 추측) |
| 28 | 로케이션 중심 모드가 `G_CB_X/Y` 를 **덮어씀**(넣기·직접 소환 모두) → 같은 프레임 뒤의 "중심 생략" 호출이 엉뚱한 자리 | GCB 1346, 661 | 호출 순서 의존 |
| 29 | `KillUnit` RepeatType·스캔 이펙트가 그 주인의 **그 유닛 전부**를 죽임 | GCB 451~453, 720 | 사람 주인의 스캔·같은 종류 유닛 소멸 |
| 30 | `TOrder` 2×2 상자라 겹친 같은 종류·같은 주인 유닛도 명령받음 | GCB 179~199 | eudext 도 같음(문서) |
| 31 | 생성 실패여도 RepeatOption 이 빈 슬롯 포인터로 진행(에너지 검사가 막음). 116 경로는 에너지 검사 없이 EXCC 를 씀 | GCB 839~909, 729~808 | 다음에 그 슬롯을 쓰는 유닛에 Ffrag 자료가 남음(추측) |
| 32 | `G_CB_SetSpawn`/`G_CB_SetSpawnX` 는 신판에서 컴파일 불가(구판 서명으로 호출) | GCB 2100~2109, 2334 | 옛 맵 이식 때 혼동 |
| 33 | `RotateTable` 숫자 표(층별)는 신판에서 안 됨(구판만) | GCB 2487~2493 vs RSV 1540~1545 | |
| 34 | `Patrol_Center` 는 어택 | GCB 543~548 | 이름 혼동 |
| 35 | `f_TempEffRepeatX` 전역 `PP` 공유 | GCB 1094~1118 | 사용 0 |
| 36 | 여러 프리펑션 작업 칸이 1,699점 고정 | GCB 1782~1787 | 큰 도형 + FN 은 넘침(추측) |
| 37 | `CB_MarNumFill` 의 `CreateVars(FP)` 가 변수 7개 | PROG 2496 | 낭비 |

---

## 11. DESIGN.md 수정 제안

1. **4.14 전면 교체**: 8절의 API(`Spawner(loc, loc2, default_target, …)`, `push`/`job().layer().push()`, `tick`, `spawn_now`, `rtype` 등록, `scan_effect`, `anchor`·`rotation`·`rot3d`)와 "원본과 일부러 다르게 하는 것" 표(8.1)를 넣는다. 초안의 `shapes=[…]`·`units=[…]` 목록 인자는 epScript 에서 `EUDArray` 가 되므로 사슬 API 를 기본으로 한다. 초안의 `repeat="attack"|"move"|("order", tx, ty)` 는 `rtype`(행동)과 `order`(명령)가 **다른 축**이므로 둘로 나눈다. `per_tick="MAX"` → `lm`. `on_point=fx` 는 1단계에서 빼고(CA_Func1 에 사용자 코드를 넣는 맵이 없음) 2단계 후보로.
2. **4.14 "근거"의 `G_CA` 제외 문장 유지**, 그리고 "RepeatType 은 맵마다 다른 표이므로 등록형" 을 명시.
3. **4.13 `shape`**: `ShapeSet.point_at(sid, i) -> (x, y)`, `count(sid)`, 도형별 **LoopMax 스케줄**(`Shape.with_schedule`, `Shape.sweep(mode, px_per_cycle)` — theSeed `GunFadeShape` 대체), 2단계 **변형**(`variants=("sweep8", "radial")`: 컴파일 시점에 정렬한 사본 K개 + 런타임 선택)을 추가. 등록 중복 제거(좌표 내용 해시) 선택 기능.
4. **4.13 `plot`**: `Plotter` 가 한 번에 한 도형만 다루므로, spawn 이 쓸 **상태 없는 부품**(점 읽기, `ratio`, `rotate`, `move`)을 공개 함수로 둔다. 스케줄 포인터는 호출자가 가진다.
5. **4.5 `mathx`**: 고정각 회전 부품 `mx.Rotator(angle, cycle)` — 사이클마다 사분면·표 값을 한 번만 구하고 점마다 곱 4번·부호 나눗셈 4번(항별 자르기 유지). `CA_Rotate3D` 호환 `mx.rotate3d(x, y, xy, yz, zx)`(2단계). 시험 벡터에 9.2 표를 넣는다.
6. **4.10 `units`**: `capture()` 가 생성 **전** 색인(`index_before`)을 주어야 `on_create` 훅(EXCC 초기화 대체)을 부를 수 있다. `UnitData.clear(index)`.
7. **4.11 `pool`**: 여러 칸을 **원자적으로** 잡는 `alloc_n(k)`(모자라면 0), 살아 있는 목록 순회 중 해제·추가 규칙(추가분은 다음 순회), 레코드 필드 24개 이하 규모의 비용 측정 항목.
8. **3.9 금지 목록**에 "로케이션 번호는 eudplib 규칙(이름 또는 1-based)만. 0-based 정수를 받는 API 금지" 추가.
9. **3.10**: 넘침 문구를 `debug` 로 옮기되 **넘침 카운터는 항상** 두는 것을 규약으로(원본은 항상 문구를 띄워 제작자가 문제를 알아챘다).
10. **5.1 `scmodel`**: spawn 시험에 필요한 것 — CreateUnit(WithProperties) 기록 + `0x628438` 갱신, KillUnit(유닛·주인 전체), Order 기록(상자·목표), MRGN 모델, CUnit +0x28 좌표 스텁.
11. **6.1 WP12 추가 완료 조건**: 9.1 표 A~P, 9.2 벡터 전부, 인게임 9.4 의 1~3. 선행에 WP9(`mathx` Rotator)를 명시.
12. **0.1 표의 "각도·반올림" 줄**에 "회전 결과는 항별 자르기(실수 회전과 최대 ±2 차이)" 를 덧붙인다.

---

## 12. 미확인

1. **LoopMax 포인터**(10-16): 코드로는 매 호출 1 로 돌아가는데 제작자는 페이드 정상으로 보고했다. 원본 빌드를 에뮬레이터나 인게임에서 밴드별 점 수로 재 봐야 한다. eudext 는 의도된 의미(작업별 포인터)로 가지만, 원본과 영상이 다르게 보일 수 있다.
2. **`TGetLocCenter` 의 nilunit 이동**: 대상 유닛이 없을 때 `MoveLocation` 이 목적 로케이션 중심으로 옮기는지, 그 중심 계산(반올림)이 `(L+R)/2` 와 같은지.
3. **로케이션 오프바이원 3건**(10-17·18·19): 인게임 확인 필요. 특히 Stella 보스 워프 명령 목표.
4. **리버 스캐럽**(10-21) theSeed 인게임 영향.
5. `0x6663C4` 가 유닛 116 의 스프라이트 이미지 칸인지, `0x666458` 이 스캐너 스윕 스프라이트(380)인지(주소·원래 값 546 은 코드와 DPS 관용구로만 확인).
6. 상태 플래그 `0xA00000` 의 정확한 의미(BWAPI 이름 NoCollide|IsGathering 로 추측).
7. `nilunit`(181) 생성이 실제로 실패하는지(CAPI 의 가짜 생성).
8. `SetCVar` 값 자리에 V 를 넣으면 컴파일 오류인지(평범 경로 변수 인자), `T_to_ByteBuffer` 1번 원소 V 의 오류.
9. 4층 같은 도형 겹침으로 공중 유닛이 사라지는 원인.
10. 원본 엔진 본체(`Include_G_CB_Library`)의 트리거 수와 점당 실행 수 — 측정하지 않았다(theSeed 빌드를 돌리지 않음). 6.11·8.6 의 수치는 추정이다.
11. `Call_Calc_NSpeed` 의 속도 단위 해석(`√(d²/4)` 가 몇 프레임 도달을 뜻하는지). Stella 맵 쪽 같은 식은 `/2` 를 쓴다(`Stella_II\MapLogic\System.lua:1240`).
12. 프리펑션 변형을 컴파일 시점 K개로 근사하는 것이 원본(연속 무작위 방향)과 체감상 같은지 — 제작자 판단 필요.
13. eudext 가 층 사이 빈 프레임 1개를 재현하는 것이 맞는지(박자 연출 호환 vs 단순화) — 제작자 판단 필요. 이 명세는 재현으로 정했다.
14. `map_size=None` 일 때 eudplib 0.81 에서 chk `DIM ` 을 읽는 공개 API — WP0 에서 확인.
