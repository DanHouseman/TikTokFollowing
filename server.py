import http.server
import socketserver
import webbrowser
import os

PORT = 8080

# Serve files from the directory containing this script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    # Open following.html in the default browser
    webbrowser.open_new_tab(f"http://localhost:{PORT}/following.html")
    httpd.serve_forever()