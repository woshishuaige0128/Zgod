# Robust Decentralized Adaptive Compensation for the Multi-Axial Real-Time Hybrid Simulation Benchmark
#### María E. Quiroz<sup>1</sup>, Cristóbal Gálmez<sup>1</sup>, Gastón A. Fermandois<sup>1</sup>
<sup>1</sup> Departamento de Obras Civiles, Universidad Técnica Federico Santa María, Valparaíso, Chile
![maRTHS](https://github.com/FermandoisLab/maRTHS-bmk-RoDeAC/assets/81593865/0e37fffe-7754-4a0b-9fff-5356b3300669)

## Abstract
Real-time hybrid simulation (RTHS) is a powerful and highly reliable technique integrating experimental testing with numerical modeling for studying rate-dependent components under realistic conditions. One of its key advantages is its cost-effectiveness compared to large-scale shake table testing, which is attained by selectively conducting experimental testing on critical parts of the analyzed structure, thus avoiding the assembly of the entire system. One of the fundamental advancements in RTHS methods is the development of multi-dimensional dynamic testing. In particular, multi-axial RTHS (maRTHS) aims to prescribe multiple-degree-of-freedom (MDOF) loading from the numerical substructure over the test specimen. Under these conditions, synchronization is a significant challenge in multiple actuator loading assemblies. This study proposes a robust and decentralized adaptive compensation (RoDeAC) method for the next-generation maRTHS benchmark problem. An initial calibration of the dynamic compensator is carried out through offline numerical simulations. Subsequently, the parameters are then updated in real-time during the test using a recursive least squares adaptive algorithm. The results demonstrate outstanding performance in experiment synchronization, even in uncertain conditions, due to variability of reference structure, seismic loading, and multi-actuator properties. Notably, this achievement is accomplished without needing a priori information about the test specimen, streamlining the procedure and reducing the risk of specimen deterioration. Additionally, the tracking performance of the tests closely aligns with the reference structure, further affirming the excellence of the outcomes.

## Requirements
- Matlab and Simulink 2021a or later.
- Simulink Coder.
- MATLAB Control Toolbox. 
- Simulink Desktop Real-time.

## Description
maRTHS-bmk-RoDeAC folder corresponds to the Matlab codes. The additional/modified files from the benchmark codes are:
- `Model_vmaRHTS_R2019b.slx`: Simulink block diagram with the implemented controller in maRTHS.
- `Support_files/Offline_calibration.m`: Matlab code with the computation of the initial parameters for the robust and decentralized adaptive compensation (RoDeAC) algorithm.
- `Support_files/Model_Calibration.slx`: Simulink block diagram to calculate the initial parameters for the RoDeAC algorithm.
- `Support_files/S3_Controller.m`: Matlab code with the implementation of the RoDeAC algorithm.

## Running the virtual maRTHS
The following steps describe the procedure to execute the vmaRTHS:
1. Calibrate the recursive least squares adaptive compensation (RLS-AC), using the Matlab script `Support_files/Offline_calibration.m`. This script contains the code to obtain a series of initial parameters for the compensation algorithm. For example, in the paper, the mean values are chosen as the initial parameters of a series of calibration experiments. A `.mat` file should be saved with the name "Initial_parameters" with the chosen parameters.
2. Open the script `main_vmaRTHS.m`. By default, the sampling frequency and ground motion record are: $f_s = 1024$ Hz, El Centro 40% PGA.
3. Run `main_vmaRTHS.m`. This script will execute the five "Support_Files" folder scripts.
4. The simulation will finish with a table of the indices shown on the screen and a final message concluding whether the controller is realizable. The responses of each simulation and the average indices are stored in the folder "Results".

