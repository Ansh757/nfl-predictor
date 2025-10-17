import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

# Import Utils 
from utils.news_scraper import RealNewsCollector

class NewsSentimentAgent:
    """
    News Sentiment Analysis Agent for NFL Games
    
    This agent analyzes team morale, recent news, and psychological factors:
    - Locker room drama and team chemistry
    - Coaching changes and staff stability
    - Player injuries and return timelines
    - Recent performance momentum
    - Media pressure and expectations
    - Motivation factors (rivalry, playoffs, etc.)
    """
    
    def __init__(self, name: str, use_real_news: bool = True):
        self.name = name
        self.status = "active"
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        self.use_real_news = use_real_news
        
        # Initialize news collector if using real news
        if self.use_real_news:
            try:
                self.news_collector = RealNewsCollector()
                self.logger.info("Real news collector initialized successfully")
            except Exception as e:
                self.logger.warning(f"Failed to initialize real news collector: {e}. Falling back to simulation.")
                self.use_real_news = False
                self.news_collector = None
        else:
            self.news_collector = None

        # News categories and their impact weights
        self.news_categories = {
            "team_chemistry": {"weight": 0.3, "max_impact": 0.15},
            "coaching": {"weight": 0.25, "max_impact": 0.12},
            "injuries": {"weight": 0.2, "max_impact": 0.10},
            "momentum": {"weight": 0.15, "max_impact": 0.08},
            "motivation": {"weight": 0.1, "max_impact": 0.05}
        }
        
        # Simulated news scenarios (fallback when real news unavailable)
        self.news_scenarios = {
            "team_chemistry": [
                {"type": "positive", "impact": 0.08, "headline": "Locker room unity at season high after team bonding event"},
                {"type": "positive", "impact": 0.06, "headline": "Veterans praise rookie leadership and team cohesion"},
                {"type": "negative", "impact": -0.10, "headline": "Reports of heated argument between star players"},
                {"type": "negative", "impact": -0.12, "headline": "Anonymous player criticizes coaching decisions"},
                {"type": "neutral", "impact": 0.02, "headline": "Team maintains professional atmosphere"}
            ],
            "coaching": [
                {"type": "positive", "impact": 0.09, "headline": "Coach wins NFL Coach of Month award"},
                {"type": "positive", "impact": 0.07, "headline": "Innovative play-calling receives league recognition"},
                {"type": "negative", "impact": -0.11, "headline": "Coach's job security questioned after recent losses"},
                {"type": "negative", "impact": -0.15, "headline": "Rumored friction between coach and front office"},
                {"type": "neutral", "impact": 0.01, "headline": "Coach maintains steady approach"}
            ],
            "injuries": [
                {"type": "positive", "impact": 0.08, "headline": "Star player returns ahead of schedule from injury"},
                {"type": "positive", "impact": 0.05, "headline": "Key players clear concussion protocol"},
                {"type": "negative", "impact": -0.09, "headline": "Starting quarterback dealing with nagging injury"},
                {"type": "negative", "impact": -0.07, "headline": "Multiple starters listed as questionable"},
                {"type": "neutral", "impact": -0.02, "headline": "Injury report shows typical wear and tear"}
            ],
            "momentum": [
                {"type": "positive", "impact": 0.06, "headline": "Team riding 4-game winning streak with confidence high"},
                {"type": "positive", "impact": 0.04, "headline": "Recent dominant performance boosts team morale"},
                {"type": "negative", "impact": -0.08, "headline": "Team struggling after blowing late leads in consecutive games"},
                {"type": "negative", "impact": -0.06, "headline": "Offense sputters in red zone for third straight week"},
                {"type": "neutral", "impact": 0.01, "headline": "Team maintains even keel despite ups and downs"}
            ],
            "motivation": [
                {"type": "positive", "impact": 0.05, "headline": "Playoff implications add extra motivation for crucial game"},
                {"type": "positive", "impact": 0.04, "headline": "Revenge game against former coach sparks team energy"},
                {"type": "negative", "impact": -0.05, "headline": "Nothing to play for with playoff hopes eliminated"},
                {"type": "negative", "impact": -0.03, "headline": "Letdown spot after emotional victory last week"},
                {"type": "neutral", "impact": 0.00, "headline": "Standard preparation for upcoming opponent"}
            ]
        }
        
        # Team-specific narrative tendencies (affects which news is more likely)
        self.team_narratives = {
            "Chiefs": {"stability": 0.8, "media_attention": 0.9, "expectation_pressure": 0.9},
            "Bills": {"stability": 0.7, "media_attention": 0.7, "expectation_pressure": 0.8},
            "Patriots": {"stability": 0.6, "media_attention": 0.8, "expectation_pressure": 0.7},
            "Cowboys": {"stability": 0.5, "media_attention": 1.0, "expectation_pressure": 0.9},
            "Packers": {"stability": 0.7, "media_attention": 0.6, "expectation_pressure": 0.7},
            "49ers": {"stability": 0.6, "media_attention": 0.7, "expectation_pressure": 0.8},
            "Ravens": {"stability": 0.7, "media_attention": 0.6, "expectation_pressure": 0.7},
            "Steelers": {"stability": 0.8, "media_attention": 0.7, "expectation_pressure": 0.6},
            "Bengals": {"stability": 0.6, "media_attention": 0.6, "expectation_pressure": 0.7},
            "Browns": {"stability": 0.5, "media_attention": 0.8, "expectation_pressure": 0.6},
            "Titans": {"stability": 0.6, "media_attention": 0.4, "expectation_pressure": 0.5},
            "Colts": {"stability": 0.6, "media_attention": 0.5, "expectation_pressure": 0.6},
            "Texans": {"stability": 0.7, "media_attention": 0.5, "expectation_pressure": 0.6},
            "Jaguars": {"stability": 0.5, "media_attention": 0.4, "expectation_pressure": 0.5},
            "Broncos": {"stability": 0.6, "media_attention": 0.6, "expectation_pressure": 0.6},
            "Chargers": {"stability": 0.6, "media_attention": 0.5, "expectation_pressure": 0.7},
            "Raiders": {"stability": 0.4, "media_attention": 0.7, "expectation_pressure": 0.5},
            "Dolphins": {"stability": 0.6, "media_attention": 0.6, "expectation_pressure": 0.6},
            "Jets": {"stability": 0.4, "media_attention": 0.8, "expectation_pressure": 0.6},
            "Eagles": {"stability": 0.7, "media_attention": 0.7, "expectation_pressure": 0.8},
            "Giants": {"stability": 0.5, "media_attention": 0.8, "expectation_pressure": 0.5},
            "Commanders": {"stability": 0.5, "media_attention": 0.6, "expectation_pressure": 0.5},
            "Lions": {"stability": 0.7, "media_attention": 0.6, "expectation_pressure": 0.7},
            "Bears": {"stability": 0.5, "media_attention": 0.6, "expectation_pressure": 0.5},
            "Vikings": {"stability": 0.6, "media_attention": 0.5, "expectation_pressure": 0.6},
            "Saints": {"stability": 0.6, "media_attention": 0.5, "expectation_pressure": 0.6},
            "Falcons": {"stability": 0.6, "media_attention": 0.5, "expectation_pressure": 0.6},
            "Panthers": {"stability": 0.5, "media_attention": 0.4, "expectation_pressure": 0.4},
            "Buccaneers": {"stability": 0.7, "media_attention": 0.6, "expectation_pressure": 0.7},
            "Rams": {"stability": 0.6, "media_attention": 0.7, "expectation_pressure": 0.7},
            "Cardinals": {"stability": 0.5, "media_attention": 0.4, "expectation_pressure": 0.5},
            "Seahawks": {"stability": 0.7, "media_attention": 0.6, "expectation_pressure": 0.6}
        }
        
        # Cache for recent news analysis
        self.news_cache = {}
        self.cache_duration = timedelta(hours=2)  # Cache news for 2 hours
        
        self.logger.info(f"NewsSentimentAgent '{name}' initialized with {len(self.news_scenarios)} news categories")
        self.logger.info(f"Using {'real' if self.use_real_news else 'simulated'} news data")
    
    async def get_status(self) -> Dict[str, Any]:
        """Return current agent status"""
        total_scenarios = sum(len(scenarios) for scenarios in self.news_scenarios.values())
        news_source = "real news APIs" if self.use_real_news else "simulated scenarios"
        
        return {
            "status": self.status,
            "last_activity": self.last_activity,
            "message": f"News sentiment analysis ready using {news_source}. Monitoring {total_scenarios} scenario types across {len(self.news_categories)} categories."
        }
    
    async def refresh(self):
        """Refresh agent data and status"""
        self.last_activity = datetime.now()
        
        # Clear old cache entries
        current_time = datetime.now()
        expired_keys = [
            key for key, (data, timestamp) in self.news_cache.items()
            if current_time - timestamp > self.cache_duration
        ]
        for key in expired_keys:
            del self.news_cache[key]
        
        # Test news collector connection if using real news
        if self.use_real_news and self.news_collector:
            try:
                await self.news_collector.test_connection()
                self.logger.info("News collector connection verified")
            except Exception as e:
                self.logger.warning(f"News collector connection issue: {e}")
        
        self.logger.info("News sentiment agent refreshed")
    
    async def predict_game(self, game_data, game_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze news sentiment impact on game outcome
        
        Args:
            game_data: Game information
            game_context: Additional context data
            
        Returns:
            Dictionary with news sentiment-based prediction
        """
        self.last_activity = datetime.now()
        self.status = "analyzing_sentiment"
        
        try:
            home_team = game_data.home_team_name
            away_team = game_data.away_team_name
            
            self.logger.info(f"Analyzing news sentiment for {away_team} @ {home_team}")
            
            # Analyze news sentiment for both teams
            home_sentiment = await self._analyze_team_sentiment(home_team)
            away_sentiment = await self._analyze_team_sentiment(away_team)
            
            # Calculate sentiment differential impact
            sentiment_analysis = self._calculate_sentiment_impact(home_team, away_team, home_sentiment, away_sentiment)
            
            # Generate prediction based on sentiment
            prediction = self._calculate_sentiment_prediction(home_team, away_team, sentiment_analysis)
            
            # Generate detailed reasoning
            reasoning = self._generate_sentiment_reasoning(
                home_team, away_team, home_sentiment, away_sentiment, prediction
            )
            
            result = {
                "winner": prediction["winner"],
                "confidence": prediction["confidence"],
                "reasoning": reasoning,
                "home_sentiment": home_sentiment,
                "away_sentiment": away_sentiment,
                "sentiment_differential": sentiment_analysis["differential"],
                "key_factors": sentiment_analysis["key_factors"],
                "data_source": "real_news" if self.use_real_news else "simulated"
            }
            
            self.logger.info(f"Sentiment analysis complete: {prediction['winner']} wins ({prediction['confidence']:.1%})")
            self.status = "active"
            
            return result
            
        except Exception as e:
            self.status = "error"
            self.logger.error(f"Error in sentiment analysis: {e}")
            raise
    
    async def _analyze_team_sentiment(self, team_name: str) -> Dict[str, Any]:
        """Get sentiment analysis from real news sources or simulation"""
        
        # Check cache first
        cache_key = f"{team_name}_sentiment"
        if cache_key in self.news_cache:
            data, timestamp = self.news_cache[cache_key]
            if datetime.now() - timestamp < self.cache_duration:
                self.logger.debug(f"Using cached sentiment data for {team_name}")
                return data
        
        try:
            if self.use_real_news and self.news_collector:
                # Get real news data
                real_news_data = await self.news_collector.get_team_news(team_name)
                
                # Convert real data to expected format
                sentiment_data = {
                    'team': team_name,
                    'overall_sentiment': real_news_data.get('sentiment_score', 0.0),
                    'sentiment_level': real_news_data.get('sentiment_level', 'neutral'),
                    'news_analysis': real_news_data.get('analysis', {}),
                    'key_headlines': real_news_data.get('key_headlines', []),
                    'article_count': real_news_data.get('article_count', 0),
                    'key_news_items': self._convert_headlines_to_news_items(
                        real_news_data.get('key_headlines', []),
                        real_news_data.get('analysis', {})
                    ),
                    'data_source': 'real_news'
                }
                
                # Cache the result
                self.news_cache[cache_key] = (sentiment_data, datetime.now())
                
                self.logger.info(f"Retrieved real news sentiment for {team_name}: {sentiment_data['sentiment_level']}")
                return sentiment_data
                
        except Exception as e:
            self.logger.warning(f"Real news analysis failed for {team_name}: {e}. Using simulation fallback.")
        
        # Fallback to simulation
        return await self._simulate_team_sentiment(team_name)
    
    def _convert_headlines_to_news_items(self, headlines: List[Dict], analysis: Dict) -> List[Dict]:
        """Convert real news headlines to the expected news items format"""
        news_items = []
        
        for headline_data in headlines[:5]:  # Limit to top 5 headlines
            headline = headline_data.get('title', '')
            sentiment = headline_data.get('sentiment', 0.0)
            
            # Categorize the headline
            category = self._categorize_headline(headline)
            
            # Convert sentiment to impact score
            impact = sentiment * 0.15  # Scale sentiment to impact range
            
            news_item = {
                'headline': headline,
                'impact': round(impact, 3),
                'category': category,
                'type': 'positive' if impact > 0.02 else 'negative' if impact < -0.02 else 'neutral',
                'source': headline_data.get('source', 'unknown')
            }
            news_items.append(news_item)
        
        return news_items
    
    def _categorize_headline(self, headline: str) -> str:
        """Categorize a headline into news categories"""
        headline_lower = headline.lower()
        
        # Keywords for each category
        category_keywords = {
            'injuries': ['injury', 'injured', 'hurt', 'protocol', 'questionable', 'doubtful', 'out', 'return'],
            'coaching': ['coach', 'coordinator', 'staff', 'play-calling', 'scheme', 'strategy'],
            'team_chemistry': ['locker room', 'team', 'unity', 'chemistry', 'leadership', 'argument', 'conflict'],
            'momentum': ['streak', 'win', 'loss', 'performance', 'dominant', 'struggling', 'confidence'],
            'motivation': ['playoff', 'playoffs', 'motivation', 'revenge', 'rivalry', 'eliminated']
        }
        
        # Count keywords for each category
        category_scores = {}
        for category, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in headline_lower)
            if score > 0:
                category_scores[category] = score
        
        # Return the category with the highest score, or default to 'momentum'
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        
        return 'momentum'  # Default category
    
    async def _simulate_team_sentiment(self, team_name: str) -> Dict[str, Any]:
        """Generate simulated sentiment analysis for a team (fallback method)"""
        
        # Get team profile or use defaults
        team_profile = self.team_narratives.get(team_name, {
            "stability": 0.6, "media_attention": 0.6, "expectation_pressure": 0.6
        })
        
        # Generate news items for each category
        key_news_items = []
        category_sentiments = {}
        
        for category, scenarios in self.news_scenarios.items():
            # Select a news scenario based on team profile
            scenario = self._select_scenario_for_team(scenarios, team_profile, category)
            
            # Adjust impact based on team characteristics
            adjusted_impact = self._adjust_impact_for_team(
                scenario["impact"], team_profile, category
            )
            
            news_item = {
                "headline": scenario["headline"],
                "impact": round(adjusted_impact, 3),
                "category": category,
                "type": scenario["type"],
                "source": "simulation"
            }
            key_news_items.append(news_item)
            category_sentiments[category] = adjusted_impact
        
        # Calculate overall sentiment
        overall_sentiment = sum(category_sentiments.values())
        
        # Determine sentiment level
        if overall_sentiment > 0.05:
            sentiment_level = "positive"
        elif overall_sentiment < -0.05:
            sentiment_level = "negative"
        else:
            sentiment_level = "neutral"
        
        # Generate summary headlines
        key_headlines = [
            {"title": item["headline"], "sentiment": item["impact"]} 
            for item in sorted(key_news_items, key=lambda x: abs(x["impact"]), reverse=True)[:3]
        ]
        
        return {
            'team': team_name,
            'overall_sentiment': round(overall_sentiment, 3),
            'sentiment_level': sentiment_level,
            'news_analysis': category_sentiments,
            'key_headlines': key_headlines,
            'article_count': len(key_news_items),
            'key_news_items': key_news_items,
            'data_source': 'simulation'
        }
    
    def _select_scenario_for_team(self, scenarios: List[Dict], team_profile: Dict, category: str) -> Dict:
        """Select an appropriate news scenario based on team profile"""
        
        # Weight scenarios based on team characteristics
        weighted_scenarios = []
        
        for scenario in scenarios:
            weight = 1.0
            
            # Adjust weights based on team profile
            if scenario["type"] == "negative":
                # Less stable teams more likely to have negative news
                if team_profile.get("stability", 0.6) < 0.6:
                    weight *= 1.5
                # High media attention teams more likely to have negative coverage
                if team_profile.get("media_attention", 0.6) > 0.8:
                    weight *= 1.3
            
            elif scenario["type"] == "positive":
                # More stable teams more likely to have positive news
                if team_profile.get("stability", 0.6) > 0.7:
                    weight *= 1.3
            
            weighted_scenarios.append((scenario, weight))
        
        # Select scenario using weighted random choice
        total_weight = sum(weight for _, weight in weighted_scenarios)
        rand_val = random.random() * total_weight
        
        current_weight = 0
        for scenario, weight in weighted_scenarios:
            current_weight += weight
            if rand_val <= current_weight:
                return scenario
        
        # Fallback to last scenario
        return weighted_scenarios[-1][0]
    
    def _adjust_impact_for_team(self, base_impact: float, team_profile: Dict, category: str) -> float:
        """Adjust news impact based on team characteristics"""
        adjusted_impact = base_impact
        
        # High media attention teams are more affected by news
        if team_profile.get("media_attention", 0.6) > 0.8:
            adjusted_impact *= 1.2
        
        # Low stability teams are more affected by negative news
        if team_profile.get("stability", 0.6) < 0.6 and base_impact < 0:
            adjusted_impact *= 1.3
        
        # High expectation teams are more affected by momentum news
        if category == "momentum" and team_profile.get("expectation_pressure", 0.6) > 0.8:
            adjusted_impact *= 1.15
        
        return adjusted_impact
    
    def _calculate_sentiment_impact(self, home_team: str, away_team: str, 
                                  home_sentiment: Dict, away_sentiment: Dict) -> Dict[str, Any]:
        """Calculate the differential impact between teams"""
        
        home_score = home_sentiment["overall_sentiment"]
        away_score = away_sentiment["overall_sentiment"]
        
        # Calculate sentiment differential (positive favors home team)
        differential = home_score - away_score
        
        # Identify key factors driving the differential
        key_factors = []
        
        # Compare significant news items
        home_key_news = home_sentiment["key_news_items"]
        away_key_news = away_sentiment["key_news_items"]
        
        for news_item in home_key_news:
            if abs(news_item["impact"]) > 0.06:
                impact_type = "positive" if news_item["impact"] > 0 else "negative"
                key_factors.append(f"{home_team}: {impact_type} {news_item['category']} news - {news_item['headline'][:50]}...")
        
        for news_item in away_key_news:
            if abs(news_item["impact"]) > 0.06:
                impact_type = "positive" if news_item["impact"] > 0 else "negative"
                key_factors.append(f"{away_team}: {impact_type} {news_item['category']} news - {news_item['headline'][:50]}...")
        
        # Determine overall sentiment advantage
        if abs(differential) < 0.05:
            advantage = "neutral"
        elif differential > 0:
            advantage = home_team
        else:
            advantage = away_team
        
        return {
            "differential": round(differential, 3),
            "advantage": advantage,
            "key_factors": key_factors[:4],  # Limit to top 4 factors
            "impact_magnitude": abs(differential)
        }
    
    def _calculate_sentiment_prediction(self, home_team: str, away_team: str, 
                                  sentiment_analysis: Dict) -> Dict[str, Any]:
        """Calculate final sentiment-based prediction"""
        
        differential = sentiment_analysis["differential"]
        impact_magnitude = sentiment_analysis["impact_magnitude"]
        
        # Base prediction on sentiment differential
        if differential > 0.02:
            winner = home_team
            advantage = differential
        elif differential < -0.02:
            winner = away_team
            advantage = abs(differential)
        else:
            # FIXED: Very close sentiment - pick randomly instead of defaulting to home
            winner = home_team if random.random() > 0.5 else away_team
            advantage = 0.01
        
        # Convert sentiment advantage to confidence
        base_confidence = 0.5
        sentiment_boost = min(0.25, advantage * 2.0)  # Cap at 25% boost
        confidence = base_confidence + sentiment_boost
        
        # Adjust confidence based on impact magnitude
        if impact_magnitude > 0.15:
            confidence += 0.05  # More confident when sentiment is strong
        elif impact_magnitude < 0.05:
            confidence = max(0.51, confidence - 0.05)  # Less confident when sentiment is weak
        
        confidence = max(0.5, min(0.9, confidence))
        
        return {
            "winner": winner,
            "confidence": round(confidence, 3),
            "sentiment_advantage": round(advantage, 3),
            "primary_factor": self._identify_primary_sentiment_factor(sentiment_analysis)
        }
    
    def _identify_primary_sentiment_factor(self, sentiment_analysis: Dict) -> str:
        """Identify the most significant sentiment factor"""
        key_factors = sentiment_analysis["key_factors"]
        
        if not key_factors:
            return "neutral_news_cycle"
        
        # Look for the most impactful category mentioned in key factors
        factor_categories = {
            "team_chemistry": ["argument", "unity", "locker room", "cohesion", "chemistry", "leadership"],
            "coaching": ["coach", "coordinator", "play-calling", "job security", "friction", "staff"],
            "injuries": ["injury", "injured", "returns", "protocol", "questionable", "hurt"],
            "momentum": ["winning streak", "struggling", "dominant", "confidence", "streak", "performance"],
            "motivation": ["playoff", "revenge", "eliminated", "motivation", "rivalry", "playoffs"]
        }
        
        for category, keywords in factor_categories.items():
            for factor in key_factors:
                if any(keyword in factor.lower() for keyword in keywords):
                    return category
        
        return "general_sentiment"
    
    def _generate_sentiment_reasoning(self, home_team: str, away_team: str, 
                                    home_sentiment: Dict, away_sentiment: Dict, 
                                    prediction: Dict) -> str:
        """Generate human-readable sentiment reasoning"""
        
        reasoning_parts = []
        
        # Data source note
        data_source = home_sentiment.get('data_source', 'unknown')
        if data_source == 'real_news':
            reasoning_parts.append("Based on real-time news analysis")
        
        # Overall sentiment summary
        home_level = home_sentiment["sentiment_level"]
        away_level = away_sentiment["sentiment_level"]
        
        if home_level == away_level == "neutral":
            reasoning_parts.append("Both teams showing neutral sentiment in recent news coverage")
        elif home_level != away_level:
            if home_sentiment["overall_sentiment"] > away_sentiment["overall_sentiment"]:
                reasoning_parts.append(f"{home_team} showing {home_level} news sentiment vs {away_team}'s {away_level} coverage")
            else:
                reasoning_parts.append(f"{away_team} showing {away_level} news sentiment vs {home_team}'s {home_level} coverage")
        
        # Key news factors (top 2 most significant)
        key_factors = []
        home_key_news = home_sentiment["key_news_items"]
        away_key_news = away_sentiment["key_news_items"]
        
        all_significant_news = []
        for news_item in home_key_news + away_key_news:
            if abs(news_item["impact"]) > 0.07:
                team = home_team if news_item in home_key_news else away_team
                impact_desc = "positive" if news_item["impact"] > 0 else "negative"
                all_significant_news.append((abs(news_item["impact"]), f"{team} has {impact_desc} {news_item['category']} news"))
        
        # Sort by impact magnitude and take top 2
        all_significant_news.sort(reverse=True)
        reasoning_parts.extend([news[1] for news in all_significant_news[:2]])
        
        # Prediction confidence explanation
        confidence = prediction["confidence"]
        if confidence > 0.7:
            reasoning_parts.append("High confidence due to clear sentiment advantage")
        elif confidence > 0.6:
            reasoning_parts.append("Moderate confidence based on news sentiment differential")
        else:
            reasoning_parts.append("Low confidence - news sentiment provides minimal edge")
        
        # Add article count context if using real news
        if data_source == 'real_news':
            total_articles = home_sentiment.get('article_count', 0) + away_sentiment.get('article_count', 0)
            if total_articles > 0:
                reasoning_parts.append(f"Analysis based on {total_articles} recent articles")
        
        return ". ".join(reasoning_parts) + "."

    async def clear_news_cache(self, team_name: str = None):
        """Clear cached news data for a team or all teams"""
        if team_name:
            cache_key = f"{team_name}_sentiment"
            if cache_key in self.news_cache:
                del self.news_cache[cache_key]
        else:
            self.news_cache.clear()
    
    async def get_news_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostics about news data sources"""
        return {
            'using_real_news': self.use_real_news,
            'cache_size': len(self.news_cache),
            'cache_keys': list(self.news_cache.keys()),
            'collector_status': 'active' if self.news_collector else 'inactive'
        }