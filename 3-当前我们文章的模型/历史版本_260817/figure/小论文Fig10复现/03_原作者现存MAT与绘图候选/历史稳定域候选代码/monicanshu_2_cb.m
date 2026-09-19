index1 = [1,4];
index2 = [2,3,5,6];
index3 = [1,7,13,4,10,16];
index4 = [2,3,5,6,8,9,11,12,14,15,17,18];
index5 = [1,4,7,10];
index6 = [2,3,5,6,8,9,11,12];
order = [index3,index4];

%Mforce = MRrt(order,order);
%Mf = diag([1,1,1,0,0,0,0,0,0,0,0,0,0,0,0].*Mforce);

Mmn = MRrt(index3,index3);
Mmsn = MRrt(index3,index4);

Cmn = CRrt(index3,index3);
Cmsn = CRrt(index3,index4);

Kmn = KRrt(index3,index3);
Kmsn = KRrt(index3,index4);
Ksn = KRrt(index4,index4);
Ksmn = KRrt(index4,index3);

KRren = (Kmn-Kmsn*(Ksn\Ksmn));
MRren = (Mmn-Mmsn*(Ksn\Ksmn));
CRren = (Cmn-Cmsn*(Ksn\Ksmn));

I = eye(length(index3)); % 主自由度单位矩阵
T = [I; -Ksn\Ksmn];      % 拼接得到转换矩阵

Mmn = MPrt(index1,index1);
Mmsn = MPrt(index1,index2);

Cmn = CPrt(index1,index1);
Cmsn = CPrt(index1,index2);

Kmn = KPrt(index1,index1);
Kmsn = KPrt(index1,index2);
Ksn = KPrt(index2,index2);
Ksmn = KPrt(index2,index1);

KPren = (Kmn-Kmsn*(Ksn\Ksmn));
MPren = (Mmn-Mmsn*(Ksn\Ksmn));
CPren = (Cmn-Cmsn*(Ksn\Ksmn));

I = eye(length(index1)); % 主自由度单位矩阵
TP = [I; -Ksn\Ksmn];     % 拼接得到转换矩阵

Mmn = MNrt_2(index5,index5);
Mmsn = MNrt_2(index5,index6);

Cmn = CNrt_2(index5,index5);
Cmsn = CNrt_2(index5,index6);

Kmn = KNrt_2(index5,index5);
Kmsn = KNrt_2(index5,index6);
Ksn = KNrt_2(index6,index6);
Ksmn = KNrt_2(index6,index5);

KNren = (Kmn-Kmsn*(Ksn\Ksmn));
MNren = (Mmn-Mmsn*(Ksn\Ksmn));
CNren = (Cmn-Cmsn*(Ksn\Ksmn));

I = eye(length(index5)); % 主自由度单位矩阵
TN = [I; -Ksn\Ksmn];     % 拼接得到转换矩阵

locate1 = [1,2];
locate2 = [3,4,5,6];
K2 = KRren;
K2(locate1,locate1) = KRren(locate1,locate1)-KPren;
K2(locate2,locate2) = KRren(locate2,locate2)-KNren;
C2 = CRren;
C2(locate1,locate1) = CRren(locate1,locate1)-CPren;
C2(locate2,locate2) = CRren(locate2,locate2)-CNren;
K1 = KRren-K2;
C1 = CRren-C2;

al = (4*MRren+2*dt*CRren+dt^2*KRren)\MRren*4;

stab = zeros(20);
for l = 0:10
%l = 3;
for j = 0:10
%j = 1;

syms z
H = sym(eye(6));
H(1,1) = z^(-l);
H(2,2) = z^(-j);

%syms z
G = (z-1)^2/z/dt^2*MRren/al+(z-1)/z/dt*C1+K1+...
    ((z-1)/z/dt*C2+K2)*H;
%G = (z-1)^2/z/dt^2*MNren/al+(z-1)/z/dt*CNren+KNren+...
%    S'*H*((z-1)/z/dt*CPren+KPren+(z-1)/z/dt*Kd_ctrl+Kp_ctrl)*S;
det_G = det(G);
Gcls_zero = vpa(solve(det_G == 0, z));
s = max(abs(Gcls_zero));
stab(l+1,j+1) = s;
end
end
save('stab_guyan_lqr.mat', 'stab');
