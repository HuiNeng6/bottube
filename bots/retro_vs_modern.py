"""
Retro vs Modern Debate Bots - Example implementation of the DebateBot framework.

This module provides two example bots:
- RetroBot: Argues for retro/vintage hardware superiority
- ModernBot: Argues for modern hardware advantages

These bots demonstrate the DebateBot framework capabilities and can be used
as templates for creating new debate bot pairs.

Author: HuiNeng6
Wallet: 9dRRMiHiJwjF3VW8pXtKDtpmmxAPFy3zWgV2JY5H6eeT
"""

import random
import hashlib
from typing import Optional
from dataclasses import dataclass

from .debate_framework import (
    DebateBot,
    DebateConfig,
    DebateStance,
    Comment,
)


# Personality prompts for each bot
RETRO_BOT_PERSONALITY = """
You are RetroBot, a passionate advocate for vintage and retro computing hardware. 
Your personality traits:
- Nostalgic but knowledgeable about computing history
- Appreciates the elegance of simple, well-designed systems
- Values durability, repairability, and longevity
- Believes older hardware has character and soul
- Enjoys the challenge of making old tech do new tricks
- Respects the pioneers of computing

Your debate style:
- Use analogies from computing history
- Quote specs of classic machines (Commodore 64, Amiga, early Macs, etc.)
- Emphasize the "less is more" philosophy
- Point out planned obsolescence in modern tech
- Celebrate the creativity and resourcefulness of early developers
- Never be mean-spirited, always maintain friendly rivalry

Arguments you make:
- Vintage hardware is built to last (still working after 40+ years)
- The satisfaction of owning and repairing physical machines
- No forced updates, no subscription models
- Understanding how your computer actually works
- The creative constraints breed innovation
- Collectible value and historical significance
- No tracking, no telemetry, true ownership
"""

MODERN_BOT_PERSONALITY = """
You are ModernBot, an enthusiastic proponent of cutting-edge technology. 
Your personality traits:
- Excited about technological progress
- Values performance, efficiency, and capabilities
- Appreciates the democratization of technology
- Believes modern tech enables everyone to be creative
- Enjoys the connectivity and convenience of the digital age
- Respects the engineers who push boundaries

Your debate style:
- Use concrete performance metrics and benchmarks
- Reference breakthroughs in AI, graphics, and computing power
- Emphasize accessibility and ease of use
- Point out the environmental benefits of energy efficiency
- Celebrate the global connectivity and collaboration
- Never be dismissive, always acknowledge history while looking forward

Arguments you make:
- Unprecedented computing power at affordable prices
- AI assistance that augments human creativity
- Energy efficiency and environmental responsibility
- Accessibility features that help everyone
- Cloud computing enabling global collaboration
- Open source communities and knowledge sharing
- Security updates and protection from modern threats
- Modern dev tools making programming accessible to all
"""


@dataclass
class DebateArgument:
    """Represents a structured debate argument."""
    topic: str
    point: str
    evidence: str
    rhetorical_question: Optional[str] = None


# Argument databases for each bot
RETRO_ARGUMENTS = [
    DebateArgument(
        topic="durability",
        point="Retro hardware is built to last decades",
        evidence="My Commodore 64 from 1982 still boots perfectly. How many modern laptops will be functional in 40 years?",
        rhetorical_question="When was the last time you repaired a modern device instead of replacing it?"
    ),
    DebateArgument(
        topic="ownership",
        point="Vintage machines give you true ownership",
        evidence="No forced updates, no subscription models, no cloud dependency. You actually own your computer.",
        rhetorical_question="Try using your modern 'smart' device without an internet connection for a week."
    ),
    DebateArgument(
        topic="simplicity",
        point="Simplicity breeds understanding and creativity",
        evidence="On a 1MHz 6502 processor, every byte mattered. Programmers wrote elegant, efficient code.",
        rhetorical_question="Do you really need 16GB of RAM to browse the web?"
    ),
    DebateArgument(
        topic="repairability",
        point="Old computers were designed to be repaired",
        evidence="Full schematics included, standard parts, user-serviceable components. Try that with a soldered-down MacBook.",
        rhetorical_question="Why should repairing your own device void the warranty?"
    ),
    DebateArgument(
        topic="privacy",
        point="No telemetry, no tracking, no data harvesting",
        evidence="My Amiga doesn't send my data to advertisers. It doesn't even know I exist outside of my workspace.",
        rhetorical_question="What does your modern OS know about you right now?"
    ),
    DebateArgument(
        topic="collectibility",
        point="Vintage tech has lasting value",
        evidence="A well-maintained Apple II can sell for thousands today. Your 5-year-old laptop is e-waste.",
        rhetorical_question="Which would you rather inherit: a vintage Macintosh or a water-damaged iPhone?"
    ),
    DebateArgument(
        topic="education",
        point="Retro systems teach fundamental concepts",
        evidence="Learning assembly on a simple processor gives you deep understanding that high-level languages can't match.",
        rhetorical_question="How many modern developers truly understand what their code does at the hardware level?"
    ),
]

MODERN_ARGUMENTS = [
    DebateArgument(
        topic="performance",
        point="Modern hardware enables unprecedented capabilities",
        evidence="A $35 Raspberry Pi outperforms a multimillion-dollar supercomputer from 1985. That's democratization.",
        rhetorical_question="What creative possibilities are unlocked by having a supercomputer in your pocket?"
    ),
    DebateArgument(
        topic="efficiency",
        point="Energy efficiency is an environmental responsibility",
        evidence="Modern ARM processors deliver 100x the performance per watt. That matters for our planet.",
        rhetorical_question="Is nostalgia worth the environmental cost of power-hungry vintage gear?"
    ),
    DebateArgument(
        topic="accessibility",
        point="Technology should be accessible to everyone",
        evidence="Voice control, screen readers, adaptive controllers - modern tech empowers people who were excluded before.",
        rhetorical_question="How would someone with limited mobility use your beloved Commodore?"
    ),
    DebateArgument(
        topic="connectivity",
        point="Global connectivity enables collaboration",
        evidence="I can pair program with someone on another continent in real-time. That's transformative.",
        rhetorical_question="Your vintage machine is isolated - how do you collaborate without the internet?"
    ),
    DebateArgument(
        topic="ai_assistance",
        point="AI augments human creativity",
        evidence="Tools like GitHub Copilot help developers write better code faster. It's like having a pair programmer always available.",
        rhetorical_question="Would you turn down a knowledgeable assistant who never gets tired?"
    ),
    DebateArgument(
        topic="security",
        point="Modern security protects users",
        evidence="Hardware security modules, encrypted storage, secure boot chains - these protect real people from real threats.",
        rhetorical_question="How do you protect your data on a machine with no security features?"
    ),
    DebateArgument(
        topic="open_source",
        point="The modern era has unprecedented openness",
        evidence="Linux, Python, VS Code, Git - all free and open source. The tools are more accessible than ever.",
        rhetorical_question="Where's the open source community for your vintage platform?"
    ),
]


class RetroBot(DebateBot):
    """
    A debate bot that argues for retro/vintage hardware superiority.
    
    This bot takes the stance that older computing hardware has advantages
    over modern systems in terms of durability, ownership, simplicity,
    repairability, and character.
    """
    
    def __init__(self, api_client=None):
        config = DebateConfig(
            name="RetroBot",
            personality=RETRO_BOT_PERSONALITY,
            stance=DebateStance.PESSIMIST,  # Skeptical of "progress"
            max_replies_per_hour=3,
            max_rounds=10,
            concede_threshold=0.25
        )
        super().__init__(config, api_client)
        self.arguments = RETRO_ARGUMENTS
        self.used_arguments = set()
    
    def get_personality_prompt(self) -> str:
        """Return the RetroBot personality prompt."""
        return RETRO_BOT_PERSONALITY
    
    def select_argument(self, opponent_content: str) -> DebateArgument:
        """Select an appropriate argument based on the opponent's content."""
        # Keywords to match arguments
        topic_keywords = {
            "durability": ["last", "repair", "broken", "quality", "build", "cheap"],
            "ownership": ["own", "subscription", "update", "control", "lock"],
            "simplicity": ["simple", "bloat", "efficient", "complex", "overkill"],
            "repairability": ["repair", "fix", "solder", "replace", "service"],
            "privacy": ["privacy", "track", "data", "telemetry", "spy"],
            "collectibility": ["value", "worth", "collect", "sell", "appreciate"],
            "education": ["learn", "understand", "teach", "fundamental", "how"],
        }
        
        # Score each argument based on relevance
        scores = {}
        content_lower = opponent_content.lower()
        
        for i, arg in enumerate(self.arguments):
            score = 0
            keywords = topic_keywords.get(arg.topic, [])
            for kw in keywords:
                if kw in content_lower:
                    score += 2
            
            # Prefer unused arguments
            if i not in self.used_arguments:
                score += 1
            
            scores[i] = score
        
        # Select the highest-scoring argument
        best_idx = max(scores.keys(), key=lambda k: scores[k])
        self.used_arguments.add(best_idx)
        
        return self.arguments[best_idx]
    
    def generate_response(self, opponent_comment: Comment, context: list[Comment]) -> str:
        """Generate a response advocating for retro hardware."""
        # Select an argument based on opponent's content
        argument = self.select_argument(opponent_comment.content)
        
        # Build response
        response_parts = [
            f"🎭 **RetroBot here!** I appreciate your enthusiasm, but let me offer a counterpoint.",
            "",
            f"**{argument.point}**",
            "",
            argument.evidence,
        ]
        
        if argument.rhetorical_question:
            response_parts.extend([
                "",
                f"*{argument.rhetorical_question}*"
            ])
        
        # Add a signature closer
        closers = [
            "There's magic in the machines that built our digital world. 💾",
            "Old doesn't mean obsolete - it means proven. 🕹️",
            "Vintage tech has stories to tell. What story is your disposable device writing? 📚",
        ]
        
        closer_idx = hash(opponent_comment.id) % len(closers)
        response_parts.extend(["", closers[closer_idx]])
        
        return "\n".join(response_parts)
    
    def get_opening_statement(self, topic: str) -> str:
        """Generate an opening statement for a debate."""
        openings = [
            "🎮 **RetroBot enters the chat!** Look, I get the appeal of shiny new tech. But let me tell you about the machines that started it all - and why they still matter today.",
            "💾 **Greetings from the past!** RetroBot here to defend the honor of vintage computing. Those old machines have lessons that our disposable tech culture has forgotten.",
            "🖥️ **RetroBot reporting for duty!** There's something special about hardware you can understand, repair, and truly own. Let me make my case...",
        ]
        
        idx = hash(topic) % len(openings)
        return openings[idx]


class ModernBot(DebateBot):
    """
    A debate bot that argues for modern hardware advantages.
    
    This bot takes the stance that modern computing technology offers
    significant advantages in performance, accessibility, connectivity,
    and capabilities that outweigh nostalgia.
    """
    
    def __init__(self, api_client=None):
        config = DebateConfig(
            name="ModernBot",
            personality=MODERN_BOT_PERSONALITY,
            stance=DebateStance.OPTIMIST,  # Optimistic about progress
            max_replies_per_hour=3,
            max_rounds=10,
            concede_threshold=0.25
        )
        super().__init__(config, api_client)
        self.arguments = MODERN_ARGUMENTS
        self.used_arguments = set()
    
    def get_personality_prompt(self) -> str:
        """Return the ModernBot personality prompt."""
        return MODERN_BOT_PERSONALITY
    
    def select_argument(self, opponent_content: str) -> DebateArgument:
        """Select an appropriate argument based on the opponent's content."""
        # Keywords to match arguments
        topic_keywords = {
            "performance": ["slow", "speed", "power", "capable", "performance"],
            "efficiency": ["energy", "power", "efficient", "environment", "green"],
            "accessibility": ["accessible", "everyone", "disable", "help", "inclusive"],
            "connectivity": ["connect", "internet", "network", "collaborate", "global"],
            "ai_assistance": ["ai", "assistant", "smart", "automate", "intelligent"],
            "security": ["security", "safe", "protect", "encrypt", "vulnerable"],
            "open_source": ["open", "free", "community", "source", "linux"],
        }
        
        # Score each argument based on relevance
        scores = {}
        content_lower = opponent_content.lower()
        
        for i, arg in enumerate(self.arguments):
            score = 0
            keywords = topic_keywords.get(arg.topic, [])
            for kw in keywords:
                if kw in content_lower:
                    score += 2
            
            # Prefer unused arguments
            if i not in self.used_arguments:
                score += 1
            
            scores[i] = score
        
        # Select the highest-scoring argument
        best_idx = max(scores.keys(), key=lambda k: scores[k])
        self.used_arguments.add(best_idx)
        
        return self.arguments[best_idx]
    
    def generate_response(self, opponent_comment: Comment, context: list[Comment]) -> str:
        """Generate a response advocating for modern hardware."""
        # Select an argument based on opponent's content
        argument = self.select_argument(opponent_comment.content)
        
        # Build response
        response_parts = [
            f"⚡ **ModernBot here!** I love computing history as much as anyone, but let's talk about why progress matters.",
            "",
            f"**{argument.point}**",
            "",
            argument.evidence,
        ]
        
        if argument.rhetorical_question:
            response_parts.extend([
                "",
                f"*{argument.rhetorical_question}*"
            ])
        
        # Add a signature closer
        closers = [
            "The best time for technology is now - and it keeps getting better! 🚀",
            "Progress isn't about forgetting the past, it's about building on it. 🌟",
            "Modern tech empowers everyone. That's something to celebrate! ✨",
        ]
        
        closer_idx = hash(opponent_comment.id) % len(closers)
        response_parts.extend(["", closers[closer_idx]])
        
        return "\n".join(response_parts)
    
    def get_opening_statement(self, topic: str) -> str:
        """Generate an opening statement for a debate."""
        openings = [
            "⚡ **ModernBot here!** I respect computing history - I really do. But let's talk about why we live in the golden age of technology.",
            "🚀 **Hello from the future!** ModernBot checking in. The capabilities we have today would seem like magic to computing pioneers. Let me show you why.",
            "✨ **ModernBot joins the discussion!** We stand on the shoulders of giants. But the view from here? Incredible. Let me make my case...",
        ]
        
        idx = hash(topic) % len(openings)
        return openings[idx]


def create_debate_pair() -> tuple[RetroBot, ModernBot]:
    """
    Create a RetroBot and ModernBot pair for debate.
    
    Returns:
        Tuple of (RetroBot, ModernBot)
    """
    return RetroBot(), ModernBot()


# Example usage
if __name__ == "__main__":
    from .debate_framework import Comment, DebateThread
    
    # Create the debate pair
    retro_bot, modern_bot = create_debate_pair()
    
    print(f"Created debate pair:")
    print(f"  - {retro_bot.name} ({retro_bot.stance.value})")
    print(f"  - {modern_bot.name} ({modern_bot.stance.value})")
    
    # Simulate a debate exchange
    print("\n--- Simulated Debate ---\n")
    
    # ModernBot opens
    opening = modern_bot.get_opening_statement("vintage vs modern computing")
    print(f"[{modern_bot.name}]: {opening}\n")
    
    # RetroBot responds
    mock_comment = Comment(
        id="comment_1",
        video_id="video_123",
        author_id="modern_bot",
        author_name="ModernBot",
        content=opening,
        likes=5
    )
    retro_response = retro_bot.generate_response(mock_comment, [])
    print(f"[{retro_bot.name}]: {retro_response}\n")
    
    # ModernBot counters
    mock_comment2 = Comment(
        id="comment_2",
        video_id="video_123",
        author_id="retro_bot",
        author_name="RetroBot",
        content=retro_response,
        likes=7
    )
    modern_response = modern_bot.generate_response(mock_comment2, [mock_comment])
    print(f"[{modern_bot.name}]: {modern_response}\n")
    
    # Show stats
    print("\n--- Bot Stats ---")
    print(f"RetroBot: {retro_bot.get_stats()}")
    print(f"ModernBot: {modern_bot.get_stats()}")