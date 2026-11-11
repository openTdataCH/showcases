set -Eeuo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

DATE_NOW=$(date +"%Y-%m-%d")

source $DIR/common.sh
source $PYTHON_VENV_PATH/bin/activate

ATLAS_FETCH_LOGFILE=$LOGS_BASEPATH/otd_fetch_csv_atlas-lines-$DATE_NOW.log
python3 $DIR/cli_otd_fetch_csv_package.py --package_id line-v2 2>&1 | tee $ATLAS_FETCH_LOGFILE
python3 $DIR/cli_otd_symlink_package.py --package_id line-v2 2>&1 | tee -a $ATLAS_FETCH_LOGFILE
symlink_latest $ATLAS_FETCH_LOGFILE

ATLAS_LOOKUP_OEV_LOGFILE=$LOGS_BASEPATH/otd_lookup_oev_atlas-lines-$DATE_NOW.log
$DIR/../atlas-lookup-lines/.venv/bin/python3 $DIR/../atlas-lookup-lines/cli_run_lookup_lines.py 2>&1 | tee $ATLAS_LOOKUP_OEV_LOGFILE
symlink_latest $ATLAS_LOOKUP_OEV_LOGFILE

ATLAS_GEOCODE_LOGFILE=$LOGS_BASEPATH/otd_geocode_atlas-lines-$DATE_NOW.log
npm --prefix $DIR/../atlas-geocode-lines/ run process_node18 2>&1 | tee $ATLAS_GEOCODE_LOGFILE
symlink_latest $ATLAS_GEOCODE_LOGFILE
