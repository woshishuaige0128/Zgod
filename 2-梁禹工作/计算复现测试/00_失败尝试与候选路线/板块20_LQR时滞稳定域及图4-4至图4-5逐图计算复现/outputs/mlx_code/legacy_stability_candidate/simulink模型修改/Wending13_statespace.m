load('benchmarkstability.mat');
load('stabilitycanshu.mat');

index1 = [13,21,26,27,29];
index2 = [1:12,14:20,22:25,28];

% 此处计算的都是整体结构的参数，用于计算CR积分算法的alpha
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

Kre = (Km-Kms*(Ks\Ksm));
Mre = (Mm-Mms*(Ks\Ksm));Mre(2,2) = 1e-6;Mre(5,5) = 1e-6;
Cre = (Cm-Cms*(Ks\Ksm));

Kren = (Kmn-Kmsn*(Ksn\Ksmn));
Mren = (Mmn-Mmsn*(Ksn\Ksmn));
Cren = (Cmn-Cmsn*(Ksn\Ksmn));

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

k6 = zeros(2,5);% 输入5维位移，取其中物理子结构的位移和转角
k6(1,4) = 1;
k6(2,2) = -1;
M5 = M_phys_5dof;
C5 = C_phys_5dof;
K5 = K_phys_5dof;

Hs1 = [1,-0.2954*sin(-0.4444);1,-0.2954*sin(0.4444)];
Hs2 = [0.5,0.5;1/(0.5908*sin(0.4444)),-1/(0.5908*sin(0.4444))];

s = tf('s');
Gns = ss((Mren.*s^2+Cren.*s+Kren)\eye(5));
Gnd = c2d(Gns,dt,'tustin');

Gp = k3*(M5*s^2+C5*s+K5);
Gps = ss(Gp);
Gpd = c2d(Gps,dt,'tustin');

P = 1.5;
I = 45;
D = 1e-8;
N = 1000;
s = tf('s');
Gpid = P+I/s+D*N/(1+N/s);
%Gp0 = P+I/s+D*s;
Gpid = [Gp0,0;0,Gp0];

Gc = ss(A_cplant,B_cplant,C_cplant,D_cplant);

G0 = series(Gpid,Gc);
G1 = feedback(G0,eye(2));

[A_G1, B_G1, C_G1, D_G1] = ssdata(G1);
Ds0 = ss(A_G1, B_G1*Hs1*k6, C_G1, D_G1*Hs1*k6);
Ds = ss(Ds0.A, Ds0.B, k4*Hs2*Ds0.C, k4*Hs2*Ds0.D);
%Ds_1 = series(Ds0,k4*Hs2);
%bode(Ds,Ds_1);检查两种写法是否有区别，bode图和simulink图来看无区别

%Gs = series(Gns,Ds);
%Gcl = feedback(Gs,-Gps);
%Gcl_m = minreal(Gcl);
%Gcld = c2d(Gcl_m,dt,'tustin');
%[Gcl_m_A,Gcl_m_B,Gcl_m_C,Gcl_m_D] = ssdata(Gcl_m);
%Gcl_tf = tf(Gcl_m);
%Gcl_tfd = c2d(Gcl_tf,dt,'tustin');

j1 = 70;
j2 = 50;
z = tf('z',dt);
td = [z^(-j1),0;0,z^(-j2)];
Ds0d = c2d(Ds0,dt,'tustin');
Ds1 = series(Ds0d,td);
Ds2 = series(Ds1,k4*Hs2);
%Gnd = c2d(Gns,dt,'tustin');
Gd = series(Gnd,Ds2);
%Gpd = c2d(Gps,dt,'tustin');
Gcld = feedback(Gd,-Gpd);
Gcld = minreal(Gcld);
%pzmap(Gcld)
max(abs(eig(Gcld.A)))
