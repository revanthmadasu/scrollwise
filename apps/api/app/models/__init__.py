"""ORM models.

API-owned tables (Alembic-managed): User, UserInterest, UserPrompt,
PostReaction, UserPostView, UserTopicProgress, TestAttempt.

Read-only mappings of the content-generator's contract tables (NOT
Alembic-managed): Post, Curriculum.
"""

from app.models.contract import Curriculum, Post
from app.models.interest import UserInterest
from app.models.progress import TestAttempt, UserPostView, UserTopicProgress
from app.models.prompt import PromptStatus, UserPrompt
from app.models.reaction import PostReaction, ReactionType
from app.models.user import User

__all__ = [
    "User",
    "UserInterest",
    "UserPrompt",
    "PromptStatus",
    "PostReaction",
    "ReactionType",
    "UserPostView",
    "UserTopicProgress",
    "TestAttempt",
    "Post",
    "Curriculum",
]
