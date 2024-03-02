from enum import IntFlag
from convert import unsigned_16

class HrmFlags(IntFlag):   
    HEART_RATE_VALUE_FORMAT_16_BIT = 0x01,
    SENSOR_CONTACT_STATUS          = 0x02,
    SENSOR_CONTACT_FEATURE         = 0x04,
    ENERGY_EXPENDED_PRESENT        = 0x08,
    RR_INTERVAL_PRESENT            = 0x10,

class HrvNotification:
    def __init__(self, data):
        flags_bitfield = data[0]

        self.flags = HrmFlags(flags_bitfield)

        if self.flags.HEART_RATE_VALUE_FORMAT_16_BIT in self.flags:              
            self.heart_rate = unsigned_16(data[1], data[2])
            idx = 3              
        else:
            self.heart_rate = data[1]
            idx = 2

        if self.flags.ENERGY_EXPENDED_PRESENT in self.flags:
            self.energy_expended = unsigned_16(data[idx], data[idx+1])
            idx += 2

        self.rr_intervals = []

        if self.flags.RR_INTERVAL_PRESENT in self.flags:

            def rr_byte_count(): 
                return len(data) - idx 

            #print(f"RR Byte Count={RRByteCount()}")

            while (rr_byte_count() > 1):
                self.rr_intervals.append( unsigned_16(data[idx], data[idx+1]))
                idx += 2

