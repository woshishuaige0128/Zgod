function compute_board19_nrmse()
% 从板块18冻结三层响应计算历史脚本及论文连续式的NRMSE候选。

codeDir = fileparts(mfilename('fullpath'));
boardRoot = fileparts(codeDir);
inputDir = fullfile(boardRoot, 'input', 'board18', 'responses');
outputDir = fullfile(boardRoot, 'outputs', 'nrmse_matlab');
if ~exist(outputDir, 'dir'); mkdir(outputDir); end

datasets = {
    1, 'Chirp', '第一类划分_Chirp响应.csv';
    1, 'ElCentro', '第一类划分_ElCentro地震响应.csv';
    2, 'Chirp', '第二类划分_Chirp响应.csv';
    2, 'ElCentro', '第二类划分_ElCentro地震响应.csv';
};
methodNames = ["Guyan", "Craig-Bampton"];
historicalBounds = [0, 7.27, 13.73, 21.4, 32.31, 40];
frequencyBounds = [0.1, 1.9, 3.5, 5.4, 8.1, 10];
exactBounds = (frequencyBounds - 0.1) / (10 - 0.1) * 40;
bandLabels = ["0.1-1.9 Hz", "1.9-3.5 Hz", "3.5-5.4 Hz", ...
    "5.4-8.1 Hz", "8.1-10 Hz"];

candidateRows = cell(0, 18);
inputRows = cell(0, 11);

for datasetIndex = 1:size(datasets,1)
    division = datasets{datasetIndex,1};
    excitation = string(datasets{datasetIndex,2});
    filename = string(datasets{datasetIndex,3});
    path = fullfile(inputDir, filename);
    data = readmatrix(path, 'FileType', 'text', 'NumHeaderLines', 1);
    assert(isequal(size(data), [40961, 10]), 'Board19:ResponseShape', ...
        '%s尺寸应为40961×10，实际为%d×%d。', filename, size(data,1), size(data,2));
    assert(all(isfinite(data), 'all'), 'Board19:ResponseFinite', '%s含NaN/Inf。', filename);
    time = data(:,1);
    dt = diff(time);
    assert(time(1) == 0 && time(end) == 40, 'Board19:ResponseTimeRange', '%s时间范围异常。', filename);
    assert(all(dt > 0), 'Board19:ResponseTimeOrder', '%s时间非严格递增。', filename);
    assert(max(abs(dt - 1/1024)) <= 5e-15, 'Board19:ResponseTimeStep', '%s步长异常。', filename);
    responses = reshape(data(:,2:10), size(data,1), 3, 3); % time × method × floor
    fileHash = file_hash_from_manifest(boardRoot, "board18/responses/" + filename);
    inputRows(end+1,:) = {division, excitation, filename, size(data,1), size(data,2), ...
        time(1), time(end), min(dt), max(dt), all(isfinite(data),'all'), fileHash}; %#ok<AGROW>

    for floor = 1:3
        reference = responses(:,1,floor);
        referenceRange = max(reference) - min(reference);
        assert(referenceRange > 0, 'Board19:ZeroReferenceRange', ...
            '%s第%d层参考响应峰峰值为0。', filename, floor);
        for methodIndex = 1:2
            method = methodNames(methodIndex);
            reduced = responses(:,methodIndex+1,floor);
            error = reference - reduced;
            if excitation == "ElCentro"
                candidateRows(end+1,:) = calculate_candidate_row(division, excitation, floor, ...
                    method, 'historical_mean_full_range', 0, "El Centro full", 0, 40, ...
                    true(size(time)), 'all_samples', false, time, error, referenceRange, filename, fileHash); %#ok<AGROW>
                candidateRows(end+1,:) = calculate_candidate_row(division, excitation, floor, ...
                    method, 'paper_trapezoid_full_range', 0, "El Centro full", 0, 40, ...
                    true(size(time)), 'all_samples', true, time, error, referenceRange, filename, fileHash); %#ok<AGROW>
            else
                for band = 1:5
                    hStart = historicalBounds(band);
                    hEnd = historicalBounds(band+1);
                    historicalMask = time >= hStart & time < hEnd;
                    inclusiveMask = time >= hStart & time <= hEnd;
                    eStart = exactBounds(band);
                    eEnd = exactBounds(band+1);
                    exactMask = time >= eStart & time < eEnd;
                    candidateRows(end+1,:) = calculate_candidate_row(division, excitation, floor, ...
                        method, 'historical_mean_full_range', band, bandLabels(band), hStart, hEnd, ...
                        historicalMask, '[start,end)', false, time, error, referenceRange, filename, fileHash); %#ok<AGROW>
                    candidateRows(end+1,:) = calculate_candidate_row(division, excitation, floor, ...
                        method, 'historical_inclusive_mean_full_range', band, bandLabels(band), hStart, hEnd, ...
                        inclusiveMask, '[start,end]', false, time, error, referenceRange, filename, fileHash); %#ok<AGROW>
                    candidateRows(end+1,:) = calculate_candidate_row(division, excitation, floor, ...
                        method, 'exact_frequency_mean_full_range', band, bandLabels(band), eStart, eEnd, ...
                        exactMask, 'linear_chirp_[start,end)', false, time, error, referenceRange, filename, fileHash); %#ok<AGROW>
                    candidateRows(end+1,:) = calculate_candidate_row(division, excitation, floor, ...
                        method, 'paper_trapezoid_full_range', band, bandLabels(band), hStart, hEnd, ...
                        historicalMask, 'historical_[start,end)', true, time, error, referenceRange, filename, fileHash); %#ok<AGROW>
                end
            end
        end
    end
end

candidateTable = cell2table(candidateRows, 'VariableNames', { ...
    'division','excitation','floor','method','route','band_id','frequency_band', ...
    'window_start_s','window_end_s','window_inclusion','sample_count', ...
    'reference_range_mm','rmse_mm','nrmse_percent','numerator_formula', ...
    'normalization','source_file','source_sha256'});
inputTable = cell2table(inputRows, 'VariableNames', { ...
    'division','excitation','source_file','row_count','column_count','time_start_s', ...
    'time_end_s','dt_min_s','dt_max_s','all_finite','source_sha256'});
candidateTable.excitation = string(candidateTable.excitation);
candidateTable.method = string(candidateTable.method);
candidateTable.route = string(candidateTable.route);
candidateTable.frequency_band = string(candidateTable.frequency_band);
candidateTable.window_inclusion = string(candidateTable.window_inclusion);
candidateTable.numerator_formula = string(candidateTable.numerator_formula);
candidateTable.normalization = string(candidateTable.normalization);
candidateTable.source_file = string(candidateTable.source_file);
candidateTable.source_sha256 = string(candidateTable.source_sha256);
inputTable.excitation = string(inputTable.excitation);
inputTable.source_file = string(inputTable.source_file);
inputTable.source_sha256 = string(inputTable.source_sha256);
historicalTable = candidateTable(candidateTable.route == "historical_mean_full_range", :);

assert(height(candidateTable) == 264, 'Board19:CandidateCount', ...
    '候选行应为264，实际为%d。', height(candidateTable));
assert(height(historicalTable) == 72, 'Board19:HistoricalCount', ...
    '历史口径行应为72，实际为%d。', height(historicalTable));

writetable(inputTable, fullfile(outputDir, 'nrmse_input_checks_matlab.csv'), 'Encoding', 'UTF-8');
writetable(candidateTable, fullfile(outputDir, 'nrmse_candidates_matlab.csv'), 'Encoding', 'UTF-8');
writetable(historicalTable, fullfile(outputDir, 'nrmse_historical_floor_candidates_matlab.csv'), 'Encoding', 'UTF-8');

summary = struct();
summary.input_files = height(inputTable);
summary.input_checks_pass = all(inputTable.row_count == 40961 & inputTable.column_count == 10 & ...
    inputTable.all_finite & abs(inputTable.dt_min_s-1/1024) <= 5e-15 & ...
    abs(inputTable.dt_max_s-1/1024) <= 5e-15);
summary.total_candidate_rows = height(candidateTable);
summary.historical_candidate_rows = height(historicalTable);
summary.historical_chirp_rows = nnz(historicalTable.excitation == "Chirp");
summary.historical_elcentro_rows = nnz(historicalTable.excitation == "ElCentro");
summary.minimum_reference_range_mm = min(candidateTable.reference_range_mm);
summary.maximum_nrmse_percent = max(candidateTable.nrmse_percent);
summary.status = 'MATLAB_COMPUTATION_COMPLETE_PENDING_INDEPENDENT_CHECK';
write_json(fullfile(outputDir, 'nrmse_matlab_summary.json'), summary);
save(fullfile(outputDir, 'nrmse_matlab.mat'), 'candidateTable', 'historicalTable', ...
    'inputTable', 'summary', '-v7');

fprintf('MATLAB NRMSE完成：输入%d/%d通过，历史口径%d行，全部候选%d行。\n', ...
    nnz(inputTable.all_finite), height(inputTable), height(historicalTable), height(candidateTable));
end

function row = calculate_candidate_row(division, excitation, floor, method, route, ...
    bandId, bandLabel, windowStart, windowEnd, mask, inclusion, useTrapz, ...
    time, error, referenceRange, filename, fileHash)
assert(nnz(mask) >= 2, 'Board19:SegmentSamples', ...
    '%s第%d层%s的%s样本不足。', filename, floor, method, route);
segmentError = error(mask);
if useTrapz
    rmse = sqrt(trapz(time(mask), segmentError.^2) / (windowEnd-windowStart));
    numeratorFormula = 'sqrt(trapz(error^2)/(window_end-window_start))';
else
    rmse = sqrt(mean(segmentError.^2));
    numeratorFormula = 'sqrt(mean(error^2))';
end
nrmse = 100 * rmse / referenceRange;
row = {division, excitation, floor, method, route, bandId, bandLabel, ...
    windowStart, windowEnd, inclusion, nnz(mask), referenceRange, rmse, nrmse, ...
    numeratorFormula, 'full_40s_reference_peak_to_peak', filename, fileHash};
end

function hash = file_hash_from_manifest(boardRoot, copiedRelativePath)
manifest = readtable(fullfile(boardRoot, 'input', 'input_manifest.csv'), ...
    'TextType', 'string', 'VariableNamingRule', 'preserve');
row = find(manifest.copied_relative_path == copiedRelativePath, 1);
assert(~isempty(row), 'Board19:ManifestRow', '冻结清单缺少：%s', copiedRelativePath);
assert(manifest.status(row) == "MATCH", 'Board19:ManifestStatus', ...
    '冻结清单未通过：%s', copiedRelativePath);
hash = manifest.sha256_copy(row);
end

function write_json(path, value)
fid = fopen(path, 'w', 'n', 'UTF-8');
cleaner = onCleanup(@() fclose(fid));
fprintf(fid, '%s\n', jsonencode(value, PrettyPrint=true));
clear cleaner;
end
