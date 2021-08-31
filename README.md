# DFTflow
DFTflow is a  calculation workflow for DFT compuations on Tianhe-2 supercomputer. 
## How to run?
1. First, you need to define the relative paths of the vasp execution file, pseudo-potential directory, etc. in the config/condor.ini file.
2. Secondly, define the calculation step parameters in config/workflow.json, including the calculation type, parameters, the number of nodes and cores used in the calculation, and so on. Note that once you define the step name, you need to define the INCAR.yaml file with the corresponding name under config/template/. 
3. Finally, when submitting the job for the first time:
```
python vasp.py run --stru_dir ${*.vasp file directory}
```
if you need to continue to calculate the cancelled or errored job:
```
python vasp.py crun --cdir ${calculation directory} 
```
5. Use python vasp.py --help to view other details.
