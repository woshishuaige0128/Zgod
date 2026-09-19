% 输入数据：
% Phi: n x m 矩阵，每列是一个模态向量
% T: r x n 选择矩阵，选出主自由度

function MPF = calc_MPF(Phi, T)
    % Phi: n x m, 模态矩阵
    % T: r x n, 主自由度选择矩阵
    
    [n, m] = size(Phi);
    [r, nT] = size(T);
    if n ~= nT
        error('主自由度选择矩阵T列数应等于模态向量自由度数n');
    end
    
    MPF = zeros(m,1); % 初始化存储MPF
    
    for i = 1:m
        phi_i = Phi(:,i);              % 第i阶模态向量
        phi_i_reduced = T * phi_i;    % 主自由度投影
        
        MPF(i) = norm(phi_i_reduced)^2 / norm(phi_i)^2; % 计算MPF_i
    end
end
