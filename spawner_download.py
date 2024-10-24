import multiprocessing
import time
import os
from downloader import download_file

def process_file(part_file, log_file, last_line_file):
    with open(part_file, 'r') as f:
        lines = f.readlines()

    if os.path.exists(last_line_file):
        with open(last_line_file, 'r') as f:
            last_line = f.read().strip()
            if last_line:
                lines = lines[:int(last_line) + 1]

    # Load the log file to check already processed files
    if os.path.exists(log_file):
        with open(log_file, 'r') as log_f:
            processed_files = set(log_f.read().splitlines())
    else:
        processed_files = set()

    with open(log_file, 'a') as log_f:
        for idx, line in enumerate(lines):
            name, file_id = line.split('-')
            if file_id not in processed_files:
                try:
                    success = download_file(name.strip(), file_id.strip())
                    if not success:
                        log_f.write(line)
                        time.sleep(60)
                except Exception as e:
                    print(f"Error downloading file {file_id}: {e}")
            
            with open(last_line_file, 'w') as f:
                f.write(str(idx))

# Worker function to be called by each process
def worker(part_file, log_file, last_line):
    process_file(part_file, log_file, last_line)

def split_file(file_path, num_parts):
    os.mkdir(f'temp/{file_name}/')

    with open(file_path, 'r') as f:
        lines = f.readlines()

    chunk_size = len(lines) // num_parts
    for i in range(num_parts):
        part_file = f'temp/{file_name}/part_{i + 1}.txt'
        with open(part_file, 'w') as part_f:
            start = i * chunk_size
            end = (i + 1) * chunk_size if i < num_parts - 1 else len(lines)
            part_f.writelines(lines[start:end])


if __name__ == '__main__':
    num_workers = 8
    processes = []
    file_name = "complete_2007"

    if not os.path.exists('temp/'):
        os.mkdir('temp/')

    if not os.path.exists(f'temp/{file_name}'):
        split_file(f'{file_name}.txt', num_workers)
    

    if not os.path.exists(f"out/{file_name.split('_')[1]}"):
        os.makedirs(f"out/{file_name.split('_')[1]}")

    # check if folder exists and create it if not
    if not os.path.exists(f'temp/{file_name}'):
        os.makedirs(f'temp/{file_name}/')

    for i in range(1, num_workers + 1):
        part_file = f'temp/{file_name}/part_{i}.txt'
        log_file = f'temp/{file_name}/log_worker_{i}.txt'
        last_line = f'temp/{file_name}/last_line{i}.txt'
        p = multiprocessing.Process(target=worker, args=(part_file, log_file, last_line))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()
