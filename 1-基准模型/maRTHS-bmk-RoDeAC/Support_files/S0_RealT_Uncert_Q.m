%%  NOTE: *** Participants SHOULD NOT modify this file ***
%                          ----------

%=========================================================================%
%                            Real-time Inquiry                            %
%=========================================================================% 
disp(' ')
prompt = 'Would you like to run this virtual maRTHS in real-time? y/n [n]: ';
rt_option = input(prompt, 's');
rt_option = lower(rt_option);

if isempty(rt_option)
    rt_option = 'n';
elseif rt_option == 'y'
    disp(' ')
    disp('Note: Make sure you have Real-Time Kernel installed')
    disp('- Instruction to install the Kernel using MATLAB:')
    disp('https://www.mathworks.com/help/sldrt/ug/real-time-windows-target-kernel.html')
    pause(1)
    disp(' ')
    prompt = 'Would you like to continue in real-time? y/n [n]: ';
    rt_option = input(prompt,'s');
end
    
load_system('Model_vmaRHTS_R2019b.slx')

switch lower(rt_option)
    case 'y'
        set_param('Model_vmaRHTS_R2019b/Real-Time Synchronization','Commented','off')
        set_param('Model_vmaRHTS_R2019b/Missed Ticks','Commented','off')      
    case 'n'
        set_param('Model_vmaRHTS_R2019b/Real-Time Synchronization','Commented','on')
        set_param('Model_vmaRHTS_R2019b/Missed Ticks','Commented','on')
end

%=========================================================================%
%                         Uncertainty Plant Inquiry                        %
%=========================================================================% 
disp(' ')
disp('NOTE: The first simulation uses an idenfified model for the plant')
disp('WITHOUT uncertainties (nominal plant).')
prompt = 'Enter the number of additional trials WITH plant uncertainties [3]: ';
num_unc_sim = input(prompt);

if isempty(num_unc_sim)
    num_unc_sim = 3;
end

%=========================================================================%
%                        Showing plots preferences                        %
%=========================================================================% 
disp(' ')
prompt = 'Would you like to plot time-history results? y/n [n]: ';
plot_on = input(prompt,'s');    
if isempty(plot_on)
    plot_on = 'n';
end

%======================

disp(' ')
disp(' ')
disp('------------------------------------------------')
if rt_option == lower('n')
    disp('--> Running the maRTHS: Off-line...')
else
    disp('--> Running the maRTHS: Real-time...')
end
disp(' ')

