"""
BoTTube Debate Bots Package

This package provides a framework for creating AI-powered debate bots
that can automatically debate with each other in BoTTube video comments.

Modules:
    debate_framework: Base classes and utilities for creating debate bots
    retro_vs_modern: Example implementation with RetroBot and ModernBot

Example Usage:
    from bots import RetroBot, ModernBot, DebateBotManager
    
    # Create a debate pair
    retro = RetroBot()
    modern = ModernBot()
    
    # Create a manager to coordinate debates
    manager = DebateBotManager()
    manager.register_bot(retro)
    manager.register_bot(modern)
    
    # Start a debate on a video
    manager.start_debate("video_id", ["RetroBot", "ModernBot"])
    
Author: HuiNeng6
Wallet: 9dRRMiHiJwjF3VW8pXtKDtpmmxAPFy3zWgV2JY5H6eeT
"""

from .debate_framework import (
    DebateBot,
    DebateBotManager,
    DebateConfig,
    DebateStance,
    DebateState,
    Comment,
    DebateThread,
    RateLimitEntry,
)

from .retro_vs_modern import (
    RetroBot,
    ModernBot,
    create_debate_pair,
    RETRO_BOT_PERSONALITY,
    MODERN_BOT_PERSONALITY,
)

__all__ = [
    # Base classes
    "DebateBot",
    "DebateBotManager",
    "DebateConfig",
    "DebateStance",
    "DebateState",
    "Comment",
    "DebateThread",
    "RateLimitEntry",
    # Example bots
    "RetroBot",
    "ModernBot",
    "create_debate_pair",
    # Personality prompts
    "RETRO_BOT_PERSONALITY",
    "MODERN_BOT_PERSONALITY",
]

__version__ = "1.0.0"
__author__ = "HuiNeng6"
__wallet__ = "9dRRMiHiJwjF3VW8pXtKDtpmmxAPFy3zWgV2JY5H6eeT"