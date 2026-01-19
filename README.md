# Overview
# 🏈 NFL Prediction System

Ensemble prediction system combining statistical models and real-time data to predict NFL games with **74.7% accuracy**.

## 🎯 Results

| Metric | Value |
|--------|-------|
| Average Accuracy | **74.7%** (over 3 weeks) |
| Week 1 | 75% (12/16) |
| Week 2 | 68% (11/16) |
| Week 3 | 81% (13/16) |

**Comparison:** Most professional models achieve 55-60% accuracy.

## 🧠 How It Works

Ensemble system combining 4 specialized predictors:

1. **Statistical Predictor**: Analyzes team performance metrics
   - Win/loss records
   - Point differential
   - Recent form (last 4 games)
   - Home/away splits

2. **Weather Analyzer**: Real-time weather impact
   - Live data from Open-Meteo & NOAA APIs
   - Team weather performance profiles
   - Historical weather impacts on gameplay

3. **News Sentiment**: Media coverage analysis
   - Real-time news scraping
   - Team morale indicators
   - Momentum factors

4. **Market Analyzer**: Betting market patterns
   - Line movements
   - Public vs sharp money
   - Market efficiency indicators

Each predictor votes, weighted by historical accuracy.

## 🚀 Tech Stack

- **Backend**: Java Spring Boot API (primary), Python FastAPI agent service, Docker
- **Data Sources**: ESPN API, Open-Meteo, NOAA, RSS feeds
- **Frontend**: React dashboard, React Native (Next)
- **Database**: PostgreSQL (primary), SQLite (schedule seed data)

## 📊 Key Features

- Real team statistics from ESPN
- Live weather data (no API key required)
- Bias elimination (60% home picks vs industry 100%)
- Confidence scoring for each prediction
- Dockerized for easy deployment

## 🔧 Setup
# Live Demo
Link: https://nfl-predictor-system-production.up.railway.app/
- Please Note: This a proof of Concept. React Native App is still in progress.
- Wanted to ensure that the agents are actually working accurately before developing an entire mobile application.

# For Developers (Source Code) 
```bash
git clone https://github.com/Ansh757/nfl-predictor.git

Add .env (to add your OWN WEATHER_API_KEY)

docker-compose up -d

```

### Service Ports (Docker)
- **Spring Boot backend**: http://localhost:8080
- **Python agent service**: http://localhost:8001
