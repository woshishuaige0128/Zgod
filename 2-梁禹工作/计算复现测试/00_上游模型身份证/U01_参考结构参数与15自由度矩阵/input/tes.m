% === 输入：质量矩阵和刚度矩阵 ===
M = MRrt;          % 替换为你的质量矩阵
K = KRrt;          % 替换为你的刚度矩阵
r = ones(size(M,1), 1);  % 激励方向，默认全部自由度均匀受力

% === 步骤1：求解模态 ===
[Phi, Lambda] = eig(K, M);       % 解广义特征值问题 K*phi = lambda*M*phi
omega = sqrt(diag(Lambda));     % 自然角频率 rad/s
f = omega / (2*pi);             % 模态频率 Hz

% === 步骤2：模态质量归一化 ===
num_modes = size(Phi, 2);
for i = 1:num_modes
    phi_i = Phi(:, i);
    phi_i = phi_i / sqrt(phi_i' * M * phi_i);
    Phi(:, i) = phi_i;  % 更新归一化模态
end

% === 步骤3：计算质量参与系数 ===
Gamma = zeros(num_modes, 1);    % 参与因子
mu = zeros(num_modes, 1);       % 质量参与系数
rMr = r' * M * r;

for i = 1:num_modes
    phi_i = Phi(:, i);
    Gamma(i) = phi_i' * M * r;
    mu(i) = (Gamma(i)^2) / rMr;
end

% === 输出结果 ===
cumulative_mu = cumsum(mu);     % 累计参与系数
disp('模态频率 (Hz):'); disp(f);
disp('质量参与系数:'); disp(mu);
disp('累计质量参与系数:'); disp(cumulative_mu);

% === 可视化（可选）===
figure;
bar(cumulative_mu, 'FaceColor', [0.2 0.4 0.6]);
xlabel('模态阶次'); ylabel('累计质量参与系数');
title('模态累计质量参与度');
grid on;
