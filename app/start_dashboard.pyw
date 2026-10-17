"""Double-click launcher for a local preview of the public dashboard (Windows).

Opens the dashboard at http://localhost:8520, starting it in the background
first if needed. See launcher.py for how it works.
"""

from launcher import launch

PORT = 8520  # its own port, never mixed up with the tracker or Streamlit's 8501

if __name__ == "__main__":
    launch("app/dashboard.py", PORT, "dashboard")
