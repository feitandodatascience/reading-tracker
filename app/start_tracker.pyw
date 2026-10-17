"""Double-click launcher for the private reading tracker (Windows).

Opens the tracker at http://localhost:8519, starting it in the background first
if needed. See launcher.py for how it works.
"""

from launcher import launch

PORT = 8519  # its own port, never mixed up with the dashboard or Streamlit's 8501

if __name__ == "__main__":
    launch("app/tracker.py", PORT, "tracker")
