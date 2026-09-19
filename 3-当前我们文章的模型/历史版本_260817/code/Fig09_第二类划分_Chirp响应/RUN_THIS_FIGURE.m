%% Fig. 9 - 第二类子结构划分的 Chirp 响应
% 本脚本只读取同一文件夹内自带的 CSV，并把结果写入同一文件夹的“输出”。

scriptFile = mfilename('fullpath');
baseDir = fileparts(scriptFile);
inputFile = fullfile(baseDir, '输入数据', '第二类划分_Chirp响应.csv');
outputDir = fullfile(baseDir, '输出');
pdfDir = fullfile(outputDir, 'PDF');
pngDir = fullfile(outputDir, 'PNG');

if ~isfile(inputFile)
    error('Fig09:MissingInput', '缺少输入文件：%s', inputFile);
end
if ~isfolder(outputDir), mkdir(outputDir); end
if ~isfolder(pdfDir), mkdir(pdfDir); end
if ~isfolder(pngDir), mkdir(pngDir); end

data = readmatrix(inputFile, 'NumHeaderLines', 1);
expectedRows = 40961;
expectedColumns = 10;
expectedStep = 1 / 1024;

if ~isequal(size(data), [expectedRows, expectedColumns])
    error('Fig09:BadSize', '输入数据应为 40961×10，实际为 %d×%d。', size(data, 1), size(data, 2));
end
if ~all(isfinite(data(:)))
    error('Fig09:NonFinite', '输入数据含有 NaN 或 Inf。');
end

time = data(:, 1);
timeStepError = max(abs(diff(time) - expectedStep));
if abs(time(1)) > 1e-14 || abs(time(end) - 40) > 1e-14
    error('Fig09:BadTimeRange', '时间范围应为 0–40 s。');
end
if timeStepError > 1e-14
    error('Fig09:BadTimeStep', '时间步长不是 1/1024 s，最大误差为 %.17g。', timeStepError);
end

% CSV 每层三列的顺序是 Original、Guyan、Craig-Bampton。
floorColumns = [2, 3, 4; 8, 9, 10];
localWindows = [13, 14; 38, 38.3];
panelLabels = {'(a)', '(b)'};

availableFonts = listfonts;
if any(strcmpi(availableFonts, 'CMU Serif'))
    fontName = 'CMU Serif';
elseif any(strcmpi(availableFonts, 'Times New Roman'))
    fontName = 'Times New Roman';
else
    fontName = 'Serif';
end

fig = figure('Color', 'w', 'Units', 'inches', 'Position', [1, 1, 6.30, 3.82]);
legendHandles = gobjects(3, 1);
curveRecords = struct('axis_index', {}, 'floor_number', {}, 'view_name', {}, ...
    'method_name', {}, 'source_column', {}, 'sample_indices', {}, ...
    'x_data', {}, 'y_data', {}, 'line_style', {}, 'marker_name', {}, 'color_rgb', {});
axisRecords = struct('axis_index', {}, 'floor_number', {}, 'view_name', {}, ...
    'x_limits', {}, 'sample_indices', {});
axisCounter = 0;

% 正文全宽图的三列宽度比为 2.30:1:1。
xPositions = [0.105, 0.5742, 0.8121];
axisWidths = [0.4092, 0.1779, 0.1779];
yPositions = [0.54, 0.13];
axisHeight = 0.31;

for row = 1:2
    values = data(:, floorColumns(row, :));

    axisCounter = axisCounter + 1;
    fullIndices = fullSampleIndices(numel(time));
    fullAxis = axes(fig, 'Position', [xPositions(1), yPositions(row), axisWidths(1), axisHeight]);
    [fullHandles, fullRecords] = drawThreeMethods(fullAxis, time, data, ...
        floorColumns(row, :), fullIndices, false, axisCounter, row * 2 - 1, 'full');
    curveRecords = [curveRecords; fullRecords(:)]; %#ok<AGROW>
    if row == 1
        legendHandles = fullHandles;
    end
    xlim(fullAxis, [0, 40]);
    xticks(fullAxis, 0:10:40);
    ylim(fullAxis, limitsWithMargin(values));
    ylabel(fullAxis, 'Displacement (mm)', 'Interpreter', 'latex');
    styleAxis(fullAxis, fontName);
    text(fullAxis, 0.025, 0.92, panelLabels{row}, 'Units', 'normalized', ...
        'HorizontalAlignment', 'left', 'VerticalAlignment', 'top', ...
        'FontName', fontName, 'FontSize', 9, 'FontWeight', 'bold', 'Interpreter', 'latex', ...
        'BackgroundColor', 'w', 'Margin', 1);
    axisRecords(axisCounter) = makeAxisRecord(axisCounter, row * 2 - 1, ...
        'full', [0, 40], fullIndices); %#ok<SAGROW>

    for windowIndex = 1:2
        window = localWindows(windowIndex, :);
        mask = time >= window(1) & time <= window(2);
        if nnz(mask) < 20
            error('Fig09:ShortWindow', '局部时间窗内样本不足。');
        end
        axisCounter = axisCounter + 1;
        localIndices = find(mask);
        localAxis = axes(fig, 'Position', [xPositions(windowIndex + 1), ...
            yPositions(row), axisWidths(windowIndex + 1), axisHeight]);
        [~, localRecords] = drawThreeMethods(localAxis, time, data, ...
            floorColumns(row, :), localIndices, true, axisCounter, row * 2 - 1, ...
            sprintf('local_%d', windowIndex));
        curveRecords = [curveRecords; localRecords(:)]; %#ok<AGROW>
        xlim(localAxis, window);
        xticks(localAxis, linspace(window(1), window(2), 3));
        ylim(localAxis, limitsWithMargin(values(mask, :)));
        styleAxis(localAxis, fontName);
        axisRecords(axisCounter) = makeAxisRecord(axisCounter, row * 2 - 1, ...
            sprintf('local_%d', windowIndex), window, localIndices); %#ok<SAGROW>
        if windowIndex == 1
            xtickformat(localAxis, '%.1f');
        else
            xtickformat(localAxis, '%.2f');
        end
        if row == 2
            xlabel(localAxis, 'Time (s)', 'Interpreter', 'latex');
        end
    end

    if row == 2
        xlabel(fullAxis, 'Time (s)', 'Interpreter', 'latex');
    end
end

methodNames = {'Original', 'Craig--Bampton', 'Guyan'};
legendBox = legend(legendHandles, methodNames, 'Orientation', 'horizontal', ...
    'Box', 'off', 'Interpreter', 'latex', 'FontName', fontName, ...
    'FontSize', 9, 'AutoUpdate', 'off', 'Location', 'none');
set(legendBox, 'Units', 'normalized', 'Position', [0.31, 0.925, 0.38, 0.045]);

pdfFile = fullfile(pdfDir, 'fig09_chirp_div2.pdf');
pngFile = fullfile(pngDir, 'fig09_chirp_div2.png');
exportgraphics(fig, pdfFile, 'ContentType', 'vector', 'BackgroundColor', 'white');
exportgraphics(fig, pngFile, 'Resolution', 600, 'BackgroundColor', 'white');

plotted_data = struct();
plotted_data.figure_id = 'Fig09';
plotted_data.input_file = '第二类划分_Chirp响应.csv';
plotted_data.input_data = data;
plotted_data.floor_numbers = [1, 3];
plotted_data.floor_columns = floorColumns;
plotted_data.local_windows_s = localWindows;
plotted_data.method_order_in_csv = {'Original', 'Guyan', 'Craig-Bampton'};
plotted_data.method_order_in_figure = {'Original', 'Craig-Bampton', 'Guyan'};
plotted_data.actual_font_name = fontName;
plotted_data.axes = axisRecords;
plotted_data.curves = curveRecords;
save(fullfile(outputDir, 'plotted_data.mat'), 'plotted_data', '-v7.3');

auditFile = fullfile(outputDir, 'data_audit.csv');
auditId = fopen(auditFile, 'w');
if auditId < 0
    error('Fig09:AuditWrite', '无法写入 data_audit.csv。');
end
fprintf(auditId, 'metric,value,expected,status\n');
fprintf(auditId, 'rows,%d,%d,PASS\n', size(data, 1), expectedRows);
fprintf(auditId, 'columns,%d,%d,PASS\n', size(data, 2), expectedColumns);
fprintf(auditId, 'time_start_s,%.17g,0,PASS\n', time(1));
fprintf(auditId, 'time_end_s,%.17g,40,PASS\n', time(end));
fprintf(auditId, 'time_step_s,%.17g,%.17g,PASS\n', median(diff(time)), expectedStep);
fprintf(auditId, 'max_time_step_error,%.17g,<=1e-14,PASS\n', timeStepError);
fprintf(auditId, 'finite_values,%d,%d,PASS\n', nnz(isfinite(data)), numel(data));
fprintf(auditId, 'axes_count,%d,6,PASS\n', numel(axisRecords));
fprintf(auditId, 'curves_count,%d,18,PASS\n', numel(curveRecords));
fprintf(auditId, 'font_used,%s,CMU Serif or fallback,PASS\n', fontName);
fclose(auditId);

fprintf('Fig. 9 绘制完成。\nPDF：%s\nPNG：%s\n', pdfFile, pngFile);

function [handles, records] = drawThreeMethods(ax, time, rawData, csvColumns, ...
        sampleIndices, isLocal, axisIndex, floorNumber, viewName)
    % 由源列映射到 Original、Craig-Bampton、Guyan。
    sourceColumns = csvColumns([1, 3, 2]);
    x = time(sampleIndices);
    colors = [85, 85, 85; 238, 102, 119; 68, 119, 170] / 255;
    lineStyles = {'--', '-', '-.'};
    markers = {'o', 's', '^'};
    if isLocal
        lineWidth = 1.10;
        markerCount = 9;
        actualMarkers = markers;
    else
        lineWidth = 0.85;
        markerCount = 0;
        actualMarkers = {'none', 'none', 'none'};
    end
    handles = gobjects(3, 1);
    methodNames = {'Original', 'Craig-Bampton', 'Guyan'};
    records = repmat(struct('axis_index', 0, 'floor_number', 0, 'view_name', '', ...
        'method_name', '', 'source_column', 0, 'sample_indices', [], ...
        'x_data', [], 'y_data', [], 'line_style', '', 'marker_name', '', ...
        'color_rgb', []), 3, 1);
    hold(ax, 'on');
    for method = 1:3
        y = rawData(sampleIndices, sourceColumns(method));
        handles(method) = plot(ax, x, y, ...
            'Color', colors(method, :), 'LineStyle', lineStyles{method}, ...
            'LineWidth', lineWidth, 'Marker', actualMarkers{method}, ...
            'MarkerSize', 3.2, 'MarkerFaceColor', 'w', ...
            'MarkerEdgeColor', colors(method, :));
        if markerCount > 0
            handles(method).MarkerIndices = unique(round(linspace(1, numel(x), markerCount)));
        end
        records(method).axis_index = axisIndex;
        records(method).floor_number = floorNumber;
        records(method).view_name = viewName;
        records(method).method_name = methodNames{method};
        records(method).source_column = sourceColumns(method);
        records(method).sample_indices = sampleIndices;
        records(method).x_data = handles(method).XData(:);
        records(method).y_data = handles(method).YData(:);
        records(method).line_style = handles(method).LineStyle;
        records(method).marker_name = handles(method).Marker;
        records(method).color_rgb = handles(method).Color;
    end
    hold(ax, 'off');
end

function indices = fullSampleIndices(sampleCount)
    stride = max(1, floor(sampleCount / 12000));
    indices = unique([(1:stride:sampleCount)'; sampleCount]);
end

function record = makeAxisRecord(axisIndex, floorNumber, viewName, xLimits, sampleIndices)
    record = struct('axis_index', axisIndex, 'floor_number', floorNumber, ...
        'view_name', viewName, 'x_limits', xLimits, 'sample_indices', sampleIndices);
end

function limits = limitsWithMargin(values)
    low = min(values(:));
    high = max(values(:));
    span = high - low;
    if span <= eps(max(abs([low, high, 1])))
        span = max(abs(low), 1);
    end
    limits = [low - 0.08 * span, high + 0.08 * span];
end

function styleAxis(ax, fontName)
    set(ax, 'Box', 'on', 'Color', 'w', 'LineWidth', 0.75, ...
        'TickDir', 'in', 'TickLength', [0.018, 0.018], ...
        'FontName', fontName, 'FontSize', 9, ...
        'TickLabelInterpreter', 'latex', 'XGrid', 'off', 'YGrid', 'off');
end
