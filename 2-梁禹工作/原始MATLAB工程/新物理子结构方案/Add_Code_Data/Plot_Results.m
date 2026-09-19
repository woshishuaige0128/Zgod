%%  NOTE: *** Participants SHOULD NOT modify this file ***
%                          ----------

%=========================================================================%
%                       PLOTTING RESULTS (if desired)                      
%=========================================================================% 
    switch EQ_sw
    case 1       
         xlimEQ = [5 40];
        xlim1=[7 8]; xlim2=[14 15]; xlim3=[31 32];
    case 2        
        xlimEQ = [5 40];
        xlim1=[8.5 9.5]; xlim2=[10 12]; xlim3=[14 15];
    case 3       
        xlimEQ = [5 30];
        xlim1=[7 8]; xlim2=[9.5 11]; xlim3=[11.3 13];
    end 

    screen_size = get(0,'ScreenSize');
      
for ii = 1:(1 + num_unc_sim)
    
    if ii == 1
        type_vRTHS = 'Virtual maRTHS with Nominal Plant';        
    else
        type_vRTHS = ['Virtual maRTHS with Uncertainties in the Plant - Trial # ',num2str(ii-1)];    
    end
    
    %Target Displacement vs Measured actuator displacement:
    figure   
    FSize0 = 13;
    set(gcf,'position',[screen_size(3)/10,screen_size(4)/10,screen_size(3)*0.8,screen_size(4)*0.8])
    
    subplot(2,3,[1,3])
    plot(t,rths_Xa1m{ii} ,'-b','LineWidth',2), hold on;
    plot(t,rths_Xa1t{ii},'-.g','LineWidth',2); grid on
    title({'Target vs Measured Displacement - Actuator 1',type_vRTHS})
    xlabel('Time [s]'), ylabel('Displacement [mm]'); xlim(xlimEQ);
    set(gca,'FontSize',FSize0), set(gca,'linewidth',2)
    LEG= legend('Measured','Target'); legend boxoff
    
    subplot(2,3,4), xlabel('Time [s]'), ylabel('Displacement [mm]')
    plot(t,rths_Xa1m{ii},'-b','LineWidth',2), hold on
    plot(t,rths_Xa1t{ii},'-.g','LineWidth',2); grid on
    xlim(xlim1); xlabel('Time [s]'), ylabel('Displacement [mm]')
    set(gca,'FontSize',FSize0), set(gca,'linewidth',2)
    
    subplot(2,3,5), xlabel('Time [s]'), ylabel('Displacement [mm]')
    plot(t,rths_Xa1m{ii},'-b','LineWidth',2), hold on
    plot(t,rths_Xa1t{ii},'-.g','LineWidth',2); grid on
    xlim(xlim2); xlabel('Time [s]'), ylabel('Displacement [mm]')
    set(gca,'FontSize',FSize0), set(gca,'linewidth',2)
    
    subplot(2,3,6), xlabel('Time [s]'), ylabel('Displacement [mm]')
    plot(t,rths_Xa1m{ii},'-b','LineWidth',2), hold on
    plot(t,rths_Xa1t{ii},'-.g','LineWidth',2); grid on
    xlim(xlim3); xlabel('Time [s]'), ylabel('Displacement [mm]')
    set(gca,'FontSize',FSize0), set(gca,'linewidth',2)
    
    %Target Displacement vs Measured actuator displacement:
    figure   
    FSize0 = 13;
    set(gcf,'position',[screen_size(3)/10,screen_size(4)/10,screen_size(3)*0.8,screen_size(4)*0.8])

    subplot(2,3,[1,3])    
    plot(t,rths_Xa2m{ii},'-r','LineWidth',2); hold on;
    title({'Target vs Measured Displacement - Actuator 2',type_vRTHS})
    plot(t,rths_Xa2t{ii},'-.g','LineWidth',2), grid on, 
    xlabel('Time [s]'), ylabel('Displacement [mm]'), xlim(xlimEQ);
    set(gca,'FontSize',FSize0), set(gca,'linewidth',2)
    LEG= legend('Measured','Target'); legend boxoff
    
    subplot(2,3,4), xlabel('Time [s]'), ylabel('Displacement [mm]')
    plot(t,rths_Xa2m{ii},'-r','LineWidth',2); hold on,
    plot(t,rths_Xa2t{ii},'-.g','LineWidth',2), grid on
    xlim(xlim1); xlabel('Time [s]'), ylabel('Displacement [mm]')
    set(gca,'FontSize',FSize0), set(gca,'linewidth',2)
    
    subplot(2,3,5), xlabel('Time [s]'), ylabel('Displacement [mm]')
    plot(t,rths_Xa2m{ii},'-r','LineWidth',2); hold on,
    plot(t,rths_Xa2t{ii},'-.g','LineWidth',2), grid on
    xlim(xlim2); xlabel('Time [s]'), ylabel('Displacement [mm]')
    set(gca,'FontSize',FSize0), set(gca,'linewidth',2)
    
    subplot(2,3,6), xlabel('Time [s]'), ylabel('Displacement [mm]')
    plot(t,rths_Xa2m{ii},'-r','LineWidth',2); hold on,
    plot(t,rths_Xa2t{ii},'-.g','LineWidth',2), grid on
    xlim(xlim3); xlabel('Time [s]'), ylabel('Displacement [mm]')
    set(gca,'FontSize',FSize0), set(gca,'linewidth',2)
    
end