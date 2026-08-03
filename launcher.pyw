import os
import subprocess
import time
import webbrowser
import sys

def main():
    # Get the directory of the current script or executable
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    # Define paths relative to the executable
    venv_python = os.path.join(base_dir, "venv", "Scripts", "python.exe")
    app_script = os.path.join(base_dir, "app.py")
    
    # Launch Streamlit invisibly in the background
    # 0x08000000 is the Windows flag for CREATE_NO_WINDOW
    subprocess.Popen(
        [venv_python, "-m", "streamlit", "run", app_script, "--server.headless=true"],
        creationflags=0x08000000 
    )
    
    # Wait 3 seconds for the local server to boot, then open browser
    time.sleep(3)
    webbrowser.open("http://localhost:8501")

if __name__ == "__main__":
    main()