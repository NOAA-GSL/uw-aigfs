scrfunc_fp=$( readlink -f "${BASH_SOURCE[0]}" )
scrfunc_dir=$( dirname "${scrfunc_fp}" )

#module use $scrfunc_dir/modulefiles
#module load wflow_$1 > /dev/null 2>&1

source /scratch3/BMC/wrfruc/cholt/aigfs/conda/etc/profile.d/conda.sh
conda activate aigfs
