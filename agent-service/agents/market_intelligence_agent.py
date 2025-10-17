import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import logging

class MarketIntelligenceAgent:
    """
    Market Intelligence Analysis Agent for NFL Games
    
    This agent analyzes betting market patterns and movements:
    - Opening vs current betting lines
    - Sharp money vs public betting patterns
    - Line movement velocity and timing
    - Steam moves and reverse line movement
    - Injury/news impact on market pricing
    - Cross-market arbitrage opportunities
    """
    
    def __init__(self, name: str):
        self.name = name
        self.status = "active"
        self.last_activity = datetime.now()
        self.logger = logging.getLogger(f"agents.{name}")
        
        # Market analysis parameters
        self.market_factors = {
            "line_movement": {"weight": 0.35, "max_impact": 0.20},
            "sharp_money": {"weight": 0.25, "max_impact": 0.15},
            "public_sentiment": {"weight": 0.20, "max_impact": 0.12},
            "steam_moves": {"weight": 0.15, "max_impact": 0.10},
            "reverse_line": {"weight": 0.05, "max_impact": 0.08}
        }
        
        # Simulated sportsbook characteristics
        self.sportsbooks = {
            "pinnacle": {"sharp_weight": 0.9, "public_weight": 0.1, "reputation": "sharp"},
            "draftkings": {"sharp_weight": 0.6, "public_weight": 0.4, "reputation": "recreational"},
            "fanduel": {"sharp_weight": 0.6, "public_weight": 0.4, "reputation": "recreational"},
            "caesars": {"sharp_weight": 0.7, "public_weight": 0.3, "reputation": "mixed"},
            "betmgm": {"sharp_weight": 0.65, "public_weight": 0.35, "reputation": "mixed"}
        }
        
        # Market scenario templates
        self.market_scenarios = {
            "sharp_money": [
                {"pattern": "early_sharp", "impact": 0.12, "description": "Sharp money hit immediately after opening"},
                {"pattern": "late_sharp", "impact": 0.10, "description": "Professional money came in close to game time"},
                {"pattern": "steam_move", "impact": 0.15, "description": "Synchronized betting across multiple books"},
                {"pattern": "reverse_engineer", "impact": 0.08, "description": "Sharp bettors taking unpopular side"}
            ],
            "public_patterns": [
                {"pattern": "public_favorite", "impact": -0.06, "description": "Heavy public action on popular team"},
                {"pattern": "media_hype", "impact": -0.08, "description": "Public overreacting to media narratives"},
                {"pattern": "recency_bias", "impact": -0.05, "description": "Public betting recent performance trends"},
                {"pattern": "contrarian_value", "impact": 0.07, "description": "Value found fading public sentiment"}
            ],
            "line_movement": [
                {"pattern": "significant_move", "impact": 0.11, "description": "Line moved 2+ points without major news"},
                {"pattern": "injury_reaction", "impact": 0.09, "description": "Market adjusted quickly to injury news"},
                {"pattern": "weather_adjustment", "impact": 0.06, "description": "Line shifted based on weather forecast"},
                {"pattern": "stable_line", "impact": 0.02, "description": "Line remained steady despite betting action"}
            ]
        }
        
        # Team market characteristics
        self.team_market_profiles = {
            "Cowboys": {"public_popularity": 0.9, "media_attention": 1.0, "sharp_respect": 0.6},
            "Chiefs": {"public_popularity": 0.85, "media_attention": 0.9, "sharp_respect": 0.9},
            "Patriots": {"public_popularity": 0.8, "media_attention": 0.8, "sharp_respect": 0.7},
            "Packers": {"public_popularity": 0.75, "media_attention": 0.7, "sharp_respect": 0.8},
            "49ers": {"public_popularity": 0.7, "media_attention": 0.75, "sharp_respect": 0.85},
            "Bills": {"public_popularity": 0.6, "media_attention": 0.6, "sharp_respect": 0.8},
            "Ravens": {"public_popularity": 0.65, "media_attention": 0.6, "sharp_respect": 0.85},
            "Steelers": {"public_popularity": 0.8, "media_attention": 0.7, "sharp_respect": 0.7}
        }
        
        self.logger.info(f"MarketIntelligenceAgent '{name}' initialized with {len(self.sportsbooks)} sportsbook profiles")
    
    async def get_status(self) -> Dict[str, Any]:
        """Return current agent status"""
        return {
            "status": self.status,
            "last_activity": self.last_activity,
            "message": f"Market analysis ready. Monitoring {len(self.sportsbooks)} sportsbooks and betting patterns."
        }
    
    async def refresh(self):
        """Refresh agent data and status"""
        self.last_activity = datetime.now()
        self.logger.info("Market intelligence agent refreshed")
    
    async def predict_game(self, game_data, game_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market intelligence for game outcome prediction
        
        Args:
            game_data: Game information
            game_context: Additional context data
            
        Returns:
            Dictionary with market-based prediction
        """
        self.last_activity = datetime.now()
        self.status = "analyzing_markets"
        
        try:
            home_team = game_data.home_team_name
            away_team = game_data.away_team_name
            
            self.logger.info(f"Analyzing market intelligence for {away_team} @ {home_team}")
            
            # Simulate market data collection
            market_data = await self._collect_market_data(home_team, away_team)
            
            # Analyze betting patterns
            betting_analysis = self._analyze_betting_patterns(market_data, home_team, away_team)
            
            # Calculate market-based prediction
            prediction = self._calculate_market_prediction(home_team, away_team, betting_analysis, market_data)
            
            # Generate market reasoning
            reasoning = self._generate_market_reasoning(
                home_team, away_team, market_data, betting_analysis, prediction
            )
            
            result = {
                "winner": prediction["winner"],
                "confidence": prediction["confidence"],
                "reasoning": reasoning,
                "market_data": market_data,
                "betting_analysis": betting_analysis,
                "market_edge": prediction["market_edge"],
                "sharp_consensus": betting_analysis["sharp_consensus"]
            }
            
            self.logger.info(f"Market analysis complete: {prediction['winner']} wins ({prediction['confidence']:.1%})")
            self.status = "active"
            
            return result
            
        except Exception as e:
            self.status = "error"
            self.logger.error(f"Error in market analysis: {e}")
            raise
    
    async def _collect_market_data(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """Simulate collection of betting market data"""
        await asyncio.sleep(0.15)  # Simulate market data collection time
        
        # Generate realistic betting line progression
        opening_line = self._generate_opening_line(home_team, away_team)
        current_line = self._simulate_line_movement(opening_line, home_team, away_team)
        
        # Generate betting volume and money percentages
        betting_splits = self._generate_betting_splits(home_team, away_team)
        
        # Generate sportsbook lines
        sportsbook_lines = self._generate_sportsbook_lines(current_line)
        
        # Market timing analysis
        line_history = self._generate_line_history(opening_line, current_line)
        
        return {
            "opening_line": opening_line,
            "current_line": current_line,
            "line_movement": current_line - opening_line,
            "betting_splits": betting_splits,
            "sportsbook_lines": sportsbook_lines,
            "line_history": line_history,
            "market_timestamp": datetime.now()
        }
    
    def _generate_opening_line(self, home_team: str, away_team: str) -> float:
        """Generate realistic opening betting line"""
        # FIXED: Start neutral (0 = pick'em), no automatic home bias
        base_line = 0.0
        
        # Adjust based on team market profiles
        home_profile = self.team_market_profiles.get(home_team, {"public_popularity": 0.5, "sharp_respect": 0.5})
        away_profile = self.team_market_profiles.get(away_team, {"public_popularity": 0.5, "sharp_respect": 0.5})
        
        # Sharp respect differential affects opening line
        sharp_differential = home_profile["sharp_respect"] - away_profile["sharp_respect"]
        base_line += sharp_differential * 3  # Up to 3-point adjustment
        
        # Add some randomness for realistic variation
        base_line += random.uniform(-1.5, 1.5)
        
        return round(base_line * 2) / 2  # Round to nearest 0.5
    
    def _simulate_line_movement(self, opening_line: float, home_team: str, away_team: str) -> float:
        """Simulate how the line moves from opening to current"""
        home_profile = self.team_market_profiles.get(home_team, {"public_popularity": 0.5})
        away_profile = self.team_market_profiles.get(away_team, {"public_popularity": 0.5})
        
        # Public teams tend to move toward them (becoming more favored)
        public_differential = home_profile["public_popularity"] - away_profile["public_popularity"]
        
        # Simulate movement patterns
        movement_scenarios = [
            {"pattern": "sharp_early", "move": -public_differential * 2, "probability": 0.3},
            {"pattern": "public_late", "move": public_differential * 1.5, "probability": 0.4},
            {"pattern": "steam_move", "move": random.choice([-2, -1.5, 1.5, 2]), "probability": 0.2},
            {"pattern": "stable", "move": random.uniform(-0.5, 0.5), "probability": 0.1}
        ]
        
        # Select movement pattern
        rand = random.random()
        cumulative_prob = 0
        for scenario in movement_scenarios:
            cumulative_prob += scenario["probability"]
            if rand <= cumulative_prob:
                movement = scenario["move"]
                break
        else:
            movement = 0
        
        current_line = opening_line + movement
        return round(current_line * 2) / 2
    
    def _generate_betting_splits(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """Generate realistic betting volume and money splits"""
        home_profile = self.team_market_profiles.get(home_team, {"public_popularity": 0.5})
        away_profile = self.team_market_profiles.get(away_team, {"public_popularity": 0.5})
        
        # Public popularity affects bet count percentage
        home_popularity = home_profile["public_popularity"]
        away_popularity = away_profile["public_popularity"]
        
        # Calculate bet percentages (public follows popularity)
        total_popularity = home_popularity + away_popularity
        home_bet_percentage = (home_popularity / total_popularity) * 100
        home_bet_percentage += random.uniform(-10, 10)  # Add variance
        home_bet_percentage = max(20, min(80, home_bet_percentage))  # Clamp realistic range
        
        # Money percentages can differ from bet percentages (sharp vs public)
        # If public is heavily on one side, sharp money might be on the other
        if home_bet_percentage > 65:  # Heavy public on home team
            home_money_percentage = home_bet_percentage - random.uniform(5, 15)
        elif home_bet_percentage < 35:  # Heavy public on away team
            home_money_percentage = home_bet_percentage + random.uniform(5, 15)
        else:  # Balanced betting
            home_money_percentage = home_bet_percentage + random.uniform(-5, 5)
        
        home_money_percentage = max(20, min(80, home_money_percentage))
        
        return {
            "home_bet_percentage": round(home_bet_percentage, 1),
            "away_bet_percentage": round(100 - home_bet_percentage, 1),
            "home_money_percentage": round(home_money_percentage, 1),
            "away_money_percentage": round(100 - home_money_percentage, 1),
            "bet_money_differential": abs(home_bet_percentage - home_money_percentage)
        }
    
    def _generate_sportsbook_lines(self, current_line: float) -> Dict[str, float]:
        """Generate lines across different sportsbooks"""
        lines = {}
        for book, profile in self.sportsbooks.items():
            # Sharp books (like Pinnacle) have tighter lines
            if profile["reputation"] == "sharp":
                variance = random.uniform(-0.25, 0.25)
            else:
                variance = random.uniform(-0.5, 0.5)
            
            book_line = current_line + variance
            lines[book] = round(book_line * 2) / 2
        
        return lines
    
    def _generate_line_history(self, opening_line: float, current_line: float) -> List[Dict[str, Any]]:
        """Generate realistic line movement history"""
        history = []
        
        # Create timeline of movements
        total_movement = current_line - opening_line
        time_points = 5  # 5 data points in history
        
        for i in range(time_points):
            progress = (i + 1) / time_points
            # Non-linear movement (more movement closer to game time)
            movement_progress = progress ** 1.5
            
            line_at_time = opening_line + (total_movement * movement_progress)
            hours_ago = (time_points - i) * 6  # Every 6 hours
            
            history.append({
                "line": round(line_at_time * 2) / 2,
                "timestamp": datetime.now() - timedelta(hours=hours_ago),
                "hours_ago": hours_ago
            })
        
        return history
    
    def _analyze_betting_patterns(self, market_data: Dict, home_team: str, away_team: str) -> Dict[str, Any]:
        """Analyze betting patterns for intelligence signals"""
        
        betting_splits = market_data["betting_splits"]
        line_movement = market_data["line_movement"]
        
        # Detect sharp money indicators
        bet_money_diff = betting_splits["bet_money_differential"]
        sharp_money_detected = bet_money_diff > 8  # Significant difference indicates sharp action
        
        # Analyze line movement patterns
        if abs(line_movement) > 1.5:
            movement_significance = "high"
        elif abs(line_movement) > 0.5:
            movement_significance = "moderate"
        else:
            movement_significance = "low"
        
        # Determine sharp consensus
        if sharp_money_detected:
            # Sharp money typically correlates with money percentage being different from bet percentage
            home_money_pct = betting_splits["home_money_percentage"]
            home_bet_pct = betting_splits["home_bet_percentage"]
            
            if home_money_pct > home_bet_pct + 5:
                sharp_consensus = home_team
            else:
                sharp_consensus = away_team
        else:
            sharp_consensus = "unclear"
        
        # Generate market scenarios
        market_signals = self._identify_market_signals(market_data, sharp_money_detected, movement_significance)
        
        return {
            "sharp_money_detected": sharp_money_detected,
            "movement_significance": movement_significance,
            "sharp_consensus": sharp_consensus,
            "market_signals": market_signals,
            "public_sentiment": self._analyze_public_sentiment(betting_splits),
            "line_efficiency": self._assess_line_efficiency(market_data)
        }
    
    def _identify_market_signals(self, market_data: Dict, sharp_detected: bool, movement_sig: str) -> List[Dict[str, Any]]:
        """Identify specific market intelligence signals"""
        signals = []
        
        line_movement = market_data["line_movement"]
        betting_splits = market_data["betting_splits"]
        
        # Sharp money signal
        if sharp_detected:
            signals.append({
                "type": "sharp_money",
                "impact": 0.12,
                "description": f"Sharp money differential of {betting_splits['bet_money_differential']:.1f}% detected"
            })
        
        # Significant line movement signal
        if movement_sig == "high":
            signals.append({
                "type": "line_movement",
                "impact": 0.10,
                "description": f"Significant line movement of {abs(line_movement)} points"
            })
        
        # Reverse line movement (line moves opposite to public betting)
        home_bet_pct = betting_splits["home_bet_percentage"]
        if line_movement > 0.5 and home_bet_pct > 60:  # Line moved toward away team despite public on home
            signals.append({
                "type": "reverse_line",
                "impact": 0.08,
                "description": "Reverse line movement against public sentiment"
            })
        
        # Steam move indicator (rapid movement across books)
        sportsbook_lines = market_data["sportsbook_lines"]
        line_variance = max(sportsbook_lines.values()) - min(sportsbook_lines.values())
        if line_variance < 0.5 and abs(line_movement) > 1:
            signals.append({
                "type": "steam_move",
                "impact": 0.15,
                "description": "Steam move detected across multiple sportsbooks"
            })
        
        return signals
    
    def _analyze_public_sentiment(self, betting_splits: Dict) -> Dict[str, Any]:
        """Analyze public betting sentiment"""
        home_bet_pct = betting_splits["home_bet_percentage"]
        
        if home_bet_pct > 70:
            sentiment = "heavy_home"
            contrarian_value = "away"
        elif home_bet_pct < 30:
            sentiment = "heavy_away"
            contrarian_value = "home"
        elif home_bet_pct > 60:
            sentiment = "moderate_home"
            contrarian_value = "slight_away"
        elif home_bet_pct < 40:
            sentiment = "moderate_away"
            contrarian_value = "slight_home"
        else:
            sentiment = "balanced"
            contrarian_value = "none"
        
        return {
            "sentiment": sentiment,
            "contrarian_value": contrarian_value,
            "public_percentage": home_bet_pct
        }
    
    def _assess_line_efficiency(self, market_data: Dict) -> Dict[str, Any]:
        """Assess how efficiently the market is pricing the game"""
        sportsbook_lines = market_data["sportsbook_lines"]
        line_variance = max(sportsbook_lines.values()) - min(sportsbook_lines.values())
        
        if line_variance < 0.5:
            efficiency = "high"
            market_confidence = 0.85
        elif line_variance < 1.0:
            efficiency = "moderate"
            market_confidence = 0.7
        else:
            efficiency = "low"
            market_confidence = 0.55
        
        return {
            "efficiency": efficiency,
            "line_variance": line_variance,
            "market_confidence": market_confidence
        }
    
    def _calculate_market_prediction(self, home_team: str, away_team: str, betting_analysis: Dict, market_data: Dict) -> Dict[str, Any]:
        """Calculate final market-based prediction"""
        
        sharp_consensus = betting_analysis["sharp_consensus"]
        market_signals = betting_analysis["market_signals"]
        line_efficiency = betting_analysis["line_efficiency"]
        
        # Base prediction on sharp consensus
        if sharp_consensus == home_team:
            winner = home_team
            base_confidence = 0.6
        elif sharp_consensus == away_team:
            winner = away_team
            base_confidence = 0.6
        else:
            # FIXED: No clear sharp consensus - use market signals, not home bias
            if betting_analysis["public_sentiment"]["sentiment"].startswith("heavy_away"):
                winner = away_team
                base_confidence = 0.55
            elif betting_analysis["public_sentiment"]["sentiment"].startswith("heavy_home"):
                winner = home_team
                base_confidence = 0.55
            else:
                # True toss-up - pick randomly when market is balanced
                if abs(market_data["line_movement"]) < 0.5:
                    winner = home_team if random.random() > 0.5 else away_team
                else:
                    # Use line movement: positive = away favored, negative = home favored
                    winner = away_team if market_data["line_movement"] > 0 else home_team
                base_confidence = 0.51
        
        # Adjust confidence based on market signals
        signal_boost = sum(signal["impact"] for signal in market_signals) * 0.5
        
        # Adjust for market efficiency
        efficiency_boost = (line_efficiency["market_confidence"] - 0.7) * 0.2
        
        final_confidence = base_confidence + signal_boost + efficiency_boost
        final_confidence = max(0.5, min(0.85, final_confidence))
        
        # Calculate market edge
        market_edge = sum(signal["impact"] for signal in market_signals)
        
        return {
            "winner": winner,
            "confidence": round(final_confidence, 3),
            "market_edge": round(market_edge, 3),
            "primary_signal": market_signals[0]["type"] if market_signals else "market_efficiency"
        }
    
    def _generate_market_reasoning(self, home_team: str, away_team: str, market_data: Dict, 
                                 betting_analysis: Dict, prediction: Dict) -> str:
        """Generate human-readable market reasoning"""
        
        reasoning_parts = []
        
        # FIXED: Line movement summary with correct interpretation
        # Negative movement = line moved toward home team (home became more favored)
        # Positive movement = line moved toward away team (away became more favored)
        line_movement = market_data["line_movement"]
        if abs(line_movement) > 1:
            if line_movement > 0:
                reasoning_parts.append(f"Line moved {abs(line_movement)} points toward {away_team}")
            else:
                reasoning_parts.append(f"Line moved {abs(line_movement)} points toward {home_team}")
        
        # Sharp money analysis
        if betting_analysis["sharp_money_detected"]:
            sharp_consensus = betting_analysis["sharp_consensus"]
            reasoning_parts.append(f"Sharp money consensus favors {sharp_consensus}")
        
        # Key market signals
        market_signals = betting_analysis["market_signals"]
        if market_signals:
            top_signal = market_signals[0]
            reasoning_parts.append(f"Key signal: {top_signal['description']}")
        
        # Public sentiment
        public_sentiment = betting_analysis["public_sentiment"]
        if public_sentiment["contrarian_value"] != "none":
            reasoning_parts.append(f"Contrarian value detected on {public_sentiment['contrarian_value']} team")
        
        # Confidence explanation
        confidence = prediction["confidence"]
        if confidence > 0.75:
            reasoning_parts.append("High confidence due to strong market signals")
        elif confidence > 0.6:
            reasoning_parts.append("Moderate confidence based on market intelligence")
        else:
            reasoning_parts.append("Low confidence - market shows mixed signals")
        
        return ". ".join(reasoning_parts) + "."