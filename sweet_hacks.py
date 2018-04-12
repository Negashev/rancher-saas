import os
import shutil
import time


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


def get_size(start_path='.', conversion=1e-9):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size * conversion


def recursive_copy_and_sleep_files(sleep_time, source_folder, destination_folder, root, files):
    for item in files:
        src_path = os.path.join(root, item)
        dst_path = os.path.join(destination_folder, src_path.replace(source_folder, "")[1:])
        time.sleep(sleep_time)
        if os.path.exists(dst_path):
            if os.stat(src_path).st_mtime > os.stat(dst_path).st_mtime:
                shutil.copy2(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)


def recursive_copy_and_sleep_dirs(source_folder, destination_folder, root, dirs):
    for item in dirs:
        src_path = os.path.join(root, item)
        dst_path = os.path.join(destination_folder, src_path.replace(source_folder, "")[1:])
        if not os.path.exists(dst_path):
            os.mkdir(dst_path)


def recursive_copy_and_sleep(sleep_time, source_folder, destination_folder):
    "Copies files from `SOURCE` one at a time to `TARGET`, sleeping in between operations"
    for root, dirs, files in os.walk(source_folder):
        recursive_copy_and_sleep_files(sleep_time, source_folder, destination_folder, root, files)
        recursive_copy_and_sleep_dirs(source_folder, destination_folder, root, dirs)
    return True


def truncate_dir(path):
    for root, dirs, files in os.walk(path):
        for f in files:
            os.unlink(os.path.join(root, f))
        for d in dirs:
            shutil.rmtree(os.path.join(root, d))