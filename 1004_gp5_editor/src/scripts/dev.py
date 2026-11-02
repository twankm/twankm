"""Run both development servers with standard-library-only process management."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == 'nt'


def commands():
    python = ROOT / 'backend' / '.venv' / ('Scripts/python.exe' if WINDOWS else 'bin/python')
    if not python.is_file():
        raise RuntimeError('Backend .venv missing. Follow the setup instructions in README.md.')
    check = subprocess.run([str(python), '-c', 'import uvicorn, fastapi, guitarpro, multipart'],
                           cwd=ROOT / 'backend', capture_output=True, text=True, errors='replace')
    if check.returncode:
        raise RuntimeError('Backend environment is broken. Rebuild it after moving the project.\n' + check.stderr)
    node = shutil.which('node')
    vite = ROOT / 'frontend/node_modules/vite/bin/vite.js'
    if not node or not vite.is_file():
        raise RuntimeError('Frontend dependencies missing. Install Node.js, then run npm ci in frontend.')
    return [
        ('backend', [str(python), '-u', '-m', 'uvicorn', 'app.main:app', '--reload',
                     '--reload-dir', str(ROOT / 'backend/app'), '--host', '127.0.0.1', '--port', '8000']),
        ('frontend', [node, str(vite), '--host', '127.0.0.1', '--port', '5173', '--strictPort']),
    ]


def check_ports():
    for port in (8000, 5173):
        with socket.socket() as probe:
            if WINDOWS:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            try:
                probe.bind(('127.0.0.1', port))
            except OSError as error:
                raise RuntimeError(f'Port {port} is already in use. Stop the existing server before starting again.') from error


def copy_output(label, process):
    assert process.stdout is not None
    for line in process.stdout:
        print(f'[{label}] {line}', end='', flush=True)


def wait_for_servers(processes):
    # Ignore proxy environment settings for these local health checks.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    urls = {'http://127.0.0.1:8000/api/health', 'http://127.0.0.1:5173/'}
    deadline = time.monotonic() + 45
    while urls and time.monotonic() < deadline:
        for label, process in processes:
            if process.poll() is not None:
                raise RuntimeError(f'{label} exited during startup (code {process.returncode}).')
        for url in list(urls):
            try:
                with opener.open(url, timeout=0.5) as response:
                    if response.status == 200:
                        urls.remove(url)
            except (OSError, urllib.error.URLError):
                pass
        if urls:
            time.sleep(0.2)
    if urls:
        raise RuntimeError('Servers did not become ready within 45 seconds. Check their logs above.')


def stop_servers(processes):
    for _, process in processes:
        if process.poll() is not None:
            continue
        try:
            if WINDOWS:
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
    for label, process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if WINDOWS:
                # Only the process tree created by this launcher is stopped.
                result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                if result.returncode and process.poll() is None:
                    print(f'Could not stop {label}. Close its process manually.', flush=True)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f'{label} did not stop.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='check dependencies and ports without starting servers')
    parser.add_argument('--smoke-test', action='store_true', help='start both servers, check HTTP responses, then stop them')
    args = parser.parse_args()
    processes = []
    readers = []
    try:
        services = commands()
        check_ports()
        if args.check:
            print('Backend dependencies, frontend files, Node.js, and ports 8000/5173: OK')
            return 0
        print('Starting GP5 Editor. Press Ctrl+C here to stop both servers.', flush=True)
        for label, command in services:
            options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {'start_new_session': True}
            process = subprocess.Popen(command, cwd=ROOT / label, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                       env={**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'}, **options)
            processes.append((label, process))
            reader = threading.Thread(target=copy_output, args=(label, process), daemon=True)
            readers.append(reader)
            reader.start()
        wait_for_servers(processes)
        if args.smoke_test:
            print('Both HTTP checks passed. Stopping test servers.', flush=True)
            return 0
        print('\nReady: http://127.0.0.1:5173/\nKeep this window open while using the editor.\n', flush=True)
        while True:
            for label, process in processes:
                if process.poll() is not None:
                    raise RuntimeError(f'{label} stopped (code {process.returncode}). Stopping the other server.')
            time.sleep(0.3)
    except KeyboardInterrupt:
        print('\nStopping GP5 Editor...', flush=True)
        return 0
    except (OSError, RuntimeError) as error:
        print(f'ERROR: {error}', file=sys.stderr, flush=True)
        return 1
    finally:
        # A second Ctrl+C should not interrupt process cleanup.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        stop_servers(processes)
        for reader in readers:
            reader.join(timeout=1)


if __name__ == '__main__':
    sys.exit(main())
