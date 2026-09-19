clear;
taskTemp=fileparts(mfilename('fullpath'));
projectRoot=fileparts(fileparts(taskTemp));
packageDir=fullfile(fileparts(projectRoot),'260817','elsevier_review_v2_20260907');
expected=load(fullfile(taskTemp,'new_figure_check.mat'));
checked=0;maximumDifference=0;driftAll=[];
calculated44=nan(44,1);
for division=1:2
    designation=repmat('I',1,division);
    model=load(fullfile(packageDir,'supplementary_data',['division_' designation '_matrices.mat']));
    M=model.M_full;Gamma=zeros(15,1);Gamma([1 6 11])=1;
    order=[model.master_dofs(:);model.slave_dofs(:)];
    for method={'full','guyan','cb'}
        name=method{1};[V,D]=eig(model.(['K_' name]),model.(['M_' name]));
        [lambda,ix]=sort(diag(D));V=V(:,ix);frequency=sqrt(lambda)/(2*pi);
        if ~strcmp(name,'full')
            physical=zeros(15,size(V,2));physical(order,:)=model.(['T_' name])*V;V=physical;
        end
        modalShare=zeros(15,1);participation=zeros(5,1);perMode=zeros(15,5);
        for k=1:5
            phi=V(:,k)/sqrt(V(:,k)'*M*V(:,k));
            participation(k)=(phi'*M*Gamma)^2;
            for j=1:15
                perMode(j,k)=M(j,j)*phi(j)^2;
            end
            perMode(:,k)=perMode(:,k)/sum(perMode(:,k));
        end
        modalShare=perMode*(participation/sum(participation));
        if strcmp(name,'full')
            fullFrequency=frequency;fullShape=V;fullShare=modalShare;
        else
            methodIndex=1+strcmp(name,'cb');master=model.master_dofs(:);
            for modeIndex=1:2
                index=(division-1)*8+(modeIndex-1)*4+methodIndex;
                calculated44(index)=abs(frequency(modeIndex)-fullFrequency(modeIndex))/fullFrequency(modeIndex)*100;
                va=fullShape(master,modeIndex);vb=V(master,modeIndex);
                calculated44(index+2)=(va'*vb)^2/((va'*va)*(vb'*vb));
            end
            if division==1,acts=[1 6];else,acts=[1 11];end
            calculated44(40+(division-1)*2+methodIndex)=sum((modalShare(acts)-fullShare(acts))./fullShare(acts));
        end
        df=max(abs(frequency-expected.(sprintf('freq_%d_%s',division,name))(:)));
        ds=max(abs(modalShare-expected.(sprintf('share_%d_%s',division,name))(:)));
        maximumDifference=max([maximumDifference,df,ds]);checked=checked+numel(frequency)+15;
        assert(df<1e-8 && ds<1e-10,'Modal comparison failed');
    end
end
middle=[];
for excitation={'eq','chirp'}
    label=excitation{1};
    for division=1:2
        response=readmatrix(fullfile(packageDir,'supplementary_data',sprintf('response_division_%d_%s.csv',division,label)));
        response=response(all(isfinite(response),2),:);t=response(:,1);
        if strcmp(label,'eq'),rowList=1;else,rowList=2:6;end
        edges=[0.1,1.9,3.5,5.4,8.1,10];
        for tableRow=rowList
            if tableRow==1,lo=0;hi=40;else,lo=(edges(tableRow-1)-.1)/.2475;hi=(edges(tableRow)-.1)/.2475;end
            times=[lo;t(t>lo & t<hi);hi];ref=response(:,2);
            for methodIndex=1:2
                error=interp1(t,response(:,2+methodIndex)-ref,times,'linear');
                calculated44(16+(tableRow-1)*4+(division-1)*2+methodIndex)=sqrt(trapz(times,error.^2)/(hi-lo))/(max(ref)-min(ref))*100;
            end
        end
        for method=0:2
            x=response(:,[2 5 8]+method);
            drift=(x-[zeros(size(x,1),1),x(:,1:2)])/635*100;
            driftAll=[driftAll;max(abs(drift),[],1)'];
        end
        if division==2
            ref=response(:,5);ranges=max(ref)-min(ref);
            for column=[6 7]
                error=response(:,column)-ref;
                value=sqrt(trapz(t,error.*error)/40)/ranges*100;
                middle=[middle;value];
            end
        end
    end
end
df=max(abs(driftAll-expected.drift_values(:)));assert(df<1e-10,'Drift comparison failed');
maximumDifference=max(maximumDifference,df);checked=checked+numel(driftAll);
json=jsondecode(fileread(fullfile(packageDir,'revision_evidence','data','new_figure_metrics.json')));
middleExpected=[json.middle_eq_nrmse_percent(:);json.middle_chirp_nrmse_percent(:)];
df=max(abs(middle-middleExpected));assert(df<1e-10,'Middle-storey comparison failed');
maximumDifference=max(maximumDifference,df);checked=checked+numel(middle);
audit=jsondecode(fileread(fullfile(packageDir,'revision_evidence','data','table345_verified_values.json')));
expected44=[audit.rows.recomputed]';
df=max(abs(calculated44-expected44));assert(all(isfinite(calculated44)) && df<1e-8,'44 table values failed');
maximumDifference=max(maximumDifference,df);checked=checked+44;
result=struct('status','PASS','checked_numeric_values',checked,'maximum_absolute_difference',maximumDifference,'frequency_tolerance',1e-8,'response_share_drift_tolerance',1e-10,'matlab_release',version('-release'));
result.table_values_checked=44;result.table_values_maximum_absolute_difference=df;
fid=fopen(fullfile(packageDir,'revision_evidence','data','new_metrics_matlab_validation.json'),'w','n','UTF-8');fprintf(fid,'%s',jsonencode(result,PrettyPrint=true));fclose(fid);
disp(jsonencode(result));
