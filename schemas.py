"""
Database Schemas for Messaging Platform

Each Pydantic model represents a MongoDB collection.
Collection name is the lowercase class name by default.

Collections:
- user: registered users
- conversation: direct or group conversations
- message: messages linked to conversations
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user"
    """
    username: str = Field(..., description="Unique username")
    display_name: str = Field(..., description="Name shown in chat")
    avatar_url: Optional[str] = Field(None, description="Profile image URL")
    status: str = Field("online", description="online, offline, away")

class Conversation(BaseModel):
    """
    Conversations collection schema
    Collection name: "conversation"
    """
    name: Optional[str] = Field(None, description="Group name if group chat")
    type: str = Field("direct", description="direct or group")
    participant_ids: List[str] = Field(..., description="List of user id strings")
    last_message_preview: Optional[str] = Field(None, description="Preview text")

class Message(BaseModel):
    """
    Messages collection schema
    Collection name: "message"
    """
    conversation_id: str = Field(..., description="Conversation id string")
    sender_id: str = Field(..., description="User id string of sender")
    content: str = Field(..., description="Message text content")
    type: str = Field("text", description="text, image, file, system")
    is_edited: bool = Field(False)
    is_deleted: bool = Field(False)
