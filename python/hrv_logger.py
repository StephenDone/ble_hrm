from timeit import default_timer

from hrv_window import HrvWindow as HrvWindow
from hrv_notification import HrvNotification
from convert import minutes_seconds


class HrvLogger:
    def __init__(self, device_name, hrv_window_size, start) -> None:
        self.device_name = device_name
        self.hrv_window = HrvWindow(hrv_window_size)
        self.start = start

    def process_hrm_data(self, data):
        # global start

        hrm_notification = HrvNotification(data)

        time_string = minutes_seconds( default_timer() - self.start )
        heart_rate_string = f'HR:{hrm_notification.heart_rate:>3d}bpm ({1000*60/hrm_notification.heart_rate:4.0f}ms)' if hrm_notification.heart_rate else ' ---- '
        interval_string = f'RR:{"["+", ".join([f"{interval:4d}" for interval in hrm_notification.rr_intervals])+"]":<13}'
        print(f"{time_string} {self.device_name:<14} {heart_rate_string}, {interval_string}")

        if hrm_notification.rr_intervals:
            for interval in hrm_notification.rr_intervals:
                (add_success, delta) = self.hrv_window.add_interval( hrm_notification.heart_rate, interval )
                if add_success:
                    if self.hrv_window.hrv_ready():
                        ( rmssd, ln_rmssd, normalised_hrv ) = self.hrv_window.hrv()
                        print(f"{' '*45}{interval:>4d}ms -> Delta:{delta:>3d}ms -> rmssd:{rmssd:3.0f}ms, ln(rmssd):{ln_rmssd:3.1f}, 0-100:{normalised_hrv:2.0f}")
                    else:
                        print(f"{' '*45}{interval:>4d}ms -> Waiting for second RR interval.")
                else:
                    print(f"{' '*45}{interval:>4d}ms -> Skipping artifact.")
