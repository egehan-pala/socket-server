import socket
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os
import threading
import time
from tkinter import ttk

class Client:
    def __init__(self, root):
        self.root = root
        self.root.title("Client GUI")
        self.client_socket = None
        self.username = None
        self.socket_lock = threading.RLock()  # Using RLock for reentrancy
        self.receive_thread_running = False  # Flag to control receive thread

        # GUI Components
        self.create_gui()

    def create_gui(self):
        
        style = ttk.Style()
        style.theme_use('clam')  # Theme for good looking GUI

        # GUI starting compenents
        settings_frame = ttk.Frame(self.root)
        settings_frame.pack(pady=10)

        ttk.Label(settings_frame, text="Server IP:").grid(row=0, column=0, padx=5, pady=5)
        self.server_ip_entry = ttk.Entry(settings_frame)
        self.server_ip_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(settings_frame, text="Server Port:").grid(row=1, column=0, padx=5, pady=5)
        self.port_entry = ttk.Entry(settings_frame)
        self.port_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(settings_frame, text="Username:").grid(row=2, column=0, padx=5, pady=5)
        self.username_entry = ttk.Entry(settings_frame)
        self.username_entry.grid(row=2, column=1, padx=5, pady=5)

        self.connect_button = ttk.Button(settings_frame, text="Connect", command=self.connect_to_server)
        self.connect_button.grid(row=3, columnspan=2, pady=10)

        

        #Activity log box 
        log_frame = ttk.Frame(self.root)
        log_frame.pack(pady=10)

        ttk.Label(log_frame, text="Activity Log:").pack()
        self.log_listbox = tk.Listbox(log_frame, width=70, height=15)
        self.log_listbox.pack()

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_listbox.config(yscrollcommand=scrollbar.set)

        # File operations of client buttons
        file_operations_frame = ttk.Frame(self.root)
        file_operations_frame.pack(pady=10)

        self.upload_button = ttk.Button(file_operations_frame, text="Upload File", command=self.upload_file, state=tk.DISABLED)
        self.upload_button.grid(row=0, column=0, padx=5, pady=5)

        self.delete_button = ttk.Button(file_operations_frame, text="Delete File", command=self.delete_file, state=tk.DISABLED)
        self.delete_button.grid(row=0, column=1, padx=5, pady=5)

        self.download_button = ttk.Button(file_operations_frame, text="Download File", command=self.download_file, state=tk.DISABLED)
        self.download_button.grid(row=1, column=0, padx=5, pady=5)

        self.list_files_button = ttk.Button(file_operations_frame, text="List Files", command=self.list_files, state=tk.DISABLED)
        self.list_files_button.grid(row=1, column=1, padx=5, pady=5)

        # Connection status
        status_frame = ttk.Frame(self.root)
        status_frame.pack(pady=10)

        
        self.status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.status_label.pack()

        # Disconnect button
        disconnect_frame = ttk.Frame(self.root)
        disconnect_frame.pack(pady=10)

        self.disconnect_button = ttk.Button(disconnect_frame, text="Disconnect", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_button.pack()

    def log_message(self, message):
        # Thread safe logging
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
        self.client_socket.settimeout(5)  # Set a timeout of 5 seconds

        try:
            self.client_socket.connect((server_ip, int(port)))
            self.client_socket.settimeout(None)  # Reset timeout to blocking mode
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
            self.start_receive_thread()
            self.update_status_label("Connected")
            self.connect_button.config(state=tk.DISABLED)

        except Exception as e:
            self.log_message(f"Error: Failed to connect to the server. {e}")
        finally:
            self.client_socket.settimeout(None)  # Ensure timeout is reset


    def enable_controls(self): # Enable request options after connection
        self.upload_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL)
        self.download_button.config(state=tk.NORMAL)
        self.list_files_button.config(state=tk.NORMAL)
        self.disconnect_button.config(state=tk.NORMAL)

    def disable_controls(self): # Disable requst options after disconnect
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

        # New thread for upload 
        threading.Thread(target=self._upload_file_thread, args=(filepath,), daemon=True).start()

    def _upload_file_thread(self, filepath):
        try:
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)

            with self.socket_lock: #Locking for thread crashes
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
            with self.socket_lock: # Locking for thread crashes
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

        # New thread for downloading files
        threading.Thread(target=self._download_file_thread, args=(filename, owner, save_dir), daemon=True).start()

    def _download_file_thread(self, filename, owner, save_dir):
        try:
            with self.socket_lock: # Locking for thread crashes
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
                        data = self.client_socket.recv(min(4096, remaining)) # Make them packet delivery again for deal with large file sizes
                        if not data:
                            break
                        f.write(data)
                        received += len(data)

                
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
                for line in response.splitlines(): # Split them from new lines to make them readable
                    self.log_message(line)

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
        self.update_status_label("Disconnected")
        self.connect_button.config(state=tk.NORMAL)

    def start_receive_thread(self): # Listening thread starter for receive message function using this in connect server function
        
        self.receive_thread_running = True
        receive_thread = threading.Thread(target=self.receive_message, daemon=True)
        receive_thread.start()

    def receive_message(self): # Listening messages from server
        try:
            while self.receive_thread_running:
                acquired = self.socket_lock.acquire(timeout=0.1) # This is for crash 
                if acquired:
                    try:
                        if self.client_socket is None:
                            break  # Socket is closed exit the loop
                        self.client_socket.settimeout(0.1)
                        try:
                            message = self.client_socket.recv(1024).decode()
                            if message: # Message content checking for motion of client
                                if message.startswith("NOTIFICATION:"):
                                    self.log_message(f"{message}")
                                elif message.startswith("DISCONNECT"):
                                    self.log_message("Disconnected by server because server is closed.")
                                    self.disconnect()
                                    break
                                else:
                                    # Handle other messages
                                    self.log_message(f"{message}")
                            else:
                                # Connection closed by server
                                self.log_message("Connection closed by server.")
                                self.disconnect()
                                break
                        except socket.timeout:
                            continue  # Contiune to listening 
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
                    
                    # Wait and try again
                    time.sleep(0.1)
        except Exception as e:
            self.log_message(f"Connection error: {e}")
            if self.client_socket:
                self.client_socket.close()
    
    def update_status_label(self, status): # User frienly function for GUI informing about connection 
        if status == "Connected":
            self.status_label.config(text="Connected", foreground="green")
        elif status == "Disconnected":
            self.status_label.config(text="Disconnected", foreground="red")
        else:
            self.status_label.config(text=status, foreground="orange")


if __name__ == "__main__":
    root = tk.Tk()
    app = Client(root)
    root.mainloop()