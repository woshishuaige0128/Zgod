%%  NOTE: *** Participants SHOULD NOT modify this file ***
%=========================================================================%
%                           Performance Indices                       
%=========================================================================% 
% See Secttion 3.7 "Evaluation Criteria" in the paper.
J1(i_RTHS,1)= finddelay(xa1_t,xa1m)/fs*1000;
J1(i_RTHS,2)= finddelay(xa2_t,xa2m)/fs*1000;

J2(i_RTHS,1) = std(xa1m-xa1_t)/std(xa1_t)*100;
J2(i_RTHS,2) = std(xa2m-xa2_t)/std(xa2_t)*100;

J3(i_RTHS,1)= max(abs(xa1m-xa1_t))/max(abs(xa1_t))*100;
J3(i_RTHS,2)= max(abs(xa2m-xa2_t))/max(abs(xa2_t))*100;

J4(i_RTHS,1)= finddelay(xa1_t,xa1m)/fs*1000;
J4(i_RTHS,2)= finddelay(xa2_t,xa2m)/fs*1000;

J5(i_RTHS,1)= std(xm_hat-xNum)/std(xNum)*100;
J5(i_RTHS,2)= std(rm_hat-rNum)/std(rNum)*100;

J6(i_RTHS,1)= max(abs(xm_hat-xNum))/max(abs(xNum))*100;
J6(i_RTHS,2)= max(abs(rm_hat-rNum))/max(abs(rNum))*100;

J7(i_RTHS,1)= std(xm_hat-xRef)/std(xRef)*100;
J7(i_RTHS,2)= std(rm_hat-rRef)/std(rRef)*100;

J8(i_RTHS,1)= std(xNum_2st-xRef_2st)/std(xRef_2st)*100;
J8(i_RTHS,2)= std(rNum_2st-rRef_2st)/std(rRef_2st)*100;
J8(i_RTHS,3)= std(xNum_3st-xRef_3st)/std(xRef_3st)*100;
J8(i_RTHS,4)= std(rNum_3st-rRef_3st)/std(rRef_3st)*100;

J9(i_RTHS,1)= max(abs(xm_hat-xRef))/max(abs(xRef))*100;
J9(i_RTHS,2)= max(abs(rm_hat-rRef))/max(abs(rRef))*100;

J10(i_RTHS,1)= max(abs(xNum_2st-xRef_2st))/max(abs(xRef_2st))*100;
J10(i_RTHS,2)= max(abs(rNum_2st-rRef_2st))/max(abs(rRef_2st))*100;
J10(i_RTHS,3)= max(abs(xNum_3st-xRef_3st))/max(abs(xRef_3st))*100;
J10(i_RTHS,4)= max(abs(rNum_3st-rRef_3st))/max(abs(rRef_3st))*100;

% IMPORTANT: The following code will execute after the last vmaRTHS simulation.
% ============================================================================

% Processing mean values of performances indices;
if i_RTHS == (1 + num_unc_sim)      

    if i_RTHS == 1
        J1avg = round(J1,1);
        J2avg = round(J2,1);
        J3avg = round(J3,1);
        J4avg = round(J4,1);
        J5avg = round(J5,1);
        J6avg = round(J6,1);
        J7avg = round(J7,1);
        J8avg = round(J8,1);
        J9avg = round(J9,1);
        J10avg = round(J10,1);
    else
        J1avg(1,1) = round(mean(J1(2:end,1)),1);
        J1avg(1,2) = round(mean(J1(2:end,2)),1);  
        
        J2avg(1,1) = round(mean(J2(2:end,1)),1);
        J2avg(1,2) = round(mean(J2(2:end,2)),1);
        
        J3avg(1,1) = round(mean(J3(2:end,1)),1);
        J3avg(1,2) = round(mean(J3(2:end,2)),1);
        
        J4avg(1,1) = round(mean(J4(2:end,1)),1);
        J4avg(1,2) = round(mean(J4(2:end,2)),1);
        
        J5avg(1,1) = round(mean(J5(2:end,1)),1);
        J5avg(1,2) = round(mean(J5(2:end,2)),1);
        
        J6avg(1,1) = round(mean(J6(2:end,1)),1);
        J6avg(1,2) = round(mean(J6(2:end,2)),1);
        
        J7avg(1,1) = round(mean(J7(2:end,1)),1);
        J7avg(1,2) = round(mean(J7(2:end,2)),1);
        
        J8avg(1,1) = round(mean(J8(2:end,1)),1);
        J8avg(1,2) = round(mean(J8(2:end,2)),1);
        J8avg(1,3) = round(mean(J8(2:end,3)),1);
        J8avg(1,4) = round(mean(J8(2:end,4)),1);
        
        J9avg(1,1) = round(mean(J9(2:end,1)),1);
        J9avg(1,2) = round(mean(J9(2:end,2)),1);
        
        J10avg(1,1) = round(mean(J10(2:end,1)),1);
        J10avg(1,2) = round(mean(J10(2:end,2)),1);
        J10avg(1,3) = round(mean(J10(2:end,3)),1);
        J10avg(1,4) = round(mean(J10(2:end,4)),1);
        
    end
    
    J_index_ALL = {J1 J2 J3 J4 J5 J6 J7 J8 J9 J10};
    J_index_AVG = {J1avg J2avg J3avg J4avg J5avg J6avg J7avg J8avg J9avg J10avg};
    %=====================================================================%
    %                           Saving Data                       
    %=====================================================================%
    % Saving data in folder "Results" 
    time = clock;
    time_test = strcat(num2str(time(1)),'_',... % Returns year 
        num2str(time(2)),'_',... % Returns month 
        num2str(time(3)),'_time',... % Returns day 
        num2str(time(4)),'_',... % returns hour 
        num2str(time(5)),'_',... % returns min 
        num2str(fix(time(6)))) ; 
    
    storage_dir = '.\Results\';
   
    if i_RTHS == 1
        file_name = [storage_dir,'Data_Nominal_',time_test];
    else
        file_name = [storage_dir,'Data_Uncert_',time_test];
    end
    save(file_name,'rths_Xa1t','rths_Xa2t','rths_Xa1m','rths_Xa2m','rths_Xa1m_hat','rths_Xa2m_hat',...
          'rths_Xm_hat','rths_Xnum','rths_Rm_hat','rths_Rnum','rths_Xref','rths_Rref',...
          'rths_Xref_2st','rths_Rref_2st','rths_Xref_3st','rths_Rref_3st',...
          'rths_Xnum_2st','rths_Rnum_2st','rths_Xnum_3st','rths_Rnum_3st',...
          'J_index_ALL','J_index_AVG')

    disp(' ')
    pause(2)
    disp('All time-history responses and performance indices were saved!')
    
    %=====================================================================%
    %                    Showing Final Results on Screen                      
    %=====================================================================%
    
    %Showing table of performance indices for Tracking control
    if i_RTHS == 1
      disp(' ')
      disp(' ')
      fprintf('*** The following Performance Indices correspond to the\n')
      fprintf('    virtual maRTHS with the identified model as the plant:\n')
      pause(2)
      input('    ...Press ''Enter'' to continue.','s');

    else
      disp(' ')
      disp(' ')
      fprintf('*** The following Performance Indices correspond to the average\n')
      fprintf('    of the %d virtual maRTHS with uncertainties in the plant:\n',num_unc_sim)
      pause(2)
      input('    ...Press ''Enter'' to continue.','s');
    end
    
    disp(' ')
    disp(' ')
    disp('===============================================================')
    disp('*                     PERFOMANCE INDICES                      *')
    disp('===============================================================')    
    disp(' ')
    
    %Showing table of indices for Tracking Control
    Index = ["Time delay J1,1"; "Time delay J1,2";"NRMS error J2,1";"NRMS error J2,2";"Max Peak error J3,1";"Max Peak error J3,2"];
    J_avg_values = [J1avg';J2avg';J3avg'];
    Units = ["ms"; "ms"; "%"; "%"; "%";"%"];
    J_Table_Tcontrol = table(Index,J_avg_values,Units);

    disp('                       Tracking Control                    ')
    disp('===============================================================')    
    disp(J_Table_Tcontrol)
    disp(' ')

    %Showing table of indices for Estimation
    Index = ["Time delay J4,1"; "Time delay J4,2";"NRMS error J5,X";"NRMS error J5,THETA";"Max Peak error J6,X";"Max Peak error J6,THETA"];
    J_avg_values = [J4avg';J5avg';J6avg'];
    Units = ["ms"; "ms"; "%"; "%"; "%";"%"];
    J_Table_Tcontrol = table(Index,J_avg_values,Units);

    disp('                          Estimation                       ')
    disp('===============================================================')    
    disp(J_Table_Tcontrol)
    disp(' ')
    
    %Showing table of indices for Global RTHS Performance
    Index = ["NRMS error J7,X"; "NRMS error J7,THETA"; "NRMS error J8,X 2nd st";"NRMS error J8,THETA 2nd st";"NRMS error J8,X 3rd st";"NRMS error J8,THETA 3rd st";...
        "Max Peak error J9,X"; "Max Peak error J9,THETA";...
        "Max Peak error J10,X 2nd st"; "Max Peak error J10,THETA 2nd st";"Max Peak error J10,X 3rd st";"Max Peak error J10,THETA 3rd st"];
    J_avg_values = [J7avg';J8avg';J9avg';J10avg'];
    Units = ["%"; "%"; "%"; "%"; "%";"%";"%"; "%"; "%"; "%"; "%";"%"];
    J_Table_Tcontrol = table(Index,J_avg_values,Units);
    
    disp('                   Global RTHS Performance                 ')
    disp('===============================================================')
    disp(J_Table_Tcontrol)
    disp('---------------------------------------------------------------')
    
    %Providing information for time-history data 
    disp('NOTE: The following data were saved in the folder "Results": ')
    disp('      1) Time-history responses. ')
    disp('      2) Performance indices for each virtual maRTHS. ')
    disp(' ')
    
    %Checking saturation of control input signals  
    max_signAct1= max(abs([rths_CMu1V{:}]));
    max_signAct2= max(abs([rths_CMu2V{:}]));
    cond_sat=0;
    contr_sat=0;
    
    k_dumm = 1;
    for jj=1:(1 + num_unc_sim)
        if max_signAct1(jj) > sat_limit && max_signAct2(jj) > sat_limit
            cond_sat = 1;
            contr_sat(k_dumm) = jj;
            k_dumm = k_dumm + 1;
        else 
            cond_sat=0;
        end
    end
 
     disp('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')
    if cond_sat == 0
        disp('The control input signals for Actuator 1 and 2 are below')
        disp('the saturation limit:');
        disp('===============================================================')
        disp('           >> The controller IS realizable <<')
        disp('===============================================================')
    else 
        disp('WARNING: The control input signals of one or both actuators')
        disp('have reached the saturation limit!');
        disp('Check the responses in the following iterations:');
        for i=1:length(contr_sat)
            fprintf('     Iteration # %d  \n',contr_sat(i));
        end
        disp('===============================================================')
        disp('        !!! The controller IS NOT realizable !!!')
        disp('===============================================================')

        % If the user didn't plot, ask again : Would you like to see time-history responses now?              
        
    end
    
    switch lower(plot_on)
        case 'y'
        Plot_Results
    end
    
end

 