function Gamma = modal_participation_factors(phi, M, direction)
    % phi: 模态向量 (columns)
    % M: 质量矩阵
    % direction: 力的方向（n×1 向量），如重力方向 ones(n,1)
    
    Gamma = phi' * M * direction;
end
