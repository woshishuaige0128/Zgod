load('benchmarkstability.mat');
load('stabilitycanshu.mat');

index1 = [13,21,26,27,29];
index2 = [1:12,14:20,22:25,28];
Ku1 = zeros(5,29);
Ku1(1,27) = 1;
Ku1(2,21) = -1;
Ku1(3,29) = -1;
Ku1(4,19) = -1;
Ku1(5,18) = -1;

%Ku1(5,18) = 1;
%Ku1(4,19) = 1;

% 此处计算的都是整体结构的参数，用于计算CR积分算法的alpha
Mm = M(index1,index1);
Mms = M(index1,index2);
Km = K(index1,index1);
Kms = K(index1,index2);
Ks = K(index2,index2);
Ksm = K(index2,index1);
Cm = C(index1,index1);
Cms = C(index1,index2);

Mmn = MNrt(index1,index1);
Mmsn = MNrt(index1,index2);
Kmn = KNbar(index1,index1);
Kmsn = KNbar(index1,index2);
Ksn = KNbar(index2,index2);
Ksmn = KNbar(index2,index1);
Cmn = CNrt(index1,index1);
Cmsn = CNrt(index1,index2);

Kre = (Km-Kms*(Ks\Ksm));
Mre = (Mm-Mms*(Ks\Ksm));Mre(2,2) = 1e-6;Mre(5,5) = 1e-6;
Cre = (Cm-Cms*(Ks\Ksm));

Krenbar = (Kmn-Kmsn*(Ksn\Ksmn));
Mrenbar = (Mmn-Mmsn*(Ksn\Ksmn));
Crenbar = (Cmn-Cmsn*(Ksn\Ksmn));

Kmn = KNrt(index1,index1);
Kmsn = KNrt(index1,index2);
Ksn = KNrt(index2,index2);
Ksmn = KNrt(index2,index1);

Kren = (Kmn-Kmsn*(Ksn\Ksmn));
Mren = (Mmn-Mmsn*(Ksn\Ksmn));
Cren = (Cmn-Cmsn*(Ksn\Ksmn));

s = tf('s');
Gns_tf = (Mren.*s^2+Cren.*s+Kren)\eye(5);
Gnd_tf = c2d(Gns_tf,dt,'tustin');
Gns_ss = ss(Gns_tf);
Gnd_ss = c2d(Gns_ss,dt,'tustin');

%bode(Gnd_ss(1,1),Gnd_tf(1,1))
%bode(Gnd_ss(1,1))
%bode(Gnd_tf(1,1))

%step(Gnd_ss,Gnd_tf)

subplot(1, 2, 1); % 参数表示(行数, 列数, 子图编号)
bode(Gnd_ss(1,1)); % 'r'表示红色，'LineWidth'设置线宽
title('状态空间方程'); % 添加标题

% 在右侧创建第二个子图
subplot(1, 2, 2); % 参数表示(行数, 列数, 子图编号)
bode(Gnd_tf(1,1)); % 'b'表示蓝色，'LineWidth'设置线宽
title('传递函数'); % 添加标题
set(gcf, 'Color', 'w')
