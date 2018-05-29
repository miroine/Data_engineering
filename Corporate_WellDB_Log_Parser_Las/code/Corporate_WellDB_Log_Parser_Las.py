import pandas as pd
import json
import las
import os
import sys
import numpy as np
# Code review with Fredrik on 08.05.2018 - pass


def read_file_contents(lasfile):
    """Read all lines from the given las file"""
    with open(lasfile, 'r') as f:
        file_contents = f.readlines()
    return file_contents


def remove_comments_blanklines(file_contents):
    """Remove all blank lines and comment lines"""
    fc = []
    for li, line in enumerate(file_contents):
        if line.startswith('#'):
            # logger.info('Comment line: ' + line)
            print('Comment line')
        elif line in ['\n', '\r\n', ' ', '\t', '', '\r']:
            # logger.info('Empty line: ' + line)
            print('Empty line')
        else:
            line = line.strip()
            fc = fc + [line]
    return fc


def list_sections_present(file_contents):
    """Return a DataFrame with overview of the sections identifies in the data retrieved from the las file"""
    sections = pd.Series()
    locations = pd.Series()
    section_ids = pd.Series()
    data_start = pd.Series()
    data_end = pd.Series()
    for il, line in enumerate(file_contents):
        if line.startswith('~'):
            section_ids = section_ids.append(pd.Series(line[0:2]))
            line = line.replace('~', '')
            line = line.strip()
            sections = sections.append(pd.Series(line))
            locations = locations.append(pd.Series(il))
    sections_overview = pd.DataFrame()
    sections_overview['Section_name'] = sections
    sections_overview['Line_number'] = locations
    sections_overview['Section_ID'] = section_ids
    for sid, sn in enumerate(sections_overview['Section_name']):
        data_start = data_start.append(pd.Series(sections_overview['Line_number'].iloc[sid] + 1))
        if sid < len(sections_overview['Section_name']) - 1:
            de = sections_overview['Line_number'].iloc[sid + 1] - 1
        else:
            de = len(file_contents) - 1
        data_end = data_end.append(pd.Series(de))
    sections_overview['Start_index'] = data_start
    sections_overview['End_index'] = data_end
    print(sections_overview['Section_name'].iloc[-1])
    return sections_overview


def retrieve_line_metadata(line):
    """Return a dict with mnemonic, unit, data, description from a line with metadata
    Example of a metadata line:
    STRT  .M                2847.0000                       : FIRST INDEX VALUE """
    mnemonic = ''
    units = ''
    value = ''
    desc = ''
    line_metadata = {}
    if len(line) > 0:
        try:
            first, desc = (line.strip()).rsplit(':', 1)
            desc = desc.strip()
            mnemonic, mid = (first.strip()).split('.', 1)
            mnemonic = mnemonic.strip()
            if mid.startswith(' '):
                # logger.info('No units available')
                print('No units available')
                value = mid.strip()
            else:
                units, value = mid.split(None, 1)
                units = units.strip()
                value = value.strip()
        except Exception as e:
            # logger.error(e)
            print(e)
    if mnemonic:
        line_metadata['mnemonic'] = mnemonic.strip()
        line_metadata['units'] = units
        line_metadata['value'] = value
        line_metadata['description'] = desc
    return line_metadata


def check_las_version(file_contents):
    """Return the version of the las file"""
    ver = None
    for line in file_contents:
        if line.startswith('VERS'):
            lm = retrieve_line_metadata(line)
            ver = float(lm['value'])
            break
    return ver


def check_null_value(file_contents):
    """Return the NULL value used in the las file"""
    nv = None
    for line in file_contents:
        if line.startswith('NULL'):
            lm = retrieve_line_metadata(line)
            nv = lm['value']
            break
    return nv


def check_las_delimiter(file_contents):
    """Return the delimiter used in the las file"""
    dlm = ' '
    for line in file_contents:
        if line.startswith('DLM'):
            lm = retrieve_line_metadata(line)
            dlm = lm['value']
            break
    if dlm == 'SPACE' or dlm == ' ':
        dlm = ' '
    elif dlm == 'COMMA':
        dlm = ','
    elif dlm == 'TAB':
        dlm = '\t'
    return dlm


def read_metadata_sections(file_contents):
    """Return a dict with all metadata
    for LAS v2: read the data from sections other than ~A
    for section ~O all the data is put in one string
    returned is a dictionary that can be dumped into JSON file
    for LAS v3
    read data in all sections that do not contain DATA in the name"""
    ver = check_las_version(file_contents)
    metadata = {}
    sections = list_sections_present(file_contents)
    if ver == 2:
        # logger.info('LAS version 2')
        print('LAS version 2')
        # find sections that contain meta data
        for si, section_id in enumerate(sections['Section_ID']):
            if not section_id == '~A':
                section_label = sections['Section_name'].iloc[si]
                section_label = section_label.replace('~', '')
                section_label = section_label.replace(' ', '_')
                metadata[section_label] = {}
                mds = sections['Start_index'].iloc[si]
                mde = sections['End_index'].iloc[si]+1
                section_metadata = file_contents[mds:mde]
                if section_id == '~O':
                    # logger.info('OTHER section detected')
                    print('OTHER section detected')
                    other_info = " ".join(line.strip() for line in section_metadata)
                    metadata[section_label]['Comment'] = other_info
                else:
                    for smdl in section_metadata:
                        line_metadata = retrieve_line_metadata(smdl)
                        name = line_metadata['mnemonic']
                        metadata[section_label][name] = line_metadata
    if ver == 3:
        # logger.info('LAS version 3')
        print('LAS version 3')
        for si, section_name in enumerate(sections['Section_name']):
            if (section_name.upper()).find('DATA') == -1:
                section_label = sections['Section_name'].iloc[si]
                section_label = section_label.replace('~', '')
                section_label = section_label.replace(' ', '_')
                metadata[section_label] = {}
                mds = sections['Start_index'].iloc[si]
                mde = sections['End_index'].iloc[si]+1
                section_metadata = file_contents[mds:mde]
                for smdl in section_metadata:
                    line_metadata = retrieve_line_metadata(smdl)
                    if line_metadata:
                        name = line_metadata['mnemonic']
                        if name:
                            metadata[section_label][name] = line_metadata
    return metadata


def save_metadata(metadata, jsonfile):
    """Save extracted metadata to a JSON file"""
    all_meta = {}
    all_meta['JSON_file'] = {}
    filename = os.path.splitext(os.path.basename(jsonfile))[0]
    all_meta['JSON_file']['filename'] = ''.join([filename, '.JSON'])
    all_meta.update(metadata)
    with open(jsonfile, 'w+') as f:
        json.dump(all_meta, f, indent=2)
    print('Saved metadata to ' + jsonfile)
    f.close()


def save_curve_data(file_contents, metadata, csvfile):
    """Extract curve data from the las file contents and save to a CSV file. In case of LAS3 files,
    due to varying numbers of columns per section the data is saved in one csv file as well as in separate file for each section"""
    ver = check_las_version(file_contents)
    null_value = -999.25
    sections = list_sections_present(file_contents)
    file_overview = {}
    if ver == 2:
        retrieved_data = pd.DataFrame()
        file_overview['CSV_file'] = {}
        # if 'CURVE' in [w.upper() for w in metadata.keys()] and 'ASCII' in [w.upper() for w in sections['Section_name']]:
        section_names_capital = [w.upper() for w in sections['Section_name']]
        curve_data_present = [cn.find('CURVE') for cn in section_names_capital]
        curve_flag = [fl for fl in curve_data_present if fl >= 0]
        curve_index = curve_data_present.index(0)
        if len(curve_flag) > 0 and 'ASCII' in section_names_capital:
            try:
                cdid = [w.upper() for w in sections['Section_name']].index('ASCII')
                # mdid = [w.upper() for w in metadata.keys()].index('CURVE')
                mdid = curve_index
                mdkey = list(metadata.keys())[mdid]
                cds = sections['Start_index'].iloc[cdid]
                cde = sections['End_index'].iloc[cdid]+1
                curves_metadata = metadata.get(mdkey)
                curve_names = list(curves_metadata.keys())
                curves_data = list(map(lambda x: x.split(), file_contents[cds:cde]))
                for ci, cn in enumerate(curve_names):
                    retrieved_data[cn] = [i[ci] for i in curves_data]
                if retrieved_data.empty:
                    # logger.critical('No data found in the file')
                    print('No data found in the file')
                else:
                    retrieved_data.to_csv(csvfile, index=False)
                    replace_null_values_in_csv(csvfile, -999.25)
                    file_overview['CSV_file']['name'] = os.path.basename(csvfile)
                    print(os.path.basename(csvfile))
                    file_overview['CSV_file']['path'] = os.path.realpath(csvfile)
                    print(os.path.realpath(csvfile))
                    # logger.info('Saved retrieved data to file ' + csvfile)
                    print('Saved retrieved data to file ' + csvfile)
            except Exception as e:
                # logger.error(e)
                print(e)
        else:
            try:
                if len(curve_flag) > 0 and 'A' in section_names_capital:
                    cdid = [w.upper() for w in sections['Section_name']].index('A')
                    mdid = curve_index
                    mdkey = list(metadata.keys())[mdid]
                    cds = sections['Start_index'].iloc[cdid]
                    cde = sections['End_index'].iloc[cdid] + 1
                    curves_metadata = metadata.get(mdkey)
                    curve_names = list(curves_metadata.keys())
                    curves_data = list(map(lambda x: x.split(), file_contents[cds:cde]))
                    for ci, cn in enumerate(curve_names):
                        retrieved_data[cn] = [i[ci] for i in curves_data]
                    if retrieved_data.empty:
                        # logger.critical('No data found in the file')
                        print('No data found in the file')
                    else:
                        # retrieved_data = retrieved_data.replace(-999.25, np.nan)
                        retrieved_data.to_csv(csvfile, index=False)
                        replace_null_values_in_csv(csvfile, -999.25)
                        # logger.info('Saved retrieved data to file ' + csvfile)
                        print('Saved retrieved data to file ' + csvfile)
            except Exception as e:
                print(e)
                print('Curve information missing from the file')
    if ver == 3:
        dlm = check_las_delimiter(file_contents)
        file_overview['Files']={}
        #with open(csvfile, 'a+') as file:
            # identify sections containing DATA
        for sid, sn in enumerate(sections['Section_name']):
            if (sn.upper()).find('DATA') > -1:
                # read_section = pd.DataFrame()
                ds = sections['Start_index'].iloc[sid]
                de = sections['End_index'].iloc[sid]+1
                data_section, def_section = sn.split('|')
                def_section = def_section.strip()
                # curve_names = list((metadata.get(def_section)).keys())
                curve_names = list((metadata.get(def_section)).keys())
                section_data = file_contents[ds:de]
                section_data_split = list(map(lambda x: x.split(dlm), section_data))
                retrieved_data = pd.DataFrame()
                for ci, cn in enumerate(curve_names):
                    cd = [i[ci] for i in section_data_split]
                    retrieved_data[cn] = pd.Series(cd)
                # retrieved_data = retrieved_data.replace(-999.25, np.nan)
                #retrieved_data.to_csv(file, index=False)
                section_file = "%s_%s.csv" % (os.path.splitext(csvfile)[0], data_section)
                file_overview['Files'][''.join([data_section,'_file'])]={}
                file_overview['Files'][''.join([data_section,'_file'])]['name']=os.path.basename(csvfile)
                file_overview['Files'][''.join([data_section,'_file'])]['path']=os.path.realpath(csvfile)
                retrieved_data.to_csv(section_file, index=False)
                replace_null_values_in_csv(section_file, -999.25)
                print('Saved section data to: '+section_file)
                file_overview
    return file_overview

def parse_lasfile(lasfile):
    # logger.info('Retrieving data from LAS file ' + lasfile)
    filename = os.path.splitext(os.path.basename(lasfile))[0]
    new_folder_path = os.path.join(os.path.dirname(lasfile), 'outputDir', filename)
    if not os.path.isdir(new_folder_path):
        os.makedirs(new_folder_path)
    csvfile = os.path.join(new_folder_path, ''.join([filename, '.csv']))
    jsonfile = os.path.join(new_folder_path, ''.join([filename, '.json']))
    try:
        metadata = {}
        print(('Retrieving data from LAS file ' + lasfile))
        retrieved_data = pd.DataFrame()
        log = las.LASReader(lasfile)
        # VERSION INFORMATION
        version_info = log.version.items
        field_names = version_info.keys()
        metadata['Version Information'] = {}
        for fn in field_names:
            field = version_info.get(fn)
            metadata['Version Information'][fn] = {}
            metadata['Version Information'][fn]['mnemonic'] = field.name
            metadata['Version Information'][fn]['units'] = field.units
            metadata['Version Information'][fn]['value'] = field.value
            metadata['Version Information'][fn]['description'] = field.descr
        # WELL INORMATION
        fields = log.well.items
        field_names = fields.keys()
        metadata['Well Information'] = {}
        for fn in field_names:
            field = fields.get(fn)
            metadata['Well Information'][fn] = {}
            metadata['Well Information'][fn]['mnemonic'] = field.name
            metadata['Well Information'][fn]['units'] = field.units
            metadata['Well Information'][fn]['value'] = field.value
            metadata['Well Information'][fn]['description'] = field.descr
        # LOG PARAMETERS
        log_parameters = log.parameters.items
        param_names = log_parameters.keys()
        metadata['Parameters'] = {}
        for pn in param_names:
            log_parameter = log_parameters.get(pn)
            metadata['Parameters'][pn] = {}
            metadata['Parameters'][pn]['mnemonic'] = log_parameter.name
            metadata['Parameters'][pn]['units'] = log_parameter.units
            metadata['Parameters'][pn]['value'] = log_parameter.data
            metadata['Parameters'][pn]['description'] = log_parameter.descr
        # ASCII
        curves = log.curves.items
        curve_names = curves.keys()
        for cn in curve_names:
            curve = curves.get(cn)
            metadata['ASCII'][cn] = {}
            metadata['ASCII'][cn]['mnemonic'] = curve.name
            metadata['ASCII'][cn]['units'] = curve.units
            metadata['ASCII'][cn]['value'] = curve.value
            metadata['ASCII'][cn]['description'] = curve.descr
            retrieved_data[cn] = pd.Series(log.data[cn])
        save_metadata(metadata, jsonfile)
        # retrieved_data = retrieved_data.replace(-999.25, np.nan)
        retrieved_data.to_csv(csvfile, index=False)
        replace_null_values_in_csv(csvfile, -999.25)
    except Exception as e:
        # logger.error(e)
        print(e)
        file_contents = read_file_contents(lasfile)
        clean_file_contents = remove_comments_blanklines(file_contents)
        metadata = read_metadata_sections(clean_file_contents)
        file_overview = save_curve_data(clean_file_contents, metadata, csvfile)
        metadata.update(file_overview)
        save_metadata(metadata, jsonfile)


def replace_null_values_in_csv(csvfile, null_value):
    try:
        with open(csvfile, 'r+') as raw_file:
            raw_data = pd.read_csv(raw_file)
            raw_data = raw_data.replace(null_value, np.nan)
            raw_data.to_csv(csvfile, index=False, na_rep='NaN')
    except Exception as e:
        print('Error while replacing '+str(null_value)+' to NaN')
        print(e)


def main():
    lasfile = sys.argv[1]
    print(lasfile)
    parse_lasfile(lasfile)


if __name__ == '__main__':
    main()
