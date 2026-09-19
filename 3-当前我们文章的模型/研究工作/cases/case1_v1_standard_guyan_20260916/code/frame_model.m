function frame = frame_model()
% 从几何与实际质量参数装配完整框架；以下计算保持已核验的算序。
% x: horizontal displacement
% @: rotation around axis perpendicular to x-y 

% Assumptions: - Vertical Displacements are ignored 
%              - Horizontal displacement are the same at each MRF node
%%% MATERIAL PROPERTIES
Lb = 762/1000;                      % Beam length (m)
Lc = 635/1000;                      % Column length (m)
Ic = 2.520*(25.4/1000)^4;           % 2nd Moment of Area x column (m^4)
Ib = 0.6132*(25.4/1000)^4;          % 2nd Moment of Area x beam (m^4)
Ac = 1.670*(25.4/1000)^2;           % Cross sectional Area column (m^2)
Ab = 0.947*(25.4/1000)^2;           % Cross sectional Area beam (m^2)

E = 206e9;                          % steel modulus of elasticity (Pa)
rho = 785e3.*1.9;                   % 实际质量参数1491500 kg/m^3，等于7850的190倍；沿用来源值

%%% MASS MATRIX

mass_b = rho*Ab*Lb;                 % Total Beam Element Mass [kg]
mass_c = rho*Ac*Lc;                 % Total Beam Column Mass [kg]

% Lumped mass matrix
M1 = 3*mass_b + 4*mass_c;
M2 = (mass_b/2)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
M3 = (mass_b)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
MRrt = diag([M1 M2 M3 M3 M2 M1 M2 M3 M3 M2 M1 M2 M3 M3 M2]);


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
fre = diag(sqrt(D)/(2*pi));
w1 = sqrt(D(1,1));             % First natural frequency (rad/s)
w2 = sqrt(D(2,2));             % Second natural frequency (rad/s)
damping = 0.05;                % Damping ratio (5%)

% Construct Rayleigh damping coefficients
Art = (1/2) * [(1/w1) w1; (1/w2) w2];
Brt = [damping; damping];
alphas = Art \ Brt;            % Solve for alpha and beta

% Compute damping matrix
CRrt = alphas(1) * MRrt + alphas(2) * KRrt;
frame=struct("M",MRrt,"C",CRrt,"K",KRrt,"frequency_hz",fre,"rayleigh",alphas,"rho_model",rho,"height_mm",Lc*1000,"span_m",Lb,"area_beam",Ab,"area_column",Ac,"inertia_beam",Ib,"inertia_column",Ic,"E",E);
end
