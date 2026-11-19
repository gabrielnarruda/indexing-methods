"""Validated recipes. Runtime URLs and credentials are not experiment parameters."""
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GRAPH_PROMPT = """Extraia entidades, eventos e relações dos trechos abaixo.
Preserve papéis, atribuição, negação e modalidade. Diferencie fatos, alegações,
decisões e referências a outros processos. Não una pessoas por nomes parecidos.
Cada relação precisa de source_idx e citação literal da passagem correspondente.
Use nomes explícitos; date e speaker ficam vazios quando não estão explícitos.
Cubra as relações relevantes dentro do limite do schema, sem inventar relações.
Trechos: {{passages}}"""
SUMMARY_PROMPT = """Crie um título e um resumo descritivo de até 150 palavras dos trechos.
Preserve nomes, assuntos, datas, atribuição e diferenças entre alegação e decisão.
O resumo serve para localizar informação; não substitui a fonte.
Trechos: {{passages}}"""
ANSWER_PROMPT = """Responda à pergunta somente com as evidências fornecidas.
Pergunta: {{question}}
Schema do valor: {{value_schema}}
Trechos: {{passages}}
Motivo da tentativa anterior: {{previous_reason}}
Preserve processo/peça, papéis, atribuição, datas, negação e todos os itens de listas.
Use filled somente com valor e citações literais curtas com chunk_id.
Se faltar evidência, use search_again, value=null e uma next_query diferente.
not_found não prova ausência no documento. Conflicting preserva o conflito.
Não use conhecimento externo. Datas em AAAA-MM-DD. Retorne o schema solicitado."""
VERIFY_PROMPT = """Confira se o valor responde à pergunta e é sustentado pelas passagens.
Pergunta: {{question}}
Valor: {{proposed_value}}
Citações: {{citations}}
Passagens: {{passages}}
Cheque papéis, processo principal versus precedentes, atribuição, negação e listas.
Não confunda citação literal existente com suporte semântico. Explique reason e
marque supported=true somente quando o valor estiver sustentado."""

class Recipe(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(default='Grafo com contexto', min_length=1, max_length=100)
    parser: Literal['pymupdf', 'pymupdf_dedup'] = 'pymupdf_dedup'
    ocr: Literal['off', 'auto'] = 'off'
    ocr_language: str = Field(default='por', pattern=r'^[a-z+]{3,30}$')
    pages: str = Field(default='', max_length=300)
    chunk_characters: int = Field(default=1800, ge=200, le=16000)
    overlap_characters: int = Field(default=200, ge=0, le=8000)
    section_characters: int = Field(default=10000, ge=1000, le=50000)
    graph_enabled: bool = True
    summary_enabled: bool = True
    graph_model: str = 'qwen3:4b'
    summary_model: str = 'qwen3:4b'
    answer_model: str = 'qwen3:4b'
    verify_model: str = 'qwen3:4b'
    embedding_model: str = 'embeddinggemma:300m'
    graph_prompt: str = GRAPH_PROMPT
    summary_prompt: str = SUMMARY_PROMPT
    answer_prompt: str = ANSWER_PROMPT
    verify_prompt: str = VERIFY_PROMPT
    max_relations: int = Field(default=24, ge=1, le=100)
    top_k: int = Field(default=4, ge=1, le=12)
    max_rounds_per_field: int = Field(default=3, ge=1, le=8)
    variant: Literal['A', 'B', 'C', 'D', 'E', 'F'] = 'F'
    graph_depth: int = Field(default=1, ge=1, le=3)
    max_output_tokens: int = Field(default=1800, ge=128, le=8192)
    context_tokens: int = Field(default=16384, ge=2048, le=131072)
    temperature: float = Field(default=0, ge=0, le=2)
    seed: int = Field(default=42, ge=0, le=2147483000)
    request_timeout_seconds: int = Field(default=300, ge=10, le=1800)
    machine_hour_rate: float | None = Field(default=None, ge=0, le=100000)
    currency: Literal['BRL', 'USD'] = 'BRL'
    cache_policy: Literal['reuse', 'rebuild'] = 'reuse'

    @model_validator(mode='after')
    def validate_recipe(self):
        if self.overlap_characters >= self.chunk_characters:
            raise ValueError('A sobreposição deve ser menor que o recorte.')
        if self.section_characters < self.chunk_characters:
            raise ValueError('O pacote de extração precisa comportar pelo menos um recorte.')
        if self.section_characters > self.context_tokens * 2:
            raise ValueError('O pacote excede o limite conservador para o contexto configurado.')
        page_selection(self.pages)
        for key in ['graph', 'summary', 'answer', 'verify']:
            prompt = getattr(self, key + '_prompt')
            if not 10 <= len(prompt) <= 30000:
                raise ValueError('Prompts precisam ter entre 10 e 30.000 caracteres.')
            allowed = {'passages'} if key in ('graph', 'summary') else {'passages', 'question', 'value_schema', 'previous_reason'} if key == 'answer' else {'passages', 'question', 'proposed_value', 'citations'}
            variables = set(re.findall(r'\{\{(.*?)\}\}', prompt))
            if variables - allowed or 'passages' not in variables:
                raise ValueError(f'Variáveis inválidas em {key}; use {sorted(allowed)}, incluindo passages.')
            if not re.fullmatch(r'[a-zA-Z0-9_.:/-]{1,150}', getattr(self, key + '_model')):
                raise ValueError('Nome de modelo inválido.')
        if not self.graph_enabled and self.variant in 'DEF':
            raise ValueError('Esta estratégia consulta o grafo; habilite o grafo ou escolha A/B/C.')
        if not self.summary_enabled and self.variant in 'CEF':
            raise ValueError('Esta estratégia consulta resumos; habilite resumos ou escolha A/B/D.')
        return self

def page_selection(value, total=None):
    if not value.strip():
        return list(range(1, total+1)) if total else None
    result = set()
    for part in value.split(','):
        if not re.fullmatch(r'\s*\d+(?:\s*-\s*\d+)?\s*', part):
            raise ValueError('Páginas: use 1-3,8 ou deixe vazio para o PDF completo.')
        limits = [int(x.strip()) for x in part.split('-')]
        first, last = limits[0], limits[-1]
        if first < 1 or last < first or last > (total or 100000):
            raise ValueError('Intervalo de páginas inválido para este documento.')
        result.update(range(first, last+1))
    return sorted(result)

def render_prompt(template, values):
    import json
    return re.sub(r'\{\{(.*?)\}\}', lambda m: json.dumps(values[m[1]], ensure_ascii=False), template)

def runtime_settings(recipe, environment):
    value = recipe.model_dump()
    return {**environment, **value, 'chat_model': recipe.answer_model,
            'stage_models': {'relations': recipe.graph_model, 'summary': recipe.summary_model,
                             'generation': recipe.answer_model, 'support_validation': recipe.verify_model}}
