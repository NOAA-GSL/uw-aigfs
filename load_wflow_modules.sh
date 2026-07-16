scrfunc_fp=$( readlink -f "${BASH_SOURCE[0]}" )
scrfunc_dir=$( dirname "${scrfunc_fp}" )

source $scrfunc_dir/conda/etc/profile.d/conda.sh
conda activate aigfs
