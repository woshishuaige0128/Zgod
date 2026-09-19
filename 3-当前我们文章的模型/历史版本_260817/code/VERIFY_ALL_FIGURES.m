% VERIFY_ALL_FIGURES
% 一键执行五个单图验证器，并汇总每张图的验证状态。

packageRoot = fileparts(mfilename('fullpath'));
verifyAllCaseFigures(packageRoot);

function verifyAllCaseFigures(packageRoot)
figureFolders = {
    'Fig06_第一类划分_ElCentro响应'
    'Fig07_第二类划分_ElCentro响应'
    'Fig08_第一类划分_Chirp响应'
    'Fig09_第二类划分_Chirp响应'
    'Fig10_双时滞稳定域'
};
figureFiles = {
    'fig06_eq_div1'
    'fig07_eq_div2'
    'fig08_chirp_div1'
    'fig09_chirp_div2'
    'fig10_stability_domain'
};

recordFolder = fullfile(packageRoot, '验证记录');
if ~isfolder(recordFolder)
    mkdir(recordFolder);
end

status = strings(numel(figureFolders), 1);
pdfBytes = zeros(numel(figureFolders), 1);
pngBytes = zeros(numel(figureFolders), 1);

fprintf('\n========== 开始验证五张案例分析结果图 ==========\n');
for index = 1:numel(figureFolders)
    figureFolder = fullfile(packageRoot, figureFolders{index});
    verifyFile = fullfile(figureFolder, 'VERIFY_THIS_FIGURE.m');
    assert(isfile(verifyFile), '缺少单图验证器：%s', verifyFile);
    fprintf('\n[%d/5] %s\n', index, figureFolders{index});
    run(verifyFile);

    outputFolder = fullfile(figureFolder, '输出');
    reportFile = fullfile(outputFolder, 'validation_report.txt');
    pdfFile = fullfile(outputFolder, 'PDF', [figureFiles{index}, '.pdf']);
    pngFile = fullfile(outputFolder, 'PNG', [figureFiles{index}, '.png']);
    assert(isfile(reportFile), '缺少单图验证报告：%s', reportFile);
    reportText = fileread(reportFile);
    assert(contains(reportText, 'STATUS=PASS'), '单图验证未通过：%s', figureFolders{index});
    assert(isfile(pdfFile) && isfile(pngFile), '单图输出不完整：%s', figureFolders{index});
    pdfInfo = dir(pdfFile);
    pngInfo = dir(pngFile);
    pdfBytes(index) = pdfInfo.bytes;
    pngBytes(index) = pngInfo.bytes;
    status(index) = "PASS";
end

summary = table(string(figureFolders), string(figureFiles), status, pdfBytes, pngBytes, ...
    'VariableNames', {'figure_folder', 'output_stem', 'status', 'pdf_bytes', 'png_bytes'});
writetable(summary, fullfile(recordFolder, 'MATLAB总验收清单.csv'), 'Encoding', 'UTF-8');

reportFile = fullfile(recordFolder, 'MATLAB总验收报告.txt');
fileId = fopen(reportFile, 'w', 'n', 'UTF-8');
assert(fileId >= 0, '无法写入总验收报告：%s', reportFile);
cleaner = onCleanup(@() fclose(fileId));
fprintf(fileId, 'STATUS=PASS\n');
fprintf(fileId, 'FIGURE_COUNT=5\n');
fprintf(fileId, 'PDF_COUNT=5\n');
fprintf(fileId, 'PNG_COUNT=5\n');
fprintf(fileId, 'SCOPE=CASE_ANALYSIS_NUMERICAL_RESULTS_FIG06_TO_FIG10\n');
clear cleaner;

fprintf('\n========== 五张图的MATLAB验证全部通过 ==========\n');
fprintf('总验收报告：%s\n', reportFile);
end
