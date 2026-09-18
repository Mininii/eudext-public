# S6 — 채팅 효과 블록과 관전자 채팅 명세 (`eudext.chat`, `eudext.textfx`, `eudext.misc.ObserverChat`)

작성 2026-09-17. 조사·명세만 했고 코드는 만들지 않았다. 근거는 `파일:줄`, 확인 못 한 것은 "(추측)".
블록 추출·맵 간 diff 는 스크래치패드 `spec_s3\s6a\`(채팅 효과), `spec_s3\s6b\`(관전자 채팅)에 있다.

## 약어

| 약어 | 파일 |
|---|---|
| CA | `ScmDraft 2\MapSource\Library\CtrigAsm v5.5.lua` |
| GB | `ScmDraft 2\MapSource\Library\Ctrig Assembler v5.4 Guide Book.txt` (26장 6266~7593) |
| OBC | `ScmDraft 2\MapSource\Library\ObserverChat.lua` (1,066줄) |
| OBA | `ScmDraft 2\MapSource\Library\ObserverChatAlways.lua` (52줄) |
| L322 | `ScmDraft 2\MapSource\Library\LibraryFor322.lua` |
| EP81 | eudplib 0.81.0 소스 `…\scratchpad\upstream\eudplib\src\eudplib\` (0.81 에서 `stringf/` → `string/`) |
| R4a / R4b | `docs\research\R4a_bullet_text.md` / `R4b_input_shape_misc.md` |
| S3 / S7 | 같은 폴더의 `S3_display.md` / `S7_strdesign.md` |

맵 약칭: ResV(`MSF_Respect_V`), Mem2(`MapSource\MSF_Memory_2`), UERE(`MapSource\MSF_UE_RE`), UE(`MapSource\MSF_UE`, 구판), NTM1(`MapSource\NewTestMap1`, 시험 맵),
Stel(`Stella_II`), Brz(`MapSource\MSF_Breeze`), Seed(`theSeed`), MEME(`MSF_MEME_EUD`), GXR(`MapSource\MSF_GaLaXy.R`, 구판).

---

## 0. 한눈에

**채팅 효과 블록(`HTextEff` + `CDPrint`)**
- 하는 일: 채팅 줄 11칸을 매 사이클 훑어 **원문이 `"\x0D\x0D!H"` 로 시작하는 줄**을 찾으면 한 번 글자 셀로 바꿔 보관하고, 그 줄을 "보이지 않는 표식(U+200B) + 빈칸"으로 덮은 뒤 **사이클마다 한 글자씩 드러낸다**(타자기 효과). `!H` 두 글자는 지운다.
- 사본 5곳: ResV·Mem2(줄마다 같음), UE(변형), UERE(UE + 보스전 속도·소리), NTM1(UE + 실험 분기). 원형은 GB 예제 26-24(GB:17048~17065).
- 표식 문자열은 맵 문구 표에 수백 번 박혀 있다(ResV 65 · Mem2 117 · UE 66 · UERE 68 · NTM1 12).
- **셀 배치 영향**: 블록의 상수(3바이트 표식 셀, 빈칸 셀)는 CtrigAsm·eudplib 배치에서 **같은 값**이다. 1바이트 글자를 비교하는 곳은 UERE 의 "공백이면 소리 생략" 하나뿐(상수 교체 필요).
  다만 CtrigAsm `CD__ScanChat` 의 **묶음 규칙**(색 코드를 다음 글자 셀에 합침, 0x0D 는 4개 단위로만 셀, 2바이트 UTF-8 미지원)이 eudplib 런타임 변환(`_cpchar_addstr`)과 달라, 그대로 바꾸면 드러나는 순서와 `!H` 위치가 달라진다 → eudext 는 CtrigAsm 묶음 규칙 + eudplib 배치로 스캐너를 새로 정의한다(4.1).
- 용량: 원본 보관소 `HStr2` 594셀 = **트리거 594개(≈1.37MiB)**. eudext 는 `Db` 2,376B 로 대체.

**관전자 채팅(`ObserverChatToOb/ToAll/ToNone`)**
- 하는 일: 관전자(로컬 번호 128~131) PC 에서 END/HOME/INSERT 를 누르면 채팅 대상 모드를 관전자(5)/전체(2)/대상없음(3)으로 정하고 안내 문구·소리를 낸 뒤, 채팅창이 열려 있는 매 프레임 `0x68C144` 를 그 값으로 덮는다. **모두 로컬.**
- 4맵(Stel·ResV·Mem2·Brz)의 블록은 들여쓰기를 빼면 **바이트까지 같다**(다른 것은 `StrDesign` 판뿐). Seed 는 키 없는 상시판(`ObserverChatToAllAlways`). ResV 는 상시 ToAll 트리거가 뒤에 따로 있어 키 모드를 덮는다.
- 원본 버그: 딜레이 감소 트리거가 **Ob1(128) 조건으로 한 번만** 만들어져 Ob2~Ob4 는 첫 입력 뒤 키가 영구히 막힌다(OBC:474~487, 2.7-B1).
- eudext: `misc.ObserverChat(keys=…, delay=…, notice=…)` — 로컬 변수에 상태, 딜레이 버그 수정, 키는 `eudext.local` 에 맡김. ToPlayer·음소거(0x57F1D8)·ObserverDrop 은 넣지 않는다(설계만/제외).

---

## 1. 채팅 효과 블록

### 1.1 위치와 사본

`SD` 전체(`DPS_eud\eud\`, `DPS_Enhance` 제외)에서 `CD__ScanChat|CDPrint(|HTextEff` 를 찾은 결과 맵 소스의 사본은 5개다.
나머지 적중은 Library 본문·설명서·연구 문서, 그리고 theSeed 주석(`theSeed\MapLogic\ChatSeedInput.lua:37~38`, `theSeed\PROGRESS.md:194`).

| 맵 | 블록 (파일:줄) | 감싸는 조건 | 준비 코드 | 관계 |
|---|---|---|---|---|
| ResV | `MSF_Respect_V\GunData.lua:2879~2936` | `CIf_GCase(189,1)`(GunData.lua:2079, 정의 316~317: 건작 189번 = 화홀 보스 실행 중) ~ `CIfEnd` 2938 | `Variables.lua:214~216,218`, `OnInit.lua:597` | 기준 |
| Mem2 | `MapSource\MSF_Memory_2\Operator.lua:464~521` | `Operator_Trig()` 최상위, `main.lua:163` 에서 호출(`CIf(AllPlayers,ElapsedTime(AtLeast,3))` 154 안) → 3초 뒤 상시 | `Var_init.lua:227~230,242`, `OnPluginStart.lua:548` | ResV 와 58줄 모두 같음(공백 제외) |
| UE | `MapSource\MSF_UE\Destr0yer.lua:598~651` (cp949) | `CIfX`(Destr0yer.lua:61: 보스 유닛 186 존재 또는 BGM 1~271, `Win==0`) 안 | `Var_Include.lua:394~397,399`, `EUDinit.lua:713` | ResV 의 변형 |
| UERE | `MapSource\MSF_UE_RE\CallTriggers.lua:942~1028` (본체 949~1026) | 서브루틴 `Call_CDPrint`. 호출처 `Destr0yer.lua:574`(보스 CIfX 안), `Sans.lua:506`(`CIf(SBossStart≥1)` 안) | `Var_Include.lua:401~404,406,408,412`, `EUDinit.lua:660` | UE + 속도·소리 |
| NTM1 | `MapSource\NewTestMap1\Interface.lua:149~237` (cp949) | `Interface()` 최상위, `main.lua:107` | `Var_init.lua:131~135,64`, `OnPluginStart.lua:356~361` | UE + 실험 분기 |

준비 코드(5맵 같음, ResV 기준):
- `HStr2 = SaveiStrArrX(FP,MakeiStrVoid(54*11))` — 글자 셀 594칸(줄 11 × 54)
- `HStr4 = SaveiStrArrX(FP,MakeiStrVoid(54))` — 빈칸 54칸
- `HVA3 = CVArray(FP,4*5)` + `CbyteConvert(FP,VArr(HVA3,0),GetStrArr(0,"\x0D\x0D!H"))` — 표식 4바이트를 dword 정렬 4가지로 저장(CA:32113~32175, 홀수 줄 비교용)
- `HLine, ChatSize, ChatOff, HCheck = CreateVars(4,FP)`

### 1.2 공통 동작 (ResV 줄 기준, Mem2 = ResV − 2415)

본문을 직접 읽어 확인했다(`MSF_Respect_V\GunData.lua:2879~2936`).

| 단계 | 줄 | 동작 |
|---|---|---|
| S1 상수 | 2879~2881 | `SpCodeBase=0x8080E200`(마스크 0xF0FFFF00 → U+2000~200F), `SpCode0=0x8880E200`(U+2008), `SpCode3=0x8B80E200`(U+200B, "`\x0D\x0D!H` 줄" 표식) |
| S2 CDPrint 한 사이클 | 2936 → CA:52633~53039 | (a) 11줄의 스테이징 셀(SVA54) 초기화: 셀 0..52 = 값 0x0D0D0D0D·**마스크 0**, 셀 53 = 값 0·마스크 0xFFFFFFFF(NUL), 홀수 줄 머리 2바이트 마스크 0 (CA:52810~52898). (b) `HTextEff` 1회(CA:52900~52913). (c) 표시 대상 PC 에서만 SVA54 를 실행해 `0x640B60+218k`(짝수)/`0x640B62+218k`(홀수)에 쓴다(CA:52917~53030, 1214~1256) |
| S3 1회 | 2883~2884 | `CA__SetNext(HStr2,8,…)`, `CA__SetNext(HStr4,8,…)` — 보관 셀의 "복사 뒤 CP 이동량"을 8 epd(스테이징 셀 간격)로 |
| S4 줄 루프 | 2891, 2934 | `HLine = 0..10`, 매 반복 `HCheck = 0` |
| S5 줄 주소 | 2892 | `f_ChatOffset(FP,HLine,0,ChatOff)` → `ChatOff = 0x640B60 + 218·HLine`(원시 주소, CA:90463~90485) |
| S6 이전 상태 | 2893 | `HCheck ← EffCV2[HLine]` |
| S7 분류 | 2894~2899 | 원시 앞 4바이트 == `0D 0D 21 48` 이면 `HCheck=3`. 아니고 셀0 `& 0xFFFFFF00 ≠ 0x8B80E200` 이면 `HCheck=0`. 둘 다 아니면 이전 값 유지(이미 변환한 줄) |
| S8a 첫 변환 | 2903~2919 | 조건: `HCheck∈[3,4]` 이고 셀0 이 U+200x 표식이 아님. `EffCV[HLine]=0`; 보관 셀 줄 0..52 를 빈칸으로; `CD__ScanChat(SVA1(HStr2,HLine·54·604),ChatOff,52,ChatSize,0,1)`(최대 52셀, NUL 셀 없음, 홀수 줄 머리 건너뜀); `HCheck==3` 이면 보관 셀 0,1 을 빈칸으로(`!H` 지움) + 스테이징 셀0 = **0x8B80E20D**; `CD__InputMask(HLine,0xFFFFFFFF,0,52)` → 이 사이클에 줄이 "표식 + 빈칸 52"로 바뀌어 원문이 가려진다 |
| S8b 드러내기 | 2920~2928 | 조건: 줄이 떠 있음(첫 바이트≠0) 이고 셀0 이 U+200B. `k = EffCV[HLine]`; 스테이징 셀 1..52 ← 빈칸; 셀 1..k ← 보관 셀 0..k−1; `k ≤ 51` 이면 `EffCV = k+1`(최대 52) |
| S9 상태 저장 | 2933 | `EffCV2[HLine] ← HCheck` |
| S10 출력 | (S2-c) | 스테이징 → 채팅 버퍼(로컬) |

- `HCheck==4`(다른 플레이어 이름 줄) 분기는 주석 처리(2895~2897), `HCheck≠3` 경로(U+2008 표식)는 이 4맵에서 도달하지 않는다.
- **부수효과**: 셀 53(NUL)은 **11줄 모두에 매 사이클** 마스크 0xFFFFFFFF 로 쓴다(CA:52888~52891 — 초기화 트리거가 `SetDeaths(CP,SetTo,0,0)` + 마스크 칸 0xFFFFFFFF 를 넣음, 직접 확인). 표시 대상 PC 에서 짝수 줄은 바이트 212, 홀수 줄은 214 뒤가 잘린다.
  R4a E.2(512줄)의 "초기화 마스크 0 으로 기존 글자를 지우지 않고"는 이 점이 빠진 설명이다.

### 1.3 화면에서 보이는 것

`DisplayText("\x0D\x0D!H\x13…")` 로 찍힌 줄은 찍힌 사이클에 곧바로 빈 줄(보이지 않는 표식)로 바뀌고, 다음 사이클부터 한 셀씩 나타난다.
셀 하나 = "보이는 글자 하나"(색 코드는 글자 셀에 합쳐짐). 처음 두 셀은 지운 `!H` 자리(빈칸)라 두 사이클은 아무것도 안 늘어난다(코드 해석).
줄이 사라지면(첫 바이트 0) 드러내기를 멈추고, 다음에 같은 slot 에 새 줄이 오면 S7 에서 상태를 새로 정한다.
여러 줄 문자열은 줄마다 표식을 다시 붙인다(예: UERE `Destr0yer.lua:11` `…♪\n\x0D\x0D!H\x13…`).

표식 문자열 사용 예: ResV `GunData.lua:2104~` 가사 표 → `DisplayTextX(k[1],4)`(2211~2213), UERE `Destr0yer.lua:7~14`, UERE `Sans.lua:12,15`(보스 대사), Mem2 `Operator.lua:459`, `System.lua:28~44`, Mem2 `"\x0D\x0D!H"..StrDesignX2(…)` 9곳(S7 3-7), 관전자 채팅 안내 문구(2.5).

### 1.4 맵별 차이

| 항목 | ResV | Mem2 | UE | UERE | NTM1 |
|---|---|---|---|---|---|
| 표시 대상 | `{Force1,Force2,Force5}` = P1~P8 + 관전자 (`main.lua:39`) | 같음 (`main.lua:108`) | `{Force1,Force5}` = P1~P7 + 관전자 (`main.lua:80`) | 같음 (`main.lua:75`) | `{Force1,Force2,Force5}` |
| `EffCV2` 인덱스 | `VArrX(EffCV2,VArrI,VArrI4)`(최적화) | 같음 | `VArr(EffCV2,HLine)` | 같음 | 같음 |
| 공개 속도 | 사이클당 1셀 | 같음 | 같음 | `SBossStart≥1` 이면 `TC==0` 인 사이클에만 +1(`TC` 는 매 호출 −1, CDPrint 뒤 `TC==0` → `TalkTimer`, 948·1012~1015·1027), 그 밖에는 사이클당 1 | 사이클당 1 |
| 소리 | 없음 | 없음 | 없음 | 드러낸 셀이 빈칸(`&0xFFFFFF00==0x0D0D0D00`)도 공백(`&0xFF000000==0x20000000`)도 아니면 `PlayWAVX("staredit\\wav\\STalk.ogg")` → HumanPlayers (999~1006) | 없음 |
| 추가 분기 | – | – | – | – | `HCheck 5/6`(203~231): 플레이어 이름 줄(`TTbytecmp(ChatOff,VA1,PLength)`) 감지, 셀 11부터 `"[BLACKTUBE]"`, 색 순환(`EfStr1`) — 실험 코드(추측) |
| 호출 경로 | 건작 189 안 | 상시 | 보스 CIfX 안 | 두 곳에서 `CallTrigger` | 상시 |

### 1.5 쓰는 CtrigAsm 함수

| 함수 | CA | GB | 인자(블록에서 쓴 값) | 동작 | 로컬/CP |
|---|---|---|---|---|---|
| `CDPrint` | 52633~53039 | 7070~7151 | `(Line=0, Size=11, Init={"\x0D",0,0}, DisplayPlayer, Preset={1,0,0,0,1,1,0,0}, CDfunc="HTextEff", PlayerID=FP)` | 스테이징 셀 초기화 → CDfunc → 대상 PC 에서 채팅 버퍼로. **Line 숫자 = slot**(`{n}`/V 는 화면 위치 → `CD__GetLine`). Init = {셀 값, 셀 마스크, 홀수 줄 머리 마스크}. Preset 8칸: [1]·[6] 무시(Line·Size 가 정함), [2] 대기 0 → 이번 사이클 실행, [3] 대기 증가 0 → 매 사이클, [4] 루프 카운터 시작, [5] 루프 한도 1 → CDfunc 사이클당 1회, [7]·[8] 출력 딜레이 0 → 매 사이클 출력 | 초기화·CDfunc 는 모든 PC, 버퍼 쓰기는 `LocalPlayerID(p)`/`TMemory(0x512684)` 가 참인 PC(CA:52950~53028) |
| `CD__ScanChat` | 54918~55051 (공용 본문 87611~88944) | 7279~7294 | `(SVA1, Offset=ChatOff, Size=52, Output=ChatSize, Null=0, SkipInit=1)` | 원시 UTF-8 줄 → iutf8 셀. 규칙은 1.7 | 공유 트리거(읽는 원본은 로컬). 끝에 RecoverCp |
| `CD__InputVAX` | 53580~53999 | 7221~7234 | `(Index=_GIndex2(L,1), SVA1, Size, Mask, DestMask, Start=8, End=604·11−1)` | 보관 셀 Size 개를 스테이징 셀로 복사하고 셀 마스크 칸(−5 epd)에 DestMask. Start~End 밖은 버림(줄의 셀0 보호) | CP 쓴 뒤 복구 |
| `CD__InputMask` | 54001~54219 | 7235~7242 | `(Line, Mask=0xFFFFFFFF, Start=0, End=52)` | 줄의 셀 Start..End 마스크 칸에 Mask(=그 셀을 이번에 쓰게 함) | CP 씀 |
| `CA__SetValue` | 47935~48043 | 6616~6627 | `(HStr2, MakeiStrLetter("\x0D",53 또는 2), 0xFFFFFFFF, CurLiV, 1, 1)` | 보관 셀에 컴파일 시점 문자열(여기선 빈칸) 굽기 | RecoverCp |
| `CA__SetMemoryX` | 56239~56340 | 6663~6673 | `(_GIndex2(L,0), 0x8B80E20D, 0xFFFFFFFF, 1)` | 스테이징 셀 **값 칸**에 쓰기(마스크 칸은 안 바꿈 → 뒤의 `CD__InputMask` 가 켬) | — |
| `CA__SetNext` | 48425~48560 | 6582~6592 | `(HStr2, 8, SetTo, 0, 593, 0)` | 셀마다 복사 뒤 CP 이동량(0x17C) 설정. 비보존(1회) | — |
| `CA__Read` (UERE) | 48851~48860 | 6643~6648 | `(_GIndex2(L, k))` | 스테이징 셀 값 읽기 | — |
| `CA__InputSVA1` (NTM1) | 47112 | 6530~6541 | 마스크 0xFF | 색 바이트만 복사 | — |
| `TTDisplay` | 49745~49785 (본문 90258~90279) | 6998~7004 | `(L, "On")` | 줄 첫 바이트 ≠ 0. 홀수 줄은 −2 주소 + 마스크 0xFF0000 | 로컬 값 조건 |
| `TTDisplayX` | 49787~ (본문 90281~90326) | 7012~7021 | `(L, 0, Type, Value, Mask)` | 줄의 셀 `Index` & Mask == Value (`"!="`/`NotSame` 은 부정) | 로컬 값 조건 |
| `TTbytecmp` | 17788~17807 → 32865~ | 6232~6235 | `(ChatOff, VArr(HVA3,0), 4)` | 원시 바이트 비교(배치 무관) | 로컬 값 조건 |
| `f_ChatOffset` / `_Chat` | 49579~49713 / 40501 | 7046~7058 | `(FP, L, 0, Out)` | `0x640B60 + Offset + 218·L` | — |
| `_GIndex2` | 40553~40589 | 7146, 7181~7185 | `(L, i)` | `L·604 + i·8` (스테이징 셀 번호) | — |
| `SVA1` / `SaveiStrArrX` / `MakeiStrVoid` | 46456 / 46147 / 46352 | 6406 / 6957 / 6325 | — | **글자 하나 = 트리거 하나**(CA:1581~1606, GB:6397). 번호는 604 배수 | — |
| `str_to_iutf8` | 45778~45863 | — | — | 컴파일 시점 셀 배치(1.7 표) | — |
| `CD__GetLine` | 53041~53044 | 7164~7167 | **안 씀**(Line 이 숫자) | slot = (row + [0x640B58]) % 11 | — |

트리거 수(수동 어림, 추측): CDPrint 약 40 + 공용 SVA54 21(≈50KB), 보관 셀 HStr2 594·HStr4 54 트리거(≈1.37MiB + 127KB), CD__ScanChat 호출당 약 6 + 공용 본문 150 이상.

### 1.6 로컬·공유와 CP

- **읽는 것은 로컬 데이터**(채팅 버퍼 0x640B60~, 0x640B58)이고, 그 결과를 **공유 트리거 메모리**(HStr2, EffCV, EffCV2, HCheck, ChatSize)에 쓴다. 이 값들을 게임 로직이 읽지 않으므로 디싱크는 없다(원본이 돌아가는 근거, 일반 원리 — 추측).
- UERE 의 소리(`PlayWAVX`)는 로컬 값(드러낸 셀) 조건으로 `RotatePlayer(…, HumanPlayers)` 를 부른다 — PlayWAV 는 표시 전용이라 안전(추측).
- CP: 각 함수가 RecoverCp 로 되돌린다(CA:55050 등).

### 1.7 셀 배치 영향 (과제 질문에 대한 답)

**두 배치** (근거: CA:45814~45843 `str_to_iutf8`, CA:88572~88710 ScanChat 경로, EP81 `string/texteffect.py:28~46` `_cpchar_addstr`, 76 `f_cpchar_adddw`, 98~105 `f_cpchar_print`, `memio/cpbyterw.py:50~72`)

| 글자 | CtrigAsm (iutf8, ScanChat) | eudplib (cpchar) |
|---|---|---|
| 1바이트 `c` | `[C][0D][0D][c]` | `[C][c][0D][0D]` |
| 2바이트 `b0 b1` | `[C][0D][b0][b1]` (단 **ScanChat 은 2바이트를 3바이트로 잘못 읽음**, 88661) | `[C][b0][b1][0D]` |
| 3바이트 `b0 b1 b2` | `[C][b0][b1][b2]` | 같음 |
| 색 코드 | 다음 글자 셀의 C 에 합침(연속이면 마지막 것) | 컴파일 시점 `f_cpchar_print` 는 합침, **런타임 `_cpchar_addstr` 는 색 코드도 1바이트 셀로 따로 씀**(C = `color_v`) |
| 0x0D | ScanChat: 4개 연속이면 빈칸 셀 `0D0D0D0D`, 모자라면 건너뜀(87977~88201) | 런타임: 1바이트 셀 |
| 0x0A | ScanChat: 셀(바로 뒤가 NUL 이거나 마지막이면 무시, 87914) | 1바이트 셀 |

(과제 설명의 "1·2바이트 글자 앞을 0x0D 로"는 1바이트에만 정확하다. 2바이트는 `[C][D][b0][b1]` 대 `[C][b0][b1][D]` 이다.)

**블록이 쓰는 상수와 판정**

| 상수 | 위치(ResV) | 뜻 | eudplib 배치에서 |
|---|---|---|---|
| `0x8080E200` / 마스크 `0xF0FFFF00` | 2904 | 바이트1~3 = U+2000~200F | **그대로**(3바이트 같음, 바이트0 은 마스크 밖) |
| `0x8B80E200` / `0xFFFFFF00`, 쓰는 값 `0x8B80E20D` | 2898, 2911, 2920 | U+200B + 색칸 0x0D | **그대로** |
| `0x8880E20D`(U+2008), NTM1 `0x8A80E20D`(U+200A) | 2913, NTM1:211 | 다른 표식 | **그대로** |
| `0x0D0D0D0D`(Init, 빈칸, HStr4) | 2936, 2907, 2924 | 빈칸 셀 | **그대로** |
| 원시 `"\x0D\x0D!H"` | 2894 | 원문 비교 | 배치 무관. 홀수 slot 은 dword 경계가 2바이트 어긋나므로 **바이트 비교**(`f_memcmp`) |
| UERE 빈칸 판정 `0x0D0D0D00`/`0xFFFFFF00` | UERE `CallTriggers.lua:1001` | 바이트1~3 = 0D | **그대로**(eudplib 빈칸도 `[C][0D][0D][0D]`) |
| **UERE 공백 판정 `0x20000000`/`0xFF000000`** | 같은 줄 | 바이트3 = 0x20 | **`0x00002000`/`0x0000FF00` 로 바꿈** |
| NTM1 `CA__InputSVA1` 마스크 `0xFF` | NTM1:225 | 색 바이트 | 그대로 |

판정: **ResV·Mem2·UE 블록은 1·2바이트 글자 바이트를 비교·치환하지 않는다** — 원시 바이트 비교, 3바이트 표식 셀, 빈칸 채우기, 셀 단위 복사·마스크뿐이다. 상수는 UERE 공백 판정 하나만 바뀐다.

**그러나 스캐너를 바꾸면 결과가 달라진다.** `CD__ScanChat` 대신 eudplib `f_cpchar_addstr` 를 그대로 쓰면:
1. 색 코드가 따로 셀이 되어 드러나는 단계 수가 늘고, 색 코드 셀이 드러나는 사이클엔 아무것도 안 보인다.
2. 원문 앞 `\x0D\x0D` 두 바이트도 셀이 되어 `!H` 가 셀 2·3 으로 밀린다 → "셀 0·1 지우기" 위치가 틀린다.
3. 2바이트 UTF-8 은 오히려 올바르게 처리된다(원본은 깨짐).
4. `_cpchar_addstr` 는 NUL 에서만 멈추므로 52셀 상한을 따로 둬야 한다.
→ eudext 는 **CtrigAsm 묶음 규칙 + eudplib 배치 + 2바이트 수정**으로 스캐너를 정의한다(4.1). 화면에는 0x0D 가 보이지 않으므로 배치가 달라도 보이는 결과는 같다.

### 1.8 사용 빈도 (주석 제외)

| 항목 | ResV | Mem2 | UE | UERE | NTM1 |
|---|---:|---:|---:|---:|---:|
| 블록 사본 | 1 | 1 | 1 | 1 | 1 |
| `CDPrint(` | 1 | 1 | 1 | 1 | 1 |
| `CD__ScanChat(` | 1 | 1 | 1 | 1 | 2 |
| `CD__InputVAX` / `CD__InputMask` | 3/1 | 3/1 | 3/1 | 3/1 | 6/2 |
| `CA__SetValue` / `SetMemoryX` / `SetNext` | 2/2/2 | 2/2/2 | 2/2/2 | 2/2/2 | 4/4/2 |
| `TTDisplayX` / `TTDisplay` / `TTbytecmp` / `f_ChatOffset` | 3/1/1/1 | 3/1/1/1 | 3/1/1/1 | 3/1/1/1 | 6/2/2/1 |
| 블록 밖 `"\x0D\x0D!H"` 출현 | 65 | 117 | 66 | 68 | 12 |

(S3 SCAN 의 `CDPrint` 수: 9맵 ResV 1·Mem2 1·UERE 1, 그 밖 UE 1·NTM1 1.)

---

## 2. 관전자 채팅

### 2.1 원본 정의와 판

- **정본**: OBC. 맵은 Library 를 `dir /b` 순서로 모두 불러오므로(`Stella_II\main.lua:23~28` 등) `CtrigAsm v5.5.lua` 뒤에 로드되는 OBC 가 CA 의 같은 이름 함수 7개를 덮는다. `ObserverChatCheck=0`(OBC:320)도 다시 실행된다.
- **CA 사본**: CA:100636~101217. 도우미 이름(`LocalPlayerID2`/`LocalPlayerID3`)만 다르고, 정규화 diff 로 **트리거 로직 차이 0줄**(`s6b\norm.py`).
- OBC 는 함수 안에서 전역 `LocalPlayerID`·`KeyPress`·`MemoryB`·`ParseKeyName` 를 **다시 정의**한다(OBC:71·91·101·118 등). 기능 차이는 `LocalPlayerID(nil)` 이 범위 조건(128~131 또는 0~7)을 돌려준다는 것뿐이고 4맵에 인자 없는 호출은 0건. OBC 머리말(5~10)에 PushErrorMsg 재정의 사고 기록(MapSource git `a542fbb`에서 제거).
- **OBA**(`ObserverChatAlways.lua:20~52`): theSeed 용 개조판. 키·Timer·딜레이 없음, 도우미를 `local` 로 두어 전역을 덮지 않는다.
- 가이드북에 ObserverChat 설명은 없다(grep 0). 관련: `LocalPlayerID` "비공유 조건용, Ob1~Ob4"(GB:3313~3316), `KeyPress` "누르는 동안 계속 인식"(GB:7631), "P9~P12 = 관전자1~4"(GB:4205).

### 2.2 함수 표

| 함수 | OBC 줄 | 인자 | 동작 | 주소 | 로컬 | 트리거 |
|---|---|---|---|---|---|---|
| `ObserverChatToOb` | 897~1063 | `(PlayerID, Timer, TargetPlayer, KeyName, Delay, Condition, Action)`. TargetPlayer nil → 128~131, `"Ob1"`~`"Ob4"` → 128~131 | A(1021~1034): 로컬 + 키 눌림 + 채팅창 닫힘(`0x68C144==0`) + 딜레이 0 + Condition → Timer 모드=5(`0x50000000`, 마스크 0x70000000), 딜레이=Delay(`<<16`), Action. B(1036~1047): 모드==5 이고 `0x68C144≥1` → `0x68C144=5`. C(1049~1061): **`ObserverChatCheck==0` 일 때만** 딜레이 −1 | Timer `0x70FF0000`, 0x68C144 | 로컬 | 2(+1) |
| `ObserverChatToAll` | 322~488 | 같음 | 같은 구조, 모드 2, `0x68C144=2` (A 446~459, B 461~472, C 474~487 — 직접 확인) | 같음 | 로컬 | 2(+1) |
| `ObserverChatToNone` | 490~656 | 같음 | 모드 3, `0x68C144=3` (A 614~627, B 629~640, C 642~654) | 같음 | 로컬 | 2(+1) |
| `ObserverChatToPlayer` | 658~895 | `(…, ActionArray)` 대상 0~7 마다 액션 | 누를 때마다 다음 플레이어로 순환(8×8 탐색), Storm ID 복사, **`0x57F1D8` 상위 16비트 = 2^(16+StormID)**, `0x68C144=4` | Timer `0xFFFF000F`, 0x57F1D8, 0x68C144 | 로컬 조건 아래 Game 구조체 영역에 씀 | 129(+1) |
| `TogglePlayerChat` | 70~249 | `(PlayerID, Timer, TargetPlayer(nil=로컬 0~7), KeyName, Delay, Condition, ActionOn, ActionOff)` | 플레이어가 키로 "관전자에게" 모드 토글(비트7), 켜진 채 채팅창이 열리면 `0x68C144=5`. Delay=nil 이면 켜기·끄기가 한 프레임에 연달아 실행(188~223) | Timer `0xFF`, 0x68C144 | 로컬 | 4 |
| `TogglePlayerModerate` | 12~68 | `(PlayerID, "On"/"Off", Timer, TargetPlayer 0~11, Condition, Action)` | 대상 Storm ID(`0x57EEE4+36p`, ≤15)를 찾아 `0x57F1D8` 비트 `2^i` 를 켬("Off")/끔("On") — 음소거로 추측. **로컬 조건 없음**, 매 프레임 | Timer 비트31, 0x57F1D8 하위 | 공유처럼 동작(Condition 에 따라) | 17 |
| `ObserverDrop` | 251~318 | `(PlayerID, Timer, TargetPlayer, Delay 필수, Condition, Action)` | 화면 암전(`0x657A9C=0`, 주석), Delay 뒤 로컬에서 CP=8 로 `RunAIScript("Turn ON Shared Vision for Player 1~8")` 8개를 매 프레임 — **공유 상태 변경 = 의도적 디싱크**(CA `FastDrop` 100595~100614 와 같은 액션). CP 복구 없음 | 0x657A9C, 시야 공유 | 로컬 조건 + 공유 변경 | 3 |
| `ObserverChatToAllAlways` (OBA) | OBA:20~52 | `(PlayerID 필수, TargetPlayer, Condition, Action)` | 관전자이고 `0x68C144≥1` → `0x68C144=2` | 0x68C144 | 로컬 | 1 |

키 처리: `KeyPress` = `MemoryB(0x596A18+vk, Exactly, 1)` **레벨 판정**(누르는 동안 참). Delay 는 "딜레이 0 일 때만 발동, 발동하면 Delay 로" = 재발동 대기 → 누르고 있으면 약 Delay 사이클마다 문구가 반복된다(코드 해석). 엣지 판정(`TTKeyPress`)은 쓰지 않는다.
키 코드: END 0x23, HOME 0x24, INSERT 0x2D(OBC:126·129, CA:80174~80236 표와 같음).

### 2.3 주소·값

| 주소 / 값 | 뜻 | 근거 |
|---|---|---|
| `0x512684` | 로컬 플레이어 번호, 관전자 128~131 | OBC:78~86, OBA:11~12, GB:3315 |
| CP 128~131 | 관전자 화면에 DisplayText 할 때의 CP | CA:392~396 (`PlayerConvertX`) |
| `0x596A18+vk` | 키 상태 바이트(1=눌림) | OBC:91, GB:3703~3706 |
| `0x68C144` = 0 / ≥1 | 채팅창 닫힘 / 입력 중 | CA:80322~80328 (`NotTyping`/`IsTyping`), GB:3700~3702 |
| `0x68C144` = 2 / 3 / 4 / 5 | 전체 / 대상 없음 / 개별 플레이어 / 관전자 | 함수 이름과 안내 문구(2.5)에서 추정. SC 쪽 정의는 **미확인**(1 의 뜻도 미확인) |
| `0x57EEE4+36p` | 플레이어 구조체 +4, 코드는 Storm ID(0~15)로 씀 | OBC:17·31·35 정황(추측) |
| `0x57F1D8` 하위/상위 16비트 | Storm ID 별 음소거 / 개별 수신자 마스크 | OBC:35·62·861 (추측). eudplib 에 정의 없음 |
| `0x657A9C` | "화면 암전" | OBC:293 주석뿐(추측) |
| Timer `0x58D740+(20*59)` = **`0x58DBDC`** | 4맵이 넘기는 상태 칸. startLocationPos 끝(0x58D740)과 로케이션 표(0x58DC60) 사이의 **정의되지 않은 틈** | EP81 `scdata/player.py:82`, `eudlib/locf/locf.py:17`. SC 가 이 칸을 쓰는지·동기 검사 대상인지 **미확인**. `Enable_HumanCheck` 기본 칸 `0x58DBF0`(L322:317)과는 겹치지 않음. 다른 사용처 0건 |

Timer 비트(한 Timer 를 여러 함수에 넘길 때): 모드 `0x70000000`(2/3/4/5 배타), 딜레이 `0x00FF0000`(공용), ToPlayer 번호 `0x0F000000`·표식 `0x0000000F`, Moderate/ToPlayer 탐색 플래그 `0x80000000`(서로 **충돌**), ObserverDrop 카운터 `0x0000FFF0`, TogglePlayerChat `0x000000FF`(ObserverDrop·ToPlayer 와 **충돌**).

### 2.4 맵별 사용 블록

| 맵 | 파일:줄 | 호출 위치 | 차이 |
|---|---|---|---|
| Stel | `Stella_II\MapLogic\System.lua:2883~2887` | `System()`, `main.lua:117` 최상위 | `StrDesign` = seed 판(S7) |
| ResV | `MSF_Respect_V\Interface.lua:2838~2842` | `Interface()`, `main.lua:79` | respect 판. **그리고 `func.lua:516~519` 에 상시 ToAll 트리거 4개**(아래) |
| Mem2 | `MapSource\MSF_Memory_2\Interface.lua:989~993` | `Interface()`, `main.lua:164`(`CIf(ElapsedTime≥3)` 154~166 안) | memory 판. 이 맵만 채팅 효과 블록이 상시 켜져 있어 안내 문구가 타자기로 나온다 |
| Brz | `MapSource\MSF_Breeze\Interface.lua:1164~1168` | `Interface()`, `main.lua:268` | 맵 판 없음 → mcf 판 |
| Seed | `theSeed\MapLogic\ObserverChat.lua:14~16` → `main.lua:277` | `SetupObserverChat()` = `ObserverChatToAllAlways(FP)` | 상시 전체 채팅. 키·문구 없음 |

공통 블록(4맵, 들여쓰기 제외 md5 동일 — `s6b\stel.txt` 등; Stel 원문 직접 확인):

```lua
for i = 128,131 do
  ObserverChatToOb  (FP,0x58D740+(20*59),i,"END",   10,nil,{SetMemory(0x6509B0,SetTo,i),DisplayText("\x0D\x0D!H"..StrDesign("\x1C채팅→관전자\x04에게 메세지를 보냅니다.").."\x0D\x0D",4),PlayWAV("staredit\\wav\\button3.wav"),SetMemory(0x6509B0,SetTo,FP)})
  ObserverChatToAll (FP,0x58D740+(20*59),i,"HOME",  10,nil,{… "\x07채팅→전체\x04에게 메세지를 보냅니다." …})
  ObserverChatToNone(FP,0x58D740+(20*59),i,"INSERT",10,nil,{… "\x02채팅→대상없음\x04에게 메세지를 보냅니다.(귓말 명령어 등 전용)" …})
end
```

- 루프는 **로컬 번호 128~131**(P9~P12 인덱스 8~11 이 아님). Condition nil, Delay 10, FP = P8(=7).
- **순환이 아니다**: 키마다 모드를 직접 고른다(END→5, HOME→2, INSERT→3). 세 함수가 같은 Timer 를 써서 모드는 배타적이고 딜레이는 공용 — 한 키를 누른 뒤 10사이클 동안 다른 키도 막힌다.
- 맵당 트리거 25개: i 마다 A·B × 3 = 6 × 4 = 24, C 는 i=128 ToOb 첫 호출에서 1개. 순서 ToOb-A, ToOb-B, [C], ToAll-A, ToAll-B, ToNone-A, ToNone-B.
- 안내 문구는 `"\x0D\x0D!H"` 표식을 달았다 → Mem2 는 타자기 효과. Stel 은 검사 코드가 주석 처리(`OnInit.lua:641`), ResV 는 건작 189 중에만 효과, Brz 는 효과 블록 없음 → 그런 때는 `!H` 두 글자가 보일 것(추측).

목록 밖 사용처:

| 파일:줄 | 모양 | 차이 |
|---|---|---|
| `MSF_Respect_V\func.lua:516~519` (`CreateUnitQueue()` 안, `main.lua:81`) | 슬롯 128~131 마다 `TriggerX(FP,{LocalPlayerID(n); Memory(0x68C144,AtLeast,1)},{SetMemory(0x68C144,SetTo,2); SetCp(n); DisplayText("\x07『 \x03관전 상태\x04에서도 …"); SetCp(FP)},{preserved})` (직접 확인) | 상시 ToAll. 채팅창이 열려 있는 **매 프레임** 문구를 찍는다. `Interface()` 보다 **나중에** 만들어져 같은 프레임의 마지막 쓰기가 2 → 이 맵에서 END/INSERT 모드는 사실상 덮인다(생성 순서는 확인, SC 가 전송 시점 값을 쓴다는 전제는 추측) |
| `MSF_MEME_EUD\Interface.lua:421~425` | 관전자 CIf + `FixText` + 위와 같은 트리거 | CP 를 늘 128 로 → Ob2~Ob4 에게 문구 안 보임(추측) |
| `MapSource\MSF_GaLaXy.R\System.lua:715~750` | 인라인: HOME **엣지 토글**(래치 Ccode) → 모드 0=관전자(5)/1=전체(2) | 기본 모드 0 이라 누르기 전에도 5 로 강제, 채팅 중 확인 없음 |
| `MapSource\NewTestMap1\System.lua:488~527` | 같은 인라인을 128~131 루프로 | — |
| `MSF-Template` | 0건 | — |
| `TogglePlayer*`/`ObserverDrop`/`ToPlayer` | 실제 사용 0건 | — |

### 2.5 공통 동작 (코드로 확인한 범위)

1. 관전자 본인 PC(0x512684 ∈ 128~131)에서만, 채팅창이 닫혀 있고 공용 딜레이가 0 이고 END/HOME/INSERT 중 하나가 눌려 있으면 모드를 5/2/3 으로, 딜레이를 10 으로 정한다.
2. 같은 트리거에서 CP 를 자기 번호로 바꿔 안내 문구·`button3.wav` 를 자기 화면에만 내고 CP 를 FP 로 되돌린다.
3. 이후 채팅창이 열려 있는 매 프레임 `0x68C144` 를 모드 값으로 덮어 관전자의 채팅 대상을 고정한다. 모드가 한 번도 정해지지 않았으면(초기 0 — 추측) 아무것도 안 한다.
4. 딜레이는 트리거 하나가 매 프레임 1씩 줄인다 — **그런데 그 트리거는 Ob1 조건뿐**(2.7-B1).
5. 쓰는 곳: Timer(0x58DBDC)·0x68C144·CP·화면. 게임 판정 로직은 건드리지 않는다.

### 2.6 사용 빈도

| | Stel | ResV | Mem2 | Brz | Seed | 그 밖 |
|---|---:|---:|---:|---:|---:|---:|
| 공통 블록(`ToOb/ToAll/ToNone` 각 1, 루프 4회) | 1 | 1 | 1 | 1 | · | · |
| `ObserverChatToAllAlways` | · | · | · | · | 1 | · |
| 인라인·상시 판 | · | 1(func.lua) | · | · | · | MEME 1, GXR 1, NTM1 1 |

(R1 1절 표의 `ObserverChat` 수: Seed 1·Stel 3·ResV 3·Mem2 3·Brz 3 = 13 — 위와 같다.)

### 2.7 원본 버그·위험

- **B1 딜레이 감소 트리거가 하나뿐** — `ObserverChatCheck` 는 전역 1회 플래그라 C 트리거가 첫 호출(ToOb, i=128)의 `LocalPlayerID(128)` 조건으로만 생긴다(OBC:474~487 직접 확인). Ob2~Ob4 PC 에서는 첫 입력 뒤 딜레이가 10 에서 멈춰 **키가 영구히 막힌다**. (관전자 PC 의 0x512684 가 실제로 슬롯마다 128~131 로 다르다면 — 미확인.)
- **B2 ResV 의 두 방식 충돌**(2.4 목록 밖 첫 줄).
- **B3 TogglePlayerChat 의 Delay=nil** 은 켜기·끄기가 같은 프레임에 연달아 돈다.
- **R1 ObserverDrop 은 의도적 디싱크**(2.2). 넣지 않는다(DESIGN D10).
- **R2 로컬 조건 아래 공유일 수 있는 쓰기**: ObserverDrop 의 시야 공유(확실), ToPlayer 의 `0x57F1D8`(미확인), 4맵의 Timer `0x58DBDC`(미확인 틈), ObserverDrop 의 CP 미복구. `0x68C144`·`0x657A9C`·`0x596A18` 은 로컬(추측).
- **R3 전역 재정의**: 로드 때 7개 함수, 호출 때 4개 도우미를 덮는다. 지금 맵에서는 결과가 같다.
- **R4 Timer 비트 충돌**(2.3 끝).
- R4b D3 절의 사실 오류(8절 제안에 반영): CA 사본 범위(100636~101217), "전부 로컬 메모리만"(틀림: Moderate·Drop·ToPlayer), ToOb 897~1063, ToPlayer 658~895, Always 20~52, Drop 251~318, 트리거 수(ToPlayer 129), B1 누락.

---

## 3. eudplib 0.81.0 부품

| 부품 | EP81 파일:줄 | 쓸모 |
|---|---|---|
| `f_getuserplayerid()` / `IsUserCP()` | `eudlib/utilf/userpl.py:23` / `27` | 로컬 판정. 값은 시작 때 0x512684 **1바이트**를 읽음(`:19~20`) → 관전자 128~131 그대로 |
| `DisplayTextAll`, `PlayWAVAll`, `f_printAll(At)` | `userpl.py:35~49`, `string/strall.py:13~50` | 로컬 번호로 CP 를 바꿔 표시(관전자 포함). `DisplayTextAll` 은 CP 를 안 되돌림 → `f_setcurpl2cpcache`(`memio/modcurpl.py:37~42`) |
| `f_getnextchatdst()` | `string/cpprint.py:101~110` | 다음에 쓸 줄의 EPD. `ceil(slot·54.5)` 로 홀수 줄 +2 규칙이 CtrigAsm 과 같다. **export 안 됨**(`string/__init__.py`) |
| `f_gettextptr()`, `FixedText` | `cpprint.py:89~98`, `75~86` | 0x640B58 읽기·고정 |
| `f_cpchar_print`, `f_cpchar_addstr(_epd)`, `f_cpchar_adddw` | `string/texteffect.py:83~121`, `28~56`, `59~80` | 셀 쓰기(eudplib 배치). `f_cpchar_*` 는 export 안 됨. 색 전역 `color_code`/`color_v`(24~25) 주의 |
| `TextFX_FadeIn/FadeOut/SetTimer/Remove` | `texteffect.py:338 / 422 / 165 / 245` | 색 쓸기 효과(타자기 아님). `_remove_textfx`(172~242)의 "11줄에서 식별자 찾기 + 홀짝 정렬"은 표식 찾기 참고 구현 |
| `StringBuffer.printAt/tagprint/fadeIn`, `DisplayTextAt` | `string/strbuffer.py:338 / 400 / 430`, `31~44` | 줄 전체를 다시 찍는 방식. 글자 단위 갱신 없음 |
| `SetPName` (`_PlayerName.set_pname`) | `string/pname.py:242~300` | 11줄 순회(ptr += 218, epd += 54, 홀짝 토글), `f_memcmp` 접두 비교, 0x640B58 불변이면 건너뛰기(196~206) — **채팅 줄 스캔 루프의 좋은 선례** |
| `f_memcmp` / `f_memcpy` | `memio/mblockio.py:76~91 / 65~74` | 원시 표식 비교 / 복사 |
| `f_bread_epd` / `f_dwread_epd` / `f_dwwrite_epd` | `memio/bwepdio.py:345`, `memio/dwepdio.py:46 / 135` | 첫 바이트(떠 있음), 셀 읽기·쓰기 |
| `f_getgametick` | `eudlib/utilf/gametick.py:13~25` | 속도(UERE `TalkTimer`) 대체 |
| `EUDPlayerLoop` | `eudlib/utilf/pexist.py:124~150` | **0~7 만** → 관전자 처리에 못 씀 |
| 키 입력, `0x68C144`, `0x57F1D8`, Storm ID | **없음** | 키는 eudext `local`(WP13, DESIGN 4.12)이 맡는다 |

---

## 4. eudext API 확정안

### 4.1 `eudext.textfx` — 셀과 스캐너

```python
from eudext import textfx as tfx

tfx.cell_const(ch: str, color=None) -> int          # eudplib 배치 셀 dword (1B [C][c][D][D], 2B [C][b0][b1][D], 3B [C][b0][b1][b2]); color=None 이면 0x0D
tfx.cell_const_ctrig(ch: str, color=None) -> int    # CtrigAsm iutf8 배치 (옛 데이터 비교용)
tfx.BLANK = 0x0D0D0D0D
tfx.MARK_U200B = 0x8B80E20D                          # 보이지 않는 표식 셀 (두 배치 공통)

tfx.f_scan_cells(src_ptr, dst_epd, max_cells, *, rule="ctrig", skip_odd_head=False) -> count
    # 런타임 UTF-8 → 셀 (CD__ScanChat 대체). 배치는 eudplib.
    # rule="ctrig": CtrigAsm 묶음 규칙 — 색 코드(0x01~08, 0x0E~11, 0x14~1F)는 다음 글자 셀의 C 로 합침(연속이면 마지막),
    #               0x0D 는 4개 연속일 때만 BLANK 셀 하나(모자라면 건너뜀), 0x0A 는 셀(바로 뒤가 NUL·끝이면 무시),
    #               그 밖 ≤0x7F(0x09·0x0B·0x0C·0x12·0x13 포함)는 1B 셀, 0xC0~0xDF 는 **2B 셀(원본 버그 수정)**, 0xE0~0xEF 는 3B 셀,
    #               0xF0 이상(4B)은 '?' 셀로 대체. NUL 에서 멈춤, NUL 셀은 쓰지 않음.
    # rule="eudplib": _cpchar_addstr 와 같음(색 코드도 셀).
    # 로컬 값을 읽으므로 로컬 분기 안에서만(DESIGN 3.7).
```

`rule="ctrig"` 기대값(참조 구현으로 계산할 표, 5.1): 원문 `0D 0D 21 48 13 07 EB B3 B4 EC 8A A4 20 04 48 50 00` →
셀 `0D0D210D`(!) `0D0D480D`(H) `0D0D130D`(\x13) `B4B3EB07`(보, 색07) `A48AEC0D`(스) `0D0D200D`(공백) `0D0D4804`(H, 색04) `0D0D500D`(P), count 8.
같은 원문의 CtrigAsm 배치(`cell_const_ctrig`)는 `210D0D0D 480D0D0D 130D0D0D B4B3EB07 A48AEC0D 200D0D0D 480D0D04 500D0D0D`(CA 코드 읽기 기반 — 원본 실행 검증 없음, 8절).

### 4.2 `eudext.chat` — 채팅 줄과 타자기

```python
from eudext import chat

chat.f_line_ptr(slot) -> ptr           # 0x640B60 + 218·slot (원시 텍스트 시작)
chat.f_line_epd(slot) -> epd           # 셀 시작 EPD: EPD(0x640B60) + ceil(slot·54.5)  (홀수 slot +2 정렬, f_getnextchatdst 와 같은 식)
chat.line_active(slot) -> Condition    # 첫 바이트 ≠ 0 (홀수 slot 은 −2 주소 + 마스크 0x00FF0000)
chat.f_slot_of_row(row) -> slot        # (row + [0x640B58]) % 11  (CD__GetLine; 채팅 효과는 slot 만 쓴다)
CELLS_PER_LINE = 54                    # 53 글자 + NUL

tw = chat.Typewriter(
    marker=b"\r\r!H",          # 원문 표식(원시 4바이트)
    targets=players.Everyone,  # 효과를 적용할 PC (원본 DisplayPlayer; 관전자 포함 기본)
    speed=1,                   # 사이클(프레임)당 드러낼 셀 수. 또는 every=N (N 프레임마다 1)
    erase=2,                   # 드러내기 전에 지울 앞 셀 수 (marker 의 보이는 부분 "!H")
    sound=None,                # WAV 이름: 드러낸 셀이 BLANK·공백이 아니면 재생 (UERE)
    nul_cell=True,             # 매 프레임 모든 줄 셀 53 = NUL (원본과 같음, 1.2 부수효과)
    rule="ctrig",              # f_scan_cells 규칙
    enable=None,               # Condition: 이 조건일 때만 동작 (원본의 건작 189 / 보스 CIfX / 3초 뒤)
)
tw.tick()                      # 매 프레임 한 번 (afterTriggerExec 등). 로컬 분기 안에서 11줄 처리
tw.mark(text: str) -> str      # marker + text, 그리고 text 안의 "\n" 뒤마다 marker 를 다시 붙인다
```

`Typewriter.tick()` 의 의미(1.2 를 옮김, 모두 **로컬**):
- 이 PC 가 `targets` 에 있고 `enable` 이 참일 때만. slot 0..10 마다:
  1. 원시 앞 4바이트 == marker(바이트 비교) → 셀 스캔(최대 52) → 보관소에 저장, 앞 `erase` 셀 BLANK, 줄 셀0 = `MARK_U200B`, 셀 1..52 = BLANK, `count=0`, `state=marked`.
  2. 아니고 줄이 떠 있고 셀0 `& 0xFFFFFF00 == 0x8B80E200` → 셀 1..52 = BLANK, 셀 1..count = 보관 셀 0..count−1, `count = min(count+speed, 52)`, `sound` 처리.
  3. 아니면 `state=none`.
  4. `nul_cell` 이면 셀 53 = 0.
- 상태 저장: `EUDArray(11)` × 2(count, state), 보관소 `Db(11·53·4)`(2,332B) — 원본 트리거 594개(≈1.37MiB)를 대체. 모두 로컬 오염 허용 구역(S3 7.1-4).
- 원본과 달리 스테이징 셀 없이 채팅 버퍼에 **직접** 쓴다(이 PC 에서만 도므로 같은 결과).
- 원본의 U+2008(`HCheck≠3`) 경로·이름 줄(HCheck 4/5/6)은 넣지 않는다(도달 0 / 실험 코드).
- 비용 목표: 본문 1벌(slot 루프 1) ≈ 60 트리거, 프레임당 실행 ≈ 11 × (판정 3~5) + 변환 줄의 스캔(글자당 ~6).

`DESIGN 4.8` 초안의 `ChatLines(rows, absolute)`/`lines.clear(row, mask=0)` 는 CDPrint 의 스테이징 모델을 옮긴 것인데, 사용처는 이 타자기 블록 하나뿐이고 eudext 는 직접 쓰기라 **마스크 개념이 필요 없다** → `ChatLines` 는 `chat.f_line_epd` + `textfx` 셀 도구로 대체하고, 화면 위치(row) 기준 쓰기가 필요할 때만 `chat.f_slot_of_row` 를 쓴다(8절 제안).

### 4.3 `eudext.misc.ObserverChat`

```python
from eudext import misc, local

obs = misc.ObserverChat(
    keys={"END": "ob", "HOME": "all", "INSERT": "none"},  # 원본 기본. 모드: "ob"=5, "all"=2, "none"=3
    delay=10,                  # 재발동 대기(프레임). 0 이면 엣지 판정만
    edge=False,                # True 면 누르는 순간에만(권장). False 는 원본처럼 누르고 있으면 delay 마다 반복
    notice={"ob": "\x1C채팅→관전자\x04에게 메세지를 보냅니다.",
            "all": "\x07채팅→전체\x04에게 메세지를 보냅니다.",
            "none": "\x02채팅→대상없음\x04에게 메세지를 보냅니다.(귓말 명령어 등 전용)"},
    decorate=True,             # 문구를 strdesign.design() 으로 (맵 판, S7)
    typewriter=None,           # chat.Typewriter 를 주면 문구를 tw.mark() 로 감싼다 (원본의 "\x0D\x0D!H" … "\x0D\x0D")
    sound="staredit\\wav\\button3.wav",
    always=None,               # "all" 이면 키 없이 늘 전체(OBA 판). keys 와 함께 주면 EPError (ResV 충돌 방지, 2.7-B2)
    slots=(128, 129, 130, 131),
)
obs.tick()                     # 매 프레임 한 번
```

의미(모두 로컬, 관전자 PC 에서만):
- `u = f_getuserplayerid()`, `u ∈ slots` 일 때만.
- 상태 `mode`, `wait` 는 eudext 가 가진 **로컬 전용 변수**(`EUDVariable` 2개 — 공유 로직이 읽지 않는다). 원본의 Timer EUD 주소(0x58DBDC)를 받지 않는다.
- 채팅창이 닫혀 있고(`0x68C144 == 0`) `wait == 0` 이면 `keys` 를 차례로 보고 눌린(엣지/레벨) 첫 키의 모드로 `mode` 를 바꾸고 `wait = delay`, 문구(CP = u 로 DisplayText, 뒤 CP 복구)·소리.
- `wait > 0` 이면 매 프레임 1 줄인다 — **모든 관전자 슬롯에서**(B1 수정).
- 채팅창이 열려 있고(`0x68C144 ≥ 1`) `mode ≠ 0` 이면 `0x68C144 = mode 값`.
- `always="all"` 이면 `mode` 를 처음부터 2 로 두고 키·문구를 만들지 않는다(OBA 와 같음, 트리거 1개 수준).
- 키 판정은 `eudext.local.key_down(name)`/`key_pressed(name)`(WP13)을 쓴다. `IsTyping` 은 `local.typing()`.
- 비용 목표: 키 3개 기준 본문 ≈ 12 트리거, 관전자 PC 가 아니면 판정 1개.

넣지 않는 것:
- `ToPlayer`(개별 플레이어 선택, `0x57F1D8` 상위 비트) — 주소 의미·공유성 미확인 → **설계만**(`mode="player"` 자리만 예약).
- `TogglePlayerModerate`(음소거) — 같은 이유로 설계만. 만든다면 `unsafe_` 접두사 후보(공유성 확인 전).
- `TogglePlayerChat`(플레이어가 관전자에게) — 사용 0 → 요청 시.
- `ObserverDrop` — 의도적 디싱크, 넣지 않는다(DESIGN D10).

### 4.4 옛 코드 옮기기 예

```python
# ResV GunData.lua:2879~2936 + CDPrint(… {Force1,Force2,Force5} …) — 건작 189 중에만
tw = chat.Typewriter(targets=players.Everyone, enable=gun.case_active(189))
# 문구 표: "\x0D\x0D!H\x13…" → tw.mark("\x13…")

# UERE CallTriggers.lua:942~1028 — 보스전 속도·소리
tw = chat.Typewriter(targets=[*players.Force1, *players.Observers], every=talk_timer,
                     sound="staredit\\wav\\STalk.ogg", enable=boss_on)

# Stella/ResV/Mem2/Breeze 관전자 블록
obs = misc.ObserverChat(typewriter=tw)          # Mem2 처럼 효과 블록이 있을 때만 typewriter 를 넘긴다

# theSeed ObserverChat.lua:14~16
obs = misc.ObserverChat(keys=None, always="all")
```

---

## 5. 시험

### 5.1 에뮬레이터 시험 (`tests/t_textfx.py`, `tests/t_chat.py`, `tests/t_misc_obs.py`)

1. `cell_const` / `cell_const_ctrig`: 1B·2B·3B·색 있음/없음 조합 기대값(4.1 예 포함). 예: `cell_const("가")` = `0x80B0EA0D`, `cell_const("a", 0x07)` = `0x0D0D6107`, `cell_const_ctrig("a", 0x07)` = `0x610D0D07`, `cell_const("é")` = `0x0DA9C30D`, `cell_const_ctrig("é")` = `0xA9C30D0D`.
2. `f_scan_cells(rule="ctrig")`: 4.1 예, `"\r\r\r\r"`(BLANK 1), `"\r\r\r"`(0), `"a\n"`(끝 줄바꿈 무시), `"\x07\x04a"`(마지막 색 04), 52셀 상한, `"é"`(2B), 4B 문자. 파이썬 참조 구현과 셀 단위 비교. `rule="eudplib"` 은 eudplib `_cpchar_addstr` 결과와 비교.
3. `Typewriter.tick()`: 채팅 버퍼 모델(0x640B60~ 11줄 × 218B, 0x640B58)에 표식 줄을 넣고 프레임마다
   - 변환 프레임(프레임 0)에 줄 = `MARK_U200B` + BLANK×52 (+ 셀 53 NUL),
   - 프레임 f(≥1)에 셀 1..min(f−1, 52) = 보관 셀 0..f−2 (앞 2개는 지운 `!H` 라 BLANK). 원본 순서: 쓰고 나서 count+1 (1.2 S8b),
   - 홀수 slot 에서 셀 시작이 +2 인지, 원시 표식 비교가 바이트 단위인지,
   - 줄이 꺼지면(첫 바이트 0) 멈추는지, 같은 slot 새 줄에서 다시 시작하는지,
   - `targets` 밖 PC 번호로 돌리면 버퍼가 그대로인지,
   - `sound` 가 BLANK·공백에서 안 나는지(eudplib 배치 공백 셀 `0x0D0D200D`).
4. `ObserverChat.tick()`: 로컬 번호 0·128·131 × 키 상태 × `0x68C144` 값으로
   - 128·131 모두에서 두 번째 입력이 `delay` 뒤에 먹히는지(B1 수정),
   - 채팅 중에는 키를 무시하는지, 채팅창이 열리면 `0x68C144` 가 모드 값인지,
   - 로컬 번호 0 에서는 아무 메모리도 바뀌지 않는지,
   - 문구 DisplayText 의 CP 가 u 이고 끝나면 호출 전 CP 인지.

### 5.2 인게임 확인 항목

1. 타자기: 가사·대사가 한 글자씩 나오는지, 홀수 줄·가운데 정렬(`\x13` 셀) 동작, `!H` 가 안 보이는지, 212바이트 NUL 이 긴 줄을 자르는지.
2. 2바이트 UTF-8(라틴 확장 등) 문구가 원본과 달리 제대로 나오는지.
3. 관전자 2~4번 슬롯에서 키 모드 전환이 두 번 이상 되는지(B1), 관전자 PC 의 0x512684 가 슬롯마다 128~131 로 다른지.
4. `0x68C144` 2/3/5 에서 실제 채팅이 누구에게 가는지(특히 3 "대상 없음").
5. `always="all"` 에서 관전자 채팅이 플레이어에게 보이는지(theSeed 방식).
6. 효과 블록이 없는 맵에서 `typewriter=None` 이면 문구에 `!H` 가 안 붙는지.

---

## 6. 함정

1. **표식 비교는 원시 바이트로.** 홀수 slot 은 dword 경계가 2바이트 어긋난다. `Memory` 조건 하나로 비교하면 홀수 줄에서 실패한다(원본은 `CbyteConvert` 4판으로 해결).
2. **스캐너 규칙**: eudplib `_cpchar_addstr` 를 그대로 쓰면 `!H` 위치·공개 단계가 바뀐다(1.7). `rule="ctrig"` 가 기본.
3. **셀 53 NUL** 은 매 프레임 모든 줄을 212/214바이트에서 자른다. 원본 호환이 기본이지만 긴 줄을 쓰는 맵은 `nul_cell=False` 를 검토.
4. **로컬 값 → 공유 메모리**: 원본은 채팅 버퍼(로컬)를 공유 트리거 메모리에 옮겼다. eudext 는 로컬 분기 안의 전용 저장소만 쓰고, 그 저장소를 공유 로직이 읽지 않게 한다.
5. **색 코드 전역**: eudplib `f_cpchar_print` 의 `color_code` 는 파이썬 전역이다(R4a D.6). textfx 는 이 함수를 부르지 않는다.
6. **관전자 루프**: `EUDPlayerLoop` 는 0~7 만 돈다. 관전자 처리는 `f_getuserplayerid()` 범위 비교로.
7. **Timer 주소를 받지 않는다**: 원본의 `0x58DBDC` 는 정의되지 않은 틈이다. eudext 는 자체 변수로 대체하고, 옛 코드를 옮길 때 그 주소를 다른 용도로 쓰던 곳이 있는지(0건 확인) 다시 보지 않아도 된다.
8. **ResV 식 상시 트리거와 키 모드를 함께 두지 말 것**(B2). `always` 와 `keys` 는 배타.
9. **레벨 키**: 원본은 누르고 있으면 `delay` 마다 문구가 반복된다. 새 맵은 `edge=True` 권장.
10. **CP**: 문구 표시 뒤 CP 를 되돌린다(원본은 FP 로 되돌림 — 호출자 CP 가 FP 가 아니었다면 다름).
11. **`0x68C144` 쓰기 시점**: 원본·eudext 모두 "채팅창이 열려 있는 매 프레임" 덮는다. SC 가 전송 시점의 값을 쓴다는 전제는 미확인.

---

## 7. DESIGN.md 수정 제안

1. **4.8 버퍼 형식 주의** 문장 교체: "1·2바이트 글자의 0x0D 채움 위치가 반대" → "1바이트 `[C][D][D][c]` 대 `[C][c][D][D]`, 2바이트 `[C][D][b0][b1]` 대 `[C][b0][b1][D]`, 3바이트 같음. 추가로 CtrigAsm `CD__ScanChat` 은 색 코드를 다음 글자 셀에 합치고 0x0D 를 4개 단위로만 셀로 만들며 2바이트 UTF-8 을 처리하지 못한다 — eudplib 런타임 변환과 **묶음 규칙이 다르다**(S6 1.7)".
2. **4.8 API 교체**: `ChatLines(rows, absolute)`·`lines.clear(row, mask=0)`·`lines.cells(row).convert_color(...)` 초안 → `chat.f_line_ptr/f_line_epd/line_active/f_slot_of_row`, `chat.Typewriter(marker, targets, speed|every, erase, sound, nul_cell, rule, enable)`, `textfx.cell_const/cell_const_ctrig/f_scan_cells(rule=)/BLANK/MARK_U200B` (S6 4.1~4.2).
   "사용자 맵 관용: 초기화 마스크 0" 설명은 "CDPrint 의 스테이징 셀 마스크 0 = 이번 사이클에 그 셀을 쓰지 않음. eudext 는 직접 쓰기라 마스크가 없다" 로 고친다.
   `f_line13`·`PinnedText` 는 `display.show_line13`·`display.pinned()` 로 옮긴다(S3 7.2) — 중복 제거.
3. **4.8 우선 구현 범위**: "채팅 효과 블록 대체" = `Typewriter` + `f_scan_cells(rule="ctrig")`. `convert_color`·`reveal`·`blit`·`convert_letter` 는 설계만(사용 0).
4. **4.8 위험** 추가: 셀 53 NUL 부수효과, 홀수 slot 원시 비교, 스캐너 규칙.
5. **4.19 표 관전자 채팅 행** 교체: API `misc.ObserverChat(keys, delay, edge, notice, decorate, typewriter, sound, always, slots)` + `obs.tick()`, 로컬, 위험 **하**(단 ToPlayer·음소거는 공유성 미확인 → 설계만, ObserverDrop 제외). 원본 버그 B1 을 고친다는 것을 명시.
6. **4.12 `local`** 에 `key_down/key_pressed(name)`, `typing()` 이 ObserverChat 의 선행 조건임을 적고, WP19 선행에 WP13 이 이미 있으니 그대로.
7. **6.1 WP17 완료 조건**: "S6 5.1 의 셀·스캐너·타자기 시험 통과, 채팅 버퍼 모델(11줄·홀짝 정렬·0x640B58)을 `testing/scmodel.py` 에 추가". WP19: "ObserverChat 시험(128·131 두 슬롯에서 두 번째 입력)".
8. **0.2 표** "채팅 효과·관전자 채팅 5맵·4맵 복붙 블록" 옆에 "원본 보관소 1.37MiB → Db 2.3KB" 를 적어 용량 이득을 보인다.
9. **R4a 수정 메모**(8절 참고 표): D.3 표 아래 "HTextEff 는 표식 셀 줄을 스캔" → "원시 `\x0D\x0D!H` 줄만 1회 스캔, 표식 셀은 블록이 직접 써서 상태 유지". E.2 의 "초기화 마스크 0 으로 기존 글자를 지우지 않고" 에 "셀 53 NUL 은 매 사이클 씀" 추가.
   **R4b 수정 메모**: D3 절 줄 범위·"전부 로컬 메모리만"·트리거 수·B1 누락(2.7 끝), D8 "ObserverChat 계열 하 / 로컬 메모리만" → "Chat 계열은 로컬, Moderate·ToPlayer·Drop 은 공유 쓰기 가능".
10. **8절 표**에 "채팅 효과 블록·관전자 채팅 → `docs/spec/S6_chat.md`" 행 추가.

---

## 8. 미확인

1. **인게임 실행 없음**: 0x0D 가 안 보이는 점, 줄 가운데 `\x13` 셀의 정렬, 실제 타자기 모양, 212/214바이트 잘림이 보이는지.
2. `CD__ScanChat` 의 "색 코드 + 1바이트" 경로 끝(최종 셀 `[C][0D][0D][c]`)과 짝수 표식 줄 스캔 결과(`[!][H][\x13]…`, 0x0D 두 개 건너뜀)는 **코드 읽기 결론**이고 실행 검증이 없다. 4.1 의 CtrigAsm 배치 기대값도 같다.
3. `SetNVar(…,Subtract)` 가 0 에서 멈추는지 — CDPrint 의 딜레이 감소가 기대는 성질(CA:21850 `CSub` 주석만 근거).
4. `0x68C144` 값 1~5 의 SC 쪽 정의(특히 1·3·4), SC 가 전송 시점 값을 읽는지.
5. `0x57F1D8` 두 반쪽의 뜻, `0x57EEE4` 가 Storm ID 인지, `0x657A9C` 의 뜻.
6. `0x58D740~0x58DC5F` 틈의 정체·초기값·동기 검사 여부(원본 Timer 칸).
7. 관전자 PC 의 0x512684 가 슬롯마다 128~131 로 다른지(모두 128 이면 B1 이 드러나지 않음).
8. 트리거 1사이클 = 1프레임인지(각 맵의 트리거 주기) — 공개 속도의 단위.
9. UERE 의 두 호출처(`Destr0yer.lua:574`, `Sans.lua:506`)가 같은 프레임에 함께 돌면 두 칸씩 나아가는지.
10. NTM1 `HCheck 5/6` 분기의 의도(실험 코드로 보임).
11. `button3.wav`·`STalk.ogg` 가 각 맵 MPQ 에 들어 있는지.
12. 효과 블록이 꺼진 맵(Stel·Brz, ResV 평소)에서 관전자 안내 문구의 `!H` 가 보이는지.
13. 트리거 수·용량은 수동 어림이다(1.5).
14. eudplib `f_getnextchatdst`·`f_cpchar_*` 는 export 가 아니라 판이 바뀌면 경로가 바뀔 수 있다 — eudext 는 `_compat` 에서만 부른다(DESIGN 3.9).
