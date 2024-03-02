from enum import IntFlag
from convert import unsigned_16

class hrm_flags(IntFlag):   
    HeartRateValueFormat16Bit = 0x01,
    SensorContactStatus       = 0x02,
    SensorContactFeature      = 0x04,
    EnergyExpendedPresent     = 0x08,
    RRIntervalPresent         = 0x10,

class Hrv_notification:
    def __init__(self, data):
        flags_bitfield = data[0]

        self.flags = hrm_flags(flags_bitfield)

        if self.flags.HeartRateValueFormat16Bit in self.flags:              
            self.HeartRate = unsigned_16(data[1], data[2])
            idx = 3              
        else:
            self.HeartRate = data[1]
            idx = 2

        if self.flags.EnergyExpendedPresent in self.flags:
            self.EnergyExpended = unsigned_16(data[idx], data[idx+1])
            idx += 2

        self.RRIntervals = []

        if self.flags.RRIntervalPresent in self.flags:

            def RRByteCount(): 
                return len(data) - idx 

            #print(f"RR Byte Count={RRByteCount()}")

            while (RRByteCount() > 1):
                self.RRIntervals.append( unsigned_16(data[idx], data[idx+1]))
                idx += 2

