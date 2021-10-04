import numpy as np
from datetime import date
import matplotlib.pyplot as plt
import matplotboard as mpb

BLACKLIST = [
    r'.\028\2021_10_01-1450-nosig.root',
]

samples = {}


@mpb.decl_fig
def simple_waveform(sample, board, channel, id_):
    load_data()
    waveform = samples[sample]['waveform'].array()[id_]
    times = samples[sample]['times'].array()[id_]
    plt.plot(times, waveform)


@mpb.decl_fig
def histogram(sample, key, n_bins=100, range_=None, x_label="", title=""):
    load_data()
    data = samples[sample][key].array()
    if range_ is None:
        range_ = (np.min(data), np.max(data))
    plt.hist(data, bins=n_bins, range=range_)
    plt.xlabel(x_label)
    plt.title(title)


@mpb.decl_fig
def correlation_v_bias(pmt_id, key):
    load_data()
    samples_ = [sample for sample in samples if sample[0] == pmt_id]
    avgs = []
    stds = []
    biases = []
    for sample in samples_:
        data = samples[sample][key].array()
        avgs.append(np.mean(data))
        stds.append(np.std(data))
        biases.append(sample[2])
    plt.errorbar(biases, avgs, yerr=stds)


def load_data():
    from os import walk
    from os.path import join, split
    from glob import glob
    from re import findall
    import uproot
    rex = r"(\d{4}_\d{2}_\d{2})-(\d*)-(.*)\.root"

    root_files = [y for x in walk('.') for y in glob(join(x[0], '*.root'))]
    for r_file in root_files:
        if r_file in BLACKLIST:
            print(f'blacklisting {r_file}')
            continue
        *_, pmt_id, filename = split(r_file)
        date, voltage, signal = findall(rex, filename)[0]
        key = (pmt_id[2:], date, voltage, signal)
        if key not in samples:
            samples[key] = uproot.open(r_file)['Events']


def main():

    load_data()
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
        pfx = f"{pmt_id}_{date_}_{voltage}_{signal}_"
        figures[pfx+'wave_10'] = simple_waveform(sample, None, 1, 10)

        for key, kwargs in keys:
            figures[pfx+key] = histogram(sample, key, **kwargs)

    for key, _ in keys:
        for pmt_id in ['007', '028']:
            figures[pmt_id+"_"+key+'_vs_bias'] = correlation_v_bias(pmt_id, key)

    mpb.configure(multiprocess=True, output_dir=f'PMTAnalysis-{date.today().isoformat()}')
    mpb.render(figures)
    mpb.generate_report(figures, 'PMT Results')


if __name__ == "__main__":
    main()

