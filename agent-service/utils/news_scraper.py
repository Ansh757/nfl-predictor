"""
Real News Scraper Implementation using RSS Feeds
No API keys required - gets started immediately
"""

import asyncio
import aiohttp
import feedparser
from typing import Dict, List, Any
import logging
from datetime import datetime, timedelta
import re

class RealNewsCollector:
    """
    Real-time news collector using RSS feeds
    Gets news from ESPN, NFL.com, CBS Sports, and other sources
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # RSS feed URLs
        self.rss_feeds = {
            'espn_nfl': 'https://www.espn.com/espn/rss/nfl/news',
            'nfl_com': 'https://www.nfl.com/feeds/rss/news',
            'cbs_sports': 'https://www.cbssports.com/rss/headlines/nfl',
            'pro_football_talk': 'https://profootballtalk.nbcsports.com/feed/',
            'bleacher_report': 'https://bleacherreport.com/nfl.rss'
        }
        
        # Team name mappings for better matching
        self.team_aliases = {
            'Chiefs': ['kansas city', 'chiefs', 'kc chiefs', 'mahomes', 'kelce', 'reid'],
            'Bills': ['buffalo', 'bills', 'josh allen', 'stefon diggs', 'matt milano', 'von miller'],
            'Cowboys': ['dallas', 'cowboys', 'dak prescott', 'micah parsons', 'ceedee lamb'],
            'Patriots': ['new england', 'patriots', 'pats', 'mac jones', 'bill belichick'],
            'Packers': ['green bay', 'packers', 'aaron rodgers', 'jordan love'],
            '49ers': ['san francisco', '49ers', 'niners', 'brock purdy', 'christian mccaffrey'],
            'Ravens': ['baltimore', 'ravens', 'lamar jackson', 'mark andrews'],
            'Steelers': ['pittsburgh', 'steelers', 'kenny pickett', 'tj watt'],
            'Eagles': ['philadelphia', 'eagles', 'jalen hurts', 'aj brown'],
            'Rams': ['los angeles rams', 'rams', 'matthew stafford', 'cooper kupp'],
            'Bengals': ['cincinnati', 'bengals', 'joe burrow', 'ja\'marr chase'],
            'Browns': ['cleveland', 'browns', 'deshaun watson', 'myles garrett'],
            'Titans': ['tennessee', 'titans', 'derrick henry', 'ryan tannehill'],
            'Colts': ['indianapolis', 'colts', 'anthony richardson', 'jonathan taylor'],
            'Texans': ['houston', 'texans', 'c.j. stroud', 'nico collins'],
            'Jaguars': ['jacksonville', 'jaguars', 'trevor lawrence', 'josh allen'],
            'Broncos': ['denver', 'broncos', 'russell wilson', 'jerry jeudy'],
            'Chargers': ['los angeles chargers', 'chargers', 'justin herbert', 'khalil mack'],
            'Raiders': ['las vegas', 'raiders', 'jimmy garoppolo', 'davante adams'],
            'Dolphins': ['miami', 'dolphins', 'tua tagovailoa', 'tyreek hill', 'mike mcdaniel', 'jaylen waddle'],
            'Jets': ['new york jets', 'jets', 'aaron rodgers', 'sauce gardner'],
            'Giants': ['new york giants', 'giants', 'daniel jones', 'saquon barkley'],
            'Commanders': ['washington', 'commanders', 'sam howell', 'terry mclaurin'],
            'Lions': ['detroit', 'lions', 'jared goff', 'amon-ra st. brown'],
            'Bears': ['chicago', 'bears', 'justin fields', 'dj moore'],
            'Vikings': ['minnesota', 'vikings', 'kirk cousins', 'justin jefferson'],
            'Saints': ['new orleans', 'saints', 'derek carr', 'alvin kamara'],
            'Falcons': ['atlanta', 'falcons', 'desmond ridder', 'kyle pitts'],
            'Panthers': ['carolina', 'panthers', 'bryce young', 'christian mccaffrey'],
            'Buccaneers': ['tampa bay', 'buccaneers', 'bucs', 'baker mayfield', 'mike evans'],
            'Cardinals': ['arizona', 'cardinals', 'kyler murray', 'deandre hopkins'],
            'Seahawks': ['seattle', 'seahawks', 'geno smith', 'dk metcalf']
        }
        
        # Sentiment keywords - enhanced for sports context
        self.positive_keywords = [
            'win', 'victory', 'won', 'success', 'successful', 'strong', 'excellent', 
            'outstanding', 'confident', 'good', 'great', 'impressive', 'dominance',
            'breakthrough', 'comeback', 'recovered', 'healthy', 'cleared', 'return',
            'praise', 'praised', 'commend', 'honor', 'award', 'celebrate', 'dominant',
            'blowout', 'crushed', 'destroyed', 'demolished', 'unstoppable', 'rolling',
            'momentum', 'hot', 'streak', 'explosive', 'perfect', 'flawless', 'mvp'
        ]
        
        self.negative_keywords = [
            'loss', 'lost', 'defeat', 'injury', 'injured', 'hurt', 'concern', 
            'worried', 'struggle', 'struggling', 'problem', 'issue', 'trouble',
            'poor', 'bad', 'terrible', 'awful', 'disappointing', 'failed',
            'criticism', 'criticized', 'blame', 'fault', 'penalty', 'suspension',
            'fired', 'lose his job', 'hot seat', 'under pressure', 'questionable',
            'doubtful', 'out', 'sidelined', 'benched', 'controversy', 'drama',
            'collapse', 'blown out', 'embarrassing', 'pathetic', 'cold'
        ]
        
        # Category keywords for classification
        self.category_keywords = {
            'injuries': [
                'injury', 'injured', 'hurt', 'pain', 'surgery', 'protocol', 
                'questionable', 'doubtful', 'out', 'sidelined', 'medical', 
                'concussion', 'ankle', 'knee', 'shoulder', 'back', 'hamstring'
            ],
            'coaching': [
                'coach', 'coaching', 'coordinator', 'staff', 'play-calling', 
                'strategy', 'scheme', 'gameplan', 'decisions', 'leadership',
                'hire', 'fired', 'promote', 'demote'
            ],
            'team_chemistry': [
                'team', 'locker room', 'chemistry', 'unity', 'bond', 'together',
                'leadership', 'culture', 'morale', 'argument', 'conflict', 
                'dispute', 'tension', 'meeting', 'talk'
            ],
            'momentum': [
                'streak', 'momentum', 'confidence', 'form', 'performance', 
                'winning', 'losing', 'hot', 'cold', 'rhythm', 'flow',
                'dominant', 'dominance', 'struggling'
            ],
            'motivation': [
                'motivation', 'motivated', 'playoff', 'playoffs', 'postseason',
                'revenge', 'rivalry', 'home', 'primetime', 'pressure',
                'expectations', 'goals', 'targets', 'mvp'
            ]
        }
    
    async def test_connection(self):
        """Test connection to RSS feeds"""
        try:
            # Test one feed
            test_feed = list(self.rss_feeds.values())[0]
            feed = feedparser.parse(test_feed)
            
            if feed.entries:
                self.logger.info(f"RSS connection test successful - {len(feed.entries)} articles found")
                return True
            else:
                raise Exception("No articles found in test feed")
                
        except Exception as e:
            self.logger.error(f"RSS connection test failed: {e}")
            raise
    
    async def get_team_news(self, team_name: str) -> Dict[str, Any]:
        """
        Get news sentiment analysis for a specific team using RSS feeds
        
        Args:
            team_name: NFL team name (e.g., "Chiefs", "Bills")
            
        Returns:
            Dictionary with sentiment analysis results
        """
        
        self.logger.info(f"Collecting RSS news for {team_name}")
        
        # Get team aliases for better matching
        team_keywords = self.team_aliases.get(team_name, [team_name.lower()])
        
        # Collect articles from all RSS feeds
        all_articles = []
        
        for source, feed_url in self.rss_feeds.items():
            try:
                articles = await self._fetch_rss_articles(feed_url, team_keywords, source)
                all_articles.extend(articles)
                self.logger.debug(f"Found {len(articles)} articles from {source}")
            except Exception as e:
                self.logger.warning(f"Failed to fetch from {source}: {e}")
                continue
        
        if not all_articles:
            self.logger.warning(f"No articles found for {team_name}, using fallback")
            return self._generate_fallback_response(team_name)
        
        # Analyze sentiment
        sentiment_analysis = self._analyze_articles_sentiment(all_articles, team_name)
        
        self.logger.info(f"Found {len(all_articles)} articles for {team_name} with {sentiment_analysis['sentiment_level']} sentiment")
        
        return sentiment_analysis
    
    async def _fetch_rss_articles(self, feed_url: str, team_keywords: List[str], source: str) -> List[Dict]:
        """Fetch articles with balanced filtering - strict enough to avoid cross-contamination"""
        
        try:
            # Parse RSS feed
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                return []
            
            primary_team = team_keywords[0] if team_keywords else ""
            team_articles = []
            
            for entry in feed.entries:
                title = entry.title.lower()
                description = getattr(entry, 'description', '').lower()
                full_text = f"{title} {description}"
                
                # Check if our team is mentioned
                team_mentioned = any(keyword in full_text for keyword in team_keywords)
                
                if team_mentioned:
                    # CRITICAL: Check for other team mentions that would indicate cross-contamination
                    other_teams_mentioned = []
                    for other_team, other_keywords in self.team_aliases.items():
                        if other_team.lower() != primary_team.lower():
                            # Check if other team is mentioned
                            if any(other_kw in full_text for other_kw in other_keywords[:3]):  # Only check main team identifiers
                                other_teams_mentioned.append(other_team)
                    
                    # If multiple teams mentioned, be more selective
                    if other_teams_mentioned:
                        # Check if our team is the PRIMARY focus
                        our_team_in_title = any(keyword in title for keyword in team_keywords[:3])  # Main identifiers only
                        
                        # Skip if other teams mentioned and we're not primary focus
                        if not our_team_in_title:
                            self.logger.debug(f"Skipping multi-team article for {primary_team}: {title}")
                            continue
                    
                    # Skip prediction/betting articles
                    skip_patterns = [
                        'prediction', 'odds', 'best bets', 'picks from', 
                        'fantasy football', 'draft kings', 'fanduel', 'prop bets'
                    ]
                    
                    if any(pattern in full_text for pattern in skip_patterns):
                        continue
                    
                    article = {
                        'title': entry.title,
                        'description': getattr(entry, 'description', ''),
                        'link': getattr(entry, 'link', ''),
                        'published': getattr(entry, 'published', ''),
                        'source': source,
                        'full_text': full_text,
                        'primary_team': primary_team
                    }
                    team_articles.append(article)
            
            self.logger.debug(f"Found {len(team_articles)} articles for {primary_team} from {source}")
            return team_articles
            
        except Exception as e:
            self.logger.error(f"Error fetching RSS from {feed_url}: {e}")
            return []
    
    def _analyze_articles_sentiment(self, articles: List[Dict], team_name: str) -> Dict[str, Any]:
        """Analyze sentiment of collected articles"""
        
        if not articles:
            return self._generate_fallback_response(team_name)
        
        # Analyze each article
        article_sentiments = []
        category_analysis = {
            'team_chemistry': [],
            'coaching': [],
            'injuries': [],
            'momentum': [],
            'motivation': []
        }
        
        for article in articles:
            # Get article sentiment
            sentiment = self._get_article_sentiment(article)
            article_sentiments.append(sentiment)
            
            # Categorize article
            category = self._categorize_article(article)
            category_analysis[category].append(sentiment)
            
            # Add to article data
            article['sentiment'] = sentiment
            article['category'] = category
        
        # Calculate overall sentiment
        overall_sentiment = sum(article_sentiments) / len(article_sentiments) if article_sentiments else 0.0
        
        # Calculate category-specific sentiments
        category_sentiments = {}
        for category, sentiments in category_analysis.items():
            if sentiments:
                category_sentiments[category] = sum(sentiments) / len(sentiments)
            else:
                category_sentiments[category] = 0.0
        
        # Get key headlines
        key_headlines = self._get_key_headlines(articles)
        
        return {
            'sentiment_score': round(overall_sentiment, 3),
            'sentiment_level': self._classify_sentiment(overall_sentiment),
            'analysis': category_sentiments,
            'key_headlines': key_headlines,
            'article_count': len(articles),
            'last_updated': datetime.now().isoformat(),
            'sources': list(set(article['source'] for article in articles))
        }
    
    def _get_article_sentiment_keyword_only(self, article: Dict) -> float:
        """Get sentiment score using keywords only (backup method)"""
        
        text = f"{article['title']} {article['description']}".lower()
        
        # Count positive and negative keywords
        positive_count = sum(1 for word in self.positive_keywords if word in text)
        negative_count = sum(1 for word in self.negative_keywords if word in text)
        
        # Special handling for obviously negative phrases
        very_negative_phrases = [
            'lose his job', 'hot seat', 'will be fired', 'coaching changes',
            'job security', 'under fire', 'calls for firing'
        ]
        
        has_very_negative = any(phrase in text for phrase in very_negative_phrases)
        if has_very_negative:
            negative_count += 3  # Heavily weight these phrases
        
        total_keywords = positive_count + negative_count
        
        if total_keywords == 0:
            return 0.0  # Neutral
        
        # Calculate sentiment score (-1 to 1)
        sentiment = (positive_count - negative_count) / total_keywords
        
        # Apply some weighting based on title vs description
        title_text = article['title'].lower()
        title_pos = sum(1 for word in self.positive_keywords if word in title_text)
        title_neg = sum(1 for word in self.negative_keywords if word in title_text)
        
        # Check for very negative phrases in title (even more important)
        title_very_negative = any(phrase in title_text for phrase in very_negative_phrases)
        if title_very_negative:
            title_neg += 2
        
        if title_pos > 0 or title_neg > 0:
            # Title sentiment is more important
            title_sentiment = (title_pos - title_neg) / (title_pos + title_neg) if (title_pos + title_neg) > 0 else 0
            sentiment = (sentiment * 0.7) + (title_sentiment * 0.3)
        
        return max(-1.0, min(1.0, sentiment))
    
    def _get_article_sentiment(self, article: Dict) -> float:
        """Enhanced sentiment analysis using TextBlob + keywords"""
        
        try:
            from textblob import TextBlob
            
            # Combine title and description
            text = f"{article['title']} {article['description']}"
            
            # Use TextBlob for sentiment analysis
            blob = TextBlob(text)
            
            # TextBlob returns polarity from -1 (negative) to 1 (positive)
            textblob_sentiment = blob.sentiment.polarity
            
            # Get keyword-based analysis for sports context
            keyword_sentiment = self._get_article_sentiment_keyword_only(article)
            
            # Weight: 70% TextBlob, 30% keyword-based (sports-specific)
            combined_sentiment = (textblob_sentiment * 0.7) + (keyword_sentiment * 0.3)
            
            return max(-1.0, min(1.0, combined_sentiment))
            
        except ImportError:
            # Fallback to keyword-based analysis if TextBlob not available
            self.logger.debug("TextBlob not available, using keyword-based sentiment")
            return self._get_article_sentiment_keyword_only(article)
        except Exception as e:
            self.logger.warning(f"TextBlob sentiment analysis failed: {e}")
            return self._get_article_sentiment_keyword_only(article)
    
    def _categorize_article(self, article: Dict) -> str:
        """Categorize article into news type"""
        
        text = f"{article['title']} {article['description']}".lower()
        
        # Count keywords for each category
        category_scores = {}
        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                category_scores[category] = score
        
        # Return category with highest score, or default to momentum
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        else:
            return 'momentum'
    
    def _classify_sentiment(self, score: float) -> str:
        """Classify sentiment score into level"""
        if score > 0.1:
            return 'positive'
        elif score < -0.1:
            return 'negative'
        else:
            return 'neutral'
    
    def _get_key_headlines(self, articles: List[Dict]) -> List[Dict]:
        """Get the most important headlines"""
        
        # Sort articles by sentiment magnitude and recency
        scored_articles = []
        
        for article in articles:
            sentiment = article.get('sentiment', 0)
            magnitude = abs(sentiment)
            
            # Prefer more recent articles (simple heuristic)
            recency_score = 1.0  # Could be improved with actual date parsing
            
            total_score = magnitude + (recency_score * 0.2)
            scored_articles.append((total_score, article))
        
        # Sort by score and take top 5
        scored_articles.sort(reverse=True, key=lambda x: x[0])
        
        key_headlines = []
        for _, article in scored_articles[:5]:
            key_headlines.append({
                'title': article['title'],
                'sentiment': article.get('sentiment', 0),
                'source': article['source'],
                'published': article.get('published', ''),
                'category': article.get('category', 'general')
            })
        
        return key_headlines
    
    def _generate_fallback_response(self, team_name: str) -> Dict[str, Any]:
        """Generate fallback response when no articles found"""
        
        return {
            'sentiment_score': 0.0,
            'sentiment_level': 'neutral',
            'analysis': {
                'team_chemistry': 0.0,
                'coaching': 0.0,
                'injuries': 0.0,
                'momentum': 0.0,
                'motivation': 0.0
            },
            'key_headlines': [
                {
                    'title': f'No recent news found for {team_name}',
                    'sentiment': 0.0,
                    'source': 'system',
                    'published': datetime.now().isoformat(),
                    'category': 'general'
                }
            ],
            'article_count': 0,
            'last_updated': datetime.now().isoformat(),
            'sources': ['system']
        }