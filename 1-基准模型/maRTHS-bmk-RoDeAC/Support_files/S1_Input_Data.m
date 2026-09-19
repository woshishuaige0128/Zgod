%%  NOTE: *** Participants SHOULD NOT modify this file ***
%                          ----------

%=========================================================================%
%                      General Simulation Parameters                      %
%=========================================================================%  

% Sampling period [s]
    dt = 1/fs;                                           

%Automatic selection of ground motion:
    switch EQ_sw
        case 1
            load('ElCentroAccelNoScaling')          % UNITS: [m/s^2]
            tend = ElCentroAccel(1,end);            % Earthquake Ending Time
        case 2
            load('KobeAccelNoScaling')              % UNITS: [m/s^2]
            tend = KobeAccel(1,end);                % Earthquake Ending Time
        case 3
            load('MorganAccelNoScaling')            % UNITS: [m/s^2]
            tend = MorganAccel(1,end);              % Earthquake Ending Time
        otherwise
    end

% Note: A zero vector of aroud 10 sec has been added to each earthquake to
%       to obtain a attenuated response of the system.        

%=========================================================================%
%                 Channels Setup and Conversion Factors
%=========================================================================%

    % Conversion fators
    v2d_gain1  = 7.4921; v2d_const1 = 0.0092;       % Voltage to displacement Actuator 1
    v2f_gain1 = 2074.7401; v2f_const1 = 0.6074;     % Voltage to force Actuator 1

    v2d_gain2  = 7.3907; v2d_const2 = -0.0059;      % Voltage to displacement Actuator 2
    v2f_gain2 = 2006.3618; v2f_const2 = 0.2450;     % Voltage to force Actuator 1

    correction_gain1 = 1.053;
    correction_gain2 = 1.055;
    
    % Saturation limits 
    sat_limit = 3.8;                                % [Volts]
    cellLoad_limit = 2500*4.44822;                  % Max capacity of load cells [N]
    HAload_limit = 2100*4.44822;                    % Max capacity of hydraulic actuators [N]

    % Quantization interval
    quantize_int = 1 / 2^18;                        % 18 bit channel

%=========================================================================%
%                           Sensor RMS noise
%=========================================================================%
    if i_RTHS == 1
        seed = rng(123);
    else
        seed = rng('shuffle'); 
    end

    %Sensor RMS noise (Displacement transducer)
    rms_noise_DT = 1.5e-7;         
    Seed_snr = rng(seed);                           % Random number generator for noise
