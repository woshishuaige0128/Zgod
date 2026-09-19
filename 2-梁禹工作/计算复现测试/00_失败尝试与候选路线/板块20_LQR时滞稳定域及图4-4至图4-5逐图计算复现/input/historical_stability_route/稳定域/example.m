% 参数定义
dt = 1/1024;         % 采样时间
m1 = 1000;           % 第1层质量 kg
m2 = 1000;           % 第2层质量 kg
k1 = 4e6;            % 第1层刚度 N/m
k2 = 4e6;            % 第2层刚度 N/m
zeta = 0.02;         % 阻尼比

c1 = 2*zeta*sqrt(k1*m1);
c2 = 2*zeta*sqrt(k2*m2);

% 质量矩阵 M
M = [m1, 0;
     0,  m2];

% 刚度矩阵 K
K = [k1+k2, -k2;
     -k2,   k2];

% 阻尼矩阵 C
C = [c1+c2, -c2;
     -c2,   c2];

% 子结构划分（假设第2层物理子结构，数值子结构是整体减去第2层）
M_phys = [0, 0; 0, m2];
K_phys = [0, 0; 0, k2];
C_phys = [0, 0; 0, c2];

M_num = M - M_phys;
K_num = K - K_phys;
C_num = C - C_phys;

% 确认数值子结构自由度数
n = size(M_num,1);

% 构造状态空间矩阵
A = [zeros(n), eye(n);
     -M_num\K_num, -M_num\C_num];

B = [zeros(n);
     M_num\eye(n)];

C_out = eye(2*n);  % 输出所有状态：位移和速度
D = zeros(2*n, n);

% 生成状态空间模型
sys_num = ss(A, B, C_out, D);

% 显示数值子结构自振频率
omega = sqrt(eig(K_num, M_num));
freq_Hz = omega/(2*pi);
disp('数值子结构自振频率 (Hz):');
disp(freq_Hz);
