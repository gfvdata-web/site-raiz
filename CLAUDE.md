# CLAUDE.md — site-raiz

Página institucional de https://gfvdata.com/ (e www): "laboratório pessoal de tecnologia e dados".
Existe para o domínio ter conteúdo claro e ser **categorizado como Tecnologia** pelos filtros de
rede corporativa (Fortinet, Zscaler, Palo Alto etc.), que bloqueavam os *.gfvdata.com por serem
"novos/sem categoria".

- Página **só institucional**: não linkar os subdomínios (decisão do usuário em 2026-10-15).
- Sem JS, sem cookies, sem analytics, sem CDN externo (a CSP em `docs/_headers` proíbe).
- Contato: `contato@gfvdata.com` (Email Routing da Cloudflare → Gmail).
- Ao criar página nova em `docs/`, incluí-la no `docs/sitemap.xml`. Renovar o `Expires` do
  `docs/.well-known/security.txt` antes de vencer (o check avisa com 60 dias).
- Funcionalidade nova entra com teste em `tests/`. `bash scripts/check` roda no hook e no pre-commit.
- Push só com pedido do usuário.

Deploy: automático no push para `main` (`.github/workflows/deploy.yml` → `wrangler deploy` do Worker
de estáticos `site-raiz`, secret `CLOUDFLARE_API_TOKEN` → https://gfvdata.com/). À mão:
`npx --yes wrangler@4.150.0 deploy`. Depois, conferir no ar com o agente `site-checker`.
