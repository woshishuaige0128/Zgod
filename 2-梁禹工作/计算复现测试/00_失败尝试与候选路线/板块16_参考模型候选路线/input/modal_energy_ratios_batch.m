function ratios_all = modal_energy_ratios_batch(Phi, M)
    % 批量计算所有模态的自由度模态能量占比
    %
    % 输入：
    %   Phi - 模态矩阵 (n自由度 x m模态数)，每列是一个模态振型
    %   M   - 质量矩阵 (n x n)，假设对角矩阵
    %
    % 输出：
    %   ratios_all - 矩阵 (n x m)，每列对应一个模态的能量占比
    
    m_diag = diag(M);             % 质量矩阵对角元素 (n x 1)
    n_modes = size(Phi, 2);       % 模态数量
    n_dofs = size(Phi, 1);        % 自由度数量
    
    ratios_all = zeros(n_dofs, n_modes);
    
    for i = 1:n_modes
        phi = Phi(:, i);
        energy_per_dof = (phi.^2) .* m_diag;
        total_energy = sum(energy_per_dof);
        ratios_all(:, i) = energy_per_dof / total_energy;
    end
end
