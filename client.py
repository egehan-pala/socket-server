import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import os

class ClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Client GUI")
        self.client_socket = None
        self.username = None

        # GUI Setup
        self.server_label = tk.Label(root, text="Server IP:")
        self.server_label.pack()
        self.server_entry = tk.Entry(root)
        self.server_entry.pack()

        self.port_label = tk.Label(root, text="Port:")
        self.port_label.pack()
        self.port_entry = tk.Entry(root)
        self.port_entry.pack()

        self.username_label = tk.Label(root, text="Username:")
        self.username_label.pack()
        self.username_entry = tk.Entry(root)
        self.username_entry.pack()

        self.connect_button = tk.Button(root, text="Connect", command=self.connect_to_server)
        self.connect_button.pack()

        self.log_label = tk.Label(root, text="Activity Log:")
        self.log_label.pack()
        self.log_listbox = tk.Listbox(root, width=50, height=20)
        self.log_listbox.pack()

        self.file_upload_button = tk.Button(root, text="Upload File", command=self.upload_file, state=tk.DISABLED)
        self.file_upload_button.pack()

        self.file_download_button = tk.Button(root, text="Download File", command=self.download_file, state=tk.DISABLED)
        self.file_download_button.pack()

        self.list_files_button = tk.Button(root, text="List Files", command=self.list_files, state=tk.DISABLED)
        self.list_files_button.pack()

        self.disconnect_button = tk.Button(root, text="Disconnect", command=self.disconnect_from_server, state=tk.DISABLED)
        self.disconnect_button.pack()

    def connect_to_server(self):
        server_ip = self.server_entry.get()
        port = self.port_entry.get()
        username = self.username_entry.get()

        if not server_ip or not port.isdigit() or not username:
            messagebox.showerror("Error", "Please enter valid server IP, port, and username!")
            return

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((server_ip, int(port)))
            self.client_socket.send(username.encode('utf-8'))
            response = self.client_socket.recv(1024).decode('utf-8')

            if "Username already taken" in response:
                messagebox.showerror("Error", response)
                self.client_socket.close()
                return

            self.username = username
            self.log_message("Connected to the server.")
            self.enable_controls()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to the server: {e}")

    def enable_controls(self):
        self.file_upload_button.config(state=tk.NORMAL)
        self.file_download_button.config(state=tk.NORMAL)
        self.list_files_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.NORMAL)

    def disable_controls(self):
        self.file_upload_button.config(state=tk.DISABLED)
        self.file_download_button.config(state=tk.DISABLED)
        self.list_files_button.config(state=tk.DISABLED)
        self.disconnect_button.config(state=tk.DISABLED)

    def log_message(self, message):
        self.log_listbox.insert(tk.END, message)
        self.log_listbox.yview(tk.END)

    def upload_file(self):
        filepath = filedialog.askopenfilename()
        if not filepath:
            return

        try:
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            self.client_socket.send(f"upload {filename}".encode('utf-8'))
            self.client_socket.recv(1024)  # Acknowledge
            self.client_socket.send(str(file_size).encode('utf-8'))
            self.client_socket.recv(1024)  # Acknowledge

            with open(filepath, "rb") as f:
                self.client_socket.sendall(f.read())

            response = self.client_socket.recv(1024).decode('utf-8')
            self.log_message(response)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to upload file: {e}")

    def download_file(self):
        filename = filedialog.askstring("Download File", "Enter filename to download:")
        owner = filedialog.askstring("File Owner", "Enter the file owner:")
        save_dir = filedialog.askdirectory()

        if not filename or not owner or not save_dir:
            return

        try:
            self.client_socket.send(f"download {filename} {owner}".encode('utf-8'))
            response = self.client_socket.recv(1024).decode('utf-8')

            if response.isdigit():
                file_size = int(response)
                save_path = os.path.join(save_dir, filename)

                with open(save_path, "wb") as f:
                    bytes_received = 0
                    while bytes_received < file_size:
                        chunk = self.client_socket.recv(1024)
                        f.write(chunk)
                        bytes_received += len(chunk)

                self.log_message(f"File {filename} downloaded successfully to {save_path}.")
            else:
                self.log_message(response)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to download file: {e}")

    def list_files(self):
        try:
            self.client_socket.send(b"list")
            response = self.client_socket.recv(1024).decode('utf-8')
            self.log_message("Available files:")
            self.log_message(response)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list files: {e}")

    def disconnect_from_server(self):
        try:
            self.client_socket.close()
            self.disable_controls()
            self.log_message("Disconnected from the server.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to disconnect: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ClientApp(root)
    root.mainloop()
