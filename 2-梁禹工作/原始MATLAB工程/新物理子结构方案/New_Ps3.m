%给出物理子结构定位
locate2 = [1,2,3,6,7,8,11,12,13];

KPrt = [2*Kc(4,4)+2*Kc(1,1)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	2*Kc(1,4)	Kc(1,6)	Kc(1,6)	0	0	0
Kc(6,4)+Kc(3,1)	Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	Kc(3,4)	Kc(3,6)	0	0	0	0
Kc(6,4)+Kc(3,1)	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)+Kc(3,3)	Kc(3,4)	0	Kc(3,6)	0	0	0
2*Kc(4,1)	Kc(4,3)	Kc(4,3)	2*Kc(4,4)+2*Kc(1,1)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	2*Kc(1,4)	Kc(1,6)	Kc(1,6)
Kc(6,1)	Kc(6,3)	0	Kc(6,4)+Kc(3,1)	Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	Kc(3,4)	Kc(3,6)	0
Kc(6,1)	0	Kc(6,3)	Kc(6,4)+Kc(3,1)	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)+Kc(3,3)	Kc(3,4)	0	Kc(3,6)
0	0	0	2*Kc(4,1)	Kc(4,3)	Kc(4,3)	2*Kc(4,4)	Kc(4,6)	Kc(4,6)
0	0	0	Kc(6,1)	Kc(6,3)	0	Kc(6,4)	Kb(3,3)+Kc(6,6)	Kb(3,6)
0	0	0	Kc(6,1)	0	Kc(6,3)	Kc(6,4)	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)
];
%KPrt = zeros(6,6);
%KPrt([1,4],[1,4]) = KRrt([1,6],[1,6]).*0.5.*0.962;
%KPrt([1,4],[1,4]) = KRrt([1,6],[1,6]).*0.5;

M4 = mass_b + 2*mass_c;
M2 = (mass_b/2)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
%M3 = (mass_b)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
MNP = diag([M4 M2 M2 1e-5 1e-5 M4 M2 M2 1e-5 1e-5 1e-5 1e-5 1e-5 1e-5 1e-5]);
%MPrt = zeros(6,6);
MPrt = diag([M4 M2 M2 M4 M2 M2 M4 M2 M2]);
%MPrt = MPrt.*1e-2;


%CPrt = CRrt(locate2,locate2);
%CPrt = zeros(6,6);
%CPrt([1,4],[1,4]) = CRrt([1,6],[1,6])/2;
%CRrtdel = CRrt(3,3)-CRrt(2,2);
%CPrt(3,3) = CRrt(3,3)-CRrtdel;
%CPrt(6,6) = CRrt(8,8)-CRrtdel;

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

KPbar=(KPrt+(a0*MPrt)+(a1*CPrt));
KPbar_inv = inv(KPbar);

lP = zeros(6,1);
lP(1,1) = 1;
lP(4,1) = 1;
RPbar = zeros(6,1);
AgP = zeros(6,1);
AgP(1,1) = 1;
AgP(4,1) = 1;