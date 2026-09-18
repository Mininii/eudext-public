# S5 — dat 패치 표와 BGM (`eudext.datpatch`, `eudext.bgm` 명세)

작성 2026-09-17. 코드는 고치지 않았다. 근거는 `파일:줄`, 확인하지 못한 것은 "(추측)".
실험 스크립트(모두 스크래치패드 `spec_s4\`): `dat\defs.py`·`cmpdefs.py`(정의 추출·판 비교), `dat\usage.py`(사용 빈도, 결과 `usage.txt`), `dat\coverage.py`(scdata 대비), `dat\scdata_members.py`, `dat_expect.py`(액션 기대값), `bgm\measure_len.py`(소리 길이).

## 약어

| 약어 | 위치 |
|---|---|
| SD | `C:\Users\whatd\Desktop\Stormcoast Fortress\ScmDraft 2` |
| MS | `SD\MapSource` |
| TPL | `C:\Users\whatd\Documents\MSF-Template` |
| LIB | `MS\Library\LibraryFor322.lua` |
| CA | `MS\Library\CtrigAsm v5.5.lua` |
| SEED | `SD\theSeed\Engine\func.lua` |
| M2 / UERE / BRZ | `MS\MSF_Memory_2` / `MS\MSF_UE_RE` / `MS\MSF_Breeze` |
| RESV / STEL | `SD\MSF_Respect_V` / `SD\Stella_II` |
| EP81 | eudplib 0.81.0 소스 `…\scratchpad\upstream\eudplib\src\eudplib\` |
| ED | `C:\euddraft0.9.2.0` (실제 0.9.10.11 / eudplib 0.76.14) |
| UPED | euddraft 최신 소스 `…\scratchpad\upstream\euddraft\` |

---

## 0. 한눈에

**dat**
- 헬퍼는 `SetUnitsDatX(UnitID, {키=값})`, `SetWeaponsDatX(WepID, {…})`, `SetUnitAbility(…위치 인자 12~19개)` 와 `PatchInsert*`(액션을 큐에 쌓기). 정본 = TPL `func.lua:27, 98, 316`. theSeed 판(SEED)이 필드가 가장 많다(유닛 65종, 무기 21종 + flingy/sprites/images/upgrades 헬퍼).
- **큐 적용 시점**: TPL `PatchInsert` → `CtrigInitArr[FP+1]` → CtrigAsm `EndCtrig` 의 `InitCtrig()`(CA:775, 38508~) 가 **게임 시작 1회**. 매 프레임 큐(`PatchArrPrsv`), 조건부 큐(RESV 모드 선택, STEL 4모드, M2 보스, UERE 페이즈)도 있다. **되돌리기는 어느 판에도 없다.**
- **scdata(0.81) 대비**: 실제 쓰기 6,875건 중 **89.9% 가 멤버 하나로 그대로**, 97.3% 가 부분 포함 대응. 호출 지점 기준으로는 Y 52.1%, Y+P 74.1%. 필드 수 기준 114개 중 Y 98·P 4·N 12. **N 은 거의 플레이어별 표**(생산 가능 `0x57F27C` 147회, 업그레이드·테크 36회).
- **결함 3개**: TPL 계열의 `WhatSndInit`/`WhatSndEnd` 가 eudplib·EUD Editor 와 **주소가 반대**, `Reqptr` 가 TPL 계열에서 **아무 일도 안 함**(STEL 22회·RESV 33회 호출), BRZ 의 `PatchInsert` 3줄이 **적용 안 됨**(추측).
- scdata 는 **대입 한 줄 = 그 자리 트리거 1개**(`DoActions`)라 시작 패치 수백 줄을 그대로 쓰면 트리거가 많다 → eudext 는 **scdata 멤버의 주소 정보(offset/stride/size)만 빌려** 액션을 모아 64개씩 낸다.

**BGM**
- 엔진은 **로컬형**(`IBGM_EPD` 인자 5, TPL)과 **공유형**(`AddBGM`+`Install_BGMSystem`+`IBGM_EPDX`, LIB + 맵, MSQC 로 경과 시간 동기화) 두 계통.
- 시간은 `0x51CE8C`(실제 시간 ms). 배속 보정 없음. 곡 길이는 전부 수동.
- "여러 조각" 표 형식은 **요청마다 조각 하나를 돌아가며** 고르는 것이고, 진짜 이어 재생은 맵이 손으로 짠다(M2 1,456 트리거).
- 소리 파일은 맵별 euddraft 플러그인이 `MPQAddFile("staredit\\wav\\"+이름, bytes)` 로 넣는다.
- eudext.bgm: 곡 표(길이 자동 측정) + `MPQAddWave(이름, 경로)` + 곡 수·대상 수와 무관한 재생 루프 + `local`/`synced` 모드 + 조각 이어 재생 + 끄기.

---

# A. dat 패치

## A.1 정의 목록

| 판 | 정의 (파일:줄) | 서명·차이 |
|---|---|---|
| **TPL (정본)** | `SetWeaponsDatX(WepID,Property)` TPL `func.lua:27~96`, `SetUnitsDatX(UnitID,Property)` `:98~264`, `SetUnitAbility(UnitID,WepID,DmgType,AIFlag,HP,Shield,Size,Cooldown,Damage,DFactor,Splash,ObjNum,RangeMax,SeekRange,Point,Text,KillPoint,UpgradeType)` `:316~456` | 두 헬퍼가 **불릴 때마다 전역 `PatchInsert` 를 다시 정의**해 `CtrigInitArr[FP+1]` 에 넣는다(`:32~34`, `:103~105`). `PatchArrPrsv={}`(`:9`)는 있지만 `PatchInsertPrsv` 는 없다. `Reqptr` 무시(`:237~239` "지원되지 않음"). `Playerable=2` 이면 P1~5=1, P6~8=0(`:127~135`). `SuppCost` ×2(`:154`), `HP` ×256(`:156`). 모르는 키는 `PushErrorMsg`(`:91, :259`) |
| STEL | `SD\Stella_II\Engine\func.lua` | TPL 과 같음(빈 줄 하나 차이, 조사 에이전트 확인) |
| **SEED (가장 넓음)** | SEED `:10~12` PatchInsertPrsv, `:13~15` PatchInput, `:33` SetWeaponsDatX, `:145` SetDamageRatio, `:191` SetUnitsDatX, `:392` SetUpgradesDatX, `:434` SetFlingyDatX, `:466` SetSpritesDatX, `:494` SetImageDatX, `:673` ApplyReqScripts, `:795` SetUnitAbility(인자 19, +ArmorDefType) | 무기에 Effect/TargetErrorMessage/SpecialAttack(`:66~101`), 유닛 12개 추가(`:354~382`), AdvFlag 비트 이름 31개(`:180~189, 281~285`). `Playerable=2` → P1~7=1, P8=0(`:220~228`). **Prsv 큐 = 매 프레임 재적용**(`:10` 주석 "게임 중 계속 초기화되는 경향이 있는 필드용") |
| DPS (읽기만) | `SD\DPS_eud\function.lua:35` PatchInit, `:40` PatchInput, `:46` PatchInsert→PatchArr, `:49` PatchInsert2, `:52` PatchInsertPrsv, `:56~58` PatchInsertC(빈 함수), `:60` SetUnitsDatX, `:207` SetWeaponsDatX, `:323` SetUnitAbility(14), `:357` SetUnitAbilityT | 무기 키 `DmgType`(`:277`), `WepID==130` 무시(`:208`), `Reqptr` → Prsv 큐(`:189~190`) |
| RESV | `SD\MSF_Respect_V\func.lua:2~5` 큐, `:20` SetWeaponsDatX, `:84~92` PatchInsert/2/Prsv, `:95` SetUnitsDatX, `:551` SetUnitAbility(14) | `Reqptr` 무시(`:225~226`) |
| BRZ | BRZ `func.lua:15~18` 큐, `:20`, `:82~92`, `:93`, `:1432` SetUnitAbility(12), `:2117` SetFlingySpeed | `Reqptr` → Prsv(`:218~219`), `Shield=false` 는 플래그만 끔 |
| M2 | M2 `func.lua:2334` SetFlingySpeed(액션 반환), `:2565` `SetWeaponsDat2X(PatchTable,…)`, `:2636` `SetUnitsDat2X` (대상 표를 인자로), `OnPluginStart.lua:6~100` 지역 래퍼 15종, `:239` PatchInsert | 정적 dat 는 `EUDEditorDat.lua`(A.6) |
| UERE | UERE `func.lua:1964` SetFlingySpeed, `:1972~2036` `SetWeaponsDat(Condition,WepID,Property,Flag)`, `EUDinit.lua:4~105` 래퍼 16종 | `SetWeaponsDat` 는 **그 자리에서 `Trigger2(FP, Condition, Action, Flag)`** 를 만든다(조건부·매 프레임 가능) |

공통 규칙: `SetMemoryB/W` 는 주소를 4바이트 경계로 내리고 칸 위치로 마스크·시프트를 정한다(CA:43497~43541). `SetMemoryW` 는 홀수 오프셋이면 오류.

### A.1.1 큐가 적용되는 때

| 큐 | 적용 코드 | 시점 |
|---|---|---|
| `CtrigInitArr[FP+1]` (TPL/STEL/SEED `PatchInsert`) | `EndCtrig` → `InitCtrig()` (CA:775) → 64개씩 트리거(CA:38508~38545) | **1회**, 트리거 목록 끝. STRCtrig 모드의 첫 사이클 순서는 추정 문서뿐(`DPS_eud\eud\spec\G5_trig.md:341~345`) |
| DPS PatchArr/2 | `DoActions2(FP,PatchArr,1)` (`function.lua:41~42`) ← `OnInit.lua:89` | 그 자리에서 1회 |
| Prsv 큐 | `DoActions2(AllPlayers, PatchArrPrsv)` — SEED `:14` ← `MapLogic\OnInit.lua:21`, STEL `MapLogic\OnInit.lua:707`, RESV `OnInit.lua:666`, BRZ `onInit.lua:336`, DPS `function.lua:43` | **매 프레임** (플레이어 수만큼) |
| RESV / BRZ PatchArr | `CIfOnce(FP)` 안 (RESV `OnInit.lua:270, 283~284`, BRZ `onInit.lua:138, 245~246`) | 1회 |
| RESV 모드 패치 | `Interface.lua:571~588`, `CIfOnce(FP,{CD(GS,1)})` (`:531`) | 모드 선택 뒤 1회 |
| STEL Act4thPatchArr | `Vars.lua:284~302` → `MapLogic\System.lua:554` `Trigger2X(FP,CD(GMode,4),…)` | 조건부 |
| M2 | `OnPluginStart.lua:318` 1회, `:319` Prsv(Force1), `GunData.lua:1532~1554` `tesPatchT` → `DoActions2(FP, tesPatchT, 1)` | 1회 / 매 프레임 / 보스 패턴 진입 1회(되돌림 없음) |
| UERE | `EUDinit.lua:467` (`main.lua:104` 3초 대기 안 `CIfOnce`), `PreservedTrig.lua:92` Prsv, `Sans.lua:78, 106, 144, 164, 195` | 3초 뒤 1회 / 매 프레임 / **페이즈 조건 동안 매 프레임**(다음 페이즈가 덮음) |

## A.2 필드 표 (필드 → dat, 주소 식, 크기, 원소 수) + scdata 대비

주소 식은 모두 `기준 + 번호 × 간격`. 판정 Y = scdata 멤버 하나로 그대로, P = 부분, N = 없음. scdata 줄 번호는 EP81 `scdata\unit.py` / `weapon.py` / `flingy.py` / `sprite.py` / `image.py` / `upgrade.py`. TEP 정의 줄은 SEED(가장 넓음) 또는 TPL.

### A.2.1 units.dat (원소 228, 번호 0~227; SEED `:207~382`, TPL `:114~256`)

| TEP 키 | 기준 | 폭(간격) | 변환·마스크 | scdata 0.81 | 판정 |
|---|---|---|---|---|---|
| MinCost / GasCost / BuildTime | 0x663888 / 0x65FD00 / 0x660428 | 2 | | `mineralCost` :362 / `gasCost` :363 / `timeCost` :364 | Y |
| SuppCost / SuppProv | 0x663CE8 / 0x6646C8 | 1 | Cost 는 **값×2** | `supplyUsed` :368 / `supplyProvided` :367 | Y |
| HP | 0x662350 | 4 | **값×256** | `maxHp` :168 | Y |
| Shield | 0x6647B0(1) + 0x660E00(2) | | bool 또는 수치(→ 플래그 1 + 양) | `hasShield` :157 + `maxShield` :166 | Y |
| Armor / DefType / DefUpType / Height | 0x65FEC8 / 0x662180 / 0x6635D0 / 0x663150 | 1 | | `armor` :310 / `sizeType` :297 / `armorUpgrade` :296 / `elevation` :175 | Y |
| BdDimX / BdDimY | 0x662860 | 2 (간격 4) | X 0xFFFF, Y 0xFFFF0000 | `buildingDimensions` :321 (dword 통째) | P |
| SizeL/SizeU, SizeR/SizeD | 0x6617C8, 0x6617CC | 2 (간격 8) | 0xFFFF / 0xFFFF0000 | `unitBoundsL/T/R/B` :349~358 | Y |
| AdvFlag `{값, 마스크}` | 0x664080 | 4 | 마스크 = 인자 | `baseProperty` :293 (DwordEnum) | P (값·마스크 한 번에 쓰는 API 없음) |
| AdvFlag 비트 이름 31개 (SEED) | 0x664080 | 비트 | | `baseProperty.<Flag>` :62~107 (10개 이름 다름, 예 RoboticUnit→Robotic) | Y |
| StarEditFlag / GroupFlag / MovementFlag | 0x661518(2) / 0x6637A0 / 0x660FC8 | | | `availabilityFlags` :383 / `groupFlags` :366 / `movementFlags` :186 | Y |
| ComputerAI | 0x660178 | 1 | 바이트 통째 | `ignoreStrategicSuicideMissions` :258(bit0) + `dontBecomeGuard` :273(bit1) | P |
| Class / Graphic | 0x663DD0 / 0x6644F8 | 1 | | `rank` :187 / `flingy` :128 | Y |
| AirWeapon / GroundWeapon / SeekRange / SightRange / SpaceProv / SpaceReq / RClickAct | 0x6616E0 / 0x6636B8 / 0x662DB8 / 0x663238 / 0x660988 / 0x664410 / 0x662098 | 1 | | `airWeapon` :233 / `groundWeapon` :232 / `seekRange` :294 / `sightRange` :295 / `transportSpace*` :369~370 / `rightClickAction` :311 | Y |
| HumanInitAct / ComputerInitAct / IdleOrder / AttackOrder / AttackMoveOrder | 0x662268 / 0x662EA0 / 0x664898 / 0x663320 / 0x663A50 | 1 | | `humanIdleOrder` :213 / `computerIdleOrder` :208 / `returnToIdleOrder` :218 / `attackUnitOrder` :223 / `attackMoveOrder` :231 | Y |
| RdySnd | 0x661FC0 | 2 | (원소 106 검사 없음, 추측) | `readySound` :314 | Y |
| **WhatSndInit** | **0x662BF0** | 2 | | **`whatSoundEnd`** :316 | Y, **이름 반대** |
| **WhatSndEnd** | **0x65FFB0** | 2 | | **`whatSoundStart`** :315 | Y, **이름 반대** |
| YesInit / YesEnd / PissedInit / PissedEnd | 0x663C10 / 0x661440 / 0x663B38 / 0x661EE8 | 2 | 번호 < 106 검사 | `yesSoundStart/End`, `pissedSoundStart/End` :317~320 | Y |
| BuildScore / KillScore | 0x663408 / 0x663EB8 | 2 | | `buildScore` :371 / `killScore` :372 | Y |
| Reqptr | 0x660A70 | 2 | TPL·STEL·RESV·MEME **무시**, DPS·BRZ·M2·NTM1 Prsv | `requirementOffset` :365 | Y |
| MaxHitsAir / MaxHitsGround / MapString / StartDirection / BroodWarFlag / Subunit1 / ConstructionAnimation / Portrait (SEED) | 0x65FC18 / 0x6645E0 / 0x660260 / 0x6605F0 / 0x6606D8 / 0x6607C0 / 0x6610B0(4) / 0x662F88 | | | `maxAirHits` :246 / `maxGroundHits` :234 / `nameString` :373 / `startDirection` :146 / `broodWarFlag` :382 / `subUnit` :130 / `constructionGraphic` :139 / `portrait` :361 | Y |
| Subunit2 / AddonPlacement / InfestationUnit (SEED) | 0x660C38 / 0x6626E0+(번호−106)·4 / 0x664980+(번호−106)·2 | | Addon 은 X/Y 마스크 | 주석 :132 / `NotImplementedMember` :339 / 주석 :134~138 | N |
| **Playerable** | **0x57F27C + P·228 + 번호** (P = 0~7) | 1 | 8칸, `2` = 사람만 | 없음 (플레이어 표) | **N** |

- scdata 의 원소 수는 멤버가 아니라 클래스 `range` 로만 있다(유닛 0~227 `unit.py:386`, 무기 0~129 `weapon.py:81`). 106·96 칸 필드는 표현이 없다 → eudext 표에 `count` 를 따로 둔다.
- 이름 반대 확인: EUD Editor 표 M2 `EUDEditorDat.lua:495` "What Sound Start #206" 이 `0x66014C = 0x65FFB0 + 2·206` → **0x65FFB0 = Start**(eudplib 과 같음). TPL `:221~224` 가 반대.

### A.2.2 weapons.dat (원소 130; SEED `:45~101`, TPL `:39~89`)

| TEP 키 | 기준(폭) | scdata | 판정 |
|---|---|---|---|
| DmgBase / DmgFactor | 0x656EB0(2) / 0x657678(2) | `damage` :66 / `damageBonus` :67 | Y |
| Cooldown / ObjectNum | 0x656FB8(1) / 0x6564E0(1) | `cooldown` :68 / `damageFactor` :69 | Y |
| Splash | `true`→0x6566F8←3, `false`→←1, `{a,b,c}`→←3 + 0x656888/0x6570C8/0x657780(2) | `explosionType` :62 + `splashInner/Middle/OuterRadius` :63~65 | Y |
| Effect (SEED) | 0x6566F8 | `explosionType` :62 | Y |
| DamageType / DmgType(DPS) | 0x657258(1) | `damageType` :58 | Y |
| RangeMin / RangeMax | 0x656A18(4) / 0x657470(4) | `minRange` :55 / `maxRange` :56 | Y |
| TargetFlag | 0x657998(2) | `targetFlags` :53 | Y |
| UpgradeType / IconType | 0x6571D0(1) / 0x656780(2) | `upgrade` :57 / `icon` :78 | Y |
| Behavior / LaunchX / LaunchY / LaunchSpin / AttackAngle / RemoveAfter | 0x656670 / 0x657910 / 0x656C20 / 0x657888 / 0x656990 / 0x657040 (모두 1) | `behavior` :59 / `forwardOffset` :73 / `verticalOffset` :75 / `launchSpin` :72 / `attackAngle` :71 / `removeAfter` :61 | Y |
| FlingyID | 0x656CA8(4) | `flingy` :50 (1바이트, 간격 4) | Y |
| WepName / TargetErrorMessage | 0x6572E0(2) / 0x656568(2) | `label` :49 / `targetErrorMessage` :77 | Y |
| SpecialAttack (SEED) | 0x6573E8 | 주석 :51 | N |

### A.2.3 기타 dat (SEED 만)

| dat | TEP 키 → 기준(폭) | scdata | 판정 |
|---|---|---|---|
| upgrades (61) | Reqptr 0x6558C0, MaxLevel 0x655700, Min/Gas/Time Cost·Factor (SEED `:405~426`) | `upgrade.py:29~39` | Y |
| flingy (209) | Speed 0x6C9EF8(4), Acceleration 0x6C9C78(2), HaltDistance 0x6C9930(4), TurnRadius 0x6C9E20(1), MovementControl 0x6C9858(1) | `flingy.py:28~34` | Y |
| sprites | ImageFile 0x666160(2), IsVisible 0x665C48 | `sprite.py:21, 25` | Y |
| images (999) | IscriptID 0x66EC48, GraphicsTurns, Clickable, UseFullIscript, DrawIfCloaked | `image.py:22~33` | Y |
| images | GRPFile, Overlay 5종 | 주석 `image.py:20~21, 34~38` | N |
| 피해 배율 `SetDamageRatio` | `0x515B88 + 0x14·피해형 + 4·크기` (SEED `:145~176`) | 없음. eudplib 문서 주석은 **0x515B84**(`unit.py:303`) | N, 주소 불일치 |

### A.2.4 플레이어 표 (dat 아님, raw 큐로 씀)

| 표 | 주소(조사 에이전트 분류, 이름은 추측) | 사용 |
|---|---|---|
| 유닛 생산 가능 | 0x57F27C + P·228 + U | Playerable 147 |
| 업그레이드 최대·현재 레벨, 테크 사용 가능·연구됨 (SC/BW) | 0x58D088, 0x58D2B0, 0x58F278, 0x58F32C, 0x58CE24, 0x58CF44, 0x58F050, 0x58F140 | 36 |
| 기타 | 0x657A9C, 0x58D718 | 3 |

eudplib 0.81 에서 `0x58D2B0` 은 `upgrade.py:61` 안 지역 상수(`sc_researched`)로만 보인다. 공개 멤버는 확인하지 못했다.

## A.3 사용 빈도 (주석·정의 제외 호출 지점, `usage.py`)

| 맵 | 헬퍼 호출 | 많이 쓴 필드 | raw 큐 |
|---|---|---|---|
| DPS | SetUnitsDatX 25, SetWeaponsDatX 8, SetUnitAbility 2(+T 1) | 유닛 37종/149회(MinCost·GasCost·SuppCost 8, Reqptr 7, Size* 6 …), 무기 11종/20회 | flingy.MovementControl 1 |
| theSeed | SetUnitsDatX 35, SetWeaponsDatX 4, Flingy 2, Sprites 2, Upgrades 1, DamageRatio 1, SetUnitAbility 1(61행 루프), SetUnitClickable 2 | 유닛 65종/163회(비트 이름 78, SuppCost 7 …), 무기 8종/17, flingy 5종/10 | e3s DataEditor 266줄 루프(`MapLogic\EUDEditorDatPatch.lua:454`) |
| Stella_II | SetUnitsDatX 37, SetWeaponsDatX 7, SetUnitAbility 1(63행 루프), SetUnitClickable 4 | 유닛 29종/237회(SuppCost·MinCost 23, Playerable 22, **Reqptr 22 무시됨**, AdvFlag·GasCost 17 …), 무기 9종/44 | 28 (테크 15, 생산 가능 5 …) |
| Respect_V | SetUnitsDatX 65, SetWeaponsDatX 19, SetUnitAbility 53 | 유닛 26종/344회(MinCost 41, SuppCost 37, BuildTime 36, Playerable 33, **Reqptr 33 무시됨** …), 무기 9종/119 | 27 (업그레이드·테크 17 …) |
| Memory_2 | 지역 래퍼 113(UnitSizePatch 41, UnitEnable 26, SetUnitAdvFlag 12 …), SetWeaponsDat2X 3, SetUnitsDat2X 2 | Size*, Playerable, Reqptr, 비용 | 37 + **EUDEditorDat 1,182줄** |
| UE_RE | 지역 래퍼 98(UnitEnableX 14, EffUnitPatch 11 …), SetWeaponsDat 5 | SuppCost, Playerable, Reqptr, Size* | 71 (upgrades 33 …) + **EUDEditorDat 773줄** |
| Breeze | SetUnitsDatX 39, SetWeaponsDatX 4, SetUnitAbility 18 | 유닛 23종/157회, 무기 5종/16 | 7 (3줄은 적용 안 됨, 추측) |
| TPL | 0 (정의만) | | |

**전체 필드별 쓰기 수(상위, SetUnitAbility·래퍼 펼침)**: Size* 각 302, AdvFlag 276, DmgBase 246, DmgFactor 239, HP 236, Shield 235, RangeMax 228, Splash 225, AirWeapon 220, Cooldown 211, DamageType 211, Class 209, GroundWeapon 208, SeekRange 208, ObjectNum 206, ComputerAI 200, GroupFlag 198, SuppCost 198, UpgradeType 197, KillScore 196, StarEditFlag 185, TargetFlag 166, Playerable 147, MinCost 140, Reqptr 125 … (전체 목록 `coverage.py` 출력).

R1 의 "8맵 950회" 는 정의 줄·주석을 포함한 정규식 수다(TPL 89/3 은 정의 줄). 위 표가 실제 호출이다.

**대표 호출 모양**
1. `SetUnitsDatX(162,{AdvFlag={0x400200,0x480200},BdDimX=1,BdDimY=1})` — STEL `MapLogic\OnInit.lua:75`
2. `SetWeaponsDatX(1,{TargetFlag=0x020+1+2,DamageType=3,DmgBase=HMBaseAtk,DmgFactor=HMFactorAtk,Splash={5,10,15}})` — STEL `MapLogic\OnInit.lua:203`
3. `SetUnitAbility(21,18,3,17000,false,30,450,false,1,160,5,45000,"Kazansky",2000)` — RESV `Variables.lua:384` (위치 인자, 판마다 12~19개)
4. `SetUnitsDatX(UnitID,{ Flyer = false, Height = 4 })` — `theSeed\MapLogic\EnemyUnitStats.lua:77`
5. `SetWeaponsDat({},128,{DmgBase=65535,FlingyID=158,Splash={8,8,8},RemoveAfter=64},{preserved})` — UERE `Sans.lua:78` (조건부·매 프레임)
6. `SetUnitsDat2X(tesPatchT,o,{AdvFlag={4,4},Height=12})` — M2 `GunData.lua:1540` (보스 진입 1회, "모든 적 유닛을 공중으로")

## A.4 scdata 가 덮는 비율 (`coverage.py`)

| 기준 | Y | P | N | 합 | Y 비율 | Y+P |
|---|---:|---:|---:|---:|---:|---:|
| 필드 수 (정의 + raw 로만 쓰는 필드) | 98 | 4 | 12 | 114 | 86% | 89% |
| 실제 쓰인 필드 수 | 76 | 4 | 4 | 84 | 90% | 95% |
| **쓰기 수** | 6,182 | 506 | 187 | 6,875 | **89.9%** | **97.3%** |
| 호출 지점 수 (키 하나라도 N 이면 N) | 376 | 159 | 187 | 722 | 52.1% | 74.1% |

- P 대부분: AdvFlag `{값,마스크}` 276, ComputerAI 200, BdDimX/Y 30.
- N: Playerable 147, 플레이어별 업그레이드·테크 36, 기타 3, DamageRatio 1. 정의만 있고 N: Subunit2, AddonPlacement, InfestationUnit, SpecialAttack, GRPFile, Overlay 5종.
- **eudext 표에 넣을 것(= scdata 로 안 되는 것)**: `player_unit_enable`(0x57F27C), 플레이어별 업그레이드 최대/현재·테크 표 4~8종(주소 확정은 미확인), `damage_ratio`(주소 확인 후), `addon_placement`, `subunit2`, `infestation_unit`, `special_attack`, 이미지 overlay·GRP(요청 시). P 필드는 scdata 멤버의 주소를 쓰되 **마스크 쓰기**를 eudext 가 한다.

### A.4.1 scdata 멤버의 동작 (설계에 영향)

| 항목 | 내용 | 근거 |
|---|---|---|
| 상수 번호 | 주소를 `divmod(offset + 번호·stride, 4)` 로 상수 계산 | EP81 `scdata/offsetmap/member.py:158~160` |
| 쓰기 | 상수면 `DoActions(SetDeathsX(…))` = **그 자리 트리거 1개**(`DoActions` 는 preserved 트리거) | EP81 `memio/bwepdio.py:144~150`, `ctrlstru/basicstru.py:16~17` |
| 변수 번호 | stride 4 면 `EPD + 번호`, 아니면 곱셈·나눗셈 캐시를 그때 만든다. 번호 최대 < 1024 검사 | `member.py:161~189`, `epdoffsetmap.py:59~146` |
| `+=` (파이썬) | 읽기 → 변수 덧셈 → 쓰기(마스크에 걸려 wrap) | `member.py:134~145` |
| `+=` (epScript) | `iaddattr` → 마스크 Add 액션 1개 | `epdoffsetmap.py:228~231`, `bwepdio.py:222~230` |
| `-=` | `isubattr` = 음수 Add (wrap, 추측 — S8 확인) | `epdoffsetmap.py:239~243` |
| 포화 뺄셈 | `isubtractattr` 는 있지만 연산자에 연결 안 됨(TODO) | `epdoffsetmap.py:233~237` |
| 비트 멤버 | `.baseProperty.Hero = True` → 비트 하나 마스크 SetTo. `{값,마스크}` 한 번에 쓰는 API 없음 → `f_maskwrite_epd` | `enummember.py:172~191`, `bwepdio.py:381` |
| 메타데이터 | 클래스에서 `TrgUnit.maxHp` → 디스크립터. `.offset`, `.stride`, `.layout`, `.kind.size()` 를 읽을 수 있다 | `member.py:108~122, 130~139`, `memberkind.py:31~33` |
| 되돌리는 패치 | `f_dwpatch_epd(epd, value)`(dword 통째), `f_blockpatch_epd`, `f_unpatchall`(LIFO, 스택 8192). **최상위 export 없음** → `_compat` 경유. src 안에서 `f_unpatchall` 을 부르는 곳은 없다 | EP81 `eudlib/utilf/mempatch.py:15, 43, 66, 113` |
| datadumper | 0.81 에 같은 코드가 라이브러리로 있음(`_add_datadumper`, `_f_datadumper`) | EP81 `eudlib/utilf/datadumper.py:15~44` |

## A.5 원시 액션 규칙 (eudext 가 따라 할 것)

- 폭 1·2 필드는 **4바이트 경계로 내린 주소 + 시프트된 값 + 마스크**(CA:43497~43541 과 같게). 폭 4 이고 마스크가 없으면 `SetMemory`.
- 값은 TEP 키를 쓸 때만 TEP 변환(HP×256, SuppCost×2, Splash bool, Shield bool, Playerable 2)을 한다. scdata 이름을 쓰면 **원시 값**.

## A.6 EUD Editor 와 dataDumper, 선택 기준

| 항목 | 내용 | 근거 |
|---|---|---|
| EUDEditorDat.lua 형식 | `{정렬 주소, Add 차분}` + 주석 `-- dat:필드 #번호 (A -> B)`. 차분 = (새 값 − 원래 값) × 256^(바이트 위치). **Add** 인 이유: 맵 chk 의 UNIx 가 이미 바꾼 칸까지 똑같이 재현 | M2 `EUDEditorDat.lua:1~12, 15~` |
| 원래 형식 | EUD Editor 3 가 만든 `DataEditor.py` 의 `onPluginStart` 안 `DoActions([SetMemory(addr, Add, d)…])` | `DPS_eud\build\eudplibData\DataEditor.py:4~6` |
| 적용 | `EUDEditorInit()` 이 Add 1,182줄 + 정보창 함수 + 요구사항 풀을 `DoActions2(FP, Acts, 1)` 로 1회. 요구사항 오프셋 표는 매 프레임 | M2 `EUDEditorPort.lua:129~159`, `main.lua:117~118`; UERE `EUDEditorPort.lua:126~134`, `main.lua:81~82` |
| theSeed | 빌드 때 `theSeed.e3s` 를 직접 읽어 `SetMemoryX(SetTo, 값, 마스크)` 로 냄(원래 값이 e3s 에 없음). 우선순위 e3s → DataEditor.py 사본(Add) → 스냅숏. 결과는 `CtrigInitArr`. "Add 는 순서·중복 적용에 민감" | `theSeed\MapLogic\E3sDatReader.lua:1~75`, `EUDEditorDatPatch.lua:60~75, 415~419, 433~456` |
| dataDumper | eds `[dataDumper]` `파일 : 주소[, copy|unpatchable]` → `onPluginStart` 에서 기본 = 포인터를 `Db(파일)` 로 교체, `copy` = 포인터가 가리키는 버퍼에 덮어쓰기, `unpatchable` = `f_dwpatch_epd` | ED `plugins\dataDumper.py:14~58`, UPED `plugins\dataDumper.py` 같음 |
| dataDumper 쓰임 | 이 맵들은 **stat_txt.tbl 을 `0x6D5A30, copy`** 로 넣는 데만 씀. **dat 배열에는 안 씀**(dat 배열은 포인터가 아니라 고정 주소) | M2·UERE `eds_template.eds` |

**선택 기준 제안** (문서·docstring 에 적을 것)

| 경우 | 권장 | 이유 |
|---|---|---|
| 게임 내내 고정이고 **맵 CHK 로 표현되는 값**(유닛 HP·실드·아머·빌드 시간·비용·이름·무기 피해/보너스, 업그레이드·테크 비용, **플레이어별 생산 가능·업그레이드·테크**) | 맵 편집기(SCMDraft 의 유닛/업그레이드 설정 = CHK UNIx/UPGx/TECx/PUNI/UPGR/PTEC) | 트리거 0개. N 필드 1·2위를 흡수(추측, 인게임 확인 A.9-1) |
| 게임 내내 고정, CHK 로 안 되는 값(투사 방식, flingy, iscript, AI 주문, 크기, 특수 능력 …) | `datpatch` 시작 1회 **또는** EUD Editor — **한 필드의 출처는 하나만** | EUD Editor 는 Add 차분이라 다른 곳의 SetTo 와 섞이면 순서에 따라 값이 달라진다(M2 `EUDEditorDat.lua:9` 도 같은 경고) |
| EUD Editor 를 이미 쓰는 맵을 옮길 때 | `datpatch.from_eud_editor(표)` 로 **같은 Add 목록을 같은 순서**로 낸 뒤, 새 값은 SetTo 로 그 뒤에 | M2 방식 그대로 |
| 게임이 되돌리는 칸(요구사항 오프셋 표 등) | `every_frame` | SEED `:10` 주석, M2 `EUDEditorPort.lua:144~159` |
| 페이즈·모드에 따라 바뀌는 값 | `datpatch.actions(...)` 를 조건 블록에 / 되돌려야 하면 `temporary()` | UERE `Sans.lua`, M2 보스 |
| 파일 통째(tbl 등, 포인터로 가리키는 자료) | dataDumper(eds) 또는 0.81 datadumper | dat 배열에는 해당 없음 |

## A.7 `eudext.datpatch` API 확정안 (DESIGN 4.16 초안을 고침)

```python
from eudext import datpatch as dat
from eudplib import TrgUnit, Weapon, Flingy          # 멤버 이름은 scdata 를 따른다

# ── 시작 시 1회 목록 (컴파일 시점 선언, 번호·값은 상수) ─────────────────
dat.unit(208).set(maxHp=5000 * 256, elevation=20, groundWeapon=127)
dat.unit("Terran Marine").set(mineralCost=75, armor=1)
dat.unit(208).flags(Flyer=True, Invincible=True)          # baseProperty 비트 (이름은 scdata)
dat.unit(162).mask("baseProperty", 0x400200, 0x480200)     # AdvFlag {값, 마스크}
dat.unit(162).set(buildingDimX=1, buildingDimY=1)          # P 필드: eudext 가 마스크 쓰기
dat.weapon(127).set(damage=60000, behavior=9, removeAfter=64)
dat.weapon(1).splash(7, 14, 21)                            # explosionType=3 + 반경 3개
dat.flingy(106).set(topSpeed=0xFFFFE0BF, acceleration=8000)
dat.upgrade(u).set(...); dat.sprite(s).set(image=…); dat.image(i).set(iscript=…)
dat.player_unit_enable(unit, players=range(5), value=1)    # N: 0x57F27C (Playerable)
dat.player_upgrade_max(p, upgrade, level)                  # N: 주소 확정 뒤

# TEP 이식 층 (키 이름·변환을 TEP 그대로)
dat.tep.SetUnitsDatX(162, {"AdvFlag": (0x400200, 0x480200), "BdDimX": 1, "BdDimY": 1})
dat.tep.SetWeaponsDatX(1, {"DmgBase": 75, "Splash": (7, 14, 21)})
dat.tep.SetUnitAbility(...)                                 # TPL 18인자 판만. 다른 판은 kw 로
dat.from_eud_editor(r"…\EUDEditorDat.lua")                 # {addr, add} 목록 → Add 액션, 순서 유지

# ── 내보내기 ───────────────────────────────────────────────
# 기본: import 한 모듈이 EUDOnStart 에 등록 → 64액션씩 트리거로 1회 적용 (선언 순서)
dat.every_frame().unit(u).set(requirementOffset=…)         # 매 프레임 목록 (Prsv)
acts = dat.actions(lambda d: d.weapon(128).set(damage=65535, flingy=158))   # 액션 목록만 (조건 블록용)
with dat.temporary():                                       # f_dwpatch_epd … f_unpatchall (dword 단위)
    dat.now.weapon(w).set(damage=v)                         # 변수 값·번호 허용, 런타임 즉시
dat.field("units", "maxHp")    # -> Field(base=0x662350, size=4, stride=4, count=228, member=TrgUnit.maxHp)
dat.addr("weapons", "damage", 127)   # 상수 -> (정렬 주소, 시프트, 마스크); 변수 -> (epd, subp)
```

**의미**
- 필드 이름은 **scdata 멤버 이름이 1순위**. eudext 표는 `{이름: (dat, base, size, stride, count, scdata 멤버 또는 None)}` 로 두고, **base·size·stride 는 scdata 디스크립터에서 읽어** 중복 기재를 피한다(`TrgUnit.maxHp.offset` 등). scdata 에 없는 필드(A.4)만 상수로 적는다.
- 상수 번호·상수 값 → **원시 액션 목록**(A.5 규칙) → 64개씩 트리거. scdata 대입문을 그대로 쓰지 않는다(한 줄 = 트리거 1개).
- 변수 번호·값(`dat.now`) → scdata 멤버 쓰기를 그대로 부른다(런타임 즉시, 비용은 scdata 몫).
- 같은 필드를 두 번 선언하면 뒤의 값이 이긴다. `debug=True` 면 컴파일 경고.
- `dat.tep` 은 TEP 키와 변환을 그대로 재현한다: HP×256, SuppCost×2, `Shield=bool`, `Splash=bool/표`, `Playerable=bool/2`(**TPL 판: P1~5**; `players=` 로 바꿀 수 있음), `AdvFlag=(값, 마스크)`. **`WhatSndInit`/`WhatSndEnd` 는 TEP 주소(반대)를 그대로 쓰고 경고**, `Reqptr` 는 `reqptr="ignore"`(TPL 동작, 기본) / `"once"` / `"every_frame"` 선택.
- 번호 범위(유닛 < 228, 무기 < 130, Yes/Pissed 소리 < 106, Addon/Infestation 106~)는 컴파일 시점 `EPError`(한국어).
- `temporary()` 는 dword 통째 패치라 폭 1·2 필드는 "현재 dword 읽기 → 바꿀 바이트만 합치기 → `f_dwpatch_epd`" 로 한다. 블록을 나가거나 호출자가 `dat.unpatch_all()` 을 부르면 되돌린다(`f_unpatchall`). 같은 프레임 안에서 쓰는 용도(eudplib 관례)이며, 프레임을 넘기는 되돌림은 호출자가 시점을 정한다.
- **CP**: 바꾸지 않음. **로컬**: 공유(모든 값이 게임 상태).
- **비용**: 시작 목록 N 액션 → `ceil(N/64)` 트리거(1회). 호출 자리 0. `every_frame` 은 매 프레임 `ceil(N/64)`.

## A.8 시험 기대값

| 시험 | 기대 (`dat_expect.py`) |
|---|---|
| `tep.SetUnitsDatX(162, {AdvFlag=(0x400200,0x480200), BdDimX=1, BdDimY=1})` | `SetMemoryX(0x664308, SetTo, 0x400200, 0x480200)`, `SetMemoryX(0x662AE8, SetTo, 0x1, 0xFFFF)`, `SetMemoryX(0x662AE8, SetTo, 0x10000, 0xFFFF0000)` |
| `tep` HP=5000, 유닛 208 | `SetMemory(0x662690, SetTo, 0x138800)` |
| `tep` SuppCost=2, 유닛 0 / 1 | `SetMemoryX(0x663CE8, SetTo, 0x4, 0xFF)` / `SetMemoryX(0x663CE8, SetTo, 0x400, 0xFF00)` |
| MinCost=75, 유닛 3 | `SetMemoryX(0x66388C, SetTo, 0x4B0000, 0xFFFF0000)` |
| SizeL=10, SizeU=12, SizeR=11, 유닛 3 | `SetMemoryX(0x6617E0, SetTo, 0xA, 0xFFFF)`, `SetMemoryX(0x6617E0, SetTo, 0xC0000, 0xFFFF0000)`, `SetMemoryX(0x6617E4, SetTo, 0xB, 0xFFFF)` |
| `tep` Shield=false, 유닛 3 | `SetMemoryX(0x6647B0, SetTo, 0x0, 0xFF000000)`, `SetMemoryX(0x660E04, SetTo, 0x0, 0xFFFF0000)` |
| `tep` WhatSndInit=5, 유닛 3 | `SetMemoryX(0x662BF4, SetTo, 0x50000, 0xFFFF0000)` + 경고 1건 |
| scdata `whatSoundStart=5`, 유닛 3 | `SetMemoryX(0x65FFB4, SetTo, 0x50000, 0xFFFF0000)` |
| `tep` DmgBase=75, 무기 1 | `SetMemoryX(0x656EB0, SetTo, 0x4B0000, 0xFFFF0000)` |
| `tep` Splash=(7,14,21), 무기 1 | `SetMemoryX(0x6566F8, SetTo, 0x300, 0xFF00)`, `SetMemoryX(0x656888, SetTo, 0x70000, 0xFFFF0000)`, `SetMemoryX(0x6570C8, SetTo, 0xE0000, 0xFFFF0000)`, `SetMemoryX(0x657780, SetTo, 0x150000, 0xFFFF0000)` |
| RemoveAfter=64, 무기 128 / FlingyID=158, 무기 128 | `SetMemoryX(0x6570C0, SetTo, 0x40, 0xFF)` / `SetMemory(0x656EA8, SetTo, 0x9E)` |
| flingy 106 topSpeed=8000 | `SetMemory(0x6CA0A0, SetTo, 0x1F40)` |
| `player_unit_enable(5, players=[0], 1)` / `[7], 0` | `SetMemoryX(0x57F280, SetTo, 0x100, 0xFF00)` / `SetMemoryX(0x57F8BC, SetTo, 0x0, 0xFF00)` |
| `tep` Reqptr (기본) | 액션 0개 |
| 모르는 키 / 유닛 228 / YesInit 에 유닛 106 | `EPError` |
| 주소표 스냅숏 | eudext 표의 (base, size, stride) 가 A.2 표 및 **scdata 디스크립터**(`TrgUnit.maxHp.offset == 0x662350`, `.kind.size() == 4` …)와 전부 같다 |
| 트리거 수 | 액션 1,182개 → 19 트리거, 773개 → 13 트리거 |
| `from_eud_editor` | M2 `EUDEditorDat.lua` 의 1,182개가 같은 순서의 `SetMemory(addr, Add, d)` 로 |
| 에뮬레이터 | 시작 목록 적용 뒤 메모리 = 기대 값. `temporary()` 블록 뒤 원래 값 복구(dword·바이트 필드 둘 다) |

## A.9 인게임 확인 항목

1. 맵 CHK(PUNI/UPGR/PTEC, UNIx)로 넣은 값과 트리거 패치 결과가 게임 시작 뒤 같은 메모리 값인지(Playerable·업그레이드 최대 레벨).
2. 시작 1회 목록이 적용되는 사이클: 맵에 미리 놓인 유닛(최대 체력 변경 전 생성)의 체력·실드가 어떻게 되는지.
3. `every_frame` 이 필요한 필드 목록(요구사항 오프셋 외에 게임이 되돌리는 칸이 있는지).
4. 피해 배율 표 주소(0x515B88 vs 0x515B84).
5. 마스크 Add/Subtract 의 wrap/포화(S8 과 공유).
6. `temporary()` 를 프레임을 넘겨 유지했을 때 저장·불러오기·리플레이 문제 없음.

## A.10 함정

- **TEP 이식 시 `WhatSndInit`/`WhatSndEnd` 반대**(A.2.1). 이름을 scdata 로 바꾸면 값이 뒤바뀐다.
- **`Reqptr` 가 TPL 계열에서 무시**된다. 이식하면서 "적용" 으로 바꾸면 기존 맵 동작이 바뀐다.
- TPL `PatchInsert` 는 헬퍼를 한 번 부른 뒤에야 전역에 생긴다. BRZ `Interface.lua:139~141` 은 큐가 소비된 뒤(`main.lua:262` 뒤 `:268`)에 쌓여 적용되지 않는 것으로 보인다(추측).
- EUD Editor Add 차분과 SetTo 를 한 필드에 섞으면 순서에 따라 결과가 달라진다.
- scdata 대입을 시작 패치 수백 줄에 그대로 쓰면 트리거 수백 개.
- `f_dwpatch_epd` 스택 8192칸 공유(eudplib 내부도 쓸 수 있음, 추측).
- `SetUnitAbility` 는 판마다 인자 수·순서가 다르다(12/14/18/19). 이식 층은 TPL 판만 위치 인자로 받는다.
- 플레이어 표 주소 이름(업그레이드·테크)은 확인 전. 확정 전에는 `player_upgrade_max` 등을 구현하지 않는다.

---

# B. BGM

## B.1 정본 정의와 판

| 함수 | 정본 | 서명·기본값 | 비고 |
|---|---|---|---|
| `IBGM_EPD` (로컬형, 인자 5) | TPL `func.lua:843~953` | `(PlayerID, TargetPlayer, Input, WAVData, AlertWav=nil)`. `WAVData = {{번호, "파일" 또는 {"조각1",…}, 길이ms}, …}`. `Input` = 주소(숫자) / V / CtrigX | `return Arr[2]`(로컬 ΔT) `:952`. theSeed `Engine\func.lua:1334`, STEL `Engine\func.lua:843` 은 TPL 과 md5 동일(조사 에이전트) |
| `ConvertTime`, `Play_BGMSystem` | TPL `BGMEngine.lua:1~3, 6~10` | `ConvertTime(분,초,ms)`, `Play_BGMSystem(Mode, TracksByMode)` → 전역 `Dt` | STEL 사본과 차이 없음 |
| `AddBGM` | LIB `:765~785` | `(BGMTypeNum, WavFile, Value_ms, StyleFlag={레벨최소,최대})` → 전역 `BGMArr` 에 추가, 번호 반환 | 상수만(`PushErrorMsg`) |
| `Install_BGMSystem` | LIB `:787~943` | `(Player, MaxPlayers, BGMTypeV, DeathUnit, ObConFlag, BGMSkipSEFlag, ObPlayers={P9..P12})` | 한 번만(`InitBGMP` 검사 `:789~793`). StyleFlag 가 있으면 전역 `LevelT` 필요(`:820`) |
| `NormalTurboSet` | LIB `:946~957` | `(Player, DeathUnitID)` | 전역 `NTCond`/`NTCond2` 정의 |
| `IBGM_EPD` (인자 4, 공유형 타이머) | LIB `:960~990` | `(Player, MaxPlayer, Option_NT, BGMDeathsT)` | **로컬 ΔT 를 공유 데스값에서 뺀다**(`:981~989`) — 디싱크 위험. EPDX 가 고친 판 |
| `IBGM_EPDX` (공유형 타이머) | UERE `func.lua:431~460` / M2 `func.lua:316~351` | UERE `(Player, MaxPlayer, MSQC_Recives, Option_NT)`(데스 유닛 12 고정), M2 는 `BGMDeathsT` 추가 | 맵마다 정의 |
| CtrigAsm 원본 `IBGM_EPD` | CA:81934~81993 | 조각·끄기·LocalPlayerID 없음, CP 복원 없음, 반환 없음 | 로드 순서(CA → LIB → 맵, UERE `main.lua:44~58`)상 뒤 정의가 덮는다 |
| 판 차이 | BRZ `func.lua:242`, MEME `function.lua:186` | TPL `:937` 의 `DoActionsX(FP, Act1)` 가 **없음** → 등록 안 된 번호나 끈 플레이어일 때 요청 칸이 안 지워짐 | RESV `func.lua:1044` 는 빈 줄 차이 |

## B.2 로컬형 런타임 (TPL)

| 단계 | 동작 | 근거 |
|---|---|---|
| 경과 시간 | `Arr[1] ← read(0x51CE8C)`, `CNeg` → 실제 시각 ms, `f_Diff` → `Arr[2]`(지난 사이클 이후 ms), `CSub(Arr[3], Arr[2])`(0 에서 멈춤) | `func.lua:847~853` |
| 요청 칸 | `Input ≥ 1` (주소면 `Memory`, V 면 `NVar`, CtrigX) | `:856~865` |
| 재생 조건 | `Arr[3](Delay) == 0` 이고 요청 ≥ 1 | `:867` |
| 한 곡 | **곡 × 대상 플레이어마다 트리거 1개**: `번호 일치 + LocalPlayerID(Pl) + DeathsX(k, Exactly, 0, 12, 0xFF000000)`(끔 비트) → `요청 칸 ← 0; SetCp(Pl); PlayWAV×2; SetCp(PlayerID); Delay += 길이` | `:910~934` |
| 관전자 | 대상 P9~P12 를 128~131 로 바꿔 `LocalPlayerID`·`SetCp` 에 씀 | `:880~883, 911~915` |
| 조각 표 | 대상마다 Ccode 카운터 `WAVs[j]`. 요청 때 카운터 번째 조각 하나 재생 후 +1, 끝이면 0. 길이는 공통 `v[3]` | `:876~908` |
| 요청 지우기 | 번호 분기 뒤 조건 없이 `Act1` | `:937` |
| 재생 중 요청 | 요청을 지우고 `AlertWav` 가 있으면 대상 전원에게(`CopyCpActionX`) | `:938~949` |
| 정지·반복 | 없음. 반복은 호출자가 다시 요청 | — |
| 로컬/공유 | `Arr[1..3]` 은 PC 마다 다르다(소리만 좌우하므로 안전). **반환값은 로컬** → RESV 가 `TSetDeathsX(i, Subtract, Dt, 12, 0xFFFFFF)` 로 공유 데스값에서 뺀다(RESV `Interface.lua:10, 1615`) → 그 값을 공유 로직이 읽으면 디싱크(추측) | |
| 비용 | 트리거 = 곡 수 × 대상 수(+조각). RESV 52×12 = 624, STEL 44×12, theSeed 35×11 | RESV `Interface.lua:10~`, 조사 에이전트 |

## B.3 공유형 런타임 (`Install_BGMSystem` + `IBGM_EPDX`)

| 단계 | 동작 | 근거 |
|---|---|---|
| 경과 시간 보내기 | 각 PC 가 로컬 ΔT 를 `0x58F500` 에 쓴다 → MSQC `val` 이 데스(i, 180)로 동기화 | UERE `func.lua:438`, `eds_template.eds`(`val, 0x58F500 : 180`) |
| 받기 | "상위 플레이어" 분기에서 `Dt ← 데스(방장, 180)` | UERE `Operator.lua:7` |
| 타이머 감소 | `Dt ≤ 2500` 일 때만 `IBGM_EPDX(FP, 6, Dt, …)`. 사람 플레이어마다 `SetDeathsX(i, Subtract, Dt, 12, 0xFFFFFF)`, FP(관전자용)도, P9~P12 는 0 | UERE `PreservedTrig.lua:59~61`, `func.lua:456~459`; M2 는 데스 유닛 {12, 14} `func.lua:340~350` |
| 곡 표 | `BGMArr[i] = {번호, 파일, ms, [{레벨최소, 최대}]}` — 같은 번호를 레벨별로 여러 줄 | LIB `:777~783`, UERE `func.lua:220~245` |
| 재생 | 요청 ≥ 1 이면 CP 를 0..MaxPlayers 로 돌며 `Deaths(CP, AtMost, 0, DeathUnit)`(**끔 비트 포함 dword 가 0** = 재생 중 아님·끄지 않음)일 때 **곡마다 트리거 1개**: `PlayWAV×2`, `SetDeathsX(CP, SetTo, ms, DeathUnit, 0xFFFFFF)` | LIB `:813~837` |
| 재생 중·끔 | 그 플레이어에게 `BGM_Skip.ogg`×3(`BGMSkipSEFlag` 가 nil 일 때) | LIB `:838~850` |
| 관전자 | 루프 뒤 FP 데스값으로 판정해 `RotatePlayer({PlayWAVX…}, ObPlayers)`. `ObConFlag` 면 관전자 128~131 각각 **로컬**로 Delete 키(`0x596A44 == 0x10000`)로 끔 토글(로컬 Ccode) | LIB `:794~811, 854~940` |
| 요청 지우기 | 끝에 `BGMTypeV ← 0` | LIB `:941` |
| 예약·반복 | UERE: `ReserveBGM` 을 두고 **전원 타이머 0** 일 때 적용, 보스가 살아 있으면 같은 곡 재예약 | UERE `func.lua:251~258` |
| 플레이어별 끄기 | 데스(i, 12) **윗바이트**. UERE 는 유닛 22 명령(공유 입력)으로 토글 | UERE `Player_interface.lua:522~534` |
| CP | 루프 뒤 `CAdd(0x6509B0, InitBGMP)` → CP = MaxPlayers+1+FP(UERE 14). 뒤 판정은 `Deaths(InitBGMP, …)` 라 영향 없어 보이나 의도 불명(추측: 버그) | LIB `:851~854` |
| 로컬/공유 | 타이머·요청·끔 비트는 공유, 모두 같은 Dt 로 갱신. `PlayWAV` 만 로컬 효과. **조각 번호로 보스 패턴을 맞추는 맵**이 있어 공유 시간이 필요하다(UERE `Destr0yer.lua` FP 데스 439 = 조각 번호) | UERE `Destr0yer.lua:52~55, 252~300` |
| 비용 | 곡 수 × (플레이어 루프 1 + 관전자 2~3) 트리거 | |

## B.4 `NormalTurboSet` (턴 속도 도우미)

- 데스(Player, 214)를 사이클마다 +1, 2 이상이면 0 → 0/1 이 번갈아 나온다(LIB `:948~949`). `NTCond()` = 1, `NTCond2()` = 0 인 사이클.
- `IBGM_EPDX` 의 `Option_NT = {A, B}`: 0 인 사이클에 `A ← Dt`, 1 인 사이클에 `B ← Dt + A` → **2사이클 동안 흐른 ms**(UERE `func.lua:442~453`).
- 쓰임: "일반 속도(2사이클에 1번)" 로 도는 보스 패턴 대기(UERE `DemonLanterns.lua:4`, `DemonicEmperor.lua:624`). **곡 길이 보정과 무관.** 호출 RESV `main.lua:47`, UERE `main.lua:89`, STEL `main.lua:77`, theSeed `main.lua:158`(조사 에이전트). `Option_NT` 는 UERE 만.
- **배속 보정은 BGM 에 없다**: 경과 시간이 실제 시간이므로 게임 속도와 무관하다. euddraft `soundlooper` 는 게임 속도·지연 설정(`0x51CE84/88`, `0x5124F0`)으로 오차 보정표를 쓴다(UPED `lib\soundlooper.py:324~360`) — 조각 사이 틈 보정용.

## B.5 조각 이어 재생 (엔진 밖, 손으로 짬)

| 맵 | 조각 | 방식 | 근거 |
|---|---|---|---|
| M2 상시 BGM | `BGM001~364.ogg`, 2000ms 고정 | 플레이어 i(0~3) × 조각 j 트리거: `데스(i,13)==j`, `데스(i,14)==0` → `SetCp(i); PlayWAV; 데스(i,14) += 2000; 데스(i,13) += 1` → **364×4 = 1,456 트리거** | M2 `System.lua:117~150` |
| M2 190 건작 | `ikasu001~148`, 1263ms | 건작 타이머 `Gun_Line(8) ≥ (i−1)·1263` 에서 1회 | M2 `GunData.lua:2396~2406` |
| UERE Destr0yer | `LV10_001~272`, 666ms | FP 데스 439 = 조각 번호, 데스 12 = 타이머. 조각 번호로 패턴·가사 동기화 | UERE `Destr0yer.lua:43~55, 252~300` |
| MSF_Memory | 157개 1000ms, 109개 2000ms | 데스 440/441 | `MS\MSF_Memory\Main.lua:15604~15640, 16121~16160` |

- 조각 길이를 곡마다 고정해 적는다(실측 BGM364 = 891.6ms 인데 2000 — 마지막 조각 뒤 쉼).
- eudext 는 이것을 **1급 기능**으로: `bgm.chunks(...)` 가 조각마다 실측 길이를 표로 두고, 재생 루프가 "남은 시간 0 → 다음 조각" 을 곡 수와 무관한 트리거로 처리한다. 현재 조각 번호를 `player.chunk(p)` 로 읽어 패턴 동기화에 쓴다.

## B.6 파일 삽입

| 항목 | 내용 | 근거 |
|---|---|---|
| TEP | 입력 scx 의 `scenario.chk` 만 바꾼다. 소리 코드 없음 | `TEP3.0_Headless_Compiler\headless\host\mpq.h:10~34`(조사 에이전트) |
| 원래 | SCMDraft 로 맵에 소리를 넣음 | M2 `tools\split_map.py:7~13` |
| 지금 | 맵별 euddraft 플러그인이 `ED\<맵>_BGM\` 의 `.ogg/.wav` 전부를 `MPQAddFile("staredit\\wav\\"+파일명, bytes)` | M2 `MSF_Memory2_BGMInput.py:25~39`, UERE `MSF_UE_RE_BGMInput.py`, theSeed·STEL·RESV·MEME 판(조사 에이전트) |
| 호출 | eds `[<모듈>.py]` + `Path :` 설정. theSeed 류는 `<맵>_Plugin.py` 를 생성해 `onPluginStart` 에서 | M2 `eds_template.eds` 끝, `theSeed\MapLogic\EUDEditorEdsGen.lua:74~101`(조사 에이전트) |
| 이름 | `staredit\wav\<파일명>` = 트리거 `PlayWAV` 문자열 | |
| 중복 | eudplib 는 입력 맵 listfile 이름을 이미 있는 것으로 등록하고 같은 이름 추가를 막는다 → 음원을 기본 맵에서 빼 둔다 | EP81 `maprw/mpqadd.py:16~49`, `split_map.py:69~125` |
| 길이 | 전부 수동 | |
| 규모 | M2 641개 73MB, UERE 335개 58MB, theSeed 56개 41MB, STEL 63개 80MB, RESV 127개 65MB, MEME 62개 43MB | 조사 에이전트 실측 |
| freeze | 파일 수는 freeze 블록 테이블에 개당 16B(블록 테이블 = 32 + 압축 chk + 해시 + (파일수+2)·16, 한도 4MiB — 사용자 메모 `theseed-freeze-limit`). 641개 ≈ 10KB | |

**길이 측정 실험** (`bgm\measure_len.py`, struct 만: Ogg = 마지막 페이지 granule ÷ 표본율, WAV = data 크기 ÷ byte rate)

| 파일 | 실측 ms | 맵에 적힌 값 | 적힌 곳 |
|---|---:|---:|---|
| GBGM1.ogg | 33095.9 | 33000 | M2 `System.lua:100` |
| finale_start_op.ogg | 150967.8 | 152000 | M2 `System.lua:99` |
| BGM001 / BGM364 | 2000.0 / 891.6 | 2000 / 2000 | M2 `System.lua:117~142` |
| ikasu001 | 1263.2 | 1263 | M2 `GunData.lua:2405` |
| LV10_001 | 666.7 | 666 | UERE `Destr0yer.lua:55` |
| GRAVITY_OP | 95635.4 | 94000 | UERE `func.lua:220` |
| BGM_167 | 60031.2 | 55000 | `theSeed\MapConfig\Buildings.lua:3141` |

- 폴더 전체: M2 640/641, UERE 331/335, theSeed 56/56 측정 성공. 실패 5개(`button3.wav`, `H-005.wav`, `H-020.wav`, `WARNING.wav` 등)는 **내용이 OggS** → 형식은 확장자가 아니라 앞 4바이트로 판별.
- 맵은 길이를 **실제보다 짧게** 적는 경향(곡 사이 겹침, theSeed `Buildings.lua:3096~3101` 주석) → 수동 길이와 `trim_ms` 를 둘 다 둔다.

## B.7 사용 모양·빈도

| 맵 | 모양 | 곡·조각 | 근거 |
|---|---|---|---|
| M2 | `AddBGM(2,"staredit\\wav\\GBGM1.ogg",33*1000)` ×16, `Install_BGMSystem(FP,3,BGMType,12,1,1,ObPlayers)`, `IBGM_EPDX(FP,3,Dt,nil,{12,14})` | 16곡 + 조각 364 + 148 | M2 `System.lua:99~115`, `main.lua:156` |
| UERE | `AddBGM(2,"staredit\\wav\\BGM1_1.ogg",42*1000,{1,2})`(레벨별), `Install_BGMSystem(FP,6,BGMTypeV,12,1)`, `IBGM_EPDX(FP,6,Dt,{Dt_NT2,Dt_NT})` | 28줄(번호 13) + 조각 272 | UERE `func.lua:220~259`, `PreservedTrig.lua:61` |
| RESV | `Dt = IBGM_EPD(FP,{P1,…,P12},BGMType,{{1,"staredit\\wav\\BGM_OP.ogg",96*1000},…})` | 52곡 | RESV `Interface.lua:10~` |
| BRZ | `{2,{"…BGM1_1.ogg","…BGM1_2.ogg"},45*1000}` | 5곡(조각 2개짜리 3) | BRZ `Interface.lua:25~31` |
| theSeed | `IBGM_EPD(FP, HumanPlayers, BGMType, WAVData, AlertWav)` (표는 건물별 설정에서 생성) | 35곡 × 11 | `theSeed\MapLogic\GunBGM.lua:70~91` |
| STEL | `Play_BGMSystem(Stella_BGM_Mode, BGMTracksByMode)` | 모드별 44곡 | STEL `MapLogic\System.lua:3`, `MapConfig\BGM.lua`(조사 에이전트) |

R1 집계(주요 맵): `AddBGM` 44, `IBGM_EPD` 5, `NormalTurboSet` 4, `Install_BGMSystem` 2, `IBGM_EPDX` 2 (7맵 57).

## B.8 대체 수단

| 수단 | 하는 일 | 한계 | 근거 |
|---|---|---|---|
| euddraft `bgmplayer.py` (ED 판) | `[bgmplayer] path, length(초)`. 파일 하나를 MPQ 이름 `"bgm"` 으로, `0xFFFFFFFF − read(0x51CE8C)` 타이머, 다 되면 로컬 CP 로 `PlayWAV("bgm")` 무한 반복. 타이머 −42ms | 곡 1개, 정지·전환·끄기·플레이어별 없음, 길이 수동, `MPQAddFile` 을 `beforeTriggerExec` 안에서 부름 | ED `plugins\bgmplayer.py:7~60` |
| 최신판 `bgmplayer.py` | 같음 + 모르는 설정 키 경고, `with open` | 같음 | UPED `plugins\bgmplayer.py:10~18, 56~57`(조사 에이전트) |
| euddraft `lib\soundlooper.py` | **ogg 길이 자동 측정**(tinytag 내장), `파일명0~999.ogg` 를 인트로/반복/마지막으로 루프, `play/pause/resume/toggle`, 속도별 오차 보정, 조각 재생은 `EUDSwitch` 로 조각마다 `PlayWAV`(`PlaySoundWorkaround`) | MPQ 이름을 임의 5자+3자리로 바꿈, 로컬 1명 기준, 관전자·끄기·공유 시간 없음 | UPED `lib\soundlooper.py:242~294, 324~383, 392~` |
| EUD Editor 3 BGMPlayer (DPS_eud 생성물) | `IsUserCP` 일 때 2220ms 마다 다음 조각, 조각 이름을 StringBuffer 에 써서 재생 | 문자열 내용 수정에 기댐 | `DPS_eud\build\eudplibData\TriggerEditor\TriggerEditor\BGMPlayer.eps:97~129`(조사 에이전트, 읽기만) |
| eudplib 0.81 `MPQAddFile(fname, path_or_content, is_wav=False)` | **경로 문자열을 받는다**(임시 파일 없이) | 이름 중복 assert | EP81 `maprw/mpqadd.py:52~81` |
| eudplib 0.81 `MPQAddWave(fname, path_or_content)` | `MPQAddFile(…, True)` | **`is_wav` 는 저장만 하고 쓰지 않는다** — `_update_mpq` 가 항상 `mpqw.add_file(fname, path)`. 0.76.14 는 `(fname, content)` + `PutWave` | EP81 `mpqadd.py:84~92, 95~130`, R3 4.1 |
| 소리 길이 API | 0.81 에 없음 | → eudext 가 struct 로 측정 | 조사 에이전트 검색 |
| `PlayWAVAll(path)` | CP 를 로컬 사용자로 바꾸고 `PlayWAV`(관전자 포함) | **CP 를 되돌리지 않는다** → 뒤에 `f_setcurpl2cpcache` 필요(DESIGN 3.6) | EP81 `eudlib/utilf/userpl.py:35~50` |
| `EUDPlayerLoop` | 0~7 만 | 관전자 제외 | EP81 `eudlib/utilf/pexist.py:124~` |

## B.9 `eudext.bgm` API 확정안 (DESIGN 4.17 초안을 고침)

```python
from eudext import bgm, sync, players as pl

# ── 컴파일 시점: 곡 표 ─────────────────────────────
bgm.set_dir(r"C:\euddraft0.9.2.0\MSF_UE_RE_BGM")          # 상대 경로 기준 (선택)
OP   = bgm.track("GRAVITY_OP.ogg")                          # MPQAddWave("staredit\\wav\\GRAVITY_OP.ogg", 절대 경로), 길이 자동
BOSS = bgm.track("SBoss.ogg", length_ms=368000)             # 수동 길이 (기존 맵 값 이식)
ED   = bgm.track("finale.ogg", trim_ms=1000)                # 자동 길이 − 1000
LV10 = bgm.chunks("LV10_{:03d}.ogg", range(1, 273))         # 조각 이어 재생, 조각마다 실측 길이
ROT  = bgm.rotation(["BGM1_1.ogg", "BGM1_2.ogg"], length_ms=45000)   # TPL 조각 표 (요청마다 돌아가며)
# 이름 규칙: 기본 "staredit\\wav\\<파일명>" (기존 맵 PlayWAV 문자열과 같음). mpq_name= 로 바꿀 수 있음

# ── 런타임 ──────────────────────────────────────────
bus = sync.Bus(transport="msqc")
player = bgm.Player(
    mode="synced",                   # "local" | "synced"
    targets=pl.humans(),             # 컴파일 시점 목록 또는 "all" (관전자 포함)
    elapsed=bus.value(bgm.clock.local_dt(), latch=True),   # synced 전용: 방장 PC 경과 ms (UERE 방식)
    max_elapsed=2500,                # 이보다 크면 그 사이클 무시 (UERE PreservedTrig.lua:60)
    busy="drop",                     # "drop" | "replace" | "queue" (UERE ReserveBGM)
    busy_sound=None,                 # 예 "staredit\\wav\\BGM_Skip.ogg"
    observers=True,                  # 관전자에게 FP 몫 타이머로 재생
    observer_toggle_key="DELETE",    # 관전자 로컬 끄기 (None = 없음)
    lead_ms=0,                       # 타이머 보정 (bgmplayer 는 −42)
)
player.request(BOSS)                 # 공유 요청 (전원)
player.request(BOSS, p)              # 한 플레이어
player.stop(p=None)                  # 남은 시간 0, 조각 진행 중지
player.loop(BOSS)                    # 끝나면 같은 곡 다시
player.mute(p, True)                 # 공유 끔 비트 (공유 입력으로만 바꿀 것)
player.is_playing(p)                 # Condition
player.current(p); player.chunk(p)   # 곡 번호, 조각 번호 (synced 에서만 공유 안전)
player.tick()                        # 매 사이클 1회

# ── 시계 (NormalTurboSet 대체) ───────────────────────
bgm.clock.local_dt()                 # 로컬 경과 ms (LocalValue — 공유 로직에 쓰면 안 됨)
bgm.clock.half()                     # 0/1 번갈아 나오는 Condition
bgm.clock.dt2(elapsed)               # 2사이클 합 (동기화된 값을 넣을 것)
```

**의미**
- 곡 표는 `EUDArray` 두 개(문자열 번호, 길이 ms) + 조각 곡의 (시작 칸, 개수). 재생 본문은 **곡 수·대상 수와 무관한 1벌**. `PlayWAV` 문자열은 두 방식 중 구현 때 고른다.
  1. `EUDSwitch(칸 번호)` 로 칸마다 `PlayWAV` 트리거 1개(soundlooper 방식, 확실하지만 곡·조각 수만큼 트리거).
  2. `PlayWAV` 액션의 문자열 칸을 런타임에 바꿔 쓰기(트리거 1개). **인게임 확인(B.11-1) 전에는 쓰지 않는다.**
- 소리는 **로컬 사용자에게만** 낸다: `f_getuserplayerid()` 로 CP 를 잠깐 바꾸고 `f_setcurpl2cpcache()` 로 복구(3.6). "로컬 사용자가 targets 에 있는가" 판정 1회.
- `local` 모드: 남은 시간·조각 번호는 로컬 변수. 요청 칸만 공유. 노출하는 값은 `LocalValue` 표식(3.7).
- `synced` 모드: 남은 시간·조각 번호·끔 비트를 플레이어별 `EUDArray`(8칸 + 관전자용 1칸)에 둔다(데스값 대신 → 데스 유닛 예약 불필요). 감소량은 `elapsed`(동기화 값)만 쓴다. 끔 비트는 타이머와 **다른 칸**(B.12).
- 재생 중 요청: `drop`(TPL·LIB 기본), `replace`, `queue`(전원 끝나면 적용, UERE).
- 레벨별 곡(UERE `StyleFlag`)은 API 에 넣지 않는다 — 호출자가 조건으로 곡을 골라 `request`.
- 파일 넣기는 `bgm.track`/`chunks` 가 `MPQAddWave(이름, 절대 경로)` 를 부른다. 형식은 앞 4바이트(`OggS`/`RIFF`). 길이는 **내림 정수 ms**. 번들 파이썬 `wave` 모듈에 기대지 않는다.
- **비용 목표**: 재생 본문 ≤ 40 트리거(+ 방식 1 이면 칸 수), `tick` 매 사이클 ≤ 10 트리거. 기존 RESV 624, M2 상시 BGM 1,456 대비.
- **CP**: 바꾸지 않음(내부에서 바꾸고 복구). **로컬**: `local` 값은 로컬 전용, `synced` 값은 `elapsed` 가 동기화 값일 때만 공유 안전.
- **의존**: `sync`(WP13, synced 모드), `players`(WP8), `local`(관전자 키).

## B.10 시험 기대값

| 시험 | 기대 |
|---|---|
| 길이 측정 `bgm.measure_ms(path)` | GBGM1.ogg → 33095, finale_start_op.ogg → 150967, BGM364.ogg → 891, ikasu001.ogg → 1263, LV10_001.ogg → 666 (±1, 내림). 파일: `ED\MSF_Memory2_BGM\`, `ED\MSF_UE_RE_BGM\`(읽기만) |
| 형식 판별 | 확장자 `.wav` + 내용 `OggS` 인 파일도 성공 |
| 모르는 형식 + `length_ms` 없음 | `EPError`(한국어) |
| MPQ 등록 | `bgm.track("a.ogg")` 두 번 → 두 번째에서 eudplib 중복 오류. 등록 이름 `staredit\wav\a.ogg` |
| 표 | `track` 3개(칸 0~2) 다음 `chunks` 272개 → 문자열·길이 표 각 275칸, 조각 곡 (시작, 개수) = (3, 272) |
| local 모드 (에뮬레이터, 경과 주입) | 요청 BOSS → 남은 368000, 요청 칸 0. 경과 1000 × 368 → 남은 0 → 다음 요청 재생. 남은 > 0 에 요청 → `drop` 이면 곡 그대로, 요청 칸 0 |
| synced 모드 | `elapsed=3000`(> 2500) → 남은 시간 그대로. 끈 플레이어 → 재생 기록 없음. `queue` → 전원 0 이 된 사이클에 적용 |
| 조각 | LV10 요청 → 조각 0, 남은 666 → … → 조각 271 뒤 끝(`loop` 아니면 곡 번호 0) |
| 트리거 수 | targets 1명과 11명 빌드에서 본문 트리거 수가 같다 |
| CP | `tick` 전후 CP 같음 |
| clock | `half()` 가 0,1,0,1…, `dt2` = 연속 두 사이클 합 |

## B.11 인게임 확인 항목

1. `PlayWAV` 문자열 칸을 런타임에 바꿔도 SC:R 이 새 소리를 내는지(방식 2 조건).
2. `PlayWAV` 를 2~3번 연속 부르는 기존 관례의 이유(음량? 누락?) — 1번으로 충분한지.
3. 조각 이어 재생의 틈·겹침(실측 길이 그대로, −42ms 보정 필요 여부). 일시정지 중 `0x51CE8C` 가 흐르는지(흐르면 조각을 건너뜀).
4. 관전자(128~131)에서 `f_getuserplayerid()` 값과 재생 여부.
5. 없는 파일 이름으로 `PlayWAV`(UERE 에는 `BGM_Skip.ogg` 가 음원 폴더에 없음) 시 동작.
6. 확장자만 `.wav` 인 Ogg 재생.
7. synced: 방장이 나갔을 때 `elapsed` 공급이 이어지는지(sync.Bus 규칙), 2인 이상 디싱크 없음.
8. 동시에 울릴 수 있는 소리 수 한도(조각 + 효과음).
9. 음원 수백 개 넣은 맵의 로딩 시간.

## B.12 함정

- 로컬 경과 시간을 **공유 상태에 쓰지 말 것**(LIB 인자 4 `IBGM_EPD`, RESV).
- `PlayWAVAll` 은 CP 를 되돌리지 않는다.
- `MPQAddWave` 의 `is_wav` 는 0.81 에서 효과 없음.
- 입력 맵에 같은 이름의 음원이 있으면 eudplib 가 중복으로 막는다(기본 맵에서 빼 둔다, `split_map.py`).
- 맵이 일부러 짧게 적은 길이를 자동 길이로 바꾸면 곡 사이 간격이 달라진다(`trim_ms`).
- 끔 비트를 타이머와 같은 dword 에 두면(`Deaths ≤ 0` 판정) 끈 플레이어는 늘 "재생 중" 으로 보인다(LIB 동작) — eudext 는 칸을 나눈다.
- 로드 순서에 따라 같은 이름 함수가 덮인다(CA → LIB → 맵). 이식 때 어느 판인지 먼저 확인.
- `IBGM_EPD` 판마다 `Act1` 누락(BRZ·MEME) → 요청 칸이 PC 마다 달라질 수 있다.

---

## DESIGN.md 수정 제안

1. **4.16 근거**: "8맵 950" 옆에 실제 호출 지점 수(A.3)와 **scdata 대비 결과**(쓰기 89.9% Y, 97.3% Y+P, 호출 지점 52.1%/74.1%)를 적는다. "주소표를 새로 만들기 전에 scdata 로 되는 범위를 먼저 확인" → "확인 완료: 표에 넣을 것은 플레이어 표·Addon/Subunit2/Infestation·SpecialAttack·피해 배율(주소 확인 후)뿐".
2. **4.16 API** 를 A.7 로 바꾼다: `dat.unit(u).set(**scdata이름)`, `.flags()`, `.mask()`, `dat.weapon(w).splash()`, `dat.player_unit_enable`, `dat.tep.*`(TEP 키·변환 이식 층), `dat.from_eud_editor`, `dat.every_frame()`, `dat.actions()`, `dat.now`, `dat.temporary()`, `dat.field()`, `dat.addr()`. 초안의 `dat.units[unit].hp.set(5000)` 모양은 버린다(scdata 이름과 충돌). `apply_on_start()` 는 자동 등록으로.
3. **4.16 의미**에 "scdata 대입문은 한 줄 = 트리거 1개 → 시작 패치는 디스크립터 주소로 원시 액션을 모아 낸다", "`WhatSndInit/End` 이름 반대, `Reqptr` 무시(TPL)" 를 적는다.
4. **4.16 시험**: "주소표 스냅숏" → "주소표를 scdata 디스크립터와 대조 + A.8 액션 기대값".
5. **4.16 선택 기준**: A.6 표를 옮긴다(CHK 로 되는 값은 맵 편집기, 한 필드 출처 하나, EUD Editor Add 차분 주의, dataDumper 는 dat 배열에 해당 없음).
6. **4.17 근거**: "`bgmplayer.py` 는 한 곡 반복만" 뒤에 "엔진 두 계통(로컬형 TPL / 공유형 LIB+EPDX, MSQC 경과 시간 동기화), 곡 길이 전부 수동, 조각 이어 재생은 맵이 손으로(M2 1,456 트리거), `NormalTurboSet` 은 곡 길이와 무관" 을 적는다.
7. **4.17 API** 를 B.9 로 바꾼다: `bgm.track/chunks/rotation`, `bgm.Player(mode, targets, elapsed, busy, observers, …)`, `player.request/stop/loop/mute/is_playing/current/chunk/tick`, `bgm.clock.local_dt/half/dt2`. 초안의 `bgm.add(name, [files], lengths_ms)` 는 `track`/`chunks` 로 나누고 **길이는 자동 측정이 기본**.
8. **4.17 선행 작업**: "S5b" → "S5 완료(`docs/spec/S5_dat_bgm.md` B절)". 의존에 **WP13(sync)** 추가(synced 모드) → 6.1 WP16 선행을 "WP8, WP13, S5" 로.
9. **2.4 번들 파이썬**: 소리 길이 측정은 `wave` 모듈에 기대지 않는다(struct 만)고 한 줄.
10. **3.6 CP 규약**에 "`PlayWAVAll`/`DisplayTextAll` 은 CP 를 되돌리지 않는다" 를 예시로.
11. **3.5 뺄셈 표**(S8 몫)에 scdata `-=`(= `isubattr`, 음수 Add)와 `isubtractattr`(Subtract, 연산자 없음)을 넣도록 S8 에 전달.
12. **4.19 misc** 또는 **4.9 players**: `NormalTurboSet` 대체(`clock.half`, `dt2`)를 bgm 밖 공용 시계로 둘지 결정 항목(7절)에 추가.
13. **7절**: D13 "BGM 재생 방식 — EUDSwitch(확실) vs PlayWAV 문자열 패치(인게임 확인 필요)", D14 "`dat.tep` 의 `WhatSnd` 반대 이름을 고칠지(기본: TEP 동작 보존 + 경고)".

## 미확인

**dat**
1. `InitCtrig` 트리거가 STRCtrig 모드에서 몇 번째 사이클에 도는지(`EUDEditorInit` 의 "첫 프레임" 주장과 G5 명세의 추정).
2. euddraft 가 `f_unpatchall` 을 언제 부르는지(컴파일된 부분이라 확인 못 함).
3. SC:R 에서 마스크 Add/Subtract 가 wrap 인지 포화인지(S8).
4. RdySnd 원소 수(106?), 플레이어 표 주소(0x58D088, 0x58CE24 등)의 정확한 이름.
5. `SetUnitAbility` 를 펼친 수는 nil 인자를 빼지 않은 상한.
6. 트리거 액션 목록 안에 직접 쓴 dat 쓰기(예: BRZ `Interface.lua:137~138`)는 세지 않았다.
7. DPS 는 DPS_eud 만 셌다(DPS_Enhance 는 같다고 추정).
8. 피해 배율 주소 0x515B84(eudplib 주석) vs 0x515B88(theSeed 는 CtrigAsm `TtoA` 의 "DamageMultiplier" 값을 따름, SEED `:124`. 같은 곳의 "제작자 실측" 기록(`:126~130`)은 칸 간격 5×0x14 에 관한 것).
9. CHK 정적 대체 뒤 메모리 값이 트리거 패치와 같은지(A.9-1).
10. BRZ `PatchInsert` 3줄 미적용(추측).
11. `f_dwpatch_epd` 스택을 eudplib 내부가 함께 쓰는지.

**BGM**
12. `Install_BGMSystem` 루프 뒤 CP 값의 의도(LIB `:853`).
13. 동시 재생 소리 수 한도.
14. euddraft 0.11.0.1 번들 파이썬에 `wave` 모듈이 있는지.
15. ED 의 `bgmplayer` 를 실제로 쓰는 맵(검색 0건).
16. BRZ·MEME 에서 요청 칸이 PC 마다 달라지는 것이 실제 디싱크로 이어지는지.
17. soundlooper 가 `PlayWAV` 문자열 패치 대신 `EUDSwitch` 를 쓴 이유("Workaround").
18. B.1·B.6·B.7 에서 "(조사 에이전트)" 로 표시한 줄 번호는 이번에 다시 열어 보지 않았다(TPL·LIB·UERE·M2 의 핵심 줄은 직접 확인).
