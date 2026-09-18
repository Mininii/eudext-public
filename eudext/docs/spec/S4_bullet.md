# S4 — 사용자판 총알 (`eudext.bullet` 명세)

작성 2026-09-17. 코드는 고치지 않았다. 근거는 `파일:줄`, 확인하지 못한 것은 "(추측)".
실험 스크립트: 스크래치패드 `spec_s4\count_bullet.py`(호출 수), `spec_s4\bullet_expect.py`(기대값). 출력은 같은 폴더의 `*_out.txt`.

## 약어

| 약어 | 위치 |
|---|---|
| SD | `C:\Users\whatd\Desktop\Stormcoast Fortress\ScmDraft 2` |
| MS | `SD\MapSource` |
| M2 | `MS\MSF_Memory_2` |
| M1 | `MS\MSF_Memory` |
| G2R / G2 | `MS\MSF_GaLaXy.2_R` / `MS\MSF_GaLaXy.2` (G2 는 G2R 의 옛판, 총알 코드는 줄 번호만 다름) |
| UERE / UE | `MS\MSF_UE_RE` / `MS\MSF_UE` (UE 는 옛판) |
| BRZ | `MS\MSF_Breeze` |
| GXY | `MS\Py\Galaxy.py` (eudplib 판. `C:\euddraft0.9.2.0\plugins\Galaxy.py` 와 같은 파일) |
| CA / GB | `MS\Library\CtrigAsm v5.5.lua` / `MS\Library\Ctrig Assembler v5.4 Guide Book.txt` |
| EP81 | eudplib 0.81.0 소스 `…\scratchpad\upstream\eudplib\src\eudplib\` |
| TEPC | `C:\Users\whatd\Documents\TEP3.0_Headless_Compiler\TrigEditPlus\Editor\Encoder\` |
| R4a | `docs\research\R4a_bullet_text.md` |

---

## 0. 한눈에

- **라이브러리 28장 `CreateBullet` 은 어디서도 안 부른다.** 총알을 쓰는 맵은 모두 **자기 판**을 정의한다. 판은 6계통이다: M2(=BRZ 사본), UERE(=UE), G2R(=G2), M1, GXY(eudplib), 그리고 속도 헬퍼만 있는 NewTestMap1. theSeed·Stella_II·Respect_V·MEME·DPS_eud·템플릿에는 정의도 호출도 없다(1.1).
- **공통 핵심** (모든 판이 같다):
  1. `Memory(0x628438, AtLeast, 1)` 일 때만 실행한다.
  2. `0x628438` 을 **마스크 0xFFFFFF 로 읽어 EPD 를 얻는다**(f_Read 의 EPD 출력).
  3. 로케이션 하나를 한 점(L=R=X, T=B=Y+보정)으로 옮기고 `CreateUnit(1, 유닛, 그 로케이션, 소유자)`.
  4. 새 유닛의 **현재 위치(+0x28)를 읽어 주문 목표(+0x58)에 복사**한다.
  5. **방향 +0x21 ← 각도(0~255)**, **주문 +0x4D ← 135**(eudplib 이름 "Attack Ground (Infested Terran)", GB 는 "자폭명령").
  6. 트리거가 끝난 뒤 게임 로직이 주문 135 를 실행하며 유닛의 지상 무기를 쏜다(R4a A.1). 생성 프레임 안에 발사된다(1프레임).
- **판별 차이**는 ① 만드는 유닛(항상 204 후 종류 교체 / 인자 유닛 직접), ② 소유자(FP·P6·인자), ③ Y 보정(+10 / 0), ④ 높이를 어디에 쓰는지(**모든 판이 틀린 주소** — 4.1 함정), ⑤ 추가 칸 패치(`0xDC` 상태 플래그·`0xE4`·`0xA3`·`0x110` 수명 12/30/없음), ⑥ 방향을 받는지(각도) 목표 좌표에서 구하는지(`f_Atan2` + 360→256 표)다.
- **방향 규약**: 사용자 맵의 총알 flingy 는 **최고속도가 음수**다(정적 EUD Editor 값 또는 `SetFlingySpeed`/`SetBulletSpeed` 의 `0xFFFFFFFF−v`). 그래서 **실제로 날아가는 방향 = 유닛 방향 + 128**이다. `CreateBulletXY` 가 `atan2(출발−목표)` 를 쓰는 이유가 이것이다(2.3). 실험으로 확인: `to_dir256(atan2(출발−목표)) = to_dir256(atan2(목표−출발)) + 128 (mod 256)` 이 무작위 10만 쌍에서 모두 성립(같은 점 제외).
- **속도·수명은 호출 인자가 아니다.** `SetBulletSpeed`/`SetFlingySpeed`/`WeaponTimeLeft` 가 **전역 dat 액션 목록**을 돌려주고, 호출자가 패턴 시작 때 따로 넣는다(4.4). 같은 프레임 같은 무기는 마지막 값을 공유한다.
- **dat 초기화는 코드에 없다.** 탄막 유닛·무기·flingy 설정은 EUD Editor 정적 수정(`EUDEditorDat.lua`, 첫 프레임 1회 적용)에 들어 있다(2.6). 28장 `BulletInitSetting` 과 같은 계열의 값이다.
- **eudext 결론**: 본문 1벌의 `f_bullet`(방향)·`f_bullet_to`(목표, `mathx.atan2`+`to_dir256`, 1프레임) + 종류 객체 `BulletKind`(속도·수명·높이 액션, 선택적 dat 묶음) + 생성 성공 확인(0 반환). 정본 칸 패치는 UERE `Install_CBullet` 판(5절).

---

## 1. 판 목록과 호출 수

### 1.1 정의 위치

| 판 | 함수 (파일:줄) | 본체(호출되는 서브루틴) | 비고 |
|---|---|---|---|
| **A. M2** | `CreateBullet(UnitId,Height,Angle,XY,Player)` M2 `func.lua:2023`, `CreateBulletCond(UnitId,Height,Angle,XY,Player,Cond,Act)` `:2049`, `CreateBulletLoc(UnitId,Height,Angle,Player)` `:2059`, `CreateBulletPosCalc(UnitId,Height,Angle,X,Y)` `:2343`, `SetBullet(UnitId,Height,XY,TargetXY)` `:2355` | `Call_CBullet` `:2085~2116`, `Call_CBullet_PosCalc` `:2233~2254`, `Call_CBulletA` `:2119~2151`. 모두 `Include_CBulletLib()` `:2083` 안 | `SetBullet` 은 `Call_SetBulletXY` 를 부르는데 그 정의가 주석 처리됨(`:2176~2229`) → 부르면 nil 오류(추측). 호출 0 |
| **A'. M2 XY** | `CreateBulletXY(UnitID,Height,XY,TargetXY,ForPlayer)` M2 `func.lua:2263` | `Call_CreateBulletXY` `:2287~2316` | 360→256 표 `DCtoSCFArr` M2 `Var_init.lua:41~49` |
| A″. BRZ | M2 와 같은 코드 BRZ `func.lua:1859~2186` | 같음 | **호출 0회, `DCtoSCFArr` 정의 없음** → 죽은 사본 |
| **B. UERE (정본)** | `Install_CBullet()` UERE `func.lua:2~117` 안에 `CreateBulletCond(UnitId,Height,Angle,XY,Player,Cond,Act)` `:12`, `CreateBullet(UnitID,Height,Angle,X,Y,ForPlayer)` `:21`, `CreateBulletXY(UnitID,Height,XY,TargetXY,ForPlayer)` `:62` | `CallCBullet` `:34~60`, `Call_CreateBulletXY` `:86~114` | 가장 최근에 손본 맵(`CHANGELOG.md`, `build.bat`, eds 틀). 표 `DCtoSCFArr` UERE `Var_Include.lua:482~490` |
| B'. UE | `CreateBullet(UnitID,Height,Angle,X,Y,ForPlayer)` UE `CallTriggers.lua:315` | `CallCBullet` `:328~354` | B 의 앞판: Y+10, 높이 → `0x66321C`, 수명 없음 |
| **C. G2R** | `CreateBullet(UnitId,Height,Angle,XY)` G2R `func.lua:1195`, `CreateBulletPosCalc` `:1219`, `SetBullet(UnitId,Height,XY)` `:1231`, `SetBulletSpeed` `:1180` | `Call_CBullet` G2R `main.lua:187~214`, `Call_SetBulletXY` `:216~262`, `Call_CBulletA` `:265~288`, `Call_CBullet_PosCalc` `:291~312` | 변수 G2R `init.lua:353, 403~408, 464~466`. 슬롯 배열 G2R `BossTrig.lua:20~34`. G2 는 `func.lua:1180~1251`, `main.lua:199~` |
| **D. M1** | `CreateBullet(Height,Angle,X,Y)` M1 `Main.lua:1042` | `CallCBullet` `:1054~1076` | 유닛 204·소유자 P6·로케이션 24 고정 |
| **E. GXY** | `CreateBullet(UnitId,Height,Angle,X,Y)` GXY `:6~34`, `CreateBulletLoc(PlayerId,UnitId,Height,Angle,LocId)` `:37~61` | **호출마다 인라인**(EUDFunc 아님) | eudplib 선례 |
| 속도 헬퍼 | `SetBulletSpeed(Value,BreakDis)` M2 `func.lua:2320`, G2R `func.lua:1180`, BRZ `:2103` / `SetFlingySpeed(FID,Value)` M2 `:2334`, UERE `func.lua:1964`, BRZ `:2117` / `WeaponTimeLeft(WepID,Value)` M2 `:2340`, BRZ `:2123` | 액션 목록 반환 | NewTestMap1 `function.lua:501` 의 `SetFlingySpeed` 는 **다른 뜻**(PatchInsert, 값 그대로 = 양수) |

검색 범위: 위 폴더 + theSeed, Stella_II, MSF_Respect_V, MSF_MEME_EUD, DPS_eud, MSF-Template → 뒤의 6곳은 `CreateBullet|SetBullet|CBullet|BulletInit` 0건.
euddraft 플러그인(`C:\euddraft0.9.2.0\plugins\`)에서 총알 코드가 있는 것은 `Galaxy.py` 하나(`MSF_Mem.py`, `MSF_UE.py` 는 무관).

### 1.2 호출 수 (주석·정의 줄 제외, `count_bullet.py`)

| 함수 | M2 | M1 | G2R | UERE | 주요 4맵 합 | G2 | UE | GXY | NTM1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CreateBullet` | 8 | 12 | 15 | 42 | **77** | 15 | 39 | 80 | · |
| `CreateBulletXY` | 7 | · | · | · | 7 | · | · | · | · |
| `CreateBulletCond` | 2 | · | · | 7 | 9 | · | · | · | · |
| `CreateBulletLoc` | 1 | · | · | · | 1 | · | · | 1 | · |
| `SetBullet` | · | · | 1 | · | 1 | 1 | · | · | · |
| `CreateBulletPosCalc` | · | · | 2 | · | 2 | 2 | · | · | · |
| 소계(생성) | 18 | 12 | 18 | 49 | **97** | 18 | 39 | 81 | · |
| `SetBulletSpeed` | 7 | · | 7 | · | 14 | 7 | · | · | · |
| `SetFlingySpeed` | 4 | · | · | 5 | 9 | · | · | · | 2 |
| `WeaponTimeLeft` | 9 | · | · | · | 9 | · | · | · | · |
| 설치(`Include_CBulletLib`/`Install_CBullet`) | 1 | · | · | 1 | 2 | · | · | · | · |

R1 의 "4맵 95회" 는 `CreateBulletPosCalc` 2회를 뺀 수다. 호출 줄 하나가 Lua 반복문 안에 있으면 실제 트리거는 더 많다(예: UERE `Sans.lua:134~137` 은 `for i = 1, 41` 안에서 2줄 → 호출 자리 82개).

### 1.3 실제 호출 모양

- 방향 직접: `CreateBullet(206,20,f_CRandNum(256),{CPosX,CPosY},P7)` M2 `BossTrig.lua:245` / `CreateBullet(208,20,Angle1,CPosX,CPosY)` UERE `Destr0yer.lua:288` / `CreateBullet(204,20,_Add(B_A1,128),BossXY)` G2R `BossTrig.lua:208` / `CreateBullet(20,_Add(B6_5_A,85),2048,2048)` M1 `Main.lua:15405`
- 좌표 식: `CreateBullet(208,20,0,_iSub(_Add(CPosX,TS_VarArr[3]),TS_VarArr[20]),_Add(_Add(CPosY,TS_VarArr[4]),TS_VarArr[19]))` UERE `CallTriggers.lua:868`
- 목표: `CreateBulletXY(206,20,{CPosX,CPosY},{2048,2048},FP)` M2 `GunData.lua:3274` (중심에서 500 떨어진 원 위에서 중심을 향해 — 앞줄 `f_Lengthdir(FP, 500, TempA, CPosX, CPosY)`)
- 조건부: `CreateBulletCond(210,20,192,{1216+16,2752-16+(i*16)},FP,{CD(PattC3[i],1)})` UERE `Sans.lua:135` — 왼쪽 벽(x=1232)에서 방향 192(서쪽)로 만들어 **동쪽으로** 날린다(음수 속도, 0절)
- 스포너 안: `CreateBulletXY(Gun_TempSpawnSet1,20,nil,{G_CA_TempTable[11],G_CA_TempTable[12]},FP)` M2 `func.lua:616`, `CreateBullet(Gun_TempSpawnSet1,20,G_CA_TempTable[14],nil,FP)` `:621` — G_CA `RepeatType==101`(탄막 유닛) 분기 `:613~626`. `XY=nil` 이면 G_CA 가 이미 옮겨 둔 로케이션 1 을 쓴다. G2R 도 G_CA 에서 유닛 204~220 이면 `SetBullet`/`CreateBullet` 을 부른다(G2R `func.lua:495~500`).
- 속도·수명(패턴 시작 액션에 섞음): `CIf(FP,CV(CA[1],1),{SetBulletSpeed(8000), SetFlingySpeed(174, 8000), WeaponTimeLeft(127,32), WeaponTimeLeft(30,32), …})` M2 `GunData.lua:3302~3306`, `CIf(FP,{…},{SetFlingySpeed(158,(20*32)*4)})` UERE `Sans.lua:77`, `CIfOnce(FP,{Memory(0x628438,AtLeast,1)},SetBulletSpeed(500))` G2R `BossTrig.lua:51`
- eudplib 선례: `CreateBullet(204,20,Angle1,2368,1728)` GXY `:448` (80회 인라인), `CreateBulletLoc(P6,204,5,B_2A,253)` GXY `:655`

---

## 2. 판별 동작 비교

### 2.1 생성 단계

| 판 | 만드는 유닛 | 소유자 | 로케이션(MRGN 번호) | Y 보정 | 높이 쓰는 곳 | 종류 교체(+0x64) | 실패 검사 |
|---|---|---|---|---|---|---|---|
| A M2 `Call_CBullet` | 인자 `CBUnitId` | 인자 `CBPlayer` | 0(=로케이션 1). **X·Y 둘 다 0 이면 옮기지 않음**(`TTOR`, `:2090`) | +10 (`:2095`) | `0x66321C` 마스크 0xFF = **유닛 204 의 elevation** (`:2100`) | `SetTo CBUnitId` 마스크 0xFFFF (중복, `:2102`) | 슬롯 조건만 |
| A' M2/UERE XY | 인자 | 인자(기본 FP) | 0 | 0 (`:2303`) | `TSetMemoryB(0x656990, UnitID, …)` = **weapons.dat attackAngle[유닛번호]** (`:2300`, UERE `:98`) | 없음 | 슬롯 조건만 |
| B UERE `CallCBullet` | 인자 | 인자(기본 FP) | 0 | 0 (`:47`) | A' 와 같은 버그 칸 (`:44`) | 없음 | 슬롯 조건만 |
| B' UE | 인자 | 인자 | 0 | +10 (`CAdd`, `:332`) | `0x66321C` (`:339`) | 없음 | 슬롯 조건만 |
| C G2R `Call_CBullet` | **항상 204** (`main.lua:203`) | **FP 고정** | 0, X·Y 0 이면 안 옮김 | +10 | `0x66321C` (`:202`) | `SetTo CBUnitId` **마스크 없음**(dword, `+0x66` 두 바이트도 0) (`:204`) | 슬롯 조건만 |
| C `Call_CBullet_PosCalc` | 204 | FP | 0 을 **Add**(상대 이동) (`:297~300`) | +10 | `0x66321C` | 마스크 0xFF (`:302`) | 〃 |
| D M1 | 204 고정 | P6 고정 | 23(=로케이션 24) | +10 (`CAdd`, `:1058`) | `0x66321C` (`:1061`) | 없음 | 〃 |
| E GXY | 204 고정 | P6 / 인자 | 247 ("BulletLoc") / 인자 | +10 | `0x66321C` | `UnitId != 204` 이면 dword SetTo (`:23~25`) | `Nextptrs >= 1` |
| (참고) CA 28장 | 인자 | 인자 | 인자 | **−2** (CA:81483) | `0x663150+UnitId` = 올바른 elevation (CA:81467) | 없음 | 슬롯 조건만 |

주소 확인: units.dat elevation 은 `0x663150`(EP81 `scdata/unit.py:175`), `0x66321C − 0x663150 = 204`. weapons.dat attackAngle 은 `0x656990`, 원소 130개(EP81 `scdata/weapon.py:71`, 범위 `(0,129)`).

### 2.2 생성 뒤 CUnit 칸 패치 (EPD 오프셋 = 바이트 ÷ 4)

| 칸 | 뜻 (EP81 `scdata/cunit.py`) | A M2 CBullet | A'/B UERE·XY | B' UE | C G2R | D M1 | E GXY | CA 28장 |
|---|---|---|---|---|---|---|---|---|
| +4 (0x10), +6 (0x18), +7 (0x1C) | moveTargetPos, nextMovementWaypoint, nextTargetWaypoint (`:114,119,123`) | ← 위치 | · | · | · | · | · | · |
| +22 (0x58) | orderTargetPos (`:170`) | ← 위치 | ← 위치 | ← 위치 | ← 위치 | ← 위치 | ← 위치 | ← 위치 |
| +8 마스크 0xFF00 (0x21) | currentDirection1 (`:126`) | ← 각×256 | ← 각×256 | ← 각×256 | ← 각×256 | ← 각×256 | ← 각×256 | ← 각(상수만 ×256) |
| +8 마스크 0xFF0000 (0x22) | turnSpeed (`:128`) | ← 127 | · | · | · | · | · | · |
| +19 마스크 0xFF00 (0x4D) | orderID (`:156`) | ← 135 | ← 135 | ← 135 | ← 135 | ← 135 | ← 135 | ← 135 (마스크 0xFFFF00: +0x4E 도 0) |
| +40 마스크 0xFF000000 (0xA3) | energy(0xA2 word)의 윗바이트 (`:225`) | · | ← 0 | ← 0 | · | ← 0 | · | · |
| +55 마스크 0x300104 (0xDC) | statusFlags: InAir 0x4·RequiresDetection 0x100 켬, IsNormal 0x100000 끔, NoCollide 0x200000 켬 (`:50~80`) | · | ← 0x200104 | ← 0x200104 | · | ← 0x200104 | · | · |
| +57 (0xE4) | visibilityStatus (`:344`) | · | ← 0 | ← 0 | · | ← 0 | · | · |
| +68 마스크 0xFFFF (0x110) | removeTimer (`:381`) | ← 30 | ← **12** | · | ← 30 | · | · | ← 6 |

위치는 모두 **생성 직후 `+10`(0x28 pos)을 읽어** 복사한다(M2 `:2104`, UERE `:51` `_ReadF`, CA:81518). 판 A·C 는 `f_Read` 로 `Locs` 변수에, B·D 는 `_ReadF` 임시값으로 읽는다.

### 2.3 각도

| 판 | 입력 | 처리 | 근거 |
|---|---|---|---|
| A, C, E | 0~255 (SC 방향) | 그대로 ×256 (A·C 는 `_Mul(CBAngle,_Mov(256))` 런타임 곱셈, E 는 eudplib `Angle*256`) | M2 `:2110`, G2R `main.lua:209`, GXY `:31` |
| B, B', D | 0~255, **음수 허용** | `Angle ≥ 0x80000000` 이면 `CNeg` 후 `256 − |a|`, 그다음 `f_Mod(·,256)` (D 는 `f_Mod` 만) | UERE `:38~42`, UE `:333~337`, M1 `:1059` |
| A', B 의 XY | 출발 XY, 목표 XY | ① `f_Atan2(FP, 출발Y−목표Y, 출발X−목표X, Angle_T)` (Cycle 360, CtrigAsm 규약: 0=+x, 화면 시계 방향) ② `Angle_T ≥ 360` 이면 `CMod 360` ③ `Angle_V = 표[Angle_T] + 64` ④ `f_Mod(Angle_V, 256)` | M2 `:2292~2298`, UERE `:91~96` |

- 표: `Angle360to256[i+1] = (i/360)*256` (M2 `Var_init.lua:41~44`) → `f_GetFileArrptr(FP,…,4,1)` 이 `SaveFileArr` 에서 `bit32.band(값, 0xFF)` 로 바이트를 뽑는다(CA:76933~76956). TEP 의 `bit32` 는 실수를 `(lua_Integer)` C 캐스트로 바꾼다(TEPC `src\linit.c:37~44`) → **0 방향 자르기**. 따라서 `표[a] = floor(a·32/45)` (0~359 전부 정수식과 일치, `bullet_expect.py`).
- `+64`: CtrigAsm 0°(+x, 동쪽)는 SC 방향 64(동쪽)다. 둘 다 화면에서 시계 방향으로 늘므로 `SC = a·256/360 + 64`.
- **출발−목표**를 쓰므로 유닛은 목표의 **반대쪽**을 본다. 음수 최고속도 flingy 가 뒤로 날아 목표로 간다(0절).
- 읽기는 `_SHRead(FArr(…))`(CA:41613, 부호 없는 dword 읽기)라 표 값 0~255 에는 영향 없다.
- 같은 점(출발=목표): 참조 구현은 `f_Div(0,0)` 을 몫 0xFFFFFFFF 로 보고 90° → 방향 128 을 낸다(추측: 실제 CtrigAsm 0 나눗셈 몫 미확인).

### 2.4 속도·수명 헬퍼 (전역 dat 액션)

| 함수 | 만드는 액션 | 대상 |
|---|---|---|
| `SetBulletSpeed(v, halt)` M2 `:2320~2333` | `SetMemory(0x6CA170, SetTo, 0xFFFFFFFF−v)`, `SetMemoryX(0x6C9DB4, SetTo, v, 0xFFFF)`, [`SetMemory(0x6C9BA8, SetTo, halt)`] | flingy **158**(Yamato Gun)의 topSpeed / acceleration / haltDistance. `0x6C9EF8+4·158 = 0x6CA170` 등(EP81 `scdata/flingy.py:28~30`) |
| `SetFlingySpeed(f, v)` M2 `:2334~2339`, UERE `:1964~1969` | `SetMemory(0x6C9EF8+4f, SetTo, 0xFFFFFFFF−v)`, `SetMemoryW(0x6C9C78+2f, SetTo, v)` | 임의 flingy (M2 174, UERE 158) |
| `WeaponTimeLeft(w, t)` M2 `:2340~2342` | `SetMemoryB(0x657040+w, SetTo, t)` | weapons.dat removeAfter (EP81 `scdata/weapon.py:61`). M2 127·30 |
| NTM1 `SetFlingySpeed` `function.lua:501~504` | `PatchInsert(SetMemory(0x6C9EF8+4f, SetTo, v))` … | **양수** 그대로, 시작 시 1회(다른 뜻) |

- `0xFFFFFFFF − v = −v−1`. CA 28장은 `−Speed`(CA:81506) → **1 차이**.
- 가속도를 최고속도 크기와 같게 둬 첫 프레임에 최고속도에 닿게 한다(추측).
- 상수만 받는다(Lua 산술). 변수 속도는 사용자판에 없다.

### 2.5 2프레임 목표판 (`SetBullet`, G2R 만 동작)

- `Call_SetBulletXY`(G2R `main.lua:216~262`): 유닛 204 생성, 종류 교체, **주문 목표 ← (BPosX, BPosY + 65536·Y)**(목표 좌표), 주문 135, 수명 30. 그리고 128칸 슬롯 배열(`BossTrig.lua:20~34`, 트리거 액션 값 칸을 변수로 씀)의 빈칸에 `(EPD, 대기=1)` 을 넣는다. 빈칸이 없으면 오류 문구(`CBulletErrT`).
- 매 프레임 슬롯마다 `Call_CBulletA`(`main.lua:265~288`): EPD 가 유닛 표 범위(19025 ~ 19025+84·1699)이고 대기=0 이면 현재 방향을 읽고, 위치를 주문 목표 등에 복사하고, **방향 += 128**(`_Add(AngleA,32768)` 마스크 0xFF00), 주문 135 를 다시 주고 슬롯을 비운다. 대기>0 이면 1 뺀다.
- 원리: 첫 프레임에 목표를 향해 몸을 돌린 뒤 반대로 뒤집어 음수 속도로 목표 쪽에 쏜다. CA `CreateBulletTarget`(R4a A.3, 2프레임)과 같은 계열.
- M2 는 이 경로를 주석 처리하고(`func.lua:2176~2229`, 호출 줄도 주석 `GunData.lua:3275`) **`CreateBulletXY`(atan2, 1프레임)로 바꿨다.** → eudext 는 1프레임 방식만 만든다.

### 2.6 초기화·dat·플러그인 전제

| 항목 | M2 | UERE | G2R | M1 |
|---|---|---|---|---|
| 설치 호출 | `Include_CBulletLib()` M2 `main.lua:132` | `Install_CBullet()` UERE `main.lua:119` (3초 대기 블록 안) | 파일 최상위(`main.lua:187~`) + 보스 시작 때 슬롯 배열 | 파일 최상위 |
| 360→256 표 | `DCtoSCFArr` 파일 배열(STRCtrig 필요) | 같음 | · | · |
| 정적 dat | `EUDEditorInit()` M2 `main.lua:117` (첫 프레임 1회, `EUDEditorDat.lua`) | `EUDEditorInit()` UERE `main.lua:81` | (맵 파일·옛 방식, 확인 못 함) | (확인 못 함) |
| 탄막 유닛 | 205→무기 126, 206→무기 30(Yamato), 207→무기 127 (`EUDEditorDat.lua:314~316`) | 208→무기 127, 210→무기 128 (`:240~242`) | 204(+ 종류 교체), 보스 때 `units[204].groundWeapon ← 125` (`BossTrig.lua:36`) | 204 |
| 언리미터 | `[unlimiter]` (`eds_template.eds`) | `[unlimiter]` (`eds_template.eds`) | (확인 못 함) | (확인 못 함) |
| 공중 충돌 끔 | `NoAirCollisionX(FP)` `main.lua:168` | `NoAirCollisionX(FP)` `main.lua:160` | `main.lua:341` | `NoAirCollisionX(P6)` `Main.lua:1105` |

**EUD Editor 가 탄막 유닛에 준 값**(M2 205~207, UERE 208·210 에서 공통으로 보이는 것):

| dat | 필드 | 값 | 근거 |
|---|---|---|---|
| units | flingy(Graphics) | 88 (Vulture) | M2 `EUDEditorDat.lua:34~36`, UERE `:33~35` |
| units | elevation | 12 (M2) / 20 (UERE) | M2 `:177~179`, UERE `:118~119` |
| units | baseProperty(특수 능력) | 0x38000004 (M2: Flyer+BattleReactions+FullAutoAttack+Invincible) / 0x20000004 (UERE: Flyer+Invincible) | M2 `:403~405`, UERE `:321~322`, 비트 이름 EP81 `scdata/unit.py:62~105` |
| units | 컴퓨터·사람 대기, 복귀, 공격 이동 주문 | 2 (M2) / 23 (UERE 210) | M2 `:216~284`, UERE `:147~216` |
| units | groundWeapon | 위 표 | |
| units | 유닛 크기(unitBounds) 1, 배치 상자 0~1 | | M2 `:518~674`, UERE `:404~422` |
| weapons | behavior | **9 (GoToMaxRange)** | M2 `:864, 878~879`, UERE `:582~583`, 이름 EP81 `scdata/offsetmap/memberkind.py:281` |
| weapons | flingy(Graphics) | M2 126→173, 127→174 / UERE 127→106, 128→164 | M2 `:802~803`, UERE `:536~537` |
| weapons | explosionType 3, 스플래시, 피해, cooldown 1 | | M2 `:886~1079`, UERE `:597~697` |
| flingy | topSpeed | M2 174 = +1707(런타임에 `SetFlingySpeed` 로 음수) / UERE 106 = **0xFFFFE0BF(−8001)**, 158 = 8000(런타임 음수) | M2 `:1108`, UERE `:733~735` |
| flingy | acceleration, haltDistance 0~1, turnRadius 127, movementControl 0 | | M2 `:1119~1146`, UERE `:742~762` |

CA 28장 `BulletInitSetting` 표(R4a A.2)와 같은 방향이다(무적+비행, 이동 플래그, 크기 1, AI 주문, 투사방식 9, 무기 flingy). 다만 사용자 맵은 **벌처 이미지 iscript(0x66F048)를 바꾸지 않는다**(M2·UERE 의 EUDEditorDat 에 image #256 없음).

### 2.7 CtrigAsm 28장 원본과의 차이 (CA:81453~81529)

| 항목 | CA 28장 | 사용자판 |
|---|---|---|
| 호출 방식 | 호출 자리마다 트리거 펼침 | 서브루틴 1벌 + 인자 변수(`SetNextTrigger`/`CallTriggerX`) |
| 속도·수명 | 인자, 실행마다 dat 기록 | 따로 헬퍼 |
| 투사방식·iscript | 실행마다 `behavior←9`, `image256.iscript←86` | 정적(EUD Editor) |
| 방향 변수 | ×256 을 호출자가 해야 함 | 본체가 곱함 |
| 수명 | 6 | 12 / 30 / 없음 |
| 사전 표 | `BulletInitSetting` → `BulletTable[UnitId]` 필수 | 없음 |
| 목표판 | `CreateBulletTarget` 2프레임, 호출 자리당 프레임당 1발 | atan2 1프레임, 제한 없음 |

---

## 3. 공통 핵심과 맵별 차이

**공통 핵심** (eudext 가 반드시 할 일)
1. 빈 슬롯 확인 → 다음 유닛 포인터·EPD 읽기.
2. 한 점 로케이션 → `CreateUnit(1, 유닛, 로케이션, 소유자)`.
3. 위치(+0x28) → 주문 목표(+0x58).
4. 방향(+0x21) ← 0~255, 주문(+0x4D) ← 135.
5. 방향 인자는 **유닛이 바라보는 방향**(SC 256 규약, 0=북, 시계). 음수 속도 flingy 이면 실제 진행 = +128.
6. 목표판은 `atan2(출발−목표)`(CtrigAsm 규약) → `floor(a·32/45)+64 mod 256`.

**맵별 차이** (옵션으로 받을 것)
- Y 보정 0 / +10 (CA −2).
- 추가 칸: 수명 12/30/없음, 상태 플래그·가시성·0xA3, 이동 목표 3칸·turnSpeed.
- 204 로 만들고 종류만 바꾸기(C·E).
- 높이(모든 판이 틀린 칸 — eudext 는 올바른 `elevation[유닛]` 을 선택 인자로).
- 소유자 기본값(FP/P6).

---

## 4. 기능별 명세

### 4.1 `CreateBullet` (방향 지정)

- **원본**: 정본 UERE `func.lua:21~32`(래퍼) + `:34~60`(본체). 다른 판은 1.1.
- **인자**: `UnitID`(상수/V), `Height`(상수/V), `Angle`(상수/V, 0~255, 음수 허용), `X`, `Y`(상수/V/식), `ForPlayer`(기본 FP). 래퍼는 `TSetCVar` 6개 + `SetNext` 로 본체를 부른다(호출 자리 트리거 1개 + 인자 식 계산).
- **런타임 동작**(UERE):
  1. `CIf(Memory(0x628438, AtLeast, 1))`
  2. `f_Read(FP, 0x628438, "X", Nextptrs, 0xFFFFFF)` → `Nextptrs` = 다음 유닛 EPD
  3. 음수 각 보정 → `Angle mod 256`
  4. 한 트리거: `attackAngle[UnitID] ← Height`(버그), 로케이션 0 ← (X, Y), `CreateUnit(1, UnitID, 1, ForPlayer)`
  5. 한 트리거: `+22 ← read(+10)`, `+8 ← Angle·256 (0xFF00)`, `+19 ← 135·256 (0xFF00)`, `+40 ← 0 (0xFF000000)`, `+55 ← 0x200104 (0x300104)`, `+57 ← 0`, `+68 ← 12 (0xFFFF)`
- **사용**: 주요 4맵 77회(1.2). 모양은 1.3.
- **eudext**: `bullet.f_bullet(kind, owner, x, y, facing, height=None)` (5.1).
- **시험**: 6.3(포인터·칸 쓰기), 6.2(높이 액션). 인게임 7절 1·3·6·7.
- **함정**
  - **높이 인자가 효과 없고 부작용만 있다.** UERE·XY 판은 `0x656990+유닛번호`(weapons attackAngle, 130칸)에 쓰므로 유닛 204~210 이면 표 밖인 **minRange** 를 덮는다: 204→무기 17 minRange 0바이트, 206→무기 17 2바이트, 208→무기 18 0바이트, 210→무기 18 2바이트(무기 17 = Gemini Missiles (Kazansky), 18 = Burst Lasers (Kazansky), eudplib 이름표). 210 의 경우 무기 18 최소 사거리가 20·65536 이 된다. A·C·D·E 판은 `0x66321C`(유닛 204 elevation)에 쓰므로 204 가 아닌 유닛에는 효과가 없다(M2 는 205~207 elevation 을 정적으로 12 고정). **옮기지 말 것.**
  - 슬롯이 있어도 `CreateUnit` 이 실패하면 빈 슬롯에 칸을 쓴다(검사 없음, R4a A.8).
  - A·C 판은 X·Y 가 둘 다 0 이면 로케이션을 옮기지 않는다 → (0,0) 발사 불가. 대신 `XY=nil` 로 "현재 로케이션 1" 을 뜻하게 쓴다(스포너).
  - A·C 의 각도 곱셈은 런타임 `_Mul` 이다(상수 각도여도).
  - C 의 종류 교체는 dword `SetTo` 라 +0x66~0x67 도 0 이 된다.

### 4.2 `CreateBulletXY` (목표 좌표)

- **원본**: 정본 UERE `func.lua:62~114`(M2 `:2263~2316` 과 같은 코드. M2 는 주석 한 줄만 다름).
- **인자**: `UnitID`, `Height`, `XY={X,Y}`(nil→{0,0}), `TargetXY={TX,TY}`(nil→{0,0}), `ForPlayer`(기본 FP). 표가 아니면 `PushErrorMsg`.
- **런타임 동작**: 2.3 의 ①~④로 `Angle_V` 를 구한 뒤 4.1 의 4·5 와 같음(수명 12).
- **사용**: M2 7회(`GunData.lua:3274, 3283, 3436, 3446, 3456`, `func.lua:616` 등). UERE·BRZ 0회.
- **eudext**: `bullet.f_bullet_to(kind, owner, x, y, tx, ty, height=None)`. 방향 = `mathx.to_dir256(mathx.atan2(y−ty, x−tx))` (kind.reverse=True, 기본) / `mathx.to_dir256(mathx.atan2(ty−y, tx−x))` (reverse=False). 두 식은 같은 점을 빼고 정확히 128 차이다(`floor((a+180)·32/45) = floor(a·32/45)+128`, 실험 10만 쌍 불일치 0).
- **시험**: 6.1 방향 표. 인게임 7절 2.
- **함정**
  - 입력 범위: `f_Atan2` 는 −32768~32767(CA:34879 주석), 내부 `Y<<16` 때문. 맵 좌표 차는 충분히 안.
  - 출발=목표이면 방향이 정해지지 않는다(2.3).
  - `f_Atan2` 출력이 360 인 경우를 `CMod` 로 접는다 → eudext `to_dir256` 도 `a mod 360` 을 먼저 한다.
  - 방향 해상도: 360→256 자르기라 1° 단위 오차 + atan2 올림 성격(최대 1°, R4b C5).

### 4.3 `CreateBulletCond`, `CreateBulletLoc`, `CreateBulletPosCalc`

| 함수 | 원본 | 동작 | 사용 | eudext 대응 |
|---|---|---|---|---|
| `CreateBulletCond(…,Cond,Act)` | UERE `func.lua:12~20`, M2 `:2049~2057` | `CallTriggerX(FP, 본체, Cond, {Act, SetCVar…})` — 조건이 참일 때만 인자 설정·호출. 인자는 **상수만**(`SetCVar`) | UERE 7, M2 2 | `if EUDIf()(cond): f_bullet(…)` — 전용 API 없음 |
| `CreateBulletLoc(UnitId,Height,Angle,Player)` | M2 `:2059~2069` | X=Y=0 으로 본체 호출 → 로케이션 1 을 그대로 씀 | M2 1 (`BossTrig.lua:288`) | `f_bullet_at(kind, owner, loc, facing)` (그 로케이션에 바로 생성, y_offset 미적용 — WP14 구현, 2026-09-17 고침) |
| GXY `CreateBulletLoc(PlayerId,UnitId,Height,Angle,LocId)` | GXY `:37~61` | 지정 로케이션에 생성 | GXY 1 | 같음 |
| `CreateBulletPosCalc(UnitId,Height,Angle,X,Y)` | G2R `func.lua:1219`, M2 `:2343` | 로케이션 0 좌표에 (X, Y+10) 을 **더해서** 생성(상대 위치), 소유자 FP | G2R 2 (`main.lua:4360, 4370`) | 호출자가 `f_getlocTL` 등으로 중심을 읽어 더한 뒤 `f_bullet` — 전용 API 없음 |

### 4.4 `SetBulletSpeed`, `SetFlingySpeed`, `WeaponTimeLeft`

- **원본·동작**: 2.4.
- **사용**: `SetBulletSpeed` M2 7·G2R 7, `SetFlingySpeed` M2 4·UERE 5, `WeaponTimeLeft` M2 9. 거의 항상 **패턴 시작 조건 블록의 액션 목록**에 넣는다(1.3).
- **eudext**: `kind.speed_actions(v, halt=None)`, `kind.time_actions(t)` → 액션 목록(상수), 변수이면 실행 함수 `kind.set_speed(v)`, `kind.set_time(t)`. `reverse=True` 이면 topSpeed ← `0xFFFFFFFF − v`(사용자판과 같은 값). 변수 v 는 `SetTo 0xFFFFFFFF` + `Subtract v`(포화지만 v ≤ 0xFFFFFFFF 라 결과 같음) 두 액션.
- **시험**: 6.2.
- **함정**: 전역이라 **같은 flingy/무기를 쓰는 모든 총알이 같은 프레임에 마지막 값을 쓴다**(GB 8040). M2 는 flingy 158 과 174 를 함께 바꾼다(무기 30·127). 발사가 트리거 뒤 게임 로직에서 일어나므로, 패턴 A 가 속도를 바꾸고 같은 프레임에 패턴 B 가 다시 바꾸면 A 의 총알도 B 속도로 나간다(추측: 발사 순간에 dat 를 읽는다고 가정).

### 4.5 `SetBullet` + `Call_CBulletA` (2프레임, G2R)

- 2.5 참고. 사용 G2R 1(스포너 안). **eudext 는 만들지 않는다**(M2 가 스스로 `CreateBulletXY` 로 대체). 필요하면 `f_bullet_to` 로 옮긴다.

### 4.6 `Include_CBulletLib` / `Install_CBullet`

- 전역 변수(인자 칸)와 서브루틴을 만든다. 호출 1회. eudext 에서는 모듈 import 와 첫 호출 때 본문 생성으로 대체(3.3 규약). 로케이션 하나만 `bullet.setup(loc=…)` 으로 예약.

---

## 5. `eudext.bullet` API 확정안 (DESIGN 4.15 초안을 고침)

### 5.1 API

```python
from eudext import bullet
from eudext.bullet import BulletKind

bullet.setup(loc="eudext.bullet")        # 로케이션 하나 예약 (이름 또는 번호). 한 번만.

k = BulletKind(
    unit=208,             # 만들 유닛 (탄막 유닛). 컴파일 시점 상수
    weapon=127,           # 그 유닛의 지상 무기 — 수명 액션·dat 묶음용 (None 이면 해당 기능 금지)
    flingy=106,           # 무기 flingy — 속도 액션·dat 묶음용
    reverse=True,         # flingy 최고속도가 음수 (사용자 맵 관례). f_bullet_to 와 speed_actions 가 따름
    shell=None,           # 정수면 이 유닛으로 만든 뒤 unitType 만 unit 으로 바꿈 (G2R·GXY 방식)
    recipe="ue_re",       # 생성 뒤 칸 패치 묶음: "ue_re"(정본) | "m2"(M2 Call_CBullet) | "minimal"(GXY)
    remove_timer=None,    # None = recipe 기본 (ue_re 12, m2 30, minimal 없음). 0 = 쓰지 않음
    y_offset=0,           # 로케이션 Y 보정 (ue_re 0, m2/G2R/M1 +10, CA −2)
    dat=None,             # BulletDat(...) 를 주면 init_actions() 가 dat 묶음을 낸다 (5.4)
)

epd = bullet.f_bullet(k, owner, x, y, facing, height=None)       # CreateBullet
epd = bullet.f_bullet_to(k, owner, x, y, tx, ty, height=None)    # CreateBulletXY (1프레임)
epd = bullet.f_bullet_at(k, owner, loc, facing, height=None)     # CreateBulletLoc
# 반환: 만든 유닛 EPD, 슬롯 없음·생성 실패면 0

acts = k.speed_actions(500, halt=None)   # SetBulletSpeed / SetFlingySpeed
acts = k.time_actions(32)                # WeaponTimeLeft
k.set_speed(v); k.set_time(t)            # 변수용 (실행 함수)
acts = k.height_actions(20)              # units.dat elevation[unit 또는 shell] (올바른 주소)
acts = k.init_actions()                  # dat 가 있을 때만. EUDOnStart/1회 구역에서 실행
facing = bullet.heading_to_facing(k, heading)   # 진행 방향 → 유닛 방향 (reverse 면 +128)
```

- `owner`, `x`, `y`, `facing`, `tx`, `ty`, `height` 는 상수·변수 모두 받는다. `facing` 은 **0~255 이외 값도 받아 `& 0xFF`**(음수 포함, UERE 보정과 같은 결과 — 부호 없는 32비트 값의 하위 8비트 = mod 256).
- 조건부 생성(`CreateBulletCond`)·상대 위치(`CreateBulletPosCalc`)는 eudplib 흐름으로 쓴다(4.3).
- epScript: `bullet.bullet(k, P8, x, y, 64);` — `k` 는 `const` 로 묶는다(3.11). (`bullet.f_bullet(…)` 은 `f_f_bullet` 으로 번역된다 — WP14 실측, 2026-09-17 고침)
- 28장 스프라이트류(`f_storm`, `f_perma_sprite`, `f_scan_sprite`, `f_unit_sprite`, `f_recall_sprite`)는 3단계 그대로.

### 5.2 본문 순서 (`f_bullet`, 의사코드)

본문은 **(recipe, y_offset, remove_timer, shell 여부, height 여부) 조합마다 1벌** 캐시한다(3.3). unit·shell 은 상수 인자로 넘긴다(본문 공유).

```
ptr, epd = f_cunitepdread_epd(EPD(0x628438))        # EP81 memio/specialized.py:13~18, 빈 목록이면 (0,0) (memifgen.py:36~42)
if epd == 0: return 0
[height]  SetMemoryX(elevation[shell or unit], SetTo, height)   # 0x663150+u, 바이트 마스크
f_setloc(loc, x, y + y_offset)                                  # EP81 eudlib/locf/locf.py:172
CreateUnit(1, shell or unit, loc, owner)
if f_dwread_epd(EPD(0x628438)) == ptr: return 0                  # 생성 실패 (units.capture 와 같은 판정, DESIGN 4.10)
[shell]   SetMemoryXEPD(epd + 0x64//4, SetTo, unit, 0xFFFF)
pos = f_dwread_epd(epd + 0x28//4)
recipe "ue_re":  +22←pos, +8←facing·256 (0xFF00), +19←135·256 (0xFF00),
                 +40←0 (0xFF000000), +55←0x200104 (0x300104), +57←0, +68←timer (0xFFFF)
recipe "m2":     +4,+6,+7,+22←pos, +8←facing·256 | 127·65536 (0xFFFF00), +19←135·256, +68←timer
recipe "minimal": +22←pos, +8←facing·256, +19←135·256
return epd
```

- `f_bullet_to` = 방향 계산(`mathx.atan2`, `mathx.to_dir256`, reverse 면 +128) 뒤 `f_bullet` 본문으로.
- `facing·256` 은 곱셈 대신 바이트 쓰기(`f_bwrite_epd(epd+8, 1, facing)`, EP81 `memio/bwepdio.py:144`) 등 싼 방법을 구현 때 측정해 고른다.
- 원시 CP 변경 없음. `f_*read_epd` 가 CP 캐시를 복구한다(memifgen.py:62~64). **CP: 바꾸지 않음.** **로컬: 공유 안전**(모든 값이 공유 상태).
- 소유자는 트리거 소유자와 무관(eudplib 는 CP 를 쓰지 않는 `CreateUnit`).

### 5.3 비용 목표 (추측, 구현 뒤 실측)

| 항목 | 목표 | 비교 |
|---|---|---|
| `f_bullet` 본문 | ≤ 40 트리거 (1벌) | GXY 는 호출마다 약 15~20 트리거 인라인(80회) |
| 호출 자리 | ≤ 3 트리거 + 인자 식 | 사용자판 래퍼 1 트리거 + 인자 식 |
| `f_bullet_to` 추가 실행 | atan2 실행(약 8 + 세밀 탐색 ≤ 12, R4b C2) + 표 1 | 사용자판 같음 |
| `speed_actions` | 상수 2~3 액션 | 같음 |

### 5.4 dat 묶음 (`BulletDat`, 선택)

사용자 맵은 EUD Editor 로 정적 수정한다(2.6). eudext 는 **EUD Editor 를 쓰지 않는 새 맵**을 위해 `datpatch`(S5) 위에 얇은 묶음을 둔다.

```python
from eudext.bullet import BulletDat
BulletDat(unit_flingy=88, elevation=20, flyer=True, invincible=True,
          idle_order=None, behavior=9, weapon_flingy=106, top_speed=8000,  # reverse 면 음수로 기록
          accel=8000, halt=1, turn=127, move_control=0,
          damage=…, splash=(…), explosion=3, cooldown=1, remove_after=…)
```

- 기록은 `datpatch` 의 시작 시 1회 목록에 쌓는다(S5). 필드 주소는 EP81 scdata 멤버를 쓴다(`TrgUnit.elevation`, `Weapon.behavior`, `Flingy.topSpeed` 등 — S5 대비표).
- **이미지 iscript(벌처 86)는 바꾸지 않는다**(사용자 맵 관례. CA 28장의 영구 부작용 회피).
- 기본값은 UERE 208 설정(2.6)을 따른다. 필드 목록 확정은 인게임 7절 9 뒤.

### 5.5 스포너 연동 (spawn, S1 에 넘길 것)

M2·G2R 의 옛 G_CA 스포너는 도형 점마다 총알을 쏜다(`RepeatType==101`, 모드 0 목표·1 방향 0·2 방향 표값·3 핵, M2 `func.lua:613~626`). theSeed G_CB 에는 이 분기가 없다(검색 0건). → `spawn.Spawner.push(..., on_point=…)` 콜백에서 `bullet.f_bullet`/`f_bullet_to` 를 부를 수 있게만 하고, 스포너에 총알 전용 옵션은 넣지 않는다. 재진입 주의: `on_point` 안에서 `f_bullet` 을 부르는 것은 괜찮지만 `f_bullet` 안에서 스포너를 부르면 안 된다(3.3).

---

## 6. 시험 기대값

### 6.1 방향 (`bullet_expect.py`, `ctrig_atan2` = `docs\proto\math_sim.py` 참조 구현)

`to_dir256(a) = (floor((a mod 360)·32/45) + 64) mod 256`

| a | 0 | 1 | 44 | 45 | 89 | 90 | 135 | 180 | 225 | 270 | 315 | 359 | 360 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| to_dir256 | 64 | 64 | 95 | 96 | 127 | 128 | 160 | 192 | 224 | 0 | 32 | 63 | 64 |

`f_bullet_to` (reverse=True, 사용자판과 같은 식)

| 출발 | 목표 | atan2(출발−목표) | facing | 진행(+128) |
|---|---|---:|---:|---:|
| (100,100) | (200,100) | 180 | 192 | 64 (동) |
| (100,100) | (100,200) | 270 | 0 | 128 (남) |
| (100,100) | (0,100) | 0 | 64 | 192 (서) |
| (100,100) | (100,0) | 90 | 128 | 0 (북) |
| (100,100) | (200,200) | 226 | 224 | 96 |
| (100,100) | (0,0) | 46 | 96 | 224 |
| (100,100) | (101,102) | 244 | 237 | 109 |
| (2048,1548) | (2048,2048) | 270 | 0 | 128 |
| (0,0) | (32767,1) | 181 | 192 | 64 |
| (100,100) | (100,100) | 90 (추측) | 128 | 0 |

- 시험 방법: `mathx` 시험(WP9)과 같은 참조 구현으로 무작위 좌표 차등. 표 기대값은 `a·32//45` 정수식과 같아야 한다(0~359 전부).
- reverse=False 이면 facing = 위 facing − 128 (mod 256), 같은 점은 예외.

### 6.2 dat 액션 목록 (eudplib 액션 형태, 주소는 4의 배수로 정렬)

| 호출 | 기대 액션 |
|---|---|
| `BulletKind(flingy=158).speed_actions(500)` | `SetMemory(0x6CA170, SetTo, 0xFFFFFE0B)`, `SetMemoryX(0x6C9DB4, SetTo, 500, 0xFFFF)` |
| 같은 것 `halt=1` | + `SetMemory(0x6C9BA8, SetTo, 1)` |
| `flingy=174` `speed_actions(8000)` | `SetMemory(0x6CA1B0, SetTo, 0xFFFFE0BF)`, `SetMemoryX(0x6C9DD4, SetTo, 8000, 0xFFFF)` |
| `flingy=173` 가속도 칸 | `SetMemoryX(0x6C9DD0, SetTo, v<<16, 0xFFFF0000)` (홀수 번호 = 윗 워드) |
| `reverse=False`, `flingy=106`, `speed_actions(8000)` | `SetMemory(0x6CA0A0, SetTo, 8000)`, `SetMemoryX(0x6C9D4C, SetTo, 8000, 0xFFFF)` |
| `weapon=127` `time_actions(32)` | `SetMemoryX(0x6570BC, SetTo, 32<<24, 0xFF000000)` |
| `weapon=30` `time_actions(32)` | `SetMemoryX(0x65705C, SetTo, 32<<16, 0xFF0000)` |
| `weapon=128` `time_actions(64)` | `SetMemoryX(0x6570C0, SetTo, 64, 0xFF)` |
| `unit=208` `height_actions(20)` | `SetMemoryX(0x663220, SetTo, 20, 0xFF)` |
| `unit=206` `height_actions(20)` | `SetMemoryX(0x66321C, SetTo, 20<<16, 0xFF0000)` |
| `shell=204, unit=210` `height_actions(20)` | `SetMemoryX(0x66321C, SetTo, 20, 0xFF)` (shell 칸) |
| 변수 v `set_speed(v)` (flingy 158) | `SetMemory(0x6CA170, SetTo, 0xFFFFFFFF)`, `SetMemory(0x6CA170, Subtract, v)`, `SetMemoryX(0x6C9DB4, SetTo, v, 0xFFFF)` → 에뮬레이터: v=500 → `0xFFFFFE0B`, v=0 → `0xFFFFFFFF` |
| **금지 확인** | 어떤 호출도 `0x656990+unit`(unit ≥ 130)에 쓰지 않는다 |

### 6.3 포인터 처리 (에뮬레이터, DESIGN 5.1 `CreateUnit 기록 + 0x628438 모델` 필요)

- 유닛 i 의 포인터 = `0x59CCA8 + 336·i`, EPD = `19025 + 84·i` (0번 EPD 19025, 사용자판 `Call_CBulletA` 범위 검사 값과 같음).
- 모델: `CreateUnit` 은 `0x628438` 이 0 이 아니면 그 유닛의 +0x28 에 로케이션 중심(가운데 = (L+R)/2, (T+B)/2)을 쓰고 머리를 다음 값으로 바꾼다. 실패 주입 옵션(머리 그대로).

| 경우 | 설정 | 기대 |
|---|---|---|
| 정상 | `0x628438 = 0x59CCA8+336·5`, f_bullet(k ue_re, P8, 1000, 2000, 300) | 반환 19445. CreateUnit 기록 1건(unit, loc, P8), 로케이션 = (1000,2000,1000,2000). `[19445+22] = pos`, `[19445+8] & 0xFF00 = 300&0xFF<<8 = 0x2C00`, `[19445+19] & 0xFF00 = 0x8700`, `[19445+40] & 0xFF000000 = 0`, `[19445+55] & 0x300104 = 0x200104`, `[19445+57] = 0`, `[19445+68] & 0xFFFF = 12` |
| 음수 방향 | facing = −64 (0xFFFFFFC0) | `[+8] & 0xFF00 = 0xC000` (192, UERE 보정과 같은 값) |
| 슬롯 없음 | `0x628438 = 0` | 반환 0, CreateUnit 기록 0건, 메모리 쓰기 0 |
| 생성 실패 | 모델이 머리를 바꾸지 않음 | 반환 0, CUnit 칸 쓰기 0 |
| shell | shell=204, unit=210 | CreateUnit 기록 unit=204, `[+25] & 0xFFFF = 210` |
| y_offset=10 | | 로케이션 T=B=2010 |
| recipe m2 | | `[+4]=[+6]=[+7]=[+22]=pos`, `[+8] & 0xFF0000 = 127<<16`, `[+68] & 0xFFFF = 30`, `+40/+55/+57` 쓰기 없음 |
| CP | 호출 전 CP=P3 | 호출 뒤 CP=P3 |

---

## 7. 인게임 확인 항목 (INGAME_CHECKLIST 로 옮길 것)

1. `f_bullet`(ue_re, 음수 속도 flingy)이 **facing+128** 방향으로 날아간다. 8방향(0,32,…,224) 각각.
2. `f_bullet_to` 가 8방향·가까운 목표(1~2픽셀)·먼 목표(2000픽셀)에서 목표를 지난다. 출발=목표일 때 튕기지 않는다.
3. 슬롯 가득(유닛 1700) 상태에서 호출 → 0 반환, 오류·튕김 없음.
4. 같은 프레임에 같은 flingy 로 다른 속도 → 모두 마지막 속도로 나가는지(문서화용).
5. `y_offset` 0 과 +10 의 발사 위치 차이. **위치 읽기(+0x28)를 빼고 (x, y+보정)을 바로 써도 같은지**(되면 본문에서 읽기 1회 절약, R4a A.5).
6. `ue_re` 추가 칸의 필요성: `+0xA3←0`, `+0xDC` 플래그, `+0xE4←0` 을 하나씩 빼 보고 차이(드래그·선택·충돌·시야)를 적는다. 의도 미상인 `+0xA3`(energy 윗바이트) 특히.
7. 수명 12 / 30 / 쓰지 않음: 발사 뒤 탄막 유닛이 남는지, 주문 135 가 유닛을 없애는지.
8. `shell` 방식(204 로 만들고 종류 교체)에서 **바뀐 종류의 무기**로 쏘는지.
9. `height_actions`(올바른 elevation 주소)로 총알 높이·그리기 층이 바뀌는지. 생성 전에 써야 하는지 뒤에 써도 되는지.
10. 소유자 사람/컴퓨터: 시야·총알 4096 표시 한도(GB 8605~8610).
11. `[unlimiter]` 켬/끔에서 한 프레임 80발 이상(UERE `Sans.lua` 패턴 규모).
12. 2인 이상 멀티에서 디싱크 없음(공유 상태만 씀).
13. `BulletDat` 로만 설정한(EUD Editor 없이) 새 맵에서 UERE 208 과 같은 모양·동작.

---

## 8. 함정 (구현자에게)

- **높이 버그를 옮기지 말 것**(4.1). 올바른 칸은 `0x663150 + 유닛`(전역 dat).
- **방향의 뜻**: `facing` 은 유닛 방향이다. 음수 속도 관례 때문에 진행 방향과 128 다르다. docstring 첫 줄에 적는다.
- **eudplib `f_atan2`/`f_atan2_256` 을 쓰지 말 것**: 반올림·기준이 다르다(R4b C4·C5). `mathx.atan2`(CtrigAsm 동일)만.
- **`EUDVariable << x` 는 대입**이다(eudplib). `facing << 8` 로 시프트하려 하면 안 된다(DESIGN 3.2-5).
- 속도·수명은 전역 dat → 같은 프레임 공유(4.4).
- 언리미터: eudext 는 `IsUnlimiterOn()`(EP81 `eudlib/utilf/unlimiterflag.py:23`, 최상위 export 없음 → `_compat`)으로 켜짐을 알 수 있다. euddraft 0.11 이 플러그인 이름에 "unlimiter" 가 있으면 켠다(`upstream\euddraft\pluginLoader.py:100~104`). 총알 생성 자체는 이 값이 필요 없다. 다만 **언리미터에서 `CSprite.from_read` 는 여전히 틀린 포인터**(0.81 `memio/specialized.py:42~47` 가 0x620000 기준 마스크) → 총알 모듈에서 스프라이트를 읽지 않는다.
- `CUnit.is_dying()` 은 언리미터에서 컴파일 오류(EP81 `scdata/cunit.py:856~864`) → 탄막 유닛 수명 판정에 쓰지 말 것.
- `f_cunitepdread_epd` 는 0.81 에서 빈 목록일 때 (0,0) 을 준다(`_check_empty`). 0.76.14 에는 없던 동작이므로 판 검사(`_compat`)에 적는다.
- CUnit 칸 쓰기는 `SetMemoryXEPD(epd + k, …)` 로. `SetMemory(ptr + off, …)`(GXY 방식)는 호출마다 EPD 나눗셈을 만든다.
- 스포너 콜백 안 재진입(5.5).

---

## 9. DESIGN.md 수정 제안

1. **4.15 API** 를 5.1 로 바꾼다: `f_bullet(kind, owner, x, y, facing, height=None)`, `f_bullet_to(kind, owner, x, y, tx, ty, height=None)`, `f_bullet_at`, `BulletKind(unit, weapon, flingy, reverse=True, shell=None, recipe="ue_re", remove_timer=None, y_offset=0, dat=None)`, `speed_actions/time_actions/height_actions/init_actions`, `heading_to_facing`. 초안의 `speed`, `time` 인자는 **뺀다**(사용자판은 전역 헬퍼로 따로 준다, 4.4). 초안의 `BulletKind(sprite=, image=, iscript=)` 는 `BulletDat` 로 옮기고 iscript 는 뺀다.
2. **4.15 의미·제약**에 추가: "`facing` 은 유닛 방향. 음수 최고속도 flingy(사용자 관례, `reverse=True`)에서는 진행 방향 = facing+128", "높이 인자의 올바른 주소는 units.dat elevation(사용자판은 모두 틀린 칸)".
3. **4.15 근거**의 "6개 폴더" 를 "6계통(M2=BRZ, UERE=UE, G2R=G2, M1, GXY, NTM1 속도만)" 으로 고치고, theSeed·Stella_II·Respect_V·MEME·DPS·템플릿은 0건이라고 적는다. 호출 수는 주요 4맵 97(PosCalc 포함).
4. **4.15 선행 작업**: "S4 완료(`docs/spec/S4_bullet.md`)".
5. **4.5 mathx**: `to_dir256(a, cycle=360)` 의 정의를 `(floor((a mod cycle)·256/cycle) + cycle/4 환산 64) mod 256` 으로 못박는다(사용자 표 = TEP 0 방향 자르기, 2.3). 음수 a 는 `CiMod` 규칙으로 먼저 0~cycle−1.
6. **4.10 units**: `capture()` 의 `ok` 판정을 bullet 이 재사용한다고 적는다(의존 WP10 → WP14 이미 있음).
7. **4.14 spawn**: 옛 G_CA 의 `RepeatType 101`(탄막) 분기는 `on_point` 콜백으로 대체한다고 한 줄(5.5).
8. **5.1 scmodel 표**의 "CreateUnit 기록 + 0x628438 모델" 필요 모듈에 `bullet` 추가, 실패 주입 옵션 명시.
9. **6.1 WP14** 추가 완료 조건: "6.2·6.3 기대값 통과, 7절 1·2·3 인게임".
10. **3.9 금지 목록**에 "`0x656990+unit`(weapons attackAngle 에 유닛 번호) 쓰기" 는 필요 없음 — 대신 4.15 위험에 한 줄.

---

## 10. 미확인

- 주문 135 가 발사 뒤 유닛을 없애는지, 수명(`+0x110`)이 없어도 사라지는지(M1·UE·GXY 는 수명을 쓰지 않음). (추측: 자폭 주문이라 사라짐, GB 7972 "자폭명령")
- `+0xA3 ← 0`, `+0xDC`, `+0xE4` 쓰기의 목적(7절 6).
- 음수 최고속도가 뒤로 나는 원리와, 가속도를 속도와 같게 두는 이유(R4a A.8 도 미확인).
- Y 보정 +10 의 이유(공중 유닛 그리기 보정으로 추측), CA 의 −2 와 차이.
- 발사 순간에 dat(속도·수명)를 읽는지, 생성 순간에 읽는지(4.4 함정의 전제).
- `f_Atan2(0,0)` 의 실제 출력(CtrigAsm 0 나눗셈 몫).
- G2R·M1 의 정적 dat(탄막 유닛 204 설정)가 어디에 있는지(EUDEditorDat 없음, 맵 파일 안으로 추측). G2R·M1 의 언리미터 사용 여부.
- `unitType` 교체 뒤 무기를 새 종류에서 읽는지(7절 8).
- UERE 의 flingy 158 이 어느 무기에 쓰이는지(무기 127→106, 128→164 이고 `SetWeaponsDat(…,128,{FlingyID=158,…})` 로 런타임에 158 로 바꾸는 곳이 있음 — UERE `Sans.lua:78`). 즉 flingy 는 런타임에도 바뀐다 → `BulletKind.flingy` 는 "속도 액션 대상" 일 뿐 무기 설정과 어긋날 수 있다.
- 에뮬레이터가 `CreateUnit` 을 흉내 내는 방법(5.1 scmodel)이 아직 없다 → 6.3 은 모델 구현 뒤 확정.
