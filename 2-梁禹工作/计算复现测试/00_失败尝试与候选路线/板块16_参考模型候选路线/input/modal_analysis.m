% 假设你已有以下矩阵
% K_full, M_full: 缩聚前
% K_red,  M_red:  缩聚后
% dof_interest:  缩聚前系统中你关注的自由度编号（如 [1,6,11]）

% ========== 设置参数 ==========
K_full = KRrt;
M_full = MRrt;
C_full = CRrt;
M = M_full;
% 假设你已经有模态矩阵 Phi，大小 n x m
% 设置计算前 i 阶模态能量占比
i = 3 % 例如前5阶模态

[Phi,omega] = eig(K_full,M_full);

[n, m] = size(Phi);
if i > m
    error('i不能大于模态矩阵的模态数');
end

Phi_i = Phi(:, 1:i);
energy_ratio = zeros(n, i);

for mode_idx = 1:i
    mode_vec = Phi_i(:, mode_idx);
    
    % 质量加权总能量（标量）
    total_energy = mode_vec' * M * mode_vec;
    
    % 质量加权每个自由度能量分量（n x 1）
    energy_per_dof = mode_vec .* (M * mode_vec);
    
    % 能量占比
    energy_ratio(:, mode_idx) = energy_per_dof / total_energy;
end
S_full = sum(energy_ratio,2);

M = MRren;
% 假设你已经有模态矩阵 Phi，大小 n x m
% 设置计算前 i 阶模态能量占比
i = 3; % 例如前5阶模态

[Phi,omega] = eig(KRren,MRren);

[n, m] = size(Phi);
if i > m
    error('i不能大于模态矩阵的模态数');
end

Phi_i = Phi(:, 1:i);
energy_ratio = zeros(n, i);

for mode_idx = 1:i
    mode_vec = Phi_i(:, mode_idx);
    
    % 质量加权总能量（标量）
    total_energy = mode_vec' * M * mode_vec;
    
    % 质量加权每个自由度能量分量（n x 1）
    energy_per_dof = mode_vec .* (M * mode_vec);
    
    % 能量占比
    energy_ratio(:, mode_idx) = energy_per_dof / total_energy;
end
S_guyan = sum(energy_ratio,2);

ratio = (S_guyan-S_full([1,6,11]))./S_full([1,6,11])


