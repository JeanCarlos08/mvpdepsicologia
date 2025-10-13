"""Camada de serviços (abstrai regras de negócio do app Streamlit).

Objetivos:
- Reduzir acoplamento entre UI e persistência.
- Facilitar testes automatizados.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List
import sys
from pathlib import Path

# Adicionar diretório pai ao path para importar db_unified
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db_unified as db  # Postgres-only

def create_atendimento(*, empresa: str, nome: str, modalidade: str, data: str, hora: str,
                       laudo_pdf: Optional[str] = None, avaliacao_pdf: Optional[str] = None,
                       observacoes: Optional[str] = None) -> bool:
    """Cria um novo atendimento."""
    new_id = db.inserir_atendimento(
        empresa, nome, modalidade, data, hora, laudo_pdf, avaliacao_pdf, observacoes
    )
    return bool(new_id)

def list_atendimentos() -> List[Dict[str, Any]]:
    """Lista todos os atendimentos."""
    return db.listar_atendimentos()

def pending_items() -> Dict[str, int]:
    """Retorna estatísticas de pendências."""
    data = list_atendimentos()
    return {
        "sem_laudo": sum(1 for r in data if not r.get("laudo_pdf")),
        "sem_avaliacao": sum(1 for r in data if not r.get("avaliacao_pdf")),
        "sem_ambos": sum(1 for r in data if not r.get("laudo_pdf") and not r.get("avaliacao_pdf")),
    }

__all__ = [
    'create_atendimento', 'list_atendimentos', 'pending_items'
]
