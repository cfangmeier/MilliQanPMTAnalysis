from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import struct
import os
import os.path
import numpy as np

from config import the_config


@dataclass
class Event:
    id: int
    board: int
    channel: int
    waveform: np.ndarray
    times: np.ndarray
    range_center: int
    scaler: float
    datetime: datetime


class DRSDatFile:
    N_BINS = 1024  # number of timing bins per channel
    MAX_EVENTS = 1_000_000

    EARLY_SPLIT = 300
    EDGE_PEAK_KEEP_OUT = 10  # Clamp peak to be at least this far from the edges

    def __init__(self, path):
        self.path = path
        self.file = None
        self.channels = []
        self.bin_widths = {}
        self._events = defaultdict(list)
        with open(self.path, "rb") as file:
            self.file = file
            self._parse()
            self.file = None
        self._process()

    def _get_str(self, length):
        data = self.file.read(length)
        if len(data) == 0:
            return None
        res = struct.unpack("c" * len(data), data)
        res = b"".join(res).decode("utf-8")
        return res

    def _get_short(self, num=1):
        data = self.file.read(2 * num)
        if len(data) == 0:
            return None
        try:
            res = struct.unpack("H" * num, data)
        except struct.error:
            res = [0] * num
        return res[0] if num == 1 else np.array(res, dtype=np.int16)

    def _get_float(self, num=1):
        data = self.file.read(4 * num)
        if len(data) == 0:
            return None
        res = struct.unpack("f" * num, data)
        return res[0] if num == 1 else np.array(res, dtype=np.float32)

    def _get_int(self, num=1):
        data = self.file.read(4 * num)
        if len(data) == 0:
            return None
        res = struct.unpack("I" * num, data)
        return res[0] if num == 1 else np.array(res, dtype=np.int32)

    def _parse(self):
        file_header = self._get_str(4)
        if file_header != "DRS2":
            raise ValueError("ERROR: unrecognized header " + file_header)

        timing_header = self._get_str(4)
        if timing_header != "TIME":
            raise ValueError("ERROR: unrecognized time header " + timing_header)

        # Parse board information
        while True:
            board_header = self._get_str(2)
            if board_header != "B#":
                self.file.seek(-2, 1)
                break
            board_number = self._get_short()
            print(f"Found board {board_number}")

            # Parse channel information
            while True:
                test = self._get_str(1)
                if test != "C":
                    self.file.seek(-1, 1)
                    break

                channel_number = int(self._get_str(3))
                print("Found channel #" + str(channel_number))
                self.channels.append((board_number, channel_number))
                self.bin_widths[(board_number, channel_number)] = self._get_float(self.N_BINS)

        # Parse event information
        event_count = 0
        while True:
            event_header = self._get_str(4)
            if event_header != "EHDR":
                self.file.seek(-4, 1)
                break
            event_count += 1
            if not event_count % 1000:
                print(f"Found {event_count} events")
            if event_count > self.MAX_EVENTS:
                print("Hit max number of events. Stopping now")
                break

            event_serial_number = self._get_int()
            year = self._get_short()
            month = self._get_short()
            day = self._get_short()
            hour = self._get_short()
            minute = self._get_short()
            second = self._get_short()
            millisecond = self._get_short()
            dt = datetime(year=year, month=month, day=day, hour=hour,
                          minute=minute, second=second, microsecond=millisecond*1000)
            range_center = self._get_short()

            if self._get_str(2) != "B#":
                raise ValueError(f"Bad format for event {event_serial_number}")
            board_number = self._get_short()

            if self._get_str(2) != "T#":
                raise ValueError(f"Bad format for event {event_serial_number}")
            trigger_cell = self._get_short()

            # Read event info for each channel
            while True:
                if self._get_str(1) != "C":
                    self.file.seek(-1, 1)
                    break
                channel_number = int(self._get_str(3))
                channel_scaler = self._get_int()
                waveform = self._get_short(self.N_BINS)
                waveform = waveform/65535.0 + (range_center/1000.0) - 0.5
                event = Event(
                    id=event_serial_number,
                    board=board_number,
                    channel=channel_number,
                    waveform=waveform,
                    times=np.cumsum(self.bin_widths[(board_number, channel_number)]),
                    range_center=range_center,
                    scaler=channel_scaler,
                    datetime=dt)
                self._events[(board_number, channel_number)].append(event)

    def _process(self):
        for channel in self.channels:
            for event in self._events[channel]:
                if not event.id % 1000:
                    print(f"Processing event {channel}:{event.id}")

                # If pulse is negative, invert the waveform
                if abs(min(event.waveform)) > abs(max(event.waveform)):
                    event.waveform *= -1

                # Here, we clip the peak to be sufficiently far from the start and end of the sample
                peak_idx = np.clip(np.argmax(event.waveform),
                                   self.EDGE_PEAK_KEEP_OUT,
                                   self.N_BINS-self.EDGE_PEAK_KEEP_OUT)
                peak_v = event.waveform[peak_idx]

                pre_peak_waveform = event.waveform[:peak_idx]
                post_peak_waveform = event.waveform[peak_idx:]
                noise_est = 0.5 * (np.percentile(event.waveform[:100], 95) - np.percentile(event.waveform[:100], 5))

                # Start and end of pulse is clamped to be at least .25*EDGE_PEAK_KEEP_OUT from the edge
                try:
                    pulse_start_idx = max(np.nonzero(pre_peak_waveform > noise_est)[0][-1]+1,
                                          self.EDGE_PEAK_KEEP_OUT//4)
                except IndexError:
                    pulse_start_idx = self.EDGE_PEAK_KEEP_OUT//4
                try:
                    pulse_end_idx = min(np.nonzero(post_peak_waveform < noise_est)[0][0]+peak_idx,
                                        self.N_BINS - self.EDGE_PEAK_KEEP_OUT//4)
                except IndexError:
                    pulse_end_idx = self.N_BINS - self.EDGE_PEAK_KEEP_OUT//4

                t_peak = event.times[peak_idx]
                offset = np.mean(event.waveform[:int(pulse_start_idx * 3 / 4)])
                width = event.times[pulse_end_idx] - event.times[pulse_start_idx]
                pre_pulse_noise = 0.5 * (np.percentile(event.waveform[:int(pulse_start_idx * 3 / 4)], 95) -
                                         np.percentile(event.waveform[:int(pulse_start_idx * 3 / 4)], 5))

                event.waveform = event.waveform - offset
                area = max(np.trapz(event.waveform[pulse_start_idx:pulse_end_idx],
                                    event.times[pulse_start_idx:pulse_end_idx]),
                           0.0)
                event.waveform = event.waveform + offset

                event.area = area
                event.width = width
                event.noise = pre_pulse_noise
                event.peak_t = t_peak
                event.peak_v = peak_v

    def to_root(self, root_file_path):
        import uproot
        root_file = uproot.recreate(root_file_path)

        events = defaultdict(list)
        for channel in self.channels:
            for event in self._events[channel]:

                fields = ['id', 'board', 'channel', 'scaler',
                          'area', 'width', 'noise', 'peak_t', 'peak_v']
                if the_config.INCLUDE_WAVEFORMS:
                    fields.append('times')
                    fields.append('waveform')
                for field in fields:
                    events[field].append(getattr(event, field))
                events['timestamp'].append(event.datetime.timestamp())

        for key, val in events.items():
            events[key] = np.array(val)

        root_file['Events'] = events
        root_file.close()


def process_all():
    found_paths, blacklisted_paths = the_config.get_dat_files()
    for (idx, dat_file_path) in enumerate(found_paths):
        relative_path = dat_file_path.relative_to(the_config.RAW_DATA_ROOT)
        root_file_path = (Path(the_config.PROCESSED_DATA_ROOT) / relative_path).with_suffix(".root")

        if the_config.RECREATE or not root_file_path.is_file():
            print(f"Processing file       ({idx+1}/{len(found_paths)}): {dat_file_path.name}")
            root_file_path.parent.mkdir(parents=True, exist_ok=True)
            drs = DRSDatFile(dat_file_path)
            drs.to_root(root_file_path)
        else:
            print(f"File exists, Skipping ({idx+1}/{len(found_paths)}): {dat_file_path.name}")


if __name__ == "__main__":
    process_all()
