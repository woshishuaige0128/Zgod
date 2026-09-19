% 参数设定
n_modes = 6;
reduced_dofs = [1,11,6,4,9,14];  % ← 这里填入缩聚保留的自由度编号，例如 [1 6 11]

% 系统刚度和质量矩阵
K = KRrt;
M = MRrt;
Kren{1} = KRren;
Mren{1} = MRren;
Kren{2} = KR_cb;
Mren{2} = MR_cb;

% ---------- 1. 计算频率 ----------
% 原始模型频率
[Phi_full, D] = eigs(K, M, n_modes, 'sm');
f_full = sqrt(diag(D)) / (2*pi);

% Guyan 模型频率
[Phi_guyan, Dg] = eigs(Kren{1}, Mren{1}, n_modes, 'sm');
f_guyan = sqrt(diag(Dg)) / (2*pi);

% CB 模型频率
[Phi_cb, Dc] = eigs(Kren{2}, Mren{2}, n_modes, 'sm');
f_cb = sqrt(diag(Dc)) / (2*pi);

% 相对误差（百分比）
relErr_guyan = abs(f_guyan - f_full) ./ f_full * 100;
relErr_cb = abs(f_cb - f_full) ./ f_full * 100;

% ---------- 2. 子空间内模态相似度（MAC） ----------
mac = @(v1, v2) (abs(v1' * v2)^2) / ((v1' * v1) * (v2' * v2));
MAC_guyan_r = zeros(1, n_modes);
MAC_cb_r = zeros(1, n_modes);

n_boundary = length(reduced_dofs);

for i = 1:n_modes
    phi_full_r = Phi_full(reduced_dofs, i);
    phi_full_r = phi_full_r / norm(phi_full_r);

    phi_g = Phi_guyan(:, i) / norm(Phi_guyan(:, i));
    
    phi_cb_boundary = Phi_cb(1:n_boundary, i); % ← 只取 CB 模态的界面自由度部分
    phi_cb_boundary = phi_cb_boundary / norm(phi_cb_boundary);

    MAC_guyan_r(i) = mac(phi_full_r, phi_g);
    MAC_cb_r(i) = mac(phi_full_r, phi_cb_boundary);
end

% ---------- 输出 ----------
disp('Guyan 模型频率误差 (%):');
disp(relErr_guyan);
disp('CB 模型频率误差 (%):');
disp(relErr_cb);

disp('Guyan 模型 MAC (缩聚子空间):');
disp(MAC_guyan_r);
disp('CB 模型 MAC (缩聚子空间):');
disp(MAC_cb_r);