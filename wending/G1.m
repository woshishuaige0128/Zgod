load('stabilitycanshu.mat');

%计算控制器
P = 1.5;
I = 45;
D = 1e-8;
N = 100;
s = tf('s');
Gp0 = P+I/s+D*N/(1+N/s);
Gp = [Gp0,0;0,Gp0];

sys_ss = ss(A_cplant,B_cplant,C_cplant,D_cplant);
G = tf(sys_ss);

G1 = (eye(2)+Gp*G)\Gp*G;