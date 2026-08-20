
% ====================================================
% *      Define an Ideal Physical Substructure       *
% ====================================================

build_physical_ideal

% ====================================================
% *    Stiffness Matrix of Numerical Substructure    *
% ====================================================

% K_Numerical  = K_Reference - K_Physical

KNrt = csvread("FE_Model/REF_SAP2000_Model/K_matrix.csv");
KNrt(27,27) = KNrt(27,27) - KP(1,1);
KNrt(27,29) = KNrt(27,29) - KP(1,2);
KNrt(27,21) = KNrt(27,21) - KP(1,3);
KNrt(29,27) = KNrt(29,27) - KP(2,1);
KNrt(29,29) = KNrt(29,29) - KP(2,2);
KNrt(29,21) = KNrt(29,21) - KP(2,3);
KNrt(21,27) = KNrt(21,27) - KP(3,1);
KNrt(21,29) = KNrt(21,29) - KP(3,2);
KNrt(21,21) = KNrt(21,21) - KP(3,3);
ndof = length(KNrt);

% ====================================================
% *      Mass Matrix of Numerical Substructure       *
% ====================================================

% M_Numerical  = M_Reference - M_Physical

MNrt = csvread("FE_Model/REF_SAP2000_Model/M_matrix.csv");
MP(2,2)=0;
MP(3,3)=0;
MNrt(27,27) = MNrt(27,27) - MP(1,1);

% ====================================================
% *     Damping Matrix of Numerical Substructure     *
% ====================================================

% C_Numerical  = C_Reference - C_Physical

CNrt = CRrt;
CNrt(27,27) = CNrt(27,27) - CP(1,1);
CNrt(27,29) = CNrt(27,29) - CP(1,2);
CNrt(27,21) = CNrt(27,21) - CP(1,3);
CNrt(29,27) = CNrt(29,27) - CP(2,1);
CNrt(29,29) = CNrt(29,29) - CP(2,2);
CNrt(29,21) = CNrt(29,21) - CP(2,3);
CNrt(21,27) = CNrt(21,27) - CP(3,1);
CNrt(21,29) = CNrt(21,29) - CP(3,2);
CNrt(21,21) = CNrt(21,21) - CP(3,3);

% ====================================================
% *                    Active DOF                    *
% ====================================================

% load readmatrix_output_numerical.mat

lN     = zeros(ndof,1);
l_dof = readmatrix("FE_Model/REF_SAP2000_Model/Joint_DOF.xlsx");
for i = 1:length(l_dof(:,2))
    u_active = l_dof(i,2);
    if u_active ~= 0
	    lN(u_active) = 1;
    end 
end 


% ====================================================
% *                 Memory for vectors               *
% ====================================================
FN       =  zeros(ndof,1);
UN0      =  zeros(ndof,1);
VelN0    =  zeros(ndof,1);
AccN0    =  zeros(ndof,1);
UN1      =  zeros(ndof,1);
VelN1    =  zeros(ndof,1);
AccN1    =  zeros(ndof,1);
AgN      =  zeros(ndof,1);
RNbar    =  zeros(ndof,1);

% ====================================================
% *             Compute Dynamic Stiffness            *
% ====================================================

delta  =  0.5;
alpha  =  0.25;
[a0,a1,a2,a3,a4,a5,a6,a7] = fcn_newmark_beta_const(delta,alpha,dt);

KNbar=(KNrt+(a0*MNrt)+(a1*CNrt));
KNbar_inv = inv(KNbar);
