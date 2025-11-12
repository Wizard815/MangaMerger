#!/usr/bin/env python3
"""
kill_server.py
Stops any running instance of the MangaMerger Flask webserver.
"""

import os
import signal
import psutil

def kill_manga_merger():
    killed = 0
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
            if "python" in proc.info['name'].lower() and "app.py" in cmd:
                print(f"🛑 Killing MangaMerger PID {proc.pid}")
                os.kill(proc.pid, signal.SIGTERM)
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if killed == 0:
        print("✅ No running MangaMerger webserver found.")
    else:
        print(f"✅ Stopped {killed} running instance(s).")

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("⚠️ psutil not installed. Installing now...")
        os.system("pip install psutil")
        import psutil

    kill_manga_merger()
