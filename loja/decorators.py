from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def vendedor_required(view_func):
    @wraps(view_func)  # preserva o nome/docstring original da view (boas práticas)
    @login_required
    def view_protegida(request, *args, **kwargs):
        # hasattr() aqui é seguro: se o usuário não tiver Vendedor associado,
        # o Django simplesmente não encontra o atributo, sem lançar erro feio.
        if not hasattr(request.user, 'perfil_vendedor'):
            messages.error(request, 'Esta área é exclusiva para contas de Vendedor.')
            return redirect('loja:lista_produtos')
        return view_func(request, *args, **kwargs)

    return view_protegida


def vendedor_atual(request):
    """
    Único lugar que define QUEM é o dono dos dados na área do vendedor.
    Todas as consultas e criações dessa área partem daqui (e nunca de um id
    vindo da URL ou do formulário). Só use depois de @vendedor_required, que
    garante que o usuário está logado e tem perfil de vendedor.
    """
    return request.user.perfil_vendedor
