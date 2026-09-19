% 提取时间序列数据
time = simout.Time;                % 时间向量
data_matrix = simout.Data;         % N×3 数据矩阵（对应三层位移）

% 创建对比图
figure('Color', 'white', 'Position', [100 100 800 450]); % 调整画布比例

% 三线差异化配置
h1 = plot(time, data_matrix(:,1), ...
    'LineWidth', 1.0, ...
    'LineStyle', '-', ...
    'Color', [0 0.2 0.8], ...
    'DisplayName', '一层');         % 深蓝线

hold on;

h2 = plot(time, data_matrix(:,2), ...
    'LineWidth', 1.0, ...
    'LineStyle', '-', ...
    'Color', [0.8 0.1 0.1], ...
    'DisplayName', '二层');         % 深红线

h3 = plot(time, data_matrix(:,3), ...
    'LineWidth', 1.0, ...
    'LineStyle', '-.', ...
    'Color', [0.1 0.6 0.2], ...
    'DisplayName', '三层');         % 深绿线

hold off;

% 坐标轴精细调节
ax = gca;
ax.XLim = [min(time) max(time)];
% ax.YLim = [floor(min(data_matrix(:))), ceil(max(data_matrix(:)))]; % 如需动态调节Y轴

ax.TickDir = 'out';
ax.Box = 'on';
set(ax, 'Layer', 'top');
set(ax, 'LineWidth', 1.2);

% 标注系统（中文字体兼容）
xlabel('时间 (s)', 'FontSize', 12, 'FontName', 'SimHei');
ylabel('响应幅值 (m)', 'FontSize', 12, 'FontName', 'SimHei');
title('结构动力学响应对比', 'FontSize', 13, 'FontName', 'SimHei');

% 专业图例配置（推荐方式：自动从 DisplayName 获取）
legend('show', ...
    'FontSize', 10, ...
    'Location', 'best', ...
    'FontName', 'SimHei', ...       % 支持中文显示
    'EdgeColor', 'none');

% 保存为高质量矢量图（EMF格式）