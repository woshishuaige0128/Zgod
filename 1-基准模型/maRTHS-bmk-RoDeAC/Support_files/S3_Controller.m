%%  NOTE: *** Participants SHOULD modify this file ***
%                          ------
% 
%=========================================================================%
%                Recursive Least Squares Adaptive Compensator
%=========================================================================%
% 
% Maria Elena Quiroz, Cristobal Galmez, Gaston Fermandois
% Universidad Tecnica Federico Santa Maria
% Valparaiso, Chile
% Correspondance: gaston.fermandois@usm.cl
% 
% Instructions:
% ------------
% 
% 1. Run the offline callibration before the virtual/physical RTHS
% 
%     > Offline_calibration.m
% 
% 2. Store the initial parameters in Matlab file
% 
%     > Initial_parameters.mat
% 
% 3. Choose a value of forgetting factor (e.g. forgfact = 1)
% 
% 4. Choose a FIR filter for the controller (e.g., Butterworth 4th order,
%    fc = 20 Hz)
% 
% 5. Controller is ready to be implemented
% 

load('Initial_parameters.mat');

% Initial discrete FIR filter 1
discrete_fir_i1 = theta0_1';
fir_coef1 = length(discrete_fir_i1);

% Initial discrete FIR filter 2
discrete_fir_i2 = theta0_2';
fir_coef2 = length(discrete_fir_i2);

%forgeting factor
forgfact = 1;

%Initial inverse correlation matrix (set both to zero for non-adaptive
%compensator)
P_corr_i_act1 = P0_1;
P_corr_i_act2 = P0_2;

%noise filter
n = 4; %order
fc = 20; %cutoff frequency
[numfilter,denfilter] = butter(n,fc/(fs/2)); %discrete filter
   
 
         
    