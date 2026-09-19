%%% MATERIAL PROPERTIES
Lb = 762/1000; % Beam length (m)
Lc = 635/1000; % Column length (m)
Ic = 2.520*(25.4/1000)^4; % 2nd Moment of Area x column (m^4)
Ib = 0.6132*(25.4/1000)^4; % 2nd Moment of Area x beam (m^4)
Ac = 1.670*(25.4/1000)^2; % Cross sectional Area column (m^2)
Ab = 0.947*(25.4/1000)^2; % Cross sectional Area beam (m^2)

E = 206e9; % steel modulus of elasticity (Pa)
rho = 785e3.*1.9; % steel density (kg/m^3)

KRrt = zeros(15,15); % Initialize stiffness matrix
MRrt = zeros(15,15); % Initialize mass matrix
CRrt = zeros(15,15); % Initialize damping matrix

%%% MASS MATRIX

mass_b = rho*Ab*Lb; % Total Beam Element Mass [kg]
mass_c = rho*Ac*Lc; % Total Beam Column Mass [kg]

% Lumped mass matrix
M1 = 3*mass_b + 4*mass_c;
%M1 = mass_b + mass_c;
M2 = (mass_b/2)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
M3 = (mass_b)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
MRrt = diag([M1 M2 M3 M3 M2 M1 M2 M3 M3 M2 M1 M2 M3 M3 M2]);


%%% STIFFNESS MATRIX

% Plane Beam-Column Element Stiffness Matrix
kc = [Ac*E/Lc 0 0 -Ac*E/Lc 0 0 ;
0 12*E*Ic/Lc^3 6*E*Ic/Lc^2 0 -12*E*Ic/Lc^3 6*E*Ic/Lc^2 ;
0 6*E*Ic/Lc^2 4*E*Ic/Lc 0 -6*E*Ic/Lc^2 2*E*Ic/Lc ;
-Ac*E/Lc 0 0 Ac*E/Lc 0 0 ;
0 -12*E*Ic/Lc^3 -6*E*Ic/Lc^2 0 12*E*Ic/Lc^3 -6*E*Ic/Lc^2;
0 6*E*Ic/Lc^2 2*E*Ic/Lc 0 -6*E*Ic/Lc^2 4*E*Ic/Lc] ;
kb = [Ab*E/Lb 0 0 -Ab*E/Lb 0 0 ;
0 12*E*Ib/Lb^3 6*E*Ib/Lb^2 0 -12*E*Ib/Lb^3 6*E*Ib/Lb^2 ;
0 6*E*Ib/Lb^2 4*E*Ib/Lb 0 -6*E*Ib/Lb^2 2*E*Ib/Lb ;
-Ab*E/Lb 0 0 Ab*E/Lb 0 0 ;
0 -12*E*Ib/Lb^3 -6*E*Ib/Lb^2 0 12*E*Ib/Lb^3 -6*E*Ib/Lb^2;
0 6*E*Ib/Lb^2 2*E*Ib/Lb 0 -6*E*Ib/Lb^2 4*E*Ib/Lb] ;
% Neglecting axial deformations:

kb(1,1:end) = zeros(1,size(kb,1));
kb(4,1:end) = zeros(1,size(kb,1));
kb(1:end,1) = zeros(1,size(kb,1));
kb(1:end,4) = zeros(1,size(kb,1));

kc(1,1:end) = zeros(1,size(kc,1));
kc(4,1:end) = zeros(1,size(kc,1));
kc(1:end,1) = zeros(1,size(kc,1));
kc(1:end,4) = zeros(1,size(kc,1));
%%% Transformation matrices
theta_c = pi/2;
theta_b = 0;

Tc = [cos(theta_c) sin(theta_c) 0 0 0 0 ;
-sin(theta_c) cos(theta_c) 0 0 0 0 ;
0 0 1 0 0 0 ;
0 0 0 cos(theta_c) sin(theta_c) 0 ; 
0 0 0 -sin(theta_c) cos(theta_c) 0 ;
0 0 0 0 0 1 ];
Tb = [cos(theta_b) sin(theta_b) 0 0 0 0 ;
-sin(theta_b) cos(theta_b) 0 0 0 0 ;
0 0 1 0 0 0 ;
0 0 0 cos(theta_b) sin(theta_b) 0 ; 
0 0 0 -sin(theta_b) cos(theta_b) 0 ;
0 0 0 0 0 1 ];

Kc = Tc'*kc*Tc; %Global stiffness matrix of columns
Kb = Tb'*kb*Tb; %Global stiffness matrix of the beam

%给出物理子结构定位
locate2 = [1,2,3,6,7,8];
tuning1 = 0.1;
KPrt = [2*Kc(4,4)+2*Kc(1,1) Kc(4,6)+Kc(1,3) Kc(4,6)+Kc(1,3) 2*Kc(1,4) Kc(1,6) Kc(1,6);
Kc(6,4)+Kc(3,1) Kb(3,3)+Kc(6,6)+Kc(3,3) Kb(3,6) Kc(3,4) Kc(3,6) 0;
Kc(6,4)+Kc(3,1) Kb(6,3) Kb(6,6)+Kc(6,6)+Kc(3,3) Kc(3,4) 0 Kc(3,6);
2*Kc(4,1) Kc(4,3) Kc(4,3) 2*Kc(4,4) Kc(4,6) Kc(4,6);
Kc(6,1) Kc(6,3) 0 Kc(6,4) Kb(3,3)+Kc(6,6) Kb(3,6);
Kc(6,1) 0 Kc(6,3) Kc(6,4) Kb(6,3) Kb(6,6)+Kc(6,6);
];

%KPrt = [4*Kc(4,4)+4*Kc(1,1) Kc(4,6)+Kc(1,3) Kc(4,6)+Kc(1,3) 4*Kc(1,4) Kc(1,6) Kc(1,6);
%Kc(6,4)+Kc(3,1) Kb(3,3)+Kc(6,6)+Kc(3,3) Kb(3,6) Kc(3,4) Kc(3,6) 0;
%Kc(6,4)+Kc(3,1) Kb(6,3) Kb(6,6)+Kb(3,3)+Kc(6,6)+Kc(3,3) Kc(3,4) 0 Kc(3,6);
%4*Kc(4,1) Kc(4,3) Kc(4,3) 4*Kc(4,4)+4*Kc(1,1) Kc(4,6)+Kc(1,3) Kc(4,6)+Kc(1,3);
%Kc(6,1) Kc(6,3) 0 Kc(6,4)+Kc(3,1) Kb(3,3)+Kc(6,6)+Kc(3,3) Kb(3,6);
%Kc(6,1) 0 Kc(6,3) Kc(6,4)+Kc(3,1) Kb(6,3) Kb(6,6)+Kb(3,3)+Kc(6,6)+Kc(3,3);
%];
%KPrt = zeros(6,6);
%KPrt([1,4],[1,4]) = KRrt([1,6],[1,6]).*0.5.*0.962;
%KPrt([1,4],[1,4]) = KRrt([1,6],[1,6]).*0.5;

M4 = mass_b + 2*mass_c;
M2 = (mass_b/2)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
%M3 = (mass_b)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
MPrt = diag([M4 M2 M2 M4 M2 M2]);
%MPrt = zeros(6,6);

% Rayleigh Damping Method
[V, D] = eig(KPrt, MPrt); % Eigenvectors and Eigenvalues
[~, idx] = sort(diag(D)); % Sort eigenvalues in ascending order
V = V(:, idx);
D = D(idx, idx);

w1 = sqrt(D(1,1)); % First natural frequency (rad/s)
w2 = sqrt(D(2,2)); % Second natural frequency (rad/s)
damping = 0.1; % Damping ratio (5%)

% Construct Rayleigh damping coefficients
Art = (1/2) * [(1/w1) w1; (1/w2) w2];
Brt = [damping; damping];
alphas = Art \ Brt; % Solve for alpha and beta

% Compute damping matrix
CPrt = alphas(1) * MPrt + alphas(2) * KPrt;

index1 = [1,4];
index2 = [2,3,5,6];
index3 = [1,6,11];
index4 = [2,3,4,5,7,8,9,10,12,13,14,15];
order = [index3,index4];

Mmn = MPrt(index1,index1);
Mmsn = MPrt(index1,index2);

Cmn = CPrt(index1,index1);
Cmsn = CPrt(index1,index2);

Kmn = KPrt(index1,index1);
Kmsn = KPrt(index1,index2);
Ksn = KPrt(index2,index2);
Ksmn = KPrt(index2,index1);

KRren = (Kmn-Kmsn*(Ksn\Ksmn));
MRren = (Mmn-Mmsn*(Ksn\Ksmn));
CRren = (Cmn-Cmsn*(Ksn\Ksmn));

I = eye(length(index1)); % 主自由度单位矩阵
T = [I; -Ksn\Ksmn]; % 拼接得到转换矩阵

Kss = KPrt(index2,index2);
Mss = MPrt(index2,index2);

% 固定边界模态分析
[phi_s, D] = eig(Kss, Mss);
omega = sqrt(diag(D));

r = 3; % 选取前3个模态
phi_s_r = phi_s(:,1:r);

Ksmn = KPrt(index2,index1);

n_mn = length(index1);
T_cb = [eye(n_mn), zeros(n_mn, r);
-Kss\Ksmn, phi_s_r];

% 组合主自由度和被缩聚自由度索引
idx_all = [index1, index2];

MR_cb = T_cb' * MPrt(idx_all, idx_all) * T_cb;
KR_cb = T_cb' * KPrt(idx_all, idx_all) * T_cb;
CR_cb = T_cb' * CPrt(idx_all, idx_all) * T_cb;
