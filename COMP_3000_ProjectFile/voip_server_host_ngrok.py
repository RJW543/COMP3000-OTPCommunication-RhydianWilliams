import socket
import threading
import socketserver

# Listen on all interfaces, port 50000 (or any free port).
HOST = '0.0.0.0'
PORT = 50000

# Keep track of connected clients: user_id -> client_socket
clients = {}

# Keep track of "call targets": call_targets[user_id] = recipient_id
call_targets = {}

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        """
        1. Receive user ID from client.
        2. Store the client in global dictionary.
        3. Handle commands from the client (CALL, AUDIO, etc.).
        4. Forward AUDIO packets to the call target if set.
        """
        client_socket = self.request
        user_id = None
        try:
            # First message from the client is their user ID
            data = client_socket.recv(1024)
            if not data:
                client_socket.close()
                return

            user_id = data.decode('utf-8').strip()
            # Validate unique user_id
            if not user_id or user_id in clients:
                client_socket.sendall(b"ERROR|Invalid or taken userID.")
                client_socket.close()
                return

            # Register client
            clients[user_id] = client_socket
            call_targets[user_id] = None
            client_socket.sendall(b"OK|Connected.")
            print(f"[+] User '{user_id}' connected from {self.client_address}")

            # Main loop: receive packets
            while True:
                packet = client_socket.recv(4096)
                if not packet:
                    break

                # Attempt to parse "COMMAND|PAYLOAD"
                try:
                    header, payload = packet.split(b'|', 1)
                    command = header.decode('utf-8')
                except ValueError:
                    # Malformed data
                    continue

                if command == "CALL":
                    # e.g. "CALL|Bob"
                    recipient_id = payload.decode('utf-8')
                    if recipient_id in clients:
                        call_targets[user_id] = recipient_id
                        client_socket.sendall(f"INFO|You are now calling {recipient_id}".encode("utf-8"))
                        print(f"[{user_id}] is calling [{recipient_id}]")
                    else:
                        client_socket.sendall(f"ERROR|Recipient {recipient_id} not found".encode("utf-8"))

                elif command == "AUDIO":
                    # Audio data from user_id -> forward to call target
                    target_id = call_targets.get(user_id)
                    if target_id and target_id in clients:
                        target_socket = clients[target_id]
                        try:
                            forward_packet = b"AUDIO|" + payload
                            target_socket.sendall(forward_packet)
                        except Exception as e:
                            print(f"[-] Error forwarding audio from {user_id} to {target_id}: {e}")
                else:
                    print(f"Unknown command from {user_id}: {command}")

        except Exception as e:
            print(f"[-] Error with client {self.client_address}: {e}")
        finally:
            # Clean up
            if user_id and user_id in clients:
                del clients[user_id]
                del call_targets[user_id]
                print(f"[-] User '{user_id}' disconnected.")
            client_socket.close()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        ip, port = server.server_address
        print(f"Server running locally on {ip}:{port}.")
        print("Use 'ngrok tcp 50000' to tunnel this port if needed.")

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print("Press Ctrl+C to stop the server...")

        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("\nShutting down the server...")
            server.shutdown()
            server.server_close()
