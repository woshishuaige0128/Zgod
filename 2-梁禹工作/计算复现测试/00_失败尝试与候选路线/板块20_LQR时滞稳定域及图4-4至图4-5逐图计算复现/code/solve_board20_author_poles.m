function result = solve_board20_author_poles(matrices, route_formula, l, j)
%SOLVE_BOARD20_AUTHOR_POLES Solve one author-formula delay point.
%
%   RESULT = SOLVE_BOARD20_AUTHOR_POLES(MATRICES, ROUTE_FORMULA, L, J)
%   constructs the Laurent matrix G(z) used by the frozen author programs,
%   clears its negative powers, and solves the resulting numerical matrix
%   polynomial with a first companion generalized eigenvalue pencil.
%
%   Required MATRICES fields for every route:
%       M, C1, K1, C2, K2, al, dt
%
%   Additional required fields for DIV2_H_LEFT_FEEDBACK_OUTSIDE:
%       S, DeltaC, DeltaK
%
%   ROUTE_FORMULA must be exactly one of:
%       ORI_DIV1_H_RIGHT
%           H = diag(z^-L at DOF 1, z^-J at DOF 6), and the delayed
%           term is ((z-1)/(z*dt)*C2 + K2) * H.
%       GUYAN_DIV1_H_LEFT
%           H = diag(z^-L at DOF 1, z^-J at DOF 2), and the delayed
%           term is H * ((z-1)/(z*dt)*C2 + K2).
%       DIV2_H_LEFT_FEEDBACK_OUTSIDE
%           The same left-H term as GUYAN_DIV1_H_LEFT, plus
%           S' * ((z-1)/(z*dt)*DeltaC + DeltaK) * S outside H.
%
%   This function deliberately does not infer Q, R, alpha, missing DOFs, or
%   any matrix from historical MAT stability masks.  L and J are integer
%   sample delays, not milliseconds.
%
%   RESULT fields:
%       poles                     finite nonzero retained roots (column)
%       raw_roots                 all generalized eigenvalues, including
%                                 Inf/NaN and clearing-origin roots
%       rho                       max(abs(poles))
%       poly_degree               degree of the cleared matrix polynomial
%       clearing_power            scalar z power used to clear G(z)
%       removed_zero_root_count   numerical origin roots removed only when
%                                 clearing_power > 0
%       retained_root_count       number of entries in poles
%       max_relative_residual     maximum polynomial eigenpair backward
%                                 residual over retained roots
%       point_status              'PASS' or 'FAIL'
%       stable                    PASS and 0 < rho < 1
%       critical                  PASS and abs(rho - 1) <= 1e-8
%       diagnostic                auditable construction/solver details
%
%   Invalid input contracts throw an error.  Numerical solution failures
%   are returned as point_status='FAIL' with the reason in diagnostic.
%
%   Complexity disclosure: the current verified core uses a dense first
%   companion pencil of order matrix_order * poly_degree.  It is intended
%   for single-point verification and small pilot batches.  A 15-DOF,
%   delay-66 point would create a roughly 1000-order pencil; callers must
%   not use this baseline for a full 31-by-67 grid without a separately
%   validated structure-aware/deflated implementation.

    [matrices, route_formula, l, j, n, delay_dofs] = ...
        validate_input_contract(matrices, route_formula, l, j);

    result = initialize_result(route_formula, l, j, n);

    try
        [coefficients, exponents] = build_laurent_coefficients( ...
            matrices, route_formula, l, j, n, delay_dofs);

        nonzero_coefficient = cellfun(@has_exact_nonzero, coefficients);
        if ~any(nonzero_coefficient)
            error('board20:solver:IdenticallyZero', ...
                'Every Laurent coefficient matrix is zero; det(G(z)) is not a regular characteristic equation.');
        end

        first = find(nonzero_coefficient, 1, 'first');
        last = find(nonzero_coefficient, 1, 'last');
        coefficients = coefficients(first:last);
        exponents = exponents(first:last);

        min_exponent = exponents(1);
        max_exponent = exponents(end);
        clearing_power = max(0, -min_exponent);
        shifted_exponents = exponents + clearing_power;
        poly_degree = max(shifted_exponents);

        polynomial = repmat({zeros(n)}, 1, poly_degree + 1);
        for k = 1:numel(coefficients)
            polynomial{shifted_exponents(k) + 1} = coefficients{k};
        end

        % Remove only exactly absent highest matrix coefficients.  No
        % tolerance-based degree fitting is permitted.
        while numel(polynomial) > 1 && ~has_exact_nonzero(polynomial{end})
            polynomial(end) = [];
        end
        poly_degree = numel(polynomial) - 1;

        result.poly_degree = poly_degree;
        result.clearing_power = clearing_power;
        result.diagnostic.laurent_min_exponent = min_exponent;
        result.diagnostic.laurent_max_exponent = max_exponent;
        result.diagnostic.coefficient_exponents = exponents;
        result.diagnostic.coefficient_frobenius_norms = ...
            cellfun(@(a) norm(a, 'fro'), coefficients);
        result.diagnostic.linearization = 'dense_first_companion_generalized_eigenvalue_pencil';
        result.diagnostic.linearization_order = n * poly_degree;

        if poly_degree < 1
            error('board20:solver:ConstantCharacteristicMatrix', ...
                'The cleared characteristic matrix is constant; a finite pole set is not defined by this route point.');
        end

        [raw_roots, eigenvectors] = solve_first_companion(polynomial);
        result.raw_roots = raw_roots(:);

        finite_mask = isfinite(real(raw_roots)) & isfinite(imag(raw_roots));
        nan_mask = isnan(real(raw_roots)) | isnan(imag(raw_roots));
        infinite_mask = ~finite_mask & ~nan_mask;

        finite_abs = abs(raw_roots(finite_mask));
        finite_nonzero_abs = finite_abs(finite_abs > 0);
        if isempty(finite_nonzero_abs)
            finite_root_scale = 1;
        else
            finite_root_scale = max(1, median(finite_nonzero_abs));
        end
        zero_tolerance = max(1e-12, ...
            100 * eps('double') * max(1, n * poly_degree) * finite_root_scale);

        % z=0 is outside the original Laurent equation whenever negative
        % powers were cleared.  Therefore only numerical-origin roots and
        % only in that case are removable as clearing artifacts.
        zero_mask = false(size(raw_roots));
        if clearing_power > 0
            zero_mask = finite_mask & (abs(raw_roots) <= zero_tolerance);
        end
        retained_mask = finite_mask & ~zero_mask;
        retained_indices = find(retained_mask);
        poles = raw_roots(retained_indices);

        result.poles = poles(:);
        result.removed_zero_root_count = nnz(zero_mask);
        result.retained_root_count = numel(poles);
        result.diagnostic.zero_root_tolerance = zero_tolerance;
        result.diagnostic.finite_raw_root_count = nnz(finite_mask);
        result.diagnostic.infinite_raw_root_count = nnz(infinite_mask);
        result.diagnostic.nan_raw_root_count = nnz(nan_mask);
        result.diagnostic.removal_rule = ...
            'clearing_power>0 AND finite root magnitude<=zero_root_tolerance';

        if isempty(poles)
            error('board20:solver:NoRetainedFiniteRoots', ...
                'No finite nonzero roots remained after removing traceable clearing-origin roots.');
        end
        result.rho = max(abs(poles));
        if ~(isfinite(result.rho) && result.rho > 0)
            error('board20:solver:InvalidRho', ...
                'rho must be finite and strictly positive, but was %.17g.', result.rho);
        end
        if any(nan_mask)
            error('board20:solver:NaNGeneralizedEigenvalue', ...
                'The generalized eigenvalue pencil returned %d NaN roots.', nnz(nan_mask));
        end

        residuals = zeros(numel(poles), 1);
        for k = 1:numel(poles)
            linearized_vector = eigenvectors(:, retained_indices(k));
            physical_vector = linearized_vector(end-n+1:end);
            residuals(k) = polynomial_eigenpair_residual( ...
                polynomial, poles(k), physical_vector);
        end
        result.diagnostic.retained_root_relative_residuals = residuals;
        result.max_relative_residual = max(residuals);

        if ~isfinite(result.max_relative_residual)
            error('board20:solver:NonfiniteResidual', ...
                'At least one retained polynomial eigenpair residual is nonfinite.');
        end
        if result.max_relative_residual > 1e-8
            error('board20:solver:ResidualGateFailed', ...
                'Maximum relative residual %.17g exceeds the fixed 1e-8 gate.', ...
                result.max_relative_residual);
        end

        result.point_status = 'PASS';
        result.stable = result.rho < 1;
        result.critical = abs(result.rho - 1) <= 1e-8;
        result.diagnostic.identifier = '';
        result.diagnostic.message = 'All finite retained roots passed the fixed 1e-8 relative-residual gate.';
    catch ME
        result.point_status = 'FAIL';
        result.stable = false;
        result.critical = false;
        result.diagnostic.identifier = ME.identifier;
        result.diagnostic.message = ME.message;
    end
end


function [matrices, route_formula, l, j, n, delay_dofs] = ...
        validate_input_contract(matrices, route_formula, l, j)
    if ~(isstruct(matrices) && isscalar(matrices))
        error('board20:solver:InvalidMatricesStruct', ...
            'matrices must be a scalar struct.');
    end

    if isstring(route_formula)
        if ~isscalar(route_formula)
            error('board20:solver:InvalidRouteFormula', ...
                'route_formula must be a character vector or scalar string.');
        end
        route_formula = char(route_formula);
    end
    if ~(ischar(route_formula) && isrow(route_formula))
        error('board20:solver:InvalidRouteFormula', ...
            'route_formula must be a character vector or scalar string.');
    end
    route_formula = upper(strtrim(route_formula));
    allowed = {'ORI_DIV1_H_RIGHT', 'GUYAN_DIV1_H_LEFT', ...
        'DIV2_H_LEFT_FEEDBACK_OUTSIDE'};
    if ~any(strcmp(route_formula, allowed))
        error('board20:solver:InvalidRouteFormula', ...
            'Unsupported route_formula "%s". No formula inference is allowed.', route_formula);
    end

    validate_delay(l, 'l');
    validate_delay(j, 'j');
    l = double(l);
    j = double(j);

    required = {'M', 'C1', 'K1', 'C2', 'K2', 'al', 'dt'};
    for k = 1:numel(required)
        if ~isfield(matrices, required{k})
            error('board20:solver:MissingMatrixField', ...
                'matrices.%s is required.', required{k});
        end
    end

    validate_numeric_matrix(matrices.M, 'M');
    n = size(matrices.M, 1);
    if size(matrices.M, 2) ~= n || n < 1
        error('board20:solver:InvalidMatrixShape', ...
            'matrices.M must be a nonempty square matrix.');
    end

    square_fields = {'C1', 'K1', 'C2', 'K2', 'al'};
    for k = 1:numel(square_fields)
        value = matrices.(square_fields{k});
        validate_numeric_matrix(value, square_fields{k});
        if ~isequal(size(value), [n, n])
            error('board20:solver:MatrixSizeMismatch', ...
                'matrices.%s must have size %d-by-%d.', square_fields{k}, n, n);
        end
    end

    if ~(isnumeric(matrices.dt) && isreal(matrices.dt) && ...
            isscalar(matrices.dt) && isfinite(matrices.dt) && matrices.dt > 0)
        error('board20:solver:InvalidTimeStep', ...
            'matrices.dt must be one finite positive real scalar.');
    end

    if rcond(double(matrices.al)) <= eps('double')
        error('board20:solver:SingularAlpha', ...
            'matrices.al must be numerically nonsingular for the author M/al operation.');
    end

    fields_to_double = {'M', 'C1', 'K1', 'C2', 'K2', 'al', 'dt'};
    for k = 1:numel(fields_to_double)
        matrices.(fields_to_double{k}) = double(matrices.(fields_to_double{k}));
    end

    switch route_formula
        case 'ORI_DIV1_H_RIGHT'
            if n < 6
                error('board20:solver:RouteDimensionMismatch', ...
                    'ORI_DIV1_H_RIGHT requires matrix order at least 6 for author delay DOFs [1,6].');
            end
            delay_dofs = [1, 6];
        case 'GUYAN_DIV1_H_LEFT'
            if n < 2
                error('board20:solver:RouteDimensionMismatch', ...
                    'GUYAN_DIV1_H_LEFT requires matrix order at least 2 for author delay DOFs [1,2].');
            end
            delay_dofs = [1, 2];
        case 'DIV2_H_LEFT_FEEDBACK_OUTSIDE'
            if n < 2
                error('board20:solver:RouteDimensionMismatch', ...
                    'DIV2_H_LEFT_FEEDBACK_OUTSIDE requires matrix order at least 2.');
            end
            delay_dofs = [1, 2];
            feedback_fields = {'S', 'DeltaC', 'DeltaK'};
            for k = 1:numel(feedback_fields)
                if ~isfield(matrices, feedback_fields{k})
                    error('board20:solver:MissingMatrixField', ...
                        'matrices.%s is required by DIV2_H_LEFT_FEEDBACK_OUTSIDE.', ...
                        feedback_fields{k});
                end
                validate_numeric_matrix(matrices.(feedback_fields{k}), feedback_fields{k});
                matrices.(feedback_fields{k}) = double(matrices.(feedback_fields{k}));
            end
            if size(matrices.S, 2) ~= n
                error('board20:solver:FeedbackSizeMismatch', ...
                    'matrices.S must have %d columns.', n);
            end
            feedback_order = size(matrices.S, 1);
            if ~isequal(size(matrices.DeltaC), [feedback_order, feedback_order]) || ...
                    ~isequal(size(matrices.DeltaK), [feedback_order, feedback_order])
                error('board20:solver:FeedbackSizeMismatch', ...
                    'DeltaC and DeltaK must be square with order size(S,1)=%d.', feedback_order);
            end
    end
end


function validate_numeric_matrix(value, field_name)
    if ~(isnumeric(value) && ismatrix(value) && isreal(value) && ...
            ~isempty(value) && all(isfinite(value(:))))
        error('board20:solver:InvalidNumericMatrix', ...
            'matrices.%s must be a nonempty finite real numeric matrix.', field_name);
    end
end


function validate_delay(value, name)
    if ~(isnumeric(value) && isreal(value) && isscalar(value) && ...
            isfinite(value) && value >= 0 && value == fix(value))
        error('board20:solver:InvalidDelay', ...
            '%s must be one finite nonnegative integer sample delay.', name);
    end
end


function result = initialize_result(route_formula, l, j, n)
    result = struct();
    result.poles = complex(zeros(0, 1));
    result.raw_roots = complex(zeros(0, 1));
    result.rho = NaN;
    result.poly_degree = NaN;
    result.clearing_power = NaN;
    result.removed_zero_root_count = 0;
    result.retained_root_count = 0;
    result.max_relative_residual = NaN;
    result.point_status = 'FAIL';
    result.stable = false;
    result.critical = false;
    result.diagnostic = struct( ...
        'identifier', '', ...
        'message', 'Solver not yet executed.', ...
        'route_formula', route_formula, ...
        'l', l, ...
        'j', j, ...
        'matrix_order', n, ...
        'source_formula_policy', ...
            'frozen_author_code_only_no_Q_R_alpha_or_historical_MAT_inference');
end


function [coefficients, exponents] = build_laurent_coefficients( ...
        matrices, route_formula, l, j, n, delay_dofs)
    delays = [l, j];
    lowest_requested_exponent = -(max(delays) + 1);
    exponents = lowest_requested_exponent:1;
    coefficients = repmat({zeros(n)}, 1, numel(exponents));

    mass_term = (matrices.M / matrices.al) / (matrices.dt ^ 2);
    coefficients = add_coefficient(coefficients, exponents, 1, mass_term);
    coefficients = add_coefficient(coefficients, exponents, 0, ...
        -2 * mass_term + matrices.C1 / matrices.dt + matrices.K1);
    coefficients = add_coefficient(coefficients, exponents, -1, ...
        mass_term - matrices.C1 / matrices.dt);

    delayed_zero = matrices.C2 / matrices.dt + matrices.K2;
    delayed_minus_one = -matrices.C2 / matrices.dt;

    for channel = 1:2
        selector = zeros(n);
        selector(delay_dofs(channel), delay_dofs(channel)) = 1;
        if strcmp(route_formula, 'ORI_DIV1_H_RIGHT')
            coefficient_at_delay = delayed_zero * selector;
            coefficient_after_delay = delayed_minus_one * selector;
        else
            coefficient_at_delay = selector * delayed_zero;
            coefficient_after_delay = selector * delayed_minus_one;
        end
        coefficients = add_coefficient(coefficients, exponents, ...
            -delays(channel), coefficient_at_delay);
        coefficients = add_coefficient(coefficients, exponents, ...
            -(delays(channel) + 1), coefficient_after_delay);
    end

    if strcmp(route_formula, 'DIV2_H_LEFT_FEEDBACK_OUTSIDE')
        feedback_zero = matrices.S' * ...
            (matrices.DeltaC / matrices.dt + matrices.DeltaK) * matrices.S;
        feedback_minus_one = matrices.S' * ...
            (-matrices.DeltaC / matrices.dt) * matrices.S;
        coefficients = add_coefficient(coefficients, exponents, 0, feedback_zero);
        coefficients = add_coefficient(coefficients, exponents, -1, feedback_minus_one);
    end
end


function coefficients = add_coefficient(coefficients, exponents, exponent, value)
    location = find(exponents == exponent, 1);
    if isempty(location)
        error('board20:solver:InternalExponentRange', ...
            'Internal Laurent exponent %d was not allocated.', exponent);
    end
    coefficients{location} = coefficients{location} + value;
end


function tf = has_exact_nonzero(matrix)
    tf = any(matrix(:) ~= 0);
end


function [roots, vectors] = solve_first_companion(polynomial)
    degree = numel(polynomial) - 1;
    n = size(polynomial{1}, 1);

    coefficient_scale = max(cellfun(@(a) norm(a, 'fro'), polynomial));
    if ~(isfinite(coefficient_scale) && coefficient_scale > 0)
        error('board20:solver:InvalidCoefficientScale', ...
            'The matrix-polynomial coefficient scale is not finite and positive.');
    end
    scaled = cellfun(@(a) a / coefficient_scale, polynomial, ...
        'UniformOutput', false);

    pencil_order = n * degree;
    A = zeros(pencil_order);
    B = zeros(pencil_order);
    for block = 1:degree
        columns = (block - 1) * n + (1:n);
        coefficient_index = degree - block + 1;
        A(1:n, columns) = -scaled{coefficient_index};
    end
    B(1:n, 1:n) = scaled{degree + 1};

    if degree > 1
        identity_columns = 1:(n * (degree - 1));
        identity_rows = n + (1:(n * (degree - 1)));
        A(identity_rows, identity_columns) = eye(n * (degree - 1));
        B(identity_rows, n + identity_columns) = eye(n * (degree - 1));
    end

    [vectors, diagonal] = eig(A, B);
    roots = diag(diagonal);
end


function residual = polynomial_eigenpair_residual(polynomial, root, vector)
    vector_norm = norm(vector, 2);
    if ~(isfinite(vector_norm) && vector_norm > 0)
        residual = Inf;
        return;
    end

    degree = numel(polynomial) - 1;
    value_times_vector = polynomial{degree + 1} * vector;
    denominator = norm(polynomial{degree + 1}, 'fro') * vector_norm;
    for exponent = degree-1:-1:0
        value_times_vector = root * value_times_vector + ...
            polynomial{exponent + 1} * vector;
        denominator = abs(root) * denominator + ...
            norm(polynomial{exponent + 1}, 'fro') * vector_norm;
    end

    if denominator == 0
        residual = Inf;
    else
        residual = norm(value_times_vector, 2) / denominator;
    end
end
