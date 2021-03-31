#
# The main EM-Lab file for in SpineToolbox.
# Commandline arguments provide which modules are run and which aren't.
#
# Jim Hommes - 25-3-2021
#

import sys
from dependencies.spinedb_reader_writer import *
from modules.capacitymarket import *


run_capacity_market = False
run_electricity_spot_market = False

# Loop over provided arguments and select modules
for arg in sys.argv[2:]:
    if arg == 'run_capacity_market':
        run_electricity_spot_market = True
        run_capacity_market = True
    if arg == 'run_electricity_spot_market':
        run_electricity_spot_market = True

# Read input database from Spine
db_url = sys.argv[1]

# Create Objects from the DB in the Repository
spinedb_reader_writer = SpineDBReaderWriter(db_url)
reps = spinedb_reader_writer.read_db_and_create_repository()

# Init all modules and commit structure to Spine
capacity_market_submit_bids = CapacityMarketSubmitBids(reps)
capacity_market_clear = CapacityMarketClearing(reps)

spinedb_reader_writer.commit('Initialize all module import structures')

# Submit bids to Capacity Market
if run_capacity_market:
    capacity_market_submit_bids.act_and_commit(reps.current_tick)

# Clear Capacity Market
if run_capacity_market:
    capacity_market_clear.act_and_commit(reps.current_tick)
