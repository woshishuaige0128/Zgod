%% Validate the author's full-boundary reproduction for Figures 4-4 and 4-5.

code_dir = fileparts(mfilename('fullpath'));
chapter_dir = fileparts(code_dir);
project_dir = fileparts(fileparts(chapter_dir));
new_structure_name = char([26032 32467 26500 31283 23450]);
plot_name = char([32472 22270]);
author_plot_dir = fullfile(project_dir, 'liangyustability-master', ...
    new_structure_name, plot_name);
output_root_name = char([20316 32773 29616 23384 77 65 84 21407 33050 26412 22797 36305 20505 36873]);
pdf_dir_name = char([80 68 70 32467 26524]);
png_dir_name = char([80 78 71 32467 26524]);
data_dir_name = char([36718 24275 25968 25454]);
validation_dir_name = char([39564 35777 35760 24405]);
boundary_suffix = ['_' char([20316 32773 23436 25972 36718 24275])];
output_root = fullfile(chapter_dir, output_root_name);
data_dir = fullfile(output_root, data_dir_name);
validation_dir = fullfile(output_root, validation_dir_name);
if ~isfolder(validation_dir), mkdir(validation_dir); end

assert(exist('bwboundaries', 'file') == 2, 'bwboundaries is unavailable.');

figure44_stem = char([22270 52 45 52 95 31532 19968 31867 23376 32467 26500 ...
    21010 20998 31283 23450 22495 95 20316 32773 29616 23384 77 65 84 ...
    21407 33050 26412 22797 36305 20505 36873]);
figure45_stem = char([22270 52 45 53 95 31532 20108 31867 23376 32467 26500 ...
    21010 20998 31283 23450 22495 95 20316 32773 29616 23384 77 65 84 ...
    21407 33050 26412 22797 36305 20505 36873]);
tasks = {
    2, '4-4', figure44_stem, [72, 65, 62];
    3, '4-5', figure45_stem, [69, 59, 56]
};
method_fields = {'Original', 'Craig_Bampton', 'Guyan'};
source_variables = {'stab_o', 'stab_C', 'stab_g'};
method_labels = {'Original', 'Craig-Bampton', 'Guyan'};

check_names = strings(0, 1);
check_status = strings(0, 1);
check_details = strings(0, 1);

for task_idx = 1:size(tasks, 1)
    data_id = tasks{task_idx, 1};
    fig_no = tasks{task_idx, 2};
    output_stem = tasks{task_idx, 3};
    expected_counts = tasks{task_idx, 4};
    source_mat = fullfile(author_plot_dir, sprintf('lqr_%d.mat', data_id));
    boundary_mat = fullfile(data_dir, [output_stem boundary_suffix '.mat']);
    pdf_file = fullfile(output_root, pdf_dir_name, [output_stem '.pdf']);
    png_file = fullfile(output_root, png_dir_name, [output_stem '.png']);

    assert(isfile(source_mat) && isfile(boundary_mat) && isfile(pdf_file) && isfile(png_file), ...
        '%s is missing a source or output file.', fig_no);
    source_data = load(source_mat, 'stab_o', 'stab_C', 'stab_g');
    reproduced_data = load(boundary_mat, 'author_boundary');

    for method_idx = 1:3
        Ss = double(source_data.(source_variables{method_idx}));
        bw = (Ss > 0) & (Ss < 1);
        B = bwboundaries(bw, 'noholes');
        assert(numel(B) == 1, '%s/%s must have one boundary.', ...
            fig_no, method_labels{method_idx});
        boundary = B{1};
        y = double(boundary(:, 1));
        x = double(boundary(:, 2));
        keep = (x > 1) & (y > 1);
        expected_boundary = [x(keep), y(keep)];
        actual_boundary = double(reproduced_data.author_boundary.(method_fields{method_idx}));

        check_name = sprintf('%s/%s pointwise boundary', fig_no, method_labels{method_idx});
        passed = isequal(actual_boundary, expected_boundary) && ...
            size(actual_boundary, 1) == expected_counts(method_idx);
        check_names(end+1, 1) = string(check_name); %#ok<SAGROW>
        check_status(end+1, 1) = string(ternary_text(passed, 'PASS', 'FAIL')); %#ok<SAGROW>
        check_details(end+1, 1) = string(sprintf( ...
            'actual=%d, expected=%d, xrange=[%g,%g], yrange=[%g,%g]', ...
            size(actual_boundary, 1), expected_counts(method_idx), ...
            min(actual_boundary(:,1)), max(actual_boundary(:,1)), ...
            min(actual_boundary(:,2)), max(actual_boundary(:,2)))); %#ok<SAGROW>
        assert(passed, '%s failed.', check_name);
    end
end

figure44_data = load(fullfile(data_dir, [figure44_stem boundary_suffix '.mat']), ...
    'author_boundary');
guyan44 = double(figure44_data.author_boundary.Guyan);
expected_right_edge = [(52 * ones(9,1)), (2:10)'];
contains_right_edge = all(ismember(expected_right_edge, guyan44, 'rows'));
check_names(end+1, 1) = "4-4/Guyan right edge (52,2)..(52,10)";
check_status(end+1, 1) = string(ternary_text(contains_right_edge, 'PASS', 'FAIL'));
check_details(end+1, 1) = string(sprintf('matched=%d/9', ...
    sum(ismember(expected_right_edge, guyan44, 'rows'))));
assert(contains_right_edge, 'Figure 4-4 Guyan right edge is incomplete.');

check_table = table(check_names, check_status, check_details, ...
    'VariableNames', {'check_item', 'status', 'details'});
check_csv_name = char([20316 32773 29616 23384 77 65 84 21407 33050 26412 ...
    22797 36305 20505 36873 36880 39033 26816 26597 46 99 115 118]);
writetable(check_table, fullfile(validation_dir, check_csv_name), 'Encoding', 'UTF-8');

summary_data = struct();
summary_data.status = 'PASS';
summary_data.check_count = height(check_table);
summary_data.pass_count = nnz(check_table.status == "PASS");
summary_data.fail_count = nnz(check_table.status == "FAIL");
summary_data.figure_4_4_guyan_right_edge = '(52,2)..(52,10)';
summary_data.evidence_level = 'candidate rerun of author surviving MAT files and plotting script';
summary_data.calculation_level_status = 'not upgraded';
summary_data.thesis_pointwise_status = 'four reduced-order curves do not match the thesis vector boundaries';
summary_json_name = char([20316 32773 29616 23384 77 65 84 21407 33050 26412 ...
    22797 36305 20505 36873 39564 25910 25688 35201 46 106 115 111 110]);
fid = fopen(fullfile(validation_dir, summary_json_name), 'w', 'n', 'UTF-8');
assert(fid >= 0, 'Cannot create validation summary.');
file_cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s', jsonencode(summary_data, 'PrettyPrint', true));

fprintf('Author surviving-MAT candidate validation: %d/%d PASS.\n', ...
    summary_data.pass_count, summary_data.check_count);

function output = ternary_text(condition, true_value, false_value)
if condition
    output = true_value;
else
    output = false_value;
end
end
