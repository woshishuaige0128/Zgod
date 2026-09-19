function boundaries = rths_boundaries(root)
% 图14只重绘历史边界。点顺序与原六条路径保持，不运行稳定性求解。
names={'Original','Guyan','CB'};panels={'4-4','4-5'};boundaries=cell(2,3);count=0;
for d=1:2
    for j=1:3
        file=fullfile(root,'必要输入',sprintf('图%s_%s_论文矢量边界.csv',panels{d},names{j}));
        a=readtable(file);assert(isequal(a.point_order,(1:height(a))'));
        assert(all(isfinite(a.tau1_step)) && all(isfinite(a.tau2_step)));
        boundaries{d,j}=struct('steps',[a.tau1_step a.tau2_step],...
            'milliseconds',1000/1024*[a.tau1_step a.tau2_step]);
        count=count+height(a);
    end
end
assert(count==386,'历史六条边界应共386点。');
fprintf('图14：历史六条边界，共386点；本入口未计算闭环稳定域。\n');
end
