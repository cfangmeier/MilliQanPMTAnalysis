from dataclasses import dataclass, field, fields
from os import environ
from os.path import dirname, split, join
from pathlib import Path

root_dir = dirname(__file__)
data_dir = join(root_dir, 'data')


@dataclass
class Config:
    """
    Config: Helps manage configuration. Fields can be any of:
      - bool
      - str
      - int
      - float
      - pathlib.Path
      - list[str | int | float]
    """
    RECREATE: bool = False
    VERBOSE: bool = False
    INCLUDE_WAVEFORMS: bool = True
    RAW_DATA_ROOT: Path = "data\\"
    PROCESSED_DATA_ROOT: Path = "processed_data\\"
    BANNED: list[str] = field(default_factory=list)  # Patterns for disallowed files
    FILES: list[str] = field(default_factory=list)  # Patterns for allowed files - overrides BANNED
    AAAAAAAAAH: bool = False

    def __post_init__(self):
        for f in fields(self):
            name = f.name
            default = getattr(self, name)
            type_ = f.type

            # get from ./env.py, fallback to environment variables, and then defaults
            try:
                import env
                val = getattr(env, name)
            except (ImportError, AttributeError):
                val = environ.get(name, default)

            if type_ == bool:
                if str(val).lower() == "true":
                    val = True
                elif str(val).lower() == "false":
                    val = False
                else:
                    raise ValueError(f"Boolean config \"{name}\" must be True or False, found \"{val}\"")
            elif getattr(type_, "__origin__", None) == list:
                if isinstance(val, str):
                    import re
                    val = re.split(',', val)
                if (sub_type := type_.__args__[0]) in (int, float, str):
                    val = [sub_type(v) for v in val]
            else:
                val = type_(val)

            setattr(self, name, val)

    def get_files(self, base_dir: Path, extension: str):
        import os.path
        found_paths = []
        banned_paths = []
        for root, _, files in os.walk(base_dir):
            for file in files:
                if not file.endswith(extension):
                    continue
                path = Path(os.path.join(root, file))

                if self.FILES:
                    if any(path.match(pattern) for pattern in self.FILES):
                        found_paths.append(path)
                    else:
                        banned_paths.append(path)
                else:
                    if any(path.match(pattern) for pattern in self.BANNED):
                        banned_paths.append(path)
                    else:
                        found_paths.append(path)

        if self.VERBOSE:
            print(f"Blacklisted the following files:")
            for banned_path in banned_paths:
                print(f"    {banned_path}")
            print(f"Found {len(found_paths)} files to process. They are:")
            for found_path in found_paths:
                print(f"    {found_path}")
        return found_paths, banned_paths

    def get_root_files(self):
        return self.get_files(self.PROCESSED_DATA_ROOT, ".root")

    def get_dat_files(self):
        return self.get_files(self.RAW_DATA_ROOT, ".dat")

    def id_from_path(self, path: Path):
        from re import findall
        date_, voltage, signal = findall(r"(\d{4}_\d{2}_\d{2})-(\d*)-(.*)\.root", path.name)[0]
        pmt_id = list(path.relative_to(self.PROCESSED_DATA_ROOT).parents)[-2].name
        return pmt_id, date_, voltage, signal

    def find_samples(self, pmt_id=None, date=None, voltage=None, signal=None):
        root_file_paths, _ = self.get_root_files()
        samples = []
        for root_file_path in root_file_paths:
            sample_id = self.id_from_path(root_file_path)
            if ((pmt_id is None or pmt_id == sample_id[0]) and (date is None or date == sample_id[1]) and
                    (voltage is None or date == sample_id[2]) and (signal is None or date == sample_id[3])):
                samples.append((sample_id, root_file_path))
        return list(zip(*samples))

    def all_pmt_ids(self):
        samples, _ = self.find_samples()
        return {sample[0] for sample in samples}

    def all_dates(self):
        samples, _ = self.find_samples()
        return {sample[1] for sample in samples}

    def all_voltages(self):
        samples, _ = self.find_samples()
        return {sample[2] for sample in samples}

    def all_signals(self):
        samples, _ = self.find_samples()
        return {sample[3] for sample in samples}


the_config = Config()
