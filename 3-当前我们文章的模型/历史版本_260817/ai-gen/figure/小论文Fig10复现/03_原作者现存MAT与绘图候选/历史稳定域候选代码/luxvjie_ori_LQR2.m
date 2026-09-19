index = [1,2,3,6,7,8]
K2 = zeros(15);
K2(index,1) = KPrt(:,1);
K2(index,6) = KPrt(:,4);

C2 = zeros(15);
C2(index,1) = CPrt(:,1);
C2(index,6) = CPrt(:,4);

C1 = CRrt-C2;
K1 = KRrt-K2;

al = (4*MRrt+2*dt*CRrt+dt^2*KRrt)\MRrt*4;

stab = zeros(20);
%for l = 0:20
l = 0;
%for j = 0:20
%j = 25;
%l = 0
j = 0;
%z=tf('z',dt);
syms z
%l = 19;
%j = 5;
H = sym(zeros(15,15));
H(1,1) = z^(-l);
H(6,6) = z^(-j);

%syms z
G = (z-1)^2/z/dt^2*MRrt/al+(z-1)/z/dt*C1+K1+...
    ((z-1)/z/dt*C2+K2)*H;
%G = (z-1)^2/z/dt^2*MNren/al+(z-1)/z/dt*CNren+KNren+...
%    S'*H*((z-1)/z/dt*CPren+KPren+(z-1)/z/dt*Kd_ctrl+Kp_ctrl)*S;
det_G = det(G);
Gcls_zero = vpa(solve(det_G == 0, z));
s = max(abs(Gcls_zero))
stab(l+1,j+1) = max(abs(Gcls_zero));
%end
%end
%save('stab_guyan_lqr.mat', 'stab');
