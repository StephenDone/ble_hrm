import asyncio
import contextlib
import logging
from bleak import BleakScanner, BleakClient
from timeit import default_timer
from Hrv_window import Hrv_window as Hrv_window
from hrv_notification import Hrv_notification
from convert import ToHex, minutes_seconds

hrm_count = 1
scan_timeout = 20
window_size = 300

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

def process_hrm_data(device, data, hrv_window:Hrv_window):
    global start

    hrm_notification = Hrv_notification(data)

    time_string = minutes_seconds( default_timer() - start )
    heart_rate_string = f'HR:{hrm_notification.HeartRate:>3d}bpm ({1000*60/hrm_notification.HeartRate:4.0f}ms)' if hrm_notification.HeartRate else ' ---- '
    interval_string = f'RR:{"["+", ".join([f"{interval:4d}" for interval in hrm_notification.RRIntervals])+"]":<13}'
    print(f"{time_string} {device.name:<14} {heart_rate_string}, {interval_string}")

    if hrm_notification.RRIntervals:
        for Interval in hrm_notification.RRIntervals:
            (add_success, delta) = hrv_window.add_interval( hrm_notification.HeartRate, Interval )
            if add_success:
                if hrv_window.hrv_ready():
                    ( rmssd, ln_rmssd, normalised_hrv ) = hrv_window.hrv()
                    print(f"{' '*45}{Interval:>4d}ms -> Delta:{delta:>3d}ms -> rmssd:{rmssd:3.0f}ms, ln(rmssd):{ln_rmssd:3.1f}, 0-100:{normalised_hrv:2.0f}")
                else:
                    print(f"{' '*45}{Interval:>4d}ms -> Waiting for second RR interval.")
            else:
                print(f"{' '*45}{Interval:>4d}ms -> Skipping artifact.")

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

            # hrv_window = Hrv_window(300)
            hrv_window = Hrv_window(window_size)

            def hrm_callback(_, data):                
                logging.info(f'{device.name} received {ToHex(data)}')
                process_hrm_data( device, data, hrv_window )

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