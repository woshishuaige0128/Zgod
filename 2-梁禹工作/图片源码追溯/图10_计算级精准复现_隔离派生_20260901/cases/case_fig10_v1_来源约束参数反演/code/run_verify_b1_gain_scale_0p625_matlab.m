function summary = run_verify_b1_gain_scale_0p625_matlab()
%RUN_VERIFY_B1_GAIN_SCALE_0P625_MATLAB Fixed blind validation entry point.
%
% This wrapper intentionally points only to the B1 gain_scale=0.625 blind
% manifest, its completed Python full-grid root, and a new isolated MATLAB
% validation output.  The generic verifier remains reusable for later final
% candidates through its three explicit path arguments.

    code_dir = fileparts([mfilename('fullpath'), '.m']);
    case_dir = fileparts(code_dir);
    manifest_path = fullfile(case_dir, 'data', 'blind_manifests', ...
        'gain_scale_0p625_target_guided_inferred', 'B1.json');
    python_fullgrid_root = fullfile(case_dir, 'data', 'blind_outputs', ...
        'coarse_gain_sweep', 'gain_scale_0p625', 'B1');
    output_dir = fullfile(case_dir, 'data', ...
        'matlab_independent_fullgrid_validation', ...
        'gain_scale_0p625', 'B1');
    summary = verify_fig10_blind_fullgrid_matlab( ...
        manifest_path, python_fullgrid_root, output_dir);
end
