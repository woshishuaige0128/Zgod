% 假设有两个振型矩阵 mode1 和 mode2，每一列代表一个振型
mode1 = V1(1:2,1:2);
mode2 = V2(1:2,1:2);
% 计算振型矩阵的尺寸
[numNodes, numModes1] = size(mode1);
[~, numModes2] = size(mode2);
% 初始化模态置信度矩阵
MAC = zeros(numModes1, numModes2);
% 计算每对振型之间的模态置信度
for i = 1:numModes1
    for j = 1:numModes2
        % 计算模态向量之间的内积
        innerProduct = abs(mode1(:, i)' * mode2(:, j));
        % 计算每个振型的能量
        energyMode1 = abs(mode1(:, i)' * mode1(:, i));
        energyMode2 = abs(mode2(:, j)' * mode2(:, j));
        % 计算模态置信度
        MAC(i, j) = innerProduct^2 / (energyMode1 * energyMode2);
    end
end
% 打印模态置信度矩阵
disp(MAC);