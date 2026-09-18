# S2 — 건물 스택(`Gun_Line`)·TStruct 명세와 `eudext.pool` API 확정안

작성 2026-09-17. 맵·라이브러리 코드는 고치지 않았다. 근거는 `파일:줄`, 확인하지 못한 것은 "(추측)".
실험 스크립트와 출력은 스크래치패드 `spec_s2\` 에 있다(모두 eudplib 0.81.0, `C:\Users\whatd\.venvs\eud081`).

| 스크립트 | 하는 일 | 출력 |
|---|---|---|
| `field_count.py` | 맵별 줄 번호 사용 빈도 (주석 제거 정규식) | `field_count_out.txt`, `field_count.json` |
| `exp_costs.py` | EUDStruct·EUDArray·EUDVArray·ObjPool·EUDSwitch 정적 트리거 수 (뒤쪽 [2] 페이로드 절은 재는 방식이 틀려 버림) | `exp_costs_out.txt` |
| `exp_exec.py` | 같은 것의 실행 트리거 수(에뮬레이터), 유형 분기 실행 수 ([A] 절은 기준 본문에 읽기 함수가 없어 한 번 드는 코드가 섞임 — 전역 풀 행만 유효) | `exp_exec_out.txt` |
| `exp_payload.py` | 페이로드 길이(한 번 드는 코드 / 원소당 저장, 기울기로 봄) | `exp_payload_out.txt` |
| `exp_chain.py` | **사슬 적재 시제품**: 목적지를 미리 정한 72B 원소 사슬로 레코드 13칸을 점프 한 번에 싣기, 되쓰기 | `exp_chain_out.txt` |
| `refmodel.py` | pool 파이썬 참조 모델 + 시나리오 T1~T14 기대값 | `refmodel_out.txt` |
| `eps_pool_probe.py` | 제안 API 의 epScript 번역(`epsCompile`) | `eps_pool_probe_out.txt` |
| `emu.py` | `docs\proto\emu.py` 사본(0.81 에서도 동작 확인) | — |

## 약어

| 약어 | 위치 |
|---|---|
| SD | `C:\Users\whatd\Desktop\Stormcoast Fortress\ScmDraft 2` |
| MS | `SD\MapSource` |
| ResV | `SD\MSF_Respect_V` |
| Mem2 | `MS\MSF_Memory_2` |
| G2R / G2 | `MS\MSF_GaLaXy.2_R` / `MS\MSF_GaLaXy.2` (G2 는 옛판, 줄 사용 수가 G2R 과 똑같다 — `field_count_out.txt`) |
| UERE / UE | `MS\MSF_UE_RE` / `MS\MSF_UE` (UE 는 옛판, 줄 사용 수가 거의 같다) |
| GR | `MS\MSF_GaLaXy.R` (ResV·Mem2 의 조상) |
| Seed | `SD\theSeed` |
| TS | `MS\Library\TStruct.lua` |
| CA / L322 | `MS\Library\CtrigAsm v5.5.lua` / `MS\Library\LibraryFor322.lua` |
| EP81 | eudplib 0.81.0 (`C:\Users\whatd\.venvs\eud081\Lib\site-packages\eudplib\`, 스크래치 `upstream\eudplib\src\eudplib\` 와 같은 판) |
| EP76 | eudplib 0.76.14 (`C:\Users\whatd\.venvs\eud076\Lib\site-packages\eudplib\`) |
| flow.py | `SD\DPS_eud\eud\ctrig\flow.py` (읽기만) |

용어: **슬롯**(레코드 한 칸) · **줄**(Line, 필드 번호) · **작업 레지스터**(`Var_TempTable`/`TS_VarArr`, "지금 도는 슬롯"의 필드를 담는 전역 변수) · **본체**(`f_Gun`/`TStr_Func`, 모든 슬롯이 공유하는 서브루틴) · **보내기**(Send, 빈 슬롯에 새 레코드 쓰기) · **Suspend**(원본 이름. 실제 뜻은 **반납**이다, 2.6).

---

## 0. 한눈에

- **건물 스택과 TStruct 는 같은 기계다.** 슬롯 하나 = CtrigAsm 트리거 하나(2,416B), 필드 k = 그 트리거 액션 k 의 값 칸(`+0x15C + k·0x20`). 매 프레임 슬롯마다 "첫 필드 ≥ 1" 조건 트리거가 돌고, 참이면 액션 k 가 "레지스터 k ← 필드 k" 를 한꺼번에 실행해 싣고, 공유 본체를 부른 뒤, 본체 끝에서 레지스터를 슬롯에 되쓴다(ResV `GunData.lua:292-308, 2980-2983`, TS `171-193, 201-212`). Seed 주석도 둘이 "정확히 같다" 고 적었다(Seed `MapLogic/GunSystem.lua:12-20`).
- **맵마다 다른 것은 네 가지**: 크기(128/64/36/200/32), 보내기가 채우는 필드, **쓰기 대상**(레지스터에 쓰고 끝에 되쓰기 — ResV·Mem2·UERE·GR·TS / 슬롯에 바로 쓰기 — G2R·G2), 줄 번호의 뜻(타이머가 7번·4번·8번 등). 0~2번 줄(유닛·X·Y)과 54번 줄(반납 표시)만 모든 건물 스택에 공통이다(2.8, 2.9).
- **`Suspend` 는 일시 정지가 아니라 반납이다.** 원본에 "멈췄다 다시 도는" 기능은 없다(2.6, 3.2).
- **비용**: 원본은 슬롯 수만큼 상시 트리거(128 × 2,416B = 302KB, 매 프레임 128회 조건 검사) + 레지스터 55개. eudext 는 **빈 슬롯 비용이 0** 이고 저장은 필드당 72B 다(5절).
- **pool 확정안(6절)**: 레코드 = **목적지를 미리 정한 72B 변수 원소의 사슬**(eudplib 0.81 `EUDQueue` 가 쓰는 기법), 방문 = 점프 한 번으로 모든 필드를 **레지스터(EUDVariable)** 에 싣기 → 본문에서 필드 조건은 보통 변수 조건(추가 트리거 0), 끝에 **바뀐 필드만** 되쓰기. 살아 있는 목록 + 표식·압축, 핸들 = 레코드 주소(0 = 없음). 시제품이 에뮬레이터에서 13필드 적재 실행 17~19, 3필드 되쓰기 18 을 냈다(`exp_chain_out.txt`).
- **EUDStruct 포인터 방식은 필드 연산마다 실행 7~11**, EUDArray(4B) 방식은 **필드 읽기마다 실행 36~38** 이라 본문이 큰 건작에는 맞지 않는다(5.2). **`EUDStruct.alloc()` 전역 풀은 페이로드를 19.28MB 늘린다**(측정) — 금지.
- **0.81 `EUDMethod` 는 정적 EUDStruct 인스턴스에도 본문 1벌을 공유한다**(EP81 `core/eudfunc/eudfmethod.py:54`, 측정: 두 번째 인스턴스 호출 자리 1 트리거). DESIGN 4.11 위험 항목은 해결됐다.
- **옛 줄 번호는 별칭 표로 옮긴다**: `Pool(..., aliases={0:"unit", 5:"started", …}, alias_base=0)` 후 `guns.Line(5, Exactly, 0)`·`guns.SetLine(7, Add, 1)`. `SetLine(…, Subtract, …)` 은 원본처럼 **포화**(6.9).

---

## 1. CtrigAsm 기본 동작 (명세에 필요한 만큼)

| 함수 | 뜻 | 근거 |
|---|---|---|
| `CreateVar(P)` / `CreateVarArr(n,P)` | 변수 하나 = **트리거 하나**(`CVariable`). 값은 그 트리거 액션 0 의 값 칸(+0x15C) | CA:75524, 75644, 1277-1280 |
| `CVar(P,Idx,Type,V,Mask)` / `SetCVar(...)` | 변수 Idx 의 값 칸을 보는 Deaths 조건 / 쓰는 SetDeaths 액션 | CA:8533, 8537 |
| `TCVar` / `TSetCVar` | 값(V)이 변수·식이어도 되는 T 계열(실행 때 패치) | CA:12543, 12547 |
| `CVar("X","X",...)` | 트리거 **자기 자신**의 +0x15C 를 보는 조건 | Install_GunStack·TS_CreateArr 에서 씀 |
| `CTrigger(P,C,A,Flags,Index)` | `Flags==1` 이면 **보존**(`{Preserved}`) | CA:7226-7252 |
| `CDoActions(P,A,Flags)` | 조건 없는 트리거. 기본 보존 | CA:7197-7224, L322:1493 |
| `CallTriggerX(P,Idx,C,A,Flags)` | `Flags==nil` → **보존(매번)**, `Flags==1/"X"` → **한 번만** | L322:287-295 |
| `SetCall`/`SetCallEnd`, `SetCall2`/`SetCallEnd2` | 서브루틴 시작 라벨·끝 트리거(끝에서 호출자 next 복구). **본문 자기 건너뛰기가 없어서** 선언 전용 CJump 블록 안에 둬야 한다 | L322:156-237, Seed `main.lua:252` 주석 |
| `SetNext(a,b,n)` | 트리거 a 의 next = b(+n) | CA:7263-7270 |
| `SetCtrigX(P1,I1,Off1,N1,Type,P2,I2,Off2,EPD2,N2)` | 트리거 (I1)+Off1 칸에 "트리거 (I2)+Off2 의 주소(EPD2=1 이면 EPD)" 를 쓴다 | CA:1827 |
| `CIfOnce` | **게임당 한 번** | CA:10397 |
| `NBag`/`NBagLoop`/`NRemove` | 필드 ≤ 32개 가방, 루프 중 지우기 = 마지막 원소를 끌어와 같은 번호 재검사 | CA:96635, 96939, 96989; flow.py:425-507 (Number=1 만 이식, `NAppend` 는 크기 검사 없음) |

트리거 하나의 메모리 간격은 0x970(2,416B, EPD 604)이다. 원본 코드가 슬롯을 "시작 주소 + 번호×0x970" 으로 계산하므로(ResV `GunData.lua:226`, TS `113, 123, 131`) 적층 포크에서도 이 트리거들은 흩을 수 없다(메모리 기록 theseed-asm-stack "주소+번호*604", 슬롯이 실제로 KEEP 인지는 미확인).

---

## 2. 건물 스택 (`Include_GunData` 계열)

### 2.1 저장 배치 (모든 맵 공통)

- 슬롯 i = `Install_GunStack` 이 만드는 i 번째 `CTrigger`. 첫 슬롯만 라벨 `CIndex`(=`FuncAlloc`, ResV `GunData.lua:14`)이나 고정 인덱스 `0x500`(G2R `System.lua:207`, UERE `Gun_System.lua:346`)을 받고 나머지는 연달아 놓인다.
- `G_InputH` = 슬롯 0 의 +0x15C EPD. 맵 시작 때 `SetCtrigX(FP,G_InputH[2],0x15C,0,SetTo,FP,CIndex,0x15C,1,0)` 로 새긴다(ResV `:36`, Mem2 `:30` 의 `G_init`, G2R `main.lua:86`, UERE `EUDinit.lua:132`).
- 슬롯 i 줄 k 의 EPD = `G_InputH + i·(0x970/4) + k·(0x20/4)` (ResV `:226, 234-237`).
- 줄 수 `LineNum` = 55(모든 맵). 슬롯 트리거의 액션은 **55(적재) + 7(제어) = 62개** 라 64 한도 안이다(ResV `:297-306`, TS `69-77` 주석).

### 2.2 활성 판정

슬롯 트리거 조건 `CVar("X","X",AtLeast,1)` = **줄 0 ≥ 1**(ResV `:297`). 보내기도 "줄 0 ≥ 1 이면 찬 칸" 으로 본다(ResV `:227`). 줄 0 에는 건물 UnitID 가 들어가므로 UnitID 0(마린)은 건작이 될 수 없다(Seed `MapConfig/Buildings.lua:996-1000` 같은 규칙).

### 2.3 생성 경로

| 경로 | 동작 | 근거 |
|---|---|---|
| `G_Send` 본체 | ① CP 저장 ② (강제 입력이 아니면) CP 기준 CUnit 에서 좌표(dword 10)·UnitID 바이트(dword 25)·소유자 바이트(dword 19)를 읽음 ③ `Convert_CPosXY` ④ **첫 맞춤 탐색**: G_A=0 부터 `줄0 ≥ 1 이고 G_A ≤ Size-1` 이면 G_A+1 로 되풀이 ⑤ `G_A ≤ Size-1` 이면 줄 0~4 쓰기, 아니면 오류 문구 ⑥ CP 복구 | ResV `:37-248` |
| 줄 0~4 의 값 | 0 UnitID, 1 X, 2 Y, 3 `DUnitCalc[4][3]`(= 죽은 유닛의 EXCC 2번 줄 = 배치 때 넣은 건물 번호 `BIndexV`, ResV `CallTriggers.lua:166-167`), 4 소유자 | ResV `:232-238` |
| ResV 필터 | `GunPlayer == 7`(P8 건물) 또는 `GunID == 119`(탄막 유닛)만 등록 | ResV `:80` |
| ResV `GunBGM` | 보내기 안에서 UnitID 별 BGM·점수·안내를 같이 처리 | ResV `:81-209` |
| `f_GSend(UnitID, Actions)` | `CallTriggerX(FP, G_Send, {DeathsX(CurrentPlayer,Exactly,UnitID,0,0xFF)}, {Actions, SetCD(f_GunForceOption,0)})` — **CP 가 죽은 유닛의 dword 25 를 가리킨 상태**에서 부른다. 보존(매번) | ResV `:252-254`; 호출 ResV `System.lua:1117-1121`(EXCC 죽은유닛 단락, `f_GunTable` 전체), Mem2 `System.lua:811` |
| `f_GunForceSend(UnitID,GP,GPos,GNum,C,A,Preserve)` | 죽은 유닛 없이 강제 입력(`f_GunForceOption=1` → CUnit 읽기를 건너뜀). `Preserve=1` 이면 **한 번만**(이름과 반대) | ResV `:255-257`; 호출 `System.lua:1367-1381`(시간별 콜 웨이브 UnitID 256), `:1621`(화홀 189 한 번) |
| Mem2 `f_GForceSend(C,UnitID,GunNum,GPlayer,{X,Y},A)` | **따로 복사한 보내기 본체** `G_ForceSend`(탐색 코드 중복). 본체 끝에 `f_LoadCp()` 가 있는데 `f_SaveCp()` 가 없다 | Mem2 `GunData.lua:99-137`, 호출 `:3489-3490`(건작 **본체 안** `CIfOnce` 에서) |
| G2R 보내기 | `GunLocPos_CallIndex` 가 CUnit 좌표를 위치 표에 저장하는 일과 같이 한다. 줄 0~3 만 쓴다(3 = CUnit +0x26 바이트, 배치 때 심은 번호(추측)) | G2R `main.lua:790-840`, 강제판 `:843-866`, `func.lua:1145-1150` |
| UERE 보내기 | 줄 0~3 과 **53**(`Gun_Type`, 잡건작이면 256)을 쓴다. 탐색 한도 `AtMost,126` → **슬롯 127 은 영영 안 쓰인다**(실제 용량 127) | UERE `CallTriggers.lua:190-221`, `Gun_System.lua:26-41` |

탐색은 매번 슬롯 0 부터다(첫 맞춤). 슬롯이 찼을 때 그 건물의 건작은 **버려지고** 문구만 남는다.

### 2.4 매 프레임 처리 (`Install_GunStack`)

`CMov(FP,Actived_Gun,0)` 뒤에 슬롯마다(ResV `:292-308`):

```
CTrigger(FP, {CVar("X","X",AtLeast,1)}, {           -- 줄 0 ≥ 1
    Var_InputCVar,                                   -- 55개: SetCVar(레지스터 k, SetTo, <이 액션의 값 칸 = 줄 k>)  ← "적재"
    SetCtrigX("X",G_TempH[2],0x15C,0,SetTo,"X","X",0x15C,1,0),   -- G_TempH = 이 슬롯 EPD (되쓰기 주소)
    SetCVar(FP,f_GunNum[2],SetTo,i),                 -- 슬롯 번호
    SetCVar(FP,Actived_Gun[2],Add,1),                -- 활성 수
    SetNext("X",f_Gun,0), SetNext(f_Gun+1,"X",1),    -- f_Gun 호출, 끝나면 다음 슬롯 트리거로
    SetCtrigX(... 0x158 ...), SetCtrigX(... 0x15C ...), SetCtrig1X(... 0x164 ...)  -- 복귀 next 복구
}, 1, TempCIndex)                                     -- 보존
```

- `Var_InputCVar` 는 `SetCVar(FP,Var_TempTable[i][2],SetTo,0)` 55개다(ResV `:258-260`). 값 칸 0 은 초기값일 뿐이고, 보내기·되쓰기가 그 칸을 고치므로 실행하면 **레지스터에 슬롯 값이 실린다**. TS 의 같은 줄 주석 "필드 초기화(0으로 리셋)" 은 틀린 설명이다(TS `185`).
- 한 프레임 비용: 슬롯 수만큼 조건 검사(빈 슬롯 포함) + 활성 슬롯마다 적재 트리거 1 + 본체.
- `Actived_Gun` 은 루프가 끝난 뒤에만 맞는 값이다(UERE `LevelUp.lua:28-29` 가 보스 무적 해제 조건으로 씀).

### 2.5 본체 `f_Gun`

| 부분 | 내용 | 근거 |
|---|---|---|
| 머리 | 좌표를 스포너 전역에 복사(`G_CB_X/Y` ← 줄 1·2), 로케이션 0 을 그 자리에, 랜덤 스위치, `GunCaseCheck=0`, **프레임 타이머 줄 7 += 1** | ResV `:331-336`; Mem2 `:209-215`(G_CA_CenterX/Y/Player ← 줄 1·2·4); GR `:176-180`(줄 7 **Subtract 1**) ; G2R `Gun_SpawnSet.lua:8-9` |
| 유형 분기 | `CIf_GCase(UnitID)` = `CIf(FP,{Gun_Line(0,Exactly,UnitID), Gun_Line(54,AtMost,0)},{SetCD(GunCaseCheck,1)})` 를 UnitID 마다 차례로(if 사슬). 등록한 UnitID 는 `f_GunTable` 에 쌓여 보내기 목록이 된다. ResV 는 `ForceOption=1` 이면 목록에서 빼고(강제 입력 전용), 같은 번호 두 번이면 `GCase_Duplicated` | ResV `:316-322`, Mem2 `:201-204` |
| 도우미 | `GCP(v,t)` = `Gun_Line(4,t,v)`(소유자), ResV `GNm(v,t)` = `Gun_Line(3,t,v)`(건물 번호), Mem2 `Gun_LineRange(n,a,b)` = `{AtLeast a, AtMost b}` | ResV `:323-330`, Mem2 `:160-163, 205-208` |
| 공통 꼬리(ResV) | 2젠 건물 10종: 반납 표시가 없으면 줄 5 := 1(첫 사이클 끝), 줄 6 ≥ 1 이면 반납, 시간 되면 줄 6 := 1 | ResV `:2945-2971` |
| 미등록 검사 | `GNm(51,AtLeast)` 또는 `GunCaseCheck == 0` 이면 줄 54 := 1 + 오류 문구 | ResV `:2976, 2978`; Mem2 `:3720`(되쓰기 **뒤**에 검사) |
| 되쓰기 | `TSetMemory(G_TempH + k·8, SetTo, 레지스터 k)` 55개를 `CDoActions` 하나로 | ResV `:2979-2983`, Mem2 `:3715-3719`, UERE `CallTriggers.lua:167-172`, GR `:960-964` |
| 반납 코드 | `줄 54 ≥ 1` 이면 (ResV: 줄 53 == 0 일 때 `GunCcode -= 1`) → `CWhile` 로 55칸을 하나씩 0 으로 → (Limit==1) 시험 문구 | ResV `:2984-2994`, Mem2 `:3721-3733`, UERE `:174-185` |
| G2R 꼬리 | 되쓰기가 **없다**(쓰기가 슬롯에 바로 가므로). `줄 4 += 1`(타이머) 뒤 반납 코드 | G2R `Gun_SpawnSet.lua:1110-1124` |

### 2.6 일시 정지·종료

| 이름 | 실제 동작 | 근거 |
|---|---|---|
| `Gun_DoSuspend()` (ResV·Mem2·GR) | `SetCVar(레지스터 55 = 줄 54, Add, 1)` → **이번 사이클 끝에 반납**. 본체의 나머지는 계속 돈다. 다른 `CIf_GCase` 는 `줄54 ≤ 0` 조건 때문에 안 들어간다 | ResV `:274-276`, `:317` |
| `Gun_DoSuspend()` (UERE) | `Gun_SetLine(54,SetTo,1)` (같은 효과) | UERE `func.lua:520-522` |
| `Gun_DoSuspend()` (G2R) | `TSetMemory(G_TempH+54·8, Add, 1)` — **슬롯에 바로** 씀. 이번 사이클의 반납 검사는 적재된 사본(줄 54 = 0)을 보므로 **반납은 다음 사이클**에 된다. 그래서 G2R 은 트리거마다 `Gun_Line(54,AtMost,0)` 을 붙인다 | G2R `func.lua:43-45`, `Gun_SpawnSet.lua:322, 419, 502, 590, …` |
| 줄 53 (ResV) | 1 이면 반납 때 `GunCcode`(남은 건물 수, 승리 조건) 를 줄이지 않는다 — 강제 입력 건작(콜·로켓) 표시 | ResV `:1593, 1811, 2985`; `System.lua:1602`(`GunCcode==0` → 승리), `Interface.lua:662`(배치 때 +1) |
| 일시 정지 | **없다.** "멈췄다 다시 도는" 레코드는 원본 어디에도 없다 | — |

### 2.7 오류·시험 문구

| 문구 | 언제 | 근거 |
|---|---|---|
| `"\x07『 \x08ERROR : \x04f_Gun의 목록이 가득 차 G_Send를 실행할 수 없습니다! 스크린샷으로 제작자에게 제보해주세요!\x07 』"` + Buzz ×3 | 보내기 넘침 | ResV `:26, 244`; UERE `Var_Include.lua:57`; G2R `init.lua:59`; Mem2 `:21`(StrDesign 판) |
| `"\x07『 \x08ERROR : \x04등록되지 않은 건작이 작동하여 자동으로 Suspend하였습니다. 건작을 등록해주세요.\x07 』"` + Buzz ×2 | 등록 안 된 UnitID, (ResV) 건물 번호 ≥ 51 | ResV `:312, 2976, 2978`; Mem2 `:199, 3720` |
| `GunCaseErrT2` "등록되지 않은 건작 인덱스…" | **정의만 되고 안 쓰인다**(번호 ≥ 51 에도 위 문구를 씀) | ResV `:313` |
| `"TESTMODE OP : f_GunSend 성공. f_Gun 실행자 : N"`, `"…EXCunit Number : N"`, `"…f_Gun Suspend 성공…"` | `Limit==1`(Mem2 는 `TestMode` 코드도) | ResV `:239-242, 2991-2993`; Mem2 `:84-89, 3726-3730` |
| `GCase_Duplicated` (컴파일) | 같은 UnitID 의 `CIf_GCase` 두 번 | ResV `:321` |

### 2.8 맵별 차이

| 항목 | ResV | Mem2 | GR (구판) | G2R (=G2) | UERE (=UE) |
|---|---|---|---|---|---|
| 크기 × 줄 | 128 × 55 (`main.lua:67`) | 128 × 55 (`main.lua:145`) | 64 × 55 (`main.lua:111`) | 128 × 55 (`System.lua:197`, `main.lua:108`) | 128 트리거, **127 사용** × 55 |
| 정의 위치 | `Include_GunData` 안 | 같음 + `G_init()` 분리 | 같음 + `G_init()` | 맵 곳곳(`main.lua`, `func.lua`, `System.lua`, `Gun_SpawnSet.lua`) | 곳곳(`Var_Include.lua`, `CallTriggers.lua`, `func.lua`) |
| 보내기 필드 | 0~4 | 0~4 (3 = EXCC 0번 줄) | 0~4 | 0~3 | 0~3, 53 |
| 강제 입력 | `f_GunForceSend` (같은 본체, 옵션 Ccode) | `f_GForceSend` (본체 복사) | 없음 | `f_ForcePosSave` | 없음 |
| `Gun_SetLine` 쓰기 대상 | 레지스터 | 레지스터 | 레지스터 | **슬롯 직접** | 레지스터(`Gun_SetLineX` = T 판) |
| `TGun_Line`/`TGun_SetLine` | 있음 | 있음 | 있음 | 없음 | `Gun_SetLineX` |
| 되쓰기 | 55칸 매 사이클 | 55칸 (미등록 검사 앞) | 55칸 | 없음 | 55칸 |
| 반납 표시 | 줄 54 Add 1 | 같음 | 같음 | 줄 54 Add 1 (슬롯 직접, 다음 사이클) | 줄 54 SetTo 1 |
| 타이머 줄 | 7 (+1/사이클) | 7 (+1), 8 (+Dt ms) | 7 (**−1** 포화) | 4 (+1) | 4 (+1) |
| 유형 분기 | `CIf_GCase` 28 | `CIf_GCase` 20 | 20 | `CIf(TTOR({Gun_Line(0,…)}))` 손 분기 | `Case_*()` 함수 + 줄 53 ≤ 255 가드 |
| 남은 수 | `GunCcode`(손 관리) | 패턴별 Ccode | — | — | `Actived_Gun` |
| 줄 사용 합(Line+SetLine) | 777 | 768 | 189 | 388 | 401 |

(줄 사용 수는 `field_count_out.txt`. R1 표의 774/735/388/401 과 Mem2 가 다른 것은 `Gun_LineRange`·`TGun_` 을 세는 방식 차이다.)

### 2.9 줄 번호 → 뜻 (빈도는 조건+대입 합)

**공통**: 0 = 건물 UnitID, 1 = X(픽셀), 2 = Y(픽셀), 54 = 반납 표시.

| 줄 | ResV (777) | Mem2 (768) | G2R (388) | UERE (401) | GR (189) |
|---|---|---|---|---|---|
| 0 | UnitID (11) | UnitID (12) | UnitID (51) | UnitID (23) | UnitID (1) |
| 1 | X (VTT[2] 13) | X | X | **X 조건 90회**(맵 좌우 판정 `Gun_Line(1,AtMost,48*32)`, `Gun_SpawnSet.lua:14`) | X |
| 2 | Y | Y | Y | Y | Y |
| 3 | 건물 번호 `GNm` (1+136) | 건물 번호(EXCC 0번 줄) (82) | 변형 번호(CUnit 바이트) (92+13) | 건작 레벨(EXCC 0번 줄) (4) | 번호 (36) |
| 4 | 소유자 `GCP` (1) | 소유자 `GCP` (4+74) | **프레임 타이머** (61+19) | **프레임 타이머** (25+25, 첫 사이클에 +480 건너뛰기 `Gun_SpawnSet.lua:7`) | 소유자 (1) |
| 5 | 첫 사이클 끝 표시 (92+5) | 같음 (27+1, `:370`) | 웨이브 번호 (103+10) | 웨이브 번호 (217+14) | — |
| 6 | 단계·배속(189 케이스) (101+11) | 단계 (78+9) | 작업 (2+6) | — | — |
| 7 | 프레임 타이머 (118+11) | 프레임 타이머 (29+11) | — | — | 거꾸로 타이머 (21+20) |
| 8 | ms 타이머·상태(케이스별) (391+6) | ms 타이머(+Dt, `:456`) (243+20, Range 22) | — | — | 작업 (72+17) |
| 9 | — (`Var_TempTable[9]` 는 줄 8) | 웨이브 카운터 (17+11) | — | — | 작업 (9+7) |
| 10~19 | 11 왕복 카운터(0~60), 13 매 사이클 +3 (127 케이스, `:1517-1528`) | 3D 도형 인자 TSize·X/Y/Z 각·Move1/2 (`:701-706`, `SetLine(17-1…)` 등) | — | — | 10 (1) |
| 20~31 | — | 20 찍음 표시, 24~26 벌점, 30 Axiom 보스 모드, 31 보스 도입 끝 (`:469, 1028-1030, 1156`) | — | — | — |
| 50~53 | 50 왕복 방향, 51 반지름 누적(± 줄 11), 52 각도(+3, 72 이면 0) (127 케이스), **53 = 카운트 제외** | — | 50~52 작업 | **53 = Gun_Type(256 잡건작)** | — |

결론: **0~2·54 만 공통**, 3~8 은 맵마다 뜻이 다르고, 9 이후는 **케이스(UnitID)마다 뜻이 다른 작업 칸**이다. 55줄 중 실제로 쓰는 줄은(54 포함) ResV 16개, Mem2 약 33개, G2R 11개, UERE 8개다.

---

## 3. TStruct (`MapSource\Library\TStruct.lua`)

### 3.1 API

| 함수 | 뜻 | 근거 |
|---|---|---|
| `TStruct_init(P, Number, Line, HumanPlayers)` | 구조체 하나. `Line` 1~55(액션 64 한도에서 나온 값), `Number ≥ 1`. 만드는 것: `StartIndex` 라벨, 작업 레지스터 `VarArr`(Line개), `InputH`(슬롯 0 EPD, 맵 시작 때 새김), `TempH`, 본체 호출 라벨 `SetCallIndex`, **보내기용 레지스터 `SendVarArr`(Line개 더)**, 보내기 서브루틴. 반환 `{P, VarArr, Number, SetCallIndex, StartIndex, InputH, TempH, SendVarArr, Send_CallIndex}` | TS `79-155` |
| 보내기 서브루틴 | **넥스트 맞춤**: 마지막 성공 슬롯 다음(`TStr_NextTry`)부터 `필드1 ≤ 0` 인 칸을 찾아 **Line 칸 전부** 씀, 커서 갱신(끝이면 0). Number 칸 모두 차면 오류 문구 | TS `101-143` |
| `TS_CreateArr(S)` | 워커 트리거 Number개(건물 스택 슬롯과 같은 모양, 제어 액션 6개: `f_GunNum`·활성 수 없음). **런타임 구역**에서 부른다 | TS `171-193`; Seed `GunSystem.lua:1181-1188`, UERE `Sans.lua:492-493` |
| `TStr_Func(S)` … `TStr_EndFunc()` | 본체 열기/닫기. 전역 `TS_Data/TS_Player/TS_VarArr/TS_CallIndex` 를 설정 → **중첩 불가**, **선언 전용 CJump 블록 안**에 둬야 함. `EndFunc` 가 `TStr_WriteData`(Line칸 되쓰기) 후 닫음 | TS `226-240`; Seed `main.lua:252` |
| `TStr_WriteData(S)` | `TSetMemory(Vi(TempH, (i-1)·8), SetTo, VarArr[i])` Line개 | TS `201-212` |
| `TS_Suspend(C, Flags)` | 조건이면 **레지스터 전부 0** → EndFunc 의 되쓰기가 슬롯을 비움(= 반납). 기본 보존. **본체 맨 끝**에 둬야 함(뒤 코드는 0 을 봄) | TS `248-257`; Seed `GunSystem.lua:1169-1173` |
| `TSLine(L,T,V,M)` / `TTSLine` | 조건. **L 은 1부터**(`TS_VarArr[L]`) | TS `264-271` |
| `SetTSLine(L,T,V,M)` / `TSetTSLine` | 레지스터 쓰기 액션 | TS `272-279` |
| `TS_Send(C, S, Props, PF)` | 상수만. 없는 필드는 0. `CallTriggerX(..., PF)` → `PF==nil` 매번, `1` 한 번 | TS `288-304` |
| `TS_SendX(C, S, Props, PF)` | 변수 허용(TSetCVar). `PF==nil` → `CIf`, 아니면 `CIfOnce`(게임당 한 번). **식(`_Add(...)`)을 넣으면 버그**(원 주석) | TS `310-333`; Seed `CunitSystem.lua:825-827` |

### 3.2 수명 규칙

1. 생성: `TS_Send(X)` → `SendVarArr` 에 값 → 보내기 서브루틴이 빈 칸(필드 1 ≤ 0)에 **모든 필드** 기록.
2. 활성: 워커 조건 `필드 1 ≥ 1`. **필드 1 이 0 이 되는 순간 그 레코드는 조용히 멈추고**(워커가 안 돎) 다음 보내기에 덮인다. Seed 는 필드 1 = UnitID 로 두고 0 을 컴파일 오류로 막는다(Seed `GunSystem.lua:884-888, 985-989`). UERE 는 필드 1 = **X 좌표**라 X 가 0 이 되면 총알이 멈춘다(추측: 맵 안 좌표라 실제로는 안 생김).
3. 매 사이클: 워커가 적재 → 본체 → Line칸 되쓰기(바뀐 칸만이 아니라 전부).
4. 반납: `TS_Suspend` 가 레지스터를 0 으로 → 되쓰기. 슬롯 번호 변수는 없다(`TempH` 만).
5. 시작 순서: 레지스터 할당(`TStruct_init`)과 본체는 init 블록, 워커는 런타임 블록(Seed `GunSystem.lua:36-45`).

### 3.3 사용처

| 맵 | 구조체 | 필드 | 근거 |
|---|---|---|---|
| Seed | `GunStruct = TStruct_init(FP, GunPoolSize=36, 13, HumanPlayers)` | `unit x y owner timer phase work1 work2 work3 done gunid glevel efftimer` (이름 → 번호는 `GunF`, 1부터) | `MapConfig/Buildings.lua:974, 1027`; `MapLogic/GunSystem.lua:70-94, 1044` |
| Seed 본체 | ① timer==0 이면 BGM 요청·안내·보상 ② UnitID 분기(표 `GunPatternDefs`) ②-R 함정(gunid) ②-U 패턴 없는 건물 즉시 done ③ timer += GunMsPerCycle ④ done≥1 또는 timer≥최대면 반납 | `GunSystem.lua:1046-1175` |
| Seed 입구 | 죽은유닛 단락 `RunGunEntrance()` 가 UnitID/좌표/막타 플레이어를 읽어 UnitID 마다 `GunSend(조건, UnitID, X, Y, owner, gunid)`. `GunSend` 는 `glevel` 에 종류별 카운터를 찍고 +1 | `CunitSystem.lua:745-835`; `GunSystem.lua:1249-1279` |
| UERE | `BlasterBullet = TStruct_init(FP,32,20,…)`, `BoneBullet = TStruct_init(FP,200,20,…)` (init 블록) | `main.lua:120-121` |
| UERE Blaster | 1 시작X 2 시작Y 3 목표X 4 목표Y 5 모드 6 각도 8 NukeDot 반복 15 첫 사이클 16~20 임시 | `CallTriggers.lua:699-711` |
| UERE Bone | 1 X 2 Y 3 프레임(30 이면 반납) | `CallTriggers.lua:893-939` |
| UERE 보내기 | 1,700칸 CUnit 훑기 안에서 조건 맞는 유닛마다 `TS_SendX({}, BoneBullet, {CPosX,CPosY})`; 시간표 `TS_SendX(CD(PattC[3],200+80), BlasterBullet, {상수 6개})` | `Sans.lua:57-73, 85-96` |

### 3.4 건물 스택과의 공통점·차이

| | 건물 스택 | TStruct |
|---|---|---|
| 슬롯 = 트리거 1개, 필드 = 액션 값 칸 | 같음 | 같음 |
| 활성 판정 | 줄 0 ≥ 1 | 필드 1 ≥ 1 |
| 번호 | **0부터**(`Var_TempTable[Line+1]`) | **1부터**(`TS_VarArr[Line]`) |
| 줄 수 | 55 고정 | 1~55 선택 |
| 보내기 탐색 | 첫 맞춤(매번 0부터), 슬롯 i 를 알려 줌(시험 문구) | 넥스트 맞춤 |
| 보내기 쓰기 | 앞 몇 칸만(나머지는 반납 때 0 이라고 가정) | 모든 칸 |
| 보내기 레지스터 | 공용 전역(`CPosX`, `GunID`…) | 구조체 전용 `SendVarArr` |
| 슬롯 번호·활성 수 | `f_GunNum`, `Actived_Gun` | 없음 |
| 반납 | 줄 54 표시 → 되쓰기 뒤 `CWhile` 55회로 0 채움 | 레지스터 0 → 되쓰기 |
| 미등록 유형 검사 | 있음(문구 + 자동 반납) | 없음(Seed 는 ②-U 로 대신) |
| 이름 붙인 필드 | 없음(도우미 `GCP`/`GNm` 둘) | Seed 가 `GunF` 이름표로 감쌈 |
| 여러 구조체 | 맵당 하나 | 여럿(UERE 2개) |

---

## 4. 실제 사용 모양 대표 예

### 4.1 줄 번호 조건 (첫 사이클 · 단계 · 시간)

| 모양 | 예 |
|---|---|
| 첫 사이클에만 소환 | `G_CB_TSetSpawn({Gun_Line(5,Exactly,0),CD(GMode,3)}, CUTable1, _G[ShapeSC], nil, {OwnerTable=P7,RotateTable="Main",RepeatType={...}})` ResV `GunData.lua:418`; `G_CA_SetSpawn2X({Gun_Line(3,Exactly,1),Gun_Line(5,Exactly,0)},{55,53,54,48},"ACAS","Circle3",1,444,nil,"CP")` Mem2 `GunData.lua:235` |
| 단계 넘기기 | `CTrigger(FP,{Gun_Line(7,AtLeast,360)},{Gun_SetLine(6,Add,1),Gun_SetLine(7,SetTo,0)},1)` ResV `:891` |
| 반납 | `CTrigger(FP,{Gun_Line(6,AtLeast,3)},{Gun_DoSuspend()},1)` ResV `:925`; `TS_Suspend({TSLine(3, AtLeast, 30)})` UERE `CallTriggers.lua:938` |
| ms 구간 | `TriggerX(FP,{Gun_LineRange(8,17520,22920),CV(CA_ACCR,150,AtMost)},{AddV(CA_ACCR,1)},{preserved})` Mem2 `:1684` |
| 이름 붙인 판 (Seed) | `CIf(FP, {G.Line("timer", AtLeast, At), G.Line("phase", Exactly, W - 1)})` … `G.SetLine("phase", SetTo, W)` — "AtLeast 로 열고 phase 로 닫는 1회성 관용구" Seed `MapLogic/JobBuilding.lua:219-237` |
| 첫 사이클 표시(TStruct) | `CIf(FP,TSLine(15, Exactly, 0),{SetTSLine(15, SetTo, 1)})` UERE `CallTriggers.lua:717` |
| 소유자별 | `CSPlot(EffShape1,i,84,0,{TempleXY[i-3][1],TempleXY[i-3][2]},1,32,FP,{Label(),GCP(i),Gun_Line(20,AtMost,0)},{Gun_SetLine(20,SetTo,1)},1)` Mem2 `:469` |

### 4.2 필드끼리 계산

- `TGun_SetLine(51,Add,Var_TempTable[12])` / `TGun_SetLine(51,Subtract,Var_TempTable[12])` — 줄 51 ± 줄 11 (포화 뺄셈) ResV `:1522-1523`
- `Gun_SetLine(11,Subtract,1)` 뒤 `Gun_Line(11,Exactly,0)` — **포화에 기대는** 왕복 ResV `:1519-1520`
- `f_Lengthdir(FP, _Div(Var_TempTable[52],_Mov(7)), _Add(Var_TempTable[53],CI), NPosX, NPosY)` ResV `:1533`
- `Set_EXCC2(DUnitCalc, CunitIndex, 2, SetTo, _Add(_Mul(_Sub(Var_TempTable[4],1),4),Var_TempTable[7]))` — (줄3−1)·4 + 줄6 을 소환 유닛의 EXCC 에 ResV `:1542`
- `TGun_SetLine(8, Add, Var_TempTable[7]), TSetMemory(0x5124F0, SetTo, Var_TempTable[7])` — 줄 8 += 줄 6, 게임 속도 = 줄 6 ResV `:2101`
- `CMov(FP,TS_VarArr[17],_Div(_Sub(TS_VarArr[3], TS_VarArr[1]),5),1); CAdd(FP,TS_VarArr[1],TS_VarArr[17])` — 목표 쪽으로 1/5 씩 UERE `CallTriggers.lua:735-751`
- `TGun_SetLine(11,Add,CA_ACCV)`, `TGun_SetLine(17-1,Add,CA_ACCV2)` Mem2 `:1620-1623`

### 4.3 다른 모듈과 주고받기

| 상대 | 모양 | 근거 |
|---|---|---|
| G_CB/G_CA 스포너 | 본체 머리에서 중심 좌표·소유자 전역에 복사, 소환 호출 조건에 줄 조건 | ResV `:332-334, 416-423`; Mem2 `:211-213`; Seed `GunSystem.lua:1050-1051` (+ `Engine/G_CB_Lib.lua:2220-2223` "CenterXY 생략 = G_CB_X/Y 기준") |
| G_CB PreserveFlag | **공유 본체 안에서 `1`(한 번)을 주면 게임당 한 번**이 된다. UERE 는 한 번만 나오는 보스라 `1` 을 줌 | Seed `Engine/G_CB_Lib.lua:2225-2229`; UERE `Gun_SpawnSet.lua:14-30` |
| 보스 패턴 | 레코드 필드를 3D 도형 전역에 복사한 뒤 CA 찍기 | Mem2 `:701-706`; Axiom 보스 모드 줄 30·31 `:1028-1030, 1156` |
| 유닛별 저장(EXCC) | 보내기가 죽은 유닛 EXCC 를 읽고(줄 3), 본체가 소환 유닛 EXCC 에 씀 | ResV `:236`, `:1542`; `CallTriggers.lua:166-167` |
| 슬롯 번호 = 자원 번호 | `f_GunNum` 으로 슬롯마다 로케이션 하나(`CurLoc2 = f_GunNum + 190-64`) | G2R `Gun_SpawnSet.lua:31-38` |
| 전역 신호 모으기 | 여러 총알 본체가 효과음 Ccode 를 1 로 → 루프 뒤 한 번 재생 | UERE `CallTriggers.lua:718-719` |
| 남은 수·승리 | `GunCcode`(배치 +1, 반납 −1, 0 이면 승리), `Actived_Gun ≤ 2`/`≤ 0` 조건 | ResV `System.lua:1602`, `Interface.lua:662`, `GunData.lua:2985`; UERE `LevelUp.lua:28-29` |
| 본체 안에서 새 건작 | 보스 본체가 `f_GForceSend` 두 번 (`CIfOnce`) | Mem2 `:3481-3492` |
| 안내·보상 | `DisplayPrint(HumanPlayers, {Head, GunOre, Tail})`, `ExchangeAwardOre(GunOre, owner)` | Seed `GunSystem.lua:1083-1104` |

---

## 5. 비용

### 5.1 원본 (CtrigAsm)

트리거 1개 = 2,416B(tepc 배치 간격). 변수 1개도 트리거 1개다(VarStack 포크를 켜면 72B, Seed 만 켬).

| 맵 | 슬롯 저장 | 레지스터 | 합 | 매 프레임 고정 |
|---|---|---|---|---|
| ResV / Mem2 / G2R / UERE | 128 × 2,416 = 309,248 | 55 × 2,416 = 132,880 | **442,128B (432KB)** | 조건 검사 128 |
| GR | 64 × 2,416 = 154,624 | 132,880 | 287,504B | 64 |
| Seed TStruct | 36 × 2,416 = 86,976 | 26개(`VarArr`+`SendVarArr`) × 72 = 1,872 (VarStack 끄면 62,816) | 88,848B (149,792B) | 36 |
| UERE TStruct 2개 | 232 × 2,416 = 560,512 | 80 × 2,416 = 193,280 | **753,792B** | 232 |

활성 슬롯마다: 적재 트리거 1(액션 55~62개) + 호출·복귀 2 + 본체 + 되쓰기 `CDoActions`(T 액션 55개, 준비 트리거 수는 미확인) + 반납 검사. 반납할 때는 `CWhile` 55회(약 55×3 실행, 추측).

### 5.2 eudplib 0.81 측정

정적 = 호출 자리 트리거 수(첫 호출은 본문 포함), 실행 = 에뮬레이터 실행 트리거 수(기준 대비).

| 연산 | 정적 | 실행 |
|---|---|---|
| EUDStruct **정적** 인스턴스: 조건 `EUDIf(s.timer==0)`+EndIf / `s.timer = 5` / `+= 16` / `x << s.timer` | 3 / 1 / 1 / 2 | — |
| EUDStruct **포인터**(`Rec.cast(v)`): `x << p.timer` | 4 (매번) | **11** |
| 포인터: `EUDIf(p.timer==0)`+EndIf | 5 | **7** |
| 포인터: `p.timer = 5` / `= x` / `+= 16` / `+= x` | 2 / 1 / 2 / 1 | `+= 16`: **10** |
| `EUDMethod` 정적 인스턴스 s (첫) / s2 / 포인터 | 8 / **1** / 1 | — |
| `EUDArray` 변수 색인 읽기 / 쓰기 / `+= 1` | 3 / 1 / 2 | 읽기 **38** |
| `EUDVArray` 변수 색인 읽기 / 쓰기 / `= a[i]+1` | 2 / 1 / 3 | 읽기 **12** |
| `f_dwread_epd` / `f_dwwrite_epd` | 2 / 1 | 읽기 **36** |
| `ObjPool(64,13).alloc` (첫/다음) / `free` | 12 / 3 / 4 | — |
| 유형 분기 26경우(ResV 번호): `EUDSwitch` / `EUDIf` 사슬 | 108 / 78 (경우 본문 포함) | **6~7** / **25~27** |
| **사슬 적재**(시제품) 13필드, 핸들을 알 때 / 살아 있는 목록 원소를 거칠 때 | 2 / 2 | **17 / 19** (필드 값 모두 맞음) |
| **되쓰기**(시제품) 3필드, `f_dwwrite_epd(EPD(rec)+18k+87, reg)` | 7 | **18** (저장 값 맞음) |

페이로드(재배치 전 길이, `exp_payload_out.txt`, 두 번 실행한 범위): 원소당 기울기가 EUDArray 8~12B, EUDVArray·`_EUDVArrayData` 73~83B, ObjPool 필드당 73~76B 로 나왔다(이론 4B / 72B / 72B — 실행마다 값이 조금씩 달라 할당기 배치 잡음으로 본다). **`EUDStruct.alloc()` 전역 풀은 +19,284,332~19,284,764B**(이론 32,768 × 8 × 72 = 18,874,368B, EP81 `collections/objpool.py:95`)이고, 필드가 8개를 넘으면 컴파일 오류다(`objpool.py:63-68`).

### 5.3 eudext pool 추정

제안 저장(6.11): 레코드당 (F + 3) × 72B(숨은 필드 3개) + 살아 있는 목록 72B + 빈 칸 스택 4B, 레지스터 (F+3) × 72B 한 벌.

| 대상 | F(이름 붙일 필드) | 용량 | 저장 | 원본 대비 |
|---|---|---|---|---|
| ResV | 16 (0~8, 11, 13, 50~53 + 여유 1) | 128 / 64 | 186KB / 94KB | 432KB |
| Mem2 | 16 (나머지 보스 전용 칸은 레코드 밖 전역으로) | 128 | 186KB | 432KB |
| Mem2 (55줄 그대로) | 55 | 128 | 548KB (**원본보다 큼** — F+3 > 33 이면 손해) | 432KB |
| G2R | 10 | 128 | 130KB | 432KB |
| UERE 건작 | 7 | 127 | 101KB | 432KB |
| Seed | 13 | 36 / 64 | 45KB / 80KB | 87~146KB |
| UERE Bone / Blaster | 3 / 14 | 200 / 32 | 102KB / 43KB | 754KB (둘 합) |

매 프레임 실행(N = 살아 있는 수, W = 바뀐 필드 수, B = 본문):

| | 원본 | eudext (시제품 수치) | eudext (목표) |
|---|---|---|---|
| 빈 풀 | 용량만큼(128) | ≤ 6 | ≤ 6 |
| 방문당 고정 | 약 3 + 되쓰기(미확인) | F + 17 + 6W | F + 12 + 2W |
| Seed (F=13, W=3, N=5) | 36 + 5×(3+?) | 약 246 | 약 161 |

**판정**: 방문당 고정비는 원본보다 크다(원본은 적재가 트리거 1회). 대신 빈 슬롯 비용이 없고 저장이 절반 이하다. 본문 안의 필드 조건 비용은 원본과 같다(둘 다 변수 조건 1개). 포인터(EUDStruct) 방식이었다면 본문의 필드 연산마다 7~11 이 더 든다 — ResV 본체의 줄 조건 728개 중 한 프레임에 수십 개만 평가돼도 수백 실행이다.

---

## 6. `eudext.pool` API 확정안 (DESIGN 4.11 초안을 고침)

### 6.1 설계 결정

| 주제 | 결정 | 이유 |
|---|---|---|
| 필드 접근 | **레지스터 방식**: 풀마다 필드별 `EUDVariable` 한 벌. 방문하면 레코드를 레지스터에 싣고, 본문은 레지스터를 쓰고, 끝에 되쓴다 | 원본 관용(`Gun_Line`=변수 조건)과 같고 조건 비용 0. 포인터 방식은 연산마다 7~11(5.2) |
| 저장 | **사슬 저장**: 레코드 h 의 필드 k = 72B 변수 원소, 목적지 = 레지스터 k, next = 필드 k+1(마지막은 복귀 트리거). 비공개 `_EUDVArrayData`(원소별 dest/value/nextptr, EP81 `core/eudstruct/vararray.py:37-66`) 또는 `EUDCustomVarBuffer`(EP81 `core/variable/vbuf.py:130-172`)를 `_compat` 로 감싼다 | 점프 한 번에 F칸 적재(시제품 실행 F+4~6). EP81 `collections/eudqueue.py:25-67` 이 같은 기법(목적지를 미리 정한 원소로 점프)을 쓴다 |
| 숨은 필드 | `_self`(레코드 주소, 상수), `_index`(0..cap-1, 상수), `_alive` | 되쓰기 주소·슬롯 번호·표식을 적재할 때 공짜로 얻음 |
| 핸들 | **레코드 주소**(`EUDVariable`), 0 = 없음. 번호는 `g.index`/`pool.index_of(h)` | 곱셈 없이 점프·쓰기. 번호 0 도 유효 |
| 살아 있는 목록 | 72B 원소 배열 `live[]`(원소 값 = 레코드 주소, 목적지 = 점프 트리거의 next) + 개수 | 목록 원소 실행 1회로 점프 주소 적재(시제품 19) |
| 해제 | **표식 + 루프가 정리(압축)**. 순서가 유지된다 | 루프 밖·다른 레코드 해제도 O(1), 위치표 불필요. 6.12 |
| 할당 | 빈 칸 스택(EUDArray, 처음엔 0,1,2… 순) | ObjPool 과 같은 구조(EP81 `objpool.py:39-85`) |
| 새 레코드 | **다음 tick 부터** 돈다(루프 시작 때 길이 고정) | 본문이 본문을 낳는 폭주 방지. 원본(첫 맞춤)은 "뒤 번호면 같은 프레임" 이라 순서만 다르다 |
| 유형 분기 | `EUDSwitch`(이진 탐색, 실행 6~7) 또는 epScript `switch`. 도우미 `pool.dispatch` | if 사슬 25~27 대비 |
| 되쓰기 | **본문 생성 중 보기 객체로 접근한 필드 중 `readonly` 가 아닌 것만**(루프 호출 자리마다 컴파일 때 정함). 접근만 기록하므로 `DoActions(g.timer.SetNumber(5))` 같은 직접 쓰기도 잡힌다. `Field(readonly=True)` 는 되쓰지 않고, 보기로 대입하면 컴파일 오류 | 원본은 55칸 전부. 쓰기만 추적하면 직접 액션 쓰기를 놓친다 |
| 금지 | `EUDStruct.alloc()`/epScript `P.alloc()`(전역 풀 18.9MB), 같은 풀 `each` 중첩, `each` 안 `EUDBreak`(1단계) | 5.2, 6.5 |

### 6.2 레코드 선언

```python
from eudext.pool import Pool, Field

guns = Pool("Gun",
    fields=[Field("unit", readonly=True), Field("x", readonly=True), Field("y", readonly=True), "owner", "timer", "phase",
            Field("dir", signed=True), "work1", "work2", "done", "gunid", "glevel"],
    capacity=36,
    aliases={0: "unit", 1: "x", 2: "y", 4: "owner", 7: "timer"},   # 옛 줄 번호(선택, 6.9 표)
    alias_base=0,            # Gun_Line 식 0부터 / TSLine 식이면 1
    on_full="report",        # "report"(원본 문구+Buzz) | "silent" | 함수(콜백)
    on_unknown="report",     # dispatch 기본 가지: 문구 + 반납 (원본 GunCaseErrT) | "silent" | 함수
    writeback="accessed",    # "accessed"(접근한 쓰기 가능 필드) | "all"
    debug=False)             # True: alloc/free 시험 문구, 이중 해제 경고
```

- `fields`: 문자열 목록, 공백으로 나눈 문자열 하나(`"unit x y owner"` — epScript 용, 6.10), 또는 `Field` 객체. 이름은 파이썬 식별자, 밑줄로 시작 금지(숨은 필드 예약), 중복이면 `EPError`.
- `Field(name, init=0, signed=False, readonly=False)`: `init` 은 `alloc` 에서 값을 안 줬을 때의 기본값. `signed` 는 문서·`cmp` 선택용(저장은 같다). `readonly` 는 alloc 때만 쓰는 필드(유닛·좌표·소유자처럼) — 되쓰기에서 빠진다. 문자열 선언에서는 이름 뒤 `!` 로 표시한다(`"unit! x! y! owner timer"`).
- 보기 객체는 본문 생성 중 접근한 필드 이름을 모은다. 본문 밖에서 레지스터를 꺼내 두었다가 쓰면 목록에 안 잡히므로 `g.touch("name")` 으로 알린다. `Pool(..., writeback="all")` 은 쓰기 가능한 필드를 모두 되쓴다(안전 모드).
- 2단계(요청 시): `Field(name, hot=False)` = 적재하지 않는 찬 필드(EUDArray 4B, `g.get/set` 으로만, 읽기 실행 38), `Field.i64(name)` = 두 칸 + `Int64.wrap` 보기.
- 필드 수 상한은 두지 않는다(원본의 55 는 트리거 액션 한도였다). 단 F+3 > 33 이면 경고: "레코드당 저장이 CtrigAsm 트리거보다 크다 — 케이스 전용 칸은 전역으로 빼라".
- `capacity` 1 이상, 컴파일 상수.

### 6.3 풀 객체 멤버

| 멤버 | 형태 | 뜻 · 비용 목표 |
|---|---|---|
| `pool.cur` | 레지스터 보기(파이썬 객체) | `pool.cur.timer` = 필드 레지스터 `EUDVariable`. `each()` 가 넘겨주는 것과 같은 객체 |
| `pool.alloc(**init)` | → `EUDVariable` 핸들(0 = 실패) | 모든 필드를 씀(준 값 / `init` / 0). 실행 ≤ 3F+30, 호출 자리 ≤ 4 |
| `pool.free(h)` | 문장 | 표식. `h` 가 지금 방문 중인 레코드면 레지스터 `_alive` 도 0. 이중 해제는 무시(debug 경고). 실행 ≤ 6 |
| `pool.free_current()` | 문장 | 루프 안 전용. 레지스터 표식만(실행 1). 본문의 나머지는 계속 돈다(원본 `Gun_DoSuspend` 와 같음) |
| `pool.count` | `EUDVariable` | 논리 개수(alloc +1, 산 것 free −1). `Actived_Gun` 대체 |
| `pool.dropped` | `EUDVariable` | 넘침 누적 수(시험용) |
| `pool.full()` | Condition | 빈 칸 스택이 비었나 |
| `pool.index_of(h)` | `EUDVariable` | (h − 시작) ÷ (72·(F+3)) — `f_div` 1회. 루프 안에서는 `g.index` 를 쓴다 |
| `pool.get(h, name)` / `pool.set(h, name, v)` | 느린 경로 | 방문 중이 아닌 레코드의 필드. `f_dwread_epd`(실행 36) / `f_dwwrite_epd`. 레지스터를 건드리지 않는다. `h` 가 현재 레코드면 레지스터를 읽고/씀 |
| `pool.is_alive(h)` | Condition(앞 계산 있음) | `_alive` 읽기 |
| `pool.each(handle=False)` | 제너레이터 | 6.5 |
| `pool.dispatch(field, cases, default=…)` | 문장 | 6.6 |
| `pool.Line / SetLine / SetLineAct / LineRange / line` | 별칭 | 6.9 |
| `pool.capacity`, `pool.fields` | 파이썬 값 | — |

레지스터 보기 `g` 의 멤버: 필드 이름마다 `EUDVariable`, 숨은 것 중 `g.index`(0..cap-1), `g.handle`(= `_self`), `g.alive`(Condition 용 변수). `g.x = v` 는 `g.x << v` 로 바뀌고(`__setattr__`), `iaddattr/isubattr/…` 를 구현한다(epScript `_ATTW` 가 부름, EP81 `epscript/helper.py:197-224`). `-=` 는 wrap(DESIGN 3.5), 포화는 `g.isub_sat("x", v)`. `eqattr` 류가 없으면 `AttributeError` 를 내야 `_ATTC` 폴백이 동작한다(`helper.py:428-467`).

### 6.4 할당·해제 의미

- 빈 칸 스택 순서: 처음 `alloc` 은 번호 0, 1, 2… . 해제된 칸은 **살아 있는 목록에서 빠지는 순간** 스택에 쌓이고(LIFO) 그 뒤 `alloc` 이 다시 준다.
- 루프 안에서 현재 레코드를 해제하면 그 방문 끝에 곧바로 스택에 들어가 **같은 프레임 뒤쪽 alloc 이 재사용**한다(원본 반납과 같음).
- 루프 밖 `free(h)`, 또는 이미 방문을 마친 레코드의 `free(h)` 는 **다음 `each` 정리 때** 스택에 들어간다. 그 사이 풀이 가득이면 `alloc` 이 실패한다(시나리오 T9). 문서에 적는다.
- 넘침: `alloc` 이 0 을 돌려주고 `dropped += 1`. `on_full="report"` 면 원본 문구(2.7 첫 줄, "f_Gun" 대신 풀 이름)와 Buzz 를 HumanPlayers 에게. 호출자는 `if (h == 0)` 로 알 수 있다. 재시도·대기열은 없다(원본과 같음).

### 6.5 루프

```python
for g in guns.each():            # 파이썬
    if EUDIf()(g.timer == 0):
        ...
    EUDEndIf()
    g.timer += 16
    if EUDIf()(g.done >= 1):
        guns.free_current()
        EUDContinue()            # 나머지 건너뛰기(되쓰기는 그래도 한다 — 반납이면 생략)
    EUDEndIf()
```

규칙:

1. 루프 시작 때 살아 있는 목록 길이를 고정한다. 그 안의 레코드 중 **방문 전에 해제되지 않은 것만** 정확히 한 번 방문한다. 순서는 할당 순서(압축해도 유지).
2. 루프 안 `alloc` → 목록 끝에 붙고 **이번 루프에서는 안 돈다**.
3. 루프 안 `free` → 6.4. 현재 레코드면 방문 끝에서 되쓰기를 **생략**하고 칸을 스택에.
4. `EUDContinue()` = 본문 나머지 건너뛰고 방문 꼬리(되쓰기·압축)로. `EUDBreak()` 는 1단계에서 컴파일 오류.
5. 같은 풀의 `each` 를 중첩하면 컴파일 오류(레지스터 공유). 다른 풀은 된다.
6. `each` 호출 자리가 여럿이어도 된다(자리마다 루프 코드 1벌, 복귀 트리거 next 를 루프 머리에서 고쳐 씀).
7. 본문 안에서 **게임당 한 번** 구조(`EUDExecuteOnce`, 보존 안 한 RawTrigger 등)를 쓰면 풀 전체에서 한 번이 된다 — 원본의 같은 함정(8절 2번). 검사는 못 하므로 docstring 경고.
8. `each(handle=True)` 는 `(g, h)` 를 준다(epScript `foreach (g, h : guns.each(handle=true))` 번역 확인).
9. CP 를 바꾸지 않는다(3.6). 본문이 바꾼 CP 는 본문 책임.

### 6.6 유형별 처리

```python
@guns.case(131)                       # 해처리
def hatchery(g): ...
@guns.case(132, 133)
def lair_hive(g): ...

for g in guns.each():
    guns.dispatch("unit")             # EUDSwitch(g.unit) + 등록된 case 본문 인라인 + default = on_unknown
```

- 같은 번호 두 번 등록 → 컴파일 오류(원본 `GCase_Duplicated`).
- `default` 기본값 = `on_unknown`("report": 원본 `GunCaseErrT` 문구 + `free_current()`).
- `dispatch(field, cases={131: fn, …}, default=fn)` 로 표를 직접 줄 수도 있다(Seed `GunPatternDefs` 같은 표 구동).
- 함수 포인터 필드(`EUDFuncPtr`)는 두지 않는다(유형이 컴파일 상수라 필요 없음).
- epScript 는 `switch (g.unit) { case 131: …; break; default: guns.free_current(); }` 를 그대로 쓴다(번역 확인, 6.10).

### 6.7 일시 정지

원본에 없으므로(2.6) API 를 두지 않는다. 안내만 한다:

- 풀 전체 멈춤: `each` 루프를 조건 안에 둔다(안 부르면 비용 0).
- 레코드별 멈춤: 사용자 필드(`sleep` 등) + 본문 머리에서 `EUDContinue()`(적재 비용은 든다, 되쓰기는 0).
- DESIGN 4.11 초안의 `suspend` 필드 예는 "반납" 과 헷갈리므로 지운다(9절).

### 6.8 넘침 처리

6.4 의 `on_full`. 추가로 `debug=True` 면 이중 해제, 루프 밖에서 `free_current()` 호출(컴파일 오류), 방문 중 아닌데 `pool.cur` 쓰기(경고)를 검사한다.

### 6.9 옛 줄 번호 별칭

| 원본 | eudext | 비고 |
|---|---|---|
| `Gun_Line(n, T, v[, m])` / `TGun_Line` | `guns.Line(n, T, v, mask=m)` → Condition | `n` 은 `alias_base` 기준. 이름 문자열도 받음. `T` = `Exactly/AtLeast/AtMost`. `v` 가 변수여도 됨(변수 비교는 `cmp`) |
| `Gun_SetLine(n, M, v[, m])` / `TGun_SetLine` / `SetTSLine` / `TSetTSLine` | `guns.SetLine(n, M, v, mask=m)` → **바로 실행**(문장) | epScript 에서 반환값이 버려지므로 액션을 돌려주지 않는다. `M=Subtract` 는 **포화**(SC 액션 의미, DESIGN 3.5 의 CtrigAsm 이름 규칙) |
| (RawTrigger 액션 목록에 넣을 때) | `guns.SetLineAct(n, M, v)` → Action 목록 | 상수 `v` 만 한 액션, 변수 `v` 는 DoActions 안에서만 |
| `Gun_LineRange(n, a, b)` | `guns.LineRange(n, a, b)` → `[AtLeast a, AtMost b]` | Mem2 |
| `Var_TempTable[n+1]`, `TS_VarArr[n]`, Seed `G.Var(name)` | `guns.line(n)` → 레지스터 `EUDVariable` | 계산식에 그대로 |
| `Gun_DoSuspend()`, `TS_Suspend(C)`, Seed `G.Finish()` | `guns.free_current()` (조건은 `EUDIf`) | |
| `GCP(v)` / `GNm(v)` | `g.owner == v` / `g.gunid == v` | 맵별 도우미로 남기려면 사용자 코드에 한 줄 |
| `f_GunNum` / `Actived_Gun` | `g.index` / `guns.count` | `count` 는 루프와 무관하게 맞다 |
| `f_GSend(UnitID)` / `TS_SendX(C,S,{…})` / `GunSend(…)` | `if EUDIf()(조건): guns.alloc(unit=…, x=…, y=…)` | 식을 그대로 넣어도 된다(TS_SendX 제약 없음) |
| 이름이 없는 번호 | 컴파일 오류 "줄 N 에 이름이 없다 — aliases 에 넣어라" | |

맵별 별칭 표 제안(옮길 때 `aliases=` 로 그대로):

| 맵 | 표 |
|---|---|
| ResV | `{0:"unit",1:"x",2:"y",3:"gunid",4:"owner",5:"started",6:"phase",7:"frames",8:"ms",11:"swing",13:"spin",50:"swing_dir",51:"radius",52:"angle",53:"no_count"}` (54 → `free_current`. 8·11·13·50~52 는 케이스 전용 칸이라 이름을 케이스에 맞게 바꿔도 된다) |
| Mem2 | `{0:"unit",1:"x",2:"y",3:"gunid",4:"owner",5:"started",6:"phase",7:"frames",8:"ms",9:"wave",13:"ms2",20:"plotted",26:"penalty",30:"axiom",31:"boss_in"}` + 10~19 는 보스 전역으로 |
| G2R | `{0:"unit",1:"x",2:"y",3:"variant",4:"frames",5:"wave",6:"work6",50:"work50",51:"work51",52:"work52"}` — **쓰기 즉시 반영으로 바뀐다**(8절 3번) |
| UERE 건작 | `{0:"unit",1:"x",2:"y",3:"level",4:"frames",5:"wave",53:"gun_type"}` |
| Seed | 필드 이름을 그대로(`alias_base=1` 로 `GunF` 번호도 받음) |
| UERE Blaster (`alias_base=1`) | `{1:"sx",2:"sy",3:"dx",4:"dy",5:"mode",6:"angle",8:"nuke_i",9:"work9",15:"inited",16:"t16",17:"t17",18:"t18",19:"t19",20:"t20"}` |
| UERE Bone (`alias_base=1`) | `{1:"x",2:"y",3:"frames"}` |

### 6.10 epScript 사용 모양

`eps_pool_probe_out.txt` 에서 번역을 확인했다(빌드는 안 함).

```js
import eudext.pool as pool;

const guns = pool.Pool("Gun", "unit! x! y! owner timer phase done gunid", capacity=36);   // ! = readonly
const g = guns.cur;                         // 레지스터 보기는 const 로 (var 에 담지 않는다)

function gunSend(u, x, y, owner) {
    const h = guns.alloc(unit=u, x=x, y=y, owner=owner);     // 키워드 인자 그대로 번역됨
    if (h == 0) { return; }
}

function afterTriggerExec() {
    foreach (_ : guns.each()) {             // → for _ in guns.each():
        if (g.timer == 0) { /* 시작 처리 */ }  // → _ATTC(g,'timer') == 0
        switch (g.unit) {                   // → EUDSwitch(g.unit)
            case 131: hatchery(); break;
            default: guns.free_current();
        }
        g.timer += 16;                      // → _ATTW(g,'timer').__iadd__(16) → g.iaddattr
        if (g.done >= 1) { guns.free_current(); continue; }
        if (guns.Line(5, Exactly, 0)) { guns.SetLine(5, SetTo, 1); }   // 별칭
    }
}
```

- `pool.Pool(...)` 은 대문자라 `f_` 가 안 붙는다. 모듈 함수(예: `pool.bag(16)`)는 `pool.f_bag` 으로 번역되므로 `f_이름` 으로 정의한다.
- 객체 메서드(`guns.alloc`, `guns.Line`)는 이름이 바뀌지 않는다.
- `g.line(5) = 1` 은 **문법 오류**(호출에 대입) → `guns.SetLine` 을 쓴다.
- `[ "unit", "x" ]` 목록 문자열은 epScript 에서 `EUDArray` 가 되므로 필드는 **공백 구분 문자열 하나**로 준다.
- 본문을 epScript `function` 으로 나눌 때 레지스터는 전역 const 로 보인다(인자로 넘길 필요 없음).

### 6.11 저장소 비교와 권장

| 방식 | 저장 | 필드 조건 | 필드 쓰기 | 레코드 방문 고정비 | 권장 |
|---|---|---|---|---|---|
| **사슬 + 레지스터 (제안)** | (F+3)×72B + 76B | 변수 조건(추가 0) | 레지스터 1 + 되쓰기 필드당 6(시제품)/2(목표) | F+5 (적재) + 꼬리 | **기본** |
| EUDStruct 포인터 + ObjPool | F×72B + 4B | 실행 7 (정적 5) | 실행 10 (`+=` 상수) | 목록 읽기 12~38 | 필드 연산이 방문당 5개 이하인 가벼운 레코드만. 풀 API 로는 두지 않음 |
| EUDArray 행 블록(4B) | F×4B | 읽기 36~38 + 비교 | `f_dwwrite_epd` | 적재하면 F×36 | 찬 필드(2단계 `hot=False`)만 |
| EUDStruct 정적 인스턴스 | F×72B | 3 (EUDIf 포함) | 1 | — | 풀이 아니라 "하나뿐인 보스 상태" 같은 곳 |
| `EUDStruct.alloc()` 전역 풀 | **+18.9MB 고정** | — | — | — | **금지** |

"72B 가 4B 보다 18배 크다" 는 사실은 그대로다. 그래도 **매 프레임 모든 필드를 읽는 레코드**에서는 4B 방식이 필드마다 실행 36 을 내므로(13필드 = 468) 72B 가 맞다(DESIGN 3.8 "원소마다 변수 트리거가 필요할 때만 EUDVArray" 에 해당). 저장을 줄이는 수단은 **필드 수 줄이기**(케이스 전용 칸을 전역으로)와 **용량 줄이기**(빈 칸 비용이 없으니 실측 최대치 + 여유)다.

### 6.12 내부 알고리즘 (구현 지침, 의사코드)

```
저장 S (cap × (F+3) 원소, 사슬):
  S[h][k]      = (dest = EPD(reg[k]),  value = 필드값, next = S[h][k+1])
  S[h][F+2]    = (dest = EPD(reg_alive), value = alive, next = T_ret)
  숨은 필드 _self = S[h][0] 의 주소(상수), _index = h(상수)  -- 위치는 구현 자유
live (cap 원소): live[i] = (dest = J.next, value = 레코드 주소, next = J)
free_stack: EUDArray(cap) (처음 0..cap-1 을 pop 순서대로), sp
count, n_live(목록 길이), dropped

each():
  T_ret.next ← 루프 복귀점            (호출 자리가 둘 이상일 때만)
  n ← n_live ; r_ptr ← live 시작 ; w_ptr ← live 시작
  while r_ptr < live + 72n:
      점프(r_ptr)  → live 원소가 J.next 에 레코드 주소 → J → 사슬 → T_ret   # 실행 F+5
      if reg_alive == 0:  push(reg_self) ; goto 다음
      yield g                                    # 본문 (EUDContinue → 꼬리)
      꼬리: if reg_alive == 0: push(reg_self) ; count 는 free 때 이미 줄임
            else: 되쓰기(더러운 필드) ;
                  if w_ptr != r_ptr: live[w_ptr].value ← reg_self
                  w_ptr += 72
      다음: r_ptr += 72
  끝 처리: n..n_live-1 (루프 중 새로 붙은 것)을 w_ptr 쪽으로 당기며 alive==0 인 것은 push
           (여기서는 레지스터를 덮어도 된다 — 방문 중인 레코드 없음)
  n_live ← (w_ptr - live) / 72

alloc(**init):
  if sp == 0: dropped += 1 ; on_full ; return 0
  h ← pop ; 모든 필드와 _alive=1 을 S[h] 에 씀 ; live[n_live] ← 주소(h) ; n_live += 1 ; count += 1
free(h):
  if alive(h) == 0: (debug) 경고 ; return
  S[h]._alive ← 0 ; count -= 1 ; if 루프 중이고 h == reg_self: reg_alive ← 0
```

참조 모델은 `refmodel.py` 의 `Pool` 이다(위와 같은 규칙, 번호 핸들). 구현 참고:
- 사슬 원소의 목적지는 **컴파일 때 정한 값**이므로 저장을 `EUDVArray` 로 드러내면 안 된다(일반 `get` 이 목적지를 덮어씀, EP81 `vararray.py:508-615`).
- `_EUDVArrayData` 의 원소 next 가 자기 자신을 가리키므로 `Forward` 로 만든 뒤 `<<` 한다(시제품은 `_init` 을 나중에 채웠다 — 구현에서는 `Forward` 권장).
- 되쓰기는 `EPD(reg_self) + 18k + 87` 에 쓴다(원소 값 칸 = 원소 주소 + 348, `vararray.py:602-615`). 필드마다 `f_dwwrite_epd` 를 부르면 실행 6, `VProc` 으로 주소 덧셈·값 대입을 묶으면 2 안팎(목표, 미측정).
- `live` 원소 목적지 = 점프 트리거 J 의 next 칸(`EPD(J)+1`). 시제품에서 동작 확인.

### 6.13 비용 목표 (구현 뒤 `docs/COSTS.md` 에 실측)

| 항목 | 목표 |
|---|---|
| 빈 풀 한 프레임 | 실행 ≤ 6 |
| 방문당 고정(분기·본문 제외) | 실행 ≤ F + 12 + 2W (시제품 수준 F + 17 + 6W 는 허용 상한). W = 그 루프에서 접근한 쓰기 가능 필드 수 |
| 압축 이동 1회 | 실행 ≤ 6 |
| `alloc` | 실행 ≤ 3F + 30, 호출 자리 ≤ 4 |
| `free` / `free_current` | 실행 ≤ 6 / 1 |
| `each` 루프 코드 | 호출 자리마다 ≤ 40 트리거 + 되쓰기 필드 수 비례 |
| 저장 | cap × ((F+3)×72 + 76) + (F+3)×72 |
| 유형 분기 | `EUDSwitch` 실행 ≤ log2(경우 수) + 3 |

### 6.14 `_compat` 요구

`_EUDVArrayData`(또는 `EUDCustomVarBuffer`)로 원소별 dest/next 를 가진 72B 배열 만들기, `EUDVariable.getValueAddr`(공개), 트리거 스코프(`PushTriggerScope`)·`SetNextPtr`·`VProc`(공개). 0.81.x 판 검사에 "`_EUDVArrayData.__init__` 이 (dest, value, nextptr) 세 쌍을 받는다" 를 넣는다.

---

## 7. 시험

### 7.1 참조 모델

`refmodel.py` `Pool(cap, fields)` — 핸들 = 번호, `None` = 없음. `tick(body)` 는 방문 순서를 돌려준다. 구현 시험은 핸들을 `index_of` 로 번호로 바꿔 비교한다.

### 7.2 시나리오 기대값 (`refmodel_out.txt`, 필드 `kind timer phase done`)

| # | 조작 | 기대 |
|---|---|---|
| T1 | cap4, alloc ×3, tick | 핸들 [0,1,2], 방문 [0,1,2], count 3, 스택 맨 위 3 |
| T2 | cap4, alloc ×3, 루프 밖 free(1) → tick → alloc → tick | free 직후 count 2·목록 [0,1,2] 그대로; tick1 방문 [0,2], 목록 [0,2], 스택 맨 위 1; alloc → 1; tick2 방문 [0,2,1] |
| T3 | 1 의 본문이 자기 free | tick1 방문 [0,1,2], 목록 [0,2], count 2, 스택 맨 위 1; tick2 방문 [0,2] |
| T4 | 0 의 본문이 2 free (아직 안 돈 것) | tick1 방문 [0,1], 목록 [0,1], 스택 맨 위 2 |
| T5 | 2 의 본문이 0 free (이미 돈 것) | tick1 방문 [0,1,2], 목록 [0,1,2](0 은 표식만), count 2, 스택 맨 위 3; tick2 방문 [1,2], 스택 맨 위 0 |
| T6 | cap5, 0 의 본문이 alloc | alloc → 3; tick1 방문 [0,1,2], 목록 [0,1,2,3], count 4; tick2 방문 [0,1,2,3] |
| T7 | cap5, 0 이 alloc(→3), 1 이 3 free | tick1 방문 [0,1,2], 목록 [0,1,2], count 3, 스택 맨 위 3 |
| T8 | cap4, alloc ×5 | [0,1,2,3,없음], dropped 1, count 4, (report 면 문구 1회) |
| T9 | cap2, alloc ×2, 루프 밖 free(0), alloc, tick, alloc | tick 전 alloc 없음(dropped 1), tick 뒤 alloc → 0, 목록 [1,0] |
| T10 | 본문 `timer += 16`, tick ×3 | timer 48, phase 0(안 쓴 필드는 그대로) |
| T11 | cap1, 본문이 timer=777·phase=3, free, tick, alloc(kind=132) | 핸들 0, 필드 {kind 132, timer 0, phase 0, done 0} |
| T12 | 본문이 timer=555 쓴 뒤 자기 free | 저장된 timer 0(되쓰기 생략), count 0, 목록 [] |
| T13 | alloc, free, free | 두 번째 free 무시(debug 경고 1), count 0 |
| T14 | cap6, alloc ×6, free(1), free(3), tick, alloc ×2, tick | 방문 [0,2,4,5]; alloc → [3,1]; 다음 방문 [0,2,4,5,3,1] |

추가 단위 시험(에뮬레이터):
- 필드 값 경계: 0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF 를 alloc 으로 넣고 적재 → 레지스터 값 동일.
- `-=` wrap / `isub_sat` / `SetLine(…, Subtract, …)` 포화: timer=3 에서 5 빼기 → 0xFFFFFFFE / 0 / 0.
- `SetLine(n, Add, v)` 뒤 같은 본문에서 `Line(n, AtLeast, v)` 가 **참**(ResV 의미. G2R 과 다름).
- `EUDContinue` 뒤에도 앞에서 쓴 필드가 저장됨.
- `dispatch`: {131, 132} 등록, kind 999 → on_unknown 이 문구 기록 + 반납, 131 본문은 131 에서만.
- `each(handle=True)` 의 h == `pool.cur.handle`, `index_of(h)` == `g.index`.
- 되쓰기 목록: 본문에서 `DoActions(g.phase.SetNumber(2))` 로만 쓴 필드도 저장됨 / `readonly` 필드에 보기로 대입하면 컴파일 오류 / 본문 밖에서 꺼낸 레지스터로 쓴 필드는 `g.touch` 없으면 저장 안 됨, `writeback="all"` 이면 저장됨.
- 두 풀을 중첩 순회(A 본문에서 B 순회) → 둘 다 정상. 같은 풀 중첩 → 컴파일 오류.
- 실행 수: 빈 풀 ≤ 6, 방문당 고정이 6.13 목표 안인지 기록.
- epScript 예제(6.10)가 `epsCompile` 과 euddraft 0.11 빌드를 통과.

### 7.3 인게임 확인 항목

1. 사슬 적재가 실제 SC:R 에서 동작(에뮬레이터 밖 첫 확인): 레코드 5개를 만들어 필드를 화면에 출력.
2. 건물 36개를 한 프레임에 부숴 넘침 문구·`dropped` 확인(Seed 2026-09-08 상황 재현).
3. 방문 중 해제·할당이 섞인 패턴(Mem2 식 보스가 새 건작 둘을 넣는 장면)에서 누락·중복 없음.
4. 한 건작 본문에서 G_CB(spawn) 호출 → 중심 좌표가 그 레코드의 x, y.
5. 128칸 풀 + 살아 있는 10개일 때 프레임 지연(원본 맵과 체감 비교).
6. 멀티(2인 이상) 디싱크 없음 — 풀 상태는 공유 값만 쓴다.

---

## 8. 함정

1. **`Suspend` = 반납.** 이름만 보고 일시 정지로 옮기면 안 된다(2.6).
2. **공유 본체 안의 "한 번" 구조는 풀 전체에서 한 번이다**: `CIfOnce`(ResV `:1725, 1731, 1737`), 보존 안 한 `TriggerX`/`Trigger2X`(ResV `:2722, 2745`, Mem2 `:1027-1028`), G_CB `PreserveFlag=1`(UERE `Gun_SpawnSet.lua:14-30`, Seed `G_CB_Lib.lua:2225-2229`). 하나뿐인 건작이면 우연히 맞고, 둘째 건물부터 조용히 빠진다.
3. **G2R 은 쓰기가 슬롯으로 바로 간다**: 같은 사이클에 쓴 값을 다시 읽으면 옛 값, 반납은 다음 사이클(그래서 모든 조건에 `Gun_Line(54,AtMost,0)`). eudext 로 옮기면 한 사이클 빨라진다.
4. **`Subtract` 는 포화**다. ResV `:1519-1520` 은 포화에 기대고, eudext `-=` 는 wrap 이다. 별칭 `SetLine(…, Subtract, …)` 은 포화로 둔다.
5. **번호 기준이 다르다**: `Gun_Line` 0부터, `TSLine` 1부터(`alias_base`).
6. **TStruct 첫 필드가 0 이면 레코드가 조용히 멈춘다**(3.2). Seed 가 UnitID 0 을 막은 이유. eudext 는 숨은 `_alive` 로 이 제약이 없다.
7. `TS_SendX` 값에 식을 넣으면 버그(TS `310`). eudext `alloc` 은 식을 받는다.
8. `TS_Suspend` 뒤 코드는 0 을 본다 — 맨 끝에 둘 것(Seed `GunSystem.lua:1169-1171`). eudext `free_current()` 는 레지스터를 지우지 않는다.
9. `SetCall`/`SetCall2` 본체는 선언 블록 안에 둬야 한다(Seed `main.lua:252`). eudext 는 해당 없음.
10. UERE 보내기 한도 `AtMost,126` → 128칸 중 127칸만 쓴다(`CallTriggers.lua:199-203`).
11. Mem2 `G_ForceSend` 는 `f_SaveCp()` 없이 `f_LoadCp()` 를 부른다(`GunData.lua:100-127`) — 영향 미확인. 게다가 이 함수는 공용 `CPosX/CPosY/GunID` 를 덮는데 건작 본체 안에서 불린다(`:3489`).
12. 보내기 넘침이면 그 건물의 건작은 **영영 안 나온다**(재시도 없음). Seed 는 실제로 겪었다(`GunSystem.lua:32-34, 1139-1146`).
13. 원본 슬롯 트리거는 빈 칸도 매 프레임 검사받고(TS `24-40`) 적층 포크에서 흩을 수 없다(주소 산술).
14. ResV `GunCaseErrT2` 는 안 쓰이고, 번호 ≥ 51 에도 "등록되지 않은 건작" 문구가 나온다(`:313, 2976`).
15. owner(막타 플레이어)의 한계 — 막타 기준, 트리거 제거 시 무의미, 0 이 P1 과 구분 안 됨(Seed `Buildings.lua:1002-1024`).
16. **`EUDStruct.alloc()` 전역 풀 = 페이로드 +18.9MB**, 필드 8개 초과 시 컴파일 오류(5.2).
17. EUDStruct 포인터 필드 연산은 실행 7~11, EUDArray 변수 색인 읽기는 38 — 본문이 큰 레코드에 쓰면 프레임 비용이 커진다.
18. 사슬 저장을 일반 `EUDVArray` 로 읽으면 목적지가 덮여 이후 적재가 엉뚱한 곳에 쓴다(6.12).
19. epScript: 필드 목록을 `[...]` 로 주면 EUDArray 가 된다 / `g.line(n) = v` 는 문법 오류 / 액션을 돌려주는 호출은 문장으로 쓰면 버려진다 / 보기 객체를 `var` 에 담지 말 것(`const` 또는 foreach 변수).
20. 루프 밖 `free` 는 다음 `each` 까지 칸을 돌려주지 않는다(T9). `each` 를 부르지 않는 프레임이 길면 풀이 마른다.
21. 새 레코드는 다음 tick 부터 돈다 — 원본(첫 맞춤, 뒤 번호면 같은 프레임)과 한 프레임 차이가 날 수 있다. 첫 사이클 조건(`timer == 0`)은 그대로 동작한다.
22. `pool.get(h, …)` 으로 **현재 레코드가 아닌** 것을 읽을 때 사슬 적재를 쓰면 레지스터가 덮인다 → 느린 경로(`f_dwread_epd`)만 쓴다.
23. 본문에서 같은 풀을 순회하는 함수를 부르면 재진입이다(EUDFunc 재귀 금지, DESIGN 3.3).
24. 로컬 값(키 입력 등)으로 `alloc`/필드 쓰기를 하면 디싱크(DESIGN 3.7).
25. 되쓰기 목록은 "보기로 접근한 필드" 로 정한다. 레지스터를 본문 밖에서 꺼내 둔 변수로 쓰면 목록에서 빠져 값이 사라진다(`g.touch` 또는 `writeback="all"`). `readonly` 필드를 다른 경로로 바꾸면 다음 방문에 옛 값으로 되돌아간다.

---

## 9. DESIGN.md 수정 제안

1. **4.11 API** 를 6.2~6.9 로 바꾼다: `Pool.Record(EUDStruct)` → `Pool(name, fields, capacity, aliases, alias_base, on_full, on_unknown, writeback, debug)` + `Field(name, init, signed, readonly)` + 레지스터 보기 `pool.cur`/`each()` 제너레이터, `free_current()`, `dispatch`/`case`, 별칭 `Line/SetLine/SetLineAct/LineRange/line`, `count/dropped/index_of/get/set`.
2. **4.11 의미**: "저장은 EUDStruct + ObjPool, 살아 있는 목록은 포인터 배열 + 맞바꿔 지우기(NBag)" → "사슬 저장(원소별 목적지를 미리 정한 72B, EUDQueue 기법) + 레지스터 적재 + 표식·압축(순서 유지)". 초안 예의 `suspend` 필드("일시 정지")를 지우고 "원본 Suspend = 반납" 을 적는다.
3. **4.11 비용 목표** 를 6.13 표로. "레코드당 필드 수 × 4B" 문구는 "사슬 72B, 찬 필드만 4B(2단계)" 로.
4. **4.11 위험** 의 `EUDMethod` 항목은 "0.81 에서 해결(정적 EUDStruct 도 본문 공유, `eudfmethod.py:54`, S2 측정)" 으로 닫고, 대신 "사슬 저장은 비공개 `_EUDVArrayData` 의존 — `_compat` 판 검사" 를 넣는다.
5. **3.9 금지 목록**에 "`EUDStruct.alloc()`/epScript `P.alloc()`(전역 풀 32,768×8×72B = 18.9MB)" 추가.
6. **3.8 저장소 고르기**에 "매 프레임 모든 필드를 읽는 레코드 = 사슬 저장 + 레지스터(pool)" 와 측정값(EUDArray 변수 색인 읽기 실행 38, EUDVArray 12, `f_dwread_epd` 36) 추가.
7. **3.5** 에 "CtrigAsm 별칭 `SetLine(…, Subtract, …)` 도 포화" 한 줄.
8. **4.1 `_compat` 접근자 목록**에 `custom_varray(triples)`(원소별 dest/value/next) 추가.
9. **4.14 spawn**: "내부는 pool(작업 레코드)" 뒤에 "공유 본체 안 PreserveFlag=1 함정(S2 8절 2번)은 spawn API 에서 한 번 옵션을 없애는 것으로 막는다" 추가.
10. **6.1 WP11**: 재사용 "flow.py NBag 구조" → "EP81 `eudqueue.py` 사슬 순회 기법, S2 `refmodel.py`"; 추가 완료 조건 "S2 7.2 T1~T14 통과, 6.13 비용 목표 기록, 사슬 적재 인게임 1회 확인(7.3-1)". 크기 중 → 중~상.
11. **0.2 표** "건물 스택·오브젝트 풀" 사용량 옆에 "(+NBag DPS 8)" 을 적고, 필요하면 `pool.Bag`(레코드 없는 핸들 가방, DPS `CUnit.lua:21-94` 대체)을 2단계 항목으로.
12. **R1 4절 "Gun_Line … 추측"** 은 S2 로 확인됐다고 8절 표에 한 줄(건물 스택과 TStruct 는 같은 구조).

---

## 10. 미확인

1. CtrigAsm `CDoActions` 가 T 액션 55개(되쓰기)를 실행 몇 번으로 처리하는지 — 원본 방문당 비용의 큰 몫인데 세지 않았다(5.1).
2. 적층 포크에서 건물 스택·TStruct 슬롯이 실제로 KEEP(step) 인지 — Seed `release/0.4/StackLayout.txt` 에 32칸 step 구간은 보이나 어느 것인지 대조하지 않았다.
3. 사슬 적재·되쓰기의 **실제 SC:R 동작**(에뮬레이터만 확인, 7.3-1). euddraft 0.11 빌드도 안 했다.
4. 되쓰기 필드당 실행 2 목표(VProc 묶음)가 되는지 — 미측정.
5. 페이로드 원소당 기울기가 이론(4B/72B)과 다른 까닭(할당기 배치 잡음으로 추측).
6. G2R 줄 3(`CVoid_ID2`, CUnit dword 9 의 +0x26 바이트)의 정확한 뜻 — 배치 때 심는 번호로 추측.
7. UE(구판)·G2(구판)의 건물 스택이 UERE·G2R 과 줄 단위로 같은지 — 사용 수만 비교했다.
8. ResV 128칸·UERE 200칸의 실제 동시 최대 사용량 — 용량을 줄여도 되는지 판단 근거가 없다.
9. Mem2 `G_ForceSend` 의 CP 불균형(8절 11번)이 실제 문제를 일으키는지.
10. UERE Blaster 9번 필드의 뜻(`TS_VarArr[9]` 가 거리 누적으로 보임, 추측).
11. epScript `foreach` 안 `continue` 가 제너레이터 블록(`EUDCreateBlock` contpoint)과 맞물려 빌드되는지 — 번역만 확인.
12. `EUDSwitch` 의 경우 수가 수백일 때 정적 크기(26경우만 쟀다).
13. R1 수치(ResV 774, Mem2 735)와 이번 셈(777, 768)의 차이는 `TGun_`·`Gun_LineRange` 포함 여부로 보이나 R1 스크립트와 줄 단위로 대조하지 않았다.
