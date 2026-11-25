from rest_framework.permissions import BasePermission


class IsVendedor(BasePermission):
    message = 'Esta API é exclusiva para contas de Vendedor.'

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario
            and usuario.is_authenticated
            and hasattr(usuario, 'perfil_vendedor')
        )
