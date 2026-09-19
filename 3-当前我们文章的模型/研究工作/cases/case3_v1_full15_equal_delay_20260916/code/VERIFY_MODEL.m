function VERIFY_MODEL(inputfile,outputfile)
% Independent force-balance implementation; no Python state matrix is reused.
data=load(inputfile);fields=fieldnames(data);checks=struct('name',{},'residual',{},'tolerance',{},'passed',{});
for j=1:numel(fields)
    field=fields{j};
    if ~endsWith(field,'_history'),continue;end
    tag=extractBefore(field,strlength(field)-7); % strip '_history'
    tag=char(tag);r=size(data.([tag '_M']),1);h=1/1024;n=double(data.([tag '_n']));
    M=data.([tag '_M']);C=data.([tag '_C']);K=data.([tag '_K']);
    C0=data.([tag '_C0']);K0=data.([tag '_K0']);Uc=data.([tag '_Uc']);Uk=data.([tag '_Uk']);
    S=data.([tag '_S']);f=data.([tag '_f']);Yn=data.([tag '_Yn']);Y0=data.([tag '_Y0']);Jd=data.([tag '_Jd']);
    Mh=M+h*C/2+h^2*K/4;old=data.(field);u=data.([tag '_u']);N=numel(u);y=zeros(N+1,6);
    for t=1:N+1
        y(t,:)=[Yn*old(1,:)';Y0*old(1,:)'+Jd*S*old(n+1,:)']';
        if t>N,break;end
        v=(old(1,:)-old(2,:))'/h;vd=(old(n+1,:)-old(n+2,:))'/h;
        req=f*u(t)-C0*v-K0*old(1,:)'-Uc*S*vd-Uk*S*old(n+1,:)';
        anew=Mh\req;qnew=old(1,:)'+h*v+h^2*anew;
        old=[qnew';old(1:end-1,:)];
    end
    expected=data.([tag '_y']);v=norm(y-expected,'fro')/norm(expected,'fro');
    checks(end+1)=struct('name',[tag '_independent_MATLAB_response'],'residual',v,'tolerance',1e-9,'passed',v<=1e-9);
    % Separate coefficient assembly and projection to the port-history space.
    Ah=zeros(r*(n+2));coeff=zeros(r,r,n+2);
    coeff(:,:,1)=2*Mh-h*C0-h^2*K0;coeff(:,:,2)=-Mh+h*C0;
    coeff(:,:,n+1)=coeff(:,:,n+1)-h*Uc*S-h^2*Uk*S;
    coeff(:,:,n+2)=coeff(:,:,n+2)+h*Uc*S;
    for k=1:n+2,Ah(1:r,(k-1)*r+1:k*r)=Mh\coeff(:,:,k);end
    Ah(r+1:end,1:end-r)=eye(r*(n+1));J=eye(2*r);
    for k=1:n,J=blkdiag(J,S);end
    target=J*Ah;value=norm(data.([tag '_A'])*J-target,'fro')/norm(target,'fro');
    checks(end+1)=struct('name',[tag '_MATLAB_history_matrix'],'residual',value,'tolerance',1e-10,'passed',value<=1e-10);
end
result=struct('status','PASS','count',numel(checks),'maximum_residual',max([checks.residual]),'checks',checks);
if ~all([checks.passed]),result.status='FAIL';end
fid=fopen(outputfile,'w','n','UTF-8');fprintf(fid,'%s',jsonencode(result,PrettyPrint=true));fclose(fid);
fprintf('%s %d checks maximum %.17g\n',result.status,result.count,result.maximum_residual);
assert(all([checks.passed]),'Independent MATLAB verification failed');
end
