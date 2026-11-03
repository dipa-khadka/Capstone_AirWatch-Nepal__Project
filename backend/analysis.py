"""Analysis and prediction (Dipa's part). Uses pandas and scikit-learn."""
import pandas as pd
from sklearn.linear_model import LinearRegression


def trend_stats(daily_rows):
    """daily_rows: list of {'day': date, 'aqi': number}. Returns average, highest, lowest."""
    df = pd.DataFrame(daily_rows)
    if df.empty:
        return None
    hi, lo = df.loc[df["aqi"].idxmax()], df.loc[df["aqi"].idxmin()]
    return {
        "average": int(round(df["aqi"].mean())),
        "highest": {"aqi": int(hi["aqi"]), "date": str(hi["day"])},
        "lowest": {"aqi": int(lo["aqi"]), "date": str(lo["day"])},
    }


def predict_next(values, steps=2):
    """Straight-line trend of the recent daily values, extended by `steps` days."""
    if len(values) < 3:
        return None
    x = [[i] for i in range(len(values))]
    model = LinearRegression().fit(x, values)
    out = []
    for k in range(steps):
        v = model.predict([[len(values) + k]])[0]
        out.append(int(max(0, min(500, round(v)))))
    return out
