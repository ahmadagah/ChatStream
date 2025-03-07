import asyncio
import structlog
import aioconsole
import traceback
import struct
from protocol import (
    Message,
    # Basic Operations
    OPCODE_HELLO, OPCODE_MESSAGE, OPCODE_ERROR,
    # Room Management
    OPCODE_CREATE_ROOM, OPCODE_LIST_ROOMS, OPCODE_LIST_USERS, OPCODE_LEAVE_ROOM, OPCODE_JOIN,
    # Connection Management
    OPCODE_CLIENT_DISCONNECT, OPCODE_SERVER_DISCONNECT,
    # Advanced Features
    OPCODE_MULTI_ROOM_MSG, OPCODE_PRIVATE_MESSAGE, OPCODE_SECURE_MESSAGE, OPCODE_FILE_TRANSFER,
    # Error Codes
    ERROR_UNKNOWN_COMMAND, ERROR_USERNAME_TAKEN, ERROR_ROOM_NOT_FOUND,
    ERROR_ROOM_ALREADY_EXISTS, ERROR_NOT_IN_ROOM, ERROR_USER_NOT_FOUND,
    ERROR_FILE_TOO_LARGE, ERROR_SERVER_FULL, ERROR_PERMISSION_DENIED, ERROR_UNKNOWN
)

# Initialize logger
log = structlog.get_logger()

# Global dictionaries to track clients and rooms
clients = {}  # Key: username, Value: StreamWriter
rooms = {}    # Key: room name, Value: list of usernames

# New: active_rooms mapping to track each user's active room
active_rooms = {}  # Key: username, Value: active room name

# -----------------------------
# Helper function: Global Broadcast
# -----------------------------
async def broadcast_message(opcode: int, payload: str) -> None:
    """
    Broadcasts a message (with given opcode and payload) to all connected clients.
    Used for system-wide notifications.
    """
    log.info(f"[INFO] Broadcasting: Opcode={opcode}, Payload={payload}")
    broadcast_msg = Message(opcode, payload)
    encoded_msg = broadcast_msg.encode()
    
    for client_writer in clients.values():
        try:
            print(f"[DEBUG] Sending {len(encoded_msg)} bytes to client (global).")
            client_writer.write(encoded_msg)
            await client_writer.drain()  # Flush the buffer
            print("[DEBUG] Global message sent successfully!")
        except Exception as e:
            print(f"[ERROR] Failed to send global message: {e}")
            traceback.print_exc()

# -----------------------------
# Helper function: Send Message to a Specific Room
# -----------------------------
async def send_room_message(room_name: str, message_text: str, sender: str) -> None:
    """
    Sends a message to all clients that are members of the specified room.
    The message format is: "<room_name> | <sender>: <message_text>"
    """
    if room_name not in rooms:
        log.error(f"[ERROR] Room '{room_name}' not found for message from {sender}.")
        return

    full_message = f"{room_name} | {sender}: {message_text}"
    room_msg = Message(OPCODE_MESSAGE, full_message)
    encoded_msg = room_msg.encode()

    for user in rooms[room_name]:
        if user in clients:
            try:
                print(f"[DEBUG] Sending {len(encoded_msg)} bytes to {user} in room '{room_name}'.")
                clients[user].write(encoded_msg)
                await clients[user].drain()
                print(f"[DEBUG] Room message sent to {user}.")
            except Exception as e:
                print(f"[ERROR] Failed to send room message to {user}: {e}")
                traceback.print_exc()


async def disconnect_client(username: str) -> None:
    """
    Disconnects a client specified by `username`.
    1. If the client is found, send OPCODE_SERVER_DISCONNECT.
    2. Close the connection.
    3. Remove user from clients, rooms, and active_rooms.
    """
    if username not in clients:
        log.info(f"[INFO] No client with username '{username}' to disconnect.")
        return

    writer = clients[username]
    # 1. Send a SERVER_DISCONNECT message to inform them
    disc_msg = Message(OPCODE_SERVER_DISCONNECT, "Server forcibly disconnecting you.")
    try:
        writer.write(disc_msg.encode())
        await writer.drain()
    except Exception as e:
        log.error("Error sending server disconnect", error=str(e))

    # 2. Close the connection
    writer.close()
    await writer.wait_closed()

    # 3. Cleanup from data structures
    clients.pop(username, None)
    for room_members in rooms.values():
        if username in room_members:
            room_members.remove(username)
    active_rooms.pop(username, None)
    log.info(f"[INFO] {username} forcibly disconnected by server.")
    print(f"[DEBUG] Client {username} forcibly disconnected.")

# -----------------------------
# Handlers for Room Management
# -----------------------------
async def handle_create_room(username: str, room_name: str, writer: asyncio.StreamWriter) -> None:
    """
    Creates a new room if it doesn't exist. Broadcasts a confirmation to all clients.
    """
    global rooms
    if room_name in rooms:
        log.info(f"[ERROR] Room '{room_name}' already exists!")
        await broadcast_message(ERROR_ROOM_ALREADY_EXISTS, f"Room '{room_name}' already exists!")
    else:
        rooms[room_name] = []  # Create new room with no members initially.
        log.info(f"[INFO] Room '{room_name}' created by {username}.")
        await broadcast_message(OPCODE_CREATE_ROOM, f"Room '{room_name}' created successfully by {username}")
        print(f"[DEBUG] Room creation response broadcasted.")

async def handle_list_rooms(username: str, writer: asyncio.StreamWriter) -> None:
    """
    Sends the list of active rooms ONLY to the user who requested it, NOT to everyone.
    """
    # Gather all active rooms into a comma-separated list
    room_list = ", ".join(rooms.keys()) if rooms else "No active rooms."
    log.info(f"[DEBUG] {username} requested room list: {room_list}")

    # Instead of broadcasting to all, only send to this requesting user
    response = Message(OPCODE_LIST_ROOMS, f"Active rooms: {room_list}")
    encoded = response.encode()

    try:
        clients[username].write(encoded)
        await clients[username].drain()
        print(f"[DEBUG] Sent room list to {username} only.")
    except Exception as e:
        print(f"[ERROR] Failed sending room list to {username}: {e}")
        traceback.print_exc()

async def handle_join_room(username: str, room_name: str, writer: asyncio.StreamWriter) -> None:
    """
    Adds the user to the specified room and sets it as their active room.
    Allows joining multiple rooms without leaving previously joined rooms.
    """
    if room_name not in rooms:
        error_msg = Message(ERROR_ROOM_NOT_FOUND, f"Room '{room_name}' does not exist")
        writer.write(error_msg.encode())
        await writer.drain()
        print(f"[DEBUG] Sent error: Room '{room_name}' not found.")
        return

    if username in rooms[room_name]:
        confirmation = Message(OPCODE_JOIN, f"You are already in room '{room_name}'")
        writer.write(confirmation.encode())
        await writer.drain()
        return
    

    # If joining a room that is not 'lobby', remove the user from lobby if present.
    if room_name.lower() != "lobby":
        if "lobby" in rooms and username in rooms["lobby"]:
            rooms["lobby"].remove(username)
            print(f"[DEBUG] Removed {username} from 'lobby' (joining '{room_name}').")

    # Add user to the new room without removing them from other rooms.
    rooms[room_name].append(username)
    # Update active room to the room they just joined.
    active_rooms[username] = room_name
    log.info(f"[INFO] {username} joined room '{room_name}'.")
    await broadcast_message(OPCODE_JOIN, f"{username} joined room '{room_name}'")
    print(f"[DEBUG] {username} joined room '{room_name}'.")


async def handle_leave_room(username: str, room_name: str, writer: asyncio.StreamWriter) -> None:
    """
    Removes the user from the specified room.
    If the user leaves their active room, update the active room to another room they are in,
    or revert to 'lobby' if none.
    """
    if room_name not in rooms or username not in rooms[room_name]:
        error_msg = Message(OPCODE_ERROR, "You are not in this room")
        writer.write(error_msg.encode())
        await writer.drain()
        print(f"[DEBUG] Sent error: You are not in room '{room_name}'.")
        return

    rooms[room_name].remove(username)
    log.info(f"[INFO] {username} left room '{room_name}'.")
    await broadcast_message(OPCODE_LEAVE_ROOM, f"{username} left room '{room_name}'")
    
    # If the room left is the active room, update active_rooms:
    if active_rooms.get(username) == room_name:
        # Choose another room if available; otherwise, default to 'lobby'
        new_active = None
        for r, members in rooms.items():
            if username in members:
                new_active = r
                break
        if new_active is None:
            new_active = "lobby"
            if "lobby" not in rooms:
                rooms["lobby"] = []
            rooms["lobby"].append(username)
        active_rooms[username] = new_active
        print(f"[DEBUG] {username}'s active room updated to '{new_active}'.")


async def handle_list_users(room_name: str, writer: asyncio.StreamWriter) -> None:
    """
    Sends a list of users in the specified room to the requesting client.
    """
    if room_name not in rooms:
        error_msg = Message(OPCODE_ERROR, f"Room '{room_name}' does not exist")
        writer.write(error_msg.encode())
        await writer.drain()
        print(f"[DEBUG] Sent error: Room '{room_name}' does not exist.")
    else:
        users = ", ".join(rooms[room_name]) if rooms[room_name] else "No users in this room"
        response = Message(OPCODE_LIST_USERS, f"Users in '{room_name}': {users}")
        writer.write(response.encode())
        await writer.drain()
        print(f"[DEBUG] Sent user list for room '{room_name}'.")

# -----------------------------
# Handlers for Messaging
# -----------------------------
async def handle_private_message(sender: str, payload: str, writer: asyncio.StreamWriter) -> None:
    """
    Handles a private message.
    Payload should be formatted as "<recipient> <message_text>".
    """
    try:
        recipient, message_text = payload.split(" ", 1)
    except ValueError:
        error_msg = Message(OPCODE_ERROR, "Usage: /msg <username> <message>")
        writer.write(error_msg.encode())
        await writer.drain()
        return

    if recipient not in clients:
        error_msg = Message(OPCODE_ERROR, f"User {recipient} not found")
        writer.write(error_msg.encode())
        await writer.drain()
        print(f"[DEBUG] Sent error: User {recipient} not found.")
        return

    pm = Message(OPCODE_PRIVATE_MESSAGE, f"PM from {sender}: {message_text}")
    clients[recipient].write(pm.encode())
    await clients[recipient].drain()
    print(f"[DEBUG] Private message from {sender} sent to {recipient}.")

async def handle_multi_room_message(username: str, payload: str) -> None:
    """
    Sends a message to multiple rooms.
    Payload format: "<room1,room2,...> <message_text>"
    """
    try:
        room_list_str, message_text = payload.split(" ", 1)
    except ValueError:
        log.error("Invalid multi-room message format.")
        return

    room_names = [room.strip() for room in room_list_str.split(",")]
    for room in room_names:
        if room in rooms:  #server delivers messages even if user hasn’t joined that room
        # if room in rooms and username in rooms[room]:
            await send_room_message(room, message_text, username)
        else:
            print(f"[DEBUG] Skipping room '{room}': Not found or {username} not in room.")

async def handle_secure_message(username: str, payload: str, writer: asyncio.StreamWriter) -> None:
    """
    Handles a secure (encrypted) message.
    Minimal implementation: treat it like a normal message with a "SECURE:" prefix.
    """
    secure_text = f"SECURE from {username}: {payload}"
    await broadcast_message(OPCODE_SECURE_MESSAGE, secure_text)
    print(f"[DEBUG] Secure message broadcasted from {username}.")

async def handle_file_transfer(username: str, payload: str, writer: asyncio.StreamWriter) -> None:
    """
    Handles file transfer.
    Minimal stub: simply broadcasts the filename.
    """
    transfer_info = f"{username} is sending file: {payload}"
    await broadcast_message(OPCODE_FILE_TRANSFER, transfer_info)
    print(f"[DEBUG] File transfer info broadcasted from {username}.")





async def server_console(server):
    """
    Allows an admin to type commands directly in the server console.
    'dc <username>' => disconnect that client if found.
    'quit'          => forcibly disconnect all clients and stop the server.
    """
    while True:
        command = await aioconsole.ainput("admin> ")
        command = command.strip()
        
        if command.startswith("dc "):
            target_user = command.split(" ", 1)[1].strip()
            await disconnect_client(target_user)
        
        elif command == "quit":
            print("[ADMIN] Shutting down the server and disconnecting all clients...")
            # 1. Disconnect all connected clients
            for user in list(clients.keys()):
                await disconnect_client(user)

            # 2. Close the server
            server.close()
            await server.wait_closed()

            print("[ADMIN] Server is now shut down. Exiting admin console.")
            return  # Stop the console task, which will allow main() to finish

        else:
            print("[ADMIN] Unknown command. Try 'dc <username>' or 'quit'.")



# -----------------------------
# Main Client Handler
# -----------------------------
async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """
    Handles a new client connection:
      1. Receives the initial HELLO message and registers the user.
      2. Processes incoming messages by opcode and calls appropriate handlers.
      3. Cleans up when the client disconnects.
    """
    addr = writer.get_extra_info('peername')
    log.info("[INFO] New connection", client=addr)

    registered = False  # NEW FLAG: Track if the user was successfully registered.

    try:
        # Read client's initial HELLO message
        data = await reader.read(1024)
        if not data:
            return

        msg = Message.decode(data)
        print(f"[DEBUG] Received HELLO: {msg.payload}")

        if msg.opcode != OPCODE_HELLO:
            error_msg = Message(OPCODE_ERROR, "Expected HELLO message first")
            writer.write(error_msg.encode())
            await writer.drain()
            return

        username = msg.payload.strip()


        # SERVER-SIDE VALIDATION: Disallow spaces in usernames.
        if " " in username:
            error_msg = Message(OPCODE_ERROR, "Usernames cannot contain spaces")
            writer.write(error_msg.encode())
            await writer.drain()
            print(f"[DEBUG] Sent error: Usernames cannot contain spaces.")
            return

        # Reject duplicate usernames
        if username in clients:
            error_msg = Message(OPCODE_ERROR, "Username already taken")
            writer.write(error_msg.encode())
            await writer.drain()
            return

        # Register client
        clients[username] = writer
        registered = True # Flag the user as successfully registered
        log.info(f"[INFO] User {username} connected.")


        # Automatically add user to the default lobby and set active room
        if "lobby" not in rooms:
            rooms["lobby"] = []
        rooms["lobby"].append(username)
        active_rooms[username] = "lobby"
        log.info(f"[INFO] {username} added to lobby as active room.")

        print(f"[DEBUG] Sending welcome message to {username}")
        welcome_msg = Message(OPCODE_HELLO, "Welcome to the chat server!")
        writer.write(welcome_msg.encode())
        await writer.drain()
        print("[DEBUG] Welcome message sent successfully!")

        # Main loop: Process incoming messages
        while True:
            data = await reader.read(1024)
            if not data:
                break

            msg = Message.decode(data)
            log.info(f"[DEBUG] Processing opcode {msg.opcode} with payload: {msg.payload}")

            if msg.opcode == OPCODE_CREATE_ROOM:
                await handle_create_room(username, msg.payload, writer)
            elif msg.opcode == OPCODE_LIST_ROOMS:
                await handle_list_rooms(username, writer)
            elif msg.opcode == OPCODE_JOIN:
                await handle_join_room(username, msg.payload, writer)
            elif msg.opcode == OPCODE_LEAVE_ROOM:
                await handle_leave_room(username, msg.payload, writer)
            elif msg.opcode == OPCODE_LIST_USERS:
                await handle_list_users(msg.payload, writer)
            elif msg.opcode == OPCODE_MESSAGE:
                # Check for explicit room override using the "|" delimiter.
                # If present, send to that room; otherwise, use the user's active room.
                if "|" in msg.payload:
                    room_name, message_text = msg.payload.split("|", 1)
                    room_name = room_name.strip()
                    message_text = message_text.strip()
                    await send_room_message(room_name, message_text, username)
                else:
                    # Use the active room for the user.
                    destination = active_rooms.get(username, "lobby")
                    await send_room_message(destination, msg.payload, username)
            elif msg.opcode == OPCODE_PRIVATE_MESSAGE:
                await handle_private_message(username, msg.payload, writer)
            elif msg.opcode == OPCODE_MULTI_ROOM_MSG:
                await handle_multi_room_message(username, msg.payload)
            elif msg.opcode == OPCODE_SECURE_MESSAGE:
                await handle_secure_message(username, msg.payload, writer)
            elif msg.opcode == OPCODE_FILE_TRANSFER:
                await handle_file_transfer(username, msg.payload, writer)
            elif msg.opcode == OPCODE_CLIENT_DISCONNECT:
                break  # Client requests disconnect
            else:
                error_msg = Message(OPCODE_ERROR, "Unknown command")
                writer.write(error_msg.encode())
                await writer.drain()

    except Exception as e:
        log.error("Error handling client", client=addr, error=str(e))
    finally:
        if registered:
            log.info(f"[INFO] Client {username} disconnected.")
            # Clean up: remove user from all rooms
            for room in rooms.values():
                if username in room:
                    room.remove(username)
            active_rooms.pop(username, None)
            clients.pop(username, None)
        writer.close()
        await writer.wait_closed()


# -----------------------------
# Main Function to Start Server
# -----------------------------
async def main() -> None:
    server = await asyncio.start_server(handle_client, "0.0.0.0", 6060)
    log.info("[INFO] Server started on port 6060")

    # Create the admin console task (which will trigger shutdown on 'quit')
    console_task = asyncio.create_task(server_console(server))

    try:
        # Run both the server's serve_forever() and the admin console concurrently.
        await asyncio.gather(server.serve_forever(), console_task)
    except asyncio.CancelledError:
        # Expected cancellation when the server is shut down.
        pass

    # This print will execute after both tasks have finished.
    print("[ADMIN] All clients disconnected and server shutdown gracefully.")


if __name__ == "__main__":
    asyncio.run(main())

