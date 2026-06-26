# Story Engine — Canal Humanos Primitivos (versão web)

Versão web do `gerar_prompt.py`: mesma lógica de geração (limite de anáfora,
distribuição de blocos, anti-repetição de arquétipos/casos, Video DNA do
título), só que rodando no navegador e salvando tudo no Firestore — assim
você acessa de qualquer computador e nada fica só na sua máquina.

Arquivos deste projeto:

```
index.html          → a página (login, gerar, bancos, histórico)
style.css           → visual
app.js              → toda a lógica (Firebase + motor de geração)
template.js         → o prompt-template gigante, portado fielmente do .py
firestore.rules     → regra de segurança do banco de dados
```

Nenhum desses arquivos contém senha ou chave secreta de verdade — você
mesmo vai colar a configuração do seu projeto Firebase dentro do `app.js`
(veja o Passo 2). Isso é normal e seguro: quem protege seus dados são as
**Regras do Firestore** + o **login obrigatório**, não o segredo da
configuração.

---

## Passo 1 — Criar o projeto no Firebase

1. Acesse https://console.firebase.google.com e crie um projeto novo
   (pode desativar o Google Analytics, não é necessário).
2. Dentro do projeto, clique no ícone **`</>`** ("Adicionar app" → Web) e
   registre um app (qualquer apelido, ex.: `storyengine-web`). Você **não**
   precisa marcar Firebase Hosting — vamos usar o GitHub Pages.
3. O Firebase vai te mostrar um objeto `firebaseConfig` parecido com:
   ```js
   const firebaseConfig = {
     apiKey: "AIza...",
     authDomain: "seu-projeto.firebaseapp.com",
     projectId: "seu-projeto",
     storageBucket: "seu-projeto.appspot.com",
     messagingSenderId: "123...",
     appId: "1:123...",
   };
   ```
   Guarde esse bloco — você vai colá-lo no Passo 4.

## Passo 2 — Ativar o Firestore (o banco de dados)

1. No menu lateral: **Build → Firestore Database → Create database**.
2. Escolha uma localização (qualquer região próxima de você serve).
3. Comece em **modo produção** (vamos colar nossas próprias regras a seguir).
4. Vá na aba **Rules** dentro do Firestore e cole o conteúdo do arquivo
   `firestore.rules` deste projeto, substituindo o que já está lá.
   Clique em **Publish**.

## Passo 3 — Ativar login com Google (Authentication)

1. Menu lateral: **Build → Authentication → Get started** (se ainda não tiver feito).
2. Na aba **Sign-in method**, ative o provedor **Google** (não Email/Password).
   Ao ativar, ele pede um "e-mail de suporte do projeto" — pode usar o seu
   mesmo e-mail.
3. Ainda em Authentication, vá na aba **Settings → Authorized domains** e
   clique em **Add domain**. Adicione o domínio do seu GitHub Pages, por
   exemplo: `lucaspires0690.github.io` (sem `https://`, sem barra no final).
   Sem esse passo, o login com Google **não funciona** fora do
   `localhost` — é um erro comum, então não pule essa parte.

O app está travado para aceitar login **apenas** do e-mail
`lucasserip1990@gmail.com` — isso está em dois lugares: na regra do
Firestore (`firestore.rules`, é a proteção real) e no `app.js` (que
desloga automaticamente qualquer outra conta Google, por clareza). Se um
dia você quiser trocar ou adicionar outro e-mail autorizado, edite os dois
arquivos.

## Passo 4 — Colar sua configuração no app.js

Abra `app.js` e substitua o bloco no topo do arquivo:

```js
const firebaseConfig = {
  apiKey: "COLE_AQUI_SUA_API_KEY",
  authDomain: "SEU_PROJETO.firebaseapp.com",
  projectId: "SEU_PROJETO",
  storageBucket: "SEU_PROJETO.appspot.com",
  messagingSenderId: "COLE_AQUI",
  appId: "COLE_AQUI",
};
```

pelo objeto real que o Firebase te deu no Passo 1.

## Passo 5 — Subir para o GitHub Pages

1. Crie um repositório novo no GitHub (pode ser privado).
2. Suba os 5 arquivos deste projeto (`index.html`, `style.css`, `app.js`,
   `template.js`, `firestore.rules`) para a raiz do repositório.
3. Vá em **Settings → Pages** do repositório.
4. Em "Build and deployment", escolha **Deploy from a branch**, branch
   `main`, pasta `/ (root)`. Salve.
5. Espere 1–2 minutos. O GitHub vai te dar uma URL do tipo
   `https://seu-usuario.github.io/seu-repositorio/`. Essa é a página que
   você vai acessar de qualquer computador.

## Passo 6 — Importar o que você já tinha localmente

Abra a URL, faça login com o usuário criado no Passo 3, e:

1. Vá na aba **Bancos** → seção "Importar pools.json existente" → escolha
   seu `pools.json` local → **Importar arquivo**. Isso substitui os bancos
   de arquétipos/casos pelo conteúdo do seu arquivo.
2. Vá na aba **Histórico** → seção "Importar historico_roteiros.json
   existente" → escolha seu `historico_roteiros.json` local → **Importar
   arquivo**. Isso acrescenta todos os roteiros já gerados ao banco novo.

Essas duas importações são **únicas** — depois disso, tudo passa a viver
no Firestore e você pode parar de depender dos arquivos locais (mas vale
guardar uma cópia de segurança deles por precaução, pelo menos por um
tempo).

## Uso no dia a dia

Depois de configurado, é só abrir a URL em qualquer computador, logar, e
usar normalmente:

1. **Gerar prompt**: digite o título e a duração desejada em minutos →
   clique em "Gerar prompt". O app calcula a quantidade de palavras
   sozinho (usando a configuração de "palavras por minuto" da tela —
   ajuste isso se você descobrir a média real do seu TTS). Copie o
   prompt e cole numa conversa nova do Claude.ai — ele já escreve o
   roteiro direto, sem perguntar nada.
2. **Mensagem de revisão**: depois que o Claude entregar o roteiro, copie
   essa segunda caixa (aparece junto com o prompt) e cole como uma nova
   mensagem na mesma conversa. Ela pede pro Claude revisar contagem de
   palavras, humor situacional e micro-histórias no texto que ele mesmo
   já escreveu.
3. **Formatar**: cole o roteiro final (com ou sem a revisão do passo 2)
   na aba Formatar e clique em "Formatar parágrafos". Isso garante,
   sem depender de IA, que nenhum parágrafo passe de 3 frases — útil
   pra narração em TTS.
4. **Bancos**: adicione/remova arquétipos e casos históricos quando quiser,
   de qualquer lugar.
5. **Histórico**: consulte os roteiros já gerados (estrutura usada, não o
   texto do roteiro em si — isso continua sendo gerado pelo Claude no chat).

## Sobre custos

O plano gratuito do Firebase (Spark) é bastante generoso para esse volume
de uso (uma pessoa gerando alguns roteiros por dia). É extremamente
improvável que esse projeto chegue a custar algo, mas vale acompanhar o
painel de uso no Firebase Console de vez em quando, por hábito.
