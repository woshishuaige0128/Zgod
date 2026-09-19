% 提取时间序列数据
time = simout3.Time;                % 时间向量
data_matrix = simout3.Data;         % N×3数据矩阵

% 创建对比图
figure('Color', 'white', 'Position', [100 100 800 450]); % 调整画布比例

% 三线差异化配置
h1 = plot(time, data_matrix(:,1),...
    'LineWidth', 1.0,...              % 最粗基准线
    'LineStyle', '-',...              % 实线
    'Color', [0 0.2 0.8],...          % 深蓝
    'DisplayName', 'origin');

hold on

h2 = plot(time, data_matrix(:,2),...
    'LineWidth', 1.0,...
    'LineStyle', '-',...             % 长虚线
    'Color', [0.8 0.1 0.1],...        % 深红
    'DisplayName', 'Guyan');

h3 = plot(time, data_matrix(:,3),...
    'LineWidth', 1.0,...
    'LineStyle', '-.',...              % 点线
    'Color', [0.1 0.6 0.2],...        % 深绿
    'DisplayName', 'Craig-Bampton');

hold off

% 坐标轴精细调节
ax = gca;
ax.XLim = [min(time) max(time)];      % 精确时间范围
%ax.YLim = [floor(min(data_matrix(:))),... % 动态下界
%          ceil(max(data_matrix(:)))]; % 动态上界
ax.TickDir = 'out';                   % 刻度外显
ax.Box = 'on';                        % 边框增强

% 标注系统
xlabel('时间 (s)', 'FontSize', 12, 'FontName', 'SimHei');
ylabel('响应幅值 (mm)', 'FontSize', 12, 'FontName', 'SimHei');
title('结构动力学响应对比', 'FontSize', 13, 'FontName', 'SimHei');

% 专业图例配置
legend([h1, h2, h3],...
    'FontSize', 10,...
    'Location', 'best',...
    'FontName', 'Times New Roman',...
    'EdgeColor', 'none');             % 去除图例边框

% 增强可读性配置
set(ax, 'Layer', 'top')               % 刻度置于顶层
set(ax, 'LineWidth', 1.2)             % 坐标轴线宽

saveas(gcf, 'C:\Users\liangyu\Desktop\新建文件夹 (3)\mode_b_verify_y_10mm_sum2-3.emf','meta');