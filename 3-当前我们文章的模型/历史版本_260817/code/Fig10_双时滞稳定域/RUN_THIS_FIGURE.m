%% RUN_THIS_FIGURE
% 读取本文件夹自带的六份论文矢量边界数据，绘制小论文 Fig. 10。
% 运行本文件不会读取本文件夹以外的任何文件。

scriptDir = fileparts(mfilename('fullpath'));
dataDir = fullfile(scriptDir, '输入数据');
outputDir = fullfile(scriptDir, '输出');
pdfDir = fullfile(outputDir, 'PDF');
pngDir = fullfile(outputDir, 'PNG');

ensureDirectory(outputDir);
ensureDirectory(pdfDir);
ensureDirectory(pngDir);

curveSpec = buildCurveSpecification();
plottedData = repmat(emptyCurveRecord(), numel(curveSpec), 1);
auditRows = repmat(emptyAuditRecord(), numel(curveSpec), 1);
plotFontName = chooseAvailableSerifFont();

for curveIndex = 1:numel(curveSpec)
    spec = curveSpec(curveIndex);
    inputPath = fullfile(dataDir, spec.fileName);
    tableData = readAndValidateCurve(inputPath, spec);

    record = emptyCurveRecord();
    record.figureId = spec.figureId;
    record.method = spec.method;
    record.sourceFile = spec.fileName;
    record.point_order = tableData.point_order;
    record.tau1_step = tableData.tau1_step;
    record.tau2_step = tableData.tau2_step;
    record.tau1_ms = stepToMilliseconds(tableData.tau1_step);
    record.tau2_ms = stepToMilliseconds(tableData.tau2_step);
    plottedData(curveIndex) = record;

    auditRows(curveIndex) = makeAuditRecord(record);
end

if sum([auditRows.point_count]) ~= 386
    error('Fig10:TotalPointCount', '六条边界的点数总和不是 386。');
end

fig = figure( ...
    'Color', 'white', ...
    'Units', 'inches', ...
    'Position', [1.0, 1.0, 6.30, 2.72], ...
    'PaperPositionMode', 'auto');
cleanupFigure = onCleanup(@() closeFigureIfValid(fig));

axesHandles = gobjects(2, 1);
axesHandles(1) = axes(fig, 'Position', [0.105, 0.180, 0.390, 0.650]);
axesHandles(2) = axes(fig, 'Position', [0.585, 0.180, 0.390, 0.650]);

allY = vertcat(plottedData.tau2_ms);
sharedYMaximum = max(allY) * 1.10;
methodOrder = ["Original", "Craig-Bampton", "Guyan"];
panelIds = ["4-4", "4-5"];
panelLabels = ["(a)", "(b)"];
legendHandles = gobjects(3, 1);

for panelIndex = 1:2
    ax = axesHandles(panelIndex);
    hold(ax, 'on');
    panelXMaximum = 0;

    for methodIndex = 1:numel(methodOrder)
        recordIndex = findCurve(plottedData, panelIds(panelIndex), methodOrder(methodIndex));
        record = plottedData(recordIndex);
        style = styleForMethod(record.method);
        markerIndices = unique(round(linspace(1, numel(record.tau1_ms), min(9, numel(record.tau1_ms)))));

        lineHandle = plot(ax, record.tau1_ms, record.tau2_ms, ...
            'Color', style.color, ...
            'LineStyle', style.lineStyle, ...
            'LineWidth', 1.2, ...
            'Marker', style.marker, ...
            'MarkerIndices', markerIndices, ...
            'MarkerSize', 4, ...
            'MarkerFaceColor', 'white', ...
            'MarkerEdgeColor', style.color, ...
            'DisplayName', style.legendLabel);

        % 保存图线对象真正接收到的坐标，而不是只保存绘图前的中间变量。
        plottedData(recordIndex).plotted_x_ms = lineHandle.XData(:);
        plottedData(recordIndex).plotted_y_ms = lineHandle.YData(:);

        panelXMaximum = max(panelXMaximum, max(record.tau1_ms));
        if panelIndex == 1
            legendHandles(methodIndex) = lineHandle;
        end
    end

    hold(ax, 'off');
    set(ax, ...
        'FontName', plotFontName, ...
        'FontSize', 9, ...
        'TickLabelInterpreter', 'latex', ...
        'TickDir', 'in', ...
        'TickLength', [0.018, 0.018], ...
        'LineWidth', 0.8, ...
        'Box', 'on', ...
        'XMinorTick', 'off', ...
        'YMinorTick', 'off', ...
        'XGrid', 'off', ...
        'YGrid', 'off', ...
        'XLim', [0, panelXMaximum * 1.08], ...
        'YLim', [0, sharedYMaximum]);
    xlabel(ax, 'Delay $\tau_1$ (ms)', 'Interpreter', 'latex', 'FontSize', 9);
    if panelIndex == 1
        ylabel(ax, 'Delay $\tau_2$ (ms)', 'Interpreter', 'latex', 'FontSize', 9);
    else
        ax.YTickLabel = [];
    end
    text(ax, 0.02, 1.02, panelLabels(panelIndex), ...
        'Units', 'normalized', ...
        'Interpreter', 'latex', ...
        'FontName', plotFontName, ...
        'FontSize', 9, ...
        'FontWeight', 'bold', ...
        'HorizontalAlignment', 'left', ...
        'VerticalAlignment', 'bottom', ...
        'Clipping', 'off');
end

linkaxes(axesHandles, 'y');
legendHandle = legend(axesHandles(1), legendHandles, ...
    {'Original', 'Craig--Bampton', 'Guyan'}, ...
    'Interpreter', 'latex', ...
    'FontName', plotFontName, ...
    'FontSize', 9, ...
    'Orientation', 'horizontal', ...
    'Box', 'off');
drawnow;
legendHandle.Units = 'normalized';
legendHandle.Position = [0.275, 0.905, 0.450, 0.060];

metadata = struct();
metadata.status = 'PLOT_LEVEL_VECTOR_TRACE_ONLY';
metadata.calculationReproduction = false;
metadata.pointCount = 386;
metadata.samplingPeriodSeconds = 1 / 1024;
metadata.conversion = 'tau_ms=(tau_step-1)*1000/1024';
metadata.pointOrderPreserved = true;
metadata.drawStyle = 'ordinary ordered polyline';
metadata.requestedFont = 'CMU Serif';
metadata.actualSystemFont = plotFontName;
metadata.textInterpreter = 'latex';
metadata.axesXLim = [axesHandles(1).XLim; axesHandles(2).XLim];
metadata.axesYLim = [axesHandles(1).YLim; axesHandles(2).YLim];
metadata.axesPosition = [axesHandles(1).Position; axesHandles(2).Position];

auditTable = struct2table(auditRows);
writetable(auditTable, fullfile(outputDir, 'data_audit.csv'), 'Encoding', 'UTF-8');
save(fullfile(outputDir, 'plotted_data.mat'), 'plottedData', 'metadata');

pdfPath = fullfile(pdfDir, 'fig10_stability_domain.pdf');
pngPath = fullfile(pngDir, 'fig10_stability_domain.png');
exportgraphics(fig, pdfPath, ...
    'ContentType', 'vector', ...
    'BackgroundColor', 'white');
exportgraphics(fig, pngPath, ...
    'Resolution', 600, ...
    'BackgroundColor', 'white');

assertFileCreated(pdfPath);
assertFileCreated(pngPath);
fprintf('Fig. 10 已生成。\nPDF: %s\nPNG: %s\n', pdfPath, pngPath);

clear cleanupFigure;
closeFigureIfValid(fig);

function spec = buildCurveSpecification()
spec = struct( ...
    'figureId', {"4-4", "4-4", "4-4", "4-5", "4-5", "4-5"}, ...
    'method', {"Original", "Craig-Bampton", "Guyan", "Original", "Craig-Bampton", "Guyan"}, ...
    'fileName', { ...
        "图4-4_Original_论文矢量边界.csv", ...
        "图4-4_CB_论文矢量边界.csv", ...
        "图4-4_Guyan_论文矢量边界.csv", ...
        "图4-5_Original_论文矢量边界.csv", ...
        "图4-5_CB_论文矢量边界.csv", ...
        "图4-5_Guyan_论文矢量边界.csv"}, ...
    'expectedCount', {72, 69, 67, 69, 56, 53}, ...
    'firstStep', {[64, 2], [59, 2], [58, 2], [57, 2], [51, 2], [48, 2]}, ...
    'lastStep', {[2, 31], [2, 26], [2, 24], [2, 28], [2, 24], [2, 23]});
end

function tableData = readAndValidateCurve(inputPath, spec)
if ~isfile(inputPath)
    error('Fig10:MissingInput', '缺少输入文件：%s', inputPath);
end
tableData = readtable(inputPath, ...
    'VariableNamingRule', 'preserve', ...
    'TextType', 'string', ...
    'Encoding', 'UTF-8');
requiredColumns = {'point_order', 'tau1_step', 'tau2_step'};
if ~all(ismember(requiredColumns, tableData.Properties.VariableNames))
    error('Fig10:MissingColumn', '%s 缺少必要列。', spec.fileName);
end
if height(tableData) ~= spec.expectedCount
    error('Fig10:PointCount', '%s 应有 %d 点，实际为 %d 点。', ...
        spec.fileName, spec.expectedCount, height(tableData));
end
expectedOrder = (1:spec.expectedCount).';
if ~isequal(tableData.point_order, expectedOrder)
    error('Fig10:PointOrder', '%s 的 point_order 不连续或文件行顺序已改变。', spec.fileName);
end
if any(~isfinite(tableData.tau1_step)) || any(~isfinite(tableData.tau2_step))
    error('Fig10:NonfiniteStep', '%s 包含非有限采样步。', spec.fileName);
end
if any(tableData.tau1_step ~= round(tableData.tau1_step)) || ...
        any(tableData.tau2_step ~= round(tableData.tau2_step))
    error('Fig10:NonintegerStep', '%s 包含非整数采样步。', spec.fileName);
end
actualFirst = [tableData.tau1_step(1), tableData.tau2_step(1)];
actualLast = [tableData.tau1_step(end), tableData.tau2_step(end)];
if ~isequal(actualFirst, spec.firstStep) || ~isequal(actualLast, spec.lastStep)
    error('Fig10:Endpoint', '%s 的首末端点不符合封存值。', spec.fileName);
end
end

function milliseconds = stepToMilliseconds(stepValue)
milliseconds = (stepValue - 1) * 1000 / 1024;
end

function record = emptyCurveRecord()
record = struct( ...
    'figureId', "", ...
    'method', "", ...
    'sourceFile', "", ...
    'point_order', [], ...
    'tau1_step', [], ...
    'tau2_step', [], ...
    'tau1_ms', [], ...
    'tau2_ms', [], ...
    'plotted_x_ms', [], ...
    'plotted_y_ms', []);
end

function audit = emptyAuditRecord()
audit = struct( ...
    'figure_id', "", ...
    'method', "", ...
    'source_file', "", ...
    'point_count', 0, ...
    'order_first', 0, ...
    'order_last', 0, ...
    'tau1_step_first', 0, ...
    'tau2_step_first', 0, ...
    'tau1_step_last', 0, ...
    'tau2_step_last', 0, ...
    'tau1_ms_first', 0, ...
    'tau2_ms_first', 0, ...
    'tau1_ms_last', 0, ...
    'tau2_ms_last', 0);
end

function audit = makeAuditRecord(record)
audit = emptyAuditRecord();
audit.figure_id = record.figureId;
audit.method = record.method;
audit.source_file = record.sourceFile;
audit.point_count = numel(record.point_order);
audit.order_first = record.point_order(1);
audit.order_last = record.point_order(end);
audit.tau1_step_first = record.tau1_step(1);
audit.tau2_step_first = record.tau2_step(1);
audit.tau1_step_last = record.tau1_step(end);
audit.tau2_step_last = record.tau2_step(end);
audit.tau1_ms_first = record.tau1_ms(1);
audit.tau2_ms_first = record.tau2_ms(1);
audit.tau1_ms_last = record.tau1_ms(end);
audit.tau2_ms_last = record.tau2_ms(end);
end

function recordIndex = findCurve(plottedData, figureId, method)
matches = arrayfun(@(record) ...
    strcmp(record.figureId, figureId) && strcmp(record.method, method), plottedData);
recordIndex = find(matches, 1, 'first');
if isempty(recordIndex)
    error('Fig10:CurveLookup', '找不到 %s / %s 数据。', figureId, method);
end
end

function style = styleForMethod(method)
switch method
    case "Original"
        style = struct('color', [85, 85, 85] / 255, ...
            'lineStyle', '--', 'marker', 'o', 'legendLabel', 'Original');
    case "Craig-Bampton"
        style = struct('color', [238, 102, 119] / 255, ...
            'lineStyle', '-', 'marker', 's', 'legendLabel', 'Craig--Bampton');
    case "Guyan"
        style = struct('color', [68, 119, 170] / 255, ...
            'lineStyle', '-.', 'marker', '^', 'legendLabel', 'Guyan');
    otherwise
        error('Fig10:UnknownMethod', '未知方法：%s', method);
end
end

function ensureDirectory(directoryPath)
if ~isfolder(directoryPath)
    [created, message] = mkdir(directoryPath);
    if ~created
        error('Fig10:CreateDirectory', '无法创建文件夹：%s\n%s', directoryPath, message);
    end
end
end

function assertFileCreated(filePath)
fileInfo = dir(filePath);
if isempty(fileInfo) || fileInfo.bytes == 0
    error('Fig10:EmptyOutput', '输出文件不存在或为空：%s', filePath);
end
end

function fontName = chooseAvailableSerifFont()
availableFonts = string(listfonts);
if any(strcmpi(availableFonts, "CMU Serif"))
    fontName = 'CMU Serif';
elseif any(strcmpi(availableFonts, "Times New Roman"))
    fontName = 'Times New Roman';
else
    fontName = 'Serif';
end
end

function closeFigureIfValid(fig)
if isgraphics(fig)
    close(fig);
end
end
