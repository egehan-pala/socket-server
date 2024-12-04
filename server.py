import socket
import threading
import tkinter as tk
from tkinter import filedialog
import os
import shlex

class Server:
    def __init__(self, root):
        self.root = root
        self.root.title("File Transfer Server")
        self.root.geometry("500x500")
        self.server_socket = None
        self.clients = {}
        self.files = {} #Holding info of clients and sockets to communicate
        self.storage_dir = None
        self.server_running = False

        # Frame for server settings
        settings_frame = tk.Frame(root)
        settings_frame.pack(pady=10)

        tk.Label(settings_frame, text="Server Port:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.port_entry = tk.Entry(settings_frame)
        self.port_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(settings_frame, text="Storage Folder:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.select_button = tk.Button(settings_frame, text="Select Folder", command=self.select_folder)
        self.select_button.grid(row=1, column=1, padx=5, pady=5)
        
        #Starting info created in first two steps


        # Frame for server buttons
        control_frame = tk.Frame(root)
        control_frame.pack(pady=10)

        self.start_button = tk.Button(control_frame, text="Start Server", command=self.start_server)
        self.start_button.grid(row=0, column=0, padx=5, pady=5)

        self.stop_button = tk.Button(control_frame, text="Close Server", command=self.stop_server, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5, pady=5)

        # Activity log
        log_frame = tk.Frame(root)
        log_frame.pack(pady=10)

        tk.Label(log_frame, text="Activity Log:").pack()
        self.log_listbox = tk.Listbox(log_frame, width=50, height=15, selectmode=tk.SINGLE)
        self.log_listbox.pack()

        # Scroolbar for listbox
        scrollbar = tk.Scrollbar(log_frame, orient="vertical", command=self.log_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_listbox.config(yscrollcommand=scrollbar.set)

    def log_message(self, message):
        self.log_listbox.insert(tk.END, message)
        self.log_listbox.yview(tk.END)

    def select_folder(self):
        self.storage_dir = filedialog.askdirectory()
        if self.storage_dir:
            self.log_message(f"Storage directory set to: {self.storage_dir}") #Info about where is server located
            self.update_file_list() # Getting info about previous files
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

        # Server starting conditions checked
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server_socket.bind(('0.0.0.0', int(port)))
            self.server_socket.listen(5)
            self.server_running = True
            self.log_message(f"Server started on port {port}")

            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL) # Makins buttons disable or normal to make user friendly GUI
            threading.Thread(target=self.accept_clients, daemon=True).start() #Listening thread started for server listening clients
        except Exception as e:
            self.log_message(f"Error starting server: {e}")
            self.server_socket = None

    def stop_server(self):
        try:
            self.log_message("Shutting down server...")

            # Stop accepting new clients
            self.server_running = False
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
                self.log_message("Server socket closed.")

            # Close all client connections and inform them about disconnection
            for client_name in list(self.clients.keys()):
                client_socket = self.clients[client_name]
                try:
                    closing_message = "DISCONNECT" # Information message for client to disconnect themself

                    client_socket.send(closing_message.encode())  

                    client_socket.close()

                    self.log_message(f"Disconnected client {client_name}")
                except Exception as e:
                    self.log_message(f"Error disconnecting client {client_name}: {e}")

            self.clients.clear()  # Clear the clients list

            # Update the GUI buttons
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.log_message("Server closed successfully.")
        except Exception as e:
            self.log_message(f"Error closing server: {e}")
            self.root.quit()
            self.root.destroy()

    def accept_clients(self):
        while self.server_running:
            try:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start() # Starting thread for listening client actions list_files etc..
            except Exception as e:
                if self.server_running:
                    self.log_message(f"Error accepting clients: {e}")
                break

    def handle_client(self, conn, addr): # Getting request from clients
        try:
            conn.send(b"Enter your username: ")
            username = conn.recv(1024).decode().strip()
            if username in self.clients:
                conn.send(b"Error: Username already taken!\n") # Info about username already taken
                conn.close()
                
                return

            self.clients[username] = conn
            self.log_message(f"Client {username} connected from {addr}")
            conn.send(b"Welcome to the server!\n")

            while True:
                data = conn.recv(1024).decode().strip()
                if not data:
                    break
                
                # Handling client requests and calling their functions
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
                        self.send_file(conn, filename, owner, username)
                    except ValueError:
                        conn.send(b"Error: Invalid download command format.\n")
                        continue
                else:
                    conn.send(b"Error: Invalid command!\n")
        except Exception as e:
            self.log_message(f"Error handling client {addr}: {e}")
        finally:
            conn.close()
            if username in self.clients:
                del self.clients[username]
                self.log_message(f"Client {username} disconnected.")

    def send_file_list(self, conn):
        try:
            if not self.files:
                conn.send(b"No files available.\n")
            else:
                file_list_entries = []
                for filename, owner in self.files.items():
                    prefix = f"{owner}_" # Writing name of file owners
                    if filename.startswith(prefix):
                        display_name = filename[len(prefix):]
                    else:
                        display_name = filename
                    file_list_entries.append(f"{display_name} (Owner: {owner})")
                file_list = "\n".join(file_list_entries)
                conn.send(file_list.encode())
        except Exception as e:
            self.log_message(f"Error sending file list: {e}")
            conn.send(b"Error: Failed to retrieve file list.\n")

    def receive_file(self, conn, filename, username): # Upload file function
        try:
            # Request file size from client
            conn.send(b"Send file size: ")
            file_size_data = conn.recv(1024).decode().strip()

            # Validate received file size
            if not file_size_data.isdigit():
                raise ValueError(f"Invalid file size received: {file_size_data}")

            file_size = int(file_size_data)
            unique_filename = f"{username}_{filename}"
            filepath = os.path.join(self.storage_dir, unique_filename) # Storage place of folder

            # If the file already exist allow overwriting
            if os.path.exists(filepath):
                self.log_message(f"Warning: Overwriting existing file {filename} uploaded by {username}.")

            received = 0

            # Write the file data to disk
            with open(filepath, "wb") as f:
                while received < file_size:
                    data = conn.recv(min(1024, file_size - received)) #Dealing with high file sizes make them packet sending style
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
        unique_filename = f"{username}_{filename}"  # Include username prefix for deleting only owner's file
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

    def send_file(self, conn, filename, owner, requesting_user): # Download file function
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
                    chunk = f.read(1024) # Again sending in packets to client
                    if not chunk:
                        break
                    conn.send(chunk)

            
            conn.send(b"File sent successfully.\n")
            self.log_message(f"File {filename} sent to {requesting_user} from {owner}.")

            # Checking if requsting_user is the owner the file
            if owner in self.clients and owner != requesting_user:
                uploader_conn = self.clients[owner]

                # Send notification to file owner
                try:
                    notification = f"NOTIFICATION: Your file '{filename}' was downloaded by {requesting_user}."
                    uploader_conn.send(notification.encode())
                    self.log_message(f"Notification sent to {owner} about download by {requesting_user}.")
                except Exception as e:
                    self.log_message(f"Error sending notification to {owner}: {e}")

        except Exception as e:
            conn.send(b"Error: File transfer failed.\n")
            self.log_message(f"Error sending file {filename} from {owner}: {e}")

    def update_file_list(self): # Using this for accesing file if it is used before by server
        if not self.storage_dir:
            return

        self.files = {}
        for filename in os.listdir(self.storage_dir):
            if os.path.isfile(os.path.join(self.storage_dir, filename)):
                parts = filename.split('_', 1)
                if len(parts) == 2:
                    owner, actual_filename = parts
                    self.files[filename] = owner

if __name__ == "__main__":
    root = tk.Tk()
    app = Server(root)
    root.mainloop()
