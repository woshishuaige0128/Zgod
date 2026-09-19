function response = rths_simulate(frame,R,inputs,excitation,demo)
% 每次从本轮模型积分；SimulationInput注入变量，不依赖旧基础工作区。
clock=tic;runDir=fullfile(demo.output,sprintf('division%d_%s',R.division,excitation));
assert(~isfolder(runDir),'该工况已经计算。重算请从初始化节开始，避免混用结果。');mkdir(runDir);
previous=Simulink.fileGenControl('getConfig');
cacheCleanup=onCleanup(@()restore_and_clean(previous,runDir));
Simulink.fileGenControl('set','CacheFolder',fullfile(runDir,'temp'),...
    'CodeGenFolder',fullfile(runDir,'temp'),'createDir',true);
modelFile=rths_make_simulink(runDir);[~,name]=fileparts(modelFile);load_system(modelFile);
modelCleanup=onCleanup(@()close_system(name,0));
job=Simulink.SimulationInput(name);
job=job.setVariable('dt',inputs.dt).setVariable('excitation_input',inputs.(excitation));
G={R.G_1,R.G_2,R.G_3};C={R.Cfloor1,R.Cfloor2,R.Cfloor3};
for j=1:3
    tag=num2str(j);
    job=job.setVariable(['A' tag],G{j}.A).setVariable(['B' tag],G{j}.B)...
        .setVariable(['C' tag],C{j}).setVariable(['D' tag],zeros(3,size(G{j}.B,2)));
end
% 沿用原链的加速度输入符号约定，三模型采用相同广义力方向。
fullForce=diag([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0].*frame.M);
job=job.setVariable('full_force',fullForce).setVariable('guyan_force',R.T'*R.Mf)...
    .setVariable('cb_force',R.T_cb'*R.Mf);
% 将同一组本轮参数存入模型自己的工作区，保存的SLX也可独立打开检查/运行。
workspace=get_param(name,'ModelWorkspace');variables=job.Variables;
for k=1:numel(variables),workspace.assignin(variables(k).Name,variables(k).Value);end
save_system(name,modelFile);
simulated=sim(job);
time=simulated.response_1.Time(:);x=zeros(numel(time),3,3);
for j=1:3
    result=simulated.(['response_' num2str(j)]);
    assert(max(abs(result.Time(:)-time))<1e-12);
    x(:,:,j)=squeeze(result.Data);
end
assert(isequal(size(x),[40961 3 3]) && all(isfinite(x(:))));
assert(abs(time(1))<1e-12 && abs(time(end)-40)<1e-12 && max(abs(diff(time)-1/1024))<1e-12);
response=struct('division',R.division,'excitation',excitation,'time',time,...
    'mm',x,'seconds',toc(clock),'model_file',modelFile);
data=[time reshape(permute(x,[1 3 2]),numel(time),9)];
names={'time_s','floor1_full_mm','floor1_guyan_mm','floor1_cb_mm',...
    'floor2_full_mm','floor2_guyan_mm','floor2_cb_mm','floor3_full_mm','floor3_guyan_mm','floor3_cb_mm'};
writetable(array2table(data,'VariableNames',names),fullfile(runDir,'response.csv'));
save(fullfile(runDir,'response.mat'),'response');
fprintf('划分%d / %s：40961×3×3响应，实际耗时%.2f s。\n',R.division,excitation,response.seconds);
end

function restore_and_clean(previous,runDir)
Simulink.fileGenControl('set','CacheFolder',previous.CacheFolder,...
    'CodeGenFolder',previous.CodeGenFolder,'createDir',true);
% 仅删除本函数新建工况目录内的temp，先确认规范绝对路径仍在该目录内。
cache=fullfile(runDir,'temp');
if isfolder(cache)
    parent=char(java.io.File(runDir).getCanonicalPath());
    target=char(java.io.File(cache).getCanonicalPath());
    assert(startsWith(target,[parent filesep]) && strcmp(target,fullfile(parent,'temp')),...
        '拒绝清理超出本次工况目录的缓存。');
    rmdir(target,'s');
end
end
