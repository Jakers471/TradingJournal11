import pandas as pd
import matplotlib.pyplot as plt
import os

def create_chart():
    """Create a bar chart of emotion distribution."""
    if os.path.exists("data/emotions.csv"):
        df = pd.read_csv("data/emotions.csv")
        df["Label"].value_counts().plot(kind="bar")
        plt.title("Emotion Distribution")
        os.makedirs("charts", exist_ok=True)
        plt.savefig("charts/emotion_distribution.png")
        plt.close()
        print("Chart saved to charts/emotion_distribution.png")
    else:
        print("No emotions data available to chart.")