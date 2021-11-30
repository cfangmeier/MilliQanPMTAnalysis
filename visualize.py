import numpy as np
from datetime import date
import matplotlib.pyplot as plt
from matplotboard import decl_fig, render, generate_report, configure, serve
from os.path import realpath
from config import the_config


@decl_fig
def simple_waveform(sample, board, channel, id_):
    from matplotboard import d
    waveform = d[sample]['waveform'].array()[id_]
    times = d[sample]['times'].array()[id_]
    plt.plot(times, waveform)


@decl_fig
def histogram(sample, key, n_bins=100, range_=None, x_label="", title=""):
    from matplotboard import d
    data = d[sample][key].array()
    if range_ is None:
        range_ = (np.min(data), np.max(data))
    plt.hist(data, bins=n_bins, range=range_)
    plt.xlabel(x_label)
    plt.title(title)


@decl_fig
def correlation_v_bias(pmt_id, key):
    from matplotboard import d
    samples_ = [sample for sample in d if sample[0] == pmt_id]
    avgs = []
    stds = []
    biases = []
    for sample in samples_:
        data = d[sample][key].array()
        avgs.append(np.mean(data))
        stds.append(np.std(data))
        biases.append(sample[2])
    plt.errorbar(biases, avgs, yerr=stds)


@decl_fig
def scaler_vs_time(sample):
    from matplotboard import d
    scaler = d[sample]['scaler'].array()
    timestamps = d[sample]['timestamp'].array()
    relative_times = (timestamps - timestamps[0]) / 60

    plt.plot(relative_times, scaler)
    plt.xlabel("Time elapsed (minutes)")
    plt.ylabel("Trigger Rate (Hz)")
    plt.ylim((0, np.max(scaler)*1.1))


@decl_fig
def trigger_rate_vs_time(sample):
    from matplotboard import d
    scaler = d[sample]['scaler'].array()
    timestamps = d[sample]['timestamp'].array()
    relative_times = timestamps - timestamps[0]
    time_deltas = timestamps[1:] - timestamps[:-1]
    hits_per_interval = scaler[1:] * time_deltas
    new_interval = (timestamps[-1] - timestamps[0]) / 100
    n_intervals = int(np.ceil(relative_times[-1] / new_interval))
    cut_times = np.array([(i+1)*new_interval for i in range(n_intervals)])

    rates_hz = []
    interval_times = []
    prev_idx = 0
    for idx, cut_time in enumerate(cut_times):
        cut_idx = np.argmax(relative_times > cut_time)
        if cut_idx == prev_idx or cut_idx == 0:
            continue
        real_interval = relative_times[cut_idx] - relative_times[prev_idx]
        hit_count = np.sum(hits_per_interval[prev_idx:cut_idx])
        # print(idx, hit_count, real_interval)
        rates_hz.append(hit_count / real_interval)
        interval_times.append(np.mean([relative_times[cut_idx], relative_times[prev_idx]]))
        prev_idx = cut_idx

    interval_times = np.array(interval_times) / 60  # -> minutes
    plt.plot(interval_times, rates_hz)
    plt.xlabel("Time elapsed (minutes)")
    plt.ylabel("Trigger Rate (Hz)")
    plt.ylim((0, np.max(rates_hz)*1.1))


@decl_fig
def trigger_rate_vs_time_v2(sample):
    from matplotboard import d
    from matplotlib.dates import DateFormatter
    from matplotlib.ticker import AutoMinorLocator
    from datetime import datetime
    scaler = d[sample]['scaler'].array()
    timestamps = d[sample]['timestamp'].array()

    mono_idxs = np.argsort(timestamps)
    scaler = scaler[mono_idxs]
    timestamps = timestamps[mono_idxs]

    in_order = 0
    out_order = 0
    for idx1, idx2 in zip(mono_idxs[:-1], mono_idxs[1:]):
        if idx2 > idx1:
            in_order += 1
        else:
            out_order += 1
    print(f"{out_order}/{in_order+out_order} ({100*out_order/(out_order+in_order):.2f}%) out of order")

    timestamps_rel = timestamps - timestamps[0]

    resolution_seconds = 10
    scaler_avgs = []
    avg_times = []
    n = 0

    prev_idx = 0
    while True:
        n += 1
        cut_idx = np.argmax(timestamps_rel > n*resolution_seconds)
        if cut_idx == 0:
            break
        elif cut_idx == prev_idx:
            continue

        scaler_avgs.append(np.mean(scaler[prev_idx:cut_idx]))
        avg_times.append((n-.5)*resolution_seconds)
        prev_idx = cut_idx
    if scaler_avgs:
        datetimes = [datetime.fromtimestamp(ts+timestamps[0]) for ts in avg_times]
        plt.semilogy(datetimes, scaler_avgs)
        plt.ylim((1, np.max(scaler_avgs)*1.1))
        plt.minorticks_on()
        plt.grid(visible=True, axis="x", which='minor', linestyle="--", alpha=0.4)
        plt.grid(visible=True, axis="x", which='major')
        plt.gca().xaxis.set_major_formatter(DateFormatter('%I:%M'))
        plt.gca().xaxis.set_minor_locator(AutoMinorLocator(n=5))
        plt.xlabel("Time of Event (HH:MM)")
        plt.ylabel("Trigger Rate (Hz)")


def find_samples():
    root_file_paths, _ = the_config.get_root_files()
    sample_ids = [the_config.id_from_path(path) for path in root_file_paths]
    return sample_ids, root_file_paths


def load_data():
    from matplotboard import d
    import uproot

    sample_ids, root_file_paths = find_samples()
    for sample_id, r_file in zip(sample_ids, root_file_paths):
        if sample_id in d:
            print(f"Warning, duplicate sample with id: {sample_id}")
        d[sample_id] = uproot.open(r_file)['Events']


def main():

    sample_ids, _ = find_samples()

    figures = {}
    keys = [
        ('scaler', {}),
    #     ('area', {'range_': (0, 35), 'x_label': 'area (V*ns)'}),
    #     ('width', {'range_': (0, 500), 'x_label': 'width (ns)'}),
    #     ('noise', {}),
    #     ('peak_t', {}),
    #     ('peak_v', {}),
    ]
    for sample_id in sample_ids:
        pmt_id, date_, voltage, signal = sample_id
        pfx = f"{pmt_id}-{date_}-{voltage}-{signal}-"
        # figures[pfx+'wave_10'] = simple_waveform(sample, None, 1, 10)
        figures[pfx+'scaler_vs_time'] = scaler_vs_time(sample_id)
        figures[pfx+'trigger_rate_vs_time'] = trigger_rate_vs_time(sample_id)
        figures[pfx+'trigger_rate_vs_time_v2'] = trigger_rate_vs_time_v2(sample_id)

        # for key, kwargs in keys:
        #     figures[pfx+key] = histogram(sample_id, key, **kwargs)

    # for key, _ in keys:
    #     for pmt_id in ['007', '028', '001N', '004', '013', '015', '018', '020', '024', '028']:
    #         figures[pmt_id+"-"+key+'-vs_bias'] = correlation_v_bias(pmt_id, key)

    output_dir = f'PMTAnalysis-{date.today().isoformat()}'
    configure(
        multiprocess=True,
        output_dir=output_dir,
        data_loader=load_data,
    )
    render(figures, ncores=4)
    generate_report(figures, 'PMT Results')

    serve()


if __name__ == "__main__":
    main()

