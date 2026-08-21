#!/bin/bash
#SBATCH --qos=preemptable
#SBATCH --export=NONE
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --time=00:30:00
#SBATCH --job-name=ohc_gcos
#SBATCH --output=%x.%j.out
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=katie.mills@colorado.edu
#SBATCH --mem=8GB
#SBATCH --exclude=blanca-g6-u21

module purge
module load anaconda/2023.09
conda activate ohc_crosscheck

# One ohc_derive blob per synthetic level, each built with --time-window 2005:2024 (the GCOS baseline);
# gcos.py reads the window off the blobs. $1 is the provenance tag.
cd $SLURM_SUBMIT_DIR
python gcos.py \
  /scratch/alpine/wimi7695/ohc_prod/results/derive_${1}_*.nc \
  --tag $1 \
  --provenance-link https://github.com/argovis/ohc_gcos_emitter/releases/tag/$1 \
  --out out
