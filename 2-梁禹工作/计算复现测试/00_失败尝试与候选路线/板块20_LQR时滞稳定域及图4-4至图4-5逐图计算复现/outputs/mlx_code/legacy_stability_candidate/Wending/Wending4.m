load('benchmarkstability.mat');
load('stabilitycanshu.mat');

[V, D] = eig(K, M);  % 计算特征值和特征向量
Phi = V;  % 假设V是特征向量矩阵
for j = 1:size(Phi, 2)
    Phi(:, j) = Phi(:, j) / norm(Phi(:, j));
end

n = size(Phi, 2);  % 特征向量的数量
for i = 1:n
    for j = i+1:n
        if abs(Phi(:, i)' * Phi(:, j)) > 1e-6  % 容忍度可以根据需要调整
            disp(['向量 ', num2str(i), ' 和 ', num2str(j), ' 不正交']);
        end
    end
end

[Q, R] = qr(Phi, 0);  % QR分解，0选项用于经济尺寸
Phi = Q;  % Q是正交的
n = size(Phi, 2);  % 特征向量的数量
for l = 1:n
    for j = l+1:n
        if abs(Phi(:, l)' * Phi(:, j)) > 1e-6  % 容忍度可以根据需要调整
            disp(['向量 ', num2str(l), ' 和 ', num2str(j), ' 不正交']);
        end
    end
end

V = Phi;
Md = V'*M*V
Cd = V'*C*V
Kd = V'*K*V

dt = 1/1024;
ald = (4*Md+2*dt*Cd+dt^2*Kd)\(4*Md);
al = V*ald*V';

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

k1 = zeros(5,2);
k1(1,1) = 1;
k1(2,2) = 1;
k2 = zeros(5,3);
k2(3,1) = 1;
k2(4,2) = 1;
k2(5,3) = 1;

k4 = k1-k2*inv(Koo)*Kot;

k3 = zeros(29,5);
k3(27,1) = 1;
k3(21,2) = 1;
k3(29,3) = 1;

k6 = zeros(2,29);
k6(1,27) = 1;
k6(2,21) = 1;

dt = 1/1024;
G1 = zpk(G1);
G1 = c2d(G1,dt);

z = tf('z',dt);

G16 = G1*k6;
M5 = k3*M_phys_5dof*k4;
C5 = k3*C_phys_5dof*k4;
K5 = k3*K_phys_5dof*k4;

%MNrt*(z-1)^2*(al\(dt^2*z*eye(29)))+CNrt*(z-1)/(z*dt)+KNrt+M5*G16*(z-1)^2*(al\(dt^2*z*eye(29)))+C5*G16*(z-1)/(z*dt)+K5*G16
%Gcl = G1*k6*((MNrt*(z-1)^2*(al\(dt^2*z*eye(29)))+CNrt*(z-1)/(z*dt)+KNrt+M5*G16*(z-1)^2*(al\(dt^2*z*eye(29)))+C5*G16*(z-1)/(z*dt)+K5*G16)\eye(29));

Gcl1 = MNrt*(z-1)^2*(al\(dt^2*z*eye(29)))+CNrt*(z-1)/(z*dt)+KNrt;
Gcl2 = M5*G16*(z-1)^2*(al\(dt^2*z*eye(29)))+C5*G16*(z-1)/(z*dt)+K5*G16;
Gcl3 = Gcl1+Gcl2;
Gcl = G1*k6*((Gcl1+Gcl2)\eye(29));
