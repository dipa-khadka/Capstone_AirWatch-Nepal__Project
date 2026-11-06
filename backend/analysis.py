"""Analysis and prediction (Dipa's part). Uses pandas and scikit-learn.
Two jobs: (1) simple numbers for the Trends page, (2) a short estimate for the Prediction page."""
import pandas as pd
from sklearn.linear_model import LinearRegression


def trend_stats(daily_rows):
    """Average, highest and lowest AQI of a period.
    daily_rows is a list like [{'day': date, 'aqi': 120}, ...] with one entry per day."""
    df = pd.DataFrame(daily_rows)
    if df.empty:
        return None
    hi = df.loc[df["aqi"].idxmax()]   # the row with the highest AQI
    lo = df.loc[df["aqi"].idxmin()]   # the row with the lowest AQI
    return {
        "average": int(round(df["aqi"].mean())),
        "highest": {"aqi": int(hi["aqi"]), "date": str(hi["day"])},
        "lowest": {"aqi": int(lo["aqi"]), "date": str(lo["day"])},
    }


def predict_next(values, steps=2):
    """Estimates the next `steps` days from the recent daily values.
    Method: fit a straight line through the values (linear regression) and continue it.
    This is a simple trend estimate, not a weather forecast. At least 3 days are needed."""
    if len(values) < 3:
        return None
    x = [[i] for i in range(len(values))]          # day numbers 0, 1, 2, ...
    model = LinearRegression().fit(x, values)      # find the best straight line
    out = []
    for k in range(steps):
        v = model.predict([[len(values) + k]])[0]  # the line's value for the next day
        out.append(int(max(0, min(500, round(v)))))  # keep the answer inside the AQI scale 0 to 500
    return out
