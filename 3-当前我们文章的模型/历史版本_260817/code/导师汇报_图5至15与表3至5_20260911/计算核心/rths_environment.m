function info = rths_environment()
% 检查真正需要的软件，不安装软件、不修改永久MATLAB路径。
assert(~isempty(ver('simulink')),'需要安装Simulink。');
assert(exist('ss','file')==2,'需要Control System Toolbox的ss函数。');
info=struct('matlab_release',version('-release'),'matlab_version',version,...
    'simulink_installed',true,'control_system_installed',true);
fprintf('环境：MATLAB %s；Simulink；Control System Toolbox。\n',info.matlab_release);
end
