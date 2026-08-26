# Deploy — Predicta (stack completa)

Sobe os 8 serviços (Postgres, TimescaleDB, Redis, ChromaDB, simulador OPC-UA,
backend, frontend) num único servidor via `docker-compose.prod.yml`.
Testado para **Oracle Cloud Always Free (ARM Ampere A1)**, mas serve para
qualquer VPS Linux x86/ARM (Hetzner, etc.) — as imagens são construídas na
própria máquina, então a arquitetura é resolvida sozinha.

---

## 1. Criar a VM (Oracle Always Free)

- **Shape:** `VM.Standard.A1.Flex` — **4 OCPU / 24 GB RAM** (dentro do Always Free).
- **Imagem:** Ubuntu 22.04 (**aarch64**).
- **Boot volume:** 100 GB (o TimescaleDB cresce com a telemetria).
- Guarde a **chave SSH** e anote o **IP público**.

> ⚠️ **"Out of capacity" do A1:** é o erro mais comum do free tier. Tente outro
> Availability Domain / região, ou mude a conta para *Pay As You Go* (continua
> Always Free de graça, mas destrava a disponibilidade do A1).

---

## 2. Abrir as portas — DOIS firewalls

O Oracle bloqueia em **duas** camadas. Abra as duas para **22, 80 e 8000**:

**a) VCN (nuvem):** Networking → VCN → Subnet → Security List → *Add Ingress Rules*
Source `0.0.0.0/0`, TCP, portas `80` e `8000` (o `22` já vem aberto).

**b) Firewall da instância (iptables):** a imagem Ubuntu da Oracle bloqueia tudo
menos SSH. Dentro da VM:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save
```

---

## 3. Instalar Docker + Compose

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
docker compose version   # confirmar o plugin compose
```

---

## 4. Subir a aplicação

```bash
git clone https://github.com/viniciusadrian1/predicta-forzy.git
cd predicta-forzy

cp .env.prod.example .env
nano .env        # preencher: senhas, JWT_SECRET_KEY, CORS_ORIGINS, PUBLIC_API_URL

docker compose -f docker-compose.prod.yml up -d --build
```

O build compila as imagens **nativas para a arquitetura da VM** (arm64 na
Oracle). Primeiro build leva alguns minutos (Tesseract + sklearn/scipy/pandas).

No `.env`, use o **IP público** da VM:

```
CORS_ORIGINS=http://SEU_IP_PUBLICO
PUBLIC_API_URL=http://SEU_IP_PUBLICO:8000
```

Gere o segredo do JWT com `openssl rand -hex 32` (sem ele o backend não sobe em
`production`).

---

## 5. Verificar

```bash
docker compose -f docker-compose.prod.yml ps          # todos "Up"/"healthy"
curl http://localhost:8000/health                     # {"status":"ok",...}
docker compose -f docker-compose.prod.yml logs -f backend   # alembic -> seed -> import -> uvicorn
```

- Frontend: `http://SEU_IP_PUBLICO`
- API/docs: `http://SEU_IP_PUBLICO:8000/docs`
- Login de teste: `admin` / `admin123` (e `gestor`/`operador`/`auditor`/`viewer` + `123`).

---

## Dados dos motores

- **MTR-001** — vem AO VIVO do simulador OPC-UA (serviço `opcua-simulator`).
- **MTR-F01 / F02** — o `start.sh` importa o histórico real (dado autêntico,
  porém de maio). Para dado **ao vivo**, preencha `EXTERNAL_SENSORS_BASE_URL`
  no `.env` com o túnel HTTP da Forzy quando estiver ativo.
- Alternativa auto-contida: `DEMO_SIMULATOR=true` no `.env` gera telemetria
  recente dos 3 motores sem depender de OPC-UA/túnel (nesse caso, remova o
  serviço `opcua-simulator` do compose para não duplicar o MTR-001).

## Operação

```bash
# Atualizar após um push
git pull && docker compose -f docker-compose.prod.yml up -d --build

# Logs / reiniciar um serviço
docker compose -f docker-compose.prod.yml logs -f <servico>
docker compose -f docker-compose.prod.yml restart backend

# Backup do banco de telemetria (volume)
docker run --rm -v predicta-prod_timescale_data:/data -v $PWD:/backup alpine \
  tar czf /backup/timescale_backup.tgz -C /data .
```

## Notas

- **ARM:** todas as dependências têm build aarch64 (numpy/scipy/scikit-learn/
  pandas via wheels manylinux; Tesseract via apt). Nada a fazer além de buildar
  na própria VM.
- **ChromaDB no ARM:** se a imagem falhar, ponha `RAG_VECTOR_BACKEND=memory` no
  `.env` e remova o serviço `chromadb` — o RAG cai para o índice em memória.
- **HTTPS / domínio (opcional):** coloque um reverse proxy (Caddy/Traefik) na
  frente para servir front + API sob um domínio com TLS automático, evitando a
  porta `:8000` exposta e problemas de mixed-content.
