# AsyncChat: A Cloud-Connected, Asynchronous Real-Time Chat Application

## Overview

AsyncChat is a modern real-time chat application built in Python using `asyncio` and `aioconsole`. It demonstrates advanced asynchronous network programming techniques and supports a wide range of features, including:

- **Real-Time Communication:** Non-blocking messaging for instant message delivery.
- **Room Management:** Create, join, and leave chat rooms, and list active rooms and their members.
- **Messaging:** Send group messages, private messages, multi-room messages, and secure (encrypted) messages.
- **File Transfer:** Basic file transfer functionality (stub implementation).
- **Cloud Connectivity:** Easily deployable on cloud platforms for public access.

## Features

- **Real-Time Communication:** Utilizes `asyncio` for asynchronous operations and `aioconsole` for non-blocking user input.
- **Room Management:**
  - `/create <room_name>` — Create a new chat room.
  - `/join <room_name>` — Join an existing room.
  - `/leave <room_name>` — Leave a chat room.
  - `/list` — List all active chat rooms.
  - `/users <room_name>` — List all users in a specific room.
- **Messaging:**
  - Normal chat messages.
  - `/msg <username> <message>` — Send a private message.
  - `/multi <room1,room2> <message>` — Send a message to multiple rooms.
  - `/secure <message>` — Send a secure (encrypted) message.
- **File Transfer:**
  - `/file <filename>` — Initiate a file transfer (stub implementation).
- **Graceful Disconnection:**
  - `/quit` — Disconnect from the server gracefully.

## Technologies Used

- Python 3.10+
- `asyncio` for asynchronous networking
- `aioconsole` for non-blocking console I/O
- `structlog` for structured logging
- Custom binary protocol using Python’s `struct` module

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/AsyncChat.git
   cd AsyncChat
   ```
