%给出物理子结构定位
locate2 = [1,2,3,6,7,8];

KPrt = KRrt(locate2,locate2);
KPrt(1,1) = KRrt(1,1)/2;
KPrt(4,4) = KRrt(6,6)/2;

M4 = 1.5*mass_b + 2*mass_c;
M2 = (mass_b/2)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
M3 = (mass_b)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
MPrt = diag([M4 M2 M3 M4 M2 M3]);

CPrt = CRrt(locate2,locate2);
CPrt(1,1) = CRrt(1,1)/2;
CPrt(4,4) = CRrt(6,6)/2;

KPbar=(KPrt+(a0*MPrt)+(a1*CPrt));
KPbar_inv = inv(KPbar);

lP = zeros(6,1);
lP(1,1) = 1;
lP(4,1) = 1;
RPbar = zeros(6,1);
AgP = zeros(6,1);
AgP(1,1) = 1;
AgP(4,1) = 1;