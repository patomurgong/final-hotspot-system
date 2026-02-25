# Updated Django Server Monitor Script
import os
import time
import subprocess
import requests
from datetime import datetime
import sys
import io
import socket
import psutil
# Using win32api for more stable notifications
from win32api import MessageBox
from win32con import MB_ICONINFORMATION
import threading

# Force UTF-8 output for correct character display such as emojis and special characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- Configuration ---
LOG_FILE = "server_monitor.log"
CMD = ["python", "manage.py", "runserver", "0.0.0.0:8001"]
MAX_LOG_LINES = 200
CHECK_INTERVAL = 15  # Increased seconds to give the server more time to start
PORT = 8001

# --- Helper Functions ---
def show_notification(title, message):
    """Show a desktop notification using pywin32 in a separate thread."""
    def notify():
        # Corrected the function call to use MessageBox instead of MessageBoxW
        MessageBox(None, message, title, MB_ICONINFORMATION)
    
    # Use a separate thread to prevent blocking the main loop
    notification_thread = threading.Thread(target=notify)
    notification_thread.start()

def trim_log():
    """Keep only the last MAX_LOG_LINES lines in the log file."""
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_LOG_LINES:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[-MAX_LOG_LINES:])

def log(message, notify=False):
    """Log to file and optionally show Windows desktop notification."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{full_message}\n")
    print(full_message)
    trim_log()
    if notify:
        show_notification("Django Monitor", message)

def is_port_in_use(port):
    """Check if a TCP port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # connect_ex returns 0 if the connection is successful (port is in use)
        return s.connect_ex(("127.0.0.1", port)) == 0

def kill_process_on_port(port):
    """
    Find and kill the process using a given port more gracefully.
    
    This function now uses psutil.net_connections() as recommended and handles
    the process termination logic correctly.
    """
    found_and_terminated = False
    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
            try:
                # Use psutil.Process() to get process details from the PID
                proc = psutil.Process(conn.pid)
                log(f"⚠️ Port {port} is in use by {proc.name()} (PID {proc.pid}). Attempting graceful termination...", notify=True)
                try:
                    # Try a graceful shutdown first
                    proc.terminate()
                    # Wait a moment to give the process time to terminate
                    time.sleep(2)
                    # If it's still running, force kill
                    if proc.is_running():
                        log(f"❌ Graceful termination failed. Forcing kill on {proc.name()} (PID {proc.pid}).", notify=True)
                        proc.kill()
                        time.sleep(1) # wait for OS to release port
                    found_and_terminated = True
                    break # Exit loop once the process is terminated
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    log(f"⚠️ Could not terminate/kill process with PID {conn.pid}. Reason: {e}", notify=True)
                except Exception as e:
                    log(f"An unexpected error occurred: {e}", notify=True)
            except psutil.NoSuchProcess:
                # The process might have terminated just before we tried to access it
                continue
    return found_and_terminated

def server_alive_with_retries(port, retries=5, delay=3):
    """Check if Django server responds with retries."""
    for i in range(retries):
        try:
            r = requests.get(f"http://127.0.0.1:{port}", timeout=2)
            if r.status_code in (200, 302):
                return True
        except requests.exceptions.RequestException:
            log(f"Attempt {i+1} of {retries}: Server not responsive. Retrying in {delay}s...", notify=False)
            time.sleep(delay)
    return False

def start_server():
    """Start the Django server process and log its output."""
    log("🔴 Server is down or unresponsive. Restarting...", notify=True)
    try:
        # Start the process without waiting for it to finish
        process = subprocess.Popen(CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Check if the server is now responsive with retries
        if server_alive_with_retries(PORT):
            log("🟢 Server restarted successfully.", notify=True)
            return process
        else:
            log("❌ Server started, but is not responding. Capturing error output...", notify=True)
            stdout_output, stderr_output = process.communicate(timeout=1)
            log("--- BEGIN SERVER STDOUT ---")
            print(stdout_output.strip())
            log("--- END SERVER STDOUT ---")
            log("--- BEGIN SERVER STDERR ---")
            print(stderr_output.strip())
            log("--- END SERVER STDERR ---")
            return None
    except Exception as e:
        log(f"❌ Error starting server: {e}", notify=True)
        return None

# --- Main loop ---
current_process = None
while True:
    if current_process is not None and current_process.poll() is not None:
        # The process has terminated unexpectedly
        log("🔴 Django process terminated unexpectedly. Will restart.", notify=True)
        current_process = None

    if current_process is None or not is_port_in_use(PORT):
        # A simple port check is sufficient here
        current_process = start_server()
    elif not server_alive_with_retries(PORT):
        # Only restart if the server is unresponsive despite the port being in use
        log("🔴 Server is unresponsive despite being on an open port. Will restart.", notify=True)
        kill_process_on_port(PORT)
        current_process = start_server()
    else:
        log("🟢 Server is alive.")

    # Main wait time
    time.sleep(CHECK_INTERVAL)
