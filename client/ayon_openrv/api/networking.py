import socket
from time import sleep

class RVConnector:
    def __init__(self, name="ayon-rv-connect", host="localhost", port=45124):
        self.name = name
        self.host = host
        self.port = port
        self.is_connected = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.connect()

    def __enter__(self):
        """Enters the context manager."""
        while not self.is_connected:
            self.connect()
            print("trying to connect...")
        return self

    def __exit__(self, *args):
        """Exits the context manager."""
        self.close()

    @property
    def message_available(self) -> bool:
        """Checks if a message is available."""
        try:
            msg = self.sock.recv(1, socket.MSG_PEEK)
            if len(msg) > 0:
                return True
        except Exception as err:
            print(err)

        return False

    def connect(self) -> None:
        """Connects to the RV server."""
        if self.is_connected:
            return
        self.__connect_socket()

    def send_message(self, message):
        print(f"send_message: {message}")
        if not self.is_connected:
            return

        msg = f"MESSAGE {len(message)} {message}"
        try:
            self.sock.sendall(msg.encode("utf-8"))
        except Exception:
            self.close()

    def send_event(self, eventName, eventContents, shall_return=True):
        """
        Send a remote event, then wait for a return value (string).
        eventName must be one of the events
        listed in the RV Reference Manual.
        """
        message = f"RETURNEVENT {eventName} * {eventContents}"
        self.send_message(message)
        if shall_return:
            return self.__process_events(process_return_only=True)

    def close(self):
        if self.is_connected:
            self.send_message("DISCONNECT")
            sleep(0.01) # wait for the message to be sent
        
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.is_connected = False

    def receive_message(self):
        msg_type, msg_data = "", None

        try:
            while True:
                char = self.sock.recv(1).decode("utf-8")
                if char == " ":
                    break
                msg_type += char
            msg_data = self.sock.recv(
                len(msg_type)).decode("utf-8")
        except Exception as err:
            print(err)

        return (msg_type, msg_data)

    def __send_initial_greeting(self):
        greeting = f"{self.name} rvController"
        cmd = f"NEWGREETING {len(greeting)} {greeting}"
        try:

            self.sock.sendall(cmd.encode("utf-8"))
        except Exception:
            self.is_connected = False

    def process_message(self, data):
        print(f"process message: {data = }")

    def __process_events(self, process_return_only=False):
        while True:
            while not self.message_available:
                if not self.is_connected:
                    return ""
                
                if not self.message_available and process_return_only:
                    sleep(0.01)
                else:
                    break

            if not self.message_available:
                break
            
            # get single message
            (resp_type, resp_data) = self.receive_message()
            print(f"received message: {resp_type}: {resp_data}")

            if resp_type == "MESSAGE":
                if resp_data == "DISCONNECT":
                    self.is_connected = False
                    self.close()
                    return
                # (event, event_data) = self.process_message()
                self.process_message()

            if resp_type == "PING":
                self.sock.sendall("PONG 1 p".encode("utf-8"))
            if resp_type == "PONG":
                pass
            if resp_type == "GREETING":
                pass
            if resp_type == "NEWGREETING":
                pass
            if resp_type == "NEWGREETING":
                pass
            # return msg

    def __connect_socket(self):
        try:
            self.sock.connect((self.host, self.port))
            self.__send_initial_greeting()
            self.sock.sendall("PINGPONGCONTROL 1 0".encode("utf-8"))
            self.is_connected = True
        except Exception as err:
            print("Failed to establish connection. Is RV running?")
            self.is_connected = False
