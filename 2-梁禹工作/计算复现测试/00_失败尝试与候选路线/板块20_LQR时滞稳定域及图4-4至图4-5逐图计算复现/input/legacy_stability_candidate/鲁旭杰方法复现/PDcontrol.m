function [Kp_ctrl, Kd_ctrl] = PDcontrol(M, K, C, omega_target, zeta_target, gain_factor)
% DESIGNPDCTRL 自动设计稳定的对角 PD 控制器
%
% 输入参数：
%   M:           n×n 质量矩阵（必须为对角）
%   K:           n×n 原始刚度矩阵
%   C:           n×n 原始阻尼矩阵
%   omega_target: n×1 各自由度的目标自然频率（单位：rad/s）
%   zeta_target:  n×1 各自由度的目标阻尼比（单位：无量纲）
%   gain_factor:  可选，控制器增益缩放（默认 1）
%
% 输出：
%   Kp_ctrl:     控制器刚度矩阵（n×n 对角，非负）
%   Kd_ctrl:     控制器阻尼矩阵（n×n 对角，非负）

    if nargin < 6
        gain_factor = 1; % 默认增益
    end

    % 取对角元素（避免误差）
    m_diag = diag(M);
    k_diag = diag(K);
    c_diag = diag(C);

    % 目标刚度和阻尼
    k_target = (omega_target .^ 2) .* m_diag;
    c_target = 2 .* zeta_target .* omega_target .* m_diag;

    % 控制器增益（对角 + 非负）
    kp_diag = gain_factor * max(k_target - k_diag, 0);
    kd_diag = gain_factor * max(c_target - c_diag, 0);

    % 构造对角控制器矩阵
    Kp_ctrl = diag(kp_diag);
    Kd_ctrl = diag(kd_diag);
end
