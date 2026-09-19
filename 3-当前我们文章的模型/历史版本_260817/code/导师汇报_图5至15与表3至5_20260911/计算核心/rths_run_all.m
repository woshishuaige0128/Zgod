function [bundle,demo] = rths_run_all(packageRoot,visible)
% 全文入口：四套响应只在本次运行中共享，不读取历史响应缓存。
if nargin<2,visible=true;end
demo=rths_begin(packageRoot,'All_figures_tables',visible);
try
    frame=frame_model();models={rths_reduce(frame,1),rths_reduce(frame,2)};
    modes=rths_modes(frame,models);inputs=rths_inputs(packageRoot);
    responses=cell(2,2);tags={'eq','chirp'};
    for d=1:2
        for ex=1:2
            responses{d,ex}=rths_simulate(frame,models{d},inputs,tags{ex},demo);
        end
    end
    metrics=rths_metrics(frame,models,modes,responses);
    boundaries=rths_boundaries(packageRoot);
    bundle=struct('frame',frame,'models',{models},'modes',{modes},'inputs',inputs,...
        'responses',{responses},'metrics',metrics,'boundaries',{boundaries});
    for n=5:15
        [fig,plotted]=rths_plot(n,bundle,demo);
        rths_save_figure(fig,n,demo,plotted);
        if ~visible,close(fig);end
    end
    for n=3:5,rths_tables(n,metrics,demo);end
    demo=rths_finish(demo,bundle);
    assignin('base','bundle',bundle);assignin('base','demo',demo);
catch problem
    demo.status='FAILED';demo.error=problem.message;rths_status(demo);rethrow(problem);
end
end
