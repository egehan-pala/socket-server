import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import os

class ServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Server GUI")
        self.server_socket = None
        self.client_threads = []
        self.clients = {}  # {username: connection}
        self.files = {}  # {filename: owner}
        self.storage_dir = None

        # GUI Setup
        self.port_label = tk.Label(root, text="Port:")
        self.port_label.pack()
        self.port_entry = tk.Entry(root)
        self.port_entry.pack()

        self.storage_label = tk.Label(root, text="Storage Directory:")
        self.storage_label.pack()
        self.storage_button = tk.Button(root, text="Select Folder", command=self.select_storage_dir)
        self.storage_button.pack()

        self.log_label = tk.Label(root, text="Activity Log:")
        self.log_label.pack()
        self.log_listbox = tk.Listbox(root, width=50, height=20)
        self.log_listbox.pack()

        self.start_button = tk.Button(root, text="Start Server", command=self.start_server)
        self.start_button.pack()

    def select_storage_dir(self):
        self.storage_dir = filedialog.askdirectory()
        self.log_message(f"Storage directory set to: {self.storage_dir}")

    def start_server(self):
        port = self.port_entry.get()
        if not port.isdigit():
            messagebox.showerror("Error", "Invalid port number!")
            return
        if not self.storage_dir:
            messagebox.showerror("Error", "Select a storage directory first!")
            return
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', int(port)))
        self.server_socket.listen(5)
        self.log_message(f"Server started on port {port}")
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def accept_clients(self):
        while True:
            conn, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

    def handle_client(self, conn, addr):
        try:
            conn.send(b"Enter username: ")
            username = conn.recv(1024).decode('utf-8').strip()
            if username in self.clients:
                conn.send(b"Username already taken. Disconnecting.\n")
                conn.close()
                return

            self.clients[username] = conn
            self.log_message(f"{username} connected from {addr}")
            conn.send(b"Connected to the server.\n")

            while True:
                data = conn.recv(1024).decode('utf-8').strip()
                if not data:
                    break
                if data == 'list':
                    self.send_file_list(conn)
                elif data.startswith('upload'):
                    self.receive_file(data.split(' ', 1)[1], conn, username)
                elif data.startswith('delete'):
                    self.delete_file(data.split(' ', 1)[1], conn, username)
                elif data.startswith('download'):
                    self.send_file(data.split(' ', 2)[1:], conn)
                else:
                    conn.send(b"Invalid command.\n")
        except ConnectionResetError:
            self.log_message(f"{username} disconnected.")
        finally:
            if username in self.clients:
                del self.clients[username]
            conn.close()

    def log_message(self, message):
        self.log_listbox.insert(tk.END, message)
        self.log_listbox.yview(tk.END)

    def send_file_list(self, conn):
        file_list = "\n".join([f"{file} (Owner: {owner})" for file, owner in self.files.items()])
        conn.send(f"Files on server:\n{file_list}\n".encode('utf-8'))

    def receive_file(self, filename, conn, username):
        conn.send(b"Send file size: ")
        file_size = int(conn.recv(1024).decode('utf-8'))
        conn.send(b"Ready to receive file\n")

        file_path = os.path.join(self.storage_dir, f"{username}_{filename}")
        with open(file_path, "wb") as f:
            bytes_received = 0
            while bytes_received < file_size:
                chunk = conn.recv(1024)
                f.write(chunk)
                bytes_received += len(chunk)

        self.files[f"{username}_{filename}"] = username
        conn.send(b"File uploaded successfully.\n")
        self.log_message(f"File {filename} uploaded by {username}")

    def delete_file(self, filename, conn, username):
        file_key = f"{username}_{filename}"
        if file_key in self.files and self.files[file_key] == username:
            os.remove(os.path.join(self.storage_dir, file_key))
            del self.files[file_key]
            conn.send(b"File deleted successfully.\n")
            self.log_message(f"File {filename} deleted by {username}")
        else:
            conn.send(b"File not found or insufficient permissions.\n")

    def send_file(self, details, conn):
        if len(details) < 2:
            conn.send(b"Invalid download command.\n")
            return

        filename, owner = details
        file_key = f"{owner}_{filename}"
        if file_key not in self.files:
            conn.send(b"File not found.\n")
            return

        file_path = os.path.join(self.storage_dir, file_key)
        file_size = os.path.getsize(file_path)
        conn.send(f"{file_size}".encode('utf-8'))
        with open(file_path, "rb") as f:
            conn.sendall(f.read())
        self.log_message(f"File {filename} sent to a client")

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerApp(root)
    root.mainloop()
