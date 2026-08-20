% =================================
% *      Define sampling rate     *
% =================================
% fs     = 4096;
% dt     = 1/fs;
delta  =  0.5;
alpha  =  0.25;

[a0,a1,a2,a3,a4,a5,a6,a7] = fcn_newmark_beta_const(delta,alpha,dt);

% ==========================
% *    Stiffness Matrix    *
% ==========================

KRrt = csvread("FE_Model/REF_SAP2000_Model/K_matrix.csv");
ndof = length(KRrt);


% ==========================
% *      Mass Matrix       *
% ==========================
MRrt = csvread("FE_Model/REF_SAP2000_Model/M_matrix.csv");


% ==========================
% *     Damping Matrix     *
% ==========================
wi = 13.493;    % [rad/sec]
wj = 165.125;   % [rad/sec]
damping = 0.05; % [Percent]

Art = (1/2)*[(1/wi) wi;(1/wj) wj];
Brt = [damping; damping];
alphas = inv(Art) * Brt;

CRrt =  alphas(1)*MRrt + alphas(2)*KRrt;

% ==========================
% *      Active DOF        *
% ==========================
% load readmatrix_output_reference.mat


l     = zeros(ndof,1);
l_dof = readmatrix("FE_Model/REF_SAP2000_Model/Joint_DOF.xlsx");
for i = 1:length(l_dof(:,2))
    u_active = l_dof(i,2);
    if u_active ~= 0
	    l(u_active) = 1;
    end 
end 


% ==========================
% *  Memory for vectors    *
% ==========================
F       =  zeros(ndof,1);
U0      =  zeros(ndof,1);
Vel0    =  zeros(ndof,1);
Acc0    =  zeros(ndof,1);
U1      =  zeros(ndof,1);
Vel1    =  zeros(ndof,1);
Acc1    =  zeros(ndof,1);
Ag      =  zeros(ndof,1);
Rbar    =  zeros(ndof,1);

% =============================
% * Compute Dynamic Stiffness *
% =============================
Kbar=(KRrt+(a0*MRrt)+(a1*CRrt));
Kbar_inv = inv(Kbar);
