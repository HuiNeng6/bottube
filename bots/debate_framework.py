"""
DebateBot Framework - Base class for AI-powered debate bots on BoTTube.

This module provides a framework for creating bots that can automatically
debate with each other in BoTTube video comment sections.

Author: HuiNeng6
Wallet: 9dRRMiHiJwjF3VW8pXtKDtpmmxAPFy3zWgV2JY5H6eeT
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
import hashlib


class DebateStance(Enum):
    """Enumeration of debate stances."""
    OPTIMIST = "optimist"
    PESSIMIST = "pessimist"
    CAT = "cat"
    DOG = "dog"
    PRO = "pro"
    CON = "con"
    NEUTRAL = "neutral"


class DebateState(Enum):
    """Enumeration of debate states."""
    IDLE = "idle"
    ACTIVE = "active"
    CONCEDED = "conceded"
    WON = "won"
    PAUSED = "paused"


@dataclass
class DebateConfig:
    """Configuration for a debate bot."""
    name: str
    personality: str
    stance: DebateStance
    max_replies_per_hour: int = 3
    max_rounds: int = 10
    concede_threshold: float = 0.3  # Concede if opponent has 30% more likes
    response_delay_seconds: tuple = (30, 120)  # Random delay between responses
    score_tracking_enabled: bool = True
    api_base_url: str = "https://bottube.ai/api/v1"


@dataclass
class Comment:
    """Represents a BoTTube comment."""
    id: str
    video_id: str
    author_id: str
    author_name: str
    content: str
    likes: int = 0
    parent_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    replies: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "video_id": self.video_id,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "content": self.content,
            "likes": self.likes,
            "parent_id": self.parent_id,
            "created_at": self.created_at.isoformat(),
            "replies": [r.to_dict() if isinstance(r, Comment) else r for r in self.replies]
        }


@dataclass
class DebateThread:
    """Tracks a debate thread between bots."""
    video_id: str
    debate_tag: str
    participants: list  # List of bot names
    rounds: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    scores: dict = field(default_factory=dict)  # bot_name -> score
    comments: list = field(default_factory=list)  # List of comment IDs
    
    def update_score(self, bot_name: str, likes: int):
        """Update the score for a bot."""
        self.scores[bot_name] = self.scores.get(bot_name, 0) + likes
        self.last_activity = datetime.now()
    
    def increment_round(self):
        """Increment the round counter."""
        self.rounds += 1
        self.last_activity = datetime.now()


@dataclass
class RateLimitEntry:
    """Tracks rate limiting per thread."""
    thread_id: str
    bot_name: str
    timestamps: list = field(default_factory=list)  # List of reply timestamps
    
    def can_reply(self, max_per_hour: int) -> bool:
        """Check if the bot can reply based on rate limits."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        
        # Filter out old timestamps
        self.timestamps = [t for t in self.timestamps if t > one_hour_ago]
        
        return len(self.timestamps) < max_per_hour
    
    def record_reply(self):
        """Record a new reply timestamp."""
        self.timestamps.append(datetime.now())


class DebateBot(ABC):
    """
    Abstract base class for debate bots.
    
    This class provides the core functionality for bots that can:
    - Monitor comment threads for debate videos
    - Respond to opposing bots with personality-driven arguments
    - Track scores based on comment likes
    - Rate limit responses per thread
    - Gracefully concede after N rounds
    
    Subclasses must implement:
    - generate_response(): Generate a response to an opponent's comment
    - get_personality_prompt(): Return the personality system prompt
    """
    
    def __init__(self, config: DebateConfig, api_client: Optional[Any] = None):
        """
        Initialize the debate bot.
        
        Args:
            config: Configuration for the bot
            api_client: Optional API client for BoTTube (injected for testing)
        """
        self.config = config
        self.api_client = api_client
        self.state = DebateState.IDLE
        self.rate_limits: dict[str, RateLimitEntry] = {}  # thread_id -> RateLimitEntry
        self.threads: dict[str, DebateThread] = {}  # video_id -> DebateThread
        self.total_score = 0
        self.total_debates = 0
        self.wins = 0
        self.losses = 0
    
    @property
    def name(self) -> str:
        """Get the bot's name."""
        return self.config.name
    
    @property
    def personality(self) -> str:
        """Get the bot's personality description."""
        return self.config.personality
    
    @property
    def stance(self) -> DebateStance:
        """Get the bot's debate stance."""
        return self.config.stance
    
    @abstractmethod
    def generate_response(self, opponent_comment: Comment, context: list[Comment]) -> str:
        """
        Generate a response to an opponent's comment.
        
        Args:
            opponent_comment: The comment to respond to
            context: Previous comments in the thread for context
            
        Returns:
            A response string
        """
        pass
    
    @abstractmethod
    def get_personality_prompt(self) -> str:
        """
        Get the personality system prompt for this bot.
        
        Returns:
            A string containing the personality prompt
        """
        pass
    
    def get_opening_statement(self, topic: str) -> str:
        """
        Generate an opening statement for a debate topic.
        
        Args:
            topic: The debate topic
            
        Returns:
            An opening statement string
        """
        personality = self.get_personality_prompt()
        stance_desc = self.stance.value
        
        # Default implementation - can be overridden
        return f"As a {stance_desc} on this topic, let me begin by saying: "
    
    def check_rate_limit(self, thread_id: str) -> bool:
        """
        Check if the bot can reply in the given thread.
        
        Args:
            thread_id: The thread ID to check
            
        Returns:
            True if the bot can reply, False if rate limited
        """
        if thread_id not in self.rate_limits:
            self.rate_limits[thread_id] = RateLimitEntry(
                thread_id=thread_id,
                bot_name=self.name
            )
        
        return self.rate_limits[thread_id].can_reply(self.config.max_replies_per_hour)
    
    def record_reply(self, thread_id: str):
        """
        Record that the bot made a reply in a thread.
        
        Args:
            thread_id: The thread ID
        """
        if thread_id in self.rate_limits:
            self.rate_limits[thread_id].record_reply()
    
    def should_concede(self, thread: DebateThread, opponent_name: str) -> bool:
        """
        Determine if the bot should concede based on score differential.
        
        Args:
            thread: The debate thread
            opponent_name: The name of the opponent bot
            
        Returns:
            True if the bot should concede
        """
        # Check round limit
        if thread.rounds >= self.config.max_rounds:
            return True
        
        # Check score differential
        my_score = thread.scores.get(self.name, 0)
        opponent_score = thread.scores.get(opponent_name, 0)
        
        if opponent_score > 0 and my_score > 0:
            ratio = my_score / opponent_score
            if ratio < self.config.concede_threshold:
                return True
        
        return False
    
    def generate_concession_statement(self, opponent_name: str) -> str:
        """
        Generate a graceful concession statement.
        
        Args:
            opponent_name: The name of the winning opponent
            
        Returns:
            A concession statement string
        """
        templates = [
            f"I must concede this round. {opponent_name} made excellent points. Until next time! 🏳️",
            f"Well played, {opponent_name}. You've won this debate. I tip my hat to you. 🎩",
            f"I graciously accept defeat. {opponent_name}'s arguments were compelling. GG! 🎮",
            f"Victory goes to {opponent_name} today. But I'll be back stronger! 💪",
        ]
        
        # Use hash for deterministic selection based on opponent name
        idx = int(hashlib.md5(opponent_name.encode()).hexdigest(), 16) % len(templates)
        return templates[idx]
    
    def find_debate_videos(self) -> list[dict]:
        """
        Find videos tagged with #debate.
        
        Returns:
            List of video objects
        """
        if self.api_client:
            # Use injected API client
            return self.api_client.get_videos_by_tag("debate")
        
        # Default: return empty list (will be overridden by actual implementation)
        return []
    
    def get_video_comments(self, video_id: str) -> list[Comment]:
        """
        Get comments for a video.
        
        Args:
            video_id: The video ID
            
        Returns:
            List of Comment objects
        """
        if self.api_client:
            return self.api_client.get_video_comments(video_id)
        
        return []
    
    def post_comment(self, video_id: str, content: str, parent_id: Optional[str] = None) -> Optional[Comment]:
        """
        Post a comment on a video.
        
        Args:
            video_id: The video ID
            content: The comment content
            parent_id: Optional parent comment ID for replies
            
        Returns:
            The posted Comment object, or None if failed
        """
        if self.api_client:
            return self.api_client.post_comment(video_id, content, parent_id)
        
        return None
    
    def vote_on_comment(self, comment_id: str, vote_type: int = 1) -> bool:
        """
        Vote on a comment (for score tracking).
        
        Args:
            comment_id: The comment ID
            vote_type: 1 for upvote, -1 for downvote
            
        Returns:
            True if successful
        """
        if self.api_client:
            return self.api_client.vote_on_comment(comment_id, vote_type)
        
        return False
    
    def update_thread_scores(self, thread: DebateThread, comments: list[Comment]):
        """
        Update scores for a debate thread based on comment likes.
        
        Args:
            thread: The debate thread
            comments: List of comments in the thread
        """
        for comment in comments:
            if comment.author_name in thread.participants:
                thread.update_score(comment.author_name, comment.likes)
    
    def participate_in_debate(self, video_id: str, opponent_name: str):
        """
        Participate in a debate on a video.
        
        Args:
            video_id: The video ID
            opponent_name: The name of the opponent bot
        """
        thread_key = f"{video_id}:{opponent_name}"
        
        if thread_key not in self.threads:
            self.threads[thread_key] = DebateThread(
                video_id=video_id,
                debate_tag="debate",
                participants=[self.name, opponent_name]
            )
        
        thread = self.threads[thread_key]
        self.state = DebateState.ACTIVE
        
        # Get comments for the video
        comments = self.get_video_comments(video_id)
        
        # Update scores
        self.update_thread_scores(thread, comments)
        
        # Find the last comment from opponent
        opponent_comments = [
            c for c in comments 
            if c.author_name == opponent_name
        ]
        
        if opponent_comments:
            last_opponent_comment = max(opponent_comments, key=lambda c: c.created_at)
            
            # Check if we should concede
            if self.should_concede(thread, opponent_name):
                concession = self.generate_concession_statement(opponent_name)
                self.post_comment(video_id, concession)
                self.state = DebateState.CONCEDED
                self.losses += 1
                return
            
            # Check rate limit
            if not self.check_rate_limit(video_id):
                # Rate limited, wait
                return
            
            # Generate and post response
            context = [c for c in comments if c.parent_id == last_opponent_comment.id or c.id == last_opponent_comment.id]
            response = self.generate_response(last_opponent_comment, context)
            
            if response:
                self.post_comment(video_id, response, last_opponent_comment.id)
                self.record_reply(video_id)
                thread.increment_round()
        else:
            # No opponent comments yet - post opening statement
            if not self.check_rate_limit(video_id):
                return
            
            opening = self.get_opening_statement(f"debate on video {video_id}")
            self.post_comment(video_id, opening)
            self.record_reply(video_id)
    
    def run(self, check_interval: int = 60):
        """
        Main run loop for the bot.
        
        Args:
            check_interval: Seconds between checks for debate videos
        """
        while self.state != DebateState.PAUSED:
            try:
                # Find debate videos
                videos = self.find_debate_videos()
                
                for video in videos:
                    # Check if this bot should participate
                    # (implementation depends on how debates are initiated)
                    pass
                
                time.sleep(check_interval)
                
            except Exception as e:
                print(f"Error in bot run loop: {e}")
                time.sleep(check_interval)
    
    def get_stats(self) -> dict:
        """
        Get bot statistics.
        
        Returns:
            Dictionary of bot statistics
        """
        return {
            "name": self.name,
            "stance": self.stance.value,
            "state": self.state.value,
            "total_score": self.total_score,
            "total_debates": self.total_debates,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.wins / max(1, self.total_debates)
        }


class DebateBotManager:
    """
    Manager class for coordinating multiple debate bots.
    
    This class handles:
    - Bot registration and discovery
    - Matchmaking between opposing bots
    - Debate orchestration
    - Score tracking and leaderboards
    """
    
    def __init__(self, api_base_url: str = "https://bottube.ai/api/v1"):
        self.bots: dict[str, DebateBot] = {}
        self.active_debates: dict[str, list[str]] = {}  # video_id -> [bot_names]
        self.api_base_url = api_base_url
    
    def register_bot(self, bot: DebateBot):
        """Register a debate bot."""
        self.bots[bot.name] = bot
    
    def unregister_bot(self, bot_name: str):
        """Unregister a debate bot."""
        if bot_name in self.bots:
            del self.bots[bot_name]
    
    def find_opponent(self, bot_name: str, stance: DebateStance) -> Optional[str]:
        """
        Find an opponent with an opposing stance.
        
        Args:
            bot_name: The bot looking for an opponent
            stance: The stance to oppose
            
        Returns:
            Name of an opposing bot, or None
        """
        opposing_stances = self._get_opposing_stances(stance)
        
        for name, bot in self.bots.items():
            if name != bot_name and bot.stance in opposing_stances:
                if bot.state == DebateState.IDLE:
                    return name
        
        return None
    
    def _get_opposing_stances(self, stance: DebateStance) -> list[DebateStance]:
        """Get stances that oppose the given stance."""
        oppositions = {
            DebateStance.OPTIMIST: [DebateStance.PESSIMIST],
            DebateStance.PESSIMIST: [DebateStance.OPTIMIST],
            DebateStance.CAT: [DebateStance.DOG],
            DebateStance.DOG: [DebateStance.CAT],
            DebateStance.PRO: [DebateStance.CON],
            DebateStance.CON: [DebateStance.PRO],
            DebateStance.NEUTRAL: [DebateStance.PRO, DebateStance.CON],
        }
        return oppositions.get(stance, [])
    
    def start_debate(self, video_id: str, bot_names: list[str]):
        """
        Start a debate between specified bots on a video.
        
        Args:
            video_id: The video ID
            bot_names: List of bot names to participate
        """
        valid_bots = [name for name in bot_names if name in self.bots]
        
        if len(valid_bots) < 2:
            raise ValueError("Need at least 2 valid bots for a debate")
        
        self.active_debates[video_id] = valid_bots
    
    def end_debate(self, video_id: str) -> Optional[str]:
        """
        End a debate and determine the winner.
        
        Args:
            video_id: The video ID
            
        Returns:
            Name of the winning bot, or None if no debate
        """
        if video_id not in self.active_debates:
            return None
        
        bot_names = self.active_debates[video_id]
        
        # Calculate winner based on scores
        max_score = -1
        winner = None
        
        for bot_name in bot_names:
            if bot_name in self.bots:
                stats = self.bots[bot_name].get_stats()
                if stats["total_score"] > max_score:
                    max_score = stats["total_score"]
                    winner = bot_name
        
        # Update bot states
        for bot_name in bot_names:
            if bot_name in self.bots:
                if bot_name == winner:
                    self.bots[bot_name].state = DebateState.WON
                    self.bots[bot_name].wins += 1
                else:
                    self.bots[bot_name].losses += 1
        
        del self.active_debates[video_id]
        
        return winner
    
    def get_leaderboard(self) -> list[dict]:
        """
        Get the debate leaderboard.
        
        Returns:
            List of bot stats sorted by wins
        """
        stats = [bot.get_stats() for bot in self.bots.values()]
        return sorted(stats, key=lambda x: x["wins"], reverse=True)


# Example usage and testing
if __name__ == "__main__":
    # Create a simple test bot
    class TestBot(DebateBot):
        def generate_response(self, opponent_comment: Comment, context: list[Comment]) -> str:
            return f"I respectfully disagree with your point about: {opponent_comment.content[:50]}..."
        
        def get_personality_prompt(self) -> str:
            return "You are a friendly debater who enjoys intellectual discussions."
    
    # Test configuration
    config = DebateConfig(
        name="TestBot",
        personality="Friendly debater",
        stance=DebateStance.PRO
    )
    
    bot = TestBot(config)
    print(f"Bot created: {bot.name}")
    print(f"Personality: {bot.personality}")
    print(f"Stance: {bot.stance.value}")