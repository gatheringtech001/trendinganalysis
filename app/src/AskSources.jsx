import React, { useState } from "react";
import { api, formatNumber, stores } from "./api";

const prompts = [
  "哪家店的连衣裙SKU最多？",
  "哪家店图片索引最多？",
  "各数据源商品价格中位数？",
  "哪家店促销SKU最多？",
  "哪家店售罄SKU最多？",
];

export function AskView({ summary }) {
  const [question, setQuestion] = useState(prompts[0]);
  const [answer, setAnswer] = useState(null);
  const [busy, setBusy] = useState(false);
  const submit = async (value = question) => {
    setQuestion(value);
    setBusy(true);
    try { setAnswer(await api.ask(value)); } finally { setBusy(false); }
  };
  return (
    <div className="ask-view">
      <section className="ask-workspace">
        <h2>直接询问已采集的数据</h2>
        <p>回答由本地SQLite实时聚合，并明确返回来源和支持范围。</p>
        <form onSubmit={(event) => { event.preventDefault(); submit(); }}>
          <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
          <button className="primary-button" disabled={busy}>{busy ? "分析中…" : "开始分析"}</button>
        </form>
        <div className="prompt-list">
          {prompts.map((prompt) => <button key={prompt} onClick={() => submit(prompt)}>{prompt}</button>)}
        </div>
      </section>
      <section className="answer-workspace">
        <h2>分析结果</h2>
        {!answer && <p className="empty-answer">选择一个问题，或输入自己的数据问题。</p>}
        {answer && (
          <>
            <div className={answer.supported ? "large-answer" : "large-answer unsupported"}>{answer.answer}</div>
            {answer.rows?.length > 0 && (
              <table>
                <thead><tr><th>店铺</th><th>{answer.label}</th><th>占比</th></tr></thead>
                <tbody>
                  {answer.rows.map((row) => (
                    <tr key={row.store_id}>
                      <td>{stores[row.store_id]}</td>
                      <td>{formatNumber(row.value)}</td>
                      <td>{row.rate == null ? "—" : `${(row.rate * 100).toFixed(1)}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="answer-source">来源：官网商品目录与客户数据集 · {answer.confidence}置信度 · 快照{summary.snapshot}</div>
          </>
        )}
      </section>
      <aside className="question-boundary">
        <h2>当前可回答</h2>
        <ul><li>SKU和分类数量</li><li>图片索引数量</li><li>价格中位数</li><li>促销与售罄情况</li></ul>
        <p>涉及趋势预测、消费者动机或经营决策的问题，需要结合报告证据由我继续分析，不会由规则引擎编造答案。</p>
      </aside>
    </div>
  );
}
