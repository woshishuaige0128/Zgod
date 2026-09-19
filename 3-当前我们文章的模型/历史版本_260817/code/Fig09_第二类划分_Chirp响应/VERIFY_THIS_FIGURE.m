%% Fig. 9 独立验收
scriptFile = mfilename('fullpath');
baseDir = fileparts(scriptFile);
inputFile = fullfile(baseDir, '输入数据', '第二类划分_Chirp响应.csv');
outputDir = fullfile(baseDir, '输出');
savedFile = fullfile(outputDir, 'plotted_data.mat');
auditFile = fullfile(outputDir, 'data_audit.csv');
pdfFile = fullfile(outputDir, 'PDF', 'fig09_chirp_div2.pdf');
pngFile = fullfile(outputDir, 'PNG', 'fig09_chirp_div2.png');
reportFile = fullfile(outputDir, 'validation_report.txt');

try
    inputData = readmatrix(inputFile, 'NumHeaderLines', 1);
    saved = load(savedFile, 'plotted_data');
    if ~isfield(saved, 'plotted_data') || ~isfield(saved.plotted_data, 'input_data')
        error('Fig09:MissingSavedData', 'plotted_data.mat 缺少绘图输入快照。');
    end
    if ~isequal(size(inputData), [40961, 10])
        error('Fig09:BadInputSize', '输入数据尺寸错误。');
    end
    if ~isequal(size(saved.plotted_data.input_data), size(inputData))
        error('Fig09:BadSavedSize', '保存的数据尺寸与输入不一致。');
    end
    snapshotError = max(abs(saved.plotted_data.input_data(:) - inputData(:)));
    if ~isfinite(snapshotError) || snapshotError > 1e-12
        error('Fig09:DataMismatch', '输入快照的最大误差 %.17g 超过 1e-12。', snapshotError);
    end
    if ~isfield(saved.plotted_data, 'axes') || numel(saved.plotted_data.axes) ~= 6
        error('Fig09:BadAxisCount', '必须保存6个坐标轴的身份与样本。');
    end
    if ~isfield(saved.plotted_data, 'curves') || numel(saved.plotted_data.curves) ~= 18
        error('Fig09:BadCurveCount', '必须保存18条实际绘制曲线。');
    end
    if ~isfield(saved.plotted_data, 'actual_font_name') || isempty(saved.plotted_data.actual_font_name)
        error('Fig09:MissingFont', '缺少实际字体记录。');
    end

    floorColumns = [2, 3, 4; 8, 9, 10];
    localWindows = [13, 14; 38, 38.3];
    methodNames = {'Original', 'Craig-Bampton', 'Guyan'};
    lineStyles = {'--', '-', '-.'};
    colors = [85, 85, 85; 238, 102, 119; 68, 119, 170] / 255;
    maxCurveError = 0;
    maxXError = 0;
    axisIndex = 0;
    for row = 1:2
        sourceColumns = floorColumns(row, [1, 3, 2]);
        for viewIndex = 1:3
            axisIndex = axisIndex + 1;
            if viewIndex == 1
                viewName = 'full';
                expectedLimits = [0, 40];
                expectedIndices = fullSampleIndices(size(inputData, 1));
            else
                viewName = sprintf('local_%d', viewIndex - 1);
                expectedLimits = localWindows(viewIndex - 1, :);
                expectedIndices = find(inputData(:, 1) >= expectedLimits(1) & ...
                    inputData(:, 1) <= expectedLimits(2));
            end
            axisRecord = saved.plotted_data.axes(axisIndex);
            if axisRecord.axis_index ~= axisIndex || axisRecord.floor_number ~= row * 2 - 1 || ...
                    ~strcmp(axisRecord.view_name, viewName) || ...
                    ~isequal(axisRecord.sample_indices(:), expectedIndices(:)) || ...
                    max(abs(axisRecord.x_limits(:) - expectedLimits(:))) > 1e-12
                error('Fig09:AxisIdentity', '第%d个坐标轴的楼层、窗口或样本身份错误。', axisIndex);
            end
            for method = 1:3
                curveNumber = (axisIndex - 1) * 3 + method;
                curve = saved.plotted_data.curves(curveNumber);
                if curve.axis_index ~= axisIndex || curve.floor_number ~= row * 2 - 1 || ...
                        ~strcmp(curve.view_name, viewName) || ...
                        ~strcmp(curve.method_name, methodNames{method}) || ...
                        curve.source_column ~= sourceColumns(method) || ...
                        ~isequal(curve.sample_indices(:), expectedIndices(:))
                    error('Fig09:CurveIdentity', '第%d条曲线的方法、窗口或源列身份错误。', curveNumber);
                end
                if ~strcmp(curve.line_style, lineStyles{method}) || ...
                        max(abs(curve.color_rgb(:) - colors(method, :)')) > 1e-12
                    error('Fig09:CurveStyle', '第%d条曲线的线型或颜色错误。', curveNumber);
                end
                if viewIndex == 1
                    if ~strcmp(curve.marker_name, 'none')
                        error('Fig09:FullMarker', '全时程曲线不应显示标记。');
                    end
                else
                    expectedMarkers = {'o', 'square', '^'};
                    acceptedMarker = strcmp(curve.marker_name, expectedMarkers{method});
                    if method == 2
                        acceptedMarker = acceptedMarker || strcmp(curve.marker_name, 's');
                    end
                    if ~acceptedMarker
                        error('Fig09:LocalMarker', '局部窗第%d种方法的标记错误。', method);
                    end
                end
                expectedX = inputData(expectedIndices, 1);
                expectedY = inputData(expectedIndices, sourceColumns(method));
                if ~isequal(size(curve.x_data(:)), size(expectedX(:))) || ...
                        ~isequal(size(curve.y_data(:)), size(expectedY(:)))
                    error('Fig09:CurveSize', '第%d条实际曲线的数据长度错误。', curveNumber);
                end
                maxXError = max(maxXError, max(abs(curve.x_data(:) - expectedX(:))));
                maxCurveError = max(maxCurveError, max(abs(curve.y_data(:) - expectedY(:))));
            end
        end
    end
    maxError = max([snapshotError, maxXError, maxCurveError]);
    if ~isfinite(maxError) || maxError > 1e-12
        error('Fig09:PlottedDataMismatch', '实际传给绘图对象的数据最大误差 %.17g 超过 1e-12。', maxError);
    end
    if ~isfile(auditFile) || ~isfile(pdfFile) || ~isfile(pngFile)
        error('Fig09:MissingOutput', '缺少审计表、PDF 或 PNG。');
    end
    pdfInfo = dir(pdfFile);
    pngInfo = dir(pngFile);
    if pdfInfo.bytes < 1000 || pngInfo.bytes < 1000
        error('Fig09:SmallOutput', 'PDF 或 PNG 文件异常小。');
    end

    reportId = fopen(reportFile, 'w');
    if reportId < 0, error('Fig09:ReportWrite', '无法写入验收报告。'); end
    fprintf(reportId, 'STATUS=PASS\n');
    fprintf(reportId, 'figure=Fig09_第二类划分_Chirp响应\n');
    fprintf(reportId, 'input_size=%d×%d\n', size(inputData, 1), size(inputData, 2));
    fprintf(reportId, 'time_range_s=%.17g,%.17g\n', inputData(1, 1), inputData(end, 1));
    fprintf(reportId, 'time_step_s=%.17g\n', median(diff(inputData(:, 1))));
    fprintf(reportId, 'axes_count=%d\n', numel(saved.plotted_data.axes));
    fprintf(reportId, 'curves_count=%d\n', numel(saved.plotted_data.curves));
    fprintf(reportId, 'actual_font=%s\n', saved.plotted_data.actual_font_name);
    fprintf(reportId, 'max_input_snapshot_error=%.17g\n', snapshotError);
    fprintf(reportId, 'max_plotted_x_error=%.17g\n', maxXError);
    fprintf(reportId, 'max_plotted_y_error=%.17g\n', maxCurveError);
    fprintf(reportId, 'max_saved_data_error=%.17g\n', maxError);
    fprintf(reportId, 'acceptance_limit=1e-12\n');
    fprintf(reportId, 'pdf_bytes=%d\n', pdfInfo.bytes);
    fprintf(reportId, 'png_bytes=%d\n', pngInfo.bytes);
    fclose(reportId);
    fprintf('Fig. 9 验收通过：最大数据误差 %.3g。\n', maxError);
catch validationError
    reportId = fopen(reportFile, 'w');
    if reportId >= 0
        fprintf(reportId, 'STATUS=FAIL\n');
        fprintf(reportId, 'identifier=%s\n', validationError.identifier);
        fprintf(reportId, 'message=%s\n', validationError.message);
        fclose(reportId);
    end
    rethrow(validationError);
end

function indices = fullSampleIndices(sampleCount)
    stride = max(1, floor(sampleCount / 12000));
    indices = unique([(1:stride:sampleCount)'; sampleCount]);
end
