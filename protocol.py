import struct
from dataclasses import dataclass

# =====================================================
# MESSAGE OPCODES - Defines different types of actions 
# =====================================================

# Basic Operations (0x01 - 0x0F)
OPCODE_HELLO = 0x01           # Client introduces itself to the server
OPCODE_JOIN = 0x02            # Client joins a room
OPCODE_MESSAGE = 0x03         # Client sends a message to a room
OPCODE_ERROR = 0xFF           # General error message

# Room Management (0x10 - 0x1F)
OPCODE_CREATE_ROOM = 0x10     # Create a new chat room
OPCODE_LIST_ROOMS = 0x11      # Request a list of all active rooms
OPCODE_LIST_USERS = 0x12      # List all users in a specific room
OPCODE_LEAVE_ROOM = 0x13      # Client leaves a room

# Connection Management (0x20 - 0x2F)
OPCODE_CLIENT_DISCONNECT = 0x20  # Client disconnects from the server
OPCODE_SERVER_DISCONNECT = 0x21  # Server disconnects a client

# Advanced Features (0x30 - 0x3F)
OPCODE_MULTI_ROOM_MSG = 0x30  # Send distinct messages to multiple rooms
OPCODE_PRIVATE_MESSAGE = 0x31 # Send a private message to another user
OPCODE_SECURE_MESSAGE = 0x32  # Send an encrypted message
OPCODE_FILE_TRANSFER = 0x33   # Send a file to a user


# =====================================================
# ERROR OPCODES (0xE0 - 0xFF) - Defines error messages
# =====================================================

ERROR_UNKNOWN_COMMAND = 0xE0       # The command is not recognized
ERROR_USERNAME_TAKEN = 0xE1        # Username already in use
ERROR_ROOM_NOT_FOUND = 0xE2        # Attempting to join a nonexistent room
ERROR_ROOM_ALREADY_EXISTS = 0xE3   # Trying to create a room that exists
ERROR_NOT_IN_ROOM = 0xE4           # Leaving a room without being in it
ERROR_USER_NOT_FOUND = 0xE5        # Sending a private message to a nonexistent user
ERROR_FILE_TOO_LARGE = 0xE6        # File transfer exceeds allowed size
ERROR_SERVER_FULL = 0xE7           # No more clients can be accepted
ERROR_PERMISSION_DENIED = 0xE8     # Client lacks permission
ERROR_UNKNOWN = 0xFF               # Generic unknown error



# =====================================================
# MESSAGE STRUCTURE - Defines how messages are encoded
# =====================================================

@dataclass
class Message:
    """
    Represents a structured message in the protocol.
    
    - `opcode`: Identifies the type of message (e.g., join room, send message)
    - `payload`: The actual data sent (e.g., message text, room name)
    """
    opcode: int
    payload: str

    def encode(self) -> bytes:
        """
        Converts the Message object into a binary format for transmission.
        
        Format:
        - First 4 bytes: Opcode (integer)
        - Next 4 bytes: Payload length (integer)
        - Remaining bytes: Payload (string data)
        
        Returns:
            bytes: Encoded binary message
        """
        payload_bytes = self.payload.encode('utf-8')  
        length = len(payload_bytes)  
        return struct.pack('!II', self.opcode, length) + payload_bytes  

    @staticmethod
    def decode(data: bytes):
        """
        Parses a binary message into a Message object.

        Parameters:
            data (bytes): Binary message received from a client or server.

        Returns:
            Message: Decoded Message object.
        """
        opcode, length = struct.unpack('!II', data[:8])  
        payload = data[8:8+length].decode('utf-8')  
        return Message(opcode, payload)  
