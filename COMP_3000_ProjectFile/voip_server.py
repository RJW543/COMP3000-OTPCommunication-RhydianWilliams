import socket
import threading
import socketserver

HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 50000

# Dictionary to store user_id -> client_socket
clients = {}

# Dictionary to store an "active call target" for each user
# e.g., call_targets["Alice"] = "Bob" means Alice is streaming audio to Bob.
call_targets = {}

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        """
        1. Receive user ID.
        2. Store the client in the global clients dictionary.
        3. Receive messages from the client:
           - 'CALL|<recipient_id>' sets up call target.
           - 'AUDIO|<bytes>' indicates audio data is being sent.
        4. Forward audio data to the call target (if any).
        """
        client_socket = self.request
        user_id = None
        try:
            # Receive the user ID
            data = client_socket.recv(1024).decode('utf-8').strip()
            user_id = data
            if not user_id or user_id in clients:
                client_socket.sendall("ERROR|Invalid or taken userID.".encode("utf-8"))
                client_socket.close()
                return

            # Register client
            clients[user_id] = client_socket
            call_targets[user_id] = None  # No call by default
            client_socket.sendall("OK|Connected.".encode("utf-8"))
            print(f"[+] User '{user_id}' connected from {self.client_address}")

            while True:
                packet = client_socket.recv(4096)
                if not packet:
                    break

                # Separate the packet into a command and data:
                # e.g. "CALL|Bob" or "AUDIO|<raw_bytes>"
                try:
                    header, payload = packet.split(b'|', 1)
                    command = header.decode('utf-8')
                except ValueError:
                    continue  # ignore malformed packets

                if command == "CALL":
                    recipient_id = payload.decode('utf-8')
                    print(f"[{user_id}] wants to call [{recipient_id}]")
                    if recipient_id in clients:
                        call_targets[user_id] = recipient_id
                        client_socket.sendall(f"INFO|You are now calling {recipient_id}".encode("utf-8"))
                    else:
                        client_socket.sendall(f"ERROR|Recipient {recipient_id} not found".encode("utf-8"))

                elif command == "AUDIO":
                    # This is raw audio data from user_id
                    # Forward to the call target
                    target_id = call_targets.get(user_id)
                    if target_id and target_id in clients:
                        target_socket = clients[target_id]
                        # Forward: "AUDIO|<raw_bytes>"
                        try:
                            forward_packet = b"AUDIO|" + payload
                            target_socket.sendall(forward_packet)
                        except Exception as e:
                            print(f"Error forwarding audio to {target_id}: {e}")
                    # If there's no target or target is invalid drop the audio
                else:
                    print(f"Unknown command from {user_id}: {command}")

        except Exception as e:
            print(f"[-] Error with client {self.client_address}: {e}")
        finally:
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
        print(f"Server running on {ip}:{port} (TCP).")
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print("Press Ctrl+C to stop the server.")
        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("\nShutting down the server...")
            server.shutdown()
            server.server_close()
