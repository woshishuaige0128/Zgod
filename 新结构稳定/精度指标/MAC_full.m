% 假设你已经有
reduced_dofs_guyan = index3;
reduced_dofs_cb = index3;
n_boundary = length(index3);

% ---------- 1. 计算频率 ----------
% 原始模型频率
K = KRrt;
M = MRrt;
Kren{1} = KRren;
Mren{1} = MRren;
Kren{2} = KR_cb;
Mren{2} = MR_cb;
[Phi_full, D] = eigs(K, M, n_modes, 'sm');
f_full = sqrt(diag(D)) / (2*pi);

% Guyan 模型频率
[Phi_guyan, Dg] = eigs(Kren{1}, Mren{1}, n_modes, 'sm');
f_guyan = sqrt(diag(Dg)) / (2*pi);

% CB 模型频率
[Phi_cb, Dc] = eigs(Kren{2}, Mren{2}, n_modes, 'sm');
f_cb = sqrt(diag(Dc)) / (2*pi);

n_modes_guyan = size(Phi_guyan, 2);
n_modes_cb = size(Phi_cb, 2);
n_modes_full = size(Phi_full, 2);

% 归一化函数
normalize = @(v) v / norm(v);

% 截取缩聚自由度对应原始模态子向量
Phi_full_guyan = Phi_full(reduced_dofs_guyan, :);
Phi_full_cb = Phi_full(reduced_dofs_cb, :);

% 归一化所有模态
for i = 1:n_modes_full
    Phi_full(:, i) = normalize(Phi_full(:, i));
end
for i = 1:n_modes_guyan
    Phi_guyan(:, i) = normalize(Phi_guyan(:, i));
end
for i = 1:n_modes_cb
    Phi_cb(:, i) = normalize(Phi_cb(:, i));
end
for i = 1:n_modes_full
    Phi_full_guyan(:, i) = normalize(Phi_full_guyan(:, i));
    Phi_full_cb(:, i) = normalize(Phi_full_cb(:, i));
end

% 计算MAC矩阵函数
mac = @(v1,v2) (abs(v1'*v2)^2) / ((v1'*v1)*(v2'*v2));

% 计算 Guyan 缩聚空间 MAC 矩阵 (n_modes_full × n_modes_guyan)
MAC_guyan = zeros(n_modes_full, n_modes_guyan);
for i = 1:n_modes_full
    for j = 1:n_modes_guyan
        MAC_guyan(i,j) = mac(Phi_full_guyan(:, i), Phi_guyan(:, j));
    end
end

% 计算 CB 缩聚空间 MAC 矩阵 (n_modes_full × n_modes_cb)
MAC_cb = zeros(n_modes_full, n_modes_cb);
for i = 1:n_modes_full
    for j = 1:n_modes_cb
        MAC_cb(i,j) = mac(Phi_full_cb(:, i), Phi_cb(:, j));
    end
end

disp('Guyan 缩聚空间 MAC 矩阵:');
disp(MAC_guyan);

disp('CB 缩聚空间 MAC 矩阵:');
disp(MAC_cb);
