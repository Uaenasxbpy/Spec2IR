import os
import json
from jinja2 import Template
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import ExtractSingleFunctionInput, ExtractSingleFunctionOutput


def extract_single_function_node(state: ExtractSingleFunctionInput, config: RunnableConfig, runtime: Runtime[Context]) -> ExtractSingleFunctionOutput:
    """
    title: 提取单函数详情
    desc: 根据function_index逐个提取算法详情
    integrations: 大语言模型
    """
    ctx = runtime.context
    
    # 读取配置文件
    cfg_file = os.path.join(os.getenv("COZE_WORKSPACE_PATH"), config['metadata']['llm_cfg'])
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        _cfg = json.load(fd)
    
    llm_config = _cfg.get("config", {})
    sp = _cfg.get("sp", "")
    up = _cfg.get("up", "")
    
    # 使用jinja2模板渲染提示词
    up_tpl = Template(up)
    user_prompt_content = up_tpl.render({
        "document_content": state.document_content,
        "function_index": json.dumps(state.function_index, ensure_ascii=False)
    })
    
    # 调用大模型
    client = LLMClient(ctx=ctx)
    messages = [
        SystemMessage(content=sp),
        HumanMessage(content=user_prompt_content)
    ]
    
    response = client.invoke(
        messages=messages,
        model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
        temperature=llm_config.get("temperature", 0.2),
        top_p=llm_config.get("top_p", 0.95),
        max_completion_tokens=llm_config.get("max_completion_tokens", 16384),
        thinking=llm_config.get("thinking", "disabled")
    )
    
    # 安全处理响应内容
    text_content = ""
    if isinstance(response.content, str):
        text_content = response.content
    elif isinstance(response.content, list):
        if response.content and isinstance(response.content[0], str):
            text_content = " ".join(response.content)
        else:
            text_parts = [
                item.get("text", "") for item in response.content 
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            text_content = " ".join(text_parts)
    
    # 解析JSON
    function_files = {}
    try:
        # 尝试从响应中提取JSON
        json_start = text_content.find("{")
        json_end = text_content.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            json_str = text_content[json_start:json_end]
            result = json.loads(json_str)
            # 如果返回的是一个包含多个函数的对象
            if isinstance(result, dict):
                # 检查是否是直接的函数文件字典
                has_function_id = any("function_id" in v for v in result.values() if isinstance(v, dict))
                if has_function_id:
                    function_files = result
                else:
                    # 可能是单个函数，尝试从function_index获取function_id
                    functions = state.function_index.get("functions", [])
                    if functions:
                        func_id = functions[0].get("function_id", "alg_001_unknown")
                        function_files[func_id] = result
    except (json.JSONDecodeError, ValueError):
        # 如果解析失败，返回空字典
        pass
    
    return ExtractSingleFunctionOutput(
        function_files=function_files
    )
