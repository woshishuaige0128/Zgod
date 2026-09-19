function fig10_extract_mask_boundaries(task_json_path)
%FIG10_EXTRACT_MASK_BOUNDARIES 仅将候选掩膜转为固定 MATLAB 可见开边界。
%
% 合同：B = bwboundaries(M, 8, 'noholes'); 取 B{1};
%       (tau1_step,tau2_step)=(column,row); 删除 x<=1 或 y<=1。
% 本函数不读取目标、不导入求解器、不运行参数搜索。

arguments
    task_json_path (1, :) char
end

task = jsondecode(fileread(task_json_path));
assert(isfield(task, 'schema_version') && ...
    strcmp(task.schema_version, 'FIG10_MASK_EXTRACTION_TASKS_V1'), ...
    '掩膜提取任务 schema_version 错误。');
assert(isfield(task, 'curves') && ~isempty(task.curves), ...
    '掩膜提取任务为空。');

for curve_index = 1:numel(task.curves)
    item = task.curves(curve_index);
    mask_path = char(item.path);
    boundary_csv = char(item.boundary_csv);
    metadata_json = char(item.metadata_json);
    expected_rows = str2double(char(item.expected_rows));
    expected_columns = str2double(char(item.expected_columns));

    raw = readmatrix(mask_path);
    assert(ismatrix(raw) && ~isempty(raw), '%s: 掩膜为空。', item.curve_id);
    assert(isequal(size(raw), [expected_rows, expected_columns]), ...
        '%s: 掩膜尺寸为 %dx%d，预期 %dx%d。', ...
        item.curve_id, size(raw, 1), size(raw, 2), expected_rows, expected_columns);
    assert(all(isfinite(raw), 'all'), '%s: 掩膜包含非有限值。', item.curve_id);
    assert(all(raw == 0 | raw == 1, 'all'), '%s: 掩膜必须只含 0/1。', item.curve_id);
    mask = logical(raw);

    boundaries = bwboundaries(mask, 8, 'noholes');
    assert(~isempty(boundaries), '%s: bwboundaries 未返回边界。', item.curve_id);
    boundary = boundaries{1};
    tau2_step = boundary(:, 1);
    tau1_step = boundary(:, 2);
    keep = tau1_step > 1 & tau2_step > 1;
    tau1_step = tau1_step(keep);
    tau2_step = tau2_step(keep);
    assert(~isempty(tau1_step), '%s: 删除坐标轴闭合段后边界为空。', item.curve_id);

    point_order = (1:numel(tau1_step)).';
    output_table = table(point_order, tau1_step, tau2_step);
    output_parent = fileparts(boundary_csv);
    if ~isfolder(output_parent)
        mkdir(output_parent);
    end
    writetable(output_table, boundary_csv, 'Encoding', 'UTF-8');

    components = bwconncomp(mask, 8);
    holes = imfill(mask, 'holes') & ~mask;
    metadata = struct();
    metadata.schema_version = 'FIG10_MASK_BOUNDARY_METADATA_V1';
    metadata.curve_id = char(item.curve_id);
    metadata.source_path = mask_path;
    metadata.source_sha256 = char(item.source_sha256);
    metadata.mask_rows = size(mask, 1);
    metadata.mask_columns = size(mask, 2);
    metadata.stable_point_count = nnz(mask);
    metadata.component_count_8_connected = components.NumObjects;
    metadata.hole_pixel_count = nnz(holes);
    metadata.returned_boundary_count = numel(boundaries);
    metadata.selected_full_boundary_point_count = size(boundary, 1);
    metadata.selected_visible_open_boundary_point_count = numel(tau1_step);
    metadata.boundary_contract = ...
        'bwboundaries(M,8,noholes); B{1}; x=column; y=row; keep x>1 and y>1';

    metadata_parent = fileparts(metadata_json);
    if ~isfolder(metadata_parent)
        mkdir(metadata_parent);
    end
    file_id = fopen(metadata_json, 'w', 'n', 'UTF-8');
    assert(file_id >= 0, '%s: 无法写入元数据 JSON。', item.curve_id);
    cleanup_object = onCleanup(@() fclose(file_id)); %#ok<NASGU>
    fwrite(file_id, jsonencode(metadata, 'PrettyPrint', true), 'char');
    fwrite(file_id, newline, 'char');
    clear cleanup_object;
end
end
