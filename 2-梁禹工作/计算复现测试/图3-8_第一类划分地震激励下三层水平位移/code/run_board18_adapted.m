%% 板块18隔离再生第3章真实仿真数据
% 从干净 MATLAB 会话运行本脚本。脚本只读取板块18冻结输入，并按
% BOARD18_RUN_ID=run1/run2 写入互不覆盖的派生目录。
% 数值链：PDmonicanshu.m -> 原始 Guyan/CB 变换 -> 原始状态空间 A/B ->
% Simulink ode4 (dt=1/1024 s) -> 三层物理坐标恢复。

clearvars;
close all force;
clc;

codeDir = fileparts(mfilename('fullpath'));
boardDir = fileparts(codeDir);
runId = getenv('BOARD18_RUN_ID');
assert(any(strcmp(runId, {'run1','run2'})), ...
    'BOARD18_RUN_ID必须是run1或run2，实际为：%s', runId);
chapterDir = fullfile(boardDir, 'outputs', ['adapted_' runId]);
sourceDir = fullfile(boardDir, 'input', 'author_source');
modelSourceDir = fullfile(sourceDir, '模型与参数原件');
dataDir = fullfile(chapterDir, '输入数据');
validationDir = fullfile(chapterDir, '验证记录');
modelCopyDir = fullfile(chapterDir, '模型副本');
groundDir = fullfile(sourceDir, '辅助来源_地震记录');

if ~exist(dataDir, 'dir'), mkdir(dataDir); end
if ~exist(validationDir, 'dir'), mkdir(validationDir); end
if ~exist(modelCopyDir, 'dir'), mkdir(modelCopyDir); end

logFile = fullfile(validationDir, '再生第3章真实仿真数据_日志.txt');
if exist(logFile, 'file'), delete(logFile); end
diary(logFile);
cleanupDiary = onCleanup(@() diary('off')); %#ok<NASGU>

fprintf('第3章真实仿真数据再生开始：%s\n', string(datetime('now')));
fprintf('MATLAB: %s\n', version);
fprintf('codeDir：%s\n', codeDir);
fprintf('BOARD18_RUN_ID：%s\n', runId);
fprintf('冻结输入根：%s\n', sourceDir);
fprintf('隔离输出根：%s\n', chapterDir);

try
    %% 1. 读取原结构参数和原始 El Centro 记录
    paramScript = fullfile(modelSourceDir, 'PDmonicanshu.m');
    eqFile = fullfile(modelSourceDir, 'EQ.mat');
    assert(isfile(paramScript), '缺少原paramScript：%s', paramScript);
    assert(isfile(eqFile), '缺少原地震数据：%s', eqFile);
    run(paramScript);
    load(eqFile, 'ElCentroAccel', 'EQ_intensity', 'EQ_sw');
    assert(EQ_sw == 1, '原模型 EQ_sw 不是 El Centro 分支（期望 1，实际 %g）。', EQ_sw);
    assert(size(ElCentroAccel,1) == 2, 'ElCentroAccel 应为 2xN：[时间; 加速度]。');

    dt = 1/1024;
    stopTime = 40;
    methodNames = {'原结构','Guyan','Craig-Bampton'};
    floorNames = {'一层','二层','三层'};

    %% 2. 在本章内准备模型副本（不改原工程）
    % 论文正文映射：第一类保留物理水平DOF [1,6]，组合主DOF含
    % [1,6,11,4,9,14]，对应 lvxvjie_guyan_2.slx；第二类仅保留
    % 物理水平DOF [1,11]（psi6为从自由度），对应 lvxvjie_guyan.slx。
    div1ModelSource = fullfile(modelSourceDir, 'lvxvjie_guyan_2.slx');
    div2ModelSource = fullfile(modelSourceDir, 'lvxvjie_guyan.slx');
    assert(isfile(div1ModelSource), '缺少div1划分原模型：%s', div1ModelSource);
    assert(isfile(div2ModelSource), '缺少div2划分原模型：%s', div2ModelSource);
    % Simulink 模型基名必须是合法 MATLAB 标识符，因此副本使用 ASCII 基名；
    % 中文含义记录在本章来源说明和交付清单中。
    div1ModelFile = fullfile(modelCopyDir, 'division1_repro.slx');
    div2ModelFile = fullfile(modelCopyDir, 'division2_repro.slx');
    prepare_model_copy(div1ModelSource, div1ModelFile, false, groundDir);
    prepare_model_copy(div2ModelSource, div2ModelFile, true, groundDir);

    %% 3. 构造三类真实激励
    fineTime = (0:dt:stopTime)';
    unitStep = double(fineTime >= 1);
    chirpAcceleration = sin(2*pi*0.1*fineTime + pi*(10-0.1)/stopTime*fineTime.^2);
    eqTime = ElCentroAccel(1,:)';
    eqAcceleration = EQ_intensity * ElCentroAccel(2,:)';
    validMask = eqTime <= stopTime;
    eqTime = eqTime(validMask);
    eqAcceleration = eqAcceleration(validMask);

    save(fullfile(dataDir, '三类真实激励.mat'), 'fineTime', 'unitStep', ...
        'chirpAcceleration', 'eqTime', 'eqAcceleration', 'dt', 'stopTime', ...
        'EQ_intensity', '-v7');
    writetable(table(fineTime, unitStep, chirpAcceleration, ...
        'VariableNames', {'时间_s','unitStep','chirpAcceleration_m每s2'}), ...
        fullfile(dataDir, '单位与Chirp激励.csv'));
    writetable(table(eqTime, eqAcceleration, ...
        'VariableNames', {'时间_s','ElCentro加速度_m每s2_缩放0点4'}), ...
        fullfile(dataDir, 'ElCentro地震激励.csv'));

    %% 4. unitStep：原结构三层响应
    div1 = build_reduction_models(MRrt, CRrt, KRrt, 1);
    assert(numel(div1.master) == 6 && size(div1.G_2.C,1) == 6 && size(div1.G_3.C,1) == 9, ...
        '第一类降阶宽度必须为 Guyan=6、Craig-Bampton=9。');
    assign_model_variables(div1, MRrt);
    unitOut = run_one_simulation(div1ModelFile, [fineTime unitStep], false, dt, stopTime);
    unitData = make_response_struct(unitOut, '单位阶跃', '第一类划分模型中的原结构列');
    save_response(unitData, fullfile(dataDir, '单位激励_原结构三层响应'));

    %% 5. El Centro：div1与div2划分
    assign_model_variables(div1, MRrt);
    div1EqOut = run_one_simulation(div1ModelFile, [eqTime eqAcceleration], true, dt, stopTime);
    div1EqData = make_response_struct(div1EqOut, 'El Centro 1940 NS，原记录乘0.40', '第一类子结构划分');
    save_response(div1EqData, fullfile(dataDir, '第一类划分_ElCentro地震响应'));

    div2 = build_reduction_models(MRrt, CRrt, KRrt, 2);
    assert(numel(div2.master) == 5 && size(div2.G_2.C,1) == 5 && size(div2.G_3.C,1) == 8, ...
        '第二类降阶宽度必须为 Guyan=5、Craig-Bampton=8。');
    assign_model_variables(div2, MRrt);
    div2EqOut = run_one_simulation(div2ModelFile, [eqTime eqAcceleration], true, dt, stopTime);
    div2EqData = make_response_struct(div2EqOut, 'El Centro 1940 NS，原记录乘0.40', '第二类子结构划分');
    save_response(div2EqData, fullfile(dataDir, '第二类划分_ElCentro地震响应'));

    %% 6. 0.1--10 Hz Chirp：div1与div2划分
    assign_model_variables(div1, MRrt);
    div1ChirpOut = run_one_simulation(div1ModelFile, [fineTime chirpAcceleration], true, dt, stopTime);
    div1ChirpData = make_response_struct(div1ChirpOut, '0.1--10 Hz线性Chirp，40 s', '第一类子结构划分');
    save_response(div1ChirpData, fullfile(dataDir, '第一类划分_Chirp响应'));

    assign_model_variables(div2, MRrt);
    div2ChirpOut = run_one_simulation(div2ModelFile, [fineTime chirpAcceleration], true, dt, stopTime);
    div2ChirpData = make_response_struct(div2ChirpOut, '0.1--10 Hz线性Chirp，40 s', '第二类子结构划分');
    save_response(div2ChirpData, fullfile(dataDir, '第二类划分_Chirp响应'));

    %% 7. 数值统计与硬门槛
    dataSets = {unitData, div1EqData, div2EqData, div1ChirpData, div2ChirpData};
    dataNames = {'单位激励','第一类ElCentro','第二类ElCentro','第一类Chirp','第二类Chirp'};
    statsTable = table();
    for d = 1:numel(dataSets)
        S = dataSets{d};
        assert(all(isfinite(S.time_s)), '%s 时间包含 NaN/Inf。', dataNames{d});
        assert(all(diff(S.time_s) > 0), '%s 时间不是严格递增。', dataNames{d});
        for f = 1:3
            for m = 1:3
                y = S.response_mm(:,f,m);
                assert(all(isfinite(y)), '%s %s %s 包含 NaN/Inf。', dataNames{d}, floorNames{f}, methodNames{m});
                newRow = table(string(dataNames{d}), string(floorNames{f}), string(methodNames{m}), ...
                    max(abs(y)), sqrt(mean(y.^2)), y(end), ...
                    'VariableNames', {'dataSets','楼层','方法','绝对峰值_mm','RMS_mm','末值_mm'});
                statsTable = [statsTable; newRow]; %#ok<AGROW>
            end
        end
    end
    writetable(statsTable, fullfile(validationDir, '第3章仿真响应数值统计.csv'));
    generatedHashFile = write_generated_data_hash_manifest(chapterDir, dataDir, validationDir);

    % 局部窗必须有足够样本；图3-15必须来自 Chirp 数据而不是地震数据。
    assert(nnz(div1EqData.time_s >= 10 & div1EqData.time_s <= 11) > 900);
    assert(nnz(div1EqData.time_s >= 21.5 & div1EqData.time_s <= 22.5) > 900);
    assert(nnz(div2ChirpData.time_s >= 13 & div2ChirpData.time_s <= 14) > 900);
    assert(nnz(div2ChirpData.time_s >= 38 & div2ChirpData.time_s <= 38.3) > 250);

    fprintf('方法列顺序：1=原结构，2=Guyan，3=Craig-Bampton。\n');
    fprintf('楼层输出顺序：simout3=一层，simout=二层，simout1=三层（适配后）。\n');
    fprintf('映射审计：第一类=lvxvjie_guyan_2.slx/组合主DOF[1,6,11,4,9,14]；第二类=lvxvjie_guyan.slx/组合主DOF[1,11,4,9,14]。\n');
    fprintf('第二类划分原模型断开的三层 Guyan/CB 输出已通过原 T/T_cb 恢复并补连。\n');
    fprintf('5组响应数据与统计均通过 NaN/Inf、时间单调性及局部窗样本检查。\n');
    fprintf('已刷新14项最终生成数据SHA-256：%s\n', generatedHashFile);
    fprintf('第3章真实仿真数据再生完成：%s\n', string(datetime('now')));
catch ME
    fprintf(2, '再生失败：%s\n', getReport(ME, 'extended', 'hyperlinks', 'off'));
    rethrow(ME);
end

%% 局部函数
function prepare_model_copy(sourceFile, targetFile, needsThirdFloorRepair, groundDir)
    if bdIsLoaded('division1_repro'), close_system('division1_repro', 0); end
    if bdIsLoaded('division2_repro'), close_system('division2_repro', 0); end
    copyfile(sourceFile, targetFile, 'f');
    [~, modelName] = fileparts(targetFile);
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
    for k = 1:numel(gainNames)
        block = [modelName '/' gainNames{k}];
        ports = get_param(block, 'PortHandles');
        lineHandle = get_param(ports.Inport, 'Line');
        if lineHandle ~= -1, delete_line(lineHandle); end
        add_line(modelName, inputPort.Outport, ports.Inport, 'autorouting', 'on');
    end

    % 原地震子系统已被本章 From Workspace 输入旁路，但 Simulink 仍会编译其
    % From File 块。将作者电脑绝对路径改为本章保存的同名原记录；拓扑不变。
    fromFileBlocks = find_system(modelName, 'LookUnderMasks', 'all', ...
        'FollowLinks', 'on', 'BlockType', 'FromFile');
    for k = 1:numel(fromFileBlocks)
        oldFile = get_param(fromFileBlocks{k}, 'FileName');
        [~, baseName, ext] = fileparts(oldFile);
        localFile = fullfile(groundDir, [baseName ext]);
        assert(isfile(localFile), '缺少本地地震辅助来源：%s', localFile);
        set_param(fromFileBlocks{k}, 'FileName', localFile);
    end

    stateBlocks = {'数值子结构1','数值子结构2','数值子结构3'};
    cVars = {'output_matrix_original','output_matrix_guyan','output_matrix_cb'};
    dVars = {'feedthrough_matrix_original','feedthrough_matrix_guyan','feedthrough_matrix_cb'};
    selectors = {'Selector3','Selector5','Selector9'};
    for k = 1:3
        set_param([modelName '/' stateBlocks{k}], 'C', cVars{k}, 'D', dVars{k});
        set_param([modelName '/' selectors{k}], 'Indices', '[1 2 3]', 'InputPortWidth', '3');
    end

    if needsThirdFloorRepair
        % 原模型保存时 Mux6 的第2/3输入未连接；补齐 Guyan 与 CB 的三层端口。
        set_param([modelName '/Demux4'], 'Outputs', '3');
        set_param([modelName '/Demux5'], 'Outputs', '3');
        % 动态增加 Demux 端口后必须保存并重载，才能获得有效的新端口句柄。
        save_system(modelName, targetFile);
        close_system(modelName, 0);
        load_system(targetFile);
        demuxNames = {'Demux4','Demux5'};
        for k = 1:2
            demuxPorts = get_param([modelName '/' demuxNames{k}], 'PortHandles');
            muxPorts = get_param([modelName '/Mux6'], 'PortHandles');
            oldLine = get_param(muxPorts.Inport(k+1), 'Line');
            if oldLine ~= -1, delete_line(oldLine); end
            add_line(modelName, demuxPorts.Outport(3), muxPorts.Inport(k+1), 'autorouting', 'on');
        end
    end
    set_param(modelName, 'StopTime', '40', 'Solver', 'ode4', 'FixedStep', 'dt');
    save_system(modelName, targetFile);
    close_system(modelName, 0);

    % 持久化后重载并验证第一类三层输出补线，禁止用补零替代缺失方法。
    if needsThirdFloorRepair
        load_system(targetFile);
        muxPorts = get_param([modelName '/Mux6'], 'PortHandles');
        expectedBlocks = {'Demux3','Demux4','Demux5'};
        for k = 1:3
            lineHandle = get_param(muxPorts.Inport(k), 'Line');
            assert(lineHandle ~= -1, 'Mux6 输入端口 %d 在保存重载后仍未连接。', k);
            srcBlock = get_param(lineHandle, 'SrcBlockHandle');
            srcPort = get_param(lineHandle, 'SrcPortHandle');
            expectedBlock = getSimulinkBlockHandle([modelName '/' expectedBlocks{k}]);
            expectedPorts = get_param([modelName '/' expectedBlocks{k}], 'PortHandles');
            assert(srcBlock == expectedBlock && srcPort == expectedPorts.Outport(3), ...
                'Mux6 输入端口 %d 的来源不是 %s/3。', k, expectedBlocks{k});
            fprintf('端口验证：Mux6/%d <- %s/3，Line=%g。\n', k, expectedBlocks{k}, lineHandle);
        end
        close_system(modelName, 0);
    end
end

function R = build_reduction_models(M, C, K, division)
    if division == 1
        master = [1,6,11,4,9,14];
        slave = [2,3,5,7,8,10,12,13,15];
        forceMask = [1,1,1,0,0,0,0,0,0,0,0,0,0,0,0];
    elseif division == 2
        master = [1,11,4,9,14];
        slave = [6,2,3,5,7,8,10,12,13,15];
        forceMask = [1,1,0,0,0,1,0,0,0,0,0,0,0,0,0];
    else
        error('未知子结构划分编号：%g', division);
    end
    order = [master, slave];
    Mo = M(order,order); Co = C(order,order); Ko = K(order,order);
    nm = numel(master);
    Mmm = Mo(1:nm,1:nm); Mms = Mo(1:nm,nm+1:end);
    Cmm = Co(1:nm,1:nm); Cms = Co(1:nm,nm+1:end);
    Kmm = Ko(1:nm,1:nm); Kms = Ko(1:nm,nm+1:end);
    Ksm = Ko(nm+1:end,1:nm); Kss = Ko(nm+1:end,nm+1:end);
    Mss = Mo(nm+1:end,nm+1:end);

    T = [eye(nm); -Kss\Ksm];
    Mg = Mmm - Mms*(Kss\Ksm);
    Cg = Cmm - Cms*(Kss\Ksm);
    Kg = Kmm - Kms*(Kss\Ksm);

    [phi, lambda] = eig(Kss, Mss);
    [~, idx] = sort(real(diag(lambda)), 'ascend');
    phi = real(phi(:,idx));
    r = 3;
    Tcb = [eye(nm), zeros(nm,r); -Kss\Ksm, phi(:,1:r)];
    Mcb = Tcb'*Mo*Tcb; Ccb = Tcb'*Co*Tcb; Kcb = Tcb'*Ko*Tcb;

    G1 = second_order_ss(M, C, K);
    G2 = second_order_ss(Mg, Cg, Kg);
    G3 = second_order_ss(Mcb, Ccb, Kcb);

    floorOriginal = [1,6,11];
    floorRowsOrdered = arrayfun(@(q)find(order==q,1), floorOriginal);
    P = eye(15); P = P(floorRowsOrdered,:);
    Cfloor1 = [eye(15), zeros(15)]; Cfloor1 = Cfloor1(floorOriginal,:);
    Cfloor2 = [P*T, zeros(3,size(T,2))];
    Cfloor3 = [P*Tcb, zeros(3,size(Tcb,2))];

    Mforce = Mo;
    Mf = diag(forceMask .* Mforce);
    R.G_1 = G1; R.G_2 = G2; R.G_3 = G3;
    R.T = T; R.T_cb = Tcb; R.Mf = Mf;
    R.Cfloor1 = Cfloor1; R.Cfloor2 = Cfloor2; R.Cfloor3 = Cfloor3;
    R.Dfloor1 = zeros(3,size(G1.B,2));
    R.Dfloor2 = zeros(3,size(G2.B,2));
    R.Dfloor3 = zeros(3,size(G3.B,2));
    R.master = master; R.slave = slave; R.order = order;
end

function G = second_order_ss(M, C, K)
    n = size(M,1);
    A = [zeros(n), eye(n); -M\K, -M\C];
    B = [zeros(n); M\eye(n)];
    Cq = [eye(n), zeros(n)];
    D = zeros(n,n);
    G = ss(A,B,Cq,D);
end

function assign_model_variables(R, MRrt)
    names = {'G_1','G_2','G_3','T','T_cb','Mf', ...
        'output_matrix_original','output_matrix_guyan','output_matrix_cb', ...
        'feedthrough_matrix_original','feedthrough_matrix_guyan','feedthrough_matrix_cb','MRrt'};
    vals = {R.G_1,R.G_2,R.G_3,R.T,R.T_cb,R.Mf, ...
        R.Cfloor1,R.Cfloor2,R.Cfloor3,R.Dfloor1,R.Dfloor2,R.Dfloor3,MRrt};
    for k = 1:numel(names), assignin('base', names{k}, vals{k}); end
end

function out = run_one_simulation(modelFile, excitation, interpolate, dt, stopTime)
    [~, modelName] = fileparts(modelFile);
    load_system(modelFile);
    assignin('base', 'excitation_input', excitation);
    assignin('base', 'dt', dt);
    if interpolate
        interpolateText = 'on';
    else
        interpolateText = 'off';
    end
    set_param([modelName '/可复现excitation_input'], 'Interpolate', interpolateText);
    set_param(modelName, 'StopTime', num2str(stopTime,17));
    simOut = sim(modelName, 'ReturnWorkspaceOutputs', 'on');
    out.floor1 = simOut.simout3;
    out.floor2 = simOut.simout;
    out.floor3 = simOut.simout1;
    close_system(modelName, 0);
end

function S = make_response_struct(out, excitationDescription, divisionDescription)
    t = out.floor1.Time(:);
    assert(max(abs(t-out.floor2.Time(:))) < 1e-12 && max(abs(t-out.floor3.Time(:))) < 1e-12, ...
        '三个楼层输出时间轴不一致。');
    D1 = squeeze(out.floor1.Data); D2 = squeeze(out.floor2.Data); D3 = squeeze(out.floor3.Data);
    assert(size(D1,2)==3 && size(D2,2)==3 && size(D3,2)==3, '楼层输出必须各含三种方法。');
    S.time_s = t;
    % 原模型三个 To Workspace 前均已有 Gain=1e3，因此 simout 数据单位已经是 mm。
    S.response_mm = cat(2, reshape(D1,[],1,3), reshape(D2,[],1,3), reshape(D3,[],1,3));
    S.method_order = {'Original','Guyan','Craig-Bampton'};
    S.floor_order = {'Floor 1','Floor 2','Floor 3'};
    S.excitation = excitationDescription;
    S.division = divisionDescription;
end

function save_response(S, basePath)
    time_s = S.time_s; response_mm = S.response_mm; %#ok<NASGU>
    method_order = S.method_order; floor_order = S.floor_order; %#ok<NASGU>
    excitation = S.excitation; division = S.division; %#ok<NASGU>
    save([basePath '.mat'], 'time_s', 'response_mm', 'method_order', 'floor_order', ...
        'excitation', 'division', '-v7');
    T = table(time_s, ...
        response_mm(:,1,1),response_mm(:,1,2),response_mm(:,1,3), ...
        response_mm(:,2,1),response_mm(:,2,2),response_mm(:,2,3), ...
        response_mm(:,3,1),response_mm(:,3,2),response_mm(:,3,3), ...
        'VariableNames', {'时间_s','原结构_一层_mm','Guyan_一层_mm','CraigBampton_一层_mm', ...
        '原结构_二层_mm','Guyan_二层_mm','CraigBampton_二层_mm', ...
        '原结构_三层_mm','Guyan_三层_mm','CraigBampton_三层_mm'});
    writetable(T, [basePath '.csv']);
end

function manifestPath = write_generated_data_hash_manifest(chapterDir, dataDir, validationDir)
    % 每次真实仿真重跑后重建清单，避免MAT/CSV变更而旧哈希仍被误认为有效。
    relativePaths = {
        '输入数据/ElCentro地震激励.csv';
        '输入数据/单位激励_原结构三层响应.csv';
        '输入数据/单位激励_原结构三层响应.mat';
        '输入数据/单位与Chirp激励.csv';
        '输入数据/第二类划分_Chirp响应.csv';
        '输入数据/第二类划分_Chirp响应.mat';
        '输入数据/第二类划分_ElCentro地震响应.csv';
        '输入数据/第二类划分_ElCentro地震响应.mat';
        '输入数据/第一类划分_Chirp响应.csv';
        '输入数据/第一类划分_Chirp响应.mat';
        '输入数据/第一类划分_ElCentro地震响应.csv';
        '输入数据/第一类划分_ElCentro地震响应.mat';
        '输入数据/三类真实激励.mat';
        '验证记录/第3章仿真响应数值统计.csv'};
    purposes = {
        'CSV可读副本'; 'CSV可读副本'; '真实仿真或激励MAT'; 'CSV可读副本';
        'CSV可读副本'; '真实仿真或激励MAT'; 'CSV可读副本'; '真实仿真或激励MAT';
        'CSV可读副本'; '真实仿真或激励MAT'; 'CSV可读副本'; '真实仿真或激励MAT';
        '真实仿真或激励MAT'; '数值统计'};
    n = numel(relativePaths);
    hashes = strings(n,1); bytes = zeros(n,1); modified = strings(n,1);
    for k = 1:n
        filePath = fullfile(chapterDir, strrep(relativePaths{k}, '/', filesep));
        assert(isfile(filePath), '生成数据哈希目标缺失：%s', filePath);
        hashes(k) = sha256_file(filePath);
        info = dir(filePath);
        bytes(k) = info.bytes;
        modified(k) = string(datetime(info.datenum, 'ConvertFrom', 'datenum', ...
            'Format', 'yyyy-MM-dd HH:mm:ss'));
    end
    manifest = table(string(relativePaths), hashes, bytes, modified, string(purposes), ...
        'VariableNames', {'相对章节路径','SHA256','字节数','最后修改时间','用途'});
    manifestPath = fullfile(validationDir, '第3章生成数据_SHA256.csv');
    writetable(manifest, manifestPath, 'Encoding', 'UTF-8');
    assert(height(manifest) == 14, '生成数据哈希清单必须恰有14项。');
end

function digestText = sha256_file(filePath)
    digestEngine = java.security.MessageDigest.getInstance('SHA-256');
    javaFile = java.io.File(filePath);
    fileBytes = java.nio.file.Files.readAllBytes(javaFile.toPath());
    digestEngine.update(fileBytes);
    digestBytes = typecast(digestEngine.digest(), 'uint8');
    digestText = upper(reshape(dec2hex(digestBytes,2).',1,[]));
end
