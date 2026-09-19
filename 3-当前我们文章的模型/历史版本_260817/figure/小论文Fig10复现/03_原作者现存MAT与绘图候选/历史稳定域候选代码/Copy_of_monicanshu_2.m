dt = 1/1024;
%%% MATERIAL PROPERTIES
Lb = 762/1000;                      % Beam length (m)
Lc = 635/1000;                      % Column length (m)
Ic = 2.520*(25.4/1000)^4;           % 2nd Moment of Area x column (m^4)
Ib = 0.6132*(25.4/1000)^4;          % 2nd Moment of Area x beam (m^4)
Ac = 1.670*(25.4/1000)^2;           % Cross sectional Area column (m^2)
Ab = 0.947*(25.4/1000)^2;           % Cross sectional Area beam (m^2)

E = 206e9;                          % steel modulus of elasticity (Pa)
rho = 785e3.*1.9;                       % steel density (kg/m^3)

KRrt  = zeros(15,15);                   % Initialize stiffness matrix
MRrt  = zeros(15,15);                   % Initialize mass matrix
CRrt  = zeros(15,15);                   % Initialize damping matrix

%%% MASS MATRIX

mass_b = rho*Ab*Lb;                 % Total Beam Element Mass [kg]
mass_c = rho*Ac*Lc;                 % Total Beam Column Mass [kg]

% Lumped mass matrix
M1 = 3*mass_b + 4*mass_c;
%M1 = mass_b + mass_c;
M2 = mass_b*(Lb.^2)/3+mass_c*(Lc.^2)/3*2;
M3 = mass_b*(Lb.^2)/3*2+mass_c*(Lc.^2)/3*2;
M4 = mass_b*(Lb.^2)/3+mass_c*(Lc.^2)/3;
M5 = mass_b*(Lb.^2)/3*2+mass_c*(Lc.^2)/3;
MRrt = diag([M1 M2 M3 M3 M2 M1 M2 M3 M3 M2 M1 M4 M5 M5 M4]);

%%% STIFFNESS MATRIX

% Plane Beam-Column Element Stiffness Matrix
kc = [Ac*E/Lc       0              0         -Ac*E/Lc    0              0           ;
       0        12*E*Ic/Lc^3   6*E*Ic/Lc^2    0         -12*E*Ic/Lc^3   6*E*Ic/Lc^2 ;
       0        6*E*Ic/Lc^2    4*E*Ic/Lc      0         -6*E*Ic/Lc^2    2*E*Ic/Lc   ;
      -Ac*E/Lc      0              0         Ac*E/Lc     0              0           ;
       0        -12*E*Ic/Lc^3  -6*E*Ic/Lc^2   0         12*E*Ic/Lc^3    -6*E*Ic/Lc^2;
       0        6*E*Ic/Lc^2    2*E*Ic/Lc      0         -6*E*Ic/Lc^2    4*E*Ic/Lc]  ;
kb = [Ab*E/Lb       0              0         -Ab*E/Lb    0              0           ;
       0        12*E*Ib/Lb^3   6*E*Ib/Lb^2    0         -12*E*Ib/Lb^3   6*E*Ib/Lb^2 ;
       0        6*E*Ib/Lb^2    4*E*Ib/Lb      0         -6*E*Ib/Lb^2    2*E*Ib/Lb   ;
      -Ab*E/Lb      0              0         Ab*E/Lb     0              0           ;
       0        -12*E*Ib/Lb^3  -6*E*Ib/Lb^2   0         12*E*Ib/Lb^3    -6*E*Ib/Lb^2;
       0        6*E*Ib/Lb^2    2*E*Ib/Lb      0         -6*E*Ib/Lb^2    4*E*Ib/Lb]  ;
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

Tc = [cos(theta_c)   sin(theta_c)   0       0             0          0 ;
      -sin(theta_c)  cos(theta_c)   0       0             0          0 ;
       0                    0       1       0             0          0 ;
       0                    0       0   cos(theta_c)   sin(theta_c)  0 ;
       0                    0       0   -sin(theta_c)  cos(theta_c)  0 ;
       0                    0       0       0             0          1  ];

Tb = [cos(theta_b)   sin(theta_b)   0       0             0          0 ;
      -sin(theta_b)  cos(theta_b)   0       0             0          0 ;
       0                    0       1       0             0          0 ;
       0                    0       0   cos(theta_b)   sin(theta_b)  0 ;
       0                    0       0   -sin(theta_b)  cos(theta_b)  0 ;
       0                    0       0       0             0          1  ];

Kc = Tc'*kc*Tc;         %Global stiffness matrix of columns
Kb = Tb'*kb*Tb;         %Global stiffness matrix of the beam
KRrt = [4*Kc(4,4)+4*Kc(1,1)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	4*Kc(1,4)	Kc(1,6)	Kc(1,6)	Kc(1,6)	Kc(1,6)	0	0	0	0	0;
Kc(6,4)+Kc(3,1)	Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	0	0	Kc(3,4)	Kc(3,6)	0	0	0	0	0	0	0	0;
Kc(6,4)+Kc(3,1)	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	0	Kc(3,4)	0	Kc(3,6)	0	0	0	0	0	0	0;
Kc(6,4)+Kc(3,1)	0	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	Kc(3,4)	0	0	Kc(3,6)	0	0	0	0	0	0;
Kc(6,4)+Kc(3,1)	0	0	Kb(6,3)	Kb(6,6)+Kc(6,6)+Kc(3,3)	Kc(3,4)	0	0	0	Kc(3,6)	0	0	0	0	0;
4*Kc(4,1)	Kc(4,3)	Kc(4,3)	Kc(4,3)	Kc(4,3)	4*Kc(4,4)+4*Kc(1,1)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	4*Kc(1,4)	Kc(1,6)	Kc(1,6)	Kc(1,6)	Kc(1,6);
Kc(6,1)	Kc(6,3)	0	0	0	Kc(6,4)+Kc(3,1)	Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	0	0	Kc(3,4)	Kc(3,6)	0	0	0;
Kc(6,1)	0	Kc(6,3)	0	0	Kc(6,4)+Kc(3,1)	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	0	Kc(3,4)	0	Kc(3,6)	0	0;
Kc(6,1)	0	0	Kc(6,3)	0	Kc(6,4)+Kc(3,1)	0	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	Kc(3,4)	0	0	Kc(3,6)	0;
Kc(6,1)	0	0	0	Kc(6,3)	Kc(6,4)+Kc(3,1)	0	0	Kb(6,3)	Kb(6,6)+Kc(6,6)+Kc(3,3)	Kc(3,4)	0	0	0	Kc(3,6);
0	0	0	0	0	4*Kc(4,1)	Kc(4,3)	Kc(4,3)	Kc(4,3)	Kc(4,3)	4*Kc(4,4)	Kc(4,6)	Kc(4,6)	Kc(4,6)	Kc(4,6);
0	0	0	0	0	Kc(6,1)	Kc(6,3)	0	0	0	Kc(6,4)	Kb(3,3)+Kc(6,6)	Kb(3,6)	0	0;
0	0	0	0	0	Kc(6,1)	0	Kc(6,3)	0	0	Kc(6,4)	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)	Kb(3,6)	0;
0	0	0	0	0	Kc(6,1)	0	0	Kc(6,3)	0	Kc(6,4)	0	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)	Kb(3,6);
0	0	0	0	0	Kc(6,1)	0	0	0	Kc(6,3)	Kc(6,4)	0	0	Kb(6,3)	Kb(6,6)+Kc(6,6);
];

% Rayleigh Damping Method
[V, D] = eig(KRrt, MRrt);          % Eigenvectors and Eigenvalues
[~, idx] = sort(diag(D));      % Sort eigenvalues in ascending order
V = V(:, idx);
D = D(idx, idx);

w1 = sqrt(D(1,1));             % First natural frequency (rad/s)
w2 = sqrt(D(2,2));             % Second natural frequency (rad/s)
damping = 0.05;                % Damping ratio (5%)

% Construct Rayleigh damping coefficients
Art = (1/2) * [(1/w1) w1; (1/w2) w2];
Brt = [damping; damping];
alphas = Art \ Brt;            % Solve for alpha and beta

% Compute damping matrix
CRrt = alphas(1) * MRrt + alphas(2) * KRrt;

%给出物理子结构定位
locate2 = [1,2,3,6,7,8];
KPrt = [2*Kc(4,4)+2*Kc(1,1)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	2*Kc(1,4)	Kc(1,6)	Kc(1,6);
Kc(6,4)+Kc(3,1)	Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	Kc(3,4)	Kc(3,6)	0;
Kc(6,4)+Kc(3,1)	Kb(6,3)	Kb(6,6)+Kc(6,6)+Kc(3,3)	Kc(3,4)	0	Kc(3,6);
2*Kc(4,1)	Kc(4,3)	Kc(4,3)	2*Kc(4,4)	Kc(4,6)	Kc(4,6);
Kc(6,1)	Kc(6,3)	0	Kc(6,4)	Kb(3,3)+Kc(6,6)	Kb(3,6);
Kc(6,1)	0	Kc(6,3)	Kc(6,4)	Kb(6,3)	Kb(3,3)+Kc(6,6);
];

M6 = mass_b + 2*mass_c;
%M3 = (mass_b)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
MPrt = diag([M6 M2 M2 M6 M4 M4]);

% Rayleigh Damping Method
[V, D] = eig(KPrt, MPrt);          % Eigenvectors and Eigenvalues
[~, idx] = sort(diag(D));      % Sort eigenvalues in ascending order
V = V(:, idx);
D = D(idx, idx);

w1 = sqrt(D(1,1));             % First natural frequency (rad/s)
w2 = sqrt(D(2,2));             % Second natural frequency (rad/s)
damping = 0.05;                % Damping ratio (5%)

% Construct Rayleigh damping coefficients
Art = (1/2) * [(1/w1) w1; (1/w2) w2];
Brt = [damping; damping];
alphas = Art \ Brt;            % Solve for alpha and beta

% Compute damping matrix
CPrt = alphas(1) * MPrt + alphas(2) * KPrt;

KNrt = KRrt;
KNrt(locate2,locate2) = KRrt(locate2,locate2)-KPrt;

MNrt = MRrt;
MNrt(locate2,locate2) = MRrt(locate2,locate2)-MPrt;

CNrt = CRrt;
CNrt(locate2,locate2) = CRrt(locate2,locate2)-CPrt;

locate = [1,3,4,5,6,7,8,9,10,11,12,13,14,15];
KNrt_1 = KNrt(locate,locate);
MNrt_1 = MNrt(locate,locate);

% Rayleigh Damping Method
[V, D] = eig(KNrt_1, MNrt_1);          % Eigenvectors and Eigenvalues
[~, idx] = sort(diag(D));      % Sort eigenvalues in ascending order
V = V(:, idx);
D = D(idx, idx);

w1 = sqrt(D(1,1));             % First natural frequency (rad/s)
w2 = sqrt(D(2,2));             % Second natural frequency (rad/s)
damping = 0.05;                % Damping ratio (5%)

% Construct Rayleigh damping coefficients
Art = (1/2) * [(1/w1) w1; (1/w2) w2];
Brt = [damping; damping];
alphas = Art \ Brt;            % Solve for alpha and beta

% Compute damping matrix
CNrt_1 = alphas(1) * MNrt_1 + alphas(2) * KNrt_1;

s = tf('s');
%Gn_1 = (MNrt*s^2+CNrt*s+KNrt)\eye(15);
%Gn_2 = (MNrt_1*s^2+CNrt_1*s+KNrt_1)\eye(14);

ln = zeros(14,1);
ln(1) = 1;
ln(5) = 1;
ln(10) = 1;
MNrt_1*ln
n = size(MNrt_1,1);
A = [zeros(n) eye(n);
     -MNrt_1\KNrt_1, -MNrt_1\CNrt_1];
B = [zeros(n);
     MNrt_1\eye(n)];
C = [eye(n), zeros(n)];
D = zeros(n);

sys = ss(A, B, C, D);

MNrt_2 = MNrt(locate,locate);
CNrt_2 = CNrt(locate,locate);
KNrt_2 = KNrt(locate,locate);

n = size(MNrt_2,1);
A = [zeros(n) eye(n);
     -MNrt_2\KNrt_2, -MNrt_2\CNrt_2];
B = [zeros(n);
     MNrt_2\eye(n)];
C = [eye(n), zeros(n)];
D = zeros(n);

sys_1 = ss(A, B, C, D);

% 检查质量矩阵条件数
cond_M = cond(MNrt_1);
disp(['cond(M): ', num2str(cond_M)]);
% 检查A矩阵特征值
eig_A = eig(A);
disp('Max real part of eigenvalues of A:');
disp(max(real(eig_A)));

Klocate = selection_matrix(14,[1,0,2,5,6,7]);

M = MRrt;
C = CRrt;
K = KRrt;
n = size(M, 1);  % 自由度数

A = [zeros(n) eye(n);
     -M \ K  -M \ C];

B = [zeros(n);
     M \ eye(n)];

C = [eye(n), zeros(n)];
D = zeros(n, n);

G_1 = ss(A, B, C, D);
