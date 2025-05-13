# backend/api/views.py
import io
from djoser.views import UserViewSet as DjoserUserViewSet
from django.http import FileResponse
from .utils import generate_shopping_list_text
from .pagination import FoodgramPageNumberPagination
from .filters import RecipeFilter, IngredientFilter
from .permissions import IsOwnerOrReadOnly
from .serializers import (
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeWriteSerializer,
    ShortRecipeSerializer,
    SubscriptionSerializer,
    AvatarSerializer,
    UserDetailSerializer,
)
from users.models import User
from .models import Ingredient, Recipe, Favorite, ShoppingCart, Subscription
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import (
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from rest_framework import (
    viewsets, status, permissions, serializers)


class AppUserViewSet(DjoserUserViewSet):
    """
    Extends Djoser's UserViewSet to add subscription functionality.
    Uses the UserDetailSerializer for responses.
    """
    queryset = User.objects.all().prefetch_related(
        'recipes', 'authors', 'followers', 'followers__author')
    serializer_class = UserDetailSerializer
    pagination_class = FoodgramPageNumberPagination

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[IsAuthenticated])
    def subscribe(self, request, id=None):
        author_to_act_on = get_object_or_404(
            User, id=id)
        current_user = request.user

        if current_user == author_to_act_on:
            if request.method == "POST":  # Prevent subscribing to self
                raise serializers.ValidationError(
                    {"errors": "Нельзя подписаться на самого себя."})

        if request.method == "POST":
            subscription, created = Subscription.objects.get_or_create(
                user=current_user, author=author_to_act_on
            )
            if not created:
                raise serializers.ValidationError(
                    {"errors": "Вы уже подписаны на этого автора."})
            serializer = SubscriptionSerializer(
                author_to_act_on, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            try:
                subscription_to_delete = Subscription.objects.get(
                    user=current_user, author=author_to_act_on)
                subscription_to_delete.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Subscription.DoesNotExist:
                raise serializers.ValidationError(
                    {"errors": "Вы не были подписаны на этого автора."})

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        current_user = request.user
        subscribed_author_ids = current_user.followers.values_list(
            'author_id', flat=True)
        authors_user_is_following = User.objects.filter(
            pk__in=subscribed_author_ids).prefetch_related('recipes')

        page = self.paginate_queryset(authors_user_is_following)
        if page is not None:
            serializer = SubscriptionSerializer(
                page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = SubscriptionSerializer(
            authors_user_is_following, many=True, context={'request': request})
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["put", "delete"],
        url_path="me/avatar",
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def avatar(self, request):
        user = request.user
        if request.method == "PUT":
            serializer = AvatarSerializer(
                data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            user.avatar = serializer.validated_data["avatar"]
            user.save()
            return Response(
                {"avatar": request.build_absolute_uri(user.avatar.url)},
                status=status.HTTP_200_OK,
            )

        # DELETE request
        if user.avatar:
            user.avatar.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(["get", "put", "patch", "delete"], detail=False,
            permission_classes=[IsAuthenticated])
    def me(self, request, *args, **kwargs):
        # self.get_instance() usually returns request.user
        self.get_object = self.get_instance
        if request.method == "GET":
            return self.retrieve(request, *args, **kwargs)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Viewset for Ingredients (Read Only)."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None  # Ingredients usually don't need pagination
    filter_backends = (IngredientFilter,)  # Use custom SearchFilter
    # Search by name start (case-insensitive default)
    search_fields = ("^name",)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.select_related("author").prefetch_related(
        "ingredients",
        "recipeingredients__ingredient",
        "favorited_by_set",
        "in_shopping_cart_set"
    )
    permission_classes = (IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly,)
    pagination_class = FoodgramPageNumberPagination
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    http_method_names = ["get", "post", "patch", "delete"]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return RecipeReadSerializer
        return RecipeWriteSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def _manage_user_recipe_relation(
        self, request, pk, model_class,
        error_msg_exists_verb, error_msg_not_exists_verb
    ):
        recipe = get_object_or_404(Recipe, pk=pk)
        current_user = request.user  # Renamed for clarity

        model_verbose_name_accusative = (
            model_class._meta.verbose_name_plural.lower())

        relation_instance, created = model_class.objects.get_or_create(
            user=current_user, recipe=recipe
        )

        if request.method == "POST":
            if not created:
                raise serializers.ValidationError(
                    {"errors": f'''Рецепт уже {error_msg_exists_verb}
                     {model_verbose_name_accusative}.'''}
                )
            # Assuming ShortRecipeSerializer is defined
            serializer = ShortRecipeSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:  # DELETE request
            if created:
                relation_instance.delete()
                raise serializers.ValidationError(
                    {"errors": f'''Рецепт не был {error_msg_not_exists_verb}
                     {model_verbose_name_accusative}
                      (попытка удалить несуществующий).'''}
                )
            # If !created, it means it existed. Delete it.
            relation_instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post", "delete"],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        return self._manage_user_recipe_relation(
            request, pk, Favorite, "добавлен в", "в"
        )

    @action(detail=True, methods=["post", "delete"],
            permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        return self._manage_user_recipe_relation(
            request, pk, ShoppingCart, "добавлен в", "в"
        )

    @action(detail=False, methods=["get"],
            permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user
        shopping_list_text = generate_shopping_list_text(user)

        # Use BytesIO for FileResponse
        text_bytes = shopping_list_text.encode('utf-8')
        file_like_object = io.BytesIO(text_bytes)

        response = FileResponse(
            file_like_object,
            as_attachment=True,
            filename="foodgram_shopping_list.txt",
            content_type="text/plain; charset=utf-8"  # Specify charset
        )
        return response

    @action(
        detail=True, methods=["get"],
        permission_classes=[permissions.AllowAny], url_path="get-link"
    )
    def get_link(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        short_link_path = reverse(
            "recipe-short-link", kwargs={"recipe_pk": recipe.pk})
        absolute_short_link = request.build_absolute_uri(short_link_path)
        return Response({"short-link": absolute_short_link},
                        status=status.HTTP_200_OK)


def recipe_short_link_redirect(request, recipe_pk):
    get_object_or_404(Recipe, pk=recipe_pk)
    frontend_url = f"/recipes/{recipe_pk}/"
    return redirect(frontend_url)
