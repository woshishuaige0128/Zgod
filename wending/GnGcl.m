%代表数值子结构
%输入力输出位移

k3 = zeros(2,29);
k3(1,27) = 1;
k3(2,21) = 1;
Gn1 = (s^2*MNrt+s*CNrt+KNrt)\eye(29,29);
Gn = k3*Gn1;

%Gcl输入力，输出位移
%输入力为29维，输出位移为2维
Gcl = (eye(2)+G1*Gn*Gp)\(G1*Gn)