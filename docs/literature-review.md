# 文献综述笔记：多智能体协作与 RAG 的多模态事实核验

> 用途：撰写毕业设计论文「相关工作 / 文献综述」章节的素材。
> 每条资料含：核心内容、与本系统的关系、可借鉴点。文末附对比表与可引用的参考文献信息。

---

## 一、Agent 编排框架

### 1. LangGraph（LangChain 官方，低层 Agent 编排框架）
- **来源**：https://github.com/langchain-ai/langgraph
- **核心定位**：面向「长时间运行、有状态 Agent」的低层编排框架（low-level orchestration framework for stateful agents）。
- **关键能力**（与本系统直接相关）：
  - **Durable execution（持久执行）**：Agent 可跨失败持久化，从断点自动恢复——对应本系统的状态记忆需求。
  - **Human-in-the-loop（人工介入）**：可在执行任意节点检查/修改状态——对应本系统的人工复核机制。
  - **Comprehensive memory（综合记忆）**：区分「短期工作记忆」（单次推理上下文）与「长期持久记忆」（跨会话）——这正是本系统补充 SQLite checkpointer 的依据。
  - **StateGraph**：以「节点 + 边 + 条件边」建模工作流，状态在节点间流转。
- **与本系统的关系**：本系统用 LangGraph `StateGraph` 编排 5 个 Agent（拆解→规划→获取→评估→重排序→结论），并用其 SQLite checkpointer 实现状态持久化与恢复。
- **可借鉴点**：正式区分「短期记忆 vs 长期记忆」的表述；把人工复核描述为 human-in-the-loop 的实例。

### 2. LangChain 多 Agent 官方教程
- **来源**：https://docs.langchain.com/oss/python/langchain/multi-agent
- **核心内容**：多 Agent 协作的常见编排模式——**supervisor（监督者分派）**、**handoff（任务移交）**、**swarm（群体协作）**等；对比单 Agent 在多步、多工具任务上的局限。
- **与本系统的关系**：本系统采用「固定流水线 + 分工协作」的多 Agent 模式，每个 Agent 负责核验流程的一个子任务（拆解、规划、获取、评估、结论），等价于一种**结构化的 handoff 编排**。
- **可借鉴点**：论文中可用「多 Agent 分工协作优于单 Agent 全包」作为动机，并说明为何选择流水线而非 supervisor 动态分派（可解释性、可控性更强）。

### 3. LangGraph 图工作流 API 文档
- **来源**：https://docs.langchain.com/oss/python/langgraph/graph-api
- **核心内容**：`StateGraph`、`node`、`edge`、条件边（conditional edge）、`checkpointer`（状态持久化）、状态通道与 reducer（如本系统的 `Annotated[list, add]` 追加语义）等 API 语义。
- **与本系统的关系**：本系统的 `agents/state.py`（`VerdictState` TypedDict + reducer）、`agents/graph.py`（6 节点串行图 + checkpointer）即基于此 API 实现。
- **可借鉴点**：论文技术实现章节可直接引用「基于 LangGraph StateGraph + checkpointer 实现有状态的多 Agent 工作流」。

---

## 二、多 Agent / RAG 事实核验相关工作

### 4. FactAgent（面向证据检索的多 Agent 事实核验）
- **来源**：https://github.com/HySonLab/FactAgent ；论文 Trinh et al., 2025, arXiv:2506.17878《Towards Robust Fact-Checking: A Multi-Agent System with Advanced Evidence Retrieval》
- **核心内容**：
  - 一个多 Agent 事实核验系统，结合**高级证据检索**验证跨领域事实声明。
  - Prompt 分模块：`input_ingestion`（输入摄取）、`query_generation`（查询生成）、`evidence_seeking`（证据搜寻）、`verdict_prediction`（结论预测）——与本系统 Agent 划分高度同构。
  - 多种推理方法做实验：`direct`、`cot`（链式思考）、`folk`、`sase`。
  - 检索用 **Serper API**（商业搜索），数据集 **HoVer / Feverous / SciFact-Open**。
- **与本系统的关系**：与本系统是**最直接的可比工作**——同为多 Agent 事实核验、同样的「拆解→查询→证据→结论」流程。区别在于：本系统加入多模态（截图/图片）+ 来源可信度评估 + 证据重排序 + 人工复核，且面向中文低风险场景。
- **可借鉴点**：论文「相关工作」中必须引用此文并说明差异（多模态扩展、来源过滤、中文场景、三类结论而非 SUPPORT/REFUTE 二分类）。

### 5. Multimodal Fact-Checking（MCVE：多模态事实核验与解释框架）
- **来源**：https://github.com/sonlam1102/multimodal-fact-checking ；论文 Luu et al., 2025, Multimedia Systems 31(3)《MCVE: multimodal claim verification and explanation framework for fact-checking system》
- **核心内容**：把多模态事实核验拆为三个子任务——
  1. **Multimodal Evidence Retrieval**（多模态证据检索）
  2. **Multimodal Claim Verification**（多模态声明核验）
  3. **Claim Truthfulness Explanation**（真实性解释）
  - 数据集：**Mocheg**、**Factify**；文本编码用 BERT/RoBERTa + Longformer/BigBird，图像编码用 ViT/DEiT。
- **与本系统的关系**：印证了「多模态事实核验」的子任务划分（证据检索→核验→解释）与本系统的流水线一致；本系统用大模型（Qwen-VL）替代其独立训练的编码器，降低了训练成本。
- **可借鉴点**：论文可引用其「三子任务」框架，说明本系统对应覆盖了前两者（检索 + 核验）并以可追溯证据链部分实现了「解释」；其数据集（Mocheg/Factify）可作为英文多模态评测的对照。

### 6. Automated Fact-Checking Resources（自动事实核验资源汇总）
- **来源**：https://github.com/Cartus/Automated-Fact-Checking-Resources
- **核心内容**：自动事实核验领域的**资源索引**，汇总数据集、模型、综述论文与工具。
- **与本系统的关系**：作为选题调研时的领域地图；本系统的测试集设计（三域 + 三标签）参考了 FEVER 系列任务的标签与评测思路。
- **可借鉴点**：论文可引用其为「领域资源梳理」的入口，佐证选题的系统性。

### 7. FEVER（Fact Extraction and VERification）
- **来源**：https://fever.ai/
- **核心内容**：事实核验领域最权威的**基准与评测任务**系列，数据集/共享任务逐年演进：
  - FEVER (2018) → FEVER 2.0 (2019) → FEVEROUS (2021，含表格) → AVeriTeC (2024，真实性归因) → AVeriTeC 2.0 (2025) → **AVerImaTeC (2026，图像-文本声明核验，证据来自网络)**。
  - FEVER 系列定义了「claim 分类为 SUPPORTED / REFUTED / NOT ENOUGH INFO」的三分类范式。
- **与本系统的关系**：
  - 本系统的「支持 / 反驳 / 证据不足」三类结论**直接对齐 FEVER 的三分类范式**。
  - FEVER9 (2026) 的 **AVerImaTeC 图像-文本声明核验任务**与本系统的多模态核验目标高度契合，是本系统最贴近的领域前沿。
- **可借鉴点**：论文中应以 FEVER 三分类为评测范式的出处，说明结论类别设计的合理性；并提及 AVerImaTeC 体现的多模态核验趋势。

### 8. RAG 证据支持的事实核验（Singal et al., FEVER 2024）
- **来源**：https://aclanthology.org/2024.fever-1.10/ ；Singal, Patwa, Patwa, Chadha, Das, 2024《Evidence-backed Fact Checking using RAG and Few-Shot In-Context Learning with LLMs》
- **核心内容**：
  - 面向社交媒体的自动事实核验，用 **Averitec** 数据集评估。
  - 方法：**RAG 流水线**从知识库检索相关证据句，连同声明一起输入 LLM 做分类；评估了多个 LLM 的 **few-shot In-Context Learning (ICL)** 能力。
  - 结果：Averitec 分数 0.33，较基线**绝对提升 22%**。
- **与本系统的关系**：是本系统「RAG + LLM 事实核验」最直接的方法论依据——同样的「检索证据 → 输入 LLM 判定」范式。本系统在此基础上叠加多 Agent 分工、多模态输入、来源可信度过滤与证据重排序。
- **可借鉴点**：论文中引用此工作说明 RAG 在事实核验中的有效性（22% 提升），并指出本系统的增量（多 Agent 协作 + 多模态 + 来源过滤）。

---

## 三、相关工作对比表

| 工作 | 多 Agent | RAG 证据 | 多模态 | 来源过滤/重排序 | 三类结论 | 人工复核 | 中文场景 |
|---|---|---|---|---|---|---|---|
| **FactAgent (2025)** | ✅ | ✅ (Serper) | ❌ | 部分 | 二分类 | ❌ | ❌ |
| **MCVE (2025)** | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Singal et al. (FEVER 2024)** | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **本系统** | ✅ (5 Agent) | ✅ (Tavily+Chroma) | ✅ (Qwen-VL) | ✅ | ✅ | ✅ | ✅ |

> 本系统的差异点可归纳为：**多 Agent 分工 + 多模态输入 + 来源可信度评估与证据重排序 + 三类结论 + 人工复核 + 中文低风险场景**。

---

## 四、可直接引用的参考文献

```bibtex
% LangGraph
@misc{langgraph,
  title = {{LangGraph}: Low-level orchestration framework for building stateful agents},
  author = {{LangChain}},
  howpublished = {\url{https://github.com/langchain-ai/langgraph}}
}

% FactAgent
@misc{trinh2025robust,
  title = {Towards Robust Fact-Checking: A Multi-Agent System with Advanced Evidence Retrieval},
  author = {Tam Trinh and Manh Nguyen and Truong-Son Hy},
  year = {2025},
  eprint = {2506.17878},
  archivePrefix = {arXiv},
  primaryClass = {cs.AI}
}

% MCVE
@article{luu2025mcve,
  title = {MCVE: multimodal claim verification and explanation framework for fact-checking system},
  author = {Luu, Son T and Vo, Trung and Nguyen, Le-Minh},
  journal = {Multimedia Systems},
  volume = {31}, number = {3}, pages = {1--24}, year = {2025},
  publisher = {Springer}
}

% RAG evidence-backed fact checking
@inproceedings{singal-etal-2024-evidence,
  title = {Evidence-backed Fact Checking using {RAG} and Few-Shot In-Context Learning with {LLM}s},
  author = {Singal, Ronit and Patwa, Pransh and Patwa, Parth and Chadha, Aman and Das, Amitava},
  booktitle = {Proceedings of the Seventh Fact Extraction and VERification Workshop (FEVER)},
  pages = {91--98}, year = {2024}, address = {Miami, Florida, USA},
  publisher = {Association for Computational Linguistics}
}

% FEVER
@inproceedings{thorne2018fever,
  title = {FEVER: a Large-scale Dataset for Fact Extraction and VERification},
  author = {Thorne, James and Vlachos, Andreas and Christodoulopoulos, Christos and Mittal, Arpit},
  booktitle = {NAACL-HLT}, year = {2018}
}
```
