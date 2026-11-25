from django.urls import path

from . import views

app_name = "szenario"

urlpatterns = [
    path("", views.index, name="index"),
    path("spiel/<int:session_id>/", views.play, name="play"),
    path("spiel/<int:session_id>/antwort/", views.answer, name="answer"),
    path("spiel/<int:session_id>/folge/", views.consequence, name="consequence"),
    path("spiel/<int:session_id>/fertig/", views.done, name="done"),
    path("protokoll/", views.protocol_list, name="protocol_list"),
    path("protokoll/<int:session_id>/", views.protocol_detail, name="protocol_detail"),
]
