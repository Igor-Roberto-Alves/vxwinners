"""Camada 4 - LLM (Claude no Bedrock): roda so no residuo que o arbitro escalou.

Nunca e chamado na base inteira. Entra quando regra e BERT discordam, quando o
dicionario casou mais de um valor ou quando o sujeito ficou incerto. A saida
passa pelo mesmo validador das outras camadas: valor fora da lista de valores
permitidos do PDM e recusado, mesmo vindo do modelo grande.

Credenciais: .env do projeto (ver claude-bedrock.sh). Sem credencial valida o
pipeline continua rodando - o residuo fica marcado para revisao humana, que e o
comportamento correto, nao um erro.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

from .pdm import Classe
from .texto import normalizar

# IDs sao perfis de inferencia (prefixo us.), nao IDs de foundation model: todos os
# Claude da conta so aceitam INFERENCE_PROFILE, invocar anthropic.* direto da erro.
# Haiku e o modelo de volume do residuo; Sonnet entra no que o Haiku erra.
MODELO_PADRAO = os.environ.get("MODELO_LLM", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
MODELO_DIFICIL = os.environ.get("MODELO_LLM_DIFICIL", "us.anthropic.claude-sonnet-5")
REGIAO_PADRAO = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

# (dolar por milhao de token de entrada, de saida). Serve para o relatorio saber
# quanto a execucao custou sem depender de ninguem fazer a conta a mao. Modelo
# nao listado cai no preco do Haiku, que subestima - confira antes de trocar de
# modelo. O preco do Haiku 4.5 e o que a frente usou para dimensionar o teto.
PRECO = {"haiku-4-5": (1.00, 5.00)}

# Da geracao Opus 4.7 / Sonnet 5 em diante temperature foi removida do inferenceConfig
# e a Converse devolve ValidationException ("`temperature` is deprecated for this
# model"). Mandar o campo derruba 100% das chamadas, nao uma parte.
_ACEITA_TEMPERATURA = re.compile(
    r"claude-(?:v2|instant|3|3-5|3-7|haiku-4-5|sonnet-4-5|opus-4-5|sonnet-4-6|opus-4-6)", re.I
)

# Erro de configuracao: repetir nao conserta e, no residuo inteiro, repetir 3x com
# backoff custa horas para produzir zero resultado. So throttling e falha de rede
# merecem nova tentativa.
_PERMANENTES = ("ValidationException", "AccessDeniedException", "ResourceNotFoundException",
                "UnrecognizedClientException", "InvalidSignatureException",
                "SerializationException")

SISTEMA = """Voce extrai atributos tecnicos de materiais industriais para um cadastro \
padronizado (PDM). Devolva APENAS o que esta escrito no texto.

Regras obrigatorias:
- Atributo com lista de valores: use EXATAMENTE um dos valores da lista, nunca uma variacao.
- Atributo ausente no texto: devolva null. Nunca deduza, nunca complete com conhecimento proprio.
- Atributo com lista: siga este procedimento de CONTAGEM, nesta ordem, sem atalho.
  Passo 1 - percorra a lista inteira e separe TODOS os valores compativeis com o
    trecho. Compativel inclui diferenca de notacao: espaco, hifen, ponto e juncao
    sao a mesma coisa, e abreviacao conta como o termo inteiro. Decida contra ESTA
    lista, nunca contra o que existe no mundo: valor que nao esta na lista nao
    entra na contagem e portanto nao cria duvida.
  Passo 2 - contou exatamente 1? devolva esse valor, escrito como a lista o escreve.
  Passo 3 - contou 2 ou mais? devolva null. O trecho nao distingue, escolher um
    inventaria o que o texto nao diz, e essa decisao e do cadastrista.
  Passo 4 - contou 0? devolva null.
  O passo 3 vale SEMPRE, inclusive quando a diferenca entre os candidatos e so o
  final do nome. Notacao nunca serve para desempatar, so para reconhecer.
    trecho "ZINC",  lista NATURAL | ZINCADO BRANCO         -> 1 -> ZINCADO BRANCO
    trecho "ZINCADO", lista ZINCADO AMARELO | ZINCADO BRANCO -> 2 -> null
    trecho "TC12",  lista TC-01 | TC-04 | TC-12 | TC-25    -> 1 -> TC-12
    trecho "A2280", lista AHLSTAR A22-80 | AHLSTAR A31-100 -> 1 -> AHLSTAR A22-80
    trecho "ACO",   lista ACO CARBONO | ACO INOX 304 | ACO INOX 316 -> 3 -> null
    trecho "INOX",  lista ACO INOX 304 | ACO INOX 316      -> 2 -> null
- Notacao compacta junta atributos: M12X50 = BITOLA M12 + COMPRIMENTO 50MM.
- Passo de rosca ausente implica ROSCA = METRICA GROSSA.
- Varias grandezas de mesma unidade na mesma classe: o texto as lista na ordem dos
  atributos. Se vierem menos numeros que atributos, o primeiro numero e do atributo
  de menor ordem (a medida principal da classe, que o texto nunca omite) e o ultimo
  e do atributo de maior ordem; os atributos do meio ficam null. Em RETENTOR
  "RET 50MM 8MM" e DIAMETRO EIXO 50MM + LARGURA 8MM, com DIAMETRO ALOJAMENTO null.
- Ordem de grandeza do dominio, use como conferencia: DIAMETRO ALOJAMENTO >
  DIAMETRO EIXO > LARGURA e ESPESSURA. Atribuicao que inverta isso esta errada.
- Milimetro: numero + MM com decimal em virgula (16,25MM). Polegada: fracao + POL (1.1/4POL).
- Pressao sempre em BAR (converta de psi dividindo por 14,5038; de MPa multiplicando por 10).
- Texto em maiusculas, sem acento e sem cedilha.

Campo evidencias - leia com atencao, ele alimenta um dicionario permanente:
- Para CADA atributo que voce preencheu, e SO para esses, copie a MENOR subcadeia do
  TEXTO que originou o valor, caractere por caractere, sem explicacao e sem reescrever.
- Atributo que voce deixou null NAO entra em evidencias. Nao use o campo para justificar
  null: a justificativa e descartada e atrapalha.
- Use o nome do atributo exatamente como aparece em ATRIBUTOS, com espaco, nunca com "_".
- Nao copie a descricao inteira: o trecho tem de ser o pedaco que identifica o valor.
    certo  "AHLSTAR A2280"
    errado "AHLSTAR A2280 (interpretado como AHLSTAR A22-80)"   <- tem explicacao
    errado "BOMBA CENTRIFUGA AHLSTAR A2280 SULZER"              <- e o texto inteiro
    errado "ZINC e ambiguo entre as opcoes da lista"             <- atributo ficou null
- NUNCA escolha uma VARIANTE quando o texto nao diz qual. Se a lista tem valores
  que diferem por uma caracteristica (processo: FORJADO x FUNDIDO; acabamento:
  BRANCO x AMARELO; grau: 304 x 316; classe: 10.9 x 12.9) e o texto nao traz essa
  caracteristica, responda null. 'INOX 316' nao diz se e forjado ou fundido:
  null. 'ZINCADO' nao diz a cor: null. 'ACO' nao diz a liga: null.
- Completar o que o cadastro nao escreveu NAO e padronizar, e inventar
  especificacao. Item com a caixa vazia vai para revisao; item com a variante
  errada vai para a producao e alguem compra a peca errada.
"""


# Identidade do prompt, para o cache por hash saber que as regras mudaram.
_VERSAO_PROMPT = hashlib.sha256(SISTEMA.encode()).hexdigest()[:12]


@dataclass
class RespostaLlm:
    valores: dict[str, str | None]
    evidencias: dict[str, str]
    bruto: str = ""
    tokens_entrada: int = 0
    tokens_saida: int = 0
    do_cache: bool = False
    erro: str = ""
    truncado: bool = False


def _ferramenta(classe: Classe) -> dict:
    """Schema de saida forcado por tool use: o modelo so pode devolver estes campos."""
    props = {}
    for a in sorted(classe.atributos, key=lambda x: x.ordem):
        campo: dict = {"description": f"{a.nome}. {a.formato}"[:300]}
        if a.valores:
            campo["type"] = ["string", "null"]
            campo["enum"] = a.valores + [None]
        else:
            campo["type"] = ["string", "null"]
        props[a.nome] = campo
    return {
        "toolSpec": {
            "name": "registrar_atributos",
            "description": f"Registra os atributos da classe {classe.id_pdm}.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        # additionalProperties False: o modelo nao pode inventar nome
                        # de atributo fora da classe. O validador recusaria depois, mas
                        # ai o custo da chamada ja foi pago.
                        "atributos": {"type": "object", "properties": props,
                                      "additionalProperties": False},
                        "evidencias": {
                            "type": "object",
                            "description": (
                                "Uma entrada para cada atributo preenchido, e so para esses. "
                                "Chave: o nome do atributo igual ao de 'atributos'. "
                                "Valor: a menor subcadeia copiada literalmente do TEXTO que "
                                "originou o valor - sem explicacao, sem reescrita e sem a "
                                "descricao inteira. Atributo null nao entra aqui."
                            ),
                            "additionalProperties": {"type": "string"},
                        },
                    },
                    # evidencias em required: sem o trecho de origem o dicionario
                    # aprendido nao aprende nada, e a chamada vira gasto de uso unico.
                    "required": ["atributos", "evidencias"],
                }
            },
        }
    }


def _prompt(classe: Classe, texto: str, foco: list[str], motivos: list[str]) -> str:
    linhas = [f"CLASSE: {classe.rotulo()} ({classe.id_pdm})", "", "ATRIBUTOS:"]
    for a in sorted(classe.atributos, key=lambda x: x.ordem):
        marca = "obrigatorio" if (a.obrigatorio and a.sempre) else "opcional"
        if a.valores:
            regra = "um de: " + " | ".join(a.valores)
        else:
            regra = a.formato or "texto livre"
        linhas.append(f"  {a.nome} ({marca}) {regra}"[:400])
    if foco:
        linhas += ["", "ATENCAO ESPECIAL nestes atributos, onde as camadas automaticas "
                   "nao chegaram a acordo:", "  " + ", ".join(foco)]
    if motivos:
        linhas += ["", "MOTIVO DA ESCALADA: " + "; ".join(motivos)]
    linhas += ["", "TEXTO:", texto]
    return "\n".join(linhas)


# Evidencia que cobre quase toda a descricao nao e termo, e a descricao: nao
# generaliza para nenhum outro registro e transformaria o dicionario aprendido
# numa copia do cache por hash do texto, que ja existe.
FRACAO_MAXIMA_EVIDENCIA = 0.7


def _limpar_evidencias(classe: Classe, texto: str, valores: dict,
                       evid: dict, contador: dict | None = None) -> dict[str, str]:
    """Mantem so a evidencia que pode virar termo de dicionario.

    `evidencias` e o unico campo de texto livre da resposta, e o modelo o usa de
    quatro formas erradas - todas medidas em resposta real do Haiku 4.5:

    1. Chave com "_" no lugar do espaco ("MODELO_EQUIPAMENTO"). O nome vem do
       texto livre do modelo, nao do enum do schema, entao nao ha nada que o
       obrigue a coincidir. Era a causa de o par mais valioso do dominio
       ("AHLSTAR A2280" -> AHLSTAR A22-80) nunca ser aprendido.
    2. Evidencia de atributo que ficou null: o modelo aproveita o campo para
       justificar a recusa ("ZINC e ambiguo entre ..."). Nao e trecho.
    3. Evidencia que nao e subcadeia do texto: pega a prosa e a reescrita que
       sobrarem. E a unica verificacao OBJETIVA possivel aqui, e por isso a mais
       importante: sem ela o dicionario guarda o que o modelo imaginou.
    4. Evidencia igual a descricao inteira (ver FRACAO_MAXIMA_EVIDENCIA).

    Limpar aqui, e nao no arbitro, e deliberado: este e o unico ponto do pipeline
    que ainda tem o TEXTO que foi enviado ao modelo, e a verificacao 3 depende dele.
    """
    def conta(chave: str) -> None:
        if contador is not None:
            contador[chave] = contador.get(chave, 0) + 1

    nomes = {normalizar(a.nome): a.nome for a in classe.atributos}
    texto_n = normalizar(texto)
    limpas: dict[str, str] = {}
    for bruta, trecho in (evid or {}).items():
        if not isinstance(trecho, str) or not trecho.strip():
            continue
        nome = nomes.get(normalizar(bruta))
        if nome is None:
            conta("evid_atributo_desconhecido")
            continue
        if nome != bruta:
            conta("evid_chave_corrigida")
        if not valores.get(nome):
            conta("evid_sem_valor")        # justificativa de null
            continue
        trecho_n = normalizar(trecho)
        if len(trecho_n) < 2 or trecho_n not in texto_n:
            conta("evid_fora_do_texto")    # prosa, reescrita ou invencao
            continue
        if len(trecho_n) >= FRACAO_MAXIMA_EVIDENCIA * len(texto_n):
            conta("evid_texto_inteiro")
            continue
        conta("evid_ok")
        limpas[nome] = trecho
    return limpas


def _compacto(s: str) -> str:
    """Forma insensivel a notacao: 'TC-12', 'TC 12' e 'TC12' viram 'TC12'.

    E a mesma equivalencia que o prompt pede ao modelo no passo 1. Serve para
    CONTAR quantos valores do enum um trecho alcanca, nada mais.
    """
    return normalizar(s).replace(" ", "").replace("-", "").replace(".", "")


_RX_DIGITOS = re.compile(r"\d+")


def _digitos(s: str) -> set[str]:
    """Numeros do texto, lidos na forma compacta.

    Compactar antes e o que faz '1 1/8 POL' e '1.1/8POL' darem o mesmo conjunto:
    comparar digito a digito na forma crua acusaria diferenca onde so existe
    notacao.
    """
    return set(_RX_DIGITOS.findall(_compacto(s)))


def _palavras(s: str) -> set[str]:
    return {p for p in normalizar(s).split() if p}


def _vocabulario_puro(atributo) -> bool:
    """Atributo cujo enum e vocabulario, nao lista de grandezas.

    O PDM ja faz essa distincao no proprio campo FORMATO, e ela importa porque
    as travas de valor abaixo comparam trecho com valor: onde o valor E uma
    grandeza, a diferenca entre os dois e ESPERADA e nao indica erro.

      ACABAMENTO, MATERIAL, CLASSE RESISTENCIA  'lista de valores'   -> trava
      BITOLA               'rosca metrica M + diametro em mm'        -> isento
      MODELO EQUIPAMENTO   'modelo como o fabricante designa'        -> isento

    Sem esta isenção a trava de gemeo numerico reprovava 'M12X50' -> BITOLA M12,
    que e a regra 2 do PDM funcionando, e a de subcadeia reprovava 'M-12' ->
    'M12' porque 'M12' tambem cabe dentro de 'M12X1,5'. Eram 25 reprovacoes
    indevidas em 31 na amostra. Nestes dois atributos a defesa fica sendo o
    procedimento de contagem do prompt.
    """
    return bool(atributo.valores) and normalizar(atributo.formato) == "LISTA DE VALORES"


def _vetar_ambiguos(classe: Classe, texto: str, valores: dict,
                    evid: dict, contador: dict | None = None) -> dict:
    """Anula valor cuja propria evidencia nao distingue um unico item do enum.

    Este e o erro que o validador NAO pega, e por isso o unico que precisa de
    codigo: 'ZINCADO' vira ZINCADO BRANCO, 'ACO' vira ACO CARBONO e 'INOX' vira
    ACO INOX 304. Os tres sao valores validos do PDM, entao passam pelo portao
    do validador intactos; o que esta errado e que o trecho servia igualmente a
    ZINCADO AMARELO, a ACO INOX 304/316 e a ACO INOX 316. Trocar 304 por 316 e o
    erro mais caro do dominio - cria item que alguem compra e instala.

    O prompt pede a contagem (passo 1 a 4 de SISTEMA) e o Haiku 4.5 acerta a
    maioria, mas erra justamente onde um valor do enum e extensao do outro:
    medido em 3 de 12 casos adversarios. Prompt nao basta para invariante
    verificavel, e esta e verificavel - so precisa do enum e do trecho.

    Escape: se o TEXTO INTEIRO contem a forma compacta do valor canonico, o texto
    distingue sozinho e o veto nao se aplica (o modelo so foi preguicoso no
    recorte). Sem isso, 'INOX 316' recortado como 'INOX' perderia um acerto.
    """
    def conta(chave: str) -> None:
        if contador is not None:
            contador[chave] = contador.get(chave, 0) + 1

    por_nome = {a.nome: a for a in classe.atributos}
    texto_c = _compacto(texto)
    for nome, valor in list(valores.items()):
        atributo = por_nome.get(nome)
        if not valor or atributo is None or not _vocabulario_puro(atributo):
            continue
        trecho = evid.get(nome)
        if not trecho:
            conta("valor_sem_evidencia")
            continue
        t = _compacto(trecho)
        if not t:
            continue

        # (a) TRAVA DE GEMEO NUMERICO. O trecho traz numero, o valor escolhido
        # traz numero, e nao sao o mesmo numero: o modelo trocou a grandeza por
        # outra parecida. Foi assim que 'CLASSE RESISTENCIA 12.9' virou '10.9'
        # em 74 registros da amostra - 12.9 existe no PDM, mas na lista de OUTRA
        # classe, entao em PDM001 a resposta certa era null.
        #
        # Esta trava nao tem escape pelo texto, de proposito: o embedding tem a
        # mesma trava (docs 04, secao 6) porque 304 por 316 e o erro mais caro
        # do dominio, e a razao vale igual para o modelo grande. O validador nao
        # pega nada disso - 10.9 e valor legitimo da lista.
        dig_t, dig_v = _digitos(trecho), _digitos(valor)
        if dig_t and dig_v and not dig_t <= dig_v:
            valores[nome] = None
            evid.pop(nome, None)
            conta("vetado_gemeo_numerico")
            continue

        # (b) ambiguidade por SUBCADEIA: 'ZINCADO' dentro de ZINCADO AMARELO e
        # de ZINCADO BRANCO.
        por_subcadeia = [v for v in atributo.valores if t in _compacto(v)]
        # (c) ambiguidade por PALAVRA: 'ACO FORJADO' nao e subcadeia de nenhum
        # valor, mas suas palavras cabem em ACO CARBONO FORJADO A105 e em ACO
        # INOX FORJADO A182 F316 - duas formas de produto diferentes. Sem este
        # caso o veto deixava passar o default do modelo.
        pal_t = _palavras(trecho)
        por_palavra = [v for v in atributo.valores if pal_t and pal_t <= _palavras(v)]

        if len(por_subcadeia) < 2 and len(por_palavra) < 2:
            continue
        if _compacto(valor) in texto_c:
            # o texto escreve o valor inteiro: distingue sozinho, e o modelo so
            # foi preguicoso no recorte
            conta("ambiguo_salvo_pelo_texto")
            continue
        valores[nome] = None
        evid.pop(nome, None)
        conta("vetado_por_ambiguidade" if len(por_subcadeia) >= 2
              else "vetado_ambiguidade_palavra")
    return valores


class DesempateLlm:
    def __init__(self, modelo: str = MODELO_PADRAO, regiao: str = REGIAO_PADRAO,
                 cache: str | Path = "artefatos/cache_llm", ativo: bool = True,
                 tentativas: int = 3, max_tokens: int = 1500):
        self.modelo = modelo
        self.regiao = regiao
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.tentativas = tentativas
        self.max_tokens = max_tokens
        self.ativo = ativo
        self._cliente = None
        self.erro_cliente = ""
        self._temperatura = bool(_ACEITA_TEMPERATURA.search(modelo))
        self.contador = {"chamadas": 0, "cache": 0, "erros": 0, "truncados": 0,
                         "tokens_entrada": 0, "tokens_saida": 0}

    # ------------------------------------------------------------- cliente

    @property
    def cliente(self):
        if self._cliente is None and self.ativo:
            try:
                import boto3

                self._cliente = boto3.client("bedrock-runtime", region_name=self.regiao)
            except Exception as e:  # credencial ausente, boto3 ausente, regiao invalida
                self.erro_cliente = f"{type(e).__name__}: {e}"
                self.ativo = False
        return self._cliente

    # ------------------------------------------------------------- cache

    def _chave(self, classe: Classe, texto: str, foco: list[str]) -> Path:
        # A versao do prompt entra na chave: sem isso, mexer em SISTEMA nao
        # invalida nada e a execucao seguinte serve em silencio respostas
        # produzidas sob as regras antigas - exatamente o caso de quando o
        # tratamento de ambiguidade mudou e o cache continuou devolvendo
        # ZINCADO BRANCO para "ZINCADO".
        crua = json.dumps([self.modelo, _VERSAO_PROMPT, classe.id_pdm, texto, sorted(foco)],
                          ensure_ascii=False)
        return self.cache / (hashlib.sha256(crua.encode()).hexdigest()[:24] + ".json")

    # ------------------------------------------------------------- chamada

    def desempatar(self, classe: Classe, texto: str, foco: list[str],
                   motivos: list[str] | None = None) -> RespostaLlm:
        arq = self._chave(classe, texto, foco)
        if arq.exists():
            d = json.loads(arq.read_text(encoding="utf-8"))
            self.contador["cache"] += 1
            return RespostaLlm(d["valores"], d.get("evidencias", {}), do_cache=True)

        if not self.ativo or self.cliente is None:
            return RespostaLlm({}, {}, erro=self.erro_cliente or "LLM desativado")

        corpo = {
            "modelId": self.modelo,
            "system": [{"text": SISTEMA}],
            "messages": [{"role": "user", "content": [{"text": _prompt(classe, texto, foco, motivos or [])}]}],
            "toolConfig": {
                "tools": [_ferramenta(classe)],
                "toolChoice": {"tool": {"name": "registrar_atributos"}},
            },
            "inferenceConfig": {"maxTokens": self.max_tokens},
        }
        if self._temperatura:
            corpo["inferenceConfig"]["temperature"] = 0

        erro = ""
        for tentativa in range(self.tentativas):
            try:
                r = self.cliente.converse(**corpo)
            except Exception as e:
                nome = type(e).__name__
                erro = f"{nome}: {e}"
                # Modelo novo que ainda nao esta em _ACEITA_TEMPERATURA: tira o campo
                # e tenta de novo em vez de perder o residuo inteiro.
                if "temperature" in str(e) and self._temperatura:
                    self._temperatura = False
                    corpo["inferenceConfig"].pop("temperature", None)
                    continue
                if nome in _PERMANENTES:
                    # Erro de configuracao vale para toda chamada seguinte: desliga a
                    # camada e guarda o motivo onde 04_extrair.py ja imprime, em vez de
                    # repetir 3.569 vezes o mesmo ValidationException em silencio.
                    self.ativo = False
                    self.erro_cliente = erro
                    break
                if tentativa < self.tentativas - 1:
                    time.sleep(2 ** tentativa + random.random())
                continue

            uso = r.get("usage", {})
            entrada_tok = uso.get("inputTokens", 0)
            saida_tok = uso.get("outputTokens", 0)
            self.contador["chamadas"] += 1
            self.contador["tokens_entrada"] += entrada_tok
            self.contador["tokens_saida"] += saida_tok

            valores, evid = {}, {}
            for bloco in r["output"]["message"]["content"]:
                if "toolUse" in bloco:
                    entrada = bloco["toolUse"]["input"]
                    valores = entrada.get("atributos", {}) or {}
                    evid = entrada.get("evidencias", {}) or {}

            # Antes de cachear: evidencia suja gravada no cache fica suja para
            # sempre, e e ela que alimenta o dicionario aprendido.
            evid = _limpar_evidencias(classe, texto, valores, evid, self.contador)
            valores = _vetar_ambiguos(classe, texto, valores, evid, self.contador)

            # maxTokens cortou a resposta no meio: o toolUse chega vazio ou pela
            # metade. Cachear isso congela o registro errado para sempre.
            truncado = r.get("stopReason") == "max_tokens"
            if truncado:
                self.contador["truncados"] += 1
            if valores and not truncado:
                arq.write_text(json.dumps({"valores": valores, "evidencias": evid},
                                          ensure_ascii=False), encoding="utf-8")
            return RespostaLlm(valores, evid, tokens_entrada=entrada_tok,
                               tokens_saida=saida_tok, truncado=truncado,
                               erro="resposta truncada por maxTokens" if truncado else "")

        self.contador["erros"] += 1
        if not self.erro_cliente:
            self.erro_cliente = erro
        return RespostaLlm({}, {}, erro=erro)

    def resumo(self) -> str:
        c = self.contador
        s = (f"LLM ({self.modelo}): {c['chamadas']} chamadas, {c['cache']} do cache, "
             f"{c['erros']} erros, {c['truncados']} truncados, "
             f"{c['tokens_entrada']} tokens entrada, {c['tokens_saida']} tokens saida")
        s += f"\n  custo estimado: US$ {self.custo():.2f}"
        aceitas = c.get("evid_ok", 0)
        descartes = {k[5:]: v for k, v in c.items()
                     if k.startswith("evid_") and k != "evid_ok" and v}
        if aceitas or descartes:
            s += (f"\n  evidencias uteis (viram termo de dicionario): {aceitas}"
                  f"\n  evidencias descartadas: {descartes or '{}'}")
        s += (f"\n  vetados: {c.get('vetado_por_ambiguidade', 0)} por subcadeia ambigua, "
              f"{c.get('vetado_ambiguidade_palavra', 0)} por palavra ambigua, "
              f"{c.get('vetado_gemeo_numerico', 0)} por gemeo numerico"
              f"\n    (salvos pelo texto: {c.get('ambiguo_salvo_pelo_texto', 0)}, "
              f"valor sem evidencia: {c.get('valor_sem_evidencia', 0)})")
        if self.erro_cliente:
            s += f"\n  ultimo erro: {self.erro_cliente}"
        return s

    def custo(self) -> float:
        """Custo em dolar das chamadas desta execucao (cache e erro nao custam)."""
        p_ent, p_sai = next(
            (p for nome, p in PRECO.items() if nome in self.modelo), PRECO["haiku-4-5"])
        c = self.contador
        return (c["tokens_entrada"] * p_ent + c["tokens_saida"] * p_sai) / 1_000_000
