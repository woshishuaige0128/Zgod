function style = rths_style()
% 全文统一方法颜色、线型与点型。MATLAB解释器直接绘制数学符号。
style.colors=[85 85 85;68 119 170;238 102 119]/255;
style.lines={'--','-.','-'};style.markers={'o','^','s'};
style.names={'Full order','Guyan','Craig--Bampton'};
fonts=listfonts;style.font='Times New Roman';
if any(strcmpi(fonts,'CMU Serif')),style.font='CMU Serif';end
end
