%%  NOTE: *** Participants SHOULD NOT modify this file ***
%                          ----------

%=========================================================================%
%                           START SIMULATION                       
%=========================================================================% 
set_param(bdroot,'SolverType','Fixed-step','Solver','ode4','StopTime','tend','FixedStep','dt')

SimOut = sim("Model_vmaRHTS_R2019b.slx");

%=========================================================================%
%                           STORING RESPONSES                       
%=========================================================================% 
% Displacement and rotation from the reference structure:
rths_Xref{i_RTHS}       = xRef;
rths_Rref{i_RTHS}       = rRef;
rths_Xref_2st{i_RTHS}   = xRef_2st;
rths_Rref_2st{i_RTHS}   = rRef_2st;
rths_Xref_3st{i_RTHS}   = xRef_3st;
rths_Rref_3st{i_RTHS}   = rRef_3st;
rths_uncRref{i_RTHS}    = r2Ref;             %Rotation of uncontrolled node

% Displacement and rotation from the numerical substructure:
rths_Xnum{i_RTHS}       = xNum;
rths_Rnum{i_RTHS}       = rNum;
rths_Xnum_2st{i_RTHS}   = xNum_2st;
rths_Rnum_2st{i_RTHS}   = rNum_2st;
rths_Xnum_3st{i_RTHS}   = xNum_3st;
rths_Rnum_3st{i_RTHS}   = rNum_3st;
rths_uncRnum{i_RTHS}    = r2Num;             %Rotation of uncontrolled node

% Target actuator displacements [mm]:
rths_Xa1t{i_RTHS}       = xa1_t;
rths_Xa2t{i_RTHS}       = xa2_t;

% Command input displacements [mm]:
% rths_CMu1{i_RTHS}       = cmd_u1;
% rths_CMu2{i_RTHS}       = cmd_u2;

% Command input signals [V]:
rths_CMu1V{i_RTHS}      = cmd1_v;
rths_CMu2V{i_RTHS}      = cmd2_v;

% Measured displacements of hydraulic actuators
rths_Xa1m{i_RTHS}       = xa1m;
rths_Xa2m{i_RTHS}       = xa2m;

% Filtered measured displacements of hydraulic actuators
%NOTE: They are computed from the measured actuator displacements after
%these has been estimated (filtered out noise) using Kalman.
rths_Xa1m_hat{i_RTHS}   = xa1m_hat;
rths_Xa2m_hat{i_RTHS}   = xa2m_hat;

% Displacement and rotation from the physical substructure (controlled node):
%NOTE: These are computed from the filtered responses of the actuators 
%by using the kinematic transformation, Section 5.1 in %the paper.
rths_Xm_hat{i_RTHS}     = xm_hat;
rths_Rm_hat{i_RTHS}     = rm_hat;
rths_uncRm_hat{i_RTHS}  = rm2_hat;             %Rotation uncontrolled node


if i_RTHS == 1
    fprintf('\t-Virtual maRTHS with nominal plant completed.\n')
    else
    fprintf('\t-Virtual maRTHS with uncertainties in plant # %d completed.\n',(i_RTHS-1))    
end

