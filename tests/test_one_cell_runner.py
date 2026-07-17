"""Contract tests for the explicit PRE one-cell runner.

All successful scheduler and lifecycle exercises in this module use private,
synthetic drivers.  No test creates a production launch authority, contacts a
scheduler, or runs a declared PRE campaign cell.
"""

from __future__ import annotations

import ast
import base64
import bz2
import dataclasses
import errno
import hashlib
import inspect
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import types
import typing
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as engine_root
from tetris_ballistic.engine import one_cell_runner as runner

_ROOT = Path(__file__).resolve().parents[1]

_SHA256_A = "a" * 64
_SHA256_B = "b" * 64
_FIXTURE_ID = "slice-8b-authority-parser-nonexecuting"
_FIXTURE_METADATA = {
    "fixture_id": _FIXTURE_ID,
    "scientific_execution_permitted": False,
}

_ARTICLE_PROTOCOL_BYTES_B85 = (
    "LRx4!F+o`-Q(173T1Ws5qW|GfkN^-"
    "$|Ns9#|Nr~{|Ns9$00aOK0ANm@_I<B8M@)f46(iW_bx9>es6he<R3emtM3=h&aEGS7Fm`+Ip7*oq?{?KsUb3$5Zm(}A0O6-"
    "*ETUPd;_7s5Q!q3D+K0R}1qt7Kz<0^MEZgnRym8NpvZg2#UgqUSce(FXwS!RE_jh~V=e6FR_m!OGGz+z`7jQY)?(SsGwzk?cr&R9"
    "jI?F4-Gy-"
    "2|y=*djpakoko%fB|)|Ywg1D=wCw}*F7(?S6NKnbE?fSCfP?Nd(_@<i}tlk`(+KPl>rBMna=A_O5a0%V@0J*6~lBhYP7Js<{v001"
    "z?l0;GJnr%-=4FJ#p0000Q8UO$QlSvT>(rKhq#*jzqo~Mc$4XL#>#-Ij(X`?_rAOa+W1QSgrCWM|-"
    "(J%!(qtT$$^)wkhBM{M`G#Uvt5d_F0o+DEcQTm!jO+Qq605kvsG{#AhfE~%I^-"
    "sSK*Ax8W{|F!B?GN8nwhT|uM);ML>E8KqPp|V+gblqMTW2m0<z{8*nCD6#l}QrnkPswwKb7o9@~nSYmC=XE{j1~j%k&jDwsG12m}"
    ";vjegEi-i2UL2#Bk0d-=2S+vWUrI=Z}&gMY&{p??nX#8c`ukC}BucE8lE+IJ!RirS``A5-"
    "gq^P)*nr5LuqPa;!ebH0NdK%b&Hoz7kSFVu+DLOu5DlJN8`fjp)vm<8MzIciZ85w@Vlr#sY(fIr3h6jLgF5UHjgolfxdZ*Oce!z1"
    "tlXbw53?Zy9=j3>H#6U9-ct{u?3FpUpYa`=}jBtr$x<i5kbOw>y7s5M@{EN^jrpj4+-"
    "iW~5sw{(4BnEl1{f&7s1*&1lzsw{6ck(DReK!{#u1%`OMYz1j9TnUKCewWnfI^tH46UR*qBgLUh>-I-"
    "s<nauFnbIzM?Q?|zk)yLG=R<m8*nOt<w7sT-5`Q9#|S=U`-"
    "t=a6OlRL7Gkh++Vs;RCv?6fhQHNit!cUo}c7rRVNo)eDCVAXDP<q7av*I!y9dI2890X$_A34$Ucg!u>(eJmj^BL*U%ELI~Js!$RQ"
    "x8)VzvuD{UW}?V1;|-1B#PRS>)BkVh_^*urDC?2#BHEuvw?7$)Ca~-"
    "VE!*26WRQf(@ivUw1GuO#kcR~bhcL)7MR2){KpRNwsvZQOYi<?5f=&<b#*lNrWG6SD#yc9$bMuT|Rb1jbMqFc-QEbibY&Et9*j|g"
    "NXsFmLEY>zm4g>}PU4xWxCuCdy@H!3Y?r=X-=pC2-P>+nd{~E8Me*&7d(qI#q9=$lYP5^*dZC;wU_-"
    "$q<vs$y(Oe)G>pSfN4U)V$z`pQXsRmmiR?U%~ku?rO>0JX*3ERVD1x)C7(^0<3EI1j(}gYF6%Vu28RqlGP?`h-$NG{zxAChu-wQN"
    "nax9*+H%g%4y_D;cz))>huDYv+`>4mO<A`QXoAb~oYACS#u5>3@)K7P-LT&0myBKgdD=V-"
    "9iPU2rBbJHPGo+m<6m7B}t`_$Kg|0*p*V=@$zG+^d`{k;RyVk9>9urcRA?6gcTIU!7tachdWJ+2q7#b%F&a#dT}eiuv}h$}(xams"
    "azliov5rGs%`hQn+0vH%x9SOj~TixP3B&wc68V9|Oo#I9nY*5!7!UTMyN99l8CZaPK>bXlAY-Vikh$9=8WOz_{}o+`GZjGeR8g9<"
    "k>>=H=hE`pE1_C5=BvpHHT7Q=Ki_Tf=O3P56bu)>K^D)4_1Uw#@uBvjBwWea2e0uua4>ZEpD6eVk@y_#CPv7ornNOov4~x22eJyU"
    "0%{al-6sF2dJTm`QyyMHhIiGF^waD9TdX&b^*q-"
    "B#RJvpLmzTygNDm79|Mu_P5<e(JdisRkh7bZLfDd@f{`s7N4aSc+#RxQPB8t{f;KKvhk_m+<oYKMSFaf|N80ii807GJ1`PAclu0a"
    "yECfL$$xD^eD5BW2gM#na(rrL5UIU-Hy@pd#MYAG9g#7OZ#-"
    "sy$!LTq4c7Fszjfy&sqKkxLwVVGSTyVI3s$71uQuXm%CqG1>36wDgPN8{sB<&&W=@0rQjb8u3KpLM$tLL&j97@+tzk+qUlIj@A)5"
    "mglUfI#thPiSW~8Pp@CcvA|{;+7Rg50WlTcg;^}ddip8Q`9aL+kGKJQ+G1AdXE*0Xi;8GyKg9T<gh3qaD<krE}ub=Glx_kzi)e{8"
    ")R}4h&Zw#of9$O6JrCKv=(q8ns^UgC%>i9AnRuIPCq8FUxoG^wLjE7}!CX<ay?tp(abaSBs1W2JUUL0wAi+1nI{D`($FQ)r6`DB>"
    "jcNsan&DlntaACu)Y2sYcZ6ciuk$Fcb-"
    "X4hN@xU$2m2;S^A~?fi^Q9%J#8sD+V+)U6A&GxiCKsI(<I^0lf$m3OXLI#i^XSdy8|v<3e?JtxKDAfwBP3I*Beyo_pkTqJ4H!mv#"
    "_6mnV&kcfQIL&C6G7agyKijYVr=zci~wHjw@^Cre=vjX9-8#lXmjnw?NlI&%AK}e9{Lf!u-"
    "kXAU%nbiX^QHqJfiq&Yc7=KT52T?l#cd;x;ApN2uw3-"
    "`^!(erLwNb%8EvYVYEJRQOJux*CfcmBm0zndGOu^ru4{fGnV=%4j=571C44PJv-FTc}JDM7wNnMJL<!A(rWvE62HCgwZ`4r9`<*U"
    "90BRzFk_tP8g!B81s52er{Bu^gvi1s_ZxENM`uNzc(}7c_}f?mvYgH?7Z(IjK<s3IBIz0!3v@@0=a^vvYh9V!z95<FVh2ZVWwIof"
    "L7JX9Ac>5_{kfg<B;xXjg{`Gm{A&LxQOzfp{XXX(UeZf(dgaE)qX|YbZP7sIa>JbWMRMBTK=xWSKq6X!QfB*Arnl3uUq@2swL$Ny"
    "bEvkS$qn_k@3Cz|dorWDap?P6!II3v^pxmC)+~gj%(4WL(V@mM9Zq!PJG&ta<$dPJ%L|T3GKP`uGcnAzH|ezQw;UeSfWY0^-"
    "xVd|8W#!-"
    "^Oe#IKRGUa#Bs8T&qFyskZ7_HNfh*#^we^3=0lP2Awrz~e)qWKX5$>6xwBVof%5!Nk~DBgfPHn(CtzY5hk;wKP<y?8@2$-"
    "J$_;GB!rWkN{h5qoioO}JIqo*o8>ZxedB%{dnn9RWEiv?td>)uq&+>>LL%TOM4+1Rn4D8$a^3814^G}}Lx7;5~RIK`N+Y6v2=*Mh"
    "FmbgA!M(+P$<G&r8`10e<J9_sGzs}oxUx1PAZS|S$a;F>I;SMK*fhg>179AI7Vu`?o!K<`O#z#m^5Xo`nlceDp3p7LX5z-"
    "n(yd8ZXFfF~uL!qHaE;wo&J1#!u+;;n<;!<F-"
    "<4d7sGQ(6yhcP+)h^bG!`Jbv&1xfynlLCGjrVl}AxbC>+N0$uw$S$S6XKkgBn>RlEN{>>&{E%LH<?BAa_ZBlgPAq;3bqE&g9YZS)"
    "!*D0*Vf(Cm;q^UC>vKWauGvF=<pN>Zf(Uk9IO=7ZC$_3~mL;|}c$mhs9~1CV=&<CFWce<HEwuR~CIKE3W(xx~sC5i7xrB~0q&QvA"
    "S<v#Qucc?RfLd)8w%FNAQ9~393{y9tsM1V`PS%<85~b47)LIlDOFMAMy~0NS)BSUAejHm`z%syQTSUZz)xxAn=N1A-"
    "Yd}SHNHNalgtolqMA$+2Mj^YQ%4-"
    "EV`x<2%*L`!0`eH*YF!@7|J)$!iY^y(2SZ#epVkAc8^oZy;z0wdjc5Lt8mH<XWbg1_O35jC47B5nLD>FUv0=m=2RqR`=qco37Pl!"
    "xT1(1dCk~TDdB%g#cHBzzB*LBXl3flA*0dlNViF`SDVjB$00w?x2yMa@j_+A9b1|4xjEId)d3(QG8Y!%w}78rjR%*)AqKs#pgtR="
    "JI7v3EC#)WVw<64Z;XCfN1@@;wJXP_cEW`XVHz5O^}mfpp-uX-OVnGO+_NrIh9`DGCND@i;Sd1v>YW2(ROQPOqEMps4#9F;RHNvz"
    ";DPn9N&psKVt&onY3J?y&*-"
    "J~e_Y^ScfpDbs1Vm7jqZ8}NyJV+}61yrxidt634)}wxv#bjAdCL<frVAGdj!zdk8U$#sIHtrg|#|vVt>RN8ZnEQ45^K#_K_G^z%("
    "tQI!+&)I`&<f=Q4&b2$5Veay#Cf(m^oYEO9kk)PI%Oz~E*o;rqESFdRYO|+E%FOOqWZ6PoV<iKD0!jF>9RD?ho$R_=I&iNkih~M;"
    "hN&P?*6mef4<x1;A!?FV!%-"
    "N^H2}k1NhLf!&_@+2E`hiIu1D(?y1@!d3<=NF~YWn^lwqi>^)#NJnz&bg8~_ynDH+I;_3;Bf23a+;y~+u9UwbL&o2x>%R7LD<iBT"
    "_wmRpQWIJ1%*Q*S?+AfQX-9ZR0C=a)?sXNv)VcF5SL6{|MtJH0|`)#Jr19l{^mF`XSw4NYe*w-UG5xd^-"
    "X}%3DMwB~|#_|$CB|u9M?caIr#Wud5M)(bR$fzHKN30%E$D9=C>Ojp=(STuH7-"
    "FH?7Uoyx<qNQG{r#&G2(oeDzKbs2Ikn*JIUTv>{o~mbibm{hexanXX4}zbJOKK9`|&rX(aKBbJ986a>3gDmExP+r`^0g4a6TOMd&"
    "Sl0Ej^93Js0acmTv3Nfrp#qFj4TBP<#U0XRAolntUy`+Mrv8RZ?%{?)$bmBr!;amx}RpX!ffhhGAvh_BZf`-"
    "YU3IGPu9LA&Pl_;)~Zlaw<o~1xGvf6I|L9$v0%DcHd7kGUX<nS6ivFXe^<lM(UX92G?dCo!DkehC4EhOJsa_$hkZ7&ic}F0;6ZYN"
    ")<xV>vPP5B5uc2(blHL`ZsLxnK8cnzR-el?C;NQoz6BS>mu2qaFcG3-FVLo`L^SUW-"
    ";4w%||XuQwW$EhbMvJSGJk7+vbDAdE<G;2V%asmbk4d*Wwi8K|mYN(ZS(u`1ti`Oh}vW%HO+sj{=$nJx7eQ6d_NN$44=CR^<{2+Z"
    "pqAXKp<6_&#>1@x*9Q?Z``Zm)|G{Ck9g5ai4&R@8bL6x{~@DzUj}U5X7A@9YP#@);Bk$vhzNsj^2vE>q%#OY&SS<kIp$iSPxE_*e"
    "QyfT<tKyb}l}-!-`hs=ipY?g`U~7!VJ23$+)-;h@XqVPkc=JDhDI20}DzS5y?><i#d_&3l%8)Rd)PbNLbfF-"
    "&qNG(}xI+epQg~y>nt)iBIxwKNW}{t8DXoy=iW5DcswOPYFM($a}k$JPLP%n9>gc{&5X8M<`iCoa;YR@en_Kgjg(5f+D~&2M^I%L"
    "e@$tZ{$G8#O)b~W%Zt@&vWy8eA;^gxj8?4u%>_BJ7~aj;Gdua*d_kHR0;F?2htgduoG`yUhBuQBDu{J76Q2ckmgPK7}Qp90seY4K"
    "|>o#Y{gQ{D6>t!Q->FjI2si0?e90rNU!y$Tp*7$_NZBX-"
    "(8<fK64W}Lb7gc_AKRk{&!_NU9;bR?GVC7g8Wa|Zo3>>p73a7DnE{rpaxN*RUje#*ZXN8-"
    "!0*L+*Ye)jwa}EmR?qGE??0{5(y(;v+Y6N2Z4B?*meydB0}fzV1q8TQwA0JcH^%94XO6|^v|zfN8R<TeovC-"
    "x(4#U+^6IrVGnCR?B$nVR)dHjKc}Z?$_>OWMIrGEodWU}0c{8{f)bFA*`4I@rWpR{Co(pX$b?d#9c<;>gS)Wfn<OA(-"
    "_=??rHV%beVBa+?Hq7vwGz-%a7UYpAdj5OjQu{%0FjY&9o>-"
    "!1r3kkzMg*9EoR<r!?+~w(cKQvyy!Mi^7=jg@!ES_&1*Wle;f{<uG`!p^ULEhq<7~%V}8e6mB2?VHhJuy-CPZJjhZWMe?N%f<08$"
    "61^F%%js4(ZSXjut4TuW}b-q>-CIdMu?0{W1E-"
    "o`+fol~g_GSj9H{Pu!$lz4%JIIYxOSu3X%6tCWQCWjCz@Z>`A8~KS0fYInxtu)V>);~ty6XaNx7&5?2`sOLtNXpbPtWJxK-"
    "e`<dn<kyW;{6%Idksp`~LOAA2-gDNU)yR1%1?#D1IN(orl<-"
    "C~xE6^nS4ORpjp9FMhr~c%^6FG5_fa_YH^f_^;JyqH_d%+dhG?Ce8hJ{~`4!gMHKG^DmhGKA)=bcpkE!Q+u!{2oPSiQLv%-"
    "^>1o^1L2039CSZm6uI4WvJYXjKNY-mLJ2_$CIB>GBLL%o%zC9ETFf`i&sQG*W)uWwAR&7EY%)Q04>Xlj29J+C^Y7PJie^K$_lCX{"
    "IXU`02HO#U-"
    "vDCYJ&;&$1SsuMYN~M1XPSX}L@1{DfRF79!K|cboy`z07h=~%!iF=#bm7YPl*#><Txk92q4aNjtyk`J5hH78)YoY0rRHZd+FWn>+"
    "~+4W2U_^c#+Nz}*DSIAqCa1f>-ct5Gq!>Ul3kAOX-Vm(UWsqmTRu@Q^P6QV84sS{!0$slu%pJyR_9CHSp1e|we;&xiuan@S~giMC"
    "zgL{nIbUApSvkFn)G}{)oO$ZV~02dyO)`9`Z|jB{U5vY`Lnocz3P26R{F*M)%J^c2e>s)GuP|?iygm=@cHN3cb<i=`Zl8I%or+#3"
    "RIv-luzS9?z`^vx(zZ{drw}fM^W#vZ(d!G{0DN64<8}sJ$J|0M?5z%643`zpQqjrT^$P;pD^iX(|O1n)%WtO;U?m^{O9q*CKb3P_"
    "^5-"
    ")&M|6rkYFv&x{Esew|KfUj7q5A@6fy8x|Z(_j0AN1=)R|YA*l1k7k6vXhB?oS;y}gZGWcdy1r(f+l?O&%xHO{06;>`<)=<KH&Ebf"
    "Z9HIEM3>|oD&$Queh7otcL<urK)Wy{jKOH1RkcM2;DJSyHSdxjjW|e|__*YLpxBhZ+k3WtZzFlT{aYL$P(W7A8vg0aGdJKm2)%U6"
    ")NeU)_5ZAotZ6yww+gQ~7n9PH3p-g94-"
    "1>tZY_<2TZYLdfK7aZXuJ`2686Z=MZ#<6#_Mi~45FCdrUa7em83Ljn<*nP}hwy5e@TWp24e)J7G&%N`>$YY_o$0BRHk$@3qK9QK2"
    "yRBRD+xCZ(r1I3KGRN8uJ$#H$n@I>Y&dT?n8928W&GN<A$pwBNRpfKAXpk6%r66zf<nUn)(^s=Vn(wh09b8ku8#*3?Cd)rE7f7#A"
    "3V=os32D7ECr&fE~$T^@#hBhwMtnQ;}oNO7$&fM;B)FFyCE&YVPL5FDm&Sz2|FNFQA2(%63arVr$};#rmNU;K8c{1T4<otohIxCt"
    "S%&KvHN(8sRMnkRTn8>FpdEf29Rj1bR|7}UFi{4w=n2Bl;=r+H_qO;g!ddKwLu)95s>=%d3m2Q2JqeAU#d6}Bu|Nf69lHvU~ioL&"
    "2mmsUx&i~d!!KDVKtFYBn_0DHVPZypeXo7sNnj%uG6gI;`hTeB8k6Dzju6_H;MH-xz}0JP!=!*n#GOIE1l~KN^8LpKak3&&+P+qa"
    "9JnO_yPYGP@&(@P<?-^^KO1a9Jv5_`F~b-b;~;*s5BaU-d6jbpLh5#-JkFOz5kUT@ceZCexJ&GA*BJ_Ij`<dMjCYq_I-"
    "*$LQ~{J<~&C}El-"
    "d7PCnl|=m>}l?T~NPNT`uQuoY_xD<|;%`@^K4ALH`;@2_89Y1SPlRR0h`&3}5{Z@L5a&`>hs+ieO2Lsd^74fnN@RV0#G6&d}#Z1k"
    "J6Xb6gkj72;t_X+IV4WubVAFtkxxm1z7O0WZ1BtkfuIaF(th!9K#g2himV(kw@92SjK^Jaz6TrOU;tNcDwmBS8@>sPawND@NZ$8M"
    "1B%ls(pULQnW$K(jfa|(t(oO0GhVp)gu91i2BjX(u2oz`eYXUm^c<A8CB&@gEcV6agV8x?PF?8pO<OO%Cw*f6~T5hLwIUVp0XpkM"
    "adyNmO#&(Z;!lZF;2*NtW6BF<~*9HTyleeqSO>|wWnUD(HYad0R|ynj?F$G9j%UAn#3STa-rVO5C6C@Khx6&Nb91%nhB5m8SZP+l"
    "{C*X3uYIkSl?YAD*y4YCVbn8yx9>P<aZIb827w0R!~<Np7v&<D}{>Gk`+_v_1VmcFe%jAdgHpP!%h1%4PvPG{+NWFKmMkdi@Y+wK"
    "q3@<c^MR~`)u7>meiB;51;v#Z+fB38ya)Kx!=gA@Ez(sT7Eq9XlM!3DgD)RIR;LBo0W<huMvCXY_cTmBe(Bh16|(LbYo(~I7qLI1"
    "A>z5+Az>~J{uDDfar8H3?{rS`)7f6m{-E4*iQ*?ySI6Y4FtH1e*kCd_2$Gscl|w~+pp8XLAO|H&5m_2WDD!^r0cVG-"
    "^45CI@>?a$tKe~w;QXbR)3dv<CxPKoWkt6le94F(m#<U6<9zri{3#yfXeZ8!5}*Y~U*kSR@>h0^a$z7N8Y6hiAPsoRWvGNxSC+o<"
    "25s;<i9YkWdi58>?pNWSfr-"
    "|Y7E!=)BHGH3EYo@4+>1cFfsKu7`)r_*n(zQ0!1KMv~W4T0VLyJ9!PS@`n#I{GR9yHj^aapD0egn&v43JO7FfT8#pR7ORBv5bm8M"
    "1n{%4Tz8yMFk?PSQyAuL5Rf`MUX_3BoLxW`e~#;tP>(4q>)Zvm50uUESud3x<JM;aLbf6+I}s6J%#3p3z{I6_~OTeo1&NfX-ybk5"
    "8~<vW5@b1hm!^C`8pqX!k@qg&cyuGB~5<d8$S%{68pUn@QGPjnM|}|)T*l%M!;0H&$TW=-"
    ")9(4&)(JlYCxiRR8pl;1v@8>1(>=w+u<e&p#vR5;Tfz+KJ`PSlXx$_urvjTgDeNZl<Oc+*L@8SifiwFAi?iKmGyCUyh<A4uS>}5R"
    "xuDkm+##a);hFhE#c=YwVOA&y~B*n>gY{Otfi^JaJE3yCnEsCV90($$_gxx4GMXoY|b!;Kse=(9z3nLBlmiT_wvGTk<5W@sN;~~Q"
    "Wisg*g_EPR>^DCOq0E5k(=N55!0ZC%3!(eNUa{vV;IvG!rV|&7G~Q6IHvJ&F&aYy<L~LrA3i`KtXUC}1(HROQbWQ5Q4kMBk2B{Cx"
    "6t@<4LBL-gUkvDj=F)!=ecq^_vm;IRNXsrB!LDjRg9axI39piWYO1|eg#9XPwg`gjKxJ16Qtr3Qp7fALytq}K^p92Edhv5$RR{m8"
    "@p8;tYlv21DJH?@Ohf1?><@>13|BPm6eh#lC$ty2Dv;D6CtK%9lCZE_1G?A($=ULoOue26(S(0ZRJ-"
    "J{i_M%ndhY*rAp_rFho^QNzD&&o}~_`6OJI5iREfpP09vOTrwM>7@#1<Vaq}YD;6{2f6QU!vlKU^A6xasan1K)Cc2ocd2L|cmdic"
    "Wkii)?1CY$^n6`yLv15`kZYUgL6T3ml2ItZ6@TE(4uw`N+KF*<G(L`^b?@dX0o7&>AGRg}O@4;YTL5AJLU|7mKG3OQ)93hQyjy9|"
    "dbX{3UY*IB3)O-"
    "2(%;rzuUM7T6MI4iH=8spp<d4BS`zuVCMjC`HW{YrZzcMPK3j|eSA}QFAp&u${zX1ELKyl%NSQ4pNKnj8OF;nh?xOr+Bu%8_SswM"
    "~0@~v|qV&54xiM{EMClh?wsD(*XvWMA%FgF6&Sq$Ob+O*mu!V6nc5=cED+99G4yhCVwQsK#j79qM=un|lwQ#gdprpPyeAPcNPsDt"
    "8#*rX~sL?RJnG`e72L!(Eu-=KpH=TiI7M-2sFD`{p-"
    "cfXZ>7pdj!DZ#%iRgsKhL!(JK_2w2mHR@nPx+}eQE{n<8EVVb%!xeIuidHtsSjXWTGk2u$N}b^uE$RtOM2i#_MJC=;det@qGWDru"
    "{S53_Fr6gcs!dEokS)kDRbv#gHUTLKB!fy_H;jp7<(4JTDlYJhav~a4JcnR&WuYB{8o|qmP^^(bK=6oz!dSzzCXzX448{+gkengm"
    "IE4V%&TS!LMJp75xRuh$+5^T*V+%9!B_|>*ox)?%g+;c7OKBTJmKgap5hj%?y~tccOpU5QTdQ(~M6DQ$6-6@)Lli-nO37rE3I(Ft"
    "(9Qlc%Xq<ZZ)1Hdm<$?%z}lc#f`}+ll}M_=NTNj+ELbrSi`b;9AjDs@Vd#c2V;KY#7$L$Pu$B>383l_FMJoWhv{#f0tU(d2jinr="
    "Vz7A{nQR#tBL_v{oNCDw1Qj6a%7Zg>nnOtui1aL|IYW6^)HumiKvZ$4D5TY4OBXGYr4AWbX|QBg3mA&B6B4Xgjox6oY!VcAY|e99"
    "wwhsy!b3z4b&$ZDpr+cwrDi7Wli?NK!cM*(l<#Z@swt3Oh#h5gqMk)nY1R($wnrB&V1>j}GDnK4qe2M3>G?UoGjOAo-"
    "b*6`SQd@a%;R9;(u!_hmnPZ~(f6se(8#G1Uf`rr7-Mq@5QS$(MFV3n#+%9&S(6AEVuh2FDlFR*Nw{GNbi!wn<%dL~64E0Hy}-"
    "f((q-o}bV{LBgQ*B(=|Rb+N+l#z9+Q|z1f+sO?;gAEI|C#i!I}n!VZ>S-_&`lrgrdBPT4G1s>7M2WN-{=HRYCHp7-"
    "9xCEJgPyRwZNN=r}<K(p$DHI6Gpo*HIHOm4Znx1mZITa}kLVai^9?2SSAdjp$r|QZ(CV8sy<2Jx(~WxTyg><iOz0TqIzG)KiBi7~"
    "s*=8g{xoJtr34QV%D4G(%M9S<^XjSv7PB)WZNMR^|7HG-"
    "=i#oN;W&8^}|gHUi2VTE;EV(ZJY%A?jR$5IEKyGKhH+5g<`SF@gYsB<svp`fHLw7dM#WGv7(}W*SIdgE-O8d4R{M+-"
    "Z<wfpoOU&?piOA)rXsSZA{1v}R(N5C|k$BoeT4M(1RBs1jtlvfNV#V2)4}mc@asnYEG3xDZB8Pi(gN-"
    "<EpIvtuNXPBjj|(goo($tIMSF?7Rmo8J?#^vp9eTPjIHOS5a=n!tg(GpR=B8@^iuYDl0{paQ-"
    "*TfLTGc#i4JLMT~rmvV8%p@}$h047flxr=ifQmW-?opsM<-"
    "+h4_Ylhwe?LFvZXE$*1aJf07j6m53#u@@A4T%Gx5qpV&&5qN)`D(>J(Rh}2Vw^U}R1E1xZu!4ocX)n3Sv}rTN0|D8AA?eni{q+{S"
    "Rye<B(F2gGEup2;12skQIly)yJXYtmvE=QGhaD*A;|%YNyUrueRFtA8C3`lDuyf>Bb%)%r85Oq16U)F=mzkP0azg(Nh~=XB@10Rh"
    ";itwBnYf%CDWdamjX)A-OI-KVLCk>_rINQr<#|1aY2UYHA4|l2Fy7)<UBS?(Lz3Q<%9g!COCn7I~-"
    "ZZ38~6W!ap|xYlf<3v~Q9l5PD`Chd6d=KtfYk3S#)JrN+DMpmQ&fgd{U-"
    "MR1~`+&$hwH8R9x!!t3%5w0TlfK0F@W!f@@Q_#n5?i#vaz~yNLZ1J#+K>)dy4BG}0%)meeV2K@;ZkiC;o2g;gPC47*LGUm={b2_-"
    "E4XNJg)p(?z|*xT^_y=CpKJ*P+R5$s(pzg4W9pG)AJ|VQdP%&ZIxy6peT7k3<fSP;8!(^PkTLbi&fsy$Io1u%)#jdTQ(BZ!gUe@x"
    "R>`2Id+n)=U3_h90RE`EiJ-"
    "2X$pYDSnh`glY<H0!Y$W>aaop=7vCtEAhQnuA+b9obQW<tAfa#`hL#AGAN_@tL388hCq&bcQ<U_V0=&Tf2f88m^$cN{*zWuy&Gxt"
    "C$gD~f)o@CFV4?`0e()wGYG(*ofEY6jb%y4r-i_0T*4VtDmId&GXP<Bs?%T6Ca8xc4dIBGChO(vw58%=1W^%)R}$m@h1-"
    "U0K)+)E)Kkzo3`me)Swx>W_Mge=dJgDp^_87LaBKVKhD7iAbKtH`{1)*ntoJ1Qb&QC1n*od^gqVC>S)8J+(^aSwDpLT3gYrDsm!s"
    "!o8UED;&dEINhl$H$IRR4G(dMQudDZkiNu%>+IPM9>X5HfPwJ<uhdK?(Nv2d^TOVL<?U-"
    "R`(V%x>u=4>h&57b=w!`3qyI44fC<O!SN#wea>n{bO1pB2-"
    "@rn79P7P+fY1fJ8Z^*X!nzRyjV*G0mNuV`e%}J7g#RDBWN;>X{%b_B0TgKo6&Q`cEEAp>j#iE-"
    "N7q_TWyr>QPcP$40#{}8SPjcWNpWOL%>Ro`#rM3*~5n;Q$%%a@dHlPK>CLyK%YkAB-"
    "6mKk4h+EC_?#cdOM!Rwe5ofY#4q4^`SmW(>u*Qjcu}bV7-"
    "sC_$3Er6Y%d}2A^<;w&68{Ub0uTmMB%v0I(&wFf`U>V^^3{*x$Z6TdY{atVbw!ElNPNQb0Mq*esaVD?G(za5IXM1w;1OVjrSg0b$"
    "ry9&#MI#fN`k7tVTN$JmGDUsZ}!4JI%$(P3E%!rHSeXnEwFN$xE?5Ed*Lz&(EfBNvotfYNtl7%+UK`eSu`0tjdt1(TGe3Dw{r{?>"
    "~PP_iBd>{y7T5)t|TWbw}GCIutlO}WZ`7&n<kkz3@5Dc~oWHn&X(u%kg|SQ;>qNU#MVs!2eESR^7vQ4sSgr#uq3<7@C!LwmVYA3U"
    "Zpk-"
    "@DYSyFL{VY8yFPoFoLqD67?bwn7t46D%WWY>FBQg;N5Sfl|A1Wc~zWM=IgCQ7DQi$?g)I7*`fxnm91qB=ro6=O%IyP@#~N>kG)n8"
    "8A|s|F$}g0NLVZJ>fF6h#G4WKn8XDySHgMF4sBE9m`s>@d6I<O1BVl!>EmaD<aEv3oB#rAHw9pt3XPm`^jxO-OA-"
    "7D%GVqKJwLMk5ed3JS0lU<k#76<D$?iV;C#g2jYT7AzJK7%Yg2D5%916@+3DK}CxqAh1yt2<w#Q0Xj!@vku#qMI8agNr<vx^8U(3"
    "l$cmT+qRJ{){xUyNm(*sXlimS=H%^G587iPG&3mCg9FfpoFE23VK}L|MYKn7+Wu_Ro9=AHWG~h`A}gjhniwUpCK5xU0Dkhp#D+O1"
    "5I5u!6P%~r@G2H9^C^DtUy$zf^+eD)@*o_W%^(&iTx>-0WJ*#@t-T0Ut`$`6swQsCXr?C)_pFZgX0%-"
    "~G~g`7i+Bw|H8G1**2!XGD%g^)84xeSI_z+mOp$Z_YnYC3lN3p%4KgT#pLLi*cj>e{&I7-"
    "+pC%te%6!UXfv|Brw}lA1lg)&_PZG2#bhfNvZxev=fq*p*YVW<kBO?o&y4l#wvX?%|DFi|y3M>R*Oi57tgLH~9N8^-"
    "oaMrRpr4Mgg>=V%8nwIV^=xDh<nIR%*;S(hwJV!-"
    "Bj!mow1fm@ra8dR>A$^7~TJz={@pwyIvP<5^BZ#&7Gs}s6hIF!(s#n#97Xj|+XF?w{Cz~Pgz&*!KigoF5mXWaR3Zkt%GQI8j5G6)"
    "r3EbRej<DEIx?Bsz7o2Osoufq(Vi!QtsT3&Ru0~?WO*#Ou4EyWSzz}g}*yht4IL8gWP{s9zT|D_Ujh{?9>)<b#q5)@19u5K#IYzL"
    "Qcu~w$Jusp5#XBOlAP@|qCh}a>4<oz-u}cMjsKN>efUr<m79gn>NU)0mVk!uc83lxu?0S3S#pFHUaV6yTFTw&I;qM2AiU;9gd-"
    "*6Gm_npbEK5oO>TLp<V`(7KP*Oz*h;>e!5cdauFJ8&fb3-"
    "z~_WBLdh2VKb<+KkS4ifdYXCx21lju&S{o~R0(6K87ZtCZi^4EVO4rI?OWy)4>EqYiCR{+q{C#b&2f#(?18zN2RbToDdr$vB-"
    "I1*nF$0sD}Yg9CndwyLKuNM{-T`u5T4ktVYi_gNcsZ$iNwyx;7-"
    "aZhShAoq1hKxMePh^qNBXa(#7Q958Ln_2#n?v1_OOt$44LPtUkHPMgpNhX%?ZUxIPqdy9`va5Mr2EZ#X5t7|s#_%mM0=(3DCaq;x"
    "oeQE8|jOM<2;6r-<`g}wb_m+GYOFb9ny-(C<EN>x$8xf5~zwtuAOMa(2-oS<+*IrtO|S-"
    "TEzxst)WF2s3M~s<xs(zLW>44W+uck2sup2R753%D}|uO2*xsqltUN2>h`T$6#E0aWoW^{(Ka+@kjZt;&c-"
    "Wg%(SpLvf0WgVjYuV6rUmF4rbc3VK+)3G9NIs_evAp(C;#l>tS@3A!M|XNXtohgD%)Zb6cdCrDxKF?GF%%1JFZ`iQ3-"
    "BTroG2;4}TvI(Aa@Cfdxz#55-"
    "^nNk^Yt}ycNo0>;cW;XMK*x#OXemD)_BPW(18%v)JhX%kkDEg2qfE~M>KRfK&EJFq*B^~3nR7$KNh~iWe<IEy^HHlc`QBexZO9I<"
    "a6$OG8q9vs-oG^wZnIUE<kEzMZ0&hXp3$djbg?MM4SJKc?K}8C$Tdb$M4!d-"
    "RvDzY|1&n8rbjjXoY*#^Y__b8l7>O5$S2sS?Dg}X+EL%@2${IA%!%RH`a2OJdmb{Q4CBq7S149=_C}esAyxMuKQY13iQlv)bbAcY"
    "t!x9jY)eI0Q(5BYu7RDzJ_Gu5kum^qJ98RABx>zVkkikO4LUUyjlqK0^OIk&_8bYkiRJozBZL0QJZZk?33{?+h2)X(x;#^aGK`pm"
    "pL`DWoCgiFSCnG`{GX$J!6e9x3@rP<v21(bzd13WVd&#s}yd@J6WytW0`675kEeD<)q=xqzv${y*)$v*3!$`T7G@+~8q3sU1AO<t"
    "BmM+piM^)D*_6ZZC_VCfk+B3Kw)l;d|L2Jg12PQVRQRIQg0GZKKRN4<nYNnj~+muHWMUZY}fng{rP1}PKtmxPYz;KR&RMCbSwULr"
    "dc4UflbGOzpcS*Wz+VKSz3mt&9QZf&M)pF!@Rq4TCB)-"
    "~sCf89~k+P_36iP*$5X@srMS)$FV_S^Op`%(H6w@}!kWkf#*`%T<m?agAPT83_rXjakLl{^CE4u~`%u-"
    "QsK_!6@q?$M*d6krP@>(is4+Md&mqq6eG8SoBq-"
    "_>Vv?>|#{7mIHA0CsZLZdOYl^hykqAILJmSzWHc=DGrBC9z$fr%6+O#eI~s9?lYN1g(4xn!oWLJ-;liVFf@fK-acBUrE&6cPe}3n"
    "~*BOklu>GL1rz&=fdq*5o&=nt)_J`bCmybgDWlcTikHzH3_x7_1z%Nf>yh=_<#?E2}85M&45xvo~;g`oWOa^dYkt6I;_@lznI0>e"
    "Y=Ri&2!y3fWeZRfGtD$cP$&oduyrmjkJ-"
    "Gfe8m@Iz_DB2Z*AjF`$$AqE!%H7^+-EG>;2n22~p(ncY=F@gA8323y)u(n$?O@nQkVj@N`e3HIY)>iNaZJmcVN&>N-ZQ!uc-exE<"
    "fM6OSt!U9MVG}EDO36_Wttvu@u|yEIilU<sS!r0T6lJ9ZQqrZi(X<$~sHnjObs$(-"
    "2N5X?Rct1DXxgNTI}1w+6hJothTs*3u39Ll-"
    "8iufZCNSXx_t_u979NkNNXsKH$Ez*es`JU=kPbi6YhzvPHcUr42f8~0bdg4A<0z@+RKp1C0fv;n_n!kal8xbkW+|JFP4@KPj%?@4"
    "w6N{9w+3z%ekQ5Bd}fd!SOUZcle=oIv`f++q85<;}%6^Ssj~p4-`|0q$^jod3>Pb-"
    "$g#iBO<~hpc%;YqT3PB_}r?eD25<rnPiza%-"
    "Zf^QdxMB7;l5JK1U?T;@wWMkTkj!EucMD3^Y6}`jb_KS)@Da#bOJV%Qa>=Zp{pn6HJ(qK+_3=OaX+L%^}$XD5R4*!{{%FQ7#^-"
    "1t+Tq@~EM8_M2!A)u^013=>iIKn<doya=(><q|<8dC|MEhiVZj2S^&}(>^dcCRgBx=7^iHAB9+VjLkEHA~UTQI0uP1=UPjXQ_rUf"
    ")0Iax2pU!bBr4d&E0|iTA~01%yga(u#OFskqtf%2<7#c_mfBF8-ab&)wo2(!Bf+uu^-"
    "#zg;33&CdWM!yN6J|bTnAH}D>3e9BqSiG15>P!{7c`<kPnPqPT2LE@1oHJn_M*_*gIl-I7-"
    "!!oeGRb3dkHoT06<K;U#4fTSc|9En>xWWsWKqwk*kDvJ$9px$Gy50_S5fM@Si2+%N{wLt-A{-"
    "8X=F<IjQxMGi443D|?uNo+i)#ScLD4(0q{PmmUq(y2xvL&vSo87vP%*T``=f`?ja2x5F_4_WBI5LG!^()i^v(y<Z^rJxiU@*;cDd"
    "<Z|y1LRu=xlO_L0m#Q*f*m@}=_1KY=Y5jq7-"
    "S}ZWVs9^CYwW)f+Sdbm+f;Pok(i)#RAy9Et&ep6Tu1Jy+~@iY`#EeN6S#vUf`61&H}@d-"
    "U@8I%u>X_;VJ2iNKR%9^XXakpNiE)g$Vc}!kCYGN@~zm!q8%xD#FB83JCS^IN}@xWfQk3sxm#au&CWl;u;(|2|*wcVb9|*bNB+9o"
    "gu7%s}^(^a>+Wf;KK<G5Daze&(tT}Aa}y_(yrF%&@pFC!AY?!4?eTU=|6_Psn$=u4ub-iQNp;FLTt(MfSM#ay@gdPeA+Laptv=YN"
    "mT_>EENS5K_D?jY8AwyEM!M0Hh}~Y9E8Y8kvw#w2st8I2UMk4EUByty0k%ns~DmxfkRZqkyTaGDqzCmQrf3*OO#H;^pL?1yidkv7"
    "lo7};W3x29!5hB2N@@KTLjt9jnOoD@ox9K78GLxv6JXCk|KDe^D_#}Yz;@8qsEb-"
    "E&~RJm~EO79a5Q%h6`*fD~?&2jk<CMTCqWEDyp?AS6F;H!i*idO}=-"
    "`G2LsqMQwo)?#b7*2+_wW*~kTBk($I?(%`1EF(mikr+l9%l<0`pA;28YDaO|=K;=attPI%OXvn17f>o7FNum!*lrkSNhVM}4vZc)"
    "o!iUeiCE*MQ5UJ<ju&^?m2}metJ(3mLhRz^SUGK$6OEKP5rXxvFg@*y;lUxj9W2+&#${(letU8l~cep7;4x!gj&zD1xwr|BbhX*j"
    "o0m|e+tOM8}6kFUHfHp|Dv>37)cj^TO$OqLDleiKTgzMeIg87X}BuP5`;G^k*;VeLEZ?NfI!h7%;LBMid;nsIdFlYn8|6ZPltF$f"
    "zt5Q@fE=n2aZ5Asc4Ar!^O2TN9DHvlBf5uwiiW|cZprBQBqwmAQ9oURL84fctdP8Qy8^MuRWZ?sG5rW4x3PDU2Lup1Lf<!|ZMmU3"
    "7vRYx33pvN-"
    "@^`3eW+mO)N7@Eu89<Ms2>s&S>C=Co^`?o*J10xj;7=c@BSCU&5^x2cFLh$^sjFsLzCyLV{aPA<NR&xJXQUWB0+QJ~mSDxi7MDj7"
    "|GvTpie<&M>$PrTQHCWNd)qjPJ#F&Y;D;X`o$%Us9th?_P8l&&R{{1dx`Ag7TtA9dT&0Xd0un)U2sehfkj6opW-Jr1W1~gO?DAUR"
    "2R8a;xdp=j#1WbeZtY24!?c!sy9))2zDVH8cPA@CcP=M-dg)ZWoOCV~b$3a8bn?didEn0-4HA`+Rwo2eBu&0~fk2vFqf+?02-"
    "GIn;-"
    "O4Q4qWuo!dU|j*bIss9S9QuKE#lu;}l(zF&u!@;EGo7CDs;iOimtqJ2<IUMl~6Xz{8QkZM7~#$<P%&vn?nd7A)s%_^90h;)fVu7e"
    "*&NDlW<eX)|pdpRcwu4G!smBu9g}pm(^2m!B0zQq0Z1^Bm^>Ph^WE@TKP5cP?=!5lWu8tWJlTUC79SX#zwV2fAqJmDsl&<&JEUPc"
    "5YY*&YQpHsED8;=t(;V~YsYYex4IL!IqU8KZ3zb-"
    "*z5d=U1Md}5}d<Lr{j?kYnfPx&faAhRP7Dzw%o8<vvgo7dq1gEW?J5i?Z~%n20KgMx4ig#p8>MW4J2RRxF^62{auL|{c&Ne7wYiB"
    "(KUr-Ugdp5DGO+8kD@o@dlDxEV2=fu@B)dv_NsSy4nq6*UR6YFXlJ<IS3uoLb)JX_`G<lgS)pSipEj>0&%2k}8(o?1b^p8&9U{Vc"
    "m}{o!W@tjk7V}1urnM3>7LQWI&;lJkIhd*&l9aG6CZNDcKAJVw1onp=0L*%HhchbKA_4oX15IbIS|?noPh`!37qw+M#VNY?ZdksH"
    "|e4LX=qwG+|-VLm5duS)(DznWFlFiqAJljB`z<6)H=KZYzf-PIWgahA<KY*HrIeh>pz}Fe8&QNRtTi$f8P(uaXR7$Tn;k7_7|iR*"
    "XYQ-3#N%Gpo`b7%r`=VY#sw95B375qKcU?Tnz~f(H}GoN^k~N*0Sw{|T^Mek|YB0AH01JOlGy60Wp}Epn_90Vf(RFMaefiFK1H-"
    "eVida?s<7+fl6$(bHoJM5PRgRE3dlL<V5S9iDMHs8ERq5=bP5D7#Y`H#KIO?VRc-IO8-NjGM|Agq@Yj!cF|G8$c8IphZQ-GDb0c#"
    "fvpmj&S24mPB(Kyf&#3yD(v8h|zT5K9YFD!!ye=3ORM{u~<zs>~pi}wRJe$oy5(}n82t)H4~w70`h(djOz3V&ghZ7ZEofE(QI4Dt"
    "m|a$Qk<xFs$*CZ$fgMwI8J~k65CzKc8Pd`!I@_EwIl_k74D)kP=?sE%<1BpJ1~=QAQV{wAmE!1gH$x^K%nYe*nOJ#d3qyIg~}vJ0"
    "utjnVU|!O!gg@jECXS%p32D8XJM_I9edr{X7+5Pw9z?vF{HW~tI^{anBux^_598Ah@87E?)HKQh!q(Iuxy=Sz@uSv#i<K26N%=%>"
    "pY!MaMK700U@@|rJes<PxbmwFjMdO#WN~;1sJ8oUqT*)?g*!XR-#(4D8iziOqN?w%UIb--ZN<X?S8@~+bEv(uBendu_>WII5tv@%"
    "fx5V-"
    "6@KPRD&?n+g0haxQn~HHFpMTx;kCGB+(LR>+!mq80n$$G4Y2KX_Fq;D$z^2*9LJ7?%E$YGbL>VyjLeuEPzSsAt9Tep1Q&*o-"
    "{uB?dsYgsS+$!Dmd$ktCqTsaO*C{vmWcnu&%WWgYaDu5fz&8gzmtRKv)9F6p9ioC+@Npkw{3OEEYwOQUIhdNL1$^Q*CIi?pp6-"
    "kK~CZ9N^?6OhS_*rw}fe7%#GA0xvU!CU;*Vy*NP!lrrS3=Ujm@CU)Q*0g#IBm4Ubuw$Z}NVg?%a_`dpSA?@9rLk=2tDMGaoRBWqC"
    "upc6-_nfY1#k5iwCC`~sk|`o3<-=SkyQm@~1=42pUNcFPPMmbEJZAxftW{MM?eW;SA;(?9<l`pp@e-"
    "m`XKQ>ZU2`qL2s4&il}5s&3D6226j&7l&8Bt^fqPSD4LY3!L{ci0Zpk;mQv(8k*k`9>a(jl^G>NnlT9AU=n-"
    "~U=^}`I7q2LL?qOZK;`$rUFuoz(q7;u2kMmj48<cg+5T~BoIFT!JFGIoksV=oAKY8+HMp_7vtOkLug=o4GVh%C@NQ$UvUgQ@D`yF"
    "zMZOASjBtgIGIqbmkQ@FpGDCgiw!M$U!>Im2v@=}|+3N6c)ZPl`vrB1jZLFzlKPClzq8hein`ndE_@du%0*;U^%EWCwx%Q8x}E9_"
    "Qfp;WmPu&JTn)V(HLMk%R|NlSZK<2yYy44G?}h9+K5fR48HjT67>lI#ghB1A*ZAhI2q-c*2u*-"
    "u1`GAZ9?x5(OnArKuy7Pk&%5B)}PK-4;T@<-`p!R6xc8XFx78GYlsOYLfLWEY{_nh*Wq)hq@h-m{UwRjNi&0v5`PSS-"
    "}c)8W2HCV$@Kh4*SOgj~!W48F6LsR=v%@y>Ysr<5GQqYc4Q8aF;ph*rFLbN(ea6m?ArHm%O?#g{lI|5Uf#Pp-"
    "R(87znMbc{+@<dP)}b!r)}+LYmA#K88Zbh2ysdkr8A?L}cAe0Yvy3>44~8t?UNrHX4*=NTo<8ZqJK+N*R=Mnc3!UCb&2|Yh>fYr3"
    "&zuaO<WqwvyW<VkH%=wN}(c6_qV*l(efAQ3O+AI`s1=PQzog`RPNl1!U_dVZO|yn?Yb3`;Aq(fsjjFpjALq1sY?g2JfQ^av4Z0B9"
    "UT>TnWKs$Ah>r1OaXG4%(qGp9gz#Q(xWox`t*dQy^%ESjY%yh(_rE1CNh~a4!AHf9ygGK4%aZr!9V@ui+l}6AB4pkTk3i^N2t+L4"
    ")ww8Wn@4SPXF%vTBwEmNcP-Fji=54A>|Jp++c$f~kWX0EHd&@rgnK3>gG0AS|>EAp_+y_(c#lkb%k%PRMTI&n*o!BG_wlO{l@mNO"
    "e7NX`(f45p11?b+C1*iA8ZW)!TQe7b+dMPJS2Sclrb}hbL39HAh4^y#Gh5>gGM_9#i9!*32Y5vXK1h$)$)YAgU<DB$0$@sXtMf`&"
    "@qzKZqUPndzTTp1=HE$rRy2LBc_4AO"
)

_ARTICLE_PROTOCOL_COMMIT_BYTES_B85 = (
    "LRx4!F+o`-Q(1T0uPFckdtZP65I_Te^+Etp06*v7urL6-"
    "W)iA;X*BkNjj8G~Xld#)X{V?frV}+Z(?9?K01~OR0Z&NN(rJhQVrXUx#cD!=Wh1}Am))$#5-"
    "un}Hyl>U(VW_FHWCGjkQAZ>s;pRJ1}$z#3k7mX&%S3Jz&SA(K?%XFst-l*M=m?egeJMcoNN^*N4t#l@kR-"
    "`?QcGnT6#WYLcLppmlUJ_U=_zR=qpAs(v&qO46s$lRnWdbqfx0<br6U>R#=ygd;L$VWm~^45l9Q)IR6)NML1B9ciXQi"
)

_ARTICLE_PROTOCOL_TREE_BYTES_B85 = (
    "LRx4!F+o`-Q(22mVtfDqYJdOnfBDD$@Avk9|Nr;@@4x;3e((R@Kl#6p^?U#O{^!-e0u@_^*Fi}U9-"
    "B&S5X9P;(9t}RrY4?%1kk}SG@5#zqiAYq#9}nS1U)9uh9hcvYGJABV2n*3YKN)fk4A)Mr=vvjdZ*%{Q3%j_AkY8<Kxv?8000Jn4F"
    ";M3XwYaf0MGyc00E!?05k!h05k<tDe4+}Pee2T8UO$Q4FCWD0000041uFSH1z-g000^d0000q0Tj`pG?O-"
    "|`4NRZPe^FMnK7s|WND_D6958WMj?b4MiH7LO))c5BLvZ=03o5K0%?;3!eq$ATL=P*6c}KY3=LtI3;_!)U{se}@QF#=>rUs09pxu"
    "asEGN^;z!R^l_S73$m-"
    "oLMlu9nF5I*<c9lMi!!=ZiM0pSZ2!aRzYOSO%zc$v(?vr&>yn}kRbXTL$pcz0M={iCq2msgxo4A2IRJpMRl}j8TW3ExtDT*^bM1U"
    "Xw(;z@J5QMlw8llyh{-"
    "}vtU^cc|9muyVYG4h43|s1iR>uMmo^cfCnRpO|4sYoCzyJUm9hWrq8AA;tWu8}02LZCg(%4QmoOB2~=H~Jw$chnRkOu&3pb+mf4>"
    "^X24CDgi(6%Lv`66cInHB}A14{zb0{6q&<9856Nrx$|JpKTQEdqfMH5Hq*slE`;uJ2z&>B3y^=!SZ;6PslOGCju{a15ekaqX1{6`"
    "O>x5;71;jYWY#r>(<eIXH0uOY)dnC^R_96C6k$SjaJ)p@_#Afvy-"
    "R1fmd@(ZkQ>Ds%;!1gj{N2t))lN1amAm8EMQkFhH#Zg&d3;E*#Tm&wWQAA5WsA-&vU|6&QSd#^w;#lZl327e-"
    "!I3bV<xKiUVgjx>}1&{$v%E{BA*E9rg%^ZLT42*&)RFbLyh*tI;D3GGO8nQ)AIuzi7A>tnlkc>=syDtF)jqD?(uRgRW{S%T<FT!k"
    "oEQo0A`<=sO@41ChJA(K={@@!L(16xdHj#u1RePqRWz4oA{ZAzguYV}L({ET)WM*uDk|X7aBw)OmvT^V%b)%_S5y$V(gVQ#VC*1$"
    "1NS|Z2b$lislsTmgj1Kmv)_N(^h&nv+d9Kez7+%#n$}OcWy2g^5uHZquTNvAgFvy-Uwz@lfyB{;x3AEKzp*WA$DNAwlzR}G6q?4!"
    "5Oe+GP?n!40yOLKX`3t8h)6;nmltRRnWI7?=gA2fRx`qsx-f><O+3h-1O@HF<NT&)C5oxSXfB"
)


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _launch_task(**changes: object) -> runner.OneCellLaunchTask:
    identity = b'{"profile":"synthetic-scientific-identity@1"}'
    values: dict[str, object] = {
        "array_position": 0,
        "wave": "f0",
        "role": "discovery",
        "task_map_id": "f0-map",
        "task_index": 0,
        "scientific_identity_bytes": identity,
        "scientific_identity_sha256": hashlib.sha256(identity).hexdigest(),
        "relative_task_directory": (f"f0/{0:020d}-{hashlib.sha256(identity).hexdigest()}"),
    }
    values.update(changes)
    return runner.OneCellLaunchTask(**values)  # type: ignore[arg-type]


def _resource_envelope(**changes: object) -> runner.OneCellSlurmResourceEnvelope:
    scientific_environment = (
        ("LANG", "C"),
        ("LC_ALL", "C"),
        ("TMPDIR", "/runtime/tmp"),
        ("NUMBA_CACHE_DIR", "/runtime/cache"),
        ("NUMBA_NUM_THREADS", "2"),
        ("OMP_NUM_THREADS", "2"),
        ("OPENBLAS_NUM_THREADS", "2"),
        ("MKL_NUM_THREADS", "2"),
        ("NUMEXPR_NUM_THREADS", "2"),
        ("BLIS_NUM_THREADS", "2"),
        ("VECLIB_MAXIMUM_THREADS", "2"),
        ("OMP_DYNAMIC", "FALSE"),
        ("MKL_DYNAMIC", "FALSE"),
    )
    values: dict[str, object] = {
        "profile": "tetris-pre-one-cell-slurm-resource-envelope@1",
        "partition": "compute",
        "wall_minutes": 17,
        "cpus_per_task": 2,
        "memory_mib": 4096,
        "array_concurrency": 1,
        "signal_name": "SIGUSR1",
        "signal_warning_seconds": 900,
        "receipt_handshake_seconds": 60,
        "scheduler_timeout_seconds": 30,
        "max_requeues_per_task": 2,
        "sbatch_executable": "/usr/bin/sbatch",
        "sbatch_executable_realpath": "/usr/bin/sbatch",
        "sbatch_owner_uid": 0,
        "sbatch_mode": 0o755,
        "sbatch_size_bytes": 1,
        "sbatch_sha256": _SHA256_A,
        "sbatch_version": f"content-sha256:{_SHA256_A}",
        "scontrol_executable": "/usr/bin/scontrol",
        "scontrol_executable_realpath": "/usr/bin/scontrol",
        "scontrol_owner_uid": 0,
        "scontrol_mode": 0o755,
        "scontrol_size_bytes": 1,
        "scontrol_sha256": _SHA256_B,
        "scontrol_version": f"content-sha256:{_SHA256_B}",
        "scheduler_environment": (("LANG", "C"), ("LC_ALL", "C")),
        "scientific_environment": scientific_environment,
    }
    values.update(changes)
    return runner.OneCellSlurmResourceEnvelope(**values)  # type: ignore[arg-type]


def _runner_paths(tmp_path: Path, **changes: object) -> runner.OneCellRunnerPaths:
    root = tmp_path.resolve()
    campaign_root = root / "campaign"
    private_root = campaign_root / "private"
    authorization_directory = root / "authorization"
    python_executable = root / "runtime" / "bin" / "python"
    runtime_python_bytes = str(python_executable).encode() + b"\n"
    values: dict[str, object] = {
        "campaign_root": str(campaign_root),
        "authorization_checkout": str(root / "checkout"),
        "authorization_directory": str(authorization_directory),
        "runtime_python_file": str(authorization_directory / "runtime-python.path"),
        "runtime_python_bytes": runtime_python_bytes,
        "runtime_python_sha256": hashlib.sha256(runtime_python_bytes).hexdigest(),
        "python_executable": str(python_executable),
        "python_executable_realpath": str(python_executable),
        "python_executable_sha256": _SHA256_A,
        "python_executable_size_bytes": 1,
        "task_root": str(private_root / "tasks"),
        "attempt_root": str(private_root / "attempts"),
        "log_root": str(private_root / "logs"),
        "cache_root": str(private_root / "cache"),
        "temporary_root": str(private_root / "tmp"),
        "submission_ledger_root": str(private_root / "submission-ledger"),
        "submission_ledger_lock": str(private_root / "submission-ledger" / "ledger.lock"),
        "authorized_run_directory": str(private_root / "run"),
        "batch_script": str(root / "run_pre_one_cell.sbatch"),
        "stdout_template": str(private_root / "logs" / "slurm-%A_%a.out"),
        "stderr_template": str(private_root / "logs" / "slurm-%A_%a.err"),
        "git_executable": "/usr/bin/git",
        "git_executable_realpath": "/usr/bin/git",
        "git_owner_uid": 0,
        "git_mode": 0o755,
        "git_size_bytes": 1,
        "git_sha256": _SHA256_B,
        "git_version": "git version synthetic",
        "coordinator_remote_url": "ssh://coordinator.example/tetris-kpz-data.git",
        "coordinator_fetch_refspec": "+refs/heads/main:refs/remotes/origin/main",
    }
    values.update(changes)
    return runner.OneCellRunnerPaths(**values)  # type: ignore[arg-type]


_PUBLIC_API = (
    "OneCellRunnerValidationError",
    "OneCellRunnerAuthorizationError",
    "OneCellSchedulerError",
    "OneCellLaunchTask",
    "OneCellSlurmResourceEnvelope",
    "OneCellRunnerPaths",
    "OneCellLaunchAuthority",
    "OneCellAuthorizedTask",
    "OneCellRunnerOutcome",
    "OneCellSubmissionOutcome",
    "load_one_cell_launch_authority",
    "list_one_cell_launch_tasks",
    "explain_one_cell_launch_task",
    "authorize_one_cell_slurm_task",
    "run_one_cell_authorized_task",
    "submit_one_cell_launch",
)

_RECORD_FIELDS = {
    "OneCellLaunchTask": (
        "array_position",
        "wave",
        "role",
        "task_map_id",
        "task_index",
        "scientific_identity_bytes",
        "scientific_identity_sha256",
        "relative_task_directory",
    ),
    "OneCellSlurmResourceEnvelope": (
        "profile",
        "partition",
        "wall_minutes",
        "cpus_per_task",
        "memory_mib",
        "array_concurrency",
        "signal_name",
        "signal_warning_seconds",
        "receipt_handshake_seconds",
        "scheduler_timeout_seconds",
        "max_requeues_per_task",
        "sbatch_executable",
        "sbatch_executable_realpath",
        "sbatch_owner_uid",
        "sbatch_mode",
        "sbatch_size_bytes",
        "sbatch_sha256",
        "sbatch_version",
        "scontrol_executable",
        "scontrol_executable_realpath",
        "scontrol_owner_uid",
        "scontrol_mode",
        "scontrol_size_bytes",
        "scontrol_sha256",
        "scontrol_version",
        "scheduler_environment",
        "scientific_environment",
    ),
    "OneCellRunnerPaths": (
        "campaign_root",
        "authorization_checkout",
        "authorization_directory",
        "runtime_python_file",
        "runtime_python_bytes",
        "runtime_python_sha256",
        "python_executable",
        "python_executable_realpath",
        "python_executable_sha256",
        "python_executable_size_bytes",
        "task_root",
        "attempt_root",
        "log_root",
        "cache_root",
        "temporary_root",
        "submission_ledger_root",
        "submission_ledger_lock",
        "authorized_run_directory",
        "batch_script",
        "stdout_template",
        "stderr_template",
        "git_executable",
        "git_executable_realpath",
        "git_owner_uid",
        "git_mode",
        "git_size_bytes",
        "git_sha256",
        "git_version",
        "coordinator_remote_url",
        "coordinator_fetch_refspec",
    ),
    "OneCellLaunchAuthority": (
        "authorization_path",
        "launch_bytes",
        "launch_sha256",
        "launch_commit",
        "launch_path",
        "launch_size_bytes",
        "profile",
        "launch_id",
        "lane",
        "campaign",
        "deployment_lock_bytes",
        "deployment_lock_sha256",
        "deployment_certificate_bytes",
        "deployment_certificate_sha256",
        "admission_bytes",
        "admission_sha256",
        "protocol_commit",
        "protocol_blob",
        "protocol_sha256",
        "software_commit",
        "wheel_sha256",
        "campaign_commit",
        "campaign_manifest_sha256",
        "deployment_commit",
        "admission_commit",
        "branch_decision_bytes",
        "branch_decision_sha256",
        "branch_commit",
        "branch_path",
        "branch_size_bytes",
        "mapping_profile",
        "ordered_tasks_profile",
        "ordered_tasks_sha256",
        "ordered_tasks",
        "readback_bytes",
        "readback_sha256",
        "git_environment",
        "resources",
        "paths",
    ),
    "OneCellAuthorizedTask": (
        "launch",
        "array_position",
        "task",
        "scientific_identity_bytes",
        "scientific_identity_sha256",
        "slurm_array_job_id",
        "slurm_array_task_id",
        "slurm_job_id",
        "restart_count",
        "attempt_id",
        "task_directory",
        "attempt_directory",
        "submission_claim_sha256",
        "submission_receipt_sha256",
        "requeue_target",
    ),
    "OneCellRunnerOutcome": (
        "disposition",
        "array_position",
        "task_map_id",
        "task_index",
        "attempt_id",
        "task_directory",
        "manifest_path",
        "generation",
        "checkpoint_count",
        "snapshot_count",
        "used_fallback",
    ),
    "OneCellSubmissionOutcome": (
        "disposition",
        "launch_sha256",
        "claim_path",
        "claim_sha256",
        "receipt_path",
        "receipt_sha256",
        "sbatch_argv_sha256",
        "array_job_id",
    ),
}

_FUNCTION_PARAMETERS = {
    "load_one_cell_launch_authority": ("authorization_path",),
    "list_one_cell_launch_tasks": ("launch",),
    "explain_one_cell_launch_task": ("launch", "array_position"),
    "authorize_one_cell_slurm_task": (
        "launch",
        "submission_claim_bytes",
        "submission_receipt_bytes",
    ),
    "run_one_cell_authorized_task": ("authorization",),
    "submit_one_cell_launch": ("launch",),
}


def test_public_surface_records_and_signatures_are_exact() -> None:
    assert tuple(runner.__all__) == _PUBLIC_API

    errors = (
        runner.OneCellRunnerValidationError,
        runner.OneCellRunnerAuthorizationError,
        runner.OneCellSchedulerError,
    )
    for error in errors:
        assert error.__bases__ == (RuntimeError,)
    assert len(set(errors)) == 3

    for name, expected_fields in _RECORD_FIELDS.items():
        record_type = getattr(runner, name)
        fields = dataclasses.fields(record_type)
        assert tuple(field.name for field in fields) == expected_fields
        assert all(field.kw_only for field in fields)
        assert record_type.__dataclass_params__.frozen is True
        assert "__dict__" not in record_type.__slots__
        with pytest.raises(TypeError):
            record_type(object())

    for name, expected_names in _FUNCTION_PARAMETERS.items():
        function = getattr(runner, name)
        parameters = tuple(inspect.signature(function).parameters.values())
        assert tuple(parameter.name for parameter in parameters) == expected_names
        assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters)
        assert all(parameter.default is inspect.Parameter.empty for parameter in parameters)


def test_public_entry_snapshots_deep_clone_every_nested_record(tmp_path: Path) -> None:
    from tests.test_one_cell_campaign import _base_fixture

    configuration_bytes, task_map_members = _base_fixture()
    campaign = runner.load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=task_map_members,
    )
    launch = dataclasses.replace(
        runner._fixture_launch_authority_for_test(directory=str(tmp_path / "authority")),
        campaign=campaign,
    )
    authorization = dataclasses.replace(
        runner._fixture_authorized_task_for_test(directory=str(tmp_path / "authority")),
        launch=launch,
        task=launch.ordered_tasks[0],
    )

    launch_snapshot = runner._snapshot_record(launch, runner.OneCellLaunchAuthority)
    authorization_snapshot = runner._snapshot_record(authorization, runner.OneCellAuthorizedTask)
    assert type(launch_snapshot) is runner.OneCellLaunchAuthority
    assert type(authorization_snapshot) is runner.OneCellAuthorizedTask
    assert launch_snapshot is not launch
    assert launch_snapshot.campaign is not launch.campaign
    assert launch_snapshot.resources is not launch.resources
    assert launch_snapshot.paths is not launch.paths
    assert launch_snapshot.ordered_tasks is not launch.ordered_tasks
    assert launch_snapshot.ordered_tasks[0] is not launch.ordered_tasks[0]
    assert launch_snapshot.campaign.bootstrap_matrices[0] is not launch.campaign.bootstrap_matrices[0]
    assert launch_snapshot.campaign.task_maps[0] is not launch.campaign.task_maps[0]
    assert launch_snapshot.campaign.horizon_branches[0] is not launch.campaign.horizon_branches[0]
    assert launch_snapshot.campaign.task_map_members is not launch.campaign.task_map_members
    assert authorization_snapshot is not authorization
    assert authorization_snapshot.launch is not authorization.launch
    assert authorization_snapshot.task is authorization_snapshot.launch.ordered_tasks[0]
    assert authorization_snapshot.task is not authorization.task

    original_partition = launch_snapshot.resources.partition
    original_log_root = launch_snapshot.paths.log_root
    original_role = launch_snapshot.ordered_tasks[0].role
    original_map_role = launch_snapshot.campaign.task_maps[0].role
    object.__setattr__(launch.resources, "partition", "caller-mutated")
    object.__setattr__(launch.paths, "log_root", "/caller-mutated")
    object.__setattr__(launch.ordered_tasks[0], "role", "caller-mutated")
    object.__setattr__(launch.campaign.task_maps[0], "role", "caller-mutated")
    assert launch_snapshot.resources.partition == original_partition
    assert launch_snapshot.paths.log_root == original_log_root
    assert launch_snapshot.ordered_tasks[0].role == original_role
    assert launch_snapshot.campaign.task_maps[0].role == original_map_role
    assert authorization_snapshot.launch.resources.partition == original_partition


def test_public_annotations_resolve_to_the_frozen_types() -> None:
    namespace = vars(runner)
    expected = {
        "OneCellLaunchTask": {
            "array_position": int,
            "wave": str,
            "role": str,
            "task_map_id": str,
            "task_index": int,
            "scientific_identity_bytes": bytes,
            "scientific_identity_sha256": str,
            "relative_task_directory": str,
        },
        "OneCellSlurmResourceEnvelope": {
            **{name: str for name in ("profile", "partition", "signal_name")},
            **{
                name: int
                for name in (
                    "wall_minutes",
                    "cpus_per_task",
                    "memory_mib",
                    "array_concurrency",
                    "signal_warning_seconds",
                    "receipt_handshake_seconds",
                    "scheduler_timeout_seconds",
                    "max_requeues_per_task",
                    "sbatch_owner_uid",
                    "sbatch_mode",
                    "sbatch_size_bytes",
                    "scontrol_owner_uid",
                    "scontrol_mode",
                    "scontrol_size_bytes",
                )
            },
            **{
                name: str
                for name in (
                    "sbatch_executable",
                    "sbatch_executable_realpath",
                    "sbatch_sha256",
                    "sbatch_version",
                    "scontrol_executable",
                    "scontrol_executable_realpath",
                    "scontrol_sha256",
                    "scontrol_version",
                )
            },
            "scheduler_environment": tuple[tuple[str, str], ...],
            "scientific_environment": tuple[tuple[str, str], ...],
        },
        "OneCellRunnerPaths": {
            **{
                name: str
                for name in (
                    "campaign_root",
                    "authorization_checkout",
                    "authorization_directory",
                    "runtime_python_file",
                    "runtime_python_sha256",
                    "python_executable",
                    "python_executable_realpath",
                    "python_executable_sha256",
                    "task_root",
                    "attempt_root",
                    "log_root",
                    "cache_root",
                    "temporary_root",
                    "submission_ledger_root",
                    "submission_ledger_lock",
                    "authorized_run_directory",
                    "batch_script",
                    "stdout_template",
                    "stderr_template",
                    "git_executable",
                    "git_executable_realpath",
                    "git_sha256",
                    "git_version",
                    "coordinator_remote_url",
                    "coordinator_fetch_refspec",
                )
            },
            "runtime_python_bytes": bytes,
            "python_executable_size_bytes": int,
            "git_owner_uid": int,
            "git_mode": int,
            "git_size_bytes": int,
        },
        "OneCellLaunchAuthority": {
            **{
                name: str
                for name in (
                    "authorization_path",
                    "launch_sha256",
                    "launch_commit",
                    "launch_path",
                    "profile",
                    "launch_id",
                    "lane",
                    "deployment_lock_sha256",
                    "deployment_certificate_sha256",
                    "admission_sha256",
                    "protocol_commit",
                    "protocol_blob",
                    "protocol_sha256",
                    "software_commit",
                    "wheel_sha256",
                    "campaign_commit",
                    "campaign_manifest_sha256",
                    "deployment_commit",
                    "admission_commit",
                    "mapping_profile",
                    "ordered_tasks_profile",
                    "ordered_tasks_sha256",
                    "readback_sha256",
                )
            },
            **{
                name: bytes
                for name in (
                    "launch_bytes",
                    "deployment_lock_bytes",
                    "deployment_certificate_bytes",
                    "admission_bytes",
                    "readback_bytes",
                )
            },
            "launch_size_bytes": int,
            "campaign": runner.OneCellCampaignAuthority,
            "branch_decision_bytes": bytes | None,
            "branch_decision_sha256": str | None,
            "branch_commit": str | None,
            "branch_path": str | None,
            "branch_size_bytes": int | None,
            "ordered_tasks": tuple[runner.OneCellLaunchTask, ...],
            "git_environment": tuple[tuple[str, str], ...],
            "resources": runner.OneCellSlurmResourceEnvelope,
            "paths": runner.OneCellRunnerPaths,
        },
        "OneCellAuthorizedTask": {
            "launch": runner.OneCellLaunchAuthority,
            "array_position": int,
            "task": runner.OneCellLaunchTask,
            "scientific_identity_bytes": bytes,
            "scientific_identity_sha256": str,
            "slurm_array_job_id": str,
            "slurm_array_task_id": str,
            "slurm_job_id": str,
            "restart_count": int,
            "attempt_id": str,
            "task_directory": str,
            "attempt_directory": str,
            "submission_claim_sha256": str,
            "submission_receipt_sha256": str,
            "requeue_target": str,
        },
        "OneCellRunnerOutcome": {
            "disposition": typing.Literal["complete", "reused", "requeue-submitted"],
            "array_position": int,
            "task_map_id": str,
            "task_index": int,
            "attempt_id": str,
            "task_directory": str,
            "manifest_path": str | None,
            "generation": int,
            "checkpoint_count": int,
            "snapshot_count": int,
            "used_fallback": bool,
        },
        "OneCellSubmissionOutcome": {
            "disposition": typing.Literal["accepted"],
            "launch_sha256": str,
            "claim_path": str,
            "claim_sha256": str,
            "receipt_path": str,
            "receipt_sha256": str,
            "sbatch_argv_sha256": str,
            "array_job_id": str,
        },
    }
    for name, expected_annotations in expected.items():
        assert typing.get_type_hints(getattr(runner, name), globalns=namespace) == expected_annotations

    function_hints = {
        "load_one_cell_launch_authority": {
            "authorization_path": str,
            "return": runner.OneCellLaunchAuthority,
        },
        "list_one_cell_launch_tasks": {
            "launch": runner.OneCellLaunchAuthority,
            "return": tuple[runner.OneCellLaunchTask, ...],
        },
        "explain_one_cell_launch_task": {
            "launch": runner.OneCellLaunchAuthority,
            "array_position": int,
            "return": bytes,
        },
        "authorize_one_cell_slurm_task": {
            "launch": runner.OneCellLaunchAuthority,
            "submission_claim_bytes": bytes,
            "submission_receipt_bytes": bytes,
            "return": runner.OneCellAuthorizedTask,
        },
        "run_one_cell_authorized_task": {
            "authorization": runner.OneCellAuthorizedTask,
            "return": runner.OneCellRunnerOutcome,
        },
        "submit_one_cell_launch": {
            "launch": runner.OneCellLaunchAuthority,
            "return": runner.OneCellSubmissionOutcome,
        },
    }
    for name, expected_hints in function_hints.items():
        assert typing.get_type_hints(getattr(runner, name), globalns=namespace) == expected_hints


def test_runner_is_explicit_only_and_has_no_eager_checkpoint_or_numba_binding() -> None:
    for name in _PUBLIC_API:
        assert not hasattr(tetris_ballistic, name)
        assert not hasattr(engine_root, name)

    forbidden_modules = {
        "numba",
        "tetris_ballistic.engine.one_cell_checkpoint",
        "tetris_ballistic.scripts.run_one_cell",
        "tetris_ballistic.scripts.run_batch",
        "tetris_ballistic.run_artifacts",
    }
    for value in vars(runner).values():
        if isinstance(value, types.ModuleType):
            assert value.__name__ not in forbidden_modules
        module_name = getattr(value, "__module__", "")
        assert module_name not in forbidden_modules

    source = inspect.getsource(runner)
    tree = ast.parse(source)
    # Only module-scope imports are forbidden.  The production contract
    # deliberately performs its first checkpoint import inside the fully
    # authorized execution entry.
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert all(alias.name not in forbidden_modules for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_modules


def test_runner_source_has_no_scheduler_or_scientific_import_side_effect() -> None:
    source_path = Path(runner.__file__)
    assert source_path.name == "one_cell_runner.py"
    source = source_path.read_text(encoding="utf-8")
    assert "os.system(" not in source
    assert "shell=True" not in source
    assert "tetris_ballistic.scripts.run_one_cell" not in source
    assert "tetris_ballistic.scripts.run_batch" not in source
    assert "tetris_ballistic.run_artifacts" not in source


def test_import_is_lazy_in_a_fresh_isolated_interpreter(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-be-created"
    script = f"""
import pathlib
import sys
import tetris_ballistic.engine.one_cell_runner
forbidden = {{
    'numba',
    'tetris_ballistic.engine.one_cell_checkpoint',
    'tetris_ballistic.scripts.run_one_cell',
    'tetris_ballistic.scripts.run_batch',
}}
assert forbidden.isdisjoint(sys.modules)
assert not pathlib.Path({str(marker)!r}).exists()
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr == b""


def test_private_no_hpc_probe_fails_without_alias_or_mutation(tmp_path: Path) -> None:
    script = """
import builtins
import pathlib
import sys
from tetris_ballistic.engine import one_cell_runner as runner

before = tuple(pathlib.Path.cwd().iterdir())
real_import = builtins.__import__
def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'numba' or name.startswith('numba.'):
        raise ModuleNotFoundError("No module named 'numba'", name='numba')
    return real_import(name, globals, locals, fromlist, level)
builtins.__import__ = blocked_import
try:
    runner._probe_one_cell_checkpoint_import_without_hpc_for_test()
except ImportError as error:
    assert str(error) == (
        "tetris_ballistic.engine.one_cell_checkpoint requires a compatible "
        "Numba installation; install the 'tetris_ballistic[hpc]' extra"
    )
else:
    raise AssertionError('the blocked HPC dependency unexpectedly imported')
finally:
    builtins.__import__ = real_import

assert 'tetris_ballistic.engine.one_cell_checkpoint' not in sys.modules
for value in vars(runner).values():
    assert getattr(value, '__module__', '') != 'tetris_ballistic.engine.one_cell_checkpoint'
assert tuple(pathlib.Path.cwd().iterdir()) == before
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr == b""


@pytest.mark.parametrize(
    "payload",
    (
        b'{"profile":"synthetic-fixture@1"}',
        b'{"profile":"synthetic-fixture@1"}\r\n',
        b'{"profile":"synthetic-fixture@1"}\n\n',
        b' {"profile":"synthetic-fixture@1"}\n',
        b'{ "profile": "synthetic-fixture@1" }\n',
        b'{"profile":"synthetic-fixture@1","profile":"synthetic-fixture@1"}\n',
        b'\xef\xbb\xbf{"profile":"synthetic-fixture@1"}\n',
        b'{"profile":"synthetic-fixture@1","value":NaN}\n',
        b'{"profile":"synthetic-fixture@1","value":1.5}\n',
        b'{"profile":"synthetic-fixture@1","value":18446744073709551616}\n',
        b"\xff\n",
    ),
)
def test_canonical_json_parser_rejects_noncanonical_or_hostile_bytes(
    payload: bytes,
) -> None:
    with pytest.raises(runner.OneCellRunnerValidationError):
        runner._parse_canonical_json_for_test(
            payload=payload,
            profile="synthetic-fixture@1",
        )


def test_canonical_json_and_jsonl_parser_oracles_are_strict() -> None:
    profile = "synthetic-fixture@1"
    first = {"fixture": _FIXTURE_METADATA, "profile": profile, "row": 0}
    second = {"fixture": _FIXTURE_METADATA, "profile": profile, "row": 1}
    first_bytes = _canonical_json(first)
    second_bytes = _canonical_json(second)

    assert (
        runner._parse_canonical_json_for_test(
            payload=first_bytes,
            profile=profile,
        )
        == first
    )
    assert runner._parse_canonical_jsonl_for_test(
        payload=first_bytes + second_bytes,
        profile=profile,
    ) == (first, second)

    with pytest.raises(runner.OneCellRunnerValidationError):
        runner._parse_canonical_json_for_test(
            payload=first_bytes,
            profile="wrong-fixture@1",
        )
    for payload in (
        first_bytes[:-1],
        first_bytes + b"\n",
        first_bytes + b"\r\n",
        first_bytes + _canonical_json({**second, "profile": "wrong-fixture@1"}),
    ):
        with pytest.raises(runner.OneCellRunnerValidationError):
            runner._parse_canonical_jsonl_for_test(
                payload=payload,
                profile=profile,
            )
    with pytest.raises(runner.OneCellRunnerValidationError):
        runner._parse_canonical_jsonl_for_test(
            payload=first_bytes + second_bytes,
            profile=profile,
            row_maximum=1,
        )


def _fixture_launch_bytes(*, profile: str, fixture: object = _FIXTURE_METADATA) -> bytes:
    commit = "1" * 40
    digest = "2" * 64

    def file_ref(path: str) -> dict[str, object]:
        return {
            "commit": commit,
            "path": path,
            "sha256": digest,
            "size_bytes": 1,
        }

    def tool(path: str, *, scheduler: bool) -> dict[str, object]:
        return {
            "path": path,
            "realpath": path,
            "owner_uid": 0,
            "mode": "0755",
            "size_bytes": 1,
            "sha256": digest,
            "version": (f"content-sha256:{digest}" if scheduler else "git version synthetic"),
        }

    return _canonical_json(
        {
            "profile": profile,
            "launch_id": "fixture-launch",
            "lane": "f0",
            "self_path": "authorizations/fixture/launch.json",
            "authorities": {
                "protocol_commit": commit,
                "protocol_sha256": digest,
                "source_commit": commit,
                "wheel_sha256": digest,
                "campaign_commit": commit,
                "campaign_manifest_sha256": digest,
                "configuration_sha256": digest,
                "deployment_lock": file_ref("campaigns/fixture/deployment.lock.json"),
                "deployment": file_ref("authorizations/fixture/deployment.json"),
                "admission": file_ref("authorizations/fixture/admission.json"),
                "branch": None,
            },
            "ordered_tasks": {
                "profile": "tetris-pre-one-cell-ordered-tasks@1",
                "path": "authorizations/fixture/ordered-tasks.jsonl",
                "sha256": digest,
                "size_bytes": 1,
                "task_count": 1,
            },
            "mapping": {
                "profile": "tetris-pre-one-cell-slurm-array-position@1",
                "array_first": 0,
                "array_last": 0,
                "array_step": 1,
            },
            "batch_script": {
                "source_commit": commit,
                "path": "scripts/easley/run_pre_one_cell.sbatch",
                "git_blob": commit,
                "sha256": digest,
                "size_bytes": 1,
            },
            "resources": {
                "profile": "tetris-pre-one-cell-slurm-resource-envelope@1",
                "partition": "compute",
                "wall_minutes": 17,
                "cpus_per_task": 1,
                "memory_mib": 1,
                "array_concurrency": 1,
                "signal_name": "SIGUSR1",
                "signal_warning_seconds": 900,
                "receipt_handshake_seconds": 60,
                "scheduler_timeout_seconds": 30,
                "max_requeues_per_task": 0,
                "sbatch_executable": "/usr/bin/sbatch",
                "scontrol_executable": "/usr/bin/scontrol",
                "scheduler_environment": {"LANG": "C", "LC_ALL": "C"},
                "scientific_environment": {},
            },
            "runtime_python": {
                "sidecar_path": "/private/authorization/runtime-python.path",
                "sidecar_bytes_hex": "2f707974686f6e0a",
                "sidecar_sha256": digest,
                "sidecar_size_bytes": 8,
                "executable_path": "/python",
                "executable_realpath": "/python",
                "executable_sha256": digest,
                "executable_size_bytes": 1,
            },
            "git_environment": {
                "LANG": "C",
                "LC_ALL": "C",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_COUNT": "0",
                "GIT_ATTR_NOSYSTEM": "1",
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
            },
            "git_local_config": {
                "core_repositoryformatversion": "0",
                "core_filemode": "true",
                "core_bare": "false",
                "core_logallrefupdates": "true",
                "remote_origin_url": "ssh://example/coordinator.git",
                "remote_origin_fetch": "+refs/heads/main:refs/remotes/origin/main",
                "branch_main_remote": "origin",
                "branch_main_merge": "refs/heads/main",
            },
            "tool_identities": {
                "sbatch": tool("/usr/bin/sbatch", scheduler=True),
                "scontrol": tool("/usr/bin/scontrol", scheduler=True),
                "git": tool("/usr/bin/git", scheduler=False),
            },
            "paths": {
                "campaign_root": "/private/campaign",
                "authorization_checkout": "/private/checkout",
                "authorization_directory": "/private/authorization",
                "runtime_python_file": "/private/authorization/runtime-python.path",
                "python_executable": "/python",
                "task_root": "/private/campaign/private/tasks",
                "attempt_root": "/private/attempts",
                "log_root": "/private/logs",
                "cache_root": "/private/cache",
                "temporary_root": "/private/tmp",
                "submission_ledger_root": "/private/ledger",
                "submission_ledger_lock": "/private/ledger/ledger.lock",
                "authorized_run_directory": "/private/run",
                "batch_script": "/private/run_pre_one_cell.sbatch",
                "stdout_template": "/private/logs/slurm-%A_%a.out",
                "stderr_template": "/private/logs/slurm-%A_%a.err",
                "git_executable": "/usr/bin/git",
                "coordinator_remote_url": "ssh://example/coordinator.git",
                "coordinator_fetch_refspec": "+refs/heads/main:refs/remotes/origin/main",
            },
            "user_approval": {
                "actor": "fixture-reviewer",
                "approved_at_utc": "2026-07-16T00:00:00Z",
                "scope": "f0",
            },
            "fixture": fixture,
        }
    )


def _admission_bytes(
    *,
    profile: str = "tetris-pre-one-cell-admission@1",
    lane_id: str = "f0",
    task_map_id: str = "f0",
    task_count: int = 8,
    fixture: object | None = None,
) -> bytes:
    commit = "1" * 40
    digest = "2" * 64

    def file_ref(path: str) -> dict[str, object]:
        return {
            "commit": commit,
            "path": path,
            "sha256": digest,
            "size_bytes": 1,
        }

    value: dict[str, object] = {
        "profile": profile,
        "authorities": {
            "protocol_commit": commit,
            "protocol_sha256": digest,
            "source_commit": commit,
            "wheel_sha256": digest,
            "campaign_commit": commit,
            "configuration_sha256": digest,
            "deployment_lock": file_ref("campaigns/pre-one-cell-discovery-v1/deployment.lock.json"),
            "deployment": file_ref("authorizations/pre-one-cell-discovery-v1/deployment/certificate.json"),
            "branch": None,
        },
        "lane": {
            "lane_id": lane_id,
            "wave": lane_id,
            "role": "excluded-forensic-canary",
            "task_map_id": task_map_id,
            "task_count": task_count,
        },
        "decision": "admitted",
        "evidence": {
            "f0_completion": None,
            "initial_p0_completion": None,
            "branch_decision": None,
            "confirmation_completion": None,
            "b2_precision_audit": None,
            "b2_resource_admission": None,
            "clean_resource_admission": None,
        },
        "user_approval": {
            "actor": "reviewer",
            "approved_at_utc": "2026-07-16T00:00:00Z",
            "scope": lane_id,
        },
    }
    if fixture is not None:
        value["fixture"] = fixture
    return _canonical_json(value)


def _git_fixture_command(git: str, repository: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        [git, "-C", str(repository), *arguments],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(runner._GIT_ENVIRONMENT),
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    return completed.stdout


def _git_object_sha1(kind: str, payload: bytes) -> str:
    header = f"{kind} {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _install_git_fixture_object(git: str, repository: Path, kind: str, payload: bytes) -> str:
    completed = subprocess.run(
        [git, "-C", str(repository), "hash-object", "-t", kind, "-w", "--stdin"],
        check=False,
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(runner._GIT_ENVIRONMENT),
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stderr == b""
    return completed.stdout.decode("ascii").strip()


def _commit_git_fixture(git: str, repository: Path, message: str) -> str:
    _git_fixture_command(git, repository, "add", "--all")
    _git_fixture_command(
        git,
        repository,
        "-c",
        "user.name=Slice 8B Fixture",
        "-c",
        "user.email=slice8b@example.invalid",
        "commit",
        "--no-gpg-sign",
        "-m",
        message,
    )
    return _git_fixture_command(git, repository, "rev-parse", "HEAD").decode("ascii").strip()


def _write_fixture_member(root: Path, relative_path: str, payload: bytes, *, mode: int = 0o600) -> Path:
    selected = root / relative_path
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_bytes(payload)
    selected.chmod(mode)
    return selected


def _file_reference(commit: str, path: str, payload: bytes) -> dict[str, object]:
    return {
        "commit": commit,
        "path": path,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }


def _tool_identity(path: Path, *, scheduler: bool, version: str | None = None) -> dict[str, object]:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    info = path.stat()
    return {
        "path": str(path),
        "realpath": str(path),
        "owner_uid": info.st_uid,
        "mode": f"{info.st_mode & 0o7777:04o}",
        "size_bytes": len(payload),
        "sha256": digest,
        "version": f"content-sha256:{digest}" if scheduler else version,
    }


def _build_public_loader_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build an ineligible authority graph using only private temp Git repos."""

    from tests.test_one_cell_campaign import _base_fixture

    located_git = shutil.which("git")
    assert located_git is not None
    git = os.path.realpath(located_git)
    git_path = Path(git)
    git_info = git_path.stat()
    if git_info.st_uid == os.geteuid():
        pytest.skip("the loader trust fixture requires non-current-user system Git ownership")
    git_version_process = subprocess.run(
        [git, "--version"],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(runner._GIT_ENVIRONMENT),
        timeout=30,
    )
    assert git_version_process.returncode == 0
    assert git_version_process.stderr == b""
    git_version = git_version_process.stdout.decode("ascii").strip()

    trusted_base = tmp_path / "trusted"
    trusted_base.mkdir(mode=0o700)
    article_checkout = trusted_base / "article"
    software_checkout = trusted_base / "software"
    coordinator_checkout = trusted_base / "coordinator"
    environment_root = trusted_base / "environment"
    readback_root = trusted_base / "readbacks"
    authorization_directory = readback_root / "f0-0001"
    campaign_root = trusted_base / "campaign"
    private_root = campaign_root / "private"
    for directory in (
        article_checkout,
        software_checkout,
        coordinator_checkout,
        environment_root,
        readback_root,
        authorization_directory,
        campaign_root,
        private_root,
        private_root / "tasks",
        private_root / "attempts",
        private_root / "logs",
        private_root / "cache",
        private_root / "cache" / "numba",
        private_root / "tmp",
        private_root / "submission-ledger",
        private_root / "submission-ledger" / "claims",
        private_root / "submission-ledger" / "receipts",
        private_root / "submission-ledger" / "requeue-permits",
        private_root / "submission-ledger" / "requeue-results",
        private_root / "run",
        trusted_base / "deployed",
    ):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    ledger_lock = private_root / "submission-ledger" / "ledger.lock"
    ledger_lock.write_bytes(b"lock\n")
    ledger_lock.chmod(0o600)

    protocol_bytes = bz2.decompress(base64.b85decode(_ARTICLE_PROTOCOL_BYTES_B85))
    protocol_commit_bytes = bz2.decompress(base64.b85decode(_ARTICLE_PROTOCOL_COMMIT_BYTES_B85))
    protocol_tree_bytes = bz2.decompress(base64.b85decode(_ARTICLE_PROTOCOL_TREE_BYTES_B85))
    assert len(protocol_bytes) == 44_883
    assert hashlib.sha256(protocol_bytes).hexdigest() == (
        "ab2f2974daf27f70af76d3039f6ac6c9b2cdecfba30a4c4a2ebd3d3652874358"
    )
    assert _git_object_sha1("blob", protocol_bytes) == "b7b654bb8d2809c409ce6ca24eb21d3afebf7885"
    assert _git_object_sha1("commit", protocol_commit_bytes) == "85404aee4dab7ade81c6893fac9f34aeaddf50dd"
    assert _git_object_sha1("tree", protocol_tree_bytes) == "40adba4c377757577978b539bb55932a8abaa10e"
    _git_fixture_command(git, article_checkout, "init", "--initial-branch=main")
    assert _install_git_fixture_object(git, article_checkout, "blob", protocol_bytes) == (
        "b7b654bb8d2809c409ce6ca24eb21d3afebf7885"
    )
    assert _install_git_fixture_object(git, article_checkout, "tree", protocol_tree_bytes) == (
        "40adba4c377757577978b539bb55932a8abaa10e"
    )
    assert _install_git_fixture_object(git, article_checkout, "commit", protocol_commit_bytes) == (
        "85404aee4dab7ade81c6893fac9f34aeaddf50dd"
    )

    batch_relative = "scripts/easley/run_pre_one_cell.sbatch"
    batch_bytes = b"#!/bin/sh\nexit 99\n"
    _git_fixture_command(git, software_checkout, "init", "--initial-branch=main")
    source_batch = _write_fixture_member(software_checkout, batch_relative, batch_bytes, mode=0o755)
    source_commit = _commit_git_fixture(git, software_checkout, "synthetic batch source")
    batch_blob = (
        _git_fixture_command(
            git,
            software_checkout,
            "rev-parse",
            f"{source_commit}:{batch_relative}",
        )
        .decode("ascii")
        .strip()
    )
    _git_fixture_command(
        git,
        software_checkout,
        "remote",
        "add",
        "origin",
        "ssh://fixture.invalid/software.git",
    )
    _git_fixture_command(
        git,
        software_checkout,
        "update-ref",
        "refs/remotes/origin/main",
        source_commit,
    )
    _git_fixture_command(git, software_checkout, "checkout", "--detach", source_commit)
    batch_script = trusted_base / "deployed" / "run_pre_one_cell.sbatch"
    batch_script.write_bytes(source_batch.read_bytes())
    batch_script.chmod(0o600)
    batch_authority = {
        "source_commit": source_commit,
        "path": batch_relative,
        "git_blob": batch_blob,
        "sha256": hashlib.sha256(batch_bytes).hexdigest(),
        "size_bytes": len(batch_bytes),
    }

    bin_root = environment_root / "bin"
    bin_root.mkdir(mode=0o700)
    bin_root.chmod(0o700)
    python_executable = _write_fixture_member(
        environment_root,
        "bin/python",
        b"#!/bin/sh\nexit 99\n",
        mode=0o755,
    )
    sbatch_executable = _write_fixture_member(
        environment_root,
        "bin/sbatch",
        b"#!/bin/sh\nexit 98\n",
        mode=0o755,
    )
    scontrol_executable = _write_fixture_member(
        environment_root,
        "bin/scontrol",
        b"#!/bin/sh\nexit 97\n",
        mode=0o755,
    )
    tool_identities = {
        "sbatch": _tool_identity(sbatch_executable, scheduler=True),
        "scontrol": _tool_identity(scontrol_executable, scheduler=True),
        "git": _tool_identity(git_path, scheduler=False, version=git_version),
    }

    private_paths = {
        "task_root": str(private_root / "tasks"),
        "attempt_root": str(private_root / "attempts"),
        "log_root": str(private_root / "logs"),
        "cache_root": str(private_root / "cache"),
        "temporary_root": str(private_root / "tmp"),
        "submission_ledger_root": str(private_root / "submission-ledger"),
        "submission_ledger_lock": str(private_root / "submission-ledger" / "ledger.lock"),
        "authorized_run_directory": str(private_root / "run"),
    }
    sidecar_bytes = os.fsencode(python_executable) + b"\n"
    runtime_python = {
        "sidecar_bytes_hex": sidecar_bytes.hex(),
        "sidecar_sha256": hashlib.sha256(sidecar_bytes).hexdigest(),
        "sidecar_size_bytes": len(sidecar_bytes),
        "executable_path": str(python_executable),
        "executable_realpath": str(python_executable),
        "executable_sha256": hashlib.sha256(python_executable.read_bytes()).hexdigest(),
        "executable_size_bytes": python_executable.stat().st_size,
    }
    scheduler_environment = {"LANG": "C", "LC_ALL": "C"}
    git_environment = dict(runner._GIT_ENVIRONMENT)
    remote_url = "ssh://fixture.invalid/coordinator.git"
    fetch_refspec = "+refs/heads/main:refs/remotes/origin/main"
    git_local_config = {
        "core_repositoryformatversion": "0",
        "core_filemode": "true",
        "core_bare": "false",
        "core_logallrefupdates": "true",
        "remote_origin_url": remote_url,
        "remote_origin_fetch": fetch_refspec,
        "branch_main_remote": "origin",
        "branch_main_merge": "refs/heads/main",
    }
    scientific_environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "TMPDIR": private_paths["temporary_root"],
        "NUMBA_CACHE_DIR": f"{private_paths['cache_root']}/numba",
        "NUMBA_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "BLIS_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "OMP_DYNAMIC": "FALSE",
        "MKL_DYNAMIC": "FALSE",
    }
    scientific_environment_template = {
        "profile": runner._SCIENTIFIC_ENV_PROFILE,
        "ordered_keys": list(runner._SCIENTIFIC_ENV_KEYS),
        "literal_bindings": {
            "LANG": "C",
            "LC_ALL": "C",
            "OMP_DYNAMIC": "FALSE",
            "MKL_DYNAMIC": "FALSE",
        },
        "path_bindings": {
            "TMPDIR": "temporary_root",
            "NUMBA_CACHE_DIR": "cache_root/numba",
        },
        "cpu_bindings": list(runner._SCIENTIFIC_ENV_KEYS[4:11]),
    }
    environment = {
        "python_implementation": "CPython",
        "python_version": "fixture",
        "numpy_version": "fixture",
        "numba_version": "fixture",
        "llvmlite_version": "fixture",
        "package_version": "fixture",
        "constraints_sha256": "c" * 64,
    }
    launch_paths = {
        "campaign_root": str(campaign_root),
        "authorization_checkout": str(coordinator_checkout),
        "authorization_directory": str(authorization_directory),
        "runtime_python_file": str(authorization_directory / "runtime-python.path"),
        "python_executable": str(python_executable),
        **private_paths,
        "batch_script": str(batch_script),
        "stdout_template": f"{private_paths['log_root']}/slurm-%A_%a.out",
        "stderr_template": f"{private_paths['log_root']}/slurm-%A_%a.err",
        "git_executable": git,
        "coordinator_remote_url": remote_url,
        "coordinator_fetch_refspec": fetch_refspec,
    }
    deployment_paths = {
        "article_checkout": str(article_checkout),
        "software_checkout": str(software_checkout),
        "coordinator_checkout": str(coordinator_checkout),
        "campaign_root": str(campaign_root),
        "environment_root": str(environment_root),
        "python_executable": str(python_executable),
        "private_task_root": private_paths["task_root"],
        "attempt_root": private_paths["attempt_root"],
        "log_root": private_paths["log_root"],
        "cache_root": private_paths["cache_root"],
        "temporary_root": private_paths["temporary_root"],
        "submission_ledger_root": private_paths["submission_ledger_root"],
        "submission_ledger_lock": private_paths["submission_ledger_lock"],
        "authorized_run_directory": private_paths["authorized_run_directory"],
        "batch_script": str(batch_script),
        "sbatch_executable": str(sbatch_executable),
        "scontrol_executable": str(scontrol_executable),
        "git_executable": git,
    }

    configuration_bytes, campaign_members = _base_fixture()
    campaign_authority = runner.load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=campaign_members,
    )
    campaign_document = json.loads(configuration_bytes)
    protocol_record = campaign_document["protocol"]
    manifest_bytes = _canonical_json({"profile": "synthetic-campaign-manifest@1"})
    wheel_bytes = b"synthetic-wheel-member\n"
    configuration_path = "campaigns/pre-one-cell-discovery-v1/campaign.json"
    manifest_path = "campaigns/pre-one-cell-discovery-v1/authority-manifest.json"
    deployment_lock_path = "campaigns/pre-one-cell-discovery-v1/deployment.lock.json"
    wheel_path = "campaigns/pre-one-cell-discovery-v1/package.whl"
    deployment_path = "authorizations/pre-one-cell-discovery-v1/deployment/certificate.json"
    admission_path = "authorizations/pre-one-cell-discovery-v1/admissions/f0-0001/admission.json"
    launch_path = "authorizations/pre-one-cell-discovery-v1/launches/f0-0001/launch.json"
    ordered_path = "authorizations/pre-one-cell-discovery-v1/launches/f0-0001/ordered-tasks.jsonl"
    protocol_authority = {
        "blob": protocol_record["protocol_blob"],
        "commit": protocol_record["article_commit"],
        "path": protocol_record["protocol_path"],
        "sha256": protocol_record["protocol_sha256"],
        "size_bytes": protocol_record["protocol_size_bytes"],
    }
    deployment_lock_bytes = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-deployment-lock@1",
            "protocol": protocol_authority,
            "source": {"commit": source_commit},
            "wheel": {
                "member_path": wheel_path,
                "sha256": hashlib.sha256(wheel_bytes).hexdigest(),
                "size_bytes": len(wheel_bytes),
            },
            "campaign": {
                "configuration_sha256": hashlib.sha256(configuration_bytes).hexdigest(),
                "authority_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            },
            "environment": environment,
            "profiles": {
                "campaign": "tetris-pre-one-cell-campaign@1",
                "scientific_identity": "tetris-pre-one-cell-scientific-identity@1",
                "array_mapping": runner._ARRAY_PROFILE,
                "runner": runner._RUNNER_PROFILE,
            },
            "batch_script": batch_authority,
        }
    )

    _git_fixture_command(git, coordinator_checkout, "init", "--initial-branch=main")
    configuration_base = Path(configuration_path).parent
    _write_fixture_member(coordinator_checkout, configuration_path, configuration_bytes)
    for member_path, member_bytes in campaign_members:
        _write_fixture_member(
            coordinator_checkout,
            str(configuration_base / member_path),
            member_bytes,
        )
    _write_fixture_member(coordinator_checkout, manifest_path, manifest_bytes)
    _write_fixture_member(coordinator_checkout, wheel_path, wheel_bytes)
    _write_fixture_member(coordinator_checkout, deployment_lock_path, deployment_lock_bytes)
    campaign_commit = _commit_git_fixture(git, coordinator_checkout, "synthetic campaign closure")

    deployment_lock_reference = _file_reference(
        campaign_commit,
        deployment_lock_path,
        deployment_lock_bytes,
    )
    deployment_bytes = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-deployment-certificate@1",
            "protocol": protocol_authority,
            "source_commit": source_commit,
            "wheel": _file_reference(campaign_commit, wheel_path, wheel_bytes),
            "campaign": {
                "commit": campaign_commit,
                "configuration": _file_reference(campaign_commit, configuration_path, configuration_bytes),
                "manifest": _file_reference(campaign_commit, manifest_path, manifest_bytes),
                "deployment_lock": deployment_lock_reference,
            },
            "batch_script": batch_authority,
            "environment": environment,
            "runtime_python": {
                "sidecar_name": "runtime-python.path",
                **runtime_python,
            },
            "scientific_environment": scientific_environment_template,
            "scheduler_environment": scheduler_environment,
            "git_environment": git_environment,
            "git_local_config": git_local_config,
            "tool_identities": tool_identities,
            "coordinator_repository": {
                "repository_id": "synthetic-coordinator",
                "remote_url": remote_url,
                "fetch_refspec": fetch_refspec,
                "branch": "main",
                "authorization_readback_root": str(readback_root),
            },
            "paths": deployment_paths,
            "mapping_profile": runner._ARRAY_PROFILE,
            "ownership": {
                "campaign_user": "synthetic-user",
                "campaign_uid": os.geteuid(),
                "trusted_base": str(trusted_base),
                "trusted_administrator_uids": [git_info.st_uid],
                "campaign_root_mode": "0700",
                "authorization_readback_root_mode": "0700",
                "environment_root_mode": "0700",
                "private_task_root_mode": "0700",
                "attempt_root_mode": "0700",
                "log_root_mode": "0700",
                "cache_root_mode": "0700",
                "temporary_root_mode": "0700",
                "no_symlink_ancestors": True,
                "user_owned_mutable_roots": True,
            },
            "capacity": {
                "quota_bytes": None,
                "free_bytes": 1,
                "free_inodes": 1,
                "private_state_envelope_bytes": 1,
                "final_output_envelope_bytes": 1,
            },
            "certification": {
                "checks": {
                    "git_authority": True,
                    "protocol": True,
                    "campaign_members": True,
                    "wheel_install": True,
                    "runtime_identity": True,
                    "path_safety": True,
                    "capacity": True,
                    "exhaustive_mapping": True,
                    "no_launch": True,
                },
                "exhaustive_map_sha256": "e" * 64,
                "no_launch_authority": True,
                "zero_scientific_tasks": 0,
                "zero_campaign_finals": 0,
                "zero_submissions": 0,
                "zero_requeues": 0,
            },
        }
    )
    _write_fixture_member(coordinator_checkout, deployment_path, deployment_bytes)
    deployment_commit = _commit_git_fixture(git, coordinator_checkout, "synthetic deployment certificate")
    deployment_reference = _file_reference(deployment_commit, deployment_path, deployment_bytes)

    common_authorities = {
        "protocol_commit": protocol_authority["commit"],
        "protocol_sha256": protocol_authority["sha256"],
        "source_commit": source_commit,
        "wheel_sha256": hashlib.sha256(wheel_bytes).hexdigest(),
        "campaign_commit": campaign_commit,
        "configuration_sha256": hashlib.sha256(configuration_bytes).hexdigest(),
    }
    admission_bytes = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-admission-fixture@1",
            "authorities": {
                **common_authorities,
                "deployment_lock": deployment_lock_reference,
                "deployment": deployment_reference,
                "branch": None,
            },
            "lane": {
                "lane_id": "f0",
                "wave": "f0",
                "role": "excluded-forensic-canary",
                "task_map_id": "f0",
                "task_count": 8,
            },
            "decision": "admitted",
            "evidence": {
                "f0_completion": None,
                "initial_p0_completion": None,
                "branch_decision": None,
                "confirmation_completion": None,
                "b2_precision_audit": None,
                "b2_resource_admission": None,
                "clean_resource_admission": None,
            },
            "user_approval": {
                "actor": "synthetic-reviewer",
                "approved_at_utc": "2026-07-16T00:00:00Z",
                "scope": "f0",
            },
            "fixture": _FIXTURE_METADATA,
        }
    )
    _write_fixture_member(coordinator_checkout, admission_path, admission_bytes)
    admission_commit = _commit_git_fixture(git, coordinator_checkout, "synthetic fixture admission")
    admission_reference = _file_reference(admission_commit, admission_path, admission_bytes)

    ordered_rows: list[bytes] = []
    for array_position in range(8):
        identity = runner.explain_one_cell_campaign_task(
            campaign=campaign_authority,
            task_map_id="f0",
            task_index=array_position,
            deployment_lock_sha256=hashlib.sha256(deployment_lock_bytes).hexdigest(),
            software_commit=source_commit,
            wheel_sha256=hashlib.sha256(wheel_bytes).hexdigest(),
            branch_decision_sha256=None,
        )
        identity_digest = hashlib.sha256(identity).hexdigest()
        ordered_rows.append(
            _canonical_json(
                {
                    "profile": "tetris-pre-one-cell-launch-task@1",
                    "array_position": array_position,
                    "wave": "f0",
                    "role": "excluded-forensic-canary",
                    "task_map_id": "f0",
                    "scientific_index": array_position,
                    "scientific_identity_hex": identity.hex(),
                    "scientific_identity_sha256": identity_digest,
                    "scientific_identity_size_bytes": len(identity),
                    "relative_task_directory": f"f0/{array_position:020d}-{identity_digest}",
                }
            )
        )
    ordered_bytes = b"".join(ordered_rows)
    launch_bytes = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-launch-fixture@1",
            "launch_id": "synthetic-f0-0001",
            "lane": "f0",
            "self_path": launch_path,
            "authorities": {
                **common_authorities,
                "campaign_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "deployment_lock": deployment_lock_reference,
                "deployment": deployment_reference,
                "admission": admission_reference,
                "branch": None,
            },
            "ordered_tasks": {
                "profile": "tetris-pre-one-cell-ordered-tasks@1",
                "path": ordered_path,
                "sha256": hashlib.sha256(ordered_bytes).hexdigest(),
                "size_bytes": len(ordered_bytes),
                "task_count": 8,
            },
            "mapping": {
                "profile": runner._ARRAY_PROFILE,
                "array_first": 0,
                "array_last": 7,
                "array_step": 1,
            },
            "batch_script": batch_authority,
            "resources": {
                "profile": "tetris-pre-one-cell-slurm-resource-envelope@1",
                "partition": "compute",
                "wall_minutes": 17,
                "cpus_per_task": 1,
                "memory_mib": 1,
                "array_concurrency": 1,
                "signal_name": "SIGUSR1",
                "signal_warning_seconds": 900,
                "receipt_handshake_seconds": 60,
                "scheduler_timeout_seconds": 30,
                "max_requeues_per_task": 0,
                "sbatch_executable": str(sbatch_executable),
                "scontrol_executable": str(scontrol_executable),
                "scheduler_environment": scheduler_environment,
                "scientific_environment": scientific_environment,
            },
            "runtime_python": {
                "sidecar_path": str(authorization_directory / "runtime-python.path"),
                **runtime_python,
            },
            "git_environment": git_environment,
            "git_local_config": git_local_config,
            "tool_identities": tool_identities,
            "paths": launch_paths,
            "user_approval": {
                "actor": "synthetic-reviewer",
                "approved_at_utc": "2026-07-16T00:00:00Z",
                "scope": "f0",
            },
            "fixture": _FIXTURE_METADATA,
        }
    )
    _write_fixture_member(coordinator_checkout, launch_path, launch_bytes)
    _write_fixture_member(coordinator_checkout, ordered_path, ordered_bytes)
    launch_commit = _commit_git_fixture(git, coordinator_checkout, "synthetic fixture launch")

    _git_fixture_command(git, coordinator_checkout, "remote", "add", "origin", remote_url)
    _git_fixture_command(
        git,
        coordinator_checkout,
        "config",
        "--replace-all",
        "remote.origin.fetch",
        fetch_refspec,
    )
    _git_fixture_command(git, coordinator_checkout, "config", "branch.main.remote", "origin")
    _git_fixture_command(
        git,
        coordinator_checkout,
        "config",
        "branch.main.merge",
        "refs/heads/main",
    )
    _git_fixture_command(
        git,
        coordinator_checkout,
        "update-ref",
        "refs/remotes/origin/main",
        launch_commit,
    )
    _git_fixture_command(git, coordinator_checkout, "checkout", "--detach", launch_commit)

    readback_bytes = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-authority-readback@1",
            "repository": {
                "repository_id": "synthetic-coordinator",
                "remote_url": remote_url,
                "fetch_refspec": fetch_refspec,
                "branch": "main",
            },
            "launch": _file_reference(launch_commit, launch_path, launch_bytes),
            "observation": {
                "checkout_root": str(coordinator_checkout),
                "head_commit": launch_commit,
                "origin_main_commit": launch_commit,
                "detached": True,
                "clean": True,
                "observed_at_utc": "2026-07-16T00:00:00Z",
            },
        }
    )
    runtime_launch = authorization_directory / "launch.json"
    runtime_ordered = authorization_directory / "ordered-tasks.jsonl"
    runtime_readback = authorization_directory / "readback.json"
    runtime_sidecar = authorization_directory / "runtime-python.path"
    for path, payload in (
        (runtime_launch, launch_bytes),
        (runtime_ordered, ordered_bytes),
        (runtime_readback, readback_bytes),
        (runtime_sidecar, sidecar_bytes),
    ):
        path.write_bytes(payload)
        path.chmod(0o600)
    return authorization_directory, runtime_ordered, article_checkout


def test_exact_launch_fixture_parses_for_inspection_but_unknown_suffix_fails() -> None:
    parsed = runner._parse_launch_wire(
        _fixture_launch_bytes(
            profile="tetris-pre-one-cell-launch-fixture@1",
        )
    )
    assert parsed["profile"] == "tetris-pre-one-cell-launch-fixture@1"
    assert parsed["_fixture"] == _FIXTURE_METADATA

    for profile, fixture in (
        ("attacker-fixture@1", _FIXTURE_METADATA),
        (
            "tetris-pre-one-cell-launch-fixture@1",
            {**_FIXTURE_METADATA, "scientific_execution_permitted": True},
        ),
        (
            "tetris-pre-one-cell-launch-fixture@1",
            {**_FIXTURE_METADATA, "unknown": False},
        ),
    ):
        with pytest.raises(runner.OneCellRunnerValidationError):
            runner._parse_launch_wire(_fixture_launch_bytes(profile=profile, fixture=fixture))


def test_public_loader_authenticates_complete_temp_git_fixture_and_refuses_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorization_directory, runtime_ordered, article_checkout = _build_public_loader_fixture(tmp_path)
    validate_checkout = runner._validate_pushed_detached_checkout

    def validate_fixture_checkout(
        paths: runner.OneCellRunnerPaths,
        *,
        checkout: str,
        commit: str,
        label: str,
        allow_origin_descendant: bool = False,
    ) -> None:
        if label == "Article checkout":
            assert checkout == str(article_checkout)
            assert commit == "85404aee4dab7ade81c6893fac9f34aeaddf50dd"
            assert allow_origin_descendant is True
            return
        validate_checkout(
            paths,
            checkout=checkout,
            commit=commit,
            label=label,
            allow_origin_descendant=allow_origin_descendant,
        )

    monkeypatch.setattr(runner, "_validate_pushed_detached_checkout", validate_fixture_checkout)
    validate_ancestor = runner._require_git_ancestor

    def validate_fixture_ancestor(
        paths: runner.OneCellRunnerPaths,
        *,
        prerequisite: str,
        trusted_commit: str,
        checkout: str | None = None,
    ) -> None:
        if prerequisite in {
            runner._SLICE_8B_SOFTWARE_PARENT,
            runner._SLICE_8B_COORDINATOR_AUTHORITY,
        }:
            assert re.fullmatch(r"[0-9a-f]{40}", trusted_commit) is not None
            return
        validate_ancestor(
            paths,
            prerequisite=prerequisite,
            trusted_commit=trusted_commit,
            checkout=checkout,
        )

    monkeypatch.setattr(runner, "_require_git_ancestor", validate_fixture_ancestor)

    loaded = runner.load_one_cell_launch_authority(
        authorization_path=str(authorization_directory),
    )
    assert loaded.profile == "tetris-pre-one-cell-launch-fixture@1"
    assert runner._parse_admission(loaded.admission_bytes)["profile"] == "tetris-pre-one-cell-admission-fixture@1"
    assert runner._parse_deployment(loaded.deployment_certificate_bytes)["profile"] == (
        "tetris-pre-one-cell-deployment-certificate@1"
    )
    assert len(runner.list_one_cell_launch_tasks(launch=loaded)) == 8
    assert (
        runner.explain_one_cell_launch_task(launch=loaded, array_position=0)
        == loaded.ordered_tasks[0].scientific_identity_bytes
    )
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as refused:
        runner.submit_one_cell_launch(launch=loaded)
    assert refused.value.exit_code == 77

    runtime_ordered.write_bytes(runtime_ordered.read_bytes() + b"tamper")
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as tampered:
        runner.load_one_cell_launch_authority(
            authorization_path=str(authorization_directory),
        )
    assert tampered.value.exit_code == 76


@pytest.mark.parametrize("record_class", ("receipt", "result"))
@pytest.mark.parametrize("limit_name", ("PC_NAME_MAX", "PC_PATH_MAX"))
def test_loader_preflights_all_link_publication_shapes_before_git(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_class: str,
    limit_name: str,
) -> None:
    authorization_directory, _runtime_ordered, _article_checkout = _build_public_loader_fixture(tmp_path)
    launch_digest = hashlib.sha256((authorization_directory / "launch.json").read_bytes()).hexdigest()
    ledger_root = tmp_path / "trusted" / "campaign" / "private" / "submission-ledger"
    if record_class == "receipt":
        parent = ledger_root / "receipts"
        record_name = f"{launch_digest}.json"
    else:
        parent = ledger_root / "requeue-results"
        record_name = f"{launch_digest}-p{1799:020d}-r{16:020d}-to-{16:020d}.json"
    temporary_name = f".{record_name}.{'0' * 32}.tmp"
    if limit_name == "PC_NAME_MAX":
        selected_limit = len(os.fsencode(record_name)) + 1
        assert len(os.fsencode(temporary_name)) > selected_limit
    else:
        selected_limit = len(os.fsencode(parent / record_name)) + 1
        assert len(os.fsencode(parent / temporary_name)) > selected_limit
    parent_identity = (parent.stat().st_dev, parent.stat().st_ino)
    real_fpathconf = runner.os.fpathconf
    targeted_calls = 0
    git_effects = 0

    def bounded(descriptor: int, name: str) -> int:
        nonlocal targeted_calls
        info = os.fstat(descriptor)
        if (info.st_dev, info.st_ino) == parent_identity and name == limit_name:
            targeted_calls += 1
            return selected_limit
        return real_fpathconf(descriptor, name)

    def unexpected_git(*args: object, **kwargs: object) -> typing.NoReturn:
        nonlocal git_effects
        del args, kwargs
        git_effects += 1
        raise AssertionError("generated path preflight reached Git execution")

    monkeypatch.setattr(runner.os, "fpathconf", bounded)
    monkeypatch.setattr(runner, "_run_bounded_process", unexpected_git)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner.load_one_cell_launch_authority(authorization_path=str(authorization_directory))
    assert caught.value.exit_code == 76
    assert targeted_calls >= 1
    assert git_effects == 0


def test_admission_lane_uses_its_frozen_slice8a_map_and_count() -> None:
    valid = runner._parse_admission(_admission_bytes())
    assert valid["lane"] == {
        "lane_id": "f0",
        "wave": "f0",
        "role": "excluded-forensic-canary",
        "task_map_id": "f0",
        "task_count": 8,
    }
    for changes in (
        {"task_map_id": "b1"},
        {"task_count": 384},
    ):
        with pytest.raises(runner.OneCellRunnerValidationError):
            runner._parse_admission(_admission_bytes(**changes))


def test_admission_evidence_routes_to_semantic_validators_with_trusted_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _runner_paths(tmp_path)
    trusted_commit = "1" * 40
    f0_reference = {"kind": "f0"}
    precision_reference = {"kind": "precision"}
    b2_resource_reference = {"kind": "b2-resource"}
    admission = {
        "lane": {"lane_id": "b2"},
        "evidence": {
            "f0_completion": f0_reference,
            "initial_p0_completion": None,
            "branch_decision": None,
            "confirmation_completion": None,
            "b2_precision_audit": precision_reference,
            "b2_resource_admission": b2_resource_reference,
            "clean_resource_admission": None,
        },
    }
    launch_authorities = {"authority": "sentinel"}
    calls: list[tuple[object, ...]] = []

    def completion(
        selected_paths: runner.OneCellRunnerPaths,
        reference: object,
        *,
        expected_lane: str,
        launch_authorities: object,
        trusted_commit: str,
    ) -> dict[str, object]:
        calls.append(
            (
                "completion",
                selected_paths,
                reference,
                expected_lane,
                launch_authorities,
                trusted_commit,
            )
        )
        return {}

    def precision(
        selected_paths: runner.OneCellRunnerPaths,
        reference: object,
        *,
        launch_authorities: object,
        trusted_commit: str,
    ) -> dict[str, object]:
        calls.append(
            (
                "precision",
                selected_paths,
                reference,
                launch_authorities,
                trusted_commit,
            )
        )
        return {}

    def resource(
        selected_paths: runner.OneCellRunnerPaths,
        reference: object,
        *,
        expected_scope: str,
        launch_authorities: object,
        trusted_commit: str,
    ) -> dict[str, object]:
        calls.append(
            (
                "resource",
                selected_paths,
                reference,
                expected_scope,
                launch_authorities,
                trusted_commit,
            )
        )
        return {}

    monkeypatch.setattr(runner, "_validate_completion_evidence", completion)
    monkeypatch.setattr(runner, "_validate_precision_evidence", precision)
    monkeypatch.setattr(runner, "_validate_resource_evidence", resource)
    runner._validate_admission_evidence(
        paths,
        admission=admission,
        configured_branch=None,
        launch_authorities=launch_authorities,
        trusted_commit=trusted_commit,
    )
    assert calls == [
        (
            "completion",
            paths,
            f0_reference,
            "f0",
            launch_authorities,
            trusted_commit,
        ),
        (
            "precision",
            paths,
            precision_reference,
            launch_authorities,
            trusted_commit,
        ),
        (
            "resource",
            paths,
            b2_resource_reference,
            "b2",
            launch_authorities,
            trusted_commit,
        ),
    ]


def test_evidence_authorities_must_join_launch_byte_for_byte() -> None:
    deployment_reference = {
        "commit": "1" * 40,
        "path": "authorizations/pre-one-cell-discovery-v1/deployment/certificate.json",
        "sha256": "2" * 64,
        "size_bytes": 1,
    }
    launch_authorities = {
        "protocol_commit": "3" * 40,
        "protocol_sha256": "4" * 64,
        "source_commit": "5" * 40,
        "wheel_sha256": "6" * 64,
        "campaign_commit": "7" * 40,
        "deployment": deployment_reference,
    }
    evidence_authorities = dict(launch_authorities)
    assert (
        runner._validate_common_evidence_authorities(
            evidence_authorities,
            launch_authorities=launch_authorities,
            label="synthetic evidence authorities",
        )
        == evidence_authorities
    )

    evidence_authorities["source_commit"] = "8" * 40
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_common_evidence_authorities(
            evidence_authorities,
            launch_authorities=launch_authorities,
            label="synthetic evidence authorities",
        )
    assert caught.value.exit_code == 76


def _branch_decision_bytes(
    *,
    rule_profile: str = "tetris-pre-one-cell-horizon-branch@1",
    rule_input_sha256: str = "a" * 64,
) -> bytes:
    def reference(path: str, *, digest: str = "a" * 64) -> dict[str, object]:
        return {
            "commit": "1" * 40,
            "path": path,
            "sha256": digest,
            "size_bytes": 1,
        }

    deployment = reference("authorizations/pre-one-cell-discovery-v1/deployment/certificate.json")
    final_manifests = reference(
        "authorizations/pre-one-cell-discovery-v1/completions/p0-initial-0001/final-manifests.jsonl"
    )
    return _canonical_json(
        {
            "profile": "tetris-pre-one-cell-branch-decision@1",
            "authorities": {
                "protocol_commit": "2" * 40,
                "protocol_sha256": "3" * 64,
                "source_commit": "4" * 40,
                "wheel_sha256": "5" * 64,
                "campaign_commit": "6" * 40,
                "deployment": deployment,
            },
            "initial_p0": {
                "completion": reference(
                    "authorizations/pre-one-cell-discovery-v1/completions/p0-initial-0001/completion.json"
                ),
                "launch": reference("authorizations/pre-one-cell-discovery-v1/launches/p0-initial-0001/launch.json"),
                "task_count": 48,
                "ordered_tasks_sha256": "7" * 64,
                "final_manifests": final_manifests,
            },
            "rule": {
                "profile": rule_profile,
                "input_sha256": rule_input_sha256,
                "l_star": None,
                "confirmation_required": False,
            },
            "selection": {
                "branch_id": "p1-no-l-star",
                "p1_task_map_id": "p1-no-l-star",
                "p1_task_map_sha256": "8" * 64,
                "confirmation_task_map_id": None,
            },
        }
    )


def test_branch_rule_profile_and_input_bind_frozen_horizon_and_pilot_index() -> None:
    parsed = runner._parse_branch(_branch_decision_bytes())
    assert parsed["rule"] == {
        "profile": "tetris-pre-one-cell-horizon-branch@1",
        "input_sha256": "a" * 64,
        "l_star": None,
        "confirmation_required": False,
    }

    with pytest.raises(runner.OneCellRunnerValidationError):
        runner._parse_branch(
            _branch_decision_bytes(
                rule_profile="tetris-pre-one-cell-horizon-branch-rule@1",
            )
        )
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as input_mismatch:
        runner._parse_branch(_branch_decision_bytes(rule_input_sha256="b" * 64))
    assert input_mismatch.value.exit_code == 76


def test_branch_p1_map_digest_must_join_the_frozen_campaign_map() -> None:
    from tests.test_one_cell_campaign import _base_fixture

    configuration_bytes, members = _base_fixture()
    campaign = runner.load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    task_map = next(item for item in campaign.task_maps if item.task_map_id == "p1-no-l-star")
    horizon = next(item for item in campaign.horizon_branches if item.branch_id == "p1-no-l-star")
    branch = {
        "selection": {
            "branch_id": "p1-no-l-star",
            "p1_task_map_id": "p1-no-l-star",
            "p1_task_map_sha256": task_map.sha256,
        },
        "rule": {
            "profile": horizon.profile,
            "l_star": horizon.l_star,
            "confirmation_required": horizon.confirmation_required,
        },
    }
    runner._validate_branch_campaign_join(branch, campaign=campaign)

    branch["selection"] = {
        **branch["selection"],
        "p1_task_map_sha256": "f" * 64,
    }
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_branch_campaign_join(branch, campaign=campaign)
    assert caught.value.exit_code == 76


@pytest.mark.parametrize("substitution", ("source", "branch"))
def test_completed_launch_refuses_source_or_branch_substitution(substitution: str) -> None:
    def reference(path: str) -> dict[str, object]:
        return {
            "commit": "1" * 40,
            "path": path,
            "sha256": "2" * 64,
            "size_bytes": 1,
        }

    launch_path = "authorizations/pre-one-cell-discovery-v1/launches/p0-initial-0001/launch.json"
    launch_reference = reference(launch_path)
    launch_authorities = {
        "protocol_commit": "3" * 40,
        "protocol_sha256": "4" * 64,
        "source_commit": "5" * 40,
        "wheel_sha256": "6" * 64,
        "campaign_commit": "7" * 40,
        "deployment": reference("authorizations/pre-one-cell-discovery-v1/deployment/certificate.json"),
        "deployment_lock": reference("campaigns/pre-one-cell-discovery-v1/deployment.lock.json"),
        "campaign_manifest_sha256": "8" * 64,
        "configuration_sha256": "9" * 64,
        "admission": reference("authorizations/pre-one-cell-discovery-v1/admissions/p0-initial-0001/admission.json"),
        "branch": None,
    }
    completion_authorities = {
        key: launch_authorities[key]
        for key in (
            "protocol_commit",
            "protocol_sha256",
            "source_commit",
            "wheel_sha256",
            "campaign_commit",
            "deployment",
        )
    }
    completed_authorities = dict(launch_authorities)
    if substitution == "source":
        completed_authorities["source_commit"] = "a" * 40
    else:
        completed_authorities["branch"] = reference(
            "authorizations/pre-one-cell-discovery-v1/branches/p1-no-l-star/decision.json"
        )
    completed_launch = {
        "self_path": launch_path,
        "authorities": completed_authorities,
    }

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_completed_launch_authorities(
            completed_launch,
            completed_launch_ref=launch_reference,
            completion_authorities=completion_authorities,
            launch_authorities=launch_authorities,
            expected_lane="p0-initial",
        )
    assert caught.value.exit_code == 76


def test_branch_evidence_is_fetched_with_reachability_and_joins_initial_p0(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _runner_paths(tmp_path)
    trusted_commit = "1" * 40
    digest = "2" * 64

    def file_ref(path: str) -> dict[str, object]:
        return {
            "commit": "3" * 40,
            "path": path,
            "sha256": digest,
            "size_bytes": 1,
        }

    branch_reference = file_ref("authorizations/pre-one-cell-discovery-v1/branches/p1-no-l-star/decision.json")
    completion_reference = file_ref(
        "authorizations/pre-one-cell-discovery-v1/completions/p0-initial-0001/completion.json"
    )
    launch_reference = file_ref("authorizations/pre-one-cell-discovery-v1/launches/p0-initial-0001/launch.json")
    final_reference = file_ref(
        "authorizations/pre-one-cell-discovery-v1/completions/p0-initial-0001/final-manifests.jsonl"
    )
    branch = {
        "authorities": {},
        "selection": {"branch_id": "p1-no-l-star"},
        "initial_p0": {
            "completion": completion_reference,
            "launch": launch_reference,
            "task_count": 48,
            "ordered_tasks_sha256": digest,
            "final_manifests": final_reference,
        },
        "rule": {"confirmation_required": False},
    }
    admission = {
        "authorities": {"branch": branch_reference},
        "lane": {"lane_id": "p0-confirmation"},
        "evidence": {
            "f0_completion": None,
            "initial_p0_completion": None,
            "branch_decision": branch_reference,
            "confirmation_completion": None,
            "b2_precision_audit": None,
            "b2_resource_admission": None,
            "clean_resource_admission": None,
        },
    }
    fetches: list[tuple[object, str]] = []

    def git_blob(
        selected_paths: runner.OneCellRunnerPaths,
        reference: object,
        *,
        maximum: int,
        trusted_commit: str,
    ) -> bytes:
        del maximum
        assert selected_paths == paths
        fetches.append((reference, trusted_commit))
        return b"branch-bytes\n"

    monkeypatch.setattr(runner, "_git_blob", git_blob)
    monkeypatch.setattr(runner, "_parse_branch", lambda payload: branch)
    monkeypatch.setattr(runner, "_validate_common_evidence_authorities", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        runner,
        "_validate_completion_evidence",
        lambda *args, **kwargs: {
            "launch": launch_reference,
            "task_count": 48,
            "ordered_tasks_sha256": digest,
            "final_manifests": final_reference,
        },
    )
    runner._validate_admission_evidence(
        paths,
        admission=admission,
        configured_branch=None,
        launch_authorities={},
        trusted_commit=trusted_commit,
    )
    assert fetches == [(branch_reference, trusted_commit)]


@pytest.mark.parametrize(
    ("launch_profile", "admission_profile"),
    (
        (
            "tetris-pre-one-cell-launch@1",
            "tetris-pre-one-cell-admission-fixture@1",
        ),
        (
            "tetris-pre-one-cell-launch-fixture@1",
            "tetris-pre-one-cell-admission@1",
        ),
    ),
)
def test_production_and_fixture_authorities_cannot_be_composed(
    launch_profile: str,
    admission_profile: str,
) -> None:
    launch: dict[str, object] = {"profile": launch_profile, "_fixture": None}
    admission: dict[str, object] = {
        "profile": admission_profile,
        "_fixture": (_FIXTURE_METADATA if admission_profile.endswith("-fixture@1") else None),
    }
    if launch_profile.endswith("-fixture@1"):
        launch["_fixture"] = _FIXTURE_METADATA
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_authority_joins(
            launch=launch,
            deployment_lock={},
            deployment={},
            admission=admission,
            branch=None,
        )
    assert caught.value.exit_code == 76


def test_only_launch_and_admission_have_persisted_fixture_profiles() -> None:
    profiles = {
        value for name, value in vars(runner).items() if name.endswith("_FIXTURE_PROFILE") and type(value) is str
    }
    assert profiles == {
        "tetris-pre-one-cell-launch-fixture@1",
        "tetris-pre-one-cell-admission-fixture@1",
    }
    assert "_FIXTURE_SUFFIX" not in vars(runner)


def test_fixture_authority_is_inspectable_but_submission_is_effect_free_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "inert-fixture-authority"
    before = tuple(tmp_path.rglob("*"))
    launch = runner._fixture_launch_authority_for_test(directory=str(directory))
    assert tuple(tmp_path.rglob("*")) == before

    monkeypatch.setattr(
        runner,
        "_load_one_cell_launch_authority_impl",
        lambda *, authorization_path: launch,
    )
    loaded = runner.load_one_cell_launch_authority(
        authorization_path=str(directory),
    )
    tasks = runner.list_one_cell_launch_tasks(launch=loaded)
    assert len(tasks) == 1
    assert (
        runner.explain_one_cell_launch_task(
            launch=loaded,
            array_position=0,
        )
        == tasks[0].scientific_identity_bytes
    )
    assert tuple(tmp_path.rglob("*")) == before

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner.submit_one_cell_launch(launch=loaded)
    assert caught.value.exit_code == 77
    assert tuple(tmp_path.rglob("*")) == before


def test_fixture_authorize_and_run_refuse_before_every_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "fixture-runtime"
    launch = runner._fixture_launch_authority_for_test(directory=str(directory))
    authorization = runner._fixture_authorized_task_for_test(directory=str(directory))
    before = tuple(tmp_path.rglob("*"))

    monkeypatch.setattr(runner, "_parse_submission_claim", lambda *args, **kwargs: _unexpected_effect())
    monkeypatch.setattr(runner, "_load_submission_handshake_for_cli", lambda **kwargs: _unexpected_effect())
    monkeypatch.setattr(runner.signal, "pthread_sigmask", lambda *args, **kwargs: _unexpected_effect())

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as authorize_error:
        runner.authorize_one_cell_slurm_task(
            launch=launch,
            submission_claim_bytes=b"not-a-claim",
            submission_receipt_bytes=b"not-a-receipt",
        )
    assert authorize_error.value.exit_code == 77

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as run_error:
        runner.run_one_cell_authorized_task(authorization=authorization)
    assert run_error.value.exit_code == 77
    assert tuple(tmp_path.rglob("*")) == before


def test_authorized_attempt_path_is_exact_before_any_execution_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "authority"
    launch = runner._production_shaped_launch_for_test(directory=str(base))
    authorization = dataclasses.replace(
        runner._fixture_authorized_task_for_test(directory=str(base)),
        launch=launch,
    )
    malformed = dataclasses.replace(authorization)
    object.__setattr__(
        malformed,
        "attempt_directory",
        str(Path(launch.paths.attempt_root) / "evil"),
    )
    before = tuple(tmp_path.rglob("*"))
    monkeypatch.setattr(
        runner.signal,
        "pthread_sigmask",
        lambda operation, mask: frozenset({signal.SIGUSR1}),
    )
    monkeypatch.setattr(
        runner,
        "_load_submission_handshake_for_cli",
        lambda **kwargs: _unexpected_effect(),
    )
    monkeypatch.setattr(
        runner,
        "_ensure_private_relative_directory",
        lambda *args, **kwargs: _unexpected_effect(),
    )

    with pytest.raises(ValueError, match="exact authorized attempt path"):
        runner.run_one_cell_authorized_task(authorization=malformed)
    assert tuple(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("effect", ("submit", "authorize"))
def test_effect_entries_rebind_every_public_launch_projection_before_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    effect: str,
) -> None:
    canonical = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    changed_resources = dataclasses.replace(
        canonical.resources,
        memory_mib=canonical.resources.memory_mib + 1,
    )
    stale = dataclasses.replace(canonical, resources=changed_resources)
    monkeypatch.setattr(
        runner,
        "_load_one_cell_launch_authority_impl",
        lambda *, authorization_path: canonical,
    )
    monkeypatch.setattr(runner, "_open_ledger", lambda *args, **kwargs: _unexpected_effect())
    monkeypatch.setattr(runner, "_run_bounded_process", lambda *args, **kwargs: _unexpected_effect())
    monkeypatch.setattr(runner, "_parse_submission_claim", lambda *args, **kwargs: _unexpected_effect())

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        if effect == "submit":
            runner.submit_one_cell_launch(launch=stale)
        else:
            runner.authorize_one_cell_slurm_task(
                launch=stale,
                submission_claim_bytes=b"synthetic-claim\n",
                submission_receipt_bytes=b"synthetic-receipt\n",
            )
    assert caught.value.exit_code == 76


def _unexpected_effect() -> typing.NoReturn:
    raise AssertionError("fixture refusal reached a forbidden effect")


def _slurm_environment_for_authorization(
    authorization: runner.OneCellAuthorizedTask,
) -> dict[str, str]:
    launch = authorization.launch
    return {
        "SLURM_ARRAY_JOB_ID": authorization.slurm_array_job_id,
        "SLURM_ARRAY_TASK_ID": authorization.slurm_array_task_id,
        "SLURM_ARRAY_TASK_MIN": "0",
        "SLURM_ARRAY_TASK_MAX": str(len(launch.ordered_tasks) - 1),
        "SLURM_ARRAY_TASK_COUNT": str(len(launch.ordered_tasks)),
        "SLURM_ARRAY_TASK_STEP": "1",
        "SLURM_JOB_ID": authorization.slurm_job_id,
        "SLURM_JOB_PARTITION": launch.resources.partition,
        "SLURM_CPUS_PER_TASK": str(launch.resources.cpus_per_task),
        "SLURM_MEM_PER_NODE": str(launch.resources.memory_mib),
        "SLURM_RESTART_COUNT": str(authorization.restart_count),
    }


def _set_slurm_environment(
    monkeypatch: pytest.MonkeyPatch,
    values: dict[str, str],
) -> None:
    for key in tuple(os.environ):
        if key.startswith("SLURM_"):
            monkeypatch.delenv(key)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("TMPDIR", "/outside/uncertified-tmp"),
        ("NUMBA_CACHE_DIR", "/outside/uncertified-numba-cache"),
    ),
)
def test_scientific_write_paths_must_join_certified_runner_paths(
    tmp_path: Path,
    key: str,
    value: str,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    environment = tuple(
        (environment_key, value if environment_key == key else environment_value)
        for environment_key, environment_value in launch.resources.scientific_environment
    )
    rebound_resources = dataclasses.replace(
        launch.resources,
        scientific_environment=environment,
    )
    with pytest.raises(ValueError):
        dataclasses.replace(launch, resources=rebound_resources)


def test_lifecycle_missing_execute_route_mask_makes_zero_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "authority"
    launch = runner._production_shaped_launch_for_test(directory=str(base))
    fixture_authorization = runner._fixture_authorized_task_for_test(directory=str(base))
    claim_bytes = b"synthetic-claim\n"
    receipt_bytes = b"synthetic-receipt\n"
    authorization = dataclasses.replace(
        fixture_authorization,
        launch=launch,
        submission_claim_sha256=hashlib.sha256(claim_bytes).hexdigest(),
        submission_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
    )
    for path in (
        Path(launch.paths.task_root),
        Path(launch.paths.attempt_root),
        Path(launch.paths.temporary_root),
        Path(launch.paths.cache_root),
        Path(launch.paths.cache_root) / "numba",
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    task_before = tuple(Path(launch.paths.task_root).rglob("*"))
    attempt_before = tuple(Path(launch.paths.attempt_root).rglob("*"))

    monkeypatch.setattr(
        runner,
        "_load_submission_handshake_for_cli",
        lambda *, launch: (claim_bytes, receipt_bytes),
    )
    monkeypatch.setattr(
        runner,
        "decode_one_cell_campaign_task",
        lambda **kwargs: types.SimpleNamespace(
            root_seed=0,
            boundary_law="periodic-v1",
            width=3,
            threshold_schedule=(0, 1),
            terminal_event_count=769,
        ),
    )
    monkeypatch.setattr(
        runner,
        "explain_one_cell_campaign_task",
        lambda **kwargs: authorization.scientific_identity_bytes,
    )
    monkeypatch.setattr(
        runner.signal,
        "pthread_sigmask",
        lambda operation, mask: frozenset(),
    )

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner.run_one_cell_authorized_task(authorization=authorization)
    assert caught.value.exit_code == 78
    assert tuple(Path(launch.paths.task_root).rglob("*")) == task_before
    assert tuple(Path(launch.paths.attempt_root).rglob("*")) == attempt_before


@pytest.mark.parametrize(
    ("slurm_array_task_id", "expected_exit_code"),
    (("1", 76), (None, 78)),
)
def test_lifecycle_revalidates_live_slurm_mapping_before_path_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    slurm_array_task_id: str | None,
    expected_exit_code: int,
) -> None:
    base = tmp_path / "authority"
    launch = runner._production_shaped_launch_for_test(directory=str(base))
    fixture_authorization = runner._fixture_authorized_task_for_test(directory=str(base))
    claim_bytes = b"synthetic-claim\n"
    receipt_bytes = b"synthetic-receipt\n"
    authorization = dataclasses.replace(
        fixture_authorization,
        launch=launch,
        submission_claim_sha256=hashlib.sha256(claim_bytes).hexdigest(),
        submission_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
    )
    for path in (
        Path(launch.paths.temporary_root),
        Path(launch.paths.cache_root),
        Path(launch.paths.cache_root) / "numba",
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    stale_environment = _slurm_environment_for_authorization(authorization)
    if slurm_array_task_id is None:
        del stale_environment["SLURM_ARRAY_TASK_ID"]
    else:
        stale_environment["SLURM_ARRAY_TASK_ID"] = slurm_array_task_id
    _set_slurm_environment(monkeypatch, stale_environment)
    path_calls: list[tuple[str, tuple[str, ...]]] = []

    monkeypatch.setattr(
        runner,
        "_load_submission_handshake_for_cli",
        lambda *, launch: (claim_bytes, receipt_bytes),
    )
    monkeypatch.setattr(runner, "_parse_submission_claim", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        runner,
        "_parse_submission_receipt",
        lambda *args, **kwargs: {"outcome": "accepted", "array_job_id": "17"},
    )
    monkeypatch.setattr(
        runner.signal,
        "pthread_sigmask",
        lambda operation, mask: frozenset({signal.SIGUSR1}),
    )

    def reject_path_creation(root: str, parts: tuple[str, ...]) -> typing.NoReturn:
        path_calls.append((root, parts))
        return _unexpected_effect()

    monkeypatch.setattr(runner, "_ensure_private_relative_directory", reject_path_creation)
    monkeypatch.setattr(
        runner,
        "decode_one_cell_campaign_task",
        lambda **kwargs: _unexpected_effect(),
    )

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner.run_one_cell_authorized_task(authorization=authorization)
    assert caught.value.exit_code == expected_exit_code
    assert path_calls == []


def test_lifecycle_restores_certified_slurm_mapping_at_requeue_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_one_cell_campaign import _base_fixture

    base = tmp_path / "authority"
    launch = runner._production_shaped_launch_for_test(directory=str(base))
    configuration_bytes, task_map_members = _base_fixture()
    launch = dataclasses.replace(
        launch,
        campaign=runner.load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=task_map_members,
        ),
        resources=dataclasses.replace(
            launch.resources,
            max_requeues_per_task=2,
        ),
    )
    fixture_authorization = runner._fixture_authorized_task_for_test(directory=str(base))
    claim_bytes = b"synthetic-claim\n"
    receipt_bytes = b"synthetic-receipt\n"
    authorization = dataclasses.replace(
        fixture_authorization,
        launch=launch,
        submission_claim_sha256=hashlib.sha256(claim_bytes).hexdigest(),
        submission_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
    )
    for path in (
        Path(launch.paths.task_root),
        Path(launch.paths.attempt_root),
        Path(launch.paths.temporary_root),
        Path(launch.paths.cache_root),
        Path(launch.paths.cache_root) / "numba",
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    slurm_environment = _slurm_environment_for_authorization(authorization)
    _set_slurm_environment(monkeypatch, slurm_environment)
    progress = types.SimpleNamespace(
        disposition="requeue-required",
        generation=1,
        manifest_path=str(Path(authorization.task_directory) / "checkpoint.00000000000000000001.manifest.json"),
        checkpoint_count=1,
        snapshot_count=0,
        used_fallback=False,
    )
    requeue_environments: list[dict[str, str]] = []

    class SyntheticBinding:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class SyntheticInterruptionFlag:
        def __init__(self) -> None:
            self.requested = False

        def request(self) -> None:
            self.requested = True

    synthetic_checkpoint = types.ModuleType("tetris_ballistic.engine.one_cell_checkpoint")
    synthetic_checkpoint.OneCellCheckpointBinding = SyntheticBinding
    synthetic_checkpoint.OneCellInterruptionFlag = SyntheticInterruptionFlag
    synthetic_checkpoint.advance_one_cell_checkpoint_generation = lambda **kwargs: _unexpected_effect()
    synthetic_checkpoint.publish_one_cell_final = lambda **kwargs: _unexpected_effect()
    monkeypatch.setitem(
        sys.modules,
        "tetris_ballistic.engine.one_cell_checkpoint",
        synthetic_checkpoint,
    )
    monkeypatch.setattr(engine_root, "one_cell_checkpoint", synthetic_checkpoint, raising=False)
    monkeypatch.setattr(
        runner,
        "_load_submission_handshake_for_cli",
        lambda *, launch: (claim_bytes, receipt_bytes),
    )
    monkeypatch.setattr(runner, "_revalidate_loaded_launch_runtime", lambda launch: None)
    monkeypatch.setattr(runner, "_parse_submission_claim", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        runner,
        "_parse_submission_receipt",
        lambda *args, **kwargs: {"outcome": "accepted", "array_job_id": "17"},
    )
    monkeypatch.setattr(
        runner,
        "decode_one_cell_campaign_task",
        lambda **kwargs: types.SimpleNamespace(
            root_seed=0,
            boundary_law="periodic-v1",
            width=3,
            threshold_schedule=(0, 1),
            terminal_event_count=769,
        ),
    )
    monkeypatch.setattr(
        runner,
        "explain_one_cell_campaign_task",
        lambda **kwargs: authorization.scientific_identity_bytes,
    )
    monkeypatch.setattr(
        runner.signal,
        "pthread_sigmask",
        lambda operation, mask: frozenset({signal.SIGUSR1}),
    )
    monkeypatch.setattr(runner.signal, "getsignal", lambda selected_signal: signal.SIG_DFL)
    monkeypatch.setattr(runner.signal, "signal", lambda selected_signal, handler: None)

    def synthetic_lifecycle(**kwargs: object) -> tuple[str, object]:
        assert dict(os.environ) == dict(launch.resources.scientific_environment)
        return "requeue-required", progress

    def capture_requeue(
        selected: runner.OneCellAuthorizedTask,
        *,
        generation: int,
        checkpoint_manifest_path: str,
    ) -> None:
        assert selected.requeue_target == authorization.requeue_target
        assert generation == progress.generation
        assert checkpoint_manifest_path == progress.manifest_path
        requeue_environments.append(dict(os.environ))

    monkeypatch.setattr(runner, "_run_lifecycle_state_machine_for_test", synthetic_lifecycle)
    monkeypatch.setattr(runner, "_submit_requeue", capture_requeue)

    outcome = runner.run_one_cell_authorized_task(authorization=authorization)
    assert outcome.disposition == "requeue-submitted"
    assert len(requeue_environments) == 1
    assert {key: requeue_environments[0].get(key) for key in slurm_environment} == slurm_environment

    def invalid_lifecycle(**kwargs: object) -> typing.NoReturn:
        del kwargs
        raise runner.OneCellRunnerValidationError("unknown checkpoint disposition")

    monkeypatch.setattr(runner, "_run_lifecycle_state_machine_for_test", invalid_lifecycle)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as invalid:
        runner.run_one_cell_authorized_task(authorization=authorization)
    assert invalid.value.exit_code == 70


def test_private_lifecycle_state_machine_freezes_linearization() -> None:
    flag = types.SimpleNamespace(requested=False)
    ready = types.SimpleNamespace(disposition="ready")
    terminal = types.SimpleNamespace(disposition="terminal", generation=2)
    complete = types.SimpleNamespace(disposition="complete")
    states = iter((ready, terminal))
    events: list[str] = []

    def advance() -> object:
        events.append("advance")
        return next(states)

    def publish() -> object:
        events.append("publish")
        return complete

    disposition, progress = runner._run_lifecycle_state_machine_for_test(
        advance=advance,
        publish=publish,
        interruption_flag=flag,
    )
    assert (disposition, progress) == ("complete", complete)
    assert events == ["advance", "advance", "publish"]

    pending = types.SimpleNamespace(requested=False)

    def terminal_then_signal() -> object:
        pending.requested = True
        return terminal

    disposition, progress = runner._run_lifecycle_state_machine_for_test(
        advance=terminal_then_signal,
        publish=lambda: _unexpected_effect(),
        interruption_flag=pending,
    )
    assert (disposition, progress) == ("requeue-required", terminal)

    during_publish = types.SimpleNamespace(requested=False)

    def winning_publish() -> object:
        during_publish.requested = True
        return complete

    disposition, progress = runner._run_lifecycle_state_machine_for_test(
        advance=lambda: terminal,
        publish=winning_publish,
        interruption_flag=during_publish,
    )
    assert (disposition, progress) == ("complete", complete)


def test_private_lifecycle_resume_reuse_and_failure_classes() -> None:
    flag = types.SimpleNamespace(requested=False)
    requeue = types.SimpleNamespace(disposition="requeue-required", generation=1)
    disposition, progress = runner._run_lifecycle_state_machine_for_test(
        advance=lambda: requeue,
        publish=lambda: _unexpected_effect(),
        interruption_flag=flag,
    )
    assert (disposition, progress) == ("requeue-required", requeue)

    reused = types.SimpleNamespace(disposition="reused")
    disposition, progress = runner._run_lifecycle_state_machine_for_test(
        advance=lambda: _unexpected_effect(),
        publish=lambda: reused,
        interruption_flag=flag,
        final_present=True,
    )
    assert (disposition, progress) == ("reused", reused)

    with pytest.raises(runner.OneCellRunnerValidationError):
        runner._run_lifecycle_state_machine_for_test(
            advance=lambda: types.SimpleNamespace(disposition="forged"),
            publish=lambda: _unexpected_effect(),
            interruption_flag=flag,
        )
    with pytest.raises(runner.OneCellRunnerValidationError):
        runner._run_lifecycle_state_machine_for_test(
            advance=lambda: types.SimpleNamespace(disposition="terminal"),
            publish=lambda: types.SimpleNamespace(disposition="forged"),
            interruption_flag=flag,
        )

    calls = 0

    def always_ready() -> object:
        nonlocal calls
        calls += 1
        return types.SimpleNamespace(disposition="ready")

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as bounded:
        runner._run_lifecycle_state_machine_for_test(
            advance=always_ready,
            publish=lambda: _unexpected_effect(),
            interruption_flag=flag,
        )
    assert bounded.value.exit_code == 70
    assert calls == 1024


def test_private_width3_terminal769_resume_matches_direct_final_bytes(
    tmp_path: Path,
) -> None:
    checkpoint = pytest.importorskip(
        "tetris_ballistic.engine.one_cell_checkpoint",
        reason="the synthetic lifecycle certificate requires the HPC extra",
    )
    boundary = pytest.importorskip("tetris_ballistic.engine.one_cell_boundary")
    binding = checkpoint.OneCellCheckpointBinding(
        root_seed=0,
        boundary_law=boundary.OneCellBoundaryLaw.PERIODIC,
        width=3,
        threshold_schedule=(0, 1, 2, 5, 10, 25, 50, 100),
        terminal_event_count=769,
        configuration_bytes=b"slice-8b-private-width3-config\n",
        scientific_identity_bytes=b"slice-8b-private-width3-identity\n",
        software_commit="a" * 40,
    )
    direct = tmp_path / "direct"
    resumed = tmp_path / "resumed"
    direct.mkdir(mode=0o700)
    resumed.mkdir(mode=0o700)

    direct_terminal = checkpoint.advance_one_cell_checkpoint_generation(
        task_directory=str(direct),
        binding=binding,
    )
    assert direct_terminal.disposition == "terminal"
    direct_final = checkpoint.publish_one_cell_final(
        task_directory=str(direct),
        binding=binding,
    )
    assert direct_final.disposition == "complete"

    interrupted_flag = checkpoint.OneCellInterruptionFlag()
    interrupted_flag.request()
    disposition, interrupted = runner._run_lifecycle_state_machine_for_test(
        advance=lambda: checkpoint.advance_one_cell_checkpoint_generation(
            task_directory=str(resumed),
            binding=binding,
            interruption_flag=interrupted_flag,
        ),
        publish=lambda: _unexpected_effect(),
        interruption_flag=interrupted_flag,
    )
    assert disposition == "requeue-required"
    assert interrupted.generation == 1

    resume_flag = checkpoint.OneCellInterruptionFlag()
    disposition, resumed_final = runner._run_lifecycle_state_machine_for_test(
        advance=lambda: checkpoint.advance_one_cell_checkpoint_generation(
            task_directory=str(resumed),
            binding=binding,
            interruption_flag=resume_flag,
        ),
        publish=lambda: checkpoint.publish_one_cell_final(
            task_directory=str(resumed),
            binding=binding,
        ),
        interruption_flag=resume_flag,
    )
    assert disposition == "complete"
    assert resumed_final.checkpoint_count == 512
    assert resumed_final.snapshot_count == 16
    assert {path.name: path.read_bytes() for path in direct.glob("final.*")} == {
        path.name: path.read_bytes() for path in resumed.glob("final.*")
    }

    disposition, reused = runner._run_lifecycle_state_machine_for_test(
        advance=lambda: _unexpected_effect(),
        publish=lambda: checkpoint.publish_one_cell_final(
            task_directory=str(resumed),
            binding=binding,
        ),
        interruption_flag=checkpoint.OneCellInterruptionFlag(),
        final_present=True,
    )
    assert disposition == "reused"
    assert reused.used_fallback is False


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    (
        ({"returncode": 0, "stdout": b"1\n", "stderr": b"", "submission": True}, ("accepted", "1")),
        (
            {
                "returncode": 0,
                "stdout": b"4294967295\n",
                "stderr": b"",
                "submission": True,
            },
            ("accepted", "4294967295"),
        ),
        ({"returncode": 2, "stdout": b"refused", "stderr": b"why", "submission": True}, ("rejected", None)),
        ({"returncode": 0, "stdout": b"", "stderr": b"", "submission": False}, ("accepted", None)),
        ({"returncode": 1, "stdout": b"", "stderr": b"why", "submission": False}, ("rejected", None)),
    ),
)
def test_scheduler_result_classifier_accepts_only_frozen_success_grammars(
    kwargs: dict[str, object],
    expected: tuple[str, str | None],
) -> None:
    assert runner._classify_scheduler_result_for_test(**kwargs) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    (
        {"returncode": 0, "stdout": b"", "stderr": b"", "submission": True},
        {"returncode": 0, "stdout": b"0\n", "stderr": b"", "submission": True},
        {"returncode": 0, "stdout": b"01\n", "stderr": b"", "submission": True},
        {"returncode": 0, "stdout": b"4294967296\n", "stderr": b"", "submission": True},
        {"returncode": 0, "stdout": b"17", "stderr": b"", "submission": True},
        {"returncode": 0, "stdout": b"17\n\n", "stderr": b"", "submission": True},
        {"returncode": 0, "stdout": b"17;cluster\n", "stderr": b"", "submission": True},
        {"returncode": 0, "stdout": b"17\n", "stderr": b"warning", "submission": True},
        {"returncode": -9, "stdout": b"", "stderr": b"", "submission": True},
        {"returncode": None, "stdout": b"", "stderr": b"", "submission": True},
        {"returncode": 0, "stdout": b"17\n", "stderr": b"", "submission": True, "timed_out": True},
        {"returncode": 0, "stdout": b"17\n", "stderr": b"", "submission": True, "spawn_ambiguous": True},
        {"returncode": 0, "stdout": b"17\n", "stderr": b"", "submission": True, "stdout_overflow": True},
        {"returncode": 0, "stdout": b"", "stderr": b"", "submission": False, "stderr_overflow": True},
        {"returncode": 0, "stdout": b"noise", "stderr": b"", "submission": False},
    ),
)
def test_scheduler_result_classifier_marks_every_ambiguity_unknown(
    changes: dict[str, object],
) -> None:
    defaults: dict[str, object] = {
        "returncode": 0,
        "stdout": b"",
        "stderr": b"",
        "submission": True,
    }
    defaults.update(changes)
    assert runner._classify_scheduler_result_for_test(**defaults) == (  # type: ignore[arg-type]
        "unknown",
        None,
    )


def test_scheduler_classifier_rejects_hostile_python_types() -> None:
    with pytest.raises(TypeError):
        runner._classify_scheduler_result_for_test(
            returncode=True,
            stdout=b"",
            stderr=b"",
            submission=True,
        )


def test_git_gate_uses_bound_binary_exact_environment_and_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _runner_paths(tmp_path)
    Path(paths.authorization_checkout).mkdir(parents=True, mode=0o700)
    calls: list[tuple[tuple[str, ...], tuple[tuple[str, str], ...], int, int]] = []
    results = iter(
        (
            runner._ProcessResult(
                0,
                b"git version synthetic\n",
                False,
                b"",
                False,
                False,
                False,
            ),
            runner._ProcessResult(
                0,
                b"clean\n",
                False,
                b"",
                False,
                False,
                False,
            ),
        )
    )

    def run_process(
        argv: tuple[str, ...],
        *,
        environment: tuple[tuple[str, str], ...],
        timeout_seconds: int,
        capture_limit: int,
    ) -> runner._ProcessResult:
        calls.append((argv, environment, timeout_seconds, capture_limit))
        return next(results)

    monkeypatch.setattr(runner, "_validate_tool_file", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_run_bounded_process", run_process)

    suffix = ("status", "--porcelain=v2", "--untracked-files=all")
    result = runner._git_command(paths, suffix, maximum=123)

    git_environment = (
        ("LANG", "C"),
        ("LC_ALL", "C"),
        ("GIT_CONFIG_NOSYSTEM", "1"),
        ("GIT_CONFIG_GLOBAL", "/dev/null"),
        ("GIT_CONFIG_COUNT", "0"),
        ("GIT_ATTR_NOSYSTEM", "1"),
        ("GIT_NO_REPLACE_OBJECTS", "1"),
        ("GIT_OPTIONAL_LOCKS", "0"),
        ("GIT_TERMINAL_PROMPT", "0"),
    )
    assert result.stdout == b"clean\n"
    assert calls == [
        (
            (paths.git_executable, "--version"),
            git_environment,
            30,
            257,
        ),
        (
            (
                paths.git_executable,
                "--no-pager",
                "--no-replace-objects",
                "--literal-pathspecs",
                "--no-optional-locks",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "diff.external=",
                "-c",
                "credential.helper=",
                "-C",
                paths.authorization_checkout,
                *suffix,
            ),
            git_environment,
            30,
            123,
        ),
    ]


def test_git_version_mismatch_refuses_before_authority_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _runner_paths(tmp_path)
    Path(paths.authorization_checkout).mkdir(parents=True, mode=0o700)
    calls = 0

    def run_process(*args: object, **kwargs: object) -> runner._ProcessResult:
        nonlocal calls
        del args, kwargs
        calls += 1
        return runner._ProcessResult(
            0,
            b"git version changed\n",
            False,
            b"",
            False,
            False,
            False,
        )

    monkeypatch.setattr(runner, "_validate_tool_file", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_run_bounded_process", run_process)

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._git_command(paths, ("status", "--porcelain=v2"))
    assert caught.value.exit_code == 78
    assert calls == 1


@pytest.mark.parametrize("version_size", (255, 256))
def test_git_version_capture_accepts_full_frozen_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version_size: int,
) -> None:
    version = "g" * version_size
    paths = dataclasses.replace(_runner_paths(tmp_path), git_version=version)
    Path(paths.authorization_checkout).mkdir(parents=True, mode=0o700)
    results = iter(
        (
            runner._ProcessResult(0, version.encode("ascii") + b"\n", False, b"", False, False, False),
            runner._ProcessResult(0, b"ok\n", False, b"", False, False, False),
        )
    )
    capture_limits: list[int] = []

    def run_process(
        argv: tuple[str, ...],
        *,
        environment: tuple[tuple[str, str], ...],
        timeout_seconds: int,
        capture_limit: int,
    ) -> runner._ProcessResult:
        del argv, environment, timeout_seconds
        capture_limits.append(capture_limit)
        return next(results)

    monkeypatch.setattr(runner, "_validate_tool_file", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_run_bounded_process", run_process)
    result = runner._git_command(paths, ("status",), maximum=17)
    assert result.stdout == b"ok\n"
    assert capture_limits == [257, 17]


def test_git_reachability_is_checked_from_prerequisite_to_pushed_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _runner_paths(tmp_path)
    prerequisite = "1" * 40
    pushed_launch = "2" * 40
    calls: list[tuple[tuple[str, ...], int, tuple[int, ...]]] = []

    def git_command(
        selected_paths: runner.OneCellRunnerPaths,
        suffix: tuple[str, ...],
        *,
        maximum: int,
        accepted_returncodes: tuple[int, ...],
    ) -> runner._ProcessResult:
        assert selected_paths == paths
        calls.append((suffix, maximum, accepted_returncodes))
        return runner._ProcessResult(0, b"", False, b"", False, False, False)

    monkeypatch.setattr(runner, "_git_command", git_command)
    runner._require_git_ancestor(
        paths,
        prerequisite=prerequisite,
        trusted_commit=pushed_launch,
    )
    assert calls == [
        (
            ("merge-base", "--is-ancestor", prerequisite, pushed_launch),
            1,
            (0, 1),
        )
    ]

    monkeypatch.setattr(
        runner,
        "_git_command",
        lambda *args, **kwargs: runner._ProcessResult(
            1,
            b"",
            False,
            b"",
            False,
            False,
            False,
        ),
    )
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._require_git_ancestor(
            paths,
            prerequisite=prerequisite,
            trusted_commit=pushed_launch,
        )
    assert caught.value.exit_code == 76


def test_user_owned_bootstrap_git_is_refused_before_any_git_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _runner_paths(tmp_path)
    deployment = {
        "ownership": {
            "campaign_uid": os.geteuid(),
            "trusted_administrator_uids": [os.geteuid()],
        },
        "_parsed_tools": {
            "git": {
                "path": paths.git_executable,
                "realpath": paths.git_executable_realpath,
                "owner_uid": os.geteuid(),
                "mode": 0o755,
                "size_bytes": paths.git_size_bytes,
                "sha256": paths.git_sha256,
            }
        },
    }
    monkeypatch.setattr(runner, "_validate_tool_file", lambda **kwargs: _unexpected_effect())
    monkeypatch.setattr(
        runner,
        "_run_bounded_process",
        lambda *args, **kwargs: _unexpected_effect(),
    )

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_bootstrap_git_trust(paths, deployment)
    assert caught.value.exit_code == 77

    source = inspect.getsource(runner._load_one_cell_launch_authority_impl)
    trust_position = source.find("_validate_bootstrap_git_trust(")
    assert trust_position >= 0
    for first_git_effect in ("_validate_git_checkout(", "_git_blob("):
        position = source.find(first_git_effect)
        assert position < 0 or trust_position < position


def test_software_batch_source_commit_blob_and_bytes_join_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _runner_paths(tmp_path)
    source_commit = "1" * 40
    git_blob = "2" * 40
    batch_path = "scripts/easley/run_pre_one_cell.sbatch"
    payload = b"#!/bin/bash\nexit 0\n"
    batch = {
        "source_commit": source_commit,
        "path": batch_path,
        "git_blob": git_blob,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
    }
    deployment = {
        "source_commit": source_commit,
        "paths": {"software_checkout": "/trusted/software-checkout"},
        "batch_script": batch,
    }
    deployment_lock = {
        "source": {"commit": source_commit},
        "batch_script": batch,
    }
    launch = {"batch_script": batch}
    calls: list[tuple[str, ...]] = []

    def git_command(
        selected_paths: runner.OneCellRunnerPaths,
        suffix: tuple[str, ...],
        **kwargs: object,
    ) -> runner._ProcessResult:
        assert selected_paths == paths
        calls.append(suffix)
        if suffix == ("rev-parse", "--path-format=absolute", "--show-toplevel"):
            stdout = b"/trusted/software-checkout\n"
        elif suffix == ("rev-parse", "--verify", "HEAD"):
            stdout = source_commit.encode() + b"\n"
        elif suffix == ("rev-parse", "--verify", "refs/remotes/origin/main"):
            stdout = source_commit.encode() + b"\n"
        elif suffix == ("symbolic-ref", "-q", "HEAD"):
            stdout = b""
        elif suffix == ("status", "--porcelain=v1", "--untracked-files=all"):
            stdout = b""
        elif suffix == (
            "merge-base",
            "--is-ancestor",
            runner._SLICE_8B_SOFTWARE_PARENT,
            source_commit,
        ):
            stdout = b""
        elif suffix == ("ls-tree", "-z", source_commit, "--", batch_path):
            stdout = f"100755 blob {git_blob}\t{batch_path}".encode() + b"\0"
        elif suffix == ("cat-file", "blob", f"{source_commit}:{batch_path}"):
            stdout = payload
        else:
            raise AssertionError(suffix)
        return runner._ProcessResult(0, stdout, False, b"", False, False, False)

    monkeypatch.setattr(runner, "_git_command", git_command)
    monkeypatch.setattr(runner, "_read_regular_file", lambda *args, **kwargs: payload)
    assert (
        runner._validate_software_checkout_and_batch(
            paths,
            deployment=deployment,
            deployment_lock=deployment_lock,
            launch=launch,
        )
        == payload
    )
    assert calls == [
        ("rev-parse", "--path-format=absolute", "--show-toplevel"),
        ("rev-parse", "--verify", "HEAD"),
        ("rev-parse", "--verify", "refs/remotes/origin/main"),
        ("symbolic-ref", "-q", "HEAD"),
        ("status", "--porcelain=v1", "--untracked-files=all"),
        (
            "merge-base",
            "--is-ancestor",
            runner._SLICE_8B_SOFTWARE_PARENT,
            source_commit,
        ),
        ("ls-tree", "-z", source_commit, "--", batch_path),
        ("cat-file", "blob", f"{source_commit}:{batch_path}"),
    ]

    def wrong_blob(
        selected_paths: runner.OneCellRunnerPaths,
        suffix: tuple[str, ...],
        **kwargs: object,
    ) -> runner._ProcessResult:
        result = git_command(selected_paths, suffix, **kwargs)
        if suffix[0] == "ls-tree":
            return dataclasses.replace(
                result,
                stdout=f"100755 blob {'3' * 40}\t{batch_path}".encode() + b"\0",
            )
        return result

    monkeypatch.setattr(runner, "_git_command", wrong_blob)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_software_checkout_and_batch(
            paths,
            deployment=deployment,
            deployment_lock=deployment_lock,
            launch=launch,
        )
    assert caught.value.exit_code == 76


def test_sbatch_argv_is_exact_and_contains_no_ambient_override(tmp_path: Path) -> None:
    launch = runner._fixture_launch_authority_for_test(directory=str(tmp_path / "fixture-authority"))
    resources = launch.resources
    paths = launch.paths
    assert runner._sbatch_argv(launch) == (
        resources.sbatch_executable,
        "--parsable",
        "--requeue",
        "--export=NIL",
        "--open-mode=append",
        "--nodes=1",
        "--ntasks=1",
        "--cpus-per-task=1",
        "--mem=1M",
        "--time=17",
        "--partition=fixture",
        "--array=0-0%1",
        "--signal=B:USR1@900",
        f"--chdir={paths.authorized_run_directory}",
        f"--output={paths.stdout_template}",
        f"--error={paths.stderr_template}",
        paths.batch_script,
        launch.authorization_path,
    )
    argv_text = "\n".join(runner._sbatch_argv(launch))
    for forbidden in (
        "--account",
        "--qos",
        "--dependency",
        "--wrap",
        "--export=NONE",
        "--clusters",
    ):
        assert forbidden not in argv_text


def test_post_load_batch_replacement_is_refused_before_claim_or_scheduler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    batch_path = Path(launch.paths.batch_script)
    batch_path.parent.mkdir(parents=True, mode=0o700)
    original = b"#!/bin/bash\nexit 0\n"
    batch_path.write_bytes(original)
    batch_path.chmod(0o600)
    wire = json.loads(_fixture_launch_bytes(profile="tetris-pre-one-cell-launch-fixture@1"))
    del wire["fixture"]
    wire["profile"] = "tetris-pre-one-cell-launch@1"
    wire["authorities"]["source_commit"] = launch.software_commit
    wire["batch_script"].update(
        {
            "source_commit": launch.software_commit,
            "path": "scripts/easley/run_pre_one_cell.sbatch",
            "sha256": hashlib.sha256(original).hexdigest(),
            "size_bytes": len(original),
        }
    )
    wire["paths"]["batch_script"] = str(batch_path)
    launch_bytes = _canonical_json(wire)
    launch = dataclasses.replace(
        launch,
        launch_bytes=launch_bytes,
        launch_sha256=hashlib.sha256(launch_bytes).hexdigest(),
        launch_size_bytes=len(launch_bytes),
    )
    assert runner._validate_live_batch_script(launch) == original

    replacement = batch_path.with_suffix(".replacement")
    replacement.write_bytes(b"#!/bin/bash\nexit 9\n")
    replacement.chmod(0o600)
    replacement.replace(batch_path)
    monkeypatch.setattr(
        runner,
        "_run_bounded_process",
        lambda *args, **kwargs: _unexpected_effect(),
    )

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._submission_claim_bytes(launch, runner._sbatch_argv(launch))
    assert caught.value.exit_code == 78


def test_ledger_rejects_a_symlinked_ancestor_before_locking(tmp_path: Path) -> None:
    real_base = tmp_path / "real-base"
    linked_base = tmp_path / "linked-base"
    ledger_root = real_base / "campaign" / "private" / "submission-ledger"
    for path in (
        ledger_root,
        ledger_root / "claims",
        ledger_root / "receipts",
        ledger_root / "requeue-permits",
        ledger_root / "requeue-results",
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    lock = ledger_root / "ledger.lock"
    lock.write_bytes(b"lock")
    lock.chmod(0o600)
    linked_base.symlink_to(real_base, target_is_directory=True)
    launch = runner._fixture_launch_authority_for_test(directory=str(linked_base))

    handles = None
    try:
        with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
            handles = runner._open_ledger(launch, exclusive=False)
        assert caught.value.exit_code == 76
    finally:
        if handles is not None:
            runner._close_ledger(handles)


@pytest.mark.parametrize("member", ("claims", "ledger.lock"))
def test_ledger_close_detects_named_child_or_lock_inode_replacement(
    tmp_path: Path,
    member: str,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    ledger_root = _create_private_ledger(launch)
    handles = runner._open_ledger(launch, exclusive=True)
    target = ledger_root / member
    displaced = ledger_root / f"{member}.displaced"
    target.rename(displaced)
    if member == "ledger.lock":
        target.write_bytes(b"replacement-lock")
        target.chmod(0o600)
    else:
        target.mkdir(mode=0o700)
        target.chmod(0o700)

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._close_ledger(handles)
    assert caught.value.exit_code == 76


def _create_private_ledger(launch: runner.OneCellLaunchAuthority) -> Path:
    ledger_root = Path(launch.paths.submission_ledger_root)
    for path in (
        ledger_root,
        ledger_root / "claims",
        ledger_root / "receipts",
        ledger_root / "requeue-permits",
        ledger_root / "requeue-results",
    ):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    lock = Path(launch.paths.submission_ledger_lock)
    lock.write_bytes(b"lock")
    lock.chmod(0o600)
    return ledger_root


def test_failed_guard_directory_fsync_removes_temporary_before_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    ledger_root = _create_private_ledger(launch)
    name = f"{launch.launch_sha256}.json"
    claim = ledger_root / "claims" / name
    claim.write_bytes(b"claimed-before-scheduler\n")
    claim.chmod(0o600)
    receipts = ledger_root / "receipts"
    descriptor = os.open(receipts, os.O_RDONLY | os.O_DIRECTORY)
    real_fsync = runner.os.fsync
    directory_fsync_calls = 0

    def fail_first_directory_fsync(selected: int) -> None:
        nonlocal directory_fsync_calls
        if selected == descriptor:
            directory_fsync_calls += 1
            if directory_fsync_calls == 1:
                raise OSError(errno.EIO, "injected receipt directory fsync failure")
        real_fsync(selected)

    monkeypatch.setattr(runner.os, "fsync", fail_first_directory_fsync)
    try:
        with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
            runner._install_link_record(
                descriptor,
                name,
                b"accepted-looking-receipt\n",
                parent_path=str(receipts),
                label="submission receipt",
            )
        assert caught.value.exit_code == 74
    finally:
        os.close(descriptor)
    assert directory_fsync_calls == 2
    assert tuple(receipts.iterdir()) == ()

    ticks = iter((0, 60_000_000_001, 60_000_000_001))
    monkeypatch.setattr(runner.time, "monotonic_ns", lambda: next(ticks))
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as handshake:
        runner._load_submission_handshake_for_cli(launch=launch)
    assert handshake.value.exit_code == 66


def test_failed_target_proving_fsync_removes_target_before_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    name = "receipt.json"
    descriptor = os.open(receipts, os.O_RDONLY | os.O_DIRECTORY)
    real_fsync = runner.os.fsync
    directory_fsync_calls = 0

    def fail_target_proving_fsync(selected: int) -> None:
        nonlocal directory_fsync_calls
        if selected == descriptor:
            directory_fsync_calls += 1
            if directory_fsync_calls == 2:
                raise OSError(errno.EIO, "injected target-proving fsync failure")
        real_fsync(selected)

    monkeypatch.setattr(runner.os, "fsync", fail_target_proving_fsync)
    try:
        with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
            runner._install_link_record(
                descriptor,
                name,
                b"accepted-looking-receipt\n",
                parent_path=str(receipts),
                label="submission receipt",
            )
        assert caught.value.exit_code == 74
    finally:
        os.close(descriptor)
    assert directory_fsync_calls == 4
    assert tuple(receipts.iterdir()) == ()


def test_failed_proving_fsync_with_unremovable_target_persists_guarded_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    name = "receipt.json"
    descriptor = os.open(receipts, os.O_RDONLY | os.O_DIRECTORY)
    real_fsync = runner.os.fsync
    real_unlink = runner.os.unlink
    directory_fsync_calls = 0
    target_unlink_calls = 0

    def fail_target_proving_fsync(selected: int) -> None:
        nonlocal directory_fsync_calls
        if selected == descriptor:
            directory_fsync_calls += 1
            if directory_fsync_calls == 2:
                raise OSError(errno.EIO, "injected target-proving fsync failure")
        real_fsync(selected)

    def refuse_target_unlink(path: str, *args: object, **kwargs: object) -> None:
        nonlocal target_unlink_calls
        if path == name:
            target_unlink_calls += 1
            raise OSError(errno.EIO, "injected target unlink failure")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(runner.os, "fsync", fail_target_proving_fsync)
    monkeypatch.setattr(runner.os, "unlink", refuse_target_unlink)
    try:
        with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
            runner._install_link_record(
                descriptor,
                name,
                b"accepted-looking-receipt\n",
                parent_path=str(receipts),
                label="submission receipt",
            )
        assert caught.value.exit_code == 74
        assert directory_fsync_calls == 3
        assert target_unlink_calls == 1
        members = tuple(receipts.iterdir())
        assert len(members) == 2
        assert all(member.stat().st_nlink == 2 for member in members)
        with pytest.raises(runner.OneCellRunnerAuthorizationError) as guarded:
            runner._read_ledger_member(
                descriptor,
                name,
                parent_path=str(receipts),
                label="submission receipt",
            )
        assert guarded.value.exit_code == 76
    finally:
        os.close(descriptor)


def test_failed_guard_cleanup_fsync_keeps_the_durable_single_link_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    name = "receipt.json"
    payload = b"durable-receipt\n"
    descriptor = os.open(receipts, os.O_RDONLY | os.O_DIRECTORY)
    real_fsync = runner.os.fsync
    directory_fsync_calls = 0

    def fail_second_directory_fsync(selected: int) -> None:
        nonlocal directory_fsync_calls
        if selected == descriptor:
            directory_fsync_calls += 1
            if directory_fsync_calls == 3:
                raise OSError(errno.EIO, "injected guard-cleanup fsync failure")
        real_fsync(selected)

    monkeypatch.setattr(runner.os, "fsync", fail_second_directory_fsync)
    try:
        runner._install_link_record(
            descriptor,
            name,
            payload,
            parent_path=str(receipts),
            label="submission receipt",
        )
        assert directory_fsync_calls == 3
        assert (
            runner._read_ledger_member(
                descriptor,
                name,
                parent_path=str(receipts),
                label="submission receipt",
            )
            == payload
        )
    finally:
        os.close(descriptor)
    assert tuple(path.name for path in receipts.iterdir()) == (name,)


@pytest.mark.parametrize(
    ("crash_point", "expected_link_count"),
    (
        ("before_guard_directory_fsync", None),
        ("after_guard_directory_fsync", None),
        ("before_target_directory_fsync", 2),
        ("after_target_directory_fsync", 2),
        ("after_guard_unlink", 1),
    ),
)
def test_link_publication_crash_boundaries_are_fail_closed_or_durable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    crash_point: str,
    expected_link_count: int | None,
) -> None:
    class InjectedCrash(BaseException):
        pass

    receipts = tmp_path / "receipts"
    receipts.mkdir(mode=0o700)
    name = "receipt.json"
    payload = b"crash-boundary-receipt\n"
    descriptor = os.open(receipts, os.O_RDONLY | os.O_DIRECTORY)
    real_fsync = runner.os.fsync
    real_link = runner.os.link
    real_unlink = runner.os.unlink
    directory_fsync_calls = 0

    def crash_fsync(selected: int) -> None:
        nonlocal directory_fsync_calls
        if selected == descriptor:
            directory_fsync_calls += 1
            if crash_point == "before_guard_directory_fsync" and directory_fsync_calls == 1:
                raise InjectedCrash
            if crash_point == "before_target_directory_fsync" and directory_fsync_calls == 2:
                raise InjectedCrash
            if crash_point == "after_guard_unlink" and directory_fsync_calls == 3:
                raise InjectedCrash
        real_fsync(selected)

    def crash_link(*args: object, **kwargs: object) -> None:
        if crash_point == "after_guard_directory_fsync":
            raise InjectedCrash
        real_link(*args, **kwargs)

    def crash_unlink(path: str, *args: object, **kwargs: object) -> None:
        if crash_point == "after_target_directory_fsync" and path != name:
            raise InjectedCrash
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(runner.os, "fsync", crash_fsync)
    monkeypatch.setattr(runner.os, "link", crash_link)
    monkeypatch.setattr(runner.os, "unlink", crash_unlink)
    try:
        with pytest.raises(InjectedCrash):
            runner._install_link_record(
                descriptor,
                name,
                payload,
                parent_path=str(receipts),
                label="submission receipt",
            )
        target = receipts / name
        if expected_link_count is None:
            assert not target.exists()
            assert (
                runner._read_ledger_member(
                    descriptor,
                    name,
                    parent_path=str(receipts),
                    label="submission receipt",
                )
                is None
            )
        elif expected_link_count == 2:
            assert target.stat().st_nlink == 2
            with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
                runner._read_ledger_member(
                    descriptor,
                    name,
                    parent_path=str(receipts),
                    label="submission receipt",
                )
            assert caught.value.exit_code == 76
        else:
            assert target.stat().st_nlink == 1
            assert (
                runner._read_ledger_member(
                    descriptor,
                    name,
                    parent_path=str(receipts),
                    label="submission receipt",
                )
                == payload
            )
    finally:
        os.close(descriptor)


def test_stable_receipt_without_claim_is_integrity_failure(tmp_path: Path) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    ledger_root = _create_private_ledger(launch)
    receipt = ledger_root / "receipts" / f"{launch.launch_sha256}.json"
    receipt.write_bytes(b"{}\n")
    receipt.chmod(0o600)

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._load_submission_handshake_for_cli(launch=launch)
    assert caught.value.exit_code == 76


def test_ledger_lock_excludes_concurrent_claimants_and_reopens_after_release(
    tmp_path: Path,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    _create_private_ledger(launch)
    first = runner._open_ledger(launch, exclusive=True)
    try:
        with pytest.raises(BlockingIOError):
            runner._open_ledger(launch, exclusive=True, nonblocking=True)
    finally:
        runner._close_ledger(first)

    reopened = runner._open_ledger(launch, exclusive=True, nonblocking=True)
    runner._close_ledger(reopened)


def test_existing_claim_refuses_repeat_submission_before_scheduler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    ledger_root = _create_private_ledger(launch)
    claim = ledger_root / "claims" / f"{launch.launch_sha256}.json"
    claim.write_bytes(b"consumed-claim\n")
    claim.chmod(0o600)
    monkeypatch.setattr(runner, "_validate_tool_file", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_revalidate_loaded_launch_runtime", lambda launch: None)
    monkeypatch.setattr(runner, "_validate_argv_path_limits", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "_submission_claim_bytes",
        lambda *args, **kwargs: b"new-claim-must-not-be-installed\n",
    )
    monkeypatch.setattr(
        runner,
        "_run_bounded_process",
        lambda *args, **kwargs: _unexpected_effect(),
    )

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._submit_one_cell_launch_impl(launch=launch)
    assert caught.value.exit_code == 77
    assert claim.read_bytes() == b"consumed-claim\n"
    assert not (ledger_root / "receipts" / claim.name).exists()


def test_submission_state_machine_consumes_claim_for_every_scheduler_outcome() -> None:
    assert runner._run_submission_state_machine_for_test(
        returncode=0,
        stdout=b"17\n",
        stderr=b"",
        receipt_durable=True,
    ) == ("accepted", "17", True)
    assert runner._run_submission_state_machine_for_test(
        returncode=2,
        stdout=b"",
        stderr=b"refused",
        receipt_durable=True,
    ) == ("rejected", None, True)
    assert runner._run_submission_state_machine_for_test(
        returncode=0,
        stdout=b"17;cluster\n",
        stderr=b"",
        receipt_durable=True,
    ) == ("unknown", None, True)
    assert runner._run_submission_state_machine_for_test(
        returncode=None,
        stdout=b"",
        stderr=b"",
        receipt_durable=True,
        spawn_ambiguous=True,
    ) == ("unknown", None, True)


def test_accepted_submission_without_durable_receipt_is_exit75_and_no_replay() -> None:
    with pytest.raises(runner.OneCellSchedulerError) as caught:
        runner._run_submission_state_machine_for_test(
            returncode=0,
            stdout=b"17\n",
            stderr=b"",
            receipt_durable=False,
        )
    assert caught.value.exit_code == 75
    assert caught.value.claim_consumed is True
    assert caught.value.additional_initial_call_permitted is False


def test_closed_pipes_do_not_escape_timeout_or_leave_child_running(
    tmp_path: Path,
) -> None:
    pid_path = tmp_path / "child.pid"
    script = (
        f"import os,time;open({str(pid_path)!r},'w').write(str(os.getpid()));os.close(1);os.close(2);time.sleep(30)"
    )
    started = time.monotonic()
    child_pid: int | None = None
    try:
        result = runner._run_bounded_process(
            (sys.executable, "-I", "-B", "-c", script),
            environment=(("LANG", "C"), ("LC_ALL", "C")),
            timeout_seconds=1,
        )
        elapsed = time.monotonic() - started
        assert elapsed < 10
        assert result.timed_out is True
        assert runner._classify_scheduler_result(
            result=result,
            submission=True,
        ) == ("unknown", None)
        child_pid = int(pid_path.read_text(encoding="ascii"))
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
    finally:
        if child_pid is None and pid_path.exists():
            child_pid = int(pid_path.read_text(encoding="ascii"))
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def _requeue_driver_arguments(**changes: object) -> dict[str, object]:
    values: dict[str, object] = {
        "scontrol_executable": "/usr/bin/scontrol",
        "array_job_id": "17",
        "array_position": 0,
        "current_restart_count": 0,
        "retry_cap": 2,
        "permit_already_exists": False,
        "result_already_exists": False,
        "returncode": 0,
        "stdout": b"",
        "stderr": b"",
        "result_durable": True,
    }
    values.update(changes)
    return values


def test_requeue_state_machine_uses_exact_element_and_consumes_permit() -> None:
    assert runner._run_requeue_state_machine_for_test(**_requeue_driver_arguments()) == (
        ("/usr/bin/scontrol", "requeue", "17_0"),
        1,
        True,
    )
    assert runner._run_requeue_state_machine_for_test(
        **_requeue_driver_arguments(
            array_job_id="4294967295",
            array_position=1799,
            current_restart_count=15,
            retry_cap=16,
        )
    ) == (("/usr/bin/scontrol", "requeue", "4294967295_1799"), 16, True)


@pytest.mark.parametrize(
    "changes",
    (
        {"current_restart_count": 0, "retry_cap": 0},
        {"current_restart_count": 2, "retry_cap": 2},
        {"permit_already_exists": True},
        {"result_already_exists": True},
    ),
)
def test_requeue_cap_and_replay_refuse_before_another_scontrol(
    changes: dict[str, object],
) -> None:
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._run_requeue_state_machine_for_test(**_requeue_driver_arguments(**changes))
    assert caught.value.exit_code == 77


@pytest.mark.parametrize(
    ("changes", "exit_code"),
    (
        ({"returncode": 2, "stderr": b"refused"}, 69),
        ({"returncode": 0, "stdout": b"unexpected"}, 75),
        ({"returncode": None, "spawn_ambiguous": True}, 75),
        ({"returncode": 0, "timed_out": True}, 75),
        ({"returncode": 0, "stdout_overflow": True}, 75),
    ),
)
def test_requeue_scheduler_failures_consume_permit_and_forbid_replay(
    changes: dict[str, object],
    exit_code: int,
) -> None:
    with pytest.raises(runner.OneCellSchedulerError) as caught:
        runner._run_requeue_state_machine_for_test(**_requeue_driver_arguments(**changes))
    assert caught.value.exit_code == exit_code
    assert caught.value.permit_consumed is True
    assert caught.value.additional_scontrol_permitted is False


def test_requeue_result_durability_failure_consumes_permit() -> None:
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._run_requeue_state_machine_for_test(**_requeue_driver_arguments(result_durable=False))
    assert caught.value.exit_code == 74
    assert caught.value.permit_consumed is True
    assert caught.value.additional_scontrol_permitted is False


def _restart_permit_records(
    launch: runner.OneCellLaunchAuthority,
    *,
    receipt_sha256: str,
    outcome: str = "accepted",
    manifest_path: str | None = None,
    manifest_sha256: str = "c" * 64,
) -> tuple[str, bytes, bytes]:
    task = launch.ordered_tasks[0]
    argv = (launch.resources.scontrol_executable, "requeue", "17_0")
    generation = 1
    selected_manifest_path = manifest_path or str(
        Path(launch.paths.task_root) / task.relative_task_directory / f"checkpoint.{generation:020d}.manifest.json"
    )
    permit_bytes = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-requeue-permit@1",
            "launch_sha256": launch.launch_sha256,
            "submission_receipt_sha256": receipt_sha256,
            "scientific_identity_sha256": task.scientific_identity_sha256,
            "array_job_id": "17",
            "array_position": 0,
            "slurm_job_id": "29",
            "current_restart_count": 0,
            "target_restart_count": 1,
            "retry_cap": launch.resources.max_requeues_per_task,
            "generation": generation,
            "checkpoint_manifest_path": selected_manifest_path,
            "checkpoint_manifest_sha256": manifest_sha256,
            "scontrol_argv": list(argv),
            "scontrol_argv_sha256": runner._argv_digest(
                argv,
                profile="tetris-pre-one-cell-scontrol-argv@1",
            ),
        }
    )
    if outcome == "accepted":
        returncode = 0
        stderr = b""
    elif outcome == "rejected":
        returncode = 1
        stderr = b"refused"
    else:
        raise AssertionError(outcome)
    result_bytes = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-requeue-result@1",
            "permit_sha256": hashlib.sha256(permit_bytes).hexdigest(),
            "outcome": outcome,
            "returncode": returncode,
            "stdout_hex": "",
            "stdout_overflow": False,
            "stderr_hex": stderr.hex(),
            "stderr_overflow": False,
        }
    )
    name = f"{launch.launch_sha256}-p{0:020d}-r{0:020d}-to-{1:020d}.json"
    return name, permit_bytes, result_bytes


def test_requeue_manifest_generation_mismatch_refuses_before_ledger_or_scheduler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "authority"
    launch = runner._production_shaped_launch_for_test(directory=str(base))
    launch = dataclasses.replace(
        launch,
        resources=dataclasses.replace(launch.resources, max_requeues_per_task=2),
    )
    authorization = dataclasses.replace(
        runner._fixture_authorized_task_for_test(directory=str(base)),
        launch=launch,
    )
    monkeypatch.setattr(runner, "_revalidate_requeue_context", lambda selected: None)
    monkeypatch.setattr(runner, "_read_regular_file", lambda *args, **kwargs: _unexpected_effect())
    monkeypatch.setattr(runner, "_open_ledger", lambda *args, **kwargs: _unexpected_effect())
    monkeypatch.setattr(runner, "_run_bounded_process", lambda *args, **kwargs: _unexpected_effect())

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._submit_requeue(
            authorization,
            generation=2,
            checkpoint_manifest_path=str(
                Path(authorization.task_directory) / "checkpoint.00000000000000000001.manifest.json"
            ),
        )
    assert caught.value.exit_code == 76


@pytest.mark.parametrize("mutation", ("path", "digest"))
def test_restart_permit_binds_exact_task_manifest_path_and_live_digest(
    tmp_path: Path,
    mutation: str,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    launch = dataclasses.replace(
        launch,
        resources=dataclasses.replace(launch.resources, max_requeues_per_task=2),
    )
    ledger_root = _create_private_ledger(launch)
    task = launch.ordered_tasks[0]
    receipt_sha256 = "b" * 64
    manifest_path = (
        Path(launch.paths.task_root) / task.relative_task_directory / "checkpoint.00000000000000000001.manifest.json"
    )
    manifest_bytes = b"synthetic-checkpoint-manifest\n"
    manifest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest_path.write_bytes(manifest_bytes)
    manifest_path.chmod(0o600)
    selected_path = (
        str(manifest_path.parent / "checkpoint.00000000000000000002.manifest.json")
        if mutation == "path"
        else str(manifest_path)
    )
    selected_digest = (
        hashlib.sha256(manifest_bytes).hexdigest()
        if mutation == "path"
        else hashlib.sha256(b"different-manifest\n").hexdigest()
    )
    name, permit_bytes, _ = _restart_permit_records(
        launch,
        receipt_sha256=receipt_sha256,
        manifest_path=selected_path,
        manifest_sha256=selected_digest,
    )
    permit_path = ledger_root / "requeue-permits" / name
    permit_path.write_bytes(permit_bytes)
    permit_path.chmod(0o600)

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_restart_permit(
            launch,
            receipt_sha256=receipt_sha256,
            task=task,
            array_job_id="17",
            array_position=0,
            restart_count=1,
        )
    assert caught.value.exit_code == 76


def test_end_of_attempt_requeue_context_allows_retired_predecessor_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "authority"
    launch = runner._production_shaped_launch_for_test(directory=str(base))
    launch = dataclasses.replace(
        launch,
        resources=dataclasses.replace(launch.resources, max_requeues_per_task=2),
    )
    claim_bytes = b"fresh-claim\n"
    receipt_bytes = b"fresh-receipt\n"
    fixture_authorization = runner._fixture_authorized_task_for_test(directory=str(base))
    attempt_id = "17_00000000000000000000-r00000000000000000001-j29"
    authorization = dataclasses.replace(
        fixture_authorization,
        launch=launch,
        restart_count=1,
        attempt_id=attempt_id,
        attempt_directory=os.path.join(
            launch.paths.attempt_root,
            fixture_authorization.task.wave,
            (f"{fixture_authorization.task.task_index:020d}-{fixture_authorization.task.scientific_identity_sha256}"),
            attempt_id,
        ),
        submission_claim_sha256=hashlib.sha256(claim_bytes).hexdigest(),
        submission_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
    )
    ledger_root = _create_private_ledger(launch)
    launch_name = f"{launch.launch_sha256}.json"
    for path, payload in (
        (ledger_root / "claims" / launch_name, claim_bytes),
        (ledger_root / "receipts" / launch_name, receipt_bytes),
    ):
        path.write_bytes(payload)
        path.chmod(0o600)
    name, permit_bytes, result_bytes = _restart_permit_records(
        launch,
        receipt_sha256=authorization.submission_receipt_sha256,
    )
    for path, payload in (
        (ledger_root / "requeue-permits" / name, permit_bytes),
        (ledger_root / "requeue-results" / name, result_bytes),
    ):
        path.write_bytes(payload)
        path.chmod(0o600)
    monkeypatch.setattr(runner, "_parse_submission_claim", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        runner,
        "_parse_submission_receipt",
        lambda *args, **kwargs: {"outcome": "accepted", "array_job_id": "17"},
    )
    monkeypatch.setattr(
        runner,
        "_validate_slurm_execution_environment",
        lambda *args, **kwargs: ("17", 0, "29", 1),
    )
    predecessor_manifest = Path(authorization.task_directory) / "checkpoint.00000000000000000001.manifest.json"
    assert not predecessor_manifest.exists()

    handles = runner._open_ledger(launch, exclusive=False)
    try:
        runner._revalidate_requeue_context_with_handles(authorization, handles)
    finally:
        runner._close_ledger(handles)


def test_rejected_predecessor_result_blocks_before_retired_manifest_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    launch = dataclasses.replace(
        launch,
        resources=dataclasses.replace(launch.resources, max_requeues_per_task=2),
    )
    ledger_root = _create_private_ledger(launch)
    receipt_sha256 = "b" * 64
    name, permit_bytes, result_bytes = _restart_permit_records(
        launch,
        receipt_sha256=receipt_sha256,
        outcome="rejected",
    )
    for path, payload in (
        (ledger_root / "requeue-permits" / name, permit_bytes),
        (ledger_root / "requeue-results" / name, result_bytes),
    ):
        path.write_bytes(payload)
        path.chmod(0o600)
    monkeypatch.setattr(runner, "_read_regular_file", lambda *args, **kwargs: _unexpected_effect())

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_restart_permit(
            launch,
            receipt_sha256=receipt_sha256,
            task=launch.ordered_tasks[0],
            array_job_id="17",
            array_position=0,
            restart_count=1,
        )
    assert caught.value.exit_code == 77


def test_requeue_named_ledger_swap_is_caught_before_scontrol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "authority"
    launch = runner._production_shaped_launch_for_test(directory=str(base))
    launch = dataclasses.replace(
        launch,
        resources=dataclasses.replace(launch.resources, max_requeues_per_task=2),
    )
    authorization = dataclasses.replace(
        runner._fixture_authorized_task_for_test(directory=str(base)),
        launch=launch,
    )
    ledger_root = _create_private_ledger(launch)
    manifest_path = Path(authorization.task_directory) / "checkpoint.00000000000000000001.manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest_path.write_bytes(b"synthetic-checkpoint-manifest\n")
    manifest_path.chmod(0o600)
    install_claim = runner._install_claim

    monkeypatch.setattr(runner, "_revalidate_requeue_context", lambda selected: None)
    monkeypatch.setattr(runner, "_revalidate_requeue_context_with_handles", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_revalidate_loaded_launch_runtime", lambda launch: None)
    monkeypatch.setattr(runner, "_validate_argv_path_limits", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_validate_scheduler_tool_file", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_run_bounded_process", lambda *args, **kwargs: _unexpected_effect())

    def install_then_replace(directory: int, name: str, payload: bytes, *, parent_path: str) -> None:
        install_claim(directory, name, payload, parent_path=parent_path)
        permits = ledger_root / "requeue-permits"
        permits.rename(ledger_root / "requeue-permits.displaced")
        permits.mkdir(mode=0o700)
        permits.chmod(0o700)

    monkeypatch.setattr(runner, "_install_claim", install_then_replace)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._submit_requeue(
            authorization,
            generation=1,
            checkpoint_manifest_path=str(manifest_path),
        )
    assert caught.value.exit_code == 76


def test_restart_permit_recomputes_result_classification(tmp_path: Path) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    resources = dataclasses.replace(
        launch.resources,
        max_requeues_per_task=2,
    )
    launch = dataclasses.replace(launch, resources=resources)
    ledger_root = _create_private_ledger(launch)
    task = launch.ordered_tasks[0]
    receipt_sha256 = "b" * 64
    array_job_id = "17"
    restart_count = 1
    argv = (launch.resources.scontrol_executable, "requeue", "17_0")
    name = f"{launch.launch_sha256}-p{0:020d}-r{0:020d}-to-{restart_count:020d}.json"
    permit_bytes = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-requeue-permit@1",
            "launch_sha256": launch.launch_sha256,
            "submission_receipt_sha256": receipt_sha256,
            "scientific_identity_sha256": task.scientific_identity_sha256,
            "array_job_id": array_job_id,
            "array_position": 0,
            "slurm_job_id": "29",
            "current_restart_count": 0,
            "target_restart_count": 1,
            "retry_cap": 2,
            "generation": 1,
            "checkpoint_manifest_path": str(
                Path(launch.paths.task_root)
                / task.relative_task_directory
                / "checkpoint.00000000000000000001.manifest.json"
            ),
            "checkpoint_manifest_sha256": "c" * 64,
            "scontrol_argv": list(argv),
            "scontrol_argv_sha256": runner._argv_digest(
                argv,
                profile="tetris-pre-one-cell-scontrol-argv@1",
            ),
        }
    )
    permit_path = ledger_root / "requeue-permits" / name
    permit_path.write_bytes(permit_bytes)
    permit_path.chmod(0o600)
    contradictory_result = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-requeue-result@1",
            "permit_sha256": hashlib.sha256(permit_bytes).hexdigest(),
            "outcome": "accepted",
            "returncode": 1,
            "stdout_hex": "00",
            "stdout_overflow": False,
            "stderr_hex": "72656675736564",
            "stderr_overflow": False,
        }
    )
    result_path = ledger_root / "requeue-results" / name
    result_path.write_bytes(contradictory_result)
    result_path.chmod(0o600)

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_restart_permit(
            launch,
            receipt_sha256=receipt_sha256,
            task=task,
            array_job_id=array_job_id,
            array_position=0,
            restart_count=restart_count,
        )
    assert caught.value.exit_code == 76


def _submission_reconciliation_record(
    *,
    outcome: str = "accepted",
    array_job_id: str | None = "4294967295",
    receipt: bool = True,
) -> dict[str, object]:
    commit = "1" * 40
    launch_ref = _file_reference(
        commit,
        "authorizations/pre-one-cell-discovery-v1/launches/f0-0001/launch.json",
        b"synthetic-launch\n",
    )
    launch_sha256 = str(launch_ref["sha256"])
    submission_prefix = f"authorizations/pre-one-cell-discovery-v1/submissions/{launch_sha256}"
    return {
        "profile": "tetris-pre-one-cell-submission-reconciliation@1",
        "launch": launch_ref,
        "claim": _file_reference(commit, f"{submission_prefix}/claim.json", b"synthetic-claim\n"),
        "receipt": (
            _file_reference(commit, f"{submission_prefix}/receipt.json", b"synthetic-receipt\n") if receipt else None
        ),
        "resolved_outcome": outcome,
        "resolved_array_job_id": array_job_id,
        "evidence": [
            _file_reference(commit, "evidence/scheduler-accounting.json", b"accounting\n"),
            _file_reference(commit, "evidence/operator-review.json", b"review\n"),
        ],
        "automatic_replay_permitted": False,
        "additional_initial_sbatch_permitted": False,
        "superseding_launch_required": True,
        "approved_by": "campaign-owner",
        "approved_at_utc": "2026-07-16T12:34:56Z",
    }


def _submission_reconciliation_reference(
    record: dict[str, object],
    payload: bytes,
) -> dict[str, object]:
    launch = record["launch"]
    assert type(launch) is dict
    return _file_reference(
        "2" * 40,
        (f"authorizations/pre-one-cell-discovery-v1/reconciliations/{launch['sha256']}-0001/reconciliation.json"),
        payload,
    )


@pytest.mark.parametrize(
    ("outcome", "array_job_id", "receipt"),
    (
        ("accepted", "4294967295", True),
        ("rejected", None, True),
        ("unknown", None, False),
    ),
)
def test_private_submission_reconciliation_parser_accepts_exact_evidence_only_record(
    outcome: str,
    array_job_id: str | None,
    receipt: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _submission_reconciliation_record(
        outcome=outcome,
        array_job_id=array_job_id,
        receipt=receipt,
    )
    payload = _canonical_json(record)
    reference = _submission_reconciliation_reference(record, payload)

    def unexpected_ledger_effect(*args: object, **kwargs: object) -> typing.NoReturn:
        del args, kwargs
        raise AssertionError("reconciliation evidence parser touched the private ledger")

    for name in ("_open_ledger", "_read_ledger_member", "_install_claim", "_install_link_record"):
        monkeypatch.setattr(runner, name, unexpected_ledger_effect)
    before = tuple(tmp_path.iterdir())
    parsed = runner._parse_submission_reconciliation(
        payload,
        reconciliation_reference=reference,
    )
    assert tuple(tmp_path.iterdir()) == before
    assert parsed["resolved_outcome"] == outcome
    assert parsed["resolved_array_job_id"] == array_job_id
    assert (parsed["receipt"] is None) is (not receipt)
    assert "_parse_submission_reconciliation" not in runner.__all__


def test_submission_reconciliation_refuses_hostile_schema_paths_and_policy() -> None:
    base = _submission_reconciliation_record()

    def cloned() -> dict[str, object]:
        selected = json.loads(json.dumps(base))
        assert type(selected) is dict
        return selected

    hostile: list[dict[str, object]] = []

    extra = cloned()
    extra["unexpected"] = False
    hostile.append(extra)
    missing = cloned()
    del missing["approved_by"]
    hostile.append(missing)
    wrong_profile = cloned()
    wrong_profile["profile"] = "tetris-pre-one-cell-submission-reconciliation-fixture@1"
    hostile.append(wrong_profile)

    wrong_launch = cloned()
    assert type(wrong_launch["launch"]) is dict
    wrong_launch["launch"]["path"] = "authorizations/pre-one-cell-discovery-v1/launches/not-a-lane-0001/launch.json"
    hostile.append(wrong_launch)
    wrong_claim = cloned()
    assert type(wrong_claim["claim"]) is dict
    wrong_claim["claim"]["path"] = f"authorizations/pre-one-cell-discovery-v1/submissions/{'f' * 64}/claim.json"
    hostile.append(wrong_claim)
    wrong_receipt = cloned()
    assert type(wrong_receipt["receipt"]) is dict
    wrong_receipt["receipt"]["path"] = "evidence/receipt.json"
    hostile.append(wrong_receipt)

    no_evidence = cloned()
    no_evidence["evidence"] = []
    hostile.append(no_evidence)
    duplicate_evidence = cloned()
    assert type(duplicate_evidence["evidence"]) is list
    duplicate_evidence["evidence"].append(duplicate_evidence["evidence"][0])
    hostile.append(duplicate_evidence)
    excess_evidence = cloned()
    excess_evidence["evidence"] = [
        _file_reference("1" * 40, f"evidence/item-{index:03d}.json", f"{index}\n".encode()) for index in range(129)
    ]
    hostile.append(excess_evidence)

    invalid_outcome = cloned()
    invalid_outcome["resolved_outcome"] = "complete"
    hostile.append(invalid_outcome)
    accepted_without_job = cloned()
    accepted_without_job["resolved_array_job_id"] = None
    hostile.append(accepted_without_job)
    rejected_with_job = cloned()
    rejected_with_job["resolved_outcome"] = "rejected"
    rejected_with_job["resolved_array_job_id"] = "17"
    hostile.append(rejected_with_job)
    noncanonical_job = cloned()
    noncanonical_job["resolved_array_job_id"] = "017"
    hostile.append(noncanonical_job)

    replay = cloned()
    replay["automatic_replay_permitted"] = True
    hostile.append(replay)
    another_initial = cloned()
    another_initial["additional_initial_sbatch_permitted"] = True
    hostile.append(another_initial)
    no_superseding = cloned()
    no_superseding["superseding_launch_required"] = False
    hostile.append(no_superseding)
    boolean_alias = cloned()
    boolean_alias["automatic_replay_permitted"] = 0
    hostile.append(boolean_alias)
    missing_approver = cloned()
    missing_approver["approved_by"] = ""
    hostile.append(missing_approver)
    noncanonical_timestamp = cloned()
    noncanonical_timestamp["approved_at_utc"] = "2026-07-16T12:34:56+00:00"
    hostile.append(noncanonical_timestamp)

    for record in hostile:
        payload = _canonical_json(record)
        reference = _submission_reconciliation_reference(record, payload)
        with pytest.raises(
            (runner.OneCellRunnerValidationError, runner.OneCellRunnerAuthorizationError, TypeError, ValueError)
        ):
            runner._parse_submission_reconciliation(
                payload,
                reconciliation_reference=reference,
            )


def test_submission_reconciliation_refuses_wrong_self_reference_and_noncanonical_bytes() -> None:
    record = _submission_reconciliation_record()
    payload = _canonical_json(record)
    exact_reference = _submission_reconciliation_reference(record, payload)

    for changes in (
        {"path": (f"authorizations/pre-one-cell-discovery-v1/reconciliations/{'f' * 64}-0001/reconciliation.json")},
        {"sha256": "f" * 64},
        {"size_bytes": len(payload) + 1},
    ):
        reference = {**exact_reference, **changes}
        with pytest.raises(runner.OneCellRunnerAuthorizationError):
            runner._parse_submission_reconciliation(
                payload,
                reconciliation_reference=reference,
            )

    for hostile_payload in (
        payload[:-1],
        payload + b"\n",
        json.dumps(record, ensure_ascii=False).encode("utf-8") + b"\n",
        b'{"profile":"x","profile":"y"}\n',
    ):
        reference = _submission_reconciliation_reference(record, hostile_payload)
        with pytest.raises(runner.OneCellRunnerValidationError):
            runner._parse_submission_reconciliation(
                hostile_payload,
                reconciliation_reference=reference,
            )

    oversized = _submission_reconciliation_record()
    oversized["evidence"] = [
        _file_reference(
            "1" * 40,
            f"evidence/{index:03d}-{'x' * 600}.json",
            f"{index}\n".encode(),
        )
        for index in range(128)
    ]
    oversized_payload = _canonical_json(oversized)
    assert len(oversized_payload) > 64 << 10
    with pytest.raises(runner.OneCellRunnerValidationError):
        runner._parse_submission_reconciliation(
            oversized_payload,
            reconciliation_reference=_submission_reconciliation_reference(oversized, oversized_payload),
        )


def test_valid_requeue_result_accepts_exact_empty_captured_streams() -> None:
    permit_bytes = b"synthetic-permit\n"
    payload = _canonical_json(
        {
            "profile": "tetris-pre-one-cell-requeue-result@1",
            "permit_sha256": hashlib.sha256(permit_bytes).hexdigest(),
            "outcome": "accepted",
            "returncode": 0,
            "stdout_hex": "",
            "stdout_overflow": False,
            "stderr_hex": "",
            "stderr_overflow": False,
        }
    )
    parsed = runner._parse_requeue_result_record(
        payload,
        permit_bytes=permit_bytes,
    )
    assert parsed["outcome"] == "accepted"


def test_timed_out_requeue_result_round_trips_as_unknown() -> None:
    permit_bytes = b"synthetic-permit\n"
    process = runner._ProcessResult(
        0,
        b"",
        False,
        b"",
        False,
        True,
        False,
    )
    outcome, job_id = runner._classify_scheduler_result(
        result=process,
        submission=False,
    )
    assert (outcome, job_id) == ("unknown", None)
    payload = runner._requeue_result_bytes(
        permit_sha256=hashlib.sha256(permit_bytes).hexdigest(),
        result=process,
        outcome=outcome,
    )
    parsed = runner._parse_requeue_result_record(
        payload,
        permit_bytes=permit_bytes,
    )
    assert parsed["outcome"] == "unknown"


def test_requeue_freshly_revalidates_receipt_and_slurm_mapping_before_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "authority"
    launch = runner._production_shaped_launch_for_test(directory=str(base))
    launch = dataclasses.replace(
        launch,
        resources=dataclasses.replace(
            launch.resources,
            max_requeues_per_task=2,
        ),
    )
    fixture_authorization = runner._fixture_authorized_task_for_test(directory=str(base))
    claim_bytes = b"fresh-claim\n"
    receipt_bytes = b"fresh-receipt\n"
    authorization = dataclasses.replace(
        fixture_authorization,
        launch=launch,
        submission_claim_sha256=hashlib.sha256(claim_bytes).hexdigest(),
        submission_receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
    )
    handles = types.SimpleNamespace(claims=1, receipts=2)

    def read_member(directory: int, name: str, *, parent_path: str, label: str) -> bytes:
        del name, parent_path
        if directory == handles.claims and label == "submission claim":
            return claim_bytes
        if directory == handles.receipts and label == "submission receipt":
            return receipt_bytes
        raise AssertionError((directory, label))

    monkeypatch.setattr(runner, "_read_ledger_member", read_member)
    monkeypatch.setattr(runner, "_parse_submission_claim", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        runner,
        "_parse_submission_receipt",
        lambda *args, **kwargs: {"outcome": "accepted", "array_job_id": "17"},
    )
    monkeypatch.setattr(
        runner,
        "_validate_slurm_execution_environment",
        lambda *args, **kwargs: ("17", 1, "29", 0),
    )
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._revalidate_requeue_context_with_handles(authorization, handles)
    assert caught.value.exit_code == 76

    sentinel = runner.OneCellRunnerAuthorizationError(
        "fresh requeue receipt changed",
        exit_code=76,
    )

    def reject_context(value: object) -> typing.NoReturn:
        assert value == authorization
        raise sentinel

    monkeypatch.setattr(runner, "_revalidate_requeue_context", reject_context)
    monkeypatch.setattr(runner, "_revalidate_loaded_launch_runtime", lambda launch: None)
    monkeypatch.setattr(
        runner,
        "_run_bounded_process",
        lambda *args, **kwargs: _unexpected_effect(),
    )
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as submitted:
        runner._submit_requeue(
            authorization,
            generation=1,
            checkpoint_manifest_path=str(
                Path(authorization.task_directory) / "checkpoint.00000000000000000001.manifest.json"
            ),
        )
    assert submitted.value is sentinel
    with pytest.raises(TypeError):
        runner._classify_scheduler_result_for_test(
            returncode=0,
            stdout=bytearray(),  # type: ignore[arg-type]
            stderr=b"",
            submission=True,
        )


def test_launch_task_exact_types_digest_and_path_are_enforced() -> None:
    task = _launch_task()
    assert task.array_position == 0
    assert task.relative_task_directory.endswith(task.scientific_identity_sha256)

    for changes, error in (
        ({"array_position": False}, TypeError),
        ({"scientific_identity_bytes": bytearray(b"x")}, TypeError),
        ({"scientific_identity_sha256": _SHA256_A}, ValueError),
        ({"relative_task_directory": "f0/../escape"}, ValueError),
        ({"relative_task_directory": "f0/0-short"}, ValueError),
    ):
        with pytest.raises(error):
            _launch_task(**changes)


def test_resource_envelope_freezes_tools_environment_and_ranges() -> None:
    resources = _resource_envelope()
    assert resources.scheduler_environment == (("LANG", "C"), ("LC_ALL", "C"))

    reversed_scheduler = tuple(reversed(resources.scheduler_environment))
    wrong_threading = tuple(
        (key, "3" if key == "OMP_NUM_THREADS" else value) for key, value in resources.scientific_environment
    )
    for changes, error in (
        ({"wall_minutes": True}, TypeError),
        ({"wall_minutes": 16}, ValueError),
        ({"partition": "compute,fallback"}, ValueError),
        ({"signal_name": "SIGTERM"}, ValueError),
        ({"receipt_handshake_seconds": 59}, ValueError),
        ({"sbatch_executable_realpath": "/other/sbatch"}, ValueError),
        ({"sbatch_mode": 0o775}, ValueError),
        ({"sbatch_version": "sbatch synthetic"}, ValueError),
        ({"scheduler_environment": reversed_scheduler}, ValueError),
        ({"scheduler_environment": {"LANG": "C", "LC_ALL": "C"}}, TypeError),
        ({"scientific_environment": wrong_threading}, ValueError),
    ):
        with pytest.raises(error):
            _resource_envelope(**changes)


def test_runner_paths_freeze_sidecar_task_root_and_git_identity(tmp_path: Path) -> None:
    paths = _runner_paths(tmp_path)
    assert paths.runtime_python_bytes == paths.python_executable.encode() + b"\n"
    assert paths.task_root == str(Path(paths.campaign_root) / "private" / "tasks")

    for changes, error in (
        ({"runtime_python_file": str(tmp_path / "sidecar")}, ValueError),
        ({"runtime_python_bytes": b"/different/python\n"}, ValueError),
        ({"runtime_python_sha256": _SHA256_A}, ValueError),
        ({"python_executable_realpath": "/different/python"}, ValueError),
        ({"task_root": str(tmp_path / "tasks")}, ValueError),
        ({"campaign_root": str(tmp_path / "bad" / "..")}, ValueError),
        ({"git_executable_realpath": "/other/git"}, ValueError),
        ({"git_mode": 0o777}, ValueError),
    ):
        with pytest.raises(error):
            _runner_paths(tmp_path, **changes)


def test_runtime_authorization_directory_is_separate_from_git_checkout(
    tmp_path: Path,
) -> None:
    launch = runner._parse_launch_wire(
        _fixture_launch_bytes(
            profile="tetris-pre-one-cell-launch-fixture@1",
        )
    )
    paths = dict(launch["paths"])
    checkout = str(tmp_path / "coordinator-checkout")
    readback_root = str(tmp_path / "runtime-authorities")
    authorization = str(Path(readback_root) / "launch-f0")
    campaign_root = str(tmp_path / "campaign")
    private_root = Path(campaign_root) / "private"
    environment_root = str(tmp_path / "environment")
    python_executable = str(Path(environment_root) / "bin" / "python")
    runtime_bytes = os.fsencode(python_executable) + b"\n"
    runtime = dict(launch["runtime_python"])
    runtime.update(
        {
            "sidecar_path": f"{authorization}/runtime-python.path",
            "sidecar_bytes_hex": runtime_bytes.hex(),
            "sidecar_sha256": hashlib.sha256(runtime_bytes).hexdigest(),
            "sidecar_size_bytes": len(runtime_bytes),
            "executable_path": python_executable,
            "executable_realpath": python_executable,
        }
    )
    launch["runtime_python"] = runtime
    paths.update(
        {
            "campaign_root": campaign_root,
            "authorization_checkout": checkout,
            "authorization_directory": authorization,
            "runtime_python_file": f"{authorization}/runtime-python.path",
            "python_executable": python_executable,
            "task_root": str(private_root / "tasks"),
            "attempt_root": str(private_root / "attempts"),
            "log_root": str(private_root / "logs"),
            "cache_root": str(private_root / "cache"),
            "temporary_root": str(private_root / "tmp"),
            "submission_ledger_root": str(private_root / "submission-ledger"),
            "submission_ledger_lock": str(private_root / "submission-ledger" / "ledger.lock"),
            "authorized_run_directory": str(private_root / "run"),
            "stdout_template": str(private_root / "logs" / "slurm-%A_%a.out"),
            "stderr_template": str(private_root / "logs" / "slurm-%A_%a.err"),
        }
    )
    launch["paths"] = paths
    deployment_paths = {
        "article_checkout": str(tmp_path / "article-checkout"),
        "software_checkout": str(tmp_path / "software-checkout"),
        "coordinator_checkout": checkout,
        "campaign_root": paths["campaign_root"],
        "environment_root": environment_root,
        "python_executable": paths["python_executable"],
        "private_task_root": paths["task_root"],
        "attempt_root": paths["attempt_root"],
        "log_root": paths["log_root"],
        "cache_root": paths["cache_root"],
        "temporary_root": paths["temporary_root"],
        "submission_ledger_root": paths["submission_ledger_root"],
        "submission_ledger_lock": paths["submission_ledger_lock"],
        "authorized_run_directory": paths["authorized_run_directory"],
        "batch_script": paths["batch_script"],
        "sbatch_executable": "/usr/bin/sbatch",
        "scontrol_executable": "/usr/bin/scontrol",
        "git_executable": paths["git_executable"],
    }
    deployment = {
        "paths": deployment_paths,
        "runtime_python": dict(runtime),
        "_parsed_tools": launch["_parsed_tools"],
        "coordinator_repository": {
            "authorization_readback_root": readback_root,
            "remote_url": paths["coordinator_remote_url"],
            "fetch_refspec": paths["coordinator_fetch_refspec"],
        },
    }
    selected = runner._paths_from_wires(
        launch,
        deployment,
        authorization_path=authorization,
        runtime_python_bytes=runtime_bytes,
    )
    assert selected.authorization_directory == authorization
    assert selected.authorization_checkout == checkout
    assert os.path.commonpath((authorization, checkout)) not in {
        authorization,
        checkout,
    }

    nested_paths = dict(paths)
    nested_authorization = f"{checkout}/runtime-authority"
    nested_paths.update(
        {
            "authorization_directory": nested_authorization,
            "runtime_python_file": f"{nested_authorization}/runtime-python.path",
        }
    )
    nested_launch = dict(launch)
    nested_launch["paths"] = nested_paths
    nested_deployment = dict(deployment)
    nested_deployment["coordinator_repository"] = {
        **deployment["coordinator_repository"],
        "authorization_readback_root": checkout,
    }
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._paths_from_wires(
            nested_launch,
            nested_deployment,
            authorization_path=nested_authorization,
            runtime_python_bytes=runtime_bytes,
        )
    assert caught.value.exit_code == 76


def test_loader_requires_local_ordered_tasks_equal_the_pushed_blob() -> None:
    source = inspect.getsource(runner._load_one_cell_launch_authority_impl)
    assert 'os.path.join(selected_path, "ordered-tasks.jsonl")' in source
    assert "local_ordered" in source
    assert "ordered_bytes" in source
    assert "local ordered task copy differs from pushed Git blob" in source


def test_inspection_rejects_stale_public_ordered_task_projection(tmp_path: Path) -> None:
    launch = runner._fixture_launch_authority_for_test(directory=str(tmp_path / "authority"))
    changed_task = dataclasses.replace(launch.ordered_tasks[0], role="changed-role")
    stale = dataclasses.replace(launch, ordered_tasks=(changed_task,))

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as listed:
        runner.list_one_cell_launch_tasks(launch=stale)
    assert listed.value.exit_code == 76
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as explained:
        runner.explain_one_cell_launch_task(launch=stale, array_position=0)
    assert explained.value.exit_code == 76


@pytest.mark.parametrize("limit_name", ("PC_NAME_MAX", "PC_PATH_MAX"))
def test_descriptor_reported_path_limits_refuse_before_directory_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
) -> None:
    root = tmp_path / "private-root"
    root.mkdir(mode=0o700)
    root_identity = (root.stat().st_dev, root.stat().st_ino)
    real_fpathconf = runner.os.fpathconf

    def bounded(descriptor: int, name: str) -> int:
        info = os.fstat(descriptor)
        if (info.st_dev, info.st_ino) == root_identity and name == limit_name:
            return 3 if name == "PC_NAME_MAX" else len(os.fsencode(root)) + 3
        return real_fpathconf(descriptor, name)

    monkeypatch.setattr(runner.os, "fpathconf", bounded)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._ensure_private_relative_directory(str(root), ("long-component",))
    assert caught.value.exit_code == 76
    assert tuple(root.iterdir()) == ()


def test_private_directory_creation_retains_and_rechecks_root_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "private-root"
    moved = tmp_path / "authorized-root-moved"
    root.mkdir(mode=0o700)
    real_mkdir = runner.os.mkdir
    swapped = False

    def swap_then_create(path: str, mode: int = 0o777, *, dir_fd: int | None = None) -> None:
        nonlocal swapped
        if not swapped and dir_fd is not None:
            swapped = True
            os.rename(root, moved)
            real_mkdir(root, 0o700)
        real_mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(runner.os, "mkdir", swap_then_create)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._ensure_private_relative_directory(str(root), ("wave", "task"))
    assert caught.value.exit_code == 76
    assert tuple(root.iterdir()) == ()
    assert (moved / "wave").is_dir()


def test_private_directory_creation_rechecks_retained_root_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "private-root"
    root.mkdir(mode=0o700)
    real_mkdir = runner.os.mkdir
    changed = False

    def chmod_root_then_create(path: str, mode: int = 0o777, *, dir_fd: int | None = None) -> None:
        nonlocal changed
        if not changed and dir_fd is not None:
            changed = True
            root.chmod(0o755)
        real_mkdir(path, mode, dir_fd=dir_fd)

    monkeypatch.setattr(runner.os, "mkdir", chmod_root_then_create)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._ensure_private_relative_directory(str(root), ("wave", "task"))
    assert caught.value.exit_code == 77


def test_private_directory_creation_classifies_symlink_child_as_integrity(tmp_path: Path) -> None:
    root = tmp_path / "private-root"
    target = tmp_path / "redirect-target"
    root.mkdir(mode=0o700)
    target.mkdir(mode=0o700)
    (root / "wave").symlink_to(target, target_is_directory=True)

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._ensure_private_relative_directory(str(root), ("wave", "task"))
    assert caught.value.exit_code == 76
    assert tuple(target.iterdir()) == ()


def test_ledger_reader_rejects_named_inode_swap_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "claims"
    parent.mkdir(mode=0o700)
    record = parent / "record.json"
    displaced = parent / "record.old"
    payload = b"stable-ledger-record\n"
    record.write_bytes(payload)
    record.chmod(0o600)
    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    real_read = runner.os.read
    swapped = False

    def swap_after_read(file_descriptor: int, size: int) -> bytes:
        nonlocal swapped
        chunk = real_read(file_descriptor, size)
        if chunk and not swapped:
            swapped = True
            os.rename(record, displaced)
            record.write_bytes(payload)
            record.chmod(0o600)
        return chunk

    monkeypatch.setattr(runner.os, "read", swap_after_read)
    try:
        with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
            runner._read_ledger_member(
                descriptor,
                record.name,
                parent_path=str(parent),
                label="submission claim",
            )
        assert caught.value.exit_code == 76
    finally:
        os.close(descriptor)


@pytest.mark.parametrize("reader", ("regular", "ledger"))
@pytest.mark.parametrize("mutation", ("chmod", "hardlink"))
def test_stable_file_readers_recheck_final_private_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader: str,
    mutation: str,
) -> None:
    parent = tmp_path / "records"
    parent.mkdir(mode=0o700)
    record = parent / "record.json"
    record.write_bytes(b"stable-private-record\n")
    record.chmod(0o600)
    sibling = parent / "record.link"
    real_read = runner.os.read
    mutated = False

    def mutate_after_read(descriptor: int, size: int) -> bytes:
        nonlocal mutated
        chunk = real_read(descriptor, size)
        if chunk and not mutated:
            mutated = True
            if mutation == "chmod":
                record.chmod(0o640)
            else:
                os.link(record, sibling)
        return chunk

    monkeypatch.setattr(runner.os, "read", mutate_after_read)
    if reader == "regular":
        with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
            runner._read_regular_file(
                str(record),
                label="private authority",
                maximum=1024,
                expected_mode=0o600,
                expected_uid=os.geteuid(),
            )
    else:
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
                runner._read_ledger_member(
                    directory,
                    record.name,
                    parent_path=str(parent),
                    label="private ledger record",
                )
        finally:
            os.close(directory)
    assert mutated is True
    assert caught.value.exit_code == 76


def test_low_ledger_name_limit_refuses_before_claim_or_scheduler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    ledger_root = _create_private_ledger(launch)
    claims = ledger_root / "claims"
    claims_identity = (claims.stat().st_dev, claims.stat().st_ino)
    real_fpathconf = runner.os.fpathconf

    def bounded(descriptor: int, name: str) -> int:
        info = os.fstat(descriptor)
        if (info.st_dev, info.st_ino) == claims_identity and name == "PC_NAME_MAX":
            return 16
        return real_fpathconf(descriptor, name)

    monkeypatch.setattr(runner.os, "fpathconf", bounded)
    monkeypatch.setattr(runner, "_revalidate_loaded_launch_runtime", lambda launch: None)
    monkeypatch.setattr(runner, "_validate_argv_path_limits", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_submission_claim_bytes", lambda *args, **kwargs: b"claim\n")
    monkeypatch.setattr(runner, "_run_bounded_process", lambda *args, **kwargs: _unexpected_effect())

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._submit_one_cell_launch_impl(launch=launch)
    assert caught.value.exit_code == 76
    assert tuple(claims.iterdir()) == ()


@pytest.mark.parametrize("limit_name", ("PC_NAME_MAX", "PC_PATH_MAX"))
def test_submission_preflights_receipt_temporary_name_before_claim_or_scheduler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    ledger_root = _create_private_ledger(launch)
    claims = ledger_root / "claims"
    receipts = ledger_root / "receipts"
    receipts_identity = (receipts.stat().st_dev, receipts.stat().st_ino)
    record_name = f"{launch.launch_sha256}.json"
    temporary_name = f".{record_name}.{'0' * 32}.tmp"
    if limit_name == "PC_NAME_MAX":
        selected_limit = len(os.fsencode(record_name)) + 1
        assert len(os.fsencode(temporary_name)) > selected_limit
    else:
        selected_limit = len(os.fsencode(receipts / record_name)) + 1
        assert len(os.fsencode(receipts / temporary_name)) > selected_limit
    real_fpathconf = runner.os.fpathconf
    targeted_calls = 0

    def bounded(descriptor: int, name: str) -> int:
        nonlocal targeted_calls
        info = os.fstat(descriptor)
        if (info.st_dev, info.st_ino) == receipts_identity and name == limit_name:
            targeted_calls += 1
            return selected_limit
        return real_fpathconf(descriptor, name)

    monkeypatch.setattr(runner.os, "fpathconf", bounded)
    monkeypatch.setattr(runner, "_revalidate_loaded_launch_runtime", lambda launch: None)
    monkeypatch.setattr(runner, "_validate_argv_path_limits", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_submission_claim_bytes", lambda *args, **kwargs: b"claim\n")
    monkeypatch.setattr(runner, "_run_bounded_process", lambda *args, **kwargs: _unexpected_effect())

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._submit_one_cell_launch_impl(launch=launch)
    assert caught.value.exit_code == 76
    assert targeted_calls >= 1
    assert tuple(claims.iterdir()) == ()
    assert tuple(receipts.iterdir()) == ()


@pytest.mark.parametrize("limit_name", ("PC_NAME_MAX", "PC_PATH_MAX"))
def test_requeue_preflights_result_temporary_name_before_permit_or_scheduler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
) -> None:
    base = tmp_path / "authority"
    launch = runner._production_shaped_launch_for_test(directory=str(base))
    launch = dataclasses.replace(
        launch,
        resources=dataclasses.replace(launch.resources, max_requeues_per_task=2),
    )
    authorization = dataclasses.replace(
        runner._fixture_authorized_task_for_test(directory=str(base)),
        launch=launch,
    )
    ledger_root = _create_private_ledger(launch)
    permits = ledger_root / "requeue-permits"
    results = ledger_root / "requeue-results"
    results_identity = (results.stat().st_dev, results.stat().st_ino)
    target = authorization.restart_count + 1
    record_name = (
        f"{launch.launch_sha256}-p{authorization.array_position:020d}"
        f"-r{authorization.restart_count:020d}-to-{target:020d}.json"
    )
    temporary_name = f".{record_name}.{'0' * 32}.tmp"
    if limit_name == "PC_NAME_MAX":
        selected_limit = len(os.fsencode(record_name)) + 1
        assert len(os.fsencode(temporary_name)) > selected_limit
    else:
        selected_limit = len(os.fsencode(results / record_name)) + 1
        assert len(os.fsencode(results / temporary_name)) > selected_limit
    real_fpathconf = runner.os.fpathconf
    targeted_calls = 0

    def bounded(descriptor: int, name: str) -> int:
        nonlocal targeted_calls
        info = os.fstat(descriptor)
        if (info.st_dev, info.st_ino) == results_identity and name == limit_name:
            targeted_calls += 1
            return selected_limit
        return real_fpathconf(descriptor, name)

    manifest_path = Path(authorization.task_directory) / "checkpoint.00000000000000000001.manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest_path.write_bytes(b"synthetic-checkpoint-manifest\n")
    manifest_path.chmod(0o600)
    monkeypatch.setattr(runner.os, "fpathconf", bounded)
    monkeypatch.setattr(runner, "_revalidate_loaded_launch_runtime", lambda launch: None)
    monkeypatch.setattr(runner, "_revalidate_requeue_context", lambda selected: None)
    monkeypatch.setattr(runner, "_validate_argv_path_limits", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "_validate_scheduler_tool_file", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_run_bounded_process", lambda *args, **kwargs: _unexpected_effect())

    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._submit_requeue(
            authorization,
            generation=1,
            checkpoint_manifest_path=str(manifest_path),
        )
    assert caught.value.exit_code == 76
    assert targeted_calls >= 1
    assert tuple(permits.iterdir()) == ()
    assert tuple(results.iterdir()) == ()


def test_argv_filesystem_limit_refuses_before_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference = tmp_path / "reference"
    reference.mkdir(mode=0o700)
    identity = (reference.stat().st_dev, reference.stat().st_ino)
    real_fpathconf = runner.os.fpathconf

    def bounded(descriptor: int, name: str) -> int:
        info = os.fstat(descriptor)
        if (info.st_dev, info.st_ino) == identity and name == "PC_PATH_MAX":
            return 8
        return real_fpathconf(descriptor, name)

    monkeypatch.setattr(runner.os, "fpathconf", bounded)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_argv_path_limits(
            ("/usr/bin/sbatch", "--parsable"),
            reference_directories=(str(reference),),
            label="scheduler argv",
        )
    assert caught.value.exit_code == 76


def test_mutable_and_authority_roots_must_be_pairwise_isolated(tmp_path: Path) -> None:
    root = tmp_path / "trusted"
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._require_pairwise_isolated_roots(
            (
                ("coordinator checkout", str(root / "coordinator")),
                ("campaign root", str(root / "coordinator" / "campaign")),
            )
        )
    assert caught.value.exit_code == 76


def test_deployed_batch_root_requires_trusted_nonwritable_ancestry(tmp_path: Path) -> None:
    trusted = tmp_path / "trusted"
    deployed = trusted / "deployed"
    trusted.mkdir(mode=0o700)
    deployed.mkdir(mode=0o700)
    deployed.chmod(0o777)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._validate_trusted_directory_chain(
            str(deployed),
            trusted_base=str(trusted),
            allowed_uids=frozenset({os.geteuid()}),
            label="deployed batch root",
        )
    assert caught.value.exit_code == 77
    assert '("deployed batch root", os.path.dirname(str(deployment_paths["batch_script"])))' in inspect.getsource(
        runner._validate_deployment_path_policy
    )


def test_deployed_batch_file_refuses_group_world_write(tmp_path: Path) -> None:
    deployed = tmp_path / "deployed"
    deployed.mkdir(mode=0o700)
    batch = deployed / "run_pre_one_cell.sbatch"
    batch.write_bytes(b"#!/bin/sh\nexit 99\n")
    batch.chmod(0o666)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._read_bound_runtime_file(
            str(batch),
            label="deployed batch script",
            maximum=1024,
            expected_uid=os.geteuid(),
            forbid_group_world_write=True,
        )
    assert caught.value.exit_code == 77
    assert "forbid_group_world_write=True" in inspect.getsource(runner._validate_live_batch_script)


def test_stable_handshake_and_restart_schema_errors_map_to_integrity_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch = runner._production_shaped_launch_for_test(directory=str(tmp_path / "authority"))
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as handshake:
        runner._parse_stable_submission_handshake(b"{}\n", b"{}\n", launch=launch)
    assert handshake.value.exit_code == 76

    def malformed_permit(*args: object, **kwargs: object) -> typing.NoReturn:
        del args, kwargs
        raise runner.OneCellRunnerValidationError("malformed durable permit")

    monkeypatch.setattr(runner, "_validate_restart_permit", malformed_permit)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as permit:
        runner._validate_restart_permit_integrity(
            launch,
            receipt_sha256="a" * 64,
            task=launch.ordered_tasks[0],
            array_job_id="17",
            array_position=0,
            restart_count=0,
        )
    assert permit.value.exit_code == 76


def test_symlinked_stable_files_are_integrity_not_absence(
    tmp_path: Path,
) -> None:
    parent = tmp_path / "records"
    parent.mkdir(mode=0o700)
    target = parent / "target.json"
    target.write_bytes(b"{}\n")
    target.chmod(0o600)
    linked = parent / "linked.json"
    linked.symlink_to(target.name)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as regular:
        runner._read_regular_file(str(linked), label="authority", maximum=1024)
    assert regular.value.exit_code == 76
    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(runner.OneCellRunnerAuthorizationError) as ledger:
            runner._read_ledger_member(
                descriptor,
                linked.name,
                parent_path=str(parent),
                label="ledger record",
            )
        assert ledger.value.exit_code == 76
    finally:
        os.close(descriptor)


@pytest.mark.parametrize("vanish_at", (1, 2))
def test_regular_reader_maps_named_identity_vanish_to_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    vanish_at: int,
) -> None:
    parent = tmp_path / "records"
    parent.mkdir(mode=0o700)
    record = parent / "record.json"
    record.write_bytes(b"stable-authority\n")
    record.chmod(0o600)
    real_stat = runner.os.stat
    named_calls = 0

    def vanish(path: object, *args: object, **kwargs: object) -> os.stat_result:
        nonlocal named_calls
        if path == record.name and kwargs.get("dir_fd") is not None and kwargs.get("follow_symlinks") is False:
            named_calls += 1
            if named_calls == vanish_at:
                raise FileNotFoundError(errno.ENOENT, "injected named identity vanish")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(runner.os, "stat", vanish)
    with pytest.raises(runner.OneCellRunnerAuthorizationError) as caught:
        runner._read_regular_file(str(record), label="authority", maximum=1024)
    assert caught.value.exit_code == 76
    assert named_calls == vanish_at


def test_slice8b_prerequisite_commits_are_runtime_pinned() -> None:
    software_source = inspect.getsource(runner._validate_software_checkout_and_batch)
    loader_source = inspect.getsource(runner._load_one_cell_launch_authority_impl)
    assert "_SLICE_8B_SOFTWARE_PARENT" in software_source
    assert "_SLICE_8B_COORDINATOR_AUTHORITY" in loader_source
    assert runner._SLICE_8B_SOFTWARE_PARENT == "b33cc0191298d80f0bdc944a3a5e444952873e37"
    assert runner._SLICE_8B_COORDINATOR_AUTHORITY == "087cdaf8d8444de7d9548bc1c97ca42f221cef27"


def test_runtime_python_sidecar_accepts_4096_and_rejects_4097_bytes(tmp_path: Path) -> None:
    def python_path(final_component_size: int) -> str:
        return "/" + ("a" * 254 + "/") * 16 + "b" * final_component_size

    accepted_path = python_path(14)
    accepted_bytes = os.fsencode(accepted_path) + b"\n"
    assert len(accepted_bytes) == 4096
    accepted = _runner_paths(
        tmp_path,
        python_executable=accepted_path,
        python_executable_realpath=accepted_path,
        runtime_python_bytes=accepted_bytes,
        runtime_python_sha256=hashlib.sha256(accepted_bytes).hexdigest(),
    )
    assert accepted.runtime_python_bytes == accepted_bytes

    rejected_path = python_path(15)
    rejected_bytes = os.fsencode(rejected_path) + b"\n"
    assert len(rejected_bytes) == 4097
    with pytest.raises(ValueError):
        _runner_paths(
            tmp_path,
            python_executable=rejected_path,
            python_executable_realpath=rejected_path,
            runtime_python_bytes=rejected_bytes,
            runtime_python_sha256=hashlib.sha256(rejected_bytes).hexdigest(),
        )


def _runner_outcome(**changes: object) -> runner.OneCellRunnerOutcome:
    values: dict[str, object] = {
        "disposition": "complete",
        "array_position": 0,
        "task_map_id": "f0-map",
        "task_index": 0,
        "attempt_id": "17_00000000000000000000-r00000000000000000000-j29",
        "task_directory": "/campaign/private/tasks/f0/task",
        "manifest_path": "/campaign/private/tasks/f0/task/final.manifest.json",
        "generation": 0,
        "checkpoint_count": 512,
        "snapshot_count": 16,
        "used_fallback": False,
    }
    values.update(changes)
    return runner.OneCellRunnerOutcome(**values)  # type: ignore[arg-type]


def test_runner_outcome_conditional_invariants_are_exact() -> None:
    assert _runner_outcome().disposition == "complete"
    assert _runner_outcome(disposition="reused").used_fallback is False
    assert (
        _runner_outcome(
            disposition="requeue-submitted",
            manifest_path=None,
            generation=1,
            checkpoint_count=1,
            snapshot_count=0,
        ).generation
        == 1
    )

    for changes, error in (
        ({"disposition": "unknown"}, ValueError),
        ({"manifest_path": None}, ValueError),
        ({"generation": 1}, ValueError),
        ({"checkpoint_count": 511}, ValueError),
        ({"snapshot_count": 15}, ValueError),
        ({"disposition": "reused", "used_fallback": True}, ValueError),
        (
            {"disposition": "requeue-submitted", "manifest_path": None, "generation": 0},
            ValueError,
        ),
        (
            {
                "disposition": "requeue-submitted",
                "manifest_path": "/unexpected/final.json",
                "generation": 1,
            },
            ValueError,
        ),
        ({"used_fallback": 0}, TypeError),
    ):
        with pytest.raises(error):
            _runner_outcome(**changes)


def _submission_outcome(**changes: object) -> runner.OneCellSubmissionOutcome:
    values: dict[str, object] = {
        "disposition": "accepted",
        "launch_sha256": _SHA256_A,
        "claim_path": f"/ledger/claims/{_SHA256_A}.json",
        "claim_sha256": _SHA256_B,
        "receipt_path": f"/ledger/receipts/{_SHA256_A}.json",
        "receipt_sha256": _SHA256_A,
        "sbatch_argv_sha256": _SHA256_B,
        "array_job_id": "4294967295",
    }
    values.update(changes)
    return runner.OneCellSubmissionOutcome(**values)  # type: ignore[arg-type]


def test_submission_outcome_requires_accepted_canonical_scheduler_id() -> None:
    assert _submission_outcome().array_job_id == "4294967295"
    for changes in (
        {"disposition": "rejected"},
        {"array_job_id": "0"},
        {"array_job_id": "01"},
        {"array_job_id": "4294967296"},
        {"array_job_id": "1;cluster"},
        {"claim_path": "relative/claim.json"},
    ):
        with pytest.raises(ValueError):
            _submission_outcome(**changes)


def test_error_exit_codes_are_frozen_and_type_strict() -> None:
    assert runner.OneCellRunnerValidationError("x").exit_code == 65
    assert runner.OneCellRunnerAuthorizationError("x").exit_code == 77
    assert runner.OneCellSchedulerError("x").exit_code == 69
    for error_type in (
        runner.OneCellRunnerValidationError,
        runner.OneCellRunnerAuthorizationError,
        runner.OneCellSchedulerError,
    ):
        for code in (64, 65, 66, 69, 70, 74, 75, 76, 77, 78):
            assert error_type("x", exit_code=code).exit_code == code
        for invalid in (True, 0, 67, 79, "77"):
            with pytest.raises(TypeError):
                error_type("x", exit_code=invalid)  # type: ignore[arg-type]


def test_generic_wrapper_and_manifest_remain_inert_and_package_separated() -> None:
    wrapper = _ROOT / "scripts" / "easley" / "run_pre_one_cell.sbatch"
    source = wrapper.read_text(encoding="utf-8")
    assert source.endswith("\n")
    assert "#SBATCH" not in source
    assert "set -euo pipefail" in source
    assert "umask 077" in source
    assert source.count('runtime_python_file="$authorization_directory/runtime-python.path"') == 1
    assert source.count("--authorization") == 1
    assert source.count("--execute") == 1
    assert source.count("-m tetris_ballistic_pre_one_cell_bootstrap") == 1
    assert source.count("\n  run \\\n") == 1
    assert "tetris_ballistic.scripts.run_pre_one_cell" not in source
    assert 'stat_executable="/usr/bin/stat"' in source
    assert source.count('check_directory_chain "$authorization_directory"') == 1
    assert source.count('check_directory_chain "$python_parent"') == 1
    assert '"$metadata_mode" == "700"' in source
    assert '"$metadata_mode" == "600"' in source
    assert source.count('"$metadata_links" == "1"') >= 2
    assert "metadata_device" in source
    assert "metadata_inode" in source
    assert "sidecar_has_exact_line_size" in source
    for forbidden in (
        "module load",
        "activate",
        "PYTHONPATH",
        "TETRIS_BALLISTIC_PRE_ONE_CELL_BOOTSTRAP",
        "git ",
        "mkdir",
        "\ntrap ",
        "--partition",
        "--account",
        "--qos",
        "run_one_cell.py",
        "run_batch.py",
    ):
        assert forbidden not in source

    syntax = subprocess.run(
        ["/bin/bash", "-n", str(wrapper)],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert syntax.returncode == 0, syntax.stderr.decode("utf-8", "replace")
    assert syntax.stdout == b""
    assert syntax.stderr == b""

    manifest = (_ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    declaration = "include scripts/easley/run_pre_one_cell.sbatch"
    assert manifest.count(declaration) == 1
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "scripts/easley/run_pre_one_cell.sbatch" not in pyproject
