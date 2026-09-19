%%% MATERIAL PROPERTIES  MP
Lb = 762/1000;                      % Beam length (m)
Lc = 635/1000;                      % Column length (m)
Ic = 2.520*(25.4/1000)^4;           % 2nd Moment of Area x column (m^4)
Ib = 0.6132*(25.4/1000)^4;          % 2nd Moment of Area x beam (m^4)
Ac = 1.670*(25.4/1000)^2;           % Cross sectional Area column (m^2)
Ab = 0.947*(25.4/1000)^2;           % Cross sectional Area beam (m^2)

% M5
Lb = 762/1000;                          % Beam length (m)
Lc = 641.35/1000;                       % Column length (m)
tuningF_beam = 1;
tuningF_col = 0.7;
Ic = 2.520*(25.4/1000)^4*tuningF_col;   % 2nd Moment of Area x column (m^4)
Ib = 4.21372e-7*tuningF_beam;           % 2nd Moment of Area x beam (m^4)
Ac = 1.670*(25.4/1000)^2;               % Cross sectional Area column (m^2)
Ab = 7.56e-4;                           % Cross sectional Area beam (m^2)
