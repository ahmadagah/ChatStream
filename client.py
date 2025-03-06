import asyncio
import structlog
import traceback
import struct
import aioconsole
from protocol import Message, OPCODE_HELLO, OPCODE_CREATE_ROOM, OPCODE_JOIN, OPCODE_LIST_ROOMS, OPCODE_LIST_USERS, OPCODE_LEAVE_ROOM, OPCODE_PRIVATE_MESSAGE, OPCODE_MULTI_ROOM_MSG, OPCODE_CLIENT_DISCONNECT, OPCODE_MESSAGE



# Initialize logger
log = structlog.get_logger()

async def chat_client():
    """
    Handles the client-side communication:
    - Connects to the chat server.
    - Sends and receives messages.
    - Supports room management and private messaging.
    """
    reader, writer = await asyncio.open_connection("127.0.0.1", 6060)
    log.info("Connected to server")

    # Send username at the start
    username = input("Enter your username: ").strip()
    writer.write(Message(OPCODE_HELLO, username).encode())
    await writer.drain()
    print(f"[DEBUG] Sent HELLO message with username: {username}")

    # ✅ Read the welcome message immediately
    # data = await reader.read(1024)
    # if data:
    #     msg = Message.decode(data)
    #     print(f"[DEBUG] Received: Opcode={msg.opcode}, Payload={msg.payload}")
    #     print(msg.payload)  # ✅ Show welcome message
    # else:
    #     print("[ERROR] No response from server!")

    # raw_data = await reader.readexactly(8)  # Read fixed-length opcode + payload size
    # opcode, length = struct.unpack('!II', raw_data)
    # payload_data = await reader.readexactly(length)  # Read exact payload size
    # msg = Message.decode(raw_data + payload_data)

    # print(f"[DEBUG] Received: Opcode={msg.opcode}, Payload={msg.payload}")


    print("[DEBUG] Creating send_messages() and receive_messages() tasks...")
    send_task = asyncio.create_task(send_messages(writer))
    receive_task = asyncio.create_task(receive_messages(reader))

    print("[DEBUG] send_messages() registered in event loop.")
    print("[DEBUG] receive_messages() registered in event loop.")

    try:
        print("[DEBUG] Running asyncio.gather() to start both tasks...")
        result = await asyncio.gather(send_task, receive_task, return_exceptions=True) # Wait for both tasks to complete
        print("[DEBUG] asyncio.gather() finished with result: {result}") # ✅ Confirm completion
    except Exception as e:
        print(f"[ERROR] Exception in asyncio.gather(): {e}")
        traceback.print_exc()




async def send_messages(writer):
    """
    Reads user input, encodes messages, and sends them to the server.
    """
    print("[DEBUG] send_messages() started...")  # Debugging output

    while True:
        print("[DEBUG] Waiting for user input...")  # ✅ Debugging message
        # user_input = input("> ").strip()


        print("[DEBUG] Before aiconsole.ainput()")
        user_input = await aioconsole.ainput("> ")
        print(f"[DEBUG] After aiconsole.ainput(), user_input={user_input!r}")

        user_input = user_input.strip()
        if not user_input:
            continue  # Ignore empty messages

        # print(f"[DEBUG] Sending user input: {user_input}")

        if user_input.startswith("/join "):
            room = user_input.split(" ", 1)[1]
            msg = Message(OPCODE_JOIN, room)

        elif user_input.startswith("/create "):
            parts = user_input.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                print("Usage: /create <room_name>")
                continue
            room = parts[1].strip()
            msg = Message(OPCODE_CREATE_ROOM, room)

        elif user_input == "/list":
            msg = Message(OPCODE_LIST_ROOMS, "")

        elif user_input == "/quit":
            msg = Message(OPCODE_CLIENT_DISCONNECT, "Goodbye!")
            writer.write(msg.encode())
            await writer.drain()
            print("[DEBUG] Sent DISCONNECT message. Closing client.")

            writer.close()
            await writer.wait_closed()

            print("[DEBUG] send_messages() exiting.")
            return

        else:
            msg = Message(OPCODE_MESSAGE, user_input)

        writer.write(msg.encode())
        await writer.drain()
        print(f"[DEBUG] Sent message: Opcode={msg.opcode}, Payload={msg.payload}")

async def receive_messages(reader):
    """
    Listens for incoming messages from the server and prints them.
    """
    print("[DEBUG] receive_messages() function started and waiting for server messages...")  # ✅ Confirm function start

    # Check if reader is properly assigned a transport

    print("[DEBUG] Entering message listening loop...")  # 🔥 Ensure we reach the while-loop
    loop_counter = 0  # ✅ Track the number of times this loop runs

    while True:
        try:
            print("[DEBUG] Waiting for incoming messages...")  # ✅ Ensure loop is running
            loop_counter += 1
            print(f"[DEBUG] Loop iteration {loop_counter} - Checking for server messages...")  # ✅ Loop runs?

            # ✅ Check if the reader is ready to receive data
            # if reader.at_eof():
            #     print("[DEBUG] Reader is at EOF. Server may have closed the connection.")
            #     break

            # ✅ Try reading raw bytes
            raw_data = await reader.read(1024)  # 🔥 Use regular `read` instead of `readexactly`
            if not raw_data:
                print("[DEBUG] No data received. Server might have closed the connection.")
                break  

            print(f"[DEBUG] Raw data received (Iteration {loop_counter}): {raw_data}")  # ✅ Check raw bytes

            print(f"[DEBUG] Raw Data Before Decoding: {raw_data}")  # ✅ Print raw bytes

            # Decode the message
            msg = Message.decode(raw_data)
            print(f"[DEBUG] Decoded Message: Opcode={msg.opcode}, Payload={msg.payload}")  # ✅ Print decoded message


            # raw_data = await reader.readexactly(8)  # Read opcode + payload size
            # opcode, length = struct.unpack('!II', raw_data)
            # payload_data = await reader.readexactly(length)  # Read the exact payload

            # msg = Message.decode(raw_data + payload_data)
            # print(f"[DEBUG] Fully Decoded Message: Opcode={msg.opcode}, Payload={msg.payload}")


        except asyncio.IncompleteReadError:
            print("[ERROR] Incomplete message received. Connection may be unstable.")
            break
        except asyncio.CancelledError:
            print("[DEBUG] receive_messages() cancelled.")
            break
        except Exception as e:
            print(f"[ERROR] Exception in receive_messages(): {e}")
            traceback.print_exc()

    print("[DEBUG] receive_messages() exiting.")  # ✅ Confirm function exit







if __name__ == "__main__":
    asyncio.run(chat_client())
