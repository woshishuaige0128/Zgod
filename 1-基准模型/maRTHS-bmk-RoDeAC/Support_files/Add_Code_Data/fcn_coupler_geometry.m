function [xv1,yv1,dv1,alpha1, xv2,yv2,dv2,alpha2] = fcn_couplerGeometry()

    % Coupler geometric properties:
    xv1 = 0.26670;   yv1 = -0.127;   dv1 = sqrt(xv1^2 + yv1^2);
    alpha1 = -25.4633*pi/180;
    
    xv2 = 0.26670;   yv2 = 0.127;    dv2 = sqrt(xv2^2 + yv2^2);
    alpha2 = 25.4633*pi/180;

end