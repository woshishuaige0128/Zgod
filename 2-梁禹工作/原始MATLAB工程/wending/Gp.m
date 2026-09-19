k1 = zeros(5,2);
k1(1,1) = 1;
k1(2,2) = 1;
k2 = zeros(5,3);
k2(3,1) = 1;
k2(4,2) = 1;
k2(5,3) = 1;

k4 = k1-k2*inv(Koo)*Kot;

%Gp输入2维位移，输出29维力
Gp1 = s^2*M_phys_5dof*k4+s*C_phys_5dof*k4+K_phys_5dof*k4;

k5 = zeros(29,5);
k5(27,1) = 1;
k5(21,2) = 1;
k5(29,3) = 1;

Gp = k5*Gp1;