"""Camada de serviços (abstrai regras de negócio do app Streamlit).

Objetivos:
- Reduzir acoplamento entre UI e persistência.
- Facilitar testes automatizados.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List

try:
	import db_unified as db  # type: ignore
except Exception:
	import db  # type: ignore as db


def create_atendimento(*, empresa: str, nome: str, modalidade: str, data: str, hora: str,
					   laudo_pdf: Optional[str] = None, avaliacao_pdf: Optional[str] = None,
					   observacoes: Optional[str] = None) -> bool:
	"""Cria um atendimento delegando ao repositório de dados.
	Retorna True/False para simplicidade (poderia lançar exceções específicas)."""
	return db.inserir_atendimento(empresa, nome, modalidade, data, hora,
								   laudo_pdf, avaliacao_pdf, observacoes)


def list_atendimentos() -> List[Dict[str, Any]]:
	"""Retorna lista de atendimentos como dicionários uniformes.
	Para SQLite retornamos tuplas -> normalizamos em dict."""
	rows = db.listar_atendimentos()
	if not rows:
		return []
	first = rows[0]
	# Heurística: se for tupla do SQLite (len >=9) mapear manualmente.
	if isinstance(first, tuple):
		keys = ["id","empresa","nome","modalidade","data","hora","laudo_pdf","avaliacao_pdf","status","observacoes"]
		out: List[Dict[str, Any]] = []
		for r in rows:
			d = {}
			for i, k in enumerate(keys):
				if i < len(r):
					d[k] = r[i]
			out.append(d)
		return out
	# Já é lista de dicts (Postgres via db_unified retorna assim)
	return rows  # type: ignore


def pending_items() -> Dict[str, int]:
	"""Calcula pendências: sem laudo, sem avaliação, ambos.
	Usado para painel de pendências."""
	data = list_atendimentos()
	sem_laudo = sum(1 for r in data if not r.get("laudo_pdf"))
	sem_av = sum(1 for r in data if not r.get("avaliacao_pdf"))
	ambos = sum(1 for r in data if (not r.get("laudo_pdf") and not r.get("avaliacao_pdf")))
	return {"sem_laudo": sem_laudo, "sem_avaliacao": sem_av, "sem_ambos": ambos}


__all__ = [
	'create_atendimento','list_atendimentos','pending_items'
]

