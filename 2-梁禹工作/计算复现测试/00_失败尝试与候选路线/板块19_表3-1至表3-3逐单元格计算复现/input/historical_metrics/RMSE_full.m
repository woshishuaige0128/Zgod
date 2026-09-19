data = simout.Data;  % 3行 × N列，N是时间点数
time = simout.Time;  % N×1 时间向量

% 转置一下更符合一般习惯，行是时间，列是自由度类型
% 这里自由度是3个类型（ref, guyan, cb）
data_t = data';  % N × 3

x_ref = data_t(1,:);    % 参考解数据 (N×1)
x_guyan = data_t(2,:);  % Guyan数据 (N×1)
x_cb = data_t(3,:);     % CB数据 (N×1)

% 计算整体 RMSE
rmse_guyan = sqrt(mean((x_ref - x_guyan).^2));
rmse_cb = sqrt(mean((x_ref - x_cb).^2));

% 归一化 RMSE：以参考信号幅值范围为基准
range_ref = max(x_ref) - min(x_ref);

nrmse_guyan = rmse_guyan / range_ref.*100;
nrmse_cb = rmse_cb / range_ref.*100;

fprintf('Guyan RMSE = %.6f, 归一化RMSE = %.6f\n', rmse_guyan, nrmse_guyan);
fprintf('CB RMSE = %.6f, 归一化RMSE = %.6f\n', rmse_cb, nrmse_cb);