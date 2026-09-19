%                            Stiffness & Mass Matrix Extractor

%       This program will run on Matlab version 2017 or greater..
%       It is particulary made for 2d and 3d frames,trusses etc. 

% How to use this

% Before running this program, your analysis must be run on Sap2000.
% Also before running the analysis, go to set analysis option in the Analyze context menu option,
% in the solver option, select advance solver and select the case for which you need stiffness and 
% mass matrix. 

% Now you can run this program to extract the matrices for your case.
% When you run this program, it will ask for the file, select any one of 
% your sap2000 project file,since Sap generate many files for 
% a single project, this program will be able to accept any one of these files.
% As output, It will give you three matrices for your analysis case.

% 1. Joint_DOF -   A matrix showing joint number and DOFs number as assigned by Etabs,Sap. 
% 2. K Matrix -   Stiffness Matrix of your analysis problem
% 3. M Matrix -   Mass Matrix of your analysis problem


clear all
clc

[file,selpath] = uigetfile('*.*');

Del=extractAfter(file,'.');
Del=strcat('.',Del);
ProjectName=erase(file,Del);

ProjectNameK=strcat(ProjectName,'.TXK');
filenameK =strcat(selpath,ProjectNameK);
opts = detectImportOptions(filenameK,'FileType','text');
ProjectNameM=strcat(ProjectName,'.TXM');
filenameM =strcat(selpath,ProjectNameM);
T = readtable(filenameK,opts);
A=table2array(T);
RowNo=max(A(:,1));
ColNo=max(A(:,2));
K=zeros(RowNo,ColNo);
for i=1:size(A,1)
    K(A(i,1),A(i,2))=A(i,3);
    K(A(i,2),A(i,1))=A(i,3);
end


opts = detectImportOptions(filenameM,'FileType','text');
T = readtable(filenameM,opts);
A=table2array(T);
RowNo=max(A(:,1));
ColNo=max(A(:,2));
M=zeros(RowNo,ColNo);
for i=1:size(A,1)
    M(A(i,1),A(i,2))=A(i,3);
    M(A(i,2),A(i,1))=A(i,3);
end

ProjectNameE=strcat(ProjectName,'.TXE');
filenameE =strcat(selpath,ProjectNameE);

fid = fopen(filenameE);
temp = textscan(fid,'%d','Headerlines',1,'delimiter','\n');
fclose(fid);
Result=double(reshape(temp{1},7,[])');
C=Result(:,2:end);
maxDOF=max(C(:));
for i=1:max(C(:))
    [row,col]=find(C==i);
    JointNo=Result(row,1);
if col==1
    DOF='UX';
elseif col==2
    DOF='UY';
elseif col==3
    DOF='UZ';
elseif col==4
    DOF='RX';
elseif col==5
    DOF='RY';
elseif col==6
    DOF='RZ';
end
H=strcat('Joint-',num2str(JointNo),',',DOF);
Title{i}=H;
end
Joint_DOF = table(Result(:,1),Result(:,2),Result(:,3),Result(:,4),Result(:,5),Result(:,6),Result(:,7),'VariableNames',{'Joint','Ux','Uy','Uz','Rx','Ry','Rz'})
format short
%K=array2table(K,'VariableNames',Title,'RowNames',Title')
%M=array2table(M,'VariableNames',Title,'RowNames',Title')


writetable(Joint_DOF,"Joint_DOF.xlsx")
writematrix(K,"K_matrix.csv")
writematrix(M,"M_matrix.csv")

