% 假设 M, K, r 已定义，r 是激励方向向量
%r=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0]';
r=[1,0,0,1,0,0,1,0,0,1,0,0,1,0,0,1,0,0]';
K = KRrt;
M = MRrt;
[phi, omega2] = eig(K, M);   % 计算模态
omega = sqrt(diag(omega2));
n = size(phi, 2);
Gamma = zeros(n, 1);

for i = 1:n
    phi(:,i) = phi(:,i) / sqrt(phi(:,i)' * M * phi(:,i));  % 质量归一化
    Gamma(i) = phi(:,i)' * M * r;   % 模态参与因子
end

% 可视化参与因子或其平方
GammaSq = Gamma.^2;
participation_ratio = GammaSq / sum(GammaSq)
bar(participation_ratio);
xlabel('模态编号');
ylabel('参与比');
title('模态参与比估计（归一化的 Γ^2）');

