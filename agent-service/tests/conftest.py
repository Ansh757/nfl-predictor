import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import logging

# Import your agent
try:
    from agents.news_sentiment_agent import NewsSentimentAgent
    IMPORT_SUCCESS = True
except ImportError as e:
    print(f"Failed to import NewsSentimentAgent: {e}")
    IMPORT_SUCCESS = False

# Skip all tests if import failed
pytestmark = pytest.mark.skipif(not IMPORT_SUCCESS, reason="NewsSentimentAgent import failed")

@pytest.fixture
def mock_game_data():
    """Mock game data fixture"""
    game_data = Mock()
    game_data.home_team_name = "Chiefs"
    game_data.away_team_name = "Bills"
    return game_data

@pytest.fixture
def game_context():
    """Game context fixture"""
    return {
        "week": 10,
        "season": 2024,
        "game_type": "regular"
    }

@pytest.fixture
def mock_news_response():
    """Mock news collector response"""
    return {
        'sentiment_score': 0.15,
        'sentiment_level': 'positive',
        'analysis': {
            'team_chemistry': 0.05,
            'coaching': 0.10,
            'injuries': -0.02,
            'momentum': 0.08,
            'motivation': 0.03
        },
        'key_headlines': [
            {
                'title': 'Chiefs show strong unity in practice',
                'sentiment': 0.8,
                'source': 'ESPN'
            },
            {
                'title': 'Coaching staff praised for innovative plays',
                'sentiment': 0.6,
                'source': 'NFL.com'
            }
        ],
        'article_count': 15
    }

class TestNewsSentimentAgent:
    """Test suite for News Sentiment Agent"""
    
    def test_agent_initialization_simulation_only(self):
        """Test agent initialization with simulation only"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        assert agent.name == "test_agent"
        assert agent.use_real_news == False
        assert agent.news_collector is None
        assert agent.status == "active"
    
    def test_agent_initialization_real_news(self):
        """Test agent initialization with real news enabled"""
        # This will fall back to simulation if RealNewsCollector doesn't exist
        agent = NewsSentimentAgent("test_agent", use_real_news=True)
        
        assert agent.name == "test_agent"
        assert agent.status == "active"
    
    @pytest.mark.asyncio
    async def test_simulation_team_sentiment(self):
        """Test simulation sentiment analysis"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        result = await agent._simulate_team_sentiment("Cowboys")
        
        assert result['team'] == "Cowboys"
        assert result['data_source'] == 'simulation'
        assert 'overall_sentiment' in result
        assert 'key_news_items' in result
        assert len(result['key_news_items']) == 5  # One per category
        
        # Check sentiment is in valid range
        assert -1.0 <= result['overall_sentiment'] <= 1.0
    
    def test_headline_categorization(self):
        """Test headline categorization logic"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        test_cases = [
            ("Quarterback suffers knee injury", "injuries"),
            ("Coach praised for innovative strategy", "coaching"),
            ("Team shows unity in locker room", "team_chemistry"),
            ("Team rides 5-game winning streak", "momentum"),
            ("Playoff hopes fuel motivation", "motivation"),
            ("Generic sports news", "momentum")  # Default should be momentum
        ]
        
        for headline, expected_category in test_cases:
            category = agent._categorize_headline(headline)
            assert category == expected_category, f"Failed for: {headline}"
    
    def test_sentiment_impact_calculation(self):
        """Test sentiment differential calculation"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        home_sentiment = {
            'overall_sentiment': 0.10,
            'key_news_items': [
                {'impact': 0.08, 'headline': 'Positive news', 'category': 'momentum'}
            ]
        }
        
        away_sentiment = {
            'overall_sentiment': -0.05,
            'key_news_items': [
                {'impact': -0.07, 'headline': 'Negative news', 'category': 'injuries'}
            ]
        }
        
        result = agent._calculate_sentiment_impact("Chiefs", "Bills", home_sentiment, away_sentiment)
        
        assert abs(result['differential'] - 0.15) < 0.01
        assert result['advantage'] == "Chiefs"
        assert len(result['key_factors']) > 0
    
    def test_prediction_confidence_scaling(self):
        """Test prediction confidence calculation"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        # High differential should increase confidence
        high_diff_analysis = {'differential': 0.20, 'impact_magnitude': 0.20, 'key_factors': []}
        prediction = agent._calculate_sentiment_prediction("Chiefs", "Bills", high_diff_analysis)
        assert prediction['confidence'] > 0.65
        assert prediction['winner'] == "Chiefs"
        
        # Low differential should lower confidence
        low_diff_analysis = {'differential': 0.02, 'impact_magnitude': 0.02, 'key_factors': []}
        prediction = agent._calculate_sentiment_prediction("Chiefs", "Bills", low_diff_analysis)
        assert prediction['confidence'] < 0.60
        
        # Negative differential should favor away team
        negative_diff_analysis = {'differential': -0.15, 'impact_magnitude': 0.15, 'key_factors': []}
        prediction = agent._calculate_sentiment_prediction("Chiefs", "Bills", negative_diff_analysis)
        assert prediction['winner'] == "Bills"
    
    @pytest.mark.asyncio
    async def test_news_cache_functionality(self):
        """Test news caching system"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        # Add item to cache
        cache_key = "Chiefs_sentiment"
        test_data = {'team': 'Chiefs', 'sentiment': 0.1}
        agent.news_cache[cache_key] = (test_data, datetime.now())
        
        assert cache_key in agent.news_cache
        
        # Test cache expiration
        old_timestamp = datetime.now() - timedelta(hours=3)
        agent.news_cache[cache_key] = (test_data, old_timestamp)
        
        # Refresh should clear expired cache
        await agent.refresh()
        assert cache_key not in agent.news_cache
    
    @pytest.mark.asyncio
    async def test_full_game_prediction(self, mock_game_data, game_context):
        """Test complete game prediction flow"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        result = await agent.predict_game(mock_game_data, game_context)
        
        # Verify result structure
        required_keys = [
            'winner', 'confidence', 'reasoning', 'home_sentiment', 
            'away_sentiment', 'sentiment_differential', 'key_factors', 'data_source'
        ]
        
        for key in required_keys:
            assert key in result, f"Missing key: {key}"
        
        # Verify confidence is reasonable
        assert 0.5 <= result['confidence'] <= 0.9
        
        # Verify winner is one of the teams
        assert result['winner'] in ["Chiefs", "Bills"]
    
    @pytest.mark.asyncio
    async def test_status_reporting(self):
        """Test agent status reporting"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        status = await agent.get_status()
        
        assert 'status' in status
        assert 'last_activity' in status
        assert 'message' in status
        assert status['status'] == 'active'
    
    def test_team_profile_coverage(self):
        """Test that all major NFL teams have profiles"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        major_teams = [
            "Chiefs", "Bills", "Patriots", "Cowboys", "Packers", "49ers",
            "Ravens", "Steelers", "Eagles", "Rams"
        ]
        
        for team in major_teams:
            assert team in agent.team_narratives, f"Missing profile for {team}"
    
    def test_convert_headlines_to_news_items(self):
        """Test conversion of real headlines to news items format"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        headlines = [
            {'title': 'Team shows strong chemistry', 'sentiment': 0.8, 'source': 'ESPN'},
            {'title': 'Coach under pressure', 'sentiment': -0.6, 'source': 'NFL.com'}
        ]
        
        analysis = {'team_chemistry': 0.1, 'coaching': -0.08}
        
        result = agent._convert_headlines_to_news_items(headlines, analysis)
        
        assert len(result) == 2
        assert 'headline' in result[0]
        assert 'impact' in result[0]
        assert 'category' in result[0]
        
        # Check that sentiments are properly scaled to impact
        assert result[0]['impact'] > 0  # Positive sentiment
        assert result[1]['impact'] < 0  # Negative sentiment


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios"""
    
    @pytest.mark.asyncio
    async def test_api_timeout_scenario(self):
        """Test handling of API timeouts"""
        with patch('agents.news_sentiment_agent.RealNewsCollector') as mock_collector_class:
            mock_collector = AsyncMock()
            mock_collector.get_team_news.side_effect = asyncio.TimeoutError("Timeout")
            mock_collector_class.return_value = mock_collector
            
            agent = NewsSentimentAgent("test_agent", use_real_news=True)
            agent.news_collector = mock_collector
            
            # Should not raise exception and fallback to simulation
            result = await agent._analyze_team_sentiment("Chiefs")
            assert result['data_source'] == 'simulation'
    
    @pytest.mark.asyncio
    async def test_partial_data_scenario(self):
        """Test handling of incomplete API data"""
        incomplete_response = {
            'sentiment_score': 0.1,
            # Missing other fields
        }
        
        with patch('agents.news_sentiment_agent.RealNewsCollector') as mock_collector_class:
            mock_collector = AsyncMock()
            mock_collector.get_team_news.return_value = incomplete_response
            mock_collector_class.return_value = mock_collector
            
            agent = NewsSentimentAgent("test_agent", use_real_news=True)
            agent.news_collector = mock_collector
            
            result = await agent._analyze_team_sentiment("Chiefs")
            
            # Should handle missing fields gracefully
            assert 'overall_sentiment' in result
            assert result['sentiment_level'] == 'neutral'  # Default
            assert result['key_headlines'] == []  # Default
    
    @pytest.mark.asyncio
    async def test_real_news_success_scenario(self, mock_news_response):
        """Test successful real news integration"""
        with patch('news_sentiment_agent.RealNewsCollector') as mock_collector_class:
            mock_collector = AsyncMock()
            mock_collector.get_team_news.return_value = mock_news_response
            mock_collector_class.return_value = mock_collector
            
            agent = NewsSentimentAgent("test_agent", use_real_news=True)
            agent.news_collector = mock_collector
            
            result = await agent._analyze_team_sentiment("Chiefs")
            
            assert result['team'] == "Chiefs"
            assert result['overall_sentiment'] == 0.15
            assert result['sentiment_level'] == 'positive'
            assert result['data_source'] == 'real_news'
            mock_collector.get_team_news.assert_called_once_with("Chiefs")


class TestErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.mark.asyncio
    async def test_invalid_team_handling(self):
        """Test handling of invalid team names"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        # Should handle gracefully without crashing
        result = await agent._simulate_team_sentiment("InvalidTeam")
        assert result['team'] == "InvalidTeam"
        assert 'overall_sentiment' in result
    
    @pytest.mark.asyncio
    async def test_missing_game_data(self):
        """Test handling of invalid game data"""
        agent = NewsSentimentAgent("test_agent", use_real_news=False)
        
        mock_game = Mock()
        mock_game.home_team_name = None  # Invalid
        mock_game.away_team_name = "Bills"
        
        # Should raise an exception or handle gracefully
        with pytest.raises(Exception):
            await agent.predict_game(mock_game, {})


# Performance and stress tests
class TestPerformance:
    """Performance tests"""
    
    @pytest.mark.asyncio
    async def test_multiple_predictions_performance(self):
        """Test performance with multiple predictions"""
        agent = NewsSentimentAgent("perf_test", use_real_news=False)
        
        teams = ["Chiefs", "Bills", "Cowboys", "Patriots", "Packers"]
        start_time = datetime.now()
        
        for i in range(5):
            mock_game = Mock()
            mock_game.home_team_name = teams[i % len(teams)]
            mock_game.away_team_name = teams[(i + 1) % len(teams)]
            
            prediction = await agent.predict_game(mock_game, {"week": i + 1})
            assert 'winner' in prediction
            assert 'confidence' in prediction
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Should complete reasonably quickly (adjust threshold as needed)
        assert duration < 10.0, f"Performance test took too long: {duration} seconds"


if __name__ == "__main__":
    # Run pytest when script is executed directly
    pytest.main([__file__, "-v"])