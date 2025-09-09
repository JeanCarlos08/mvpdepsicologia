"""JULIANA - Gestão Clínica (MVP)"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
from datetime import datetime, date, time
import os, sys, pathlib, hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any

DATE_FORMAT = "%d/%m/%Y"
TIME_FORMAT = "%H:%M"
MAX_UPLOAD_MB = 50
PRIMARY_ACCENT = "#4DA768"
ADVANCED_UI = True  # Defina False para reverter facilmente as melhorias de design

_BASE_DIR = pathlib.Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
	sys.path.insert(0, str(_BASE_DIR))

try:
	import db_unified as db  # type: ignore
except Exception:
	import db  # type: ignore

def _load_security_module():
	"""Importa security.py; se falhar retorna fallback enxuto."""
	import importlib, importlib.util
	candidates = ["security"]
	sec_path = _BASE_DIR / "security.py"
	if sec_path.exists():
		candidates.append(str(sec_path))
	for cand in candidates:
		try:
			if cand.endswith(".py"):
				spec = importlib.util.spec_from_file_location("security", cand)
				if spec and spec.loader:
					mod = importlib.util.module_from_spec(spec)
					spec.loader.exec_module(mod)
					return mod
			else:
				return importlib.import_module(cand)
		except Exception:
			continue
	st.warning("Segurança em modo degradado")
	class _SecFallback:
		def log_access(self, *a, **k): return None
		def sanitize_input(self, x): return x if isinstance(x, str) else str(x)
		def validate_file_upload(self, *a, **k): return True, ""
		def generate_safe_filename(self, original_name: str):
			return f"fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
	return _SecFallback()

security = _load_security_module()

# Editor rich-text (opcional)
import importlib
try:
	_quill_mod = importlib.import_module("streamlit_quill")
	st_quill = getattr(_quill_mod, "st_quill", None)
except Exception:
	st_quill = None

class ModalidadeAtendimento(Enum):
	ADMISSIONAL = "Admissional"
	PERIODICO = "Periódico"
	DEMISSIONAL = "Demissional"
	RETORNO = "Retorno"

@dataclass
class AtendimentoData:
	empresa: str
	nome: str
	modalidade: str
	data: str
	hora: str
	laudo_pdf: Optional[str] = None
	avaliacao_pdf: Optional[str] = None

def hex_to_rgba(hex_color: str, alpha: float = 0.10) -> str:
	"""Converte #RRGGBB ou #RGB em rgba(r,g,b,a)."""
	try:
		if not hex_color:
			return "rgba(77,167,104,0.08)"
		c = hex_color.strip()
		if c.lower().startswith("rgba"):
			return c
		if c.lower().startswith("rgb("):
			vals = c[c.find("(")+1:c.find(")")].split(",")
			r, g, b = [int(v) for v in vals[:3]]
			return f"rgba({r},{g},{b},{alpha})"
		if c.startswith("#"):
			c = c[1:]
		if len(c) == 3:
			r, g, b = [int(ch*2, 16) for ch in c]
		elif len(c) == 6:
			r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
		else:
			return "rgba(77,167,104,0.08)"
		return f"rgba({r},{g},{b},{alpha})"
	except Exception:
		return "rgba(77,167,104,0.08)"

def save_uploaded_pdf(uploaded_file) -> Optional[str]:
	"""Valida e salva PDF retornando caminho ou None."""
	if uploaded_file is None:
		return None
	try:
		ok, msg = security.validate_file_upload(uploaded_file.name, len(uploaded_file.getvalue()), max_size_mb=MAX_UPLOAD_MB)
		if not ok:
			st.error(msg)
			return None
		def _uploads_dir() -> str:
			base_dir = os.path.dirname(__file__)
			dest_local = os.path.join(base_dir, "uploads")
			os.makedirs(dest_local, exist_ok=True)
			return dest_local
		safe_name = security.generate_safe_filename(uploaded_file.name)
		dest = _uploads_dir()
		path = os.path.join(dest, safe_name)
		file_bytes = uploaded_file.getvalue()
		with open(path, "wb") as f:
			f.write(file_bytes)
		# Hash
		try:
			h = hashlib.sha256(file_bytes).hexdigest()
			hashes_path = os.path.join(dest, "hashes.csv")
			import csv, time
			new_row = [safe_name, h, int(time.time())]
			write_header = not os.path.exists(hashes_path)
			with open(hashes_path, "a", newline="", encoding="utf-8") as cf:
				w = csv.writer(cf)
				if write_header:
					w.writerow(["arquivo","sha256","epoch"])
				w.writerow(new_row)
		except Exception:
			pass
		return path
	except Exception as e:
		st.error(f"Falha ao salvar arquivo: {e}")
		return None

def display_cards(cards: List[Dict[str, Any]]) -> None:
	"""Versão simplificada: cards estáticos com borda neon chamativa."""
	if not cards:
		return
	cols = st.columns(len(cards))
	for i, c in enumerate(cards):
		with cols[i]:
			icon = c.get("icon", "📦")
			title = c.get("title", "Item")
			value = c.get("value", 0)
			color = c.get("acc", "#39ff14") or "#39ff14"
			def _esc(s: Any) -> str:
				try:
					return (str(s)
						.replace("&", "&amp;")
						.replace("<", "&lt;")
						.replace(">", "&gt;")
						.replace("'", "&#39;")
						.replace('"', "&quot;")
					)
				except Exception:
					return ""
			safe_title = _esc(title)
			st.markdown(f"""
			<div class='simple-card' style='border-color:{color};'>
				<div class='sc-icon'>{icon}</div>
				<div class='sc-title'>{safe_title}</div>
				<div class='sc-value'>{value}</div>
			</div>
			""", unsafe_allow_html=True)

def apply_custom_css(dark_mode: bool = False, advanced: bool = ADVANCED_UI) -> None:
	"""Injeta CSS global. Se advanced=False usa tema básico. Dark mode com override."""
	if not advanced:
		st.markdown("""
		<style>
		.stApp { background:#f5fff6; }
		.simple-card { background:#ffffffcc; border:2px solid #4DA768; border-radius:14px; padding:14px; }
		</style>
		""", unsafe_allow_html=True)
		return

	# Paleta e design avançado
	base_css = f"""
	<style>
	:root {{
		--acc-1:{PRIMARY_ACCENT};
		--acc-2:#1d3b29;
		--bg-grad:linear-gradient(135deg,#99E89D 0%,#7FD784 55%,#4DA768 100%);
		--card-bg:linear-gradient(145deg,rgba(255,255,255,0.65) 0%,rgba(255,255,255,0.30) 100%);
		--card-border:#39ff14;
		--radius-xl:22px; --radius-lg:18px; --radius-md:12px;
		--shadow-sm:0 2px 4px -2px rgba(0,0,0,0.18);
		--shadow-md:0 6px 18px -4px rgba(0,0,0,0.25);
		--shadow-neon:0 0 6px #39ff14,0 0 18px rgba(57,255,20,.55),0 0 32px rgba(57,255,20,.35);
		--transition-base:.35s cubic-bezier(.16,.8,.24,1);
		--sidebar-grad:linear-gradient(200deg,#4DA768 0%,#3A8A56 50%,#2c5f3d 100%);
	}}
	body {{ font-family: 'Inter', system-ui, Arial, sans-serif; }}
	.stApp {{ background: var(--bg-grad); background-attachment:fixed; }}
	section[data-testid="stSidebar"] {{ width:360px !important; }}
	section[data-testid="stSidebar"]>div {{ background:var(--sidebar-grad)!important; backdrop-filter:blur(6px) saturate(1.15); }}
	section[data-testid="stSidebar"] * {{ color:#fff !important; }}
	/* Scrollbar */
	::-webkit-scrollbar {{ width:10px; }}
	::-webkit-scrollbar-track {{ background:rgba(255,255,255,0.1); }}
	::-webkit-scrollbar-thumb {{ background:#2f6b44; border-radius:20px; border:2px solid rgba(255,255,255,0.2); }}
	::-webkit-scrollbar-thumb:hover {{ background:#368250; }}
	/* Radio menu */
	section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap:4px !important; }}
	section[data-testid="stSidebar"] div[role="radiogroup"] label {{ display:flex; align-items:center; gap:14px; padding:8px 12px; border-radius:16px; cursor:pointer; transition:var(--transition-base); font-weight:600; font-size:0.95rem; letter-spacing:.3px; position:relative; }}
	section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background:rgba(255,255,255,0.12); transform:translateX(2px); }}
	section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {{ background:linear-gradient(135deg,#4DA768 0%,#30714a 100%); box-shadow:0 4px 14px -4px rgba(0,0,0,.45),0 0 0 1px rgba(255,255,255,0.25) inset; }}
	section[data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {{ margin:0; }}
	/* Toggle dark mode indicator */
	.dark-label {{ font-size:0.75rem; opacity:.75; margin-top:-4px; }}
	/* Cards */
	.simple-card {{ background:var(--card-bg); backdrop-filter:blur(6px) saturate(1.15); border:3px solid var(--card-border); border-radius:var(--radius-lg); padding:20px 16px 18px; box-shadow:0 0 2px #39ff14,0 0 8px rgba(57,255,20,0.40); text-align:center; min-height:160px; display:flex; flex-direction:column; justify-content:center; gap:6px; position:relative; overflow:hidden; transition:var(--transition-base); }}
	.simple-card:before {{ content:""; position:absolute; inset:0; background:radial-gradient(circle at 20% 15%,rgba(255,255,255,.65),rgba(255,255,255,0)); opacity:.35; pointer-events:none; }}
	.simple-card:hover {{ transform:translateY(-8px) scale(1.025); box-shadow:var(--shadow-neon); }}
	.sc-icon {{ font-size:2.35rem; line-height:1; filter:drop-shadow(0 4px 6px rgba(0,0,0,0.25)); }}
	.sc-title {{ font-weight:800; font-size:.80rem; letter-spacing:1px; text-transform:uppercase; color:#0d301c; opacity:.9; }}
	.sc-value {{ font-weight:900; font-size:2.05rem; letter-spacing:.5px; color:#042; text-shadow:0 0 6px rgba(57,255,20,0.65); }}
	/* Headings */
	h1,h2,h3,h4,h5,h6 {{ font-family:'Inter',system-ui,Arial Black,sans-serif; font-weight:800; letter-spacing:.5px; }}
	/* Buttons */
	button[kind="primary"] {{ background:linear-gradient(135deg,#4DA768 0%,#3b8a56 100%) !important; border:0 !important; box-shadow:0 4px 14px -4px rgba(0,0,0,0.4); font-weight:700; letter-spacing:.4px; transition:var(--transition-base); }}
	button[kind="primary"]:hover {{ filter:brightness(1.07); transform:translateY(-2px); }}
	button[kind="secondary"] {{ border-radius:10px !important; }}
	/* Dataframe */
	.dataframe thead th {{ position:sticky; top:0; backdrop-filter:blur(4px); background:rgba(255,255,255,0.75)!important; }}
	.dataframe tbody tr:hover {{ background:rgba(77,167,104,0.10)!important; }}
	.dataframe tbody tr:nth-child(even) {{ background:rgba(255,255,255,0.40); }}
	/* Focus */
	button:focus, input:focus, select:focus, textarea:focus {{ outline:2px solid #39ff14 !important; outline-offset:2px; box-shadow:0 0 0 3px rgba(57,255,20,0.35)!important; }}
	/* Badges */
	.badge {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:0.60rem; font-weight:700; letter-spacing:.6px; text-transform:uppercase; backdrop-filter:blur(4px); }}
	.badge-ok {{ background:#2ecc71; color:#fff; }}
	.badge-warn {{ background:#f1c40f; color:#1d2100; }}
	.badge-err {{ background:#e74c3c; color:#fff; }}
	.badge-info {{ background:#3498db; color:#fff; }}
	/* Skeleton */
	.skel {{ background:linear-gradient(90deg, rgba(255,255,255,0.15) 25%, rgba(255,255,255,0.40) 50%, rgba(255,255,255,0.15) 75%); background-size:200% 100%; animation:skel 1.2s ease-in-out infinite; border-radius:10px; }}
	@keyframes skel {{ 0%{{background-position:0 0;}} 100%{{background-position:-200% 0;}} }}
	/* Nav header */
	.nav-header {{ display:flex; align-items:center; gap:10px; font-size:1.05rem; font-weight:800; padding:6px 4px 4px; margin:4px 0 16px; letter-spacing:.5px; }}
	/* Utility containers */
	.glass-box {{ background:linear-gradient(145deg,rgba(255,255,255,0.55) 0%,rgba(255,255,255,0.22) 100%); padding:1.4rem 1.2rem; border-radius:20px; border:1px solid rgba(255,255,255,0.55); box-shadow:0 10px 28px -10px rgba(0,0,0,0.35); backdrop-filter:blur(8px) saturate(1.4); }}
	/* Dark overrides serão adicionados separadamente sem necessidade de classe */
	</style>
	"""
	st.markdown(base_css, unsafe_allow_html=True)
	if dark_mode:
		st.markdown(inject_dark_theme(), unsafe_allow_html=True)

def inject_dark_theme() -> str:
	"""CSS de override para modo escuro (separado para reutilização/teste)."""
	return """
	<style>
	:root { --bg-grad:linear-gradient(135deg,#062312 0%,#0d4424 55%,#0a301b 100%); --card-bg:linear-gradient(145deg,rgba(15,40,25,0.85) 0%,rgba(30,70,40,0.55) 100%); }
	.stApp { color:#f5fff6; }
	h1,h2,h3,h4,h5,h6 { color:#e8ffee !important; }
	.simple-card { border-color:#39ff14; box-shadow:0 0 3px #39ff14,0 0 10px rgba(57,255,20,0.35); }
	.sc-title { color:#d9ffe9; }
	.sc-value { color:#d7ffe4; text-shadow:0 0 10px rgba(57,255,20,0.85); }
	.dataframe thead th { background:rgba(10,40,22,0.85)!important; color:#d9ffe9 !important; }
	.dataframe tbody tr:nth-child(even) { background:rgba(255,255,255,0.06); }
	section[data-testid="stSidebar"]>div { background:linear-gradient(200deg,#113a22 0%,#0e301c 55%,#0b2716 100%)!important; }
	section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) { background:linear-gradient(135deg,#145d33 0%,#0d3d22 100%); }
	</style>
	"""

def apply_plotly_theme(dark_mode: bool = False) -> None:
	"""Registra e aplica templates Plotly (claro/escuro) alinhados ao tema UI."""
	light = {
		"layout": {
			"paper_bgcolor": "rgba(0,0,0,0)",
			"plot_bgcolor": "rgba(255,255,255,0.55)",
			"font": {"family": "Inter,Arial,sans-serif", "color": "#123"},
			"title": {"x": 0.02, "font": {"size": 20, "color": "#123", "family": "Inter,Arial Black,sans-serif"}},
			"legend": {"bgcolor": "rgba(255,255,255,0.6)", "borderwidth": 0},
			"margin": {"l": 40, "r": 30, "t": 60, "b": 40},
			"xaxis": {"gridcolor": "rgba(0,0,0,0.08)", "zeroline": False},
			"yaxis": {"gridcolor": "rgba(0,0,0,0.08)", "zeroline": False},
			"colorway": ["#4DA768", "#7FD784", "#2ecc71", "#3A8A56", "#99E89D", "#16a085"],
		}
	}
	dark = {
		"layout": {
			"paper_bgcolor": "rgba(0,0,0,0)",
			"plot_bgcolor": "rgba(15,40,25,0.55)",
			"font": {"family": "Inter,Arial,sans-serif", "color": "#e8ffee"},
			"title": {"x": 0.02, "font": {"size": 20, "color": "#d9ffe9", "family": "Inter,Arial Black,sans-serif"}},
			"legend": {"bgcolor": "rgba(15,40,25,0.35)", "borderwidth": 0},
			"margin": {"l": 40, "r": 30, "t": 60, "b": 40},
			"xaxis": {"gridcolor": "rgba(255,255,255,0.12)", "zeroline": False, "tickcolor": "rgba(255,255,255,0.4)"},
			"yaxis": {"gridcolor": "rgba(255,255,255,0.12)", "zeroline": False, "tickcolor": "rgba(255,255,255,0.4)"},
			"colorway": ["#39ff14", "#7FD784", "#4DA768", "#2ecc71", "#16a085", "#3A8A56"],
		}
	}
	pio.templates["juliana_light"] = light
	pio.templates["juliana_dark"] = dark
	pio.templates.default = "juliana_dark" if dark_mode else "juliana_light"


def configure_page() -> None:
	"""Configura parâmetros básicos da página Streamlit."""
	st.set_page_config(
		page_title="🧠 JULIANA - Gestão Clínica",
		page_icon="🧠",
		layout="wide",
		initial_sidebar_state="expanded",
	)

def render_page_header(title: str, subtitle: str = "", inverse: bool = False) -> None:
	title_color = "#ffffff" if inverse else "var(--acc-2)"
	subtitle_color = "#ffffff" if inverse else "var(--acc-2)"
	title_border = "rgba(255,255,255,0.35)" if inverse else "rgba(77,167,104,0.25)"
	subtitle_border = "rgba(255,255,255,0.25)" if inverse else "rgba(77,167,104,0.18)"
	container_bg = (
		"linear-gradient(135deg, rgba(77,167,104,0.25) 0%, rgba(77,167,104,0.15) 100%)"
		if inverse else
		"linear-gradient(135deg, rgba(255,255,255,0.10) 0%, rgba(77,167,104,0.10) 100%)"
	)
	title_bg = (
		# Removido gradiente para não "lavar" a cor do texto ao fundo
		"none"
	)
	subtitle_bg = (
		# Também removido gradiente do subtítulo
		"none"
	)
	st.markdown(f"""
	<div style='
		text-align: center;
		background: {container_bg};
		border-radius: 18px;
		padding: 2.2rem 2rem;
		margin: 1rem 0 2rem 0;
		border: 1px solid {title_border};
		backdrop-filter: blur(10px);
		box-shadow: 0 10px 28px rgba(0,0,0,0.12);
		position: relative;
	'>
		<div style="position:absolute;left:18px;top:18px;font-size:1.6rem;">✨</div>
		<h1 style='
			font-size: 2.5rem; 
			font-weight: 900; 
			color: {title_color}; 
			background-image: {title_bg};
			background-size: 100% 40%;
			background-repeat: no-repeat;
			background-position: 0 85%;
			border-bottom: 2px solid {title_border};
			padding-bottom: 3px;
			margin: 0 0 0.5rem 0;
			text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
		'>{title}</h1>
		<p style='
			font-size: 1.1rem; 
			color: {subtitle_color}; 
			background-image: {subtitle_bg};
			background-size: 100% 30%;
			background-repeat: no-repeat;
			background-position: 0 85%;
			border-bottom: 1px solid {subtitle_border};
			padding-bottom: 2px;
			margin: 0.5rem 0 0 0;
			text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
		'>{subtitle}</p>
	</div>
	""", unsafe_allow_html=True)


class DatabaseManager:
	@staticmethod
	@st.cache_resource
	def initialize_database() -> bool:
		try:
			return bool(db.init_db())
		except Exception as e:
			st.error(f"Falha ao inicializar DB: {e}")
			return False

	@staticmethod
	def get_backend_engine() -> str:
		try:
			if hasattr(db, 'USE_PG') and getattr(db, 'USE_PG'):
				return 'Postgres'
		except Exception:
			pass
		return 'SQLite'

	@staticmethod
	@st.cache_data(ttl=30)
	def get_all_appointments() -> List[Dict[str, Any]]:
		try:
			return db.listar_atendimentos() or []
		except Exception as e:
			st.error(f"Erro ao buscar atendimentos: {e}")
			return []

	@staticmethod
	@st.cache_data(ttl=60)
	def get_statistics() -> Dict[str, Any]:
		try:
			return db.obter_estatisticas() or {"total_atendimentos": 0, "atendimentos_hoje": 0, "modalidades": {}}
		except Exception as e:
			st.error(f"Erro ao calcular estatísticas: {e}")
			return {"total_atendimentos": 0, "atendimentos_hoje": 0, "modalidades": {}}

	@staticmethod
	def add_appointment(appointment_data: AtendimentoData) -> bool:
		try:
			success = db.inserir_atendimento(
				appointment_data.empresa,
				appointment_data.nome,
				appointment_data.modalidade,
				appointment_data.data,
				appointment_data.hora,
				appointment_data.laudo_pdf,
				appointment_data.avaliacao_pdf
			)
			if success:
				st.cache_data.clear()
			return success
		except Exception as e:
			st.error(f"Erro ao adicionar atendimento: {e}")
			return False

	@staticmethod
	def update_appointment(
		apt_id: int,
		empresa: Optional[str] = None,
		nome: Optional[str] = None,
		modalidade: Optional[str] = None,
		data: Optional[str] = None,
		hora: Optional[str] = None,
		laudo_pdf: Optional[str] = None,
		avaliacao_pdf: Optional[str] = None,
		status: Optional[str] = None,
		observacoes: Optional[str] = None,
	) -> bool:
		"""Atualiza um atendimento; apenas campos não-nulos são enviados ao DB."""
		try:
			campos: Dict[str, Any] = {}
			if empresa is not None: campos["empresa"] = empresa
			if nome is not None: campos["nome"] = nome
			if modalidade is not None: campos["modalidade"] = modalidade
			if data is not None: campos["data"] = data
			if hora is not None: campos["hora"] = hora
			if laudo_pdf is not None: campos["laudo_pdf"] = laudo_pdf
			if avaliacao_pdf is not None: campos["avaliacao_pdf"] = avaliacao_pdf
			if status is not None: campos["status"] = status
			if observacoes is not None: campos["observacoes"] = observacoes
			success = db.atualizar_atendimento(apt_id, **campos)
			if success:
				st.cache_data.clear()
			return success
		except Exception as e:
			st.error(f"Erro ao atualizar atendimento: {e}")
			return False

	@staticmethod
	def delete_appointment(apt_id: int) -> bool:
		try:
			success = db.excluir_atendimento(apt_id)
			if success:
				st.cache_data.clear()
			return success
		except Exception as e:
			st.error(f"Erro ao excluir atendimento: {e}")
			return False





class UIComponents:
	@staticmethod
	def render_header(page: str) -> None:
		# Páginas controlam seus próprios títulos/headers
		pass

	@staticmethod
	def render_sidebar() -> Dict[str, Any]:
		# Cabeçalho de navegação alinhado
		st.sidebar.markdown("<div class='nav-header'>🧭 <span>Navegação</span></div>", unsafe_allow_html=True)
		# Toggle Dark Mode (design intensificado) - estabilizado
		if 'dark_mode' not in st.session_state:
			st.session_state.dark_mode = False
		
		# Usar key estável para evitar recriar widget
		dark_mode = st.sidebar.toggle("🌙 Dark Mode", value=st.session_state.dark_mode, 
									  help="Alternar modo escuro/claro (aplica tema avançado)",
									  key="stable_dark_mode")
		st.session_state.dark_mode = dark_mode
		st.sidebar.caption("Interface avançada" if ADVANCED_UI else "Interface básica")
		menu_items = [
			"🏠 Painel",
			"📝 Atendimentos",
			"📊 Relatórios",
			"📄 Carregar",
			"⚙️ Configurações",
		]
		# Key estável para evitar recriar radio
		page = st.sidebar.radio("", menu_items, index=0, key="stable_main_nav")

		# Ações rápidas (contextuais) – somente em páginas operacionais
		if page in ("📝 Atendimentos", "📊 Relatórios"):
			with st.sidebar.expander("⚡ Ações Rápidas", expanded=False):
				st.caption("Atalhos úteis:")
				st.write("• Use filtros abaixo para refinar lista")
				st.write("• Exporte dados no rodapé da página")

		# Filtros contextuais (somente para Atendimentos e Relatórios)
		date_filter = None
		modalidade_filter = ""
		empresa_filter = ""
		paciente_filter = ""

		# Preferências UI
		# (Seção de aparência removida a pedido. Usando defaults: animações ON, modo compacto OFF, neon ON.)
		if "ui_disable_anim" not in st.session_state:
			st.session_state.ui_disable_anim = False
		if "ui_compact_cards" not in st.session_state:
			st.session_state.ui_compact_cards = False
		if "ui_neon_cards" not in st.session_state:
			st.session_state.ui_neon_cards = True
		if page in ("📝 Atendimentos", "📊 Relatórios"):
			st.sidebar.markdown("### 🔍 Filtros")
			use_date_filter = st.sidebar.checkbox("Filtrar por data", value=False)
			date_filter = st.sidebar.date_input("Data:") if use_date_filter else None
			modalidade_filter = st.sidebar.selectbox(
				"Modalidade:", [""] + [m.value for m in ModalidadeAtendimento], index=0,
				format_func=lambda x: "Selecione..." if x == "" else x,
			)
			empresa_filter = st.sidebar.text_input("Empresa:", value="")
			paciente_filter = st.sidebar.text_input("Paciente:", value="")

		return {
			"page": page,
			"date_filter": date_filter,
			"modalidade_filter": modalidade_filter,
			"empresa_filter": empresa_filter,
			"paciente_filter": paciente_filter,
			"disable_anim": st.session_state.ui_disable_anim,
			"compact_cards": st.session_state.ui_compact_cards,
			"dark_mode": dark_mode,  # Usar variável local ao invés do session_state
		}

	@staticmethod
	def render_appointment_form() -> Optional[AtendimentoData]:
		with st.expander("➕ Cadastrar Novo Atendimento", expanded=False):
			with st.form("appointment_form", clear_on_submit=True):
				col1, col2 = st.columns(2)
				with col1:
					empresa = st.text_input("🏢 Empresa/Organização")
					modalidade = st.selectbox("🏥 Modalidade", [m.value for m in ModalidadeAtendimento])
					data_sel = st.date_input("📅 Data", min_value=date.today())
				with col2:
					nome = st.text_input("👤 Nome do Paciente")
					hora_sel = st.time_input("🕐 Horário")
				c1, c2, _ = st.columns([1, 1, 4])
				with c1:
					submitted = st.form_submit_button("💾 Salvar", type="primary")
				with c2:
					st.form_submit_button("🔄 Limpar")
				if submitted:
					if not empresa or not nome:
						st.error("Preencha os campos obrigatórios.")
					else:
						return AtendimentoData(
							empresa=empresa.strip(),
							nome=nome.strip(),
							modalidade=modalidade,
							data=data_sel.strftime(DATE_FORMAT),
							hora=hora_sel.strftime(TIME_FORMAT),
						)
		return None


class DashboardPage:
	@staticmethod
	def render() -> None:
		# Cabeçalho unificado (hero) do Dashboard
		render_page_header("🧠 JULIANA - Gestão Clínica", "Dashboard Executivo — Indicadores e métricas principais do sistema", inverse=True)

		# Status de conexão
		conn_ok = False
		try:
			conn_ok = db.verificar_conexao()
		except Exception:
			conn_ok = False
		# Detecta tipo de backend (se módulo db_unified expõe USE_PG ou fallback)
		backend = "SQLite"
		try:
			if hasattr(db, 'USE_PG') and getattr(db, 'USE_PG'):
				backend = "Postgres"
		except Exception:
			backend = "SQLite"
		badge_class = 'pg' if backend == 'Postgres' else 'sqlite'
		st.caption(f"🔌 Banco de Dados: {'Conectado' if conn_ok else 'Desconectado'} <span class='db-badge {badge_class}'>{backend}</span>", unsafe_allow_html=True)

		# Estatísticas + fallback direto dos registros para evitar zeros indevidos
		try:
			stats = DatabaseManager.get_statistics() or {}
			appts = DatabaseManager.get_all_appointments() or []
			total_at = len(appts)
			empresas_unicas = {str(a[1]) for a in appts if len(a) > 1}
			laudos_env = sum(1 for a in appts if len(a) > 6 and a[6])
			avals_env = sum(1 for a in appts if len(a) > 7 and a[7])
			total_emp = len(empresas_unicas)
		except Exception as e:
			st.error(f"Erro ao carregar estatísticas: {e}")
			total_at = total_emp = laudos_env = avals_env = 0

		# Pendências
		try:
			from services import pending_items
			pend = pending_items()
		except Exception:
			pend = {"sem_laudo":0,"sem_avaliacao":0,"sem_ambos":0}

		# Cards idênticos
		cards = [
			{"icon": "👥", "title": "Atendimentos", "value": total_at, "acc": PRIMARY_ACCENT, "soft": True, "spark": [0,2,3,5,4,6,7]},
			{"icon": "🏢", "title": "Empresas", "value": total_emp, "acc": PRIMARY_ACCENT, "soft": True, "spark": [0,1,1,2,2,3,3]},
			{"icon": "📄", "title": "Relatórios", "value": laudos_env, "acc": PRIMARY_ACCENT, "soft": True, "spark": [0,0,1,1,2,2,2]},
			{"icon": "📝", "title": "Avaliações", "value": avals_env, "acc": PRIMARY_ACCENT, "soft": True, "spark": [0,1,0,1,1,1,2]},
			{"icon": "⚠️", "title": "Pend. Laudo", "value": pend.get("sem_laudo",0), "acc": "#e67e22", "soft": True},
			{"icon": "⚠️", "title": "Pend. Avaliação", "value": pend.get("sem_avaliacao",0), "acc": "#d35400", "soft": True},
			{"icon": "⏳", "title": "Pend. Ambos", "value": pend.get("sem_ambos",0), "acc": "#c0392b", "soft": True},
		]
		display_cards(cards)

		# Dica se não houver dados
		if not total_at:
			st.info("Sem dados ainda. Vá em ⚙️ Configurações > 'Popular dados de exemplo (demo)' para visualizar o painel.")

		# Gráfico de modalidades
		if stats.get("modalidades"):
			vals = list(stats["modalidades"].values())
			labels = list(stats["modalidades"].keys())
			fig = px.pie(values=vals, names=labels, title="Distribuição por Modalidade")
			fig.update_traces(textposition="inside", textinfo="percent+label", pull=[0.04]*len(vals))
			fig.update_layout(legend_title_text="Modalidade", height=420)
			st.plotly_chart(fig, use_container_width=True)


class AppointmentsPage:
	@staticmethod
	def render(filters: Dict) -> None:
		render_page_header("📝 Atendimentos", "Gerenciamento de Consultas e Procedimentos", inverse=True)
		st.markdown("<div class='reports-scope'>", unsafe_allow_html=True)

		# Excluir (com snapshot para desfazer)
		try:
			appts = DatabaseManager.get_all_appointments()
			if appts:
				df_head = pd.DataFrame(
					appts,
					columns=[
						"ID",
						"Empresa",
						"Nome",
						"Modalidade",
						"Data",
						"Hora",
						"Laudo PDF",
						"Avaliação PDF",
						"Status",
						"Observações",
					],
				)
				col_sel, col_del, col_undo = st.columns([3, 1, 1])
				with col_sel:
					labels = [
						f"ID {int(r.ID)} — {r.Nome} • {r.Empresa} • {r.Data} {r.Hora}"
						for _, r in df_head.iterrows()
					]
					opt = dict(zip(labels, df_head.ID.astype(int).tolist()))
					chosen = st.selectbox("Selecione para excluir:", labels) if labels else None
				with col_del:
					if st.button("🗑️ Excluir") and chosen:
						sel_id = opt.get(chosen)
						if sel_id is None:
							st.error("Seleção inválida.")
						else:
							snapshot = df_head[df_head.ID == sel_id].iloc[0].to_dict()
							st.session_state["last_deleted_snapshot"] = snapshot
							if DatabaseManager.delete_appointment(int(sel_id)):
								st.success(f"Excluído ID {sel_id}.")
								st.rerun()
				with col_undo:
					if st.session_state.get("last_deleted_snapshot"):
						if st.button("↩️ Desfazer"):
							s = st.session_state["last_deleted_snapshot"]
							db.inserir_atendimento(
								s.get("Empresa", ""),
								s.get("Nome", ""),
								s.get("Modalidade", ""),
								s.get("Data", ""),
								s.get("Hora", ""),
								s.get("Laudo PDF"),
							 s.get("Avaliação PDF"),
								s.get("Observações"),
							)
							st.session_state.pop("last_deleted_snapshot", None)
							st.success("Registro restaurado.")
							st.rerun()
		except Exception as e:
			st.error(f"Erro ao montar exclusão/desfazer: {e}")

		# Cadastro com anexos (Laudo/Avaliação)
		with st.expander("➕ Cadastrar Novo Atendimento", expanded=False):
			with st.form("appointment_form_new", clear_on_submit=True):
				col1, col2 = st.columns(2)
				with col1:
					empresa = st.text_input("🏢 Empresa/Organização")
					modalidade = st.selectbox("🏥 Modalidade", [m.value for m in ModalidadeAtendimento])
					data_sel = st.date_input("📅 Data", min_value=date.today())
				with col2:
					nome = st.text_input("👤 Nome do Paciente")
					hora_sel = st.time_input("🕐 Horário")

				st.markdown("#### 📎 Anexos (opcional)")
				c1a, c2a = st.columns(2)
				with c1a:
					up_laudo = st.file_uploader("📎 Laudo PDF", type=["pdf"], key="up_laudo_new", help="Limite de 50 MB por arquivo • PDF")
					st.caption("Limite de 50 MB por arquivo • PDF")
					if up_laudo is not None:
						try:
							size_mb = len(up_laudo.getvalue()) / (1024 * 1024)
							st.caption(f"Selecionado: {up_laudo.name} — {size_mb:.2f} MB")
						except Exception:
							st.caption(f"Selecionado: {up_laudo.name}")
						st.markdown("<span class='uploader-badge'>✅ Arquivo selecionado</span>", unsafe_allow_html=True)
						c_la1, c_la2 = st.columns([6,1])
						with c_la2:
							if st.button("🗑️", key="clear_up_laudo_new", help="Remover seleção"):
								st.session_state["up_laudo_new"] = None
								st.rerun()
				with c2a:
					up_avaliacao = st.file_uploader("📝 Avaliação PDF", type=["pdf"], key="up_aval_new", help="Limite de 50 MB por arquivo • PDF")
					st.caption("Limite de 50 MB por arquivo • PDF")
					if up_avaliacao is not None:
						try:
							size_mb2 = len(up_avaliacao.getvalue()) / (1024 * 1024)
							st.caption(f"Selecionado: {up_avaliacao.name} — {size_mb2:.2f} MB")
						except Exception:
							st.caption(f"Selecionado: {up_avaliacao.name}")
						st.markdown("<span class='uploader-badge'>✅ Arquivo selecionado</span>", unsafe_allow_html=True)
						c_av1, c_av2 = st.columns([6,1])
						with c_av2:
							if st.button("🗑️", key="clear_up_aval_new", help="Remover seleção"):
								st.session_state["up_aval_new"] = None
								st.rerun()

				c1, c2, _ = st.columns([1, 1, 4])
				with c1:
					submitted_new = st.form_submit_button("💾 Salvar", type="primary")
				with c2:
					st.form_submit_button("🔄 Limpar")

				if submitted_new:
					if not empresa or not nome:
						st.error("Preencha os campos obrigatórios.")
					else:
						laudo_path = save_uploaded_pdf(up_laudo)
						avaliacao_path = save_uploaded_pdf(up_avaliacao)

						novo = AtendimentoData(
							empresa=security.sanitize_input(empresa),
							nome=security.sanitize_input(nome),
							modalidade=modalidade,
							data=data_sel.strftime(DATE_FORMAT),
							hora=hora_sel.strftime(TIME_FORMAT),
							laudo_pdf=laudo_path,
							avaliacao_pdf=avaliacao_path,
						)
						if DatabaseManager.add_appointment(novo):
							security.log_access("ADD_APPOINTMENT", f"{security.sanitize_input(nome)} - {security.sanitize_input(empresa)}")
							st.success("✅ Atendimento cadastrado!")
							st.rerun()

		AppointmentsPage._render_table(filters)

	@staticmethod
	def _render_table(filters: Dict) -> None:
		appts = DatabaseManager.get_all_appointments()
		if not appts:
			st.info("Nenhum atendimento encontrado.")
			return

		# Ações rápidas (recarregar / pendências / limpar)
		a1, a2, a3, a4 = st.columns([1,1,1,2])
		with a1:
			if st.button("🔄 Recarregar", help="Recarrega dados do banco"):
				st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
		with a2:
			if st.button("⚠️ Sem Laudo", help="Filtrar atendimentos sem laudo"):
				filters["quick"] = "sem_laudo"
		with a3:
			if st.button("⚠️ Sem Avaliação", help="Filtrar atendimentos sem avaliação"):
				filters["quick"] = "sem_avaliacao"
		with a4:
			if st.button("🧹 Limpar Filtros"):
				for k in ["modalidade_filter","date_filter","empresa_filter","paciente_filter","quick"]:
					filters.pop(k, None)
				st.rerun()

		df = pd.DataFrame(appts, columns=[
			"ID","Empresa","Nome","Modalidade","Data","Hora","Laudo PDF","Avaliação PDF","Status","Observações"
		])

		if filters.get("modalidade_filter"):
			df = df[df["Modalidade"] == filters["modalidade_filter"]]
		if filters.get("date_filter"):
			try:
				d = filters["date_filter"].strftime(DATE_FORMAT)
				df = df[df["Data"] == d]
			except Exception:
				pass
		emp = (filters.get("empresa_filter") or "").strip()
		if emp:
			df = df[df["Empresa"].str.contains(emp, case=False, na=False)]
		pac = (filters.get("paciente_filter") or "").strip()
		if pac:
			df = df[df["Nome"].str.contains(pac, case=False, na=False)]

		# Filtro rápido aplicado
		quick = filters.get("quick")
		if quick == "sem_laudo":
			df = df[df["Laudo PDF"].isna() | (df["Laudo PDF"] == "")]
		elif quick == "sem_avaliacao":
			df = df[df["Avaliação PDF"].isna() | (df["Avaliação PDF"] == "")]

		# Colunas visuais: mostrar feedback textual "SIM" (arquivo presente) ou "NÃO" (ausente)
		# (Anteriormente era "OK"; ajustado conforme solicitação do usuário)
		df["Laudo"] = df["Laudo PDF"].apply(lambda x: "SIM" if bool(x) else "NÃO")
		df["Avaliação"] = df["Avaliação PDF"].apply(lambda x: "SIM" if bool(x) else "NÃO")

		st.markdown("### 📋 Lista de Atendimentos")
		df_show = df[["Empresa", "Nome", "Modalidade", "Data", "Hora", "Laudo", "Avaliação"]].copy()
		# Estilização: "SIM" em verde, "NÃO" em vermelho para facilitar leitura rápida
		try:
			def _style_flag(val: str) -> str:
				val_norm = str(val).strip().upper()
				if val_norm == "SIM":
					return (
						"background-color: rgba(60,170,95,0.22); "
						"border: 1px solid rgba(60,170,95,0.55); "
						"color: #0e4521; font-weight: 700; border-radius:6px; "
						"box-shadow: inset 0 0 0 1px rgba(255,255,255,0.15);"
					)
				if val_norm == "NÃO":
					return (
						"background-color: rgba(200,60,60,0.15); "
						"border: 1px solid rgba(200,60,60,0.45); "
						"color: #6d1a1a; font-weight: 600; border-radius:6px; "
						"box-shadow: inset 0 0 0 1px rgba(255,255,255,0.12);"
					)
				return ""
			styler = df_show.style.map(_style_flag, subset=["Laudo", "Avaliação"])
			st.dataframe(styler, use_container_width=True, height=400)
		except Exception:
			# Fallback sem estilo caso o Styler não seja suportado
			st.dataframe(df_show, use_container_width=True, height=400)
		csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
		st.download_button("⬇️ Exportar CSV", data=csv_bytes, file_name="atendimentos.csv", mime="text/csv")

		with st.expander("✏️ Editar Atendimento"):
			ids = df["ID"].astype(int).tolist()
			if not ids:
				st.info("Sem registros para editar.")
				return
			sel = st.selectbox("Selecione (ID):", ids)
			row = df[df["ID"] == sel].iloc[0]
			try:
				cur_date = datetime.strptime(row["Data"], DATE_FORMAT).date()
			except Exception:
				cur_date = date.today()
			try:
				h, m = (row["Hora"] or "09:00").split(":")
				cur_time = time(int(h), int(m))
			except Exception:
				cur_time = time(9, 0)

			with st.form("edit_form"):
				c1, c2 = st.columns(2)
				with c1:
					empresa_n = st.text_input("🏢 Empresa", value=str(row["Empresa"]))
					modalidade_n = st.selectbox(
						"🏥 Modalidade",
						[m.value for m in ModalidadeAtendimento],
						index=max(
							0,
							[m.value for m in ModalidadeAtendimento].index(str(row["Modalidade"]))
							if str(row["Modalidade"]) in [m.value for m in ModalidadeAtendimento]
							else 0,
						),
					)
					data_n = st.date_input("📅 Data", value=cur_date)
				with c2:
					nome_n = st.text_input("👤 Nome", value=str(row["Nome"]))
					hora_n = st.time_input("🕒 Hora", value=cur_time)
					status_n = st.selectbox(
						"📌 Status",
						["Agendado", "Concluído", "Cancelado"],
						index=["Agendado", "Concluído", "Cancelado"].index(
							str(row.get("Status", "Agendado")) if row.get("Status") else "Agendado"
						),
					)
				obs_n = st.text_area("📝 Observações", value=str(row.get("Observações", "")))

				st.markdown("#### 📎 Anexos do atendimento")
				col_a1, col_a2 = st.columns(2)
				with col_a1:
					if row.get("Laudo PDF"):
						st.caption(f"Atual: {os.path.basename(str(row['Laudo PDF']))}")

						try:
							with open(str(row["Laudo PDF"]), "rb") as f:
								st.download_button("⬇️ Baixar Laudo", f.read(), file_name=os.path.basename(str(row["Laudo PDF"])) , key=f"dl_laudo_{sel}")
						except Exception:
							pass
					up_laudo_edit = st.file_uploader("Substituir Laudo (PDF)", type=["pdf"], key=f"laudo_edit_{sel}", help="Limite de 50 MB por arquivo • PDF")
					st.caption("Limite de 50 MB por arquivo • PDF")
					if up_laudo_edit is not None:
						try:
							size_mb3 = len(up_laudo_edit.getvalue()) / (1024 * 1024)
							st.caption(f"Selecionado: {up_laudo_edit.name} — {size_mb3:.2f} MB")
						except Exception:
							st.caption(f"Selecionado: {up_laudo_edit.name}")
						st.markdown("<span class='uploader-badge'>✅ Arquivo selecionado</span>", unsafe_allow_html=True)
						c_el1, c_el2 = st.columns([6,1])
						with c_el2:
							if st.button("🗑️", key=f"clear_laudo_{sel}", help="Remover seleção"):
								st.session_state[f"laudo_edit_{sel}"] = None
								st.rerun()
				with col_a2:
					if row.get("Avaliação PDF"):
						st.caption(f"Atual: {os.path.basename(str(row['Avaliação PDF']))}")
						try:
							with open(str(row["Avaliação PDF"]), "rb") as f:
								st.download_button("⬇️ Baixar Avaliação", f.read(), file_name=os.path.basename(str(row["Avaliação PDF"])) , key=f"dl_aval_{sel}")
						except Exception:
							pass
					up_aval_edit = st.file_uploader("Substituir Avaliação (PDF)", type=["pdf"], key=f"aval_edit_{sel}", help="Limite de 50 MB por arquivo • PDF")
					st.caption("Limite de 50 MB por arquivo • PDF")
					if up_aval_edit is not None:
						try:
							size_mb4 = len(up_aval_edit.getvalue()) / (1024 * 1024)
							st.caption(f"Selecionado: {up_aval_edit.name} — {size_mb4:.2f} MB")
						except Exception:
							st.caption(f"Selecionado: {up_aval_edit.name}")
						st.markdown("<span class='uploader-badge'>✅ Arquivo selecionado</span>", unsafe_allow_html=True)
						c_ea1, c_ea2 = st.columns([6,1])
						with c_ea2:
							if st.button("🗑️", key=f"clear_aval_{sel}", help="Remover seleção"):
								st.session_state[f"aval_edit_{sel}"] = None
								st.rerun()

				submit_edit = st.form_submit_button("Salvar alterações", type="primary")
				if submit_edit:
					laudo_path_novo = row.get("Laudo PDF")
					aval_path_novo = row.get("Avaliação PDF")
					try:
						if up_laudo_edit is not None:
							ok, msg = security.validate_file_upload(up_laudo_edit.name, len(up_laudo_edit.getvalue()), max_size_mb=50)
							if not ok:
								st.error(f"Laudo: {msg}")
								st.stop()
							safe = security.generate_safe_filename(up_laudo_edit.name)
							base_dir = os.path.dirname(__file__)
							destp = os.path.join(base_dir, "uploads")
							os.makedirs(destp, exist_ok=True)
							laudo_path_novo = os.path.join(destp, safe)
							with open(laudo_path_novo, "wb") as f:
								f.write(up_laudo_edit.getbuffer())
						if up_aval_edit is not None:
							ok, msg = security.validate_file_upload(up_aval_edit.name, len(up_aval_edit.getvalue()), max_size_mb=50)
							if not ok:
								st.error(f"Avaliação: {msg}")
								st.stop()
							safe2 = security.generate_safe_filename(up_aval_edit.name)
							base_dir = os.path.dirname(__file__)
							destp2 = os.path.join(base_dir, "uploads")
							os.makedirs(destp2, exist_ok=True)
							aval_path_novo = os.path.join(destp2, safe2)
							with open(aval_path_novo, "wb") as f:
								f.write(up_aval_edit.getbuffer())
					except Exception as e:
						st.error(f"Falha ao salvar anexos: {e}")
						st.stop()

					ok = DatabaseManager.update_appointment(
						int(sel),
						empresa=security.sanitize_input(empresa_n or ""),
						nome=security.sanitize_input(nome_n or ""),
						modalidade=modalidade_n,
						data=data_n.strftime(DATE_FORMAT),
						hora=hora_n.strftime(TIME_FORMAT),
						status=status_n,
						observacoes=security.sanitize_input(obs_n or ""),
						laudo_pdf=laudo_path_novo,
						avaliacao_pdf=aval_path_novo,
					)
					if ok:
						security.log_access("UPDATE_APPOINTMENT", f"ID {sel} - {nome_n}")
						st.success("Atualizado!")
						try:
							if up_laudo_edit is not None:
								p = save_uploaded_pdf(up_laudo_edit)
								if p: laudo_path_novo = p
							if up_aval_edit is not None:
								p2 = save_uploaded_pdf(up_aval_edit)
								if p2: aval_path_novo = p2
						except Exception:
							pass
		tab1, tab2 = st.tabs(["Adicionar PDF", "Baixar PDFs"])
		with tab1:
			UploadPage._render_upload_form()
		with tab2:
			UploadPage._render_download_list()
		st.markdown("</div>", unsafe_allow_html=True)

	# (métodos de upload agora centralizados na classe UploadPage)


class SettingsPage:
	@staticmethod
	def render() -> None:
		render_page_header("⚙️ Configurações", "Administração do Sistema", inverse=True)
		# Determina backend novamente (escopo local)
		backend = "SQLite"
		try:
			if hasattr(db, 'USE_PG') and getattr(db, 'USE_PG'):
				backend = "Postgres"
		except Exception:
			backend = "SQLite"
		# KPIs da seção Configurações
		try:
			conn_ok = db.verificar_conexao()
			stats = DatabaseManager.get_statistics() or {}
			cards = [
				{"icon": "🔌", "title": "Banco de Dados", "value": ("Conectado" if conn_ok else "Offline"), "acc": PRIMARY_ACCENT},
				{"icon": "🗄️", "title": backend, "value": "Postgres" if backend=="Postgres" else "SQLite", "acc": PRIMARY_ACCENT},
				{"icon": "📦", "title": "Cache (itens)", "value": stats.get("total_atendimentos", 0), "acc": PRIMARY_ACCENT},
			]
			display_cards(cards)
		except Exception:
			pass
		st.markdown("<div class='reports-scope'>", unsafe_allow_html=True)
		col1, col2, col3, col4 = st.columns(4)
		with col1:
			if st.button("🔄 Limpar cache"):
				st.cache_data.clear(); st.cache_resource.clear(); st.success("Cache limpo.")
		with col2:
			if st.button("🗄️ Verificar Banco"):
				ok = db.verificar_conexao()
				st.success("Conexão OK.") if ok else st.error("Falha na conexão.")
		with col3:
			if st.button("🔍 Testar Backend"):
				info = getattr(db, 'get_backend_info', lambda: {"engine":"?"})()
				st.info(f"Engine: {info.get('engine')} | URL definida: {info.get('url_present')}")
		with col4:
			if st.button("🛠️ Reinicializar"):
				st.cache_resource.clear(); DatabaseManager.initialize_database(); st.success("Reinicializado.")

		st.markdown("---")
		# Diagnóstico detalhado do banco e segurança
		with st.expander("📋 Diagnóstico do Sistema", expanded=False):
			from json import dumps
			# DB
			try:
				from db import get_db_diagnostics
				db_diag = get_db_diagnostics()
			except Exception as e:
				db_diag = {"error":"falhou diagnóstico DB", "detail": str(e)}
			# Security health (mock simplificado baseado em security module)
			sec_health = {
				"security_loaded": bool(security),
				"logs_directory": os.path.isdir(os.path.join(os.path.dirname(__file__), 'logs')),
				"log_file_writable": True,
			}
			# Disco livre
			try:
				import shutil, datetime as _dt
				free_mb = int(shutil.disk_usage(os.path.dirname(__file__)).free/1024/1024)
				sec_health["free_mb"] = free_mb
				sec_health["timestamp"] = _dt.datetime.utcnow().isoformat()
			except Exception:
				pass
			payload = {**db_diag, **sec_health}
			st.code(dumps(payload, ensure_ascii=False, indent=2), language="json")
		st.markdown("### 🩺 Diagnóstico do Sistema")
		with st.expander("Executar / Ver resultado", expanded=False):
			if st.button("▶️ Rodar Diagnóstico", key="run_diag"):
				try:
					import sqlite3, json, math, time as _t
					inicio = _t.time()
					resultado = {}
					# Caminho do DB
					resultado["db_path"] = getattr(db, "DATABASE_PATH", "?")
					if os.path.exists(resultado["db_path"]):
						resultado["db_exists"] = True
						resultado["db_size_kb"] = os.path.getsize(resultado["db_path"]) // 1024
					else:
						resultado["db_exists"] = False
					# Listar tabelas
					resultado["tables"] = []
					try:
						with sqlite3.connect(resultado["db_path"]) as _c:
							_c.row_factory = sqlite3.Row
							cur = _c.cursor()
							cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")
							tabs = [r[0] for r in cur.fetchall()]
							for t in tabs:
								try:
									cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
									resultado["tables"].append({"table": t, "rows": cnt})
								except Exception:
									resultado["tables"].append({"table": t, "rows": "?"})
					except Exception as e_tab:
						resultado["tables_error"] = str(e_tab)
					# Security
					resultado["security_loaded"] = bool(hasattr(security, "log_access"))
					try:
						if hasattr(security, "check_system_health"):
							resultado["security_health"] = security.check_system_health()
					except Exception as e_sec:
						resultado["security_health_error"] = str(e_sec)
					# Métricas simples
					resultado["duration_ms"] = int((_t.time() - inicio) * 1000)
					st.success("Diagnóstico concluído.")
					st.json(resultado)
				except Exception as e:
					st.error(f"Falha no diagnóstico: {e}")
		st.markdown("</div>", unsafe_allow_html=True)


class ReportsPage:
	@staticmethod
	def render() -> None:
		render_page_header("📊 Relatórios", "Análises e Exportações", inverse=True)
		# Filtros adicionais
		col1, col2 = st.columns(2)
		with col1:
			periodo = st.selectbox("Período", ["Últimos 7 dias", "Últimos 30 dias", "Ano atual", "Tudo"], index=1)
		with col2:
			formato = st.selectbox("Exportar como", ["CSV", "Excel"], index=0)

		# Dados
		appts = DatabaseManager.get_all_appointments() or []
		if not appts:
			st.info("Sem dados para relatório.")
			return
		df = pd.DataFrame(
			appts,
			columns=[
				"ID", "Empresa", "Nome", "Modalidade", "Data", "Hora",
				"Laudo PDF", "Avaliação PDF", "Status", "Observações",
			],
		)

		# Converter Data e aplicar filtro por período
		import pandas as _pd
		_df = df.copy()
		try:
			_df["Data_dt"] = _pd.to_datetime(_df["Data"], format=DATE_FORMAT, errors="coerce")
		except Exception:
			_df["Data_dt"] = _pd.NaT
		from datetime import datetime as _dt, timedelta as _td
		now = _dt.now()
		start = None
		if periodo == "Últimos 7 dias":
			start = now - _td(days=7)
		elif periodo == "Últimos 30 dias":
			start = now - _td(days=30)
		elif periodo == "Ano atual":
			start = _dt(now.year, 1, 1)
		# "Tudo" não aplica filtro
		if start is not None:
			_df = _df[(_df["Data_dt"].notna()) & (_df["Data_dt"] >= start) & (_df["Data_dt"] <= now)]

		# KPI simples (com filtro)
		st.markdown("<div class='reports-scope'>", unsafe_allow_html=True)
		st.markdown("### 📈 Resumo")
		_total = len(_df)
		_emp = _df["Empresa"].nunique()
		_mod = _df["Modalidade"].nunique()
		# Usar os mesmos cards modernos do painel para manter o padrão
		cards = [
			{"icon": "👥", "title": "Total de Atendimentos", "value": _total, "acc": PRIMARY_ACCENT},
			{"icon": "🏢", "title": "Empresas", "value": _emp, "acc": PRIMARY_ACCENT},
			{"icon": "🧾", "title": "Modalidades", "value": _mod, "acc": PRIMARY_ACCENT},
		]
		display_cards(cards)

		# Gráfico Modalidades
		try:
			modal_counts = _df["Modalidade"].value_counts()
			fig = px.bar(x=modal_counts.index, y=modal_counts.values, title="Atendimentos por Modalidade")
			fig.update_traces(hovertemplate="Modalidade=%{x}<br>Qtd=%{y}<extra></extra>")
			fig.update_layout(xaxis_title="Modalidade", yaxis_title="Quantidade", height=460)
			st.plotly_chart(fig, use_container_width=True)
		except Exception:
			pass

		# Exportação
		st.markdown("### ⬇️ Exportar")
		st.markdown("</div>", unsafe_allow_html=True)
		if formato == "CSV":
			data = _df.drop(columns=[c for c in ["Data_dt"] if c in _df.columns], errors="ignore").to_csv(index=False).encode("utf-8-sig")
			st.download_button("Baixar CSV", data=data, file_name="relatorio_atendimentos.csv", mime="text/csv")
		else:
			try:
				import io
				buf = io.BytesIO()
				with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
					_df.drop(columns=[c for c in ["Data_dt"] if c in _df.columns], errors="ignore").to_excel(writer, index=False, sheet_name="Atendimentos")
				buf.seek(0)
				st.download_button("Baixar Excel", data=buf.getvalue(), file_name="relatorio_atendimentos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
			except Exception as e:
				st.error(f"Falha ao exportar Excel: {e}")


class UploadPage:
	"""Página de Upload de PDFs (utiliza funções estáticas internas)."""

	@staticmethod
	def render() -> None:
		render_page_header("📄 Carregar", "Gerencie arquivos PDF enviados", inverse=True)
		st.markdown("<div class='reports-scope'>", unsafe_allow_html=True)
		UploadPage._render_upload_form()
		st.markdown("---")
		UploadPage._render_download_list()
		st.markdown("</div>", unsafe_allow_html=True)

	@staticmethod
	def _uploads_dir() -> str:
		base_dir = os.path.dirname(__file__)
		d = os.path.join(base_dir, "uploads")
		os.makedirs(d, exist_ok=True)
		return d

	@staticmethod
	def _render_upload_form() -> None:
		up = st.file_uploader("📄 Selecione um PDF", type=["pdf"], help="Limite de 50 MB por arquivo • PDF", key="upload_pdf")
		if up is None:
			return
		size_mb = len(up.getvalue()) / (1024 * 1024)
		st.info(f"Arquivo: {up.name} — {size_mb:.2f} MB")
		nome_seguro = security.generate_safe_filename(up.name)
		destino = os.path.join(UploadPage._uploads_dir(), nome_seguro)
		st.markdown("<span class='uploader-badge'>✅ Arquivo selecionado</span>", unsafe_allow_html=True)
		c1, c2 = st.columns([6,1])
		with c2:
			if st.button("🗑️", key="clear_upload_pdf", help="Remover seleção"):
				st.session_state["upload_pdf"] = None
				st.rerun()
		if st.button("Salvar PDF", type="primary"):
			ok, msg = security.validate_file_upload(up.name, len(up.getvalue()), max_size_mb=MAX_UPLOAD_MB)
			if not ok:
				st.error(msg); return
			with open(destino, "wb") as f:
				f.write(up.getbuffer())
			st.success("PDF salvo.")
			st.download_button("Baixar agora", up.getvalue(), file_name=nome_seguro)

	@staticmethod
	def _render_download_list() -> None:
		pasta = UploadPage._uploads_dir()
		arqs = [f for f in os.listdir(pasta) if f.lower().endswith('.pdf')]
		if not arqs:
			st.info("Nenhum PDF encontrado."); return
		for i, nome in enumerate(sorted(arqs, reverse=True)):
			caminho = os.path.join(pasta, nome)
			cols = st.columns([4,1,1])
			with cols[0]:
				st.write(f"📄 {nome}"); st.caption(f"{os.path.getsize(caminho)//1024} KB")
			with cols[1]:
				with open(caminho, 'rb') as f:
					st.download_button('Baixar', f.read(), file_name=nome, key=f'dl_{i}')
			with cols[2]:
				if st.button('Excluir', key=f'rm_{i}'):
					try:
						os.remove(caminho); security.log_access('DELETE_PDF', nome); st.success('Arquivo excluído.'); st.rerun()
					except Exception as e:
						st.error(f'Falha ao excluir: {e}')


class NotesPage:
	"""Página de Bloco de Notas com filtros, lista, editor, histórico e exportação."""

	TAG_PALETTE = ["#4DA768", "#2ecc71", "#27ae60", "#7FD784", "#3A8A56", "#16a085"]

	@staticmethod
	def _build_df(notas: List[tuple], query: str) -> pd.DataFrame:
		cols = ["ID","Título","Conteúdo","Tags","Criada em","Atualizada em","Favorita"]
		df = pd.DataFrame(notas, columns=cols) if notas else pd.DataFrame(columns=cols)
		if query:
			mask = df["Título"].str.contains(query, case=False, na=False) | df["Tags"].str.contains(query, case=False, na=False)
			df = df[mask]
		return df

	@staticmethod
	def _filters_ui(df: pd.DataFrame) -> Dict[str, Any]:
		colf1, colf2, colf3, colf4 = st.columns([2,2,1,1])
		with colf1:
			all_tags = sorted({t.strip() for ts in df["Tags"].dropna().astype(str).tolist() for t in ts.split(',') if t.strip()})
			selected_tags = st.multiselect("Filtrar por tags", options=all_tags, default=[])
		with colf2:
			ordenar = st.selectbox("Ordenar por", ["Atualizada (desc)", "Título (A→Z)", "Data criação (desc)"])
		with colf3:
			somente_fav = st.checkbox("Só favoritas 📌", value=False)
		with colf4:
			sem_tag = st.checkbox("Sem tag", value=False)
		return {"tags": selected_tags, "ordenar": ordenar, "somente_fav": somente_fav, "sem_tag": sem_tag}

	@staticmethod
	def _apply_filters(df: pd.DataFrame, f: Dict[str, Any]) -> pd.DataFrame:
		if f.get("sem_tag"):
			df = df[df["Tags"].fillna("").astype(str).str.strip() == ""]
		elif f.get("tags"):
			selected_tags = f["tags"]
			def _has_tags(tags_str: str) -> bool:
				set_row = {t.strip().lower() for t in (tags_str or "").split(',') if t.strip()}
				set_sel = {t.strip().lower() for t in selected_tags if t.strip()}
				return set_sel.issubset(set_row)
			df = df[df["Tags"].apply(_has_tags)]
		if f.get("somente_fav"):
			df = df[df["Favorita"].fillna(0).astype(int) == 1]
		ordem = f.get("ordenar")
		if ordem == "Título (A→Z)":
			df = df.sort_values(by=["Título"], ascending=True)
		elif ordem == "Data criação (desc)":
			df = df.sort_values(by=["Criada em"], ascending=False)
		else:
			df = df.sort_values(by=["Favorita","Atualizada em"], ascending=[False, False])
		return df

	@staticmethod
	def _badge_tags(tags: str) -> str:
		if not tags or not str(tags).strip():
			return ""
		badges = []
		for i, t in enumerate([x.strip() for x in str(tags).split(',') if x.strip()]):
			c = NotesPage.TAG_PALETTE[i % len(NotesPage.TAG_PALETTE)]
			badges.append(f"<span style='display:inline-block;margin:2px;padding:2px 8px;border-radius:999px;background:{c}20;color:{c};border:1px solid {c}55;font-weight:700;font-size:12px;'>{t}</span>")
		return " ".join(badges)

	@staticmethod
	def _render_stats() -> None:
		"""Exibe gráficos (tags e favoritas) com exportação de imagens."""
		try:
			notas_stats = db.listar_notas() or []
			if not notas_stats:
				return
			import pandas as _pds, plotly.express as _px, collections
			df_all = _pds.DataFrame(notas_stats, columns=["ID","Título","Conteúdo","Tags","Criada em","Atualizada em","Favorita"])
			# Tags
			all_tags: list[str] = []
			for ts in df_all["Tags"].dropna().astype(str).tolist():
				for t in [x.strip() for x in ts.split(',') if x.strip()]:
					all_tags.append(t)
			cnt = collections.Counter(all_tags)
			if cnt:
				st.markdown("### 🔖 Tags mais usadas")
				tags_df = _pds.DataFrame(cnt.most_common(), columns=["Tag","Qtd"])
				fig_tags = _px.bar(tags_df, x="Tag", y="Qtd", title="Frequência de Tags")
				fig_tags.update_traces(hovertemplate="Tag=%{x}<br>Qtd=%{y}<extra></extra>")
				fig_tags.update_layout(height=340, xaxis_tickangle=-25, margin=dict(t=60,l=40,r=20,b=70))
				st.plotly_chart(fig_tags, use_container_width=True)
				col_t1, col_t2 = st.columns(2)
				with col_t1:
					if st.button("💾 PNG Tags", key="exp_png_tags"):
						try:
							st.download_button("Baixar tags.png", data=fig_tags.to_image(format="png", scale=2), file_name="tags_frequencia.png", mime="image/png", key="dl_png_tags")
						except Exception as e_img:
							st.error(f"Falha PNG: {e_img}")
				with col_t2:
					if st.button("🖼️ SVG Tags", key="exp_svg_tags"):
						try:
							st.download_button("Baixar tags.svg", data=fig_tags.to_image(format="svg"), file_name="tags_frequencia.svg", mime="image/svg+xml", key="dl_svg_tags")
						except Exception as e_svg:
							st.error(f"Falha SVG: {e_svg}")
			# Favoritas
			fav_counts = df_all['Favorita'].fillna(0).astype(int).value_counts()
			if not fav_counts.empty:
				st.markdown("### ⭐ Distribuição de Favoritas")
				fav_df = _pds.DataFrame({"Status":["Favoritas","Não Favoritas"], "Qtd":[int(fav_counts.get(1,0)), int(fav_counts.get(0,0))]})
				fig_fav = _px.pie(fav_df, values="Qtd", names="Status", title="Notas Favoritas vs Não")
				fig_fav.update_traces(textinfo="percent+label", pull=[0.05,0])
				fig_fav.update_layout(height=340, legend_orientation='h', legend_y=-0.15)
				st.plotly_chart(fig_fav, use_container_width=True)
				col_f1, col_f2 = st.columns(2)
				with col_f1:
					if st.button("💾 PNG Favoritas", key="exp_png_fav"):
						try:
							st.download_button("Baixar favoritas.png", data=fig_fav.to_image(format="png", scale=2), file_name="notas_favoritas.png", mime="image/png", key="dl_png_fav")
						except Exception as e_fp:
							st.error(f"Falha PNG: {e_fp}")
				with col_f2:
					if st.button("🖼️ SVG Favoritas", key="exp_svg_fav"):
						try:
							st.download_button("Baixar favoritas.svg", data=fig_fav.to_image(format="svg"), file_name="notas_favoritas.svg", mime="image/svg+xml", key="dl_svg_fav")
						except Exception as e_fs:
							st.error(f"Falha SVG: {e_fs}")
		except Exception as e:
			st.info(f"(Estatísticas de notas indisponíveis: {e})")

	@staticmethod
	def _render_list(df: pd.DataFrame) -> None:
		with st.expander("📚 Notas", expanded=True):
			if df.empty:
				st.caption("Nenhuma nota encontrada.")
				return
			st.caption(f"{len(df)} nota(s)")
			for _, r in df.iterrows():
				cols = st.columns([0.5, 4.5, 2.2, 1.2, 1.2])
				pin_on = int(r.get("Favorita", 0)) == 1
				with cols[0]:
					st.write("📌" if pin_on else "")
				with cols[1]:
					st.markdown(f"**{r['Título']}**")
					html = NotesPage._badge_tags(r.get("Tags", ""))
					if html:
						st.markdown(html, unsafe_allow_html=True)
				with cols[2]:
					st.caption(f"Atualizada em: {r['Atualizada em']}")
				with cols[3]:
					if st.button("Desafixar" if pin_on else "Fixar", key=f"pin_{int(r['ID'])}"):
						try:
							db.atualizar_nota(int(r['ID']), favorita=0 if pin_on else 1)
							security.log_access("PIN_NOTE", f"ID {int(r['ID'])} -> {'OFF' if pin_on else 'ON'}")
							# Evitar rerun imediato para reduzir conflitos DOM
							st.session_state['_pin_changed'] = True
						except Exception as e:
							st.error(f"Falha ao atualizar pin: {e}")
				with cols[4]:
					if st.button("Editar", key=f"edit_{int(r['ID'])}"):
						st.session_state['notes_selected_id'] = int(r['ID'])
						st.session_state['notes_open_editor'] = True
						# Evitar rerun imediato
						st.session_state['_edit_requested'] = True
			# Exportações
			csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
			st.download_button("⬇️ Exportar CSV", data=csv_bytes, file_name="notas.csv", mime="text/csv")

	@staticmethod
	def _html_to_md(html: str) -> str:
		import re
		md = re.sub(r"<\/?(strong|b)>", "**", html or "")
		md = re.sub(r"<\/?(em|i)>", "*", md)
		md = re.sub(r"<br\s*\/?>", "\n", md)
		md = re.sub(r"<ul>|</ul>", "", md)
		md = re.sub(r"<li>", "- ", md)
		md = re.sub(r"</li>", "\n", md)
		md = re.sub(r"<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"[\2](\1)", md)
		md = re.sub(r"<[^>]+>", "", md)
		return md

	@staticmethod
	def _content_key(nota_id: Optional[int]) -> str:
		return f"note_content_{nota_id if nota_id is not None else 'new'}"

	@staticmethod
	def _toolbar_md(content_key: str) -> None:
		st.caption("Dicas Markdown: **negrito**, *itálico*, - lista, [texto](url), # Título")
		b1, b2, b3, b4, b5 = st.columns(5)
		def _append(txt: str):
			st.session_state[content_key] = (st.session_state.get(content_key, "") or "") + txt
		with b1:
			if st.button("B", key=f"md_b_{content_key}"):
				_append("**texto**")
		with b2:
			if st.button("I", key=f"md_i_{content_key}"):
				_append("*texto*")
		with b3:
			if st.button("#", key=f"md_h_{content_key}"):
				_append("\n# Título\n")
		with b4:
			if st.button("Lista", key=f"md_l_{content_key}"):
				_append("\n- item\n- item\n")
		with b5:
			if st.button("Link", key=f"md_link_{content_key}"):
				_append("[texto](https://)")

	@staticmethod
	def _history_ui(df: pd.DataFrame, selected_id: Optional[int] = None) -> None:
		if df.empty:
			return
		with st.expander("🕒 Histórico de versões"):
			ids_h = [int(selected_id)] if selected_id is not None else df["ID"].astype(int).tolist()
			if not ids_h:
				return
			sel_h = st.selectbox("Nota", ids_h, key="note_hist_sel")
			reg = db.listar_historico_nota(int(sel_h)) or []
			if not reg:
				st.caption("Sem histórico ainda.")
				return
			cols = ["HistID","NotaID","Título","Conteúdo","Tags","Favorita","Data"]
			_hist_df = pd.DataFrame(reg, columns=cols)
			st.dataframe(_hist_df[["HistID","Título","Tags","Favorita","Data"]], use_container_width=True, height=220)
			sel_hist = st.selectbox("Restaurar versão (HistID)", _hist_df["HistID"].astype(int).tolist())
			if st.button("↩️ Restaurar versão"):
				rowh = _hist_df[_hist_df["HistID"] == sel_hist].iloc[0]
				db.inserir_historico_nota(int(sel_h), rowh["Título"], rowh["Conteúdo"], rowh["Tags"], int(rowh["Favorita"]))
				db.atualizar_nota(int(sel_h), titulo=rowh["Título"], conteudo=rowh["Conteúdo"], tags=rowh["Tags"], favorita=int(rowh["Favorita"]))
				st.success("Versão restaurada.")
				st.rerun()

	@staticmethod
	def render() -> None:
		render_page_header("🗒️ Bloco de Notas", "Anotações rápidas em Markdown")
		# Layout em duas colunas: esquerda (filtros/lista), direita (editor/histórico)
		col_left, col_right = st.columns([1.2, 2])

		with col_left:
			# Busca e novo
			q = st.text_input("Buscar por título ou tag", value="")
			new_open = st.button("➕ Nova nota", type="primary")
			if new_open:
				st.session_state['notes_selected_id'] = None
				st.session_state['notes_open_editor'] = True
				st.session_state['_new_note_requested'] = True
			# Dados e filtros
			notas = db.listar_notas() or []
			df = NotesPage._build_df(notas, q)
			filters = NotesPage._filters_ui(df)
			df = NotesPage._apply_filters(df, filters)
			NotesPage._render_list(df)

		with col_right:
			open_editor = st.session_state.get('notes_open_editor', False)
			selected_id = st.session_state.get('notes_selected_id', None)
			# Estatísticas
			NotesPage._render_stats()

			if open_editor:
				# Carregar defaults
				if selected_id is not None and not df.empty and (df["ID"].astype(int) == int(selected_id)).any():
					row = df[df["ID"].astype(int) == int(selected_id)].iloc[0]
					nota_id = int(row["ID"])
					titulo_def = str(row["Título"]) or ""; tags_def = str(row["Tags"]) or ""; conteudo_def = str(row["Conteúdo"]) or ""; fav_def = bool(int(row.get("Favorita", 0)))
					st.subheader(f"✏️ Editando: {titulo_def}")
				else:
					nota_id = None; titulo_def = ""; tags_def = ""; conteudo_def = ""; fav_def = False
					st.subheader("🆕 Nova nota")

				# Botão para fechar editor
				if st.button("Fechar editor"):
					st.session_state['notes_open_editor'] = False
					st.session_state['notes_selected_id'] = None
					st.session_state['_editor_closed'] = True

				content_key = NotesPage._content_key(nota_id)
				if content_key not in st.session_state:
					st.session_state[content_key] = conteudo_def or ""
				if st_quill is None:
					NotesPage._toolbar_md(content_key)

				with st.form("nota_form"):
					c1, c2 = st.columns([2,1])
					with c1:
						titulo = st.text_input("Título", value=titulo_def, placeholder="Ex.: Reunião com empresa X")
					with c2:
						tags = st.text_input("Tags (separe por vírgula)", value=tags_def, placeholder="ex.: empresaX,financeiro")
					conteudo = conteudo_def
					if st_quill is not None:
						st.caption("Editor rich-text (negrito, itálico, listas, links). O conteúdo é salvo como Markdown.")
						q = st_quill(html=True, value=st.session_state[content_key], key=f"quill_{nota_id if nota_id is not None else 'new'}")
						try:
							conteudo = NotesPage._html_to_md(q or "")
						except Exception:
							conteudo = q or st.session_state[content_key] or ""
						st.session_state[content_key] = conteudo
					else:
						conteudo = st.text_area("Conteúdo (Markdown)", value=st.session_state[content_key], height=220, placeholder="Escreva suas anotações aqui...")
						st.session_state[content_key] = conteudo
					fav = st.checkbox("Marcar como favorita (📌)", value=fav_def)
					if tags:
						st.markdown(NotesPage._badge_tags(tags), unsafe_allow_html=True)
					col1, col2, col3 = st.columns(3)
					with col1:
						save = st.form_submit_button("💾 Salvar", type="primary")
					with col2:
						delete = st.form_submit_button("🗑️ Excluir")
					with col3:
						preview = st.form_submit_button("👁️ Pré-visualizar")

				if preview:
					st.markdown("---"); st.markdown("### Pré-visualização"); st.markdown(conteudo or "(vazio)")

				if save:
					if not titulo.strip():
						st.error("Informe um título.")
					else:
						tit = security.sanitize_input(titulo); tgs = security.sanitize_input(tags)
						if nota_id is None:
							ok = db.inserir_nota(tit, conteudo, tgs, favorita=fav)
							if ok:
								security.log_access("ADD_NOTE", tit); st.success("Nota criada.")
								st.session_state['notes_selected_id'] = None
								st.session_state['notes_open_editor'] = False
								st.rerun()
							else:
								st.error("Falha ao criar a nota.")
						else:
							try:
								db.inserir_historico_nota(int(nota_id), titulo_def, conteudo_def, tags_def, 1 if fav_def else 0)
							except Exception:
								pass
							ok = db.atualizar_nota(int(nota_id), titulo=tit, conteudo=conteudo, tags=tgs, favorita=1 if fav else 0)
							if ok:
								security.log_access("UPDATE_NOTE", f"ID {nota_id}"); st.success("Nota atualizada."); st.rerun()
							else:
								st.error("Falha ao atualizar a nota.")

				if (nota_id is not None) and not save and not delete and not preview:
					if (titulo != titulo_def) or (tags != tags_def) or (conteudo != conteudo_def) or (fav != fav_def):
						try:
							db.inserir_historico_nota(int(nota_id), titulo_def, conteudo_def, tags_def, 1 if fav_def else 0)
							db.atualizar_nota(int(nota_id), titulo=security.sanitize_input(titulo), conteudo=conteudo, tags=security.sanitize_input(tags), favorita=1 if fav else 0)
							st.toast("Alterações salvas automaticamente."); st.experimental_rerun()
						except Exception:
							pass

				if delete and (nota_id is not None):
					ok = db.excluir_nota(int(nota_id))
					if ok:
						security.log_access("DELETE_NOTE", f"ID {nota_id}"); st.success("Nota excluída.")
						st.session_state['notes_selected_id'] = None
						st.session_state['notes_open_editor'] = False
						st.rerun()
					else:
						st.error("Falha ao excluir a nota.")

				# Histórico e exportação da nota selecionada
				NotesPage._history_ui(df, selected_id=nota_id if 'nota_id' in locals() else None)
				st.markdown("---"); st.markdown("### ⬇️ Exportar Nota (Markdown)")
				if 'nota_id' in locals() and nota_id is not None:
					md = f"# {titulo_def}\n\n" + str(st.session_state.get(content_key, conteudo_def) or "")
					st.download_button("Baixar .md", data=md.encode("utf-8"), file_name=f"nota_{nota_id}.md", mime="text/markdown")
				else:
					st.caption("Selecione uma nota ou crie uma nova para exportar.")


class ClinicalManagementApp:
	def run(self) -> None:
		configure_page()
		if not DatabaseManager.initialize_database():
			st.stop()
		
		# Verificar mudanças pendentes e aplicar refresh controlado
		needs_refresh = any([
			st.session_state.get('_pin_changed', False),
			st.session_state.get('_edit_requested', False),
			st.session_state.get('_new_note_requested', False),
			st.session_state.get('_editor_closed', False)
		])
		
		if needs_refresh:
			# Limpar flags
			for flag in ['_pin_changed', '_edit_requested', '_new_note_requested', '_editor_closed']:
				st.session_state.pop(flag, None)
			st.rerun()
		
		filters = UIComponents.render_sidebar()
		# Aplicar CSS após saber se dark mode está ativo
		is_dark = filters.get("dark_mode", False)
		apply_custom_css(dark_mode=is_dark, advanced=ADVANCED_UI)
		apply_plotly_theme(dark_mode=is_dark)
		page = filters["page"]
		UIComponents.render_header(page)
		if page == "🏠 Painel":
			DashboardPage.render()
		elif page == "📝 Atendimentos":
			AppointmentsPage.render(filters)
		elif page == "📊 Relatórios":
			ReportsPage.render()
		elif page == "📄 Carregar":
			UploadPage.render()
		# Bloco de Notas removido conforme solicitação
		elif page == "⚙️ Configurações":
			SettingsPage.render()


if __name__ == "__main__":
	try:
		ClinicalManagementApp().run()
	except Exception as e:
		# Log simples em arquivo para investigar falhas no deploy (ex.: Streamlit Cloud)
		try:
			import traceback, os
			log_dir = os.path.join(os.path.dirname(__file__), 'logs')
			os.makedirs(log_dir, exist_ok=True)
			with open(os.path.join(log_dir, 'boot_error.log'), 'a', encoding='utf-8') as lf:
				lf.write(f"\n[{datetime.now().isoformat()}] ERRO FATAL APP\n")
				lf.write(''.join(traceback.format_exception(e)))
		except Exception:
			pass
		st.error("Falha inesperada ao iniciar o aplicativo. Verifique logs/boot_error.log")
