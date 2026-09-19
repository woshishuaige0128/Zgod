function VERIFY_ALGEBRA(outputFile)
% Source matrix evaluation and independent congruence checks only. No sim.
root=fileparts(fileparts(mfilename('fullpath')));
A=load(fullfile(root,'results','audit_matrices.mat'));
B=load(fullfile(root,'sources','full_frame','calculation.mat'));
frame=B.bundle.frame;rows=struct([]);
for division=1:2
    sourcePath=fullfile(root,'sources','historical',sprintf('PDmonicanshu%d.m',division+1));
    sourceText=fileread(sourcePath);
    cut=regexp(sourceText,'(?m)^index1\s*=','once');
    assert(~isempty(cut),'Source prefix marker missing.');
    eval(sourceText(1:cut-1));
    prefix=sprintf('div%d_',division);J=A.([prefix 'J']);
    row.division=division;
    for entry={'M','C','K'}
        key=entry{1};target=frame.(key);
        row.([key '_join_residual'])=norm(J'*A.([prefix key '_U'])*J-target,'fro')/norm(target,'fro');
        assert(row.([key '_join_residual'])<1e-10);
    end
    row.source_mass_difference=norm(MPrt-A.([prefix 'M_P']),'fro')/norm(MPrt,'fro');
    row.source_stiffness_difference=norm(KPrt-A.([prefix 'K_P']),'fro')/norm(KPrt,'fro');
    row.source_damping_difference=norm(CPrt-A.([prefix 'C_P']),'fro')/norm(CPrt,'fro');
    row.stiffness_delta=KPrt-A.([prefix 'K_P']);
    assert(row.source_mass_difference<1e-10);
    if division==1,assert(row.source_stiffness_difference<1e-10);end
    rows=[rows;row];
end
delayRows=struct([]);W=A.delay_W;z=exp(2i*pi*9/1024);
for steps=[0,4]
    dx=eye(size(W))+(z^(-steps)-1)*A.delay_En;
    dq=eye(size(W))+(z^(-steps)-1)*A.delay_Eq;
    dr.delay_steps=steps;
    for entry={'C','K'}
        key=entry{1};physical=A.(['delay_' key 'p_natural']);
        left=W'*physical*W*dq;right=W'*physical*dx*W;
        dr.([key '_delay_projection_difference'])=norm(left-right,'fro')/norm(right,'fro');
        if steps==0,assert(dr.([key '_delay_projection_difference'])<1e-10);end
    end
    delayRows=[delayRows;dr];
end
save(outputFile,'rows','delayRows','-v7');
fprintf('ALGEBRA_SOURCE_CHECKS_PASS: two divisions; no time integrations.\n');
end
