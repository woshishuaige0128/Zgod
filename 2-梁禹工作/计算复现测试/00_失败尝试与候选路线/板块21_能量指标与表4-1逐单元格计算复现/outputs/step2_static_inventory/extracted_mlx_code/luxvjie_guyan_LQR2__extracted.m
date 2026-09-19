% Static extraction from luxvjie_guyan_LQR2.mlx
% Source SHA-256: 85B71050673BCB956E397490E41A8BC6D748AF2E633F00F5D0D8968BAFB67102
% No MATLAB execution was performed.

%% CODE_CELL_C001
index1 = [1,2];
index2 = [3,4,5,6,7,8];
K2 = KRren;
K2(index1,index1) = KRren(index1,index1)-KPren;
K2(index2,index2) = KRren(index2,index2)-KNren;
C2 = CRren;
C2(index1,index1) = CRren(index1,index1)-CPren;
C2(index2,index2) = CRren(index2,index2)-CNren;
C1 = CRren-C2;
K1 = KRren-K2;

dt = 1/1024;
al = (4*MRren+2*dt*CRren+dt^2*KRren)\MRren*4;
al = diag(diag(al));

%% CODE_CELL_C002
% 2. 选择矩阵 S: 6x15
S = zeros(2, 6);

% 定义映射：小矩阵第1-3行 → 大矩阵第1-3行
% 小矩阵第4-6行 → 大矩阵第6-8行
row_map = [1 2];

for i = 1:2
    S(i, row_map(i)) = 1;
end

M = MPren;
C = CPren;
K = KPren;
n = length(M);
% 系统矩阵
A = [zeros(n) eye(n); -M\K -M\C];
B = [zeros(n); M\eye(n)];

% 连续系统 -> 离散
sys_c = ss(A, B, eye(2*n), zeros(2*n, n));
dt = 1/1024;  % 离散化周期
sys_d = c2d(sys_c, dt);
Ad = sys_d.A;
Bd = sys_d.B;

Q = diag([4e8, 1e4, 1e2, 1e1]);
R = diag([3e-3,1e-2]);
[K_lqr, ~, ~] = dlqr(Ad, Bd, Q, R);
% 闭环系统矩阵
Acl = Ad - Bd * K_lqr;

% 分解增益为刚度、阻尼反馈
DeltaK = diag(diag(MPren*K_lqr(:, 1:n)))
DeltaC = diag(diag(MPren*K_lqr(:, n+1:end)));

DeltaG = (z-1)/z/dt*DeltaC+DeltaK;

%for l = 1:20
%    for j = 1:30

%% CODE_CELL_C003
stab = zeros(20);
for l = 0:15
%l =5;
%for j = 0:15
%j = 25;
j = 0;
%j = 0;
%z=tf('z',dt);
syms z
%l = 19;
%j = 5;
H = sym(eye(6,6));
H(1,1) = z^(-l);
H(2,2) = z^(-j);

%syms z
G = (z-1)^2/z/dt^2*MRren/al+(z-1)/z/dt*C1+K1+...
    ((z-1)/z/dt*C2+K2)*H+S'*DeltaG*S;
%G = (z-1)^2/z/dt^2*MNren/al+(z-1)/z/dt*CNren+KNren+...
%    S'*H*((z-1)/z/dt*CPren+KPren+(z-1)/z/dt*Kd_ctrl+Kp_ctrl)*S;
det_G = det(G);
Gcls_zero = vpa(solve(det_G == 0, z));
s = max(abs(Gcls_zero))
stab(l+1,j+1) = s;
end
%end
