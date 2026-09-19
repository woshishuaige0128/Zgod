load('EQ.mat')
dt=1/1024;
index3 = [1,4];
index4 = [2,3,5,6];

Mmn = MPrt(index3,index3);
Mmsn = MPrt(index3,index4);

Cmn = CPrt(index3,index3);
Cmsn = CPrt(index3,index4);

Kmn = KPrt(index3,index3);
Kmsn = KPrt(index3,index4);
Ksn = KPrt(index4,index4);
Ksmn = KPrt(index4,index3);

KPren = (Kmn-Kmsn*(Ksn\Ksmn));
MPren = (Mmn-Mmsn*(Ksn\Ksmn));
CPren = (Cmn-Cmsn*(Ksn\Ksmn));

index3 = [1,6,4,9,11];
index4 = [3,5,7,8,10,12,13,14,15];

Mmn = MNrt(index3,index3);
Mmsn = MNrt(index3,index4);

Cmn = CNrt(index3,index3);
Cmsn = CNrt(index3,index4);

Kmn = KNrt(index3,index3);
Kmsn = KNrt(index3,index4);
Ksn = KNrt(index4,index4);
Ksmn = KNrt(index4,index3);

KNren = (Kmn-Kmsn*(Ksn\Ksmn));
MNren = (Mmn-Mmsn*(Ksn\Ksmn));
CNren = (Cmn-Cmsn*(Ksn\Ksmn));

index3 = [1,6,4,9,11];
index4 = [2,3,5,7,8,10,12,13,14,15];

Mmn = MRrt(index3,index3);
Mmsn = MRrt(index3,index4);

Cmn = CRrt(index3,index3);
Cmsn = CRrt(index3,index4);

Kmn = KRrt(index3,index3);
Kmsn = KRrt(index3,index4);
Ksn = KRrt(index4,index4);
Ksmn = KRrt(index4,index3);

KRren = (Kmn-Kmsn*(Ksn\Ksmn));
MRren = (Mmn-Mmsn*(Ksn\Ksmn));
CRren = (Cmn-Cmsn*(Ksn\Ksmn));
%M = sym([m1,0;0,m2]);
%C1 = sym([c1,-c2;0,c2]);
%C2 = sym([c2,0;-c2,0]);
%C = C1+C2;
%K1 = sym([k1,-k2;0,k2]);
%K2 = sym([k2,0;-k2,0]);
%K = K1+K2;
%Kd = sym([0,0;0,kd2]);
%Kp = sym([0,0;0,kp2]);
%al = (4*M+2*dt*C+dt^2*K)\M*4;

M = MRren;
%C = CRren;
K = KRren;

% Rayleigh Damping Method
[V, D] = eig(K, M);          % Eigenvectors and Eigenvalues
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
CRren = alphas(1) * M + alphas(2) * K;

M = MPren;
%C = CRren;
K = KPren;

% Rayleigh Damping Method
[V, D] = eig(K, M);          % Eigenvectors and Eigenvalues
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
CPren = alphas(1) * M + alphas(2) * K;

C2 = zeros(5);
K2 = zeros(5);
C2([1,2],[1,2]) = CPren;
K2([1,2],[1,2]) = KPren;
C1 = CRren-C2;
K1 = KRren-K2;

al = (4*MRren+2*dt*CRren+dt^2*KRren)\MRren*4;

z=tf('z',dt);
l = 14;
j = 29;
H = tf(zeros(5,5));
H(1,1) = z^(-l);
H(2,2) = z^(-j);

%syms z
G = ((z-1)^2/z/dt^2*MRren/al+(z-1)/z/dt*C1+K1+...
    H*((z-1)/z/dt*C2+K2)...
    +S'*((z-1)/z/dt*Kd_ctrl+Kp_ctrl)*S)\eye(5);
%    S'*H*((z-1)/z/dt*CPren+KPren+(z-1)/z/dt*Kd_ctrl+Kp_ctrl)*S;
%G = ((z-1)^2/z/dt^2*MRren/al+(z-1)/z/dt*C+K)\eye(11);
Gss = ss(G);