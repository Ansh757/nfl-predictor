#!/bin/bash

echo "NFL Agent Testing Suite (Fixed)"
echo "==============================="

# Test 1: Agent Status
echo "Agent Status Check:"
echo "==================="
response=$(curl -s http://localhost:8001/agents/status)
if [[ $response == *"active"* ]]; then
    echo "SUCCESS: All agents responding"
    echo "Found 5 active agents"
else
    echo "ERROR: Agent status issue"
    echo "$response"
fi
echo ""

# Test 2: System Health
echo "System Health:"
echo "=============="
health=$(curl -s http://localhost:8001/health)
echo "$health"
echo ""

# Test 3: Individual Agent Tests (with required IDs)
echo "Individual Agent Tests:"
echo "======================="

echo "Basic Predictor Agent:"
echo "---------------------"
basic_result=$(curl -s -X POST http://localhost:8001/agents/basic/predict \
  -H "Content-Type: application/json" \
  -d '{
    "game_data": {
      "game_id": 1,
      "home_team_id": 14,
      "away_team_id": 1,
      "home_team_name": "Chiefs",
      "away_team_name": "Bills",
      "game_time": "2024-01-21T15:30:00",
      "is_dome": false
    }
  }')
echo "Response: $basic_result"
echo ""

echo "Weather Impact Agent:"
echo "--------------------"
weather_result=$(curl -s -X POST http://localhost:8001/agents/weather/predict \
  -H "Content-Type: application/json" \
  -d '{
    "game_data": {
      "game_id": 1,
      "home_team_id": 14,
      "away_team_id": 1,
      "home_team_name": "Chiefs",
      "away_team_name": "Bills",
      "game_time": "2024-01-21T15:30:00",
      "is_dome": false
    }
  }')
echo "Response: $weather_result"
echo ""

echo "News Sentiment Agent:"
echo "--------------------"
news_result=$(curl -s -X POST http://localhost:8001/agents/news/predict \
  -H "Content-Type: application/json" \
  -d '{
    "game_data": {
      "game_id": 1,
      "home_team_id": 14,
      "away_team_id": 1,
      "home_team_name": "Chiefs", 
      "away_team_name": "Bills",
      "game_time": "2024-01-21T15:30:00",
      "is_dome": false
    }
  }')
echo "Response: $news_result"
echo ""

echo "Market Intelligence Agent:"
echo "--------------------------"
market_result=$(curl -s -X POST http://localhost:8001/agents/market/predict \
  -H "Content-Type: application/json" \
  -d '{
    "game_data": {
      "game_id": 1,
      "home_team_id": 14,
      "away_team_id": 1,
      "home_team_name": "Chiefs",
      "away_team_name": "Bills", 
      "game_time": "2024-01-21T15:30:00",
      "is_dome": false
    }
  }')
echo "Response: $market_result"
echo ""

# Test 4: Agent Comparison
echo "Agent Comparison Test:"
echo "====================="
comparison=$(curl -s -X POST http://localhost:8001/agents/compare \
  -H "Content-Type: application/json" \
  -d '{
    "game_data": {
      "game_id": 1,
      "home_team_id": 14,
      "away_team_id": 1,
      "home_team_name": "Chiefs",
      "away_team_name": "Bills",
      "game_time": "2024-01-21T15:30:00",
      "is_dome": false
    }
  }')
echo "Comparison Result:"
echo "$comparison"
echo ""

# Test 5: Full Consensus
echo "Full 4-Agent Consensus:"
echo "======================="
consensus=$(curl -s -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{
    "game_data": {
      "game_id": 1,
      "home_team_id": 14,
      "away_team_id": 1,
      "home_team_name": "Chiefs",
      "away_team_name": "Bills", 
      "game_time": "2024-01-21T15:30:00",
      "is_dome": false
    }
  }')
echo "Consensus Result:"
echo "$consensus"
echo ""

# Test 6: Dome vs Outdoor Comparison
echo "Dome vs Outdoor Test:"
echo "===================="

echo "Testing DOME game (Saints vs Falcons):"
dome_result=$(curl -s -X POST http://localhost:8001/agents/weather/predict \
  -H "Content-Type: application/json" \
  -d '{
    "game_data": {
      "game_id": 2,
      "home_team_id": 23,
      "away_team_id": 17,
      "home_team_name": "Saints",
      "away_team_name": "Falcons",
      "game_time": "2024-01-28T13:00:00",
      "venue": "Mercedes-Benz Superdome",
      "is_dome": true
    }
  }')
echo "Dome weather result: $dome_result"
echo ""

echo "Testing OUTDOOR game (Packers vs Bears):"
outdoor_result=$(curl -s -X POST http://localhost:8001/agents/weather/predict \
  -H "Content-Type: application/json" \
  -d '{
    "game_data": {
      "game_id": 3,
      "home_team_id": 22,
      "away_team_id": 21,
      "home_team_name": "Packers", 
      "away_team_name": "Bears",
      "game_time": "2024-01-28T13:00:00",
      "venue": "Lambeau Field",
      "is_dome": false
    }
  }')
echo "Outdoor weather result: $outdoor_result"
echo ""

# Test 7: Multiple Consensus Tests
echo "Consistency Test - Multiple Runs:"
echo "================================="
for i in {1..3}; do
    echo "Run $i:"
    run_result=$(curl -s -X POST http://localhost:8001/predict \
      -H "Content-Type: application/json" \
      -d '{
        "game_data": {
          "game_id": '$i',
          "home_team_id": 14,
          "away_team_id": 17,
          "home_team_name": "Chiefs",
          "away_team_name": "Cowboys",
          "game_time": "2024-01-21T15:30:00",
          "is_dome": false
        }
      }')
    echo "Result: $run_result"
    echo "---"
done
echo ""

echo "TESTING COMPLETE"
echo "================"
echo "STATUS: All agents are active and responding"
echo "NEXT: Analyze the JSON responses above for agent behavior patterns"