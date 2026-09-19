%给出数值子结构定位
locate = [1,3,4,5,6,7,8,9,10,11,12,13,14,15];
%给出物理子结构定位
locate2 = [1,2,3];
locate3 = zeros(15,6);
%locate3(locate2,1:6) = eye(6);

KNrt = KRrt;
KNrt(locate2,locate2) = KRrt(locate2,locate2)-KPrt;
%KNrt([1,6],[1,6]) = KRrt([1,6],[1,6])/2;
%KNrt = KNrt(locate,locate);

M5 = 2*mass_b + 2*mass_c;
M6 = (mass_b/2)*(Lb.^2)/12;
M2 = (mass_b/2)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
M3 = (mass_b)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
MNrt = diag([M5 1e-5 M6 M3 M2 M1 M2 M3 M3 M2 M1 M2 M3 M3 M2]);

CNrt = CRrt;
CNrt(locate2,locate2) = CRrt(locate2,locate2)-CPrt;
%CNrt = CNrt(locate,locate);

KNbar=(KNrt+(a0*MNrt)+(a1*CNrt));
KNbar_inv = inv(KNbar);

AgN = zeros(15,1);
lN = zeros(15,1);
lN(1,1) = 1;
lN(6,1) = 1;
lN(11,1) = 1;
RNbar = zeros(15,1);
FN = zeros(15,1);