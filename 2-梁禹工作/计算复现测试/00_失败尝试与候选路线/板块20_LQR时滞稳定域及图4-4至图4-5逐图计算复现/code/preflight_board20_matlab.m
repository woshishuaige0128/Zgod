% 板块20最小步骤2：MATLAB环境与真实外部依赖预检
% 只检查运行环境，不执行作者极点扫描。

scriptPath = mfilename('fullpath');
boardRoot = fileparts(fileparts(scriptPath));
outputRoot = fullfile(boardRoot, 'outputs');
if ~isfolder(outputRoot)
    mkdir(outputRoot);
end
outputPath = fullfile(outputRoot, 'step2_matlab_preflight.json');

result = struct();
result.schema = 'board20_matlab_preflight_v1';
result.created_at = char(datetime('now', 'TimeZone', 'local', ...
    'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));
result.matlab_version = version;
result.matlab_release = version('-release');
result.computer = computer;
result.matlab_root = matlabroot;
result.pid = feature('getpid');
result.starting_working_directory = pwd;

result.licenses = struct();
result.licenses.symbolic_toolbox = logical(license('test', 'Symbolic_Toolbox'));
result.licenses.control_toolbox = logical(license('test', 'Control_Toolbox'));

functionNames = {'syms', 'sym', 'solve', 'vpa', 'ss', 'c2d', 'dlqr', 'eigs'};
functionRecords = repmat(struct('name', '', 'resolved_path', '', ...
    'resolved_paths', {{}}, 'available', false), numel(functionNames), 1);
for k = 1:numel(functionNames)
    resolved = which(functionNames{k});
    resolvedAll = which(functionNames{k}, '-all');
    if ischar(resolvedAll)
        resolvedAll = {resolvedAll};
    end
    functionRecords(k).name = functionNames{k};
    functionRecords(k).resolved_path = resolved;
    functionRecords(k).resolved_paths = resolvedAll;
    functionRecords(k).available = ~isempty(resolved);
end
result.functions = functionRecords;

smoke = struct();
smoke.symbolic = struct('status', 'FAIL', 'roots', [], ...
    'error_identifier', '', 'error_message', '');
try
    syms x
    symbolicRoots = sort(double(vpa(solve(x^2 - 1 == 0, x))));
    smoke.symbolic.roots = symbolicRoots(:).';
    if numel(symbolicRoots) == 2 && max(abs(symbolicRoots(:) - [-1; 1])) < 1e-12
        smoke.symbolic.status = 'PASS';
    end
catch smokeError
    smoke.symbolic.error_identifier = smokeError.identifier;
    smoke.symbolic.error_message = smokeError.message;
end

smoke.control = struct('status', 'FAIL', 'discrete_A', [], ...
    'lqr_gain', [], 'closed_loop_poles', [], ...
    'error_identifier', '', 'error_message', '');
try
    smokeA = [0, 1; -2, -3];
    smokeB = [0; 1];
    smokeContinuous = ss(smokeA, smokeB, eye(2), zeros(2, 1));
    smokeDiscrete = c2d(smokeContinuous, 1e-3);
    [smokeGain, ~, smokePoles] = dlqr(smokeDiscrete.A, smokeDiscrete.B, ...
        eye(2), 1);
    smoke.control.discrete_A = smokeDiscrete.A;
    smoke.control.lqr_gain = smokeGain;
    smoke.control.closed_loop_poles = smokePoles;
    if all(isfinite(smokeDiscrete.A), 'all') && all(isfinite(smokeGain), 'all') ...
            && all(abs(smokePoles) < 1)
        smoke.control.status = 'PASS';
    end
catch smokeError
    smoke.control.error_identifier = smokeError.identifier;
    smoke.control.error_message = smokeError.message;
end
result.smoke = smoke;

helperPath = fullfile(boardRoot, 'input', 'historical_upstream', ...
    '新物理子结构方案', 'fcn_newmark_beta_const.m');
helperDirectory = fileparts(helperPath);
helperRecord = struct();
helperRecord.frozen_path = helperPath;
helperRecord.exists = isfile(helperPath);
helperRecord.filename_function_name = 'fcn_newmark_beta_const';
helperRecord.declared_function_name = '';
helperRecord.filename_matches_declaration = false;
helperRecord.which_before_addpath = which('fcn_newmark_beta_const');
helperRecord.which_after_addpath = '';
helperRecord.call_status = 'FAIL';
helperRecord.call_values = [];
helperRecord.call_expected = [4194304, 2048, 4096, 1, 1, 0, ...
    0.00048828125, 0.00048828125];
helperRecord.call_max_abs_error = [];
helperRecord.warning_identifier = '';
helperRecord.warning_message = '';
helperRecord.error_identifier = '';
helperRecord.error_message = '';
if helperRecord.exists
    helperText = fileread(helperPath);
    token = regexp(helperText, ...
        'function\s+\[[^\]]*\]\s*=\s*([A-Za-z]\w*)', 'tokens', 'once');
    if ~isempty(token)
        helperRecord.declared_function_name = token{1};
    end
    helperRecord.filename_matches_declaration = strcmp( ...
        helperRecord.filename_function_name, helperRecord.declared_function_name);
    addpath(helperDirectory, '-begin');
    pathCleanup = onCleanup(@() rmpath(helperDirectory));
    helperRecord.which_after_addpath = which('fcn_newmark_beta_const');
    try
        lastwarn('');
        [ha0, ha1, ha2, ha3, ha4, ha5, ha6, ha7] = ...
            fcn_newmark_beta_const(0.5, 0.25, 1/1024);
        [helperWarningMessage, helperWarningIdentifier] = lastwarn;
        helperRecord.call_values = [ha0, ha1, ha2, ha3, ha4, ha5, ha6, ha7];
        helperRecord.call_max_abs_error = max(abs( ...
            helperRecord.call_values - helperRecord.call_expected));
        helperRecord.warning_identifier = helperWarningIdentifier;
        helperRecord.warning_message = helperWarningMessage;
        if helperRecord.call_max_abs_error < 1e-12
            helperRecord.call_status = 'PASS';
        end
    catch helperError
        helperRecord.error_identifier = helperError.identifier;
        helperRecord.error_message = helperError.message;
    end
end
result.helper = helperRecord;

requiredFunctionsAvailable = all([functionRecords.available]);
result.status = 'PASS';
if ~result.licenses.symbolic_toolbox || ~result.licenses.control_toolbox || ...
        ~requiredFunctionsAvailable || ~helperRecord.exists || ...
        isempty(helperRecord.which_after_addpath) || ...
        ~strcmp(smoke.symbolic.status, 'PASS') || ...
        ~strcmp(smoke.control.status, 'PASS') || ...
        ~strcmp(helperRecord.call_status, 'PASS')
    result.status = 'FAIL';
end

jsonText = jsonencode(result, 'PrettyPrint', true);
fileId = fopen(outputPath, 'w', 'n', 'UTF-8');
if fileId < 0
    error('Board20:PreflightOutputOpenFailed', ...
        '无法写入预检JSON：%s', outputPath);
end
fileCleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, '%s\n', jsonText);

fprintf(['BOARD20_MATLAB_PREFLIGHT status=%s release=%s symbolic=%d control=%d ' ...
    'symbolic_smoke=%s control_smoke=%s helper_name_match=%d helper_call=%s\n'], ...
    result.status, result.matlab_release, result.licenses.symbolic_toolbox, ...
    result.licenses.control_toolbox, result.smoke.symbolic.status, ...
    result.smoke.control.status, result.helper.filename_matches_declaration, ...
    result.helper.call_status);
fprintf('OUTPUT=%s\n', outputPath);

if strcmp(result.status, 'FAIL')
    error('Board20:MatlabPreflightFailed', 'MATLAB预检未通过。');
end
