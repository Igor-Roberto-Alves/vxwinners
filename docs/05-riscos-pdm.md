# Riscos estruturais do PDM

Gerado por `scripts/08_auditar_pdm.py` a partir de
`dados/03_padrao_cadastro_PDM.xlsx`. Nao editar a mao.

```

================================================================================================
RISCO A - MESMO SUBSTANTIVO, QUALIFICADOR SUPERCONJUNTO
================================================================================================
Uma classe e a outra MAIS alguma coisa. Se o texto nao traz a palavra
extra, o casamento lexico cai sempre na classe geral.
COMO RESOLVER: regras.ClassificadorLexico._preferir_irmao_especifico: troca para a
               especifica quando o texto evidencia as caixas exclusivas dela.

  PDM010 MANGUEIRA HIDRAULICA               <- geral
  PDM011 MANGUEIRA HIDRAULICA MONTADA       <- especifica
     substantivo comum .......... MANGUEIRA
     unidade ................... M vs PC   (a unidade do cadastro ja e uma pista)
     caixas exclusivas da especifica (4): ['COMPRIMENTO', 'TERMINAL A', 'TERMINAL B', 'MATERIAL TERMINAIS']

  PDM001 PARAFUSO SEXTAVADO                 <- geral
  PDM002 PARAFUSO SEXTAVADO INTERNO         <- especifica
     substantivo comum .......... PARAFUSO
     unidade ................... PC vs PC
     caixas exclusivas da especifica (1): ['TIPO CABECA']


================================================================================================
RISCO B - MESMO SUBSTANTIVO, QUALIFICADORES DISJUNTOS
================================================================================================
Irmas que se distinguem por uma palavra. Se a palavra faltar no texto,
nao ha como escolher entre elas pelo nome.
COMO RESOLVER: a palavra do qualificador tem de estar no texto; sem ela o registro
               fica com empate e vai para a banda do LLM com as candidatas do grupo.

  ARRUELA                  1 par(es): PDM004 LISA, PDM005 PRESSAO
  JUNTA                    1 par(es): PDM033 ESPIRALADA, PDM034 PLANA
  LUVA                     1 par(es): PDM050 -, PDM070 SEGURANCA
  MANGUEIRA                5 par(es): PDM010 HIDRAULICA, PDM011 HIDRAULICA MONTADA, PDM012 INDUSTRIAL, PDM013 PNEUMATICA
  ROLAMENTO                3 par(es): PDM020 RIGIDO ESFERAS, PDM021 AUTOCOMPENSADOR ROLOS, PDM022 ROLOS CONICOS
  VALVULA                  10 par(es): PDM040 ESFERA, PDM041 GAVETA, PDM042 GLOBO, PDM043 RETENCAO, PDM044 BORBOLETA

================================================================================================
RISCO C - SUBSTANTIVO COMPARTILHADO ENTRE GRUPOS DIFERENTES
================================================================================================
O mesmo substantivo designa objetos SEM NENHUMA relacao. Se o
GRUPO_MERCADORIA do cadastro estiver errado, o item vira outra coisa.
COMO RESOLVER: manter o filtro por grupo e nunca abandonar grupo de classe unica;
               quando a busca ampla troca de grupo, marcar grupo_corrigido.

  'LUVA'
      EPI01  PDM070  LUVA SEGURANCA   (EPI)
      TUB01  PDM050  BUCHA REDUCAO   (TUBOS E CONEXOES)


================================================================================================
RISCO D - NOME DE ATRIBUTO IGUAL COM ENUM DIFERENTE
================================================================================================
Os 93 nomes de atributo do PDM sao GLOBAIS. O mesmo nome tem listas de
valores diferentes em classes diferentes.
COMO RESOLVER: qualquer cache ou dicionario indexado por nome de atributo precisa
               validar o valor contra o enum DA CLASSE na leitura.

  MATERIAL  (17 classes, 15 listas diferentes)
      PDM001: ['ACO CARBONO', 'ACO INOX 304', 'ACO INOX 316']
      PDM002: ['ACO INOX 304', 'ACO INOX 316', 'ACO LIGA']
      PDM003: ['ACO CARBONO', 'ACO INOX 304', 'ACO INOX 316']
      PDM004: ['ACO CARBONO', 'ACO INOX 304', 'ACO INOX 316']
      ... e mais 13 classes

  TIPO  (14 classes, 14 listas diferentes)
      PDM003: ['AUTOTRAVANTE', 'CASTELO', 'SEXTAVADA', 'SEXTAVADA FLANGEADA']
      PDM023: ['PEDESTAL COM ROLAMENTO']
      PDM032: ['B1', 'BA', 'BAB', 'BASL']
      PDM043: ['ESFERA', 'PISTAO', 'PORTINHOLA']
      ... e mais 10 classes

  NORMA  (10 classes, 9 listas diferentes)
      PDM001: ['ASME B18.2.1', 'DIN 931', 'DIN 933']
      PDM003: ['DIN 6923', 'DIN 934', 'DIN 935', 'DIN 985']
      PDM004: ['DIN 125', 'DIN 9021']
      PDM005: ['DIN 127']
      ... e mais 6 classes

  APLICACAO  (6 classes, 6 listas diferentes)
      PDM012: ['AGUA', 'AR COMPRIMIDO', 'COMBUSTIVEL', 'MULTIUSO', 'OLEO']...
      PDM014: ['DESCARGA', 'SUCCAO', 'SUCCAO E DESCARGA']
      PDM081: ['ACO CARBONO', 'ACO CARBONO E INOX', 'ACO INOX']
      PDM090: ['COMPRESSOR', 'ENGRENAGEM', 'HIDRAULICO', 'MOTOR DIESEL', 'TURBINA']
      ... e mais 2 classes

  BITOLA  (4 classes, 4 listas diferentes)
      PDM001: ['M6', 'M8', 'M10', 'M12', 'M14']...
      PDM002: ['M3', 'M4', 'M5', 'M6', 'M8']...
      PDM003: ['M6', 'M8', 'M10', 'M12', 'M14']...
      PDM006: ['M6', 'M8', 'M10', 'M12', 'M16']...

  CLASSE RESISTENCIA  (4 classes, 4 listas diferentes)
      PDM001: ['10.9', '5.8', '8.8', 'A2-70', 'A4-70']...
      PDM002: ['12.9', 'A2-70', 'A4-70']
      PDM003: ['10', '5', '8', 'A2-70', 'A4-70']
      PDM006: ['4.8', '8.8', 'A2-70']

  ACABAMENTO  (6 classes, 4 listas diferentes)
      PDM001: ['GALVANIZADO A FOGO', 'NATURAL', 'ORGANOMETALICO', 'OXIDADO PRETO', 'SEM ACABAMENTO']...
      PDM002: ['NATURAL', 'OXIDADO PRETO', 'ZINCADO BRANCO']
      PDM003: ['GALVANIZADO A FOGO', 'NATURAL', 'ORGANOMETALICO', 'OXIDADO PRETO', 'SEM ACABAMENTO']...
      PDM004: ['GALVANIZADO A FOGO', 'NATURAL', 'ORGANOMETALICO', 'OXIDADO PRETO', 'SEM ACABAMENTO']...
      ... e mais 2 classes

  CLASSE PRESSAO  (7 classes, 4 listas diferentes)
      PDM033: ['150#', '1500#', '300#', '600#', '900#']
      PDM034: ['150#', '300#']
      PDM040: ['150#', '300#', '600#', '800#', 'PN 16']...
      PDM041: ['150#', '300#', '600#', '800#', 'PN 16']...
      ... e mais 3 classes

  CONEXAO  (7 classes, 4 listas diferentes)
      PDM040: ['FLANGE FF', 'FLANGE RF', 'ROSCA BSP', 'ROSCA NPT', 'SOLDA ENCAIXE SW']...
      PDM041: ['FLANGE FF', 'FLANGE RF', 'ROSCA BSP', 'ROSCA NPT', 'SOLDA ENCAIXE SW']...
      PDM042: ['FLANGE FF', 'FLANGE RF', 'ROSCA BSP', 'ROSCA NPT', 'SOLDA ENCAIXE SW']...
      PDM043: ['FLANGE FF', 'FLANGE RF', 'ROSCA BSP', 'ROSCA NPT', 'SOLDA ENCAIXE SW']...
      ... e mais 3 classes

  ACIONAMENTO  (4 classes, 4 listas diferentes)
      PDM040: ['ALAVANCA', 'ATUADOR PNEUMATICO', 'REDUTOR']
      PDM041: ['REDUTOR', 'VOLANTE']
      PDM042: ['VOLANTE']
      PDM044: ['ALAVANCA', 'ATUADOR ELETRICO', 'ATUADOR PNEUMATICO', 'REDUTOR']

  COR  (3 classes, 3 listas diferentes)
      PDM013: ['AMARELA', 'AZUL', 'CRISTAL', 'PRETA', 'VERMELHA']
      PDM060: ['AZUL', 'BRANCO', 'CINZA', 'PRETO', 'VERDE']...
      PDM071: ['MARROM', 'PRETA']

  TAMANHO  (3 classes, 3 listas diferentes)
      PDM064: ['10X38MM', '14X51MM', '22X58MM', 'D II', 'D III']...
      PDM070: ['7', '8', '9', '10', '11']...
      PDM071: ['34', '35', '36', '37', '38']...

  ROSCA  (2 classes, 2 listas diferentes)
      PDM001: ['METRICA FINA', 'METRICA GROSSA', 'UNC', 'UNF']
      PDM003: ['METRICA FINA', 'METRICA GROSSA']

  REFORCO  (2 classes, 2 listas diferentes)
      PDM010: ['1 TRAMA ACO', '2 TRAMAS ACO', '4 ESPIRAIS ACO']
      PDM012: ['ESPIRAL ACO + LONAS TEXTEIS', 'LONAS TEXTEIS']

  FURO  (2 classes, 2 listas diferentes)
      PDM021: ['CILINDRICO', 'CONICO']
      PDM061: ['M3', 'M4', 'M5', 'M6', 'M8']...

  REFERENCIA  (2 classes, 2 listas diferentes)
      PDM022: ['30203', '30204', '30205', '30206', '30207']...
      PDM023: ['UCP204', 'UCP205', 'UCP206', 'UCP207', 'UCP208']...

  MATERIAL CAIXA  (2 classes, 2 listas diferentes)
      PDM023: ['FERRO FUNDIDO']
      PDM067: ['ACO CARBONO', 'ACO INOX 304']

  ENCHIMENTO  (2 classes, 2 listas diferentes)
      PDM033: ['GRAFITE FLEXIVEL', 'PTFE']
      PDM067: ['GLICERINA', 'SECO']

  MATERIAL CORPO  (5 classes, 2 listas diferentes)
      PDM040: ['ACO CARBONO FORJADO A105', 'ACO CARBONO FUNDIDO A216 WCB', 'ACO INOX FORJADO A182 F316', 'ACO INOX FUNDIDO A351 CF8M', 'FERRO FUNDIDO NODULAR']...
      PDM041: ['ACO CARBONO FORJADO A105', 'ACO CARBONO FUNDIDO A216 WCB', 'ACO INOX FORJADO A182 F316', 'ACO INOX FUNDIDO A351 CF8M', 'FERRO FUNDIDO NODULAR']...
      PDM042: ['ACO CARBONO FORJADO A105', 'ACO CARBONO FUNDIDO A216 WCB', 'ACO INOX FORJADO A182 F316', 'ACO INOX FUNDIDO A351 CF8M', 'FERRO FUNDIDO NODULAR']...
      PDM043: ['ACO CARBONO FORJADO A105', 'ACO CARBONO FUNDIDO A216 WCB', 'ACO INOX FORJADO A182 F316', 'ACO INOX FUNDIDO A351 CF8M', 'FERRO FUNDIDO NODULAR']...
      ... e mais 1 classes

  VEDACAO SEDE  (2 classes, 2 listas diferentes)
      PDM040: ['METAL-METAL', 'PTFE', 'RPTFE']
      PDM044: ['EPDM', 'NBR', 'PTFE']

  SCHEDULE  (2 classes, 2 listas diferentes)
      PDM050: ['SCH 10S', 'SCH 40', 'SCH 40S', 'SCH 80']
      PDM051: ['CLASSE MEDIA', 'SCH 10S', 'SCH 160', 'SCH 40', 'SCH 40S']...

  TENSAO  (2 classes, 2 listas diferentes)
      PDM065: ['220V', 'BIVOLT']
      PDM066: ['10-30VCC']

  FABRICANTE  (2 classes, 2 listas diferentes)
      PDM100: ['BALDWIN', 'CATERPILLAR', 'DONALDSON', 'FLEETGUARD', 'FRAM']...
      PDM110: ['ATLAS COPCO', 'CATERPILLAR', 'CONTINENTAL', 'EPIROC', 'FLENDER']...


================================================================================================
RISCO E - CLASSES COM OS MESMOS ATRIBUTOS OBRIGATORIOS
================================================================================================
Duas classes cujas caixas obrigatorias coincidem nao podem ser
distinguidas por evidencia de caixa - so pelo nome.
COMO RESOLVER: se o nome nao resolver, nao ha sinal estrutural: precisa de LLM ou
               de decisao humana.

  nenhum caso.

================================================================================================
RISCO F - VALOR DE ENUM QUE E SUBCADEIA DE OUTRO
================================================================================================
Procurar 'INOX 316' no texto casa tambem dentro de 'ACO INOX 316'.
Sem casamento mais longo, o gazetteer escolhe o errado ou acusa ambiguidade.
COMO RESOLVER: regras._por_gazetteer ordena por tamanho e descarta o que e subcadeia
               de um casamento maior.

  PDM003 TIPO                   'SEXTAVADA' dentro de 'SEXTAVADA FLANGEADA'
  PDM010 MATERIAL COBERTURA     'BORRACHA SINTETICA' dentro de 'BORRACHA SINTETICA ANTIABRASAO'
  PDM012 REFORCO                'ESPIRAL ACO + LONAS TEXTEIS' dentro de 'LONAS TEXTEIS'
  PDM014 APLICACAO              'DESCARGA' dentro de 'SUCCAO E DESCARGA'
  PDM014 APLICACAO              'SUCCAO' dentro de 'SUCCAO E DESCARGA'
  PDM030 PERFIL                 'A' dentro de 'A DENTADA'
  PDM030 PERFIL                 'B' dentro de 'B DENTADA'
  PDM064 TIPO                   'NH' dentro de 'ULTRARRAPIDO NH'
  PDM066 MONTAGEM               'FACEADO' dentro de 'NAO FACEADO'
  PDM072 TRATAMENTO             'ANTIEMBACANTE' dentro de 'ANTIEMBACANTE E ANTIRRISCO'
  PDM072 TRATAMENTO             'ANTIEMBACANTE E ANTIRRISCO' dentro de 'ANTIRRISCO'
  PDM081 APLICACAO              'ACO CARBONO' dentro de 'ACO CARBONO E INOX'
  PDM082 TIPO                   'HSS' dentro de 'HSS COBALTO'
  PDM110 MATERIAL               'BORRACHA' dentro de 'BORRACHA NATURAL'
  ... e mais 2 pares

================================================================================================
RISCO G - VALORES GEMEOS NUMERICOS NO MESMO ENUM
================================================================================================
Valores que diferem SO por numero. Medido: cos(ACO INOX 304, ACO INOX 316)
= 0,963 - o embedding nao os separa, e confundi-los cria item errado.
COMO RESOLVER: caixas.classificar_banda tem trava: se 1o e 2o colocados sao gemeos
               numericos, o embedding nunca decide, vai para o LLM.

  PDM001 BITOLA                 134 par(es), ex.: 'M6' x 'M8'
  PDM001 CLASSE RESISTENCIA     7 par(es), ex.: '10.9' x '5.8'
  PDM001 MATERIAL               1 par(es), ex.: 'ACO INOX 304' x 'ACO INOX 316'
  PDM001 NORMA                  1 par(es), ex.: 'DIN 931' x 'DIN 933'
  PDM002 BITOLA                 45 par(es), ex.: 'M3' x 'M4'
  PDM002 CLASSE RESISTENCIA     1 par(es), ex.: 'A2-70' x 'A4-70'
  PDM002 MATERIAL               1 par(es), ex.: 'ACO INOX 304' x 'ACO INOX 316'
  PDM003 BITOLA                 105 par(es), ex.: 'M6' x 'M8'
  PDM003 CLASSE RESISTENCIA     4 par(es), ex.: '10' x '5'
  PDM003 MATERIAL               1 par(es), ex.: 'ACO INOX 304' x 'ACO INOX 316'
  PDM003 NORMA                  6 par(es), ex.: 'DIN 6923' x 'DIN 934'
  PDM004 MATERIAL               1 par(es), ex.: 'ACO INOX 304' x 'ACO INOX 316'
  PDM004 NORMA                  1 par(es), ex.: 'DIN 125' x 'DIN 9021'
  PDM004 PARA PARAFUSO          78 par(es), ex.: 'M6' x 'M8'
  PDM005 MATERIAL               1 par(es), ex.: 'ACO INOX 304' x 'ACO INOX 316'
  PDM005 PARA PARAFUSO          78 par(es), ex.: 'M6' x 'M8'
  ... e mais 40 atributos

================================================================================================
RESUMO
================================================================================================
  A      2  mesmo substantivo, qualificador superconjunto
  B     21  mesmo substantivo, qualificadores disjuntos
  C      1  substantivo compartilhado entre grupos
  D     23  nome de atributo com enum diferente por classe
  E      0  classes com os mesmos atributos obrigatorios
  F     16  valor de enum subcadeia de outro
  G   1146  valores gemeos numericos no mesmo enum
```
