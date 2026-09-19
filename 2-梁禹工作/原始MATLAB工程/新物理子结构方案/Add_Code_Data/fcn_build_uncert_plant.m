function [A,B,C,D, h1z_1u,h1z_2u,h1p_1u,h1p_2u,frame_pole_1u,  ...
          h12z_1u, h2p_1u, h2p_2u, h22z_1u ] = f_build_uncert_ControlPlant()

% Definition of the NOMINAL MODEL
% ***********************************************************
   foutREF = [0.01:0.01:110]'*2*pi;

% Poles of the numerical substtructure (frame):
    frame_pole_1 = (-50-63j)*2*pi;
    frame_pole_2 = (-50+63j)*2*pi;
    
% Poles and zeros of the first column of H (i.e. H11 and H21):    
    h1z_1 = -120*2*pi;     h1z_2 = -90*2*pi;      %zeros for H11 and H21
    h1p_1 = -2.65*2*pi;     h1p_2 = -40*2*pi;       %poles for H11 and H21
    gain_11 = 2165.2;
    gain_21 = 349.95;

% Poles and zeros of the second column of H(i.e. H12 and H22):    
    h12z_1 = -3*2*pi;                               %zeros for H12
    h22z_1 = -5*2*pi;                               %zeros for H22
    h2p_1 = -3.5*2*pi;     h2p_2 = -18.5*2*pi;      %poles for H12 and H22
    gain_12 = 4.5394e6;
    gain_22 = 1.9238e7;
    
        %H11:
        zeros = [h1z_1 h1z_2];                    
        poles = [h1p_1 h1p_2 frame_pole_1 frame_pole_2];
        gain = gain_11;
        
        H_u = zpk(zeros, poles,gain);
        [magACT,phaseACT,fout] = bode(H_u,foutREF);
                       
        magH = 20*log10(squeeze(magACT));
        magREF11 = 10^(magH(1)/20);
        
        %H21:
        gain = gain_21;
        H_u = zpk(zeros, poles,gain);
        [magACT,phaseACT,fout] = bode(H_u);
        
        magH = 20*log10(squeeze(magACT));
        magREF21 = 10^(magH(1)/20);
        
        %H12:
        zeros = [h12z_1];
        poles = [h2p_1 h2p_2 frame_pole_1 frame_pole_2];
        gain = gain_12;

        H_u = zpk(zeros, poles,gain);
        [magACT,phaseACT,fout] = bode(H_u);
        
        magH = 20*log10(squeeze(magACT));
        magREF12 = 10^(magH(1)/20);
        
        %H22:
        zeros = [h22z_1];
        poles = [h2p_1 h2p_2 frame_pole_1 frame_pole_2];
        gain = gain_22;
                       
        H_u = zpk(zeros, poles,gain);
        [magACT,phaseACT,fout] = bode(H_u);
        
        magH = 20*log10(squeeze(magACT));
        magREF22 = 10^(magH(1)/20);           

       
% UNCERTAINTIES: Defining the SIMULATED control plant
% ***********************************************************      

% Constructing the family of TF of the plant.

    %Standard deviation for H11 and H21:
    std1_z1 = 0.01*h1z_1;      %0.055
    std1_z2 = 0.01*h1z_2;      %0.055
    std1_p1 = 0.03*h1p_1;       %0.06
    std1_p2 = 0.03*h1p_2;       %0.06
       
    %Standard deviation for H12 and H22:
    std2_z1 = 0.01*h12z_1;      %0.03
    std2_z2 = 0.01*h22z_1;      %0.03
    std2_p1 = 0.0*h2p_1;       %0.03
    std2_p2 = 0.02*h2p_2;       %0.03
    
    %standard deviation for frame's poles:
    std_f_p_1 = 0.01*frame_pole_1;  %0.05

    freqLIMIT = 100;
 
    %Random TF:
    %H11:
        h1z_1u = h1z_1 + std1_z1*randn(1,1);
        h1z_2u = h1z_2 + std1_z2*randn(1,1);
        h1p_1u = h1p_1 + std1_p1*randn(1,1);
        h1p_2u = h1p_2 + std1_p2*randn(1,1);           
        frame_pole_1u = frame_pole_1 + std_f_p_1*randn(1,1); 
        frame_pole_2u = complex(real(frame_pole_1u),-imag(frame_pole_1u));

        zeros = [h1z_1u h1z_2u];                    
        poles = [h1p_1u h1p_2u frame_pole_1u frame_pole_2u];
        gain = gain_11;
        
        H_u = zpk(zeros, poles,gain);
        [magACT_unc,phaseACT_unc,fout_unc] = bode(H_u,foutREF);
                       
        magH = 20*log10(squeeze(magACT_unc));
        magREF = 10^(magH(1)/20);
        ratioMAG11= magREF11/magREF;
        H11u = zpk(zeros, poles,gain*ratioMAG11);
    
    %H21:
        gain = gain_21;
        
        H_u = zpk(zeros, poles,gain);
        [magACT_unc,phaseACT_unc,fout_unc] = bode(H_u);
        
        magH = 20*log10(squeeze(magACT_unc));
        magREF = 10^(magH(1)/20);
        ratioMAG21= magREF21/magREF;
        H21u = zpk(zeros, poles,gain*ratioMAG21);

    %H12:
        h12z_1u = h12z_1 + std2_z1*randn(1,1);
        h2p_1u = h2p_1 + std2_p1*randn(1,1);
        h2p_2u = h2p_2 + std2_p2*randn(1,1);                      
        
        zeros = [h12z_1u];
        poles = [h2p_1u h2p_2u frame_pole_1u frame_pole_2u];
        gain = gain_12;

        H_u = zpk(zeros, poles,gain);
        [magACT_unc,phaseACT_unc,fout_unc] = bode(H_u);
        
        magH = 20*log10(squeeze(magACT_unc));
        magREF = 10^(magH(1)/20);
        ratioMAG12= magREF12/magREF;
        H12u = zpk(zeros, poles,gain*ratioMAG12);
        
    %H22
        h22z_1u = h22z_1 + std2_z2*randn(1,1);
        
        zeros = [h22z_1u];
        poles = [h2p_1u h2p_2u frame_pole_1u frame_pole_2u];
        gain = gain_22;
                       
        H_u = zpk(zeros, poles,gain);
        [magACT_unc,phaseACT_unc,fout_unc] = bode(H_u);
        
        magH = 20*log10(squeeze(magACT_unc));
        magREF = 10^(magH(1)/20);
        ratioMAG22= magREF22/magREF;
        H22u = zpk(zeros, poles,gain*ratioMAG22); 
        
% Transfer Function Matrix:
    plantFRAME_TFv = [H11u H12u; H21u H22u];
% State-Space system
    plantFRAME_StateS = ss(plantFRAME_TFv);
    A = plantFRAME_StateS.a; B = plantFRAME_StateS.b; C = plantFRAME_StateS.c; D = plantFRAME_StateS.d;
    
end