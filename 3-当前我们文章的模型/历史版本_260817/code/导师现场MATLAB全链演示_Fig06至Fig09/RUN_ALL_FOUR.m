function RUN_ALL_FOUR
% 可选总入口：依次运行 Fig.6--Fig.9 四个独立全计算链演示。
% 导师现场逐图讲解时，建议仍打开各子文件夹内的 RUN_FIGxx_FULLCHAIN.m。

rootDir = fileparts(mfilename('fullpath'));
entries = {
    fullfile(rootDir, 'Fig06_第一类划分_ElCentro全链计算', 'RUN_FIG06_FULLCHAIN.m')
    fullfile(rootDir, 'Fig07_第二类划分_ElCentro全链计算', 'RUN_FIG07_FULLCHAIN.m')
    fullfile(rootDir, 'Fig08_第一类划分_Chirp全链计算', 'RUN_FIG08_FULLCHAIN.m')
    fullfile(rootDir, 'Fig09_第二类划分_Chirp全链计算', 'RUN_FIG09_FULLCHAIN.m')
    };

fprintf('开始依次运行 Fig.6--Fig.9 四个全计算链演示。\n');
for k = 1:numel(entries)
    assert(isfile(entries{k}), '缺少逐图入口：%s', entries{k});
    escapedEntry = strrep(entries{k}, '''', '''''');
    evalin('base', sprintf('run(''%s'');', escapedEntry));
end
fprintf('ALL_FOUR_FULL_CHAINS=PASS\n');
end
