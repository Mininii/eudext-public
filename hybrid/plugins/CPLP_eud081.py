# [eudext hybrid] euddraft 0.11 / eudplib 0.81 사본 — 원본 CPLP.py (md5 01ee95cbed7b420effd2e13184887c7e, 줄 끝 LF 기준).
# hybrid/make_plugins.py 가 만든다. 손으로 고치지 말 것 (규칙은 그 파일의 머리 주석).
from eudplib import *
# from eudx import *  # eudplib 0.81: eudx.py 는 0.76 전용 인자를 써서 실패. 쓰는 함수는 eudplib 에 있다 (eudext hybrid)
import math
import random

def f_epdread_epd1(targetplayer, mask, _readerdict={}):
	if mask in _readerdict:
		readerf = _readerdict[mask]
	else:
		def bits(n):
			while n:
				b = n & (~n+1)
				yield b
				n ^= b

		@EUDFunc
		def readerf(targetplayer):

			f_setcurpl(targetplayer)

			ret = EUDVariable()
			ret << 0
			# Fill flags
			for i in bits(mask):
				RawTrigger(
					conditions=[
						DeathsX(CurrentPlayer, Exactly, i, 0, i)
					],
					actions=[
						ret.AddNumber(i//4)
					]
				)

			return ret

		_readerdict[mask] = readerf

	return readerf(targetplayer)

def f_epdread_epd2(targetplayer, mask, _readerdict={}):
	if mask in _readerdict:
		readerf = _readerdict[mask]
	else:
		def bits(n):
			while n:
				b = n & (~n+1)
				yield b
				n ^= b

		@EUDFunc
		def readerf(targetplayer):

			f_setcurpl(targetplayer)

			ret = EUDVariable()
			ret << -1452249
			# Fill flags
			for i in bits(mask):
				RawTrigger(
					conditions=[
						DeathsX(CurrentPlayer, Exactly, i, 0, i)
					],
					actions=[
						ret.AddNumber(i//4)
					]
				)

			return ret

		_readerdict[mask] = readerf

	return readerf(targetplayer)

def GetMPQepd():
	A = EUDVariable()
	A << -1488059	#0x4FE544
	return f_epdread_epd2(f_epdread_epd1(A*4+0x58A364,0xFFFFFFFF)+0xFFEABC26,0xFFFFFFFF)

def LAdd(Xh,Xl,Yh,Yl):
	Rl, Rh = EUDCreateVariables(2)
	Rl << Xl + Yl
	Rh << Xh + Yh + 1
	if EUDIf()((Rl >= Xl)):
	   Rh << Rh - 1
	EUDEndIf()
	return Rh, Rl

def LiSub(Xh,Xl,Yh,Yl):
	Rl, Rh = EUDCreateVariables(2)
	Yl = 0xFFFFFFFF - Yl
	Yh = 0xFFFFFFFF - Yh
	Yh, Yl = LAdd(Yh,Yl,0,1)
	Rh, Rl = LAdd(Xh,Xl,Yh,Yl)
	return Rh, Rl

def DropType1():
	Nextptr = EUDVariable()
	Ret = EUDVariable()
	if EUDWhile()(True):
		Nextptr << f_maskread_epd(EPD(0x628438),0xFFFFFFFF)
	EUDEndWhile()
	Ret << 0xFFFFFFFF
	return Ret

def DropType2():
	global LocID1, LocID2
	LocID1 = random.randrange(0,256)
	LocID2 = random.randrange(0,256)
	X = EUDVariable()
	Y = EUDVariable()
	A1 = Forward()
	A2 = RawTrigger(
		nextptr=A1,
		actions=[
					SetMemory(0x58DC60 + 0x14*LocID1 + 0, SetTo, 0),
					SetMemory(0x58DC60 + 0x14*LocID1 + 4, SetTo, 0),
					SetMemory(0x58DC60 + 0x14*LocID1 + 8, SetTo, 0),
					SetMemory(0x58DC60 + 0x14*LocID1 + 12, SetTo, 0),
					MoveLocation(LocID1,20,0,LocID2),
				]
			 )
	X << f_maskread_epd(EPD(0x58DC60+0x14*LocID1),0xFFFFFFFF)
	Y << f_maskread_epd(EPD(0x58DC64+0x14*LocID1),0xFFFFFFFF)
	A1 << RawTrigger(nextptr=A2,actions=[X.AddNumber(1024),Y.AddNumber(1024)])
	return X

def DropType3():
	B1 = Forward()
	B2 = Forward()
	global LocID3, LocID4
	LocID3 = random.randrange(0,256)
	LocID4 = random.randrange(0,256)
	Speed = EUDVariable()
	B0 = RawTrigger(nextptr=B1)
	B4 = RawTrigger()
	Speed << f_maskread_epd(EPD(0x5124F0),0xFFFFFFFF)
	B5 = RawTrigger(nextptr=B2)
	B1 << RawTrigger(nextptr=B2)

	B3 = Forward()
	B2 << RawTrigger(
		nextptr=B3,
		conditions=[Bring(P1,Exactly,1,"(men)",LocID3)],
		actions=[
				   MoveUnit(1,"(men)",P1,LocID3,LocID4),
				   SetMemory(0x5124F0,SetTo,21),
				]
			 )
	B3 << RawTrigger(nextptr=B4,actions=[Speed.SetNumber(21)])
	return Speed

def onPluginStart(): # CustomPlibLockProtector v1.0 Made by Ninfia
	X, Y, Z = EUDCreateVariables(3)
	CZ = Forward()
	END = Forward()
	C0 = Forward()
	CY = Forward()
	CX = RawTrigger(nextptr=CY)
	C0 << RawTrigger(nextptr=CY)
	CY << NextTrigger()
	
	mpqEPD, MPQ, HET, BET, mpq, bet, mpqEPD2, MPQoff, MPQEND = EUDCreateVariables(9)
	mpqEPD << GetMPQepd()
	mpqEPD2 << mpqEPD + 1
	mpq << 38
	mpq << mpq + 38
	bet << 0x138//2
	bet << bet - mpq
	MPQoff << bet * mpq + 0x1A40
	MPQ << f_epdread_epd2(mpqEPD+mpq,0xFFFFFFFF)
	BET << f_epdread_epd2(mpqEPD2+mpq,0xFFFFFFFF)
	HET << f_epdread_epd2(mpqEPD+bet-2,0xFFFFFFFF)


	k1l, k1h, k2l, k2h, kkk = EUDCreateVariables(5)
	k2h << f_maskread_epd(BET+0x4DEC//4+MPQoff//4,0xFFFFFFFF)	
	DoActions([MPQoff.AddNumber(0x1000)])
	k1l << f_maskread_epd(BET+0x3DE0//4+MPQoff//4,0xFFFFFFFF) - MPQoff
	k1h << f_maskread_epd(BET+0x3DE4//4+MPQoff//4,0xFFFFFFFF)
	kkk << MPQoff//0x10
	k2l << f_maskread_epd(BET+0x3DE8//4+MPQoff//4,0xFFFFFFFF)


	HETDl, HETDh, HETOl, HETOh, HETCur, Tl, Th, Temp = EUDCreateVariables(8)
	HETCheck = Forward()
	HETCur << 1 + HET + 2
	if EUDWhile()(True):
		MPQEND << MPQ+8
		Temp << f_maskread_epd(HETCur,0x80000000)  
		EUDJumpIf([Temp == 0x80000000], HETCheck)
		HETCur << HETCur + 4
	EUDEndWhile()
	HETCheck << RawTrigger(
		actions=[
			HETCur.SubtractNumber(3),
		]
	)
	Tl << f_maskread_epd(HETCur,0xFFFFFFFF)
	Th << f_maskread_epd(HETCur+1,0xFFFFFFFF)
	Th << f_bitxor(Th,k2h)
	Tl << f_bitxor(Tl,k2l)
	Th, Tl = LiSub(Th,Tl,0,1)
	HETOl << f_maskread_epd(MPQ+4,0xFFFFFFFF)
	Th << f_bitxor(Th,k1h)
	Tl << f_bitxor(Tl,k1l)
	HETOh << f_maskread_epd(MPQ+6,0xFFFFFFFF)
	Th, Tl = LiSub(Th,Tl,0x7FFFFFFF,0)
	C4, C5, C6 = Forward(), Forward(), Forward()
	Trigger(conditions=[HETOh == Th, HETOl == Tl],
		actions=[SetNextPtr(C5,C6),MPQEND.AddNumber(0xFFFFFFFF)])


	BETDl, BETDh, BETOl, BETOh = EUDCreateVariables(4)
	BETCheck = Forward()
	HETCur << 0x2000//4 + HET + 0x1FFC//4 
	if EUDWhile()(True):
		Temp << f_maskread_epd(HETCur,0x80000000)  
		EUDJumpIf([Temp == 0x80000000], BETCheck)
		HETCur << HETCur - 4
	EUDEndWhile()
	BETCheck << RawTrigger(
		actions=[
			HETCur.SubtractNumber(3),
		]
	)	
	
	C5 << RawTrigger()
	Y << DropType2()
	C4 << RawTrigger(nextptr=C5)
	C6 << NextTrigger()
	

	Tl << f_maskread_epd(HETCur,0xFFFFFFFF)
	Th << f_maskread_epd(HETCur+1,0xFFFFFFFF)
	Th << f_bitxor(Th,k2h)
	BETOl << f_maskread_epd(MPQ+5,0xFFFFFFFF)
	Tl << f_bitxor(Tl,k2l)
	Th, Tl = LiSub(Th,Tl,0,1)
	Th << f_bitxor(Th,k1h)
	BETOh << f_maskread_epd(MPQ+7,0xFFFFFFFF)
	Tl << f_bitxor(Tl,k1l)
	C2, C3 = Forward(), Forward()
	Trigger(conditions=[BETOh == Th, BETOl == Tl, Y == 0],
		actions=[SetNextPtr(C2,C3),MPQEND.AddNumber(0xFFFFFFFE)])


	C2 << RawTrigger()
	Z << DropType3()
	C3 << RawTrigger()
	FileDl, FileDh, FileOl, FileOh, BETCur = EUDCreateVariables(5)
	FileCheck = Forward()
	MPQX = EUDVariable()
	MPQX << MPQ + 1
	HETCur << 2 + HET + 1
	if EUDLoopN()(0x400):
		Temp << f_maskread_epd(HETCur,0x80000000)  
		if EUDIf()(Temp == 0x00000000):
			BETCur << BET + 0x3DD0//4 - f_maskread_epd(HETCur,0xFFFFFFFF)*4 + MPQoff//4
			Tl << f_maskread_epd(BETCur,0xFFFFFFFF) - 0x4200
			Th << f_maskread_epd(BETCur+1,0xFFFFFFFF)
			BETCur << BET + f_maskread_epd(HETCur,0xFFFFFFFF)*4
			FileOl << f_maskread_epd(BETCur,0xFFFFFFFF)
			FileOh << f_maskread_epd(BETCur+2,0xFFFFFFFF)
			Th << f_bitxor(Th,k2h)
			Tl << f_bitxor(Tl,k2l)
			Th, Tl = LiSub(Th,Tl,0,1)
			Th << f_bitxor(Th,k1h)
			Tl << f_bitxor(Tl,k1l)
			Th, Tl = LAdd(Th,Tl,0,0x4200)
			Trigger(conditions=[FileOh == Th, FileOl == Tl, Z == 0],
				actions=[SetNextPtr(CZ,END),MPQ.SetNumber(MPQX)])
		EUDEndIf()
		HETCur << HETCur + 4
	EUDEndLoopN()
	MPQData = EUDVariable()
	DoActions([MPQData.SetNumber(0xFFFFFFFF),MPQEND.AddNumber(0xFFFFFFFD)])
	CZ << RawTrigger(nextptr=CX,conditions=[mpq==0],actions=[SetNextPtr(CZ,C0)])
	END << NextTrigger()
	FF = Forward()
	CF = Forward()

	if EUDWhile()(True):
		Temp << f_maskread_epd(MPQ,0xFFFFFFFF)
		if EUDIf()((Temp != MPQData)):
			X << DropType1()
		if EUDElse()():
			MPQ << MPQ + 1
		EUDEndIf()
		EUDJumpIf([MPQ>MPQEND],CF)
	EUDEndWhile()
	
	CF << RawTrigger(nextptr=CF,conditions=[MPQData == 0xFFFFFFFF,kkk == 0x420,X==0],actions=[SetNextPtr(CF,FF)])
	FF << NextTrigger()


	

