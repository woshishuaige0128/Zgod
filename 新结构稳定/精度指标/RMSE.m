% 频率区间对应的时间段（单位秒），根据你之前计算结果
time_intervals = [0, 7.27;   % 0.1–1.9Hz
                  7.27, 13.73;  % 1.9–3.5Hz （7.27 + 6.46）
                  13.73, 21.4;  % 3.5–5.4Hz （13.73 + 7.67）
                  21.4, 32.31;  % 5.4–8.1Hz （21.4 + 10.91）
                  32.31, 40];   % 8.1–10Hz （32.31 + 7.67）

% data_t: N×3
x_ref = data_t(1,:);
x_guyan = data_t(2,:);
x_cb = data_t(3,:);

range_ref = max(x_ref) - min(x_ref);

for i = 1:size(time_intervals,1)
    t_start = time_intervals(i,1);
    t_end = time_intervals(i,2);
    
    % 找出对应时间段的索引
    idx = find(time >= t_start & time < t_end);
    
    % 取出对应时间段数据
    ref_segment = x_ref(idx);
    guyan_segment = x_guyan(idx);
    cb_segment = x_cb(idx);
    
    % 计算RMSE
    rmse_guyan = sqrt(mean((ref_segment - guyan_segment).^2));
    rmse_cb = sqrt(mean((ref_segment - cb_segment).^2));
    
    % 归一化
    nrmse_guyan = rmse_guyan / range_ref * 100;
    nrmse_cb = rmse_cb / range_ref * 100;
    
    fprintf('区间 %d (%.2f-%.2fs): Guyan RMSE=%.6f, 归一化RMSE=%.6f%%; CB RMSE=%.6f, 归一化RMSE=%.6f%%\n', ...
        i, t_start, t_end, rmse_guyan, nrmse_guyan, rmse_cb, nrmse_cb);
end
