"""Modelos de domínio (DTOs) para o núcleo da aplicação.
Separar dessas estruturas facilita validação futura e testes.
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

