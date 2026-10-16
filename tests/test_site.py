"""Testes da página institucional (docs/) e da publicação. Sem rede, sem tokens."""
import datetime as dt
import json
import re
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
PAGINAS = sorted(DOCS.glob("*.html"))
INDEXAVEIS = [p for p in PAGINAS if p.name != "404.html"]
SUBDOMINIOS = ("bolaof1", "meiospagamento", "creditomodalidade", "plantscare", "painel",
               "arrecadacaofederal", "ia")


class Leitor(HTMLParser):
    VAZIAS = {"meta", "link", "img", "br", "hr", "input", "source"}

    def __init__(self):
        super().__init__()
        self.pilha, self.erros, self.tags = [], [], []
        self.ld, self._no_ld = [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        if tag == "script" and a.get("type") == "application/ld+json":
            self._no_ld = True
        if tag not in self.VAZIAS:
            self.pilha.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VAZIAS:
            return
        if not self.pilha or self.pilha[-1] != tag:
            self.erros.append(f"</{tag}> fora de ordem (aberta: {self.pilha[-1:]})")
            return
        self.pilha.pop()
        self._no_ld = False

    def handle_data(self, data):
        if self._no_ld:
            self.ld.append(data)


def ler(p):
    leitor = Leitor()
    leitor.feed(p.read_text(encoding="utf-8"))
    return leitor


class TestPaginas(unittest.TestCase):
    def test_html_bem_formado(self):
        for p in PAGINAS:
            r = ler(p)
            self.assertEqual(r.erros, [], p.name)
            self.assertEqual(r.pilha, [], f"{p.name}: tags sem fechar")

    def test_cabecalho_basico(self):
        for p in PAGINAS:
            tags = ler(p).tags
            nomes = [(t, a.get("name"), a.get("rel")) for t, a in tags]
            self.assertIn(("html", None, None), nomes, p.name)
            self.assertEqual(dict(tags[0][1]).get("lang"), "pt-BR", p.name)
            self.assertIn(("meta", "viewport", None), nomes, p.name)
            self.assertIn(("title", None, None), nomes, p.name)
            self.assertIn(("link", None, "stylesheet"), nomes, p.name)

    def test_indexaveis_tem_descricao_e_canonical(self):
        for p in INDEXAVEIS:
            tags = ler(p).tags
            self.assertTrue(any(t == "meta" and a.get("name") == "description" and len(a.get("content", "")) > 50
                                for t, a in tags), p.name)
            self.assertTrue(any(t == "link" and a.get("rel") == "canonical"
                                and a.get("href", "").startswith("https://gfvdata.com/") for t, a in tags), p.name)

    def test_json_ld(self):
        r = ler(DOCS / "index.html")
        self.assertEqual(len(r.ld), 1)
        dados = json.loads("".join(r.ld))
        self.assertEqual(dados["@context"], "https://schema.org")
        tipos = {n["@type"]: n for n in dados["@graph"]}
        self.assertEqual(set(tipos), {"Organization", "WebSite"})
        self.assertEqual(tipos["Organization"]["email"], "contato@gfvdata.com")
        self.assertEqual(tipos["WebSite"]["url"], "https://gfvdata.com/")

    def test_links_locais_existem(self):
        for p in PAGINAS:
            for t, a in ler(p).tags:
                alvo = a.get("href") or a.get("src")
                if not alvo or re.match(r"^(https?:|mailto:|#)", alvo):
                    continue
                arq = DOCS / alvo.lstrip("/").split("#")[0]
                if arq.is_dir() or alvo.endswith("/"):
                    arq = arq / "index.html"
                self.assertTrue(arq.exists(), f"{p.name}: {alvo}")

    def test_sem_script_executavel_nem_recurso_externo(self):
        # A CSP (docs/_headers) só permite CSS e imagens locais.
        for p in PAGINAS:
            for t, a in ler(p).tags:
                if t == "script":
                    self.assertEqual(a.get("type"), "application/ld+json", f"{p.name}: <script> executável")
                if t in ("link", "img", "script") and (a.get("src") or (a.get("href") if t == "link" else None)):
                    url = a.get("src") or a.get("href")
                    self.assertFalse(url.startswith(("http:", "https:", "//")) and a.get("rel") != "canonical",
                                     f"{p.name}: recurso externo {url}")
            self.assertNotIn("style=", p.read_text(encoding="utf-8"), f"{p.name}: style inline bloqueado pela CSP")

    def test_institucional_sem_links_para_subdominios(self):
        for p in PAGINAS:
            texto = p.read_text(encoding="utf-8")
            for s in SUBDOMINIOS:
                self.assertNotIn(f"{s}.gfvdata.com", texto, f"{p.name} cita {s}.gfvdata.com")


class TestArquivosDeRobos(unittest.TestCase):
    def test_robots(self):
        texto = (DOCS / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Allow: /", texto)
        self.assertNotIn("Disallow: /\n", texto)
        self.assertIn("Sitemap: https://gfvdata.com/sitemap.xml", texto)

    def test_sitemap_bate_com_paginas(self):
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = {e.text for e in ET.parse(DOCS / "sitemap.xml").getroot().findall("s:url/s:loc", ns)}
        esperado = {"https://gfvdata.com/" + ("" if p.name == "index.html" else p.name) for p in INDEXAVEIS}
        self.assertEqual(locs, esperado)

    def test_security_txt(self):
        texto = (DOCS / ".well-known" / "security.txt").read_text(encoding="utf-8")
        self.assertIn("Contact: mailto:contato@gfvdata.com", texto)
        m = re.search(r"^Expires: (\d{4}-\d{2}-\d{2})T", texto, re.M)
        self.assertIsNotNone(m)
        vence = dt.date.fromisoformat(m.group(1))
        self.assertGreater(vence, dt.date.today() + dt.timedelta(days=60),
                           "security.txt vence em menos de 60 dias: renove o Expires")

    def test_headers(self):
        texto = (DOCS / "_headers").read_text(encoding="utf-8")
        for h in ("Strict-Transport-Security", "X-Content-Type-Options: nosniff",
                  "Referrer-Policy", "Content-Security-Policy", "Permissions-Policy"):
            self.assertIn(h, texto)


class TestPublicacao(unittest.TestCase):
    def test_wrangler(self):
        bruto = (RAIZ / "wrangler.jsonc").read_text(encoding="utf-8")
        cfg = json.loads(re.sub(r"^\s*//.*$", "", bruto, flags=re.M))
        self.assertEqual(cfg["name"], "site-raiz")
        self.assertEqual(cfg["assets"]["directory"], "./docs")
        rotas = {r["pattern"] for r in cfg["routes"] if r.get("custom_domain")}
        self.assertEqual(rotas, {"gfvdata.com", "www.gfvdata.com"})
        self.assertFalse(cfg["workers_dev"])

    def test_workflow(self):
        texto = (RAIZ / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main]", texto)
        self.assertIn("CLOUDFLARE_API_TOKEN", texto)
        self.assertIn("wrangler@4.150.0 deploy", texto)


if __name__ == "__main__":
    unittest.main()
