%% Reproduce thesis Figures 4-4 and 4-5 using the author's full boundaries.
% ASCII filename and source avoid MATLAB run() limitations on this host.

code_dir = fileparts(mfilename('fullpath'));
chapter_dir = fileparts(code_dir);
project_dir = fileparts(fileparts(chapter_dir));
new_structure_name = char([26032 32467 26500 31283 23450]);
plot_name = char([32472 22270]);
author_plot_dir = fullfile(project_dir, 'liangyustability-master', ...
    new_structure_name, plot_name);
author_plot_script = fullfile(author_plot_dir, 'huitu_2.m');

output_root_name = char([20316 32773 29616 23384 77 65 84 21407 33050 26412 22797 36305 20505 36873]);
pdf_dir_name = char([80 68 70 32467 26524]);
png_dir_name = char([80 78 71 32467 26524]);
data_dir_name = char([36718 24275 25968 25454]);
boundary_suffix = ['_' char([20316 32773 23436 25972 36718 24275])];
output_root = fullfile(chapter_dir, output_root_name);
pdf_dir = fullfile(output_root, pdf_dir_name);
png_dir = fullfile(output_root, png_dir_name);
data_dir = fullfile(output_root, data_dir_name);
if ~isfolder(pdf_dir), mkdir(pdf_dir); end
if ~isfolder(png_dir), mkdir(png_dir); end
if ~isfolder(data_dir), mkdir(data_dir); end

assert(isfile(author_plot_script), 'Author plotting script not found: %s', author_plot_script);
assert(exist('bwboundaries', 'file') == 2, 'bwboundaries is unavailable.');

old_visibility = get(groot, 'DefaultFigureVisible');
visibility_cleanup = onCleanup(@() set(groot, 'DefaultFigureVisible', old_visibility)); %#ok<NASGU>
set(groot, 'DefaultFigureVisible', 'off');

figure44_stem = char([22270 52 45 52 95 31532 19968 31867 23376 32467 26500 ...
    21010 20998 31283 23450 22495 95 20316 32773 29616 23384 77 65 84 ...
    21407 33050 26412 22797 36305 20505 36873]);
figure45_stem = char([22270 52 45 53 95 31532 20108 31867 23376 32467 26500 ...
    21010 20998 31283 23450 22495 95 20316 32773 29616 23384 77 65 84 ...
    21407 33050 26412 22797 36305 20505 36873]);
tasks = {
    2, '4-4', figure44_stem;
    3, '4-5', figure45_stem
};
method_fields = {'Original', 'Craig_Bampton', 'Guyan'};
method_labels = {'Original', 'Craig-Bampton', 'Guyan'};

for task_idx = 1:size(tasks, 1)
    data_id = tasks{task_idx, 1};
    fig_no = tasks{task_idx, 2};
    output_stem = tasks{task_idx, 3};
    source_mat = fullfile(author_plot_dir, sprintf('lqr_%d.mat', data_id));
    assert(isfile(source_mat), 'Historical MAT not found: %s', source_mat);

    historical_data = load(source_mat, 'stab_o', 'stab_C', 'stab_g');
    stab_o = historical_data.stab_o; %#ok<NASGU>
    stab_C = historical_data.stab_C; %#ok<NASGU>
    stab_g = historical_data.stab_g; %#ok<NASGU>

    close all force;
    run(author_plot_script);
    assert(exist('plot_handles', 'var') == 1 && numel(plot_handles) == 3, ...
        '%s did not create three author boundary curves.', fig_no);
    drawnow;

    fig_handle = gcf;
    pdf_file = fullfile(pdf_dir, [output_stem '.pdf']);
    png_file = fullfile(png_dir, [output_stem '.png']);
    exportgraphics(fig_handle, pdf_file, 'ContentType', 'vector', 'BackgroundColor', 'white');
    exportgraphics(fig_handle, png_file, 'Resolution', 600, 'BackgroundColor', 'white');

    author_boundary = struct();
    method_col = strings(0, 1);
    sequence_col = zeros(0, 1);
    x_index_col = zeros(0, 1);
    y_index_col = zeros(0, 1);
    for method_idx = 1:3
        x = double(get(plot_handles(method_idx), 'XData'));
        y = double(get(plot_handles(method_idx), 'YData'));
        x = x(:);
        y = y(:);
        assert(numel(x) == numel(y) && ~isempty(x), ...
            '%s/%s boundary is empty.', fig_no, method_labels{method_idx});
        author_boundary.(method_fields{method_idx}) = [x, y];

        point_count = numel(x);
        method_col = [method_col; repmat(string(method_labels{method_idx}), point_count, 1)]; %#ok<AGROW>
        sequence_col = [sequence_col; (1:point_count)']; %#ok<AGROW>
        x_index_col = [x_index_col; x]; %#ok<AGROW>
        y_index_col = [y_index_col; y]; %#ok<AGROW>
    end

    source_file = source_mat; %#ok<NASGU>
    author_script = author_plot_script; %#ok<NASGU>
    save(fullfile(data_dir, [output_stem boundary_suffix '.mat']), ...
        'author_boundary', 'source_file', 'author_script', 'fig_no');
    boundary_table = table(method_col, sequence_col, x_index_col, y_index_col, ...
        'VariableNames', {'method', 'boundary_sequence', 'tau1_raw_index', 'tau2_raw_index'});
    writetable(boundary_table, fullfile(data_dir, [output_stem boundary_suffix '.csv']), ...
        'Encoding', 'UTF-8');

    close(fig_handle);
    fprintf('%s generated:\n  %s\n  %s\n', fig_no, pdf_file, png_file);
end
