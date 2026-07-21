# RockFeed RJ 🎸

Microserviço que varre sites de venda de ingressos, filtra shows de **rock no estado do Rio de Janeiro** (capital e interior — Volta Redonda, Campos dos Goytacazes, Maricá etc., não só a cidade do Rio) e publica tudo como um **feed RSS** — pronto pra assinar no seu leitor (Feeder, NewsBlur, Miniflux, etc).

## Como funciona

```
scrapers (Sympla, Eventim, Articket, Meaple, Bileto, Shotgun,
          uTicket, Clube do Ingresso, Uhuu)
   → filtro de rock (keywords/categoria própria do site, conforme a fonte)
   → SQLite (deduplicação por hash de fonte+URL)
   → /feed.xml (RSS 2.0)
```

O serviço roda os scrapers a cada 60 min (configurável em `app/main.py`, `REFRESH_MINUTES`). Cada evento novo vira um item do feed; eventos já vistos são ignorados, então o leitor RSS só te notifica de novidades. Shows cujo dia já passou saem do feed automaticamente.

## Instalação

```bash
cd ~/rockfeed-rj
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # navegador usado pelos scrapers da Shotgun e uTicket
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Feed em: `http://localhost:8000/feed.xml`

Endpoints úteis:
- `GET /feed.xml` — o feed RSS (suporta `ETag`/`304 Not Modified`)
- `GET /refresh` — força uma varredura agora (limitado a 1 vez a cada 5 min; bom pra testar scrapers)
- `GET /health` — status e contagem de eventos

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

## Assinando no leitor RSS

- **No próprio PC:** assine `http://localhost:8000/feed.xml`.
- **No celular (Pixel):** na mesma rede Wi-Fi, use `http://IP-DO-PC:8000/feed.xml` (troque `--host` para `0.0.0.0`). Ou use Tailscale para acessar de qualquer lugar sem expor porta.

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
