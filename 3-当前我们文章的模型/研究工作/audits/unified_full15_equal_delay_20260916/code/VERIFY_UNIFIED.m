function VERIFY_UNIFIED(outputFile)
% Independent MATLAB bases and full-coordinate history implementation.
out=fileparts(fileparts(mfilename('fullpath')));
src=fullfile(out,'sources'); a=load(fullfile(src,'audit_matrices.mat'));
b=load(fullfile(src,'calculation.mat')); f=b.bundle.frame;
old=load(fullfile(src,'model_and_cases.mat')); gain=old.Full15.gain;
py=load(fullfile(out,'results','operators.mat')); h=1/1024;
values=[];names={}; rows=struct([]);
for d=1:2
    if d==1
        p=[1 2 3 6 7 8]; n=[1 3 4 5 6 7 8 9 10 11 12 13 14 15];
        ports=[1 6]; retained=[1 6 11 4 9 14]; nr0=retained;
        count=9; pairs=[0 0;1 1;3 1;5 1];
    else
        p=[1 2 3 6 7 8 11 12 13];n=[1 3 4 5 6 8 9 10 11 13 14 15];
        ports=[1 11];retained=[1 11 4 9 14];nr0=[1 11 6 4 9 14];
        count=10;pairs=[0 0;1 1;2 2;3 3];
    end
    E=eye(15);select=E(p,:);S=E(ports,:);B=S';L=E([1 6 11],:);
    Cp=select'*a.(sprintf('div%d_C_P',d))*select;
    Kp=select'*a.(sprintf('div%d_K_P',d))*select;
    F=struct('M',f.M,'C',f.C,'K',f.K,'C0',f.C-Cp*B*S,'K0',f.K-Kp*B*S,...
        'Uc',Cp*B+B*gain(:,3:4),'Uk',Kp*B+B*gain(:,1:2),'R',S,...
        'f',f.M*sum(L,1)','Y0',L*(eye(15)-B*S),'Yd',L*B*S);
    for key={'M','C','K','C0','K0','Uc','Uk','R','f','Y0','Yd'}
        k=key{1};add(sprintf('d%d_source_%s',d,k),F.(k),py.(sprintf('d%d_%s',d,k)));
    end
    for modes=[0 3 count]
        T=cb(f.K,f.M,retained,modes);tag=sprintf('d%d_m%d',d,modes);
        verify(T,tag,F,T'*f.M*T);
    end
    common=intersect(p,n);nr=[nr0,setdiff(common,nr0,'stable')];pr=[ports,setdiff(common,ports,'stable')];
    MN=a.(sprintf('div%d_M_N',d));KN=a.(sprintf('div%d_K_N',d));
    MP=a.(sprintf('div%d_M_P',d));KP=a.(sprintf('div%d_K_P',d));
    [~,irN]=ismember(nr,n);[~,irP]=ismember(pr,p);
    icN=setdiff(1:numel(n),irN,'stable');icP=setdiff(1:numel(p),irP,'stable');
    rows(d).division=d;rows(d).numerical_internal_min_mass=min(eig(MN(icN,icN)));
    rows(d).physical_internal_min_mass=min(eig(MP(icP,icP)));
    assert(rows(d).numerical_internal_min_mass>0 && rows(d).physical_internal_min_mass>0);
    for k=1:size(pairs,1)
        mN=pairs(k,1);mP=pairs(k,2);tn=cb(KN,MN,irN,mN);tp=cb(KP,MP,irP,mP);
        r=numel(nr)+mN+mP;en=[eye(numel(nr)+mN),zeros(numel(nr)+mN,mP)];
        ep=zeros(numel(pr)+mP,r);
        for j=1:numel(pr),ep(j,find(nr==pr(j)))=1;end
        ep(numel(pr)+1:end,numel(nr)+mN+1:end)=eye(mP);
        RN=tn*en;RP=tp*ep;T=zeros(15,r);T(n,:)=RN;
        for j=1:numel(p),if ~ismember(p(j),n),T(p(j),:)=RP(j,:);end,end
        tag=sprintf('interface_d%d_N%d_P%d',d,mN,mP);
        verify(T,tag,F,RN'*MN*RN+RP'*MP*RP);
    end
end
result=struct('status','PASS','checks',numel(values),'tolerance',1e-10,...
    'max_normalized_residual',max(values),'divisions',rows,...
    'names',{names},'residuals',values,'new_time_histories',0,'new_pole_scans',0);
fid=fopen(outputFile,'w','n','UTF-8');assert(fid>0);fprintf(fid,'%s',jsonencode(result));fclose(fid);
fprintf('MATLAB_PASS %d checks, max residual %.16g\n',numel(values),max(values));

    function add(name,A,B)
        v=norm(A-B,'fro')/max(norm(B,'fro'),1e-30);
        assert(v<=1e-10,'%s residual %.16g',name,v);names{end+1}=name;values(end+1)=v;
    end
    function verify(T,tag,F,localM)
        TP=py.([tag '_T']);r=size(T,2);R=project(F,T);
        add([tag '_basis_subspace'],T*pinv(T),TP*pinv(TP));
        add([tag '_local_mass'],R.M,localM);
        add([tag '_algorithm_mass'],mass(R,h),T'*mass(F,h)*T);
        for ns=[0 1 4 5]
            Ar=fullhistory(R,ns,h);Af=fullhistory(F,ns,h);
            if r==15
                Q=kron(eye(max(2,ns+2)),T);
                add(sprintf('%s_n%d_similarity',tag,ns),Af*Q,Q*Ar);
            end
            for freq=[.7 3 9 20]
                z=exp(2i*pi*freq*h);Zf=characteristic(F,z,ns,h);Zr=characteristic(R,z,ns,h);
                add(sprintf('%s_n%d_f%g_Z',tag,ns,freq),Zr,T'*Zf*T);
                if r==15
                    add(sprintf('%s_n%d_f%g_recovery',tag,ns,freq),T*(Zr\R.f),Zf\F.f);
                    add(sprintf('%s_n%d_f%g_output',tag,ns,freq),...
                        (R.Y0+z^(-ns)*R.Yd)*(Zr\R.f),(F.Y0+z^(-ns)*F.Yd)*(Zf\F.f));
                end
            end
        end
    end
end

function T=cb(K,M,r,count)
c=setdiff(1:size(K,1),r,'stable');T=zeros(size(K,1),numel(r)+count);
T(r,1:numel(r))=eye(numel(r));T(c,1:numel(r))=-K(c,c)\K(c,r);
[V,D]=eig(K(c,c),M(c,c));[~,ix]=sort(real(diag(D)));V=real(V(:,ix));
for j=1:size(V,2),V(:,j)=V(:,j)/sqrt(V(:,j)'*M(c,c)*V(:,j));end
T(c,numel(r)+1:end)=V(:,1:count);
end
function R=project(F,T)
R=F;for key={'M','C','K','C0','K0'},k=key{1};R.(k)=T'*F.(k)*T;end
R.Uc=T'*F.Uc;R.Uk=T'*F.Uk;R.R=F.R*T;R.f=T'*F.f;R.Y0=F.Y0*T;R.Yd=F.Yd*T;
end
function Mh=mass(F,h),Mh=F.M+h/2*F.C+h*h/4*F.K;end
function Z=characteristic(F,z,n,h)
Z=(z-2+1/z)/h^2*mass(F,h)+(1-1/z)/h*F.C0+F.K0+...
    z^(-n)*((1-1/z)/h*F.Uc+F.Uk)*F.R;
end
function A=fullhistory(F,n,h)
r=size(F.M,1);nblocks=max(2,n+2);A=zeros(r*nblocks);Mh=mass(F,h);
A(1:r,1:r)=2*eye(r)-Mh\(h*F.C0+h*h*F.K0);
A(1:r,r+1:2*r)=-eye(r)+Mh\(h*F.C0);
A(r+1:end,1:end-r)=eye(r*(nblocks-1));
A(1:r,n*r+1:(n+1)*r)=A(1:r,n*r+1:(n+1)*r)-Mh\((h*F.Uc+h*h*F.Uk)*F.R);
A(1:r,(n+1)*r+1:(n+2)*r)=A(1:r,(n+1)*r+1:(n+2)*r)+Mh\(h*F.Uc*F.R);
end
