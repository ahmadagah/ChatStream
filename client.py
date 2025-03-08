import asyncio
import base64
import structlog
import traceback
import struct
from cryptography.fernet import Fernet
import aioconsole
from protocol import (
    OPCODE_EPHEMERAL_MESSAGE,
    OPCODE_JOIN,
    Message,
    # Basic Operations
    OPCODE_HELLO, OPCODE_MESSAGE, OPCODE_ERROR,
    # Room Management
    OPCODE_CREATE_ROOM, OPCODE_LIST_ROOMS, OPCODE_LIST_USERS, OPCODE_LEAVE_ROOM,
    # Connection Management
    OPCODE_CLIENT_DISCONNECT, OPCODE_SERVER_DISCONNECT,
    # Advanced Features
    OPCODE_MULTI_ROOM_MSG, OPCODE_PRIVATE_MESSAGE, OPCODE_SECURE_MESSAGE, OPCODE_FILE_TRANSFER
)

# Initialize a logger (for optional debug/info output)
log = structlog.get_logger()



# Secret key for secure messaging (NOTE: In a real-world app, use a shared key exchange method)
fernet_key = Fernet.generate_key()
cipher = Fernet(fernet_key)  # This is used to encrypt secure messages


async def chat_client() -> None:
    """
    Main entry point for the async client.

    1. Connects to the chat server on 127.0.0.1:6060.
    2. Sends a HELLO message with the chosen username.
    3. Launches two concurrent tasks:
       - send_messages(): Handles user input and sends it to the server.
       - receive_messages(): Listens for incoming server messages and prints them.
    4. Uses asyncio.gather() to run both tasks simultaneously.
    """
    # 1. Connect to the server
    reader, writer = await asyncio.open_connection("127.0.0.1", 8080)
    log.info("Connected to server")

    # 2. Prompt for username in a loop until we get one with no spaces
    username = ""
    while not username:
        username_input = input("Enter your username: ").strip()
        if " " in username_input:
            print("Error: Usernames cannot contain spaces. Please try again.")
            continue
        if not username_input:
            print("Error: Username cannot be empty. Please try again.")
            continue
        username = username_input

    # Send a HELLO message with the chosen username
    writer.write(Message(OPCODE_HELLO, username).encode())
    await writer.drain()
    print(f"[DEBUG] Sent HELLO message with username: {username}")

    # 3. Create tasks for sending & receiving messages
    # print("[DEBUG] Creating send_messages() and receive_messages() tasks...")
    send_task = asyncio.create_task(send_messages(writer))
    receive_task = asyncio.create_task(receive_messages(reader))

    # print("[DEBUG] send_messages() registered in event loop.")
    # print("[DEBUG] receive_messages() registered in event loop.")

    # 4. Run both tasks concurrently
    try:
        print("[DEBUG] Running asyncio.gather() to start both tasks...")
        results = await asyncio.gather(send_task, receive_task, return_exceptions=True)
        print(f"[DEBUG] asyncio.gather() finished with results: {results}")
    except Exception as e:
        print(f"[ERROR] Exception in asyncio.gather(): {e}")
        traceback.print_exc()

async def send_messages(writer: asyncio.StreamWriter) -> None:
    """
    Reads user input (non-blocking via aioconsole.ainput), encodes commands into Message objects,
    and sends them to the server using the appropriate opcode.

    Supported commands (example usage):
      /create <room_name>       -> Create a new chat room
      /list                     -> List all active rooms
      /join <room_name>         -> Join a specific room
      /leave <room_name>        -> Leave a specific room
      /users <room_name>        -> List all users in the specified room
      /msg <username> <message> -> Private message to a single user
      /multi <rooms> <message>  -> Send a message to multiple rooms (comma-separated)
      /secure <message>         -> Send a secure (encrypted) message
      /file <filename>          -> Send a file to another user/room (basic stub)
      /quit                     -> Disconnect from the server
      Anything else             -> Treated as a normal chat message
    """
    print("[DEBUG] send_messages() started...")

    while True:
        # Prompt for user input in a non-blocking way
        user_input = await aioconsole.ainput("> ")

        # Clean up whitespace
        user_input = user_input.strip()
        if not user_input:
            # Ignore empty lines
            continue

        # Decide which opcode to use based on the command
        msg = None

        # 1. Join a Room
        if user_input.startswith("/join "):
            room = user_input.split(" ", 1)[1]
            msg = Message(opcode=OPCODE_JOIN, payload=room)

        # 2. Create a Room
        elif user_input.startswith("/create "):
            parts = user_input.split(" ", 1)
            room_name = parts[1].strip() if len(parts) > 1 else ""
            if not room_name:
                print("Usage: /create <room_name>")
                continue
            msg = Message(opcode=OPCODE_CREATE_ROOM, payload=room_name)

        # 3. List Rooms
        elif user_input == "/list":
            msg = Message(opcode=OPCODE_LIST_ROOMS, payload="")

        # 4. Leave a Room
        elif user_input.startswith("/leave "):
            parts = user_input.split(" ", 1)
            room_name = parts[1].strip() if len(parts) > 1 else ""
            if not room_name:
                print("Usage: /leave <room_name>")
                continue
            msg = Message(opcode=OPCODE_LEAVE_ROOM, payload=room_name)

        # 5. List Users in a Room
        elif user_input.startswith("/users "):
            parts = user_input.split(" ", 1)
            room_name = parts[1].strip() if len(parts) > 1 else ""
            if not room_name:
                print("Usage: /users <room_name>")
                continue
            msg = Message(opcode=OPCODE_LIST_USERS, payload=room_name)

        # 6. Private Message
        elif user_input.startswith("/msg "):
            parts = user_input.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /msg <username> <message>")
                continue
            recipient, message_text = parts[1], parts[2]
            payload = f"{recipient} {message_text}"
            msg = Message(opcode=OPCODE_PRIVATE_MESSAGE, payload=payload)

        # 7. Multi-Room Message
        elif user_input.startswith("/multi "):
            parts = user_input.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /multi <room1,room2> <message>")
                continue
            room_list, message_text = parts[1], parts[2]
            payload = f"{room_list} {message_text}"
            msg = Message(opcode=OPCODE_MULTI_ROOM_MSG, payload=payload)

        # ✅ Secure Message (NEW)
        elif user_input.startswith("/secure "):
            secure_text = user_input.split(" ", 1)[1]
            encrypted_text = cipher.encrypt(secure_text.encode()).decode()  # Encrypt message
            msg = Message(OPCODE_SECURE_MESSAGE, payload=encrypted_text)

        # ✅ Ephemeral Message (NEW)
        elif user_input.startswith("/ephemeral "):
            parts = user_input.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /ephemeral <username> <message>")
                continue
            recipient, message_text = parts[1], parts[2]
            payload = f"{recipient} {message_text}"
            msg = Message(OPCODE_EPHEMERAL_MESSAGE, payload=payload)

        # ✅ File Transfer (NEW)
        elif user_input.startswith("/file "):
            parts = user_input.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /file <target> <filename>")
                continue
            target, filename = parts[1], parts[2]

            # Read file and encode as base64
            try:
                with open(filename, "rb") as f:
                    file_data = base64.b64encode(f.read()).decode()
                payload = f"{target}|{filename}|{file_data}"
                msg = Message(OPCODE_FILE_TRANSFER, payload=payload)
            except FileNotFoundError:
                print(f"[ERROR] File '{filename}' not found.")
                continue

        # 10. Quit
        elif user_input == "/quit":
            msg = Message(opcode=OPCODE_CLIENT_DISCONNECT, payload="Goodbye!")
            writer.write(msg.encode())
            await writer.drain()
            print("[DEBUG] Sent DISCONNECT message. Closing client.")

            # Close the connection gracefully
            writer.close()
            await writer.wait_closed()
            print("[DEBUG] send_messages() exiting.")
            return

        # Otherwise, treat as a normal chat message
        else:
            msg = Message(opcode=OPCODE_MESSAGE, payload=user_input)

        # Send the Message to the server
        writer.write(msg.encode())
        await writer.drain()
        print(f"[DEBUG] Sent message: Opcode={msg.opcode}, Payload={msg.payload}")

async def receive_messages(reader: asyncio.StreamReader) -> None:
    """
    Continuously reads incoming messages from the server and prints them.

    1. Uses reader.read(1024) in a loop to receive data.
    2. Decodes the data into a Message object (opcode + payload).
    3. Prints debug info about the incoming message.
    4. If no data is received, it means the server disconnected or closed the connection.
    """
    print("[DEBUG] receive_messages() function started and waiting for server messages...")
    loop_counter = 0

    while True:
        try:
            loop_counter += 1
            # print(f"[DEBUG] Loop iteration {loop_counter} - Checking for server messages...")

            # Read up to 1024 bytes
            raw_data = await reader.read(1024)
            if not raw_data:
                print("[DEBUG] No data received. Server might have closed the connection.")
                break

            # print(f"[DEBUG] Raw data received (Iteration {loop_counter}): {raw_data}")

            # Decode the raw bytes into a Message
            msg = Message.decode(raw_data)
            print(f"[DEBUG] Decoded Message: Opcode={msg.opcode}, Payload={msg.payload}")

            # ✅ Decrypt Secure Messages
            if msg.opcode == OPCODE_SECURE_MESSAGE:
                try:
                    decrypted_text = cipher.decrypt(msg.payload.encode()).decode()
                    print(f"[SECURE] {decrypted_text}")
                except:
                    print(f"[SECURE] (UNREADABLE) {msg.payload}")

            # ✅ Display Ephemeral Messages
            elif msg.opcode == OPCODE_EPHEMERAL_MESSAGE:
                print(f"[EPHEMERAL] {msg.payload}")

            # ✅ Handle File Transfers
            elif msg.opcode == OPCODE_FILE_TRANSFER:
                target, filename, file_data = msg.payload.split("|", 2)
                with open(f"received_{filename}", "wb") as f:
                    f.write(base64.b64decode(file_data))
                print(f"[FILE] Received '{filename}' from {target}.")

            # Default Messages
            else:
                print(f"[CHAT] {msg.payload}")

        except asyncio.IncompleteReadError:
            print("[ERROR] Incomplete message received. Connection may be unstable.")
            break
        except asyncio.CancelledError:
            print("[DEBUG] receive_messages() cancelled.")
            break
        except Exception as e:
            print(f"[ERROR] Exception in receive_messages(): {e}")
            traceback.print_exc()

    print("[DEBUG] receive_messages() exiting.")

if __name__ == "__main__":
    # Start the async client
    asyncio.run(chat_client())
