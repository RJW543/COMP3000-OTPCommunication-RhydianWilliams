import socket

def main():
    # You can set the server listening port manually (e.g., via localxpose)
    server_port = int(input("Enter the server listening port (e.g. 6000): ") or "6000")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", server_port))
    print("UDP forwarding server listening on port", server_port)

    clients = []  # This will store addresses of connected clients

    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = data.decode("utf-8")
            # Record new client addresses (up to 2 clients)
            if addr not in clients:
                if len(clients) < 2:
                    clients.append(addr)
                    print("New client connected:", addr)
                else:
                    print("Additional client attempted to connect, ignoring:", addr)
                    continue

            print(f"Received from {addr}: {message}")
            # Only forward if we have two clients connected.
            if len(clients) < 2:
                print("Waiting for a second client; message not forwarded.")
            else:
                # Forward the message to the other client
                for client in clients:
                    if client != addr:
                        # Here you might modify the message or add identifiers as needed.
                        forward_message = f"{message}"
                        sock.sendto(forward_message.encode("utf-8"), client)
                        print(f"Forwarded message from {addr} to {client}")
        except KeyboardInterrupt:
            print("Server shutting down.")
            break

if __name__ == '__main__':
    main()
