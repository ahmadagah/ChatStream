import asyncio
import structlog
import traceback
from protocol import *

# Initialize logger
log = structlog.get_logger()

# Dictionary to track connected clients (Key: Username, Value: Writer Object)
clients = {}

# Dictionary to store chat rooms (Key: Room Name, Value: List of Usernames)
rooms = {}

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handles a new client connection."""
    addr = writer.get_extra_info('peername')  
    log.info("[INFO] New connection", client=addr)

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

        # Reject duplicate usernames
        if username in clients:
            error_msg = Message(OPCODE_ERROR, "Username already taken")
            writer.write(error_msg.encode())
            await writer.drain()
            return

        # Register client
        clients[username] = writer
        log.info(f"[INFO] User {username} connected.")

        # ✅ Add debug log before sending the message
        print(f"[DEBUG] Sending welcome message to {username}")

        # Send welcome message
        welcome_msg = Message(OPCODE_HELLO, "Welcome to the chat server!")
        writer.write(welcome_msg.encode())
        await writer.drain()

        print("[DEBUG] Welcome message sent successfully!")

        while True:
            data = await reader.read(1024)
            if not data:
                break
            
            msg = Message.decode(data)
            log.info(f"[DEBUG] Processing opcode {msg.opcode} with payload: {msg.payload}")

            # Handle different message types
            if msg.opcode == OPCODE_CREATE_ROOM:
                await handle_create_room(username, msg.payload, writer)
            elif msg.opcode == OPCODE_LIST_ROOMS:
                await handle_list_rooms(writer)
            # elif msg.opcode == OPCODE_JOIN:
            #     await handle_join_room(username, msg.payload, writer)
            # elif msg.opcode == OPCODE_LEAVE_ROOM:
            #     await handle_leave_room(username, msg.payload, writer)
            # elif msg.opcode == OPCODE_LIST_USERS:
            #     await handle_list_users(msg.payload, writer)
            elif msg.opcode == OPCODE_MESSAGE:
                await broadcast_message(OPCODE_MESSAGE, f"{username}: {msg.payload}")
            # elif msg.opcode == OPCODE_PRIVATE_MESSAGE:
            #     await handle_private_message(username, msg.payload)
            # elif msg.opcode == OPCODE_MULTI_ROOM_MSG:
            #     await handle_multi_room_message(username, msg.payload)
            elif msg.opcode == OPCODE_CLIENT_DISCONNECT:
                break  # User wants to disconnect
            else:
                error_msg = Message(OPCODE_ERROR, "Unknown command")
                writer.write(error_msg.encode())
                await writer.drain()

    except Exception as e:
        log.error("Error handling client", client=addr, error=str(e))

    finally:
        log.info(f"[INFO] Client {username} disconnected.")
        clients.pop(username, None)  
        writer.close()
        await writer.wait_closed()



async def broadcast_message(opcode: int, payload: str):
    """
    Broadcasts a message with the given opcode and payload to all connected clients.
    """
    log.info(f"[INFO] Broadcasting: Opcode={opcode}, Payload={payload}")
    broadcast_msg = Message(opcode, payload)
    encoded_msg = broadcast_msg.encode()

    for client_writer in clients.values():
        try:
            print(f"[DEBUG] Sending {len(encoded_msg)} bytes to client.")
            client_writer.write(encoded_msg)
            await client_writer.drain()  # Flush the buffer
            print("[DEBUG] Message sent successfully!")
        except Exception as e:
            print(f"[ERROR] Failed to send message: {e}")
            traceback.print_exc()


# async def handle_send_message(username, message_payload):
#     """Broadcasts a message to all clients."""
#     log.info(f"[INFO] Broadcasting message: {username}: {message_payload}")
#     broadcast_msg = Message(OPCODE_MESSAGE, f"{username}: {message_payload}")
#     encoded_msg = broadcast_msg.encode()

#     for client_writer in clients.values():
#         try:
#             print(f"[DEBUG] Sending {len(encoded_msg)} bytes to client.")  # ✅ Print byte length
#             client_writer.write(encoded_msg)  # 🔥 Write data
#             await client_writer.drain()  # ✅ Explicitly flush the buffer
#             print("[DEBUG] Message sent successfully!")
#         except Exception as e:
#             print(f"[ERROR] Failed to send message: {e}")
#             traceback.print_exc()




async def handle_create_room(username, room_name, writer):
    """Handles room creation by a client and ensures it is stored properly."""
    global rooms  

    if room_name in rooms:
        log.info(f"[ERROR] Room '{room_name}' already exists!")  
        # response = Message(ERROR_ROOM_ALREADY_EXISTS, f"Room '{room_name}' already exists!")
        await broadcast_message(ERROR_ROOM_ALREADY_EXISTS, f"Room '{room_name}' already exists!")
    else:
        rooms[room_name] = []  
        log.info(f"[INFO] Room '{room_name}' created.")  
        # response = Message(OPCODE_CREATE_ROOM, f"Room '{room_name}' created successfully")
        await broadcast_message(OPCODE_CREATE_ROOM, f"Room '{room_name}' created successfully")
        print(f"[DEBUG] Room creation response sent successfully!")

    # encoded_response = response.encode()
    # print(f"[DEBUG] Preparing to send room creation confirmation: {encoded_response}")  # ✅ Print encoded message


    # writer.write(encoded_response)  # 🔥 Write data
    # await writer.drain()






async def handle_list_rooms(writer):
    """Sends list of rooms to client."""
    room_list = ", ".join(rooms.keys()) if rooms else "No active rooms."
    log.info(f"[DEBUG] Preparing to send room list: {room_list}")

    await broadcast_message(OPCODE_LIST_ROOMS, f"Active rooms: {room_list}")
    print(f"[DEBUG] Room list sent successfully!")
    
    # response = Message(OPCODE_LIST_ROOMS, room_list)
    # encoded_response = response.encode()

    # # ✅ Add debug logs
    # print(f"[DEBUG] Sending {len(response.encode())} bytes to client.")

    # writer.write(encoded_response)
    # await writer.drain()






async def main():
    """Starts the chat server."""
    server = await asyncio.start_server(handle_client, "0.0.0.0", 6060)
    log.info("[INFO] Server started on port 6060")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())



# async def handle_join_room(username, room_name, writer):
#     """Handles client joining a room."""
#     if room_name not in rooms:
#         response = Message(ERROR_ROOM_NOT_FOUND, f"Room '{room_name}' does not exist")
#     else:
#         if username not in rooms[room_name]:
#             rooms[room_name].append(username)
#         response = Message(OPCODE_JOIN, f"You have joined '{room_name}'")
    
#     log.info(f"[INFO] {username} joined room '{room_name}'. Members: {rooms[room_name]}")
#     writer.write(response.encode())
#     await writer.drain()


# async def handle_leave_room(username, room_name, writer):
#     """Handles client leaving a room."""
#     if room_name not in rooms or username not in rooms[room_name]:
#         response = Message(OPCODE_ERROR, "You are not in this room")
#     else:
#         rooms[room_name].remove(username)
#         response = Message(OPCODE_LEAVE_ROOM, f"You left '{room_name}'")
    
#     log.info(f"[INFO] {username} left room '{room_name}'.")
#     writer.write(response.encode())
#     await writer.drain()


# async def handle_list_users(room_name, writer):
#     """Lists all users in a given room."""
#     if room_name not in rooms:
#         response = Message(OPCODE_ERROR, "Room does not exist")
#     else:
#         users = ", ".join(rooms[room_name]) if rooms[room_name] else "No users in this room"
#         response = Message(OPCODE_LIST_USERS, users)
    
#     writer.write(response.encode())
#     await writer.drain()




# async def handle_private_message(sender, payload):
#     """Handles private messaging."""
#     try:
#         recipient, message_text = payload.split(" ", 1)
#     except ValueError:
#         return  

#     if recipient not in clients:
#         error_msg = Message(OPCODE_ERROR, f"User {recipient} not found")
#         clients[sender].write(error_msg.encode())
#         await clients[sender].drain()
#         return

#     pm = Message(OPCODE_PRIVATE_MESSAGE, f"PM from {sender}: {message_text}")
#     clients[recipient].write(pm.encode())
#     await clients[recipient].drain()


# async def handle_multi_room_message(username, payload):
#     """Sends messages to multiple rooms."""
#     try:
#         room_list, message_text = payload.split(" ", 1)
#     except ValueError:
#         return  

#     room_names = room_list.split(",")

#     for room_name in room_names:
#         if room_name in rooms and username in rooms[room_name]:
#             for user in rooms[room_name]:
#                 if user in clients:
#                     message = Message(OPCODE_MULTI_ROOM_MSG, f"{room_name} | {username}: {message_text}")
#                     clients[user].write(message.encode())
#                     await clients[user].drain()


