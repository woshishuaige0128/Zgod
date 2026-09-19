function demo = rths_begin(root,label,visible)
% 新建本次运行目录，不读取或覆盖旧运行；所有路径由当前包位置生成。
if nargin<3,visible=strcmp(get(groot,'DefaultFigureVisible'),'on');end
demo=struct('root',root,'label',label,'visible',visible,'stage',0);
demo.environment=rths_environment();
runId=[char(datetime('now','Format','yyyyMMdd_HHmmss_SSS')) '_' label];
demo.output=fullfile(root,'运行结果',runId);
assert(~isfolder(demo.output),'本次运行目录已存在，请重新运行初始化节。');
mkdir(demo.output);
demo.started_at=char(datetime('now','Format','yyyy-MM-dd HH:mm:ss'));
demo.timer=tic;demo.simulation_count=0;demo.status='STARTED';
rths_status(demo);
fprintf('\n%s：开始本轮计算，输出 %s\n',label,demo.output);
end
