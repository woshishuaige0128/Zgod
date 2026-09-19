function run_original_metric_attempts()
% 在空基础工作区逐个原样运行梁禹历史精度脚本，保存真实失败现场。

codeDir = fileparts(mfilename('fullpath'));
boardRoot = fileparts(codeDir);
inputDir = fullfile(boardRoot, 'input', 'historical_metrics');
manifestPath = fullfile(boardRoot, 'input', 'input_manifest.csv');
outputDir = fullfile(boardRoot, 'outputs');
logDir = fullfile(boardRoot, 'logs');
if ~exist(outputDir, 'dir'); mkdir(outputDir); end
if ~exist(logDir, 'dir'); mkdir(logDir); end

scriptNames = {'fguyou.m'; 'MAC.m'; 'MAC_full.m'; 'RMSE_full.m'; 'RMSE.m'};
manifest = readtable(manifestPath, 'TextType', 'string', 'VariableNamingRule', 'preserve');
status = strings(numel(scriptNames), 1);
errorIdentifier = strings(numel(scriptNames), 1);
errorMessage = strings(numel(scriptNames), 1);
scriptSha256 = strings(numel(scriptNames), 1);
capturedCharacters = zeros(numel(scriptNames), 1);

for i = 1:numel(scriptNames)
    scriptPath = fullfile(inputDir, scriptNames{i});
    assert(isfile(scriptPath), 'Board19:MissingScript', '缺少冻结脚本：%s', scriptPath);
    copiedPath = "historical_metrics/" + string(scriptNames{i});
    manifestRow = find(manifest.copied_relative_path == copiedPath, 1);
    assert(~isempty(manifestRow), 'Board19:MissingManifestRow', '冻结清单缺少：%s', copiedPath);
    assert(manifest.status(manifestRow) == "MATCH", 'Board19:ManifestMismatch', ...
        '冻结清单未通过：%s', copiedPath);
    scriptSha256(i) = manifest.sha256_copy(manifestRow);
    evalin('base', 'clearvars');
    command = sprintf("run('%s')", strrep(scriptPath, "'", "''"));
    captured = "";
    try
        captured = string(evalc("evalin('base', command);"));
        status(i) = "SUCCESS";
    catch ME
        status(i) = "FAIL";
        errorIdentifier(i) = string(ME.identifier);
        errorMessage(i) = string(ME.message);
        captured = captured + newline + string(getReport(ME, 'extended', 'hyperlinks', 'off'));
    end
    capturedCharacters(i) = strlength(captured);
    logPath = fullfile(logDir, sprintf('original_%s.log', erase(scriptNames{i}, '.m')));
    fid = fopen(logPath, 'w', 'n', 'UTF-8');
    cleaner = onCleanup(@() fclose(fid));
    fprintf(fid, '脚本：%s\nSHA-256：%s\n状态：%s\n错误标识：%s\n错误消息：%s\n\n%s\n', ...
        scriptPath, scriptSha256(i), status(i), errorIdentifier(i), errorMessage(i), captured);
    clear cleaner;
end
evalin('base', 'clearvars');

attempts = table(string(scriptNames), scriptSha256, status, errorIdentifier, errorMessage, ...
    capturedCharacters, 'VariableNames', {'script', 'sha256', 'status', 'error_identifier', ...
    'error_message', 'captured_characters'});
writetable(attempts, fullfile(outputDir, 'original_script_attempts.csv'), 'Encoding', 'UTF-8');

summary = struct();
summary.script_count = height(attempts);
summary.success_count = nnz(attempts.status == "SUCCESS");
summary.failure_count = nnz(attempts.status == "FAIL");
summary.empty_workspace_before_each = true;
summary.status = char(string(ternary(summary.failure_count == summary.script_count, ...
    'EXPECTED_FAILURES_RECORDED', 'UNEXPECTED_RESULT')));
fid = fopen(fullfile(outputDir, 'original_script_attempts_summary.json'), 'w', 'n', 'UTF-8');
cleaner = onCleanup(@() fclose(fid));
fprintf(fid, '%s\n', jsonencode(summary, PrettyPrint=true));
clear cleaner;

disp(attempts(:, {'script','status','error_identifier'}));
fprintf('原样尝试：%d个脚本，成功%d，失败%d，裁决=%s\n', ...
    summary.script_count, summary.success_count, summary.failure_count, summary.status);
end

function value = ternary(condition, trueValue, falseValue)
if condition
    value = trueValue;
else
    value = falseValue;
end
end
