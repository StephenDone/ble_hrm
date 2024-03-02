import asyncio
import aioconsole
from bleak import BleakScanner, BleakClient
from timeit import default_timer
from hrm_uuids import hrm_service, hrm_characteristic
from hrv_logger import HrvLogger

SCAN_TIMEOUT    =  20
HRV_WINDOW_SIZE = 300

async def main():

    start = default_timer()

    def match_hrm_uuid(device, advertisement_data):
        return hrm_service in advertisement_data.service_uuids

    device = await BleakScanner.find_device_by_filter(filterfunc=match_hrm_uuid, timeout=SCAN_TIMEOUT)

    if not device: 
        print('HRM device not found')
        return

    print(f'found device: {device.name}')

    hrv_logger = HrvLogger(device.name, HRV_WINDOW_SIZE, start)

    def hrm_callback(_, data):                
        hrv_logger.process_hrm_data( data )

    async with BleakClient(device) as client:
        await client.start_notify(hrm_characteristic, hrm_callback)
        print('Press Enter to exit.')
        await aioconsole.ainput()
        print('Exiting...')
        await client.stop_notify(hrm_characteristic)

asyncio.run(main())
