function modes = rths_modes(frame,models)
% 先求解，再恢复15坐标，再按同一个完整质量矩阵归一化。
M=frame.M;Gamma=zeros(15,1);Gamma([1 6 11])=1;
modes=cell(2,3);
for d=1:2
    R=models{d};masses={M,R.Mg,R.Mcb};stiffnesses={frame.K,R.Kg,R.Kcb};
    bases={eye(15),R.T,R.T_cb};
    for j=1:3
        Mr=masses{j};Kr=stiffnesses{j};
        [V,L]=eig(Kr,Mr);[lambda,index]=sort(real(diag(L)));V=real(V(:,index));
        assert(all(lambda>0),'模态特征值必须为正。');
        residual=zeros(numel(lambda),1);
        for k=1:numel(lambda)
            residual(k)=norm(Kr*V(:,k)-lambda(k)*Mr*V(:,k))/((norm(Kr)+lambda(k)*norm(Mr))*norm(V(:,k)));
        end
        assert(max(residual)<1e-12,'特征值方程残差超限。');
        physical=V;
        if j>1,physical=zeros(15,size(V,2));physical(R.order,:)=bases{j}*V;end
        for k=1:size(physical,2)
            physical(:,k)=physical(:,k)/sqrt(physical(:,k)'*M*physical(:,k));
            if physical(11,k)<0,physical(:,k)=-physical(:,k);end
        end
        phi=physical(:,1:5);
        gamma=phi'*M*Gamma;
        weights=gamma.^2/sum(gamma.^2);
        coordinate=diag(M).*phi.^2;
        coordinate=coordinate./sum(coordinate,1);
        contributions=coordinate.*weights';
        shares=sum(contributions,2);
        horizontal=physical([1 6 11],1:2);
        horizontal=horizontal./max(abs(horizontal),[],1);
        assert(abs(sum(shares)-1)<1e-12 && abs(sum(weights)-1)<1e-12);
        modes{d,j}=struct('frequency_hz',sqrt(lambda)/(2*pi),'native_modes',V,...
            'physical_modes',physical,'horizontal',horizontal,'gamma',gamma,...
            'weights',weights,'coordinate_fractions',coordinate,...
            'weighted_contributions',contributions,'shares',shares,'residual',residual);
    end
end
fprintf('模态：两种划分×三种模型；前5阶参与权重与15坐标份额已计算。\n');
end
