# gRPC Bidirectional Streaming Chat Application

A real-time chat application demonstrating gRPC bidirectional streaming with Python. This project showcases how to build a multi-user, multi-room chat system using Protocol Buffers and gRPC streaming capabilities.

## Features

- **Real-time messaging** using gRPC bidirectional streaming
- **Multi-room support** for organized conversations
- **Message history** - new users see recent messages when joining
- **Join/leave notifications** for user activity tracking
- **Thread-safe server** handling multiple concurrent clients
- **Cross-platform compatibility** - works on Windows, macOS, and Linux
- **Protocol Buffer schema** ensuring type safety and compatibility

## Prerequisites

- Python 3.7 or higher
- pip package manager
- Terminal/Command prompt access

## Installation

### 1. Clone or Download the Project

Create the project structure:
```
grpc_chat/
├── protos/
│   └── chat.proto
├── server/
│   └── chat_server.py
├── client/
│   └── chat_client.py
├── pbs/          # Will be created by protoc
├── requirements.txt
└── README.md
```

### 2. Install Dependencies

```bash
cd grpc_chat
pip install -r requirements.txt
```
### 3. Generate gRPC Code

Run this command from the `grpc_chat` directory:

```bash
python -m grpc_tools.protoc \
  -I./protos \
  --python_out=./pbs \
  --grpc_python_out=./pbs \
  ./protos/chat.proto
```

This generates:
- `pbs/chat_pb2.py` - Protocol Buffer message classes
- `pbs/chat_pb2_grpc.py` - gRPC service stubs

## Quick Start

### Step 1: Start the Server

```bash
python server/chat_server.py
```

Expected output:
```
2024-XX-XX XX:XX:XX - INFO - ChatServer initialized with message history
2024-XX-XX XX:XX:XX - INFO - Enhanced gRPC Chat Server listening on [::]:50051
2024-XX-XX XX:XX:XX - INFO - Features: Room isolation, Message history, Better logging
```

### Step 2: Connect Clients

Open new terminal windows and start clients:

**Client 1 (Alice in general room):**
```bash
python client/chat_client.py Alice
```

**Client 2 (Bob in general room):**
```bash
python client/chat_client.py Bob general
```

**Client 3 (Charlie in developers room):**
```bash
python client/chat_client.py Charlie developers
```

### Step 3: Start Chatting!

Type messages and press Enter. You'll see:
- Your messages appear in other clients' terminals
- Join/leave notifications when users connect/disconnect
- Message history when joining rooms with previous activity

## Usage Examples

### Basic Chat Commands

- **Send message**: Type and press Enter
- **Quit**: Type `/quit`, `/exit`, or `/q`
- **Join room**: Specify room when starting client

### Example Chat Session

**Terminal 1 (Server):**
```
2024-01-15 14:30:15 - INFO - User Alice (uuid-1234) joining room 'general'
2024-01-15 14:30:20 - INFO - [general] Alice: Hello everyone!
2024-01-15 14:30:25 - INFO - User Bob (uuid-5678) joining room 'general'
2024-01-15 14:30:30 - INFO - [general] Bob: Hi Alice!
```

**Terminal 2 (Alice):**
```
[CLIENT] Connecting to localhost:50051 as Alice
[CLIENT] Joining room: general
[CLIENT] Type messages and press Enter. Type '/quit' to exit.
--------------------------------------------------
Hello everyone!
[14:30:25] >>> Bob joined the room
[14:30:30] Bob: Hi Alice!
Great to meet you!
```

**Terminal 3 (Bob):**
```
[CLIENT] Connecting to localhost:50051 as Bob
[CLIENT] Joining room: general
[CLIENT] Type messages and press Enter. Type '/quit' to exit.
--------------------------------------------------
[14:30:20] --- Recent messages in general ---
[14:30:15] >>> Alice joined the room
[14:30:20] Alice: Hello everyone!
[14:30:25] --- End of history ---
Hi Alice!
[14:30:35] Alice: Great to meet you!
```

## Project Structure

```
grpc_chat/
├── protos/
│   └── chat.proto              # Protocol Buffer schema definition
├── server/
│   └── chat_server.py          # gRPC server implementation
├── client/
│   └── chat_client.py          # Command-line chat client
├── pbs/                  # Auto-generated gRPC code
│   ├── chat_pb2.py            # Protocol Buffer message classes
│   └── chat_pb2_grpc.py       # gRPC service stubs
├── requirements.txt            # Python dependencies
└── README.md                  # This file
```

## Configuration

### Server Configuration

**Default settings:**
- **Port**: 50051
- **Max workers**: 10 concurrent threads
- **Message history**: 50 messages per room

**To change the port:**
```python
# In chat_server.py
listen_addr = '[::]:8080'  # Change to desired port
```

### Client Configuration

**Command-line arguments:**
```bash
python client/chat_client.py <username> [room_id] [server_address]
```

- `username` (required): Your display name
- `room_id` (optional): Room to join (default: "general")
- `server_address` (optional): Server location (default: "localhost:50051")

**Examples:**
```bash
# Join default room on localhost
python client/chat_client.py Alice

# Join specific room
python client/chat_client.py Bob developers

# Connect to remote server
python client/chat_client.py Charlie general 192.168.1.100:50051
```

## Architecture Overview

### gRPC Service Definition

```protobuf
service ChatService {
  rpc JoinChat(stream ChatMessage) returns (stream ChatMessage);
}
```

### Message Types

- **TEXT**: Regular chat messages
- **JOIN**: User joined notifications
- **LEAVE**: User left notifications  
- **SYSTEM**: Server announcements

### Key Components

1. **ChatServer**: Handles multiple concurrent client streams
2. **Room Management**: Isolates messages by room
3. **Message History**: Stores and replays recent messages
4. **Thread Safety**: Uses locks for concurrent access
5. **Graceful Cleanup**: Proper resource management

## Troubleshooting

### Common Issues

**1. Import Error - Generated Files Not Found**
```
ImportError: No module named 'chat_pb2'
```
**Solution**: Run the protoc command to generate gRPC code:
```bash
python -m grpc_tools.protoc -I./protos --python_out=./pbs --grpc_python_out=./pbs ./protos/chat.proto
```

**2. Connection Refused**
```
grpc._channel._InactiveRpcError: failed to connect to all addresses
```
**Solution**: Ensure the server is running before starting clients.

**3. Messages Appearing in Wrong Rooms**
**Solution**: Check that each client specifies the correct room name.

**4. Port Already in Use**
```
OSError: [Errno 48] Address already in use
```
**Solution**: Kill existing server process or use a different port.

### Debug Mode

Enable detailed logging by setting the log level:
```python
# In chat_server.py
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

### Planned Features

- [ ] **Web interface** via WebSocket gateway
- [ ] **Message persistence** with database storage
- [ ] **User authentication** and authorization
- [ ] **Private messaging** between users
- [ ] **File sharing** capabilities
- [ ] **Message reactions** and rich formatting
- [ ] **Chat moderation** tools
- [ ] **Docker deployment** configuration



## About This Project

This chat application demonstrates the power of gRPC bidirectional streaming for real-time applications. It serves as a foundation for understanding:

- **Protocol Buffer schema design**
- **gRPC service implementation**
- **Streaming communication patterns**
- **Multi-client server architecture**
- **Real-time application challenges**

Perfect for developers learning gRPC or building real-time communication systems!