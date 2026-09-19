% Static extraction from untitled2.mlx
% Source SHA-256: 8D2E0BA775C6028C3572976C26B3A4B7109D887441D6DB0379758D2B5B822A55
% No MATLAB execution was performed.

%% CODE_CELL_C001
% 1. 原系统模态分析
[phi_full, omega2_full] = eig(KPrt, MPrt);
omega_full = sqrt(diag(omega2_full));
n_modes_full = size(phi_full, 2);

% 质量归一化模态矩阵
for i = 1:n_modes_full
    phi_full(:,i) = phi_full(:,i) / sqrt(phi_full(:,i)' * MPrt * phi_full(:,i));
end

% 2. Guyan 缩聚模态分析
[phi_guyan, omega2_guyan] = eig(KPren, MPren);
omega_guyan = sqrt(diag(omega2_guyan));
n_modes_guyan = size(phi_guyan, 2);
for i = 1:n_modes_guyan
    phi_guyan(:,i) = phi_guyan(:,i) / sqrt(phi_guyan(:,i)' * MPren * phi_guyan(:,i));
end

% 3. Craig-Bampton 缩聚模态分析（假设 KPCB、MPCB 已定义）
[phi_cb, omega2_cb] = eig(KP_cb, MP_cb);
omega_cb = sqrt(diag(omega2_cb));
n_modes_cb = size(phi_cb, 2);
for i = 1:n_modes_cb
    phi_cb(:,i) = phi_cb(:,i) / sqrt(phi_cb(:,i)' * MP_cb * phi_cb(:,i));
end

% --- 计算模态能量占比函数 ---
calc_modal_energy_ratio = @(phi, omega, M) ...
    (omega.^2) ./ sum(omega.^2);

% 计算模态能量占比 (这里用频率平方归一化近似)
E_ratio_full = calc_modal_energy_ratio(omega_full, omega_full, MPrt);
E_ratio_guyan = calc_modal_energy_ratio(omega_guyan, omega_guyan, MPren);
E_ratio_cb = calc_modal_energy_ratio(omega_cb, omega_cb, MP_cb);

% 归一化确保和为1
E_ratio_full = E_ratio_full / sum(E_ratio_full);
E_ratio_guyan = E_ratio_guyan / sum(E_ratio_guyan);
E_ratio_cb = E_ratio_cb / sum(E_ratio_cb);

% --- 保留率指标计算示范 ---
% 用转换矩阵 T 计算缩聚模态在原模态空间的映射
% 这里举例 Guyan 缩聚
T = TP; % Guyan转换矩阵

% 把缩聚模态映射回原空间
phi_guyan_expand = T * phi_guyan;

% 对应模态能量投影保留率：
modal_preservation_guyan = zeros(n_modes_guyan,1);
for i = 1:n_modes_guyan
    % 计算映射后模态与原系统模态的重叠（能量保留率）
    modal_preservation_guyan(i) = ...
        (phi_guyan_expand(:,i)' * MPrt * phi_guyan_expand(:,i)) / ...
        (phi_guyan(:,i)' * MPren * phi_guyan(:,i)); % 理论上=1，计算投影大小则用不同方法
end

% 或者用模态投影的平方和作为能量保留率指标：
modal_preservation_guyan = zeros(n_modes_guyan,1);
for i = 1:n_modes_guyan
    phi_proj = T' * phi_full(:,i); % 主自由度上的投影
    modal_preservation_guyan(i) = sum(phi_proj.^2);
end

% 同理，Craig-Bampton对应计算即可

% 总结输出：
fprintf('原系统模态能量占比前5个:\n');
disp(E_ratio_full(1:5));
fprintf('Guyan缩聚模态能量占比前5个:\n');
disp(E_ratio_guyan(1:5));
fprintf('Craig-Bampton缩聚模态能量占比前5个:\n');
disp(E_ratio_cb(1:5));
fprintf('Guyan模态投影能量保留率示例:\n');
disp(modal_preservation_guyan(1:5));
