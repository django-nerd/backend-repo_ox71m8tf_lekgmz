import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User as UserSchema, Conversation as ConversationSchema, Message as MessageSchema

app = FastAPI(title="Messaging Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_id(doc):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d and isinstance(d["_id"], ObjectId):
        d["id"] = str(d["_id"])
        del d["_id"]
    # Convert nested ObjectIds if present
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
        elif isinstance(v, list):
            d[k] = [str(x) if isinstance(x, ObjectId) else x for x in v]
    return d


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# -------------------- Users --------------------
class CreateUserRequest(BaseModel):
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


@app.post("/users")
def create_user(payload: CreateUserRequest):
    # Ensure username uniqueness
    existing = db.user.find_one({"username": payload.username})
    if existing:
        return serialize_id(existing)

    user = UserSchema(
        username=payload.username,
        display_name=payload.display_name or payload.username,
        avatar_url=payload.avatar_url,
        status="online",
    )
    user_id = create_document("user", user)
    created = db.user.find_one({"_id": ObjectId(user_id)})
    return serialize_id(created)


@app.get("/users")
def list_users(q: Optional[str] = Query(None, description="Search by username or display name")):
    filter_dict = {}
    if q:
        filter_dict = {"$or": [
            {"username": {"$regex": q, "$options": "i"}},
            {"display_name": {"$regex": q, "$options": "i"}},
        ]}
    users = db.user.find(filter_dict).limit(50)
    return [serialize_id(u) for u in users]


# -------------------- Conversations --------------------
class CreateConversationRequest(BaseModel):
    type: str = "direct"  # direct or group
    name: Optional[str] = None
    participant_ids: List[str]


@app.post("/conversations")
def create_conversation(payload: CreateConversationRequest):
    # For direct chats, check if one already exists between the two users
    if payload.type == "direct" and len(payload.participant_ids) == 2:
        existing = db.conversation.find_one({
            "type": "direct",
            "participant_ids": {"$all": payload.participant_ids, "$size": 2}
        })
        if existing:
            return serialize_id(existing)

    convo = ConversationSchema(
        name=payload.name,
        type=payload.type,
        participant_ids=payload.participant_ids,
        last_message_preview=None,
    )
    convo_id = create_document("conversation", convo)
    created = db.conversation.find_one({"_id": ObjectId(convo_id)})
    return serialize_id(created)


@app.get("/conversations")
def list_conversations(user_id: str = Query(...)):
    convos = db.conversation.find({"participant_ids": user_id}).sort("updated_at", -1)
    return [serialize_id(c) for c in convos]


# -------------------- Messages --------------------
class CreateMessageRequest(BaseModel):
    conversation_id: str
    sender_id: str
    content: str
    type: str = "text"


@app.post("/messages")
def send_message(payload: CreateMessageRequest):
    # Validate conversation exists and sender is a participant
    convo = db.conversation.find_one({"_id": ObjectId(payload.conversation_id)})
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if payload.sender_id not in convo.get("participant_ids", []):
        raise HTTPException(status_code=403, detail="Sender is not a participant of this conversation")

    msg = MessageSchema(
        conversation_id=payload.conversation_id,
        sender_id=payload.sender_id,
        content=payload.content,
        type=payload.type,
        is_edited=False,
        is_deleted=False,
    )
    message_id = create_document("message", msg)

    # Update conversation preview and activity timestamps
    db.conversation.update_one(
        {"_id": ObjectId(payload.conversation_id)},
        {
            "$set": {
                "last_message_preview": payload.content,
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )

    created = db.message.find_one({"_id": ObjectId(message_id)})
    return serialize_id(created)


@app.get("/messages")
def list_messages(conversation_id: str, limit: int = 50):
    msgs = db.message.find({"conversation_id": conversation_id}).sort("created_at", -1).limit(limit)
    result = [serialize_id(m) for m in msgs]
    result.reverse()  # return oldest -> newest
    return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
