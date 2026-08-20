% *****************************************
%  		Compute Newmark Beta Constants
% *****************************************
function [a0,a1,a2,a3,a4,a5,a6,a7] = newmark_beta_constants(delta,alpha,dt)
	a0     =  1/alpha/dt^2; 
	a1     =  delta/alpha/dt; 
	a2     =  1/alpha/dt; 
	a3     =  1/2/alpha-1;
	a4     =  delta/alpha-1;
	a5     =  dt/2*(delta/alpha-2); 
	a6     =  dt*(1-delta); 
	a7     =  delta*dt;
end 