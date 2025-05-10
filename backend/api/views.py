# backend/api/views.py
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.urls import reverse  # Ensure this is imported
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import (
    Ingredient, Tag, Recipe, Favorite, ShoppingCart, Subscription
)
from users.models import User
from .serializers import (
    IngredientSerializer, TagSerializer, RecipeReadSerializer,
    RecipeWriteSerializer, ShortRecipeSerializer, SubscriptionSerializer,
    AvatarSerializer
)
from .permissions import IsOwnerOrReadOnly, IsAdminOrReadOnly
from .filters import RecipeFilter, IngredientFilter
# Assuming pagination is defined
from .pagination import CustomPageNumberPagination
from .utils import generate_shopping_list_text  # Import the helper

# Use Djoser's viewset for user management
from djoser.views import UserViewSet as DjoserUserViewSet
from djoser.conf import settings as djoser_settings


class CustomUserViewSet(DjoserUserViewSet):
    """
    Extends Djoser's UserViewSet to add subscription functionality.
    Uses the CustomUserSerializer for responses.
    """
    pagination_class = CustomPageNumberPagination
    # Ensure CustomUserSerializer is used by default for list/retrieve
    # Djoser might handle this automatically based on settings,
    # but explicitly setting can be safer.
    # serializer_class = CustomUserSerializer # Check Djoser settings first

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == 'me':
            # Use Djoser's configured permission for current_user (defaults to IsAuthenticated)
            # This ensures /me/ is strictly IsAuthenticated
            self.permission_classes = djoser_settings.PERMISSIONS.current_user
        elif self.action == 'list':
            # Use Djoser's configured permission for user_list
            self.permission_classes = djoser_settings.PERMISSIONS.user_list
        elif self.action in ['retrieve', 'update', 'partial_update', 'destroy']:
            # Use Djoser's configured permission for user (detail actions)
            # For GET /api/users/{id}/ (retrieve), this will use IsAuthenticatedOrReadOnly
            # For PUT/PATCH/DELETE /api/users/{id}/, this will also use IsAuthenticatedOrReadOnly,
            # which is fine because object-level permissions (like IsOwnerOrReadOnly, or Djoser's CurrentUserOrAdmin)
            # will further restrict write operations.
            self.permission_classes = djoser_settings.PERMISSIONS.user
        # Add other custom authenticated actions
        elif self.action in ['subscribe', 'avatar', 'set_password']:
            # Your custom actions that require authentication
            self.permission_classes = [permissions.IsAuthenticated]
        # For any other actions not explicitly covered,
        # you might fall back to DRF's default or Djoser's UserViewSet default.
        # Or, set a more restrictive default if necessary.
        # else:
        #     self.permission_classes = [permissions.IsAdminUser] # Example restrictive default

        return super().get_permissions()

    @action(
        detail=True,
        methods=['post', 'delete']
    )
    def subscribe(self, request, id=None):
        """Subscribe/unsubscribe to an author."""
        author = get_object_or_404(User, id=id)
        user = request.user

        if user == author:
            return Response(
                {'errors': 'Нельзя подписаться на самого себя.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscription_exists = Subscription.objects.filter(
            user=user, author=author
        ).exists()

        if request.method == 'POST':
            if subscription_exists:
                return Response(
                    {'errors': 'Вы уже подписаны на этого автора.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            subscription = Subscription.objects.create(
                user=user, author=author)
            serializer = SubscriptionSerializer(
                author, context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # DELETE request
        if not subscription_exists:
            return Response(
                {'errors': 'Вы не были подписаны на этого автора.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        Subscription.objects.filter(user=user, author=author).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['get']
    )
    def subscriptions(self, request):
        """List authors the current user is subscribed to."""
        user = request.user
        # Filter authors followed by user
        authors = User.objects.filter(following__user=user)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(authors, request)
        serializer = SubscriptionSerializer(
            page, many=True, context={'request': request}
        )
        return paginator.get_paginated_response(serializer.data)

    # Djoser handles /me/, /set_password/ endpoints automatically

    # Avatar handling (could be separate ViewSet but action is simpler here)
    @action(
        detail=False,  # Action on the '/users/me/avatar/' path
        methods=['put', 'delete'],
        url_path='me/avatar',
        parser_classes=[MultiPartParser, FormParser,
                        JSONParser]  # Allow different input types
    )
    def avatar(self, request):
        user = request.user
        if request.method == 'PUT':
            serializer = AvatarSerializer(
                data=request.data, context={'request': request})
            if serializer.is_valid():
                user.avatar = serializer.validated_data['avatar']
                user.save()
                # Return only the avatar URL as per Postman
                return Response({'avatar': request.build_absolute_uri(user.avatar.url)}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # DELETE request
        if user.avatar:
            user.avatar.delete(save=True)  # Delete file and update model
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Viewset for Tags (Read Only)."""
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None  # Tags usually don't need pagination


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Viewset for Ingredients (Read Only)."""
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None  # Ingredients usually don't need pagination
    filter_backends = (IngredientFilter,)  # Use custom SearchFilter
    # Search by name start (case-insensitive default)
    search_fields = ('^name',)


class RecipeViewSet(viewsets.ModelViewSet):
    """Viewset for Recipes (CRUD + custom actions)."""
    queryset = Recipe.objects.select_related('author').prefetch_related(
        'tags', 'ingredients'
    )
    permission_classes = (IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly,)
    pagination_class = CustomPageNumberPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    # Explicitly define allowed methods
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return RecipeReadSerializer
        return RecipeWriteSerializer  # For create, update, partial_update

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def _manage_related_object(self, request, pk, related_model, error_msg_exists, error_msg_not_exists):
        """Helper function for favorite and shopping_cart actions."""
        recipe = get_object_or_404(Recipe, pk=pk)
        user = request.user
        obj_exists = related_model.objects.filter(
            user=user, recipe=recipe).exists()

        if request.method == 'POST':
            if obj_exists:
                return Response(
                    {'errors': error_msg_exists},
                    status=status.HTTP_400_BAD_REQUEST
                )
            related_model.objects.create(user=user, recipe=recipe)
            serializer = ShortRecipeSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # DELETE request
        if not obj_exists:
            return Response(
                {'errors': error_msg_not_exists},
                status=status.HTTP_400_BAD_REQUEST
            )
        related_model.objects.filter(user=user, recipe=recipe).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        """Add/remove recipe from favorites."""
        return self._manage_related_object(
            request, pk, Favorite,
            'Рецепт уже в избранном.',
            'Рецепта нет в избранном.'
        )

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        """Add/remove recipe from shopping cart."""
        return self._manage_related_object(
            request, pk, ShoppingCart,
            'Рецепт уже в списке покупок.',
            'Рецепта нет в списке покупок.'
        )

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        """Download the shopping list as a text file."""
        user = request.user
        shopping_list_text = generate_shopping_list_text(user)

        response = HttpResponse(shopping_list_text, content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="foodgram_shopping_list.txt"'
        )
        return response

    # Short link - basic implementation stub (needs actual short link logic)
    @action(
        detail=True,
        methods=['get'],
        permission_classes=[permissions.AllowAny],
        url_path='get-link'
    )
    def get_link(self, request, pk=None):
        """Get a short link for the recipe."""
        recipe = get_object_or_404(Recipe, pk=pk)

        # Generate the short URL using the 'recipe-short-link' pattern from foodgram/urls.py
        try:
            # This 'recipe-short-link' name must match the name given in foodgram/urls.py
            # path('s/<int:recipe_pk>/', recipe_short_link_redirect, name='recipe-short-link'),
            short_link_path = reverse(
                'recipe-short-link', kwargs={'recipe_pk': recipe.pk})
            absolute_short_link = request.build_absolute_uri(short_link_path)
        except Exception as e:
            # Log the error e for debugging
            return Response({'error': 'Could not generate short link.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'short-link': absolute_short_link}, status=status.HTTP_200_OK)


def recipe_short_link_redirect(request, recipe_pk):
    recipe = get_object_or_404(Recipe, pk=recipe_pk)
    # Redirect to the frontend URL structure for a recipe
    # Example: frontend handles /recipes/{id}
    # In production, you'd use settings for FRONTEND_BASE_URL
    # For now, assuming frontend is on the same domain or Nginx routes it.
    # This is a placeholder for where your frontend shows the recipe.
    # If your frontend route is just /<recipe_id> or /recipe/<recipe_id>
    # then adjust accordingly. For an SPA, this path will be handled by index.html
    # and client-side routing.
    frontend_url = f"/recipes/{recipe.pk}/"  # Example relative path for SPA
    return redirect(frontend_url)
