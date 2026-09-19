function VERIFY_CASES(workdir)
% Independent MATLAB second-order force balance on six complete EQ records.
S=load(fullfile(workdir,'matlab_case_inputs.mat')); cases=S.cases;
rows=struct([]);
for j=1:numel(cases)
 c=cases{j};r=size(c.M,1);hist=zeros(r,c.n+2);y=zeros(numel(c.u)+1,6);
 Mh=c.M+c.h*c.C/2+c.h^2*c.K/4;
 R=chol(Mh); % independent factorization; no Python state matrix is used
 for k=1:numel(c.u)
  v=(hist(:,1)-hist(:,2))/c.h; vd=(hist(:,c.n+1)-hist(:,c.n+2))/c.h;
  force=c.f*c.u(k)-c.C0*v-c.K0*hist(:,1)-c.Uc*c.S*vd-c.Uk*c.S*hist(:,c.n+1);
  aa=R\(R'\force); q=hist(:,1)+c.h*v+c.h^2*aa;
  hist(:,2:end)=hist(:,1:end-1);hist(:,1)=q;
  y(k+1,:)=[c.Yn*hist(:,1);c.Y0*hist(:,1)+c.Jd*c.S*hist(:,c.n+1)]';
 end
 residual=norm(y-c.expected,'fro')/norm(c.expected,'fro');
 rows(j).name=c.name;rows(j).residual=residual;rows(j).tolerance=1e-9;rows(j).passed=residual<=1e-9;
 assert(rows(j).passed,'Independent complete-record recurrence differs');
 fprintf('%s %.16g\n',c.name,residual);
end
fid=fopen(fullfile(workdir,'matlab_case_validation.json'),'w');fwrite(fid,jsonencode(struct('status','PASS','checks',rows)),'char');fclose(fid);
end
