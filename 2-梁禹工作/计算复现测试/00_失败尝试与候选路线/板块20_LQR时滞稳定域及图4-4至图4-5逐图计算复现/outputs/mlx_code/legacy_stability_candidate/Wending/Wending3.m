load('stabilitycanshu.mat');
dt = 1/1024;

P = 1.5;
I = 45;
D = 1e-8;
N = 100;
s = tf('s');
Gp0 = P+I/s+D*N/(1+N/s)
Gp = [Gp0,0;0,Gp0]

%sys_ss = ss(A,B,C,D);
sys_ss = ss(A_cplant,B_cplant,C_cplant,D_cplant);
G = tf(sys_ss)

G1 = (eye(2)+Gp*G)\Gp*G

%G2 = zpk(G1);
%G2 = c2d(G2,dt);
%G3 = tf(G2);

%G1 = G3;

k1 = zeros(5,2);
k1(1,1) = 1;
k1(2,2) = 1;
k2 = zeros(5,3);
k2(3,1) = 1;
k2(4,2) = 1;
k2(5,3) = 1;

k4 = k1-k2*inv(Koo)*Kot;

%z = tf('z',dt)
%s = zpk(s)
%al2 = (4*M_phys_5dof+2*dt*C_phys_5dof+dt^2*K_phys_5dof)\(4*M_phys_5dof);
%fm = ((1-exp(-dt*s))^2*M_phys_5dof*k4*G1*k3/al+(1-exp(-dt*s))*dt*C_phys_5dof*k4*G1*k3+dt^2*K_phys_5dof*k4*G1*k3*exp(-dt*s))/(exp(-dt*s)*dt^2);
Gp1 = s^2*M_phys_5dof*k4+s*C_phys_5dof*k4+K_phys_5dof*k4
% 使用 prescale 命令对系统进行预缩放
%fm = prescale(fm)

k5 = zeros(29,5);
k5(27,1) = 1;
k5(21,2) = 1;
k5(29,3) = 1;

Gp = k5*Gp1;

k3 = zeros(2,29);
k3(1,27) = 1;
k3(2,21) = 1;
Gn1 = (s^2*MNrt+s*CNrt+KNrt)\eye(29,29);
Gn = k3*Gn1

Gcl = (eye(2)+G1*Gn*Gp)\(G1*Gn)

kk1 = [1,0,0;0,0,1];
MP2 = kk1*MP1*kk1'
CP2 = kk1*CP1*kk1'
KP2 = kk1*KP1*kk1'
kk2 = zeros(29,2);
kk2(21,2) = 1;
kk2(27,1) = 1;
Gcl = s^2*MNrt+s*CNrt+KNrt+fm2;
%zero(Gcl)

Gcld = zpk(Gcl);

sym_G = sym(zeros(29,29));

% 转换每个传递函数元素
for i = 1:29
    for j = 1:29
        num_coeffs = Gcl(i,j).Num;
        den_coeffs = Gcl(i,j).Den;
        sym_G(i,j) = poly2sym(num_coeffs, sym('z')) / poly2sym(den_coeffs, sym('z'));
    end
end
Gcl = sym_G

%计算特征方程的行列式
Gcl = simplify(Gcl);
%使用vpa调整精度，默认按照32位计算，不然detGcl计算不出来
Gcl = vpa(Gcl);
detGcl = det(Gcl);
%求解行列式的零点
Gclzero = solve(detGcl);
%计算零点中的最大值
Gclmax = max(abs(Gclzero))
