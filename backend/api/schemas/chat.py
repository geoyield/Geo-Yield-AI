"""
==============================================================================
API SCHEMA: CHAT INPUT PAYLOAD (DTO)
==============================================================================
File: backend/api/schemas/chat.py

Data Transfer Object (DTO) for the conversational chat endpoint.
Defines the strict JSON contract for incoming user messages.
"""

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    # Security: Rejects any JSON payload containing fields other than 'mensaje',
    # preventing injection attempts or malformed requests.
    model_config = ConfigDict(extra="forbid")

    # Cost Defense Strategy: 
    # Validates input length before making expensive/slow network calls to the LLM.
    # Discards empty or accidental keystrokes (min_length=3) at the routing layer 
    # (HTTP 422 Unprocessable Entity) without invoking the business logic.
    mensaje: str = Field(..., min_length=3)