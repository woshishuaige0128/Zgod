function run_one_board20_candidate(configPath)
%RUN_ONE_BOARD20_CANDIDATE 在干净MATLAB会话中运行一条板块20原始MLX路线。
% 外层只负责证据捕获，不修改候选MLX或其上游脚本。

configPath = char(configPath);
cfg = jsondecode(fileread(configPath));
originalDirectory = pwd;
cleanupObject = onCleanup(@() cleanup_run(originalDirectory)); %#ok<NASGU>

assert(isfolder(cfg.work_dir), 'Board20:MissingWorkDirectory', ...
    '工作目录不存在：%s', cfg.work_dir);
assert(isfile(cfg.candidate_mlx), 'Board20:MissingCandidate', ...
    '候选MLX不存在：%s', cfg.candidate_mlx);

status = struct();
status.schema = 'board20_original_mlx_run_status_v2';
status.route_id = cfg.route_id;
status.declared_method = cfg.declared_method;
status.declared_division = cfg.declared_division;
status.actual_code_identity = cfg.actual_code_identity;
status.execution_artifact = cfg.execution_artifact;
status.replicate = cfg.replicate;
status.dependency_mode = cfg.dependency_mode;
status.config_path = configPath;
status.candidate_mlx = cfg.candidate_mlx;
status.candidate_sha256 = cfg.candidate_sha256;
status.source_contains_dlqr = logical(cfg.source_contains_dlqr);
status.runtime_dlqr_reached = false;
status.runtime_call_evidence = cfg.runtime_call_evidence;
status.profile_enabled = logical(cfg.enable_profile);
status.expected_scan_point_count = cfg.expected_scan_point_count;
status.expected_stab_shape = cfg.expected_stab_shape;
status.source_save_call_count = cfg.source_save_call_count;
status.started_at = timestamp_now();
status.finished_at = '';
status.final_status = 'RUNNING';
status.execution_status = 'NOT_STARTED';
status.evidence_status = 'NOT_EVALUATED';
status.process_exit_semantics = 'RUNNING';
status.current_stage = 'CONFIG';
status.current_file = '';
status.failed_stage = '';
status.failed_file = '';
status.error = empty_error_record();
status.capture_errors = {};
status.available_scientific_variables = {};
status.scientific_arrays_status = 'NOT_EVALUATED';
status.actual_stab_shape = [];
status.actual_scan_point_count = -1;
status.actual_scan_point_count_method = 'NOT_EVALUATED';
status.scan_evidence = empty_scan_evidence();
status.instrumentation = empty_instrumentation_record();
status.author_saved_files = empty_file_records();
status.stages = empty_stage_records();
status.work_files_before = empty_file_records();
status.work_files_after = empty_file_records();
status.input_hashes_before = empty_hash_records();
status.input_hashes_after = empty_hash_records();

assert(~isfile(cfg.status_json), 'Board20:RunAlreadyExists', ...
    '运行状态已存在，拒绝复用同一rep：%s', cfg.status_json);
assert_pristine_outputs(cfg);
assert_pristine_work(cfg);

restoredefaultpath;
rehash toolboxcache;
cd(cfg.work_dir);
addpath(cfg.work_dir, '-begin');
dependencyDirectories = normalize_text_list(cfg.dependency_directories);
for k = 1:numel(dependencyDirectories)
    assert(isfolder(dependencyDirectories{k}), ...
        'Board20:MissingDependencyDirectory', ...
        '依赖目录不存在：%s', dependencyDirectories{k});
    addpath(dependencyDirectories{k}, '-begin');
end

status.environment = environment_record();
diary(cfg.diary_file);
fprintf('BOARD20_ROUTE_START route=%s artifact=%s replicate=%s\n', ...
    cfg.route_id, cfg.execution_artifact, cfg.replicate);
fprintf('CONFIG=%s\n', configPath);
fprintf('WORK=%s\n', cfg.work_dir);

evalin('base', 'clearvars');
initialVariables = snapshot_base_variables();
if ~isempty(initialVariables)
    error('Board20:DirtyBaseWorkspace', ...
        '清理后base工作区仍含%d个变量。', numel(initialVariables));
end
status.stages(end + 1) = make_stage('clean_base_workspace', 'PASS', initialVariables); %#ok<AGROW>
write_json(cfg.status_json, status);

profileWasStarted = false;
executionSucceeded = false;
originalError = [];
currentStage = 'INPUT_PREFLIGHT';
currentFile = '';
try
    status.current_stage = currentStage;
    status.instrumentation = verify_instrumentation(cfg, configPath);
    status.input_hashes_before = verify_file_contracts(cfg);
    status.work_files_before = directory_snapshot(cfg.work_dir);
    status.stages(end + 1) = make_stage( ...
        'input_hash_preflight', 'PASS', empty_variable_records()); %#ok<AGROW>
    write_json(cfg.status_json, status);

    upstreamFiles = normalize_text_list(cfg.upstream_files);
    for k = 1:numel(upstreamFiles)
        stageName = sprintf('upstream_%02d_%s', k, file_basename(upstreamFiles{k}));
        currentStage = stageName;
        currentFile = upstreamFiles{k};
        status.current_stage = currentStage;
        status.current_file = currentFile;
        fprintf('BOARD20_STAGE_START route=%s stage=%s file=%s\n', ...
            cfg.route_id, stageName, upstreamFiles{k});
        run_in_base(upstreamFiles{k});
        variables = snapshot_base_variables();
        status.stages(end + 1) = make_stage(stageName, 'PASS', variables); %#ok<AGROW>
        write_json(cfg.status_json, status);
        fprintf('BOARD20_STAGE_PASS route=%s stage=%s variables=%d\n', ...
            cfg.route_id, stageName, numel(variables));
    end

    beforeCandidate = snapshot_base_variables();
    status.stages(end + 1) = make_stage( ...
        'before_candidate_original_mlx', 'PASS', beforeCandidate); %#ok<AGROW>
    write_json(cfg.status_json, status);

    currentStage = 'candidate_original_mlx';
    currentFile = cfg.candidate_mlx;
    status.current_stage = currentStage;
    status.current_file = currentFile;
    if status.profile_enabled
        profile clear;
        profile on;
        profileWasStarted = true;
    end
    fprintf('BOARD20_CANDIDATE_START route=%s file=%s\n', ...
        cfg.route_id, cfg.candidate_mlx);
    run_in_base(cfg.candidate_mlx);
    executionSucceeded = true;
catch caughtError
    originalError = caughtError;
end

if executionSucceeded
    if profileWasStarted
        profile off;
        profileWasStarted = false;
        [profileInfo, ~] = capture_profile(cfg.profile_info);
        status.profile_function_count = numel(profileInfo.FunctionTable);
    else
        status.profile_function_count = 0;
    end
    afterCandidate = snapshot_base_variables();
    status.runtime_dlqr_reached = any(strcmp({afterCandidate.name}, 'K_lqr'));
    status.stages(end + 1) = make_stage( ...
        'candidate_original_mlx', 'PASS', afterCandidate); %#ok<AGROW>
    status.execution_status = 'EXECUTION_SUCCESS';
    status.current_stage = 'EVIDENCE_CAPTURE';
    status.current_file = '';
    status.capture_errors = [status.capture_errors, ...
        save_base_workspace(cfg.workspace_success)];
    [availableScientific, scientificErrors] = save_scientific_arrays( ...
        cfg.scientific_arrays, cfg.raw_stab);
    status.available_scientific_variables = availableScientific;
    status.capture_errors = [status.capture_errors, scientificErrors];
    if any(strcmp({afterCandidate.name}, 'stab'))
        stabValue = evalin('base', 'stab');
        status.scan_evidence = analyze_stab(stabValue, cfg);
        status.actual_stab_shape = status.scan_evidence.actual_shape;
        status.actual_scan_point_count = ...
            status.scan_evidence.actual_finite_positive_point_count;
        status.actual_scan_point_count_method = ...
            'FINAL_STAB_EXPECTED_REGIONS_FINITE_POSITIVE';
        if status.scan_evidence.expected_region_point_count ~= ...
                double(cfg.expected_scan_point_count)
            status.capture_errors{end + 1} = sprintf( ...
                'scan_contract_region_count_mismatch:expected=%d:regions=%d', ...
                cfg.expected_scan_point_count, ...
                status.scan_evidence.expected_region_point_count);
        end
        if status.actual_scan_point_count ~= double(cfg.expected_scan_point_count)
            status.capture_errors{end + 1} = sprintf( ...
                'scan_populated_point_count_mismatch:expected=%d:actual=%d', ...
                cfg.expected_scan_point_count, status.actual_scan_point_count);
        end
        if status.scan_evidence.actual_finite_point_count ~= ...
                status.scan_evidence.expected_region_point_count
            status.capture_errors{end + 1} = sprintf( ...
                'scan_nonfinite_values:expected_finite=%d:actual_finite=%d', ...
                status.scan_evidence.expected_region_point_count, ...
                status.scan_evidence.actual_finite_point_count);
        end
        if status.scan_evidence.outside_region_nonzero_count ~= 0
            status.capture_errors{end + 1} = sprintf( ...
                'scan_unexpected_outside_nonzero=%d', ...
                status.scan_evidence.outside_region_nonzero_count);
        end
    else
        status.capture_errors{end + 1} = 'missing_expected_stab_after_execution_success';
    end
    try
        status.author_saved_files = collect_author_saved( ...
            cfg, 'FINAL_FILE_AFTER_DECLARED_SAVE_CALLS');
    catch saveTargetError
        status.capture_errors{end + 1} = sprintf( ...
            'author_saved_capture:%s:%s', ...
            saveTargetError.identifier, saveTargetError.message);
    end
    try
        status.input_hashes_after = verify_file_contracts(cfg);
    catch hashError
        status.capture_errors{end + 1} = sprintf( ...
            'input_hash_postflight:%s:%s', hashError.identifier, hashError.message);
    end
    try
        status.work_files_after = directory_snapshot(cfg.work_dir);
    catch snapshotError
        status.capture_errors{end + 1} = sprintf( ...
            'directory_snapshot:%s:%s', snapshotError.identifier, snapshotError.message);
    end
    if ~isfile(cfg.workspace_success)
        status.capture_errors{end + 1} = 'missing_workspace_complete_file';
    end
    if ~isfile(cfg.scientific_arrays)
        status.capture_errors{end + 1} = 'missing_scientific_arrays_file';
        status.scientific_arrays_status = 'MISSING';
    else
        status.scientific_arrays_status = 'PRESENT';
    end
    if ~isfile(cfg.raw_stab)
        status.capture_errors{end + 1} = 'missing_raw_stab_file';
    end
    if ~isempty(status.actual_stab_shape) && ...
            ~isequal(double(status.actual_stab_shape(:).'), ...
            double(cfg.expected_stab_shape(:).'))
        status.capture_errors{end + 1} = sprintf( ...
            'stab_shape_mismatch:expected=%s:actual=%s', ...
            mat2str(cfg.expected_stab_shape), mat2str(status.actual_stab_shape));
    end
    requiredAuthorTargets = normalize_text_list(cfg.author_save_targets);
    for k = 1:numel(requiredAuthorTargets)
        if ~isfile(fullfile(cfg.work_dir, requiredAuthorTargets{k}))
            status.capture_errors{end + 1} = sprintf( ...
                'missing_author_save_target:%s', requiredAuthorTargets{k});
        end
    end
    status.finished_at = timestamp_now();
    if isempty(status.capture_errors)
        status.evidence_status = 'PASS';
        status.final_status = 'SUCCESS';
        status.process_exit_semantics = 'EXPECTED_ZERO';
    else
        status.evidence_status = 'FAIL';
        status.final_status = 'EXECUTION_SUCCESS_EVIDENCE_FAIL';
        status.process_exit_semantics = 'EXPECTED_NONZERO_EVIDENCE_FAILURE';
    end
    write_json(cfg.status_json, status);
    if strcmp(status.evidence_status, 'PASS')
        fprintf(['BOARD20_ROUTE_SUCCESS route=%s variables=%d ' ...
            'runtime_dlqr_reached=%d\n'], cfg.route_id, numel(afterCandidate), ...
            status.runtime_dlqr_reached);
        diary off;
        return;
    end
    fprintf(2, 'BOARD20_EVIDENCE_FAIL route=%s errors=%s\n', ...
        cfg.route_id, strjoin(status.capture_errors, ' | '));
    diary off;
    error('Board20:EvidenceValidationFailed', ...
        '原始MLX执行完成，但证据验收失败：%s', ...
        strjoin(status.capture_errors, ' | '));
else
    if profileWasStarted
        try
            profile off;
        catch
        end
    end
    if status.profile_enabled
        try
            [profileInfo, ~] = capture_profile(cfg.profile_info);
            status.profile_function_count = numel(profileInfo.FunctionTable);
        catch profileError
            status.capture_errors{end + 1} = sprintf( ...
                'profile_capture:%s:%s', profileError.identifier, profileError.message);
        end
    else
        status.profile_function_count = 0;
    end
    status.execution_status = 'EXECUTION_FAIL';
    status.current_stage = 'EVIDENCE_CAPTURE_AFTER_FAILURE';
    status.current_file = '';
    status.failed_stage = currentStage;
    status.failed_file = currentFile;
    try
        failureVariables = snapshot_base_variables();
        status.runtime_dlqr_reached = any(strcmp({failureVariables.name}, 'K_lqr'));
        status.stages(end + 1) = make_stage( ...
            'failure_snapshot', 'FAIL', failureVariables); %#ok<AGROW>
    catch snapshotError
        failureVariables = empty_variable_records();
        status.capture_errors{end + 1} = sprintf( ...
            'variable_snapshot:%s:%s', snapshotError.identifier, snapshotError.message);
    end
    status.capture_errors = [status.capture_errors, ...
        save_base_workspace(cfg.workspace_failure)];
    [availableScientific, scientificErrors] = save_scientific_arrays( ...
        cfg.scientific_arrays, cfg.raw_stab);
    status.available_scientific_variables = availableScientific;
    status.capture_errors = [status.capture_errors, scientificErrors];
    if isempty(availableScientific)
        status.scientific_arrays_status = 'NOT_APPLICABLE_NO_REQUESTED_VARIABLES';
    elseif isfile(cfg.scientific_arrays)
        status.scientific_arrays_status = 'PRESENT';
    else
        status.scientific_arrays_status = 'MISSING';
        status.capture_errors{end + 1} = ...
            'missing_scientific_arrays_despite_available_variables';
    end
    try
        status.author_saved_files = collect_author_saved(cfg, 'PARTIAL_AT_FAILURE');
    catch saveTargetError
        status.capture_errors{end + 1} = sprintf( ...
            'author_saved_capture:%s:%s', ...
            saveTargetError.identifier, saveTargetError.message);
    end
    status.error = exception_record(originalError);
    try
        status.input_hashes_after = verify_file_contracts(cfg);
    catch hashError
        status.capture_errors{end + 1} = sprintf( ...
            'input_hash_postflight:%s:%s', hashError.identifier, hashError.message);
    end
    try
        status.work_files_after = directory_snapshot(cfg.work_dir);
    catch snapshotError
        status.capture_errors{end + 1} = sprintf( ...
            'directory_snapshot:%s:%s', snapshotError.identifier, snapshotError.message);
    end
    if ~isfile(cfg.workspace_failure)
        status.capture_errors{end + 1} = 'missing_workspace_failure_file';
    end
    try
        write_text(fullfile(cfg.run_log_dir, 'error_report.txt'), ...
            getReport(originalError, 'extended', 'hyperlinks', 'off'));
    catch reportError
        status.capture_errors{end + 1} = sprintf( ...
            'error_report_write:%s:%s', reportError.identifier, reportError.message);
    end
    if isempty(status.capture_errors)
        status.evidence_status = 'PASS';
    else
        status.evidence_status = 'FAIL';
    end
    status.finished_at = timestamp_now();
    status.final_status = 'EXECUTION_FAIL';
    status.process_exit_semantics = 'EXPECTED_NONZERO_RETHROW';
    try
        write_json(cfg.status_json, status);
    catch jsonError
        fprintf(2, 'BOARD20_STATUS_WRITE_FAIL identifier=%s message=%s\n', ...
            jsonError.identifier, jsonError.message);
    end
    fprintf(2, 'BOARD20_ROUTE_FAIL route=%s identifier=%s message=%s\n', ...
        cfg.route_id, originalError.identifier, originalError.message);
    diary off;
    rethrow(originalError);
end
end


function run_in_base(pathValue)
escaped = escape_matlab_text(pathValue);
evalin('base', sprintf("run('%s');", escaped));
end


function errors = save_base_workspace(pathValue)
errors = {};
try
    escaped = escape_matlab_text(pathValue);
    evalin('base', sprintf("save('%s', '-v7.3');", escaped));
catch saveError
    errors{end + 1} = sprintf('workspace_save:%s:%s', ...
        saveError.identifier, saveError.message);
end
end


function [available, errors] = save_scientific_arrays(scientificPath, rawStabPath)
requested = {'stab', 'Q', 'R', 'K_lqr', 'DeltaK', 'DeltaC', 'DeltaG', ...
    'Ad', 'Bd', 'Acl', 'MRrt', 'CRrt', 'KRrt', 'MPrt', 'CPrt', 'KPrt', ...
    'MRren', 'CRren', 'KRren', 'MPren', 'CPren', 'KPren', ...
    'MRcb', 'CRcb', 'KRcb', 'K1', 'K2', 'C1', 'C2', 'H', 'G'};
available = {};
errors = {};
try
    baseVariables = snapshot_base_variables();
    baseNames = {baseVariables.name};
    available = requested(ismember(requested, baseNames));
catch snapshotError
    errors{end + 1} = sprintf('scientific_snapshot:%s:%s', ...
        snapshotError.identifier, snapshotError.message);
    return;
end
if ~isempty(available)
    try
        variableArguments = cellfun( ...
            @(name) sprintf('''%s''', name), available, 'UniformOutput', false);
        command = sprintf('save(''%s'', %s, ''-v7.3'');', ...
            escape_matlab_text(scientificPath), strjoin(variableArguments, ', '));
        evalin('base', command);
    catch saveError
        errors{end + 1} = sprintf('scientific_save:%s:%s', ...
            saveError.identifier, saveError.message);
    end
end
if ismember('stab', available)
    try
        evalin('base', sprintf("save('%s', 'stab', '-v7.3');", ...
            escape_matlab_text(rawStabPath)));
    catch saveError
        errors{end + 1} = sprintf('raw_stab_save:%s:%s', ...
            saveError.identifier, saveError.message);
    end
end
end


function records = collect_author_saved(cfg, completeness)
targets = normalize_text_list(cfg.author_save_targets);
records = empty_file_records();
for k = 1:numel(targets)
    source = fullfile(cfg.work_dir, targets{k});
    record = make_file_record();
    record.name = targets{k};
    record.source_path = source;
    record.exists = isfile(source);
    record.completeness = completeness;
    if record.exists
        [~, name, extension] = fileparts(targets{k});
        destination = fullfile(cfg.author_saved_dir, sprintf( ...
            '%s__%s__%s%s', cfg.route_id, cfg.replicate, name, extension));
        copyfile(source, destination);
        item = dir(destination);
        record.copied_path = destination;
        record.bytes = item.bytes;
        record.sha256 = sha256_file(source);
        record.copied_sha256 = sha256_file(destination);
        record.hash_match = strcmp(record.sha256, record.copied_sha256);
        record.mtime_iso = char(datetime(item.datenum, 'ConvertFrom', ...
            'datenum', 'TimeZone', 'local', 'Format', ...
            'yyyy-MM-dd''T''HH:mm:ssXXX'));
        assert(record.hash_match, 'Board20:AuthorSaveCopyMismatch', ...
            '作者保存文件复制前后哈希不一致：%s', targets{k});
    end
    records(end + 1) = record; %#ok<AGROW>
end
end


function [profileInfo, dlqrReached] = capture_profile(outputPath)
profileInfo = profile('info');
save(outputPath, 'profileInfo', '-v7.3');
dlqrReached = false;
if isfield(profileInfo, 'FunctionTable') && ~isempty(profileInfo.FunctionTable)
    names = {profileInfo.FunctionTable.CompleteName};
    dlqrReached = any(contains(lower(string(names)), 'dlqr'));
end
end


function record = environment_record()
record = struct();
record.matlab_version = version;
record.matlab_release = version('-release');
record.computer = computer;
record.matlab_root = matlabroot;
record.pid = feature('getpid');
record.pwd = pwd;
record.path = path;
record.symbolic_license = logical(license('test', 'Symbolic_Toolbox'));
record.control_license = logical(license('test', 'Control_Toolbox'));
names = {'syms', 'solve', 'vpa', 'ss', 'c2d', 'dlqr', 'eigs', ...
    'fcn_newmark_beta_const'};
resolved = repmat(struct('name', '', 'paths', {{}}), numel(names), 1);
for k = 1:numel(names)
    paths = which(names{k}, '-all');
    if ischar(paths)
        paths = {paths};
    end
    resolved(k).name = names{k};
    resolved(k).paths = paths;
end
record.functions = resolved;
end


function records = snapshot_base_variables()
raw = evalin('base', 'whos');
records = empty_variable_records();
for k = 1:numel(raw)
    sparseValue = false;
    complexValue = false;
    globalValue = false;
    if isfield(raw, 'sparse')
        sparseValue = logical(raw(k).sparse);
    end
    if isfield(raw, 'complex')
        complexValue = logical(raw(k).complex);
    end
    if isfield(raw, 'global')
        globalValue = logical(raw(k).global);
    end
    records(end + 1) = struct( ...
        'name', raw(k).name, ...
        'class', raw(k).class, ...
        'size', raw(k).size, ...
        'bytes', raw(k).bytes, ...
        'is_sparse', sparseValue, ...
        'is_complex', complexValue, ...
        'is_global', globalValue); %#ok<AGROW>
end
end


function records = directory_snapshot(rootPath)
listing = dir(fullfile(rootPath, '**', '*'));
records = empty_file_records();
for k = 1:numel(listing)
    if listing(k).isdir
        continue;
    end
    record = make_file_record();
    record.name = listing(k).name;
    record.source_path = fullfile(listing(k).folder, listing(k).name);
    record.exists = true;
    record.bytes = listing(k).bytes;
    record.sha256 = sha256_file(record.source_path);
    record.mtime_iso = char(datetime(listing(k).datenum, 'ConvertFrom', ...
        'datenum', 'TimeZone', 'local', 'Format', ...
        'yyyy-MM-dd''T''HH:mm:ssXXX'));
    records(end + 1) = record; %#ok<AGROW>
end
end


function stage = make_stage(name, stageStatus, variables)
stage = struct('name', name, 'status', stageStatus, ...
    'timestamp', timestamp_now(), 'variable_count', numel(variables), ...
    'variables', variables);
end


function record = exception_record(exception)
record = struct();
record.identifier = exception.identifier;
record.message = exception.message;
record.report = getReport(exception, 'extended', 'hyperlinks', 'off');
record.stack = repmat(struct('file', '', 'name', '', 'line', 0), 0, 1);
for k = 1:numel(exception.stack)
    record.stack(end + 1) = struct( ...
        'file', exception.stack(k).file, ...
        'name', exception.stack(k).name, ...
        'line', exception.stack(k).line); %#ok<AGROW>
end
record.causes = cell(numel(exception.cause), 1);
for k = 1:numel(exception.cause)
    record.causes{k} = struct( ...
        'identifier', exception.cause{k}.identifier, ...
        'message', exception.cause{k}.message);
end
end


function record = empty_error_record()
record = struct('identifier', '', 'message', '', 'report', '', ...
    'stack', repmat(struct('file', '', 'name', '', 'line', 0), 0, 1), ...
    'causes', {{}});
end


function records = empty_variable_records()
records = repmat(struct('name', '', 'class', '', 'size', [], 'bytes', 0, ...
    'is_sparse', false, 'is_complex', false, 'is_global', false), 0, 1);
end


function records = empty_stage_records()
records = repmat(struct('name', '', 'status', '', 'timestamp', '', ...
    'variable_count', 0, 'variables', empty_variable_records()), 0, 1);
end


function records = empty_file_records()
records = repmat(make_file_record(), 0, 1);
end


function record = make_file_record()
record = struct('name', '', 'source_path', '', 'exists', false, ...
    'copied_path', '', 'bytes', 0, 'sha256', '', 'copied_sha256', '', ...
    'hash_match', [], 'mtime_iso', '', 'completeness', '');
end


function records = empty_hash_records()
records = repmat(struct('kind', '', 'execution_order', 0, 'path', '', ...
    'expected_sha256', '', 'actual_sha256', '', 'match', false, ...
    'frozen_manifest_item_id', ''), 0, 1);
end


function record = empty_instrumentation_record()
record = struct('config_path', '', 'config_hash_file', '', ...
    'config_expected_sha256', '', 'config_actual_sha256', '', ...
    'config_match', false, 'files', empty_instrumentation_file_records());
end


function records = empty_instrumentation_file_records()
records = repmat(struct('name', '', 'path', '', 'expected_sha256', '', ...
    'actual_sha256', '', 'match', false), 0, 1);
end


function record = verify_instrumentation(cfg, configPath)
record = empty_instrumentation_record();
record.config_path = char(configPath);
record.config_hash_file = char(cfg.config_hash_file);
assert(isfile(record.config_hash_file), 'Board20:MissingConfigHashFile', ...
    '缺少run_config封签文件：%s', record.config_hash_file);
record.config_expected_sha256 = upper(strtrim(fileread(record.config_hash_file)));
record.config_actual_sha256 = sha256_file(configPath);
record.config_match = strcmp(record.config_expected_sha256, ...
    record.config_actual_sha256);
assert(record.config_match, 'Board20:ConfigHashMismatch', ...
    'run_config.json与分发时封签不一致。');

names = {'stager', 'matlab_runner', 'outer_executor'};
for k = 1:numel(names)
    name = names{k};
    item = cfg.instrumentation.(name);
    pathValue = char(item.path);
    assert(isfile(pathValue), 'Board20:InstrumentationFileMissing', ...
        '运行仪器文件缺失：%s', pathValue);
    actual = sha256_file(pathValue);
    expected = upper(char(item.sha256));
    match = strcmp(actual, expected);
    record.files(end + 1) = struct( ...
        'name', name, 'path', pathValue, 'expected_sha256', expected, ...
        'actual_sha256', actual, 'match', match); %#ok<AGROW>
    assert(match, 'Board20:InstrumentationHashMismatch', ...
        '运行仪器代码与分发时封签不一致：%s', name);
end
end


function evidence = empty_scan_evidence()
evidence = struct('actual_shape', [], 'expected_region_point_count', 0, ...
    'actual_finite_point_count', 0, ...
    'actual_finite_positive_point_count', 0, ...
    'actual_nonpositive_point_count', 0, ...
    'outside_region_nonzero_count', 0, ...
    'minimum_region_value', NaN, 'maximum_region_value', NaN);
end


function evidence = analyze_stab(stabValue, cfg)
evidence = empty_scan_evidence();
evidence.actual_shape = size(stabValue);
regions = double(cfg.expected_written_regions);
if isvector(regions)
    regions = reshape(regions, 1, 4);
end
assert(size(regions, 2) == 4, 'Board20:InvalidWrittenRegions', ...
    'expected_written_regions必须为N×4。');
mask = false(size(stabValue));
for k = 1:size(regions, 1)
    rowStart = regions(k, 1);
    rowEnd = regions(k, 2);
    columnStart = regions(k, 3);
    columnEnd = regions(k, 4);
    assert(all([rowStart, rowEnd, columnStart, columnEnd] >= 1) && ...
        rowStart <= rowEnd && columnStart <= columnEnd && ...
        rowEnd <= size(stabValue, 1) && columnEnd <= size(stabValue, 2), ...
        'Board20:WrittenRegionOutOfBounds', ...
        '预期写入区域越界：%s', mat2str(regions(k, :)));
    mask(rowStart:rowEnd, columnStart:columnEnd) = true;
end
regionValues = double(stabValue(mask));
evidence.expected_region_point_count = nnz(mask);
evidence.actual_finite_point_count = sum(isfinite(regionValues));
evidence.actual_finite_positive_point_count = ...
    sum(isfinite(regionValues) & regionValues > 0);
evidence.actual_nonpositive_point_count = ...
    sum(isfinite(regionValues) & regionValues <= 0);
evidence.outside_region_nonzero_count = nnz(stabValue(~mask));
if ~isempty(regionValues)
    evidence.minimum_region_value = min(regionValues);
    evidence.maximum_region_value = max(regionValues);
end
end


function values = normalize_text_list(value)
if isempty(value)
    values = {};
elseif ischar(value)
    values = {value};
elseif isstring(value)
    values = cellstr(value(:));
elseif iscell(value)
    values = cellfun(@char, value(:), 'UniformOutput', false);
else
    error('Board20:InvalidTextList', '配置中的文本列表类型不受支持。');
end
end


function name = file_basename(pathValue)
[~, base, extension] = fileparts(pathValue);
name = [base, extension];
end


function escaped = escape_matlab_text(value)
escaped = strrep(char(value), '''', '''''');
end


function value = timestamp_now()
value = char(datetime('now', 'TimeZone', 'local', ...
    'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));
end


function write_json(pathValue, value)
text = jsonencode(value, 'PrettyPrint', true);
fileId = fopen(pathValue, 'w', 'n', 'UTF-8');
if fileId < 0
    error('Board20:JsonOpenFailed', '无法写入JSON：%s', pathValue);
end
cleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
fprintf(fileId, '%s\n', text);
end


function write_text(pathValue, text)
fileId = fopen(pathValue, 'w', 'n', 'UTF-8');
if fileId < 0
    error('Board20:TextOpenFailed', '无法写入文本：%s', pathValue);
end
cleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
fprintf(fileId, '%s\n', text);
end


function assert_pristine_outputs(cfg)
runnerOwned = {cfg.diary_file, cfg.workspace_success, cfg.workspace_failure, ...
    cfg.scientific_arrays, cfg.raw_stab, cfg.profile_info, ...
    fullfile(cfg.run_log_dir, 'error_report.txt')};
for k = 1:numel(runnerOwned)
    assert(~isfile(runnerOwned{k}), 'Board20:ExistingRunnerOutput', ...
        '运行器输出已存在，拒绝复用同一rep：%s', runnerOwned{k});
end
authorTargets = normalize_text_list(cfg.author_save_targets);
for k = 1:numel(authorTargets)
    assert(~isfile(fullfile(cfg.work_dir, authorTargets{k})), ...
        'Board20:ExistingAuthorOutput', ...
        '工作目录已存在作者保存目标，拒绝运行：%s', ...
        authorTargets{k});
end
if isfolder(cfg.author_saved_dir)
    listing = dir(fullfile(cfg.author_saved_dir, '**', '*'));
    assert(~any(~[listing.isdir]), 'Board20:ExistingCapturedAuthorOutput', ...
        '作者保存证据目录非空，拒绝复用同一rep。');
end
end


function assert_pristine_work(cfg)
expected = normalize_text_list(cfg.allowed_work_files);
expected = sort(strrep(expected, '\', '/'));
listing = dir(fullfile(cfg.work_dir, '**', '*'));
actual = {};
rootPrefix = [char(cfg.work_dir), filesep];
for k = 1:numel(listing)
    if listing(k).isdir
        continue;
    end
    absolute = fullfile(listing(k).folder, listing(k).name);
    assert(startsWith(absolute, rootPrefix, 'IgnoreCase', true), ...
        'Board20:WorkFileOutsideRoot', '工作文件越出隔离目录：%s', absolute);
    relative = absolute(numel(rootPrefix) + 1:end);
    actual{end + 1, 1} = strrep(relative, '\', '/'); %#ok<AGROW>
end
actual = sort(actual);
assert(isequal(actual(:), expected(:)), 'Board20:DirtyWorkDirectory', ...
    '工作目录与分发白名单不一致。expected=%s actual=%s', ...
    strjoin(expected, '|'), strjoin(actual, '|'));
end


function records = verify_file_contracts(cfg)
contracts = cfg.file_contracts;
records = empty_hash_records();
for k = 1:numel(contracts)
    pathValue = char(contracts(k).path);
    assert(isfile(pathValue), 'Board20:ContractFileMissing', ...
        '运行合同文件缺失：%s', pathValue);
    actual = sha256_file(pathValue);
    expected = upper(char(contracts(k).expected_sha256));
    match = strcmp(actual, expected);
    record = struct( ...
        'kind', char(contracts(k).kind), ...
        'execution_order', double(contracts(k).execution_order), ...
        'path', pathValue, ...
        'expected_sha256', expected, ...
        'actual_sha256', actual, ...
        'match', match, ...
        'frozen_manifest_item_id', char(contracts(k).frozen_manifest_item_id));
    records(end + 1) = record; %#ok<AGROW>
    assert(match, 'Board20:InputHashMismatch', ...
        '运行输入哈希与步骤1冻结基线不一致：%s', pathValue);
end
end


function value = sha256_file(pathValue)
% R2025b/Windows下用Java MessageDigest读取原始字节，不依赖shell解析。
digest = java.security.MessageDigest.getInstance('SHA-256');
stream = java.io.FileInputStream(java.io.File(char(pathValue)));
cleanup = onCleanup(@() stream.close()); %#ok<NASGU>
channel = stream.getChannel();
buffer = java.nio.ByteBuffer.allocate(1024 * 1024);
while true
    count = channel.read(buffer);
    if count < 0
        break;
    end
    if count > 0
        buffer.flip();
        digest.update(buffer);
        buffer.clear();
    end
end
bytes = typecast(digest.digest(), 'uint8');
value = upper(reshape(dec2hex(bytes, 2).', 1, []));
end


function cleanup_run(originalDirectory)
try
    diary off;
catch
end
try
    evalin('base', 'clearvars');
catch
end
try
    cd(originalDirectory);
catch
end
end
