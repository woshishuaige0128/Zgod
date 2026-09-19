%% VERIFY_THIS_FIGURE
% 独立重读六份输入CSV，并与 RUN_THIS_FIGURE 保存的逐点数据进行比较。

scriptDir = fileparts(mfilename('fullpath'));
dataDir = fullfile(scriptDir, '输入数据');
outputDir = fullfile(scriptDir, '输出');
reportPath = fullfile(outputDir, 'validation_report.txt');

if ~isfolder(outputDir)
    [created, message] = mkdir(outputDir);
    if ~created
        error('Fig10:CreateOutputDirectory', '无法创建输出文件夹：%s\n%s', outputDir, message);
    end
end

try
    verification = performVerification(dataDir, outputDir);
    writeReport(reportPath, 'PASS', verification, '');
    fprintf('Fig. 10 独立验收通过。\n报告: %s\n', reportPath);
catch verificationError
    failedResult = struct('totalPoints', NaN, 'maximumPointError', NaN, ...
        'checkedCurves', 0, 'pdfBytes', NaN, 'pngBytes', NaN, ...
        'actualFont', "UNKNOWN");
    writeReport(reportPath, 'FAIL', failedResult, verificationError.message);
    rethrow(verificationError);
end

function result = performVerification(dataDir, outputDir)
spec = buildCurveSpecification();
matPath = fullfile(outputDir, 'plotted_data.mat');
auditPath = fullfile(outputDir, 'data_audit.csv');
pdfPath = fullfile(outputDir, 'PDF', 'fig10_stability_domain.pdf');
pngPath = fullfile(outputDir, 'PNG', 'fig10_stability_domain.png');

requiredOutputFiles = {matPath, auditPath, pdfPath, pngPath};
for fileIndex = 1:numel(requiredOutputFiles)
    assertNonemptyFile(requiredOutputFiles{fileIndex});
end

saved = load(matPath, 'plottedData', 'metadata');
if ~isfield(saved, 'plottedData') || ~isfield(saved, 'metadata')
    error('Fig10:MissingSavedVariable', 'plotted_data.mat 缺少 plottedData 或 metadata。');
end
if numel(saved.plottedData) ~= 6
    error('Fig10:SavedCurveCount', 'plotted_data.mat 应保存六条曲线。');
end
if saved.metadata.pointCount ~= 386 || saved.metadata.calculationReproduction
    error('Fig10:Metadata', '保存的证据等级元数据不符合要求。');
end
if ~isfield(saved.metadata, 'actualSystemFont') || ...
        ~isfield(saved.metadata, 'axesXLim') || ...
        ~isfield(saved.metadata, 'axesYLim') || ...
        ~isfield(saved.metadata, 'axesPosition')
    error('Fig10:MetadataFields', '保存的字体或坐标轴元数据不完整。');
end
if any(abs(saved.metadata.axesXLim(:, 1)) > 1e-12) || ...
        any(abs(saved.metadata.axesYLim(:, 1)) > 1e-12)
    error('Fig10:AxisOrigin', '两个面板的坐标轴没有从0开始。');
end
if abs(saved.metadata.axesPosition(1, 3) - saved.metadata.axesPosition(2, 3)) > 1e-12
    error('Fig10:PanelWidth', '两个面板的宽度不一致。');
end

maximumPointError = 0;
totalPoints = 0;
for curveIndex = 1:numel(spec)
    expected = spec(curveIndex);
    csvPath = fullfile(dataDir, expected.fileName);
    csvData = readtable(csvPath, ...
        'VariableNamingRule', 'preserve', ...
        'TextType', 'string', ...
        'Encoding', 'UTF-8');

    if height(csvData) ~= expected.expectedCount
        error('Fig10:PointCount', '%s 点数错误。', expected.fileName);
    end
    expectedOrder = (1:expected.expectedCount).';
    if ~isequal(csvData.point_order, expectedOrder)
        error('Fig10:PointOrder', '%s 的 point_order 不连续或顺序已改变。', expected.fileName);
    end
    if ~isequal([csvData.tau1_step(1), csvData.tau2_step(1)], expected.firstStep) || ...
            ~isequal([csvData.tau1_step(end), csvData.tau2_step(end)], expected.lastStep)
        error('Fig10:Endpoint', '%s 的端点与封存值不一致。', expected.fileName);
    end

    savedIndex = findSavedCurve(saved.plottedData, expected.figureId, expected.method);
    record = saved.plottedData(savedIndex);
    expectedTau1 = (csvData.tau1_step - 1) * 1000 / 1024;
    expectedTau2 = (csvData.tau2_step - 1) * 1000 / 1024;

    requireExact(record.point_order, csvData.point_order, expected.fileName, 'point_order');
    requireExact(record.tau1_step, csvData.tau1_step, expected.fileName, 'tau1_step');
    requireExact(record.tau2_step, csvData.tau2_step, expected.fileName, 'tau2_step');
    if numel(record.plotted_x_ms) ~= expected.expectedCount || ...
            numel(record.plotted_y_ms) ~= expected.expectedCount
        error('Fig10:PlottedPointCount', '%s 实际图线对象的点数错误。', expected.fileName);
    end
    pointError = max([max(abs(record.plotted_x_ms(:) - expectedTau1(:))), ...
        max(abs(record.plotted_y_ms(:) - expectedTau2(:)))]);
    if pointError > 1e-12
        error('Fig10:PointMismatch', '%s 的毫秒坐标误差 %.17g 超过 1e-12。', ...
            expected.fileName, pointError);
    end
    maximumPointError = max(maximumPointError, pointError);
    totalPoints = totalPoints + height(csvData);
end

if totalPoints ~= 386
    error('Fig10:TotalPointCount', '六条边界的点数总和不是 386。');
end

auditTable = readtable(auditPath, ...
    'VariableNamingRule', 'preserve', ...
    'TextType', 'string', ...
    'Encoding', 'UTF-8');
if height(auditTable) ~= 6 || sum(auditTable.point_count) ~= 386
    error('Fig10:AuditTable', 'data_audit.csv 的曲线数或总点数错误。');
end

pdfInfo = dir(pdfPath);
pngInfo = dir(pngPath);
result = struct( ...
    'totalPoints', totalPoints, ...
    'maximumPointError', maximumPointError, ...
    'checkedCurves', numel(spec), ...
    'pdfBytes', pdfInfo.bytes, ...
    'pngBytes', pngInfo.bytes, ...
    'actualFont', string(saved.metadata.actualSystemFont));
end

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

function savedIndex = findSavedCurve(plottedData, figureId, method)
matches = arrayfun(@(record) ...
    strcmp(record.figureId, figureId) && strcmp(record.method, method), plottedData);
savedIndex = find(matches, 1, 'first');
if isempty(savedIndex)
    error('Fig10:SavedCurveMissing', 'plotted_data.mat 缺少 %s / %s。', figureId, method);
end
end

function requireExact(actual, expected, fileName, fieldName)
if ~isequal(actual, expected)
    error('Fig10:ExactMismatch', '%s 的 %s 未逐点保持。', fileName, fieldName);
end
end

function assertNonemptyFile(filePath)
fileInfo = dir(filePath);
if isempty(fileInfo) || fileInfo.bytes == 0
    error('Fig10:MissingOutput', '输出文件不存在或为空：%s', filePath);
end
end

function writeReport(reportPath, status, result, errorMessage)
fileId = fopen(reportPath, 'w', 'n', 'UTF-8');
if fileId < 0
    error('Fig10:ReportOpen', '无法写入验收报告：%s', reportPath);
end
cleanupFile = onCleanup(@() fclose(fileId));
fprintf(fileId, 'STATUS=%s\n', status);
fprintf(fileId, 'EVIDENCE_LEVEL=PLOT_LEVEL_VECTOR_TRACE_ONLY\n');
fprintf(fileId, 'CALCULATION_REPRODUCTION=NOT_PASSED\n');
fprintf(fileId, 'CHECKED_CURVES=%g\n', result.checkedCurves);
fprintf(fileId, 'TOTAL_POINTS=%g\n', result.totalPoints);
fprintf(fileId, 'MAX_POINT_ERROR=%.17g\n', result.maximumPointError);
fprintf(fileId, 'TOLERANCE=1e-12\n');
fprintf(fileId, 'PDF_BYTES=%g\n', result.pdfBytes);
fprintf(fileId, 'PNG_BYTES=%g\n', result.pngBytes);
fprintf(fileId, 'ACTUAL_SYSTEM_FONT=%s\n', char(result.actualFont));
fprintf(fileId, 'TEXT_INTERPRETER=latex\n');
if ~isempty(errorMessage)
    fprintf(fileId, 'ERROR=%s\n', replace(errorMessage, newline, ' | '));
end
clear cleanupFile;
end
