# backend/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import recipe_short_link_redirect
from .views import (
    IngredientViewSet, RecipeViewSet, AppUserViewSet
)

router = DefaultRouter()  # Renamed from router_v1
router.register('ingredients', IngredientViewSet, basename='ingredients')
router.register('recipes', RecipeViewSet, basename='recipes')
router.register('users', AppUserViewSet,
                basename='users')


urlpatterns = [
    path('', include(router.urls)),  # Use renamed router
    path('auth/', include('djoser.urls.authtoken')),
    path('s/<int:recipe_pk>/', recipe_short_link_redirect,
         name='recipe-short-link'),
]
