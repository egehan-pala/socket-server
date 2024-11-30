import socket
import threading
import tkinter as tk
from tkinter import filedialog
import os
import shlex 

class Server:
    def __init__(self, root):
        self.root = root
        self.root.title("Server GUI")
        self.server_socket = None
        self.clients = {}
        self.files = {}
        self.storage_dir = None

        # GUI Components
        tk.Label(root, text="Server Port:").pack()
        self.port_entry = tk.Entry(root)
        self.port_entry.pack()

        tk.Label(root, text="Storage Folder:").pack()
        self.select_button = tk.Button(root, text="Select Folder", command=self.select_folder)
        self.select_button.pack()

        self.start_button = tk.Button(root, text="Start Server", command=self.start_server)
        self.start_button.pack()

        self.stop_button = tk.Button(root, text="Close Server", command=self.stop_server, state=tk.DISABLED)
        self.stop_button.pack() #newly added


        tk.Label(root, text="Activity Log:").pack()
        self.log_listbox = tk.Listbox(root, width=50, height=20)
        self.log_listbox.pack()

    def log_message(self, message):
        self.log_listbox.insert(tk.END, message)
        self.log_listbox.yview(tk.END)

    def select_folder(self):
        self.storage_dir = filedialog.askdirectory()
        if self.storage_dir:
            self.log_message(f"Storage directory set to: {self.storage_dir}")
            self.update_file_list()
        else:
            self.log_message("No folder selected.")

    def start_server(self):
        port = self.port_entry.get()
        if not port.isdigit():
            self.log_message("Error: Invalid port number!")
            return
        if not self.storage_dir:
            self.log_message("Error: Storage folder not selected!")
            return

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', int(port)))
        self.server_socket.listen(5)
        self.log_message(f"Server started on port {port}")

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        threading.Thread(target=self.accept_clients, daemon=True).start()

    def stop_server(self):
        try:
            self.log_message("Shutting down server...")

            # Stop accepting new clients
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
                self.log_message("Server socket closed.")

            # Close all client connections
            for client_name in list(self.clients.keys()):
                client_socket = self.clients[client_name]
                try:
                    closing_message = "DISCONNECT"
                    
                    client_socket.send(closing_message.encode())  # Send closing message to client
                    
                    client_socket.close()
                    
                    self.log_message(f"Disconnected client {client_name}")
                except Exception as e:
                    self.log_message(f"Error disconnecting client {client_name}: {e}")

            self.clients.clear()  # Clear the clients list

            # Update the GUI
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.log_message("Server closed successfully.")
        except Exception as e:
            self.log_message(f"Error closing server: {e}")
            self.root.quit()
            self.root.destroy()


    def accept_clients(self):
        while True:
            conn, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()


    def handle_client(self, conn, addr):
        conn.send(b"Enter your username: ")
        username = conn.recv(1024).decode().strip()
        if username in self.clients:
            conn.send(b"Error: Username already taken!\n")
            conn.close()
            return

        self.clients[username] = conn
        self.log_message(f"Client {username} connected from {addr}")
        conn.send(b"Welcome to the server!\n")

        while True:
            try:
                data = conn.recv(1024).decode().strip()
                if not data:
                    break

                if data.startswith("list"):
                    self.send_file_list(conn)
                elif data.startswith("upload"):
                    try:
                        tokens = shlex.split(data)
                        if len(tokens) != 2:
                            conn.send(b"Error: Invalid upload command format.\n")
                            continue
                        _, filename = tokens
                        self.receive_file(conn, filename, username)
                    except ValueError:
                        conn.send(b"Error: Invalid upload command format.\n")
                        continue
                elif data.startswith("delete"):
                    try:
                        tokens = shlex.split(data)
                        if len(tokens) != 2:
                            conn.send(b"Error: Invalid delete command format.\n")
                            continue
                        _, filename = tokens
                        self.delete_file(conn, filename, username)
                    except ValueError:
                        conn.send(b"Error: Invalid delete command format.\n")
                        continue
                elif data.startswith("download"):
                    try:
                        tokens = shlex.split(data)
                        
                        if len(tokens) != 3:
                            conn.send(b"Error: Invalid download command format.\n")
                            continue
                        _, filename, owner = tokens
                        self.send_file(conn, filename, owner,username)

                    except ValueError:
                        conn.send(b"Error: Invalid download command format.\n")
                        continue
                else:
                    conn.send(b"Error: Invalid command!\n")
            except Exception as e:
                self.log_message(f"Error handling client {username}: {e}")
                break

        conn.close()
        del self.clients[username]
        self.log_message(f"Client {username} disconnected.")


    def send_file_list(self, conn):
        if not self.files:
            conn.send(b"No files available.\n")
        else:
            file_list_entries = []
            for filename, owner in self.files.items():
                prefix = f"{owner}_"
                if filename.startswith(prefix):
                    display_name = filename[len(prefix):]
                else:
                    display_name = filename
                file_list_entries.append(f"{display_name} (Owner: {owner})")
            file_list = "\n".join(file_list_entries)
            conn.send(file_list.encode())

    def receive_file(self, conn, filename, username):
        try:
            # Request file size from client
            conn.send(b"Send file size: ")
            file_size_data = conn.recv(1024).decode().strip()

            # Validate received file size
            if not file_size_data.isdigit():
                raise ValueError(f"Invalid file size received: {file_size_data}")

            file_size = int(file_size_data)
            unique_filename = f"{username}_{filename}"
            filepath = os.path.join(self.storage_dir, unique_filename)

            # If the file already exists, allow overwriting
            if os.path.exists(filepath):
                self.log_message(f"Warning: Overwriting existing file {filename} uploaded by {username}.")

            received = 0

            # Write the file data to disk
            with open(filepath, "wb") as f:
                while received < file_size:
                    data = conn.recv(min(1024, file_size - received))
                    if not data:
                        raise ConnectionError("Connection interrupted during file upload.")
                    f.write(data)
                    received += len(data)

            # Check if the entire file was received
            if received == file_size:
                self.files[unique_filename] = username
                conn.send(b"File received successfully.\n")
                self.log_message(f"File {filename} uploaded successfully by {username}.")
            else:
                raise ValueError(f"File size mismatch: expected {file_size}, received {received}")

        except ValueError as ve:
            conn.send(f"Error: {ve}\n".encode())
            self.log_message(f"Error receiving file {filename} from {username}: {ve}")

        except ConnectionError as ce:
            conn.send(b"Error: Connection lost during file upload.\n")
            self.log_message(f"Connection error for file {filename} from {username}: {ce}")

        except Exception as e:
            conn.send(b"Error: File upload failed.\n")
            self.log_message(f"Unexpected error receiving file {filename} from {username}: {e}")

    def delete_file(self, conn, filename, username):
        unique_filename = f"{username}_{filename}"  # Include username prefix
        if unique_filename in self.files and self.files[unique_filename] == username:
            try:
                # Remove the file from the storage directory
                file_path = os.path.join(self.storage_dir, unique_filename)
                os.remove(file_path)
                del self.files[unique_filename]  # Remove the file entry
                conn.send(b"File deleted successfully.\n")
                self.log_message(f"File {filename} deleted by {username}.")
            except FileNotFoundError:
                conn.send(b"Error: File not found on disk.\n")
                self.log_message(f"Error deleting file {filename}: File not found on disk.")
            except Exception as e:
                conn.send(b"Error: Unable to delete the file.\n")
                self.log_message(f"Error deleting file {filename} for {username}: {e}")
        else:
            conn.send(b"Error: File not found or insufficient permissions.\n")
            self.log_message(f"Failed delete attempt by {username} for file {filename}.")

    def send_file(self, conn, filename, owner,requesting_user):
        try:
            # Construct the unique filename
            unique_filename = f"{owner}_{filename}"
            if unique_filename not in self.files:
                conn.send(b"Error: File not found.\n")
                self.log_message(f"Client requested missing file: {filename} from {owner}.")
                return

            filepath = os.path.join(self.storage_dir, unique_filename)
            file_size = os.path.getsize(filepath)

            # Notify client about the file size
            conn.send(str(file_size).encode())
            confirmation = conn.recv(1024).decode()
            if confirmation != "Ready":
                self.log_message(f"Client not ready to receive file: {filename} from {owner}.")
                return

            # Send the file in chunks
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    conn.send(chunk)

            # Notify client about successful transfer
            conn.send(b"File sent successfully.\n")
            self.log_message(f"File {filename} sent to {requesting_user} from {owner}.")
            if owner in self.clients:
                uploader_conn = self.clients[owner]
                uploader_conn.send(f"File {filename} was downloaded by {requesting_user}.\n".encode())
            if owner in self.clients and owner != requesting_user:
                uploader_conn = self.clients[owner]
               
                # Send the message to the owner's client, which will be displayed on the owner's GUI
                uploader_conn.send(f"File {filename} was downloaded by {requesting_user}.\n".encode())
   
        except Exception as e:
            conn.send(b"Error: File transfer failed.\n")
            self.log_message(f"Error sending file {filename} from {owner}: {e}")


    def update_file_list(self):
    
        if not self.storage_dir:
            return
        
        self.files = {}
        for filename in os.listdir(self.storage_dir):
            if os.path.isfile(os.path.join(self.storage_dir, filename)):
                owner = filename.split('_')[0]  # Assuming the file has the format `owner_filename`
                self.files[filename] = owner
if __name__ == "__main__":
    root = tk.Tk()
    app = Server(root)
    root.mainloop()