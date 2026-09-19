%% 0. 初始化：建立本次运行，必须先执行这一节
% Fig11：第二种划分扫频响应
% F5完整运行；Ctrl+Enter按节运行。核心函数可右键打开逐行查看。
packageRoot=fileparts(fileparts(mfilename('fullpath')));
addpath(fullfile(packageRoot,'计算核心'));
demo=rths_begin(packageRoot,'Fig11');
frame=[];models={};modes={};inputs=[];
responses=cell(2,2);metrics=struct;boundaries={};
demo.stage=0;

%% 1. 由结构参数装配完整模型
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig11') && demo.stage==0, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
frame=frame_model();
% 查看frame.M、frame.C、frame.K：均为15×15；质量参数见frame.rho_model。
disp(size(frame.M));disp(frame.frequency_hz(1:5));
demo.stage=1;

%% 2. 计算两种划分的Guyan与Craig–Bampton模型
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig11') && demo.stage==1, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
models={rths_reduce(frame,1),rths_reduce(frame,2)};
% 查看models{1}.master、models{2}.master及T/T_cb，跟踪坐标顺序。
fprintf('位移自由度：划分I为15/6/9，划分II为15/5/8。\n');
demo.stage=2;

%% 3. 求模态并恢复到15个物理坐标
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig11') && demo.stage==2, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
modes=rths_modes(frame,models);
% modes{划分,方法}：方法1完整，2 Guyan，3 Craig–Bampton。
% 查看frequency_hz、physical_modes、weights、shares。
demo.stage=3;

%% 4. 建立地震／扫频激励与积分时间轴
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig11') && demo.stage==3, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
inputs=rths_inputs(packageRoot);
% inputs.eq为原始采样缩放记录；chirp由公式生成；time为40961点积分网格。
demo.stage=4;

%% 5. 重新积分：第2种划分、扫频激励
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig11') && demo.stage==4, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
responses{2,2}=rths_simulate(frame,models{2},inputs,'chirp',demo);
% mm的三个下标依次为时间、楼层、方法，尺寸40961×3×3。
% 如需查看并行仿真图：open_system(responses{2,2}.model_file)
demo.stage=5;

%% 6. 从本轮模型与时程计算指标
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig11') && demo.stage==5, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
metrics=rths_metrics(frame,models,modes,responses);
% modal：频率误差/MAC；errors：NRMSE；drifts：峰值层间角；totals：表5。
demo.stage=6;

%% 7. 生成本图并保存可编辑结果
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig11') && demo.stage==6, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
bundle=struct('frame',frame,'models',{models},'modes',{modes},'inputs',inputs,...
    'responses',{responses},'metrics',metrics,'boundaries',{boundaries});
[fig,plotted]=rths_plot(11,bundle,demo);
artifact=rths_save_figure(fig,11,demo,plotted);
demo=rths_finish(demo,bundle);
demo.stage=7;
