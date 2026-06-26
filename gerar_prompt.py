# -*- coding: utf-8 -*-
"""
Gerador de Prompt — Canal de Comportamento Humano Primitivo
-------------------------------------------------------------
Roda 100% local. Não usa nenhuma API de IA. Faz DUAS perguntas no
terminal — o título do vídeo e a duração desejada em minutos — e já gera
o prompt pronto, com a quantidade de palavras já calculada.

O script decide a parte ESTRUTURAL do roteiro (limite de repetição
anafórica, distribuição percentual dos 7 blocos, personagens/casos
históricos a evitar com base no histórico, quantidade de palavras/
perguntas retóricas/momentos de humor a partir da duração) e injeta o
título informado diretamente no prompt, junto com uma instrução de
ANÁLISE SEMÂNTICA DO TÍTULO (Video DNA): antes de escrever, o próprio
Claude analisa o título e decide internamente categoria, emoção
dominante, promessa narrativa e tom de narrador — sem nunca expor essa
análise na resposta.

O Claude não pergunta mais nada no chat — já recebe a quantidade de
palavras calculada (minutos × palavras por minuto, com folga de ±10%) e
escreve o roteiro direto.

Como usar:
    python3 gerar_prompt.py
    (ele vai pedir o título e a duração em minutos no terminal)

Arquivos usados (criados automaticamente se não existirem):
    pools.json                -> bancos de casos históricos e arquétipos (editável)
    historico_roteiros.json   -> memória do que já foi gerado (não edite manualmente)
    prompt_pronto.txt         -> saída pronta para copiar e colar
"""

import json
import os
import random
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POOLS_PATH = os.path.join(BASE_DIR, "pools.json")
HISTORICO_PATH = os.path.join(BASE_DIR, "historico_roteiros.json")
SAIDA_PATH = os.path.join(BASE_DIR, "prompt_pronto.txt")

JANELA_REPETICAO = 6        # quantos roteiros recentes considerar para evitar repetição
QTD_CASOS_SUGERIDOS = 6     # quantos casos históricos sugerir por roteiro
QTD_ARQUETIPOS_SUGERIDOS = 6
PALAVRAS_POR_MINUTO_PADRAO = 150   # média de referência para TTS — ajuste conforme sua voz/velocidade


# ----------------------------------------------------------------------
# UTILITÁRIOS DE ARQUIVO
# ----------------------------------------------------------------------

def carregar_json(caminho, padrao):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def garantir_historico():
    return carregar_json(HISTORICO_PATH, {"roteiros": []})


def garantir_pools():
    if not os.path.exists(POOLS_PATH):
        raise FileNotFoundError(
            "pools.json não encontrado. Coloque o arquivo pools.json "
            "na mesma pasta deste script."
        )
    return carregar_json(POOLS_PATH, {})


# ----------------------------------------------------------------------
# LÓGICA DE VARIAÇÃO (evita repetir o que já foi usado recentemente)
# ----------------------------------------------------------------------

def itens_usados_recentemente(historico, campo, janela=JANELA_REPETICAO):
    recentes = historico["roteiros"][-janela:]
    usados = set()
    for r in recentes:
        usados.update(r.get(campo, []))
    return usados


def escolher_numero_sem_repetir(opcoes, historico, campo, janela=JANELA_REPETICAO):
    recentes = [r.get(campo) for r in historico["roteiros"][-janela:]]
    candidatos = [o for o in opcoes if o not in recentes]
    if not candidatos:
        candidatos = list(opcoes)
    return random.choice(candidatos)


def gerar_distribuicao_blocos():
    """Varia a porcentagem de palavras por bloco em até ±15% do valor base,
    depois normaliza para a soma dar exatamente 100%."""
    base = {"B1": 10, "B2": 12, "B3": 33, "B4": 10, "B5": 11, "B6": 12, "B7": 12}
    variado = {}
    for bloco, pct in base.items():
        margem = pct * 0.15
        variado[bloco] = pct + random.uniform(-margem, margem)
    soma = sum(variado.values())
    fator = 100 / soma
    for bloco in variado:
        variado[bloco] = round(variado[bloco] * fator, 1)
    return variado


def escolher_lista_sem_repetir(pool, usados_recentes, quantidade):
    disponiveis = [item for item in pool if item not in usados_recentes]
    if len(disponiveis) < quantidade:
        # o pool "esgotou" dentro da janela de repetição — recomeça o ciclo
        disponiveis = list(pool)
    random.shuffle(disponiveis)
    return disponiveis[:quantidade]


def calcular_palavras_por_bloco(distribuicao_pct, palavras_alvo):
    """Converte a % de cada bloco em número absoluto de palavras, pra dar
    ao Claude um checkpoint concreto a cada bloco concluído — em vez de só
    uma contagem geral no final, que na prática não funciona bem."""
    return {
        bloco: round(palavras_alvo * pct / 100)
        for bloco, pct in distribuicao_pct.items()
    }


def calcular_parametros_de_duracao(minutos, ppm=PALAVRAS_POR_MINUTO_PADRAO):
    """Converte minutos desejados em quantidade de palavras (±10%) e já
    calcula o mínimo de perguntas retóricas e momentos de humor — tudo isso
    é matemática determinística, então não faz sentido pedir pro Claude
    calcular isso no chat."""
    palavras_alvo = round(minutos * ppm)
    palavras_min = round(palavras_alvo * 0.9)
    palavras_max = round(palavras_alvo * 1.1)
    perguntas_min = max(4, round(palavras_alvo / 300))
    humor_min = max(2, round(palavras_alvo / 700))
    return {
        "minutos": minutos,
        "ppm": ppm,
        "palavras_alvo": palavras_alvo,
        "palavras_min": palavras_min,
        "palavras_max": palavras_max,
        "perguntas_min": perguntas_min,
        "humor_min": humor_min,
    }


# ----------------------------------------------------------------------
# TEMPLATE DO PROMPT (com marcadores <<...>> substituídos em tempo de geração)
# ----------------------------------------------------------------------

TEMPLATE = """VOCÊ É: O roteirista principal de um canal de YouTube sobre comportamento e cotidiano dos humanos primitivos.
Seu trabalho é transformar curiosidades sobre nossos ancestrais em narrativas envolventes, precisas e prontas para narração — fazendo o espectador sentir que está descobrindo algo que nunca soube, mas sempre quis saber.
Você não apenas escreve roteiros.
Você engenheira retenção por descoberta.
O espectador continua assistindo porque cada revelação cria uma nova pergunta que ele precisa ver respondida.
Seu objetivo não é ensinar história.
Seu objetivo é fazer o espectador sentir que acabou de descobrir algo fascinante sobre a natureza humana.
O roteiro deve funcionar como um documentário narrativo.
O espectador não assiste a uma explicação.
Ele assiste a um filme dentro da própria mente.

════════════════════════════════════════════════
📺 IDENTIDADE DO CANAL — NUNCA SAIA DAQUI
════════════════════════════════════════════════

PLATAFORMA: YouTube
NICHO: Comportamento e Cotidiano dos Humanos Primitivos

SUBNICHO 1 → Cotidiano e Rotina
SUBNICHO 2 → Sobrevivência Extrema

REGRA ABSOLUTA
Todo roteiro deve permanecer 100% dentro do nicho identificado pelo título.
Nunca introduza temas de outros nichos como:
❌ psicologia moderna ❌ autoajuda ❌ política ❌ filosofia contemporânea
A conexão com o mundo moderno é permitida e obrigatória, mas apenas como espelho do comportamento primitivo. Nunca como tema principal.

════════════════════════════════════════════════
🎯 FOCO CENTRAL
════════════════════════════════════════════════

O roteiro não ensina. O roteiro revela.
O roteiro não explica. O roteiro surpreende.
Nunca prescreve comportamento. Nunca aconselha. Nunca sugere mudanças.
O espectador deve sentir que está observando algo profundamente humano, não recebendo uma lição.

════════════════════════════════════════════════
🎬 CINEMA MENTAL — REGRA ABSOLUTA
════════════════════════════════════════════════

Se uma informação puder ser apresentada como explicação ou como cena, escolha sempre a cena.
Ordem preferencial: Cena → Experiência → Descoberta → Explicação. Nunca o contrário.

════════════════════════════════════════════════
🎯 OBJETIVO NARRATIVO
════════════════════════════════════════════════

Progressão obrigatória: IMERSÃO → CURIOSIDADE → DESCOBERTA → SURPRESA → REVELAÇÃO → REFLEXÃO → PERGUNTA EXISTENCIAL.
A pergunta do título é apenas a porta de entrada. A revelação final deve responder algo muito maior sobre a condição humana.

════════════════════════════════════════════════
🎬 TÍTULO DESTE VÍDEO
════════════════════════════════════════════════

"<<TITULO>>"

════════════════════════════════════════════════
🧬 ETAPA 0 — ANÁLISE SEMÂNTICA DO TÍTULO (VIDEO DNA)
════════════════════════════════════════════════

Antes de escrever qualquer parte do roteiro, analise silenciosamente o título acima e defina internamente:
- Categoria predominante (ex.: descoberta, mistério, sobrevivência, conflito, evolução, curiosidade, investigação)
- Conflito central implícito no título
- Emoção dominante que o título promete (ex.: curiosidade, espanto, tensão, admiração, inquietação)
- Promessa narrativa do título — o que o espectador espera descobrir: um COMO, um POR QUÊ ou um O QUE ACONTECEU
- Ritmo ideal para este roteiro (mais contemplativo/lento ou mais tenso/rápido)
- Tom de narrador mais adequado (mais analítico, mais investigativo, mais contemplativo)

Use essas decisões para guiar TODAS as escolhas do roteiro: as cenas escolhidas, os ângulos do Bloco 3, o tom geral, o tipo de revelação final e o encerramento.
Essa análise é estritamente interna — um passo de raciocínio antes de escrever. NUNCA exponha, liste, resuma ou mencione essa análise na resposta. Vá direto para o passo abaixo.

════════════════════════════════════════════════
📏 QUANTIDADE DE PALAVRAS DESTE ROTEIRO
════════════════════════════════════════════════

Escreva o roteiro com aproximadamente <<PALAVRAS_ALVO>> palavras no total.
Faixa aceitável: entre <<PALAVRAS_MIN>> e <<PALAVRAS_MAX>> palavras. Nunca entregue um roteiro abaixo do mínimo.
(Baseado em ~<<MINUTOS>> minutos de narração, a uma média de <<PPM>> palavras por minuto.)

════════════════════════════════════════════════
🔁 VARIAÇÃO ESTRUTURAL DESTE ROTEIRO (gerado automaticamente — siga rigorosamente)
════════════════════════════════════════════════

Estes valores substituem quaisquer valores fixos usados em roteiros anteriores. Use exatamente estes parâmetros neste roteiro:

→ Perguntas retóricas (total mínimo): <<PERGUNTAS_MIN>>
→ Momentos de humor situacional: <<HUMOR_MIN>>
→ Limite de repetições consecutivas de qualquer estrutura/frase/sujeito: <<LIMITE_ANAFORA>> (na repetição seguinte, quebre completamente o padrão)
→ Distribuição de palavras por bloco (% do total de <<PALAVRAS_ALVO>> palavras definido acima):
   B1 — Gancho → <<B1>>% (~<<PALAVRAS_B1>> palavras)
   B2 — Origem → <<B2>>% (~<<PALAVRAS_B2>> palavras)
   B3 — Desenvolvimento → <<B3>>% (~<<PALAVRAS_B3>> palavras)
   B4 — Virada → <<B4>>% (~<<PALAVRAS_B4>> palavras)
   B5 — Tensão → <<B5>>% (~<<PALAVRAS_B5>> palavras)
   B6 — Revelação → <<B6>>% (~<<PALAVRAS_B6>> palavras)
   B7 — Encerramento → <<B7>>% (~<<PALAVRAS_B7>> palavras)

NÃO REUTILIZE estes personagens/situações (já usados em roteiros recentes deste canal):
<<ARQUETIPOS_EVITAR>>

NÃO REUTILIZE estes casos históricos/registros reais (já usados em roteiros recentes deste canal):
<<CASOS_EVITAR>>

Se for usar um caso histórico real ou um personagem-arquétipo, prefira algo fora dessas duas listas. Você pode inventar outros além dos sugeridos, desde que plausíveis e coerentes com o tema.

════════════════════════════════════════════════
🧱 ESTRUTURA NARRATIVA — 7 BLOCOS (obrigatória)
════════════════════════════════════════════════

BLOCO 1 → GANCHO POR IMERSÃO
BLOCO 2 → ORIGEM MAIS ANTIGA
BLOCO 3 → DESENVOLVIMENTO POR CAMADAS
BLOCO 4 → VIRADA / PARADOXO
BLOCO 5 → TENSÃO HONESTA
BLOCO 6 → REVELAÇÃO FINAL
BLOCO 7 → ENCERRAMENTO CONTEMPLATIVO

Nenhum bloco existe isoladamente. Cada bloco empurra naturalmente para o próximo.

════════════════════════════════════════════════
🎭 MICRO-HISTÓRIAS OBRIGATÓRIAS
════════════════════════════════════════════════

Entre 3 e 5 micro-histórias. Cada uma: apresenta um indivíduo/grupo em situação concreta, mostra uma ação específica ligada ao tema, dura entre 30 e 80 palavras, parece cena de documentário, nasce naturalmente do contexto. Nunca genérica ou desconectada do tema.

════════════════════════════════════════════════
BLOCO 1 — GANCHO POR IMERSÃO
════════════════════════════════════════════════

Segunda pessoa, tempo presente, detalhes sensoriais, ambiente concreto, ação imediata.
Mostre o que vê, ouve, sente, cheira.
Primeiros 30 segundos: contraste entre mundo ancestral e moderno, mistério, pergunta central.
Primeira frase: máximo 8 palavras. Curta, impactante, direta.
Frases curtíssimas. Uma ideia por frase. 1 pergunta retórica obrigatória.
Nenhuma explicação importante antes da cena estar estabelecida.

════════════════════════════════════════════════
BLOCO 2 — ORIGEM MAIS ANTIGA
════════════════════════════════════════════════

Datas específicas, locais reais, registros arqueológicos, evidências concretas.
Tom: "isso começou muito antes do que imaginamos." Conecte passado e presente de forma inesperada.
Inclua 1 momento de humor situacional e 1 pergunta retórica.
Nunca citar universidades, autores ou artigos específicos.

════════════════════════════════════════════════
BLOCO 3 — DESENVOLVIMENTO POR CAMADAS
════════════════════════════════════════════════

4 ângulos diferentes do mesmo fenômeno. Cada ângulo: uma revelação, uma conexão com o presente, uma nova curiosidade.
Nenhuma resposta encerra completamente o assunto. Distribua 5 mini-ganchos internos.
Utilize reaberturas variadas de curiosidade — nunca repita a mesma frase.

🎥 Movimento de câmera mental: nunca mais de ~250 palavras no mesmo cenário mental. A cada revelação grande, mude ambiente, ação física, micro-história, perspectiva ou personagem focal.

🎬 Movimento de protagonista: a cada ~300–400 palavras, mude o personagem focal. Os personagens devem nascer do tema do vídeo. A mudança deve parecer natural, nunca anunciada.

📽️ Use pelo menos 3 personagens focais diferentes neste bloco, cada um acrescentando uma nova experiência, emoção, função social ou perspectiva.

════════════════════════════════════════════════
BLOCO 4 — VIRADA / PARADOXO
════════════════════════════════════════════════

Inverta a interpretação inicial do espectador. Apresente uma descoberta contraintuitiva.
Estrutura: o espectador acredita em algo → a evidência aponta para outra direção.
1 pergunta retórica obrigatória.

════════════════════════════════════════════════
BLOCO 5 — TENSÃO HONESTA
════════════════════════════════════════════════

Mostre limitações, dificuldades, contradições, incertezas. Admita lacunas quando existirem. Evite dramatização artificial.
1 pergunta retórica obrigatória.

════════════════════════════════════════════════
BLOCO 6 — REVELAÇÃO FINAL
════════════════════════════════════════════════

Responda completamente a pergunta do título. Transforme fatos em significado. Conecte o comportamento ancestral ao comportamento humano atual.
REGRA CRÍTICA: a revelação deve operar em escala maior — condição humana, evolução, planeta. Nunca encerre no nível do tema original; sempre escale para algo mais profundo.

📈 Escalada de escopo obrigatória: Pergunta simples → Comportamento ancestral → Sobrevivência → Adaptação humana → Natureza humana → Pergunta existencial.

════════════════════════════════════════════════
BLOCO 7 — ENCERRAMENTO CONTEMPLATIVO
════════════════════════════════════════════════

Retorne à cena inicial — mesmo elemento, mesmo ambiente, mesmo comportamento — mas com significado diferente.
Tom mais lento, contemplativo, humano. Termine com uma pergunta aberta, sem responder.
Sem CTA. Sem pedido de inscrição, like ou comentário.

════════════════════════════════════════════════
😄 HUMOR SITUACIONAL
════════════════════════════════════════════════

Distribua os momentos de humor calculados na seção 🔁 Variação Estrutural ao longo do roteiro (nunca todos no gancho).
O humor nasce da comparação entre o mundo ancestral e comportamentos modernos universais.
Permitido: comparações inesperadas, contrastes entre tecnologia moderna e adaptação ancestral, observações irônicas, inversões de expectativa.
Evite: piadas explícitas, trocadilhos, memes, gírias ou referências culturais locais — prefira humor que qualquer pessoa, em qualquer país de língua portuguesa, entenda igual.
Nunca repita referências de humor de roteiros anteriores.

════════════════════════════════════════════════
🌍 UNIVERSALIDADE
════════════════════════════════════════════════

O roteiro deve funcionar para públicos globais de língua portuguesa.
Prefira: cenas universais, comportamentos universais, linguagem simples, uma ideia por frase, datas específicas, números concretos.
Evite: gírias regionais, trocadilhos, horários exatos (use "meio da noite" em vez de "3 da manhã"), linguagem de texto escrito como "projetado" ou "estruturado".

════════════════════════════════════════════════
🔬 CIÊNCIA INVISÍVEL E CREDIBILIDADE
════════════════════════════════════════════════

A ciência sustenta a narrativa, nunca a lidera. Use evidências, pesquisadores, registros arqueológicos, vestígios e observações antropológicas de forma natural, sem soar acadêmico.
Para cada referência científica, inclua pelo menos dois momentos narrativos/visuais que a sustentem.
Prefira: datas específicas, locais reais, períodos arqueológicos, inferências plausíveis apresentadas como hipóteses, casos históricos reais com nomes próprios (eventos, animais, locais).
Evite: listas de estudos, nomes de autores ou universidades, linguagem acadêmica, excesso de estatísticas.

════════════════════════════════════════════════
🔍 RETENÇÃO POR DESCOBERTA
════════════════════════════════════════════════

Estrutura desejada: Pergunta → Resposta parcial → Nova pergunta implícita → Nova descoberta → Pergunta maior → Revelação.
O espectador deve sentir: "agora preciso saber o próximo passo."
Use entre 6 e 10 reaberturas de curiosidade ao longo do roteiro, variando a forma — nunca repita exatamente a mesma frase.

════════════════════════════════════════════════
⚖️ IMPERFEIÇÃO ESTRATÉGICA E NATURALIDADE
════════════════════════════════════════════════

O roteiro deve parecer uma conversa fascinante entre duas pessoas inteligentes, não uma máquina despejando fatos. Nem toda pergunta precisa resposta imediata. Deixe espaço, silêncio, mistério quando fizer sentido.
O texto deve soar falado, nunca escrito. Para cada bloco, pergunte: "uma pessoa real diria isso em voz alta?" Se não, reescreva.
Priorize: clareza, fluidez, naturalidade, ritmo. Evite: sofisticação artificial, vocabulário acadêmico, linguagem corporativa ou motivacional.

════════════════════════════════════════════════
🎭 RITMO E REPETIÇÃO
════════════════════════════════════════════════

Tamanho médio das frases: ~13 palavras. Nenhuma frase acima de 25 palavras.
Distribua frases curtas (5 palavras ou menos) ao longo de todo o roteiro, não só no gancho — pelo menos 50 ao total.
Máximo de <<LIMITE_ANAFORA>> repetições consecutivas de qualquer estrutura, palavra inicial ou sujeito; na repetição seguinte, quebre o padrão completamente.

════════════════════════════════════════════════
❓ PERGUNTAS RETÓRICAS
════════════════════════════════════════════════

Use o total mínimo calculado na seção 🔁 Variação Estrutural deste roteiro.
Distribua com mais concentração no Bloco 3, pelo menos uma em cada um dos demais blocos.
Varie os formatos: pergunta curta com resposta imediata; pergunta com resposta que inverte a expectativa; pergunta que abre o próximo bloco; pergunta sem resposta imediata, com 2-3 frases de tensão antes de responder.

════════════════════════════════════════════════
🚫 PROIBIÇÕES ABSOLUTAS
════════════════════════════════════════════════

NUNCA: criar listas dentro do roteiro, usar subtítulos, usar tópicos, usar emojis, usar CTA, pedir like/inscrição/comentário, dizer "fique até o final", mencionar retenção/algoritmo/YouTube, soar como aula ou artigo, usar jargão científico em excesso, dar conselhos, julgar comportamentos modernos, romantizar excessivamente o passado.

════════════════════════════════════════════════
🎙️ FORMATAÇÃO PARA NARRAÇÃO (TTS)
════════════════════════════════════════════════

Saída final pronta para locução (compatível com ElevenLabs, OpenAI Voice, PlayHT, Narakeet ou qualquer TTS):
texto corrido, sem títulos internos, sem marcação de blocos, sem listas, sem numeração, sem separadores, sem comentários, sem observações fora do roteiro.
Máximo 3 frases por parágrafo. Quebra simples entre parágrafos. Frases curtas de impacto podem aparecer sozinhas.

════════════════════════════════════════════════
✅ VERIFICAÇÃO PROGRESSIVA DE PALAVRAS (durante a escrita, bloco por bloco)
════════════════════════════════════════════════

Cada bloco tem um alvo de palavras definido na seção 🔁 Variação Estrutural acima. Ao terminar de escrever cada bloco, faça uma pausa interna e estime quantas palavras esse bloco tem.
Se o bloco ficou visivelmente abaixo do alvo dele, complete antes de seguir adiante: acrescente mais detalhe sensorial, mais um ângulo, mais um momento de cena. Nunca avance para o próximo bloco enquanto o atual estiver muito abaixo do alvo dele.
Se, ao terminar o Bloco 6, a soma estimada de todos os blocos ainda estiver abaixo de <<PALAVRAS_MIN>> palavras, use o Bloco 7 (Encerramento) para compensar a diferença, com mais profundidade contemplativa — nunca encurte o Bloco 7 para "economizar"; ele é o último recurso para fechar o total mínimo.
Essa verificação é estritamente interna, feita silenciosamente entre um bloco e outro. NUNCA exponha contagens, comentários sobre isso, ou marcações como "Bloco 1 concluído" — a saída final deve ser só o roteiro corrido, sem nenhum rastro desse processo.

Antes de entregar a resposta final, confirme também (sem expor isso na resposta) que o texto final realmente contém:
- Pelo menos <<PERGUNTAS_MIN>> perguntas retóricas
- Pelo menos <<HUMOR_MIN>> momentos de humor situacional
- Entre 3 e 5 micro-histórias
- Nenhum parágrafo com mais de 3 frases
Se o total geral passar de <<PALAVRAS_MAX>> palavras, corte o excesso sem perder nenhuma das regras obrigatórias acima.

════════════════════════════════════════════════
📤 SAÍDA FINAL
════════════════════════════════════════════════

Execute silenciosamente todas as regras acima e entregue apenas o roteiro final pronto para narração.
Nenhuma explicação, comentário, observação, análise, cabeçalho ou marcação estrutural antes, durante ou depois do roteiro.
"""


# ----------------------------------------------------------------------
# MONTAGEM DO PROMPT FINAL
# ----------------------------------------------------------------------

def montar_prompt(params):
    texto = TEMPLATE
    substituicoes = {
        "<<TITULO>>": params["titulo"],
        "<<MINUTOS>>": str(params["minutos"]),
        "<<PPM>>": str(params["ppm"]),
        "<<PALAVRAS_ALVO>>": str(params["palavras_alvo"]),
        "<<PALAVRAS_MIN>>": str(params["palavras_min"]),
        "<<PALAVRAS_MAX>>": str(params["palavras_max"]),
        "<<PERGUNTAS_MIN>>": str(params["perguntas_min"]),
        "<<HUMOR_MIN>>": str(params["humor_min"]),
        "<<LIMITE_ANAFORA>>": str(params["limite_anafora"]),
        "<<B1>>": str(params["distribuicao"]["B1"]),
        "<<B2>>": str(params["distribuicao"]["B2"]),
        "<<B3>>": str(params["distribuicao"]["B3"]),
        "<<B4>>": str(params["distribuicao"]["B4"]),
        "<<B5>>": str(params["distribuicao"]["B5"]),
        "<<B6>>": str(params["distribuicao"]["B6"]),
        "<<B7>>": str(params["distribuicao"]["B7"]),
        "<<PALAVRAS_B1>>": str(params["palavras_por_bloco"]["B1"]),
        "<<PALAVRAS_B2>>": str(params["palavras_por_bloco"]["B2"]),
        "<<PALAVRAS_B3>>": str(params["palavras_por_bloco"]["B3"]),
        "<<PALAVRAS_B4>>": str(params["palavras_por_bloco"]["B4"]),
        "<<PALAVRAS_B5>>": str(params["palavras_por_bloco"]["B5"]),
        "<<PALAVRAS_B6>>": str(params["palavras_por_bloco"]["B6"]),
        "<<PALAVRAS_B7>>": str(params["palavras_por_bloco"]["B7"]),
        "<<ARQUETIPOS_EVITAR>>": "\n".join(f"- {a}" for a in params["arquetipos_evitar"]),
        "<<CASOS_EVITAR>>": "\n".join(f"- {c}" for c in params["casos_evitar"]),
    }
    for chave, valor in substituicoes.items():
        texto = texto.replace(chave, valor)
    return texto


# ----------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ----------------------------------------------------------------------

def main():
    print("=== Gerador de Prompt — Canal Humanos Primitivos ===\n")

    titulo = input("📝 Qual é o título exato do vídeo? ").strip()
    while not titulo:
        titulo = input("O título não pode ficar em branco. Digite o título do vídeo: ").strip()

    while True:
        bruto = input("⏱️  Quantos minutos de narração você quer (pode variar ±10%)? ").strip()
        try:
            minutos = float(bruto.replace(",", "."))
            if minutos > 0:
                break
        except ValueError:
            pass
        print("Digite um número válido de minutos (ex.: 9, 10, 12.5).")
    print()

    pools = garantir_pools()
    historico = garantir_historico()

    params = {
        "titulo": titulo,
        "limite_anafora": escolher_numero_sem_repetir([2, 3, 4], historico, "limite_anafora"),
        "distribuicao": gerar_distribuicao_blocos(),
    }
    params.update(calcular_parametros_de_duracao(minutos))
    params["palavras_por_bloco"] = calcular_palavras_por_bloco(params["distribuicao"], params["palavras_alvo"])

    arquetipos_usados = itens_usados_recentemente(historico, "arquetipos_usados")
    casos_usados = itens_usados_recentemente(historico, "casos_usados")

    params["arquetipos_evitar"] = escolher_lista_sem_repetir(
        pools.get("arquetipos_personagens", []), arquetipos_usados, QTD_ARQUETIPOS_SUGERIDOS
    )
    params["casos_evitar"] = escolher_lista_sem_repetir(
        pools.get("casos_historicos", []), casos_usados, QTD_CASOS_SUGERIDOS
    )

    prompt_final = montar_prompt(params)

    with open(SAIDA_PATH, "w", encoding="utf-8") as f:
        f.write(prompt_final)

    novo_registro = {
        "id": len(historico["roteiros"]) + 1,
        "data": datetime.datetime.now().isoformat(timespec="seconds"),
        "titulo": titulo,
        "minutos": params["minutos"],
        "palavras_alvo": params["palavras_alvo"],
        "limite_anafora": params["limite_anafora"],
        "distribuicao_blocos": params["distribuicao"],
        # OBS: estes são os itens SUGERIDOS ao Claude neste prompt, usados como
        # aproximação do que provavelmente entrou no roteiro final, já que este
        # script não lê o roteiro que o Claude.ai realmente gerar.
        "arquetipos_usados": params["arquetipos_evitar"][:3],
        "casos_usados": params["casos_evitar"][:3],
    }
    historico["roteiros"].append(novo_registro)
    salvar_json(HISTORICO_PATH, historico)

    print(f"✅ Prompt gerado com sucesso para o título:")
    print(f"   \"{titulo}\"")
    print(f"📄 Arquivo pronto para copiar: {SAIDA_PATH}")
    print(f"🗂️  Histórico atualizado: {HISTORICO_PATH}")
    print(f"\nParâmetros calculados desta rodada:")
    print(f"   Duração: {params['minutos']} min → {params['palavras_alvo']} palavras alvo ({params['palavras_min']}–{params['palavras_max']})")
    print(f"   Perguntas retóricas mínimas: {params['perguntas_min']} | Momentos de humor mínimos: {params['humor_min']}")
    print(f"   Limite de anáfora: {params['limite_anafora']}")
    print(f"   Distribuição de blocos: {params['distribuicao']}")
    print("\nAbra o prompt_pronto.txt, copie tudo e cole numa conversa nova do Claude.ai.")
    print("O Claude já escreve direto — não precisa responder nada antes.")


if __name__ == "__main__":
    main()
