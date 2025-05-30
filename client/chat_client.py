import grpc
import threading
import time
import sys
import os
import uuid

# Add pbs files to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pbs'))

import chat_pb2
import chat_pb2_grpc


class ChatClient:
    def __init__(self, server_address='localhost:50051'):
        self.server_address = server_address
        self.user_id = str(uuid.uuid4())
        self.username = None
        self.room_id = "general"
        self.channel = None
        self.stub = None
        self.stream = None
        self.running = False
        
    def connect(self, username, room_id="general"):
        """Connect to the chat server"""
        self.username = username
        self.room_id = room_id
        
        try:
            # Create gRPC channel
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = chat_pb2_grpc.ChatServiceStub(self.channel)
            
            print(f"[CLIENT] Connecting to {self.server_address} as {username}")
            print(f"[CLIENT] Joining room: {room_id}")
            print("[CLIENT] Type messages and press Enter. Type '/quit' to exit.")
            print("-" * 50)
            
            # Start the bidirectional stream
            self.start_chat()
            
        except Exception as e:
            print(f"[CLIENT] Connection error: {e}")
    
    def start_chat(self):
        """Start the bidirectional streaming chat"""
        self.running = True
        
        def message_generator():
            """Generator for outgoing messages"""
            # Send initial join message
            join_message = chat_pb2.ChatMessage(
                user_id=self.user_id,
                username=self.username,
                message="",
                timestamp=int(time.time() * 1000),
                type=chat_pb2.MessageType.JOIN,
                room_id=self.room_id
            )
            yield join_message
            
            # Handle user input
            while self.running:
                try:
                    user_input = input()
                    
                    if user_input.lower() in ['/quit', '/exit', '/q']:
                        # Send leave message
                        leave_message = chat_pb2.ChatMessage(
                            user_id=self.user_id,
                            username=self.username,
                            message="",
                            timestamp=int(time.time() * 1000),
                            type=chat_pb2.MessageType.LEAVE,
                            room_id=self.room_id
                        )
                        yield leave_message
                        break
                    
                    if user_input.strip():  # Only send non-empty messages
                        message = chat_pb2.ChatMessage(
                            user_id=self.user_id,
                            username=self.username,
                            message=user_input,
                            timestamp=int(time.time() * 1000),
                            type=chat_pb2.MessageType.TEXT,
                            room_id=self.room_id
                        )
                        yield message
                        
                except EOFError:
                    # Handle Ctrl+D
                    break
                except KeyboardInterrupt:
                    # Handle Ctrl+C
                    break
        
        try:
            # Start the bidirectional stream
            self.stream = self.stub.JoinChat(message_generator())
            
            # Handle incoming messages
            for response in self.stream:
                self.handle_incoming_message(response)
                
        except grpc.RpcError as e:
            print(f"[CLIENT] gRPC error: {e}")
        except Exception as e:
            print(f"[CLIENT] Error: {e}")
        finally:
            self.disconnect()
    
    def handle_incoming_message(self, message):
        """Handle incoming messages from server"""
        timestamp = time.strftime('%H:%M:%S', time.localtime(message.timestamp / 1000))
        
        if message.type == chat_pb2.MessageType.TEXT:
            print(f"[{timestamp}] {message.username}: {message.message}")
        elif message.type == chat_pb2.MessageType.JOIN:
            print(f"[{timestamp}] >>> {message.message}")
        elif message.type == chat_pb2.MessageType.LEAVE:
            print(f"[{timestamp}] <<< {message.message}")
        elif message.type == chat_pb2.MessageType.SYSTEM:
            print(f"[{timestamp}] SYSTEM: {message.message}")
    
    def disconnect(self):
        """Disconnect from the server"""
        self.running = False
        if self.channel:
            self.channel.close()
        print("\n[CLIENT] Disconnected from chat server")


def main():
    if len(sys.argv) < 2:
        print("Usage: python chat_client.py <username> [room_id] [server_address]")
        sys.exit(1)
    
    username = sys.argv[1]
    room_id = sys.argv[2] if len(sys.argv) > 2 else "general"
    server_address = sys.argv[3] if len(sys.argv) > 3 else "localhost:50051"
    
    client = ChatClient(server_address)
    
    try:
        client.connect(username, room_id)
    except KeyboardInterrupt:
        print("\n[CLIENT] Interrupted by user")
    except Exception as e:
        print(f"[CLIENT] Unexpected error: {e}")


if __name__ == '__main__':
    main()