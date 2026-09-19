function compute_board21_step4_formulas(inputRoot, outputRoot, executionToken)
% Independent MATLAB implementation of Liang Yu thesis Eqs. (4-41)--(4-45)
% and the seven preserved historical energy-script variants.

if nargin < 3
    executionToken = '';
end
inputRoot = char(inputRoot);
outputRoot = char(outputRoot);
executionToken = char(executionToken);
if isfolder(outputRoot) || isfile(outputRoot)
    error('BOARD21:S4:OutputExists', 'Exclusive output already exists: %s', outputRoot);
end
if ~isfolder(inputRoot)
    error('BOARD21:S4:InputMissing', 'Input root does not exist: %s', inputRoot);
end

stageSummary = jsondecode(fileread(fullfile(inputRoot, 'staging_summary.json')));
assert(strcmp(stageSummary.status, 'PASS'));
assert(stageSummary.step3_run_case_count == 14);
assert(stageSummary.total_manifest_item_count == 103);
assert(~stageSummary.table4_1_adjudicated);

caseIndex = readtable(fullfile(inputRoot, 'case_index.csv'), ...
    'TextType', 'string', 'VariableNamingRule', 'preserve');
assert(height(caseIndex) == 14);
assert(numel(unique(caseIndex.case_id)) == 14);

mkdir(outputRoot);
valueFile = fullfile(outputRoot, 'values.csv');
resultFile = fullfile(outputRoot, 'case_results.csv');
W = openValueWriter(valueFile);
R = openResultWriter(resultFile);
cleanupObject = onCleanup(@() closeWriters(W, R)); %#ok<NASGU>

for caseNumber = 1:height(caseIndex)
    relativeDir = char(caseIndex.staged_relative_dir(caseNumber));
    caseRoot = fullfile(inputRoot, strrep(relativeDir, '/', filesep));
    spec = jsondecode(fileread(fullfile(caseRoot, 'case.json')));
    assert(strcmp(spec.case_id, char(caseIndex.case_id(caseNumber))));
    assert(strcmp(spec.route_id, char(caseIndex.route_id(caseNumber))));
    data = load(fullfile(caseRoot, char(spec.workspace_file)));
    target = load(fullfile(caseRoot, char(spec.historical_target_file)), ...
        'E_total', 'E_total_guyan', 'E_total_cb', ...
        'energy_sum_orig', 'energy_sum_guyan', 'energy_sum_cb', ...
        'total_increase_guyan', 'total_increase_cb');
    [W, R] = runHistoricalCase(spec, data, target, W, R);
    [W, R] = runPaperCase(spec, data, W, R);
end
[W, R] = runWholeModelCases(inputRoot, W, R);

fclose(W.fid); W.fid = -1;
fclose(R.fid); R.fid = -1;

summary = struct();
summary.schema_version = 'BOARD21_STEP4_COMPUTE_V1';
summary.implementation = 'MATLAB_EIG_INDEPENDENT';
summary.status = 'PASS';
summary.input_case_count = 14;
summary.whole_model_candidate_count = 2;
summary.value_row_count = W.count;
summary.case_result_count = R.count;
summary.historical_result_count = R.historicalCount;
summary.paper_conditional_result_count = R.paperCount;
summary.author_route_reproduction_count = R.historicalCount;
summary.max_author_abs_error = R.maxAuthorError;
summary.formula_4_45_evaluated_conditionally = true;
summary.table4_1_adjudicated = false;
summary.scientific_status = ...
    'AUTHOR_ROUTE_REPRODUCED_AND_PAPER_LITERAL_CONDITIONAL_TABLE4_1_PENDING';
summary.values_sha256 = sha256File(valueFile);
summary.case_results_sha256 = sha256File(resultFile);
summaryFile = fullfile(outputRoot, 'compute_summary.json');
writeJsonNew(summaryFile, summary);

manifestFile = fullfile(outputRoot, 'output_manifest.csv');
fid = fopenNewUtf8(manifestFile);
fprintf(fid, ['artifact_order,relative_path,size_bytes,sha256,' ...
    'manifest_scope%c'], 10);
payloadNames = {'values.csv', 'case_results.csv', 'compute_summary.json'};
for index = 1:numel(payloadNames)
    path = fullfile(outputRoot, payloadNames{index});
    info = dir(path);
    fprintf(fid, '%d,%s,%d,%s,%s%c', index, payloadNames{index}, ...
        info.bytes, sha256File(path), ...
        'CANONICAL_PAYLOAD_EXCLUDING_OUTPUT_MANIFEST_ITSELF', 10);
end
fclose(fid);

terminal = summary;
terminal.execution_token = executionToken;
fprintf('%s\n', jsonencode(terminal));
end


function W = openValueWriter(path)
W = struct();
W.fid = fopenNewUtf8(path);
W.count = 0;
header = ['row_order,case_id,scope,coordinate_identity,route_variant,' ...
    'result_identity,excitation_identity,recovery_identity,mode_count,' ...
    'model,quantity,row,column,value,value_status,uncertainty_flags'];
fprintf(W.fid, '%s%c', header, 10);
end


function R = openResultWriter(path)
R = struct();
R.fid = fopenNewUtf8(path);
R.count = 0;
R.historicalCount = 0;
R.paperCount = 0;
R.maxAuthorError = 0;
header = ['result_order,case_id,scope,coordinate_identity,route_variant,' ...
    'result_identity,excitation_identity,recovery_identity,mode_count,' ...
    'comparison_model,eq445_sum,eq445_status,historical_total_percent,' ...
    'author_target_percent,author_abs_error,boundary_status'];
fprintf(R.fid, '%s%c', header, 10);
end


function closeWriters(W, R)
if isfield(W, 'fid') && W.fid > 0
    closeIfStillOpen(W.fid);
end
if isfield(R, 'fid') && R.fid > 0
    closeIfStillOpen(R.fid);
end
end


function closeIfStillOpen(fileId)
fileName = fopen(fileId);
if ~isempty(fileName)
    fclose(fileId);
end
end


function fid = fopenNewUtf8(path)
if isfile(path) || isfolder(path)
    error('BOARD21:S4:FileExists', 'Exclusive file already exists: %s', path);
end
[fid, message] = fopen(path, 'w', 'n', 'UTF-8');
if fid < 0
    error('BOARD21:S4:OpenFailed', 'Cannot open %s: %s', path, message);
end
end


function writeJsonNew(path, value)
fid = fopenNewUtf8(path);
payload = jsonencode(value, PrettyPrint=true);
fprintf(fid, '%s%c', payload, 10);
fclose(fid);
end


function context = makeContext(caseId, scope, coordinateIdentity, ...
        routeVariant, resultIdentity, excitationIdentity, recoveryIdentity, modeCount)
context = struct();
context.case_id = char(caseId);
context.scope = char(scope);
context.coordinate_identity = char(coordinateIdentity);
context.route_variant = char(routeVariant);
context.result_identity = char(resultIdentity);
context.excitation_identity = char(excitationIdentity);
context.recovery_identity = char(recoveryIdentity);
context.mode_count = modeCount;
end


function text = canonicalNumber(value)
assert(isscalar(value) && isreal(value) && isfinite(value));
if value == 0
    value = 0;
end
text = sprintf('%.17g', value);
end


function assertCsvText(value)
value = char(value);
assert(~contains(value, ',') && ~contains(value, '"') && ...
    ~contains(value, sprintf('\r')) && ~contains(value, sprintf('\n')));
end


function W = emitArray(W, context, model, quantity, value, status, flags)
if nargin < 7
    flags = '';
end
if nargin < 6
    status = 'FINITE';
end
assert(isnumeric(value) && isreal(value) && all(isfinite(value(:))));
strings = {context.case_id, context.scope, context.coordinate_identity, ...
    context.route_variant, context.result_identity, context.excitation_identity, ...
    context.recovery_identity, model, quantity, status, flags};
for index = 1:numel(strings)
    assertCsvText(strings{index});
end
if isscalar(value)
    W = emitValue(W, context, model, quantity, 0, 0, value, status, flags);
elseif isvector(value)
    vector = value(:);
    for row = 1:numel(vector)
        W = emitValue(W, context, model, quantity, row, 0, vector(row), status, flags);
    end
elseif ismatrix(value)
    for row = 1:size(value, 1)
        for column = 1:size(value, 2)
            W = emitValue(W, context, model, quantity, row, column, ...
                value(row, column), status, flags);
        end
    end
else
    error('BOARD21:S4:Rank', 'Cannot emit rank greater than two.');
end
end


function W = emitValue(W, context, model, quantity, row, column, value, status, flags)
W.count = W.count + 1;
fprintf(W.fid, '%d,%s,%s,%s,%s,%s,%s,%s,%d,%s,%s,%d,%d,%s,%s,%s%c', ...
    W.count, context.case_id, context.scope, context.coordinate_identity, ...
    context.route_variant, context.result_identity, context.excitation_identity, ...
    context.recovery_identity, context.mode_count, model, quantity, row, column, ...
    canonicalNumber(value), status, flags, 10);
end


function W = emitModal(W, context, model, A, flags)
quantities = { ...
    'input_M', A.M; ...
    'input_K', A.K; ...
    'input_r', A.r; ...
    'eigenvalue', A.eigenvalue; ...
    'frequency_hz', A.frequency_hz; ...
    'phi_mass_normalized', A.phi; ...
    'eq441_numerator', A.gamma_numerator; ...
    'eq441_denominator', A.gamma_denominator; ...
    'eq441_gamma', A.gamma; ...
    'eq442_gamma_sq', A.gamma_sq; ...
    'eq442_gamma_sq_sum', A.participation_denominator; ...
    'eq442_participation_ratio', A.participation_ratio; ...
    'eq443_energy_raw', A.energy_raw; ...
    'eq443_energy_column_sum', A.energy_column_sum; ...
    'eq443_energy_normalized', A.energy_normalized; ...
    'energy_used_by_branch', A.energy_used; ...
    'eq444_energy_total', A.energy_total; ...
    'invariant_participation_sum', sum(A.participation_ratio); ...
    'invariant_energy_total_sum', sum(A.energy_total); ...
    'invariant_max_modal_mass_error', max(abs(A.gamma_denominator - 1))};
for index = 1:size(quantities, 1)
    W = emitArray(W, context, model, quantities{index, 1}, ...
        quantities{index, 2}, 'FINITE', flags);
end
end


function W = emitModeSensitivity(W, context, model, A, flags)
vectorQuantities = { ...
    'eigenvalue', A.eigenvalue; ...
    'frequency_hz', A.frequency_hz; ...
    'eq441_numerator', A.gamma_numerator; ...
    'eq441_denominator', A.gamma_denominator; ...
    'eq441_gamma', A.gamma; ...
    'eq442_gamma_sq', A.gamma_sq; ...
    'eq442_participation_ratio', A.participation_ratio};
for index = 1:size(vectorQuantities, 1)
    W = emitVector(W, context, model, vectorQuantities{index, 1}, ...
        vectorQuantities{index, 2}, 'FINITE', flags);
end
scalarAndDofQuantities = { ...
    'eq442_gamma_sq_sum', A.participation_denominator; ...
    'eq444_energy_total', A.energy_total; ...
    'invariant_participation_sum', sum(A.participation_ratio); ...
    'invariant_energy_total_sum', sum(A.energy_total); ...
    'invariant_max_modal_mass_error', max(abs(A.gamma_denominator - 1))};
for index = 1:size(scalarAndDofQuantities, 1)
    W = emitArray(W, context, model, scalarAndDofQuantities{index, 1}, ...
        scalarAndDofQuantities{index, 2}, 'FINITE', flags);
end
end


function W = emitVector(W, context, model, quantity, value, status, flags)
vector = value(:);
assert(~isempty(vector) && isreal(vector) && all(isfinite(vector)));
for row = 1:numel(vector)
    W = emitValue(W, context, model, quantity, row, 0, vector(row), status, flags);
end
end


function [eigenvalue, phi] = solveModes(M, K)
assertSquare(M, 'M');
assertSquare(K, 'K');
assert(isequal(size(M), size(K)));
scaleM = max(1, norm(M, 'fro'));
scaleK = max(1, norm(K, 'fro'));
assert(norm(M - M', 'fro') <= 1e-10 * scaleM);
assert(norm(K - K', 'fro') <= 1e-10 * scaleK);
[~, cholStatus] = chol(M);
assert(cholStatus == 0);
[phi, eigenvalue] = eig(K, M, 'vector');
assert(isreal(phi) && isreal(eigenvalue));
[eigenvalue, order] = sort(real(eigenvalue), 'ascend');
phi = real(phi(:, order));
assert(all(isfinite(eigenvalue)) && all(eigenvalue > 0));
phi = canonicalizeModes(M, phi);
residual = norm(K * phi - M * phi * diag(eigenvalue), 'fro');
scale = max(1, norm(K * phi, 'fro'));
assert(residual / scale <= 1e-10);
end


function phi = canonicalizeModes(M, phi)
for index = 1:size(phi, 2)
    denominator = phi(:, index)' * M * phi(:, index);
    assert(isfinite(denominator) && denominator > 0);
    phi(:, index) = phi(:, index) / sqrt(denominator);
    [~, pivot] = max(abs(phi(:, index)));
    if phi(pivot, index) < 0
        phi(:, index) = -phi(:, index);
    end
end
end


function assertSquare(value, name)
if ~ismatrix(value) || size(value, 1) ~= size(value, 2) || ...
        ~isreal(value) || ~all(isfinite(value(:)))
    error('BOARD21:S4:Matrix', '%s is not a finite real square matrix.', name);
end
end


function A = analyzeModal(M, K, r, modeCount, normalizeEnergy)
[eigenvalue, phi] = solveModes(M, K);
A = modalFromBasis(M, K, r, eigenvalue, phi, modeCount, normalizeEnergy);
end


function A = modalFromBasis(M, K, r, eigenvalue, phi, modeCount, normalizeEnergy)
assertSquare(M, 'M');
assertSquare(K, 'K');
r = double(r(:));
eigenvalue = double(eigenvalue(:));
assert(numel(r) == size(M, 1));
assert(size(phi, 1) == size(M, 1) && size(phi, 2) == numel(eigenvalue));
if modeCount == -1
    count = numel(eigenvalue);
else
    count = modeCount;
end
assert(count >= 1 && count <= numel(eigenvalue));
eigenvalue = eigenvalue(1:count);
phi = canonicalizeModes(M, phi(:, 1:count));
gammaNumerator = phi' * M * r;
gammaDenominator = diag(phi' * M * phi);
assert(all(abs(gammaDenominator) > 1e-15));
gamma = gammaNumerator ./ gammaDenominator;
gammaSq = gamma .^ 2;
participationDenominator = sum(gammaSq);
assert(isfinite(participationDenominator) && participationDenominator > 0);
participationRatio = gammaSq / participationDenominator;
energyRaw = 0.5 .* (diag(M) * eigenvalue') .* (phi .^ 2);
energyColumnSum = sum(energyRaw, 1)';
assert(all(abs(energyColumnSum) > 1e-15));
energyNormalized = energyRaw ./ energyColumnSum';
if normalizeEnergy
    energyUsed = energyNormalized;
else
    energyUsed = energyRaw;
end
energyTotal = energyUsed * participationRatio;
assert(all(isfinite(energyTotal)));
A = struct();
A.M = M; A.K = K; A.r = r;
A.eigenvalue = eigenvalue;
A.frequency_hz = sqrt(eigenvalue) / (2*pi);
A.phi = phi;
A.gamma_numerator = gammaNumerator;
A.gamma_denominator = gammaDenominator;
A.gamma = gamma;
A.gamma_sq = gammaSq;
A.participation_denominator = participationDenominator;
A.participation_ratio = participationRatio;
A.energy_raw = energyRaw;
A.energy_column_sum = energyColumnSum;
A.energy_normalized = energyNormalized;
A.energy_used = energyUsed;
A.energy_total = energyTotal;
end


function A = recoveredAnalysis(fullM, fullK, fullR, transform, reduced)
physicalPhi = transform * reduced.phi;
A = modalFromBasis(fullM, fullK, fullR, reduced.eigenvalue, ...
    physicalPhi, numel(reduced.eigenvalue), true);
end


function [literal, direction] = authorVectors(spec, rawM)
dimension = size(rawM, 1);
rule = char(spec.excitation_rule);
switch rule
    case 'BINARY_FIRST_3'
        literal = zeros(dimension, 1); literal(1:3) = 1;
        direction = literal;
    case 'BINARY_FIRST_2'
        literal = zeros(dimension, 1); literal(1:2) = 1;
        direction = literal;
    case 'MASS_TIMES_ONES'
        direction = ones(dimension, 1);
        literal = rawM * direction;
    otherwise
        error('BOARD21:S4:Excitation', 'Unknown excitation rule: %s', rule);
end
end


function value = dynamicField(data, name)
name = char(name);
if ~isfield(data, name)
    error('BOARD21:S4:Variable', 'Workspace is missing variable %s.', name);
end
value = double(data.(name));
assert(isreal(value) && all(isfinite(value(:))));
end


function T = checkedTransform(value, fullSize, name)
T = double(value);
if ~ismatrix(T) || size(T, 1) ~= fullSize || ~isreal(T) || ~all(isfinite(T(:)))
    error('BOARD21:S4:Transform', 'Transform %s has invalid shape/content.', char(name));
end
end


function value = scopedSum(vector, indices, scope)
vector = vector(:);
scope = char(scope);
if strcmp(scope, 'ALL')
    value = sum(vector);
elseif strcmp(scope, 'SELECTED')
    indices = double(indices(:));
    assert(all(indices >= 1) && all(indices <= numel(vector)));
    value = sum(vector(indices));
else
    error('BOARD21:S4:Scope', 'Unknown sum scope: %s', scope);
end
end


function [W, R] = runHistoricalCase(spec, data, target, W, R)
rawM = dynamicField(data, spec.full_M);
rawK = dynamicField(data, spec.full_K);
assertSquare(rawM, char(spec.full_M));
assertSquare(rawK, char(spec.full_K));
order = double(spec.consumer_order(:));
fullM = rawM(order, order);
fullK = rawK(order, order);
[literal, ~] = authorVectors(spec, fullM);
T = checkedTransform(dynamicField(data, spec.guyan_T), size(fullM, 1), spec.guyan_T);
Tcb = checkedTransform(dynamicField(data, spec.cb_T), size(fullM, 1), spec.cb_T);
Mg = dynamicField(data, spec.guyan_M); Kg = dynamicField(data, spec.guyan_K);
Mcb = dynamicField(data, spec.cb_M); Kcb = dynamicField(data, spec.cb_K);
normalizeEnergy = logical(spec.energy_normalized);
original = analyzeModal(fullM, fullK, literal, -1, normalizeEnergy);
guyan = analyzeModal(Mg, Kg, T' * literal, -1, normalizeEnergy);
cb = analyzeModal(Mcb, Kcb, Tcb' * literal, -1, normalizeEnergy);
context = makeContext(spec.case_id, 'HISTORICAL', 'AUTHOR_CONSUMER_ORDER', ...
    'AUTHOR_HISTORICAL_FORMULA', 'AUTHOR_ROUTE_REPRODUCED', ...
    'AUTHOR_LITERAL', 'REDUCED_GENERALIZED', -1);
flags = char(spec.coordinate_status);
W = emitArray(W, context, 'guyan', 'input_T', T, 'FINITE', flags);
W = emitArray(W, context, 'cb', 'input_T', Tcb, 'FINITE', flags);
W = emitModal(W, context, 'orig', original, flags);
W = emitModal(W, context, 'guyan', guyan, flags);
W = emitModal(W, context, 'cb', cb, flags);
sOrig = scopedSum(original.energy_total, spec.d_orig, spec.orig_sum_scope);
sGuyan = scopedSum(guyan.energy_total, spec.d_guyan, spec.guyan_sum_scope);
sCb = scopedSum(cb.energy_total, spec.d_cb, spec.cb_sum_scope);
if strcmp(char(spec.historical_denominator), 'ORIGINAL')
    denominator = sOrig;
else
    denominator = sGuyan;
end
assert(denominator ~= 0);
totalG = (sGuyan - sOrig) / denominator * 100;
totalCb = (sCb - sOrig) / denominator * 100;
targetG = double(target.total_increase_guyan);
targetCb = double(target.total_increase_cb);
computedVectors = {original.energy_total, guyan.energy_total, cb.energy_total};
targetVectors = {target.E_total, target.E_total_guyan, target.E_total_cb};
models = {'orig', 'guyan', 'cb'};
for index = 1:3
    computed = computedVectors{index}(:);
    saved = double(targetVectors{index}(:));
    assert(isequal(size(computed), size(saved)));
    W = emitArray(W, context, models{index}, 'author_saved_energy_total', ...
        saved, 'FINITE', flags);
    W = emitArray(W, context, models{index}, ...
        'author_saved_energy_total_abs_error', abs(computed - saved), 'FINITE', flags);
end
W = emitArray(W, context, 'orig', 'historical_energy_sum', sOrig, 'FINITE', flags);
W = emitArray(W, context, 'guyan', 'historical_energy_sum', sGuyan, 'FINITE', flags);
W = emitArray(W, context, 'cb', 'historical_energy_sum', sCb, 'FINITE', flags);
W = emitArray(W, context, 'guyan', 'historical_total_increase_percent', totalG, 'FINITE', flags);
W = emitArray(W, context, 'cb', 'historical_total_increase_percent', totalCb, 'FINITE', flags);
W = emitArray(W, context, 'guyan', 'author_saved_total_increase_percent', targetG, 'FINITE', flags);
W = emitArray(W, context, 'cb', 'author_saved_total_increase_percent', targetCb, 'FINITE', flags);
assert(max(abs([totalG-targetG, totalCb-targetCb])) <= 1e-8);
R = addResult(R, context, 'guyan', [], 'NOT_EQ445', ...
    [flags '|HISTORICAL_RATIO_OF_SUMS_PERCENT'], totalG, targetG);
R = addResult(R, context, 'cb', [], 'NOT_EQ445', ...
    [flags '|HISTORICAL_RATIO_OF_SUMS_PERCENT'], totalCb, targetCb);
end


function [numerator, denominator, ratio, total, status] = equation445(original, reduced, dOrig, dReduced)
original = original(:); reduced = reduced(:);
dOrig = double(dOrig(:)); dReduced = double(dReduced(:));
assert(numel(dOrig) == numel(dReduced) && ~isempty(dOrig));
assert(all(dOrig >= 1) && all(dOrig <= numel(original)));
assert(all(dReduced >= 1) && all(dReduced <= numel(reduced)));
denominator = original(dOrig);
numerator = reduced(dReduced) - denominator;
if any(denominator == 0)
    ratio = zeros(size(numerator)); total = 0;
    status = 'UNDEFINED_DENOMINATOR';
else
    ratio = numerator ./ denominator;
    total = sum(ratio);
    if any(abs(denominator) <= 1e-14)
        status = 'ILL_CONDITIONED';
    else
        status = 'FINITE';
    end
end
end


function [W, total, status] = emitEquation445(W, context, model, ...
        original, reduced, dOrig, dReduced, flags)
[numerator, denominator, ratio, total, status] = ...
    equation445(original, reduced, dOrig, dReduced);
W = emitArray(W, context, model, 'eq445_numerator', numerator, status, flags);
W = emitArray(W, context, model, 'eq445_denominator', denominator, status, flags);
if ~strcmp(status, 'UNDEFINED_DENOMINATOR')
    W = emitArray(W, context, model, 'eq445_signed_ratio', ratio, status, flags);
    W = emitArray(W, context, model, 'eq445_signed_sum', total, status, flags);
end
end


function R = addResult(R, context, comparisonModel, eq445Sum, eq445Status, ...
        boundaryStatus, historicalTotal, authorTarget)
if nargin < 8
    authorTarget = [];
end
if nargin < 7
    historicalTotal = [];
end
R.count = R.count + 1;
if strcmp(context.scope, 'HISTORICAL')
    R.historicalCount = R.historicalCount + 1;
elseif strcmp(context.scope, 'PAPER')
    R.paperCount = R.paperCount + 1;
end
if isempty(eq445Sum), eqText = ''; else, eqText = canonicalNumber(eq445Sum); end
if isempty(historicalTotal), histText = ''; else, histText = canonicalNumber(historicalTotal); end
if isempty(authorTarget)
    targetText = ''; errorText = '';
else
    targetText = canonicalNumber(authorTarget);
    errorValue = abs(historicalTotal - authorTarget);
    errorText = canonicalNumber(errorValue);
    R.maxAuthorError = max(R.maxAuthorError, errorValue);
end
strings = {comparisonModel, eq445Status, boundaryStatus};
for index = 1:numel(strings), assertCsvText(strings{index}); end
fprintf(R.fid, '%d,%s,%s,%s,%s,%s,%s,%s,%d,%s,%s,%s,%s,%s,%s,%s%c', ...
    R.count, context.case_id, context.scope, context.coordinate_identity, ...
    context.route_variant, context.result_identity, context.excitation_identity, ...
    context.recovery_identity, context.mode_count, comparisonModel, eqText, ...
    eq445Status, histText, targetText, errorText, boundaryStatus, 10);
end


function [W, R] = paperVariants(caseId, coordinateIdentity, boundary, ...
        fullM, fullK, literal, direction, T, MgHist, KgHist, ...
        Tcb, Mcb, Kcb, dOrig, dGuyan, dCb, W, R)
MgStandard = T' * fullM * T;
KgStandard = T' * fullK * T;
variants = { ...
    struct('id', 'GUYAN_HISTORICAL_ONESIDED', 'model', 'guyan', ...
        'T', T, 'M', MgHist, 'K', KgHist, 'd', dGuyan), ...
    struct('id', 'GUYAN_STANDARD_CONGRUENT', 'model', 'guyan', ...
        'T', T, 'M', MgStandard, 'K', KgStandard, 'd', dGuyan), ...
    struct('id', 'CB_SAVED_CONGRUENT', 'model', 'cb', ...
        'T', Tcb, 'M', Mcb, 'K', Kcb, 'd', dCb)};
excitationIdentities = {'AUTHOR_LITERAL', 'FORCE_CONSISTENT_INFERENCE'};
[fullEigenvalue, fullPhi] = solveModes(fullM, fullK);
for excitationIndex = 1:numel(excitationIdentities)
    excitationIdentity = excitationIdentities{excitationIndex};
    if strcmp(excitationIdentity, 'AUTHOR_LITERAL')
        fullR = literal;
    else
        fullR = direction;
    end
    for variantIndex = 1:numel(variants)
        V = variants{variantIndex};
        if strcmp(excitationIdentity, 'AUTHOR_LITERAL')
            reducedR = V.T' * literal;
        else
            reducedForce = V.T' * fullM * direction;
            reducedR = V.M \ reducedForce;
        end
        [reducedEigenvalue, reducedPhi] = solveModes(V.M, V.K);
        maximumCommon = min(numel(fullEigenvalue), numel(reducedEigenvalue));
        modeCounts = [-1, 1:maximumCommon];
        for modeIndex = 1:numel(modeCounts)
            modeCount = modeCounts(modeIndex);
            original = modalFromBasis(fullM, fullK, fullR, ...
                fullEigenvalue, fullPhi, modeCount, true);
            reduced = modalFromBasis(V.M, V.K, reducedR, ...
                reducedEigenvalue, reducedPhi, modeCount, true);
            if strcmp(V.model, 'cb')
                directRecovery = 'CB_REDUCED_GENERALIZED';
            else
                directRecovery = 'GUYAN_REDUCED_GENERALIZED';
            end
            context = makeContext(caseId, 'PAPER', coordinateIdentity, ...
                V.id, 'PAPER_LITERAL_CONDITIONAL', excitationIdentity, ...
                directRecovery, modeCount);
            flags = [boundary ...
                '|INPUT_IDENTITY_UNRESOLVED|MODE_COUNT_UNSPECIFIED|' ...
                'D_SET_UNSPECIFIED|WHOLE_VS_LOCAL_MODEL_UNRESOLVED'];
            if strcmp(V.model, 'cb')
                flags = [flags '|CB_ANALOGY_NOT_PRINTED_IN_EQ445|CB_RECOVERY_UNSPECIFIED'];
            end
            if modeCount == -1
                W = emitArray(W, context, V.model, 'input_T', V.T, 'FINITE', flags);
                W = emitModal(W, context, 'orig', original, flags);
                W = emitModal(W, context, V.model, reduced, flags);
            else
                W = emitModeSensitivity(W, context, 'orig', original, flags);
                W = emitModeSensitivity(W, context, V.model, reduced, flags);
            end
            [W, total, status] = emitEquation445(W, context, V.model, ...
                original.energy_total, reduced.energy_total, dOrig, V.d, flags);
            R = addResult(R, context, V.model, total, status, flags);

            recovered = recoveredAnalysis(fullM, fullK, fullR, V.T, reduced);
            if strcmp(V.model, 'cb')
                recoveredIdentity = 'CB_PHYSICAL_RECOVERY_INFERENCE';
            else
                recoveredIdentity = 'GUYAN_PHYSICAL_RECOVERY_INFERENCE';
            end
            recoveredContext = makeContext(caseId, 'PAPER', coordinateIdentity, ...
                V.id, 'PAPER_LITERAL_CONDITIONAL', excitationIdentity, ...
                recoveredIdentity, modeCount);
            if modeCount == -1
                W = emitArray(W, recoveredContext, V.model, 'input_T', V.T, 'FINITE', flags);
                W = emitModal(W, recoveredContext, 'orig', original, flags);
                W = emitModal(W, recoveredContext, V.model, recovered, flags);
            else
                W = emitModeSensitivity(W, recoveredContext, 'orig', original, flags);
                W = emitModeSensitivity(W, recoveredContext, V.model, recovered, flags);
            end
            [W, total, status] = emitEquation445(W, recoveredContext, V.model, ...
                original.energy_total, recovered.energy_total, dOrig, dOrig, flags);
            R = addResult(R, recoveredContext, V.model, total, status, flags);
        end
    end
end
end


function [W, R] = runPaperCase(spec, data, W, R)
rawM = dynamicField(data, spec.full_M);
rawK = dynamicField(data, spec.full_K);
assertSquare(rawM, char(spec.full_M)); assertSquare(rawK, char(spec.full_K));
T = checkedTransform(dynamicField(data, spec.guyan_T), size(rawM, 1), spec.guyan_T);
Tcb = checkedTransform(dynamicField(data, spec.cb_T), size(rawM, 1), spec.cb_T);
Mg = dynamicField(data, spec.guyan_M); Kg = dynamicField(data, spec.guyan_K);
Mcb = dynamicField(data, spec.cb_M); Kcb = dynamicField(data, spec.cb_K);
consumer = double(spec.consumer_order(:));
producer = double(spec.producer_order(:));
coordinateIdentities = {'AUTHOR_CONSUMER_ORDER'};
orders = {consumer};
boundaries = {char(spec.coordinate_status)};
if ~isequal(consumer, producer)
    coordinateIdentities{end+1} = 'PRODUCER_ALIGNED_ORDER'; %#ok<AGROW>
    orders{end+1} = producer; %#ok<AGROW>
    boundaries{end+1} = 'COORDINATE_ALIGNMENT_INFERENCE'; %#ok<AGROW>
end
for index = 1:numel(orders)
    order = orders{index};
    fullM = rawM(order, order); fullK = rawK(order, order);
    [literal, direction] = authorVectors(spec, fullM);
    [W, R] = paperVariants(spec.case_id, coordinateIdentities{index}, ...
        boundaries{index}, fullM, fullK, literal, direction, ...
        T, Mg, Kg, Tcb, Mcb, Kcb, spec.d_orig, spec.d_guyan, spec.d_cb, W, R);
end
end


function [W, R] = runWholeModelCases(inputRoot, W, R)
G = load(fullfile(inputRoot, 'g', 'gr.mat'), 'division1', 'division2');
for division = 1:2
    D = G.(sprintf('division%d', division));
    fullM = double(D.Mo); fullK = double(D.Ko);
    T = double(D.T); Tcb = double(D.T_cb);
    Mg = double(D.M_historical); Kg = double(D.K_historical);
    Mcb = double(D.M_cb); Kcb = double(D.K_cb);
    direction = double(D.force_mask_ordered(:));
    if division == 1, d = [1, 2, 3]; else, d = [1, 2]; end
    boundary = ['WHOLE_MODEL_EXISTING_CANDIDATE|' ...
        'BOARD17_CALCULATION_LEVEL_EXTERNAL_ASSET_INDIRECTLY_PASSPORT_BOUND_CURRENT_HASH_MATCH|' ...
        'LOCAL_NUMERICAL_SUBSTRUCTURE_12D_PENDING'];
    caseId = sprintf('w0%d', division);
    coordinateIdentity = sprintf('BOARD17_DIVISION%d_ORDERED_MODEL', division);
    [W, R] = paperVariants(caseId, coordinateIdentity, boundary, ...
        fullM, fullK, direction, direction, T, Mg, Kg, Tcb, Mcb, Kcb, ...
        d, d, d, W, R);
    context = makeContext(caseId, 'WHOLE_INPUT_AUDIT', coordinateIdentity, ...
        'BOARD17_SEALED_MATRIX_IDENTITY', 'WHOLE_MODEL_EXISTING_CANDIDATE', ...
        'NOT_APPLICABLE', 'NOT_APPLICABLE', -1);
    W = emitArray(W, context, 'guyan', ...
        'matrix_identity_M_standard_minus_TtMT', double(D.M_projected)-T'*fullM*T);
    W = emitArray(W, context, 'guyan', ...
        'matrix_identity_K_standard_minus_TtKT', double(D.K_projected)-T'*fullK*T);
    W = emitArray(W, context, 'cb', ...
        'matrix_identity_M_cb_minus_TtMT', Mcb-Tcb'*fullM*Tcb);
    W = emitArray(W, context, 'cb', ...
        'matrix_identity_K_cb_minus_TtKT', Kcb-Tcb'*fullK*Tcb);
end
end


function hash = sha256File(path)
fid = fopen(path, 'r');
if fid < 0, error('BOARD21:S4:HashOpen', 'Cannot open %s', path); end
cleanupObject = onCleanup(@() fclose(fid)); %#ok<NASGU>
digest = java.security.MessageDigest.getInstance('SHA-256');
while ~feof(fid)
    bytes = fread(fid, 1024*1024, '*uint8');
    if ~isempty(bytes)
        digest.update(bytes);
    end
end
raw = typecast(digest.digest(), 'uint8');
hash = upper(reshape(dec2hex(raw, 2).', 1, []));
end
