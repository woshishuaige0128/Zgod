function metrics = rths_metrics(frame,models,modes,responses)
% 所有指标来自本轮模型/时程。空responses时只计算模态类指标。
metrics=struct;modalRows=[];shareRows=[];barRows=[];sumRows=[];weightRows=[];
for d=1:2
    R=models{d};full=modes{d,1};acts=[1 6];if d==2,acts=[1 11];end
    for j=1:3
        s=modes{d,j};
        shareRows=[shareRows;d*ones(15,1) j*ones(15,1) (1:15)' s.shares]; %#ok<AGROW>
        for k=1:5
            weightRows=[weightRows;d j k s.frequency_hz(k) s.gamma(k) s.weights(k)]; %#ok<AGROW>
        end
        if j==1,continue;end
        for k=1:2
            a=full.native_modes(R.master,k);b=s.native_modes(1:numel(R.master),k);
            mac=(a'*b)^2/((a'*a)*(b'*b));
            error=abs(s.frequency_hz(k)-full.frequency_hz(k))/full.frequency_hz(k)*100;
            modalRows=[modalRows;d j k full.frequency_hz(k) s.frequency_hz(k) error mac]; %#ok<AGROW>
        end
        deviation=abs((s.shares(acts)-full.shares(acts))./full.shares(acts));
        for k=1:2,barRows=[barRows;d j acts(k) full.shares(acts(k)) s.shares(acts(k)) deviation(k)];end %#ok<AGROW>
        sumRows=[sumRows;d j sum(deviation)]; %#ok<AGROW>
    end
end
metrics.modal=array2table(modalRows,'VariableNames',{'division','method','mode','full_hz','reduced_hz','frequency_error_percent','MAC'});
metrics.shares=array2table(shareRows,'VariableNames',{'division','method','physical_dof','share'});
metrics.weights=array2table(weightRows,'VariableNames',{'division','method','mode','frequency_hz','gamma','weight'});
metrics.deviations=array2table(barRows,'VariableNames',{'division','method','physical_dof','full_share','reduced_share','absolute_relative_deviation'});
metrics.totals=array2table(sumRows,'VariableNames',{'division','method','delta_E'});
if isempty(responses) || all(cellfun(@isempty,responses),'all'),return;end
drifts=[];errors=[];edges=[0.1 1.9 3.5 5.4 8.1 10];
for d=1:2
    for ex=1:2
        if isempty(responses{d,ex}),continue;end
        r=responses{d,ex};t=r.time;
        for j=1:3
            x=r.mm(:,:,j);relative=diff([zeros(numel(t),1) x],1,2);
            [peak,index]=max(abs(relative),[],1);
            for floor=1:3
                lower=0;if floor>1,lower=x(index(floor),floor-1);end
                drifts=[drifts;d ex j floor peak(floor)/frame.height_mm*100 t(index(floor)) x(index(floor),floor) lower]; %#ok<AGROW>
            end
            if j==1,continue;end
            for floor=1:3
                ref=r.mm(:,floor,1);err=r.mm(:,floor,j)-ref;range=max(ref)-min(ref);
                fullError=100*sqrt(trapz(t,err.^2)/40)/range;
                errors=[errors;d ex j floor 0 0 40 fullError]; %#ok<AGROW>
                if ex==2 && floor==1
                    for band=1:5
                        lo=(edges(band)-0.1)/0.2475;hi=(edges(band+1)-0.1)/0.2475;
                        tb=[lo;t(t>lo & t<hi);hi];eb=interp1(t,err,tb,'linear');
                        value=100*sqrt(trapz(tb,eb.^2)/(hi-lo))/range;
                        errors=[errors;d ex j floor band lo hi value]; %#ok<AGROW>
                    end
                end
            end
        end
    end
end
metrics.drifts=array2table(drifts,'VariableNames',{'division','excitation','method','storey','peak_drift_percent','peak_time_s','upper_mm','lower_mm'});
metrics.errors=array2table(errors,'VariableNames',{'division','excitation','method','storey','band','start_s','end_s','NRMSE_percent'});
end
