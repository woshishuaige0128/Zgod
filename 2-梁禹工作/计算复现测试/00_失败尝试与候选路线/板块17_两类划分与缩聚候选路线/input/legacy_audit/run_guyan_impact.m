%% Guyan 单侧历史路线与双侧合同投影路线的结论影响核查
% 运行边界：
% 1. 只读取本 test 目录 input_copies 下的冻结副本；不读取或修改项目源文件。
% 2. 只创建 outputs/、logs/ 内的文件和模型工作副本。
% 3. 只比较既有两类划分、El Centro 和 0.1--10 Hz chirp，不增加算例。
% 4. 先严格复现四个历史响应基线；任何门槛失败均立即报错并停止。

clearvars;
close all force;
clc;

codeDir = fileparts(mfilename('fullpath'));
testDir = fileparts(codeDir);
inputDir = fullfile(testDir, 'input_copies');
modelInputDir = fullfile(inputDir, 'model_and_parameters');
auxGroundDir = fullfile(inputDir, 'auxiliary_ground_motions');
historicalOutputDir = fullfile(inputDir, 'historical_outputs');
manifestPath = fullfile(testDir, 'source_manifest.csv');

outputDir = fullfile(testDir, 'outputs');
matrixDir = fullfile(outputDir, 'matrices');
modalDir = fullfile(outputDir, 'modal');
responseDir = fullfile(outputDir, 'responses');
historicalResponseDir = fullfile(responseDir, 'historical_single_sided');
projectedResponseDir = fullfile(responseDir, 'projected_congruence');
metricDir = fullfile(outputDir, 'metrics');
modelWorkDir = fullfile(outputDir, 'model_work');
logDir = fullfile(testDir, 'logs');

requiredDirs = {outputDir, matrixDir, modalDir, responseDir, ...
    historicalResponseDir, projectedResponseDir, metricDir, modelWorkDir, logDir};
for k = 1:numel(requiredDirs)
    if ~exist(requiredDirs{k}, 'dir')
        mkdir(requiredDirs{k});
    end
end

logTimestamp = char(datetime('now', 'Format', 'yyyyMMdd_HHmmss_SSS'));
logFile = fullfile(logDir, ['run_guyan_impact_matlab_' logTimestamp '.log']);
logSuffix = 1;
while isfile(logFile)
    logFile = fullfile(logDir, sprintf( ...
        'run_guyan_impact_matlab_%s_%02d.log', logTimestamp, logSuffix));
    logSuffix = logSuffix + 1;
end
diary(logFile);
diaryCleanup = onCleanup(@() diary('off')); %#ok<NASGU>

oldDir = pwd;
modelNames = {'division1_impact', 'division2_impact'};
environmentCleanup = onCleanup(@() cleanup_environment(modelNames, oldDir)); %#ok<NASGU>
cd(modelWorkDir);

fprintf('Guyan 双侧投影结论影响核查开始：%s\n', string(datetime('now')));
fprintf('MATLAB：%s\n', version);
fprintf('testDir：%s\n', testDir);

try
    %% 1. 冻结输入预检：只接受 source_manifest.csv 中已记录且哈希一致的复制件
    parameterScript = fullfile(modelInputDir, 'PDmonicanshu.m');
    eqFile = fullfile(modelInputDir, 'EQ.mat');
    division1SourceModel = fullfile(modelInputDir, 'lvxvjie_guyan_2.slx');
    division2SourceModel = fullfile(modelInputDir, 'lvxvjie_guyan.slx');
    baselineFiles = {
        fullfile(historicalOutputDir, '第一类划分_ElCentro地震响应.csv');
        fullfile(historicalOutputDir, '第一类划分_Chirp响应.csv');
        fullfile(historicalOutputDir, '第二类划分_ElCentro地震响应.csv');
        fullfile(historicalOutputDir, '第二类划分_Chirp响应.csv')};
    auxiliaryFiles = {
        fullfile(auxGroundDir, 'ElCentroAccelNoScaling.mat');
        fullfile(auxGroundDir, 'KobeAccelNoScaling.mat');
        fullfile(auxGroundDir, 'MorganAccelNoScaling.mat')};
    requiredInputs = [{parameterScript; eqFile; division1SourceModel; division2SourceModel}; ...
        baselineFiles; auxiliaryFiles];
    verify_frozen_inputs(manifestPath, requiredInputs);

    %% 2. 从冻结参数脚本和 EQ.mat 恢复与历史生成器相同的矩阵和激励
    run(parameterScript);
    assert(exist('MRrt', 'var') == 1 && exist('CRrt', 'var') == 1 && ...
        exist('KRrt', 'var') == 1, ...
        'PDmonicanshu.m 未生成 MRrt/CRrt/KRrt。');
    assert(isequal(size(MRrt), [15,15]) && isequal(size(CRrt), [15,15]) && ...
        isequal(size(KRrt), [15,15]), '完整模型矩阵必须均为 15x15。');
    assert(all(isfinite(MRrt), 'all') && all(isfinite(CRrt), 'all') && ...
        all(isfinite(KRrt), 'all'), '完整模型矩阵包含 NaN/Inf。');

    load(eqFile, 'ElCentroAccel', 'EQ_intensity', 'EQ_sw');
    assert(EQ_sw == 1, 'EQ.mat 的 EQ_sw 必须为 1（El Centro 分支）。');
    assert(abs(EQ_intensity - 0.40) <= 10*eps(max(1, abs(EQ_intensity))), ...
        'EQ_intensity 必须保持为 0.40，实际为 %.17g。', EQ_intensity);
    assert(size(ElCentroAccel,1) == 2, ...
        'ElCentroAccel 必须为 2xN：[时间; 加速度]。');

    dt = 1/1024;
    stopTime = 40;
    fineTime = (0:dt:stopTime)';
    chirpAcceleration = sin(2*pi*0.1*fineTime + ...
        pi*(10-0.1)/stopTime*fineTime.^2);
    eqTime = ElCentroAccel(1,:)';
    eqAcceleration = EQ_intensity * ElCentroAccel(2,:)';
    validMask = eqTime <= stopTime;
    eqTime = eqTime(validMask);
    eqAcceleration = eqAcceleration(validMask);
    assert(all(diff(eqTime) > 0), 'El Centro 时间轴必须严格递增。');
    assert(all(isfinite(eqAcceleration)), 'El Centro 激励包含 NaN/Inf。');
    assert(numel(fineTime) == 40961, '40 s、1/1024 s 应产生 40961 个固定步输出。');

    excitationCases = struct([]);
    excitationCases(1).key = 'ElCentro';
    excitationCases(1).fileToken = 'ElCentro地震响应';
    excitationCases(1).description = 'El Centro 1940 NS，原记录乘0.40';
    excitationCases(1).input = [eqTime, eqAcceleration];
    excitationCases(1).interpolate = true;
    excitationCases(2).key = 'Chirp';
    excitationCases(2).fileToken = 'Chirp响应';
    excitationCases(2).description = '0.1--10 Hz线性Chirp，40 s';
    excitationCases(2).input = [fineTime, chirpAcceleration];
    excitationCases(2).interpolate = true;

    %% 3. 仅在 outputs/model_work 中建立模型副本并做历史生成器同口径适配
    divisionModelFiles = {
        fullfile(modelWorkDir, 'division1_impact.slx');
        fullfile(modelWorkDir, 'division2_impact.slx')};
    prepare_model_copy(division1SourceModel, divisionModelFiles{1}, false, ...
        auxGroundDir, dt, stopTime);
    prepare_model_copy(division2SourceModel, divisionModelFiles{2}, true, ...
        auxGroundDir, dt, stopTime);

    %% 4. 构造两条 Guyan 路线；除 Mg/Cg/Kg 外，其余对象完全相同
    historicalModels = cell(2,1);
    projectedModels = cell(2,1);
    for division = 1:2
        historicalModels{division} = build_reduction_models( ...
            MRrt, CRrt, KRrt, division, 'historical_single_sided');
        % 从同一历史对象派生标准路线，保证完整模型、CB、T、载荷和恢复矩阵
        % 逐元素不变；唯一替换的是 Guyan 的 M/C/K 及由它们生成的 G_2。
        projectedModels{division} = make_projected_variant( ...
            historicalModels{division});
        assert(isequal(historicalModels{division}.T, projectedModels{division}.T), ...
            '两条路线的 Guyan T 必须逐元素一致。');
        assert(isequal(historicalModels{division}.Mf, projectedModels{division}.Mf), ...
            '两条路线的 Mf 必须逐元素一致。');
        assert(norm(historicalModels{division}.T_cb - ...
            projectedModels{division}.T_cb, 'fro') == 0, ...
            '两条路线的 Craig--Bampton T_cb 必须逐元素一致。');
    end

    %% 5. 矩阵门槛和矩阵输出
    matrixTable = table();
    for division = 1:2
        H = historicalModels{division};
        Pj = projectedModels{division};
        row = audit_matrix_pair(H, Pj, division);
        matrixTable = append_table_rows(matrixTable, row);

        matrixBundle = struct( ...
            'division', division, 'master', H.master, 'slave', H.slave, ...
            'order', H.order, 'T', H.T, 'T_cb', H.T_cb, 'Mf', H.Mf, ...
            'Mo', H.Mo, 'Co', H.Co, 'Ko', H.Ko, ...
            'M_historical', H.M_legacy, 'C_historical', H.C_legacy, ...
            'K_historical', H.K_legacy, ...
            'M_projected', Pj.M_projected, 'C_projected', Pj.C_projected, ...
            'K_projected', Pj.K_projected, ...
            'M_cb', H.M_cb, 'C_cb', H.C_cb, 'K_cb', H.K_cb);
        save(fullfile(matrixDir, sprintf('division_%d_guyan_matrices.mat', division)), ...
            'matrixBundle', '-v7');
    end
    writetable(matrixTable, fullfile(matrixDir, 'guyan_matrix_audit.csv'), ...
        'Encoding', 'UTF-8');

    %% 6. 前两阶自然频率和相对完整模型误差
    fullFrequencyHz = natural_frequencies(MRrt, KRrt, 2, '完整模型');
    modalTable = table();
    for division = 1:2
        H = historicalModels{division};
        Pj = projectedModels{division};
        historicalFrequencyHz = natural_frequencies( ...
            H.M_legacy, H.K_legacy, 2, sprintf('Division %d historical', division));
        projectedFrequencyHz = natural_frequencies( ...
            Pj.M_projected, Pj.K_projected, 2, sprintf('Division %d projected', division));
        cbFrequencyHz = natural_frequencies( ...
            H.M_cb, H.K_cb, 2, sprintf('Division %d Craig-Bampton', division));
        for modeIndex = 1:2
            modalTable = append_table_rows(modalTable, make_modal_row(division, ...
                'Original', 'route_invariant', modeIndex, fullFrequencyHz(modeIndex), ...
                fullFrequencyHz(modeIndex)));
            modalTable = append_table_rows(modalTable, make_modal_row(division, ...
                'Guyan', 'historical_single_sided', modeIndex, ...
                historicalFrequencyHz(modeIndex), fullFrequencyHz(modeIndex)));
            modalTable = append_table_rows(modalTable, make_modal_row(division, ...
                'Guyan', 'projected_congruence', modeIndex, ...
                projectedFrequencyHz(modeIndex), fullFrequencyHz(modeIndex)));
            modalTable = append_table_rows(modalTable, make_modal_row(division, ...
                'Craig-Bampton', 'route_invariant', modeIndex, ...
                cbFrequencyHz(modeIndex), fullFrequencyHz(modeIndex)));
        end
    end
    writetable(modalTable, fullfile(modalDir, 'guyan_modal_comparison.csv'), ...
        'Encoding', 'UTF-8');

    %% 7. 先复现历史四个基线；未通过时禁止进入标准路线
    baselineAbsToleranceMm = 1e-9;
    baselineRelativeTolerance = 1e-10;
    baselineTimeToleranceS = 1e-12;
    historicalResponses = cell(2, numel(excitationCases));
    baselineTable = table();
    divisionLabels = {'第一类划分', '第二类划分'};

    for division = 1:2
        H = historicalModels{division};
        for caseIndex = 1:numel(excitationCases)
            E = excitationCases(caseIndex);
            assign_model_variables(H, MRrt);
            rawOutput = run_one_simulation(divisionModelFiles{division}, ...
                E.input, E.interpolate, dt, stopTime);
            response = make_response_struct(rawOutput, E.description, ...
                divisionLabels{division}, 'historical_single_sided', dt, stopTime);
            historicalResponses{division,caseIndex} = response;

            outputBase = fullfile(historicalResponseDir, ...
                [divisionLabels{division}, '_', E.fileToken]);
            save_response(response, outputBase);

            frozenPath = fullfile(historicalOutputDir, ...
                [divisionLabels{division}, '_', E.fileToken, '.csv']);
            checkRow = compare_historical_baseline(response, frozenPath, ...
                division, E.key, baselineTimeToleranceS, ...
                baselineAbsToleranceMm, baselineRelativeTolerance);
            baselineTable = append_table_rows(baselineTable, checkRow);
        end
    end
    assert(height(baselineTable) == 4 && all(baselineTable.pass), ...
        '四个历史基线必须全部通过后才允许运行标准路线。');
    writetable(baselineTable, fullfile(metricDir, 'historical_baseline_check.csv'), ...
        'Encoding', 'UTF-8');
    fprintf('历史基线门槛：4/4 PASS。\n');

    %% 8. 标准 T''AT 路线：同两类划分、同两种激励、同模型副本
    projectedResponses = cell(2, numel(excitationCases));
    invariantTable = table();
    for division = 1:2
        Pj = projectedModels{division};
        for caseIndex = 1:numel(excitationCases)
            E = excitationCases(caseIndex);
            assign_model_variables(Pj, MRrt);
            rawOutput = run_one_simulation(divisionModelFiles{division}, ...
                E.input, E.interpolate, dt, stopTime);
            response = make_response_struct(rawOutput, E.description, ...
                divisionLabels{division}, 'projected_congruence', dt, stopTime);
            projectedResponses{division,caseIndex} = response;

            outputBase = fullfile(projectedResponseDir, ...
                [divisionLabels{division}, '_', E.fileToken]);
            save_response(response, outputBase);

            invariantRow = verify_route_invariants( ...
                historicalResponses{division,caseIndex}, response, ...
                division, E.key, baselineAbsToleranceMm, baselineRelativeTolerance);
            invariantTable = append_table_rows(invariantTable, invariantRow);
        end
    end
    assert(height(invariantTable) == 4 && all(invariantTable.pass), ...
        'Original/CB 路线不变性检查未全部通过。');
    writetable(invariantTable, fullfile(metricDir, 'route_invariant_check.csv'), ...
        'Encoding', 'UTF-8');

    %% 9. 统一三层响应指标：全时程 NRMSE、绝对峰值和 chirp 五频段 NRMSE
    metricTable = table();
    routeNames = {'historical_single_sided', 'projected_congruence'};
    routeResponses = {historicalResponses, projectedResponses};
    for routeIndex = 1:numel(routeNames)
        responsesForRoute = routeResponses{routeIndex};
        for division = 1:2
            for caseIndex = 1:numel(excitationCases)
                rows = compute_response_metrics( ...
                    responsesForRoute{division,caseIndex}, routeNames{routeIndex}, ...
                    division, excitationCases(caseIndex).key);
                metricTable = append_table_rows(metricTable, rows);
            end
        end
    end
    assert(all(isfinite(metricTable.nrmse_percent)), ...
        '响应指标表包含非有限 NRMSE。');
    writetable(metricTable, fullfile(metricDir, 'guyan_response_metrics.csv'), ...
        'Encoding', 'UTF-8');

    %% 10. 保存汇总 MAT，便于独立复核而不依赖工作区
    save(fullfile(outputDir, 'guyan_impact_summary.mat'), ...
        'matrixTable', 'modalTable', 'baselineTable', 'invariantTable', ...
        'metricTable', 'fullFrequencyHz', 'dt', 'stopTime', '-v7');

    fprintf('矩阵输出：%s\n', matrixDir);
    fprintf('模态输出：%s\n', modalDir);
    fprintf('响应输出：%s\n', responseDir);
    fprintf('指标输出：%s\n', metricDir);
    fprintf('Guyan 双侧投影结论影响核查完成：%s\n', string(datetime('now')));
catch ME
    fprintf(2, 'Guyan 影响核查失败：%s\n', ...
        getReport(ME, 'extended', 'hyperlinks', 'off'));
    rethrow(ME);
end

%% 局部函数

function verify_frozen_inputs(manifestPath, requiredFiles)
    assert(isfile(manifestPath), '缺少冻结清单：%s', manifestPath);
    manifest = readtable(manifestPath, 'VariableNamingRule', 'preserve', ...
        'TextType', 'string');
    requiredColumns = {'CopyPath','SHA256Copy','InitialIntegrity'};
    assert(all(ismember(requiredColumns, manifest.Properties.VariableNames)), ...
        'source_manifest.csv 缺少必要列。');

    manifestPaths = normalize_windows_path(manifest.CopyPath);
    for k = 1:numel(requiredFiles)
        filePath = requiredFiles{k};
        assert(isfile(filePath), '冻结输入缺失：%s', filePath);
        normalized = normalize_windows_path(string(filePath));
        index = find(strcmpi(manifestPaths, normalized), 1);
        assert(~isempty(index), '冻结输入未登记在 source_manifest.csv：%s', filePath);
        assert(strcmpi(manifest.InitialIntegrity(index), 'MATCH'), ...
            '冻结清单中的输入不是 MATCH：%s', filePath);
        actualHash = sha256_file(filePath);
        assert(strcmpi(actualHash, manifest.SHA256Copy(index)), ...
            '冻结输入 SHA-256 不匹配：%s', filePath);
    end
    fprintf('冻结输入预检：%d 项全部匹配 source_manifest.csv。\n', numel(requiredFiles));
end

function paths = normalize_windows_path(paths)
    paths = replace(string(paths), '/', '\');
end

function prepare_model_copy(sourceFile, targetFile, needsThirdFloorRepair, ...
        auxGroundDir, dt, stopTime)
    assert(isfile(sourceFile), '模型冻结副本缺失：%s', sourceFile);
    [~, modelName] = fileparts(targetFile);
    if bdIsLoaded(modelName)
        close_system(modelName, 0);
    end
    copyfile(sourceFile, targetFile, 'f');
    load_system(targetFile);

    inputBlock = [modelName '/可复现excitation_input'];
    if getSimulinkBlockHandle(inputBlock) < 0
        add_block('simulink/Sources/From Workspace', inputBlock, ...
            'VariableName', 'excitation_input', 'Interpolate', 'on', ...
            'OutputAfterFinalValue', 'Holding final value', ...
            'Position', [45 515 160 545]);
    end
    inputPort = get_param(inputBlock, 'PortHandles');
    gainNames = {'地震激励-力1','地震激励-力2','Gain5'};
    expectedGainExpressions = { ...
        'diag([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0].*MRrt)', ...
        'T''*Mf', 'T_cb''*Mf'};
    for k = 1:numel(gainNames)
        block = [modelName '/' gainNames{k}];
        assert(getSimulinkBlockHandle(block) >= 0, '模型缺少激励增益块：%s', block);
        actualGain = regexprep(get_param(block, 'Gain'), '\s+', '');
        expectedGain = regexprep(expectedGainExpressions{k}, '\s+', '');
        assert(strcmp(actualGain, expectedGain), ...
            ['冻结模型激励增益表达式已变化：%s；期望 %s，' ...
            '实际 %s。本脚本只核对，不改写 Gain。'], ...
            block, expectedGainExpressions{k}, get_param(block, 'Gain'));
        ports = get_param(block, 'PortHandles');
        lineHandle = get_param(ports.Inport, 'Line');
        if lineHandle ~= -1
            delete_line(lineHandle);
        end
        add_line(modelName, inputPort.Outport, ports.Inport, 'autorouting', 'on');
    end

    % 原地震子系统被本次 From Workspace 输入旁路，但编译时仍需其 From File 文件。
    fromFileBlocks = find_system(modelName, 'LookUnderMasks', 'all', ...
        'FollowLinks', 'on', 'BlockType', 'FromFile');
    for k = 1:numel(fromFileBlocks)
        oldFile = get_param(fromFileBlocks{k}, 'FileName');
        [~, baseName, ext] = fileparts(oldFile);
        localFile = fullfile(auxGroundDir, [baseName ext]);
        assert(isfile(localFile), '缺少冻结的地震编译依赖：%s', localFile);
        set_param(fromFileBlocks{k}, 'FileName', localFile);
    end

    stateBlocks = {'数值子结构1','数值子结构2','数值子结构3'};
    cVars = {'output_matrix_original','output_matrix_guyan','output_matrix_cb'};
    dVars = {'feedthrough_matrix_original','feedthrough_matrix_guyan', ...
        'feedthrough_matrix_cb'};
    selectors = {'Selector3','Selector5','Selector9'};
    for k = 1:3
        set_param([modelName '/' stateBlocks{k}], 'C', cVars{k}, 'D', dVars{k});
        set_param([modelName '/' selectors{k}], ...
            'Indices', '[1 2 3]', 'InputPortWidth', '3');
    end

    if needsThirdFloorRepair
        % 与历史生成器一致：只修复复制模型中原先断开的第三层 Guyan/CB 输出。
        set_param([modelName '/Demux4'], 'Outputs', '3');
        set_param([modelName '/Demux5'], 'Outputs', '3');
        save_system(modelName, targetFile);
        close_system(modelName, 0);
        load_system(targetFile);

        demuxNames = {'Demux4','Demux5'};
        for k = 1:2
            demuxPorts = get_param([modelName '/' demuxNames{k}], 'PortHandles');
            muxPorts = get_param([modelName '/Mux6'], 'PortHandles');
            oldLine = get_param(muxPorts.Inport(k+1), 'Line');
            if oldLine ~= -1
                delete_line(oldLine);
            end
            add_line(modelName, demuxPorts.Outport(3), muxPorts.Inport(k+1), ...
                'autorouting', 'on');
        end
    end

    set_param(modelName, 'StopTime', num2str(stopTime,17), ...
        'Solver', 'ode4', 'SolverType', 'Fixed-step', ...
        'FixedStep', num2str(dt,17));
    save_system(modelName, targetFile);
    close_system(modelName, 0);

    if needsThirdFloorRepair
        load_system(targetFile);
        muxPorts = get_param([modelName '/Mux6'], 'PortHandles');
        expectedBlocks = {'Demux3','Demux4','Demux5'};
        for k = 1:3
            lineHandle = get_param(muxPorts.Inport(k), 'Line');
            assert(lineHandle ~= -1, 'Mux6 输入端口 %d 未连接。', k);
            sourceBlock = get_param(lineHandle, 'SrcBlockHandle');
            sourcePort = get_param(lineHandle, 'SrcPortHandle');
            expectedBlock = getSimulinkBlockHandle([modelName '/' expectedBlocks{k}]);
            expectedPorts = get_param([modelName '/' expectedBlocks{k}], 'PortHandles');
            assert(sourceBlock == expectedBlock && sourcePort == expectedPorts.Outport(3), ...
                'Mux6/%d 不是由 %s/3 驱动。', k, expectedBlocks{k});
        end
        close_system(modelName, 0);
    end
end

function R = build_reduction_models(M, C, K, division, route)
    if division == 1
        master = [1,6,11,4,9,14];
        slave = [2,3,5,7,8,10,12,13,15];
        forceMask = [1,1,1,0,0,0,0,0,0,0,0,0,0,0,0];
    elseif division == 2
        master = [1,11,4,9,14];
        slave = [6,2,3,5,7,8,10,12,13,15];
        forceMask = [1,1,0,0,0,1,0,0,0,0,0,0,0,0,0];
    else
        error('未知划分编号：%g', division);
    end

    order = [master, slave];
    assert(isequal(sort(order), 1:15) && numel(unique(order)) == 15, ...
        'Division %d 的 master/slave 不是 1:15 的无重复分割。', division);
    Mo = M(order,order);
    Co = C(order,order);
    Ko = K(order,order);
    nm = numel(master);
    Mmm = Mo(1:nm,1:nm);
    Mms = Mo(1:nm,nm+1:end);
    Cmm = Co(1:nm,1:nm);
    Cms = Co(1:nm,nm+1:end);
    Kmm = Ko(1:nm,1:nm);
    Kms = Ko(1:nm,nm+1:end);
    Ksm = Ko(nm+1:end,1:nm);
    Kss = Ko(nm+1:end,nm+1:end);
    Mss = Mo(nm+1:end,nm+1:end);

    staticRelation = -(Kss \ Ksm);
    T = [eye(nm); staticRelation];
    Mlegacy = Mmm + Mms*staticRelation;
    Clegacy = Cmm + Cms*staticRelation;
    Klegacy = Kmm + Kms*staticRelation;
    Mprojected = T'*Mo*T;
    Cprojected = T'*Co*T;
    Kprojected = T'*Ko*T;

    if strcmp(route, 'historical_single_sided')
        Mactive = Mlegacy;
        Cactive = Clegacy;
        Kactive = Klegacy;
    elseif strcmp(route, 'projected_congruence')
        Mactive = Mprojected;
        Cactive = Cprojected;
        Kactive = Kprojected;
    else
        error('未知 Guyan 路线：%s', route);
    end

    % Craig--Bampton 与历史生成器一致，固定保留3阶固定界面模态。
    [phi, lambda] = eig(Kss, Mss);
    [~, modeOrder] = sort(real(diag(lambda)), 'ascend');
    phi = real(phi(:,modeOrder));
    retainedFixedInterfaceModes = 3;
    assert(size(phi,2) >= retainedFixedInterfaceModes, ...
        '固定界面模态数不足3阶。');
    Tcb = [eye(nm), zeros(nm,retainedFixedInterfaceModes); ...
        staticRelation, phi(:,1:retainedFixedInterfaceModes)];
    Mcb = Tcb'*Mo*Tcb;
    Ccb = Tcb'*Co*Tcb;
    Kcb = Tcb'*Ko*Tcb;

    G1 = second_order_ss(M, C, K);
    G2 = second_order_ss(Mactive, Cactive, Kactive);
    G3 = second_order_ss(Mcb, Ccb, Kcb);

    floorOriginal = [1,6,11];
    floorRowsOrdered = arrayfun(@(q)find(order == q, 1), floorOriginal);
    P = eye(15);
    P = P(floorRowsOrdered,:);
    Cfloor1 = [eye(15), zeros(15)];
    Cfloor1 = Cfloor1(floorOriginal,:);
    Cfloor2 = [P*T, zeros(3,size(T,2))];
    Cfloor3 = [P*Tcb, zeros(3,size(Tcb,2))];

    % 严格保持历史载荷口径：先取三层水平质量对角项，再在 SLX 中乘 T'。
    Mf = diag(forceMask .* Mo);

    R.route = route;
    R.G_1 = G1;
    R.G_2 = G2;
    R.G_3 = G3;
    R.T = T;
    R.T_cb = Tcb;
    R.Mf = Mf;
    R.Cfloor1 = Cfloor1;
    R.Cfloor2 = Cfloor2;
    R.Cfloor3 = Cfloor3;
    R.Dfloor1 = zeros(3,size(G1.B,2));
    R.Dfloor2 = zeros(3,size(G2.B,2));
    R.Dfloor3 = zeros(3,size(G3.B,2));
    R.master = master;
    R.slave = slave;
    R.order = order;
    R.staticRelation = staticRelation;
    R.Ksm = Ksm;
    R.Kss = Kss;
    R.Mo = Mo;
    R.Co = Co;
    R.Ko = Ko;
    R.M_legacy = Mlegacy;
    R.C_legacy = Clegacy;
    R.K_legacy = Klegacy;
    R.M_projected = Mprojected;
    R.C_projected = Cprojected;
    R.K_projected = Kprojected;
    R.M_cb = Mcb;
    R.C_cb = Ccb;
    R.K_cb = Kcb;
    R.M_active = Mactive;
    R.C_active = Cactive;
    R.K_active = Kactive;
end

function R = make_projected_variant(H)
    R = H;
    R.route = 'projected_congruence';
    R.M_active = H.M_projected;
    R.C_active = H.C_projected;
    R.K_active = H.K_projected;
    R.G_2 = second_order_ss(R.M_active, R.C_active, R.K_active);
    R.Dfloor2 = zeros(3,size(R.G_2.B,2));
end

function G = second_order_ss(M, C, K)
    n = size(M,1);
    assert(isequal(size(M), [n,n]) && isequal(size(C), [n,n]) && ...
        isequal(size(K), [n,n]), '二阶状态空间矩阵维数不一致。');
    assert(all(isfinite(M), 'all') && all(isfinite(C), 'all') && ...
        all(isfinite(K), 'all'), '二阶状态空间矩阵包含 NaN/Inf。');
    assert(rcond(M) > eps, '状态空间质量矩阵数值奇异，rcond=%.3e。', rcond(M));
    A = [zeros(n), eye(n); -(M\K), -(M\C)];
    B = [zeros(n); M\eye(n)];
    Cq = [eye(n), zeros(n)];
    D = zeros(n,n);
    G = ss(A,B,Cq,D);
end

function row = audit_matrix_pair(H, Pj, division)
    transformRows = size(H.T,1);
    transformColumns = size(H.T,2);
    rankT = rank(H.T);
    staticResidual = norm(H.Ksm + H.Kss*H.staticRelation, 'fro') / ...
        max(norm(H.Ksm, 'fro'), eps);
    relativeM = relative_frobenius(H.M_legacy, Pj.M_projected);
    relativeC = relative_frobenius(H.C_legacy, Pj.C_projected);
    relativeK = relative_frobenius(H.K_legacy, Pj.K_projected);
    symmetryLegacyM = symmetry_residual(H.M_legacy);
    symmetryLegacyC = symmetry_residual(H.C_legacy);
    symmetryLegacyK = symmetry_residual(H.K_legacy);
    symmetryM = symmetry_residual(Pj.M_projected);
    symmetryC = symmetry_residual(Pj.C_projected);
    symmetryK = symmetry_residual(Pj.K_projected);

    eigM = eig((Pj.M_projected + Pj.M_projected')/2);
    eigC = eig((Pj.C_projected + Pj.C_projected')/2);
    eigK = eig((Pj.K_projected + Pj.K_projected')/2);
    minEigM = min(real(eigM));
    minEigC = min(real(eigC));
    minEigK = min(real(eigK));
    dampingNegativeTolerance = 1e-12 * max(norm(Pj.C_projected, 2), 1);

    assert(transformRows == numel(H.master)+numel(H.slave) && ...
        transformColumns == numel(H.master), ...
        'Division %d: T 维数应为 %dx%d，实际为 %dx%d。', ...
        division, numel(H.master)+numel(H.slave), numel(H.master), ...
        transformRows, transformColumns);
    assert(rankT == numel(H.master), ...
        'Division %d: rank(T)=%d，不等于主自由度数%d。', ...
        division, rankT, numel(H.master));
    assert(staticResidual < 1e-12, ...
        'Division %d: 静力缩聚残差 %.3e 超过1e-12。', division, staticResidual);
    assert(symmetryM < 1e-12 && symmetryC < 1e-12 && symmetryK < 1e-12, ...
        'Division %d: 标准投影矩阵对称残差超过1e-12。', division);
    assert(relativeK < 1e-12, ...
        'Division %d: 两条刚度路线相对差 %.3e 超过1e-12。', division, relativeK);
    assert(minEigM > 0, 'Division %d: 标准质量矩阵不是正定矩阵。', division);
    assert(minEigK > 0, 'Division %d: 标准刚度矩阵不是正定矩阵。', division);
    assert(minEigC >= -dampingNegativeTolerance, ...
        'Division %d: 标准阻尼矩阵最小特征值 %.3e 超出舍入容差 %.3e。', ...
        division, minEigC, dampingNegativeTolerance);

    row = table(division, numel(H.master), numel(H.slave), ...
        transformRows, transformColumns, rankT, ...
        staticResidual, relativeM, relativeC, relativeK, ...
        symmetryLegacyM, symmetryLegacyC, symmetryLegacyK, ...
        symmetryM, symmetryC, symmetryK, minEigM, minEigC, minEigK, ...
        dampingNegativeTolerance, ...
        'VariableNames', {'division','n_master','n_slave','T_rows','T_columns','rank_T', ...
        'static_residual','relative_M','relative_C','relative_K', ...
        'symmetry_M_historical','symmetry_C_historical','symmetry_K_historical', ...
        'symmetry_M_projected','symmetry_C_projected','symmetry_K_projected', ...
        'min_eigenvalue_M_projected','min_eigenvalue_C_projected', ...
        'min_eigenvalue_K_projected','damping_negative_tolerance'});
end

function value = relative_frobenius(A, reference)
    denominator = norm(reference, 'fro');
    assert(denominator > 0, 'Frobenius 相对差分母为0。');
    value = norm(A-reference, 'fro') / denominator;
end

function value = symmetry_residual(A)
    value = norm(A-A', 'fro') / max(norm(A, 'fro'), eps);
end

function frequencyHz = natural_frequencies(M, K, numberOfModes, description)
    lambda = eig(K, M);
    assert(all(isfinite(lambda)), '%s 的广义特征值包含 NaN/Inf。', description);
    imaginaryTolerance = 1e-9 * max(1, max(abs(real(lambda))));
    assert(max(abs(imag(lambda))) <= imaginaryTolerance, ...
        '%s 的广义特征值存在显著虚部。', description);
    lambda = sort(real(lambda));
    positiveLambda = lambda(lambda > 0);
    assert(numel(positiveLambda) >= numberOfModes, ...
        '%s 的正特征值不足%d个。', description, numberOfModes);
    frequencyHz = sqrt(positiveLambda(1:numberOfModes)) / (2*pi);
end

function row = make_modal_row(division, model, route, modeIndex, frequencyHz, fullFrequencyHz)
    relativeErrorPercent = abs(frequencyHz-fullFrequencyHz) / fullFrequencyHz * 100;
    row = table(division, string(model), string(route), modeIndex, fullFrequencyHz, ...
        frequencyHz, relativeErrorPercent, ...
        'VariableNames', {'division','model','route','mode','full_frequency_hz', ...
        'frequency_hz','relative_frequency_error_percent'});
end

function assign_model_variables(R, MRrt)
    names = {'G_1','G_2','G_3','T','T_cb','Mf', ...
        'output_matrix_original','output_matrix_guyan','output_matrix_cb', ...
        'feedthrough_matrix_original','feedthrough_matrix_guyan', ...
        'feedthrough_matrix_cb','MRrt'};
    values = {R.G_1,R.G_2,R.G_3,R.T,R.T_cb,R.Mf, ...
        R.Cfloor1,R.Cfloor2,R.Cfloor3,R.Dfloor1,R.Dfloor2,R.Dfloor3,MRrt};
    for k = 1:numel(names)
        assignin('base', names{k}, values{k});
    end
end

function out = run_one_simulation(modelFile, excitation, interpolate, dt, stopTime)
    [~, modelName] = fileparts(modelFile);
    if bdIsLoaded(modelName)
        close_system(modelName, 0);
    end
    load_system(modelFile);
    assignin('base', 'excitation_input', excitation);
    assignin('base', 'dt', dt);
    if interpolate
        interpolateText = 'on';
    else
        interpolateText = 'off';
    end
    set_param([modelName '/可复现excitation_input'], ...
        'Interpolate', interpolateText);
    set_param(modelName, 'StopTime', num2str(stopTime,17), ...
        'Solver', 'ode4', 'SolverType', 'Fixed-step', ...
        'FixedStep', num2str(dt,17));
    simulationOutput = sim(modelName, 'ReturnWorkspaceOutputs', 'on');
    out.floor1 = simulationOutput.simout3;
    out.floor2 = simulationOutput.simout;
    out.floor3 = simulationOutput.simout1;
    close_system(modelName, 0);
end

function S = make_response_struct(out, excitationDescription, divisionDescription, ...
        routeDescription, dt, stopTime)
    time = out.floor1.Time(:);
    assert(max(abs(time-out.floor2.Time(:))) < 1e-12 && ...
        max(abs(time-out.floor3.Time(:))) < 1e-12, ...
        '三个楼层输出时间轴不一致。');
    expectedSamples = round(stopTime/dt) + 1;
    assert(numel(time) == expectedSamples, ...
        '固定步输出应为%d点，实际为%d点。', expectedSamples, numel(time));
    assert(abs(time(1)) < 1e-12 && abs(time(end)-stopTime) < 1e-12, ...
        '输出时间轴端点必须为0和40 s。');
    assert(max(abs(diff(time)-dt)) < 1e-12, ...
        '输出时间步长不是严格的1/1024 s。');

    floor1 = squeeze(out.floor1.Data);
    floor2 = squeeze(out.floor2.Data);
    floor3 = squeeze(out.floor3.Data);
    assert(size(floor1,2) == 3 && size(floor2,2) == 3 && size(floor3,2) == 3, ...
        '每层输出必须包含 Original、Guyan、Craig-Bampton 三列。');
    responseMm = cat(2, reshape(floor1,[],1,3), ...
        reshape(floor2,[],1,3), reshape(floor3,[],1,3));
    assert(all(isfinite(responseMm), 'all'), '响应包含 NaN/Inf。');

    S.time_s = time;
    S.response_mm = responseMm;
    S.method_order = {'Original','Guyan','Craig-Bampton'};
    S.floor_order = {'Floor 1','Floor 2','Floor 3'};
    S.excitation = excitationDescription;
    S.division = divisionDescription;
    S.route = routeDescription;
end

function save_response(S, basePath)
    time_s = S.time_s; %#ok<NASGU>
    response_mm = S.response_mm; %#ok<NASGU>
    method_order = S.method_order; %#ok<NASGU>
    floor_order = S.floor_order; %#ok<NASGU>
    excitation = S.excitation; %#ok<NASGU>
    division = S.division; %#ok<NASGU>
    route = S.route; %#ok<NASGU>
    save([basePath '.mat'], 'time_s', 'response_mm', 'method_order', ...
        'floor_order', 'excitation', 'division', 'route', '-v7');
    responseTable = response_to_table(S);
    writetable(responseTable, [basePath '.csv'], 'Encoding', 'UTF-8');
end

function responseTable = response_to_table(S)
    responseTable = table(S.time_s, ...
        S.response_mm(:,1,1),S.response_mm(:,1,2),S.response_mm(:,1,3), ...
        S.response_mm(:,2,1),S.response_mm(:,2,2),S.response_mm(:,2,3), ...
        S.response_mm(:,3,1),S.response_mm(:,3,2),S.response_mm(:,3,3), ...
        'VariableNames', {'时间_s','原结构_一层_mm','Guyan_一层_mm', ...
        'CraigBampton_一层_mm','原结构_二层_mm','Guyan_二层_mm', ...
        'CraigBampton_二层_mm','原结构_三层_mm','Guyan_三层_mm', ...
        'CraigBampton_三层_mm'});
end

function row = compare_historical_baseline(response, frozenPath, division, ...
        excitationKey, timeTolerance, absoluteToleranceMm, relativeTolerance)
    frozen = readtable(frozenPath, 'VariableNamingRule', 'preserve');
    generated = response_to_table(response);
    assert(isequal(string(frozen.Properties.VariableNames), ...
        string(generated.Properties.VariableNames)), ...
        '历史基线列名不一致：%s', frozenPath);
    assert(height(frozen) == height(generated), ...
        '历史基线行数不一致：%s', frozenPath);
    frozenValues = table2array(frozen);
    generatedValues = table2array(generated);
    assert(all(isfinite(frozenValues), 'all'), '冻结历史基线包含 NaN/Inf：%s', frozenPath);

    maxTimeError = max(abs(generatedValues(:,1)-frozenValues(:,1)));
    responseDifference = generatedValues(:,2:end)-frozenValues(:,2:end);
    maxAbsErrorMm = max(abs(responseDifference), [], 'all');
    frozenScaleMm = max(abs(frozenValues(:,2:end)), [], 'all');
    allowedMaxErrorMm = absoluteToleranceMm + ...
        relativeTolerance*max(1, frozenScaleMm);
    relativeFrobeniusError = norm(responseDifference, 'fro') / ...
        max(norm(frozenValues(:,2:end), 'fro'), eps);
    pass = maxTimeError <= timeTolerance && ...
        maxAbsErrorMm <= allowedMaxErrorMm && ...
        relativeFrobeniusError <= relativeTolerance;
    assert(pass, ['历史基线未复现：Division %d %s；time=%.3e s，' ...
        'maxAbs=%.3e mm（门槛%.3e），relFro=%.3e（门槛%.3e）。'], ...
        division, excitationKey, maxTimeError, maxAbsErrorMm, ...
        allowedMaxErrorMm, relativeFrobeniusError, relativeTolerance);

    row = table(division, string(excitationKey), height(frozen), maxTimeError, ...
        maxAbsErrorMm, frozenScaleMm, allowedMaxErrorMm, ...
        relativeFrobeniusError, relativeTolerance, pass, ...
        'VariableNames', {'division','excitation','samples','max_time_error_s', ...
        'max_abs_response_error_mm','frozen_response_scale_mm', ...
        'allowed_max_response_error_mm','relative_frobenius_error', ...
        'relative_tolerance','pass'});
end

function row = verify_route_invariants(historical, projected, division, ...
        excitationKey, absoluteToleranceMm, relativeTolerance)
    assert(max(abs(historical.time_s-projected.time_s)) < 1e-12, ...
        '两路线时间轴不一致。');
    invariantMethodIndices = [1,3]; % Original 与 Craig--Bampton
    difference = historical.response_mm(:,:,invariantMethodIndices) - ...
        projected.response_mm(:,:,invariantMethodIndices);
    reference = historical.response_mm(:,:,invariantMethodIndices);
    maxAbsErrorMm = max(abs(difference), [], 'all');
    referenceScaleMm = max(abs(reference), [], 'all');
    allowedMaxErrorMm = absoluteToleranceMm + ...
        relativeTolerance*max(1, referenceScaleMm);
    relativeFrobeniusError = norm(difference(:)) / max(norm(reference(:)), eps);
    pass = maxAbsErrorMm <= allowedMaxErrorMm && ...
        relativeFrobeniusError <= relativeTolerance;
    assert(pass, ['只有 Guyan 可以随路线改变；Division %d %s 的 Original/CB ' ...
        'maxAbs=%.3e mm，rel=%.3e。'], ...
        division, excitationKey, maxAbsErrorMm, relativeFrobeniusError);
    row = table(division, string(excitationKey), maxAbsErrorMm, ...
        referenceScaleMm, allowedMaxErrorMm, relativeFrobeniusError, ...
        relativeTolerance, pass, ...
        'VariableNames', {'division','excitation','max_abs_original_cb_error_mm', ...
        'reference_scale_mm','allowed_max_error_mm','relative_frobenius_error', ...
        'relative_tolerance','pass'});
end

function metricRows = compute_response_metrics(S, route, division, excitationKey)
    metricRows = table();
    methodIndices = [2,3];
    methodNames = {'Guyan','Craig-Bampton'};
    fullMask = true(size(S.time_s));
    for floorIndex = 1:3
        fullResponse = S.response_mm(:,floorIndex,1);
        denominator = max(fullResponse)-min(fullResponse);
        assert(denominator > eps, ...
            'Division %d %s Floor %d 的完整模型峰峰值为0。', ...
            division, excitationKey, floorIndex);
        fullPeak = max(abs(fullResponse));
        assert(fullPeak > eps, ...
            'Division %d %s Floor %d 的完整模型绝对峰值为0。', ...
            division, excitationKey, floorIndex);

        for methodIndex = 1:numel(methodIndices)
            methodResponse = S.response_mm(:,floorIndex,methodIndices(methodIndex));
            nrmsePercent = nrmse_with_fixed_denominator( ...
                fullResponse, methodResponse, fullMask, denominator);
            methodPeak = max(abs(methodResponse));
            peakRelativeErrorPercent = abs(methodPeak-fullPeak)/fullPeak*100;
            metricRows = append_table_rows(metricRows, make_metric_row(route, division, ...
                excitationKey, 'full_record', NaN, NaN, floorIndex, ...
                methodNames{methodIndex}, nnz(fullMask), denominator, ...
                nrmsePercent, fullPeak, methodPeak, ...
                peakRelativeErrorPercent));
        end

        if strcmp(excitationKey, 'Chirp')
            frequency = 0.1 + (10-0.1)/40*S.time_s;
            bandEdges = [0.1,1.9,3.5,5.4,8.1,10.0];
            bandLabels = {'0.1--1.9 Hz','1.9--3.5 Hz','3.5--5.4 Hz', ...
                '5.4--8.1 Hz','8.1--10.0 Hz'};
            for bandIndex = 1:(numel(bandEdges)-1)
                if bandIndex < numel(bandEdges)-1
                    mask = frequency >= bandEdges(bandIndex) & ...
                        frequency < bandEdges(bandIndex+1);
                else
                    mask = frequency >= bandEdges(bandIndex) & ...
                        frequency <= bandEdges(bandIndex+1);
                end
                assert(nnz(mask) > 1, 'Chirp 频段 %s 样本不足。', bandLabels{bandIndex});
                for methodIndex = 1:numel(methodIndices)
                    methodResponse = S.response_mm(:,floorIndex,methodIndices(methodIndex));
                    nrmsePercent = nrmse_with_fixed_denominator( ...
                        fullResponse, methodResponse, mask, denominator);
                    metricRows = append_table_rows(metricRows, make_metric_row(route, division, ...
                        excitationKey, bandLabels{bandIndex}, ...
                        bandEdges(bandIndex), bandEdges(bandIndex+1), ...
                        floorIndex, methodNames{methodIndex}, nnz(mask), ...
                        denominator, nrmsePercent, NaN, NaN, NaN));
                end
            end
        end
    end
end

function value = nrmse_with_fixed_denominator(reference, approximation, mask, denominator)
    difference = reference(mask)-approximation(mask);
    value = sqrt(mean(difference.^2))/denominator*100;
end

function row = make_metric_row(route, division, excitation, scope, ...
        lowerFrequencyHz, upperFrequencyHz, floorIndex, method, samples, ...
        denominatorMm, nrmsePercent, fullPeakMm, methodPeakMm, peakErrorPercent)
    row = table(string(route), division, string(excitation), string(scope), ...
        lowerFrequencyHz, upperFrequencyHz, floorIndex, string(method), ...
        samples, denominatorMm, nrmsePercent, fullPeakMm, methodPeakMm, ...
        peakErrorPercent, ...
        'VariableNames', {'route','division','excitation','scope', ...
        'lower_frequency_hz','upper_frequency_hz','floor','method','samples', ...
        'full_record_peak_to_peak_denominator_mm','nrmse_percent', ...
        'full_absolute_peak_mm','method_absolute_peak_mm', ...
        'absolute_peak_relative_error_percent'});
end

function combined = append_table_rows(existing, newRows)
    if width(existing) == 0
        combined = newRows;
    else
        combined = [existing; newRows];
    end
end

function digestText = sha256_file(filePath)
    digestEngine = java.security.MessageDigest.getInstance('SHA-256');
    javaFile = java.io.File(filePath);
    fileBytes = java.nio.file.Files.readAllBytes(javaFile.toPath());
    digestEngine.update(fileBytes);
    digestBytes = typecast(digestEngine.digest(), 'uint8');
    digestText = upper(reshape(dec2hex(digestBytes,2).',1,[]));
end

function cleanup_environment(modelNames, oldDir)
    for k = 1:numel(modelNames)
        if bdIsLoaded(modelNames{k})
            close_system(modelNames{k}, 0);
        end
    end
    cd(oldDir);
end
