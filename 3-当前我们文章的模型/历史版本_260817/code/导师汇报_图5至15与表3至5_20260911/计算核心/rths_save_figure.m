function paths = rths_save_figure(fig,number,demo,plotted)
% 图像、可编辑图和实际图线数据同名，保存到当前运行目录。
base=fullfile(demo.output,sprintf('Fig%02d',number));
savefig(fig,[base '.fig']);
exportgraphics(fig,[base '.pdf'],'ContentType','vector','BackgroundColor','white');
exportgraphics(fig,[base '.png'],'Resolution',600,'BackgroundColor','white');
save([base '_plot_data.mat'],'plotted');
paths=struct('fig',[base '.fig'],'pdf',[base '.pdf'],'png',[base '.png']);
fprintf('图%d已保存为FIG、矢量PDF和600 dpi PNG。\n',number);
end
