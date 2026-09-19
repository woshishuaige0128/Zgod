function run_one_board21_energy_route(configPath)
%RUN_ONE_BOARD21_ENERGY_ROUTE 在干净基础工作区原样执行一条能量候选路线。
% 外层只捕获证据；本函数不改作者脚本、不注入科学变量、不修正公式。

configPath = require_absolute_existing_config(configPath);
[configBytes, cfg, configContract, trustedConfigHashPath] = ...
    capture_and_verify_config(configPath);

% 这一段是纯读预检：在它全部通过前，不使用 JSON 中的任何
% 路径写状态、切换目录或开启 diary。
validate_config_shape_and_paths(cfg, configPath, trustedConfigHashPath);
instrumentContracts = verify_instrument_contracts(cfg);
inputHashesBefore = verify_input_contracts(cfg);
workFilesBefore = assert_pristine_work(cfg);
assert_pristine_outputs(cfg);

originalDirectory = pwd;
cleanupObject = onCleanup(@() cleanup_run(originalDirectory));
status = initial_status(cfg, configPath);
status.config_contract = configContract;
status.instrument_contracts = instrumentContracts;
status.input_hashes_before = inputHashesBefore;
status.work_files_before = workFilesBefore;
status.stages(end + 1) = make_stage( ...
    'sealed_read_only_preflight', 'PASS', empty_variable_records());
write_json(cfg.status_json, status);

inventory = struct('after_clear', empty_variable_records(), ...
    'after_upstream', empty_variable_records(), ...
    'after_candidate_or_failure', empty_variable_records());
executionSucceeded = false;
authorCallFailed = false;
primaryErrorOrigin = 'INFRASTRUCTURE';
originalError = [];
currentStage = 'RUNTIME_PREPARATION';
currentFile = '';
try
    status.current_stage = currentStage;
    restoredefaultpath;
    rehash toolboxcache;
    cd(cfg.work_dir);
    addpath(cfg.work_dir, '-begin');
    status.environment = environment_record();
    diary(cfg.diary_file);
    fprintf('BOARD21_ROUTE_START route=%s replicate=%s\n', ...
        cfg.route_id, cfg.replicate);
    fprintf('CONFIG=%s\nWORK=%s\nUPSTREAM=%s\nCANDIDATE=%s\n', ...
        configPath, cfg.work_dir, cfg.upstream_file, cfg.candidate_mlx);

    evalin('base', 'clearvars');
    afterClear = snapshot_base_variables();
    assert(isempty(afterClear), 'Board21:DirtyBaseWorkspace', ...
        '清理后基础工作区仍有%d个变量。', numel(afterClear));
    inventory.after_clear = afterClear;
    status.which_contracts = verify_which_contracts(cfg);
    [repeatConfigBytes, repeatCfg, repeatConfigContract, ...
        repeatConfigHashPath] = capture_and_verify_config(configPath);
    assert(strcmpi(repeatConfigHashPath, trustedConfigHashPath) && ...
        isequal(repeatConfigBytes, configBytes) && ...
        isequaln(repeatCfg, cfg) && ...
        isequal(repeatConfigContract, configContract), ...
        'Board21:ConfigChangedBeforeAuthorCall', ...
        '配置原始字节或解析结构在作者脚本启动前发生变化。');
    validate_config_shape_and_paths( ...
        repeatCfg, configPath, repeatConfigHashPath);
    repeatInstrumentContracts = verify_instrument_contracts(repeatCfg);
    repeatInputHashes = verify_input_contracts(repeatCfg);
    repeatWorkFiles = assert_pristine_work(repeatCfg);
    assert(isequal(repeatInstrumentContracts, instrumentContracts) && ...
        isequal(repeatInputHashes, inputHashesBefore) && ...
        isequal(repeatWorkFiles, workFilesBefore), ...
        'Board21:PreflightChangedBeforeAuthorCall', ...
        '可信预检结果在作者脚本启动前发生变化，拒绝执行。');
    status.stages(end + 1) = make_stage( ...
        'clean_base_workspace', 'PASS', afterClear);
    status.stages(end + 1) = make_stage( ...
        'input_and_path_preflight', 'PASS', afterClear);
    write_json(cfg.status_json, status);

    currentStage = 'UPSTREAM_ORIGINAL';
    currentFile = char(cfg.upstream_file);
    status.current_stage = currentStage;
    status.current_file = currentFile;
    fprintf('BOARD21_STAGE_START stage=%s file=%s\n', currentStage, currentFile);
    try
        run_in_base(currentFile);
    catch authorError
        authorCallFailed = true;
        primaryErrorOrigin = 'AUTHOR_CALL';
        rethrow(authorError);
    end

    currentStage = 'UPSTREAM_EVIDENCE_CAPTURE';
    status.current_stage = currentStage;
    afterUpstream = snapshot_base_variables();
    inventory.after_upstream = afterUpstream;
    save_base_workspace(cfg.workspace_after_upstream);
    status.stages(end + 1) = make_stage( ...
        'upstream_original', 'PASS', afterUpstream);
    assert(isfile(cfg.workspace_after_upstream), ...
        'Board21:MissingUpstreamWorkspace', ...
        '上游执行后工作区快照未生成。');
    fprintf('BOARD21_STAGE_PASS stage=%s variables=%d\n', ...
        currentStage, numel(afterUpstream));
    write_json(cfg.status_json, status);

    currentStage = 'CANDIDATE_ORIGINAL_MLX';
    currentFile = char(cfg.candidate_mlx);
    status.current_stage = currentStage;
    status.current_file = currentFile;
    fprintf('BOARD21_STAGE_START stage=%s file=%s\n', currentStage, currentFile);
    try
        run_in_base(currentFile);
    catch authorError
        authorCallFailed = true;
        primaryErrorOrigin = 'AUTHOR_CALL';
        rethrow(authorError);
    end
    executionSucceeded = true;
catch caughtError
    originalError = caughtError;
    if ~authorCallFailed
        primaryErrorOrigin = 'INFRASTRUCTURE';
    end
end

afterFinal = empty_variable_records();
try
    afterFinal = snapshot_base_variables();
    inventory.after_candidate_or_failure = afterFinal;
catch finalSnapshotError
    status.capture_errors{end + 1} = sprintf( ...
        'final_variable_snapshot:%s:%s', ...
        finalSnapshotError.identifier, finalSnapshotError.message);
end
try
    write_json(cfg.variable_inventory_json, inventory);
catch inventoryError
    status.capture_errors{end + 1} = sprintf( ...
        'variable_inventory_write:%s:%s', ...
        inventoryError.identifier, inventoryError.message);
end
[status.input_hashes_after, postHashError] = safe_verify_input_contracts(cfg);
if ~isempty(postHashError)
    status.capture_errors{end + 1} = postHashError;
end
[status.work_files_after, snapshotError] = safe_assert_pristine_work(cfg);
if ~isempty(snapshotError)
    status.capture_errors{end + 1} = snapshotError;
end
try
    status.scientific = inspect_scientific_workspace(cfg);
catch scientificInspectionError
    status.capture_errors{end + 1} = sprintf( ...
        'scientific_inspection:%s:%s', ...
        scientificInspectionError.identifier, scientificInspectionError.message);
    status.scientific = empty_scientific_record();
end
status.available_scientific_variables = status.scientific.available_variables;

if executionSucceeded
    status.stages(end + 1) = make_stage( ...
        'candidate_original_mlx', 'PASS', afterFinal);
    try
        save_base_workspace(cfg.workspace_success);
    catch workspaceSaveError
        status.capture_errors{end + 1} = sprintf( ...
            'workspace_success_save:%s:%s', ...
            workspaceSaveError.identifier, workspaceSaveError.message);
    end
    status.capture_errors = [status.capture_errors, ...
        save_scientific_arrays(cfg.scientific_mat, ...
        status.available_scientific_variables)];
    if ~isfile(cfg.workspace_success)
        status.capture_errors{end + 1} = 'missing_workspace_complete';
    end
    if ~isfile(cfg.scientific_mat)
        status.capture_errors{end + 1} = 'missing_scientific_mat';
    end
    if ~status.scientific.required_present
        status.capture_errors{end + 1} = 'required_scientific_variables_missing';
    end
    if ~status.scientific.lengths_match
        status.capture_errors{end + 1} = 'energy_vector_lengths_mismatch';
    end
    if ~status.scientific.all_finite
        status.capture_errors{end + 1} = 'scientific_values_nonfinite';
    end
    if ~status.scientific.required_variables_valid
        status.capture_errors{end + 1} = ...
            'required_scientific_variables_not_double_real_dense_nonglobal_finite';
    end
    if ~status.scientific.summary_scalars_valid
        status.capture_errors{end + 1} = ...
            'summary_metrics_not_real_double_finite_scalars';
    end
    if ~all([status.input_hashes_after.match])
        status.capture_errors{end + 1} = 'input_hash_changed_after_execution';
    end
    status.execution_status = 'EXECUTION_SUCCESS';
    status.finished_at = timestamp_now();
    status.current_stage = 'COMPLETE';
    status.current_file = '';
    if isempty(status.capture_errors)
        status.evidence_status = 'PASS';
        status.final_status = 'SUCCESS_AUTHOR_ROUTE_REPEAT_PENDING';
        status.process_exit_semantics = 'ZERO';
        write_json(cfg.status_json, status);
        fprintf(['BOARD21_ROUTE_SUCCESS route=%s replicate=%s ' ...
            'guyan=%.17g cb=%.17g\n'], cfg.route_id, cfg.replicate, ...
            status.scientific.total_increase_guyan, ...
            status.scientific.total_increase_cb);
        close all force;
        diary off;
        return;
    end
    status.evidence_status = 'FAIL';
    status.final_status = 'EXECUTION_SUCCESS_EVIDENCE_FAIL';
    status.process_exit_semantics = 'NONZERO_EVIDENCE_FAILURE';
    write_json(cfg.status_json, status);
    fprintf(2, 'BOARD21_EVIDENCE_FAIL route=%s errors=%s\n', ...
        cfg.route_id, strjoin(status.capture_errors, ' | '));
    close all force;
    diary off;
    error('Board21:EvidenceValidationFailed', ...
        '作者路线执行完成但证据门失败：%s', ...
        strjoin(status.capture_errors, ' | '));
else
    status.execution_status = 'EXECUTION_FAIL';
    status.failed_stage = currentStage;
    status.failed_file = currentFile;
    [status.error, exceptionCaptureErrors] = ...
        safe_exception_record(originalError);
    status.capture_errors = [status.capture_errors, exceptionCaptureErrors];
    status.capture_errors = [status.capture_errors, ...
        validate_error_record(status.error)];
    status.stages(end + 1) = make_stage( ...
        'failure_snapshot', 'FAIL', afterFinal);
    try
        save_base_workspace(cfg.workspace_failure);
        if ~isfile(cfg.workspace_failure)
            status.capture_errors{end + 1} = 'missing_workspace_failure';
        end
    catch saveError
        status.capture_errors{end + 1} = sprintf( ...
            'workspace_failure_save:%s:%s', saveError.identifier, saveError.message);
    end
    status.capture_errors = [status.capture_errors, ...
        save_scientific_arrays(cfg.scientific_mat, ...
        status.available_scientific_variables)];
    try
        reportText = status.error.report;
        if isempty(reportText)
            reportText = sprintf('%s: %s', ...
                status.error.identifier, status.error.message);
        end
        write_text(cfg.error_report, reportText);
    catch reportError
        status.capture_errors{end + 1} = sprintf( ...
            'error_report_write:%s:%s', reportError.identifier, reportError.message);
    end
    status.finished_at = timestamp_now();
    status.current_stage = 'FAILED_COMPLETE';
    status.current_file = '';
    status.process_exit_semantics = 'NONZERO_RETHROW';
    authorStages = {'UPSTREAM_ORIGINAL', 'CANDIDATE_ORIGINAL_MLX'};
    isAuthorFailure = strcmp(primaryErrorOrigin, 'AUTHOR_CALL') && ...
        authorCallFailed && any(strcmp(currentStage, authorStages));
    if isAuthorFailure
        status.error_origin = 'AUTHOR_CALL';
        if isempty(status.capture_errors)
            status.final_status = 'EXECUTION_FAIL_AUTHOR_ERROR_CAPTURED';
            status.evidence_status = 'PASS_FAILURE_EVIDENCE';
        else
            status.final_status = 'EXECUTION_FAIL_AUTHOR_ERROR_EVIDENCE_FAIL';
            status.evidence_status = 'FAIL_FAILURE_EVIDENCE';
        end
    else
        status.error_origin = 'INFRASTRUCTURE';
        status.final_status = 'EXECUTION_FAIL_INFRASTRUCTURE';
        status.evidence_status = 'FAIL_FAILURE_EVIDENCE';
    end
    try
        write_json(cfg.status_json, status);
    catch finalStatusWriteError
        fprintf(2, ['BOARD21_FINAL_STATUS_WRITE_FAIL identifier=%s ' ...
            'message=%s\n'], finalStatusWriteError.identifier, ...
            finalStatusWriteError.message);
    end
    safe_failure_epilogue(cfg, currentStage, originalError);
    rethrow(originalError);
end
end


function status = initial_status(cfg, configPath)
status = struct();
status.schema_version = 'BOARD21_STEP3_ROUTE_STATUS_V1';
status.route_id = char(cfg.route_id);
status.route_label_cn = char(cfg.route_label_cn);
status.replicate = char(cfg.replicate);
status.division_identity = char(cfg.division_identity);
status.parameter_family = char(cfg.parameter_family);
status.static_boundary = char(cfg.static_boundary);
status.config_path = char(configPath);
status.started_at = timestamp_now();
status.finished_at = '';
status.current_stage = 'CONFIG';
status.current_file = '';
status.failed_stage = '';
status.failed_file = '';
status.execution_status = 'NOT_STARTED';
status.evidence_status = 'NOT_EVALUATED';
status.final_status = 'RUNNING';
status.process_exit_semantics = 'RUNNING';
status.environment = struct();
status.config_contract = struct();
status.instrument_contracts = empty_hash_records();
status.input_hashes_before = empty_hash_records();
status.input_hashes_after = empty_hash_records();
status.which_contracts = repmat(struct('name', '', 'expected', '', ...
    'actual', '', 'match', false), 0, 1);
status.work_files_before = empty_file_records();
status.work_files_after = empty_file_records();
status.stages = empty_stage_records();
status.scientific = empty_scientific_record();
status.available_scientific_variables = {};
status.capture_errors = {};
status.error = empty_error_record();
status.error_origin = 'NONE';
end


function run_in_base(pathValue)
escaped = escape_matlab_text(pathValue);
evalin('base', sprintf("run('%s');", escaped));
end


function save_base_workspace(pathValue)
escaped = escape_matlab_text(pathValue);
evalin('base', sprintf("save('%s', '-v7.3');", escaped));
end


function errors = save_scientific_arrays(pathValue, available)
errors = {};
if isempty(available)
    return;
end
try
    variableArguments = cellfun(@(name) sprintf('''%s''', name), ...
        available, 'UniformOutput', false);
    command = sprintf('save(''%s'', %s, ''-v7.3'');', ...
        escape_matlab_text(pathValue), strjoin(variableArguments, ', '));
    evalin('base', command);
catch saveError
    errors{end + 1} = sprintf('scientific_save:%s:%s', ...
        saveError.identifier, saveError.message);
end
end


function safe_failure_epilogue(cfg, currentStage, originalError)
try
    fprintf(2, ['BOARD21_ROUTE_FAIL route=%s replicate=%s stage=%s ' ...
        'identifier=%s message=%s\n'], cfg.route_id, cfg.replicate, ...
        currentStage, originalError.identifier, originalError.message);
catch
end
try
    close all force;
catch
end
try
    diary off;
catch
end
end


function record = inspect_scientific_workspace(cfg)
record = empty_scientific_record();
requested = scientific_variable_names();
baseVariables = snapshot_base_variables();
baseNames = {baseVariables.name};
record.available_variables = requested(ismember(requested, baseNames));
required = {'E_total', 'E_total_guyan', 'E_total_cb', ...
    'energy_sum_orig', 'energy_sum_guyan', 'energy_sum_cb', ...
    'total_increase_guyan', 'total_increase_cb'};
record.missing_required = required(~ismember(required, baseNames));
record.required_present = isempty(record.missing_required);
if ~record.required_present
    return;
end
record.energy_lengths = [numel(evalin('base', 'E_total')), ...
    numel(evalin('base', 'E_total_guyan')), ...
    numel(evalin('base', 'E_total_cb'))];
record.expected_energy_lengths = double(cfg.expected_energy_lengths(:).');
record.lengths_match = isequal(record.energy_lengths, ...
    record.expected_energy_lengths);

record.required_variable_audit = empty_required_variable_audit();
record.required_variables_valid = true;
record.all_finite = true;
for k = 1:numel(required)
    metadataIndex = find(strcmp(baseNames, required{k}), 1, 'first');
    metadata = baseVariables(metadataIndex);
    value = evalin('base', required{k});
    isDouble = strcmp(metadata.class, 'double') && isa(value, 'double');
    isReal = false;
    isDense = false;
    isNonGlobal = ~metadata.is_global;
    isFinite = false;
    if isDouble
        isReal = ~metadata.is_complex && isreal(value);
        isDense = ~metadata.is_sparse && ~issparse(value);
        isFinite = all(isfinite(value(:)));
    end
    storageContractPass = isDouble && isReal && isDense && ...
        isNonGlobal && isFinite;
    record.required_variable_audit(end + 1) = struct( ...
        'name', required{k}, 'matlab_class', metadata.class, ...
        'is_double', isDouble, 'is_real', isReal, ...
        'is_dense', isDense, 'is_global', metadata.is_global, ...
        'is_finite', isFinite, 'numel', numel(value), ...
        'storage_contract_pass', storageContractPass);
    if ~storageContractPass
        record.required_variables_valid = false;
    end
    if ~isFinite
        record.all_finite = false;
    end
end

summaryNames = {'energy_sum_orig', 'energy_sum_guyan', 'energy_sum_cb', ...
    'total_increase_guyan', 'total_increase_cb'};
record.summary_scalars_valid = true;
for k = 1:numel(summaryNames)
    value = evalin('base', summaryNames{k});
    isValidSummary = isa(value, 'double') && isreal(value) && ...
        isscalar(value) && isfinite(value);
    if isValidSummary
        record.(summaryNames{k}) = value;
    else
        record.summary_scalars_valid = false;
    end
end
record.embedded_historical_percent = ...
    double(cfg.embedded_historical_percent(:).');
end


function names = scientific_variable_names()
names = {'E_total', 'E_total_guyan', 'E_total_cb', 'E', 'Gamma', ...
    'GammaSq', 'participation_ratio', 'energy_sum_orig', ...
    'energy_sum_guyan', 'energy_sum_cb', 'total_increase_guyan', ...
    'total_increase_cb', 'KRrt', 'MRrt', 'CRrt', 'KPrt', 'MPrt', ...
    'CPrt', 'T', 'KRren', 'MRren', 'CRren', 'T_cb', 'KR_cb', ...
    'MR_cb', 'CR_cb', 'TP', 'KPren', 'MPren', 'CPren', 'TP_cb', ...
    'KP_cb', 'MP_cb', 'CP_cb', 'index1', 'index2', 'index3', ...
    'index4', 'order', 'd', 'd2', 'r', 'r0'};
end


function record = empty_scientific_record()
record = struct('available_variables', {{}}, 'missing_required', {{}}, ...
    'required_present', false, 'energy_lengths', [], ...
    'expected_energy_lengths', [], 'lengths_match', false, ...
    'all_finite', false, 'required_variables_valid', false, ...
    'required_variable_audit', empty_required_variable_audit(), ...
    'summary_scalars_valid', false, ...
    'total_increase_guyan', NaN, ...
    'total_increase_cb', NaN, 'energy_sum_orig', NaN, ...
    'energy_sum_guyan', NaN, 'energy_sum_cb', NaN, ...
    'embedded_historical_percent', []);
end


function records = empty_required_variable_audit()
records = repmat(struct('name', '', 'matlab_class', '', ...
    'is_double', false, 'is_real', false, 'is_dense', false, ...
    'is_global', false, 'is_finite', false, 'numel', 0, ...
    'storage_contract_pass', false), 0, 1);
end


function value = require_text(rawValue, fieldName)
assert((ischar(rawValue) && isrow(rawValue)) || ...
    (isstring(rawValue) && isscalar(rawValue) && ~ismissing(rawValue)), ...
    'Board21:InvalidTextField', ...
    '配置字段必须是单个文本标量：%s', fieldName);
value = char(rawValue);
end


function value = require_nonempty_text(rawValue, fieldName)
value = require_text(rawValue, fieldName);
assert(~isempty(value), 'Board21:EmptyTextField', ...
    '配置文本字段不得为空：%s', fieldName);
end


function values = require_text_list(rawValue, fieldName)
if isstring(rawValue)
    assert(isvector(rawValue) && ~any(ismissing(rawValue)), ...
        'Board21:InvalidTextList', '配置字段必须是文本列表：%s', fieldName);
    values = cellstr(rawValue(:));
elseif iscell(rawValue)
    assert(isvector(rawValue), 'Board21:InvalidTextList', ...
        '配置字段必须是一维文本列表：%s', fieldName);
    values = cell(numel(rawValue), 1);
    for k = 1:numel(rawValue)
        values{k} = require_text(rawValue{k}, sprintf('%s[%d]', fieldName, k));
    end
else
    error('Board21:InvalidTextList', ...
        '配置字段必须是文本列表：%s', fieldName);
end
end


function pathValue = require_canonical_absolute_path(rawValue, fieldName)
pathValue = require_nonempty_text(rawValue, fieldName);
assert(java.io.File(pathValue).isAbsolute(), ...
    'Board21:PathNotAbsolute', '配置路径不是绝对路径：%s', fieldName);
canonical = canonical_path(pathValue);
assert(strcmpi(pathValue, canonical), 'Board21:PathNotCanonical', ...
    '配置路径不是规范绝对路径：%s', fieldName);
pathValue = canonical;
end


function assert_same_path(actual, expected, identifier, message, varargin)
actualCanonical = canonical_path(require_nonempty_text(actual, 'actual_path'));
expectedCanonical = canonical_path(require_nonempty_text(expected, 'expected_path'));
assert(strcmpi(actualCanonical, expectedCanonical), ...
    identifier, message, varargin{:});
end


function value = basename(pathValue)
[~, name, extension] = fileparts(char(pathValue));
value = [name, extension];
end


function match = is_sha256_text(value)
match = ischar(value) && isrow(value) && ...
    ~isempty(regexp(value, '^[0-9A-Fa-f]{64}$', 'once'));
end


function result = paths_disjoint(firstPath, secondPath)
firstCanonical = lower(canonical_path(firstPath));
secondCanonical = lower(canonical_path(secondPath));
firstPrefix = [firstCanonical, filesep];
secondPrefix = [secondCanonical, filesep];
result = ~strcmp(firstCanonical, secondCanonical) && ...
    ~startsWith(firstPrefix, secondPrefix) && ...
    ~startsWith(secondPrefix, firstPrefix);
end


function configPath = require_absolute_existing_config(configPath)
assert((ischar(configPath) && isrow(configPath)) || ...
    (isstring(configPath) && isscalar(configPath)), ...
    'Board21:InvalidConfigPathType', ...
    '配置路径必须是单个文本标量。');
configPath = char(configPath);
assert(~isempty(configPath), 'Board21:EmptyConfigPath', ...
    '配置路径不得为空。');
assert(java.io.File(configPath).isAbsolute(), ...
    'Board21:ConfigPathNotAbsolute', '配置路径必须是绝对路径。');
canonical = canonical_path(configPath);
assert(strcmpi(configPath, canonical), ...
    'Board21:ConfigPathNotCanonical', ...
    '配置路径必须是无别名、无.. 的规范绝对路径。');
assert(isfile(canonical), 'Board21:MissingConfig', ...
    '运行配置不存在：%s', canonical);
[~, name, extension] = fileparts(canonical);
assert(strcmp([name, extension], 'run_config.json'), ...
    'Board21:UnexpectedConfigName', ...
    '配置文件必须命名为run_config.json。');
configPath = canonical;
end


function [configBytes, cfg, record, trustedHashPath] = ...
        capture_and_verify_config(configPath)
metadataDirectory = fileparts(configPath);
trustedHashPath = fullfile(metadataDirectory, 'run_config.sha256');
trustedHashPath = canonical_path(trustedHashPath);
assert(isfile(trustedHashPath), 'Board21:MissingConfigHash', ...
    '缺少配置同级封签：%s', trustedHashPath);
configBytes = read_file_bytes(configPath);
expectedRaw = strtrim(fileread(trustedHashPath));
assert(is_sha256_text(expectedRaw), 'Board21:InvalidConfigHashText', ...
    '配置封签必须是单个64位SHA-256十六进制串。');
expected = upper(expectedRaw);
actual = sha256_bytes(configBytes);
record = struct('hash_file', trustedHashPath, ...
    'expected_sha256', expected, 'actual_sha256', actual, ...
    'match', strcmp(expected, actual));
assert(record.match, 'Board21:ConfigHashMismatch', ...
    '运行配置与同级封签不一致。');
try
    configText = native2unicode(configBytes(:).', 'UTF-8');
    cfg = jsondecode(configText);
catch decodeError
    error('Board21:ConfigDecodeFailed', ...
        '已封签配置字节无法按UTF-8 JSON解析：%s', decodeError.message);
end
end


function validate_config_shape_and_paths(cfg, configPath, trustedHashPath)
assert(isstruct(cfg) && isscalar(cfg), ...
    'Board21:InvalidConfigRoot', '配置根节点必须是单个JSON对象。');
requiredFields = {'schema_version', 'created_at', 'route_id', ...
    'route_label_cn', 'replicate', 'division_identity', ...
    'parameter_family', 'static_boundary', 'expected_energy_lengths', ...
    'embedded_historical_percent', 'execution_status', ...
    'matlab_executable', 'work_dir', 'output_dir', 'log_dir', ...
    'upstream_file', 'candidate_mlx', 'input_contracts', ...
    'instrument_sha256', 'instrument_contracts', ...
    'allowed_work_files', 'status_json', 'config_hash_file', ...
    'variable_inventory_json', 'workspace_after_upstream', ...
    'workspace_success', 'workspace_failure', 'scientific_mat', ...
    'diary_file', 'error_report', 'matlab_command_txt', 'shell_log', ...
    'matlab_stdout_log', 'matlab_stderr_log', 'process_exit_json'};
for k = 1:numel(requiredFields)
    assert(isfield(cfg, requiredFields{k}), ...
        'Board21:MissingConfigField', ...
        '配置缺少必需字段：%s', requiredFields{k});
end

assert(strcmp(require_text(cfg.schema_version, 'schema_version'), ...
    'BOARD21_STEP3_ROUTE_CONFIG_V1'), ...
    'Board21:ConfigSchemaMismatch', '步骤3配置版本不匹配。');
require_nonempty_text(cfg.created_at, 'created_at');
require_nonempty_text(cfg.route_id, 'route_id');
require_nonempty_text(cfg.route_label_cn, 'route_label_cn');
replicate = require_text(cfg.replicate, 'replicate');
assert(any(strcmp(replicate, {'rep01', 'rep02'})), ...
    'Board21:InvalidReplicate', '重复标识必须是rep01或rep02。');
require_nonempty_text(cfg.division_identity, 'division_identity');
require_nonempty_text(cfg.parameter_family, 'parameter_family');
require_nonempty_text(cfg.static_boundary, 'static_boundary');
assert(strcmp(require_text(cfg.execution_status, 'execution_status'), ...
    'STAGED_NOT_RUN'), 'Board21:ConfigAlreadyExecuted', ...
    '配置的execution_status必须是STAGED_NOT_RUN。');

assert(isnumeric(cfg.expected_energy_lengths) && ...
    isvector(cfg.expected_energy_lengths), ...
    'Board21:InvalidExpectedLengthsType', ...
    'expected_energy_lengths必须是数值向量。');
expectedLengths = double(cfg.expected_energy_lengths(:).');
assert(numel(expectedLengths) == 3 && all(isfinite(expectedLengths)) && ...
    all(expectedLengths > 0) && all(expectedLengths == fix(expectedLengths)), ...
    'Board21:InvalidExpectedLengths', ...
    'expected_energy_lengths必须是3个正整数。');
assert(isnumeric(cfg.embedded_historical_percent) && ...
    isvector(cfg.embedded_historical_percent), ...
    'Board21:InvalidHistoricalPercentType', ...
    'embedded_historical_percent必须是数值向量。');
historicalPercent = double(cfg.embedded_historical_percent(:).');
assert(numel(historicalPercent) == 2 && all(isfinite(historicalPercent)), ...
    'Board21:InvalidHistoricalPercent', ...
    'embedded_historical_percent必须是2个有限数。');

pathFields = {'matlab_executable', 'work_dir', 'output_dir', 'log_dir', ...
    'upstream_file', 'candidate_mlx', 'status_json', ...
    'config_hash_file', 'variable_inventory_json', ...
    'workspace_after_upstream', 'workspace_success', ...
    'workspace_failure', 'scientific_mat', 'diary_file', ...
    'error_report', 'matlab_command_txt', 'shell_log', ...
    'matlab_stdout_log', 'matlab_stderr_log', 'process_exit_json'};
for k = 1:numel(pathFields)
    require_canonical_absolute_path(cfg.(pathFields{k}), pathFields{k});
end

matlabExecutable = char(cfg.matlab_executable);
assert(isfile(matlabExecutable), 'Board21:MissingMatlabExecutable', ...
    'MATLAB可执行文件不存在：%s', matlabExecutable);
assert(strcmpi(canonical_path(matlabExecutable), ...
    canonical_path('D:\Downlad\Matlab\bin\matlab.exe')), ...
    'Board21:UnexpectedMatlabExecutable', ...
    'MATLAB可执行文件不是锁定路径。');

workDirectory = char(cfg.work_dir);
outputDirectory = char(cfg.output_dir);
logDirectory = char(cfg.log_dir);
routeIdentifier = char(cfg.route_id);
assert(isfolder(workDirectory), 'Board21:MissingWorkDirectory', ...
    '工作目录不存在：%s', workDirectory);
assert(isfolder(outputDirectory), 'Board21:MissingOutputDirectory', ...
    '输出目录不存在：%s', outputDirectory);
assert(isfolder(logDirectory), 'Board21:MissingLogDirectory', ...
    '日志目录不存在：%s', logDirectory);

runnerDirectory = canonical_path(fileparts(mfilename('fullpath')));
assert(strcmp(basename(runnerDirectory), 'code'), ...
    'Board21:RunnerAnchorMismatch', ...
    '运行器未从板块21的code目录加载。');
boardDirectory = canonical_path(fileparts(runnerDirectory));
expectedOutputDirectory = fullfile(boardDirectory, 'outputs', ...
    'step3_runs', routeIdentifier, replicate);
expectedWorkDirectory = fullfile(boardDirectory, 'tmp', ...
    'step3_runs', routeIdentifier, replicate, 'work');
expectedLogDirectory = fullfile(boardDirectory, 'logs', ...
    'step3_runs', routeIdentifier, replicate);
assert_same_path(outputDirectory, expectedOutputDirectory, ...
    'Board21:OutputRootAnchorMismatch', ...
    '输出目录未锚定到运行器所在板块21/outputs/step3_runs。');
assert_same_path(workDirectory, expectedWorkDirectory, ...
    'Board21:WorkRootAnchorMismatch', ...
    '工作目录未锚定到运行器所在板块21/tmp/step3_runs。');
assert_same_path(logDirectory, expectedLogDirectory, ...
    'Board21:LogRootAnchorMismatch', ...
    '日志目录未锚定到运行器所在板块21/logs/step3_runs。');
assert(paths_disjoint(workDirectory, outputDirectory) && ...
    paths_disjoint(workDirectory, logDirectory) && ...
    paths_disjoint(outputDirectory, logDirectory), ...
    'Board21:OverlappingRunDirectories', ...
    '工作、输出和日志目录必须彼此隔离。');

[outputRouteDirectory, outputReplicate] = fileparts(outputDirectory);
[~, outputRoute] = fileparts(outputRouteDirectory);
[logRouteDirectory, logReplicate] = fileparts(logDirectory);
[~, logRoute] = fileparts(logRouteDirectory);
[workReplicateDirectory, workLeaf] = fileparts(workDirectory);
[workRouteDirectory, workReplicate] = fileparts(workReplicateDirectory);
[~, workRoute] = fileparts(workRouteDirectory);
assert(strcmp(outputReplicate, replicate) && strcmp(outputRoute, routeIdentifier) && ...
    strcmp(logReplicate, replicate) && strcmp(logRoute, routeIdentifier) && ...
    strcmp(workLeaf, 'work') && strcmp(workReplicate, replicate) && ...
    strcmp(workRoute, routeIdentifier), ...
    'Board21:RunDirectoryIdentityMismatch', ...
    '工作、输出、日志目录与route_id/replicate身份不一致。');

metadataDirectory = fullfile(outputDirectory, 'metadata');
workspaceDirectory = fullfile(outputDirectory, 'workspace');
scientificDirectory = fullfile(outputDirectory, 'scientific');
assert(isfolder(metadataDirectory) && isfolder(workspaceDirectory) && ...
    isfolder(scientificDirectory), 'Board21:MissingOutputSubdirectory', ...
    '输出目录必须包含metadata、workspace和scientific子目录。');
assert_same_path(configPath, fullfile(metadataDirectory, 'run_config.json'), ...
    'Board21:ConfigTopologyMismatch', '配置文件目录拓扑不匹配。');
assert_same_path(cfg.config_hash_file, trustedHashPath, ...
    'Board21:ConfigHashPathMismatch', '配置内的封签路径与同级封签不一致。');
assert_same_path(cfg.status_json, fullfile(metadataDirectory, 'run_status.json'), ...
    'Board21:StatusPathMismatch', '状态JSON路径不符合固定拓扑。');
assert_same_path(cfg.variable_inventory_json, ...
    fullfile(metadataDirectory, 'variable_inventory.json'), ...
    'Board21:InventoryPathMismatch', '变量清单路径不符合固定拓扑。');
assert_same_path(cfg.process_exit_json, ...
    fullfile(metadataDirectory, 'process_exit.json'), ...
    'Board21:ProcessExitPathMismatch', '进程退出记录路径不符合固定拑扑。');
assert_same_path(cfg.workspace_after_upstream, ...
    fullfile(workspaceDirectory, 'workspace_after_upstream.mat'), ...
    'Board21:UpstreamWorkspacePathMismatch', '上游工作区快照路径不匹配。');
assert_same_path(cfg.workspace_success, ...
    fullfile(workspaceDirectory, 'workspace_complete.mat'), ...
    'Board21:SuccessWorkspacePathMismatch', '成功工作区快照路径不匹配。');
assert_same_path(cfg.workspace_failure, ...
    fullfile(workspaceDirectory, 'workspace_failure.mat'), ...
    'Board21:FailureWorkspacePathMismatch', '失败工作区快照路径不匹配。');
assert_same_path(cfg.scientific_mat, ...
    fullfile(scientificDirectory, 'historical_energy_outputs.mat'), ...
    'Board21:ScientificPathMismatch', '科学数组MAT路径不匹配。');

logNames = {'diary_file', 'error_report', 'matlab_command_txt', ...
    'shell_log', 'matlab_stdout_log', 'matlab_stderr_log'};
expectedLogFiles = {'matlab_diary.log', 'error_report.txt', ...
    'matlab_command.txt', 'shell_stdout_stderr.log', ...
    'matlab_stdout.log', 'matlab_stderr.log'};
for k = 1:numel(logNames)
    assert_same_path(cfg.(logNames{k}), ...
        fullfile(logDirectory, expectedLogFiles{k}), ...
        'Board21:LogPathMismatch', ...
        '日志路径不符合固定拓扑：%s', logNames{k});
end

allowed = require_text_list(cfg.allowed_work_files, 'allowed_work_files');
assert(numel(allowed) == 2 && numel(unique(allowed)) == 2, ...
    'Board21:InvalidWorkWhitelist', ...
    '工作目录白名单必须恰好包含2个不同文件名。');
for k = 1:numel(allowed)
    assert(strcmp(allowed{k}, basename(allowed{k})), ...
        'Board21:InvalidWhitelistedName', ...
        '工作目录白名单不得包含路径：%s', allowed{k});
end
assert(isfile(cfg.upstream_file), 'Board21:MissingUpstream', ...
    '上游脚本不存在：%s', cfg.upstream_file);
assert(isfile(cfg.candidate_mlx), 'Board21:MissingCandidate', ...
    '能量MLX不存在：%s', cfg.candidate_mlx);
assert_same_path(fileparts(char(cfg.upstream_file)), workDirectory, ...
    'Board21:UpstreamOutsideWork', '上游脚本不在锁定工作目录根层。');
assert_same_path(fileparts(char(cfg.candidate_mlx)), workDirectory, ...
    'Board21:CandidateOutsideWork', '能量MLX不在锁定工作目录根层。');
assert(isequal(allowed(:), ...
    {basename(cfg.upstream_file); basename(cfg.candidate_mlx)}), ...
    'Board21:WorkWhitelistOrderMismatch', ...
    '工作目录白名单必须按上游、候选MLX顺序与路径一致。');

contracts = cfg.input_contracts;
assert(isstruct(contracts) && numel(contracts) == 2, ...
    'Board21:InvalidInputContractCount', '输入合同必须恰好有2项。');
expectedKinds = {'upstream', 'candidate'};
expectedPaths = {char(cfg.upstream_file), char(cfg.candidate_mlx)};
for k = 1:2
    requiredContractFields = {'kind', 'order', 'name', ...
        'author_original_path', 'frozen_path', 'staged_path', ...
        'expected_sha256', 'copied_sha256', 'size_bytes'};
    for j = 1:numel(requiredContractFields)
        assert(isfield(contracts(k), requiredContractFields{j}), ...
            'Board21:MissingInputContractField', ...
            '输入合同缺少字段：%s', requiredContractFields{j});
    end
    assert(strcmp(require_text(contracts(k).kind, 'input.kind'), ...
        expectedKinds{k}), 'Board21:InputContractKindMismatch', ...
        '输入合同kind或顺序不匹配。');
    assert(isnumeric(contracts(k).order) && isscalar(contracts(k).order) && ...
        isfinite(contracts(k).order) && contracts(k).order == k, ...
        'Board21:InputContractOrderMismatch', ...
        '输入合同order必须与锁定顺序一致。');
    assert(strcmp(require_text(contracts(k).name, 'input.name'), ...
        basename(expectedPaths{k})), 'Board21:InputContractNameMismatch', ...
        '输入合同文件名与工作副本不一致。');
    assert_same_path(contracts(k).staged_path, expectedPaths{k}, ...
        'Board21:InputStagedPathMismatch', ...
        '输入合同的staged_path与工作副本不一致。');
    require_canonical_absolute_path( ...
        contracts(k).author_original_path, 'input.author_original_path');
    require_canonical_absolute_path( ...
        contracts(k).frozen_path, 'input.frozen_path');
    expectedHash = require_text(contracts(k).expected_sha256, ...
        'input.expected_sha256');
    copiedHash = require_text(contracts(k).copied_sha256, ...
        'input.copied_sha256');
    assert(is_sha256_text(expectedHash) && strcmp(expectedHash, upper(expectedHash)), ...
        'Board21:InvalidInputExpectedHash', ...
        '输入合同expected_sha256必须是大写64位封签。');
    assert(strcmp(copiedHash, expectedHash), ...
        'Board21:InputCopiedHashMismatch', ...
        '输入合同copied_sha256与expected_sha256不一致。');
    assert(isnumeric(contracts(k).size_bytes) && ...
        isscalar(contracts(k).size_bytes) && ...
        isfinite(contracts(k).size_bytes) && ...
        contracts(k).size_bytes >= 0 && ...
        contracts(k).size_bytes == fix(contracts(k).size_bytes), ...
        'Board21:InvalidInputSize', '输入合同size_bytes必须是非负整数。');
end

assert(isstruct(cfg.instrument_sha256) && isscalar(cfg.instrument_sha256), ...
    'Board21:InvalidInstrumentHashMap', ...
    'instrument_sha256必须是单个JSON对象。');
expectedInstrumentNames = expected_instrument_names();
assert(isstruct(cfg.instrument_contracts) && ...
    numel(cfg.instrument_contracts) == numel(expectedInstrumentNames), ...
    'Board21:InvalidInstrumentContractCount', ...
    '运行工具合同必须恰好有5项。');
expectedHashFields = cell(size(expectedInstrumentNames));
for k = 1:numel(expectedInstrumentNames)
    % jsondecode 按 matlab.lang.makeValidName 转换带点的JSON键。
    expectedHashFields{k} = ...
        matlab.lang.makeValidName(expectedInstrumentNames{k});
end
assert(numel(unique(expectedHashFields)) == numel(expectedHashFields), ...
    'Board21:InstrumentHashKeyCollision', ...
    '工具名经makeValidName转换后发生键冲突。');
actualHashFields = fieldnames(cfg.instrument_sha256);
assert(isequal(sort(actualHashFields), sort(expectedHashFields(:))), ...
    'Board21:InvalidInstrumentHashMapKeys', ...
    'instrument_sha256的键集与5个固定工具名不一致。');
assert(numel(actualHashFields) == 5, 'Board21:InvalidInstrumentHashMapCount', ...
    'instrument_sha256必须恰好包含5个工具封签。');
for k = 1:numel(expectedInstrumentNames)
    contractName = require_text(cfg.instrument_contracts(k).name, ...
        'instrument.name');
    assert(strcmp(contractName, expectedInstrumentNames{k}), ...
        'Board21:InstrumentOrderMismatch', ...
        '运行工具合同的名称或顺序不匹配。');
    contractHash = require_text( ...
        cfg.instrument_contracts(k).expected_sha256, ...
        'instrument.expected_sha256');
    mapHash = require_text( ...
        cfg.instrument_sha256.(expectedHashFields{k}), ...
        ['instrument_sha256.', expectedHashFields{k}]);
    assert(is_sha256_text(mapHash) && strcmp(mapHash, upper(mapHash)), ...
        'Board21:InvalidInstrumentHashMapValue', ...
        'instrument_sha256中的每个值必须是大写64位封签。');
    assert(strcmp(mapHash, contractHash), ...
        'Board21:InstrumentHashNameBindingMismatch', ...
        'instrument_sha256与instrument_contracts的同名工具封签不一致：%s', ...
        expectedInstrumentNames{k});
end
end


function names = expected_instrument_names()
names = {'stage_board21_step3_runs.py', ...
    'run_one_board21_energy_route.m', ...
    'execute_board21_step3_route.py', ...
    'run_board21_step3_all.py', ...
    'validate_board21_step3_runs.py'};
end


function records = verify_instrument_contracts(cfg)
records = empty_hash_records();
contracts = cfg.instrument_contracts;
expectedNames = expected_instrument_names();
assert(isstruct(contracts) && numel(contracts) == numel(expectedNames), ...
    'Board21:InvalidInstrumentContractCount', ...
    '运行工具合同必须恰好有5项。');
runnerDirectory = fileparts(mfilename('fullpath'));
for k = 1:numel(contracts)
    assert(isfield(contracts(k), 'name') && isfield(contracts(k), 'path') && ...
        isfield(contracts(k), 'expected_sha256'), ...
        'Board21:MissingInstrumentContractField', ...
        '运行工具合同缺少name/path/expected_sha256。');
    name = require_text(contracts(k).name, 'instrument.name');
    assert(strcmp(name, expectedNames{k}), ...
        'Board21:InstrumentOrderMismatch', ...
        '运行工具合同的名称或顺序不匹配。');
    pathValue = require_canonical_absolute_path( ...
        contracts(k).path, 'instrument.path');
    assert_same_path(pathValue, fullfile(runnerDirectory, name), ...
        'Board21:InstrumentPathMismatch', ...
        '运行工具未指向运行器同目录的锁定文件。');
    expected = require_text(contracts(k).expected_sha256, ...
        'instrument.expected_sha256');
    assert(is_sha256_text(expected) && strcmp(expected, upper(expected)), ...
        'Board21:InvalidInstrumentHash', ...
        '运行工具封签必须是大写64位SHA-256。');
    assert(isfile(pathValue), 'Board21:MissingInstrument', ...
        '运行工具不存在：%s', pathValue);
    actual = sha256_file(pathValue);
    match = strcmp(expected, actual);
    records(end + 1) = struct('layer', 'instrument', ...
        'kind', name, 'path', pathValue, ...
        'expected_sha256', expected, 'actual_sha256', actual, ...
        'match', match); %#ok<AGROW>
    assert(match, 'Board21:InstrumentHashMismatch', ...
        '运行工具与暂存时哈希不一致：%s', pathValue);
end
end


function records = verify_input_contracts(cfg)
records = empty_hash_records();
contracts = cfg.input_contracts;
layers = {'author_original_path', 'frozen_path', 'staged_path'};
layerNames = {'author_original', 'step1_frozen', 'run_copy'};
for k = 1:numel(contracts)
    expected = require_text(contracts(k).expected_sha256, ...
        'input.expected_sha256');
    assert(is_sha256_text(expected) && strcmp(expected, upper(expected)), ...
        'Board21:InvalidInputHash', ...
        '输入封签必须是大写64位SHA-256。');
    for j = 1:numel(layers)
        pathValue = require_canonical_absolute_path( ...
            contracts(k).(layers{j}), ['input.', layers{j}]);
        assert(isfile(pathValue), 'Board21:MissingContractFile', ...
            '三层输入合同文件缺失：%s', pathValue);
        actual = sha256_file(pathValue);
        match = strcmp(expected, actual);
        records(end + 1) = struct('layer', layerNames{j}, ...
            'kind', char(contracts(k).kind), 'path', pathValue, ...
            'expected_sha256', expected, 'actual_sha256', actual, ...
            'match', match); %#ok<AGROW>
        assert(match, 'Board21:InputHashMismatch', ...
            '三层输入哈希不一致：%s', pathValue);
    end
    stagedInfo = dir(char(contracts(k).staged_path));
    assert(isscalar(stagedInfo) && ...
        stagedInfo.bytes == double(contracts(k).size_bytes), ...
        'Board21:InputSizeMismatch', ...
        '工作副本字节数与输入合同不一致。');
end
end


function [records, errorMessage] = safe_verify_input_contracts(cfg)
errorMessage = '';
try
    records = verify_input_contracts(cfg);
catch errorValue
    errorMessage = sprintf('post_input_hash:%s:%s', ...
        errorValue.identifier, errorValue.message);
    records = empty_hash_records();
end
end


function records = verify_which_contracts(cfg)
records = repmat(struct('name', '', 'expected', '', 'actual', '', ...
    'match', false), 0, 1);
paths = {char(cfg.upstream_file), char(cfg.candidate_mlx)};
for k = 1:numel(paths)
    [~, base, extension] = fileparts(paths{k});
    name = [base, extension];
    actual = which(name);
    expected = canonical_path(paths{k});
    actualCanonical = canonical_path(actual);
    match = strcmpi(expected, actualCanonical);
    records(end + 1) = struct('name', name, 'expected', expected, ...
        'actual', actualCanonical, 'match', match); %#ok<AGROW>
    assert(match, 'Board21:WhichPathMismatch', ...
        'which解析未指向本轮工作副本：%s actual=%s', name, actual);
end
end


function records = assert_pristine_work(cfg)
expected = sort(require_text_list(cfg.allowed_work_files, ...
    'allowed_work_files'));
listing = dir(cfg.work_dir);
listing = listing(~ismember({listing.name}, {'.', '..'}));
assert(~any([listing.isdir]), 'Board21:WorkDirectoryContainsSubdirectory', ...
    '工作目录白名单不允许任何子目录。');
topLevelNames = sort({listing.name}.');
assert(isequal(expected(:), topLevelNames(:)), ...
    'Board21:DirtyWorkDirectoryTopLevel', ...
    '工作目录顶层必须恰好包含白名单中的2个文件。');
records = directory_snapshot(cfg.work_dir);
actual = sort({records.name}.');
assert(isequal(expected(:), actual(:)), 'Board21:DirtyWorkDirectory', ...
    '工作目录必须恰好包含一个上游和一个汇总MLX。expected=%s actual=%s', ...
    strjoin(expected, '|'), strjoin(actual, '|'));
end


function assert_pristine_outputs(cfg)
paths = {cfg.status_json, cfg.workspace_after_upstream, cfg.workspace_success, ...
    cfg.workspace_failure, cfg.scientific_mat, cfg.diary_file, ...
    cfg.error_report, cfg.variable_inventory_json};
for k = 1:numel(paths)
    assert(~isfile(paths{k}) && ~isfolder(paths{k}), ...
        'Board21:ExistingRunnerOutput', ...
        '运行器输出已存在，拒绝复用：%s', paths{k});
end
end


function records = snapshot_base_variables()
raw = evalin('base', 'whos');
records = empty_variable_records();
for k = 1:numel(raw)
    sparseValue = isfield(raw, 'sparse') && logical(raw(k).sparse);
    complexValue = isfield(raw, 'complex') && logical(raw(k).complex);
    globalValue = isfield(raw, 'global') && logical(raw(k).global);
    records(end + 1) = struct('name', raw(k).name, ...
        'class', raw(k).class, 'size', raw(k).size, 'bytes', raw(k).bytes, ...
        'is_sparse', sparseValue, 'is_complex', complexValue, ...
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
    absolute = fullfile(listing(k).folder, listing(k).name);
    records(end + 1) = struct('name', listing(k).name, ...
        'path', absolute, 'bytes', listing(k).bytes, ...
        'sha256', sha256_file(absolute)); %#ok<AGROW>
end
end


function [records, errorMessage] = safe_assert_pristine_work(cfg)
errorMessage = '';
try
    records = assert_pristine_work(cfg);
catch errorValue
    errorMessage = sprintf('work_whitelist:%s:%s', ...
        errorValue.identifier, errorValue.message);
    records = empty_file_records();
end
end


function stage = make_stage(name, stageStatus, variables)
stage = struct('name', name, 'status', stageStatus, ...
    'timestamp', timestamp_now(), 'variable_count', numel(variables), ...
    'variables', variables);
end


function [record, captureErrors] = safe_exception_record(exception)
record = empty_error_record();
captureErrors = {};
try
    record.identifier = char(exception.identifier);
catch captureError
    captureErrors{end + 1} = exception_capture_error( ...
        'exception_identifier', captureError);
    record.identifier = 'Board21:OriginalErrorIdentifierUnavailable';
end
try
    record.message = char(exception.message);
catch captureError
    captureErrors{end + 1} = exception_capture_error( ...
        'exception_message', captureError);
    record.message = '原始异常消息无法序列化';
end
try
    record.report = getReport(exception, 'extended', 'hyperlinks', 'off');
catch captureError
    captureErrors{end + 1} = exception_capture_error( ...
        'exception_report', captureError);
    record.report = '';
end
try
    originalStack = exception.stack;
    for k = 1:numel(originalStack)
        try
            stackFile = char(originalStack(k).file);
            stackName = char(originalStack(k).name);
            stackLine = double(originalStack(k).line);
            record.stack(end + 1) = struct('file', stackFile, ...
                'name', stackName, 'line', stackLine);
        catch captureError
            captureErrors{end + 1} = exception_capture_error( ...
                sprintf('exception_stack_item_%d', k), captureError); %#ok<AGROW>
        end
    end
catch captureError
    captureErrors{end + 1} = exception_capture_error( ...
        'exception_stack', captureError);
end
end


function value = exception_capture_error(stage, captureError)
try
    identifier = char(captureError.identifier);
catch
    identifier = 'UNKNOWN_CAPTURE_IDENTIFIER';
end
try
    message = char(captureError.message);
catch
    message = 'UNKNOWN_CAPTURE_MESSAGE';
end
value = sprintf('%s:%s:%s', stage, identifier, message);
end


function errors = validate_error_record(record)
errors = {};
if ~isstruct(record) || ~isscalar(record)
    errors{end + 1} = 'original_error_record_not_scalar_struct';
    return;
end
textFields = {'identifier', 'message', 'report'};
errorNames = {'original_error_identifier_missing', ...
    'original_error_message_missing', 'original_error_report_missing'};
for k = 1:numel(textFields)
    fieldName = textFields{k};
    if ~isfield(record, fieldName) || ...
            ~is_nonempty_text_scalar(record.(fieldName))
        errors{end + 1} = errorNames{k}; %#ok<AGROW>
    end
end

if ~isfield(record, 'stack') || ~isstruct(record.stack) || ...
        isempty(record.stack)
    errors{end + 1} = 'original_error_stack_missing_or_invalid';
    return;
end
for k = 1:numel(record.stack)
    frame = record.stack(k);
    if ~isfield(frame, 'file') || ~is_nonempty_text_scalar(frame.file)
        errors{end + 1} = sprintf( ...
            'original_error_stack_item_%d_file_invalid', k); %#ok<AGROW>
    end
    if ~isfield(frame, 'name') || ~is_nonempty_text_scalar(frame.name)
        errors{end + 1} = sprintf( ...
            'original_error_stack_item_%d_name_invalid', k); %#ok<AGROW>
    end
    lineValid = false;
    if isfield(frame, 'line')
        lineValue = frame.line;
        lineValid = isnumeric(lineValue) && ~islogical(lineValue) && ...
            isscalar(lineValue) && isfinite(lineValue) && ...
            lineValue == fix(lineValue) && lineValue > 0;
    end
    if ~lineValid
        errors{end + 1} = sprintf( ...
            'original_error_stack_item_%d_line_invalid', k); %#ok<AGROW>
    end
end
end


function valid = is_nonempty_text_scalar(value)
valid = ((ischar(value) && isrow(value)) || ...
    (isstring(value) && isscalar(value) && ~ismissing(value))) && ...
    ~isempty(strtrim(char(value)));
end


function record = empty_error_record()
record = struct('identifier', '', 'message', '', 'report', '', ...
    'stack', repmat(struct('file', '', 'name', '', 'line', 0), 0, 1));
end


function records = empty_variable_records()
records = repmat(struct('name', '', 'class', '', 'size', [], 'bytes', 0, ...
    'is_sparse', false, 'is_complex', false, 'is_global', false), 0, 1);
end


function records = empty_stage_records()
records = repmat(struct('name', '', 'status', '', 'timestamp', '', ...
    'variable_count', 0, 'variables', empty_variable_records()), 0, 1);
end


function records = empty_hash_records()
records = repmat(struct('layer', '', 'kind', '', 'path', '', ...
    'expected_sha256', '', 'actual_sha256', '', 'match', false), 0, 1);
end


function records = empty_file_records()
records = repmat(struct('name', '', 'path', '', 'bytes', 0, ...
    'sha256', ''), 0, 1);
end


function record = environment_record()
record = struct('matlab_version', version, ...
    'matlab_release', version('-release'), 'computer', computer, ...
    'matlab_root', matlabroot, 'pid', feature('getpid'), ...
    'pwd', pwd, 'path', path);
end


function bytes = read_file_bytes(pathValue)
fileId = fopen(pathValue, 'rb');
if fileId < 0
    error('Board21:BinaryOpenFailed', ...
        '无法以二进制方式读取文件：%s', pathValue);
end
cleanup = onCleanup(@() fclose(fileId));
bytes = fread(fileId, Inf, '*uint8');
end


function value = sha256_bytes(bytes)
assert(isa(bytes, 'uint8') && isvector(bytes), ...
    'Board21:InvalidHashBytes', 'SHA-256输入必须是uint8向量。');
digest = java.security.MessageDigest.getInstance('SHA-256');
if ~isempty(bytes)
    buffer = java.nio.ByteBuffer.wrap(typecast(bytes(:), 'int8'));
    digest.update(buffer);
end
digestBytes = typecast(digest.digest(), 'uint8');
value = upper(reshape(dec2hex(digestBytes, 2).', 1, []));
end


function value = sha256_file(pathValue)
digest = java.security.MessageDigest.getInstance('SHA-256');
stream = java.io.FileInputStream(java.io.File(char(pathValue)));
cleanup = onCleanup(@() stream.close());
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


function value = canonical_path(pathValue)
if isempty(pathValue)
    value = '';
else
    value = char(java.io.File(char(pathValue)).getCanonicalPath());
end
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
    error('Board21:JsonOpenFailed', '无法写入JSON：%s', pathValue);
end
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, '%s\n', text);
end


function write_text(pathValue, textValue)
fileId = fopen(pathValue, 'w', 'n', 'UTF-8');
if fileId < 0
    error('Board21:TextOpenFailed', '无法写入文本：%s', pathValue);
end
cleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, '%s\n', textValue);
end


function cleanup_run(originalDirectory)
try
    close all force;
catch
end
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
