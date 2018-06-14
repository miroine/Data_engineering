import json
import las
import os
import sys
import numpy as np
import io
import logging
import pandas as pd
import re
import datetime

LOG_FORMAT = "%(levelname)s %(asctime)s - %(funcName)s, %(lineno)d - %(message)s"
logging.basicConfig(filename='lasparser2.log', level=logging.DEBUG, format=LOG_FORMAT)
logger = logging.getLogger()


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
            logger.info('Comment line: ' + line)
        elif line in ['\n', '\r\n', ' ', '\t', '', '\r']:
             logger.info('Empty line: ' + line)
        else:
            line = line.strip()
            fc = fc + [line]
    return fc


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
                logger.info('No units available')
                value = mid.strip()
            else:
                units, value = mid.split(None, 1)
                units = units.strip()
                value = value.strip()
        except Exception as e:
            logger.error(e)
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


def check_wrap_setting(file_contents):
    """Return the WRAP setting"""
    wrap = None
    for line in file_contents:
        if line.startswith('WRAP'):
            lm = retrieve_line_metadata(line)
            wrap = lm['value']
            break
    if wrap=='YES':
        wrap = True
    else:
        wrap = False
    return wrap

def standardize_meta_section_names(metadata):
    m_fields = list(metadata.keys())
    for mf in m_fields:
        if 'VERSION' in mf.upper() and 'DATA' not in mf.upper() and 'DEFINITION' not in mf.upper():
            metadata['VERSION INFORMATION SECTION'] = metadata[mf]
            del metadata[mf]
        if 'WELL' in mf.upper() and 'DATA' not in mf.upper() and 'DEFINITION' not in mf.upper():
            metadata['WELL INFORMATION SECTION'] = metadata[mf]
            del metadata[mf]
        if 'CURVE' in mf.upper() and 'DATA' not in mf.upper() and 'DEFINITION' not in mf.upper():
            metadata['CURVE INFORMATION SECTION'] = metadata[mf]
            del metadata[mf]
        if 'PARAMETER' in mf.upper() and 'DATA' not in mf.upper() and 'DEFINITION' not in mf.upper():
            metadata['PARAMETER INFORMATION SECTION'] = metadata[mf]
            del metadata[mf]
        if 'OTHER' in mf.upper() and 'DATA' not in mf.upper() and 'DEFINITION' not in mf.upper():
            metadata['OTHER'] = metadata[mf]
            del metadata[mf]
        if 'REMARKS' in mf.upper() and 'DATA' not in mf.upper() and 'DEFINITION' not in mf.upper():
            metadata['OTHER'] = metadata[mf]
            del metadata[mf]
    return metadata

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
    #clean_file_contents = remove_comments_blanklines(file_contents)
    ver = check_las_version(file_contents)
    metadata = {}
    sections = list_sections_present(file_contents)
    if ver == 2:
        # logger.info('LAS version 2')
        logger.info('LAS version 2')
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
                    logger.info('OTHER section detected')
                    other_info = " ".join(line.strip() for line in section_metadata)
                    metadata[section_label]['Comment'] = other_info
                else:
                    for smdl in section_metadata:
                        line_metadata = retrieve_line_metadata(smdl)
                        name = line_metadata['mnemonic']
                        metadata[section_label][name] = line_metadata
    if ver == 3:
        logger.info('LAS version 3')
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
        m_fields = list(metadata.keys())
        for m in m_fields:
            if 'CURVE' in m.upper():
                md = {}
                logger.error('CURVE is reserved for LAS v2')
                print('CURVE is reserved for LAS v2')
                for line in file_contents:
                    if 'DATA' in line.upper() and 'DEFINITION' in line.upper():
                        curve_metadata = metadata.get(m)
                        section_name = line.split('|')[1].strip()
                        md[section_name] = {}
                        md[section_name] = curve_metadata
                        metadata.update(md)
                        # print(metadata.keys())
                        break

    return metadata


def save_metadata(metadata, jsonfile):
    """Save extracted metadata to a JSON file"""

    filename = os.path.splitext(os.path.basename(jsonfile))[0]
    #all_meta['JSON_file']['filename'] = ''.join([filename, '.JSON'])
    with open(jsonfile, 'w+') as f:
        json.dump(metadata, f, indent=2)
    logger.info('Saved metadata to ' + jsonfile)
    f.close()


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
    return sections_overview


#def parse_lasfile(lasfile, mpath, destination_folder):
def parse_lasfile(lasfile):
    """ mpath - the way that the path is to be modified"""
    """ mpath will be inserted between destination folder and files_name.csv"""
    # logger.info('Retrieving data from LAS file ' + lasfile)
    filename = os.path.splitext(os.path.basename(lasfile))[0]
    source_folder = os.path.dirname(lasfile)
    #destination_folder = 'E:/IT/Projects/REP/LAS/LASTEST'
    new_folder_path = os.path.join(source_folder, 'outputDir', filename)
    #print(new_folder_path)
    if not os.path.isdir(new_folder_path):
        os.makedirs(new_folder_path)
    csvfile = os.path.join(new_folder_path, ''.join([filename, '.csv']))
    print('Generated CSV path: '+csvfile)
    jsonfile = os.path.join(new_folder_path, ''.join([filename, '.json']))
    try:
        metadata = {}
        logger.info('Retrieving data from LAS file ' + lasfile)
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
        #print(type(log.data))
        for cn in curve_names:
            curve = curves.get(cn)
            metadata['ASCII'][cn] = {}
            metadata['ASCII'][cn]['mnemonic'] = curve.name
            metadata['ASCII'][cn]['units'] = curve.units
            metadata['ASCII'][cn]['value'] = curve.value
            metadata['ASCII'][cn]['description'] = curve.descr
            retrieved_data[cn] = pd.Series(log.data[cn])
        # save_metadata(metadata, jsonfile)
        # retrieved_data = retrieved_data.replace(-999.25, np.nan)
        retrieved_data.to_csv(csvfile, index=False)

        metadata['LAS file']=os.path.basename(lasfile)
        if os.path.isfile(csvfile):
            replace_null_values_in_csv(csvfile, -999.25)
            metadata['CSV_files']={}
            temp = os.path.realpath(csvfile)
            # print(temp.find('outputDir'))
            metadata['Data files']= temp[temp.find('outputDir')+8:]
            # print(list(metadata.keys()))
            metadata = standardize_meta_section_names(metadata)
            # print(list(metadata.keys()))
            save_metadata(metadata, jsonfile)
    except Exception as e:
        logger.error(e)
        file_contents = read_file_contents(lasfile)
        clean_file_contents = remove_comments_blanklines(file_contents)
        #file_contents have to be used so in case ~CURVE used in LASv3 we can retrieve curve names
        metadata = read_metadata_sections(clean_file_contents)
        try:
            parse_curve_data(metadata, clean_file_contents, csvfile)
            ver = check_las_version(file_contents)
        except Exception as e:
            print(e)


def fix_file_contents(file_contents, **kwargs):
    fixed_file_contents=list()
    if kwargs.get('dlm'):
        dlm = kwargs.get('dlm')
    else:
        dlm = ' '
    for line in file_contents:
        line = line.rstrip()
        line = re.sub(' +',' ',line)
        # for dlm in possible_delims:
        #     line = re.sub(dlm,' ', line)
        vals = line.split(dlm)
        nvals = list()
        for iv, v in enumerate(vals):
            if '-999.25' in v:
                v = 'NaN'
            nvals.append(v)
        fixed_file_contents.append(nvals)
    #print(fixed_file_contents[0])
    #print(len(fixed_file_contents[0]))
    #print(type(fixed_file_contents[0]))
    return fixed_file_contents

def save_to_csv(file_contents, csvfile, col_names):
    with open(csvfile,'w+') as f:
        f.write(col_names)
        f.write('\n')
        for lid,line in enumerate(file_contents):
            sline = ','.join(line)
            f.write(sline)
            if lid<=len(file_contents)-2:
                #print('Line '+str(lid)+' of '+str(len(file_contents)))
                f.write('\n')
    f.close()

def parse_curve_data(metadata, file_contents, csvfile):
    ver = check_las_version(file_contents)
    dlm = check_las_delimiter(file_contents)
    if ver == 2:
        logger.info('LAS v. 2')
        parse_las2_file(metadata, file_contents, csvfile)
    elif ver == 3:
        logger.info('LAS v. 3')
        dlm = check_las_delimiter(file_contents)
        parse_las3_file(metadata,file_contents,csvfile, dlm=dlm)
    else:
        logger.critical('no version information')

def parse_las2_file(metadata, file_contents, csvfile,**kwargs):
    if kwargs.get('dlm'):
        dlm = kwargs.get('dlm')
    else:
        dlm = ' '
    meta_fields = list(metadata.keys())
    curve_info_field = [s for s in meta_fields if s.upper().startswith("CURVE")][0]
    curves = metadata.get(curve_info_field)
    curve_names = list(curves.keys())
    wrap = check_wrap_setting(file_contents)
    col_names = ','.join(curve_names)
    for lid,line in enumerate(file_contents):
        if line.startswith('~A'):
            file_data = file_contents[lid+1:]
            break
    if wrap:
        logger.info('WRAP: YES')
        cn = len(curve_names)
        logger.info('there are '+str(cn)+' curves')
        if not curve_names[0].upper() == 'DEPTH':
            logger.error('First curve should be DEPTH')
        else:
            unwrapped_data = list()
            for i,line in enumerate(file_data):
                if len(line.strip().split())==1:
                    depth = list()
                    depth = line.strip().split()
                    c_left = cn-1
                    for ci,cline in enumerate(file_data[i+1:]):
                        cline_data = cline.strip().split()
                        depth.extend(cline_data)
                        c_left = c_left-len(cline_data)
                        if c_left<=0:
                            unwrapped_data.append(depth)
                            break
        fixed_file_contents = list()
        for line in unwrapped_data:
            for iv,val in enumerate(line):
                if '-999.25' in val:
                    line[iv]='NaN'
            fixed_file_contents.append(line)
    else:
        fixed_file_contents = fix_file_contents(file_data,dlm=dlm)
    #print(fixed_file_contents)
    save_to_csv(fixed_file_contents, csvfile, col_names)
    if os.path.isfile(csvfile):
        jsonfile = csvfile.replace('csv','json')
        metadata['Data files']={}
        temp = os.path.realpath(csvfile)
        temp = temp[temp.find('outputDir')+8:]
        temp = temp.replace('\\','/')
        # print(temp)
        metadata['Data files']= temp[2:]
        #metadata['CSV_files']=os.path.realpath(csvfile)
        # print(list(metadata.keys()))
        metadata = standardize_meta_section_names(metadata)
        # print(list(metadata.keys()))
        save_metadata(metadata, jsonfile)
    else:
        logger.error('No csv file created')
        print('No csv file created')
        print(csvfile)


def parse_las3_file(metadata,file_contents,csvfile,**kwargs):
    if kwargs.get('dlm'):
        dlm = kwargs.get('dlm')
    else:
        dlm = ' '
    meta_fields = list(metadata.keys())
    # print(meta_fields)
    section_overview = list_sections_present(file_contents)
    # print(section_overview)
    """ find sections that contain data"""
    data_sections = list()
    for s in section_overview['Section_name']:
        if "DATA" in s.upper():
            data_sections.append(s)
    # print(data_sections)
    created_files = list()
    for ds in data_sections:
        if 'INPUT' not in ds.upper():
            section_info = section_overview.loc[section_overview['Section_name']==ds]
            print(ds)
            #print(section_info)
            si = section_info.at[0,"Start_index"]
            ei = section_info.at[0,"End_index"]+1
            file_data = file_contents[si:ei]
            section, definition = ds.split('|')
            section = section.strip()
            section_meta = metadata.get(definition.strip())
            curve_names = list(section_meta.keys())
            wrap = check_wrap_setting(file_contents)
            if wrap:
                logger.info('WRAP:YES')
                if curve_names[0].upper()=='DEPTH':
                    unwrapped_data = list()
                    for i,line in enumerate(file_data):
                        if len(line.strip().split())==1:
                            depth = list()
                            depth = line.strip().split()
                            c_left = cn-1
                            for ci,cline in enumerate(file_data[i+1:]):
                                cline_data = cline.strip().split()
                                depth.extend(cline_data)
                                c_left = c_left-len(cline_data)
                                if c_left<=0:
                                    unwrapped_data.append(depth)
                                    break
                    fixed_file_contents = list()
                    for line in unwrapped_data:
                        for iv,val in enumerate(line):
                            if '-999.25' in val:
                                line[iv]='NaN'
                    fixed_file_contents.append(line)
                else:
                    logger.error('DEPTH should be the first curve')
            else:
                file_data = fix_file_contents(file_data, dlm=dlm)
            section_file = ''.join([os.path.splitext(csvfile)[0],'_',re.sub(' ','_',section),'.csv'])
            print(section_file)
            col_names = ','.join(curve_names)
            save_to_csv(file_data, section_file, col_names)
    metadata['Data files']={}
    #create a list of file names
    fd = list()
    for ds in data_sections:
        section, definition = ds.split('|')
        section = section.strip()
        f = ''.join([os.path.splitext(csvfile)[0],'_',re.sub(' ','_',section),'.csv'])
        if os.path.isfile(f):
            temp = os.path.realpath(f)
            temp = temp[temp.find('outputDir')+8:]
            temp = temp.replace('\\','/')
            fd.append(temp[2:])
    metadata['Data files']=fd
    # print(list(metadata.keys()))
    metadata = standardize_meta_section_names(metadata)
    # print(list(metadata.keys()))
    save_metadata(metadata, csvfile.replace('csv','json'))
    """some files have versoin declared as 3 but have structure following LAS2 standard"""
    if os.path.isfile(csvfile.replace('csv','json')) and not created_files:
        try:
            logger.error('No files created')
            #print('No csv file created')
            #print(csvfile)
            #print('Trying to parse as LAS2')
            logger.error('Trying to parse as LAS2')
            parse_las2_file(metadata, file_contents, csvfile,dlm=dlm)
        except Exception as e:
            logger.error(e)


def replace_null_values_in_csv(csvfile, null_value):
    try:
        with open(csvfile, 'r+') as raw_file:
            raw_data = pd.read_csv(raw_file)
            raw_data = raw_data.replace(null_value, np.nan)
            raw_data.round(5)
            raw_data.to_csv(csvfile, index=False, na_rep='NaN')
    except Exception as e:
        print('Error while replacing '+str(null_value)+' to NaN')
        print(e)


def main():
    lasfile = sys.argv[1]
    print('Parsing file: '+lasfile)
    logger.info('Parsing file: '+lasfile)
    parse_lasfile(lasfile)


if __name__ == '__main__':
    main()
