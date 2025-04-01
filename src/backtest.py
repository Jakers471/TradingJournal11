import os
import cv2
import numpy as np
import pytesseract
from datetime import datetime

# Color codes (RGB format for OpenCV)
COLORS = {
    "Red": (0, 0, 255),      # #FF0000
    "Green": (0, 255, 0),    # #00FF00
    "Blue": (255, 0, 0),     # #0000FF
    "Cyan": (255, 255, 0),   # #00FFFF
    "Magenta": (255, 0, 255),# #FF00FF
    "Yellow": (0, 255, 255), # #FFFF00
    "Orange": (0, 165, 255), # #FFA500
    "Purple": (128, 0, 128), # #800080
    "Black": (0, 0, 0),      # #000000
    "Brown": (42, 42, 165),  # #A52A2A
    "Teal": (128, 128, 0),   # #008080
    "Lime": (0, 255, 0),     # #00FF00 (same as Green)
    "Grey": (128, 128, 128), # #808080
    "Olive": (0, 128, 128),  # #808000
    "Maroon": (0, 0, 128),   # #800000
    "Pink": (203, 192, 255)  # #FFC0CB
}

# Map colors to labels
COLOR_TO_LABEL = {
    "Red": ["S.1", "Inv"],  # Stage 1 or Invalidation
    "Green": ["St.2", "Val"],  # Stage 2 or Validation
    "Blue": "D",  # Demand
    "Cyan": "S",  # Support
    "Magenta": "R",  # Resistance
    "Yellow": "Sup",  # Supply
    "Orange": "50%",  # 50% Invalidation
    "Purple": "30%",  # 30%
    "Black": "M",  # Mid Line
    "Brown": "HW",  # Highlighted Wick
}

# Wave colors for patterns
WAVE_COLORS = {
    "Blue": "Pattern 1",
    "Orange": "Pattern 2",
    "Purple": "Pattern 3",
    "Pink": "Pattern 4",
    "Teal": "Pattern 5",
    "Lime": "Pattern 6",
    "Brown": "Pattern 7",
    "Grey": "Pattern 8",
    "Olive": "Pattern 9",
    "Maroon": "Pattern 10"
}

def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple for OpenCV."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (4, 2, 0))  # BGR format

def find_closest_color(bgr_color):
    """Find the closest color name from the COLORS dictionary."""
    min_dist = float("inf")
    closest_color = None
    for color_name, color_bgr in COLORS.items():
        dist = np.sqrt(sum((bgr_color[i] - color_bgr[i]) ** 2 for i in range(3)))
        if dist < min_dist:
            min_dist = dist
            closest_color = color_name
    return closest_color

def detect_shapes_and_labels(image_path):
    """Detect shapes, colors, and labels in the image."""
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("Could not load image.")

    # Convert to grayscale for shape detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # Detect contours (shapes)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    elements = []
    for contour in contours:
        # Approximate the contour to a polygon
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        x, y, w, h = cv2.boundingRect(approx)

        # Determine shape type
        if len(approx) == 4:  # Rectangle (stages, key levels)
            # Extract the region of interest (ROI) to determine color
            roi = img[y:y+h, x:x+w]
            avg_color = np.mean(roi, axis=(0, 1)).astype(int)
            color_name = find_closest_color(avg_color)

            # Detect label text near the shape
            label_roi = img[max(0, y-30):y, x:x+w]
            label_text = pytesseract.image_to_string(label_roi, config="--psm 6").strip()
            if not label_text:
                label_text = COLOR_TO_LABEL.get(color_name, ["Unknown"])[0]

            # Determine element type based on color and label
            if color_name == "Red" and label_text == "S.1":
                element_type = "Stage 1"
            elif color_name == "Green" and label_text == "St.2":
                element_type = "Stage 2"
            else:
                element_type = "Key Level"
                label_text = COLOR_TO_LABEL.get(color_name, "Unknown")

            elements.append({
                "type": element_type,
                "label": label_text,
                "color": color_name,
                "x": x,
                "y": y,
                "width": w,
                "height": h
            })

        elif len(approx) > 4:  # Possible wave line
            # Check for wave colors
            roi = img[y:y+h, x:x+w]
            avg_color = np.mean(roi, axis=(0, 1)).astype(int)
            color_name = find_closest_color(avg_color)
            if color_name in WAVE_COLORS:
                elements.append({
                    "type": "Wave",
                    "pattern": WAVE_COLORS[color_name],
                    "color": color_name,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h
                })

    return elements

def backtest_pattern(backtest_file):
    """Run a backtest by interpreting a TradingView chart screenshot."""
    symbol = input("Enter Symbol for Backtest (e.g., APPL): ")
    date_range = input("Enter Date Range (e.g., 2025-03-01 to 2025-03-22): ")
    image_path = input("Enter path to TradingView Chart Image (e.g., charts/APPL_2025-03-22.png): ")

    # Detect elements in the image
    elements = detect_shapes_and_labels(image_path)

    # Organize elements
    stages = [e for e in elements if e["type"] in ["Stage 1", "Stage 2"]]
    key_levels = [e for e in elements if e["type"] == "Key Level"]
    waves = [e for e in elements if e["type"] == "Wave"]

    # Sort waves by x-coordinate to determine sequence
    waves.sort(key=lambda x: x["x"])

    # Assign bar counts (simplified: assume linear mapping of x-coordinates to bars)
    chart_width = 1920  # Example chart width in pixels (adjust based on your screenshots)
    pixels_per_bar = 19.2  # From your calibration
    pattern_data = []
    for i, wave in enumerate(waves):
        start_bar = int(wave["x"] / pixels_per_bar)
        end_bar = int((wave["x"] + wave["width"]) / pixels_per_bar)
        duration = end_bar - start_bar + 1
        pattern_data.append({
            "Wave": chr(97 + i),  # a, b, c, ...
            "Level": "Wave",
            "Start Bar": start_bar,
            "End Bar": end_bar,
            "Duration": duration,
            "Pattern": wave["pattern"]
        })

    # Find Stage 1 and Stage 2 for S2SI calculation
    stage1 = next((s for s in stages if s["type"] == "Stage 1"), None)
    stage2 = next((s for s in stages if s["type"] == "Stage 2"), None)

    # Calculate S2SI (simplified: use Stage 2 duration and a placeholder volume multiplier)
    stage2_duration = 0
    if stage2:
        stage2_start_bar = int(stage2["x"] / pixels_per_bar)
        stage2_end_bar = int((stage2["x"] + stage2["width"]) / pixels_per_bar)
        stage2_duration = stage2_end_bar - stage2_start_bar + 1
    volume_multiplier = 2  # Placeholder
    max_bars = 50  # Normalization factor
    s2si = (volume_multiplier * (max_bars / stage2_duration)) if stage2_duration > 0 else 0

    # Display results
    print(f"\n[Backtest Pattern: {symbol} | Date Range: {date_range}]")
    print("Detected Elements:")
    for element in stages + key_levels:
        print(f"Type: {element['type']}, Label: {element['label']}, Color: {element['color']}, Position: (x={element['x']}, y={element['y']})")
    print("\nWave Sequence:")
    for data in pattern_data:
        print(f"Wave {data['Wave']} | Pattern: {data['Pattern']} | Start Bar: {data['Start Bar']} | End Bar: {data['End Bar']} | Duration: {data['Duration']}")
    print(f"\nStage 2 Strength Index (S2SI): {s2si:.2f}")

    # Save results
    os.makedirs("data", exist_ok=True)
    with open(backtest_file, "a") as f:
        f.write(f"{symbol},{date_range},{s2si:.2f}\n")
    print(f"Saved to {backtest_file}")