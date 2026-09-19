%% 
% 鲁旭杰师兄的方式
% 
% 定义K1、K2、K3
% 
% 这里以2层的物理子结构为例，边界条件处的自由度属于K2，物理子结构剩余部分属于K3，K3和数值子结构的刚度矩阵共同构成K1
% 
% 将时滞施加到K2上，K1无时滞，构建运动方程，通过计算此运动方程的极点来判断稳定性，理论上来说，离散会降低稳定性，这也是鲁师兄的学术核心，即离散后的系统稳定不能完全按照之前的稳定性判据
% 
% 本研究的立足点就在于继续推进，研究系统缩聚对系统稳定带来的影响，验证缩聚后的系统稳定性，保证缩聚后的RTHS试验能够顺利进行
% 
% 1.确定结构参数，这里先以未缩聚的结构举例，KNrt是数值，KPrt是物理

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
%% 
% 首先定义K2
% 
% 之前犯了一个错误，K2之前一直按照鲁旭杰的思路定义，实际上与我的结构存在差异
% 
% 最直观的差异就是每一层的水平位移，鲁旭杰是按照每一层只有一个水平自由度得到的，但是我的结构是第一层的其中一品作为物理子结构，剩下的几品作为数值
% 
% 带来了一个巨大的不同，因为我的水平自由度是按照每一层相等计算的，所以划分完子结构后物理和数值完全瓜分了水平自由度，即水平自由度全部都是K1
% 
% 回到原本的理论，根据理论推导，K2实际上是两个子结构交互的界面，只是它的结构划分的比较明确，所以才看似是独立于两个子结构，所以实际情况是我的物理子结构矩阵中有一部分参与了界面力的计算，应该划分到K2当中去

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