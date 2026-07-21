# CLAUDE.md — RockFeed RJ

Microserviço em Python que raspa sites de venda de ingressos, filtra shows de **rock no estado do Rio de Janeiro** (capital e interior — não só a cidade do Rio) e publica um feed **RSS 2.0** em `/feed.xml`, consumido por um leitor RSS.

## Arquitetura

```
app/
├── main.py            # FastAPI + loop de refresh em background (60 min)
├── models.py          # dataclass Event (formato normalizado) + uid p/ dedup
├── store.py           # SQLite em app/data/events.db, dedup por uid
├── feed.py            # gera o XML RSS a partir do store
└── scrapers/
    ├── base.py        # classe Scraper, cliente httpx, filtro is_rock(), strip_html()
    ├── browser.py      # Playwright (Chromium headless) p/ sites com anti-bot
    ├── sympla.py       # API de busca por organizer_id + eventos avulsos
    ├── eventim.py      # via pyventim (API pública), filtra categoria "Rock" + estado RJ
    ├── articket.py     # páginas de produtoras (JSON-LD por evento)
    ├── meaple.py       # API de canais/bares (ex: Macaco Caolho Rock Pub)
    ├── bileto.py       # API de eventos avulsos da plataforma legada da Sympla
    ├── shotgun.py      # via browser.py — site protegido por Vercel challenge
    ├── uticket.py      # via browser.py — site protegido por Cloudflare
    └── clubedoingresso.py  # HTML tradicional, sem bloqueio; só eventos avulsos
```

Fluxo: scrapers → `is_rock()` → `store.upsert()` (dedup por sha1 de `source|url`) → `feed.build_rss()`.

## Comandos

```bash
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium            # navegador usado pelo scraper da Shotgun
uvicorn app.main:app --port 8000       # servir
curl localhost:8000/refresh            # forçar varredura (testar scrapers)
curl localhost:8000/feed.xml           # ver o feed
curl localhost:8000/health             # contagem de eventos
```

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes cobrem `is_rock()`, dedup no store, escaping/filtro do feed e os endpoints de `main.py` — todos com mocks, sem rede real. Scrapers (HTTP/HTML real) ainda se validam manualmente com `/refresh` e checando os logs (cada scraper loga "N eventos, M novos").

## Convenções

- Todo scraper herda de `Scraper` (base.py), implementa `fetch() -> list[Event]` e é registrado na lista `SCRAPERS` em `main.py`.
- Scrapers devem ser tolerantes: exceções são capturadas em `run_scrapers()`, então um site fora do ar não derruba os outros. Não engula exceções dentro do scraper — deixe subir.
- Datas: usar `datetime` no campo `Event.date` quando o site fornecer; `None` é aceitável.
- URLs relativas devem ser convertidas em absolutas dentro do scraper.
- Filtro de gênero: ajustar `ROCK_KEYWORDS` / `BLOCKLIST` em `base.py`, nunca hardcodar filtros dentro de um scraper (exceto lógica específica do site).
- Páginas de produtoras da Articket entram em `PAGES` no `articket.py`, não como scraper novo.
- `browser.py` (Playwright) só deve ser usado quando o site bloqueia requisições HTTP simples mesmo com headers/cookies corretos (confirmado testando de fora do ambiente) — é bem mais pesado (baixa um Chromium, cada página demora segundos).

## Avisos

- Os endpoints/seletores são **não oficiais e quebram** quando os sites mudam. Ao consertar, inspecione o site com DevTools (aba Network) e atualize URL/params/seletores — mantenha o comentário no topo do arquivo indicando a página de referência.
- Não reduzir o intervalo de refresh (`REFRESH_MINUTES`) para menos de 30 min; respeitar robots.txt e não paralelizar requisições agressivamente contra o mesmo site.
- `app/data/` é gerado em runtime — nunca commitar o banco.
- O `uid` (sha1 de `source|url`) é a chave de dedup: mudar sua composição duplica todo o histórico do feed.
- `clubedoingresso.py` não tem descoberta automática: a página de evento mostra o organizador, mas não existe página de produtor, e a única listagem geral (`/categoria/3`, "Shows") traz ~450 eventos do Brasil inteiro, sem filtro de cidade/gênero — visitar todos pra achar os poucos do RJ seria desproporcional ao resto do projeto. Por enquanto essa fonte só funciona por lista curada (`EVENTS`); novos shows precisam ser adicionados manualmente.
- `eventim.py`: `www.eventim.com.br` bloqueia qualquer requisição direta (httpx, curl, Playwright com Chromium real — testado até com o navegador do sistema do usuário) no nível de rede/TLS, mesmo de dentro da rede residencial do usuário (confirmado — não é bloqueio de IP de datacenter). A saída foi a lib de terceiros `pyventim`, que usa a API pública de busca (`public-api.eventim.com`) — essa não tem esse bloqueio. Descoberta automática via categoria "Rock" + `search_term="rock"`, filtrando por `state == "RJ"`. Sem preço (exigiria o fetcher "privado" da lib, que abre um Chromium com patches anti-detecção via patchright/scrapling — funciona, mas é pesado, e o preço costuma vir vazio mesmo assim).
