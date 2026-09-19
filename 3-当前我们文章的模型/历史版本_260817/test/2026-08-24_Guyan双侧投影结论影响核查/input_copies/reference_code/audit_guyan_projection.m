%% 第二章 Guyan 合同投影与现有单侧消元实现的只读对照
% 本脚本只读取 PDmonicanshu.m 生成的工作区矩阵，不保存或改写原工程文件。

clear;
clc;

workspace_root = 'D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master';
parameter_dir = fullfile(workspace_root, 'figure', ...
    '第3章_缩聚对试验精度的影响', '原始来源副本', ...
    '模型与参数原件');

old_dir = pwd;
cleanup_obj = onCleanup(@() cd(old_dir)); %#ok<NASGU>
cd(parameter_dir);
run('PDmonicanshu.m');

full_lambda = sort(real(eig(KRrt, MRrt)));
full_frequency_hz = sqrt(full_lambda(full_lambda > 0)) / (2*pi);
fprintf('FULL f1=%.8f f2=%.8f Hz\n', ...
    full_frequency_hz(1), full_frequency_hz(2));

partitions = {
    struct('name', 'CASE_I', ...
           'master', [1, 6, 11, 4, 9, 14], ...
           'slave',  [2, 3, 5, 7, 8, 10, 12, 13, 15]), ...
    struct('name', 'CASE_II', ...
           'master', [1, 11, 4, 9, 14], ...
           'slave',  [2, 3, 5, 6, 7, 8, 10, 12, 13, 15]) ...
    };

for case_index = 1:numel(partitions)
    p = partitions{case_index};
    order = [p.master, p.slave];
    M = MRrt(order, order);
    C = CRrt(order, order);
    K = KRrt(order, order);
    n_master = numel(p.master);

    mm = 1:n_master;
    ss = (n_master + 1):size(K, 1);
    psi = -(K(ss, ss) \ K(ss, mm));
    T = [eye(n_master); psi];

    M_legacy = M(mm, mm) - M(mm, ss) * (K(ss, ss) \ K(ss, mm));
    C_legacy = C(mm, mm) - C(mm, ss) * (K(ss, ss) \ K(ss, mm));
    K_legacy = K(mm, mm) - K(mm, ss) * (K(ss, ss) \ K(ss, mm));

    M_projected = T' * M * T;
    C_projected = T' * C * T;
    K_projected = T' * K * T;

    relative_M = norm(M_legacy - M_projected, 'fro') / norm(M_projected, 'fro');
    relative_C = norm(C_legacy - C_projected, 'fro') / norm(C_projected, 'fro');
    relative_K = norm(K_legacy - K_projected, 'fro') / norm(K_projected, 'fro');

    lambda_legacy = sort(real(eig(K_legacy, M_legacy)));
    lambda_projected = sort(real(eig(K_projected, M_projected)));
    frequency_legacy_hz = sqrt(lambda_legacy(lambda_legacy > 0)) / (2*pi);
    frequency_projected_hz = sqrt(lambda_projected(lambda_projected > 0)) / (2*pi);

    fprintf(['%s relM=%.12g relC=%.12g relK=%.12g ' ...
             'legacy=[%.8f %.8f] projected=[%.8f %.8f] Hz\n'], ...
        p.name, relative_M, relative_C, relative_K, ...
        frequency_legacy_hz(1), frequency_legacy_hz(2), ...
        frequency_projected_hz(1), frequency_projected_hz(2));
end
