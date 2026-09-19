index1 = [1,2,6,7,8];
index2 = [3,4,5,6,7,8];
K2 = KR_cb;
K2(index1,index1) = KR_cb(index1,index1)-KP_cb;
K2(index2,index2) = KR_cb(index2,index2)-KN_cb;
C2 = CR_cb;
C2(index1,index1) = CR_cb(index1,index1)-CP_cb;
C2(index2,index2) = CR_cb(index2,index2)-CN_cb;
C1 = CR_cb-C2;
K1 = KR_cb-K2;

dt = 1/1024;
al = (4*MR_cb+2*dt*CR_cb+dt^2*KR_cb)\MR_cb*4;
al = diag(diag(al));

% 2. 选择矩阵 S: 6x15
S = zeros(2, 8);

% 定义映射：小矩阵第1-3行 → 大矩阵第1-3行
% 小矩阵第4-6行 → 大矩阵第6-8行
row_map = [1 2];

for i = 1:2
    S(i, row_map(i)) = 1;
end

%    for j = 1:30

stab = zeros(20);
%for l = 0:15
%l =5;
for j = 0:15
%j = 25;
l = 0;
%j = 0;
%z=tf('z',dt);
syms z
%l = 19;
%j = 5;
H = sym(eye(8));
H(1,1) = z^(-l);
H(2,2) = z^(-j);

%syms z
G = (z-1)^2/z/dt^2*MR_cb/al+(z-1)/z/dt*C1+K1+...
    ((z-1)/z/dt*C2+K2)*H;
%+S'*DeltaG*S
%G = (z-1)^2/z/dt^2*MNren/al+(z-1)/z/dt*CNren+KNren+...
%    S'*H*((z-1)/z/dt*CPren+KPren+(z-1)/z/dt*Kd_ctrl+Kp_ctrl)*S;
det_G = det(G);
Gcls_zero = vpa(solve(det_G == 0, z));
s = max(abs(Gcls_zero))
stab(l+1,j+1) = s;
end
%end
