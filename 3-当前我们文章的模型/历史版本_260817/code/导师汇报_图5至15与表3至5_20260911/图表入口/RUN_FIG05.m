%% 0. 初始化：建立本次运行，必须先执行这一节
% Fig05：地震与扫频输入
% F5完整运行；Ctrl+Enter按节运行。核心函数可右键打开逐行查看。
packageRoot=fileparts(fileparts(mfilename('fullpath')));
addpath(fullfile(packageRoot,'计算核心'));
demo=rths_begin(packageRoot,'Fig05');
frame=[];models={};modes={};inputs=[];
responses=cell(2,2);metrics=struct;boundaries={};
demo.stage=0;

%% 1. 建立地震／扫频激励与积分时间轴
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig05') && demo.stage==0, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
inputs=rths_inputs(packageRoot);
% inputs.eq为原始采样缩放记录；chirp由公式生成；time为40961点积分网格。
demo.stage=1;

%% 2. 生成本图并保存可编辑结果
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig05') && demo.stage==1, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
bundle=struct('frame',frame,'models',{models},'modes',{modes},'inputs',inputs,...
    'responses',{responses},'metrics',metrics,'boundaries',{boundaries});
[fig,plotted]=rths_plot(5,bundle,demo);
artifact=rths_save_figure(fig,5,demo,plotted);
demo=rths_finish(demo,bundle);
demo.stage=2;
