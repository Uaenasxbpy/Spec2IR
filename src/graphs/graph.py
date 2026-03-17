from langgraph.graph import StateGraph, END
from graphs.state import (
    GlobalState,
    GraphInput,
    GraphOutput
)
from graphs.nodes.parse_document_node import parse_document_node
from graphs.nodes.extract_document_info_node import extract_document_info_node
from graphs.nodes.extract_parameter_sets_node import extract_parameter_sets_node
from graphs.nodes.extract_function_index_node import extract_function_index_node
from graphs.nodes.extract_single_function_node import extract_single_function_node
from graphs.nodes.save_files_node import save_files_node


# 创建状态图，指定工作流的入参和出参
builder = StateGraph(GlobalState, input_schema=GraphInput, output_schema=GraphOutput)

# 添加节点
builder.add_node(
    "parse_document", 
    parse_document_node
)
builder.add_node(
    "extract_document_info", 
    extract_document_info_node, 
    metadata={"type": "agent", "llm_cfg": "config/document_info_extraction_cfg.json"}
)
builder.add_node(
    "extract_parameter_sets", 
    extract_parameter_sets_node, 
    metadata={"type": "agent", "llm_cfg": "config/parameter_sets_extraction_cfg.json"}
)
builder.add_node(
    "extract_function_index", 
    extract_function_index_node, 
    metadata={"type": "agent", "llm_cfg": "config/function_index_extraction_cfg.json"}
)
builder.add_node(
    "extract_single_function", 
    extract_single_function_node, 
    metadata={"type": "agent", "llm_cfg": "config/single_function_extraction_cfg.json"}
)
builder.add_node(
    "save_files", 
    save_files_node
)

# 设置入口点
builder.set_entry_point("parse_document")

# 添加边
builder.add_edge("parse_document", "extract_document_info")
builder.add_edge("extract_document_info", "extract_parameter_sets")
builder.add_edge("extract_parameter_sets", "extract_function_index")
builder.add_edge("extract_function_index", "extract_single_function")
builder.add_edge("extract_single_function", "save_files")
builder.add_edge("save_files", END)

# 编译图
main_graph = builder.compile()
