function inputs = rths_inputs(root)
% 输入与积分网格分开：地震按原0.02 s采样送入Simulink，求解时线性插值。
D=load(fullfile(root,'必要输入','EQ.mat'),'ElCentroAccel','EQ_intensity','EQ_sw');
assert(D.EQ_sw==1 && abs(D.EQ_intensity-0.4)<1e-14,'地震输入配置不符。');
inputs.dt=1/1024;inputs.duration=40;
inputs.time=(0:inputs.dt:inputs.duration)';
raw=D.ElCentroAccel;keep=raw(1,:)<=inputs.duration;
inputs.eq=[raw(1,keep)' D.EQ_intensity*raw(2,keep)'];
t=inputs.time;
inputs.chirp=[t sin(2*pi*0.1*t+pi*9.9/40*t.^2)];
inputs.eq_on_grid=interp1(inputs.eq(:,1),inputs.eq(:,2),t,'linear');
inputs.chirp_frequency_hz=0.1+9.9/40*t;
assert(all(isfinite(inputs.eq_on_grid)) && isequal(size(inputs.chirp),[40961 2]));
fprintf('激励：El Centro×0.40；扫频0.1—10 Hz；积分网格40961点。\n');
end
