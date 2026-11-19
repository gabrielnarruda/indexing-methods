import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, fmt, time, money, percent, statusLabel } from "./api";
import type {
  Answer,
  Bootstrap,
  Comparison,
  Configuration,
  Dataset,
  Fact,
  Graph,
  Plan,
  Recipe,
  Run,
  Scalar,
  Stage,
} from "./types";
import "./style.css";

const icons: Record<string, string> = {
  flask: "⚗",
  book: "▤",
  prompt: "⌘",
  graph: "⑂",
  clock: "◷",
  settings: "☷",
  grid: "▦",
  compare: "▥",
  file: "▤",
  cut: "☷",
  spark: "✧",
  vector: "⫶",
  search: "⌕",
  json: "{}",
  shield: "◇",
};
const editorStages = [
  ["parse", "file", "Leitura do PDF"],
  ["chunk", "cut", "Recortes e pacotes"],
  ["graph", "graph", "Entidades e relações"],
  ["summary", "spark", "Resumos"],
  ["embed", "vector", "Embeddings"],
  ["search", "search", "Recuperação"],
  ["answer", "json", "Extração JSON"],
  ["verify", "shield", "Verificação"],
  ["cost", "clock", "Custo e execução"],
];
const variants: Record<string, string> = {
  A: "Lexical (BM25)",
  B: "Híbrida (lexical + vetor)",
  C: "Híbrida + resumos",
  D: "Híbrida + grafo",
  E: "Híbrida + resumos + grafo",
  F: "Híbrida + resumos + grafo, iterativa",
};
const running = (run: Run) =>
  ["queued", "starting", "running"].includes(run.status);
const short = (value: string) => value.slice(0, 11);

function Badge({ status }: { status: string }) {
  return (
    <span
      className={
        "badge " +
        (["complete", "reused"].includes(status)
          ? "green"
          : ["failed", "cancelled", "interrupted"].includes(status)
            ? "red"
            : status === "running"
              ? "blue"
              : "")
      }
    >
      {statusLabel[status] || status}
    </span>
  );
}
function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <section className="card empty">
      <h2>{title}</h2>
      <p>{children}</p>
    </section>
  );
}
function DatasetEditor({
  dataset,
  onSaved,
}: {
  dataset: Dataset;
  onSaved: () => Promise<void>;
}) {
  const [text, setText] = useState(
      JSON.stringify({ form: dataset.form, cases: dataset.cases }, null, 2),
    ),
    [error, setError] = useState(""),
    [saving, setSaving] = useState(false);
  return (
    <>
      <p>
        Edite o formulário JSON e suas referências. Salvar cria uma nova versão;
        runs anteriores preservam seus insumos.
      </p>
      <p className="meta">
        Campos: id, path, question e value_schema. Referências: field_id,
        expected, aliases, reference_pages e split (development ou held_out).
        Gabaritos não são enviados aos modelos.
      </p>
      <label className="field">
        <span>Formulário e referências (JSON)</span>
        <textarea
          aria-label="Formulário e referências (JSON)"
          style={{ minHeight: 440, marginTop: 12 }}
          spellCheck={false}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button
        className="btn primary"
        disabled={saving}
        onClick={async () => {
          setSaving(true);
          setError("");
          try {
            await api(
              "/documents/" + dataset.source.id + "/dataset",
              JSON.parse(text),
            );
            await onSaved();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setSaving(false);
          }
        }}
      >
        Salvar nova versão do formulário
      </button>
    </>
  );
}
function StageTable({
  stages,
  other,
  currency = "BRL",
  otherCurrency,
}: {
  stages: Stage[];
  other?: Stage[];
  currency?: string;
  otherCurrency?: string;
}) {
  return (
    <div
      className="scroll"
      tabIndex={0}
      role="region"
      aria-label="Tempos por etapa"
    >
      <table className="timing-table">
        <thead>
          <tr>
            <th>Etapa</th>
            <th>{other ? "Referência" : "Duração nesta run"}</th>
            {other && <th>Candidata</th>}
            <th>{other ? "Diferença" : "Estado / custo"}</th>
          </tr>
        </thead>
        <tbody>
          {stages.map((stage) => {
            const candidate = other?.find((s) => s.name === stage.name);
            const delta =
              candidate?.duration_ms != null && stage.duration_ms != null
                ? (candidate.duration_ms - stage.duration_ms) / 1000
                : null;
            const cell = (s: Stage, unit: string) => (
              <>
                <strong>
                  {time(s.duration_ms == null ? null : s.duration_ms / 1000)}
                </strong>
                <small>
                  {statusLabel[s.status] || s.status}
                  {s.history_ms != null
                    ? " · construção anterior " + time(s.history_ms / 1000)
                    : ""}
                </small>
                {s.detail?.reason && <small>{s.detail.reason}</small>}
                {s.duration_is_running && (
                  <small>Tempo decorrido · em andamento</small>
                )}
                {s.duration_is_partial && (
                  <small>Tempo parcial · operações registradas</small>
                )}
                <small>{s.model_calls || 0} chamadas de modelo</small>
                {!!s.cached_operations && (
                  <small>
                    {s.cached_operations} operações reaproveitadas do cache
                  </small>
                )}
                {other && (
                  <small>
                    API {money(s.api_cost, unit)} · máquina{" "}
                    {money(s.machine_cost_estimate, unit)}
                  </small>
                )}
              </>
            );
            return (
              <tr key={stage.name}>
                <td>
                  <strong>{stage.label}</strong>
                  <small>
                    {stage.detail?.total != null
                      ? (["relations", "summary"].includes(stage.name)
                          ? "Pacotes: "
                          : "Itens: ") +
                        stage.detail.completed +
                        "/" +
                        stage.detail.total
                      : ""}
                  </small>
                </td>
                <td>{cell(stage, currency)}</td>
                {other && (
                  <td>
                    {candidate
                      ? cell(candidate, otherCurrency || currency)
                      : "—"}
                  </td>
                )}
                <td>
                  {other ? (
                    <span
                      className={delta != null && delta > 0 ? "negative" : ""}
                    >
                      {delta == null
                        ? "Não comparável"
                        : (delta > 0 ? "+" : "") + time(delta)}
                    </span>
                  ) : (
                    <>
                      <Badge status={stage.status} />
                      <small>API: {money(stage.api_cost, currency)}</small>
                      <small>
                        Máquina: {money(stage.machine_cost_estimate, currency)}
                      </small>
                      {stage.detail?.error && (
                        <small className="error">{stage.detail.error}</small>
                      )}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
function App() {
  const [boot, setBoot] = useState<Bootstrap | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const [recipe, setRecipe] = useState<Recipe | null>(null),
    [parent, setParent] = useState<string | null>(null),
    [dirty, setDirty] = useState(false),
    [configs, setConfigs] = useState<Configuration[]>([]);
  const [page, setPage] = useState("experimentos"),
    [tab, setTab] = useState(
      location.hash === "#tempos" ? "compare" : "config",
    ),
    [stage, setStage] = useState("graph"),
    [menu, setMenu] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]),
    [selectedRun, setSelectedRun] = useState<Run | null>(null),
    [runFilter, setRunFilter] = useState(""),
    [runPage, setRunPage] = useState(0);
  const [documents, setDocuments] = useState(["adpf54", "dom-casmurro"]),
    [repetitions, setRepetitions] = useState(1),
    [split, setSplit] = useState("development"),
    [mode, setMode] = useState("end_to_end"),
    [fieldSelection, setFieldSelection] = useState<Record<string, string[]>>(
      {},
    );
  const [axes, setAxes] = useState<{ key: string; values: string }[]>([]),
    [planned, setPlanned] = useState<Plan | null>(null);
  const [reference, setReference] = useState(
      new URLSearchParams(location.search).get("reference") || "",
    ),
    [candidate, setCandidate] = useState(
      new URLSearchParams(location.search).get("candidate") || "",
    ),
    [comparison, setComparison] = useState<Comparison | null>(null);
  const [graphRun, setGraphRun] = useState(""),
    [graph, setGraph] = useState<Graph | null>(null),
    [graphOffset, setGraphOffset] = useState(0),
    [fact, setFact] = useState<Fact | null>(null);
  const [modal, setModal] = useState<{
    title: string;
    content: React.ReactNode;
  } | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const timingLinkOpened = useRef(false);
  const [health, setHealth] = useState<
    Record<string, { ok: boolean; error?: string }>
  >({});
  async function refresh() {
    const result = await api<Run[]>("/runs");
    setRuns(result);
    return result;
  }
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api<Bootstrap>("/bootstrap", undefined, controller.signal),
      api<Run[]>("/runs", undefined, controller.signal),
    ])
      .then(([data, jobs]) => {
        setBoot(data);
        setConfigs(data.configurations);
        setRecipe(data.configurations[0]?.body || data.defaults);
        setParent(data.configurations[0]?.id || null);
        setRuns(jobs);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    api<typeof health>("/health", undefined, controller.signal)
      .then(setHealth)
      .catch(() => {});
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const poll = setInterval(
      () =>
        api<Run[]>("/runs", undefined, controller.signal)
          .then(setRuns)
          .catch((e) => {
            if (e.name !== "AbortError") setError(e.message);
          }),
      3000,
    );
    return () => {
      clearInterval(poll);
      controller.abort();
    };
  }, []);
  useEffect(() => {
    if (modal) dialog.current?.showModal();
    else dialog.current?.close();
  }, [modal]);
  useEffect(() => {
    if (!selectedRun || !running(selectedRun)) return;
    const id = selectedRun.id,
      controller = new AbortController();
    const timer = setInterval(
      () =>
        api<Run>("/runs/" + id, undefined, controller.signal)
          .then(setSelectedRun)
          .catch((e) => {
            if (e.name !== "AbortError") setError(e.message);
          }),
      2500,
    );
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [selectedRun?.id, selectedRun?.status]);
  useEffect(() => {
    if (!reference || !candidate) {
      const done = runs.filter((r) => r.result?.evaluation);
      if (done.length) {
        if (!candidate) setCandidate(done[0].id);
        if (!reference)
          setReference(
            (
              done.find(
                (r) =>
                  r.id !== done[0].id &&
                  r.request.input_hash === done[0].request.input_hash,
              ) || done[0]
            ).id,
          );
      }
    }
  }, [runs, reference, candidate]);
  useEffect(() => {
    if (reference && candidate) {
      const controller = new AbortController();
      api<Comparison>(
        `/compare?reference=${reference}&candidate=${candidate}`,
        undefined,
        controller.signal,
      )
        .then(setComparison)
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
      return () => controller.abort();
    }
  }, [reference, candidate]);
  useEffect(() => {
    if (
      comparison &&
      tab === "compare" &&
      location.hash === "#tempos" &&
      !timingLinkOpened.current
    ) {
      const target = document.getElementById("tempos");
      if (target) {
        target.scrollIntoView({ block: "start" });
        timingLinkOpened.current = true;
      }
    }
  }, [comparison, tab, boot]);
  useEffect(() => {
    if (graphRun) {
      const controller = new AbortController();
      api<Graph>(
        `/runs/${graphRun}/graph?offset=${graphOffset}&limit=50`,
        undefined,
        controller.signal,
      )
        .then((value) => {
          setGraph(value);
          setFact(value.facts[0] || null);
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError(e.message);
        });
      return () => controller.abort();
    }
  }, [graphRun, graphOffset]);
  useEffect(() => {
    if (page === "grafo" && !graphRun) {
      const found = runs.find((r) => r.result?.index);
      if (found) setGraphRun(found.id);
    }
  }, [page, runs, graphRun]);
  async function act(operation: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function change(key: string, value: Scalar) {
    setRecipe((old) => (old ? { ...old, [key]: value } : null));
    setDirty(true);
    setPlanned(null);
  }
  function nav(next: string) {
    setPage(next);
    setMenu(false);
  }
  async function save() {
    if (!recipe) return;
    const saved = await api<Configuration>("/configurations", {
      recipe,
      parent_id: parent,
    });
    setConfigs((old) => [saved, ...old]);
    setParent(saved.id);
    setDirty(false);
    setNotice(
      "Versão " + saved.revision + " salva. As anteriores foram preservadas.",
    );
  }
  function payload() {
    if (!recipe) throw new Error("Configuração ainda não carregou.");
    const parsed: Record<string, Scalar[]> = {};
    for (const axis of axes) {
      if (!axis.key) continue;
      if (parsed[axis.key])
        throw new Error("Cada parâmetro deve aparecer em um único eixo.");
      try {
        const values = JSON.parse(axis.values);
        if (!Array.isArray(values)) throw new Error();
        parsed[axis.key] = values;
      } catch {
        throw new Error(
          'Cada eixo precisa de um array JSON, por exemplo [4, 8] ou ["modelo:a", "modelo:b"].',
        );
      }
    }
    return {
      recipe,
      parent_id: parent,
      axes: parsed,
      documents,
      repetitions,
      split,
      mode,
      dataset_versions: Object.fromEntries(
        (boot?.datasets || []).map((d) => [d.source.id, d.id]),
      ),
      field_ids: Object.fromEntries(
        Object.entries(fieldSelection).filter(([, ids]) => ids.length),
      ),
    };
  }
  async function inspect(id: string) {
    setSelectedRun(await api<Run>("/runs/" + id));
    setPage("experimentos");
    setTab("runs");
  }
  const labelRun = (r: Run) =>
    `${r.request.recipe.name} · ${r.corpus_id === "adpf54" ? "ADPF 54" : "Dom Casmurro"} · ${short(r.id)} · ${statusLabel[r.status] || r.status}`;
  const title =
    page === "experimentos"
      ? recipe?.name
      : page === "biblioteca"
        ? "Biblioteca e referências"
        : page === "prompts"
          ? "Biblioteca de prompts"
          : "Laboratório do grafo";
  const formField = (
    label: string,
    key: string,
    help = "",
    type = "number",
  ) => (
    <label className="field">
      <span>{label}</span>
      <input
        aria-label={label}
        type={type}
        value={recipe?.[key] == null ? "" : String(recipe[key])}
        onChange={(e) =>
          change(
            key,
            type === "number"
              ? e.target.value === ""
                ? null
                : Number(e.target.value)
              : e.target.value,
          )
        }
      />
      {help && <small>{help}</small>}
    </label>
  );
  const choice = (
    label: string,
    key: string,
    options: { value: string; label: string }[],
    help = "",
  ) => (
    <label className="field">
      <span>{label}</span>
      <select
        aria-label={label}
        value={String(recipe?.[key] ?? "")}
        onChange={(e) => change(key, e.target.value)}
      >
        {options.map((x) => (
          <option key={x.value} value={x.value}>
            {x.label}
          </option>
        ))}
      </select>
      {help && <small>{help}</small>}
    </label>
  );
  const toggle = (label: string, key: string) => (
    <label className="checkbox-line">
      <input
        type="checkbox"
        checked={Boolean(recipe?.[key])}
        onChange={(e) => change(key, e.target.checked)}
      />
      {label}
    </label>
  );
  const models = (key: string, embedding = false) =>
    choice(
      "Modelo " + (embedding ? "de embedding" : "da etapa"),
      key,
      (boot?.models || [])
        .filter((m) =>
          m.capabilities.includes(embedding ? "embedding" : "completion"),
        )
        .map((m) => ({ value: m.name, label: m.name })),
      "Modelos realmente instalados no Ollama local.",
    );
  const prompt = (key: string) => (
    <>
      <div className="prompt-head">
        <label className="field-label" htmlFor={key}>
          Prompt da etapa
        </label>
        <button
          className="btn ghost"
          onClick={() =>
            setModal({
              title: "Variáveis e schema",
              content: (
                <>
                  <p>
                    O pedido usa as variáveis entre chaves e o schema validado
                    do pipeline. As fontes são dados, não instruções.
                  </p>
                  <pre>{String(recipe?.[key])}</pre>
                  <p className="meta">
                    Os gabaritos de avaliação não são enviados ao modelo.
                  </p>
                </>
              ),
            })
          }
        >
          Ver contrato
        </button>
      </div>
      <textarea
        id={key}
        spellCheck={false}
        value={String(recipe?.[key] ?? "")}
        onChange={(e) => change(key, e.target.value)}
      />
      <p className="meta">
        {String(recipe?.[key] || "").length} caracteres · variável obrigatória:{" "}
        {"{{passages}}"}
      </p>
    </>
  );
  function configBody() {
    if (stage === "parse")
      return (
        <>
          {choice("Parser", "parser", [
            {
              value: "pymupdf_dedup",
              label: "PyMuPDF · remover blocos exatamente repetidos por página",
            },
            {
              value: "pymupdf",
              label:
                "PyMuPDF · todos os blocos originais, incluindo repetições",
            },
          ])}
          {choice(
            "OCR",
            "ocr",
            [
              { value: "off", label: "Não aplicar OCR" },
              {
                value: "auto",
                label: "Automático em páginas com imagem sem texto",
              },
            ],
            "OCR usa Tesseract local; a execução informa se o idioma não estiver instalado.",
          )}
          {formField("Idioma do OCR", "ocr_language", "", "text")}
          {formField(
            "Páginas",
            "pages",
            "Vazio = documento completo. Exemplo: 1-3,8. A seleção faz parte da identidade do teste.",
            "text",
          )}
        </>
      );
    if (stage === "chunk")
      return (
        <>
          {formField(
            "Tamanho do recorte",
            "chunk_characters",
            "Caracteres, preservando páginas e offsets.",
          )}
          {formField("Sobreposição", "overlap_characters")}
          {formField(
            "Tamanho do pacote de contexto",
            "section_characters",
            "Orçamento aproximado em caracteres para as chamadas de resumo e grafo.",
          )}
        </>
      );
    if (stage === "graph")
      return (
        <>
          {models("graph_model")}
          {prompt("graph_prompt")}
          <div className="rule" />
          {toggle("Construir entidades, eventos e relações", "graph_enabled")}
          {formField("Limite de relações por pacote", "max_relations")}
          <div className="hint">
            As relações precisam de citação literal. Isso valida a localização
            da fonte, mas não garante correção semântica.
          </div>
        </>
      );
    if (stage === "summary")
      return (
        <>
          {models("summary_model")}
          {prompt("summary_prompt")}
          {toggle("Construir resumos", "summary_enabled")}
        </>
      );
    if (stage === "embed")
      return (
        <>
          {models("embedding_model", true)}
          <div className="hint">
            A dimensão é determinada pela resposta real do modelo e registrada
            no índice. Texto original fica em arquivos locais; o OpenSearch
            guarda os termos pesquisáveis e os vetores.
          </div>
        </>
      );
    if (stage === "search")
      return (
        <>
          {choice(
            "Estratégia de busca",
            "variant",
            Object.entries(variants).map(([value, label]) => ({
              value,
              label,
            })),
          )}
          {formField(
            "Trechos por rodada",
            "top_k",
            "De 1 a 12 trechos. Cada evidência preserva documento, página e localização.",
          )}
          {formField(
            "Profundidade do grafo",
            "graph_depth",
            "De 1 a 3 expansões, com orçamento limitado de candidatos.",
          )}
        </>
      );
    if (stage === "answer")
      return (
        <>
          {models("answer_model")}
          {prompt("answer_prompt")}
          {formField(
            "Máximo de rodadas por campo",
            "max_rounds_per_field",
            "Aplicado à estratégia iterativa F; as demais usam uma rodada.",
          )}
        </>
      );
    if (stage === "verify")
      return (
        <>
          {models("verify_model")}
          {prompt("verify_prompt")}
          <div className="hint">
            A verificação de citações e schema ocorre antes da checagem
            semântica pelo modelo.
          </div>
        </>
      );
    return (
      <>
        <div className="formgrid">
          {formField("Tokens máximos de saída", "max_output_tokens")}
          {formField("Janela de contexto", "context_tokens")}
          {formField("Temperatura", "temperature")}
          {formField("Seed base", "seed")}
          {formField("Timeout por chamada (s)", "request_timeout_seconds")}
          {formField(
            "Custo da máquina por hora",
            "machine_hour_rate",
            "Deixe vazio se não souber. Custo desconhecido não aparece como zero.",
          )}
        </div>
        {choice("Moeda da tarifa local", "currency", [
          { value: "BRL", label: "BRL" },
          { value: "USD", label: "USD" },
        ])}
        {choice("Reaproveitamento", "cache_policy", [
          { value: "reuse", label: "Reaproveitar artefatos compatíveis" },
          { value: "rebuild", label: "Reconstruir para medir trabalho novo" },
        ])}
        <div className="hint">
          A API do Ollama local não cobra por token. O custo de hardware é uma
          estimativa baseada na tarifa informada e na duração medida.
        </div>
      </>
    );
  }
  function configurationView() {
    return (
      <>
        <div className="editor-layout">
          <section className="card editor">
            <nav className="stage-nav" aria-label="Etapas">
              <p className="meta">Etapas do método</p>
              {editorStages.map(([id, icon, label]) => (
                <button
                  className={"stage " + (stage === id ? "active" : "")}
                  key={id}
                  onClick={() => setStage(id)}
                >
                  <span aria-hidden>{icons[icon]}</span>
                  {label}
                </button>
              ))}
            </nav>
            <div className="editor-main">
              <div className="cardhead">
                <h2>{editorStages.find((x) => x[0] === stage)?.[2]}</h2>
                <span className="badge">
                  {dirty ? "Rascunho" : "Versão salva"}
                </span>
              </div>
              <div className="cardbody">{configBody()}</div>
            </div>
          </section>
          <aside className="aside">
            <section className="card sidecard">
              <div className="cardbody">
                <h3>Conjunto de dados</h3>
                {boot?.datasets.map((d) => (
                  <div className="docmini" key={d.source.id}>
                    <span>▤</span>
                    <div>
                      {d.source.id === "adpf54" ? "ADPF 54" : "Dom Casmurro"}
                      <small>
                        {d.source.pages} páginas · {d.form.fields.length} campos
                      </small>
                    </div>
                  </div>
                ))}
                <p className="meta">
                  Referências provisórias, sujeitas a revisão humana.
                </p>
              </div>
            </section>
            <section className="card sidecard">
              <div className="cardbody">
                <h3>Versões preservadas</h3>
                <label className="field">
                  <span>Carregar como rascunho</span>
                  <select
                    aria-label="Carregar como rascunho"
                    value={parent || ""}
                    onChange={(e) => {
                      const value = configs.find(
                        (c) => c.id === e.target.value,
                      );
                      if (value) {
                        setRecipe(value.body);
                        setParent(value.id);
                        setDirty(false);
                        setPlanned(null);
                      }
                    }}
                  >
                    {configs.map((c) => (
                      <option value={c.id} key={c.id}>
                        {c.name} · v{c.revision}
                      </option>
                    ))}
                  </select>
                </label>
                <p className="meta">
                  Cada execução guarda a receita e os insumos. Alterações
                  posteriores não mudam uma run existente.
                </p>
              </div>
            </section>
            <p className="rightnote">
              Resumo, relações e embeddings têm artefatos separados. A
              comparação informa o que foi medido agora e o que veio de cache.
            </p>
          </aside>
        </div>
        <div className="footer-actions">
          <p>Edite a configuração e escolha o que executar.</p>
          <button className="btn primary" onClick={() => setTab("matrix")}>
            Montar matriz de testes
          </button>
        </div>
      </>
    );
  }
  function matrixView() {
    return (
      <>
        <div className="sectionhead">
          <div>
            <h2>Uma receita, várias combinações</h2>
            <p>Escolha os dados e os parâmetros que vão variar.</p>
          </div>
        </div>
        <div className="matrix-layout">
          <section className="card">
            <div className="cardbody">
              <div className="formgrid">
                <label className="field">
                  <span>Modo de execução</span>
                  <select
                    aria-label="Modo de execução"
                    value={mode}
                    onChange={(e) => {
                      setMode(e.target.value);
                      setPlanned(null);
                    }}
                  >
                    <option value="end_to_end">
                      Indexar, extrair e avaliar
                    </option>
                    <option value="index_only">Somente indexação</option>
                  </select>
                </label>
                <label className="field">
                  <span>Conjunto de avaliação</span>
                  <select
                    aria-label="Conjunto de avaliação"
                    value={split}
                    onChange={(e) => {
                      setSplit(e.target.value);
                      setPlanned(null);
                    }}
                  >
                    <option value="development">Desenvolvimento</option>
                    <option value="held_out">Reservado</option>
                    <option value="all">
                      Todos — sem separação experimental
                    </option>
                  </select>
                </label>
              </div>
              <h3>Documentos e perguntas</h3>
              {boot?.datasets.map((dataset) => (
                <div className="dataset-select" key={dataset.source.id}>
                  <label className="checkbox-line">
                    <input
                      type="checkbox"
                      checked={documents.includes(dataset.source.id)}
                      onChange={(e) => {
                        setDocuments((old) =>
                          e.target.checked
                            ? [...old, dataset.source.id]
                            : old.filter((x) => x !== dataset.source.id),
                        );
                        setPlanned(null);
                      }}
                    />
                    {dataset.source.title}
                  </label>
                  {documents.includes(dataset.source.id) && (
                    <details>
                      <summary>
                        Selecionar campos · padrão: todos do conjunto escolhido
                      </summary>
                      <div className="field-choices">
                        {dataset.form.fields.map((f) => (
                          <label key={f.id}>
                            <input
                              type="checkbox"
                              checked={(
                                fieldSelection[dataset.source.id] || []
                              ).includes(f.id)}
                              onChange={(e) => {
                                setFieldSelection((old) => ({
                                  ...old,
                                  [dataset.source.id]: e.target.checked
                                    ? [...(old[dataset.source.id] || []), f.id]
                                    : (old[dataset.source.id] || []).filter(
                                        (x) => x !== f.id,
                                      ),
                                }));
                                setPlanned(null);
                              }}
                            />
                            {f.question}
                          </label>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              ))}
              <div className="rule" />
              <div className="sectionhead">
                <h3>Eixos paramétricos</h3>
                <button
                  className="btn"
                  onClick={() => {
                    setAxes((old) => [
                      ...old,
                      { key: "top_k", values: "[4, 8]" },
                    ]);
                    setPlanned(null);
                  }}
                  disabled={axes.length >= 5}
                >
                  Adicionar parâmetro
                </button>
              </div>
              <p className="meta">
                Sem eixos, executa a configuração atual. Para variar prompts,
                use um array JSON de textos completos.
              </p>
              {axes.map((axis, i) => (
                <div className="axis-edit" key={i}>
                  <label className="field">
                    <span>Parâmetro</span>
                    <select
                      aria-label="Parâmetro"
                      value={axis.key}
                      onChange={(e) => {
                        setAxes((old) =>
                          old.map((x, j) =>
                            j === i ? { ...x, key: e.target.value } : x,
                          ),
                        );
                        setPlanned(null);
                      }}
                    >
                      {Object.keys(recipe || {})
                        .filter((k) => k !== "name")
                        .map((key) => (
                          <option key={key}>{key}</option>
                        ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>Alternativas (JSON)</span>
                    <textarea
                      aria-label="Alternativas (JSON)"
                      value={axis.values}
                      onChange={(e) => {
                        setAxes((old) =>
                          old.map((x, j) =>
                            j === i ? { ...x, values: e.target.value } : x,
                          ),
                        );
                        setPlanned(null);
                      }}
                    />
                  </label>
                  <button
                    className="btn ghost danger"
                    aria-label={"Remover eixo " + (i + 1)}
                    onClick={() => {
                      setAxes((old) => old.filter((_, j) => j !== i));
                      setPlanned(null);
                    }}
                  >
                    Remover
                  </button>
                </div>
              ))}
              <label className="field" style={{ maxWidth: 240, marginTop: 24 }}>
                <span>Repetições por documento</span>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={repetitions}
                  onChange={(e) => {
                    setRepetitions(Number(e.target.value));
                    setPlanned(null);
                  }}
                />
              </label>
            </div>
          </section>
          <aside>
            <section className="card sidecard">
              <div className="cardbody">
                <h3>Plano de execução</h3>
                <div className="matrix-total">{planned?.run_count ?? "—"}</div>
                <p className="small muted">runs de documento</p>
                {planned && (
                  <dl className="definition">
                    <div>
                      <dt>Configurações</dt>
                      <dd>{planned.configuration_count}</dd>
                    </div>
                    <div>
                      <dt>Documentos</dt>
                      <dd>{documents.length}</dd>
                    </div>
                    <div>
                      <dt>Repetições</dt>
                      <dd>{repetitions}</dd>
                    </div>
                  </dl>
                )}
                <button
                  className="btn full"
                  disabled={busy}
                  onClick={() =>
                    act(async () =>
                      setPlanned(
                        await api<Plan>("/experiments/preview", payload()),
                      ),
                    )
                  }
                >
                  Conferir combinações
                </button>
                <button
                  className="btn primary full"
                  style={{ marginTop: 12 }}
                  disabled={busy || !planned}
                  onClick={() =>
                    act(async () => {
                      const result = await api<{
                        batch_id: string;
                        jobs: Run[];
                      }>("/experiments", payload());
                      await refresh();
                      setTab("runs");
                      setSelectedRun(null);
                      setNotice(
                        "Bateria " +
                          result.batch_id.slice(0, 8) +
                          " criada com " +
                          result.jobs.length +
                          " runs reais.",
                      );
                      setPlanned(null);
                    })
                  }
                >
                  Executar bateria real
                </button>
                <p className="meta" style={{ marginTop: 16 }}>
                  Uma execução por vez para medir no mesmo computador. Fechar a
                  aba não interrompe o worker.
                </p>
              </div>
            </section>
            <div className="hint warning">
              A execução pode levar minutos ou horas conforme páginas e modelos.
              Tarifa de hardware{" "}
              {recipe?.machine_hour_rate == null
                ? "não configurada"
                : money(
                    Number(recipe.machine_hour_rate),
                    String(recipe.currency),
                  ) + "/h"}
              . Nenhuma API paga está conectada.
            </div>
          </aside>
        </div>
        {planned && (
          <section className="card" style={{ marginTop: 22 }}>
            <div className="cardhead">
              <h3>Combinações validadas</h3>
            </div>
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Variações</th>
                    <th>Campos por documento</th>
                  </tr>
                </thead>
                <tbody>
                  {planned.configurations.map((row, i) => (
                    <tr key={i}>
                      <td>{i + 1}</td>
                      <td>
                        {axes.length
                          ? axes
                              .map(
                                (a) =>
                                  a.key +
                                  ": " +
                                  String(row.recipe[a.key]).slice(0, 140),
                              )
                              .join(" · ")
                          : "Configuração atual"}
                      </td>
                      <td>
                        {Object.entries(row.fields)
                          .map(([doc, fields]) => doc + ": " + fields.length)
                          .join(" · ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </>
    );
  }
  function runDetailView(run: Run) {
    const m = run.metrics;
    return (
      <>
        <div className="sectionhead">
          <div>
            <h2>
              {short(run.id)} · {run.corpus_id}
            </h2>
            <p>
              {run.request.recipe.name} · repetição {run.repetition + 1} ·{" "}
              {run.request.recipe.pages
                ? "páginas " + run.request.recipe.pages
                : "documento completo"}
            </p>
          </div>
          <div className="toolbar">
            <button className="btn" onClick={() => act(() => inspect(run.id))}>
              Atualizar detalhe
            </button>
            <button className="btn" onClick={() => setSelectedRun(null)}>
              Voltar à lista
            </button>
          </div>
        </div>
        <div className="summary-strip">
          <div>
            <strong>{percent(run.result?.evaluation?.accuracy)}</strong>
            <span>
              Acerto · {run.result?.evaluation?.annotated_count ?? 0} campos
              anotados
            </span>
          </div>
          <div>
            <strong>{time(m.wall_seconds)}</strong>
            <span>Tempo da run · fila: {time(m.queue_seconds)}</span>
          </div>
          <div>
            <strong>{money(m.total_cost, m.currency)}</strong>
            <span>Custo total · API {money(m.api_cost, m.currency)}</span>
          </div>
          <div>
            <strong>{m.mcp_calls}</strong>
            <span>Chamadas MCP · {m.agent_rounds} rodadas</span>
          </div>
        </div>
        <div className="toolbar" style={{ marginBottom: 20 }}>
          <Badge status={run.status} />
          {running(run) ? (
            <button
              className="btn danger"
              disabled={busy || Boolean(run.cancel_requested)}
              onClick={() =>
                act(async () => {
                  await api("/runs/" + run.id + "/cancel", {});
                  await inspect(run.id);
                  await refresh();
                })
              }
            >
              {run.cancel_requested
                ? "Cancelamento solicitado"
                : "Cancelar novas etapas"}
            </button>
          ) : (
            <button
              className="btn"
              onClick={() =>
                act(async () => {
                  await api("/runs/" + run.id + "/retry", {});
                  await refresh();
                  setSelectedRun(null);
                })
              }
            >
              Repetir com a mesma receita
            </button>
          )}
          {["json", "csv", "html"].map((format) => (
            <a
              className="btn"
              key={format}
              href={"/api/runs/" + run.id + "/export?format=" + format}
            >
              Exportar {format.toUpperCase()}
            </a>
          ))}
        </div>
        {run.error && <div className="hint warning">{run.error}</div>}
        {run.provenance?.implementation_changed_during_run && (
          <div className="hint warning">
            O código foi alterado durante esta execução. A versão inicial foi
            arquivada; repita a run com o código estável antes de usar seus
            tempos como referência.
          </div>
        )}
        {m.wall_seconds_upper_bound != null && (
          <p className="hint warning">
            O encerramento não foi observado. O intervalo até detectar a
            interrupção foi de {time(m.wall_seconds_upper_bound)}; ele não
            representa a duração exata da run.
          </p>
        )}
        <section className="card">
          <div className="cardhead">
            <h2>Tempo de cada etapa</h2>
            <span className="badge green">Medições reais</span>
          </div>
          <StageTable stages={m.stages} currency={m.currency} />
          <p className="timing-note">{m.timing_note}</p>
          <p className="timing-note">
            Reaproveitamento tem tempo novo de leitura/validação; construção
            histórica fica separada. Custo da máquina{" "}
            {m.machine_cost_estimate == null
              ? "não configurado"
              : money(m.machine_cost_estimate, m.currency)}
            . Uso desconhecido em {m.usage_unknown_calls} chamada(s).
          </p>
        </section>
        <section className="card" style={{ marginTop: 22 }}>
          <div className="cardhead">
            <h2>Respostas e evidências</h2>
          </div>
          {run.fields?.length ? (
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>Campo</th>
                    <th>Resposta</th>
                    <th>Estado</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {run.fields.map((field) => (
                    <tr key={field.id}>
                      <td>{field.question}</td>
                      <td className="answer-cell">{fmt(field.value)}</td>
                      <td>{field.status}</td>
                      <td>
                        <button
                          className="linkbutton"
                          onClick={() => answerModal(run, field)}
                        >
                          Investigar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="cardbody">
              <p>Nenhuma resposta publicada ainda.</p>
            </div>
          )}
        </section>
        <details className="card technical">
          <summary>Configuração, uso e proveniência</summary>
          <pre>
            {JSON.stringify(
              {
                configuration: run.config_id,
                request: run.request,
                metrics: run.metrics,
                index: run.result?.index,
                provenance: run.provenance,
              },
              null,
              2,
            )}
          </pre>
        </details>
      </>
    );
  }
  function answerModal(run: Run, field: Answer) {
    setModal({
      title: field.question,
      content: (
        <>
          <div className="answerbox">
            <h3>Resposta · {field.status}</h3>
            <pre>{fmt(field.value)}</pre>
            <p>{field.reason}</p>
          </div>
          <h3 style={{ marginTop: 20 }}>Fontes</h3>
          {field.evidence.map((e, i) => (
            <blockquote className="quote" key={i}>
              {e.quote}
              <p className="meta">
                Página {e.page} · {e.chunk_id}
              </p>
              <a
                href={"/api/documents/" + run.corpus_id + "/pdf#page=" + e.page}
                target="_blank"
                rel="noreferrer"
              >
                Abrir página no PDF
              </a>
              <button
                className="linkbutton"
                style={{ marginLeft: 16 }}
                onClick={() =>
                  act(async () => {
                    const passage = await api<{ text: string; page: number }>(
                      "/runs/" +
                        run.id +
                        "/passages/" +
                        encodeURIComponent(e.chunk_id),
                    );
                    setModal({
                      title: "Trecho original · página " + passage.page,
                      content: <pre>{passage.text}</pre>,
                    });
                  })
                }
              >
                Ler trecho completo
              </button>
            </blockquote>
          ))}
          <h3>Rodadas de investigação</h3>
          {field.rounds.map((round) => (
            <details key={round.round}>
              <summary>
                Rodada {round.round} · {round.query}
              </summary>
              <pre>{JSON.stringify(round, null, 2)}</pre>
            </details>
          ))}
          <p className="meta">
            Uma citação existente não garante que o valor tenha sido atribuído
            corretamente. Revise a evidência.
          </p>
        </>
      ),
    });
  }
  function runsView() {
    if (selectedRun) return runDetailView(selectedRun);
    const filtered = runs.filter((r) =>
      JSON.stringify([r.id, r.corpus_id, r.request.recipe.name, r.status])
        .toLowerCase()
        .includes(runFilter.toLowerCase()),
    );
    return (
      <>
        <div className="sectionhead">
          <div>
            <h2>Execuções reais</h2>
            <p>
              Fila persistente · uma run ativa por vez · atualização a cada 3
              segundos.
            </p>
          </div>
          <button
            className="btn"
            onClick={() =>
              act(async () => {
                await refresh();
              })
            }
          >
            Atualizar
          </button>
        </div>
        <section className="card">
          <div className="table-tools">
            <input
              type="text"
              value={runFilter}
              aria-label="Buscar execuções"
              placeholder="Run, documento, nome ou estado"
              onChange={(e) => {
                setRunFilter(e.target.value);
                setRunPage(0);
              }}
            />
            <span className="meta">
              {runs.filter((r) => r.status === "running").length} ativa(s) ·{" "}
              {runs.filter((r) => r.status === "queued").length} na fila
            </span>
          </div>
          {filtered.length ? (
            <>
              <div className="scroll">
                <table className="run-table">
                  <thead>
                    <tr>
                      <th>Run / documento</th>
                      <th>Configuração</th>
                      <th>Estado</th>
                      <th>Qualidade</th>
                      <th>Tempo</th>
                      <th>Custo</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered
                      .slice(runPage * 10, runPage * 10 + 10)
                      .map((run) => (
                        <tr key={run.id}>
                          <td>
                            <strong>{short(run.id)}</strong>
                            <small>
                              {run.corpus_id} · repetição {run.repetition + 1}
                            </small>
                          </td>
                          <td>
                            {run.request.recipe.name}
                            <small>
                              {run.request.recipe.pages
                                ? "Páginas " + run.request.recipe.pages
                                : "PDF completo"}
                            </small>
                          </td>
                          <td>
                            <Badge status={run.status} />
                            {run.cancel_requested ? (
                              <small>Cancelamento solicitado</small>
                            ) : null}
                          </td>
                          <td>
                            {percent(run.result?.evaluation?.accuracy)}
                            <small>
                              {run.result?.evaluation?.annotated_count ?? 0}{" "}
                              anotados
                            </small>
                          </td>
                          <td>
                            {time(run.metrics.wall_seconds)}
                            <small>
                              Fila: {time(run.metrics.queue_seconds)}
                            </small>
                          </td>
                          <td>
                            {money(
                              run.metrics.total_cost,
                              run.metrics.currency,
                            )}
                            <small>
                              API:{" "}
                              {money(
                                run.metrics.api_cost,
                                run.metrics.currency,
                              )}
                            </small>
                          </td>
                          <td>
                            <button
                              className="linkbutton"
                              onClick={() => act(() => inspect(run.id))}
                            >
                              Inspecionar
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <div className="editor-footer">
                <span>
                  {runPage * 10 + 1}–
                  {Math.min(filtered.length, runPage * 10 + 10)} de{" "}
                  {filtered.length}
                </span>
                <div className="toolbar">
                  <button
                    className="btn"
                    disabled={!runPage}
                    onClick={() => setRunPage((x) => x - 1)}
                  >
                    Anterior
                  </button>
                  <button
                    className="btn"
                    disabled={(runPage + 1) * 10 >= filtered.length}
                    onClick={() => setRunPage((x) => x + 1)}
                  >
                    Próxima
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="empty">
              <h3>Nenhuma execução encontrada</h3>
              <p>
                Monte uma matriz para iniciar seu primeiro experimento real.
              </p>
            </div>
          )}
        </section>
      </>
    );
  }
  function compareView() {
    const a = comparison?.reference,
      b = comparison?.candidate;
    return (
      <>
        <section className="card compare-controls">
          <label className="field">
            <span>Run de referência</span>
            <select
              aria-label="Run de referência"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
            >
              <option value="">Selecione</option>
              {runs
                .filter((r) => !running(r))
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {labelRun(r)}
                  </option>
                ))}
            </select>
          </label>
          <label className="field">
            <span>Run candidata</span>
            <select
              aria-label="Run candidata"
              value={candidate}
              onChange={(e) => setCandidate(e.target.value)}
            >
              <option value="">Selecione</option>
              {runs
                .filter((r) => !running(r))
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {labelRun(r)}
                  </option>
                ))}
            </select>
          </label>
          <div className="field">
            <span>Mesmo conjunto de casos</span>
            <span
              className={
                "badge " + (comparison?.compatible ? "green" : "amber")
              }
            >
              {comparison
                ? comparison.compatible
                  ? "Compatível"
                  : "Comparação exige atenção"
                : "Selecione duas runs"}
            </span>
          </div>
        </section>
        {a && b ? (
          <>
            {comparison?.warning && (
              <div className="hint warning">{comparison.warning}</div>
            )}
            <section className="card" style={{ marginTop: 22 }}>
              <div className="cardhead">
                <h2>Qualidade, custo e tempo</h2>
                <a className="btn" href="#tempos">
                  Ver tempo de cada etapa ↓
                </a>
              </div>
              <div className="scroll">
                <table className="compare-table">
                  <thead>
                    <tr>
                      <th>Métrica</th>
                      <th>Referência</th>
                      <th>Candidata</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      [
                        "Acerto automático",
                        percent(a.result?.evaluation?.accuracy),
                        percent(b.result?.evaluation?.accuracy),
                      ],
                      [
                        "Campos anotados",
                        a.result?.evaluation?.annotated_count ?? 0,
                        b.result?.evaluation?.annotated_count ?? 0,
                      ],
                      [
                        "Tempo da run",
                        time(a.metrics.wall_seconds),
                        time(b.metrics.wall_seconds),
                      ],
                      [
                        "Espera na fila",
                        time(a.metrics.queue_seconds),
                        time(b.metrics.queue_seconds),
                      ],
                      [
                        "Custo de API",
                        money(a.metrics.api_cost, a.metrics.currency),
                        money(b.metrics.api_cost, b.metrics.currency),
                      ],
                      [
                        "Estimativa de hardware",
                        money(
                          a.metrics.machine_cost_estimate,
                          a.metrics.currency,
                        ),
                        money(
                          b.metrics.machine_cost_estimate,
                          b.metrics.currency,
                        ),
                      ],
                      [
                        "Chamadas MCP",
                        a.metrics.mcp_calls,
                        b.metrics.mcp_calls,
                      ],
                      [
                        "Rodadas do agente",
                        a.metrics.agent_rounds,
                        b.metrics.agent_rounds,
                      ],
                      [
                        "Tokens de entrada / saída",
                        a.metrics.input_tokens +
                          " / " +
                          a.metrics.output_tokens,
                        b.metrics.input_tokens +
                          " / " +
                          b.metrics.output_tokens,
                      ],
                    ].map(([name, x, y]) => (
                      <tr key={String(name)}>
                        <td>{name}</td>
                        <td>{x}</td>
                        <td>{y}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="timing-note">
                Referências provisórias. Um maior acerto nesta amostra não
                demonstra generalização. A tarifa de hardware é uma estimativa;
                ausência de tarifa significa custo desconhecido.
              </p>
            </section>
            <section className="card timing-panel" id="tempos">
              <div className="cardhead">
                <h2>Tempos por etapa</h2>
                <span className="badge">Referência × candidata</span>
              </div>
              <StageTable
                stages={a.metrics.stages}
                other={b.metrics.stages}
                currency={a.metrics.currency}
                otherCurrency={b.metrics.currency}
              />
              <p className="timing-note">
                {b.metrics.timing_note} Compare estados de cache antes de
                interpretar diferenças.
              </p>
            </section>
            <section className="card" style={{ marginTop: 22 }}>
              <div className="cardhead">
                <h2>O que mudou em cada campo</h2>
              </div>
              <div className="scroll">
                <table className="fieldlist">
                  <thead>
                    <tr>
                      <th>Campo</th>
                      <th>Referência</th>
                      <th>Candidata</th>
                      <th>Diferença</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {b.result?.evaluation?.fields.map((score) => {
                      const other = a.result?.evaluation?.fields.find(
                        (s) => s.field_id === score.field_id,
                      );
                      const label = !comparison?.compatible
                        ? "Não comparável"
                        : score.correct === other?.correct
                          ? "Estável"
                          : score.correct
                            ? "Ganho"
                            : "Regressão";
                      return (
                        <tr key={score.field_id}>
                          <td>{score.field_id}</td>
                          <td>
                            {fmt(other?.actual)}
                            <small>
                              {other?.correct == null
                                ? "Não avaliado"
                                : other.correct
                                  ? "Correto"
                                  : "Incorreto"}
                            </small>
                          </td>
                          <td>
                            {fmt(score.actual)}
                            <small>
                              {score.correct == null
                                ? "Não avaliado"
                                : score.correct
                                  ? "Correto"
                                  : "Incorreto"}
                            </small>
                          </td>
                          <td>
                            <span
                              className={
                                "badge " +
                                (label === "Ganho"
                                  ? "green"
                                  : label === "Regressão"
                                    ? "red"
                                    : "")
                              }
                            >
                              {label}
                            </span>
                          </td>
                          <td>
                            <button
                              className="linkbutton"
                              onClick={() => {
                                const fa = a.fields?.find(
                                    (f) => f.id === score.field_id,
                                  ),
                                  fb = b.fields?.find(
                                    (f) => f.id === score.field_id,
                                  );
                                setModal({
                                  title: "Comparar campo · " + score.field_id,
                                  content: (
                                    <>
                                      <p className="meta">
                                        Gabarito provisório:{" "}
                                        {fmt(score.expected)}
                                      </p>
                                      <div className="detailcols">
                                        {[
                                          [a, fa, "Referência"],
                                          [b, fb, "Candidata"],
                                        ].map(([r, f, label]) => (
                                          <div
                                            className="answerbox"
                                            key={String(label)}
                                          >
                                            <h3>{String(label)}</h3>
                                            <pre>
                                              {fmt((f as Answer)?.value)}
                                            </pre>
                                            <p>{(f as Answer)?.reason}</p>
                                            {(f as Answer)?.evidence.map(
                                              (e, i) => (
                                                <blockquote
                                                  className="quote"
                                                  key={i}
                                                >
                                                  {e.quote}
                                                  <small>
                                                    {" "}
                                                    · página {e.page}
                                                  </small>
                                                </blockquote>
                                              ),
                                            )}
                                            {f && (
                                              <button
                                                className="btn"
                                                onClick={() =>
                                                  answerModal(
                                                    r as Run,
                                                    f as Answer,
                                                  )
                                                }
                                              >
                                                Investigar rodadas e fontes
                                              </button>
                                            )}
                                          </div>
                                        ))}
                                      </div>
                                    </>
                                  ),
                                });
                              }}
                            >
                              Ver evidências
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
            <details className="card technical">
              <summary>Diferenças da receita</summary>
              <pre>{JSON.stringify(comparison?.differences, null, 2)}</pre>
            </details>
          </>
        ) : (
          <Empty title="Selecione duas runs para comparar">
            As métricas virão das execuções e dos eventos reais. O protótipo
            continua disponível como referência de UI, separado desta aplicação.
          </Empty>
        )}
      </>
    );
  }
  function libraryView() {
    return (
      <div className="docgrid">
        {boot?.datasets.map((d) => (
          <article className="card doccard" key={d.source.id}>
            <div className="cardbody">
              <span className="badge">
                {d.source.kind === "judicial"
                  ? "Documento judicial aberto"
                  : "Literatura de domínio público"}
              </span>
              <h2 style={{ marginTop: 18 }}>{d.source.title}</h2>
              <p className="small muted">{d.source.scope}</p>
              <div className="facts">
                <span>{d.source.pages} páginas</span>
                <span>{d.form.fields.length} campos</span>
              </div>
              <div className="toolbar">
                <a
                  className="btn"
                  href={"/api/documents/" + d.source.id + "/pdf"}
                  target="_blank"
                  rel="noreferrer"
                >
                  Abrir PDF
                </a>
                <button
                  className="btn"
                  onClick={() =>
                    act(async () => {
                      const data = await api<{ page: number; text: string }>(
                        "/documents/" + d.source.id + "/pages/1",
                      );
                      setModal({
                        title: "Leitura real · página 1",
                        content: (
                          <>
                            <a
                              href={
                                "/api/documents/" + d.source.id + "/pdf#page=1"
                              }
                              target="_blank"
                              rel="noreferrer"
                            >
                              Conferir no PDF
                            </a>
                            <pre>{data.text}</pre>
                          </>
                        ),
                      });
                    })
                  }
                >
                  Inspecionar leitura
                </button>
                <button
                  className="btn ghost"
                  onClick={() =>
                    setModal({
                      title: "Perguntas e gabarito · " + d.source.id,
                      content: (
                        <>
                          <p className="hint warning">
                            Gabarito provisório, sem revisão humana. A avaliação
                            fica separada do contexto enviado ao modelo.
                          </p>
                          <div className="scroll">
                            <table>
                              <thead>
                                <tr>
                                  <th>Pergunta</th>
                                  <th>Referência</th>
                                  <th>Páginas / conjunto</th>
                                </tr>
                              </thead>
                              <tbody>
                                {d.form.fields.map((f) => {
                                  const c = d.cases.find(
                                    (c) => c.field_id === f.id,
                                  );
                                  return (
                                    <tr key={f.id}>
                                      <td>
                                        {f.question}
                                        <small>{f.path}</small>
                                      </td>
                                      <td>{fmt(c?.expected)}</td>
                                      <td>
                                        {c?.reference_pages.join(", ")}
                                        <small>{c?.split}</small>
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        </>
                      ),
                    })
                  }
                >
                  Ver perguntas
                </button>
              </div>
              <div className="rule" />
              <label className="field">
                <span>Versão do formulário e referências</span>
                <select
                  aria-label="Versão do formulário e referências"
                  value={d.id}
                  onChange={(e) =>
                    act(async () => {
                      const versions = await api<Dataset[]>(
                        "/documents/" + d.source.id + "/datasets",
                      );
                      const selected = versions.find(
                        (v) => v.id === e.target.value,
                      );
                      if (selected) {
                        setBoot((old) =>
                          old
                            ? {
                                ...old,
                                datasets: old.datasets.map((item) =>
                                  item.source.id === d.source.id
                                    ? { ...d, ...selected }
                                    : item,
                                ),
                              }
                            : old,
                        );
                        setPlanned(null);
                        setFieldSelection((old) => ({
                          ...old,
                          [d.source.id]: [],
                        }));
                      }
                    })
                  }
                >
                  {d.versions.map((v) => (
                    <option value={v.id} key={v.id}>
                      Versão {v.revision}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="btn"
                onClick={() =>
                  setModal({
                    title: "Editar formulário · " + d.source.id,
                    content: (
                      <DatasetEditor
                        dataset={d}
                        onSaved={async () => {
                          const updated = await api<Bootstrap>("/bootstrap");
                          setBoot((old) =>
                            old ? { ...old, datasets: updated.datasets } : old,
                          );
                          setPlanned(null);
                          setModal(null);
                          setNotice(
                            "Nova versão do formulário salva. Runs existentes preservadas.",
                          );
                        }}
                      />
                    ),
                  })
                }
              >
                Editar formulário JSON
              </button>
              <p className="meta hash">SHA-256: {d.source.sha256}</p>
            </div>
          </article>
        ))}
      </div>
    );
  }
  function graphView() {
    return (
      <>
        <section className="card">
          <div className="cardbody">
            <label className="field">
              <span>Construção do grafo</span>
              <select
                aria-label="Construção do grafo"
                value={graphRun}
                onChange={(e) => {
                  setGraphRun(e.target.value);
                  setGraphOffset(0);
                }}
              >
                <option value="">Selecione uma run com índice publicado</option>
                {runs
                  .filter((r) => r.result?.index)
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {labelRun(r)}
                    </option>
                  ))}
              </select>
            </label>
            <p className="meta">
              {graph?.total ?? 0} relações ancoradas · {graph?.rejected ?? 0}{" "}
              propostas rejeitadas · versão {graph?.version || "—"}
            </p>
          </div>
        </section>
        {graph?.facts.length ? (
          <div className="graph-layout" style={{ marginTop: 22 }}>
            <section className="card">
              <div className="cardhead">
                <h2>Relações e fontes</h2>
                <span className="badge">
                  Página {Math.floor(graphOffset / 50) + 1}
                </span>
              </div>
              <div className="graph-canvas">
                <svg
                  viewBox="0 0 700 230"
                  aria-label="Relação selecionada e evidência"
                >
                  <path
                    d="M220 85H275M425 85H480M350 115V155"
                    stroke="#9ab5a3"
                    strokeWidth={2}
                    fill="none"
                  />
                  {[
                    [25, 50, 195, fact?.subject || ""],
                    [275, 50, 150, fact?.predicate || ""],
                    [480, 50, 195, fact?.object || ""],
                    [
                      240,
                      155,
                      220,
                      "Página " + fact?.page + " · fonte literal",
                    ],
                  ].map(([x, y, w, text], i) => (
                    <g key={i}>
                      <rect
                        x={Number(x)}
                        y={Number(y)}
                        width={Number(w)}
                        height={65}
                        rx={7}
                        fill={i === 1 ? "#e7f1eb" : "white"}
                        stroke="#a8bfb0"
                      />
                      <text
                        x={Number(x) + 12}
                        y={Number(y) + 35}
                        fontSize={13}
                        fill="#233b38"
                      >
                        {String(text).slice(0, i === 1 ? 18 : 24)}
                      </text>
                      <title>{String(text)}</title>
                    </g>
                  ))}
                </svg>
              </div>
              <div className="scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Sujeito</th>
                      <th>Relação</th>
                      <th>Objeto</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {graph.facts.map((f, i) => (
                      <tr key={i} className={fact === f ? "selected-row" : ""}>
                        <td>{f.subject}</td>
                        <td>{f.predicate}</td>
                        <td>{f.object}</td>
                        <td>
                          <button
                            className="linkbutton"
                            onClick={() => setFact(f)}
                          >
                            Ver fonte
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="editor-footer">
                <span>
                  {graphOffset + 1}–{Math.min(graph.total, graphOffset + 50)} de{" "}
                  {graph.total}
                </span>
                <div className="toolbar">
                  <button
                    className="btn"
                    disabled={!graphOffset}
                    onClick={() => setGraphOffset((x) => Math.max(0, x - 50))}
                  >
                    Anterior
                  </button>
                  <button
                    className="btn"
                    disabled={graphOffset + 50 >= graph.total}
                    onClick={() => setGraphOffset((x) => x + 50)}
                  >
                    Próxima
                  </button>
                </div>
              </div>
            </section>
            <aside className="card cardbody">
              <h3>Evidência da relação</h3>
              <blockquote className="quote">{fact?.quote}</blockquote>
              <p className="small">
                {fact?.subject} → {fact?.predicate} → {fact?.object}
              </p>
              <p className="meta">
                {fact?.speaker && "Atribuição: " + fact.speaker}
                {fact?.date && " · Data: " + fact.date}
              </p>
              <a
                className="btn"
                style={{ marginTop: 18 }}
                href={
                  "/api/documents/" +
                  runs.find((r) => r.id === graphRun)?.corpus_id +
                  "/pdf#page=" +
                  fact?.page
                }
                target="_blank"
                rel="noreferrer"
              >
                Abrir página {fact?.page}
              </a>
              <p className="meta" style={{ marginTop: 18 }}>
                A relação é uma proposta do modelo ancorada em texto. Revise
                papéis, escopo e atribuição.
              </p>
            </aside>
          </div>
        ) : (
          <Empty title="Nenhuma relação disponível">
            {graph?.note ||
              "Escolha uma run com grafo. Se não houver relações aceitas, a tela permanece vazia; não criaremos nós demonstrativos."}
          </Empty>
        )}
      </>
    );
  }
  if (!boot || !recipe)
    return (
      <main className="loading">
        <h1>Indexing Methods</h1>
        <p>{error || "Conectando à plataforma local…"}</p>
        {error && (
          <button className="btn" onClick={() => location.reload()}>
            Tentar novamente
          </button>
        )}
      </main>
    );
  return (
    <>
      <a className="skip" href="#main">
        Ir para conteúdo
      </a>
      <aside className={"sidebar " + (menu ? "open" : "")}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            nav("experimentos");
          }}
        >
          <span className="brand-mark">⑂</span>
          <span className="brand-name">
            indexing
            <br />
            methods<small>Workbench local</small>
          </span>
        </a>
        <div className="project">
          <span>IM</span>
          <div>
            Meu laboratório<small>Dados no computador</small>
          </div>
        </div>
        <p className="navlabel">Área de trabalho</p>
        <nav>
          {[
            ["biblioteca", "book", "Biblioteca"],
            ["experimentos", "flask", "Experimentos"],
            ["prompts", "prompt", "Prompts"],
            ["grafo", "graph", "Grafo"],
          ].map(([id, icon, label]) => (
            <button
              key={id}
              className={"navbutton " + (page === id ? "active" : "")}
              aria-current={page === id ? "page" : undefined}
              onClick={() => nav(id)}
            >
              <span aria-hidden>{icons[icon]}</span>
              {label}
            </button>
          ))}
        </nav>
        <div className="nav-bottom">
          <a
            className="navbutton"
            href="/history/relatorio.html"
            target="_blank"
            rel="noreferrer"
          >
            ▤ Relatório histórico da PoC
          </a>
          <div className="local">
            <span>●</span>Execução local real
          </div>
        </div>
      </aside>
      {menu && (
        <button
          className="mobile-shade open"
          aria-label="Fechar menu"
          onClick={() => setMenu(false)}
        />
      )}
      <div className="shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="iconbtn mobile-menu"
              aria-label="Abrir menu"
              onClick={() => setMenu((x) => !x)}
            >
              ☰
            </button>
            <span>Meu laboratório</span>
            <span>›</span>
            <strong>
              {page === "experimentos"
                ? "Experimentos"
                : page === "biblioteca"
                  ? "Biblioteca"
                  : page === "prompts"
                    ? "Prompts"
                    : "Grafo"}
            </strong>
          </div>
          <div className="toolbar">
            <span className="badge">Uso individual</span>
            <span className="avatar">GA</span>
          </div>
        </header>
        <div className="live-banner">
          <span>
            <strong>Plataforma local</strong> · Execuções e métricas reais ·
            Ollama
          </span>
          <span>
            {Object.entries(health).map(([key, value]) => (
              <span
                className={"service " + (value.ok ? "ok" : "bad")}
                key={key}
              >
                {key} {value.ok ? "●" : "○"}
              </span>
            ))}
          </span>
        </div>
        <main className="workspace" id="main">
          <div className="pagehead">
            <div>
              <div className="titleline">
                <h1>{title}</h1>
                {page === "experimentos" && (
                  <span className={"badge " + (dirty ? "amber" : "green")}>
                    {dirty ? "Rascunho alterado" : "Configuração versionada"}
                  </span>
                )}
              </div>
              <p>
                {page === "experimentos"
                  ? "Compare métodos sobre os mesmos documentos, com evidência em cada resposta."
                  : "Documentos, versões e fontes do pipeline real."}
              </p>
            </div>
            {page === "experimentos" && (
              <div className="toolbar">
                <button
                  className="btn"
                  onClick={() => {
                    setRecipe({ ...recipe, name: recipe.name + " · cópia" });
                    setDirty(true);
                    setTab("config");
                    setNotice(
                      "Cópia em rascunho. Renomeie e salve uma nova versão.",
                    );
                  }}
                >
                  Duplicar
                </button>
                <button
                  className="btn primary"
                  disabled={busy}
                  onClick={() => act(save)}
                >
                  Salvar versão
                </button>
              </div>
            )}
          </div>
          {error && (
            <div className="alert error" role="alert">
              <span>{error}</span>
              <button className="btn ghost" onClick={() => setError("")}>
                Fechar
              </button>
            </div>
          )}
          {notice && (
            <div className="alert" role="status">
              <span>{notice}</span>
              <button className="btn ghost" onClick={() => setNotice("")}>
                Fechar
              </button>
            </div>
          )}
          {boot.model_error && (
            <div className="hint warning">{boot.model_error}</div>
          )}
          {page === "experimentos" && (
            <>
              <nav className="tabs" aria-label="Seções do experimento">
                {[
                  ["config", "Configuração"],
                  ["matrix", "Matriz de testes"],
                  ["runs", "Execuções"],
                  ["compare", "Comparação"],
                ].map(([key, label]) => (
                  <button
                    className={"tab " + (tab === key ? "active" : "")}
                    key={key}
                    aria-current={tab === key ? "page" : undefined}
                    onClick={() => setTab(key)}
                  >
                    {label}
                    {key === "runs" && <small>{runs.length}</small>}
                  </button>
                ))}
              </nav>
              {tab === "config" && (
                <>
                  <label className="field recipe-name">
                    <span>Nome da configuração</span>
                    <input
                      type="text"
                      value={recipe.name}
                      onChange={(e) => change("name", e.target.value)}
                    />
                  </label>
                  {configurationView()}
                </>
              )}
              {tab === "matrix" && matrixView()}
              {tab === "runs" && runsView()}
              {tab === "compare" && compareView()}
            </>
          )}
          {page === "biblioteca" && libraryView()}
          {page === "prompts" && (
            <section className="card">
              {[
                ["graph", "Entidades e relações"],
                ["summary", "Resumos"],
                ["answer", "Extração JSON"],
                ["verify", "Verificação"],
              ].map(([id, label]) => (
                <div className="prompt-row" key={id}>
                  <div>
                    <h3>{label}</h3>
                    <p>
                      {String(recipe[id + "_model"])} ·{" "}
                      {String(recipe[id + "_prompt"]).length} caracteres
                    </p>
                  </div>
                  <button
                    className="btn"
                    onClick={() => {
                      nav("experimentos");
                      setTab("config");
                      setStage(id);
                    }}
                  >
                    Editar prompt
                  </button>
                </div>
              ))}
            </section>
          )}
          {page === "grafo" && graphView()}
        </main>
      </div>
      <dialog ref={dialog} className="wide" onCancel={() => setModal(null)}>
        <div className="modalhead">
          <h2>{modal?.title}</h2>
          <button
            className="iconbtn"
            aria-label="Fechar detalhe"
            onClick={() => setModal(null)}
          >
            ×
          </button>
        </div>
        <div className="modalbody">{modal?.content}</div>
        <div className="modalfoot">
          <button className="btn" onClick={() => setModal(null)}>
            Fechar
          </button>
        </div>
      </dialog>
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
