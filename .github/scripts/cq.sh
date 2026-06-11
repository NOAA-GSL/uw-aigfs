set -eu
source conda/etc/profile.d/conda.sh
conda activate uw-aigfs
set -x
make test
