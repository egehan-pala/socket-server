import socket
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os
import threading
import time

class Client:
    def __init__(self, root):
        self.root = root
        self.root.title("Client GUI")
        self.client_socket = None
        self.username = None
        self.socket_lock = threading.RLock()  # Using RLock for reentrancy
        self.receive_thread_running = False  # Flag to control receive thread

        # GUI Components
        tk.Label(root, text="Server IP:").pack()
        self.server_ip_entry = tk.Entry(root)
        self.server_ip_entry.pack()

        tk.Label(root, text="Server Port:").pack()
        self.port_entry = tk.Entry(root)
        self.port_entry.pack()

        tk.Label(root, text="Username:").pack()
        self.username_entry = tk.Entry(root)
        self.username_entry.pack()

        self.connect_button = tk.Button(root, text="Connect", command=self.connect_to_server)
        self.connect_button.pack()

        tk.Label(root, text="Activity Log:").pack()
        self.log_listbox = tk.Listbox(root, width=50, height=20)
        self.log_listbox.pack()

        self.upload_button = tk.Button(root, text="Upload File", command=self.upload_file, state=tk.DISABLED)
        self.upload_button.pack()

        self.delete_button = tk.Button(root, text="Delete File", command=self.delete_file, state=tk.DISABLED)
        self.delete_button.pack()

        self.download_button = tk.Button(root, text="Download File", command=self.download_file, state=tk.DISABLED)
        self.download_button.pack()

        self.list_files_button = tk.Button(root, text="List Files", command=self.list_files, state=tk.DISABLED)
        self.list_files_button.pack()

        self.disconnect_button = tk.Button(root, text="Disconnect", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_button.pack()

    def log_message(self, message):
        # Ensure GUI updates are thread-safe
        self.root.after(0, self._log_message_safe, message)

    def _log_message_safe(self, message):
        self.log_listbox.insert(tk.END, message)
        self.log_listbox.yview(tk.END)

    def connect_to_server(self):
        server_ip = self.server_ip_entry.get()
        port = self.port_entry.get()
        username = self.username_entry.get()

        if not server_ip or not port.isdigit() or not username:
            self.log_message("Error: Enter valid server IP, port, and username!")
            return
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect((server_ip, int(port)))
            response = self.client_socket.recv(1024).decode()
            self.log_message(response)

            self.client_socket.send(username.encode())
            response = self.client_socket.recv(1024).decode()

            if "Error" in response:
                self.log_message(response)
                self.client_socket.close()
                return
            else:
                self.log_message(response)

            self.username = username
            self.log_message("Connected to the server.")
            self.enable_controls()
            self.start_receive_thread()  # Start the receive_message thread

        except Exception as e:
            self.log_message(f"Error: Failed to connect to the server. {e}")

    def enable_controls(self):
        self.upload_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL)
        self.download_button.config(state=tk.NORMAL)
        self.list_files_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.NORMAL)

    def disable_controls(self):
        self.upload_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.download_button.config(state=tk.DISABLED)
        self.list_files_button.config(state=tk.DISABLED)
        self.disconnect_button.config(state=tk.DISABLED)

    def upload_file(self):
        filepath = filedialog.askopenfilename()
        if not filepath:
            self.log_message("No file selected.")
            return

        # Start a new thread for the upload operation
        threading.Thread(target=self._upload_file_thread, args=(filepath,), daemon=True).start()

    def _upload_file_thread(self, filepath):
        try:
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)

            with self.socket_lock:
                if self.client_socket is None:
                    self.log_message("Not connected to the server.")
                    return
                command = f'upload "{filename}"'
                self.client_socket.send(command.encode())
                response = self.client_socket.recv(1024).decode()

                if not response.startswith("Send file size"):
                    self.log_message(f"Unexpected response from server: {response}")
                    return

                self.client_socket.send(str(file_size).encode())

                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        self.client_socket.sendall(chunk)

                response = self.client_socket.recv(1024).decode()
                self.log_message(response)

            self.log_message(f"File {filename} uploaded successfully.")

        except Exception as e:
            self.log_message(f"Error: Failed to upload file. {e}")

    def delete_file(self):
        filename = simpledialog.askstring("Delete File", "Enter the filename to delete:")
        if not filename:
            self.log_message("No filename entered.")
            return

        try:
            with self.socket_lock:
                if self.client_socket is None:
                    self.log_message("Not connected to the server.")
                    return
                command = f'delete "{filename}"'
                self.client_socket.send(command.encode())
                response = self.client_socket.recv(1024).decode()
                self.log_message(response)

        except Exception as e:
            self.log_message(f"Error: Failed to delete file. {e}")

    def download_file(self):
        filename = simpledialog.askstring("Download File", "Enter the filename to download:")
        owner = simpledialog.askstring("File Owner", "Enter the owner of the file:")
        save_dir = filedialog.askdirectory()

        if not filename or not owner or not save_dir:
            self.log_message("Error: Missing information for download.")
            return

        # Start a new thread for the download operation
        threading.Thread(target=self._download_file_thread, args=(filename, owner, save_dir), daemon=True).start()

    def _download_file_thread(self, filename, owner, save_dir):
        try:
            with self.socket_lock:
                if self.client_socket is None:
                    self.log_message("Not connected to the server.")
                    return
                command = f'download "{filename}" "{owner}"'
                self.client_socket.send(command.encode())
                response = self.client_socket.recv(1024).decode()

                if not response.isdigit():
                    self.log_message(response)
                    return

                file_size = int(response)
                self.client_socket.send(b"Ready")

                save_path = os.path.join(save_dir, filename)
                with open(save_path, "wb") as f:
                    received = 0
                    while received < file_size:
                        remaining = file_size - received
                        data = self.client_socket.recv(min(4096, remaining))
                        if not data:
                            break
                        f.write(data)
                        received += len(data)

                # Now, after receiving the file data, read any additional messages
                if self.client_socket is None:
                    self.log_message("Not connected to the server.")
                    return
                # Read the confirmation message from the server
                response = self.client_socket.recv(1024).decode()
                self.log_message(response)

            self.log_message(f"File {filename} downloaded successfully to {save_dir}.")

        except Exception as e:
            self.log_message(f"Error: Failed to download file. {e}")

    def list_files(self):
        try:
            with self.socket_lock:
                if self.client_socket is None:
                    self.log_message("Not connected to the server.")
                    return
                self.client_socket.send(b"list")
                data = b""
                while True:
                    chunk = self.client_socket.recv(1024)
                    data += chunk
                    if len(chunk) < 1024:
                        break

                response = data.decode()
                self.log_message("Files on the server:")
                self.log_message(response)

        except Exception as e:
            self.log_message(f"Error: Failed to list files. {e}")

    def disconnect(self):
        try:
            with self.socket_lock:
                if self.client_socket:
                    self.client_socket.close()
                self.client_socket = None
                self.receive_thread_running = False  # Stop the receive thread
            self.disable_controls()
            self.log_message("Disconnected from the server.")
        except Exception as e:
            self.log_message(f"Error: Failed to disconnect. {e}")

    def start_receive_thread(self):
        # Create a separate thread to handle receiving messages from the server.
        self.receive_thread_running = True
        receive_thread = threading.Thread(target=self.receive_message, daemon=True)
        receive_thread.start()

    def receive_message(self):
        try:
            while self.receive_thread_running:
                acquired = self.socket_lock.acquire(timeout=0.1)
                if acquired:
                    try:
                        if self.client_socket is None:
                            break  # Socket is closed, exit the loop
                        self.client_socket.settimeout(0.1)
                        try:
                            message = self.client_socket.recv(1024).decode()
                            if message:
                                if message.startswith("NOTIFICATION:"):
                                    self.log_message(f"Server: {message}")
                                elif message.startswith("DISCONNECT"):
                                    self.log_message("Disconnected by server.")
                                    self.disconnect()
                                    break
                                else:
                                    # Handle other messages
                                    self.log_message(f"Server: {message}")
                            else:
                                # Connection closed by server
                                self.log_message("Connection closed by server.")
                                self.disconnect()
                                break
                        except socket.timeout:
                            continue  # No message available, continue checking
                        except Exception as e:
                            self.log_message(f"Error while receiving message: {e}")
                            self.disconnect()
                            break
                        finally:
                            if self.client_socket:
                                self.client_socket.settimeout(None)
                    finally:
                        self.socket_lock.release()
                else:
                    # Could not acquire lock, socket is being used by another thread
                    # Wait a bit and try again
                    time.sleep(0.1)
        except Exception as e:
            self.log_message(f"Connection error: {e}")
            if self.client_socket:
                self.client_socket.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = Client(root)
    root.mainloop()
