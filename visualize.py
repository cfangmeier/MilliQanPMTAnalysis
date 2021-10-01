import numpy as np
import matplotlib.pyplot as plt
import matplotboard as mpb

samples = {}


@mpb.decl_fig
def simple_waveform(sample, board, channel, id_):
    waveform = samples[sample]['waveform'].array()[id_]
    times = samples[sample]['times'].array()[id_]
    plt.plot(times, waveform)


def load_data():
    from os import walk
    from os.path import join, split
    from glob import glob
    from re import findall
    import uproot
    rex = r"(\d{4}_\d{2}_\d{2})-(\d*)-(.*)\.root"

    root_files = [y for x in walk('.') for y in glob(join(x[0], '*.root'))]
    for r_file in root_files:
        *_, pmt_id, filename = split(r_file)
        date, voltage, signal = findall(rex, filename)[0]
        samples[(pmt_id, date, voltage, signal)] = uproot.open(r_file)['Events']


def main():
    import webbrowser

    load_data()
    figures = {}
    for sample in samples:
        pmt_id, date, voltage, signal = sample
        figures[f"{pmt_id}_{date}_{voltage}_{signal}"] = simple_waveform(sample, None, 1, 10)

    mpb.render(figures)
    mpb.generate_report(figures, 'PMT Results')

    webbrowser.open('./dashboard/report.html', new=2)


if __name__ == "__main__":
    main()

