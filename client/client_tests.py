import argparse
import asyncio
import aiohttp
import ssl
import random
import time
import os
import multiprocessing
import signal

async def fetch_url(session, url):
    try:
        async with session.get(url) as response:
            await response.read()
            return response.content_length or 0
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return 0

async def task_worker(task_queue, session, obj_sizes_mb, config, server_ip, https_percent, avg_object_size_mb, stats_pipe, duration):
    connections = 0
    bytes_transferred = 0
    start_time = time.time()
    last_report = start_time

    while True:
        if time.time() - start_time > duration:
            break

        try:
            url = await create_request_url(session, task_queue, obj_sizes_mb, config, server_ip, https_percent, avg_object_size_mb)
            if url is None:
                break

            # Execute fetch task
            data_size = await fetch_url(session, url)
            bytes_transferred += data_size
            connections += 1

            # Periodically send updates to the stats_pipe
            if time.time() - last_report >= 1:  # Report every second
                stats_pipe.send((bytes_transferred, connections, time.time() - start_time))
                last_report = time.time()

        except Exception as e:
            print(f"Error in task worker: {e}")

async def create_request_url(session, task_queue, obj_sizes_mb, config, server_ip, https_percent, avg_object_size_mb):
    if await task_queue.get() is None:
        return None

    # Select objects based on average object size
    close_sizes = [(i, size) for i, size in enumerate(obj_sizes_mb) if abs(size - avg_object_size_mb) < 0.5 * avg_object_size_mb]
    if not close_sizes:
        close_sizes = [(i, size) for i, size in enumerate(obj_sizes_mb)]

    index, _ = random.choice(close_sizes)
    path, _ = config[index]

    # Determine HTTP or HTTPS
    scheme = "https" if random.random() < https_percent / 100 else "http"
    return f"{scheme}://{server_ip}:{8443 if scheme == 'https' else 8080}/{path}"

def create_request_url(obj_sizes_mb, config, server_ip, https_percent, avg_object_size_mb):
    """Create request URL ensuring a mix of file types with appropriate sizes."""
    # Group files by type and size
    close_files = []
    other_files = []
    
    for i, (path, size) in enumerate(config):
        file_type = path.split('.')[-1].lower()
        if abs(size - avg_object_size_mb) < 0.5 * avg_object_size_mb:
            close_files.append((i, path, size, file_type))
        else:
            other_files.append((i, path, size, file_type))
    
    # If no files close to target size, use all files
    candidate_files = close_files if close_files else other_files
    
    # Weighted selection based on file type
    file_weights = {
        'bin': 0.4,  # 40% binary files
        'zip': 0.4,  # 40% zip files
        'docx': 0.2, # 10% docx files
    }
    
    # Filter files by type and apply weights
    weighted_files = []
    for idx, path, size, ftype in candidate_files:
        weight = file_weights.get(ftype, 0.0)
        if weight > 0:
            weighted_files.extend([idx] * int(weight * 100))
    
    # If no weighted files found, fall back to any file of appropriate size
    if not weighted_files:
        index = random.choice([i for i, _, _ in config])
    else:
        index = random.choice(weighted_files)
    
    path, _ = config[index]
    
    # Determine HTTP or HTTPS
    scheme = "https" if random.random() < https_percent / 100 else "http"
    return f"{scheme}://{server_ip}:{8443 if scheme == 'https' else 8080}/{path}"

async def connection_worker(session, obj_sizes_mb, config, server_ip, https_percent, avg_object_size_mb, stats_pipe):
    while True:
        try:
            url = create_request_url(obj_sizes_mb, config, server_ip, https_percent, avg_object_size_mb)
            data_size = await fetch_url(session, url)
            # Only send completed request data
            stats_pipe.send((data_size, 1))  # (bytes, completed_count)
        except Exception as e:
            print(f"Error in connection worker: {e}")
            await asyncio.sleep(0.1)

async def run_client_instance(server_ip, max_connections, https_percent, avg_object_size_mb, config, stats_pipe, duration):
    obj_sizes_mb = [size for _, size in config]
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(
        ssl=ssl_context,
        limit=max_connections,
        limit_per_host=max_connections
    )

    async with aiohttp.ClientSession(connector=connector) as session:
        workers = [
            connection_worker(
                session, obj_sizes_mb, config, server_ip, 
                https_percent, avg_object_size_mb, stats_pipe
            ) for _ in range(max_connections)
        ]
        
        try:
            await asyncio.gather(*[asyncio.create_task(w) for w in workers])
        except asyncio.CancelledError:
            pass

def aggregate_statistics(parent_pipes, duration):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    start_time = time.perf_counter()
    last_time = start_time
    interval_bytes = 0
    interval_completed = 0

    while True:
        current_time = time.perf_counter()
        if current_time - start_time > duration:
            break

        # Read all available data from pipes
        for pipe in parent_pipes:
            while pipe.poll():
                try:
                    bytes_transferred, completed = pipe.recv()
                    interval_bytes += bytes_transferred
                    interval_completed += completed
                except EOFError:
                    continue

        # Report every second
        if current_time - last_time >= 1.0:
            elapsed = current_time - last_time
            
            throughput_gbps = (interval_bytes * 8) / (elapsed * 1e9)
            cps = interval_completed / elapsed
            
            print(f"Time: {current_time - start_time:.2f}s, "
                  f"CPS: {cps:.2f}, "
                  f"Throughput: {throughput_gbps:.2f} Gbps")
            
            # Reset interval counters
            interval_bytes = 0
            interval_completed = 0
            last_time = current_time
        
        time.sleep(0.01)

def run_client_process(server_ip, max_connections, https_percent, avg_object_size_mb, config, child_pipe, duration):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(
            run_client_instance(
                server_ip, max_connections, https_percent,
                avg_object_size_mb, config, child_pipe, duration
            )
        )
    finally:
        loop.close()

def run_client(server_ip, max_connections, https_percent, avg_object_size_mb, duration, config_path):
    config = []
    with open(config_path) as f:
        for line in f:
            path, size_str = line.strip().split(', ')
            size_mb = float(size_str.replace('MB', ''))
            config.append((path, size_mb))

    process_count = os.cpu_count() or 1
    connections_per_process = max(1, max_connections // process_count)
    
    processes = []
    parent_pipes = []

    for _ in range(process_count):
        parent_pipe, child_pipe = multiprocessing.Pipe()
        parent_pipes.append(parent_pipe)
        p = multiprocessing.Process(
            target=run_client_process,
            args=(server_ip, connections_per_process, https_percent, 
                  avg_object_size_mb, config, child_pipe, duration)
        )
        processes.append(p)
        p.start()

    try:
        aggregate_statistics(parent_pipes, duration)
    finally:
        for p in processes:
            p.terminate()
        for pipe in parent_pipes:
            pipe.close()

if __name__ == "__main__":
    server_ip = os.getenv('SERVER_IP', '127.0.0.1')
    max_connections = int(os.getenv('MAX_CONNECTIONS', '300'))
    https_percent = float(os.getenv('HTTPS_PERCENT', '50'))
    avg_object_size_mb = float(os.getenv('AVG_OBJECT_SIZE_MB', '2'))
    duration = int(os.getenv('DURATION', '60'))
    config_path = os.getenv('CONFIG_PATH', 'config.txt')

    run_client(
        server_ip=server_ip,
        max_connections=max_connections,
        https_percent=https_percent,
        avg_object_size_mb=avg_object_size_mb,
        duration=duration,
        config_path=config_path
    )