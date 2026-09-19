function run_reference_model()
%RUN_REFERENCE_MODEL 原样运行梁禹真实响应参数脚本并保存板块16证据。

code_dir = fileparts(mfilename('fullpath'));
base_dir = fileparts(code_dir);
input_dir = fullfile(base_dir, 'input');
output_dir = fullfile(base_dir, 'outputs');
log_dir = fullfile(base_dir, 'logs');
if ~exist(output_dir, 'dir'), mkdir(output_dir); end
if ~exist(log_dir, 'dir'), mkdir(log_dir); end

log_file = fullfile(log_dir, 'run_reference_model_matlab.log');
if exist(log_file, 'file'), delete(log_file); end
diary(log_file);
cleanup_diary = onCleanup(@() diary('off')); %#ok<NASGU>
old_visibility = get(groot, 'defaultFigureVisible');
set(groot, 'defaultFigureVisible', 'off');
cleanup_visibility = onCleanup(@() set(groot, 'defaultFigureVisible', old_visibility)); %#ok<NASGU>
addpath(input_dir);
cleanup_path = onCleanup(@() rmpath(input_dir)); %#ok<NASGU>

fprintf('板块16 MATLAB参考模型复现开始：%s\n', string(datetime('now')));
fprintf('MATLAB版本：%s\n', version);
fprintf('隔离目录：%s\n', base_dir);

parameter_script = fullfile(input_dir, 'PDmonicanshu.m');
assert(isfile(parameter_script), '缺少输入参数脚本：%s', parameter_script);
input_sha256 = sha256_file(parameter_script);
expected_input_sha256 = "CB25DFABD21175FE0CE5F93ABE722B365D25C0D4ADE9BEAF3B7EBD25328D1C4D";
assert(input_sha256 == expected_input_sha256, 'PDmonicanshu.m复制件SHA-256不一致。');

%% 1. 原样运行真实响应参数入口
run(parameter_script);
assert(isequal(size(MRrt), [15,15]) && isequal(size(CRrt), [15,15]) && isequal(size(KRrt), [15,15]), ...
    '完整模型M/C/K必须均为15x15。');

source_parameters = struct('Lb',Lb,'Lc',Lc,'Ic',Ic,'Ib',Ib,'Ac',Ac,'Ab',Ab,'E',E,'rho',rho, ...
    'mass_b',mass_b,'mass_c',mass_c,'M1',M1,'M2',M2,'M3',M3);

%% 2. 重新求解完整模型模态，避免脚本末尾物理子结构变量覆盖
[Phi, Lambda_matrix] = eig(KRrt, MRrt);
lambda = real(diag(Lambda_matrix));
[lambda, sort_index] = sort(lambda, 'ascend');
Phi = real(Phi(:,sort_index));
assert(all(lambda > 0), '完整模型存在非正广义特征值。');
omega_rad_s = sqrt(lambda);
frequency_hz = omega_rad_s/(2*pi);

for mode_index = 1:size(Phi,2)
    modal_mass = Phi(:,mode_index)'*MRrt*Phi(:,mode_index);
    Phi(:,mode_index) = Phi(:,mode_index)/sqrt(modal_mass);
end

direction_horizontal = zeros(15,1);
direction_horizontal([1,6,11]) = 1;
direction_all_ones = ones(15,1);
[gamma_horizontal, effective_ratio_horizontal] = effective_modal_mass(Phi, MRrt, direction_horizontal);
[gamma_all_ones, effective_ratio_all_ones] = effective_modal_mass(Phi, MRrt, direction_all_ones);
cumulative_horizontal = cumsum(effective_ratio_horizontal);
cumulative_all_ones = cumsum(effective_ratio_all_ones);

%% 3. 完整模型5% Rayleigh阻尼独立回算
damping_ratio = 0.05;
rayleigh_system = 0.5*[(1/omega_rad_s(1)) omega_rad_s(1); (1/omega_rad_s(2)) omega_rad_s(2)];
rayleigh_coefficients = rayleigh_system\[damping_ratio; damping_ratio];
rayleigh_alpha = rayleigh_coefficients(1);
rayleigh_beta = rayleigh_coefficients(2);
CRrt_recomputed = rayleigh_alpha*MRrt + rayleigh_beta*KRrt;
rayleigh_matrix_relative_error = norm(CRrt-CRrt_recomputed,'fro')/norm(CRrt,'fro');

%% 4. 预注册数值门槛
expected_frequency_hz = [2.707425741915; 9.328408686763; 18.4426700565; 22.6735592218; 24.2277487321];
expected_rayleigh = [1.318462500458; 0.001322342410366];
assert(max(abs(frequency_hz(1:5)-expected_frequency_hz)) < 1e-9, '前五阶频率未复现既有响应代码值。');
assert(max(abs((rayleigh_coefficients-expected_rayleigh)./expected_rayleigh)) < 1e-10, ...
    '完整模型Rayleigh系数未达到预注册容差。');
assert(rayleigh_matrix_relative_error < 1e-12, 'CRrt与重新计算的5%% Rayleigh矩阵不一致。');

matrix_names = ["MRrt";"CRrt";"KRrt"];
matrix_values = {MRrt;CRrt;KRrt};
matrix_rows = zeros(3,1); matrix_cols = zeros(3,1); matrix_rank = zeros(3,1);
symmetry_relative = zeros(3,1); minimum_eigenvalue = zeros(3,1); maximum_eigenvalue = zeros(3,1);
for matrix_index = 1:3
    current_matrix = matrix_values{matrix_index};
    matrix_rows(matrix_index) = size(current_matrix,1);
    matrix_cols(matrix_index) = size(current_matrix,2);
    matrix_rank(matrix_index) = rank(current_matrix);
    symmetry_relative(matrix_index) = norm(current_matrix-current_matrix','fro')/max(norm(current_matrix,'fro'),eps);
    eigenvalues_current = eig((current_matrix+current_matrix')/2);
    minimum_eigenvalue(matrix_index) = min(real(eigenvalues_current));
    maximum_eigenvalue(matrix_index) = max(real(eigenvalues_current));
end
assert(all(matrix_rows==15 & matrix_cols==15 & matrix_rank==15), 'M/C/K维数或秩检查失败。');
assert(all(symmetry_relative < 1e-12), 'M/C/K对称性检查失败。');
assert(all(minimum_eigenvalue > 0), 'M/C/K正定性检查失败。');

%% 5. 原样执行tes.m的全1方向路线
tes_script = fullfile(input_dir, 'tes.m');
% tes.m中的变量mu与Robust Control Toolbox的mu()同名。直接从函数工作区
% run脚本后读取mu会触发名称解析冲突，因此在隔离base workspace原样执行，
% 并在同一工作区立即保存字面脚本输出；这不修改tes.m或其公式。
tes_capture_file = fullfile(output_dir, 'tes_literal_workspace_capture.mat');
assignin('base','MRrt',MRrt);
assignin('base','KRrt',KRrt);
tes_script_escaped = strrep(tes_script,'''','''''');
tes_capture_escaped = strrep(tes_capture_file,'''','''''');
tes_command = sprintf(['set(groot,''defaultFigureVisible'',''off''); run(''%s''); ' ...
    'save(''%s'',''f'',''Gamma'',''mu'',''cumulative_mu'',''-v7''); close all force;'], ...
    tes_script_escaped,tes_capture_escaped);
evalin('base',tes_command);
tes_capture = load(tes_capture_file,'f','Gamma','mu','cumulative_mu');
tes_frequency_native_hz = tes_capture.f;
tes_gamma_native = tes_capture.Gamma;
tes_ratio_native = tes_capture.mu;
tes_cumulative_native = tes_capture.cumulative_mu;
evalin('base','clear MRrt KRrt M K r Phi Lambda omega f num_modes Gamma mu rMr cumulative_mu phi_i i;');
tes_native_is_frequency_sorted = all(diff(tes_frequency_native_hz) >= 0);

%% 6. 实际捕获energy.m的18维方向在15自由度模型上的结果
energy_script = fullfile(input_dir, 'energy.m');
energy_route_status = "UNTESTED";
energy_error_identifier = "";
energy_error_message = "";
try
    run(energy_script);
    energy_route_status = "UNEXPECTED_PASS";
catch ME
    energy_route_status = "EXPECTED_DIMENSION_FAILURE";
    energy_error_identifier = string(ME.identifier);
    energy_error_message = string(ME.message);
end
assert(energy_route_status == "EXPECTED_DIMENSION_FAILURE", ...
    'energy.m在15自由度矩阵上应因18维方向向量而失败。');
close all force;

%% 7. calc_MPF欧氏投影比，与有效模态质量分开保存
selection_horizontal = zeros(3,15);
selection_horizontal(1,1)=1; selection_horizontal(2,6)=1; selection_horizontal(3,11)=1;
mpf_euclidean_horizontal = calc_MPF(Phi, selection_horizontal);

%% 8. 论文表值与其他rho分支的最小替换敏感性
route_names = ["真实响应代码";"rho=785e3分支";"rho=7.85e3分支";"论文表值最小替换"];
route_E_pa = [E; E; E; 200e9];
route_rho_kg_m3 = [rho; 785e3; 7.85e3; 7850];
route_frequency = zeros(numel(route_names),5);
for route_index = 1:numel(route_names)
    mass_scaled = MRrt*(route_rho_kg_m3(route_index)/rho);
    stiffness_scaled = KRrt*(route_E_pa(route_index)/E);
    lambda_route = sort(real(eig(stiffness_scaled,mass_scaled)),'ascend');
    route_frequency(route_index,:) = (sqrt(lambda_route(1:5))/(2*pi))';
end

paper_frequency_hz = [2.7;9.1;18.0;22.1;23.6];
frequency_absolute_error_vs_paper = frequency_hz(1:5)-paper_frequency_hz;
frequency_relative_error_vs_paper_percent = frequency_absolute_error_vs_paper./paper_frequency_hz*100;

%% 9. 写出原始数据契约
parameter_name = ["Lb";"Lc";"Ic";"Ib";"Ac";"Ab";"E";"rho";"mass_b";"mass_c";"M1";"M2";"M3";"rayleigh_alpha";"rayleigh_beta"];
parameter_value = [Lb;Lc;Ic;Ib;Ac;Ab;E;rho;mass_b;mass_c;M1;M2;M3;rayleigh_alpha;rayleigh_beta];
parameter_unit = ["m";"m";"m^4";"m^4";"m^2";"m^2";"Pa";"kg/m^3";"kg";"kg";"kg";"kg*m^2";"kg*m^2";"1/s";"s"];
writetable(table(parameter_name,parameter_value,parameter_unit), fullfile(output_dir,'reference_parameters.csv'), 'Encoding','UTF-8');

dof_number = (1:15)';
dof_label = "psi" + string(dof_number);
floor_number = repelem((1:3)',5);
dof_type = repmat(["horizontal_translation";"node_rotation";"node_rotation";"node_rotation";"node_rotation"],3,1);
node_or_floor = strings(15,1);
for dof_index=1:15
    if dof_type(dof_index)=="horizontal_translation"
        node_or_floor(dof_index) = "floor_" + floor_number(dof_index) + "_shared_x";
    else
        node_in_floor = mod(dof_index-2,5)+1;
        node_or_floor(dof_index) = "floor_" + floor_number(dof_index) + "_column_node_" + node_in_floor;
    end
end
in_horizontal_influence = ismember(dof_number,[1;6;11]);
writetable(table(dof_number,dof_label,floor_number,dof_type,node_or_floor,in_horizontal_influence), ...
    fullfile(output_dir,'dof_map.csv'), 'Encoding','UTF-8');

mode = (1:15)';
modal_table = table(mode,frequency_hz,gamma_horizontal,effective_ratio_horizontal,cumulative_horizontal, ...
    gamma_all_ones,effective_ratio_all_ones,cumulative_all_ones,mpf_euclidean_horizontal, ...
    'VariableNames',{'mode','frequency_hz','gamma_horizontal','effective_mass_ratio_horizontal', ...
    'cumulative_effective_mass_horizontal','gamma_all_ones','effective_mass_ratio_all_ones', ...
    'cumulative_effective_mass_all_ones','euclidean_horizontal_projection_ratio'});
writetable(modal_table, fullfile(output_dir,'modal_results_matlab.csv'), 'Encoding','UTF-8');

frequency_table = table((1:5)',paper_frequency_hz,frequency_hz(1:5),frequency_absolute_error_vs_paper, ...
    frequency_relative_error_vs_paper_percent, ...
    'VariableNames',{'mode','thesis_frequency_hz','response_code_frequency_hz','absolute_difference_hz','relative_difference_percent'});
writetable(frequency_table, fullfile(output_dir,'frequency_comparison_thesis_vs_code.csv'), 'Encoding','UTF-8');

route_column = strings(numel(route_names)*5,1); route_mode = zeros(numel(route_names)*5,1);
route_E_column = zeros(numel(route_names)*5,1); route_rho_column = zeros(numel(route_names)*5,1);
route_frequency_column = zeros(numel(route_names)*5,1); cursor=0;
for route_index=1:numel(route_names)
    for mode_index=1:5
        cursor=cursor+1;
        route_column(cursor)=route_names(route_index); route_mode(cursor)=mode_index;
        route_E_column(cursor)=route_E_pa(route_index); route_rho_column(cursor)=route_rho_kg_m3(route_index);
        route_frequency_column(cursor)=route_frequency(route_index,mode_index);
    end
end
writetable(table(route_column,route_mode,route_E_column,route_rho_column,route_frequency_column, ...
    'VariableNames',{'route','mode','E_pa','rho_kg_m3','frequency_hz'}), ...
    fullfile(output_dir,'parameter_route_frequencies_matlab.csv'), 'Encoding','UTF-8');

writetable(table(matrix_names,matrix_rows,matrix_cols,matrix_rank,symmetry_relative,minimum_eigenvalue,maximum_eigenvalue), ...
    fullfile(output_dir,'matrix_diagnostics_matlab.csv'), 'Encoding','UTF-8');

tes_mode_native = (1:numel(tes_frequency_native_hz))';
writetable(table(tes_mode_native,tes_frequency_native_hz,tes_gamma_native,tes_ratio_native,tes_cumulative_native), ...
    fullfile(output_dir,'tes_literal_results_matlab.csv'), 'Encoding','UTF-8');

energy_status_table = table(energy_route_status,energy_error_identifier,energy_error_message);
writetable(energy_status_table, fullfile(output_dir,'energy_route_status.csv'), 'Encoding','UTF-8');

save(fullfile(output_dir,'reference_model_matlab.mat'), ...
    'MRrt','CRrt','KRrt','CRrt_recomputed','Phi','lambda','omega_rad_s','frequency_hz', ...
    'direction_horizontal','direction_all_ones','gamma_horizontal','effective_ratio_horizontal', ...
    'cumulative_horizontal','gamma_all_ones','effective_ratio_all_ones','cumulative_all_ones', ...
    'mpf_euclidean_horizontal','rayleigh_alpha','rayleigh_beta','rayleigh_matrix_relative_error', ...
    'source_parameters','tes_frequency_native_hz','tes_gamma_native','tes_ratio_native', ...
    'tes_cumulative_native','tes_native_is_frequency_sorted','energy_route_status','energy_error_identifier', ...
    'energy_error_message','route_names','route_E_pa','route_rho_kg_m3','route_frequency','-v7');

summary_file = fullfile(output_dir,'matlab_run_summary.txt');
fid = fopen(summary_file,'w','n','UTF-8');
assert(fid~=-1,'无法写入MATLAB摘要。');
fprintf(fid,'MATLAB_VERSION=%s\n',version);
fprintf(fid,'INPUT_SHA256=%s\n',input_sha256);
fprintf(fid,'MATRIX_DIMENSION=15x15\n');
fprintf(fid,'FREQUENCY_FIRST5_HZ=%.15g,%.15g,%.15g,%.15g,%.15g\n',frequency_hz(1:5));
fprintf(fid,'RAYLEIGH_ALPHA=%.15g\nRAYLEIGH_BETA=%.15g\n',rayleigh_alpha,rayleigh_beta);
fprintf(fid,'HORIZONTAL_CUMULATIVE_FIRST2=%.15g\n',cumulative_horizontal(2));
fprintf(fid,'HORIZONTAL_CUMULATIVE_FIRST5=%.15g\n',cumulative_horizontal(5));
fprintf(fid,'ALL_ONES_CUMULATIVE_FIRST2=%.15g\n',cumulative_all_ones(2));
fprintf(fid,'ALL_ONES_CUMULATIVE_FIRST5=%.15g\n',cumulative_all_ones(5));
fprintf(fid,'TES_NATIVE_SORTED=%d\n',tes_native_is_frequency_sorted);
fprintf(fid,'ENERGY_ROUTE_STATUS=%s\n',energy_route_status);
fclose(fid);

fprintf('前五阶频率(Hz)：%.12f %.12f %.12f %.12f %.12f\n',frequency_hz(1:5));
fprintf('水平影响向量累计有效模态质量：前2阶=%.12f，前5阶=%.12f\n',cumulative_horizontal(2),cumulative_horizontal(5));
fprintf('tes.m全1向量累计有效模态质量：前2阶=%.12f，前5阶=%.12f\n',cumulative_all_ones(2),cumulative_all_ones(5));
fprintf('energy.m在15自由度模型上的状态：%s\n',energy_route_status);
fprintf('板块16 MATLAB参考模型复现完成：%s\n',string(datetime('now')));
end


function [gamma, ratio] = effective_modal_mass(Phi, M, direction)
gamma = Phi'*M*direction;
total_directional_mass = direction'*M*direction;
ratio = (gamma.^2)/total_directional_mass;
end


function digest_text = sha256_file(file_path)
digest_engine = java.security.MessageDigest.getInstance('SHA-256');
java_file = java.io.File(file_path);
file_bytes = java.nio.file.Files.readAllBytes(java_file.toPath());
digest_engine.update(file_bytes);
digest_bytes = typecast(digest_engine.digest(),'uint8');
digest_text = string(upper(reshape(dec2hex(digest_bytes,2).',1,[])));
end
