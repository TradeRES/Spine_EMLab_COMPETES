"""
This file contains some helper functions for the scripts in resources/scripts.
An example that all of them use is to read the current year from the EMLAB SpineDB.

Jim Hommes - 29-6-2021
"""
from spinedb import *


def get_current_ticks(db: SpineDB, offset: int):
    current_emlab_tick = max(row['parameter_value'] for row in db.query_object_parameter_values_by_object_class('SystemClockTicks'))
    current_competes_tick = current_emlab_tick + offset
    current_competes_tick_rounded = offset + round(current_emlab_tick / 5) * 5
    return int(current_emlab_tick), int(current_competes_tick), int(current_competes_tick_rounded)
