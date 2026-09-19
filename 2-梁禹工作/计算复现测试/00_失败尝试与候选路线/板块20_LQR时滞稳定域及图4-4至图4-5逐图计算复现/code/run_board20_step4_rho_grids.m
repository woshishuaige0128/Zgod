function summary = run_board20_step4_rho_grids(varargin)
%RUN_BOARD20_STEP4_RHO_GRIDS Run sealed Board-20 spectral-radius grids.
%
% This file is an orchestrator only.  It never reconstructs the
% characteristic polynomial.  Every requested point is delegated to:
%
%   result = solve_board20_author_poles(matrices, route_formula, l, j)
%
% Supported modes (no full grid is run by default):
%   preflight   - verify hashes, step-2 success, matrix fields and plans;
%                 create no output.
%   point_list  - run Points (N-by-2 [l,j]); when Points is empty, use the
%                 immutable pilot_points stored in the route manifest.
%   small_grid  - run the Cartesian product SmallLValues x SmallJValues.
%   full        - run all 31x67 common-grid points and resume checkpoints.
%
% Examples:
%   run_board20_step4_rho_grids('Mode','preflight')
%   run_board20_step4_rho_grids('Mode','point_list', ...
%       'RouteIds',{'main_ori_div1'},'Points',[0 0; 1 0])
%   run_board20_step4_rho_grids('Mode','small_grid', ...
%       'SmallLValues',0:1,'SmallJValues',0:1)
%   run_board20_step4_rho_grids('Mode','full','Resume',true)
%
% Safety and provenance:
%   * inputs/config/source code are checked against SHA-256 contracts;
%   * final MAT files are never overwritten;
%   * one route checkpoint is atomically replaced after a bounded number
%     of new points and can be resumed only under the same identity hashes;
%   * author_code_grid and common_31x67_same_formula_candidate are separate;
%   * step-2 active points must reproduce the sealed stab value within the
%     tolerance in board20_step4_route_manifest.json, otherwise the point is
%     recorded as FAIL rather than silently accepted.

parser = inputParser;
parser.FunctionName = mfilename;
addParameter(parser, 'Mode', 'preflight', @is_text_scalar);
addParameter(parser, 'RouteIds', {}, @is_text_list);
addParameter(parser, 'Points', zeros(0, 2), @is_point_matrix);
addParameter(parser, 'SmallLValues', 0:2, @is_integer_vector);
addParameter(parser, 'SmallJValues', 0:2, @is_integer_vector);
addParameter(parser, 'Resume', true, @(x) islogical(x) && isscalar(x));
addParameter(parser, 'CheckpointEvery', 10, ...
    @(x) isnumeric(x) && isscalar(x) && isfinite(x) && x >= 1 && x == floor(x));
parse(parser, varargin{:});
options = parser.Results;
mode = lower(char(string(options.Mode)));
allowedModes = {'preflight', 'point_list', 'small_grid', 'full'};
assert(any(strcmp(mode, allowedModes)), 'Board20Step4:InvalidMode', ...
    'Mode must be preflight, point_list, small_grid, or full.');

runnerPath = [mfilename('fullpath'), '.m'];
codeDir = fileparts(runnerPath);
baseDir = fileparts(codeDir);
manifestPath = fullfile(codeDir, 'board20_step4_route_manifest.json');
assert(isfile(manifestPath), 'Board20Step4:ManifestMissing', ...
    'Route manifest is missing: %s', manifestPath);
manifest = jsondecode(fileread(manifestPath));
assert(strcmp(char(manifest.schema_version), ...
    'board20_step4_route_manifest_v1'), ...
    'Board20Step4:ManifestSchemaMismatch', ...
    'Unexpected route manifest schema: %s', char(manifest.schema_version));
verify_failed_evidence_routes(baseDir, manifest.failed_routes);

oldPath = path;
pathCleanup = onCleanup(@() path(oldPath));
addpath(codeDir, '-begin');
solverPath = which(char(manifest.solver.function));
assert(~isempty(solverPath) && isfile(solverPath), ...
    'Board20Step4:SolverMissing', ...
    'Expected solver is not available: %s', char(manifest.solver.function));
solverNargin = nargin(char(manifest.solver.function));
assert(solverNargin == 4 || solverNargin < 0, ...
    'Board20Step4:SolverSignatureMismatch', ...
    'Solver must accept matrices, route_formula, l, and j.');

globalIdentity = struct( ...
    'manifest_path', manifestPath, ...
    'manifest_sha256', sha256_file(manifestPath), ...
    'runner_path', runnerPath, ...
    'runner_sha256', sha256_file(runnerPath), ...
    'solver_path', solverPath, ...
    'solver_sha256', sha256_file(solverPath), ...
    'solver_function', char(manifest.solver.function));

selectedIds = normalize_text_list(options.RouteIds);
routes = manifest.routes;
records = repmat(empty_summary_record(), 0, 1);
for routeIndex = 1:numel(routes)
    route = array_item(routes, routeIndex);
    routeId = char(route.route_id);
    if ~isempty(selectedIds) && ~any(strcmp(routeId, selectedIds))
        continue;
    end

    [matrices, step2Reference, routeIdentity, matrixShape] = ...
        preflight_route(baseDir, route, globalIdentity);
    [authorPlan, commonPlan] = build_route_plans(route, step2Reference, ...
        double(manifest.step2_match_tolerance));

    if strcmp(mode, 'preflight')
        record = empty_summary_record();
        record.route_id = routeId;
        record.mode = mode;
        record.overall_status = 'PREFLIGHT_PASS';
        record.matrix_shape = matrixShape;
        record.author_requested_points = nnz(authorPlan.requested_mask);
        record.common_requested_points = nnz(commonPlan.requested_mask);
        record.completed_points = 0;
        record.fail_points = 0;
        record.status_path = '';
    else
        record = execute_route(baseDir, manifest, route, matrices, ...
            routeIdentity, authorPlan, commonPlan, options, mode);
    end
    records(end + 1) = record; %#ok<AGROW>
end

assert(~isempty(records), 'Board20Step4:NoSelectedRoutes', ...
    'No manifest route matched RouteIds.');
summary = struct( ...
    'schema_version', 'board20_step4_runner_summary_v1', ...
    'created_at', timestamp_now(), ...
    'mode', mode, ...
    'manifest_path', manifestPath, ...
    'manifest_sha256', globalIdentity.manifest_sha256, ...
    'runner_sha256', globalIdentity.runner_sha256, ...
    'solver_sha256', globalIdentity.solver_sha256, ...
    'selected_route_count', numel(records), ...
    'failed_evidence_only_route_count', numel(manifest.failed_routes), ...
    'records', records);

if nargout == 0
    fprintf('Board20 step4 mode=%s; routes=%d; manifest=%s\n', ...
        mode, numel(records), globalIdentity.manifest_sha256);
    for k = 1:numel(records)
        fprintf('  %s: %s, completed=%d, fail=%d\n', ...
            records(k).route_id, records(k).overall_status, ...
            records(k).completed_points, records(k).fail_points);
    end
end
end


function record = execute_route(baseDir, manifest, route, matrices, ...
        identity, authorPlan, commonPlan, options, mode)
routeId = char(route.route_id);
routeDir = fileparts(resolve_relpath(baseDir, ...
    char(route.common_grid.output_relpath)));
authorOutput = resolve_relpath(baseDir, ...
    char(route.author_code_grid.output_relpath));
commonOutput = resolve_relpath(baseDir, ...
    char(route.common_grid.output_relpath));
assert(strcmp(routeDir, fileparts(authorOutput)), ...
    'Board20Step4:OutputDirectoryMismatch', ...
    'Both grids for route %s must share one output directory.', routeId);
checkpointPath = fullfile(routeDir, 'checkpoint.mat');
statusPath = fullfile(routeDir, 'status.json');

if ~isfolder(routeDir)
    [made, message] = mkdir(routeDir);
    assert(made, 'Board20Step4:OutputDirectoryCreateFailed', ...
        'Cannot create output directory %s: %s', routeDir, message);
end

if isfile(checkpointPath)
    assert(options.Resume, 'Board20Step4:CheckpointExistsResumeDisabled', ...
        'Checkpoint exists and Resume=false: %s', checkpointPath);
    loaded = load(checkpointPath, 'checkpoint');
    assert(isfield(loaded, 'checkpoint'), ...
        'Board20Step4:InvalidCheckpoint', ...
        'Checkpoint variable is missing: %s', checkpointPath);
    checkpoint = loaded.checkpoint;
    assert_checkpoint_identity(checkpoint, identity, routeId);
    authorState = checkpoint.author_code_grid;
    commonState = checkpoint.common_grid;
    assert_grid_compatible(authorState, authorPlan, routeId);
    assert_grid_compatible(commonState, commonPlan, routeId);
else
    assert(~isfile(authorOutput) && ~isfile(commonOutput) && ...
        ~isfile(statusPath), 'Board20Step4:OutputExistsWithoutCheckpoint', ...
        ['Final/status output already exists without a resumable checkpoint. ' ...
         'Refusing to overwrite route %s.'], routeId);
    authorState = authorPlan;
    commonState = commonPlan;
    checkpoint = initialize_checkpoint(route, identity, authorState, commonState);
end

selectionMask = make_selection_mask(commonState, route, options, mode);
todoMask = selectionMask & commonState.requested_mask & ...
    ~commonState.completed_mask;
[todoRows, todoColumns] = find(todoMask);
attemptedThisCall = 0;

for pointIndex = 1:numel(todoRows)
    row = todoRows(pointIndex);
    column = todoColumns(pointIndex);
    lValue = commonState.l_values(row);
    jValue = commonState.j_values(column);
    [result, contractPass] = call_solver_point(matrices, ...
        char(route.route_formula), lValue, jValue, ...
        manifest.solver.required_result_fields, ...
        manifest.solver.additional_result_fields);

    [commonState, finalPass] = store_point(commonState, row, column, ...
        result, contractPass, double(manifest.step2_match_tolerance));
    [inAuthor, authorRow, authorColumn] = locate_grid_point( ...
        authorState, lValue, jValue);
    if inAuthor && authorState.requested_mask(authorRow, authorColumn)
        [authorState, ~] = store_point(authorState, authorRow, authorColumn, ...
            result, contractPass, double(manifest.step2_match_tolerance));
    end

    attemptedThisCall = attemptedThisCall + 1;
    if ~finalPass
        fprintf(2, 'Board20 step4 FAIL: route=%s l=%d j=%d status=%s\n', ...
            routeId, lValue, jValue, commonState.point_status{row, column});
    end
    if mod(attemptedThisCall, options.CheckpointEvery) == 0
        checkpoint = update_checkpoint(checkpoint, authorState, ...
            commonState, mode, attemptedThisCall);
        write_checkpoint_atomic(checkpointPath, checkpoint);
        write_status_atomic(statusPath, build_route_status(route, identity, ...
            checkpointPath, authorOutput, commonOutput, authorState, ...
            commonState, mode, attemptedThisCall));
    end
end

checkpoint = update_checkpoint(checkpoint, authorState, commonState, ...
    mode, attemptedThisCall);
write_checkpoint_atomic(checkpointPath, checkpoint);

if grid_is_complete(authorState) && ~isfile(authorOutput)
    write_grid_output(authorOutput, route, identity, authorState);
end
if grid_is_complete(commonState) && ~isfile(commonOutput)
    write_grid_output(commonOutput, route, identity, commonState);
end
routeStatus = build_route_status(route, identity, checkpointPath, ...
    authorOutput, commonOutput, authorState, commonState, mode, ...
    attemptedThisCall);
write_status_atomic(statusPath, routeStatus);

record = empty_summary_record();
record.route_id = routeId;
record.mode = mode;
record.overall_status = routeStatus.overall_status;
record.matrix_shape = size(matrices.M);
record.author_requested_points = nnz(authorState.requested_mask);
record.common_requested_points = nnz(commonState.requested_mask);
record.completed_points = nnz(commonState.requested_mask & ...
    commonState.completed_mask);
record.fail_points = nnz(commonState.requested_mask & commonState.status == 2);
record.status_path = statusPath;
end


function [matrices, step2Reference, identity, matrixShape] = ...
        preflight_route(baseDir, route, globalIdentity)
routeId = char(route.route_id);
contracts = route.file_contracts;
contractRecords = repmat(struct('role', '', 'path', '', ...
    'expected_sha256', '', 'actual_sha256', '', 'match', false), 0, 1);
for k = 1:numel(contracts)
    pathValue = resolve_relpath(baseDir, char(contracts(k).relpath));
    assert(isfile(pathValue), 'Board20Step4:ContractFileMissing', ...
        'Contract file is missing for %s: %s', routeId, pathValue);
    actualHash = sha256_file(pathValue);
    expectedHash = upper(char(contracts(k).sha256));
    assert(strcmp(actualHash, expectedHash), ...
        'Board20Step4:ContractHashMismatch', ...
        'Hash mismatch for route %s file %s.', routeId, pathValue);
    contractRecords(end + 1) = struct( ...
        'role', char(contracts(k).role), 'path', pathValue, ...
        'expected_sha256', expectedHash, 'actual_sha256', actualHash, ...
        'match', true); %#ok<AGROW>
end

configPath = resolve_relpath(baseDir, char(route.run_config_relpath));
config = jsondecode(fileread(configPath));
assert(strcmp(char(config.route_id), routeId), ...
    'Board20Step4:Step2ConfigRouteMismatch', ...
    'Step-2 run_config route_id mismatch for %s.', routeId);
assert(strcmp(char(config.replicate), char(route.step2_replicate)), ...
    'Board20Step4:Step2ConfigReplicateMismatch', ...
    'Step-2 replicate mismatch for %s.', routeId);
assert(strcmpi(char(config.candidate_sha256), ...
    char(route.candidate_mlx_sha256)), ...
    'Board20Step4:Step2CandidateIdentityMismatch', ...
    'Step-2 candidate MLX hash mismatch for %s.', routeId);

statusPath = resolve_relpath(baseDir, char(route.run_status_relpath));
step2Status = jsondecode(fileread(statusPath));
assert(isfield(step2Status, 'final_status') && ...
    isfield(step2Status, 'execution_status') && ...
    strcmp(char(step2Status.final_status), 'SUCCESS') && ...
    strcmp(char(step2Status.execution_status), 'EXECUTION_SUCCESS'), ...
    'Board20Step4:Step2NotSuccessful', ...
    'Route %s does not have sealed EXECUTION_SUCCESS evidence.', routeId);

workspacePath = resolve_relpath(baseDir, char(route.workspace_relpath));
variableMap = route.matrix_variable_map;
targetNames = fieldnames(variableMap);
sourceNames = cell(size(targetNames));
for k = 1:numel(targetNames)
    sourceNames{k} = char(variableMap.(targetNames{k}));
end
sourceNames = unique(sourceNames, 'stable');
workspaceVariables = who('-file', workspacePath);
missing = setdiff(sourceNames, workspaceVariables, 'stable');
assert(isempty(missing), 'Board20Step4:WorkspaceVariableMissing', ...
    'Route %s workspace is missing: %s', routeId, strjoin(missing, ', '));
loaded = load(workspacePath, sourceNames{:});

requiredTargets = {'M', 'C1', 'K1', 'C2', 'K2', 'al', 'dt'};
if strcmpi(char(route.division), 'div2')
    requiredTargets = [requiredTargets, {'S', 'DeltaC', 'DeltaK'}];
end
for k = 1:numel(requiredTargets)
    target = requiredTargets{k};
    assert(isfield(variableMap, target), ...
        'Board20Step4:MatrixMapMissing', ...
        'Route %s matrix map lacks %s.', routeId, target);
    source = char(variableMap.(target));
    matrices.(target) = loaded.(source);
end
referenceSource = char(variableMap.step2_rho_reference);
step2Reference = double(loaded.(referenceSource));
validate_matrices(matrices, char(route.division), routeId);
validate_active_reference_bounds(route, step2Reference);
matrixShape = size(matrices.M);

identity = globalIdentity;
identity.route_id = routeId;
identity.route_formula = char(route.route_formula);
identity.step2_replicate = char(route.step2_replicate);
identity.workspace_path = workspacePath;
identity.workspace_sha256 = hash_for_role(contractRecords, ...
    'workspace_complete');
identity.run_config_path = configPath;
identity.run_config_sha256 = hash_for_role(contractRecords, 'run_config');
identity.run_status_path = statusPath;
identity.run_status_sha256 = hash_for_role(contractRecords, 'run_status');
identity.source_m_path = resolve_relpath(baseDir, char(route.source_m_relpath));
identity.source_m_sha256 = hash_for_role(contractRecords, ...
    'extracted_author_m');
identity.candidate_mlx_sha256 = upper(char(route.candidate_mlx_sha256));
identity.contract_records = contractRecords;
identity.matrix_variable_map = variableMap;
end


function verify_failed_evidence_routes(baseDir, failedRoutes)
% Failure routes remain evidence-only.  Their sealed failure artifacts are
% hash-checked, and the two forbidden rho-grid filenames must not exist.
for routeIndex = 1:numel(failedRoutes)
    route = array_item(failedRoutes, routeIndex);
    routeId = char(route.route_id);
    assert(strcmp(char(route.rho_grid_policy), 'DO_NOT_CREATE'), ...
        'Board20Step4:FailedRoutePolicyMismatch', ...
        'Failure route %s must have DO_NOT_CREATE policy.', routeId);
    contracts = route.file_contracts;
    for contractIndex = 1:numel(contracts)
        pathValue = resolve_relpath(baseDir, char(contracts(contractIndex).path));
        assert(isfile(pathValue), 'Board20Step4:FailedEvidenceMissing', ...
            'Failure evidence is missing for %s: %s', routeId, pathValue);
        actualHash = sha256_file(pathValue);
        expectedHash = char(contracts(contractIndex).sha256);
        assert(strcmpi(actualHash, expectedHash), ...
            'Board20Step4:FailedEvidenceHashMismatch', ...
            'Failure evidence hash mismatch for %s: %s', routeId, pathValue);
    end
    statusValue = jsondecode(fileread(resolve_relpath(baseDir, ...
        char(route.run_status_relpath))));
    assert(isfield(statusValue, 'final_status') && ...
        isfield(statusValue, 'execution_status') && ...
        strcmp(char(statusValue.final_status), 'EXECUTION_FAIL') && ...
        strcmp(char(statusValue.execution_status), 'EXECUTION_FAIL'), ...
        'Board20Step4:FailedEvidenceStatusMismatch', ...
        'Failure route %s is not sealed as EXECUTION_FAIL.', routeId);
    forbiddenDir = fullfile(baseDir, 'outputs', 'step4_rho_grids', routeId);
    assert(~isfile(fullfile(forbiddenDir, 'author_code_grid.mat')) && ...
        ~isfile(fullfile(forbiddenDir, ...
        'common_31x67_same_formula_candidate.mat')), ...
        'Board20Step4:ForbiddenFailureRouteGrid', ...
        'A rho grid exists for failure-only route %s.', routeId);
end
end


function [authorState, commonState] = build_route_plans(route, ...
        step2Reference, tolerance)
authorState = initialize_grid_state(route, route.author_code_grid, ...
    false, step2Reference, tolerance);
commonState = initialize_grid_state(route, route.common_grid, ...
    true, step2Reference, tolerance);
assert(nnz(authorState.requested_mask) == ...
    double(route.author_code_grid.expected_point_count), ...
    'Board20Step4:AuthorPointCountMismatch', ...
    'Author-grid point count mismatch for %s.', char(route.route_id));
assert(nnz(commonState.requested_mask) == ...
    double(route.common_grid.expected_point_count), ...
    'Board20Step4:CommonPointCountMismatch', ...
    'Common-grid point count mismatch for %s.', char(route.route_id));
assert(nnz(commonState.planned_provenance_code == 1) == ...
    double(route.active_points), 'Board20Step4:ActivePointCountMismatch', ...
    'Active-point count mismatch for %s.', char(route.route_id));
assert(nnz(commonState.planned_provenance_code == 2) == ...
    double(route.commented_author_intent_points), ...
    'Board20Step4:IntentPointCountMismatch', ...
    'Commented-intent point count mismatch for %s.', char(route.route_id));
assert(nnz(commonState.planned_provenance_code == 3) == ...
    double(route.supplemental_points), ...
    'Board20Step4:SupplementPointCountMismatch', ...
    'Supplement point count mismatch for %s.', char(route.route_id));
end


function state = initialize_grid_state(route, gridDefinition, isCommon, ...
        step2Reference, tolerance)
lValues = double(gridDefinition.l_start):double(gridDefinition.l_end);
jValues = double(gridDefinition.j_start):double(gridDefinition.j_end);
shape = [numel(lValues), numel(jValues)];
expectedShape = double(gridDefinition.expected_shape(:)).';
assert(isequal(shape, expectedShape), 'Board20Step4:GridShapeMismatch', ...
    'Grid shape declaration mismatch for %s.', char(route.route_id));
activeMask = regions_to_mask(route.active_regions, lValues, jValues);
intentMask = regions_to_mask(route.commented_author_intent_regions, ...
    lValues, jValues) & ~activeMask;
if isCommon
    requestedMask = true(shape);
else
    requestedMask = activeMask | intentMask;
end
plannedCode = zeros(shape, 'uint8');
plannedCode(activeMask) = uint8(1);
plannedCode(intentMask) = uint8(2);
plannedCode(requestedMask & plannedCode == 0) = uint8(3);

state = struct();
state.schema_version = 'board20_step4_grid_state_v1';
state.route_id = char(route.route_id);
state.route_formula = char(route.route_formula);
state.grid_name = char(gridDefinition.grid_name);
state.l_values = lValues;
state.j_values = jValues;
state.index_base = double(gridDefinition.index_base);
state.requested_mask = requestedMask;
state.completed_mask = false(shape);
state.planned_provenance_code = plannedCode;
state.provenance_code = plannedCode;
state.status = zeros(shape, 'uint8');
state.rho = NaN(shape);
state.stable = NaN(shape);
state.residual = NaN(shape);
state.poly_degree = NaN(shape);
state.clearing_power = NaN(shape);
state.removed_zero_root_count = NaN(shape);
state.retained_root_count = NaN(shape);
state.poles = cell(shape);
state.raw_roots = cell(shape);
state.critical = cell(shape);
state.point_status = cell(shape);
state.diagnostic = cell(shape);
state.step2_rho_reference = NaN(shape);
state.step2_abs_diff = NaN(shape);
state.step2_match = NaN(shape);
state.step2_match_tolerance = tolerance;
state.created_at = timestamp_now();
state.updated_at = state.created_at;

for row = 1:shape(1)
    for column = 1:shape(2)
        if activeMask(row, column)
            sourceRow = lValues(row) + 1;
            sourceColumn = jValues(column) + 1;
            if sourceRow <= size(step2Reference, 1) && ...
                    sourceColumn <= size(step2Reference, 2)
                state.step2_rho_reference(row, column) = ...
                    step2Reference(sourceRow, sourceColumn);
            end
        end
    end
end
end


function mask = regions_to_mask(regions, lValues, jValues)
mask = false(numel(lValues), numel(jValues));
if isempty(regions)
    return;
end
for k = 1:numel(regions)
    lMask = lValues >= double(regions(k).l_start) & ...
        lValues <= double(regions(k).l_end);
    jMask = jValues >= double(regions(k).j_start) & ...
        jValues <= double(regions(k).j_end);
    mask = mask | (lMask(:) * jMask(:).');
end
end


function selectionMask = make_selection_mask(commonState, route, options, mode)
shape = size(commonState.requested_mask);
selectionMask = false(shape);
switch mode
    case 'full'
        selectionMask = commonState.requested_mask;
    case 'small_grid'
        lSelected = ismember(commonState.l_values, ...
            double(options.SmallLValues(:)).');
        jSelected = ismember(commonState.j_values, ...
            double(options.SmallJValues(:)).');
        selectionMask = lSelected(:) * jSelected(:).';
    case 'point_list'
        points = double(options.Points);
        if isempty(points)
            points = double(route.pilot_points);
            if isvector(points) && numel(points) == 2
                points = reshape(points, 1, 2);
            end
        end
        assert(size(points, 2) == 2, 'Board20Step4:InvalidPointList', ...
            'Points must be N-by-2 [l,j].');
        for k = 1:size(points, 1)
            [inside, row, column] = locate_grid_point(commonState, ...
                points(k, 1), points(k, 2));
            assert(inside, 'Board20Step4:PointOutsideCommonGrid', ...
                'Point [%g,%g] is outside the common grid for %s.', ...
                points(k, 1), points(k, 2), char(route.route_id));
            selectionMask(row, column) = true;
        end
    otherwise
        error('Board20Step4:InternalModeError', 'Unexpected mode: %s', mode);
end
selectionMask = logical(selectionMask) & commonState.requested_mask;
end


function [result, contractPass] = call_solver_point(matrices, routeFormula, ...
        lValue, jValue, requiredFields, additionalFields)
contractPass = true;
try
    result = solve_board20_author_poles(matrices, routeFormula, ...
        lValue, jValue);
    assert(isstruct(result) && isscalar(result), ...
        'Board20Step4:SolverContractViolation', ...
        'Solver result must be a scalar struct.');
    required = normalize_text_list(requiredFields);
    missing = required(~isfield(result, required));
    assert(isempty(missing), 'Board20Step4:SolverContractViolation', ...
        'Solver result is missing fields: %s', strjoin(missing, ', '));
    additional = normalize_text_list(additionalFields);
    for k = 1:numel(additional)
        if ~isfield(result, additional{k})
            result.(additional{k}) = [];
        end
    end
    assert(isnumeric(result.rho) && isscalar(result.rho), ...
        'Board20Step4:SolverContractViolation', ...
        'result.rho must be a numeric scalar.');
    assert(isnumeric(result.max_relative_residual) && ...
        isscalar(result.max_relative_residual), ...
        'Board20Step4:SolverContractViolation', ...
        'result.max_relative_residual must be a numeric scalar.');
catch exception
    if strcmp(exception.identifier, 'Board20Step4:SolverContractViolation')
        rethrow(exception);
    end
    contractPass = false;
    diagnostic = struct( ...
        'kind', 'SOLVER_EXCEPTION', ...
        'identifier', exception.identifier, ...
        'message', exception.message, ...
        'stack', {exception.stack});
    result = struct( ...
        'poles', [], 'rho', NaN, 'poly_degree', NaN, ...
        'clearing_power', NaN, 'removed_zero_root_count', NaN, ...
        'max_relative_residual', NaN, 'point_status', 'FAIL', ...
        'stable', false, 'raw_roots', [], 'retained_root_count', NaN, ...
        'critical', [], 'diagnostic', diagnostic);
end
end


function [state, finalPass] = store_point(state, row, column, result, ...
        contractPass, tolerance)
statusText = normalize_point_status(result.point_status);
solverPass = contractPass && strcmp(statusText, 'PASS') && ...
    isfinite(double(result.rho));
reference = state.step2_rho_reference(row, column);
referencePass = true;
if state.planned_provenance_code(row, column) == 1 && isfinite(reference)
    state.step2_abs_diff(row, column) = abs(double(result.rho) - reference);
    referencePass = isfinite(state.step2_abs_diff(row, column)) && ...
        state.step2_abs_diff(row, column) <= tolerance;
    state.step2_match(row, column) = double(referencePass);
end
finalPass = solverPass && referencePass;

state.completed_mask(row, column) = true;
state.poles{row, column} = result.poles;
state.rho(row, column) = double(result.rho);
state.poly_degree(row, column) = double(result.poly_degree);
state.clearing_power(row, column) = double(result.clearing_power);
state.removed_zero_root_count(row, column) = ...
    double(result.removed_zero_root_count);
state.residual(row, column) = double(result.max_relative_residual);
state.raw_roots{row, column} = result.raw_roots;
state.retained_root_count(row, column) = ...
    double(result.retained_root_count);
state.critical{row, column} = result.critical;
state.diagnostic{row, column} = result.diagnostic;

if finalPass
    state.status(row, column) = uint8(1);
    state.point_status{row, column} = 'PASS';
    state.stable(row, column) = double(logical(result.stable));
    state.provenance_code(row, column) = ...
        state.planned_provenance_code(row, column);
else
    state.status(row, column) = uint8(2);
    state.point_status{row, column} = 'FAIL';
    state.stable(row, column) = NaN;
    state.provenance_code(row, column) = uint8(4);
    if solverPass && ~referencePass
        state.diagnostic{row, column} = struct( ...
            'kind', 'STEP2_ACTIVE_POINT_MISMATCH', ...
            'solver_diagnostic', result.diagnostic, ...
            'step2_rho_reference', reference, ...
            'rho', double(result.rho), ...
            'absolute_difference', state.step2_abs_diff(row, column), ...
            'tolerance', tolerance);
    end
end
state.updated_at = timestamp_now();
end


function checkpoint = initialize_checkpoint(route, identity, authorState, ...
        commonState)
checkpoint = struct( ...
    'schema_version', 'board20_step4_checkpoint_v1', ...
    'route_id', char(route.route_id), ...
    'route_formula', char(route.route_formula), ...
    'identity', identity, ...
    'created_at', timestamp_now(), ...
    'updated_at', timestamp_now(), ...
    'last_mode', '', ...
    'attempted_points_last_call', 0, ...
    'author_code_grid', authorState, ...
    'common_grid', commonState);
end


function checkpoint = update_checkpoint(checkpoint, authorState, commonState, ...
        mode, attemptedThisCall)
checkpoint.author_code_grid = authorState;
checkpoint.common_grid = commonState;
checkpoint.updated_at = timestamp_now();
checkpoint.last_mode = mode;
checkpoint.attempted_points_last_call = attemptedThisCall;
end


function assert_checkpoint_identity(checkpoint, identity, routeId)
assert(isfield(checkpoint, 'schema_version') && ...
    strcmp(char(checkpoint.schema_version), 'board20_step4_checkpoint_v1'), ...
    'Board20Step4:CheckpointSchemaMismatch', ...
    'Checkpoint schema mismatch for route %s.', routeId);
fields = {'manifest_sha256', 'runner_sha256', 'solver_sha256', ...
    'workspace_sha256', 'run_config_sha256', 'run_status_sha256', ...
    'source_m_sha256', 'candidate_mlx_sha256', 'route_formula'};
for k = 1:numel(fields)
    field = fields{k};
    assert(isfield(checkpoint.identity, field) && ...
        strcmp(char(checkpoint.identity.(field)), char(identity.(field))), ...
        'Board20Step4:CheckpointIdentityMismatch', ...
        'Checkpoint identity mismatch for route %s field %s.', ...
        routeId, field);
end
end


function assert_grid_compatible(state, plan, routeId)
assert(strcmp(char(state.schema_version), char(plan.schema_version)) && ...
    strcmp(char(state.grid_name), char(plan.grid_name)) && ...
    isequal(state.l_values, plan.l_values) && ...
    isequal(state.j_values, plan.j_values) && ...
    isequal(state.requested_mask, plan.requested_mask) && ...
    isequal(state.planned_provenance_code, ...
    plan.planned_provenance_code), ...
    'Board20Step4:CheckpointPlanMismatch', ...
    'Checkpoint grid plan mismatch for route %s grid %s.', ...
    routeId, char(plan.grid_name));
end


function statusValue = build_route_status(route, identity, checkpointPath, ...
        authorOutput, commonOutput, authorState, commonState, mode, ...
        attemptedThisCall)
authorSummary = summarize_grid(authorState, authorOutput);
commonSummary = summarize_grid(commonState, commonOutput);
if commonSummary.pending_points > 0
    overall = 'IN_PROGRESS';
elseif commonSummary.fail_points > 0
    overall = 'COMPLETE_WITH_FAIL';
else
    overall = 'COMPLETE_PASS';
end
statusValue = struct( ...
    'schema_version', 'board20_step4_route_status_v1', ...
    'route_id', char(route.route_id), ...
    'route_formula', char(route.route_formula), ...
    'mode_last_call', mode, ...
    'overall_status', overall, ...
    'updated_at', timestamp_now(), ...
    'attempted_points_last_call', attemptedThisCall, ...
    'checkpoint_path', checkpointPath, ...
    'identity', identity, ...
    'author_code_grid', authorSummary, ...
    'common_31x67_same_formula_candidate', commonSummary);
end


function value = summarize_grid(state, outputPath)
requested = state.requested_mask;
completed = requested & state.completed_mask;
compared = requested & isfinite(state.step2_match);
value = struct( ...
    'grid_name', char(state.grid_name), ...
    'output_path', outputPath, ...
    'output_exists', isfile(outputPath), ...
    'expected_shape', size(requested), ...
    'requested_points', nnz(requested), ...
    'completed_points', nnz(completed), ...
    'pass_points', nnz(requested & state.status == 1), ...
    'fail_points', nnz(requested & state.status == 2), ...
    'pending_points', nnz(requested & ~state.completed_mask), ...
    'step2_compared_points', nnz(compared), ...
    'step2_match_points', nnz(compared & state.step2_match == 1), ...
    'step2_mismatch_points', nnz(compared & state.step2_match == 0));
if isfile(outputPath)
    value.output_sha256 = sha256_file(outputPath);
else
    value.output_sha256 = '';
end
end


function write_grid_output(outputPath, route, identity, state)
assert(~isfile(outputPath), 'Board20Step4:RefuseFinalOverwrite', ...
    'Refusing to overwrite final grid: %s', outputPath);
schema_version = 'board20_step4_grid_output_v1';
route_id = char(route.route_id);
route_name = char(route.route_name);
route_formula = char(route.route_formula);
grid_name = char(state.grid_name);
l_values = state.l_values;
j_values = state.j_values;
index_base = state.index_base;
requested_mask = state.requested_mask;
completed_mask = state.completed_mask;
rho = state.rho;
stable = state.stable;
critical = state.critical;
residual = state.residual;
status = state.status;
point_status = state.point_status;
diagnostic = state.diagnostic;
provenance_code = state.provenance_code;
planned_provenance_code = state.planned_provenance_code;
status_code_map = struct('PASS', uint8(1), 'FAIL', uint8(2));
provenance_code_map = struct('ORIGINAL_ACTIVE_POINT', uint8(1), ...
    'COMMENTED_AUTHOR_INTENT', uint8(2), ...
    'SAME_FORMULA_SUPPLEMENT', uint8(3), 'FAIL', uint8(4));
poles = state.poles;
raw_roots = state.raw_roots;
poly_degree = state.poly_degree;
clearing_power = state.clearing_power;
removed_zero_root_count = state.removed_zero_root_count;
retained_root_count = state.retained_root_count;
step2_rho_reference = state.step2_rho_reference;
step2_abs_diff = state.step2_abs_diff;
step2_match = state.step2_match;
step2_match_tolerance = state.step2_match_tolerance;
source_step2_relpath = char(route.source_step2_relpath);
matrix_variable_map = route.matrix_variable_map;
completed_at = timestamp_now();

outputDir = fileparts(outputPath);
temporaryPath = [tempname(outputDir), '.mat'];
cleanup = onCleanup(@() delete_if_exists(temporaryPath));
save(temporaryPath, 'schema_version', 'route_id', 'route_name', ...
    'route_formula', 'grid_name', 'l_values', 'j_values', 'index_base', ...
    'requested_mask', 'completed_mask', 'rho', 'stable', 'critical', ...
    'residual', 'status', 'point_status', 'diagnostic', ...
    'provenance_code', 'planned_provenance_code', 'status_code_map', ...
    'provenance_code_map', 'poles', 'raw_roots', 'poly_degree', ...
    'clearing_power', 'removed_zero_root_count', 'retained_root_count', ...
    'step2_rho_reference', 'step2_abs_diff', 'step2_match', ...
    'step2_match_tolerance', 'source_step2_relpath', ...
    'matrix_variable_map', 'identity', 'completed_at', '-v7.3');
assert(~isfile(outputPath), 'Board20Step4:RefuseFinalOverwrite', ...
    'Final grid appeared during save; refusing overwrite: %s', outputPath);
[moved, message] = movefile(temporaryPath, outputPath);
assert(moved, 'Board20Step4:FinalMoveFailed', ...
    'Cannot publish final grid %s: %s', outputPath, message);
end


function write_checkpoint_atomic(pathValue, checkpoint)
folder = fileparts(pathValue);
temporaryPath = [tempname(folder), '.mat'];
cleanup = onCleanup(@() delete_if_exists(temporaryPath));
save(temporaryPath, 'checkpoint', '-v7.3');
[moved, message] = movefile(temporaryPath, pathValue, 'f');
assert(moved, 'Board20Step4:CheckpointMoveFailed', ...
    'Cannot update checkpoint %s: %s', pathValue, message);
end


function write_status_atomic(pathValue, value)
folder = fileparts(pathValue);
temporaryPath = [tempname(folder), '.json'];
cleanup = onCleanup(@() delete_if_exists(temporaryPath));
fileId = fopen(temporaryPath, 'w', 'n', 'UTF-8');
assert(fileId >= 0, 'Board20Step4:StatusOpenFailed', ...
    'Cannot open temporary status JSON: %s', temporaryPath);
fileCleanup = onCleanup(@() fclose(fileId));
fprintf(fileId, '%s\n', jsonencode(value, 'PrettyPrint', true));
clear fileCleanup;
[moved, message] = movefile(temporaryPath, pathValue, 'f');
assert(moved, 'Board20Step4:StatusMoveFailed', ...
    'Cannot update status JSON %s: %s', pathValue, message);
end


function complete = grid_is_complete(state)
complete = all(state.completed_mask(state.requested_mask));
end


function [inside, row, column] = locate_grid_point(state, lValue, jValue)
row = find(state.l_values == lValue, 1);
column = find(state.j_values == jValue, 1);
inside = ~isempty(row) && ~isempty(column);
if ~inside
    row = NaN;
    column = NaN;
end
end


function validate_matrices(matrices, division, routeId)
baseFields = {'M', 'C1', 'K1', 'C2', 'K2', 'al'};
n = size(matrices.M, 1);
assert(isnumeric(matrices.M) && ismatrix(matrices.M) && ...
    size(matrices.M, 2) == n && n > 0 && all(isfinite(matrices.M), 'all'), ...
    'Board20Step4:InvalidMassMatrix', ...
    'Route %s has an invalid M matrix.', routeId);
for k = 2:numel(baseFields)
    field = baseFields{k};
    value = matrices.(field);
    assert(isnumeric(value) && isequal(size(value), [n, n]) && ...
        all(isfinite(value), 'all'), 'Board20Step4:InvalidMatrix', ...
        'Route %s has invalid matrix %s.', routeId, field);
end
assert(isnumeric(matrices.dt) && isscalar(matrices.dt) && ...
    isfinite(matrices.dt) && matrices.dt > 0, ...
    'Board20Step4:InvalidTimeStep', ...
    'Route %s has invalid dt.', routeId);
if strcmpi(division, 'div2')
    assert(isnumeric(matrices.DeltaC) && ...
        isequal(size(matrices.DeltaC), size(matrices.DeltaK)) && ...
        size(matrices.DeltaC, 1) == size(matrices.DeltaC, 2) && ...
        all(isfinite(matrices.DeltaC), 'all') && ...
        all(isfinite(matrices.DeltaK), 'all'), ...
        'Board20Step4:InvalidFeedbackMatrices', ...
        'Route %s has invalid DeltaC/DeltaK.', routeId);
    feedbackSize = size(matrices.DeltaC, 1);
    assert(isnumeric(matrices.S) && ...
        isequal(size(matrices.S), [feedbackSize, n]) && ...
        all(isfinite(matrices.S), 'all'), ...
        'Board20Step4:InvalidSelectionMatrix', ...
        'Route %s has invalid S dimensions.', routeId);
end
end


function validate_active_reference_bounds(route, reference)
regions = route.active_regions;
for k = 1:numel(regions)
    assert(double(regions(k).l_end) + 1 <= size(reference, 1) && ...
        double(regions(k).j_end) + 1 <= size(reference, 2), ...
        'Board20Step4:Step2ReferenceOutOfBounds', ...
        'Active region exceeds sealed step-2 stab for %s.', ...
        char(route.route_id));
end
end


function hash = hash_for_role(records, role)
index = find(strcmp({records.role}, role), 1);
assert(~isempty(index), 'Board20Step4:ContractRoleMissing', ...
    'Contract role is missing: %s', role);
hash = records(index).actual_sha256;
end


function value = resolve_relpath(baseDir, relativePath)
relativePath = strrep(char(relativePath), '/', filesep);
assert(~startsWith(relativePath, filesep) && ...
    isempty(regexp(relativePath, '^[A-Za-z]:', 'once')), ...
    'Board20Step4:ExpectedRelativePath', ...
    'Manifest path must be relative: %s', relativePath);
value = fullfile(baseDir, relativePath);
end


function text = normalize_point_status(value)
if ischar(value) || (isstring(value) && isscalar(value))
    text = upper(strtrim(char(value)));
else
    text = 'FAIL';
end
end


function values = normalize_text_list(value)
if isempty(value)
    values = {};
elseif ischar(value)
    values = {value};
elseif isstring(value)
    values = cellstr(value(:));
elseif iscell(value)
    values = cellfun(@char, value(:), 'UniformOutput', false);
else
    error('Board20Step4:InvalidTextList', ...
        'Expected char, string, or cell text list.');
end
end


function value = array_item(arrayValue, index)
if iscell(arrayValue)
    value = arrayValue{index};
else
    value = arrayValue(index);
end
end


function result = is_text_scalar(value)
result = ischar(value) || (isstring(value) && isscalar(value));
end


function result = is_text_list(value)
result = isempty(value) || ischar(value) || isstring(value) || ...
    (iscell(value) && all(cellfun(@(x) ischar(x) || ...
    (isstring(x) && isscalar(x)), value(:))));
end


function result = is_point_matrix(value)
result = isnumeric(value) && ismatrix(value) && ...
    (isempty(value) || size(value, 2) == 2) && ...
    all(isfinite(value), 'all') && all(value == floor(value), 'all') && ...
    all(value >= 0, 'all');
end


function result = is_integer_vector(value)
result = isnumeric(value) && isvector(value) && ~isempty(value) && ...
    all(isfinite(value)) && all(value == floor(value)) && all(value >= 0);
end


function value = timestamp_now()
value = char(datetime('now', 'TimeZone', 'local', ...
    'Format', 'yyyy-MM-dd''T''HH:mm:ssXXX'));
end


function value = sha256_file(pathValue)
digest = java.security.MessageDigest.getInstance('SHA-256');
stream = java.io.FileInputStream(java.io.File(char(pathValue)));
cleanup = onCleanup(@() stream.close());
channel = stream.getChannel();
buffer = java.nio.ByteBuffer.allocate(1024 * 1024);
while true
    count = channel.read(buffer);
    if count < 0
        break;
    end
    if count > 0
        buffer.flip();
        digest.update(buffer);
        buffer.clear();
    end
end
bytes = typecast(digest.digest(), 'uint8');
value = upper(reshape(dec2hex(bytes, 2).', 1, []));
end


function delete_if_exists(pathValue)
if isfile(pathValue)
    delete(pathValue);
end
end


function value = empty_summary_record()
value = struct( ...
    'route_id', '', ...
    'mode', '', ...
    'overall_status', '', ...
    'matrix_shape', [], ...
    'author_requested_points', 0, ...
    'common_requested_points', 0, ...
    'completed_points', 0, ...
    'fail_points', 0, ...
    'status_path', '');
end
