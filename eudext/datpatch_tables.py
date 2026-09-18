"""`eudext.datpatch` 가 쓰는 표 (DESIGN 4.16, docs/spec/S5_dat_bgm.md A.2·A.4·A.7).

- dat 종류 표 `DATS`: 이름 → (scdata 클래스, 번호 인코더). 원소 수는 scdata 클래스의 `range` 에서 읽는다.
- eudext 전용 필드 `EXTRA_FIELDS`: scdata 로 안 되는 칸(A.4 의 N·P)만 적는다. scdata 필드는 여기 적지 않고
  `datpatch` 가 import 때 scdata 디스크립터에서 주소·크기·간격을 읽어 만든다(중복 기재 금지, A.7).
- 원소 수 보정 `COUNT_OVERRIDE`: scdata 에 표현이 없는 106칸 필드(A.2.1 주석).
- TEP 키 표 `TEP_*`: 템플릿 `func.lua`(정본, reference/MSF-Template/func.lua:27~264)와 theSeed 판
  (reference/theSeed/Engine/func.lua:33~535, 필드가 가장 많음)의 키 → scdata 이름과 변환.

이 모듈은 트리거를 만들지 않는다(컴파일 시점 자료만). 맵 코드는 `eudext.datpatch` 를 쓴다.
"""

# ---------------------------------------------------------------------------------------------
# dat 종류
# ---------------------------------------------------------------------------------------------

# 키: datpatch 가 쓰는 표 이름. (scdata 클래스 이름, eudplib 번호 인코더 이름, 별칭들)
DATS = {
    "units": ("TrgUnit", "EncodeUnit", ("unit", "units.dat", "TrgUnit")),
    "weapons": ("Weapon", "EncodeWeapon", ("weapon", "weapons.dat", "Weapon")),
    "flingy": ("Flingy", "EncodeFlingy", ("flingy.dat", "Flingy")),
    "upgrades": ("Upgrade", "EncodeUpgrade", ("upgrade", "upgrades.dat", "Upgrade")),
    "techdata": ("Tech", "EncodeTech", ("tech", "techdata.dat", "Tech")),
    "sprites": ("Sprite", "EncodeSprite", ("sprite", "sprites.dat", "Sprite")),
    "images": ("Image", "EncodeImage", ("image", "images.dat", "Image")),
}

# dat 가 아닌 표 (플레이어별 표, 피해 배율). 번호는 정수만 받는다.
PSEUDO_DATS = {
    "players": ("players", "player_table"),
    "damage": ("damage_ratio", "damageRatio"),
}

# 명세(A.2)에 적힌 원소 수. 시험이 scdata `range` 와 대조한다.
SPEC_COUNTS = {"units": 228, "weapons": 130, "flingy": 209, "upgrades": 61, "techdata": 44, "sprites": 517, "images": 999}

# ---------------------------------------------------------------------------------------------
# 원소 수 보정 (scdata 는 클래스 range 만 있어 106칸 필드를 표현하지 못한다, S5 A.2.1)
# ---------------------------------------------------------------------------------------------

# 근거: units.dat 배열 배치. 0x663C10 + 106*2 = 0x663CE4 → 다음 배열 supplyUsed(0x663CE8),
# 0x661FC0 + 228*2 = 0x662188 이면 rightClickAction(0x662098)·sizeType(0x662180) 과 겹친다 → 106칸.
COUNT_OVERRIDE = {
    ("units", "readySound"): 106,
    ("units", "yesSoundStart"): 106,
    ("units", "yesSoundEnd"): 106,
    ("units", "pissedSoundStart"): 106,
    ("units", "pissedSoundEnd"): 106,
}

# ---------------------------------------------------------------------------------------------
# eudext 전용 필드 (A.4: scdata 로 안 되는 것만)
# ---------------------------------------------------------------------------------------------
# 항목: (dat, 이름, 주소, 크기, 간격, 첫 번호, 원소 수, 비고)
#  주소가 ("member", scdata 이름, 더할 값) 이면 scdata 디스크립터의 offset 에서 읽는다(중복 기재 피함).
#  원소 수 None = 그 dat 의 원소 수.

READONLY_SCR_NOTE = "SC:R 에서 읽기 전용일 수 있음(eud-book 표기, 인게임 미확인)"

EXTRA_FIELDS = (
    # units — P 필드: buildingDimensions(dword 통째)의 X/Y 워드
    ("units", "buildingDimX", ("member", "buildingDimensions", 0), 2, 4, 0, None, "buildingDimensions 하위 워드 (TEP BdDimX)"),
    ("units", "buildingDimY", ("member", "buildingDimensions", 2), 2, 4, 0, None, "buildingDimensions 상위 워드 (TEP BdDimY)"),
    # units — P 필드: 0x660178 바이트 통째 (scdata 는 비트 0·1 두 멤버로 나눴다)
    ("units", "computerAI", ("member", "ignoreStrategicSuicideMissions", 0), 1, 1, 0, None, "AI 바이트 통째 (TEP ComputerAI)"),
    # units — N 필드
    ("units", "subunit2", 0x660C38, 2, 2, 0, None, "게임에서 쓰지 않음 (scdata unit.py 주석)"),
    ("units", "addonPlacement", ("member", "addonPlacement", 0), 4, 4, 106, 96, "건물 전용(106~201), X|Y<<16"),
    ("units", "addonPlacementX", ("member", "addonPlacement", 0), 2, 4, 106, 96, "건물 전용(106~201)"),
    ("units", "addonPlacementY", ("member", "addonPlacement", 2), 2, 4, 106, 96, "건물 전용(106~201)"),
    ("units", "infestationUnit", 0x664980, 2, 2, 106, 96, "건물 전용(106~201)"),
    # weapons — N 필드
    ("weapons", "specialAttack", 0x6573E8, 1, 1, 0, None, "참고용(게임에서 쓰지 않음, scdata weapon.py 주석)"),
    # images — N 필드 (theSeed SetImageDatX, scdata image.py 주석 이름)
    ("images", "grpFile", 0x668AA0, 4, 4, 0, None, READONLY_SCR_NOTE),
    ("images", "shieldsOverlay", 0x66C538, 4, 4, 0, None, READONLY_SCR_NOTE),
    ("images", "attackOverlay", 0x66B1B0, 4, 4, 0, None, READONLY_SCR_NOTE),
    ("images", "damageOverlay", 0x66A210, 4, 4, 0, None, READONLY_SCR_NOTE),
    ("images", "specialOverlay", 0x667B00, 4, 4, 0, None, READONLY_SCR_NOTE),
    ("images", "landingDustOverlay", 0x666778, 4, 4, 0, None, READONLY_SCR_NOTE),
    ("images", "liftOffDustOverlay", 0x66D8C0, 4, 4, 0, None, READONLY_SCR_NOTE),
    # 플레이어별 생산 가능 표 (dat 아님): 0x57F27C + 플레이어·228 + 유닛 (TEP Playerable, CtrigAsm SetUnitAvailable)
    ("players", "unitAvailability", 0x57F27C, 1, 1, 0, 228 * 12, "번호 = 플레이어·228 + 유닛 (플레이어 0~11)"),
    # 피해 배율 (dat 아님): 0x515B88 + 0x14·피해형 + 4·크기 (CtrigAsm SetDamageMultiplier, theSeed SetDamageRatio)
    ("damage", "ratio", 0x515B88, 4, 4, 0, 25, "번호 = 피해형·5 + 크기, 256 = 1배. 주소 인게임 미확인(eudplib 주석은 0x515B84)"),
)

# 사용할 때 한 번 경고하는 필드 (인게임 확인 전)
WARN_FIELDS = {
    ("damage", "ratio"): "피해 배율 표 주소 0x515B88 은 CtrigAsm·theSeed 값이고 인게임 확인 전입니다(eudplib 주석은 0x515B84, S5 A.9-4)",
    ("images", "grpFile"): READONLY_SCR_NOTE,
    ("images", "shieldsOverlay"): READONLY_SCR_NOTE,
    ("images", "attackOverlay"): READONLY_SCR_NOTE,
    ("images", "damageOverlay"): READONLY_SCR_NOTE,
    ("images", "specialOverlay"): READONLY_SCR_NOTE,
    ("images", "landingDustOverlay"): READONLY_SCR_NOTE,
    ("images", "liftOffDustOverlay"): READONLY_SCR_NOTE,
}

# 기본 비트 이름 표 (flags() 에 필드 이름을 주지 않았을 때)
DEFAULT_FLAG_FIELD = {"units": "baseProperty", "weapons": "targetFlags"}

# 피해 배율 표 크기 (theSeed DAMAGE_TYPE_DESIGN.md: 5행 × 5열, 행 간격 0x14)
DAMAGE_TYPES = 5
DAMAGE_SIZES = 5

# 플레이어별 표의 플레이어 수 (PUNI 와 같게 12)
PLAYER_COUNT = 12
UNIT_COUNT = 228

# ---------------------------------------------------------------------------------------------
# A.2 주소 스냅숏 (시험이 scdata 디스크립터 값과 대조한다: TEP 키 → (기준 주소, 폭))
# ---------------------------------------------------------------------------------------------

SPEC_TEP_ADDR = {
    "units": {
        "MinCost": (0x663888, 2), "GasCost": (0x65FD00, 2), "BuildTime": (0x660428, 2),
        "SuppCost": (0x663CE8, 1), "SuppProv": (0x6646C8, 1), "HP": (0x662350, 4),
        "Armor": (0x65FEC8, 1), "DefType": (0x662180, 1), "DefUpType": (0x6635D0, 1), "Height": (0x663150, 1),
        "BdDimX": (0x662860, 2), "BdDimY": (0x662862, 2),
        "SizeL": (0x6617C8, 2), "SizeU": (0x6617CA, 2), "SizeR": (0x6617CC, 2), "SizeD": (0x6617CE, 2),
        "AdvFlag": (0x664080, 4), "StarEditFlag": (0x661518, 2), "GroupFlag": (0x6637A0, 1),
        "MovementFlag": (0x660FC8, 1), "ComputerAI": (0x660178, 1), "Class": (0x663DD0, 1), "Graphic": (0x6644F8, 1),
        "AirWeapon": (0x6616E0, 1), "GroundWeapon": (0x6636B8, 1), "SeekRange": (0x662DB8, 1),
        "SightRange": (0x663238, 1), "SpaceProv": (0x660988, 1), "SpaceReq": (0x664410, 1), "RClickAct": (0x662098, 1),
        "HumanInitAct": (0x662268, 1), "ComputerInitAct": (0x662EA0, 1), "IdleOrder": (0x664898, 1),
        "AttackOrder": (0x663320, 1), "AttackMoveOrder": (0x663A50, 1), "RdySnd": (0x661FC0, 2),
        "WhatSndInit": (0x662BF0, 2), "WhatSndEnd": (0x65FFB0, 2),
        "YesInit": (0x663C10, 2), "YesEnd": (0x661440, 2), "PissedInit": (0x663B38, 2), "PissedEnd": (0x661EE8, 2),
        "BuildScore": (0x663408, 2), "KillScore": (0x663EB8, 2), "Reqptr": (0x660A70, 2),
        "MaxHitsAir": (0x65FC18, 1), "MaxHitsGround": (0x6645E0, 1), "MapString": (0x660260, 2),
        "StartDirection": (0x6605F0, 1), "BroodWarFlag": (0x6606D8, 1), "Subunit1": (0x6607C0, 2),
        "Subunit2": (0x660C38, 2), "ConstructionAnimation": (0x6610B0, 4), "Portrait": (0x662F88, 2),
        "InfestationUnit": (0x664980, 2),
    },
    "weapons": {
        "DmgBase": (0x656EB0, 2), "DmgFactor": (0x657678, 2), "Cooldown": (0x656FB8, 1), "ObjectNum": (0x6564E0, 1),
        "Effect": (0x6566F8, 1), "DamageType": (0x657258, 1), "RangeMin": (0x656A18, 4), "RangeMax": (0x657470, 4),
        "TargetFlag": (0x657998, 2), "UpgradeType": (0x6571D0, 1), "IconType": (0x656780, 2),
        "Behavior": (0x656670, 1), "LaunchX": (0x657910, 1), "LaunchY": (0x656C20, 1), "LaunchSpin": (0x657888, 1),
        "AttackAngle": (0x656990, 1), "RemoveAfter": (0x657040, 1), "FlingyID": (0x656CA8, 4),
        "WepName": (0x6572E0, 2), "TargetErrorMessage": (0x656568, 2), "SpecialAttack": (0x6573E8, 1),
    },
    "upgrades": {
        "Reqptr": (0x6558C0, 2), "MaxLevel": (0x655700, 1), "MinCost": (0x655740, 2), "MinFactor": (0x6559C0, 2),
        "GasCost": (0x655840, 2), "GasFactor": (0x6557C0, 2), "TimeCost": (0x655B80, 2), "TimeFactor": (0x655940, 2),
    },
    "flingy": {
        "Speed": (0x6C9EF8, 4), "Acceleration": (0x6C9C78, 2), "HaltDistance": (0x6C9930, 4),
        "TurnRadius": (0x6C9E20, 1), "MovementControl": (0x6C9858, 1),
    },
    "sprites": {"ImageFile": (0x666160, 2), "IsVisible": (0x665C48, 1)},
    "images": {
        "GRPFile": (0x668AA0, 4), "IscriptID": (0x66EC48, 4), "GraphicsTurns": (0x66E860, 1),
        "Clickable": (0x66C150, 1), "UseFullIscript": (0x66D4D8, 1), "DrawIfCloaked": (0x667718, 1),
        "SpecialOverlay": (0x667B00, 4), "DamageOverlay": (0x66A210, 4), "AttackOverlay": (0x66B1B0, 4),
        "ShieldsOverlay": (0x66C538, 4), "LandingDustOverlay": (0x666778, 4),
    },
}

# ---------------------------------------------------------------------------------------------
# TEP 키 표
# ---------------------------------------------------------------------------------------------
# 값: (필드 이름, 곱할 수, 폭 덮어쓰기) — 폭 덮어쓰기는 TEP 가 scdata 멤버보다 넓게 쓰는 경우(바이트·dword 통째).
# 특수 키(Shield, Splash, AdvFlag, Playerable, Reqptr, AddonPlacement, IsVisible, 비트 이름)는 datpatch.Tep 이 처리한다.

TEP_UNITS = {
    "MinCost": ("mineralCost", 1, None),
    "GasCost": ("gasCost", 1, None),
    "BuildTime": ("timeCost", 1, None),
    "SuppCost": ("supplyUsed", 2, None),  # TPL func.lua:154 k*2
    "SuppProv": ("supplyProvided", 1, None),
    "HP": ("maxHp", 256, None),  # TPL func.lua:156 k*256
    "Armor": ("armor", 1, None),
    "DefType": ("sizeType", 1, None),
    "DefUpType": ("armorUpgrade", 1, None),
    "Height": ("elevation", 1, None),
    "BdDimX": ("buildingDimX", 1, None),
    "BdDimY": ("buildingDimY", 1, None),
    "SizeL": ("unitBoundsL", 1, None),
    "SizeU": ("unitBoundsT", 1, None),
    "SizeR": ("unitBoundsR", 1, None),
    "SizeD": ("unitBoundsB", 1, None),
    "StarEditFlag": ("availabilityFlags", 1, None),
    "GroupFlag": ("groupFlags", 1, None),
    "MovementFlag": ("movementFlags", 1, None),
    "ComputerAI": ("computerAI", 1, None),
    "Class": ("rank", 1, None),
    "Graphic": ("flingy", 1, None),
    "AirWeapon": ("airWeapon", 1, None),
    "GroundWeapon": ("groundWeapon", 1, None),
    "SeekRange": ("seekRange", 1, None),
    "SightRange": ("sightRange", 1, None),
    "SpaceProv": ("transportSpaceProvided", 1, None),
    "SpaceReq": ("transportSpaceRequired", 1, None),
    "RClickAct": ("rightClickAction", 1, None),
    "HumanInitAct": ("humanIdleOrder", 1, None),
    "ComputerInitAct": ("computerIdleOrder", 1, None),
    "IdleOrder": ("returnToIdleOrder", 1, None),
    "AttackOrder": ("attackUnitOrder", 1, None),
    "AttackMoveOrder": ("attackMoveOrder", 1, None),
    "RdySnd": ("readySound", 1, None),
    # D19: TEP 이름이 eudplib·EUD Editor 와 반대다. TEP 주소를 그대로 쓰고 경고한다 (S5 A.2.1).
    "WhatSndInit": ("whatSoundEnd", 1, None),  # 0x662BF0
    "WhatSndEnd": ("whatSoundStart", 1, None),  # 0x65FFB0
    "YesInit": ("yesSoundStart", 1, None),
    "YesEnd": ("yesSoundEnd", 1, None),
    "PissedInit": ("pissedSoundStart", 1, None),
    "PissedEnd": ("pissedSoundEnd", 1, None),
    "BuildScore": ("buildScore", 1, None),
    "KillScore": ("killScore", 1, None),
    # theSeed 판에만 있는 키 (Engine/func.lua:354~382)
    "MaxHitsAir": ("maxAirHits", 1, None),
    "MaxHitsGround": ("maxGroundHits", 1, None),
    "MapString": ("nameString", 1, None),
    "StartDirection": ("startDirection", 1, None),
    "BroodWarFlag": ("broodWarFlag", 1, None),
    "Subunit1": ("subUnit", 1, None),
    "Subunit2": ("subunit2", 1, None),
    "ConstructionAnimation": ("constructionGraphic", 1, 4),  # TEP 는 dword 통째 (scdata 멤버는 워드)
    "Portrait": ("portrait", 1, None),
    "InfestationUnit": ("infestationUnit", 1, None),
}

TEP_UNIT_SPECIAL = ("Shield", "AdvFlag", "Playerable", "Reqptr", "AddonPlacement")

TEP_WHATSOUND = {"WhatSndInit": "whatSoundStart", "WhatSndEnd": "whatSoundEnd"}  # 경고 문구용: 뜻대로 쓰려면

# theSeed AdvFlagBitArr (Engine/func.lua:180~189). 값 = 그 비트 마스크.
TEP_ADV_FLAG_BITS = {
    "Building": 0x00000001, "Addon": 0x00000002, "Flyer": 0x00000004, "Worker": 0x00000008,
    "Subunit": 0x00000010, "FlyingBuilding": 0x00000020, "Hero": 0x00000040, "RegeneratesHP": 0x00000080,
    "AnimatedIdle": 0x00000100, "Cloakable": 0x00000200, "TwoUnitsInEgg": 0x00000400, "SingleEntity": 0x00000800,
    "ResourceDepot": 0x00001000, "ResourceContainer": 0x00002000, "RoboticUnit": 0x00004000, "Detector": 0x00008000,
    "OrganicUnit": 0x00010000, "RequiresCreep": 0x00020000, "RequiresPsi": 0x00080000, "Burrowable": 0x00100000,
    "Spellcaster": 0x00200000, "PermanentCloak": 0x00400000, "PickupItem": 0x00800000, "IgnoreSupplyCheck": 0x01000000,
    "UseMediumOverlays": 0x02000000, "UseLargeOverlays": 0x04000000, "BattleReactions": 0x08000000,
    "FullAutoAttack": 0x10000000, "Invincible": 0x20000000, "MechanicalUnit": 0x40000000, "ProducesUnits": 0x80000000,
}

TEP_WEAPONS = {
    "DmgBase": ("damage", 1, None),
    "DmgFactor": ("damageBonus", 1, None),
    "Cooldown": ("cooldown", 1, None),
    "Effect": ("explosionType", 1, None),
    "DamageType": ("damageType", 1, None),
    "DmgType": ("damageType", 1, None),  # DPS 판 키 (DPS_eud function.lua:277)
    "RangeMin": ("minRange", 1, None),
    "RangeMax": ("maxRange", 1, None),
    "TargetFlag": ("targetFlags", 1, None),
    "UpgradeType": ("upgrade", 1, None),
    "ObjectNum": ("damageFactor", 1, None),
    "IconType": ("icon", 1, None),
    "Behavior": ("behavior", 1, None),
    "LaunchX": ("forwardOffset", 1, None),
    "LaunchY": ("verticalOffset", 1, None),
    "LaunchSpin": ("launchSpin", 1, None),
    "AttackAngle": ("attackAngle", 1, None),
    "RemoveAfter": ("removeAfter", 1, None),
    "FlingyID": ("flingy", 1, 4),  # TEP 는 dword 통째 (scdata 멤버는 바이트, 간격 4)
    "WepName": ("label", 1, None),
    "TargetErrorMessage": ("targetErrorMessage", 1, None),
    "SpecialAttack": ("specialAttack", 1, None),
}

TEP_WEAPON_SPECIAL = ("Splash",)

TEP_UPGRADES = {
    "Reqptr": ("requirementOffset", 1, None),  # theSeed 판은 업그레이드 Reqptr 를 실제로 쓴다(func.lua:405)
    "MaxLevel": ("maxLevel", 1, None),
    "MinCost": ("mineralCostBase", 1, None),
    "MinFactor": ("mineralCostFactor", 1, None),
    "GasCost": ("gasCostBase", 1, None),
    "GasFactor": ("gasCostFactor", 1, None),
    "TimeCost": ("timeCostBase", 1, None),
    "TimeFactor": ("timeCostFactor", 1, None),
}

TEP_FLINGY = {
    "Speed": ("topSpeed", 1, None),
    "Acceleration": ("acceleration", 1, None),
    "HaltDistance": ("haltDistance", 1, None),
    "TurnRadius": ("turnSpeed", 1, None),
    "MovementControl": ("movementControl", 1, None),
}

TEP_SPRITES = {
    "ImageFile": ("image", 1, None),
}

TEP_SPRITE_SPECIAL = ("IsVisible",)

TEP_IMAGES = {
    "GRPFile": ("grpFile", 1, None),
    "IscriptID": ("iscript", 1, None),
    "GraphicsTurns": ("isTurnable", 1, 1),  # TEP 는 바이트 통째 (scdata 멤버는 비트 0)
    "Clickable": ("isClickable", 1, 1),
    "UseFullIscript": ("useFullIscript", 1, 1),
    "DrawIfCloaked": ("drawIfCloaked", 1, 1),
    "SpecialOverlay": ("specialOverlay", 1, None),
    "DamageOverlay": ("damageOverlay", 1, None),
    "AttackOverlay": ("attackOverlay", 1, None),
    "ShieldsOverlay": ("shieldsOverlay", 1, None),
    "LandingDustOverlay": ("landingDustOverlay", 1, None),
}

# SetUnitAbility (TPL func.lua:316~456) 상수
ABILITY_SUBUNIT_OWNERS = (3, 5, 17, 23, 25, 30)  # 서브유닛(번호+1)에 무기를 주는 유닛
ABILITY_AIR_SAME = (62, 58, 98, 86, 124)  # 공중 무기 = 지상 무기
ABILITY_COLOR = {1: 0x11, 2: 0x1D, 3: 0x1B, 4: 0x1F}
