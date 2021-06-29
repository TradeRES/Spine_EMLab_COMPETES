"""
This script handles all preparations necessary for the execution of COMPETES.
This entails translating the COMPETES SpineDB to MS Access databases.

Jim Hommes - 1-6-2021
"""
import pyodbc
import shutil
import sys
import numpy as np
import pandas
from spinedb import SpineDB


class TriangularTrend:
    """
    COPIED FROM EMLAB

    The TriangularTrend grows according to a Triangular distribution.
    Because of the random nature of this trend, values are saved in self.values so that once generated, the value \
    does not change.
    """
    def __init__(self, top, maxx, minn):
        self.top = top
        self.max = maxx
        self.min = minn

    def get_values(self, start, start_time, end_time):
        res_values = [start]
        for i in range(end_time-start_time):
            last_value = res_values[-1]
            random_number = np.random.triangular(-1, 0, 1)
            if random_number < 0:
                res_values.append(last_value * (self.top + (random_number * (self.top - self.min))))
            else:
                res_values.append(last_value * (self.top + (random_number * (self.max - self.top))))
        return res_values


def export_to_mdb(path: str, filename: str,
                  tables_objects_type1: dict, tables_objects_type2: dict,
                  tables_relationships_type1: dict, tables_relationships_type2: dict):
    """
    Initialize the connection to the MS Access DB and import the tables.
    Type1 Mapping: SpineDB has an object with parameters. {'Table Name': 'Object Column Name'}
    Type2 Mapping: SpineDB has an object with one parameter, which is a map. In this map, the first index is unique,
    and the second is the parameter names. {'Table Name': ('Object Column Name', 'Index Column Name)}
    Type1 Relationships Mapping: SpineDB has a relationship with parameters.
    {'Table Name': ('Object 1 Column Name', 'Object 2 Column Name')}
    Type2 Relationships Mapping: SpineDB has a relationship with one parameter which is a map.
    First index is unique, second is the parameter names.
    {'Table Name': ('Object 1 Column Name', 'Object 2 Column Name', 'Index Column Name')}

    :param path: Path to COMPETES data folder
    :param filename: MS Access filename
    :param tables_objects_type1: Dict as described above
    :param tables_objects_type2: Dict as described above
    :param tables_relationships_type1: Dict as described above
    :param tables_relationships_type2: Dict as described above
    :return:
    """
    print('Initializing connection to ' + filename)
    try:
        con_string = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=' + path + filename + ';'
        conn = pyodbc.connect(con_string)
        cursor = conn.cursor()
        print("Connected To " + filename)

        # Unique structures / Separate function required
        if filename == 'COMPETES EU 2050-KIP.mdb':
            print('Staging Unique Mappings...')
            export_co2_prices(cursor)
            export_fuelpriceyears(cursor)
            export_nset(cursor)
            print('Finished Unique Mappings')

        print('Staging Type 1 Mappings...')
        for (table_name, id_parameter_name) in tables_objects_type1.items():
            print('Exporting table ' + table_name)
            export_type1(cursor, table_name, id_parameter_name)
        print('Finished Type 1 Mappings')

        print('Staging Type 2 Mappings...')
        for (table_name, value) in tables_objects_type2.items():
            print('Exporting table ' + table_name)
            id_parameter_name = value[0]
            index_parameter_names = value[1:]
            export_type2(cursor, table_name, id_parameter_name, index_parameter_names)
        print('Finished Type 2 Mappings')

        print('Staging Relationships Type 1...')
        for (table_name, (object1_parameter_name, object2_parameter_name)) in tables_relationships_type1.items():
            print('Exporting Relationships table ' + table_name)
            export_relationships_type1(cursor, table_name, object1_parameter_name, object2_parameter_name)

        print('Finished Relationships Type 1')

        print('Staging Relationships Type 2...')
        for (table_name, (object1_parameter_name, object2_parameter_name, index_parameter_name)) \
                in tables_relationships_type2.items():
            print('Exporting Relationships table ' + table_name)
            export_relationships_type2(cursor, table_name, object1_parameter_name, object2_parameter_name,
                                       index_parameter_name)
        print('Finished Relationships Type 2')

        print('Committing...')
        cursor.commit()
    except pyodbc.Error as e:
        print("Error in Connection", e)
    finally:
        cursor.close()
        conn.close()
        print('Done')


def export_type1(cursor, table_name, id_parameter_name):
    """
    Type1 Mapping: SpineDB has an object with parameters. {'Table Name': 'Object Column Name'}

    :param cursor: PYODBC Cursor
    :param table_name: Table Name
    :param id_parameter_name: Object ID Column Name
    :return:
    """
    for (_, id_parameter_value, _) in [i for i in db_competes_data['objects'] if i[0] == table_name]:
        param_values = [('[' + str(param_name) + ']', param_value) for (itable_name, iid, param_name, param_value, _)
                        in db_competes_data['object_parameter_values']
                        if itable_name == table_name and iid == id_parameter_value]

        # Workaround for Excel sheet name restrictions
        if table_name == 'NL Installed Capacity-RES (+he':
            table_res = 'NL Installed Capacity-RES (+heat)'
        else:
            table_res = table_name

        sql_query = 'INSERT INTO [' + table_res + '] ([' + id_parameter_name + '], ' + \
                    ', '.join([i[0] for i in param_values]) + ') VALUES (?, ' + \
                    ', '.join(list('?' * len(param_values))) + ');'
        values = (id_parameter_value,) + tuple(i[1] for i in param_values)
        cursor.execute(sql_query, values)


def export_type2(cursor, table_name, id_parameter_name, index_parameter_names):
    """
    Type2 Mapping: SpineDB has an object with one parameter, which is a map. In this map, the first index is unique,
    and the second is the parameter names. {'Table Name': ('Object Column Name', 'Index Column Name)}

    :param cursor: PYODBC Cursor
    :param table_name: Table Name
    :param id_parameter_name: Object ID Column Name
    :param index_parameter_names: Array of Index Column Names
    """
    for (_, id_parameter_value, _) in [i for i in db_competes_data['objects'] if i[0] == table_name]:
        value_map = next(i[3] for i in db_competes_data['object_parameter_values']
                         if i[0] == table_name and i[1] == id_parameter_value)
        for value_map_row in value_map.to_dict()['data']:
            export_type2_recursive(cursor, table_name, id_parameter_name, id_parameter_value, index_parameter_names, [value_map_row[0]], value_map_row[1]['data'])


def export_type2_recursive(cursor, table_name, id_parameter_name, id_parameter_value, index_parameter_names, index_parameter_values, data):
    if len(data) > 0:
        first_el = data[0]
        if len(first_el) == 2 and type(first_el[1]) == dict and 'type' in first_el[1].keys() and first_el[1]['type'] == 'map':
            # In this case, it MUST be another map
            # Go one level deeper
            for value_map_row in data:
                export_type2_recursive(cursor, table_name, id_parameter_name, id_parameter_value,
                                       index_parameter_names, index_parameter_values + [value_map_row[0]],
                                       value_map_row[1]['data'])
        else:
            # Otherwise, treat as regular value and export it to MDB
            param_values = [('[' + str(i[0]) + ']', i[1]) for i in data]
            sql_query = 'INSERT INTO [' + table_name + '] ([' + id_parameter_name + '],[' + \
                        '],['.join(index_parameter_names) + '],' + ','.join([i[0] for i in param_values]) + \
                        ') VALUES (?,' + ','.join(list('?' * len(index_parameter_values))) + ',' + ','.join(list('?' * len(param_values))) + ');'
            # print(param_values)
            # print(sql_query)
            values = (id_parameter_value,) + tuple(index_parameter_values) + tuple(i[1] for i in param_values)
            cursor.execute(sql_query, values)


def export_relationships_type1(cursor, table, object1_param_name, object2_param_name):
    """
    Type1 Relationships Mapping: SpineDB has a relationship with parameters.
    {'Table Name': ('Object 1 Column Name', 'Object 2 Column Name')}

    :param cursor: PYODBC Cursor
    :param table: Table Name
    :param object1_param_name: Object ID1 Column Name
    :param object2_param_name: Object ID2 Column Name
    :return:
    """
    for (_, object_parameter_name_value_list) in [i for i in db_competes_data['relationships'] if i[0] == table]:
        param_values = [('[' + str(param_name) + ']', param_value)
                        for (itable, iobject_list, param_name, param_value, _)
                        in db_competes_data['relationship_parameter_values']
                        if itable == table and iobject_list == object_parameter_name_value_list]
        sql_query = 'INSERT INTO [' + table + '] ([' + object1_param_name + '],[' + \
                        object2_param_name + '],' + ','.join([i[0] for i in param_values]) + \
                        ') VALUES (?,?,' + ','.join(list('?' * len(param_values))) + ');'
        values = tuple(object_parameter_name_value_list) + tuple(i[1] for i in param_values)
        cursor.execute(sql_query, values)


def export_relationships_type2(cursor, table, object1_param_name, object2_param_name, index_param_name):
    """
    Type2 Relationships Mapping: SpineDB has a relationship with one parameter which is a map.
    First index is unique, second is the parameter names.
    {'Table Name': ('Object 1 Column Name', 'Object 2 Column Name', 'Index Column Name')}

    :param cursor: PYODBC Cursor
    :param table: Table Name
    :param object1_param_name: Object ID1 Column Name
    :param object2_param_name: Object ID2 Column Name
    :param index_param_name: Index Column Name
    :return:
    """
    for (_, [object1, object2], _, value_map, _) in [i for i in db_competes_data['relationship_parameter_values']
                                                     if i[0] == table]:
        for value_map_row in value_map.to_dict()['data']:
            index = value_map_row[0]
            param_values = [('[' + str(i[0]) + ']', i[1]) for i in value_map_row[1]['data']]
            sql_query = 'INSERT INTO [' + table + '] ([' + object1_param_name + '],[' + \
                            object2_param_name + '],[' + index_param_name + '],' + \
                            ','.join([i[0] for i in param_values]) + ') VALUES (?,?,?,' + \
                            ','.join(list('?' * len(param_values))) + ');'
            values = (object1, object2, index,) + tuple(i[1] for i in param_values)
            cursor.execute(sql_query, values)


def export_co2_prices(cursor):
    """
    Separate function because of structure in SpineDB.

    :param cursor: PYODBC Cursor
    :return:
    """
    print('Exporting CO2 Prices...')
    table_name = 'EU_ETS_CO2price'
    for (object_class_name, year, month, price, _) in [i for i in db_competes_data['object_parameter_values']
                                                       if i[0] == table_name]:
        sql_query = 'INSERT INTO [' + table_name + '] ([Year input], [Month input], [CO2price]) VALUES (?,?,?)'
        cursor.execute(sql_query, (year, month, price))


def export_fuelpriceyears(cursor):
    """
    Separate function because of the required execution of the "trends" to print numbers into MS Access.

    :param cursor: PYODBC
    :return:
    """
    print('Exporting Fuelpriceyears...')
    table_name_spine = 'FuelpriceTrends'
    table_name_competes = 'Fuelpriceyears'
    years = [2020, 2025, 2030, 2035, 2040, 2045, 2050]
    months = ['[' + i[1] + ']' for i in db_competes_data['objects'] if i[0] == 'Months']
    countries = [i[1] for i in db_competes_data['objects'] if i[0] == 'Country']
    for (_, trend_name, _) in [i for i in db_competes_data['objects'] if i[0] == table_name_spine]:
        param_values = {k: v for (table_name, object_name, k, v, _) in db_competes_data['object_parameter_values']
                        if table_name == table_name_spine and object_name == trend_name}
        fuelname = param_values['Fuel']
        trend_obj = TriangularTrend(param_values['Top'], param_values['Max'], param_values['Min'])

        for year in years:
            prices = trend_obj.get_values(param_values['Start'], years[0], years[-1])
            for country in countries:
                print("Exporting for year " + str(year) + ' and country ' + country)
                sql_query = 'INSERT INTO [' + table_name_competes + '] ([Fuelname], [Country], [Year], ' + ', '.join(months) + ') VALUES (' + ','.join(['?']*15) + ');'
                cursor.execute(sql_query, (fuelname, country, year,) + (prices[year - 2020],) * 12)


def export_nset(cursor):
    """
    Separate function because of single object structure

    :param cursor: PYODBC cursor
    :return:
    """
    for (_, object_name, _) in [i for i in db_competes_data['objects'] if i[0] == 'Nset']:
        sql_query = 'INSERT INTO [Nset] ([n2]) VALUES (?);'
        cursor.execute(sql_query, (object_name,))


print('===== Starting COMPETES SpineDB to MS Access script =====')

config_url = sys.argv[2]
print('Config file path: ' + config_url)

print('Reading current year..')
f = open(sys.argv[3])
current_competes_tick = int(f.read())

print('Copying empty Excel sheet...')
originalfiles = ['../../COMPETES/Results/Empty output files/Output_Dynamic_Gen&Trans_INSERTYEAR.xlsx']

for originalfile in originalfiles:
    shutil.copyfile(originalfile, originalfile.replace("INSERTYEAR", str(current_competes_tick)).replace('/Empty output files', ''))

print('Copying empty databases...')
originalfiles = sys.argv[4:]
targetfiles = [i.replace('empty_', '') for i in originalfiles]


for originalfile in originalfiles:
    shutil.copyfile(originalfile, originalfile.replace("empty_", ""))
print('Done copying empty databases')

print('Connecting and exporting SpineDB...')
db_competes = SpineDB(sys.argv[1])
try:
    db_competes_data = db_competes.export_data()
    db_competes.close_connection()
    print('Done')

    path_to_data = originalfiles[0].split("empty_")[0]

    print('Reading type 1 mapping from config file')
    object_mapping_type1 = {i[0]: i[1] for i in pandas.read_excel(config_url, 'Object Type 1').values}
    print(object_mapping_type1)

    print('Reading type 2 mapping from config file')
    object_mapping_type2 = {i[0]: tuple([j for j in i[1:] if type(j) == str]) for i in pandas.read_excel(config_url, 'Object Type 2').values}
    print(object_mapping_type2)

    print('Reading relationship type 1 mapping from config file')
    relationship_mapping_type1 = {i[0]: (i[1], i[2]) for i in pandas.read_excel(config_url, 'Relationship Type 1').values}
    print(relationship_mapping_type1)

    print('Reading relationship type 2 mapping from config file')
    relationship_mapping_type2 = {i[0]: (i[1], i[2], i[3]) for i in pandas.read_excel(config_url, 'Relationship Type 2').values}
    print(relationship_mapping_type2)

    print('Reading PP type 1 mapping from config file')
    pp_object_mapping_type1 = {i[0]: i[1] for i in pandas.read_excel(config_url, 'PP Object Type 1').values}
    print(pp_object_mapping_type1)

    print('Reading PP type 2 mapping from config file')
    pp_object_mapping_type2 = {i[0]: tuple([j for j in i[1:] if type(j) == str]) for i in pandas.read_excel(config_url, 'PP Object Type 2').values}
    print(pp_object_mapping_type2)

    print('Reading PP relationship type 1 mapping from config file')
    pp_relationship_mapping_type1 = {i[0]: (i[1], i[2]) for i in pandas.read_excel(config_url, 'PP Relationship Type 1').values}
    print(pp_relationship_mapping_type1)

    print('Reading PP relationship type 2 mapping from config file')
    pp_relationship_mapping_type2 = {i[0]: (i[1], i[2], i[3]) for i in pandas.read_excel(config_url, 'PP Relationship Type 2').values}
    print(pp_relationship_mapping_type2)

    export_to_mdb(path_to_data, 'COMPETES EU 2050-KIP.mdb',
                  object_mapping_type1, object_mapping_type2, relationship_mapping_type1, relationship_mapping_type2)

    export_to_mdb(path_to_data, 'COMPETES EU PowerPlants 2050-KIP', pp_object_mapping_type1, pp_object_mapping_type2,
                  pp_relationship_mapping_type1, pp_relationship_mapping_type2)
except Exception as e:
    print('Exception occurred: ' + str(e))
    raise
finally:
    print('Closing database connection...')
    db_competes.close_connection()
    print('===== End of COMPETES SpineDB to MS Access script =====')
