function run_board18_original_attempt()
%RUN_BOARD18_ORIGINAL_ATTEMPT 以作者保存状态审计并尝试运行两份原始 SLX。
%
% 严格边界：
%   1. 只从本板块 input/author_source 读取冻结副本；
%   2. 每个模型前清空 base workspace，只运行 PDmonicanshu.m；
%   3. 不改 FromFile 路径，不补线，不旁路输入，不调用 save_system；
%   4. 分别尝试 SimulationCommand=update 和无参数、按保存状态 sim；
%   5. 任何失败都转为结构化证据，并继续下一份模型；
%   6. 模型前后 SHA-256 必须一致。

board_dir = fileparts(fileparts(mfilename('fullpath')));
input_dir = fullfile(board_dir, 'input', 'author_source');
output_dir = fullfile(board_dir, 'outputs', 'original_attempt');
log_dir = fullfile(board_dir, 'logs');

assert(isfolder(input_dir), ...
    'BOARD18:InputFreezeMissing', ...
    '冻结输入尚不存在，不得运行原模型尝试：%s', input_dir);

parameter_file = find_one_frozen_file(input_dir, 'PDmonicanshu.m');
model_files = {
    find_one_frozen_file(input_dir, 'lvxvjie_guyan_2.slx'), ...
    find_one_frozen_file(input_dir, 'lvxvjie_guyan.slx')};
model_labels = {'第一类原始模型', '第二类原始模型'};

if ~isfolder(output_dir), mkdir(output_dir); end
if ~isfolder(log_dir), mkdir(log_dir); end
log_file = fullfile(log_dir, 'run_board18_original_attempt.log');
if isfile(log_file), delete(log_file); end
diary(log_file);
cleanup = onCleanup(@() cleanup_session()); %#ok<NASGU>

fprintf('板块18原始 SLX 保存状态尝试开始\n');
fprintf('MATLAB=%s\n', version);
fprintf('input_dir=%s\n', input_dir);
fprintf('约束：不改路径/不补线/不旁路/不保存模型\n');

summary_rows = empty_summary_rows();
parameter_rows = empty_parameter_rows();
callback_rows = empty_callback_rows();
fromfile_rows = empty_fromfile_rows();
source_rows = empty_source_rows();
solver_rows = empty_solver_rows();
toworkspace_rows = empty_toworkspace_rows();
mux_rows = empty_mux_rows();
simout_rows = empty_simout_rows();

for model_index = 1:numel(model_files)
    model_file = model_files{model_index};
    model_label = string(model_labels{model_index});
    [~, model_name] = fileparts(model_file);
    hash_before = file_sha256(model_file);

    fprintf('\n=== %s | %s ===\n', model_label, model_file);
    close_loaded_models_without_saving();
    evalin('base', 'clearvars; close all force; clc;');

    parameter_status = "ERROR";
    parameter_error_id = "";
    parameter_error_message = "";
    mr_size = ""; cr_size = ""; kr_size = "";
    try
        evalin('base', sprintf('run(''%s'');', escape_matlab_string(parameter_file)));
        parameter_status = "SUCCESS";
        mr_size = base_variable_size('MRrt');
        cr_size = base_variable_size('CRrt');
        kr_size = base_variable_size('KRrt');
    catch ME
        parameter_error_id = string(ME.identifier);
        parameter_error_message = single_line_message(ME.message);
    end
    parameter_rows(end+1) = struct( ... %#ok<AGROW>
        'model_label', model_label, ...
        'model_file', string(model_file), ...
        'parameter_file', string(parameter_file), ...
        'status', parameter_status, ...
        'MRrt_size', mr_size, 'CRrt_size', cr_size, 'KRrt_size', kr_size, ...
        'error_identifier', parameter_error_id, ...
        'error_message', parameter_error_message);

    load_status = "ERROR";
    update_status = "NOT_ATTEMPTED";
    simulation_status = "NOT_ATTEMPTED";
    load_error_id = ""; load_error_message = "";
    update_error_id = ""; update_error_message = "";
    simulation_error_id = ""; simulation_error_message = "";
    close_status = "NOT_LOADED";
    close_error_id = ""; close_error_message = "";
    dirty_after_load = "NOT_AVAILABLE";
    dirty_after_update = "NOT_AVAILABLE";
    dirty_after_sim = "NOT_AVAILABLE";
    sim_out = [];

    try
        load_system(model_file);
        load_status = "SUCCESS";
        dirty_after_load = string(get_param(model_name, 'Dirty'));

        callback_rows = [callback_rows, collect_callbacks(model_name, model_label)]; %#ok<AGROW>
        fromfile_rows = [fromfile_rows, collect_fromfile_paths(model_name, model_label)]; %#ok<AGROW>
        source_rows = [source_rows, collect_root_source_connections(model_name, model_label)]; %#ok<AGROW>
        solver_rows = [solver_rows, collect_solver_settings(model_name, model_label)]; %#ok<AGROW>
        toworkspace_rows = [toworkspace_rows, collect_to_workspace(model_name, model_label)]; %#ok<AGROW>
        mux_rows = [mux_rows, collect_mux6_inputs(model_name, model_label)]; %#ok<AGROW>

        try
            set_param(model_name, 'SimulationCommand', 'update');
            update_status = "SUCCESS";
        catch ME
            update_status = "ERROR";
            update_error_id = string(ME.identifier);
            update_error_message = exception_tree_message(ME);
        end
        dirty_after_update = string(get_param(model_name, 'Dirty'));

        try
            sim_out = sim(model_name);
            simulation_status = "SUCCESS";
        catch ME
            simulation_status = "ERROR";
            simulation_error_id = string(ME.identifier);
            simulation_error_message = exception_tree_message(ME);
        end
        dirty_after_sim = string(get_param(model_name, 'Dirty'));
    catch ME
        load_error_id = string(ME.identifier);
        load_error_message = exception_tree_message(ME);
        update_status = "SKIPPED_LOAD_ERROR";
        simulation_status = "SKIPPED_LOAD_ERROR";
    end

    simout_rows = [simout_rows, collect_simout_dimensions( ...
        sim_out, model_label, simulation_status, simulation_error_message)]; %#ok<AGROW>

    if bdIsLoaded(model_name)
        try
            close_system(model_name, 0);
            close_status = "SUCCESS_WITHOUT_SAVE";
        catch ME
            close_status = "ERROR";
            close_error_id = string(ME.identifier);
            close_error_message = single_line_message(ME.message);
        end
    end
    hash_after = file_sha256(model_file);
    hash_match = strcmp(hash_before, hash_after);

    summary_rows(end+1) = struct( ... %#ok<AGROW>
        'model_label', model_label, ...
        'model_file', string(model_file), ...
        'sha256_before', string(hash_before), ...
        'sha256_after', string(hash_after), ...
        'sha256_match', hash_match, ...
        'parameter_status', parameter_status, ...
        'load_status', load_status, ...
        'update_status', update_status, ...
        'simulation_status', simulation_status, ...
        'dirty_after_load', dirty_after_load, ...
        'dirty_after_update', dirty_after_update, ...
        'dirty_after_sim', dirty_after_sim, ...
        'load_error_identifier', load_error_id, ...
        'load_error_message', load_error_message, ...
        'update_error_identifier', update_error_id, ...
        'update_error_message', update_error_message, ...
        'simulation_error_identifier', simulation_error_id, ...
        'simulation_error_message', simulation_error_message, ...
        'close_status', close_status, ...
        'close_error_identifier', close_error_id, ...
        'close_error_message', close_error_message);

    fprintf('parameter=%s load=%s update=%s sim=%s hash_match=%d\n', ...
        parameter_status, load_status, update_status, simulation_status, hash_match);
end

write_struct_csv(parameter_rows, fullfile(output_dir, 'pdmonicanshu_attempts.csv'));
write_struct_csv(callback_rows, fullfile(output_dir, 'model_callbacks.csv'));
write_struct_csv(fromfile_rows, fullfile(output_dir, 'fromfile_paths.csv'));
write_struct_csv(source_rows, fullfile(output_dir, 'root_source_connections.csv'));
write_struct_csv(solver_rows, fullfile(output_dir, 'solver_settings.csv'));
write_struct_csv(toworkspace_rows, fullfile(output_dir, 'to_workspace_variables.csv'));
write_struct_csv(mux_rows, fullfile(output_dir, 'division2_mux6_inputs.csv'));
write_struct_csv(simout_rows, fullfile(output_dir, 'simout_dimensions.csv'));
write_struct_csv(summary_rows, fullfile(output_dir, 'model_attempt_summary.csv'));

json_summary = struct();
json_summary.schema = 'board18-original-saved-state-attempt-v1';
json_summary.scope = ['Frozen author SLX saved-state inspection/update/sim attempt; ' ...
    'no path edits, no line repair, no input bypass, no save_system.'];
json_summary.parameter_file = parameter_file;
json_summary.models = summary_rows;
json_summary.parameter_attempts = parameter_rows;
json_summary.callbacks = callback_rows;
json_summary.fromfile_paths = fromfile_rows;
json_summary.root_source_connections = source_rows;
json_summary.solver_settings = solver_rows;
json_summary.to_workspace_variables = toworkspace_rows;
json_summary.division2_mux6_inputs = mux_rows;
json_summary.simout_dimensions = simout_rows;
json_summary.all_model_hashes_match = all([summary_rows.sha256_match]);
json_summary.output_directory = output_dir;
write_json(json_summary, fullfile(output_dir, 'original_attempt_summary.json'));

assert(all([summary_rows.sha256_match]), ...
    'BOARD18:SourceHashChanged', '至少一份原始 SLX 的前后 SHA-256 不一致。');
fprintf('\nBOARD18_ORIGINAL_ATTEMPT_COMPLETE\n');
fprintf('models=%d all_hashes_match=1\n', numel(summary_rows));
fprintf('outputs=%s\n', output_dir);
end


function path = find_one_frozen_file(root_dir, file_name)
matches = dir(fullfile(root_dir, '**', file_name));
matches = matches(~[matches.isdir]);
assert(numel(matches) == 1, ...
    'BOARD18:FrozenFileCount', ...
    '冻结输入中 %s 必须恰好有1份，实际%d份。', file_name, numel(matches));
path = fullfile(matches(1).folder, matches(1).name);
end


function escaped = escape_matlab_string(value)
escaped = strrep(value, '''', '''''');
end


function value = base_variable_size(name)
if evalin('base', sprintf('exist(''%s'',''var'')', name)) ~= 1
    value = "MISSING";
    return;
end
dims = evalin('base', sprintf('size(%s)', name));
value = join(string(dims), "x");
end


function rows = collect_callbacks(model_name, model_label)
callbacks = {'PreLoadFcn','PostLoadFcn','InitFcn','StartFcn','PauseFcn', ...
    'ContinueFcn','StopFcn','PreSaveFcn','PostSaveFcn','CloseFcn'};
rows = empty_callback_rows();
for k = 1:numel(callbacks)
    value = string(get_param(model_name, callbacks{k}));
    if strlength(strtrim(value)) == 0
        state = "EMPTY";
    else
        state = "NONEMPTY";
    end
    rows(end+1) = struct( ... %#ok<AGROW>
        'model_label', model_label, ...
        'callback', string(callbacks{k}), ...
        'state', state, ...
        'value', value);
end
end


function rows = collect_fromfile_paths(model_name, model_label)
blocks = find_system(model_name, 'LookUnderMasks', 'all', ...
    'FollowLinks', 'on', 'BlockType', 'FromFile');
rows = empty_fromfile_rows();
for k = 1:numel(blocks)
    file_name = string(get_param(blocks{k}, 'FileName'));
    [absolute_path, absolute_path_basis] = audit_absolute_path( ...
        file_name, get_param(model_name, 'FileName'));
    rows(end+1) = struct( ... %#ok<AGROW>
        'model_label', model_label, ...
        'block', string(blocks{k}), ...
        'file_name_saved', file_name, ...
        'is_absolute_path', is_absolute_path(file_name), ...
        'absolute_path', absolute_path, ...
        'absolute_path_basis', absolute_path_basis, ...
        'path_exists_as_saved', isfile(char(file_name)), ...
        'path_exists_absolute', isfile(char(absolute_path)));
end
end


function [absolute_path, basis] = audit_absolute_path(file_name, model_file)
if is_absolute_path(file_name)
    absolute_path = file_name;
    basis = "SAVED_ABSOLUTE";
else
    absolute_path = string(fullfile(fileparts(model_file), char(file_name)));
    basis = "MODEL_DIRECTORY_CANDIDATE_FOR_RELATIVE_SAVED_PATH";
end
end


function tf = is_absolute_path(value)
text = char(value);
tf = ~isempty(regexp(text, '^[A-Za-z]:[\\/]', 'once')) || ...
    startsWith(text, '\\') || startsWith(text, '//');
end


function rows = collect_root_source_connections(model_name, model_label)
blocks = find_system(model_name, 'SearchDepth', 1, 'Type', 'Block');
rows = empty_source_rows();
for k = 1:numel(blocks)
    ports = get_param(blocks{k}, 'PortHandles');
    if ~isempty(ports.Inport) || isempty(ports.Outport)
        continue;
    end
    block_type = string(get_param(blocks{k}, 'BlockType'));
    for port_index = 1:numel(ports.Outport)
        line_handle = get_param(ports.Outport(port_index), 'Line');
        if line_handle == -1
            rows(end+1) = make_source_row(model_label, blocks{k}, block_type, ...
                port_index, "", "", NaN, "UNCONNECTED"); %#ok<AGROW>
            continue;
        end
        dst_blocks = get_param(line_handle, 'DstBlockHandle');
        dst_ports = get_param(line_handle, 'DstPortHandle');
        dst_blocks = dst_blocks(:); dst_ports = dst_ports(:);
        if isempty(dst_blocks) || all(dst_blocks == -1)
            rows(end+1) = make_source_row(model_label, blocks{k}, block_type, ...
                port_index, "", "", NaN, "UNCONNECTED"); %#ok<AGROW>
            continue;
        end
        for j = 1:numel(dst_blocks)
            if dst_blocks(j) == -1, continue; end
            destination = string(getfullname(dst_blocks(j)));
            destination_type = string(get_param(dst_blocks(j), 'BlockType'));
            destination_port = NaN;
            if j <= numel(dst_ports) && dst_ports(j) ~= -1
                destination_port = double(get_param(dst_ports(j), 'PortNumber'));
            end
            rows(end+1) = make_source_row(model_label, blocks{k}, block_type, ...
                port_index, destination, destination_type, destination_port, "CONNECTED"); %#ok<AGROW>
        end
    end
end
end


function row = make_source_row(model_label, source, source_type, source_port, ...
        destination, destination_type, destination_port, status)
row = struct( ...
    'model_label', model_label, ...
    'source_block', string(source), ...
    'source_block_type', string(source_type), ...
    'source_port', double(source_port), ...
    'destination_block', string(destination), ...
    'destination_block_type', string(destination_type), ...
    'destination_port', double(destination_port), ...
    'connection_status', string(status));
end


function rows = collect_solver_settings(model_name, model_label)
rows = empty_solver_rows();
rows(end+1) = struct( ...
    'model_label', model_label, ...
    'start_time', string(get_param(model_name, 'StartTime')), ...
    'stop_time', string(get_param(model_name, 'StopTime')), ...
    'solver_type', string(get_param(model_name, 'SolverType')), ...
    'solver', string(get_param(model_name, 'Solver')), ...
    'fixed_step', string(get_param(model_name, 'FixedStep')));
end


function rows = collect_to_workspace(model_name, model_label)
blocks = find_system(model_name, 'LookUnderMasks', 'all', ...
    'FollowLinks', 'on', 'BlockType', 'ToWorkspace');
rows = empty_toworkspace_rows();
for k = 1:numel(blocks)
    ports = get_param(blocks{k}, 'PortHandles');
    [source_block, source_port, status] = input_source(ports.Inport(1));
    rows(end+1) = struct( ... %#ok<AGROW>
        'model_label', model_label, ...
        'block', string(blocks{k}), ...
        'variable_name', string(get_param(blocks{k}, 'VariableName')), ...
        'save_format', string(get_param(blocks{k}, 'SaveFormat')), ...
        'sample_time', string(get_param(blocks{k}, 'SampleTime')), ...
        'source_block', source_block, ...
        'source_port', source_port, ...
        'connection_status', status);
end
end


function rows = collect_mux6_inputs(model_name, model_label)
rows = empty_mux_rows();
if model_label ~= "第二类原始模型"
    return;
end
mux_path = [model_name '/Mux6'];
if getSimulinkBlockHandle(mux_path) < 0
    rows(end+1) = struct( ...
        'model_label', model_label, 'mux_block', string(mux_path), ...
        'input_port', NaN, 'source_block', "", 'source_port', NaN, ...
        'connection_status', "MUX6_NOT_FOUND");
    return;
end
ports = get_param(mux_path, 'PortHandles');
for k = 1:numel(ports.Inport)
    [source_block, source_port, status] = input_source(ports.Inport(k));
    rows(end+1) = struct( ... %#ok<AGROW>
        'model_label', model_label, 'mux_block', string(mux_path), ...
        'input_port', double(k), 'source_block', source_block, ...
        'source_port', source_port, 'connection_status', status);
end
end


function [source_block, source_port, status] = input_source(port_handle)
line_handle = get_param(port_handle, 'Line');
if line_handle == -1
    source_block = ""; source_port = NaN; status = "UNCONNECTED";
    return;
end
block_handle = get_param(line_handle, 'SrcBlockHandle');
src_port_handle = get_param(line_handle, 'SrcPortHandle');
if block_handle == -1
    source_block = ""; source_port = NaN; status = "UNCONNECTED";
    return;
end
source_block = string(getfullname(block_handle));
source_port = double(get_param(src_port_handle, 'PortNumber'));
status = "CONNECTED";
end


function rows = collect_simout_dimensions(sim_out, model_label, sim_status, sim_error)
variables = {'simout3','simout','simout1'};
floors = {'一层','二层','三层'};
rows = empty_simout_rows();
for k = 1:numel(variables)
    present = false; value_class = ""; time_size = ""; data_size = "";
    capture_source = ""; status = "NOT_AVAILABLE"; note = sim_error;
    if sim_status == "SUCCESS"
        [present, value, capture_source, read_note] = ...
            read_saved_state_output(sim_out, variables{k});
        if present
            value_class = string(class(value));
            if isa(value, 'timeseries')
                time_size = size_text(value.Time);
                data_size = size_text(value.Data);
            elseif isstruct(value) && isfield(value, 'time') && ...
                    isfield(value, 'signals') && isfield(value.signals, 'values')
                time_size = size_text(value.time);
                data_size = size_text(value.signals.values);
            else
                data_size = size_text(value);
            end
            status = "CAPTURED";
            note = "";
        else
            status = "MISSING_OR_UNREADABLE";
            note = read_note;
        end
    end
    rows(end+1) = struct( ... %#ok<AGROW>
        'model_label', model_label, ...
        'variable_name', string(variables{k}), ...
        'expected_floor', string(floors{k}), ...
        'present', present, ...
        'value_class', value_class, ...
        'time_size', time_size, ...
        'data_size', data_size, ...
        'capture_source', capture_source, ...
        'status', status, ...
        'note', note);
end
end


function [present, value, source, note] = read_saved_state_output(sim_out, name)
present = false;
value = [];
source = "";
notes = strings(0, 1);
if isa(sim_out, 'Simulink.SimulationOutput')
    try
        value = sim_out.get(name);
        present = true;
        source = "SIMULATION_OUTPUT";
        note = "";
        return;
    catch ME
        notes(end+1) = "SimulationOutput: " + single_line_message(ME.message); %#ok<AGROW>
    end
end
try
    if evalin('base', sprintf('exist(''%s'',''var'')', name)) == 1
        value = evalin('base', name);
        present = true;
        source = "BASE_WORKSPACE";
        note = "";
        return;
    end
catch ME
    notes(end+1) = "base workspace: " + single_line_message(ME.message); %#ok<AGROW>
end
if isempty(notes)
    note = "变量未出现在保存状态产生的 SimulationOutput 或 base workspace 中。";
else
    note = join(notes, " | ");
end
end


function text = size_text(value)
text = join(string(size(value)), "x");
end


function write_struct_csv(rows, path)
writetable(struct2table(rows), path, 'Encoding', 'UTF-8');
end


function write_json(value, path)
text = jsonencode(value, 'PrettyPrint', true);
fid = fopen(path, 'w', 'n', 'UTF-8');
assert(fid ~= -1, 'BOARD18:JsonOpenFailed', '无法写入 JSON：%s', path);
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s\n', text);
end


function text = single_line_message(value)
text = string(value);
text = replace(text, [newline, char(13)], " | ");
text = regexprep(text, '\s+', ' ');
end


function text = exception_tree_message(root_exception)
queue = {root_exception};
parts = strings(0, 1);
while ~isempty(queue)
    current = queue{1};
    queue(1) = [];
    identifier = string(current.identifier);
    if strlength(identifier) == 0, identifier = "NO_IDENTIFIER"; end
    parts(end+1, 1) = identifier + ": " + single_line_message(current.message); %#ok<AGROW>
    causes = current.cause;
    for cause_index = 1:numel(causes)
        queue{end+1} = causes{cause_index}; %#ok<AGROW>
    end
end
text = strjoin(parts, " || ");
end


function hash_value = file_sha256(path)
fid = fopen(path, 'rb');
assert(fid ~= -1, 'BOARD18:HashOpenFailed', '无法打开待哈希文件：%s', path);
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
digest = java.security.MessageDigest.getInstance('SHA-256');
while ~feof(fid)
    block = fread(fid, 1024 * 1024, '*uint8');
    if ~isempty(block), digest.update(block); end
end
bytes = typecast(digest.digest(), 'uint8');
hash_value = upper(reshape(dec2hex(bytes, 2).', 1, []));
end


function close_loaded_models_without_saving()
loaded = find_system('Type', 'block_diagram');
for k = 1:numel(loaded)
    try
        close_system(loaded{k}, 0);
    catch
    end
end
end


function cleanup_session()
close_loaded_models_without_saving();
try
    evalin('base', 'clearvars; close all force;');
catch
end
try
    diary('off');
catch
end
end


function rows = empty_summary_rows()
rows = struct('model_label', {}, 'model_file', {}, 'sha256_before', {}, ...
    'sha256_after', {}, 'sha256_match', {}, 'parameter_status', {}, ...
    'load_status', {}, 'update_status', {}, 'simulation_status', {}, ...
    'dirty_after_load', {}, 'dirty_after_update', {}, 'dirty_after_sim', {}, ...
    'load_error_identifier', {}, 'load_error_message', {}, ...
    'update_error_identifier', {}, 'update_error_message', {}, ...
    'simulation_error_identifier', {}, 'simulation_error_message', {}, ...
    'close_status', {}, 'close_error_identifier', {}, 'close_error_message', {});
end


function rows = empty_parameter_rows()
rows = struct('model_label', {}, 'model_file', {}, 'parameter_file', {}, ...
    'status', {}, 'MRrt_size', {}, 'CRrt_size', {}, 'KRrt_size', {}, ...
    'error_identifier', {}, 'error_message', {});
end


function rows = empty_callback_rows()
rows = struct('model_label', {}, 'callback', {}, 'state', {}, 'value', {});
end


function rows = empty_fromfile_rows()
rows = struct('model_label', {}, 'block', {}, 'file_name_saved', {}, ...
    'is_absolute_path', {}, 'absolute_path', {}, 'absolute_path_basis', {}, ...
    'path_exists_as_saved', {}, 'path_exists_absolute', {});
end


function rows = empty_source_rows()
rows = struct('model_label', {}, 'source_block', {}, 'source_block_type', {}, ...
    'source_port', {}, 'destination_block', {}, 'destination_block_type', {}, ...
    'destination_port', {}, 'connection_status', {});
end


function rows = empty_solver_rows()
rows = struct('model_label', {}, 'start_time', {}, 'stop_time', {}, ...
    'solver_type', {}, 'solver', {}, 'fixed_step', {});
end


function rows = empty_toworkspace_rows()
rows = struct('model_label', {}, 'block', {}, 'variable_name', {}, ...
    'save_format', {}, 'sample_time', {}, 'source_block', {}, ...
    'source_port', {}, 'connection_status', {});
end


function rows = empty_mux_rows()
rows = struct('model_label', {}, 'mux_block', {}, 'input_port', {}, ...
    'source_block', {}, 'source_port', {}, 'connection_status', {});
end


function rows = empty_simout_rows()
rows = struct('model_label', {}, 'variable_name', {}, 'expected_floor', {}, ...
    'present', {}, 'value_class', {}, 'time_size', {}, 'data_size', {}, ...
    'capture_source', {}, 'status', {}, 'note', {});
end
