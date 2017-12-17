import os


def mkdir_with_chmod(path):
    path_full = os.path.join(os.getenv('DATA_DIR'), path)
    os.makedirs(path_full, exist_ok=True)
    os.chmod(path_full, 0o777)
    return path_full


def get_dirs(path):
    return [os.path.join(path, o) for o in os.listdir(path)
            if os.path.isdir(os.path.join(path, o))]
