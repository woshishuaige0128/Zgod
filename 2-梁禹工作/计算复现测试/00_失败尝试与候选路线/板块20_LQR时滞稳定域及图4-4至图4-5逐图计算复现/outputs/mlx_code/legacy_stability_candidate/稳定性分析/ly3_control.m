P = 1.5;
I = 45;
D = 1e-8;
N = 1000;
s = tf('s');
Gpid = P+I/s+D*N/(1+N/s);
%Gp0 = P+I/s+D*s;
Gpid = [Gp0,0;0,Gp0];

Gc = ss(A_cplant,B_cplant,C_cplant,D_cplant);

G0 = series(Gpid,Gc);
Ds_ss = feedback(G0,eye(2));
Ds_tf = tf(Ds_ss);
Dd_tf = c2d(Ds_tf,dt,'tustin');
Dd_ss = c2d(Ds_ss,dt,'tustin');

%bode(Ds,G1_tfd)

%step(Ds,G1_tfd)

subplot(1, 2, 1); % 参数表示(行数, 列数, 子图编号)
bode(Dd_ss(1,1)); % 'r'表示红色，'LineWidth'设置线宽
title('状态空间方程'); % 添加标题

% 在右侧创建第二个子图
subplot(1, 2, 2); % 参数表示(行数, 列数, 子图编号)
bode(Dd_ss(1,1)); % 'b'表示蓝色，'LineWidth'设置线宽
title('传递函数'); % 添加标题
set(gcf, 'Color', 'w')
