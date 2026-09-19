load('benchmarkstability.mat');
load('stabilitycanshu.mat');

index1 = [13,21,26,27,29];
index2 = [1:12,14:20,22:25,28];

Mm = M(index1,index1);
Mms = M(index1,index2);
Km = K(index1,index1);
Kms = K(index1,index2);
Ks = K(index2,index2);
Ksm = K(index2,index1);
Cm = C(index1,index1);
Cms = C(index1,index2);

Mmn = MNrt(index1,index1);
Mmsn = MNrt(index1,index2);
Kmn = KNrt(index1,index1);
Kmsn = KNrt(index1,index2);
Ksn = KNrt(index2,index2);
Ksmn = KNrt(index2,index1);
Cmn = CNrt(index1,index1);
Cmsn = CNrt(index1,index2);

KP = K-KNrt;
CP = C-CNrt;
MP = M-MNrt;

Mmp = MP(index1,index1);
Mmsp = MP(index1,index2);
Kmp = KP(index1,index1);
Kmsp = KP(index1,index2);
Ksp = KP(index2,index2);
Ksmp = KP(index2,index1);
Cmp = CP(index1,index1);
Cmsp = CP(index1,index2);

Kre = (Km-Kms*(Ks\Ksm));
Mre = (Mm-Mms*(Ks\Ksm));Mre(2,2) = 1e-2;Mre(5,5) = 1e-2;
Cre = (Cm-Cms*(Ks\Ksm));

Kren = (Kmn-Kmsn*(Ksn\Ksmn));
Mren = (Mmn-Mmsn*(Ksn\Ksmn));
Cren = (Cmn-Cmsn*(Ksn\Ksmn));

Krep = Kmp; % 物理子结构的自由度已经被包括在主自由度中了
Mrep = Mmp;
Crep = Cmp;

dt = 1/1024;
al = (4*Mre+2*dt*Cre+dt^2*Kre)\(4*Mre);

P = 1.5;
I = 40;
D = 1e-8;
N = 1000;
s = tf('s');
%Gp0 = P+I/s+D*N/(1+N/s);
Gp0 = P+I/s+D*s;
Gp = [Gp0,0;0,Gp0];
Gps = ss(Gp);

%sys_ss = ss(A,B,C,D);
Gs = ss(A_cplant,B_cplant,C_cplant,D_cplant);
%G = tf(Gs);

%k1 = [0,1;1,0];
%G2 = zpk(G2);
%G1 = c2d(G2);
%G1 = k1*G1;
%G11 = c2d(G5,dt)
%G2 = (eye(2)+Gp*G)\Gp*G

%Gpd = c2d(Gp,dt,'tustin');
%Gd = c2d(G,dt,'tustin');
%sys_combined1 = series(Gpd, Gd);
%G3 = feedback(sys_combined1, eye(2));
%G4 = (eye(2)+Gpd*Gd)\Gpd*Gd;

%G1 = tf(G1);bode(G1,G2);bode(G1,G3);

sys_combined = series(Gps, Gs);
G5 = feedback(sys_combined, eye(2));
G1 = c2d(G5,dt);

k1 = zeros(5,2);
k1(1,1) = 1;
k1(2,2) = 1;
k2 = zeros(5,3);
k2(3,1) = 1;
k2(4,2) = 1;
k2(5,3) = 1;

k4 = k1-k2*inv(Koo)*Kot;

k3 = zeros(5,5);
k3(4,1) = 1;
k3(2,2) = 1;
k3(5,3) = 1;

k6 = zeros(2,5);
k6(1,4) = 1;
k6(2,2) = 1;
M5 = k3*M_phys_5dof*k4;
C5 = k3*C_phys_5dof*k4;
K5 = k3*K_phys_5dof*k4;

G1 = tf(G1);
G1 = G1*k6;
fm = M5*G1*(z-1)^2*(al\(dt^2*z*eye(5)))+C5*G1*(z-1)/(z*dt)+K5*G1;

%传递函数,如果是连续时间会怎样
s = tf('s');
s2 = s^2;
G5s = tf(G5);
Gcl1s = Mren*s^2+Cren*s+Kren;
%Gcl1s = series(Mren,ss(s2))+series(Cren,ss(s))+Kren;
fms = M5*G5s*k6*s^2+C5*G5s*k6*s+K5*G5s*k6;
%fms = series(series(M5,series(series(k6,s),G5)+series(series(C5,G5),series(k6,s))+series(series(K5,G5),k6);

Gcl3s = Gcl1s+fms;
%Gcl3ss = parallel(Gcl1s,fms);
%Gcl3s = tf(Gcl3ss);

[num,den] = tfdata(Gcl3s, 'v');
sym x;
x = sym('x');
Gcl4s = x*ones(5);
for d1 = 1:5
    for d2 = 1:5
        Polynum = poly2sym(num(d1,d2), x);
        Polyden = poly2sym(den(d1,d2), x);
        Gcl4s(d1,d2) = Polynum/Polyden;
    end
end

detGs = vpa((det(Gcl4s)),50);
solGs = solve(detGs);
max(real(solGs))
figure;
plot(real(solGs),imag(solGs),'o');
title('连续传递函数零点图')

l = 0;
j = 0;
z = tf('z',dt);

Gcl1 = (Mren*(z-1)^2)*(al\(dt^2*z*eye(5)))+Cren*(z-1)/(z*dt)+Kren;
%fm = z^(-l)*(Crep*k1*G1(2,2)*(z-1)/(z*dt))+z^(-j)*(Krep*k1*G1(2,2));
Gcl3 = Gcl1+fm;
Gcl3 = minreal(Gcl3);
Gcl3 = simplify(Gcl3)
%max(abs(tzero(Gcl3)))

[num,den] = tfdata(Gcl3, 'v');
sym x;
x = sym('x');
Gcl4 = x*ones(5);
%Gcl3 = c2d(Gcl3s,dt,'tustin');
for d1 = 1:5
    for d2 = 1:5
        Polynum = poly2sym(num(d1,d2), x);
        Polyden = poly2sym(den(d1,d2), x);
        Gcl4(d1,d2) = Polynum/Polyden;
    end
end

detG = vpa((det(Gcl4)),12);
solG = solve(detG == 0,x);
Gzero1= max(abs(solG))
figure;
plot(real(solG),imag(solG),'o');
title('离散传递函数零点图')
%z = tf('z',dt);
%Gzero = zeros(50);
%for l = 1:50
%    for j = 1:50
%Gcl1 = (Mren+Mrep*G1(2,2))*(z-1)^2*(al\(dt^2*z*eye(3)))+Cren*(z-1)/(z*dt)+Kren;
%fm = z^(-l)*(Crep*G1(2,2)*(z-1)/(z*dt))+z^(-j)*(Krep*G1(2,2));
%Gcl3 = Gcl1+fm;
%Gzero(l,j) = max(abs(zero(Gcl3)));
%    end
%end
