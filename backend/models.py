from sqlalchemy import Column, Integer, Float, DateTime, Text
from sqlalchemy.sql import func
from .database import Base


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)

    distance_cm = Column(Float, nullable=False)
    rain_analog = Column(Integer, nullable=False)
    float_status = Column(Integer, nullable=False)

    predicted_risk = Column(Integer)
    risk_probability = Column(Float)

    explanation = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
