#!/usr/bin/env python3

import os
import re
import sys
import time
import datetime
import argparse
import midas.client
import midas.file_reader
import json
from dotenv import load_dotenv

from config.setup1 import getSummary as getSetup1Summary
from config.setup2 import getSummary as getSetup2Summary
from db.rundb import RunDb

load_dotenv()

parser = argparse.ArgumentParser(description="DS Proto MIDAS RunViewer information provider")
parser.add_argument('--setup', action='store', type=int, help='DS proto setup [1, 2]', choices=[1,2])
parser.add_argument('--dump', action='store_true', help='dump json to screen without store it on database')
parser.add_argument('--run', action='store', type=int, help='run number')
parser.add_argument('--host', action='store', type=str, help='MIDAS hostname')
parser.add_argument('--expt', action='store', type=str, help='MIDAS experiment name')
parser.add_argument('--verbose', action='store_true', help='print additional info on screen')
args = parser.parse_args()

sys.dont_write_bytecode = True

# fetch whole ODB tree from file or online ODB
if args.run:
    if args.setup is None:
        print('E: missing setup option')
        sys.exit(-1)
    run = str(args.run).zfill(int(os.getenv('RUNNUMWIDTH')))
    rundir = os.getenv(f"RUNDIR{args.setup}") + '/' + f'run{run}'
    print('I: fetch ODB from run file')
    try:
        flist = os.listdir(rundir)
    except:
        print(f'E: directory {rundir} does not exist')
        sys.exit(-1)

    if len(flist) == 0:
        print(f'E: directory {rundir} is empty')
        sys.exit(-1)

    startFile = stopFile = None
    fdict = {}      # key is subrun
    for f in flist:
        if f.startswith(f'run{run}'):
            mlist = re.findall('\d+', f)
            if len(mlist) > 1:
                subrun = int(mlist[1])
            else:
                subrun = f
            fdict[subrun] = f
    sortedSubrun = sorted(fdict.keys())
    startFile = fdict[sortedSubrun[0]] 
    stopFile = fdict[sortedSubrun[-1]]

    if startFile is None or stopFile is None:
        print(f'E: startFile or stopFile not found for run {args.run}')
        sys.exit(-1)

    print(f'I: startFile: {startFile}, stopFile: {stopFile}')

    startOdb = stopOdb = None
    # start file
    mfile = midas.file_reader.MidasFile(f'{rundir}/{startFile}')
    startOdb = mfile.get_bor_odb_dump().data

    # stop file
    mfile = midas.file_reader.MidasFile(f'{rundir}/{stopFile}')
    stopOdb = mfile.get_eor_odb_dump().data

    if startOdb is None and stopOdb is None:
        print("E: no BOR/EOR ODB found")
        sys.exit(-1)
    else:
        odbSource = 'FILE'
        if(args.verbose):
            print(startOdb)
            print(stopOdb)
else:
    odbSource = 'ONLINE'
    print('I: fetch ODB from online')
    try:
        mclient = midas.client.MidasClient("rvprovider", host_name=args.host, expt_name=args.expt)
    except Exception as e:
        print(f'E: {e}')
        sys.exit(-1)
    odb = mclient.odb_get('/')
    mclient.disconnect()

summary = {}
if(args.setup == 1):
    if odbSource == 'ONLINE':
        summary = getSetup1Summary(odb)
    elif odbSource == 'FILE':
        summaryStart = getSetup1Summary(startOdb)
        summaryStop = getSetup1Summary(stopOdb)
elif(args.setup == 2):
    if odbSource == 'ONLINE':
        summary = getSetup2Summary(odb)
    elif odbSource == 'FILE':
        summaryStart = getSetup2Summary(startOdb)
        summaryStop = getSetup2Summary(stopOdb)
else:
    print('E: unknown setup number')
    sys.exit(-1)

if odbSource == 'ONLINE':
    runNumber = summary["RI"]["runNumber"]
elif odbSource == 'FILE':
    runNumber = summaryStart["RI"]["runNumber"]
    # check if stopTimestamp exists... (due to erase of last sub file)
    if 'stopTimestamp' not in summaryStop["RI"]:
        summaryStop["RI"]["stopTime"] = time.ctime(stopOdb['System']['Buffers']['SYSTEM']['Size/key']['last_written'])
        summaryStop["RI"]["stopTimestamp"] = stopOdb['System']['Buffers']['SYSTEM']['Size/key']['last_written']
        durationSec = summaryStop["RI"]["stopTimestamp"] - summaryStart["RI"]["startTimestamp"]
        durationStr = str(datetime.timedelta(seconds=durationSec))
        summaryStop["RI"]["duration"] = durationStr
        # mark the run as 'not complete': status = 'aborted'
        summaryStop["RI"]["partialRun"] = True

if args.dump:
    jsonDoc = {}
    if odbSource == 'FILE':
        summary['START'] = summaryStart
        summary['STOP'] = summaryStop
    jsonDoc = json.dumps(summary, indent=2)
    print(jsonDoc)
    sys.exit(0)

db = RunDb(os.getenv('DBHOST'), os.getenv('DBUSER'), os.getenv('DBPASS'), os.getenv('DBNAME'))

if odbSource == 'ONLINE':
    if db.hasRun(args.setup, runNumber):
        # update stop summary
        db.updateStopField(args.setup, runNumber, json.dumps(summary))
    else:
        # update start summary
        db.updateStartField(args.setup, runNumber, json.dumps(summary))
elif odbSource == 'FILE':
    if not db.hasRun(args.setup, runNumber):
        db.updateStartField(args.setup, runNumber, json.dumps(summaryStart))
        db.updateStopField(args.setup, runNumber, json.dumps(summaryStop))
    else:
        print(f"I: run {runNumber} already in db - no action executed")

sys.exit(0)
