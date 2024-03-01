import math
from collections import deque


class Hrv_window:
    def __init__(self, window_size):
        self.window = deque([], window_size)
        self.total = 0
        self.sd_total = 0

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
            return (False, None)
        else:
            if self.window.maxlen == len(self.window):
                self.total -= self.window[0]
                self.sd_total -= (self.window[0]-self.window[1])**2
            
            self.window.append(interval)
            self.total += interval

            if len(self.window) < 2:
                difference = None
            else:
                difference = abs(self.window[-1]-self.window[-2])
                self.sd_total += (difference)**2

            return (True, difference)

    def hrv_ready(self):
        return len(self.window) >= 2

    def print_window(self):
        print(
            f'{", ".join([f"{interval:4d}" for interval in self.window])}'
        )

    def rr_avg(self): return self.total / len(self.window)

    def rmssd(self): return math.sqrt(self.sd_total / len(self.window))

    def hrv(self):
        rmssd = self.rmssd()
        ln_rmssd = math.log( rmssd, math.e ) if rmssd else 0
        normalised_hrv = ln_rmssd * 100 / 6.5
        return ( rmssd, ln_rmssd, normalised_hrv )
