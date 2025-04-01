import os
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets setup
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_name("config/trading-journal-credentials.json", SCOPE)
CLIENT = gspread.authorize(CREDS)

def sync_to_sheets(trade_id, symbol, pl, direction, sheet_name):
    """Sync trade data to Google Sheets."""
    sheet = CLIENT.open(sheet_name).sheet1
    sheet.append_row([trade_id, str(datetime.now().date()), symbol, direction, pl])
    print(f"Trade {trade_id} synced to Google Sheets.")

def analyze_market(emotions_file, sheet_name, symbol, trade_id, tf_label, tf_value, trend, stage, bars, avg_bars, key_levels, mas, validation_price, validation_hit, invalidation_price, invalidation_hit, overall_signal):
    """Analyze a market chart for a specific timeframe using form data."""
    print(f"\n[Analyzing {tf_label}: {tf_value} for {symbol}]")

    # Calculate expectancy
    expectancy = (bars / avg_bars) * 100

    # Calculate Bias
    if "bullish" in trend.lower() or "g" in trend.lower():
        bias = "100% Long" if "2" in stage else "50% Long"
    elif "bearish" in trend.lower() or "r" in trend.lower():
        bias = "100% Short" if "2" in stage else "50% Short"
    else:
        bias = "-"

    # Placeholder lights
    stage_light = "Grey"  # Simplified for now
    price_light = "Red"   # Simplified for now

    # Store data
    analysis_data = {
        "Trend": trend,
        "Stage": stage,
        "Bars": bars,
        "Expectancy": expectancy,
        "Key Levels": key_levels if key_levels else "None",
        "MAs": mas if mas else "None",
        "Bias": bias,
        "Stage Light": stage_light,
        "Price Light": price_light,
        "Validation": f"@{validation_price} [{validation_hit}]",
        "Invalidation": f"@{invalidation_price} [{invalidation_hit}]"
    }

    return analysis_data

def recall_analysis(emotions_file):
    """Display previous emotions from emotions.csv."""
    if os.path.exists(emotions_file):
        print("Previous Emotions:")
        with open(emotions_file, "r") as f:
            print(f.read())
    else:
        print("No previous emotions recorded.")