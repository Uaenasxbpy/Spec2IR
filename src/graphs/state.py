from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from utils.file.file import File


# ==================== 全局状态定义 ====================
class GlobalState(BaseModel):
    """全局状态定义"""
    document_file: File = Field(..., description="用户上传的PDF文件")
    document_content: str = Field(default="", description="文档内容")
    document_info: Optional[Dict] = Field(default=None, description="document_info.json内容")
    parameter_sets: Optional[Dict] = Field(default=None, description="parameter_sets.json内容")
    function_index: Optional[Dict] = Field(default=None, description="function_index.json内容")
    function_files: Dict[str, Dict] = Field(default_factory=dict, description="各个算法函数的JSON内容，key为function_id")
    output_directory: str = Field(default="assets/spec_ir", description="输出目录")


# ==================== 图输入输出定义 ====================
class GraphInput(BaseModel):
    """工作流的输入"""
    document_file: File = Field(..., description="用户上传的PDF文件")


class GraphOutput(BaseModel):
    """工作流的输出"""
    output_directory: str = Field(..., description="生成文件的输出目录")
    document_info_path: str = Field(..., description="document_info.json路径")
    parameter_sets_path: str = Field(..., description="parameter_sets.json路径")
    function_index_path: str = Field(..., description="function_index.json路径")


# ==================== 各节点输入输出定义 ====================

# 文档解析节点
class ParseDocumentInput(BaseModel):
    """文档解析节点的输入"""
    document_file: File = Field(..., description="用户上传的PDF文件")


class ParseDocumentOutput(BaseModel):
    """文档解析节点的输出"""
    document_content: str = Field(..., description="文档内容")


# document_info提取节点
class ExtractDocumentInfoInput(BaseModel):
    """document_info提取节点的输入"""
    document_content: str = Field(..., description="文档内容")


class ExtractDocumentInfoOutput(BaseModel):
    """document_info提取节点的输出"""
    document_info: Dict = Field(..., description="document_info.json内容")


# parameter_sets提取节点
class ExtractParameterSetsInput(BaseModel):
    """parameter_sets提取节点的输入"""
    document_content: str = Field(..., description="文档内容")
    document_info: Dict = Field(..., description="document_info.json内容")


class ExtractParameterSetsOutput(BaseModel):
    """parameter_sets提取节点的输出"""
    parameter_sets: Dict = Field(..., description="parameter_sets.json内容")


# function_index提取节点
class ExtractFunctionIndexInput(BaseModel):
    """function_index提取节点的输入"""
    document_content: str = Field(..., description="文档内容")
    document_info: Dict = Field(..., description="document_info.json内容")


class ExtractFunctionIndexOutput(BaseModel):
    """function_index提取节点的输出"""
    function_index: Dict = Field(..., description="function_index.json内容")


# 单函数JSON提取节点
class ExtractSingleFunctionInput(BaseModel):
    """单函数JSON提取节点的输入"""
    document_content: str = Field(..., description="文档内容")
    function_index: Dict = Field(..., description="function_index.json内容")


class ExtractSingleFunctionOutput(BaseModel):
    """单函数JSON提取节点的输出"""
    function_files: Dict[str, Dict] = Field(..., description="各个算法函数的JSON内容，key为function_id")


# 文件保存节点
class SaveFilesInput(BaseModel):
    """文件保存节点的输入"""
    document_info: Dict = Field(..., description="document_info.json内容")
    parameter_sets: Dict = Field(..., description="parameter_sets.json内容")
    function_index: Dict = Field(..., description="function_index.json内容")
    function_files: Dict[str, Dict] = Field(default_factory=dict, description="各个算法函数的JSON内容")


class SaveFilesOutput(BaseModel):
    """文件保存节点的输出"""
    output_directory: str = Field(..., description="输出目录")
    document_info_path: str = Field(..., description="document_info.json路径")
    parameter_sets_path: str = Field(..., description="parameter_sets.json路径")
    function_index_path: str = Field(..., description="function_index.json路径")
