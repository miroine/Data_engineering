# Corporate_WellDB_Log_Parser_Las

Parser extracting data from *.las files
The metadata is saved to a *.json file while the curve data is saved to a csv file/files.
The parser deals with most of the files following LAS v2 and LAS v3 standard.

Following transformations are performed in the process:
- '-999.25', which in most cases is used as NULL representation is replaced with 'NaN'
- in case of files following LAS v3 standard the curves from each section will be saved in a separate file
- metadata section names are standardized according to the names listed in LAS version 2 standard
http://www.cwls.org/wp-content/uploads/2017/02/Las2_Update_Feb2017.pdf
- in case of files formatted according to LASv3 standard, the sections containing user INPUT are excluded from csv

All the inconsistncies in file formatting that were identified during the development of this parser are listed in the following document:
https://statoilsrm.sharepoint.com/:w:/r/sites/Data-Engineering-Team/Shared%20Documents/Data/REP-WellDB-LAS%20v2%20v3%20errors.docx?d=w860df0c2f30745179b6555d7aa9e8c52&csf=1&e=6T7RhK


## Prerequisites

The parser was created using Python 3.6.5 along with modeules/packages listed in the requirements.txt file


## Authors

uwo@equinor.com
