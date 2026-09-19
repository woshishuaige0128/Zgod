% 图2-9：按 KPrt/CPrt/MPrt 参数语义定位并只读导出原 SLX 反力子系统。
% 不以易漂移的“Computation编号”定位；关闭模型时显式禁止保存。

codeDir = fileparts(mfilename('fullpath'));
chapterDir = fileparts(codeDir);
sourceModel = fullfile(chapterDir, '原始来源副本', 'lvxvjie_guyan_2_readonly.slx');
if ~isfile(sourceModel)
    error('缺少只读模型副本: %s', sourceModel);
end

handle = load_system(sourceModel);
sourceName = get_param(handle, 'Name');
try
    % 论文用子系统被保存在注释分支中，必须显式纳入 IncludeCommented；仍只读。
    candidates = find_system(sourceName, 'SearchDepth', 1, 'IncludeCommented', 'on', ...
        'BlockType', 'SubSystem');
    matched = {};
    for k = 1:numel(candidates)
        gains = find_system(candidates{k}, 'SearchDepth', 1, 'IncludeCommented', 'on', ...
            'BlockType', 'Gain');
        values = cell(size(gains));
        for j = 1:numel(gains)
            values{j} = get_param(gains{j}, 'Gain');
        end
        if all(ismember({'KPrt', 'CPrt', 'MPrt'}, values))
            matched{end + 1} = candidates{k}; %#ok<SAGROW>
        end
    end
    if numel(matched) ~= 1
        error('KPrt/CPrt/MPrt 子系统匹配数不是1: %d', numel(matched));
    end
    fprintf('图2-9语义匹配子系统: %s, SID=%s\n', ...
        strrep(matched{1}, newline, '<NL>'), get_param(matched{1}, 'SID'));
    % 该论文用分支在当前文件中被标记为 Commented=on。仅在内存中恢复显示，
    % 使 Gain 图标显示 KPrt/CPrt/MPrt；close_system(...,0) 保证不写回源 SLX。
    set_param(matched{1}, 'Commented', 'off');
    % 当前 MATLAB 版本在直接打印旧版 SLX 时不显示 Gain 参数图标文字。
    % 仅在内存中将块显示名设为其原始 Gain 参数，确保输出保留 KPrt/CPrt/MPrt 语义。
    semanticGains = find_system(matched{1}, 'SearchDepth', 1, 'BlockType', 'Gain');
    for j = 1:numel(semanticGains)
        gainValue = get_param(semanticGains{j}, 'Gain');
        set_param(semanticGains{j}, 'Name', [gainValue '*uvec'], 'ShowName', 'on', ...
            'HideAutomaticName', 'off', 'NamePlacement', 'alternate');
    end
    set_param(matched{1}, 'ZoomFactor', 'FitSystem');
    print(['-s' matched{1}], '-dpdf', '-bestfit', ...
        fullfile(chapterDir, 'PDF结果', '图2-9_物理子结构反力计算.pdf'));
    print(['-s' matched{1}], '-dpng', '-r600', ...
        fullfile(chapterDir, 'PNG结果', '图2-9_物理子结构反力计算.png'));
catch ME
    if bdIsLoaded(sourceName)
        close_system(sourceName, 0);
    end
    rethrow(ME);
end
if bdIsLoaded(sourceName)
    close_system(sourceName, 0);
end
