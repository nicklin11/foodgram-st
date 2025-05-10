# backend/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import recipe_short_link_redirect  # Import it
from .views import (
    TagViewSet, IngredientViewSet, RecipeViewSet, CustomUserViewSet
)

# Using DefaultRouter for automatic URL generation
router_v1 = DefaultRouter()
router_v1.register('tags', TagViewSet, basename='tags')
router_v1.register('ingredients', IngredientViewSet, basename='ingredients')
router_v1.register('recipes', RecipeViewSet, basename='recipes')
# Register CustomUserViewSet - Djoser might handle /users/ and /users/me/
# Check Djoser docs for preferred registration method with custom actions
router_v1.register('users', CustomUserViewSet, basename='users')


urlpatterns = [
    # Include router-generated URLs
    path('', include(router_v1.urls)),

    # Include Djoser auth URLs (token login/logout)
    # Prefix with 'auth/' to match Postman collection
    path('auth/', include('djoser.urls.authtoken')),

    # Djoser base URLs (like user registration) might already be included
    # if 'users/' is registered above and DjoserUserViewSet handles it.
    # If not, include them separately:
    # path('', include('djoser.urls')),
    path('s/<int:recipe_pk>/', recipe_short_link_redirect,
         name='recipe-short-link'),
]
