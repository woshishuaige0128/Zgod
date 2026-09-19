% Static extraction from luxvjie_cb_3.mlx
% Source SHA-256: 39E05BDFF4DC6C7AFB775AC136A8948FEADAE6F29A70D2017DD82E75A261EF6B
% No MATLAB execution was performed.

%% CODE_CELL_C001
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

Kmm = KRrt(index3,index3);
Kms = KRrt(index3,index4);
Ksm = KRrt(index4,index3);
Kss = KRrt(index4,index4);

Mmm = MRrt(index3,index3);
Mms = MRrt(index3,index4);
Msm = MRrt(index4,index3);
Mss = MRrt(index4,index4);

Cmm = CRrt(index3,index3);
Cms = CRrt(index3,index4);
Csm = CRrt(index4,index3);
Css = CRrt(index4,index4);

% Step 2: 计算静力部分
Tg = -Kss \ Ksm;

N_r = 3;
% Step 3: 固定主自由度的特征值问题（提取前 N_r 个模态）
[Phi, D] = eigs(Kss, Mss, N_r, 'SM');  % N_r 是你要保留的模态数
% 通常可取 N_r = 3–6，看频率变化而定

% Step 4: 构造变换矩阵 Tcb
Tcb = [eye(length(index3)), zeros(length(index3), N_r);
       Tg,                   Phi];

% Step 5: 缩聚后的矩阵
MRcb = Tcb' * MRrt([index3, index4], [index3, index4]) * Tcb;
CRcb = Tcb' * CRrt([index3, index4], [index3, index4]) * Tcb;
KRcb = Tcb' * KRrt([index3, index4], [index3, index4]) * Tcb;

%% CODE_CELL_C002
%K2_1 = zeros(15);
%K2_1(3:4,3) = [Kb(3,3);Kb(6,3)];
%K2_2 = zeros(15);
%K2_2(6:8,6) = [2*Kc(1,1);Kc(3,1);Kc(3,1)];
%K2_2(11:13,6) = [2*Kc(4,1);Kc(6,1);Kc(6,1)];

%K1 = KRrt-K2_1-K2_2;

%% CODE_CELL_C003
dt = 1/1024;
al = (4*MRren+2*dt*CRren+dt^2*KRren)\MRren*4;
al = diag(diag(al));

%% CODE_CELL_C004
% 2. 选择矩阵 S: 6x15
S = zeros(2, 5);

% 定义映射：小矩阵第1-3行 → 大矩阵第1-3行
% 小矩阵第4-6行 → 大矩阵第6-8行
row_map = [1 2];

for i = 1:2
    S(i, row_map(i)) = 1;
end

l = 0;
j = 0;

syms z

%for l = 1:20
%    for j = 1:30

%% CODE_CELL_C005
M = MRren;
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

%% CODE_CELL_C006
C2 = zeros(8);
K2 = zeros(8);
C2([1,2],[1,2]) = CPren;
K2([1,2],[1,2]) = KPren;
C1 = CRcb-C2;
K1 = KRcb-K2;

al = (4*MRcb+2*dt*CRcb+dt^2*KRcb)\MRcb*4;

%% CODE_CELL_C007
stab = zeros(20);
for l = 0:20
%l =5;
for j = 0:20
%j = 25;
%l = 0
%j = 0
%z=tf('z',dt);
syms z
%l = 19;
%j = 5;
H = sym(zeros(8,8));
H(1,1) = z^(-l);
H(2,2) = z^(-j);

%syms z
G = (z-1)^2/z/dt^2*MRcb/al+(z-1)/z/dt*C1+K1+...
    H*((z-1)/z/dt*C2+K2);
%G = (z-1)^2/z/dt^2*MNren/al+(z-1)/z/dt*CNren+KNren+...
%    S'*H*((z-1)/z/dt*CPren+KPren+(z-1)/z/dt*Kd_ctrl+Kp_ctrl)*S;
det_G = det(G);
Gcls_zero = vpa(solve(det_G == 0, z));
s = max(abs(Gcls_zero))
stab(l+1,j+1) = s;
end
end
