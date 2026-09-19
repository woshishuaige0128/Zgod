function rths_status(demo)
% 只保存简洁的状态与计时，不把工作区或旧参考数组写入状态文件。
data=rmfield(demo,intersect(fieldnames(demo),{'timer','stage'}));
f=fopen(fullfile(demo.output,'运行状态.json'),'w','n','UTF-8');
assert(f>=0,'无法写入本次运行目录。');cleanup=onCleanup(@()fclose(f));
fprintf(f,'%s',jsonencode(data,'PrettyPrint',true));
end
