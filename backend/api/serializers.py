# backend/api/serializers.py
import base64
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from djoser.serializers import UserSerializer as DjoserUserSerializer
from djoser.serializers import UserCreateSerializer as DjoserUserCreateSerializer
from django.contrib.auth.models import AnonymousUser  # Import AnonymousUser

from .models import (
    Ingredient, Tag, Recipe, RecipeIngredient, Favorite, ShoppingCart,
    Subscription
)
from users.models import User  # Import custom User model

# --- Custom Fields ---


class Base64ImageField(serializers.ImageField):
    """Handles base64 encoded image strings."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            # base64 encoded image - decode
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)
        return super().to_internal_value(data)

# --- User Serializers ---


class CustomUserSerializer(DjoserUserSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)
    # REMOVE redundant source arguments:
    first_name = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)  # No source='first_name'
    last_name = serializers.CharField(
        required=False, allow_blank=True, allow_null=True)  # No source='last_name'
    # email = serializers.EmailField() # Usually handled by DjoserUserSerializer Meta
    # username = serializers.CharField() # Usually handled by DjoserUserSerializer Meta

    class Meta(DjoserUserSerializer.Meta):
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name',
            'is_subscribed', 'avatar'
        )
        read_only_fields = DjoserUserSerializer.Meta.read_only_fields + \
            ('is_subscribed',) if DjoserUserSerializer.Meta.read_only_fields else (
                'is_subscribed',)

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return False
        if not isinstance(obj, User) or not obj.pk:
            return False
        return Subscription.objects.filter(user=request.user, author=obj).exists()

    def to_representation(self, instance):
        if isinstance(instance, AnonymousUser) or not instance.is_authenticated:
            return {
                'id': None,
                'email': getattr(instance, 'email', ''),  # Safely get email
                # Safely get username
                'username': getattr(instance, 'username', 'Anonymous'),
                'first_name': '',
                'last_name': '',
                'is_subscribed': False,
                'avatar': None
            }
        representation = super().to_representation(instance)
        # Ensure is_subscribed is always present
        representation['is_subscribed'] = self.get_is_subscribed(instance)
        # Ensure avatar is handled correctly even if it's None from DB
        representation['avatar'] = instance.avatar.url if instance.avatar else None
        return representation


class CustomUserCreateSerializer(DjoserUserCreateSerializer):
    """Serializer for User registration."""
    class Meta(DjoserUserCreateSerializer.Meta):
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name', 'password'
        )


class AvatarSerializer(serializers.Serializer):
    """Serializer for avatar update."""
    avatar = Base64ImageField(required=True)

# --- Ingredient & Tag Serializers ---


class IngredientSerializer(serializers.ModelSerializer):
    """Serializer for Ingredient."""
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag."""
    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')

# --- Recipe Related Serializers ---


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Serializer for reading ingredients within a recipe."""
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeIngredientWriteSerializer(serializers.ModelSerializer):
    """Serializer for writing ingredient amounts when creating/updating recipes."""
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField()  # Validation handled by model

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')


class RecipeReadSerializer(serializers.ModelSerializer):
    """Serializer for reading/displaying Recipe details."""
    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        source='recipeingredients', many=True
    )
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)
    image = Base64ImageField()  # Read as URL, handle write in RecipeWriteSerializer

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text', 'cooking_time'
        )

    def get_user_from_context(self):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            return request.user
        return None

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
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    ingredients = RecipeIngredientWriteSerializer(many=True)
    image = Base64ImageField(required=True, allow_null=False)
    author = CustomUserSerializer(read_only=True)  # Set automatically

    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'ingredients', 'name', 'image',
            'text', 'cooking_time'
        )
    # In RecipeWriteSerializer

    def validate(self, data):
        is_update = self.instance is not None
        if is_update and self.partial:  # self.partial is True for PATCH
            if 'ingredients' not in self.initial_data:  # Check raw request data
                raise serializers.ValidationError(
                    {'ingredients': ['Это поле обязательно.']})
            if 'tags' not in self.initial_data:  # Check raw request data
                raise serializers.ValidationError(
                    {'tags': ['Это поле обязательно.']})
        return data

    def validate_ingredients(self, ingredients):
        if not ingredients:
            raise serializers.ValidationError(
                'Нужно добавить хотя бы один ингредиент.'
            )
        ingredient_ids = [item['id'] for item in ingredients]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                'Ингредиенты не должны повторяться.'
            )
        for item in ingredients:
            if int(item['amount']) < 1:
                raise serializers.ValidationError({
                    'ingredients': ('Количество ингредиента '
                                    'должно быть 1 или больше.')
                })
        return ingredients

    def validate_tags(self, tags):
        if not tags:
            raise serializers.ValidationError(
                'Нужно выбрать хотя бы один тег.')
        if len(tags) != len(set(tags)):
            raise serializers.ValidationError('Теги не должны повторяться.')
        return tags

    def validate_cooking_time(self, value):
        if value < 1:
            raise serializers.ValidationError(
                'Время приготовления должно быть не менее 1 минуты.'
            )
        return value

    def _add_ingredients_and_tags(self, recipe, ingredients_data, tags_data):
        """Helper to handle ingredient/tag creation for a recipe."""
        recipe.tags.set(tags_data)
        RecipeIngredient.objects.bulk_create([
            RecipeIngredient(
                recipe=recipe,
                # ingredient is validated to be an Ingredient instance
                ingredient=ingredient['id'],
                amount=ingredient['amount']
            ) for ingredient in ingredients_data
        ])

    @transaction.atomic  # Ensure atomicity
    def create(self, validated_data):
        tags_data = validated_data.pop('tags')
        ingredients_data = validated_data.pop('ingredients')

        # --- FIX: Remove author from validated_data before unpacking ---
        validated_data.pop('author', None)  # Safely remove author if it exists

        recipe = Recipe.objects.create(
            author=self.context['request'].user,  # Explicitly set the author
            **validated_data                     # Unpack the rest
        )
        self._add_ingredients_and_tags(recipe, ingredients_data, tags_data)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', None)
        tags_data = validated_data.pop('tags', None)

        # Handle ingredients update only if provided in PATCH
        if ingredients_data is not None:
            # Ensure this validation is suitable for updates
            self.validate_ingredients(ingredients_data)
            instance.recipeingredients.all().delete()  # Clear old through-model instances
            RecipeIngredient.objects.bulk_create([
                RecipeIngredient(
                    recipe=instance,
                    # 'id' is the Ingredient instance from validation
                    ingredient=ing_data['id'],
                    amount=ing_data['amount']
                ) for ing_data in ingredients_data
            ])

        # Handle tags update only if provided in PATCH
        if tags_data is not None:
            # Ensure this validation is suitable for updates
            self.validate_tags(tags_data)
            # .set() handles clearing and setting for direct M2M
            instance.tags.set(tags_data)

        # Update other fields if they are in validated_data
        instance.name = validated_data.get('name', instance.name)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get(
            'cooking_time', instance.cooking_time
        )
        if 'image' in validated_data:
            instance.image = validated_data.get('image', instance.image)

        instance.save()
        return instance

    def to_representation(self, instance):
        # Use the read serializer for representation after write actions
        return RecipeReadSerializer(
            instance,
            context={'request': self.context.get('request')}
        ).data

# --- Utility/Action Serializers ---


class ShortRecipeSerializer(serializers.ModelSerializer):
    """Simplified serializer for recipes in lists (favorite, cart)."""
    image = Base64ImageField(read_only=True)

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class SubscriptionSerializer(CustomUserSerializer):
    """Serializer for displaying subscriptions (authors user follows)."""
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(CustomUserSerializer.Meta):
        fields = CustomUserSerializer.Meta.fields + \
            ('recipes', 'recipes_count')
        read_only_fields = CustomUserSerializer.Meta.fields

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.query_params.get('recipes_limit')
        recipes = obj.recipes.all()
        if limit:
            try:
                recipes = recipes[:int(limit)]
            except (TypeError, ValueError):
                pass  # Ignore invalid limit param
        serializer = ShortRecipeSerializer(recipes, many=True, read_only=True)
        return serializer.data
