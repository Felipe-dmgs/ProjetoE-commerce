from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Cupom


def normalizar_codigo_cupom(codigo):
    return codigo.strip().upper()


def validar_codigo_cupom_unico(vendedor, codigo, cupom_atual=None):
    existentes = Cupom.objects.filter(vendedor=vendedor, codigo__iexact=codigo)
    if cupom_atual is not None and cupom_atual.pk:
        existentes = existentes.exclude(pk=cupom_atual.pk)
    if existentes.exists():
        raise ValidationError('Você já possui um cupom com este código.')


def validar_validade_cupom(validade, cupom_atual=None):
    validade_mudou = (
        cupom_atual is None
        or not cupom_atual.pk
        or validade != cupom_atual.validade
    )
    if validade and validade_mudou and validade < timezone.localdate():
        raise ValidationError('A data de validade não pode ser no passado.')
