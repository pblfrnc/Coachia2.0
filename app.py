import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from datetime import datetime
import re
import random
import io
import urllib.parse
import tempfile
import asyncio
import edge_tts
import requests
import threading

# --- CONFIGURAÇÃO DA CHAVE DE API (SEGURA) ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
    CONEXAO_OK = True
except:
    API_KEY = ""
    CONEXAO_OK = False

# --- Configuração da Página ---
st.set_page_config(
    page_title="Coach Suprabio",
    page_icon="🏆",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS Responsivo e Estilo do Chat ---
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        height: 3.5em;
        font-weight: bold;
        border-radius: 12px;
        font-size: 15px;
    }
    .cliente-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #f0f2f6;
        border-left: 5px solid #ff4b4b;
        margin-bottom: 5px;
    }
    .vendedor-box {
        padding: 15px;
        border-radius: 10px;
        background-color: #e8f4f8;
        border-right: 5px solid #0088cc;
        margin-bottom: 10px;
        text-align: right;
    }
    .chat-texto {
        font-size: 17px;
        color: #31333F;
    }
    .chat-label {
        font-size: 12px;
        font-weight: bold;
        color: #777;
        margin-bottom: 5px;
    }
    .titulo-central {
        text-align: center;
        font-size: 2.2em;
        font-weight: 800;
        margin-bottom: 5px;
    }
    .subtitulo-central {
        text-align: center;
        color: #555;
        margin-bottom: 20px;
    }
    [data-testid="stImage"] img {
        border-radius: 15px;
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        color: #0088cc;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- ARQUIVOS E RAG ---
ARQUIVO_HISTORICO = "historico_treinamento.xlsx"
ARQUIVO_EQUIPE = "equipe.csv"

BASE_RAG_SUPRABIO = """
DOCUMENTO DE PRODUTOS SUPRABIO E OBJEÇÕES COMUNS:
- Magnésio Dimalato: Excelente para energia, dores crônicas, fibromialgia e fadiga. Objeção comum: "Já tomo magnésio de farmácia barato". Resposta esperada: "O Dimalato tem absorção superior e não solta o intestino".
- Cloreto de Magnésio: Foco em articulações, bico de papagaio, lubrificação de juntas. Objeção comum: "Tem gosto ruim?". Resposta esperada: "Em cápsulas você não sente o sabor".
- Melatonina e Clamvit Zen: Foco no sono e ansiedade. Melatonina induz o sono, Clamvit relaxa sem dopar. Objeção comum: "Vicia? Deixa de ressaca?". Resposta: "Totalmente natural, sem efeito ressaca".
- Coenzima Q10: Saúde do coração, energia mitocondrial e para quem toma Estatinas. Objeção: "É muito caro". Resposta: "O custo-benefício para tirar a dor muscular da estatina é enorme".
- Colágeno e Cálcio MDK: Foco estrutural e beleza. MDK direciona o cálcio para o osso (Vitamina K2). Objeção: "Cálcio dá pedra nos rins?". Resposta: "O MDK evita isso justamente por causa da vitamina K2".
"""

# --- BANCO DE DADOS DE CASOS REAIS (BLINDADO COM GÊNERO E IDADE) ---
CASOS_REAIS = [
    {"queixa": "Moça, eu ando muito esquecido, a cabeça parece que não funciona direito e tô sem energia mental.", "produto_alvo": "Magnésio Dimalato ou Complexo B", "prompt_img": "portrait of a stressed middle-aged brazilian man rubbing his temples looking confused", "genero": "M", "idade": "adulto"},
    {"queixa": "Minha memória tá terrível, esqueço onde coloquei a chave, o que ia falar... Queria algo pro cérebro e que fizesse bem pro coração.", "produto_alvo": "Ômega 3", "prompt_img": "portrait of an elderly brazilian woman looking forgetful and concerned", "genero": "F", "idade": "idoso"},
    {"queixa": "Vou prestar concurso no fim do ano, mas sento pra estudar e não consigo focar, parece que dá um branco. Falaram que gordura de peixe é bom.", "produto_alvo": "Ômega 3", "prompt_img": "portrait of a young brazilian male student looking tired with books", "genero": "M", "idade": "jovem"},
    {"queixa": "Sinto muitas cãibras na panturrilha de madrugada, acordo gemendo de dor. Tem alguma vitamina pra isso?", "produto_alvo": "Magnésio Dimalato ou Cloreto de Magnésio", "prompt_img": "portrait of an elderly brazilian man grimacing in pain holding his leg", "genero": "M", "idade": "idoso"},
    {"queixa": "Acordo de manhã e parece que passou um caminhão em cima de mim. O corpo todo dolorido, pesado, uma canseira muscular crônica.", "produto_alvo": "Magnésio Dimalato", "prompt_img": "portrait of a middle-aged brazilian woman looking exhausted and sore", "genero": "F", "idade": "adulto"},
    {"queixa": "Tenho sentido muita dor nas articulações, meu joelho estala quando subo escada. Tem algo pra 'lubrificar'?", "produto_alvo": "Cloreto de Magnésio ou Colágeno", "prompt_img": "portrait of an older brazilian woman pointing to her knee with a pained expression", "genero": "F", "idade": "idoso"},
    {"queixa": "Tenho uns bicos de papagaio na coluna e acordo com as juntas todas travadas, duro igual um robô.", "produto_alvo": "Cloreto de Magnésio", "prompt_img": "portrait of an older brazilian man moving stiffly holding his back", "genero": "M", "idade": "idoso"},
    {"queixa": "Tenho um esporão no calcanhar que me mata de dor quando piso no chão de manhã. Me falaram de um suplemento que desfaz isso.", "produto_alvo": "Cloreto de Magnésio", "prompt_img": "portrait of a middle-aged brazilian woman wincing while standing", "genero": "F", "idade": "adulto"},
    {"queixa": "Fiz um exame e deu osteopenia. O médico mandou tomar cálcio, mas disseram que tem um que vai direto pro osso.", "produto_alvo": "Cálcio MDK", "prompt_img": "portrait of a concerned post-menopausal brazilian woman holding an exam result", "genero": "F", "idade": "idoso"},
    {"queixa": "As mulheres da minha família têm histórico de osteoporose. Eu já passei dos 40 e queria começar a prevenir desde já.", "produto_alvo": "Cálcio MDK", "prompt_img": "portrait of a brazilian woman in her 40s looking proactive and health-conscious", "genero": "F", "idade": "adulto"},
    {"queixa": "Tomei um tombo bobo e trinquei o osso do braço. Queria um suplemento pra ajudar a colar esse osso mais rápido e fortificar.", "produto_alvo": "Cálcio MDK", "prompt_img": "portrait of a young adult brazilian person with an arm sling looking impatient", "genero": "M", "idade": "jovem"},
    {"queixa": "Eu deito na cama e fico rolando. O corpo cansa, mas a mente não desliga. Queria algo natural pra dormir.", "produto_alvo": "Melatonina ou Clamvit Zen", "prompt_img": "portrait of a brazilian woman with dark circles under eyes looking sleepless", "genero": "F", "idade": "adulto"},
    {"queixa": "Eu viajo muito a trabalho e meu fuso horário vira uma bagunça, perco totalmente a hora de dormir.", "produto_alvo": "Melatonina", "prompt_img": "portrait of a brazilian businessman in a suit looking jet-lagged with luggage", "genero": "M", "idade": "adulto"},
    {"queixa": "Eu até pego no sono rápido, mas acordo umas 3 da manhã e fico com o olho arregalado até clarear o dia. Tô um zumbi.", "produto_alvo": "Melatonina", "prompt_img": "portrait of a tired brazilian man with wide eyes looking desperate", "genero": "M", "idade": "adulto"},
    {"queixa": "Trabalho por turno, uma semana de dia, outra de madrugada. Meu relógio biológico pifou, não durmo direito em horário nenhum.", "produto_alvo": "Melatonina", "prompt_img": "portrait of a shift worker brazilian woman in uniform looking exhausted", "genero": "F", "idade": "adulto"},
    {"queixa": "Tô muito estressado, pavio curto, qualquer coisa eu explodo. Queria algo pra acalmar sem dar sono.", "produto_alvo": "Clamvit Zen", "prompt_img": "portrait of a tense middle-aged brazilian man looking irritable and stressed", "genero": "M", "idade": "adulto"},
    {"queixa": "Estou numa ansiedade terrível por conta de problemas na família. Meu coração até acelera, mas tenho pavor de tomar tarja preta.", "produto_alvo": "Clamvit Zen", "prompt_img": "portrait of an anxious brazilian woman clutching her chest looking worried", "genero": "F", "idade": "adulto"},
    {"queixa": "Tenho sentido um aperto no peito e um nó na garganta de tanta ansiedade com as provas da faculdade, mas não posso tomar remédio que dopa.", "produto_alvo": "Clamvit Zen", "prompt_img": "portrait of a young university brazilian student looking overwhelmed and anxious", "genero": "M", "idade": "jovem"},
    {"queixa": "Tô sentindo uma fraqueza no coração, me sinto muito cansado depois que fiz 40 anos. O médico falou de uma vitamina pro coração.", "produto_alvo": "Coenzima Q10", "prompt_img": "portrait of a man over 40 brazilian looking out of breath holding chest", "genero": "M", "idade": "adulto"},
    {"queixa": "Comecei a tomar estatina pra colesterol e agora sinto muita dor muscular, parece que fui atropelado. O médico falou de um suplemento.", "produto_alvo": "Coenzima Q10", "prompt_img": "portrait of an older brazilian man rubbing his arm muscle in pain", "genero": "M", "idade": "idoso"},
    {"queixa": "Tenho muita enxaqueca e o médico disse que tem um suplemento que dá energia para as células e ajuda a diminuir as crises.", "produto_alvo": "Coenzima Q10", "prompt_img": "portrait of a brazilian woman holding her head in pain with migraine", "genero": "F", "idade": "adulto"},
    {"queixa": "Tive uma infecção forte há uns meses e parece que minha bateria nunca mais voltou aos 100%. Qualquer esforço já me deixa ofegante.", "produto_alvo": "Coenzima Q10", "prompt_img": "portrait of a person recovering from illness brazilian looking weak and tired", "genero": "F", "idade": "adulto"},
    {"queixa": "Sinto um formigamento constante nas mãos e nos pés, além de um cansaço que não passa com nada.", "produto_alvo": "Complexo B", "prompt_img": "portrait of a brazilian woman looking at her tingling hands with concern", "genero": "F", "idade": "adulto"},
    {"queixa": "Sou diabético e ultimamente tenho sentido umas pontadas e uma queimação esquisita na sola dos pés.", "produto_alvo": "Complexo B", "prompt_img": "portrait of an older diabetic brazilian man looking worried about his feet", "genero": "M", "idade": "idoso"},
    {"queixa": "Tô bebendo muita bebida alcoólica nos finais de semana e sinto que meu fígado e meus nervos tão pedindo arrego.", "produto_alvo": "Complexo B", "prompt_img": "portrait of a middle-aged brazilian man looking hungover and regretful", "genero": "M", "idade": "adulto"},
    {"queixa": "Minha boca tá cheia de afta e eu pego resfriado toda semana. Minha imunidade deve estar no chão.", "produto_alvo": "Vitamina C ou Suprabio A-Z", "prompt_img": "portrait of a young brazilian person showing a mouth sore looking sickly", "genero": "F", "idade": "jovem"},
    {"queixa": "Meu nariz vive escorrendo. Basta o tempo mudar um pouquinho ou bater um vento gelado que eu já fico resfriada.", "produto_alvo": "Vitamina C", "prompt_img": "portrait of a brazilian woman with a runny nose using a tissue", "genero": "F", "idade": "adulto"},
    {"queixa": "Sinto que minha garganta arranha por qualquer friagem. E também demora muito pra cicatrizar qualquer machucadinho.", "produto_alvo": "Vitamina C", "prompt_img": "portrait of a person checking a slow-healing small cut on hand", "genero": "M", "idade": "jovem"},
    {"queixa": "Tô me sentindo fraco, sem disposição pra trabalhar. Sou homem, tenho 35 anos, queria um tônico geral.", "produto_alvo": "Suprabio Homem", "prompt_img": "portrait of a 35 year old brazilian man in work clothes looking unmotivated and tired", "genero": "M", "idade": "adulto"},
    {"queixa": "Trabalho o dia inteiro sentado no computador, chego em casa exausto, sem pique nem pra brincar com meus filhos.", "produto_alvo": "Suprabio Homem", "prompt_img": "portrait of a tired brazilian father in office shirt sitting slumped", "genero": "M", "idade": "adulto"},
    {"queixa": "A rotina tá tão puxada que chego à noite em casa sem vontade de nada, até minha libido caiu por falta de ânimo físico.", "produto_alvo": "Suprabio Homem", "prompt_img": "portrait of a stressed brazilian man looking downcast and lacking energy", "genero": "M", "idade": "adulto"},
    {"queixa": "Menina, tô na menopausa, sentindo uns calores e muito desânimo. Tem alguma vitamina completa pra mulher?", "produto_alvo": "Suprabio Mulher", "prompt_img": "portrait of a middle-aged brazilian woman fanning herself looking uncomfortable with hot flash", "genero": "F", "idade": "adulto"},
    {"queixa": "Meu fluxo menstrual é muito intenso e depois eu fico uns dias me arrastando, pálida e sem força nenhuma.", "produto_alvo": "Suprabio Mulher ou Complexo B", "prompt_img": "portrait of a young brazilian woman looking pale and weak wrapping a blanket", "genero": "F", "idade": "jovem"},
    {"queixa": "Trabalho, cuido da casa, dos filhos... tô me sentindo esgotada fisicamente e com a pele meio sem vida.", "produto_alvo": "Suprabio Mulher", "prompt_img": "portrait of a busy brazilian mother looking exhausted and overwhelmed", "genero": "F", "idade": "adulto"},
    {"queixa": "Já passei dos 50 anos e sinto que meus ossos estão fracos e me falta energia pro dia a dia.", "produto_alvo": "Suprabio 50+", "prompt_img": "portrait of a brazilian senior citizen over 50 looking frail but active", "genero": "F", "idade": "idoso"},
    {"queixa": "Minha mãe tem 68 anos e está comendo muito mal. Quase não come carne e tá ficando muito fraquinha.", "produto_alvo": "Suprabio 50+", "prompt_img": "portrait of a concerned adult daughter talking about her elderly mother", "genero": "F", "idade": "adulto"},
    {"queixa": "Meu pai tá com 75 anos, almoça que é um passarinho. Tô com medo dele ficar desnutrido ou perder músculo.", "produto_alvo": "Suprabio 50+", "prompt_img": "portrait of a concerned adult son talking about his elderly father", "genero": "M", "idade": "adulto"},
    {"queixa": "Olha o estado da minha unha! Tá quebrando igual papel. E meu cabelo cai muito no banho.", "produto_alvo": "Suprabio Cabelos e Unhas", "prompt_img": "portrait of a brazilian woman showing brittle fingernails to camera", "genero": "F", "idade": "adulto"},
    {"queixa": "Tirei aquele alongamento de gel e minha unha natural tá um papel, quebra só de encostar. Preciso fortalecer urgente.", "produto_alvo": "Suprabio Cabelos e Unhas", "prompt_img": "portrait of a brazilian woman looking frustrated at her damaged nails", "genero": "F", "idade": "adulto"},
    {"queixa": "Tive dengue faz uns meses e agora meu cabelo tá caindo aos tufos, tô ficando desesperada.", "produto_alvo": "Suprabio Cabelos e Unhas", "prompt_img": "portrait of a brazilian woman holding a clump of fallen hair looking distressed", "genero": "F", "idade": "adulto"},
    {"queixa": "Estou sentindo minha pele do rosto e dos braços muito flácida, perdendo a firmeza da juventude.", "produto_alvo": "Colágeno", "prompt_img": "portrait of a middle-aged brazilian woman touching her cheek skin critically", "genero": "F", "idade": "adulto"},
    {"queixa": "Emagreci bastante nos últimos meses, mas agora tô sentindo a pele do rosto meio caída, sabe? Queria algo de dentro pra fora.", "produto_alvo": "Colágeno", "prompt_img": "portrait of a brazilian person who lost weight pinching saggy skin on face", "genero": "F", "idade": "adulto"},
    {"queixa": "Meu intestino é um relógio... parado! Fico 3 dias sem ir ao banheiro e me sinto inchada.", "produto_alvo": "Fibras ou Lactulose", "prompt_img": "portrait of a brazilian woman holding her bloated stomach looking uncomfortable", "genero": "F", "idade": "adulto"},
    {"queixa": "Tenho hemorroida e sofro demais pra ir ao banheiro porque as fezes ficam muito ressecadas. Preciso amolecer isso urgente.", "produto_alvo": "Lactulose ou Fibras", "prompt_img": "portrait of a middle-aged brazilian man looking pained and uncomfortable sitting", "genero": "M", "idade": "adulto"},
    {"queixa": "Eu não quero tomar purgante porque me dá cólica, mas minha barriga tá tão estufada que não fecha nem a calça. Queria algo natural pra uso diário.", "produto_alvo": "Fibras", "prompt_img": "portrait of a brazilian woman trying to zip tight jeans looking frustrated due to bloating", "genero": "F", "idade": "adulto"},
    {"queixa": "Minha avó é acamada e o intestino dela é super preguiçoso. O médico falou de um xarope doce que não agride o estômago.", "produto_alvo": "Lactulose", "prompt_img": "portrait of a caregiver asking for medicine for an elderly bedridden patient", "genero": "F", "idade": "adulto"},
    {"queixa": "Toda tarde minha visão fica cansada, embaçada, parece que forço muito pra ler.", "produto_alvo": "Luteína", "prompt_img": "portrait of a middle-aged brazilian person rubbing tired eyes while holding a book", "genero": "M", "idade": "adulto"},
    {"queixa": "Fico o dia todo olhando pra tela do computador e do celular. No final do dia meu olho arde muito e fica seco.", "produto_alvo": "Luteína", "prompt_img": "portrait of a young adult brazilian office worker with red tired eyes looking at a screen", "genero": "F", "idade": "jovem"},
    {"queixa": "Trabalho como motorista de aplicativo, rodo o dia todo. A claridade do sol e farol à noite tão me incomodando demais.", "produto_alvo": "Luteína", "prompt_img": "portrait of a brazilian ride-share driver in a car squinting bothered by light", "genero": "M", "idade": "adulto"}
]

# --- FUNÇÕES ---
def carregar_equipe():
    if os.path.exists(ARQUIVO_EQUIPE):
        try: return pd.read_csv(ARQUIVO_EQUIPE)['Nome'].tolist()
        except: pass
    padrao = ["André", "Bruna", "Eliana", "Leticia", "Marcella", "Jessica", "Diego", "Anderson"]
    salvar_equipe(padrao)
    return padrao

def salvar_equipe(lista):
    pd.DataFrame({'Nome': lista}).to_csv(ARQUIVO_EQUIPE, index=False)

def carregar_historico():
    if os.path.exists(ARQUIVO_HISTORICO):
        try: return pd.read_excel(ARQUIVO_HISTORICO)
        except: pass
    return pd.DataFrame(columns=["Data", "Colaborador", "ProdutoAlvo", "Conversa", "Nota", "FeedbackIA"])

def salvar_sessao(dados):
    df = carregar_historico()
    df = pd.concat([df, pd.DataFrame([dados])], ignore_index=True)
    df.to_excel(ARQUIVO_HISTORICO, index=False)

# O CULPADO DO ERRO "ROBOTICS-PREVIEW" FOI DELETADO.
# Fixamos o modelo diretamente para garantir 100% de estabilidade.
# Substitua a função encontrar_modelo() por esta:
# E garanta que a variável seja definida assim:
@st.cache_resource
def encontrar_modelo():
    if not API_KEY: 
        return None
    
    # Lista dos modelos estáveis atuais (evite 'preview' ou nomes antigos)
    modelos_recomendados = [
        "gemini-1.5-flash-002",
        "gemini-1.5-flash",
        "gemini-1.5-pro-002",
        "gemini-1.5-pro"
    ]
    
    try:
        # Verifica quais modelos estão disponíveis na sua conta
        modelos_disponiveis = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Seleciona o primeiro que encontrar na nossa lista recomendada
        for modelo in modelos_recomendados:
            if modelo in modelos_disponiveis or f"models/{modelo}" in modelos_disponiveis:
                return f"models/{modelo}"
        
        # Caso nenhum dos recomendados esteja disponível (fallback)
        return "models/gemini-1.5-flash"
    except Exception as e:
        # Fallback de segurança em caso de falha na conexão
        return "models/gemini-1.5-flash"

def gerar_imagem_cliente_segura(prompt_bruto):
    try:
        prompt_formatado = urllib.parse.quote(prompt_bruto + " looking at camera")
        seed = random.randint(1, 100000)
        url = f"https://image.pollinations.ai/prompt/{prompt_formatado}?seed={seed}&width=300&height=300&nologo=true"
        resposta = requests.get(url, timeout=15)
        if resposta.status_code == 200:
            return resposta.content
        return None
    except:
        return None

def transcrever_audio_para_texto(audio_file):
    with st.spinner("🎧 Transcrevendo sua voz..."):
        try:
            mime_limpo = audio_file.type.split(';')[0] if audio_file.type else 'audio/wav'
            if mime_limpo == "audio/mp4" or mime_limpo == "audio/m4a":
                mime_limpo = "audio/mp4"

            model = genai.GenerativeModel(MODELO_NOME)
            res = model.generate_content([
                "Transcreva este áudio de atendimento de farmácia. Retorne APENAS o texto exato que foi falado, sem aspas, comentários ou formatação.",
                {"mime_type": mime_limpo, "data": audio_file.getvalue()}
            ])
            
            texto = res.text.strip()
            if not texto: return "Áudio incompreensível ou vazio."
            return texto
        except Exception as e:
            st.error(f"Erro do Google Gemini ao ler o áudio: {e}")
            return None

def gerar_audio_cliente(texto, genero="F"):
    try:
        if genero == "M":
            voz = "pt-BR-AntonioNeural" # Masculino
        else:
            voz = "pt-BR-FranciscaNeural" # Feminino
            
        resultado = []
        
        def worker():
            async def _gerar():
                communicate = edge_tts.Communicate(texto, voz)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                    temp_name = fp.name
                await communicate.save(temp_name)
                return temp_name
                
            try:
                arquivo_gerado = asyncio.run(_gerar())
                resultado.append(arquivo_gerado)
            except Exception as e:
                resultado.append(e)

        t = threading.Thread(target=worker)
        t.start()
        t.join() 
        
        res = resultado[0]
        if isinstance(res, Exception):
            st.error(f"Falha ao gerar voz da IA: {res}")
            return None
            
        with open(res, "rb") as f:
            data = f.read()
        os.remove(res) 
        return data
        
    except Exception as e:
        st.error(f"Erro fatal ao gerar áudio: {e}")
        return None

# --- ESTADO INICIAL ---
if "equipe" not in st.session_state: st.session_state.equipe = carregar_equipe()
if "historico_chat" not in st.session_state: st.session_state.historico_chat = []
if "turno" not in st.session_state: st.session_state.turno = 1
MAX_TURNOS = 4
if "produto_alvo" not in st.session_state: st.session_state.produto_alvo = ""
if "nota" not in st.session_state: st.session_state.nota = 0.0
if "feedback" not in st.session_state: st.session_state.feedback = ""
if "imagem_cliente" not in st.session_state: st.session_state.imagem_cliente = None
if "caso_atual" not in st.session_state: st.session_state.caso_atual = None
if "casos_disponiveis" not in st.session_state: st.session_state.casos_disponiveis = CASOS_REAIS.copy()

# ==========================================
# HEADER
# ==========================================
st.markdown("<div class='titulo-central'>🏆 💊 Coach Suprabio 🧠</div>", unsafe_allow_html=True)

if not CONEXAO_OK:
    st.error("⚠️ Configure a API Key nos 'Secrets'!")

col_esq, col_meio, col_dir = st.columns([1, 1, 1])
with col_meio:
    with st.popover("⚙️ Ajustes", use_container_width=True):
        st.header("Ajustes do Gerente")
        if not CONEXAO_OK:
            nova_key = st.text_input("Cole API Key aqui:", type="password")
            if nova_key:
                genai.configure(api_key=nova_key)
                st.rerun()
                
        novo = st.text_input("Add Colaborador:")
        if st.button("➕ Adicionar") and novo:
            st.session_state.equipe.append(novo)
            salvar_equipe(st.session_state.equipe)
            st.rerun()
            
        df_historico = carregar_historico()
        if not df_historico.empty:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_historico.to_excel(writer, index=False, sheet_name='Treinamentos')
            st.download_button(
                label="📥 Baixar Excel",
                data=buffer.getvalue(),
                file_name=f"treino_coach_suprabio_{datetime.now().strftime('%d%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

st.markdown("---")

# ==========================================
# RANKING / GAMIFICAÇÃO DA EQUIPE
# ==========================================
df_rank = carregar_historico()
if not df_rank.empty:
    st.markdown("<h4 style='text-align: center; color: #555;'>🔥 Top Vendedores (Média de Notas)</h4>", unsafe_allow_html=True)
    
    df_rank['Nota'] = pd.to_numeric(df_rank['Nota'], errors='coerce')
    resumo = df_rank.groupby("Colaborador").agg(
        Media=("Nota", "mean"),
        Treinos=("Nota", "count")
    ).reset_index().sort_values("Media", ascending=False)
    
    top_n = min(len(resumo), 3)
    cols = st.columns(top_n)
    
    medalhas = ["🥇", "🥈", "🥉"]
    for i in range(top_n):
        nome = resumo.iloc[i]["Colaborador"]
        media = resumo.iloc[i]["Media"]
        treinos = resumo.iloc[i]["Treinos"]
        
        with cols[i]:
            st.metric(
                label=f"{medalhas[i]} {nome.upper()}", 
                value=f"{media:.1f}", 
                delta=f"{treinos} clientes",
                delta_color="normal"
            )
    st.markdown("---")

# ==========================================
# ÁREA DE TREINAMENTO
# ==========================================
st.markdown("<h3 class='subtitulo-central'>👤 Quem vai treinar agora?</h3>", unsafe_allow_html=True)
colaborador = st.selectbox("Vendedor:", ["Clique aqui para selecionar..."] + st.session_state.equipe, label_visibility="collapsed")
st.markdown("<br>", unsafe_allow_html=True)

if colaborador != "Clique aqui para selecionar...":
    
    if not st.session_state.historico_chat:
        if st.button("🔔 CHAMAR PRÓXIMO CLIENTE", type="primary"):
            
            if not st.session_state.casos_disponiveis:
                st.session_state.casos_disponiveis = CASOS_REAIS.copy()
            
            caso = random.choice(st.session_state.casos_disponiveis)
            st.session_state.casos_disponiveis.remove(caso)
            
            st.session_state.caso_atual = caso
            prompt_bruto = caso.get("prompt_img", "portrait of a brazilian person in a pharmacy")
            genero_caso = caso.get("genero", "F")
            
            with st.spinner("O cliente está entrando na farmácia..."):
                imagem_bytes = gerar_imagem_cliente_segura(prompt_bruto)
                st.session_state.imagem_cliente = imagem_bytes
                
                audio_bytes = gerar_audio_cliente(caso["queixa"], genero=genero_caso)
                
                st.session_state.historico_chat = [{"role": "Cliente", "text": caso["queixa"], "audio": audio_bytes}]
                st.session_state.produto_alvo = caso["produto_alvo"]
                st.session_state.turno = 1
                st.session_state.feedback = ""
            st.rerun()

    else:
        for i, msg in enumerate(st.session_state.historico_chat):
            if msg["role"] == "Cliente":
                col_img, col_txt = st.columns([1, 4])
                with col_img:
                    if st.session_state.imagem_cliente:
                        st.image(st.session_state.imagem_cliente, use_container_width=True)
                    else:
                        st.info("👤")
                with col_txt:
                    st.markdown(f"""<div class="cliente-box"><div class="chat-label">🗣️ CLIENTE:</div><div class="chat-texto">"{msg['text']}"</div></div>""", unsafe_allow_html=True)
                    if "audio" in msg and msg["audio"]:
                        st.audio(msg["audio"], format="audio/mpeg")
            else:
                st.markdown(f"""<div class="vendedor-box"><div class="chat-label">🧑‍⚕️ {colaborador.upper()}:</div><div class="chat-texto">{msg['text']}</div></div>""", unsafe_allow_html=True)

        if not st.session_state.feedback:
            with st.expander("🤫 Gabarito do Gerente (Não mostre ao colaborador)"):
                st.write(f"**Indicação ideal esperada:** {st.session_state.produto_alvo}")
                
            st.write(f"*(Turno {st.session_state.turno} de {MAX_TURNOS})*")
            
            resposta_texto = st.text_area("✍️ Digite sua resposta ou grave um áudio abaixo:", height=80, key=f"input_{st.session_state.turno}")
            audio_val = st.audio_input("🎙️ Gravar resposta em áudio", key=f"audio_{st.session_state.turno}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.session_state.turno < MAX_TURNOS:
                    if st.button("🗣️ RESPONDER E CONTINUAR"):
                        resposta_final = ""
                        if audio_val is not None:
                            resposta_final = transcrever_audio_para_texto(audio_val)
                        elif resposta_texto.strip() != "":
                            resposta_final = resposta_texto
                            
                        if not resposta_final:
                            st.warning("⚠️ Escreva algo ou grave um áudio para continuar!")
                        else:
                            with st.spinner("Cliente ouvindo e pensando..."):
                                st.session_state.historico_chat.append({"role": "Vendedor", "text": resposta_final})
                                texto_conversa = "\n".join([f"{m['role']}: {m['text']}" for m in st.session_state.historico_chat])
                                
                                prompt_cliente = f"""
                                {BASE_RAG_SUPRABIO}
                                
                                Atue como um cliente de farmácia brasileiro.
                                Sua queixa principal inicial era a falta de: {st.session_state.produto_alvo}.
                                
                                Histórico da conversa:
                                {texto_conversa}
                                
                                Aja naturalmente. Use as informações do "DOCUMENTO DE PRODUTOS SUPRABIO" para criar objeções realistas se o vendedor recomendar o produto.
                                Exemplo: Se o vendedor falar o nome do produto, pergunte sobre o preço ou se não vai fazer mal pro estômago.
                                Regras:
                                1. Seja curto (1 a 2 frases). Sem aspas.
                                2. Se o vendedor ainda não indicou o produto, apenas dê mais detalhes da sua dor.
                                3. Se o vendedor já indicou, traga uma objeção clássica baseada no documento RAG.
                                """
                                try:
                                    model = genai.GenerativeModel(MODELO_NOME)
                                    res_cliente = model.generate_content(prompt_cliente)
                                    texto_resposta_cliente = res_cliente.text.strip()
                                    
                                    genero_caso = st.session_state.caso_atual.get("genero", "F")
                                    audio_bytes = gerar_audio_cliente(texto_resposta_cliente, genero=genero_caso)
                                    
                                    st.session_state.historico_chat.append({"role": "Cliente", "text": texto_resposta_cliente, "audio": audio_bytes})
                                    st.session_state.turno += 1
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro na conexão com IA: {e}")
                else:
                    st.info("Limite de perguntas atingido. Finalize a venda.")

            with col2:
                btn_tipo = "primary" if st.session_state.turno == MAX_TURNOS else "secondary"
                if st.button("✅ FINALIZAR E AVALIAR", type=btn_tipo):
                    resposta_final = ""
                    if audio_val is not None:
                        resposta_final = transcrever_audio_para_texto(audio_val)
                    elif resposta_texto.strip() != "":
                        resposta_final = resposta_texto
                        
                    if not resposta_final:
                        st.warning("⚠️ Escreva sua resposta final ou valide sua gravação!")
                    else:
                        with st.spinner("O Coach está analisando o atendimento..."):
                            st.session_state.historico_chat.append({"role": "Vendedor", "text": resposta_final})
                            texto_conversa_final = "\n".join([f"{m['role']}: {m['text']}" for m in st.session_state.historico_chat])
                            
                            prompt_aval = f"""
                            {BASE_RAG_SUPRABIO}
                            
                            Aja como um gerente técnico de farmácia rigoroso.
                            CONVERSA:
                            {texto_conversa_final}
                            
                            PRODUTO ALVO ESPERADO: {st.session_state.produto_alvo}
                            
                            AVALIAÇÃO:
                            1. O vendedor quebrou as objeções do cliente baseando-se no DOCUMENTO DE PRODUTOS? (Ex: Explicou que dimalato não solta intestino, ou que MDK tira o cálcio da artéria e põe no osso).
                            2. Teve empatia no atendimento?
                            3. Fez o fechamento da venda e indicou o {st.session_state.produto_alvo} corretamente?
                            
                            SAÍDA OBRIGATÓRIA:
                            NOTA_FINAL: [Sua nota de 0 a 10. Seja duro. Desconte pontos se ele só leu o rótulo sem quebrar objeção]
                            FEEDBACK: [Feedback prático avaliando o conjunto]
                            """
                            try:
                                model = genai.GenerativeModel(MODELO_NOME)
                                res_aval = model.generate_content(prompt_aval)
                                match = re.search(r"NOTA_FINAL:\s*(\d+(?:[\.,]\d+)?)", res_aval.text, re.IGNORECASE)
                                st.session_state.feedback = res_aval.text.replace("FEEDBACK:", "").strip()
                                st.session_state.nota = float(match.group(1).replace(',', '.')) if match else 0.0
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao avaliar: {e}")

        # 4. RESULTADO
        if st.session_state.feedback:
            st.markdown("---")
            cor = "green" if st.session_state.nota >= 7 else "red"
            st.markdown(f"<h1 style='text-align: center; color: {cor}'>{st.session_state.nota}/10</h1>", unsafe_allow_html=True)
            with st.container(border=True):
                st.info(st.session_state.feedback)
            
            col_save, col_discard = st.columns(2)
            with col_save:
                if st.button("💾 SALVAR TREINO", type="primary"):
                    conversa_str = " | ".join([f"{m['role']}: {m['text']}" for m in st.session_state.historico_chat])
                    salvar_sessao({
                        "Data": datetime.now().strftime("%d/%m %H:%M"), 
                        "Colaborador": colaborador, 
                        "ProdutoAlvo": st.session_state.produto_alvo,
                        "Conversa": conversa_str, 
                        "Nota": st.session_state.nota, 
                        "FeedbackIA": st.session_state.feedback
                    })
                    st.success("Salvo!")
                    st.session_state.historico_chat = []
                    st.session_state.feedback = ""
                    st.session_state.imagem_cliente = None
                    st.session_state.caso_atual = None
                    st.rerun()
            with col_discard:
                if st.button("🗑️ DESCARTAR"):
                    st.session_state.historico_chat = []
                    st.session_state.feedback = ""
                    st.session_state.imagem_cliente = None
                    st.session_state.caso_atual = None
                    st.rerun()