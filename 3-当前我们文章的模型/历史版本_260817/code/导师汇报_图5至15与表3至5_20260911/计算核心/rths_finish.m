function demo = rths_finish(demo,bundle)
% 只有前面各节成功后才写完成状态；完整中间量保存在本次数据文件。
fields=fieldnames(bundle.metrics);
for k=1:numel(fields)
    value=bundle.metrics.(fields{k});
    if istable(value),writetable(value,fullfile(demo.output,['metric_' fields{k} '.csv']));end
end
save(fullfile(demo.output,'calculation.mat'),'bundle','-v7');
if isfield(bundle,'inputs') && ~isempty(bundle.inputs)
    x=bundle.inputs;
    values=[x.time x.eq_on_grid x.chirp(:,2) x.chirp_frequency_hz];
    writetable(array2table(values,'VariableNames',{'time_s','earthquake_m_s2','chirp_m_s2','chirp_frequency_hz'}),...
        fullfile(demo.output,'excitation.csv'));
end
demo.elapsed_seconds=toc(demo.timer);demo.status='COMPLETED';
if strcmp(demo.label,'Fig14')
    demo.calculation_type='historical_boundary_redraw';
elseif strcmp(demo.label,'All_figures_tables')
    demo.calculation_type='fresh_calculations_with_Fig14_historical_redraw';
else
    demo.calculation_type='fresh_calculation';
end
if isfield(bundle,'responses')
    demo.simulation_count=sum(~cellfun(@isempty,bundle.responses),'all');
end
rths_status(demo);
fprintf('\n%s 完成，耗时%.2f s。工作区bundle保留本轮中间量。\n',demo.label,demo.elapsed_seconds);
end
