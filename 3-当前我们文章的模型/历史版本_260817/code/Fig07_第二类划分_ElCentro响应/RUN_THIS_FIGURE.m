% RUN_THIS_FIGURE
% 独立生成小论文 Fig.7：第二类子结构划分的 El Centro 响应。
% 本文件只依赖同一图文件夹内的“输入数据”子目录。

scriptPath = mfilename('fullpath');
if isempty(scriptPath)
    error('Fig07:ScriptLocation', 'MATLAB cannot determine this script location.');
end
figureDir = fileparts(scriptPath);

sourceName = '第二类划分_ElCentro地震响应.csv';
inputPath = fullfile(figureDir, '输入数据', sourceName);
outputRoot = fullfile(figureDir, '输出');
pdfDir = fullfile(outputRoot, 'PDF');
pngDir = fullfile(outputRoot, 'PNG');
pdfPath = fullfile(pdfDir, 'fig07_eq_div2.pdf');
pngPath = fullfile(pngDir, 'fig07_eq_div2.png');
matPath = fullfile(outputRoot, 'plotted_data.mat');
auditPath = fullfile(outputRoot, 'data_audit.csv');

if ~isfile(inputPath)
    error('Fig07:MissingInput', 'Missing bundled input CSV: %s', inputPath);
end
if ~isfolder(pdfDir)
    mkdir(pdfDir);
end
if ~isfolder(pngDir)
    mkdir(pngDir);
end

plotFont = choose_plot_font();

raw = readmatrix(inputPath);
expectedSize = [40961, 10];
if ~isequal(size(raw), expectedSize)
    error('Fig07:InputShape', 'Expected 40961-by-10 data, received %d-by-%d.', size(raw, 1), size(raw, 2));
end
if ~all(isfinite(raw(:)))
    error('Fig07:FiniteData', 'The input CSV contains NaN or Inf.');
end

time_s = raw(:, 1);
expectedStep = 1 / 1024;
timeTolerance = 1e-12;
if abs(time_s(1)) > timeTolerance || abs(time_s(end) - 40) > timeTolerance
    error('Fig07:TimeRange', 'The time vector must start at 0 s and end at 40 s.');
end
stepError = max(abs(diff(time_s) - expectedStep));
if stepError > timeTolerance
    error('Fig07:TimeStep', 'The maximum time-step error is %.17g s.', stepError);
end

% response_mm 的维度依次为：时间点、楼层、方法。
% 方法顺序与CSV一致：Original、Guyan、Craig-Bampton。
response_mm = zeros(expectedSize(1), 3, 3);
for floorIndex = 1:3
    firstColumn = 2 + (floorIndex - 1) * 3;
    response_mm(:, floorIndex, :) = reshape( ...
        raw(:, firstColumn:(firstColumn + 2)), expectedSize(1), 1, 3);
end

plotted_data = struct();
plotted_data.figure_id = 'Fig07';
plotted_data.source_file = sourceName;
plotted_data.time_s = time_s;
plotted_data.response_mm = response_mm;
plotted_data.floor_numbers = [1, 3];
plotted_data.method_order_in_data = {'Original', 'Guyan', 'Craig-Bampton'};
plotted_data.local_windows_s = [10.0, 11.0; 21.5, 22.5];
plotted_data.full_history_stride = max(1, floor(numel(time_s) / 12000));
plotted_data.plot_font = plotFont;

write_data_audit(auditPath, size(raw, 1), size(raw, 2), ...
    time_s(1), time_s(end), expectedStep, stepError, all(isfinite(raw(:))), plotFont);

fig = figure( ...
    'Visible', 'off', ...
    'Color', 'white', ...
    'Renderer', 'painters', ...
    'Units', 'centimeters', ...
    'Position', [2, 2, 16.0, 9.70]);

% 两行分别为一层和三层；三列依次为全时程和两个局部窗。
positions = [ ...
    0.085, 0.565, 0.414, 0.320; ...
    0.539, 0.565, 0.180, 0.320; ...
    0.759, 0.565, 0.180, 0.320; ...
    0.085, 0.115, 0.414, 0.320; ...
    0.539, 0.115, 0.180, 0.320; ...
    0.759, 0.115, 0.180, 0.320];
windows = [10.0, 11.0; 21.5, 22.5];
floors = [1, 3];
panels = {'(a)', '(b)'};
axesHandles = gobjects(2, 3);
legendHandles = gobjects(1, 3);
axisTemplate = struct('axis_index', 0, 'floor_number', 0, ...
    'view_name', '', 'window_s', [0, 0], 'position', zeros(1, 4));
axesRecords = repmat(axisTemplate, 6, 1);
curveTemplate = struct('axis_index', 0, 'floor_number', 0, ...
    'view_name', '', 'method_name', '', 'input_column', 0, ...
    'x_data', [], 'y_data', [], 'color_rgb', zeros(1, 3), ...
    'line_style', '', 'marker', '', 'line_width', 0);
curveRecords = repmat(curveTemplate, 18, 1);
curveCounter = 0;
methodNames = {'Original', 'Craig-Bampton', 'Guyan'};

for row = 1:2
    floorValues = squeeze(response_mm(:, floors(row), :));

    ax = axes('Parent', fig, 'Position', positions((row - 1) * 3 + 1, :));
    axesHandles(row, 1) = ax;
    currentHandles = plot_three_methods(ax, time_s, floorValues, false);
    xlim(ax, [0, 40]);
    ylim(ax, padded_limits(floorValues));
    xticks(ax, 0:10:40);
    ylabel(ax, 'Displacement (mm)', 'Interpreter', 'latex');
    apply_axis_style(ax, plotFont);
    text(ax, 0.025, 0.92, panels{row}, ...
        'Units', 'normalized', ...
        'VerticalAlignment', 'top', ...
        'HorizontalAlignment', 'left', ...
        'FontName', plotFont, ...
        'FontSize', 9, ...
        'FontWeight', 'bold', ...
        'Interpreter', 'latex', ...
        'BackgroundColor', 'white', ...
        'Margin', 1);
    if row == 1
        legendHandles = currentHandles;
    else
        xlabel(ax, 'Time (s)', 'Interpreter', 'latex');
    end
    axisIndex = (row - 1) * 3 + 1;
    firstColumn = 2 + (floors(row) - 1) * 3;
    sourceColumns = firstColumn - 1 + [1, 3, 2];
    axesRecords(axisIndex) = make_axis_record( ...
        ax, axisIndex, floors(row), 'full', [0, 40]);
    newRecords = capture_curve_records( ...
        currentHandles, axisIndex, floors(row), 'full', methodNames, sourceColumns);
    curveRecords(curveCounter + (1:3)) = newRecords;
    curveCounter = curveCounter + 3;

    for windowIndex = 1:2
        window = windows(windowIndex, :);
        mask = time_s >= window(1) & time_s <= window(2);
        if nnz(mask) < 20
            error('Fig07:WindowSamples', 'The local window contains fewer than 20 samples.');
        end
        ax = axes('Parent', fig, 'Position', positions((row - 1) * 3 + 1 + windowIndex, :));
        axesHandles(row, 1 + windowIndex) = ax;
        localTime = time_s(mask);
        localValues = floorValues(mask, :);
        currentHandles = plot_three_methods(ax, localTime, localValues, true);
        xlim(ax, window);
        ylim(ax, padded_limits(localValues));
        xticks(ax, linspace(window(1), window(2), 3));
        apply_axis_style(ax, plotFont);
        if row == 2
            xlabel(ax, 'Time (s)', 'Interpreter', 'latex');
        end
        axisIndex = (row - 1) * 3 + 1 + windowIndex;
        viewNames = {'window_10_to_11_s', 'window_21_5_to_22_5_s'};
        axesRecords(axisIndex) = make_axis_record( ...
            ax, axisIndex, floors(row), viewNames{windowIndex}, window);
        newRecords = capture_curve_records( ...
            currentHandles, axisIndex, floors(row), viewNames{windowIndex}, ...
            methodNames, sourceColumns);
        curveRecords(curveCounter + (1:3)) = newRecords;
        curveCounter = curveCounter + 3;
    end
end

legendObject = legend(axesHandles(1, 1), legendHandles, ...
    {'Original', 'Craig--Bampton', 'Guyan'}, ...
    'Interpreter', 'latex', ...
    'FontName', plotFont, ...
    'FontSize', 9, ...
    'Orientation', 'horizontal', ...
    'NumColumns', 3, ...
    'Box', 'off');
legendObject.Units = 'normalized';
legendObject.Position = [0.300, 0.925, 0.400, 0.045];

plotted_data.column_width_ratio = [2.30, 1.00, 1.00];
plotted_data.axes = axesRecords;
plotted_data.curves = curveRecords;
save(matPath, 'plotted_data', '-v7');

drawnow;
exportgraphics(fig, pdfPath, 'ContentType', 'vector', 'BackgroundColor', 'white');
exportgraphics(fig, pngPath, 'Resolution', 600, 'BackgroundColor', 'white');
close(fig);

pdfInfo = dir(pdfPath);
pngInfo = dir(pngPath);
if isempty(pdfInfo) || pdfInfo.bytes < 1000
    error('Fig07:PDFExport', 'The vector PDF was not created or is unexpectedly small.');
end
if isempty(pngInfo) || pngInfo.bytes < 10000
    error('Fig07:PNGExport', 'The 600-dpi PNG was not created or is unexpectedly small.');
end

fprintf('Fig.7 generated successfully.\n');
fprintf('PDF: %s\n', pdfPath);
fprintf('PNG: %s\n', pngPath);
fprintf('Saved data: %s\n', matPath);
fprintf('Data audit: %s\n', auditPath);
fprintf('Plot font: %s\n', plotFont);


function handles = plot_three_methods(ax, time_s, values, isLocal)
% 三种方法的身份固定为 Original、Craig-Bampton、Guyan。
    methodColumns = [1, 3, 2];
    colors = [85, 85, 85; 238, 102, 119; 68, 119, 170] / 255;
    lineStyles = {'--', '-', '-.'};
    markers = {'o', 's', '^'};
    drawOrder = [3, 2, 1];
    handles = gobjects(1, 3);

    if isLocal
        stride = 1;
        lineWidth = 1.10;
    else
        stride = max(1, floor(numel(time_s) / 12000));
        lineWidth = 0.85;
    end
    selected = 1:stride:numel(time_s);
    if selected(end) ~= numel(time_s)
        selected(end + 1) = numel(time_s);
    end
    markerIndices = unique(round(linspace(1, numel(selected), 9)));

    hold(ax, 'on');
    for methodIndex = drawOrder
        handles(methodIndex) = plot(ax, ...
            time_s(selected), values(selected, methodColumns(methodIndex)), ...
            'Color', colors(methodIndex, :), ...
            'LineStyle', lineStyles{methodIndex}, ...
            'LineWidth', lineWidth);
        if isLocal
            set(handles(methodIndex), ...
                'Marker', markers{methodIndex}, ...
                'MarkerIndices', markerIndices, ...
                'MarkerSize', 3.2, ...
                'MarkerFaceColor', 'white', ...
                'MarkerEdgeColor', colors(methodIndex, :));
        else
            set(handles(methodIndex), 'Marker', 'none');
        end
    end
    hold(ax, 'off');
end


function limits = padded_limits(values)
    lower = min(values(:));
    upper = max(values(:));
    span = upper - lower;
    if span <= eps(max(abs([lower, upper])))
        span = max(abs(lower), 1);
    end
    limits = [lower - 0.08 * span, upper + 0.08 * span];
end


function apply_axis_style(ax, plotFont)
    set(ax, ...
        'FontName', plotFont, ...
        'FontSize', 9, ...
        'TickLabelInterpreter', 'latex', ...
        'TickDir', 'in', ...
        'TickLength', [0.012, 0.012], ...
        'Box', 'on', ...
        'LineWidth', 0.8, ...
        'Layer', 'top', ...
        'XGrid', 'off', ...
        'YGrid', 'off', ...
        'XMinorTick', 'off', ...
        'YMinorTick', 'off');
end


function write_data_audit(path, rows, columns, startTime, endTime, expectedStep, stepError, finiteFlag, plotFont)
    fileId = fopen(path, 'w');
    if fileId < 0
        error('Fig07:AuditWrite', 'Cannot create data_audit.csv.');
    end
    cleanup = onCleanup(@() fclose(fileId));
    fprintf(fileId, 'metric,value,requirement,status\n');
    fprintf(fileId, 'row_count,%d,40961,PASS\n', rows);
    fprintf(fileId, 'column_count,%d,10,PASS\n', columns);
    fprintf(fileId, 'time_start_s,%.17g,0,PASS\n', startTime);
    fprintf(fileId, 'time_end_s,%.17g,40,PASS\n', endTime);
    fprintf(fileId, 'expected_step_s,%.17g,0.0009765625,PASS\n', expectedStep);
    fprintf(fileId, 'maximum_step_error_s,%.17g,<=1e-12,PASS\n', stepError);
    fprintf(fileId, 'all_values_finite,%d,1,PASS\n', finiteFlag);
    fprintf(fileId, 'plot_font,%s,recorded,PASS\n', plotFont);
    clear cleanup;
end


function plotFont = choose_plot_font()
    installedFonts = listfonts;
    if any(strcmpi(installedFonts, 'CMU Serif'))
        plotFont = 'CMU Serif';
    elseif any(strcmpi(installedFonts, 'Times New Roman'))
        plotFont = 'Times New Roman';
    else
        plotFont = 'Serif';
    end
end


function record = make_axis_record(ax, axisIndex, floorNumber, viewName, window)
    record = struct( ...
        'axis_index', axisIndex, ...
        'floor_number', floorNumber, ...
        'view_name', viewName, ...
        'window_s', window, ...
        'position', get(ax, 'Position'));
end


function records = capture_curve_records(handles, axisIndex, floorNumber, viewName, methodNames, sourceColumns)
    template = struct('axis_index', 0, 'floor_number', 0, ...
        'view_name', '', 'method_name', '', 'input_column', 0, ...
        'x_data', [], 'y_data', [], 'color_rgb', zeros(1, 3), ...
        'line_style', '', 'marker', '', 'line_width', 0);
    records = repmat(template, 3, 1);
    for methodIndex = 1:3
        records(methodIndex).axis_index = axisIndex;
        records(methodIndex).floor_number = floorNumber;
        records(methodIndex).view_name = viewName;
        records(methodIndex).method_name = methodNames{methodIndex};
        records(methodIndex).input_column = sourceColumns(methodIndex);
        xData = get(handles(methodIndex), 'XData');
        yData = get(handles(methodIndex), 'YData');
        records(methodIndex).x_data = xData(:);
        records(methodIndex).y_data = yData(:);
        records(methodIndex).color_rgb = get(handles(methodIndex), 'Color');
        records(methodIndex).line_style = get(handles(methodIndex), 'LineStyle');
        records(methodIndex).marker = get(handles(methodIndex), 'Marker');
        records(methodIndex).line_width = get(handles(methodIndex), 'LineWidth');
    end
end
