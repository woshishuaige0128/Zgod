function run_board17_local_candidates()
%RUN_BOARD17_LOCAL_CANDIDATES Isolated, auditable execution of frozen P/N candidates.
%
% This runner never edits the frozen inputs and never starts Simulink.  It
% separates literal execution, the most plausible frozen 15-DOF context,
% and a dimension-only probe.  The probe uses a0=a1=1 solely to expose
% downstream dimensions; those values are not historical coefficients.

code_dir = fileparts(mfilename('fullpath'));
candidate_root = fileparts(code_dir);
local_dir = fullfile(candidate_root, 'input', 'local_candidates');
response_dir = fullfile(candidate_root, 'input', 'response_chain');
output_dir = fullfile(candidate_root, 'outputs');
log_dir = fullfile(candidate_root, 'logs');

assert(isfolder(local_dir), 'BOARD17:MissingFrozenInputs', ...
    'Frozen local-candidate directory is missing: %s', local_dir);
assert(isfile(fullfile(response_dir, 'PDmonicanshu.m')), ...
    'BOARD17:MissingFrozenBase', 'Frozen PDmonicanshu.m is missing.');
if ~isfolder(output_dir); mkdir(output_dir); end
if ~isfolder(log_dir); mkdir(log_dir); end

log_path = fullfile(log_dir, 'local_candidates_matlab.log');
fid = fopen(log_path, 'w');
assert(fid >= 0, 'BOARD17:LogOpenFailed', 'Cannot open log: %s', log_path);
fprintf(fid, 'Board 17 local physical/numerical candidate execution\n');
fprintf(fid, 'Started: %s\n', char(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss.SSS')));
fprintf(fid, 'Frozen input: %s\n', local_dir);
fprintf(fid, 'No Simulink execution. a0=a1=1 is used only in dimension probes.\n');
fclose(fid);
diary(log_path);
cleanup_diary = onCleanup(@() diary('off')); %#ok<NASGU>

fprintf('\n=== Frozen physical-substructure scripts ===\n');
pd2 = execute_pd_script(fullfile(local_dir, 'PDmonicanshu2.m'), 'PDmonicanshu2.m');
pd3 = execute_pd_script(fullfile(local_dir, 'PDmonicanshu3.m'), 'PDmonicanshu3.m');
assert(strcmp(pd2.run_status, 'success'), 'BOARD17:PD2Failed', '%s', pd2.error_report);
assert(strcmp(pd3.run_status, 'success'), 'BOARD17:PD3Failed', '%s', pd3.error_report);

pd_summary = make_pd_summary(pd2, pd3);
writetable(pd_summary, fullfile(output_dir, 'local_pd_reduction_summary.csv'), ...
    'Encoding', 'UTF-8');

damping_audit = make_damping_audit(local_dir);
writetable(damping_audit, fullfile(output_dir, 'local_damping_comment_audit.csv'), ...
    'Encoding', 'UTF-8');

matrix_values = [matrix_long_rows(pd2); matrix_long_rows(pd3)];
writetable(matrix_values, fullfile(output_dir, 'local_pd_matrix_values.csv'), ...
    'Encoding', 'UTF-8');

modal_values = [modal_long_rows(pd2); modal_long_rows(pd3)];
writetable(modal_values, fullfile(output_dir, 'local_pd_modal_values.csv'), ...
    'Encoding', 'UTF-8');

save(fullfile(output_dir, 'local_pd_reductions.mat'), 'pd2', 'pd3', '-v7');

fprintf('\n=== Frozen New_* scripts: literal and contextual attempts ===\n');
script_names = {'New_Ps2.m', 'New_Ns2.m', 'New_Ps3.m', 'New_Ns3.m'};
pair_names = {'', 'New_Ps2.m', '', 'New_Ps3.m'};
attempts = repmat(empty_attempt(), 0, 1);
for i = 1:numel(script_names)
    attempts(end+1,1) = execute_new_attempt(local_dir, response_dir, ...
        script_names{i}, pair_names{i}, 'empty_workspace'); %#ok<AGROW>
    attempts(end+1,1) = execute_new_attempt(local_dir, response_dir, ...
        script_names{i}, pair_names{i}, 'frozen_full15_no_coeff'); %#ok<AGROW>
    attempts(end+1,1) = execute_new_attempt(local_dir, response_dir, ...
        script_names{i}, pair_names{i}, 'unit_coeff_dimension_probe'); %#ok<AGROW>
end

attempt_table = attempts_to_table(attempts);
writetable(attempt_table, fullfile(output_dir, 'local_new_script_attempts.csv'), ...
    'Encoding', 'UTF-8');
save(fullfile(output_dir, 'local_new_script_attempts.mat'), 'attempts', '-v7');

interface_table = make_interface_table(attempts);
writetable(interface_table, fullfile(output_dir, 'local_interface_dimension_audit.csv'), ...
    'Encoding', 'UTF-8');

gate_table = make_assembly_gate(pd2, pd3, attempts);
writetable(gate_table, fullfile(output_dir, 'local_assembly_12d_gate.csv'), ...
    'Encoding', 'UTF-8');

summary = make_json_summary(pd2, pd3, attempts, gate_table);
write_json(fullfile(output_dir, 'local_candidate_summary.json'), summary);

% Acceptance assertions describe facts that must remain true for this
% frozen snapshot.  They do not turn a dimension probe into reproduction.
assert(pd2.full_dof == 6 && pd2.guyan_dof == 2 && pd2.cb_dof == 5, ...
    'BOARD17:UnexpectedPD2Dimensions', 'Unexpected PDmonicanshu2 dimensions.');
assert(pd3.full_dof == 9 && pd3.guyan_dof == 2 && pd3.cb_dof == 5, ...
    'BOARD17:UnexpectedPD3Dimensions', 'Unexpected PDmonicanshu3 dimensions.');
assert(abs(pd2.damping_numeric - 0.1) <= eps && ...
       abs(pd3.damping_numeric - 0.1) <= eps, ...
    'BOARD17:UnexpectedPDDamping', 'Expected frozen PD scripts to use damping=0.1.');
assert(all(strcmp({attempts(strcmp({attempts.scenario}, 'empty_workspace')).run_status}, ...
                  'error')), ...
    'BOARD17:UnexpectedLiteralSuccess', 'A New_* script unexpectedly ran in an empty workspace.');
assert(strcmp(gate_table.Result(end), 'FAIL_PENDING_DECISION'), ...
    'BOARD17:UnexpectedAssemblyGate', 'The 12-DOF gate must remain failed/pending.');

fprintf('\n=== Final local-candidate result ===\n');
fprintf('PDmonicanshu2: 6 full -> 2 Guyan / 5 Craig-Bampton, damping=%.3f.\n', ...
    pd2.damping_numeric);
fprintf('PDmonicanshu3: 9 full -> 2 Guyan / 5 Craig-Bampton, damping=%.3f.\n', ...
    pd3.damping_numeric);
fprintf('New_* literal attempts: 4/4 expected errors in empty workspace.\n');
fprintf('12-DOF P/N assembly: FAIL_PENDING_DECISION; no 12x12 matrix was fabricated.\n');
fprintf('Outputs written to: %s\n', output_dir);
end

function s = execute_pd_script(script_path, script_name)
fprintf('Running %s exactly from frozen copy...\n', script_name);
s = struct();
s.script = script_name;
s.source_path = script_path;
s.run_status = 'error';
s.error_identifier = '';
s.error_message = '';
s.error_report = '';
try
    run(script_path);

    s.run_status = 'success';
    s.full_dof = size(KPrt, 1);
    s.master_dof = numel(index1);
    s.slave_dof = numel(index2);
    s.guyan_dof = size(KRren, 1);
    s.cb_modes = r;
    s.cb_dof = size(KR_cb, 1);
    s.damping_numeric = damping;
    s.damping_comment_claim = 0.05;
    s.damping_comment_consistency = abs(damping - 0.05) <= eps;
    s.index_master = index1;
    s.index_slave = index2;
    s.idx_all = idx_all;
    s.locate2 = locate2_if_present();
    s.alpha_rayleigh = alphas;
    s.full_frequency_hz = sorted_frequency(KPrt, MPrt);
    s.guyan_frequency_hz = sorted_frequency(KRren, MRren);
    s.cb_frequency_hz = sorted_frequency(KR_cb, MR_cb);
    s.fixed_interface_omega_raw = omega;
    s.KPrt = KPrt;
    s.MPrt = MPrt;
    s.CPrt = CPrt;
    s.KRren = KRren;
    s.MRren = MRren;
    s.CRren = CRren;
    s.T = T;
    s.T_cb = T_cb;
    s.KR_cb = KR_cb;
    s.MR_cb = MR_cb;
    s.CR_cb = CR_cb;
    s.matrix_finite = all(isfinite([KPrt(:); MPrt(:); CPrt(:); ...
        KRren(:); MRren(:); CRren(:); T(:); T_cb(:); ...
        KR_cb(:); MR_cb(:); CR_cb(:)]));
    fprintf('  success: full=%d, Guyan=%d, CB=%d, damping=%.3f\n', ...
        s.full_dof, s.guyan_dof, s.cb_dof, s.damping_numeric);
catch ME
    s.full_dof = NaN;
    s.master_dof = NaN;
    s.slave_dof = NaN;
    s.guyan_dof = NaN;
    s.cb_modes = NaN;
    s.cb_dof = NaN;
    s.damping_numeric = NaN;
    s.damping_comment_claim = 0.05;
    s.damping_comment_consistency = false;
    s.error_identifier = ME.identifier;
    s.error_message = ME.message;
    s.error_report = getReport(ME, 'extended', 'hyperlinks', 'off');
    fprintf('  ERROR %s: %s\n', ME.identifier, ME.message);
end
end

function locate2_value = locate2_if_present()
% The exact PD scripts define locate2 only in PDmonicanshu2.m.  The 9-DOF
% script expresses the mapping through its matrix construction but omits
% the locate2 assignment; retain an empty value instead of inventing one.
if evalin('caller', 'exist(''locate2'', ''var'')')
    locate2_value = evalin('caller', 'locate2');
else
    locate2_value = [];
end
end

function f = sorted_frequency(K, M)
lambda = eig(K, M);
lambda = real(lambda(abs(imag(lambda)) <= 1e-8 * max(1, abs(real(lambda)))));
lambda(lambda < 0 & abs(lambda) <= 1e-9 * max(1, max(abs(lambda)))) = 0;
f = sort(sqrt(lambda) / (2*pi));
end

function t = make_pd_summary(pd2, pd3)
p = [pd2; pd3];
n = numel(p);
Script = strings(n,1);
RunStatus = strings(n,1);
FullDOF = zeros(n,1);
MasterDOF = zeros(n,1);
SlaveDOF = zeros(n,1);
GuyanDOF = zeros(n,1);
CBModes = zeros(n,1);
CBDOF = zeros(n,1);
DampingNumeric = zeros(n,1);
DampingCommentClaim = zeros(n,1);
DampingCommentConsistency = false(n,1);
MatrixFinite = false(n,1);
for i = 1:n
    Script(i) = p(i).script;
    RunStatus(i) = p(i).run_status;
    FullDOF(i) = p(i).full_dof;
    MasterDOF(i) = p(i).master_dof;
    SlaveDOF(i) = p(i).slave_dof;
    GuyanDOF(i) = p(i).guyan_dof;
    CBModes(i) = p(i).cb_modes;
    CBDOF(i) = p(i).cb_dof;
    DampingNumeric(i) = p(i).damping_numeric;
    DampingCommentClaim(i) = p(i).damping_comment_claim;
    DampingCommentConsistency(i) = p(i).damping_comment_consistency;
    MatrixFinite(i) = p(i).matrix_finite;
end
t = table(Script, RunStatus, FullDOF, MasterDOF, SlaveDOF, GuyanDOF, ...
    CBModes, CBDOF, DampingNumeric, DampingCommentClaim, ...
    DampingCommentConsistency, MatrixFinite);
end

function t = make_damping_audit(local_dir)
names = {'PDmonicanshu2.m','PDmonicanshu3.m','New_Ps2.m', ...
    'New_Ns2.m','New_Ps3.m','New_Ns3.m'};
n = numel(names);
Script = string(names(:));
AssignmentLine = NaN(n,1);
DampingNumeric = NaN(n,1);
DampingCommentClaim = NaN(n,1);
CommentConsistency = false(n,1);
Observation = strings(n,1);
for i = 1:n
    lines = regexp(fileread(fullfile(local_dir, names{i})), '\r\n|\n|\r', 'split');
    found = false;
    for j = 1:numel(lines)
        token = regexp(lines{j}, ...
            'damping\s*=\s*([0-9.eE+\-]+)\s*;\s*%[^\r\n]*\(([0-9.]+)%\)', ...
            'tokens', 'once');
        if ~isempty(token)
            AssignmentLine(i) = j;
            DampingNumeric(i) = str2double(token{1});
            DampingCommentClaim(i) = str2double(token{2}) / 100;
            CommentConsistency(i) = abs(DampingNumeric(i) - ...
                DampingCommentClaim(i)) <= eps;
            if CommentConsistency(i)
                Observation(i) = 'MATCH';
            else
                Observation(i) = 'CONFLICT_NUMERIC_VALUE_VS_COMMENT';
            end
            found = true;
            break;
        end
    end
    if ~found
        Observation(i) = 'NO_LOCAL_DAMPING_ASSIGNMENT';
    end
end
t = table(Script, AssignmentLine, DampingNumeric, DampingCommentClaim, ...
    CommentConsistency, Observation);
end

function t = matrix_long_rows(p)
names = {'KPrt','MPrt','CPrt','KRren','MRren','CRren','T','T_cb', ...
    'KR_cb','MR_cb','CR_cb'};
Script = strings(0,1);
Matrix = strings(0,1);
MatrixRow = zeros(0,1);
MatrixColumn = zeros(0,1);
ValueReal = zeros(0,1);
ValueImag = zeros(0,1);
for k = 1:numel(names)
    A = p.(names{k});
    [rr, cc] = ndgrid(1:size(A,1), 1:size(A,2));
    count = numel(A);
    Script(end+1:end+count,1) = string(p.script); %#ok<AGROW>
    Matrix(end+1:end+count,1) = string(names{k}); %#ok<AGROW>
    MatrixRow(end+1:end+count,1) = rr(:); %#ok<AGROW>
    MatrixColumn(end+1:end+count,1) = cc(:); %#ok<AGROW>
    ValueReal(end+1:end+count,1) = real(A(:)); %#ok<AGROW>
    ValueImag(end+1:end+count,1) = imag(A(:)); %#ok<AGROW>
end
t = table(Script, Matrix, MatrixRow, MatrixColumn, ValueReal, ValueImag);
end

function t = modal_long_rows(p)
sets = {'full_frequency_hz','guyan_frequency_hz','cb_frequency_hz', ...
    'fixed_interface_omega_raw'};
labels = {'full_Hz','guyan_Hz','craig_bampton_Hz','fixed_interface_raw_rad_s'};
Script = strings(0,1);
Quantity = strings(0,1);
Index = zeros(0,1);
Value = zeros(0,1);
for k = 1:numel(sets)
    x = p.(sets{k});
    n = numel(x);
    Script(end+1:end+n,1) = string(p.script); %#ok<AGROW>
    Quantity(end+1:end+n,1) = string(labels{k}); %#ok<AGROW>
    Index(end+1:end+n,1) = (1:n)'; %#ok<AGROW>
    Value(end+1:end+n,1) = real(x(:)); %#ok<AGROW>
end
t = table(Script, Quantity, Index, Value);
end

function a = empty_attempt()
a = struct('script', '', 'scenario', '', 'run_status', '', ...
    'status_label', '', 'coefficient_source', '', 'paired_predecessor', '', ...
    'upstream_status', '', 'upstream_error_identifier', '', ...
    'upstream_error_message', '', 'error_identifier', '', 'error_message', '', ...
    'error_report', '', 'stack_top_file', '', 'stack_top_line', NaN, ...
    'KPrt_rows', NaN, 'MPrt_rows', NaN, 'CPrt_rows', NaN, ...
    'KPbar_rows', NaN, 'lP_rows', NaN, 'AgP_rows', NaN, ...
    'KNrt_rows', NaN, 'MNrt_rows', NaN, 'CNrt_rows', NaN, ...
    'KNbar_rows', NaN, 'lN_rows', NaN, 'AgN_rows', NaN, ...
    'locate_count', NaN, 'locate2_count', NaN, 'all_observed_finite', false, ...
    'notes', '');
end

function a = execute_new_attempt(local_dir, response_dir, script_name, ...
    paired_predecessor, scenario)
a = empty_attempt();
a.script = script_name;
a.scenario = scenario;
a.paired_predecessor = paired_predecessor;
script_path = fullfile(local_dir, script_name);
base_path = fullfile(response_dir, 'PDmonicanshu.m');

fprintf('Attempt %s [%s]...\n', script_name, scenario);
try
    if ~strcmp(scenario, 'empty_workspace')
        run(base_path);
        a.upstream_status = 'PDmonicanshu_success';
    else
        a.upstream_status = 'none';
    end

    if strcmp(scenario, 'unit_coeff_dimension_probe')
        a0 = 1; %#ok<NASGU>
        a1 = 1; %#ok<NASGU>
        a.coefficient_source = 'unit_probe_only_not_historical';
    else
        a.coefficient_source = 'not_defined_in_frozen_m_files_or_slx_workspace';
    end

    if ~isempty(paired_predecessor) && ~strcmp(scenario, 'empty_workspace')
        predecessor_path = fullfile(local_dir, paired_predecessor);
        try
            run(predecessor_path);
            a.upstream_status = [a.upstream_status '+paired_predecessor_success'];
        catch predecessor_ME
            a.upstream_status = [a.upstream_status '+paired_predecessor_error_continued'];
            a.upstream_error_identifier = predecessor_ME.identifier;
            a.upstream_error_message = predecessor_ME.message;
        end
    end

    run(script_path);
    a.run_status = 'success';
    if strcmp(scenario, 'unit_coeff_dimension_probe')
        a.status_label = 'DIMENSION_PROBE_ONLY_NOT_REPRODUCTION';
    else
        a.status_label = 'LITERAL_SUCCESS';
    end
catch ME
    a.run_status = 'error';
    a.status_label = 'FAILED_ATTEMPT';
    a.error_identifier = ME.identifier;
    a.error_message = ME.message;
    a.error_report = getReport(ME, 'extended', 'hyperlinks', 'off');
    if ~isempty(ME.stack)
        a.stack_top_file = ME.stack(1).file;
        a.stack_top_line = ME.stack(1).line;
    end
end

% Variables created before a script error remain valuable evidence.
a.KPrt_rows = local_rows('KPrt');
a.MPrt_rows = local_rows('MPrt');
a.CPrt_rows = local_rows('CPrt');
a.KPbar_rows = local_rows('KPbar');
a.lP_rows = local_rows('lP');
a.AgP_rows = local_rows('AgP');
a.KNrt_rows = local_rows('KNrt');
a.MNrt_rows = local_rows('MNrt');
a.CNrt_rows = local_rows('CNrt');
a.KNbar_rows = local_rows('KNbar');
a.lN_rows = local_rows('lN');
a.AgN_rows = local_rows('AgN');
a.locate_count = local_numel('locate');
a.locate2_count = local_numel('locate2');
a.all_observed_finite = observed_finite();
a.notes = classify_attempt_notes(a);

if strcmp(a.run_status, 'success')
    fprintf('  success (%s): P K/vector=%g/%g, N K/vector=%g/%g\n', ...
        a.status_label, a.KPrt_rows, a.lP_rows, a.KNrt_rows, a.lN_rows);
else
    fprintf('  ERROR %s at line %g: %s\n', a.error_identifier, ...
        a.stack_top_line, a.error_message);
end
end

function n = local_rows(name)
if evalin('caller', sprintf('exist(''%s'', ''var'')', name))
    value = evalin('caller', name);
    n = size(value, 1);
else
    n = NaN;
end
end

function n = local_numel(name)
if evalin('caller', sprintf('exist(''%s'', ''var'')', name))
    value = evalin('caller', name);
    n = numel(value);
else
    n = NaN;
end
end

function tf = observed_finite()
names = {'KPrt','MPrt','CPrt','KPbar','lP','AgP', ...
    'KNrt','MNrt','CNrt','KNbar','lN','AgN'};
tf = true;
found = false;
for i = 1:numel(names)
    if evalin('caller', sprintf('exist(''%s'', ''var'')', names{i}))
        x = evalin('caller', names{i});
        tf = tf && all(isfinite(x(:)));
        found = true;
    end
end
tf = tf && found;
end

function note = classify_attempt_notes(a)
if strcmp(a.scenario, 'empty_workspace')
    note = 'Literal empty-workspace execution; external dependencies intentionally absent.';
elseif strcmp(a.scenario, 'frozen_full15_no_coeff')
    note = ['Frozen PDmonicanshu.m supplied structural variables; a0/a1 were not ' ...
        'invented, so the exact stopping point is retained.'];
else
    note = ['a0=a1=1 only bypasses the missing coefficient source to reveal later ' ...
        'matrix/vector dimensions; numerical values are not historical results.'];
end
end

function t = attempts_to_table(a)
t = struct2table(a);
end

function t = make_interface_table(attempts)
probe = attempts(strcmp({attempts.scenario}, 'unit_coeff_dimension_probe'));
n = numel(probe);
Script = strings(n,1);
PMatrixRows = NaN(n,1);
PLoadRows = NaN(n,1);
PInternalCompatible = false(n,1);
NMatrixRows = NaN(n,1);
NLoadRows = NaN(n,1);
NInternalCompatible = false(n,1);
LocateCount = NaN(n,1);
Locate2Count = NaN(n,1);
DimensionFinding = strings(n,1);
for i = 1:n
    Script(i) = probe(i).script;
    PMatrixRows(i) = probe(i).KPrt_rows;
    PLoadRows(i) = probe(i).lP_rows;
    PInternalCompatible(i) = same_or_missing(PMatrixRows(i), PLoadRows(i));
    NMatrixRows(i) = probe(i).KNrt_rows;
    NLoadRows(i) = probe(i).lN_rows;
    NInternalCompatible(i) = same_or_missing(NMatrixRows(i), NLoadRows(i));
    LocateCount(i) = probe(i).locate_count;
    Locate2Count(i) = probe(i).locate2_count;
    if contains(probe(i).script, 'Ps3') && PMatrixRows(i) == 9 && PLoadRows(i) == 6
        DimensionFinding(i) = 'FAIL: 9x9 physical matrices but 6x1 physical vectors.';
    elseif contains(probe(i).script, 'Ns2') && NMatrixRows(i) == 11 && NLoadRows(i) == 15
        DimensionFinding(i) = 'FAIL: 11x11 numerical matrices but 15x1 numerical vectors.';
    elseif contains(probe(i).script, 'Ns3') && NMatrixRows(i) == 15 && LocateCount(i) == 14
        DimensionFinding(i) = 'FAIL: 15x15 numerical matrices while locate declares 14 coordinates.';
    elseif contains(probe(i).script, 'Ps2') && PMatrixRows(i) == 6 && PLoadRows(i) == 6
        DimensionFinding(i) = 'PASS internally for physical 6-DOF probe only.';
    else
        DimensionFinding(i) = 'No additional deterministic finding.';
    end
end
t = table(Script, PMatrixRows, PLoadRows, PInternalCompatible, ...
    NMatrixRows, NLoadRows, NInternalCompatible, LocateCount, ...
    Locate2Count, DimensionFinding);
end

function tf = same_or_missing(a, b)
tf = (isnan(a) && isnan(b)) || (~isnan(a) && ~isnan(b) && a == b);
end

function t = make_assembly_gate(pd2, pd3, attempts)
Gate = [
    "Physical substructure Craig-Bampton matrix available";
    "Numerical substructure Craig-Bampton matrix available";
    "Two shared-interface coordinates explicitly assembled";
    "Physical matrix and load-vector dimensions internally compatible";
    "Numerical matrix and load-vector dimensions internally compatible";
    "Newmark a0/a1 provenance available in frozen inputs";
    "Assembled 12x12 M/C/K matrices produced by frozen route";
    "Final 12-DOF calculation-level reproduction gate"];
Expected = [
    "5 DOF for each physical candidate";
    "9 DOF for each numerical candidate";
    "2 shared coordinates and an explicit Boolean/assembly operator";
    "matrix rows equal load-vector rows";
    "matrix rows equal load-vector rows";
    "author-defined coefficient values or initialization route";
    "all three matrices finite and dimension 12x12";
    "all preceding gates PASS"];
Observed = [
    sprintf('PASS: %s=%d, %s=%d', pd2.script, pd2.cb_dof, pd3.script, pd3.cb_dof);
    "FAIL: New_Ns2/New_Ns3 contain no Guyan or Craig-Bampton reduction";
    "FAIL: locate arrays exist, but no reduced P/N assembly operator exists";
    "FAIL: New_Ps3 has 9x9 matrices and 6x1 vectors (New_Ps2 is 6/6)";
    "FAIL: New_Ns2 has 11x11 matrices and 15x1 vectors; New_Ns3 is not a reduced 9-DOF model";
    "FAIL: SLX declares a0/a1 as workspace parameters but frozen inputs provide no values";
    "FAIL: no frozen script creates assembled 12x12 M/C/K matrices";
    "FAIL_PENDING_DECISION"];
Result = ["PASS"; "FAIL"; "FAIL"; "FAIL"; "FAIL"; "FAIL"; "FAIL"; ...
    "FAIL_PENDING_DECISION"];
Evidence = [
    "local_pd_reductions.mat";
    "New_Ns2.m and New_Ns3.m exact source plus local_new_script_attempts.csv";
    "locate/locate2 dimensions in local_interface_dimension_audit.csv";
    "unit_coeff_dimension_probe rows in local_interface_dimension_audit.csv";
    "unit_coeff_dimension_probe rows in local_interface_dimension_audit.csv";
    "local_slx_static_probe XML and frozen m-file search";
    "all six frozen local-candidate scripts";
    "local_assembly_12d_gate.csv"];
t = table(Gate, Expected, Observed, Result, Evidence);

% Make the otherwise unused input explicit: attempts are the live evidence
% used to create the interface table and must include all 12 scenarios.
assert(numel(attempts) == 12, 'BOARD17:AttemptCount', ...
    'Expected exactly 12 New_* execution attempts.');
end

function summary = make_json_summary(pd2, pd3, attempts, gate_table)
summary = struct();
summary.generated_at = [char(datetime('now', ...
    'Format', 'yyyy-MM-dd''T''HH:mm:ss.SSS')) '+08:00'];
summary.scope = 'Frozen local P/N candidates only; no Simulink, excitation, response, stability, or plotting run.';
summary.status_labels = struct( ...
    'pd2_pd3', 'CALCULATION_LEVEL_LOCAL_SUBSTRUCTURE_ONLY', ...
    'new_scripts', 'FAILED_ATTEMPTS_OR_DIMENSION_PROBES', ...
    'assembled_12d', 'FAILED_ATTEMPT_PENDING_DECISION');
summary.pd_candidates = [pd_json(pd2), pd_json(pd3)];
summary.new_attempt_count = numel(attempts);
summary.new_attempt_success_count = sum(strcmp({attempts.run_status}, 'success'));
summary.new_attempt_error_count = sum(strcmp({attempts.run_status}, 'error'));
summary.dimension_probe_disclaimer = ...
    'a0=a1=1 was used only to expose dimensions and is not an author value or historical result.';
summary.assembly_12d_claim_arithmetic = 'manuscript: numerical CB 9 + physical CB 5 - two shared interfaces = 12';
summary.assembly_12d_observed = char(gate_table.Observed(end));
summary.assembly_12d_result = char(gate_table.Result(end));
summary.no_assembled_matrix_created = true;
end

function x = pd_json(p)
x = struct('script', p.script, 'run_status', p.run_status, ...
    'full_dof', p.full_dof, 'master_dof', p.master_dof, ...
    'slave_dof', p.slave_dof, 'guyan_dof', p.guyan_dof, ...
    'cb_modes', p.cb_modes, 'cb_dof', p.cb_dof, ...
    'damping_numeric', p.damping_numeric, ...
    'damping_comment_claim', p.damping_comment_claim, ...
    'damping_comment_consistency', p.damping_comment_consistency, ...
    'matrix_finite', p.matrix_finite);
end

function write_json(path, value)
text = jsonencode(value, 'PrettyPrint', true);
fid = fopen(path, 'w', 'n', 'UTF-8');
assert(fid >= 0, 'BOARD17:JSONOpenFailed', 'Cannot open JSON: %s', path);
cleanup_file = onCleanup(@() fclose(fid)); %#ok<NASGU>
fwrite(fid, text, 'char');
fwrite(fid, newline, 'char');
end
