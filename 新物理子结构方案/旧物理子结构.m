% Benchmark Problem in Real-Time Hybrid Simulation
% Physical Plant: 1st-Story; 1st-Bay

%%% PHYSICAL PLANT MODEL DESCRIPTION

%                                   ^ Y                              
%         .-----------.             |
%        6|         7 |             |
%         |           |             |
%         |           |             -------> X
%       2 ^         3 ^ 
%     -------------------
%     ---Ground Motion---   (shaking direction: <-->)
%     -------------------

%  GLOBAL DOF'S: 
%  1) x_27    2) @_29     3) @_21
%
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

E = 200e9;                          % steel modulus of elasticity (Pa)
rho = 785e3;                       % steel density (kg/m^3)

KP 	= zeros(3,3);                   % Initialize stiffness matrix
MP 	= zeros(3,3);                   % Initialize mass matrix
CP  = zeros(3,3);                   % Initialize damping matrix

%%% MASS MATRIX

mass_b = rho*Ab*Lb;                 % Total Beam Element Mass [kg]
mass_c = rho*Ac*Lc;                 % Total Beam Column Mass [kg]

% Lumped mass matrix
M1 = mass_b + mass_c;
M2 = (mass_b/2)*(Lb.^2)/12 +(mass_c/2)*(Lc.^2)/12;
MP = diag([M1 M2 M2]);


%%% STIFFNESS MATRIX

% Plane Beam-Column Element Stiffness Matrix
KP = [2*(3*Ic*E/(Lc^3))         -3*E*Ic/(Lc^2)              -3*E*Ic/(Lc^2);
     -3*E*Ic/(Lc^2)             (3*E*Ic/Lc + 4*E*Ib/Lb)     -2*E*Ib/Lb;
     -3*E*Ic/(Lc^2)             -2*E*Ib/Lb                  (3*E*Ic/Lc + 4*E*Ib/Lb)]; 


%%% DAMPING MATRIX

% Initialize damping matrix
C = zeros(3);

% Rayleigh Damping Method
[V,D]=eig(KP,MP);               % Eigenvectors and Eigenvalues
w1 = sqrt(D(1,1));              % Frequencies (rad/s)
w2 = sqrt(D(3,3));
damping = 0.05;                 % Damping Percentage [5%]

Art = (1/2)*[(1/w1) w1;(1/w2) w2];
Brt = [damping; damping];
alphas = inv(Art) * Brt;

CP =  alphas(1)*MP + alphas(2)*KP;
[V3,D3] = eig(KP,MP)
