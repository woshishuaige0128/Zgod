% RUN_ALL_FIGURES
% 一键生成小论文案例分析的五张数值结果图。
% 每张图仍由自己的自包含入口运行；本文件只是批量执行的便利入口。

packageRoot = fileparts(mfilename('fullpath'));
runAllCaseFigures(packageRoot);

function runAllCaseFigures(packageRoot)
figureFolders = {
    'Fig06_第一类划分_ElCentro响应'
    'Fig07_第二类划分_ElCentro响应'
    'Fig08_第一类划分_Chirp响应'
    'Fig09_第二类划分_Chirp响应'
    'Fig10_双时滞稳定域'
};

fprintf('\n========== 开始生成五张案例分析结果图 ==========\n');
for index = 1:numel(figureFolders)
    entryFile = fullfile(packageRoot, figureFolders{index}, 'RUN_THIS_FIGURE.m');
    assert(isfile(entryFile), '缺少单图入口：%s', entryFile);
    fprintf('\n[%d/5] %s\n', index, figureFolders{index});
    run(entryFile);
end
fprintf('\n========== 五张图全部生成完成 ==========\n');
fprintf('每张图的PDF和PNG位于各自文件夹的“输出”目录。\n');
end
