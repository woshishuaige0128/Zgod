% Static extraction from simulink_str_2.mlx
% Source SHA-256: A442C31EE6F7D86B16EDB8A2916E2194F87B10BC1069F98CF824AB29AA22CED9
% No MATLAB execution was performed.

%% CODE_CELL_C001
index1 = [1,4];
index2 = [2,3,5,6];
index3 = [1,7,13,4,10,16];
index4 = [2,3,6,8,9,12,14,15,18,5,11,17];
order = [index3,index4];

Mforce = MRrt(order,order);
Mf = diag([1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0].*Mforce);

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

I = eye(length(index3)); % 主自由度单位矩阵
T = [I; -Ksn\Ksmn];      % 拼接得到转换矩阵

%index3 = [1,7,13,4,10,16];
%index4 = [2,3,5,6,8,9,11,12,14,15,17,18];

%Kguyan = selection_matrix(6,[1,2]);

Kss = KRrt(index4,index4);
Mss = MRrt(index4,index4);

% 固定边界模态分析
[phi_s, D] = eig(Kss, Mss);
omega = sqrt(diag(D));

r = 6; % 选取前3个模态
phi_s_r = phi_s(:,1:r);

Ksmn = KRrt(index4,index3);

n_mn = length(index3);
T_cb = [eye(n_mn), zeros(n_mn, r);
        -Kss\Ksmn,   phi_s_r];

% 组合主自由度和被缩聚自由度索引
idx_all = [index3, index4];

MR_cb = T_cb' * MRrt(idx_all, idx_all) * T_cb;
KR_cb = T_cb' * KRrt(idx_all, idx_all) * T_cb;
CR_cb = T_cb' * CRrt(idx_all, idx_all) * T_cb;

%% CODE_CELL_C002
s = tf('s');
M = MRrt(order,order);
C = CRrt(order,order);
K = KRrt(order,order);
n = size(M, 1);  % 自由度数

A = [zeros(n) eye(n);
     -M \ K  -M \ C];

B = [zeros(n);
     M \ eye(n)];

C = [eye(n), zeros(n)];
D = zeros(n, n);

G_1 = ss(A, B, C, D);

M = MRren;
C = CRren;
K = KRren;
n = size(M, 1);  % 自由度数

A = [zeros(n) eye(n);
     -M \ K  -M \ C];

B = [zeros(n);
     M \ eye(n)];

C = [eye(n), zeros(n)];
D = zeros(n, n);

G_2 = ss(A, B, C, D);

M = MR_cb;
C = CR_cb;
K = KR_cb;
n = size(M, 1);  % 自由度数

A = [zeros(n) eye(n);
     -M \ K  -M \ C];

B = [zeros(n);
     M \ eye(n)];

C = [eye(n), zeros(n)];
D = zeros(n, n);

G_3 = ss(A, B, C, D);
