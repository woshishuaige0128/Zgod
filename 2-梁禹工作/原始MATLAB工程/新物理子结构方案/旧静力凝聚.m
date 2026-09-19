

%%% PHYSICAL PLANT MODEL DESCRIPTION
%
%         ^ Y
%         |
%         |
%                               
%         .-----------O<|             
%       2 |         1 |             
%         |           |              
%         |           |             
%         .           . -------> X
%       3 A         4 A 
%     -------------------
%     ///////////////////
%     ...Ground Motion...   (shaking direction: <-->)
%     ...................
%
%  ***** 1,2,3,4 are node labels ******
%  Note: Node 1 is the interface node
%
%  Boundary conditions at nodes 3 and 4 (frame base): pinned connections
%
%  GLOBAL DOF'S: 
%  1) X_1_2   2)@_1    3)@_2   4) @_3    5) @_4
%
%  X_n: horizontal displacement of node 'n'
%  @_n: rotation around axis perpendicular to X-Y of node 'n'
%
%****** ASSUMPTION: Axial deformations are neglected *******
%       ----------


%%% MATERIAL PROPERTIES

Lb = 762/1000;                          % Beam length (m)
Lc = 641.35/1000;                       % Column length (m)
tuningF_beam = 1;    
tuningF_col = 0.7;     
Ic = 2.520*(25.4/1000)^4*tuningF_col;   % 2nd Moment of Area x column (m^4)
Ib = 4.21372e-7*tuningF_beam;           % 2nd Moment of Area x beam (m^4)
Ac = 1.670*(25.4/1000)^2;               % Cross sectional Area column (m^2)
Ab = 7.56e-4;                           % Cross sectional Area beam (m^2)
E = 200E9;                              % steel modulus of elasticity (Pa)
rho = 7.85e3;                           % steel density (kg/m^3)

% Local Stiffness matrices (columns and beam):

%      ^ y'
%      |
%      |
%      | 
%   (1) ____________________ (2) ......> x'
%         (beam or column)
%
% Local Stiffness matrix - Columns:

%         x'_1      y'_1          @z'_1         x'_2        y'_2            @z'_2
kc = [Ac*E/Lc       0              0         -Ac*E/Lc    0              0           ;
       0        12*E*Ic/Lc^3   6*E*Ic/Lc^2    0         -12*E*Ic/Lc^3   6*E*Ic/Lc^2 ;
       0        6*E*Ic/Lc^2    4*E*Ic/Lc      0         -6*E*Ic/Lc^2    2*E*Ic/Lc   ;
      -Ac*E/Lc      0              0         Ac*E/Lc     0              0           ;
       0        -12*E*Ic/Lc^3  -6*E*Ic/Lc^2   0         12*E*Ic/Lc^3    -6*E*Ic/Lc^2;
       0        6*E*Ic/Lc^2    2*E*Ic/Lc      0         -6*E*Ic/Lc^2    4*E*Ic/Lc]  ;
   
% Local Stiffness matrix - beam:

%       x'_1        y'_1          @z'_1          x'_2        y'_2           @z'_2
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

% Transformation matrices:     
     
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

% Tc(1,1) = 0; Tc(3,3)= 0;
   
Kc = Tc'*kc*Tc;         %Global stiffness matrix of columns
Kb = Tb'*kb*Tb;         %Global stiffness matrix of the beam

% Global stiffness matrix of the frame:
%
% %    X_1        @_1                @_2             @_3        @_4
% % ---------------------------------------------------------------------
K = [Kc(4,4)*2   Kc(4,6)           Kc(4,6)          Kc(4,3)    Kc(4,3);
     Kc(6,4)     Kc(6,6)+Kb(6,6)   Kb(6,3)          0          Kc(6,3);
     Kc(6,4)     Kb(3,6)           Kc(6,6)+Kb(3,3)  Kc(6,3)    0      ;
     Kc(3,4)     0                 Kc(3,6)          Kc(3,3)    0      ;
     Kc(3,4)     Kc(3,6)           0                0          Kc(3,3);
     ];


ForcePhyFrame = [-2e4 0 0 0 0]';
x = inv(K)*ForcePhyFrame;

% Lumped Mass matrix
mass_b = rho*Ab*Lb;                 % Total Beam Element Mass [kg]
mass_c = rho*Ac*Lc;                 % Total Beam Element Mass [kg]

% Mass at node (1) and (2):
M1x = (mass_b + mass_c*2)/2*1.1;
M12z = (mass_b/2*Lb^2 + mass_c/2*Lc^2)/3*1.1;
M34z = mass_c/2*Lc^2/3*1.1;

M = diag([M1x M12z M12z M34z M34z]);

% Damping matrix
C = zeros(size(M,1));
etha = 0.05;
zetas = etha*(ones(1,size(M,1)));
[fi, w_cuad] = eig(M\K);                   % Eigenvectors and Eigenvalues
[frecs, ind]= sort(sqrt(diag(w_cuad)));    % Frequencies (rad/s)
frecs = diag(round(100*frecs)/100);
fnn = frecs/2/pi;                          % Frequencies (Hz)
fi = fi(:,ind');
Tn = diag(2*pi./frecs);

Mm = diag(fi'*M*fi);

for i = 1:size(M,1)
    cc = M*(2*zetas(i)*frecs(i,i)*fi(:,i)*fi(:,i)'/Mm(i))*M;
    C = cc+C;
end

K_phys_5dof = K;
C_phys_5dof = C;
M_phys_5dof = M;
[V1,D] = eig(K_phys_5dof,M_phys_5dof);
%% Simplified 2-DOF model (Static condensation)
% ------------------------
                            %  _       _
Ktt = K(1:2,1:2);           % | Ktt Kto |         
Kto = K(1:2,3:end);         % |_Kot Koo_|
Koo = K(3:end,3:end);       
Kot = K(3:end,1:2); 

% Condensation:
Kred = K(1:2,1:2) - K(1:2,3:end)*inv(K(3:end,3:end))*K(3:end,1:2);
K = Kred;
        
% Lumped Mass matrix
mass_b = rho*Ab*Lb;                 % Total Beam Element Mass [kg]
mass_c = rho*Ac*Lc;                 % Total Beam Element Mass [kg]

% Mass at node (1) and (2):
M1x = (mass_b + mass_c*2)/2;
M12z = (mass_b/2*Lb^2 + mass_c/2*Lc^2)/3;
M34z = mass_c/2*Lc^2/3;

M = diag([M1x M12z M12z M34z M34z]);
M = M(1:2,1:2);

% Damping matrix
C = zeros(size(M,1)); 
zetas = 0.05*(ones(1,size(M,1)));
[fi, w_cuad] = eig(M\K);                   % Eigenvectors and Eigenvalues
[frecs, ind]= sort(sqrt(diag(w_cuad)));    % Frequencies (rad/s)
frecs = diag(round(100*frecs)/100);
fnn = frecs/2/pi;                          % Frequencies (Hz)
fi = fi(:,ind');
Tn = diag(2*pi./frecs);

Mm = diag(fi'*M*fi);

for i = 1:size(M,1)
    cc = M*(2*zetas(i)*frecs(i,i)*fi(:,i)*fi(:,i)'/Mm(i))*M;
    C = cc+C;
end

% Simplified 2-DOF frame model
K_phys_2dof = K;
C_phys_2dof = C;
M_phys_2dof = M;
[V2,D] = eig(K_phys_2dof,M_phys_2dof);

%clear AA_phy BB_phy CC_phy DD_phy M C K Kb Kc kb kc cc Kred n iota Mi zetas ...
%       fi w_cuad frecs ind fnn Tn xc x ForcePhyFrame M1x M12z M34z mass_b mass_c Tc Tb ...
%       theta_c theta_b Ab Ac E i Ib Ic Lb Lc rho Mm SS_physicalFrame2 SS_physicalFrame5



