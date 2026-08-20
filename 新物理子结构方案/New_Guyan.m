%% 将模型缩聚到两个子结构交界面处
% ------------------------
                            %  _       _
locate4 = [1,3,6,7,8];
locate5 = [2,4,5,9,10,11,12,13,14,15];
KNuu = KNrt(locate5,locate5);           % | Kuu Kuc |         
KNuc = KNrt(locate5,locate4);         % |_Kcu Kcc_|
KNcc = KNrt(locate4,locate4);       
KNcu = KNrt(locate4,locate5); 
KNuu(1,1) = 1e-5;

CNuu = CNrt(locate5,locate5);           % | Kuu Kuc |         
CNuc = CNrt(locate5,locate4);         % |_Kcu Kcc_|
CNcc = CNrt(locate4,locate4);       
CNcu = CNrt(locate4,locate5); 
CNuu(1,1) = 1e-5;

MNuu = MNrt(locate5,locate5);           % | Kuu Kuc |         
MNuc = MNrt(locate5,locate4);         % |_Kcu Kcc_|
MNcc = MNrt(locate4,locate4);       
MNcu = MNrt(locate4,locate5); 
MNuu(1,1) = 1e-5;

% Condensation:
KNred = KNcc - KNcu*inv(KNuu)*KNuc;
CNred = CNcc - KNcu*inv(CNuu)*KNuc;
MNred = MNcc - KNcu*inv(MNuu)*KNuc;

KNbar_red=(KNred+(a0*MNred)+(a1*CNred));
KNbar_red_inv = inv(KNbar_red);

AgNred = zeros(5,1);
lNred = zeros(5,1);
lNred(1,1) = 1;
lNred(3,1) = 1;
RNbarred = zeros(5,1);
FNred = zeros(5,1);

locate4 = [1,3,4,5,6];
locate5 = 2;
KPuu = KPrt(locate5,locate5); % | Kuu Kuc | 
KPuc = KPrt(locate5,locate4); % |_Kcu Kcc_|
KPcc = KPrt(locate4,locate4); 
KPcu = KPrt(locate4,locate5); 

CPuu = CPrt(locate5,locate5); % | Kuu Kuc | 
CPuc = CPrt(locate5,locate4); % |_Kcu Kcc_|
CPcc = CPrt(locate4,locate4); 
CPcu = CPrt(locate4,locate5); 

MPuu = MPrt(locate5,locate5); % | Kuu Kuc | 
MPuc = MPrt(locate5,locate4); % |_Kcu Kcc_|
MPcc = MPrt(locate4,locate4); 
MPcu = MPrt(locate4,locate5); 

KPred = KPcc - KPcu*inv(KPuu)*KPuc;
CPred = CPcc - KPcu*inv(CPuu)*KPuc;
MPred = MPcc - KPcu*inv(MPuu)*KPuc;

K_P1 = zeros(6,5);
K_P1(1,1) = 1;
K_P1(3,2) = 1;
K_P1(4,3) = 1;
K_P1(5,4) = 1;
K_P1(6,5) = 1;
K_P2 = zeros(6,1);
K_P2(2,1) = 1;
%-KPuu\KPuc