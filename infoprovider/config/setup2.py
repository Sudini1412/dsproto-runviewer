
from providers.run import RunProvider
from providers.shift import ShiftProvider
from providers.logger import LoggerProvider
from providers.sequencer import SequencerProvider
from providers.vx2740 import VX2740Provider

def getSummary(odb):

    dictMerged = {}

    if 'Runinfo' in odb:
        dictMerged['RI'] = RunProvider(odb['Runinfo']).getData()

    if 'Sequencer' in odb:
        if bool(odb['Sequencer']['State']['Running']) is True:
            dictMerged['SQ'] = SequencerProvider(odb['Sequencer']).getData()

    if 'Edit on Start' in odb['Experiment']:
        dictMerged['SI'] = ShiftProvider(odb['Experiment']['Edit on Start']).getData()

    if 'Logger' in odb:
        dictMerged['LI'] = LoggerProvider(odb['Logger']).getData()

    if 'VX2740_Data_Group_000' in odb['Equipment']:
        dictMerged['BD'] = VX2740Provider(odb['Equipment']['VX2740_Config_Group_000'], odb['Equipment']['VX2740_Data_Group_000']).getData()

    return dictMerged
