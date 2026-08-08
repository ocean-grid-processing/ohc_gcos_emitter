for level in 15_20 15_300 300_700 700_1850 1800_1850
do
  cp /scratch/alpine/wimi7695/gcos_validation/OP20260127b_potentialTemperature_-89.5S_89.5N_20.5W_379.5E_2004_2025_${level}/derive_LocalGP_2004_2025_lev${level}.nc data/.
done

sbatch combine.slurm
