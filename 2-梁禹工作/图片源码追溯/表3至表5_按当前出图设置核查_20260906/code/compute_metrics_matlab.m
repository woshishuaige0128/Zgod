function compute_metrics_matlab()
% Independent implementation of the manuscript metrics, using fresh snapshots.
root=fileparts(fileparts(mfilename('fullpath')));
cfg=jsondecode(fileread(fullfile(root,'evidence','runtime_derivation.json')));
D=cell(1,4);
for j=1:4
    D{j}=load(fullfile(cfg(j).runtime,'输出','本轮计算数据','audit_snapshot.mat'));
end
values=zeros(44,1);count=0;energy=zeros(2,2);
for division=1:2
    d=D{division};M=d.M_full;master=d.master_dofs(:);order=[master;d.slave_dofs(:)];
    [f,V]=modal_solution(M,d.K_full);
    E0=modal_share(V,M);
    if division==1,acts=[1,6];else,acts=[1,11];end
    ferror=zeros(2,2);mac=zeros(2,2);
    for method=1:2
        if method==1
            [fr,Vr]=modal_solution(d.M_guyan,d.K_guyan);T=d.T_guyan;
        else
            [fr,Vr]=modal_solution(d.M_cb,d.K_cb);T=d.T_cb;
        end
        full=zeros(15,numel(fr));full(order,:)=T*Vr;
        Er=modal_share(full,M);
        energy(division,method)=sum((Er(acts)-E0(acts))./E0(acts));
        for i=1:2
            a=V(master,i);b=Vr(1:numel(master),i);
            ferror(i,method)=abs(fr(i)-f(i))/f(i)*100;
            mac(i,method)=(a'*b)^2/((a'*a)*(b'*b));
        end
    end
    for i=1:2
        values(count+(1:4))=[ferror(i,1);ferror(i,2);mac(i,1);mac(i,2)];count=count+4;
    end
end
edges=[0.1,1.9,3.5,5.4,8.1,10];
for row=0:5
    for division=1:2
        if row==0,d=D{division};t0=0;t1=40;
        else,d=D{division+2};t0=(edges(row)-.1)/.2475;t1=(edges(row+1)-.1)/.2475;end
        a=d.computed_matrix;t=a(:,1);ref=a(:,2);
        tt=[t0;t(t>t0 & t<t1);t1];den=max(ref)-min(ref);
        for method=1:2
            err=interp1(t,ref-a(:,method+2),tt,'linear');
            count=count+1;values(count)=100*sqrt(trapz(tt,err.^2)/(t1-t0))/den;
        end
    end
end
for division=1:2
    for method=1:2,count=count+1;values(count)=energy(division,method);end
end
assert(count==44 && all(isfinite(values)));
writematrix([(1:44)',values],fullfile(root,'results','MATLAB独立复算_44项.csv'));
fprintf('MATLAB_INDEPENDENT_44_METRICS=PASS\n');
end

function [f,V]=modal_solution(M,K)
[V,L]=eig(K,M);[lam,ix]=sort(real(diag(L)));V=real(V(:,ix));
assert(all(lam>0));f=sqrt(lam)/(2*pi);
for j=1:numel(lam)
    residual=norm(K*V(:,j)-lam(j)*M*V(:,j))/((norm(K)+abs(lam(j))*norm(M))*norm(V(:,j)));
    assert(residual<1e-12);
end
end

function E=modal_share(V,M)
V=V(:,1:5);
for i=1:5,V(:,i)=V(:,i)/sqrt(V(:,i)'*M*V(:,i));end
Gamma=zeros(15,1);Gamma([1,6,11])=1;
gamma=zeros(5,1);coordinate=zeros(15,5);
for i=1:5
    gamma(i)=(V(:,i)'*M*Gamma)/(V(:,i)'*M*V(:,i));
    coordinate(:,i)=diag(M).*V(:,i).^2;
    coordinate(:,i)=coordinate(:,i)/sum(coordinate(:,i));
end
p=gamma.^2/sum(gamma.^2);E=coordinate*p;
assert(abs(sum(E)-1)<1e-12);
end
