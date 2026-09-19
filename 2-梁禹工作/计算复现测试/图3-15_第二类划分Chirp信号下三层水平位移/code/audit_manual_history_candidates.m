%% 板块18：历史时程人工候选的只读审核
% 目的：对 history_timeseries_scan.csv 中 MANUAL_REVIEW_REQUIRED 的 6 个
% MAT 文件逐一执行 whos -file，并仅对可能承载时程的变量做选择性只读
% load。脚本不调用 Simulink、不修改原件、不建立逐图成功目录。

clearvars;
clc;

codeDir = fileparts(mfilename('fullpath'));
boardDir = fileparts(codeDir);
outputsDir = fullfile(boardDir, 'outputs');
scanFile = fullfile(outputsDir, 'history_timeseries_scan.csv');
inventoryFile = fullfile(outputsDir, 'manual_history_variable_inventory.csv');
adjudicationFile = fullfile(outputsDir, 'manual_history_file_adjudication.csv');
summaryFile = fullfile(outputsDir, 'manual_history_audit_summary.json');

assert(isfile(scanFile), '缺少历史候选扫描表：%s', scanFile);
if ~isfolder(outputsDir)
    mkdir(outputsDir);
end

successDirsBefore = list_success_directories(boardDir);
opts = detectImportOptions(scanFile, 'TextType', 'string', ...
    'VariableNamingRule', 'preserve');
scanTable = readtable(scanFile, opts);
requiredColumns = ["absolute_path", "status", "size_bytes", "sha256"];
assert(all(ismember(requiredColumns, string(scanTable.Properties.VariableNames))), ...
    '历史候选扫描表缺少必需列。');
candidates = scanTable(scanTable.status == "MANUAL_REVIEW_REQUIRED", :);
assert(height(candidates) == 6, ...
    'MANUAL_REVIEW_REQUIRED 应为 6 行，实际为 %d 行。', height(candidates));

inventory = make_inventory_table();
adjudication = make_adjudication_table();

fprintf('板块18历史时程人工候选只读审核开始。候选数：%d\n', height(candidates));
fprintf('MATLAB版本：%s\n', version);

for fileIndex = 1:height(candidates)
    sourcePath = char(candidates.absolute_path(fileIndex));
    assert(isfile(sourcePath), '候选MAT不存在：%s', sourcePath);

    fileInfo = dir(sourcePath);
    scanSha256 = upper(string(candidates.sha256(fileIndex)));
    sha256Before = string(sha256_file(sourcePath));
    scanHashMatch = strcmpi(scanSha256, sha256Before);
    matFormat = string(detect_mat_format(sourcePath));

    whosStatus = "FAIL";
    whosError = "";
    inspectionMethod = "whos-file";
    whosVariables = struct([]);
    hdf5DatasetCount = 0;
    inspectionComplete = false;

    try
        whosVariables = whos('-file', sourcePath);
        whosStatus = "PASS";
        inspectionComplete = true;
    catch ME
        whosError = sanitize_message(ME.message);
    end

    exactTensorCount = 0;
    timeseriesClassCount = 0;
    simoutNameCount = 0;
    simoutShapeItems = strings(0, 1);
    loadAttemptCount = 0;
    loadSuccessCount = 0;
    loadFailureCount = 0;
    loadedExactTensorCount = 0;
    loadedTimeseriesCount = 0;

    if whosStatus == "PASS"
        for variableIndex = 1:numel(whosVariables)
            item = whosVariables(variableIndex);
            variableName = string(item.name);
            variableClass = string(item.class);
            variableSize = double(item.size);
            isExactTensor = is_exact_response_tensor_size(variableSize);
            isTimeseriesClass = is_timeseries_class_name(variableClass);
            hasTimeName = has_timeseries_name_signature(variableName);
            hasSimoutName = has_simout_response_name(variableName);
            shouldLoad = isExactTensor || isTimeseriesClass || hasTimeName || ...
                is_container_class(variableClass);

            loadAttempted = false;
            loadStatus = "NOT_NEEDED";
            loadError = "";
            loaded = empty_loaded_details();

            if shouldLoad
                loadAttempted = true;
                loadAttemptCount = loadAttemptCount + 1;
                try
                    loadedStruct = load(sourcePath, char(variableName));
                    loadedValue = loadedStruct.(char(variableName));
                    loaded = inspect_loaded_value(loadedValue, variableName);
                    loadStatus = "PASS";
                    loadSuccessCount = loadSuccessCount + 1;
                catch ME
                    loadStatus = "FAIL_RECORDED";
                    loadError = sanitize_message(ME.message);
                    loadFailureCount = loadFailureCount + 1;
                end
            end

            exactTensorCount = exactTensorCount + double(isExactTensor);
            timeseriesClassCount = timeseriesClassCount + double(isTimeseriesClass);
            simoutNameCount = simoutNameCount + double(hasSimoutName);
            if hasSimoutName
                simoutShapeItems(end + 1, 1) = variableName + ":" + ... %#ok<AGROW>
                    size_string(variableSize);
            end
            loadedExactTensorCount = loadedExactTensorCount + ...
                double(loaded.hasExactTensor);
            loadedTimeseriesCount = loadedTimeseriesCount + ...
                double(loaded.hasTimeseriesOrSimout);

            inventory(end + 1, :) = { ... %#ok<AGROW>
                fileIndex, string(sourcePath), sha256Before, matFormat, ...
                inspectionMethod, variableIndex, variableName, variableClass, ...
                size_string(variableSize), prod_or_zero(variableSize), ...
                double(item.bytes), logical_field(item, 'complex'), ...
                logical_field(item, 'sparse'), isExactTensor, ...
                isTimeseriesClass, hasTimeName, loadAttempted, loadStatus, ...
                loaded.valueClass, loaded.valueSize, loaded.sampleCount, ...
                loaded.hasExactTensor, loaded.hasTimeseriesOrSimout, ...
                loaded.nestedSummary, loadError};
        end

        if isempty(whosVariables)
            inventory(end + 1, :) = { ... %#ok<AGROW>
                fileIndex, string(sourcePath), sha256Before, matFormat, ...
                inspectionMethod, 0, "<NO_VARIABLES>", "", "[]", 0, 0, ...
                false, false, false, false, false, false, "NOT_NEEDED", ...
                "", "", 0, false, false, "", ""};
        end
    elseif contains(matFormat, "7.3") || contains(matFormat, "HDF5")
        % v7.3/HDF5 的备用路线只读取目录元数据，不写回文件。
        inspectionMethod = "whos-file_FAILED_then_h5info";
        try
            h5Root = h5info(sourcePath);
            datasets = collect_h5_datasets(h5Root);
            hdf5DatasetCount = numel(datasets);
            inspectionComplete = true;
            for datasetIndex = 1:numel(datasets)
                datasetSize = double(datasets(datasetIndex).size);
                isExactTensor = is_exact_response_tensor_size(datasetSize);
                datasetName = string(datasets(datasetIndex).name);
                hasTimeName = has_timeseries_name_signature(datasetName);
                hasSimoutName = has_simout_response_name(datasetName);
                exactTensorCount = exactTensorCount + double(isExactTensor);
                simoutNameCount = simoutNameCount + double(hasSimoutName);
                inventory(end + 1, :) = { ... %#ok<AGROW>
                    fileIndex, string(sourcePath), sha256Before, matFormat, ...
                    inspectionMethod, datasetIndex, datasetName, ...
                    string(datasets(datasetIndex).dataClass), ...
                    size_string(datasetSize), prod_or_zero(datasetSize), NaN, ...
                    false, false, isExactTensor, false, hasTimeName, false, ...
                    "NOT_LOADED_HDF5_METADATA_ONLY", "", "", 0, ...
                    false, hasSimoutName, "h5info数据集元数据", whosError};
            end
            if isempty(datasets)
                inventory(end + 1, :) = { ... %#ok<AGROW>
                    fileIndex, string(sourcePath), sha256Before, matFormat, ...
                    inspectionMethod, 0, "<NO_HDF5_DATASETS>", "", "[]", ...
                    0, 0, false, false, false, false, false, false, ...
                    "NOT_LOADED_HDF5_METADATA_ONLY", "", "", 0, false, ...
                    false, "", whosError};
            end
        catch ME
            whosError = whosError + " | h5info: " + sanitize_message(ME.message);
            inventory(end + 1, :) = { ... %#ok<AGROW>
                fileIndex, string(sourcePath), sha256Before, matFormat, ...
                inspectionMethod, 0, "<INSPECTION_FAILED>", "", "[]", ...
                0, 0, false, false, false, false, false, false, ...
                "FAILED", "", "", 0, false, false, "", whosError};
        end
    else
        inventory(end + 1, :) = { ... %#ok<AGROW>
            fileIndex, string(sourcePath), sha256Before, matFormat, ...
            inspectionMethod, 0, "<WHOS_FAILED>", "", "[]", 0, 0, ...
            false, false, false, false, false, false, "FAILED", "", ...
            "", 0, false, false, "", whosError};
    end

    sha256After = string(sha256_file(sourcePath));
    hashUnchanged = strcmpi(sha256Before, sha256After);
    supportsBoard18 = (exactTensorCount + loadedExactTensorCount + ...
        timeseriesClassCount + loadedTimeseriesCount) > 0;

    if ~inspectionComplete
        decision = "INSPECTION_FAILED_WITH_EVIDENCE";
        reason = "whos -file失败，且适用的只读备用目录路线也未成功；不得猜测其内容。";
    elseif (exactTensorCount + loadedExactTensorCount) > 0
        decision = "EXACT_40961x3x3_RESPONSE_FOUND";
        reason = "发现40961×3×3响应张量；仍需另行核对激励、楼层与方法身份后才能作为逐图基准。";
    elseif (timeseriesClassCount + loadedTimeseriesCount) > 0
        decision = "TIMESERIES_OR_SIMOUT_FOUND_NEEDS_MAPPING";
        reason = "发现timeseries/simout时程证据；尚需核对时间轴、激励、楼层及方法映射。";
    elseif simoutNameCount > 0
        decision = "EXCLUDED_INCOMPATIBLE_SIMOUT_SHAPE";
        reason = "虽发现SimOut/yout/response命名变量（" + ...
            strjoin(simoutShapeItems, ";") + ...
            "），但它不是40961×3×3，也没有可确认的40961点时间轴及楼层×方法响应通道，不能支持图3-5至图3-15。";
    else
        decision = "EXCLUDED_NO_BOARD18_TIMESERIES";
        reason = "变量目录及必要的选择性只读load均未发现40961×3×3响应、timeseries或simout时程。";
    end
    if loadFailureCount > 0
        reason = reason + sprintf(' 有%d个可疑变量选择性load失败，失败信息已逐变量保留。', ...
            loadFailureCount);
    end
    if ~scanHashMatch
        reason = reason + " 当前审核前SHA-256与历史扫描记录不一致。";
    end
    if ~hashUnchanged
        reason = reason + " 审核前后SHA-256不一致，原件保护失败。";
    end

    adjudication(end + 1, :) = { ... %#ok<AGROW>
        fileIndex, string(sourcePath), double(fileInfo.bytes), scanSha256, ...
        sha256Before, sha256After, scanHashMatch, hashUnchanged, matFormat, ...
        whosStatus, whosError, inspectionMethod, numel(whosVariables), ...
        loadAttemptCount, loadSuccessCount, loadFailureCount, ...
        exactTensorCount, timeseriesClassCount, simoutNameCount, ...
        strjoin(simoutShapeItems, ";"), ...
        loadedExactTensorCount, loadedTimeseriesCount, hdf5DatasetCount, ...
        supportsBoard18, decision, reason};

    fprintf('[%d/%d] %s | whos=%s | variables=%d | decision=%s | hash=%d\n', ...
        fileIndex, height(candidates), sourcePath, whosStatus, ...
        numel(whosVariables), decision, hashUnchanged);
end

successDirsAfter = list_success_directories(boardDir);
newSuccessDirs = setdiff(successDirsAfter, successDirsBefore, 'stable');

writetable(inventory, inventoryFile, 'Encoding', 'UTF-8');
writetable(adjudication, adjudicationFile, 'Encoding', 'UTF-8');

allHashesUnchanged = all(adjudication.hash_unchanged);
allScanHashesMatch = all(adjudication.scan_hash_match);
inspectionCompleteCount = sum(adjudication.whos_status == "PASS" | ...
    contains(adjudication.inspection_method, "h5info"));
allInspectionsComplete = inspectionCompleteCount == height(adjudication) && ...
    ~any(adjudication.adjudication == "INSPECTION_FAILED_WITH_EVIDENCE");
allRequiredGates = height(adjudication) == 6 && allHashesUnchanged && ...
    allScanHashesMatch && allInspectionsComplete && isempty(newSuccessDirs);

if allRequiredGates && any(adjudication.load_failure_count > 0)
    overallStatus = "PASS_WITH_RECORDED_SELECTIVE_LOAD_FAILURES";
elseif allRequiredGates
    overallStatus = "PASS";
else
    overallStatus = "FAIL";
end

summary = struct();
summary.generated_at = char(datetime('now', 'TimeZone', 'UTC', ...
    'Format', 'yyyy-MM-dd''T''HH:mm:ss.SSSXXX'));
summary.matlab_version = version;
summary.overall_status = char(overallStatus);
summary.scan_file = scanFile;
summary.scan_file_sha256 = sha256_file(scanFile);
summary.manual_candidate_count = height(candidates);
summary.whos_pass_count = sum(adjudication.whos_status == "PASS");
summary.hdf5_fallback_file_count = sum(contains(adjudication.inspection_method, "h5info"));
summary.inspection_complete_count = inspectionCompleteCount;
summary.unique_source_sha256_count = numel(unique(adjudication.source_sha256_before));
summary.exact_40961x3x3_file_count = sum(adjudication.exact_40961x3x3_count > 0 | ...
    adjudication.loaded_exact_tensor_count > 0);
summary.timeseries_or_simout_file_count = sum(adjudication.timeseries_class_count > 0 | ...
    adjudication.loaded_timeseries_or_simout_count > 0);
summary.supports_board18_timeseries_file_count = sum(adjudication.supports_board18_timeseries);
summary.excluded_no_board18_timeseries_count = sum(...
    adjudication.adjudication == "EXCLUDED_NO_BOARD18_TIMESERIES");
summary.excluded_incompatible_simout_shape_count = sum(...
    adjudication.adjudication == "EXCLUDED_INCOMPATIBLE_SIMOUT_SHAPE");
summary.total_excluded_file_count = ...
    summary.excluded_no_board18_timeseries_count + ...
    summary.excluded_incompatible_simout_shape_count;
summary.inspection_failure_file_count = sum(...
    adjudication.adjudication == "INSPECTION_FAILED_WITH_EVIDENCE");
summary.selective_load_attempt_count = sum(adjudication.load_attempt_count);
summary.selective_load_success_count = sum(adjudication.load_success_count);
summary.selective_load_failure_count = sum(adjudication.load_failure_count);
summary.scan_hash_match_count = sum(adjudication.scan_hash_match);
summary.source_hash_unchanged_count = sum(adjudication.hash_unchanged);
summary.all_original_files_unchanged = allHashesUnchanged;
summary.success_directories_before = cellstr(successDirsBefore);
summary.success_directories_after = cellstr(successDirsAfter);
summary.success_directories_created_by_script = cellstr(newSuccessDirs);
summary.simulink_run = false;
summary.plot_run = false;
summary.source_write_operation = false;
summary.inventory_csv = inventoryFile;
summary.inventory_row_count = height(inventory);
summary.inventory_csv_sha256 = sha256_file(inventoryFile);
summary.adjudication_csv = adjudicationFile;
summary.adjudication_row_count = height(adjudication);
summary.adjudication_csv_sha256 = sha256_file(adjudicationFile);
summary.files = table2struct(adjudication);

jsonText = jsonencode(summary, 'PrettyPrint', true);
fid = fopen(summaryFile, 'w', 'n', 'UTF-8');
assert(fid >= 0, '无法写入JSON摘要：%s', summaryFile);
cleanupFile = onCleanup(@() fclose_if_open(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', jsonText);
fclose(fid);
clear cleanupFile;

fprintf('审核状态：%s\n', overallStatus);
fprintf('变量清单：%d行，%s\n', height(inventory), inventoryFile);
fprintf('逐文件裁决：%d行，%s\n', height(adjudication), adjudicationFile);
fprintf('40961x3x3文件：%d；timeseries/simout文件：%d；排除文件：%d\n', ...
    summary.exact_40961x3x3_file_count, ...
    summary.timeseries_or_simout_file_count, ...
    summary.total_excluded_file_count);
fprintf('原件前后哈希一致：%d/%d；新建成功目录：%d；Simulink运行：0\n', ...
    summary.source_hash_unchanged_count, height(adjudication), numel(newSuccessDirs));

assert(allRequiredGates, ...
    '人工候选审核未通过全部门槛；请查看%s。', summaryFile);


function T = make_inventory_table()
names = {'candidate_index','absolute_path','source_sha256_before', ...
    'mat_format','inspection_method','variable_index','variable_name', ...
    'variable_class','dimensions','element_count','bytes','is_complex', ...
    'is_sparse','is_exact_40961x3x3','is_timeseries_class', ...
    'name_has_timeseries_signature','load_attempted','load_status', ...
    'loaded_class','loaded_dimensions','loaded_sample_count', ...
    'loaded_has_exact_tensor','loaded_has_timeseries_or_simout', ...
    'nested_summary','inspection_error'};
types = {'double','string','string','string','string','double','string', ...
    'string','string','double','double','logical','logical','logical', ...
    'logical','logical','logical','string','string','string','double', ...
    'logical','logical','string','string'};
T = table('Size', [0 numel(names)], 'VariableTypes', types, ...
    'VariableNames', names);
end


function T = make_adjudication_table()
names = {'candidate_index','absolute_path','size_bytes','scan_sha256', ...
    'source_sha256_before','source_sha256_after','scan_hash_match', ...
    'hash_unchanged','mat_format','whos_status','whos_error', ...
    'inspection_method','variable_count','load_attempt_count', ...
    'load_success_count','load_failure_count','exact_40961x3x3_count', ...
    'timeseries_class_count','simout_name_count','simout_shape_summary', ...
    'loaded_exact_tensor_count','loaded_timeseries_or_simout_count', ...
    'hdf5_dataset_count','supports_board18_timeseries','adjudication','reason'};
types = {'double','string','double','string','string','string','logical', ...
    'logical','string','string','string','string','double','double', ...
    'double','double','double','double','double','string', ...
    'double','double','double','logical','string','string'};
T = table('Size', [0 numel(names)], 'VariableTypes', types, ...
    'VariableNames', names);
end


function details = empty_loaded_details()
details = struct('valueClass', "", 'valueSize', "", 'sampleCount', 0, ...
    'hasExactTensor', false, 'hasTimeseriesOrSimout', false, ...
    'nestedSummary', "");
end


function details = inspect_loaded_value(value, variableName)
details = empty_loaded_details();
details.valueClass = string(class(value));
details.valueSize = size_string(size(value));
details.hasExactTensor = is_exact_response_tensor_size(size(value));

if isnumeric(value) || islogical(value)
    if ~isempty(value)
        details.sampleCount = size(value, 1);
    end
    % 单列、任意长度的 SimOut 也可能只是参数扫描或稳定性指标。
    % 只有与板块18冻结基线长度一致且含时间/响应列的数值矩阵，才作为
    % 可继续映射的 simout 时程证据。
    if has_simout_response_name(variableName) && ...
            size(value, 1) == 40961 && size(value, 2) >= 2
        details.hasTimeseriesOrSimout = true;
    end
    return;
end

if isa(value, 'timeseries') || is_timeseries_class_name(class(value))
    details.hasTimeseriesOrSimout = true;
    try
        timeValue = value.Time;
        dataValue = value.Data;
        details.sampleCount = numel(timeValue);
        details.hasExactTensor = details.hasExactTensor || ...
            is_exact_response_tensor_size(size(dataValue));
        details.nestedSummary = "Time:" + size_string(size(timeValue)) + ...
            ";Data:" + size_string(size(dataValue));
    catch ME
        details.nestedSummary = "timeseries属性读取失败:" + sanitize_message(ME.message);
    end
    return;
end

if istimetable(value)
    details.sampleCount = height(value);
    details.hasTimeseriesOrSimout = height(value) > 0 && width(value) >= 1;
    details.nestedSummary = "timetable变量:" + ...
        strjoin(string(value.Properties.VariableNames), ";");
    return;
end

if istable(value)
    details.sampleCount = height(value);
    names = string(value.Properties.VariableNames);
    details.hasTimeseriesOrSimout = height(value) == 40961 && width(value) >= 2 && ...
        any(arrayfun(@has_timeseries_name_signature, names));
    details.nestedSummary = "table变量:" + strjoin(names, ";");
    return;
end

if isstruct(value)
    [details.hasExactTensor, details.hasTimeseriesOrSimout, ...
        details.sampleCount, details.nestedSummary] = inspect_struct_value(value);
    return;
end

if iscell(value)
    summaries = strings(0, 1);
    maxItems = min(numel(value), 25);
    for index = 1:maxItems
        cellValue = value{index};
        summaries(end + 1, 1) = sprintf('{%d}:%s:%s', index, ... %#ok<AGROW>
            class(cellValue), size_string(size(cellValue)));
        details.hasExactTensor = details.hasExactTensor || ...
            is_exact_response_tensor_size(size(cellValue));
        details.hasTimeseriesOrSimout = details.hasTimeseriesOrSimout || ...
            is_timeseries_class_name(class(cellValue));
        if has_simout_response_name(variableName) && isnumeric(cellValue) && ...
                size(cellValue, 1) == 40961 && size(cellValue, 2) >= 2
            details.hasTimeseriesOrSimout = true;
        end
    end
    details.nestedSummary = strjoin(summaries, ";");
end
end


function [hasExact, hasTimeseries, sampleCount, summaryText] = inspect_struct_value(value)
hasExact = false;
hasTimeseries = false;
sampleCount = 0;
summaryItems = strings(0, 1);
timeLengths = [];
responseLengths = [];
fields = string(fieldnames(value));
if isempty(value)
    summaryText = "空struct";
    return;
end
firstValue = value(1);
for fieldIndex = 1:numel(fields)
    fieldName = fields(fieldIndex);
    try
        fieldValue = firstValue.(char(fieldName));
        fieldClass = string(class(fieldValue));
        fieldSize = size(fieldValue);
        summaryItems(end + 1, 1) = fieldName + ":" + fieldClass + ... %#ok<AGROW>
            ":" + size_string(fieldSize);
        hasExact = hasExact || is_exact_response_tensor_size(fieldSize);
        hasTimeseries = hasTimeseries || is_timeseries_class_name(fieldClass);
        if has_time_only_name(fieldName) && (isnumeric(fieldValue) || isduration(fieldValue))
            timeLengths(end + 1) = numel(fieldValue); %#ok<AGROW>
        end
        if has_simout_response_name(fieldName) && ...
                (isnumeric(fieldValue) || islogical(fieldValue)) && ...
                size(fieldValue, 1) == 40961 && size(fieldValue, 2) >= 2
            responseLengths(end + 1) = size(fieldValue, 1); %#ok<AGROW>
            hasTimeseries = true;
        end
    catch ME
        summaryItems(end + 1, 1) = fieldName + ":读取失败:" + ... %#ok<AGROW>
            sanitize_message(ME.message);
    end
end
if ~isempty(timeLengths)
    sampleCount = max(timeLengths);
end
if ~isempty(timeLengths) && ~isempty(responseLengths)
    hasTimeseries = hasTimeseries || any(ismember(timeLengths, responseLengths));
end
summaryText = strjoin(summaryItems, ";");
end


function tf = is_exact_response_tensor_size(dimensions)
dimensions = double(dimensions(:).');
tf = isequal(dimensions, [40961 3 3]);
end


function tf = is_timeseries_class_name(className)
className = lower(string(className));
tf = contains(className, "timeseries") || contains(className, "timetable");
end


function tf = is_container_class(className)
className = lower(string(className));
tf = any(className == ["struct", "cell", "table", "timetable"]) || ...
    contains(className, "simulink") || contains(className, "timeseries");
end


function tf = has_timeseries_name_signature(name)
name = lower(string(name));
tokens = ["simout", "tout", "yout", "time", "response", "result", ...
    "output", "disp", "accel"];
tf = any(contains(name, tokens));
end


function tf = has_simout_response_name(name)
name = lower(string(name));
tokens = ["simout", "yout", "response"];
tf = any(contains(name, tokens));
end


function tf = has_time_only_name(name)
name = lower(string(name));
tf = contains(name, "time") || name == "tout" || name == "t" || name == "time_s";
end


function text = size_string(dimensions)
dimensions = double(dimensions(:).');
if isempty(dimensions)
    text = "[]";
else
    text = string(mat2str(dimensions));
end
end


function count = prod_or_zero(dimensions)
if isempty(dimensions)
    count = 0;
else
    count = prod(double(dimensions));
end
end


function value = logical_field(item, fieldName)
if isfield(item, fieldName)
    value = logical(item.(fieldName));
else
    value = false;
end
end


function formatName = detect_mat_format(filePath)
fid = fopen(filePath, 'rb');
assert(fid >= 0, '无法读取MAT文件头：%s', filePath);
cleanup = onCleanup(@() fclose_if_open(fid)); %#ok<NASGU>
headerBytes = fread(fid, 128, '*uint8');
headerText = char(headerBytes(:).');
if contains(headerText, 'MATLAB 7.3 MAT-file') || ...
        (numel(headerBytes) >= 8 && isequal(headerBytes(1:8).', ...
        uint8([137 72 68 70 13 10 26 10])))
    formatName = 'MATLAB 7.3/HDF5';
elseif contains(headerText, 'MATLAB 5.0 MAT-file')
    formatName = 'MATLAB 5.0 MAT-file';
else
    formatName = 'UNKNOWN_MAT_FORMAT';
end
end


function datasets = collect_h5_datasets(groupInfo)
datasets = struct('name', {}, 'size', {}, 'dataClass', {});
for datasetIndex = 1:numel(groupInfo.Datasets)
    dataset = groupInfo.Datasets(datasetIndex);
    if strcmp(groupInfo.Name, '/')
        datasetPath = ['/' dataset.Name];
    else
        datasetPath = [groupInfo.Name '/' dataset.Name];
    end
    dataClass = "UNKNOWN";
    if isfield(dataset, 'Datatype') && isfield(dataset.Datatype, 'Class')
        dataClass = string(dataset.Datatype.Class);
    end
    dataSize = [];
    if isfield(dataset, 'Dataspace') && isfield(dataset.Dataspace, 'Size')
        dataSize = dataset.Dataspace.Size;
    end
    datasets(end + 1) = struct('name', datasetPath, ... %#ok<AGROW>
        'size', dataSize, 'dataClass', char(dataClass));
end
for groupIndex = 1:numel(groupInfo.Groups)
    childDatasets = collect_h5_datasets(groupInfo.Groups(groupIndex));
    datasets = [datasets childDatasets]; %#ok<AGROW>
end
end


function names = list_success_directories(boardDir)
items = dir(boardDir);
items = items([items.isdir]);
rawNames = string({items.name});
rawNames = rawNames(rawNames ~= "." & rawNames ~= "..");
mask = false(size(rawNames));
for index = 1:numel(rawNames)
    mask(index) = ~isempty(regexp(char(rawNames(index)), ...
        '^(图3-|F3-)[0-9]+', 'once'));
end
names = sort(rawNames(mask));
end


function hexText = sha256_file(filePath)
digest = java.security.MessageDigest.getInstance('SHA-256');
fid = fopen(filePath, 'rb');
assert(fid >= 0, '无法读取文件以计算SHA-256：%s', filePath);
cleanup = onCleanup(@() fclose_if_open(fid)); %#ok<NASGU>
while true
    bytes = fread(fid, 1024 * 1024, '*uint8');
    if isempty(bytes)
        break;
    end
    digest.update(typecast(bytes(:), 'int8'));
end
hashBytes = typecast(digest.digest(), 'uint8');
hexText = upper(reshape(dec2hex(hashBytes, 2).', 1, []));
end


function message = sanitize_message(message)
message = string(message);
message = replace(message, [newline, char(13), char(10)], " ");
message = strip(message);
end


function fclose_if_open(fid)
if isnumeric(fid) && isscalar(fid) && fid > 0
    try
        fclose(fid);
    catch
        % onCleanup 可能在显式 fclose 后再次触发；已关闭即视为完成。
    end
end
end
