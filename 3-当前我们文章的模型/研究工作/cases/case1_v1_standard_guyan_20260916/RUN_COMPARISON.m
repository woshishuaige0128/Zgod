function RUN_COMPARISON(outputRoot)
% Same full-frame model and inputs; only Guyan matrix construction changes.
packageRoot=fileparts(mfilename('fullpath'));addpath(fullfile(packageRoot,'code'));
if nargin<1,outputRoot=fullfile(packageRoot,'results',char(datetime('now','Format','yyyyMMdd_HHmmss')));end
if ~isfolder(outputRoot),mkdir(outputRoot);end
frame=frame_model();inputs=rths_inputs(packageRoot);
formulations={'legacy','standard'};
for variant=1:2
    formulation=formulations{variant};out=fullfile(outputRoot,formulation);
    assert(~isfolder(out),'Output exists; choose a new output root.');mkdir(out);
    demo=struct('output',out,'visible',false,'label',formulation);
    models={rths_reduce(frame,1,formulation),rths_reduce(frame,2,formulation)};
    modes=rths_modes(frame,models);responses=cell(2,2);tags={'eq','chirp'};
    for d=1:2
        R=models{d};T=R.T;
        if variant==2
            assert(norm(R.Mg-T'*R.Mo*T,'fro')/norm(R.Mg,'fro')<1e-12);
            assert(norm(R.Cg-T'*R.Co*T,'fro')/norm(R.Cg,'fro')<1e-12);
            assert(norm(R.Kg-T'*R.Ko*T,'fro')/norm(R.Kg,'fro')<1e-12);
            [~,p]=chol(R.Mg);assert(p==0);[~,p]=chol(R.Kg);assert(p==0);
        end
        for ex=1:2
            responses{d,ex}=rths_simulate(frame,R,inputs,tags{ex},demo);
        end
    end
    metrics=rths_metrics(frame,models,modes,responses);
    bundle=struct('frame',frame,'models',{models},'modes',{modes},'inputs',inputs,'responses',{responses},'formulation',formulation);
    save(fullfile(out,'calculation.mat'),'bundle','-v7');
    fields=fieldnames(metrics);
    for k=1:numel(fields),writetable(metrics.(fields{k}),fullfile(out,['metric_' fields{k} '.csv']));end
    fprintf('FORMULATION_COMPLETE=%s\n',formulation);
end
fprintf('ALL_EIGHT_SIMULATIONS_COMPLETE\n');
end
