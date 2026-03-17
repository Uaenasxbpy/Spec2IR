import os
from utils.file.file import FileOps
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import ParseDocumentInput, ParseDocumentOutput


def parse_document_node(state: ParseDocumentInput, config: RunnableConfig, runtime: Runtime[Context]) -> ParseDocumentOutput:
    """
    title: 文档解析
    desc: 读取用户上传的PDF文档内容
    """
    ctx = runtime.context
    
    try:
        # 使用FileOps提取PDF文本内容
        text_content = FileOps.extract_text(state.document_file)
        
        return ParseDocumentOutput(
            document_content=text_content
        )
    except Exception as e:
        # 如果提取失败，返回空内容，让后续节点处理
        return ParseDocumentOutput(
            document_content=""
        )
