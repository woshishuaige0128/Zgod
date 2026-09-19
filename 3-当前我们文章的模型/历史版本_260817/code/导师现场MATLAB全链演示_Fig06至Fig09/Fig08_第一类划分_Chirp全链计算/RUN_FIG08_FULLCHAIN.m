%% Fig.6--Fig.9 现场全计算链演示入口（本文件按文件名自动识别具体图号）
% 使用方法：
% 1. 在 MATLAB “当前文件夹”中进入本脚本所在文件夹；
% 2. 打开 RUN_FIGxx_FULLCHAIN.m；
% 3. 点击编辑器上方绿色“运行”按钮，或按 F5；
% 4. 也可把光标放在每个 %% 章节内，按 Ctrl+Enter 逐段讲解。
%
% 重要证据边界：
% - 计算从 PDmonicanshu.m 生成的 15 自由度 M/C/K 开始；
% - 当前结果 CSV 只在最后“末端验收”章节读取，不参与结构、降阶、
%   状态空间、激励或 Simulink 计算；
% - 原始 SLX 不直接修改。脚本复制一份运行模型，再修复作者电脑绝对路径；
% - 第二类划分还会在运行副本中补齐原模型遗漏的三层 Guyan/CB 输出线；
% - 因此本演示属于“现存代码/必要适配路线的计算级复现”，不冒充作者
%   当年的历史工作区数组，也不声称原始保存状态的 SLX 可以直接运行。

clearvars;
close all force;
clc;

scriptPath = mfilename('fullpath');
assert(~isempty(scriptPath), '无法确定当前脚本的位置。请保存文件后再运行。');
caseDir = fileparts(scriptPath);
entryName = mfilename;
cfg = local_case_config(entryName);

inputDir = fullfile(caseDir, '输入模型与参数');
groundDir = fullfile(inputDir, '地震记录');
referenceDir = fullfile(caseDir, '参考结果_仅用于末端验收');
outputDir = fullfile(caseDir, '输出');
modelOutputDir = fullfile(outputDir, '运行模型副本');
dataOutputDir = fullfile(outputDir, '本轮计算数据');
figureOutputDir = fullfile(outputDir, '本轮计算图');
if ~isfolder(modelOutputDir), mkdir(modelOutputDir); end
if ~isfolder(dataOutputDir), mkdir(dataOutputDir); end
if ~isfolder(figureOutputDir), mkdir(figureOutputDir); end

% 将Simulink缓存和代码生成目录限制在本图“输出”内，防止缓存散落到
% MATLAB当前目录或单图根目录；脚本结束或报错时自动恢复用户原设置。
simulinkCacheDir = fullfile(outputDir, 'Simulink缓存');
simulinkCodegenDir = fullfile(outputDir, 'Simulink代码生成');
previousFileGenConfig = Simulink.fileGenControl('getConfig');
fileGenCleanup = onCleanup(@() restore_file_generation_settings(previousFileGenConfig)); %#ok<NASGU>
Simulink.fileGenControl('set', 'CacheFolder', simulinkCacheDir, ...
    'CodeGenFolder', simulinkCodegenDir, 'createDir', true);

logFile = fullfile(outputDir, 'MATLAB现场运行日志.txt');
if isfile(logFile), delete(logFile); end
diary(logFile);
diaryCleanup = onCleanup(@() diary('off')); %#ok<NASGU>
totalTimer = tic;

fprintf('\n============================================================\n');
fprintf('%s：%s\n', cfg.figure_id, cfg.description_cn);
fprintf('计算路线：15自由度原结构 -> Guyan / Craig-Bampton -> 状态空间 -> Simulink -> 物理楼层恢复 -> 绘图\n');
fprintf('本图目录：%s\n', caseDir);
fprintf('注意：参考CSV尚未读取；它只在最后的末端验收章节使用。\n');
if strcmp(cfg.figure_id, 'Fig09')
    fprintf('Fig.9口径：本脚本使用物理一致的Chirp局部窗13--14 s与38--38.3 s；不复刻硕士论文图3-15混入El Centro局部窗的历史错误。\n');
end
fprintf('============================================================\n\n');

%% 1. 从梁禹参数脚本建立 15 自由度原结构质量、阻尼、刚度矩阵
% PDmonicanshu.m 根据三层钢框架的梁柱尺寸、材料参数和单元刚度装配：
%   MRrt：15×15 质量矩阵 M
%   CRrt：15×15 Rayleigh 阻尼矩阵 C
%   KRrt：15×15 刚度矩阵 K
% 这里不是读取响应结果，而是在当前 MATLAB 会话重新生成动力模型。
paramScript = fullfile(inputDir, 'PDmonicanshu.m');
eqFile = fullfile(inputDir, 'EQ.mat');
assert(isfile(paramScript), '缺少参数脚本：%s', paramScript);
assert(isfile(eqFile), '缺少地震输入文件：%s', eqFile);
assert(~isempty(ver('simulink')), '当前 MATLAB 未安装或未授权 Simulink。');
assert(exist('ss', 'file') == 2, '当前 MATLAB 缺少 Control System Toolbox 的 ss 函数。');

run(paramScript);
load(eqFile, 'ElCentroAccel', 'EQ_intensity', 'EQ_sw');
assert(isequal(size(MRrt), [15,15]) && isequal(size(CRrt), [15,15]) && isequal(size(KRrt), [15,15]), ...
    '原结构 M/C/K 必须均为15×15。');
assert(all(isfinite(MRrt(:))) && all(isfinite(CRrt(:))) && all(isfinite(KRrt(:))), ...
    '原结构 M/C/K 含 NaN 或 Inf。');

M_full = MRrt;
C_full = CRrt;
K_full = KRrt;
fprintf('[1/9] 原结构矩阵完成：M/C/K = 15×15；前两阶频率 = %.6f, %.6f Hz。\n', fre(1), fre(2));

%% 2. 复制并适配本图使用的 Simulink 模型（只改运行副本）
% 作者原模型保存了其电脑上的绝对地震文件路径，不能在本机直接编译。
% 本节进行三件事：
%   A. 把原 SLX 复制到“输出/运行模型副本”；
%   B. 增加 From Workspace 输入，绕过未连接的 Step/Chirp 根块；
%   C. 把 From File 的绝对路径换成本图文件夹自带的原地震记录。
% 第二类划分还会补齐 Mux6 中缺失的三层 Guyan 和 CB 输出线。
modelSourceFile = fullfile(inputDir, cfg.model_filename);
runtime_model_file = fullfile(modelOutputDir, cfg.runtime_model_filename);
assert(isfile(modelSourceFile), '缺少本图模型：%s', modelSourceFile);
prepare_model_copy(modelSourceFile, runtime_model_file, cfg.needs_third_floor_repair, groundDir);
fprintf('[2/9] 运行模型副本完成：%s\n', runtime_model_file);
if cfg.needs_third_floor_repair
    fprintf('      已在副本补齐第二类划分三层输出：Mux6/2 <- Demux4/3，Mux6/3 <- Demux5/3。\n');
end

%% 3. 按本图的子结构划分重新计算 Guyan 与 Craig--Bampton 降阶模型
% 第一步按“主自由度在前、从自由度在后”重排 M/C/K。
% Guyan：用静力关系 q_s = -K_ss^{-1}K_sm q_m 消去从自由度。
%         为追踪梁禹现存路线，本演示保留其单侧 M/C/K 公式，而不是静默改成 T'AT。
% Craig--Bampton：保留约束模态，并加入按特征值升序选取的3个固定界面模态。
reduction = build_reduction_models(M_full, C_full, K_full, cfg.division);

M_guyan = reduction.Mg;
C_guyan = reduction.Cg;
K_guyan = reduction.Kg;
M_cb = reduction.Mcb;
C_cb = reduction.Ccb;
K_cb = reduction.Kcb;
T_guyan = reduction.T;
T_cb = reduction.T_cb;
master_dofs = reduction.master;
slave_dofs = reduction.slave;

fprintf('[3/9] 降阶完成：Original=%d，Guyan=%d，Craig-Bampton=%d 个位移自由度。\n', ...
    size(M_full,1), size(M_guyan,1), size(M_cb,1));
fprintf('      主自由度：%s\n', mat2str(master_dofs));
fprintf('      从自由度：%s\n', mat2str(slave_dofs));

%% 4. 把三套二阶动力方程写成状态空间并定义三层物理位移恢复矩阵
% 对 M*qdd + C*qd + K*q = f*u(t)，状态 x=[q;qd]：
%   xdot = [0 I; -M\K -M\C] x + [0; M\I] f*u(t)
% 完整模型直接取物理自由度 [1,6,11]；降阶模型分别通过 T_guyan、T_cb
% 恢复到原15自由度，再取一、二、三层水平位移。
assign_model_variables(reduction, M_full);
state_dimensions = [size(reduction.G_1.A,1), size(reduction.G_2.A,1), size(reduction.G_3.A,1)];
fprintf('[4/9] 状态空间完成：三套状态维数 = %s。\n', mat2str(state_dimensions));

%% 5. 现场生成本图激励，而不是读取既有响应
% Fig.6/7：El Centro 1940 NS 原记录乘 EQ_intensity=0.40。
% Fig.8/9：0.1--10 Hz、40 s线性Chirp：
%   u(t)=sin(2*pi*0.1*t + pi*(10-0.1)/40*t^2)
dt = 1/1024;
stopTime = 40;
fineTime = (0:dt:stopTime)';
if strcmp(cfg.excitation_type, 'ElCentro')
    assert(EQ_sw == 1, 'EQ.mat 的 EQ_sw 不是 El Centro 分支。');
    assert(abs(EQ_intensity - 0.40) < 1e-14, 'EQ_intensity 应为0.40，实际为%.17g。', EQ_intensity);
    eqTime = ElCentroAccel(1,:)';
    eqAcceleration = EQ_intensity * ElCentroAccel(2,:)';
    keep = eqTime <= stopTime;
    excitation_input = [eqTime(keep), eqAcceleration(keep)];
    excitation_description = sprintf('El Centro 1940 NS × %.2f', EQ_intensity);
else
    chirpAcceleration = sin(2*pi*0.1*fineTime + pi*(10-0.1)/stopTime*fineTime.^2);
    excitation_input = [fineTime, chirpAcceleration];
    excitation_description = '0.1--10 Hz linear Chirp over 40 s';
end
assert(all(isfinite(excitation_input(:))) && all(diff(excitation_input(:,1)) > 0), ...
    '激励时间轴或数值非法。');
fprintf('[5/9] 激励完成：%s；输入样本数=%d。\n', excitation_description, size(excitation_input,1));

%% 6. 用 Simulink ode4 固定步长重新积分 40 s
% 模型中三条并行支路分别计算 Original、Guyan、Craig--Bampton。
% 求解器：四阶定步长 Runge--Kutta（ode4）；dt=1/1024 s；总时长40 s。
% 运行输出的固定映射是：simout3=一层，simout=二层，simout1=三层。
simulationTimer = tic;
simulation_output = run_one_simulation(runtime_model_file, excitation_input, dt, stopTime);
simulation_seconds = toc(simulationTimer);
fprintf('[6/9] Simulink完成：耗时 %.2f s。\n', simulation_seconds);

%% 7. 把三套坐标统一恢复为 40961×3×3 的物理楼层响应
% response_mm 的三个维度依次是：时间点、楼层、方法。
% 方法轴顺序：1=Original，2=Guyan，3=Craig--Bampton。
% 作者模型的 To Workspace 前已有1e3增益，因此输出单位已经是mm。
[time_s, response_mm] = make_response_arrays(simulation_output);
assert(isequal(size(response_mm), [40961,3,3]), ...
    'response_mm 应为40961×3×3，实际为%s。', mat2str(size(response_mm)));
assert(abs(time_s(1)) <= 1e-14 && abs(time_s(end)-40) <= 1e-14, '时间范围不是0--40 s。');
time_step_error = max(abs(diff(time_s)-dt));
assert(time_step_error <= 1e-14, '时间步长误差超限：%.17g。', time_step_error);
assert(all(isfinite(response_mm(:))), '响应含 NaN 或 Inf。');

computed_matrix = response_to_matrix(time_s, response_mm);
computed_mat_file = fullfile(dataOutputDir, [cfg.figure_id '_本轮全链计算响应.mat']);
computed_csv_file = fullfile(dataOutputDir, [cfg.figure_id '_本轮全链计算响应.csv']);
save(computed_mat_file, 'time_s', 'response_mm', 'computed_matrix', 'cfg', ...
    'M_full', 'C_full', 'K_full', 'M_guyan', 'C_guyan', 'K_guyan', ...
    'M_cb', 'C_cb', 'K_cb', 'T_guyan', 'T_cb', 'master_dofs', 'slave_dofs', '-v7.3');
write_response_csv(computed_csv_file, computed_matrix);
write_peak_rms(fullfile(dataOutputDir, [cfg.figure_id '_峰值与RMS.csv']), response_mm);
fprintf('[7/9] 物理响应恢复完成：response_mm = 40961×3×3；本轮CSV已保存。\n');

%% 8. 直接使用本轮 response_mm 绘制论文图，不从参考CSV取曲线
% 两行分别为一层和三层；每行左图是0--40 s，右侧两图是局部放大。
% 数据内部顺序为 Original/Guyan/CB；图例显示顺序为 Original/CB/Guyan。
% Original=深灰虚线，CB=红色实线，Guyan=蓝色点划线。
plotFont = choose_plot_font();
showOnScreen = usejava('desktop');
fig = plot_journal_figure(time_s, response_mm, cfg.local_windows_s, plotFont, showOnScreen);
pdfFile = fullfile(figureOutputDir, [cfg.output_stem '.pdf']);
pngFile = fullfile(figureOutputDir, [cfg.output_stem '.png']);
exportgraphics(fig, pdfFile, 'ContentType', 'vector', 'BackgroundColor', 'white');
exportgraphics(fig, pngFile, 'Resolution', 600, 'BackgroundColor', 'white');
if ~showOnScreen, close(fig); end
fprintf('[8/9] 绘图完成：\n      PDF=%s\n      PNG=%s\n', pdfFile, pngFile);

%% 9. 末端验收：现在才读取“当前结果CSV”，证明新计算是否一致
% 到本节之前，结构、降阶、激励、Simulink、响应恢复和图均已完成并保存。
% 这里读取当前结果只做逐点比较；它没有参与任何上游计算。
referenceFile = fullfile(referenceDir, cfg.reference_filename);
assert(isfile(referenceFile), '缺少末端验收参考：%s', referenceFile);
reference_matrix = readmatrix(referenceFile, 'NumHeaderLines', 1);
assert(isequal(size(reference_matrix), [40961,10]), ...
    '参考结果应为40961×10，实际为%s。', mat2str(size(reference_matrix)));
comparison_error = abs(computed_matrix - reference_matrix);
max_abs_difference_to_current = max(comparison_error(:));
comparison_pass = max_abs_difference_to_current <= 1e-12;
assert(comparison_pass, '本轮计算与当前结果最大差%.17g，超过1e-12。', max_abs_difference_to_current);

validationFile = fullfile(outputDir, '现场演示验收报告.txt');
write_validation_report(validationFile, cfg, size(M_full,1), size(M_guyan,1), size(M_cb,1), ...
    size(response_mm), time_step_error, max_abs_difference_to_current, simulation_seconds, ...
    computed_csv_file, pdfFile, pngFile, runtime_model_file);

fprintf('[9/9] 末端验收通过：本轮计算与当前结果最大绝对差 = %.17g mm。\n', max_abs_difference_to_current);
fprintf('\nSTATUS=PASS\n');
fprintf('FULL_CHAIN=PASS\n');
fprintf('总耗时：%.2f s\n', toc(totalTimer));
fprintf('现场建议查看工作区变量：M_full、M_guyan、M_cb、T_guyan、T_cb、excitation_input、response_mm。\n');
fprintf('如需打开实际运行模型副本，请在命令窗口输入：open_system(runtime_model_file)\n\n');

clear diaryCleanup;
clear fileGenCleanup;

%% 本文件以下为局部函数：支撑上述九个现场章节
function cfg = local_case_config(entryName)
    switch entryName
        case 'RUN_FIG06_FULLCHAIN'
            cfg.figure_id = 'Fig06';
            cfg.description_cn = '第一类子结构划分，El Centro地震响应';
            cfg.division = 1;
            cfg.excitation_type = 'ElCentro';
            cfg.model_filename = 'lvxvjie_guyan_2.slx';
            cfg.runtime_model_filename = 'fig06_division1_repro.slx';
            cfg.needs_third_floor_repair = false;
            cfg.local_windows_s = [10,11;21.5,22.5];
            cfg.reference_filename = '第一类划分_ElCentro地震响应.csv';
            cfg.output_stem = 'fig06_eq_div1_fullchain';
        case 'RUN_FIG07_FULLCHAIN'
            cfg.figure_id = 'Fig07';
            cfg.description_cn = '第二类子结构划分，El Centro地震响应';
            cfg.division = 2;
            cfg.excitation_type = 'ElCentro';
            cfg.model_filename = 'lvxvjie_guyan.slx';
            cfg.runtime_model_filename = 'fig07_division2_repro.slx';
            cfg.needs_third_floor_repair = true;
            cfg.local_windows_s = [10,11;21.5,22.5];
            cfg.reference_filename = '第二类划分_ElCentro地震响应.csv';
            cfg.output_stem = 'fig07_eq_div2_fullchain';
        case 'RUN_FIG08_FULLCHAIN'
            cfg.figure_id = 'Fig08';
            cfg.description_cn = '第一类子结构划分，0.1--10 Hz Chirp响应';
            cfg.division = 1;
            cfg.excitation_type = 'Chirp';
            cfg.model_filename = 'lvxvjie_guyan_2.slx';
            cfg.runtime_model_filename = 'fig08_division1_repro.slx';
            cfg.needs_third_floor_repair = false;
            cfg.local_windows_s = [13,14;38,38.3];
            cfg.reference_filename = '第一类划分_Chirp响应.csv';
            cfg.output_stem = 'fig08_chirp_div1_fullchain';
        case 'RUN_FIG09_FULLCHAIN'
            cfg.figure_id = 'Fig09';
            cfg.description_cn = '第二类子结构划分，0.1--10 Hz Chirp响应';
            cfg.division = 2;
            cfg.excitation_type = 'Chirp';
            cfg.model_filename = 'lvxvjie_guyan.slx';
            cfg.runtime_model_filename = 'fig09_division2_repro.slx';
            cfg.needs_third_floor_repair = true;
            cfg.local_windows_s = [13,14;38,38.3];
            cfg.reference_filename = '第二类划分_Chirp响应.csv';
            cfg.output_stem = 'fig09_chirp_div2_fullchain';
        otherwise
            error('未知现场入口文件名：%s。请勿重命名 RUN_FIGxx_FULLCHAIN.m。', entryName);
    end
end

function restore_file_generation_settings(config)
    Simulink.fileGenControl('set', 'CacheFolder', config.CacheFolder, ...
        'CodeGenFolder', config.CodeGenFolder, 'createDir', true);
end

function prepare_model_copy(sourceFile, targetFile, needsThirdFloorRepair, groundDir)
    [~, modelName] = fileparts(targetFile);
    if bdIsLoaded(modelName), close_system(modelName, 0); end
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
    for k = 1:numel(gainNames)
        block = [modelName '/' gainNames{k}];
        ports = get_param(block, 'PortHandles');
        oldLine = get_param(ports.Inport, 'Line');
        if oldLine ~= -1, delete_line(oldLine); end
        add_line(modelName, inputPort.Outport, ports.Inport, 'autorouting', 'on');
    end

    fromFileBlocks = find_system(modelName, 'LookUnderMasks', 'all', ...
        'FollowLinks', 'on', 'BlockType', 'FromFile');
    for k = 1:numel(fromFileBlocks)
        oldFile = get_param(fromFileBlocks{k}, 'FileName');
        [~, baseName, ext] = fileparts(oldFile);
        localFile = fullfile(groundDir, [baseName ext]);
        assert(isfile(localFile), '缺少本地地震辅助文件：%s', localFile);
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
            if oldLine ~= -1, delete_line(oldLine); end
            add_line(modelName, demuxPorts.Outport(3), muxPorts.Inport(k+1), 'autorouting', 'on');
        end
    end

    set_param(modelName, 'StopTime', '40', 'Solver', 'ode4', 'FixedStep', 'dt');
    save_system(modelName, targetFile);
    close_system(modelName, 0);

    if needsThirdFloorRepair
        load_system(targetFile);
        muxPorts = get_param([modelName '/Mux6'], 'PortHandles');
        expectedBlocks = {'Demux3','Demux4','Demux5'};
        for k = 1:3
            lineHandle = get_param(muxPorts.Inport(k), 'Line');
            assert(lineHandle ~= -1, 'Mux6输入端口%d仍未连接。', k);
            srcBlock = get_param(lineHandle, 'SrcBlockHandle');
            srcPort = get_param(lineHandle, 'SrcPortHandle');
            expectedBlock = getSimulinkBlockHandle([modelName '/' expectedBlocks{k}]);
            expectedPorts = get_param([modelName '/' expectedBlocks{k}], 'PortHandles');
            assert(srcBlock == expectedBlock && srcPort == expectedPorts.Outport(3), ...
                'Mux6输入端口%d不是来自%s/3。', k, expectedBlocks{k});
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

    staticConstraint = -(Kss\Ksm);
    T = [eye(nm); staticConstraint];
    Mg = Mmm + Mms*staticConstraint;
    Cg = Cmm + Cms*staticConstraint;
    Kg = Kmm + Kms*staticConstraint;

    [phi, lambda] = eig(Kss, Mss);
    [~, idx] = sort(real(diag(lambda)), 'ascend');
    phi = real(phi(:,idx));
    retainedModes = 3;
    Tcb = [eye(nm), zeros(nm,retainedModes); staticConstraint, phi(:,1:retainedModes)];
    Mcb = Tcb'*Mo*Tcb;
    Ccb = Tcb'*Co*Tcb;
    Kcb = Tcb'*Ko*Tcb;

    G1 = second_order_ss(M, C, K);
    G2 = second_order_ss(Mg, Cg, Kg);
    G3 = second_order_ss(Mcb, Ccb, Kcb);

    floorOriginal = [1,6,11];
    floorRowsOrdered = arrayfun(@(q)find(order==q,1), floorOriginal);
    P = eye(15); P = P(floorRowsOrdered,:);
    Cfloor1 = [eye(15), zeros(15)]; Cfloor1 = Cfloor1(floorOriginal,:);
    Cfloor2 = [P*T, zeros(3,size(T,2))];
    Cfloor3 = [P*Tcb, zeros(3,size(Tcb,2))];

    Mf = diag(forceMask .* Mo);
    R.G_1 = G1; R.G_2 = G2; R.G_3 = G3;
    R.T = T; R.T_cb = Tcb; R.Mf = Mf;
    R.Cfloor1 = Cfloor1; R.Cfloor2 = Cfloor2; R.Cfloor3 = Cfloor3;
    R.Dfloor1 = zeros(3,size(G1.B,2));
    R.Dfloor2 = zeros(3,size(G2.B,2));
    R.Dfloor3 = zeros(3,size(G3.B,2));
    R.master = master; R.slave = slave; R.order = order;
    R.Mg = Mg; R.Cg = Cg; R.Kg = Kg;
    R.Mcb = Mcb; R.Ccb = Ccb; R.Kcb = Kcb;
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

function out = run_one_simulation(modelFile, excitation, dt, stopTime)
    [~, modelName] = fileparts(modelFile);
    if bdIsLoaded(modelName), close_system(modelName, 0); end
    load_system(modelFile);
    assignin('base', 'excitation_input', excitation);
    assignin('base', 'dt', dt);
    set_param([modelName '/可复现excitation_input'], 'Interpolate', 'on');
    set_param(modelName, 'StopTime', num2str(stopTime,17));
    simOut = sim(modelName, 'ReturnWorkspaceOutputs', 'on');
    out.floor1 = simOut.simout3;
    out.floor2 = simOut.simout;
    out.floor3 = simOut.simout1;
    close_system(modelName, 0);
end

function [time_s, response_mm] = make_response_arrays(out)
    time_s = out.floor1.Time(:);
    assert(max(abs(time_s-out.floor2.Time(:))) < 1e-12 && ...
        max(abs(time_s-out.floor3.Time(:))) < 1e-12, '三个楼层时间轴不一致。');
    D1 = squeeze(out.floor1.Data);
    D2 = squeeze(out.floor2.Data);
    D3 = squeeze(out.floor3.Data);
    assert(size(D1,2)==3 && size(D2,2)==3 && size(D3,2)==3, ...
        '每个楼层输出必须包含Original、Guyan和Craig-Bampton三列。');
    response_mm = cat(2, reshape(D1,[],1,3), reshape(D2,[],1,3), reshape(D3,[],1,3));
end

function matrix = response_to_matrix(time_s, response_mm)
    matrix = [time_s, ...
        response_mm(:,1,1), response_mm(:,1,2), response_mm(:,1,3), ...
        response_mm(:,2,1), response_mm(:,2,2), response_mm(:,2,3), ...
        response_mm(:,3,1), response_mm(:,3,2), response_mm(:,3,3)];
end

function write_response_csv(path, matrix)
    T = array2table(matrix, 'VariableNames', ...
        {'时间_s','原结构_一层_mm','Guyan_一层_mm','CraigBampton_一层_mm', ...
         '原结构_二层_mm','Guyan_二层_mm','CraigBampton_二层_mm', ...
         '原结构_三层_mm','Guyan_三层_mm','CraigBampton_三层_mm'});
    writetable(T, path, 'Encoding', 'UTF-8');
end

function write_peak_rms(path, response_mm)
    floorNames = {'一层','二层','三层'};
    methodNames = {'Original','Guyan','Craig-Bampton'};
    rows = table();
    for floorIndex = 1:3
        for methodIndex = 1:3
            y = response_mm(:,floorIndex,methodIndex);
            row = table(string(floorNames{floorIndex}), string(methodNames{methodIndex}), ...
                max(abs(y)), sqrt(mean(y.^2)), y(end), ...
                'VariableNames', {'楼层','方法','绝对峰值_mm','RMS_mm','末值_mm'});
            rows = [rows; row]; %#ok<AGROW>
        end
    end
    writetable(rows, path, 'Encoding', 'UTF-8');
end

function fig = plot_journal_figure(time_s, response_mm, localWindows, plotFont, showOnScreen)
    visibility = 'off';
    if showOnScreen, visibility = 'on'; end
    fig = figure('Visible', visibility, 'Color', 'white', 'Renderer', 'painters', ...
        'Units', 'inches', 'Position', [1,1,6.30,3.82]);
    positions = [ ...
        0.1050,0.540,0.4092,0.310; 0.5742,0.540,0.1779,0.310; 0.8121,0.540,0.1779,0.310; ...
        0.1050,0.130,0.4092,0.310; 0.5742,0.130,0.1779,0.310; 0.8121,0.130,0.1779,0.310];
    floors = [1,3];
    panelLabels = {'(a)','(b)'};
    axesHandles = gobjects(2,3);
    legendHandles = gobjects(1,3);

    for row = 1:2
        floorValues = squeeze(response_mm(:,floors(row),:));
        ax = axes('Parent', fig, 'Position', positions((row-1)*3+1,:));
        axesHandles(row,1) = ax;
        currentHandles = plot_three_methods(ax, time_s, floorValues, false);
        xlim(ax,[0,40]); xticks(ax,0:10:40); ylim(ax,padded_limits(floorValues));
        ylabel(ax,'Displacement (mm)','Interpreter','latex');
        apply_axis_style(ax,plotFont);
        text(ax,0.025,0.92,panelLabels{row},'Units','normalized', ...
            'VerticalAlignment','top','FontName',plotFont,'FontSize',9, ...
            'FontWeight','bold','Interpreter','latex','BackgroundColor','white','Margin',1);
        if row==1, legendHandles=currentHandles; else, xlabel(ax,'Time (s)','Interpreter','latex'); end

        for windowIndex = 1:2
            window = localWindows(windowIndex,:);
            mask = time_s>=window(1) & time_s<=window(2);
            assert(nnz(mask)>=20,'局部窗样本不足。');
            ax = axes('Parent',fig,'Position',positions((row-1)*3+1+windowIndex,:));
            axesHandles(row,1+windowIndex)=ax;
            plot_three_methods(ax,time_s(mask),floorValues(mask,:),true);
            xlim(ax,window); xticks(ax,linspace(window(1),window(2),3));
            ylim(ax,padded_limits(floorValues(mask,:)));
            apply_axis_style(ax,plotFont);
            if windowIndex==1, xtickformat(ax,'%.1f'); else, xtickformat(ax,'%.2f'); end
            if row==2, xlabel(ax,'Time (s)','Interpreter','latex'); end
        end
    end

    legendObject = legend(axesHandles(1,1),legendHandles, ...
        {'Original','Craig--Bampton','Guyan'},'Interpreter','latex', ...
        'FontName',plotFont,'FontSize',9,'Orientation','horizontal', ...
        'NumColumns',3,'Box','off');
    legendObject.Units='normalized';
    legendObject.Position=[0.31,0.925,0.38,0.045];
    drawnow;
end

function handles = plot_three_methods(ax, time_s, values, isLocal)
    methodColumns = [1,3,2];
    colors = [85,85,85;238,102,119;68,119,170]/255;
    lineStyles = {'--','-','-.'};
    markers = {'o','s','^'};
    handles = gobjects(1,3);
    if isLocal
        indices = 1:numel(time_s); lineWidth=1.10;
    else
        stride=max(1,floor(numel(time_s)/12000));
        indices=unique([1:stride:numel(time_s),numel(time_s)]); lineWidth=0.85;
    end
    markerIndices=unique(round(linspace(1,numel(indices),9)));
    hold(ax,'on');
    for methodIndex=1:3
        handles(methodIndex)=plot(ax,time_s(indices),values(indices,methodColumns(methodIndex)), ...
            'Color',colors(methodIndex,:),'LineStyle',lineStyles{methodIndex},'LineWidth',lineWidth);
        if isLocal
            set(handles(methodIndex),'Marker',markers{methodIndex},'MarkerIndices',markerIndices, ...
                'MarkerSize',3.2,'MarkerFaceColor','white','MarkerEdgeColor',colors(methodIndex,:));
        end
    end
    hold(ax,'off');
end

function limits = padded_limits(values)
    lower=min(values(:)); upper=max(values(:)); span=upper-lower;
    if span<=eps(max(abs([lower,upper,1]))), span=max(abs(lower),1); end
    limits=[lower-0.08*span,upper+0.08*span];
end

function apply_axis_style(ax, plotFont)
    set(ax,'FontName',plotFont,'FontSize',9,'TickLabelInterpreter','latex', ...
        'TickDir','in','TickLength',[0.012,0.012],'Box','on','LineWidth',0.8, ...
        'Layer','top','XGrid','off','YGrid','off','XMinorTick','off','YMinorTick','off');
end

function plotFont = choose_plot_font()
    installedFonts=listfonts;
    if any(strcmpi(installedFonts,'CMU Serif'))
        plotFont='CMU Serif';
    elseif any(strcmpi(installedFonts,'Times New Roman'))
        plotFont='Times New Roman';
    else
        plotFont='Serif';
    end
end

function write_validation_report(path, cfg, nFull, nGuyan, nCb, responseSize, ...
        timeStepError, maxDifference, simulationSeconds, csvFile, pdfFile, pngFile, modelFile)
    fileId=fopen(path,'w');
    assert(fileId>=0,'无法写入验收报告：%s',path);
    cleanup=onCleanup(@()fclose(fileId));
    fprintf(fileId,'STATUS=PASS\n');
    fprintf(fileId,'FIGURE=%s\n',cfg.figure_id);
    fprintf(fileId,'DESCRIPTION=%s\n',cfg.description_cn);
    fprintf(fileId,'EVIDENCE_LEVEL=计算级复现（现存代码/必要适配路线）\n');
    fprintf(fileId,'AUTHOR_HISTORICAL_POINT_VALUES=待决定\n');
    fprintf(fileId,'DISPLACEMENT_DOF=Original:%d,Guyan:%d,Craig-Bampton:%d\n',nFull,nGuyan,nCb);
    fprintf(fileId,'RESPONSE_SIZE=%s\n',mat2str(responseSize));
    fprintf(fileId,'TIME_RANGE_S=0,40\n');
    fprintf(fileId,'FIXED_STEP_S=0.0009765625\n');
    fprintf(fileId,'MAX_TIME_STEP_ERROR_S=%.17g\n',timeStepError);
    fprintf(fileId,'MAX_ABS_DIFFERENCE_TO_CURRENT_MM=%.17g\n',maxDifference);
    fprintf(fileId,'SIMULATION_SECONDS=%.6f\n',simulationSeconds);
    fprintf(fileId,'COMPUTED_CSV=%s\n',csvFile);
    fprintf(fileId,'VECTOR_PDF=%s\n',pdfFile);
    fprintf(fileId,'PNG_600DPI=%s\n',pngFile);
    fprintf(fileId,'RUNTIME_MODEL_COPY=%s\n',modelFile);
    clear cleanup;
end
