"""评测域（成员 C 口径 + D 执行 + E 数据集）。

目录约定（指南 §6 / 项目目录树）：
  * datasets/  E：问题集 questions.jsonl + 期望来源 expected_sources.jsonl
  * judges/    C：LLM-as-judge prompt 与结果解析（faithfulness / answer_relevance）
  * runners/   B/C：retrieval_eval.py（B 口径）/ answer_eval.py（C 口径）
  * reports/   D：run_experiment 落盘（提交入库，回归对比依据）
"""
