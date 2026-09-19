function [fig,plotted] = rths_plot(number,bundle,demo)
% 从本轮bundle生成一张图。曲线对象保存可核查的绘图数据。
s=rths_style();height=4.9;
if any(number==[6 13]),height=3.55;elseif number==14,height=3.1;elseif number==5,height=3.9;end
fig=figure('Color','w','Units','inches','Position',[1 1 7.48 height],...
    'Visible',mat2str_onoff(demo.visible),'Renderer','painters','Name',sprintf('Figure %d',number),...
    'NumberTitle','off','PaperPositionMode','auto');
switch number
    case 5
        in=bundle.inputs;t=in.time;series={in.eq_on_grid,in.chirp(:,2)};
        for k=1:2
            ax=axes(fig,'Position',[.10 .57-(k-1)*.43 .87 .35]);
            plot(ax,t,series{k},'Color',s.colors(1,:),'LineWidth',.8);
            style_axis(ax,s);xlim(ax,[0 40]);xticks(ax,0:8:40);ylim(ax,padded(series{k},.18));
            ylabel(ax,'Acceleration (m/s$^2$)','Interpreter','latex');
            captions={'(a) El Centro, scale 0.40','(b) Linear chirp, 0.1--10 Hz'};
            label(ax,captions{k});if k==2,xlabel(ax,'Time (s)');end
        end
    case 6
        handles=gobjects(3,1);
        for k=1:4
            d=1+(k>2);mode=1+mod(k-1,2);
            ax=axes(fig,'Position',[.063+(k-1)*.237 .16 .205 .74]);hold(ax,'on');
            for j=1:3
                q=bundle.modes{d,j};handles(j)=plot(ax,[0;q.horizontal(:,mode)],0:3,...
                    'Color',s.colors(j,:),'LineStyle',s.lines{j},'Marker',s.markers{j},...
                    'MarkerFaceColor','w','LineWidth',1.2,'MarkerSize',4);
            end
            xline(ax,0,'Color',[.75 .75 .75],'LineWidth',.5,'HandleVisibility','off');
            style_axis(ax,s);xlim(ax,[-1.18 1.18]);ylim(ax,[-.12 3.48]);xticks(ax,[-1 -.5 0 .5 1]);yticks(ax,0:3);
            if k>1,yticklabels(ax,{});else,ylabel(ax,'Storey level');end
            text(ax,.04,.985,sprintf('(%c) Division %s\nMode %d',96+k,repmat('I',1,d),mode),...
                'Units','normalized','VerticalAlignment','top','FontSize',8,'FontName',s.font,'Interpreter','none');
            freq=arrayfun(@(j)bundle.modes{d,j}.frequency_hz(mode),1:3);
            msg=sprintf('f (Hz)\nFull %.4f\nGuyan %.4f\nCB %.4f',freq);
            if mode==1,pos=[.04 .58];va='top';else,pos=[.51 .095];va='bottom';end
            h=text(ax,pos(1),pos(2),msg,'Units','normalized','VerticalAlignment',va,...
                'FontSize',8,'FontName',s.font,'Interpreter','none','Tag','frequency_annotation');
            h.UserData=struct('frequency_hz',freq,'division',d,'mode',mode);
        end
        shared_legend(fig,handles,s,.915);shared_xlabel(fig,'Normalised horizontal displacement',.008);
    case {7,8,10,11}
        d=1+any(number==[8 11]);ex=1+(number>=10);r=bundle.responses{d,ex};t=r.time;
        windows=[10 11;21.5 22.5];if ex==2,windows=[13 14;38 38.3];end
        handles=gobjects(3,1);
        for row=1:2
            floor=1+2*(row-1);values=squeeze(r.mm(:,floor,:));
            for col=1:3
                xpos=[.08 .57 .81];width=[.41 .17 .17];
                ax=axes(fig,'Position',[xpos(col) .56-(row-1)*.43 width(col) .34]);
                range=[0 40];if col>1,range=windows(col-1,:);end
                ids=find(t>=range(1) & t<=range(2));
                if col==1,ids=ids(unique([1:6:numel(ids),numel(ids)]));end
                handles=three_curves(ax,t(ids),values(ids,:),s,col>1);
                style_axis(ax,s);xlim(ax,range);ylim(ax,padded(values(ids,:),.10));
                if col==1,xticks(ax,0:8:40);end
                if col==1,ylabel(ax,'Displacement (mm)');label(ax,sprintf('(%c) Storey %d',96+row,floor));end
                if row==2,xlabel(ax,'Time (s)');end
            end
        end
        shared_legend(fig,handles,s,.935);
    case {9,12}
        ex=1+(number==12);r=bundle.responses{2,ex};t=r.time;x=squeeze(r.mm(:,2,:));
        errors=x(:,2:3)-x(:,1);metric=100*sqrt(trapz(t,errors.^2)/40)/(max(x(:,1))-min(x(:,1)));
        for row=1:3
            ax=axes(fig,'Position',[.11 .71-(row-1)*.295 .86 .24]);
            if row==1
                handles=three_curves(ax,t,x,s,false);values=x;
                ylabel(ax,'Displacement (mm)');label(ax,'(a) Middle storey, $\psi_6$');
                legend(ax,handles,s.names,'Interpreter','latex','Box','off','Location','northeast','Orientation','horizontal','FontSize',9);
            else
                j=row;values=errors(:,row-1);plot(ax,t,values,'Color',s.colors(j,:),'LineStyle',s.lines{j},'LineWidth',.9);
                yline(ax,0,'Color',[.75 .75 .75],'LineWidth',.5);ylabel(ax,'Error (mm)');
                label(ax,sprintf('(%c) %s, NRMSE = %.3f\\%%',96+row,s.names{j},metric(row-1)));
            end
            style_axis(ax,s);xlim(ax,[0 40]);xticks(ax,0:8:40);ylim(ax,padded(values,.20));
            if row==3,xlabel(ax,'Time (s)');else,xticklabels(ax,{});end
        end
    case 13
        handles=gobjects(3,1);D=bundle.metrics.drifts;
        for k=1:4
            d=1+mod(k-1,2);ex=1+(k>2);
            ax=axes(fig,'Position',[.065+(k-1)*.236 .16 .205 .74]);hold(ax,'on');
            for j=1:3
                rows=D(D.division==d & D.excitation==ex & D.method==j,:);
                handles(j)=plot(ax,rows.peak_drift_percent,rows.storey,'Color',s.colors(j,:),...
                    'LineStyle',s.lines{j},'Marker',s.markers{j},'MarkerFaceColor','w','LineWidth',1.2,'MarkerSize',4);
            end
            style_axis(ax,s);ylim(ax,[.8 3.55]);yticks(ax,1:3);
            if ex==1,xlim(ax,[0 .92]);xticks(ax,[0 .25 .5 .75]);else,xlim(ax,[0 2.65]);xticks(ax,[0 .8 1.6 2.4]);end
            if k==1,ylabel(ax,'Storey');else,yticklabels(ax,{});end
            names={'El Centro','Chirp'};
            label(ax,sprintf('(%c) Division %s\n%s',96+k,repmat('I',1,d),names{ex}));
        end
        shared_legend(fig,handles,s,.925);shared_xlabel(fig,'Peak interstorey drift (\%)',.008);
    case 14
        B=bundle.boundaries;handles=gobjects(3,1);
        maxY=max(cellfun(@(x)max(x.milliseconds(:,2)),B),[],'all');
        for d=1:2
            ax=axes(fig,'Position',[.085+(d-1)*.49 .19 .405 .70]);hold(ax,'on');
            for j=1:3
                xy=B{d,j}.milliseconds;
                handles(j)=plot(ax,xy(:,1),xy(:,2),'Color',s.colors(j,:),'LineStyle',s.lines{j},'LineWidth',1.2);
            end
            maxX=max(cellfun(@(x)max(x.milliseconds(:,1)),B(d,:)));
            style_axis(ax,s);xlim(ax,[0 maxX*1.08]);ylim(ax,[0 maxY*1.12]);xlabel(ax,'Delay $\tau_1$ (ms)','Interpreter','latex');
            if d==1,ylabel(ax,'Delay $\tau_2$ (ms)','Interpreter','latex');end
            label(ax,sprintf('(%c) Division %s',96+d,repmat('I',1,d)));
        end
        shared_legend(fig,handles,s,.935);
    case 15
        for d=1:2
            ax=axes(fig,'Position',[.08 .57-(d-1)*.44 .48 .35]);hold(ax,'on');
            handles=gobjects(3,1);
            for j=1:3
                handles(j)=plot(ax,1:15,bundle.modes{d,j}.shares,'Color',s.colors(j,:),...
                    'LineStyle',s.lines{j},'Marker',s.markers{j},'MarkerFaceColor','w','LineWidth',1.2,'MarkerSize',4);
            end
            style_axis(ax,s);xlim(ax,[.5 15.5]);ylim(ax,[-.02 .8]);xticks(ax,[1 3 6 9 12 15]);
            xlabel(ax,'Physical coordinate index $j$','Interpreter','latex');ylabel(ax,'Modal share $E_j$','Interpreter','latex');
            label(ax,sprintf('(%c) Division %s',95+2*d,repmat('I',1,d)));
            if d==1,legend(ax,handles,s.names,'Interpreter','latex','Box','off','Location','northeast','FontSize',9);end
            ax=axes(fig,'Position',[.685 .57-(d-1)*.44 .295 .35]);hold(ax,'on');
            A=bundle.metrics.deviations;values=zeros(2,2);
            for j=2:3,rows=A(A.division==d & A.method==j,:);values(:,j-1)=rows.absolute_relative_deviation;end
            bars=bar(ax,1:2,values,.72,'grouped');
            for j=1:2,bars(j).FaceColor=s.colors(j+1,:);bars(j).EdgeColor='white';end
            style_axis(ax,s);xticks(ax,1:2);xlim(ax,[.45 2.55]);
            ticks={'$\psi_1$','$\psi_6$'};if d==2,ticks{2}='$\psi_{11}$';end
            xticklabels(ax,ticks);ax.TickLabelInterpreter='latex';ylim(ax,[0 max(values,[],'all')*1.30]);
            ylabel(ax,'Relative share deviation');xlabel(ax,'Actuated coordinate');
            label(ax,sprintf('(%c) Division %s',96+2*d,repmat('I',1,d)));
        end
    otherwise,error('没有图%d的绘图入口。',number);
end
drawnow;
% 保存实际图线收到的X/Y值，便于验证抽稀显示仍来自本轮计算。
lines=findall(fig,'Type','line');plotted=cell(numel(lines),1);
for k=1:numel(lines),plotted{k}=struct('x',lines(k).XData,'y',lines(k).YData,'name',lines(k).DisplayName);end
fig.UserData=struct('figure_number',number,'run_label',demo.label,'data_origin','current_run','curves',{plotted});
if number==14,fig.UserData.data_origin='historical_boundary_redraw';end
end

function style_axis(ax,s)
set(ax,'FontName',s.font,'FontSize',9,'TickLabelInterpreter','latex','TickDir','in',...
    'Box','on','LineWidth',.8,'XMinorTick','off','YMinorTick','off','XGrid','off','YGrid','off');
end
function h=three_curves(ax,t,x,s,markers)
hold(ax,'on');h=gobjects(3,1);
for j=[3 2 1]
    h(j)=plot(ax,t,x(:,j),'Color',s.colors(j,:),'LineStyle',s.lines{j},'LineWidth',1.0);
    if markers,set(h(j),'Marker',s.markers{j},'MarkerIndices',unique(round(linspace(1,numel(t),10))),...
            'MarkerSize',4,'MarkerFaceColor','w');end
end
end
function y=padded(x,fraction)
lo=min(x,[],'all');hi=max(x,[],'all');span=max(hi-lo,1e-8);y=[lo-.06*span hi+fraction*span];
end
function label(ax,message)
text(ax,.025,.96,message,'Units','normalized','VerticalAlignment','top','FontSize',9,'Interpreter','latex');
end
function shared_xlabel(fig,message,y)
annotation(fig,'textbox',[.11 y .81 .08],'String',message,'EdgeColor','none',...
    'HorizontalAlignment','center','VerticalAlignment','middle','Interpreter','latex','FontSize',9);
end
function shared_legend(fig,h,s,y)
l=legend(h,s.names,'Interpreter','latex','Box','off','Orientation','horizontal','FontSize',9);
l.Units='normalized';l.Position=[.19 y .65 .06];
end
function text=mat2str_onoff(value)
text='off';if value,text='on';end
end
