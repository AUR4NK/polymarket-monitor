# 🎯 Polymarket BTC 15-Minute Monitor

24/7 monitoring service for Polymarket BTC 15-minute prediction markets with real-time notifications.

## 🚀 Features

- **Continuous Monitoring**: Polls Polymarket API every 2 minutes to catch ALL new markets
- **Smart Detection**: Identifies markets that just started (0-3 minutes old)
- **AI Predictions**: Generates UP/DOWN predictions based on:
  - BTC momentum (24h price change)
  - Crowd sentiment (market odds)
  - Volume analysis
- **Real-time Alerts**: Sends detailed notifications via webhook
- **Risk Analysis**: Warns about low-volume markets

## 📊 How It Works

1. **Polling**: Every 2 minutes, fetches active BTC 15-minute markets from Polymarket
2. **Timing Analysis**: Calculates market start time and runtime
3. **New Market Detection**: Identifies markets running for 0-3 minutes
4. **BTC Data**: Fetches current BTC price and 24h change from CoinGecko
5. **Prediction Engine**: Analyzes momentum, sentiment, and volume
6. **Notification**: Sends formatted alert with prediction and analysis

## 🔧 Deployment on Render.com

### Environment Variables

Set the following in Render dashboard:

```
NEBULA_WEBHOOK_URL=https://nebula.gg/api/webhooks/threads/YOUR_THREAD_ID/messages
```

### Deploy Steps

1. **Create Web Service** on Render
2. **Connect GitHub Repository**: `AUR4NK/polymarket-monitor`
3. **Configure Service**:
   - **Name**: `polymarket-btc-monitor`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python render_monitor.py`
4. **Add Environment Variable**: `NEBULA_WEBHOOK_URL`
5. **Deploy**: Click "Create Web Service"

### Render Configuration

- **Instance Type**: Free tier (512MB RAM) is sufficient
- **Auto-Deploy**: Enabled (deploys on git push)
- **Health Check**: Disabled (background service)

## 📦 Dependencies

```
httpx>=0.27.0
```

## 🎯 Notification Format

Each alert includes:

- ⏰ **Market Start Time** (WIB timezone)
- 🔗 **Market URL** (direct link to Polymarket)
- 📊 **Prediction**: UP/DOWN with confidence level
- 💡 **Analysis**: Detailed reasoning
- 💰 **Market Conditions**: BTC price, odds, volume
- ⏱️ **Timing**: Start time, close time, time remaining
- ⚠️ **Risk Warnings**: For low-volume markets

## 🔐 Security

- No API keys required (public APIs only)
- Webhook URL stored as environment variable
- No sensitive data logged

## 📈 Performance

- **Check Interval**: 2 minutes (120 seconds)
- **Response Time**: ~2-3 seconds per check
- **Memory Usage**: ~50-100MB
- **CPU Usage**: Minimal (<5% on free tier)

## 🛠️ Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variable
export NEBULA_WEBHOOK_URL="your_webhook_url"

# Run monitor
python render_monitor.py
```

## 📝 License

MIT License - feel free to use and modify!

## 🤝 Contributing

Issues and PRs welcome!

---

**Built with ❤️ for Polymarket traders**
