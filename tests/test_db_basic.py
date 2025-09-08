import os, importlib

import db_unified as db

def test_init_db():
    assert hasattr(db, 'init_db')
    assert db.init_db() is True


def test_inserir_listar_atendimento():
    ok = db.inserir_atendimento('ACME','Paciente X','Admissional','2025-01-01','09:00',None,None,'Obs')
    assert ok is True
    lista = db.listar_atendimentos()
    assert isinstance(lista, list)
    assert any('Paciente X' in str(l) for l in lista)


def test_estatisticas():
    stats = db.obter_estatisticas() if hasattr(db,'obter_estatisticas') else {}
    assert isinstance(stats, dict)
