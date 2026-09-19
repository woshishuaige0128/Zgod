function RUN_DELAY_RESPONSES(outputFolder,caseIndices)
% Independent MATLAB implementation of the manuscript CR velocity update.
% Zero initial conditions and zero negative-time displacement/velocity.
root=fileparts(fileparts(mfilename('fullpath')));
if nargin<1,outputFolder=fullfile(root,'results','matlab_run');end
if isfolder(outputFolder),error('Choose a new output directory.');end
mkdir(outputFolder);
D=load(fullfile(root,'results','model_and_cases.mat'));
if nargin<2,caseIndices=1:size(D.delays,1);end
names={'Full15','Uncondensed19','Guyan6','CB12'};inputs={'eq','chirp'};
h=D.dt;t=D.time(:);ns=numel(t);summary=[];
for id=caseIndices
 delays=double(D.delays(id,:));tag=sprintf('n%02d_%02d',delays(1),delays(2));
 for ie=1:2
  ag=D.(inputs{ie})(:);
  for im=1:4
   timer=tic;m=D.(names{im});m.force=m.force(:);n=size(m.M,1);
   Bcr=m.M+h/2*m.C+h*h/4*m.K;alpha=Bcr\m.M;
   C0=m.C;K0=m.K;Cl=cell(2,1);Kl=cell(2,1);
   for ell=1:2
    e=m.S(ell,:)';cp=m.Cp*e*e';kp=m.Kp*e*e';C0=C0-cp;K0=K0-kp;
    Cl{ell}=cp+e*m.gain(ell,3:4)*m.S;
    Kl{ell}=kp+e*m.gain(ell,1:2)*m.S;
   end
   q=zeros(ns,n);v=zeros(ns,n);accel=zeros(n,1);
   for k=1:ns-1
    force=m.force*ag(k)-C0*v(k,:)'-K0*q(k,:)';
    for ell=1:2
     lag=k-delays(ell);
     if lag>=1,force=force-Cl{ell}*v(lag,:)'-Kl{ell}*q(lag,:)';end
    end
    accel=m.M\force;
    v(k+1,:)=v(k,:)+(h*alpha*accel)';
    q(k+1,:)=q(k,:)+h*v(k+1,:);
   end
   numerical_mm=1000*q*m.Yn';physical_mm=1000*q*m.Yp';
   for ell=1:2
    active=q*m.S(ell,:)';delay=delays(ell);
    if delay>0,lagged=[zeros(delay,1);active(1:end-delay)];else,lagged=active;end
    physical_mm=physical_mm+1000*(lagged-active)*(m.Yp*m.S(ell,:)')';
   end
   assert(all(isfinite(q(:))));
   path=fullfile(outputFolder,[tag '_' inputs{ie} '_' names{im} '.mat']);
   save(path,'q','v','physical_mm','numerical_mm','-v7');
   seconds=toc(timer);summary=[summary;id,ie,im,seconds,max(abs(physical_mm(:)))]; %#ok<AGROW>
  end
 end
 fprintf('DELAY_COMPLETE=%s (%g,%g) ms\n',tag,delays*h*1000);
end
writematrix(summary,fullfile(outputFolder,'runtime_summary.csv'));
fprintf('ALL_DELAY_RESPONSES_COMPLETE=%d\n',size(summary,1));
end
