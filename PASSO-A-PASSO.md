# Passo a passo — do zero até postar sozinho

Guia completo para deixar o **@oversiculo.diario** publicando um versículo por dia
sem intervenção. Uns 30 a 40 minutos, feitos uma única vez.

O código já está pronto. Tudo abaixo é credencial e configuração.

> **Os rótulos dos botões no painel da Meta mudam com frequência.** Descrevi os
> pontos de referência em vez de fingir precisão de clique. Se alguma tela não
> bater com o texto, procure pelo elemento descrito, não pelo nome exato.

---

## Etapa 1 — Conta do Instagram (5 min)

1. No app do Instagram, entre no **@oversiculo.diario**.
2. **Configurações → Tipo de conta e ferramentas → Mudar para conta profissional.**
3. Escolha **Criador** ou **Empresa** — tanto faz para a API.

**Não é preciso vincular Página do Facebook.** O caminho que vamos usar
("Instagram Login") dispensa. Se algum passo insistir em pedir Página, é sinal de
que você caiu no caminho antigo, via Facebook Login — volte e refaça a Etapa 2.

✅ Pronto quando o perfil aparece como profissional no próprio app.

---

## Etapa 2 — App no Meta for Developers (15 min)

Pode ser feito pelo Safari do iPhone; se a tela ficar apertada, ative
"Solicitar site para computador".

1. Acesse **developers.facebook.com** e entre com seu Facebook pessoal. Na
   primeira vez ele pede para confirmar e-mail ou telefone. Não tem custo.
2. **Meus Apps → Criar app.**
3. Na tela **Casos de uso**, marque **"Gerenciar mensagens e conteúdo no
   Instagram"** — o card com o ícone do Instagram, cuja descrição começa com
   "Publique posts".

   Cuidado com dois vizinhos parecidos que estão errados:
   - *"Gerenciar tudo na sua Página"* é a API de Páginas do Facebook e exigiria
     uma Página vinculada.
   - *"Autenticar e solicitar dados de usuários com o Login do Facebook"* é o
     caminho antigo do Instagram, que também exige Página.

   Ignore também o **"Outro"** no rodapé: está marcado como "going away soon" e
   joga você na experiência antiga.
4. Dê um nome qualquer ao app — `Versiculo Diario Bot` serve. Esse nome não
   aparece para ninguém.
5. Em **Empresa**, ele pede um portfólio empresarial. Se não tiver, crie na hora:
   é só um agrupamento administrativo e não muda nada no seu perfil.
6. Em **Requisitos**, resolva o que aparecer — costuma ser só confirmação de conta.

✅ Pronto quando você cai no **Painel** do app.

---

## Etapa 3 — Conectar a conta e gerar o token (10 min)

1. No painel, abra **"Personalizar o caso de uso"** (a primeira linha, na setinha
   à direita). Pelo menu lateral, o mesmo lugar é **Casos de uso**.
2. Procure a seção **API setup with Instagram login** (em português pode aparecer
   como "Configuração da API com login do Instagram").
3. Em **adicionar conta**, autorize com o **@oversiculo.diario**. Como sua Central
   de Contas já liga Instagram e Facebook, o fluxo tende a ser rápido.
4. Clique em **Gerar token**. Marque as duas permissões que a publicação exige:
   - `instagram_business_basic`
   - `instagram_business_content_publish`
5. **Copie o token.** Ele já é de longa duração — vale **60 dias**.
6. No mesmo painel, ao lado da conta conectada, copie o **número longo**: é o
   `IG_ACCOUNT_ID`.

**Ignore o card "Torne-se um Provedor de Tecnologia".** Isso só serve para enviar
o app à análise e acessar dados de terceiros. Publicando na própria conta, com o
app em modo de desenvolvimento, **não é preciso passar pelo App Review**.

⚠️ **Não cole o token em conversa nenhuma.** Ele dá controle de publicação da sua
conta. Guarde no gerenciador de senhas ou no app Notas com cadeado até a Etapa 5.

✅ Pronto quando você tem em mãos: **token** e **Account ID**.

---

## Etapa 4 — Chave do Claude (5 min, opcional)

1. **console.anthropic.com → API keys → Create key.**
2. Adicione uns poucos dólares de crédito.

Sem essa chave o sistema continua funcionando: a legenda cai num texto padrão em
vez de uma reflexão escrita na hora. Dá para adicionar depois, a qualquer momento,
sem mexer em mais nada.

---

## Etapa 5 — GitHub (5 min)

No terminal:

```bash
cd ~/oversiculo-diario
gh repo create oversiculo-diario --public --source=. --remote=origin --push
```

Depois, um comando por segredo. Cada um pede o valor no terminal e não grava em
arquivo nenhum:

```bash
gh secret set IG_ACCESS_TOKEN
gh secret set IG_ACCOUNT_ID
gh secret set ANTHROPIC_API_KEY   # pule se não fez a Etapa 4
```

**Por que público:** a Graph API precisa baixar a imagem de uma URL sem
autenticação, e é o `raw.githubusercontent.com` que faz isso. Num repositório
privado o Instagram recebe um pedido de login e a publicação falha. Ficam
visíveis só o código e as imagens publicadas — os secrets são cifrados e não
aparecem nem em fork nem em pull request.

---

## Etapa 6 — Ensaio antes de soltar (5 min)

1. No GitHub: **Actions → Publicar versículo do dia → Run workflow.**
2. Marque **ensaio** e confirme.
3. Ao terminar, baixe o artefato **post-do-dia** e confira a imagem e a legenda.

O ensaio gera tudo e **não publica nada**. Só depois de gostar do resultado, deixe
o cron correr sozinho.

Se quiser publicar de verdade na hora, rode de novo **sem** marcar ensaio.

---

## Depois disso

A rotina dispara todo dia às **11:00 UTC (8h de Brasília)**. Não precisa fazer
mais nada.

**A única manutenção é o token, que expira em ~60 dias.** A rotina confere a
validade a cada execução e emite um aviso no log do Actions quando faltam 7 dias
ou menos — o GitHub te manda e-mail. Aí é só repetir a Etapa 3 (passos 4 a 5) e
rodar `gh secret set IG_ACCESS_TOKEN` de novo.

---

## Se algo falhar

O log de cada execução fica em **Actions**, com as mensagens de erro em texto
claro. Os enganos mais prováveis:

| Sintoma | Causa provável |
|---|---|
| `faltam IG_ACCESS_TOKEN e/ou IG_ACCOUNT_ID` | secret não cadastrado, ou nome digitado diferente |
| erro de permissão ao publicar | token gerado sem `instagram_business_content_publish` |
| o Instagram não baixa a imagem | repositório privado |
| `container falhou` | imagem inacessível na URL, ou fora do formato JPEG |
| parou de postar de repente | token de 60 dias expirou |
