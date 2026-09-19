function VERIFY_LQR()
root=fileparts(fileparts(mfilename('fullpath')));D=load(fullfile(root,'results','model_and_cases.mat'));g=D.Guyan6;
T=[eye(2);-(g.K(3:end,3:end)\g.K(3:end,1:2))];M=T'*g.M*T;C=T'*g.C*T;K=T'*g.K*T;
A=[zeros(2),eye(2);-M\K,-M\C];B=[zeros(2);M\eye(2)];
[gain,X,closedPoles]=lqr(A,B,diag([1e6,1e6,1e4,1e4]),diag([1e-2,1e-2]));
relative_difference=norm(gain-g.gain,'fro')/norm(g.gain,'fro');assert(relative_difference<1e-8);
fprintf('MATLAB_LQR_RELATIVE_DIFFERENCE=%.17g\n',relative_difference);
save(fullfile(root,'results','matlab_lqr_check.mat'),'gain','X','closedPoles','relative_difference');
end
