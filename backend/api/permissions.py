# backend/api/permissions.py
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    Assumes the model instance has an `author` attribute.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the author of the object.
        return obj.author == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allows read access to anyone, but write access only to admin users.
    """

    def has_permission(self, request, view):
        # Allow read-only methods for anyone
        if request.method in permissions.SAFE_METHODS:
            return True
        # Allow write methods only for admin users
        return request.user and request.user.is_staff
