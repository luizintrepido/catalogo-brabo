# -*- coding: utf-8 -*-
"""
Rotação Automática de Criativos — Campanha STORIES (O Brabo das Vendas)

Roda a cada 3 dias (via GitHub Actions). Para cada anúncio do conjunto Stories
que está performando MAL, busca uma foto AINDA NÃO USADA na pasta do Drive
"story ads" e substitui o criativo do anúncio por essa foto nova.

Critério de "mau desempenho" (janela de DIAS dias):
  - Gastou >= GASTO_MIN e ZERO conversas, OU
  - Tem >= IMPR_MIN impressões e CTR < CTR_MIN, OU
  - Tem conversas mas CPL > CPL_MAX

Limita a MAX_TROCAS trocas por execução (evita churn).
Rastreia fotos já usadas em usadas.json.

Variáveis de ambiente:
  META_ACCESS_TOKEN  (secret)
  + credenciais Google Drive (scraper/credentials.json + token.json)
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

# Reusar o DriveUploader do scraper
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE.parent / "scraper"))
from drive_uploader import DriveUploader  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Config ─────────────────────────────────────────────
TOKEN        = os.environ.get("META_ACCESS_TOKEN", "")
AD_ACCOUNT   = "act_1350642725759754"
PAGE_ID      = "1953737774857073"
PHONE        = "5513991575019"
ADSET_STORIES = "120245820540170752"          # conjunto Stories
DRIVE_FOLDER = "13Fxt6Un_LGy6xPIqpnpXXuyoietuCuBe"  # pasta "story ads"
API          = "https://graph.facebook.com/v22.0"

# Janela de avaliação e limites
DIAS       = 7
MAX_TROCAS = 2

# Thresholds de mau desempenho
GASTO_MIN = 2.0    # R$ gasto mínimo pra considerar que teve chance
IMPR_MIN  = 150    # impressões mínimas pra avaliar CTR
CTR_MIN   = 1.5    # CTR abaixo disso = ruim (%)
CPL_MAX   = 12.0   # custo por conversa acima disso = ruim (R$)

USADAS_FILE = BASE / "usadas.json"
TROCADOS_FILE = BASE / "trocados.json"
COOLDOWN_DIAS = 5   # não troca o mesmo anúncio de novo antes disso


# ── Meta API ───────────────────────────────────────────
def meta(method, path, data=None):
    url = f"{API}/{path}"
    if data is None:
        data = {}
    data["access_token"] = TOKEN
    if method == "POST":
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=body, method="POST")
    else:
        url = url + "?" + urllib.parse.urlencode(data)
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.loads(e.read().decode())}
        except Exception:
            return {"error": str(e)}


def conversas(row):
    a = {x["action_type"]: float(x["value"]) for x in row.get("actions", [])}
    for k in ("onsite_conversion.messaging_conversation_started_7d",
              "onsite_conversion.total_messaging_connection",
              "onsite_conversion.messaging_first_reply"):
        if k in a:
            return int(a[k])
    return 0


def upload_meta_image(img_bytes, nome):
    """Sobe imagem na Meta via multipart e retorna o hash."""
    import io
    boundary = "----brabostory" + str(int(time.time()))
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="filename"; filename="{nome}"\r\n'.encode())
    parts.append(b"Content-Type: image/jpeg\r\n\r\n")
    parts.append(img_bytes)
    parts.append(f"\r\n--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="access_token"\r\n\r\n')
    parts.append(TOKEN.encode())
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        f"{API}/{AD_ACCOUNT}/adimages", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            d = json.loads(r.read().decode())
        imgs = d.get("images", {})
        for v in imgs.values():
            return v.get("hash")
    except Exception as e:
        print(f"  ERRO upload Meta: {e}")
    return None


def wa_link(msg):
    return f"https://api.whatsapp.com/send?phone={PHONE}&text={urllib.parse.quote(msg, safe='')}"


def criar_creative_e_trocar(ad_id, image_hash, nome_foto):
    """Cria criativo Story com a nova foto e troca no anúncio."""
    msg = ("Chegou novidade no estoque do Brabo. "
           "Confere as condições e chama no zap 👇")
    oss = {
        "page_id": PAGE_ID,
        "link_data": {
            "image_hash": image_hash,
            "link": wa_link("Oi Luiz! Vi esse carro no Story e quero saber as condições. CPF limpo"),
            "message": msg,
            "call_to_action": {"type": "WHATSAPP_MESSAGE"},
        },
    }
    cr = meta("POST", f"{AD_ACCOUNT}/adcreatives", {
        "name": f"CR_STORY_AUTO_{nome_foto}",
        "object_story_spec": json.dumps(oss),
    })
    cr_id = cr.get("id")
    if not cr_id:
        print(f"  ERRO criar criativo: {cr.get('error')}")
        return False
    upd = meta("POST", ad_id, {"creative": json.dumps({"creative_id": cr_id})})
    if upd.get("success") or upd.get("id"):
        return True
    print(f"  ERRO trocar criativo: {upd.get('error')}")
    return False


# ── Tracking de fotos usadas ───────────────────────────
def carregar_usadas():
    if USADAS_FILE.exists():
        try:
            return set(json.loads(USADAS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def salvar_usadas(usadas):
    USADAS_FILE.write_text(json.dumps(sorted(usadas), ensure_ascii=False, indent=2),
                           encoding="utf-8")


def carregar_trocados():
    if TROCADOS_FILE.exists():
        try:
            return json.loads(TROCADOS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def em_carencia(ad_id, trocados):
    """True se o anúncio foi trocado há menos de COOLDOWN_DIAS."""
    from datetime import datetime, timedelta
    ts = trocados.get(ad_id)
    if not ts:
        return False
    try:
        dt = datetime.fromisoformat(ts)
        return datetime.now() - dt < timedelta(days=COOLDOWN_DIAS)
    except Exception:
        return False


# ── Lógica principal ───────────────────────────────────
def main():
    if not TOKEN:
        print("ERRO: META_ACCESS_TOKEN não definido.")
        sys.exit(1)

    print("=== ROTAÇÃO DE STORIES — Brabo das Vendas ===\n")

    # 1. Performance por anúncio do conjunto Stories
    ins = meta("GET", f"{ADSET_STORIES}/insights", {
        "level": "ad",
        "fields": "ad_id,ad_name,spend,impressions,ctr,actions",
        "date_preset": f"last_{DIAS}d" if DIAS in (7, 14, 30) else "last_7d",
        "limit": "100",
    })
    if "error" in ins:
        print(f"ERRO na API Meta: {json.dumps(ins['error'], ensure_ascii=False)[:500]}")
        print("Verifique o secret META_ACCESS_TOKEN (pode estar cortado ou expirado).")
        sys.exit(1)
    rows = ins.get("data", [])
    print(f"Anúncios avaliados: {len(rows)}")

    # 2. Identificar maus desempenhos
    ruins = []
    for r in rows:
        sp = float(r.get("spend", 0) or 0)
        impr = int(float(r.get("impressions", 0) or 0))
        ctr = float(r.get("ctr", 0) or 0)
        cv = conversas(r)
        cpl = (sp / cv) if cv else 0
        motivo = None
        if sp >= GASTO_MIN and cv == 0:
            motivo = f"gastou R${sp:.2f} e 0 conversas"
        elif impr >= IMPR_MIN and ctr < CTR_MIN:
            motivo = f"CTR {ctr:.2f}% (baixo)"
        elif cv and cpl > CPL_MAX:
            motivo = f"CPL R${cpl:.2f} (alto)"
        if motivo:
            ruins.append((r.get("ad_id"), r.get("ad_name", ""), sp, motivo))
            print(f"  RUIM: {r.get('ad_name')} -> {motivo}")
        else:
            print(f"  ok:   {r.get('ad_name')} (R${sp:.2f}, {cv} conv, CTR {ctr:.2f}%)")

    # Remover os que estão em carência (trocados recentemente)
    trocados = carregar_trocados()
    antes = len(ruins)
    ruins = [x for x in ruins if not em_carencia(x[0], trocados)]
    if antes != len(ruins):
        print(f"  ({antes - len(ruins)} em carência, pulados)")

    if not ruins:
        print("\nNenhum anúncio ruim. Nada a trocar. ✅")
        return

    # Pior primeiro (mais gasto desperdiçado)
    ruins.sort(key=lambda x: x[2], reverse=True)
    ruins = ruins[:MAX_TROCAS]

    # 3. Fotos disponíveis no Drive
    # O DriveUploader procura credentials.json/token.json no diretório atual.
    # As credenciais ficam em scraper/, então entramos nessa pasta antes.
    scraper_dir = BASE.parent / "scraper"
    if (scraper_dir / "credentials.json").exists() or (scraper_dir / "token.json").exists():
        os.chdir(scraper_dir)
    drive = DriveUploader()
    fotos = drive.list_files_in_folder(DRIVE_FOLDER)
    print(f"\nFotos na pasta: {len(fotos)}")
    usadas = carregar_usadas()
    disponiveis = [f for f in fotos if f["id"] not in usadas]
    print(f"Já usadas: {len(usadas)} | Disponíveis: {len(disponiveis)}")

    if not disponiveis:
        print("\nSem fotos novas disponíveis na pasta. Adicione mais fotos ao Drive.")
        return

    # 4. Trocar
    trocas = 0
    for ad_id, nome, sp, motivo in ruins:
        if not disponiveis:
            print("Acabaram as fotos novas.")
            break
        foto = disponiveis.pop(0)
        print(f"\n>> Trocando '{nome}' ({motivo})")
        print(f"   Nova foto: {foto['name']} ({foto['id']})")
        img = drive.download_file_bytes(foto["id"])
        if not img:
            print("   ERRO: não baixou a foto.")
            continue
        h = upload_meta_image(img, foto["name"])
        if not h:
            print("   ERRO: não subiu pra Meta.")
            continue
        if criar_creative_e_trocar(ad_id, h, foto["name"].replace(".", "_")):
            usadas.add(foto["id"])
            from datetime import datetime
            trocados[ad_id] = datetime.now().isoformat()
            trocas += 1
            print(f"   OK! Criativo trocado.")
        time.sleep(2)

    salvar_usadas(usadas)
    TROCADOS_FILE.write_text(json.dumps(trocados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== CONCLUÍDO: {trocas} anúncio(s) renovado(s) ===")


if __name__ == "__main__":
    main()
