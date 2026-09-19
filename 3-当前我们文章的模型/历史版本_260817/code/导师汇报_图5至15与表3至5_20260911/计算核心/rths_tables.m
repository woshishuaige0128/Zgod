function result = rths_tables(number,metrics,demo)
% 先输出数值，再按稿件精度格式化；不会将论文数值写死为计算结果。
switch number
    case 3
        T=metrics.modal;values=zeros(4,6);r=0;
        for d=1:2
            for mode=1:2
                r=r+1;g=T(T.division==d & T.method==2 & T.mode==mode,:);
                c=T(T.division==d & T.method==3 & T.mode==mode,:);
                values(r,:)=[d mode g.frequency_error_percent c.frequency_error_percent g.MAC c.MAC];
            end
        end
        result=array2table(values,'VariableNames',{'division','mode','Guyan_frequency_error_percent','CB_frequency_error_percent','Guyan_MAC','CB_MAC'});
        fprintf('\n表3：划分 阶次 | Guyan频率误差 CB频率误差 | Guyan_MAC CB_MAC\n');
        for r=1:4,fprintf('%d %d | %.3f %.3f | %.4f %.4f\n',values(r,:));end
    case 4
        E=metrics.errors;values=zeros(6,4);
        for row=1:6
            ex=1+(row>1);band=max(0,row-1);
            for d=1:2
                for method=2:3
                    q=E(E.division==d & E.excitation==ex & E.method==method & E.storey==1 & E.band==band,:);
                    assert(height(q)==1,'表4需要四套响应的全时程及分频段结果。');
                    values(row,(d-1)*2+method-1)=q.NRMSE_percent;
                end
            end
        end
        labels={'El Centro';'Chirp 0.1-1.9 Hz';'Chirp 1.9-3.5 Hz';'Chirp 3.5-5.4 Hz';'Chirp 5.4-8.1 Hz';'Chirp 8.1-10 Hz'};
        result=[table(labels,'VariableNames',{'excitation'}) array2table(values,'VariableNames',{'division1_Guyan','division1_CB','division2_Guyan','division2_CB'})];
        fprintf('\n表4：全时程峰峰值归一化，数值单位%%\n');
        for r=1:6
            fprintf('%s | ',labels{r});
            for c=1:4,if values(r,c)<.001,fprintf('<0.001 ');else,fprintf('%.3f ',values(r,c));end,end
            fprintf('\n');
        end
    case 5
        T=metrics.totals;values=zeros(2,3);
        for d=1:2,values(d,:)=[d T.delta_E(T.division==d & T.method==2) T.delta_E(T.division==d & T.method==3)];end
        result=array2table(values,'VariableNames',{'division','Guyan','Craig_Bampton'});
        fprintf('\n表5：各作动坐标的绝对相对偏离之和\n');
        for r=1:2,fprintf('划分%d | %.4f | %.4f\n',values(r,:));end
    otherwise,error('没有表%d。',number);
end
writetable(result,fullfile(demo.output,sprintf('Table%02d.csv',number)));
save(fullfile(demo.output,sprintf('Table%02d.mat',number)),'result');
end
