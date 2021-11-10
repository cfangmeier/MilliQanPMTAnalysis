import numpy as np
from datetime import date
import matplotlib.pyplot as plt
from matplotboard import decl_fig, render, generate_report, configure, serve
from os.path import realpath

BLACKLIST = [
    r'*\2021_10_01-*-*.root',
    r'*\Bad-2021_10_06-*-*.root',
]

DATA_ROOT = realpath(r"C:\Users\Husker\University of Nebraska-Lincoln\UNL-Nebraska Detector Lab - PMTData\\")

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
def trigger_rate_vs_time(sample):
    from matplotboard import d
    scaler = d[sample]['scaler']
    timestamps = d[sample]['timestamp'].array()
    timestamps = (timestamps - timestamps[0])/60
    plt.plot(timestamps, scaler)
    plt.xlabel("Time elapsed (minutes)")
    plt.ylabel("Trigger Rate (Hz)")


def find_samples():
    from os import walk
    from os.path import join, split
    from glob import glob
    from re import findall
    rex = r"(\d{4}_\d{2}_\d{2})-(\d*)-(.*)\.root"

    root_files = [y for x in walk(DATA_ROOT) for y in glob(join(x[0], '*.root'))]
    for bl in BLACKLIST:
        for blf in glob(join(DATA_ROOT, bl)):
            try:
                root_files.remove(blf)
                print(f"Blacklisted {blf}")
            except ValueError:
                pass
    samples = []
    for r_file in root_files:
        path, filename = split(r_file)
        _, pmt_id = split(path)
        date_, voltage, signal = findall(rex, filename)[0]
        samples.append((pmt_id, date_, voltage, signal))
    return samples, root_files


def load_data():
    from matplotboard import d
    import uproot

    samples, root_files = find_samples()
    for sample, r_file in zip(samples, root_files):
        d[sample] = uproot.open(r_file)['Events']


def main():

    samples, root_files = find_samples()
    figures = {}
    keys = [
        ('scaler', {}),
        ('area', {'range_': (0, 35), 'x_label': 'area (V*ns)'}),
        ('width', {'range_': (0, 500), 'x_label': 'width (ns)'}),
        ('noise', {}),
        ('peak_t', {}),
        ('peak_v', {}),
    ]
    for sample in samples:
        pmt_id, date_, voltage, signal = sample
        pfx = f"{pmt_id}-{date_}-{voltage}-{signal}-"
        # figures[pfx+'wave_10'] = simple_waveform(sample, None, 1, 10)
        figures[pfx+'trigger_rate_vs_time'] = trigger_rate_vs_time(sample)

        for key, kwargs in keys:
            figures[pfx+key] = histogram(sample, key, **kwargs)

    for key, _ in keys:
        for pmt_id in ['007', '028', '001N', '004', '013', '015', '018', '020', '024', '028']:
            figures[pmt_id+"-"+key+'-vs_bias'] = correlation_v_bias(pmt_id, key)

    output_dir = f'PMTAnalysis-{date.today().isoformat()}'
    configure(
        multiprocess=True,
        output_dir=output_dir,
        data_loader=load_data,
    )
    render(figures, ncores=8)
    generate_report(figures, 'PMT Results')

    serve()


if __name__ == "__main__":
    main()

