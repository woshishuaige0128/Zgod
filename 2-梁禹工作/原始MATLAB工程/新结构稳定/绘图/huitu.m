%load('guyan_PD.mat')
Ss = double(stab);
Ss(Ss==0) = 2;
bw = (Ss > 0) & (Ss < 1);
bw_1 = Ss < 1;
% 显示所有点灰色，<1 的点蓝色
[nRows, nCols] = size(Ss);
[x, y] = meshgrid(1:nCols, 1:nRows);
x = x(:); y = y(:); z = Ss(:);

figure;
scatter(x, y, 10, [0.8 0.8 0.8], 'filled'); hold on;
scatter(x(z<1), y(z<1), 20, 'b', 'filled');

% 使用 contour 提取边界
hold on;
[~, h] = contour(bw, [1 1], 'r', 'LineWidth', 2);

xlabel('z^(-j)（一层位移）');
ylabel('z^(-l)（二层位移）');
title('值 < 1 区域的边界线');
legend('所有点', '值 < 1', '边界线');
axis equal;
grid on;