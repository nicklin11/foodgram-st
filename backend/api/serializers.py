# backend/api/serializers.py
from django.db import transaction
from rest_framework import serializers
from djoser.serializers import UserSerializer as DjoserUserSerializer


from drf_extra_fields.fields import Base64ImageField

from .models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    Favorite,
    ShoppingCart,
    Subscription,
)
from users.models import User  # Import custom User model


# --- User Serializers ---


class UserDetailSerializer(DjoserUserSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta(DjoserUserSerializer.Meta):
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
            "avatar",
        )
        read_only_fields = fields

    def get_is_subscribed(self, target_user: User) -> bool:
        request = self.context.get("request")
        return bool(
            request
            and request.user
            and request.user.is_authenticated
            and Subscription.objects.filter(
                user=request.user, author=target_user
            ).exists()
        )


class AvatarSerializer(serializers.Serializer):
    """Serializer for avatar update."""

    avatar = Base64ImageField(required=True)


# --- Ingredient & Tag Serializers ---


class IngredientSerializer(serializers.ModelSerializer):
    """Serializer for Ingredient."""

    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


# --- Recipe Related Serializers ---


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Serializer for reading ingredients within a recipe."""

    id = serializers.ReadOnlyField(source="ingredient.id")
    name = serializers.ReadOnlyField(source="ingredient.name")
    measurement_unit = serializers.ReadOnlyField(
        source="ingredient.measurement_unit"
    )

    class Meta:
        model = RecipeIngredient
        fields = ("id", "name", "measurement_unit", "amount")
        read_only_fields = fields


class RecipeIngredientWriteSerializer(serializers.ModelSerializer):
    """Serializer for writing ingredient amounts
    when creating/updating recipes."""

    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = RecipeIngredient
        fields = ("id", "amount")


class RecipeReadSerializer(serializers.ModelSerializer):
    """Serializer for reading/displaying Recipe details."""

    author = UserDetailSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        source="recipeingredients", many=True
    )
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)
    image = (
        Base64ImageField()
    )  # Read as URL, handle write in RecipeWriteSerializer

    class Meta:
        model = Recipe
        fields = (
            "id",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
        )
        read_only_fields = fields

    def get_user_from_context(self):
        request = self.context.get("request")
        return request.user if (request
                                and request.user.is_authenticated) else None

    def get_is_favorited(self, obj):
        """Check if the recipe is favorited by the request user."""
        user = self.get_user_from_context()
        if not user:
            return False
        return Favorite.objects.filter(user=user, recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        """Check if the recipe is in the shopping cart of the request user."""
        user = self.get_user_from_context()
        if not user:
            return False
        return ShoppingCart.objects.filter(user=user, recipe=obj).exists()


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating Recipes."""

    ingredients = RecipeIngredientWriteSerializer(many=True)
    image = Base64ImageField(required=True, allow_null=False)
    author = UserDetailSerializer(read_only=True)  # Set automatically
    cooking_time = serializers.IntegerField(min_value=1)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "author",
            "ingredients",
            "name",
            "image",
            "text",
            "cooking_time",
        )

    def validate_image(self, value):
        """
        Custom validation for the 'image' field.
        'value' here is what Base64ImageField's to_internal_value() returns.
        If an empty string was provided initially, Base64ImageField might
        convert
        it to None or raise an error itself if "" is not valid base64 (which
        it isn't).
        This method is an additional check.
        """
        image_initial_payload = self.initial_data.get('image')
        if image_initial_payload == "":  # Explicitly check for an empty
            # string in the input
            raise serializers.ValidationError(
                "Поле image не может быть пустой строкой.")
        if not value:
            raise serializers.ValidationError(
                "Необходимо предоставить действительное изображение.")

        return value

    def validate(self, data):
        is_update = self.instance is not None
        if is_update and self.partial:  # self.partial is True for PATCH
            if (
                "ingredients" not in self.initial_data
            ):  # Check raw request data
                raise serializers.ValidationError(
                    {"ingredients": ["Это поле обязательно."]}
                )
        return data

    def validate_ingredients(self, ingredients):
        if not ingredients:
            raise serializers.ValidationError(
                "Нужно добавить хотя бы один ингредиент."
            )
        ingredient_ids = []
        for item in ingredients:
            ingredient_instance = item['id']
            if ingredient_instance.id in ingredient_ids:
                raise serializers.ValidationError(
                    "Ингредиенты не должны повторяться."
                )
            ingredient_ids.append(ingredient_instance.id)
        return ingredients

    def _add_ingredients(self, recipe, ingredients_data):
        """Helper to handle ingredient creation for a recipe."""
        RecipeIngredient.objects.bulk_create(
            (
                RecipeIngredient(
                    recipe=recipe,
                    ingredient=ingredient_item["id"],
                    amount=ingredient_item["amount"],
                )
                for ingredient_item in ingredients_data
            )
        )

    @transaction.atomic
    def create(self, validated_data):
        ingredients_data = validated_data.pop("ingredients")
        recipe = Recipe.objects.create(**validated_data)
        self._add_ingredients(recipe, ingredients_data)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop("ingredients", None)
        instance.recipeingredients.all().delete()
        self._add_ingredients(instance, ingredients_data)
        instance.save()  # нельзя вернуть метод safe()
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        return RecipeReadSerializer(
            instance, context={"request": self.context.get("request")}
        ).data


# --- Utility/Action Serializers ---


class ShortRecipeSerializer(serializers.ModelSerializer):
    """Simplified serializer for recipes in lists (favorite, cart)."""

    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")
        read_only_fields = fields


class SubscribedAuthorSerializer(UserDetailSerializer):
    """Serializer for displaying subscriptions (authors user follows)."""
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count', read_only=True)

    class Meta(UserDetailSerializer.Meta):
        fields = UserDetailSerializer.Meta.fields + (
            "recipes",
            "recipes_count",
        )

    def get_recipes(self, author_obj: User):  # Renamed obj
        request = self.context.get("request")
        try:
            limit_str = request.GET.get('recipes_limit')
            recipes_limit = int(limit_str) if limit_str is not None else None
        except (ValueError, TypeError):
            recipes_limit = 10**10

        recipes_queryset = author_obj.recipes.all()[:recipes_limit]

        serializer = ShortRecipeSerializer(
            recipes_queryset, many=True, read_only=True)
        return serializer.data
