% VERIFY_THIS_FIGURE
% 从自带CSV第三次重建Fig.6的6个坐标轴和18条实际曲线，并逐条验收。

scriptPath = mfilename('fullpath');
if isempty(scriptPath)
    error('Fig06Verify:ScriptLocation', 'MATLAB cannot determine this script location.');
end
figureDir = fileparts(scriptPath);
inputPath = fullfile(figureDir, '输入数据', '第一类划分_ElCentro地震响应.csv');
outputRoot = fullfile(figureDir, '输出');
pdfPath = fullfile(outputRoot, 'PDF', 'fig06_eq_div1.pdf');
pngPath = fullfile(outputRoot, 'PNG', 'fig06_eq_div1.png');
matPath = fullfile(outputRoot, 'plotted_data.mat');
auditPath = fullfile(outputRoot, 'data_audit.csv');
reportPath = fullfile(outputRoot, 'validation_report.txt');

if ~isfolder(outputRoot)
    mkdir(outputRoot);
end

try
    requiredFiles = {inputPath, pdfPath, pngPath, matPath, auditPath};
    for fileIndex = 1:numel(requiredFiles)
        if ~isfile(requiredFiles{fileIndex})
            error('Fig06Verify:MissingFile', 'Required file is missing: %s', requiredFiles{fileIndex});
        end
    end

    raw = readmatrix(inputPath);
    if ~isequal(size(raw), [40961, 10])
        error('Fig06Verify:InputShape', 'Input data is not 40961-by-10.');
    end
    if ~all(isfinite(raw(:)))
        error('Fig06Verify:FiniteData', 'Input data contains NaN or Inf.');
    end
    if abs(raw(1, 1)) > 1e-12 || abs(raw(end, 1) - 40) > 1e-12
        error('Fig06Verify:TimeRange', 'Input time range is not 0 to 40 s.');
    end
    maximumStepError = max(abs(diff(raw(:, 1)) - 1 / 1024));
    if maximumStepError > 1e-12
        error('Fig06Verify:TimeStep', 'Time-step error exceeds 1e-12 s.');
    end

    saved = load(matPath, 'plotted_data');
    if ~isfield(saved, 'plotted_data')
        error('Fig06Verify:SavedData', 'plotted_data is missing from the MAT file.');
    end
    plotted = saved.plotted_data;
    requiredFields = {'figure_id', 'source_file', 'time_s', 'response_mm', ...
        'floor_numbers', 'method_order_in_data', 'local_windows_s', ...
        'full_history_stride', 'plot_font', 'column_width_ratio', 'axes', 'curves'};
    for fieldIndex = 1:numel(requiredFields)
        if ~isfield(plotted, requiredFields{fieldIndex})
            error('Fig06Verify:SavedField', 'Missing plotted_data field: %s', requiredFields{fieldIndex});
        end
    end

    if ~strcmp(plotted.figure_id, 'Fig06')
        error('Fig06Verify:FigureIdentity', 'The saved figure identity is not Fig06.');
    end
    if ~isequal(plotted.floor_numbers, [1, 3])
        error('Fig06Verify:Floors', 'The saved floors are not first and third floors.');
    end
    if max(abs(plotted.local_windows_s(:) - [10.0; 21.5; 11.0; 22.5])) > 1e-12
        error('Fig06Verify:Windows', 'The saved local windows are incorrect.');
    end
    if max(abs(plotted.column_width_ratio - [2.30, 1.00, 1.00])) > 1e-12
        error('Fig06Verify:ColumnWidths', 'The column-width ratio is not 2.30:1:1.');
    end

    sourceResponse = zeros(40961, 3, 3);
    for floorIndex = 1:3
        firstColumn = 2 + (floorIndex - 1) * 3;
        sourceResponse(:, floorIndex, :) = reshape( ...
            raw(:, firstColumn:(firstColumn + 2)), 40961, 1, 3);
    end
    timeCopyError = max(abs(plotted.time_s(:) - raw(:, 1)));
    responseCopyError = max(abs(plotted.response_mm(:) - sourceResponse(:)));
    if max(timeCopyError, responseCopyError) > 1e-12
        error('Fig06Verify:SavedCopy', 'Saved full data differs from the bundled CSV.');
    end

    if numel(plotted.axes) ~= 6
        error('Fig06Verify:AxisCount', 'Expected 6 axes, received %d.', numel(plotted.axes));
    end
    if numel(plotted.curves) ~= 18
        error('Fig06Verify:CurveCount', 'Expected 18 curves, received %d.', numel(plotted.curves));
    end

    expectedFloors = [1, 1, 1, 3, 3, 3];
    expectedViews = {'full', 'window_10_to_11_s', 'window_21_5_to_22_5_s', ...
        'full', 'window_10_to_11_s', 'window_21_5_to_22_5_s'};
    expectedWindows = [0, 40; 10, 11; 21.5, 22.5; 0, 40; 10, 11; 21.5, 22.5];
    expectedMethods = {'Original', 'Craig-Bampton', 'Guyan'};
    expectedStyles = {'--', '-', '-.'};
    % MATLAB把方形标记的简写“s”规范化保存为“square”。
    expectedLocalMarkers = {'o', 'square', '^'};
    expectedColors = [85, 85, 85; 238, 102, 119; 68, 119, 170] / 255;
    fullStride = max(1, floor(size(raw, 1) / 12000));
    maximumCurveError = 0;

    for axisIndex = 1:6
        axisRecord = plotted.axes(axisIndex);
        if axisRecord.axis_index ~= axisIndex || axisRecord.floor_number ~= expectedFloors(axisIndex)
            error('Fig06Verify:AxisIdentity', 'Axis %d has the wrong identity.', axisIndex);
        end
        if ~strcmp(axisRecord.view_name, expectedViews{axisIndex})
            error('Fig06Verify:AxisView', 'Axis %d has the wrong view.', axisIndex);
        end
        if max(abs(axisRecord.window_s - expectedWindows(axisIndex, :))) > 1e-12
            error('Fig06Verify:AxisWindow', 'Axis %d has the wrong time window.', axisIndex);
        end
        columnInRow = mod(axisIndex - 1, 3) + 1;
        expectedWidth = 0.180;
        if columnInRow == 1
            expectedWidth = 0.414;
        end
        if abs(axisRecord.position(3) - expectedWidth) > 1e-12
            error('Fig06Verify:AxisWidth', 'Axis %d has the wrong physical width.', axisIndex);
        end

        floorNumber = expectedFloors(axisIndex);
        firstColumn = 2 + (floorNumber - 1) * 3;
        sourceColumns = firstColumn - 1 + [1, 3, 2];
        if columnInRow == 1
            selected = 1:fullStride:size(raw, 1);
            if selected(end) ~= size(raw, 1)
                selected(end + 1) = size(raw, 1);
            end
        else
            window = expectedWindows(axisIndex, :);
            selected = find(raw(:, 1) >= window(1) & raw(:, 1) <= window(2));
        end

        for methodIndex = 1:3
            curveIndex = (axisIndex - 1) * 3 + methodIndex;
            curve = plotted.curves(curveIndex);
            if curve.axis_index ~= axisIndex || curve.floor_number ~= floorNumber
                error('Fig06Verify:CurveAxis', 'Curve %d is attached to the wrong axis.', curveIndex);
            end
            if ~strcmp(curve.view_name, expectedViews{axisIndex}) || ...
                    ~strcmp(curve.method_name, expectedMethods{methodIndex})
                error('Fig06Verify:MethodIdentity', 'Curve %d has the wrong method identity.', curveIndex);
            end
            if curve.input_column ~= sourceColumns(methodIndex)
                error('Fig06Verify:ColumnContract', 'Curve %d uses the wrong input column.', curveIndex);
            end
            if ~strcmp(curve.line_style, expectedStyles{methodIndex})
                error('Fig06Verify:LineStyle', 'Curve %d uses the wrong line style.', curveIndex);
            end
            if columnInRow == 1
                expectedMarker = 'none';
            else
                expectedMarker = expectedLocalMarkers{methodIndex};
            end
            if ~strcmp(curve.marker, expectedMarker)
                error('Fig06Verify:Marker', 'Curve %d uses the wrong marker.', curveIndex);
            end
            if max(abs(curve.color_rgb - expectedColors(methodIndex, :))) > 1e-12
                error('Fig06Verify:Color', 'Curve %d uses the wrong color.', curveIndex);
            end

            expectedX = raw(selected, 1);
            expectedY = raw(selected, sourceColumns(methodIndex));
            if numel(curve.x_data) ~= numel(expectedX) || numel(curve.y_data) ~= numel(expectedY)
                error('Fig06Verify:CurveLength', 'Curve %d has the wrong point count.', curveIndex);
            end
            xError = max(abs(curve.x_data(:) - expectedX));
            yError = max(abs(curve.y_data(:) - expectedY));
            maximumCurveError = max([maximumCurveError, xError, yError]);
            if max(xError, yError) > 1e-12
                error('Fig06Verify:CurveData', 'Curve %d differs from the third reconstruction.', curveIndex);
            end
        end
    end

    pdfInfo = dir(pdfPath);
    pngInfo = dir(pngPath);
    if pdfInfo.bytes < 1000 || pngInfo.bytes < 10000
        error('Fig06Verify:OutputSize', 'One or more figure outputs are unexpectedly small.');
    end

    write_pass_report(reportPath, plotted.plot_font, maximumStepError, ...
        timeCopyError, responseCopyError, maximumCurveError, pdfInfo.bytes, pngInfo.bytes);
    fprintf('Fig.6 validation PASS. Maximum curve error: %.3e\n', maximumCurveError);
    fprintf('Validation report: %s\n', reportPath);
catch verificationError
    write_fail_report(reportPath, verificationError);
    rethrow(verificationError);
end


function write_pass_report(path, plotFont, stepError, timeCopyError, responseCopyError, curveError, pdfBytes, pngBytes)
    fileId = fopen(path, 'w');
    if fileId < 0
        error('Fig06Verify:ReportWrite', 'Cannot create validation_report.txt.');
    end
    cleanup = onCleanup(@() fclose(fileId));
    fprintf(fileId, 'STATUS=PASS\n');
    fprintf(fileId, 'FIGURE=Fig06\n');
    fprintf(fileId, 'AXIS_COUNT=6\n');
    fprintf(fileId, 'CURVE_COUNT=18\n');
    fprintf(fileId, 'COLUMN_WIDTH_RATIO=2.30:1:1\n');
    fprintf(fileId, 'FULL_HISTORY_MARKERS=none\n');
    fprintf(fileId, 'LOCAL_WINDOW_MARKERS=o,square,^\n');
    fprintf(fileId, 'ACTUAL_FONT=%s\n', plotFont);
    fprintf(fileId, 'MAX_TIME_STEP_ERROR=%.17g\n', stepError);
    fprintf(fileId, 'MAX_SAVED_TIME_ERROR=%.17g\n', timeCopyError);
    fprintf(fileId, 'MAX_SAVED_RESPONSE_ERROR=%.17g\n', responseCopyError);
    fprintf(fileId, 'MAX_18_CURVE_ERROR=%.17g\n', curveError);
    fprintf(fileId, 'ERROR_TOLERANCE=1e-12\n');
    fprintf(fileId, 'PDF_BYTES=%d\n', pdfBytes);
    fprintf(fileId, 'PNG_BYTES=%d\n', pngBytes);
    clear cleanup;
end


function write_fail_report(path, verificationError)
    fileId = fopen(path, 'w');
    if fileId < 0
        return;
    end
    cleanup = onCleanup(@() fclose(fileId));
    message = strrep(verificationError.message, newline, ' ');
    fprintf(fileId, 'STATUS=FAIL\n');
    fprintf(fileId, 'ERROR_ID=%s\n', verificationError.identifier);
    fprintf(fileId, 'ERROR_MESSAGE=%s\n', message);
    clear cleanup;
end
