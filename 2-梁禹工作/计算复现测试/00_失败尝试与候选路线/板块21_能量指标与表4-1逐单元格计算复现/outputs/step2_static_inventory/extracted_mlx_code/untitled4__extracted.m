% Static extraction from untitled4.mlx
% Source SHA-256: AA7CB11E993998938AFDC1A085A1E9FC8EDB03151DBD33B34A1684C71142BF6D
% No MATLAB execution was performed.

%% CODE_CELL_C001
% 原系统模态
K = KPrt;
M = MPrt;

% 模态分析
[phi, omega2] = eig(K, M);
omega = sqrt(diag(omega2));
E_modal = 0.5 * omega.^2;

% 加权因子（如模态参与因子）
r = [1;0;0;1;0;0;1;0;0];     % 激励方向
r_r = TP'*r
% 假设你已有 M, phi, r
Gamma = phi' * M * r;
Gamma2 = Gamma.^2;
Gamma2_norm = Gamma2 / sum(Gamma2);  % 归一化

% 可用于加权能量
omega = sqrt(diag(omega2));  % 来自 eig(K, M)
E_weighted = sum(Gamma2_norm .* E_modal);

% 缩聚后相同步骤
[phi_r, omega2_r] = eig(K_r, M_r);
omega_r = sqrt(diag(omega2_r));
E_modal_r = 0.5 * omega_r.^2;
Gamma = phi_r' * M_r * r_r;
Gamma2 = Gamma.^2;
Gamma2_norm = Gamma2 / sum(Gamma2);  % 归一化

% 可用于加权能量
omega = sqrt(diag(omega2));  % 来自 eig(K, M)
E_weighted_r = sum(Gamma2_norm .* E_modal_r);

% 加权能量变化率
delta_E_weighted = (E_weighted_r - E_weighted) / E_weighted * 100
