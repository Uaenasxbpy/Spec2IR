import os
import json
from jinja2 import Template
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import ExtractDocumentInfoInput, ExtractDocumentInfoOutput


def extract_document_info_node(state: ExtractDocumentInfoInput, config: RunnableConfig, runtime: Runtime[Context]) -> ExtractDocumentInfoOutput:
    """
    title: 提取文档信息
    desc: 从文档内容中提取document_info.json
    integrations: 大语言模型
    """
    from coze_coding_dev_sdk import LLMClient  # type: ignore
    
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
    user_prompt_content = up_tpl.render({"document_content": state.document_content})
    
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
        max_completion_tokens=llm_config.get("max_completion_tokens", 4096),
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
    try:
        # 尝试从响应中提取JSON
        json_start = text_content.find("{")
        json_end = text_content.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            json_str = text_content[json_start:json_end]
            document_info = json.loads(json_str)
        else:
            document_info = json.loads(text_content)
    except (json.JSONDecodeError, ValueError):
        # 如果解析失败，返回默认结构
        document_info = {
            "document_info": {
                "standard": "",
                "full_title": "",
                "publisher": "",
                "publication_date": "",
                "core_algorithm": ""
            }
        }
    
    return ExtractDocumentInfoOutput(
        document_info=document_info
    )
