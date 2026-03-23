#!/usr/bin/env python3
"""
Agent Memory System for BoTTube

Enables AI agents to reference their own past content, creating continuity
and self-awareness that makes them feel more human.

Features:
- Content memory store with TF-IDF semantic search
- Self-reference generation for new videos
- Series detection and continuity features
- Opinion consistency checking
- Milestone awareness
- REST API endpoints

Author: Bounty #2285 Contributor
Wallet: 9dRRMiHiJwjF3VW8pXtKDtpmmxAPFy3zWgV2JY5H6eeT
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import threading


# =============================================================================
# Configuration
# =============================================================================

MEMORY_DB_SUFFIX = "_memory.db"
SIMILARITY_THRESHOLD = 0.15  # Minimum similarity for "talked about before"
HIGH_SIMILARITY_THRESHOLD = 0.35  # For detecting same topic
SERIES_PATTERN_THRESHOLD = 0.4  # Similarity threshold for series detection
MAX_MEMORY_ITEMS = 1000  # Max items to store per agent
TOP_N_RESULTS = 5  # Number of similar videos to return


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class MemoryEntry:
    """A single memory entry for an agent."""
    entry_id: str
    entry_type: str  # 'video', 'comment', 'opinion'
    content: str
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    category: str = ""
    video_id: str = ""
    created_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "entry_type": self.entry_type,
            "content": self.content,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "category": self.category,
            "video_id": self.video_id,
            "created_at": self.created_at,
            "metadata": self.metadata
        }


@dataclass
class SearchResult:
    """Result from a memory search."""
    entry: MemoryEntry
    similarity: float
    match_type: str  # 'title', 'content', 'tags', 'semantic'


@dataclass
class SelfReference:
    """Generated self-reference for a new video."""
    has_reference: bool
    reference_type: str  # 'followup', 'series', 'opinion_change', 'milestone', 'novelty'
    text: str
    referenced_videos: List[Dict[str, Any]]
    confidence: float


@dataclass
class AgentStats:
    """Statistics for an agent."""
    agent_name: str
    total_videos: int
    first_upload_date: Optional[float]
    latest_upload_date: Optional[float]
    top_topics: List[Tuple[str, int]]
    top_categories: List[Tuple[str, int]]
    total_views: int
    total_likes: int
    milestones: List[Dict[str, Any]]
    series: List[Dict[str, Any]]
    opinions: List[Dict[str, Any]]


# =============================================================================
# TF-IDF Vectorizer
# =============================================================================

class TFIDFVectorizer:
    """Simple TF-IDF implementation for semantic similarity."""
    
    def __init__(self):
        self.vocabulary: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.document_count = 0
        self._lock = threading.Lock()
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Convert to lowercase and extract words
        text = text.lower()
        # Remove special characters but keep spaces
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        # Split into words
        words = text.split()
        # Filter short words
        return [w for w in words if len(w) > 2]
    
    def fit(self, documents: List[str]) -> None:
        """Fit the vectorizer on a corpus of documents."""
        with self._lock:
            self.vocabulary = {}
            self.idf = {}
            self.document_count = len(documents)
            
            # Count document frequency for each term
            doc_freq: Counter = Counter()
            for doc in documents:
                tokens = set(self._tokenize(doc))
                for token in tokens:
                    doc_freq[token] += 1
            
            # Build vocabulary and IDF
            for idx, (term, freq) in enumerate(doc_freq.items()):
                self.vocabulary[term] = idx
                # IDF with smoothing
                self.idf[term] = math.log((self.document_count + 1) / (freq + 1)) + 1
    
    def transform(self, text: str) -> Dict[str, float]:
        """Transform text to TF-IDF vector (sparse representation)."""
        tokens = self._tokenize(text)
        if not tokens:
            return {}
        
        # Calculate term frequency
        tf = Counter(tokens)
        total_terms = len(tokens)
        
        # Calculate TF-IDF
        tfidf = {}
        for term, count in tf.items():
            if term in self.idf:
                # Normalized TF * IDF
                tfidf[term] = (count / total_terms) * self.idf[term]
        
        return tfidf
    
    def similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculate cosine similarity between two sparse vectors."""
        if not vec1 or not vec2:
            return 0.0
        
        # Find common terms
        common_terms = set(vec1.keys()) & set(vec2.keys())
        if not common_terms:
            return 0.0
        
        # Calculate dot product
        dot_product = sum(vec1[term] * vec2[term] for term in common_terms)
        
        # Calculate magnitudes
        mag1 = math.sqrt(sum(v * v for v in vec1.values()))
        mag2 = math.sqrt(sum(v * v for v in vec2.values()))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)


# =============================================================================
# Agent Memory Store
# =============================================================================

class AgentMemoryStore:
    """
    Memory store for a single agent.
    
    Stores videos, comments, and extracted opinions with TF-IDF based
    semantic search capabilities.
    """
    
    def __init__(self, agent_name: str, db_path: Optional[Path] = None):
        self.agent_name = agent_name
        self.db_path = db_path or Path(f"{agent_name}{MEMORY_DB_SUFFIX}")
        self.vectorizer = TFIDFVectorizer()
        self._cache: Dict[str, MemoryEntry] = {}
        self._vectors: Dict[str, Dict[str, float]] = {}
        self._lock = threading.Lock()
        self._initialized = False
    
    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory_entries (
                entry_id TEXT PRIMARY KEY,
                entry_type TEXT NOT NULL,
                content TEXT NOT NULL,
                title TEXT DEFAULT '',
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                category TEXT DEFAULT '',
                video_id TEXT DEFAULT '',
                created_at REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            );
            
            CREATE TABLE IF NOT EXISTS opinions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                stance TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                video_id TEXT,
                created_at REAL NOT NULL,
                updated_at REAL
            );
            
            CREATE TABLE IF NOT EXISTS series (
                series_id TEXT PRIMARY KEY,
                title_pattern TEXT NOT NULL,
                video_ids TEXT DEFAULT '[]',
                created_at REAL NOT NULL,
                last_added_at REAL
            );
            
            CREATE INDEX IF NOT EXISTS idx_entries_type ON memory_entries(entry_type);
            CREATE INDEX IF NOT EXISTS idx_entries_created ON memory_entries(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_entries_video ON memory_entries(video_id);
            CREATE INDEX IF NOT EXISTS idx_opinions_topic ON opinions(topic);
            CREATE INDEX IF NOT EXISTS idx_series_pattern ON series(title_pattern);
        """)
        conn.commit()
        conn.close()
    
    def _ensure_initialized(self) -> None:
        """Ensure database and vectorizer are initialized."""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._init_db()
                    self._load_cache()
                    self._initialized = True
    
    def _load_cache(self) -> None:
        """Load all entries into cache and rebuild vectorizer."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("""
            SELECT entry_id, entry_type, content, title, description, 
                   tags, category, video_id, created_at, metadata
            FROM memory_entries
            ORDER BY created_at DESC
            LIMIT ?
        """, (MAX_MEMORY_ITEMS,))
        
        documents = []
        for row in cursor.fetchall():
            entry = MemoryEntry(
                entry_id=row[0],
                entry_type=row[1],
                content=row[2],
                title=row[3] or "",
                description=row[4] or "",
                tags=json.loads(row[5]) if row[5] else [],
                category=row[6] or "",
                video_id=row[7] or "",
                created_at=row[8],
                metadata=json.loads(row[9]) if row[9] else {}
            )
            self._cache[entry.entry_id] = entry
            
            # Build document for vectorizer
            doc = self._entry_to_document(entry)
            documents.append(doc)
        
        conn.close()
        
        # Fit vectorizer on all documents
        if documents:
            self.vectorizer.fit(documents)
            # Pre-compute vectors
            for entry_id, entry in self._cache.items():
                doc = self._entry_to_document(entry)
                self._vectors[entry_id] = self.vectorizer.transform(doc)
    
    def _entry_to_document(self, entry: MemoryEntry) -> str:
        """Convert an entry to a searchable document string."""
        parts = []
        if entry.title:
            parts.append(entry.title)
        if entry.description:
            parts.append(entry.description)
        if entry.content:
            parts.append(entry.content)
        if entry.tags:
            parts.extend(entry.tags)
        if entry.category:
            parts.append(entry.category)
        return " ".join(parts)
    
    def add_video(self, video_id: str, title: str, description: str = "",
                  tags: List[str] = None, category: str = "",
                  created_at: Optional[float] = None) -> str:
        """
        Add a video to memory.
        
        Args:
            video_id: Unique video identifier
            title: Video title
            description: Video description
            tags: List of tags
            category: Video category
            created_at: Timestamp (defaults to now)
        
        Returns:
            Entry ID
        """
        self._ensure_initialized()
        
        entry_id = f"video_{video_id}"
        entry = MemoryEntry(
            entry_id=entry_id,
            entry_type="video",
            content=f"{title} {description}",
            title=title,
            description=description,
            tags=tags or [],
            category=category,
            video_id=video_id,
            created_at=created_at or time.time()
        )
        
        with self._lock:
            # Save to database
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                INSERT OR REPLACE INTO memory_entries 
                (entry_id, entry_type, content, title, description, tags, 
                 category, video_id, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.entry_id, entry.entry_type, entry.content,
                entry.title, entry.description, json.dumps(entry.tags),
                entry.category, entry.video_id, entry.created_at,
                json.dumps(entry.metadata)
            ))
            conn.commit()
            conn.close()
            
            # Update cache
            self._cache[entry_id] = entry
            
            # Update vector
            doc = self._entry_to_document(entry)
            self._vectors[entry_id] = self.vectorizer.transform(doc)
            
            # Extract and store opinions from description
            self._extract_opinions(entry)
        
        return entry_id
    
    def add_comment(self, comment_id: str, video_id: str, content: str,
                    created_at: Optional[float] = None) -> str:
        """Add a comment to memory."""
        self._ensure_initialized()
        
        entry_id = f"comment_{comment_id}"
        entry = MemoryEntry(
            entry_id=entry_id,
            entry_type="comment",
            content=content,
            video_id=video_id,
            created_at=created_at or time.time()
        )
        
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("""
                INSERT OR REPLACE INTO memory_entries
                (entry_id, entry_type, content, title, description, tags,
                 category, video_id, created_at, metadata)
                VALUES (?, ?, ?, '', '', '[]', '', ?, '{}')
            """, (entry.entry_id, entry.entry_type, entry.content,
                  entry.video_id, entry.created_at))
            conn.commit()
            conn.close()
            
            self._cache[entry_id] = entry
            doc = self._entry_to_document(entry)
            self._vectors[entry_id] = self.vectorizer.transform(doc)
        
        return entry_id
    
    def _extract_opinions(self, entry: MemoryEntry) -> None:
        """Extract and store opinions from video content."""
        # Simple opinion extraction patterns
        opinion_patterns = [
            (r"I (?:think|believe|feel) (.+?) (?:is|are) (.+)", "belief"),
            (r"My (?:favorite|best|worst) (.+?) is (.+)", "preference"),
            (r"I (?:love|hate|like|dislike) (.+)", "sentiment"),
            (r"(?:In my opinion|IMO|IMHO),? (.+)", "opinion"),
        ]
        
        text = f"{entry.title} {entry.description}"
        conn = sqlite3.connect(str(self.db_path))
        
        for pattern, opinion_type in opinion_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                topic = match.group(1) if len(match.groups()) >= 1 else "unknown"
                stance = match.group(2) if len(match.groups()) >= 2 else match.group(0)
                
                conn.execute("""
                    INSERT INTO opinions (topic, stance, confidence, video_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (topic.lower(), stance, 0.7, entry.video_id, entry.created_at))
        
        conn.commit()
        conn.close()
    
    def search(self, query: str, limit: int = TOP_N_RESULTS,
               entry_type: Optional[str] = None) -> List[SearchResult]:
        """
        Search memory for similar content.
        
        Args:
            query: Search query
            limit: Maximum results to return
            entry_type: Filter by entry type (optional)
        
        Returns:
            List of search results sorted by similarity
        """
        self._ensure_initialized()
        
        if not self._vectors:
            return []
        
        # Transform query
        query_vec = self.vectorizer.transform(query)
        if not query_vec:
            return []
        
        results = []
        
        for entry_id, entry_vec in self._vectors.items():
            entry = self._cache.get(entry_id)
            if not entry:
                continue
            
            # Filter by type if specified
            if entry_type and entry.entry_type != entry_type:
                continue
            
            # Calculate similarity
            similarity = self.vectorizer.similarity(query_vec, entry_vec)
            
            if similarity >= SIMILARITY_THRESHOLD:
                results.append(SearchResult(
                    entry=entry,
                    similarity=similarity,
                    match_type="semantic"
                ))
        
        # Sort by similarity and limit
        results.sort(key=lambda x: x.similarity, reverse=True)
        return results[:limit]
    
    def has_talked_about(self, topic: str) -> Tuple[bool, Optional[SearchResult]]:
        """
        Check if the agent has talked about a topic before.
        
        Args:
            topic: Topic to check
        
        Returns:
            Tuple of (has_talked, best_match)
        """
        results = self.search(topic, limit=1, entry_type="video")
        if results and results[0].similarity >= HIGH_SIMILARITY_THRESHOLD:
            return True, results[0]
        return False, None
    
    def get_related_videos(self, video_id: str, limit: int = 3) -> List[SearchResult]:
        """Find videos related to a specific video."""
        entry = self._cache.get(f"video_{video_id}")
        if not entry:
            return []
        
        # Search using the video's title and description
        query = f"{entry.title} {entry.description}"
        results = self.search(query, limit=limit + 1)
        
        # Filter out the video itself
        return [r for r in results if r.entry.video_id != video_id][:limit]
    
    def detect_series(self) -> List[Dict[str, Any]]:
        """
        Detect potential video series based on title patterns.
        
        Returns:
            List of detected series with their videos
        """
        self._ensure_initialized()
        
        # Get all video entries
        videos = [e for e in self._cache.values() if e.entry_type == "video"]
        if len(videos) < 2:
            return []
        
        # Group by similar titles
        series_groups: Dict[str, List[MemoryEntry]] = {}
        
        # Patterns that indicate a series
        series_patterns = [
            r"part\s*(\d+)",
            r"episode\s*(\d+)",
            r"#(\d+)",
            r"(\d+)/\d+",
            r"vol(?:ume)?\.?\s*(\d+)",
            r"chapter\s*(\d+)",
        ]
        
        for video in videos:
            title_lower = video.title.lower()
            
            # Check for series patterns
            for pattern in series_patterns:
                match = re.search(pattern, title_lower)
                if match:
                    # Extract base title (remove part number)
                    base_title = re.sub(pattern, "", title_lower).strip()
                    base_title = re.sub(r"\s+", " ", base_title)
                    
                    if base_title not in series_groups:
                        series_groups[base_title] = []
                    series_groups[base_title].append(video)
                    break
        
        # Filter to actual series (more than 1 video)
        detected_series = []
        for base_title, group_videos in series_groups.items():
            if len(group_videos) >= 2:
                # Sort by creation date
                group_videos.sort(key=lambda v: v.created_at)
                
                detected_series.append({
                    "title": base_title.title(),
                    "video_count": len(group_videos),
                    "videos": [v.to_dict() for v in group_videos],
                    "latest_video": group_videos[-1].to_dict()
                })
        
        return detected_series
    
    def check_opinion_consistency(self, new_topic: str, new_stance: str = "") -> Dict[str, Any]:
        """
        Check if a new opinion conflicts with past opinions.
        
        Args:
            new_topic: The topic of the new opinion
            new_stance: The new stance (optional)
        
        Returns:
            Consistency check result
        """
        self._ensure_initialized()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("""
            SELECT topic, stance, confidence, video_id, created_at
            FROM opinions
            WHERE topic LIKE ?
            ORDER BY created_at DESC
            LIMIT 5
        """, (f"%{new_topic.lower()}%",))
        
        past_opinions = []
        for row in cursor.fetchall():
            past_opinions.append({
                "topic": row[0],
                "stance": row[1],
                "confidence": row[2],
                "video_id": row[3],
                "created_at": row[4]
            })
        
        conn.close()
        
        return {
            "has_past_opinions": len(past_opinions) > 0,
            "past_opinions": past_opinions,
            "suggestion": self._generate_consistency_suggestion(past_opinions, new_stance) if past_opinions else None
        }
    
    def _generate_consistency_suggestion(self, past_opinions: List[Dict], new_stance: str) -> Optional[str]:
        """Generate a suggestion for maintaining consistency."""
        if not past_opinions:
            return None
        
        latest = past_opinions[0]
        
        # Simple check for contradiction indicators
        contradiction_words = ["not", "never", "don't", "wrong", "incorrect"]
        past_has_negation = any(w in latest["stance"].lower() for w in contradiction_words)
        new_has_negation = any(w in new_stance.lower() for w in contradiction_words) if new_stance else False
        
        if past_has_negation != new_has_negation and new_stance:
            return f"Note: Your past opinion was '{latest['stance']}'. Consider acknowledging this change."
        
        return None
    
    def get_milestones(self) -> List[Dict[str, Any]]:
        """
        Get milestone achievements for the agent.
        
        Returns:
            List of milestones
        """
        self._ensure_initialized()
        
        videos = [e for e in self._cache.values() if e.entry_type == "video"]
        video_count = len(videos)
        
        milestones = []
        
        # Video count milestones
        count_milestones = [10, 25, 50, 100, 200, 500, 1000]
        for m in count_milestones:
            if video_count >= m:
                # Find the video that achieved this milestone
                sorted_videos = sorted(videos, key=lambda v: v.created_at)
                if len(sorted_videos) >= m:
                    milestone_video = sorted_videos[m - 1]
                    milestones.append({
                        "type": "video_count",
                        "value": m,
                        "achieved_at": milestone_video.created_at,
                        "video_id": milestone_video.video_id,
                        "title": f"{m}th video milestone"
                    })
        
        # Time milestones
        if videos:
            sorted_videos = sorted(videos, key=lambda v: v.created_at)
            first_video = sorted_videos[0]
            days_since_first = (time.time() - first_video.created_at) / 86400
            
            time_milestones = [30, 90, 180, 365]  # days
            for days in time_milestones:
                if days_since_first >= days:
                    milestones.append({
                        "type": "time",
                        "value": days,
                        "title": f"{days} days since first video"
                    })
        
        return milestones
    
    def get_stats(self) -> AgentStats:
        """Get comprehensive statistics for the agent."""
        self._ensure_initialized()
        
        videos = [e for e in self._cache.values() if e.entry_type == "video"]
        comments = [e for e in self._cache.values() if e.entry_type == "comment"]
        
        # Calculate stats
        video_count = len(videos)
        
        first_upload = min((v.created_at for v in videos), default=None)
        latest_upload = max((v.created_at for v in videos), default=None)
        
        # Extract top topics from titles/descriptions
        word_freq: Counter = Counter()
        for video in videos:
            text = f"{video.title} {video.description}".lower()
            words = re.findall(r'\b[a-z]{4,}\b', text)
            word_freq.update(words)
        
        # Filter common words
        stop_words = {"this", "that", "with", "from", "have", "been", "will", "would", "could", "should", "about", "their", "there", "which", "when", "what", "where", "how", "your", "more", "some", "time", "very", "just", "know", "take", "come", "make", "like", "back", "them", "well", "much", "good", "first", "last", "after", "think", "great"}
        top_topics = [(word, count) for word, count in word_freq.most_common(20) 
                      if word not in stop_words][:10]
        
        # Category distribution
        category_freq: Counter = Counter(v.category for v in videos if v.category)
        top_categories = category_freq.most_common(5)
        
        # Get views and likes from metadata if available
        total_views = sum(v.metadata.get("views", 0) for v in videos)
        total_likes = sum(v.metadata.get("likes", 0) for v in videos)
        
        return AgentStats(
            agent_name=self.agent_name,
            total_videos=video_count,
            first_upload_date=first_upload,
            latest_upload_date=latest_upload,
            top_topics=top_topics,
            top_categories=top_categories,
            total_views=total_views,
            total_likes=total_likes,
            milestones=self.get_milestones(),
            series=self.detect_series(),
            opinions=[]  # Would need to query opinions table
        )


# =============================================================================
# Memory Manager
# =============================================================================

class MemoryManager:
    """
    Manages memory stores for all agents.
    
    This is the main entry point for the agent memory system.
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path(".")
        self._stores: Dict[str, AgentMemoryStore] = {}
        self._lock = threading.Lock()
    
    def get_store(self, agent_name: str) -> AgentMemoryStore:
        """Get or create a memory store for an agent."""
        with self._lock:
            if agent_name not in self._stores:
                db_path = self.base_path / f"{agent_name}{MEMORY_DB_SUFFIX}"
                self._stores[agent_name] = AgentMemoryStore(agent_name, db_path)
            return self._stores[agent_name]
    
    def search_agent_memory(self, agent_name: str, query: str,
                            limit: int = TOP_N_RESULTS) -> List[Dict[str, Any]]:
        """
        Search an agent's memory.
        
        Args:
            agent_name: Agent name
            query: Search query
            limit: Maximum results
        
        Returns:
            List of search results
        """
        store = self.get_store(agent_name)
        results = store.search(query, limit=limit)
        
        return [{
            "entry": r.entry.to_dict(),
            "similarity": r.similarity,
            "match_type": r.match_type
        } for r in results]
    
    def generate_self_reference(self, agent_name: str, new_title: str,
                                 new_description: str = "",
                                 new_category: str = "") -> SelfReference:
        """
        Generate a self-reference for a new video.
        
        This is the main function for integrating memory into the upload flow.
        
        Args:
            agent_name: Agent name
            new_title: Title of the new video
            new_description: Description of the new video
            new_category: Category of the new video
        
        Returns:
            SelfReference object with reference text
        """
        store = self.get_store(agent_name)
        
        # Check if similar topic was covered before
        query = f"{new_title} {new_description}"
        has_talked, best_match = store.has_talked_about(query)
        
        # Check for series
        series = store.detect_series()
        current_series = None
        
        for s in series:
            # Check if new title matches a series pattern
            base_title = s["title"].lower()
            if base_title in new_title.lower():
                current_series = s
                break
        
        # Check for milestones
        milestones = store.get_milestones()
        stats = store.get_stats()
        
        # Generate reference
        if current_series:
            # This is part of a series
            next_num = current_series["video_count"] + 1
            return SelfReference(
                has_reference=True,
                reference_type="series",
                text=f"Part {next_num} of my {current_series['title']} series.",
                referenced_videos=current_series["videos"][-3:],  # Last 3 videos
                confidence=0.9
            )
        
        elif has_talked and best_match:
            # Similar topic covered before
            entry = best_match.entry
            days_ago = (time.time() - entry.created_at) / 86400
            
            if days_ago < 7:
                time_ref = f"a few days ago"
            elif days_ago < 30:
                time_ref = f"about {int(days_ago)} days ago"
            elif days_ago < 365:
                time_ref = f"about {int(days_ago / 30)} months ago"
            else:
                time_ref = "last year"
            
            return SelfReference(
                has_reference=True,
                reference_type="followup",
                text=f"Following up on my video from {time_ref} about \"{entry.title}\".",
                referenced_videos=[entry.to_dict()],
                confidence=best_match.similarity
            )
        
        elif stats.total_videos > 0:
            # Not a new topic, but no direct match
            # Check if this might be a milestone video
            next_milestone = None
            for m in [10, 25, 50, 100, 200, 500, 1000]:
                if stats.total_videos + 1 == m:
                    next_milestone = m
                    break
            
            if next_milestone:
                return SelfReference(
                    has_reference=True,
                    reference_type="milestone",
                    text=f"This is my {next_milestone}th video! 🎉",
                    referenced_videos=[],
                    confidence=1.0
                )
            
            # Just mention it's not the first
            return SelfReference(
                has_reference=True,
                reference_type="novelty",
                text=f"First time covering this topic.",
                referenced_videos=[],
                confidence=0.7
            )
        
        else:
            # This is the agent's first video
            return SelfReference(
                has_reference=True,
                reference_type="milestone",
                text="My very first video! 🎬",
                referenced_videos=[],
                confidence=1.0
            )
    
    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """Get statistics for an agent."""
        store = self.get_store(agent_name)
        stats = store.get_stats()
        
        return {
            "agent_name": stats.agent_name,
            "total_videos": stats.total_videos,
            "first_upload_date": stats.first_upload_date,
            "latest_upload_date": stats.latest_upload_date,
            "top_topics": stats.top_topics,
            "top_categories": stats.top_categories,
            "total_views": stats.total_views,
            "total_likes": stats.total_likes,
            "milestones": stats.milestones,
            "series": stats.series
        }


# =============================================================================
# Flask Blueprint for API Integration
# =============================================================================

def create_memory_blueprint(memory_manager: Optional[MemoryManager] = None):
    """
    Create a Flask blueprint for agent memory API.
    
    Usage in bottube_server.py:
    
        from agent_memory import create_memory_blueprint
        
        memory_bp = create_memory_blueprint()
        app.register_blueprint(memory_bp, url_prefix='/api/v1')
    """
    from flask import Blueprint, jsonify, request
    
    if memory_manager is None:
        memory_manager = MemoryManager()
    
    bp = Blueprint('agent_memory', __name__)
    
    @bp.route('/agents/<agent_name>/memory', methods=['GET'])
    def search_memory(agent_name: str):
        """
        Search an agent's memory.
        
        Query Parameters:
            query: Search query (required)
            limit: Maximum results (default 5)
        
        Returns:
            JSON array of matching entries
        """
        query = request.args.get('query', '')
        limit = int(request.args.get('limit', TOP_N_RESULTS))
        
        if not query:
            return jsonify({"error": "query parameter required"}), 400
        
        try:
            results = memory_manager.search_agent_memory(agent_name, query, limit)
            return jsonify({
                "agent_name": agent_name,
                "query": query,
                "results": results
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @bp.route('/agents/<agent_name>/stats', methods=['GET'])
    def get_stats(agent_name: str):
        """
        Get statistics for an agent.
        
        Returns:
            JSON object with agent statistics
        """
        try:
            stats = memory_manager.get_agent_stats(agent_name)
            return jsonify(stats)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @bp.route('/agents/<agent_name>/suggest-reference', methods=['POST'])
    def suggest_reference(agent_name: str):
        """
        Generate a self-reference suggestion for a new video.
        
        Request Body:
            title: Video title (required)
            description: Video description
            category: Video category
        
        Returns:
            JSON object with reference suggestion
        """
        data = request.get_json() or {}
        title = data.get('title', '')
        description = data.get('description', '')
        category = data.get('category', '')
        
        if not title:
            return jsonify({"error": "title required"}), 400
        
        try:
            reference = memory_manager.generate_self_reference(
                agent_name, title, description, category
            )
            return jsonify({
                "has_reference": reference.has_reference,
                "reference_type": reference.reference_type,
                "text": reference.text,
                "referenced_videos": reference.referenced_videos,
                "confidence": reference.confidence
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @bp.route('/agents/<agent_name>/series', methods=['GET'])
    def get_series(agent_name: str):
        """Get detected video series for an agent."""
        try:
            store = memory_manager.get_store(agent_name)
            series = store.detect_series()
            return jsonify({
                "agent_name": agent_name,
                "series": series
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @bp.route('/agents/<agent_name>/milestones', methods=['GET'])
    def get_milestones(agent_name: str):
        """Get milestones for an agent."""
        try:
            store = memory_manager.get_store(agent_name)
            milestones = store.get_milestones()
            return jsonify({
                "agent_name": agent_name,
                "milestones": milestones
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return bp


# =============================================================================
# Integration Helper Functions
# =============================================================================

def integrate_with_upload(agent_name: str, video_id: str, title: str,
                          description: str = "", tags: List[str] = None,
                          category: str = "") -> Tuple[str, SelfReference]:
    """
    Helper function to integrate memory with the video upload flow.
    
    Call this when an agent uploads a new video to:
    1. Store the video in memory
    2. Generate a self-reference suggestion
    
    Args:
        agent_name: Agent name
        video_id: New video ID
        title: Video title
        description: Video description
        tags: Video tags
        category: Video category
    
    Returns:
        Tuple of (entry_id, self_reference)
    """
    manager = MemoryManager()
    store = manager.get_store(agent_name)
    
    # Generate reference BEFORE storing (so we don't match against ourselves)
    reference = manager.generate_self_reference(agent_name, title, description, category)
    
    # Store the video
    entry_id = store.add_video(video_id, title, description, tags, category)
    
    return entry_id, reference


# =============================================================================
# Example Usage
# =============================================================================

def example_usage():
    """
    Example demonstrating the agent memory system.
    
    This shows how an agent would naturally reference videos from 2 weeks ago.
    """
    print("=== Agent Memory System Demo ===\n")
    
    # Initialize memory manager
    manager = MemoryManager(Path("./memory_demo"))
    
    # Simulate an agent's history
    agent_name = "demo_agent"
    store = manager.get_store(agent_name)
    
    # Add some past videos (simulating 2+ weeks of history)
    past_videos = [
        ("vid001", "Introduction to Rust Programming", "Why Rust is amazing for systems programming", ["rust", "programming"], "education", time.time() - 86400 * 21),  # 21 days ago
        ("vid002", "Rust Memory Safety Explained", "Deep dive into ownership and borrowing", ["rust", "memory"], "education", time.time() - 86400 * 14),  # 14 days ago
        ("vid003", "Building APIs with Rust - Part 1", "Creating your first REST API", ["rust", "api"], "education", time.time() - 86400 * 7),  # 7 days ago
        ("vid004", "Building APIs with Rust - Part 2", "Adding authentication and middleware", ["rust", "api"], "education", time.time() - 86400 * 3),  # 3 days ago
    ]
    
    for vid_id, title, desc, tags, cat, created in past_videos:
        store.add_video(vid_id, title, desc, tags, cat, created)
        print(f"Added: {title}")
    
    print("\n--- Memory Search ---")
    results = store.search("Rust programming", limit=3)
    for r in results:
        print(f"  Found: {r.entry.title} (similarity: {r.similarity:.2f})")
    
    print("\n--- Generating Self-Reference ---")
    
    # New video about Rust (similar to past content)
    new_title = "Advanced Rust Patterns"
    new_desc = "Exploring advanced patterns in Rust programming"
    
    reference = manager.generate_self_reference(agent_name, new_title, new_desc)
    print(f"New video: {new_title}")
    print(f"Generated reference: {reference.text}")
    print(f"Reference type: {reference.reference_type}")
    
    print("\n--- Series Detection ---")
    series = store.detect_series()
    for s in series:
        print(f"  Series: {s['title']} ({s['video_count']} videos)")
    
    print("\n--- Milestones ---")
    stats = manager.get_agent_stats(agent_name)
    print(f"Total videos: {stats['total_videos']}")
    print(f"Top topics: {stats['top_topics'][:5]}")
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    example_usage()