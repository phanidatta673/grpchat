import grpc
import threading
import time
from concurrent import futures
import sys
import os

# Add pbs files to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pbs'))

import chat_pb2
import chat_pb2_grpc


class ChatServer(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self):
        # Store active client streams by user_id
        self.clients = {}
        # Store clients by room_id
        self.rooms = {}
        # Thread lock for thread-safe operations
        self.lock = threading.RLock()
        
    def JoinChat(self, request_iterator, context):
        """Handle bidirectional streaming chat"""
        user_id = None
        username = None
        room_id = None
        
        try:
            # Get the first message to identify the user
            first_message = next(request_iterator)
            user_id = first_message.user_id
            username = first_message.username
            room_id = first_message.room_id or "general"
            
            print(f"[SERVER] {username} ({user_id}) joining room '{room_id}'")
            
            # Create a queue for this client
            import queue
            client_queue = queue.Queue()
            
            # Register client
            with self.lock:
                self.clients[user_id] = {
                    'queue': client_queue,
                    'username': username,
                    'room_id': room_id,
                    'context': context
                }
                
                # Add to room
                if room_id not in self.rooms:
                    self.rooms[room_id] = set()
                self.rooms[room_id].add(user_id)
            
            # Send join notification to room
            join_message = chat_pb2.ChatMessage(
                user_id="SYSTEM",
                username="System",
                message=f"{username} joined the chat",
                timestamp=int(time.time() * 1000),
                type=chat_pb2.MessageType.JOIN,
                room_id=room_id
            )
            self.broadcast_to_room(room_id, join_message, exclude_user=user_id)
            
            # Start thread to handle outgoing messages
            def send_messages():
                try:
                    while True:
                        try:
                            message = client_queue.get(timeout=1.0)
                            if message is None:  # Shutdown signal
                                break
                            yield message
                        except queue.Empty:
                            # Check if client is still connected
                            if context.is_active():
                                continue
                            else:
                                break
                except Exception as e:
                    print(f"[SERVER] Error in send_messages for {username}: {e}")
            
            # Start the response generator
            response_thread = send_messages()
            
            # Handle the first message
            if first_message.type == chat_pb2.MessageType.TEXT:
                self.broadcast_to_room(room_id, first_message)
            
            # Process incoming messages
            for message in request_iterator:
                if message.type == chat_pb2.MessageType.TEXT:
                    print(f"[SERVER] {message.username}: {message.message}")
                    self.broadcast_to_room(room_id, message)
                elif message.type == chat_pb2.MessageType.LEAVE:
                    break
            
            return response_thread
            
        except Exception as e:
            print(f"[SERVER] Error handling client {username}: {e}")
        finally:
            # Cleanup when client disconnects
            self.cleanup_client(user_id, username, room_id)
    
    def broadcast_to_room(self, room_id, message, exclude_user=None):
        """Broadcast message to all clients in a room"""
        with self.lock:
            if room_id not in self.rooms:
                return
            
            for client_user_id in self.rooms[room_id].copy():
                if exclude_user and client_user_id == exclude_user:
                    continue
                
                if client_user_id in self.clients:
                    try:
                        client_info = self.clients[client_user_id]
                        client_info['queue'].put(message)
                    except Exception as e:
                        print(f"[SERVER] Error sending to {client_user_id}: {e}")
                        # Remove problematic client
                        self.cleanup_client(client_user_id, None, room_id)
    
    def cleanup_client(self, user_id, username, room_id):
        """Clean up client data when they disconnect"""
        if not user_id:
            return
            
        with self.lock:
            # Remove from clients
            if user_id in self.clients:
                client_info = self.clients[user_id]
                username = username or client_info.get('username', 'Unknown')
                room_id = room_id or client_info.get('room_id', 'general')
                
                # Signal shutdown to client thread
                try:
                    client_info['queue'].put(None)
                except:
                    pass
                
                del self.clients[user_id]
                print(f"[SERVER] {username} ({user_id}) disconnected")
            
            # Remove from room
            if room_id in self.rooms and user_id in self.rooms[room_id]:
                self.rooms[room_id].remove(user_id)
                
                # Send leave notification
                if username:
                    leave_message = chat_pb2.ChatMessage(
                        user_id="SYSTEM",
                        username="System", 
                        message=f"{username} left the chat",
                        timestamp=int(time.time() * 1000),
                        type=chat_pb2.MessageType.LEAVE,
                        room_id=room_id
                    )
                    self.broadcast_to_room(room_id, leave_message)
                
                # Clean up empty rooms
                if not self.rooms[room_id]:
                    del self.rooms[room_id]


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_server = ChatServer()
    chat_pb2_grpc.add_ChatServiceServicer_to_server(chat_server, server)
    
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    
    print(f"[SERVER] Starting gRPC Chat Server on {listen_addr}")
    server.start()
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        server.stop(0)


if __name__ == '__main__':
    serve()