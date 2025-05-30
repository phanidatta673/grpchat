import os
import sys
import grpc
import threading
import time
import logging
from concurrent import futures
from collections import defaultdict, deque

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pbs'))

import chat_pb2
import chat_pb2_grpc

class ChatServer(chat_pb2_grpc.ChatServiceServicer):
    def __init__(self):
        self.clients = {}  # user_id -> client_info
        self.rooms = defaultdict(set)  # room_id -> set of user_ids
        self.message_history = defaultdict(lambda: deque(maxlen=50))  # room_id -> recent messages
        self.lock = threading.RLock()
        logger.info("ChatServer initialized with message history")
    
    def JoinChat(self, request_iterator, context):
        user_id = None
        username = None
        room_id = None

        try:
            # Get the first message to identify the user
            first_message = next(request_iterator)
            user_id = first_message.user_id
            username = first_message.username
            room_id = first_message.room_id or "general"

            logger.info(f"User {username} ({user_id}) joining room '{room_id}'")

            # Queue for this specific client
            import queue
            client_queue = queue.Queue()

            # Register client with their specific room
            with self.lock:
                self.clients[user_id] = {
                    'queue': client_queue,
                    'username': username,
                    'room_id': room_id,  # Store the room this client is in
                    'context': context
                }
                
                # Add to the specific room
                self.rooms[room_id].add(user_id)
                logger.info(f"Room '{room_id}' now has users: {[self.clients[uid]['username'] for uid in self.rooms[room_id]]}")
            
            # Send recent message history to the new user
            self.send_message_history(user_id, room_id)
            
            # Send join notification to room (but not to the joining user)
            join_message = chat_pb2.ChatMessage(
                user_id="SYSTEM",
                username="System",
                message=f"{username} joined the room",
                timestamp=int(time.time() * 1000),
                type=chat_pb2.MessageType.JOIN,
                room_id=room_id
            )
            
            # Store join message in history
            with self.lock:
                self.message_history[room_id].append(join_message)
            
            # Broadcast to others in the same room only
            self.broadcast_to_room(room_id, join_message, exclude_user=user_id)

            # Generator for outgoing messages to this specific client
            def send_messages():
                try:
                    while True:
                        try:
                            message = client_queue.get(timeout=1.0)
                            if message is None:
                                break
                            # Only send messages meant for this client's room
                            if message.room_id == room_id or message.user_id == "SYSTEM":
                                yield message
                        except queue.Empty:
                            if context.is_active():
                                continue
                            else:
                                break
                except Exception as e:
                    logger.error(f"Error in send_messages for {username}: {e}")

            response_generator = send_messages()

            # Handle the first message if it's a text message
            if first_message.type == chat_pb2.MessageType.TEXT:
                first_message.timestamp = int(time.time() * 1000)
                with self.lock:
                    self.message_history[room_id].append(first_message)
                self.broadcast_to_room(room_id, first_message)
            
            # Process incoming messages from this client
            for message in request_iterator:
                # Ensure message has the correct room_id
                message.room_id = room_id
                message.timestamp = int(time.time() * 1000)
                
                if message.type == chat_pb2.MessageType.TEXT:
                    logger.info(f"[{room_id}] {message.username}: {message.message}")
                    
                    # Store in history
                    with self.lock:
                        self.message_history[room_id].append(message)
                    
                    # Broadcast only to users in the same room
                    self.broadcast_to_room(room_id, message)
                    
                elif message.type == chat_pb2.MessageType.LEAVE:
                    break
            
            return response_generator
    
        except StopIteration:
            logger.warning("Client disconnected without sending initial message")
        except Exception as e:
            logger.error(f"Error handling client {username}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup_client(user_id, username, room_id)
    
    def send_message_history(self, user_id, room_id):
        """Send recent message history to a newly joined user"""
        with self.lock:
            if room_id in self.message_history:
                history_messages = list(self.message_history[room_id])
                if history_messages:
                    # Send a system message indicating history
                    history_header = chat_pb2.ChatMessage(
                        user_id="SYSTEM",
                        username="System",
                        message=f"--- Recent messages in {room_id} ---",
                        timestamp=int(time.time() * 1000),
                        type=chat_pb2.MessageType.SYSTEM,
                        room_id=room_id
                    )
                    self.clients[user_id]['queue'].put(history_header)
                    
                    # Send each historical message
                    for msg in history_messages:
                        if msg.type in [chat_pb2.MessageType.TEXT, chat_pb2.MessageType.JOIN, chat_pb2.MessageType.LEAVE]:
                            self.clients[user_id]['queue'].put(msg)
                    
                    # Send separator
                    history_footer = chat_pb2.ChatMessage(
                        user_id="SYSTEM",
                        username="System", 
                        message="--- End of history ---",
                        timestamp=int(time.time() * 1000),
                        type=chat_pb2.MessageType.SYSTEM,
                        room_id=room_id
                    )
                    self.clients[user_id]['queue'].put(history_footer)

    def broadcast_to_room(self, target_room_id, message, exclude_user=None):
        """Broadcast message ONLY to users in the specified room"""
        with self.lock:
            if target_room_id not in self.rooms:
                logger.warning(f"Attempted to broadcast to non-existent room: {target_room_id}")
                return

            # Get users only from the target room
            room_users = self.rooms[target_room_id].copy()
            recipients = [uid for uid in room_users if uid != exclude_user]
            
            logger.info(f"Broadcasting to room '{target_room_id}': {len(recipients)} recipients")

            for client_user_id in recipients:
                if client_user_id in self.clients:
                    client_info = self.clients[client_user_id]
                    
                    # Double-check the client is in the correct room
                    if client_info['room_id'] == target_room_id:
                        try:
                            client_info['queue'].put(message)
                        except Exception as e:
                            logger.error(f"Error sending to {client_user_id}: {e}")
                            self.cleanup_client(client_user_id, None, target_room_id)

    def cleanup_client(self, user_id, username, room_id):
        """Cleanup client data when they disconnect"""
        if not user_id:
            return
        
        with self.lock:
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
                logger.info(f"Removed {username} ({user_id}) from clients")

            # Remove from room
            if room_id in self.rooms and user_id in self.rooms[room_id]:
                self.rooms[room_id].remove(user_id)
                
                # Send leave notification
                if username:
                    leave_message = chat_pb2.ChatMessage(
                        user_id="SYSTEM",
                        username="System",
                        message=f"{username} left the room",
                        timestamp=int(time.time() * 1000),
                        type=chat_pb2.MessageType.LEAVE,
                        room_id=room_id
                    )
                    
                    # Store in history
                    self.message_history[room_id].append(leave_message)
                    
                    # Broadcast to remaining users in the room
                    self.broadcast_to_room(room_id, leave_message)

                # Clean up empty rooms (but keep message history)
                if not self.rooms[room_id]:
                    logger.info(f"Room '{room_id}' is now empty (keeping message history)")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    chat_server = ChatServer()
    chat_pb2_grpc.add_ChatServiceServicer_to_server(chat_server, server)

    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)

    logger.info(f"Enhanced gRPC Chat Server listening on {listen_addr}")
    logger.info("Features: Room isolation, Message history, Better logging")
    server.start()

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop(0)

if __name__ == '__main__':
    serve()