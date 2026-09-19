% Static extraction from luxvjie_ori_LQR3.mlx
% Source SHA-256: 149E9FDD7F98CFD0A5B581D7BD2B27521908BC89FFB2DEF1F891D4402E4B89D5
% No MATLAB execution was performed.

%% CODE_CELL_C001
locate2 = [1,2,3,7,8,9]



K2 = KRrt-KNrt_1-KPrt_1;
C2 = CRrt-CNrt_1-CPrt_1;
K1 = KRrt-K2;
C1 = CRrt-C2;

al = (4*MRrt+2*dt*CRrt+dt^2*KRrt)\MRrt*4;

S = zeros(2, 18);

% 定义映射：小矩阵第1-3行 → 大矩阵第1-3行
% 小矩阵第4-6行 → 大矩阵第6-8行
row_map = [1 13];

for i = 1:2
    S(i, row_map(i)) = 1;
end

%% CODE_CELL_C002
stab = zeros(20);
%for l = 0:5
l = 0;
%for j = 0:5
j = 6;

syms z
H = sym(eye(18));
H(1,1) = z^(-l);
H(13,13) = z^(-j);

%syms z
G = (z-1)^2/z/dt^2*MRrt/al+(z-1)/z/dt*C1+K1+...
    ((z-1)/z/dt*C2+K2)*H;
%+S'*DeltaG*S
%G = (z-1)^2/z/dt^2*MNren/al+(z-1)/z/dt*CNren+KNren+...
%    S'*H*((z-1)/z/dt*CPren+KPren+(z-1)/z/dt*Kd_ctrl+Kp_ctrl)*S;
det_G = det(G);
Gcls_zero = vpa(solve(det_G == 0, z));
s = max(abs(Gcls_zero))
stab(l+1,j+1) = s;
%end
%end
%save('stab_guyan_lqr.mat', 'stab');
