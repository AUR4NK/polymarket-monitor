"""
Polymarket BTC 15M Continuous Monitor for Render.com
Polls every 2 minutes to catch ALL market starts (24/7)
Sends notifications to Nebula channel via webhook
"""
import httpx
from datetime import datetime, timezone, timedelta
import time
import json
import os
import sys

# Configuration
CHECK_INTERVAL = 120  # 2 minutes between checks
NEBULA_WEBHOOK_URL = os.getenv("NEBULA_WEBHOOK_URL")  # Set this in Render environment variables

def get_wib_time():
    """Get current time in WIB timezone"""
    wib = timezone(timedelta(hours=7))
    return datetime.now(timezone.utc).astimezone(wib)

def fetch_btc_price():
    """Fetch current BTC price and 24h change from CoinGecko"""
    try:
        response = httpx.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin",
                "vs_currencies": "usd",
                "include_24hr_change": "true"
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        btc_price = data["bitcoin"]["usd"]
        btc_change_24h = data["bitcoin"]["usd_24h_change"]
        
        return btc_price, btc_change_24h
    except Exception as e:
        print(f"❌ Error fetching BTC price: {e}")
        return None, None

def fetch_polymarket_markets():
    """Fetch all BTC 15-minute markets from Polymarket"""
    try:
        response = httpx.get(
            "https://gamma-api.polymarket.com/events",
            params={
                "tag": "btc-15m",
                "closed": "false",
                "active": "true",
                "archived": "false",
                "limit": 50
            },
            timeout=15
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching Polymarket markets: {e}")
        return []

def analyze_market_timing(market):
    """
    Analyze if market just started (0-3 minutes running)
    Returns: (is_new, start_time_wib, minutes_running)
    """
    try:
        # Try to parse end_date_iso (close time)
        end_time_str = market.get("end_date_iso")
        if not end_time_str:
            return False, None, None
            
        end_time_utc = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
        
        # Market duration is 15 minutes
        start_time_utc = end_time_utc - timedelta(minutes=15)
        now_utc = datetime.now(timezone.utc)
        
        # Check if market is currently running
        if now_utc < start_time_utc or now_utc > end_time_utc:
            return False, None, None
        
        # Calculate how long market has been running
        minutes_running = (now_utc - start_time_utc).total_seconds() / 60
        
        # Check if just started (0-3 minutes)
        is_new = 0 <= minutes_running <= 3
        
        wib = timezone(timedelta(hours=7))
        start_time_wib = start_time_utc.astimezone(wib)
        
        return is_new, start_time_wib, minutes_running
        
    except Exception as e:
        print(f"⚠️  Error analyzing timing: {e}")
        return False, None, None

def generate_prediction(btc_price, btc_change_24h, market):
    """
    Generate UP/DOWN prediction based on:
    1. BTC momentum (24h change)
    2. Crowd sentiment (odds)
    3. Volume analysis
    """
    try:
        # Get market odds
        markets_data = market.get("markets", [])
        if not markets_data or len(markets_data) < 2:
            return "UNKNOWN", "LOW", "Insufficient market data"
        
        # Find UP and DOWN outcomes
        up_market = next((m for m in markets_data if "up" in m.get("outcome", "").lower()), None)
        down_market = next((m for m in markets_data if "down" in m.get("outcome", "").lower()), None)
        
        if not up_market or not down_market:
            return "UNKNOWN", "LOW", "Cannot find UP/DOWN outcomes"
        
        # Get odds (outcomePrices are in format "0.XX")
        up_odds = float(up_market.get("outcomePrices", ["0.5"])[0]) * 100
        down_odds = float(down_market.get("outcomePrices", ["0.5"])[0]) * 100
        
        # Get volume
        volume = float(market.get("volume", 0))
        
        # Analysis factors
        factors = []
        score = 0  # Positive = UP, Negative = DOWN
        
        # Factor 1: BTC Momentum (weight: 40%)
        if btc_change_24h is not None:
            if btc_change_24h > 2:
                score += 2
                factors.append(f"BTC strong bullish momentum (+{btc_change_24h:.2f}%)")
            elif btc_change_24h > 0.5:
                score += 1
                factors.append(f"BTC bullish (+{btc_change_24h:.2f}%)")
            elif btc_change_24h < -2:
                score -= 2
                factors.append(f"BTC strong bearish momentum ({btc_change_24h:.2f}%)")
            elif btc_change_24h < -0.5:
                score -= 1
                factors.append(f"BTC bearish ({btc_change_24h:.2f}%)")
            else:
                factors.append(f"BTC neutral ({btc_change_24h:.2f}%)")
        
        # Factor 2: Crowd Sentiment (weight: 30%)
        odds_diff = up_odds - down_odds
        if odds_diff > 10:
            score += 1
            factors.append(f"Crowd leans UP ({up_odds:.0f}% vs {down_odds:.0f}%)")
        elif odds_diff < -10:
            score -= 1
            factors.append(f"Crowd leans DOWN ({up_odds:.0f}% vs {down_odds:.0f}%)")
        else:
            factors.append(f"Crowd neutral ({up_odds:.0f}% vs {down_odds:.0f}%)")
        
        # Factor 3: Volume Analysis (weight: 30%)
        if volume < 100:
            factors.append(f"⚠️ Very low volume (${volume:.0f}) - high risk!")
        elif volume < 500:
            factors.append(f"Low volume (${volume:.0f}) - moderate risk")
        else:
            factors.append(f"Good volume (${volume:.0f})")
        
        # Generate prediction
        if score >= 2:
            prediction = "UP 📈"
            confidence = "HIGH" if score >= 3 else "MEDIUM"
        elif score <= -2:
            prediction = "DOWN 📉"
            confidence = "HIGH" if score <= -3 else "MEDIUM"
        else:
            prediction = "NEUTRAL ➡️"
            confidence = "LOW"
        
        reasoning = "\n".join([f"  • {f}" for f in factors])
        
        return prediction, confidence, reasoning
        
    except Exception as e:
        return "UNKNOWN", "LOW", f"Error in prediction: {e}"

def format_notification(market, btc_price, btc_change_24h, start_time_wib, minutes_running):
    """Format notification message for Nebula channel"""
    
    # Generate prediction
    prediction, confidence, reasoning = generate_prediction(btc_price, btc_change_24h, market)
    
    # Get market details
    slug = market.get("slug", "unknown")
    market_url = f"https://polymarket.com/event/{slug}"
    
    # Get odds and volume
    markets_data = market.get("markets", [])
    up_market = next((m for m in markets_data if "up" in m.get("outcome", "").lower()), None)
    down_market = next((m for m in markets_data if "down" in m.get("outcome", "").lower()), None)
    
    up_odds = float(up_market.get("outcomePrices", ["0.5"])[0]) * 100 if up_market else 50
    down_odds = float(down_market.get("outcomePrices", ["0.5"])[0]) * 100 if down_market else 50
    volume = float(market.get("volume", 0))
    
    # Calculate close time
    close_time_wib = start_time_wib + timedelta(minutes=15)
    time_to_close_min = 15 - minutes_running
    
    # BTC momentum emoji
    btc_emoji = "📈" if btc_change_24h and btc_change_24h > 0 else "📉"
    
    # Volume warning
    volume_warning = ""
    if volume < 100:
        volume_warning = "\n\n⚠️ **CRITICAL WARNING: Very low volume - extremely high risk!**"
    elif volume < 500:
        volume_warning = "\n\n⚠️ **WARNING: Low volume - high risk!**"
    
    message = f"""🔔 **MARKET BARU DIMULAI!**

{'='*50}
⏰ **STARTED AT:** {start_time_wib.strftime('%H:%M:%S')} WIB
{'='*50}

🔗 {market_url}

📊 **PREDIKSI: {prediction} {confidence.upper()}**
Confidence: {confidence}

💡 **Analisis:**
{reasoning}

💰 **Market Conditions:**
- BTC: ${btc_price:,.0f} ({btc_change_24h:+.2f}% 24h) {btc_emoji}
- Odds: {up_odds:.0f}% UP / {down_odds:.0f}% DOWN
- Volume: ${volume:.0f}{volume_warning}

⏱️ **Timing:**
- Started: {start_time_wib.strftime('%H:%M')} WIB
- Closes: {close_time_wib.strftime('%H:%M')} WIB  
- Time to Close: {time_to_close_min:.1f} minutes
- Running: {minutes_running:.1f} minutes
"""
    
    return message

def send_notification(message):
    """Send notification to Nebula channel via webhook"""
    if not NEBULA_WEBHOOK_URL:
        print("⚠️  NEBULA_WEBHOOK_URL not set - notification not sent")
        print(f"\n{message}\n")
        return False
    
    try:
        response = httpx.post(
            NEBULA_WEBHOOK_URL,
            json={"message": message},
            timeout=10
        )
        response.raise_for_status()
        print("✅ Notification sent successfully")
        return True
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        print(f"\nMessage that failed to send:\n{message}\n")
        return False

def check_for_new_markets():
    """Main check function - polls markets and sends notifications"""
    now_wib = get_wib_time()
    print(f"\n{'='*60}")
    print(f"🔍 Checking for new markets at {now_wib.strftime('%H:%M:%S')} WIB")
    print(f"{'='*60}")
    
    # Fetch BTC price
    btc_price, btc_change_24h = fetch_btc_price()
    if btc_price:
        print(f"💰 BTC: ${btc_price:,.2f} ({btc_change_24h:+.2f}% 24h)")
    
    # Fetch markets
    markets = fetch_polymarket_markets()
    print(f"📊 Found {len(markets)} active markets")
    
    if not markets:
        print("⚠️  No markets found or API error")
        return
    
    # Check each market
    new_markets_found = 0
    for market in markets:
        is_new, start_time_wib, minutes_running = analyze_market_timing(market)
        
        if is_new:
            new_markets_found += 1
            slug = market.get("slug", "unknown")
            print(f"\n🎯 NEW MARKET DETECTED!")
            print(f"   Slug: {slug}")
            print(f"   Started: {start_time_wib.strftime('%H:%M:%S')} WIB")
            print(f"   Running: {minutes_running:.1f} minutes")
            
            # Format and send notification
            notification = format_notification(
                market, btc_price, btc_change_24h, 
                start_time_wib, minutes_running
            )
            send_notification(notification)
    
    if new_markets_found == 0:
        print("✅ No new markets (0-3 minutes old)")
    else:
        print(f"\n🎉 Total new markets detected: {new_markets_found}")

def main():
    """Main loop - runs continuously"""
    print("🚀 POLYMARKET BTC 15M MONITOR STARTED")
    print(f"⏱️  Check interval: {CHECK_INTERVAL} seconds (2 minutes)")
    print(f"🌐 Webhook URL configured: {'YES ✅' if NEBULA_WEBHOOK_URL else 'NO ❌'}")
    print(f"{'='*60}\n")
    
    if not NEBULA_WEBHOOK_URL:
        print("⚠️  WARNING: NEBULA_WEBHOOK_URL environment variable not set!")
        print("   Notifications will only be printed to console.\n")
    
    check_count = 0
    
    while True:
        try:
            check_count += 1
            print(f"\n📍 CHECK #{check_count}")
            
            check_for_new_markets()
            
            # Sleep until next check
            print(f"\n💤 Sleeping for {CHECK_INTERVAL} seconds...")
            print(f"⏰ Next check at: {(get_wib_time() + timedelta(seconds=CHECK_INTERVAL)).strftime('%H:%M:%S')} WIB")
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Monitor stopped by user")
            break
        except Exception as e:
            print(f"\n❌ Error in main loop: {e}")
            print("⏳ Waiting 60 seconds before retry...")
            time.sleep(60)

if __name__ == "__main__":
    main()
