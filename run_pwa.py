"""HADJ AIR TOUCH PWA Local Server Runner.

Launches a local HTTP web server to serve the Progressive Web App (PWA)
and automatically opens it in your default web browser.
"""
import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8080
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pwa")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        # Clean logging output
        sys.stdout.write(f"[PWA Server] {self.address_string()} - {args[0]}\n")
        sys.stdout.flush()

def main():
    global PORT
    if not os.path.exists(DIRECTORY):
        print(f"Error: Directory '{DIRECTORY}' not found.")
        sys.exit(1)

    print("==================================================")
    print("   HADJ AIR TOUCH - Progressive Web App (PWA)")
    print("==================================================")
    print(f"Server root: {DIRECTORY}")
    print(f"Local URL:   http://localhost:{PORT}")
    print(f"Network URL: http://192.168.1.5:{PORT} (Accessible depuis les autres PC/Mobiles sur le même Wi-Fi)")
    print("--------------------------------------------------")
    print("App is 100% offline capable after initial load!")
    print("Press Ctrl+C to stop the server.\n")

    # Automatically open browser
    webbrowser.open(f"http://localhost:{PORT}")

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    try:
        with ReusableTCPServer(("0.0.0.0", PORT), Handler) as httpd:
            httpd.serve_forever()
    except OSError:
        PORT = 8085
        print(f"Port 8080 busy, switching to http://localhost:{PORT} / http://192.168.1.5:{PORT}")
        with ReusableTCPServer(("0.0.0.0", PORT), Handler) as httpd:
            httpd.serve_forever()

if __name__ == "__main__":
    main()
