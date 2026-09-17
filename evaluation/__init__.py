"""评测域：问题集与标注、判分、runner、报告。

目录约定：
  * datasets/  E：问题集 questions.jsonl + 期望来源 expected_sources.jsonl
  * judges/    C：LLM-as-judge prompt 与结果解析（faithfulness / answer_relevance）
  * runners/   B/C：retrieval_eval.py（B 口径）/ answer_eval.py（C 口径）
  * reports/   D：run_experiment 落盘（提交入库，回归对比依据）
"""
