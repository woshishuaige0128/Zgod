function [U27_MA,V27_MA,A27_MA,Theta21_MA,VTheta21_MA,ATheta21_MA,Theta29_MA,VTheta29_MA,ATheta29_MA,U1,Vel1,Acc1]=...
    fcn(accel_grd,FB_force27,FB_moment29,FB_moment21,Kbar_inv, MNrt, CNrt,Ag,l,Rbar,F,...
    U0,Vel0,Acc0, a0, a1, a2, a3, a4, a5, a6, a7)
             
             
    % ============================
	% *  Update next iteration   *
	% ============================
    ndof = length(Kbar_inv);
    U1   = zeros(ndof,1);
    Vel1 = zeros(ndof,1);
    Acc1 = zeros(ndof,1);
    
    U27_MA = 0;
    V27_MA = 0;
    A27_MA = 0;

    Theta21_MA = 0;
    VTheta21_MA = 0;
    ATheta21_MA = 0;
% 
%     U6_MA = 0;
%     V6_MA = 0;
%     A6_MA = 0;

    Theta29_MA = 0;
    VTheta29_MA = 0;
    ATheta29_MA = 0;

    % ============================
	% *  Feedback Force / Moment *
	% ============================
    F(27) = FB_force27;
    F(21) = FB_moment21;
    F(29) = FB_moment29;

    % ==========================
	% *     Update Matrices    *
	% ==========================
    Ag(:)  = accel_grd * l;
    
   	% ==========================
	% * 	  Form Rbar  	   *
	% ==========================
	Rbar = ( (MNrt * ((a0*U0)+(a2*Vel0)+(a3*Acc0))) + ...
		     (CNrt * ((a1*U0)+(a4*Vel0)+(a5*Acc0))) - F - (MNrt * Ag) );
    
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
    U27_MA    = U1(27);
    V27_MA    = Vel1(27);
    A27_MA    = Acc1(27);    

%     U6_MA    = U1(27);
%     V6_MA    = Vel1(27);
%     A6_MA    = Acc1(27);

    Theta21_MA = U1(21);
    VTheta21_MA = Vel1(21);
    ATheta21_MA = Acc1(21);

    Theta29_MA = U1(29);
    VTheta29_MA = Vel1(29);
    ATheta29_MA = Acc1(29);

end 