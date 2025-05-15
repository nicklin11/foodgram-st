# backend/api/views.py
from djoser.views import UserViewSet as DjoserUserViewSet
from django.http import FileResponse, Http404
from .utils import generate_shopping_list_text
from .pagination import FoodgramPageNumberPagination
from .filters import RecipeFilter, IngredientFilter
from .permissions import IsOwnerOrReadOnly
from .serializers import (
    IngredientSerializer,
    RecipeReadSerializer,
    RecipeWriteSerializer,
    ShortRecipeSerializer,
    SubscribedAuthorSerializer,
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
    def subscribe(self, request, id=None):
        author = get_object_or_404(
            User, id=id)
        current_user = request.user

        if request.method == "POST":

            if current_user == author:
                raise serializers.ValidationError(
                    {"errors": "Нельзя подписаться на самого себя."})

            subscription, created = Subscription.objects.get_or_create(
                user=current_user, author=author
            )
            if not created:
                raise serializers.ValidationError(
                    {"errors": f"Вы уже подписаны на автора"
                     f" {author.username}."})
            serializer = SubscribedAuthorSerializer(
                author, context={"request": request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # в ТЗ нужно 400 возвращать, нельзя 404
        # delete_non_existing_subscription // Second User
        # "При попытке пользователя удалить несуществующую подписку должен
        # вернуться ответ со статусом 400"
        try:
            subscription_to_delete = Subscription.objects.get(
                user=current_user, author=author
            )
            subscription_to_delete.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Subscription.DoesNotExist:
            # возвращает 400
            raise serializers.ValidationError(
                {"errors": f"Вы не были подписаны на автора"
                 f" {author.username}."}
            )

    @action(detail=False, methods=['get'],
            permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        current_user = request.user
        subscribed_author_ids = current_user.followers.values_list(
            'author_id', flat=True)
        authors_user_is_following = User.objects.filter(
            pk__in=subscribed_author_ids).prefetch_related('recipes')
        page = self.paginate_queryset(authors_user_is_following)
        serializer = SubscribedAuthorSerializer(
            page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

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
        return super().me(request, *args, **kwargs)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Viewset for Ingredients (Read Only)."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = (permissions.AllowAny,)
    pagination_class = None
    filter_backends = (IngredientFilter,)
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
        self, request, pk, model_class
    ):
        recipe = get_object_or_404(Recipe, pk=pk)
        current_user = request.user  # Renamed for clarity

        model_verbose_name_accusative = (
            model_class._meta.verbose_name_plural.lower())

        if request.method == "POST":
            relation_instance, created = model_class.objects.get_or_create(
                user=current_user, recipe=recipe
            )
            if not created:
                raise serializers.ValidationError(
                    {"errors": f"Рецепт уже добавлен в"
                     f" {model_verbose_name_accusative}."}
                )
            serializer = ShortRecipeSerializer(recipe)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # в ТЗ нужно 400 возвращать, нельзя 404
        # remove_not_added_from_shopping_cart // Second User
        # "Запрос зарегистрированного пользователя на удаление из корзины
        # рецепта, который не был туда добавлен, должен
        # вернуть ответ со статусом 400"
        # remove_not_added_from_favorite // Second User
        # "Запрос пользователя на удаление из избранного рецепта,
        # который не был туда добавлен, должен вернуть ответ со статусом 400"
        try:
            instance_to_delete = model_class.objects.get(
                user=current_user, recipe=recipe
            )
            instance_to_delete.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except model_class.DoesNotExist:
            # возвращает 400
            raise serializers.ValidationError(
                {"errors": "Попытка удалить несуществующий рецепт."}
            )

    @action(detail=True, methods=["post", "delete"],
            permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        return self._manage_user_recipe_relation(
            request, pk, Favorite
        )

    @action(detail=True, methods=["post", "delete"],
            permission_classes=[IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        return self._manage_user_recipe_relation(
            request, pk, ShoppingCart
        )

    @action(detail=False, methods=["get"],
            permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user
        shopping_list_text = generate_shopping_list_text(user)

        response = FileResponse(
            shopping_list_text,
            as_attachment=True,
            filename="foodgram_shopping_list.txt",
            content_type="text/plain"
        )
        return response

    @action(
        detail=True, methods=["get"],
        permission_classes=[permissions.AllowAny], url_path="get-link"
    )
    def get_link(self, request, pk=None):
        if not Recipe.objects.filter(pk=pk).exists():
            raise Http404("Рецепт не найден.")
        short_link_path = reverse(
            "recipe-short-link", args=[pk])
        absolute_short_link = request.build_absolute_uri(short_link_path)
        return Response({"short-link": absolute_short_link},
                        status=status.HTTP_200_OK)


def recipe_short_link_redirect(request, recipe_pk):
    get_object_or_404(Recipe, pk=recipe_pk)
    return redirect(f"/recipes/{recipe_pk}/")
