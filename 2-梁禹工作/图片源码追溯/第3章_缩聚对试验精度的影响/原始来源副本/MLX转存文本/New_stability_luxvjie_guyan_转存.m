%% 
% guyan缩聚这里只对物理子结构进行缩聚
% 
% 有

index3 = [3,4];
index4 = [1,2,5,6];

order = [1,2,3,6,7,8];
K1 = KRrt;
K1(order,order) = KRrt(order,order)-KPrt

Mmn = MPrt(index3,index3);
Mmsn = MPrt(index3,index4);

Cmn = CPrt(index3,index3);
Cmsn = CPrt(index3,index4);

Kmn = KPrt(index3,index3);
Kmsn = KPrt(index3,index4);
Ksn = KPrt(index4,index4);
Ksmn = KPrt(index4,index3);

KPren = (Kmn-Kmsn*(Ksn\Ksmn));
MPren = (Mmn-Mmsn*(Ksn\Ksmn));
CPren = (Cmn-Cmsn*(Ksn\Ksmn));
%% 
% 

K2_1 = zeros(15);
K2_1(3:4,3) = [Kb(3,3);Kb(6,3)];
K2_2 = zeros(15);
K2_2(6:8,6) = [2*Kc(1,1);Kc(3,1);Kc(3,1)];
K2_2(11:13,6) = [2*Kc(4,1);Kc(6,1);Kc(6,1)];

K1 = KRrt-K2_1-K2_2;
%% 
% 计算稳定性时将时滞施加在K2上，得到系统运动方程
% 
% 计算CR积分的alpha
% 
% 计算CR积分算法的alpha，定义为al
% 
% al = 4*inv(4*M+2*dt*C+2*dt^2*K)*M;
% 
% al = (4*M+2*dt*C+dt^2*K)\(4*M);

K = KRrt;
M = MRrt;
C = CRrt;
[V, D] = eig(K, M);  % 计算特征值和特征向量
Phi = V;  % 假设V是特征向量矩阵
for i = 1:size(Phi, 2)
    Phi(:, i) = Phi(:, i) / norm(Phi(:, i));
end
%% 
% 计算结果显示特征值数量小于特征向量，说明存在特征向量对应同一个特征值，则特征向量间可能不正交
% 
% 检查其正交性

n = size(Phi, 2);  % 特征向量的数量
for i = 1:n
    for j = i+1:n
        if abs(Phi(:, i)' * Phi(:, j)) > 1e-6  % 容忍度可以根据需要调整
            disp(['向量 ', num2str(i), ' 和 ', num2str(j), ' 不正交']);
        end
    end
end
%% 
% 确定向量不正交，对向量进行正交化处理使用QR分解确保正交

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
%% 
% 经过转化矩阵得到对角化的M C K矩阵，记作Md Cd Kd

V = Phi;
Md = V'*M*V
Cd = V'*C*V
Kd = V'*K*V
%% 
% 计算对应的al（此时得到的是对角化的ald矩阵）矩阵

dt = 1/1024;
al = (4*Md+2*dt*Cd+dt^2*Kd)\(4*Md)
%al = 4*inv(4*Md+2*dt*Cd+dt^2*Kd)*Md;
%al = 4*inv(4*MRrt+2*dt*CRrt+dt^2*KRrt)*MRrt;
%al = V*ald*V'
%% 
% $$\frac{X\left(z\right)}{F\left(z\right)}=\frac{1}{\frac{{\left(z-1\right)}^2 
% }{\alpha z\Delta t^2 }M+\frac{z-1}{z\Delta t}C_1 +{\mathrm{K}}_1 +z^{-j} \left(\frac{z-1}{z\Delta 
% t}C_2 +{\mathrm{K}}_2 \right)}$$
% 
% 按照上述公式计算传递函数

%z = tf('z',dt); 
%s = tf('s');

syms z
i = 10
j = 10

KPren = sym(KPren);
KPren(1:2,1) = KPren(1:2,1)*z^(-i);
KPren(1:2,2) = KPren(1:2,2)*z^(-j);

% 反推扩展回原始大小的近似矩阵
Kmm_approx = KPren + Kmsn * (Ksn \ Ksmn);
Mmm_approx = MPren + Mmsn * (Ksn \ Ksmn);
Cmm_approx = CPren + Cmsn * (Ksn \ Ksmn);

% 初始化扩展矩阵，大小等于原矩阵大小
n = size(KPrt, 1);
K_ext = sym(zeros(n));
M_ext = sym(zeros(n));
C_ext = sym(zeros(n));

% 主自由度填充近似块
K_ext(index3, index3) = Kmm_approx;
M_ext(index3, index3) = Mmm_approx;
C_ext(index3, index3) = Cmm_approx;

% 剩余子块直接从原矩阵取
K_ext(index3, index4) = Kmsn;
K_ext(index4, index3) = Ksmn;
K_ext(index4, index4) = Ksn;

M_ext(index3, index4) = Mmsn;
M_ext(index4, index3) = Mmsn';  % 质量矩阵对称，转置赋值
M_ext(index4, index4) = MPrt(index4, index4);

C_ext(index3, index4) = Cmsn;
C_ext(index4, index3) = Cmsn';  % 阻尼矩阵一般对称，转置赋值
C_ext(index4, index4) = CPrt(index4, index4);

K3 = zeros(15);
K3 = sym(K3);
K3(locate2,locate2) = K_ext;

stab = zeros(30,30);
%for i = 1:30;
%    for j = 1:1
Kp = zeros(15);
Kd = zeros(15);
Kp(3,3) = 2;


syms z
syms s
% MRrt*(z-1)^2/(al*z*dt^2)+C1*(z-1)/(z*dt)+K1+z^(-j)*(C2*(z-1)/(z*dt)+K2)
Gcl = eye(15)*(z-1)^2/al/z/dt^2*MRrt+(z-1)/z/dt*CRrt+K1+K3;
det_G = det(Gcl);
Gcls_zero = vpa(solve(det_G == 0, z));
max(abs(Gcls_zero))