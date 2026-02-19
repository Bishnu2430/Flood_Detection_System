from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import threading
from typing import Deque, Dict, Optional, Tuple


@dataclass(frozen=True)
class _Sample:
    ts: float
    distance_cm: float
    rain_analog: float
    float_status: int


def _now_ts() -> float:
    return datetime.now().timestamp()


def _mean(values) -> float:
    values = list(values)
    return float(sum(values) / len(values)) if values else 0.0


def _std(values) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    var = sum((v - m) ** 2 for v in values) / (len(values) - 1)
    return float(var ** 0.5)


class FeatureBuffer:
    """Online feature computation to match training feature set.

    The trained model expects engineered features (rolling mean/std, trends, etc.).
    This buffer keeps a small time window of recent samples to compute them.
    """

    def __init__(self) -> None:
        # Keep 35 minutes to support 30-minute window + slack.
        self._samples: Deque[_Sample] = deque(maxlen=35 * 60)
        self._rain_start_ts: Optional[float] = None
        self._lock = threading.Lock()

    @staticmethod
    def _window_from(samples: Tuple[_Sample, ...], seconds: int, now_ts: float) -> Tuple[_Sample, ...]:
        cutoff = now_ts - seconds
        return tuple(s for s in samples if s.ts >= cutoff)

    def build_features(self, raw: Dict, *, update_state: bool = True) -> Dict[str, float]:
        with self._lock:
            now_ts = _now_ts()
            now_dt = datetime.fromtimestamp(now_ts)

            distance_cm = float(raw.get("distance_cm"))
            rain_analog = float(raw.get("rain_analog"))
            float_status = int(raw.get("float_status"))

            current = _Sample(ts=now_ts, distance_cm=distance_cm, rain_analog=rain_analog, float_status=float_status)

            # Snapshot state so we can compute without mutating.
            prev = self._samples[-1] if self._samples else None
            samples_snapshot = tuple(self._samples)
            rain_start_ts = self._rain_start_ts

            if update_state:
                self._samples.append(current)
                samples_for_calc = tuple(self._samples)
            else:
                # Compute as-if current sample arrived now, without persisting it.
                samples_for_calc = samples_snapshot + (current,)

            # --- Rolling distance features (3 minutes) ---
            win_3m = self._window_from(samples_for_calc, 3 * 60, now_ts)
            dist_3m = [s.distance_cm for s in win_3m]
            distance_rolling_mean_3min = _mean(dist_3m)
            distance_rolling_std_3min = _std(dist_3m)

            # --- Rise rate (cm/min). Positive means water is rising.
            # The sensor measures distance-to-water; decreasing distance implies rising water.
            rise_rate_cm_per_min = 0.0
            if prev is not None:
                dt_min = max((now_ts - prev.ts) / 60.0, 1e-6)
                rise_rate_cm_per_min = float((prev.distance_cm - distance_cm) / dt_min)

            # --- Rain trend (5 minutes): use rolling mean of rain_analog.
            win_5m = self._window_from(samples_for_calc, 5 * 60, now_ts)
            rain_5m = [s.rain_analog for s in win_5m]
            rain_trend_5min = _mean(rain_5m)

            # --- Cumulative rain (30 minutes): approximate accumulation using scaled rain.
            # Training values suggest cumulative is not a raw sum of 0-1023; we scale down.
            # This is a pragmatic approximation to avoid inference failures.
            win_30m = self._window_from(samples_for_calc, 30 * 60, now_ts)
            cumulative_rain_30min = 0.0
            if len(win_30m) >= 2:
                # Integrate (rain/100) over time in minutes.
                for a, b in zip(win_30m, win_30m[1:]):
                    dt_min = max((b.ts - a.ts) / 60.0, 0.0)
                    cumulative_rain_30min += ((a.rain_analog + b.rain_analog) / 2.0) / 100.0 * dt_min

            # --- Time since rain start (minutes)
            # Define "rain present" using a reasonable threshold on the 0-1023 scale.
            rain_present = rain_analog >= 500
            if rain_present and rain_start_ts is None:
                rain_start_ts = now_ts
            if not rain_present:
                rain_start_ts = None

            if update_state:
                self._rain_start_ts = rain_start_ts
            time_since_rain_start = 0.0
            if rain_start_ts is not None:
                time_since_rain_start = float((now_ts - rain_start_ts) / 60.0)

            emergency_flag = float(1 if float_status == 1 else 0)
            month = int(now_dt.month)
            season_flag = float(1 if month in (6, 7, 8, 9) else 0)

            return {
                "distance_cm": float(distance_cm),
                "rain_analog": float(rain_analog),
                "float_status": float(float_status),
                "rise_rate_cm_per_min": float(rise_rate_cm_per_min),
                "rain_trend_5min": float(rain_trend_5min),
                "distance_rolling_mean_3min": float(distance_rolling_mean_3min),
                "distance_rolling_std_3min": float(distance_rolling_std_3min),
                "cumulative_rain_30min": float(cumulative_rain_30min),
                "time_since_rain_start": float(time_since_rain_start),
                "emergency_flag": float(emergency_flag),
                "season_flag": float(season_flag),
                "hour_of_day": float(now_dt.hour),
                "day_of_week": float(now_dt.weekday()),
                "month": float(month),
            }


FEATURE_BUFFER = FeatureBuffer()
