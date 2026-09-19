function S = selection_matrix(n, idx)
    % n: 输入向量长度
    % idx: 含0的索引向量，0表示该行全0
    
    m = length(idx);
    S = zeros(m, n);
    for i = 1:m
        if idx(i) ~= 0
            S(i, idx(i)) = 1;
        end
        % idx(i)==0时，S该行全0，代表不选任何元素
    end
end