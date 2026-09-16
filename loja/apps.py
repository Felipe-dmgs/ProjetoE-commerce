from django.apps import AppConfig


class LojaConfig(AppConfig):
    """
    Configuração do app "loja". O Django usa essa classe para saber o nome
    do app e outros detalhes internos. Normalmente não precisamos mexer aqui.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loja'
    verbose_name = 'Loja (E-commerce)'  # nome amigável mostrado no admin
