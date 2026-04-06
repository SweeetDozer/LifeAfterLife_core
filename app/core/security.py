import uuid

active_tokens = {}

def create_token(user_id: int):
    token = str(uuid.uuid4())
    active_tokens[token] = user_id
    return token

def get_user_by_token(token: str):
    return active_tokens.get(token)