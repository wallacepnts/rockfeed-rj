# RockFeed RJ 🎸

Microserviço que varre sites de venda de ingressos, filtra shows de **rock no estado do Rio de Janeiro** (capital e interior — Volta Redonda, Campos dos Goytacazes, Maricá etc., não só a cidade do Rio) e publica tudo como um **feed RSS** — pronto pra assinar no seu leitor (Feeder, NewsBlur, Miniflux, etc). Também pode **enviar os eventos automaticamente pro [Revel](https://github.com/DuRockRJ/revel-backend)** (a plataforma de ingressos do DuRock RJ), como rascunho pra revisão manual.

## Como funciona

```
scrapers (Sympla, Eventim, Articket, Meaple, Bileto, Shotgun,
          uTicket, Clube do Ingresso, Uhuu)
   → filtro de rock (keywords/categoria própria do site, conforme a fonte)
   → SQLite (deduplicação por hash de fonte+URL)
   → /feed.xml (RSS 2.0)
   → Revel, via POST /api/external/events (opcional — ver "Envio automático pro Revel")
```

O serviço roda os scrapers a cada 60 min (configurável em `app/main.py`, `REFRESH_MINUTES`). Cada evento novo vira um item do feed; eventos já vistos são ignorados, então o leitor RSS só te notifica de novidades. Shows cujo dia já passou saem do feed automaticamente. Se o envio pro Revel estiver configurado, a mesma varredura também empurra os eventos pra lá.

## Instalação

```bash
cd ~/rockfeed-rj
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # navegador usado pelos scrapers da Shotgun e uTicket
uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Feed em: `http://localhost:8765/feed.xml`

Endpoints úteis:
- `GET /feed.xml` — o feed RSS (suporta `ETag`/`304 Not Modified`)
- `GET /events.json` — exportação estruturada dos eventos (campos separados: `venue`, `address`, `organizer`, `date`, `price` etc.), pra importação por outros sistemas — não é feito pra leitor RSS, é pra automação (ver `app/events_json.py`)
- `GET /refresh` — força uma varredura agora (limitado a 1 vez a cada 5 min; bom pra testar scrapers)
- `GET /health` — status e contagem de eventos

### Envio automático pro Revel

Além de servir `/events.json` passivamente, o serviço pode **enviar** os eventos pro Revel a
cada varredura (`app/revel_push.py`), via `POST /api/external/events`. Configure via
variáveis de ambiente (num arquivo `.env` na raiz do projeto — veja `EnvironmentFile=` em
`rockfeed.service`/`rockfeed-rj.container`, ou `environment:` no `docker-compose.yml`):

```bash
REVEL_INGEST_URL=https://api.revel.exemplo.com.br/api/external/events
REVEL_INGEST_API_KEY=<o mesmo valor de EXTERNAL_INGEST_API_KEY configurado no Revel>
```

Se qualquer uma das duas faltar, o envio fica desabilitado silenciosamente — útil pra rodar
localmente sem o Revel. O envio nunca bloqueia nem derruba a varredura: se o Revel estiver
fora do ar (ele roda intermitente, ao contrário do RockFeed), a falha só é logada e a próxima
varredura (60 min) tenta de novo com os dados atualizados — sem retry.

**O que acontece do lado do Revel** (endpoint implementado em `revel-backend`, app `events`):

- Cada evento vira um `Event` com `status=DRAFT` — nada é publicado automaticamente, um admin
  revisa e publica manualmente depois.
- Dedup pelo `uid` (o mesmo hash de `source|url` usado aqui) — reenviar o mesmo evento
  atualiza o rascunho existente em vez de duplicar. Uma vez publicado (qualquer status além
  de `DRAFT`), o Revel para de tocar naquele evento — reenvios subsequentes são ignorados.
- O `organizer` vira uma `Organization` (criada automaticamente se não existir; eventos sem
  organizador caem numa organização "Não classificado" pra classificar manualmente depois).
  Uma vez atribuída, a organização não é mais trocada em reenvios futuros.
- É criado um ingresso do tipo "externo", apontando pra `url` do evento original (Sympla,
  Eventim, etc.), com o `price` quando disponível.
- A `image` é baixada e usada como capa do evento (assíncrono, não atrasa o envio) — aceita
  paisagem, retrato ou quadrada, mas descarta imagens pequenas demais (logos, placeholders
  1x1), pra não virar capa feia.
- Títulos que vierem TODO EM MAIÚSCULA são normalizados pra Title Case; do contrário ficam como vieram.

### Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes cobrem o parsing de cada scraper, o filtro de rock, dedup, escaping/filtro do feed e os endpoints — todos com mocks, sem bater na rede real. Pra validar contra os sites de verdade, use `/refresh` e acompanhe os logs (cada scraper loga "N eventos, M novos").

## Rodar como serviço (systemd user)

```bash
mkdir -p ~/.config/systemd/user
cp rockfeed.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now rockfeed
loginctl enable-linger $USER   # continua rodando sem sessão aberta
```

## Rodar com Docker/Podman

```bash
docker compose up -d --build
# ou, com Podman:
podman compose up -d --build
```

O `docker-compose.yml` expõe a porta 8765 e mapeia `./app/data` como volume, pra o banco SQLite sobreviver a rebuilds do container. A imagem já inclui o Chromium (usado pelos scrapers da Shotgun e uTicket) — o build demora um pouco mais por causa disso (baixa ~300MB), mas só na primeira vez.

Sem compose, direto:

```bash
docker build -t rockfeed-rj .
docker run -d -p 8765:8765 -v ./app/data:/app/data:Z --name rockfeed-rj rockfeed-rj
```

### Versionamento da imagem

A versão atual fica no arquivo `VERSION` (semver). Pra buildar já gerando a tag de versão **e** `latest` de uma vez:

```bash
./scripts/build-image.sh          # usa podman
./scripts/build-image.sh docker   # ou docker
```

Isso gera `rockfeed-rj:0.1.0`, `rockfeed-rj:latest` e as mesmas tags com o prefixo `ghcr.io/wallacepnts/rockfeed-rj` (usadas pelo Quadlet, veja abaixo). Pra lançar uma nova versão: edite o `VERSION`, rode o script de novo, publique no GHCR (`./scripts/push-image.sh`) e o `podman-auto-update.timer` cuida do resto.

> O script builda com `--format docker` quando usa Podman — por padrão o Podman gera imagens em formato OCI, que **não suporta `HEALTHCHECK`** (fica silenciosamente ignorado). Se preferir buildar com `podman compose`/`docker compose` em vez do script, o healthcheck não funciona, mas o resto do serviço roda normalmente.

A imagem também expõe um `HEALTHCHECK` (`GET /health` a cada 30s) — usado tanto pelo `podman ps`/`docker ps` (coluna `STATUS`) quanto pelo auto-update do Podman pra decidir se um container "subiu saudável" depois de atualizar.

### Auto-update com Podman + Quadlet + GHCR

A imagem é publicada no GitHub Container Registry (`ghcr.io/wallacepnts/rockfeed-rj`). Login (uma vez só; precisa de um [Personal Access Token](https://github.com/settings/tokens) com escopo `write:packages`):

```bash
echo "$SEU_TOKEN" | podman login ghcr.io -u wallacepnts --password-stdin
```

Build + publish de uma nova versão:

```bash
./scripts/build-image.sh
./scripts/push-image.sh
```

Com o Podman rodando o container via [Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html) (unidades systemd geradas automaticamente a partir de arquivos `.container`):

```bash
mkdir -p ~/.config/containers/systemd
cp rockfeed-rj.container ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user enable --now rockfeed-rj.service

# habilita o timer que checa/reinicia containers com imagem atualizada no registry
systemctl --user enable --now podman-auto-update.timer
```

O `AutoUpdate=registry` no `rockfeed-rj.container` faz o `podman-auto-update.timer` (roda diariamente por padrão) checar `ghcr.io/wallacepnts/rockfeed-rj:latest` periodicamente; quando o digest publicado muda (após um `push-image.sh`), o Podman baixa a imagem nova e reinicia o container sozinho. O healthcheck (`HealthCmd`/`HealthInterval`/... no próprio `.container`, batendo em `/health`) decide se a atualização "pegou" — se o container novo não ficar saudável dentro do `HealthStartPeriod`, o Podman reverte pra imagem anterior automaticamente. O `Notify=healthy` faz o systemd só considerar o serviço "ativo" depois do primeiro healthcheck passar.

Se o pacote no GHCR ficar privado (padrão no primeiro push), o `podman login` precisa continuar válido na máquina que roda o auto-update — o token fica salvo em `~/.config/containers/auth.json`.

Ajuste o caminho do volume em `rockfeed-rj.container` (`%h/rockfeed-rj/app/data`) se o repositório estiver clonado em outro lugar.

## Assinando no leitor RSS

- **No próprio PC:** assine `http://localhost:8765/feed.xml`.
- **No celular (Pixel):** na mesma rede Wi-Fi, use `http://IP-DO-PC:8765/feed.xml` (troque `--host` para `0.0.0.0`). Ou use Tailscale para acessar de qualquer lugar sem expor porta.

## Fontes

| Site | Como descobre eventos novos | Observação |
|---|---|---|
| **Sympla** | Automática, por produtor rastreado (`ORGANIZERS` em `sympla.py`) + lista avulsa (`EVENTS`) | API pública de busca; eventos avulsos usam a página do próprio evento |
| **Eventim** | Automática — busca por categoria "Rock" + estado RJ, sem lista curada | Via [`pyventim`](https://pypi.org/project/pyventim/), que usa a API pública da Eventim |
| **Articket** | Automática, por produtora rastreada (`PAGES` em `articket.py`) | Cada evento traz dados estruturados (JSON-LD) |
| **Meaple** | Automática, por canal/bar rastreado (`CHANNELS` em `meaple.py`) | API pública de canais |
| **Bileto** | Só lista avulsa (`EVENTS` em `bileto.py`) | Plataforma legada da Sympla; não existe listagem por produtor |
| **Shotgun** | Automática, por local rastreado (`VENUES` em `shotgun.py`) | Site protegido por desafio Vercel — usa navegador real (Playwright) |
| **uTicket** | Automática, por produtor rastreado (`ORGANIZERS`) + lista avulsa (`EVENTS`) | Site protegido por Cloudflare — usa navegador real (Playwright) |
| **Clube do Ingresso** | Só lista avulsa (`EVENTS` em `clubedoingresso.py`) | Sem página de produtor; a listagem geral do site é nacional e não dá pra filtrar por cidade/gênero |
| **Uhuu** | Só lista avulsa (`EVENTS` em `uhuu.py`) | Sem página de produtor nem listagem filtrável |

"Automática" significa que, uma vez que um produtor/canal/local está na lista rastreada, novos shows dele aparecem sozinhos nas próximas varreduras — sem precisar mexer no código. Fontes "só lista avulsa" exigem adicionar o link de cada show manualmente.

### Adicionando uma fonte nova

1. Crie `app/scrapers/novosite.py` herdando de `Scraper` (`app/scrapers/base.py`) e implementando `fetch() -> list[Event]`.
2. Registre a instância em `SCRAPERS` no `app/main.py`.
3. Se o site bloquear requisições HTTP simples (Cloudflare, Vercel etc.), use `app/scrapers/browser.py` (Playwright) — mas só nesse caso; é bem mais pesado.

Sites que valem adicionar depois: Ingresse, Ticket360, Bilheteria Digital, Ticketmaster BR, e agendas de casas como Fundição Progresso.

## Avisos importantes

- Os endpoints/seletores dos sites **não são oficiais e mudam** — quando um scraper quebrar, abra o site com o DevTools (aba Network) e ajuste URL/seletores. O serviço continua funcionando com os outros scrapers (uma falha isolada não derruba os outros).
- O filtro de rock por keyword está em `app/scrapers/base.py` (`ROCK_KEYWORDS` / `BLOCKLIST`) — usado pelas fontes sem categorização própria. Ajuste ao seu gosto.
- Respeite os termos de uso e o `robots.txt` dos sites; o intervalo de 60 min é de propósito, pra não sobrecarregar ninguém.
- Shotgun e uTicket usam Playwright (Chromium headless) por estarem atrás de proteção anti-bot — isso deixa a varredura completa mais lenta (alguns minutos, contra segundos das fontes só-HTTP). Normal e esperado.
