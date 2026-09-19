%% 0. 初始化：建立本次运行，必须先执行这一节
% Fig14：历史双时滞稳定域重绘
% F5完整运行；Ctrl+Enter按节运行。核心函数可右键打开逐行查看。
packageRoot=fileparts(fileparts(mfilename('fullpath')));
addpath(fullfile(packageRoot,'计算核心'));
demo=rths_begin(packageRoot,'Fig14');
frame=[];models={};modes={};inputs=[];
responses=cell(2,2);metrics=struct;boundaries={};
demo.stage=0;

%% 1. 读取历史边界与时间单位转换
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig14') && demo.stage==0, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
boundaries=rths_boundaries(packageRoot);
% boundaries{划分,方法}.steps为历史延迟步数；milliseconds=steps*1000/1024。
demo.stage=1;

%% 2. 生成本图并保存可编辑结果
assert(exist('demo','var')==1 && isstruct(demo) && isfield(demo,'stage') && strcmp(demo.label,'Fig14') && demo.stage==1, ...
    '请先从本文件初始化节开始，按顺序运行；重复计算请重新初始化。');
bundle=struct('frame',frame,'models',{models},'modes',{modes},'inputs',inputs,...
    'responses',{responses},'metrics',metrics,'boundaries',{boundaries});
[fig,plotted]=rths_plot(14,bundle,demo);
artifact=rths_save_figure(fig,14,demo,plotted);
demo=rths_finish(demo,bundle);
demo.stage=2;
