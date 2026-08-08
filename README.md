# O Versículo Diário

Automação que publica um versículo bíblico por dia no Instagram
[@oversiculo.diario](https://instagram.com/oversiculo.diario): escolhe o versículo,
renderiza a imagem 1080×1080, escreve a legenda com a API do Claude e publica pela
Graph API da Meta. Roda no GitHub Actions — sem servidor, sem custo, sem cartão.

## O que roda todo dia

```
cron 11:00 UTC (08:00 Brasília)
  └─ escolhe o versículo (sem repetir enquanto houver inédito)
  └─ renderiza posts/AAAA-MM-DD.jpg
  └─ escreve a legenda (Claude; cai num texto padrão se faltar chave)
  └─ commita a imagem no repositório          ← precisa vir antes de publicar
  └─ publica no Instagram usando a URL crua do commit
  └─ registra em dados/historico.json
```

## Por que GitHub Actions e não Cloud Functions

O plano original era Firebase. GitHub Actions sai na frente em três pontos: o cron
é nativo, não exige o plano Blaze (ou seja, nenhum cartão de crédito cadastrado) e
o próprio repositório resolve a hospedagem da imagem, que a Graph API exige em URL
pública. Migrar para Firebase depois é troca de invólucro — a lógica em `src/` não
muda.

**Consequência:** o repositório precisa ser **público**. É o que faz
`raw.githubusercontent.com` servir a imagem sem autenticação; num repositório privado
o Instagram recebe um pedido de login e a publicação falha. As credenciais não
ficam no repositório — vivem em *Secrets*, que são cifrados e não aparecem nem em
fork nem em pull request.

## Instalar

Para a configuração inicial completa, do zero até postar sozinho, siga
[PASSO-A-PASSO.md](PASSO-A-PASSO.md). O resumo abaixo assume que você já tem o
token e o Account ID da Meta em mãos.

### 1. Criar o repositório (público)

```bash
cd ~/oversiculo-diario
gh repo create oversiculo-diario --public --source=. --remote=origin --push
```

### 2. Cadastrar os secrets

Em **Settings → Secrets and variables → Actions → New repository secret**, ou pelo
terminal:

```bash
gh secret set IG_ACCESS_TOKEN     # token de longa duração da Meta
gh secret set IG_ACCOUNT_ID       # ID numérico da conta profissional
gh secret set ANTHROPIC_API_KEY   # opcional; sem ele a legenda usa o texto padrão
```

| Secret | Onde obter | Obrigatório |
|---|---|---|
| `IG_ACCESS_TOKEN` | Meta for Developers → app → Instagram → API setup with Instagram login | sim |
| `IG_ACCOUNT_ID` | mesmo painel, ao lado da conta conectada | sim |
| `ANTHROPIC_API_KEY` | console.anthropic.com | não |

Permissões necessárias no token: `instagram_business_basic` e
`instagram_business_content_publish`. Com o app em modo de desenvolvimento e
publicando só na própria conta, não é preciso passar pelo App Review.

### 3. Testar sem publicar

Em **Actions → Publicar versículo do dia → Run workflow**, marque **ensaio**. Ele
gera imagem e legenda, anexa como artefato e não posta nada. Confira o resultado
antes de deixar o cron solto.

## Rodar na mão

```bash
pip install -r requirements.txt
python3 -m src.principal --fase ensaio     # gera em posts/, não publica
```

## Estrutura

```
src/
  versiculos.py   escolha do dia + histórico
  imagem.py       render 1080x1080
  legenda.py      Claude com queda para texto padrão
  instagram.py    Graph API (container → espera → publica)
  principal.py    orquestra as duas fases
dados/
  versiculos.json pool com o texto já embutido
  historico.json  o que já foi publicado
ferramentas/
  montar_pool.py  busca os textos na bible-api (rodar só ao ampliar o pool)
fontes/           EB Garamond e Cinzel (OFL, licenças incluídas)
posts/            imagens e legendas geradas
```

## Decisões que valem saber

**O texto dos versículos está no repositório, não é buscado todo dia.** A
`bible-api.com` limita requisições em rajada (HTTP 429 por volta da 15ª). Um post
por dia caberia, mas não há motivo para a rotina depender de um serviço externo.
A tradução de Almeida usada é **domínio público**, então guardar o texto é
legítimo — publicar diariamente uma tradução protegida não seria.

**A rotina tem duas fases porque a Graph API baixa a imagem de uma URL.** O
arquivo precisa estar commitado e publicado antes de a publicação ser chamada.
Por isso `preparar` e `publicar` são etapas separadas, com o commit no meio.

**A imagem sai em JPEG, não PNG.** A Graph API aceita **apenas** JPEG para
publicação de imagem — mandar PNG falha. O subsampling é desligado (4:4:4)
porque o padrão borra o dourado fino da moldura sobre o fundo azul.

**A URL da imagem aponta para o SHA do commit, não para o branch.** O raw do
GitHub tem cache por referência; apontar para `main` logo após o push pode servir
a versão anterior ou um 404, e o Instagram falha sem dizer por quê.

**O sorteio é semeado pela data.** Rodar duas vezes no mesmo dia — um retry do
workflow, por exemplo — escolhe o mesmo versículo em vez de queimar outro do pool.

**A legenda nunca derruba o post.** Sem chave, com erro de rede, com JSON
inesperado ou com recusa dos classificadores, cai num texto padrão e segue. Numa
rotina que roda sem ninguém olhando, perder a legenda boa é melhor que perder o
post.

## Manutenção

**O token se renova sozinho.** O workflow `renovar-token.yml` roda toda segunda,
chama o endpoint de renovação do Instagram e regrava o secret `IG_ACCESS_TOKEN`
com um token novo de 60 dias. Como renova semanalmente, o token nunca chega perto
de vencer — nenhuma ação manual é necessária.

Isso exige um secret a mais: `GH_PAT`, um token de acesso pessoal do GitHub
(fine-grained) com permissão de **escrever secrets** só neste repositório. É o
único jeito de um workflow reescrever o próprio cofre, e como o repositório é
público o token do Instagram não pode ficar em arquivo. Se o `GH_PAT` não existir,
a renovação falha e o token volta a expirar em 60 dias — aí é renová-lo à mão pelo
caminho do `PASSO-A-PASSO.md`.

**Ampliar o pool de versículos:** acrescente as referências em
`ferramentas/montar_pool.py` e rode `python3 ferramentas/montar_pool.py`. Ele só
busca o que falta e avisa quais textos passam de 260 caracteres (ainda cabem — a
fonte encolhe sozinha — mas vale conferir o enquadramento).

**Quando o pool esgota**, a escolha reabre pelos versículos publicados há mais
tempo, em vez de travar.
