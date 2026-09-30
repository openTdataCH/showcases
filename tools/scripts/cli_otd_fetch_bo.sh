set -Eeuo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

DATE_NOW=$(date +"%Y-%m-%d")

source $DIR/common.sh
source $PYTHON_VENV_PATH/bin/activate

BO_LOGFILE=$LOGS_BASEPATH/otd_fetch_csv_business-organisations-$DATE_NOW.log
python3 $DIR/cli_otd_fetch_csv_package.py --package_id business-organisation-v2 2>&1 | tee $BO_LOGFILE
python3 $DIR/cli_otd_symlink_package.py --package_id business-organisation-v2 2>&1 | tee -a $BO_LOGFILE
symlink_latest $BO_LOGFILE

GO_LOGFILE=$LOGS_BASEPATH/otd_fetch_csv_go-realtime-$DATE_NOW.log
python3 $DIR/cli_otd_fetch_csv_package.py --package_id go-realtime --overwrite 2>&1 | tee $GO_LOGFILE
symlink_latest $GO_LOGFILE
