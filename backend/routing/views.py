from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .domain import LatLon
from .serializers import PlanRequestSerializer
from .service import plan_trip


@api_view(["GET"])
@throttle_classes([])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
@throttle_classes([AnonRateThrottle])
def plan(request):
    s = PlanRequestSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    result = plan_trip(
        origin=LatLon(d["origin"]["lat"], d["origin"]["lon"]),
        destination=LatLon(d["destination"]["lat"], d["destination"]["lon"]),
        departure=d["departure"],
        load_lbs=d["load_weight_lbs"],
        interval_mi=int(d["interval_miles"]),
        include_heatmap=d["include_heatmap"],
    )
    result["origin"] = d["origin"]
    result["destination"] = d["destination"]
    return Response(result)


def spa_index(request):
    """Serve the built React app's index.html (single-service deploy)."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return HttpResponseNotFound("Frontend not built. Run `npm run build` in frontend/.")
    return HttpResponse(index.read_text(encoding="utf-8"), content_type="text/html")
