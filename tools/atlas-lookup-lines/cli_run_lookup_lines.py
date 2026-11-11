import os, sys

from pathlib import Path

from atlas_lookup_lines.atlas_lookup_lines_controller import AtlasLookupLinesController

# from compare_gtfs_rt_static.gtfs_controller import GTFS_Controller
# from compare_gtfs_rt_static.models.gtfs_static_db_catalog import GTFS_Static_Catalog_Item
from atlas_lookup_lines.helpers.log_helpers import log_message

def main():
    log_message('START: Lookup Atlas Routes')
    
    app_path = Path(os.path.realpath(__file__)).parent
    atlas_lookup_controller = AtlasLookupLinesController(app_path)
    atlas_lookup_controller.process()
    
    log_message('DONE: Lookup Atlas Routes')

if __name__ == "__main__":
    main()
