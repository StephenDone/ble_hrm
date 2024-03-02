import asyncio
import contextlib
from bleak import BleakScanner, BleakClient
from timeit import default_timer
from hrm_uuids import hrm_service, hrm_characteristic
from hrv_logger import HrvLogger

HRM_COUNT       =   1
SCAN_TIMEOUT    =  20
HRV_WINDOW_SIZE = 300

start = None

async def connect_to_device( connect_lock: asyncio.Lock, device ):
    try:
        async with contextlib.AsyncExitStack() as stack:

            async with connect_lock:

                client = BleakClient(device)

                await stack.enter_async_context(client)

            hrv_logger = HrvLogger(device.name, HRV_WINDOW_SIZE, start )

            def hrm_callback(_, data):                
                hrv_logger.process_hrm_data( data )

            await client.start_notify(hrm_characteristic, hrm_callback)
            await asyncio.sleep(3600)
            await client.stop_notify(hrm_characteristic)

    except Exception as e:
        print(f'error with {device}: {e}')


async def get_hrm_devices(device_count):

    devices = []
    def detection_callback(device, advertising_data):
        if not device in devices:
            print(f'found {device.name}')
            devices.append( device )

            if len(devices)==device_count:
                device_future.set_result(devices)

    device_future = asyncio.Future()

    print(f'Scanning for {device_count} device(s) with {SCAN_TIMEOUT}s timeout...')

    async with BleakScanner( detection_callback, [hrm_service], scanning_mode='active' ) as scanner:
        try:
            async with asyncio.timeout(SCAN_TIMEOUT):
                return await device_future
        except asyncio.TimeoutError:
            print(f"Timed out scanning for {device_count} HRM sensor{'s' if device_count>1 else ''}")
            return None


async def main():

    global start
    start = default_timer()

    devices = await get_hrm_devices(device_count=HRM_COUNT)

    if not devices: return

    print(f'found {len(devices)} device(s): {", ".join([device.name for device in devices])}')

    disconnect_future = asyncio.Future()

    connect_lock = asyncio.Lock()
    await asyncio.gather(
        *(
            connect_to_device(connect_lock, device) for device in devices
        )
    )

asyncio.run(main())