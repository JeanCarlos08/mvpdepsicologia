"""Modelos de dom├¡nio (DTOs) para o n├║cleo da aplica├º├úo.
Separar dessas estruturas facilita valida├º├úo futura e testes.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(slots=True)
class AtendimentoDTO:
	id: Optional[int]
	empresa: str
	nome: str
	modalidade: str
	data: str
	hora: str
	laudo_pdf: Optional[str] = None
	avaliacao_pdf: Optional[str] = None
	status: str = "Agendado"
	observacoes: Optional[str] = None

__all__ = ['AtendimentoDTO']

