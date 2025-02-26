import os
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
import ssl
import threading

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def run_http_server(port):
    os.chdir('/home/terratrax/Code/SkyhighSecurity/SwgTestSuite/server_content')  # Change directory to content directory
    httpd = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    logging.info(f"Starting HTTP server on port {port}")
    httpd.serve_forever()

def run_https_server(port):
    os.chdir('/home/terratrax/Code/SkyhighSecurity/SwgTestSuite/server_content')  # Change directory to content directory
    httpd = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    # Create an SSL context and wrap the server socket
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='/home/terratrax/Code/SkyhighSecurity/SwgTestSuite/cert.pem',
                            keyfile='/home/terratrax/Code/SkyhighSecurity/SwgTestSuite/key.pem')
    
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    logging.info(f"Starting HTTPS server on port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    http_thread = threading.Thread(target=run_http_server, args=(8080,))
    https_thread = threading.Thread(target=run_https_server, args=(8443,))

    http_thread.start()
    https_thread.start()

    http_thread.join()
    https_thread.join()