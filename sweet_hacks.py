import os


def mkdir_with_chmod(path_full):
    os.makedirs(path_full, exist_ok=True)
    os.chmod(path_full, 0o777)
    return path_full


def get_dirs(path):
    return [os.path.join(path, o) for o in os.listdir(path)
            if os.path.isdir(os.path.join(path, o))]


def last_modify_file(dirname="."):
    newer_file, newer_time = None, None
    for dirpath, dirs, files in os.walk(dirname):
        for filename in files:
            file_path = os.path.join(dirpath, filename)
            file_time = os.stat(file_path).st_mtime
            if newer_time is None:
                newer_file, newer_time = file_path, file_time
            if file_time > newer_time:
                newer_file, newer_time = file_path, file_time
    return newer_file, newer_time
