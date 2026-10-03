"""audit（审核页面）app 的 URL 路由。"""
from django.urls import path

from audit import views

urlpatterns = [
    path("review/<str:link_id>/", views.review_page, name="review_page"),
    path("review/<str:link_id>/submit/", views.review_submit, name="review_submit"),
]
