function MAC_matrix = compute_MAC(phi1, phi2)
    % phi1, phi2: 模态矩阵（列为模态）
    % 返回 MAC 矩阵，phi1 的第 i 模态 vs phi2 的第 j 模态

    n1 = size(phi1, 2);
    n2 = size(phi2, 2);
    MAC_matrix = zeros(n1, n2);
    
    for i = 1:n1
        for j = 1:n2
            num = abs(phi1(:,i)' * phi2(:,j))^2;
            den = (phi1(:,i)' * phi1(:,i)) * (phi2(:,j)' * phi2(:,j));
            MAC_matrix(i,j) = num / den;
        end
    end
end
