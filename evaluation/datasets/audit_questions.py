"""
问题集审核脚本 - 对照 struct_v1.jsonl 的地面真值
"""
import json
from pathlib import Path


def load_questions():
    """加载 questions.jsonl"""
    questions = []
    with open("evaluation/datasets/questions.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
    return questions


def load_struct_v1():
    """加载 struct_v1.jsonl 作为地面真值"""
    nodes = []
    with open("data/processed/struct_v1.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                nodes.append(json.loads(line))
    return nodes


def check_question_accuracy(question, nodes):
    """检查问题的页码准确性"""
    question_id = question["id"]
    question_text = question["question"]
    
    # 在 struct_v1.jsonl 中查找相关内容（使用关键词匹配）
    relevant_nodes = []
    keywords = question_text.split()[:5]  # 取前 5 个关键词
    
    for node in nodes:
        node_text = node.get("text", "")
        node_title = node.get("metadata", {}).get("title", "")
        section = node.get("metadata", {}).get("section_path", "")
        
        # 检查是否包含关键词或标题匹配
        if any(kw.lower() in node_text.lower() for kw in keywords):
            relevant_nodes.append(node)
        elif question_text.lower() in node_text.lower():
            relevant_nodes.append(node)
        elif question_id in node.get("metadata", {}).get("node_ids", []):
            relevant_nodes.append(node)
    
    if not relevant_nodes:
        return {
            "question_id": question_id,
            "status": "NO_MATCH",
            "message": f"在 struct_v1.jsonl 中未找到相关内容",
            "suggested_pages": []
        }
    
    # 提取页码信息（从 metadata 中获取）
    page_ranges = []
    for node in relevant_nodes[:3]:  # 取前 3 个匹配
        metadata = node.get("metadata", {})
        printed_page = metadata.get("printed_page_start", "N/A")
        physical_page = metadata.get("physical_page_start", "N/A")
        section = metadata.get("section_path", "")
        title = metadata.get("title", "")
        
        page_ranges.append({
            "printed_page": str(printed_page) if printed_page != "N/A" else "N/A",
            "physical_page": str(physical_page) if physical_page != "N/A" else "N/A",
            "section": section,
            "title": title,
            "node_id": node.get("chunk_id", "")[:80] + "..."
        })
    
    return {
        "question_id": question_id,
        "status": "FOUND",
        "message": f"找到 {len(relevant_nodes)} 个相关节点",
        "suggested_pages": page_ranges
    }


def audit_all_questions():
    """审核所有问题"""
    questions = load_questions()
    nodes = load_struct_v1()
    
    print("=" * 80)
    print("问题集审核报告")
    print("=" * 80)
    print()
    
    results = []
    for q in questions:
        result = check_question_accuracy(q, nodes)
        results.append(result)
        status = result["status"]
        print(f"[{status}] {q['id']}: {q['question'][:50]}...")
        if status == "FOUND":
            for page in result["suggested_pages"][:2]:  # 显示前 2 个匹配
                print(f"    - 印刷页：{page['printed_page']}, 章节：{page['section'][:60]}...")
    
    print()
    print("=" * 80)
    print("审核完成")
    print("=" * 80)
    
    # 保存结果
    with open("evaluation/datasets/audit_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return results


if __name__ == "__main__":
    audit_all_questions()
