## 项目概述
- **名称**: 标准文档算法提取 Agent
- **功能**: 从标准文档（通常为 PDF）中严格按约定 JSON 格式提取算法信息，包括文档元信息、参数集、算法索引和各算法详情，保存为多个独立文件

### 节点清单
| 节点名 | 文件位置 | 类型 | 功能描述 | 分支逻辑 | 配置文件 |
|-------|---------|------|---------|---------|---------|
| parse_document | `src/graphs/nodes/parse_document_node.py` | task | 读取用户上传的PDF文档内容 | - | - |
| extract_document_info | `src/graphs/nodes/extract_document_info_node.py` | agent | 从文档内容中提取document_info.json | - | `config/document_info_extraction_cfg.json` |
| extract_parameter_sets | `src/graphs/nodes/extract_parameter_sets_node.py` | agent | 从文档内容中提取parameter_sets.json | - | `config/parameter_sets_extraction_cfg.json` |
| extract_function_index | `src/graphs/nodes/extract_function_index_node.py` | agent | 从文档内容中提取function_index.json | - | `config/function_index_extraction_cfg.json` |
| extract_single_function | `src/graphs/nodes/extract_single_function_node.py` | agent | 根据function_index逐个提取算法详情 | - | `config/single_function_extraction_cfg.json` |
| save_files | `src/graphs/nodes/save_files_node.py` | task | 将所有生成的JSON文件保存到指定目录 | - | - |

**类型说明**: task(task节点) / agent(大模型) / condition(条件分支) / looparray(列表循环) / loopcond(条件循环)

## 子图清单
| 子图名 | 文件位置 | 功能描述 | 被调用节点 |
|-------|---------|------|---------|-----------|
| 无 | - | - | - |

## 技能使用
- 节点`extract_document_info`使用技能大语言模型
- 节点`extract_parameter_sets`使用技能大语言模型
- 节点`extract_function_index`使用技能大语言模型
- 节点`extract_single_function`使用技能大语言模型
