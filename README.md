# RockFeed RJ 🎸

Microserviço que varre sites de venda de ingressos, filtra shows de **rock no estado do Rio de Janeiro** (capital e interior — Volta Redonda, Campos dos Goytacazes, Maricá etc., não só a cidade do Rio) e publica tudo como um **feed RSS** — pronto pra assinar no seu leitor (Feeder, NewsBlur, Miniflux, etc).

## Como funciona

```
scrapers (Sympla, Eventim, Articket/Tomarock)
   → filtro de rock (keywords + blocklist)
   → SQLite (deduplicação por hash de fonte+URL)
   → /feed.xml (RSS 2.0)
```

O serviço roda os scrapers a cada 60 min (configurável em `app/main.py`, `REFRESH_MINUTES`). Cada evento novo vira um item do feed; eventos já vistos são ignorados, então o leitor RSS só te notifica de novidades.

## Instalação (Fedora)

```bash
cd ~/rockfeed-rj
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # baixa o navegador usado pelo scraper da Shotgun
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Feed em: `http://localhost:8000/feed.xml`

Endpoints úteis:
- `GET /feed.xml` — o feed RSS
- `GET /refresh` — força uma varredura agora (bom pra testar cada scraper)
- `GET /health` — status e contagem de eventos

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

## Adicionando/ajustando fontes

1. Crie `app/scrapers/novosite.py` herdando de `Scraper` e retornando `list[Event]`.
2. Registre a instância em `SCRAPERS` no `app/main.py`.
3. Páginas de produtoras na Articket: adicione em `PAGES` no `articket.py`.

Sites que valem adicionar depois: Ingresse, Ticket360, Bilheteria Digital, Ticketmaster BR, e agendas de casas como Circo Voador e Fundição Progresso.

## Avisos importantes

- Os endpoints/seletores dos sites **não são oficiais e mudam** — quando um scraper quebrar, abra o site com o DevTools (aba Network) e ajuste URL/seletores. O serviço continua funcionando com os outros scrapers.
- O filtro de rock está em `app/scrapers/base.py` (`ROCK_KEYWORDS` / `BLOCKLIST`) — ajuste ao seu gosto.
- Respeite os termos de uso e o `robots.txt` dos sites; o intervalo de 60 min é de propósito, pra não sobrecarregar ninguém.
