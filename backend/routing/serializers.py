from __future__ import annotations

from datetime import UTC, datetime, timedelta

from rest_framework import serializers

from .checkpoints import ALLOWED_INTERVALS
from .clients.openmeteo import horizon_end
from .geo import haversine_mi

MAX_LOAD_LBS = 80_000  # US federal gross limit; a load alone can't exceed it
MAX_TRIP_MI = 3_500


class PlaceSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(max_length=300, required=False, allow_blank=True)


class PlanRequestSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure = serializers.DateTimeField()
    load_weight_lbs = serializers.FloatField(min_value=0, max_value=MAX_LOAD_LBS)
    interval_miles = serializers.ChoiceField(choices=ALLOWED_INTERVALS, default=25)
    include_heatmap = serializers.BooleanField(default=True)

    def validate_departure(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise serializers.ValidationError("Include a UTC offset, e.g. 2026-11-06T08:00-06:00.")
        now = datetime.now(UTC)
        if value < now - timedelta(hours=1):
            raise serializers.ValidationError("Departure can't be in the past.")
        if value > horizon_end() - timedelta(hours=1):
            raise serializers.ValidationError(
                "Departure must be within the 16-day weather forecast range."
            )
        return value

    def validate(self, attrs):
        o, d = attrs["origin"], attrs["destination"]
        dist = haversine_mi((o["lat"], o["lon"]), (d["lat"], d["lon"]))
        if dist < 1:
            raise serializers.ValidationError(
                {"destination": "Origin and destination are the same place."}
            )
        if dist > MAX_TRIP_MI:
            raise serializers.ValidationError(
                {"destination": f"Trips longer than {MAX_TRIP_MI:,} miles aren't supported."}
            )
        return attrs
