% 假设工作区中已有 stab_o、stab_C、stab_g 三个矩阵

figure('Units', 'pixels', 'Position', [100 100 600 300]);

hold on;
grid on;
axis equal;

xlabel('τ1');
ylabel('τ2');
title('稳定域');

% 定义颜色、点形状、图例文字
colors = {'b', 'r', 'g'};
markers = {'o', 's', '^'};
labels = {'原结构', 'Craig–Bampton', 'Guyan'};

% 三个数据组合成 cell 数组
stabs = {stab_o, stab_C, stab_g};

% 存储每条线的绘图句柄用于 legend
plot_handles = [];

for i = 1:3
    % 提取稳定区域边界
    Ss = double(stabs{i});
    bw = (Ss > 0) & (Ss < 1);
    B = bwboundaries(bw, 'noholes');

    if ~isempty(B)
        boundary = B{1}; % 提取主边界
        y = boundary(:,1);
        x = boundary(:,2);

        % 去掉接近坐标轴的点（可选）
        keep = (x > 1) & (y > 1);
        x = x(keep);
        y = y(keep);

        % 绘图并保存句柄
        h = plot(x, y, '-', ...
            'Color', colors{i}, ...
            'LineWidth', 1, ...
            'Marker', markers{i}, ...
            'MarkerEdgeColor', colors{i}, ...
            'MarkerFaceColor', 'none', ... % 中空标记
            'MarkerIndices', 1:length(x), ...
            'MarkerSize', 6);
        plot_handles(end+1) = h;
    end
end

% 正确设置图例（确保 plot_handles 不为空且为 line 对象）
if ~isempty(plot_handles)
    legend(plot_handles, labels, 'Location', 'northeast');
end

xlim([1 size(stab_o,2)]);
ylim([1 size(stab_o,1)]);
axis tight
