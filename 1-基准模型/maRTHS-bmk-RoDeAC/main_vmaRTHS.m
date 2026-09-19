%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%            ***  Simulation Tool for v-maRTHS benchmark ***              %
%                     MATLAB/SIMULINK Version R2019b                      %
%            ===============================================              @
%                                                                         %
%              IISL, Purdue University, West Lafayette, IN                %
%               The University of Texas at San Antonio, TX                %
%                                                                         %
%                    Coded by:           Johnny Condori Uribe             %
%                    Collaborators:      Manuel Salmeron                  %
%                                        Edwin Patino                     %
%                                        Christian Silva                  %
%                                        Herta Montoya                    %
%                                        Mehdi Najarian                   %
%                                                                         %
%                    Supervised by:      Shirley J. Dyke                  %
%                                        Amin Maghareh                    %
%                                        Arturo Montoya                   %
%                                                                         %
%                    Created:            June 25, 2022                    %
%                                                                         %
%                    Last Updated:       July 13, 2023                    %
%                                                                         %
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

clc, clear, close all

disp('===============================================================')
disp('       VIRTUAL MULTI-AXIAL RTHS BENCHMARK CONTROL PROBLEM      ')
disp('                        Simulation Tool                        ')
disp('===============================================================')

% ========================================
% *        Simulation parameters         * 
% ========================================    

% NOTE: Participants might modify the following 4 parameters

fs = 1024;                      % Sampling frequency [Hz]

EQ_sw = 1;                      % Ground motion record: 
                                % 1: El centro, 2: Kobe, 3: Morgan
                              
EQ_intensity = 0.4;             % Ground motion scale factor 
     
%% NOTE: *** Participants SHOULD NOT modify this section ***

addpath(genpath('Support_files'));

S0_RealT_Uncert_Q               % Real-time and Plant Uncertainty Options


for i_RTHS = 1:(1 + num_unc_sim)
    
    % ========================================    
    % *               Input Data             *
    % ========================================
        S1_Input_Data

    % ========================================
    % * Control Plant, Reference, Partition  *
    % ========================================
        S2_Plant_Ref_Part

    % ========================================
    % *               Controller             *
    % ========================================
        S3_Controller

    % ========================================
    % *               Simulation             *
    % ========================================
        S4_Simulation

    % ========================================
    % *               Evaluation             *
    % ========================================
        S5_Evaluation

end   




  
    
    