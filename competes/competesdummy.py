#
# Dummy file to simulate a COMPETES output.
# Just generates random numbers and adds this to the SpineDB.
#
# Jim Hommes - 17-3-2021
#

import sys
import random
from datetime import datetime
from spinedb import SpineDB

# Input DB
db_url = sys.argv[1]
db = SpineDB(db_url)

# Reading SegmentLength
input_db_data = db.export_data()
segmentLength_parameterValueObject = [obj[3] for obj in input_db_data['object_parameter_values'] if obj[0] == 'emlabModel' and obj[1] == 'emlabModel' and obj[2] == 'SimulationLength']
segmentLength = int(segmentLength_parameterValueObject[0])


def addRandomness(number):
    return number + ((random.random() - 0.5) * 2)


output = [round(addRandomness(i), 2) for i in range(1, segmentLength)]
db.import_object_classes(['actualOutput'])
db.import_objects([('actualOutput', 'actualOutput')])
db.import_data({'object_parameters': [['actualOutput', 'hourlyDemand']]})
db.import_object_parameter_values([('actualOutput', 'actualOutput', 'hourlyDemand', {'type': 'time_series', 'data': output})])
db.commit('COMPETES Dummy Commit: ' + str(datetime.now()))