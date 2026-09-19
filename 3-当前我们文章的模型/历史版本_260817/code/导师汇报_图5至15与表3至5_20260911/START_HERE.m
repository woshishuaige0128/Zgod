%% 从这里开始：图5—15、表3—5的MATLAB现场计算
% 本文件负责检查环境和提供入口。先按F5运行，再点击命令窗口链接。
packageRoot=fileparts(mfilename('fullpath'));
addpath(fullfile(packageRoot,'计算核心'));
environment=rths_environment();
items={
    '图表入口\RUN_FIG05.m', 'Fig05 地震与扫频输入';
    '图表入口\RUN_FIG06.m', 'Fig06 前两阶频率与水平振型';
    '图表入口\RUN_FIG07.m', 'Fig07 第一种划分地震响应';
    '图表入口\RUN_FIG08.m', 'Fig08 第二种划分地震响应';
    '图表入口\RUN_FIG09.m', 'Fig09 第二种划分中层地震重构误差';
    '图表入口\RUN_FIG10.m', 'Fig10 第一种划分扫频响应';
    '图表入口\RUN_FIG11.m', 'Fig11 第二种划分扫频响应';
    '图表入口\RUN_FIG12.m', 'Fig12 第二种划分中层扫频重构误差';
    '图表入口\RUN_FIG13.m', 'Fig13 峰值层间位移角';
    '图表入口\RUN_FIG14.m', 'Fig14 历史双时滞稳定域重绘';
    '图表入口\RUN_FIG15.m', 'Fig15 模态份额与逐坐标偏离';
    '图表入口\RUN_TABLE03.m', 'Table03 频率误差与模态保证准则';
    '图表入口\RUN_TABLE04.m', 'Table04 首层全时程及分频段响应误差';
    '图表入口\RUN_TABLE05.m', 'Table05 模态份额绝对相对偏离之和'
};
fprintf('\n逐图表入口：点击打开文件；F5完整计算；Ctrl+Enter从第0节开始。\n');
for k=1:size(items,1)
    p=strrep(fullfile(packageRoot,items{k,1}),'''','''''');
    fprintf('<a href="matlab:edit(''%s'')">%s</a>\n',p,items{k,2});
end
p=strrep(packageRoot,'''','''''');
fprintf('\n<a href="matlab:rths_run_all(''%s'',true)">重新计算全部图表（四套响应各算一次）</a>\n',p);
fprintf('<a href="matlab:web(fullfile(''%s'',''MATLAB图表计算与现场操作汇报.html''),''-browser'')">打开中文操作与代码讲解</a>\n',p);
fprintf('图14使用历史边界重绘，其余计算图表从参数/原始激励重新计算。\n');
