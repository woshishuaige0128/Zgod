function [U1_MA,Theta_MA,U1,Vel1,Acc1,FRef,M1Ref,M2Ref]=fcn(accel_grd,Kbar_inv, MNrt, CNrt,Ag,l,Rbar,F,...
    U0,Vel0,Acc0, a0, a1, a2, a3, a4, a5, a6, a7)
             
             
    % ============================
	% *  Update next iteration   *
	% ============================
    ndof = length(Kbar_inv);
    U1   = zeros(ndof,1);
    Vel1 = zeros(ndof,1);
    Acc1 = zeros(ndof,1);
    U1_MA = 0;
    Theta_MA = 0;
    FRef = 0;
    M1Ref = 0;
    M2Ref = 0;

    % ============================
	% *  Feedback Force / Moment *
	% ============================
%     F(27) = -FB_force;
%     F(14) = -FB_moment;

    % ==========================
	% *     Update Matrices    *
	% ==========================
    Ag(:)  = accel_grd * l;
    
   	% ==========================
	% * 	  Form Rbar  	   *
	% ==========================
	Rbar = ( (MNrt * ((a0*U0)+(a2*Vel0)+(a3*Acc0))) + ...
		     (CNrt * ((a1*U0)+(a4*Vel0)+(a5*Acc0))) - F - (MNrt * Ag) );
    FRef = Rbar(27);
    M1Ref= Rbar(21);
    M2Ref= Rbar(29);
    % ==========================
	% * Solve for Displacement *
	% ==========================
	U1 = Kbar_inv * Rbar;
    
	% ============================
	% * Compute Velocity & Accel *
	% ============================
	Acc1=a0*(U1-U0)-a2*Vel0-a3*Acc0;
	Vel1=Vel0+a7*Acc1+a6*Acc0; 

	% ============================
	% *    Output u1 and theta   *
	% ============================
    U1_MA    = U1(27);
    Theta_MA = U1(21);


end 