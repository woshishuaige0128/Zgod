function build_board20_step8c_routes_matlab()
%BUILD_BOARD20_STEP8C_ROUTES_MATLAB 由冻结工作区建立图4-4/图4-5六条矩阵链。
% 数值输入仅包括后缀2/后缀3 rep03 workspace_complete.mat 和步骤8B MAT合同。
% 本程序不读取论文PDF、历史稳定域掩膜或边界坐标。

code_dir = fileparts(mfilename('fullpath'));
board20 = fileparts(code_dir);
out_dir = fullfile(board20, 'outputs', 'step8c_六链模型生成', 'matlab');
if ~exist(out_dir, 'dir')
    mkdir(out_dir);
end

input_paths = struct();
input_paths.div1 = fullfile(board20, 'outputs', 'step2_runs', 'main_ori_div1', ...
    'original_mlx', 'rep03', 'workspace', 'workspace_complete.mat');
input_paths.div2 = fullfile(board20, 'outputs', 'step2_runs', 'main_ori_div2', ...
    'original_mlx', 'rep03', 'workspace', 'workspace_complete.mat');
input_paths.contract = fullfile(board20, 'outputs', 'step8b_论文代码矩阵合同', ...
    '步骤8B_基础矩阵与选择矩阵.mat');
must_exist(input_paths.div1);
must_exist(input_paths.div2);
must_exist(input_paths.contract);

keep = {'MRrt','CRrt','KRrt','MPrt','CPrt','KPrt','alpha','delta','dt'};
source1 = load(input_paths.div1, keep{:});
source2 = load(input_paths.div2, keep{:});
contract = load(input_paths.contract);

specs(1) = struct('division', 1, 'figure_label', '图4-4', ...
    'master', [1 6 11 4 9 14], 'slave', [2 3 5 7 8 10 12 13 15], ...
    'local_dofs', [1 2 3 6 7 8], 'expected_dims', [15 6 9], ...
    'source_path', input_paths.div1);
specs(2) = struct('division', 2, 'figure_label', '图4-5', ...
    'master', [1 11 4 9 14], 'slave', [6 2 3 5 7 8 10 12 13 15], ...
    'local_dofs', [1 2 3 6 7 8 11 12 13], 'expected_dims', [15 5 8], ...
    'source_path', input_paths.div2);
sources = {source1, source2};

division_cells = cell(1, 2);
route_cells = cell(1, 6);
route_index = 0;
route_rows = cell(7, 18);
route_rows(1,:) = {'路线ID','图号','方法','主矩阵版本','维数','R维数','rank(R)', ...
    'rank(S)','M最小特征值','C最小特征值','K最小特征值','M相对不对称', ...
    'C相对不对称','K相对不对称','静力相对残差','固定界面最大残差', ...
    '步骤8B最大相对差','门状态'};
cb_rows = {'图号','划分类别','模态序号','特征值','频率_Hz','最大绝对分量行号', ...
    '该分量数值','模态质量','固定界面相对残差'};
local_rows = {'图号','局部完整维数','E维数','J维数','J乘E转置与S_N误差', ...
    '局部静力相对残差','标准M最小特征值','标准C最小特征值', ...
    '标准K最小特征值','历史与标准M相对差','历史与标准C相对差', ...
    '历史与标准K相对差','步骤8B局部最大相对差','门状态'};
petrov_rows = {'图号','审计对象','W维数','rank(W)','S_L维数','S_R维数', ...
    'rank(S_L)','rank(S_R)','S_L第二时延通道范数','S_R第二时延通道范数', ...
    '第二时延通道判读','M的W转置AR与历史单边矩阵相对差', ...
    'C的W转置AR与历史单边矩阵相对差','K的W转置AR与历史单边矩阵相对差', ...
    'S_R与R01-R04主路线S相对差','右乘H等于I时因子闭合最大相对差', ...
    '左乘H等于I时因子闭合最大相对差','R05_R06可执行控制候选', ...
    'Petrov审计门状态'};

for d = 1:2
    div = build_division(sources{d}, specs(d), contract);
    division_cells{d} = div;

    for mode_index = 1:3
        [~, pivot] = max(abs(div.global.fixed_modes(:, mode_index)));
        cb_rows(end+1,:) = {div.figure_label, sprintf('第%d类', d), mode_index, ...
            div.global.fixed_eigenvalues(mode_index), div.global.fixed_frequency_hz(mode_index), ...
            pivot, div.global.fixed_modes(pivot, mode_index), ...
            div.global.fixed_modes(:,mode_index)' * div.global.Mss * ...
            div.global.fixed_modes(:,mode_index), div.global.fixed_residual(mode_index)}; %#ok<AGROW>
    end

    local_pass = div.local.contract_max_relative_difference <= 1e-10 && ...
        div.local.embedding_identity_error <= 1e-12 && ...
        div.local.static_residual <= 1e-12 && all(div.local.standard_min_eigenvalue > 0);
    local_rows(end+1,:) = {div.figure_label, size(div.local.full.M,1), ...
        shape_text(div.local.E), shape_text(div.local.J), div.local.embedding_identity_error, ...
        div.local.static_residual, div.local.standard_min_eigenvalue(1), ...
        div.local.standard_min_eigenvalue(2), div.local.standard_min_eigenvalue(3), ...
        relative_difference(div.local.two_channel_historical.M, div.local.two_channel_standard.M), ...
        relative_difference(div.local.two_channel_historical.C, div.local.two_channel_standard.C), ...
        relative_difference(div.local.two_channel_historical.K, div.local.two_channel_standard.K), ...
        div.local.contract_max_relative_difference, pass_text(local_pass)}; %#ok<AGROW>

    petrov = div.global.guyan_petrov_audit;
    petrov_rows(end+1,:) = {div.figure_label, '历史单边Guyan（仅审计证据）', ...
        shape_text(petrov.W_natural), petrov.rank_W, shape_text(petrov.S_L), ...
        shape_text(petrov.S_R), petrov.rank_S_L, petrov.rank_S_R, ...
        petrov.S_L_second_channel_norm, petrov.S_R_second_channel_norm, ...
        petrov.second_channel_interpretation, petrov.relative_difference_M, ...
        petrov.relative_difference_C, petrov.relative_difference_K, ...
        petrov.S_R_primary_selector_relative_difference, ...
        petrov.right_factor_identity_closure_max_relative_difference, ...
        petrov.left_factor_identity_closure_max_relative_difference, ...
        petrov.executable_control_candidate_status, petrov.status}; %#ok<AGROW>

    methods = {'Original','Guyan','Craig-Bampton'};
    for m = 1:numel(methods)
        route_index = route_index + 1;
        route = build_route(div, methods{m}, contract);
        route_cells{route_index} = route;
        output_name = route_output_name(route);
        save(fullfile(out_dir, output_name), 'route', '-v7.3');

        route_rows(route_index+1,:) = {route.route_id, route.figure_label, route.method_cn, ...
            route.selected_variant, route.dimension, shape_text(route.R_natural), ...
            route.validation.rank_R, route.validation.rank_S, ...
            route.validation.min_eigenvalue_M, route.validation.min_eigenvalue_C, ...
            route.validation.min_eigenvalue_K, route.validation.relative_asymmetry_M, ...
            route.validation.relative_asymmetry_C, route.validation.relative_asymmetry_K, ...
            route.validation.static_residual, route.validation.fixed_interface_max_residual, ...
            route.validation.contract_max_relative_difference, route.validation.status};
    end
end

divisions = [division_cells{:}];
routes = [route_cells{:}];
metadata = struct();
metadata.status = 'PASS_六链模型已生成';
metadata.identity = '来源补全重建；不是作者六份Live Script原样执行';
metadata.numerical_inputs = input_paths;
metadata.forbidden_inputs = {'梁禹手稿.pdf','任何历史稳定域掩膜','任何论文曲线坐标'};
metadata.alpha = [divisions.alpha];
metadata.delta = [divisions.delta];
metadata.dt = [divisions.dt];
metadata.formula_guyan_historical = 'A_mm + A_ms Psi_s';
metadata.formula_guyan_standard = 'T'' A_order T';
metadata.formula_cb = 'T_CB'' A_order T_CB；固定界面特征值升序，前三模态';
metadata.formula_delay_left = 'S'' D(z) A_2 S';
metadata.formula_delay_right = 'S'' A_2 D(z) S';
metadata.petrov_audit_scope = '历史单边Guyan只保存Petrov审计证据；不改变R01-R04标准合同主路线数值';
metadata.petrov_test_basis = 'W=P''*[I;0]';
metadata.petrov_selectors = 'S_R=J*E''*R；S_L=J*E''*W';
metadata.petrov_delay_right = 'W''*E*A_local*J''*H*S_R';
metadata.petrov_delay_left = 'S_L''*H*J*A_local*E''*R';
metadata.excluded_executable_candidates = {'R05','R06'};
metadata.exclusion_reason = ['MATLAB仅生成六条底模与Petrov审计，不生成控制候选；' ...
    'Python另存R05/R06的BLOCKED诊断包，禁止进入论文网格'];

all_pass = all(arrayfun(@(x) strcmp(x.validation.status, 'PASS'), routes));
all_pass = all_pass && all(strcmp(local_rows(2:end,end), 'PASS'));
all_pass = all_pass && all(strcmp(petrov_rows(2:end,end), 'PASS'));
if ~all_pass
    error('步骤8C矩阵门禁未全部通过。请查看CSV。');
end

save(fullfile(out_dir, '步骤8C_六链模型汇总.mat'), ...
    'routes', 'divisions', 'metadata', 'input_paths', '-v7.3');
writecell(route_rows, fullfile(out_dir, '六链模型与矩阵门禁.csv'), 'Encoding', 'UTF-8');
writecell(cb_rows, fullfile(out_dir, 'CB排序3模态检查.csv'), 'Encoding', 'UTF-8');
writecell(local_rows, fullfile(out_dir, '两类局部完整与两通道矩阵检查.csv'), 'Encoding', 'UTF-8');
writecell(petrov_rows, fullfile(out_dir, 'Guyan历史单边Petrov门禁.csv'), 'Encoding', 'UTF-8');
write_summary(fullfile(out_dir, '步骤8C_六链模型生成摘要.md'), routes, divisions, input_paths);

fprintf('STEP8C_STATUS=PASS\n');
fprintf('STEP8C_ROUTES=%d\n', numel(routes));
fprintf('STEP8C_OUTPUT=%s\n', out_dir);
for k = 1:numel(routes)
    fprintf('%s dim=%d rankR=%d minEig=[%.9g %.9g %.9g] contractRel=%.3e PASS\n', ...
        routes(k).route_id, routes(k).dimension, routes(k).validation.rank_R, ...
        routes(k).validation.min_eigenvalue_M, routes(k).validation.min_eigenvalue_C, ...
        routes(k).validation.min_eigenvalue_K, ...
        routes(k).validation.contract_max_relative_difference);
end
for d = 1:numel(divisions)
    petrov = divisions(d).global.guyan_petrov_audit;
    fprintf('%s Guyan-Petrov rankW=%d rankSL=%d rankSR=%d histRelMax=%.3e SL2=%.3e %s\n', ...
        divisions(d).figure_label, petrov.rank_W, petrov.rank_S_L, ...
        petrov.rank_S_R, petrov.historical_matrix_max_relative_difference, ...
        petrov.S_L_second_channel_norm, petrov.status);
end
end

function div = build_division(source, spec, contract)
full_model = matrix_set(source.MRrt, source.CRrt, source.KRrt);
local_full = matrix_set(source.MPrt, source.CPrt, source.KPrt);
assert(isequal(size(full_model.M), [15 15]));
assert(isequal(size(local_full.M), [numel(spec.local_dofs) numel(spec.local_dofs)]));
assert(isscalar(source.alpha) && isscalar(source.delta) && isscalar(source.dt));

order = [spec.master spec.slave];
n_master = numel(spec.master);
ordered = matrix_set(full_model.M(order,order), full_model.C(order,order), full_model.K(order,order));
Mss = ordered.M(n_master+1:end,n_master+1:end);
Ksm = ordered.K(n_master+1:end,1:n_master);
Kss = ordered.K(n_master+1:end,n_master+1:end);
static_relation = -(Kss \ Ksm);
Tg = [eye(n_master); static_relation];
historical = matrix_set( ...
    ordered.M(1:n_master,1:n_master) + ordered.M(1:n_master,n_master+1:end)*static_relation, ...
    ordered.C(1:n_master,1:n_master) + ordered.C(1:n_master,n_master+1:end)*static_relation, ...
    ordered.K(1:n_master,1:n_master) + ordered.K(1:n_master,n_master+1:end)*static_relation);
standard = matrix_set(Tg'*ordered.M*Tg, Tg'*ordered.C*Tg, Tg'*ordered.K*Tg);

[phi_all, lambda_all] = eig(Kss, Mss, 'vector');
[lambda_all, idx] = sort(real(lambda_all), 'ascend');
phi_all = real(phi_all(:,idx));
phi = phi_all(:,1:3);
lambda = lambda_all(1:3);
for j = 1:3
    phi(:,j) = phi(:,j) / sqrt(phi(:,j)'*Mss*phi(:,j));
    [~, pivot] = max(abs(phi(:,j)));
    if phi(pivot,j) < 0
        phi(:,j) = -phi(:,j);
    end
end
Tcb = [eye(n_master), zeros(n_master,3); static_relation, phi];
cb = matrix_set(Tcb'*ordered.M*Tcb, Tcb'*ordered.C*Tcb, Tcb'*ordered.K*Tcb);
P = eye(15); P = P(order,:);
R_original = eye(15);
R_guyan = P'*Tg;
R_cb = P'*Tcb;
S_natural = eye(15); S_natural = S_natural([1 6],:);
S_original = S_natural*R_original;
S_guyan = S_natural*R_guyan;
S_cb = S_natural*R_cb;

fixed_residual = zeros(3,1);
for j = 1:3
    lhs = Kss*phi(:,j);
    fixed_residual(j) = norm(lhs - lambda(j)*Mss*phi(:,j)) / max(norm(lhs), eps);
end
static_residual = norm(Kss*static_relation + Ksm, 'fro') / max(norm(Ksm,'fro'), eps);

E = eye(15); E = E(:,spec.local_dofs);
J = eye(numel(spec.local_dofs)); J = J([1 4],:);
local_two = build_local_two_channel(local_full);
local_contract_rel = compare_local_contract(contract, spec.division, local_full, E, J, local_two, source);
W_guyan = P' * [eye(n_master); zeros(numel(spec.slave), n_master)];
guyan_petrov_audit = build_guyan_petrov_audit(full_model, historical, R_guyan, ...
    W_guyan, S_guyan, E, J, local_full, spec);

div = struct();
div.division = spec.division;
div.figure_label = spec.figure_label;
div.source_workspace = spec.source_path;
div.alpha = source.alpha;
div.delta = source.delta;
div.dt = source.dt;
div.master = spec.master;
div.slave = spec.slave;
div.order = order;
div.expected_dims = spec.expected_dims;
div.full = full_model;
div.global = struct('ordered', ordered, 'Mss', Mss, 'Kss', Kss, ...
    'static_relation', static_relation, 'T_guyan', Tg, ...
    'guyan_historical', historical, 'guyan_standard', standard, ...
    'fixed_modes', phi, 'fixed_eigenvalues', lambda, ...
    'fixed_frequency_hz', sqrt(max(lambda,0))/(2*pi), ...
    'fixed_residual', fixed_residual, 'T_cb', Tcb, 'cb_sorted', cb, ...
    'R_original', R_original, 'R_guyan', R_guyan, 'R_cb', R_cb, ...
    'S_natural_psi1_psi6', S_natural, 'S_original', S_original, ...
    'S_guyan', S_guyan, 'S_cb', S_cb, 'W_guyan', W_guyan, ...
    'guyan_petrov_audit', guyan_petrov_audit, 'static_residual', static_residual);
div.local = struct('full', local_full, 'global_dofs', spec.local_dofs, ...
    'E', E, 'J', J, 'two_channel_historical', local_two.historical, ...
    'two_channel_standard', local_two.standard, 'T_two_channel', local_two.T, ...
    'order_two_channel', local_two.order, 'static_relation', local_two.static_relation, ...
    'static_residual', local_two.static_residual, ...
    'standard_min_eigenvalue', min_eigenvalues(local_two.standard), ...
    'embedding_identity_error', norm(J*E' - S_natural, 'fro'), ...
    'contract_max_relative_difference', local_contract_rel);
end

function route = build_route(div, method, contract)
empty_set = matrix_set([],[],[]);
empty_petrov = struct();
switch method
    case 'Original'
        selected = div.full;
        selected_variant = '15维完整模型';
        historical = empty_set;
        standard = empty_set;
        cb_sorted = empty_set;
        R = div.global.R_original;
        S = div.global.S_original;
        petrov_audit = empty_petrov;
        method_cn = 'Original（完整模型）';
    case 'Guyan'
        selected = div.global.guyan_standard;
        selected_variant = '标准合同投影T''AT；同时保留历史单边矩阵';
        historical = div.global.guyan_historical;
        standard = div.global.guyan_standard;
        cb_sorted = empty_set;
        R = div.global.R_guyan;
        S = div.global.S_guyan;
        petrov_audit = div.global.guyan_petrov_audit;
        method_cn = 'Guyan（历史+标准）';
    case 'Craig-Bampton'
        selected = div.global.cb_sorted;
        selected_variant = '固定界面特征值升序的前三模态';
        historical = empty_set;
        standard = empty_set;
        cb_sorted = div.global.cb_sorted;
        R = div.global.R_cb;
        S = div.global.S_cb;
        petrov_audit = empty_petrov;
        method_cn = 'Craig-Bampton（排序3模态）';
    otherwise
        error('未知方法：%s', method);
end

contract_rel = compare_route_contract(contract, div, method, selected, historical, standard, R, S);
mins = min_eigenvalues(selected);
asym = relative_asymmetries(selected);
fixed_max = max(div.global.fixed_residual);
expected_dim = div.expected_dims(strcmp({'Original','Guyan','Craig-Bampton'}, method));
pass = size(selected.M,1) == expected_dim && size(selected.M,2) == expected_dim && ...
    rank(R) == expected_dim && rank(S) == 2 && all(mins > 0) && ...
    all(asym < 1e-10) && div.global.static_residual <= 1e-12 && ...
    fixed_max <= 1e-10 && contract_rel <= 1e-10 && ...
    div.local.contract_max_relative_difference <= 1e-10;

route = struct();
route.route_id = sprintf('图4-%d_%s_%d维', div.division+3, strrep(method,'Craig-Bampton','CB'), expected_dim);
route.figure_label = div.figure_label;
route.division = div.division;
route.method = method;
route.method_cn = method_cn;
route.identity = '来源补全重建';
route.source_workspace = div.source_workspace;
route.alpha = div.alpha;
route.delta = div.delta;
route.dt = div.dt;
route.dimension = expected_dim;
route.master_natural_dofs = div.master;
route.slave_natural_dofs = div.slave;
route.selected_variant = selected_variant;
route.M = selected.M;
route.C = selected.C;
route.K = selected.K;
route.guyan_historical = historical;
route.guyan_standard = standard;
route.guyan_historical_petrov_audit = petrov_audit;
route.cb_sorted = cb_sorted;
route.R_natural = R;
route.S_psi1_psi6 = S;
route.fixed_interface_modes = div.global.fixed_modes;
route.fixed_interface_eigenvalues = div.global.fixed_eigenvalues;
route.fixed_interface_frequency_hz = div.global.fixed_frequency_hz;
route.local = div.local;
route.delay_factors_from_local_full = full_local_delay_factors(R, S, div.local);
route.delay_factors_two_channel_historical = two_channel_delay_factors(S, div.local.two_channel_historical);
route.delay_factors_two_channel_standard = two_channel_delay_factors(S, div.local.two_channel_standard);
route.executable_candidate_scope = ['MATLAB仅生成六条底模与Petrov审计，不生成控制候选；' ...
    'Python另存R05/R06的BLOCKED诊断包，禁止进入论文网格'];
route.validation = struct('rank_R', rank(R), 'rank_S', rank(S), ...
    'min_eigenvalue_M', mins(1), 'min_eigenvalue_C', mins(2), ...
    'min_eigenvalue_K', mins(3), 'relative_asymmetry_M', asym(1), ...
    'relative_asymmetry_C', asym(2), 'relative_asymmetry_K', asym(3), ...
    'static_residual', div.global.static_residual, ...
    'fixed_interface_max_residual', fixed_max, ...
    'contract_max_relative_difference', contract_rel, 'status', pass_text(pass));
end

function audit = build_guyan_petrov_audit(full_model, historical, R, W, S_primary, E, J, local_full, spec)
% 历史单边Guyan可写成Petrov投影W'*A*R；仅用于追溯R05/R06历史路线。
S_R = J*E'*R;
S_L = J*E'*W;
reconstructed = matrix_set(W'*full_model.M*R, W'*full_model.C*R, W'*full_model.K*R);
relative_differences = [relative_difference(reconstructed.M, historical.M), ...
    relative_difference(reconstructed.C, historical.C), ...
    relative_difference(reconstructed.K, historical.K)];
delay_factors = petrov_full_local_delay_factors(W, R, S_L, S_R, E, J, local_full);

right_closure = zeros(1,3);
left_closure = zeros(1,3);
names = {'M','C','K'};
for k = 1:3
    name = names{k};
    A = local_full.(name);
    right_direct = W'*E*A*J'*eye(2)*S_R;
    left_direct = S_L'*eye(2)*J*A*E'*R;
    right_from_factors = delay_factors.(name).right_before_H*eye(2)* ...
        delay_factors.(name).right_after_H;
    left_from_factors = delay_factors.(name).left_before_H*eye(2)* ...
        delay_factors.(name).left_after_H;
    right_closure(k) = relative_difference(right_from_factors, right_direct);
    left_closure(k) = relative_difference(left_from_factors, left_direct);
end

left_second_norm = norm(S_L(2,:), 2);
right_second_norm = norm(S_R(2,:), 2);
if spec.division == 2
    second_channel_interpretation = [ ...
        '预期为零：图4-5的物理psi6不在测试空间W；仅限制历史Petrov路线，' ...
        '不改变R01-R04标准合同主路线'];
else
    second_channel_interpretation = '非零：图4-4的物理psi6属于测试空间W';
end
selector_rel = relative_difference(S_R, S_primary);
pass = rank(W) == size(W,2) && rank(S_R) == 2 && ...
    max(relative_differences) <= 1e-12 && selector_rel <= 1e-12 && ...
    max(right_closure) <= 1e-12 && max(left_closure) <= 1e-12;

audit = struct();
audit.identity = '历史单边Guyan的Petrov审计证据；不属于R01-R04主路线';
audit.W_formula = 'W=P''*[I;0]';
audit.W_natural = W;
audit.R_natural = R;
audit.S_R_formula = 'S_R=J*E''*R';
audit.S_L_formula = 'S_L=J*E''*W';
audit.S_R = S_R;
audit.S_L = S_L;
audit.reconstructed_historical = reconstructed;
audit.delay_factors_from_local_full = delay_factors;
audit.rank_W = rank(W);
audit.rank_S_L = rank(S_L);
audit.rank_S_R = rank(S_R);
audit.S_L_second_channel_norm = left_second_norm;
audit.S_R_second_channel_norm = right_second_norm;
audit.second_channel_interpretation = second_channel_interpretation;
audit.relative_difference_M = relative_differences(1);
audit.relative_difference_C = relative_differences(2);
audit.relative_difference_K = relative_differences(3);
audit.historical_matrix_max_relative_difference = max(relative_differences);
audit.S_R_primary_selector_relative_difference = selector_rel;
audit.right_factor_identity_closure_relative_difference = right_closure;
audit.left_factor_identity_closure_relative_difference = left_closure;
audit.right_factor_identity_closure_max_relative_difference = max(right_closure);
audit.left_factor_identity_closure_max_relative_difference = max(left_closure);
audit.excluded_candidate_ids = {'R05','R06'};
audit.executable_control_candidate_generated = false;
audit.executable_control_candidate_status = ['MATLAB不生成控制候选；' ...
    'Python另存R05/R06的BLOCKED诊断包，禁止进入论文网格'];
audit.primary_R01_R04_numerics_unchanged = true;
audit.status = pass_text(pass);
end

function local = build_local_two_channel(full_model)
master = [1 4];
slave = setdiff(1:size(full_model.M,1), master, 'stable');
order = [master slave];
n_master = 2;
ordered = matrix_set(full_model.M(order,order), full_model.C(order,order), full_model.K(order,order));
Ksm = ordered.K(n_master+1:end,1:n_master);
Kss = ordered.K(n_master+1:end,n_master+1:end);
static_relation = -(Kss \ Ksm);
T = [eye(2); static_relation];
historical = matrix_set( ...
    ordered.M(1:2,1:2) + ordered.M(1:2,3:end)*static_relation, ...
    ordered.C(1:2,1:2) + ordered.C(1:2,3:end)*static_relation, ...
    ordered.K(1:2,1:2) + ordered.K(1:2,3:end)*static_relation);
standard = matrix_set(T'*ordered.M*T, T'*ordered.C*T, T'*ordered.K*T);
local = struct('historical', historical, 'standard', standard, 'T', T, ...
    'order', order, 'static_relation', static_relation, ...
    'static_residual', norm(Kss*static_relation+Ksm,'fro')/max(norm(Ksm,'fro'),eps));
end

function factors = full_local_delay_factors(R, S, local)
names = {'M','C','K'};
for k = 1:3
    name = names{k}; A = local.full.(name);
    factors.(name).left_column = S';
    factors.(name).left_row = local.J*A*local.E'*R;
    factors.(name).right_column = R'*local.E*A*local.J';
    factors.(name).right_row = S;
end
factors.left_formula = 'S'' D J A_local E'' R';
factors.right_formula = 'R'' E A_local J'' D S';
end

function factors = petrov_full_local_delay_factors(W, R, S_L, S_R, E, J, local_full)
% H保留为2x2中间算子；保存H左右两侧因子，不把历史审计路线混入主路线。
names = {'M','C','K'};
for k = 1:3
    name = names{k}; A = local_full.(name);
    factors.(name).right_before_H = W'*E*A*J';
    factors.(name).right_after_H = S_R;
    factors.(name).left_before_H = S_L';
    factors.(name).left_after_H = J*A*E'*R;
end
factors.right_formula = 'W'' E A_local J'' H S_R';
factors.left_formula = 'S_L'' H J A_local E'' R';
factors.H_dimension = [2 2];
end

function factors = two_channel_delay_factors(S, two)
names = {'M','C','K'};
for k = 1:3
    name = names{k}; A = two.(name);
    factors.(name).matrix_2x2 = A;
    factors.(name).left_column = S';
    factors.(name).left_row = A*S;
    factors.(name).right_column = S'*A;
    factors.(name).right_row = S;
    factors.(name).zero_delay_matrix = S'*A*S;
end
factors.left_formula = 'S'' D A_2 S';
factors.right_formula = 'S'' A_2 D S';
end

function max_rel = compare_route_contract(contract, div, method, selected, historical, standard, R, S)
d = div.division;
rels = [];
switch method
    case 'Original'
        variant = 'source_full15'; key = 'Original'; sets = {selected}; variants = {variant};
    case 'Guyan'
        key = 'Guyan'; sets = {historical,standard};
        variants = {'source_historical_single_sided','source_standard_congruence'};
    case 'Craig-Bampton'
        key = 'Craig_Bampton'; sets = {selected}; variants = {'source_sorted_three_modes'};
end
for v = 1:numel(sets)
    names = {'M','C','K'};
    for k = 1:3
        field = sprintf('div%d_%s_%s_%s', d, key, variants{v}, names{k});
        rels(end+1) = relative_difference(sets{v}.(names{k}), contract.(field)); %#ok<AGROW>
    end
end
fieldR = sprintf('div%d_%s_recovery_natural', d, key);
fieldS = sprintf('div%d_%s_delay_selector_psi1_psi6', d, key);
rels(end+1) = relative_difference(R, contract.(fieldR));
rels(end+1) = relative_difference(S, contract.(fieldS));
max_rel = max(rels);
end

function max_rel = compare_local_contract(contract, d, full_model, E, J, local_two, source)
rels = [];
names = {'M','C','K'};
for k = 1:3
    name = names{k};
    rels(end+1) = relative_difference(full_model.(name), ...
        contract.(sprintf('div%d_local_full_%s',d,name))); %#ok<AGROW>
    rels(end+1) = relative_difference(local_two.historical.(name), ...
        contract.(sprintf('div%d_local_psi1_psi6_historical_%s',d,name))); %#ok<AGROW>
    rels(end+1) = relative_difference(local_two.standard.(name), ...
        contract.(sprintf('div%d_local_psi1_psi6_projected_%s',d,name))); %#ok<AGROW>
end
rels(end+1) = relative_difference(E, contract.(sprintf('div%d_local_embedding_E',d)));
rels(end+1) = relative_difference(J, contract.(sprintf('div%d_local_delay_selection_J_psi1_psi6',d)));
rels(end+1) = relative_difference(source.alpha, contract.(sprintf('div%d_source_alpha_newmark',d)));
rels(end+1) = relative_difference(source.delta, contract.(sprintf('div%d_source_delta_newmark',d)));
rels(end+1) = relative_difference(source.dt, contract.(sprintf('div%d_source_dt',d)));
max_rel = max(rels);
end

function s = matrix_set(M,C,K)
s = struct('M',M,'C',C,'K',K);
end

function values = min_eigenvalues(s)
names = {'M','C','K'}; values = zeros(1,3);
for k = 1:3
    A = s.(names{k}); values(k) = min(real(eig((A+A')/2)));
end
end

function values = relative_asymmetries(s)
names = {'M','C','K'}; values = zeros(1,3);
for k = 1:3
    A = s.(names{k}); values(k) = norm(A-A','fro')/max(norm(A,'fro'),eps);
end
end

function value = relative_difference(a,b)
value = norm(double(a)-double(b),'fro')/max(norm(double(b),'fro'),eps);
end

function text = shape_text(A)
text = sprintf('%dx%d',size(A,1),size(A,2));
end

function text = pass_text(value)
if value, text = 'PASS'; else, text = 'FAIL'; end
end

function name = route_output_name(route)
switch route.method
    case 'Original'
        name = sprintf('%s_Original_%d维.mat', route.figure_label, route.dimension);
    case 'Guyan'
        name = sprintf('%s_Guyan_%d维_含历史与标准.mat', route.figure_label, route.dimension);
    otherwise
        name = sprintf('%s_Craig-Bampton_%d维_排序3模态.mat', route.figure_label, route.dimension);
end
end

function must_exist(path_value)
if ~isfile(path_value), error('缺少冻结输入：%s', path_value); end
end

function write_summary(path_value, routes, divisions, input_paths)
fid = fopen(path_value, 'w', 'n', 'UTF-8');
if fid < 0, error('不能写入摘要：%s', path_value); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '# 步骤8C：图4-4与图4-5六链模型生成摘要\n\n');
fprintf(fid, '状态：`PASS_六链模型已生成`。六条路线均通过维数、恢复矩阵秩、M/C/K正定、静力约束、固定界面模态及步骤8B逐矩阵比对。\n\n');
fprintf(fid, '## 冻结输入\n\n');
fprintf(fid, '- 图4-4：`%s`。\n', input_paths.div1);
fprintf(fid, '- 图4-5：`%s`。\n', input_paths.div2);
fprintf(fid, '- 步骤8B合同：`%s`。\n', input_paths.contract);
fprintf(fid, '- 没有读取论文PDF、历史稳定域掩膜或论文曲线坐标。\n\n');
fprintf(fid, '## 模型合同\n\n');
fprintf(fid, '- 图4-4采用第一类主自由度 `[1,6,11,4,9,14]`，输出Original 15维、Guyan 6维、Craig--Bampton 9维。\n');
fprintf(fid, '- 图4-5采用第二类主自由度 `[1,11,4,9,14]`，输出Original 15维、Guyan 5维、Craig--Bampton 8维；物理ψ6经自然坐标恢复后为稠密选择行。\n');
fprintf(fid, '- Guyan同时保存作者历史单边矩阵 `A_mm+A_ms*Psi_s` 与标准合同投影矩阵 `T''*A*T`；路线主矩阵采用标准合同投影。\n');
fprintf(fid, '- 历史单边Guyan另存Petrov证据：`W=P''*[I;0]`、`S_R=J*E''*R`、`S_L=J*E''*W`，并逐项验证 `W''*A*R` 与历史单边M/C/K一致。\n');
fprintf(fid, '- Petrov右乘时延因子为 `W''*E*A_local*J''*H*S_R`，左乘时延因子为 `S_L''*H*J*A_local*E''*R`；这些因子只服务历史路线审计。\n');
fprintf(fid, ['- MATLAB仅生成六条底模与Petrov审计，不生成控制候选；' ...
    'Python另存R05/R06的 `BLOCKED` 诊断包，禁止进入论文网格；R01-R04仍使用标准合同投影，主路线数值不变。\n']);
fprintf(fid, '- 图4-5中 `S_L` 第二时延通道为零，因为物理ψ6不在测试空间 `W`；该事实被记录为预期Petrov退化，不作为R01-R04主路线失败。\n');
fprintf(fid, '- Craig--Bampton固定界面特征值升序取前三模态，每列最大绝对分量固定为正。\n');
fprintf(fid, '- 每条路线保存自然坐标恢复 `R_natural`、ψ1/ψ6选择 `S_psi1_psi6`、局部完整 `E/J`、两通道历史/标准矩阵及左右乘时延低秩因子。\n');
fprintf(fid, '- `alpha=%.17g`，`delta=%.17g`，`dt=%.17g s`。这些值来自冻结工作区，身份为来源补全，不倒写为论文自包含参数。\n\n', divisions(1).alpha, divisions(1).delta, divisions(1).dt);
fprintf(fid, '## 数值门禁\n\n');
fprintf(fid, '| 路线 | 维数 | rank(R) | M/C/K最小特征值 | 静力残差 | 固定界面最大残差 | 合同最大相对差 |\n');
fprintf(fid, '|---|---:|---:|---|---:|---:|---:|\n');
for k = 1:numel(routes)
    v = routes(k).validation;
    fprintf(fid, '| %s | %d | %d | %.8g / %.8g / %.8g | %.3e | %.3e | %.3e |\n', ...
        routes(k).route_id, routes(k).dimension, v.rank_R, v.min_eigenvalue_M, ...
        v.min_eigenvalue_C, v.min_eigenvalue_K, v.static_residual, ...
        v.fixed_interface_max_residual, v.contract_max_relative_difference);
end
fprintf(fid, '\n## 历史单边Guyan Petrov审计门禁\n\n');
fprintf(fid, '| 图号 | rank(W) | rank(S_L) | rank(S_R) | S_L第二通道范数 | M/C/K复算最大相对差 | S_R与主路线S相对差 | 门状态 |\n');
fprintf(fid, '|---|---:|---:|---:|---:|---:|---:|---|\n');
for d = 1:numel(divisions)
    p = divisions(d).global.guyan_petrov_audit;
    fprintf(fid, '| %s | %d | %d | %d | %.3e | %.3e | %.3e | %s |\n', ...
        divisions(d).figure_label, p.rank_W, p.rank_S_L, p.rank_S_R, ...
        p.S_L_second_channel_norm, p.historical_matrix_max_relative_difference, ...
        p.S_R_primary_selector_relative_difference, p.status);
end
fprintf(fid, '\n图4-5的 `rank(S_L)=1` 与第二通道零范数是测试空间定义导致的预期结果；Petrov门禁只要求 `W''*A*R` 历史矩阵复算、`S_R` 主路线选择器及左右时延因子闭合。\n');
fprintf(fid, '\n科学身份：这些MAT是由冻结后缀工作区按步骤8B合同重新生成的计算级模型，不是作者六份Live Script原样运行结果。\n');
end
