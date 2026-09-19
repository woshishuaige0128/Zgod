%%  NOTE: *** Participants SHOULD NOT modify this file ***
%                          ----------

%%=========================================================================%
%                              Control Plant                     
%=========================================================================%
    
    % Load identified model (from experimental data)
    load('ID_Control_plant_100Hz.mat')
    
    if i_RTHS == 1
        % Build state-space control plant model from the identified
        % nominal model, i.e., plant model WITHOUT uncertainties:
        A_cplant = plantFRAME_SS.a;
        B_cplant = plantFRAME_SS.b;
        C_cplant = plantFRAME_SS.c;
        D_cplant = plantFRAME_SS.d;
    else
        % Plant model WITH uncertainties:
        [A_cplant,B_cplant,C_cplant,D_cplant, h1z_1u,h1z_2u,h1p_1u,h1p_2u,frame_pole_1u, ...
            h12z_1u, h2p_1u, h2p_2u, h22z_1u] = fcn_build_uncert_plant(); 
    end
       
%=========================================================================%
%                   Kinematic Coordinate Transformation        
%=========================================================================%
    
    % Coupler geometric properties:
    [xv1,yv1,dv1,alpha1, xv2,yv2,dv2,alpha2] = fcn_coupler_geometry();

    % NOTE: The coordinate transformation equations are implemented 
    % directly in the Simulink model "Model_vmaRHTS_SimR2029b.slx"

%=========================================================================%
%                        Define Reference Structure            
%=========================================================================%
    build_reference  
    
%=========================================================================%
%                       Define Numerical Substructure         
%=========================================================================%  
    build_numerical 

%=========================================================================%
%           Physical Frame Model for Feedback Force Computation  
%=========================================================================%  
    physicalFrame_feedbackForce
    
    










