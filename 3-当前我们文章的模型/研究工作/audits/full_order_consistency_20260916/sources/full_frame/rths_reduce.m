function R = rths_reduce(frame, division, formulation)
if nargin<3, formulation='standard'; end
% 唯一对照因素为Guyan矩阵构造；基底、荷载、CB及完整模型一致。
M=frame.M;C=frame.C;K=frame.K;
    if division == 1
        master = [1,6,11,4,9,14];
        slave = [2,3,5,7,8,10,12,13,15];
        forceMask = [1,1,1,0,0,0,0,0,0,0,0,0,0,0,0];
    elseif division == 2
        master = [1,11,4,9,14];
        slave = [6,2,3,5,7,8,10,12,13,15];
        forceMask = [1,1,0,0,0,1,0,0,0,0,0,0,0,0,0];
    else
        error('未知子结构划分编号：%g', division);
    end

    order = [master, slave];
    Mo = M(order,order); Co = C(order,order); Ko = K(order,order);
    nm = numel(master);
    Mmm = Mo(1:nm,1:nm); Mms = Mo(1:nm,nm+1:end);
    Cmm = Co(1:nm,1:nm); Cms = Co(1:nm,nm+1:end);
    Kmm = Ko(1:nm,1:nm); Kms = Ko(1:nm,nm+1:end);
    Ksm = Ko(nm+1:end,1:nm); Kss = Ko(nm+1:end,nm+1:end);
    Mss = Mo(nm+1:end,nm+1:end);

    staticConstraint = -(Kss\Ksm);
    T = [eye(nm); staticConstraint];
    if strcmp(formulation,'standard')
        Mg = T'*Mo*T; Cg = T'*Co*T; Kg = T'*Ko*T;
    elseif strcmp(formulation,'legacy')
    Mg = Mmm + Mms*staticConstraint;
    Cg = Cmm + Cms*staticConstraint;
    Kg = Kmm + Kms*staticConstraint;
    else
        error('Unknown Guyan formulation');
    end

    [phi, lambda] = eig(Kss, Mss);
    [~, idx] = sort(real(diag(lambda)), 'ascend');
    phi = real(phi(:,idx));
    retainedModes = 3;
    Tcb = [eye(nm), zeros(nm,retainedModes); staticConstraint, phi(:,1:retainedModes)];
    Mcb = Tcb'*Mo*Tcb;
    Ccb = Tcb'*Co*Tcb;
    Kcb = Tcb'*Ko*Tcb;

    G1 = second_order_ss(M, C, K);
    G2 = second_order_ss(Mg, Cg, Kg);
    G3 = second_order_ss(Mcb, Ccb, Kcb);

    floorOriginal = [1,6,11];
    floorRowsOrdered = arrayfun(@(q)find(order==q,1), floorOriginal);
    P = eye(15); P = P(floorRowsOrdered,:);
    Cfloor1 = [eye(15), zeros(15)]; Cfloor1 = Cfloor1(floorOriginal,:);
    Cfloor2 = [P*T, zeros(3,size(T,2))];
    Cfloor3 = [P*Tcb, zeros(3,size(Tcb,2))];

    Mf = diag(forceMask .* Mo);
    R.G_1 = G1; R.G_2 = G2; R.G_3 = G3;
    R.T = T; R.T_cb = Tcb; R.Mf = Mf;
    R.Cfloor1 = Cfloor1; R.Cfloor2 = Cfloor2; R.Cfloor3 = Cfloor3;
    R.Dfloor1 = zeros(3,size(G1.B,2));
    R.Dfloor2 = zeros(3,size(G2.B,2));
    R.Dfloor3 = zeros(3,size(G3.B,2));
    R.master = master; R.slave = slave; R.order = order;
    R.division = division; R.Mo=Mo; R.Co=Co; R.Ko=Ko; R.staticConstraint=staticConstraint; R.fixed_interface_modes=phi(:,1:retainedModes);
    R.Mg = Mg; R.Cg = Cg; R.Kg = Kg;
    R.Mcb = Mcb; R.Ccb = Ccb; R.Kcb = Kcb;
end

function G = second_order_ss(M, C, K)
    n = size(M,1);
    A = [zeros(n), eye(n); -M\K, -M\C];
    B = [zeros(n); M\eye(n)];
    Cq = [eye(n), zeros(n)];
    D = zeros(n,n);
    G = ss(A,B,Cq,D);
end

