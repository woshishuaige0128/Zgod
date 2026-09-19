%=========================================================================%
%                     Offline RLS-AC Calibration                          %
%=========================================================================% 

fs = 1024;                      % Sampling frequency [Hz]
intensities = [0.2,0.4,0.6];    % Earthquakes scaling factors
rt_option = 'n';
num_unc_sim = 10;               % Number of considered uncertainty plants
plot_on = 'n';
cont = 1;                       % Auxiliary variable

for EQ_sw = [1,2,3]             % Ground motion record: 
                                % 1: El centro, 2: Kobe, 3: Morgan         
    for j = 1:length(intensities)
        EQ_intensity = intensities(j);   % Ground motion scale factor 

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
            % *               Simulation             *
            % ========================================
            set_param(bdroot,'SolverType','Fixed-step','Solver','ode4','StopTime','tend','FixedStep','dt')

            SimOut = sim("Model_Calibration.slx");

            %=========================================================================%
            %                           STORING RESPONSES                       
            %=========================================================================% 
            % Target actuator displacements [mm]:
            rths_Xa1t{i_RTHS}       = xa1_t;
            rths_Xa2t{i_RTHS}       = xa2_t;

            % Measured displacements of hydraulic actuators
            rths_Xa1m{i_RTHS}       = xa1m;
            rths_Xa2m{i_RTHS}       = xa2m;

            phi1 = [];
            phi2 = [];
            for i = 4:length(xa1m)
                phi1 = [phi1;xa1m(i) xa1m(i-1) xa1m(i-2) xa1m(i-3)];
                phi2 = [phi2;xa2m(i) xa2m(i-1) xa2m(i-2) xa2m(i-3)];
            end

            gamma1 = phi1.*1e-3; 
            P0_1{cont} = (gamma1'*gamma1)^-1;
            theta0_1{cont} = P0_1{cont}*gamma1'*xa1_t(4:length(xa1m))*1e-3;

            gamma2 = phi2.*1e-3; 
            P0_2{cont} = (gamma2'*gamma2)^-1;
            theta0_2{cont} = P0_2{cont}*gamma2'*xa2_t(4:length(xa1m))*1e-3;
            
            cont  = cont +1
        end
    end
end

