import argparse
import asyncio
import contextlib
import logging
import time
from typing import Iterable
from enum import IntFlag
from bleak import BleakScanner, BleakClient
from timeit import default_timer
from collections import deque
import math

hrm_count = 1
scan_timeout = 20

hrm_service        = '0000180d-0000-1000-8000-00805f9b34fb'
hrm_characteristic = '00002a37-0000-1000-8000-00805f9b34fb'

start = None

def print_uuids(client:BleakClient, ShowCharacteristicDescriptors:bool=False):

    for handle in client.services.services:
        svc = client.services.services[handle]
        print(f"{handle:<2}        {svc.uuid}  {' '*44}  {svc.description}")

        for char in svc.characteristics:
            print(f"   {char.handle:<2}     {char.uuid}  {f'{char.properties}':<44}  {char.description}")

            if(ShowCharacteristicDescriptors):
                for des in char.descriptors:
                    print(f"      {des.handle:<2}  {des.uuid}  {' '*44}  {des.description.replace('Client Characteristic Configuration','CCCD')}")

        print()

def ToHex(bytes):
    return f'[{" ".join(map("{:02x}".format, bytes))}]'

def unsigned_16(b1, b2):
    return b1 | b2 << 8

class hrm_flags(IntFlag):   
    HeartRateValueFormat16Bit = 0x01,
    SensorContactStatus       = 0x02,
    SensorContactFeature      = 0x04,
    EnergyExpendedPresent     = 0x08,
    RRIntervalPresent         = 0x10,

class Hrv_window:
    def __init__(self, window_size):
        self.fifo = deque([], window_size)
        self.dirty = False

        self.rmssd = 0
        self.ln_rmssd = 0
        self.norm_hrv = 0

    def is_artifact( self, hr, interval ):
        hr_ms = 1000 * 60 / hr

        upper_bound = hr_ms * 1.3
        lower_bound = hr_ms * 0.7

        result = (interval > upper_bound) \
              or (interval < lower_bound)
        
        if result:
            print(f'is_artifact: {lower_bound:.0f} < {interval} < {upper_bound:.0f}')

        return result

    def add_interval(self, hr, interval):
        if self.is_artifact( hr, interval ):
            pass
            # print(f'Skipping artifact: {interval}ms')
        else:
            self.fifo.append(interval)
            self.dirty = True

    def add_intervals(self, hr, intervals):
        for interval in intervals:
            self.add_interval(hr, interval)

    def hrv_ready(self):
        return len(self.fifo) >= 2

    def print_window(self):
        print(
            f'{", ".join([f"{interval:4d}" for interval in self.fifo])}'
        )

    def calc_hrv(self):
        if not self.hrv_ready(): return False
        if not self.dirty: return True

        total = 0
        for rr in self.fifo: total += rr

        sd_total = 0
        for i in range(0, len(self.fifo)-1):
            sd_total += (self.fifo[i] - self.fifo[i+1])**2

        self.rr_avg   = total / len(self.fifo)
        self.rmssd    = math.sqrt(sd_total / len(self.fifo))
        self.ln_rmssd = math.log(self.rmssd, math.e)
        self.norm_hrv = self.ln_rmssd * 100 / 6.5

        self.dirty = False
        return True

    def rr_avg_as_string(self):
        return f'{(f"{self.rr_avg:.0f}ms" if self.hrv_ready() else "---")}'

    def rmssd_as_string(self):
        return f'{(f"{self.rmssd:.0f}ms" if self.hrv_ready() else "---")}'
    
    def ln_rmssd_as_string(self):
        return f'{(f"{self.ln_rmssd:.1f}" if self.hrv_ready() else "---")}'

    def norm_hrv_as_string(self):
        return f'{(f"{self.norm_hrv:.0f}" if self.hrv_ready() else "---")}'

    def full_hrv_as_string(self):
        self.calc_hrv()
        return f'RRAVG={self.rr_avg_as_string():>6}, RMSSD={self.rmssd_as_string():>5}, ln(RMSSD)={self.ln_rmssd_as_string():>3}, 0-100 score={self.norm_hrv_as_string():>3}'

class Hrv_stats:
    def __init__(self):
        self.window_15 = Hrv_window(15)
        self.window_60 = Hrv_window(60)
        self.window_300 = Hrv_window(300)

    def add_intervals(self, hr, intervals):
        self.window_15.add_intervals( hr, intervals )
        self.window_60.add_intervals( hr, intervals )
        self.window_300.add_intervals( hr, intervals )

    def calc_hrv(self):
        self.window_15.calc_hrv()
        self.window_60.calc_hrv()
        self.window_300.calc_hrv()

    def print_windows(self):
        self.window_15.print_window()
        self.window_60.print_window()
        self.window_300.print_window()

    def print_hrv(self):
        print(self.window_15.full_hrv_as_string())
        print(self.window_60.full_hrv_as_string())
        print(self.window_300.full_hrv_as_string())


def process_hrm_data(device, data, hrv_stats:Hrv_stats):
    global start

    flags_bitfield = data[0]

    flags = hrm_flags(flags_bitfield)

    if flags.HeartRateValueFormat16Bit in flags:              
        HeartRate = unsigned_16(data[1], data[2])
        idx = 3              
    else:
        HeartRate = data[1]
        idx = 2

    if flags.EnergyExpendedPresent in flags:
        EnergyExpended = unsigned_16(data[idx], data[idx+1])
        idx += 2

    RRIntervals = []

    if flags.RRIntervalPresent in flags:
        # This is a local function
        def RRByteCount(): 
            return len(data) - idx 

        #print(f"RR Byte Count={RRByteCount()}")

        while (RRByteCount() > 1):
            RRIntervals.append( unsigned_16(data[idx], data[idx+1]))
            idx += 2

    if RRIntervals:
        hrv_stats.add_intervals( HeartRate, RRIntervals )
        hrv_stats.calc_hrv()

    time_string = time.strftime( "%M:%S", time.gmtime( default_timer() - start ) )
    heart_rate_string = f'HR:{HeartRate:>3d}bpm ({1000*60/HeartRate:4.0f}ms)' if HeartRate else ' ---- '
    interval_string = f'RR:{"["+", ".join([f"{interval:4d}" for interval in RRIntervals])+"],":<13}'
    # window_string = f'15s:{hrv_stats.window_15.rmssd_as_string():>5},  60s:{hrv_stats.window_60.rmssd_as_string():>5},  5min:{hrv_stats.window_300.rmssd_as_string():>5}'
    window_string = f'5 min window:[ {hrv_stats.window_300.full_hrv_as_string()} ]'

    print(f"{time_string} {device.name:<14} {heart_rate_string}, {interval_string} {window_string}")


async def connect_to_device( connect_lock: asyncio.Lock, device ):
    logging.info(f'starting {device.name} task')

    try:
        async with contextlib.AsyncExitStack() as stack:

            # Trying to establish a connection to two devices at the same time
            # can cause errors, so use a lock to avoid this.
            async with connect_lock:

                client = BleakClient(device)

                await stack.enter_async_context(client)

                # This will be called immediately before client.__aexit__ when
                # the stack context manager exits.
                stack.callback(logging.info, f'disconnecting from {device.name}')

            # The lock is released here. The device is still connected and the
            # Bluetooth adapter is now free to scan and connect another device
            # without disconnecting this one.

            hrv_stats = Hrv_stats()

            def hrm_callback(_, data):                
                logging.info(f'{device.name} received {ToHex(data)}')
                process_hrm_data( device, data, hrv_stats )

            await client.start_notify(hrm_characteristic, hrm_callback)
            await asyncio.sleep(3600)
            await client.stop_notify(hrm_characteristic)

        # The stack context manager exits here, triggering disconnection.

        logging.info(f'disconnected from {device}')

    except Exception:
        logging.exception(f'error with {device}')


async def get_hrm_devices(device_count):
    devices = []
    def detection_callback(device, advertising_data):
        if not device in devices:
            print(f'found {device.name}')
            devices.append( device )

            if len(devices)==device_count:
                device_future.set_result(devices)

    device_future = asyncio.Future()

    print(f'Scanning for {device_count} device(s) with {scan_timeout}s timeout...')

    async with BleakScanner( detection_callback, [hrm_service], scanning_mode='active' ) as scanner:
        try:
            async with asyncio.timeout(scan_timeout):
                return await device_future
        except asyncio.TimeoutError:
            print(f"Timed out scanning for {device_count} HRM sensor{'s' if device_count>1 else ''}")
            return None


async def main():
    global start
    start = default_timer()

    # logging.basicConfig(level=logging.INFO)

    devices = await get_hrm_devices(device_count=hrm_count)

    if not devices: return

    print(f'found devices: {", ".join([device.name for device in devices])}')

    disconnect_future = asyncio.Future()

    connect_lock = asyncio.Lock()
    await asyncio.gather(
        *(
            connect_to_device(connect_lock, device) for device in devices
        )
    )

asyncio.run(main())