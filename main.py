import os
from datetime import datetime, timedelta
import pytz
from flask import Flask, render_template, request, redirect, url_for
from src.analysis import recall_analysis, sync_to_sheets, analyze_market
from src.backtest import backtest_pattern
from src.ai_insights import create_chart

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Define file paths
EMOTIONS_FILE = "data/trades/emotions.csv"
BACKTEST_FILE = "data/trades/backtest_patterns.csv"
CHART_FILE = "charts/emotion_distribution.png"
SHEET_NAME = "Trade Performance"

# Define NYSE trading hours and holidaysç
EASTERN = pytz.timezone("US/Eastern")
NYSE_OPEN_TIME = {"hour": 9, "minute": 30}  # 9:30 AM EDT
NYSE_CLOSE_TIME = {"hour": 16, "minute": 0}  # 4:00 PM EDT
NYSE_EARLY_CLOSE_TIME = {"hour": 13, "minute": 0}  # 1:00 PM EDT for early closures

HOLIDAYS_2025 = [
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
    "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25"
]

EARLY_CLOSURES_2025 = ["2025-07-03", "2025-11-28", "2025-12-24"]

def get_next_trading_day(current_date):
    next_day = current_date + timedelta(days=1)
    while True:
        if next_day.weekday() >= 5 or next_day.strftime("%Y-%m-%d") in HOLIDAYS_2025:
            next_day += timedelta(days=1)
            continue
        break
    return next_day

def calculate_market_time():
    now = datetime.now(pytz.UTC).astimezone(EASTERN)
    today = now.date()
    today_str = today.strftime("%Y-%m-%d")
    
    is_holiday = today_str in HOLIDAYS_2025
    is_weekend = today.weekday() >= 5
    is_trading_day = not (is_holiday or is_weekend)
    
    is_early_closure = today_str in EARLY_CLOSURES_2025
    close_time = NYSE_EARLY_CLOSE_TIME if is_early_closure else NYSE_CLOSE_TIME
    
    market_open = EASTERN.localize(datetime(today.year, today.month, today.day, NYSE_OPEN_TIME["hour"], NYSE_OPEN_TIME["minute"]))
    market_close = EASTERN.localize(datetime(today.year, today.month, today.day, close_time["hour"], close_time["minute"]))
    
    if is_trading_day:
        if market_open <= now <= market_close:
            time_until_close = market_close - now
            total_minutes = int(time_until_close.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            message = f"The market is open! It will close in {hours} hours and {minutes} minutes."
            return message, False
        elif now < market_open:
            time_until_open = market_open - now
            total_minutes = int(time_until_open.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            message = f"Good morning! The market opens in {hours} hours and {minutes} minutes today."
            return message, False
    
    next_trading_day = get_next_trading_day(today)
    next_open = EASTERN.localize(datetime(next_trading_day.year, next_trading_day.month, next_trading_day.day, NYSE_OPEN_TIME["hour"], NYSE_OPEN_TIME["minute"]))
    time_until_next_open = next_open - now
    total_minutes = int(time_until_next_open.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    if is_trading_day:
        message = f"The market has closed for today. It will open in {hours} hours and {minutes} minutes on {next_trading_day.strftime('%A')}."
    else:
        message = f"Good morning! The market is closed today. It will open in {hours} hours and {minutes} minutes on {next_trading_day.strftime('%A')}."
    
    return message, True

# Ensure data folder exists
os.makedirs("data", exist_ok=True)
if not os.path.exists(EMOTIONS_FILE):
    with open(EMOTIONS_FILE, "w") as f:
        f.write("Date,Time,Context,Response,Label,TradeID\n")

@app.route('/')
def index():
    print("Loading index route, rendering analyze.html")  # Debug print
    market_message, is_market_closed = calculate_market_time()
    if not is_market_closed:
        if request.args.get('morning_feeling'):
            morning_feeling = request.args.get('morning_feeling')
            label = "Positive" if "good" in morning_feeling.lower() else "Negative"
            with open(EMOTIONS_FILE, "a") as f:
                f.write(f"{datetime.now().date()},{datetime.now().time()},Morning Emotions/Thoughts,{morning_feeling},{label},\n")
    return render_template('analyze.html', market_message=market_message, is_market_closed=is_market_closed)

@app.route('/analyze', methods=['GET', 'POST'])
def analyze():
    print("Loading analyze route")  # Debug print
    if request.method == 'POST':
        print("Processing POST request for analyze")  # Debug print
        # Retrieve form data
        symbol = request.form['symbol']
        trade_id = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Timeframes
        htf = request.form['htf']
        mtf = request.form['mtf']
        ltf = request.form['ltf']
        
        # Per-timeframe data
        timeframes = {"HTF": htf, "MTF": mtf, "LTF": ltf}
        analysis_data = {}
        overall_signal = "MTF-LTF Align Short | [Green]Green[/Green]"  # Placeholder
        
        for tf_label, tf_value in timeframes.items():
            trend = ", ".join(request.form.getlist(f'{tf_label}_trend'))
            stage = ", ".join(request.form.getlist(f'{tf_label}_stage'))
            bars = int(request.form[f'{tf_label}_bars'])
            avg_bars = int(request.form[f'{tf_label}_avg_bars'])
            key_levels = ", ".join(request.form.getlist(f'{tf_label}_key_levels'))
            mas = ", ".join(request.form.getlist(f'{tf_label}_mas'))
            validation_price = request.form[f'{tf_label}_validation_price']
            validation_hit = ", ".join(request.form.getlist(f'{tf_label}_validation_hit'))
            invalidation_price = request.form[f'{tf_label}_invalidation_price']
            invalidation_hit = ", ".join(request.form.getlist(f'{tf_label}_invalidation_hit'))
            
            # Pass to analysis function (bias will be calculated in analyze_market)
            result = analyze_market(
                emotions_file=EMOTIONS_FILE,
                sheet_name=SHEET_NAME,
                symbol=symbol,
                trade_id=trade_id,
                tf_label=tf_label,
                tf_value=tf_value,
                trend=trend,
                stage=stage,
                bars=bars,
                avg_bars=avg_bars,
                key_levels=key_levels,
                mas=mas,
                validation_price=validation_price,
                validation_hit=validation_hit,
                invalidation_price=invalidation_price,
                invalidation_hit=invalidation_hit,
                overall_signal=overall_signal
            )
            analysis_data[tf_label] = result

        # Trade placement
        place_trade = request.form.get('place_trade')
        during_feeling = request.form.get('during_feeling', '')
        after_feeling = request.form.get('after_feeling', '')
        
        if place_trade == "yes" and during_feeling:
            label = "Mixed" if "but" in during_feeling.lower() else "Positive"
            with open(EMOTIONS_FILE, "a") as f:
                f.write(f"{datetime.now().date()},{datetime.now().time()},During Trade {trade_id},{during_feeling},{label},{trade_id}\n")

            os.makedirs("data/trades", exist_ok=True)
            trade_file = f"data/trades/{datetime.now().date()}_trades.csv"
            with open(trade_file, "a") as f:
                f.write(f"{trade_id},{symbol},Placed,{overall_signal}\n")

        # Trade exit
        exit_trade = request.form.get('exit_trade')
        if exit_trade == "yes" and after_feeling:
            pl = 50  # Example P/L
            direction = "Long"
            sync_to_sheets(trade_id, symbol, pl, direction, SHEET_NAME)
            label = "Positive" if "good" in after_feeling.lower() else "Negative"
            with open(EMOTIONS_FILE, "a") as f:
                f.write(f"{datetime.now().date()},{datetime.now().time()},After Trade {trade_id},{after_feeling},{label},{trade_id}\n")

        print("Rendering analyze.html with analysis data")  # Debug print
        return render_template('analyze.html', analysis_data=analysis_data, timeframes=timeframes, symbol=symbol, trade_placed=place_trade, overall_signal=overall_signal)

    return redirect(url_for('index'))

@app.route('/recall')
def recall():
    with open(EMOTIONS_FILE, "r") as f:
        emotions = f.read()
    return render_template('analyze.html', emotions=emotions)

@app.route('/backtest', methods=['POST'])
def backtest():
    backtest_pattern(backtest_file=BACKTEST_FILE)
    return redirect(url_for('index'))

@app.route('/chart', methods=['POST'])
def chart():
    create_chart(emotions_file=EMOTIONS_FILE, chart_file=CHART_FILE)
    return redirect(url_for('index'))

@app.route('/exit', methods=['POST'])
def exit_app():
    reason = request.form['reason']
    label = "Physical" if "tired" in reason.lower() else "Negative"
    with open(EMOTIONS_FILE, "a") as f:
        f.write(f"{datetime.now().date()},{datetime.now().time()},Non-Trading Exit,{reason},{label},\n")
    return "Exit recorded. You can close the tab."

if __name__ == '__main__':
    app.run(debug=True)