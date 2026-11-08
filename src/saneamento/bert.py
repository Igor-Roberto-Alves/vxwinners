"""Camada 2 - BERT: classificacao de token (BIO) para separar sujeito e caracteristicas.

Treinado nos rotulos gratuitos da propria base (ver rotulos.py). Faz o que o
gazetteer nao faz: decidir QUAL atributo e cada valor quando o texto nao diz.
Em 'RET. 110MM 15MM BASL NBR' a regra acha dois numeros em MM e nao sabe se
110 e o diametro do eixo ou do alojamento; o modelo aprende a ordem com os
14 mil exemplos auto-rotulados.

Loop de treino em PyTorch puro, sem Trainer, para nao depender da API de uma
versao especifica de transformers. Roda em CPU: e o cenario do hackathon.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

MODELO_PADRAO = "distilbert-base-multilingual-cased"


@dataclass
class Predicao:
    atributo: str
    valor: str
    confianca: float
    tokens: tuple[int, ...]


def _rotulos_bio(nomes_atributos: list[str]) -> list[str]:
    out = ["O"]
    for n in nomes_atributos:
        out += [f"B-{n}", f"I-{n}"]
    return out


def agrupar_bio(tokens: list[str], por_palavra: dict[int, tuple[str, float]],
                corte: float = 0.0) -> list["Predicao"]:
    """Junta B-/I- consecutivos no valor do atributo.

    `por_palavra` e {indice da palavra: (rotulo BIO, probabilidade)}. Fora da
    classe de proposito: e a regra de decodificacao, e vale poder testa-la sem
    carregar torch nem o modelo de 500 MB.

    `corte` e o piso POR PALAVRA: abaixo dele a palavra e tratada como O, o que
    FECHA o span em vez de engoli-la. O limiar que o pipeline ja tinha
    (LIMIAR_BERT) olha a media do span, e media esconde a palavra fraca - o
    recorte 'INOX 316 EXTREMIDADES' (0,88 / 0,99 / 0,31) da 0,73 e passa.
    """
    saida: list[Predicao] = []
    atual_attr: str | None = None
    atual_toks: list[int] = []
    atual_probs: list[float] = []

    def fechar():
        if atual_attr and atual_toks:
            saida.append(Predicao(
                atributo=atual_attr,
                valor=" ".join(tokens[i] for i in atual_toks),
                confianca=sum(atual_probs) / len(atual_probs),
                tokens=tuple(atual_toks),
            ))

    for w in range(len(tokens)):
        rot, p = por_palavra.get(w, ("O", 0.0))
        if corte and p < corte:
            rot = "O"            # palavra fraca nao entra no span nem abre um
        if rot == "O":
            fechar()
            atual_attr, atual_toks, atual_probs = None, [], []
            continue
        prefixo, _, nome = rot.partition("-")
        if prefixo == "B" or nome != atual_attr:
            fechar()
            atual_attr, atual_toks, atual_probs = nome, [w], [p]
        else:
            atual_toks.append(w)
            atual_probs.append(p)
    fechar()
    return saida


class ExtratorBert:
    def __init__(self, nomes_atributos: list[str], modelo_base: str = MODELO_PADRAO,
                 max_len: int = 96, dispositivo: str | None = None,
                 piso_palavra: float = 0.0):
        import torch

        self.torch = torch
        self.rotulos = _rotulos_bio(nomes_atributos)
        self.id2label = dict(enumerate(self.rotulos))
        self.label2id = {v: k for k, v in self.id2label.items()}
        self.modelo_base = modelo_base
        self.max_len = max_len
        # Piso de probabilidade POR PALAVRA (ver prever()). O limiar do pipeline
        # (LIMIAR_BERT, 0,60) e sobre a MEDIA do span, e media dilui a palavra
        # fraca: 'INOX 316 EXTREMIDADES' com 0,88/0,99/0,31 da 0,73 e passa.
        # Zero = comportamento historico (argmax puro, sem piso).
        self.piso_palavra = piso_palavra
        self.dispositivo = dispositivo or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tok = None
        self.modelo = None
        self._estado_retomada: dict | None = None

    # ------------------------------------------------------------- carga

    def _montar(self, origem: str | None = None):
        from transformers import AutoModelForTokenClassification, AutoTokenizer

        origem = origem or self.modelo_base
        self.tok = AutoTokenizer.from_pretrained(origem)
        self.modelo = AutoModelForTokenClassification.from_pretrained(
            origem, num_labels=len(self.rotulos),
            id2label=self.id2label, label2id=self.label2id,
        ).to(self.dispositivo)

    def carregar(self, diretorio: str | Path, para_treino: bool = False) -> "ExtratorBert":
        d = Path(diretorio)
        meta = json.loads((d / "rotulos.json").read_text(encoding="utf-8"))
        self.rotulos = meta["rotulos"]
        self.id2label = {int(k): v for k, v in meta["id2label"].items()}
        self.label2id = {v: k for k, v in self.id2label.items()}
        self._montar(str(d))
        self.modelo.eval()
        arq = d / "retomada.pt"
        if para_treino and arq.exists():
            self._estado_retomada = self.torch.load(arq, weights_only=False)
        return self

    @property
    def epoca_concluida(self) -> int:
        return (self._estado_retomada or {}).get("epoca_concluida", 0)

    def salvar(self, diretorio: str | Path, otimizador=None, agendador=None,
               epoca_concluida: int = 0, historico: dict | None = None) -> None:
        d = Path(diretorio)
        d.mkdir(parents=True, exist_ok=True)
        self.modelo.save_pretrained(d)
        self.tok.save_pretrained(d)
        (d / "rotulos.json").write_text(
            json.dumps({"rotulos": self.rotulos,
                        "id2label": {str(k): v for k, v in self.id2label.items()}},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        if otimizador is not None:
            self.torch.save(
                {"otimizador": otimizador.state_dict(),
                 "agendador": agendador.state_dict() if agendador else None,
                 "epoca_concluida": epoca_concluida,
                 "historico": historico or {}},
                d / "retomada.pt",
            )

    # ------------------------------------------------------------- lote

    def _codificar(self, lote: list[dict], com_rotulo: bool = True):
        torch = self.torch
        enc = self.tok(
            [e["tokens"] for e in lote],
            is_split_into_words=True, truncation=True, max_length=self.max_len,
            padding=True, return_tensors="pt",
        )
        if not com_rotulo:
            return enc, None
        alvos = []
        for i, e in enumerate(lote):
            ids = enc.word_ids(i)
            anterior, linha = None, []
            for w in ids:
                if w is None:
                    linha.append(-100)                    # especial: ignorado na perda
                elif w != anterior:
                    linha.append(self.label2id.get(e["rotulos"][w], 0))
                else:
                    linha.append(-100)                    # so o 1o subtoken da palavra
                anterior = w
            alvos.append(linha)
        return enc, torch.tensor(alvos)

    # ------------------------------------------------------------- treino

    def treinar(self, treino: list[dict], validacao: list[dict] | None = None,
                epocas: int = 3, lote: int = 16, lr: float = 5e-5,
                log_cada: int = 50, semente: int = 42,
                checkpoint: str | Path | None = None) -> dict:
        """Treina, gravando checkpoint ao FIM DE CADA EPOCA.

        O checkpoint existe porque treino em CPU e longo e qualquer interrupcao
        antes do fim perdia tudo: salvar so no final significa que parar no passo
        650 de 1944 devolve zero. Com checkpoint por epoca, retomar() continua de
        onde parou.
        """
        torch = self.torch
        torch.manual_seed(semente)       # mesma semente, mesmo modelo
        if self.modelo is None:
            self._montar()
        self.modelo.train()

        historico = {"perda": [], "validacao": []}
        inicio = 0
        estado = self._estado_retomada
        if estado:
            inicio = estado.get("epoca_concluida", 0)
            historico = estado.get("historico") or historico
            print(f"  retomando da epoca {inicio + 1}/{epocas}", flush=True)

        por_epoca = math.ceil(len(treino) / lote)
        restantes = por_epoca * max(epocas - inicio, 1)   # orcamento do agendador
        passos = por_epoca * epocas                       # total, so para o log
        passo = inicio * por_epoca

        otim = torch.optim.AdamW(self.modelo.parameters(), lr=lr)
        # O agendador e dimensionado para os passos QUE FALTAM e nao e restaurado
        # do checkpoint: o estado salvo carrega o total_steps do treino anterior e
        # estourava ("Tried to step 7 times, total is 6") ao continuar com mais
        # epocas. Recriar da um novo ciclo de LR sobre o orcamento restante, que e
        # o comportamento previsivel de um warm restart.
        sched = torch.optim.lr_scheduler.OneCycleLR(
            otim, max_lr=lr, total_steps=max(restantes, 1), pct_start=0.1
        )
        if estado and estado.get("otimizador"):
            otim.load_state_dict(estado["otimizador"])
        self._estado_retomada = None

        for ep in range(inicio, epocas):
            soma, n = 0.0, 0
            for i in range(0, len(treino), lote):
                bloco = treino[i:i + lote]
                enc, alvos = self._codificar(bloco)
                enc = {k: v.to(self.dispositivo) for k, v in enc.items()}
                saida = self.modelo(**enc, labels=alvos.to(self.dispositivo))
                saida.loss.backward()
                torch.nn.utils.clip_grad_norm_(self.modelo.parameters(), 1.0)
                otim.step()
                sched.step()
                otim.zero_grad()
                soma += float(saida.loss.detach())
                n += 1
                passo += 1
                if log_cada and passo % log_cada == 0:
                    print(f"  epoca {ep + 1}/{epocas}  passo {passo}/{passos}  perda {soma / n:.4f}", flush=True)
            historico["perda"].append(soma / max(n, 1))
            if validacao:
                m = self.avaliar(validacao)
                historico["validacao"].append(m)
                print(f"  epoca {ep + 1}: perda {soma / max(n, 1):.4f}  "
                      f"F1 token {m['f1']:.3f}  exato {m['exato']:.3f}", flush=True)
                self.modelo.train()
            if checkpoint:
                self.salvar(checkpoint, otimizador=otim, agendador=sched,
                            epoca_concluida=ep + 1, historico=historico)
                print(f"  checkpoint da epoca {ep + 1} gravado em {checkpoint}", flush=True)
        self.modelo.eval()
        return historico

    # ------------------------------------------------------------- avaliacao

    def avaliar(self, dados: list[dict], lote: int = 32) -> dict:
        torch = self.torch
        self.modelo.eval()
        acerto = total = 0
        tp = fp = fn = 0
        exatos = 0
        with torch.no_grad():
            for i in range(0, len(dados), lote):
                bloco = dados[i:i + lote]
                enc, alvos = self._codificar(bloco)
                enc_d = {k: v.to(self.dispositivo) for k, v in enc.items()}
                logits = self.modelo(**enc_d).logits.cpu()
                pred = logits.argmax(-1)
                for j, e in enumerate(bloco):
                    mascara = alvos[j] != -100
                    p = pred[j][mascara].tolist()
                    a = alvos[j][mascara].tolist()
                    acerto += sum(1 for x, y in zip(p, a) if x == y)
                    total += len(a)
                    exatos += int(p == a)
                    for x, y in zip(p, a):
                        if y != 0 and x == y:
                            tp += 1
                        elif y != 0 and x != y:
                            fn += 1
                        elif y == 0 and x != 0:
                            fp += 1
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        return {
            "acuracia_token": acerto / total if total else 0.0,
            "precisao": prec, "recall": rec,
            "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "exato": exatos / len(dados) if dados else 0.0,
            "n": len(dados),
        }

    # ------------------------------------------------------------- inferencia

    def prever(self, tokens: list[str], piso: float | None = None) -> list[Predicao]:
        """Roda o modelo e agrupa B-/I- consecutivos no valor do atributo.

        `piso` (ou self.piso_palavra) e um corte de probabilidade POR PALAVRA:
        palavra cujo rotulo mais provavel nao alcanca o piso e tratada como O, o
        que fecha o span em vez de engolir a palavra duvidosa. Serve ao caso em
        que o limiar do arbitro nao chega: ele olha a MEDIA do span, e a media
        esconde um I- fraco entre dois tokens altos.
        """
        torch = self.torch
        if self.modelo is None:
            raise RuntimeError("modelo nao carregado: use carregar() ou treinar()")
        corte = self.piso_palavra if piso is None else piso
        enc, _ = self._codificar([{"tokens": tokens}], com_rotulo=False)
        ids_palavra = enc.word_ids(0)
        with torch.no_grad():
            logits = self.modelo(**{k: v.to(self.dispositivo) for k, v in enc.items()}).logits[0].cpu()
        probs = logits.softmax(-1)

        # um rotulo por palavra: o do primeiro subtoken
        por_palavra: dict[int, tuple[str, float]] = {}
        anterior = None
        for pos, w in enumerate(ids_palavra):
            if w is None or w == anterior:
                anterior = w
                continue
            anterior = w
            idx = int(probs[pos].argmax())
            por_palavra[w] = (self.id2label.get(idx, "O"), float(probs[pos][idx]))

        return agrupar_bio(tokens, por_palavra, corte)
