%给出物理子结构定位
locate2 = [1,2,3,6,7,8];

KPrt = [2*Kc(4,4)+2*Kc(1,1)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	2*Kc(1,4)	Kc(1,6)	Kc(1,6);
Kc(6,4)+Kc(3,1)	Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	Kc(3,4)	Kc(3,6)	0;
Kc(6,4)+Kc(3,1)	Kb(6,3)	Kb(6,6)+Kc(6,6)+Kc(3,3)	Kc(3,4)	0	Kc(3,6);
2*Kc(4,1)	Kc(4,3)	Kc(4,3)	2*Kc(4,4)+2*Kc(1,1)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3);
Kc(6,1)	Kc(6,3)	0	Kc(6,4)+Kc(3,1)	Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6);
Kc(6,1)	0	Kc(6,3)	Kc(6,4)+Kc(3,1)	Kb(6,3)	Kb(6,6)+Kc(6,6)+Kc(3,3);
];
%KPrt = zeros(6,6);
KPrt([1,4],[1,4]) = KRrt([1,6],[1,6]).*0.5.*0.962;

M4 = mass_b + 2*mass_c;
M2 = (mass_b/2)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
%M3 = (mass_b)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
MPrt = diag([M4 M2 M2 M4 M2 M2]);
%MPrt = zeros(6,6);

CPrt = CRrt(locate2,locate2);
%CPrt = zeros(6,6);
CPrt([1,4],[1,4]) = CRrt([1,6],[1,6])/2;
CRrtdel = CRrt(3,3)-CRrt(2,2);
CPrt(3,3) = CRrt(3,3)-CRrtdel;
CPrt(6,6) = CRrt(8,8)-CRrtdel;

KPbar=(KPrt+(a0*MPrt)+(a1*CPrt));
KPbar_inv = inv(KPbar);

lP = zeros(6,1);
lP(1,1) = 1;
lP(4,1) = 1;
RPbar = zeros(6,1);
AgP = zeros(6,1);
AgP(1,1) = 1;
AgP(4,1) = 1;