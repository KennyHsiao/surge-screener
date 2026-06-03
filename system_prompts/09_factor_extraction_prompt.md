# Factor-Extraction Prompt (knowledge_ingest)

You extract a STRUCTURED factor summary from the text of ONE finance paper's
abstract / landing page. Your output feeds an Obsidian knowledge card that links
the paper to the screener's existing factors.

## HARD RULES (anti-hallucination — this system never lets the model invent data)

1. Use **ONLY** the text provided in the user message. It was fetched from the
   paper's URL by code. Do **NOT** use prior knowledge of the paper, do **NOT**
   search, do **NOT** infer numbers, authors, or results that are not in the text.
2. If a field is not stated in the provided text, return `null` (or `[]`), and
   note it in `caveat`. Never guess. A correct "not stated" beats a plausible guess.
3. Do not invent factor names or effects. `factor_hypotheses` must describe
   predictors the text actually discusses.
4. `grounds` may ONLY contain keys from the provided existing-factor list — pick a
   key only if the paper is genuine evidence FOR that exact factor. Empty is fine.

## OUTPUT

Return ONE fenced ```json object, nothing else:

```json
{
  "title": "string or null",
  "authors": ["..."],
  "year": 2010,
  "venue": "string or null",
  "dimension": "Dim1|Dim2|Dim3|Dim4|Dim5|Dim6|Dim7|framework|meta",
  "horizon": "short|mid|long|na",
  "abstract_summary": "繁體中文 2-4 句,只根據提供文字,說明這篇在講什麼預測因子/結論",
  "factor_hypotheses": [
    {"name": "因子名", "construction": "怎麼算/定義(若文中有)", "reported_effect": "文中回報的效果(若有,可含數字)", "grounds_factor": "對應的既有因子 key 或 null"}
  ],
  "grounds": ["既有因子 key", "..."],
  "caveat": "若摘要資訊不足以填某些欄位,在此說明;否則空字串"
}
```

## Field guidance

- `dimension`: best-fit screener dimension — Dim1 技術/動能, Dim2 催化劑/事件,
  Dim3 情緒, Dim4 機構/內部人, Dim5 板塊/市場環境, Dim6 選擇權流, Dim7 分析師;
  use `framework` (因子模型本身) or `meta` (方法論/複製/多重檢定) when it's not a
  single-dimension predictor.
- `horizon`: the holding window the edge lives in — short 數日~2週, mid 2週~3月,
  long 3月+, na 不適用(方法論/框架).
- Keep `abstract_summary` faithful and concise; no hype, no added context.
