%给出数值子结构定位
locate = [1,3,4,5,6,7,8,9,10,11,12,13,14,15];
%给出物理子结构定位
locate2 = [1,2,3,6,7,8];
locate3 = zeros(15,6);
locate3(locate2,1:6) = eye(6);

KNrt = [2*Kc(4,4)+2*Kc(1,1)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	2*Kc(1,4)	Kc(1,6)	Kc(1,6)	0	0	0	0	0;
Kc(6,4)+Kc(3,1)	Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	Kc(3,4)	Kc(3,6)	0	0	0	0	0	0;
Kc(6,4)+Kc(3,1)	Kb(6,3)	Kb(6,6)+Kc(6,6)+Kc(3,3)	Kc(3,4)	0	Kc(3,6)	0	0	0	0	0;
2*Kc(4,1)	Kc(4,3)	Kc(4,3)	2*Kc(4,4)+2*Kc(1,1)	Kc(4,6)+Kc(1,3)	Kc(4,6)+Kc(1,3)	2*Kc(1,4)	0	0	Kc(1,6)	Kc(1,6);
Kc(6,1)	Kc(6,3)	0	Kc(6,4)+Kc(3,1)	Kb(3,3)+Kc(6,6)+Kc(3,3)	Kb(3,6)	Kc(3,4)	0	0	Kc(3,6)	0;
Kc(6,1)	0	Kc(6,3)	Kc(6,4)+Kc(3,1)	Kb(6,3)	Kb(6,6)+Kc(6,6)+Kc(3,3)	Kc(3,4)	0	0	0	Kc(3,6);
0	0	0	2*Kc(4,1)	Kc(4,3)	Kc(4,3)	4*Kc(4,4)	Kc(4,6)	Kc(4,6)	Kc(4,6)	Kc(4,6);
0	0	0	0	0	0	Kc(6,4)	Kb(3,3)+Kc(6,6)	Kb(3,6)	0	0;
0	0	0	0	0	0	Kc(6,4)	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)	Kb(3,6)	0;
0	0	0	Kc(6,1)	Kc(6,3)	0	Kc(6,4)	0	Kb(6,3)	Kb(6,6)+Kb(3,3)+Kc(6,6)	Kb(3,6);
0	0	0	Kc(6,1)	0	Kc(6,3)	Kc(6,4)	0	0	Kb(6,3)	Kb(6,6)+Kc(6,6);
];
%KNrt(locate2,locate2) = KRrt(locate2,locate2)-KPrt;
%KNrt([1,6],[1,6]) = KRrt([1,6],[1,6])/2;
%KNrt = KNrt(locate,locate);

M5 = 2*mass_b + 2*mass_c;
M6 = (mass_b/2)*(Lb.^2)/12;
M2 = (mass_b/2)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
M3 = (mass_b)*(Lb.^2)/12+(mass_c)*(Lc.^2)/12;
MNrt = diag([M4 M2 M2 M4 M2 M2 M1 M2 M3 M3 M2]);

% Rayleigh Damping Method
[V, D] = eig(KNrt, MNrt);          % Eigenvectors and Eigenvalues
[~, idx] = sort(diag(D));      % Sort eigenvalues in ascending order
V = V(:, idx);
D = D(idx, idx);

w1 = sqrt(D(1,1));             % First natural frequency (rad/s)
w2 = sqrt(D(2,2));             % Second natural frequency (rad/s)
damping = 0.1;                % Damping ratio (5%)

% Construct Rayleigh damping coefficients
Art = (1/2) * [(1/w1) w1; (1/w2) w2];
Brt = [damping; damping];
alphas = Art \ Brt;            % Solve for alpha and beta

% Compute damping matrix
CNrt = alphas(1) * MNrt + alphas(2) * KNrt;

KNbar=(KNrt+(a0*MNrt)+(a1*CNrt));
KNbar_inv = inv(KNbar);

AgN = zeros(15,1);
lN = zeros(15,1);
lN(1,1) = 1;
lN(6,1) = 1;
lN(11,1) = 1;
RNbar = zeros(15,1);
FN = zeros(15,1);