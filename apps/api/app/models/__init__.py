"""ORM models.

API-owned tables (Alembic-managed): User, InterestCategory, UserInterest,
UserPrompt, PostReaction, UserPostView, UserTopicProgress, TestAttempt.

Read-only mappings of the content-generator's contract tables (NOT
Alembic-managed): Post, Curriculum.
"""

from app.models.category import InterestCategory
from app.models.contract import Curriculum, Post
from app.models.interest import UserInterest
from app.models.progress import TestAttempt, UserPostView, UserTopicProgress
from app.models.prompt import PromptStatus, UserPrompt
from app.models.reaction import PostReaction, ReactionType
from app.models.template import Template, TemplateStatus
from app.models.user import User
from app.models.waitlist import WaitlistEntry

__all__ = [
    "User",
    "InterestCategory",
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
    "WaitlistEntry",
    "Template",
    "TemplateStatus",
]
