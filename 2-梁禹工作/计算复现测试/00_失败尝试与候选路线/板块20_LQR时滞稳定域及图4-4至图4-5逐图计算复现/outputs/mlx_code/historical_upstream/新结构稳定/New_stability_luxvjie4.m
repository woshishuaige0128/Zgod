%K2 = zeros(6,6);
%order = [1];
%order3 = [1,2,3,4,5,6];
%K2 = KPrt(order3,order);
%C2 = CPrt(order3,order);
%order2 = [1];

%K1 = KRrt;
%K1(order3,order2) = KRrt(order3,order2) - K2;
%C1 = CRrt;
%C1(order3,order2) = CRrt(order3,order2) - C2;

%K2 = KRrt-K1;
%C2 = CRrt-C1;

K2_1 = zeros(15);
K2_1(3:4,3) = [Kb(3,3);Kb(6,3)];
K2_2 = zeros(15);
K2_2(6:8,6) = [2*Kc(1,1);Kc(3,1);Kc(3,1)];
K2_2(11:13,6) = [2*Kc(4,1);Kc(6,1);Kc(6,1)];

K1 = KRrt-K2_1-K2_2;

K = KRrt;
M = MRrt;
C = CRrt;
[V, D] = eig(K, M);  % 计算特征值和特征向量
Phi = V;  % 假设V是特征向量矩阵
for i = 1:size(Phi, 2)
    Phi(:, i) = Phi(:, i) / norm(Phi(:, i));
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
for i = 1:n
    for j = i+1:n
        if abs(Phi(:, i)' * Phi(:, j)) > 1e-6  % 容忍度可以根据需要调整
            disp(['向量 ', num2str(i), ' 和 ', num2str(j), ' 不正交']);
        end
    end
end

V = Phi;
Md = V'*M*V
Cd = V'*C*V
Kd = V'*K*V

dt = 1/1024;
al = (4*Md+2*dt*Cd+dt^2*Kd)\(4*Md)
%al = 4*inv(4*Md+2*dt*Cd+dt^2*Kd)*Md;
%al = 4*inv(4*MRrt+2*dt*CRrt+dt^2*KRrt)*MRrt;
%al = V*ald*V'

%z = tf('z',dt);
%s = tf('s');

i = 0
j = 10

stab = zeros(30,30);
%for i = 1:30;
%    for j = 1:1
Kp = zeros(15);
Kd = zeros(15);
Kp(3,3) = 2;

syms z
syms s
% MRrt*(z-1)^2/(al*z*dt^2)+C1*(z-1)/(z*dt)+K1+z^(-j)*(C2*(z-1)/(z*dt)+K2)
Gcl = eye(15)*(z-1)^2/al/z/dt^2*MRrt+(z-1)/z/dt*CRrt+K1+z^(-i)*K2_1+z^(-j)*K2_2;
det_G = det(Gcl);
Gcls_zero = vpa(solve(det_G == 0, z));
max(abs(Gcls_zero))
