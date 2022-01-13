import numpy as np
from datetime import date
import matplotlib.pyplot as plt
from matplotboard import decl_fig, render, generate_report, configure, serve
from os.path import realpath
from config import the_config


def decorate(sample_id):
    from matplotboard import d
    pmt_id, date_, voltage, signal = sample_id
    ts = d[sample_id]['timestamp'].array()
    duration = (ts[-1] - ts[0]) / 60
    text = (
        f"PMT ID: {pmt_id}\n"
        f"Date: {date_}\n"
        f"Duration: {duration:.2f} mins\n"
        f"Pulse Count: {len(ts)}\n"
        f"Bias: {voltage} V\n"
        f"Signal: {signal}"
        )
    plt.text(0.01, 0.99, text, transform=plt.gcf().transFigure,
             horizontalalignment="left",
             verticalalignment="top",
             bbox=dict(facecolor='white', alpha=0.9, linewidth=2.0))


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
    decorate(sample)


@decl_fig
def histogram_2d(sample, key_x, key_y, n_bins=(100, 100), range_=None, x_label="", y_label="", title=""):
    from matplotboard import d
    # from matplotlib.colors import
    data_x = d[sample][key_x].array()
    data_y = d[sample][key_y].array()
    if range_ is None or range_[0] is None:
        range_x = (np.min(data_x), np.max(data_x))
    else:
        range_x = range_[0]
    if range_ is None or range_[1] is None:
        range_y = (np.min(data_y), np.max(data_y))
    else:
        range_y = range_[1]

    plt.hist2d(data_x, data_y, bins=n_bins, range=(range_x, range_y), cmin=1)
    plt.colorbar()
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    plt.title(title)
    decorate(sample)


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
def trigger_rate_vs_time(pmt_ids):
    from matplotboard import d
    from matplotlib.dates import DateFormatter
    from matplotlib.ticker import AutoMinorLocator
    import matplotlib.colors as mcolors
    from datetime import datetime
    from random import shuffle

    samples = []
    for pmt_id in pmt_ids:
        samples.extend(the_config.find_samples(pmt_id=pmt_id)[0])

    if len(samples) <= 10:
        colors = list(mcolors.TABLEAU_COLORS.values())
    else:
        colors = list(mcolors.XKCD_COLORS.values())
        shuffle(colors)
    for sample, color in zip(samples, colors):
        scaler = d[sample]['scaler'].array()
        timestamps = d[sample]['timestamp'].array()

        mono_idxs = np.argsort(timestamps)
        scaler = scaler[mono_idxs]
        timestamps = timestamps[mono_idxs]

        # in_order = 0
        # out_order = 0
        # for idx1, idx2 in zip(mono_idxs[:-1], mono_idxs[1:]):
        #     if idx2 > idx1:
        #         in_order += 1
        #     else:
        #         out_order += 1
        # print(f"{out_order}/{in_order+out_order} ({100*out_order/(out_order+in_order):.2f}%) out of order")

        timestamps_rel = timestamps - timestamps[0]

        resolution_seconds = 20
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
            plt.semilogy(np.array(avg_times)/60, scaler_avgs, label=str(sample), color=color)
            plt.ylim((1, 10_000))
            plt.minorticks_on()
            plt.grid(visible=True, axis="both", which='minor', linestyle="--", alpha=0.4)
            plt.grid(visible=True, axis="both", which='major')
            plt.gca().xaxis.set_minor_locator(AutoMinorLocator(n=5))
            plt.xlabel("Minutes into run")
            plt.ylabel("Trigger Rate (Hz)")
    plt.legend()


@decl_fig
def observable_comparison(pmt_ids, key, sample_start=0.5, range_=None):
    from matplotboard import d

    all_data = []
    labels = []
    for pmt_id in pmt_ids:
        sample_id = the_config.find_samples(pmt_id=pmt_id)[0][0]
        sample_data = d[sample_id][key].array()
        sample_data = sample_data[int(sample_start*len(sample_data)):]
        all_data.append(sample_data)
        labels.append(pmt_id)
    labels, all_data = zip(*sorted(zip(labels, all_data)))
    plt.violinplot(all_data,
                   showextrema=False,
                   showmeans=True,
                   points=200,
                   vert=False)
    plt.yticks([x+1 for x in range(len(all_data))], labels)
    if range_ is not None:
        plt.xlim(range_)


def load_data():
    from matplotboard import d
    import uproot

    sample_ids, root_file_paths = the_config.find_samples()
    for sample_id, r_file in zip(sample_ids, root_file_paths):
        if sample_id in d:
            print(f"Warning, duplicate sample with id: {sample_id}")
        d[sample_id] = uproot.open(r_file)['Events']


def main():
    sample_ids, _ = the_config.find_samples()

    figures = {}
    for sample_id in sample_ids:
        pmt_id, date_, voltage, signal = sample_id
        pfx = f"{pmt_id}-{date_}-{voltage}-{signal}-"

        figures[pfx+'area'] = histogram(sample_id, 'area', range_=(0, 10), x_label='area (V*ns)')
        figures[pfx+'width'] = histogram(sample_id, 'width', range_=(0, 500), x_label='width (ns)')
        figures[pfx+'noise'] = histogram(sample_id, 'noise', range_=(0, 0.005), x_label='noise (V)')
        figures[pfx+'peak_t'] = histogram(sample_id, 'peak_t', range_=None, x_label='')
        figures[pfx+'peak_v'] = histogram(sample_id, 'peak_v', range_=(0, 0.5), x_label='')

        figures[pfx+'peak_v_vs_area'] = histogram_2d(sample_id, 'peak_v', 'area', x_label="peak_v", y_label="area",
                                                     n_bins=(300, 300), range_=((0, 0.4), (0, 10)))

        figures[pfx+'peak_v_vs_width'] = histogram_2d(sample_id, 'peak_v', 'width', x_label="peak_v", y_label="width",
                                                      n_bins=(300, 300), range_=((0, 0.4), (0, 500)))

    figures[f'all_trigger_rate_vs_time_v2'] = trigger_rate_vs_time(the_config.all_pmt_ids())

    figures[f'all_peak_v'] = observable_comparison(the_config.all_pmt_ids(), 'peak_v', range_=(0, 0.15))
    figures[f'all_noise'] = observable_comparison(the_config.all_pmt_ids(), 'noise', range_=(0, 0.005))
    figures[f'all_area'] = observable_comparison(the_config.all_pmt_ids(), 'area', range_=(0, 10))
    figures[f'all_width'] = observable_comparison(the_config.all_pmt_ids(), 'width', range_=(0, 500))
    # figures[f'all_scaler'] = observable_comparison(the_config.all_pmt_ids(), 'scaler', )

    output_dir = f'PMTAnalysis-{date.today().isoformat()}'
    configure(
        multiprocess=True,
        output_dir=output_dir,
        data_loader=load_data,
    )
    render(figures, ncores=8)
    generate_report(figures, 'PMT Results')

    try:
        import beepy
        if the_config.AAAAAAAAAH:
            beepy.beep(sound="wilhelm")
        else:
            beepy.beep(sound="coin")
    except ImportError:
        print('\a')  # UNIX Bell thingy

    serve()


if __name__ == "__main__":
    main()

