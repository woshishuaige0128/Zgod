function run_board17_global_routes
%% 板块17：两类15自由度全局缩聚路线的隔离复现
% 只读取候选目录 input/ 中的冻结副本；只写 outputs/global_* 和 logs/global_*。
% 不运行 Simulink，不读取地震/扫频数据，不修改项目源文件或论文。

close all force;
clc;

codeDir = fileparts(mfilename('fullpath'));
candidateDir = fileparts(codeDir);
inputDir = fullfile(candidateDir, 'input');
outputDir = fullfile(candidateDir, 'outputs');
logDir = fullfile(candidateDir, 'logs');
if ~exist(outputDir, 'dir'), mkdir(outputDir); end
if ~exist(logDir, 'dir'), mkdir(logDir); end

logFile = fullfile(logDir, 'global_routes_matlab.log');
if isfile(logFile), delete(logFile); end
diary(logFile);
diaryCleanup = onCleanup(@() diary('off')); %#ok<NASGU>

fprintf('15自由度两类全局缩聚复现开始：%s\n', string(datetime('now')));
fprintf('MATLAB：%s\n', version);
fprintf('候选隔离目录：%s\n', candidateDir);

try
    %% 1. 冻结输入和参考矩阵
    referenceFile = fullfile(inputDir, 'upstream_u01', ...
        'reference_model_matlab.mat');
    parameterScript = fullfile(inputDir, 'response_chain', 'PDmonicanshu.m');
    transferFiles = {
        fullfile(inputDir, 'response_chain', 'untitled2_转存.m');
        fullfile(inputDir, 'response_chain', 'untitled_转存.m')};
    generatorFile = fullfile(inputDir, 'response_chain', ...
        'regenerate_chapter3_data.m');
    requiredFiles = [{referenceFile; parameterScript; generatorFile}; transferFiles];
    for k = 1:numel(requiredFiles)
        assert(isfile(requiredFiles{k}), '冻结输入缺失：%s', requiredFiles{k});
    end

    reference = load(referenceFile, 'MRrt', 'CRrt', 'KRrt', 'frequency_hz');
    requiredVariables = {'MRrt','CRrt','KRrt','frequency_hz'};
    assert(all(isfield(reference, requiredVariables)), ...
        '参考MAT缺少 MRrt/CRrt/KRrt/frequency_hz。');
    MRrt = reference.MRrt;
    CRrt = reference.CRrt;
    KRrt = reference.KRrt;
    frequency_hz_reference = reference.frequency_hz(:);
    assert(isequal(size(MRrt), [15,15]) && isequal(size(CRrt), [15,15]) && ...
        isequal(size(KRrt), [15,15]), '参考完整矩阵必须均为15x15。');
    assert(all(isfinite(MRrt), 'all') && all(isfinite(CRrt), 'all') && ...
        all(isfinite(KRrt), 'all'), '参考完整矩阵包含 NaN/Inf。');

    sourceTable = table(string(requiredFiles), ...
        strings(numel(requiredFiles),1), 'VariableNames', {'file','sha256'});
    for k = 1:height(sourceTable)
        sourceTable.sha256(k) = sha256_file(sourceTable.file(k));
    end
    writetable(sourceTable, fullfile(outputDir, 'global_source_hashes.csv'), ...
        'Encoding', 'UTF-8');

    %% 2. 完整模型频率和两类划分
    [full_frequency_hz, full_imaginary_ratio] = natural_frequencies(MRrt, KRrt);
    assert(numel(full_frequency_hz) == 15, '完整模型应有15个正频率。');
    reference_frequency_relative_error = norm( ...
        full_frequency_hz-frequency_hz_reference, 'inf') / ...
        max(norm(frequency_hz_reference, 'inf'), eps);
    assert(reference_frequency_relative_error < 1e-12, ...
        '由参考矩阵重算的频率与MAT内频率不一致：%.3e。', ...
        reference_frequency_relative_error);

    division1 = build_division(MRrt, CRrt, KRrt, 1, ...
        [1,6,11,4,9,14], [2,3,5,7,8,10,12,13,15], ...
        [1,1,1,0,0,0,0,0,0,0,0,0,0,0,0]);
    division2 = build_division(MRrt, CRrt, KRrt, 2, ...
        [1,11,4,9,14], [6,2,3,5,7,8,10,12,13,15], ...
        [1,1,0,0,0,1,0,0,0,0,0,0,0,0,0]);

    matrixAuditTable = [matrix_audit_row(division1); ...
        matrix_audit_row(division2)];
    assert(all(matrixAuditTable.internal_gate_pass), ...
        '两类划分的维数/静力关系/投影矩阵内部门槛未全部通过。');
    writetable(matrixAuditTable, ...
        fullfile(outputDir, 'global_matrix_audit.csv'), 'Encoding', 'UTF-8');

    dimensionTable = [dimension_rows(division1); dimension_rows(division2)];
    assert(all(dimensionTable.dimension_gate_pass), ...
        '降阶对象维数未满足第一类6/9维、第二类5/8维门槛。');
    writetable(dimensionTable, ...
        fullfile(outputDir, 'global_dimension_gates.csv'), 'Encoding', 'UTF-8');

    %% 3. 频率、矩阵、恢复矩阵和输入投影逐项导出
    modalTable = frequency_rows(0, '完整15自由度', ...
        'reference_full_model', full_frequency_hz, full_imaginary_ratio);
    modalTable = [modalTable; division_frequency_rows(division1); ...
        division_frequency_rows(division2)]; %#ok<AGROW>
    writetable(modalTable, ...
        fullfile(outputDir, 'global_modal_frequencies.csv'), 'Encoding', 'UTF-8');

    matrixEntries = [matrix_entry_rows(division1); ...
        matrix_entry_rows(division2)];
    writetable(matrixEntries, ...
        fullfile(outputDir, 'global_reduced_matrix_entries.csv'), ...
        'Encoding', 'UTF-8');

    recoveryTable = [recovery_rows(division1); recovery_rows(division2)];
    writetable(recoveryTable, ...
        fullfile(outputDir, 'global_recovery_matrices.csv'), 'Encoding', 'UTF-8');

    inputTable = [input_projection_rows(division1); ...
        input_projection_rows(division2)];
    writetable(inputTable, ...
        fullfile(outputDir, 'global_input_projection.csv'), 'Encoding', 'UTF-8');

    %% 4. 冻结原参数脚本 + 原转存脚本在独立函数工作区原样执行
    % 当前 Windows/MATLAB 对中文 .m 文件名直接 run 会先于脚本内容解析失败。
    % 因此同时保留直接运行失败，并运行逐字节相同、仅文件名改为 ASCII 的副本。
    transferByteCopies = {
        fullfile(outputDir, 'global_original_division1_bytecopy.m');
        fullfile(outputDir, 'global_original_division2_bytecopy.m')};
    for k = 1:2
        copyfile(transferFiles{k}, transferByteCopies{k}, 'f');
        assert(strcmpi(sha256_file(transferFiles{k}), ...
            sha256_file(transferByteCopies{k})), ...
            '原转存脚本 ASCII 文件名副本不是逐字节相同：Division %d。', k);
    end
    directOriginal1 = run_original_transfer( ...
        parameterScript, transferFiles{1}, reference);
    directOriginal2 = run_original_transfer( ...
        parameterScript, transferFiles{2}, reference);
    original1 = run_original_transfer( ...
        parameterScript, transferByteCopies{1}, reference);
    original2 = run_original_transfer( ...
        parameterScript, transferByteCopies{2}, reference);
    original1.execution_mode = "BYTE_IDENTICAL_ASCII_FILENAME_COPY";
    original2.execution_mode = "BYTE_IDENTICAL_ASCII_FILENAME_COPY";
    original1.source_transfer_script = transferFiles{1};
    original2.source_transfer_script = transferFiles{2};
    original1.bytecopy_sha256_match = true;
    original2.bytecopy_sha256_match = true;
    original1.direct_filename_status = directOriginal1.status;
    original2.direct_filename_status = directOriginal2.status;
    original1.direct_filename_error_identifier = directOriginal1.error_identifier;
    original2.direct_filename_error_identifier = directOriginal2.error_identifier;
    original1.direct_filename_error_message = directOriginal1.error_message;
    original2.direct_filename_error_message = directOriginal2.error_message;
    originalComparisonTable = [compare_original_script(division1, original1); ...
        compare_original_script(division2, original2)];
    writetable(originalComparisonTable, ...
        fullfile(outputDir, 'global_original_script_comparison.csv'), ...
        'Encoding', 'UTF-8');

    fprintf('中文原文件名直接运行第一类状态：%s；[%s] %s\n', ...
        directOriginal1.status, directOriginal1.error_identifier, ...
        directOriginal1.error_message);
    fprintf('中文原文件名直接运行第二类状态：%s；[%s] %s\n', ...
        directOriginal2.status, directOriginal2.error_identifier, ...
        directOriginal2.error_message);
    fprintf('逐字节相同ASCII文件名副本第一类状态：%s\n', original1.status);
    fprintf('逐字节相同ASCII文件名副本第二类状态：%s\n', original2.status);
    if original1.success
        fprintf('第一类原脚本逐对象比较：%s\n', ...
            pass_text(originalComparisonTable.comparison_pass(1)));
    else
        fprintf(2, '第一类原脚本失败：[%s] %s\n', ...
            original1.error_identifier, original1.error_message);
    end
    if original2.success
        fprintf('第二类原脚本逐对象比较：%s\n', ...
            pass_text(originalComparisonTable.comparison_pass(2)));
    else
        fprintf(2, '第二类原脚本失败：[%s] %s\n', ...
            original2.error_identifier, original2.error_message);
    end

    %% 5. 固定名称MAT与JSON汇总
    source_hashes = sourceTable; %#ok<NASGU>
    save(fullfile(outputDir, 'global_routes_matlab.mat'), ...
        'MRrt', 'CRrt', 'KRrt', 'frequency_hz_reference', ...
        'full_frequency_hz', 'full_imaginary_ratio', ...
        'reference_frequency_relative_error', 'division1', 'division2', ...
        'original1', 'original2', 'directOriginal1', 'directOriginal2', ...
        'matrixAuditTable', 'dimensionTable', ...
        'modalTable', 'originalComparisonTable', 'source_hashes', '-v7');

    summary = make_summary(referenceFile, sourceTable, full_frequency_hz, ...
        reference_frequency_relative_error, division1, division2, ...
        original1, original2, originalComparisonTable);
    summaryFile = fullfile(outputDir, 'global_route_summary.json');
    write_json(summaryFile, summary);

    %% 6. 生成产物哈希清单（不包含仍在写入的日志与清单自身）
    outputFiles = {
        fullfile(outputDir, 'global_routes_matlab.mat');
        summaryFile;
        fullfile(outputDir, 'global_source_hashes.csv');
        fullfile(outputDir, 'global_matrix_audit.csv');
        fullfile(outputDir, 'global_dimension_gates.csv');
        fullfile(outputDir, 'global_modal_frequencies.csv');
        fullfile(outputDir, 'global_reduced_matrix_entries.csv');
        fullfile(outputDir, 'global_recovery_matrices.csv');
        fullfile(outputDir, 'global_input_projection.csv');
        fullfile(outputDir, 'global_original_script_comparison.csv');
        transferByteCopies{1};
        transferByteCopies{2};
        mfilename('fullpath') + ".m"};
    hashTable = table(string(outputFiles), strings(numel(outputFiles),1), ...
        zeros(numel(outputFiles),1), ...
        'VariableNames', {'file','sha256','bytes'});
    for k = 1:height(hashTable)
        assert(isfile(hashTable.file(k)), '哈希目标缺失：%s', hashTable.file(k));
        hashTable.sha256(k) = sha256_file(hashTable.file(k));
        info = dir(hashTable.file(k));
        hashTable.bytes(k) = info.bytes;
    end
    writetable(hashTable, fullfile(outputDir, 'global_output_hashes.csv'), ...
        'Encoding', 'UTF-8');

    fprintf('内部矩阵/维数门槛：2/2 PASS。\n');
    fprintf('完整模型频率与参考MAT相对无穷范数误差：%.3e。\n', ...
        reference_frequency_relative_error);
    fprintf('第一类：Guyan=%d维，Craig-Bampton=%d维。\n', ...
        division1.n_master, division1.n_master+division1.r);
    fprintf('第二类：Guyan=%d维，Craig-Bampton=%d维。\n', ...
        division2.n_master, division2.n_master+division2.r);
    fprintf('主MAT SHA-256：%s\n', ...
        sha256_file(fullfile(outputDir, 'global_routes_matlab.mat')));
    fprintf('JSON SHA-256：%s\n', sha256_file(summaryFile));
    fprintf('15自由度两类全局缩聚复现完成：%s\n', string(datetime('now')));
catch ME
    fprintf(2, '15自由度全局缩聚复现失败：%s\n', ...
        getReport(ME, 'extended', 'hyperlinks', 'off'));
    rethrow(ME);
end
end

function D = build_division(M, C, K, divisionId, master, slave, forceMaskOrdered)
    order = [master, slave];
    assert(isequal(sort(order), 1:15) && numel(unique(order)) == 15, ...
        'Division %d 的 order 不是1:15的置换。', divisionId);
    nMaster = numel(master);
    nSlave = numel(slave);
    r = 3;
    Mo = M(order,order);
    Co = C(order,order);
    Ko = K(order,order);
    mm = 1:nMaster;
    ss = nMaster+1:15;
    Mmm = Mo(mm,mm); Mms = Mo(mm,ss);
    Cmm = Co(mm,mm); Cms = Co(mm,ss);
    Kmm = Ko(mm,mm); Kms = Ko(mm,ss);
    Ksm = Ko(ss,mm); Kss = Ko(ss,ss);
    Mss = Mo(ss,ss);
    staticRelation = -(Kss\Ksm);
    T = [eye(nMaster); staticRelation];

    MHistorical = Mmm - Mms*(Kss\Ksm);
    CHistorical = Cmm - Cms*(Kss\Ksm);
    KHistorical = Kmm - Kms*(Kss\Ksm);
    MProjected = T'*Mo*T;
    CProjected = T'*Co*T;
    KProjected = T'*Ko*T;

    [phiRaw, lambdaMatrixRaw] = eig(Kss, Mss);
    lambdaRaw = real(diag(lambdaMatrixRaw));
    [lambdaSorted, sortIndex] = sort(lambdaRaw, 'ascend');
    phiSorted = real(phiRaw(:,sortIndex));
    fixedFrequencySortedHz = sqrt(lambdaSorted)/(2*pi);
    TcbRaw = [eye(nMaster), zeros(nMaster,r); ...
        staticRelation, real(phiRaw(:,1:r))];
    Tcb = [eye(nMaster), zeros(nMaster,r); ...
        staticRelation, phiSorted(:,1:r)];
    McbRaw = TcbRaw'*Mo*TcbRaw;
    CcbRaw = TcbRaw'*Co*TcbRaw;
    KcbRaw = TcbRaw'*Ko*TcbRaw;
    Mcb = Tcb'*Mo*Tcb;
    Ccb = Tcb'*Co*Tcb;
    Kcb = Tcb'*Ko*Tcb;

    Porder = eye(15);
    Porder = Porder(order,:);
    RgNatural = Porder'*T;
    RcbNatural = Porder'*Tcb;
    RcbRawNatural = Porder'*TcbRaw;
    SfloorNatural = eye(15);
    SfloorNatural = SfloorNatural([1,6,11],:);
    floorGuyan = SfloorNatural*RgNatural;
    floorCb = SfloorNatural*RcbNatural;
    floorCbRaw = SfloorNatural*RcbRawNatural;

    MfOrdered = diag(forceMaskOrdered .* Mo);
    inputFullNatural = Porder'*MfOrdered;
    inputGuyan = T'*MfOrdered;
    inputCb = Tcb'*MfOrdered;
    inputCbRaw = TcbRaw'*MfOrdered;

    D.division_id = divisionId;
    D.label = sprintf('第%d类划分', divisionId);
    D.master = master;
    D.slave = slave;
    D.order = order;
    D.n_master = nMaster;
    D.n_slave = nSlave;
    D.r = r;
    D.force_mask_ordered = forceMaskOrdered;
    D.Mo = Mo; D.Co = Co; D.Ko = Ko;
    D.Mss = Mss; D.Kss = Kss; D.Ksm = Ksm;
    D.static_relation = staticRelation;
    D.T = T;
    D.M_historical = MHistorical;
    D.C_historical = CHistorical;
    D.K_historical = KHistorical;
    D.M_projected = MProjected;
    D.C_projected = CProjected;
    D.K_projected = KProjected;
    D.fixed_interface_eigenvalues_raw = lambdaRaw;
    D.fixed_interface_phi_raw = real(phiRaw);
    D.fixed_interface_sort_index = sortIndex;
    D.fixed_interface_eigenvalues_sorted = lambdaSorted;
    D.fixed_interface_frequency_hz_sorted = fixedFrequencySortedHz;
    D.fixed_interface_phi_sorted = phiSorted;
    D.T_cb_raw = TcbRaw;
    D.M_cb_raw = McbRaw;
    D.C_cb_raw = CcbRaw;
    D.K_cb_raw = KcbRaw;
    D.T_cb = Tcb;
    D.M_cb = Mcb;
    D.C_cb = Ccb;
    D.K_cb = Kcb;
    D.P_order = Porder;
    D.R_guyan_natural = RgNatural;
    D.R_cb_natural = RcbNatural;
    D.R_cb_raw_natural = RcbRawNatural;
    D.S_floor_natural = SfloorNatural;
    D.floor_recovery_guyan = floorGuyan;
    D.floor_recovery_cb = floorCb;
    D.floor_recovery_cb_raw = floorCbRaw;
    D.Mf = MfOrdered;
    D.input_full_natural = inputFullNatural;
    D.input_guyan = inputGuyan;
    D.input_cb = inputCb;
    D.input_cb_raw = inputCbRaw;
end

function row = matrix_audit_row(D)
    expectedMaster = 7-D.division_id;
    expectedCb = expectedMaster+3;
    dimensionPass = isequal(size(D.T), [15,expectedMaster]) && ...
        isequal(size(D.T_cb), [15,expectedCb]) && ...
        rank(D.T) == expectedMaster && rank(D.T_cb) == expectedCb;
    staticResidual = norm(D.Ksm + D.Kss*D.static_relation, 'fro') / ...
        max(norm(D.Ksm, 'fro'), eps);
    fixedModeResidual = norm(D.Kss*D.fixed_interface_phi_sorted - ...
        D.Mss*D.fixed_interface_phi_sorted*diag( ...
        D.fixed_interface_eigenvalues_sorted), 'fro') / ...
        max(norm(D.Kss*D.fixed_interface_phi_sorted, 'fro'), eps);
    relativeM = relative_frobenius(D.M_historical, D.M_projected);
    relativeC = relative_frobenius(D.C_historical, D.C_projected);
    relativeK = relative_frobenius(D.K_historical, D.K_projected);
    symmetryHistoricalM = symmetry_residual(D.M_historical);
    symmetryHistoricalC = symmetry_residual(D.C_historical);
    symmetryHistoricalK = symmetry_residual(D.K_historical);
    symmetryProjectedM = symmetry_residual(D.M_projected);
    symmetryProjectedC = symmetry_residual(D.C_projected);
    symmetryProjectedK = symmetry_residual(D.K_projected);
    symmetryCbM = symmetry_residual(D.M_cb);
    symmetryCbC = symmetry_residual(D.C_cb);
    symmetryCbK = symmetry_residual(D.K_cb);
    minEigProjectedM = min(eig((D.M_projected+D.M_projected')/2));
    minEigProjectedK = min(eig((D.K_projected+D.K_projected')/2));
    permutationResidual = norm(D.P_order*D.P_order'-eye(15), 'fro');
    recoveryResidual = norm(D.P_order*D.R_guyan_natural-D.T, 'fro') + ...
        norm(D.P_order*D.R_cb_natural-D.T_cb, 'fro');
    naturalMask = zeros(1,15);
    naturalMask([1,6,11]) = 1;
    expectedFullInput = diag(naturalMask .* (D.P_order'*D.Mo*D.P_order));
    inputResidual = norm(D.input_full_natural-expectedFullInput) / ...
        max(norm(expectedFullInput), eps);
    internalPass = dimensionPass && staticResidual < 1e-12 && ...
        fixedModeResidual < 1e-10 && relativeK < 1e-12 && ...
        symmetryProjectedM < 1e-12 && symmetryProjectedC < 1e-12 && ...
        symmetryProjectedK < 1e-12 && symmetryCbM < 1e-12 && ...
        symmetryCbC < 1e-12 && symmetryCbK < 1e-12 && ...
        minEigProjectedM > 0 && minEigProjectedK > 0 && ...
        permutationResidual < 1e-12 && recoveryResidual < 1e-12 && ...
        inputResidual < 1e-12;
    row = table(D.division_id, D.n_master, D.n_slave, ...
        size(D.T,1), size(D.T,2), rank(D.T), ...
        size(D.T_cb,1), size(D.T_cb,2), rank(D.T_cb), ...
        staticResidual, fixedModeResidual, relativeM, relativeC, relativeK, ...
        symmetryHistoricalM, symmetryHistoricalC, symmetryHistoricalK, ...
        symmetryProjectedM, symmetryProjectedC, symmetryProjectedK, ...
        symmetryCbM, symmetryCbC, symmetryCbK, ...
        minEigProjectedM, minEigProjectedK, permutationResidual, ...
        recoveryResidual, inputResidual, dimensionPass, internalPass, ...
        'VariableNames', {'division','n_master','n_slave','T_rows','T_columns', ...
        'rank_T','T_cb_rows','T_cb_columns','rank_T_cb','static_residual', ...
        'fixed_interface_mode_residual','relative_M_historical_vs_projected', ...
        'relative_C_historical_vs_projected', ...
        'relative_K_historical_vs_projected', ...
        'symmetry_M_historical','symmetry_C_historical','symmetry_K_historical', ...
        'symmetry_M_projected','symmetry_C_projected','symmetry_K_projected', ...
        'symmetry_M_cb','symmetry_C_cb','symmetry_K_cb', ...
        'min_eigenvalue_M_projected','min_eigenvalue_K_projected', ...
        'permutation_residual','natural_recovery_residual','input_residual', ...
        'dimension_gate_pass','internal_gate_pass'});
end

function rows = dimension_rows(D)
    expectedGuyan = 7-D.division_id;
    expectedCb = expectedGuyan+3;
    route = ["完整15自由度"; "作者历史Guyan单边式"; ...
        "标准Guyan合同投影"; "确定性Craig-Bampton升序3模态"];
    reducedDof = [15; D.n_master; D.n_master; D.n_master+D.r];
    transformRows = [15; size(D.T,1); size(D.T,1); size(D.T_cb,1)];
    transformColumns = [15; size(D.T,2); size(D.T,2); size(D.T_cb,2)];
    stateDimension = 2*reducedDof;
    inputDimension = reducedDof;
    outputDimension = reducedDof;
    expectedDof = [15; expectedGuyan; expectedGuyan; expectedCb];
    dimensionGatePass = reducedDof == expectedDof & ...
        transformRows == 15 & transformColumns == expectedDof;
    rows = table(repmat(D.division_id,4,1), route, reducedDof, ...
        transformRows, transformColumns, stateDimension, inputDimension, ...
        outputDimension, expectedDof, dimensionGatePass, ...
        'VariableNames', {'division','route','reduced_dof','transform_rows', ...
        'transform_columns','state_dimension','input_dimension', ...
        'output_dimension','expected_reduced_dof','dimension_gate_pass'});
end

function rows = division_frequency_rows(D)
    [historicalHz, historicalImag] = natural_frequencies( ...
        D.M_historical, D.K_historical);
    [projectedHz, projectedImag] = natural_frequencies( ...
        D.M_projected, D.K_projected);
    [cbHz, cbImag] = natural_frequencies(D.M_cb, D.K_cb);
    [cbRawHz, cbRawImag] = natural_frequencies(D.M_cb_raw, D.K_cb_raw);
    rows = frequency_rows(D.division_id, '固定界面从自由度', ...
        'eig_raw_order', sqrt(D.fixed_interface_eigenvalues_raw)/(2*pi), 0);
    rows = [rows; frequency_rows(D.division_id, '固定界面从自由度', ...
        'eig_explicit_ascending', D.fixed_interface_frequency_hz_sorted, 0)];
    rows = [rows; frequency_rows(D.division_id, 'Guyan', ...
        'historical_single_sided', historicalHz, historicalImag)];
    rows = [rows; frequency_rows(D.division_id, 'Guyan', ...
        'projected_congruence', projectedHz, projectedImag)];
    rows = [rows; frequency_rows(D.division_id, 'Craig-Bampton', ...
        'raw_eig_first_3', cbRawHz, cbRawImag)];
    rows = [rows; frequency_rows(D.division_id, 'Craig-Bampton', ...
        'explicit_ascending_first_3', cbHz, cbImag)];
end

function rows = frequency_rows(division, model, route, frequencyHz, imaginaryRatio)
    frequencyHz = frequencyHz(:);
    n = numel(frequencyHz);
    rows = table(repmat(division,n,1), repmat(string(model),n,1), ...
        repmat(string(route),n,1), (1:n)', frequencyHz, ...
        repmat(imaginaryRatio,n,1), ...
        'VariableNames', {'division','model','route','mode_order', ...
        'frequency_hz','generalized_eigenvalue_imaginary_ratio'});
end

function rows = matrix_entry_rows(D)
    objects = {
        'historical_single_sided','M',D.M_historical;
        'historical_single_sided','C',D.C_historical;
        'historical_single_sided','K',D.K_historical;
        'projected_congruence','M',D.M_projected;
        'projected_congruence','C',D.C_projected;
        'projected_congruence','K',D.K_projected;
        'cb_raw_eig_first_3','M',D.M_cb_raw;
        'cb_raw_eig_first_3','C',D.C_cb_raw;
        'cb_raw_eig_first_3','K',D.K_cb_raw;
        'cb_explicit_ascending_first_3','M',D.M_cb;
        'cb_explicit_ascending_first_3','C',D.C_cb;
        'cb_explicit_ascending_first_3','K',D.K_cb};
    rows = table();
    for k = 1:size(objects,1)
        rows = append_rows(rows, long_matrix(D.division_id, ...
            objects{k,1}, objects{k,2}, objects{k,3}));
    end
end

function rows = recovery_rows(D)
    objects = {
        'P_order_natural_to_ordered',D.P_order;
        'T_guyan_ordered',D.T;
        'R_guyan_natural',D.R_guyan_natural;
        'T_cb_raw_ordered',D.T_cb_raw;
        'R_cb_raw_natural',D.R_cb_raw_natural;
        'T_cb_sorted_ordered',D.T_cb;
        'R_cb_sorted_natural',D.R_cb_natural;
        'S_floor_natural',D.S_floor_natural;
        'floor_recovery_guyan',D.floor_recovery_guyan;
        'floor_recovery_cb_raw',D.floor_recovery_cb_raw;
        'floor_recovery_cb_sorted',D.floor_recovery_cb};
    rows = table();
    for k = 1:size(objects,1)
        rows = append_rows(rows, long_matrix(D.division_id, ...
            'recovery_and_selection', objects{k,1}, objects{k,2}));
    end
end

function rows = input_projection_rows(D)
    routes = {'full_natural',D.input_full_natural; ...
        'guyan_T_transpose_Mf',D.input_guyan; ...
        'cb_raw_T_transpose_Mf',D.input_cb_raw; ...
        'cb_sorted_T_transpose_Mf',D.input_cb};
    rows = table();
    for k = 1:size(routes,1)
        values = routes{k,2}(:);
        newRows = table(repmat(D.division_id,numel(values),1), ...
            repmat(string(routes{k,1}),numel(values),1), ...
            (1:numel(values))', values, ...
            'VariableNames', {'division','route','coordinate_index','value'});
        rows = append_rows(rows, newRows);
    end
end

function rows = long_matrix(division, route, object, A)
    [rowIndex, columnIndex] = ndgrid(1:size(A,1), 1:size(A,2));
    n = numel(A);
    rows = table(repmat(division,n,1), repmat(string(route),n,1), ...
        repmat(string(object),n,1), rowIndex(:), columnIndex(:), A(:), ...
        'VariableNames', {'division','route','object','row','column','value'});
end

function result = run_original_transfer(parameterScript, transferScript, reference)
    result = struct();
    result.parameter_script = parameterScript;
    result.transfer_script = transferScript;
    result.status = "FAILED";
    result.success = false;
    result.error_identifier = "";
    result.error_message = "";
    result.error_report = "";
    result.parameter_relative_M = NaN;
    result.parameter_relative_C = NaN;
    result.parameter_relative_K = NaN;
    try
        run(parameterScript);
        result.parameter_relative_M = relative_frobenius(MRrt, reference.MRrt);
        result.parameter_relative_C = relative_frobenius(CRrt, reference.CRrt);
        result.parameter_relative_K = relative_frobenius(KRrt, reference.KRrt);
        assert(max([result.parameter_relative_M, result.parameter_relative_C, ...
            result.parameter_relative_K]) < 1e-12, ...
            '冻结PDmonicanshu与参考MAT矩阵不一致。');
        run(transferScript);
        required = {'T','T_cb','MRren','CRren','KRren', ...
            'MR_cb','CR_cb','KR_cb','Mf','omega','G_1','G_2','G_3'};
        for k = 1:numel(required)
            assert(exist(required{k}, 'var') == 1, ...
                '原转存脚本未生成变量：%s', required{k});
        end
        result.T = T;
        result.T_cb = T_cb;
        result.M_historical = MRren;
        result.C_historical = CRren;
        result.K_historical = KRren;
        result.M_cb = MR_cb;
        result.C_cb = CR_cb;
        result.K_cb = KR_cb;
        result.Mf = Mf;
        result.omega = omega;
        result.G_1_state_dimension = size(G_1.A,1);
        result.G_1_input_dimension = size(G_1.B,2);
        result.G_1_output_dimension = size(G_1.C,1);
        result.G_2_state_dimension = size(G_2.A,1);
        result.G_2_input_dimension = size(G_2.B,2);
        result.G_2_output_dimension = size(G_2.C,1);
        result.G_3_state_dimension = size(G_3.A,1);
        result.G_3_input_dimension = size(G_3.B,2);
        result.G_3_output_dimension = size(G_3.C,1);
        result.status = "SUCCESS";
        result.success = true;
    catch ME
        result.error_identifier = string(ME.identifier);
        result.error_message = string(ME.message);
        result.error_report = string(getReport(ME, 'extended', 'hyperlinks', 'off'));
    end
end

function row = compare_original_script(D, O)
    values = nan(1,10);
    comparisonPass = false;
    originalGuyanDof = NaN;
    originalCbDof = NaN;
    if O.success
        values = [relative_frobenius(O.T,D.T), ...
            relative_frobenius(O.M_historical,D.M_historical), ...
            relative_frobenius(O.C_historical,D.C_historical), ...
            relative_frobenius(O.K_historical,D.K_historical), ...
            relative_frobenius(O.T_cb,D.T_cb_raw), ...
            relative_frobenius(O.M_cb,D.M_cb_raw), ...
            relative_frobenius(O.C_cb,D.C_cb_raw), ...
            relative_frobenius(O.K_cb,D.K_cb_raw), ...
            relative_frobenius(O.Mf,D.Mf), ...
            norm(O.omega(:)-sqrt(D.fixed_interface_eigenvalues_raw(:))) / ...
            max(norm(sqrt(D.fixed_interface_eigenvalues_raw(:))),eps)];
        comparisonPass = max(values) < 1e-12;
        originalGuyanDof = size(O.T,2);
        originalCbDof = size(O.T_cb,2);
    end
    row = table(D.division_id, string(O.direct_filename_status), ...
        string(O.direct_filename_error_identifier), ...
        string(O.direct_filename_error_message), ...
        string(O.execution_mode), O.bytecopy_sha256_match, ...
        string(O.status), O.success, ...
        string(O.error_identifier), string(O.error_message), ...
        O.parameter_relative_M, O.parameter_relative_C, O.parameter_relative_K, ...
        originalGuyanDof, originalCbDof, ...
        values(1), values(2), values(3), values(4), values(5), ...
        values(6), values(7), values(8), values(9), values(10), comparisonPass, ...
        'VariableNames', {'division','direct_filename_status', ...
        'direct_filename_error_identifier','direct_filename_error_message', ...
        'execution_mode','bytecopy_sha256_match','script_status','script_success', ...
        'error_identifier','error_message','parameter_relative_M', ...
        'parameter_relative_C','parameter_relative_K','original_guyan_dof', ...
        'original_cb_dof','relative_T','relative_M_historical', ...
        'relative_C_historical','relative_K_historical','relative_T_cb_raw', ...
        'relative_M_cb_raw','relative_C_cb_raw','relative_K_cb_raw', ...
        'relative_Mf','relative_omega_raw','comparison_pass'});
end

function summary = make_summary(referenceFile, sourceTable, fullFrequencyHz, ...
        frequencyError, D1, D2, O1, O2, comparisonTable)
    summary = struct();
    summary.schema = 'board17_global_routes_v1';
    summary.created_at = char(datetime('now', ...
        'Format', 'yyyy-MM-dd HH:mm:ss Z'));
    summary.matlab_version = version;
    summary.reference_file = referenceFile;
    summary.reference_sha256 = char(sourceTable.sha256(1));
    summary.full_frequency_hz = fullFrequencyHz(:)';
    summary.reference_frequency_relative_error = frequencyError;
    summary.route_labels = struct( ...
        'historical_guyan', '作者转存脚本单边 Mmm-Mms*(Kss\\Ksm)', ...
        'projected_guyan', '标准合同投影 T''*A*T', ...
        'raw_cb', '作者原脚本 eig 返回顺序的前3列', ...
        'sorted_cb', '显式按固定界面特征值升序后的前3列');
    summary.division1 = summary_division(D1, O1, comparisonTable(1,:));
    summary.division2 = summary_division(D2, O2, comparisonTable(2,:));
    summary.internal_gate_pass = true;
end

function S = summary_division(D, O, comparisonRow)
    S = struct();
    S.label = D.label;
    S.master = D.master;
    S.slave = D.slave;
    S.order = D.order;
    S.guyan_dimension = D.n_master;
    S.cb_dimension = D.n_master+D.r;
    S.fixed_interface_modes_retained = D.r;
    S.relative_M_historical_vs_projected = ...
        relative_frobenius(D.M_historical,D.M_projected);
    S.relative_C_historical_vs_projected = ...
        relative_frobenius(D.C_historical,D.C_projected);
    S.relative_K_historical_vs_projected = ...
        relative_frobenius(D.K_historical,D.K_projected);
    S.original_transfer_status = char(O.status);
    S.direct_chinese_filename_status = char(O.direct_filename_status);
    S.direct_chinese_filename_error_identifier = ...
        char(O.direct_filename_error_identifier);
    S.direct_chinese_filename_error_message = ...
        char(O.direct_filename_error_message);
    S.execution_mode = char(O.execution_mode);
    S.bytecopy_sha256_match = O.bytecopy_sha256_match;
    S.original_transfer_error_identifier = char(O.error_identifier);
    S.original_transfer_error_message = char(O.error_message);
    S.original_transfer_comparison_pass = comparisonRow.comparison_pass;
end

function [frequencyHz, imaginaryRatio] = natural_frequencies(M, K)
    lambda = eig(K,M);
    imaginaryRatio = max(abs(imag(lambda))) / max(max(abs(lambda)), eps);
    realLambda = sort(real(lambda), 'ascend');
    tolerance = 1e-10*max(max(abs(realLambda)),1);
    assert(imaginaryRatio < 1e-10, ...
        '广义特征值存在显著虚部，比值 %.3e。', imaginaryRatio);
    positive = realLambda(realLambda > tolerance);
    assert(~isempty(positive), '没有正广义特征值。');
    frequencyHz = sqrt(positive)/(2*pi);
end

function value = relative_frobenius(A, B)
    value = norm(A-B,'fro') / max(norm(B,'fro'),eps);
end

function value = symmetry_residual(A)
    value = norm(A-A','fro') / max(norm(A,'fro'),eps);
end

function combined = append_rows(existing, newRows)
    if width(existing) == 0
        combined = newRows;
    else
        combined = [existing; newRows];
    end
end

function write_json(path, value)
    text = jsonencode(value, 'PrettyPrint', true);
    fileId = fopen(path, 'w', 'n', 'UTF-8');
    assert(fileId ~= -1, '无法写入JSON：%s', path);
    cleanup = onCleanup(@() fclose(fileId)); %#ok<NASGU>
    fprintf(fileId, '%s\n', text);
end

function digestText = sha256_file(filePath)
    digestEngine = java.security.MessageDigest.getInstance('SHA-256');
    javaFile = java.io.File(char(filePath));
    fileBytes = java.nio.file.Files.readAllBytes(javaFile.toPath());
    digestEngine.update(fileBytes);
    digestBytes = typecast(digestEngine.digest(), 'uint8');
    digestText = string(upper(reshape(dec2hex(digestBytes,2).',1,[])));
end

function text = pass_text(value)
    if value
        text = 'PASS';
    else
        text = 'FAIL';
    end
end
