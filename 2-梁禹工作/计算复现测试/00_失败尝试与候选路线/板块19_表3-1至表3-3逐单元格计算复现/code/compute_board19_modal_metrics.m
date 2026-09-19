function compute_board19_modal_metrics()
% 从板块17冻结矩阵计算表3-1频率误差与表3-2多种MAC口径。

codeDir = fileparts(mfilename('fullpath'));
boardRoot = fileparts(codeDir);
inputMat = fullfile(boardRoot, 'input', 'board17', 'outputs', 'global_routes_matlab.mat');
outputDir = fullfile(boardRoot, 'outputs', 'modal_matlab');
if ~exist(outputDir, 'dir'); mkdir(outputDir); end

S = load(inputMat, 'MRrt', 'KRrt', 'division1', 'division2');
[Vfull, lambdaFull, fFull] = solve_modes(S.KRrt, S.MRrt);
fullResidual = generalized_residual(S.KRrt, S.MRrt, Vfull, lambdaFull);
assert(fullResidual <= 5e-10, 'Board19:FullEigenResidual', ...
    '完整模型特征残差超限：%.16g', fullResidual);

paperFrequency = zeros(2, 2, 2); % division, method(1=Guyan,2=CB), mode
paperFrequency(1,1,:) = [0.648, 5.411];
paperFrequency(1,2,:) = [0.003, 0.284];
paperFrequency(2,1,:) = [13.040, 24.575];
paperFrequency(2,2,:) = [0.007, 0.834];

paperMac = zeros(2, 2, 2);
paperMac(1,1,:) = [1.0000, 0.9998];
paperMac(1,2,:) = [1.0000, 1.0000];
paperMac(2,1,:) = [0.9962, 0.9255];
paperMac(2,2,:) = [1.0000, 0.9998];

frequencyRows = cell(0, 12);
macRows = cell(0, 12);
residualRows = cell(0, 5);
modal = struct();
modal.Vfull = Vfull;
modal.lambda_full = lambdaFull;
modal.frequency_full_hz = fFull;

for division = 1:2
    D = S.(sprintf('division%d', division));
    master = double(D.master(:));
    nMaster = double(D.n_master);
    assert(numel(master) == nMaster, 'Board19:MasterDimension', '主自由度数量不一致。');

    routeDefs = {
        'Guyan', 'historical_single_sided', D.K_historical, D.M_historical, D.R_guyan_natural;
        'Guyan', 'projected_congruence', D.K_projected, D.M_projected, D.R_guyan_natural;
        'Craig-Bampton', 'sorted_cb', D.K_cb, D.M_cb, D.R_cb_natural;
        'Craig-Bampton', 'raw_cb', D.K_cb_raw, D.M_cb_raw, D.R_cb_raw_natural;
    };

    modal.(sprintf('division%d', division)) = struct();
    for r = 1:size(routeDefs,1)
        method = string(routeDefs{r,1});
        route = string(routeDefs{r,2});
        K = routeDefs{r,3};
        M = routeDefs{r,4};
        recovery = routeDefs{r,5};
        [Vred, lambdaRed, fRed] = solve_modes(K, M);
        residual = generalized_residual(K, M, Vred, lambdaRed);
        residualRows(end+1,:) = {division, method, route, residual, residual <= 5e-10}; %#ok<AGROW>
        routeField = matlab.lang.makeValidName(char(route));
        modal.(sprintf('division%d', division)).(routeField) = struct( ...
            'method', method, 'Vred', Vred, 'lambda', lambdaRed, ...
            'frequency_hz', fRed, 'recovery', recovery, 'residual', residual);

        methodIndex = 1 + double(method == "Craig-Bampton");
        for mode = 1:2
            relError = 100 * abs(fRed(mode) - fFull(mode)) / fFull(mode);
            paperValue = paperFrequency(division, methodIndex, mode);
            roundedValue = round(relError, 3);
            roundedMatch = abs(roundedValue - paperValue) <= 5e-12;
            frequencyRows(end+1,:) = {division, method, route, mode, fFull(mode), ...
                fRed(mode), relError, paperValue, 3, roundedValue, ...
                abs(relError-paperValue), roundedMatch}; %#ok<AGROW>
        end
    end

    % MAC只用表格最可能对应的历史Guyan与升序CB；其他频率路线不混入表值裁决。
    G = modal.(sprintf('division%d', division)).historical_single_sided;
    C = modal.(sprintf('division%d', division)).sorted_cb;
    methodDefs = {
        'Guyan', G.Vred, G.recovery;
        'Craig-Bampton', C.Vred, C.recovery;
    };
    for m = 1:size(methodDefs,1)
        method = string(methodDefs{m,1});
        Vred = methodDefs{m,2};
        recovery = methodDefs{m,3};
        methodIndex = m;
        for mode = 1:2
            phiFull = Vfull(:,mode);
            phiRed = Vred(:,mode);
            phiRecovered = recovery * phiRed;

            add_mac_row('boundary_correct_master', master, phiFull(master), ...
                phiRed(1:nMaster), '作者脚本意图：只比较正确顺序保留坐标');
            add_mac_row('full_recovery_euclidean', (1:15)', phiFull, ...
                phiRecovered, '必要适配：恢复到完整15维后普通欧氏MAC');
            add_mac_row('full_recovery_mass_weighted', (1:15)', phiFull, ...
                phiRecovered, '候选：恢复到完整15维后以完整质量矩阵加权');
            add_mac_row('three_floor_euclidean', [1;6;11], phiFull([1,6,11]), ...
                phiRecovered([1,6,11]), '候选：只比较三层水平位移');
            add_mac_row('first_two_boundary_euclidean', master(1:min(2,nMaster)), ...
                phiFull(master(1:min(2,nMaster))), phiRed(1:min(2,nMaster)), ...
                'motai2.m候选：只比较前两个保留坐标');

            if division == 1
                wrongOrder = [1;11;6;4;9;14];
                add_mac_row('script_literal_wrong_order', wrongOrder, phiFull(wrongOrder), ...
                    phiRed(1:nMaster), 'MAC.m字面顺序：交换自然自由度6与11');
            else
                macRows(end+1,:) = {division, method, 'script_literal_wrong_order', mode, ...
                    6, NaN, paperMac(division,methodIndex,mode), 4, NaN, NaN, false, ...
                    'FAIL_DIMENSION_AND_NMODES：脚本6坐标/6阶，第二类Guyan仅5维'}; %#ok<AGROW>
            end
        end
    end
end

frequencyTable = cell2table(frequencyRows, 'VariableNames', { ...
    'division','method','route','mode','full_frequency_hz','reduced_frequency_hz', ...
    'relative_error_percent','paper_value_percent','printed_decimals','rounded_value', ...
    'absolute_difference_percent','rounded_match'});
macTable = cell2table(macRows, 'VariableNames', { ...
    'division','method','route','mode','coordinate_dimension','mac_value','paper_value', ...
    'printed_decimals','rounded_value','absolute_difference','rounded_match','interpretation'});
residualTable = cell2table(residualRows, 'VariableNames', { ...
    'division','method','route','relative_eigen_residual','pass'});

writetable(frequencyTable, fullfile(outputDir, 'frequency_candidates_matlab.csv'), 'Encoding', 'UTF-8');
writetable(macTable, fullfile(outputDir, 'mac_candidates_matlab.csv'), 'Encoding', 'UTF-8');
writetable(residualTable, fullfile(outputDir, 'modal_eigen_residuals_matlab.csv'), 'Encoding', 'UTF-8');

table31 = frequencyTable((frequencyTable.route == "historical_single_sided" & frequencyTable.method == "Guyan") | ...
    (frequencyTable.route == "sorted_cb" & frequencyTable.method == "Craig-Bampton"), :);
table31.evidence_label = repmat("历史值/待决定", height(table31), 1);
table31.evidence_label(table31.rounded_match) = "计算级复现候选（待Python独立复算）";
table31.formula = repmat("100*abs(f_full-f_red)/f_full", height(table31), 1);
table31.source_route = table31.route;
writetable(table31, fullfile(outputDir, 'table3_1_cell_adjudication_matlab.csv'), 'Encoding', 'UTF-8');

table32 = macTable(macTable.route == "boundary_correct_master", :);
table32.evidence_label = repmat("历史值/待决定", height(table32), 1);
table32.evidence_label(table32.rounded_match) = "计算级复现候选（待Python独立复算）";
table32.formula = repmat("abs(phi_full'*phi_red)^2/((phi_full'*phi_full)*(phi_red'*phi_red))", height(table32), 1);
writetable(table32, fullfile(outputDir, 'table3_2_cell_adjudication_matlab.csv'), 'Encoding', 'UTF-8');

summary = struct();
summary.full_model_first_two_frequency_hz = fFull(1:2).';
summary.full_model_relative_eigen_residual = fullResidual;
summary.frequency_candidate_rows = height(frequencyTable);
summary.mac_candidate_rows = height(macTable);
summary.table3_1_target_cells = height(table31);
summary.table3_1_rounded_matches = nnz(table31.rounded_match);
summary.table3_2_target_cells = height(table32);
summary.table3_2_rounded_matches = nnz(table32.rounded_match);
summary.maximum_reduced_eigen_residual = max(residualTable.relative_eigen_residual);
summary.status = 'MATLAB_COMPUTATION_COMPLETE_PENDING_INDEPENDENT_CHECK';
write_json(fullfile(outputDir, 'modal_metrics_matlab_summary.json'), summary);
save(fullfile(outputDir, 'modal_metrics_matlab.mat'), 'modal', 'frequencyTable', 'macTable', ...
    'residualTable', 'table31', 'table32', 'summary', '-v7');

fprintf('MATLAB模态指标完成：表3-1命中%d/%d，表3-2命中%d/%d，最大特征残差=%.3e。\n', ...
    summary.table3_1_rounded_matches, summary.table3_1_target_cells, ...
    summary.table3_2_rounded_matches, summary.table3_2_target_cells, ...
    summary.maximum_reduced_eigen_residual);

    function add_mac_row(routeName, coordinateIds, vectorFull, vectorReduced, interpretation)
        if strcmp(routeName, 'full_recovery_mass_weighted')
            value = weighted_mac(vectorFull, vectorReduced, S.MRrt);
        else
            value = euclidean_mac(vectorFull, vectorReduced);
        end
        paperValue = paperMac(division, methodIndex, mode);
        roundedValue = round(value, 4);
        roundedMatch = abs(roundedValue-paperValue) <= 5e-12;
        macRows(end+1,:) = {division, method, routeName, mode, numel(coordinateIds), ...
            value, paperValue, 4, roundedValue, abs(value-paperValue), roundedMatch, interpretation}; %#ok<AGROW>
    end
end

function [V, lambda, frequencyHz] = solve_modes(K, M)
[V, lambda] = eig(K, M, 'vector');
[~, order] = sort(real(lambda), 'ascend');
lambda = lambda(order);
V = V(:,order);
imagRatio = max(abs(imag(lambda)) ./ max(abs(real(lambda)), eps));
assert(imagRatio <= 1e-10, 'Board19:ComplexEigenvalue', ...
    '广义特征值虚部比例超限：%.16g', imagRatio);
lambda = real(lambda);
V = real(V);
assert(all(lambda > 0), 'Board19:NonPositiveEigenvalue', '出现非正广义特征值。');
for i = 1:size(V,2)
    V(:,i) = V(:,i) / norm(V(:,i));
end
frequencyHz = sqrt(lambda) / (2*pi);
end

function value = euclidean_mac(a, b)
a = a(:); b = b(:);
assert(numel(a) == numel(b), 'Board19:MacDimension', 'MAC向量维数不一致。');
value = abs(a' * b)^2 / real((a' * a) * (b' * b));
value = real(value);
end

function value = weighted_mac(a, b, W)
a = a(:); b = b(:);
assert(numel(a) == size(W,1) && numel(b) == size(W,2), ...
    'Board19:WeightedMacDimension', '质量加权MAC维数不一致。');
value = abs(a' * W * b)^2 / real((a' * W * a) * (b' * W * b));
value = real(value);
end

function value = generalized_residual(K, M, V, lambda)
numerator = norm(K*V - M*V*diag(lambda), 'fro');
denominator = max(norm(K*V, 'fro'), eps);
value = numerator / denominator;
end

function write_json(path, value)
fid = fopen(path, 'w', 'n', 'UTF-8');
cleaner = onCleanup(@() fclose(fid));
fprintf(fid, '%s\n', jsonencode(value, PrettyPrint=true));
clear cleaner;
end
