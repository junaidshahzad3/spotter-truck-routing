from django.urls import include, path, re_path

from routing.views import spa_index

urlpatterns = [
    path("api/", include("routing.urls")),
    # Anything else falls through to the React app (when it has been built).
    re_path(r"^(?!api/|static/).*$", spa_index),
]
