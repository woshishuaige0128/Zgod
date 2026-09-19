% Static extraction from untitled3.mlx
% Source SHA-256: CC021A80CBD7D2E5C820B1B9141936AE197DE028C4983A6D60B5ED0C3FD0F777
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
r = [1;0;0;1;0;0];     % 激励方向
r_r = TP'*r
Gamma = phi' * M * r;
w = Gamma.^2;          % 可作为加权因子

% 加权总能量
E_weighted = sum(w .* E_modal);

% 缩聚后相同步骤
[phi_r, omega2_r] = eig(K_r, M_r);
omega_r = sqrt(diag(omega2_r));
E_modal_r = 0.5 * omega_r.^2;
Gamma_r = phi_r' * M_r * r_r;   % 若缩聚后激励向量变了也要换
w_r = Gamma_r.^2;
E_weighted_r = sum(w_r .* E_modal_r);

% 加权能量变化率
delta_E_weighted = (E_weighted_r - E_weighted) / E_weighted * 100
