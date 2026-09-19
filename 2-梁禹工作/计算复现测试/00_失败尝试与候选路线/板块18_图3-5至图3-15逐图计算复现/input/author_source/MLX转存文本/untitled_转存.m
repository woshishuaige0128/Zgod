%% 
% 缩聚

index3 = [1,4];
index4 = [2,3,5,6];
dt = 1/1024
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

index3 = [1,11,4,9,14];
index4 = [6,2,3,5,7,8,10,12,13,15];
order = [1,11,4,9,14,6,2,3,5,7,8,10,12,13,15];

Mforce = MRrt(order,order);
Mf = diag([1,1,0,0,0,1,0,0,0,0,0,0,0,0,0].*Mforce);

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

I = eye(length(index3)); % 主自由度单位矩阵 3x3
T = [I; -Ksn\Ksmn];      % 拼接得到转换矩阵

index3 = [1,11,4,9,14];
index4 = [6,2,3,5,7,8,10,12,13,15];

Kss = KRrt(index4,index4);
Mss = MRrt(index4,index4);

% 固定边界模态分析
[phi_s, D] = eig(Kss, Mss);
omega = sqrt(diag(D));

r = 3; % 选取前5个模态
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
%% 
% 

s = tf('s');
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