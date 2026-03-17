import os
import json
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import SaveFilesInput, SaveFilesOutput


def save_files_node(state: SaveFilesInput, config: RunnableConfig, runtime: Runtime[Context]) -> SaveFilesOutput:
    """
    title: 保存文件
    desc: 将所有生成的JSON文件保存到指定目录
    """
    ctx = runtime.context
    
    # 输出目录 - 保存到项目的assets目录
    workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
    output_dir = os.path.join(workspace_path, "assets", "spec_ir")
    functions_dir = os.path.join(output_dir, "functions")
    
    # 创建目录
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(functions_dir, exist_ok=True)
    
    # 保存document_info.json
    document_info_path = os.path.join(output_dir, "document_info.json")
    with open(document_info_path, 'w', encoding='utf-8') as f:
        json.dump(state.document_info, f, ensure_ascii=False, indent=2)
    
    # 保存parameter_sets.json
    parameter_sets_path = os.path.join(output_dir, "parameter_sets.json")
    with open(parameter_sets_path, 'w', encoding='utf-8') as f:
        json.dump(state.parameter_sets, f, ensure_ascii=False, indent=2)
    
    # 保存function_index.json
    function_index_path = os.path.join(output_dir, "function_index.json")
    with open(function_index_path, 'w', encoding='utf-8') as f:
        json.dump(state.function_index, f, ensure_ascii=False, indent=2)
    
    # 保存各个函数文件
    for function_id, function_data in state.function_files.items():
        function_file_path = os.path.join(functions_dir, f"{function_id}.json")
        with open(function_file_path, 'w', encoding='utf-8') as f:
            json.dump(function_data, f, ensure_ascii=False, indent=2)
    
    return SaveFilesOutput(
        output_directory=output_dir,
        document_info_path=document_info_path,
        parameter_sets_path=parameter_sets_path,
        function_index_path=function_index_path
    )
