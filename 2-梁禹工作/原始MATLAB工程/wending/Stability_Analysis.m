clear;clc
%% 结构参数
dt=1/1024;
M=10; %质量（kg）
Mass = M;
K=5500;%刚度（N/m）
s=0.02;%阻尼比
C=2*s*sqrt(M*K);%阻尼（Ns/m）
Mn=8;%数值子结构质量
Kn=4500;%数值子结构刚度（N/m）
Cn=2*s*sqrt(Mn*Kn);%数值子结构阻尼
Me=M-Mn;%物理子结构质量
Ke=K-Kn;%物理子结构刚度
Ce=C-Cn;%物理子结构阻尼
alpha1=4*M/(4*M+2*C*dt+K*dt^2);
alpha2=alpha1;
z=tf('z',dt);
G=4*dt^2*z/((dt^2*(Kn+Ke)+2*Cn*dt+4*Mn)*z^2+(2*dt^2*(Kn-Ke)-8*Mn)*z+dt^2*(Kn+Ke)-2*Cn*dt+4*Mn);
for alpha_delay=1:30;
Gd=Ke*z/(alpha_delay*z-(alpha_delay-1));
Gcl=G/(1+G*Gd);
pole(Gcl);
Stability_Index(alpha_delay)=max(abs(ans));
end
